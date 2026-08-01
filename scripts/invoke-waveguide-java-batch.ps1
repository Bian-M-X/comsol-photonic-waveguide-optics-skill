param(
  [Parameter(Mandatory=$true)]
  [string]$JavaFile,

  [Parameter(Mandatory=$true)]
  [string]$OutputFile,

  [Parameter(Mandatory=$true)]
  [string]$BatchLog,

  [string]$SolverRoot = $env:PHOTONIC_SOLVER_ROOT,
  [string]$PrefsDir = $env:PHOTONIC_SOLVER_PREFS,
  [string]$ConfigDir = $env:PHOTONIC_SOLVER_CONFIG,
  [string]$TmpDir = $env:PHOTONIC_SOLVER_TMP,
  [string]$CompilerExecutable,
  # Backward-compatible alias retained for callers of the pre-0.4 wrapper.
  [string]$JavacExecutable,
  [string]$BatchExecutable,
  [switch]$DryRun,
  [switch]$ShowFullPaths
)

$ErrorActionPreference = "Stop"

function Get-FileSignature {
  param([Parameter(Mandatory=$true)][string]$Path)
  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
  $item = Get-Item -LiteralPath $Path
  return "$($item.Length):$($item.LastWriteTimeUtc.Ticks)"
}

if ([string]::IsNullOrWhiteSpace($SolverRoot)) {
  throw "Set -SolverRoot or PHOTONIC_SOLVER_ROOT to your licensed solver installation root."
}

$runtimeRoot = Join-Path ([System.IO.Path]::GetTempPath()) "photonic-waveguide-solver"
if ([string]::IsNullOrWhiteSpace($PrefsDir)) { $PrefsDir = Join-Path $runtimeRoot "prefs" }
if ([string]::IsNullOrWhiteSpace($ConfigDir)) { $ConfigDir = Join-Path $runtimeRoot "config" }
if ([string]::IsNullOrWhiteSpace($TmpDir)) { $TmpDir = Join-Path $runtimeRoot "tmp" }

$compiler = if (-not [string]::IsNullOrWhiteSpace($CompilerExecutable)) {
  $CompilerExecutable
} elseif (-not [string]::IsNullOrWhiteSpace($JavacExecutable)) {
  $JavacExecutable
} else {
  Join-Path $SolverRoot "bin\win64\comsolcompile.exe"
}
$batch = if ([string]::IsNullOrWhiteSpace($BatchExecutable)) {
  Join-Path $SolverRoot "bin\win64\comsolbatch.exe"
} else {
  $BatchExecutable
}
$classFile = [System.IO.Path]::ChangeExtension($JavaFile, ".class")

$compileArgs = @($JavaFile)
$batchArgs = @(
  "-prefsdir", $PrefsDir,
  "-configuration", $ConfigDir,
  "-tmpdir", $TmpDir,
  "-inputfile", $classFile,
  "-outputfile", $OutputFile,
  "-batchlog", $BatchLog
)
$outputDirectory = Split-Path -Parent $OutputFile
$outputStem = [System.IO.Path]::GetFileNameWithoutExtension($OutputFile)

if ($DryRun) {
  Write-Host "Compile:"
  if ($ShowFullPaths) {
    Write-Host "`"$compiler`" $($compileArgs -join ' ')"
  } else {
    Write-Host "comsolcompile `"$JavaFile`""
  }
  Write-Host "Batch:"
  if ($ShowFullPaths) {
    Write-Host "`"$batch`" $($batchArgs -join ' ')"
  } else {
    Write-Host "batch-executable -prefsdir <runtime prefs> -configuration <runtime config> -tmpdir <runtime tmp> -inputfile `"$classFile`" -outputfile `"$OutputFile`" -batchlog `"$BatchLog`""
  }
  return
}

if (-not (Test-Path -LiteralPath $JavaFile)) { throw "Java file not found: $JavaFile" }
if (-not (Test-Path -LiteralPath $compiler)) { throw "COMSOL compiler not found: $compiler" }
if (-not (Test-Path -LiteralPath $batch)) { throw "batch executable not found: $batch" }

New-Item -ItemType Directory -Force -Path $PrefsDir, $ConfigDir, $TmpDir | Out-Null
New-Item -ItemType Directory -Force -Path $outputDirectory, (Split-Path -Parent $BatchLog) | Out-Null

# Never allow a failed or incomplete compilation to leave a stale class as the
# batch input. comsolcompile should recreate this file during this invocation.
if (Test-Path -LiteralPath $classFile) {
  Remove-Item -LiteralPath $classFile -Force
}

& $compiler @compileArgs
$compilerExitCode = $LASTEXITCODE
if ($compilerExitCode -ne 0) {
  throw "COMSOL compiler failed with exit code $compilerExitCode. Batch execution was not started."
}
if (-not (Test-Path -LiteralPath $classFile -PathType Leaf)) {
  throw "COMSOL compiler reported success but did not create the expected class file: $classFile. Batch execution was not started."
}

$beforeNamedOutputs = @{}
Get-ChildItem -LiteralPath $outputDirectory -Filter "$outputStem`_*.mph" -File -ErrorAction SilentlyContinue | ForEach-Object {
  $beforeNamedOutputs[$_.FullName] = "$($_.Length):$($_.LastWriteTimeUtc.Ticks)"
}
$beforeOutputSignature = Get-FileSignature -Path $OutputFile
$beforeLogSignature = Get-FileSignature -Path $BatchLog

& $batch @batchArgs
$batchExitCode = $LASTEXITCODE
if ($batchExitCode -ne 0) {
  throw "Batch solver failed with exit code $batchExitCode."
}
$afterOutputSignature = Get-FileSignature -Path $OutputFile
$exactOutputIsFresh = (
  $null -ne $afterOutputSignature -and
  $afterOutputSignature -ne $beforeOutputSignature
)
if (-not $exactOutputIsFresh) {
  $freshNamedOutputs = @(
    Get-ChildItem -LiteralPath $outputDirectory -Filter "$outputStem`_*.mph" -File -ErrorAction SilentlyContinue |
      Where-Object {
        $signature = "$($_.Length):$($_.LastWriteTimeUtc.Ticks)"
        -not $beforeNamedOutputs.ContainsKey($_.FullName) -or $beforeNamedOutputs[$_.FullName] -ne $signature
      }
  )
  if ($freshNamedOutputs.Count -eq 1) {
    Move-Item -LiteralPath $freshNamedOutputs[0].FullName -Destination $OutputFile -Force
  } elseif ($freshNamedOutputs.Count -gt 1) {
    throw "Batch solver created multiple named model outputs; cannot normalize one output safely: $($freshNamedOutputs.FullName -join ', ')"
  } else {
    throw "Batch solver reported success but did not create the expected output model: $OutputFile"
  }
}
if ((Get-FileSignature -Path $BatchLog) -eq $beforeLogSignature) {
  throw "Batch solver reported success but did not create the expected batch log: $BatchLog"
}
