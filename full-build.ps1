# PowerShell wrapper for the repository's canonical full-build batch file.
# Usage: .\full-build.ps1 [--release [APP_VERSION]]

$inputArgs = @($args)
$publishRelease = $false
$releaseVersion = $null

if ($inputArgs.Count -eq 1 -and $inputArgs[0] -in @("--help", "-h")) {
    Write-Host "Usage: full-build.ps1 [--release [APP_VERSION]]"
    Write-Host "  --release       publish the current APP_VERSION after a green build"
    Write-Host "  --release APP_VERSION require that version to match the configured APP_VERSION"
    exit 0
}
elseif ($inputArgs.Count -eq 1 -and $inputArgs[0] -eq "--release") {
    $publishRelease = $true
}
elseif ($inputArgs.Count -eq 2 -and $inputArgs[0] -eq "--release") {
    $publishRelease = $true
    $releaseVersion = [string]$inputArgs[1]
    if ($releaseVersion -notmatch '^v\d+\.\d+\.\d+$') {
        [Console]::Error.WriteLine("Invalid release version. Expected v followed by three numeric components.")
        exit 2
    }
}
elseif ($inputArgs.Count -ne 0) {
    [Console]::Error.WriteLine("Usage: full-build.ps1 [--release [APP_VERSION]]")
    exit 2
}

$buildScript = Join-Path $PSScriptRoot "full-build.bat"
if (-not (Test-Path -LiteralPath $buildScript -PathType Leaf)) {
    [Console]::Error.WriteLine("Missing full-build.bat: $buildScript")
    exit 1
}

Push-Location -LiteralPath $PSScriptRoot
$exitCode = 0
try {
    & $buildScript
    $exitCode = $LASTEXITCODE

    if ($exitCode -eq 0 -and $publishRelease) {
        $python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
        if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
            [Console]::Error.WriteLine("Missing build Python: $python")
            $exitCode = 1
        }
        else {
            $releaseScript = Join-Path $PSScriptRoot "tools\release.py"
            if ($null -ne $releaseVersion) {
                & $python $releaseScript --release $releaseVersion
            }
            else {
                & $python $releaseScript --release
            }
            $exitCode = $LASTEXITCODE
        }
    }
}
finally {
    Pop-Location
}

exit $exitCode
