@echo off
setlocal

set OPSDIR=%~dp0
for %%I in ("%OPSDIR%..") do set ROOT=%%~fI
set LOGDIR=%ROOT%\ops\logs
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

cd /d "%ROOT%\frontend"
if errorlevel 1 (
  echo Errore: cartella frontend non trovata in "%ROOT%\frontend" >> "%LOGDIR%\frontend.log"
  exit /b 1
)
echo --- FRONTEND START %DATE% %TIME% --- >> "%LOGDIR%\frontend.log"
echo ROOT=%ROOT% >> "%LOGDIR%\frontend.log"
echo CWD=%CD% >> "%LOGDIR%\frontend.log"
if not exist ".next\\BUILD_ID" (
  echo Build Next mancante, avvio build... >> "%LOGDIR%\frontend.log"
  call npm run build >> "%LOGDIR%\frontend.log" 2>&1
)
if not exist ".next\\BUILD_ID" (
  echo ERRORE: build frontend non disponibile (.next\\BUILD_ID assente). >> "%LOGDIR%\frontend.log"
  exit /b 1
)
call npm run start -- -H 0.0.0.0 -p 3001 >> "%LOGDIR%\frontend.log" 2>&1

endlocal
