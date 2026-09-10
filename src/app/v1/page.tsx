'use client';
import { useEffect, useState } from 'react';
import { Header, Footer } from '@/components/Layout';
import { SeasonalHero } from '@/components/SeasonalHero';
import { NowGuri } from '@/components/NowGuri';
import { QuickFinder } from '@/components/QuickFinder';
import { RecommendedMaps } from '@/components/RecommendedMaps';
import { SpatialInfo } from '@/components/SpatialInfo';
import { UrbanStats } from '@/components/UrbanStats';
import {
  OpenData,
  CitizenParticipation,
  KgeoLab,
  ExternalServices,
} from '@/components/ContentSections';
import { DevSeasonToolbar } from '@/components/DevSeasonToolbar';
import { getAutoSeason, seasonConfig } from '@/config/season.config';
import type { SeasonKey } from '@/types/content';
export default function Home() {
  const [selection, setSelection] = useState<'auto' | SeasonKey>('auto');
  const [auto, setAuto] = useState<SeasonKey>('summer');
  useEffect(() => setAuto(getAutoSeason()), []);
  const season = seasonConfig[selection === 'auto' ? auto : selection];
  return (
    <main
      className="v1-home"
      style={
        {
          '--accent': season.accentColor,
          '--accent-soft': season.accentSoft,
        } as React.CSSProperties
      }
    >
      <Header />
      <SeasonalHero season={season} />
      <NowGuri season={season} />
      <QuickFinder />
      <RecommendedMaps />
      <SpatialInfo />
      <UrbanStats />
      <OpenData />
      <CitizenParticipation />
      <KgeoLab />
      <ExternalServices />
      <Footer />
      <DevSeasonToolbar value={selection} onChange={setSelection} />
    </main>
  );
}
