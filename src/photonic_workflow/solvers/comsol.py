from __future__ import annotations

from pathlib import Path
from typing import Any

from photonic_workflow.exceptions import InvalidInputError
from photonic_workflow.security import ensure_within_allowed_roots


def build_java_batch_plan(
    *,
    java_file: Path,
    output_mph: Path,
    batch_log: Path,
    runtime_dir: Path,
    timeout_s: int,
    allowed_roots: list[Path],
    solver_root_source: str = "env:PHOTONIC_SOLVER_ROOT",
) -> dict[str, Any]:
    java = ensure_within_allowed_roots(java_file, allowed_roots)
    output = ensure_within_allowed_roots(output_mph, allowed_roots)
    log = ensure_within_allowed_roots(batch_log, allowed_roots)
    runtime = ensure_within_allowed_roots(runtime_dir, allowed_roots)
    if java.suffix.lower() != ".java":
        raise InvalidInputError("java_file must end with .java")
    if output.suffix.lower() != ".mph":
        raise InvalidInputError("output_mph must end with .mph")
    if log.suffix.lower() != ".log":
        raise InvalidInputError("batch_log must end with .log")
    if not 1 <= timeout_s <= 7 * 24 * 60 * 60:
        raise InvalidInputError("timeout_s must be between 1 and 604800")
    class_file = java.with_suffix(".class")
    prefs = runtime / "prefs"
    config = runtime / "config"
    temporary = runtime / "tmp"
    return {
        "dry_run": True,
        "will_execute": False,
        "solver_root_source": solver_root_source,
        "solver_root_redacted_as": "<PHOTONIC_SOLVER_ROOT>",
        "java_file": str(java),
        "class_file": str(class_file),
        "output_mph": str(output),
        "batch_log": str(log),
        "runtime_dirs": {
            "root": str(runtime),
            "prefs": str(prefs),
            "config": str(config),
            "tmp": str(temporary),
        },
        "timeout_s": timeout_s,
        "compile_command_shape": [
            "<PHOTONIC_SOLVER_ROOT>\\bin\\win64\\comsolcompile.exe",
            str(java),
        ],
        "batch_command_shape": [
            "<PHOTONIC_SOLVER_ROOT>\\bin\\win64\\comsolbatch.exe",
            "-prefsdir",
            str(prefs),
            "-configuration",
            str(config),
            "-tmpdir",
            str(temporary),
            "-inputfile",
            str(class_file),
            "-outputfile",
            str(output),
            "-batchlog",
            str(log),
        ],
        "safety_gate": (
            "dry-run only here; trusted execution remains scripts/invoke-waveguide-java-batch.ps1 "
            "until direct-batch parity is proven"
        ),
        "compiler_policy": (
            "use the vendor comsolcompile entrypoint so the installed COMSOL version owns "
            "its Java classpath and compatibility"
        ),
    }
