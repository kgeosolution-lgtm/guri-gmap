import type { SeasonKey } from '@/types/content';
import { themeUrl } from './links';
export interface FeaturedItem {
  title: string;
  /** 연결된 지도 페이지. null 이면 준비중. */
  href: string | null;
}
export interface SeasonTheme {
  key: SeasonKey;
  label: string;
  heroImage: string;
  /** 사진 장소 — 히어로 오른쪽 아래 작은 글씨 */
  place: string;
  backgroundColor: string;
  accentColor: string;
  accentSoft: string;
  titleColor: string;
  eyebrow: string;
  featuredItems: FeaturedItem[];
}
export const seasonConfig: Record<SeasonKey, SeasonTheme> = {
  spring: {
    key: 'spring',
    label: '봄',
    heroImage: '/images/hero-spring.webp',
    place: '장자호수공원',
    backgroundColor: '#F7ECEE',
    accentColor: '#E65F80',
    accentSoft: '#FFF0F4',
    titleColor: '#18382E',
    eyebrow: '꽃처럼 피어나는 구리의 봄',
    featuredItems: [
      { title: '한강시민공원 봄 산책', href: null },
      { title: '구리 유채꽃 명소', href: null },
      { title: '아이와 가기 좋은 공원', href: null },
      { title: '봄철 미세먼지 정보', href: null },
      { title: '주말 문화행사', href: null },
    ],
  },
  summer: {
    key: 'summer',
    label: '여름',
    heroImage: '/images/hero-summer.webp',
    place: '이문안호수공원',
    backgroundColor: '#E6F4F3',
    accentColor: '#2A7FA8', // = theme.html 시즌·여름 accent
    accentSoft: '#E8F8F4',
    titleColor: '#083D43',
    eyebrow: '초록과 강바람이 반가운 여름',
    featuredItems: [
      { title: '한강 물놀이 쉼터', href: themeUrl('시즌·여름') },
      { title: '시원한 실내 문화공간', href: themeUrl('시즌·여름') },
      { title: '무더위 쉼터 찾기', href: themeUrl('시즌·여름') },
      { title: '여름철 안전 정보', href: themeUrl('시즌·여름') },
      { title: '야간 산책 코스', href: themeUrl('시즌·여름') },
    ],
  },
  autumn: {
    key: 'autumn',
    label: '가을',
    heroImage: '/images/hero-autumn.webp',
    place: '한강시민공원',
    backgroundColor: '#F7EBDD',
    accentColor: '#A65A2E', // = theme.html 시즌·가을 accent
    accentSoft: '#FFF1E8',
    titleColor: '#472B20',
    eyebrow: '천천히 걷고 싶은 구리의 가을',
    featuredItems: [
      { title: '아차산 단풍 산책', href: themeUrl('문화·여가') },
      { title: '구리 코스모스 축제', href: null },
      { title: '가을 문화행사', href: null },
      { title: '우리동네 전통시장', href: null },
      { title: '자전거 추천 코스', href: null },
    ],
  },
  winter: {
    key: 'winter',
    label: '겨울',
    heroImage: '/images/hero-winter.webp',
    place: '동구릉',
    backgroundColor: '#E8F0FA',
    accentColor: '#35679A', // = theme.html 시즌·겨울 accent
    accentSoft: '#EDF5FF',
    titleColor: '#173B61',
    eyebrow: '포근한 일상을 잇는 구리의 겨울',
    featuredItems: [
      { title: '한파쉼터 찾기', href: themeUrl('시즌·겨울') },
      { title: '우리 동네 제설함', href: themeUrl('시즌·겨울') },
      { title: '결빙취약구간 확인', href: themeUrl('시즌·겨울') },
      { title: '겨울 둘레길·등산로', href: themeUrl('시즌·겨울') },
      { title: '연말 문화행사', href: themeUrl('문화·여가') },
    ],
  },
};
/** 메인에 보여 줄 계절. 'auto' 면 날짜로 정하고, 계절 이름을 적으면 그 계절로 고정한다(2026-11 오픈은 겨울 사진·추천으로). */
export const SEASON_OVERRIDE: SeasonKey | 'auto' = 'winter';
export function getAutoSeason(date = new Date()): SeasonKey {
  if (SEASON_OVERRIDE !== 'auto') return SEASON_OVERRIDE;
  const m = date.getMonth() + 1;
  if (m >= 3 && m <= 5) return 'spring';
  if (m >= 6 && m <= 8) return 'summer';
  if (m >= 9 && m <= 11) return 'autumn';
  return 'winter';
}
