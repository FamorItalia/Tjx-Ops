param(
    [string]$TaskName = "TJX Ops - Daily Backup"
)

$ErrorActionPreference = "Stop"

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Task rimosso: $TaskName"
} else {
    Write-Host "Task non trovato: $TaskName"
}
