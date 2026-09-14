import { basePath } from './paths';
export const siteConfig = {
  name: 'G-MAP',
  fullName: '구리시 시민생활지도',
  description: '구리 시민이 지금 필요한 생활정보를 지도에서 쉽게 찾는 사이트',
  /** 지도 페이지(theme.html, animal.html, aerial.html)가 놓인 기준 URL. public/maps 로 옮기면 값만 바꾼다. */
  mapsBase: process.env.NEXT_PUBLIC_MAPS_BASE ?? `${basePath}/maps`,
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
