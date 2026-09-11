import {
  Sun,
  Leaf,
  ShieldCheck,
  Stethoscope,
  School,
  ShoppingBag,
  Store,
  Trees,
  PawPrint,
  Bus,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import type { ThemeGroup } from './links';

export interface ThemeGroupItem {
  group: ThemeGroup;
  icon: LucideIcon;
  color: string;
  /** 그룹에 들어 있는 대표 테마 (theme.html GROUPS 기준) */
  summary: string;
}

/** theme.html 의 GROUPS 순서 그대로. 연한 배경 위 아이콘 색이라 원색을 쓴다(테마지도 accent 는 흰 글자 대비용 보정값). */
export const themeGroups: ThemeGroupItem[] = [
  { group: '시즌·여름', icon: Sun, color: '#1FA2DE', summary: '물놀이장·무더위쉼터·그늘막' },
  { group: '시즌·가을', icon: Leaf, color: '#C1652B', summary: '구리 명소·둘레길·등산로' },
  { group: '안전·재난', icon: ShieldCheck, color: '#E5533C', summary: '대피소·AED·CCTV' },
  { group: '건강·의료', icon: Stethoscope, color: '#2E9E5B', summary: '약국·병의원·예방접종' },
  { group: '육아·교육', icon: School, color: '#7A6FE0', summary: '어린이집·학교·도서관' },
  { group: '생활편의', icon: ShoppingBag, color: '#2F6FE4', summary: '주차장·화장실·충전소' },
  { group: '경제·상권', icon: Store, color: '#C75A24', summary: '모범음식점·시장·맛집' },
  { group: '문화·여가', icon: Trees, color: '#01A774', summary: '둘레길·공원·축제' },
  { group: '반려동물', icon: PawPrint, color: '#F0608A', summary: '동물병원·유기동물' },
  { group: '교통', icon: Bus, color: '#5B6C7E', summary: '버스정류장·공사·통제' },
];
