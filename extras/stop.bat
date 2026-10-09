@echo off
cd /d "%~dp0.."
python camfrog_auto.py stop %*
pause
