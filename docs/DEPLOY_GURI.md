# 구리시 서버 배포 절차 — 생활지도 (현장 수동 배포)

담당: 강민아 · 작성 2026-11-16

구리시 서버는 원격 작업이 되지 않아 **직접 방문해 USB 로 반입**한다. 이 문서는 그 한 번의 방문을 실수 없이 끝내기 위한 절차서다. 순서대로 따라가면 되고, 각 단계 끝의 확인란에 표시하면서 진행한다.

## 0. 한눈에 보기

- **생활지도는 정적 웹사이트**(HTML·JS·이미지)다. 서버 쪽 프로그램·DB 가 없다.
- **자료(레이어)는 이미 구리 포털에 있다.** 사이트는 `https://www.guri.go.kr/gmapsvr/...`(호스팅 피처 서비스·벡터타일)와 `https://www.guri.go.kr/gmap/...`(3D 웹씬)을 그대로 읽는다. 자료를 다시 넣을 일은 없다.
- 따라서 **넣을 것은 빌드 결과 폴더(`out/`, 약 6MB) 하나**이고, **넣을 곳은 Machine 1(DMZ, Web Adaptor 가 있는 IIS)** 이다. Machine 2·3·4 에는 파일 작업이 없고 브라우저로 공유 설정만 확인한다.

```
[시민 브라우저] ──HTTPS──▶ Machine 1 (DMZ, IIS)
                             ├─ /gmap      Web Adaptor → Machine 2 Portal
                             ├─ /gmapsvr   Web Adaptor → Machine 3 ArcGIS Server(호스팅 자료)
                             └─ /gmaplife  ★ 생활지도 정적 파일 (이번에 추가)
```

## 1. 방문 전 준비(사무실, 방문 1주 전부터)

### 1-1. 최종 주소 확정

구리시 전산 담당과 **사이트 주소**를 정한다. 권장: `https://www.guri.go.kr/gmaplife/` (이 문서는 이 값을 예로 쓴다).

- `/gmap`·`/gmapsvr` 는 Web Adaptor 가 쓰므로 **다른 별칭**이어야 한다.
- **같은 도메인(www.guri.go.kr)** 에 두면 자료 조회가 같은 출처(same-origin)라 CORS 설정이 전혀 필요 없다. 다른 도메인을 쓰면 3-3 절을 추가로 해야 한다.

확인 □ 주소 확정: `https://www.guri.go.kr/________/`

### 1-2. 외부 개통 확인 (가장 중요)

전에 모바일에서 "구리시 포털 12.1 을 hosts 에 설정하지 못해 자료가 0건"이었던 것은 **www.guri.go.kr 이 외부 DNS 에서 Machine 1 로 풀리지 않거나 443 이 막혀 있다**는 뜻이다. 이게 안 열려 있으면 사이트를 올려도 시민 휴대폰에서는 자료가 보이지 않는다.

구리시에 확인할 것:

- 외부 DNS: `www.guri.go.kr` → Machine 1 공인 IP
- 방화벽: 외부 → Machine 1 **443** 허용
- Web Adaptor(Server, `/gmapsvr`)가 **익명 접근**으로 공개 서비스를 내려주는지(관리자 접근은 꺼져 있어도 됨)

사무실에서 미리 해 볼 수 있는 검사(와이파이 끄고 휴대폰 LTE):

```
https://www.guri.go.kr/gmapsvr/rest/services/Hosted/life_gas/FeatureServer?f=json
```

로그인 없이 JSON 이 나오면 개통된 것이다. 안 나오면 방문 전에 구리시와 먼저 해결한다.

확인 □ LTE 에서 위 주소 JSON 확인

### 1-3. 도메인 등록형 API 키 재등록 (승인에 며칠 걸림 — 가장 먼저 신청)

항공사진 비교 페이지가 쓰는 키 3개는 **등록한 도메인에서만** 동작한다. 지금은 kgeodata.com 만 등록돼 있다.

| 키                           | 파일·위치                               | 할 일                                                                                               |
| ---------------------------- | --------------------------------------- | --------------------------------------------------------------------------------------------------- |
| 국토정보플랫폼 항공사진 WMTS | `public/maps/aerial.html` `NGII.apiKey` | 국토정보플랫폼 > 오픈API > 항공사진 신청 도메인에 `www.guri.go.kr` 추가(또는 새 키 발급 후 값 교체) |
| 브이월드 WMS/WMTS            | `public/maps/aerial.html` `VW.key`      | 브이월드 > 인증키 관리 > 서비스 도메인에 `www.guri.go.kr` 추가                                      |
| 카카오 로드뷰                | `public/maps/aerial.html` `KAKAO.jsKey` | 카카오 개발자 콘솔 > 앱 > 플랫폼 > Web > 사이트 도메인에 `https://www.guri.go.kr` 추가              |

카톡 공유 키(`public/maps/gmap-share.js` `KAKAO_JS_KEY`)는 비워 두기로 했으므로 해당 없음.

확인 □ NGII □ 브이월드 □ 카카오 로드뷰

### 1-4. kgeodata.com 에 남아 있는 것

| 기능                       | 코드                                                                      | 이번 방문                                                                                            |
| -------------------------- | ------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| 동물병원·동물약국 사진     | `theme.html` `IMG_BASE`(빌드 때 `deploy.config.json` `photoBase` 로 바뀜) | **같이 옮긴다** — 1-5 의 "사진 복사" 단계. 사이트와 함께 USB 에 담긴다                               |
| 항공사진 비교의 연속지적도 | `aerial.html` `cadastreUrl`(kgeodata ArcGIS Server)                       | 그대로 둔다(지적도 겹치기만 kgeodata 의존). 옮기려면 구리 서버에 호스팅 레이어로 게시한 뒤 주소 교체 |

### 1-5. 설정 바꾸고 빌드하기 (서버에는 Node 가 없다고 보고 사무실에서 빌드)

1. `deploy.config.json` — 배포 주소·사진 폴더 한 곳

   ```json
   { "origin": "https://www.guri.go.kr", "base": "/gmaplife", "photoBase": "/images/pet/" }
   ```

   사이트 루트(`https://도메인/`)에 두기로 했다면 `"base": ""`. `photoBase` 는 사진이 사이트 안에 있다는 뜻이며 빌드가 `/gmaplife/images/pet/` 로 바꿔 넣는다(미리보기는 `https://kgeodata.com/guri/img/`).

1. **사진 복사** — kgeodata 서버의 사진 폴더(`https://kgeodata.com/guri/img/` 가 가리키는 IIS 실제 폴더) 내용을 **파일 이름 그대로** 저장소의 `public/images/pet/` 에 복사한다. 포털 레이어(`pet_hospital`·`pet_pharmacy`)의 `이미지명` 값이 이 파일 이름과 같아야 보인다. 이 폴더는 `.gitignore` 에 있어 Git 에 올라가지 않는다(빌드 결과에만 들어감). 용량은 서버에서 PowerShell 로 잰다:

   ```powershell
   (Get-ChildItem <사진 폴더> -Recurse -File | Measure-Object Length -Sum).Sum / 1MB
   ```

   빌드 때 `[경고] 사진 폴더 public/images/pet/ 가 없어…` 가 나오면 복사가 안 된 것이다.

1. `src/config/site.config.ts` — 오픈용 스위치

   ```ts
   features: { animalMap: false, newsHub: false, reviewWidget: false }
   ```

   `reviewWidget: false` 로 "수정 요청" 검토 위젯을 뺀다(홈·지도 4쪽 모두). `newsHub` 는 12월 요청 때 `true`.

1. 빌드

   ```bash
   npm ci
   npm run build:deploy
   ```

   끝에 `Static deployment ready: out -> https://www.guri.go.kr/gmaplife/` 가 찍혀야 하고, 그 앞에 `[경고] 사진 폴더…` 가 **없어야** 한다. 빌드 중 3D 웹씬 스냅샷(`scripts/fetch-scene.mjs` → `public/maps/data/scene.json`)을 포털에서 받는데, 사무실에서 포털에 못 닿으면 "실패해도 배포는 계속"이라 저장소에 있는 기존 `scene.json` 이 쓰인다(문제 없음).

1. 결과 확인 (`out/` 안)

   ```bash
   cat out/deployment.json          # "url": "https://www.guri.go.kr/gmaplife/"
   grep -c "review/review.js" out/index.html        # 0 이어야 함
   grep -o 'og:image" content="[^"]*' out/maps/theme.html   # https://www.guri.go.kr/gmaplife/images/og-cover.jpg
   grep -o 'const IMG_BASE="[^"]*"' out/maps/theme.html        # "/gmaplife/images/pet/"
   ls out/images/pet | wc -l                                    # 사진 수
   ```

   `out/` 구성: `index.html`, `404.html`, `maps/`(지도 4쪽·아이콘·3D 스냅샷), `images/`(사진 `pet/` 포함), `fonts/`, `styles/`, `_next/`, `robots.txt`, `web.config`, `deployment.json`, `v1/`(보존된 옛 홈), `review/`(스위치가 꺼져 있으면 아무 페이지도 안 불러옴 — 폴더째 빼고 복사해도 됨).

1. USB 에 복사. **`out/` 폴더 전체**를 복사하고, 폴더 이름을 `gmaplife` 로 바꿔 둔다. 소스·`.git`·`node_modules` 는 가져가지 않는다.

**용량**: 사진을 뺀 사이트는 약 6MB(파일 194개)이고, 여기에 사진 폴더 용량이 더해진다.

확인 □ deploy.config.json(photoBase 포함) □ 사진 복사 □ reviewWidget false □ 빌드 성공(사진 경고 없음) □ deployment.json url □ USB

### 1-6. 챙겨 갈 것

- USB(빌드 결과 `gmaplife/`), 이 문서 인쇄본
- **와이파이 끈 휴대폰(LTE)** — 외부 접속 검증용
- 구리시 담당자 연락처, IIS 관리자 권한을 가진 분 동석 요청

## 2. 현장 — Machine 1 (IIS)

관리자 권한으로 로그인한다. IIS 사이트·Web Adaptor·`/gmap`·`/gmapsvr` 설정은 **건드리지 않는다**. 응용 프로그램 하나를 **추가**만 한다.

### 2-1. 파일 복사

1. 웹 폴더를 만든다. 예: `D:\www\gmaplife` (Web Adaptor 폴더 안이나 `inetpub\wwwroot` 안은 피한다).
2. USB 의 `gmaplife/` 내용을 그 폴더에 복사한다. 복사 후 `D:\www\gmaplife\index.html`, `maps\theme.html`, `web.config` 가 바로 보여야 한다(폴더가 한 겹 더 들어가지 않게).
3. 폴더 속성 > 보안 > `IIS_IUSRS` 에 **읽기 및 실행·폴더 내용 보기·읽기** 권한.

확인 □ 복사 □ 권한

### 2-2. IIS 응용 프로그램 추가

1. IIS 관리자 실행 → 왼쪽 트리에서 **Web Adaptor 가 붙어 있는 사이트**(보통 Default Web Site, `www.guri.go.kr` 인증서로 443 바인딩) 선택.
2. 사이트 우클릭 → **응용 프로그램 추가**
   - 별칭: `gmaplife`
   - 응용 프로그램 풀: 기본값(DefaultAppPool) — 정적 파일이라 .NET 버전 무관. 별도 풀을 만들어도 됨(관리 코드 없음 권장).
   - 실제 경로: `D:\www\gmaplife`
3. **확인** 버튼으로 바로 닫지 말고 "설정 테스트" 로 인증·권한이 모두 통과하는지 본다.

`web.config` 는 빌드 결과에 포함돼 있고 다음만 한다: 기본 문서 `index.html`, 디렉터리 검색 끔, MIME(`.webp .woff2 .json .svg`), 캐시 끔. 상위 설정은 바꾸지 않는다.

확인 □ 응용 프로그램 추가 □ 설정 테스트 통과

### 2-3. 404 페이지 (선택, 권장)

없는 주소로 들어오면 한글 안내(`404.html`)가 나오게 한다. 응용 프로그램 수준에서만 설정한다.

1. 왼쪽 트리에서 `gmaplife` 선택 → **오류 페이지** → 404 더블클릭(없으면 추가)
2. "이 사이트의 URL 실행" `/gmaplife/404.html`
3. 오른쪽 "기능 설정 편집" → "사용자 지정 오류 페이지" 선택

`httpErrors` 섹션이 서버 수준에서 잠겨 있으면 500.19 가 난다. 그러면 **이 설정만 되돌리고**(사이트 전체 잠금은 풀지 말 것) 404 는 생략한다 — 나머지 기능에는 영향이 없다.

확인 □ 404 설정 (또는 □ 생략)

### 2-4. 서버에서 1차 확인

서버 브라우저로 연다.

- `https://www.guri.go.kr/gmaplife/` → 메인
- `https://www.guri.go.kr/gmaplife/maps/theme.html?group=시즌·겨울` → 칩 건수가 0 이 아닌지
- `https://www.guri.go.kr/gmaplife/deployment.json` → `commit` 이 빌드한 커밋과 같은지

내부에서 `www.guri.go.kr` 이 안 풀리면 `C:\Windows\System32\drivers\etc\hosts` 에 Machine 1 주소를 **잠깐** 넣고 확인한 뒤 지운다.

## 3. 포털·서버 확인 (브라우저만, 파일 작업 없음)

### 3-1. 자료 공개 여부

시민은 로그인 없이 보므로 사이트가 쓰는 호스팅 서비스가 모두 **"모든 사용자(공개)"** 로 공유돼 있어야 한다. 가장 확실한 검사는 **시크릿 창**(로그아웃 상태)에서 아래 주소를 열어 로그인 없이 JSON 이 나오는지 보는 것이다.

```
https://www.guri.go.kr/gmapsvr/rest/services/Hosted/<서비스이름>/FeatureServer?f=json
```

지금 서비스 중인 그룹이 쓰는 서비스(여름·가을·육아 등 숨긴 그룹은 제외해도 됨):

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
| 배경 벡터타일 | `NGII_MAP_SD_20260901` `GURI_BND` `Korea_Boundary` (`.../VectorTileServer`), 유기동물용 `NGII_SD_20250604`                                                    |
| 3D            | 웹씬 항목 `b5e573a06e7f4195bb2f092aad19b253` — `https://www.guri.go.kr/gmap/home/item.html?id=b5e573a06e7f4195bb2f092aad19b253` 이 로그인 없이 열려야 함      |

포털에서 한 번에 보려면: 콘텐츠 > 내 콘텐츠(또는 조직) > 필터 "공유: 모든 사용자" 로 좁혀 위 목록이 다 들어 있는지 본다. 빠진 항목은 **공유 > 모든 사용자(공개)** 로 바꾼다. 항목 **제목**은 바꿔도 되지만 **서비스 이름(URL)** 은 바꾸면 안 된다(사이트는 URL 로 읽는다).

확인 □ 전부 공개

### 3-2. 전기차 스케줄러

포털 노트북(구리시 전기차 상태갱신)이 **10분마다** 돌고 있는지 노트북 > 작업(Tasks)에서 마지막 실행 시각을 본다. 이미 재설정해 둔 것이라 보통 할 일은 없다.

### 3-3. CORS (사이트가 www.guri.go.kr 이 아닐 때만)

같은 도메인이면 건너뛴다. 다른 도메인(예: `https://gmap.guri.go.kr`)에 두었다면:

- ArcGIS Server 관리자 `https://www.guri.go.kr/gmapsvr/admin` → security → config → `allowedOrigins` 에 사이트 도메인 추가
- 포털 조직 설정 > 보안 > 허용된 출처에 사이트 도메인 추가(3D 웹씬용)

## 4. 현장 검증 체크리스트 (휴대폰 LTE, 와이파이 끄고)

내부망에서만 되는 것을 걸러내는 가장 확실한 방법이다. 담당자 휴대폰으로 그 자리에서 한다.

| #   | 확인                                                                                 | 결과 |
| --- | ------------------------------------------------------------------------------------ | ---- |
| 1   | `https://www.guri.go.kr/gmaplife/` 메인이 열리고 겨울 사진·'구리의 사계절' 줄이 보임 | □    |
| 2   | 메인 > 우리동네 지도 열기 → 시즌·겨울로 열리고 칩 건수가 0 이 아님                   | □    |
| 3   | 칩 하나(한파쉼터) → 목록 → 항목 → 팝업, 전화·네이버 길찾기 단추                      | □    |
| 3-1 | 반려동물 > 동물병원 항목 팝업에 사진이 보임(사진 폴더 복사·`photoBase`)              | □    |
| 4   | 테마 변경(생활편의 > 전기차) → "상태는 10분마다 새로 받아요" 문구, 건수 표시         | □    |
| 5   | 첫 화면·칩 변경 때 구리시가 시트 위 영역에 꽉 차게 보임                              | □    |
| 6   | 3D입체지도가 열림(웹씬 공개 여부)                                                    | □    |
| 7   | 항공사진 비교: 항공사진 타일이 보임(NGII 키 도메인), 연도 전환                       | □    |
| 8   | 공유 단추 → 복사된 주소가 `https://www.guri.go.kr/gmaplife/...`                      | □    |
| 9   | 없는 주소(`/gmaplife/abc`) → 한글 404 (2-3 을 했을 때)                               | □    |
| 10  | 카톡으로 메인 주소 보내 미리보기 그림(겨울 사진)이 뜸 — 캐시 때문에 늦을 수 있음     | □    |
| 11  | 메뉴에 '구리 동네소식'·'유기동물 찾기'·'수정 요청'이 **없음**                        | □    |

PC 에서도 1·2·5·6·7 을 한 번 더 본다.

## 5. 문제가 생겼을 때

| 증상                                              | 원인                                                                  | 조치                                                                                                |
| ------------------------------------------------- | --------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| 칩 건수가 전부 0, 목록 없음                       | 자료 서비스를 못 읽음: 외부 DNS/443 미개통(1-2) 또는 항목 비공개(3-1) | 브라우저 F12 > 네트워크에서 `gmapsvr` 요청의 응답 코드 확인. 403/499 → 공유, 연결 실패 → DNS·방화벽 |
| 서버 안에서는 되는데 휴대폰에서 안 됨             | 외부 개통 문제                                                        | 1-2                                                                                                 |
| 메인은 뜨는데 지도 페이지 스타일 깨짐·아이콘 없음 | 폴더가 한 겹 더 들어감 / MIME                                         | `maps/sym/theme/*.png`, `styles/site-shell.css` 주소를 직접 열어 200 인지                           |
| 500.19                                            | `web.config` 의 어떤 섹션이 서버 수준에서 잠김                        | 오류 화면의 섹션 이름 확인. 2-3 의 404 설정이면 되돌림. 사이트 전체 잠금 해제는 하지 않음           |
| 항공사진 타일 안 보임                             | NGII 키 도메인 미등록                                                 | 1-3                                                                                                 |
| 3D 가 안 열림                                     | 웹씬 항목 비공개 또는 포털 CORS                                       | 3-1, 3-3                                                                                            |
| 동물병원 사진 안 보임                             | 사진 폴더 미복사 또는 `photoBase` 미설정                              | 1-5 사진 복사, `out/maps/theme.html` 의 `IMG_BASE` 값 확인. 사진 주소를 직접 열어 200 인지          |
| 수정 요청 메뉴가 보임                             | `reviewWidget` 을 안 끄고 빌드                                        | 1-5 다시                                                                                            |
| 카톡 미리보기 그림이 옛 것                        | 카카오 캐시                                                           | 카카오 공유 디버거에서 새로고침                                                                     |

브라우저 콘솔(F12)에는 `[시작 화면]`, `[전체보기]`, `[웹맵]` 같은 한글 로그가 찍히므로 어디서 멈췄는지 바로 보인다.

## 6. 이후 운영 (수정이 생겼을 때)

원격이 안 되므로 **빌드 → USB → 폴더 덮어쓰기**를 반복한다.

1. 사무실: 1-5 와 같이 빌드(설정은 이미 맞춰져 있으니 `npm run build:deploy` 만)
2. 현장: 기존 `D:\www\gmaplife` 를 `D:\www\gmaplife_backup_날짜` 로 **복사해 두고**(되돌리기용) 새 `out/` 내용을 덮어쓴다. 자산 파일은 이름에 해시가 붙어 겹치지 않으며, `index.html` 은 마지막에 복사한다.
3. 되돌리기: 백업 폴더 내용을 다시 덮어쓴다.

GitHub Actions 자동 배포(`guri-preview.yml`)는 kgeodata.com **미리보기용**으로 계속 쓴다. 구리시가 "외부 → 내부 단방향 파일 반입"을 허용하면 그 경로로 자동화할 수 있으니 방문 때 한 번 물어본다.

**외부 CDN**: 지도 엔진(ArcGIS JS API 4.29)은 시민 브라우저가 `js.arcgis.com` 에서, 브랜드 서체(와구리체)는 `cdn.jsdelivr.net` 에서 받는다. 구리시 정책상 외부 CDN 을 막아야 하면 API 를 Machine 1 에 함께 올려 주소만 바꾸면 된다(별도 작업).

## 7. 관련 문서

- `docs/TEAM_HANDOFF.md` — 작업 이력, "오픈 준비 ②" 의 도메인 전환 체크리스트
- `docs/DEPLOY_IIS.md` — kgeodata.com 미리보기 자동 배포(실행기)
- `deploy.config.json` — 배포 주소·사진 폴더 한 곳
