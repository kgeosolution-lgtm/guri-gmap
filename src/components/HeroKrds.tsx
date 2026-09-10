'use client';
import { motion } from 'framer-motion';
import type { SeasonTheme } from '@/config/season.config';
import { themeGroups } from '@/config/theme-groups.config';
import { themeUrl } from '@/config/links';
import { Container } from './ui';

/**
 * 계절 히어로 (KRDS 홈용). v1 의 SeasonalHero 에서 이미지·문구·계절 전환은 그대로 두고
 * 아직 동작하지 않는 검색폼·추천검색어를 뺐다. 하단 띠는 테마지도 실제 그룹 9개로 연결.
 */
export function HeroKrds({ season }: { season: SeasonTheme }) {
  return (
    <section
      className="relative overflow-hidden"
      style={{ backgroundColor: season.backgroundColor }}
      aria-labelledby="hero-title"
    >
      <motion.div
        key={season.key}
        initial={{ opacity: 0, scale: 1.02 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.7 }}
        className="absolute inset-0 bg-cover bg-[62%_center] md:bg-center"
        style={{ backgroundImage: `url(${season.heroImage})` }}
        aria-hidden="true"
      />
      <div className="absolute inset-0 bg-gradient-to-r from-white/95 via-white/65 to-transparent md:from-white/88 md:via-white/30" />
      <Container className="relative flex min-h-[600px] flex-col justify-center pb-[260px] pt-10 md:min-h-[560px] md:pb-44 md:pt-12">
        <motion.div
          key={`${season.key}-copy`}
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="max-w-[620px]"
        >
          <div
            className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/70 bg-white/75 px-4 py-2 text-sm font-bold shadow-sm backdrop-blur"
            style={{ color: season.accentColor }}
          >
            <span className="h-2 w-2 rounded-full" style={{ background: season.accentColor }} />
            {season.eyebrow}
          </div>
          <h1
            id="hero-title"
            className="break-keep text-[38px] font-black leading-[1.15] tracking-[-.05em] md:text-[56px] lg:text-[64px]"
            style={{ color: season.titleColor }}
          >
            구리의 생활을
            <br />
            <span style={{ color: season.accentColor }}>지도에서</span> 만나보세요
          </h1>
          <p className="mt-5 text-base font-medium text-gray-70 md:text-lg">
            약국부터 산책로, 유기동물 보호소까지
            <br className="hidden sm:block" /> 필요한 생활정보를 지도에서 바로 찾아보세요.
          </p>
        </motion.div>
      </Container>
      <div className="absolute inset-x-0 bottom-0">
        <Container>
          <nav className="krds-group-strip" aria-label="테마지도 분류 바로가기">
            {themeGroups.map(({ group, icon: Icon, color }) => (
              <a
                key={group}
                href={themeUrl(group)}
                target="_blank"
                rel="noopener"
                title={`${group} 테마지도 (새 창 열림)`}
              >
                <span
                  className="ico"
                  style={{ background: `${color}18`, color }}
                  aria-hidden="true"
                >
                  <Icon size={21} />
                </span>
                <span>{group}</span>
              </a>
            ))}
          </nav>
        </Container>
      </div>
    </section>
  );
}
