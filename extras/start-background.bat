@echo off
cd /d "%~dp0.."
python camfrog_auto.py start %*
pause
