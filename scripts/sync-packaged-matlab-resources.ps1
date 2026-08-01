[CmdletBinding()]
param(
    [switch]$Update
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$sourceRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $repositoryRoot 'matlab')
)
$targetRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $repositoryRoot 'src\photonic_workflow\data\matlab')
)
$controlledRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $repositoryRoot 'src\photonic_workflow\data')
)
if (-not $targetRoot.StartsWith(
    $controlledRoot + [System.IO.Path]::DirectorySeparatorChar,
    [System.StringComparison]::OrdinalIgnoreCase
)) {
    throw "Packaged MATLAB target escaped its controlled root: $targetRoot"
}
if ($Update) {
    New-Item -ItemType Directory -Force -Path $targetRoot | Out-Null
}

function Get-RelativeMatlabFiles {
    param([string]$Root)
    if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
        return @{}
    }
    $files = @{}
    $rootPrefix = $Root.TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    ) + [System.IO.Path]::DirectorySeparatorChar
    foreach ($file in Get-ChildItem -LiteralPath $Root -Recurse -File -Filter '*.m') {
        $absolute = [System.IO.Path]::GetFullPath($file.FullName)
        if (-not $absolute.StartsWith(
            $rootPrefix,
            [System.StringComparison]::OrdinalIgnoreCase
        )) {
            throw "MATLAB resource escaped its enumerated root: $absolute"
        }
        $relative = $absolute.Substring($rootPrefix.Length)
        $files[$relative] = $file.FullName
    }
    return $files
}

$sourceFiles = Get-RelativeMatlabFiles -Root $sourceRoot
$targetFiles = Get-RelativeMatlabFiles -Root $targetRoot
if ($Update) {
    foreach ($relative in $sourceFiles.Keys) {
        $destination = [System.IO.Path]::GetFullPath(
            (Join-Path $targetRoot $relative)
        )
        if (-not $destination.StartsWith(
            $targetRoot + [System.IO.Path]::DirectorySeparatorChar,
            [System.StringComparison]::OrdinalIgnoreCase
        )) {
            throw "Packaged MATLAB destination escaped its root: $destination"
        }
        New-Item -ItemType Directory -Force -Path (
            Split-Path -Parent $destination
        ) | Out-Null
        Copy-Item -LiteralPath $sourceFiles[$relative] -Destination $destination -Force
    }
    foreach ($relative in $targetFiles.Keys) {
        if (-not $sourceFiles.ContainsKey($relative)) {
            $obsolete = [System.IO.Path]::GetFullPath($targetFiles[$relative])
            if (-not $obsolete.StartsWith(
                $targetRoot + [System.IO.Path]::DirectorySeparatorChar,
                [System.StringComparison]::OrdinalIgnoreCase
            )) {
                throw "Refusing to remove MATLAB file outside packaged root: $obsolete"
            }
            Remove-Item -LiteralPath $obsolete -Force
        }
    }
    $targetFiles = Get-RelativeMatlabFiles -Root $targetRoot
}

$findings = [System.Collections.Generic.List[string]]::new()
foreach ($relative in $sourceFiles.Keys) {
    if (-not $targetFiles.ContainsKey($relative)) {
        $findings.Add("missing packaged MATLAB resource: $relative")
        continue
    }
    $sourceHash = (
        Get-FileHash -LiteralPath $sourceFiles[$relative] -Algorithm SHA256
    ).Hash
    $targetHash = (
        Get-FileHash -LiteralPath $targetFiles[$relative] -Algorithm SHA256
    ).Hash
    if ($sourceHash -ne $targetHash) {
        $findings.Add("packaged MATLAB resource differs: $relative")
    }
}
foreach ($relative in $targetFiles.Keys) {
    if (-not $sourceFiles.ContainsKey($relative)) {
        $findings.Add("unexpected packaged MATLAB resource: $relative")
    }
}

if ($findings.Count -gt 0) {
    $findings | ForEach-Object { Write-Error $_ }
    exit 1
}

$mode = if ($Update) { 'updated and verified' } else { 'verified' }
Write-Output "Packaged MATLAB resources $mode."
