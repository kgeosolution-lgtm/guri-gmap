/** KRDS 건너뛰기 링크 (html/code/skip_link.html 구조) */
export function SkipLink() {
  return (
    <div id="krds-skip-link">
      <a href="#main-content">본문 바로가기</a>
    </div>
  );
}

/** KRDS 마스트헤드 (html/code/masthead.html 마크업 그대로). 태극 아이콘은 CSS ::before */
export function Masthead() {
  return (
    <div id="krds-masthead">
      <div className="toggle-wrap">
        <div className="toggle-head">
          <div className="inner">
            <span className="nuri-txt">이 누리집은 대한민국 공식 전자정부 누리집입니다.</span>
          </div>
        </div>
      </div>
    </div>
  );
}
