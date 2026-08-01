from __future__ import annotations

import json
import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from photonic_workflow.exceptions import InvalidInputError
from photonic_workflow.models.contracts import ExecutionStatus, MatlabResultManifest
from photonic_workflow.models.io import parse_contract_body
from photonic_workflow.security import ensure_within_allowed_roots


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number is not allowed: {value}")


def _validate_relative_artifact_path(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise InvalidInputError(f"{field_name} must be a non-empty relative path")
    path = Path(value)
    if path.is_absolute() or path.drive or ".." in path.parts:
        raise InvalidInputError(f"{field_name} must not be absolute or contain traversal")


def parse_matlab_result(
    payload: Any,
    *,
    expected_run_id: str | None = None,
) -> MatlabResultManifest:
    if not isinstance(payload, dict):
        raise InvalidInputError("MATLAB result root must be a JSON object")
    result = parse_contract_body(payload, "MatlabResultManifest")
    assert isinstance(result, MatlabResultManifest)

    if expected_run_id is not None and result.run_id != expected_run_id:
        raise InvalidInputError(
            f"MATLAB result run_id {result.run_id!r} does not match {expected_run_id!r}"
        )
    if result.duration_s is not None and (
        not math.isfinite(result.duration_s) or result.duration_s < 0.0
    ):
        raise InvalidInputError("MATLAB result duration_s must be finite and non-negative")
    if result.execution_status == ExecutionStatus.SUCCEEDED and result.exit_code != 0:
        raise InvalidInputError("a succeeded MATLAB result requires exit_code 0")
    if result.execution_status == ExecutionStatus.FAILED and result.exit_code == 0:
        raise InvalidInputError("a failed MATLAB result cannot have exit_code 0")
    if result.execution_status == ExecutionStatus.PLANNED and result.exit_code is not None:
        raise InvalidInputError("a planned MATLAB result cannot have an exit_code")

    artifact_ids: set[str] = set()
    for index, artifact in enumerate(result.artifacts):
        _validate_relative_artifact_path(
            artifact.relative_path,
            f"artifacts[{index}].relative_path",
        )
        if artifact.stable_id in artifact_ids:
            raise InvalidInputError(
                f"MATLAB result contains duplicate artifact stable_id: {artifact.stable_id}"
            )
        artifact_ids.add(artifact.stable_id)
    if result.log_path not in {None, ""}:
        _validate_relative_artifact_path(result.log_path, "log_path")
    return result


def load_matlab_result(
    path: Path,
    *,
    expected_run_id: str | None = None,
    allowed_roots: Sequence[Path] | None = None,
) -> MatlabResultManifest:
    checked = (
        ensure_within_allowed_roots(path, allowed_roots)
        if allowed_roots is not None
        else path.resolve()
    )
    try:
        payload = json.loads(
            checked.read_text(encoding="utf-8"),
            parse_constant=_reject_json_constant,
        )
    except FileNotFoundError as exc:
        raise InvalidInputError(f"MATLAB result not found: {path}") from exc
    except (json.JSONDecodeError, ValueError) as exc:
        raise InvalidInputError(f"invalid MATLAB result JSON in {path}: {exc}") from exc
    return parse_matlab_result(payload, expected_run_id=expected_run_id)
