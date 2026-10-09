@echo off
set "APP=%~dp0..\dist\room-control\room-control.exe"
if not exist "%APP%" (
  echo Build the standalone Room Control app first: build.bat
  exit /b 1
)
start "" "%APP%" %*
