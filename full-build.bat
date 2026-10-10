@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================================
echo FULL BUILD: Camfrog feature apps + line-status-changer
echo ============================================================
echo.
echo Usage: full-build.bat [--release]
echo   --release  publish the GitHub release after a green build
echo              (version from APP_VERSION, needs: gh auth login).
echo Without --release, no GitHub release is created.
echo.

rem --- Build Camfrog feature apps ---
echo [1/3] Building Camfrog feature apps...
call build.bat
if errorlevel 1 (
    echo.
    echo BUILD FAILED: Camfrog feature apps
    exit /b 1
)
echo.

rem --- Build line-status-changer ---
echo [2/3] Building line-status-changer...
cd line
call build.bat
if errorlevel 1 (
    echo.
    echo BUILD FAILED: line-status-changer
    cd ..
    exit /b 1
)
cd ..
echo.

rem --- Verify all build outputs ---
echo [3/3] Verifying outputs...
if not exist dist\room-control\room-control.exe (
    echo ERROR: dist\room-control\room-control.exe not found
    exit /b 1
)
if not exist dist\chat-im-private\chat-im-private.exe (
    echo ERROR: dist\chat-im-private\chat-im-private.exe not found
    exit /b 1
)
if not exist dist\status-random\status-random.exe (
    echo ERROR: dist\status-random\status-random.exe not found
    exit /b 1
)
if not exist dist\status-marquee\status-marquee.exe (
    echo ERROR: dist\status-marquee\status-marquee.exe not found
    exit /b 1
)
if not exist dist\im-autoreply\im-autoreply.exe (
    echo ERROR: dist\im-autoreply\im-autoreply.exe not found
    exit /b 1
)
if not exist dist\web-status\web-status.exe (
    echo ERROR: dist\web-status\web-status.exe not found
    exit /b 1
)
if not exist dist\music-dj\music-dj.exe (
    echo ERROR: dist\music-dj\music-dj.exe not found
    exit /b 1
)
if not exist line\dist\line-status-changer.exe (
    echo ERROR: line\dist\line-status-changer.exe not found
    exit /b 1
)
if not exist line\dist\line_config.json (
    echo ERROR: line\dist\line_config.json not found
    exit /b 1
)
if not exist camfrog-features-windows.zip (
    echo ERROR: camfrog-features-windows.zip not found
    exit /b 1
)
if not exist dist\SHA256SUMS.txt (
    echo ERROR: dist\SHA256SUMS.txt not found
    exit /b 1
)
echo All expected outputs found.
echo.

rem --- Publish the GitHub release (opt-in only) ---
if /i "%~1"=="--release" (
    echo [4/4] Publishing GitHub release...
    if not exist ".venv\Scripts\python.exe" (
        echo ERROR: .venv\Scripts\python.exe not found, cannot publish release
        exit /b 1
    )
    ".venv\Scripts\python.exe" tools\release.py
    if errorlevel 1 (
        echo.
        echo RELEASE FAILED: GitHub release was not published
        exit /b 1
    )
    echo.
) else (
    echo Skipping GitHub release ^(pass --release to publish^).
    echo.
)

echo.
echo ============================================================
echo FULL BUILD COMPLETE
echo ============================================================
echo.
echo Outputs:
echo   dist\room-control\room-control.exe
echo   dist\chat-im-private\chat-im-private.exe
echo   dist\status-random\status-random.exe
echo   dist\status-marquee\status-marquee.exe
echo   dist\im-autoreply\im-autoreply.exe
echo   dist\web-status\web-status.exe
echo   dist\music-dj\music-dj.exe
echo   camfrog-features-windows.zip
echo   dist\SHA256SUMS.txt
echo   line\dist\line-status-changer.exe
echo   line\dist\line_config.json
echo.
echo Build only: no Git staging, commit, or push is performed.
echo Without --release, no GitHub release is created either.
echo.
