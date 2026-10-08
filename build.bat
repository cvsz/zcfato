@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

set "NAME=camfrog-auto"

rem ============================================================
rem Select supported 64-bit Python
rem ============================================================
set "PYSEL="

for %%V in (3.12 3.13 3.11 3.14) do (
    if not defined PYSEL (
        py -%%V-64 -c "import sys" >nul 2>&1
        if not errorlevel 1 set "PYSEL=py -%%V-64"
    )
)

if not defined PYSEL set "PYSEL=python"

echo Using Python / ใช้ Python:
%PYSEL% -c "import sys,struct;print(sys.version);print(struct.calcsize('P')*8,'bit')"
if errorlevel 1 goto :nopython

for /f %%i in ('%PYSEL% -c "import sys;print(sys.version_info[0]*100+sys.version_info[1])"') do (
    set "PYV=%%i"
)

%PYSEL% tools\doctor.py --quick
if errorlevel 1 goto :nopython


rem ============================================================
rem Create/recreate virtual environment
rem ============================================================

if exist ".venv\pyver.txt" (
    findstr /x "%PYV%" ".venv\pyver.txt" >nul
    if errorlevel 1 rmdir /s /q ".venv"
)

if exist ".venv" (
    if not exist ".venv\pyver.txt" rmdir /s /q ".venv"
)

if not exist ".venv" (
    %PYSEL% -m venv ".venv"
    if errorlevel 1 goto :fail

    > ".venv\pyver.txt" echo %PYV%
)

set "VENV_PY=%CD%\.venv\Scripts\python.exe"

if not exist "%VENV_PY%" goto :fail

echo Build Python:
"%VENV_PY%" -c "import sys;print(sys.executable);print(sys.version)"
if errorlevel 1 goto :fail


rem ============================================================
rem Dependencies
rem ============================================================

"%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 goto :fail

"%VENV_PY%" -m pip install --only-binary=:all: "pywin32>=311"
if errorlevel 1 goto :pywin

"%VENV_PY%" -m pip install -r requirements-dev.txt "pyinstaller>=6.9"
if errorlevel 1 goto :fail


rem ============================================================
rem Quality gates
rem ============================================================

echo.
echo === PYTHON COMPILE CHECK ===

"%VENV_PY%" -m py_compile ^
    camfrog_auto.py ^
    camfrog_gui.py ^
    camfrog_status_gui.py ^
    camfrog_tray.py ^
    clipboard_support.py

if errorlevel 1 goto :fail


echo.
echo === TESTS ===

"%VENV_PY%" -m pytest -q tests
if errorlevel 1 goto :fail


echo.
echo === CONFIG VALIDATION EN ===

"%VENV_PY%" camfrog_auto.py check --config config.json
if errorlevel 1 goto :fail


echo.
echo === CONFIG VALIDATION TH ===

"%VENV_PY%" camfrog_auto.py --lang th check --config config.json
if errorlevel 1 goto :fail


rem ============================================================
rem Stop running dist applications
rem ============================================================

echo.
echo === STOP OLD APPLICATIONS ===

if exist "dist\%NAME%.exe" (
    "dist\%NAME%.exe" stop >nul 2>&1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass ^
    -File "%~dp0tools\end_dist_processes.ps1"

if errorlevel 1 goto :fail

"%VENV_PY%" -c "import time; time.sleep(2)"
if errorlevel 1 goto :fail


rem ============================================================
rem Clean old build
rem ============================================================

echo.
echo === CLEAN BUILD DIRECTORIES ===

if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

if exist "dist" goto :distlocked


rem ============================================================
rem Icon
rem ============================================================

set "ICONARG="

if exist "app.ico" (
    set "ICONARG=--icon app.ico"
) else (
    echo WARNING: app.ico not found, building without an icon.
    echo WARNING: ไม่พบ app.ico จะสร้างโดยไม่มีไอคอน
)


rem ============================================================
rem CLI executable
rem ============================================================

echo.
echo === BUILD CLI ===

"%VENV_PY%" -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --console ^
    --name "%NAME%" ^
    %ICONARG% ^
    --collect-all pywinauto ^
    --collect-submodules comtypes ^
    camfrog_auto.py

if errorlevel 1 goto :fail

if not exist "dist\%NAME%.exe" goto :fail


rem ============================================================
rem Full GUI executable
rem ============================================================

echo.
echo === BUILD GUI ===

"%VENV_PY%" -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --name "%NAME%-gui" ^
    %ICONARG% ^
    --collect-all pywinauto ^
    --collect-submodules comtypes ^
    camfrog_gui.py

if errorlevel 1 goto :fail

if not exist "dist\%NAME%-gui.exe" goto :fail


rem ============================================================
rem Status changer executable
rem ============================================================

echo.
echo === BUILD STATUS CHANGER ===

"%VENV_PY%" -m PyInstaller --noconfirm --clean ^
    --distpath dist ^
    --workpath build\zcfato\work ^
    zcfato.spec

if errorlevel 1 goto :fail

if not exist "dist\zcfato.exe" goto :fail


rem ============================================================
rem Distribution files
rem ============================================================

echo.
echo === COPY DISTRIBUTION FILES ===

copy /y "config.json" "dist\config.json" >nul
if errorlevel 1 goto :fail

if exist "app.ico" (
    copy /y "app.ico" "dist\app.ico" >nul
)

copy /y "CONFIG.md" "dist\CONFIG.md" >nul
if errorlevel 1 goto :fail

copy /y "README.md" "dist\README.md" >nul
if errorlevel 1 goto :fail

copy /y "extras\*.bat" "dist\" >nul
if errorlevel 1 goto :fail


rem ============================================================
rem Package + SHA256
rem ============================================================

echo.
echo === PACKAGE RELEASE ===

"%VENV_PY%" tools\package.py "%NAME%"
if errorlevel 1 goto :fail


rem ============================================================
rem Final verification
rem ============================================================

echo.
echo === VERIFY RELEASE ===

if not exist "dist\%NAME%.exe" goto :fail
if not exist "dist\%NAME%-gui.exe" goto :fail
if not exist "dist\zcfato.exe" goto :fail
if not exist "%NAME%-windows.zip" goto :fail

echo.
echo BUILD OK / สร้างสำเร็จ
echo.
echo dist\%NAME%.exe
echo dist\%NAME%-gui.exe
echo dist\zcfato.exe
echo %NAME%-windows.zip
echo.
echo Next / ขั้นต่อไป:
echo Run dist\zcfato.exe to edit status pools and start the standalone worker.
echo Or run dist\%NAME%-gui.exe for the full GUI.

exit /b 0


rem ============================================================
rem Error handlers
rem ============================================================

:distlocked
echo.
echo ERROR: cannot delete the dist folder.
echo A file in dist is still being used.
echo Close camfrog-auto, antivirus scanning, or Explorer windows using dist.
echo.
echo ข้อผิดพลาด: ไม่สามารถลบโฟลเดอร์ dist ได้
echo กรุณาปิด camfrog-auto และโปรแกรมที่กำลังใช้ไฟล์ใน dist
goto :fail


:pywin
%PYSEL% tools\doctor.py

echo.
echo pywin32 has no wheel for this Python.
echo Install Python 3.13 64-bit, delete .venv, then run build.bat again.
echo.
echo ไม่มี pywin32 สำหรับ Python ตัวนี้
echo ติดตั้ง Python 3.13 แบบ 64-bit ลบ .venv แล้วรัน build.bat ใหม่
echo.
echo winget install Python.Python.3.13

goto :fail


:nopython
echo.
echo Python not found or unusable.
echo Install Python 3.13 64-bit:
echo.
echo winget install Python.Python.3.13
echo.
echo ไม่พบ Python หรือ Python ไม่รองรับ

goto :fail


:fail
echo.
echo BUILD FAILED / สร้างไม่สำเร็จ
exit /b 1