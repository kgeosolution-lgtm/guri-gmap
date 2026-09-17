import { ChevronRight } from 'lucide-react';
import { siteConfig } from '@/config/site.config';
import { animalUrl, themeUrl } from '@/config/links';

/** KRDS 푸터 (html/code/footer.html 의 f-logo / f-cnt / f-btm + krds-identifier 구조) */
export function KrdsFooter() {
  return (
    <footer id="krds-footer">
      <div className="inner">
        <div className="f-logo" id="about">
          <img className="ci" src="/images/guri-ci.png" alt="구리시" height={40} />
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
              <a href={themeUrl('시즌·가을')} className="krds-btn medium text">
                우리동네 찾기 <ChevronRight className="svg-icon" aria-hidden="true" />
              </a>
              <a href={animalUrl()} className="krds-btn medium text">
                유기동물 찾기 <ChevronRight className="svg-icon" aria-hidden="true" />
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
              <img className="ci" src="/images/guri-ci.png" alt="구리시" height={22} />
            </span>
            <span className="ban-txt">이 누리집은 구리시 누리집이에요.</span>
          </div>
          <p className="f-maker">제작 케이지오솔루션</p>
        </div>
      </div>
    </footer>
  );
}
