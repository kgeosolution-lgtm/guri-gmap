/** 홈 동네소식 안내 일러스트 — 소식지 한 장(제목·사진·글줄) + 확성기 배지. 선은 currentColor, 면은 --art-fill */
export function NewsArt() {
  return (
    <svg
      viewBox="0 0 240 200"
      fill="none"
      stroke="currentColor"
      strokeWidth="3"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <rect
        x="30"
        y="34"
        width="150"
        height="150"
        rx="10"
        opacity="0.35"
        transform="rotate(-6 105 109)"
      />
      <rect x="44" y="26" width="150" height="150" rx="10" fill="#fff" />
      <path d="M62 50 H134" strokeWidth="5" />
      <g fill="var(--art-fill)" stroke="none">
        <rect x="62" y="66" width="52" height="40" rx="4" />
      </g>
      <path d="M62 66 H114 V106 H62 Z" strokeWidth="2.5" />
      <path d="M70 98 L82 84 L92 94 L100 86 L108 98" strokeWidth="2.5" />
      <circle cx="102" cy="76" r="3.5" fill="currentColor" stroke="none" />
      <path d="M126 70 H176 M126 84 H176 M126 98 H166" strokeWidth="2.5" />
      <path d="M62 122 H176 M62 136 H176 M62 150 H140" strokeWidth="2.5" />
      <circle cx="186" cy="48" r="30" fill="var(--art-fill)" stroke="none" opacity="0.9" />
      <circle cx="186" cy="48" r="30" />
      <path d="M170 44 V54 H178 L192 62 V32 L178 42 H170 Z" fill="#fff" />
      <path d="M198 42 C202 46 202 52 198 56" strokeWidth="2.5" />
      <path d="M204 36 C211 42 211 54 204 60" strokeWidth="2.5" opacity="0.7" />
    </svg>
  );
}
