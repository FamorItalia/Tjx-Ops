@echo off
setlocal

set OPSDIR=%~dp0
for %%I in ("%OPSDIR%..") do set ROOT=%%~fI
cd /d "%ROOT%\frontend"
if errorlevel 1 (
  echo Errore: cartella frontend non trovata in "%ROOT%\frontend"
  exit /b 1
)

echo [0/3] Encoding check pre-release...
powershell -NoProfile -ExecutionPolicy Bypass -File "%OPSDIR%check-encoding.ps1"
if errorlevel 1 (
  echo Errore check encoding
  exit /b 1
)

echo [1/3] Install dipendenze frontend...
call npm install
if errorlevel 1 (
  echo Errore npm install
  exit /b 1
)

echo [2/3] Build frontend produzione...
call npm run build
if errorlevel 1 (
  echo Errore npm run build
  exit /b 1
)

echo Build completata.
endlocal
