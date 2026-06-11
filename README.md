# Photonic Waveguide Optics Skill

An installable Codex skill for reproducible integrated-photonic simulation work: waveguides, bends, splitters, directional couplers, MZI/aMZI/LT-aMZI devices, resonators, gratings, sensors, modulators, parameter sweeps, and simulation reports.

The main idea is simple: this skill teaches Codex how to treat photonic simulations as an auditable engineering workflow, not just as geometry drawing. A good run should preserve the chain from literature parameters, geometry assumptions, material selections, ports, mesh, solver settings, exported spectra, postprocessing scripts, and final interpretation.

## What This Skill Helps With

Use this skill when you want Codex to help with:

- SOI strip/rib waveguide models and 2D effective-index approximations;
- straight waveguide, bend, taper, transition, and mode-converter validation;
- directional couplers, MMI couplers, Y-branches, and splitters;
- ring resonators, Bragg gratings, periodic filters, and grating couplers;
- conventional MZI, asymmetric MZI, and loop-terminated asymmetric MZI workflows;
- sensors, modulators, and early inverse-design or layout-screening studies;
- wavelength sweeps, S-parameter extraction, FSR checks, insertion loss, extinction ratio, and energy-budget diagnostics;
- Java API plus batch automation for licensed local finite-element solver installations;
- structured reports, handoff notes, and publication-safe artifact audits.

The skill is especially useful when a project needs a new Codex conversation to quickly understand what has been done, what is trusted, what is still only approximate, and what should be tested next.

## What This Repository Does Not Provide

This is an independent educational and workflow aid.

- It is not an official COMSOL product, add-on, tutorial, example library, or vendor package.
- It is not affiliated with, endorsed by, sponsored by, or authorized by COMSOL AB.
- It does not include or license any commercial solver, module, plugin jar, official model, official screenshot, documentation, logo, license file, or vendor dataset.
- It does not make a 2D effective-index model equivalent to final 3D fabrication sign-off.
- It does not remove the user's obligation to comply with their own software license and institutional rules.

COMSOL and COMSOL Multiphysics are registered trademarks of COMSOL AB. References to those names are used only to identify compatible third-party software environments.

## Install

Clone this repository into your Codex skills folder.

Typical Windows location:

```text
C:\Users\<you>\.codex\skills\photonic-waveguide-optics-skill
```

Recommended PowerShell install command:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.codex\skills" | Out-Null
git clone https://github.com/Bian-M-X/comsol-photonic-waveguide-optics-skill.git "$env:USERPROFILE\.codex\skills\photonic-waveguide-optics-skill"
```

If the folder already exists:

```powershell
git -C "$env:USERPROFILE\.codex\skills\photonic-waveguide-optics-skill" pull
```

Restart Codex or open a new session if the skill does not appear immediately.

## First Prompt

After installation, use a prompt like:

```text
Use $photonic-waveguide-optics to build, debug, optimize, or report an integrated photonic waveguide simulation workflow.
```

For an existing project, give Codex the project folder and ask it to read local handoff/report files first:

```text
Use $photonic-waveguide-optics. Read this project folder first, identify the latest trusted simulation state, then propose the next validation or optimization step.
```

## Local Solver Setup

The skill assumes the user has their own licensed local solver installation. For COMSOL-based automation, helper scripts expect a solver root that contains:

```text
bin\win64\comsolbatch.exe
java\win64\jre\bin\javac.exe
plugins\*.jar
```

Set the solver root in PowerShell:

```powershell
$env:PHOTONIC_SOLVER_ROOT = 'C:\Path\To\LicensedSolverRoot'
```

For a persistent Windows user environment variable:

```powershell
setx PHOTONIC_SOLVER_ROOT "C:\Path\To\LicensedSolverRoot"
```

Optional runtime directories can be separated for long jobs or sequential sweeps:

```powershell
$env:PHOTONIC_SOLVER_PREFS = Join-Path $env:TEMP 'photonic-waveguide-solver\prefs'
$env:PHOTONIC_SOLVER_CONFIG = Join-Path $env:TEMP 'photonic-waveguide-solver\config'
$env:PHOTONIC_SOLVER_TMP = Join-Path $env:TEMP 'photonic-waveguide-solver\tmp'
```

Verify the expected files:

```powershell
Test-Path (Join-Path $env:PHOTONIC_SOLVER_ROOT 'bin\win64\comsolbatch.exe')
Test-Path (Join-Path $env:PHOTONIC_SOLVER_ROOT 'java\win64\jre\bin\javac.exe')
Test-Path (Join-Path $env:PHOTONIC_SOLVER_ROOT 'plugins')
```

## Recommended Workflow

For most photonic devices, use a staged flow:

1. Extract literature targets and decide what must be reproduced.
2. Choose the model level: 2D effective-index, substructure 3D, or full 3D.
3. Validate the straight waveguide and numeric ports.
4. Validate standalone building blocks: bend, taper, coupler, splitter, ring, grating, or MMI.
5. Assemble the final device only after key blocks are stable.
6. Run a single-wavelength field check before sweeping.
7. Sweep wavelength or geometry and export CSV/TXT tables.
8. Compare against theory, papers, reduced-order models, or measured data.
9. Write a model-quality report that separates verified facts, approximations, and next actions.

This order prevents a common failure mode: debugging a full interferometer while the real issue is a port, material selection, boundary condition, bend, coupler, mesh, or postprocessing expression.

## Batch Automation

The preferred execution route is Java API source plus the local solver's batch runner.

Preview the command without launching a solve:

```powershell
.\scripts\invoke-waveguide-java-batch.ps1 `
  -SolverRoot $env:PHOTONIC_SOLVER_ROOT `
  -JavaFile 'C:\Path\To\ModelSource.java' `
  -OutputFile 'C:\Path\To\OutputModel.mph' `
  -BatchLog 'C:\Path\To\BatchLog.log' `
  -DryRun
```

Run the model:

```powershell
.\scripts\invoke-waveguide-java-batch.ps1 `
  -SolverRoot $env:PHOTONIC_SOLVER_ROOT `
  -JavaFile 'C:\Path\To\ModelSource.java' `
  -OutputFile 'C:\Path\To\OutputModel.mph' `
  -BatchLog 'C:\Path\To\BatchLog.log'
```

The batch route remains the first choice for trusted solver execution because it is reproducible, easy to log, and keeps model source under review.

## Included Scripts

| Script | Purpose |
|---|---|
| `scripts/invoke-waveguide-java-batch.ps1` | Compile Java API source with the solver-bundled `javac.exe`, then run it through batch mode. |
| `scripts/new-photonic-project.ps1` | Create a standard project folder scaffold for simulation work. |
| `scripts/parse-comsol-sweep.py` | Parse exported sweep tables and summarize peaks, valleys, FSR-like spacings, `S11`, `T21`, and `S11+T21`. |
| `scripts/audit-simulation-artifacts.ps1` | Scan a folder before publication or commit for blocked artifacts and obvious sensitive data. |
| `scripts/emit-analytic-bend-java-helper.py` | Emit a Java helper skeleton for analytic circular/annular-sector bends. |
| `scripts/mcp_photonic_server.py` | Dependency-free stdio MCP-style prototype for resources, safe local tools, sweep parsing, and redacted batch dry-run planning. |
| `scripts/test_mcp_photonic_server.py` | Protocol-level smoke test for the MCP prototype. |

## Documentation Map

Use `SKILL.md` as the router. Load detailed references only when needed.

| Reference | When to read it |
|---|---|
| `references/environment-and-runner.md` | Local solver path setup, batch runner behavior, runtime directories, dry-run safety. |
| `references/wave-optics-port-models.md` | Materials, numeric ports, boundary mode analysis, datasets, mesh, S-parameter expressions. |
| `references/device-family-workflows.md` | General workflows for waveguides, bends, tapers, splitters, rings, gratings, sensors, modulators, and inverse-design regions. |
| `references/interferometer-workflows.md` | MZI, aMZI, LT-aMZI topology, directional coupler calibration, FSR checks, and common failure modes. |
| `references/optimization-and-reporting.md` | Sweeps, objective functions, diagnostics, result tables, reports, and reproducibility packages. |
| `references/smooth-bend-geometry.md` | True smooth bends, analytic circular arcs, annular sectors, centerline length preservation, and bend-radius scans. |
| `references/subagent-orchestration.md` | Planning, execution, geometry, audit, result review, and data-processing subagent patterns. |
| `references/comsol-mcp-evaluation.md` | Direct batch vs interactive server vs MCP wrapper route selection and adoption gates. |
| `references/quantum-photonic-knowledge-base.md` | Quantum photonic chip basics, MZI meshes, phase shifters, Hadamard/CNOT-style building blocks, and literature entry points. |
| `references/project-structure-and-git.md` | Recommended folder layout, naming, handoff files, artifact management, and git policy. |
| `references/legal-and-trademark-notes.md` | Publication, trademark, license, and local-data safety guardrails. |
| `references/source-notes.md` | Pointers to official docs, MCP specs, and paper entry points that should be refreshed when needed. |

## Subagent Roles

The skill includes role contracts under `agents/` for workflows where a new conversation wants structured delegation or independent audit.

Available roles include:

- planning agent;
- geometry-modeling agent;
- execution agent;
- code auditor;
- model auditor;
- results auditor;
- data-processing agent;
- literature/knowledge agent;
- MCP-integration agent.

Recommended use:

1. Read `references/subagent-orchestration.md`.
2. Select only the role files needed for the task.
3. Give each subagent a narrow scope and the relevant local artifacts.
4. Keep solver paths, license information, `.mph` files, raw logs, and private data out of subagent context unless explicitly authorized.

## MCP Prototype Status

The repository includes a minimal local MCP-style server prototype. Its current safe uses are:

- list resources and skill references;
- create a photonic project scaffold;
- audit a project folder for obvious blocked artifacts;
- parse a COMSOL-style sweep table into structured summaries;
- render a redacted Java batch dry-run plan.

Real solver execution through MCP is intentionally not the default. The current route ranking is:

1. Direct Java API plus batch runner for trusted execution.
2. MCP wrapper for structured discovery, parsing, audit, and dry-run planning.
3. Interactive server or LiveLink-style workflows only for special inspection/debugging cases.

Before MCP becomes a daily execution route, it should pass direct-batch equality tests, timeout/failure-mode tests, redaction audits, and a small validated smoke model.

## Example Prompts

Straight waveguide validation:

```text
Use $photonic-waveguide-optics to create a 2D effective-index straight waveguide validation model with two numeric ports, run a single-wavelength solve, and report S21, S11, and field confinement.
```

Directional coupler calibration:

```text
Use $photonic-waveguide-optics to build a standalone 2x2 directional coupler, sweep coupling length and gap, find the 3 dB point near 1550 nm, and export a calibration table.
```

LT-aMZI reproduction:

```text
Use $photonic-waveguide-optics to reproduce a loop-terminated asymmetric MZI using a 2D effective-index approximation. Verify both directional couplers first, connect the loop reflector, sweep wavelength, extract FSR, and compare with lambda^2/(2*n_g*DeltaL).
```

Low-transmission debugging:

```text
Use $photonic-waveguide-optics to audit this model for material selections, port placement, boundary mode datasets, bend loss, coupler imbalance, mesh resolution, S-parameter expressions, and energy balance.
```

True-smooth bend or `R_bend` optimization:

```text
Use $photonic-waveguide-optics to convert polygonal bends to true smooth circular/annular-sector bends, preserve centerline DeltaL, then sweep R_bend and compare max_T21, S11_at_max, S11+T21, peak spacing, weak/strong peak ratio, and path-length error.
```

Report writing:

```text
Use $photonic-waveguide-optics to write a model-quality report that separates paper parameters, implemented assumptions, validation steps, simulation results, known limitations, and next engineering actions.
```

## Key Modeling Rules

- Keep paper-faithful reproduction and engineering optimization as separate tracks.
- Compute path length and `DeltaL` along the centerline, not by coordinate differences.
- Validate standalone couplers/splitters before inserting them into a larger interferometer.
- Do not assume a standalone 3 dB coupler length is optimal inside a round-trip LT-aMZI.
- For LT-aMZI, use `FSR = lambda^2 / (2*n_g*DeltaL)`.
- Check `S11`, `T21`, `S11+T21`, and uncollected energy; do not optimize only peak transmission.
- Use true smooth bend geometry when possible, then preserve path length explicitly.
- Treat 2D effective-index models as fast topology and trend tools, not final 3D fabrication sign-off.
- Run expensive solver jobs sequentially unless runtime directories and memory pressure are known to be isolated.

## Output Expectations

A serious simulation handoff should normally include:

- source scripts or model-generation scripts;
- model files if the user is allowed to keep or share them;
- batch logs;
- exported CSV/TXT sweep data;
- field plots and spectra;
- parameter tables;
- model-quality audit notes;
- comparison with theory, paper data, or experimental data;
- known limitations and next steps.

For public repositories, keep heavy/proprietary/local artifacts out of git unless there is explicit permission and a clear reason.

## Privacy And Release Checklist

Before pushing changes to a public repository, scan for:

- local absolute paths and user names;
- home directories and temporary directories;
- license servers, license files, tokens, credentials, or private environment variables;
- private research PDFs, vendor documentation, official screenshots, official model files, or logos;
- generated `.mph`, `.class`, `.log`, cache, status, and temporary sweep files;
- unpublished project names, unpublished data, and confidential partner information.

The included `.gitignore` blocks common solver outputs and temporary files, but it does not replace a manual audit.

Run the included audit script before publishing:

```powershell
.\scripts\audit-simulation-artifacts.ps1 -ProjectRoot .
```

## Repository Layout

```text
photonic-waveguide-optics-skill/
  SKILL.md
  README.md
  LICENSE
  NOTICE.md
  agents/
  references/
  scripts/
```

## License

The original text, workflow notes, and helper scripts in this repository are provided under the MIT License.

The license does not grant rights to any third-party solver, API, trademark, documentation, model file, example, logo, dataset, or commercial software component beyond what its owner allows.
