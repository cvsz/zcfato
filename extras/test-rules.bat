@echo off
cd /d "%~dp0"
if "%~1"=="" (
  echo usage: test-rules.bat "message text" [--sender NAME]
  echo        test-rules.bat --file chat.txt
  exit /b 1
)
camfrog-auto.exe test-rules %*
pause
