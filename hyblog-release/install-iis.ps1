param([Parameter(Mandatory=$true)][string]$SourceRoot,[Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{40}$')][string]$SourceCommit)
$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
if($env:COMPUTERNAME -ne 'KGO-GIS'){throw 'Unexpected server'}
$taskWeb='D:\codesolution\kgeodata';$taskTarget=Join-Path $taskWeb 'hyblog';$taskRelease='D:\services\hyblog';$taskData=Join-Path $taskRelease 'data'
$taskPython='C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe'
if(-not(Test-Path -LiteralPath $taskPython)){throw 'Existing CGI Python runtime unavailable'}
foreach($p in @($taskWeb,$taskTarget,$taskRelease,$taskData)){if((Test-Path -LiteralPath $p) -and ((Get-Item -LiteralPath $p).Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'Unexpected reparse point'}}
if([IO.Path]::GetFullPath($taskTarget) -ne 'D:\codesolution\kgeodata\hyblog'){throw 'Target boundary mismatch'}
$taskPrior=Join-Path $taskTarget 'deployment.json'
if(Test-Path -LiteralPath $taskTarget){if(-not(Test-Path -LiteralPath $taskPrior)){throw 'Unmanaged existing target'};if((Get-Content -LiteralPath $taskPrior -Raw|ConvertFrom-Json).application -ne 'hyblog'){throw 'Wrong existing app'}}
$taskFiles=@('index.html','app.js','style.css','mark.svg','enhancements.js','gifenc.js','gifenc-LICENSE.txt','api.py','web.config')
foreach($f in $taskFiles){if(-not(Test-Path -LiteralPath (Join-Path $SourceRoot ('dist\'+$f)))){throw ('Missing release asset: '+$f)}}
& $taskPython -c "import pathlib; compile(pathlib.Path(r'$SourceRoot\dist\api.py').read_text(encoding='utf-8'),'api.py','exec'); import sqlite3, json, hashlib"
if($LASTEXITCODE -ne 0){throw 'Queue code check failed'}
if($env:HYBLOG_WORKER_HASH -notmatch '^[a-f0-9]{64}$'){throw 'Worker verifier missing'}
New-Item -ItemType Directory -Path $taskData -Force|Out-Null
$taskConfig=Join-Path $taskData 'config.json'
if(Test-Path -LiteralPath $taskConfig){if((Get-Content -LiteralPath $taskConfig -Raw|ConvertFrom-Json).workerHash -ne $env:HYBLOG_WORKER_HASH){throw 'Existing worker identity differs; no automatic rotation'}}else{[IO.File]::WriteAllText($taskConfig,(@{workerHash=$env:HYBLOG_WORKER_HASH}|ConvertTo-Json),[Text.UTF8Encoding]::new($false))}
$env:HYBLOG_WORKER_HASH=$null
& icacls.exe $taskData /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-20:(OI)(CI)M' '*S-1-5-32-568:(OI)(CI)M' '*S-1-5-17:(OI)(CI)M'|Out-Null
if($LASTEXITCODE -ne 0){throw 'Private queue permission setup failed'}
$taskLock=[IO.File]::Open((Join-Path $taskRelease 'deploy.lock'),[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
$taskRun=[Guid]::NewGuid().ToString('N');$taskStage=Join-Path $taskRelease ('stage-'+$taskRun);$taskBackup=Join-Path $taskRelease ('backup-'+$taskRun);$taskFailed=Join-Path $taskRelease ('failed-'+$taskRun)
foreach($p in @($taskStage,$taskBackup,$taskFailed)){if(-not([IO.Path]::GetFullPath($p).StartsWith($taskRelease+'\',[StringComparison]::OrdinalIgnoreCase))){throw 'Release boundary mismatch'}}
$taskOldMoved=$false;$taskNewMoved=$false
try{
 New-Item -ItemType Directory -Path $taskStage|Out-Null
 $taskHashes=@()
 foreach($f in $taskFiles){$taskSrc=Join-Path $SourceRoot ('dist\'+$f);$taskDst=Join-Path $taskStage $f;Copy-Item -LiteralPath $taskSrc -Destination $taskDst;$taskHash=(Get-FileHash -LiteralPath $taskSrc -Algorithm SHA256).Hash.ToLowerInvariant();if((Get-FileHash -LiteralPath $taskDst -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskHash){throw 'Checksum mismatch'};if($f -notin @('api.py','web.config')){$taskHashes+=@{path=$f;sha256=$taskHash}}}
 [IO.File]::WriteAllText((Join-Path $taskStage 'deployment.json'),(@{application='hyblog';sourceCommit=$SourceCommit;deployedAt=[DateTime]::UtcNow.ToString('o');access='public-ui-approved-devices-for-generation';files=$taskHashes}|ConvertTo-Json -Depth 6),[Text.UTF8Encoding]::new($false))
 & icacls.exe $taskStage /grant '*S-1-5-32-568:(OI)(CI)RX' '*S-1-5-17:(OI)(CI)RX'|Out-Null
 if($LASTEXITCODE -ne 0){throw 'IIS asset permission failed'}
 if(Test-Path -LiteralPath $taskTarget){Move-Item -LiteralPath $taskTarget -Destination $taskBackup;$taskOldMoved=$true}
 Move-Item -LiteralPath $taskStage -Destination $taskTarget;$taskNewMoved=$true
 $taskBase='https://kgeodata.com/app/hyblog/'
 $taskLive=Invoke-RestMethod -Uri ($taskBase+'deployment.json?v='+$taskRun) -TimeoutSec 30
 if($taskLive.sourceCommit -ne $SourceCommit){throw 'Public revision mismatch'}
 $taskHealth=Invoke-RestMethod -Uri ($taskBase+'api.py?route=%2Fapi%2Fhealth&v='+$taskRun) -TimeoutSec 30
 if($taskHealth.application -ne 'hyblog'){throw 'Queue handler did not execute'}
 $taskPage=Invoke-WebRequest -UseBasicParsing -Uri $taskBase -TimeoutSec 30
 if($taskPage.StatusCode -ne 200 -or $taskPage.Content -notmatch './app.js'){throw 'Page check failed'}
 $taskStatus=Invoke-RestMethod -Uri ($taskBase+'api.py?route=%2Fapi%2Fstatus') -TimeoutSec 30
 if(-not $taskStatus.authRequired -or $taskStatus.ready){throw 'Anonymous generation is not blocked'}
 $taskDenied=0;try{$taskResponse=Invoke-WebRequest -UseBasicParsing -Uri ($taskBase+'api.py?route=%2Fworker%2Fpairs');$taskDenied=[int]$taskResponse.StatusCode}catch{if($_.Exception.Response){$taskDenied=[int]$_.Exception.Response.StatusCode}}
 if($taskDenied -ne 403){throw 'Worker route auth failed'}
 @{installed=$true;httpVerified=$true;sourceCommit=$SourceCommit;anonymousBlocked=$true;backup=if($taskOldMoved){$taskBackup}else{$null}}|ConvertTo-Json
}catch{
 if($taskNewMoved -and (Test-Path -LiteralPath $taskTarget)){Move-Item -LiteralPath $taskTarget -Destination $taskFailed}
 if($taskOldMoved -and (Test-Path -LiteralPath $taskBackup) -and -not(Test-Path -LiteralPath $taskTarget)){Move-Item -LiteralPath $taskBackup -Destination $taskTarget}
 throw
}finally{$taskLock.Dispose()}
