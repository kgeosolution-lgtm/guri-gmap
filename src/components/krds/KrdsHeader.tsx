'use client';
import { useState } from 'react';
import { Search, Menu, X } from 'lucide-react';
import { siteConfig } from '@/config/site.config';
import { animalUrl, themeUrl } from '@/config/links';

const menu = [
  { label: '테마지도', href: themeUrl('여름') },
  { label: '유기동물 찾기', href: animalUrl() },
  { label: '소개', href: '#about' },
];

/** KRDS 헤더 (html/code/header.html 의 header-container + krds-main-menu 구조) */
export function KrdsHeader() {
  const [open, setOpen] = useState(false);
  return (
    <header id="krds-header">
      <div className="header-in">
        <div className="header-container">
          <div className="inner">
            <div className="header-branding">
              <h2 className="logo">
                <a href="/">
                  <img className="ci" src="/images/guri-ci.png" alt="구리시" height={32} />
                  <span>
                    <span className="logo-name">{siteConfig.name}</span>
                    <span className="logo-sub">{siteConfig.fullName}</span>
                  </span>
                </a>
              </h2>
              <div className="header-actions">
                <button type="button" className="btn-navi sch" title="통합검색은 준비 중이에요">
                  <Search className="ico" aria-hidden="true" />
                  통합검색
                </button>
                <button
                  type="button"
                  className="btn-navi all"
                  aria-controls="mobile-nav"
                  aria-expanded={open}
                  onClick={() => setOpen(!open)}
                >
                  {open ? (
                    <X className="ico" aria-hidden="true" />
                  ) : (
                    <Menu className="ico" aria-hidden="true" />
                  )}
                  {open ? '닫기' : '전체메뉴'}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* 메인메뉴 : 데스크탑 */}
        <nav className="krds-main-menu" aria-label="주 메뉴">
          <div className="inner">
            <ul className="gnb-menu">
              {menu.map((m) => (
                <li key={m.label}>
                  <a href={m.href} className="gnb-main-trigger is-link">
                    {m.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </nav>
      </div>

      {/* 메인메뉴 : 모바일 */}
      <div id="mobile-nav" className={`krds-main-menu-mobile${open ? ' is-open' : ''}`}>
        <nav className="gnb-wrap" aria-label="주 메뉴(모바일)">
          <div className="gnb-body">
            <div className="gnb-menu">
              <div className="menu-wrap">
                <ul>
                  {menu.map((m) => (
                    <li key={m.label}>
                      <a href={m.href} className="gnb-main-trigger" onClick={() => setOpen(false)}>
                        {m.label}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </nav>
      </div>
    </header>
  );
}
