@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

rem --- same interpreter choice as build.bat: CPython 3.12 x64 ---
set "PYSEL="
py -3.12-64 -c "import sys" >nul 2>&1 && set "PYSEL=py -3.12-64"
if not defined PYSEL set "PYSEL=python"

echo build.bat will use / build.bat จะใช้: %PYSEL%
echo.
%PYSEL% tools\doctor.py
set "RC=%errorlevel%"
pause
exit /b %RC%
