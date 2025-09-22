Param(
  [string]$Root = "U:\docketwatch\python",
  [string]$AuditDir = "U:\docketwatch\audit",
  [switch]$DryRun
)

# Input CSVs
$entryCsv = Join-Path $AuditDir "production_entrypoints.csv"
$closureCsv = Join-Path $AuditDir "production_closure.csv"    # preferred if present
$orphansCsv = Join-Path $AuditDir "orphans_final.csv"         # preferred if present
if (-not (Test-Path $entryCsv)) { throw "Missing $entryCsv" }

# Target folders
$ProdDir   = Join-Path $Root "prod"
$CoreDir   = Join-Path $Root "core"
$ArchiveDir= Join-Path $Root ("archive\_archive_{0:yyyyMMdd}" -f (Get-Date))
$ReportsDir= Join-Path $Root "reports"
$SandboxDir= Join-Path $Root "sandbox"

$targets = @($ProdDir,$CoreDir,$ArchiveDir,$ReportsDir,$SandboxDir)
foreach ($d in $targets) { if (-not $DryRun) { New-Item -ItemType Directory -Force -Path $d | Out-Null } }

# Helper: safe move
function Move-Safe {
  param([string]$Path,[string]$DestDir)
  if (-not (Test-Path $Path)) { return }
  $name = [IO.Path]::GetFileName($Path)
  $dest = Join-Path $DestDir $name
  if ($DryRun) { "{0} -> {1}" -f $Path, $dest; return }
  if ((Test-Path $dest) -and ((Get-FileHash $dest).Hash -eq (Get-FileHash $Path).Hash)) {
    # identical duplicate; archive the source copy instead of overwrite
    $dest = Join-Path $ArchiveDir $name
  }
  Move-Item -LiteralPath $Path -Destination $dest -Force
}

# 1) Put scraper_base.py in /core (canonical)
$scraperBase = Join-Path $Root "scraper_base.py"
if (Test-Path $scraperBase) {
  Move-Safe -Path $scraperBase -DestDir $CoreDir
}

# 2) Build production set
# Prefer production_closure.csv (all deps). Fallback to entrypoints.
$keepSet = New-Object System.Collections.Generic.HashSet[string]([StringComparer]::OrdinalIgnoreCase)
if (Test-Path $closureCsv) {
  (Import-Csv $closureCsv) | % { $p=$_.file.Trim(); if ($p) { [void]$keepSet.Add((Resolve-Path $p).Path) } }
} else {
  (Import-Csv $entryCsv) | % {
    $p = ($_.python_path ?? $_.python ?? $_.path ?? "").Trim()
    if ($p -and (Test-Path $p)) { [void]$keepSet.Add((Resolve-Path $p).Path) }
  }
}

# 3) Move production entrypoints to /prod
$entryPaths = (Import-Csv $entryCsv | % { ($_.python_path ?? $_.python ?? $_.path ?? "").Trim() }) | ? { $_ } | Select-Object -Unique
foreach ($p in $entryPaths) {
  if (Test-Path $p) { Move-Safe -Path (Resolve-Path $p).Path -DestDir $ProdDir }
}

# 4) Archive orphans (prefer orphans_final; fallback to orphans_initial)
$orphCsv = if (Test-Path $orphansCsv) { $orphansCsv } else { Join-Path $AuditDir "orphans_initial.csv" }
if (Test-Path $orphCsv) {
  (Import-Csv $orphCsv | % { ($_.file ?? $_.fullpath ?? $_.python_path ?? $_.path ?? "").Trim() }) |
    ? { $_ -and (Test-Path $_) } |
    % { Move-Safe -Path (Resolve-Path $_).Path -DestDir $ArchiveDir }
}

# 5) Sweep entire tree: anything not in keepSet goes to archive, except prod/core/reports/sandbox
$excludedRoots = @($ProdDir,$CoreDir,$ReportsDir,$SandboxDir,$ArchiveDir)
Get-ChildItem -Path $Root -Recurse -File -Include *.py |
  ? { $excludedRoots -notcontains $_.DirectoryName } |
  ? { $_.FullName -notmatch '\\__pycache__\\|\\venv\\' } |
  % {
    $rp = (Resolve-Path $_.FullName).Path
    if (-not $keepSet.Contains($rp)) { Move-Safe -Path $rp -DestDir $ArchiveDir }
  }

# 6) Create __init__.py for packages
foreach ($pkg in @($ProdDir,$CoreDir)) {
  $init = Join-Path $pkg "__init__.py"
  if (-not $DryRun) { if (-not (Test-Path $init)) { Set-Content -Path $init -Value "" -Encoding UTF8 } }
}

# 7) Report
$counts = [pscustomobject]@{
  prod_files    = (Get-ChildItem $ProdDir -File -Recurse -Filter *.py | Measure-Object).Count
  core_files    = (Get-ChildItem $CoreDir -File -Recurse -Filter *.py | Measure-Object).Count
  archived_now  = (Get-ChildItem $ArchiveDir -File -Recurse -Filter *.py | Measure-Object).Count
}
$counts | Format-List | Out-String | Write-Host
Write-Host "Archive: $ArchiveDir"
if ($DryRun) { Write-Host "DryRun only. No changes written." }
