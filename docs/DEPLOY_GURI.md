# 구리시 생활지도 — 서버 이관 절차 (10.9 → 12.1 전환, https://www.guri.go.kr/gmapweb/)

담당: 강민아 · 2026-11-17 · 대상 주소 `https://www.guri.go.kr/gmapweb/`

## 0. 한눈에 보는 상황

- 구리시가 ArcGIS Enterprise 를 **10.9(옛 장비) → 12.1(새 장비)** 로 바꾼다. 장비 자체가 달라진다.
- 레이어·3D 웹씬·연속지적도는 모두 **12.1 포털에 이미 발행**돼 있고, 생활지도 코드도 12.1 을 보도록 돼 있다(서비스 이름·아이템 ID·웹씬 ID·스케줄러 대상 전부 12.1 기준). 전환 때 바뀌는 것은 **외부 접속 경로(DNS·방화벽)뿐**이다.
- **수요일(11-18)**: 새 12.1 서버(GMAP-WEB)에 생활지도 파일을 미리 배치하고 hosts 로 검증(외부 공개 전).
- **다음 주**: 구리시가 외부 DNS·방화벽을 12.1 로 전환 → 생활지도·레이어가 한꺼번에 공개. 시민은 전환 전까지 옛 10.9 의 생활지도를 그대로 본다(무중단).

생활지도는 **정적 웹사이트**(HTML·JS·이미지)다. 서버 프로그램·DB 가 없고, 자료는 구리 포털(`/gmapsvr` 호스팅 서비스, `/gmap` 3D 웹씬)에서 그대로 읽는다. 넣을 것은 빌드 결과 한 묶음(약 6MB + 사진 50장)뿐이다.

```
[시민] ──HTTPS──▶ GMAP-WEB (DMZ, IIS, 새 12.1 장비)
                    ├─ /gmap      Web Adaptor → Portal 12.1
                    ├─ /gmapsvr   Web Adaptor → ArcGIS Server 12.1 (호스팅 자료)
                    └─ /gmapweb   ★ 생활지도 정적 파일 (기존 것을 새 사이트로 교체)
```

### 이미 끝난 것 (2026-11-17 기준)

| 항목                                             | 상태                                                                        |
| ------------------------------------------------ | --------------------------------------------------------------------------- |
| 외부 키 도메인 등록(NGII·브이월드·카카오 로드뷰) | 완료 가정 — 키 값 변동 없음, 코드 수정 없음                                 |
| 지도 엔진 CDN(`js.arcgis.com`)                   | 구리시가 허용                                                               |
| 글꼴(와구리체·Pretendard GOV)                    | `public/fonts/` 자체 호스팅, 배포 브랜치에 병합(#131)                       |
| 연속지적도                                       | 12.1 호스팅 `LSMD_CONT_LDREG_41310` 로 교체(#130), 공개 완료                |
| 사진 50장                                        | `public/images/pet/` 에 복사, 빌드·zip 완료(`gmapweb-20261117-bea965a.zip`) |
| 코드 점검                                        | 9장 — kgeodata·`/app/guri` 잔존 없음(주석만), 캐시·robots 보강              |

## 1. 전체 순서

| 단계                    | 언제        | 어디서               | 할 일                                               | 절      |
| ----------------------- | ----------- | -------------------- | --------------------------------------------------- | ------- |
| ① 빌드 → zip            | 완료        | 사무실               | `npm run build:guri` → `dist/gmapweb-날짜-커밋.zip` | 2-1     |
| ② zip 포털 업로드 + USB | 화요일      | 사무실(포털)         | 콘텐츠 > 새 항목 > 파일, USB 예비                   | 2-2     |
| ③ 장비 확인             | 수요일 현장 | GMAP-WEB             | 12.1 장비가 맞는지, IIS 구조 확인                   | 3-0     |
| ④ 기존 /gmapweb 백업    | 수요일 현장 | GMAP-WEB             | 실제 경로 확인, 폴더 통째 복사                      | 3-1     |
| ⑤ 새 사이트 배치        | 수요일 현장 | GMAP-WEB             | zip 내려받아 새 폴더에 풀고 실제 경로 변경          | 3-2     |
| ⑥ 캐시·MIME·404         | 수요일 현장 | GMAP-WEB             | 응답 헤더 확인, 404 지정(선택)                      | 3-3·3-4 |
| ⑦ 서버에서 1차 확인     | 수요일 현장 | GMAP-WEB             | hosts 로 접속, deployment.json                      | 3-5     |
| ⑧ 레이어 공개 확인      | 수요일 현장 | 브라우저             | 호스팅 서비스·웹씬·연속지적도 공개, 스케줄러        | 4       |
| ⑨ 검증                  | 수요일 현장 | 노트북·휴대폰(hosts) | 체크리스트 13항목                                   | 5       |
| ⑩ 전환 공개             | 다음 주     | 구리시               | 외부 DNS·방화벽을 12.1 로 → LTE 재검증              | 6       |

## 2. 사전 준비 (사무실)

### 2-1. 빌드 → zip (`npm run build:guri`) — 완료

설정은 `deploy.guri.json` 한 파일(origin `https://www.guri.go.kr`, base `/gmapweb`, photoBase `/images/pet/`, reviewWidget false, zip true). `deploy.config.json`(kgeodata 미리보기)과 `site.config.ts` 는 건드리지 않는다.

```
cd D:\work\guri-gmap
git checkout design/service-home-refresh
git pull
npm ci
npm run build:guri
```

끝에 세 줄이 나와야 한다. `[경고] 사진 폴더…` 가 보이면 `public\images\pet\` 에 사진이 없는 것이다.

```
Static deployment ready: out -> https://www.guri.go.kr/gmapweb/
검토 위젯(review.js) 제거됨
zip: dist/gmapweb-20261117-bea965a.zip
```

결과 확인: `dir out\images\pet`(사진 50), `type out\deployment.json`(`url` 이 gmapweb, `config` 가 `deploy.guri.json`), `out\fonts\waguri.woff2` 있음.

확인 ☑ 빌드 3줄 ☑ 사진 50 ☑ zip: `gmapweb-20261117-bea965a.zip`

### 2-2. zip 전달 — 포털 업로드 + USB

1. 구리 포털 `https://www.guri.go.kr/gmap`(hosts 로 접속) 로그인 → **콘텐츠 > 새 항목 > 파일** → zip 선택. 유형은 자동("코드 샘플")이면 그대로, 제목은 파일명 그대로.
2. **공유는 본인·구리시 담당자에게만**(공개 금지).
3. 같은 zip 을 USB 에도 복사(현장에서 포털 다운로드가 막힐 때 예비).

포털은 파일을 보관만 하고 사이트를 서비스하지는 못하므로 3 장의 배치 작업은 그대로 필요하다.

확인 □ 포털 항목(제목: ______________) □ USB

### 2-3. 챙겨 갈 것

- 이 문서 인쇄본, USB(예비 zip)
- 노트북(hosts 편집 가능한 관리자 권한) + 휴대폰(와이파이, hosts 는 노트북 테더링 또는 구리시 내부 무선망)
- 구리시 담당자 연락처, GMAP-WEB 관리자 권한자·포털 관리자 동석
- **12.1 DMZ 서버의 IP**(hosts 에 넣을 값) — 담당자에게 미리 받아 둔다: ______________

## 3. 현장 — GMAP-WEB (IIS, 새 12.1 장비) · 약 40분

관리자 권한으로 로그인한다. **사이트·Web Adaptor·`/gmap`·`/gmapsvr` 설정은 건드리지 않는다.** `gmapweb` 응용 프로그램의 **콘텐츠(실제 경로)만** 바꾼다.

### 3-0. 이 장비가 12.1 이 맞는지 (5분)

옛 10.9 장비를 건드리지 않기 위해 먼저 확인한다.

1. 서버 브라우저로 `https://localhost/gmap/home/`(인증서 경고는 "계속")을 열어 로그인 → 오른쪽 위 **조직 > 설정** 또는 화면 아래 **정보**에서 버전이 **12.1** 인지 본다. 더 빠르게는 `https://localhost/gmap/sharing/rest?f=json` 의 `currentVersion` 값이 12.x 이면 된다.
2. **IIS 관리자**(시작 → "IIS" 검색 → 인터넷 정보 서비스(IIS) 관리자) → 왼쪽 트리 **서버명 > 사이트 > Default Web Site**(또는 www.guri.go.kr 인증서가 바인딩된 사이트)를 펼친다. 아래에 `gmap`, `gmapsvr`(Web Adaptor), `gmapweb` 세 응용 프로그램이 보여야 한다.
3. 사이트 선택 → 오른쪽 **바인딩…** → `https` 443 에 `www.guri.go.kr` 인증서가 걸려 있는지 본다.

확인 □ 포털 버전 12.1 □ gmap·gmapsvr·gmapweb 응용 프로그램 □ 443 바인딩

### 3-1. 기존 /gmapweb 백업 (5분)

1. IIS 관리자 → `gmapweb` 선택 → 오른쪽 작업 창 **기본 설정…** → **실제 경로** 를 적는다. 예: `D:\www\gmapweb`. 이 창의 **응용 프로그램 풀** 이름도 적어 둔다(바꾸지 않는다).
2. 파일 탐색기로 그 폴더의 **상위 폴더**를 열고, 폴더를 복사해 이름을 `gmapweb_backup_20261118` 로 붙여 넣는다. 용량이 크면(수백 MB 이상) 웹 루트 밖(예: `D:\backup\`)에 둔다.
   - PowerShell 로 하려면(관리자): `Copy-Item 'D:\www\gmapweb' 'D:\www\gmapweb_backup_20261118' -Recurse`
3. 기존 폴더의 `web.config` 를 메모장으로 열어 본다. `<rewrite>`·`<handlers>`·`<httpErrors>` 처럼 **다른 서비스가 기대는 설정**이 있으면 담당자에게 묻는다. 새 사이트는 정적 파일이라 우리 `web.config`(기본 문서·MIME·캐시)로 충분하다.

확인 □ 실제 경로: `______________` □ 응용 프로그램 풀: `__________` □ 백업 폴더 □ web.config 확인

### 3-2. 새 폴더에 배치 → 실제 경로 변경 (15분)

되돌리기가 쉬운 **새 폴더 + 실제 경로 변경** 방식을 쓴다. 기존 폴더는 손대지 않는다.

**(1) zip 내려받기**

1. 서버 브라우저로 `https://localhost/gmap/home/`(또는 hosts 를 잡고 `https://www.guri.go.kr/gmap/home/`) 로그인 → **콘텐츠 > 내 콘텐츠** → 2-2 에서 올린 항목 → **다운로드**. 기본 저장 위치는 `다운로드` 폴더.
2. 포털 다운로드가 막히면 USB 의 zip 을 쓴다.
3. 파일 크기가 사무실 zip 과 같은지 확인(탐색기 속성). 다르면 다시 받는다.

**(2) 새 폴더에 풀기**

1. 새 폴더를 만든다: `D:\www\gmapweb_20261118` (기존 폴더와 같은 상위 폴더, Web Adaptor 폴더 안이나 `inetpub\wwwroot` 안은 피한다).
2. zip 우클릭 → **압축 풀기…** → 대상에 `D:\www\gmapweb_20261118` 를 넣고 푼다.
   - PowerShell: `Expand-Archive -Path "$env:USERPROFILE\Downloads\gmapweb-20261117-bea965a.zip" -DestinationPath 'D:\www\gmapweb_20261118'`
3. **한 겹 더 들어가지 않았는지** 본다: `D:\www\gmapweb_20261118\` 바로 아래에 `index.html`, `web.config`, `maps\`, `images\`, `fonts\`, `deployment.json` 이 보여야 한다. `gmapweb_20261118\gmapweb-…\index.html` 처럼 한 겹 더 있으면 안쪽 내용을 위로 올린다.
4. `images\pet\` 에 사진 50개, `fonts\` 에 `waguri.woff2` 가 있는지 본다.

**(3) 폴더 권한**

1. 새 폴더 우클릭 → **속성 > 보안** 탭 → 그룹 또는 사용자 이름에 `IIS_IUSRS` 가 있고 **읽기 및 실행·폴더 내용 보기·읽기** 에 체크돼 있는지 본다.
2. 없으면 **편집 > 추가** → 이름에 `IIS_IUSRS` 입력 → 이름 확인 → 확인 → 위 세 권한 체크 → 확인.
   - 보통 상위 폴더(`D:\www`)에서 상속되므로 기존 폴더의 보안 탭과 같게 맞추면 된다.

**(4) 실제 경로 변경**

1. IIS 관리자 → `gmapweb` 선택 → 오른쪽 **기본 설정…** → **실제 경로** 를 `D:\www\gmapweb_20261118` 로 바꾼다.
2. 같은 창의 **설정 테스트…** → "인증", "권한 부여" 두 줄이 모두 녹색 체크인지 본다. 권한 부여가 빨간색이면 (3) 을 다시 본다(`IIS_IUSRS` 또는 응용 프로그램 풀 ID 읽기 권한).
3. **확인**. 응용 프로그램 풀 재시작·iisreset 은 필요 없다(정적 파일).
4. 기존 폴더는 지우지 않는다(백업 = 되돌리기).

**되돌리기(1분)**: 같은 창에서 실제 경로를 원래 폴더(3-1 의 값)로 바꾸고 확인.

확인 □ zip 크기 일치 □ 새 폴더 구조(한 겹) □ 사진 50·글꼴 □ 권한 □ 실제 경로 변경 □ 설정 테스트 녹색

### 3-3. web.config — 캐시·MIME (5분)

빌드 결과에 포함돼 있어 **손으로 만들 것은 없다.** 무엇이 들어 있는지와 확인 방법만 적는다.

| 위치                                      | 내용                                                                                                                                           |
| ----------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `web.config`(루트)                        | 기본 문서 `index.html`, 디렉터리 검색 끔, MIME(`.webp .woff2 .json .svg`), **캐시 끔** — `index.html`·`deployment.json`·지도 HTML 이 항상 새것 |
| `_next\static\web.config`                 | 이름에 해시가 붙는 자산 → **1년** 캐시                                                                                                         |
| `fonts\web.config`, `maps\sym\web.config` | 글꼴·아이콘 → **7일** 캐시                                                                                                                     |

확인(서버 브라우저 F12 > 네트워크): `index.html` 응답 헤더 `Cache-Control: no-cache`, `_next/static/chunks/*.js` 는 `max-age=31536000`, `fonts/waguri.woff2` 는 `max-age=604800` 이고 Content-Type 이 `font/woff2`. `maps/data/scene.json` 이 `application/json` 으로 200.

하위 폴더 `web.config` 때문에 **500.19** 가 나면(서버 수준에서 `staticContent` 잠김): 하위 세 개 `web.config` 만 지운다(캐시만 못 할 뿐 동작엔 지장 없음). 루트 것까지 500.19 면 담당자와 `staticContent` 섹션 잠금을 확인한다 — 사이트 전체 잠금 해제는 하지 않는다.

### 3-4. 404 페이지 (선택, 5분)

1. IIS 관리자 → `gmapweb` 선택 → 가운데 **오류 페이지** 더블클릭 → 목록의 **404** 더블클릭(없으면 오른쪽 **추가…**, 상태 코드 404).
2. **이 사이트의 URL 실행** 선택 → `/gmapweb/404.html` → 확인.
3. 오른쪽 **기능 설정 편집…** → **사용자 지정 오류 페이지** 선택 → 확인.
4. 브라우저에서 `https://localhost/gmapweb/abc` → 한글 404 가 나오면 성공. **500.19** 가 나면(`httpErrors` 잠김) 1~3 을 되돌리고 생략한다.

### 3-5. 서버에서 1차 확인 (5분)

hosts 가 필요하면 메모장을 **관리자 권한으로** 열어 `C:\Windows\System32\drivers\etc\hosts` 끝에 한 줄을 넣고 저장한다(끝나면 지운다).

```
<12.1 DMZ 서버 IP>   www.guri.go.kr
```

서버 브라우저(시크릿 창)로 차례로 연다.

| 주소                                                             | 기대                                                                                                        |
| ---------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `https://www.guri.go.kr/gmapweb/deployment.json`                 | `"url": "https://www.guri.go.kr/gmapweb/"`, `"config": "deploy.guri.json"`, `commit` 이 빌드 커밋(bea965a…) |
| `https://www.guri.go.kr/gmapweb/`                                | 메인(겨울 사진)                                                                                             |
| `https://www.guri.go.kr/gmapweb/maps/theme.html?group=시즌·겨울` | 칩 건수가 0 이 아님(0 이면 4 장)                                                                            |
| `https://www.guri.go.kr/gmapweb/fonts/waguri.woff2`              | 다운로드됨(404 면 폴더 한 겹 문제)                                                                          |

확인 □ deployment.json(config=guri) □ 메인 □ 칩 건수 □ 글꼴 파일

## 4. 포털·레이어 공개 확인 (브라우저만, 파일 작업 없음)

시민은 로그인 없이 보므로 사이트가 쓰는 자료가 모두 **"모든 사용자(공개)"** 여야 한다. **시크릿 창**에서 아래가 로그인 없이 JSON 을 내면 공개된 것이다.

```
https://www.guri.go.kr/gmapsvr/rest/services/Hosted/<서비스이름>/FeatureServer?f=json
```

| 그룹          | 서비스 이름                                                                                                                                                   |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 시즌·겨울     | `winter_shelter` `winter_saltbox_new` `winter_icyroad_l` `winter_icyroad_p` `culture_dulle` `culture_dulle_fac` `culture_hiking_new` `culture_hiking_fac_new` |
| 치안안심      | `safety_all` `safety_secure_map`(1번 레이어)                                                                                                                  |
| 건강·의료     | `health_hospital` `health_lifecare` `health_pharmacy` `health_vaccine`                                                                                        |
| 생활편의      | `life_parking` `life_restroom` `life_gas` `life_evcharge_new` `life_lpg` `life_kiosk` `life_wifi` `life_mosquito`                                             |
| 우수맛집      | `restaurant_long` `restaurant_waguri`                                                                                                                         |
| 문화·여가     | `culture_park` `culture_sports` `autumn_foliage` (+ 둘레길·등산로)                                                                                            |
| 반려동물      | `pet_hospital` `pet_pharmacy` `pet_service` `pet_stray`                                                                                                       |
| 교통          | `transit_bus_p` `transit_bus_l`                                                                                                                               |
| 공통          | `구리시경계` `행정동경계`                                                                                                                                     |
| 연속지적도    | `LSMD_CONT_LDREG_41310` (아이템 `452bf1326d694183b675f6b81e6b48ee`, 공개 완료)                                                                                |
| 배경 벡터타일 | `NGII_MAP_SD_20260901` `GURI_BND` `Korea_Boundary` (`.../VectorTileServer`)                                                                                   |
| 3D            | 웹씬 `b5e573a06e7f4195bb2f092aad19b253` — `https://www.guri.go.kr/gmap/home/item.html?id=b5e573a06e7f4195bb2f092aad19b253` 이 로그인 없이 열려야 함           |

포털 **콘텐츠 > 필터 "공유: 모든 사용자"** 로 좁혀 위 목록이 다 있는지 본다. 빠진 항목은 **공유 > 모든 사용자(공개)**. 항목 **제목**은 바꿔도 되지만 **서비스 이름(URL)** 은 바꾸면 안 된다.

**스케줄러**: 포털 노트북 > 작업에서 전기차 상태갱신(10분)과 주 1회 갱신의 **마지막 실행 시각**이 최근인지 본다.

**CORS**: 사이트가 `www.guri.go.kr` 이므로 할 일 없음(같은 출처).

확인 □ 테마 서비스 전부 공개 □ 연속지적도 □ 벡터타일·경계 □ 3D 웹씬 □ 스케줄러 정상

## 5. 검증 체크리스트 (수요일: hosts 잡은 노트북·휴대폰 / 전환 후: LTE)

| #   | 확인                                                                                             | 결과 |
| --- | ------------------------------------------------------------------------------------------------ | ---- |
| 1   | `https://www.guri.go.kr/gmapweb/` 메인, 겨울 사진·'구리의 사계절' 줄                             | □    |
| 2   | 우리동네 지도 열기 → 시즌·겨울, 칩 건수 0 아님                                                   | □    |
| 3   | 칩(한파쉼터) → 목록 → 팝업, 전화·네이버 길찾기                                                   | □    |
| 4   | 반려동물 > 동물병원 팝업에 사진                                                                  | □    |
| 5   | 생활편의 > 전기차: "상태는 10분마다 새로 받아요", 건수                                           | □    |
| 6   | 첫 화면·칩 변경 때 구리시가 꽉 차게(모바일은 시트 위 영역)                                       | □    |
| 7   | 3D입체지도 열림                                                                                  | □    |
| 8   | 항공사진 비교: 타일 보임(NGII 키), 연도 전환                                                     | □    |
| 9   | 항공사진 비교 > 지도 위에 함께 보기 > 연속지적도가 구리 서버 자료로 뜸(확대해야 보임, 축척 제한) | □    |
| 10  | 제목 글씨가 와구리체, 본문 Pretendard(기본 글꼴로 보이면 글꼴 파일·MIME)                         | □    |
| 11  | 공유 단추 → 주소가 `https://www.guri.go.kr/gmapweb/...`                                          | □    |
| 12  | 메뉴에 '구리 동네소식'·'유기동물 찾기'·'수정 요청'이 **없음**                                    | □    |
| 13  | `deployment.json` commit = 빌드 커밋, config = deploy.guri.json                                  | □    |

PC 에서도 1·2·6·7·8·9·10 을 한 번 더. 브라우저 콘솔(F12)에 `[시작 화면]`, `[전체보기]`, `[웹맵]` 한글 로그가 찍히므로 어디서 멈췄는지 바로 보인다.

## 6. 전환일 (다음 주)

구리시가 외부 DNS·방화벽을 12.1 서버로 전환한다. 생활지도가 보는 대상(포털·서버·연속지적도·웹씬)은 이미 12.1 이라 바뀌지 않는다.

- 전환 전 최종 확인: 4 장 공개 공유 전부, `js.arcgis.com` 허용 적용, 생활지도 실제 경로가 **새 폴더**인지(수요일에 그대로 두고 온다).
- 전환 직후: 외부(LTE 휴대폰)에서 5 장 체크리스트를 다시 돌린다. 칩 건수 0 이면 7 장 첫 줄.
- 전환 뒤 카톡 미리보기 그림이 옛 것이면 카카오 공유 디버거에서 새로고침(캐시).

## 7. 문제가 생겼을 때

| 증상                                        | 원인                                | 조치                                                                                                     |
| ------------------------------------------- | ----------------------------------- | -------------------------------------------------------------------------------------------------------- |
| 칩 건수 전부 0, 목록 없음                   | 자료 비공개 또는 외부 미개통        | F12 > 네트워크에서 `gmapsvr` 응답 코드. 403/499 → 공유(4장), 연결 실패 → DNS·방화벽(6장)                 |
| 서버는 되는데 휴대폰 안 됨                  | 전환 전(정상)                       | 전환일 대기, hosts 로 검증                                                                               |
| 스타일 깨짐·아이콘 없음                     | zip 한 겹 더 풀림 또는 MIME         | `maps/sym/theme/*.png`, `styles/site-shell.css` 직접 열어 200 인지                                       |
| 글씨가 기본 글꼴                            | 글꼴 파일 미포함 또는 `.woff2` MIME | `fonts/waguri.woff2` 직접 열어 200·`font/woff2`                                                          |
| 지도 안 그려짐, 콘솔에 `js.arcgis.com` 차단 | CDN 미허용                          | 구리시 방화벽/CSP: `script-src`·`style-src`·`font-src`·`worker-src` 에 `js.arcgis.com`                   |
| 500.19                                      | `web.config` 섹션 서버 수준 잠김    | 오류 화면의 섹션 이름 확인. 하위 캐시 `web.config` 면 지움, 404 면 되돌림. 사이트 전체 잠금 해제는 안 함 |
| 옛 사이트가 계속 보임                       | 실제 경로 미변경 또는 캐시          | IIS 기본 설정 확인, 시크릿 창, `deployment.json` 의 `config`                                             |
| 항공사진 타일 안 보임                       | NGII 키 도메인 미등록               | 키 등록 확인                                                                                             |
| 연속지적도 안 뜸                            | 비공개 또는 축척                    | 4장 공개, 1:8,000 보다 확대                                                                              |
| 3D 안 열림                                  | 웹씬 비공개                         | 4장                                                                                                      |
| 동물병원 사진 없음                          | 사진 미포함                         | `images/pet/` 50개 확인                                                                                  |
| 수정 요청 메뉴 보임                         | `build:deploy` 로 빌드함            | `build:guri` 로 다시, `deployment.json` 의 `reviewWidget` 이 false 인지                                  |

## 8. 이후 운영 (수정이 생겼을 때)

첫 배포 뒤에는 구리시 담당자가 혼자서도 할 수 있다.

1. 사무실: `git pull` → `npm run build:guri` → `dist/gmapweb-날짜-커밋.zip`
2. 포털 > 콘텐츠 > 새 항목 > 파일로 zip 업로드(담당자에게만 공유)
3. GMAP-WEB: zip 을 **새 폴더**(예 `D:\www\gmapweb_20261125`)에 풀고(3-2 의 (2)·(3)), `gmapweb` 실제 경로를 그 폴더로 변경(3-2 의 (4)). 직전 폴더는 남겨 둔다.
4. 되돌리기: 실제 경로를 직전 폴더로.

사진·글꼴은 자주 안 바뀌므로 저장소에 한 번 넣어 두면 매번 zip 에 함께 담긴다. `guri-preview.yml` 자동 배포는 kgeodata.com 미리보기용으로 계속 쓴다.

## 9. 코드 점검 결과 (2026-11-17, 이관 대비)

| 점검                                     | 결과                                                                                        |
| ---------------------------------------- | ------------------------------------------------------------------------------------------- |
| 자료 주소                                | 지도 4쪽 모두 `www.guri.go.kr/gmapsvr`·`/gmap`(12.1). kgeodata 의존 없음                    |
| 빌드 결과물의 `kgeodata.com`·`/app/guri` | 기능 코드에 0건(주석만). 옛 주석 1건 정리                                                   |
| 외부 호출                                | `js.arcgis.com`(허용), 브이월드·NGII·카카오(키 등록), 네이버 길찾기 링크(새 창)             |
| 브이월드 `domain` 파라미터               | 실제 접속 호스트(`www.guri.go.kr`)를 보냄                                                   |
| 혼합 콘텐츠(http://)                     | 없음                                                                                        |
| 캐시                                     | 루트 캐시 끔 + `_next/static` 1년 + 글꼴·아이콘 7일 (이번에 추가)                           |
| robots                                   | `/review/`·`/v1/`(보존용 옛 홈) 검색 제외 (이번에 추가)                                     |
| `deployment.json`                        | `url`·`commit` 에 더해 `config`(어느 설정으로 빌드했는지)·`reviewWidget` 기록 (이번에 추가) |
| 검토 위젯                                | `build:guri` 에서 제거, 남아 있으면 빌드 실패                                               |
| 숨긴 메뉴                                | 유기동물·동네소식은 HTML 주석으로만 남음(`newsHub`·`animalMap` 스위치)                      |

## 10. 관련 문서

- `docs/TEAM_HANDOFF.md` — 작업 이력
- `docs/DEPLOY_IIS.md` — kgeodata.com 미리보기 자동 배포(실행기)
- `deploy.guri.json` — 구리 운영 빌드 설정 / `deploy.config.json` — 미리보기 설정
