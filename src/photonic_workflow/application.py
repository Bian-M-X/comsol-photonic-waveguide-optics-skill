"""Typed application use cases shared by CLI and MCP transports."""

from __future__ import annotations

from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import CONFIG_NAME, load_project_config
from .exceptions import InvalidInputError
from .gates import GateLedger
from .runtime import RunStore
from .security import ensure_within_allowed_roots

MAX_PROJECT_STATUS_RUNS = 20


@dataclass(frozen=True, slots=True)
class RunRecoveryView:
    """Bounded recovery evidence for one corrupt run directory."""

    recoverable: bool
    missing: tuple[str, ...]
    mismatches: tuple[str, ...]

    def to_payload(self) -> dict[str, Any]:
        return {
            "recoverable": self.recoverable,
            "missing": list(self.missing),
            "mismatches": list(self.mismatches),
        }


@dataclass(frozen=True, slots=True)
class ProjectRunView:
    """One run projection in a project-status response."""

    run_id: str
    manifest: dict[str, Any] | None
    recovery: RunRecoveryView

    @property
    def trusted(self) -> bool:
        return bool(
            self.recovery.recoverable
            and self.manifest is not None
            and self.manifest.get("execution_status") == "succeeded"
            and self.manifest.get("acceptance_status") == "accepted"
        )

    def to_payload(self) -> dict[str, Any]:
        if self.recovery.recoverable and self.manifest is not None:
            # Preserve the original CLI shape for healthy runs.
            return deepcopy(self.manifest)
        return {
            "run_id": self.run_id,
            "status": "corrupt",
            "recovery": self.recovery.to_payload(),
        }


@dataclass(frozen=True, slots=True)
class ProjectStatusView:
    """Transport-neutral, bounded project status."""

    project: str
    profile: str
    runs: tuple[ProjectRunView, ...]
    latest_trusted_run: dict[str, Any] | None
    gates: dict[str, Any]

    def to_payload(self) -> dict[str, Any]:
        return {
            "project": self.project,
            "profile": self.profile,
            "runs": [run.to_payload() for run in self.runs],
            "latest_trusted_run": deepcopy(self.latest_trusted_run),
            "gates": deepcopy(self.gates),
        }


class ProjectStatusService:
    """Load one bounded project-status snapshot under an explicit read policy."""

    def __init__(
        self,
        project_root: Path,
        *,
        read_roots: Sequence[Path],
    ) -> None:
        self.read_roots = tuple(root.resolve() for root in read_roots)
        if not self.read_roots:
            raise InvalidInputError("project status requires at least one read root")
        self.project_root = ensure_within_allowed_roots(
            project_root,
            self.read_roots,
        )

    def inspect(
        self,
        *,
        run_limit: int = MAX_PROJECT_STATUS_RUNS,
    ) -> ProjectStatusView:
        if (
            type(run_limit) is not int
            or run_limit < 1
            or run_limit > MAX_PROJECT_STATUS_RUNS
        ):
            raise InvalidInputError(
                f"run_limit must be an integer from 1 to {MAX_PROJECT_STATUS_RUNS}"
            )

        # Validate every path that downstream readers derive from the project
        # root. This prevents a project-local symlink from expanding an MCP
        # caller's read policy.
        ensure_within_allowed_roots(
            self.project_root / CONFIG_NAME,
            self.read_roots,
        )
        root, config = load_project_config(self.project_root)
        ensure_within_allowed_roots(
            root / "verification" / "gates.json",
            self.read_roots,
        )
        gates = GateLedger(root).summary()

        runs_root = ensure_within_allowed_roots(
            root / "runs",
            self.read_roots,
        )
        run_ids: list[str] = []
        if runs_root.is_dir():
            for candidate in runs_root.iterdir():
                checked = ensure_within_allowed_roots(
                    candidate,
                    self.read_roots,
                )
                if checked.is_dir():
                    run_ids.append(candidate.name)
        selected_run_ids = sorted(run_ids, reverse=True)[:run_limit]

        store = RunStore(root, list(self.read_roots))
        runs = tuple(
            self._recover_run(store, run_id)
            for run_id in selected_run_ids
        )
        trusted = [run.manifest for run in runs if run.trusted and run.manifest]
        latest_trusted = (
            max(trusted, key=self._manifest_timestamp)
            if trusted
            else None
        )
        return ProjectStatusView(
            project=config.stable_id,
            profile=config.profile.value,
            runs=runs,
            latest_trusted_run=latest_trusted,
            gates=gates,
        )

    @staticmethod
    def _recover_run(store: RunStore, run_id: str) -> ProjectRunView:
        recovery = store.recover(run_id)
        manifest = recovery.get("manifest")
        manifest_payload = manifest if isinstance(manifest, dict) else None
        view = RunRecoveryView(
            recoverable=bool(recovery.get("recoverable")),
            missing=tuple(str(item) for item in recovery.get("missing", ())),
            mismatches=tuple(str(item) for item in recovery.get("mismatches", ())),
        )
        return ProjectRunView(
            run_id=run_id,
            manifest=manifest_payload,
            recovery=view,
        )

    @staticmethod
    def _manifest_timestamp(manifest: dict[str, Any]) -> tuple[datetime, str]:
        raw = manifest.get("finished_at") or manifest.get("created_at")
        if not isinstance(raw, str):
            raise InvalidInputError("trusted run manifest is missing its timestamp")
        try:
            timestamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError as exc:
            raise InvalidInputError(
                "trusted run manifest has an invalid timestamp"
            ) from exc
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        return timestamp, str(manifest.get("stable_id", ""))


__all__ = [
    "MAX_PROJECT_STATUS_RUNS",
    "ProjectRunView",
    "ProjectStatusService",
    "ProjectStatusView",
    "RunRecoveryView",
]
