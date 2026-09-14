import { spawnSync } from 'node:child_process';
import { readFileSync, writeFileSync, readdirSync, existsSync } from 'node:fs';
import path from 'node:path';
const base = '/app/guri';
const result = spawnSync(process.execPath, ['node_modules/next/dist/bin/next', 'build'], {
  stdio: 'inherit',
  env: {
    ...process.env,
    GMAP_EXPORT: '1',
    NEXT_PUBLIC_BASE_PATH: base,
    NEXT_PUBLIC_MAPS_BASE: `${base}/maps`,
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
  text = text.replace(/(["'(=])\/(images|fonts|maps|styles)\//g, `$1${base}/$2/`);
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
  'maps/aerial.html',
  'images/guri-emblem.png',
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
writeFileSync(
  'out/deployment.json',
  JSON.stringify(
    {
      commit: process.env.GITHUB_SHA || 'local-verification',
      branch: process.env.GITHUB_REF_NAME || 'local',
      builtAt: new Date().toISOString(),
    },
    null,
    2,
  ),
);
console.log(`Static deployment ready: out -> https://kgeodata.com${base}/`);
