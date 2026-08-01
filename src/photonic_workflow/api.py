from __future__ import annotations

import json
from typing import Any

from .compatibility import CURRENT_API_ENVELOPE_SCHEMA_VERSION
from .exceptions import ExitCode


def envelope(
    *,
    command: str,
    data: Any,
    ok: bool = True,
    status: str = "success",
    exit_code: int | ExitCode = ExitCode.SUCCESS,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": CURRENT_API_ENVELOPE_SCHEMA_VERSION,
        "command": command,
        "ok": ok,
        "status": status,
        "exit_code": int(exit_code),
        "data": data,
        "warnings": warnings or [],
        "errors": errors or [],
    }


def strict_json(value: Any, *, indent: int = 2) -> str:
    return json.dumps(value, indent=indent, ensure_ascii=False, allow_nan=False)
