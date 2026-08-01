param()

$ErrorActionPreference = "Stop"

function Assert-True {
  param(
    [Parameter(Mandatory=$true)][bool]$Condition,
    [Parameter(Mandatory=$true)][string]$Message
  )
  if (-not $Condition) { throw "Assertion failed: $Message" }
}

function Assert-Contains {
  param(
    [Parameter(Mandatory=$true)][string]$Text,
    [Parameter(Mandatory=$true)][string]$Expected,
    [Parameter(Mandatory=$true)][string]$Message
  )
  Assert-True -Condition $Text.Contains($Expected) -Message "$Message (missing '$Expected')"
}

function Invoke-ExpectedFailure {
  param(
    [Parameter(Mandatory=$true)][scriptblock]$Action,
    [Parameter(Mandatory=$true)][string]$ExpectedMessage
  )

  $failureMessage = $null
  try {
    & $Action
  } catch {
    $failureMessage = $_.Exception.Message
  }

  Assert-True -Condition (-not [string]::IsNullOrWhiteSpace($failureMessage)) -Message "Expected the action to fail."
  Assert-Contains -Text $failureMessage -Expected $ExpectedMessage -Message "Failure must report the native exit code."
}

$runner = Join-Path $PSScriptRoot "invoke-waveguide-java-batch.ps1"
$auditor = Join-Path $PSScriptRoot "audit-simulation-artifacts.ps1"
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("photonic-powershell-safety-" + [Guid]::NewGuid().ToString("N"))
$previousTrace = $env:PHOTONIC_TEST_TRACE

try {
  New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null

  $solverRoot = Join-Path $tempRoot "solver"
  $pluginDir = Join-Path $solverRoot "plugins"
  $sourceDir = Join-Path $tempRoot "source"
  $stubDir = Join-Path $tempRoot "stubs"
  New-Item -ItemType Directory -Force -Path $pluginDir, $sourceDir, $stubDir | Out-Null
  Set-Content -LiteralPath (Join-Path $pluginDir "dummy.jar") -Value "test fixture" -Encoding ASCII

  $javaFile = Join-Path $sourceDir "SafetyFixture.java"
  $classFile = [System.IO.Path]::ChangeExtension($javaFile, ".class")
  Set-Content -LiteralPath $javaFile -Value "public class SafetyFixture {}" -Encoding ASCII

  $javacStub = Join-Path $stubDir "fake-javac.cmd"
  $batchStub = Join-Path $stubDir "fake-batch.cmd"
  $traceFile = Join-Path $tempRoot "native-trace.txt"
  $env:PHOTONIC_TEST_TRACE = $traceFile

  $runnerArgs = @{
    JavaFile = $javaFile
    OutputFile = (Join-Path $tempRoot "output\model.mph")
    BatchLog = (Join-Path $tempRoot "output\batch.log")
    SolverRoot = $solverRoot
    PrefsDir = (Join-Path $tempRoot "runtime\prefs")
    ConfigDir = (Join-Path $tempRoot "runtime\config")
    TmpDir = (Join-Path $tempRoot "runtime\tmp")
    JavacExecutable = $javacStub
    BatchExecutable = $batchStub
  }

  # A failing compiler must remove any stale class and must not start batch.
  Set-Content -LiteralPath $classFile -Value "stale" -Encoding ASCII
  Set-Content -LiteralPath $javacStub -Encoding ASCII -Value @(
    "@echo off",
    "echo javac>>`"%PHOTONIC_TEST_TRACE%`"",
    "exit /b 17"
  )
  Set-Content -LiteralPath $batchStub -Encoding ASCII -Value @(
    "@echo off",
    "echo batch>>`"%PHOTONIC_TEST_TRACE%`"",
    "exit /b 0"
  )

  Invoke-ExpectedFailure -ExpectedMessage "exit code 17" -Action { & $runner @runnerArgs }
  $compileFailureTrace = @(Get-Content -LiteralPath $traceFile)
  Assert-True -Condition ($compileFailureTrace.Count -eq 1 -and $compileFailureTrace[0] -eq "javac") -Message "Batch ran after javac failed."
  Assert-True -Condition (-not (Test-Path -LiteralPath $classFile)) -Message "A stale class survived a failed compilation."

  # A successful fake compiler creates a fresh class; a batch failure must surface.
  Remove-Item -LiteralPath $traceFile -Force
  Set-Content -LiteralPath $javacStub -Encoding ASCII -Value @(
    "@echo off",
    "echo javac>>`"%PHOTONIC_TEST_TRACE%`"",
    "type nul > `"%~dpn4.class`"",
    "exit /b 0"
  )
  Set-Content -LiteralPath $batchStub -Encoding ASCII -Value @(
    "@echo off",
    "echo batch>>`"%PHOTONIC_TEST_TRACE%`"",
    "exit /b 23"
  )

  Invoke-ExpectedFailure -ExpectedMessage "exit code 23" -Action { & $runner @runnerArgs }
  $batchFailureTrace = @(Get-Content -LiteralPath $traceFile)
  Assert-True -Condition (($batchFailureTrace -join ",") -eq "javac,batch") -Message "Expected javac and batch to run exactly once."

  # Exit code zero is insufficient when the expected solver artifacts were
  # not created by this invocation.
  Remove-Item -LiteralPath $traceFile -Force
  Set-Content -LiteralPath $batchStub -Encoding ASCII -Value @(
    "@echo off",
    "echo batch>>`"%PHOTONIC_TEST_TRACE%`"",
    "exit /b 0"
  )
  Invoke-ExpectedFailure -ExpectedMessage "did not create the expected output model" -Action { & $runner @runnerArgs }

  # Dry-run must not execute either native command or delete an existing class.
  Remove-Item -LiteralPath $traceFile -Force
  Set-Content -LiteralPath $classFile -Value "dry-run-sentinel" -Encoding ASCII
  & $runner @runnerArgs -DryRun *> $null
  Assert-True -Condition (-not (Test-Path -LiteralPath $traceFile)) -Message "Dry-run executed a native command."
  Assert-True -Condition ((Get-Content -LiteralPath $classFile -Raw).Trim() -eq "dry-run-sentinel") -Message "Dry-run modified the class file."

  # The audit must see hidden .env files and extensionless configuration, but
  # it must avoid interpreting a NUL-containing binary blob as text.
  $auditRoot = Join-Path $tempRoot "audit-root"
  New-Item -ItemType Directory -Force -Path $auditRoot | Out-Null
  $environmentFile = Join-Path $auditRoot ".env"
  $tokenName = "TO" + "KEN"
  [System.IO.File]::WriteAllText($environmentFile, $tokenName + "=fixture-value")
  [System.IO.File]::SetAttributes($environmentFile, [System.IO.File]::GetAttributes($environmentFile) -bor [System.IO.FileAttributes]::Hidden)

  $configFile = Join-Path $auditRoot "config"
  $passwordName = "PASS" + "WORD"
  [System.IO.File]::WriteAllText($configFile, $passwordName + ": fixture-value")

  $binaryFile = Join-Path $auditRoot "binaryblob"
  [System.IO.File]::WriteAllBytes($binaryFile, [byte[]](0, 84, 79, 75, 69, 78, 61, 120))

  $hostExecutable = (Get-Process -Id $PID).Path
  $auditOutput = @(& $hostExecutable -NoProfile -ExecutionPolicy Bypass -File $auditor -ProjectRoot $auditRoot -FailOnIssues 2>&1)
  $auditExitCode = $LASTEXITCODE
  $auditText = $auditOutput | Out-String

  Assert-True -Condition ($auditExitCode -eq 1) -Message "-FailOnIssues did not return a failing process exit code."
  Assert-Contains -Text $auditText -Expected ".env" -Message "The hidden .env file was not reported."
  Assert-Contains -Text $auditText -Expected "credential-token" -Message "Credential content was not detected."
  Assert-Contains -Text $auditText -Expected "config" -Message "The extensionless config file was not scanned."
  Assert-True -Condition (-not $auditText.Contains("binaryblob")) -Message "The obvious binary file was read as text."

  Write-Host "PowerShell safety regression tests passed (javac gate, batch gate, dry-run, hidden/config audit, binary skip)."
} finally {
  $env:PHOTONIC_TEST_TRACE = $previousTrace
  if (Test-Path -LiteralPath $tempRoot) {
    Remove-Item -LiteralPath $tempRoot -Recurse -Force
  }
}

# PowerShell 7 otherwise propagates the expected child audit failure stored in
# $LASTEXITCODE even though every regression assertion above passed.
exit 0
