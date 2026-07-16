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
$normalizedFamily = $DeviceFamily.Trim().ToLowerInvariant()
$useMziTemplate = $normalizedFamily -in @("mzi", "balanced-mzi", "interferometer")
$assembly = Join-Path $root "circuits\assembly.json"
$assemblyTool = Join-Path $root "scripts\photonic_assembly.py"
$requirementsFile = Join-Path $root "requirements.txt"
$assemblyTemplate = if ($useMziTemplate) {
  Join-Path $templateRoot "mzi-4port\circuits\assembly.json"
} else {
  Join-Path $templateRoot "assembly.json"
}
$sparameterTemplates = if ($useMziTemplate) {
  @(
    @{ Source = (Join-Path $templateRoot "mzi-4port\components\sparameters\directional_coupler.csv"); Name = "directional_coupler.csv" },
    @{ Source = (Join-Path $templateRoot "mzi-4port\components\sparameters\arm.csv"); Name = "arm.csv" }
  )
} else {
  @(@{ Source = (Join-Path $templateRoot "waveguide.csv"); Name = "waveguide.csv" })
}
if ((Test-Path -LiteralPath $assemblyTemplate) -and -not (Test-Path -LiteralPath $assembly)) {
  Copy-Item -LiteralPath $assemblyTemplate -Destination $assembly
}
foreach ($template in $sparameterTemplates) {
  $destination = Join-Path $root ("components\sparameters\" + $template.Name)
  if ((Test-Path -LiteralPath $template.Source) -and -not (Test-Path -LiteralPath $destination)) {
    Copy-Item -LiteralPath $template.Source -Destination $destination
  }
}
if (-not (Test-Path -LiteralPath $assemblyTool)) {
  Copy-Item -LiteralPath (Join-Path $PSScriptRoot "photonic_assembly.py") -Destination $assemblyTool
}
if (-not (Test-Path -LiteralPath $requirementsFile)) {
  Copy-Item -LiteralPath (Join-Path $PSScriptRoot "..\requirements.txt") -Destination $requirementsFile
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
