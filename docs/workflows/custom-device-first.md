# Custom-Device-First Workflow

Status: primary Phase A solver-independent workflow

## Use when

Use this profile for a new waveguide, bend, taper, coupler, interferometer,
grating, sensor, modulator, inverse-designed region, or other device that must
be qualified before it becomes a reusable circuit component.

## Flow

1. Freeze topology, ports, band, stack, modes, metrics, tolerances, corners,
   and intended claim.
2. Establish a straight-waveguide and port baseline at the lowest sufficient
   fidelity.
3. Build the smallest model that captures the device physics.
4. Export a complete complex multiport S dataset with common normalization,
   phase/time convention, reference planes, and stable port order.
5. Validate passivity, reciprocity where expected, per-input energy closure,
   mesh/boundary/sampling sensitivity, and validity envelope.
6. Release a `ComponentContract` and `ModelCard`.
7. Compose components into a circuit using the legacy-compatible assembly
   contract or a simulation netlist.
8. Generate or import layout, extract connectivity, and promote critical
   interactions.
9. Evaluate robustness and package the evidence.

COMSOL source columns must come from one model/common port basis or a separately
verified gauge-alignment transform.

## Gates and claim boundary

G0 freezes the question; G1 qualifies the straight-waveguide/port basis; G2
qualifies the component; G3-G4 validate composition and circuit behavior; G5
checks layout/connectivity; G6 promotes critical full-wave subassemblies; G7
tests robustness; G8 packages evidence.

An analytic, reduced, modal, MATLAB FDFD, 2D EIM, circuit, or single-mesh result
is labeled at its actual fidelity. It is never relabeled as converged 3D or
experimental evidence.

## Capability and phases

- **Phase A:** contracts, NumPy S-parameter validation/composition, legacy CSV
  and assembly compatibility, COMSOL/MATLAB dry-run plans, and gate records.
- **Phase B:** local MATLAB fixtures and selected cross-tool numerical parity.
- **Phase C:** authorized solver execution, PDK layout/signoff, multiphysics,
  optimization, packaging, and measurement correlation.

The selected adapter must report implementation and local availability before
execution. Missing physics inputs cannot be replaced by runtime defaults.

## No-fake boundary

Do not qualify a component from one transmission trace or field plot. Do not
fill undefined source-sweep entries with zero, invent convergence, or call the
best sampled design globally optimal. Mock components remain test fixtures.
