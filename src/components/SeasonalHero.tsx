'use client';
import { motion } from 'framer-motion';
import { Search, MapPin, Navigation } from 'lucide-react';
import type { SeasonTheme } from '@/config/season.config';
import { quickCategories } from '@/config/categories.config';
import { Container } from './ui';
export function SeasonalHero({ season }: { season: SeasonTheme }) {
  return (
    <section
      className="relative overflow-hidden"
      style={{ backgroundColor: season.backgroundColor }}
    >
      <motion.div
        key={season.key}
        initial={{ opacity: 0, scale: 1.02 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.7 }}
        className="absolute inset-0 bg-cover bg-[62%_center] md:bg-center"
        style={{ backgroundImage: `url(${season.heroImage})` }}
      />
      <div className="absolute inset-0 bg-gradient-to-r from-white/95 via-white/65 to-transparent md:from-white/88 md:via-white/30" />
      <Container className="relative flex min-h-[610px] flex-col justify-center pb-36 pt-12 md:min-h-[680px] md:pb-40">
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
            className="break-keep text-[42px] font-black leading-[1.15] tracking-[-.055em] md:text-[60px] lg:text-[68px]"
            style={{ color: season.titleColor }}
          >
            구리의 생활을
            <br />
            <span style={{ color: season.accentColor }}>지도에서</span> 만나보세요
          </h1>
          <p className="mt-5 text-base font-medium text-slate-600 md:text-lg">
            약국부터 산책로, 우리 동네 도시정보까지
            <br className="hidden sm:block" /> 필요한 생활정보를 쉽고 빠르게 찾아보세요.
          </p>
          <form
            onSubmit={(e) => e.preventDefault()}
            className="mt-8 flex max-w-[600px] items-center rounded-[20px] bg-white p-2 shadow-[0_18px_55px_rgba(26,45,37,.18)]"
          >
            <MapPin className="ml-3 hidden text-slate-400 sm:block" size={21} />
            <input
              aria-label="통합검색"
              className="min-w-0 flex-1 bg-transparent px-3 py-3.5 text-[15px] outline-none placeholder:text-slate-400 md:text-base"
              placeholder="장소, 주소, 생활정보를 검색해 보세요"
            />
            <button
              className="grid h-12 w-12 shrink-0 place-items-center rounded-[15px] text-white"
              style={{ background: season.accentColor }}
            >
              <Search size={21} />
            </button>
          </form>
          <div className="mt-4 flex items-center gap-3 text-xs font-medium text-slate-500">
            <Navigation size={14} />
            <span>추천 검색어</span>
            <button>무더위쉼터</button>
            <button>공영주차장</button>
            <button>아차산 둘레길</button>
          </div>
        </motion.div>
      </Container>
      <div className="absolute inset-x-0 bottom-0">
        <Container>
          <div className="grid grid-cols-3 overflow-hidden rounded-t-[26px] border border-white/70 bg-white/92 shadow-soft backdrop-blur-xl md:grid-cols-6">
            {quickCategories.map(({ id, label, icon: Icon, color }) => (
              <button
                key={id}
                className="group flex items-center justify-center gap-3 border-b border-r border-slate-100 px-2 py-4 transition hover:bg-white md:py-6"
              >
                <span
                  className="grid h-10 w-10 place-items-center rounded-[14px] transition group-hover:-translate-y-1"
                  style={{ background: `${color}16`, color }}
                >
                  <Icon size={21} />
                </span>
                <span className="font-bold text-slate-700">{label}</span>
              </button>
            ))}
          </div>
        </Container>
      </div>
    </section>
  );
}
