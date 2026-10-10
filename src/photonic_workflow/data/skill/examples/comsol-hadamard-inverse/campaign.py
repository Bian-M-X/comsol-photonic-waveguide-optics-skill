"""Sequential, bounded native inverse-design campaign; default is JSON plan only.

All scientific results come from fresh execution receipts and independent
analysis. This driver does not promise a successful design or use a GPU.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import subprocess
import sys
import time
from decimal import Decimal
from pathlib import Path

LOW, HIGH = 0.44, 0.53
MAX_STEP = 0.02
REPEAT_TOLERANCE = 1e-6
BINARY_CANDIDATES = 6
TRAINING_WAVELENGTHS = (1520.0, 1536.61, 1550.0, 1565.0, 1580.0)
HOLDOUT_WAVELENGTHS = (1543.3, 1572.3)
STATES = ("zero", "one", "plus", "minus", "plus_i", "minus_i")
_RUNNER_SPEC = importlib.util.spec_from_file_location("hadamard_native_runner", Path(__file__).with_name("run.py"))
_RUNNER = importlib.util.module_from_spec(_RUNNER_SPEC)
_RUNNER_SPEC.loader.exec_module(_RUNNER)


class CostOverrun(RuntimeError):
    """Observed work exceeded the threshold; retain evidence and stop native jobs."""


def optimization_cost_prechecks(receipt, batch, config, training):
    actual = _RUNNER.parse_optimization_trace(batch, config)
    if receipt.get("optimization_cost") != actual or receipt.get("optimization_cost_error"):
        raise RuntimeError("Missing or inconsistent native optimization cost receipt")
    if not actual["completed_requested_stages"]:
        raise RuntimeError("Native optimization trace has incomplete or mismatched requested stages")
    for stage in actual["stages"]:
        if stage["outer_iterations"] > config["iterations"]:
            raise RuntimeError("Native optimization outer iterations exceed requested bound")
        last = stage["rows"][-1]
        minimum = training["training_stages"][stage["stage"]]["minimum"]["objective"]
        rounding = Decimal(last["objective_text"]).as_tuple().exponent
        if abs(last["objective_rounded"] - minimum) > 0.5 * 10 ** rounding + 1e-10:
            raise RuntimeError("Rounded optimization trace objective contradicts training minimum")
    return actual


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path):
    def reject(value):
        raise ValueError(f"Nonfinite JSON constant: {value}")

    return json.loads(path.read_text(encoding="utf-8"), parse_constant=reject)


def imbalance(report):
    ratios = report["both_input_split_ratios"]
    if len(ratios) != 2:
        raise ValueError("Need two split ratios")
    if any(value is None for value in ratios):
        return None
    if any(isinstance(value, bool) or not math.isfinite(value) or value < 0 for value in ratios):
        raise ValueError("Invalid split ratio")
    if any(value == 0 for value in ratios):
        return None
    return 0.5 * (math.log(ratios[0]) - math.log(ratios[1]))


def propose_threshold(history):
    """Six observed trials; bracketed secant or a step from the best finite anchor."""
    if len(history) >= BINARY_CANDIDATES:
        raise ValueError("Binary candidate budget exhausted")
    if not history:
        return 0.5
    for row in history:
        if (
            isinstance(row["threshold"], bool)
            or not isinstance(row["threshold"], (int, float))
            or not math.isfinite(row["threshold"])
            or not LOW <= row["threshold"] <= HIGH
        ):
            raise ValueError("Invalid threshold history")
        if row["f"] is not None and (
            isinstance(row["f"], bool) or not isinstance(row["f"], (int, float)) or not math.isfinite(row["f"])
        ):
            raise ValueError("Invalid imbalance history")
    previous = [row["threshold"] for row in history]
    if any(abs(a - b) <= REPEAT_TOLERANCE for index, a in enumerate(previous) for b in previous[:index]):
        raise ValueError("Repeated threshold history")
    observed = [row for row in history if row["f"] is not None]
    anchor = min(observed, key=lambda row: (abs(row["f"]), row["threshold"])) if observed else history[0]
    lower, upper = max(LOW, anchor["threshold"] - MAX_STEP), min(HIGH, anchor["threshold"] + MAX_STEP)

    def usable(value):
        return (
            math.isfinite(value)
            and lower <= value <= upper
            and all(abs(value - old) > REPEAT_TOLERANCE for old in previous)
        )

    if len(history) < 3:
        probe = (0.5, 0.495, 0.505)[len(history)]
        if usable(probe):
            return probe

    def secant(a, b):
        difference = b["f"] - a["f"]
        if not math.isfinite(difference) or abs(difference) <= 1e-8:
            return None
        value = b["threshold"] - (b["f"] / difference) * (b["threshold"] - a["threshold"])
        return value if math.isfinite(value) else None

    ordered = sorted(observed, key=lambda row: row["threshold"])
    brackets = [
        (a, b) for index, a in enumerate(ordered) for b in ordered[index + 1 :]
        if a["f"] < 0 < b["f"] or b["f"] < 0 < a["f"]
    ]
    if brackets:
        a, b = min(brackets, key=lambda pair: (
            pair[1]["threshold"] - pair[0]["threshold"], pair[0]["threshold"], pair[1]["threshold"]
        ))
        value = secant(a, b)
        if value is not None and a["threshold"] < value < b["threshold"] and usable(value):
            return value
        # Midpoint of the bracket's feasible part still obeys the anchor step.
        lower, upper = max(lower, a["threshold"]), min(upper, b["threshold"])
        midpoint = lower + (upper - lower) / 2
        if lower < upper and a["threshold"] < midpoint < b["threshold"] and usable(midpoint):
            return midpoint
        raise ValueError("No fresh threshold inside the observed bracket and anchor step")

    neighbors = sorted(
        (row for row in observed if row is not anchor and abs(row["f"] - anchor["f"]) > 1e-8),
        key=lambda row: (abs(row["threshold"] - anchor["threshold"]), row["threshold"]),
    )
    proposals = []
    if neighbors:
        value = secant(neighbors[0], anchor)
        if value is not None:
            proposals.append(min(upper, max(lower, value)))
    # Fallback selects only fresh design inputs, never invented function values.
    proposals.extend(
        anchor["threshold"] + offset for offset in (-0.005, 0.005, -0.01, 0.01, -0.015, 0.015, -0.02, 0.02)
    )
    proposals.extend(
        lower + (upper - lower) * index / (BINARY_CANDIDATES + 1) for index in range(1, BINARY_CANDIDATES + 1)
    )
    for value in proposals:
        if usable(value):
            return value
    raise ValueError("No fresh threshold available within declared bounds/step")


def select_candidate(history):
    passing = [
        row for row in history if row["acceptance_pass"] is True and row["f"] is not None and math.isfinite(row["f"])
    ]
    return min(passing, key=lambda row: abs(row["f"])) if passing else None


def convergence(reference, comparison):
    groups = {
        "eta": (
            [reference["six_states"][state]["target_throughput"] for state in STATES],
            [comparison["six_states"][state]["target_throughput"] for state in STATES],
            0.005,
        ),
        "all_input_eta": (
            [reference["minimum_target_throughput_all_inputs"]],
            [comparison["minimum_target_throughput_all_inputs"]],
            0.005,
        ),
        "fidelity": (
            [reference["min_six_state_conditional_fidelity"], reference["conditional_choi_overlap"]],
            [comparison["min_six_state_conditional_fidelity"], comparison["conditional_choi_overlap"]],
            0.002,
        ),
        "ratio": (reference["both_input_split_ratios"], comparison["both_input_split_ratios"], 0.02),
    }
    result = {}
    for name, (a, b, tolerance) in groups.items():
        if len(a) != len(b) or any(v is None or isinstance(v, bool) or not math.isfinite(v) for v in [*a, *b]):
            raise ValueError("Invalid convergence metric")
        difference = max(abs(x - y) for x, y in zip(a, b, strict=True))
        result[name] = {"max_absolute_change": difference, "tolerance": tolerance, "pass": difference <= tolerance}
    result["pass"] = all(item["pass"] for item in result.values())
    return result


def expected_objective(config):
    """Exact reviewed native expression; reject a different objective/profile."""
    profile = config.get("objective_profile", "coherent")
    if profile not in ("coherent", "state_floor"):
        raise RuntimeError("Unsupported optimization objective profile")
    a, b = "comp1.ewfd.S31", "comp1.ewfd.S41"
    if config.get("boundary_model", "exterior_modal") == "slit_pml":
        a, b = "comp1.modal_a3", "comp1.modal_a4"
    target, error = f"({a}-i*{b})", f"({a}+i*{b})"
    expression = f"(realdot({target},{target})-(gate_weight-1)*realdot({error},{error}))/2"
    if profile == "state_floor":
        expression += f"-sqrt(4*realdot({a},{b})^2+1e-8)"
    return expression


def training_components(receipt, lines, config, stages):
    """Rescore stored raw amplitudes without another licensed postprocessing job."""
    raw = [line for line in lines if line.startswith("TRAINING_MODAL=")]
    if not raw and not receipt.get("training_modal_observations"):
        return {"available": False, "reason": "Legacy log has no raw training modal amplitudes"}
    if raw != receipt.get("training_modal_observations"):
        raise RuntimeError("Missing or inconsistent training modal receipt")
    derived = {stage: {"points": []} for stage in stages}
    for line in raw:
        try:
            parts = line.split("=", 1)[1].split(",")
            if len(parts) != 6:
                raise ValueError("Expected stage, wavelength and two complex amplitudes")
            stage = int(parts[0])
            wavelength, ar, ai, br, bi = map(float, parts[1:])
            if stage not in stages or not all(math.isfinite(v) for v in (wavelength, ar, ai, br, bi)):
                raise ValueError("Invalid training modal stage/value")
            eta = ar * ar + ai * ai + br * br + bi * bi
            wrong = ((ar - bi) ** 2 + (ai + br) ** 2) / 2
            cross = ar * br + ai * bi
            floor_penalty = math.sqrt(4 * cross * cross + 1e-8)
            coherent = eta - config["fidelity_weight"] * wrong
            state_floor = coherent - floor_penalty
            minimum_surrogate = eta - 2 * abs(cross)
            if not all(math.isfinite(v) for v in (eta, wrong, cross, floor_penalty, coherent, state_floor,
                                                  minimum_surrogate)):
                raise ValueError("Nonfinite derived training component")
        except (ValueError, OverflowError, KeyError) as error:
            raise RuntimeError("Malformed training modal observation") from error
        match = [point for point in stages[stage]["points"] if abs(point["wavelength_nm"] - wavelength) <= 1e-6]
        if len(match) != 1 or any(abs(p["wavelength_nm"] - wavelength) <= 1e-6 for p in derived[stage]["points"]):
            raise RuntimeError("Training modal wavelength missing, duplicated, or mismatched")
        expected = state_floor if config.get("objective_profile", "coherent") == "state_floor" else coherent
        if abs(expected - match[0]["objective"]) > 1e-9 * max(1.0, abs(expected)):
            raise RuntimeError("Raw training amplitudes contradict native objective")
        derived[stage]["points"].append({
            "wavelength_nm": wavelength, "a": [ar, ai], "b": [br, bi],
            "target_throughput_input1": eta, "wrong_superposition_power": wrong,
            "real_cross_overlap": cross, "state_floor_penalty": floor_penalty,
            "coherent_objective": coherent, "state_floor_objective": state_floor,
            "mirror_all_input_throughput_surrogate": minimum_surrogate,
        })
    for stage, record in derived.items():
        if len(record["points"]) != len(stages[stage]["points"]):
            raise RuntimeError("Missing training modal stage/frequency observations")
        record["minima"] = {key: min(point[key] for point in record["points"]) for key in (
            "target_throughput_input1", "coherent_objective", "state_floor_objective",
            "mirror_all_input_throughput_surrogate",
        )}
    return {
        "available": True, "training_stages": derived,
        "scope": "One training input; mirror all-input value is a symmetry surrogate, not measured two-column "
                 "acceptance. Common rescoring compares objectives without changing the physical gates.",
    }


def optimization_prechecks(receipt, console, config):
    """Require recorded native objective readback and actual per-stage values."""
    lines = console.splitlines()
    markers = [line for line in lines if line.startswith("OPTIMIZATION_OBJECTIVE_VERIFIED=")]
    band = config["training_band"]
    if band not in ("single", "three", "five"):
        raise RuntimeError("Unsupported optimization training band")
    aggregation = "auto" if band == "single" else "min"
    expected = f"OPTIMIZATION_OBJECTIVE_VERIFIED={aggregation},{expected_objective(config)}"
    if markers != [expected]:
        raise RuntimeError("Missing or incompatible native optimization objective readback")
    controls = [line.split("=", 1)[1] for line in lines if line.startswith("OPTIMIZER_CONTROLS_VERIFIED=")]
    if len(controls) != 1:
        raise RuntimeError("Missing or repeated optimizer control readback")
    try:
        method, move, evaluations = controls[0].split(",")
        move, evaluations = float(move), int(evaluations)
    except (ValueError, TypeError) as error:
        raise RuntimeError("Malformed optimizer control readback") from error
    if (
        method != config.get("optimizer", "mma")
        or not math.isfinite(move)
        or abs(move - config.get("move_limit", 0.05)) > 1e-12
        or evaluations != config.get("evaluation_limit", 1000)
    ):
        raise RuntimeError("Optimizer control readback does not match requested tuning")
    observations = receipt.get("training_observations")
    recorded = [line for line in lines if line.startswith(("TRAINING_POINT=", "TRAINING_MINIMUM="))]
    if not isinstance(observations, list) or observations != recorded or not observations:
        raise RuntimeError("Missing or inconsistent native training observations")
    expected_wavelengths = (
        list(TRAINING_WAVELENGTHS)
        if band == "five"
        else [1520.0, 1550.0, 1580.0]
        if band == "three"
        else [config["wavelength_nm"]]
    )
    stages = {stage: {"points": [], "minimum": None} for stage in range(1, config["stages"] + 1)}
    for line in observations:
        kind, text = line.split("=", 1)
        parts = text.split(",")
        if len(parts) != 3:
            raise RuntimeError("Malformed training observation")
        stage = int(parts[0])
        wavelength, value = map(float, parts[1:])
        if stage not in stages or not math.isfinite(wavelength) or not math.isfinite(value):
            raise RuntimeError("Invalid training observation stage/value")
        observation = {"wavelength_nm": wavelength, "objective": value}
        if kind == "TRAINING_POINT":
            stages[stage]["points"].append(observation)
        elif stages[stage]["minimum"] is not None:
            raise RuntimeError("Repeated training minimum")
        else:
            stages[stage]["minimum"] = observation
    for stage in stages.values():
        points, minimum = stage["points"], stage["minimum"]
        actual = sorted(point["wavelength_nm"] for point in points)
        if len(actual) != len(expected_wavelengths) or any(
            abs(a - b) > 1e-6 for a, b in zip(actual, sorted(expected_wavelengths), strict=True)
        ):
            raise RuntimeError("Training wavelengths missing, duplicated, or mismatched")
        if minimum is None or abs(minimum["objective"] - min(point["objective"] for point in points)) > 1e-10:
            raise RuntimeError("Recorded training minimum is inconsistent")
        if not any(
            abs(point["wavelength_nm"] - minimum["wavelength_nm"]) <= 1e-6
            and abs(point["objective"] - minimum["objective"]) <= 1e-10
            for point in points
        ):
            raise RuntimeError("Training minimum active wavelength is inconsistent")
    return {
        "objective_readback": markers[0],
        "optimizer_controls": {"method": method, "move_limit": move, "evaluation_limit_per_stage": evaluations},
        "training_stages": stages,
        "objective_components": training_components(receipt, lines, config, stages),
        "scope": "Exact native objective/aggregation and per-frequency values; not a multi-frequency gradient proof",
    }


def plan():
    base = {
        "wavelength_nm": 1550,
        "mesh_um": 0.045,
        "rf_um": 0.05,
        "beta": 2,
        "eps_core": 12.1,
        "eps_clad": 2.1,
        "guided_modes": 2,
        "outer_half_um": 3.15,
        "port_half_um": 1.5,
        "cladding_mesh_um": 0.10,
        "fidelity_weight": 10,
        "training_band": "single",
        "objective_profile": "coherent",
        "optimizer": "mma",
        "move_limit": 0.05,
        "boundary_model": "slit_pml",
        "pml_thickness_um": 0.8,
        "pml_scale": 1,
        "pml_curvature": 3,
        "projection_offset_um": 0.2,
    }
    mesh020 = {"mesh_um": 0.02, "cladding_mesh_um": 0.08}
    mesh015 = {"mesh_um": 0.015, "cladding_mesh_um": 0.06}
    validation = [("mesh020", mesh020), ("mesh015", mesh015)]
    roles = {
        "mesh020": "Joint core/cladding mesh refinement at 1550 nm",
        "mesh015": "Joint core/cladding mesh refinement at 1550 nm",
    }
    # Names retain the existing endpoint/1536.61 nm conventions.
    names = {1520.0: "wave1520", 1536.61: "wave1536", 1550.0: "mesh020", 1565.0: "wave1565", 1580.0: "wave1580"}
    for wavelength in TRAINING_WAVELENGTHS:
        if wavelength == 1550:
            continue
        name = names[wavelength]
        validation.append((name, mesh020 | {"wavelength_nm": wavelength}))
        roles[name] = f"Independent locked binary check at training wavelength {wavelength:g} nm"
    comparisons = {"mesh020": ["selected_binary", "mesh020"], "mesh015": ["selected_binary", "mesh015"]}
    perturbations = (
        ("boundary", (1550.0, 1520.0, 1536.61, 1580.0), {"outer_half_um": 3.65, "port_half_um": 1.7}),
        ("pml", (1550.0, 1536.61), {"pml_thickness_um": 1.2, "pml_scale": 2}),
        ("projection", (1550.0, 1536.61), {"projection_offset_um": 0.4}),
        ("mesh015", (1520.0, 1536.61, 1580.0), mesh015),
    )
    for variant, wavelengths, changes in perturbations:
        for wavelength in wavelengths:
            baseline = names[wavelength]
            name = variant if wavelength == 1550 else f"{baseline}_{variant}"
            validation.append((name, mesh020 | {"wavelength_nm": wavelength} | changes))
            comparisons[name] = [baseline, name]
            roles[name] = f"Training wavelength {wavelength:g} nm: same-mask {variant} convergence comparison"
    # Keep holdouts untouched when a known training/numerical check already
    # disqualifies this mask. The set of nineteen configurations is unchanged.
    for wavelength in HOLDOUT_WAVELENGTHS:
        name = f"holdout{str(wavelength).replace('.', '_')}"
        validation.append((name, mesh020 | {"wavelength_nm": wavelength}))
        roles[name] = f"Held-out wavelength {wavelength:g} nm; never used to tune the locked mask"
    startup = [
        (
            "gradient0" if wavelength == 1550 else f"gradient0_{names[wavelength]}",
            base | {"mode": "gradient", "direction": 0, "wavelength_nm": wavelength},
        )
        for wavelength in TRAINING_WAVELENGTHS
    ] + [("gradient1", base | {"mode": "gradient", "direction": 1})]
    optimization = base | {"mode": "optimize", "training_band": "five"}
    startup += [
        ("warmup", optimization | {"iterations": 8, "stages": 1, "beta": 2, "evaluation_limit": 9}),
        ("coarse", optimization | {
            "iterations": 32, "stages": 1, "beta": 2, "evaluation_limit": 33, "reconfigure_restart": True
        }),
        ("projection", optimization | {"iterations": 40, "stages": 2, "beta": 4, "evaluation_limit": 41}),
        ("sharpen", optimization | {"iterations": 40, "stages": 1, "beta": 16, "evaluation_limit": 41}),
        ("fine", optimization | {"iterations": 40, "stages": 1, "beta": 32, "evaluation_limit": 41, "mesh_um": 0.025}),
    ]
    budget = {
        "gradient_and_optimization": len(startup),
        "binary_candidates": BINARY_CANDIDATES,
        "locked_validation": len(validation),
    }
    return {
        "schema_version": 3,
        "native_job_budget_max": sum(budget.values()),
        "budget_breakdown": budget,
        "single_worker": True,
        "gpu_used": False,
        "initial_design": (
            "Fresh uniform theta_c=0.5 for warmup; "
            "coarse is a separate 32-iteration restart after 8 warmup iterations"
        ),
        "contour_grid_spacing_um": 0.005,
        "contour_symmetry": "mirror_xy",
        "startup": startup,
        "restart_sources": {"coarse": "warmup", "projection": "coarse", "sharpen": "projection", "fine": "sharpen"},
        "binary_nominal": base | {"mode": "binary", "mesh_um": 0.025, "objective_profile": "state_floor"},
        "threshold_policy": {
            "first": 0.5,
            "second": 0.495,
            "third": 0.505,
            "maximum_trials": BINARY_CANDIDATES,
            "bounds": [LOW, HIGH],
            "max_step": MAX_STEP,
            "step_anchor": "Best finite observed abs(f); first observed threshold if no finite f exists",
            "proposal": (
                "Narrowest sign bracket secant with fresh midpoint fallback; "
                "otherwise nearest usable observed secant and bounded fresh fallback"
            ),
            "selection": "full acceptance required, minimize observed abs(f); early stop abs(f)<=0.02",
        },
        "validation": validation,
        "validation_roles": roles,
        "validation_order_policy": "Training and numerical checks first; holdouts last; stop on first failed gate",
        "convergence_pairs": comparisons,
        "training_wavelengths_nm": list(TRAINING_WAVELENGTHS),
        "holdout_wavelengths_nm": list(HOLDOUT_WAVELENGTHS),
        "convergence_tolerances": {"eta": 0.005, "all_input_eta": 0.005, "fidelity": 0.002, "ratio": 0.02},
        "scope": (
            "2D material-index surrogate; seven discrete wavelengths (five training and two holdout); "
            "mesh/domain-boundary checks at four selected training wavelengths and stronger-PML/projection "
            "checks at two selected training wavelengths; no continuous-band proof "
            "or paper measured-fidelity equivalence"
        ),
    }


class Campaign:
    def __init__(self, output, solver_root, processors, timeout):
        self.output, self.solver_root = output, solver_root
        self.processors, self.timeout = processors, timeout
        self.scripts = Path(__file__).resolve().parent
        self.document = plan() | {
            "status": "running",
            "runs": [],
            "candidates": [],
            "selection": None,
            "summary": {},
            "cost": {"native_jobs": 0, "subprocess_seconds": 0.0},
        }

    def save(self):
        (self.output / "campaign.json").write_text(
            json.dumps(self.document, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )

    def subprocess(self, command, log):
        start = time.perf_counter()
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        source_root = str(self.scripts.parents[1] / "src")
        environment["PYTHONPATH"] = source_root + os.pathsep + environment.get("PYTHONPATH", "")
        with log.open("w", encoding="utf-8") as stream:
            result = subprocess.run(
                command,
                stdout=stream,
                stderr=subprocess.STDOUT,
                check=False,
                env=environment,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        self.document["cost"]["subprocess_seconds"] += time.perf_counter() - start
        return result.returncode

    def record_optimization_cost(self, row, folder, config):
        """Count verified trace observations before deciding execution/physics success."""
        cost = self.document["cost"]
        receipt = row["receipt"] or {}
        try:
            for name in ("plan.json", "batch.log"):
                expected = receipt.get("artifacts", {}).get(name, {}).get("sha256")
                if expected != digest(folder / name):
                    raise ValueError(f"Unverified optimization cost artifact: {name}")
            observed_config = read_json(folder / "plan.json")["config"]
            if any(observed_config.get(key) != value for key, value in config.items()):
                raise ValueError("Optimization cost plan differs from requested configuration")
            actual = _RUNNER.parse_optimization_trace(
                (folder / "batch.log").read_text(encoding="utf-8", errors="replace"), config
            )
            if receipt.get("optimization_cost") != actual or receipt.get("optimization_cost_error"):
                raise ValueError("Optimization cost receipt differs from raw trace")
        except (OSError, ValueError, KeyError, TypeError) as error:
            row["cost_status"] = "unknown"
            row["optimization_cost_error"] = str(error)
            cost["unknown_optimization_jobs"] = cost.get("unknown_optimization_jobs", 0) + 1
            cost["optimization_counts_are_lower_bounds"] = True
            self.save()
            return

        row["optimization_cost"] = actual
        for counter in ("observed_band_evaluations", "nominal_training_frequency_state_evaluations"):
            cost[counter] = cost.get(counter, 0) + actual[counter]
        cost["optimization_count_scope"] = actual["scope"]
        partial = (not actual["completed_requested_stages"] or row["execution_exit"] != 0
                   or receipt.get("completed") is not True)
        if partial:
            cost["incomplete_optimization_jobs"] = cost.get("incomplete_optimization_jobs", 0) + 1
            cost["optimization_counts_are_lower_bounds"] = True
        overruns = [stage["stage"] for stage in actual["stages"]
                    if stage["evaluations"] > config.get("evaluation_limit", 1000)]
        row["cost_status"] = "overrun" if overruns else (
            "partial_lower_bound" if partial else "within_requested_threshold"
        )
        if overruns:
            row["overrun_stages"] = overruns
            cost["stop_further_native_jobs"] = True
            self.document["status"] = "cost_overrun"
        self.save()

    def native(self, name, config, restart=None, mask=None):
        if self.document["cost"].get("stop_further_native_jobs"):
            raise CostOverrun("Actual optimization evaluation cost overran requested threshold; native jobs stopped")
        if self.document["cost"]["native_jobs"] >= self.document["native_job_budget_max"]:
            raise RuntimeError("Declared native-job budget exhausted")
        config_path = self.output / f"{name}-config.json"
        config_path.write_text(json.dumps(config, allow_nan=False), encoding="utf-8")
        folder = self.output / name
        command = [
            sys.executable,
            str(self.scripts / "run.py"),
            "--solver-root",
            str(self.solver_root),
            "--config",
            str(config_path),
            "--output",
            str(folder),
            "--processors",
            str(self.processors),
            "--timeout",
            str(self.timeout),
            "--execute",
        ]
        if restart is not None:
            command.extend(["--restart", str(restart)])
        if mask is not None:
            command.extend(["--mask", str(mask)])
        row = {"name": name, "config": config, "run_directory": name, "status": "executing"}
        if mask is not None:
            row["mask"] = {"sha256": digest(mask), "threshold": read_json(mask)["threshold"]}
        self.document["runs"].append(row)
        self.document["cost"]["native_jobs"] += 1
        self.save()
        code = self.subprocess(command, self.output / f"{name}-driver.log")
        row["execution_exit"] = code
        receipt_path = folder / "receipt.json"
        row["receipt"] = read_json(receipt_path) if receipt_path.exists() else None
        if config["mode"] == "optimize":
            self.record_optimization_cost(row, folder, config)
        if code != 0 or row["receipt"] is None or row["receipt"].get("completed") is not True:
            row["status"] = "execution_failure"
            self.save()
            raise RuntimeError(f"Native execution failed: {name}")
        row["status"] = "checking_native_evidence"
        artifacts = ["plan.json", "console.log"] + (["batch.log"] if config["mode"] == "optimize" else [])
        for artifact in artifacts:
            expected = row["receipt"].get("artifacts", {}).get(artifact, {}).get("sha256")
            if expected != digest(folder / artifact):
                raise RuntimeError(f"Native receipt artifact mismatch: {name}/{artifact}")
        observed_plan = read_json(folder / "plan.json")
        if any(observed_plan["config"].get(key) != value for key, value in config.items()):
            raise RuntimeError("Native plan does not match requested configuration")
        if mask is not None and observed_plan.get("mask_sha256") != row["mask"]["sha256"]:
            raise RuntimeError("Native plan does not match requested mask")
        if restart is not None and observed_plan.get("restart_sha256") != digest(restart):
            raise RuntimeError("Native plan does not match requested restart")
        if config["mode"] == "optimize":
            row["optimization_prechecks"] = optimization_prechecks(
                row["receipt"], (folder / "console.log").read_text(encoding="utf-8", errors="replace"), config
            )
            row["optimization_cost"] = optimization_cost_prechecks(
                row["receipt"], (folder / "batch.log").read_text(encoding="utf-8", errors="replace"),
                config, row["optimization_prechecks"],
            )
            self.save()
        if config["mode"] == "gradient":
            row["status"] = "gradient_pass_from_native_receipt"
            self.save()
            return None
        code = self.subprocess(
            [sys.executable, str(self.scripts / "analyze.py"), str(folder)], self.output / f"{name}-analysis.log"
        )
        row["analysis_exit"] = code
        if code not in (0, 2) or not (folder / "verification.json").exists():
            row["status"] = "analysis_execution_failure"
            self.save()
            raise RuntimeError(f"Evidence analysis failed: {name}")
        report = read_json(folder / "verification.json")
        if not isinstance(report.get("acceptance_pass"), bool) or (code == 0) != report["acceptance_pass"]:
            raise RuntimeError("Analysis exit contradicts report acceptance")
        row["status"] = "scientific_pass" if report["acceptance_pass"] else "scientific_failure"
        row["report"] = report
        self.save()
        if self.document["cost"].get("stop_further_native_jobs"):
            raise CostOverrun(f"Actual optimization evaluation cost overrun: {name}; physical report retained")
        return report

    def run(self):
        recipe = plan()
        observed = set()
        for name, config in recipe["startup"]:
            restart = None
            if name in recipe["restart_sources"]:
                source = recipe["restart_sources"][name]
                if source not in observed:
                    raise RuntimeError(f"Restart source must be observed before {name}: {source}")
                restart = self.output / source / "final.mph"
                if not restart.is_file():
                    raise RuntimeError(f"Restart source is missing for {name}: {restart}")
            self.native(name, config, restart=restart)
            observed.add(name)
        return self.qualify_binary(self.output / "fine/density.txt")

    def qualify_binary(self, density):
        """Calibrate a contour, freeze its mask, then spend the validation reserve."""
        recipe = plan()
        nominal = recipe["binary_nominal"]
        for index in range(recipe["budget_breakdown"]["binary_candidates"]):
            threshold = propose_threshold(self.document["candidates"])
            name = f"binary{index + 1}"
            mask_folder = self.output / f"{name}-mask"
            code = self.subprocess(
                [
                    sys.executable,
                    str(self.scripts / "extract_mask.py"),
                    str(density),
                    "--threshold",
                    str(threshold),
                    "--grid-spacing-um",
                    str(recipe["contour_grid_spacing_um"]),
                    "--symmetry",
                    recipe["contour_symmetry"],
                    "--output",
                    str(mask_folder),
                ],
                self.output / f"{name}-mask.log",
            )
            if code != 0:
                raise RuntimeError("Mask extraction failed")
            report = self.native(name, nominal, mask=mask_folder / "mask.json")
            candidate = {
                "name": name,
                "threshold": threshold,
                "f": imbalance(report),
                "acceptance_pass": report["acceptance_pass"],
                "report": report,
                "mask": str((mask_folder / "mask.json").relative_to(self.output)),
            }
            self.document["candidates"].append(candidate)
            self.save()
            if candidate["acceptance_pass"] and candidate["f"] is not None and abs(candidate["f"]) <= 0.02:
                break
        selected = select_candidate(self.document["candidates"])
        if selected is None:
            self.document["status"] = "scientific_failure"
            self.document["summary"] = {"reason": "No binary candidate passed full declared acceptance"}
            self.save()
            return 2
        locked_mask = self.output / selected["mask"]
        mask_hash = hashlib.sha256(locked_mask.read_bytes()).hexdigest()
        self.document["selection"] = {
            "name": selected["name"],
            "threshold": selected["threshold"],
            "f": selected["f"],
            "mask": selected["mask"],
            "mask_sha256": mask_hash,
        }
        reports, comparisons = {}, {}
        references = {"selected_binary": selected["report"]}
        for name, changes in recipe["validation"]:
            if hashlib.sha256(locked_mask.read_bytes()).hexdigest() != mask_hash:
                raise RuntimeError("Locked mask changed during independent validation")
            reports[name] = self.native(name, nominal | changes, mask=locked_mask)
            references[name] = reports[name]
            for pair, (reference, comparison) in recipe["convergence_pairs"].items():
                if comparison == name:
                    if reference not in references:
                        raise RuntimeError("Convergence reference must be observed before its comparison")
                    comparisons[pair] = convergence(references[reference], references[comparison])
            observed_pass = all(r["acceptance_pass"] for r in reports.values())
            convergence_pass = all(c["pass"] for c in comparisons.values())
            unspent = [item for item, _ in recipe["validation"] if item not in reports]
            self.document["summary"] = {
                "all_locked_validation_full_pass": not unspent and observed_pass,
                "observed_locked_runs_pass": observed_pass,
                "locked_validation_complete": not unspent,
                "completed_locked_checks": list(reports),
                "unspent_locked_checks": unspent,
                "convergence": comparisons,
                "mask_locked_before_validation": True,
            }
            if not observed_pass or not convergence_pass:
                self.document["status"] = "scientific_failure"
                self.document["summary"]["first_failed_locked_check"] = name
                self.save()
                return 2
            self.save()
        if set(comparisons) != set(recipe["convergence_pairs"]):
            raise RuntimeError("Required convergence comparison is missing")
        self.document["status"] = "pass"
        self.save()
        return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--solver-root",
        type=Path,
        default=Path(os.environ["PHOTONIC_SOLVER_ROOT"]) if "PHOTONIC_SOLVER_ROOT" in os.environ else None,
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--processors", type=int, choices=range(1, 33), default=8)
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.output.exists() or not 30 <= args.timeout <= 7200:
        parser.error("Output must be new; timeout must be 30..7200 seconds per native job")
    print(json.dumps(plan(), indent=2, allow_nan=False), flush=True)
    if not args.execute:
        return 0
    if args.solver_root is None:
        parser.error("Supply --solver-root or PHOTONIC_SOLVER_ROOT")
    args.output.mkdir(parents=True, exist_ok=False)
    campaign = Campaign(args.output.resolve(), args.solver_root.resolve(), args.processors, args.timeout)
    campaign.save()
    try:
        return campaign.run()
    except CostOverrun as error:
        campaign.document["status"] = "cost_overrun"
        campaign.document["summary"] = {
            "error": str(error),
            "physical_reports_retained": any("report" in row for row in campaign.document["runs"]),
        }
        campaign.save()
        print(str(error), file=sys.stderr)
        return 3
    except (OSError, RuntimeError, ValueError, KeyError, TypeError) as error:
        cost_stop = campaign.document["cost"].get("stop_further_native_jobs", False)
        campaign.document["status"] = "cost_overrun" if cost_stop else "execution_failure"
        campaign.document["summary"] = {"error": str(error)}
        campaign.save()
        print(str(error), file=sys.stderr)
        return 3 if cost_stop else 1


if __name__ == "__main__":
    raise SystemExit(main())
