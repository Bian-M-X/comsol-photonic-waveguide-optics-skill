# Photonic Waveguide Optics Skill

An installable Codex skill for integrated photonic waveguide simulation workflows.

This project is intentionally named without any commercial solver trademark. In practical use, the bundled automation guidance is mainly written for users who run their own licensed COMSOL&reg; Multiphysics&reg; installation in batch mode. The repository does not include, copy, redistribute, or sublicense any proprietary solver software, documentation, example models, screenshots, logos, license files, or vendor-owned datasets.

## What This Skill Is For

Use this skill when you want Codex to help build, debug, automate, or report optical simulations for integrated photonics, especially:

- SOI strip or rib waveguides
- 2D effective-index top-view models
- port-based frequency-domain wave-optics models
- directional couplers and 3 dB coupler calibration
- conventional MZI, asymmetric MZI, and loop-terminated asymmetric MZI devices
- wavelength sweeps, S-parameters, FSR extraction, insertion loss, and extinction-ratio checks
- external parameter sweeps and reproducible model-quality reports

The skill is designed to push Codex toward an auditable workflow rather than just drawing a geometry. A good simulation deliverable should include geometry assumptions, material assignments, port definitions, boundary conditions, mesh strategy, solver settings, field plots, sweep data, model files, logs, and a comparison with theory or reference papers.

## What This Skill Is Not

- It is not an official COMSOL product, add-on, tutorial, or example library.
- It is not affiliated with, endorsed by, sponsored by, or authorized by COMSOL AB.
- It does not grant access to any commercial solver or module.
- It does not replace the user's obligation to comply with their own software license.
- It does not turn a 2D effective-index model into a final 3D fabrication sign-off.

## Install The Skill

Clone or copy this repository into your Codex skills directory.

Typical Windows location:

```text
C:\Users\<you>\.codex\skills\photonic-waveguide-optics-skill
```

The repository root contains `SKILL.md`, so Codex can load it directly as a skill project.

Recommended PowerShell install command:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.codex\skills" | Out-Null
git clone https://github.com/Bian-M-X/photonic-waveguide-optics-skill.git "$env:USERPROFILE\.codex\skills\photonic-waveguide-optics-skill"
```

If the folder already exists and you only want to update it:

```powershell
git -C "$env:USERPROFILE\.codex\skills\photonic-waveguide-optics-skill" pull
```

If Git is not installed, download the ZIP release manually from GitHub, extract it, and place the extracted folder at:

```text
C:\Users\<you>\.codex\skills\photonic-waveguide-optics-skill
```

After copying or cloning, restart Codex or start a new session if the skill does not appear immediately.

After installation, a typical prompt is:

```text
Use $photonic-waveguide-optics to build, debug, optimize, or report an integrated photonic waveguide simulation workflow.
```

## Main COMSOL-Based Usage Model

The skill assumes the user has their own licensed solver installation. For COMSOL-based automation, the helper script expects a solver root directory that contains these vendor-provided files:

```text
bin\win64\comsolbatch.exe
java\win64\jre\bin\javac.exe
plugins\*.jar
```

Only the paths are referenced. These binaries and plugin jars are not included in this repository.

## Configure Your Local Solver Path

This repository does not hard-code the author's machine path. Each user should point the skill to their own local installation.

For the current PowerShell session:

```powershell
$env:PHOTONIC_SOLVER_ROOT = 'C:\Path\To\LicensedSolverRoot'
```

For a persistent Windows user environment variable:

```powershell
setx PHOTONIC_SOLVER_ROOT "C:\Path\To\LicensedSolverRoot"
```

Example only:

```powershell
$env:PHOTONIC_SOLVER_ROOT = 'C:\Path\To\COMSOL\Multiphysics'
```

If your installation is on another drive or uses another version folder, use that path instead. The important point is that `PHOTONIC_SOLVER_ROOT` should be the folder above `bin`, `java`, and `plugins`.

Optional runtime directories default to your temporary folder. You may override them when running long jobs or parallel sweeps:

```powershell
$env:PHOTONIC_SOLVER_PREFS = Join-Path $env:TEMP 'photonic-waveguide-solver\prefs'
$env:PHOTONIC_SOLVER_CONFIG = Join-Path $env:TEMP 'photonic-waveguide-solver\config'
$env:PHOTONIC_SOLVER_TMP = Join-Path $env:TEMP 'photonic-waveguide-solver\tmp'
```

Use separate runtime directories for parallel jobs to avoid preference, cache, and lock-file collisions.

## Verify The Local Setup

After setting `PHOTONIC_SOLVER_ROOT`, check that the expected files exist:

```powershell
Test-Path (Join-Path $env:PHOTONIC_SOLVER_ROOT 'bin\win64\comsolbatch.exe')
Test-Path (Join-Path $env:PHOTONIC_SOLVER_ROOT 'java\win64\jre\bin\javac.exe')
Test-Path (Join-Path $env:PHOTONIC_SOLVER_ROOT 'plugins')
```

You can also preview the helper script's command shape without launching a solve:

```powershell
.\scripts\invoke-waveguide-java-batch.ps1 `
  -SolverRoot $env:PHOTONIC_SOLVER_ROOT `
  -JavaFile 'C:\Path\To\ModelSource.java' `
  -OutputFile 'C:\Path\To\OutputModel.mph' `
  -BatchLog 'C:\Path\To\BatchLog.log' `
  -DryRun
```

By default, `-DryRun` hides the full plugin classpath so public logs do not expose local installation details. Add `-ShowFullPaths` only for private local debugging.

## Typical COMSOL Batch Workflow

A normal automated workflow is:

1. Ask Codex to generate or update a Java API model source file.
2. Compile the Java source with the solver-bundled `javac.exe` and the local plugin jars.
3. Run the compiled class through `comsolbatch.exe`.
4. Save the `.mph` model from inside the solver run.
5. Export sweep data as CSV/TXT.
6. Generate field plots, spectra, and a model-quality report outside the solver.

The bundled helper script performs steps 2 and 3:

```powershell
.\scripts\invoke-waveguide-java-batch.ps1 `
  -SolverRoot $env:PHOTONIC_SOLVER_ROOT `
  -JavaFile 'C:\Path\To\ModelSource.java' `
  -OutputFile 'C:\Path\To\OutputModel.mph' `
  -BatchLog 'C:\Path\To\BatchLog.log'
```

## How To Prompt Codex

For a straight waveguide validation:

```text
Use $photonic-waveguide-optics to create a 2D effective-index straight waveguide validation model with two numeric ports, run a single-wavelength solve, and report S21, S11, and field confinement.
```

For directional coupler calibration:

```text
Use $photonic-waveguide-optics to build a standalone 2x2 directional coupler, sweep coupling length and gap, find the 3 dB point at 1550 nm, and export a calibration table.
```

For MZI or LT-aMZI reproduction:

```text
Use $photonic-waveguide-optics to reproduce a loop-terminated asymmetric MZI using a 2D effective-index approximation, verify both directional couplers first, connect the loop reflector, sweep wavelength, extract FSR, and compare with lambda^2/(2*n_g*DeltaL).
```

For debugging a low-transmission model:

```text
Use $photonic-waveguide-optics to audit this model for material selections, port placement, boundary mode datasets, bend loss, coupler imbalance, mesh resolution, S-parameter expressions, and energy balance.
```

For reporting:

```text
Use $photonic-waveguide-optics to write a model-quality report that separates paper parameters, implemented assumptions, validation steps, simulation results, known limitations, and next engineering actions.
```

## Recommended Modeling Order

For integrated photonic circuits, do not start from the final full device unless the building blocks are already verified.

Recommended order:

1. Straight waveguide validation.
2. Standalone port and boundary-mode validation.
3. Standalone directional coupler or splitter calibration.
4. Conventional MZI or asymmetric MZI verification.
5. Final target topology, such as LT-aMZI.
6. Wavelength sweep and metric extraction.
7. Mesh refinement and sensitivity checks.
8. Report and reproducibility package.

This staged approach makes failures easier to localize. Low transmission may come from port mismatch, wrong material domains, an uncalibrated coupler, bend radiation, bad mesh, boundary loss, dataset selection, or an incorrect topology.

## Project Structure

```text
photonic-waveguide-optics-skill/
  SKILL.md
  README.md
  LICENSE
  NOTICE.md
  agents/
    openai.yaml
  references/
    environment-and-runner.md
    wave-optics-port-models.md
    interferometer-workflows.md
    optimization-and-reporting.md
    legal-and-trademark-notes.md
  scripts/
    invoke-waveguide-java-batch.ps1
```

Use `SKILL.md` as the router. It tells Codex which reference file to load for each task:

- `references/environment-and-runner.md`: local solver path configuration, batch execution, helper script usage, and privacy-safe dry runs.
- `references/wave-optics-port-models.md`: materials, ports, boundary mode analysis, mesh, datasets, and S-parameter expressions.
- `references/interferometer-workflows.md`: directional coupler, MZI, aMZI, and LT-aMZI construction and acceptance checks.
- `references/optimization-and-reporting.md`: sweeps, diagnostics, optimization loops, exported data, and reporting.
- `references/legal-and-trademark-notes.md`: publication, trademark, license, and local-data safety guardrails.

## Output Expectations

A serious simulation result should normally include:

- source scripts or model-generation scripts
- `.mph` model files when the user is allowed to share them
- batch logs
- exported CSV/TXT sweep data
- field plots, spectra, and convergence figures
- parameter tables
- model-quality audit
- comparison with theory, paper data, or experimental references
- known limitations and next steps

Before publishing outputs, remove private paths, license details, local logs, paper PDFs, vendor documentation, and any model files that you are not allowed to redistribute.

## Privacy And Release Checklist

Before pushing changes to a public repository, scan for:

- local absolute paths from the author's machine
- user names and home directories
- license server names, license files, access tokens, or credentials
- private research PDFs or vendor documentation
- generated `.mph`, `.class`, `.log`, cache, and temporary sweep files
- unpublished project names, unpublished data, or confidential partner information

The included `.gitignore` blocks common solver outputs and temporary files, but it is not a substitute for reviewing the repository before release.

## Legal And Trademark Notes

See `NOTICE.md` and `references/legal-and-trademark-notes.md`.

Short version:

- This is an independent educational and workflow skill.
- It is not affiliated with, endorsed by, sponsored by, or authorized by COMSOL AB.
- COMSOL and COMSOL Multiphysics are registered trademarks of COMSOL AB.
- Any references to those marks are used only to identify compatible third-party software environments.
- Users must provide and comply with their own valid software licenses.
- This repository does not include proprietary solver binaries, official documentation, official images, official model files, examples, logos, license files, or vendor-owned datasets.

## License

The original text, workflow notes, and helper script in this repository are provided under the MIT License. The license does not grant rights to any third-party software, trademarks, documentation, model files, examples, logos, APIs, or datasets beyond what their owners allow.
