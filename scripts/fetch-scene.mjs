/* 구리시 포털 웹씬 JSON 스냅샷 — 브라우저가 포털(/gmap)에 직접 접근하지 못해도(CORS) 3D 지도가 열리도록
   배포 빌드 때 서버 쪽에서 받아 public/maps/data/scene.json 으로 함께 올린다. */
import { writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { sanitizeScene } from './scene-sanitize.mjs';
const ID = 'b5e573a06e7f4195bb2f092aad19b253';
const url =
  process.env.SCENE_DATA_URL ||
  `https://www.guri.go.kr/gmap/sharing/rest/content/items/${ID}/data?f=json`;
const out = 'public/maps/data/scene.json';
try {
  const r = await fetch(url, {
    signal: AbortSignal.timeout(25000),
    headers: { accept: 'application/json' },
  });
  if (!r.ok) throw new Error('HTTP ' + r.status);
  const j = await r.json();
  if (j.error) throw new Error(j.error.message || JSON.stringify(j.error));
  if (!j.operationalLayers && !j.baseMap) throw new Error('웹씬 JSON 형식이 아닙니다');
  for (const line of sanitizeScene(j)) console.log('[scene snapshot] 정리:', line);
  mkdirSync('public/maps/data', { recursive: true });
  writeFileSync(
    out,
    JSON.stringify({ ...j, _snapshot: { itemId: ID, fetchedAt: new Date().toISOString() } }),
  );
  console.log(
    `[scene snapshot] 저장 ${out} | 레이어 ${(j.operationalLayers || []).length} | 슬라이드 ${j.presentation && j.presentation.slides ? j.presentation.slides.length : 0}`,
  );
} catch (e) {
  console.warn(
    '[scene snapshot] 포털에서 웹씬 JSON을 받지 못했습니다:',
    String((e && e.message) || e),
  );
  if (existsSync(out)) console.warn('   ↳ 저장소에 있는 기존 스냅샷을 그대로 씁니다:', out);
  else console.warn('   ↳ 스냅샷 없이 배포합니다. 페이지는 포털에서 직접 읽기를 시도합니다.');
}
