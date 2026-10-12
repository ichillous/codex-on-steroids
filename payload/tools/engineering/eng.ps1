[CmdletBinding(PositionalBinding = $false)]
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$EngineeringArguments)
$ErrorActionPreference = 'Stop'
$engineeringPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $engineeringPython)) {
    throw 'Engineering Python is missing. Run .\tools\engineering\bootstrap.ps1 first.'
}
$engineeringWorkspace = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
& $engineeringPython -B -m workspace_engineering --workspace $engineeringWorkspace @EngineeringArguments
exit $LASTEXITCODE
