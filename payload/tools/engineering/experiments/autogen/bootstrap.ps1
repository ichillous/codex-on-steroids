[CmdletBinding()]
param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
$studioEnvironment = Join-Path $PSScriptRoot '.venv-studio'
$studioPython = Join-Path $studioEnvironment 'Scripts/python.exe'
if (-not (Test-Path -LiteralPath $studioPython)) {
    & $Python -m venv $studioEnvironment
    if ($LASTEXITCODE -ne 0) { throw 'Studio virtual environment creation failed.' }
}
$studioRequirements = Join-Path $PSScriptRoot 'requirements.lock'
if (-not (Test-Path -LiteralPath $studioRequirements)) {
    $studioRequirements = Join-Path $PSScriptRoot 'requirements.txt'
}
& $studioPython -m pip install --requirement $studioRequirements
if ($LASTEXITCODE -ne 0) { throw 'Studio dependency installation failed.' }
& $studioPython -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Studio dependency verification failed.' }
Write-Output "Studio environment ready: $studioPython"
