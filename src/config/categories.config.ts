import {
  Heart,
  ShieldCheck,
  Stethoscope,
  Trees,
  MapPinned,
  Building2,
  Pill,
  ParkingCircle,
  Accessibility,
  BatteryCharging,
  Bath,
  CircleDot,
  Users,
  Store,
  FileSearch,
  LandPlot,
  Construction,
  Database,
  MessageCircle,
  Lightbulb,
  Map,
  Footprints,
  Utensils,
  Cross,
  PawPrint,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import type { CardItem } from '@/types/content';
import { animalUrl, themeUrl } from './links';

export interface QuickCategory {
  id: string;
  label: string;
  icon: LucideIcon;
  color: string;
  href?: string | null;
}
export type LinkedCard = CardItem & { icon: LucideIcon; color: string };

/** 히어로 하단 6개 카테고리. 관광·부동산은 대응 그룹이 없어 준비중. */
export const quickCategories: QuickCategory[] = [
  { id: 'life', label: '생활', icon: Heart, color: '#F06B72', href: themeUrl('생활편의') },
  { id: 'safety', label: '안전', icon: ShieldCheck, color: '#E66E36', href: themeUrl('안전·재난') },
  { id: 'health', label: '건강', icon: Stethoscope, color: '#15A58C', href: themeUrl('건강·의료') },
  { id: 'leisure', label: '여가', icon: Trees, color: '#4B8D63', href: themeUrl('문화·여가') },
  { id: 'tour', label: '관광', icon: MapPinned, color: '#4983CF', href: null },
  { id: 'estate', label: '부동산', icon: Building2, color: '#785DC1', href: null },
];
export const quickFinder: LinkedCard[] = [
  {
    id: 'pharmacy',
    title: '약국',
    description: '운영 중인 약국',
    icon: Pill,
    color: '#F05474',
    href: themeUrl('건강·의료'),
  },
  {
    id: 'shelter',
    title: '쉼터',
    description: '가까운 안전쉼터',
    icon: Accessibility,
    color: '#5A7AE6',
    href: themeUrl('안전·재난'),
  },
  {
    id: 'parking',
    title: '주차장',
    description: '공영주차장 정보',
    icon: ParkingCircle,
    color: '#3769C8',
    href: themeUrl('생활편의'),
  },
  {
    id: 'toilet',
    title: '화장실',
    description: '공중화장실',
    icon: Bath,
    color: '#19A0A8',
    href: themeUrl('생활편의'),
  },
  {
    id: 'ev',
    title: '전기차 충전소',
    description: '충전소 위치',
    icon: BatteryCharging,
    color: '#18A86B',
    href: themeUrl('생활편의'),
  },
  {
    id: 'aed',
    title: 'AED',
    description: '자동심장충격기',
    icon: CircleDot,
    color: '#E85145',
    href: null,
  },
];
export const recommendedMaps: LinkedCard[] = [
  {
    id: 'facility',
    title: '우리동네 편의시설',
    description: '생활 반경 안의 공공·편의시설을 한눈에',
    icon: Map,
    color: '#386FE8',
    href: themeUrl('생활편의'),
  },
  {
    id: 'walk',
    title: '걷기 좋은 구리',
    description: '공원과 산책로를 잇는 추천 걷기 코스',
    icon: Footprints,
    color: '#2BA66D',
    href: themeUrl('문화·여가'),
  },
  {
    id: 'safe',
    title: '시민안전 생활지도',
    description: '안전시설과 재난대피 정보를 가까이',
    icon: ShieldCheck,
    color: '#F26E47',
    href: themeUrl('안전·재난'),
  },
  {
    id: 'food',
    title: '우수맛집 지도',
    description: '구리가 인증한 맛있는 가게 찾기',
    icon: Utensils,
    color: '#E25563',
    href: themeUrl('경제·상권'),
  },
  {
    id: 'life',
    title: '생명존중 지도',
    description: '마음건강 상담과 생명안전 시설 정보',
    icon: Cross,
    color: '#845AC7',
    href: themeUrl('건강·의료'),
  },
  {
    id: 'animal',
    title: '유기동물 찾기',
    description: '보호 중인 아이들을 지도에서 찾아보세요',
    icon: PawPrint,
    color: '#F5820D',
    href: animalUrl(),
  },
];
export const urbanStats = [
  { id: 'population', title: '동네 인구구조', description: '연령·세대별 인구', icon: Users },
  { id: 'business', title: '상권 통계', description: '업종과 유동인구', icon: Store },
  { id: 'parcel', title: '일필지 조회', description: '필지별 토지정보', icon: FileSearch },
  { id: 'landuse', title: '토지이용현황', description: '용도지역·지구', icon: LandPlot },
  { id: 'development', title: '개발구역현황', description: '도시개발 사업', icon: Construction },
];
export const participation = [
  { title: '시민 지도 제안', description: '생활에 필요한 지도를 제안해 주세요', icon: Lightbulb },
  {
    title: '공간정보 오류 신고',
    description: '잘못된 지도 정보를 알려 주세요',
    icon: MessageCircle,
  },
  { title: '공공데이터 신청', description: '필요한 데이터를 요청해 주세요', icon: Database },
];
