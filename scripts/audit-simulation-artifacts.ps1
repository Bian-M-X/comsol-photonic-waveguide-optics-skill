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
$textExtensions = @(
  ".md", ".txt", ".csv", ".java", ".py", ".ps1", ".psm1", ".json",
  ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".config",
  ".properties", ".xml", ".sh", ".cmd", ".bat", ".log", ".sql",
  ".pem", ".key", ".pub"
)
$sensitiveFileNamePattern = '^(?:\.env(?:\..+)?|credentials?(?:\..+)?|secrets?(?:\..+)?|tokens?(?:\..+)?|id_(?:rsa|dsa|ecdsa|ed25519)(?:\.pub)?)$'
$sensitivePatterns = [ordered]@{
  "license-setting" = '(?im)\b(?:LM_LICENSE_FILE|COMSOL_LICENSE)\b\s*[:=]'
  "license-file" = '(?im)(?:license\.dat|\S+\.lic)'
  "credential-token" = '(?im)^[\t ]*(?:export[\t ]+)?["'']?(?:api[_-]?key|access[_-]?token|auth[_-]?token|token|password|passwd|secret)["'']?[\t ]*[:=][\t ]*[^\s#;]+'
  "private-key" = '(?m)-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----'
  "user-profile-path" = '(?i)C:\\Users\\'
  "solver-install-path" = '(?i)(?:COMSOL64\\Multiphysics|D:\\COMSOL|D:\\cosmol)'
}
$excludedDirectoryNames = @(".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv")

function Test-LikelyTextFile {
  param([Parameter(Mandatory=$true)][System.IO.FileInfo]$File)

  if ($File.Length -eq 0) { return $true }

  $stream = $null
  try {
    $stream = [System.IO.File]::Open($File.FullName, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
    $sampleSize = [int][Math]::Min(4096, $File.Length)
    $buffer = New-Object byte[] $sampleSize
    $bytesRead = $stream.Read($buffer, 0, $sampleSize)

    if ($bytesRead -ge 2 -and (($buffer[0] -eq 0xFF -and $buffer[1] -eq 0xFE) -or ($buffer[0] -eq 0xFE -and $buffer[1] -eq 0xFF))) {
      return $true
    }

    $controlBytes = 0
    for ($index = 0; $index -lt $bytesRead; $index++) {
      $value = $buffer[$index]
      if ($value -eq 0) { return $false }
      if (($value -lt 32) -and ($value -notin @(9, 10, 12, 13))) {
        $controlBytes++
      }
    }
    return ($controlBytes -le [Math]::Max(1, [Math]::Floor($bytesRead * 0.02)))
  } catch {
    return $false
  } finally {
    if ($null -ne $stream) { $stream.Dispose() }
  }
}

Get-ChildItem -LiteralPath $root -Recurse -File -Force | ForEach-Object {
  $file = $_
  $relativePath = $file.FullName.Substring($root.TrimEnd('\', '/').Length).TrimStart('\', '/')
  $pathParts = @($relativePath -split '[\\/]')
  if (@($pathParts | Where-Object { $excludedDirectoryNames -contains $_ }).Count -gt 0) {
    return
  }

  if ($blockedExtensions -contains $file.Extension.ToLowerInvariant()) {
    $issues.Add("blocked-extension: $($file.FullName)")
  }
  if ($file.Length -gt $largeLimit) {
    $issues.Add("large-file>$LargeFileMB MB: $($file.FullName)")
  }
  $isSensitiveFileName = $file.Name -match $sensitiveFileNamePattern
  if ($isSensitiveFileName) {
    $issues.Add("sensitive-file-name: $($file.FullName)")
  }

  $isExtensionless = [string]::IsNullOrWhiteSpace($file.Extension)
  $isEnvironmentFile = $file.Name -match '^\.env(?:\..+)?$'
  $isTextCandidate = ($textExtensions -contains $file.Extension.ToLowerInvariant()) -or $isExtensionless -or $isEnvironmentFile
  if ($isTextCandidate -and $file.Name -ne "audit-simulation-artifacts.ps1" -and (Test-LikelyTextFile -File $file)) {
    $content = Get-Content -LiteralPath $file.FullName -Raw -ErrorAction SilentlyContinue
    if ($null -eq $content) { return }
    foreach ($entry in $sensitivePatterns.GetEnumerator()) {
      if ($content -match $entry.Value) {
        $issues.Add("possible-sensitive-pattern '$($entry.Key)': $($file.FullName)")
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
