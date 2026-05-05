@echo off
setlocal

set OPSDIR=%~dp0
for %%I in ("%OPSDIR%..") do set ROOT=%%~fI
set LOGDIR=%ROOT%\ops\logs
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

cd /d "%ROOT%\backend"
if errorlevel 1 (
  echo Errore: cartella backend non trovata in "%ROOT%\backend" >> "%LOGDIR%\backend.log"
  exit /b 1
)
call ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-server-header >> "%LOGDIR%\backend.log" 2>&1

endlocal
