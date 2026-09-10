'use client';
import { useEffect, useState } from 'react';
import { SkipLink, Masthead } from '@/components/krds/Masthead';
import { KrdsHeader } from '@/components/krds/KrdsHeader';
import { KrdsFooter } from '@/components/krds/KrdsFooter';
import { HeroKrds } from '@/components/HeroKrds';
import { MapsNow } from '@/components/MapsNow';
import { NowGuri } from '@/components/NowGuri';
import { ComingSoon } from '@/components/ComingSoon';
import { DevSeasonToolbar } from '@/components/DevSeasonToolbar';
import { getAutoSeason, seasonConfig } from '@/config/season.config';
import type { SeasonKey } from '@/types/content';

/** KRDS 기반 홈. 이전 홈은 /v1 에 그대로 남아 있다. */
export default function Home() {
  const [selection, setSelection] = useState<'auto' | SeasonKey>('auto');
  const [auto, setAuto] = useState<SeasonKey>('summer');
  useEffect(() => setAuto(getAutoSeason()), []);
  const season = seasonConfig[selection === 'auto' ? auto : selection];
  return (
    <>
      <SkipLink />
      <Masthead />
      <KrdsHeader />
      <main
        id="main-content"
        className="krds-home"
        style={
          {
            '--accent': season.accentColor,
            '--accent-soft': season.accentSoft,
          } as React.CSSProperties
        }
      >
        <HeroKrds season={season} />
        <MapsNow />
        <NowGuri season={season} />
        <ComingSoon />
      </main>
      <KrdsFooter />
      <DevSeasonToolbar value={selection} onChange={setSelection} />
    </>
  );
}
