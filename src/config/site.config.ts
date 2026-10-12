import { basePath } from './paths';
export const siteConfig = {
  name: 'G-MAP',
  fullName: '구리시 시민생활지도',
  description: '구리 시민이 지금 필요한 생활정보를 지도에서 쉽게 찾는 사이트',
  /** 지도 페이지(theme.html, animal.html, scene.html, aerial.html)가 놓인 기준 URL. public/maps 로 옮기면 값만 바꾼다. */
  mapsBase: process.env.NEXT_PUBLIC_MAPS_BASE ?? `${basePath}/maps`,
  /** 보이기 설정 — 구리시 요청(2026-10). 유기동물 찾기는 내년도 제작 예정 지도라 모든 메뉴·메인에서 숨긴다.
   *  내년에 서비스하면 animalMap 을 true 로만 바꾸면 메뉴·메인·추천 카드가 다시 보인다(지도 파일 maps/animal.html 은 그대로 배포됨). */
  features: { animalMap: false },
  nav: [
    { label: '생활지도', href: '#recommended' },
    { label: '공간정보', href: '#spatial' },
    { label: '도시계획·통계', href: '#urban' },
    { label: '열린데이터', href: '#open-data' },
    { label: '시민참여', href: '#participation' },
  ],
  contact: {
    department: '구리시 토지정보과',
    phone: '031-550-0000',
    address: '경기도 구리시 아차산로 439',
  },
};
