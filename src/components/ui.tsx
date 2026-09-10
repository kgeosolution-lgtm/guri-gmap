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
