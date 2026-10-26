export const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
/** 배포 주소의 origin(https://kgeodata.com). og:image 처럼 절대 주소가 필요한 곳에만 쓴다. 개발 중엔 빈 값. */
export const siteOrigin = process.env.NEXT_PUBLIC_SITE_ORIGIN || '';
/** 사이트 안 경로를 절대 주소로(배포 origin + base). origin 이 없으면 루트 기준 경로 그대로 */
export function absUrl(path: string) {
  return `${siteOrigin}${basePath}${path}`;
}
export function homeUrl(fragment = '') {
  return `${basePath}/${fragment}`;
}
