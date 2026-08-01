"""Deterministic, explicit migration support for persisted contracts."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from photonic_workflow.exceptions import IncompatibleVersionError, InvalidInputError

ContractTransform = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class ContractMigration:
    """One pure migration step for one contract type."""

    migration_id: str
    contract_type: str
    from_version: str
    to_version: str
    transform: ContractTransform

    def __post_init__(self) -> None:
        for field_name in (
            "migration_id",
            "contract_type",
            "from_version",
            "to_version",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")
        if self.from_version == self.to_version:
            raise ValueError("a migration must change schema_version")


@dataclass(frozen=True)
class MigrationResult:
    payload: dict[str, Any]
    applied_migrations: tuple[str, ...] = ()


class ContractMigrationRegistry:
    """Route old contract versions through explicitly registered steps.

    The registry never guesses a migration and never drops unknown fields.
    Callers still run the migrated payload through the strict Pydantic model.
    """

    def __init__(self) -> None:
        self._steps: dict[tuple[str, str], ContractMigration] = {}
        self._migration_ids: set[str] = set()
        self._frozen = False

    @classmethod
    def from_steps(
        cls,
        migrations: Iterable[ContractMigration],
        *,
        frozen: bool = False,
    ) -> ContractMigrationRegistry:
        registry = cls()
        registry.register_many(migrations)
        if frozen:
            registry.freeze()
        return registry

    def register(self, migration: ContractMigration) -> None:
        self.register_many((migration,))

    def register_many(self, migrations: Iterable[ContractMigration]) -> None:
        """Register a batch atomically.

        Built-in migrations are loaded through this method at module import, so
        every parser sees the same deterministic registry before its first
        contract is read.
        """

        if self._frozen:
            raise InvalidInputError("contract migration registry is frozen")
        pending = tuple(migrations)
        steps = dict(self._steps)
        migration_ids = set(self._migration_ids)
        for migration in pending:
            if not isinstance(migration, ContractMigration):
                raise InvalidInputError("invalid contract migration registration")
            key = (migration.contract_type, migration.from_version)
            if key in steps:
                raise InvalidInputError(
                    "contract migration is already registered for "
                    f"{migration.contract_type} schema {migration.from_version}"
                )
            if migration.migration_id in migration_ids:
                raise InvalidInputError(
                    f"contract migration ID is already registered: "
                    f"{migration.migration_id}"
                )
            steps[key] = migration
            migration_ids.add(migration.migration_id)
        self._steps = steps
        self._migration_ids = migration_ids

    def migrations(self) -> tuple[ContractMigration, ...]:
        """Return registrations in a stable review order."""

        return tuple(
            self._steps[key]
            for key in sorted(self._steps)
        )

    def freeze(self) -> ContractMigrationRegistry:
        """Prevent command order or plugins from mutating parser semantics."""

        self._frozen = True
        return self

    @property
    def frozen(self) -> bool:
        return self._frozen

    def migrate(
        self,
        payload: dict[str, Any],
        *,
        contract_type: str,
        target_version: str,
    ) -> MigrationResult:
        normalized = dict(payload)
        source_version = normalized.get("schema_version")
        if source_version is None:
            raise InvalidInputError(
                f"{contract_type} contract must declare schema_version"
            )
        if not isinstance(source_version, str) or not source_version.strip():
            raise InvalidInputError("schema_version must be a non-empty string")

        original_stable_id = normalized.get("stable_id")
        applied: list[str] = []
        visited: set[str] = set()
        current_version = source_version

        while current_version != target_version:
            if current_version in visited:
                raise IncompatibleVersionError(
                    f"contract migration cycle detected for {contract_type} "
                    f"at schema {current_version}"
                )
            visited.add(current_version)
            step = self._steps.get((contract_type, current_version))
            if step is None:
                raise IncompatibleVersionError(
                    f"{contract_type} schema {source_version!r} is incompatible; "
                    f"this runtime accepts {target_version!r} and has no registered "
                    f"migration from {current_version!r}"
                )
            candidate = step.transform(dict(normalized))
            if not isinstance(candidate, dict):
                raise InvalidInputError(
                    f"contract migration {step.migration_id!r} did not return an object"
                )
            if candidate.get("contract_type", contract_type) != contract_type:
                raise InvalidInputError(
                    f"contract migration {step.migration_id!r} changed contract_type"
                )
            if (
                original_stable_id is not None
                and candidate.get("stable_id") != original_stable_id
            ):
                raise InvalidInputError(
                    f"contract migration {step.migration_id!r} changed stable_id"
                )
            normalized = dict(candidate)
            normalized["schema_version"] = step.to_version
            current_version = step.to_version
            applied.append(step.migration_id)

        if applied:
            provenance = normalized.get("provenance", [])
            if not isinstance(provenance, list):
                raise InvalidInputError(
                    "contract provenance must be an array before migration markers "
                    "can be recorded"
                )
            normalized["provenance"] = [
                *provenance,
                *(f"contract-migration:{migration_id}" for migration_id in applied),
            ]
        return MigrationResult(normalized, tuple(applied))


__all__ = [
    "ContractMigration",
    "ContractMigrationRegistry",
    "ContractTransform",
    "MigrationResult",
]
