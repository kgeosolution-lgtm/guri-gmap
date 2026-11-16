# 구리시 서버 배포 절차 — 생활지도 (https://www.guri.go.kr/gmapweb/)

담당: 강민아 · 작성 2026-11-16 (12.1 오픈 전 1차 배포 기준)

## 0. 결정 사항 (2026-11-16)

| 항목        | 결정                                                                                                      |
| ----------- | --------------------------------------------------------------------------------------------------------- |
| 서비스 주소 | **`https://www.guri.go.kr/gmapweb/`** — 지금 쓰는 생활지도 주소 그대로. 새 사이트가 그 자리를 **교체**    |
| 전달 방법   | **구리 포털에 zip 업로드** → GMAP-WEB 에서 내려받아 배치 (USB 는 예비)                                    |
| 빌드 명령   | **`npm run build:guri`** 한 번 — 주소·사진·검토 위젯 제거·zip 생성까지 (`deploy.guri.json`)               |
| 작업 서버   | 파일 변경은 **GMAP-WEB(Machine 1, DMZ IIS)** 만. GMAP-AP(포털)·GMAP-GIS(서버)는 브라우저로 공개 설정 확인 |
| 일정        | 수요일(11-18) 1차 배치·검증 → 12.1 오픈(다음 주 월·화)에 맞춰 공개                                        |

생활지도는 **정적 웹사이트**(HTML·JS·이미지)다. 서버 프로그램·DB 가 없고, 자료(레이어)는 이미 구리 포털(`/gmapsvr` 호스팅 서비스, `/gmap` 3D 웹씬)에 있어 그대로 읽는다. 넣을 것은 빌드 결과 한 묶음(약 6MB + 사진)뿐이다.

```
[시민] ──HTTPS──▶ GMAP-WEB (DMZ, IIS)
                    ├─ /gmap      Web Adaptor → GMAP-AP  Portal
                    ├─ /gmapsvr   Web Adaptor → GMAP-GIS ArcGIS Server(호스팅 자료)
                    └─ /gmapweb   ★ 생활지도 정적 파일 (기존 것을 새 사이트로 교체)
```

## 1. 전체 순서 (한눈에)

| 단계                     | 언제                  | 어디서       | 할 일                                                                                 | 절      |
| ------------------------ | --------------------- | ------------ | ------------------------------------------------------------------------------------- | ------- |
| ① 키 도메인 등록 신청    | 지금 바로 (승인 며칠) | 사무실       | 국토정보플랫폼·브이월드·카카오 로드뷰에 `www.guri.go.kr` 추가                         | 2-1     |
| ② 오픈 방식 확인         | 수요일 전             | 구리시 문의  | 12.1 오픈이 DNS 전환인지, 서비스 공개인지                                             | 2-2     |
| ③ 사진 복사 → 빌드 → zip | 화요일                | 사무실       | `public/images/pet/` 에 사진 복사, `npm run build:guri`, `dist/gmapweb-날짜-커밋.zip` | 2-3     |
| ④ zip 포털 업로드        | 화요일                | 사무실(포털) | 콘텐츠 > 새 항목 > 파일 (USB 에도 복사해 예비)                                        | 2-4     |
| ⑤ 기존 /gmapweb 백업     | 수요일 현장           | GMAP-WEB     | 실제 경로 확인, 폴더 통째 복사                                                        | 3-1     |
| ⑥ 새 사이트 배치         | 수요일 현장           | GMAP-WEB     | zip 내려받아 새 폴더에 풀고 실제 경로 변경, 404                                       | 3-2·3-3 |
| ⑦ 포털 공개 확인         | 수요일 현장           | 브라우저     | 호스팅 서비스·웹씬이 공개인지                                                         | 4       |
| ⑧ 검증                   | 수요일 현장           | 휴대폰·PC    | 체크리스트                                                                            | 5       |
| ⑨ 공개 시점 맞추기       | 수요일 끝 / 오픈일    | GMAP-WEB     | 오픈 방식(②)에 따라 경로를 새 폴더로 두거나, 오픈일에 바꿈                            | 3-4     |

## 2. 방문 전 준비 (사무실)

### 2-1. 도메인 등록형 API 키 재등록 — 가장 먼저 신청 (승인에 며칠)

항공사진 비교 페이지가 쓰는 키 3개는 등록한 도메인에서만 동작한다. 지금은 kgeodata.com 만 등록돼 있다.

| 키                           | 파일·위치                               | 할 일                                                                                            |
| ---------------------------- | --------------------------------------- | ------------------------------------------------------------------------------------------------ |
| 국토정보플랫폼 항공사진 WMTS | `public/maps/aerial.html` `NGII.apiKey` | 오픈API > 항공사진 신청 도메인에 `www.guri.go.kr` 추가(또는 새 키 발급 후 값 교체 → GitHub 수정) |
| 브이월드                     | `public/maps/aerial.html` `VW.key`      | 인증키 관리 > 서비스 도메인에 `www.guri.go.kr` 추가                                              |
| 카카오 로드뷰                | `public/maps/aerial.html` `KAKAO.jsKey` | 개발자 콘솔 > 플랫폼 > Web 사이트 도메인에 `https://www.guri.go.kr` 추가                         |

새 키를 발급받았다면 값만 바꿔 GitHub 에 올린 뒤(아래 7장) 빌드한다. 도메인만 추가했다면 코드 수정은 없다. 카톡 공유 키(`gmap-share.js` `KAKAO_JS_KEY`)는 비워 두기로 했으므로 해당 없음.

확인 □ NGII □ 브이월드 □ 카카오 로드뷰

### 2-2. 12.1 오픈 방식 확인 (구리시 문의)

"다음 주 오픈"이 무엇을 바꾸는지에 따라 수요일 마지막 단계(3-4)가 달라진다.

- **A. 외부 DNS·방화벽을 12.1 서버로 돌리는 것**: 지금 시민이 보는 `/gmapweb` 은 옛 서버에 있고 12.1 서버는 외부에서 아직 안 닿는다(hosts 로만 접속되던 상황). 수요일에 12.1 서버의 `/gmapweb` 을 새 사이트로 바꿔도 시민에겐 변화가 없다 → **새 폴더로 두고 온다.** 오픈 순간 새 사이트와 레이어가 함께 열린다.
- **B. www.guri.go.kr 이 이미 12.1 서버이고, 오픈 = 레이어·포털 공개**: 수요일에 바꾸면 공개 전까지 빈 지도가 된다 → 검증 뒤 **옛 폴더로 되돌려 두고**, 오픈일에 구리시 담당자가 실제 경로만 새 폴더로 바꾼다(1분, 전화 안내 가능).

확인 □ A □ B — 담당자: ________

### 2-3. 사진 복사 → 빌드 → zip (`npm run build:guri`)

서버에는 Node 가 없으므로 사무실에서 빌드한다. 설정은 `deploy.guri.json` 한 파일이고 이미 맞춰져 있다(origin `https://www.guri.go.kr`, base `/gmapweb`, photoBase `/images/pet/`, reviewWidget false, zip true). `deploy.config.json`(kgeodata 미리보기)과 `site.config.ts` 는 **건드리지 않는다**.

1. **사진 복사**: kgeodata 서버의 사진 폴더(`https://kgeodata.com/guri/img/` 가 가리키는 IIS 실제 폴더) 내용을 **파일 이름 그대로** 저장소의 `public/images/pet/` 에 복사한다. 포털 레이어(`pet_hospital`·`pet_pharmacy`)의 `이미지명` 값이 이 파일 이름과 같아야 보인다. 이 폴더는 `.gitignore` 에 있어 Git 에 올라가지 않는다. 용량은 서버에서:

   ```powershell
   (Get-ChildItem <사진 폴더> -Recurse -File | Measure-Object Length -Sum).Sum / 1MB
   ```

2. **빌드**

   ```bash
   git checkout design/service-home-refresh && git pull
   npm ci
   npm run build:guri
   ```

   끝에 다음 세 줄이 나와야 한다. `[경고] 사진 폴더…` 가 보이면 1 이 안 된 것이다.

   ```
   Static deployment ready: out -> https://www.guri.go.kr/gmapweb/
   검토 위젯(review.js) 제거됨
   zip: dist/gmapweb-20261118-abc1234.zip
   ```

   빌드 중 3D 웹씬 스냅샷(`public/maps/data/scene.json`)을 포털에서 받는데, 사무실에서 포털에 못 닿으면 저장소의 기존 파일이 쓰인다(문제 없음).

3. **결과 확인**

   ```bash
   cat out/deployment.json                                 # "url": "https://www.guri.go.kr/gmapweb/", commit
   grep -o 'const IMG_BASE="[^"]*"' out/maps/theme.html    # "/gmapweb/images/pet/"
   ls out/images/pet | wc -l                               # 사진 수
   grep -c "구리 동네소식" out/index.html                   # 0 (12월 공개 전)
   ```

   `out/` 구성: `index.html` `404.html` `maps/`(지도 4쪽·아이콘·3D 스냅샷) `images/`(사진 `pet/` 포함) `fonts/` `styles/` `_next/` `robots.txt` `web.config` `deployment.json` `v1/`. 검토 위젯 폴더(`review/`)는 빠진다. **용량**: 약 6MB + 사진.

확인 □ 사진 복사 □ 빌드 3줄 □ deployment.json url·commit □ zip 파일명: ______________

### 2-4. zip 전달 — 포털 업로드 (+ USB 예비)

1. 구리 포털(`https://www.guri.go.kr/gmap`, hosts 로 접속) 로그인 → **콘텐츠 > 새 항목 > 파일** → `dist/gmapweb-날짜-커밋.zip`. 유형은 "코드 샘플"(zip 자동 인식). 제목에 날짜·커밋을 남긴다. **공유는 본인·구리시 담당자에게만**(공개 금지).
2. 같은 zip 을 USB 에도 복사해 둔다(포털 다운로드가 막힐 때 예비).

포털은 파일을 보관만 하고 사이트를 서비스하지는 못하므로 3 장의 배치 작업은 그대로 필요하다.

확인 □ 포털 항목 올림(항목 제목: ______________) □ USB 예비

### 2-5. 챙겨 갈 것

- 이 문서 인쇄본, USB(예비 zip)
- **와이파이 끈 휴대폰(LTE)** — 외부 접속 검증용. 경우 B 면 hosts 를 잡은 노트북도
- 구리시 담당자 연락처, GMAP-WEB 관리자 권한자·포털 관리자 동석 요청

## 3. 현장 — GMAP-WEB (Machine 1, IIS)

관리자 권한으로 로그인한다. 사이트·Web Adaptor·`/gmap`·`/gmapsvr` 설정은 **건드리지 않는다**. `gmapweb` 응용 프로그램의 **콘텐츠만** 바꾼다.

### 3-1. 기존 /gmapweb 확인·백업 (교체 작업이므로 먼저)

1. IIS 관리자 → Web Adaptor 가 붙어 있는 사이트(보통 Default Web Site, `www.guri.go.kr` 인증서 443) → `gmapweb` 응용 프로그램 → 오른쪽 **기본 설정** → **실제 경로**를 적는다. 예: `D:\www\gmapweb`
2. 그 폴더를 통째로 복사해 백업한다. 예: `D:\www\gmapweb_backup_20261118` (웹 루트 밖이면 더 좋다). 되돌릴 때 이 폴더만 있으면 된다.
3. 기존 폴더의 `web.config` 를 열어 본다. 재작성 규칙·핸들러 등 **다른 서비스가 기대는 설정**이 있으면 담당자와 확인한다. 새 사이트는 정적 파일이라 우리 `web.config`(기본 문서·MIME·캐시)로 충분하다.
4. 응용 프로그램 풀은 기존 것을 그대로 쓴다(정적 파일이라 .NET 버전 무관).

확인 □ 실제 경로: `__________` □ 백업 폴더 □ web.config 확인

### 3-2. zip 내려받아 새 폴더에 배치 → 실제 경로 변경

되돌리기가 쉬운 **새 폴더 + 실제 경로 변경** 방식을 쓴다.

1. GMAP-WEB 의 브라우저로 포털(`https://www.guri.go.kr/gmap` 또는 `https://localhost/gmap`)에 로그인 → 2-4 의 항목 → **다운로드**. 안 되면 USB 의 zip.
2. 새 폴더에 푼다. 예: `D:\www\gmapweb_20261118` (Web Adaptor 폴더 안이나 `inetpub\wwwroot` 안은 피한다). 풀고 나서 `gmapweb_20261118\index.html`, `maps\theme.html`, `web.config` 가 **바로** 보여야 한다(폴더가 한 겹 더 들어가지 않게 — zip 은 내용이 루트에 오도록 만들어져 있다).
3. 폴더 속성 > 보안 > `IIS_IUSRS` 에 **읽기 및 실행·폴더 내용 보기·읽기** 권한.
4. IIS 관리자 → `gmapweb` 응용 프로그램 → **기본 설정** → 실제 경로를 새 폴더로 바꾸고 "설정 테스트"로 인증·권한 통과 확인.
5. 기존 폴더는 지우지 않는다(백업이 곧 되돌리기).

**되돌리기**: 실제 경로를 원래 폴더로 되돌린다. 1분이면 된다.

확인 □ zip 내려받음 □ 새 폴더: `__________` □ 권한 □ 실제 경로 변경 □ 설정 테스트 통과

### 3-3. 404 페이지 (선택, 권장)

없는 주소로 들어오면 한글 안내(`404.html`)가 나오게 한다. 응용 프로그램 수준에서만 설정한다.

1. 왼쪽 트리에서 `gmapweb` 선택 → **오류 페이지** → 404 더블클릭(없으면 추가)
2. "이 사이트의 URL 실행" `/gmapweb/404.html`
3. 오른쪽 "기능 설정 편집" → "사용자 지정 오류 페이지" 선택

`httpErrors` 섹션이 서버 수준에서 잠겨 있으면 500.19 가 난다. 그러면 **이 설정만 되돌리고**(사이트 전체 잠금은 풀지 말 것) 404 는 생략한다.

확인 □ 404 설정 (또는 □ 생략)

### 3-4. 공개 시점 맞추기 (2-2 의 답에 따라)

- **경우 A**(오픈 = DNS 전환): 실제 경로를 **새 폴더로 둔 채** 돌아온다. 오픈 때 자동으로 공개된다.
- **경우 B**(오픈 = 서비스 공개): 5 장 검증을 마친 뒤 실제 경로를 **옛 폴더로 되돌려** 두고, 오픈일에 구리시 담당자가 새 폴더로 바꾼다. 담당자에게 3-2 의 4 번만 알려 주면 된다.

확인 □ 경로 최종 상태: □ 새 폴더 □ 옛 폴더(오픈일 변경 예정, 담당자: ______)

### 3-5. 서버에서 1차 확인

서버 브라우저로 `https://www.guri.go.kr/gmapweb/`(hosts 필요하면 잠깐 넣고 지운다), `.../gmapweb/maps/theme.html?group=시즌·겨울`, `.../gmapweb/deployment.json`(commit 이 빌드한 것과 같은지).

## 4. 포털·서버 확인 (브라우저만, 파일 작업 없음)

### 4-1. 자료 공개 여부

시민은 로그인 없이 보므로 사이트가 쓰는 호스팅 서비스가 모두 **"모든 사용자(공개)"** 여야 한다. **시크릿 창**에서 아래 주소가 로그인 없이 JSON 을 내면 된다.

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
| 배경 벡터타일 | `NGII_MAP_SD_20260901` `GURI_BND` `Korea_Boundary` (`.../VectorTileServer`), 유기동물용 `NGII_SD_20250604`                                                    |
| 3D            | 웹씬 항목 `b5e573a06e7f4195bb2f092aad19b253` — `https://www.guri.go.kr/gmap/home/item.html?id=b5e573a06e7f4195bb2f092aad19b253` 이 로그인 없이 열려야 함      |

포털 콘텐츠 > 필터 "공유: 모든 사용자" 로 좁혀 위 목록이 다 있는지 본다. 빠진 항목은 **공유 > 모든 사용자(공개)** 로. 항목 **제목**은 바꿔도 되지만 **서비스 이름(URL)** 은 바꾸면 안 된다. 경우 B 면 이 작업이 "오픈" 자체일 수 있으니 구리시 일정과 맞춘다.

확인 □ 전부 공개 (또는 □ 오픈일에 공개 예정)

### 4-2. 전기차 스케줄러

포털 노트북(구리시 전기차 상태갱신)이 10분마다 도는지 노트북 > 작업에서 마지막 실행 시각을 본다.

### 4-3. CORS

사이트가 `www.guri.go.kr` 이므로 **할 일 없음**(같은 출처).

## 5. 검증 체크리스트

경우 A 는 외부에서 아직 안 닿으므로 hosts 를 잡은 노트북·휴대폰(와이파이)으로, 경우 B 는 휴대폰 LTE 로 한다.

| #   | 확인                                                                                      | 결과 |
| --- | ----------------------------------------------------------------------------------------- | ---- |
| 1   | `https://www.guri.go.kr/gmapweb/` 메인, 겨울 사진·'구리의 사계절' 줄                      | □    |
| 2   | 메인 > 우리동네 지도 열기 → 시즌·겨울, 칩 건수가 0 이 아님(경우 B 의 공개 전엔 0 이 정상) | □    |
| 3   | 칩(한파쉼터) → 목록 → 항목 → 팝업, 전화·네이버 길찾기                                     | □    |
| 4   | 반려동물 > 동물병원 팝업에 사진                                                           | □    |
| 5   | 생활편의 > 전기차: "상태는 10분마다 새로 받아요", 건수                                    | □    |
| 6   | 첫 화면·칩 변경 때 구리시가 (모바일은 시트 위 영역에) 꽉 차게                             | □    |
| 7   | 3D입체지도 열림                                                                           | □    |
| 8   | 항공사진 비교: 타일 보임(NGII 키 도메인), 연도 전환                                       | □    |
| 9   | 공유 단추 → 복사된 주소가 `https://www.guri.go.kr/gmapweb/...`                            | □    |
| 10  | 없는 주소(`/gmapweb/abc`) → 한글 404 (3-3 을 했을 때)                                     | □    |
| 11  | 메뉴에 '구리 동네소식'·'유기동물 찾기'·'수정 요청'이 **없음**                             | □    |
| 12  | `deployment.json` 의 commit = 빌드 커밋                                                   | □    |

PC 에서도 1·2·6·7·8 을 한 번 더.

## 6. 문제가 생겼을 때

| 증상                                  | 원인                                                          | 조치                                                                                |
| ------------------------------------- | ------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| 칩 건수가 전부 0, 목록 없음           | 자료 서비스를 못 읽음: 외부 미개통(2-2) 또는 항목 비공개(4-1) | F12 > 네트워크에서 `gmapsvr` 응답 코드. 403/499 → 공유, 연결 실패 → DNS·방화벽      |
| 서버 안에서는 되는데 휴대폰에서 안 됨 | 외부 개통 전(경우 A 정상)                                     | 2-2                                                                                 |
| 스타일 깨짐·아이콘 없음               | zip 을 한 겹 더 들어간 폴더에 풀었거나 MIME                   | `maps/sym/theme/*.png`, `styles/site-shell.css` 직접 열어 200 인지                  |
| 500.19                                | `web.config` 의 어떤 섹션이 서버 수준에서 잠김                | 오류 화면의 섹션 이름 확인. 3-3 의 404 면 되돌림. 사이트 전체 잠금 해제는 하지 않음 |
| 옛 사이트가 계속 보임                 | 실제 경로 미변경 또는 브라우저 캐시                           | IIS 기본 설정 확인, 시크릿 창                                                       |
| 항공사진 타일 안 보임                 | NGII 키 도메인 미등록                                         | 2-1                                                                                 |
| 3D 가 안 열림                         | 웹씬 항목 비공개                                              | 4-1                                                                                 |
| 동물병원 사진 안 보임                 | 사진 폴더 미복사(`[경고]` 무시)                               | 2-3 의 1                                                                            |
| 수정 요청 메뉴가 보임                 | `build:guri` 가 아닌 `build:deploy` 로 빌드                   | 2-3                                                                                 |

브라우저 콘솔(F12)에 `[시작 화면]`, `[전체보기]`, `[웹맵]` 같은 한글 로그가 찍히므로 어디서 멈췄는지 바로 보인다.

## 7. GitHub 에서 할 일 (언제·무엇)

| 언제                        | 파일                                                               | 할 일                                                                |
| --------------------------- | ------------------------------------------------------------------ | -------------------------------------------------------------------- |
| 지금(완료)                  | `deploy.guri.json`, `scripts/build-deploy.mjs`, `package.json`     | 구리 빌드 명령 `npm run build:guri`(주소·사진·위젯 제거·zip) — 이 PR |
| 키를 새로 발급했을 때만     | `public/maps/aerial.html` `NGII.apiKey` / `VW.key` / `KAKAO.jsKey` | 값 교체 후 PR → 다시 빌드. 도메인만 추가했으면 수정 없음             |
| 사진을 구리 서버로 옮기면서 | `public/images/pet/`                                               | Git 에 올리지 않음(`.gitignore`). 로컬에 복사만                      |
| 12월 동네소식 공개 때       | `src/config/site.config.ts` `features.newsHub`                     | `true` → 빌드·배포                                                   |
| 유기동물 찾기 공개 때(내년) | `src/config/site.config.ts` `features.animalMap`                   | `true`                                                               |
| 옮긴 뒤(선택)               | `public/maps/aerial.html` `cadastreUrl`                            | 연속지적도를 구리 서버에 게시하면 주소 교체                          |
| 건드리지 않음               | `deploy.config.json`, `.github/workflows/guri-preview.yml`         | kgeodata 미리보기 자동 배포용. 구리 운영과 분리                      |

## 8. 이후 운영 (수정이 생겼을 때)

첫 배포 뒤에는 구리시 담당자가 혼자서도 할 수 있다.

1. 사무실: `git pull` → `npm run build:guri` → `dist/gmapweb-날짜-커밋.zip`
2. 포털 > 콘텐츠 > 새 항목 > 파일로 zip 업로드(담당자에게만 공유)
3. GMAP-WEB: zip 내려받아 **새 폴더**(예 `D:\www\gmapweb_20261125`)에 풀고, `gmapweb` 응용 프로그램의 실제 경로를 그 폴더로 변경(3-2). 직전 폴더는 남겨 둔다.
4. 되돌리기: 실제 경로를 직전 폴더로.

`guri-preview.yml` 자동 배포는 kgeodata.com 미리보기용으로 계속 쓴다. 외부 CDN(ArcGIS JS API `js.arcgis.com`, 와구리체 `cdn.jsdelivr.net`)을 막아야 하면 Machine 1 에 함께 올려 주소만 바꾸면 된다(별도 작업).

## 9. 관련 문서

- `docs/TEAM_HANDOFF.md` — 작업 이력
- `docs/DEPLOY_IIS.md` — kgeodata.com 미리보기 자동 배포(실행기)
- `deploy.guri.json` — 구리 운영 빌드 설정 / `deploy.config.json` — 미리보기 설정
