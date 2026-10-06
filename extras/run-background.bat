@echo off
rem Run camfrog-auto hidden in the background (no window). Stop with stop.bat. Log: camfrog_auto.log
cd /d "%~dp0"
camfrog-auto.exe start %*
timeout /t 5 >nul
