$ErrorActionPreference = "Stop"

$opsDir = $PSScriptRoot
$backendCmd = Join-Path $opsDir "run-backend-prod.cmd"
$frontendCmd = Join-Path $opsDir "run-frontend-prod.cmd"

if (!(Test-Path $backendCmd)) { throw "File non trovato: $backendCmd" }
if (!(Test-Path $frontendCmd)) { throw "File non trovato: $frontendCmd" }

Write-Host "Avvio backend e frontend in background..."
Start-Process -FilePath "cmd.exe" -ArgumentList "/c `"$backendCmd`"" -WindowStyle Hidden
Start-Sleep -Seconds 2
Start-Process -FilePath "cmd.exe" -ArgumentList "/c `"$frontendCmd`"" -WindowStyle Hidden

Write-Host "Attendo avvio servizi..."
Start-Sleep -Seconds 4

& "$opsDir\check-services.ps1"
