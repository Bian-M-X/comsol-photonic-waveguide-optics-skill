from __future__ import annotations

from collections import Counter
from typing import Any

from photonic_workflow.exceptions import InvalidInputError
from photonic_workflow.models import BaseNetlist, ExtractedNetlist, LogicalNetlist, SimulationNetlist
from photonic_workflow.models.io import revalidate_internal


def _endpoint_parts(endpoint: str) -> tuple[str, str]:
    if not isinstance(endpoint, str) or endpoint.count(":") != 1:
        raise InvalidInputError(f"netlist endpoint must be 'instance:port': {endpoint!r}")
    instance, port = endpoint.split(":", 1)
    if not instance or not port:
        raise InvalidInputError(f"netlist endpoint must be 'instance:port': {endpoint!r}")
    return instance, port


def validate_netlist(netlist: BaseNetlist) -> dict[str, Any]:
    instance_names = [instance.name for instance in netlist.instances]
    duplicate_instances = sorted(name for name, count in Counter(instance_names).items() if count > 1)
    errors: list[str] = []
    if duplicate_instances:
        errors.append("duplicate instances: " + ", ".join(duplicate_instances))
    known = set(instance_names)
    occupied: dict[str, str] = {}
    for connection in netlist.connections:
        for endpoint in (connection.source_endpoint, connection.target_endpoint):
            try:
                instance, _ = _endpoint_parts(endpoint)
            except InvalidInputError as exc:
                errors.append(str(exc))
                continue
            if instance not in known:
                errors.append(f"unknown instance in endpoint: {endpoint}")
            if endpoint in occupied:
                errors.append(f"endpoint reused: {endpoint}")
            occupied[endpoint] = connection.stable_id
        if connection.source_endpoint == connection.target_endpoint:
            errors.append(f"self-connection: {connection.source_endpoint}")
    for external_name, endpoint in netlist.external_ports.items():
        try:
            instance, _ = _endpoint_parts(endpoint)
        except InvalidInputError as exc:
            errors.append(str(exc))
            continue
        if instance not in known:
            errors.append(f"unknown external endpoint: {external_name}={endpoint}")
        if endpoint in occupied:
            errors.append(f"external endpoint is internally occupied: {endpoint}")
        occupied[endpoint] = f"external:{external_name}"
    return {
        "valid": not errors,
        "errors": errors,
        "instance_count": len(netlist.instances),
        "connection_count": len(netlist.connections),
        "external_port_count": len(netlist.external_ports),
    }


def _connection_key(source: str, target: str) -> tuple[str, str]:
    return tuple(sorted((source, target)))


def compare_netlists(
    intended: LogicalNetlist | SimulationNetlist,
    extracted: ExtractedNetlist,
) -> dict[str, Any]:
    intended_instances = {instance.name: instance.component_id for instance in intended.instances}
    extracted_instances = {instance.name: instance.component_id for instance in extracted.instances}
    intended_connections = {
        _connection_key(item.source_endpoint, item.target_endpoint) for item in intended.connections
    }
    extracted_connections = {
        _connection_key(item.source_endpoint, item.target_endpoint) for item in extracted.connections
    }
    mismatched_types = {
        name: {
            "intended": intended_instances[name],
            "extracted": extracted_instances[name],
        }
        for name in intended_instances.keys() & extracted_instances.keys()
        if intended_instances[name] != extracted_instances[name]
    }
    report = {
        "missing_instances": sorted(intended_instances.keys() - extracted_instances.keys()),
        "unexpected_instances": sorted(extracted_instances.keys() - intended_instances.keys()),
        "mismatched_component_types": mismatched_types,
        "missing_connections": sorted(intended_connections - extracted_connections),
        "unexpected_connections": sorted(extracted_connections - intended_connections),
        "external_ports_match": intended.external_ports == extracted.external_ports,
        "intended_external_ports": intended.external_ports,
        "extracted_external_ports": extracted.external_ports,
    }
    report["equivalent"] = not any(
        (
            report["missing_instances"],
            report["unexpected_instances"],
            report["mismatched_component_types"],
            report["missing_connections"],
            report["unexpected_connections"],
        )
    ) and report["external_ports_match"]
    return report


def backannotate_waveguide_lengths(
    netlist: SimulationNetlist,
    lengths_um: dict[str, float],
) -> SimulationNetlist:
    unknown = sorted(set(lengths_um) - {instance.name for instance in netlist.instances})
    if unknown:
        raise InvalidInputError("cannot backannotate unknown instances: " + ", ".join(unknown))
    payload = netlist.model_dump()
    for instance in payload["instances"]:
        if instance["name"] in lengths_um:
            length = lengths_um[instance["name"]]
            if length <= 0:
                raise InvalidInputError("backannotated waveguide lengths must be positive")
            instance["settings"]["extracted_length_um"] = length
    payload["revision"] = str(int(netlist.revision) + 1) if netlist.revision.isdigit() else netlist.revision
    payload["provenance"] = [*netlist.provenance, "layout-length-backannotation"]
    return revalidate_internal(SimulationNetlist, payload)
