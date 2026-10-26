'use client';
import { useEffect, useState } from 'react';
import {
  ArrowUpRight,
  ArrowUp,
  Search,
  PawPrint,
  MapPin,
  Layers,
  Compass,
  ArrowRight,
} from 'lucide-react';
import { themeGroups } from '@/config/theme-groups.config';
import { themeUrl, animalUrl, sceneUrl, aerialUrl } from '@/config/links';
import { shellLinks } from '@/config/shell-nav';
import { TimeLapseArt } from '@/components/TimeLapseArt';
import { SkylineArt } from '@/components/SkylineArt';
import { NewsArt } from '@/components/NewsArt';
import { SiteHeader } from '@/components/krds/SiteHeader';
import { SkipLink, Masthead } from '@/components/krds/Masthead';
import { siteConfig } from '@/config/site.config';
import { getAutoSeason, seasonConfig } from '@/config/season.config';
import type { SeasonKey } from '@/types/content';
import './service-home.css';
/** 푸터 '지도 바로가기' — 헤더와 같은 메뉴(src/config/shell-nav.json) */
const footerLinks = shellLinks();
export default function Home() {
  const [query, setQuery] = useState('');
  const [selection, setSelection] = useState<'auto' | SeasonKey>('auto');
  const [automatic, setAutomatic] = useState<SeasonKey>('summer');
  useEffect(() => setAutomatic(getAutoSeason()), []);
  const season = seasonConfig[selection === 'auto' ? automatic : selection];
  const groups = themeGroups.filter((g) =>
    `${g.group} ${g.summary}`
      .replace(/[·\s]/g, '')
      .toLowerCase()
      .includes(query.replace(/[·\s]/g, '').toLowerCase()),
  );
  return (
    <>
      <SkipLink />
      <Masthead />
      <SiteHeader />
      <main id="main-content" className="service-home">
        <section className="service-hero" style={{ backgroundColor: season.backgroundColor }}>
          <img
            key={season.key}
            className="season-backdrop"
            src={season.heroImage}
            alt=""
            fetchPriority="high"
          />
          <div className="season-shade" aria-hidden="true" />
          <span className="season-place">{season.place}</span>
          <div className="home-wrap hero-layout">
            <div className="hero-copy">
              <p className="eyebrow">
                <span /> {season.eyebrow}
              </p>
              <h1>
                구리의 일상,
                <br />
                지도로 <em>더 가까이.</em>
              </h1>
              <p className="hero-description">
                필요한 곳을 찾고, 우리 동네를 새롭게 만나요.
                <br />
                구리의 생활정보를 한 장의 지도에서 살펴보세요.
              </p>
              <a className="home-button" href={themeUrl('생활편의')}>
                우리 동네 지도 열기 <ArrowUpRight size={18} />
              </a>
              <a className="hero-text-link" href="#search">
                어떤 지도가 있나요? <ArrowRight size={16} />
              </a>
            </div>
          </div>
          <div className="home-wrap season-controls">
            <span>구리의 사계절</span>
            <div role="group" aria-label="계절 선택">
              {(['spring', 'summer', 'autumn', 'winter'] as const).map((key) => (
                <button
                  key={key}
                  type="button"
                  aria-pressed={season.key === key}
                  onClick={() => setSelection(key)}
                >
                  {seasonConfig[key].label}
                </button>
              ))}
            </div>
          </div>
        </section>
        <section id="search" className="home-wrap discovery">
          <div className="section-heading">
            <div>
              <p className="eyebrow">EXPLORE GURI</p>
              <h2>어떤 곳을 찾고 계세요?</h2>
            </div>
            <p>관심 있는 테마를 골라 지도로 이동해요.</p>
          </div>
          <div className="theme-search">
            <Search size={22} />
            <label className="sr-only" htmlFor="theme-query">
              테마 이름 또는 시설 종류 찾기
            </label>
            <input
              id="theme-query"
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="테마나 시설 종류를 입력하세요. 예: 약국, 주차장"
            />
            <span>테마 검색</span>
          </div>
          <p className="sr-only" role="status">
            {groups.length}개 테마 그룹
          </p>
          <div className="group-catalog">
            {groups.map(({ group, icon: Icon, color, summary }, i) => (
              <a
                href={themeUrl(group)}
                key={group}
                style={{ '--group-color': color, '--order': i } as React.CSSProperties}
              >
                <span className="catalog-icon">
                  <Icon size={24} />
                </span>
                <span>
                  <strong>{group}</strong>
                  <small>{summary}</small>
                </span>
                <ArrowUpRight size={18} />
              </a>
            ))}
          </div>
          {!groups.length && (
            <div className="search-empty">
              일치하는 테마가 없어요. 다른 시설 종류로 찾아보세요.
              <button onClick={() => setQuery('')}>전체 테마 보기</button>
            </div>
          )}
        </section>
        {siteConfig.features.animalMap && (
          <section className="pet-section">
            <div className="home-wrap pet-layout">
              <div className="pet-illustration" aria-hidden="true">
                <PawPrint strokeWidth={0.85} />
                <span>A NEW BEGINNING</span>
              </div>
              <div>
                <p className="eyebrow">함께 살아가는 구리</p>
                <h2>
                  새로운 가족을 기다리는
                  <br />
                  아이들을 만나보세요.
                </h2>
                <p>
                  보호 중인 동물의 사진과 발견 장소,
                  <br />
                  보호소 정보를 한곳에서 확인할 수 있어요.
                </p>
                <a className="home-button pet-button" href={animalUrl()}>
                  유기동물 찾기 <ArrowUpRight size={18} />
                </a>
              </div>
            </div>
          </section>
        )}
        <section className="scene-section">
          <div className="home-wrap scene-layout">
            <div className="scene-illustration" aria-hidden="true">
              <SkylineArt />
              <span>GURI IN 3D</span>
            </div>
            <div>
              <p className="eyebrow">입체로 보는 구리</p>
              <h2>
                우리 동네를 하늘에서
                <br />
                내려다보세요.
              </h2>
              <p>
                건물과 지형을 3D로 돌려 보며
                <br />
                구리의 모습을 입체적으로 살펴볼 수 있어요.
              </p>
              <a className="home-button" href={sceneUrl()}>
                3D입체지도 보기 <ArrowUpRight size={18} />
              </a>
            </div>
          </div>
        </section>
        <section className="aerial-section">
          <div className="home-wrap aerial-layout">
            <div className="aerial-illustration" aria-hidden="true">
              <TimeLapseArt />
              <span>TIME LAPSE</span>
            </div>
            <div>
              <p className="eyebrow">시간을 따라 보는 구리</p>
              <h2>
                우리 동네의 변화 과정을
                <br />
                구경하세요.
              </h2>
              <p>
                해마다 찍은 항공사진을 나란히 놓고
                <br />
                우리 동네가 어떻게 달라졌는지 볼 수 있어요.
              </p>
              <a className="home-button" href={aerialUrl()}>
                항공사진 비교 보기 <ArrowUpRight size={18} />
              </a>
            </div>
          </div>
        </section>
        <section className="news-section">
          <div className="home-wrap news-layout">
            <div className="news-illustration" aria-hidden="true">
              <NewsArt />
              <span>NEIGHBORHOOD NEWS</span>
            </div>
            <div>
              <p className="eyebrow">함께 나누는 구리</p>
              <h2>
                우리 동네 소식을
                <br />
                한곳에서 만나보세요.
              </h2>
              <p>
                행사와 공지, 공약지도와 생활 정보까지
                <br />
                구리 동네소식에서 모아 볼 수 있어요.
              </p>
              <a
                className="home-button"
                href="https://guri.kgeohub.com/"
                target="_blank"
                rel="noopener"
              >
                구리 동네소식 보기 <ArrowUpRight size={18} />
              </a>
            </div>
          </div>
        </section>
        <section id="about" className="home-wrap about-section">
          <div>
            <p className="eyebrow">ABOUT G-MAP</p>
            <h2>
              우리 동네를 아는
              <br />
              가장 가까운 방법.
            </h2>
            <p>
              G-MAP은 구리의 생활 시설{siteConfig.features.animalMap ? '과 보호 동물' : ''} 정보를
              <br />
              지도에서 찾아보는 시민생활지도예요.
            </p>
          </div>
          <div className="usage-guide">
            {[
              {
                icon: Layers,
                title: '관심 있는 테마를 선택해요',
                text: '생활편의부터 문화·여가까지, 필요한 정보를 골라보세요.',
              },
              {
                icon: MapPin,
                title: '지도에서 장소를 확인해요',
                text: '목록과 지도를 함께 보며 위치와 상세정보를 확인해요.',
              },
              {
                icon: Compass,
                title: '방문 전에 한 번 더 확인해요',
                text: '운영시간과 이용 가능 여부는 해당 시설에 확인해 주세요.',
              },
            ].map(({ icon: Icon, title, text }, i) => (
              <div key={title}>
                <span className="guide-number">0{i + 1}</span>
                <Icon size={22} />
                <div>
                  <h3>{title}</h3>
                  <p>{text}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
      </main>
      <footer className="service-footer">
        <div className="home-wrap footer-main">
          <div className="footer-brand">
            <img src="/images/guri-ci.png" alt="구리시" height="40" />
            <p className="footer-site">
              <b>G-MAP</b> 구리시 시민생활지도
            </p>
            <p className="footer-tagline">{siteConfig.description}</p>
          </div>
          <nav className="footer-col" aria-label="지도 바로가기">
            <h3>지도 바로가기</h3>
            <ul>
              {footerLinks.map((l) => (
                <li key={l.label}>
                  <a
                    href={l.href}
                    {...(l.external ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
                  >
                    {l.label}
                    {l.external && <ArrowUpRight size={14} aria-hidden="true" />}
                  </a>
                </li>
              ))}
            </ul>
          </nav>
          <div className="footer-col">
            <h3>문의</h3>
            <ul>
              <li>{siteConfig.contact.department}</li>
              <li>
                <a href={`tel:${siteConfig.contact.phone.replace(/[^\d]/g, '')}`}>
                  {siteConfig.contact.phone}
                </a>
              </li>
              <li>{siteConfig.contact.address}</li>
            </ul>
          </div>
          <a className="footer-top-btn" href="#main-content" aria-label="맨 위로">
            <ArrowUp size={18} aria-hidden="true" />
            <span>맨 위로</span>
          </a>
        </div>
        <div className="footer-bar">
          <div className="home-wrap">
            <span>© {new Date().getFullYear()} 구리시</span>
            <span className="footer-id">
              <img src="/images/guri-emblem.png" alt="" height="16" />이 누리집은 구리시
              누리집이에요
            </span>
            <span>제작 케이지오솔루션</span>
          </div>
        </div>
      </footer>
    </>
  );
}
