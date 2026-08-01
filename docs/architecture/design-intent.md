# Design Intent

Status: Phase A architecture contract

## Purpose

Design intent is the durable source of what the PIC is meant to do. Geometry,
solver files, layout databases, and measurement scripts are derived views; none
is allowed to become the only copy of the intent.

## Contract graph

`DesignIntent` records the problem, topology, external ports, band, modes,
process stack, metrics, tolerances, and intended claim. It is refined by:

- `DeviceContract` for device family, materials, ports, and acceptance
  criteria;
- `DesignVariant` for one parameter/corner revision that the workflow treats as
  a snapshot once evidence depends on it;
- `LogicalNetlist` for intended instances and connections;
- `SimulationNetlist` for selected model bindings;
- `ExtractedNetlist` for connectivity recovered from layout;
- `LayoutManifest`, `ModelCard`, `TestPlan`, and `MeasurementManifest` for
  downstream representations.

Stable IDs and revisions link these objects. A derived artifact links its
parent intent and variant through a dedicated ID where the contract provides
one, otherwise through provenance. It does not overwrite the parent. Phase A
defines this revision policy; enforcement requires the Run/provenance service
and is not implied by Pydantic validation alone.

## Input discipline

Physical decisions are explicit contract fields. Geometry, material, band,
mode, topology, process stack, boundary conditions, thresholds, optimization
variables, and instrument safety limits must not be inherited implicitly from
global configuration. Runtime defaults such as timeout, workspace, logging,
worker count, and dry-run may be defaulted only when the chosen values are
recorded.

File-derived facts such as GDS layers, model tags, PCell ports, mesh size, or
instrument identity require a real-file or real-device probe and provenance.

## Gates and claim boundary

G0 passes only when the design/device contracts identify ports, modes, band,
stack, metrics, tolerances, and intended claim. Later gates compare their
artifacts back to the same stable IDs:

- G3 checks simulation-netlist and circuit consistency;
- G5 checks logical versus extracted connectivity;
- G6-G7 record promotion and robustness against the same intent;
- G8 packages the lineage and unresolved limitations.

A diagram, GDS file, model file, or passing solver run cannot repair an
ambiguous G0 contract by inference. Missing intent keeps G0 `blocked`.

## Capability and phases

- **Phase A:** versioned intent, device, variant, and netlist contracts plus
  mock fixtures and comparison interfaces.
- **Phase B:** locally validated import/export round trips for MATLAB and
  selected layout or numerical tools.
- **Phase C:** PDK-specific schematic/layout extraction, co-simulation, and
  measurement-driven backannotation.

Capability reports state whether a representation can be read, generated, or
compared. They do not state that a particular design is correct.

## No-fake boundary

Unknown physical inputs remain unknown. The runtime must not invent a material,
mode, distribution, tolerance, PDK rule, or instrument limit. A mock intent is
valid only for contract tests and cannot be labeled foundry, full-wave, robust,
or measurement verified.
