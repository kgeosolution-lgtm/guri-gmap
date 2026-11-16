/* ============================================================
   kgeoScan Viewer - Main Script (Three.js GLB Viewer)
   ============================================================ */
function isMobile() { return window.matchMedia("(max-width: 768px)").matches; }
const MOBILE_SHEET_PEEK = 80;          // 폰: 아래 목록 시트가 접혔을 때 보이는 높이 (viewer.css #listPanel 과 같게)
const TYPE_INFO = {
  home:   { label: "집·실내", icon: "", color: [56, 189, 248] },
  survey: { label: "현장",    icon: "", color: [251, 146, 60] },
};
/* 2026-11-16 디자인 개편 (docs/design_system.md): 기록 '종류'는 무엇으로 찍었는지 — 지도 핀 색·목록 표시.
   scan_points 에는 종류 필드가 없어 산출물 주소로 가린다: glb 있으면 LiDAR 실측, 스플랫만 있으면 3D 촬영, 둘 다 없으면 VR 투어 */
const KIND_INFO = {
  lidar:   { label: "LiDAR 실측", color: [28, 95, 212] },
  photo3d: { label: "3D 촬영",    color: [116, 64, 232] },
  vr:      { label: "VR 투어",    color: [11, 143, 127] },
  trench:  { label: "굴착 기록",  color: [226, 160, 0] },
};
function recKind(a) {
  if (!a) return "photo3d";
  if (a.rec_kind && KIND_INFO[a.rec_kind]) return a.rec_kind;       // 2026-11-16 레이어 필드 (maintenance backfill-links)
  if (a.glb_url) return "lidar";
  if (a.splat_url) return "photo3d";
  return "vr";
}
/* 앱 기본 제목 '스캔 20261110_1701' → '11월 10일 오후 5:01 스캔' (사람이 읽는 제목). 사용자가 붙인 제목은 그대로 */
/* 레이어 필드(job_id·pano_url·floorplan_url·utility_url, 2026-11-16)가 채워진 기록이면 그 값을 믿고 파일을 찔러 보지 않는다.
   job_id 가 없는 기록(옛 레이어·status 로 연 링크 공유 기록)은 예전처럼 작업 번호로 주소를 짐작해 찾아본다 */
function fieldsKnown(a) { return !!(a && a.job_id); }
function displayTitle(a) {
  const t = (a && a.scan_title) || "";
  const m = t.match(/^스캔\s*(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(?:[-_].*)?$/);
  if (!m) return t || "제목 없는 기록";
  const h = +m[4], ap = h < 12 ? "오전" : "오후", h12 = h % 12 || 12;
  return `${+m[2]}월 ${+m[3]}일 ${ap} ${h12}:${m[5]} 스캔`;
}
function fmtDateKo(v) {
  if (!v) return "";
  const d = new Date(v); if (isNaN(d)) return "";
  const h = d.getHours(), ap = h < 12 ? "오전" : "오후";
  return `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일 ${ap} ${h % 12 || 12}:${String(d.getMinutes()).padStart(2, "0")}`;
}
function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
/* 없는·잘못된·비공개 기록 링크 안내 (2026-11-16 UX 점검): 예전엔 아무 말 없거나 'STEP 0/7' 알약이 잠깐 떴다.
   잘못된 주소 값은 지워 새로고침·복사에 남지 않게 한다 */
function showNotFound(msg) {
  try { history.replaceState(null, "", location.pathname); } catch (e) {}
  const old = document.getElementById("notFound"); if (old) old.remove();
  const el = document.createElement("div");
  el.id = "notFound"; el.className = "knf"; el.setAttribute("role", "alertdialog"); el.setAttribute("aria-labelledby", "knfT");
  el.innerHTML = '<b id="knfT">기록을 찾을 수 없어요</b><span></span><button type="button" class="k-btn primary small">지도에서 기록 보기</button>';
  el.querySelector("span").textContent = msg || "지워졌거나 공개 범위가 바뀌었을 수 있어요. 링크 주소가 잘렸는지도 확인해 주세요.";
  const close = () => { el.remove(); document.removeEventListener("keydown", onKey); };
  const onKey = e => { if (e.key === "Escape") close(); };
  el.querySelector("button").onclick = close;
  document.addEventListener("keydown", onKey);
  document.body.appendChild(el);
  try { el.querySelector("button").focus({ preventScroll: true }); } catch (e) {}
}

/* LINK-HELPERS-BEGIN ── 같은 장소 기록 묶기 (✦ 3D · 🥽 VR 투어 · 📐 평면도, 2026-11-12)
   scan_points 레이어에는 site_id·pano_url·floorplan_url 필드가 없다 → 작업 번호(glb·썸네일·스플랫 주소의 8자리)로 산출물을 찾고,
   같은 장소는 site_id(있으면) 또는 같은 유형·20 m 안·30일 안으로 묶는다. 순수 함수 — node 시험: server/tools/test_link.js */
const LINK_RADIUS_M = 20, LINK_DAYS = 30;
function linkJobId(a) {
  for (const k of ["glb_url", "thumb_url", "splat_url", "ortho_url", "pano_url", "floorplan_url"]) {
    const m = a && a[k] && String(a[k]).match(/\/([0-9a-f]{8})(?:\.glb|\.jpg|\.splat|_ortho\.json|_pano\/tour\.json|_floorplan\.json)(?:\?.*)?$/i);
    if (m) return m[1].toLowerCase();
  }
  return "";
}
function linkBase(a) {                         // 서빙 폴더 주소 (…/glb/) — 같은 작업의 다른 산출물 이름을 만든다
  for (const k of ["glb_url", "thumb_url", "splat_url", "ortho_url"]) {
    const m = a && a[k] && String(a[k]).match(/^(.*\/)[0-9a-f]{8}[^/]*$/i);
    if (m) return m[1];
  }
  return "";
}
function linkPanoUrl(a) { if (a && a.pano_url) return a.pano_url; const b = linkBase(a), j = linkJobId(a); return b && j ? b + j + "_pano/tour.json" : ""; }
function linkPlanUrl(a) { if (a && a.floorplan_url) return a.floorplan_url; const b = linkBase(a), j = linkJobId(a); return b && j ? b + j + "_floorplan.json" : ""; }
function linkHas3D(a) { return !!(a && (a.glb_url || a.splat_url)); }
function linkPanoCandidate(a) { return !!(a && !a.glb_url && !a.splat_url && (a.pano_url || a.thumb_url)); }   // VR 투어만 있는 작업 후보
function linkDistM(lon1, lat1, lon2, lat2) {
  const R = 6371008.8, r = Math.PI / 180, dφ = (lat2 - lat1) * r, dλ = (lon2 - lon1) * r;
  const h = Math.sin(dφ / 2) ** 2 + Math.cos(lat1 * r) * Math.cos(lat2 * r) * Math.sin(dλ / 2) ** 2;
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
}
function linkKey(a) { return String((a && (a.objectid ?? a.OBJECTID)) ?? "") + "|" + linkJobId(a); }
/* items: [{a: attributes, lon, lat}] → target 과 같은 장소인 다른 기록(가까운 날짜 순). opt: {radius, days} */
function findSiblings(target, items, opt) {
  const R = (opt && opt.radius) || LINK_RADIUS_M, D = ((opt && opt.days) || LINK_DAYS) * 86400000;
  if (!target || !target.a) return [];
  const ta = target.a, tk = linkKey(ta), tType = ta.scan_type || "", tDate = +ta.pub_date || 0;
  const out = [];
  for (const it of items || []) {
    const a = it && it.a;
    if (!a || linkKey(a) === tk) continue;
    let ok = false;
    if (ta.site_id && a.site_id) ok = String(ta.site_id) === String(a.site_id);       // 관리 대상(장소)이 정해져 있으면 그것만 본다
    else {
      if ((a.scan_type || "") !== tType) continue;
      if (![target.lon, target.lat, it.lon, it.lat].every(Number.isFinite)) continue;
      if (linkDistM(target.lon, target.lat, it.lon, it.lat) > R) continue;
      if (tDate && +a.pub_date && Math.abs(+a.pub_date - tDate) > D) continue;
      ok = true;
    }
    if (ok) out.push(it);
  }
  return out.sort((x, y) => Math.abs((+x.a.pub_date || 0) - tDate) - Math.abs((+y.a.pub_date || 0) - tDate));
}
function linkDateLabel(ms) { if (!ms) return ""; const d = new Date(+ms); return String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0"); }
/* LINK-HELPERS-END */

require([
  "esri/config",
  "esri/WebMap",
  "esri/views/MapView",
  "esri/layers/FeatureLayer",
  "esri/renderers/SimpleRenderer",
  "esri/renderers/UniqueValueRenderer",
  "esri/symbols/SimpleMarkerSymbol",
  "esri/widgets/Home",
  "esri/widgets/Zoom",
  "esri/widgets/BasemapToggle",
  "esri/widgets/Search",
  "esri/widgets/ScaleBar",
  "esri/Graphic",
  "esri/Basemap",
  "esri/layers/TileLayer",
  "esri/layers/VectorTileLayer",
  "esri/layers/WebTileLayer",
  "esri/widgets/Locate",
  "esri/layers/GroupLayer",
], function(
  esriConfig, WebMap, MapView, FeatureLayer, SimpleRenderer, UniqueValueRenderer, SimpleMarkerSymbol,
  Home, Zoom, BasemapToggle, Search, ScaleBar, Graphic,
  Basemap, TileLayer, VectorTileLayer, WebTileLayer, Locate, GroupLayer
) {
  /* ── 배경지도: WebMap 에 저장된 네이버 타일은 CORS 로 막혀 안 보이므로
        다른 kgeodata 앱(goyang1000_page/basemaps.js)과 같은 구성을 코드에서 만든다 ── */
  const KGEO_VT = "https://kgeodata.com/server/rest/services/Hosted/";
  function makeBasemap(kind) {
    if (kind === "imagery") {
      return new Basemap({
        title: "영상", id: "kgeo-imagery",
        baseLayers: [
          new TileLayer({ url: "https://services.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer", maxScale: 25000000 }),
          new WebTileLayer({ urlTemplate: "https://cdn.vworld.kr/2d/Satellite/service/{level}/{col}/{row}.jpeg", copyright: "VWORLD" }),
          // 영상 위 도로·지명 (국토지리정보원 하이브리드). referenceLayers 로 두면 ArcGIS 가 핀보다 위에 그려
          // 도로선이 핀을 덮었다 (2026-11-16 사용자) → 배경의 맨 위 층으로 둔다
          new VectorTileLayer({ url: KGEO_VT + "NGII_Hybrid_20250610/VectorTileServer", minScale: 12000000 })
        ]
      });
    }
    // 2026-11-16 디자인 개편: 두 지도가 같은 축척(1:1200만~1:300만)에서 겹쳐 지명이 두 번씩 보였다 →
    // 세계 축척은 Esri, 1:1200만부터는 국토지리정보원 회색 지도만. 음영은 약하게 (지도는 배경, 핀이 주인공)
    return new Basemap({
      title: "지도", id: "kgeo-gray",
      baseLayers: [
        new TileLayer({ url: "https://services.arcgisonline.com/arcgis/rest/services/Elevation/World_Hillshade/MapServer", opacity: 0.32 }),
        new VectorTileLayer({ url: "https://cdn.arcgis.com/sharing/rest/content/items/d9b6f47909c74f1fb5c7cefd14470e68/resources/styles/root.json", maxScale: 12000000 }),
        new VectorTileLayer({ url: "https://kgeodata.com/server/rest/services/Hosted/NGII_GRAY_2026/VectorTileServer/resources/styles/root.json", minScale: 12000000, blendMode: "multiply" })
      ]
    });
  }
  esriConfig.portalUrl = "https://kgeodata.com/portal";
  /* 지도 글꼴 압축 사본 (2026-11-16): 기본 지도(회색)·영상 지명 레이어의 글꼴(pbf)은 지도 서버가 압축 없이 보내
     첫 화면에서만 약 6MB 였다(전체의 2/3). 서버 정비 작업(maintenance build-fonts)이 미리 gzip 으로 만든 사본
     /app/3dscan/fonts/ngii/<글꼴>/<범위>.pbf 로 주소를 바꿔 받는다 (약 절반). 두 서비스는 글꼴 파일이 같다 */
  const FONT_COPY_STACKS = new Set(["NanumGothicOTF ExtraBold", "NanumGothic ExtraBold", "Arial Regular"]);
  esriConfig.request.interceptors.push({
    urls: /\/Hosted\/NGII_(GRAY_2026|Hybrid_20250610)\/VectorTileServer\/resources\/fonts\//,
    before(params) {
      const m = String(params.url).match(/\/resources\/fonts\/([^/?]+)\/(\d+-\d+)\.pbf/);
      if (!m) return;
      let stack;
      try { stack = decodeURIComponent(m[1]); } catch (e) { return; }
      if (!FONT_COPY_STACKS.has(stack)) return;
      params.url = "https://kgeodata.com/app/3dscan/fonts/ngii/" + encodeURIComponent(stack) + "/" + m[2] + ".pbf";
    }
  });
  const WEBMAP_ID  = "c61a12cd31684312b5be93863e7a1a07";
  const PT_ITEM_ID = "1058978572fd43e799f7068330ff90d8";

  let currentAttrs    = null;
  let currentSceneUrl = null;
  let isExpanded      = false;

  // Three.js GLB 뷰어 상태
  let glbRenderer   = null;
  let glbScene      = null;
  let glbCamera     = null;
  let glbControls   = null;
  let glbAnimFrame  = null;
  let _glbModel     = null;        // 측정·평면 보기용
  let _glbMaxDim    = 1;
  let _glbDist      = 3;
  const _ms = { on: false, pts: [], objs: [], text: "" };   // 거리 측정 상태
  let _walk = null;                         // 🚶 걸어보기 (walk.js, 집·방 스캔일 때만)
  let _viewMode   = "glb";                  // 사이드바 뷰어 모드: "glb"(메시) | "splat"(가우시안 스플랫 iframe)
  let _splatFrame = null;                   // splat.html iframe
  const WALK_JS = "walk.js?v=0981c0752e";                                          // 🚶 걸어보기 모듈 (배포 때 ?v=해시 를 붙이면 좋다)
  const ORTHO_PAGE = "ortho.html?v=0e87657983";                       // 배포(deploy.mjs stampAssets)가 ?v=해시 를 붙인다
  const SPLAT_PAGE = "splat.html?v=02de1520e0";          // 배포(deploy.mjs stampAssets)가 ?v=해시 를 붙인다
  const UTILITY_PAGE = "utility.html?v=e960a8d41c";                   // 굴착 기록 3D X-ray (배포가 ?v=해시 를 붙인다)
  let _utilInfo = null;                                  // 현재 스캔의 굴착 기록 {url, report} (utilities.json 이 있을 때만)
  const PANO_PAGE = "pano.html?v=4c97fd9136";                                       // 🥽 VR 투어 360° 실사 (배포가 ?v=해시 를 붙인다)
  let _panoInfo = null;                                  // 현재 스캔의 VR 투어 {url, count, from?} (<job>_pano/tour.json 이 있을 때만, from = 같은 장소 다른 기록)
  let _sib3d = null;                                     // VR 투어만 있는 기록일 때 같은 장소의 3D 기록 속성 (✦ 3D·◈ 메시 탭을 거기서 빌린다)
  let _planInfo = null;                                  // 📐 평면도 {url, json, from?} (<job>_floorplan.json — 자기 것 우선, 없으면 같은 장소 기록)
  let _pendingMode = null;                               // 같은 장소 칩으로 다른 기록을 열 때, 그 기록의 이 탭을 바로 연다
  const _panoCache = new Map(), _planCache = new Map();  // 주소 → Promise<json|null> (목록 배지·같은 장소 찾기가 같이 쓴다)
  function fetchJsonCached(url, cache) {
    if (!url) return Promise.resolve(null);
    if (!cache.has(url)) cache.set(url, fetch(url, { cache: "no-store" }).then(r => r.ok ? r.json() : null).catch(() => null));
    return cache.get(url);
  }
  const effGlb   = () => (currentAttrs && currentAttrs.glb_url) || (_sib3d && _sib3d.glb_url) || null;
  const effSplat = () => (currentAttrs && currentAttrs.splat_url) || (_sib3d && _sib3d.splat_url) || null;

  /* ── 지도 레이어 (2026-11-16 사용자: "영상 아이콘 잘 나오게, 수치지형도·지적도를 켤 수 있으면 현장조사에 좋겠다")
        배경: 지도(국토지리정보원 회색) / 영상(위성 + 도로·지명). 겹쳐 보기: 수치지형도 1:5000(NGII5000_*), 지적도(연속지적도_VT).
        모두 kgeodata 서버의 공개 벡터 타일. 고른 것은 이 기기(localStorage)에 기억한다 ── */
  const LAYER_KEY = "kgeo_map_layers";
  const OVERLAY_DEF = {
    topo: { title: "수치지형도 (1:5000)", hint: "건물·도로·등고선·지명 — 동네 크기로 확대하면 보여요",
      make: () => new GroupLayer({ title: "수치지형도", listMode: "hide",
        layers: ["contour", "river", "road", "rail", "wall", "building", "spot", "label"].map(n => new VectorTileLayer({ url: KGEO_VT + "NGII5000_" + n + "/VectorTileServer" })) }) },
    cad: { title: "지적도", hint: "필지 경계·지번 — 동네 크기로 확대하면 보여요",
      make: () => new VectorTileLayer({ url: KGEO_VT + encodeURIComponent("연속지적도_VT") + "/VectorTileServer", minScale: 25000 }) },
  };
  const _overlays = {}, _basemaps = {};
  function loadLayerPrefs() { try { const o = JSON.parse(localStorage.getItem(LAYER_KEY) || "{}"); return o && typeof o === "object" ? o : {}; } catch (e) { return {}; } }
  function saveLayerPrefs(p) { try { localStorage.setItem(LAYER_KEY, JSON.stringify(p)); } catch (e) {} }
  function setBase(kind) {
    const k = kind === "imagery" ? "imagery" : "map";
    if (!_basemaps[k]) _basemaps[k] = makeBasemap(k === "imagery" ? "imagery" : "gray");
    webmap.basemap = _basemaps[k];
  }
  function setOverlay(key, on) {
    if (on && !_overlays[key]) { _overlays[key] = OVERLAY_DEF[key].make(); webmap.add(_overlays[key], 0); }   // 0: 배경 바로 위, 핀 아래
    if (_overlays[key]) _overlays[key].visible = !!on;
  }
  function buildLayerControl() {
    const tile = "tile/15/12692/27941";                     // 서울역 부근 한 칸 — 배경 고르기 미리보기 (회색 지도는 한국에 z15 자료가 없어 z13)
    const wrap = document.createElement("div");
    wrap.className = "klc";
    wrap.innerHTML =
      '<button type="button" class="klc-btn" aria-expanded="false" aria-label="지도 레이어" title="지도 레이어 (배경·수치지형도·지적도)">' +
      '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path d="M12 3l9 5-9 5-9-5z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><path d="M3 12.5l9 5 9-5M3 16.5l9 5 9-5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg></button>' +
      '<div class="klc-panel" hidden role="dialog" aria-label="지도 레이어">' +
      '<div class="klc-h">배경 지도</div><div class="klc-bases">' +
      `<button type="button" class="klc-base" data-base="map"><span class="klc-thumb" style="background-image:url('https://services.arcgisonline.com/arcgis/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/13/3173/6985')"></span>지도</button>` +
      `<button type="button" class="klc-base" data-base="imagery"><span class="klc-thumb" style="background-image:url('https://services.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/${tile}')"></span>영상</button>` +
      '</div><div class="klc-h">겹쳐 보기 <small>현장조사용</small></div>' +
      Object.entries(OVERLAY_DEF).map(([k, d]) => `<label class="klc-ov"><input type="checkbox" data-ov="${k}"><span><b>${esc(d.title)}</b><small>${esc(d.hint)}</small></span></label>`).join("") +
      '</div>';
    const btn = wrap.querySelector(".klc-btn"), panel = wrap.querySelector(".klc-panel");
    const sync = () => {
      const p = loadLayerPrefs();
      wrap.querySelectorAll(".klc-base").forEach(b => b.setAttribute("aria-pressed", String((p.base || "map") === b.dataset.base)));
      wrap.querySelectorAll("[data-ov]").forEach(c => { c.checked = !!p[c.dataset.ov]; });
      btn.classList.toggle("on", p.base === "imagery" || Object.keys(OVERLAY_DEF).some(k => p[k]));
    };
    const close = () => { panel.hidden = true; btn.setAttribute("aria-expanded", "false"); };
    btn.onclick = e => { e.stopPropagation(); const open = panel.hidden; panel.hidden = !open; btn.setAttribute("aria-expanded", String(open)); };
    wrap.querySelectorAll(".klc-base").forEach(b => { b.onclick = () => { const p = loadLayerPrefs(); p.base = b.dataset.base; saveLayerPrefs(p); setBase(p.base); sync(); }; });
    wrap.querySelectorAll("[data-ov]").forEach(c => { c.onchange = () => { const p = loadLayerPrefs(); p[c.dataset.ov] = c.checked; saveLayerPrefs(p); setOverlay(c.dataset.ov, c.checked); sync(); }; });
    document.addEventListener("click", e => { if (!panel.hidden && !wrap.contains(e.target)) close(); });
    document.addEventListener("keydown", e => { if (e.key === "Escape" && !panel.hidden) { close(); btn.focus(); } });
    sync();
    const prefs = loadLayerPrefs();
    for (const k of Object.keys(OVERLAY_DEF)) if (prefs[k]) setOverlay(k, true);
    return wrap;
  }

  /* ── MapView ── */
  const webmap = new WebMap({ portalItem: { id: WEBMAP_ID } });
  webmap.load().then(() => setBase(loadLayerPrefs().base)).catch(() => {});
  const mapView = new MapView({
    container: "viewDiv",
    map: webmap,
    ui: { components: [] },
    popup: { autoOpenEnabled: false }
  });

  // ── 레이어뷰 (하이라이트용)
  let _highlightHandle = null;
  let _layerView = null;
  function highlightFeature(oid) {
    if (_highlightHandle) { _highlightHandle.remove(); _highlightHandle = null; }
    if (_layerView && oid != null) _highlightHandle = _layerView.highlight(oid);
  }
  // ArcGIS 파란 포커스 링 제거
  mapView.when(() => {
    // 모든 하위 엘리먼트 tabindex 제거 + style 주입
    function removeFocus() {
      document.querySelectorAll(
        ".esri-view-surface, .esri-view-surface--inset-outline, #viewDiv canvas, #viewDiv *[tabindex]"
      ).forEach(el => {
        el.setAttribute("tabindex", "-1");
        el.style.cssText += ";outline:none!important;border:none!important;box-shadow:none!important;";
      });
      // ::after 수도 요소는 style 태그로 덮어씀
      let styleTag = document.getElementById("esri-focus-fix");
      if (!styleTag) {
        styleTag = document.createElement("style");
        styleTag.id = "esri-focus-fix";
        styleTag.textContent = `
          .esri-view-surface--inset-outline:focus::after {
            outline: none !important;
            border: none !important;
            box-shadow: none !important;
            inset: 0 !important;
          }
          .esri-view *:focus { outline: none !important; box-shadow: none !important; }
        `;
        document.head.appendChild(styleTag);
      }
    }
    removeFocus();
    // 지도 클릭 시마다 재적용
    mapView.on("click", () => setTimeout(removeFocus, 10));
    mapView.on("pointer-down", () => setTimeout(removeFocus, 10));
  });

  const pointLayer = new FeatureLayer({
    portalItem: { id: PT_ITEM_ID },
    outFields: ["*"],
    renderer: new SimpleRenderer({
      symbol: new SimpleMarkerSymbol({
        style: "circle",
        color: [56, 189, 248, 0.9],
        size: "14px",
        outline: { color: [56, 189, 248], width: 2 }
      })
    })
  });
  webmap.add(pointLayer);
  window._pointLayer = pointLayer;      // 완료 팝업 → 확대 (require 밖에서 접근)
  window._mapView    = mapView;

  /* ── 지도 핀 (2026-11-16 디자인 개편, docs/design_system.md 2-8절): 기록 종류 색의 말뚝 핀 + 흰 테두리·흰 점.
        종류는 산출물 주소로 가린다(recKind 와 같은 규칙, Arcade). 가까운 기록은 묶어 숫자로 (잉크색 원 + 마킹 주황 고리) ── */
  function pinRing() {                      // 끝이 아래(12,0)인 물방울: 중심 (12,20) 반지름 11 원에 두 접선
    const cx = 12, cy = 20, r = 11, a0 = -33.4, a1 = 213.4, pts = [[12, 0]];
    for (let i = 0; i <= 28; i++) { const a = (a0 + (a1 - a0) * i / 28) * Math.PI / 180; pts.push([cx + r * Math.cos(a), cy + r * Math.sin(a)]); }
    pts.push([12, 0]);
    return pts.reverse();                   // 바깥 고리는 시계 방향
  }
  function circleRing(cx, cy, r) {
    const pts = [];
    for (let i = 0; i <= 24; i++) { const a = -i / 24 * Math.PI * 2; pts.push([cx + r * Math.cos(a), cy + r * Math.sin(a)]); }
    return pts;
  }
  function pinSymbol(rgb, size) {
    const fill = c => ({ type: "CIMPolygonSymbol", symbolLayers: [{ type: "CIMSolidFill", enable: true, color: c }] });
    return {
      type: "cim",
      data: { type: "CIMSymbolReference", symbol: { type: "CIMPointSymbol", symbolLayers: [{
        type: "CIMVectorMarker", enable: true, size: size || 28, anchorPoint: { x: 0, y: -0.5 }, anchorPointUnits: "Relative",
        frame: { xmin: 0, ymin: 0, xmax: 24, ymax: 32 }, scaleSymbolsProportionally: true, respectFrame: true,
        markerGraphics: [
          { type: "CIMMarkerGraphic", geometry: { rings: [pinRing()] }, symbol: { type: "CIMPolygonSymbol", symbolLayers: [
            { type: "CIMSolidStroke", enable: true, width: 1.6, color: [255, 255, 255, 255] },
            { type: "CIMSolidFill", enable: true, color: [rgb[0], rgb[1], rgb[2], 255] }] } },
          { type: "CIMMarkerGraphic", geometry: { rings: [circleRing(12, 20, 4.2)] }, symbol: fill([255, 255, 255, 255]) }   // 흰 점은 마지막(위)에
        ]
      }] } }
    };
  }
  function kindRenderer(withKindField) {
    return new UniqueValueRenderer({
      valueExpression: withKindField
        ? "IIF(!IsEmpty($feature.rec_kind), $feature.rec_kind, IIF(!IsEmpty($feature.glb_url), 'lidar', IIF(!IsEmpty($feature.splat_url), 'photo3d', 'vr')))"
        : "IIF(!IsEmpty($feature.glb_url), 'lidar', IIF(!IsEmpty($feature.splat_url), 'photo3d', 'vr'))",
      valueExpressionTitle: "기록 종류",
      defaultSymbol: pinSymbol([118, 131, 140]),
      uniqueValueInfos: Object.entries(KIND_INFO).map(([v, k]) => ({ value: v, symbol: pinSymbol(k.color), label: k.label }))
    });
  }
  pointLayer.renderer = kindRenderer();
  pointLayer.featureReduction = {
    type: "cluster", clusterRadius: "52px", clusterMinSize: "30px", clusterMaxSize: "46px", popupEnabled: false, maxScale: 4000,   // 확대하면 핀으로
    symbol: { type: "simple-marker", color: [19, 32, 42, 0.92], outline: { color: [255, 107, 44, 1], width: 3 } },
    labelingInfo: [{
      deconflictionStrategy: "none", labelPlacement: "center-center",
      labelExpressionInfo: { expression: "Text($feature.cluster_count, '#,###')" },
      symbol: { type: "text", color: [255, 255, 255, 1], font: { size: 12, weight: "bold" } }
    }]
  };
  mapView.highlightOptions = { color: [255, 107, 44, 1], haloOpacity: 1, fillOpacity: 0.15 };
  let _dataExtent = null;                   // 기록이 있는 범위 (처음 화면·🏠)
  let _hasTypeField = false;
  pointLayer.load().then(() => {
    const names = new Set((pointLayer.fields || []).map(f => f.name.toLowerCase()));
    _hasTypeField = names.has("scan_type");
    if (names.has("rec_kind")) pointLayer.renderer = kindRenderer(true);     // 굴착(노랑)·VR(청록) 핀은 이 필드로
    const lf = document.getElementById("lpFilters");
    if (lf) lf.style.display = _hasTypeField ? "" : "none";
  }).catch(() => {});


  mapView.when(async () => {
    document.getElementById("mapLoading").classList.add("done");
    pointLayer.queryFeatureCount()
      .then(cnt => { document.getElementById("ptCount").textContent = cnt + "개"; })
      .catch(() => {});

    loadListPanel();
    if (isMobile() && _lpOpen) toggleListPanel();      // 폰: 지도 먼저, 목록은 아래 시트(접힘)
    if (isMobile()) mapView.padding = Object.assign({}, mapView.padding, { bottom: MOBILE_SHEET_PEEK });
    const typeParam = new URLSearchParams(window.location.search).get("type");
    if (typeParam && TYPE_INFO[typeParam]) setTypeFilter(typeParam);

    // ── 레이어뷰 등록
    mapView.whenLayerView(pointLayer).then(lv => { _layerView = lv; });

    // ── 위젯: PC 는 왼쪽 위(오른쪽은 기록 보기에 가려짐). 폰은 확대·축소 단추 없이(두 손가락) 오른쪽 위에 처음 위치·내 위치
    const homeW = new Home({ view: mapView });
    homeW.goToOverride = (view, params) => !_dataExtent ? view.goTo(params.target)
      : view.goTo(_dataExtent.width === 0 ? { target: _dataExtent.center, zoom: 16 } : _dataExtent.clone().expand(1.4));
    // 2026-11-16 사용자: "홈 → 확대·축소 → 내 위치 순으로, 오른쪽 위로" (그 아래 레이어 단추)
    mapView.ui.add([homeW, new Zoom({ view: mapView }), new Locate({ view: mapView, scale: 5000, popupEnabled: false })], "top-right");
    mapView.ui.add(new ScaleBar({ view: mapView, style: "line", unit: "metric" }), "bottom-left");
    mapView.ui.add(buildLayerControl(), "top-right");     // 배경 지도·영상, 수치지형도·지적도

    // URL 파라미터로 피처 자동 선택 (?select=<scene_item_id>)
    const urlParams    = new URLSearchParams(window.location.search);
    const autoSelectId = urlParams.get("select");
    // 바로가기 주소가 아니면 처음 화면을 기록이 있는 곳에 맞춘다 (한반도 전체 대신)
    const deepLink = ["select", "job", "site", "site_id", "oid", "id"].some(k => urlParams.has(k));
    pointLayer.queryExtent().then(r => {
      if (!r || !r.extent || !r.count) return;
      _dataExtent = r.extent;
      if (deepLink) return;
      const tiny = r.count === 1;
      mapView.goTo(tiny ? { target: r.extent.center, zoom: 16 } : _dataExtent.clone().expand(1.4), { duration: 0 }).catch(() => {});
    }).catch(() => {});
    if (autoSelectId) {
      let found = false;
      try {
        if (/^[0-9A-Za-z_-]{1,64}$/.test(autoSelectId)) {        // 주소 값은 그대로 질의에 넣지 않는다
          await pointLayer.load();
          const q = pointLayer.createQuery();
          q.where          = "scene_item_id = '" + autoSelectId + "'";
          q.outFields      = ["*"];
          q.returnGeometry = true;
          const fs = await pointLayer.queryFeatures(q);
          if (fs.features.length) {
            found = true;
            const feat = fs.features[0];
            await mapView.goTo({ target: feat.geometry, zoom: 17 }, { duration: 800 });
            openSidebar(feat.attributes);
          }
        }
      } catch(e) { console.warn("자동선택 실패:", e); }
      if (!found) {                                           // 2026-11-16 UX 점검: 아무 말 없이 지도만 보이던 것
        showNotFound();
        if (_dataExtent) mapView.goTo(_dataExtent.clone().expand(1.4), { duration: 0 }).catch(() => {});
      }
    }
  }).catch(err => {
    document.querySelector(".load-text").textContent = "WebMap 로드 실패";
    console.error(err);
  });

  mapView.on("pointer-move", e => {
    const pt = mapView.toMap({ x: e.x, y: e.y });
    if (!pt) return;
    document.getElementById("cx").textContent = pt.longitude.toFixed(5) + "°";
    document.getElementById("cy").textContent = pt.latitude.toFixed(5) + "°";
  });

  mapView.on("click", async e => {
    if (window._pickMode) { window._setPickedLocation(e.mapPoint); return; }   // 업로드 위치 지정 중
    closePointPicker();
    const res = await mapView.hitTest(e, { include: [pointLayer] });
    if (!res.results.length) return;
    const g = res.results[0].graphic;
    if (g.isAggregate) {                    // 묶음 숫자: 그 안의 기록을 골라 열게 (2026-11-16 사용자)
      let feats = [];
      try {
        if (_layerView) {
          const q = _layerView.createQuery();
          q.aggregateIds = [g.getObjectId()]; q.outFields = ["*"]; q.returnGeometry = true;
          feats = (await _layerView.queryFeatures(q)).features;
        }
      } catch (err) { feats = []; }
      if (feats.length) { showPointPicker(feats, e, g.geometry); return; }
      mapView.goTo({ target: g.geometry, zoom: Math.min(mapView.zoom + 2, 19) }, { duration: 500, easing: "ease-out" }).catch(() => {});
      return;
    }
    // 같은 자리에 겹친 핀 (같은 사무실에서 여러 번 찍은 기록 등): 한 번에 고르게
    const oids = [...new Set(res.results.filter(r => r.graphic && !r.graphic.isAggregate)
      .map(r => r.graphic.attributes && (r.graphic.attributes.OBJECTID || r.graphic.attributes.objectid)).filter(v => v != null))];
    if (oids.length > 1) {
      try {
        const q = pointLayer.createQuery(); q.objectIds = oids; q.outFields = ["*"]; q.returnGeometry = true;
        const fs = await pointLayer.queryFeatures(q);
        if (fs.features.length > 1) { showPointPicker(fs.features, e, g.geometry); return; }
      } catch (err) {}
    }
    const oid = g.attributes.OBJECTID || g.attributes.objectid;
    await mapView.goTo({ target: g.geometry, zoom: Math.max(mapView.zoom, 16) },
                       { duration: 600, easing: "ease-out" });
    flashHighlight(oid);
    const q = pointLayer.createQuery();
    q.objectIds = [oid];
    q.outFields = ["*"];
    const fs = await pointLayer.queryFeatures(q);
    if (fs.features.length) openSidebar(fs.features[0].attributes);
  });

  /* ── 업로드 위치 지정: 지도 클릭 / 현재 위치 (require 안: mapView, Graphic 필요) ── */
  function showPickMarker(lon, lat) {
    mapView.graphics.removeAll();
    mapView.graphics.add(new Graphic({
      geometry: { type: "point", longitude: lon, latitude: lat },
      symbol: { type: "simple-marker", style: "diamond", color: [250, 204, 21, 0.95], size: 15,
                outline: { color: [15, 23, 42], width: 1.5 } }
    }));
  }
  window._setPickedLocation = function(pt) {
    if (!pt) return;
    setLocationFields(pt.longitude, pt.latitude);
    showPickMarker(pt.longitude, pt.latitude);
    endMapPick();
  };
  window.showPickMarker  = showPickMarker;
  window.clearPickMarker = function() { mapView.graphics.removeAll(); };
  window.goToLocation    = function(lon, lat) {
    mapView.goTo({ center: [lon, lat], zoom: Math.max(mapView.zoom, 17) }, { duration: 600 }).catch(() => {});
  };

  /* ── 사이드바 열기 ── */
  window.openSidebar = function(attrs) {
    currentAttrs    = attrs;
    currentSceneUrl = attrs.scene_url || null;

    const fmt = v => fmtDateKo(v) || "—";

    document.getElementById("sbTitle").textContent    = displayTitle(attrs);
    document.getElementById("sbAuthor").textContent   = attrs.author     || "—";
    document.getElementById("sbDate").textContent     = fmt(attrs.pub_date);
    document.getElementById("sbDate").hidden          = !attrs.pub_date;          // 2026-11-16 UX 점검: 빈 '—' 자리 숨김
    // 제목: 머리와 같은 읽기 쉬운 이름, 자동 이름(스캔 20261110_1701)이면 원래 이름을 작게 덧붙인다
    const aT = document.getElementById("aTitle"), shownT = displayTitle(attrs);
    aT.textContent = shownT || "—";
    if (attrs.scan_title && attrs.scan_title !== shownT) {
      const s = document.createElement("small"); s.className = "attr-sub"; s.textContent = "원래 이름 " + attrs.scan_title; aT.appendChild(s);
    }
    const expert = document.querySelector(".sb-expert");
    if (expert) expert.hidden = !attrs.scene_item_id;                            // 장면 ID 가 없으면 눌러도 아무 일 없는 단추만 남았다
    document.getElementById("aDate").textContent      = fmt(attrs.pub_date);
    document.getElementById("aNote").textContent      = attrs.note       || "—";
    document.getElementById("aSceneId").textContent   = attrs.scene_item_id || "—";
    // 장소 (동 단위, 서버 역지오코딩 place_name — 2026-11-16)
    const place = (attrs.place_name || "").trim(), sbPlace = document.getElementById("sbPlace");
    if (sbPlace) { sbPlace.hidden = !place; sbPlace.lastElementChild.textContent = place; }
    if (document.getElementById("aPlaceRow")) { document.getElementById("aPlaceRow").hidden = !place; document.getElementById("aPlace").textContent = place || "—"; }
    const tinfo = TYPE_INFO[attrs.scan_type] || null;
    const kind = recKind(attrs), kinfo = KIND_INFO[kind];
    const tag = document.getElementById("sbTypeTag");
    tag.innerHTML = `<span class="k-dot ${kind}"></span>${esc(kinfo.label)}` + (tinfo ? ` <span class="sb-tag-sub">${esc(tinfo.label)}</span>` : "");
    tag.className   = "sb-tag kind-" + kind;
    document.getElementById("aType").textContent = kinfo.label + (tinfo ? ` (${tinfo.label})` : "");
    setVisTag(attrs._visibility || "public");          // 🌐 공개 / 🔗 링크 공유 / 🔒 비공개 (docs/share_contract.md 1절)
    // 📷 이 장소 기록 더하기: 같은 제목으로 시작하면 목록·같은 장소 묶기에서 한눈에 이어진다 (위치는 촬영 페이지가 GPS 로 잡는다)
    const capQ = (attrs.scan_title ? "title=" + encodeURIComponent(attrs.scan_title) : "") +
      (attrs.site_id ? (attrs.scan_title ? "&" : "") + "site_id=" + encodeURIComponent(attrs.site_id) : "");
    const capVr = document.getElementById("lnkCapVr"), cap3d = document.getElementById("lnkCap3d");
    if (capVr) capVr.href = "capture_pano.html" + (capQ ? "?" + capQ : "");
    if (cap3d) cap3d.href = "capture.html" + (capQ ? "?" + capQ : "");

    const sceneLink = document.getElementById("aSceneUrl");
    if (attrs.scene_item_id) {
      sceneLink.href = `https://kgeodata.com/portal/home/item.html?id=${attrs.scene_item_id}`;
      sceneLink.style.display = "";
    } else {
      sceneLink.style.display = "none";
    }

    setWidth(isMobile() ? "100vw" : "40vw");
    isExpanded = false;
    document.getElementById("btnExpand").classList.add("active");
    document.getElementById("sidebar").classList.add("open", "expanded");

    setupViewerTabs(attrs);                 // splat_url 이 있으면 메시/스플랫 탭 표시. 항상 메시 모드로 시작

    // GLB URL 우선, 없으면 glb_url 필드 사용
    const glbUrl = attrs.glb_url || null;
    if (glbUrl) {
      loadGLBViewer(glbUrl);
    } else if (attrs.splat_url) {
      setViewMode("splat");                 // 웹 3D 현장조사(영상): 메시 없이 스플랫만
    } else {
      // 메시가 없음: 영상 현장조사는 GPU 가 스플랫을 만드는 중일 수 있다
      const loadingEl = document.getElementById("sceneLoading");
      const loadText  = document.querySelector(".scene-load-text");
      loadingEl.classList.remove("done");
      loadText.textContent = attrs.scan_type === "survey" ? "3D를 아직 만드는 중이에요. 영상으로 찍은 기록은 서버 처리가 끝나면 '사진 3D'로 나타나요." : "이 기록에는 3D 파일이 없어요.";
      setTimeout(() => loadingEl.classList.add("done"), 2500);
    }

    setListActive(attrs.scene_item_id || attrs.OBJECTID || attrs.objectid);
    recordHistory(attrs);
  };

  /* ── 뒤로 가기 (2026-11-16): 기록을 열면 방문 기록을 하나 쌓는다 → 폰 '뒤로'가 사이트를 나가지 않고 기록을 닫는다.
        주소도 ?select=<장면> 또는 ?job=<작업> 으로 바뀌어 그대로 복사·새로고침할 수 있다 ── */
  let _navFromPop = false;
  function recordUrl(a) {
    const u = new URL(location.href);
    u.search = ""; u.hash = "";
    const job = linkJobId(a) || a.job_id || a._job_id;
    if (a.scene_item_id) u.searchParams.set("select", a.scene_item_id);
    else if (job) u.searchParams.set("job", job);
    return u.pathname + u.search;
  }
  function recordHistory(a) {
    if (_navFromPop) return;
    try {
      const st = { kgeo: "rec" };
      if (history.state && history.state.kgeo === "rec") history.replaceState(st, "", recordUrl(a));
      else history.pushState(st, "", recordUrl(a));
    } catch (e) {}
  }
  window.closeRecord = function () {                       // ✕ 단추: 방문 기록이 있으면 뒤로 (popstate 가 닫는다)
    if (history.state && history.state.kgeo === "rec") { history.back(); return; }
    closeSidebar();
  };
  window.addEventListener("popstate", () => {
    const st = history.state || {};
    if (document.body.classList.contains("pseudo-full-open") && st.kgeo !== "full") { pseudoFull(false, true); }
    if (st.kgeo === "rec" || st.kgeo === "full") return;
    if (document.getElementById("sidebar").classList.contains("open")) {
      _navFromPop = true;
      try { closeSidebar(); } finally { _navFromPop = false; }
      try { history.replaceState(null, "", location.pathname); } catch (e) {}
    }
    if (typeof window.closeStartSheet === "function") window.closeStartSheet();
  });

  /* 링크 복사 (2026-11-16): 지도에 있는 기록은 ?select=, 없으면 작업 번호 ?job= */
  window.copyRecordLink = async function() {
    const a = currentAttrs; if (!a) return;
    const job = linkJobId(a);
    const url = location.origin + location.pathname + (a.scene_item_id ? `?select=${encodeURIComponent(a.scene_item_id)}` : job ? `?job=${job}` : "");
    const btn = document.getElementById("btnCopyLink");
    if (navigator.share && isMobile()) {                   // 폰: 공유 시트(카카오톡·문자·메일) — 2026-11-16
      try { await navigator.share({ title: displayTitle(a), text: (a.place_name ? a.place_name + " · " : "") + "kgeoScan 3D 기록", url }); return; }
      catch (e) { if (e && e.name === "AbortError") return; }
    }
    let ok = false;
    try { await navigator.clipboard.writeText(url); ok = true; } catch (e) {
      try { const ta = Object.assign(document.createElement("textarea"), { value: url }); document.body.appendChild(ta); ta.select(); ok = document.execCommand("copy"); ta.remove(); } catch (e2) {}
    }
    if (!ok && navigator.share) { try { await navigator.share({ title: displayTitle(a), url }); return; } catch (e) {} }
    if (btn) { const t = btn.dataset.label || (btn.dataset.label = btn.textContent); btn.textContent = ok ? "링크를 복사했어요" : "복사하지 못했어요"; setTimeout(() => { btn.textContent = t; }, 1800); }
  };

  window.closeSidebar = function() {
    document.getElementById("sidebar").classList.remove("open", "expanded");
    setWidth("0px");
    isExpanded = false;
    document.getElementById("btnExpand").classList.remove("active");
    destroyGLB();
    removeSplatFrame();
    _viewMode = "glb";
    setListActive(null);
  };

  /* 2026-11-16 기술 점검 8: 닫힌 기록 창이 화면 밖에서도 Tab 순서에 남았다 → inert. 열면 제목으로 초점, Esc 로 닫고 초점을 돌려준다 */
  (function sidebarA11y() {
    const sb = document.getElementById("sidebar"), t = document.getElementById("sbTitle");
    if (!sb) return;
    sb.setAttribute("role", "dialog"); sb.setAttribute("aria-labelledby", "sbTitle");
    sb.inert = !sb.classList.contains("open");
    if (t) t.tabIndex = -1;
    let back = null;
    const _open = window.openSidebar, _close = window.closeSidebar;
    window.openSidebar = function () {
      if (!sb.classList.contains("open")) back = document.activeElement;
      const r = _open.apply(this, arguments);
      sb.inert = false;
      try { if (t) t.focus({ preventScroll: true }); } catch (e) {}
      return r;
    };
    window.closeSidebar = function () {
      const r = _close.apply(this, arguments);
      sb.inert = true;
      try { if (back && back.focus && document.contains(back)) back.focus({ preventScroll: true }); } catch (e) {}
      back = null;
      return r;
    };
    document.addEventListener("keydown", e => {
      if (e.key !== "Escape" || !sb.classList.contains("open")) return;
      if (document.body.classList.contains("pseudo-full-open") || document.getElementById("pointPicker") || document.getElementById("notFound")) return;
      window.closeRecord();
    }, true);                                              // 캡처: 고르기 카드·안내 카드가 먼저 닫히기 전에 판단
  })();

  /* ── 50:50 토글 ── */
  window.toggleExpand = function() {
    if (isMobile()) return;                 // 폰은 항상 전체 폭
    isExpanded = !isExpanded;
    const btn = document.getElementById("btnExpand");
    if (isExpanded) {
      setWidth("50vw");
      btn.classList.add("active");
      btn.title = "축소 (400px)";
      document.getElementById("sidebar").classList.add("expanded");
    } else {
      setWidth("400px");
      btn.classList.remove("active");
      btn.title = "50:50 확장";
      document.getElementById("sidebar").classList.remove("expanded");
    }
    // Three.js 캔버스 리사이즈
    setTimeout(() => resizeGLB(), 420);
  };

  function setWidth(w) {
    const sidebar  = document.getElementById("sidebar");
    const coordBar = document.getElementById("coordBar");
    const viewDiv  = document.getElementById("viewDiv");
    const closed   = (w === "0px" || w === "0");

    // CSS 변수 + sidebar 너비
    document.documentElement.style.setProperty("--sw", w);
    sidebar.style.width = w;

    // viewDiv margin-right: 지도가 실제로 줄어들어 포인트가 중앙에
    viewDiv.style.marginRight = closed ? "0px" : w;

    // 좌표바 right 조정
    coordBar.style.right = closed ? "0px" : w;

    // ArcGIS: padding으로 지도 중심 기준점 보정
    // (goTo 호출 시 포인트가 보이는 영역의 정확한 중앙에 위치)
    if (typeof mapView !== "undefined" && mapView && !mapView.destroyed) {
      const px = closed ? 0 : parseFloat(w) || parseInt(w) || 0;
      // vw 단위면 픽셀로 변환
      const pxVal = isMobile() ? 0 : (w.endsWith("vw")
        ? Math.round(window.innerWidth * parseFloat(w) / 100)
        : px);
      mapView.padding = { top: 0, right: pxVal, bottom: isMobile() ? MOBILE_SHEET_PEEK : 0, left: 0 };
      // transition 완료 후 resize
      setTimeout(() => {
        try { mapView.resize(); } catch(e) {}
      }, 380);
    }
  }

  /* ════ Three.js GLB 뷰어 ════ */
  function destroyGLB() {
    _glbSeq++;                                              // 3D 프로그램을 받는 중에 닫거나 다른 기록을 열면 그 요청은 버린다
    clearMeasure(true);
    if (_walk) { _walk.destroy(); _walk = null; }
    if (document.getElementById("btnWalk")) document.getElementById("btnWalk").style.display = "none";
    _glbModel = null;
    if (glbAnimFrame) { cancelAnimationFrame(glbAnimFrame); glbAnimFrame = null; }
    if (glbRenderer)  { glbRenderer.dispose(); glbRenderer = null; }
    if (glbControls)  { glbControls.dispose(); glbControls = null; }
    glbScene  = null;
    glbCamera = null;
    const c = document.getElementById("sceneDiv");
    while (c.firstChild) c.removeChild(c.firstChild);
  }

  function resizeGLB() {
    if (!glbRenderer || !glbCamera) return;
    const c = document.getElementById("sceneDiv");
    const w = c.clientWidth || 1;
    const h = c.clientHeight || 1;
    glbRenderer.setSize(w, h);
    glbCamera.aspect = w / h;
    glbCamera.updateProjectionMatrix();
  }

  /* three.js r128 는 3D 보기를 처음 열 때 ES 모듈로 받는다 (2026-11-16 첫 화면 속도 — 예전엔 <head> 에서 약 600KB 를 먼저 받았다).
     viewer.js·walk.js 는 전역 THREE(GLTFLoader·OrbitControls 포함)를 그대로 쓴다 */
  let _threeP = null, _glbSeq = 0;
  function ensureThree() {
    if (window.THREE && window.THREE.GLTFLoader && window.THREE.OrbitControls) return Promise.resolve(window.THREE);
    if (!_threeP) {
      const base = "https://cdn.jsdelivr.net/npm/three@0.128.0/";
      // jsDelivr '+esm': 예제 모듈의 import "three" 를 같은 three 묶음(+esm)으로 바꿔 준다 → THREE 가 하나 (GLTFLoader 의 manager === DefaultLoadingManager 확인)
      _threeP = Promise.all([import(base + "+esm"), import(base + "examples/jsm/loaders/GLTFLoader.js/+esm"),
                             import(base + "examples/jsm/controls/OrbitControls.js/+esm")])
        .then(([T, G, O]) => (window.THREE = Object.assign({}, T, { GLTFLoader: G.GLTFLoader, OrbitControls: O.OrbitControls })))
        .catch(e => { _threeP = null; throw e; });
    }
    return _threeP;
  }
  window.ensureThree = ensureThree;
  /* 폰은 가벼운 판 <job>_m.glb 를 먼저 받는다 (2026-11-16: 텍스처 2048·정수 좌표 — 9.6 MB → 3.3 MB, worker/glb_mobile.py).
     없으면(옛 기록) 원본으로 다시 받는다. 걷기·평면도는 원본 주소 기준 */
  function mobileGlbUrl(u) {
    return (isMobile() && /\.glb(\?|$)/.test(u) && !/_m\.glb(\?|$)/.test(u)) ? u.replace(/\.glb(\?.*)?$/, "_m.glb$1") : u;
  }
  function loadGLBViewer(glbUrl) {
    destroyGLB();
    const seq = ++_glbSeq;
    const url = mobileGlbUrl(glbUrl);
    if (!(window.THREE && window.THREE.GLTFLoader)) {
      document.getElementById("sceneLoading").classList.remove("done");
      document.querySelector(".scene-load-text").textContent = "3D 보기 준비 중...";
      ensureThree().then(() => { if (seq === _glbSeq) loadGLBViewerNow(url, glbUrl); })
        .catch(() => { if (seq === _glbSeq) document.querySelector(".scene-load-text").textContent = "3D 보기 프로그램을 받지 못했어요. 인터넷 연결을 확인하고 다시 열어 주세요."; });
      return;
    }
    loadGLBViewerNow(url, glbUrl);
  }
  function loadGLBViewerNow(glbUrl, origUrl) {
    destroyGLB();

    const loadingEl = document.getElementById("sceneLoading");
    const loadText  = document.querySelector(".scene-load-text");
    loadingEl.classList.remove("done");
    loadText.textContent = "3D 모델 로딩 중...";

    const container = document.getElementById("sceneDiv");
    const W = container.clientWidth  || 400;
    const H = container.clientHeight || 300;

    glbScene  = new THREE.Scene();
    glbCamera = new THREE.PerspectiveCamera(45, W / H, 0.01, 10000);
    glbCamera.position.set(0, 1, 3);

    glbRenderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    glbRenderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    glbRenderer.setSize(W, H);
    glbRenderer.outputEncoding     = THREE.sRGBEncoding;
    glbRenderer.toneMapping        = THREE.ACESFilmicToneMapping;
    glbRenderer.toneMappingExposure = 1.5;
    glbRenderer.setClearColor(0x080b0f, 1);
    container.appendChild(glbRenderer.domElement);

    // 조명
    const ambient = new THREE.AmbientLight(0xffffff, 0.8);
    glbScene.add(ambient);
    const dirLight = new THREE.DirectionalLight(0xffffff, 1.0);
    dirLight.position.set(5, 10, 5);
    glbScene.add(dirLight);
    const fillLight = new THREE.DirectionalLight(0x88aaff, 0.4);
    fillLight.position.set(-5, -2, -5);
    glbScene.add(fillLight);

    // OrbitControls
    glbControls = new THREE.OrbitControls(glbCamera, glbRenderer.domElement);
    glbControls.enableDamping      = true;
    glbControls.dampingFactor      = 0.05;
    glbControls.screenSpacePanning = true;
    glbControls.minDistance        = 0.01;
    glbControls.maxDistance        = 10000;
    glbControls.rotateSpeed        = 0.7;
    glbControls.zoomSpeed          = 1.2;

    const loader = new THREE.GLTFLoader();
    loader.load(
      glbUrl,
      (gltf) => {
        const model = gltf.scene;

        // 바운딩박스
        const box    = new THREE.Box3().setFromObject(model);
        const center = box.getCenter(new THREE.Vector3());
        const size   = box.getSize(new THREE.Vector3());
        const maxDim = Math.max(size.x, size.y, size.z);

        model.position.sub(center);
        // 텍스처 선명도 최대화
        model.traverse(child => {
          if (child.isMesh && child.material) {
            const isArr = Array.isArray(child.material);
            const mats  = isArr ? child.material : [child.material];
            const out   = mats.map(mat => {
              ['map','normalMap','roughnessMap','metalnessMap','emissiveMap'].forEach(key => {
                if (mat[key]) {
                  // 서버 텍스처(삼각형별 아틀라스)는 밉맵을 끄고 선형 필터만 써야 경계가 번지지 않음
                  mat[key].anisotropy  = glbRenderer.capabilities.getMaxAnisotropy();
                  mat[key].minFilter   = THREE.LinearFilter;
                  mat[key].magFilter   = THREE.LinearFilter;
                  mat[key].generateMipmaps = false;
                  mat[key].needsUpdate = true;
                }
              });
              if (mat.map) {
                // 사진 텍스처는 조명 없이 그대로 보여 준다 (Scaniverse 뷰어와 같은 느낌)
                const unlit = new THREE.MeshBasicMaterial({ map: mat.map, side: mat.side, vertexColors: mat.vertexColors });
                unlit.toneMapped = false;
                return unlit;
              }
              return mat;
            });
            child.material = isArr ? out : out[0];
          }
        });
        glbScene.add(model);

        const dist = maxDim * 1.6;
        _glbModel = model; _glbMaxDim = maxDim; _glbDist = dist;
        glbCamera.position.set(dist * 0.6, dist * 0.5, dist);
        glbCamera.near = maxDim * 0.001;
        glbCamera.far  = maxDim * 100;
        glbCamera.updateProjectionMatrix();
        glbControls.target.set(0, 0, 0);
        glbControls.update();

        loadingEl.classList.add("done");

        // 캔버스 크기 재설정 (사이드바 열린 후 크기 확정)
        setTimeout(() => {
          resizeGLB();
        }, 50);

        // ── 키보드 상태
        const keys = {};
        function onKeyDown(e) {
          // 입력창 포커스 시 무시
          if (document.activeElement && ['INPUT','TEXTAREA'].includes(document.activeElement.tagName)) return;
          keys[e.code] = true;
          // R키: 뷰 리셋
          if (e.code === 'KeyR') {
            if (_walk) _walk.exit();
            glbCamera.position.set(dist * 0.6, dist * 0.5, dist);
            glbControls.target.set(0, 0, 0);
            glbControls.update();
          }
          // M키: 측정 토글
          if (e.code === 'KeyM') window.toggleMeasure();
          // F키: 전체화면
          if (e.code === 'KeyF') {
            const el = document.getElementById("sceneDiv");
            if (document.fullscreenElement) document.exitFullscreen();
            else el.requestFullscreen && el.requestFullscreen();
          }
          e.preventDefault && ['ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].includes(e.code) && e.preventDefault();
        }
        function onKeyUp(e) { keys[e.code] = false; }
        const _cnv = glbRenderer.domElement;
        _cnv.setAttribute('tabindex', '0');
        // 마우스가 캔버스 위에 있을 때만 키 입력 활성화
        _cnv.addEventListener('mouseenter', () => _cnv.focus());
        _cnv.addEventListener('mouseleave', () => _cnv.blur());
        _cnv.addEventListener('keydown', (e) => {
          onKeyDown(e);
          // 방향키가 페이지 스크롤/지도 이동 안 하도록 차단
          if (['ArrowUp','ArrowDown','ArrowLeft','ArrowRight',
               'KeyW','KeyS','KeyA','KeyD','KeyQ','KeyE',
               'PageUp','PageDown'].includes(e.code)) {
            e.stopPropagation();
            e.preventDefault();
          }
        });
        _cnv.addEventListener('keyup', onKeyUp);

        // ── 더블클릭: 해당 지점으로 타겟 이동
        _cnv.addEventListener('dblclick', (e) => {
          const rect   = _cnv.getBoundingClientRect();
          const mouse  = new THREE.Vector2(
            ((e.clientX - rect.left) / rect.width)  * 2 - 1,
           -((e.clientY - rect.top)  / rect.height) * 2 + 1
          );
          const raycaster = new THREE.Raycaster();
          raycaster.setFromCamera(mouse, glbCamera);
          const hits = raycaster.intersectObject(model, true);
          if (hits.length > 0) {
            const pt = hits[0].point;
            glbControls.target.lerp(pt, 0.8);
            glbControls.update();
          }
        });

        // ── 측정: 드래그가 아닌 클릭으로 모델 위 두 점을 찍는다 (마우스·터치 공통)
        let _pd = null;
        _cnv.addEventListener('pointerdown', e => { _pd = { x: e.clientX, y: e.clientY }; });
        _cnv.addEventListener('pointerup', e => {
          if (!_ms.on || !_pd) { _pd = null; return; }
          const moved = Math.hypot(e.clientX - _pd.x, e.clientY - _pd.y);
          _pd = null;
          if (moved > 6) return;
          const rect  = _cnv.getBoundingClientRect();
          const mouse = new THREE.Vector2(((e.clientX - rect.left) / rect.width) * 2 - 1, -((e.clientY - rect.top) / rect.height) * 2 + 1);
          const rc = new THREE.Raycaster();
          rc.setFromCamera(mouse, glbCamera);
          const hits = rc.intersectObject(model, true);
          if (hits.length) addMeasurePoint(hits[0].point.clone());
        });
        const lblEl = document.createElement('div');
        lblEl.id = 'measureLabel';
        lblEl.className = 'measure-label';
        container.appendChild(lblEl);

        // ── 조작 도움말 표시
        const helpEl = document.createElement('div');
        helpEl.id = 'glbHelp';
        helpEl.style.cssText = `
          position:absolute; bottom:10px; left:50%; transform:translateX(-50%);
          background:rgba(0,0,0,0.55); color:#ccc; font-size:11px;
          padding:5px 12px; border-radius:20px; pointer-events:none;
          white-space:nowrap; letter-spacing:0.3px;
        `;
        helpEl.innerHTML = isMobile()
          ? '한 손가락 회전 · 두 손가락 이동·확대 · 거리 재기는 두 점 터치'
          : '좌클릭: 회전 &nbsp;|&nbsp; 우클릭: 이동 &nbsp;|&nbsp; 휠: 줌 &nbsp;|&nbsp; WASD: 이동 &nbsp;|&nbsp; R: 리셋 &nbsp;|&nbsp; M: 측정 &nbsp;|&nbsp; 더블클릭: 포커스';
        container.style.position = 'relative';
        container.appendChild(helpEl);

        function animate() {
          glbAnimFrame = requestAnimationFrame(animate);

          // ── WASD / 방향키 카메라 이동
          const moveSpeed = maxDim * 0.012;
          const fwd = new THREE.Vector3();
          glbCamera.getWorldDirection(fwd);
          fwd.y = 0; fwd.normalize();
          const right = new THREE.Vector3();
          right.crossVectors(fwd, new THREE.Vector3(0,1,0)).normalize();
          const up = new THREE.Vector3(0, 1, 0);

          let moved = false;
          if (keys['KeyW'] || keys['ArrowUp'])    { glbCamera.position.addScaledVector(fwd,   moveSpeed); glbControls.target.addScaledVector(fwd,   moveSpeed); moved=true; }
          if (keys['KeyS'] || keys['ArrowDown'])  { glbCamera.position.addScaledVector(fwd,  -moveSpeed); glbControls.target.addScaledVector(fwd,  -moveSpeed); moved=true; }
          if (keys['KeyA'] || keys['ArrowLeft'])  { glbCamera.position.addScaledVector(right,-moveSpeed); glbControls.target.addScaledVector(right,-moveSpeed); moved=true; }
          if (keys['KeyD'] || keys['ArrowRight']) { glbCamera.position.addScaledVector(right, moveSpeed); glbControls.target.addScaledVector(right, moveSpeed); moved=true; }
          if (keys['KeyQ'] || keys['PageUp'])     { glbCamera.position.addScaledVector(up,    moveSpeed); glbControls.target.addScaledVector(up,    moveSpeed); moved=true; }
          if (keys['KeyE'] || keys['PageDown'])   { glbCamera.position.addScaledVector(up,   -moveSpeed); glbControls.target.addScaledVector(up,   -moveSpeed); moved=true; }
          if (moved) glbControls.update();

          if (_walk) _walk.tick();                // 걷기 중이면 카메라·조작 중심을 걷기가 정한다 (WASD 는 walk.js 가 가로챔)
          glbControls.update();
          glbRenderer.render(glbScene, glbCamera);
          updateMeasureLabel();
          if (_walk) _walk.draw();
        }
        animate();
        setupWalk(model, origUrl || glbUrl, container);
      },
      (xhr) => {
        if (xhr.total) {
          const pct = Math.round(xhr.loaded / xhr.total * 100);
          loadText.textContent = `3D 모델 로딩 중... ${pct}%`;
        }
      },
      (err) => {
        if (origUrl && origUrl !== glbUrl) { loadGLBViewerNow(origUrl); return; }   // 폰용 가벼운 판이 없다 → 원본
        console.error("GLB 로드 실패:", err);
        loadingEl.classList.add("done");
        loadText.textContent = "GLB 로드 실패: " + (err.message || err);
      }
    );

    window.addEventListener("resize", resizeGLB);
  }

  /* ════ 🚶 걸어보기 (walk.js — splat.html 과 같은 모듈) ════
     바닥이 있고 2 m² 넘게 걸을 수 있는 스캔(집·방)일 때만 버튼을 보인다. 평면도: attrs.floorplan_url → <job>_floorplan.json */
  function loadWalkJs() {
    if (window.KgeoWalk) return Promise.resolve(true);
    if (!loadWalkJs._p) loadWalkJs._p = new Promise(res => {
      const s = document.createElement("script");
      s.src = WALK_JS; s.onload = () => res(!!window.KgeoWalk); s.onerror = () => res(false);
      document.head.appendChild(s);
    });
    return loadWalkJs._p;
  }
  async function setupWalk(model, glbUrl, container) {
    if (!(await loadWalkJs()) || model !== _glbModel) return;
    const off = model.position.toArray();                  // 모델을 가운데로 옮긴 만큼 (평면도 ARKit 좌표 → 화면 좌표)
    const fpUrl = (currentAttrs && currentAttrs.floorplan_url) || (fieldsKnown(currentAttrs) ? String(glbUrl)
      : String(glbUrl).replace(/\.glb(\?.*)?$/i, "_floorplan.json"));       // 필드가 있는데 비었으면 평면도 없음 (아래 비교로 건너뜀)
    const fp = fpUrl !== String(glbUrl) ? await KgeoWalk.loadFloorplan(fpUrl) : null;
    if (model !== _glbModel) return;
    const plan = fp ? KgeoWalk.floorplanWorld(fp, off) : null;
    const pts = KgeoWalk.pointsFromObject3D(THREE, model, { max: 400000 });
    const S = KgeoWalk.analyze(pts.P, { floorPts: pts.up, floorY: plan ? plan.floorY : undefined, ceilY: plan ? plan.ceilY : undefined,
                                        floorSrc: "floorplan", solidMin: 1, obsTol: 0, plan });
    const indoor = (currentAttrs && currentAttrs.scan_type === "home") || plan || S.ceilY != null;   // 굴착·야외 스캔엔 안 보인다
    if (!S.ok || !S.walkable || !indoor || model !== _glbModel) return;
    const help = document.getElementById("glbHelp"), helpOrbit = help ? help.innerHTML : "";
    _walk = KgeoWalk.create({
      THREE, camera: glbCamera, dom: glbRenderer.domElement, container, getControls: () => glbControls,
      scene: S, plan, isBusy: () => _ms.on, mapCorner: "bl", mapSize: isMobile() ? 110 : 140,
      onChange: on => {
        const b = document.getElementById("btnWalk");
        if (b) { b.classList.toggle("active", on); b.textContent = on ? "↩ 둘러보기" : "🚶 걸어보기"; }
        if (help) help.innerHTML = !on ? helpOrbit : isMobile() ? "바닥 탭: 이동 &nbsp;|&nbsp; 드래그: 둘러보기 &nbsp;|&nbsp; 미니맵 탭: 그 자리로"
          : "바닥 클릭: 이동 &nbsp;|&nbsp; 드래그: 둘러보기 &nbsp;|&nbsp; 휠: 확대 &nbsp;|&nbsp; WASD: 걷기 &nbsp;|&nbsp; Esc: 나가기";
      },
    });
    let b = document.getElementById("btnWalk");
    if (!b) {
      b = document.createElement("button");
      b.className = "vctrl"; b.id = "btnWalk"; b.type = "button";
      b.title = "집 안을 눈높이로 걸어 다니기 — 바닥을 누르면 그 자리로, 미니맵을 누르면 그 방으로";
      const ref = document.getElementById("btnTop");
      if (ref) ref.parentNode.insertBefore(b, ref);
    }
    b.textContent = "걸어보기"; b.style.display = "";
    b.onclick = () => _walk && _walk.toggle();
    console.info("[walk]", `floor ${S.floorY.toFixed(3)} (${plan ? "floorplan" : "estimate"}) voxel ${S.v.toFixed(3)} footprint ${S.footprintM2.toFixed(1)} m2`);
  }

  /* ════ 거리 측정 · 평면 보기 ════ */
  function fmtLen(m) { return m >= 1 ? m.toFixed(2) + " m" : (m * 100).toFixed(1) + " cm"; }
  function setMeasureBox(html, hasResult) {
    const box = document.getElementById("measureBox");
    if (!box) return;
    box.innerHTML = html ? html + (hasResult ? ' <button type="button" class="mbtn" onclick="clearMeasure(false)">새로 재기</button>' : "") : "";
    box.style.display = html ? "flex" : "none";
  }
  function addMeasurePoint(p) {
    if (_ms.pts.length >= 2) clearMeasure(false);
    _ms.pts.push(p);
    const r = Math.max(_glbMaxDim * 0.006, 0.004);
    const marker = new THREE.Mesh(new THREE.SphereGeometry(r, 14, 14), new THREE.MeshBasicMaterial({ color: 0xfacc15, depthTest: false }));
    marker.position.copy(p); marker.renderOrder = 999;
    glbScene.add(marker); _ms.objs.push(marker);
    if (_ms.pts.length === 2) {
      const [a, b] = _ms.pts;
      const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints([a, b]), new THREE.LineBasicMaterial({ color: 0xfacc15, depthTest: false }));
      line.renderOrder = 998;
      glbScene.add(line); _ms.objs.push(line);
      const d = a.distanceTo(b), dh = Math.hypot(b.x - a.x, b.z - a.z), dv = Math.abs(b.y - a.y);
      _ms.text = fmtLen(d);
      setMeasureBox(`<b>${fmtLen(d)}</b><span>수평 ${fmtLen(dh)} · 높이차 ${fmtLen(dv)}</span>`, true);
    } else {
      setMeasureBox((isMobile() ? "두 번째 점을 누르세요" : "두 번째 점을 클릭하세요"), false);
    }
  }
  function clearMeasure(all) {
    _ms.objs.forEach(o => { if (glbScene) glbScene.remove(o); if (o.geometry) o.geometry.dispose(); if (o.material) o.material.dispose(); });
    _ms.objs = []; _ms.pts = []; _ms.text = "";
    const lbl = document.getElementById("measureLabel"); if (lbl) lbl.style.display = "none";
    const btn = document.getElementById("btnMeasure");
    if (all) {
      _ms.on = false;
      if (btn) btn.classList.remove("active");
      if (glbRenderer) glbRenderer.domElement.style.cursor = "";
      setMeasureBox("", false);
    } else if (_ms.on) {
      setMeasureBox((isMobile() ? "첫 번째 점을 누르세요" : "첫 번째 점을 클릭하세요"), false);
    }
  }
  function updateMeasureLabel() {
    const lbl = document.getElementById("measureLabel");
    if (!lbl || _ms.pts.length < 2 || !glbCamera) return;
    const c   = document.getElementById("sceneDiv");
    const mid = _ms.pts[0].clone().add(_ms.pts[1]).multiplyScalar(0.5).project(glbCamera);
    if (mid.z > 1) { lbl.style.display = "none"; return; }
    lbl.style.display = "block";
    lbl.textContent   = _ms.text;
    lbl.style.left    = ((mid.x + 1) / 2 * c.clientWidth) + "px";
    lbl.style.top     = ((1 - mid.y) / 2 * c.clientHeight) + "px";
  }
  window.clearMeasure = clearMeasure;
  window._glbRefs = () => ({ scene: glbScene, camera: glbCamera, model: _glbModel, controls: glbControls, ms: _ms, walk: _walk });   // 콘솔 디버그용
  window.toggleMeasure = function() {
    if (!_glbModel) return;
    _ms.on = !_ms.on;
    document.getElementById("btnMeasure").classList.toggle("active", _ms.on);
    if (glbRenderer) glbRenderer.domElement.style.cursor = _ms.on ? "crosshair" : "";
    if (_ms.on) setMeasureBox((isMobile() ? "첫 번째 점을 누르세요" : "첫 번째 점을 클릭하세요"), false);
    else clearMeasure(true);
  };
  window.viewTop = function() {
    if (!glbCamera || !glbControls) return;
    if (_walk) _walk.exit();
    glbCamera.position.set(0.001, _glbDist * 1.25, 0.001);
    glbControls.target.set(0, 0, 0);
    glbControls.update();
  };

  /* ════ 가우시안 스플랫 (사진 기반 3D 기록) — splat.html 을 iframe 으로 ════
     scan_points.splat_url 은 GPU 워커(worker_gpu/splat_worker.py)가 학습을 마치면 채운다.
     three r128 전역 스크립트와 스플랫 라이브러리(three 0.165 모듈)가 한 페이지에 못 있으므로 전용 페이지를 띄운다. */
  function splatPageUrl(url) {               // 홈스캔이면 home=1 → 스플랫 페이지가 천장이 안 찍혀도 🚶 걸어보기를 보인다
    return SPLAT_PAGE + (SPLAT_PAGE.includes("?") ? "&" : "?") + "model=" + encodeURIComponent(url) +
      (currentAttrs && currentAttrs.scan_type === "home" ? "&home=1" : "") +
      (currentAttrs && currentAttrs.floorplan_url ? "&floorplan=" + encodeURIComponent(currentAttrs.floorplan_url) : "");
  }
  function removeSplatFrame() {
    if (_splatFrame) { try { _splatFrame.src = "about:blank"; } catch (e) {} _splatFrame.remove(); _splatFrame = null; }
    const sceneDiv = document.getElementById("sceneDiv"), loadingEl = document.getElementById("sceneLoading");
    if (sceneDiv) sceneDiv.style.display = "";
    if (loadingEl) loadingEl.style.display = "";
  }
  function orthoPageUrl(url) {                  // title: 보고서용 이미지 저장의 제목
    return ORTHO_PAGE + (ORTHO_PAGE.includes("?") ? "&" : "?") + "meta=" + encodeURIComponent(url) +
      (currentAttrs && currentAttrs.scan_title ? "&title=" + encodeURIComponent(currentAttrs.scan_title) : "");
  }
  /* ── 굴착 기록(지하시설물): 서버가 <job>_utilities.json 을 GLB 옆에 둔다 (레이어 필드 없이 GLB 주소로 찾는다) ── */
  function utilitiesUrlFor(a) {
    const g = a && a.glb_url;
    return g && /\.glb(\?|$)/.test(g) ? g.replace(/\.glb(\?.*)?$/, "_utilities.json") : "";
  }
  function utilityPageUrl() {
    const a = currentAttrs || {}, q = UTILITY_PAGE.includes("?") ? "&" : "?";
    return UTILITY_PAGE + q + "meta=" + encodeURIComponent(_utilInfo.url) +
      (a.scan_title ? "&title=" + encodeURIComponent(a.scan_title) : "") +
      (a.splat_url ? "&splat=" + encodeURIComponent(a.splat_url) : "");
  }
  async function probeUtilities(attrs) {
    if (!fieldsKnown(attrs) && attrs.scan_type && attrs.scan_type !== "survey") return;      // 굴착 기록은 현장조사(survey)로만 올라온다
    const url = fieldsKnown(attrs) ? (attrs.utility_url || "") : utilitiesUrlFor(attrs);
    if (!url) return;
    let j;
    try { const r = await fetch(url, { cache: "no-store" }); if (!r.ok) return; j = await r.json(); } catch (e) { return; }
    if (currentAttrs !== attrs || !j || !((j.utilities || []).length || j.trench)) return;   // 굴착·관을 못 찾은 기록은 탭을 내지 않는다
    let report = url.replace(/_utilities\.json$/, "_util/report.html");
    try { const r = await fetch(report, { method: "HEAD", cache: "no-store" }); if (!r.ok) report = ""; } catch (e) { report = ""; }
    if (currentAttrs !== attrs) return;
    _utilInfo = { url, report, count: (j.utilities || []).length };
    const g = id => document.getElementById(id);
    if (g("viewerTabs")) g("viewerTabs").style.display = "flex";
    if (g("vtabUtil")) { g("vtabUtil").style.display = ""; g("vtabUtil").textContent = `⛏ 지하시설물 ${_utilInfo.count}`; }
    applyViewMode();
  }
  /* ── 🥽 VR 투어(360° 실사): 서버가 <job>_pano/tour.json 을 GLB·썸네일 옆에 둔다 (docs/pano_contract.md 2절)
     "✦ 3D"(스플랫)와 따로 탭을 둔다. 레이어에 pano_url 필드가 없어도 glb_url·thumb_url·splat_url 의 작업 번호로 찾는다 ── */
  function panoUrlFor(a) { return linkPanoUrl(a); }       // <job>_pano/tour.json (LINK-HELPERS)
  function planPngUrl() {                                 // 📐 평면도 미리보기 PNG (VR 투어 미니맵·평면도 탭)
    if (!_planInfo) return "";
    const u = (_planInfo.json && _planInfo.json.urls) || {};
    return u.png || _planInfo.url.replace(/_floorplan\.json(\?.*)?$/, "_floorplan/floorplan.png");
  }
  function panoPageUrl(embed) {
    const q = PANO_PAGE.includes("?") ? "&" : "?";
    return PANO_PAGE + q + "tour=" + encodeURIComponent(_panoInfo.url) + (embed ? "&embed=1" : "") +
      (_planInfo ? "&plan=" + encodeURIComponent(planPngUrl()) : "");     // 같은 장소 평면도 → VR 투어 미니맵 (pano.html 이 지원하면 씀)
  }
  function showVrTag(on, linked) {
    const t = document.getElementById("sbVrTag");
    if (!t) return;
    t.style.display = on && !(currentAttrs && recKind(currentAttrs) === "vr") ? "" : "none";   // VR 투어 기록이면 종류 표시와 겹친다
    t.title = linked ? "같은 장소의 다른 기록에 VR 투어가 있습니다" : "이 기록에 VR 투어가 있습니다";
  }
  async function probePano(attrs) {
    const url = fieldsKnown(attrs) ? (attrs.pano_url || "") : panoUrlFor(attrs);
    if (!url) return;
    const j = await fetchJsonCached(url, _panoCache);
    if (currentAttrs !== attrs || !j || !(j.spots || []).length) return;
    _panoInfo = { url, count: j.spots.length };
    const g = id => document.getElementById(id);
    if (g("viewerTabs")) g("viewerTabs").style.display = "flex";
    if (g("vtabPano")) { g("vtabPano").style.display = ""; g("vtabPano").title = `VR 투어 — 360° 실사 사진 ${_panoInfo.count}곳을 오가며 둘러보기`; }
    showVrTag(true, false);
    if (!attrs.glb_url && !attrs.splat_url || _pendingMode === "pano") { _pendingMode = null; setViewMode("pano"); }   // VR 투어만 있는 스캔은 바로 연다
    else applyViewMode();
  }

  /* ════ 같은 장소 기록 묶기 (✦ 3D · 🥽 VR 투어 · 📐 평면도) ════
     목록(_allFeatures)에서 같은 장소 기록을 찾아(LINK-HELPERS findSiblings) 칩으로 보이고, 이 기록에 없는 것은 탭으로 빌려 온다 */
  function itemOf(feat) {
    const p = feat && feat.geometry;
    return { a: feat.attributes, lon: p ? p.longitude : NaN, lat: p ? p.latitude : NaN, feat };
  }
  function allItems() { return _allFeatures.map(itemOf); }
  function currentItem(attrs) {
    const k = linkKey(attrs);
    const f = _allFeatures.find(ft => linkKey(ft.attributes) === k);
    return f ? itemOf(f) : null;
  }
  async function probeLinks(attrs) {
    const me = currentItem(attrs);
    if (!me) return;                                       // 목록이 아직 없으면 loadListPanel 끝에서 다시 부른다
    const sibs = findSiblings(me, allItems()).slice(0, 8);
    const recs = [me, ...sibs];
    const info = await Promise.all(recs.map(async it => ({
      it,
      pano: (fieldsKnown(it.a) ? !!it.a.pano_url : linkPanoCandidate(it.a)) ? await fetchJsonCached(linkPanoUrl(it.a), _panoCache) : null,
      plan: (fieldsKnown(it.a) ? !!it.a.floorplan_url : (it.a.scan_type || "home") === "home" && it.a.glb_url)
        ? await fetchJsonCached(linkPlanUrl(it.a), _planCache) : null,
    })));
    if (currentAttrs !== attrs) return;
    const g = id => document.getElementById(id);
    const hasPano = x => x.pano && (x.pano.spots || []).length;
    const hasPlan = x => x.plan && (x.plan.rooms || []).length;
    // VR 투어: 이 기록에 없으면 같은 장소 기록의 것을 탭으로
    const sp = info.find(x => x.it !== me && hasPano(x));
    if (!_panoInfo && sp) {
      _panoInfo = { url: linkPanoUrl(sp.it.a), count: sp.pano.spots.length, from: sp.it.a };
      if (g("vtabPano")) { g("vtabPano").style.display = ""; g("vtabPano").title = `VR 투어 — 같은 장소 기록(${linkDateLabel(sp.it.a.pub_date)})의 360° 실사 ${_panoInfo.count}곳`; }
      showVrTag(true, true);
    }
    // ✦ 3D·◈ 메시: VR 투어만 있는 기록이면 같은 장소의 3D 기록을 빌린다
    const s3 = !linkHas3D(attrs) && info.find(x => x.it !== me && linkHas3D(x.it.a));
    if (s3) {
      _sib3d = s3.it.a;
      if (g("vtabGlb") && _sib3d.glb_url) { g("vtabGlb").style.display = ""; g("vtabGlb").title = `LiDAR 메시 — 같은 장소 기록(${linkDateLabel(_sib3d.pub_date)})`; }
      if (g("vtabSplat") && _sib3d.splat_url) { g("vtabSplat").style.display = ""; g("vtabSplat").title = `3D — 같은 장소 기록(${linkDateLabel(_sib3d.pub_date)})의 가우시안 스플랫`; }
    }
    // 📐 평면도: 자기 것 우선
    const pp = info.find(x => x.it === me && hasPlan(x)) || info.find(x => hasPlan(x));
    if (pp) {
      _planInfo = { url: linkPlanUrl(pp.it.a), json: pp.plan, from: pp.it === me ? null : pp.it.a };
      if (g("vtabPlan")) { g("vtabPlan").style.display = ""; g("vtabPlan").title = "평면도 — 벽·문·창·치수·방 면적 (안목 기준 참고용)" + (_planInfo.from ? ` · 같은 장소 기록(${linkDateLabel(_planInfo.from.pub_date)})` : ""); }
    }
    if ((sp || s3 || pp) && g("viewerTabs")) g("viewerTabs").style.display = "flex";
    renderLinkChips(me, info, hasPano, hasPlan);
    const pm = _pendingMode;
    if (pm === "pano" && _panoInfo) { _pendingMode = null; setViewMode("pano"); }
    else if (pm === "plan" && _planInfo) { _pendingMode = null; setViewMode("plan"); }
    else applyViewMode();
  }
  function renderLinkChips(me, info, hasPano, hasPlan) {
    const box = document.getElementById("sbLinks");
    if (!box) return;
    const chips = [];
    info.forEach((x, i) => {
      const a = x.it.a, d0 = linkDateLabel(a.pub_date), d = d0 ? `${+d0.slice(0, 2)}월 ${+d0.slice(3)}일` : "", self = x.it === me;
      const k = esc(linkKey(a));
      if (linkHas3D(a)) chips.push(`<button type="button" class="sb-link${self ? " self" : ""}" data-key="${k}" data-kind="3d" title="${self ? "지금 보는 기록" : esc(a.scan_title || "")}">3D${d ? " " + d : ""}</button>`);
      if (hasPano(x)) chips.push(`<button type="button" class="sb-link vr${self ? " self" : ""}" data-key="${k}" data-kind="pano" title="${esc(a.scan_title || "")} — 360° ${x.pano.spots.length}곳">VR 투어${d ? " " + d : ""}</button>`);
      if (hasPlan(x)) {
        const tot = x.plan.rooms.filter(r => !r.partial).reduce((s, r) => s + (r.area_m2 || 0), 0);
        chips.push(`<button type="button" class="sb-link plan${self ? " self" : ""}" data-key="${k}" data-kind="plan" title="${esc(a.scan_title || "")} 평면도">평면도${tot ? " " + tot.toFixed(1) + " m²" : ""}</button>`);
      }
    });
    const others = info.length > 1;
    if (!others && chips.length < 2) { box.style.display = "none"; box.innerHTML = ""; return; }   // 이 기록 하나뿐이고 고를 게 없으면 숨김
    box.innerHTML = `<span class="sb-links-label">${others ? "같은 장소 기록" : "이 기록"}</span>` + chips.join("");
    box.style.display = "";
    box.onclick = e => {
      const b = e.target.closest ? e.target.closest(".sb-link") : null;
      if (!b) return;
      const x = info.find(y => linkKey(y.it.a) === b.dataset.key);
      if (!x) return;
      const kind = b.dataset.kind, self = x.it === me;
      if (kind === "pano" && _panoInfo && _panoInfo.url === linkPanoUrl(x.it.a)) return setViewMode("pano");
      if (kind === "plan" && _planInfo && _planInfo.url === linkPlanUrl(x.it.a)) return setViewMode("plan");
      if (kind === "3d" && (self || x.it.a === _sib3d)) return setViewMode(effSplat() ? "splat" : "glb");
      openLinkedRecord(x.it, kind);                         // 탭으로 빌려 오지 않은 기록 → 그 기록을 연다
    };
  }
  function openLinkedRecord(it, kind) {
    _pendingMode = kind === "3d" ? null : kind;
    if (it.feat && it.feat.geometry) mapView.goTo({ target: it.feat.geometry, zoom: Math.max(mapView.zoom, 17) }, { duration: 500 }).catch(() => {});
    openSidebar(it.a);
  }
  window.openUtilReport = function() {
    if (_utilInfo && _utilInfo.report) window.open(_utilInfo.report, "_blank");
  };
  // 🔗 매물 공유 페이지 (tour.html, docs/share_contract.md 3절): VR 투어가 있는 기록(같은 장소 기록 포함)에서 연다.
  // 이 기기에 그 VR 작업의 관리 키가 있으면 #key= 를 붙여 편집 모드로 연다 (키는 주소의 # 뒤라 서버로 가지 않는다)
  function panoJobId() {
    const m = _panoInfo && String(_panoInfo.url || "").match(/([0-9a-f]{8})_pano\/tour\.json/);
    return m ? m[1] : null;
  }
  window.openTourShare = function() {
    const job = panoJobId(); if (!job) return;
    const key = typeof editKeyFor === "function" ? editKeyFor(job) : null;
    window.open(`tour.html?job=${job}` + (key ? `#key=${encodeURIComponent(key)}` : ""), "_blank", "noopener");
  };
  function setupViewerTabs(attrs) {
    removeSplatFrame();
    removeOrthoOverlay();
    _viewMode = "glb";
    _utilInfo = null;
    _panoInfo = null;
    _sib3d = null;
    _planInfo = null;
    const g = id => document.getElementById(id);
    const tabs = g("viewerTabs");
    if (tabs) tabs.style.display = (attrs.splat_url || attrs.ortho_url) ? "flex" : "none";
    if (g("vtabGlb")) { g("vtabGlb").style.display = attrs.glb_url ? "" : "none"; g("vtabGlb").title = "LiDAR 메시 — 치수 측정 가능"; }   // 영상 현장조사는 메시가 없다
    if (g("vtabSplat")) { g("vtabSplat").style.display = attrs.splat_url ? "" : "none"; g("vtabSplat").title = "3D — 사진처럼 보이는 가우시안 스플랫, 🚶 걸어보기"; }
    if (g("vtabOrtho")) g("vtabOrtho").style.display = attrs.ortho_url ? "" : "none";
    if (g("vtabUtil")) g("vtabUtil").style.display = "none";
    if (g("vtabPano")) g("vtabPano").style.display = "none";
    if (g("vtabPlan")) g("vtabPlan").style.display = "none";
    if (g("sbLinks")) { g("sbLinks").style.display = "none"; g("sbLinks").innerHTML = ""; }
    showVrTag(false);
    applyViewMode();
    probeUtilities(attrs);
    probePano(attrs);
    probeLinks(attrs);
  }
  function applyViewMode() {
    const splat = _viewMode === "splat", ortho = _viewMode === "ortho", glb = _viewMode === "glb", util = _viewMode === "util",
      pano = _viewMode === "pano", plan = _viewMode === "plan";
    const g = id => document.getElementById(id);
    if (g("vtabGlb"))      g("vtabGlb").classList.toggle("active", glb);
    if (g("vtabSplat"))    g("vtabSplat").classList.toggle("active", splat);
    if (g("vtabOrtho"))    g("vtabOrtho").classList.toggle("active", ortho);
    if (g("vtabUtil"))     g("vtabUtil").classList.toggle("active", util);
    if (g("vtabPano"))     g("vtabPano").classList.toggle("active", pano);
    if (g("vtabPlan"))     g("vtabPlan").classList.toggle("active", plan);
    if (g("btnMeasure"))   g("btnMeasure").style.display   = glb ? "" : "none";
    if (g("btnTop"))       g("btnTop").style.display       = glb ? "" : "none";
    if (g("btnSplatOpen")) g("btnSplatOpen").style.display = glb ? "none" : "";
    if (g("btnOrthoMap"))  g("btnOrthoMap").style.display  = ortho ? "" : "none";
    if (g("btnUtilReport")) g("btnUtilReport").style.display = _utilInfo && _utilInfo.report ? "" : "none";
    if (g("btnTourShare")) {
      const job = panoJobId();
      g("btnTourShare").style.display = job ? "" : "none";
      if (job) g("btnTourShare").title = (typeof editKeyFor === "function" && editKeyFor(job))
        ? "매물 공유 페이지 — 링크·QR·삽입 코드, 이 기기에 관리 키가 있어 평면도 배치·설명 표시를 고칠 수 있어요"
        : "매물 공유 페이지 — 링크·QR 코드·다른 사이트 삽입 코드";
    }
    const badge = document.querySelector(".viewer-badge");
    if (badge) badge.textContent = splat ? "Gaussian Splat · 3DGS Viewer" : ortho ? "Orthophoto · 정사영상" :
      util ? "Underground Utilities · 지하시설물" : pano ? "VR Tour · VR 투어" : plan ? "Floor Plan · 평면도" : "3D Object · GLB Viewer";
    syncViewerChrome();
  }
  /* 2026-11-16 UX 점검: 안에 띄운 뷰어(사진 3D·정사영상·VR·지하시설물·평면도)는 제 단추가 있다. 이 화면의 탭·단추가 그 위를 덮어
     폰에서 측정·공유 단추를 누를 수 없었다 → 탭·단추 자리(띠)를 비워 두고 그 안쪽에만 띄운다 (viewer.css .sb-viewer.frame).
     탭이 하나뿐이면 고를 게 없으니 숨긴다 */
  function syncViewerChrome() {
    const v = document.querySelector(".sb-viewer"), tabs = document.getElementById("viewerTabs");
    if (!v) return;
    const shown = el => el && el.style.display !== "none";
    const nTabs = tabs ? [...tabs.querySelectorAll(".vtab")].filter(shown).length : 0;
    if (tabs && tabs.style.display !== "none" && nTabs < 2) tabs.style.display = "none";
    const hasTabs = shown(tabs) && nTabs >= 2;
    const hasCtl = [...document.querySelectorAll(".viewer-controls .vctrl")].some(shown);
    v.classList.toggle("frame", _viewMode !== "glb");
    v.classList.toggle("has-tabs", hasTabs);
    v.classList.toggle("has-ctl", hasCtl);
  }
  /* ── 📐 평면도 탭: floorplan.svg + 방 면적·천장 높이 + 내려받기 (SVG·PNG·DXF) ── */
  function planViewEl() {
    const P = _planInfo, fp = P.json || {}, u = fp.urls || {};
    const base = P.url.replace(/_floorplan\.json(\?.*)?$/, "_floorplan/");
    const svg = u.svg || base + "floorplan.svg", png = planPngUrl(), dxf = u.dxf || ((fp.files || {}).dxf ? base + "floorplan.dxf" : "");
    const rooms = (fp.rooms || []).filter(r => !r.partial), part = (fp.rooms || []).filter(r => r.partial);
    const tot = rooms.reduce((s, r) => s + (r.area_m2 || 0), 0);
    const ch = fp.levels && fp.levels.ceiling_height_m;
    const el = document.createElement("div");
    el.id = "splatFrame";
    el.className = "plan-view";
    el.innerHTML = `<div class="plan-wrap"><img class="plan-img" alt="평면도" src="${esc(svg)}" onerror="if(!this.dataset.f){this.dataset.f=1;this.src='${esc(png)}'}"></div>
      <div class="plan-info">
        <div class="plan-total">${tot ? `합계 <b>${tot.toFixed(2)} m²</b> (${(tot * 0.3025).toFixed(2)}평)` : "면적 정보 없음"}${ch ? ` · 천장 ${(+ch).toFixed(2)} m` : ""}${part.length ? ` · 일부만 찍힌 공간 ${part.length}곳` : ""}</div>
        <div class="plan-rooms">${rooms.map(r => `<span>${esc(r.name || r.id)} ${(+r.area_m2).toFixed(2)} m²${r.width_m ? ` (${(+r.width_m).toFixed(2)}×${(+r.depth_m).toFixed(2)} m)` : ""}</span>`).join("")}</div>
        <div class="plan-dl"><a href="${esc(svg)}" target="_blank" rel="noopener">SVG</a>${png ? `<a href="${esc(png)}" target="_blank" rel="noopener" download>PNG</a>` : ""}${dxf ? `<a href="${esc(dxf)}" download>DXF</a>` : ""}</div>
        <div class="plan-note">안목 기준 참고용입니다. 거래·광고에는 건축물대장 면적을 씁니다.${P.from ? ` · 같은 장소 기록(${linkDateLabel(P.from.pub_date)})의 평면도` : ""}</div>
      </div>`;
    return el;
  }
  /* ── 정사영상: 지도 위 제자리에 겹치기 (바닥 정사영상만 좌표가 있음) ── */
  let _orthoLayer = null;
  function removeOrthoOverlay() {
    if (_orthoLayer) { try { webmap.remove(_orthoLayer); } catch (e) {} _orthoLayer = null; }
    const b = document.getElementById("btnOrthoMap"); if (b) b.classList.remove("active");
  }
  window.toggleOrthoOverlay = async function() {
    if (_orthoLayer) { removeOrthoOverlay(); return; }
    if (!currentAttrs?.ortho_url) return;
    let m;
    try { m = await (await fetch(currentAttrs.ortho_url, { cache: "no-store" })).json(); } catch (e) { alert("정사영상 정보를 불러오지 못했습니다"); return; }
    const c = m.georef && m.georef.corners_lonlat;
    if (!c) { alert("벽 정사영상은 지도 좌표가 없어 겹칠 수 없습니다"); return; }
    // 콜백은 async 로 쓰지 않는다: 4.30 AMD require 가 async 콜백을 부르지 않는다(로컬에서 확인)
    require(["esri/layers/MediaLayer", "esri/layers/support/ImageElement", "esri/layers/support/CornersGeoreference", "esri/geometry/Point", "esri/layers/support/TileInfo"],
      (MediaLayer, ImageElement, CornersGeoreference, Point, TileInfo) => {
        // 배경지도 타일 단계(최대 19)로는 수 m 짜리 정사영상이 몇 픽셀이라, 확대 단계를 24 까지 늘린다(배경은 확대해 보임)
        if ((mapView.constraints.lods || []).length < 25) mapView.constraints.lods = TileInfo.create({ numLODs: 25 }).lods;
        const P = ll => new Point({ longitude: ll[0], latitude: ll[1], spatialReference: { wkid: 4326 } });
        const el = new ImageElement({ image: m.files.overlay || m.files.image,
          georeference: new CornersGeoreference({ topLeft: P(c.top_left), topRight: P(c.top_right), bottomRight: P(c.bottom_right), bottomLeft: P(c.bottom_left) }) });
        _orthoLayer = new MediaLayer({ source: [el], title: "정사영상", opacity: 1 });
        webmap.add(_orthoLayer);
        const b = document.getElementById("btnOrthoMap"); if (b) b.classList.add("active");
        _orthoLayer.when(() => mapView.goTo({ target: _orthoLayer.fullExtent.expand(1.6) }, { duration: 700 }).catch(() => {}));
      });
  };
  window.setViewMode = function(mode) {
    if (!currentAttrs) return;
    if (mode === "splat" && !effSplat()) return;
    if (mode === "ortho" && !currentAttrs.ortho_url) return;
    if (mode === "util" && !_utilInfo) return;
    if (mode === "pano" && !_panoInfo) return;
    if (mode === "plan" && !_planInfo) return;
    if (mode === _viewMode && !(mode === "glb" && !glbRenderer && effGlb())) return;   // VR 투어만 있던 기록: 빌려 온 메시는 처음 누를 때 띄운다
    if (mode !== "ortho") removeOrthoOverlay();
    _viewMode = mode;
    applyViewMode();
    const sceneDiv = document.getElementById("sceneDiv"), loadingEl = document.getElementById("sceneLoading");
    if (mode === "plan") {
      destroyGLB();
      removeSplatFrame();
      sceneDiv.style.display = "none";
      loadingEl.style.display = "none";
      const el = planViewEl();
      sceneDiv.parentNode.insertBefore(el, sceneDiv);
      _splatFrame = el;
    } else if (mode === "splat" || mode === "ortho" || mode === "util" || mode === "pano") {
      destroyGLB();                                   // 폰 GPU 메모리를 아끼려 메시 뷰어를 내리고 한 가지만 띄운다
      removeSplatFrame();
      sceneDiv.style.display = "none";
      loadingEl.style.display = "none";
      const f = document.createElement("iframe");
      f.id = "splatFrame";
      f.title = mode === "ortho" ? "Orthophoto Viewer" : mode === "util" ? "Underground Utility Viewer" : mode === "pano" ? "VR Tour Viewer" : "Gaussian Splat Viewer";
      f.setAttribute("allow", mode === "pano" ? "fullscreen; gyroscope; accelerometer" : "fullscreen");   // VR 투어: 폰 기울여 보기
      f.allowFullscreen = true;
      f.src = mode === "ortho" ? orthoPageUrl(currentAttrs.ortho_url) : mode === "util" ? utilityPageUrl() :
        mode === "pano" ? panoPageUrl(true) : splatPageUrl(effSplat());
      sceneDiv.parentNode.insertBefore(f, sceneDiv);
      _splatFrame = f;
    } else {
      removeSplatFrame();
      if (effGlb()) loadGLBViewer(effGlb());
    }
  };
  window.openSplatPage = function() {
    if (_viewMode === "ortho" && currentAttrs?.ortho_url) { window.open(orthoPageUrl(currentAttrs.ortho_url), "_blank"); return; }
    if (_viewMode === "util" && _utilInfo) { window.open(utilityPageUrl(), "_blank"); return; }
    if (_viewMode === "pano" && _panoInfo) { window.open(panoPageUrl(false), "_blank"); return; }
    if (_viewMode === "plan" && _planInfo) {
      const u = (_planInfo.json && _planInfo.json.urls) || {};
      window.open(u.svg || _planInfo.url.replace(/_floorplan\.json(\?.*)?$/, "_floorplan/floorplan.svg"), "_blank"); return;
    }
    if (!effSplat()) return;
    window.open(splatPageUrl(effSplat()), "_blank");
  };

  /* ── Portal Scene Viewer로 열기 (새 탭) ── */
  window.openSceneViewer = function() {
    if (!currentAttrs?.scene_item_id) return;
    const url = `https://kgeodata.com/portal/home/webscene/viewer.html?layers=${currentAttrs.scene_item_id}`;
    window.open(url, "_blank");
  };

  window.openPortalItem = function() {
    if (!currentAttrs?.scene_item_id) return;
    window.open(`https://kgeodata.com/portal/home/item.html?id=${currentAttrs.scene_item_id}`, "_blank");
  };

  /* ── sceneDiv 전체화면 (Fullscreen API) ── */
  window.openFullscreen = function() {
    // 2026-11-16: 아이폰 사파리·kgeoScan 앱(웹뷰)은 요소 전체 화면이 안 되고, 안드로이드·PC 는 3D 판만 전체 화면이 되어
    // 닫기·거리 재기·탭이 모두 사라졌다(UX 점검) → 언제나 극장 모드(단추 포함)로 채우고, 되는 기기는 그 극장을 통째로 전체 화면으로
    pseudoFull(true);
    const v = document.querySelector(".sb-viewer");
    const req = v && (v.requestFullscreen || v.webkitRequestFullscreen);
    const canFs = document.fullscreenEnabled || document.webkitFullscreenEnabled;
    if (req && canFs && !isIOSLike()) { try { const r = req.call(v); if (r && r.catch) r.catch(() => {}); } catch (e) {} }
  };
  function isIOSLike() { return /iP(hone|od|ad)/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1); }
  function fsEl() { return document.fullscreenElement || document.webkitFullscreenElement || null; }
  function exitFs() { try { const f = document.exitFullscreen || document.webkitExitFullscreen; if (fsEl() && f) { const r = f.call(document); if (r && r.catch) r.catch(() => {}); } } catch (e) {} }
  // 기기 전체 화면을 Esc·뒤로 등으로 빠져나오면 극장 모드도 같이 닫는다
  ["fullscreenchange", "webkitfullscreenchange"].forEach(ev => document.addEventListener(ev, () => {
    if (!fsEl() && document.body.classList.contains("pseudo-full-open")) pseudoFull(false);
  }));
  /* 극장 모드: 3D·VR 뷰어를 화면 가득 (닫기 단추·뒤로 가기·Esc 로 나온다) */
  function pseudoFull(on, fromPop) {
    const v = document.querySelector(".sb-viewer");
    if (!v) return;
    const was = document.body.classList.contains("pseudo-full-open");
    v.classList.toggle("pseudo-full", on);
    document.body.classList.toggle("pseudo-full-open", on);
    let x = document.getElementById("pfClose");
    if (on && !x) {
      x = document.createElement("button");
      x.id = "pfClose"; x.type = "button"; x.className = "pf-close"; x.textContent = "닫기";
      x.setAttribute("aria-label", "전체 화면 닫기");
      x.onclick = () => pseudoFull(false);
      v.appendChild(x);
    }
    if (x) x.hidden = !on;
    if (!on) exitFs();
    if (on && !was) { try { history.pushState({ kgeo: "full" }, ""); } catch (e) {} }
    if (!on && was && !fromPop && history.state && history.state.kgeo === "full") { try { history.back(); } catch (e) {} }
    setTimeout(resizeGLB, 80);
  }
  window.pseudoFull = pseudoFull;
  document.addEventListener("keydown", e => { if (e.key === "Escape" && document.body.classList.contains("pseudo-full-open")) pseudoFull(false); });

  document.addEventListener("fullscreenchange",       () => setTimeout(resizeGLB, 100));
  document.addEventListener("webkitfullscreenchange", () => setTimeout(resizeGLB, 100));

  /* ════ 목록 패널 ════ */
  let _allFeatures = [];

  window._loadListPanel = () => loadListPanel();
  async function loadListPanel() {
    try {
      await pointLayer.load();
      const q = pointLayer.createQuery();
      q.where         = "1=1";
      q.outFields     = ["*"];
      q.returnGeometry = true;
      q.orderByFields = ["pub_date DESC"];
      const fs = await pointLayer.queryFeatures(q);
      _allFeatures = fs.features;

      document.getElementById("ptCount").textContent = _allFeatures.length + "개";
      applyListFilter();
      probeListVr();                                       // 🥽 배지: VR 투어만 있는 작업 후보의 tour.json 을 확인한 뒤 다시 그린다
      if (currentAttrs) probeLinks(currentAttrs);          // ?select= 로 목록보다 먼저 연 기록도 같은 장소 묶기
    } catch(e) {
      console.warn("목록 로드 실패:", e);
      document.getElementById("lpList").innerHTML =
        '<div class="lp-empty"><b>기록을 불러오지 못했어요</b><span>' + esc(e && e.message || '') + '</span><button type="button" class="k-btn small" onclick="window._loadListPanel && window._loadListPanel()">다시 시도</button></div>';
    }
  }

  /* ── 🥽 VR 배지: 레이어에 pano_url 필드가 없어 VR 투어만 있는 작업 후보(GLB·스플랫 없음)의 tour.json 을 확인한다.
        3D 기록은 같은 장소에 VR 투어가 있으면 연결 배지(🥽↔)를 단다 ── */
  const _vrOwn = new Set(), _vrLinked = new Set();
  async function probeListVr() {
    const items = allItems();
    const cands = items.filter(it => fieldsKnown(it.a) ? !!it.a.pano_url : linkPanoCandidate(it.a)).slice(0, 60);
    let i = 0;
    const next = async () => {                             // 동시에 4개씩
      while (i < cands.length) {
        const it = cands[i++];
        const j = await fetchJsonCached(linkPanoUrl(it.a), _panoCache);
        if (j && (j.spots || []).length) _vrOwn.add(linkKey(it.a));
      }
    };
    await Promise.all([next(), next(), next(), next()]);
    _vrLinked.clear();
    const vr = items.filter(it => _vrOwn.has(linkKey(it.a)));
    if (vr.length) for (const it of items) {
      if (_vrOwn.has(linkKey(it.a))) continue;
      if (findSiblings(it, vr).length) _vrLinked.add(linkKey(it.a));
    }
    if (vr.length) applyListFilter();
  }
  const hasVr = a => _vrOwn.has(linkKey(a)) || _vrLinked.has(linkKey(a));

  function renderList(features) {
    const el = document.getElementById("lpList");
    if (!features.length) {
      el.innerHTML = _typeFilter === "vr"
        ? '<div class="lp-empty"><b>아직 VR 투어가 없어요</b><span>방 한가운데서 폰을 두 바퀴 돌리면 360° 투어가 만들어져요.</span><a class="k-btn primary small" href="capture_pano.html">VR 투어 찍기</a></div>'
        : _kw ? '<div class="lp-empty"><b>찾는 기록이 없어요</b><span>제목이나 메모의 다른 낱말로 찾아보세요.</span></div>'
        : '<div class="lp-empty"><b>아직 기록이 없어요</b><span>폰 카메라로 현장을 찍으면 3D 기록이 이 지도에 올라와요.</span><a class="k-btn primary small" href="capture.html?trench=0">3D 촬영 시작</a></div>';
      return;
    }
    const now = Date.now();
    const DAY = 86400000;
    el.innerHTML = features.map((feat) => {
      const i   = _allFeatures.indexOf(feat);          // 필터된 목록에서도 원본 인덱스로 연결
      const a   = feat.attributes;
      const dt  = a.pub_date ? new Date(a.pub_date) : null;
      const autoTitle = displayTitle(a) !== (a.scan_title || '');     // 제목이 이미 날짜면 날짜를 또 쓰지 않는다
      const dtStr = dt && !autoTitle ? `${dt.getMonth() + 1}월 ${dt.getDate()}일` : '';
      const isNew = dt && (now - dt.getTime()) < DAY * 3;
      const sid = a.scene_item_id || '';
      const t   = TYPE_INFO[a.scan_type] || null;
      const kind = recKind(a), k = KIND_INFO[kind];
      const thumb = a.thumb_url
        ? `<img class="lp-thumb" src="${esc(a.thumb_url)}" loading="lazy" alt="" onerror="this.outerHTML='<div class=&quot;lp-thumb lp-thumb-none&quot;></div>'">`
        : `<div class="lp-thumb lp-thumb-none"></div>`;
      // 함께 볼 수 있는 것: 사진 3D(스플랫)·정사영상·VR 투어 — 글자로 짧게 (기호만으로는 뜻을 모른다)
      const extras = [];
      if (kind === "lidar" && a.splat_url) extras.push("사진 3D");
      if (a.ortho_url) extras.push("정사영상");
      if (_vrOwn.has(linkKey(a)) || _vrLinked.has(linkKey(a))) extras.push("VR 투어");
      return `<div class="lp-item" data-sid="${esc(sid)}" data-idx="${i}" onclick="onListItemClick(${i})" role="button" tabindex="0" onkeydown="if(event.key==='Enter')onListItemClick(${i})">
        ${thumb}
        <div class="lp-item-body">
          <div class="lp-item-title">${esc(displayTitle(a))}${isNew ? '<span class="lp-item-new">새 기록</span>' : ''}</div>
          <div class="lp-item-meta">
            <span class="lp-item-kind"><span class="k-dot ${kind}"></span>${esc(k.label)}</span>
            ${a.place_name ? `<span class="lp-item-place">${esc(a.place_name)}</span>`
              : t ? `<span class="lp-item-type ${esc(a.scan_type)}">${esc(t.label)}</span>` : ''}
            ${dtStr ? `<span class="lp-item-date k-num">${dtStr}</span>` : ''}
          </div>
          ${extras.length ? `<div class="lp-item-extras">${extras.map(x => `<span>${esc(x)}</span>`).join('')}</div>` : ''}
        </div>
      </div>`;
    }).join('');
  }

  /* ── 묶음·겹친 핀 고르기 (2026-11-16 사용자: "포인트를 클릭하면 그 마커의 기록 중 어떤 걸 고를지 보이면 좋겠다") ──
        PC: 누른 자리 옆에 뜬 카드 / 폰: 아래 목록 시트 위에 붙은 카드. 항목을 누르면 그 기록을 연다 */
  function closePointPicker() { const el = document.getElementById("pointPicker"); if (el) el.remove(); }
  window.closePointPicker = closePointPicker;
  function showPointPicker(feats, ev, center) {
    closePointPicker();
    feats = feats.slice().sort((a, b) => (b.attributes.pub_date || 0) - (a.attributes.pub_date || 0));
    const box = document.createElement("div");
    box.id = "pointPicker"; box.className = "kpick"; box.setAttribute("role", "dialog"); box.setAttribute("aria-label", "이 자리의 기록");
    const places = [...new Set(feats.map(f => f.attributes.place_name).filter(Boolean))];
    box.innerHTML =
      `<div class="kpick-h"><b>이 자리의 기록 <span class="k-num">${feats.length}</span></b>` +
      (places.length === 1 ? `<small>${esc(places[0])}</small>` : "") +
      `<button type="button" class="kpick-x" aria-label="닫기">✕</button></div>` +
      `<div class="kpick-list">` + feats.map((f, i) => {
        const a = f.attributes, kind = recKind(a), k = KIND_INFO[kind];
        const dt = a.pub_date ? new Date(a.pub_date) : null;
        const auto = displayTitle(a) !== (a.scan_title || "");
        const sub = [k.label, !auto && dt ? `${dt.getMonth() + 1}월 ${dt.getDate()}일` : ""].filter(Boolean);
        const th = a.thumb_url ? `<img src="${esc(a.thumb_url)}" alt="" loading="lazy" onerror="this.replaceWith(Object.assign(document.createElement('span'),{className:'kpick-noth'}))">` : `<span class="kpick-noth"></span>`;
        return `<button type="button" class="kpick-it" data-i="${i}">${th}<span class="kpick-t"><b>${esc(displayTitle(a))}</b>` +
          `<small><span class="k-dot ${kind}"></span>${sub.map(esc).join(" ")}</small></span></button>`;
      }).join("") + `</div>` +
      `<button type="button" class="kpick-zoom">이 자리로 확대</button>`;
    box.querySelector(".kpick-x").onclick = closePointPicker;
    box.querySelector(".kpick-zoom").onclick = () => {
      closePointPicker();
      mapView.goTo({ target: center, zoom: Math.min(Math.max(mapView.zoom + 2, 17), 20) }, { duration: 500, easing: "ease-out" }).catch(() => {});
    };
    box.querySelectorAll(".kpick-it").forEach(btn => btn.onclick = () => {
      const f = feats[+btn.dataset.i]; closePointPicker(); if (f) openFeature(f);
    });
    const host = document.getElementById("viewDiv");
    host.appendChild(box);
    if (!isMobile()) {                     // 누른 자리 옆 (지도 안에 들어오게)
      const W = host.clientWidth, H = host.clientHeight, bw = box.offsetWidth, bh = box.offsetHeight;
      let x = ev.x + 18, y = ev.y - bh / 2;
      if (x + bw > W - 12) x = ev.x - bw - 18;
      box.style.left = Math.max(12, x) + "px";
      box.style.top = Math.max(12, Math.min(H - bh - 12, y)) + "px";
    }
    const first = box.querySelector(".kpick-it"); if (first) first.focus({ preventScroll: true });
  }
  async function openFeature(feat) {
    const oid = feat.attributes.OBJECTID || feat.attributes.objectid;
    try { await mapView.goTo({ target: feat.geometry, zoom: Math.max(mapView.zoom, 17) }, { duration: 600, easing: "ease-out" }); flashHighlight(oid); } catch (e) {}
    openSidebar(feat.attributes);
  }
  document.addEventListener("keydown", e => { if (e.key === "Escape") closePointPicker(); });
  mapView.on("drag", () => closePointPicker());
  mapView.on("mouse-wheel", () => closePointPicker());

  window.onListItemClick = async function(idx) {
    const feat = _allFeatures[idx];
    if (!feat) return;
    if (isMobile() && _lpOpen) toggleListPanel();       // 폰: 목록 오버레이 닫고 지도·사이드바로
    const oid = feat.attributes.OBJECTID || feat.attributes.objectid;
    try {
      await mapView.goTo({ target: feat.geometry, zoom: 17 },
                         { duration: 800, easing: "ease-in-out" });
      // goTo 완료 후 flash highlight
      flashHighlight(oid);
    } catch(e) {}
    openSidebar(feat.attributes);
  };

  // ArcGIS 공식 flash - highlight를 껐다 켜서 깜빡임 효과
  function flashHighlight(oid) {
    let count = 0;
    const interval = setInterval(() => {
      if (count % 2 === 0) {
        if (_highlightHandle) { _highlightHandle.remove(); _highlightHandle = null; }
      } else {
        highlightFeature(oid);
      }
      count++;
      if (count >= 6) {
        clearInterval(interval);
        highlightFeature(oid); // 마지막엔 켜진 상태로
      }
    }, 200);
  }

  function setListActive(sceneId) {
    document.querySelectorAll(".lp-item").forEach(el => {
      el.classList.toggle("active", !!sceneId && el.dataset.sid === sceneId);
    });
  }

  let _typeFilter = "";
  let _kw = "";
  function applyListFilter() {
    let fs = _allFeatures;
    if (_typeFilter === "vr") fs = fs.filter(f => hasVr(f.attributes));          // 🥽 VR 투어 (자기 것 + 같은 장소 연결)
    else if (_typeFilter) fs = fs.filter(f => (f.attributes.scan_type || '') === _typeFilter);
    if (_kw) fs = fs.filter(f => (f.attributes.scan_title || '').toLowerCase().includes(_kw) ||
                                 displayTitle(f.attributes).toLowerCase().includes(_kw) ||
                                 (f.attributes.place_name || '').toLowerCase().includes(_kw) ||
                                 KIND_INFO[recKind(f.attributes)].label.toLowerCase().includes(_kw) ||
                                 (f.attributes.note || '').toLowerCase().includes(_kw));
    document.getElementById("lpCount").textContent =
      fs.length !== _allFeatures.length ? `${fs.length} / ${_allFeatures.length}` : String(_allFeatures.length);
    renderList(fs);
    filterMap(fs);
  }
  /* 2026-11-16 UX 점검: 찾기·칩이 목록만 줄이고 지도는 그대로였다 → 지도 핀·묶음도 같은 결과만 보인다.
     걸러진 상태면 목록 위에 '지도를 결과에 맞추기' 단추 */
  let _mapFiltered = null;
  function filterMap(fs) {
    const on = !!(_kw || _typeFilter) && fs.length !== _allFeatures.length;
    const ids = on ? fs.map(f => f.attributes.OBJECTID ?? f.attributes.objectid).filter(v => v != null) : null;
    _mapFiltered = on ? fs : null;
    const apply = lv => { try { lv.filter = on ? { objectIds: ids.length ? ids : [-1] } : null; } catch (e) {} };
    if (_layerView) apply(_layerView); else if (typeof mapView !== "undefined" && pointLayer) mapView.whenLayerView(pointLayer).then(apply).catch(() => {});
    let b = document.getElementById("lpFit");
    if (!b) {
      b = document.createElement("button");
      b.type = "button"; b.id = "lpFit"; b.className = "lp-fit";
      b.onclick = () => {
        const g = (_mapFiltered || []).map(f => f.geometry).filter(Boolean);
        if (!g.length) return;
        if (isMobile() && _lpOpen) toggleListPanel();
        mapView.goTo(g.length === 1 ? { target: g[0], zoom: Math.max(mapView.zoom, 16) } : g, { duration: 600, easing: "ease-out" }).catch(() => {});
      };
      const f = document.getElementById("lpFilters");
      if (f) f.insertAdjacentElement("afterend", b);
    }
    b.hidden = !(on && fs.length);
    b.textContent = `지도를 찾은 기록 ${fs.length}개에 맞추기`;
  }
  window.filterList = function(val) { _kw = val.trim().toLowerCase(); applyListFilter(); };
  window.setTypeFilter = function(t) {
    _typeFilter = TYPE_INFO[t] || t === "vr" ? t : "";
    document.querySelectorAll("#lpFilters .lp-chip").forEach(el => el.classList.toggle("active", el.dataset.type === _typeFilter));
    applyListFilter();
  };

  let _lpOpen = true;
  /* 폰: 목록 시트 머리를 손가락으로 끌어 올리고 내린다 (2026-11-16). 짧게 누르면 예전처럼 열고 닫기 */
  (function sheetDrag() {
    const panel = document.getElementById("listPanel"), head = panel && panel.querySelector(".lp-head");
    if (!head) return;
    let y0 = 0, t0 = 0, base = 0, dragging = false, moved = false;
    head.addEventListener("pointerdown", e => {
      if (!isMobile() || e.target.closest("button")) return;
      dragging = true; moved = false; y0 = e.clientY; t0 = performance.now();
      const r = panel.getBoundingClientRect(), full = r.height;
      base = panel.classList.contains("collapsed") ? full - 80 : 0;
      panel.style.transition = "none";
      try { head.setPointerCapture(e.pointerId); } catch (err) {}
    });
    head.addEventListener("pointermove", e => {
      if (!dragging) return;
      const dy = e.clientY - y0;
      if (Math.abs(dy) > 6) moved = true;
      if (!moved) return;
      const full = panel.getBoundingClientRect().height;
      panel.style.transform = `translateY(${Math.max(0, Math.min(full - 80, base + dy))}px)`;
    });
    const end = e => {
      if (!dragging) return;
      dragging = false;
      panel.style.transition = ""; panel.style.transform = "";
      if (!moved) return;                                  // 짧게 누름: lp-head onclick 이 열고 닫는다
      head.dataset.dragged = "1"; setTimeout(() => { delete head.dataset.dragged; }, 50);
      const dy = e.clientY - y0, v = dy / Math.max(1, performance.now() - t0);
      const wantOpen = v < -0.3 || (v <= 0.3 && dy < -60) || (!_lpOpen && dy < -60);
      const wantClose = v > 0.3 || dy > 60;
      if (wantOpen && !_lpOpen) toggleListPanel();
      else if (wantClose && _lpOpen) toggleListPanel();
    };
    head.addEventListener("pointerup", end);
    head.addEventListener("pointercancel", end);
  })();
  window.toggleListPanel = function() {
    _lpOpen = !_lpOpen;
    const panel   = document.getElementById("listPanel");
    const openBtn = document.getElementById("btnLpOpen");
    const colBtn  = document.getElementById("btnLpCollapse");
    if (_lpOpen) {
      panel.classList.remove("collapsed");
      openBtn.style.display = "none";
      colBtn.textContent    = "◀";
    } else {
      panel.classList.add("collapsed");
      openBtn.style.display = "";
      colBtn.textContent    = "▶";
    }
  };

}); // require 끝

/* ── 업로드 모달 ── */
const _files = { las: null, glb: null, zip: null };
let _mode = "stray";                 // "stray" | "legacy"
let _scanType = "home";              // "home" (홈스캔) | "survey" (현장조사)
let _loc  = { lon: null, lat: null };

function setScanType(t) {
  _scanType = TYPE_INFO[t] ? t : "home";
  document.getElementById("typeHome").classList.toggle("active", _scanType === "home");
  document.getElementById("typeSurvey").classList.toggle("active", _scanType === "survey");
}

function openModal()  {
  document.getElementById("modal").classList.add("show");
  document.getElementById("mTitle").value = "";
  document.getElementById("mNote").value  = "";
  const tc = document.getElementById("titleCheck");
  if (tc) { tc.textContent = ""; tc.className = "title-check"; }
  for (const t of ["las", "glb", "zip"]) {
    _files[t] = null;
    document.getElementById(t + "Name").textContent = "";
    document.getElementById(t + "Zone").classList.remove("selected");
    const inp = document.querySelector("#" + t + "Zone input"); if (inp) inp.value = "";
  }
  document.getElementById("mElev").value = "";
  document.getElementById("mHeading").value = "";
  setLocationFields(null, null);
  if (window.clearPickMarker) window.clearPickMarker();
  setUploadMode(_mode);
  setScanType(_scanType);
}
function closeModal() {
  endMapPick();
  document.getElementById("modal").classList.remove("show");
  if (window.clearPickMarker) window.clearPickMarker();
}

function setUploadMode(mode) {
  _mode = mode;
  document.getElementById("tabStray").classList.toggle("active", mode === "stray");
  document.getElementById("tabLegacy").classList.toggle("active", mode === "legacy");
  document.getElementById("modeStray").style.display  = mode === "stray"  ? "" : "none";
  document.getElementById("modeLegacy").style.display = mode === "legacy" ? "" : "none";
}

function onFile(input, type) {
  const f = input.files[0]; if (!f) return;
  _files[type] = f;
  document.getElementById(type + "Name").textContent = f.name + "  (" + (f.size / 1048576).toFixed(1) + " MB)";
  document.getElementById(type + "Zone").classList.add("selected");
}

/* ── PC 에서 Stray 녹화 폴더를 그대로 고르면 브라우저가 zip 으로 묶는다 (압축 없이 담기만 해서 빠름) ── */
async function onFolder(input) {
  const files = Array.from(input.files || []);
  if (!files.length) return;
  const need = ["odometry.csv", "rgb.mp4"];
  const names = new Set(files.map(f => f.name));
  if (!need.every(n => names.has(n))) { alert("Stray Scanner 녹화 폴더가 아닙니다 (odometry.csv, rgb.mp4 필요)"); return; }
  let JSZipLib = window.JSZip;                            // 2026-11-16: 첫 화면에서 받지 않고 폴더를 고를 때 ES 모듈로
  if (!JSZipLib) {
    try { JSZipLib = (await import("https://cdn.jsdelivr.net/npm/jszip@3.10.1/+esm")).default; } catch (e) { JSZipLib = null; }
  }
  if (!JSZipLib) { alert("zip 프로그램을 받지 못했습니다. 폴더를 직접 압축해 올려 주세요."); return; }
  const nameEl = document.getElementById("zipName");
  const root = (files[0].webkitRelativePath || files[0].name).split("/")[0] || "scan";
  const zip = new JSZipLib();
  let total = 0;
  for (const f of files) { zip.file(f.webkitRelativePath || f.name, f); total += f.size; }
  nameEl.textContent = `폴더 ${root}: ${files.length}개 파일 (${(total / 1048576).toFixed(0)} MB) 묶는 중...`;
  try {
    const blob = await zip.generateAsync({ type: "blob", compression: "STORE" },
      meta => { nameEl.textContent = `폴더 ${root} 묶는 중... ${meta.percent.toFixed(0)}%`; });
    _files.zip = new File([blob], root + ".zip", { type: "application/zip" });
    nameEl.textContent = root + ".zip  (" + (blob.size / 1048576).toFixed(1) + " MB, 폴더에서 생성)";
    document.getElementById("zipZone").classList.add("selected");
  } catch (e) {
    nameEl.textContent = "";
    alert("폴더를 zip 으로 묶지 못했습니다: " + e.message);
  }
  input.value = "";
}

/* ── 업로드 (진행률 표시) ── */
function uploadWithProgress(url, fd, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    xhr.upload.onprogress = e => { if (e.lengthComputable) onProgress(e.loaded, e.total); };
    xhr.onload = () => {
      let data = null;
      try { data = JSON.parse(xhr.responseText); } catch (e) { data = { error: "서버 응답 오류 (HTTP " + xhr.status + ")" }; }
      resolve(data);
    };
    // IIS 가 HTTP/2 로 받은 CGI POST 의 응답을 끊는 문제(본문은 다 받아 작업은 만들어짐) → 호출 쪽에서 client_id 로 접수 확인
    xhr.onerror = () => { const e = new Error("네트워크 오류로 업로드에 실패했습니다"); e.network = true; e.sentAll = xhr._sentAll; reject(e); };
    xhr.upload.onload = () => { xhr._sentAll = true; };
    xhr.ontimeout = () => reject(new Error("업로드 시간 초과"));
    xhr.timeout = 30 * 60 * 1000;
    xhr.send(fd);
  });
}

/* ── 위치 지정 ── */
function setLocationFields(lon, lat) {
  _loc = { lon, lat };
  const el = document.getElementById("mLocText");
  if (lon == null || lat == null) {
    el.textContent = "지도에서 위치를 찍어 주세요";
    el.classList.add("empty");
  } else {
    el.textContent = `경도 ${lon.toFixed(6)}  위도 ${lat.toFixed(6)}`;
    el.classList.remove("empty");
  }
  document.getElementById("mLon").value = lon == null ? "" : lon;
  document.getElementById("mLat").value = lat == null ? "" : lat;
}
function startMapPick() {
  window._pickMode = true;
  document.getElementById("modal").classList.add("picking");
  document.getElementById("pickBanner").classList.add("show");
  document.getElementById("viewDiv").classList.add("picking");
}
function endMapPick() {
  window._pickMode = false;
  document.getElementById("modal").classList.remove("picking");
  document.getElementById("pickBanner").classList.remove("show");
  document.getElementById("viewDiv").classList.remove("picking");
}
function cancelMapPick() { endMapPick(); }
function useCurrentLocation() {
  if (!navigator.geolocation) { alert("이 브라우저는 위치를 지원하지 않습니다."); return; }
  const el = document.getElementById("mLocText");
  el.textContent = "현재 위치 확인 중...";
  navigator.geolocation.getCurrentPosition(pos => {
    const { longitude: lon, latitude: lat, accuracy } = pos.coords;
    setLocationFields(lon, lat);
    el.textContent += `  (±${Math.round(accuracy)} m)`;
    if (window.showPickMarker) window.showPickMarker(lon, lat);
    if (window.goToLocation)   window.goToLocation(lon, lat);
  }, err => {
    setLocationFields(null, null);
    alert("현재 위치를 가져오지 못했습니다: " + err.message + "\n지도에서 직접 찍어 주세요.");
  }, { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 });
}

async function checkTitle(val) {
  const title = val.trim();
  const el = document.getElementById("titleCheck");
  if (!title) { el.textContent = ""; return; }
  el.textContent = "확인 중...";
  el.className = "title-check";
  try {
    const r = await fetch(`/app/3dupload/check_title.py?title=${encodeURIComponent(title)}`);
    const d = await r.json();
    if (d.exists) {
      el.textContent = "⚠ 이미 사용 중인 제목입니다";
      el.className = "title-check error";
    } else {
      el.textContent = "✓ 사용 가능한 제목입니다";
      el.className = "title-check ok";
    }
  } catch(e) { el.textContent = ""; }
}

/* ── 진행 팝업 ── */
let _progressPopupOpen = false;
window.toggleProgressPopup = function() {
  const pp = document.getElementById("progressPopup");
  if (!pp) return;
  _progressPopupOpen = !_progressPopupOpen;
  pp.style.display = _progressPopupOpen ? "block" : "none";
};

const STEP_NAMES = ["대기 중", "입력 준비", "융합 · 사진 텍스처", "좌표 · LAS", "GLB 준비", "SLPK 생성", "Portal 발행", "완료"];
const STEP_PCTS  = [5, 15, 45, 55, 62, 78, 92, 100];
const LAST_STEP  = 7;

function updateProgressPopup(step, title, pct, msg) {
  const pp = document.getElementById("progressPopup");
  if (!pp) return;
  document.getElementById("ppTitle").textContent = title || "";
  document.getElementById("ppBar").style.width = (pct || 0) + "%";
  const m = document.getElementById("ppMsg"); if (m) m.textContent = msg || "";
  for (let i = 0; i <= LAST_STEP; i++) {
    const el = document.getElementById("ppStep" + i);
    if (!el) continue;
    el.className = "pp-step" + (i < step ? " done" : i === step ? " active" : "");
    const dot = el.querySelector(".pp-dot");
    if (dot) dot.className = "pp-dot";
  }
  // 진행 중이면 팝업을 작업마다 한 번만 자동 표시 (닫으면 헤더의 진행 표시를 눌러 다시 연다)
  if (pct > 0 && pct < 100 && !window._ppAutoShown) {
    window._ppAutoShown = true;
    pp.style.display = "block";
    _progressPopupOpen = true;
  }
}

/* ── 완료 팝업 ── */
let _doneSceneId = null;
let _doneGlbUrl  = null;
let _doneOid     = null;                          // 영상 현장조사: Scene·GLB 없이 점만 있어 objectid 로 찾는다
let _doneStatus  = null;                          // status.py 응답 (링크 공유·비공개는 지도 점 없이 이것으로 연다)
window.closeDoneModal = function() {
  document.getElementById("doneModal").classList.remove("show");
};
window.viewDoneScene = async function() {
  closeDoneModal();
  const pointLayer = window._pointLayer, mapView = window._mapView;
  const publicPoint = !_doneStatus || (_doneStatus.visibility || "public") === "public";
  if (!publicPoint || !pointLayer || !mapView) {           // 지도 점이 없거나 지도가 아직 안 떴다
    if (_doneStatus && window.openSidebar) openSidebar(attrsFromStatus(_doneStatus));
    return;
  }
  try {
    const q = pointLayer.createQuery();
    if (_doneSceneId)      q.where = `scene_item_id = '${_doneSceneId}'`;
    else if (_doneGlbUrl)  q.where = `glb_url = '${_doneGlbUrl}'`;
    else if (_doneOid)     { q.where = "1=1"; q.objectIds = [_doneOid]; }
    else { if (_doneStatus) openSidebar(attrsFromStatus(_doneStatus)); return; }
    q.outFields      = ["*"];
    q.returnGeometry = true;
    await pointLayer.when();
    await pointLayer.refresh();
    await new Promise(r => setTimeout(r, 800));
    const fs = await pointLayer.queryFeatures(q);
    if (fs.features.length) {
      const feat = fs.features[0];
      await mapView.goTo({ target: feat.geometry, zoom: 18 }, { duration: 700 });
      openSidebar(Object.assign({}, feat.attributes, _doneStatus ? { _job_id: _doneStatus.job_id, _visibility: _doneStatus.visibility } : {}));
      if (window._loadListPanel) window._loadListPanel();
    } else if (_doneStatus) {
      openSidebar(attrsFromStatus(_doneStatus));          // 지도에 점이 없다 → 상태 정보로 바로 연다
    }
  } catch(e) {
    console.warn("확대 실패:", e);
    if (_doneStatus) openSidebar(attrsFromStatus(_doneStatus));
  }
};

/* ── 헤더 업로드 진행 표시 ── */
function setUploadState(state, title, step, pct, msg) {
  const btnWrap  = document.getElementById("uploadBtnWrap");
  const btnEl    = document.getElementById("btnUpload");
  const progEl   = document.getElementById("uploadProgress");
  const upTitle  = document.getElementById("upTitle");
  const upBar    = document.getElementById("upBar");
  const upStep   = document.getElementById("upStep");

  if (state === "idle") {
    btnEl.style.display   = "";
    progEl.style.display  = "none";
    btnEl.style.borderColor = "";
  } else if (state === "processing") {
    btnEl.style.display   = "none";
    progEl.style.display  = "flex";
    progEl.style.borderColor = "rgba(56,189,248,0.4)";
    upTitle.textContent  = msg || "처리 중...";
    upBar.style.background = "#38bdf8";
    upBar.style.width    = (pct || 0) + "%";
    upStep.textContent   = `STEP ${step || 0} / ${LAST_STEP}`;
    updateProgressPopup(step, msg, pct, window._lastStatusMsg || "");
  } else if (state === "done") {
    progEl.style.borderColor = "rgba(74,222,128,0.4)";
    upTitle.textContent  = "✓ 완료: " + title;
    upBar.style.background = "#4ade80";
    upBar.style.width    = "100%";
    upStep.textContent   = `${LAST_STEP} / ${LAST_STEP}`;
    document.querySelector(".up-spinner").style.borderTopColor = "#4ade80";
    // 진행 팝업 닫기
    const pp = document.getElementById("progressPopup");
    if (pp) pp.style.display = "none";
    setTimeout(() => setUploadState("idle"), 4000);
  } else if (state === "error") {
    progEl.style.borderColor = "rgba(239,68,68,0.4)";
    upTitle.textContent  = "❌ " + (msg || "오류");
    upBar.style.background = "#ef4444";
    document.querySelector(".up-spinner").style.borderTopColor = "#ef4444";
    const pp = document.getElementById("progressPopup");
    if (pp) pp.style.display = "none";
    setTimeout(() => setUploadState("idle"), 5000);
  }
}

async function startUpload() {
  const titleEl = document.getElementById("mTitle");
  const checkEl = document.getElementById("titleCheck");
  const title = titleEl.value.trim();
  if (!title)                                         { alert("스캔 제목을 입력해주세요."); return; }
  if (checkEl && checkEl.classList.contains("error")) { alert("이미 사용 중인 제목입니다."); return; }

  const clientId = "web-" + ((window.crypto && crypto.randomUUID) ? crypto.randomUUID()
                   : Date.now().toString(36) + Math.random().toString(36).slice(2));
  const fd = new FormData();
  fd.append("title", title);
  fd.append("note",  document.getElementById("mNote").value);
  fd.append("mode",  _mode);
  fd.append("scan_type", _scanType);
  fd.append("client_id", clientId);
  fd.append("app", "web");
  if (_mode === "stray") {
    if (!_files.zip)                     { alert("Stray Scanner 녹화 zip 파일을 선택해주세요."); return; }
    if (_loc.lon == null || _loc.lat == null) { alert("스캔 위치를 지도에서 찍거나 현재 위치로 지정해주세요."); return; }
    fd.append("scan_zip", _files.zip);
    fd.append("lon", _loc.lon);
    fd.append("lat", _loc.lat);
    const elev = document.getElementById("mElev").value.trim();
    const hdg  = document.getElementById("mHeading").value.trim();
    if (elev !== "") fd.append("elev", elev);
    if (hdg  !== "") fd.append("heading", hdg);
  } else {
    if (!_files.las) { alert("LAS 파일을 선택해주세요."); return; }
    if (!_files.glb) { alert("GLB 파일을 선택해주세요."); return; }
    fd.append("las_file", _files.las);
    fd.append("glb_file", _files.glb);
  }

  closeModal();
  const totalMB = ((_mode === "stray" ? _files.zip.size : _files.las.size + _files.glb.size) / 1048576).toFixed(0);
  setUploadState("processing", title, 0, 5, `파일 업로드 중... (${totalMB} MB)`);

  try {
    const data = await uploadWithProgress("/app/3dupload/upload.py", fd, (loaded, total) => {
      const pct = Math.round(loaded / total * 100);
      setUploadState("processing", title, 0, Math.max(1, Math.round(pct * 0.1)),
                     `업로드 중 ${pct}%  (${(loaded / 1048576).toFixed(0)} / ${(total / 1048576).toFixed(0)} MB)`);
    });
    if (!data.job_id) throw new Error(data.error || "업로드 실패");
    trackJob(data.job_id, title);
  } catch(err) {
    if (err.network) {
      // 응답만 끊긴 경우가 많다: 서버에 이 업로드(client_id)로 만든 작업이 있는지 확인
      setUploadState("processing", title, 0, 10, "서버 접수 확인 중...");
      const jobId = await findJobByClientId(clientId, err.sentAll ? 90 : 20);
      if (jobId) { trackJob(jobId, title); return; }
    }
    setUploadState("error", title, 0, 0, err.message);
  }
}

/* client_id 로 서버 작업을 찾는다 (3초 간격, 최대 seconds 초). 찾으면 job_id, 못 찾으면 null */
async function findJobByClientId(clientId, seconds) {
  const until = Date.now() + seconds * 1000;
  while (Date.now() < until) {
    try {
      const r = await fetch(`/app/3dupload/find_job.py?client_id=${encodeURIComponent(clientId)}`, { cache: "no-store" });
      if (r.ok) { const d = await r.json(); if (d.job_id) return d.job_id; }
    } catch (e) {}
    await new Promise(res => setTimeout(res, 3000));
  }
  return null;
}

/* ── 작업 추적: 업로드 직후, ?job=<id> (아이폰 단축어·앱), 새로고침 뒤 이어서 ── */
const JOBS_KEY = "kgeoscan_jobs";
function loadJobs()  { try { return JSON.parse(localStorage.getItem(JOBS_KEY) || "[]"); } catch (e) { return []; } }
function saveJobs(l) { try { localStorage.setItem(JOBS_KEY, JSON.stringify(l.slice(-5))); } catch (e) {} }
function rememberJob(jobId, title) { saveJobs(loadJobs().filter(j => j.job_id !== jobId).concat([{ job_id: jobId, title: title || "", t: Date.now() }])); }
function forgetJob(jobId) { saveJobs(loadJobs().filter(j => j.job_id !== jobId)); }

let _tracking = null;
function hideProgressPopup() { const pp = document.getElementById("progressPopup"); if (pp) pp.style.display = "none"; }
async function trackJob(jobId, title) {
  if (!/^[0-9a-f]{8}$/.test(jobId || "") || _tracking === jobId) return;
  _tracking = jobId;
  title = title || "";
  rememberJob(jobId, title);
  setUploadState("processing", title, 0, STEP_PCTS[0], "처리 대기 중...");
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const finish = () => { _tracking = null; forgetJob(jobId); window._lastStatusMsg = ""; };
  window._ppAutoShown = false;
  for (let i = 0; i < 600; i++) {                 // 3초 × 600 = 30분 (Stray 처리 + SLPK + 발행)
    try {
      const sr = await statusFetch(jobId);
      if (sr.status === 404 || sr.status === 400) {   // 2026-11-16 UX 점검: 'STEP 0/7' 알약 대신 안내 카드, 잘못 저장된 관리 키도 지운다
        finish(); setUploadState("idle"); hideProgressPopup(); forgetEditKey(jobId); renderMine();
        showNotFound();
        return;
      }
      const sd = await sr.json();
      if (sd.visibility === "private" && sd.step === undefined) {     // 관리 키 없이 연 비공개 기록
        finish(); setUploadState("idle"); hideProgressPopup();
        showNotFound("비공개 기록이에요. 올린 사람이 보낸 관리 링크로 열어야 볼 수 있어요.");
        return;
      }
      if (i === 0 && sd.status === "done") {          // 공유 링크(?job=)로 이미 끝난 기록을 열었다 → 팝업·완료 알약 없이 바로 연다
        finish(); setUploadState("idle"); hideProgressPopup();
        openFromStatus(sd);
        return;
      }
      if (!title && sd.title) { title = sd.title; rememberJob(jobId, title); }
      const step = Math.min(sd.step || 0, LAST_STEP);
      window._lastStatusMsg = sd.message || "";
      setUploadState("processing", title, step, STEP_PCTS[step], (sd.step_name || STEP_NAMES[step]) + "...");

      if (sd.status === "done") {
        finish();
        setUploadState("done", title, LAST_STEP, 100, "");
        _doneSceneId = sd.scene_item_id || null;
        _doneGlbUrl  = sd.glb_url || null;
        _doneOid     = sd.objectid || null;
        _doneStatus  = sd;
        setTimeout(() => {
          const dm = document.getElementById("doneModal");
          if (dm) {
            document.getElementById("doneModalTitle").textContent = "기록이 다 만들어졌어요";
            // 2026-11-16 UX 점검: SLPK·GPU 워커·✦ 스플랫 같은 말 대신 지금 탭 이름(사진 3D·지하시설물)과 쉬운 말로
            document.getElementById("doneModalMsg").innerHTML =
              `<strong style="color:var(--text)">${esc(title)}</strong> ` + ((sd.visibility || "public") === "public" ? "기록이 지도에 올라갔어요."
                : sd.visibility === "private" ? "비공개 기록이에요. 관리 링크가 있는 사람만 볼 수 있어요." : "링크 공유 기록이에요. 지도·목록에는 나오지 않고 링크를 받은 사람만 봐요.") +
              (sd.mode === "pano" ? "<br><span style='color:var(--accent)'>'보기'를 누르면 360° 사진으로 지점 사이를 오가며 둘러볼 수 있어요.</span>"
                : sd.mode === "video" ? "<br><span style='color:var(--acc-o)'>사진 3D는 서버가 영상으로 만드는 중이에요(보통 10~30분). 다 되면 목록에서 열어 '사진 3D'로 보세요.</span>"
                : "") +
              (sd.mode !== "video" && (sd.splat_status === "pending" || sd.splat_status === "processing")
                ? "<br><span style='color:var(--acc-o)'>사진 3D는 몇 분 뒤 더해져요. 다 되면 목록에서 다시 열어 '사진 3D' 탭을 누르세요.</span>" : "") +
              (sd.utilities_url ? "<br><span style='color:var(--accent)'>굴착 기록: 목록에서 열어 '지하시설물' 탭에서 관 위치·깊이를 보고 '조서·산출물'을 내려받으세요.</span>" : "") +
              (sd.message && sd.message !== "처리 완료" ? `<br><span style='color:var(--text3)'>${esc(sd.message)}</span>` : "");
            dm.classList.add("show");
          } else {
            if (sd.scene_item_id) location.href = `/app/3dscan/?select=${sd.scene_item_id}`;
            else location.reload();
          }
        }, 1200);
        return;
      }
      if (sd.status === "failed") {
        finish();
        setUploadState("error", title, 0, 0, sd.message || "처리 실패");
        return;
      }
    } catch(e) {}
    await sleep(3000);
  }
  finish();
  setUploadState("error", title, 0, 0, "시간 초과");
}

window.addEventListener("DOMContentLoaded", () => {
  const p   = new URLSearchParams(window.location.search);
  const job = (p.get("job") || "").trim().toLowerCase();
  const km  = (window.location.hash || "").match(/[#&]key=([A-Za-z0-9_\-]{10,100})/);
  if (km && /^[0-9a-f]{8}$/.test(job)) saveEditKey(job, km[1]);   // 관리 링크로 열었다 → 이 기기의 '내 기록'에 넣는다 (없는 작업이면 trackJob 이 지운다)
  renderMine();
  if (/^[0-9a-f]{8}$/.test(job)) { trackJob(job, ""); return; }
  if (p.has("job")) { showNotFound(); return; }                   // ?job= 값이 작업 번호 모양이 아니다
  // 새로고침·재방문: 24시간 안에 시작했고 아직 끝나지 않은 최근 작업을 이어서 보여 준다
  const recent = loadJobs().filter(j => Date.now() - j.t < 86400000).pop();
  if (recent) trackJob(recent.job_id, recent.title);
});


/* ════ 공개 범위·관리 키·내 기록 (docs/share_contract.md 1·2절, 2026-11-12) ════
   관리 키는 업로드 응답으로 한 번만 나오고 이 기기 localStorage['kgeo_keys'] 에만 둔다 (서버에는 해시만).
   link·private 기록은 지도(scan_points)에 점이 없으므로 status.py 응답으로 attrs 를 만들어 openSidebar 로 연다 */
const KEYS_KEY = "kgeo_keys";
const VIS_INFO = { public: { icon: "🌐", label: "공개" }, link: { icon: "🔗", label: "링크 공유" }, private: { icon: "🔒", label: "비공개" } };
function loadEditKeys() { try { const o = JSON.parse(localStorage.getItem(KEYS_KEY) || "{}"); return o && typeof o === "object" && !Array.isArray(o) ? o : {}; } catch (e) { return {}; } }
function saveEditKey(job, key) { try { const o = loadEditKeys(); o[job] = key; localStorage.setItem(KEYS_KEY, JSON.stringify(o)); } catch (e) {} }
function forgetEditKey(job) { try { const o = loadEditKeys(); if (job in o) { delete o[job]; localStorage.setItem(KEYS_KEY, JSON.stringify(o)); } } catch (e) {} }
function editKeyFor(job) { return loadEditKeys()[job] || null; }
function statusFetch(job) {
  const k = editKeyFor(job);
  return fetch(`/app/3dupload/status.py?job_id=${job}`, { cache: "no-store", headers: k ? { "X-Edit-Key": k } : {} });
}
let _visJob = null;                               // 지금 사이드바에 열린 기록의 작업 번호 (status 로 연 경우)
function setVisTag(v) {
  const t = document.getElementById("sbVisTag"); if (!t) return;
  const i = VIS_INFO[v] || VIS_INFO.public;
  t.textContent = i.label;
  t.className = "sb-tag " + (v === "link" ? "vis-link" : v === "private" ? "vis-private" : "green");
}
function attrsFromStatus(sd) {
  _visJob = sd.job_id;
  return {
    objectid: sd.objectid || null, scan_title: sd.title || sd.job_id, scan_type: sd.scan_type, note: "",
    glb_url: sd.glb_url || null, thumb_url: sd.thumb_url || null, splat_url: sd.splat_url || null,
    ortho_url: sd.ortho_url || null, pano_url: sd.pano_url || null, floorplan_url: sd.floorplan_url || null,
    scene_item_id: sd.scene_item_id || null, site_id: sd.site_id || null, pub_date: null, author: "",
    _job_id: sd.job_id, _visibility: sd.visibility || "public",
  };
}
async function openFromStatus(sd) {
  _doneSceneId = sd.scene_item_id || null; _doneGlbUrl = sd.glb_url || null; _doneOid = sd.objectid || null; _doneStatus = sd;
  for (let i = 0; i < 40 && !window.openSidebar; i++) await new Promise(r => setTimeout(r, 200));   // 지도·사이드바 준비 대기
  if ((sd.visibility || "public") === "public" && sd.objectid) {
    for (let i = 0; i < 40 && !window._pointLayer; i++) await new Promise(r => setTimeout(r, 200));
  }
  window.viewDoneScene();
}
async function setVisibility(job, v) {
  const k = editKeyFor(job); if (!k) return null;
  try {
    const r = await fetch("/app/3dupload/edit.py", { method: "POST", cache: "no-store",
      headers: { "Content-Type": "application/json", "X-Edit-Key": k }, body: JSON.stringify({ op: "visibility", job_id: job, visibility: v }) });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.error || ("HTTP " + r.status));
    return d;
  } catch (e) { alert("공개 범위를 바꾸지 못했습니다: " + e.message); return null; }
}
async function renderMine() {
  const box = document.getElementById("lpMine"); if (!box) return;
  const jobs = Object.keys(loadEditKeys()).filter(j => /^[0-9a-f]{8}$/.test(j));
  if (!jobs.length) { box.hidden = true; return; }
  box.hidden = false;
  box.innerHTML = `<div class="lp-mine-head">🔑 내 기록 <small>(이 기기에 관리 키가 있는 기록 ${jobs.length}개)</small></div>`;
  for (const job of jobs.slice(-30).reverse()) {
    const row = document.createElement("div");
    row.className = "lp-mine-item"; row.dataset.job = job;
    row.innerHTML = `<span class="t">${esc(job)}</span><span class="st">확인 중…</span>`;
    box.appendChild(row);
    statusFetch(job).then(r => r.ok ? r.json() : null).then(sd => {
      if (!sd) { row.querySelector(".st").textContent = "없음"; return; }
      const vis = sd.visibility || "public";
      row.innerHTML = `<span class="t" title="${esc(sd.title || job)}">${esc(sd.title || job)}</span>` +
        `<span class="st">${sd.status === "done" ? "완료" : sd.status === "failed" ? "실패" : "처리 중"}</span>` +
        `<select title="공개 범위">${Object.entries(VIS_INFO).map(([k, i]) => `<option value="${k}"${k === vis ? " selected" : ""}>${i.icon} ${i.label}</option>`).join("")}</select>` +
        `<button type="button" title="관리 링크 복사">🔑</button>`;
      row.onclick = ev => { if (ev.target.closest("select,button")) return; if (sd.status === "done") openFromStatus(sd); else trackJob(job, sd.title || ""); };
      row.querySelector("select").onchange = async ev => {
        const d = await setVisibility(job, ev.target.value);
        if (!d) { ev.target.value = vis; return; }
        sd.visibility = d.visibility;
        if (_visJob === job) setVisTag(d.visibility);
        if (window._loadListPanel) setTimeout(() => window._loadListPanel(), 6000);   // 공개로 바꿨으면 지도 등록 뒤 목록 새로 고침
      };
      row.querySelector("button").onclick = () => {
        const url = `${location.origin}/app/3dscan/?job=${job}#key=${editKeyFor(job)}`;
        (navigator.clipboard ? navigator.clipboard.writeText(url) : Promise.reject()).then(
          () => { const b = row.querySelector("button"); b.textContent = "✓"; setTimeout(() => { b.textContent = "🔑"; }, 1500); },
          () => prompt("관리 링크 (길게 눌러 복사)", url));
      };
    }).catch(() => { row.querySelector(".st").textContent = "확인 실패"; });
  }
}

/* ════ 시작 화면 (2026-11-13 사용자: "들어가면 골라 갈 수 있게") ════
   ?job= 같은 바로가기 주소로 들어왔거나 '다음부터 바로 지도 보기'를 켰으면 띄우지 않는다. 위쪽 ☰ 시작 으로 다시 연다 */
(function () {
  const SKIP_KEY = "kgeo_start_skip";
  const sheet = document.getElementById("startSheet");
  if (!sheet) return;
  const lsGet = k => { try { return localStorage.getItem(k); } catch (e) { return null; } };
  const lsSet = (k, v) => { try { if (v == null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch (e) {} };
  const mineCount = () => { try { return Object.keys(loadEditKeys()).length; } catch (e) { return 0; } };
  /* kgeoScan 아이폰 앱 안 (2026-11-16): 앱이 문서 시작 때 window.kgeoApp = {platform, version, lidar} 를 넣는다.
     LiDAR 카드 → 앱의 LiDAR 촬영(새 스캔)으로, '이 폰의 LiDAR 스캔' 카드 → 앱에 저장된 녹화 목록으로 (앱 쪽: kgeoscan-ios WebHome.swift) */
  const appBridge = (window.kgeoApp && window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.kgeoApp) || null;
  const appLidar = !!(appBridge && window.kgeoApp.lidar !== false);
  const toApp = action => { try { appBridge.postMessage({ action }); return true; } catch (e) { return false; } };
  if (appBridge) {
    const up = sheet.querySelector('[data-go="upload"]');
    if (up && appLidar) {
      up.querySelector(".st").innerHTML = "<b>LiDAR 스캔</b><small>이 앱으로 바로 찍어 올리면 실측 3D·평면도가 나와요. 크기를 잴 수 있어요.</small>";
      up.setAttribute("data-go", "app-lidar");
      const list = document.createElement("button");
      list.type = "button"; list.className = "start-card k-lidar"; list.setAttribute("data-go", "app-scans");
      list.innerHTML = '<span class="si"><svg viewBox="0 0 28 28" width="28" height="28" aria-hidden="true"><rect x="6" y="5" width="16" height="19" rx="3" fill="none" stroke="currentColor" stroke-width="2"/><path d="M10 11h8M10 15h8M10 19h5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg></span><span class="st"><b>이 폰의 LiDAR 스캔</b><small>앱에 저장된 녹화를 보고, 올리지 못한 것을 다시 올려요.</small></span>';
      up.after(list);
    } else if (up) {
      up.querySelector(".st small").textContent = "이 아이폰엔 LiDAR 가 없어요 — 다른 기기의 녹화 zip 올리기";
    }
  }
  window.openStart = function () {
    const n = mineCount(), m = document.getElementById("startMine"), s = document.getElementById("startMineN");
    if (m) m.hidden = !n;
    if (s) s.textContent = n ? `(${n})` : "";
    const cb = document.getElementById("startSkip");
    if (cb) cb.checked = lsGet(SKIP_KEY) === "1";
    sheet.hidden = false;
    document.body.classList.add("start-open");
    // 폰 '뒤로'가 사이트를 나가지 않고 이 화면을 닫게 (2026-11-16)
    try { if (!(history.state && history.state.kgeo === "start")) history.pushState({ kgeo: "start" }, ""); } catch (e) {}
  };
  function closeStart() {
    if (sheet.hidden) return;
    sheet.hidden = true; document.body.classList.remove("start-open");
    try { if (history.state && history.state.kgeo === "start") history.back(); } catch (e) {}
  }
  window.closeStartSheet = function () { if (!sheet.hidden) { sheet.hidden = true; document.body.classList.remove("start-open"); } };
  function openListPanel() {
    const panel = document.getElementById("listPanel");
    if (panel && panel.classList.contains("collapsed") && typeof window.toggleListPanel === "function") window.toggleListPanel();
  }
  sheet.addEventListener("click", e => {
    if (e.target === sheet) { closeStart(); return; }
    const b = e.target.closest("[data-go]");
    if (!b) return;
    const go = b.getAttribute("data-go");
    closeStart();
    if (go === "app-lidar" && toApp("lidar")) return;
    if (go === "app-scans" && toApp("scans")) return;
    if (go === "upload" && typeof window.openModal === "function") window.openModal();
    else if (go === "upload" && typeof openModal === "function") openModal();
    else if (go === "mine") {
      openListPanel();
      const box = document.getElementById("lpMine");
      if (box) setTimeout(() => box.scrollIntoView({ behavior: "smooth", block: "start" }), 250);
    } else if (go === "map" && window.matchMedia("(max-width: 768px)").matches) {
      // 휴대폰: 지도부터 보이고 목록은 왼쪽 ▸ 로 연다 (그대로 둠)
    }
  });
  document.addEventListener("keydown", e => { if (e.key === "Escape" && !sheet.hidden) closeStart(); });
  const cb = document.getElementById("startSkip");
  if (cb) cb.addEventListener("change", () => lsSet(SKIP_KEY, cb.checked ? "1" : null));
  const p = new URLSearchParams(location.search);
  const deep = ["select", "job", "type", "site", "site_id", "oid", "id"].some(k => p.has(k)) || location.hash.length > 1;
  if (!deep && lsGet(SKIP_KEY) !== "1") window.openStart();
})();
