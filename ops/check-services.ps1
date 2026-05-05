$ErrorActionPreference = "SilentlyContinue"

$backendStatus = $null
$frontendStatus = $null

try {
  $backendStatus = (Invoke-WebRequest "http://127.0.0.1:8000/api/v1/health" -UseBasicParsing -TimeoutSec 3).StatusCode
} catch {}

try {
  $frontendStatus = (Invoke-WebRequest "http://127.0.0.1:3001/login" -UseBasicParsing -TimeoutSec 3).StatusCode
} catch {}

$backendOk = ($backendStatus -eq 200)
$frontendOk = ($frontendStatus -eq 200)

Write-Host "=== TJX Ops Hub service check ==="
if ($backendOk) {
  Write-Host "Backend OK (http://127.0.0.1:8000/api/v1/health) - Status $backendStatus"
} else {
  Write-Host "Backend KO (non risponde su porta 8000)"
}

if ($frontendOk) {
  Write-Host "Frontend OK (http://127.0.0.1:3001/login) - Status $frontendStatus"
} else {
  Write-Host "Frontend KO (non risponde su porta 3001)"
}

Write-Host ""
Write-Host "URL locale: http://localhost:3001/login"
