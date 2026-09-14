/** 홈 시계열 항공사진 안내 일러스트 — 겹쳐진 항공사진 프레임 + 연도 슬라이더. 선은 currentColor, 면은 --art-fill */
export function TimeLapseArt() {
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
        x="26"
        y="20"
        width="176"
        height="126"
        rx="8"
        opacity="0.35"
        transform="rotate(-7 114 83)"
      />
      <rect
        x="38"
        y="30"
        width="176"
        height="126"
        rx="8"
        opacity="0.55"
        transform="rotate(-3.5 126 93)"
      />
      <rect x="52" y="42" width="176" height="126" rx="8" fill="#fff" />
      <path d="M52 108 H228" />
      <path d="M144 42 V168" />
      <path
        d="M100 42 C120 70 130 78 156 90 C176 100 184 112 196 168"
        strokeWidth="2.5"
        opacity="0.9"
      />
      <g fill="var(--art-fill)" stroke="none">
        <rect x="70" y="60" width="16" height="16" rx="2" />
        <rect x="112" y="56" width="20" height="20" rx="2" />
        <rect x="160" y="60" width="18" height="14" rx="2" />
        <rect x="192" y="52" width="22" height="26" rx="2" />
        <rect x="70" y="128" width="20" height="14" rx="2" />
        <rect x="118" y="136" width="14" height="18" rx="2" />
        <rect x="192" y="122" width="24" height="18" rx="2" />
        <circle cx="152" cy="140" r="7" />
      </g>
      <path d="M40 184 H240" strokeWidth="2.5" />
      <path d="M40 178 V190 M100 178 V190 M240 178 V190" strokeWidth="2.5" />
      <circle cx="160" cy="184" r="7" fill="currentColor" stroke="none" />
    </svg>
  );
}
