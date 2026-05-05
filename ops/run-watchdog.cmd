@echo off
setlocal
set OPSDIR=%~dp0
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%OPSDIR%watchdog.ps1"
endlocal
