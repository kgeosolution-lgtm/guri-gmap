<#
  kgeodata.com IIS 서버 전체 설정 (2026-11-16 기술 점검) — 관리자 PowerShell 로 한 번 실행

    powershell -ExecutionPolicy Bypass -File D:\kgeoHub\tools\3dscan\iis_tune.ps1            # 적용
    powershell -ExecutionPolicy Bypass -File D:\kgeoHub\tools\3dscan\iis_tune.ps1 -DryRun    # 바꿀 것만 보기
    powershell -ExecutionPolicy Bypass -File D:\kgeoHub\tools\3dscan\iis_tune.ps1 -Undo      # 바로 전 상태로 되돌리기

  하는 일
    1. applicationHost.config 백업 (appcmd add backup kgeo-tune-<시각>) — -Undo 가 이것으로 되돌린다
    2. 압축: 동적 압축 기능이 없으면 설치, JSON·GeoJSON·glTF·SVG·manifest 를 압축 목록 맨 앞에 추가,
       정적 파일은 첫 요청부터 압축 (frequentHitThreshold=1). application/octet-stream 은 넣지 않는다
       (포털 항목 내려받기 같은 큰 파일을 실시간 압축하면 느려지고 이어받기가 깨질 수 있다)
    3. https 강제: http 요청을 https 로 301, HSTS 머리글(기본 1일). Windows Server 2019(빌드 17763) 이상은 IIS 사이트 HSTS 기능,
       그보다 낮으면 URL Rewrite 전역 규칙(설치돼 있을 때만)
    4. 확인: http→https, JSON gzip, 포털·서버 REST 200, 벡터 타일 정상

  인증서 자동 갱신(Let's Encrypt HTTP-01)은 https 로 넘겨도 따라가므로 그대로 동작한다.
#>
param(
  [switch]$Undo,
  [switch]$DryRun,
  [switch]$SkipHttps,
  [switch]$SkipCompression,
  [int]$HstsMaxAge = 86400,
  [string]$HostName = 'kgeodata.com'
)
$ErrorActionPreference = 'Stop'
$appcmd = Join-Path $env:windir 'system32\inetsrv\appcmd.exe'
$stateFile = Join-Path $PSScriptRoot 'iis_tune_last_backup.txt'

function Say($m) { Write-Host $m }
function Run($desc, [string[]]$a, [switch]$DupOk) {
  if ($DryRun) { Say "  [DRY] $desc"; return }
  $out = (& $appcmd @a 2>&1) -join ' '
  if ($LASTEXITCODE -ne 0) {
    if ($DupOk -and $out -match 'duplicate') { Say "  ..  $desc (already)"; return }
    throw "$desc failed: $out"
  }
  Say "  OK  $desc"
}

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { throw 'Run this in an Administrator PowerShell (right-click > Run as administrator).' }
if (-not (Test-Path -LiteralPath $appcmd)) { throw "appcmd not found: $appcmd" }

# ── 되돌리기
if ($Undo) {
  if (-not (Test-Path -LiteralPath $stateFile)) { throw "no backup record: $stateFile" }
  $name = (Get-Content -LiteralPath $stateFile -Raw).Trim()
  Say "Restoring IIS configuration backup: $name"
  & $appcmd restore backup $name
  if ($LASTEXITCODE -ne 0) { throw 'restore failed' }
  Say 'Restored. (applicationHost.config is back to the state before iis_tune.ps1)'
  exit 0
}

# ── 사이트 찾기: https(443) 바인딩이 있는 사이트 중 호스트 이름이 맞거나 비어 있는 것
$sitesXml = [xml](& $appcmd list site /config /xml)
$site = $null
foreach ($s in $sitesXml.appcmd.SITE) {
  $b = @($s.site.bindings.binding)
  if ($b | Where-Object { $_.protocol -eq 'https' -and ($_.bindingInformation -match ":443:$([regex]::Escape($HostName))$" -or $_.bindingInformation -match ':443:$') }) { $site = $s.'SITE.NAME'; break }
}
if (-not $site) { throw "no IIS site with an https:443 binding for $HostName" }
$build = [Environment]::OSVersion.Version.Build
Say "Site: $site   (Windows build $build)"

# ── 1. 백업
$bkName = 'kgeo-tune-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
if (-not $DryRun) {
  & $appcmd add backup $bkName | Out-Null
  if ($LASTEXITCODE -ne 0) { throw 'backup failed' }
  Set-Content -LiteralPath $stateFile -Value $bkName -Encoding ASCII
  Say "Backup: $bkName  (undo: iis_tune.ps1 -Undo)"
}

# ── 2. 압축
if (-not $SkipCompression) {
  Say 'Compression'
  $feat = $null
  try { Import-Module ServerManager -ErrorAction Stop; $feat = Get-WindowsFeature Web-Dyn-Compression } catch { }
  if ($feat -and $feat.InstallState -ne 'Installed') {
    if ($DryRun) { Say '  [DRY] install Web-Dyn-Compression' } else { Install-WindowsFeature Web-Dyn-Compression | Out-Null; Say '  OK  installed Web-Dyn-Compression' }
  } elseif ($feat) { Say '  ..  dynamic compression feature already installed' }
  else { Say '  !!  could not check Web-Dyn-Compression (not Windows Server?) - continuing' }

  # 목록 맨 앞(@start)에 넣는다: 기본 목록 끝의 */* (enabled=false) 보다 먼저 맞아야 한다. 이미 있으면 건너뛴다
  # ArcGIS 는 'application/json; charset=UTF-8' 로 보내므로 charset 이 붙은 모양도 넣는다
  $static  = @('application/json', 'application/json; charset=utf-8', 'application/geo+json', 'application/manifest+json', 'model/gltf-binary', 'image/svg+xml', 'application/xml')
  $dynamic = @('application/json', 'application/json; charset=utf-8', 'application/json;charset=utf-8', 'application/geo+json', 'application/xml')
  foreach ($t in $static) {
    Run "static  += $t" @('set', 'config', '-section:system.webServer/httpCompression', "/+staticTypes.[@start,mimeType='$t',enabled='True']", '/commit:apphost') -DupOk
  }
  foreach ($t in $dynamic) {
    Run "dynamic += $t" @('set', 'config', '-section:system.webServer/httpCompression', "/+dynamicTypes.[@start,mimeType='$t',enabled='True']", '/commit:apphost') -DupOk
  }
  Run 'static compression from the first request (frequentHitThreshold=1)' @('set', 'config', '-section:system.webServer/serverRuntime', '/frequentHitThreshold:1', '/commit:apphost')
  Run 'urlCompression static+dynamic on (server level)' @('set', 'config', '-section:system.webServer/urlCompression', '/doStaticCompression:True', '/doDynamicCompression:True', '/commit:apphost')
}

# ── 3. https 강제 + HSTS
if (-not $SkipHttps) {
  Say 'HTTPS'
  if ($build -ge 17763) {
    Run "HSTS on site '$site' (max-age=$HstsMaxAge, http->https 301)" @('set', 'config', '-section:system.applicationHost/sites',
      "/[name='$site'].hsts.enabled:True", "/[name='$site'].hsts.max-age:$HstsMaxAge", "/[name='$site'].hsts.redirectHttpToHttps:True", '/commit:apphost')
  } elseif (Test-Path -LiteralPath (Join-Path $env:windir 'system32\inetsrv\rewrite.dll')) {
    $rules = (& $appcmd list config -section:system.webServer/rewrite/globalRules /text:*) -join "`n"
    if ($rules -match 'kgeo-https') { Say '  ..  rewrite rule kgeo-https already present' }
    else {
      Run 'URL Rewrite global rule kgeo-https' @('set', 'config', '-section:system.webServer/rewrite/globalRules', "/+[name='kgeo-https',stopProcessing='True']", '/commit:apphost')
      Run '  match .*' @('set', 'config', '-section:system.webServer/rewrite/globalRules', "/[name='kgeo-https'].match.url:(.*)", '/commit:apphost')
      Run '  condition HTTPS off' @('set', 'config', '-section:system.webServer/rewrite/globalRules', "/+[name='kgeo-https'].conditions.[input='{HTTPS}',pattern='^OFF$']", '/commit:apphost')
      Run '  redirect 301' @('set', 'config', '-section:system.webServer/rewrite/globalRules', "/[name='kgeo-https'].action.type:Redirect", "/[name='kgeo-https'].action.url:https://{HTTP_HOST}/{R:1}", "/[name='kgeo-https'].action.redirectType:Permanent", '/commit:apphost')
    }
  } else { Say '  !!  Windows build < 17763 and no URL Rewrite: skipped (the pages already switch to https by themselves)' }
}

if ($DryRun) { Say 'Dry run only - nothing changed.'; exit 0 }

# ── 4. 확인
Say 'Checks'
Start-Sleep -Seconds 2
$curl = Join-Path $env:windir 'system32\curl.exe'
function Head($url, [string[]]$extra) {
  if (Test-Path -LiteralPath $curl) { return (& $curl -s -o NUL -D - --max-time 30 @extra $url) -join "`n" }
  try { $r = Invoke-WebRequest -Uri $url -UseBasicParsing -MaximumRedirection 0 -Headers @{ 'Accept-Encoding' = 'gzip' } -TimeoutSec 30 -ErrorAction Stop; return "HTTP/1.1 $($r.StatusCode)`n" + ($r.Headers.GetEnumerator() | ForEach-Object { "$($_.Key): $($_.Value)" }) -join "`n" }
  catch { $resp = $_.Exception.Response; if ($resp) { return "HTTP/1.1 $([int]$resp.StatusCode)`nLocation: $($resp.Headers['Location'])" } return "ERROR $($_.Exception.Message)" }
}
$bad = 0
function Check($label, $text, $pattern) {
  $ok = $text -match $pattern
  if (-not $ok) { $script:bad++ }
  Say ("  {0}  {1}" -f $(if ($ok) { 'OK ' } else { 'BAD' }), $label)
  if (-not $ok) { Say ('       ' + (($text -split "`n" | Select-Object -First 6) -join ' | ')) }
}
if (-not $SkipHttps) { Check 'http -> https redirect' (Head "http://$HostName/app/3dscan/" @()) '(?mi)^HTTP/\S+ 30[178][\s\S]*^Location: https://' }
Check 'site page 200' (Head "https://$HostName/app/3dscan/" @()) '(?m)^HTTP/\S+ 200'
Check 'portal 200' (Head "https://$HostName/portal/home/" @()) '(?m)^HTTP/\S+ (200|302)'
Check 'server REST 200' (Head "https://$HostName/server/rest/info?f=json" @()) '(?m)^HTTP/\S+ 200'
if (-not $SkipCompression) {
  Check 'basemap style JSON is gzip' (Head "https://$HostName/server/rest/services/Hosted/NGII_GRAY_2026/VectorTileServer/resources/styles/root.json" @('-H', 'Accept-Encoding: gzip')) '(?mi)^Content-Encoding: gzip'
  Check 'site manifest.json is gzip' (Head "https://$HostName/app/3dscan/manifest.json" @('-H', 'Accept-Encoding: gzip')) '(?mi)^Content-Encoding: gzip'
  if (Test-Path -LiteralPath $curl) {
    & $curl -s --compressed -o NUL --max-time 30 "https://$HostName/server/rest/services/Hosted/NGII_GRAY_2026/VectorTileServer/tile/10/400/870.pbf"
    $ok = $LASTEXITCODE -eq 0; if (-not $ok) { $bad++ }
    Say ("  {0}  vector tile downloads and decodes" -f $(if ($ok) { 'OK ' } else { 'BAD' }))
  }
}
if ($bad) {
  Say ''
  Say "$bad check(s) failed. To undo everything right now:"
  Say "  powershell -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Undo"
  exit 1
}
Say ''
Say 'All checks passed.'
Say "Undo any time: powershell -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Undo"
