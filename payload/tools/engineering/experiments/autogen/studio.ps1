[CmdletBinding()]
param([ValidateRange(1024,65535)][int]$Port = 8081)
$ErrorActionPreference = 'Stop'
$studioPython = Join-Path $PSScriptRoot '.venv-studio/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $studioPython)) {
    throw 'Run tools/engineering/experiments/autogen/bootstrap.ps1 first.'
}
& $studioPython (Join-Path $PSScriptRoot 'launch_studio.py') --port $Port
exit $LASTEXITCODE
