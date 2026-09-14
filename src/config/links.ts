import { siteConfig } from './site.config';

/** theme.html 의 GROUPS 키와 동일해야 한다. (2026-09-10 kgeodata.com/guri/theme.html 기준) */
export type ThemeGroup =
  | '여름'
  | '안전·재난'
  | '건강·의료'
  | '육아·교육'
  | '생활편의'
  | '경제·상권'
  | '문화·여가'
  | '반려동물'
  | '교통';

export function themeUrl(group: ThemeGroup): string {
  return `${siteConfig.mapsBase}/theme.html?group=${encodeURIComponent(group)}`;
}

export function animalUrl(): string {
  return `${siteConfig.mapsBase}/animal.html`;
}

export function aerialUrl(): string {
  return `${siteConfig.mapsBase}/aerial.html`;
}
