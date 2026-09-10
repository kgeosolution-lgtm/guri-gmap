import { quickFinder } from '@/config/categories.config';
import { CardLink, Container, ReadyBadge, SectionHeading } from './ui';
export function QuickFinder() {
  return (
    <section className="bg-[#F5F8F7] py-20 md:py-24">
      <Container>
        <SectionHeading
          title="지금 바로 찾기"
          description="급할 때, 가까운 생활시설을 바로 확인하세요."
        />
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
          {quickFinder.map(({ id, title, description, icon: Icon, color, href }) => (
            <CardLink
              key={id}
              href={href}
              as="button"
              className="group relative rounded-[22px] border border-slate-100 bg-white p-5 text-left shadow-sm transition hover:-translate-y-1 hover:shadow-card md:p-6"
            >
              <span
                className="mb-6 grid h-12 w-12 place-items-center rounded-[16px]"
                style={{ color, background: `${color}13` }}
              >
                <Icon size={25} />
              </span>
              <strong className="block text-lg text-slate-800">{title}</strong>
              <span className="mt-1 block text-xs text-slate-400">{description}</span>
              {!href && <ReadyBadge className="absolute right-4 top-4" />}
            </CardLink>
          ))}
        </div>
      </Container>
    </section>
  );
}
