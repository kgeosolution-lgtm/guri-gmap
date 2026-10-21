import {
  Sun,
  Leaf,
  Snowflake,
  ShieldCheck,
  Stethoscope,
  School,
  ShoppingBag,
  Utensils,
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
  /** true 면 홈 카드·검색에서 숨김 (theme.html 의 hidden 과 맞춘다) */
  hidden?: boolean;
}

/** theme.html 의 GROUPS 순서 그대로. 색은 theme.html 의 그룹 accent 와 같은 값(한 팔레트) — 바꾸면 둘 다 바꾼다. */
const themeGroupsAll: ThemeGroupItem[] = [
  {
    group: '시즌·여름',
    icon: Sun,
    color: '#2A7FA8',
    summary: '물놀이장·무더위쉼터·그늘막',
    hidden: true,
  },
  {
    group: '시즌·가을',
    icon: Leaf,
    color: '#A65A2E',
    summary: '축제·둘레길·등산로',
    hidden: true /* 2026-11 오픈은 겨울 시즌. 명소는 문화·여가로 옮김 */,
  },
  {
    group: '시즌·겨울',
    icon: Snowflake,
    color: '#35679A',
    summary: '한파쉼터·제설함·결빙취약구간',
  },
  { group: '치안안심', icon: ShieldCheck, color: '#B9473B', summary: 'CCTV·AED·안심귀갓길' },
  { group: '건강·의료', icon: Stethoscope, color: '#1E8A78', summary: '약국·병의원·예방접종' },
  {
    group: '육아·교육',
    icon: School,
    color: '#6F5FBF',
    summary: '어린이집·학교·도서관',
    hidden: true /* 이벤트성 지도로 분류되어 이번 구축 대상에서 제외(구리시, 2026-10). 다시 보이려면 이 줄과 theme.html 의 hidden 을 지운다 */,
  },
  { group: '생활편의', icon: ShoppingBag, color: '#4C5FAE', summary: '주차장·화장실·충전소' },
  { group: '우수맛집', icon: Utensils, color: '#B26331', summary: '와구리맛집·노포식당' },
  { group: '문화·여가', icon: Trees, color: '#4E7F3C', summary: '축제·명소·둘레길·공원' },
  { group: '반려동물', icon: PawPrint, color: '#B2507A', summary: '동물병원·유기동물' },
  { group: '교통', icon: Bus, color: '#58687B', summary: '버스정류장·공사·통제' },
];

/** 홈에 보이는 그룹. 비활성화(hidden) 그룹은 제외 */
export const themeGroups: ThemeGroupItem[] = themeGroupsAll.filter((g) => !g.hidden);
