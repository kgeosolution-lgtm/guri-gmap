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

| 영역                      | 경로                                            |
| ------------------------- | ----------------------------------------------- |
| 새 홈·계절 선택·그룹 검색 | src/app/page.tsx                                |
| 새 홈 스타일              | src/app/service-home.css                        |
| React 헤더                | src/components/krds/SiteHeader.tsx              |
| 홈·지도 공용 헤더 스타일  | public/styles/site-shell.css                    |
| KRDS 토큰·폰트            | src/app/globals.css                             |
| 계절 이미지·문구          | src/config/season.config.ts                     |
| 그룹 색·아이콘·설명       | src/config/theme-groups.config.ts               |
| 지도 URL 헬퍼             | src/config/links.ts                             |
| 지도 기본 주소            | src/config/site.config.ts                       |
| 정적 지도 페이지          | public/maps/theme.html, public/maps/animal.html |
| 지도 공용 토큰            | public/maps/gmap-shared.css                     |

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

## 2026-09-11 전체보기 배율 고정·시즌·여름 비활성화

- 배율: 그룹 변경·동 전체 선택 시 `resetView`가 시작 화면(`INIT_VIEW`)으로 되돌리던 것을, 지도 크기에 맞춰 구리시 경계가 여백 10%로 들어오는 소수점 배율(`cityFit`)로 매번 계산하도록 바꿨습니다. 시작 화면도 같은 함수로 맞춥니다. `MapView`에 `snapToZoom:false`를 주어 소수점 배율이 정수(12)로 내려가 구리시가 작게 보이던 문제를 없앴습니다. `goTo` 전에 `view.when()`을 기다립니다.
- 시즌·여름 비활성화(코드 유지): theme.html 그룹에 `hidden:true`를 두고 `visibleGroups()`로 드롭다운 메뉴·기본 그룹에서 제외했습니다. `?group=시즌·여름` 직접 접근과 `cat` 파라미터 역탐색은 그대로 동작합니다. 홈은 `theme-groups.config.ts`에 `hidden` 플래그를 두고 `themeGroups`를 필터로 내보내 카드·검색에서 빠집니다. 헤더·푸터·지도 바로가기의 테마지도 링크는 `시즌·가을`로, 홈 "쉼터" 카드는 `안전·재난`(무더위·한파쉼터)으로 바꿨습니다. `season.config.ts`의 여름 계절 추천 항목은 여름 화면에서만 쓰이므로 그대로 두었습니다.
- 검증: 로컬 1280×800(지도 928×647)에서 시작·그룹 변경·동 전체 모두 배율 12.58로 일치, 그룹 메뉴 9개(여름 없음), 홈 카드에 여름 없음, 콘솔 오류 없음. `npm run build`, `build:deploy`, `tsc --noEmit`, prettier, `git diff --check` 통과. 개별 동 확대는 브라우저 패널이 숨김 상태라 애니메이션 `goTo`가 끝나지 않아 이 환경에서는 재확인하지 못했습니다(코드 변경 없음).
