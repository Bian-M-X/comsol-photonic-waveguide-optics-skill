---
name: photonic-waveguide-optics
description: Design, build, run, debug, optimize, hierarchically compose, and report integrated-photonic device simulations. Use for waveguides, bends, tapers, splitters, directional/MMI couplers, rings, gratings, MZI/aMZI/LT-aMZI, sensors, modulators, inverse-designed regions, COMSOL Wave Optics Java/batch workflows, 2D effective-index and 3D validation, S-parameter compact models, port-aware circuit/netlist composition, layout-readiness checks, parameter sweeps, robustness studies, and evidence-backed handoffs.
---

# Photonic Waveguide Optics

Build an auditable path from device requirements to validated components, composed circuits, selected full-wave checks, optimization, and reporting. Treat geometry, circuit behavior, layout connectivity, and fabrication readiness as separate evidence layers.

## Start Here

1. Read the user-specified project, paper, handoff, model, or repository first.
2. Classify the task as `design`, `reproduce`, `debug`, `optimize`, `compose`, `validate`, or `report`.
3. Declare the target device, external ports, band, polarization/modes, process stack, metrics, tolerances, and intended claim level.
4. Choose the lowest-cost model that can answer the question.
5. Use the verification gates below before advancing to a larger or more expensive model.

Do not start a complete complex-device solve before the straight-waveguide/port baseline and critical building blocks are qualified.

## Route to the Right Reference

Read only the modules needed for the next action:

| Task | Read |
|---|---|
| Solver paths, Java compilation, batch execution | `references/environment-and-runner.md` |
| Materials, ports, boundary-mode studies, mesh, datasets | `references/wave-optics-port-models.md` |
| Waveguides, bends, tapers, couplers, rings, gratings, sensors | `references/device-family-workflows.md` |
| MZI, aMZI, LT-aMZI, coupler calibration, FSR | `references/interferometer-workflows.md` |
| Circular/Euler bend geometry and path-length control | `references/smooth-bend-geometry.md` |
| Multi-device composition, compact models, layout/netlists | `references/hierarchical-device-workflow.md` |
| Stage acceptance and claim boundaries | `references/verification-gates.md` |
| Sweeps, objectives, inverse design, 2D-to-3D, reports | `references/optimization-and-reporting.md` |
| Quantum photonic circuits and mesh context | `references/quantum-photonic-knowledge-base.md` |
| Project structure, artifacts, git, handoffs | `references/project-structure-and-git.md` |
| Batch vs interactive server vs MCP wrapper | `references/comsol-mcp-evaluation.md` |
| Current source links and refresh targets | `references/source-notes.md` |
| Public release, licensing, trademarks, local-data safety | `references/legal-and-trademark-notes.md` |
| Optional delegation, independent audit, and solver concurrency | `references/subagent-orchestration.md` |

## Select the Modeling Level

| Question | Default model |
|---|---|
| topology, phase trend, FSR, coarse screening | analytic/reduced or 2D EIM |
| individual passive block with in-plane confinement | 2D EIM full-wave, then targeted 3D |
| vertical confinement, etch depth, grating/free-space coupling | 3D full-wave |
| many calibrated blocks connected as a circuit | complex multiport S-parameter network |
| placement, routing, connectivity, PDK rules | port-aware layout and extracted netlist |
| final performance under process/temperature variation | circuit corners plus promoted full-wave checks |

Use a complete full-device 3D solve only when interaction physics invalidates block separation, the device is small enough to converge, or the claim explicitly requires whole-device fields.

## Core Workflow

### 1. Freeze the device contract

Record:

- topology and device family;
- input/output ports and excitations;
- wavelength/frequency band and sampling needs;
- materials, cross-section, polarization, supported modes, and process stack;
- metrics, tolerances, corner variables, and claim level;
- paper-faithful baseline separately from engineering optimization.

### 2. Establish the baseline

Build a straight waveguide with the same cross-section and port convention. Verify mode shape, `S21`, `S11`, phase, mesh, boundary, and reference planes. For numeric ports, use one Boundary Mode Analysis step per port before the driven frequency/wavelength study.

Exclude port boundaries from scattering/radiation selections. Use stable numeric port names when full S-matrix sweeps or Touchstone export are required.

### 3. Qualify building blocks

Build the smallest independent model for each bend, taper, splitter, coupler, ring, grating, transition, phase section, or inverse-design region. Evaluate the device-family metrics from `references/device-family-workflows.md`.

For reusable circuit models, export the complete complex S matrix across the declared band. Record port order, modes, normalization, time/phase convention, reference planes, model level, geometry/process parameters, and validity range.

### 4. Compose complex devices hierarchically

Prefer this scalable route:

```text
validated component geometry
  -> calibrated complex multiport S data
  -> validated assembly manifest/netlist
  -> circuit-level spectrum and sensitivity
  -> port-aware layout and extracted connectivity
  -> full-wave promotion of critical subassemblies
  -> final evidence package
```

Use `scripts/photonic_assembly.py` to validate a manifest and compose an external S matrix. Represent waveguide phase, propagation loss, bends, and transitions as explicit components; an ideal manifest connection has zero length and no loss.

Use geometry parts for reusable COMSOL geometry, but explicitly rebind materials, physics, mesh, and named selections after assembly. Geometry reuse alone is not component qualification.

### 5. Run full-wave models reproducibly

Prefer Java API source plus the licensed local batch runner. Resolve the solver from `PHOTONIC_SOLVER_ROOT`; never hard-code a personal installation path.

Preview first:

```powershell
& scripts/invoke-waveguide-java-batch.ps1 `
  -JavaFile <model.java> -OutputFile <model.mph> -BatchLog <run.log> -DryRun
```

Remove `-DryRun` only after reviewing paths, selections, study sequence, expected cost, and output locations. Run jobs sequentially when runtime directories or license resources are shared.

### 6. Diagnose before optimizing

When results are wrong, check in this order:

1. topology and path-length definition;
2. materials and geometry selections;
3. port boundaries, orientation, modes, and study binding;
4. boundary conditions and background/PML margin;
5. mesh and wavelength resolution;
6. physics tag, expression, and final dataset;
7. energy budget and missing output channels;
8. only then geometry or optimizer settings.

For a passive two-port device:

```text
T21 = abs(S21)^2
R11 = abs(S11)^2
uncollected = 1 - T21 - R11
```

For a multiport device, evaluate every intended output and each independent input separately. Do not combine different excitations and call the sum one energy balance.

### 7. Optimize at validated fidelity

Define the objective and constraints before running a search. Preserve the baseline. Use coarse-to-fine sweeps, then local or multiobjective optimization only after solver noise and failure handling are understood.

Include penalties for reflection, imbalance, loss, nonuniformity, bandwidth error, fabrication limits, and robustness as appropriate. Re-evaluate winners at higher fidelity and across relevant corners. Do not call a local sweep winner globally optimal.

### 8. Report evidence and hand off

Separate these labels:

- `analytic/reduced-model verified`;
- `circuit-level verified`;
- `2D effective-index full-wave verified`;
- `3D subassembly verified`;
- `full-device 3D verified`;
- `layout concept` or `PDK/DRC checked`;
- `requires experimental validation`.

Leave model/build scripts, manifests, component contracts, logs, tables, plots, gate status, limitations, and the exact next safe action. Keep heavy or proprietary solver artifacts out of public git unless explicitly authorized.

## Verification Gates

Use `references/verification-gates.md` and stop escalation when a gate fails:

1. `G0` device contract;
2. `G1` port and straight-waveguide baseline;
3. `G2` component qualification;
4. `G3` assembly contract;
5. `G4` circuit behavior;
6. `G5` layout/connectivity;
7. `G6` promoted full-wave subassembly;
8. `G7` robustness/optimization;
9. `G8` evidence package.

Missing evidence is not a pass.

## Included Tools

| Tool | Purpose |
|---|---|
| `scripts/new-photonic-project.ps1` | Create a project scaffold with component, circuit, layout, verification, run, report, and handoff folders. |
| `scripts/invoke-waveguide-java-batch.ps1` | Compile Java API source and run the licensed solver batch executable. |
| `scripts/parse-comsol-sweep.py` | Parse exported tables and summarize spectral metrics. |
| `scripts/photonic_assembly.py` | Validate component contracts and compose hierarchical S-parameter networks. |
| `scripts/test_photonic_assembly.py` | Test cascade composition and mode-mismatch rejection. |
| `scripts/test_numeric_tools.py` | Test spectral extrema/spacing and arbitrary-angle circular-bend geometry. |
| `scripts/audit-simulation-artifacts.ps1` | Scan for blocked binaries, large files, and obvious local secrets before publication. |
| `scripts/test_powershell_safety.ps1` | Test native failure propagation, dry-run isolation, and hidden credential-file detection. |
| `scripts/emit-analytic-bend-java-helper.py` | Emit a circular-bend Java helper skeleton. |
| `scripts/mcp_photonic_server.py` | Experimental read/parse/audit/scaffold/dry-run integration layer; not the trusted solver backend. |

## Hard Guardrails

- Do not claim a pretty field plot proves device performance.
- Do not substitute one scalar transmission trace for a complete multiport component contract.
- Do not connect incompatible modes or reference planes silently.
- Do not treat 2D EIM, circuit simulation, DRC, and 3D full-wave evidence as interchangeable.
- Do not publish local paths, usernames, credentials, license data, proprietary PDFs/models, `.mph`, `.class`, logs, or caches without explicit authorization.
- Do not imply vendor affiliation or redistribute proprietary solver files.
- Keep delegated work bounded and auditable. Do not run licensed solver jobs in parallel unless the user authorizes the execution plan and runtime/license isolation is established.
