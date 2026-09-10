import {
  Database,
  Download,
  FileJson,
  Lightbulb,
  MessageCircle,
  ArrowRight,
  FlaskConical,
  Sparkles,
  ScanLine,
  Box,
  Map,
  BrainCircuit,
  ExternalLink,
} from 'lucide-react';
import { participation } from '@/config/categories.config';
import { externalLinks } from '@/config/external-links.config';
import { Container, SectionHeading } from './ui';
export function OpenData() {
  return (
    <section id="open-data" className="bg-[#F5F8F7] py-20 md:py-24">
      <Container>
        <div className="grid items-center gap-10 overflow-hidden rounded-[28px] bg-white p-7 shadow-card md:grid-cols-2 md:p-12">
          <div>
            <p className="mb-3 text-sm font-bold text-[var(--accent)]">OPEN DATA</p>
            <h2 className="text-3xl font-black tracking-tight md:text-4xl">
              공간데이터를
              <br />
              자유롭게 활용하세요
            </h2>
            <p className="mt-4 max-w-md leading-7 text-slate-500">
              구리시가 보유한 공간정보의 목록을 확인하고, 시민과 기업이 활용할 수 있는 데이터를
              내려받을 수 있어요.
            </p>
            <button className="mt-7 inline-flex items-center gap-2 rounded-full bg-slate-900 px-5 py-3 text-sm font-bold text-white">
              열린데이터 둘러보기
              <ArrowRight size={16} />
            </button>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {[
              [Database, '64', '공간데이터'],
              [Download, '1,280', '누적 다운로드'],
              [FileJson, 'SHP · CSV', '제공 형식'],
              [Sparkles, 'NEW 8', '신규 데이터'],
            ].map(([Icon, n, l]) => (
              <div key={String(l)} className="rounded-[20px] bg-slate-50 p-5">
                <Icon className="mb-8 text-[var(--accent)]" />
                <strong className="block text-2xl">{n as string}</strong>
                <span className="text-xs text-slate-400">{l as string}</span>
              </div>
            ))}
          </div>
        </div>
      </Container>
    </section>
  );
}
export function CitizenParticipation() {
  return (
    <section id="participation" className="py-20 md:py-28">
      <Container>
        <SectionHeading
          title="시민참여"
          description="시민의 목소리로 더 정확하고 쓸모 있는 지도를 만듭니다."
        />
        <div className="grid gap-4 md:grid-cols-3">
          {participation.map(({ title, description, icon: Icon }, i) => (
            <button
              key={title}
              className="flex items-center gap-5 rounded-[22px] border border-slate-200 p-6 text-left transition hover:border-[var(--accent)] hover:shadow-card"
            >
              <span className="grid h-14 w-14 shrink-0 place-items-center rounded-[18px] bg-[var(--accent-soft)] text-[var(--accent)]">
                <Icon size={25} />
              </span>
              <span>
                <strong className="text-lg">{title}</strong>
                <small className="mt-1 block text-slate-500">{description}</small>
              </span>
              <ArrowRight className="ml-auto text-slate-300" size={19} />
            </button>
          ))}
        </div>
      </Container>
    </section>
  );
}
export function KgeoLab() {
  const tags = [
    [BrainCircuit, 'AI'],
    [ScanLine, 'AR'],
    [Box, '3D'],
    [Map, 'GIS'],
    [Sparkles, 'GeoAI'],
  ] as const;
  return (
    <section className="pb-20 md:pb-28">
      <Container>
        <div className="relative overflow-hidden rounded-[30px] bg-[#15294A] px-7 py-12 text-white md:px-14 md:py-16">
          <div className="absolute -right-24 -top-32 h-96 w-96 rounded-full bg-cyan-400/10 blur-2xl" />
          <div className="relative grid items-center gap-10 lg:grid-cols-[1.2fr_1fr]">
            <div>
              <div className="mb-5 inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1.5 text-xs font-bold text-cyan-200">
                <FlaskConical size={14} />
                kgeoLab
              </div>
              <h2 className="text-3xl font-black tracking-tight md:text-5xl">
                공간기술의 내일을
                <br />
                구리에서 실험합니다
              </h2>
              <p className="mt-5 max-w-lg leading-7 text-white/60">
                AI와 3D, 증강현실을 공간정보와 연결해 더 쉽고 새로운 시민 서비스를 연구합니다.
              </p>
              <button className="mt-7 inline-flex items-center gap-2 rounded-full bg-white px-5 py-3 text-sm font-bold text-slate-900">
                실험실 보기
                <ArrowRight size={16} />
              </button>
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {tags.map(([Icon, label], i) => (
                <div
                  key={label}
                  className={`grid aspect-square place-items-center rounded-[22px] border border-white/10 bg-white/[.06] ${i === 4 ? 'col-span-2 sm:col-span-1' : ''}`}
                >
                  <Icon size={28} className="mb-[-28px] text-cyan-300" />
                  <strong>{label}</strong>
                </div>
              ))}
            </div>
          </div>
        </div>
      </Container>
    </section>
  );
}
export function ExternalServices() {
  return (
    <section className="border-t border-slate-100 py-14">
      <Container>
        <h2 className="mb-6 text-xl font-extrabold">함께 이용하면 좋아요</h2>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
          {externalLinks.map((x) => (
            <a
              key={x.name}
              href={x.href}
              target="_blank"
              rel="noreferrer"
              className="group flex min-h-24 items-center justify-between rounded-[18px] border border-slate-200 p-4 transition hover:border-slate-400"
            >
              <span>
                <strong className="block text-sm">{x.name}</strong>
                <small className="mt-1 block text-slate-400">{x.description}</small>
              </span>
              <ExternalLink size={16} className="text-slate-300 group-hover:text-slate-600" />
            </a>
          ))}
        </div>
      </Container>
    </section>
  );
}
