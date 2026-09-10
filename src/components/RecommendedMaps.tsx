import { recommendedMaps } from '@/config/categories.config';
import { Container, SectionHeading, ArrowButton } from './ui';
export function RecommendedMaps() {
  return (
    <section id="recommended" className="py-20 md:py-28">
      <Container>
        <SectionHeading
          eyebrow="LIFE MAP"
          title="구리 추천 생활지도"
          description="생활의 순간마다 유용한 지도를 골라 보세요."
          action="생활지도 전체 보기"
        />
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
          {recommendedMaps.map(({ id, title, description, icon: Icon, color }, i) => (
            <article
              key={id}
              className={`group flex min-h-[280px] flex-col rounded-[24px] p-6 transition hover:-translate-y-1 ${i === 0 ? 'text-white lg:col-span-2' : 'border border-slate-100 bg-white shadow-card'}`}
              style={i === 0 ? { background: `linear-gradient(145deg,${color},#243D83)` } : {}}
            >
              <span
                className={`grid h-12 w-12 place-items-center rounded-[16px] ${i === 0 ? 'bg-white/15' : 'bg-slate-50'}`}
                style={{ color: i === 0 ? 'white' : color }}
              >
                <Icon size={25} />
              </span>
              <h3 className="mt-auto text-xl font-extrabold tracking-tight">{title}</h3>
              <p
                className={`mb-5 mt-2 break-keep text-sm leading-6 ${i === 0 ? 'text-white/70' : 'text-slate-500'}`}
              >
                {description}
              </p>
              <ArrowButton label="지도 열기" />
            </article>
          ))}
        </div>
      </Container>
    </section>
  );
}
