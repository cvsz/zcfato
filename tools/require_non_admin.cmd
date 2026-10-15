@echo off
setlocal

powershell.exe -NoProfile -NonInteractive -Command "$principal = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent()); if ($principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { [Console]::Error.WriteLine('ERROR: Run Windows builds from a non-elevated terminal. PyInstaller does not support administrator builds.'); exit 1 }"
if errorlevel 1 exit /b 1
exit /b 0
