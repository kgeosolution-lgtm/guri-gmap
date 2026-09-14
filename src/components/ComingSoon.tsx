const items = ['공간정보(2D/3D)', '도시계획·통계', '열린데이터', '시민참여'];

/** 준비 중인 지도 — 한 줄짜리 칩 목록 (큰 섹션 없음) */
export function ComingSoon() {
  return (
    <section id="coming-soon" className="krds-section slim" aria-labelledby="coming-soon-title">
      <div className="krds-inner flex flex-wrap items-center gap-krds-5">
        <h2 id="coming-soon-title" className="m-0 text-[15px] font-bold text-gray-70">
          준비 중인 지도
        </h2>
        <ul className="krds-tag-wrap small m-0 list-none p-0">
          {items.map((label) => (
            <li key={label}>
              <span className="krds-btn-tag disabled">
                {label}
                <span className="krds-badge bg-gray">준비중</span>
              </span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
