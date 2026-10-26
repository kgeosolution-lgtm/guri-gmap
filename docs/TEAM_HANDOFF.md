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

## 2026-09-17 3D 지도 구리시 밖 회색 처리·시 밖 건물 (담당: 강민아)

- 요청: 웹씬에 넣은 '구리외건물'(ArcGIS Online Esri 3D 건물, 시 안쪽은 필터로 제외, 팝업·범례 없음)과 'Korea_Boundary SE'(시 밖 회색 처리)를 3D 지도에도.
- 조치(포털 웹씬 JSON 을 사이트에서 읽을 수 없어 페이지가 직접 만든다, `addOutsideMask`):
  - 시 경계: 행정동 경계 서비스(`SCENE.dongUrl`)를 뷰 좌표계로 읽어 합치고 항공사진 페이지와 같은 `cleanOutline` 규칙으로 바깥 고리만 남깁니다.
  - 회색 덮개: 시 크기의 25배 사각형(시계 방향)에 시 경계를 구멍(반시계 방향)으로 뚫은 폴리곤(`maskRings`)을 지면에 입혀 맨 아래 레이어로 추가(색 `SCENE.maskColor`, 흰 테두리). 웹씬의 'Korea_Boundary SE' 벡터 타일은 겹치지 않게 숨깁니다.
  - 시 밖 건물: `SCENE.outsideBuildingsUrl`(Esri3D_Buildings_v1 SceneServer)을 SceneLayer 로 얹고 `filter`(시 경계와 disjoint)로 시 안쪽은 제외, 회색 mesh 렌더러, `popupEnabled/legendEnabled=false`, 목록 숨김. 클릭 대상에도 넣지 않았습니다. 주소가 틀리면 콘솔에 '로딩 실패' 경고만 남기고 레이어를 뺍니다.
- 브랜치: `work/kangmina-3d-outside` (base `design/service-home-refresh` 6dd8d5d).
- 검증: 인라인 스크립트 `node --check`, 단위 검사(고리 방향, 덮개 고리 구성, 경계 정리, 레이어 추가·필터·팝업/범례 끔·웹씬 타일 숨김, 경계 실패 시 생략), `npm run build:deploy`, `git diff --check` 통과. Esri 3D 건물 서비스 주소는 샌드박스에서 확인 불가 — 배포 후 콘솔 확인 필요(틀리면 웹씬 '구리외건물' 레이어의 URL 로 `SCENE.outsideBuildingsUrl` 교체).

## 2026-09-17 3D 지도 시 밖 회색을 Korea_Boundary SE 벡터 타일로·시 밖 건물 주소 확정 (담당: 강민아)

- 시 밖 건물 주소를 담당자가 알려 준 `https://basemaps3d.arcgis.com/arcgis/rest/services/Esri3D_Buildings_v1/SceneServer/layers/0`으로 확정(`SCENE.outsideBuildingsUrl`).
- 시 밖 회색 처리는 담당자 요청대로 웹씬의 'Korea_Boundary SE' 벡터 타일(`https://www.guri.go.kr/gmapsvr/rest/services/Hosted/Korea_Boundary/VectorTileServer`)을 씁니다(`SCENE.maskMode:'tile'`, `addBoundaryTile`): 스냅샷에 있으면 켜고(앞선 변경에서 숨겼던 것을 되돌림), 없으면 그 주소로 맨 아래에 추가. 행정동 경계로 만든 회색 폴리곤 덮개는 `maskMode:'polygon'`으로 남겨 두어, 벡터 타일이 3D 에서 회색으로 안 보이면 값 하나로 바꿀 수 있습니다. 시 경계(행정동 합집합)는 시 밖 건물 필터에만 쓰고, 경계 로드에 실패하면 타일만 켜고 건물은 생략.
- 브랜치: `work/kangmina-3d-outside-tile` (base `design/service-home-refresh` 98ea20d).
- 검증: 인라인 스크립트 `node --check`, 단위 검사(타일 켬/추가, 건물 주소·필터·팝업/범례 끔, 경계 실패 시 생략, polygon 대안), `npm run build:deploy`, `git diff --check` 통과. 벡터 타일이 3D 뷰에서 실제로 회색으로 그려지는지는 배포 후 확인 필요.

## 2026-09-17 3D 지도 시 밖 회색·시 밖 건물이 안 보이던 문제 (담당: 강민아)

- 증상: 배포 후에도 구리시 밖 회색 처리와 시 밖 건물이 보이지 않음.
- 원인 추정과 조치:
  - 시 경계 조회가 `outFields:['OBJECTID']`로 고정돼 있어 호스트 서비스의 OID 필드명이 다르면(`objectid`) 조회가 실패하고, 그러면 덮개·건물이 모두 생략됐습니다. 레이어를 `load()`한 뒤 실제 `objectIdField`로 조회하도록 고침.
  - 'Korea_Boundary SE' 벡터 타일은 3D 뷰에서 그려지지 않는 것으로 보여(웹씬 뷰어 목록에서도 흐리게 표시됨 — 국내 좌표계 타일은 SceneView 가 지원하지 않음) 기본을 `maskMode:'polygon'`(행정동 경계 기반 회색 덮개)으로 바꿨습니다. 타일 방식은 `'tile'`로 남겨 둠.
  - 시 밖 건물 SceneLayer 는 `load()`를 먼저 기다려 주소·권한 오류를 잡고, 경계·덮개·건물 실패 시 화면 토스트로 원인(오류 메시지 앞 90자)을 보여 줍니다. Esri 3D 건물 서비스가 API 키를 요구하면 토스트에 403 계열 메시지가 뜰 것이며, 그때는 `esriConfig.apiKey` 설정이 필요합니다.
- 브랜치: `work/kangmina-3d-outside-fix` (base `design/service-home-refresh` 55bc9da).
- 검증: 인라인 스크립트 `node --check`, 단위 검사(OID 필드명 사용, 기본 polygon 모드 덮개·건물, 건물 로드 실패 토스트, 경계 실패 토스트·생략, tile 대안), `npm run build:deploy`, `git diff --check` 통과.

## 2026-09-17 3D 지도 명소·축제 지시선 제거·레이블 간격 (담당: 강민아)

- 의견: 심볼을 띄우는 흰 지시선이 눈에 거슬림. 축제·명소 심볼과 레이블 사이가 먼 것도 있음.
- 원인: 레이블은 원래 지점(지면) 기준으로 놓이고 심볼만 44px 띄워져 있어, 보는 각도에 따라 레이블이 심볼 위·아래로 멀리 떨어졌습니다.
- 조치: 지시선은 투명(`callout` 색 0)으로 두고 띄우기만 유지하되 높이를 44→30px(최소 16m)로 낮췄습니다. 레이블(`LabelSymbol3D`)에도 같은 `verticalOffset`을 줘 심볼 바로 위에 붙게 했습니다(`label3d`의 `lift`). 실제 자리는 지면(건물 위) 7px 색 점(명소 주황·축제 분홍, 흰 테두리)으로 표시하는 별도 레이어(`placeDotLayer`, 목록·범례 숨김)를 얹었고, 점을 눌러도 같은 카드가 뜹니다.
- 브랜치: `work/kangmina-3d-callout-tune` (base `design/service-home-refresh` 9f336f0).
- 검증: 인라인 스크립트 `node --check`, 단위 검사(투명 지시선·30px, 레이블 동일 오프셋, 땅 점 레이어 색·크기·팝업 끔), `npm run build:deploy`, `git diff --check` 통과. 띄우는 높이·점 크기는 배포 후 눈으로 확인 필요.

## 2026-09-17 3D 지도 명소·축제 심볼을 지면·건물 위로 되돌림, 땅 점 제거 (담당: 강민아)

- 의견: 심볼이 있는데 점을 또 찍는 것은 이상함. 심볼은 지면이나 건물 위에, 레이블은 심볼 가까이.
- 조치: 지시선·띄우기·땅 점(`placeDotLayer`)을 모두 걷어내고, 명소·축제 심볼을 원래의 2D 그림 마커로 지면·건물 지붕 바로 위(`relative-to-scene` 3m)에 놓습니다. 레이블은 띄우지 않고 심볼 바로 위(`above-center`). 지시선 방식은 주소 뒤 `?callout`으로만 비교 가능(`USE_CALLOUT` 기본 false).
- 알려진 한계: 건물 사이의 명소(예: 곱창골목)는 시점에 따라 옆 건물에 가려질 수 있습니다(담당자 판단으로 지면 배치를 우선).
- 브랜치: `work/kangmina-3d-symbols-ground` (base `design/service-home-refresh` c574f22).
- 검증: 인라인 스크립트 `node --check`, 단위 검사(2D 그림 마커, 3m 오프셋, 땅 점 없음, 레이블 미부양), `npm run build:deploy`, `git diff --check` 통과.

## 2026-09-17 오픈 전 검토용 "수정 요청" 위젯 (담당: 강민아)

- 요청: 담당자가 준 설치 지시서대로 헤더 "테마 찾기" 옆에 "수정 요청" 메뉴를 붙이고, 화면·종류·내용·중요도·드래그 캡처를 서버에 모아 여러 명이 상태(수정전/수정완료)를 함께 보게.
- 프론트(이 저장소, 지시서 (1)):
  - `public/review/review.js` — 지시서의 내용 그대로(접두사 `gr-`로 페이지 CSS와 분리, 자기 UI를 스스로 붙임). `.service-nav`와 모바일 `header nav` 양쪽에 "수정 요청" 링크가 붙고, 없으면 떠 있는 버튼. API 는 `/api/guri-review`(같은 kgeodata 서버), 관리자는 주소 뒤 `?review=guri`.
  - 네 지도 페이지(`theme/animal/aerial/scene.html`) `</body>` 앞에 `<script src="/review/review.js" defer>` 한 줄, 홈은 `src/app/layout.tsx`에 `next/script`(basePath 붙임).
  - `scripts/build-deploy.mjs`: 배포 치환 목록에 `review/` 추가(→ `/app/guri/review/review.js`), 필수 출력에 `review/review.js` 추가. 지도 조회·필터·렌더 로직은 건드리지 않음.
  - 오픈할 때: 페이지 5곳의 그 한 줄만 지우면 사라짐(파일·백엔드는 남겨도 화면엔 안 보임).
- 백엔드(지시서 (2), `kgeo_api175` 저장소): 이 세션에서 접근 가능한 저장소가 아니라 **아직 미적용**. 테이블 `guri_review` 생성, `routes/guriReview.js`, `app.js`의 `app.use('/api/guri-review', …)`, 환경변수 `GURI_REVIEW_KEY`(기본 guri)를 지시서대로 넣어야 목록 조회·저장이 동작합니다. 그 전까지 위젯의 목록 탭은 "서버 연결(API)을 확인해 주세요"로 표시됩니다.
- 브랜치: `work/kangmina-review-widget` (base `design/service-home-refresh` 6f3a1f7).
- 검증: `node --check review.js`, 헤드리스 크롬으로 헤더 스텁에 붙여 링크 2개 생성·클릭 시 창 열림 확인, `npm run build:deploy` 후 `out/review/review.js` 존재와 홈·지도 페이지의 경로가 `/app/guri/review/review.js`로 치환됨 확인, prettier·`git diff --check` 통과. 실제 캡처(https 전용)·서버 연동은 백엔드 적용 후 확인 필요.

## 2026-09-17 "수정 요청" 저장소를 구글 시트 + Apps Script 로 (담당: 강민아)

- 배경: 지시서의 백엔드(kgeo_api175, Express+PostgreSQL)는 이 세션에서 접근할 수 없고 guri-gmap 은 정적 사이트라 서버 코드를 실행할 수 없음. 담당자 결정으로 서버 없이 구글 시트 한 장에 저장하는 방식으로 변경.
- 백엔드 대체: `docs/review/Code.gs`(Apps Script) — `GET ?action=list`(목록, status 를 todo/done 으로 정규화, 시트에서 '수정완료'라고 적어도 done), `GET ?action=shot&id=`(드라이브의 캡처를 data URL 로 반환 → 파일 공유 설정 불필요), `POST {action:add|status|delete}`(본문 JSON 문자열, 관리자 암호 `ADMIN_KEY`=guri, 삭제는 본인 토큰 또는 관리자). 시트 `수정요청` 탭과 드라이브 폴더 `구리 생활지도 수정요청 캡처`는 스크립트가 만든다. 설치 순서는 `docs/review/README.md`.
- 프론트: `public/review/review.js` 의 API 층만 교체 — `API` 상수(웹 앱 URL, 아직 `PASTE_APPS_SCRIPT_WEB_APP_URL` 자리표시), GET/POST 를 Apps Script 규약으로(POST 에 Content-Type 헤더를 붙이지 않아 사전 요청 회피), 캡처는 `shot_id` 로 목록에 싣고 화면에서 늦게 불러와 캐시(`loadShots`), 요청에 `page_url` 추가. UI·캡처·크롭 로직은 그대로.
- 남은 일: 담당자가 시트를 만들고 Code.gs 를 웹 앱으로 배포한 뒤 **웹 앱 URL 을 `review.js` 의 `API` 에 넣어 커밋**해야 동작. 그 전에는 목록 탭에 "API 주소가 아직 설정되지 않았어요" 표시.
- 브랜치: `work/kangmina-review-sheets` (base `design/service-home-refresh` 2fadac3).
- 검증: Code.gs 는 Apps Script 전역(SpreadsheetApp/DriveApp/Utilities/ContentService/LockService)을 흉내 낸 Node 하네스로 목록·추가(캡처 저장)·빈 내용 거부·상태(관리자만)·시트 직접 편집 인식·삭제(본인/관리자, 캡처 휴지통)·잘못된 요청을 검사. review.js 는 헤드리스 크롬에서 fetch 를 흉내 내어 목록 2건 렌더·캡처 늦은 로드·관리자 완료 버튼 POST(status, key)·보내기 POST(add, page_url) 확인. `node --check`, `npm run build:deploy`, prettier, `git diff --check` 통과. 실제 Apps Script 배포 후의 CORS·리다이렉트 동작은 배포해 봐야 확인 가능.

## 2026-09-17 "수정 요청" 웹 앱 URL 연결·헤더 중복 방지 (담당: 강민아)

- 담당자가 회사 공유 드라이브 구리시 폴더에 시트를 만들고 Code.gs 를 웹 앱으로 배포(액세스: 모든 사용자). 그 URL 을 `public/review/review.js` 의 `API` 에 넣어 위젯이 실제 저장소와 연결됨.
- 첫 목록 응답에 헤더 이름이 값으로 들어간 행(`id:"id"`)이 보여, 첫 요청 두 개가 동시에 와 헤더를 두 번 넣은 것으로 판단. `Code.gs` 를 고침: 헤더 유무를 1행 1열 값(`id`)으로 판단하고 잠금 안에서만 넣으며(이미 데이터가 있으면 1행에 삽입), 목록에서 `id` 값이 `id` 인 행은 건너뜀. **담당자가 시트의 중복 헤더 행을 지우고, Apps Script 를 새 버전으로 재배포해야 반영**(배포 → 배포 관리 → 연필 → 새 버전 → 배포, URL 유지).
- 브랜치: `work/kangmina-review-url` (base `design/service-home-refresh` 4a22e4c).
- 검증: Apps Script 하네스에 헤더 중복 행 제외·헤더 없는 시트에 1행 삽입 검사 추가 통과, review.js 헤드리스 크롬 검사 통과, `npm run build:deploy`, prettier, `git diff --check` 통과.

## 2026-09-17 "수정 요청" 창이 갑자기 닫히는 문제·지도 위에서 바로 드래그 캡처 (담당: 강민아)

- 증상 1: 글을 쓰다가 창이 갑자기 사라짐. 원인은 글을 드래그해 고르다 창 밖에서 마우스를 떼면 브라우저가 그것을 바깥 클릭으로 보고 닫던 것. 밖에서 누르고 밖에서 뗐을 때만 닫도록 고쳤고, 쓰던 글(내용·위치)은 `sessionStorage`에 남겨 실수로 닫히거나 새로고침돼도 복구됩니다(보내면 지움).
- 증상 2: 캡처가 브라우저 화면 고르기부터 시작해 원하는 부분만 담기 번거로움. 흐름을 바꿈 — 📷 을 누르면 창이 잠깐 닫히고 지도 위에 반투명 오버레이가 떠서 원하는 부분을 드래그(그냥 클릭하면 전체, Esc 취소) → `getDisplayMedia`에 `preferCurrentTab`·`selfBrowserSurface:'include'`·`surfaceSwitching/monitorTypeSurfaces:'exclude'`를 줘 브라우저 고르기 창에 현재 탭이 바로 잡히게(사용자는 "공유"만 누름) → 잡힌 화면에서 드래그한 부분만 잘라(뷰포트 대비 비율로 좌표 변환) 담고 창을 다시 엽니다. 잡힌 화면 비율이 이 탭과 다르면(다른 창을 골랐을 때) 전체를 담고 예전 크롭 화면으로 넘겨 직접 자르게 합니다. Ctrl+V 붙여넣기 흐름은 그대로.
- 브라우저 제약: 브라우저 정책상 화면 고르기 창 자체는 없앨 수 없어 "공유" 클릭 한 번은 남습니다(크롬은 현재 탭이 미리 선택됨).
- 브랜치: `work/kangmina-review-capture` (base `design/service-home-refresh` d545104).
- 검증: 헤드리스 크롬에서 `getDisplayMedia`를 캔버스 스트림으로 흉내 내어 드래그 100×60px → 2배 화면에서 200×120px 이미지가 담기고 창이 다시 열리는 것, 안에서 누르고 밖에서 떼면 안 닫히고 밖에서 누르고 떼면 닫히는 것, 초안 저장을 확인. `node --check`, `npm run build:deploy`, prettier, `git diff --check` 통과. 실제 크롬의 화면 고르기 동작은 배포 후 확인 필요.

## 2026-09-17 푸터 구리시 로고의 흰 박스 제거 (담당: 강민아)

- 증상: 홈 푸터의 구리시 CI(`public/images/guri-ci.png`)가 회색 푸터 위에 흰 상자처럼 보임. CSS 문제가 아니라 PNG 자체가 알파 없는 RGB(흰 배경이 그림에 박힘, 인터레이스)였습니다.
- 조치: 헤드리스 크롬 캔버스로 흰 바탕 위 합성을 되돌려(알파 = 255 − min(R,G,B), 색은 언블렌딩) 투명 배경 RGBA PNG(137×56, 5.8KB)로 교체. 같은 파일을 쓰는 푸터 하단 작은 로고와 홈 `page.tsx`의 로고도 함께 투명해집니다. 회색·짙은 배경 위 합성 미리보기로 가장자리 확인.
- 브랜치: `work/kangmina-footer-logo` (base `design/service-home-refresh` 215c909).
- 검증: PNG 헤더(colortype 6, 비인터레이스) 확인, 순수 파이썬 합성 미리보기, `npm run build:deploy`, `git diff --check` 통과.

## 2026-09-17 "수정 요청" 캡처 보기를 사진 앱처럼 (담당: 강민아)

- 의견: 목록의 캡처를 누르면 작은 흰 상자 안에 어정쩡하게 떠서, 캡처 이미지만 크게 보고 싶음.
- 조치: 캡처 보기(`.gr-lb`)를 화면 전체를 어둡게 덮는 사진 뷰어로 바꿈 — 위쪽 막대에 화면·위치·시간, 내려받기(`guri-review-<id>.jpg`), "실제 크기/화면에 맞춤", 닫기. 사진은 화면에 맞춰 크게(최대 100vw−32px × 100vh−76px), 사진을 누르면 실제 크기로 토글, 배경 클릭·닫기·Esc 로 닫힘. 페이지 CSS 가 `img` 를 건드려도 흐트러지지 않게 크기·배경·테두리는 `!important`.
- 브랜치: `work/kangmina-review-lightbox` (base `design/service-home-refresh` 71204c2).
- 검증: 헤드리스 크롬에서 썸네일 클릭 → 뷰어 열림·제목·내려받기 이름, 사진 클릭 → 실제 크기, Esc → 닫힘 확인. `node --check`, `npm run build:deploy`, prettier, `git diff --check` 통과.

## 2026-09-17 "수정 요청" 목록 오류 수정·허용 창 없는 캡처 (담당: 강민아)

- 오류: 목록 탭에 `TypeError: (s || "").replace is not a function`. 시트 셀에 숫자만 적힌 값(예: 위치 "4567")이 숫자로 와서 `esc()`가 문자열 메서드를 못 찾던 것. `esc`가 어떤 값이든 문자열로 바꾼 뒤 처리하도록 고쳤고, `Code.gs`의 목록도 모든 칸을 문자열로 보내게(`S_`) 했습니다(재배포 필요).
- 캡처 허용 창: 브라우저의 "이 탭을 보도록 허용" 창은 웹 페이지가 없앨 수 없는 보안 절차라, 그 절차를 거치지 않는 방식을 먼저 씁니다 — 드래그 뒤 페이지를 직접 그림(`captureLocal`): 지도(WebGL)는 ArcGIS `view.takeScreenshot()`으로, 헤더·카드·버튼 등 나머지는 html2canvas(cdnjs, 처음 캡처 때 한 번 로드)로 그려 지도 스크린샷 위에 겹칩니다(캔버스 요소는 제외, 지도 자리와 조상 배경은 복제본에서 투명 처리, 위젯 자신은 제외). 네 지도 페이지의 전역 `view`를 그대로 씁니다. html2canvas 로드나 그리기에 실패하면 예전 브라우저 화면 캡처(허용 창)로 자동 전환.
- 한계: html2canvas 는 CSS 를 흉내 내어 그리므로 그림자·일부 폰트·고정 요소가 실제와 조금 다를 수 있습니다. 지도 위 팝업 카드·버튼은 포함되지만 ArcGIS 팝업처럼 캔버스에 그려지는 것은 지도 스크린샷 쪽에 들어갑니다.
- 브랜치: `work/kangmina-review-capture2` (base `design/service-home-refresh` 9317ba2).
- 검증: 헤드리스 크롬에서 숫자 값이 섞인 목록 렌더, 가짜 `view.takeScreenshot`·html2canvas 로 드래그 100×80 영역이 지도(아래)+화면(위)로 합성되고 `getDisplayMedia`는 호출되지 않음, 지도 표시 속성 정리, 창 다시 열림 확인. Apps Script 하네스에 숫자 셀 문자열화 검사 추가. `node --check`, `npm run build:deploy`, prettier, `git diff --check` 통과. 실제 페이지에서의 html2canvas 렌더 품질은 배포 후 확인 필요.

## 2026-09-17 3D 지도 모든 건물에 투명도 40%·진한 회색 얇은 외곽선 (담당: 강민아)

- 요청: 3D 지도의 모든 건물에 투명도 40%, 외곽선을 진한 회색으로 얇게.
- 조치: `SCENE.building={opacity:0.6, edgeColor:[64,68,72,.9], edgeSize:0.6}`. 구리 건물(LOD1·LOD2 SceneLayer)은 레이어가 로드된 뒤 `applyBuildingStyle`로 `mesh-3d` 심볼을 새로 입힘 — 원래 렌더러가 단순 심볼이면 그 색과 colorMixMode(텍스처 tint 등)를 살리고 불투명도만 0.6으로, 없으면 흰색. 외곽선은 `edges:{type:'solid', color, size:0.6pt}`. 시 밖 Esri 건물도 같은 `meshSym`(회색 + 같은 투명도·외곽선). 클릭 강조·팝업 카드는 그대로.
- 브랜치: `work/kangmina-3d-building-style` (base `design/service-home-refresh` 0a57b6a).
- 검증: 단위 검사(원래 색·mix 보존 + 0.6, 렌더러 없을 때 흰색, 시 밖 건물 심볼, prepBuildings 적용), `node --check`, `npm run build:deploy`, `git diff --check` 통과. 실제 투명 건물의 겹침·외곽선 굵기는 배포 후 확인 필요.

## 2026-09-17 시계열 항공사진: 지도 위에 함께 보기(브이월드 6종) + 로드뷰 (담당: 강민아)

- 요청: 항공사진만 있어 밋밋하니 고양(gomap)·남원(plan.html)처럼 로드뷰, 행정구역, 연속지적도, 용도지역, 도시지역, 국토계획구역, 공간시설을 추가. 브이월드 키 2A668728-… 사용.
- 버튼: 검색창 아래 "지도 위에 함께 보기" 카드에 알약 토글 칩(연도 버튼과 같은 결). 자료마다 색 점이 있고 켜면 그 색으로 채워짐, 여러 개 동시에 켤 수 있음. 켜진 게 있으면 아래에 '진하기' 슬라이더(30~100%)와 '모두 끄기', 마지막에 켠 자료의 한 줄 설명. 모바일은 지역 선택 아래로 내려가고 칩이 줄바꿈. 켠 자료는 주소 `ov=` 에 남아 공유 링크로 재현됨.
- 브이월드: `BaseDynamicLayer` 하위 클래스 `VWorldLayer`가 화면 범위마다 WMS GetMap(1.1.1, EPSG:3857, PNG 투명, `KEY`·`DOMAIN=kgeodata.com`) 한 장을 받는다(`vwUrl`). 항공사진 바로 위·경계선 아래에 놓이고(`overlayIndex`), 투명도는 슬라이더로. 연속지적도는 1:18,000 이하에서만(더 축소하면 안내). 설정은 `OVERLAYS` 배열(키·라벨·색·브이월드 레이어 ID·설명·minScale).
  - 레이어 ID(브이월드 2D 데이터 WMS): 행정구역 `lt_c_adsigg,lt_c_ademd` / 연속지적도 `lp_pa_cbnd_bubun` / 용도지역 `lt_c_uq111` / 도시지역 `lt_c_upisuq151` / 국토계획구역 `lt_c_uq113,lt_c_uq129`(용도구역+지구단위계획구역) / 공간시설 `lt_c_uq122`. **도시지역·국토계획구역 ID 는 문서 기억에 의존한 추정**이라 배포 후 안 보이면 남원 plan.html 의 설정값으로 `OVERLAYS[].ids` 를 맞출 것. 잘못된 ID 는 브이월드가 오류 XML 을 주어 그 자료만 비어 보임.
- 로드뷰(카카오): "로드뷰 보기" 칩을 켜면 지도 커서가 십자로 바뀌고 클릭한 곳에 주황 점 표시. `KAKAO.jsKey`(JavaScript 키, 카카오 개발자 콘솔에 kgeodata.com 등록 필요)가 있으면 지도 오른쪽 46%(모바일은 아래 절반) 패널에서 `kakao.maps.Roadview` 로 바로 보고(가장 가까운 파노라마 60m 탐색, 로드뷰 안에서 이동하면 지도 점도 따라감), 키가 없으면 `map.kakao.com/link/roadview/위도,경도` 를 새 창으로 연다(현재 상태). gomap 은 접근이 막혀 참고하지 못했고, 카카오 로드뷰 표준 방식으로 구현.
- 브랜치: `work/kangmina-aerial-overlays` (base `design/service-home-refresh` acebf7a).
- 검증: 인라인 스크립트 `node --check`, 가짜 DOM·지도 하네스로 WMS URL 구성, 칩 6개+로드뷰 칩 생성, 주소 `ov=` 복원·갱신, 지적도 확대 안내, 모두 끄기, 로드뷰 새 창 URL 검사 통과. 칩 카드 CSS 는 정적 미리보기로 확인. `npm run build:deploy`, `git diff --check` 통과. 실제 브이월드 응답(키·도메인·레이어 ID)과 카카오 로드뷰는 배포 후 확인 필요.

## 2026-09-17 시계열 항공사진: 브이월드 요청 형식 자동 탐색·원인 보기, 로드뷰 패널은 클릭 후 (담당: 강민아)

- 증상: `<img>` 방식으로 바꿔도 브이월드 6종이 안 보이고 "불러오지 못했어요 (키·도메인·레이어 ID 확인)"만 뜸. 담당자 확인: 키에 kgeodata.com·구리시·고양시 도메인이 모두 등록됨. 로드뷰는 켜자마자 빈 패널이 열리고, 클릭해도 내용이 없음.
- 브이월드 조치: 브이월드가 받아 주는 요청 표기가 문서와 다를 수 있어(WMS 1.1.1/SRS vs 1.3.0/CRS, `DOMAIN` 을 호스트/`https://호스트`/생략/설정값 중 무엇으로) 첫 그림이 실패하면 `VW_VARIANTS` 8가지를 차례로 시도하고 성공한 형식을 기억(`vwLocked`). 모두 실패하면 안내 토스트에 **"원인 보기 ↗"** 링크(첫 형식의 GetMap 주소)를 넣어 새 창에서 브이월드의 오류 XML(도메인 불일치·레이어 없음 등)을 바로 볼 수 있게 함. 사이트에서는 CORS 때문에 오류 본문을 스크립트가 읽지 못할 수 있어 링크가 가장 확실한 진단 수단.
- 로드뷰 조치(담당자 요청): "로드뷰 보기"를 켜면 SDK 만 미리 받고 패널은 열지 않음. 지도를 클릭하면 반경 150m(`RV_RADIUS`) 안의 가장 가까운 파노라마를 찾고, **찾았을 때만** 오른쪽 패널을 열어 그때 `kakao.maps.Roadview` 를 만들고 `relayout()` 후 파노라마를 놓음(숨겨진 상태에서 만들어 크기가 0이 되던 문제 방지). 없으면 "150m 안에는 로드뷰가 없어요" 안내만. SDK 로드 실패 시 새 창 폴백.
- 브랜치: `work/kangmina-aerial-overlays-fix2` (base `design/service-home-refresh` e8d4984).
- 검증: 하네스에 요청 형식 폴백(1.1.1 실패→1.3.0 성공·형식 고정, origin/생략 표기), 전부 실패 시 '원인 보기' 링크 토스트, 가짜 카카오 SDK 로 켜기만으로는 패널 안 열림·로드뷰 없는 곳은 안내·찾으면 패널 열림+relayout+setPanoId 검사 추가 통과. `node --check`, `npm run build:deploy`, prettier, `git diff --check` 통과.

## 2026-09-17 시계열 항공사진 격자 줄 제거 (담당: 강민아)

- 증상: 항공사진 위에 네모난 격자(옅은 줄)가 보여 레이어를 얹은 것처럼 보임.
- 원인: 항공사진 타일은 국토정보플랫폼의 EPSG:5179 타일을 회전·축척 변환으로 웹 메르카토르 캔버스에 이어 붙이는데, 소스 타일을 딱 맞춰 그리면 변환된 가장자리의 안티앨리어싱으로 경계 픽셀이 반투명해져 아래 바탕지도가 격자처럼 비침. 헤드리스 크롬 실험으로 확인(여유 없이 그리면 타일당 반투명 픽셀 493개, 0.5px 이상 넓히면 0개).
- 조치: `AirPhotoLayer.fetchTile` 에서 소스 타일을 사방 `BLEED=0.75px` 씩 넓혀 그림(`drawImage(img,0,0,T,T,-B,-B,T+2B,T+2B)`). 겹침은 0.75px 이라 사진 왜곡은 없음.
- 브랜치: `work/kangmina-aerial-seams` (base `design/service-home-refresh` d3ac9e1).
- 검증: 인접 타일 4장 변환 합성 실험(여유 0 → 493, 0.5/0.75/1 → 0), `node --check`, 겹쳐 보기 하네스, `npm run build:deploy`, `git diff --check` 통과.

## 2026-09-17 시계열 항공사진: 로드뷰 칩 흰색 기본/짙은 켜짐, 패널 아이콘, 시 경계 자르기를 CSS polygon 으로 (담당: 강민아)

- 로드뷰 칩: 기본은 다른 칩처럼 흰 바탕 + 카카오 아이콘 + "로드뷰", 켜면 짙은 배경·흰 글씨(담당자 시안). 패널 머리의 사람 모양 이모지도 카카오 아이콘으로.
- 레이어가 다시 안 보인 원인 판단: #52 에서 넣은 시 경계 자르기(SVG `clipPath` 참조)가 브라우저·레이아웃에 따라 이미지 층을 통째로 가릴 수 있어(요청은 성공해도 화면에 안 보임), 자르기를 화면 좌표 CSS `clip-path: polygon(...)` 으로 바꿈: 시 경계의 가장 큰 고리를 Douglas–Peucker(1.5m)로 간추려 두고(`simplifyRing`), 화면이 움직일 때마다 화면 픽셀 좌표로 polygon 문자열을 다시 씀(`updateCityClip`). 주소 뒤 `?noclip` 이면 자르지 않음(진단용).
- 브랜치: `work/kangmina-aerial-overlays-4` (base `design/service-home-refresh` f438f14).
- 검증: 하네스에 간추리기(직선 점 제거·꺾임 유지), 큰 고리 선택, polygon 좌표 변환, 칩 문구 검사 통과. `node --check`, `npm run build:deploy`, prettier, `git diff --check` 통과. 실제로 레이어가 보이는지는 배포 후 확인(안 보이면 `?noclip` 으로 자르기 여부를 갈라 볼 것).

## 2026-09-17 시계열 항공사진: 행정구역 벡터 스타일·통리반, 지적도 선만+지번 크게, 범례, 로드뷰 재선택, 공공문화체육시설 삭제 (담당: 강민아)

- 로드뷰: 패널이 열린 뒤 다른 곳을 찍으면 바로 그곳으로 옮김(첫 열림에만 `relayout` 지연, 이후는 즉시 `setPanoId`). 로드뷰 객체는 하나만 만든다.
- 행정구역: 브이월드 WMS 대신 구리시 행정동경계 서비스를 우리 스타일로 그림(`kind:'adm'`, `admLayerDefs`) — 흰 테두리 5px 아래 파란 선 2px, 아주 옅은 파란 채움, 동 이름 13pt 굵게·흰 halo(`always-horizontal`, 겹치면 숨김). 통리반은 `CITY.tongUrl`(구리시 서비스 층 URL)·`tongNameField` 를 넣으면 1:12,000 이하에서 점선 1.2px + 11pt 레이블로 보임. **현재 통리반 서비스 URL 이 없어 비어 있음 — 담당자에게 요청.** 구리시 자료라 시 경계 자르기 불필요.
- 연속지적도: 브이월드 WFS(`lp_pa_cbnd_bubun`, EPSG:3857, 최대 3,000필지)로 필지를 받아 GeoJSONLayer 로 그림(`refreshCadastre`/`cadastreLayer`) — 채움 없이 보라 선 1.1px, 지번(`jibun`) 11pt 굵게(브이월드 기본보다 한 포인트 큼). 좌표는 경위도로 변환(`geojsonToWgs84`). 1:8,000 이하에서만. WFS 가 CORS 등으로 막히면 예전 WMS 그림으로 자동 대체하고 안내(`wfsFailed`).
- 범례: 용도지역·문화재보호(`legend:true`)를 켜면 카드 아래에 브이월드 `GetLegendGraphic` 이미지가 붙음(`renderLegends`). 브이월드가 범례 그림을 안 주면 "제공하지 않아요" 문구.
- 공공문화체육시설 삭제. 레이어 목록: 행정구역·연속지적도·용도지역·도시지역·문화재보호.
- 브랜치: `work/kangmina-aerial-overlays-5` (base `design/service-home-refresh` 5c484ab).
- 검증: 하네스에 레이어 목록, 행정동 2겹 레이어·레이블 13pt·표시/숨김, 지적도 WFS→GeoJSON(채움 0·지번 11pt·blob URL·지도 추가)와 WFS 실패→WMS 대체, 범례 이미지(용도지역만), 로드뷰 두 번째 클릭 즉시 이동·객체 1개 검사 추가 통과. `node --check`, `npm run build:deploy`, prettier, `git diff --check` 통과. 브이월드 WFS 의 CORS 허용 여부·범례 제공 여부는 배포 후 확인.

## 2026-09-17 시계열 항공사진: 연속지적도를 kgeodata 서비스로(구리시만), 용도지역·문화재보호 범례를 우리 색 표로 (담당: 강민아)

- 연속지적도(담당자 요청): 브이월드 대신 kgeodata ArcGIS 서비스 `Hosted/연속지적도형정보_20260208/FeatureServer/0`(`CITY.cadastreUrl`) 을 FeatureLayer 로 그림(`kind:'cad'`, `cadastreDef`/`refreshCadastre`). 같은 사이트라 CORS 문제 없음. **구리시 필지만**: `definitionExpression` 으로 PNU 앞 5자리 `41310`(`CITY.sggCode`) 만 남김. 필드명(`pnu`·`jibun`)은 서비스 `load()` 뒤 `fields` 에서 자동으로 찾음(`pickField`). 채움 없이 보라 선 1.1px, 지번 11pt 굵게·흰 halo, 1:8,000 이하(`minScale`). 레이어는 한 번만 만들고 켜고 끌 때 `visible` 만 바꿈.
- 용도지역·문화재보호(`kind:'vec'`): 브이월드 WFS(`lt_c_uq111`, `lt_c_uo301`)로 받아 GeoJSONLayer 로 **우리가 정한 색**으로 칠함. 색 표는 `CLASS_TABLES` 하나에 두고 렌더러(Arcade `valueExpression`, 용도지역명에 포함된 글자로 22종 분류)와 범례(`renderLegends`, 색 견본 + 이름)가 같은 표를 쓰므로 **범례 = 실제로 칠한 색**. 용도지역: 주거(노랑→주황 6단계)·상업(빨강 4)·공업(파랑 3)·녹지(초록 3)·관리(연두 3)·농림·자연환경보전·그 밖(회색). 문화재보호구역: 갈색 `#8B5E34`.
- WFS 가 막히면(CORS 등) 예전처럼 브이월드 WMS 그림으로 자동 대체(`wfsFailed`)하고 범례 아래에 "지금은 브이월드 그림으로 보여서 지도 색이 이 표와 다를 수 있어요" 를 붙임. 브이월드 `GetLegendGraphic` 은 더 이상 안 씀.
- 남은 확인: 브이월드 WFS 의 CORS 허용 여부는 배포 후 확인. 정확한 색을 보장하려면 용도지역·문화재보호도 지적도처럼 kgeodata 서버에 올리고 `CITY` 에 URL 만 넣으면 됨(같은 `CLASS_TABLES` 로 칠하도록 확장 가능). 도시지역·문화재보호의 브이월드 레이어 ID 는 추정값(`alt` 로 재시도).
- 브랜치: `work/kangmina-aerial-overlays-7` (base `design/service-home-refresh` 07311c6).
- 검증: 하네스 개편 — 용도지역 WFS→GeoJSON(unique-value 22종, Arcade 괄호 짝, r2g=#FFC000, 범례에 같은 색·주의문 없음, 이동 시 새 조각으로 교체), 연속지적도 FeatureLayer(kgeodata URL, `pnu LIKE '41310%'`, 채움 0·선 #7A5FD0, 지번 11pt, minScale 8000, 한 번만 생성·visible 토글), 문화재보호 WFS 실패→WMS 그림+대체 ID+범례 주의문, 형식 폴백·원인 보기·로드뷰 검사 통과. `node --check`, `npm run build:deploy`, prettier, `git diff --check` 통과.

## 2026-09-17 시계열 항공사진: 용도지역·문화재 레이블, 브이월드 자료를 데이터 API·JSONP 로도 받기 (담당: 강민아)

- 요청: "범례랑 매칭이 잘 안된다. 범례는 그대로 두고, 확대하면 용도지역은 어떤 용도인지, 문화재는 누가 지정했는지 레이블을 보이게".
- 레이블(`vectorLabels`): 용도지역은 용도지역 이름 항목(`uname` 등) 그대로, 1:10,000 이하에서. 문화재는 이름(`crltsn_nm`·`uname`·`nm`…) + 지정한 곳(`ccbaAdmin`·지정기관·지정종목… 자료에 있는 항목을 `CLASS_TABLES.HER.who` 후보에서 찾음)을 두 줄로, 1:25,000 이하에서. 11pt 굵게·흰 halo. 항목은 첫 피처의 속성에서 자동으로 찾고 없으면 레이블 없음. 실제로 어떤 항목을 썼는지는 콘솔 `console.info('[용도지역] n건 (경로), 분류·레이블 항목 …')` 로 확인 가능.
- 범례 "매칭 안 됨"의 원인: 브이월드 WFS 가 CORS 로 막히면 그림(WMS)으로 대체되는데 그 그림은 브이월드 색이라 우리 범례와 다름. 그래서 벡터 자료 받는 경로를 셋으로(`fetchVector`): ① WFS fetch → ② 브이월드 2D 데이터 API(`/req/data`, fetch, EPSG:4326, 1,000건×최대 3쪽) → ③ 같은 API 를 `callback=` JSONP(`<script>`)로. ③ 은 CORS 와 무관하게 통하므로 브이월드가 JSONP 를 받아 주면 색·레이블이 모두 우리 것으로 나옴. fetch 가 CORS 로 막힌 것을 기억(`fetchBlocked`)해 다음부턴 바로 JSONP. 레이어 ID 후보(`alt`)도 차례로.
- 그래도 다 실패하면 예전처럼 그림으로 대체하고 범례에 "그림이라 색이 다를 수 있고 확대해도 레이블이 안 나와요" 표시. 벡터로 성공하면 범례에 "확대하면 …이 보여요" 안내.
- 브랜치: `work/kangmina-aerial-overlays-8` (base `design/service-home-refresh` ea000ae).
- 검증: 하네스 — 용도지역 레이블(`$feature["uname"]`, minScale 10,000), 문화재 WFS http 오류→데이터 API fetch 2쪽 이어 받기·이름+지정한 곳 레이블(NewLine)·범례 안내, CORS 차단→JSONP 경로(막힌 fetch 재시도 없음, 콜백 정리), 전부 실패→그림+대체 ID+주의문 검사 통과. `node --check`, `npm run build:deploy`, prettier, `git diff --check` 통과. 배포 후 확인: 용도지역을 켜고 콘솔에 `(jsonp:…)` 또는 `(wfs)` 가 찍히면 성공, "벡터 자료 실패" 경고면 브이월드가 JSONP 도 안 주는 것이라 kgeodata 서버에 올리는 방법으로 가야 함.

## 2026-09-17 시계열 항공사진: 용도지역·문화재를 구리시 안만, 표준 색·투명도, 레이블 작게, 문화재 둘째 줄 숫자 제거 (담당: 강민아)

- 구리시 안만(`clipToCity`): 벡터로 받은 용도지역·문화재 폴리곤을 시 경계 폴리곤(`cityPoly`, 행정동 합집합)으로 잘라 냄 — 안에 있으면 그대로, 걸치면 `geometryEngine.intersect` 로 안쪽만, 밖이면 버림. 잘린 결과의 고리는 시계 방향(바깥)·반시계(구멍)로 나눠 GeoJSON Polygon/MultiPolygon 으로 되돌림. `?noclip` 이면 자르지 않음. 콘솔에 `n건/전체 구리시 안` 으로 표시.
- 색: 담당자 요청("아까 쓰던 색")에 따라 `CLASS_TABLES.USE` 를 도시·군관리계획 도면 표준 색 계열(브이월드 용도지역 그림과 같은 계열: 주거 노랑→주황, 상업 빨강·분홍, 공업 파랑·보라, 녹지 초록, 관리 연두·황갈, 농림 진초록, 자연환경보전 청록)로 바꿈. 범례는 같은 표에서 그리므로 자동으로 맞음. **브이월드의 정확한 색 값은 이 환경에서 읽을 수 없어 표준 색으로 맞춘 것** — 특정 용도가 다르게 보이면 표의 색만 고치면 됨.
- 투명도: 레이어 투명도 대신 채움 색에 알파(`fillAlpha` = 진하기×0.6, 기본 0.45)를 줘서 레이블은 또렷하게. 진하기 슬라이더는 렌더러를 다시 만들어(`__mk`) 채움만 바꿈.
- 레이블: 9pt(`LABEL_PT`), halo 1.3. 문화재 둘째 줄(지정한 곳)은 번호·코드 항목(`WHO_SKIP`: no/cd/code/num/seq/id…)을 후보에서 빼고, 값이 숫자면 항목 자체를 안 쓰며, Arcade 에서도 숫자면 이름만 표시.
- 브랜치: `work/kangmina-aerial-overlays-9` (base `design/service-home-refresh` 9132ca8).
- 검증: 하네스 — 표준 색·채움 알파, 슬라이더로 채움만 변경, 시 경계 자르기(밖 버림·걸침 자르기·구멍 고리·경위도 되돌림·고리 방향), 레이블 9pt, 지정한 곳 후보 필터(번호 항목·숫자 값 제외) 통과. `node --check`, `npm run build:deploy`, prettier, `git diff --check` 통과.

## 2026-09-17 시계열 항공사진: 연속지적도 케이지오 실패 시 브이월드 그림으로 자동 복구, 칩 3+3 배치 (담당: 강민아)

- 증상: 담당자 화면에서 케이지오(kgeodata) 연속지적도 서비스가 안 보임(원인은 이 환경에서 kgeodata.com 에 접속할 수 없어 확인 못 함 — 권한·좌표계·PNU 항목형 등 가능).
- 조치(`refreshCadastre`): ① 서비스 `load()` 15초 시간 제한 ② PNU 항목이 **문자형일 때만** `LIKE '41310%'` 조건(숫자형이면 조건 없이) ③ 지도에 올리기 전에 `queryFeatureCount`(조건식 + 화면 범위)로 실제 질의가 되는지 확인 ④ 레이어뷰 생성 오류(`layerview-create-error`)도 감지. 어느 단계든 실패하면 `cadastreFallback` 이 케이지오 레이어를 걷어내고 `L.kgFailed` 를 세워 예전 **브이월드 지적도 그림**(`lp_pa_cbnd_bubun`, 채움 걷어내기 `stripFill`)으로 자동 대체, 토스트로 원인 한 줄 안내. 콘솔 `[연속지적도] 케이지오 서비스 실패 → …` 에 원인이 남으니 담당자에게 그 줄을 받아 보면 서비스 쪽 원인을 알 수 있음.
- 구리시만: 케이지오 레이어는 조건식 대신(또는 더해서) 레이어뷰 `filter={geometry:시 경계}` 로 화면에서 걸러 냄(`applyCadastreClip`, 경계가 늦게 오면 `setCityClip` 에서 다시 적용). 이때 벡터(용도지역·문화재)도 다시 잘라 냄.
- 칩: 로드뷰 + 5개 = 6개를 3열 격자(`.ov-chips{display:grid;grid-template-columns:repeat(3,1fr)}`)로 위 3개·아래 3개. 칩은 칸을 꽉 채우고 가운데 정렬, 모바일은 안쪽 여백을 줄임.
- 브랜치: `work/kangmina-aerial-overlays-10` (base `design/service-home-refresh` 5aeca6f).
- 검증: 하네스 — 건수 질의(조건식·화면 범위), 시 경계 필터(경계가 늦게 와도 적용), 숫자 PNU 는 조건식 없음, 접속 실패·질의 오류 → 브이월드 그림 + 토스트(실패 레이어는 지도에 없음), 칩 6개·3열 격자 검사 통과. `node --check`, `npm run build:deploy`, prettier, `git diff --check` 통과.

## 2026-09-17 시계열 항공사진: 지적도 대체 안내 토스트 제거, 케이지오 층 번호 자동 찾기 (담당: 강민아)

- 담당자 화면에 "케이지오 연속지적도를 못 불러와 브이월드 지적도로 보여요 (Layer not found)" 토스트가 떠서 요청대로 뺌 — 대체는 조용히, 원인은 콘솔에만.
- 그 문구의 원인 "Layer not found": `CITY.cadastreUrl` 의 층 번호 `/0` 이 서비스에 없음. `resolveCadastreUrl` 이 `…/FeatureServer?f=json` 목록을 읽어(같은 사이트) 요청한 번호가 없으면 폴리곤 층(없으면 첫 층)의 번호로 바꿔 씀. 콘솔에 `층 번호를 0 → n 로 바꿔 씀` 이 찍힘. 맞는 번호를 알면 `CITY.cadastreUrl` 에 직접 넣어도 됨.
- 브랜치: `work/kangmina-aerial-overlays-11` (base `design/service-home-refresh` cf3d094).
- 검증: 하네스 — 실패 시 토스트 없음, 목록에 0 이 없고 폴리곤 층 5 가 있으면 `/5` 로 성공 검사 통과. `node --check`, `npm run build:deploy`, prettier, `git diff --check` 통과.

## 2026-09-17 시계열 항공사진: 케이지오 연속지적도 레이블을 지번지목부호로, 10pt (담당: 강민아)

- 케이지오 연속지적도가 보이기 시작함(층 번호 자동 찾기 효과). 담당자 요청으로 레이블을 **지번지목부호**(예: 123-4 대) 항목으로, 글자를 11 → 10pt 로.
- 항목 찾기(`cadastreDef`): 항목 이름 또는 별칭(alias)에서 `지번지목부호`·`jibun_jimok`·`jimok` 순으로 찾고, 없으면 지번(`jibun`·별칭 `지번`), 그래도 없으면 첫 항목. 실제로 어떤 항목이 잡혔는지는 레이어 `outFields` 첫 값으로 확인.
- 브랜치: `work/kangmina-aerial-overlays-12` (base `design/service-home-refresh` b855c94).
- 검증: 하네스 — 이름 `jibun_jimok` 로 찾기, 별칭 `지번지목부호`(이름 `field_9`)로 찾기, 없으면 `jibun`, 10pt 검사 통과. `node --check`, `npm run build:deploy`, prettier, `git diff --check` 통과.

## 2026-09-17 메뉴 제목 변경: 우리동네 찾기 · 유기동물 찾기 · 3D입체지도 · 항공사진 비교 · G-MAP 소개 (담당: 강민아)

- 바뀐 이름: 테마지도 → **우리동네 찾기**, 3D 지도 → **3D입체지도**, 시계열 항공사진 → **항공사진 비교** (유기동물 찾기·G-MAP 소개는 그대로). 주소(`/maps/theme.html` 등)와 파일명은 그대로.
- 고친 곳: 홈 헤더 `SiteHeader.tsx`(PC·모바일 메뉴 모두 같은 배열), 푸터 `KrdsFooter.tsx` 바로가기, 홈 본문 버튼(`page.tsx` "3D입체지도 보기"·"항공사진 비교 보기"), 홈 카드 `MapsNow.tsx`, 히어로 띠 `HeroKrds.tsx`(보조 문구), 정적 지도 4쪽(`theme/animal/scene/aerial.html`)의 헤더 메뉴·모바일 메뉴·`service-page-name`·`<title>`·og:title, 지도 안 문구(3D 불러오는 중/오류, 항공사진 연도 막대 제목, 공유·인쇄 라벨), 수정요청 위젯 `review.js` 의 화면 이름 목록.
- 코드 주석 속 "테마지도식 카드" 같은 표현은 그대로(사용자에게 안 보임).
- 브랜치: `work/kangmina-menu-titles` (base `design/service-home-refresh` af89e1f).
- 검증: 지도 4쪽 인라인 스크립트 `node --check`, 겹쳐 보기 하네스, `tsc --noEmit`, prettier(src), `npm run build:deploy` 후 `out/index.html` 에 새 이름 각 2회(PC·모바일)·옛 이름 0회 확인, `git diff --check` 통과.

## 2026-09-17 시계열 항공사진: 겹쳐 보기 깜빡임 제거, 지적도 지번은 한 단계 더 확대해서 (담당: 강민아)

- 증상: 용도지역·도시지역·문화재보호가 화면을 옮길 때마다 깜빡이며 다시 그려짐.
- 원인: 멈출 때마다 새로 요청하고, 그림은 같은 `<img>` 의 `src` 를 갈아 끼워 잠깐 비었고, 벡터는 새 GeoJSONLayer 를 올리자마자 옛 레이어를 지워 새 레이어가 그려지기 전 빈 순간이 있었음.
- 조치:
  - 다시 받지 않기: 그림은 받아 둔 범위(`L.ext`, 화면의 1.4배)가 화면을 덮고 해상도가 같으면 그대로(`boxCovers`·`sameRes`). 벡터는 화면의 **2배** 범위(`vecBox`, `L.vext`)를 받아 두고 그 안에서는 다시 안 받음(확대해도 자료는 같으므로 그대로).
  - 그림 바꿔 끼우기: 새 `<img>` 를 만들어 `decode()` 가 끝난 뒤 옛 것과 한 번에 교체(`swap`). `L.img` 는 항상 현재 요소.
  - 벡터 바꿔 끼우기: 새 레이어의 레이어뷰가 `updating=false` 가 된 뒤 옛 레이어 제거(`removeWhenDrawn`, `reactiveUtils.whenOnce`; 못 기다리면 0.4초, 최대 4초).
- 연속지적도 레이블: 선은 1:8,000 이하(레벨 17, 1:4,514)부터, 지번은 레이블 클래스 `minScale=3000`(`CAD_LABEL_MIN`) 으로 한 단계 더 확대한 레벨 18(1:2,257)부터.
- 브랜치: `work/kangmina-aerial-smooth` (base `design/service-home-refresh` 3b38b32).
- 검증: 하네스 — 범위 안 이동은 그림·벡터 모두 다시 안 받음, 확대(해상도 변경)하면 새 `<img>` 로 교체되고 옛 것은 제거, 벡터는 추가 뒤 제거 순서, 2배 범위 계산, 지번 레이블 `minScale 3000` 검사 통과. `node --check`, `npm run build:deploy`, prettier, `git diff --check` 통과.

## 2026-10-12 구리시 수정사항: 유기동물 찾기 숨김(내년도 제작 예정), 우리동네 찾기의 육아·교육 그룹 제외 (담당: 강민아)

- 유기동물 찾기: 내년도 제작 예정 지도로 지정되어 **모든 메뉴·메인에서 숨김**. 지도 파일(`maps/animal.html`)과 코드는 그대로 두고 보이기만 끔 — 내년에 서비스하면 `src/config/site.config.ts` 의 `features.animalMap` 을 `true` 로 바꾸고, 정적 지도 4쪽 헤더의 `<!-- 유기동물 찾기(내년도 서비스 예정…): <a …> -->` 주석과 `theme.html` 유기동물 보호현황 팝업의 앱 링크 주석, `review.js` 화면 목록을 되돌리면 됨.
  - 플래그로 가린 곳: 홈 헤더 `SiteHeader.tsx`(PC·모바일), 푸터 `KrdsFooter.tsx`, 홈 본문 "새로운 가족을 기다리는…" 구역(`page.tsx`, 이어지는 3D·항공 구역 번호를 02·03 으로), 소개 문구("…생활 시설 정보를"), 홈 카드 `MapsNow.tsx`, `HeroKrds.tsx` 문구, v1 추천 지도 카드(`categories.config.ts` `recommendedMaps` 필터).
  - 주석으로 가린 곳: `theme/animal/scene/aerial.html` 헤더의 PC·모바일 메뉴 링크(각 2곳), `theme.html` 유기동물 보호현황 팝업의 "유기동물 찾기 앱에서 더 보기" 링크. `review.js` "어느 화면" 목록에서 제거.
  - 우리동네 찾기의 **반려동물 > 유기동물 보호현황** 테마는 앱이 아니라 테마라 그대로 둠(홈 반려동물 요약 "동물병원·유기동물"도 그대로).
- 육아·교육: 이벤트성 지도로 분류되어 이번 구축 대상에서 제외 → `theme.html` GROUPS `'육아·교육'` 에 `hidden:true`(시즌·여름과 같은 방식: 그룹 메뉴·검색에서 숨김, URL 직접 접근은 가능), 홈 테마 카탈로그 `theme-groups.config.ts` 도 `hidden: true`. 되돌리려면 두 곳의 `hidden` 만 지움.
- 브랜치: `work/kangmina-hide-animal-childcare` (base `design/service-home-refresh` 308caf9).
- 검증: `tsc --noEmit`, prettier(src), 지도 4쪽 인라인 스크립트·review.js `node --check`, 겹쳐 보기 하네스, `npm run build:deploy` 후 `out/index.html` 에 유기동물 찾기 링크·육아·교육 카드 0, v1 카드 0, 정적 4쪽 헤더의 `animal.html` 링크가 주석 밖에 0개(주석 안 2개), `git diff --check` 통과.

## 2026-10-12 우리동네 찾기: 경제·상권 → 우수맛집(와구리맛집·노포식당 새 레이어) (담당: 강민아)

- 그룹 이름 `'경제·상권'` → **`'우수맛집'`** (`theme.html` GROUPS 키, 홈 `links.ts` ThemeGroup·`theme-groups.config.ts`(아이콘 Utensils, 요약 "와구리맛집·노포식당")·`categories.config.ts` 우수맛집 지도 카드 링크). 그룹 아이콘은 `TOPIC_IC['우수맛집']`(포크·나이프)을 새로 넣음.
- 레이어는 새로 발행된 둘만: **와구리맛집** `Hosted/restaurant_waguri/FeatureServer`(심볼은 기존 추천맛집 `econ_waguri` 그대로), **노포식당** `Hosted/restaurant_long/FeatureServer`(새 심볼 `econ_nopo`: 테라코타 원 + 김 나는 뚝배기, `scripts/nopo-icon.py` 로 생성해 `SYM` 에 base64 로 넣음). 옛 모범음식점·시장 및 마트 테마 설정은 이 커밋 이전 이력(#65 이전 `theme.html`)에 있음.
- 팝업: 둘 다 기존 와구리 추천맛집 구성(이름 → 대표메뉴 칩 → 안내 → 지정년도 → 출처 안내). 노포식당은 "개업"(개업년도·창업년도·업력 등) 한 줄 추가. **새 서비스의 실제 항목 이름은 이 환경에서 확인하지 못해** 이름(영업소명·업소명·상호·상호명·업체명·사업장명·식당명·가게명·명칭·name)·대표메뉴(대표메뉴·주메뉴·메뉴·주요메뉴)·지정년도(지정년도·지정연도·선정년도·선정연도) 후보로 자동 매칭함 — 화면에서 이름이나 메뉴가 비면 서비스 항목 이름을 받아 후보에 추가할 것.
- 옛 주소 호환: `?group=경제·상권` → 우수맛집, `?cat=와구리 추천맛집`(또는 추천맛집) → 와구리맛집 (`GROUP_ALIAS`/`CAT_ALIAS`).
- 브랜치: `work/kangmina-restaurants` (base `design/service-home-refresh` aefea3f).
- 검증: theme.html 인라인 스크립트 `node --check`, 설정 검사(우수맛집 그룹의 테마가 와구리맛집·노포식당 둘뿐, 두 서비스 URL·심볼·아이콘·별칭 존재), `tsc --noEmit`, prettier, `npm run build:deploy` 후 홈에 우수맛집 카드·옛 이름 0회, `git diff --check` 통과.

## 2026-10-12 우리동네 찾기: 안전·재난 → 치안안심(safety_all 한 레이어를 시설 종류별 칩으로) (담당: 강민아)

- 그룹 이름 `'안전·재난'` → **`'치안안심'`** (`theme.html` GROUPS, 홈 `links.ts`·`theme-groups.config.ts`(요약 "CCTV·AED·안심귀갓길")·`categories.config.ts` 3곳). 그룹 아이콘은 방패(`TOPIC_IC['치안안심']`). 옛 주소 `?group=안전·재난` 은 `GROUP_ALIAS` 로 이어짐.
- 자료는 새 레이어 **`Hosted/safety_all/FeatureServer` 하나**. 시설 종류가 12가지라 종류마다 칩(테마)이 나와야 하는데 **구리시 포털은 외부에서 토큰 없이 읽을 수 없어(499 Token Required, GitHub Actions 에서 확인) 항목 이름·값을 미리 알 수 없음** → 화면에서 자료를 받은 뒤 자동으로 만든다(`buildDynThemes`, `loadGroupData` 첫 줄에서 호출):
  1. 종류 항목 찾기: `GROUPS.치안안심.dyn.field` 후보(시설종류·시설물종류·시설구분·구분·종류·유형·분류·type…)를 이름/부분일치로, 없으면 "값이 2~30가지(행 수 절반 이하)인 글자 항목 중 가짓수가 가장 적은 것".
  2. 값마다 테마 생성(`safetyThemeFor`): `src:{url,catField,catValue}` 로 같은 자료를 종류별로 걸러 씀(`rowsFor` 의 catField 기능). 종류 이름에 든 글자로 **옛 안전·재난 테마 설정(`SAFETY_PRESETS`: 팝업·심볼·안내·AED 상태·보호구역 폴리곤)을 재사용**(AED·귀갓길·CCTV·대피·쉼터·지킴이·보호구역·소방/소화). 새 종류는 `SAFETY_RULES` 의 새 심볼+팝업: 비상벨(`safety_bell`)·택배함(`safety_parcel`)·경찰/지구대/파출소(`safety_police`)·보안등/가로등(`safety_lamp`)·순찰/안심구역(`safety_patrol`)·반사경(`safety_mirror`), 그 밖은 `safety_default`(방패)에 색 6가지 순환. 새 심볼은 `scripts/safety-icons.py` 로 생성해 `SYM` 에 넣음.
  3. 칩 순서는 `SAFETY_ORDER`(쉼터·대피·AED·귀갓길·CCTV·보호구역·지킴이·소방·비상벨·택배·경찰·보안등) 뒤에 나머지는 건수순. 종류 항목은 팝업에서 숨김(칩 이름이 대신).
  4. 콘솔에 `[치안안심] 시설 종류 항목 "…" → n가지: …` 가 찍힘 — **배포 후 담당자에게 이 줄을 받아 12가지가 맞는지, 심볼·팝업이 종류에 맞게 붙었는지 확인**. 맞지 않는 종류는 `SAFETY_RULES` 의 정규식만 고치면 됨.
- 서비스 항목 확인용 수동 워크플로 `.github/workflows/inspect-service.yml` 추가(현재는 포털이 토큰을 요구해 쓸모가 없지만, 공개 서비스에는 됨. 기본 브랜치에 없으면 dispatch 가 404 라 쓸 때 push 트리거를 잠시 붙임).
- 브랜치: `work/kangmina-safety` (base `design/service-home-refresh` db5046d).
- 검증: 하네스 `safety-test.js` — 10행 가짜 자료로 종류 9가지 생성, 우선순위 정렬, 종류→옛 설정/새 심볼 매칭(AED 팝업 재사용 등), 종류별 행 걸러내기, 후보 밖 항목 자동 탐지, 항목 없으면 한 덩어리 통과. theme.html `node --check`, `tsc --noEmit`, prettier, `npm run build:deploy`(홈에 치안안심 카드·옛 이름 0), `git diff --check` 통과.

## 2026-10-12 치안안심 0건 수정: loadOne 범위 오류, 종류 항목은 '시설물' (담당: 강민아)

- 증상: 치안안심을 열면 칩 없이 "0곳 · 데이터를 준비하고 있어요".
- 원인: `buildDynThemes` 가 `loadOne` 을 불렀는데 `loadOne` 은 `loadGroupData` **안의 지역 함수**라 밖에서는 ReferenceError → try/catch 에 먹혀 조용히 0건. (하네스가 `loadOne` 을 전역으로 흉내 내서 못 잡았음.)
- 조치: `loadGroupData` 안에서 `loadOne` 이 정의된 뒤에 `buildDynThemes(curGroup, loadOne)` 으로 넘겨 호출. 하네스에 "정의 뒤에서 loadOne 을 넘겨 호출" 정적 검사 추가.
- 담당자 캡처로 확인한 safety_all 항목: `구분`(전부 '구리시시설물'), **`시설물`(종류, 예: 'CCTV 및 비상벨')**, `상세정보`(관리번호), `설명`, `장소`(이름), `주소`, `기타`, `x`, `y`. 961건. → 종류 후보에 `시설물` 을 맨 앞에 두고, **값이 한 가지뿐인 후보('구분')는 건너뛰게** 함. 자료가 0건이면 토스트로 "레이어 공개 설정을 확인" 안내.
- 브랜치: `work/kangmina-safety-fix` (base `design/service-home-refresh` 564ab20).
- 검증: 하네스 — 실제 자료 모양(구분 동일·시설물 종류)으로 '시설물' 선택과 종류별 칩, 정적 호출 위치 검사 통과. theme.html `node --check`, `npm run build:deploy`, prettier, `git diff --check` 통과.

## 2026-10-12 치안안심: CCTV 보관 기간 문구 제거, 팝업 제목은 장소 이름 (담당: 강민아)

- 담당자 문의 "구리시 CCTV 도 30일 보관이 맞느냐" — 확인된 사실이 아니라(기관·설치 목적마다 다름) 옛 CCTV 안내문 "영상은 30일 보관… 30일 안에 요청"을 **"방범과 생활안전을 위해 설치된 CCTV예요 / 영상 열람이 필요하면 관리기관에 문의하세요"** 로 바꿈(`SAFETY_PRESETS.CCTV.guide`).
- 팝업 제목이 "구리시시설물 CCTV" 로 나오던 것: 옛 CCTV 설정의 `nameFn`·`cat` 이 `구분` 항목을 쓰는데 safety_all 의 `구분` 은 전부 '구리시시설물'. 치안안심 테마(`safetyThemeFor`)는 이제 제목을 **`장소`(없으면 시설명·명칭…, 그래도 없으면 종류 이름)** 로, 옛 설정의 분류 뱃지(`cat`·`catFn`·`titleFn`)는 쓰지 않음. 값이 한 가지뿐인 항목(`구분`)과 종류 항목(`시설물`)은 팝업에서 숨김(`constFields`).
- 브랜치: `work/kangmina-safety-text` (base `design/service-home-refresh` d63d04f).
- 검증: 하네스 — 제목이 장소(없으면 종류 이름), 구분·시설물 숨김, 분류 뱃지 없음, '30일' 문구 없음 검사 통과. theme.html `node --check`, `npm run build:deploy`, prettier, `git diff --check` 통과.

## 2026-10-13 치안안심 문구 손질: 구급함·재난용 CCTV 안내문, '구분' 항목 숨김 (담당: 강민아)

- 산악구급함: "쓴 뒤에는 관리기관에 알려 주세요"는 연락처가 없어 뺌 → "크게 다쳤을 땐 먼저 119에 신고하세요".
- 재난용 CCTV: "비가 많이 올 땐 이 주변을 피해 주세요"는 근거 없는 행동 지시라 뺌 → "재난 상황을 살피기 위해 설치된 감시 카메라예요 / 호우·태풍 때는 재난 문자와 안내 방송을 확인하세요".
- 팝업에 '구분: 구리시시설물'이 계속 보이던 것: 값이 한 가지뿐인 항목만 자동으로 숨기는데 실제 자료에서는 그렇지 않았을 수 있어 `GROUPS.치안안심.dyn.hide=['구분']` 으로 늘 숨김.
- 브랜치: `work/kangmina-safety-text2` (base `design/service-home-refresh` 46fbfae).
- 검증: 하네스 — 두 문구, '구분' 값이 둘이어도 숨김 검사 통과. theme.html `node --check`, `npm run build:deploy`, prettier, `git diff --check` 통과.

## 2026-10-13 우리동네 찾기 목록 배지: 공사·통제는 '진행중', AED 는 '사용 가능' (담당: 강민아)

- 교통 공사·통제 목록의 상태 배지가 '영업중'으로 나오던 것(목록 배지는 statusFn 테마면 일괄 '영업중'/'영업 전'/'종료'로 바꿔 보여 줌) → 테마가 `badge:{on,pre,off}` 로 배지 글자를 정할 수 있게 `rowStatus` 확장. 공사·통제 `{on:'진행중',pre:'예정',off:'종료'}`(팝업의 "진행중"과 맞춤), AED `{on:'사용 가능',off:'사용 불가'}`(치안안심 AED 칩에도 같이 적용). `badge` 가 없는 테마는 전과 같음.
- 브랜치: `work/kangmina-roadwork-status` (base `design/service-home-refresh` 65eddc5).
- 검증: 하네스 `badge-test.js`(rowStatus 를 떼어 내 배지 글자·기본값 검사), 치안안심 하네스, theme.html `node --check`, `npm run build:deploy`, prettier, `git diff --check` 통과.

## 2026-10-13 교통 공사·통제: 지도에 심볼 보이게 (담당: 강민아)

- 증상: 공사·통제 칩을 눌러도 지도에 심볼이 하나도 안 보임(목록엔 46건).
- 원인 둘: ① `svcSym:true` 라 ESRI UTIC 서비스의 원본 심볼(FeatureLayer)로 그리는데 화면에 나오지 않음 ② 칩을 고를 때 자료 범위로 옮기는 `view.goTo(catExtent())` 가 일반 객체를 넘겨 ArcGIS 가 무시(지도가 구리시에 머묾 — 공사·통제는 수도권 자료라 대부분 시 밖).
- 조치: 공사·통제를 `svcSym:false` 로 바꿔 우리 심볼(노란 삼각형 `transit_roadwork`)을 점 마커로 그림. `setCat` 의 범위 이동은 `asExtent()` 로 Extent 도형을 넘겨 실제로 움직이게(모든 테마에 적용: 칩을 고르면 그 자료 범위로 이동).
- 브랜치: `work/kangmina-roadwork-symbols` (base `design/service-home-refresh` c57f15e).
- 검증: theme.html `node --check`, 치안안심 하네스, `npm run build:deploy`, prettier, `git diff --check` 통과. 실제 심볼 표시는 배포 후 확인.

## 2026-10-13 교통 공사·통제: 사건유형별 원본 심볼, 목록 제목은 사건유형 (담당: 강민아)

- UTIC 레이어(`ESRIKR/UTIC_Traffic_Incident`)의 렌더러를 GitHub Actions 검사 워크플로로 읽어(이 환경은 esrikr.com 접속 불가) 사건유형 7종(사고·공사·행사·기상·통제·재난·기타)의 원본 그림 심볼(imageData)을 `SYM` 에 `utic_accident/work/event/weather/control/disaster/etc` 로 넣음. `symKey` 가 `교통 공사·통제` 행의 `incidentetype` 으로 고르므로 지도 핀·목록 아이콘이 유형별 원본 심볼로, 칩 아이콘은 테마 심볼(`transit_roadwork`) 그대로.
- 목록 제목(`nameFn`): 세부유형을 먼저 쓰던 것을 **사건유형 먼저**로("공사"), 세부유형은 유형과 다르고 다른 유형 이름이 아닐 때만 뒤에("사고 · 고장차량"). 자료에 공사인데 세부유형이 '교통사고'인 경우가 있어 그렇게 함.
- 확인한 UTIC 항목: incidentetype(사건유형)·incidentesubtype·incidenttitle·startdate·enddate·lane·roadname·source·controltypename·importantname·addressjibun·locationdatax/y. 좌표계 5179.
- 브랜치: `work/kangmina-utic-symbols` (base `design/service-home-refresh` eb5f2ce).
- 검증: 하네스 `utic-test.js`(유형→심볼 7종·기본값·칩 아이콘, 제목 규칙), 치안안심 하네스, theme.html `node --check`, `npm run build:deploy`, prettier, `git diff --check` 통과.

## 2026-10-13 교통 공사·통제 심볼 크기: 다른 심볼과 같은 72px 캔버스로 (담당: 강민아)

- UTIC 원본 심볼은 32~39px 캔버스에 투명 여백 3px 이라 같은 26px 핀으로 그리면 우리 심볼(72px 원이 꽉 참)보다 작아 보임 → `scripts/utic-icons.py` 로 여백을 잘라 72×72 에 꽉 차게(비율 유지, 알파 가중 양선형 보간) 키워 `SYM` 의 `utic_*` 를 교체. 그림 자체는 원본 그대로.
- 브랜치: `work/kangmina-utic-size` (base `design/service-home-refresh` 2c11ffd).
- 검증: 몽타주로 transit_roadwork 와 크기 비교, UTIC 하네스, theme.html `node --check`, `npm run build:deploy`, prettier, `git diff --check` 통과.

## 2026-10-14 전기차 충전소: '며칠 전 기준' 대신 '확인한 시각', 충전중은 몇 시간째 (담당: 강민아)

- 문제: "N시간 전 기준"·"1일 전 종료"가 자료를 받은 시각이 아니라 환경부 `상태갱신일시`(상태가 마지막으로 바뀐 시각)·`마지막충전종료` 라서, 15분마다 갱신해도 한가한 충전소는 "1일 전"으로 보임.
- 조치:
  - `evSyncTime(t)`: 스케줄 작업이 넣어 주는 수집 시각 항목(`EV_SYNC_FIELDS`: 수집일시·수집시각·데이터갱신일시·갱신일시·sync_dt·collected_at)이 있으면 그 최댓값, 없으면 **전체 충전기의 상태갱신일시 최댓값**(어디선가 15분 안에 바뀌므로 수집 시각과 거의 같음). 자료 묶음마다 한 번만 계산(WeakMap).
  - 목록: "지금 2대 충전 가능 (전체 5대) · 5분 전 확인". 팝업 아래: "🕐 5분 전 확인 · 15분마다 갱신돼요", 확인 시각이 45분(`EV_STALE_MIN`)을 넘으면 "⚠️ 최근 갱신이 지연되고 있어요" 빨간 줄.
  - 충전기 표: 충전가능은 시각 꼬리 없음, 충전중은 `sinceTxt` 로 "25분째 / 1시간째". 안내문은 "도착 시점엔 충전 상태가 달라질 수 있어요".
- 더 정확히 하려면: 15분 스케줄 작업이 레이어에 `수집일시` 항목(작업 실행 시각)을 함께 쓰면 화면이 자동으로 그 값을 씀(코드 수정 불필요).
- 브랜치: `work/kangmina-ev-freshness` (base `design/service-home-refresh` e075563).
- 검증: 하네스 `ev-test.js`(상태갱신일시 최댓값, 수집일시 우선, 45분 지연 경고, 캐시, 몇 시간째 표기, 설정 문구), 치안안심 하네스, theme.html `node --check`, `npm run build:deploy`, prettier, `git diff --check` 통과.

## 2026-10-21 치안안심: 여성안심귀갓길 4개 코스(선) 추가 (담당: 강민아)

- 자료: `Hosted/safety_secure_map/FeatureServer/1`(safety_safe_route, 선 4건). 항목(담당자 캡처): Shape_Leng·둘레길(코스: 안심1코스…)·지역(구간)·지정사·길이·명칭(○○지구대 여성안심귀갓길)·지정일·경로·순찰방법·순찰방법(야간).
- 치안안심은 safety_all 을 종류별 칩으로 만드는 동적 그룹이라, 고정 테마는 `GROUPS.치안안심.dyn.extra` 에 두고 `buildDynThemes` 가 종류별 칩 뒤에 합침(`addExtra`, safety_all 이 0건이어도 남음).
- 테마 `'안심귀갓길'`: 칩 아이콘은 안심귀갓길 심볼(`safety_nightcctv`), 선 색은 코스별(`colorBy:'course'` → 둘레길과 같은 `courseColor`; 코스 번호 후보에 '둘레길' 항목 이름 추가). 목록: 제목 = 명칭, 부제 = 지역(구간), "📏 300m 📅 2019.06 지정". 팝업: 코스 뱃지, 길이·지정일 칩, 안내("밤길이 걱정될 땐 이 길로… 경찰이 정기적으로 순찰"), 구간·경로·낮 순찰·밤 순찰(순찰방법(야간): 실제 항목 이름이 `순찰방법_야간_` 등이어도 정규화로 잡힘)·지정(지정사). Shape_Leng·코스 항목은 숨김. 코스를 누르면 경로가 지도에 표시.
- 브랜치: `work/kangmina-safe-route` (base `design/service-home-refresh` a6e43c1).
- 검증: 치안안심 하네스(스크래치가 초기화되어 다시 작성: 12종 심볼·extra 합치기(맨 뒤·0건이어도)·설정·loadOne 호출 위치) 통과, theme.html `node --check`, `npm run build:deploy`, prettier, `git diff --check` 통과. 실제 항목 이름·선 표시는 배포 후 확인.

## 2026-10-21 안심귀갓길 0건 수정: 뒤에 붙인 테마의 자료도 불러오게 (담당: 강민아)

- 증상: 안심귀갓길 칩이 생겼지만 0곳.
- 원인: `loadGroupData` 가 불러올 목록(`jobs`)을 함수 첫머리에서 만드는데, `buildDynThemes` 가 그 뒤에 `dyn.extra` 테마를 붙이므로 안심귀갓길 자료는 목록에 없어 한 번도 요청되지 않음.
- 조치: `buildDynThemes` 호출 직후, 그룹 테마 중 아직 안 받은 자료를 `jobs` 에 더함. 하네스에 호출 위치 정적 검사 추가.
- 브랜치: `work/kangmina-safe-route-load` (base `design/service-home-refresh` 1ef580e).
- 검증: 치안안심 하네스, theme.html `node --check`, `npm run build:deploy`, prettier, `git diff --check` 통과.

## 2026-10-21 메뉴: 수정 요청 빼고 구리 동네소식 추가, 메인에 동네소식 구역, 안심귀갓길 지정일 제거 (담당: 강민아)

- 안심귀갓길 팝업·목록에서 "📅 2019.06 지정" 제거(`지정일` 칩·목록 문구 삭제, 자동 행에서도 숨김).
- "수정 요청" 메뉴: 시민용 메뉴에서 뺌. `review.js` 는 주소에 `?review`(예: `?review=1`, 관리자 `?review=guri`)가 있을 때만 메뉴·창을 만든다(`REVIEW_ON`). 검토용으로는 그대로 쓸 수 있음 — `docs/review/README.md` 5절에 적음.
- "구리 동네소식"(https://guri.kgeohub.com/, 새 창): 홈 헤더 `SiteHeader.tsx`(PC·모바일, `external` 링크는 `target=_blank rel=noopener`)와 정적 지도 4쪽 헤더(PC·모바일 메뉴)에 G-MAP 소개 다음으로 추가.
- 메인 페이지: G-MAP 소개 구역 아래에 `news-section`(연한 주황 띠: "우리 동네 소식, 한곳에서 보세요" + "구리 동네소식 보러 가기 ↗" 버튼, 새 창). CSS `.news-section/.news-layout/.news-button`, 900px 이하 1열.
- 브랜치: `work/kangmina-news-menu` (base `design/service-home-refresh` 27c3c75).
- 검증: `tsc --noEmit`, prettier(src·site-shell.css), 지도 4쪽 인라인 스크립트·review.js `node --check`, 치안안심 하네스, `npm run build:deploy` 후 홈·지도 출력에 동네소식 링크 확인, `git diff --check` 통과.

## 2026-10-21 메인 동네소식 구역을 3D·항공과 같은 구성으로, 구역 번호 라벨 제거 (담당: 강민아)

- 담당자 피드백: 동네소식 띠가 성의 없어 보임 → 3D·항공 구역과 같은 구성(원형 일러스트 + 보조 문구 + 제목 + 설명 + 버튼)으로 다시 만듦. 소개(ABOUT) 식 좌우 2단보다 이 구성을 택한 이유: 동네소식은 3D·항공처럼 "들어가 보는 서비스"라 같은 결로 나란히 두는 쪽이 자연스럽고, ABOUT 구성은 사이트 설명 한 곳에만 쓰는 것이 구분이 됨.
- 새 일러스트 `src/components/NewsArt.tsx`(소식지 한 장: 제목·사진·글줄 + 확성기 배지, 선 currentColor·면 `--art-fill`), 따뜻한 주황 계열(`.news-illustration` 배경 #fbe8d3, 면 #f2cfae, 선 #b25a1e), 문구 "함께 나누는 구리 / 우리 동네 소식을 한곳에서 만나보세요. / 행사와 공지, 생활 정보까지 구리 동네소식에서 모아 볼 수 있어요.", 버튼 "구리 동네소식 보기 ↗"(새 창). 모바일(620px 이하)은 다른 구역과 같이 1열·가운데 정렬.
- 3D·항공(및 숨겨진 유기동물) 구역 오른쪽 위 "02 / SKYLINE", "03 / TIMELINE" 라벨 제거(`*-section-index` 요소·CSS 삭제).
- 브랜치: `work/kangmina-news-section` (base `design/service-home-refresh` 5438beb).
- 검증: `tsc --noEmit`, prettier, `npm run build:deploy` 후 홈 출력에 라벨 0회·동네소식 구역 확인, `git diff --check` 통과.

## 2026-10-21 동네소식: 메인에서 소개 위로, 메뉴에서 G-MAP 소개 앞으로, 문구에 공약지도 (담당: 강민아)

- 메인 페이지: 동네소식 구역을 G-MAP 소개(ABOUT) 구역 **위**로 옮김(항공사진 비교 → 동네소식 → 소개 순).
- 메뉴: 홈 헤더(PC·모바일)와 정적 지도 4쪽 헤더에서 "구리 동네소식"을 "G-MAP 소개" 앞에 둠.
- 문구: "행사와 공지, 공약지도와 생활 정보까지 / 구리 동네소식에서 모아 볼 수 있어요."
- 브랜치: `work/kangmina-news-order` (base `design/service-home-refresh` e792102).
- 검증: `tsc --noEmit`, prettier, `npm run build:deploy` 후 홈 출력에서 구역 순서·메뉴 순서·문구, 지도 3쪽 메뉴 순서 확인, `git diff --check` 통과.

## 2026-10-21 메인 계절 사진 교체 + 장소명 표기 (담당: 강민아)

- 담당자가 준 사진 4장으로 `public/images/hero-{spring,summer,autumn,winter}.webp` 교체: 봄 장자호수공원(1916×821), 여름 이문안호수공원(1919×820), 가을 한강시민공원(1916×821), 겨울 동구릉(1771×888). 원본 webp 그대로(각 350~420KB).
- 장소명: `season.config.ts` 에 `place` 추가, 히어로 오른쪽 아래에 `.season-place`(11px 흰 글씨, 반투명 검정 알약)로 표시. 사진이 바뀌면 글씨도 같이 바뀜.
- 브랜치: `work/kangmina-season-photos` (base `design/service-home-refresh` fb90eb5).
- 검증: `tsc --noEmit`, prettier, `npm run build:deploy` 후 출력에 장소명·사진 파일 확인, `git diff --check` 통과.

## 2026-10-21 모바일: 우리동네 찾기 칩 막대 얇게·목록 최소화, 항공사진 비교는 지역 선택 숨김·함께 보기를 아이콘으로 (담당: 강민아)

- 우리동네 찾기(≤900px): 테마·레이어 막대 84 → **62px**(그룹 아이콘 24px, 칩 아이콘 20px·이름 11px·건수 9.5px, 전체 칩 58px), 지도 영역 `calc(100dvh - 62px)`. 목록 바텀시트에 **최소(min)** 단계 추가(`.panel.min` = 손잡이 54px만): 손잡이를 아래로 끌거나 손잡이를 누르면 최소 ↔ 살짝(peek) 전환, 손잡이 아래에 "지도 크게 보기 ▾ / 목록 보기 ▴" 안내. 스냅 단계 full·half·peek·min.
- 항공사진 비교: "지도 위에 함께 보기" 카드를 기본 숨김으로 바꾸고, 오른쪽 컨트롤 맨 위에 **레이어 아이콘 버튼**(`#ovBtn`, `toggleOvBar()`)을 두어 누르면 카드(로드뷰·행정구역·연속지적도·용도지역·도시지역·문화재보호 6개 + 진하기·범례)가 펼쳐짐. 켜진 것이 있으면 아이콘이 초록으로(`is-on`), 카드 머리에 × 닫기, 로드뷰 켜면 지도를 찍어야 하니 카드 자동 닫힘. 데스크톱 카드 위치는 지역 선택 아래 오른쪽(`right:54px; top:62px`).
- 항공사진 비교 모바일(≤640px): 도·시군구·읍면동 선택(`.region`) 숨김, 카드는 화면 폭 전체·위 62px·세로 스크롤, 비교 라벨은 카드가 열리면 숨김.
- 브랜치: `work/kangmina-mobile-layout` (base `design/service-home-refresh` 484f8ad).
- 검증: theme/aerial 인라인 스크립트 `node --check`, 치안안심 하네스, `npm run build:deploy` 후 출력에 버튼·숨김 규칙·min 단계 확인, `git diff --check` 통과. 실제 모바일 화면은 배포 후 확인.

## 2026-10-21 항공사진 비교: 함께 보기 아이콘 방식은 모바일에서만, 데스크톱은 전처럼 (담당: 강민아)

- 데스크톱(>640px): "지도 위에 함께 보기" 카드가 전처럼 왼쪽 위(검색창 아래)에 항상 보이고, 레이어 아이콘 버튼(`#ovBtn`)과 × 닫기는 숨김(`display:none`).
- 모바일(≤640px): 카드 기본 숨김, 아이콘 버튼으로 열고 닫음(기존 동작). `toggleOvBar` 는 `show` 클래스만 바꾸므로 데스크톱에선 영향 없음(로드뷰 켤 때도 카드 유지).
- 브랜치: `work/kangmina-ovbar-desktop` (base `design/service-home-refresh` dd90daf).
- 검증: aerial 인라인 스크립트 `node --check`, `npm run build:deploy`, prettier, `git diff --check` 통과.

## 2026-10-21 모바일 수정: 치안안심 0건이면 다시 받기, 로드뷰 안내 문구 (담당: 강민아)

- 증상: 모바일에서 치안안심이 안심귀갓길 칩 하나(0건)만 보임. 데스크톱은 정상 → 첫 요청이 실패(느린 망·일시 오류)하면 `dataCache[url]=[]` 가 남아 다시 받지 않고, `dynBuilt` 도 남아 종류별 칩이 영영 안 만들어지던 구조.
- 조치: 실패한 자료는 빈 배열에 `__failed` 표시 → `loadGroupData` 진입 때 캐시를 지우고 다시 받음. `buildDynThemes` 는 0건이면 `dynBuilt` 를 남기지 않고 캐시를 지우며, 같은 그룹에 머물러 있으면 3초 뒤 자동 재시도(최대 2번, 안내 토스트), 그래도 안 되면 "새로고침" 안내.
- 항공사진 비교 로드뷰 안내: 모바일(≤640px)은 패널이 아래에 열리므로 "로드뷰가 아래쪽에 열려요"로.
- 브랜치: `work/kangmina-mobile-fixes` (base `design/service-home-refresh` 27000bc).
- 검증: 치안안심 하네스(0건이면 dynBuilt 없음·캐시 삭제·재시도 횟수, 실패 표시 처리 정적 검사) 통과, theme/aerial `node --check`, `npm run build:deploy`, prettier, `git diff --check` 통과.

## 2026-10-21 항공사진 비교 모바일: 연도 막대 안내문을 접어 두고 ⓘ 로 펼치기 (담당: 강민아)

- 모바일(≤640px)에서 "왼쪽 ○년 ↔ 오른쪽 ○년…"·"○년 항공사진은 1:4,500 보다…" 안내가 두 줄씩 차지해 지도가 좁아 보임 → 안내문(`.ts-hint`, `.ts-note`)은 접어 두고 제목 옆 **ⓘ 버튼**(`#tsInfo`, `toggleTsInfo()`)을 누를 때만 펼침(`.ts-bar.info-open`). 확대 한계 경고(`.ts-note.zoomed`: 사진이 안 나오는 축척)만은 접힌 상태에서도 바로 보임. 데스크톱은 전과 같음(ⓘ 숨김).
- 브랜치: `work/kangmina-tsbar-mobile` (base `design/service-home-refresh` 9b1bd0d).
- 검증: aerial 인라인 스크립트 `node --check`, `npm run build:deploy`, prettier, `git diff --check` 통과.

## 2026-10-21 자료 못 받았을 때 이유 표시 + 다시 시도 (담당: 강민아)

- 담당자 휴대폰(카카오톡 안 브라우저, LTE)에서 치안안심이 여전히 0건·안심귀갓길 칩만 보임. 데스크톱(사무실 망)은 정상. 같은 guri.go.kr 서비스인데 행정동 경계(ArcGIS JS 레이어)는 휴대폰에서도 그려지므로 원인을 이 환경에서 단정할 수 없음(망·서버 응답·앱 내 브라우저 가능성).
- 조치: `loadOne` 이 실패 이유(`why`: "Token Required", "Failed to fetch", "0건" 등)를 `loadWhy[url]` 에 남기고, 목록이 비었을 때 실패한 자료가 있으면 "자료를 불러오지 못했어요 + 이유 한 줄 + **다시 시도** 버튼"을 보여 줌. `retryGroup()` 은 그룹 자료 캐시를 지우고(치안안심은 `dynBuilt` 도 초기화) 그룹을 다시 연다.
- 담당자에게: 휴대폰에서 치안안심을 열어 목록에 뜨는 이유 한 줄을 캡처해 보내 달라고 요청 → 원인 확정 후 수정.
- 브랜치: `work/kangmina-load-diag` (base `design/service-home-refresh` 0da82c7).
- 검증: theme `node --check`, 치안안심 하네스, `npm run build:deploy`, prettier, `git diff --check` 통과.

## 2026-10-21 치안안심이 휴대폰에서만 0건인 원인 추정: 새 레이어 공개 공유 미설정 (담당: 강민아)

- 담당자 확인: 같은 휴대폰에서 다른 주제는 칩이 다 나오고 치안안심만 안심귀갓길 칩 하나(0건). → 종류별로 나눠 보는 방식 문제가 아니라, **치안안심이 쓰는 두 새 레이어(safety_all, safety_secure_map/1)만 휴대폰(외부 망)에서 못 받는 것**. 다른 주제의 레이어는 예전부터 공개 공유된 것들이고, GitHub Actions(외부 IP)에서도 이 서비스는 `499 Token Required` 였음. 사무실 망(데스크톱)에서는 포털 내부 접근이라 보였을 가능성이 큼.
- 조치(코드): 빈 목록의 실패 이유가 "Token Required/499" 면 "이 자료는 아직 공개(모든 사용자) 공유가 안 되어 있어요 — 포털에서 공유 설정을 바꿔야…" 로, 연결 실패면 "서버에 연결하지 못했어요 — 잠시 뒤 다시 시도" 로 쉬운 말로 표시.
- 조치(포털, 담당자): 구리시 포털에서 `safety_all` 과 `safety_secure_map` 항목을 **모든 사용자(공개)** 로 공유. 바꾼 뒤 휴대폰에서 "다시 시도".
- 브랜치: `work/kangmina-load-reason-ko` (base `design/service-home-refresh` b587cf1).
- 검증: theme `node --check`, `npm run build:deploy`, prettier, `git diff --check` 통과.

## 2026-10-21 못 받은 레이어 이름과 이유를 목록 위 띠로 표시 (담당: 강민아)

- 담당자 확인: 레이어를 모두 공개로 바꿨는데도 휴대폰에서 치안안심은 안심귀갓길 칩 하나(0건)만 나옴. 안심귀갓길도 0건이므로 **새 레이어 두 개(safety_all, safety_secure_map/1)만 휴대폰(외부 망)에서 못 받는 상태**. 같은 호스트의 다른 레이어(공영주차장 등)는 휴대폰에서 정상.
- GitHub Actions(해외 IP)에서는 옛 레이어(life_parking)도 `499 Token Required` 라 외부 검증은 불가 — 해외 IP 차단으로 보임. 사무실 데스크톱은 내부 망이라 새 레이어도 보임.
- 휴대폰에서 직접 확인하는 방법(브라우저 주소창에 입력):
  - 되는 것: `https://www.guri.go.kr/gmapsvr/rest/services/Hosted/life_parking/FeatureServer/0/query?where=1%3D1&returnCountOnly=true&f=json`
  - 확인 대상: `https://www.guri.go.kr/gmapsvr/rest/services/Hosted/safety_all/FeatureServer/0/query?where=1%3D1&returnCountOnly=true&f=json`
  - 둘의 응답이 다르면(두 번째가 `Token Required`, 오류 페이지, 빈 화면 등) 서버/망 쪽 설정(항목 공유 외에 외부 접속 허용 경로·웹방화벽 URL 등록)을 확인해야 함.
- 조치(코드): 목록 위에 주황 띠로 "자료를 못 받았어요 · safety_all/FeatureServer/0 + 이유 + 다시 시도" 표시(`loadFailNote()`/`showLoadNote()`, `#loadNote`). 스크롤하지 않아도 원인이 보임. 이유는 토큰 요구/연결 실패/JSON 아님(보안 차단 페이지) 세 가지를 쉬운 말로 바꿈.
- 브랜치: `work/kangmina-load-note` (base `design/service-home-refresh` f368f3a).
- 검증: theme `node --check`, 스크래치 `note-test.js`(이유 생성 4 경우) 통과, `npm run build:deploy`, prettier, `git diff --check` 통과.

## 2026-10-21 시즌·겨울 추가, 시즌·가을 숨김, 명소는 문화·여가로, 메인은 겨울 사진 (담당: 강민아)

- 배경: 11월 홈페이지 이전·오픈에 맞춰 겨울 시즌으로 전환(구리시 요청).
- `public/maps/theme.html`
  - 새 그룹 `시즌·겨울`(아이콘 `TOPIC_IC['겨울']` 눈송이, accent `#2F5F9E`), 테마 8개:
    - 한파쉼터 `winter_shelter` — 시설구분·이용안내·운영기간·운영시간·야간/주말 팝업, 수용인원 칩
    - 제설함 `winter_saltbox_new` — 이름이 없으면 설치장소→주소→'제설함 번호' 순으로 표시, 종류·규격/비치 자재/관리기관 팝업, 눈 올 때 안내 문구
    - 결빙취약구간 `winter_icyroad_l`(선) + 결빙취약구간 시종점 `winter_icyroad_p`(점, `chipHide:true`, `pair`) — 칩은 '결빙취약구간' 하나, 목록에는 구간과 시점·종점이 각각 나옴(둘레길·둘레길 시설물과 같은 방식). 구간 길이(`hikeLen`)·시점·종점·취약 사유 팝업
    - 둘레길·둘레길 시설물·등산로·등산로 시설물 — 시즌·가을 정의를 `trailThemes(계절)` 함수로 빼서 가을·겨울이 같이 씀(문구만 계절에 맞춤)
  - 심볼 4개 `winter_shelter/saltbox/icyroad/icyroad_p` 를 `scripts/winter-icons.py`(safety-icons.py 도형 도구 재사용)로 그려 SYM 에 base64 로 넣음
  - `시즌·가을` 은 `hidden:true`(URL 직접 접근은 가능), `구리 명소` 는 `문화·여가` 의 축제 바로 뒤로 옮김(문구 '구리의 대표 명소…')
- 홈(Next.js)
  - `links.ts` ThemeGroup 에 `시즌·겨울`, `theme-groups.config.ts` 가을 `hidden:true` + 겨울 카드(Snowflake, '한파쉼터·제설함·결빙취약구간'), 문화·여가 요약 '축제·명소·둘레길·공원'
  - 헤더·푸터·지도 카드의 '우리동네 찾기' 링크 → `시즌·겨울`
  - `season.config.ts`: `SEASON_OVERRIDE='winter'` 로 메인 사진·추천을 겨울로 고정(`'auto'` 로 바꾸면 날짜 기준). 겨울 추천 항목은 시즌·겨울/문화·여가 지도로 연결, 가을 '아차산 단풍 산책'은 문화·여가로
- 필드 이름은 레이어를 아직 못 읽어(개발 환경에서 guri.go.kr 접속 불가) 후보를 넓게 잡았음. 실제 자료가 뜨면 목록 이름·부제·팝업이 맞는지 확인하고 `fields`/`pop` 후보를 다듬을 것.
- 검증: theme `node --check`, Playwright(오프라인, 가짜 자료) — 기본 그룹=시즌·겨울, 칩 6개(시종점 숨김), 결빙취약구간 선택 시 구간+시종점 3건 목록, 이름/부제/길이 포맷 확인(`scratchpad/pw/winter-test.js`); `npx tsc --noEmit`, prettier, `npm run build:deploy`, `git diff --check` 통과.
- 브랜치: `work/kangmina-winter` (base `design/service-home-refresh` c70f603).

## 2026-10-21 겨울 팝업 손질: 제설함 문구·전화 라벨, 결빙취약구간 시점·종점 지번주소 (담당: 강민아)

- 실제 자료 확인(담당자 캡처): 제설함 항목은 주소·전화·관리기관·비고·세부설치장소·관리부서_동·관리자_전화번호. 결빙취약구간(선·점) 항목은 구간·연장·**시점지번주·종점지번주**(ArcGIS 항목 이름이 잘린 것, 뜻은 시점/종점 지번주소)·시점_경도·정북기준_1·기점기준심 등.
- 제설함: 안내문에서 "쓰고 난 삽은 다시 넣어 주세요" 삭제, 전화 버튼은 `telLabel:'관리기관에 전화하기'`.
- 결빙취약구간(선): 팝업 시점·종점을 `시점지번주`/`종점지번주`(정확 일치 `pickVal(...,true)`)로. 부분 일치를 쓰면 '시점'이 `시점_경도`를 잡아 좌표가 보였음. 좌표·정북기준 항목은 `hidePat`으로 숨김.
- 시종점(점): 시점/종점 여부는 `icyEnd()`가 비고('결빙취약구간종점')·구분 값에서 읽어 이름("강변북로 종점")·부제·칩에 씀. 팝업은 구간·시점 주소·종점 주소·비고만 보이고 구분(=결빙취약구간)·시점_경도·정북기준_1·기점기준심은 숨김.
- 검증: theme `node --check`, Playwright 오프라인(캡처와 같은 모양의 가짜 행: 이름·부제 확인), `npm run build:deploy`, `git diff --check` 통과. 팝업 본문은 `POP_MAP`이 지도 초기화 뒤에 생겨 오프라인 검사가 안 되므로 배포본에서 확인.
- 브랜치: `work/kangmina-winter-pop`.

## 2026-10-21 팝업 자동 항목 라벨 정리, 시종점 중복 항목 숨김 (담당: 강민아)

- 팝업의 자동 항목 라벨에서 밑줄(_)을 띄어쓰기로 바꾸고 `_동` 꼬리는 뗀다(관리부서_동 → 관리부서, 관리자_전화번호 → 관리자 전화번호). 모든 테마 공통.
- 결빙취약구간 시종점: 위에 '시점 주소'·'종점 주소'가 있으니 원본 항목(시점지번주·종점지번주)은 `hidePat`으로 숨김. 총길이는 '구간 길이'로 km 표시(`hikeLen`)하고 원본은 숨김.
- 검증: theme `node --check`, 라벨/정규식 단위 확인, `npm run build:deploy`, `git diff --check` 통과. 브랜치 `work/kangmina-pop-labels`.

## 2026-10-21 치안안심: 자료를 못 받아도 종류 칩 12개는 보이게, 안내 띠 제거 (담당: 강민아)

- 담당자 설명: 휴대폰은 구리시 포털 주소(hosts)를 못 잡아 자료가 0건인 건 알고 있음. 문제는 **치안안심만 전체 옆 칩이 안심귀갓길 하나**라는 것(시즌·겨울 등은 자료가 0건이어도 칩이 다 보임). 치안안심 칩은 받은 자료의 '시설물' 값으로 만들기 때문.
- 조치: `SAFETY_KNOWN`(담당자 캡처 기준 12종: AED, CCTV 및 비상벨, 주정차단속 CCTV, CCTV, 재난용 CCTV, 방범용 CCTV, 지킴이집, 소방시설, 안심가림판 공중화장실, 로고젝터, 안심안내판, 산악구급함)으로 **0건 자리표시 칩**(`placeholder:true`, `SAFETY_ORDER` 순)을 깔고 안심귀갓길은 맨 뒤. 자료가 오면(3초 뒤 자동 재시도 ≤2회, 또는 '다시 시도') 자리표시를 지우고 실제 값으로 다시 만든다. 0건일 때 캐시는 지우지 않고 실패 표시(`__failed`)로 두어 같은 주소를 두 번 요청하지 않음. 토스트 두 개(불러오는 중/못 불러옴)는 뺌.
- 목록 위 주황 안내 띠(`#loadNote`, #88)와 빈 목록의 실패 이유 문구(#86·#87) 제거 → 원래 빈 목록 문구로 복원. 못 받은 레이어가 있으면 '다시 시도' 단추만 붙음.
- 검증: 하네스 `safety-test.js`(0건 → 12종 자리표시 + 안심귀갓길 맨 뒤, 재시도 성공 시 실제 값으로 교체) 통과, Playwright 오프라인(휴대폰 폭, 모든 요청 실패) 칩 14개(전체 + 12종 + 안심귀갓길)·띠 없음·원래 빈 목록 문구 확인, theme `node --check`, `npm run build:deploy`, `git diff --check` 통과. 브랜치 `work/kangmina-safety-chips`.

## 2026-10-21 우리동네 찾기 디자인 1차: 그룹 색 팔레트 정리, 테마 칩 막대 얇게 (담당: 강민아)

- 구리시 요청 "모든 페이지 디자인을 통일되고 이쁘게" 의 1차 조치. 담당자 제안대로 테마 색과 칩 두께부터.
- 그룹 강조색(`GROUPS[g].accent`)을 채도 낮추고 밝기를 맞춘 한 팔레트로(흰 글자 대비 4.5:1 이상): 겨울 `#35679A`, 치안안심 `#B9473B`, 건강·의료 `#1E8A78`, 생활편의 `#4C5FAE`, 우수맛집 `#B26331`, 문화·여가 `#4E7F3C`, 반려동물 `#B2507A`, 교통 `#58687B`(숨긴 여름 `#2A7FA8`·가을 `#A65A2E`·육아 `#6F5FBF`). 홈 그룹 카드(`theme-groups.config.ts`)도 같은 값 — 바꾸면 둘 다 바꾼다.
- 칩 막대: 데스크톱 96→76px, 모바일 62→56px(`.mapwrap` top/height 도 56px). 아이콘 30→26px(모바일 18), 글자 13.5→13px, 그라데이션·칸 구분선은 더 옅게.
- 칩은 `flex:1 0 auto` 로 글자보다 좁아지지 않게 — 긴 이름("CCTV 및 비상벨")이 옆 칸을 덮던 문제 해결. 안심가림판 공중화장실은 칩에서 `short:'안심가림판'`.
- 전후 비교: 스크래치 `compare-desktop.png`·`compare-mobile.png`(Playwright 오프라인, `pw/shot.js`).
- 검증: theme `node --check`, 치안안심 하네스, `npx tsc --noEmit`, prettier, `npm run build:deploy`, `git diff --check` 통과. 브랜치 `work/kangmina-chip-style`.
- 다음 후보(담당자 확인 뒤): 상단바·푸터를 지도 4쪽과 홈에서 같은 높이·글꼴·버튼으로, 팝업·목록 카드 모서리/그림자 규격 통일, 목록 아이콘 크기 통일, 3D·항공 페이지의 안내 카드 톤을 테마지도와 맞추기, 홈 카드 색을 accent 팔레트로(이번에 반영).

## 2026-10-21 메인 푸터 새 단장 (담당: 강민아)

- 디자인 통일 2차. 두 줄짜리 밋밋한 푸터를 **밝은 안내 영역 + 짙은 초록 띠** 구성으로.
  - 안내 영역(`.footer-main`, 4칸 그리드): 브랜드(CI, "G-MAP 구리시 시민생활지도", `siteConfig.description` 한 줄) / 지도 바로가기(`footerLinks` — 헤더 메뉴와 같은 구성: 우리동네 찾기·3D입체지도·항공사진 비교·구리 동네소식(새 창)·G-MAP 소개, 유기동물은 `features.animalMap`) / 문의(부서·전화 `tel:` 링크·주소) / 맨 위로(원형 버튼, hover 시 초록으로).
  - 띠(`.footer-bar`, `#173e30`): © 연도 구리시 · 구리시 문장(`guri-emblem.png`) "이 누리집은 구리시 누리집이에요" · 제작 케이지오솔루션.
  - 모바일(≤900px): 브랜드 한 줄, 바로가기·문의 두 칸, 맨 위로 가운데, 띠는 줄바꿈 가운데 정렬.
- 푸터는 `.service-home` 바깥이라 `var(--forest)`가 안 먹음 → 색 값을 직접 씀(처음 캡처에서 띠가 흰색으로 나온 원인).
- 전후 비교: 스크래치 `footer-compare-desktop.png`·`footer-compare-mobile.png`(빌드 결과를 로컬 http 로 띄워 Playwright 캡처, `pw/footer-shot.js`).
- 검증: `npx tsc --noEmit`, prettier, `npm run build:deploy`, `git diff --check` 통과. 브랜치 `work/kangmina-footer`. `KrdsFooter.tsx` 는 미사용(v1)이라 손대지 않음.

## 2026-10-21 상단바 통일(공통 요소 1번) + 푸터 연락처 (담당: 강민아)

- 푸터 문의: `siteConfig.contact` → 부서 '경기도 구리시청 토지정보과', 전화 '031-550-8731'(담당자 지시).
- **메뉴 한 곳**: `src/config/shell-nav.json`(링크 종류 theme/animal/scene/aerial/external/home, 숨긴 기능은 `feature`). 홈 `SiteHeader.tsx` 는 `shell-nav.ts` 의 `shellLinks()`/`shellSearch` 로, 푸터 바로가기도 같은 함수로 읽음.
- **지도 4쪽의 정적 헤더 자동 생성**: `scripts/sync-shell.mjs` 가 같은 json 으로 `<!-- shell:header -->…<!-- /shell:header -->` 블록을 다시 써 넣음(`npm run sync:shell`, `build:deploy` 시작 때 자동). 손으로 고치지 말 것. 이번에 지도 4쪽의 '우리동네 찾기' 링크가 `?group=여름`(옛 값)이던 것이 `시즌·겨울` 로 맞춰짐. 숨긴 유기동물 메뉴는 주석으로 남음.
- **높이 한 값**: `site-shell.css` `:root{--shell-h:64px}`(≤768px 56px). 홈 76px·지도 56px 이던 것을 모두 64px 로, 모바일은 모두 56px. 경계선은 `box-shadow: inset` 이라 총 높이 = `--shell-h`. 지도 페이지의 오프셋은 변수로: theme `.chipbar{top:var(--shell-h)}`, scene·aerial `.main{height:calc(100dvh - var(--shell-h))}`, animal `.filters{top:var(--shell-h)}`.
- 지도 변형(`.map`)은 가로 여백 24px·전체 폭, 홈은 1248px 가운데·32px(본문과 정렬) — 글꼴·메뉴 간격·테마 찾기 버튼·모바일 메뉴는 동일.
- `gmap-shared.css` 의 안 쓰던 옛 `.site-header` 블록(150~365줄) 삭제.
- 마스트헤드(정부 누리집 띠)는 홈에만 둠(지도 쪽은 공간 우선). 필요하면 sync-shell 에 한 줄 추가하면 됨.
- 전후: 스크래치 `header-compare-1280.png`·`header-compare-390.png`(위 2개 전: 홈·테마 / 아래 3개 후: 홈·테마·항공).
- 검증: `npx tsc --noEmit`, prettier, 지도 4쪽 `node --check`, `npm run build:deploy`(sync 포함), `git diff --check` 통과. 브랜치 `work/kangmina-header-unify`.

## 2026-10-21 카드·팝업 규격 통일(공통 요소 2번) (담당: 강민아)

- `public/styles/site-shell.css` `:root` 에 공통 규격 토큰: `--ui-radius-sm` 6px(버튼·입력·칩), `--ui-radius` 10px(카드·팝업·떠 있는 패널), `--ui-radius-lg` 16px(큰 카드·모달·바텀시트), `--ui-line`, `--ui-shadow`(0 2px 10px, 8%), `--ui-shadow-lg`(0 12px 32px, 16%), `--ui-pad` 16px(카드·팝업 가로 여백), `--ui-title` 17px(제목). 홈은 globals.css 가, 지도 4쪽은 `<link>` 가 같은 파일을 읽는다.
- 지도 4쪽의 `:root` `--radius/--shadow/--shadow-lg` 는 토큰의 별칭(폴백 포함)으로. 적용: theme 팝업(`.infocard` 10px·그림자·머리/본문 여백·제목)·`.opcard`·그룹 메뉴·바텀시트 16px; scene 팝업(같은 값)·`.hint`·`.bar`·`.cover .box`; aerial `.ts-bar`·`.ov-bar`(12→10)·`.key-warn`·검색 제안; animal `.card` 10px·`.modal` 16px; 홈 `.theme-search`·`.catalog-icon`(10, 모바일 6)·`.home-button`·푸터 맨 위로 버튼 그림자.
- 바뀐 수치는 작다(8/12 → 10, 그림자 톤 통일). 핵심은 **앞으로 한 곳(`--ui-*`)만 바꾸면 모든 페이지가 같이 바뀐다**는 것. 새 카드·팝업을 만들 때는 이 토큰을 쓸 것.
- 검증: 지도 4쪽 `node --check`, prettier, `npm run build:deploy`, `git diff --check` 통과. 전후 캡처(스크래치 `ui-compare.png`, 3D·항공 떠 있는 카드)는 차이가 미세함. 브랜치 `work/kangmina-ui-tokens`.

## 2026-10-21 아이콘 규격 통일(공통 요소 3번) (담당: 강민아)

- 조사: 지도 4쪽의 UI 선 아이콘은 이미 `stroke-width="1.75"`·16px(버튼 안)·18px(지도 컨트롤)로 통일돼 있었음. theme.html 에 남은 1.4~2.6 굵기는 전부 **심볼·그룹 타일 픽토그램**(색 원 위 흰 그림, 28 viewBox)이라 의도된 값 — 그대로 둠.
- 홈(lucide-react)은 기본 굵기 2 에 크기 13·16·18·19·22·25 가 섞여 있었음 → `service-home.css` 에 `.service-home svg.lucide, .service-footer svg.lucide{stroke-width:1.75}` 로 지도 쪽과 같은 굵기, 크기는 14(작은 글 옆)·18(링크 화살표·버튼)·22(목록 아이콘)·24(카드 타일) 네 단계로 정리(`page.tsx`).
- 규격 요약(새 아이콘을 넣을 때): UI 선 아이콘 = lucide 계열, 선 1.75, 둥근 끝, 크기는 위 네 단계. 지도 심볼 = 72px PNG(색 원 + 흰 그림, `scripts/*-icons.py`), 그룹 타일 = `TOPIC_IC` SVG.
- 검증: `npx tsc --noEmit`, prettier, `npm run build:deploy`, `git diff --check` 통과. 브랜치 `work/kangmina-icons`.

## 2026-10-21 자료 요청 시간 제한(25초) — 서버가 응답을 안 주면 '불러오는 중…'에 머물지 않게 (담당: 강민아)

- 담당자 캡처(데스크톱, 시즌·겨울): 칩 전부 0, 목록은 회색 자리표시(skeleton), 지도 오른쪽 위 '불러오는 중…'. 코드 경로는 가짜 응답으로 끝까지 확인됨(8개 레이어 → 칩 건수·목록·머리글 모두 표시, `pw/flow-test.js`). 캡처 상태는 **요청이 끝나지 않고 계속 대기 중**인 모양 — 서버(guri.go.kr, hosts 로 내부 IP)에 연결은 되는데 응답이 안 오는 경우(VPN·내부망 끊김 등). 이전에는 그러면 영원히 '불러오는 중…' 이었음.
- 조치(`theme.html`): `fetchT(url,ms)`(AbortController, `FETCH_MS`=25초)를 레이어 질의·메타 조회·행정동 경계에 적용. 질의가 시간 초과면 메타 조회로 더 기다리지 않고, 같은 그룹의 나머지 레이어도 즉시 실패 처리(`srvDown`) → 총 대기 25초 뒤 빈 목록 + '다시 시도'. 실패 이유는 "응답 없음(25초)".
- 검증: `pw/hang-test.js`(guri 요청에 응답을 안 주는 상황) 28초 시점에 목록 복귀 확인, `flow-test.js`(가짜 응답) 정상, 치안안심 하네스, theme `node --check`, `npm run build:deploy`, `git diff --check` 통과. 브랜치 `work/kangmina-fetch-timeout`.

## 2026-10-21 메인 섹션 리듬 통일(공통 요소 4번) (담당: 강민아)

- `service-home.css` `.service-home` 에 `--sec-y: 80px`(모바일 `--sec-y-m: 48px`). 본문 섹션 다섯 곳(찾기 80/88, 3D·항공·동네소식 60/60, 소개 90/90; 모바일 48/50·48/45·50/50)이 제각각이던 위아래 여백을 모두 이 값으로. 히어로(56px)와 푸터는 성격이 달라 그대로.
- 제목 h2(32px, 모바일 26px)·eyebrow(11px)·설명(14px)은 이미 통일돼 있었음.
- 계절 강조색(`season.config.ts` accentColor)을 그룹 팔레트와 연결: 겨울 `#35679A`(=시즌·겨울), 가을 `#A65A2E`(=시즌·가을), 여름 `#2A7FA8`(=시즌·여름). 봄은 해당 그룹이 없어 그대로.
- 전후: 스크래치 `home-compare-1280.png`·`home-compare-390.png`(전체 페이지, 왼쪽 전·오른쪽 후).
- 검증: `npx tsc --noEmit`, prettier, `npm run build:deploy`, `git diff --check` 통과. 브랜치 `work/kangmina-section-rhythm`.

## 2026-10-21 모바일 바텀시트·상단 막대 통일(공통 요소 5번) (담당: 강민아)

- 손잡이 모양(`.sheet-handle`: 44×5 회색 막대 + 11px 안내 글자)을 `gmap-shared.css` 로 옮겨 지도 4쪽 공용으로. theme.html 의 중복 규칙은 제거(모바일에서 `display:block` 켜는 줄과 ::before 글자만 남김).
- 3D(`.bar`)·항공(`.ts-bar`)의 모바일 하단 막대를 우리동네 찾기 목록과 같은 **바텀시트 모양**으로: 화면 아래에 붙고(좌우 여백 0), 위 모서리 16px(`--ui-radius-lg`), 같은 그림자, 맨 위에 손잡이. 손잡이를 누르면 `.min` 으로 접혀 손잡이만 남고 지도가 커짐(글자: 3D '장소 목록 보기 ▴', 항공 '연도 선택 보기 ▴' ↔ '지도 크게 보기 ▾'). 우리동네 찾기는 기존처럼 끌기 가능(min/peek/half/full), 3D·항공은 누르기 토글.
- 지도 컨트롤 버튼은 세 쪽 모두 34px·오른쪽 10px. 위치(위/아래)는 페이지 구조에 따라 다름: 우리동네 찾기는 오른쪽 위, 3D·항공은 하단 막대 위(검색창이 위를 차지).
- 상단바는 #95 에서 이미 56px 공통. 유기동물 찾기는 숨김 상태라 손대지 않음.
- 검증: Playwright 모바일(390px) — 세 쪽 모두 손잡이 표시, 모서리 16px·그림자 동일, 손잡이 클릭 시 글자 전환 확인(`pw/sheet-test.js`); 지도 3쪽 `node --check`, prettier, `npm run build:deploy`, `git diff --check` 통과. 브랜치 `work/kangmina-mobile-sheet`.

## 2026-10-21 우리동네 찾기 목록 줄을 카드처럼 (추가 다듬기 1번) (담당: 강민아)

- `.row`: 둥근 모서리(`--ui-radius` 10px)·좌우 8px 띄움, 행 사이는 옅은 선(`::before`), 선택은 왼쪽 막대 대신 연한 배경 전체 + 1px 테두리, 아이콘 32px, 이름 15px, 부제 12.5px(줄 간격 1.35), 상태 배지는 알약(20px, radius 999), 행동 버튼 34px. 모바일은 좌우 6px.
- 전후: 스크래치 `list-compare.png`(왼쪽 전·오른쪽 후, 가짜 자료 5건·두 번째 줄 선택).
- 검증: theme `node --check`, Playwright 캡처, `npm run build:deploy`, `git diff --check` 통과. 브랜치 `work/kangmina-list-rows`.

## 2026-10-21 목록 '상세' 단추 제거, 링크 공유창 공용화 (담당: 강민아)

- 우리동네 찾기 목록의 선택 줄 행동에서 '상세' 단추를 뺌(줄을 누르면 팝업이 바로 열림). 길찾기·전화가 둘 다 없으면 행동 줄 자체를 생략.
- 공유: 담당자 확인 — 항공사진 비교를 휴대폰(카카오톡 안 브라우저)에서 공유 아이콘을 누르면 "주소를 복사했어요" 토스트만 뜸. 그 브라우저엔 기기 공유창(`navigator.share`)이 없어 복사로 떨어지던 것.
  → `public/maps/gmap-share.js`(+ `gmap-shared.css` `.gm-share-*`): `gmapShare({title,url})` — 기기 공유창이 있으면 그것, 없으면 **페이지 안 공유창**(주소 복사·카카오톡(sharer.kakao.com)·문자(sms:)·이메일(mailto:) + 안내 한 줄). 데스크톱은 가운데 창, 모바일은 바텀시트. 우리동네 찾기·3D·항공 세 쪽의 `shareUrl()`이 같은 함수를 씀(옛 복사 폴백은 http 가 아닌 주소용으로 남김).
- 검증: Playwright(로컬 http, `navigator.share` 없음) — 항공(모바일)·우리동네 찾기(데스크톱) 공유창 열림·주소·카카오 링크 확인(`pw/share-test.js`); 지도 3쪽 `node --check`, prettier, `npm run build:deploy`(`out/maps/gmap-share.js` 포함), `git diff --check` 통과. 브랜치 `work/kangmina-share-dialog`.

## 2026-10-21 공유창 카카오톡 단추: 앱 키 없이는 숨김 (담당: 강민아)

- 담당자 확인: 공유창의 '카카오톡'(sharer.kakao.com 링크)을 누르면 "요청 실패 — 잘못된 요청으로 인증에 실패". 카카오 공유는 **카카오 개발자 앱의 JavaScript 키와 도메인 등록**이 있어야 동작함(키 없는 sharer 주소는 막혀 있음).
- 조치(`gmap-share.js`): 카카오톡 단추를 카카오 JS SDK(2.7.4, `Kakao.Share.sendDefault` 텍스트 메시지)로 바꾸고 `KAKAO_JS_KEY` 가 비어 있으면 **단추를 숨기고** 안내문을 "카카오톡으로 보내려면 '복사'한 주소를 대화창에 붙여 넣거나, 오른쪽 위 ⋮ 메뉴의 '공유하기'를 눌러 주세요" 로. SDK 는 단추를 처음 누를 때만 불러옴.
- 키 발급 절차(구리시 또는 케이지오 카카오 계정): developers.kakao.com → 내 애플리케이션 → 앱 추가(이름 예: 구리시 G-MAP) → [앱 키] **JavaScript 키** 복사 → [플랫폼 > Web] 사이트 도메인에 `https://kgeodata.com` 과 최종 서비스 도메인 등록. 카카오 로그인·동의항목은 필요 없음. 키를 `public/maps/gmap-share.js` 맨 위 `KAKAO_JS_KEY` 에 넣고 배포하면 단추가 살아남.
- 검증: Playwright(로컬 http) 키 없음 → 카카오 단추 숨김·안내문 확인(`pw/share-test.js`); `node --check`, prettier, `npm run build:deploy`, `git diff --check` 통과. 브랜치 `work/kangmina-share-kakao`.

## 2026-10-21 공유창 안내문: ⋮ 메뉴 위치를 못 박지 않음 (담당: 강민아)

- 담당자 지적: 안내문의 "오른쪽 위 ⋮ 메뉴"가 휴대폰(안드로이드 카카오톡 브라우저)에서는 오른쪽 아래에 있음. 위치를 단정하지 않도록 "브라우저의 ⋮ 메뉴"로 고침(`gmap-share.js` 안내문 2곳).
- 검증: `node --check`, prettier, `npm run build:deploy`, `git diff --check` 통과. 브랜치 `work/kangmina-share-tip`.

## 2026-10-21 그룹별 머리글 한 줄 소개 (추가 다듬기 2번) (담당: 강민아)

- `theme.html` `GROUP_DESC`(그룹 11개: 겨울·여름·가을·치안안심·건강·의료·육아·교육·생활편의·우수맛집·문화·여가·반려동물·교통) + `groupDesc(g)`. '전체' 보기의 목록 머리글이 "○○ 분야의 생활 시설을 한 지도에서 확인하세요" 대신 그룹별 문구로. 칩을 고르면 전처럼 테마의 `info`. 새 그룹을 만들면 여기에 한 줄 추가(없으면 옛 문구로 폴백).
- 문구는 초안 — 담당자·구리시가 고치면 `GROUP_DESC` 값만 바꾸면 됨.
- 검증: theme `node --check`, 그룹 목록과 문구 키 대조(누락 0), `npm run build:deploy`, `git diff --check` 통과. 브랜치 `work/kangmina-group-desc`.

## 2026-10-26 팝업 머리 정돈(추가 다듬기 3번) + 지도 위 떠 있는 요소 자리 통일(4번) (담당: 강민아)

- 팝업 머리(우리동네 찾기·3D 공통): 강조색 단색 배경·흰 글씨 → **흰 바탕 + 왼쪽 4px 색 띠 + 심볼 타일(40px, 연한 강조색)**, 분류는 강조색 11px, 이름은 검정 17px, 닫기는 회색 네모. 마크업 `.hd > .hd-ic + .hd-tx(.cat,.nm) + .close`(3D는 심볼 타일 없음). 전화·길찾기 단추 줄(`.btnstack/.btnrow/.btns`)은 `position:sticky; bottom`으로 카드 아래에 붙어 긴 팝업을 내려도 바로 누를 수 있음.
- 자리 규칙(데스크톱): **왼쪽 위 = 안내·팝업, 오른쪽 위 = 컨트롤(+건수 배지·지역 선택), 아래 = 막대·범례**. 우리동네 찾기 팝업을 왼쪽 아래 → 왼쪽 위로(3D 와 같게). 모바일은 전처럼 시트 위(아래쪽).
- 컨트롤 순서 통일: 확대·축소 ┃(칸 띄움 `.sep`)┃ (페이지 도구) → 내 위치 → **처음 화면** → 공유. 우리동네 찾기에 '처음 화면' 단추 추가(`resetView`), 항공의 '구리시 전체 보기'는 '처음 화면'으로 이름 통일.
- 모바일 컨트롤 위치는 페이지 구조상 다름(우리동네 찾기 오른쪽 위, 3D·항공 시트 위 오른쪽 아래) — 크기·순서만 같음.
- 검증: 지도 3쪽 `node --check`, Playwright(팝업 머리를 견본 내용으로 렌더: 데스크톱 테마·3D, 모바일 테마 — `pw/popup-shot.js`), `npm run build:deploy`, `git diff --check` 통과. 브랜치 `work/kangmina-popup-head`.

## 2026-10-26 메인: 계절 버튼 줄 → 사진 구석 계절 점, 그룹 목록 → 카드 (추가 다듬기 5·6번) (담당: 강민아)

- 히어로 아래 '구리의 사계절 | 자동·봄·여름·가을·겨울' 버튼 줄 제거. 대신 사진 오른쪽 아래 장소명 옆에 **계절 점 네 개**(`.season-badge > .season-place + .season-dots`, 각 계절 accentColor, 현재 계절은 흰 테두리). 누르면 그 계절 사진·추천으로 바뀜(`setSelection`). 기본은 전처럼 `SEASON_OVERRIDE`(겨울). 옛 `.season-controls` CSS 전부 제거.
- "어떤 곳을 찾고 계세요?" 그룹 8개를 가는 줄 목록에서 **카드 3열**로: 연한 그룹 색 바탕(5%)·테두리, 아이콘 타일 48px(그룹 색 13%), 이름 15px·요약, 오른쪽 화살표(hover 시 그룹 색). 모서리 `--ui-radius-lg`, hover 시 살짝 떠오름. ≤900px 2열, ≤620px 1열(모서리 10px).
- 전후: 스크래치 `hero-compare.png`, `disc-compare.png`, `disc-after-m.png`.
- 검증: `npx tsc --noEmit`, prettier, `npm run build:deploy`, `git diff --check` 통과. 브랜치 `work/kangmina-home-cards`.

## 2026-10-26 메인 '구리의 사계절' 줄 복원(자동·안내문 없이, 겨울 선택 표시) (담당: 강민아)

- 담당자 지시로 #107 의 계절 점 대신 사진 아래 '구리의 사계절 | 봄·여름·가을·겨울' 버튼 줄을 되돌림. '자동' 버튼과 "현재 계절을 보여드려요" 글은 뺌. 보이는 계절(기본 겨울)에 `aria-pressed`, 다른 계절을 누르면 그 계절 사진·추천(`setSelection`). `.season-controls{position:relative;z-index:1}` 로 사진 음영 위에 올려 눌림 보장. 장소명 배지는 전처럼.
- 검증: `npx tsc --noEmit`, prettier, `npm run build:deploy`, `git diff --check`; Playwright — 초기 겨울 선택·겨울 사진, 가을 클릭 시 가을 선택·한강시민공원 사진 확인. 브랜치 `work/kangmina-season-row`.

## 2026-10-26 작은 마무리: 연한 글자 대비 4.5:1, 빈 상태·로딩 톤 통일 (추가 다듬기 7번) (담당: 강민아)

- `site-shell.css` 토큰 `--ui-faint: #667570`(흰 바탕 4.6:1). 지도 4쪽의 `--faint`(옛 KRDS gray-40 ≈3.1:1)와 theme 의 gray-40 직접 사용(거리 단위·건수·팝업 라벨·빈 목록), 인라인 `#9AA6A0`·`#8A968F`, 공용 손잡이/공유창 안내 `#7c8a82`, 홈의 `#8eaa97·#96a397·#76847a·#708075·#758078`을 모두 이 토큰으로. 홈 일러스트 캡션 4색과 운영 배지 주황(`#B77410→#8C5A0A`, `#B26A00→#8A5200`)도 한 단계 진하게(연한 배경 기준 4.5:1 이상). 흰 글자·짙은 배경 위 글자는 그대로.
- 빈 상태·로딩 공통 모양 `.gm-empty`(둥근 돋보기 아이콘 `.gm-empty-ic` + 굵은 한 줄 + 설명) / `.gm-spin`(site-shell.css). 적용: 우리동네 찾기 빈 목록·오류 문구, 홈 테마 검색 결과 없음, 3D 로딩 상자(제목 15px·설명 faint·스피너 색 통일), 유기동물 빈 목록 색.
- 검증: 남은 4.5:1 미만 글자색은 짙은 배경 위(항공 로드뷰 패널) 뿐. `npx tsc --noEmit`, prettier, 지도 4쪽 `node --check`, 치안안심 하네스, `npm run build:deploy`, `git diff --check` 통과. 캡처 `empty-shot.png`(우리동네 찾기 빈 목록·3D 로딩·홈 검색 결과 없음). 브랜치 `work/kangmina-contrast-empty`.

## 2026-10-26 모바일: 계절 줄과 장소명 배지 겹침 해결, 지도 위 건수 배지 숨김 (담당: 강민아)

- 메인(≤620px): 사진 오른쪽 아래 장소명 배지(`.season-place`)가 '구리의 사계절' 줄의 겨울 버튼과 겹침 → 배지를 `bottom:70px` 로 계절 줄 위로. Playwright 로 겹침 없음 확인.
- 우리동네 찾기(≤900px): 지도 오른쪽 위 '시즌·겨울 · ○○ 0곳' 배지(`.locate-hint`) 숨김 — 칩에 건수가 있으므로. 데스크톱은 그대로.
- 검증: theme `node --check`, prettier, `npm run build:deploy`, `git diff --check` 통과. 브랜치 `work/kangmina-mobile-overlap`.

## 2026-10-26 전기차 충전소: 갱신 주기 10분으로, '확인 시각'과 '상태 변경 시각' 구분, 보고 있는 동안 배경 갱신 (담당: 강민아)

- 담당자: 포털 노트북 스케줄(구리시 전기차 상태갱신)을 10분 주기로 다시 만듦. 그런데 팝업에 "23분 전 확인 · 15분마다 갱신돼요"가 떠서 갱신이 안 되는 것처럼 보임.
- 원인 후보 둘: ① 레이어에 **수집 시각 항목**(`EV_SYNC_FIELDS`: 수집일시·수집시각·데이터수집일시·데이터갱신일시·갱신일시·sync_dt·collected_at)이 없으면 화면은 충전기 `상태갱신일시` 최댓값(= 가장 최근에 상태가 바뀐 시각)을 보여 줌 — 스케줄이 10분마다 돌아도 아무 충전기의 상태가 안 바뀌면 이 값은 그대로라 "23분 전"이 나올 수 있음(갱신 실패가 아님). ② 수집 시각 항목이 있는데도 오래됐다면 스케줄이 실제로 안 쓰고 있는 것. 개발 환경에선 레이어를 못 읽어 어느 쪽인지 확인 못 함 → 포털에서 레이어 항목에 수집일시류 항목이 있는지 보면 됨.
- 조치(`theme.html`): `EV_SYNC_EVERY_MIN=10`(문구·지연 기준 30분 모두 여기서), `evSyncKind()`로 시각 종류를 구분해 문구를 정확히 — 수집 시각이면 "n분 전 확인 · 10분마다 갱신돼요", 상태 변경 시각이면 "마지막 상태 변경 n분 전 · 상태는 10분마다 새로 받아요"(목록은 "상태 변경 n분 전"). 지연 경고(`evStale`)는 수집 시각이 있을 때만. 페이지를 보고 있는 동안 10분마다 전기차 자료를 조용히 다시 받음(`autoRefresh:true`, `loadGroupData(quiet)`, 자리표시 없음, 탭이 숨겨져 있으면 건너뜀).
- 권장(노트북): 갱신할 때 모든 행에 `수집일시`(KST, ISO 문자열 또는 날짜형)를 함께 쓰면 화면이 "n분 전 확인"으로 진짜 확인 시각을 보여 주고 지연 경고도 동작함.
- 검증: 하네스 `ev-when-test.js`(상태 시각/수집 시각 두 경우의 문구·지연 판단·상수), 치안안심 하네스(loadGroupData 서명 변경 반영), theme `node --check`, `npm run build:deploy`, `git diff --check` 통과. 브랜치 `work/kangmina-ev-sync`.

## 2026-10-26 전기차 '충전중 n시간째' 시각: 충전중시작 대신 마지막충전시작 우선, 미래·지난 세션 값은 버림 (담당: 강민아)

- 담당자 캡처(`life_evcharge_new` 데이터 탭)로 확인한 환경부 자료 특성: `마지막충전시작`(lastTsdt)은 `상태갱신일시`와 맞아떨어지는데, `충전중시작`(nowTsdt)은 ① 지난 세션 값이 남아 있거나(예: 어제 17:54, 종료 20:42보다 앞) ② 지금보다 9시간 앞선 미래 값(예: 22:25 — 시간대 변환이 두 번 적용된 꼴)이 섞여 있음. 화면의 "충전중 2일째/17시간째"는 이 값에서 나왔던 것.
- 조치(`theme.html` `evNowStart()`): 충전중일 때 `마지막충전시작` → 없으면 `충전중시작` 순으로 쓰되, 지금+5분보다 미래이거나 `마지막충전종료`보다 앞이면 버림(그러면 '몇 분째' 꼬리를 안 붙임).
- 노트북 쪽 확인 권장: nowTsdt 를 쓸 때 KST 변환을 한 번만(환경부 값은 이미 KST). 다만 화면은 이제 lastTsdt 를 쓰므로 급하지 않음.
- 검증: 하네스 `ev-nowt-test.js`(캡처 1·4행 꼴 등 5경우), `ev-when-test.js`, 치안안심 하네스, theme `node --check`, `npm run build:deploy`, `git diff --check` 통과. 브랜치 `work/kangmina-ev-nowt`.

## 2026-10-26 전기차 팝업: 상태 변경 시각 문구 제거, '충전중 n시간째' 계산 검토·강화 (담당: 강민아)

- 팝업의 "마지막 상태 변경 n분 전 · …"을 빼고 **"상태는 10분마다 새로 받아요"**만 표시(목록의 "상태 변경 n분 전"도 제거). 레이어에 수집 시각 항목이 생기면 전처럼 "n분 전 확인 · 10분마다 갱신돼요"로 자동 전환(`evWhenTxt`).
- '충전중 n시간째'가 갈수록 "며칠째"로 늘던 원인: 환경부 자료의 `충전중시작`/`마지막충전시작`이 세션이 바뀔 때 번갈아 갱신되지 않아 지난 세션 값이 남고, 화면은 그 값을 그대로 썼음. `evNowStart()` 규칙을 보강: ① 미래 값 버림 ② `마지막충전종료`보다 앞(지난 세션) 버림 ③ `상태갱신일시`보다 10분 넘게 뒤(그 상태와 무관) 버림 ④ 24시간 넘게 '충전중'(`EV_NOW_MAX_H`)이면 숨김 ⑤ 둘 다 맞으면 더 늦은 쪽. 못 믿을 값이면 '몇 분째'를 붙이지 않음 → "며칠째"는 더 안 나옴.
- 검증: 하네스 `ev-nowt-test.js`(캡처 줄 꼴 포함 9경우), `ev-when-test.js`, 치안안심 하네스, theme `node --check`, `npm run build:deploy`, `git diff --check` 통과. 브랜치 `work/kangmina-ev-wording`.

## 2026-10-26 팝업 맨 아래 안내 한 줄이 잘리던 것 수정 (담당: 강민아)

- 원인: 전화·길찾기 단추 묶음(`.btnstack`)을 카드 아래에 붙이면서(#106, `position:sticky`) 그 뒤에 오던 안내 한 줄(`.foot`, "운영시간은 등록 정보 기준…")이 단추 묶음에 가려짐.
- 조치: 안내 한 줄을 단추 묶음 안 맨 아래로 옮김(우리동네 찾기·3D 팝업). 단추와 함께 붙어 따라오며 항상 보임.
- 검증: 지도 2쪽 `node --check`, Playwright 견본 팝업(끝까지 스크롤) 캡처, `npm run build:deploy`, `git diff --check` 통과. 브랜치 `work/kangmina-popup-foot`.

## 2026-10-26 팝업 아래 단추 띠: 구분선 추가(잘린 듯 보이던 것) (담당: 강민아)

- 담당자 지적: 팝업 내용이 길어 스크롤될 때 아래에 붙는 단추 띠가 회색 정보 상자를 중간에서 덮어, 상자가 잘린 듯 보임. 의도한 모양이 아니라 붙박이 띠의 겹침.
- 조치: 단추 띠(`.btnstack` 등)에 위 구분선(1px)과 조금 더 또렷한 그림자를 주어 '아래에 붙은 띠'로 읽히게(우리동네 찾기·3D 공통).
- 검증: 지도 2쪽 `node --check`, Playwright 견본 팝업(스크롤 위쪽 상태) 캡처, `npm run build:deploy`, `git diff --check` 통과. 브랜치 `work/kangmina-popup-footbar`.

## 2026-10-26 팝업 단추 띠 제거, 전기차 칩 건수를 충전소 수로 (담당: 강민아)

- 팝업의 전화·길찾기 단추를 붙박이 띠(#106·#115)에서 되돌려 흐름대로 맨 아래에 둠(우리동네 찾기·3D). 담당자 요청: 띠처럼 보이는 게 싫음.
- 칩·'전체' 건수를 목록과 같은 기준으로: `countFor(t)` — `dedupeBy` 가 있는 테마는 대표 한 건씩만 센다. 전기차 칩이 충전기 1822대가 아니라 충전소 321곳으로 목록과 일치. 전체 합계도 같이 줄어듦.
- 검증: Playwright(가짜 자료: 충전소 2곳·충전기 6대) → 칩 '전기차 2', 목록 '2곳'; 지도 2쪽 `node --check`, `npm run build:deploy`, `git diff --check` 통과. 브랜치 `work/kangmina-ev-count`.

## 2026-10-26 오픈 준비 ①: 검토 위젯 스위치, 탭 제목 통일, 404 한글 페이지, robots·링크 미리보기 그림 (담당: 강민아)

- **검토용 "수정 요청" 위젯 스위치**: `src/config/site.config.ts` `features.reviewWidget` 한 곳. 오픈할 때 `false` 로 바꾸면 홈(`layout.tsx`)과 지도 4쪽(`<!-- shell:review -->` 표식, `scripts/sync-shell.mjs` 가 build:deploy 때 반영)에서 모두 빠진다. 지금은 `true`(검토 계속).
- **탭 제목 통일**: 지도 4쪽 모두 `<페이지> · 구리시 G-MAP`(우리동네 찾기만 "· 구리생활지도"였음). og:title 도 `구리시 G-MAP <페이지>` 로 통일, `<meta name="description">` 추가(유기동물 찾기에도).
- **404 페이지**(`src/app/not-found.tsx`, 정적 배포 `404.html`): 한글 안내 + 메인·우리동네 찾기 단추 + 문의 전화. ★ IIS 는 404 를 이 파일로 보내 주도록 서버 쪽 설정이 필요(web.config `httpErrors` 는 서버에서 잠겨 있으면 사이트 전체가 500 이 나므로 코드에 넣지 않음). 서버 관리자에게: `/app/guri` 사이트(또는 최종 도메인)의 오류 페이지 404 → `…/404.html` 실행 URL 로 지정.
- **robots.txt**(`public/robots.txt`): 전체 허용, `/review/` 만 제외.
- **링크 미리보기 그림**(og:image): 카톡·문자·SNS 에 링크를 보낼 때 뜨는 그림이 없었음 → 겨울 대표사진을 1200×630 `public/images/og-cover.jpg`(약 210KB)로 만들어 홈·지도 4쪽에 절대 주소로 넣음. 배포 origin 은 `scripts/build-deploy.mjs` 의 `origin`(→ `NEXT_PUBLIC_SITE_ORIGIN`, `src/config/paths.ts` `absUrl()`), 지도 4쪽은 빌드 때 치환. 도메인이 바뀌면 origin 만 바꾸면 된다(오픈 준비 ② 에서 한 곳으로 모음). 카톡은 미리보기를 캐시하므로 바뀐 그림이 바로 안 보일 수 있음.
- 검증: 위젯 스위치 on/off 둘 다 sync-shell 로 확인(off 면 script 가 주석으로), `npx tsc --noEmit`, prettier, `npm run build:deploy`(out 의 og:image 절대 주소·robots·404 확인), Playwright 404 페이지 데스크톱·모바일 캡처, `git diff --check` 통과. 브랜치 `work/kangmina-launch-prep`.

## 2026-10-26 오픈 준비 ②: 배포 주소 한 곳(deploy.config.json), 최종 도메인 전환 체크리스트 (담당: 강민아)

- **배포 주소 한 곳**: 루트의 `deploy.config.json` — `origin`(https://kgeodata.com)·`base`(/app/guri). `scripts/build-deploy.mjs` 가 읽어 홈 basePath, 지도 4쪽 경로 치환, og:image 절대 주소, `deployment.json` 의 `url` 까지 모두 맞춘다. 한 번만 다르게 빌드하려면 환경변수 `DEPLOY_ORIGIN` / `DEPLOY_BASE`. 사이트 루트에 두면 `base` 를 `""` 로(확인: `DEPLOY_ORIGIN=https://예시.go.kr DEPLOY_BASE= npm run build:deploy` → 모든 링크가 `/maps/…`, og:image 가 `https://예시.go.kr/images/…`).
- `scripts/deploy-iis.ps1`: 확인 URL 을 `deployment.json` 의 `url` 에서 읽고, 웹 폴더는 `-Target` 매개변수(기본값은 미리보기 서버 폴더). 최종 서버에선 워크플로의 호출만 `-Target 'D:\…'` 로 바꾸면 된다.
- **11월 최종 도메인 전환 체크리스트**(도메인 정해지면 순서대로):
  1. `deploy.config.json` 의 `origin`·`base` 수정 → 빌드 후 `out/deployment.json` 의 `url` 확인.
  2. 도메인 등록형 API 키 재등록(등록 안 된 도메인에서는 타일·로드뷰가 안 나옴):
     - 국토정보플랫폼 항공사진 `public/maps/aerial.html` `NGII.apiKey` — 오픈API 신청 도메인에 최종 도메인 추가(또는 새 키).
     - 브이월드 `public/maps/aerial.html` `VW.key` — 브이월드 인증키 관리에서 도메인 추가. (우리동네 찾기 `theme.html` 의 `vworldKey` 는 비어 있어 기본 지도를 쓰므로 해당 없음.)
     - 카카오 로드뷰 `public/maps/aerial.html` `KAKAO.jsKey` — 카카오 개발자 콘솔 > 플랫폼 > Web 사이트 도메인에 추가. (카톡 공유 `gmap-share.js` `KAKAO_JS_KEY` 는 비워 두기로 함 — 단추 숨김.)
  3. 서버: IIS 사이트(또는 가상 디렉터리)에 `out` 배포, 404 오류 페이지를 `404.html` 로 지정(오픈 준비 ① 참고), 워크플로 `guri-preview.yml` 의 러너·`-Target` 조정.
  4. 오픈 직전: `src/config/site.config.ts` `features.reviewWidget: false`(검토 위젯 제거), `npm run build:deploy` 후 지도 4쪽에 `review.js` 가 주석으로 바뀌었는지 확인.
  5. 카톡 미리보기(og:image)는 캐시가 남을 수 있음 — 카카오 공유 디버거에서 새로고침.
- 검증: 기본 빌드와 루트 도메인 덮어쓰기 빌드 둘 다 `npm run build:deploy` 통과(링크·og:image·deployment.json 확인), prettier, `git diff --check` 통과. 브랜치 `work/kangmina-deploy-config`.

## 2026-10-26 오픈 준비 ③: 우리동네 찾기 용량 718KB → 290KB (아이콘을 파일로) (담당: 강민아)

- `theme.html` 에 테마 아이콘 75개가 base64 로 내장돼(449KB) 모바일 첫 로딩이 무거웠음 → `public/maps/sym/theme/<키>.png`(72×72, 총 약 330KB, 브라우저가 캐시) 로 빼고, 페이지는 `SYM_FILES` 키 목록으로 주소만 만든다(`sym/theme/<키>.png`, 상대 경로라 배포 base 와 무관).
- 예외: `culture_dulle_fac`(둘레길 시설물)만 base64 유지 — 코스별 색을 입히는 `tintSym()` 이 SVG `<image>` 안에 그림을 넣는데, data URL 로 만든 SVG 는 외부 파일을 못 불러오기 때문.
- 새 아이콘 추가: png 를 저 폴더에 넣고 `SYM_FILES` 에 키만 추가(`scripts/winter-icons.py` 설명도 맞춤).
- 검증: theme `node --check`, Playwright(생활편의 가짜 자료: 칩 9개 아이콘 모두 로드, sym 요청 27건 전부 200, 목록·범례 아이콘 표시), 기존 하네스(칩 건수·치안안심·전기차 문구), `npm run build:deploy`, `git diff --check` 통과. 브랜치 `work/kangmina-theme-size`.
