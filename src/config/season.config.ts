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
    backgroundColor: '#E6F4F3',
    accentColor: '#078C78',
    accentSoft: '#E8F8F4',
    titleColor: '#083D43',
    eyebrow: '초록과 강바람이 반가운 여름',
    featuredItems: [
      { title: '한강 물놀이 쉼터', href: themeUrl('여름') },
      { title: '시원한 실내 문화공간', href: themeUrl('여름') },
      { title: '무더위 쉼터 찾기', href: themeUrl('여름') },
      { title: '여름철 안전 정보', href: themeUrl('여름') },
      { title: '야간 산책 코스', href: themeUrl('여름') },
    ],
  },
  autumn: {
    key: 'autumn',
    label: '가을',
    heroImage: '/images/hero-autumn.webp',
    backgroundColor: '#F7EBDD',
    accentColor: '#C75A24',
    accentSoft: '#FFF1E8',
    titleColor: '#472B20',
    eyebrow: '천천히 걷고 싶은 구리의 가을',
    featuredItems: [
      { title: '아차산 단풍 산책', href: null },
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
    backgroundColor: '#E8F0FA',
    accentColor: '#3B6FA9',
    accentSoft: '#EDF5FF',
    titleColor: '#173B61',
    eyebrow: '포근한 일상을 잇는 구리의 겨울',
    featuredItems: [
      { title: '제설 현황 안내', href: null },
      { title: '한파 쉼터 찾기', href: null },
      { title: '겨울철 안전 정보', href: null },
      { title: '따뜻한 실내 나들이', href: null },
      { title: '연말 문화행사', href: null },
    ],
  },
};
export function getAutoSeason(date = new Date()): SeasonKey {
  const m = date.getMonth() + 1;
  if (m >= 3 && m <= 5) return 'spring';
  if (m >= 6 && m <= 8) return 'summer';
  if (m >= 9 && m <= 11) return 'autumn';
  return 'winter';
}
