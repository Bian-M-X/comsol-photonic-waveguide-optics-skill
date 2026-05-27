# Photonic Waveguide Optics Skill

An installable Codex skill for integrated photonic waveguide simulation workflows, with emphasis on port-based finite-element optical models, directional couplers, MZI/aMZI/LT-aMZI interferometers, wavelength sweeps, and parameter optimization.

This project is intentionally named without any commercial solver trademark. It may describe interoperability with licensed third-party simulation software, but it does not include, copy, redistribute, or sublicense any proprietary software, documentation, examples, logos, or model files.

## What This Skill Helps With

- Building auditable simulation workflows for optical waveguides and interferometers.
- Using 2D effective-index approximations responsibly.
- Setting up materials, ports, boundary mode analysis, frequency-domain studies, and wavelength sweeps.
- Calibrating directional couplers before assembling MZI or LT-aMZI devices.
- Diagnosing low transmission using S-parameters and energy balance.
- Running external parameter sweeps and preparing reproducible reports.

## Install

Copy or clone this repository into your Codex skills directory. Typical locations are:

```text
C:\Users\<you>\.codex\skills\photonic-waveguide-optics-skill
```

The root folder contains `SKILL.md`, so it can be used directly as a skill project.

## Suggested Usage Prompt

```text
Use $photonic-waveguide-optics to build, debug, or report a port-based optical waveguide simulation workflow.
```

Example:

```text
Use $photonic-waveguide-optics to reproduce an SOI loop-terminated asymmetric MZI in a 2D effective-index model, calibrate its directional couplers, sweep wavelength, extract FSR, and prepare a model-quality report.
```

## Configure Your Solver Path

This project intentionally does not hard-code the author's local installation path. Before using the helper script, set your own licensed solver root:

```powershell
$env:PHOTONIC_SOLVER_ROOT = 'C:\Path\To\LicensedSolverRoot'
```

Optional runtime directories default to your temporary folder, but can be overridden:

```powershell
$env:PHOTONIC_SOLVER_PREFS = Join-Path $env:TEMP 'photonic-waveguide-solver\prefs'
$env:PHOTONIC_SOLVER_CONFIG = Join-Path $env:TEMP 'photonic-waveguide-solver\config'
$env:PHOTONIC_SOLVER_TMP = Join-Path $env:TEMP 'photonic-waveguide-solver\tmp'
```

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

## Legal and Trademark Notes

See `NOTICE.md` and `references/legal-and-trademark-notes.md`.

Short version:

- This is an independent educational/workflow skill.
- It is not affiliated with, endorsed by, sponsored by, or authorized by COMSOL AB.
- COMSOL and COMSOL Multiphysics are registered trademarks of COMSOL AB.
- Users must provide their own valid license for any proprietary solver they use.
- This repository does not include proprietary solver binaries, official documentation, official images, official model files, or logos.

## Public Release Review

- Project folder/repository name: `photonic-waveguide-optics-skill`, with no third-party solver trademark.
- Skill name: `photonic-waveguide-optics`, with no third-party solver trademark.
- Included content: original workflow instructions, reference notes, and one helper script.
- Excluded content: proprietary software, license files, copied manuals, official examples, official screenshots, and logos.
- Solver references are compatibility statements only and do not imply endorsement, sponsorship, authorization, or affiliation.
- Local-data check: no author-specific absolute paths, user home directories, paper PDFs, model outputs, logs, license files, or solver cache files are intended to be committed.

## License

The original text, workflow notes, and helper script in this repository are provided under the MIT License. The license does not grant rights to any third-party software, trademarks, documentation, model files, or APIs beyond what their owners allow.
