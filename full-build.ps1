# PowerShell version of full-build.bat
# Supports --release v2.xx.x parameter

# ============================================================
# FULL BUILD: Camfrog feature apps + line-status-changer
# ============================================================
Write-Host "============================================================"
Write-Host "FULL BUILD: Camfrog feature apps + line-status-changer"
Write-Host "============================================================"
Write-Host ""
Write-Host "Usage: full-build.ps1 [--release VERSION]"
Write-Host "  --release v2.xx.x  publish the GitHub release after a green build"
Write-Host "                     (version v2.xx.x, needs: gh auth login)."
Write-Host "  --release          use the version from APP_VERSION, needs: gh auth login."
Write-Host "Without --release, no GitHub release is created."
Write-Host ""

# --- Capture the source used for this build; release.ps checks this marker ---
$BUILD_SOURCE_COMMIT = "unknown"
$BUILD_SOURCE_CLEAN = $false
$BUILD_STATUS_FILE = ""

# Capture git commit
$BUILD_SOURCE_COMMIT = git rev-parse HEAD 2>$null
if ($error.Count -gt 0) { $BUILD_SOURCE_COMMIT = "unknown" }

# Capture git status
if ($env:TEMP) {
    $BUILD_STATUS_FILE = "$($env:TEMP)\camfrog-build-source-$($RANDOM)-$($RANDOM).tmp"
    git status --porcelain --untracked-files=normal > $BUILD_STATUS_FILE 2>$null
    if ($error.Count -eq 0) {
        if (Test-Path $BUILD_STATUS_FILE) {
            $fileSize = [int](Get-Item $BUILD_STATUS_FILE).Length
            if ($fileSize -gt 0) {
                $BUILD_SOURCE_CLEAN = $true
            }
        }
    }
}

# Clean up status file
if ($BUILD_STATUS_FILE -and (Test-Path $BUILD_STATUS_FILE)) {
    Remove-Item $BUILD_STATUS_FILE -Force -ErrorAction SilentlyContinue
}

# ============================================================
# Build Camfrog feature apps
# ============================================================
Write-Host "[1/3] Building Camfrog feature apps..."
.
# ===========================================================================
# Build line-status-changer
# ===========================================================================
Write-Host "[2/3] Building line-status-changer..."
cd line
.

# ============================================================================
# Verify all build outputs
# ============================================================================
Write-Host "[3/3] Verifying outputs..."

$requiredFiles = @(
    "dist\room-control\room-control.exe",
    "dist\chat-im-private\chat-im-private.exe",
    "dist\status-random\status-random.exe",
    "dist\status-marquee\status-marexe",
    "dist\status-changer\status-changer.exe",
    "dist\im-autoreply\im-autoreply.exe",
    "dist\music-dj\music-dj.exe",
    "dist\web-status\web-status.exe",
    "line\dist\line-status-changer.exe",
    "line\dist\line_config.json",
    "camfrog-features-windows.zip",
    "dist\SHA256SUMS.txt"
)

$missingFiles = @()
foreach ($file in $requiredFiles) {
    if (-not (Test-Path $file)) {
        $missingFiles += $file
    }
}

if ($missingFiles.Count -gt 0) {
    Write-Host "ERROR: The following files are missing:"
    foreach ($file in $missingFiles) {
        Write-Host "  $file"
    }
    exit 1
}

Write-Host "All expected outputs found."
Write-Host ""

# --- Publish the GitHub release (opt-in only) ---
if ($args -contains "--release") {
    # Check if a version was specified
    $releaseArgs = $args -match "--release (.+)"
    
    if ($releaseArgs.Count -gt 0) {
        $specifiedVersion = $releaseArgs[0]
        if ($specifiedVersion -match "^v2\.(\d+)\.(\d+)$") {
            Write-Host "[4/4] Publishing GitHub release version $specifiedVersion..."
        }
        else {
            Write-Host "[4/4] Publishing GitHub release using APP_VERSION..."
        }
    }
    else {
        Write-Host "[4/4] Publishing GitHub release using APP_VERSION..."
    }
    
    if (-not (Test-Path ".venv\Scripts\python.exe")) {
        Write-Host "ERROR: .venv\Scripts\python.exe not found, cannot publish release"
        exit 1
    }
    
    .
    "`""
    .venv\Scripts\python.exe tools\release.py
    "`"
    
    if ($error.Count -gt 0) {
        Write-Host ""
        Write-Host "RELEASE FAILED: GitHub release was not published"
        exit 1
    }
    
    Write-Host ""
}
else {
    Write-Host "Skipping GitHub release (pass --release to publish)."
    Write-Host ""
}

Write-Host ""
Write-Host "============================================================"
Write-Host "FULL BUILD COMPLETE"
WriteCenter "============================================================"
Write-Host ""
Write-Host "Outputs:"
Write-Host "  dist\room-control\room-control.exe"
Write-Host "  dist\chat-im-private\chat-im-private.exe"
Write-Host "  dist\status-random\status-random.exe"
Write-Host "  dist\status-marquee\status-marquee.exe"
Write-Host "  dist\status-changer\status-changer.exe"
Write-Host "  dist\im-autoreply\im-autoreply.exe"
Write-Host "  dist\music-dj\music-dj.exe"
Write-Host "  camfrog-features-windows.zip"
Write-Host "  dist\SHA256SUMS.txt"
Write-Host "  dist\BUILD_SOURCE.txt"
Write-Host "  line\dist\line-status-changer.exe"
Write-Host "  line\dist\line_config.json"
Write-Host ""
Write-Host "Build only: no Git staging, commit, or push is performed."
Write-Host "Without --release, no GitHub release is created either."
Write-Host ""