$ErrorActionPreference = "SilentlyContinue"
schtasks /Delete /TN "TJX-OpsHub-Watchdog" /F | Out-Null
Write-Host "Watchdog rimosso."
