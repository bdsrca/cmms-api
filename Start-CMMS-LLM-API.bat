@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-CMMS-LLM-API.ps1"
echo.
echo API stopped. Press any key to close this window.
pause >nul
