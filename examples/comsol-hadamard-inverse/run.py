"""Run the reviewed COMSOL Hadamard example in a fresh, bounded Windows process.

The default is a plan. --execute starts the licensed local solver. Keep raw
models and logs in the chosen output directory, outside the public source tree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def parse_optimization_trace(batch: str, config: dict) -> dict:
    """Read accepted optimizer rows, not Newton rows; partial counts are lower bounds."""
    stages = []
    section = None
    active = None
    table = False
    for line in batch.splitlines():
        text = line.strip()
        if text.startswith("<---- "):
            section = text.strip("<-> ")
        if text.split() == ["Iter", "Inner", "nEval", "Error", "Objective", "MaxInfeas"]:
            if active is not None:
                raise ValueError("Optimization trace starts a stage before the preceding solver closed")
            active = {"stage": len(stages) + 1, "completed": False, "rows": []}
            stages.append(active)
            active_section = section
            table = True
            continue
        if active is None:
            continue
        if text.startswith("----- ") and text.endswith(">") and text.strip("<-> ") == active_section:
            if not active["rows"]:
                raise ValueError("Empty optimization trace stage")
            active["completed"] = True
            active = None
            table = False
            continue
        if text.split()[:1] == ["Iter"]:
            table = False  # e.g. Iter SolEst Damping Stepsize #Res #Jac #Sol LinErr LinRes
        if not table or not re.match(r"^\d+(?:\s|$)", text):
            continue
        parts = text.split()
        try:
            if len(parts) != 6 or not parts[0].isdigit() or not parts[2].isdigit():
                raise ValueError("Expected six optimizer columns")
            iteration, evaluations = int(parts[0]), int(parts[2])
            inner = None if parts[1] == "-" else int(parts[1])
            error = None if parts[3] == "-" else float(parts[3])
            objective = float(parts[4])
            infeasibility = None if parts[5] == "-" else float(parts[5])
            if not all(math.isfinite(v) for v in (objective, error or 0, infeasibility or 0)):
                raise ValueError("Nonfinite optimizer value")
            rows = active["rows"]
            if iteration != len(rows) or evaluations < iteration + 1:
                raise ValueError("Missing, repeated or inconsistent optimizer iteration")
            if not rows:
                if evaluations != 1 or inner is not None or error is not None:
                    raise ValueError("Expected initial optimizer evaluation")
            elif (
                inner is None or inner < 0 or error is None or error < 0
                or evaluations <= rows[-1]["evaluations"]
                or evaluations - rows[-1]["evaluations"] < inner
            ):
                raise ValueError("Inconsistent optimizer evaluation/inner counters")
        except (ValueError, OverflowError) as exc:
            raise ValueError(f"Malformed optimization trace row: {text}") from exc
        rows.append({
            "iteration": iteration, "inner": inner, "evaluations": evaluations,
            "error": error, "objective_rounded": objective, "objective_text": parts[4],
            "max_infeasibility": infeasibility,
        })
    if not stages or not any(stage["rows"] for stage in stages):
        raise ValueError("Missing optimization trace or no reported evaluations")
    for stage in stages:
        if not stage["rows"]:
            # An interrupted next stage must not erase completed prefix work.
            # Zero is an observed lower bound, not a claim of zero solver work.
            stage.update(evaluations=0, outer_iterations=0, inner_iterations=0)
            continue
        last = stage["rows"][-1]
        stage.update(evaluations=last["evaluations"], outer_iterations=last["iteration"],
                     inner_iterations=sum(row["inner"] or 0 for row in stage["rows"]))
    evaluations = sum(stage["evaluations"] for stage in stages)
    frequencies = {"single": 1, "three": 3, "five": 5}[config["training_band"]]
    return {
        "stages": stages,
        "completed_requested_stages": len(stages) == config["stages"] and all(s["completed"] for s in stages),
        "observed_band_evaluations": evaluations,
        "nominal_training_frequency_state_evaluations": evaluations * frequencies,
        "scope": "Accepted-row nEval includes initial and rejected inner-loop evaluations; incomplete stages "
                 "are lower bounds. Nominal training frequency-state count excludes validation, adjoint, "
                 "Newton and linear solves; printed objectives are rounded.",
    }


def process(command: list[str], cwd: Path, log: Path, timeout: int) -> tuple[int, float]:
    started = time.perf_counter()
    with log.open("wb") as stream:
        proc = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=stream,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            else:
                proc.kill()
            proc.wait(timeout=30)
            code = 124
    return code, time.perf_counter() - started


def configuration(path: Path | None) -> dict:
    defaults = {
        "mode": "baseline",
        "wavelength_nm": 1550.0,
        "iterations": 3,
        "optimizer": "mma",
        "move_limit": 0.05,
        "evaluation_limit": 1000,
        "beta": 2.0,
        "rf_um": 0.05,
        "mesh_um": 0.045,
        "eps_core": 12.1,
        "eps_clad": 2.1,
        "direction": 0,
        "stages": 1,
        "outer_half_um": 3.15,
        "port_half_um": 1.5,
        "guided_modes": 2,
        "training_band": "single",
        "objective_profile": "coherent",
        "reconfigure_restart": False,
        "boundary_model": "exterior_modal",
        "pml_thickness_um": 0.8,
        "pml_scale": 1.0,
        "pml_curvature": 3.0,
        "projection_offset_um": 0.2,
        "fidelity_weight": 1.0,
        "cladding_mesh_um": 0.10,
    }
    values = json.loads(path.read_text(encoding="utf-8")) if path else {}
    if not isinstance(values, dict) or set(values) - set(defaults):
        raise ValueError("configuration must be an object with supported example keys")
    defaults.update(values)
    if defaults["mode"] not in {"baseline", "optimize", "gradient", "binary", "frozen"}:
        raise ValueError("mode must be baseline, optimize, gradient, binary or frozen")
    if not isinstance(defaults["optimizer"], str) or defaults["optimizer"] not in {"mma", "gcmma"}:
        raise ValueError("optimizer must be mma or gcmma")
    if defaults["training_band"] not in {"single", "three", "five"}:
        raise ValueError("training_band must be single, three or five")
    if defaults["training_band"] != "single" and defaults["wavelength_nm"] != 1550:
        raise ValueError("the multi-frequency training fixture requires 1550 nm as its validation center")
    if defaults["training_band"] == "five" and defaults["mode"] not in {"optimize", "frozen"}:
        raise ValueError("five-frequency training requires optimize or frozen mode")
    if not isinstance(defaults["objective_profile"], str) or defaults["objective_profile"] not in {
        "coherent", "state_floor"
    }:
        raise ValueError("objective_profile must be coherent or state_floor")
    if not isinstance(defaults["reconfigure_restart"], bool):
        raise ValueError("reconfigure_restart must be a boolean")
    if defaults["reconfigure_restart"] and defaults["mode"] != "optimize":
        raise ValueError("reconfigure_restart requires optimize mode and --restart")
    if not isinstance(defaults["boundary_model"], str) or defaults["boundary_model"] not in {
        "exterior_modal", "slit_pml"
    }:
        raise ValueError("boundary_model must be exterior_modal or slit_pml")
    if defaults["training_band"] != "single" and defaults["mode"] == "gradient":
        raise ValueError("directional gradient diagnostics are qualified per frequency; use single")
    bounds = {
        "wavelength_nm": (1450, 1650),
        "iterations": (1, 1000),
        "move_limit": (0.0001, 0.2),
        "evaluation_limit": (2, 5000),
        "beta": (0.1, 128),
        "rf_um": (0.01, 0.25),
        "mesh_um": (0.015, 0.1),
        "eps_core": (4, 16),
        "eps_clad": (1, 4),
        "direction": (0, 1),
        "stages": (1, 6),
        "outer_half_um": (2, 5.65),
        "port_half_um": (0.7, 2.5),
        "guided_modes": (1, 2),
        "fidelity_weight": (1, 100),
        "cladding_mesh_um": (0.06, 0.3),
        "pml_thickness_um": (0.4, 1.6),
        "pml_scale": (0.5, 3),
        "pml_curvature": (1, 5),
        "projection_offset_um": (0.1, 0.5),
    }
    for key, (low, high) in bounds.items():
        value = defaults[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"{key} must be a finite number")
        if not low <= value <= high:
            raise ValueError(f"{key} must be in [{low}, {high}]")
    if any(not isinstance(defaults[key], int) for key in (
        "iterations", "stages", "direction", "guided_modes", "evaluation_limit"
    )):
        raise ValueError("iterations, stages, direction, guided_modes and evaluation_limit must be integers")
    if defaults["beta"] * 2 ** (defaults["stages"] - 1) > 128:
        raise ValueError("final continuation beta must not exceed 128")
    if defaults["eps_core"] <= defaults["eps_clad"]:
        raise ValueError("core permittivity must exceed cladding permittivity")
    if defaults["port_half_um"] >= defaults["outer_half_um"]:
        raise ValueError("port window must leave a nonempty open boundary")
    if defaults["boundary_model"] == "slit_pml" and defaults["port_half_um"] >= (
        defaults["outer_half_um"] - defaults["projection_offset_um"]
    ):
        raise ValueError("slit_pml port window must lie inside the closed projection contour")
    return defaults


def render_mask(path: Path) -> str:
    mask = json.loads(path.read_text(encoding="utf-8"))
    if mask.get("units") != "um" or mask.get("design_bounds") != [-0.65, 0.65, -0.65, 0.65]:
        raise ValueError("mask must declare the fixed 1.3 um square and micrometre units")
    polygons = mask.get("polygons")
    if not isinstance(polygons, list) or len(polygons) > 2000:
        raise ValueError("mask must contain at most 2000 connected polygons")
    lines = []
    vertex_count = 0
    for i, polygon in enumerate(polygons):
        rings = [polygon["outer"], *polygon.get("holes", [])]
        names = []
        for j, ring in enumerate(rings):
            vertex_count += len(ring)
            if len(ring) < 3 or vertex_count > 100000:
                raise ValueError("invalid or excessively large mask ring")
            for pair in ring:
                if len(pair) != 2 or any(
                    isinstance(v, bool)
                    or not isinstance(v, (int, float))
                    or not math.isfinite(v)
                    or abs(v) > 0.6500000001
                    for v in pair
                ):
                    raise ValueError("mask coordinates must be finite and inside the fixed design square")
            tag = f"mask{i}ring{j}"
            names.append(tag)
            table = ",".join("{" + ",".join(format(v, ".17g") for v in pair) + "}" for pair in ring)
            contribution = '"binary"' if len(rings) == 1 else "null"
            lines.append(f'maskPolygon(g,"{tag}",new double[][]{{{table}}},{contribution});')
        if len(rings) > 1:
            tag = f"mask{i}"
            holes = ",".join(json.dumps(name) for name in names[1:])
            lines.extend(
                [
                    f'g.create("{tag}","Difference");',
                    f'g.feature("{tag}").selection("input").set(new String[]{{"{names[0]}"}});',
                    f'g.feature("{tag}").selection("input2").set(new String[]{{{holes}}});',
                    f'g.feature("{tag}").set("selresult","on");',
                    f'g.feature("{tag}").set("contributeto","binary");',
                ]
            )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--solver-root",
        type=Path,
        default=Path(os.environ["PHOTONIC_SOLVER_ROOT"]) if "PHOTONIC_SOLVER_ROOT" in os.environ else None,
    )
    parser.add_argument("--source", type=Path, default=Path(__file__).with_name("HadamardNative.java"))
    parser.add_argument("--config", type=Path)
    parser.add_argument("--mask", type=Path, help="binary contour JSON; required only for binary mode")
    parser.add_argument("--restart", type=Path, help="previous native optimization final.mph")
    parser.add_argument("--output", type=Path, required=True, help="new directory; never reused")
    parser.add_argument("--processors", type=int, choices=range(1, 33), default=8)
    parser.add_argument("--timeout", type=int, default=900, help="batch wall time limit in seconds")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("this example runner currently supports Windows native COMSOL only")
    if not args.solver_root or not 30 <= args.timeout <= 7200:
        parser.error("supply solver root; timeout must be 30..7200 seconds")
    source = args.source.resolve(strict=True)
    destination = args.output.resolve()
    if source.name != "HadamardNative.java" or destination.exists():
        parser.error("source must be HadamardNative.java and output directory must be new")
    compiler = args.solver_root / "bin/win64/comsolcompile.exe"
    batch = args.solver_root / "bin/win64/comsolbatch.exe"
    if not compiler.is_file() or not batch.is_file():
        parser.error("official COMSOL native entrypoints were not found")
    try:
        config = configuration(args.config)
        if config["reconfigure_restart"] and args.restart is None:
            raise ValueError("reconfigure_restart requires optimize mode and --restart")
        if (config["mode"] == "binary") != (args.mask is not None):
            raise ValueError("supply --mask exactly when mode is binary")
        mask_java = render_mask(args.mask) if args.mask else ""
        if args.restart and (
            config["mode"] not in {"optimize", "frozen"}
            or args.restart.suffix.lower() != ".mph"
            or not args.restart.is_file()
        ):
            raise ValueError("restart requires optimize/frozen mode and a prior MPH from this fixture")
        if config["mode"] == "frozen" and args.restart is None:
            raise ValueError("frozen mode requires --restart")
    except (ValueError, OSError) as error:
        parser.error(str(error))
    plan = {
        "schema_version": 1,
        "source_sha256": digest(source),
        "config": config,
        "processors": args.processors,
        "timeout_seconds": args.timeout,
        "execute": args.execute,
        "model_level": "2D_material_index_surrogate",
        "acceptance": "execution receipt only; run the independent matrix verifier separately",
    }
    if args.mask:
        plan["mask_sha256"] = digest(args.mask)
    if args.restart:
        plan["restart_sha256"] = digest(args.restart)
    print(json.dumps(plan, indent=2), flush=True)
    if not args.execute:
        return 0
    destination.mkdir(parents=True, exist_ok=False)
    for name in ("prefs", "configuration", "tmp"):
        (destination / name).mkdir()
    source_text = source.read_text(encoding="utf-8")
    literal = json.dumps(destination.as_posix(), ensure_ascii=True)
    rendered = source_text.replace('"__RUN_DIRECTORY__"', literal)
    rendered = rendered.replace(
        '"__RESTART_MODEL__"', json.dumps(args.restart.resolve().as_posix() if args.restart else "", ensure_ascii=True)
    )
    rendered = rendered.replace(
        "// __RUN_CONFIG__",
        "\n".join(f"cfg.setProperty({json.dumps(key)}, {json.dumps(str(value))});" for key, value in config.items()),
    )
    rendered = rendered.replace("// __MASK_GEOMETRY__", mask_java)
    (destination / source.name).write_text(rendered, encoding="utf-8")
    (destination / "design.properties").write_text(
        "".join(f"{key}={value}\n" for key, value in config.items()), encoding="ascii"
    )
    (destination / "plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    receipt = {"started_utc": datetime.now(UTC).isoformat(), "completed": False}
    code, elapsed = process(
        [str(compiler), str(destination / source.name)], destination, destination / "compile.log", 120
    )
    receipt.update(compile_exit=code, compile_seconds=elapsed)
    class_file = destination / "HadamardNative.class"
    # COMSOL's compiler can return zero after a Java compilation error.
    if code == 0 and class_file.is_file():
        command = [
            str(batch),
            "-np",
            str(args.processors),
            "-prefsdir",
            str(destination / "prefs"),
            "-configuration",
            str(destination / "configuration"),
            "-tmpdir",
            str(destination / "tmp"),
            "-inputfile",
            str(class_file),
            "-batchlog",
            str(destination / "batch.log"),
        ]
        code, elapsed = process(command, destination, destination / "console.log", args.timeout)
        receipt.update(batch_exit=code, batch_seconds=elapsed)
        if config["mode"] == "optimize":
            try:
                receipt["optimization_cost"] = parse_optimization_trace(
                    (destination / "batch.log").read_text(encoding="utf-8", errors="replace"), config
                )
            except (OSError, ValueError) as error:
                receipt["optimization_cost_error"] = str(error)
        console = (destination / "console.log").read_bytes()
        lines = console.decode("utf-8", errors="replace").splitlines()
        receipt["training_observations"] = [
            line for line in lines if line.startswith(("TRAINING_POINT=", "TRAINING_MINIMUM="))
        ]
        receipt["training_modal_observations"] = [line for line in lines if line.startswith("TRAINING_MODAL=")]
        headers = [line.split("=", 1)[1] for line in lines if line.startswith("HADAMARD_CSV_HEADER=")]
        rows = [line.split("=", 1)[1] for line in lines if line.startswith("HADAMARD_CSV=")]
        if len(headers) == 1 and rows:
            (destination / "metrics.csv").write_text("\n".join(headers + rows) + "\n", encoding="ascii")
        density_header = [line.split("=", 1)[1] for line in lines if line.startswith("HADAMARD_DENSITY_HEADER=")]
        density_rows = [line.split("=", 1)[1] for line in lines if line.startswith("HADAMARD_DENSITY=")]
        if len(density_header) == 1 and density_rows:
            (destination / "density.txt").write_text("\n".join(density_header + density_rows) + "\n", encoding="ascii")
        field_header = [line.split("=", 1)[1] for line in lines if line.startswith("HADAMARD_FIELD_HEADER=")]
        field_rows = [line.split("=", 1)[1] for line in lines if line.startswith("HADAMARD_FIELD=")]
        if len(field_header) == 1 and field_rows:
            (destination / "field.txt").write_text("\n".join(field_header + field_rows) + "\n", encoding="ascii")
        power_header = [line.split("=", 1)[1] for line in lines if line.startswith("HADAMARD_POWER_HEADER=")]
        power_rows = [line.split("=", 1)[1] for line in lines if line.startswith("HADAMARD_POWER=")]
        if len(power_header) == 1 and power_rows:
            (destination / "power.csv").write_text("\n".join(power_header + power_rows) + "\n", encoding="ascii")
        model = destination / ("final.mph" if config["mode"] == "optimize" else "baseline.mph")
        required = (
            model,
            destination / "metrics.csv",
            destination / "power.csv",
            destination / ("field.txt" if config["mode"] == "binary" else "density.txt"),
        )
        receipt["completed"] = (
            code == 0
            and b"HADAMARD_DIAGNOSTIC_EXPORT_COMPLETE" in console
            and all(p.is_file() and p.stat().st_size > 0 for p in required)
        )
        if config["mode"] == "gradient":
            receipt["completed"] = (
                code == 0
                and b"HADAMARD_GRADIENT_CHECK_COMPLETE" in console
                and (destination / "gradient.mph").is_file()
            )
            receipt["gradient_checks"] = [line for line in lines if line.startswith("GRADIENT_CHECK=")]
    receipt["artifacts"] = {
        p.name: {"bytes": p.stat().st_size, "sha256": digest(p)} for p in destination.iterdir() if p.is_file()
    }
    (destination / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2), flush=True)
    return 0 if receipt["completed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
