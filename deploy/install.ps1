$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
if ($env:COMPUTERNAME -ne 'KGO-GIS') { throw 'Unexpected server' }
$root = [IO.Path]::GetFullPath('D:\codesolution\kgeodata')
$target = [IO.Path]::GetFullPath((Join-Path $root 'goyang_time_map'))
if ($target -ne 'D:\codesolution\kgeodata\goyang_time_map') { throw 'Target mismatch' }
foreach ($check in @('D:\codesolution', $root)) { if ((Get-Item -LiteralPath $check).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Unexpected linked parent' } }
if (Test-Path -LiteralPath $target) { throw 'Target already exists; refusing to overwrite' }
$stage = [IO.Path]::GetFullPath((Join-Path $root ('goyang_time_map.stage-' + $env:GITHUB_RUN_ID)))
if (-not $stage.StartsWith($root + '\goyang_time_map.stage-') -or (Test-Path -LiteralPath $stage)) { throw 'Staging path unavailable' }
$source = Join-Path $env:GITHUB_WORKSPACE 'goyang_time_map'
$expected = Get-Content -LiteralPath (Join-Path $env:GITHUB_WORKSPACE 'deploy/manifest.json') -Raw | ConvertFrom-Json
function Check-Tree([string]$folder) {
  $files = @(Get-ChildItem -LiteralPath $folder -Recurse -File)
  $entries = @($expected.PSObject.Properties)
  if ($files.Count -ne $entries.Count) { throw 'Unexpected file count' }
  foreach ($entry in $entries) {
    $file = Join-Path $folder $entry.Name
    if ((Get-Item -LiteralPath $file).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Unexpected linked file' }
    if ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value) { throw ('File hash mismatch: ' + $entry.Name) }
  }
}
Check-Tree $source
New-Item -ItemType Directory -Path $stage | Out-Null
Get-ChildItem -LiteralPath $source | Copy-Item -Destination $stage -Recurse
Check-Tree $stage
Move-Item -LiteralPath $stage -Destination $target
try {
  $page = Invoke-WebRequest -UseBasicParsing -Uri 'https://kgeodata.com/app/goyang_time_map/' -TimeoutSec 30
  if ($page.StatusCode -ne 200 -or -not $page.Content.Contains('data-year="2025"')) { throw 'Public HTML check failed' }
  foreach ($year in @(2006,2011,2022,2025)) {
    $response = Invoke-WebRequest -UseBasicParsing -Uri ('https://kgeodata.com/app/goyang_time_map/data/' + $year + '.json') -TimeoutSec 30
    $dataset = $response.Content | ConvertFrom-Json
    if ($response.StatusCode -ne 200 -or $dataset.type -ne 'FeatureCollection' -or $dataset.features.Count -lt 1) { throw ('Public data check failed: ' + $year) }
    Write-Output ('DATA_OK ' + $year + ' ' + $dataset.features.Count)
  }
} catch {
  $rollback = [IO.Path]::GetFullPath(('D:\codesolution\_deploy_backup\goyang_time_map-failed-' + $env:GITHUB_RUN_ID))
  if (-not $rollback.StartsWith('D:\codesolution\_deploy_backup\goyang_time_map-failed-') -or (Test-Path -LiteralPath $rollback)) { throw 'Rollback path unavailable' }
  New-Item -ItemType Directory -Path (Split-Path -Parent $rollback) -Force | Out-Null
  Move-Item -LiteralPath $target -Destination $rollback
  throw
}
Write-Output 'DEPLOYED https://kgeodata.com/app/goyang_time_map/'
