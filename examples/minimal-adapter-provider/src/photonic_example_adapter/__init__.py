"""Descriptor-only example for photonic-workflow adapter SPI 1.0."""

from __future__ import annotations

from photonic_workflow.adapters import AdapterRegistration
from photonic_workflow.models import AdapterDescriptor, ImplementationStatus


SUPPORTED_ADAPTER_SPI = "1.0"
SUPPORTED_CONTRACT_SCHEMAS = {
    "CapabilityReport": "1.0",
    "RunSpec": "1.0",
}


def provide_adapters() -> tuple[AdapterRegistration, ...]:
    """Return deterministic metadata without importing an optional backend."""

    descriptor = AdapterDescriptor(
        stable_id="adapter:reviewed-example",
        name="Reviewed example adapter",
        source="photonic-example-adapter 0.1.0",
        adapter="reviewed-example",
        adapter_spi_version=SUPPORTED_ADAPTER_SPI,
        contract_schema_versions=dict(SUPPORTED_CONTRACT_SCHEMAS),
        implementation=ImplementationStatus.PLANNED,
        execution_modes=["descriptor"],
        input_contracts=["RunSpec"],
        output_contracts=["CapabilityReport"],
        capabilities=["bounded descriptor-provider example"],
        limitations=[
            "adapter SPI 1.0 does not expose a third-party execution factory",
            "no backend availability or physics validity is claimed",
        ],
        default_dry_run=True,
        default_concurrency=1,
    )
    return (
        AdapterRegistration(
            descriptor=descriptor,
            factory=None,
            spi_version=SUPPORTED_ADAPTER_SPI,
        ),
    )


__all__ = [
    "SUPPORTED_ADAPTER_SPI",
    "SUPPORTED_CONTRACT_SCHEMAS",
    "provide_adapters",
]
