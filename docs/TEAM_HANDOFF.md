# 팀 협업 및 Claude 인수인계

## 공유할 주소와 현재 상태

- 저장소: https://github.com/kgeosolution-lgtm/guri-gmap
- 최신 디자인: https://github.com/kgeosolution-lgtm/guri-gmap/tree/design/service-home-refresh
- 작업 기준 브랜치: `design/service-home-refresh`
- 디자인 변경 커밋: `ed4b6a9` (이후 인수인계 문서 커밋 포함)
- 현재 이 디자인은 main에 병합하지 않았습니다. main만 clone하면 이전 화면입니다.
- GitHub 업로드와 운영 사이트 배포는 별개입니다. localhost는 각 직원 PC에서 실행하는 주소입니다.
- 비공개 저장소 접근에는 직원 본인의 GitHub 계정에 저장소 접근 권한이 필요합니다. 저장소 관리자에게 초대를 요청하고 수락하세요. 작업 브랜치를 push하려면 쓰기 권한도 필요합니다. 계정·토큰을 공유하지 않습니다.

## 처음 내려받아 실행하기

Git과 Node.js/npm이 설치된 개인 작업 폴더에서 실행하세요. 이 작업은 Node.js v24.21.0에서 검증했습니다. 의존성 버전은 package-lock.json을 기준으로 설치합니다.

```bash
git clone --branch design/service-home-refresh https://github.com/kgeosolution-lgtm/guri-gmap.git
cd guri-gmap
git config --local pull.ff only
npm ci
npm run dev
```

확인할 화면:

- 홈: http://localhost:3000/
- 테마지도: http://localhost:3000/maps/theme.html?group=여름
- 유기동물: http://localhost:3000/maps/animal.html
- 3D 지도: http://localhost:3000/maps/scene.html
- 시계열 항공사진: http://localhost:3000/maps/aerial.html
- 보존된 초기 홈: http://localhost:3000/v1

포트 3000을 이미 사용하는 경우 개발 서버가 출력한 실제 포트를 확인하세요. `.env.local`은 기본 실행에 필수가 아닙니다. 지도 주소를 바꿀 때 `.env.example`을 참고하세요. 기본 지도 주소는 `/maps`입니다. 홈의 사계절 선택은 본 화면에 포함되며, 기존 `NEXT_PUBLIC_SHOW_THEME_TOOLBAR`는 이전 개발 도구에 대한 설정입니다.

## 직원별 작업 시작과 제출

새 clone에서 다음과 같이 본인 작업 브랜치를 만드세요. 예시 이름의 직원명·작업명을 바꿔 사용합니다.

```bash
git status
git fetch origin
git switch -c work/employee-task origin/design/service-home-refresh
```

기존 작업 폴더에 미커밋 변경이 있다면 먼저 내용을 확인하고 보존합니다. 무조건 pull/reset/checkout으로 덮어쓰지 않습니다. 각자 별도 clone과 브랜치에서 작업하고, 같은 폴더를 여러 AI가 동시에 수정하지 않습니다.

```bash
npm run build
npx prettier --check src public/styles/site-shell.css
git diff --check
git diff
```

변경 파일만 지정해 `git add`하고 커밋한 다음 `git push -u origin work/employee-task`로 올립니다. GitHub PR의 base는 당분간 `design/service-home-refresh`로 지정하고 팀 검토를 받습니다. 디자인 브랜치를 main에 병합한 뒤에는 팀 공지에 따라 main에서 새 작업을 시작합니다. 같은 파일을 수정하는 작업은 담당 범위를 먼저 공유합니다. force push, 다른 사람의 변경 삭제, 검토 없는 main 직접 push는 하지 않습니다.

## 이번에 바뀐 내용

- 기존 사계절 이미지를 홈 전체 배경으로 유지. 자동 계절 적용 및 봄·여름·가을·겨울 선택 유지.
- 배경 위 글씨 가독성, 여백, 버튼, 메뉴 및 계절 전환 애니메이션 정리.
- 9개 테마 그룹 검색, 유기동물 안내, 실제 이용 안내로 홈 재구성. 검색은 테마 그룹 검색이며 개별 시설 전체 검색이 아닙니다.
- 홈·테마지도·유기동물의 공통 헤더 CSS 도입. 지도 페이지에서 다른 서비스로 이동 가능.
- 이전 컴포넌트와 /v1 보존. 지도 조회·필터·차트·렌더 스크립트는 그대로 유지.

## 주요 파일

| 영역                      | 경로                                                                                             |
| ------------------------- | ------------------------------------------------------------------------------------------------ |
| 새 홈·계절 선택·그룹 검색 | src/app/page.tsx                                                                                 |
| 새 홈 스타일              | src/app/service-home.css                                                                         |
| React 헤더                | src/components/krds/SiteHeader.tsx                                                               |
| 홈·지도 공용 헤더 스타일  | public/styles/site-shell.css                                                                     |
| KRDS 토큰·폰트            | src/app/globals.css                                                                              |
| 계절 이미지·문구          | src/config/season.config.ts                                                                      |
| 그룹 색·아이콘·설명       | src/config/theme-groups.config.ts                                                                |
| 지도 URL 헬퍼             | src/config/links.ts                                                                              |
| 지도 기본 주소            | src/config/site.config.ts                                                                        |
| 정적 지도 페이지          | public/maps/theme.html, public/maps/animal.html, public/maps/scene.html, public/maps/aerial.html |
| 지도 공용 토큰            | public/maps/gmap-shared.css                                                                      |

React 헤더와 정적 HTML 헤더는 같은 CSS를 사용하지만 마크업은 각각 존재합니다. 구조를 수정하면 양쪽을 함께 확인하세요. 지도 헤더 높이는 테두리 포함 57px이며 기존 밴드·패널의 위치 계산과 연결됩니다. theme.html에는 큰 base64 심볼이 있으므로 전체를 출력하지 말고 필요한 구간만 읽으세요. public/maps/는 Prettier 제외 대상입니다.

## Claude에 처음 붙여 넣을 지시서

아래 지시서를 프로젝트 폴더를 연 Claude에 붙여 넣으세요. 마지막에 이번에 맡길 구체적인 작업을 덧붙입니다.

```text
이 저장소의 구리시 G-MAP 작업을 이어서 협업해 줘.

먼저 수정하지 말고 현재 소스 경로, git status, 브랜치, origin URL, 최신 커밋을 확인해.
README.md, AGENTS.md, docs/TEAM_HANDOFF.md를 읽어.
과거 Claude 대화나 다른 AI의 완료 선언보다 현재 저장소와 실제 실행 결과를 기준으로 판단해.

git fetch origin으로 원격 상태를 확인해. 현재 디자인 기준은 origin/design/service-home-refresh야.
이미 main에 병합됐는지는 실제 Git 이력으로 확인하고, 미병합이면 그 디자인 브랜치에서
work/<담당자>-<작업명> 형태의 새 작업 브랜치를 만들어. 미커밋 변경은 덮어쓰지 말고 보존해.

package-lock.json과 실제 설치 버전을 확인하고 npm ci로 설치해.
이 프로젝트의 Next.js는 학습한 일반적인 버전과 다를 수 있으니 AGENTS.md에 따라
node_modules/next/dist/docs의 관련 문서를 읽고 구현해.
개발 서버가 이미 있으면 중복 실행하지 말고 실제 포트와 페이지를 확인해.

기존 사계절 이미지를 홈 전체 배경으로 사용하는 디자인, 자동·수동 계절 전환,
KRDS 토큰·Pretendard GOV·와구리체, /v1 보존 원칙을 유지해.
지도 URL은 site.config.ts와 links.ts 헬퍼를 사용해.
공통 헤더는 public/styles/site-shell.css이고 React와 정적 HTML 마크업이 각각 있으니 함께 확인해.

별도 요청 없이는 theme.html의 CITY/GROUPS/F 및 지도·데이터 렌더 로직,
animal.html의 조회·필터·차트·지도 로직은 건드리지 마.
theme.html의 큰 base64 심볼을 통째로 출력하거나 정적 지도 파일 전체를 포맷하지 마.
홈 검색은 그룹 검색이므로 개별 시설 검색이라고 표시하지 마.

변경 후 PC 1280px·모바일 390px에서 관련 화면과 실제 동작·콘솔을 확인하고
npm run build, npx prettier --check src public/styles/site-shell.css, git diff --check를 실행해.
원래 있던 변경과 이번 변경을 구분하고 본인 변경 파일만 커밋해.
작업 브랜치로 push하고 PR 검토를 받을 수 있게 해. main 직접 push나 force push는 하지 마.
검증하지 못한 내용과 운영 배포 여부를 구분해서 보고하고 인수인계 문서도 갱신해.

이번에 맡길 작업: [여기에 구체적인 요청을 입력]
```

## 검증 범위

2026-09-11 디자인 작업에서 빌드·포맷 검사, PC/모바일 3개 페이지 시각 점검, 콘솔 오류 없음, 홈 그룹 검색/빈 결과 복원/계절 전환/모바일 메뉴를 확인했습니다. 정적 지도 기존 script 블록은 변경 전과 동일함을 비교했습니다. 운영 배포나 전체 데이터 정확성 검증은 수행하지 않았습니다. 이후 변경은 각 작업자가 다시 검증합니다.

## 2026-09-11 반려동물 팝업 링크 수정

- 변경: `public/maps/theme.html` 반려동물 그룹 유기동물 테마의 `links` 항목 URL을 `https://kgeodata.com/guri/animal.html` → `https://kgeodata.com/app/guri/maps/animal.html` 로 한 곳만 변경. CITY/GROUPS/F·렌더 로직·base64 심볼은 변경 없음.
- 브랜치: `work/kangmina-animal-link` (base `design/service-home-refresh` 4f282d6).
- 검증: `npm ci`, `npm run build`, `npm run build:deploy`, `npx prettier --check src public/styles/site-shell.css`, `git diff --check` 통과. `out/maps/theme.html` 에 새 주소 포함 확인. `npm run dev` 후 `/maps/theme.html?group=반려동물` 유기동물 팝업의 "유기동물 찾기 앱에서 더 보기" href가 새 주소이고 콘솔 오류 없음 확인. 운영 배포는 수행하지 않음(개인 브랜치 push만으로는 공개 사이트에 반영되지 않음).

## 2026-09-11 테마지도 둘레길 코스 구분·추천맛집 팝업 이식

- 배경: 별도 작업본 `theme.html`(2026-09-10, 이전 헤더·목록 디자인 기반)에 추가된 내용을 현재 브랜치의 화면·목록·팝업 디자인은 유지한 채로 `public/maps/theme.html`에 옮겼습니다. 헤더, 칩바, 목록 마크업, 팝업 스타일, 이모지 라벨 등 디자인 차이는 가져오지 않았습니다.
- 옮긴 내용: 둘레길 코스별 색·이름(`n코스 …`)·안내문(`COURSE_INFO`), 둘레길 시설물 심볼의 코스 색 틴트(`tintSym`/`courseDot`), 선 레이어 코스별 unique-value 렌더러, 목록 선 아이콘의 코스 색, 와구리 추천맛집의 이름 필드 후보·`지정년도` 팝업·숨김 패턴 확장.
- 조정: 현재 `econ_waguri` 레이어에는 `지정년도` 필드가 없고 연도가 `추가정보`("2023년, 2025년")에 있어, `지정년도` 팝업 항목이 `추가정보`·`비고`로 대체 표시되도록 했습니다. 데이터에 `지정년도` 필드가 추가되면 그 값이 우선합니다.
- 브랜치: `work/kangmina-dulle-course` (base `design/service-home-refresh` 4755da5).
- 검증: `npm run build`, `npm run build:deploy`, `npx prettier --check --end-of-line auto src public/styles/site-shell.css`, `git diff --check` 통과. `out/maps/theme.html`에 코스 로직 포함 확인. 로컬 `?group=문화·여가` 둘레길에서 코스별 선 색·목록 색·팝업 안내문, `?group=경제·상권` 추천맛집 팝업, 콘솔 오류 없음 확인. 운영 배포는 수행하지 않았습니다.

## 2026-09-11 시즌·가을 그룹 추가 이식

- 원본: 별도 작업본 `theme.html`(2026-09-10 17:52, 이전 디자인 기반). 현재 화면·목록·팝업 디자인은 유지하고 내용만 옮겼습니다.
- theme.html: 그룹 `여름` → `시즌·여름` 이름 변경, `시즌·가을` 그룹 추가(구리 명소·둘레길·둘레길 시설물·등산로·등산로 시설물), 가을 그룹 아이콘(`TOPIC_IC`), 명소 심볼·색(`SPOT_STYLE`/`spotKind`/`spotSym`), 긴 글 요약(`briefText`), 테마별 `symUrlFn`·`where`·`photos`(사진 여러 장, `.pgal` CSS) 지원. 가을 그룹 accent는 `#B5551F`로 새로 지정.
- 홈: `links.ts` 그룹 이름 목록, `theme-groups.config.ts` 카드(Leaf 아이콘, `#C1652B`), `themeUrl('여름')` 참조 5곳을 `시즌·여름`으로, 가을 추천 항목 "아차산 단풍 산책"을 `시즌·가을`로 연결. 나머지 가을 추천 항목은 기존처럼 준비중(null).
- 호환: `?group=여름` 예전 주소는 GROUPS 첫 항목 fallback으로 `시즌·여름`이 열립니다.
- 브랜치: `work/kangmina-dulle-course` (둘레길 코스 커밋 5447496 위에 추가).
- 검증: `npm run build`, `npm run build:deploy`, `tsc --noEmit`, prettier(eol auto), `git diff --check` 통과. 로컬 `?group=시즌·가을`에서 4개 칩(명소 19·둘레길 7·등산로 442·등산로시설 928), 그룹 메뉴 가을 아이콘, 명소 팝업(사진 6장·편의시설 칩·소개·가는 길·전화) 확인. 홈에 시즌·가을 카드 노출 확인. 콘솔 오류 없음(기존 `animation` 경고만 있음). 운영 배포는 수행하지 않았습니다.

## 2026-09-11 목록 상태 배지 정리·긴 팝업 스크롤

- 목록 배지: `rowStatus`가 모든 `statusFn` 결과를 영업중/종료로 바꿔 보여 주던 것을, 운영시간 기준 테마만 표시하도록 제한했습니다. `op:true` 테마(운영시간 계산)와 `listStatus:true`로 지정한 테마(AED, 약국, 병의원, 교통 공사·통제)만 배지가 나옵니다. 구리 명소(휴무일 존재), 전기차 충전소(빈 충전기 없음), 유기동물 보호현황(처리 상태)은 배지가 사라지며, 팝업의 상태 문구는 그대로입니다. 휴무·휴장 상태는 "휴무"로 표시합니다.
- 팝업 스크롤: PC에서 `.infocard`에 `max-height:calc(100% - 24px); overflow-y:auto`를 주어 지도 높이를 넘는 팝업은 안에서 스크롤됩니다. 900px 이하 태블릿 폭 규칙(`bottom:160px`)에도 같은 상한을 넣었습니다. 모바일 56dvh 규칙은 기존 그대로입니다.
- 검증: 로컬 1280×800에서 명소 19건·전기차 330건 목록 배지 0개, 약국 108건은 영업중 93·종료 15 유지. 건원릉 팝업이 지도 안(상단 165px~하단 788px)에 머물고 내용 1060px을 스크롤(439px 이동) 확인. 콘솔 오류 없음. `npm run build`, `build:deploy`, `git diff --check` 통과.

## 2026-09-11 전체보기 배율 고정·시즌·여름 비활성화

- 배율: 그룹 변경·동 전체 선택 시 `resetView`가 시작 화면(`INIT_VIEW`)으로 되돌리던 것을, 지도 크기에 맞춰 구리시 경계가 여백 10%로 들어오는 소수점 배율(`cityFit`)로 매번 계산하도록 바꿨습니다. 시작 화면도 같은 함수로 맞춥니다. `MapView`에 `snapToZoom:false`를 주어 소수점 배율이 정수(12)로 내려가 구리시가 작게 보이던 문제를 없앴습니다. `goTo` 전에 `view.when()`을 기다립니다.
- 시즌·여름 비활성화(코드 유지): theme.html 그룹에 `hidden:true`를 두고 `visibleGroups()`로 드롭다운 메뉴·기본 그룹에서 제외했습니다. `?group=시즌·여름` 직접 접근과 `cat` 파라미터 역탐색은 그대로 동작합니다. 홈은 `theme-groups.config.ts`에 `hidden` 플래그를 두고 `themeGroups`를 필터로 내보내 카드·검색에서 빠집니다. 헤더·푸터·지도 바로가기의 테마지도 링크는 `시즌·가을`로, 홈 "쉼터" 카드는 `안전·재난`(무더위·한파쉼터)으로 바꿨습니다. `season.config.ts`의 여름 계절 추천 항목은 여름 화면에서만 쓰이므로 그대로 두었습니다.
- 검증: 로컬 1280×800(지도 928×647)에서 시작·그룹 변경·동 전체 모두 배율 12.58로 일치, 그룹 메뉴 9개(여름 없음), 홈 카드에 여름 없음, 콘솔 오류 없음. `npm run build`, `build:deploy`, `tsc --noEmit`, prettier, `git diff --check` 통과. 개별 동 확대는 브라우저 패널이 숨김 상태라 애니메이션 `goTo`가 끝나지 않아 이 환경에서는 재확인하지 못했습니다(코드 변경 없음).

## 2026-09-14 시계열 항공사진 추가 (담당: 강민아)

- 페이지: `public/maps/aerial.html` 추가. 국토지리정보원 국토정보플랫폼 항공사진 WMTS(EPSG:5179)를 웹 메르카토르 위에 재투영해 2011~2025년 연도별로 보여주고, "두 시기 비교" 스와이프를 지원합니다. 헤더는 다른 지도 페이지와 같은 `service-header` 마크업이며 지도 높이는 헤더 57px 기준입니다.
- 공통 헤더: React `SiteHeader.tsx`와 정적 `theme.html`·`animal.html` 헤더(PC nav·모바일 nav) 모두 "유기동물 찾기" 옆에 "시계열 항공사진" 링크를 추가했습니다. 정적 HTML은 헤더 한 줄만 바꿨고 지도·데이터 로직은 손대지 않았습니다.
- 홈: 유기동물 안내 아래에 `aerial-section`(원형 일러스트 `TimeLapseArt.tsx` + "시간을 따라 보는 구리 / 우리 동네의 변화 과정을 구경하세요." + "시계열 항공사진 보기" 버튼) 추가. 스타일은 `service-home.css`의 `.aerial-*`이며 반려동물 섹션과 같은 구조로 모바일(620px 이하)에서는 세로 배치·가운데 정렬입니다.
- 링크 헬퍼: `links.ts`에 `aerialUrl()` 추가. `scripts/build-deploy.mjs` 필수 산출물에 `maps/aerial.html` 추가.
- 인증키: 항공사진 인증키(`NGII.apiKey`)는 도메인 등록형이라 국토정보플랫폼에 등록된 도메인(kgeodata.com, 개발 시 localhost)에서만 타일이 보입니다. 다른 도메인에 배포하면 등록을 추가해야 합니다.
- 브랜치: `work/kangmina-aerial-timelapse` (base `design/service-home-refresh` a6a5955). 같은 내용이 이전에 main(#5)에도 병합돼 있으나, 운영 미리보기는 `design/service-home-refresh` 기준입니다.
- 검증: `tsc --noEmit`, `npm run build`, `npm run build:deploy`(`out/maps/aerial.html` 생성·`/app/guri/maps/aerial.html` 링크 치환 확인), `npx prettier --check src public/styles/site-shell.css`, `git diff --check` 통과. 헤드리스 Chromium 1280px·390px에서 홈 섹션, 항공사진 페이지 헤더(현재 페이지 표시), 유기동물 페이지 헤더 링크 확인. 이 환경은 외부망이 막혀 항공사진 타일·유기동물 데이터 로드는 확인하지 못했습니다. 운영 배포 여부는 Actions 실행과 공개 URL로 별도 확인합니다.

## 2026-09-14 시계열 항공사진 2차 교체 (담당: 강민아)

- `public/maps/aerial.html`을 새 작업본으로 통째로 교체했습니다. 제목·공유 문구의 "구리생활지도"만 "구리시 G-MAP"으로 맞췄고 나머지는 작업본 그대로입니다.
- 추가된 기능: 왼쪽 위 주소·장소 검색(ArcGIS Search 위젯, 구리 인근으로 검색 범위 제한), 오른쪽 위 지역 선택(경기도 · 구리시 고정, 행정동 드롭다운 — `CITY.dongUrl` 행정동경계 FeatureServer에서 목록을 받아 이동·노란 외곽선 강조, 지도 이동 시 중심 동 자동 표시), 시 외곽선을 행정동 합집합으로 생성(별도 시경계 레이어 제거).
- 비교 방식 변경: "두 시기 비교"에서 연도를 누르면 먼저 고른 해가 새 해로 바뀌며 왼쪽은 항상 과거, 오른쪽은 최근 해입니다(기준 연도 select 제거). 비교 라벨은 지도 하단 좌·우로 이동.
- 브랜치: `work/kangmina-aerial-search-dong` (base `design/service-home-refresh` 2905de9).
- 검증: `npm run build:deploy`(`out/maps/aerial.html` 경로 치환 확인), `git diff --check` 통과. 헤드리스 Chromium 1280px·390px에서 헤더·검색창·지역 선택·연도 바 배치 확인. 외부망이 막힌 환경이라 ArcGIS 위젯 동작, 행정동 데이터, 항공사진 타일은 실제 브라우저에서 확인이 필요합니다.

## 2026-09-14 시계열 항공사진 시 외곽선 정리 (담당: 강민아)

- 증상: 행정동 합집합으로 만든 시 외곽선 안쪽(인창동·수택동 부근)에 작은 흰 자국이 보였습니다. 동 경계끼리 딱 맞물리지 않아 union 결과에 생긴 작은 구멍(안쪽 고리)과 조각(작은 섬)이 헤일로·본선으로 그려진 것입니다.
- 조치: `public/maps/aerial.html`에 `cleanOutline()` 추가. union 결과에서 시계 방향(바깥) 고리만 남기고 반시계 방향(구멍) 고리는 버리며, 바깥 고리 중 가장 큰 면적의 2% 미만인 조각도 버립니다. 동 선택·이동·현재 동 표시 로직과 항공사진 로직은 변경 없음.
- 브랜치: `work/kangmina-aerial-outline-clean` (base `design/service-home-refresh` 267dd12).
- 검증: 인라인 스크립트 `node --check`, `cleanOutline` 단위 검사(큰 고리 1 + 구멍 1 + 조각 1 → 큰 고리만 남음), `npm run build:deploy`, `git diff --check` 통과. 실제 행정동 데이터로는 외부망이 막혀 확인하지 못했으니 배포 후 지도에서 흰 자국이 사라졌는지 확인이 필요합니다.

## 2026-09-14 시계열 항공사진 검색 버튼 정리 (담당: 강민아)

- 증상: 왼쪽 위 주소 검색창의 돋보기 버튼이 ArcGIS 위젯 기본 높이(32px)로 그려져 42px 검색창 위쪽에 흰 틈이 남고 아이콘이 아래로 치우쳐 보였습니다.
- 조치: `public/maps/aerial.html`의 `.search-host` 규칙에서 `esri-search__form`·`esri-search__input-container`를 42px stretch 로 맞추고, 돋보기(`esri-search__submit-button`)·지우기(`esri-search__clear-button`) 버튼을 42px 높이·flex 가운데 정렬로 바꿨습니다. 검색 동작 로직은 변경 없음.
- 브랜치: `work/kangmina-aerial-search-button` (base `design/service-home-refresh` 5a61365).
- 검증: ArcGIS CSS 를 내려받을 수 없는 환경이라 위젯 기본 규칙(버튼 32px, flex 컨테이너)을 흉내 낸 목업으로 버튼이 42px 를 채우고 아이콘이 가운데 오는지 측정했습니다. `npm run build:deploy`, `git diff --check` 통과. 실제 위젯에서는 배포 후 확인이 필요합니다.

## 2026-09-14 시계열 항공사진 배율 안내문 (담당: 강민아)

- 배경: 국토정보플랫폼 항공사진은 2019년 이하 연도에 1:4,500보다 크게 확대한 배율의 타일이 없어, 그 배율에서는 바탕 지형도(브이월드)만 보입니다.
- 조치: `public/maps/aerial.html` 연도 버튼 아래에 안내문(`#tsNote`)을 추가했습니다. 설정은 `NGII.limited = {maxYear:2019, minScale:4500}`. 2019년 이하 연도가 선택돼 있을 때만 보이고(비교 모드는 두 해 중 해당 연도만 언급), 실제로 `view.scale`이 4,500보다 작으면 "지금 배율에서는 … 바탕 지형도가 보여요" 문구로 바뀌며 노란 강조색이 됩니다. `reactiveUtils.watch(view.scale)`로 배율이 바뀔 때마다 갱신합니다. 항공사진·비교 로직은 변경 없음.
- 브랜치: `work/kangmina-aerial-scale-note` (base `design/service-home-refresh` 1b3dbf3).
- 검증: 인라인 스크립트 `node --check`, `updateNote` 단위 검사 5건(해당 없음/단일 연도/확대 상태/비교 모드 한쪽만/비교 모드 양쪽) 통과, `npm run build:deploy`, `git diff --check` 통과. 실제 지도에서의 표시는 배포 후 확인이 필요합니다.

## 2026-09-14 테마지도 배경 웹맵 통일·축제 테마 추가 (담당: 강민아)

- 배경지도: `CITY.basemapWebmapId`에 구리시 포털 웹맵 `51c2bc2db0d3423382d30ff755563f31`을 넣어 테마지도의 모든 배경이 이 웹맵의 베이스맵을 쓰도록 했습니다(`useWebmapBasemap`). 읽어 온 베이스맵은 `WM_BASEMAP`에 두어 그룹 웹맵으로 지도를 바꿀 때도 같은 배경을 적용합니다. 로딩 제한을 15초로 늘리고, 하위 레이어(loadAll)가 늦어도 베이스맵은 먼저 적용합니다. 이 페이지가 시 바깥 음영을 직접 그리므로 웹맵 안의 마스크성 레이어(제목에 mask/마스크/음영/dim/바깥/외부)는 겹치지 않게 뺍니다. 웹맵을 못 읽으면 기존처럼 브이월드 → 바로e맵 → 회색 순으로 대체합니다.
- 축제 테마: `시즌·가을` 그룹의 `구리 명소` 앞에 `축제` 추가(`Hosted/culture_festival_New/FeatureServer`). 목록은 이름 + 상태 배지(진행중·오늘 개최·예정·계획·일정 미정·종료), 기간(`시작일`~`종료일`, 예정이면 "n일 뒤 시작"), 장소명. 팝업은 구리 명소와 같은 구성으로 소개(`축제소개`), 축제유형·무료·연계행사 칩, 기간·시간·장소·주요 프로그램·요금·주최·주관·연계행사·일정 확정(`확정수준`+`최종확인일`)·참고(`비고`), 공식페이지 링크, 문의처 전화, 사진 여러 장(`이미지URL`, 쉼표·공백·줄바꿈 구분). 심볼은 상태 색 깃발(`festSym`), 순서는 진행중 → 예정(가까운 순) → 계획·미정 → 종료(최근 순).
- 렌더 로직 변경(최소): 목록 정렬에 테마별 `sortRank` 훅 한 줄 추가(다른 테마는 0이라 영향 없음), 상태 배지 CSS `.st.live/.soon/.plan/.done` 추가. CITY/GROUPS의 기존 테마와 F는 변경 없음.
- 브랜치: `work/kangmina-theme-basemap-festival` (base `design/service-home-refresh` e013e29).
- 검증: 인라인 스크립트 전체 `node --check`, 축제 상태·기간·시간·정렬 단위 검사(종료/예정/epoch 날짜/계획/미공개/진행중/오늘 8건), `npm run build:deploy`, `git diff --check` 통과. 구리시 서버(guri.go.kr)가 이 환경에서 차단돼 웹맵 베이스맵 실제 적용, 축제 데이터 로드, 사진 표시는 배포 후 브라우저에서 확인이 필요합니다.

## 2026-09-14 테마지도 배경 바로e맵 기본화·시 외곽선 통일·축제 팝업 정리 (담당: 강민아)

- 배경지도: 포털 웹맵(`basemapWebmapId`)이 실제 화면에서 적용되지 않아(브이월드가 그대로 보임), 웹맵과 같은 모습인 구리시 포털 바로e맵 벡터타일(`CITY.ngiiVt`)을 기본 배경으로 바꿨습니다. 대체 순서는 바로e맵 → 브이월드 → 회색. 웹맵 읽기 시도는 그대로 두어 성공하면 그 베이스맵으로 바뀝니다. 콘솔에 `[배경 웹맵 실패]` 또는 `[배경] …대체` 경고로 원인을 남깁니다.
- 시 외곽선·마스크: 시경계 레이어(`boundaryUrl`)와 행정동 경계가 어긋나 경계가 두 줄로 보이던 문제. 시경계 FeatureLayer 두 장(`bndHalo`/`bnd`)을 기본 지도에서 빼고, 행정동 레이어를 4326으로 질의해 `geometryEngine.union` + `cleanOutline`(바깥 고리만, 작은 조각 제거)으로 만든 외곽선을 `bndLayer`(GraphicsLayer)에 그립니다. 바깥 음영 마스크도 같은 도형으로 그립니다(시계열 항공사진과 같은 방식). 합집합에 실패하면 예전 시경계 레이어와 마스크로 되돌립니다. `getCityRings`(전체보기 배율 계산)는 그대로 시경계를 씁니다.
- 축제 팝업: '일정 확정' 항목 제거. '참고'(`비고`)는 `festNote`로 "…개최장소 사용", "위치 근거", "데이터의 연속성" 같은 관리용 문장을 뺀 뒤 요약. '공식페이지 바로가기'는 `festLink`로 값이 http(s) 주소이고 사이트 첫 화면이 아니며 다른 축제와 같은 주소(공통 안내 페이지)가 아닐 때만 버튼을 만듭니다. 이를 위해 팝업 링크 설정에 `fn:(row,pickVal,theme)=>url|null` 지원을 한 줄 추가했습니다.
- 브랜치: `work/kangmina-theme-basemap-boundary` (base `design/service-home-refresh` 2fd9601).
- 검증: 인라인 스크립트 `node --check`, `festNote`/`festLink` 단위 검사 6건, `npm run build:deploy`, `git diff --check` 통과. 구리시 서버가 차단된 환경이라 바로e맵 표시, 외곽선 합집합, 축제 팝업은 배포 후 브라우저 확인이 필요합니다.

## 2026-09-14 테마지도 배경맵 아이템(51c2bc2d…) 적용 방식 보강 (담당: 강민아)

- 요청: 배경맵 아이템 `51c2bc2db0d3423382d30ff755563f31`을 테마지도 배경으로. 앞서 WebMap 로드 → 베이스맵 추출 한 가지 방법만 있어 실제 화면에서 적용되지 않았습니다.
- 조치: `useWebmapBasemap`을 세 단계로 바꿨습니다. ① `Basemap({portalItem:{id}})` 직접 로드(배경맵 갤러리 방식) → ② `WebMap` 로드 후 베이스맵 추출 → ③ `…/sharing/rest/content/items/{id}/data?f=json`을 직접 읽어 `baseMap.baseMapLayers`를 VectorTileLayer/TileLayer/MapImageLayer/WebTileLayer로 조립. 각 20초 제한. 성공하면 `WM_BASEMAP`에 두어 그룹 웹맵 전환 시에도 유지. 웹맵의 일반 레이어(마스크 등)는 더 이상 추가하지 않습니다(배경만). 모두 실패하면 바로e맵을 유지하고 콘솔에 `[배경 웹맵 실패 — 바로e맵 유지]`와 단계별 사유, 공유 설정 확인 주소를 남깁니다.
- 확인 필요: 아이템이 포털에서 "모든 사용자(공개)"로 공유돼 있어야 로그인하지 않은 시민도 배경을 볼 수 있습니다. 비공개면 세 방법 모두 실패합니다.
- 브랜치: `work/kangmina-theme-webmap-basemap` (base `design/service-home-refresh` 682a6fc).
- 검증: 인라인 스크립트 `node --check`, ③ 조립 분기 단위 검사(벡터타일·숨김 레이어 제외·WebTiled 투명도), `npm run build:deploy`, `git diff --check` 통과. 포털이 이 환경에서 차단돼 실제 적용은 배포 후 브라우저 콘솔의 `[배경 웹맵] 적용(…)` 메시지로 확인해야 합니다.

## 2026-09-14 문화·여가 축제·행사 → 축제 테마로 교체 (담당: 강민아)

- `문화·여가` 그룹의 `축제·행사`(예전 `culture_festival`, 카드형)를 `시즌·가을`의 `축제`와 같은 테마로 바꿨습니다. 정의를 `festTheme()` 팩토리 함수 하나로 빼고 두 그룹에서 `'축제':festTheme()`로 각각 새 객체를 만들어 씁니다(테마 객체는 실행 중 상태가 붙으므로 공유하지 않음). 데이터는 둘 다 `culture_festival_New`.
- 심볼: 축제 깃발은 `SYM['fest_flag']`로 등록하고 테마 `sym:'fest_flag'`. 원래 base64 `culture_festival` 아이콘은 덮어쓰지 않고 그대로 둡니다.
- 브랜치: `work/kangmina-culture-festival` (base `design/service-home-refresh` b9da18b).
- 검증: 인라인 스크립트 `node --check`, 로컬 헤드리스 Chrome에서 `문화·여가`·`시즌·가을` 테마 순서와 데이터 주소 확인, `npm run build:deploy`, `git diff --check` 통과. 실제 데이터 표시는 배포 후 확인이 필요합니다.

## 2026-09-16 테마지도 배경을 벡터타일 3장으로 직접 구성 (담당: 강민아)

- 포털 웹맵(51c2bc2d…)은 실제 화면에서 적용되지 않아, 그 웹맵의 베이스맵 구성을 레이어로 직접 재현했습니다. `CITY`에 `ngiiVt`(NGII_MAP_SD_20260901), `guriBndVt`(GURI_BND), `koreaBndVt`(Korea_Boundary) 벡터타일 주소를 두고, 베이스맵을 아래→위 순으로 ① NGII_MAP_SD 일반 → ② GURI_BND_SE `blendMode:"darken"` → ③ Korea_Boundary SE `blendMode:"multiply"`로 겹칩니다. `basemapWebmapId`는 비워 웹맵 시도를 끕니다(코드는 유지).
- 자체 바깥 음영 마스크(`maskLayer`)는 이 배경이 이미 바깥을 어둡게 하므로 기본 숨김이고, ①을 못 읽어 브이월드로 대체될 때만 켭니다. ②③은 못 읽어도 지도는 유지되며 콘솔 경고만 남깁니다.
- 브랜치: `work/kangmina-theme-layer-basemap` (base `design/service-home-refresh` 417b1cb).
- 검증: 인라인 스크립트 `node --check`, `npm run build:deploy`, `git diff --check` 통과. 구리시 서버가 차단된 환경이라 실제 배경 모습(음영·경계 그림자·블렌드)은 배포 후 브라우저 확인이 필요합니다.

## 2026-09-16 테마지도 전체보기 범위 맞춤·시 외곽선 숨김 (담당: 강민아)

- 증상: 주제 변경·동 전체 선택 시 구리시 북쪽이 잘리는 배율로 나옴. 전체보기(`resetView`)와 시작 화면이 `cityFit()`의 줌 숫자로 배율을 정하는데, 줌 숫자의 실제 축척은 배경 타일 체계(LOD)에 따라 달라서 벡터타일 배경으로 바꾼 뒤 같은 줌이 더 크게 확대됐습니다.
- 조치: `fitExtent()`(구리시 범위 + 여백 5%, 4326)를 두고 시작 화면은 `view.extent=fitExtent()`, 전체보기는 `view.goTo({target:fitExtent()})`로 범위를 맞춥니다(소수점 배율 허용, 타일 체계와 무관). 실패할 때만 예전 `cityFit()` 줌 계산을 씁니다. 동 이동(`gotoDong`)도 동 범위 goTo를 먼저, 중심+줌은 예비로 바꿨습니다. 콘솔에 배율과 축척(1:n)을 함께 남깁니다.
- 시 외곽선: 배경(GURI_BND_SE)이 경계 그림자를 그리므로 행정동 합집합 외곽선(`bndLayer`)은 기본 숨김이고, 바로e맵을 못 읽어 브이월드로 대체될 때만 마스크와 함께 켭니다.
- 브랜치: `work/kangmina-theme-fit-outline` (base `design/service-home-refresh` 4bac670).
- 검증: 인라인 스크립트 `node --check`, `fitExtent` 단위 검사, `npm run build:deploy`, `git diff --check` 통과. 실제 배율은 배포 후 브라우저에서 주제 변경·동 전체·동 선택으로 확인이 필요합니다.

## 2026-09-16 전체보기·동 이동 복구 (담당: 강민아)

- 증상: 직전 변경(#16) 뒤 주제 변경·동 전체에서 구리시 전체가 보이지 않고, 동 선택 시 확대·이동도 되지 않았습니다.
- 원인: `view.goTo({target:{type:"extent",…}})`처럼 일반 객체로 준 범위는 ArcGIS goTo가 이동 대상(도형)으로 인식하지 않아 아무 동작 없이 성공으로 끝났고, 그래서 예비 경로(중심+줌)도 실행되지 않았습니다.
- 조치: `esri/geometry/Extent`를 로드해 `ExtentCls`로 두고, `asExtent()`로 실제 Extent 도형을 만들어 `view.goTo(도형)`으로 넘깁니다. 시작 화면·전체보기(`fitExtent`)·동 이동(`gotoDong`)·`moveTo` 모두 적용. Extent 모듈이 없으면 예외를 던져 예전 중심+줌 경로로 넘어갑니다.
- 브랜치: `work/kangmina-theme-fit-fix` (base `design/service-home-refresh` 7f62e18).
- 검증: 인라인 스크립트 `node --check`, `fitExtent`/`asExtent` 단위 검사(Extent 인스턴스 생성, 모듈 없을 때 예외), `npm run build:deploy`, `git diff --check` 통과. 실제 이동은 배포 후 브라우저에서 주제 변경·동 전체·동 선택으로 확인이 필요합니다.

## 2026-09-16 동 선택 강조 경계 모양 일치 (담당: 강민아)

- 증상: 동 선택 시 깜빡이는 강조 경계가 지도에 그려진 행정동 점선 경계와 모양이 달랐습니다. 강조·동 필터용 행정동 도형을 받아올 때 `maxAllowableOffset=0.0004`(≈40m)로 단순화한 것이 원인입니다.
- 조치: `loadDongs`의 질의를 `maxAllowableOffset=0.00001`(≈1m)로 바꿔 지도에 그려지는 점선 경계(같은 행정동 레이어 원본)와 같은 모양이 되게 했습니다. 동 필터(점-폴리곤 판정)도 같은 도형을 쓰므로 함께 정확해집니다. 구리시 행정동은 9개라 데이터 증가는 미미합니다.
- 브랜치: `work/kangmina-dong-highlight-shape` (base `design/service-home-refresh` 2b2cba7).
- 검증: 인라인 스크립트 `node --check`, `npm run build:deploy`, `git diff --check` 통과. 실제 모양 일치는 배포 후 동 선택으로 확인이 필요합니다.

## 2026-09-16 등산로 팝업 길이·시간 단위 수정 (담당: 강민아)

- 증상: 등산로 팝업이 길이 2.39를 "2.39m", 상행·하행 42·30을 "42시간·30시간"으로 표시. 데이터는 길이 km, 시간 분 단위의 숫자입니다.
- 조치: `hikeLen(v)`(100 미만 숫자는 km, 100 이상은 m, 단위가 이미 있으면 그대로)·`hikeMin(v)`(분 → "42분", 60분 이상은 "1시간 35분") 헬퍼를 두고 `시즌·가을`·`문화·여가`의 등산로 팝업 '등산로 길이'·'상행시간'·'하행시간' 항목에 적용했습니다.
- 브랜치: `work/kangmina-hiking-units` (base `design/service-home-refresh` 88215e3).
- 검증: 인라인 스크립트 `node --check`, 단위 변환 단위 검사 12건, `npm run build:deploy`, `git diff --check` 통과.

## 2026-09-16 3D 지도 추가 (담당: 강민아)

- 페이지: `public/maps/scene.html`. 구리시 포털 웹씬 `b5e573a06e7f4195bb2f092aad19b253`을 `WebScene` + `SceneView`(qualityProfile high)로 엽니다. 로드 후 대기·별·고화질 대기 효과, 직사 그림자·주변광 차폐·물 반사, 6월 오후 2시 햇빛을 적용하고(`beautify`), 하단 바에서 그림자 끄기·저녁 빛(18:30) 전환이 가능합니다. 웹씬에 저장된 슬라이드가 있으면 "장소 바로가기" 칩과 "한 바퀴 둘러보기"(슬라이드 순회)가 나오고, 없으면 안내 문구만 나옵니다. 우상단 컨트롤: 확대·축소, 위에서/비스듬히 보기 전환, 북쪽 맞추기, 내 위치, 처음 화면(웹씬 시작 화면, 없으면 구리시 중심), 공유. 로딩 덮개와 실패 시 안내(공개 설정 확인·다시 시도·구리시 3D 뷰어 열기 링크)가 있습니다. WebGL 미지원 브라우저는 안내만 표시.
- 메뉴: React `SiteHeader.tsx`와 정적 `theme.html`·`animal.html`·`aerial.html` 헤더(PC·모바일)에 "3D 지도"를 유기동물 찾기와 시계열 항공사진 사이에 추가. `links.ts`에 `sceneUrl()`.
- 홈: 유기동물 안내와 시계열 항공사진 사이에 `scene-section`(등각 건물 일러스트 `SkylineArt.tsx`, "입체로 보는 구리 / 우리 동네를 하늘에서 내려다보세요.", "3D 지도 보기" 버튼, 파란 톤) 추가. 항공사진 섹션 번호는 04로.
- `scripts/build-deploy.mjs` 필수 산출물에 `maps/scene.html` 추가.
- 브랜치: `work/kangmina-3d-scene` (base `design/service-home-refresh` cb4d0c2).
- 검증: `tsc --noEmit`, prettier, scene.html 인라인 스크립트 `node --check`, `npm run build`, 헤드리스 Chrome 홈(PC 1280·모바일 390) 및 3D 페이지 셸 렌더링 확인, `npm run build:deploy`, `git diff --check` 통과. 구리시 포털이 이 환경에서 차단돼 실제 3D 씬 로딩·효과·슬라이드는 배포 후 브라우저 확인이 필요합니다. 웹씬 아이템이 "모든 사용자(공개)"로 공유돼 있어야 시민이 볼 수 있습니다.

## 2026-09-16 3D 지도: 웹씬 스냅샷 방식 (담당: 강민아)

- 증상: 배포된 3D 지도가 "Failed to load portal item"으로 실패. 웹씬 아이템은 공개(`access:public`)이고 시크릿 창에서 JSON이 읽히므로 공유 문제는 아니며, kgeodata.com 브라우저에서 구리시 포털(/gmap)로의 교차 출처 요청이 막히는 것(CORS)으로 판단. 지도 서비스(/gmapsvr)는 정상.
- 조치: `scripts/fetch-scene.mjs`가 `…/items/b5e573a0…/data?f=json`을 받아 `public/maps/data/scene.json`으로 저장하고, `build:deploy`가 `next build` 전에 이 스크립트를 실행합니다(실패해도 배포는 계속, 기존 파일이 있으면 그대로 사용). `scene.html`은 같은 서버의 `data/scene.json`을 먼저 읽어 `WebScene.fromJSON`으로 열고, 없으면 포털에서 직접 읽습니다. 실패하면 아이템 JSON을 직접 조회해 공개 설정 문제인지 CORS인지 구분해 안내합니다.
- 씬을 포털에서 수정한 뒤 반영하려면 배포를 다시 실행(design 브랜치 push 또는 Actions의 Run workflow)하면 됩니다. GitHub 러너가 포털에 접속하지 못하는 경우엔 시크릿 창에서 위 data 주소를 열어 JSON을 `public/maps/data/scene.json`으로 저장해 커밋해도 됩니다. 로컬은 `npm run fetch:scene`.
- 브랜치: `work/kangmina-3d-snapshot` (base `design/service-home-refresh` bf779c4).
- 검증: 스크립트 `node --check`, 가짜 응답으로 스냅샷 저장·검증 로직 확인, `npm run build:deploy`, `git diff --check` 통과. 실제 씬 표시는 배포 후 확인 필요(Actions 로그의 `[scene snapshot]` 줄로 러너가 JSON을 받았는지 확인).

## 2026-09-16 3D 지도: 웹씬 스냅샷 커밋·명소 바로가기 (담당: 강민아)

- 배포 로그의 `[scene snapshot] … Item does not exist or is inaccessible`로 GitHub 러너(해외 IP)는 포털 data 엔드포인트를 읽지 못하지만, 국내 브라우저(시크릿 창)에서는 읽히는 것을 확인. 담당자가 저장한 웹씬 JSON을 `public/maps/data/scene.json`으로 커밋했습니다(`_snapshot.source: manual`). `build:deploy`의 자동 스냅샷이 실패하면 이 파일을 그대로 씁니다. 씬을 포털에서 바꾼 뒤에는 같은 방법으로 JSON을 다시 저장해 교체하면 됩니다.
- 스냅샷 안에서 포털(/gmap)을 가리키던 것은 `Korea_Boundary SE` 벡터타일의 스타일 주소 하나뿐이라 지도 서버(`gmapsvr/…/Korea_Boundary/VectorTileServer`)로 바꿨습니다(`fetch-scene.mjs`도 같은 정리를 합니다). 건물 3D(LOD1·LOD2 SceneServer), 지형(Esri Terrain3D + 구리 NGII_DEM_5m), 항공영상(브이월드), 피처 레이어는 모두 브라우저에서 직접 읽습니다.
- 웹씬에 슬라이드가 없어 `scene.html`이 구리 명소 레이어(`autumn_foliage/FeatureServer/0`, 최대 12곳)를 조회해 "장소 바로가기" 칩과 "한 바퀴 둘러보기"를 만듭니다(각 명소로 비스듬히 날아감). 웹씬에 슬라이드를 넣으면 그것이 우선합니다.
- 브랜치: `work/kangmina-3d-snapshot-data` (base `design/service-home-refresh` 5b36abb).
- 검증: scene.html 인라인 스크립트 `node --check`, 스냅샷 JSON 구조·포털 참조 제거 확인, `npm run build:deploy`(스냅샷 파일이 out/maps/data 에 포함되는지), `git diff --check` 통과. 실제 3D 표시는 배포 후 브라우저 확인 필요.

## 2026-09-16 3D 지도 명소·축제 심볼·팝업 (담당: 강민아)

- 증상: 3D 씬에서 명소·축제 심볼이 안 보임. 웹씬 렌더러(uniqueValue, 필드 `이름`/`축제명`)의 아이콘 주소가 포털 아이템 안의 상대 경로(`./resources/symbols/resources/*.png`)라 우리 사이트에서는 읽을 수 없기 때문.
- 조치: 담당자가 준 PNG 22장을 `public/maps/sym/scene/`에 올리고, `scripts/scene-sanitize.mjs`(공용 정리 모듈)가 스냅샷의 아이콘 주소를 `/maps/sym/scene/파일명`으로 바꿉니다(배포 시 `/app/guri/maps/...`로 치환). 이름이 렌더러에 없는 항목용 기본 심볼(원형)도 추가. `fetch-scene.mjs`도 이 모듈을 써서 자동 스냅샷에 같은 정리가 적용됩니다. 새 명소·축제가 생기면 CSV의 파일명 규칙대로 PNG를 추가하고 포털 렌더러에 값을 넣은 뒤 스냅샷을 다시 저장하면 됩니다.
- 팝업: 웹씬에 이미 있는 Arcade 팝업(사진 여러 장·칩·정보 행·전화/홈페이지 버튼)을 그대로 씁니다. 축제 팝업만 빈 필드 표 제거, '참고'에서 "…개최장소 사용" 같은 관리용 문장 제거(`NoteClean`), 공식페이지 버튼은 실제 페이지 주소일 때만(`LinkOK`, 사이트 첫 화면 제외)으로 테마지도와 기준을 맞췄습니다.
- 브랜치: `work/kangmina-3d-symbols` (base `design/service-home-refresh` 11ad0d6).
- 검증: 스크립트 `node --check`, 스냅샷 재정리 결과(22개 주소 치환·기본 심볼·팝업 요소) 확인, `npm run build:deploy`에서 `out/maps/data/scene.json`의 아이콘 주소가 `/app/guri/maps/sym/scene/`으로 치환되는지 확인, `git diff --check` 통과. 실제 아이콘·팝업 표시는 배포 후 확인 필요.

## 2026-09-16 3D 지도 심볼 주소 절대화·기본 핀·이름 레이블 (담당: 강민아)

- 증상: 심볼 주소를 `/app/guri/maps/sym/…`(루트 상대)로 넣었더니 ArcGIS가 웹씬 JSON의 상대 href를 페이지가 아닌 포털 기준으로 풀어 아이콘을 찾지 못했고, 렌더러에 없는 이름은 기본 원형만 보였습니다.
- 조치: `scene.html`이 스냅샷을 읽은 직후 `absolutizeIcons()`로 렌더러 아이콘 href를 페이지 기준 절대 주소(`new URL(href, location.href)`)로 바꿉니다(로컬·배포 모두 동작). 기본 심볼은 순수 파이썬으로 만든 초록 핀 `public/maps/sym/scene/pin.png`(64×80)을 18px, 아래 기준점으로 씁니다. 명소(`이름`)·축제(`축제명`) 레이블을 `labelingInfo`(LabelSymbol3D, 11px 굵게, 흰 테두리, 아이콘 위, `deconflictionStrategy: static`으로 겹치면 자동 숨김)로 넣고 `showLabels: true`. 모두 `scene-sanitize.mjs`에 있어 스냅샷을 교체해도 다시 적용됩니다.
- 브랜치: `work/kangmina-3d-symbols-fix` (base `design/service-home-refresh` 39d227c).
- 검증: 스크립트 `node --check`, 스냅샷 재정리 결과(기본 핀·레이블·showLabels), `absolutizeIcons` 단위 검사, `npm run build:deploy`, `git diff --check` 통과. 실제 아이콘·레이블 표시는 배포 후 확인 필요.

## 2026-09-16 3D 지도 명소·축제를 페이지가 직접 얹는 방식으로 (담당: 강민아)

- 증상: 아이콘 주소를 절대 주소로 바꾼 뒤에도 웹씬 JSON의 3D 아이콘(PointSymbol3D Icon, 60px)은 보이지 않고 기본 핀·레이블만 보였습니다. 웹씬 정의의 3D 아이콘 심볼 자체가 이 환경에서 렌더링되지 않는 것으로 판단.
- 조치: `scene.html`이 스냅샷에서 `명소`·`축제` 레이어 정의를 떼어 내고(`takeOverlayDefs`), 씬이 준비되면 같은 서비스 주소(테마지도와 동일: `autumn_foliage/0`, `culture_festival_New/14`)로 `FeatureLayer`를 직접 만들어 얹습니다(`addOverlays`). 심볼은 렌더러의 이름→PNG 매핑을 그대로 쓰되 2D 그림 마커(picture-marker, 명소 44px·축제 40px, 빌보드)로, `elevationInfo: relative-to-scene(+6m)`으로 건물·지형 위에 놓아 가려지지 않게 했습니다. 이름이 없으면 초록 핀(16×20). 레이블은 label-3d(11px 굵게·흰 테두리, 아이콘 위, 겹치면 숨김). 팝업은 웹씬의 Arcade 팝업 JSON을 `PopupTemplate.fromJSON`으로 그대로 사용.
- 포털에서 직접 읽는 대체 경로(스냅샷 없음)에서는 이 처리가 없고 웹씬 정의를 그대로 씁니다.
- 브랜치: `work/kangmina-3d-overlay-layers` (base `design/service-home-refresh` ab75c12).
- 검증: 인라인 스크립트 `node --check`, 단위 검사(레이어 분리·렌더러 22개 심볼 URL·기본 핀·레이블 식·팝업 요소), `npm run build:deploy`, `git diff --check` 통과. 실제 표시는 배포 후 확인 필요.

## 2026-09-16 3D 지도 레이블 축약·테마지도식 팝업·심볼 그림자 (담당: 강민아)

- 레이블: `LABEL_SHORT` 지정 목록(예: "2026 구리 코스모스축제" → "코스모스 축제", "갈매구릉산자락길(무장애나눔길)" → "갈매구릉산자락길")을 Arcade Dictionary 로 넣고, 목록에 없으면 '제n회'·연도·괄호·'구리'를 떼어 짧게 만듭니다(`shortLabelArcade`).
- 팝업: ArcGIS 팝업 대신 테마지도의 축제·구리 명소 팝업과 같은 구성의 카드(`#infocard`, CSS 이식)를 페이지가 직접 그립니다(`showCard`, `CARD` 설정). 사진 여러 장, 상태·칩, 소개, 주소(복사)·전화, 정보 행, 전화·홈페이지 버튼, 안내 문구까지 같고 네이버 길찾기만 뺐습니다. 축제의 참고 문장 정리·공식페이지 조건(`festNote`/`festLink`, 전체 행 캐시로 중복 주소 제외)도 동일. 얹은 레이어는 `popupEnabled:false`, `view.hitTest`로 클릭한 피처의 속성을 카드에 표시.
- 심볼: `scripts/shadow-icons.py`(순수 파이썬 PNG 디코드·박스 블러·합성)로 `public/maps/sym/scene/shadow/*.png`(284×275, 아래로 7px 이동한 부드러운 그림자)를 만들어 사용. 그림 심볼은 명소 58px·축제 54px 로 키우고, 이름이 목록에 없는 곳의 초록 핀은 12×15 로 줄였습니다. 원본 PNG를 바꾸면 `python3 scripts/shadow-icons.py`로 다시 생성.
- 브랜치: `work/kangmina-3d-polish` (base `design/service-home-refresh` e485ec4).
- 검증: 인라인 스크립트 `node --check`, 레이블 축약·팝업 카드 조립 단위 검사(샘플 행), `npm run build:deploy`, `git diff --check` 통과. 실제 표시는 배포 후 확인 필요.

## 2026-09-17 3D 지도 둘러보기 팝업·둘레길/등산로 3D 심볼·팝업 (담당: 강민아)

- 둘러보기 팝업: 장소 바로가기·'한 바퀴 둘러보기'로 명소에 도착하면 그 명소의 팝업 카드가 자동으로 뜹니다(`PLACES`에 `attrs` 저장, `flyToSlide`가 비행이 끝난 뒤 `showCard`; 비행이 겹치면 마지막 것만). 카드를 읽을 수 있게 둘러보기 머무는 시간을 3.6초→5초로 늘렸고, 처음 화면으로 돌아가면 카드를 닫습니다.
- 둘레길·등산로: 웹씬의 투박한 3D 심볼(원형 아이콘·20m 두께 관) 대신 테마지도와 같은 서비스 레이어 4개(둘레길 `culture_dulle/7`, 둘레길 시설물 `culture_dulle_fac/0`, 등산로 `culture_hiking_new/17`, 등산로 시설물 `culture_hiking_fac_new/0`)를 명소·축제처럼 스냅샷에서 떼어 내(`OVERLAY_KIND`) 페이지가 직접 그립니다(`trailLayer`).
  - 선: 지면에 입힌 두 겹 선(흰 테두리 + 색, `lineSym3D`). 둘레길은 테마지도의 `COURSE_INFO`/`COURSE_COLORS`와 같은 코스 색(1 아차산-망우산길 초록, 2 구릉산-갈매마을길 주황, 3 왕숙천길 파랑, 4 한강코스모스길 분홍)으로 스냅샷 렌더러의 코스 값마다 색을 매기고, 4만 분의 1 이하로 다가가면 '1코스 아차산-망우산길' 식의 선 레이블이 붙습니다. 등산로는 초록(#5B8C5A) 선 위에 흰 점선 무늬.
  - 시설물: 테마지도 픽토그램(`public/maps/sym/scene/src/*.png`, 테마지도 SYM 에서 추출)에서 흰 그림만 떼어 코스 색 바탕의 둥근 배지(흰 테두리·그림자)로 다시 그린 PNG(`public/maps/sym/scene/trail/`, 116×121)를 30px 그림 마커로 건물 위(relative-to-scene)에 띄웁니다. 둘레길 시설물은 행을 읽은 뒤 코스 필드(`둘레길이름` 등)를 찾아 코스별 배지로 바꾸고(`dulle_fac_1~8.png`, 기본 `dulle_fac_0.png`), 등산로 시설물은 `hiking_fac.png`. 시설물은 2만 5천 분의 1 이하에서, 이름 레이블은 6천 분의 1 이하에서 보입니다. `scripts/trail-icons.py`(순수 파이썬, `shadow-icons.py`의 PNG·그림자 함수를 재사용)로 생성하며 색·원본을 바꾸면 `python3 scripts/trail-icons.py`로 다시 만듭니다.
  - 팝업: 테마지도 '시즌·가을'의 둘레길/둘레길 시설물/등산로/등산로 시설물 팝업과 같은 구성(`CARD.dulle/dulleFac/hiking/hikingFac`) — 제목·머리말·칩·소개·정보 행(등산로 길이 km·시간 분 변환 `hikeLen`/`hikeMin`, 119 안내문)과 테마지도의 자동 정보 행(`autoRows`, 시스템 필드 제외)까지 같고 네이버 길찾기만 없습니다. 카드 색은 코스 색을 따르고, 클릭한 둘레길·등산로 구간은 노랗게 강조(`layerView.highlight`)했다가 카드를 닫으면 풀립니다.
- 브랜치: `work/kangmina-3d-trails` (base `design/service-home-refresh` 5e5a6c5).
- 검증: 인라인 스크립트 `node --check`, 단위 검사(코스 번호·색·배지, 스냅샷 렌더러 값 추출과 코스 선 렌더러, 시설물 코스 배지 전환, 4종 팝업 카드 조립, 둘러보기 도착 후 팝업), `npm run build:deploy`(출력에 `maps/sym/scene/trail/` 10장 포함), `git diff --check` 통과. 실제 3D 표시(선 굵기·배지 크기·레이블 겹침)는 배포 후 확인 필요.

## 2026-09-17 3D 지도 등산로 팝업 상행·하행시간 누락·시설물 표시 축척 (담당: 강민아)

- 증상: 3D 지도 등산로 팝업에 상행시간·하행시간이 빠짐. 서비스 필드명이 후보('상행시간')보다 긴 형태라 정확히 일치하는 이름만 찾던 3D 페이지의 `pv`가 놓쳤습니다(테마지도 `pickVal`은 부분일치 폴백이 있어 보였음).
- 조치: `pv`에 테마지도와 같은 부분일치 폴백(키에 후보가 포함되면 사용)을 넣어 네 레이어 팝업이 테마지도와 같은 항목을 보이게 했습니다.
- 시설물 축척: 둘레길·등산로 시설물이 멀리서도 다 보여 복잡하다는 의견으로 `minScale`을 25,000 → 3,000(길 하나가 화면에 차는 정도)으로, 이름 레이블은 6,000 → 1,500으로 좁혔습니다.
- 브랜치: `work/kangmina-3d-trails-fix` (base `design/service-home-refresh` d931375).
- 검증: 인라인 스크립트 `node --check`, 단위 검사(긴 필드명 행의 상행·하행시간 표시, 축척값), `npm run build:deploy`, `git diff --check` 통과.

## 2026-09-17 3D 지도 건물 팝업 카드화·기울기/북쪽 전환 시 화면 중심 유지 (담당: 강민아)

- 건물 팝업: 웹씬 3D 건물(SceneLayer LOD1 `3D_Buildings_LOD1_2508`, LOD2 `Buildings_LOD2_2508`)의 ArcGIS 기본 팝업(우하단 도킹)을 끄고(`view.popupEnabled=false`, `prepBuildings`), 클릭하면 웹씬에 설정된 Arcade 팝업과 같은 구성(용도·구조 칩, 층수·높이·면적·건폐율·용적률·세대·지붕·사용승인·행정구역·건물번호·PNU, 안내문)을 명소·둘레길과 같은 좌상단 카드로 그립니다(`CARD.bldg1/bldg2`, 헬퍼 `bC/bPos/bArea/bPct/bMtr/bYmd/bNo`는 Arcade 의 C/Pos/Area/Pct/Mtr/Ymd 규칙과 동일, LOD2 코드값은 레이어 필드 도메인으로 이름 변환 `domainName`). 히트 결과에 속성이 없으면 ObjectID 로 다시 조회(`bldgAttrs`). 클릭한 건물은 노랗게 강조.
- 기울기·북쪽: '위에서 보기/비스듬히 보기'와 '북쪽 맞추기'가 카메라 위치를 그대로 두고 기울기만 바꿔 화면이 다른 곳으로 가던 것을, 지금 보는 화면 중심(`view.center`)·축척을 유지한 채 기울기·방향만 바꾸도록 고쳤습니다(`pivotView`).
- 브랜치: `work/kangmina-3d-bldg-popup` (base `design/service-home-refresh` e70576c).
- 검증: 인라인 스크립트 `node --check`, 단위 검사(레이어 종류 판별, 도메인 이름, LOD1/LOD2 카드 조립과 0 값·중복 숨김, ObjectID 재조회, 기울기·북쪽 전환 시 중심·축척 유지), `npm run build:deploy`, `git diff --check` 통과. 실제 SceneLayer 히트 속성·조회 동작은 배포 후 확인 필요.

## 2026-09-17 3D 지도 등산로 산 이름 레이블 (담당: 강민아)

- 요청: 등산로에 대표 산 이름 하나만 나오게.
- 조치: 등산로 구간마다 레이블을 붙이면 같은 산 이름이 수십 개 겹치므로, 등산로 레이어를 좌표와 함께 읽어 산명(`산명`/`산이름` 등, `mountainNameKey`)별로 모든 꼭짓점 평균에 가장 가까운 꼭짓점을 대표 지점으로 잡고(`mountainPoints`), 보이지 않는 점 레이어('3D 산 이름', 숲 위 35m)에 3D 텍스트(15px 굵게, 흰 테두리, 겹치면 자동 숨김)로 산 이름을 하나씩 띄웁니다(`addMountainLabels`). 산 이름 필드가 없으면 조용히 생략.
- 브랜치: `work/kangmina-3d-mountain-labels` (base `design/service-home-refresh` ba64814).
- 검증: 인라인 스크립트 `node --check`, 단위 검사(산 이름 필드 판별, 산별 대표 지점·구간 수, 레이어 생성·생략), `npm run build:deploy`, `git diff --check` 통과. 대표 지점 위치가 어색한 산이 있으면 배포 후 확인 필요.

## 2026-09-17 3D 지도 구리시청 레이블 (담당: 강민아)

- 요청: 구리시청 레이블 하나.
- 조치: 산 이름에 쓰던 '글자만 보이는 점 레이어'를 공용 `textPointLayer`로 빼고, 주요 시설 목록 `LANDMARKS`(현재 구리시청)를 건물 레이어(LOD1)에서 이름(`bldg_nm`/`dtl_bldg_nm` LIKE '%구리시청%')으로 찾아 그 건물 중심 위(지붕 위 14m, `relative-to-scene`)에 14px 짙은 남색 3D 텍스트로 띄웁니다(`addLandmarkLabels`). 건물 조회가 안 되면 알려진 좌표(127.1294, 37.5942)에 놓습니다. 다른 시설을 더 넣으려면 `LANDMARKS`에 이름·좌표·검색식 한 줄을 추가.
- 브랜치: `work/kangmina-3d-cityhall-label` (base `design/service-home-refresh` 01f676a).
- 검증: 인라인 스크립트 `node --check`, 단위 검사(도형 중심 계산, 건물에서 찾은 경우·조회 실패·건물 레이어 없음의 좌표), `npm run build:deploy`, `git diff --check` 통과. 건물 검색이 실제 서버에서 되는지는 배포 후 콘솔의 '(건물에서 찾음)/(기본 좌표)' 로그로 확인.

## 2026-09-17 3D 지도 명소·축제 심볼이 건물에 가려지지 않게 (담당: 강민아)

- 증상: 건물 사이에 있는 명소(예: 구리전통시장 곱창골목)의 심볼이 시점에 따라 옆 건물에 가려 보였다 안 보였다 함. 심볼이 지면(또는 지붕) 6m 위에 놓여 있어 더 높은 이웃 건물이 시선을 막았습니다.
- 조치: 명소·축제 심볼을 2D 그림 마커 대신 `point-3d`(같은 그림자 PNG, `IconSymbol3DLayer`)로 바꾸고 `verticalOffset`(화면 44px, 세계 좌표 최소 28m·최대 260m)로 공중에 띄운 뒤 흰 지시선(`callout`)으로 실제 자리를 가리키게 했습니다(`placeSym`). 빽빽한 도심에서 점 심볼이 가려지지 않게 하는 ArcGIS 권장 방식입니다. 이름이 목록에 없는 곳의 초록 핀도 같은 방식(아래 기준점).
- 예전 방식으로 비교하려면 주소 뒤에 `?nocallout`(`USE_CALLOUT=false` → 2D 그림 마커, 6m 오프셋).
- 브랜치: `work/kangmina-3d-callout` (base `design/service-home-refresh` 1568843).
- 검증: 인라인 스크립트 `node --check`, 단위 검사(심볼 구조·지시선·기본 핀 기준점·레이어 오프셋), `npm run build:deploy`, `git diff --check` 통과. 띄우는 높이(44px)와 지시선 굵기는 배포 후 눈으로 확인 필요.
