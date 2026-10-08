@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

rem --- same interpreter choice as build.bat (never the free-threaded "t" build) ---
set "PYSEL="
for %%V in (3.12 3.13 3.11 3.14) do (
  if not defined PYSEL (
    py -%%V-64 -c "import sys" >nul 2>&1 && set "PYSEL=py -%%V-64"
  )
)
if not defined PYSEL set "PYSEL=python"

echo build.bat will use / build.bat จะใช้: %PYSEL%
echo.
%PYSEL% tools\doctor.py
set "RC=%errorlevel%"
pause
exit /b %RC%
