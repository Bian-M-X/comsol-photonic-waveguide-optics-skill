"""Deterministic public-surface snapshots used by maintenance tooling."""

from __future__ import annotations

from enum import Enum
from typing import Any

from .compatibility import (
    ADAPTER_ENTRY_POINT_GROUP,
    CURRENT_ADAPTER_SPI_VERSION,
    DEFAULT_CONTRACT_SCHEMA_VERSION,
)
from .exceptions import ExitCode
from .models import (
    BACKEND_ADOPTION_DEFINITIONS,
    MODEL_CLASSES,
    AcceptanceStatus,
    AvailabilityStatus,
    BackendAdoptionCheck,
    BackendAdoptionPhase,
    BackendAdoptionTarget,
    ExecutionStatus,
    FidelityLevel,
    GateName,
    GateStatus,
    ImplementationStatus,
    RunStatus,
    TimeConvention,
    Validity,
    WorkflowProfile,
)

PUBLIC_ENUMS = (
    AcceptanceStatus,
    AvailabilityStatus,
    BackendAdoptionCheck,
    BackendAdoptionPhase,
    BackendAdoptionTarget,
    ExecutionStatus,
    FidelityLevel,
    GateName,
    GateStatus,
    ImplementationStatus,
    RunStatus,
    TimeConvention,
    Validity,
    WorkflowProfile,
)


def _stable_cli_default(value: Any) -> Any:
    if type(value).__name__ == "Sentinel" and getattr(value, "name", "") == "UNSET":
        return None
    if isinstance(value, Enum):
        return value.value
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_stable_cli_default(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _stable_cli_default(item)
            for key, item in sorted(value.items())
        }
    return f"<{type(value).__name__}>"


def _cli_surface() -> dict[str, Any]:
    import click

    from .cli import cli

    surface: dict[str, Any] = {}
    pending: list[tuple[str, click.Command]] = [("photonic", cli)]
    while pending:
        path, command = pending.pop()
        parameters: list[dict[str, Any]] = []
        for parameter in command.params:
            parameter_type = parameter.type
            item: dict[str, Any] = {
                "name": parameter.name,
                "kind": type(parameter).__name__,
                "type": getattr(parameter_type, "name", type(parameter_type).__name__),
                "required": parameter.required,
                "nargs": parameter.nargs,
                "default": _stable_cli_default(parameter.default),
            }
            choices = getattr(parameter_type, "choices", None)
            if choices is not None:
                item["choices"] = [str(choice) for choice in choices]
            options = getattr(parameter, "opts", None)
            if options is not None:
                item["options"] = list(options)
                item["secondary_options"] = list(
                    getattr(parameter, "secondary_opts", ())
                )
                item["multiple"] = parameter.multiple
            parameters.append(item)
        surface[path] = {
            "kind": type(command).__name__,
            "parameters": parameters,
        }
        if isinstance(command, click.Group):
            pending.extend(
                (f"{path} {name}", child)
                for name, child in command.commands.items()
            )
    return {path: surface[path] for path in sorted(surface)}


def contract_surface_snapshot() -> dict[str, Any]:
    """Return a dependency-stable snapshot of persisted contract structure."""

    from .adapters import default_adapter_registry
    from .mcp.server import PhotonicMcpServer, default_skill_root

    contracts: dict[str, Any] = {}
    for model_class in sorted(MODEL_CLASSES, key=lambda item: item.contract_type):
        fields = model_class.model_fields
        contracts[model_class.contract_type] = {
            "model": model_class.__name__,
            "current_schema_version": model_class.current_schema_version,
            "schema_version_default": fields["schema_version"].default,
            "fields": sorted(fields),
            "required_fields": sorted(
                name for name, field in fields.items() if field.is_required()
            ),
            "extra_policy": model_class.model_config.get("extra"),
        }
    adapter_registry = default_adapter_registry()
    from . import adapters as public_adapters
    from .models.migration_catalog import PRODUCTION_MIGRATIONS

    mcp_server = PhotonicMcpServer(
        default_skill_root(),
        read_roots=[],
        write_roots=[],
    )
    return {
        "snapshot_schema_version": "1.2",
        "default_contract_schema_version": DEFAULT_CONTRACT_SCHEMA_VERSION,
        "production_migrations": [
            {
                "migration_id": migration.migration_id,
                "contract_type": migration.contract_type,
                "from_version": migration.from_version,
                "to_version": migration.to_version,
            }
            for migration in PRODUCTION_MIGRATIONS
        ],
        "contracts": contracts,
        "enums": {
            enum_class.__name__: [item.value for item in enum_class]
            for enum_class in PUBLIC_ENUMS
        },
        "backend_adoption_gates": {
            target.value: {
                "phase": definition.phase.value,
                "required_checks": [
                    check.value for check in definition.required_checks
                ],
            }
            for target, definition in BACKEND_ADOPTION_DEFINITIONS.items()
        },
        "exit_codes": {item.name: int(item) for item in ExitCode},
        "adapters": {
            descriptor.adapter: {
                "implementation": descriptor.implementation.value,
                "adapter_spi_version": descriptor.adapter_spi_version,
                "contract_schema_versions": descriptor.contract_schema_versions,
                "commercial": descriptor.commercial,
                "execution_modes": descriptor.execution_modes,
                "input_contracts": descriptor.input_contracts,
                "output_contracts": descriptor.output_contracts,
                "has_factory": adapter_registry.has_factory(descriptor.adapter),
            }
            for descriptor in adapter_registry.descriptors()
        },
        "adapter_provider_spi": {
            "version": CURRENT_ADAPTER_SPI_VERSION,
            "entry_point_group": ADAPTER_ENTRY_POINT_GROUP,
            "descriptor_only": True,
            "public_exports": sorted(public_adapters.__all__),
        },
        "mcp": {
            "resources": [
                resource["uri"] for resource in mcp_server.resource_list()
            ],
            "tools": {
                tool["name"]: tool["inputSchema"]
                for tool in mcp_server.tool_list()
            },
        },
        "cli": _cli_surface(),
    }


__all__ = ["PUBLIC_ENUMS", "contract_surface_snapshot"]
