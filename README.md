# Photonic Waveguide Optics Skill

[![Validate skill](https://github.com/Bian-M-X/comsol-photonic-waveguide-optics-skill/actions/workflows/validate.yml/badge.svg)](https://github.com/Bian-M-X/comsol-photonic-waveguide-optics-skill/actions/workflows/validate.yml)

Use this installable Codex skill to design, simulate, debug, optimize, hierarchically compose, and report integrated-photonic devices with explicit evidence gates.

The skill covers individual waveguide devices and larger circuits assembled from validated complex multiport S-parameter models. It keeps analytic, circuit-level, 2D effective-index, 3D full-wave, layout, and experimental claims separate so that a fast model is never presented as stronger evidence than it is.

> Skill token: `$photonic-waveguide-optics`
>
> Repository: `Bian-M-X/comsol-photonic-waveguide-optics-skill`
>
> License: MIT for this repository's original text and helper code

## Why Use It

- Start from a device contract instead of an untracked geometry sketch.
- Validate straight-waveguide ports before debugging a large circuit.
- Qualify bends, tapers, couplers, splitters, rings, gratings, sensors, and modulators independently.
- Export complete complex S matrices with explicit port, mode, normalization, phase, and reference-plane conventions.
- Compose many calibrated components into a complex circuit before promoting only critical subassemblies to expensive full-wave models.
- Preserve scripts, manifests, logs, metrics, validation gates, limitations, and the next safe action in every handoff.

## Supported Workflows

| Area | Included workflow |
|---|---|
| Component design | Waveguides, bends, tapers, mode converters, directional/MMI couplers, Y branches, rings, gratings, sensors, modulators, and inverse-designed regions |
| Interferometers | MZI, aMZI, LT-aMZI, coupler calibration, path-length control, FSR checks, and energy-budget diagnosis |
| Solver automation | COMSOL Wave Optics Java API source, licensed local batch execution, dry-run review, sweeps, and structured exports |
| Hierarchical composition | Component contracts, full complex multiport S data, assembly manifests, exact port occupancy, mode checks, network reduction, and external S-matrix export |
| Verification | Circuit, 2D EIM, 3D subassembly, full-device, layout/PDK, robustness, and experimental claim boundaries |
| Reproducibility | Project scaffolding, artifact audits, reports, and checkpointable handoffs |

## Install

Clone the repository into the Codex skills folder:

```powershell
$SkillRoot = Join-Path $env:USERPROFILE '.codex\skills\photonic-waveguide-optics'
New-Item -ItemType Directory -Force (Split-Path $SkillRoot) | Out-Null
git clone https://github.com/Bian-M-X/comsol-photonic-waveguide-optics-skill.git $SkillRoot
```

Update an existing installation with a fast-forward-only pull:

```powershell
$SkillRoot = Join-Path $env:USERPROFILE '.codex\skills\photonic-waveguide-optics'
if (-not (Test-Path -LiteralPath $SkillRoot)) {
  $SkillRoot = Join-Path $env:USERPROFILE '.codex\skills\photonic-waveguide-optics-skill'
}
git -C $SkillRoot pull --ff-only
```

Restart Codex or open a new task if the skill does not appear immediately.

## Start With One Prompt

```text
Use $photonic-waveguide-optics. Read D:\Path\To\MyProject first, identify the latest trusted evidence, and propose the next validation or optimization step.
```

For a new complex device:

```text
Use $photonic-waveguide-optics to define component contracts, calibrate reusable building blocks, compose their complete complex S matrices, verify the circuit and layout connectivity, and promote only the critical subassemblies to higher-fidelity full-wave checks.
```

## Run a Solver-Free Smoke Test

Use Python 3 with NumPy. No commercial solver is needed for this example.

```powershell
git clone https://github.com/Bian-M-X/comsol-photonic-waveguide-optics-skill.git
Set-Location .\comsol-photonic-waveguide-optics-skill

python -m pip install -r .\requirements.txt
python .\scripts\test_photonic_assembly.py

$Demo = Join-Path $env:TEMP 'photonic-skill-demo'
.\scripts\new-photonic-project.ps1 -ProjectRoot $Demo -DeviceFamily mzi

python "$Demo\scripts\photonic_assembly.py" validate `
  "$Demo\circuits\assembly.json"

python "$Demo\scripts\photonic_assembly.py" compose `
  "$Demo\circuits\assembly.json" `
  --output "$Demo\data\processed\circuit_sparameters.csv" `
  --summary "$Demo\verification\circuit_summary.json"
```

The `mzi` scaffold includes two ideal 2x2 directional couplers, two arm instances, four external ports, and complete sample complex S data at three wavelengths. Replace the analytic fixtures with qualified component models before making a device claim. Use the default `waveguide` family when you only need the two-stage cascade template.

## Compose a Complex Device

Use this scalable route:

```text
device requirements
  -> validated straight-waveguide and port baseline
  -> qualified component models
  -> complete complex multiport S data
  -> validated assembly manifest
  -> circuit spectrum and sensitivity
  -> port-aware layout and extracted connectivity
  -> selected full-wave subassembly checks
  -> robustness study and evidence package
```

Define each reusable component in `assembly.json` with:

- an ordered port list and one declared mode per port;
- a model level: `analytic`, `reduced`, `full-wave-2d-eim`, `full-wave-3d`, or `measured`;
- a reference-plane description;
- a relative path to a complete wavelength-dependent complex S-matrix CSV;
- a passivity declaration when applicable.

Store one matrix entry per row with the exact columns `wavelength_nm,out_port,in_port,s_real,s_imag`.

Use `scripts/photonic_assembly.py` to reject unknown endpoints, reused or dangling ports, connected mode mismatches, incomplete S matrices, mismatched wavelength grids, and non-passive component data. The composer eliminates internal connected ports and exports the external circuit S matrix at every supplied wavelength.

Represent phase, propagation loss, bends, tapers, and transitions as explicit components. Treat a manifest connection as an ideal zero-length, zero-loss connection.

### Current composition boundary

The supplied composer is a deterministic circuit-level reference implementation. It does not yet import Touchstone or solver port sweeps automatically, interpolate mismatched wavelength grids, generate a foundry layout, run DRC, infer electromagnetic coupling between nominally separate blocks, or replace a 2D/3D solver. Promote a subassembly or the complete device when block separation is physically invalid, parasitic coupling matters, or the intended claim requires whole-device fields.

## Use the Verification Gates

| Gate | Required evidence |
|---|---|
| `G0` | Device contract: topology, ports, modes, band, stack, metrics, tolerances, and claim level |
| `G1` | Straight-waveguide, port, mesh, boundary, phase, and reference-plane baseline |
| `G2` | Independent component qualification and complete reusable S data |
| `G3` | Valid manifest, conventions, endpoints, modes, occupancy, and wavelength grid |
| `G4` | Circuit response, energy/passivity checks, sensitivity, and expected limiting behavior |
| `G5` | Port-aware layout, extracted connectivity, and PDK/DRC status when applicable |
| `G6` | Promoted full-wave validation of the critical interaction region or subassembly |
| `G7` | Re-evaluated optimum across solver fidelity and relevant process/temperature corners |
| `G8` | Reproducible evidence package with limitations and an exact next action |

Stop escalation when a gate fails. Missing evidence is not a pass.

## Run a Licensed Local Solver

Provide your own licensed COMSOL installation. Set the solver root instead of hard-coding a personal path:

```powershell
$env:PHOTONIC_SOLVER_ROOT = 'C:\Path\To\LicensedSolverRoot'
```

Preview the generated batch command first:

```powershell
.\scripts\invoke-waveguide-java-batch.ps1 `
  -SolverRoot $env:PHOTONIC_SOLVER_ROOT `
  -JavaFile 'C:\Path\To\ModelSource.java' `
  -OutputFile 'C:\Path\To\OutputModel.mph' `
  -BatchLog 'C:\Path\To\BatchLog.log' `
  -DryRun
```

Remove `-DryRun` only after reviewing paths, selections, study order, expected cost, and outputs. Keep direct Java API plus batch execution as the trusted solve path; use the MCP prototype for discovery, scaffolding, parsing, audit, and redacted dry-run planning until it passes solver-execution parity tests.

## Included Tools

| Tool | Purpose |
|---|---|
| `scripts/new-photonic-project.ps1` | Create requirements, components, circuits, layout, models, runs, data, verification, reports, and handoff folders. |
| `scripts/photonic_assembly.py` | Validate a hierarchical manifest and compose external wavelength-dependent complex S parameters. |
| `scripts/test_photonic_assembly.py` | Test a two-stage cascade, a four-component balanced MZI, and mode-mismatch rejection. |
| `scripts/invoke-waveguide-java-batch.ps1` | Compile Java API source with the solver-bundled JDK and run the licensed batch executable. |
| `scripts/parse-comsol-sweep.py` | Parse exported sweep tables and summarize spectral metrics. |
| `scripts/test_numeric_tools.py` | Test wavelength ordering, plateau extrema, zero spectra, and arbitrary-angle circular bends. |
| `scripts/audit-simulation-artifacts.ps1` | Detect blocked binaries, large files, and obvious local secrets before publication. |
| `scripts/test_powershell_safety.ps1` | Test compiler/batch failure propagation, dry-run isolation, and hidden credential-file detection without COMSOL. |
| `scripts/emit-analytic-bend-java-helper.py` | Emit a circular-bend Java helper skeleton. |
| `scripts/mcp_photonic_server.py` | Expose dependency-free local resource, scaffold, parse, audit, and dry-run operations. |
| `scripts/test_mcp_photonic_server.py` | Exercise the MCP protocol surface without executing a solver. |

## Validate This Skill

Run the deterministic tests from the repository root:

```powershell
python .\scripts\test_photonic_assembly.py
python .\scripts\test_numeric_tools.py
python .\scripts\test_mcp_photonic_server.py
.\scripts\test_powershell_safety.ps1
.\scripts\audit-simulation-artifacts.ps1 -ProjectRoot . -FailOnIssues
git diff --check
```

When the Codex system `skill-creator` package and PyYAML are available in the selected Python environment, also run:

```powershell
python "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" .
```

## Documentation Map

Use `SKILL.md` as the concise router and load only the reference needed for the next action.

| Need | Reference |
|---|---|
| Local solver and batch setup | `references/environment-and-runner.md` |
| Materials, ports, studies, datasets, and mesh | `references/wave-optics-port-models.md` |
| Complete complex S matrices and source sweeps | `references/frequency-domain-source-sweeps.md` |
| Component-family workflows | `references/device-family-workflows.md` |
| MZI, aMZI, LT-aMZI, couplers, and FSR | `references/interferometer-workflows.md` |
| Circular and Euler bend geometry | `references/smooth-bend-geometry.md` |
| Hierarchical component-to-circuit workflow | `references/hierarchical-device-workflow.md` |
| Stage acceptance and claim boundaries | `references/verification-gates.md` |
| Optimization, robustness, and reporting | `references/optimization-and-reporting.md` |
| Quantum photonic circuits and mesh context | `references/quantum-photonic-knowledge-base.md` |
| Project layout, artifacts, git, and handoffs | `references/project-structure-and-git.md` |
| Batch, interactive server, and MCP route selection | `references/comsol-mcp-evaluation.md` |
| Official source links and refresh targets | `references/source-notes.md` |
| Licensing, trademarks, and publication safety | `references/legal-and-trademark-notes.md` |
| Optional delegated-role boundaries | `references/subagent-orchestration.md` |

## Repository Layout

```text
photonic-waveguide-optics/
  SKILL.md
  README.md
  requirements.txt
  agents/openai.yaml
  assets/templates/hierarchical-device/
  references/
  scripts/
```

## Safety, Licensing, and Claim Boundaries

This repository is an independent workflow aid. It is not affiliated with, endorsed by, sponsored by, or authorized by COMSOL AB. It does not include or license any commercial solver, proprietary model, official screenshot, vendor documentation, license file, logo, or dataset. COMSOL and COMSOL Multiphysics are registered trademarks of COMSOL AB and are named only to identify a compatible third-party software environment.

Before publication, exclude local paths, user names, credentials, license data, private papers/models, `.mph`, `.class`, logs, caches, and unpublished results. A clean field plot, a circuit trace, or a 2D EIM result is not by itself full-device 3D or experimental validation.

## License

The repository's original text, workflow notes, and helper scripts are available under the [MIT License](LICENSE). Third-party tools, APIs, trademarks, documents, models, and datasets remain subject to their owners' terms.
