@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

set "PYTHONPATH=%CD%\zchat-client\src;%CD%\control-server\src"
python zchat-client\main.py
