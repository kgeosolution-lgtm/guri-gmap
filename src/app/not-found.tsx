import type { Metadata } from 'next';
import { SiteHeader } from '@/components/krds/SiteHeader';
import { homeUrl } from '@/config/paths';
import { siteConfig } from '@/config/site.config';
export const metadata: Metadata = { title: '페이지를 찾을 수 없어요 · 구리시 G-MAP' };
/** 없는 주소로 들어왔을 때(정적 배포의 404.html). IIS 가 404 를 이 파일로 보내 줘야 보인다 — docs/TEAM_HANDOFF.md 참고 */
export default function NotFound() {
  return (
    <>
      <SiteHeader variant="map" pageName="페이지 없음" />
      <main className="not-found">
        <p className="not-found-ic" aria-hidden="true">
          🗺️
        </p>
        <h1>페이지를 찾을 수 없어요</h1>
        <p>
          주소가 바뀌었거나 잘못 입력된 것 같아요.
          <br />
          아래에서 원하는 지도로 바로 가 보세요.
        </p>
        <div className="not-found-actions">
          <a className="not-found-btn primary" href={homeUrl()}>
            메인으로 가기
          </a>
          <a className="not-found-btn" href={`${siteConfig.mapsBase}/theme.html`}>
            우리동네 찾기
          </a>
        </div>
        <p className="not-found-foot">
          문의 {siteConfig.contact.department} {siteConfig.contact.phone}
        </p>
      </main>
    </>
  );
}
