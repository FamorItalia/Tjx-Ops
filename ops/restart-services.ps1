$ErrorActionPreference = "SilentlyContinue"

function Stop-PortProcess($port) {
  $conns = Get-NetTCPConnection -LocalPort $port -State Listen
  foreach ($c in $conns) {
    if ($c.OwningProcess -and $c.OwningProcess -gt 0) {
      Stop-Process -Id $c.OwningProcess -Force
    }
  }
}

function Stop-ZombieManagedProcesses() {
  try {
    $procs = Get-CimInstance Win32_Process
    foreach ($p in $procs) {
      $name = ([string]$p.Name).ToLowerInvariant()
      $cmd = ([string]$p.CommandLine).ToLowerInvariant()
      if ($name -eq "node.exe" -and ($cmd.Contains("\\frontend\\") -or $cmd.Contains("next"))) {
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
      }
      if ($name -eq "python.exe" -and ($cmd.Contains("\\backend\\") -and $cmd.Contains("uvicorn"))) {
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
      }
      if ($name -eq "cmd.exe" -and ($cmd.Contains("run-frontend-prod.cmd") -or $cmd.Contains("run-backend-prod.cmd"))) {
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
      }
    }
  } catch {}
}

Write-Host "Stop servizi su porte 8000/3001..."
Stop-PortProcess 8000
Stop-PortProcess 3001
Stop-ZombieManagedProcesses
Start-Sleep -Seconds 2

Write-Host "Riavvio servizi..."
& "$PSScriptRoot\start-now.ps1"
