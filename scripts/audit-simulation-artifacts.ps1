param(
  [Parameter(Mandatory=$true)]
  [string]$ProjectRoot,

  [int]$LargeFileMB = 25,
  [switch]$FailOnIssues
)

$ErrorActionPreference = "Stop"

$root = [System.IO.Path]::GetFullPath($ProjectRoot)
if (-not (Test-Path -LiteralPath $root)) {
  throw "Project root not found: $root"
}

$sourceRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\src"))
$previousPythonPath = $env:PYTHONPATH
try {
  $env:PYTHONPATH = if ([string]::IsNullOrWhiteSpace($previousPythonPath)) {
    $sourceRoot
  } else {
    $sourceRoot + [System.IO.Path]::PathSeparator + $previousPythonPath
  }
  $raw = @(
    & python -B -m photonic_workflow.cli audit artifacts $root `
      --large-file-mb $LargeFileMB --json 2>&1
  )
  $cliExitCode = $LASTEXITCODE
} finally {
  $env:PYTHONPATH = $previousPythonPath
}

if ($cliExitCode -ne 0) {
  $raw | ForEach-Object { Write-Host $_ }
  throw "photonic artifact audit failed with exit code $cliExitCode"
}

try {
  $payload = ($raw | Out-String) | ConvertFrom-Json -ErrorAction Stop
} catch {
  $raw | ForEach-Object { Write-Host $_ }
  throw "photonic artifact audit returned invalid JSON"
}

$findings = @($payload.data.findings)
if ($findings.Count -eq 0) {
  Write-Host "Artifact audit passed: no obvious blocked files or sensitive patterns."
  exit 0
}

Write-Host "Artifact audit findings:"
foreach ($finding in $findings | Sort-Object path, kind) {
  $fullPath = Join-Path $root ([string]$finding.path)
  $kind = [string]$finding.kind
  if ($kind.StartsWith("possible_sensitive_content:")) {
    $pattern = $kind.Substring("possible_sensitive_content:".Length).Replace("_", "-")
    Write-Host "- possible-sensitive-pattern '$pattern': $fullPath"
  } elseif ($kind -eq "blocked_extension") {
    Write-Host "- blocked-extension: $fullPath"
  } elseif ($kind -eq "sensitive_file_name") {
    Write-Host "- sensitive-file-name: $fullPath"
  } else {
    Write-Host "- $($kind.Replace("_", "-")): $fullPath"
  }
}

if ($FailOnIssues) {
  exit 1
}

exit 0
