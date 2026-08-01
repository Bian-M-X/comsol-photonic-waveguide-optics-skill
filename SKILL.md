---
name: photonic-waveguide-optics
description: Design, validate, compose, debug, optimize, and report auditable photonic integrated circuits. Use for waveguides, bends, tapers, couplers, splitters, rings, gratings, MZI/aMZI/LT-aMZI, sensors, modulators, compact models, complex optical S parameters, PDK/layout/netlist workflows, COMSOL Wave Optics Java and batch work, MATLAB-assisted legacy or numerical workflows, robustness, packaging, tapeout, measurement correlation, and evidence-gated handoffs.
---

# Photonic Waveguide Optics

Build an auditable path from design intent to qualified components, composed
circuits, layout/connectivity evidence, selected full-wave checks, and
measurement correlation. Use the installed `photonic` runtime as the business
entry point and treat external tools as bounded adapters.

## Start Every Task

1. Read the user-specified project, handoff, model, paper, or repository first.
2. Identify the latest trusted run, current G0-G8/M0-M4 ledger, unresolved
   blockers, and exact next action.
3. Classify the request as `design`, `reproduce`, `debug`, `compose`,
   `validate`, `optimize`, `layout`, `tapeout`, `measure`, or `report`.
4. Freeze the intended claim, device ports, band, modes/polarization, process
   stack or PDK alias, metrics, tolerances, and evidence level.
5. Choose the lowest-cost model that can answer the question.
6. Verify capabilities before using optional tools. Keep implementation,
   availability, execution, and physical acceptance separate.

Do not begin a large full-wave solve or optimization before the
straight-waveguide/port baseline and critical building blocks are qualified.
Missing evidence is `blocked`, never an inferred pass.

## Route to the Required Material

Read the minimum relevant set, but read each selected file completely.

| Task | Read |
|---|---|
| Runtime, CLI, runs, phases | `docs/architecture/runtime-design.md`, `docs/roadmap.md` |
| Adapter and contract policy | `docs/architecture/adapter-contract.md`, `docs/architecture/design-intent.md` |
| Third-party adapter provider | `docs/providers/authoring-third-party-adapter.md` |
| PDK and compact-model lifecycle | `docs/architecture/pdk-model.md`, `docs/architecture/compact-model-lifecycle.md` |
| MATLAB integration or security | `docs/architecture/matlab-integration.md`, `docs/architecture/matlab-security.md` |
| Provenance or migration | `docs/architecture/provenance.md`, `docs/migration.md` |
| Runtime upgrades, compatibility, packaged resources | `docs/maintenance.md` |
| PDK/layout/custom/MATLAB/tapeout workflows | matching file under `docs/workflows/` |
| Current PIC tool research | `docs/research/tool-landscape.md` |
| Current MATLAB tool research | `docs/research/matlab-tool-landscape.md` |
| Solver paths, Java compilation, batch execution | `references/environment-and-runner.md` |
| Materials, ports, mode studies, mesh, datasets | `references/wave-optics-port-models.md` |
| Complete complex S matrices and source sweeps | `references/frequency-domain-source-sweeps.md` |
| Waveguides, bends, tapers, couplers, rings, gratings | `references/device-family-workflows.md` |
| MZI, aMZI, LT-aMZI, couplers, FSR | `references/interferometer-workflows.md` |
| Circular/Euler bends and path length | `references/smooth-bend-geometry.md` |
| Versioned reusable geometry, port, material, and S-matrix recipes | `references/modeling-recipes.md` |
| Hierarchical circuits and layout/netlists | `references/hierarchical-device-workflow.md` |
| Gates and claim boundaries | `references/verification-gates.md` |
| Sweeps, optimization, robustness, reports | `references/optimization-and-reporting.md` |
| Project artifacts, git, handoffs | `references/project-structure-and-git.md` |
| MCP vs batch vs interactive control | `references/comsol-mcp-evaluation.md` |
| Sources, licenses, trademarks, publication | `references/source-notes.md`, `references/legal-and-trademark-notes.md` |
| Optional delegated roles | `references/subagent-orchestration.md` |

## Use the Runtime

Prefer the installed CLI:

```powershell
photonic --version
photonic check --project-root <project> --json
photonic status --project-root <project> --json
photonic doctor --project-root <project> --json
```

Create a project with `photonic init`; do not copy package business logic into
the project. Available profiles are `pdk-first`, `layout-first`,
`custom-device-first`, `matlab-legacy-layout`, and
`matlab-assisted-design`.

Use these command groups as narrow workflow surfaces:

- contracts and models: `pdk`, `component`, `model`, `sparams`, `variation`;
- topology and implementation: `circuit`, `netlist`, `layout`;
- bounded external planning: `solver`, `matlab`;
- campaigns and release: `optimize`, `package`, `testplan`, `tapeout`,
  `measurement`;
- evidence and publication safety: `gate`, `report`, `audit`.

Use `--json` for machine-facing work. Preserve exit-code meaning: invalid input
2, unavailable 3, incompatible 4, execution failure 5, acceptance rejection 6,
security violation 7, timeout 8.

Legacy scripts remain compatibility routes. Do not fork new numerical,
scaffold, parser, or audit logic into them.

## Modeling Ladder

| Question | Default evidence level |
|---|---|
| topology, phase trend, FSR, coarse screening | analytic/reduced or circuit |
| many qualified connected blocks | complete complex multiport S network |
| individual passive in-plane block | 2D EIM, then targeted 3D |
| vertical confinement, etch depth, free-space/grating coupling | 3D full wave |
| placement, routing, connectivity, rules | layout and extracted netlist |
| final corner behavior | circuit corners plus promoted full-wave checks |
| fabricated behavior | calibrated measurement and correlation |

Use a complete-device 3D solve only when the claim requires it, the device is
small enough to converge, or interaction physics invalidates block separation.

## Core Workflow

### 1. Freeze the design intent

Record topology, external ports and excitations, wavelength/frequency band,
materials and cross-sections, polarization/modes, PDK/process stack, metrics,
tolerances, variation variables, packaging/test constraints, and claim level.
Keep a paper-faithful baseline separate from engineering optimization.

### 2. Establish the port baseline

Use the same cross-section and conventions as the intended device. Verify mode
shape, `S21`, `S11`, phase, mesh, boundaries/PML, and reference planes. Numeric
ports require one Boundary Mode Analysis per port before the driven study.
Exclude ports from scattering/radiation selections.

After materials, boundaries, ports, PML, or mesh change, invalidate stale mode
selection and phase evidence.

### 3. Qualify building blocks

Evaluate each bend, taper, splitter, coupler, ring, grating, transition, phase
section, sensor, modulator, or inverse-designed region independently.

For reusable models, export the complete complex S matrix across the declared
band. Record port order, modes, normalization, time/phase convention,
reference planes, model level, geometry/process parameters, validity range,
source run, and hashes.

For COMSOL source sweeps, obtain every input column from the same built model
and common modal basis. Do not rebuild the second input independently without
a proved gauge alignment.

### 4. Compose before promoting

```text
qualified components
  -> complete complex S data
  -> validated manifest/netlist
  -> circuit response and sensitivity
  -> layout and extracted connectivity
  -> selected full-wave promotion
```

Represent propagation phase/loss, bends, tapers, and transitions explicitly.
An assembly connection is ideal and zero-length. Reject unknown endpoints,
port reuse, dangling required ports, mode mismatches, incomplete matrices,
wavelength-grid mismatches, non-finite values, and passivity violations.

Geometry-part reuse does not transfer material, physics, mesh, selection, or
component-qualification evidence.

### 5. Run external tools reproducibly

Probe first and render a dry-run plan. Use argument arrays, allowed roots,
isolated runtime directories, timeouts, redaction, fixed entrypoints, and
commercial concurrency one unless explicitly authorized otherwise.

For COMSOL, Java API source plus the licensed local batch runner remains the
trusted legacy execution path:

```powershell
& .\scripts\invoke-waveguide-java-batch.ps1 `
  -JavaFile <model.java> `
  -OutputFile <model.mph> `
  -BatchLog <run.log> `
  -DryRun
```

Remove `-DryRun` only after reviewing paths, selections, study order, cost,
outputs, and authorization. Exit code zero without the declared output model
and batch log is failure.

For MATLAB, `matlab -batch` is the default controlled route. Phase A supports
check/plan and fixed-wrapper contracts. An Engine import, shared-session name,
product list, or compiled MEX file is not trusted execution. Run real batch,
Engine, layout, FDFD, or RF fixtures only as authorized Phase B validation.
LiveLink, Lumerical, instruments, Simulink, real PDK/tapeout, and remote/HPC
work remain Phase C until their own adoption gates pass.

### 6. Debug by evidence

Check, in order:

1. topology and path-length definition;
2. material and geometry selections;
3. port orientation, modes, study binding, normalization, reference planes;
4. boundaries, background/PML, and missing channels;
5. mesh and wavelength sampling;
6. physics tag, expression, dataset, and source column;
7. energy/passivity budget;
8. only then geometry or optimizer settings.

For each independent input, account for every intended output. Do not combine
different excitations and label the sum one energy balance.

### 7. Optimize at accepted fidelity

Define objectives, constraints, budgets, failure handling, and robustness
variables before searching. Preserve the baseline and checkpoints. Re-evaluate
winners at higher fidelity and relevant process/temperature corners. A local,
heuristic, surrogate, or noisy search winner is not a proved global optimum.

### 8. Inspect, gate, and hand off

Execution status and acceptance status are independent. Inspect artifacts,
hashes, units, conventions, convergence, tolerances, and limitations before
changing a gate.

Use:

- G0 device contract;
- G1 port and straight-waveguide baseline;
- G2 component qualification;
- G3 assembly contract;
- G4 circuit behavior;
- G5 layout and connectivity;
- G6 promoted full-wave subassembly;
- G7 robustness and optimization;
- G8 reproducible evidence package;
- M0-M4 for test readiness, raw integrity, calibrated measurement,
  correlation, and model recalibration.

Handoff scripts/contracts, manifests, logs, tables, plots, run/gate state,
limitations, and the exact next safe action. Keep proprietary or heavy
artifacts out of public git unless explicitly authorized.

## Phase and Claim Boundaries

- Phase A proves the local core, contracts, mocks, safe plans, and compatibility
  paths only after its acceptance suite passes.
- Phase B is licensed local validation with controlled non-confidential
  fixtures.
- Phase C is bounded commercial, foundry, instrument, measurement, and remote
  integration after backend-specific adoption gates.

Use only the evidence label actually earned: analytic/reduced, circuit,
layout-concept, PDK/DRC-checked, 2D EIM, 3D subassembly, full-device 3D,
measured, calibrated, correlated, or recalibrated. These labels are not
interchangeable.

## Hard Guardrails

- Never claim a field plot, import, dry-run, descriptor, product listing, or
  process exit alone proves device performance.
- Never substitute a scalar transmission trace for a complete multiport
  contract.
- Never connect incompatible modes, normalizations, or reference planes
  silently.
- Never expose arbitrary shell, Python, MATLAB, Lumerical, or instrument text.
- Never mutate a frozen tapeout manifest or immutable raw measurement.
- Never publish credentials, usernames, local paths, license data, instrument
  addresses, NDA PDKs, proprietary papers/models, solver binaries, `.mph`,
  compiled artifacts, logs, or caches without explicit authorization.
- Never imply vendor affiliation or redistribute third-party assets outside
  their license.
- Keep delegated work bounded and independently auditable. Do not parallelize
  licensed solver work without explicit authorization and proven isolation.
