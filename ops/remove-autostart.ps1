$ErrorActionPreference = "SilentlyContinue"

schtasks /Delete /TN "TJX-OpsHub-Backend" /F | Out-Null
schtasks /Delete /TN "TJX-OpsHub-Frontend" /F | Out-Null

netsh advfirewall firewall delete rule name="TJX Ops Hub Backend 8000" > $null
netsh advfirewall firewall delete rule name="TJX Ops Hub Frontend 3001" > $null

Write-Host "Rimozione completata (attività + regole firewall)."
