[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$TargetSkillRoot,
    [string]$Python = 'python'
)

$sourceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$targetFull = [System.IO.Path]::GetFullPath($TargetSkillRoot)
if ($sourceRoot.Equals($targetFull, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'TargetSkillRoot cannot equal the source skill root.'
}
$targetParent = Split-Path -Parent $targetFull
$targetLeaf = Split-Path -Leaf $targetFull
if (-not (Test-Path -LiteralPath $targetParent)) {
    throw "Target parent does not exist: $targetParent"
}

$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$staging = Join-Path $targetParent (".$targetLeaf.candidate_$stamp")
$backup = Join-Path $targetParent (".$targetLeaf.backup_$stamp")
Copy-Item -LiteralPath $sourceRoot -Destination $staging -Recurse -Force

$validator = Join-Path $staging 'paper-review\scripts\validate_skill_suite.py'
& $Python $validator $staging --json
if ($LASTEXITCODE -ne 0) {
    throw 'Candidate validation failed; target was not changed.'
}

if (Test-Path -LiteralPath $targetFull) {
    Move-Item -LiteralPath $targetFull -Destination $backup
}
Move-Item -LiteralPath $staging -Destination $targetFull

$installedValidator = Join-Path $targetFull 'paper-review\scripts\validate_skill_suite.py'
& $Python $installedValidator $targetFull --json
if ($LASTEXITCODE -ne 0) {
    if (Test-Path -LiteralPath $backup) {
        Move-Item -LiteralPath $targetFull -Destination "$targetFull.failed_$stamp"
        Move-Item -LiteralPath $backup -Destination $targetFull
    }
    throw 'Installed copy failed validation and was restored from backup.'
}

Write-Output "installed=$targetFull"
if (Test-Path -LiteralPath $backup) { Write-Output "backup=$backup" }
