$ErrorActionPreference = "SilentlyContinue"

$opsDir = $PSScriptRoot
$startNow = Join-Path $opsDir "start-now.ps1"

function Test-Http200($url) {
  try {
    $code = (Invoke-WebRequest $url -UseBasicParsing -TimeoutSec 3).StatusCode
    return ($code -eq 200)
  } catch {
    return $false
  }
}

$backendOk = Test-Http200 "http://127.0.0.1:8000/api/v1/health"
$frontendOk = Test-Http200 "http://127.0.0.1:3001/login"

try {
  $logDir = Join-Path $opsDir "logs"
  if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
  }
  $heartbeat = @{
    last_run_utc = (Get-Date).ToUniversalTime().ToString("o")
    backend_ok = $backendOk
    frontend_ok = $frontendOk
    runner = "watchdog.ps1"
  } | ConvertTo-Json -Depth 4
  $heartbeat | Set-Content -Encoding UTF8 (Join-Path $logDir "watchdog-heartbeat.json")
} catch {}

if (-not $backendOk -or -not $frontendOk) {
  & $startNow | Out-Null
}
