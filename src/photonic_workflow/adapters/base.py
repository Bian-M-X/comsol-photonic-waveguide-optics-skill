from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from photonic_workflow.exceptions import UnavailableCapabilityError
from photonic_workflow.models.contracts import (
    AdapterDescriptor,
    AvailabilityStatus,
    ContractBase,
    ImplementationStatus,
    RunSpec,
)
from photonic_workflow.security import command_shape


@dataclass(frozen=True)
class PlannedFile:
    """A deterministic file that a later run-staging step may materialize."""

    path: Path
    content: str
    media_type: str = "text/plain"

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()

    def public_payload(self) -> dict[str, str]:
        return {
            "name": self.path.name,
            "media_type": self.media_type,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class AdapterPlan:
    """Internal execution plan with a deliberately redacted public projection."""

    adapter: str
    operation: str
    dry_run: bool
    command: tuple[str, ...]
    working_directory: Path
    timeout_s: int
    expected_artifacts: tuple[Path, ...] = ()
    generated_files: tuple[PlannedFile, ...] = ()
    environment: tuple[tuple[str, str], ...] = ()
    implementation: ImplementationStatus = ImplementationStatus.UNVERIFIED
    availability: AvailabilityStatus = AvailabilityStatus.UNVERIFIED
    reasons: tuple[str, ...] = ()
    sensitive_command_indexes: tuple[int, ...] = ()
    sensitive_environment_keys: tuple[str, ...] = ()
    shell: bool = field(default=False, init=False)
    execution_verified: bool = field(default=False, init=False)

    def environment_dict(self) -> dict[str, str]:
        return dict(self.environment)

    def public_payload(self) -> dict[str, Any]:
        sensitive_keys = set(self.sensitive_environment_keys)
        environment = {
            key: "<redacted>" if key in sensitive_keys else value
            for key, value in self.environment
        }
        return {
            "adapter": self.adapter,
            "operation": self.operation,
            "dry_run": self.dry_run,
            "shell": self.shell,
            "execution_verified": self.execution_verified,
            "implementation": self.implementation.value,
            "availability": self.availability.value,
            "command_shape": command_shape(self.command, self.sensitive_command_indexes),
            "working_directory": "<runtime-directory>",
            "timeout_s": self.timeout_s,
            "expected_artifacts": [path.name for path in self.expected_artifacts],
            "generated_files": [item.public_payload() for item in self.generated_files],
            "environment": environment,
            "reasons": list(self.reasons),
        }


class Adapter(ABC):
    """Common Phase-A adapter contract.

    Concrete adapters may implement probes and planning. External execution is
    unavailable until a concrete adapter overrides ``execute`` and supplies
    backend-specific parity and failure-mode evidence.
    """

    descriptor: AdapterDescriptor

    @abstractmethod
    def check(self) -> ContractBase:
        raise NotImplementedError

    @abstractmethod
    def plan(self, run_spec: RunSpec) -> AdapterPlan:
        raise NotImplementedError

    def execute(self, plan: AdapterPlan) -> ContractBase:
        raise UnavailableCapabilityError(
            f"{self.descriptor.adapter} execution is not verified or enabled in Phase A"
        )
