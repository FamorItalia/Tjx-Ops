$ErrorActionPreference = "Stop"

$opsDir = $PSScriptRoot
$runner = Join-Path $opsDir "run-watchdog.cmd"
if (!(Test-Path $runner)) { throw "File non trovato: $runner" }

$tr = "cmd /c `"$runner`""

schtasks /Create /TN "TJX-OpsHub-Watchdog" /TR "$tr" /SC HOURLY /MO 1 /RL HIGHEST /F | Out-Null

Write-Host "Watchdog creato: TJX-OpsHub-Watchdog (ogni 1 ora)."
Write-Host "Avvio immediato..."
schtasks /Run /TN TJX-OpsHub-Watchdog | Out-Null
Write-Host "FATTO."
