$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
if ($env:COMPUTERNAME -ne 'KGO-GIS') { throw 'Unexpected server' }
if ($env:GITHUB_RUN_ID -notmatch '^\d+$') { throw 'Invalid deployment run ID' }
$root = [IO.Path]::GetFullPath('D:\codesolution\kgeodata')
$target = [IO.Path]::GetFullPath((Join-Path $root 'goyang_time_map'))
$backupRoot = [IO.Path]::GetFullPath('D:\codesolution\_deploy_backup')
$stage = [IO.Path]::GetFullPath((Join-Path $root ('goyang_time_map.stage-' + $env:GITHUB_RUN_ID)))
$backup = [IO.Path]::GetFullPath((Join-Path $backupRoot ('goyang_time_map-' + $env:GITHUB_RUN_ID)))
$failed = [IO.Path]::GetFullPath((Join-Path $backupRoot ('goyang_time_map-failed-' + $env:GITHUB_RUN_ID)))
if ($target -ne 'D:\codesolution\kgeodata\goyang_time_map' -or
    -not $stage.StartsWith($root + '\goyang_time_map.stage-') -or
    -not $backup.StartsWith($backupRoot + '\goyang_time_map-') -or
    -not $failed.StartsWith($backupRoot + '\goyang_time_map-failed-')) { throw 'Unexpected resolved path' }
foreach ($check in @('D:\codesolution', $root, $target, $backupRoot)) {
  if ((Test-Path -LiteralPath $check) -and ((Get-Item -LiteralPath $check -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Unexpected linked parent' }
}
if (-not (Test-Path -LiteralPath $target -PathType Container)) { throw 'Existing map folder is missing' }
foreach ($check in @($stage, $backup, $failed)) { if (Test-Path -LiteralPath $check) { throw 'Deployment destination already exists' } }
$source = Join-Path $env:GITHUB_WORKSPACE 'goyang_time_map'
$expected = Get-Content -LiteralPath (Join-Path $env:GITHUB_WORKSPACE 'deploy/manifest.json') -Raw | ConvertFrom-Json
$previous = Get-Content -LiteralPath (Join-Path $env:GITHUB_WORKSPACE 'deploy/previous-manifest.json') -Raw | ConvertFrom-Json
function Check-Tree([string]$folder, $manifest) {
  $items = @(Get-ChildItem -LiteralPath $folder -Recurse -Force)
  foreach ($item in $items) { if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Unexpected linked content' } }
  $files = @($items | Where-Object { -not $_.PSIsContainer })
  $entries = @($manifest.PSObject.Properties)
  if ($files.Count -ne $entries.Count) { throw 'Unexpected file count' }
  foreach ($entry in $entries) {
    if ($entry.Name -notmatch '^[A-Za-z0-9_./-]+$' -or $entry.Name.Contains('..')) { throw 'Invalid manifest path' }
    $file = [IO.Path]::GetFullPath((Join-Path $folder $entry.Name))
    if (-not $file.StartsWith($folder + '\')) { throw 'Manifest escaped folder' }
    if ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value) { throw ('File hash mismatch: ' + $entry.Name) }
  }
}
$owner = Get-Content -LiteralPath (Join-Path $target 'deployment.json') -Raw | ConvertFrom-Json
if ($owner.application -ne 'goyang-time-map-seoul021') { throw 'Map ownership marker mismatch' }
Check-Tree $target $previous
Check-Tree $source $expected
New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
New-Item -ItemType Directory -Path $stage | Out-Null
Get-ChildItem -LiteralPath $source -Force | Copy-Item -Destination $stage -Recurse -Force
Check-Tree $stage $expected
Move-Item -LiteralPath $target -Destination $backup
try {
  Move-Item -LiteralPath $stage -Destination $target
  Check-Tree $target $expected
  $page = Invoke-WebRequest -UseBasicParsing -Uri ('https://kgeodata.com/app/goyang_time_map/?release=' + $env:GITHUB_RUN_ID) -TimeoutSec 30
  if ($page.StatusCode -ne 200 -or -not $page.Content.Contains('id="insightSection"') -or -not $page.Content.Contains('id="swipeRange"')) { throw 'Public insight page check failed' }
  foreach ($year in @(2006,2011,2022,2025)) {
    $response = Invoke-WebRequest -UseBasicParsing -Uri ('https://kgeodata.com/app/goyang_time_map/data/' + $year + '.json') -TimeoutSec 30
    $dataset = $response.Content | ConvertFrom-Json
    if ($response.StatusCode -ne 200 -or $dataset.type -ne 'FeatureCollection' -or $dataset.features.Count -lt 1) { throw ('Public data check failed: ' + $year) }
    Write-Output ('DATA_OK ' + $year + ' ' + $dataset.features.Count)
  }
} catch {
  $deploymentError = $_
  if (Test-Path -LiteralPath $target) { Move-Item -LiteralPath $target -Destination $failed }
  Move-Item -LiteralPath $backup -Destination $target
  Check-Tree $target $previous
  Write-Output 'Previous map restored after failed update'
  throw $deploymentError
}
Write-Output ('PREVIOUS_VERSION ' + $backup)
Write-Output 'DEPLOYED https://kgeodata.com/app/goyang_time_map/'
