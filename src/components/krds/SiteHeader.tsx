'use client';
import { homeUrl } from '@/config/paths';
import { animalUrl, themeUrl } from '@/config/links';
export function SiteHeader({
  variant = 'home',
  pageName,
  active,
}: {
  variant?: 'home' | 'map';
  pageName?: string;
  active?: string;
}) {
  const links = [
    { label: '테마지도', href: themeUrl('시즌·가을') },
    { label: '유기동물 찾기', href: animalUrl() },
    { label: 'G-MAP 소개', href: homeUrl('#about') },
  ];
  const navigation = links.map((link) => (
    <a key={link.label} href={link.href} aria-current={active === link.label ? 'page' : undefined}>
      {link.label}
    </a>
  ));
  return (
    <header className={`service-header ${variant === 'map' ? 'map topbar' : 'home'}`}>
      <div className="service-header-inner">
        <a className="service-brand" href={homeUrl()} aria-label="G-MAP 구리시 시민생활지도 홈">
          <img src="/images/guri-emblem.png" alt="" width="50" height="41" />
          <span>
            <b>G-MAP</b>
            <small>구리시 시민생활지도</small>
          </span>
        </a>
        {pageName && <span className="service-page-name">{pageName}</span>}
        <nav className="service-nav" aria-label="주 메뉴">
          {navigation}
        </nav>
        <a className="service-search" href={homeUrl('#search')}>
          테마 찾기 <span aria-hidden="true">↗</span>
        </a>
        <details
          className="service-mobile"
          onKeyDown={(e) => {
            if (e.key === 'Escape') {
              e.currentTarget.open = false;
              e.currentTarget.querySelector('summary')?.focus();
            }
          }}
        >
          <summary aria-label="메뉴 열기·닫기">
            <span />
            <span />
          </summary>
          <nav
            aria-label="모바일 주 메뉴"
            onClick={(e) => {
              if ((e.target as HTMLElement).closest('a'))
                e.currentTarget.closest('details')?.removeAttribute('open');
            }}
          >
            {navigation}
            <a href={homeUrl('#search')}>테마 찾기</a>
          </nav>
        </details>
      </div>
    </header>
  );
}
