[CmdletBinding()]
param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$Python = 'python',
    [string]$Codex = 'codex',
    [string]$GraphifyPython,
    [string[]]$GraphifyScope = @(),
    [ValidateSet('idea-research', 'blueprint-first')][string[]]$Modules = @(),
    [string]$Model,
    [ValidateRange(30,7200)][int]$TimeoutSeconds = 600,
    [switch]$Static,
    [switch]$PlanOnly,
    [switch]$SkipDependencies,
    [string]$Rollback
)
$ErrorActionPreference = 'Stop'
& $Python -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 or newer is required.' }
$setupArguments = @('-B', (Join-Path $PSScriptRoot 'scripts/install.py'), '--project-root', $ProjectRoot, '--codex', $Codex, '--timeout', "$TimeoutSeconds")
if ($Model) { $setupArguments += @('--model', $Model) }
foreach ($moduleName in $Modules) { $setupArguments += @('--module', $moduleName) }
if ($Static) { $setupArguments += '--static' }
if ($PlanOnly) { $setupArguments += '--plan-only' }
if ($Rollback) { $setupArguments += @('--rollback', $Rollback) }
& $Python @setupArguments
if ($LASTEXITCODE -ne 0) { throw 'Setup analysis or installation failed. Review the error and saved setup evidence; existing conflicting files were preserved.' }
if ($PlanOnly -or $Rollback) { exit 0 }
if ($SkipDependencies) {
    Write-Output 'Configuration and project skills installed. Dependencies and Graphify preparation were explicitly skipped; run tools/engineering/graphify.ps1 and the runner/Studio bootstrap commands before use.'
    exit 0
}
$graphifyArguments = @('-I', '-B', (Join-Path $ProjectRoot 'tools/engineering/graphify_setup.py'), '--project-root', $ProjectRoot)
if ($GraphifyPython) { $graphifyArguments += @('--python', $GraphifyPython) }
foreach ($sourceScope in $GraphifyScope) { $graphifyArguments += @('--scope', $sourceScope) }
& $Python @graphifyArguments
if ($LASTEXITCODE -ne 0) { throw 'Graphify preparation failed. Configuration is installed and existing publications were preserved. Review the error; select -GraphifyScope for a large project or repair an invalid publication, then rerun.' }
$engineeringBootstrap = Join-Path $ProjectRoot 'tools/engineering/bootstrap.ps1'
$studioBootstrap = Join-Path $ProjectRoot 'tools/engineering/experiments/autogen/bootstrap.ps1'
# Run scripts in child PowerShell processes: their exit statements must not
# terminate this setup before both isolated environments have been installed.
& powershell.exe -NoProfile -File $engineeringBootstrap -Python $Python -SkipDoctor
if ($LASTEXITCODE -ne 0) { throw 'Engineering environment installation failed. Configuration is installed; rerun setup to retry dependencies.' }
& powershell.exe -NoProfile -File $studioBootstrap -Python $Python
if ($LASTEXITCODE -ne 0) { throw 'AutoGen Studio environment installation failed. Rerun setup to retry dependencies.' }
Write-Output 'Graphify is available and its publication was consulted. Engineering and Studio environments are installed. Reload VS Code, then ask Codex to use $workspace-engineering.'
Write-Output 'Run .\tools\engineering\eng.ps1 doctor to inspect repository, graph and runtime readiness. Setup has not run application checks.'
