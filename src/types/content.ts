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
}
export interface LayerDefinition extends CardItem {
  icon: LucideIcon;
  type: 'feature' | 'scene' | 'webmap' | 'imagery' | 'mock';
  mockCount?: number;
}
