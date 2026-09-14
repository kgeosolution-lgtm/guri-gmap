import { ArrowUpRight } from 'lucide-react';
import { aerialUrl } from '@/config/links';

/** 시계열 항공사진 안내 띠 — 유기동물 찾기 카드 아래. 왼쪽 원형 일러스트 + 오른쪽 문구·버튼 */
export function AerialPromo() {
  const aerial = aerialUrl();
  return (
    <section id="aerial" className="krds-section" aria-labelledby="aerial-title">
      <div className="krds-inner">
        <div className="krds-aerial-promo">
          <a
            href={aerial}
            className="promo-art"
            title="시계열 항공사진 열기"
            aria-hidden="true"
            tabIndex={-1}
          >
            <TimeLapseArt />
            <span className="promo-caption">TIME LAPSE</span>
          </a>
          <div className="promo-body">
            <p className="promo-eyebrow">시간을 따라 보는 구리</p>
            <h2 id="aerial-title" className="promo-title">
              우리 동네의 변화 과정을
              <br />
              구경하세요.
            </h2>
            <p className="promo-desc">
              해마다 찍은 항공사진을 나란히 놓고
              <br />
              우리 동네가 어떻게 달라졌는지 볼 수 있어요.
            </p>
            <div className="promo-actions">
              <a href={aerial} className="krds-btn primary">
                시계열 항공사진 보기 <ArrowUpRight className="svg-icon" aria-hidden="true" />
              </a>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

/** 겹쳐진 항공사진 프레임 + 연도 슬라이더 일러스트 (선 색은 currentColor, 면 색은 --promo-fill) */
function TimeLapseArt() {
  return (
    <svg
      className="promo-svg"
      viewBox="0 0 240 200"
      fill="none"
      stroke="currentColor"
      strokeWidth="3"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {/* 뒤에 겹쳐진 이전 연도 사진 두 장 */}
      <g opacity="0.35">
        <rect x="26" y="20" width="176" height="126" rx="8" transform="rotate(-7 114 83)" />
      </g>
      <g opacity="0.55">
        <rect x="38" y="30" width="176" height="126" rx="8" transform="rotate(-3.5 126 93)" />
      </g>
      {/* 맨 앞 사진: 도로·필지 */}
      <rect x="52" y="42" width="176" height="126" rx="8" fill="#fff" />
      <path d="M52 108 H228" />
      <path d="M144 42 V168" />
      <path
        d="M100 42 C120 70 130 78 156 90 C176 100 184 112 196 168"
        strokeWidth="2.5"
        opacity="0.9"
      />
      <g fill="var(--promo-fill)" stroke="none">
        <rect x="70" y="60" width="16" height="16" rx="2" />
        <rect x="112" y="56" width="20" height="20" rx="2" />
        <rect x="160" y="60" width="18" height="14" rx="2" />
        <rect x="192" y="52" width="22" height="26" rx="2" />
        <rect x="70" y="128" width="20" height="14" rx="2" />
        <rect x="118" y="136" width="14" height="18" rx="2" />
        <rect x="192" y="122" width="24" height="18" rx="2" />
        <circle cx="152" cy="140" r="7" />
      </g>
      {/* 연도 슬라이더 */}
      <path d="M40 184 H240" strokeWidth="2.5" />
      <path d="M40 178 V190 M100 178 V190 M240 178 V190" strokeWidth="2.5" />
      <circle cx="160" cy="184" r="7" fill="currentColor" stroke="none" />
    </svg>
  );
}
