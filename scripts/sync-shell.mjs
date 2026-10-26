#!/usr/bin/env node
/** 지도 4쪽(public/maps/*.html)의 정적 헤더를 src/config/shell-nav.json 한 곳에서 다시 써 넣는다.
 *  홈(SiteHeader.tsx)과 같은 마크업·같은 메뉴가 되도록. 메뉴를 바꾸면 json 만 고치고 `npm run sync:shell`(build:deploy 가 자동 실행).
 *  주소는 루트 기준(/maps/…, /#about) — build-deploy.mjs 가 배포 base 를 붙인다. (담당: 강민아) */
import { readFileSync, writeFileSync } from 'node:fs';
const nav = JSON.parse(readFileSync('src/config/shell-nav.json', 'utf8'));
const site = readFileSync('src/config/site.config.ts', 'utf8');
const features = {
  animalMap: /animalMap:\s*true/.test(site),
  reviewWidget: /reviewWidget:\s*true/.test(site),
};
const PAGES = {
  'public/maps/theme.html': { name: '우리동네 찾기', active: '우리동네 찾기' },
  'public/maps/animal.html': { name: '유기동물 찾기', active: '유기동물 찾기' },
  'public/maps/scene.html': { name: '3D입체지도', active: '3D입체지도' },
  'public/maps/aerial.html': { name: '항공사진 비교', active: '항공사진 비교' },
};
const href = (l) =>
  ({
    theme: () => `/maps/theme.html?group=${encodeURIComponent(l.group)}`,
    animal: () => '/maps/animal.html',
    scene: () => '/maps/scene.html',
    aerial: () => '/maps/aerial.html',
    external: () => l.href,
    home: () => `/${l.hash || ''}`,
  })[l.kind]();
const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
function links(active) {
  return nav.links
    .map((l) => {
      const a = `<a href="${href(l)}"${active === l.label ? ' aria-current="page"' : ''}${l.kind === 'external' ? ' target="_blank" rel="noopener"' : ''}>${esc(l.label)}</a>`;
      /* 숨긴 기능의 메뉴는 주석으로 남겨 두어, features 를 켜면 다시 나온다 */
      return l.feature && !features[l.feature]
        ? `<!-- ${esc(l.label)}(features.${l.feature}=false 로 숨김): ${a} -->`
        : a;
    })
    .join('');
}
function header({ name, active }) {
  return (
    `<!-- shell:header — scripts/sync-shell.mjs 가 src/config/shell-nav.json 으로 생성. 직접 고치지 말 것 -->` +
    `<header class="service-header map topbar"><div class="service-header-inner">` +
    `<a class="service-brand" href="/" aria-label="G-MAP 구리시 시민생활지도 홈"><img src="/images/guri-emblem.png" alt="" width="50" height="41"><span><b>G-MAP</b><small>구리시 시민생활지도</small></span></a>` +
    `<span class="service-page-name">${esc(name)}</span>` +
    `<nav class="service-nav" aria-label="주 메뉴">${links(active)}</nav>` +
    `<a class="service-search" href="/${nav.search.hash}">${esc(nav.search.label)} <span aria-hidden="true">↗</span></a>` +
    `<details class="service-mobile"><summary aria-label="메뉴 열기·닫기"><span></span><span></span></summary>` +
    `<nav aria-label="모바일 주 메뉴">${links(active)}<a href="/${nav.search.hash}">${esc(nav.search.label)}</a></nav></details>` +
    `</div></header><!-- /shell:header -->`
  );
}
function review() {
  const tag = '<script src="/review/review.js" defer></script>';
  return (
    '<!-- shell:review -->' +
    (features.reviewWidget
      ? tag
      : `<!-- 수정 요청 위젯(features.reviewWidget=false 로 끔): ${tag.replace(/</g, '&lt;')} -->`) +
    '<!-- /shell:review -->'
  );
}
let changed = 0;
for (const [file, cfg] of Object.entries(PAGES)) {
  const src = readFileSync(file, 'utf8');
  const re =
    /<!-- shell:header[\s\S]*?<!-- \/shell:header -->|<header class="service-header[\s\S]*?<\/header>/;
  if (!re.test(src)) throw new Error(`헤더를 못 찾음: ${file}`);
  let out = src.replace(re, header(cfg));
  /* 검토용 "수정 요청" 위젯(site.config features.reviewWidget) — 끄면 script 한 줄이 주석으로 바뀐다 */
  const rw = /<!-- shell:review -->[\s\S]*?<!-- \/shell:review -->/;
  if (!rw.test(out)) throw new Error(`검토 위젯 표식을 못 찾음: ${file}`);
  out = out.replace(rw, review());
  if (out !== src) {
    writeFileSync(file, out);
    changed++;
    console.log('헤더 갱신:', file);
  }
}
console.log(changed ? `${changed}개 파일 갱신` : '변경 없음(이미 최신)');
