$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$targets = @(
  (Join-Path $root "backend"),
  (Join-Path $root "frontend"),
  (Join-Path $root "ops")
)

$extensions = @("*.py", "*.ts", "*.tsx", "*.js", "*.mjs", "*.md", "*.txt", "*.ps1", "*.cmd")
$excludePathFragments = @("\node_modules\", "\.next\", "\.venv\", "\.git\", "\dist\", "\build\")

# Common mojibake leading chars from UTF-8 interpreted as ANSI/Windows-1252.
$suspiciousChars = @(
  [string][char]0x00C3,
  [string][char]0x00C2,
  [string][char]0x00E2,
  [string][char]0x00EF
)

$hits = @()
foreach ($base in $targets) {
  if (-not (Test-Path $base)) { continue }
  foreach ($ext in $extensions) {
    Get-ChildItem -Path $base -Recurse -File -Filter $ext | ForEach-Object {
      $path = $_.FullName
      $low = $path.ToLowerInvariant()
      foreach ($frag in $excludePathFragments) {
        if ($low.Contains($frag)) { return }
      }

      $content = Get-Content -Raw -Encoding UTF8 -LiteralPath $path
      foreach ($ch in $suspiciousChars) {
        if ($content.Contains($ch)) {
          $hits += [PSCustomObject]@{ File = $path; SuspiciousChar = $ch }
        }
      }
    }
  }
}

if ($hits.Count -gt 0) {
  Write-Host "Trovati possibili problemi di encoding:" -ForegroundColor Red
  $hits | Sort-Object File, SuspiciousChar -Unique | Format-Table -AutoSize
  exit 1
}

Write-Host "Encoding check OK: nessuna sequenza sospetta trovata."
