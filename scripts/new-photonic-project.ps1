param(
  [Parameter(Mandatory=$true)]
  [string]$ProjectRoot,

  [string]$DeviceFamily = "waveguide",

  [switch]$InitGit,
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$root = [System.IO.Path]::GetFullPath($ProjectRoot)
$folders = @(
  "requirements",
  "components\contracts",
  "components\sparameters",
  "circuits",
  "layout",
  "models\java",
  "models\mph",
  "runs",
  "scripts",
  "data\raw",
  "data\processed",
  "verification",
  "reports",
  "handoff"
)

if ($DryRun) {
  Write-Host "Project root: $root"
  foreach ($folder in $folders) { Write-Host "mkdir $folder" }
  if ($InitGit) { Write-Host "git init" }
  return
}

New-Item -ItemType Directory -Force -Path $root | Out-Null
foreach ($folder in $folders) {
  New-Item -ItemType Directory -Force -Path (Join-Path $root $folder) | Out-Null
}

$projectMd = Join-Path $root "PROJECT.md"
if (-not (Test-Path -LiteralPath $projectMd)) {
  @(
    "# Photonic Simulation Project",
    "",
    "Device family: $DeviceFamily",
    "",
    "## Objective",
    "",
    "## Assumptions",
    "",
    "## Validation Targets",
    "",
    "## Current Baseline",
    ""
  ) | Set-Content -LiteralPath $projectMd -Encoding UTF8
}

$handoff = Join-Path $root "handoff\latest.md"
if (-not (Test-Path -LiteralPath $handoff)) {
  @(
    "# Latest Handoff",
    "",
    "Status: initialized",
    "",
    "Next action:",
    ""
  ) | Set-Content -LiteralPath $handoff -Encoding UTF8
}

$templateRoot = Join-Path $PSScriptRoot "..\assets\templates\hierarchical-device"
$assembly = Join-Path $root "circuits\assembly.json"
$sampleSparams = Join-Path $root "components\sparameters\waveguide.csv"
$assemblyTool = Join-Path $root "scripts\photonic_assembly.py"
if ((Test-Path -LiteralPath $templateRoot) -and -not (Test-Path -LiteralPath $assembly)) {
  Copy-Item -LiteralPath (Join-Path $templateRoot "assembly.json") -Destination $assembly
}
if ((Test-Path -LiteralPath $templateRoot) -and -not (Test-Path -LiteralPath $sampleSparams)) {
  Copy-Item -LiteralPath (Join-Path $templateRoot "waveguide.csv") -Destination $sampleSparams
}
if (-not (Test-Path -LiteralPath $assemblyTool)) {
  Copy-Item -LiteralPath (Join-Path $PSScriptRoot "photonic_assembly.py") -Destination $assemblyTool
}

$gitignore = Join-Path $root ".gitignore"
if (-not (Test-Path -LiteralPath $gitignore)) {
  @(
    "*.mph",
    "*.class",
    "*.log",
    "*.mphbin",
    "models/mph/",
    "runs/**/runtime/",
    "data/raw/",
    "__pycache__/",
    "*.pyc"
  ) | Set-Content -LiteralPath $gitignore -Encoding UTF8
}

if ($InitGit -and -not (Test-Path -LiteralPath (Join-Path $root ".git"))) {
  git -C $root init | Out-Null
}

Write-Host "Initialized photonic project scaffold: $root"
