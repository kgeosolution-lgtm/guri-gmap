# IIS 자동 배포: 구리 미리보기

## 확인된 서버 연결

사용자가 원격 서버에서 조회한 결과(2026-09-11):

- IIS: Default Web Site, HTTPS kgeodata.com:443
- 기존 가상 디렉터리 /app → D:\codesolution\kgeodata
- 배포 대상 D:\codesolution\kgeodata\guri 존재
- 공개 주소 https://kgeodata.com/app/guri/

기존 IIS 사이트·ArcGIS 응용 프로그램·/app 연결은 수정하지 않습니다. 하위 폴더의 web.config만 배포합니다.

## 동작

`design/service-home-refresh` push → GitHub hosted runner에서 npm ci 및 build:deploy → 빌드 성공 시 Windows 서버 실행기가 결과를 내려받아 배포합니다. 서비스 등록 이후에는 원격 데스크톱을 닫아도 실행기가 동작합니다. 서버가 인터넷으로 GitHub HTTPS에 연결할 수 있어야 합니다. 인바운드 FTP/SSH 포트를 새로 열 필요는 없습니다.

서버 실행기 라벨은 `guri-preview`, 저장소는 `kgeosolution-lgtm/guri-gmap` 전용입니다. workflow_dispatch로 수동 재배포도 가능합니다. 다른 브랜치나 PR 코드는 서버에서 자동 실행하지 않습니다. main 병합 시 배포 브랜치 조건도 명시적으로 변경해야 합니다.

## 서버 최초 설치

1. GitHub 저장소 Settings → Actions → Runners → New self-hosted runner를 엽니다. Windows / x64를 선택합니다.
2. 원격 서버의 관리자 PowerShell에서 `D:\actions-runner-guri` 폴더를 만들고 그곳으로 이동합니다. 웹 공개 폴더 안에는 설치하지 않습니다.
3. GitHub 화면의 Download 명령을 순서대로 실행합니다. 버전·다운로드 주소·검증 명령은 GitHub가 현재 제공하는 값을 그대로 사용합니다.
4. Configure 명령은 GitHub 화면에서 복사하되 아래 옵션을 추가합니다.

```text
--name kgeodata-guri --labels guri-preview --work _work --runasservice
```

GitHub가 발급한 등록 토큰은 해당 원격 서버 터미널에만 입력하세요. 채팅·문서·Git에 저장하지 않습니다. 서비스 계정 질문에는 가능한 한 전용 일반 계정을 사용하세요. 그 계정에는 runner 설치 폴더, `D:\codesolution\kgeodata\guri`, `D:\guri-deploy-backups`의 수정 권한이 필요합니다. IIS 읽기 권한은 기존 /app 접근 계정을 기준으로 확인합니다. 서버 전체에 Everyone/FullControl을 부여하지 않습니다.

5. 서비스 설치 후 GitHub Runners 화면에서 Idle 상태와 `guri-preview` 라벨을 확인합니다. 서비스가 멈춰 있으면 Windows 서비스 관리에서 해당 GitHub Actions Runner 서비스를 시작합니다. 콘솔 run.cmd만 실행하면 로그아웃 시 지속 실행을 보장하지 않습니다.
6. 저장소 Actions → Guri IIS preview → 최신 실행을 확인합니다. 실행이 실패하거나 대기 시간이 만료됐다면 해당 실행의 Re-run jobs로 재실행합니다. 기본 브랜치에 workflow가 없으면 Run workflow 버튼이 보이지 않을 수 있습니다.
7. 공개 홈·테마지도·유기동물 및 `https://kgeodata.com/app/guri/deployment.json`의 commit이 Actions 실행 커밋과 같은지 확인합니다.

실행기 계정/폴더 권한은 실제 서버에서 아직 설정·검증하지 않았습니다. GitHub Actions 사용 가능 여부와 조직 정책도 실제 실행 결과를 확인해야 합니다.

## 배포 및 복구

- 원본 소스/.git/node_modules는 웹 폴더에 복사하지 않습니다.
- 빌드 결과에만 /app/guri 하위 자산·링크 경로를 반영합니다. 로컬 npm run dev는 기존 / 경로입니다.
- 기존 파일은 웹 루트 밖 `D:\guri-deploy-backups\시각`에 백업합니다.
- 새 자산을 먼저 복사하고 index.html을 나중에 복사합니다. 삭제/purge는 하지 않아 기존 탭의 해시 자산을 보존합니다. 전체 교체가 원자적이지는 않으므로 배포 순간의 정적 지도 파일 교체는 발생할 수 있습니다.
- 실패 시 이전 index.html이 있는 백업을 복원합니다. 첫 배포에는 이전 정상본이 없어 자동 복구할 버전이 없습니다. 실패 원인을 고친 후 재실행합니다.
- 백업과 이전 해시 자산은 누적됩니다. 용량을 확인하고 검증된 이전 버전을 남기는 정리 정책을 추후 적용하세요.
- web.config 관련 500.19/잠긴 섹션 오류가 나면 사이트 전체 잠금을 해제하지 말고 해당 IIS 오류의 정확한 섹션과 상위 설정을 확인합니다.

## 로컬 검증

```bash
npm run build:deploy
```

`out`은 배포 결과물로 Git 제외 대상입니다. 이 명령은 IIS에 접속하거나 배포하지 않습니다. 실제 자동 배포 완료 여부는 Actions 성공 + 공개 URL 검증으로 판단합니다.
