[CmdletBinding()]
param([string]$Python = 'python', [switch]$SkipDoctor)
$ErrorActionPreference = 'Stop'
$engineeringEnvironment = Join-Path $PSScriptRoot '.venv'
$engineeringPython = Join-Path $engineeringEnvironment 'Scripts/python.exe'
& $Python -I -B (Join-Path $PSScriptRoot 'bootstrap_runtime.py') --kind engineering --root $PSScriptRoot
if ($LASTEXITCODE -ne 0) { throw 'Engineering environment preparation failed; inspect the preserved environment and reported recovery guidance.' }
if (-not $SkipDoctor) {
    $engineeringWorkspace = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
    & $engineeringPython -I -B -m workspace_engineering --workspace $engineeringWorkspace doctor
    if ($LASTEXITCODE -ne 0) {
        Write-Warning 'Dependencies installed. Doctor reported configuration or graph prerequisites; inspect its output before starting a job. A missing graph needs a publication or an explicitly authorized task-specific exception.'
    }
}
exit 0
