[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)]
    [string]$TargetSkillRoot,
    [string]$Python = 'python'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-NormalPath([string]$Path) {
    $full = [System.IO.Path]::GetFullPath($Path)
    $root = [System.IO.Path]::GetPathRoot($full)
    if ($full -eq $root) { return $root }
    return $full.TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
}
function Test-Within([string]$Path, [string]$Parent) {
    $prefix = $Parent.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
    return $Path.Equals($Parent, [StringComparison]::OrdinalIgnoreCase) -or $Path.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)
}
function Assert-NoLinkAncestors([string]$Path) {
    $cursor = $Path
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            $item = Get-Item -LiteralPath $cursor -Force
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Linked path is not allowed: $cursor" }
        }
        $next = Split-Path -Parent $cursor
        if ($next -eq $cursor) { break }
        $cursor = $next
    }
}
function Assert-NoLinksInTree([string]$Path) {
    # Traverse one directory at a time and reject links before entering them.
    foreach ($item in Get-ChildItem -LiteralPath $Path -Force) {
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Linked entry is not allowed: $($item.FullName)" }
        if ($item.PSIsContainer) { Assert-NoLinksInTree $item.FullName }
    }
}
function Invoke-SuiteValidation([string]$Root) {
    $validator = Join-Path $Root 'paper-review\scripts\validate_skill_suite.py'
    if (-not (Test-Path -LiteralPath $validator -PathType Leaf)) { throw "Missing suite validator: $validator" }
    & $Python $validator $Root --json
    if ($LASTEXITCODE -ne 0) { throw "Suite validation failed: $Root (exit $LASTEXITCODE)" }
}

$sourceRoot = Get-NormalPath (Join-Path $PSScriptRoot '..')
$targetFull = Get-NormalPath $TargetSkillRoot
if ((Test-Within $targetFull $sourceRoot) -or (Test-Within $sourceRoot $targetFull)) {
    throw 'Source and target must be disjoint: equal, ancestor and descendant paths are forbidden.'
}
Assert-NoLinkAncestors $sourceRoot
Assert-NoLinkAncestors $targetFull
Assert-NoLinksInTree $sourceRoot
$targetParent = Split-Path -Parent $targetFull
$targetLeaf = Split-Path -Leaf $targetFull
if (-not $targetLeaf -or -not (Test-Path -LiteralPath $targetParent -PathType Container)) {
    throw 'Target must be a named directory with an existing parent.'
}
$skillNames = @('data-preparation','figure-generation','model-evaluation','model-implementation','modeling-design','modeling-scientist','paper-review','paper-writing')
$allowedNames = $skillNames + @('scripts','shared-references','AGENTS.md')
if (Test-Path -LiteralPath $targetFull) {
    if (-not (Test-Path -LiteralPath $targetFull -PathType Container)) { throw 'Target is not a directory.' }
    Assert-NoLinksInTree $targetFull
    $entries = @(Get-ChildItem -LiteralPath $targetFull -Force)
    if ($entries.Count -gt 0) {
        foreach ($entry in $entries) {
            if ($entry.Name -notin $allowedNames) { throw "Unmanaged target entry; refusing whole-directory replacement: $($entry.Name)" }
        }
        foreach ($name in $skillNames + @('shared-references')) {
            if (-not (Test-Path -LiteralPath (Join-Path $targetFull $name) -PathType Container)) { throw "Target is not a complete managed skill suite: missing $name" }
        }
        if (-not (Test-Path -LiteralPath (Join-Path $targetFull 'AGENTS.md') -PathType Leaf)) { throw 'Target lacks the suite AGENTS.md marker.' }
    }
}
if (-not $PSCmdlet.ShouldProcess($targetFull, 'Install the validated mathematics-modeling skill suite, retaining a backup')) { return }

$stamp = (Get-Date -Format 'yyyyMMdd_HHmmss') + '_' + [Guid]::NewGuid().ToString('N')
$staging = Get-NormalPath (Join-Path $targetParent (".$targetLeaf.candidate_$stamp"))
$backup = Get-NormalPath (Join-Path $targetParent (".$targetLeaf.backup_$stamp"))
$failed = Get-NormalPath (Join-Path $targetParent (".$targetLeaf.failed_$stamp"))
foreach ($candidate in @($staging,$backup,$failed)) {
    if (-not (Test-Within $candidate $targetParent) -or (Test-Within $candidate $sourceRoot) -or (Test-Within $sourceRoot $candidate) -or (Test-Path -LiteralPath $candidate)) {
        throw "Unsafe or occupied transaction path: $candidate"
    }
}
$backedUp = $false
$installed = $false
try {
    Copy-Item -LiteralPath $sourceRoot -Destination $staging -Recurse -Force -ErrorAction Stop
    Invoke-SuiteValidation $staging
    Assert-NoLinkAncestors $targetFull
    if (Test-Path -LiteralPath $targetFull) {
        Move-Item -LiteralPath $targetFull -Destination $backup -ErrorAction Stop
        $backedUp = $true
    }
    Move-Item -LiteralPath $staging -Destination $targetFull -ErrorAction Stop
    $installed = $true
    Invoke-SuiteValidation $targetFull
}
catch {
    $originalFailure = $_.Exception.Message
    try {
        if ($installed -and (Test-Path -LiteralPath $targetFull)) {
            Move-Item -LiteralPath $targetFull -Destination $failed -ErrorAction Stop
        }
        if ($backedUp) {
            if (Test-Path -LiteralPath $targetFull) { throw 'Target is occupied; backup preserved for explicit recovery.' }
            Move-Item -LiteralPath $backup -Destination $targetFull -ErrorAction Stop
        }
    }
    catch {
        throw "Install failed: $originalFailure. Recovery also failed: $($_.Exception.Message). Backup: $backup; candidate: $staging; failed copy: $failed"
    }
    throw "Install failed: $originalFailure. Previous target restored or left unchanged. Candidate/failed copies retained: $staging; $failed"
}
Write-Output "installed=$targetFull"
if ($backedUp) { Write-Output "backup=$backup" }
