/** 홈 3D 지도 안내 일러스트 — 등각 투영 건물 세 채 + 바닥 격자. 선은 currentColor, 면은 --art-fill */
export function SkylineArt() {
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
      {/* 바닥 판 */}
      <path d="M120 186 L22 132 L120 78 L218 132 Z" fill="#fff" />
      <path d="M71 105 L169 159 M169 105 L71 159" strokeWidth="1.8" opacity="0.35" />
      {/* 낮은 건물 (왼쪽) */}
      <path d="M52 124 V96 L84 78 L116 96 V124 L84 142 Z" fill="#fff" />
      <path d="M52 96 L84 114 L116 96 M84 114 V142" />
      <path d="M52 96 L84 78 L116 96 L84 114 Z" fill="var(--art-fill)" />
      {/* 높은 건물 (가운데) */}
      <path d="M96 120 V56 L128 38 L160 56 V120 L128 138 Z" fill="#fff" />
      <path d="M96 56 L128 74 L160 56 M128 74 V138" />
      <path d="M96 56 L128 38 L160 56 L128 74 Z" fill="var(--art-fill)" />
      <path d="M106 84 h10 M106 98 h10 M140 84 h10 M140 98 h10" strokeWidth="2.2" opacity="0.7" />
      {/* 중간 건물 (오른쪽) */}
      <path d="M150 140 V104 L182 86 L214 104 V140 L182 158 Z" fill="#fff" />
      <path d="M150 104 L182 122 L214 104 M182 122 V158" />
      <path d="M150 104 L182 86 L214 104 L182 122 Z" fill="var(--art-fill)" />
      {/* 해 */}
      <circle cx="40" cy="36" r="10" fill="var(--art-fill)" stroke="none" />
      <path d="M40 18 V12 M40 60 V54 M22 36 H16 M64 36 H58" strokeWidth="2.2" opacity="0.8" />
    </svg>
  );
}
