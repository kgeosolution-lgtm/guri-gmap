# kgeoScan 큐 러너 작업 스케줄러 등록 — 서버(KGO-GIS)에서 관리자 PowerShell 로 1회 실행
# 러너는 kgo 계정으로 돌아야 한다 (ArcGIS Pro 라이선스가 그 계정에 있음). 실행하면 kgo 비밀번호를 묻는다.
$TaskName = 'kgeoScanQueueRunner'
$Python   = 'D:\kgeoHub\tools\3dscan\venv\Scripts\python.exe'
$Script   = 'D:\kgeoHub\tools\3dscan\queue_runner.py'
$User     = 'kgo'

if (-not (Test-Path $Python)) { throw "python 없음: $Python (배포 워크플로가 venv 를 만들었는지 확인)" }
if (-not (Test-Path $Script)) { throw "스크립트 없음: $Script" }

$cred = Get-Credential -UserName $User -Message "작업 스케줄러에 등록할 $User 계정 비밀번호"
$pw   = $cred.GetNetworkCredential().Password

schtasks /delete /tn $TaskName /f 2>$null | Out-Null
schtasks /create /tn $TaskName /tr "`"$Python`" -I `"$Script`"" /sc ONLOGON /ru $User /rp $pw /rl HIGHEST /f
if ($LASTEXITCODE -ne 0) { throw '등록 실패 — 관리자 PowerShell 인지 확인' }
schtasks /run /tn $TaskName | Out-Null
Start-Sleep -Seconds 5
"등록·시작 완료: $TaskName"
Get-Content 'D:\kgeoHub\data\3dscan\logs\queue_runner.log' -Tail 5 -ErrorAction SilentlyContinue
