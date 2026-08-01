param(
  [Parameter(Mandatory=$true)]
  [string]$ProjectRoot,

  [string]$DeviceFamily = "waveguide",

  [switch]$InitGit,
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$root = [System.IO.Path]::GetFullPath($ProjectRoot)
$sourceRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\src"))
$previousPythonPath = $env:PYTHONPATH
try {
  $env:PYTHONPATH = if ([string]::IsNullOrWhiteSpace($previousPythonPath)) {
    $sourceRoot
  } else {
    $sourceRoot + [System.IO.Path]::PathSeparator + $previousPythonPath
  }
  $arguments = @(
    "-B", "-m", "photonic_workflow.cli", "init", $root,
    "--device-family", $DeviceFamily
  )
  if ($DryRun) {
    $arguments += "--dry-run"
  }
  & python @arguments
  $cliExitCode = $LASTEXITCODE
  if ($cliExitCode -ne 0) {
    throw "photonic init failed with exit code $cliExitCode"
  }
} finally {
  $env:PYTHONPATH = $previousPythonPath
}

if ($InitGit) {
  if ($DryRun) {
    Write-Host "git init"
  } elseif (-not (Test-Path -LiteralPath (Join-Path $root ".git"))) {
    git -C $root init | Out-Null
    if ($LASTEXITCODE -ne 0) {
      throw "git init failed with exit code $LASTEXITCODE"
    }
  }
}

if (-not $DryRun) {
  Write-Host "Initialized photonic project scaffold: $root"
}
