param(
    [string]$TaskName = "TJX Ops - Daily Backup",
    [string]$RunAt = "19:00"
)

$ErrorActionPreference = "Stop"
$opsDir = (Resolve-Path $PSScriptRoot).Path
$scriptPath = Join-Path $opsDir "backup-daily.ps1"

if (-not (Test-Path $scriptPath)) {
    throw "Script non trovato: $scriptPath"
}

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`""
$trigger = New-ScheduledTaskTrigger -Daily -At $RunAt
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description "Backup giornaliero TJX Ops (DB + snapshot + output + anagrafiche)" -Force | Out-Null

Write-Host "Task creato/aggiornato: $TaskName alle $RunAt"
