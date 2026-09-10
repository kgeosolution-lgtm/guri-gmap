import type { LucideIcon } from 'lucide-react';
export type SeasonKey = 'spring' | 'summer' | 'autumn' | 'winter';
export interface CardItem {
  id: string;
  title: string;
  description: string;
  icon?: LucideIcon;
  badge?: string;
  image?: string;
  color?: string;
  portalItemId?: string | null;
  /** 연결된 지도 페이지 URL. 없으면(null/undefined) "준비중" 상태로 표시한다. */
  href?: string | null;
}
export interface LayerDefinition extends CardItem {
  icon: LucideIcon;
  type: 'feature' | 'scene' | 'webmap' | 'imagery' | 'mock';
  mockCount?: number;
}
