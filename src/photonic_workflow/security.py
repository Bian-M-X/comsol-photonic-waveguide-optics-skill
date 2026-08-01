from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Iterable, Sequence
from pathlib import Path

from .exceptions import SecurityViolationError

SAFE_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
SAFE_LABEL_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
SAFE_MATLAB_FUNCTION_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.]{0,127}\Z")
WINDOWS_RESERVED_BASENAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}
MATLAB_STATEMENT_TOKENS = (";", "\n", "\r", "'", '"', "(", ")", "[", "]", "{", "}", "!", "=")
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?im)\b(api[_-]?key|access[_-]?token|auth[_-]?token|password|passwd|secret)"
    r"\s*[:=]\s*[^\s,;]+"
)
LICENSE_SETTING_RE = re.compile(r"(?im)\b(?:LM_LICENSE_FILE|COMSOL_LICENSE)\b\s*[:=]\s*[^\s,;]+")
USER_PATH_RE = re.compile(r"(?i)C:\\Users\\[^\\\s]+")
VISA_RESOURCE_RE = re.compile(
    r"(?i)\b(?:GPIB|TCPIP|USB|ASRL|PXI|VXI)\d*(?:::[A-Za-z0-9._-]+)+(?:::INSTR)?\b"
)


def _norm(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))


def ensure_within_allowed_roots(path: Path, allowed_roots: Iterable[Path]) -> Path:
    resolved = path.resolve()
    resolved_norm = _norm(resolved)
    for root in allowed_roots:
        root_norm = _norm(root)
        if resolved_norm == root_norm or resolved_norm.startswith(root_norm + os.sep):
            return resolved
    raise SecurityViolationError(f"path is outside configured allowed roots: {path}")


def validate_safe_label(value: str) -> str:
    if not isinstance(value, str) or not value or value in {".", ".."}:
        raise SecurityViolationError("label must be a non-empty safe basename")
    if "/" in value or "\\" in value or Path(value).is_absolute() or not SAFE_LABEL_RE.fullmatch(value):
        raise SecurityViolationError(
            "label must be a basename using only ASCII letters, digits, '.', '_' and '-'"
        )
    if value.split(".", 1)[0].upper() in WINDOWS_RESERVED_BASENAMES:
        raise SecurityViolationError(f"label is a Windows reserved basename: {value}")
    return value


def validate_stable_id(value: str) -> str:
    if not isinstance(value, str) or not SAFE_ID_RE.fullmatch(value):
        raise SecurityViolationError(
            "stable_id must begin with an ASCII letter or digit and contain only letters, digits, '.', '_', ':' or '-'"
        )
    return value


def validate_matlab_function(value: str, allowlist: Sequence[str]) -> str:
    if not isinstance(value, str) or not SAFE_MATLAB_FUNCTION_RE.fullmatch(value):
        raise SecurityViolationError("MATLAB function must be a single qualified function name")
    if any(token in value for token in MATLAB_STATEMENT_TOKENS):
        raise SecurityViolationError("MATLAB statements are not accepted")
    if value not in set(allowlist):
        raise SecurityViolationError(f"MATLAB function is not allowlisted: {value}")
    return value


def validate_fixed_script(value: str, allowlist: Sequence[str], kind: str) -> str:
    if not isinstance(value, str) or value not in set(allowlist):
        raise SecurityViolationError(f"{kind} script is not allowlisted")
    if any(token in value for token in ("\n", "\r", ";", "`", "$(", "&&", "||")):
        raise SecurityViolationError(f"{kind} script contains statement or shell syntax")
    return value


def validate_matlab_paths(paths: Sequence[Path], allowed_roots: Sequence[Path]) -> tuple[Path, ...]:
    resolved: list[Path] = []
    for path in paths:
        checked = ensure_within_allowed_roots(path, allowed_roots)
        lowered = checked.name.lower()
        if lowered in {"pathdef.m", "startup.m"}:
            raise SecurityViolationError("permanent or implicit MATLAB path hooks are not accepted")
        resolved.append(checked)
    return tuple(resolved)


def require_known_mex(path: Path, expected_sha256: str | None, allowed_roots: Sequence[Path]) -> str:
    checked = ensure_within_allowed_roots(path, allowed_roots)
    if checked.suffix.lower() not in {".mexw64", ".mexa64", ".mexmaci64"}:
        raise SecurityViolationError("file is not a recognized MEX binary")
    if not expected_sha256:
        raise SecurityViolationError("unknown MEX binaries are not compiled or executed")
    digest = hashlib.sha256(checked.read_bytes()).hexdigest()
    if digest.lower() != expected_sha256.lower():
        raise SecurityViolationError("MEX fingerprint does not match the approved value")
    return digest


def verify_engine_session_identity(actual: str, expected_sha256: str | None) -> None:
    if not expected_sha256:
        raise SecurityViolationError("shared MATLAB session identity must be explicitly approved")
    actual_hash = hashlib.sha256(actual.encode("utf-8")).hexdigest()
    if actual_hash.lower() != expected_sha256.lower():
        raise SecurityViolationError("shared MATLAB session identity does not match the approved fingerprint")


def enforce_commercial_concurrency(worker_count: int, explicitly_authorized: bool) -> int:
    if worker_count < 1:
        raise SecurityViolationError("worker count must be positive")
    if worker_count > 1 and not explicitly_authorized:
        raise SecurityViolationError("commercial solver concurrency above one requires explicit authorization")
    return worker_count


def enforce_instrument_safety(limits: dict[str, float | str | None]) -> None:
    required = ("max_laser_power", "scan_range", "safe_shutdown")
    missing = [name for name in required if limits.get(name) in {None, ""}]
    if missing:
        raise SecurityViolationError(
            "real instrument execution requires explicit physical safety limits: " + ", ".join(missing)
        )


def enforce_tapeout_mutable(frozen: bool) -> None:
    if frozen:
        raise SecurityViolationError("a frozen tapeout manifest cannot be modified in place")


def redact_text(value: str) -> str:
    redacted = SECRET_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}=<redacted>", value)
    redacted = LICENSE_SETTING_RE.sub("<license-setting-redacted>", redacted)
    redacted = USER_PATH_RE.sub(lambda _match: r"C:\Users\<redacted>", redacted)
    redacted = VISA_RESOURCE_RE.sub("<instrument-resource-redacted>", redacted)
    return redacted


def command_shape(command: Sequence[str], sensitive_indexes: Iterable[int] = ()) -> list[str]:
    hidden = set(sensitive_indexes)
    return ["<redacted>" if index in hidden else redact_text(str(item)) for index, item in enumerate(command)]
