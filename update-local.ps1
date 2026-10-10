# ZCFATO safe Windows updater. Run from PowerShell: .\update-local.ps1 -Build
[CmdletBinding()]
param(
    [switch]$Build,
    [switch]$FullBuild,
    [switch]$SkipTests,
    [string]$RepoPath = $PSScriptRoot
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($Build -and $FullBuild) { throw 'Select only one of -Build or -FullBuild.' }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Git is not installed or not on PATH.' }
if (-not (Test-Path -LiteralPath $RepoPath -PathType Container)) { throw "Missing repository directory: $RepoPath" }

Push-Location -LiteralPath $RepoPath
try {
    $root = (& git rev-parse --show-toplevel 2>$null)
    if ($LASTEXITCODE -ne 0 -or -not $root) { throw 'RepoPath is not inside a Git worktree.' }
    $root = [IO.Path]::GetFullPath([string]$root).TrimEnd('\', '/')
    $requested = [IO.Path]::GetFullPath((Get-Location).Path).TrimEnd('\', '/')
    if (-not [string]::Equals($root, $requested, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Run from repository root ($root) or pass -RepoPath explicitly."
    }
    $remote = (& git remote get-url origin 2>$null)
    if ($LASTEXITCODE -ne 0 -or $remote -notmatch '(^|[:/])cvsz/zcfato(\.git)?$') {
        throw "Unexpected origin remote: $remote. Expected cvsz/zcfato."
    }
    $changes = @(& git status --porcelain --untracked-files=normal)
    if ($LASTEXITCODE -ne 0) { throw 'Could not inspect Git status.' }
    if ($changes.Count -gt 0) {
        Write-Host 'Local changes detected. No checkout, stash, reset or pull performed.' -ForegroundColor Yellow
        $changes | ForEach-Object { Write-Host $_ }
        throw 'Commit or back up local changes before updating.'
    }
    $branch = (& git branch --show-current).Trim()
    if ($branch -ne 'main') { throw "Current branch is '$branch'. Switch to main manually after preserving your changes." }

    Write-Host '[1/4] Fetching latest origin/main...'
    & git fetch --prune origin main
    if ($LASTEXITCODE -ne 0) { throw 'git fetch failed.' }
    Write-Host '[2/4] Fast-forwarding main...'
    & git pull --ff-only origin main
    if ($LASTEXITCODE -ne 0) { throw 'Fast-forward pull failed. No history rewrite attempted.' }
    $sha = (& git rev-parse HEAD).Trim()
    Write-Host "Updated to $sha" -ForegroundColor Green

    if (-not $SkipTests) {
        Write-Host '[3/4] Running Python tests...'
        $py = $null
        if (Test-Path '.venv\Scripts\python.exe') { $py = '.venv\Scripts\python.exe' }
        elseif (Get-Command py -ErrorAction SilentlyContinue) { $py = 'py' }
        elseif (Get-Command python -ErrorAction SilentlyContinue) { $py = 'python' }
        if (-not $py) { throw 'No Python found. Install Python 3.12 x64 or use -SkipTests.' }
        if ($py -eq 'py') { & py -3.12 -m pytest -q tests }
        else { & $py -m pytest -q tests }
        if ($LASTEXITCODE -ne 0) { throw 'Tests failed. Build was not started.' }
    } else {
        Write-Host '[3/4] Tests skipped by explicit request.' -ForegroundColor Yellow
    }

    if ($FullBuild) {
        Write-Host '[4/4] Building Camfrog + LINE apps without publishing...'
        & cmd /c 'call full-build.bat'
        if ($LASTEXITCODE -ne 0) { throw 'Full build failed.' }
    } elseif ($Build) {
        Write-Host '[4/4] Building Camfrog feature EXEs without publishing...'
        & cmd /c 'call build.bat'
        if ($LASTEXITCODE -ne 0) { throw 'Windows build failed.' }
    } else {
        Write-Host '[4/4] Build skipped (pass -Build or -FullBuild).' 
    }
    Write-Host "SUCCESS: ZCFATO local main is at $sha" -ForegroundColor Green
    Write-Host 'No release or deployment was published.'
} finally {
    Pop-Location
}
