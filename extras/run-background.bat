@echo off
rem Source CLI wrapper; requires Python and this checkout.
cd /d "%~dp0.."
python camfrog_auto.py start %*
timeout /t 5 >nul
