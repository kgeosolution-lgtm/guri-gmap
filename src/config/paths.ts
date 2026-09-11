export const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
export function homeUrl(fragment = '') {
  return `${basePath}/${fragment}`;
}
