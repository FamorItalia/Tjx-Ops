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

if (-not $backendOk -or -not $frontendOk) {
  & $startNow | Out-Null
}
