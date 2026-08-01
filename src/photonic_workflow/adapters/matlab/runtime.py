from __future__ import annotations

import re
import shutil
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from photonic_workflow.exceptions import InvalidInputError, UnavailableCapabilityError
from photonic_workflow.models.contracts import (
    AvailabilityStatus,
    MatlabEnvironmentReport,
    MatlabRunSpec,
    MatlabToolboxRecord,
    RunSpec,
)
from photonic_workflow.models.io import contract_json
from photonic_workflow.security import (
    enforce_commercial_concurrency,
    ensure_within_allowed_roots,
    validate_matlab_paths,
    validate_safe_label,
)

from ..base import Adapter, AdapterPlan, PlannedFile
from .descriptors import MATLAB_RUNTIME_DESCRIPTOR
from .engine import EngineProbeResult, probe_matlab_engine
from .inventory import (
    MatlabProductInventory,
    load_product_inventory,
    parse_product_inventory,
)

ExecutableResolver = Callable[[str], str | None]
EngineProbe = Callable[[str | None], EngineProbeResult]

MATLAB_EXECUTABLE_ALIAS_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
MATLAB_ENTRYPOINT_IDS = ("photonic.environment.validate.v1",)
PHASE_A_OPERATIONS = ("environment.validate",)
WRAPPER_NAME = "photonic_batch_wrapper"
WRAPPER_FILENAME = f"{WRAPPER_NAME}.m"


def _default_matlab_entry_root() -> Path:
    packaged = Path(__file__).resolve().parents[2] / "data" / "matlab"
    if packaged.is_dir():
        return packaged
    return Path(__file__).resolve().parents[4] / "matlab"


def _default_engine_probe(release: str | None) -> EngineProbeResult:
    return probe_matlab_engine(matlab_release=release)


class MatlabRuntimeAdapter(Adapter):
    """MATLAB Phase-A environment probe and fixed-wrapper dry-run planner."""

    descriptor = MATLAB_RUNTIME_DESCRIPTOR

    def __init__(
        self,
        *,
        project_root: Path | None = None,
        allowed_roots: Sequence[Path] | None = None,
        executable_alias: str = "matlab",
        matlab_entry_root: Path | None = None,
        inventory: MatlabProductInventory | Mapping[str, Any] | Path | None = None,
        community_toolbox_paths: Mapping[str, Path] | None = None,
        community_toolbox_fingerprints: Mapping[str, str] | None = None,
        executable_resolver: ExecutableResolver = shutil.which,
        engine_probe: EngineProbe = _default_engine_probe,
    ) -> None:
        self.project_root = (project_root or Path.cwd()).resolve()
        self.allowed_roots = tuple(
            root.resolve() for root in (allowed_roots or (self.project_root,))
        )
        ensure_within_allowed_roots(self.project_root, self.allowed_roots)
        self.executable_alias = self._validate_executable_alias(executable_alias)
        self.matlab_entry_root = (
            matlab_entry_root.resolve()
            if matlab_entry_root is not None
            else _default_matlab_entry_root().resolve()
        )
        self.inventory_source = inventory
        self.community_toolbox_paths = dict(community_toolbox_paths or {})
        self.community_toolbox_fingerprints = dict(community_toolbox_fingerprints or {})
        self.executable_resolver = executable_resolver
        self.engine_probe = engine_probe

    @staticmethod
    def _validate_executable_alias(value: str) -> str:
        if not isinstance(value, str) or not MATLAB_EXECUTABLE_ALIAS_RE.fullmatch(value):
            raise InvalidInputError(
                "MATLAB executable alias must be a safe basename such as 'matlab' or 'matlab.exe'"
            )
        return value

    def _inventory(self) -> MatlabProductInventory | None:
        if self.inventory_source is None:
            return None
        if isinstance(self.inventory_source, MatlabProductInventory):
            return self.inventory_source
        if isinstance(self.inventory_source, Path):
            checked = ensure_within_allowed_roots(
                self._resolve_project_path(self.inventory_source),
                self.allowed_roots,
            )
            return load_product_inventory(checked)
        return parse_product_inventory(dict(self.inventory_source))

    def _resolve_project_path(self, value: str | Path) -> Path:
        path = Path(value)
        return (self.project_root / path).resolve() if not path.is_absolute() else path.resolve()

    def _community_records(self) -> tuple[MatlabToolboxRecord, ...]:
        records: list[MatlabToolboxRecord] = []
        unexpected_fingerprints = set(self.community_toolbox_fingerprints) - set(
            self.community_toolbox_paths
        )
        if unexpected_fingerprints:
            raise InvalidInputError(
                "community toolbox fingerprints have no matching path aliases: "
                + ", ".join(sorted(unexpected_fingerprints))
            )
        for alias, raw_path in sorted(self.community_toolbox_paths.items()):
            safe_alias = validate_safe_label(alias)
            path = ensure_within_allowed_roots(
                self._resolve_project_path(raw_path),
                self.allowed_roots,
            )
            fingerprint = self.community_toolbox_fingerprints.get(alias)
            if fingerprint is not None and not re.fullmatch(r"[A-Fa-f0-9]{64}", fingerprint):
                raise InvalidInputError(
                    f"community toolbox {alias!r} fingerprint must be a SHA-256 hex digest"
                )
            records.append(
                MatlabToolboxRecord(
                    stable_id=f"matlab-community:{safe_alias}",
                    name=alias,
                    source="configured MATLAB community-toolbox path alias",
                    status="installed" if path.is_dir() else "unavailable",
                    product_name=alias,
                    installed=path.is_dir(),
                    license_verified=False,
                    path_alias=alias,
                    fingerprint=fingerprint,
                    provenance=["filesystem-presence-only; no toolbox code executed"],
                )
            )
        return tuple(records)

    def check(self) -> MatlabEnvironmentReport:
        inventory = self._inventory()
        executable = self.executable_resolver(self.executable_alias)
        release = inventory.release if inventory else None
        engine = self.engine_probe(release)
        configured_community = self._community_records()

        reasons: list[str] = []
        if executable is None:
            availability = AvailabilityStatus.UNAVAILABLE
            reasons.append(f"MATLAB executable alias {self.executable_alias!r} was not resolved")
        elif inventory is None:
            availability = AvailabilityStatus.UNVERIFIED
            reasons.append(
                "MATLAB executable was located, but no structured local inventory was supplied"
            )
        elif inventory.availability == AvailabilityStatus.AVAILABLE and inventory.batch_capable:
            availability = AvailabilityStatus.AVAILABLE
            reasons.append("structured inventory reports a batch-capable MATLAB installation")
        else:
            availability = inventory.availability
            reasons.append(
                "structured inventory does not establish an available batch-capable MATLAB"
            )
        reasons.extend(engine.reasons)

        inventory_community = inventory.community_toolboxes if inventory else ()
        community = (*inventory_community, *configured_community)
        return MatlabEnvironmentReport(
            stable_id="capability:matlab-environment",
            name="MATLAB environment",
            source="local executable discovery and optional structured inventory; no MATLAB process started",
            status=availability.value,
            validity="unknown",
            provenance=reasons,
            availability=availability,
            executable_alias=self.executable_alias,
            root_alias=inventory.root_alias if inventory else None,
            release=release,
            version=inventory.version if inventory else None,
            platform=inventory.platform if inventory else None,
            architecture=inventory.architecture if inventory else None,
            batch_capable=bool(executable) and bool(inventory and inventory.batch_capable),
            products=list(inventory.products) if inventory else [],
            engine_importable=engine.importable,
            engine_compatible=engine.compatible,
            shared_session_count=engine.shared_session_count,
            community_toolboxes=list(community),
            comsol_livelink=(
                inventory.comsol_livelink
                if inventory
                else AvailabilityStatus.UNVERIFIED
            ),
            lumerical_api=(
                inventory.lumerical_api if inventory else AvailabilityStatus.UNVERIFIED
            ),
            instrument_control=(
                inventory.instrument_control
                if inventory
                else AvailabilityStatus.UNVERIFIED
            ),
            simulink=inventory.simulink if inventory else AvailabilityStatus.UNVERIFIED,
            redacted=True,
        )

    def _required_path(self, raw: str, field_name: str) -> Path:
        if not isinstance(raw, str) or not raw.strip():
            raise InvalidInputError(f"{field_name} must be a non-empty path")
        return ensure_within_allowed_roots(
            self._resolve_project_path(raw),
            self.allowed_roots,
        )

    def _trusted_wrapper(self) -> str:
        wrapper = self.matlab_entry_root / "startup" / WRAPPER_FILENAME
        entry = self.matlab_entry_root / "+photonic" / "entry.m"
        if not wrapper.is_file() or not entry.is_file():
            raise UnavailableCapabilityError(
                "trusted MATLAB fixed entry files are unavailable from this installation"
            )
        content = wrapper.read_text(encoding="utf-8")
        if f"function {WRAPPER_NAME}" not in content:
            raise InvalidInputError("trusted MATLAB wrapper has an unexpected function declaration")
        lowered = content.casefold()
        if any(token in lowered for token in ("eval(", "evalin(", "feval(", "system(")):
            raise InvalidInputError("trusted MATLAB wrapper contains a forbidden dynamic execution primitive")
        return content

    def plan(self, run_spec: RunSpec) -> AdapterPlan:
        if not isinstance(run_spec, MatlabRunSpec):
            raise InvalidInputError("MatlabRuntimeAdapter requires a MatlabRunSpec")
        if run_spec.execution_model != "batch":
            raise InvalidInputError("Phase A supports only the MATLAB batch execution model")
        if run_spec.entrypoint_id not in MATLAB_ENTRYPOINT_IDS:
            raise InvalidInputError(
                f"MATLAB entrypoint_id is not registered: {run_spec.entrypoint_id!r}"
            )
        if run_spec.operation not in PHASE_A_OPERATIONS:
            raise UnavailableCapabilityError(
                f"MATLAB operation {run_spec.operation!r} is not implemented in Phase A"
            )
        if not run_spec.dry_run:
            raise UnavailableCapabilityError(
                "real MATLAB execution remains unverified in Phase A; use dry_run=true"
            )
        enforce_commercial_concurrency(
            run_spec.worker_count,
            run_spec.commercial_parallel_authorized,
        )

        run_spec_path = self._required_path(run_spec.run_spec_path, "run_spec_path")
        result_path = self._required_path(run_spec.result_path, "result_path")
        runtime_directory = self._required_path(
            run_spec.runtime_directory,
            "runtime_directory",
        )
        if runtime_directory == self.project_root:
            raise InvalidInputError("runtime_directory must be isolated below the project root")

        requested_matlab_paths = tuple(
            self._resolve_project_path(path) for path in run_spec.matlab_paths
        )
        matlab_paths = validate_matlab_paths(
            requested_matlab_paths,
            self.allowed_roots,
        )
        missing_paths = [path for path in matlab_paths if not path.is_dir()]
        if missing_paths:
            raise InvalidInputError(
                "configured MATLAB paths do not exist as directories: "
                + ", ".join(path.name for path in missing_paths)
            )

        wrapper_path = runtime_directory / WRAPPER_FILENAME
        log_path = runtime_directory / "matlab.log"
        expected: list[Path] = [result_path, log_path]
        for raw in run_spec.expected_artifacts:
            expected.append(self._required_path(raw, "expected_artifacts"))
        unique_paths = {
            str(path): path for path in (run_spec_path, result_path, wrapper_path, log_path)
        }
        if len(unique_paths) != 4:
            raise InvalidInputError(
                "run spec, result, wrapper and log paths must be distinct"
            )

        wrapper_content = self._trusted_wrapper()
        generated_files = (
            PlannedFile(
                path=run_spec_path,
                content=contract_json(run_spec),
                media_type="application/json",
            ),
            PlannedFile(
                path=wrapper_path,
                content=wrapper_content,
                media_type="text/x-matlab",
            ),
        )
        command = (
            self.executable_alias,
            "-sd",
            str(runtime_directory),
            "-logfile",
            str(log_path),
            "-batch",
            WRAPPER_NAME,
        )
        environment = (
            ("PHOTONIC_MATLAB_ENTRY_ROOT", str(self.matlab_entry_root)),
            ("PHOTONIC_RESULT_PATH", str(result_path)),
            ("PHOTONIC_RUN_SPEC", str(run_spec_path)),
        )
        report = self.check()
        return AdapterPlan(
            adapter=self.descriptor.adapter,
            operation=run_spec.operation,
            dry_run=True,
            command=command,
            working_directory=runtime_directory,
            timeout_s=run_spec.timeout_s,
            expected_artifacts=tuple(dict.fromkeys(expected)),
            generated_files=generated_files,
            environment=environment,
            implementation=self.descriptor.implementation,
            availability=report.availability,
            reasons=(
                "dry-run plan only; no MATLAB process was started",
                "batch expression and wrapper function are fixed and do not contain user statements",
                "real execution requires a future version-matched local smoke test",
            ),
            sensitive_command_indexes=(2, 4),
            sensitive_environment_keys=tuple(key for key, _ in environment),
        )
