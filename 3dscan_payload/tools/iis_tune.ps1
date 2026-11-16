<#
  kgeodata.com IIS 서버 전체 설정 (2026-11-16 기술 점검) — 관리자 PowerShell 로 한 번 실행

    powershell -ExecutionPolicy Bypass -File D:\kgeoHub\tools\3dscan\iis_tune.ps1 -DryRun    # 바꿀 것만 보기 (아무것도 안 바꿈)
    powershell -ExecutionPolicy Bypass -File D:\kgeoHub\tools\3dscan\iis_tune.ps1            # 적용
    powershell -ExecutionPolicy Bypass -File D:\kgeoHub\tools\3dscan\iis_tune.ps1 -Undo      # 바로 전 상태로 되돌리기

  하는 일
    1. applicationHost.config 백업 (appcmd add backup kgeo-tune-<시각>) — -Undo 가 이것으로 되돌린다
    2. 압축: 동적 압축 기능이 없으면 설치(이때 IIS 앱 풀이 한 번 재시작 = 포털·서버 몇 초 느림), JSON·GeoJSON·glTF·SVG·manifest 를
       압축 목록 맨 앞에 추가, 정적 파일은 첫 요청부터 압축. application/octet-stream 은 넣지 않는다
       (포털 항목 내려받기 같은 큰 파일을 실시간 압축하면 느려지고 이어받기가 깨질 수 있다)
    3. https: URL Rewrite 전역 규칙 하나 — http 이고 주소가 kgeodata.com 또는 www.kgeodata.com 일 때만 https://kgeodata.com 같은 경로로 301.
       - IIS 사이트 HSTS 의 'http→https' 는 쓰지 않는다: www 는 https 가 404 라(2026-11-16 확인) http://www 사용자가 깨진다
       - HSTS 머리글은 기본으로 보내지 않는다(-Hsts 로 켬): 같은 주소 3000 번 포트에 http 서비스가 있어 브라우저가 https 로 강제하면 깨진다
       - Let's Encrypt 인증 경로(/.well-known/acme-challenge/)는 넘기지 않는다
       - 다른 도메인·IP 로 들어오는 요청, 3000 번 같은 다른 포트는 건드리지 않는다
    4. 확인: http→https, www→https://kgeodata.com, JSON gzip(풀리는지 포함), 포털·서버 REST, 벡터 타일, 기록 질의
#>
param(
  [switch]$Undo,
  [switch]$DryRun,
  [switch]$SkipHttps,
  [switch]$SkipCompression,
  [switch]$Hsts,
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
    # 한국어 Windows 는 'duplicate' 대신 '중복' 으로 답한다 (2026-11-16 첫 실행이 image/svg+xml 에서 멈춘 원인)
    if ($DupOk -and $out -match 'duplicate|중복') { Say "  ..  $desc (already)"; return }
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

# ── 현재 상태 보이기: 사이트·바인딩 (HSTS 를 켤 때 쓸 사이트 = https 바인딩에 이 호스트가 있는 사이트)
$build = [Environment]::OSVersion.Version.Build
Say "Windows build $build"
$sitesXml = [xml](& $appcmd list site /config /xml)
$site = $null
foreach ($s in $sitesXml.appcmd.SITE) {
  $b = @($s.site.bindings.binding)
  Say ("Site '{0}': {1}" -f $s.'SITE.NAME', (($b | ForEach-Object { $_.protocol + ' ' + $_.bindingInformation }) -join ', '))
  if (-not $site -and ($b | Where-Object { $_.protocol -eq 'https' -and $_.bindingInformation -match ":443:$([regex]::Escape($HostName))$" })) { $site = $s.'SITE.NAME' }
}
if (-not $site) {
  foreach ($s in $sitesXml.appcmd.SITE) { if (@($s.site.bindings.binding) | Where-Object { $_.protocol -eq 'https' -and $_.bindingInformation -match ':443:$' }) { $site = $s.'SITE.NAME'; break } }
}
$rewriteOk = Test-Path -LiteralPath (Join-Path $env:windir 'system32\inetsrv\rewrite.dll')
if (-not $SkipHttps -and -not $rewriteOk) { throw 'URL Rewrite module is not installed - run again with -SkipHttps, or install URL Rewrite first' }

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
    if ($DryRun) { Say '  [DRY] install Web-Dyn-Compression (IIS app pools recycle once)' } else { Install-WindowsFeature Web-Dyn-Compression | Out-Null; Say '  OK  installed Web-Dyn-Compression' }
  } elseif ($feat) { Say '  ..  dynamic compression feature already installed' }
  else { Say '  !!  could not check Web-Dyn-Compression (not Windows Server?) - continuing' }
  # 기능은 설치돼 있는데 IIS 에 모듈 등록이 없을 수 있다 (설치 뒤 -Undo 로 설정을 되돌린 경우) → 등록
  $dll = Join-Path $env:windir 'System32\inetsrv\compdyn.dll'
  $mod = (& $appcmd list module /name:DynamicCompressionModule 2>&1) -join ' '
  if ($mod -notmatch 'DynamicCompressionModule') {
    if (Test-Path -LiteralPath $dll) {
      Run 'register DynamicCompressionModule in IIS' @('install', 'module', '/name:DynamicCompressionModule', "/image:$dll") -DupOk
      $mod = (& $appcmd list module /name:DynamicCompressionModule 2>&1) -join ' '
      if (-not $DryRun -and $mod -notmatch 'DynamicCompressionModule') { Run '  enable it at server level' @('add', 'module', '/name:DynamicCompressionModule') -DupOk }
    }
    elseif ($DryRun) { Say '  [DRY] (module will be registered by the feature install)' }
    else { Say '  !!  compdyn.dll not found - dynamic compression unavailable' }
  } else { Say '  ..  DynamicCompressionModule registered' }

  # 목록 맨 앞(@start)에 넣는다: 기본 목록 끝의 */* (enabled=false) 보다 먼저 맞아야 한다. 이미 있으면 건너뛴다
  # ArcGIS 는 'application/json; charset=UTF-8' 로 보내므로 charset 이 붙은 모양도 넣는다
  $static  = @('application/json', 'application/json; charset=utf-8', 'application/geo+json', 'application/manifest+json', 'model/gltf-binary', 'image/svg+xml', 'application/xml')
  $dynamic = @('application/json', 'application/json; charset=utf-8', 'application/json;charset=utf-8', 'application/geo+json', 'application/xml')
  # 이미 있는 형식은 먼저 읽어서 건너뛴다 (기본 목록에 image/svg+xml 등이 이미 있다)
  $cfgTxt = (& $appcmd list config -section:system.webServer/httpCompression 2>&1) -join "`n"
  $blk = { param($name) $m = [regex]::Match($cfgTxt, "(?s)<$name>(.*?)</$name>"); if ($m.Success) { @([regex]::Matches($m.Groups[1].Value, 'mimeType="([^"]+)"') | ForEach-Object { $_.Groups[1].Value.ToLower() }) } else { @() } }
  $haveStatic = & $blk 'staticTypes'; $haveDynamic = & $blk 'dynamicTypes'
  foreach ($t in $static) {
    if ($haveStatic -contains $t.ToLower()) { Say "  ..  static  $t (already)"; continue }
    Run "static  += $t" @('set', 'config', '-section:system.webServer/httpCompression', "/+staticTypes.[@start,mimeType='$t',enabled='True']", '/commit:apphost') -DupOk
  }
  foreach ($t in $dynamic) {
    if ($haveDynamic -contains $t.ToLower()) { Say "  ..  dynamic $t (already)"; continue }
    Run "dynamic += $t" @('set', 'config', '-section:system.webServer/httpCompression', "/+dynamicTypes.[@start,mimeType='$t',enabled='True']", '/commit:apphost') -DupOk
  }
  Run 'static compression from the first request (frequentHitThreshold=1)' @('set', 'config', '-section:system.webServer/serverRuntime', '/frequentHitThreshold:1', '/commit:apphost')
  Run 'urlCompression static+dynamic on (server level)' @('set', 'config', '-section:system.webServer/urlCompression', '/doStaticCompression:True', '/doDynamicCompression:True', '/commit:apphost')
}

# ── 3. https: kgeodata.com·www 의 http 만 https://kgeodata.com 으로
if (-not $SkipHttps) {
  Say 'HTTPS redirect (URL Rewrite global rule kgeo-https)'
  $rules = (& $appcmd list config -section:system.webServer/rewrite/globalRules /text:*) -join "`n"
  if ($rules -match "kgeo-https") { Say '  ..  rule kgeo-https already present' }
  else {
    $sec = '-section:system.webServer/rewrite/globalRules'
    $hostPat = '^(www\.)?' + [regex]::Escape($HostName) + '(:80)?$'
    Run 'add rule kgeo-https (first in the list)' @('set', 'config', $sec, "/+[@start,name='kgeo-https',patternSyntax='ECMAScript',stopProcessing='True']", '/commit:apphost')
    Run '  match any path' @('set', 'config', $sec, "/[name='kgeo-https'].match.url:.*", '/commit:apphost')
    Run '  only plain http' @('set', 'config', $sec, "/+[name='kgeo-https'].conditions.[input='{HTTPS}',pattern='^OFF$']", '/commit:apphost')
    Run "  only host $HostName / www.$HostName" @('set', 'config', $sec, "/+[name='kgeo-https'].conditions.[input='{HTTP_HOST}',pattern='$hostPat']", '/commit:apphost')
    Run '  not the Lets Encrypt challenge path' @('set', 'config', $sec, "/+[name='kgeo-https'].conditions.[input='{REQUEST_URI}',pattern='^/\.well-known/acme-challenge/',negate='True']", '/commit:apphost')
    Run "  301 -> https://$HostName{REQUEST_URI}" @('set', 'config', $sec, "/[name='kgeo-https'].action.type:Redirect", "/[name='kgeo-https'].action.url:https://$HostName{REQUEST_URI}", "/[name='kgeo-https'].action.appendQueryString:False", "/[name='kgeo-https'].action.redirectType:Permanent", '/commit:apphost')
  }
  if ($Hsts) {
    if (-not $site) { throw 'HSTS: no https site found' }
    Say "  !!  HSTS on - browsers will also force https on other ports of $HostName (e.g. :3000) for $HstsMaxAge s"
    Run "HSTS header on site '$site' (max-age=$HstsMaxAge, no redirect)" @('set', 'config', '-section:system.applicationHost/sites',
      "/[name='$site'].hsts.enabled:True", "/[name='$site'].hsts.max-age:$HstsMaxAge", "/[name='$site'].hsts.redirectHttpToHttps:False", '/commit:apphost')
  } else { Say '  ..  HSTS header not sent (use -Hsts to turn it on)' }
}

if ($DryRun) { Say ''; Say 'Dry run only - nothing changed.'; exit 0 }

# ── 4. 확인
Say 'Checks'
Start-Sleep -Seconds 3
$curl = Join-Path $env:windir 'system32\curl.exe'
if (-not (Test-Path -LiteralPath $curl)) { Say '  !!  curl.exe not found - skipping checks'; exit 0 }
function Head($url, [string[]]$extra) { (& $curl -s -o NUL -D - --max-time 30 @extra $url) -join "`n" }
$bad = 0
function Check($label, $text, $pattern) {
  $ok = $text -match $pattern
  if (-not $ok) { $script:bad++ }
  Say ("  {0}  {1}" -f $(if ($ok) { 'OK ' } else { 'BAD' }), $label)
  if (-not $ok) { Say ('       ' + (($text -split "`n" | Select-Object -First 6) -join ' | ')) }
}
if (-not $SkipHttps) {
  Check 'http://kgeodata.com -> https' (Head "http://$HostName/app/3dscan/?x=1" @()) "(?mi)^HTTP/\S+ 301[\s\S]*^Location: https://$([regex]::Escape($HostName))/app/3dscan/\?x=1"
  Check 'http://www -> https://kgeodata.com' (Head "http://www.$HostName/app/3dscan/" @()) "(?mi)^HTTP/\S+ 301[\s\S]*^Location: https://$([regex]::Escape($HostName))/app/3dscan/"
  Check 'acme path not redirected' (Head "http://$HostName/.well-known/acme-challenge/kgeo-probe" @()) '(?m)^HTTP/\S+ (404|200)'
}
Check 'site page 200' (Head "https://$HostName/app/3dscan/" @()) '(?m)^HTTP/\S+ 200'
Check 'portal 200/302' (Head "https://$HostName/portal/home/" @()) '(?m)^HTTP/\S+ (200|302)'
Check 'server REST 200' (Head "https://$HostName/server/rest/info?f=json" @()) '(?m)^HTTP/\S+ 200'
if (-not $SkipCompression) {
  Check 'basemap style JSON is gzip' (Head "https://$HostName/server/rest/services/Hosted/NGII_GRAY_2026/VectorTileServer/resources/styles/root.json" @('-H', 'Accept-Encoding: gzip')) '(?mi)^Content-Encoding: gzip'
  Check 'site manifest.json is gzip' (Head "https://$HostName/app/3dscan/manifest.json" @('-H', 'Accept-Encoding: gzip')) '(?mi)^Content-Encoding: gzip'
  $j = (& $curl -s --compressed --max-time 30 "https://$HostName/server/rest/services/Hosted/scan_points/FeatureServer/0/query?where=1%3D1&returnCountOnly=true&f=json") -join ''
  $ok = $j -match '"count"'; if (-not $ok) { $bad++ }
  Say ("  {0}  feature query JSON decodes ({1})" -f $(if ($ok) { 'OK ' } else { 'BAD' }), $j.Substring(0, [Math]::Min(60, $j.Length)))
  & $curl -s --compressed -o NUL --max-time 30 "https://$HostName/server/rest/services/Hosted/NGII_GRAY_2026/VectorTileServer/tile/10/400/870.pbf"
  $ok = $LASTEXITCODE -eq 0; if (-not $ok) { $bad++ }
  Say ("  {0}  vector tile downloads and decodes" -f $(if ($ok) { 'OK ' } else { 'BAD' }))
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
