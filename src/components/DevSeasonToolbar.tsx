'use client';
import { Settings2, X } from 'lucide-react';
import { useState } from 'react';
import type { SeasonKey } from '@/types/content';
const options: ['auto' | SeasonKey, string][] = [
  ['auto', 'AUTO'],
  ['spring', '봄'],
  ['summer', '여름'],
  ['autumn', '가을'],
  ['winter', '겨울'],
];
export function DevSeasonToolbar({
  value,
  onChange,
}: {
  value: 'auto' | SeasonKey;
  onChange: (v: 'auto' | SeasonKey) => void;
}) {
  const [open, setOpen] = useState(true);
  if (process.env.NEXT_PUBLIC_SHOW_THEME_TOOLBAR === 'false') return null;
  return (
    <div className="fixed bottom-4 right-4 z-[60] flex items-center gap-2 rounded-[18px] border border-slate-200 bg-white/95 p-2 shadow-2xl backdrop-blur">
      <button
        onClick={() => setOpen(!open)}
        aria-label="테마 도구"
        className="grid h-9 w-9 place-items-center rounded-xl bg-slate-900 text-white"
      >
        {open ? <X size={16} /> : <Settings2 size={17} />}
      </button>
      {open && (
        <div className="flex items-center gap-1">
          {options.map(([id, label]) => (
            <button
              key={id}
              onClick={() => onChange(id)}
              className={`rounded-xl px-3 py-2 text-xs font-bold transition ${value === id ? 'bg-[var(--accent)] text-white' : 'text-slate-500 hover:bg-slate-100'}`}
            >
              {label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
