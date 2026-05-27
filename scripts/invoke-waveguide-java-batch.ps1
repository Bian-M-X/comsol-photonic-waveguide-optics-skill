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
  [switch]$DryRun,
  [switch]$ShowFullPaths
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($SolverRoot)) {
  throw "Set -SolverRoot or PHOTONIC_SOLVER_ROOT to your licensed solver installation root."
}

$runtimeRoot = Join-Path ([System.IO.Path]::GetTempPath()) "photonic-waveguide-solver"
if ([string]::IsNullOrWhiteSpace($PrefsDir)) { $PrefsDir = Join-Path $runtimeRoot "prefs" }
if ([string]::IsNullOrWhiteSpace($ConfigDir)) { $ConfigDir = Join-Path $runtimeRoot "config" }
if ([string]::IsNullOrWhiteSpace($TmpDir)) { $TmpDir = Join-Path $runtimeRoot "tmp" }

$javac = Join-Path $SolverRoot "java\win64\jre\bin\javac.exe"
$batch = Join-Path $SolverRoot "bin\win64\comsolbatch.exe"
$plugins = Join-Path $SolverRoot "plugins"
$cp = ""
if (Test-Path -LiteralPath $plugins) {
  $cp = (Get-ChildItem -LiteralPath $plugins -Filter "*.jar" | ForEach-Object { $_.FullName }) -join ";"
}
$classFile = [System.IO.Path]::ChangeExtension($JavaFile, ".class")

$compileArgs = @("-proc:none", "-cp", $cp, $JavaFile)
$batchArgs = @(
  "-prefsdir", $PrefsDir,
  "-configuration", $ConfigDir,
  "-tmpdir", $TmpDir,
  "-inputfile", $classFile,
  "-outputfile", $OutputFile,
  "-batchlog", $BatchLog
)

if ($DryRun) {
  $pluginCount = 0
  if (Test-Path -LiteralPath $plugins) {
    $pluginCount = @(Get-ChildItem -LiteralPath $plugins -Filter "*.jar").Count
  }
  Write-Host "Compile:"
  if ($ShowFullPaths) {
    Write-Host "`"$javac`" $($compileArgs -join ' ')"
  } else {
    Write-Host "javac -proc:none -cp <plugin jars: $pluginCount> `"$JavaFile`""
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
if (-not (Test-Path -LiteralPath $javac)) { throw "javac not found: $javac" }
if (-not (Test-Path -LiteralPath $batch)) { throw "batch executable not found: $batch" }
if ([string]::IsNullOrWhiteSpace($cp)) { throw "No plugin jars found under: $plugins" }

New-Item -ItemType Directory -Force -Path $PrefsDir, $ConfigDir, $TmpDir | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $OutputFile), (Split-Path -Parent $BatchLog) | Out-Null

& $javac @compileArgs
& $batch @batchArgs
