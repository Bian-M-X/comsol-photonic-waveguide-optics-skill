"""Fixed beta8 checkpoint -> beta16 native CVF directional diagnostic.

Default: validate inputs and print a plan, without writes or solver startup.
Execution completion and scientific gradient agreement are separate receipt fields.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
from datetime import UTC, datetime
from pathlib import Path

# Reuse the sibling runner's native process supervision and streaming SHA-256.
_SPEC = importlib.util.spec_from_file_location("hadamard_native_runner", Path(__file__).with_name("run.py"))
_RUNNER = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_RUNNER)
digest = _RUNNER.digest
process = _RUNNER.process

WAVELENGTHS = (1580.0, 1565.0, 1550.0, 1536.61, 1520.0)
STEPS = (0.0, 0.001, -0.001, 0.0005, -0.0005)
RELATIVE_TOLERANCE = 0.002
TIE_TOLERANCE = 1e-9
COMPLETE = "DIAGNOSTIC_COMPLETE=true;FIVE_FREQUENCY_COMPLETE=true;NO_PERFORMANCE_ACCEPTANCE=true"
SEED_ASSOCIATION = "SEED_STUDY_ASSOCIATION=std1,attached=false,StudyStep=std1/freq,splitcomplex=true"
CONTRACT = "LEGACY_COMPLEX_CVF_RETAINED=true;NO_OPTIMIZER_UPDATES=true;NO_REMESH=true;BETA=16;OBJECTIVE="
EXPECTED_OBJECTIVE = (
    "(realdot((comp1.modal_a3-i*comp1.modal_a4),(comp1.modal_a3-i*comp1.modal_a4))"
    "-(gate_weight-1)*realdot((comp1.modal_a3+i*comp1.modal_a4),(comp1.modal_a3+i*comp1.modal_a4)))/2"
    "-sqrt(4*realdot(comp1.modal_a3,comp1.modal_a4)^2+1e-8)"
)
SCOPE = (
    "Fixed checkpoint, fixed mesh, retained complex CVF, one feasible direction at beta16; "
    "not all-direction gradient correctness or device performance acceptance."
)


def _rows(lines: list[str], marker: str, positional: int, named: tuple[str, ...] = ()) -> list[list[float]]:
    result = []
    for line in lines:
        if not line.startswith(marker + "="):
            continue
        fields = line.split("=", 1)[1].split(",")
        if len(fields) != positional + len(named):
            raise ValueError(f"Malformed {marker} row")
        raw = fields[:positional]
        for field, name in zip(fields[positional:], named, strict=True):
            if not field.startswith(name + "="):
                raise ValueError(f"Unexpected {marker} field: {name}")
            raw.append(field.split("=", 1)[1])
        try:
            values = [float(value) for value in raw]
        except ValueError as exc:
            raise ValueError(f"Nonnumeric {marker} row") from exc
        if not all(math.isfinite(value) for value in values):
            raise ValueError(f"Nonfinite {marker} row")
        result.append(values)
    return result


def _indexed(rows: list[list[float]], expected: set[tuple[float, float]], marker: str) -> dict:
    values = {}
    for row in rows:
        key = tuple(row[:2])
        if key not in expected or key in values:
            raise ValueError(f"Unexpected or duplicate {marker} wavelength/step")
        values[key] = row[2:]
    if set(values) != expected:
        raise ValueError(f"Missing {marker} rows")
    return values


def _same(actual: float, expected: float, label: str) -> None:
    # Serialized %.17g rows should agree to rounding, not to the scientific tolerance.
    if not math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-12):
        raise ValueError(f"Inconsistent {label}: printed={actual}, recomputed={expected}")


def parse_diagnostic(console: str) -> dict:
    """Fail closed on incomplete, repeated, nonfinite or self-inconsistent data."""
    lines = console.splitlines()
    if any(line.startswith("PROBE_EXCEPTION=") for line in lines):
        raise ValueError("Native probe reported an exception")
    for marker in (COMPLETE, SEED_ASSOCIATION):
        if lines.count(marker) != 1:
            raise ValueError("Missing or repeated diagnostic/seed marker")
    contracts = [line for line in lines if line.startswith("LEGACY_COMPLEX_CVF_RETAINED=")]
    if contracts != [CONTRACT + EXPECTED_OBJECTIVE]:
        raise ValueError("Missing, repeated or changed fixed-fixture contract/objective marker")
    observations = _indexed(
        _rows(lines, "OBSERVATION", 4, ("mapped_fsens_max_imag",)),
        {(w, a) for w in WAVELENGTHS for a in STEPS}, "OBSERVATION",
    )
    if any(not 0 <= row[2] <= 1e-12 for row in observations.values()):
        raise ValueError("Nonzero/invalid mapped Fsens imaginary part")
    readbacks = _indexed(
        _rows(lines, "SEED_READBACK", 2, ("max_error",)), set(observations), "SEED_READBACK",
    )
    if any(not 0 <= row[0] < 2e-10 for row in readbacks.values()):
        raise ValueError("Fresh control readback exceeds tolerance")
    controls = [line for line in lines if line.startswith("FRESH_CONTROL=")]
    if len(controls) != 25 or any(
        line != "FRESH_CONTROL=probeSol/v1/comp1_theta_c,valuetype=complex,scale=1" for line in controls
    ):
        raise ValueError("Missing or changed fresh complex CVF readback")
    done = _rows(lines, "WAVELENGTH_DIAGNOSTIC_COMPLETE", 1)
    if len(done) != 5 or {row[0] for row in done} != set(WAVELENGTHS):
        raise ValueError("Missing, duplicate or unexpected wavelength completion")
    comparisons = _indexed(
        _rows(lines, "COMPARISON", 5), {(w, h) for w in WAVELENGTHS for h in (0.001, 0.0005)}, "COMPARISON",
    )
    checks = []
    for (wavelength, h), printed in comparisons.items():
        adjoint = observations[wavelength, 0.0][1]
        finite_difference = (observations[wavelength, h][0] - observations[wavelength, -h][0]) / (2 * h)
        relative_error = abs(finite_difference - adjoint) / max(1e-10, abs(finite_difference), abs(adjoint))
        for actual, expected, name in zip(printed, (adjoint, finite_difference, relative_error),
                                          ("adjoint", "finite difference", "relative error"), strict=True):
            _same(actual, expected, f"COMPARISON {name}")
        checks.append({"wavelength_nm": wavelength, "h": h, "adjoint": adjoint,
                       "finite_difference": finite_difference, "relative_error": relative_error})
    minima = {a: min(observations[w, a][0] for w in WAVELENGTHS) for a in STEPS}
    active = min(WAVELENGTHS, key=lambda w: observations[w, 0.0][0])
    gap = min(observations[w, 0.0][0] for w in WAVELENGTHS if w != active) - minima[0.0]
    tied = [observations[w, 0.0][1] for w in WAVELENGTHS
            if observations[w, 0.0][0] - minima[0.0] <= TIE_TOLERANCE]
    right_adjoint, left_adjoint = min(tied), max(tied)
    active_rows = _rows(lines, "MIN_ACTIVE", 2, ("gap", "right_derivative", "left_derivative", "tie_tol"))
    if len(active_rows) != 1:
        raise ValueError("Missing or repeated MIN_ACTIVE")
    for actual, expected in zip(active_rows[0],
                                (active, minima[0.0], gap, right_adjoint, left_adjoint, TIE_TOLERANCE), strict=True):
        _same(actual, expected, "MIN_ACTIVE")
    min_rows = _rows(lines, "MIN_FD", 1, ("central", "right", "left", "central_expected"))
    if len(min_rows) != 2 or {row[0] for row in min_rows} != {0.001, 0.0005}:
        raise ValueError("Missing, repeated or unexpected MIN_FD")
    min_checks = []
    for h, central, right, left, expected in min_rows:
        fd = (minima[h] - minima[-h]) / (2 * h)
        derivative = (right_adjoint + left_adjoint) / 2
        recomputed = (fd, (minima[h] - minima[0.0]) / h, (minima[0.0] - minima[-h]) / h, derivative)
        for actual, value in zip((central, right, left, expected), recomputed, strict=True):
            _same(actual, value, "MIN_FD")
        error = abs(fd - derivative) / max(1e-10, abs(fd), abs(derivative))
        min_checks.append({"h": h, "central": fd, "right": recomputed[1], "left": recomputed[2],
                           "central_expected": derivative, "relative_error": error})
    worst = max(check["relative_error"] for check in checks + min_checks)
    return {"valid": True, "gradient_pass": worst <= RELATIVE_TOLERANCE,
            "relative_tolerance": RELATIVE_TOLERANCE, "worst_relative_error": worst,
            "counts": {"observations": 25, "comparisons": 10, "wavelength_completions": 5,
                       "min_active": 1, "min_fd": 2, "fresh_control_readbacks": 25},
            "checks": checks, "minimum": {"active_wavelength_nm": active, "value": minima[0.0],
                                         "gap": gap, "checks": min_checks}, "scope": SCOPE}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    solver_default = Path(os.environ["PHOTONIC_SOLVER_ROOT"]) if "PHOTONIC_SOLVER_ROOT" in os.environ else None
    parser.add_argument("--solver-root", type=Path, default=solver_default)
    parser.add_argument("--restart", type=Path, required=True, help="fixed beta8 five-frequency checkpoint MPH")
    parser.add_argument("--output", type=Path, required=True, help="new private run directory")
    parser.add_argument("--processors", type=int, choices=range(1, 33), default=8)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    try:
        if os.name != "nt" or not args.solver_root or not 30 <= args.timeout <= 7200:
            raise ValueError("Windows native COMSOL, solver root and timeout 30..7200 required")
        root = args.solver_root.resolve(strict=True)
        compiler, batch = (root / "bin/win64" / name for name in ("comsolcompile.exe", "comsolbatch.exe"))
        if not compiler.is_file() or not batch.is_file():
            raise ValueError("Official COMSOL native entrypoints not found")
        restart = args.restart.resolve(strict=True)
        source = Path(__file__).with_name("CvfDiscreteGradientProbe.java").resolve(strict=True)
        destination = args.output.resolve()
        if destination.exists() or args.output.is_symlink():
            raise ValueError("Output must be a new directory")
        if not restart.is_file() or restart.suffix.lower() != ".mph" or restart.stat().st_size == 0:
            raise ValueError("Restart must be a nonempty beta8 fixture MPH")
        template = source.read_text(encoding="utf-8")
        if template.count('"__RESTART_MODEL__"') != 1 or template.count('"__RUN_DIRECTORY__"') != 1:
            raise ValueError("Native template placeholders missing or repeated")
        source_hash, restart_hash = digest(source), digest(restart)
    except (OSError, ValueError) as exc:
        print(json.dumps({"completed": False, "gradient_pass": False, "error": str(exc)}), flush=True)
        return 1
    plan = {"schema_version": 1, "execute": args.execute, "single_worker": True,
            "source_sha256": source_hash, "restart_sha256": restart_hash,
            "fixture": "beta8 endpoint -> beta16, weight10 state_floor slit-PML five-frequency checkpoint",
            "wavelengths_nm": WAVELENGTHS, "steps": STEPS, "relative_tolerance": RELATIVE_TOLERANCE,
            "processors": args.processors, "timeout_seconds": args.timeout, "scope": SCOPE}
    print(json.dumps(plan, indent=2), flush=True)
    if not args.execute:
        return 0
    # Revalidate the input bytes immediately before making the isolated run directory.
    if digest(source) != source_hash or digest(restart) != restart_hash or destination.exists():
        print(json.dumps({"completed": False, "gradient_pass": False, "error": "Inputs/output changed since plan"}))
        return 1
    destination.mkdir(parents=True, exist_ok=False)
    receipt = {"started_utc": datetime.now(UTC).isoformat(), "completed": False, "gradient_pass": False,
               "source_sha256": source_hash, "restart_sha256": restart_hash, "scope": SCOPE}
    try:
        for name in ("prefs", "configuration", "tmp"):
            (destination / name).mkdir()
        rendered = template.replace('"__RESTART_MODEL__"', json.dumps(restart.as_posix(), ensure_ascii=True))
        rendered = rendered.replace('"__RUN_DIRECTORY__"', json.dumps(destination.as_posix(), ensure_ascii=True))
        native = destination / source.name
        native.write_text(rendered, encoding="utf-8")
        plan_path = destination / "plan.json"
        plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        receipt.update(rendered_source_sha256=digest(native), plan_sha256=digest(plan_path))
        code, elapsed = process([str(compiler), str(native)], destination, destination / "compile.log", 120)
        receipt.update(compile_exit=code, compile_seconds=elapsed)
        class_file = destination / "CvfDiscreteGradientProbe.class"
        if code == 0 and class_file.is_file() and class_file.stat().st_size:
            command = [str(batch), "-np", str(args.processors), "-prefsdir", str(destination / "prefs"),
                       "-configuration", str(destination / "configuration"), "-tmpdir", str(destination / "tmp"),
                       "-inputfile", str(class_file), "-batchlog", str(destination / "batch.log")]
            code, elapsed = process(command, destination, destination / "console.log", args.timeout)
            receipt.update(batch_exit=code, batch_seconds=elapsed)
            console = (destination / "console.log").read_text(encoding="utf-8", errors="replace")
            receipt["completed"] = (code == 0 and console.splitlines().count(COMPLETE) == 1
                                    and (destination / "batch.log").is_file()
                                    and (destination / "batch.log").stat().st_size > 0)
            if receipt["completed"]:
                try:
                    receipt["gradient_check"] = parse_diagnostic(console)
                    receipt["gradient_pass"] = receipt["gradient_check"]["gradient_pass"]
                except ValueError as exc:
                    receipt["gradient_check_error"] = str(exc)
        else:
            receipt["error"] = "Native compilation failed or fresh nonempty top-level class missing"
    except (OSError, ValueError) as exc:
        receipt["error"] = str(exc)
    receipt["artifacts"] = {p.name: {"bytes": p.stat().st_size, "sha256": digest(p)}
                            for p in destination.iterdir() if p.is_file()}
    (destination / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2), flush=True)
    if not receipt["completed"] or "gradient_check_error" in receipt:
        return 1
    return 0 if receipt["gradient_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
