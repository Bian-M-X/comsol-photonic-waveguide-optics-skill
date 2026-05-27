---
name: photonic-waveguide-optics
description: Use when building, running, debugging, or reporting finite-element optical simulations for integrated photonic waveguides, directional couplers, MZI/aMZI/LT-aMZI interferometers, wavelength sweeps, port-based wave-optics models, and parameter optimization workflows. Compatible with licensed third-party finite-element solver installations without bundling or redistributing proprietary software.
---

# Photonic Waveguide Optics

Use this skill for integrated photonics simulation work: SOI strip/rib waveguides, directional couplers, MMI/splitters, conventional MZI, asymmetric MZI, loop-terminated asymmetric MZI, port-based wave-optics sweeps, and external parameter optimization.

The goal is not just to draw geometry. Build an auditable evidence chain:

1. Extract paper/device topology, dimensions, materials, ports, and target metrics.
2. Validate the simplest physical blocks before assembling the final circuit.
3. Keep geometry, materials, ports, boundaries, mesh, datasets, and postprocessing expressions traceable.
4. Compare sweep results against theory or paper data.
5. Deliver model files, scripts, logs, CSV/TXT data, figures, and a concise report.

## Reference Map

Load only the reference needed for the current task:

- Machine setup, batch runner patterns, and local solver paths: `references/environment-and-runner.md`.
- 2D effective-index waveguide modeling, materials, ports, boundaries, datasets, and mesh: `references/wave-optics-port-models.md`.
- Directional coupler, MZI, aMZI, and LT-aMZI workflows: `references/interferometer-workflows.md`.
- External optimization, parameter sweeps, energy diagnostics, and reporting: `references/optimization-and-reporting.md`.
- Trademark, license, and publication-risk guardrails: `references/legal-and-trademark-notes.md`.

## Default Workflow

1. Read the user request and identify the device class: straight waveguide, coupler, splitter, MZI/aMZI/LT-aMZI, inverse-design region, or report-only task.
2. Extract target metrics: effective index, group index, coupling ratio, FSR, T21/S21, S11, insertion loss, extinction ratio, field map, or fabrication constraints.
3. Build a minimal validation model first: straight waveguide -> coupler/splitter -> conventional interferometer -> final topology.
4. Use a reproducible batch path when possible: generate script/source, run the licensed solver in batch, save model, print metrics, export data.
5. Validate one expression or one model feature at a time before launching long sweeps.
6. Keep low-level solver output and final scientific interpretation separate: raw CSV/TXT first, plots and report second.
7. When presenting results, explicitly label them as full-wave, reduced/analytical, preliminary candidate, or requiring 3D/experimental validation.

## Core Modeling Rules

- For 2D top-view models, state clearly that the vertical waveguide thickness is represented through an effective-index approximation.
- Always separate background/cladding material and waveguide-core material selections.
- Do not use coordinate distance as a substitute for centerline path length in interferometers.
- Smooth bends and S-bends are preferred over sharp corners.
- Numeric ports must sit on exterior boundaries, be perpendicular to straight local waveguide sections, and use boundary mode analysis before the driven frequency-domain step.
- Scattering/radiation boundaries must not include port boundaries.
- Postprocessing expressions should use the component prefix when required, for example `comp1.emw.normE^2` or `abs(comp1.emw.S21)^2`.
- Make sure the dataset is the final frequency/sweep solution, not a boundary-mode dataset, when evaluating S parameters.
- If FSR is correct but peak transmission is low, do not immediately rebuild the topology. First check reflection, port matching, coupler round-trip conditions, boundary loss, bend loss, and mesh.

## MZI/LT-aMZI Acceptance Checklist

For a loop-terminated asymmetric MZI:

- DC1 and DC2 are both 2x2 directional couplers.
- Upper and lower arms are separate waveguide paths with identical width/material and different centerline lengths.
- `DeltaL = L2 - L1` is computed along centerlines.
- The two right-side outputs of DC2 are connected by exactly one continuous loop reflector.
- The final LT-aMZI has no right-side output port.
- Input and output ports are both on the left side near DC1.
- A single-wavelength field plot shows input splitting, two-arm propagation, loop return, and left-side output.
- Wavelength sweep gives periodic fringes, with FSR compared against `lambda^2/(2*n_g*DeltaL)`.

## Reporting Standards

Every deliverable should include:

- model file(s)
- build/run scripts
- logs
- sweep CSV/TXT
- field and spectrum figures
- model-quality audit
- comparison with paper/theory
- known limitations and next steps

Avoid overclaiming:

- A 2D effective-index model is not a final 3D fabrication sign-off.
- A local parameter-sweep winner is not a proven global optimum.
- A field plot is qualitative evidence, not enough by itself.
- Do not claim compatibility, endorsement, or authorization by any commercial solver vendor unless you have it.

For legal and trademark guardrails, read `references/legal-and-trademark-notes.md` before publishing or uploading the project.
