# Verification Gates

Use these gates to decide whether work can advance to a more expensive model or stronger claim. Record each gate as `pass`, `fail`, `blocked`, or `not_applicable` with artifact paths and numeric evidence.

## G0 Device Contract

Require:

- device family and topology;
- external ports and input conditions;
- wavelength/frequency band;
- process stack, materials, polarization, and modes;
- target metrics and tolerances;
- claim level: exploratory, reduced-model, 2D EIM, 3D, or experiment-correlated.

Do not build a full device while these fields are ambiguous.

## G1 Port and Straight-Waveguide Baseline

Require:

- solved input/output modes;
- stable port orientation and numbering;
- exact disjoint and complete exterior-boundary partition audit;
- `S21`, `S11`, phase, and mode profile;
- one declared power normalization, reference-plane convention, and complex
  port-mode phase basis;
- all claimed complex S-matrix columns from one model/source sweep or an
  independently verified gauge-alignment transform;
- per-input modal, signed exterior-flux, and material-absorption accounting;
- acceptable boundary and mesh sensitivity;
- driven-field physical audit from the final dataset, with geometry, ports,
  scale, and full exterior visible;
- reference-plane locations recorded.

This gate establishes the normalization inherited by all component models.

## G2 Component Qualification

For every reusable block require:

- complete complex multiport S matrix over the declared band;
- correct mode label for every port;
- passivity check for passive components;
- reciprocity check when physically expected;
- per-input energy budget;
- geometry/process parameters and model level;
- mesh, boundary, wavelength-step, and port-reference checks;
- limits outside which the model must not be used.

Do not qualify a component from a field plot or one transmission curve alone.
Also do not qualify a component from attractive S values when the field plot
has an unexplained physical red flag. Visual plausibility is necessary
diagnostic evidence for field-based work but is never sufficient by itself.

## G3 Assembly Contract

Require:

- all instances reference known components;
- each instance port is connected exactly once or exposed externally;
- no mode mismatch at a direct connection;
- one wavelength grid and one S-parameter convention;
- routing phase/loss represented by explicit components;
- manifest validation passes.

Use `python scripts/photonic_assembly.py validate <manifest>`.

## G4 Circuit-Level Behavior

Require:

- external S matrix generated over the target band;
- passive-network singular value within tolerance;
- expected reciprocity/nonreciprocity behavior;
- correct qualitative transfer function;
- energy accounting per independent input;
- wavelength resolution sufficient for narrow features;
- sensitivity or corner screen for high-impact parameters.

When a COMSOL source sweep supplies the matrix, require the source-conditioned
column mapping, phase basis, and evidence checks in
`frequency-domain-source-sweeps.md`.

Label this evidence `circuit-level verified`, not `full-wave verified`.

## G5 Layout and Connectivity

Require:

- port-aware placement and routing;
- no unintended disconnected or multiply connected ports;
- extracted connectivity agrees with the intended manifest;
- minimum bend radius, spacing, cross-section, and layer transitions checked;
- DRC passes against the selected PDK or declared surrogate rules;
- layout artifacts and PDK/version are recorded.

Label a design without a real PDK as `layout concept`, not `tapeout ready`.

## G6 Promoted Subassembly

Require at least one higher-fidelity check for each critical interaction:

- same external reference planes and input modes as the circuit model;
- same wavelength range and comparable sampling;
- complex S-matrix or metric comparison;
- declared error tolerance;
- root-cause analysis for disagreement;
- compact-model update when necessary.

## G7 Robustness and Optimization

Require:

- objective and constraints recorded before optimization;
- baseline preserved;
- nominal and corner results separated;
- mesh/solver noise smaller than claimed improvement;
- winner re-evaluated at the highest validated fidelity;
- local-search results not called globally optimal.

## G8 Final Evidence Package

Require:

- source or model-generation scripts;
- manifests and component contracts;
- solver logs and exported tables where shareable;
- plots generated from stored data;
- gate ledger;
- comparison with theory, literature, or measurement;
- limitations and exact next step;
- public-release audit if publishing.

## Minimum Gate Ledger

```text
gate,status,evidence,metric_or_reason,next_action
G0,pass,requirements/device-contract.md,band=1500-1600 nm,build baseline
G1,pass,verification/straight-waveguide.json,max_R11=...,qualify components
G2,blocked,components/dc/verification.md,mesh convergence missing,refine gap mesh
```

Never convert missing evidence into a pass by inference.
