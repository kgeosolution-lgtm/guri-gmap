# 구리시 G-MAP 시민생활지도 — PHASE 1

ArcGIS Enterprise 연결 전 단계의 반응형 프론트엔드 프로토타입입니다.

```bash
npm install
npm run dev
```

## 구조

- `src/config`: 사이트·계절·카테고리·레이어·추천·외부 서비스 데이터
- `src/components`: 페이지 섹션별 재사용 컴포넌트
- `public/images`: 봄·여름·가을·겨울 Hero 자산
- `layers.config.ts`: PHASE 2에서 `portalItemId`를 등록할 ArcGIS 연결 지점

계절은 현재 날짜를 기준으로 자동 선택됩니다. 우측 하단 도구에서 강제로 전환할 수 있으며, 운영 환경에서는 `NEXT_PUBLIC_SHOW_THEME_TOOLBAR=false`로 숨길 수 있습니다.

## KRDS 적용 방식

홈은 [KRDS(대한민국 디지털 정부서비스 UI/UX 가이드라인)](https://www.krds.go.kr) 기반으로 구성했고, 이전 홈은 `/v1` 에 그대로 남아 있습니다.

- **토큰**: `krds-uiux` 패키지의 `krds_tokens.css` 를 `globals.css` 에서 import 합니다. KRDS 토큰은 html 10px 기준 rem 이라, 이 프로젝트(Tailwind 16px 기준)에서 같은 픽셀값이 나오도록 number·font-size 토큰만 px 로 덮어썼습니다. `tailwind.config.ts` 의 `primary/secondary/gray/danger/warning/success/info/point` 색과 `krds-*` 간격·라운드·그림자는 모두 이 토큰 변수를 가리킵니다.
- **확장형 primary**: 구리시 초록 `#018058` 을 50단계로 두고, KRDS 기본 primary(블루)의 단계별 OKLCH 명도 곡선을 유지한 채 색상·채도만 바꿔 5~95 팔레트를 만들어 `--krds-color-light-primary-*` 를 덮어썼습니다. 60단계는 버튼 호버 `#01573C`. 명도 대비는 KRDS 매직넘버 기준으로 50단계 vs 흰색 4.96:1(4.5:1 이상), 40단계 vs 흰색 3.23:1(3:1 이상) 입니다.
- **서체**: `public/fonts` 의 Pretendard GOV(Regular/Medium/Bold, woff2) 를 `@font-face` 로 선언해 본문 기본 서체로 씁니다.
- **컴포넌트**: 마스트헤드·건너뛰기 링크·헤더·푸터·기관 식별자·버튼·태그는 KRDS HTML 컴포넌트 키트의 마크업 구조(`#krds-masthead`, `#krds-header`, `#krds-footer`, `.krds-btn`, `.krds-btn-tag` …)를 따르되, 540KB 짜리 컴포넌트 CSS 를 통째로 넣지 않고 필요한 규칙만 토큰 기반으로 `globals.css` 에 구현했습니다. 다크모드·고대비 모드는 아직 적용하지 않았습니다.

## 공동 작업

- 각자 별도로 clone한 폴더를 사용합니다. 같은 폴더를 여러 편집 도구나 에이전트가 동시에 수정하지 않습니다.
- 작업 시작 전 `git status`와 `git fetch origin`으로 변경 여부를 확인합니다. 깨끗한 main에서 `git pull --ff-only origin main` 후 `git switch -c 작업브랜치명`으로 작업별 브랜치를 만듭니다.
- 커밋 전 diff를 검토하고 변경에 맞는 검사와 `npm run build`를 실행합니다. 본인 작업 파일만 지정해 stage합니다.
- 작업 브랜치를 push하고 GitHub Pull Request로 검토·병합합니다. main 강제 push와 다른 사람의 변경을 덮어쓰는 reset은 하지 않습니다.
- 원격 변경과 이력이 갈라졌으면 자동으로 밀어 넣지 않고 차이를 확인해 작업 브랜치에서 충돌을 해결합니다.
- 각 clone에서 `git config --local pull.ff only`를 설정하면 실수로 pull 병합 커밋을 만드는 것을 막을 수 있습니다. 이는 GitHub 브랜치 보호 설정을 대신하지 않습니다.
- 로컬 개발 화면과 운영 배포본은 별개입니다. 운영 반영 여부는 따로 확인합니다.

### 2026-09-11 홈·공통 헤더 개편

홈은 기존 사계절 이미지를 전체 배경으로 유지하고 자동/수동 계절 선택, 테마 그룹 검색, 유기동물 안내, 이용 안내로 구성합니다. 기존 컴포넌트와 `/v1`은 보존합니다. `public/styles/site-shell.css`를 홈과 정적 지도 페이지가 함께 사용합니다. 지도 헤더는 기존 높이 57px(테두리 포함)를 유지하며 지도 조회·필터·렌더 스크립트는 수정하지 않았습니다. 모바일 메뉴는 네이티브 details를 사용하고, 홈에서는 Escape 닫기와 링크 선택 후 닫기를 추가했습니다. 애니메이션은 계절 배경 전환, 첫 화면 등장, 메뉴 및 링크 반응에 적용하며 `prefers-reduced-motion`을 존중합니다.

검증: `npm run build`, `npx prettier --check src public/styles/site-shell.css` 통과. 홈·테마지도·유기동물 페이지 PC 1280px / 모바일 390px 육안 점검 및 콘솔 오류 없음. 홈 검색(약국/건강·의료/일치 없음), 전체 복원, 계절 수동 전환, 모바일 메뉴를 확인했습니다. 데이터 전체 정확성이나 운영 서버 반영을 검증한 것은 아닙니다. 계절 배경은 기존 이미지 자산을 그대로 사용합니다.

## 팀원·Claude 인수인계

최신 디자인 브랜치, 실행 명령, 직원별 Git 작업 절차, Claude에 붙여 넣을 지시서는 [팀 협업 및 Claude 인수인계](docs/TEAM_HANDOFF.md)를 확인하세요. 현재 디자인은 `design/service-home-refresh`에 있으며 main 병합 전입니다.
