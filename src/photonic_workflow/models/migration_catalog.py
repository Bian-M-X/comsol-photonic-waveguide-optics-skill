"""Frozen production catalog for persisted-contract migrations.

Add deterministic one-version steps to ``PRODUCTION_MIGRATIONS`` (or import
them here from contract-specific modules). Historical fixtures and migration
tests are required before the tuple grows. The parser consumes only the frozen
registry below; tests use their own registry instead of mutating production
state.
"""

from __future__ import annotations

from typing import Final

from .versioning import ContractMigration, ContractMigrationRegistry

PRODUCTION_MIGRATIONS: Final[tuple[ContractMigration, ...]] = ()
CONTRACT_MIGRATIONS = ContractMigrationRegistry.from_steps(
    PRODUCTION_MIGRATIONS,
    frozen=True,
)


__all__ = ["CONTRACT_MIGRATIONS", "PRODUCTION_MIGRATIONS"]
