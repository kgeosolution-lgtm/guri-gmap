import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = {
  title: '구리시 G-MAP 시민생활지도',
  description: '구리 시민이 지금 필요한 생활정보를 지도에서 쉽게 찾는 사이트',
};
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
