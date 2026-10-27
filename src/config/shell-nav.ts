import nav from './shell-nav.json';
import { homeUrl } from './paths';
import { siteConfig } from './site.config';
import { aerialUrl, animalUrl, sceneUrl, themeUrl } from './links';
import type { ThemeGroup } from './links';

export interface ShellLink {
  label: string;
  href: string;
  external?: boolean;
}
type Raw = {
  label: string;
  kind: 'theme' | 'animal' | 'scene' | 'aerial' | 'external' | 'home';
  group?: string;
  feature?: 'animalMap' | 'newsHub';
  href?: string;
  hash?: string;
};

/** 헤더·푸터 공용 메뉴 — shell-nav.json 을 실제 주소로 푼다. 숨긴 기능(features)은 뺀다 */
export function shellLinks(): ShellLink[] {
  return (nav.links as Raw[])
    .filter((l) => !l.feature || siteConfig.features[l.feature])
    .map((l) => {
      switch (l.kind) {
        case 'theme':
          return { label: l.label, href: themeUrl(l.group as ThemeGroup) };
        case 'animal':
          return { label: l.label, href: animalUrl() };
        case 'scene':
          return { label: l.label, href: sceneUrl() };
        case 'aerial':
          return { label: l.label, href: aerialUrl() };
        case 'external':
          return { label: l.label, href: l.href || '#', external: true };
        default:
          return { label: l.label, href: homeUrl(l.hash || '') };
      }
    });
}
export const shellSearch = { label: nav.search.label, href: () => homeUrl(nav.search.hash) };
