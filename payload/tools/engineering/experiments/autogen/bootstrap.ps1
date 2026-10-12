[CmdletBinding()]
param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
$studioEnvironment = Join-Path $PSScriptRoot '.venv-studio'
$studioPython = Join-Path $studioEnvironment 'Scripts/python.exe'
& $Python -I -B (Join-Path $PSScriptRoot '../../bootstrap_runtime.py') --kind studio --root $PSScriptRoot
if ($LASTEXITCODE -ne 0) { throw 'Studio environment preparation failed; inspect the preserved environment and reported recovery guidance.' }
Write-Output "Studio environment ready: $studioPython"
