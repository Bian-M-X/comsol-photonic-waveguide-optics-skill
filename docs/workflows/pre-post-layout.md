# Pre- and Post-Layout Workflow

Status: workflow comparison contract

## Purpose

This workflow keeps the logical, extracted, and simulation netlists aligned
while quantifying the effect of routing, physical lengths, transitions, bends,
crossings, and layout-dependent parasitics.

## Pre-layout

1. Freeze G0 design intent and a `LogicalNetlist`.
2. Bind qualified component `ModelCard` revisions.
3. Represent propagation phase/loss and transitions explicitly.
4. Validate the simulation netlist and compose the complete complex response.
5. Store pre-layout results, acceptance, and provenance as an immutable baseline.

## Post-layout

1. Freeze a `LayoutManifest` revision and PDK fingerprint.
2. Extract instances, ports, connections, waveguide lengths, bends, crossings,
   tapers, reference planes, and relevant thermal/electrical occupancy.
3. Compare logical and extracted netlists; resolve or waive every difference.
4. Backannotate a new simulation netlist without mutating the pre-layout one.
5. Re-run the same metrics, band, ports, modes, and sampling.
6. Attribute differences and promote regions where compact separation fails.

## Gates and claim boundary

G3-G4 govern the pre-layout circuit contract and behavior. G5 requires
layout/extracted agreement and declared PDK/DRC/LVS status. Post-layout circuit
results remain circuit evidence. G6 is required for high-risk interactions or
unexplained pre/post discrepancies. G7 evaluates post-layout corners, and G8
links both immutable baselines.

A smaller pre/post metric difference does not prove layout correctness; a
larger difference is not automatically a solver failure.

## Capability and phases

- **Phase A:** three netlist contracts, NumPy circuit baseline, layout manifest,
  comparison/backannotation interfaces, and mock fixtures.
- **Phase B:** local layout import/extraction fixtures and cross-backend checks.
- **Phase C:** real PDK extraction, DRC/LVS, parasitic models, promoted solver
  checks, and tapeout linkage.

Each capability reports whether it can read, extract, compare, backannotate, or
simulate. Missing extraction capability leaves G5 `blocked`.

## No-fake boundary

Do not invent path lengths, layers, parasitics, or netlist matches. Never
overwrite the pre-layout baseline. Mock extraction and DRC results are contract
tests, not post-layout qualification.
