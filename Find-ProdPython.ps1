Param(
  [string]$SchedulerDir = "U:\docketwatch\docketwatch_scheduler",
  [string]$PythonDir    = "U:\docketwatch\python",
  [string]$OutDir       = "U:\docketwatch\audit"
)

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$cfm = Get-ChildItem -Path $SchedulerDir -Recurse -Include *.cfm,*.cfml -File

$rows = @()

foreach ($f in $cfm) {
  $txt = Get-Content -Raw $f.FullName

  # cfexecute patterns
  $execs = [regex]::Matches($txt, '(?is)<cfexecute\b[^>]*?>.*?</cfexecute>|<cfexecute\b[^>]+/>')
  foreach ($m in $execs) {
    $block = $m.Value
    $exe   = ([regex]::Match($block, '(?i)\b(?:name|executable)\s*=\s*"([^"]+)"')).Groups[1].Value
    $args  = ([regex]::Match($block, '(?i)\barguments\s*=\s*"([^"]*)"')).Groups[1].Value
    $py    = ([regex]::Match($args, '(?i)([A-Z]:\\|/)[^"\s]*?\.py')).Groups[0].Value
    if (-not $py -and $args -match '(?i)\.py\b') { $py = $args }
    $rows += [pscustomobject]@{
      cfm_path     = $f.FullName
      call_type    = 'cfexecute'
      executable   = $exe
      arguments    = $args
      python_path  = $py
    }
  }

  # cfhttp to app endpoints that shell out
  $http = [regex]::Matches($txt, '(?is)<cfhttp\b[^>]*url\s*=\s*"([^"]+)"[^>]*>')
  foreach ($h in $http) {
    $url = $h.Groups[1].Value
    if ($url -match '(?i)docketwatch|tmztools|scheduler') {
      $rows += [pscustomobject]@{
        cfm_path     = $f.FullName
        call_type    = 'cfhttp'
        executable   = ''
        arguments    = $url
        python_path  = ''
      }
    }
  }
}

# normalize and cross-check against python dir
$prod = foreach ($r in $rows) {
  $p = $r.python_path
  if ($p -and (Test-Path $p)) { $exists = 'yes' } else { $exists = 'no' }
  [pscustomobject]@{
    cfm_path     = $r.cfm_path
    call_type    = $r.call_type
    executable   = $r.executable
    arguments    = $r.arguments
    python_path  = $p
    python_exists= $exists
  }
}

$prod | Sort-Object cfm_path, python_path | Export-Csv -NoTypeInformation -Path (Join-Path $OutDir 'production_entrypoints.csv')

# full python inventory with hashes
$pyFiles = Get-ChildItem -Path $PythonDir -Recurse -Include *.py -File | Where-Object {
  $_.FullName -notmatch '\\__pycache__\\' -and $_.FullName -notmatch '\\venv\\'
}
$inv = foreach ($p in $pyFiles) {
  $bytes = [System.IO.File]::ReadAllBytes($p.FullName)
  $sha1  = (Get-FileHash -Algorithm SHA1 -InputStream ([System.IO.MemoryStream]::new($bytes))).Hash
  [pscustomobject]@{
    python_path = $p.FullName
    size_bytes  = $p.Length
    sha1        = $sha1
    mtime_utc   = $p.LastWriteTimeUtc.ToString('s')
  }
}
$inv | Export-Csv -NoTypeInformation -Path (Join-Path $OutDir 'python_inventory.csv')

# orphans = python not referenced by any cfm
$prodPaths = $prod | Where-Object { $_.python_path } | Select-Object -ExpandProperty python_path -Unique
$orphans = $inv | Where-Object { $prodPaths -notcontains $_.python_path }
$orphans | Export-Csv -NoTypeInformation -Path (Join-Path $OutDir 'orphans_initial.csv')

Write-Host "Wrote: production_entrypoints.csv, python_inventory.csv, orphans_initial.csv to $OutDir"
