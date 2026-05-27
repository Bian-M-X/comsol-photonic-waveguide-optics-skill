# Environment and Batch Runner

Use this reference when a task needs local solver paths, Java API automation, batch execution, or runtime-directory setup.

## Local Solver Environment

This workflow can be used with a licensed COMSOL&reg; Multiphysics&reg; simulation software installation. The user must provide and comply with their own valid software license.

Do not hard-code the author's local installation path in reusable skills, examples, logs, or reports. Each user should configure their own machine-specific paths with parameters or environment variables.

Recommended environment variables:

```powershell
$env:PHOTONIC_SOLVER_ROOT = 'C:\Path\To\LicensedSolverRoot'
$env:PHOTONIC_SOLVER_PREFS = Join-Path $env:TEMP 'photonic-waveguide-solver\prefs'
$env:PHOTONIC_SOLVER_CONFIG = Join-Path $env:TEMP 'photonic-waveguide-solver\config'
$env:PHOTONIC_SOLVER_TMP = Join-Path $env:TEMP 'photonic-waveguide-solver\tmp'
```

The solver root is expected to contain the vendor-provided batch executable, bundled Java compiler, and plugin jars. On Windows, common relative locations under the solver root are:

```text
bin\win64\comsolbatch.exe
java\win64\jre\bin\javac.exe
plugins\*.jar
```

These executable names are compatibility references only; the repository does not include those files.

Run batch jobs sequentially when they share runtime directories. For parallel sweeps, create separate runtime directories per worker to avoid lock-file and cache collisions.

## Reliable Compile Pattern

```powershell
$solverRoot = $env:PHOTONIC_SOLVER_ROOT
if (-not $solverRoot) { throw 'Set PHOTONIC_SOLVER_ROOT first.' }

$plugins = Join-Path $solverRoot 'plugins'
$javac = Join-Path $solverRoot 'java\win64\jre\bin\javac.exe'
$cp = (Get-ChildItem -LiteralPath $plugins -Filter '*.jar' | ForEach-Object { $_.FullName }) -join ';'
& $javac -proc:none -cp $cp 'C:\Path\To\ModelSource.java'
```

`-proc:none` avoids annotation-processing noise and has been more reliable in local batch workflows.

## Reliable Batch Pattern

```powershell
$solverRoot = $env:PHOTONIC_SOLVER_ROOT
$prefs = if ($env:PHOTONIC_SOLVER_PREFS) { $env:PHOTONIC_SOLVER_PREFS } else { Join-Path $env:TEMP 'photonic-waveguide-solver\prefs' }
$cfg = if ($env:PHOTONIC_SOLVER_CONFIG) { $env:PHOTONIC_SOLVER_CONFIG } else { Join-Path $env:TEMP 'photonic-waveguide-solver\config' }
$tmp = if ($env:PHOTONIC_SOLVER_TMP) { $env:PHOTONIC_SOLVER_TMP } else { Join-Path $env:TEMP 'photonic-waveguide-solver\tmp' }
$batch = Join-Path $solverRoot 'bin\win64\comsolbatch.exe'

& $batch `
  -prefsdir $prefs `
  -configuration $cfg `
  -tmpdir $tmp `
  -inputfile 'C:\Path\To\ModelSource.class' `
  -outputfile 'C:\Path\To\OutputModel.mph' `
  -batchlog 'C:\Path\To\BatchLog.log'
```

## Helper Script

Use the bundled helper with explicit paths or environment variables:

```powershell
.\scripts\invoke-waveguide-java-batch.ps1 `
  -SolverRoot $env:PHOTONIC_SOLVER_ROOT `
  -JavaFile 'C:\Path\To\ModelSource.java' `
  -OutputFile 'C:\Path\To\OutputModel.mph' `
  -BatchLog 'C:\Path\To\BatchLog.log'
```

For a privacy-safe command preview:

```powershell
.\scripts\invoke-waveguide-java-batch.ps1 `
  -SolverRoot $env:PHOTONIC_SOLVER_ROOT `
  -JavaFile 'C:\Path\To\ModelSource.java' `
  -OutputFile 'C:\Path\To\OutputModel.mph' `
  -BatchLog 'C:\Path\To\BatchLog.log' `
  -DryRun
```

`-DryRun` hides the full plugin classpath by default. Add `-ShowFullPaths` only for local debugging, not for public logs.

## File I/O Guardrails

Inside solver-side Java, arbitrary local file reads can be restricted by security policy. Prefer:

- embedding small configs into generated Java source
- printing metrics to stdout
- saving `.mph` from inside the solver
- writing normal CSV/TXT outputs outside the solver orchestration layer

Do not depend on solver-side Java reading arbitrary text files unless that exact path has been validated.

## Local-Data Safety

Before publishing a repository, scan for:

- absolute paths from the author's machine
- user names and home directories
- license server names, tokens, or license files
- private paper PDFs or downloaded vendor documentation
- `.mph`, `.class`, `.log`, temporary sweep output, and solver cache files
- institution/project names that should not be public

Keep reusable workflow instructions public; keep local models, logs, credentials, and license details private unless they were intentionally cleared for release.

## Long-Run Discipline

- Start with a single-wavelength solve.
- Then run a small sweep.
- Then run dense sweeps only after model features and expressions are validated.
- If a foreground command times out, inspect the output directory, log file, and partial artifacts before declaring failure.
