import { ArrowUpRight } from 'lucide-react';
import type { SeasonTheme } from '@/config/season.config';
import { featuredDetails } from '@/config/featured.config';
import { Container, SectionHeading } from './ui';
export function NowGuri({ season }: { season: SeasonTheme }) {
  return (
    <section className="py-20 md:py-28">
      <Container>
        <SectionHeading
          eyebrow="NOW, GURI"
          title="지금 구리"
          description="이 계절, 구리에서 놓치지 말아야 할 생활정보예요."
          action="전체 보기"
        />
        <div className="grid grid-cols-2 gap-4 md:grid-cols-6 md:grid-rows-2 md:gap-5">
          {season.featuredItems.map((title, i) => {
            const d = featuredDetails[i];
            return (
              <article
                key={title}
                className={`group relative min-h-[210px] overflow-hidden rounded-[24px] p-6 ${i === 0 ? 'col-span-2 md:col-span-3 md:row-span-2 md:min-h-[454px]' : i === 1 ? 'md:col-span-3' : i === 2 ? 'md:col-span-2' : i === 3 ? 'md:col-span-2' : 'col-span-2 md:col-span-2'}`}
                style={{
                  background:
                    i === 0
                      ? `linear-gradient(145deg,${season.accentColor},${season.titleColor})`
                      : i === 1
                        ? season.accentSoft
                        : '#F6F8F7',
                }}
              >
                <div className={`relative z-10 ${i === 0 ? 'text-white' : ''}`}>
                  <span
                    className={`inline-block rounded-full px-3 py-1 text-xs font-bold ${i === 0 ? 'bg-white/18' : 'bg-white'}`}
                  >
                    {d.badge}
                  </span>
                  <h3
                    className={`mt-4 break-keep font-extrabold tracking-tight ${i === 0 ? 'max-w-sm text-3xl md:text-4xl' : 'text-lg md:text-xl'}`}
                  >
                    {title}
                  </h3>
                  <p className={`mt-2 text-sm ${i === 0 ? 'text-white/75' : 'text-slate-500'}`}>
                    {d.description}
                  </p>
                </div>
                <ArrowUpRight
                  className={`absolute bottom-5 right-5 transition group-hover:-translate-y-1 group-hover:translate-x-1 ${i === 0 ? 'text-white' : 'text-slate-400'}`}
                />
                {i === 0 && (
                  <>
                    <div className="absolute -bottom-20 -right-14 h-72 w-72 rounded-full border-[50px] border-white/10" />
                    <div className="absolute bottom-16 right-24 h-20 w-20 rounded-full bg-white/10" />
                  </>
                )}
              </article>
            );
          })}
        </div>
      </Container>
    </section>
  );
}
