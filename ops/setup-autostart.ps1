$ErrorActionPreference = "Stop"

$opsDir = $PSScriptRoot
$root = Split-Path -Path $opsDir -Parent
$backendCmd = "$root\ops\run-backend-prod.cmd"
$frontendCmd = "$root\ops\run-frontend-prod.cmd"

if (!(Test-Path $backendCmd)) { throw "File non trovato: $backendCmd" }
if (!(Test-Path $frontendCmd)) { throw "File non trovato: $frontendCmd" }

Write-Host "Creo attività pianificate di avvio automatico..."

# Avvio all'accesso utente corrente, in background.
# Usiamo cmd /c per gestire correttamente path con spazi/accenti.
$backendTr = "cmd /c `"$backendCmd`""
$frontendTr = "cmd /c `"$frontendCmd`""
schtasks /Create /TN "TJX-OpsHub-Backend" /TR "$backendTr" /SC ONLOGON /RL HIGHEST /F | Out-Null
schtasks /Create /TN "TJX-OpsHub-Frontend" /TR "$frontendTr" /SC ONLOGON /RL HIGHEST /F | Out-Null

Write-Host "Creo regole firewall (porte 8000 e 3001)..."
netsh advfirewall firewall add rule name="TJX Ops Hub Backend 8000" dir=in action=allow protocol=TCP localport=8000 > $null
netsh advfirewall firewall add rule name="TJX Ops Hub Frontend 3001" dir=in action=allow protocol=TCP localport=3001 > $null

Write-Host ""
Write-Host "FATTO."
Write-Host "Attività create: TJX-OpsHub-Backend, TJX-OpsHub-Frontend"
Write-Host "Per avviarle subito senza riavvio:"
Write-Host "  schtasks /Run /TN TJX-OpsHub-Backend"
Write-Host "  schtasks /Run /TN TJX-OpsHub-Frontend"
