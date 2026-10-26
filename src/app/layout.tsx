import type { Metadata } from 'next';
import Script from 'next/script';
import './globals.css';
import { siteConfig } from '@/config/site.config';
import { absUrl } from '@/config/paths';
export const metadata: Metadata = {
  title: '구리시 G-MAP 시민생활지도',
  description: siteConfig.description,
  /* 카톡·문자·SNS 로 링크를 보낼 때 뜨는 미리보기(겨울 대표사진, 지도 4쪽도 같은 그림) */
  openGraph: {
    title: '구리시 G-MAP 시민생활지도',
    description: siteConfig.description,
    type: 'website',
    images: [{ url: absUrl('/images/og-cover.jpg'), width: 1200, height: 630 }],
  },
};
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        {children}
        {/* 오픈 전 검토용 "수정 요청" 위젯 — 오픈할 때 site.config features.reviewWidget 을 false 로 */}
        {siteConfig.features.reviewWidget && (
          <Script
            src={`${process.env.NEXT_PUBLIC_BASE_PATH || ''}/review/review.js`}
            strategy="afterInteractive"
          />
        )}
      </body>
    </html>
  );
}
