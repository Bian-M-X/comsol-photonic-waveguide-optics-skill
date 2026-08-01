# Layout-First Workflow

Status: workflow contract; backend execution may be unavailable

## Use when

Use this profile when parameterized geometry or an existing GDS/OASIS layout is
the initial artifact. The layout is treated as an input representation to
normalize and compare, not as implicit design intent or proof of performance.

## Flow

1. Freeze a G0 design/device contract before interpreting geometry.
2. Register the layout artifact, backend, top cell, units, layer map, and hash.
3. Normalize hierarchy without changing geometry silently.
4. Recover port metadata, orientations, cross-sections, path lengths, bends,
   crossings, tapers, and transitions.
5. Produce `LayoutManifest` and `ExtractedNetlist`.
6. Compare extracted instances, connections, and external ports with a logical
   netlist; unresolved differences are explicit.
7. Bind qualified component model cards to form a simulation netlist.
8. Run circuit/post-layout analysis and promote high-risk regions.
9. Run authorized DRC/LVS against the declared PDK when available.

Unknown geometry semantics remain unknown. A transition must be explicit when
layers, widths, modes, or reference planes differ.

## Gates and claim boundary

- G0 prevents layout-derived guesses from becoming requirements.
- G2 requires qualified models for extracted components.
- G3 validates the simulation netlist and model conventions.
- G4 is circuit/post-layout evidence only.
- G5 requires port-aware extraction, logical/extracted agreement, and declared
  DRC/LVS status.
- G6-G8 cover promoted full-wave checks, robustness, and the final lineage.

Geometry similarity, XOR agreement, or DRC success is not optical equivalence.
Without a real PDK, report `layout concept`; without model qualification, do not
claim circuit verification.

## Capability and phases

- **Phase A:** layout/netlist contracts, backend descriptors, mock fixtures,
  comparison interfaces, and dry-run plans.
- **Phase B:** local GDS import/export and KLayout/GDSFactory checks on
  non-confidential fixtures.
- **Phase C:** real PDK DRC/LVS, extraction/backannotation, and authorized
  tapeout workflows.

Capability reports distinguish read, normalize, extract, DRC, LVS, and compare;
availability of one feature does not imply the others.

## No-fake boundary

Do not infer ports, layers, PCells, or rules without file evidence. Do not
describe a synthetic extraction, mock DRC result, or backend descriptor as a
completed layout check. Never rewrite a frozen tapeout artifact in place.
