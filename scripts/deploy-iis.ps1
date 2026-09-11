param([Parameter(Mandatory=$true)][string]$Source)
$ErrorActionPreference = 'Stop'
$target = 'D:\codesolution\kgeodata\guri'
$backupRoot = 'D:\guri-deploy-backups'
$sourcePath = (Resolve-Path -LiteralPath $Source).Path
$targetPath = (Resolve-Path -LiteralPath $target).Path
if ($targetPath.TrimEnd('\') -ne $target) { throw 'Unexpected deployment target' }
if ($sourcePath -eq $targetPath -or $sourcePath.StartsWith($targetPath + '\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Source must be outside web folder' }
foreach ($required in @('index.html','web.config','deployment.json','maps\theme.html','maps\animal.html')) {
  if (!(Test-Path -LiteralPath (Join-Path $sourcePath $required))) { throw "Missing artifact: $required" }
}
# Save prior successful files outside the web root. No purge or recursive removal.
$backup = Join-Path $backupRoot (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
New-Item -ItemType Directory -Path $backup -Force | Out-Null
& robocopy $targetPath $backup /E /R:1 /W:1 /NFL /NDL /NJH /NJS
if ($LASTEXITCODE -ge 8) { throw 'Backup failed; deployment stopped' }
try {
  # Publish resources before entry HTML. Retain previous hashed chunks for open tabs.
  & robocopy $sourcePath $targetPath /E /XF index.html deployment.json /R:2 /W:1 /NFL /NDL /NJH /NJS
  if ($LASTEXITCODE -ge 8) { throw 'Resource copy failed' }
  Get-ChildItem -LiteralPath $sourcePath -Filter index.html -Recurse | ForEach-Object {
    $relative = $_.FullName.Substring($sourcePath.Length).TrimStart('\')
    Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $targetPath $relative) -Force
  }
  Copy-Item -LiteralPath (Join-Path $sourcePath 'deployment.json') -Destination $targetPath -Force
  $live = Invoke-RestMethod -Uri ('https://kgeodata.com/app/guri/deployment.json?check=' + [DateTimeOffset]::UtcNow.ToUnixTimeSeconds())
  $expected = Get-Content -LiteralPath (Join-Path $sourcePath 'deployment.json') -Raw | ConvertFrom-Json
  if ($live.commit -ne $expected.commit) { throw 'Published commit does not match' }
  foreach ($url in @('https://kgeodata.com/app/guri/','https://kgeodata.com/app/guri/maps/theme.html','https://kgeodata.com/app/guri/maps/animal.html')) {
    $response = Invoke-WebRequest -Uri $url -UseBasicParsing
    if ($response.StatusCode -ne 200) { throw "HTTP check failed: $url" }
  }
  Write-Output "Published $($expected.commit). Previous files: $backup"
} catch {
  if (Test-Path -LiteralPath (Join-Path $backup 'index.html')) {
    & robocopy $backup $targetPath /E /R:1 /W:1 /NFL /NDL /NJH /NJS
    if ($LASTEXITCODE -ge 8) { Write-Warning "Restore incomplete. Backup: $backup" }
  }
  throw
}
exit 0
