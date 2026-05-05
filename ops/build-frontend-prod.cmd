@echo off
setlocal

set OPSDIR=%~dp0
for %%I in ("%OPSDIR%..") do set ROOT=%%~fI
cd /d "%ROOT%\frontend"
if errorlevel 1 (
  echo Errore: cartella frontend non trovata in "%ROOT%\frontend"
  exit /b 1
)

echo [1/2] Install dipendenze frontend...
call npm install
if errorlevel 1 (
  echo Errore npm install
  exit /b 1
)

echo [2/2] Build frontend produzione...
call npm run build
if errorlevel 1 (
  echo Errore npm run build
  exit /b 1
)

echo Build completata.
endlocal
