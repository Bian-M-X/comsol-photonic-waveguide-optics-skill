from __future__ import annotations

import importlib.metadata
import importlib.util
import platform
import shutil
from pathlib import Path

from .models import (
    AvailabilityStatus,
    CapabilityReport,
    ImplementationStatus,
)


def probe_python_package(
    distribution: str,
    *,
    module: str | None = None,
    capability: str | None = None,
    implementation: ImplementationStatus = ImplementationStatus.EXPERIMENTAL,
) -> CapabilityReport:
    available = importlib.util.find_spec(module or distribution.replace("-", "_")) is not None
    version: str | None = None
    reasons: list[str] = []
    if available:
        try:
            version = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            reasons.append("module is import-discoverable but distribution metadata is unavailable")
    else:
        reasons.append("optional Python package is not import-discoverable")
    return CapabilityReport(
        stable_id=f"capability:python:{distribution}",
        name=capability or distribution,
        source="local importlib capability probe",
        status="probed",
        validity="valid",
        capability=capability or distribution,
        implementation=implementation,
        availability=AvailabilityStatus.AVAILABLE if available else AvailabilityStatus.UNAVAILABLE,
        version=version,
        platform=platform.platform(),
        reasons=reasons,
        features={"importable": available},
        probe_method="importlib.util.find_spec and importlib.metadata",
    )


def probe_executable(
    alias: str,
    *,
    capability: str,
    implementation: ImplementationStatus,
) -> CapabilityReport:
    resolved = shutil.which(alias)
    return CapabilityReport(
        stable_id=f"capability:executable:{capability}",
        name=capability,
        source="local executable discovery probe",
        status="probed",
        validity="valid",
        capability=capability,
        implementation=implementation,
        availability=AvailabilityStatus.AVAILABLE if resolved else AvailabilityStatus.UNAVAILABLE,
        platform=platform.platform(),
        reasons=[] if resolved else [f"executable alias is not discoverable: {alias}"],
        features={
            "executable_alias": Path(resolved).name if resolved else alias,
            "path_redacted": bool(resolved),
        },
        probe_method="shutil.which; installation path redacted",
    )


def core_capability_reports() -> list[CapabilityReport]:
    return [
        probe_python_package(
            "numpy",
            capability="numpy-circuit-composition",
            implementation=ImplementationStatus.IMPLEMENTED,
        ),
        probe_python_package(
            "pydantic",
            capability="versioned-data-contracts",
            implementation=ImplementationStatus.IMPLEMENTED,
        ),
        probe_python_package(
            "click",
            capability="photonic-cli",
            implementation=ImplementationStatus.IMPLEMENTED,
        ),
    ]


def optional_capability_reports() -> list[CapabilityReport]:
    """Probe optional packages without importing or executing their backends."""

    package_capabilities = (
        ("gdsfactory", None, "gdsfactory-layout"),
        ("kfactory", None, "kfactory-layout"),
        ("gplugins", None, "gplugins-simulation-bridges"),
        ("sax", None, "sax-circuit-simulation"),
        ("scikit-rf", "skrf", "scikit-rf-network-data"),
        ("meep", None, "meep-full-wave"),
        ("femwell", None, "femwell-finite-element"),
        ("tidy3d", None, "tidy3d-simulation"),
    )
    reports = [
        probe_python_package(
            distribution,
            module=module,
            capability=capability,
            implementation=ImplementationStatus.PLANNED,
        )
        for distribution, module, capability in package_capabilities
    ]
    reports.extend(
        [
            probe_executable(
                "klayout",
                capability="klayout-layout-verification",
                implementation=ImplementationStatus.PLANNED,
            ),
            probe_executable(
                "sim",
                capability="sim-cli",
                implementation=ImplementationStatus.EXPERIMENTAL,
            ),
        ]
    )
    return reports
