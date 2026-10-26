[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$SourceRoot,[Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{40}$')][string]$SourceCommit)
$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
if($env:COMPUTERNAME -ne 'KGO-GIS'){throw 'Unexpected server'}
$web=[IO.Path]::GetFullPath('D:\codesolution\kgeodata');$target=[IO.Path]::GetFullPath((Join-Path $web 'hyinsta'));$release=[IO.Path]::GetFullPath('D:\services\kong-library');$source=[IO.Path]::GetFullPath($SourceRoot);$dist=Join-Path $source 'dist'
if($target -ne "$web\hyinsta" -or $release.StartsWith($web+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Boundary mismatch'}
if(-not(Test-Path -LiteralPath $web -PathType Container)){throw 'Web root missing'}
foreach($p in @($web,$target,$release)){if((Test-Path -LiteralPath $p) -and ((Get-Item -LiteralPath $p).Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'Reparse point rejected'}}
$metadata=Join-Path $target 'deployment.json'
if(Test-Path -LiteralPath $target){if(-not(Test-Path -LiteralPath $metadata)){throw 'Unmanaged target exists'};$old=Get-Content -LiteralPath $metadata -Raw|ConvertFrom-Json;if($old.application -ne 'kong-library'){throw 'Wrong application'}}
foreach($f in @('index.html','app.js','styles.css','favicon.svg','data\library.json')){if(-not(Test-Path -LiteralPath (Join-Path $dist $f))){throw "Missing asset $f"}}
$data=Get-Content -LiteralPath (Join-Path $dist 'data\library.json') -Raw -Encoding UTF8|ConvertFrom-Json
if($data.version -ne 1 -or @($data.items).Count -gt 2000){throw 'Invalid feed'}
New-Item -ItemType Directory -Path $release -Force|Out-Null
$lock=[IO.File]::Open((Join-Path $release 'deployment.lock'),[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
$run=[Guid]::NewGuid().ToString('N');$stage=[IO.Path]::GetFullPath((Join-Path $release ('stage-'+$run)));$backup=[IO.Path]::GetFullPath((Join-Path $release ('backup-'+$run)));$failed=[IO.Path]::GetFullPath((Join-Path $release ('failed-'+$run)))
foreach($p in @($stage,$backup,$failed)){if(-not $p.StartsWith($release+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Release boundary mismatch'}}
$oldMoved=$false;$newMoved=$false
try{
 if(Test-Path -LiteralPath $target){$current=Get-Content -LiteralPath $metadata -Raw|ConvertFrom-Json;if($current.application -ne 'kong-library' -or $current.sourceCommit -ne $old.sourceCommit){throw 'Target changed'}}
 New-Item -ItemType Directory -Path $stage|Out-Null
 $manifest=@()
 foreach($asset in Get-ChildItem -LiteralPath $dist -File -Recurse){
  if($asset.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Asset reparse rejected'}
  $relative=$asset.FullName.Substring($dist.TrimEnd('\').Length+1).Replace('\','/')
  if($relative -notmatch '^(index\.html|app\.js|styles\.css|favicon\.svg|data/library\.json|images/[a-f0-9]{24}\.jpg|fonts/(PretendardVariable\.woff2|OFL\.txt)|brand/hayeon-charms\.png)$'){throw 'Asset not allowlisted'}
  $dest=[IO.Path]::GetFullPath((Join-Path $stage $relative));if(-not $dest.StartsWith($stage+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Asset boundary mismatch'}
  New-Item -ItemType Directory -Path (Split-Path $dest -Parent) -Force|Out-Null;Copy-Item -LiteralPath $asset.FullName -Destination $dest
  $hash=(Get-FileHash -LiteralPath $asset.FullName -Algorithm SHA256).Hash.ToLowerInvariant();if((Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash.ToLowerInvariant() -ne $hash){throw 'Copy checksum mismatch'}
  $manifest+=@{path=$relative;sha256=$hash}
 }
 Copy-Item -LiteralPath (Join-Path $source 'deploy\web.config') -Destination (Join-Path $stage 'web.config')
 $receipt=@{application='kong-library';sourceCommit=$SourceCommit;deployedAt=[DateTime]::UtcNow.ToString('o');access='public';itemCount=@($data.items).Count;files=$manifest}
 [IO.File]::WriteAllText((Join-Path $stage 'deployment.json'),($receipt|ConvertTo-Json -Depth 6),[Text.UTF8Encoding]::new($false))
 & icacls.exe $stage /grant '*S-1-5-32-568:(OI)(CI)RX' '*S-1-5-17:(OI)(CI)RX'|Out-Null;if($LASTEXITCODE -ne 0){throw 'IIS read access failed'}
 if(Test-Path -LiteralPath $target){Move-Item -LiteralPath $target -Destination $backup;$oldMoved=$true}
 Move-Item -LiteralPath $stage -Destination $target;$newMoved=$true
 $base='https://kgeodata.com/app/hyinsta/'
 $remote=Invoke-RestMethod -Uri ($base+'deployment.json?verify='+$run) -TimeoutSec 30
 if($remote.sourceCommit -ne $SourceCommit){throw 'HTTP revision mismatch'}
 $page=Invoke-WebRequest -UseBasicParsing -Uri ($base+'?verify='+$run) -TimeoutSec 30
 if($page.StatusCode -ne 200 -or $page.Content -notmatch 'HAYEON'){throw 'HTTP page failed'}
 $feed=Invoke-RestMethod -Uri ($base+'data/library.json?verify='+$run) -TimeoutSec 30
 if(@($feed.items).Count -ne @($data.items).Count){throw 'HTTP feed mismatch'}
 # Redirect only the identified earlier library; do not change any other IIS app.
 $legacy=[IO.Path]::GetFullPath((Join-Path $web 'kong'))
 if($legacy -ne "$web\kong"){throw 'Legacy boundary mismatch'}
 if(Test-Path -LiteralPath (Join-Path $legacy 'deployment.json')){
  if((Get-Item -LiteralPath $legacy).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Legacy reparse rejected'}
  $legacyMeta=Get-Content -LiteralPath (Join-Path $legacy 'deployment.json') -Raw|ConvertFrom-Json
  if($legacyMeta.application -eq 'kong-library'){
   $index=Join-Path $legacy 'index.html';$savedIndex=[IO.Path]::GetFullPath((Join-Path $release ('legacy-index-'+$run+'.html')))
   if(-not $savedIndex.StartsWith($release+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Legacy backup boundary mismatch'}
   Copy-Item -LiteralPath $index -Destination $savedIndex
   [IO.File]::WriteAllText($index,'<!doctype html><html lang="ko"><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=https://kgeodata.com/app/hyinsta/"><title>HAYEON - moved</title><a href="https://kgeodata.com/app/hyinsta/">HAYEON</a></html>',[Text.UTF8Encoding]::new($false))
  }
 }
 @{installed=$true;sourceCommit=$SourceCommit;items=@($feed.items).Count;httpVerified=$true;backup=if($oldMoved){$backup}else{$null}}|ConvertTo-Json
}catch{
 if($newMoved -and (Test-Path -LiteralPath $target)){Move-Item -LiteralPath $target -Destination $failed}
 if($oldMoved -and (Test-Path -LiteralPath $backup) -and -not(Test-Path -LiteralPath $target)){Move-Item -LiteralPath $backup -Destination $target}
 throw
}finally{$lock.Dispose()}
