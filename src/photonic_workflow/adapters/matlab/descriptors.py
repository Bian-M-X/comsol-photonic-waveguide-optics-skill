from __future__ import annotations

from photonic_workflow.models.contracts import (
    AdapterDescriptor,
    ImplementationStatus,
    current_contract_schema_versions,
)


def _descriptor(
    adapter: str,
    name: str,
    *,
    implementation: ImplementationStatus,
    execution_modes: list[str],
    input_contracts: list[str],
    output_contracts: list[str],
    capabilities: list[str],
    limitations: list[str],
    optional: bool = True,
) -> AdapterDescriptor:
    return AdapterDescriptor(
        stable_id=f"adapter:{adapter}",
        name=name,
        source="photonic_workflow Phase A adapter registry",
        status="phase-a",
        adapter=adapter,
        implementation=implementation,
        commercial=True,
        optional=optional,
        version_sensitive=True,
        execution_modes=execution_modes,
        input_contracts=input_contracts,
        output_contracts=output_contracts,
        contract_schema_versions=current_contract_schema_versions(
            [*input_contracts, *output_contracts]
        ),
        capabilities=capabilities,
        limitations=limitations,
        default_dry_run=True,
        default_concurrency=1,
    )


MATLAB_RUNTIME_DESCRIPTOR = _descriptor(
    "matlab-runtime",
    "MATLAB batch runtime",
    implementation=ImplementationStatus.IMPLEMENTED,
    execution_modes=["batch-plan"],
    input_contracts=["MatlabRunSpec"],
    output_contracts=["MatlabEnvironmentReport", "MatlabResultManifest"],
    capabilities=[
        "executable discovery",
        "structured environment inventory parsing",
        "fixed-wrapper batch planning",
    ],
    limitations=[
        "Phase A implements check and dry-run planning only",
        "real MATLAB batch execution and release parity remain unverified",
        "tool execution success is not physics acceptance",
    ],
    optional=False,
)

MATLAB_ENGINE_DESCRIPTOR = _descriptor(
    "matlab-engine",
    "MATLAB Engine API probe",
    implementation=ImplementationStatus.EXPERIMENTAL,
    execution_modes=["probe-only"],
    input_contracts=[],
    output_contracts=["CapabilityReport"],
    capabilities=[
        "module/distribution discovery",
        "optional shared-session count without connecting",
    ],
    limitations=[
        "does not start or connect to a MATLAB session",
        "Python/MATLAB release compatibility is not inferred from package presence",
        "no arbitrary function invocation",
    ],
)

MATLAB_LAYOUT_DESCRIPTOR = _descriptor(
    "matlab-layout",
    "MATLAB legacy GDS layout bridge",
    implementation=ImplementationStatus.EXPERIMENTAL,
    execution_modes=["descriptor", "capability-probe-contract", "dry-run-plan"],
    input_contracts=["LayoutManifest", "PCellContract", "MatlabRunSpec"],
    output_contracts=["LayoutManifest", "ExtractedNetlist", "MatlabResultManifest"],
    capabilities=[
        "legacy MatlabGDSPhotonicsToolbox/GDSII Toolbox handoff contract",
        "fixed layout entry contract",
        "GDS and sidecar artifact expectations",
    ],
    limitations=[
        "no Phase-A GDS generation is executed",
        "unknown MEX binaries are never compiled or run",
        "MATLAB layout output is not PDK/DRC/LVS or tapeout signoff",
    ],
)

MATLAB_FDFD_DESCRIPTOR = _descriptor(
    "matlab-fdfd",
    "MATLAB photonic FDFD bridge",
    implementation=ImplementationStatus.EXPERIMENTAL,
    execution_modes=["descriptor", "capability-probe-contract", "dry-run-plan"],
    input_contracts=["DeviceContract", "MatlabRunSpec"],
    output_contracts=["ModelCard", "SParameterDataset", "MatlabResultManifest"],
    capabilities=[
        "2D and variational 2.5D fidelity labels",
        "field/S-parameter artifact contract",
        "mesh-convergence evidence contract",
    ],
    limitations=[
        "no Phase-A FDFD backend is executed",
        "MATLAB FDFD is not full-device 3D evidence",
        "boundary conditions and GDS semantics require local validation",
    ],
)

MATLAB_COMSOL_DESCRIPTOR = _descriptor(
    "matlab-comsol-livelink",
    "MATLAB LiveLink for COMSOL bridge",
    implementation=ImplementationStatus.UNVERIFIED,
    execution_modes=["descriptor", "probe-contract", "dry-run-plan"],
    input_contracts=["MultiPhysicsModelCard", "MatlabRunSpec"],
    output_contracts=["SParameterDataset", "MatlabResultManifest"],
    capabilities=["version-sensitive LiveLink workflow contract", "direct-Java parity contract"],
    limitations=[
        "requires separate MATLAB, COMSOL, LiveLink and license availability",
        "native COMSOL Java batch remains the trusted default",
        "no execution before local parity and failure-mode tests pass",
    ],
)

MATLAB_LUMERICAL_DESCRIPTOR = _descriptor(
    "matlab-lumerical",
    "MATLAB bridge for Ansys Lumerical products",
    implementation=ImplementationStatus.UNVERIFIED,
    execution_modes=["descriptor", "probe-contract", "dry-run-plan"],
    input_contracts=["ModelCard", "MatlabRunSpec"],
    output_contracts=["SParameterDataset", "MatlabResultManifest"],
    capabilities=["FDTD/MODE/DEVICE/INTERCONNECT handoff contract", "artifact conversion contract"],
    limitations=[
        "requires a locally configured, version-matched Lumerical MATLAB API",
        "no arbitrary Lumerical script strings are accepted",
        "no Phase-A execution or result parity evidence",
    ],
)

MATLAB_INSTRUMENT_DESCRIPTOR = _descriptor(
    "matlab-instrument",
    "MATLAB Instrument Control bridge",
    implementation=ImplementationStatus.PLANNED,
    execution_modes=["descriptor", "probe-contract", "dry-run-plan"],
    input_contracts=["TestPlan", "MatlabRunSpec"],
    output_contracts=["MeasurementManifest", "MatlabResultManifest"],
    capabilities=["instrument capability/safety contract", "immutable raw-data artifact contract"],
    limitations=[
        "no arbitrary SCPI strings are accepted",
        "real hardware requires explicit identity, safety limits and authorization",
        "Phase A performs no instrument I/O",
    ],
)

MATLAB_SIMULINK_DESCRIPTOR = _descriptor(
    "matlab-simulink",
    "MATLAB Simulink system-model bridge",
    implementation=ImplementationStatus.PLANNED,
    execution_modes=["descriptor", "probe-contract", "dry-run-plan"],
    input_contracts=["ModelCard", "MatlabRunSpec"],
    output_contracts=["ModelCard", "MatlabResultManifest"],
    capabilities=["fixed-model entry contract", "input/output port contract"],
    limitations=[
        "no Phase-A model execution or cosimulation",
        "COMSOL/Simulink cosimulation requires real models and licenses",
        "system-level evidence is distinct from photonic full-wave evidence",
    ],
)


MATLAB_ADAPTER_DESCRIPTORS: tuple[AdapterDescriptor, ...] = (
    MATLAB_RUNTIME_DESCRIPTOR,
    MATLAB_ENGINE_DESCRIPTOR,
    MATLAB_LAYOUT_DESCRIPTOR,
    MATLAB_FDFD_DESCRIPTOR,
    MATLAB_COMSOL_DESCRIPTOR,
    MATLAB_LUMERICAL_DESCRIPTOR,
    MATLAB_INSTRUMENT_DESCRIPTOR,
    MATLAB_SIMULINK_DESCRIPTOR,
)

MATLAB_DESCRIPTOR_BY_NAME = {
    descriptor.adapter: descriptor for descriptor in MATLAB_ADAPTER_DESCRIPTORS
}
