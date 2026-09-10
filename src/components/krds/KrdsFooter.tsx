import { ExternalLink, MapPinned } from 'lucide-react';
import { siteConfig } from '@/config/site.config';
import { animalUrl, themeUrl } from '@/config/links';

/** KRDS 푸터 (html/code/footer.html 의 f-logo / f-cnt / f-btm + krds-identifier 구조) */
export function KrdsFooter() {
  return (
    <footer id="krds-footer">
      <div className="inner">
        <div className="f-logo" id="about">
          <span className="logo-mark" aria-hidden="true">
            CI
          </span>
          <span className="logo-name">구리시</span>
        </div>
        <div className="f-cnt">
          <div className="f-info">
            <p className="info-addr">{siteConfig.contact.address}</p>
            <ul className="info-cs">
              <li>
                <strong className="strong">{siteConfig.contact.department}</strong>
                <span className="span">{siteConfig.contact.phone}</span>
              </li>
            </ul>
          </div>
          <div className="f-link">
            <div className="link-go">
              <a
                href={themeUrl('여름')}
                className="krds-btn medium text"
                target="_blank"
                rel="noopener"
                title="새 창 열림"
              >
                테마지도 <ExternalLink className="svg-icon" aria-hidden="true" />
              </a>
              <a
                href={animalUrl()}
                className="krds-btn medium text"
                target="_blank"
                rel="noopener"
                title="새 창 열림"
              >
                유기동물 찾기 <ExternalLink className="svg-icon" aria-hidden="true" />
              </a>
            </div>
          </div>
        </div>
        <div className="f-btm">
          <div className="f-btm-text">
            <p className="f-copy">© {new Date().getFullYear()} 구리시. All rights reserved.</p>
          </div>
          <div className="krds-identifier">
            <span className="logo">
              <MapPinned size={18} aria-hidden="true" />
              구리시
            </span>
            <span className="ban-txt">이 누리집은 구리시 누리집이에요.</span>
          </div>
          <p className="f-maker">제작 케이지오솔루션</p>
        </div>
      </div>
    </footer>
  );
}
