param([Parameter(Mandatory=$true)][string]$Source, [string]$Target = 'D:\codesolution\kgeodata\guri')
$ErrorActionPreference = 'Stop'
# 서버의 웹 폴더(미리보기 서버 기준). 최종 서버에선 -Target 으로 바꿔 부른다. 확인 URL 은 deployment.json 의 url(= deploy.config.json origin+base)을 쓴다.
$target = $Target
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
  $expected = Get-Content -LiteralPath (Join-Path $sourcePath 'deployment.json') -Raw | ConvertFrom-Json
  $siteUrl = if ($expected.url) { $expected.url } else { 'https://kgeodata.com/app/guri/' }
  $live = Invoke-RestMethod -Uri ($siteUrl + 'deployment.json?check=' + [DateTimeOffset]::UtcNow.ToUnixTimeSeconds())
  if ($live.commit -ne $expected.commit) { throw 'Published commit does not match' }
  foreach ($url in @($siteUrl, ($siteUrl + 'maps/theme.html'), ($siteUrl + 'maps/animal.html'))) {
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
