from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from pydantic import ValidationError

from photonic_workflow.exceptions import InvalidInputError

from .contracts import MODEL_REGISTRY, ContractBase
from .migration_catalog import CONTRACT_MIGRATIONS
from .versioning import ContractMigrationRegistry

ContractModelT = TypeVar("ContractModelT", bound=ContractBase)


def contract_payload(model: ContractBase) -> dict[str, Any]:
    return {
        "contract_type": model.contract_type,
        **model.model_dump(mode="json"),
    }


def contract_json(model: ContractBase, *, indent: int = 2) -> str:
    return json.dumps(contract_payload(model), indent=indent, ensure_ascii=False, allow_nan=False) + "\n"


def parse_contract(
    payload: Any,
    expected_type: str | None = None,
    *,
    migration_registry: ContractMigrationRegistry | None = None,
) -> ContractBase:
    if not isinstance(payload, dict):
        raise InvalidInputError("contract root must be a JSON object")
    contract_type = payload.get("contract_type")
    if expected_type is not None and contract_type != expected_type:
        raise InvalidInputError(f"expected contract_type {expected_type!r}, got {contract_type!r}")
    model_class = MODEL_REGISTRY.get(str(contract_type))
    if model_class is None:
        raise InvalidInputError(f"unknown contract_type: {contract_type!r}")
    registry = (
        migration_registry
        if migration_registry is not None
        else CONTRACT_MIGRATIONS
    )
    migration = registry.migrate(
        payload,
        contract_type=model_class.contract_type,
        target_version=model_class.current_schema_version,
    )
    body = migration.payload
    body.pop("contract_type", None)
    try:
        return model_class.model_validate(body)
    except ValidationError as exc:
        raise InvalidInputError(f"invalid {contract_type} contract: {exc}") from exc


def parse_contract_body(
    payload: Any,
    expected_type: str,
    *,
    migration_registry: ContractMigrationRegistry | None = None,
) -> ContractBase:
    """Parse a typed body from a transport that omits ``contract_type``.

    TOML project configuration and a small number of legacy fixed-type
    transports use this entry point. The caller supplies the type; the same
    version gate and strict model validation still apply.
    """

    if not isinstance(payload, dict):
        raise InvalidInputError("contract body must be an object")
    body = dict(payload)
    declared_type = body.get("contract_type")
    if declared_type not in {None, expected_type}:
        raise InvalidInputError(
            f"expected contract_type {expected_type!r}, got {declared_type!r}"
        )
    body["contract_type"] = expected_type
    return parse_contract(
        body,
        expected_type,
        migration_registry=migration_registry,
    )


def revalidate_internal(
    model_class: type[ContractModelT],
    payload: dict[str, Any],
) -> ContractModelT:
    """Validate a mutation derived from an already parsed typed contract.

    This deliberately performs no migration. External JSON/TOML readers must
    use ``parse_contract`` or ``parse_contract_body`` first.
    """

    try:
        return model_class.model_validate(payload)
    except ValidationError as exc:
        raise InvalidInputError(
            f"invalid internal {model_class.contract_type} update: {exc}"
        ) from exc


def load_contract(
    path: Path,
    expected_type: str | None = None,
    *,
    migration_registry: ContractMigrationRegistry | None = None,
) -> ContractBase:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise InvalidInputError(f"contract not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise InvalidInputError(f"invalid JSON in {path}: {exc}") from exc
    return parse_contract(
        payload,
        expected_type,
        migration_registry=migration_registry,
    )


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        Path(temporary).replace(path)
    except Exception:
        try:
            Path(temporary).unlink(missing_ok=True)
        finally:
            raise


def atomic_create_text(
    path: Path,
    text: str,
    *,
    path_guard: Callable[[Path], None] | None = None,
) -> None:
    """Create ``path`` atomically without replacing an existing file.

    The temporary file is created in the destination directory so the final
    hard-link operation stays on one filesystem.  ``os.link`` is deliberately
    used instead of a check-then-replace sequence: it fails atomically when the
    destination already exists.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    if path_guard is not None:
        path_guard(path)
    handle, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    created = False
    try:
        if path_guard is not None:
            path_guard(path)
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        if path_guard is not None:
            path_guard(path)
        os.link(temporary, path)
        created = True
        if path_guard is not None:
            path_guard(path)
    except Exception:
        if created:
            path.unlink(missing_ok=True)
        raise
    finally:
        Path(temporary).unlink(missing_ok=True)


def write_contract(path: Path, model: ContractBase) -> None:
    atomic_write_text(path, contract_json(model))


def create_contract(path: Path, model: ContractBase) -> None:
    """Create a contract atomically and fail if ``path`` already exists."""

    atomic_create_text(path, contract_json(model))
