import { ArrowRight } from 'lucide-react';
export function Container({
  children,
  className = '',
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`mx-auto w-full max-w-[1280px] px-5 md:px-8 ${className}`}>{children}</div>
  );
}
export function SectionHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: string;
}) {
  return (
    <div className="mb-6 flex items-end justify-between gap-5 md:mb-8">
      <div>
        {eyebrow && (
          <p className="mb-1.5 text-xs font-bold tracking-wide text-[var(--accent)]">{eyebrow}</p>
        )}
        <h2 className="text-[26px] font-extrabold tracking-[-.04em] text-slate-900 md:text-[32px]">
          {title}
        </h2>
        {description && (
          <p className="mt-1.5 text-sm text-slate-500 md:text-[15px]">{description}</p>
        )}
      </div>
      {action && (
        <button className="hidden shrink-0 items-center gap-1 text-sm font-bold text-slate-600 md:flex">
          {action}
          <ArrowRight size={16} />
        </button>
      )}
    </div>
  );
}
export function ArrowButton({ label = '자세히 보기' }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-1 text-sm font-bold">
      {label}
      <ArrowRight size={15} />
    </span>
  );
}
/**
 * 카드 껍데기. href 가 있으면 <a>(같은 사이트라 같은 탭), 없으면 기존 태그(button/article)를 그대로 쓴다.
 * 어느 태그든 data-card 를 달아 globals.css 의 밀도 규칙이 동일하게 적용되게 한다.
 */
export function CardLink({
  href,
  as = 'article',
  className,
  style,
  children,
}: {
  href?: string | null;
  as?: 'button' | 'article';
  className?: string;
  style?: React.CSSProperties;
  children: React.ReactNode;
}) {
  if (href) {
    return (
      <a href={href} data-card className={className} style={style}>
        {children}
      </a>
    );
  }
  const Tag = as;
  return (
    <Tag data-card className={className} style={style}>
      {children}
    </Tag>
  );
}
/** 연결 페이지가 아직 없는 카드에 붙이는 작은 "준비중" 배지 */
export function ReadyBadge({
  tone = 'dark',
  className = '',
}: {
  tone?: 'dark' | 'light';
  className?: string;
}) {
  const color = tone === 'light' ? 'bg-white/20 text-white/80' : 'bg-slate-100 text-slate-400';
  return (
    <span
      className={`pointer-events-none inline-block rounded-full px-2 py-0.5 text-[10px] font-bold leading-4 ${color} ${className}`}
    >
      준비중
    </span>
  );
}
