import { layersConfig } from '@/config/layers.config';
import { Container, SectionHeading } from './ui';
import { ArrowUpRight } from 'lucide-react';
export function SpatialInfo() {
  return (
    <section id="spatial" className="bg-[#182F2A] py-20 text-white md:py-28">
      <Container>
        <SectionHeading
          eyebrow="SPATIAL INFORMATION"
          title="구리 공간정보"
          description="평면에서 입체까지, 구리의 공간을 더 깊게 살펴보세요."
        />
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {layersConfig.map(({ id, title, description, icon: Icon, type, mockCount }) => (
            <article
              key={id}
              className="group relative min-h-[260px] overflow-hidden rounded-[24px] border border-white/10 bg-white/[.07] p-6 transition hover:bg-white/[.12]"
            >
              <span className="grid h-12 w-12 place-items-center rounded-[15px] bg-white/10 text-[#7FE0BC]">
                <Icon size={24} />
              </span>
              <div className="absolute -right-12 -top-10 h-40 w-40 rounded-full border-[30px] border-white/[.025]" />
              <div className="mt-14">
                <span className="text-[10px] font-bold uppercase tracking-[.18em] text-white/40">
                  {type} {mockCount && `· ${mockCount} layers`}
                </span>
                <h3 className="mt-2 text-2xl font-extrabold">{title}</h3>
                <p className="mt-2 text-sm leading-6 text-white/55">{description}</p>
              </div>
              <ArrowUpRight className="absolute bottom-6 right-6 text-white/50 transition group-hover:-translate-y-1 group-hover:translate-x-1" />
            </article>
          ))}
        </div>
      </Container>
    </section>
  );
}
