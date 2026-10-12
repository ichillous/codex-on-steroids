[CmdletBinding()]
param(
    [string]$Python = 'python',
    [string]$GraphifyPython,
    [string[]]$Scope = @(),
    [string]$Query
)
$ErrorActionPreference = 'Stop'
$graphifyWorkspace = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$graphifyArguments = @('-I', '-B', (Join-Path $PSScriptRoot 'graphify_setup.py'), '--project-root', $graphifyWorkspace)
if ($GraphifyPython) { $graphifyArguments += @('--python', $GraphifyPython) }
foreach ($sourceScope in $Scope) { $graphifyArguments += @('--scope', $sourceScope) }
if ($Query) { $graphifyArguments += @('--query', $Query) }
& $Python @graphifyArguments
exit $LASTEXITCODE
