'use client';
import { useState } from 'react';
import { Menu, Search, X, MapPinned, ChevronDown, Instagram, Youtube } from 'lucide-react';
import { siteConfig } from '@/config/site.config';
import { Container } from './ui';
export function Header() {
  const [open, setOpen] = useState(false);
  return (
    <header className="relative z-50 border-b border-white/10 bg-white">
      <Container className="flex h-[72px] items-center justify-between lg:h-[82px]">
        <a href="#" className="flex items-center gap-2">
          <span className="grid h-10 w-10 place-items-center rounded-[14px] bg-[#13A376] text-white shadow-lg shadow-emerald-200">
            <MapPinned size={22} />
          </span>
          <span>
            <strong className="block text-xl leading-none tracking-tight text-[#163B31]">
              G-MAP
            </strong>
            <small className="hidden text-[10px] font-semibold tracking-tight text-slate-500 sm:block">
              구리시 시민생활지도
            </small>
          </span>
        </a>
        <nav className="hidden items-center gap-8 lg:flex">
          {siteConfig.nav.map((x) => (
            <a
              key={x.href}
              href={x.href}
              className="text-[15px] font-bold text-slate-700 transition hover:text-[var(--accent)]"
            >
              {x.label}
            </a>
          ))}
        </nav>
        <div className="flex items-center gap-1">
          <button
            aria-label="검색"
            className="grid h-10 w-10 place-items-center rounded-full hover:bg-slate-100"
          >
            <Search size={20} />
          </button>
          <button className="hidden items-center gap-1 rounded-full bg-[#173E34] px-4 py-2.5 text-sm font-bold text-white sm:flex">
            전체메뉴
            <ChevronDown size={14} />
          </button>
          <button
            onClick={() => setOpen(!open)}
            aria-label="메뉴"
            className="grid h-10 w-10 place-items-center lg:hidden"
          >
            {open ? <X /> : <Menu />}
          </button>
        </div>
      </Container>
      {open && (
        <nav className="absolute inset-x-0 top-full border-t bg-white p-5 shadow-xl lg:hidden">
          {siteConfig.nav.map((x) => (
            <a
              key={x.href}
              onClick={() => setOpen(false)}
              href={x.href}
              className="block border-b border-slate-100 py-4 font-bold"
            >
              {x.label}
            </a>
          ))}
        </nav>
      )}
    </header>
  );
}
export function Footer() {
  return (
    <footer className="bg-[#142D28] py-12 text-white/70">
      <Container>
        <div className="flex flex-col justify-between gap-8 md:flex-row">
          <div>
            <div className="mb-4 flex items-center gap-2 text-white">
              <MapPinned />
              <strong className="text-xl">G-MAP</strong>
              <span className="text-sm">구리시 시민생활지도</span>
            </div>
            <p className="text-sm leading-7">
              {siteConfig.contact.address}
              <br />
              {siteConfig.contact.department} · {siteConfig.contact.phone}
            </p>
          </div>
          <div className="flex flex-wrap items-start gap-6 text-sm">
            <a href="#">이용안내</a>
            <a href="#" className="font-bold text-white">
              개인정보처리방침
            </a>
            <a href="#">저작권정책</a>
            <a href="#">사이트맵</a>
            <Instagram size={18} />
            <Youtube size={20} />
          </div>
        </div>
        <div className="mt-9 border-t border-white/10 pt-6 text-xs text-white/40">
          COPYRIGHT © GURI CITY. ALL RIGHTS RESERVED.
        </div>
      </Container>
    </footer>
  );
}
