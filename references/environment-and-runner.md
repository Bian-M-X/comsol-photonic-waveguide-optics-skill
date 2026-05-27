# Environment and Batch Runner

Use this reference when a task needs local solver-path setup, Java API automation, batch execution, runtime-directory control, or privacy-safe command previews.

## Core Principle

The skill must not hard-code the author's local installation path. Each user supplies their own licensed solver root through either `-SolverRoot` or `PHOTONIC_SOLVER_ROOT`.

Expected Windows relative files under the solver root:

```text
bin\win64\comsolbatch.exe
java\win64\jre\bin\javac.exe
plugins\*.jar
```

These are compatibility references only. This repository does not include solver binaries, plugins, license files, or proprietary documentation.

## Configure A Local Solver Root

For the current PowerShell session:

```powershell
$env:PHOTONIC_SOLVER_ROOT = 'C:\Path\To\LicensedSolverRoot'
```

For a persistent user-level variable:

```powershell
setx PHOTONIC_SOLVER_ROOT "C:\Path\To\LicensedSolverRoot"
```

Optional runtime directories:

```powershell
$env:PHOTONIC_SOLVER_PREFS = Join-Path $env:TEMP 'photonic-waveguide-solver\prefs'
$env:PHOTONIC_SOLVER_CONFIG = Join-Path $env:TEMP 'photonic-waveguide-solver\config'
$env:PHOTONIC_SOLVER_TMP = Join-Path $env:TEMP 'photonic-waveguide-solver\tmp'
```

For parallel sweeps, use separate runtime directories per worker:

```powershell
$worker = 'worker-001'
$env:PHOTONIC_SOLVER_PREFS = Join-Path $env:TEMP "photonic-waveguide-solver\$worker\prefs"
$env:PHOTONIC_SOLVER_CONFIG = Join-Path $env:TEMP "photonic-waveguide-solver\$worker\config"
$env:PHOTONIC_SOLVER_TMP = Join-Path $env:TEMP "photonic-waveguide-solver\$worker\tmp"
```

## Verify The Installation

Run these checks after setting `PHOTONIC_SOLVER_ROOT`:

```powershell
$root = $env:PHOTONIC_SOLVER_ROOT
Test-Path (Join-Path $root 'bin\win64\comsolbatch.exe')
Test-Path (Join-Path $root 'java\win64\jre\bin\javac.exe')
Test-Path (Join-Path $root 'plugins')
```

Expected result: all three commands return `True`.

If any check returns `False`, ask the user to provide the correct solver root. Do not guess by publishing local machine paths. If searching the machine is necessary, keep results local and do not commit them.

## Preferred Automation Route

Use Java API plus batch execution:

1. Generate or patch a Java source file.
2. Compile it with the solver-bundled `javac.exe`.
3. Run the compiled `.class` with `comsolbatch.exe`.
4. Save the `.mph` model inside the solver-side Java run.
5. Print key metrics to stdout or write CSV/TXT outputs.
6. Use Python or PowerShell outside the solver for aggregation, plotting, and reporting.

Avoid these as first choices:

- `mphserver`, unless the user explicitly needs an interactive service.
- Running standalone Java outside the solver batch runtime.
- Large external config reads inside solver-side Java. Prefer generated source or small embedded parameters.

## Compile Pattern

```powershell
$solverRoot = $env:PHOTONIC_SOLVER_ROOT
if (-not $solverRoot) { throw 'Set PHOTONIC_SOLVER_ROOT first.' }

$plugins = Join-Path $solverRoot 'plugins'
$javac = Join-Path $solverRoot 'java\win64\jre\bin\javac.exe'
$cp = (Get-ChildItem -LiteralPath $plugins -Filter '*.jar' | ForEach-Object { $_.FullName }) -join ';'

& $javac -proc:none -cp $cp 'C:\Path\To\ModelSource.java'
```

`-proc:none` avoids annotation-processing noise and should be kept unless there is a clear reason to remove it.

## Batch Pattern

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

Use the bundled wrapper for repeatable compile-and-run:

```powershell
.\scripts\invoke-waveguide-java-batch.ps1 `
  -SolverRoot $env:PHOTONIC_SOLVER_ROOT `
  -JavaFile 'C:\Path\To\ModelSource.java' `
  -OutputFile 'C:\Path\To\OutputModel.mph' `
  -BatchLog 'C:\Path\To\BatchLog.log'
```

Privacy-safe preview:

```powershell
.\scripts\invoke-waveguide-java-batch.ps1 `
  -SolverRoot $env:PHOTONIC_SOLVER_ROOT `
  -JavaFile 'C:\Path\To\ModelSource.java' `
  -OutputFile 'C:\Path\To\OutputModel.mph' `
  -BatchLog 'C:\Path\To\BatchLog.log' `
  -DryRun
```

`-DryRun` hides the full plugin classpath by default. Use `-ShowFullPaths` only in private local debugging.

## Long-Run Discipline

- Start with a single wavelength.
- Then run a small wavelength sweep.
- Then run dense sweeps only after geometry, materials, ports, expressions, and datasets are validated.
- If a command times out, inspect output files and the batch log before declaring failure.
- Save summaries for restartability: candidate id, parameters, metrics, output model path, log path, and status.

## Failure Triage

| Symptom | Likely cause | First action |
|---|---|---|
| `Set PHOTONIC_SOLVER_ROOT first` | no solver root configured | set env var or pass `-SolverRoot` |
| `javac not found` | wrong solver root or different install layout | verify `java\win64\jre\bin\javac.exe` |
| `batch executable not found` | wrong solver root or missing batch tool | verify `bin\win64\comsolbatch.exe` |
| no plugin jars | wrong solver root | verify `plugins` directory |
| solver-side file read fails | Java security or path policy | embed small config in source or write outputs externally |
| parallel jobs corrupt runtime state | shared prefs/config/tmp | use per-worker runtime dirs |
| public logs expose local machine data | full classpath or absolute paths printed | use `-DryRun` without `-ShowFullPaths` |

## Files That Should Not Be Published By Default

- `.mph`
- `.class`
- `.log`
- solver cache directories
- license files or license-server details
- local path manifests
- private paper PDFs or vendor documentation
- generated plots/data containing confidential project names

Keep reusable workflow instructions public; keep local models, logs, credentials, and license details private unless explicitly cleared for release.
