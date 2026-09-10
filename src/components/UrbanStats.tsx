import { urbanStats } from '@/config/categories.config';
import { Container, SectionHeading } from './ui';
import { ChevronRight } from 'lucide-react';
export function UrbanStats() {
  return (
    <section id="urban" className="py-20 md:py-28">
      <Container>
        <SectionHeading
          eyebrow="MY NEIGHBORHOOD"
          title="우리 동네 도시계획·통계"
          description="숫자와 지도로 우리 동네의 오늘과 내일을 읽어보세요."
        />
        <div className="grid overflow-hidden rounded-[24px] border border-slate-200 md:grid-cols-5">
          {urbanStats.map(({ id, title, description, icon: Icon }) => (
            <button
              key={id}
              className="group flex items-center gap-4 border-b border-slate-100 bg-white p-5 text-left transition hover:bg-[var(--accent-soft)] md:block md:border-b-0 md:border-r md:p-6"
            >
              <span className="grid h-11 w-11 shrink-0 place-items-center rounded-[14px] bg-slate-100 text-slate-700 group-hover:bg-white group-hover:text-[var(--accent)]">
                <Icon size={22} />
              </span>
              <span className="flex-1 md:block">
                <strong className="block mt-0 md:mt-8">{title}</strong>
                <small className="mt-1 block text-slate-400">{description}</small>
              </span>
              <ChevronRight size={17} className="text-slate-300 md:mt-5" />
            </button>
          ))}
        </div>
      </Container>
    </section>
  );
}
