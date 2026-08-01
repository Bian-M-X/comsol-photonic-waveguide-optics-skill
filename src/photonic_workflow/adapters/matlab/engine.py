from __future__ import annotations

import importlib
import importlib.metadata
import importlib.util
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from importlib.machinery import ModuleSpec
from typing import Any

from photonic_workflow.exceptions import UnavailableCapabilityError
from photonic_workflow.models.contracts import (
    AvailabilityStatus,
    CapabilityReport,
    ImplementationStatus,
    RunSpec,
)

from ..base import Adapter, AdapterPlan
from .descriptors import MATLAB_ENGINE_DESCRIPTOR

SpecFinder = Callable[[str], ModuleSpec | None]
DistributionVersionGetter = Callable[[str], str]
SessionFinder = Callable[[], Sequence[str]]


@dataclass(frozen=True)
class EngineProbeResult:
    importable: bool
    distribution_version: str | None
    compatible: bool | None
    shared_session_count: int | None
    reasons: tuple[str, ...]


def _distribution_version(
    version_getter: DistributionVersionGetter,
) -> str | None:
    for distribution in ("matlabengine", "matlab-engine-for-python"):
        try:
            return version_getter(distribution)
        except importlib.metadata.PackageNotFoundError:
            continue
    return None


def probe_matlab_engine(
    *,
    matlab_release: str | None = None,
    inspect_shared_sessions: bool = False,
    spec_finder: SpecFinder = importlib.util.find_spec,
    version_getter: DistributionVersionGetter = importlib.metadata.version,
    session_finder: SessionFinder | None = None,
) -> EngineProbeResult:
    """Probe Engine packaging without starting or connecting to MATLAB."""

    reasons: list[str] = []
    try:
        matlab_spec = spec_finder("matlab")
        engine_spec = spec_finder("matlab.engine") if matlab_spec is not None else None
    except (ImportError, ModuleNotFoundError, ValueError) as exc:
        matlab_spec = None
        engine_spec = None
        reasons.append(f"MATLAB Engine module discovery failed: {type(exc).__name__}")

    importable = matlab_spec is not None and engine_spec is not None
    distribution_version = _distribution_version(version_getter) if importable else None
    if not importable:
        reasons.append("MATLAB Engine for Python is not importable")
        return EngineProbeResult(
            importable=False,
            distribution_version=None,
            compatible=False,
            shared_session_count=None,
            reasons=tuple(reasons),
        )

    compatible: bool | None = None
    if matlab_release:
        reasons.append(
            "Engine package presence does not prove compatibility with "
            f"MATLAB {matlab_release}; a version-matched local smoke test is required"
        )
    else:
        reasons.append("MATLAB release is unknown, so Engine compatibility is unverified")

    shared_session_count: int | None = None
    if inspect_shared_sessions:
        try:
            finder = session_finder
            if finder is None:
                engine_module: Any = importlib.import_module("matlab.engine")
                finder = engine_module.find_matlab
            shared_session_count = len(tuple(finder()))
        except Exception as exc:
            reasons.append(f"shared-session enumeration failed: {type(exc).__name__}")
    else:
        reasons.append("shared-session enumeration was not requested")

    return EngineProbeResult(
        importable=True,
        distribution_version=distribution_version,
        compatible=compatible,
        shared_session_count=shared_session_count,
        reasons=tuple(reasons),
    )


class MatlabEngineAdapter(Adapter):
    descriptor = MATLAB_ENGINE_DESCRIPTOR

    def __init__(
        self,
        *,
        matlab_release: str | None = None,
        inspect_shared_sessions: bool = False,
        spec_finder: SpecFinder = importlib.util.find_spec,
        version_getter: DistributionVersionGetter = importlib.metadata.version,
        session_finder: SessionFinder | None = None,
    ) -> None:
        self.matlab_release = matlab_release
        self.inspect_shared_sessions = inspect_shared_sessions
        self.spec_finder = spec_finder
        self.version_getter = version_getter
        self.session_finder = session_finder

    def probe(self) -> EngineProbeResult:
        return probe_matlab_engine(
            matlab_release=self.matlab_release,
            inspect_shared_sessions=self.inspect_shared_sessions,
            spec_finder=self.spec_finder,
            version_getter=self.version_getter,
            session_finder=self.session_finder,
        )

    def check(self) -> CapabilityReport:
        result = self.probe()
        availability = (
            AvailabilityStatus.UNAVAILABLE
            if not result.importable
            else AvailabilityStatus.UNVERIFIED
        )
        return CapabilityReport(
            stable_id="capability:matlab-engine",
            name="MATLAB Engine API",
            source="local Python module probe; no MATLAB session was started",
            status=availability.value,
            validity="unknown",
            capability="matlab-engine",
            implementation=ImplementationStatus.EXPERIMENTAL,
            availability=availability,
            version=result.distribution_version,
            reasons=list(result.reasons),
            features={
                "engine_importable": result.importable,
                "engine_compatible": result.compatible,
                "shared_session_count": result.shared_session_count,
                "session_started": False,
                "session_connected": False,
            },
            probe_method="importlib discovery with optional find_matlab enumeration",
        )

    def plan(self, run_spec: RunSpec) -> AdapterPlan:
        raise UnavailableCapabilityError(
            "MATLAB Engine is probe-only in Phase A; no Engine execution plan is available"
        )
