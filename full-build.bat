@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================================
echo FULL BUILD: camfrog-auto + line-status-changer
echo ============================================================
echo.

rem --- Build camfrog-auto ---
echo [1/4] Building camfrog-auto...
call build.bat
if errorlevel 1 (
    echo.
    echo BUILD FAILED: camfrog-auto
    exit /b 1
)
echo.

rem --- Build line-status-changer ---
echo [2/4] Building line-status-changer...
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

rem --- Verify both exes exist ---
echo [3/4] Verifying outputs...
if not exist dist\camfrog-auto.exe (
    echo ERROR: dist\camfrog-auto.exe not found
    exit /b 1
)
if not exist dist\camfrog-auto-gui.exe (
    echo ERROR: dist\camfrog-auto-gui.exe not found
    exit /b 1
)
if not exist dist\zcfato.exe (
    echo ERROR: dist\zcfato.exe not found
    exit /b 1
)
if not exist line\dist\line-status-changer.exe (
    echo ERROR: line\dist\line-status-changer.exe not found
    exit /b 1
)
echo All executables found.
echo.

rem --- GPG commit and push ---
echo [4/4] Commit and push...
git add -A
if errorlevel 1 (
    echo ERROR: git add failed
    exit /b 1
)

rem Check if there are changes to commit
git diff --cached --quiet
if errorlevel 1 (
    rem Prefer a GPG-signed commit; fall back to unsigned when no secret key
    rem is available (e.g. a fresh Windows checkout). The build itself already
    rem succeeded -- this step only publishes it.
    git commit -S -m "build: release %DATE% %TIME%"
    if errorlevel 1 (
        echo WARNING: signed commit failed; retrying as unsigned commit...
        rem commit.gpgsign may be globally true, so explicitly disable it here.
        git -c commit.gpgsign=false commit -m "build: release %DATE% %TIME%"
        if errorlevel 1 (
            echo ERROR: commit failed
            exit /b 1
        )
    )
    git push
    if errorlevel 1 (
        echo ERROR: git push failed
        exit /b 1
    )
    echo.
    echo Pushed successfully.
)

echo.
echo ============================================================
echo FULL BUILD COMPLETE
echo ============================================================
echo.
echo Outputs:
echo   dist\camfrog-auto.exe
echo   dist\camfrog-auto-gui.exe
echo   dist\zcfato.exe
echo   line\dist\line-status-changer.exe
echo.