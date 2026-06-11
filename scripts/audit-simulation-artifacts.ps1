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

$issues = New-Object System.Collections.Generic.List[string]
$largeLimit = $LargeFileMB * 1MB
$blockedExtensions = @(".mph", ".class", ".mphbin", ".mphstatus")
$textExtensions = @(".md", ".txt", ".csv", ".java", ".py", ".ps1", ".json", ".yaml", ".yml")
$sensitivePatterns = @(
  "LM_LICENSE_FILE",
  "COMSOL_LICENSE",
  "license.dat",
  ".lic",
  "token=",
  "password=",
  "COMSOL64\\Multiphysics",
  "C:\\Users\\",
  "D:\\COMSOL",
  "D:\\cosmol"
)

Get-ChildItem -LiteralPath $root -Recurse -File | ForEach-Object {
  $file = $_
  if ($blockedExtensions -contains $file.Extension.ToLowerInvariant()) {
    $issues.Add("blocked-extension: $($file.FullName)")
  }
  if ($file.Length -gt $largeLimit) {
    $issues.Add("large-file>$LargeFileMB MB: $($file.FullName)")
  }
  if (($textExtensions -contains $file.Extension.ToLowerInvariant()) -and $file.Name -ne "audit-simulation-artifacts.ps1") {
    $content = Get-Content -LiteralPath $file.FullName -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
    foreach ($pattern in $sensitivePatterns) {
      if ($content -like "*$pattern*") {
        $issues.Add("possible-sensitive-pattern '$pattern': $($file.FullName)")
        break
      }
    }
  }
}

if ($issues.Count -eq 0) {
  Write-Host "Artifact audit passed: no obvious blocked files or sensitive patterns."
  exit 0
}

Write-Host "Artifact audit findings:"
$issues | Sort-Object | ForEach-Object { Write-Host "- $_" }

if ($FailOnIssues) {
  exit 1
}
