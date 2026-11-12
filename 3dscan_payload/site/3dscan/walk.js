/* ============================================================
   kgeoScan 걸어보기(워크스루) — 스플랫 뷰어(splat.html, three 0.165)와 메시 뷰어(viewer.js, three r128)가 같이 쓴다.
   window.KgeoWalk = { analyze, create, pointsFromObject3D, floorplanWorld, loadFloorplan }

   좌표: ARKit 월드(미터, +Y 위). 메시 뷰어는 모델을 가운데로 옮기므로 offset 으로 floorplan 좌표를 맞춘다.
   방법
     - 바닥 높이: 20 cm 칸마다 가장 낮은 점(하위 1 %, 떠다니는 점 제외)의 높이 분포에서 넓은 봉우리 중 가장 낮은 것.
       floorplan.json(worker/floorplan.py)이 있으면 그 floor_h 를 쓴다.
     - 점유 격자(약 10 cm 복셀): 바닥 클릭이 벽·가구 너머인지(시선), 서 있을 자리인지(머리까지 빈 기둥), 스캔 안쪽인지(발자국) 판단.
     - 화면 위 표시(바닥 링·추천 지점·측정선)는 SVG 로 그린다 → 렌더러와 상관없이 같은 모양.
   조작: 바닥 클릭/탭 → 0.6–0.8 s 이동, 드래그 → 제자리 둘러보기, 휠/두 손가락 → 화각, WASD·방향키 → 걷기, Esc → 나가기.
   ============================================================ */
(function (root) {
  'use strict';
  if (root.KgeoWalk) return;

  const EYE = 1.5;                  // 바닥 위 눈높이 (m)
  const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
  const now = () => (root.performance ? performance.now() : Date.now());
  const easeInOut = t => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

  /* ── 스타일 (한 번만) ── */
  function injectStyle() {
    if (document.getElementById('kgeoWalkStyle')) return;
    const s = document.createElement('style');
    s.id = 'kgeoWalkStyle';
    s.textContent = `
      .kw-svg { position:absolute; inset:0; width:100%; height:100%; pointer-events:none; z-index:5; overflow:visible; }
      .kw-ring { fill:rgba(255,255,255,.16); stroke:#fff; stroke-width:2.4; filter:drop-shadow(0 0 3px rgba(0,0,0,.55)); }
      .kw-ring-in { fill:rgba(255,255,255,.85); stroke:none; }
      .kw-way { fill:rgba(255,255,255,.07); stroke:rgba(255,255,255,.55); stroke-width:1.6; }
      .kw-way.hot { fill:rgba(56,189,248,.22); stroke:#38bdf8; stroke-width:2.2; }
      .kw-fade { position:absolute; inset:0; background:#000; opacity:0; pointer-events:none; transition:opacity .16s; z-index:6; }
      .kw-map { position:absolute; z-index:8; border-radius:8px; background:rgba(8,11,15,.72); border:1px solid rgba(148,163,184,.35);
                box-shadow:0 2px 10px rgba(0,0,0,.45); backdrop-filter:blur(6px); padding:6px; cursor:pointer; user-select:none; -webkit-user-select:none; touch-action:none; }
      .kw-map canvas { display:block; }
      .kw-map .kw-map-t { position:absolute; left:8px; top:5px; font:600 9.5px/1 -apple-system,'Pretendard',system-ui,sans-serif; color:#94a3b8; letter-spacing:.3px; pointer-events:none; }
      .kw-map.tl { left:10px; top:10px; } .kw-map.bl { left:10px; bottom:40px; }
      .kw-toast { position:absolute; left:50%; top:56px; transform:translateX(-50%); z-index:9; background:rgba(0,0,0,.66); color:#e2e8f0; font-size:12px;
                  padding:6px 12px; border-radius:16px; pointer-events:none; opacity:0; transition:opacity .25s; white-space:nowrap; }
      .kw-toast.on { opacity:1; }
    `;
    document.head.appendChild(s);
  }

  /* ════════════════════════════════════════════════════════════
     1) 장면 분석: 점들 → 바닥·천장·점유 격자·발자국
     P: Float32Array [x,y,z,...] (월드, y 위)   opt.floorPts: 바닥 추정에만 쓸 점(메시의 위를 보는 면 등)
     ════════════════════════════════════════════════════════════ */
  function sampleQuantiles(P, axis, qs, maxN) {
    const n = P.length / 3, step = Math.max(1, Math.floor(n / (maxN || 60000)));
    const a = new Float32Array(Math.ceil(n / step));
    let k = 0;
    for (let i = 0; i < n; i += step) a[k++] = P[i * 3 + axis];
    const s = a.subarray(0, k).sort();
    return qs.map(q => s[clamp(Math.floor(q * (k - 1)), 0, k - 1)]);
  }

  // 칸별 낮은/높은 점 → 높이 분포 봉우리
  function estimateLevels(P, lo, hi, cell) {
    const n = P.length / 3;
    const nx = Math.max(1, Math.ceil((hi[0] - lo[0]) / cell)), nz = Math.max(1, Math.ceil((hi[2] - lo[2]) / cell));
    const nc = nx * nz, cnt = new Int32Array(nc), ci = new Int32Array(n);
    for (let i = 0; i < n; i++) {
      const x = P[i * 3], y = P[i * 3 + 1], z = P[i * 3 + 2];
      if (!(x >= lo[0] && x < hi[0] && y >= lo[1] && y <= hi[1] && z >= lo[2] && z < hi[2])) { ci[i] = -1; continue; }
      const c = Math.floor((x - lo[0]) / cell) * nz + Math.floor((z - lo[2]) / cell);
      ci[i] = c; cnt[c]++;
    }
    const start = new Int32Array(nc + 1);
    for (let c = 0; c < nc; c++) start[c + 1] = start[c] + cnt[c];
    const ys = new Float32Array(start[nc]), fill = start.slice(0, nc);
    for (let i = 0; i < n; i++) if (ci[i] >= 0) ys[fill[ci[i]]++] = P[i * 3 + 1];
    const mins = [], maxs = [];
    for (let c = 0; c < nc; c++) {
      const m = cnt[c];
      if (m < 5) continue;
      const s = ys.subarray(start[c], start[c + 1]).sort();
      const k = Math.max(2, Math.floor(m * 0.01));
      mins.push(s[Math.min(k, m - 1)]);
      maxs.push(s[Math.max(0, m - 1 - k)]);
    }
    const bin = 0.04, nb = Math.max(3, Math.ceil((hi[1] - lo[1]) / bin) + 1);
    function peaks(vals) {
      const h = new Float32Array(nb);
      for (const v of vals) h[clamp(Math.floor((v - lo[1]) / bin), 0, nb - 1)]++;
      const sm = new Float32Array(nb);
      for (let b = 0; b < nb; b++) sm[b] = (h[Math.max(0, b - 1)] + 2 * h[b] + h[Math.min(nb - 1, b + 1)]) / 4;
      const out = [];
      for (let b = 0; b < nb; b++) {
        const l = b > 0 ? sm[b - 1] : -1, r = b < nb - 1 ? sm[b + 1] : -1;
        if (sm[b] > 0 && sm[b] > l && sm[b] >= r) {
          let mass = 0;
          for (let j = Math.max(0, b - 2); j <= Math.min(nb - 1, b + 2); j++) mass += h[j];
          out.push({ y: lo[1] + (b + 0.5) * bin, mass });
        }
      }
      return out;
    }
    const near = (vals, y, tol) => { const a = vals.filter(v => Math.abs(v - y) <= tol).sort((p, q) => p - q); return a.length ? a[a.length >> 1] : y; };
    const pf = peaks(mins);
    let floor = null;
    if (pf.length) {
      const mx = Math.max(...pf.map(p => p.mass)), thr = Math.max(4, 0.25 * mx), lim = lo[1] + 0.7 * (hi[1] - lo[1]);
      const c = pf.filter(p => p.mass >= thr && p.y <= lim).sort((a, b) => a.y - b.y)[0];
      if (c) floor = { y: near(mins, c.y, 0.06), mass: c.mass };
    }
    let ceil = null;
    if (floor) {
      const pc = peaks(maxs).filter(p => p.y >= floor.y + 1.9);
      if (pc.length) {
        const mx = Math.max(...pc.map(p => p.mass)), thr = Math.max(4, 0.25 * mx);
        const c = pc.filter(p => p.mass >= thr).sort((a, b) => b.y - a.y)[0];
        if (c) ceil = { y: near(maxs, c.y, 0.06), mass: c.mass };
      }
    }
    return { floor, ceil, cells: mins.length };
  }

  function analyze(P, opt) {
    opt = opt || {};
    const n = P.length / 3;
    if (n < 200) return { ok: false, reason: 'few points' };
    const qx = sampleQuantiles(P, 0, [0.005, 0.995]), qy = sampleQuantiles(P, 1, [0.005, 0.995]), qz = sampleQuantiles(P, 2, [0.005, 0.995]);
    const pad = 0.25;
    const lo = [qx[0] - pad, qy[0] - pad, qz[0] - pad], hi = [qx[1] + pad, qy[1] + pad, qz[1] + pad];
    // 바닥·천장
    let floorY = Number.isFinite(opt.floorY) ? opt.floorY : null, ceilY = Number.isFinite(opt.ceilY) ? opt.ceilY : null, floorSrc = floorY != null ? (opt.floorSrc || 'given') : null;
    if (floorY == null || ceilY == null) {
      const lv = estimateLevels(opt.floorPts && opt.floorPts.length > 600 ? opt.floorPts : P, lo, hi, 0.2);
      if (floorY == null && lv.floor) { floorY = lv.floor.y; floorSrc = 'estimate'; }
      if (ceilY == null && lv.ceil && floorY != null && lv.ceil.y > floorY + 1.8) ceilY = lv.ceil.y;
    }
    if (floorY == null) return { ok: false, reason: 'no floor' };
    lo[1] = Math.min(lo[1], floorY - 0.3);
    // 점유 격자
    const vol = (hi[0] - lo[0]) * (hi[1] - lo[1]) * (hi[2] - lo[2]);
    const v = clamp(Math.cbrt(vol / 2.0e6), opt.voxelMin || 0.08, 0.3);
    const nx = Math.ceil((hi[0] - lo[0]) / v), ny = Math.ceil((hi[1] - lo[1]) / v), nz = Math.ceil((hi[2] - lo[2]) / v);
    const occ = new Uint8Array(nx * ny * nz);
    for (let i = 0; i < n; i++) {
      const ix = Math.floor((P[i * 3] - lo[0]) / v), iy = Math.floor((P[i * 3 + 1] - lo[1]) / v), iz = Math.floor((P[i * 3 + 2] - lo[2]) / v);
      if (ix < 0 || iy < 0 || iz < 0 || ix >= nx || iy >= ny || iz >= nz) continue;
      const k = (ix * nz + iz) * ny + iy;
      if (occ[k] < 255) occ[k]++;
    }
    const solidMin = opt.solidMin || 2;
    const S = { ok: true, lo, hi, v, nx, ny, nz, occ, solidMin, floorY, ceilY, floorSrc, n };
    const capY = ceilY != null ? ceilY + 0.1 : floorY + 2.8;
    S.capY = capY;
    S.eye = ceilY != null ? clamp(Math.min(EYE, ceilY - floorY - 0.3), 1.0, EYE) : EYE;
    const iyOf = y => clamp(Math.floor((y - lo[1]) / v), 0, ny - 1);
    // 기둥별: 아무 점이나(발자국), 몸 높이 장애물 수, 바닥 보임
    const nc = nx * nz, any = new Uint8Array(nc), obs = new Uint8Array(nc), low = new Uint8Array(nc), tall = new Uint8Array(nc), flo = new Uint8Array(nc);
    const dens = new Float32Array(nc);       // 기둥마다 점 수 (스플랫: 촬영이 적은 곳은 성기다 → '흐릴 수 있어요' 안내)
    const yA = iyOf(floorY - 0.15), yB = iyOf(capY), yO0 = iyOf(floorY + 0.35), yO1 = iyOf(floorY + 1.75), yT0 = iyOf(floorY + 1.2), yF1 = iyOf(floorY + 0.12);
    for (let c = 0; c < nc; c++) {
      const b = c * ny;
      let a = 0, o = 0, t = 0, f = 0;
      for (let iy = yA; iy <= yB; iy++) {
        dens[c] += occ[b + iy];
        if (occ[b + iy] < solidMin) continue;
        a = 1;
        if (iy <= yF1) f = 1;
        if (iy >= yO0 && iy <= yO1) { o++; if (iy >= yT0) t++; }
      }
      any[c] = a; obs[c] = Math.min(255, o); tall[c] = Math.min(255, t); low[c] = o - t > 0 ? 1 : 0; flo[c] = f;
    }
    // 발자국: 닫기(팽창→침식) + 막힌 구멍 채우기
    const dil = (src, r) => { const out = new Uint8Array(nc); for (let ix = 0; ix < nx; ix++) for (let iz = 0; iz < nz; iz++) { if (!src[ix * nz + iz]) continue; for (let dx = -r; dx <= r; dx++) for (let dz = -r; dz <= r; dz++) { const x = ix + dx, z = iz + dz; if (x >= 0 && z >= 0 && x < nx && z < nz) out[x * nz + z] = 1; } } return out; };
    const ero = (src, r) => { const out = new Uint8Array(nc); for (let ix = 0; ix < nx; ix++) for (let iz = 0; iz < nz; iz++) { let ok = 1; for (let dx = -r; dx <= r && ok; dx++) for (let dz = -r; dz <= r; dz++) { const x = ix + dx, z = iz + dz; if (x < 0 || z < 0 || x >= nx || z >= nz || !src[x * nz + z]) { ok = 0; break; } } out[ix * nz + iz] = ok; } return out; };
    const r = Math.max(1, Math.round(0.2 / v));
    let fp = ero(dil(any, r), r);
    const seen = new Uint8Array(nc), stack = [];
    for (let ix = 0; ix < nx; ix++) for (let iz = 0; iz < nz; iz++) if ((ix === 0 || iz === 0 || ix === nx - 1 || iz === nz - 1) && !fp[ix * nz + iz]) { seen[ix * nz + iz] = 1; stack.push(ix * nz + iz); }
    while (stack.length) {
      const c = stack.pop(), ix = (c / nz) | 0, iz = c % nz;
      for (const [dx, dz] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
        const x = ix + dx, z = iz + dz;
        if (x < 0 || z < 0 || x >= nx || z >= nz) continue;
        const k = x * nz + z;
        if (!seen[k] && !fp[k]) { seen[k] = 1; stack.push(k); }
      }
    }
    for (let c = 0; c < nc; c++) if (!fp[c] && !seen[c]) fp[c] = 1;
    let area = 0;
    for (let c = 0; c < nc; c++) area += fp[c];
    area *= v * v;
    // 설 수 있는 안쪽: 발자국 가장자리(스캔 끝, 덜 찍혀 흐린 곳)에서 30 cm 이상 들어온 곳
    const core = ero(fp, Math.max(1, Math.round(0.3 / v)));
    const dv = [];
    for (let c = 0; c < nc; c++) if (any[c]) dv.push(dens[c]);
    dv.sort((p, q) => p - q);
    const densRef = Math.max(1, dv.length ? dv[dv.length >> 1] : 1);    // 점이 있는 기둥의 중앙값
    Object.assign(S, { any, obs, low, tall, flo, fp, core, dens, densRef, footprintM2: area });
    S.walkable = area >= 2.0 && Math.max(hi[0] - lo[0], hi[2] - lo[2]) >= 1.8 && (qy[1] - floorY) >= 1.0;
    // 조회 함수
    S.cellOf = (x, z) => { const ix = Math.floor((x - lo[0]) / v), iz = Math.floor((z - lo[2]) / v); return ix < 0 || iz < 0 || ix >= nx || iz >= nz ? -1 : ix * nz + iz; };
    S.solidAt = (x, y, z) => {
      const ix = Math.floor((x - lo[0]) / v), iy = Math.floor((y - lo[1]) / v), iz = Math.floor((z - lo[2]) / v);
      if (ix < 0 || iy < 0 || iz < 0 || ix >= nx || iy >= ny || iz >= nz) return false;
      return occ[(ix * nz + iz) * ny + iy] >= solidMin;
    };
    S.inFootprint = (x, z) => { const c = S.cellOf(x, z); return c >= 0 && fp[c] === 1; };
    const br = Math.max(1, Math.round(0.12 / v)), bt = Math.max(br, Math.round(0.3 / v));
    const obsTol = opt.obsTol != null ? opt.obsTol : 1;
    // 평면도가 있으면 방 다각형 안, 벽선에서 30 cm 이상 (유리창·커튼은 점유 격자에 안 잡히므로)
    const rooms = opt.plan && Array.isArray(opt.plan.rooms) ? opt.plan.rooms.filter(r => r.poly && r.poly.length > 2) : [];
    const segDist = (x, z, a, b) => { const ux = b[0] - a[0], uz = b[1] - a[1], L2 = ux * ux + uz * uz || 1e-9; const t = clamp(((x - a[0]) * ux + (z - a[1]) * uz) / L2, 0, 1); return Math.hypot(x - a[0] - ux * t, z - a[1] - uz * t); };
    const planOK = (x, z) => {
      if (!rooms.length) return true;
      for (const r of rooms) {
        if (!pointInPoly(x, z, r.poly)) continue;
        let ok = true;
        for (let i = 0; i < r.poly.length && ok; i++) if (segDist(x, z, r.poly[i], r.poly[(i + 1) % r.poly.length]) < 0.3) ok = false;
        if (ok) return true;
      }
      return false;
    };
    S.standable = (x, z) => {
      const c = S.cellOf(x, z);
      if (c < 0 || !core[c]) return false;
      const ix = (c / nz) | 0, iz = c % nz;
      for (let dx = -bt; dx <= bt; dx++) for (let dz = -bt; dz <= bt; dz++) {
        const X = ix + dx, Z = iz + dz;
        if (X < 0 || Z < 0 || X >= nx || Z >= nz) return false;
        const k = X * nz + Z, near = Math.abs(dx) <= br && Math.abs(dz) <= br;
        if (near && obs[k] > obsTol) return false;          // 몸통(약 25 cm) 안 가구·벽
        if (tall[k] > 1 + obsTol) return false;             // 30 cm 안 벽·키 큰 가구
      }
      return planOK(x, z);
    };
    // 가까운 설 자리 (같은 점이면 그대로)
    S.snap = (x, z, maxR) => {
      if (S.standable(x, z)) return [x, z];
      const R = Math.ceil((maxR || 0.4) / v);
      let best = null, bd = 1e9;
      for (let dx = -R; dx <= R; dx++) for (let dz = -R; dz <= R; dz++) {
        const d = dx * dx + dz * dz;
        if (d > R * R || d >= bd) continue;
        const X = x + dx * v, Z = z + dz * v;
        if (S.standable(X, Z)) { bd = d; best = [X, Z]; }
      }
      return best;
    };
    // 시선: a → b 사이(양 끝 근처·바닥 근처 제외)에 막힌 칸이 있나
    S.clearLine = (a, b, opts) => {
      const dx = b.x - a.x, dy = b.y - a.y, dz = b.z - a.z, L = Math.hypot(dx, dy, dz);
      const skipA = (opts && opts.skipA) || 0.3, skipB = (opts && opts.skipB) || 0.08, minY = floorY + ((opts && opts.minAbove) || 0.2);
      const st = v * 0.5;
      for (let t = skipA; t < L - skipB; t += st) {
        const x = a.x + dx * t / L, y = a.y + dy * t / L, z = a.z + dz * t / L;
        if (y < minY) continue;
        if (S.solidAt(x, y, z)) return false;
      }
      return true;
    };
    // 화면 광선이 처음 닿는 막힌 칸 (측정 예비용)
    S.marchHit = (o, d, maxT) => {
      const st = v * 0.4;
      for (let t = 0.05; t < (maxT || 30); t += st) {
        const x = o.x + d.x * t, y = o.y + d.y * t, z = o.z + d.z * t;
        if (S.solidAt(x, y, z)) return t;
      }
      return null;
    };
    // 추천 지점(네이버식 바닥 링): 바닥이 보인 설 자리 중 약 1.3 m 간격
    //   바닥이 거의 안 찍힌 스캔(벽·천장 위주)은 바닥 조건을 빼고 다시 뽑는다
    const gs = Math.max(1, Math.round(1.3 / v)), rr = Math.max(1, Math.round(0.25 / v));
    const pickWay = needFloor => {
      const way = [];
      for (let ix = Math.floor(gs / 2); ix < nx; ix += gs) for (let iz = Math.floor(gs / 2); iz < nz; iz += gs) {
        // 칸 묶음 안에서 설 자리 하나 (가운데에 가까운 것)
        let best = null, bd = 1e9;
        for (let dx = -rr; dx <= rr; dx++) for (let dz = -rr; dz <= rr; dz++) {
          const X = ix + dx, Z = iz + dz;
          if (X < 0 || Z < 0 || X >= nx || Z >= nz) continue;
          const c = X * nz + Z;
          if (!fp[c] || (needFloor && !flo[c])) continue;
          const x = lo[0] + (X + 0.5) * v, z = lo[2] + (Z + 0.5) * v;
          if (!S.standable(x, z)) continue;
          const d = dx * dx + dz * dz;
          if (d < bd) { bd = d; best = [x, z]; }
        }
        if (best) way.push(best);
      }
      return way;
    };
    let way = pickWay(true);
    if (way.length < Math.max(3, area / 6)) way = pickWay(false);
    S.waypoints = way.slice(0, 80);
    return S;
  }

  /* ── 메시(Object3D) → 점: 삼각형 중심 + 큰 삼각형 안쪽 표본, 위를 보는 면은 바닥 추정용으로 따로 ── */
  function pointsFromObject3D(THREE, obj, opt) {
    opt = opt || {};
    const maxPts = opt.max || 500000, spacing = opt.spacing || 0.05;
    obj.updateMatrixWorld(true);
    const out = [], up = [];
    const a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3(), e1 = new THREE.Vector3(), e2 = new THREE.Vector3(), nrm = new THREE.Vector3();
    let total = 0;
    obj.traverse(m => { if (m.isMesh && m.geometry && m.geometry.attributes.position) total += (m.geometry.index ? m.geometry.index.count : m.geometry.attributes.position.count) / 3; });
    const step = Math.max(1, Math.floor(total / maxPts));
    obj.traverse(m => {
      if (!m.isMesh || !m.geometry || !m.geometry.attributes.position) return;
      const pos = m.geometry.attributes.position, idx = m.geometry.index, mw = m.matrixWorld;
      const nt = (idx ? idx.count : pos.count) / 3;
      for (let t = 0; t < nt; t += step) {
        const i0 = idx ? idx.getX(t * 3) : t * 3, i1 = idx ? idx.getX(t * 3 + 1) : t * 3 + 1, i2 = idx ? idx.getX(t * 3 + 2) : t * 3 + 2;
        a.fromBufferAttribute(pos, i0).applyMatrix4(mw); b.fromBufferAttribute(pos, i1).applyMatrix4(mw); c.fromBufferAttribute(pos, i2).applyMatrix4(mw);
        e1.subVectors(b, a); e2.subVectors(c, a); nrm.crossVectors(e1, e2);
        const area2 = nrm.length();
        if (area2 < 1e-12) continue;
        const ny = nrm.y / area2;
        const cx = (a.x + b.x + c.x) / 3, cy = (a.y + b.y + c.y) / 3, cz = (a.z + b.z + c.z) / 3;
        out.push(cx, cy, cz);
        if (ny > 0.85) up.push(cx, cy, cz);
        const extra = Math.min(40, Math.floor(area2 * 0.5 / (spacing * spacing)));
        for (let k = 0; k < extra; k++) {
          let u = Math.random(), w = Math.random();
          if (u + w > 1) { u = 1 - u; w = 1 - w; }
          const x = a.x + e1.x * u + e2.x * w, y = a.y + e1.y * u + e2.y * w, z = a.z + e1.z * u + e2.z * w;
          out.push(x, y, z);
          if (ny > 0.85) up.push(x, y, z);
        }
      }
    });
    return { P: new Float32Array(out), up: new Float32Array(up) };
  }

  /* ── floorplan.json (worker/floorplan.py) → 월드 좌표 ── */
  function floorplanWorld(fp, offset) {
    if (!fp || !fp.frame || !Array.isArray(fp.rooms)) return null;
    const off = offset || [0, 0, 0];
    const M = fp.frame.plan_to_input || [[1, 0], [0, 1]];
    const th = (fp.frame.theta_deg || 0) * Math.PI / 180;
    const toW = (u, v) => { const X = M[0][0] * u + M[0][1] * v, Y = M[1][0] * u + M[1][1] * v; return [X + off[0], -Y + off[2]]; };
    const floorH = fp.levels && Number.isFinite(fp.levels.floor_h) ? fp.levels.floor_h : fp.frame.floor_level;
    const ceilH = fp.levels && Number.isFinite(fp.levels.ceiling_h) ? fp.levels.ceiling_h : null;
    return {
      theta: th,
      floorY: Number.isFinite(floorH) ? floorH + off[1] : null,
      ceilY: Number.isFinite(ceilH) ? ceilH + off[1] : null,
      rooms: fp.rooms.map(r => ({
        name: r.name, area: r.area_m2,
        poly: (r.polygon || []).map(p => toW(p[0], p[1])),
        label: r.label_at ? toW(r.label_at[0], r.label_at[1]) : null,
        edges: (r.edges || []).map(e => ({ a: toW(e.a[0], e.a[1]), b: toW(e.b[0], e.b[1]), wall: e.kind === 'wall' })),
      })),
      openings: fp.openings || [],
    };
  }
  async function loadFloorplan(url) {
    try {
      const r = await fetch(url, { cache: 'no-store' });
      if (!r.ok) return null;
      const j = await r.json();
      return j && j.rooms ? j : null;
    } catch (e) { return null; }
  }
  function pointInPoly(x, z, poly) {
    let ins = false;
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      const xi = poly[i][0], zi = poly[i][1], xj = poly[j][0], zj = poly[j][1];
      if ((zi > z) !== (zj > z) && x < (xj - xi) * (z - zi) / (zj - zi) + xi) ins = !ins;
    }
    return ins;
  }

  /* ════════════════════════════════════════════════════════════
     2) 걷기 컨트롤러
     opt: { THREE, camera, dom(입력 받을 캔버스), container(겹쳐 그릴 부모, position 있음), getControls()→OrbitControls,
            scene(analyze 결과), plan(floorplanWorld 결과|null), isBusy()→측정 중이면 true, mapCorner('tl'|'bl'),
            mapSize, onChange(active), onMove(), help(el|null), helpText{walk,orbit} }
     ════════════════════════════════════════════════════════════ */
  function create(opt) {
    injectStyle();
    const THREE = opt.THREE, cam = opt.camera, dom = opt.dom, box = opt.container, S = opt.scene, plan = opt.plan || null;
    const ctl = () => (opt.getControls ? opt.getControls() : null);
    const W = {
      active: false, pos: new THREE.Vector3(), yaw: 0, pitch: 0, fov: 60, eye: S.eye,
      anim: null, keys: {}, hover: null, lastT: 0, saved: null,
    };
    const tmp = new THREE.Vector3(), tmp2 = new THREE.Vector3(), fwd = new THREE.Vector3();
    const dir = (yaw, pitch, out) => out.set(-Math.sin(yaw) * Math.cos(pitch), Math.sin(pitch), -Math.cos(yaw) * Math.cos(pitch));

    /* ── 겹쳐 그리기 ── */
    const NS = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(NS, 'svg'); svg.setAttribute('class', 'kw-svg'); svg.style.display = 'none';
    const gWay = document.createElementNS(NS, 'g'); svg.appendChild(gWay);
    const ring = document.createElementNS(NS, 'path'); ring.setAttribute('class', 'kw-ring'); svg.appendChild(ring);
    const ringIn = document.createElementNS(NS, 'path'); ringIn.setAttribute('class', 'kw-ring-in'); svg.appendChild(ringIn);
    box.appendChild(svg);
    const fade = document.createElement('div'); fade.className = 'kw-fade'; box.appendChild(fade);
    const toast = document.createElement('div'); toast.className = 'kw-toast'; box.appendChild(toast);
    let toastT = 0;
    function showToast(msg, ms) { toast.textContent = msg; toast.classList.add('on'); clearTimeout(toastT); toastT = setTimeout(() => toast.classList.remove('on'), ms || 1800); }

    function sizeOf() { return { w: box.clientWidth || dom.clientWidth || 1, h: box.clientHeight || dom.clientHeight || 1 }; }
    // 월드 점 → 화면 px (카메라 뒤면 null)
    function toScreen(x, y, z, sz) {
      tmp.set(x, y, z).applyMatrix4(cam.matrixWorldInverse);
      if (tmp.z > -0.05) return null;
      tmp.applyMatrix4(cam.projectionMatrix);
      return [(tmp.x + 1) / 2 * sz.w, (1 - tmp.y) / 2 * sz.h];
    }
    function ellipsePath(cx, cz, r, sz, seg) {
      let d = '';
      for (let i = 0; i <= (seg || 40); i++) {
        const a = i / (seg || 40) * Math.PI * 2;
        const p = toScreen(cx + Math.cos(a) * r, S.floorY + 0.015, cz + Math.sin(a) * r, sz);
        if (!p) return null;
        d += (i ? 'L' : 'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1);
      }
      return d + 'Z';
    }
    // 화면 좌표 → 광선
    function rayFrom(sx, sy, sz) {
      const ndx = sx / sz.w * 2 - 1, ndy = -(sy / sz.h) * 2 + 1;
      const o = new THREE.Vector3().setFromMatrixPosition(cam.matrixWorld);
      const d = new THREE.Vector3(ndx, ndy, 0.5).unproject(cam).sub(o).normalize();
      return { o, d };
    }
    // 화면 좌표 → 갈 수 있는 바닥 점 {x,z} | null
    function floorTarget(sx, sy) {
      const sz = sizeOf(), r = rayFrom(sx, sy, sz);
      if (r.d.y > -0.03) return null;
      const t = (S.floorY - r.o.y) / r.d.y;
      if (!(t > 0.2 && t < 30)) return null;
      const p = r.o.clone().addScaledVector(r.d, t);
      if (!S.inFootprint(p.x, p.z) && !inPlan(p.x, p.z)) return null;
      if (!S.clearLine(r.o, p)) return null;                // 벽·가구 너머 → 무시
      const s = S.snap(p.x, p.z, 0.4);
      if (!s) return null;
      if ((s[0] !== p.x || s[1] !== p.z) && !S.clearLine(r.o, { x: s[0], y: S.floorY, z: s[1] })) return null;   // 옮긴 자리도 보여야
      // 추천 지점 가까이면 그 자리로
      const w = nearWaypointPx(sx, sy, sz);
      return w || { x: s[0], z: s[1] };
    }
    function inPlan(x, z) { return !!(plan && plan.rooms.some(r => r.poly.length > 2 && pointInPoly(x, z, r.poly))); }

    /* ── 추천 지점 ── */
    let wayVis = [], wayKey = '';
    function visibleWaypoints() {
      const key = W.pos.x.toFixed(2) + ',' + W.pos.z.toFixed(2);
      if (key === wayKey) return wayVis;
      wayKey = key;
      const eye = tmp2.copy(W.pos);
      wayVis = (S.waypoints || []).filter(([x, z]) => {
        const d = Math.hypot(x - eye.x, z - eye.z);
        if (d < 0.7 || d > 8) return false;
        return S.clearLine(eye, { x, y: S.floorY + 0.02, z });
      });
      return wayVis;
    }
    function nearWaypointPx(sx, sy, sz) {
      let best = null, bd = 40 * 40;
      for (const [x, z] of visibleWaypoints()) {
        const p = toScreen(x, S.floorY, z, sz);
        if (!p) continue;
        const d = (p[0] - sx) ** 2 + (p[1] - sy) ** 2;
        if (d < bd) { bd = d; best = { x, z }; }
      }
      return best;
    }

    /* ── 미니맵 ── */
    const map = buildMinimap();
    function buildMinimap() {
      const th = plan ? plan.theta : 0, c = Math.cos(th), s = Math.sin(th);
      const toUV = (x, z) => { const X = x, Y = -z; return [X * c + Y * s, -X * s + Y * c]; };
      const fromUV = (u, v) => { const X = u * c - v * s, Y = u * s + v * c; return [X, -Y]; };
      // 범위: 발자국 + 평면도
      let u0 = 1e9, u1 = -1e9, v0 = 1e9, v1 = -1e9;
      const ext = (x, z) => { const [u, v] = toUV(x, z); if (u < u0) u0 = u; if (u > u1) u1 = u; if (v < v0) v0 = v; if (v > v1) v1 = v; };
      for (let ix = 0; ix < S.nx; ix++) for (let iz = 0; iz < S.nz; iz++) if (S.fp[ix * S.nz + iz]) { const x = S.lo[0] + (ix + 0.5) * S.v, z = S.lo[2] + (iz + 0.5) * S.v; ext(x - S.v / 2, z - S.v / 2); ext(x + S.v / 2, z + S.v / 2); }
      if (plan) for (const r of plan.rooms) for (const p of r.poly) ext(p[0], p[1]);
      if (!(u1 > u0)) return null;
      const margin = 0.3; u0 -= margin; u1 += margin; v0 -= margin; v1 += margin;
      const maxPx = opt.mapSize || 180;
      const sc = maxPx / Math.max(u1 - u0, v1 - v0);
      const cw = Math.max(60, Math.round((u1 - u0) * sc)), ch = Math.max(60, Math.round((v1 - v0) * sc));
      const dpr = Math.min(2, root.devicePixelRatio || 1);
      const wrap = document.createElement('div'); wrap.className = 'kw-map ' + (opt.mapCorner || 'tl'); wrap.style.display = 'none';
      wrap.title = '미니맵: 누르면 그 자리로 이동';
      const t = document.createElement('div'); t.className = 'kw-map-t'; t.textContent = plan ? '평면도' : '미니맵';
      const cv = document.createElement('canvas'); cv.width = cw * dpr; cv.height = ch * dpr; cv.style.width = cw + 'px'; cv.style.height = ch + 'px';
      wrap.appendChild(cv); wrap.appendChild(t); box.appendChild(wrap);
      const toPx = (x, z) => { const [u, v] = toUV(x, z); return [(u - u0) * sc, (v1 - v) * sc]; };
      // 바탕 (한 번)
      const base = document.createElement('canvas'); base.width = cv.width; base.height = cv.height;
      const g = base.getContext('2d'); g.scale(dpr, dpr);
      // 칸을 불투명한 색으로 겹쳐 그려 격자무늬가 안 생기게: 바닥 → 낮은 가구 → 벽·높은 가구 순
      const cs = S.v * sc * 1.15 + 0.5;
      //   평면도가 있으면 점 바탕은 흐리게(평면도 벽선이 주인공)
      const layers = plan ? [[k => true, '#172131'], [k => S.obs[k] >= 2, '#2a3850']]
                          : [[k => true, '#1f2a3a'], [k => S.obs[k] >= 2 && S.tall[k] < 2, '#4b5a70'], [k => S.tall[k] >= 2, '#cbd5e1']];
      for (const [want, col] of layers) {
        g.fillStyle = col;
        for (let ix = 0; ix < S.nx; ix++) for (let iz = 0; iz < S.nz; iz++) {
          const k = ix * S.nz + iz;
          if (!S.fp[k] || !want(k)) continue;
          const [px, py] = toPx(S.lo[0] + (ix + 0.5) * S.v, S.lo[2] + (iz + 0.5) * S.v);
          g.fillRect(px - cs / 2, py - cs / 2, cs, cs);
        }
      }
      if (plan) {
        g.lineJoin = 'round';
        for (const r of plan.rooms) {
          if (r.poly.length < 3) continue;
          g.beginPath(); r.poly.forEach((p, i) => { const q = toPx(p[0], p[1]); i ? g.lineTo(q[0], q[1]) : g.moveTo(q[0], q[1]); }); g.closePath();
          g.fillStyle = 'rgba(56,189,248,.10)'; g.fill();
          for (const e of r.edges) {
            const a = toPx(e.a[0], e.a[1]), b = toPx(e.b[0], e.b[1]);
            g.beginPath(); g.moveTo(a[0], a[1]); g.lineTo(b[0], b[1]);
            g.setLineDash(e.wall ? [] : [3, 3]);
            g.strokeStyle = e.wall ? 'rgba(241,245,249,.95)' : 'rgba(148,163,184,.7)'; g.lineWidth = e.wall ? 2.2 : 1; g.stroke();
          }
          g.setLineDash([]);
          if (r.label && r.name) {
            const q = toPx(r.label[0], r.label[1]);
            g.font = '600 9px -apple-system, "Pretendard", system-ui, sans-serif'; g.textAlign = 'center'; g.fillStyle = 'rgba(226,232,240,.85)';
            g.fillText(r.name, q[0], q[1]);
            if (r.area) { g.font = '9px ui-monospace, monospace'; g.fillStyle = 'rgba(148,163,184,.9)'; g.fillText(r.area.toFixed(1) + '㎡', q[0], q[1] + 10); }
          }
        }
      }
      const ctx = cv.getContext('2d');
      let lastKey = '';
      function draw(force) {
        const key = W.pos.x.toFixed(2) + W.pos.z.toFixed(2) + W.yaw.toFixed(3) + W.fov.toFixed(1);
        if (!force && key === lastKey) return;
        lastKey = key;
        ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.clearRect(0, 0, cv.width, cv.height); ctx.drawImage(base, 0, 0);
        ctx.scale(dpr, dpr);
        const [px, py] = toPx(W.pos.x, W.pos.z);
        // 보는 방향 부채꼴 (가로 화각)
        const f = dir(W.yaw, 0, tmp), [qx, qy] = toPx(W.pos.x + f.x, W.pos.z + f.z);
        const ang = Math.atan2(qy - py, qx - px);
        const sz = sizeOf();
        const hf = Math.atan(Math.tan(W.fov * Math.PI / 360) * sz.w / sz.h);
        const R = 34;
        const grd = ctx.createRadialGradient(px, py, 2, px, py, R);
        grd.addColorStop(0, 'rgba(56,189,248,.55)'); grd.addColorStop(1, 'rgba(56,189,248,0)');
        ctx.beginPath(); ctx.moveTo(px, py); ctx.arc(px, py, R, ang - hf, ang + hf); ctx.closePath(); ctx.fillStyle = grd; ctx.fill();
        ctx.beginPath(); ctx.arc(px, py, 5, 0, Math.PI * 2); ctx.fillStyle = '#38bdf8'; ctx.fill(); ctx.lineWidth = 2; ctx.strokeStyle = '#fff'; ctx.stroke();
        ctx.setTransform(1, 0, 0, 1, 0, 0);
      }
      function pick(e) {
        const rc = cv.getBoundingClientRect();
        const u = (e.clientX - rc.left) / sc + u0, v = v1 - (e.clientY - rc.top) / sc;
        return fromUV(u, v);
      }
      wrap.addEventListener('pointerdown', e => { e.stopPropagation(); });
      wrap.addEventListener('click', e => {
        e.stopPropagation();
        const [x, z] = pick(e);
        if (!S.inFootprint(x, z) && !inPlan(x, z)) { showToast('스캔된 공간 안쪽을 눌러 주세요'); return; }
        const s = S.snap(x, z, 0.6);
        if (!s) { showToast('그 자리는 가구·벽이라 설 수 없어요'); return; }
        moveTo(s[0], s[1], { fromMap: true });
      });
      return { el: wrap, draw };
    }

    /* ── 이동 ── */
    function eyeAt(x, z, out) { return (out || new THREE.Vector3()).set(x, S.floorY + W.eye, z); }
    function moveTo(x, z, o) {
      o = o || {};
      const to = eyeAt(x, z);
      const dist = to.distanceTo(W.pos);
      if (dist < 0.05) return;
      // 미니맵 이동인데 가슴·눈 높이 길이 막혀 있으면(벽 너머) 잠깐 어둡게 했다가 옮긴다
      const blocked = o.fromMap && !(S.clearLine(W.pos, to, { skipA: 0.2, skipB: 0.2 }) && S.clearLine(tmp.copy(W.pos).setY(S.floorY + 1.0), tmp2.copy(to).setY(S.floorY + 1.0), { skipA: 0.2, skipB: 0.2 }));
      if (blocked) {
        fade.style.opacity = '1';
        setTimeout(() => { W.anim = null; W.pos.copy(to); fade.style.opacity = '0'; wayKey = ''; opt.onMove && opt.onMove(); }, 170);
        return;
      }
      W.anim = { from: W.pos.clone(), to, t0: now(), dur: clamp(0.6 + dist * 0.04, 0.6, 0.8) * 1000 };
    }

    /* ── 입력 ── */
    const ptrs = new Map();
    let down = null, pinch = null;
    function localXY(e) { const r = dom.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; }
    dom.addEventListener('pointerdown', e => {
      if (!W.active) return;
      ptrs.set(e.pointerId, localXY(e));
      if (ptrs.size === 1) { const [x, y] = localXY(e); down = { x, y, t: now(), lx: x, ly: y, drag: false, id: e.pointerId }; }
      else if (ptrs.size === 2) { const [a, b] = [...ptrs.values()]; pinch = { d: Math.hypot(a[0] - b[0], a[1] - b[1]), fov: W.fov }; if (down) down.drag = true; }
      try { dom.setPointerCapture(e.pointerId); } catch (_) {}
    });
    dom.addEventListener('pointermove', e => {
      if (!W.active) return;
      const [x, y] = localXY(e);
      if (ptrs.has(e.pointerId)) ptrs.set(e.pointerId, [x, y]);
      if (pinch && ptrs.size >= 2) {
        const [a, b] = [...ptrs.values()];
        const d = Math.hypot(a[0] - b[0], a[1] - b[1]);
        if (pinch.d > 10) W.fov = clamp(pinch.fov * pinch.d / d, 30, 90);
        return;
      }
      if (down && e.pointerId === down.id) {
        if (!down.drag && Math.hypot(x - down.x, y - down.y) > 5) down.drag = true;
        if (down.drag) {
          const sz = sizeOf(), k = (W.fov * Math.PI / 180) / sz.h;     // 화면을 잡고 끄는 느낌: 1 px = 화각/높이
          W.yaw += (x - down.lx) * k;
          W.pitch = clamp(W.pitch + (y - down.ly) * k, -1.45, 1.45);
          down.lx = x; down.ly = y;
          W.hover = null;
        }
        return;
      }
      if (e.pointerType === 'mouse') W.hover = [x, y];
    });
    function endPtr(e) {
      if (!W.active) return;
      ptrs.delete(e.pointerId);
      if (ptrs.size < 2) pinch = null;
      if (!down || e.pointerId !== down.id) return;
      const d = down; down = null;
      if (d.drag || now() - d.t > 600 || e.type === 'pointercancel') return;
      if (opt.isBusy && opt.isBusy()) return;              // 측정 중: 클릭은 측정이 가져간다
      const [x, y] = localXY(e);
      const tg = floorTarget(x, y);
      if (tg) moveTo(tg.x, tg.z);
      else if (e.pointerType !== 'mouse') showToast('바닥을 눌러 이동하세요');
    }
    dom.addEventListener('pointerup', endPtr);
    dom.addEventListener('pointercancel', endPtr);
    dom.addEventListener('pointerleave', () => { W.hover = null; });
    dom.addEventListener('wheel', e => {
      if (!W.active) return;
      e.preventDefault(); e.stopPropagation();
      W.fov = clamp(W.fov * Math.exp(e.deltaY * 0.0012), 30, 90);
    }, { passive: false, capture: true });
    // 키: 라이브러리(스플랫 뷰어)의 방향키 기울이기와 겹치지 않게 capture 단계에서 먼저 받는다
    const MOVE_KEYS = ['KeyW', 'KeyA', 'KeyS', 'KeyD', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'KeyQ', 'KeyE'];
    const onKeyDown = e => {
      if (!W.active) return;
      const tag = document.activeElement && document.activeElement.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA') return;
      if (e.code === 'Escape') { exit(); e.preventDefault(); return; }
      if (MOVE_KEYS.includes(e.code)) { W.keys[e.code] = true; e.preventDefault(); e.stopPropagation(); }
    };
    const onKeyUp = e => { if (W.keys[e.code]) { W.keys[e.code] = false; e.stopPropagation(); } };
    const onBlur = () => { W.keys = {}; };
    root.addEventListener('keydown', onKeyDown, true);
    root.addEventListener('keyup', onKeyUp, true);
    root.addEventListener('blur', onBlur);
    function destroy() {
      if (W.active) exit();
      root.removeEventListener('keydown', onKeyDown, true);
      root.removeEventListener('keyup', onKeyUp, true);
      root.removeEventListener('blur', onBlur);
      for (const el of [svg, fade, toast, map && map.el]) if (el && el.parentNode) el.parentNode.removeChild(el);
    }

    /* ── 촬영이 적은 쪽 안내 (스플랫만: opt.coverageHint) ──
       보는 방향 ±14° 세 줄로 0.6–3.5 m 앞 기둥들의 점 수를 장면 중앙값과 견준다. 벽(키 큰 칸)에서 멈추고,
       스캔 밖(창 너머 등)은 0 으로 센다. 비율이 HINT_RATIO 미만이 두 번 이어지면 한 줄 안내(같은 자리·방향은 한 번). */
    const HINT_RATIO = opt.hintRatio || 0.35, TAU = Math.PI * 2;
    let hintT = 0, lastHint = -1e9, lowStreak = 0;
    const hinted = new Set();
    function coverageAhead(yaw0, at) {
      let sum = 0, n = 0;
      const y0 = yaw0 != null ? yaw0 : W.yaw, px = at ? at[0] : W.pos.x, pz = at ? at[1] : W.pos.z;
      for (const da of [-0.25, 0, 0.25]) {
        const dx = -Math.sin(y0 + da), dz = -Math.cos(y0 + da);
        for (let t = 0.6; t <= 3.5; t += S.v) {
          const c = S.cellOf(px + dx * t, pz + dz * t);
          if (c < 0 || !S.fp[c]) { n += Math.round((3.5 - t) / S.v) + 1; break; }
          sum += Math.min(S.dens[c], S.densRef * 2); n++;
          if (S.tall[c] >= 2) break;
        }
      }
      return n ? sum / n / S.densRef : 1;
    }
    function coverageHint(t) {
      if (!opt.coverageHint || W.anim || t - hintT < 400 || Math.abs(W.pitch) > 0.7) return;
      hintT = t;
      lowStreak = coverageAhead() < HINT_RATIO ? lowStreak + 1 : 0;
      if (lowStreak < 2 || t - lastHint < 8000) return;
      const key = Math.round(W.pos.x) + ',' + Math.round(W.pos.z) + ',' + Math.round((((W.yaw % TAU) + TAU) % TAU) / (Math.PI / 4)) % 8;
      if (hinted.has(key)) return;
      hinted.add(key); lastHint = t;
      showToast('이쪽은 촬영이 적어 흐릴 수 있어요', 2600);
    }

    /* ── 프레임 ── */
    function tick() {
      if (!W.active) return;
      const t = now(), dt = Math.min(0.05, W.lastT ? (t - W.lastT) / 1000 : 0.016);
      W.lastT = t;
      coverageHint(t);
      if (W.anim) {
        const a = W.anim, u = clamp((t - a.t0) / a.dur, 0, 1), e = easeInOut(u);
        W.pos.lerpVectors(a.from, a.to, e);
        if (a.yaw0 != null) { W.yaw = a.yaw0 + (a.yaw1 - a.yaw0) * e; W.pitch = a.p0 + (a.p1 - a.p0) * e; }
        if (u >= 1) { W.anim = null; wayKey = ''; opt.onMove && opt.onMove(); }
      } else {
        // 키보드 걷기 (막히면 축별로 미끄러지기)
        const k = W.keys;
        // W/S·↑/↓ 앞뒤, A/D 옆걸음, ←/→·Q/E 돌기
        const turn = (k.KeyQ || k.ArrowLeft ? 1 : 0) - (k.KeyE || k.ArrowRight ? 1 : 0);
        if (turn) W.yaw += turn * 1.6 * dt;
        const f = (k.KeyW || k.ArrowUp ? 1 : 0) - (k.KeyS || k.ArrowDown ? 1 : 0);
        const sd = (k.KeyD ? 1 : 0) - (k.KeyA ? 1 : 0);
        if (f || sd) {
          const sp = 1.3 * dt, fy = dir(W.yaw, 0, tmp);
          const dx = (fy.x * f - fy.z * sd) * sp, dz = (fy.z * f + fy.x * sd) * sp;
          const x = W.pos.x, z = W.pos.z;
          if (S.standable(x + dx, z + dz)) W.pos.set(x + dx, W.pos.y, z + dz);
          else if (S.standable(x + dx, z)) W.pos.x = x + dx;
          else if (S.standable(x, z + dz)) W.pos.z = z + dz;
          wayKey = '';
        }
      }
      applyCamera();
    }
    function applyCamera() {
      cam.position.copy(W.pos);
      dir(W.yaw, W.pitch, fwd);
      const c = ctl();
      if (c) c.target.copy(W.pos).addScaledVector(fwd, 0.05);
      cam.up.set(0, 1, 0);
      cam.lookAt(tmp.copy(W.pos).addScaledVector(fwd, 1));
      if (Math.abs(cam.fov - W.fov) > 0.01) { cam.fov = W.fov; cam.updateProjectionMatrix(); }
      cam.updateMatrixWorld();
    }
    // 화면 위 표시 (렌더 뒤에 부른다: 카메라 행렬이 최신)
    function draw() {
      if (!W.active) return;
      cam.updateMatrixWorld();
      const sz = sizeOf();
      svg.setAttribute('viewBox', `0 0 ${sz.w} ${sz.h}`);
      // 추천 지점
      const ws = visibleWaypoints();
      let hot = null;
      if (W.hover && !W.anim && !(opt.isBusy && opt.isBusy())) hot = floorTarget(W.hover[0], W.hover[1]);
      while (gWay.childNodes.length > ws.length) gWay.removeChild(gWay.lastChild);
      ws.forEach(([x, z], i) => {
        let el = gWay.childNodes[i];
        if (!el) { el = document.createElementNS(NS, 'path'); gWay.appendChild(el); }
        const d = W.anim ? null : ellipsePath(x, z, 0.2, sz, 28);
        if (!d) { el.setAttribute('d', ''); return; }
        el.setAttribute('d', d);
        el.setAttribute('class', 'kw-way' + (hot && Math.hypot(hot.x - x, hot.z - z) < 0.05 ? ' hot' : ''));
        const dist = Math.hypot(x - W.pos.x, z - W.pos.z);
        el.style.opacity = String(clamp(1.25 - dist / 7, 0.25, 1));
      });
      // 마우스 아래 바닥 링
      const d1 = hot ? ellipsePath(hot.x, hot.z, 0.26, sz) : null, d2 = hot ? ellipsePath(hot.x, hot.z, 0.06, sz, 20) : null;
      ring.setAttribute('d', d1 || ''); ringIn.setAttribute('d', d2 || '');
      dom.style.cursor = (opt.isBusy && opt.isBusy()) ? 'crosshair' : hot ? 'pointer' : down && down.drag ? 'grabbing' : 'grab';
      if (map) map.draw();
    }

    /* ── 켜기/끄기 ── */
    function startSpot() {
      const c = ctl();
      const cands = [];
      if (c) cands.push([c.target.x, c.target.z]);
      cands.push([cam.position.x, cam.position.z]);
      if (plan) { const big = plan.rooms.slice().sort((a, b) => (b.area || 0) - (a.area || 0))[0]; if (big && big.label) cands.push(big.label); }
      for (const [x, z] of cands) { if (S.inFootprint(x, z)) { const s = S.snap(x, z, 0.8); if (s) return s; } }
      // 발자국 무게중심에서 가장 가까운 설 자리
      let sx = 0, sz = 0, n = 0;
      for (let ix = 0; ix < S.nx; ix++) for (let iz = 0; iz < S.nz; iz++) if (S.fp[ix * S.nz + iz]) { sx += ix; sz += iz; n++; }
      if (!n) return null;
      const cx = S.lo[0] + (sx / n + 0.5) * S.v, cz = S.lo[2] + (sz / n + 0.5) * S.v;
      return S.snap(cx, cz, 3) || (S.waypoints && S.waypoints[0]) || null;
    }
    // 처음 바라볼 방향: 눈·가슴 높이에서 가장 멀리 트인 쪽 (지금 보던 방향이 그만큼 트였으면 그대로)
    function openYaw(spot, cur) {
      const free = yaw => {
        const dx = -Math.sin(yaw), dz = -Math.cos(yaw);
        let best = 6;
        for (const h of [W.eye, 1.0]) {
          for (let t = 0.3; t < 6; t += S.v * 0.5) {
            const x = spot[0] + dx * t, z = spot[1] + dz * t;
            // 막힌 칸이나 스캔 밖(창·커튼 뒤 빈 곳)에서 멈춘다
            if (S.solidAt(x, S.floorY + h, z) || !S.inFootprint(x, z)) { best = Math.min(best, t); break; }
          }
        }
        return best;
      };
      // 점수 = 트인 거리 × 촬영 밀도(장면 중앙값 대비, 최대 1) — 창 너머처럼 트였지만 덜 찍힌 쪽은 피한다
      const score = y => free(y) * clamp(coverageAhead(y, spot), 0.05, 1);
      let by = cur, bs = -1;
      for (let i = 0; i < 24; i++) { const y = i / 24 * Math.PI * 2, s = score(y); if (s > bs) { bs = s; by = y; } }
      return score(cur) >= 0.8 * bs ? cur : by;
    }
    function enter(o) {
      if (W.active) return true;
      o = o || {};
      const spot = o.at || startSpot();
      if (!spot) { showToast('걸을 수 있는 바닥을 찾지 못했어요'); return false; }
      const c = ctl();
      W.saved = { fov: cam.fov, pos: cam.position.clone(), target: c ? c.target.clone() : null, up: cam.up.clone(),
                  c: c ? { enabled: c.enabled, minP: c.minPolarAngle, maxP: c.maxPolarAngle, damp: c.enableDamping, minD: c.minDistance } : null };
      if (c) { c.enableDamping = false; c.update(); c.enabled = false; c.minPolarAngle = 0; c.maxPolarAngle = Math.PI; c.minDistance = 0; }
      cam.getWorldDirection(fwd);
      const yaw1 = o.yaw != null ? o.yaw : openYaw(spot, Math.atan2(-fwd.x, -fwd.z));
      const p0 = Math.asin(clamp(fwd.y, -1, 1));
      // 화각: 가로 화면 세로 65°, 세로(폰) 화면은 가로 화각이 너무 좁지 않게 넓힌다
      const szE = sizeOf(), asp = szE.w / szE.h;
      W.active = true; W.lastT = 0; W.fov = asp >= 1 ? 65 : clamp(2 * Math.atan(Math.tan(32 * Math.PI / 180) / asp) * 180 / Math.PI, 70, 90); W.keys = {}; W.hover = null;
      const to = eyeAt(spot[0], spot[1]);
      if (o.instant) { W.pos.copy(to); W.yaw = yaw1; W.pitch = -0.08; W.anim = null; }
      else {
        W.pos.copy(cam.position); W.yaw = yaw1; W.pitch = p0;
        W.anim = { from: cam.position.clone(), to, t0: now(), dur: 900, yaw0: yaw1, yaw1, p0, p1: -0.08 };
      }
      svg.style.display = ''; if (map) map.el.style.display = '';
      wayKey = '';
      applyCamera();
      if (map) map.draw(true);
      opt.onChange && opt.onChange(true);
      return true;
    }
    function exit() {
      if (!W.active) return;
      W.active = false; W.anim = null; W.keys = {}; down = null; pinch = null; ptrs.clear();
      svg.style.display = 'none'; if (map) map.el.style.display = 'none';
      const c = ctl(), sv = W.saved;
      dir(W.yaw, W.pitch, fwd);
      cam.fov = sv ? sv.fov : 50; cam.updateProjectionMatrix();
      if (c) {
        // 지금 자리에서 앞쪽 1.5 m 를 중심으로 돌려 보기를 이어 간다
        c.target.copy(W.pos).addScaledVector(fwd, 1.5);
        if (sv && sv.c) { c.minPolarAngle = sv.c.minP; c.maxPolarAngle = sv.c.maxP; c.minDistance = sv.c.minD; c.enabled = sv.c.enabled; c.update(); c.enableDamping = sv.c.damp; }
        else { c.enabled = true; c.update(); }
      }
      dom.style.cursor = '';
      opt.onChange && opt.onChange(false);
    }

    return {
      get active() { return W.active; },
      get pos() { return W.pos; },
      get yaw() { return W.yaw; },
      get eye() { return W.eye; },
      scene: S, plan,
      enter, exit, toggle: o => (W.active ? (exit(), false) : enter(o)), destroy,
      tick, draw, moveTo, floorTarget, showToast, applyCamera, coverageAhead,
      setPose(x, z, yaw) { W.anim = null; W.pos.copy(eyeAt(x, z)); if (yaw != null) W.yaw = yaw; wayKey = ''; },
      minimap: map ? map.el : null,
    };
  }

  root.KgeoWalk = { analyze, create, pointsFromObject3D, floorplanWorld, loadFloorplan, pointInPoly, EYE, version: '0.1' };
})(window);
