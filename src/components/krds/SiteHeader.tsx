'use client';
import { useState } from 'react';
import { Search, Menu, X } from 'lucide-react';
import { siteConfig } from '@/config/site.config';
import { aerialUrl, animalUrl, themeUrl } from '@/config/links';

const menu = [
  { label: '테마지도', href: themeUrl('여름') },
  { label: '유기동물 찾기', href: animalUrl() },
  { label: '시계열 항공사진', href: aerialUrl() },
  { label: '소개', href: '#about' },
];

/** 브랜드 락업: 엠블럼 + G-MAP(와구리체) + 구리시 시민생활지도. 홈·지도 페이지 공통 */
function Brand() {
  return (
    <a className="brand" href="/" title="G-MAP 홈으로">
      <img className="emblem" src="/images/guri-emblem.png" alt="구리시" width={50} height={41} />
      <span className="txt">
        <span className="name">{siteConfig.name}</span>
        <span className="sub">{siteConfig.fullName}</span>
      </span>
    </a>
  );
}

/**
 * 사이트 헤더.
 * - variant="home": 64px, 가운데 메뉴, 오른쪽 검색 아이콘. 모바일(≤768px)은 락업 + 햄버거 → 드로어.
 * - variant="map":  56px, 락업 옆 페이지명.
 *   로고가 홈 링크라 "메인으로" 버튼은 두지 않는다. map 변형의 마크업·CSS는 public/maps/gmap-shared.css 의 .topbar 와 동일하다(픽셀 단위 일치).
 */
export function SiteHeader({
  variant = 'home',
  pageName,
  active,
}: {
  variant?: 'home' | 'map';
  pageName?: string;
  active?: string;
}) {
  const [open, setOpen] = useState(false);

  if (variant === 'map') {
    return (
      <header className="site-header map topbar">
        <div className="inner">
          <Brand />
          {pageName && <span className="page-name">· {pageName}</span>}
        </div>
      </header>
    );
  }

  return (
    <header className="site-header home">
      <div className="inner">
        <Brand />
        <nav className="nav" aria-label="주 메뉴">
          {menu.map((m) => (
            <a key={m.label} href={m.href} className={m.label === active ? 'active' : undefined}>
              {m.label}
            </a>
          ))}
        </nav>
        <div className="actions">
          <button type="button" className="hd-btn search" title="통합검색은 준비 중이에요">
            <Search size={20} aria-hidden="true" />
            <span className="sr-only">통합검색</span>
          </button>
          <button
            type="button"
            className="hd-btn menu-btn"
            aria-controls="site-drawer"
            aria-expanded={open}
            onClick={() => setOpen(true)}
          >
            <Menu size={22} aria-hidden="true" />
            <span className="sr-only">전체메뉴 열기</span>
          </button>
        </div>
      </div>

      {/* 모바일 드로어 */}
      <div id="site-drawer" className={`drawer${open ? ' open' : ''}`} aria-hidden={!open}>
        <div className="dim" onClick={() => setOpen(false)} />
        <nav className="sheet" aria-label="주 메뉴(모바일)">
          <div className="sheet-head">
            <Brand />
            <button type="button" className="hd-btn" onClick={() => setOpen(false)}>
              <X size={22} aria-hidden="true" />
              <span className="sr-only">닫기</span>
            </button>
          </div>
          {menu.map((m) => (
            <a
              key={m.label}
              href={m.href}
              className={m.label === active ? 'active' : undefined}
              onClick={() => setOpen(false)}
            >
              {m.label}
            </a>
          ))}
        </nav>
      </div>
    </header>
  );
}
