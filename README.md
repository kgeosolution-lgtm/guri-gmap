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
