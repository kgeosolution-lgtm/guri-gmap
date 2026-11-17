import { spawnSync, execSync } from 'node:child_process';
import { readFileSync, writeFileSync, readdirSync, existsSync, mkdirSync, rmSync } from 'node:fs';
import path from 'node:path';
// 배포 설정 파일: 기본 deploy.config.json(kgeodata 미리보기), `--config deploy.guri.json`(구리 운영, npm run build:guri).
// 환경변수 DEPLOY_ORIGIN / DEPLOY_BASE / DEPLOY_PHOTO_BASE 는 파일 값을 한 번만 덮어쓴다.
const argi = process.argv.indexOf('--config');
const cfgFile = argi > -1 ? process.argv[argi + 1] : 'deploy.config.json';
if (!existsSync(cfgFile)) throw new Error(`배포 설정 파일이 없음: ${cfgFile}`);
const cfg = JSON.parse(readFileSync(cfgFile, 'utf8'));
console.log(`배포 설정: ${cfgFile}`);
const reviewWidget = cfg.reviewWidget !== false; // false 면 결과물에서 검토 위젯 script 를 뺀다
const commit =
  process.env.GITHUB_SHA ||
  (() => {
    try {
      return execSync('git rev-parse HEAD', { stdio: ['ignore', 'pipe', 'ignore'] })
        .toString()
        .trim();
    } catch {
      return 'local-verification';
    }
  })();
const origin = (process.env.DEPLOY_ORIGIN ?? cfg.origin).replace(/\/+$/, '');
const base = (process.env.DEPLOY_BASE ?? cfg.base).replace(/\/+$/, '');
if (!/^https?:\/\/[^/]+$/.test(origin))
  throw new Error(`origin 형식: https://도메인 (지금: ${origin})`);
if (base && !base.startsWith('/')) throw new Error(`base 는 / 로 시작(지금: ${base})`);
// 동물병원·동물약국 사진 폴더 — 절대 주소(https://…/) 또는 사이트 안 경로(/images/pet/, 아래에서 base 가 붙음)
const photoBase = (process.env.DEPLOY_PHOTO_BASE ?? cfg.photoBase ?? '').replace(/\/*$/, '/');
if (!/^(https?:\/\/|\/)/.test(photoBase))
  throw new Error(`photoBase 는 https://… 또는 / 로 시작(지금: ${photoBase})`);
if (photoBase.startsWith('/') && !existsSync(path.join('public', photoBase)))
  console.warn(
    `[경고] 사진 폴더 public${photoBase} 가 없어 팝업 사진이 안 보입니다 — kgeodata 서버의 /guri/img 내용을 복사하세요`,
  );
// 지도 4쪽의 정적 헤더를 메뉴 설정(shell-nav.json)과 맞춘다
const sync = spawnSync(process.execPath, ['scripts/sync-shell.mjs'], { stdio: 'inherit' });
if (sync.status !== 0) process.exit(sync.status || 1);
// 3D 지도용 웹씬 스냅샷(실패해도 배포는 계속)
spawnSync(process.execPath, ['scripts/fetch-scene.mjs'], { stdio: 'inherit' });
const result = spawnSync(process.execPath, ['node_modules/next/dist/bin/next', 'build'], {
  stdio: 'inherit',
  env: {
    ...process.env,
    GMAP_EXPORT: '1',
    NEXT_PUBLIC_BASE_PATH: base,
    NEXT_PUBLIC_MAPS_BASE: `${base}/maps`,
    NEXT_PUBLIC_SITE_ORIGIN: origin,
    NEXT_PUBLIC_REVIEW_WIDGET: reviewWidget ? '1' : '0',
  },
});
if (result.status !== 0) process.exit(result.status || 1);
// Rewrite only local asset paths in exported output. Source map/data scripts are untouched.
function walk(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) =>
    e.isDirectory() ? walk(path.join(dir, e.name)) : [path.join(dir, e.name)],
  );
}
for (const file of walk('out')) {
  if (!/\.(html|css|js|json|txt|svg)$/.test(file)) continue;
  let text = readFileSync(file, 'utf8');
  // 검토용 "수정 요청" 위젯 제거(reviewWidget:false) — 홈의 Next Script 태그와 지도 4쪽의 shell:review 표식
  if (!reviewWidget && file.endsWith('.html')) {
    text = text.replace(
      /<!-- shell:review -->[\s\S]*?<!-- \/shell:review -->/g,
      '<!-- shell:review: 제거됨(reviewWidget:false) -->',
    );
    text = text.replace(/<script[^>]*\/review\/review\.js[^>]*><\/script>/g, '');
  }
  // 사진 폴더 주소(theme.html 의 IMG_BASE)를 배포 설정 값으로 — 사이트 안 경로면 아래 /images/ 치환이 base 를 붙인다
  if (file.endsWith('maps/theme.html'))
    text = text.replace(/const IMG_BASE="[^"]*";/, `const IMG_BASE="${photoBase}";`);
  // 링크 미리보기 그림은 절대 주소여야 한다(지도 4쪽 정적 HTML)(아래 /images/ 치환보다 먼저)
  text = text.replace(/(property="og:image" content=")\/images\//g, `$1${origin}${base}/images/`);
  text = text.replace(/(["'(=])\/(images|fonts|maps|styles|review)\//g, `$1${base}/$2/`);
  text = text.replace(/(["'(=])\/icon\.svg/g, `$1${base}/icon.svg`);
  if (file.endsWith('.html'))
    text = text.replace(
      /href=(["'])\/(#(?:about|search))?\1/g,
      (_, q, hash = '') => `href=${q}${base}/${hash}${q}`,
    );
  writeFileSync(file, text);
}
for (const file of [
  'index.html',
  'v1/index.html',
  'maps/theme.html',
  'maps/animal.html',
  'maps/scene.html',
  'maps/aerial.html',
  'images/guri-emblem.png',
  ...(reviewWidget ? ['review/review.js'] : []),
]) {
  if (!existsSync(path.join('out', file))) throw new Error(`Missing output: ${file}`);
}
writeFileSync(
  'out/web.config',
  `<?xml version="1.0" encoding="utf-8"?>
<configuration><system.webServer>
<defaultDocument enabled="true"><files><clear/><add value="index.html"/></files></defaultDocument>
<directoryBrowse enabled="false"/>
<staticContent>
<remove fileExtension=".webp"/><mimeMap fileExtension=".webp" mimeType="image/webp"/>
<remove fileExtension=".woff2"/><mimeMap fileExtension=".woff2" mimeType="font/woff2"/>
<remove fileExtension=".json"/><mimeMap fileExtension=".json" mimeType="application/json"/>
<remove fileExtension=".svg"/><mimeMap fileExtension=".svg" mimeType="image/svg+xml"/>
<clientCache cacheControlMode="DisableCache"/>
</staticContent>
</system.webServer></configuration>`,
);
// 캐시: 루트는 캐시 끔(index.html·deployment.json 이 항상 새것) — 이름에 해시가 붙는 _next/static 은 1년, 글꼴·아이콘은 7일
const cacheCfg = (seconds) => `<?xml version="1.0" encoding="utf-8"?>
<configuration><system.webServer><staticContent>
<clientCache cacheControlMode="UseMaxAge" cacheControlMaxAge="${seconds >= 86400 ? Math.floor(seconds / 86400) + '.00:00:00' : '00:' + String(Math.floor(seconds / 60)).padStart(2, '0') + ':00'}"/>
</staticContent></system.webServer></configuration>`;
for (const [dir, sec] of [
  ['out/_next/static', 365 * 86400],
  ['out/fonts', 7 * 86400],
  ['out/maps/sym', 7 * 86400],
]) {
  if (existsSync(dir)) writeFileSync(path.join(dir, 'web.config'), cacheCfg(sec));
}
writeFileSync(
  'out/deployment.json',
  JSON.stringify(
    {
      commit,
      branch: process.env.GITHUB_REF_NAME || 'local',
      builtAt: new Date().toISOString(),
      url: `${origin}${base}/`,
      config: cfgFile, // 어느 설정으로 만든 결과물인지(deploy.guri.json = 구리 운영)
      reviewWidget,
    },
    null,
    2,
  ),
);
console.log(`Static deployment ready: out -> ${origin}${base}/`);
if (!reviewWidget) {
  rmSync('out/review', { recursive: true, force: true }); // 어느 페이지도 안 쓰므로 폴더째 뺀다
  const left = walk('out').filter(
    (f) => f.endsWith('.html') && /review\/review\.js/.test(readFileSync(f, 'utf8')),
  );
  if (left.length) throw new Error(`검토 위젯이 남아 있음: ${left.join(', ')}`);
  console.log('검토 위젯(review.js) 제거됨');
}
// 포털 업로드·반입용 zip (out 의 내용이 zip 루트에 오도록)
if (cfg.zip) {
  const stamp = new Date().toISOString().slice(0, 10).replace(/-/g, '');
  const name = `${cfg.zipName || 'site'}-${stamp}-${commit.slice(0, 7)}.zip`;
  mkdirSync('dist', { recursive: true });
  const zipPath = path.resolve('dist', name);
  rmSync(zipPath, { force: true });
  const r =
    process.platform === 'win32'
      ? spawnSync(
          'powershell',
          [
            '-NoProfile',
            '-Command',
            `Compress-Archive -Path out\\* -DestinationPath "${zipPath}" -Force`,
          ],
          { stdio: 'inherit' },
        )
      : spawnSync('zip', ['-qr', zipPath, '.'], { cwd: 'out', stdio: 'inherit' });
  if (r.status !== 0)
    throw new Error('zip 생성 실패 — Windows 는 PowerShell, 그 외는 zip 명령이 필요');
  console.log(`zip: dist/${name}`);
}
