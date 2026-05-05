param(
    [string]$ProjectRoot = "",
    [string]$BackupRoot = "",
    [int]$RetentionDays = 180
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}
if ([string]::IsNullOrWhiteSpace($BackupRoot)) {
    $BackupRoot = Join-Path $ProjectRoot "BACKUPS"
}

$backendDir = Join-Path $ProjectRoot "backend"
$opsDir = Join-Path $ProjectRoot "ops"
$templatesDir = Join-Path $ProjectRoot "TEMPLATES"
$frontendDir = Join-Path $ProjectRoot "frontend"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$runDir = Join-Path $BackupRoot $timestamp
$dbBackupDir = Join-Path $runDir "db"
$outputBackupDir = Join-Path $runDir "output"
$masterDataDir = Join-Path $runDir "master_data"
$logsDir = Join-Path $runDir "logs"

New-Item -ItemType Directory -Force -Path $runDir, $dbBackupDir, $outputBackupDir, $masterDataDir, $logsDir | Out-Null

function Resolve-DbPath {
    param([string]$BackendPath)
    $envFile = Join-Path $BackendPath ".env"
    if (Test-Path $envFile) {
        $line = Get-Content -LiteralPath $envFile | Where-Object { $_ -match "^\s*SQLITE_DB_PATH\s*=" } | Select-Object -First 1
        if ($line) {
            $value = ($line -split "=", 2)[1].Trim().Trim('"').Trim("'")
            if (-not [string]::IsNullOrWhiteSpace($value)) {
                if ([System.IO.Path]::IsPathRooted($value)) {
                    return $value
                }
                return (Join-Path $BackendPath $value)
            }
        }
    }
    return (Join-Path $BackendPath "data\tjx_operativita.db")
}

$dbPath = Resolve-DbPath -BackendPath $backendDir
$dbPathResolved = (Resolve-Path -LiteralPath $dbPath).Path
$dbBackupFile = Join-Path $dbBackupDir "tjx_operativita.sqlite3"

# Prefer backend venv python if present
$pyExe = Join-Path $backendDir ".venv\Scripts\python.exe"
if (-not (Test-Path $pyExe)) {
    $pyExe = "python"
}

# SQLite hot backup
$backupScript = @"
import sqlite3
import sys
src, dst = sys.argv[1], sys.argv[2]
conn_src = sqlite3.connect(src)
conn_dst = sqlite3.connect(dst)
try:
    conn_src.backup(conn_dst)
finally:
    conn_dst.close()
    conn_src.close()
"@

& $pyExe -c $backupScript $dbPathResolved $dbBackupFile
if ($LASTEXITCODE -ne 0) {
    throw "Backup SQLite fallito"
}

# Snapshot CSV + received order PDFs
$snapshotScript = Join-Path $opsDir "backup_snapshot_export.py"
& $pyExe $snapshotScript $dbPathResolved $runDir | Out-File -FilePath (Join-Path $logsDir "snapshot_export.log") -Encoding utf8
if ($LASTEXITCODE -ne 0) {
    throw "Export snapshot fallito"
}

# Master data files
$anagraficheDir = Join-Path $templatesDir "ANAGRAFICHE"
if (Test-Path $anagraficheDir) {
    Copy-Item -LiteralPath $anagraficheDir -Destination (Join-Path $masterDataDir "ANAGRAFICHE") -Recurse -Force
}

# Backend generated output
$backendOutputDir = Join-Path $backendDir "output"
if (Test-Path $backendOutputDir) {
    Copy-Item -LiteralPath $backendOutputDir -Destination (Join-Path $outputBackupDir "backend_output") -Recurse -Force
}

# Frontend generated output (if present)
$frontendPublicOutputDir = Join-Path $frontendDir "public\output"
if (Test-Path $frontendPublicOutputDir) {
    Copy-Item -LiteralPath $frontendPublicOutputDir -Destination (Join-Path $outputBackupDir "frontend_public_output") -Recurse -Force
}

$manifest = [ordered]@{
    created_at = (Get-Date).ToString("s")
    project_root = $ProjectRoot
    db_source = $dbPathResolved
    db_backup = $dbBackupFile
    retention_days = $RetentionDays
}

$manifest | ConvertTo-Json -Depth 5 | Out-File -FilePath (Join-Path $runDir "backup_manifest.json") -Encoding utf8

# Retention cleanup
$cutoff = (Get-Date).AddDays(-1 * $RetentionDays)
Get-ChildItem -LiteralPath $BackupRoot -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -lt $cutoff } |
    ForEach-Object {
        Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
    }

Write-Host "Backup completato: $runDir"
