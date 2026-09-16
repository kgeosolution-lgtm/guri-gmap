'use client';
import { useEffect, useState } from 'react';
import { ArrowUpRight, Search, PawPrint, MapPin, Layers, Compass, ArrowRight } from 'lucide-react';
import { themeGroups } from '@/config/theme-groups.config';
import { themeUrl, animalUrl, sceneUrl, aerialUrl } from '@/config/links';
import { TimeLapseArt } from '@/components/TimeLapseArt';
import { SkylineArt } from '@/components/SkylineArt';
import { SiteHeader } from '@/components/krds/SiteHeader';
import { SkipLink, Masthead } from '@/components/krds/Masthead';
import { siteConfig } from '@/config/site.config';
import { getAutoSeason, seasonConfig } from '@/config/season.config';
import type { SeasonKey } from '@/types/content';
import './service-home.css';
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
                우리 동네 지도 열기 <ArrowUpRight size={19} />
              </a>
              <a className="hero-text-link" href="#search">
                어떤 지도가 있나요? <ArrowRight size={16} />
              </a>
            </div>
          </div>
          <div className="home-wrap season-controls">
            <span>구리의 사계절</span>
            <div role="group" aria-label="계절 선택">
              {(['auto', 'spring', 'summer', 'autumn', 'winter'] as const).map((key) => (
                <button
                  key={key}
                  aria-pressed={selection === key}
                  onClick={() => setSelection(key)}
                >
                  {key === 'auto' ? '자동' : seasonConfig[key].label}
                </button>
              ))}
            </div>
            <small>
              {selection === 'auto' ? '현재 계절을 보여드려요' : '다른 계절을 둘러보고 있어요'}
            </small>
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
                  <Icon size={25} strokeWidth={1.7} />
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
                유기동물 찾기 <ArrowUpRight size={19} />
              </a>
            </div>
            <span className="pet-section-index">02 / COMPANION</span>
          </div>
        </section>
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
                3D 지도 보기 <ArrowUpRight size={19} />
              </a>
            </div>
            <span className="scene-section-index">03 / SKYLINE</span>
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
                시계열 항공사진 보기 <ArrowUpRight size={19} />
              </a>
            </div>
            <span className="aerial-section-index">04 / TIMELINE</span>
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
              G-MAP은 구리의 생활 시설과 보호 동물 정보를
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
        <div className="home-wrap">
          <div className="footer-top">
            <img src="/images/guri-ci.png" alt="구리시" height="40" />
            <p>
              구리시 시민생활지도
              <br />
              <span>{siteConfig.contact.address}</span>
            </p>
            <a href="#main-content">맨 위로 ↑</a>
          </div>
          <div className="footer-bottom">
            <span>© {new Date().getFullYear()} 구리시</span>
            <span>케이지오솔루션</span>
          </div>
        </div>
      </footer>
    </>
  );
}
