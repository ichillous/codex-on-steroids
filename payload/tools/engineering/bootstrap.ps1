[CmdletBinding()]
param([string]$Python = 'python', [switch]$SkipDoctor)
$ErrorActionPreference = 'Stop'
$engineeringEnvironment = Join-Path $PSScriptRoot '.venv'
$engineeringPython = Join-Path $engineeringEnvironment 'Scripts/python.exe'
if (-not (Test-Path -LiteralPath $engineeringPython)) {
    & $Python -m venv $engineeringEnvironment
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the dedicated engineering environment.' }
}
& $engineeringPython -m pip install --requirement (Join-Path $PSScriptRoot 'requirements.lock')
if ($LASTEXITCODE -ne 0) { throw 'Locked engineering dependency installation failed.' }
& $engineeringPython -m pip install --no-deps --editable $PSScriptRoot
if ($LASTEXITCODE -ne 0) { throw 'Engineering package installation failed.' }
if (-not $SkipDoctor) {
    $engineeringWorkspace = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
    & $engineeringPython -B -m workspace_engineering --workspace $engineeringWorkspace doctor
    if ($LASTEXITCODE -ne 0) {
        Write-Warning 'Dependencies installed. Doctor reported configuration or graph prerequisites; inspect its output before starting a job. A missing graph needs a publication or an explicitly authorized task-specific exception.'
    }
}
exit 0
