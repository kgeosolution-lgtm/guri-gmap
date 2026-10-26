/* ============================================================
   kgeoScan Viewer - Main Script (Three.js GLB Viewer)
   ============================================================ */
require([
  "esri/config",
  "esri/WebMap",
  "esri/views/MapView",
  "esri/layers/FeatureLayer",
  "esri/renderers/SimpleRenderer",
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
], function(
  esriConfig, WebMap, MapView, FeatureLayer, SimpleRenderer, SimpleMarkerSymbol,
  Home, Zoom, BasemapToggle, Search, ScaleBar, Graphic,
  Basemap, TileLayer, VectorTileLayer, WebTileLayer
) {
  /* ── 배경지도: WebMap 에 저장된 네이버 타일은 CORS 로 막혀 안 보이므로
        다른 kgeodata 앱(goyang1000_page/basemaps.js)과 같은 구성을 코드에서 만든다 ── */
  function makeBasemap(kind) {
    if (kind === "imagery") {
      return new Basemap({
        title: "영상", id: "kgeo-imagery",
        baseLayers: [
          new TileLayer({ url: "https://services.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer", maxScale: 25000000 }),
          new WebTileLayer({ urlTemplate: "https://cdn.vworld.kr/2d/Satellite/service/{level}/{col}/{row}.jpeg", copyright: "VWORLD" })
        ]
      });
    }
    return new Basemap({
      title: "지형", id: "kgeo-gray",
      baseLayers: [
        new TileLayer({ url: "https://services.arcgisonline.com/arcgis/rest/services/Elevation/World_Hillshade/MapServer", opacity: 0.65 }),
        new VectorTileLayer({ url: "https://cdn.arcgis.com/sharing/rest/content/items/d9b6f47909c74f1fb5c7cefd14470e68/resources/styles/root.json", maxScale: 3000000 }),
        new VectorTileLayer({ url: "https://kgeodata.com/server/rest/services/Hosted/NGII_GRAY_2026/VectorTileServer/resources/styles/root.json", minScale: 12000000, blendMode: "multiply" })
      ]
    });
  }
  esriConfig.portalUrl = "https://kgeodata.com/portal";
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

  /* ── MapView ── */
  const webmap = new WebMap({ portalItem: { id: WEBMAP_ID } });
  webmap.load().then(() => { webmap.basemap = makeBasemap("gray"); }).catch(() => {});
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


  mapView.when(async () => {
    document.getElementById("mapLoading").classList.add("done");
    pointLayer.queryFeatureCount()
      .then(cnt => { document.getElementById("ptCount").textContent = cnt + "개"; })
      .catch(() => {});

    loadListPanel();

    // ── 레이어뷰 등록
    mapView.whenLayerView(pointLayer).then(lv => { _layerView = lv; });

    // ── 위젯 추가 - 지도 왼쪽에 배치 (우측은 사이드바에 가려짐)
    mapView.ui.add(new Zoom({ view: mapView }), "top-left");
    mapView.ui.add(new Home({ view: mapView }), "top-left");
    mapView.ui.add(new ScaleBar({ view: mapView, style: "line", unit: "metric" }), "bottom-left");
    mapView.ui.add(new BasemapToggle({ view: mapView, nextBasemap: makeBasemap("imagery") }), "bottom-left");

    // URL 파라미터로 피처 자동 선택 (?select=<scene_item_id>)
    const urlParams    = new URLSearchParams(window.location.search);
    const autoSelectId = urlParams.get("select");
    if (autoSelectId) {
      try {
        await pointLayer.load();
        const q = pointLayer.createQuery();
        q.where          = "scene_item_id = '" + autoSelectId + "'";
        q.outFields      = ["*"];
        q.returnGeometry = true;
        const fs = await pointLayer.queryFeatures(q);
        if (fs.features.length) {
          const feat = fs.features[0];
          await mapView.goTo({ target: feat.geometry, zoom: 17 }, { duration: 800 });
          openSidebar(feat.attributes);
        }
      } catch(e) { console.warn("자동선택 실패:", e); }
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
    const res = await mapView.hitTest(e, { include: [pointLayer] });
    if (!res.results.length) return;
    const g = res.results[0].graphic;
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

    const fmt = v => v ? new Date(v).toLocaleString('ko-KR') : "—";

    document.getElementById("sbTitle").textContent    = attrs.scan_title || "—";
    document.getElementById("sbAuthor").textContent   = attrs.author     || "—";
    document.getElementById("sbDate").textContent     = fmt(attrs.pub_date);
    document.getElementById("aTitle").textContent     = attrs.scan_title || "—";
    document.getElementById("aDate").textContent      = fmt(attrs.pub_date);
    document.getElementById("aNote").textContent      = attrs.note       || "—";
    document.getElementById("aSceneId").textContent   = attrs.scene_item_id || "—";

    const sceneLink = document.getElementById("aSceneUrl");
    if (attrs.scene_item_id) {
      sceneLink.href = `https://kgeodata.com/portal/home/item.html?id=${attrs.scene_item_id}`;
      sceneLink.style.display = "";
    } else {
      sceneLink.style.display = "none";
    }

    setWidth("40vw");
    isExpanded = false;
    document.getElementById("btnExpand").classList.add("active");
    document.getElementById("sidebar").classList.add("open", "expanded");

    // GLB URL 우선, 없으면 glb_url 필드 사용
    const glbUrl = attrs.glb_url || null;
    if (glbUrl) {
      loadGLBViewer(glbUrl);
    } else {
      // glb_url 필드 없으면 로딩 실패 표시
      const loadingEl = document.getElementById("sceneLoading");
      const loadText  = document.querySelector(".scene-load-text");
      loadingEl.classList.remove("done");
      loadText.textContent = "GLB 파일 정보 없음";
      setTimeout(() => loadingEl.classList.add("done"), 1000);
    }

    setListActive(attrs.scene_item_id || attrs.OBJECTID || attrs.objectid);
  };

  window.closeSidebar = function() {
    document.getElementById("sidebar").classList.remove("open", "expanded");
    setWidth("0px");
    isExpanded = false;
    document.getElementById("btnExpand").classList.remove("active");
    destroyGLB();
    setListActive(null);
  };

  /* ── 50:50 토글 ── */
  window.toggleExpand = function() {
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
      const pxVal = w.endsWith("vw")
        ? Math.round(window.innerWidth * parseFloat(w) / 100)
        : px;
      mapView.padding = { top: 0, right: pxVal, bottom: 0, left: 0 };
      // transition 완료 후 resize
      setTimeout(() => {
        try { mapView.resize(); } catch(e) {}
      }, 380);
    }
  }

  /* ════ Three.js GLB 뷰어 ════ */
  function destroyGLB() {
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

  function loadGLBViewer(glbUrl) {
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
            glbCamera.position.set(dist * 0.6, dist * 0.5, dist);
            glbControls.target.set(0, 0, 0);
            glbControls.update();
          }
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

        // ── 조작 도움말 표시
        const helpEl = document.createElement('div');
        helpEl.id = 'glbHelp';
        helpEl.style.cssText = `
          position:absolute; bottom:10px; left:50%; transform:translateX(-50%);
          background:rgba(0,0,0,0.55); color:#ccc; font-size:11px;
          padding:5px 12px; border-radius:20px; pointer-events:none;
          white-space:nowrap; letter-spacing:0.3px;
        `;
        helpEl.innerHTML = '좌클릭: 회전 &nbsp;|&nbsp; 우클릭: 이동 &nbsp;|&nbsp; 휠: 줌 &nbsp;|&nbsp; WASD/방향키: 이동 &nbsp;|&nbsp; R: 리셋 &nbsp;|&nbsp; 더블클릭: 포커스';
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

          glbControls.update();
          glbRenderer.render(glbScene, glbCamera);
        }
        animate();
      },
      (xhr) => {
        if (xhr.total) {
          const pct = Math.round(xhr.loaded / xhr.total * 100);
          loadText.textContent = `3D 모델 로딩 중... ${pct}%`;
        }
      },
      (err) => {
        console.error("GLB 로드 실패:", err);
        loadingEl.classList.add("done");
        loadText.textContent = "GLB 로드 실패: " + (err.message || err);
      }
    );

    window.addEventListener("resize", resizeGLB);
  }

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
    const el = document.getElementById("sceneDiv");
    if (!el) return;
    const req = el.requestFullscreen
      || el.webkitRequestFullscreen
      || el.mozRequestFullScreen
      || el.msRequestFullscreen;
    if (req) req.call(el);
  };

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

      document.getElementById("lpCount").textContent = _allFeatures.length;
      document.getElementById("ptCount").textContent = _allFeatures.length + "개";
      renderList(_allFeatures);
    } catch(e) {
      console.warn("목록 로드 실패:", e);
      document.getElementById("lpList").innerHTML =
        '<div class="lp-empty">목록 로드 실패<br>' + e.message + '</div>';
    }
  }

  function renderList(features) {
    const el = document.getElementById("lpList");
    if (!features.length) {
      el.innerHTML = '<div class="lp-empty">등록된 스캔이 없습니다.<br>＋ 스캔 업로드로 추가하세요.</div>';
      return;
    }
    const now = Date.now();
    const DAY = 86400000;
    el.innerHTML = features.map((feat, i) => {
      const a   = feat.attributes;
      const dt  = a.pub_date ? new Date(a.pub_date) : null;
      const dtStr = dt ? (
        String(dt.getMonth()+1).padStart(2,'0') + '.' +
        String(dt.getDate()).padStart(2,'0') + ' ' +
        String(dt.getHours()).padStart(2,'0') + ':' +
        String(dt.getMinutes()).padStart(2,'0')
      ) : '—';
      const isNew = dt && (now - dt.getTime()) < DAY * 3;
      const sid = a.scene_item_id || '';
      return `<div class="lp-item" data-sid="${sid}" data-idx="${i}" onclick="onListItemClick(${i})">
        <div class="lp-item-title">${a.scan_title || '—'}</div>
        <div class="lp-item-meta">
          <span class="lp-item-date">${dtStr}</span>
          ${isNew ? '<span class="lp-item-new">NEW</span>' : ''}
        </div>
      </div>`;
    }).join('');
  }

  window.onListItemClick = async function(idx) {
    const feat = _allFeatures[idx];
    if (!feat) return;
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

  window.filterList = function(val) {
    const kw = val.trim().toLowerCase();
    if (!kw) { renderList(_allFeatures); return; }
    const filtered = _allFeatures.filter(f =>
      (f.attributes.scan_title || '').toLowerCase().includes(kw)
    );
    renderList(filtered);
  };

  let _lpOpen = true;
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
let _loc  = { lon: null, lat: null };

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
  if (typeof JSZip === "undefined") { alert("zip 라이브러리를 불러오지 못했습니다. 폴더를 직접 압축해 올려 주세요."); return; }
  const nameEl = document.getElementById("zipName");
  const root = (files[0].webkitRelativePath || files[0].name).split("/")[0] || "scan";
  const zip = new JSZip();
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
    xhr.onerror = () => reject(new Error("네트워크 오류로 업로드에 실패했습니다"));
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
  // 진행 중이면 팝업 자동 표시
  if (pct > 0 && pct < 100) {
    pp.style.display = "block";
    _progressPopupOpen = true;
  }
}

/* ── 완료 팝업 ── */
let _doneSceneId = null;
let _doneGlbUrl  = null;
window.closeDoneModal = function() {
  document.getElementById("doneModal").classList.remove("show");
};
window.viewDoneScene = async function() {
  closeDoneModal();
  const pointLayer = window._pointLayer, mapView = window._mapView;
  if (!pointLayer || !mapView) return;
  try {
    const q = pointLayer.createQuery();
    if (_doneSceneId)      q.where = `scene_item_id = '${_doneSceneId}'`;
    else if (_doneGlbUrl)  q.where = `glb_url = '${_doneGlbUrl}'`;
    else return;
    q.outFields      = ["*"];
    q.returnGeometry = true;
    await pointLayer.when();
    await pointLayer.refresh();
    await new Promise(r => setTimeout(r, 800));
    const fs = await pointLayer.queryFeatures(q);
    if (fs.features.length) {
      const feat = fs.features[0];
      await mapView.goTo({ target: feat.geometry, zoom: 18 }, { duration: 700 });
      openSidebar(feat.attributes);
      if (window._loadListPanel) window._loadListPanel();
    }
  } catch(e) {
    console.warn("확대 실패:", e);
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

  const fd = new FormData();
  fd.append("title", title);
  fd.append("note",  document.getElementById("mNote").value);
  fd.append("mode",  _mode);
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

    const jobId = data.job_id;
    setUploadState("processing", title, 0, STEP_PCTS[0], "처리 대기 중...");

    let pollCount = 0;
    const MAX_POLLS = 600;   // 3초 × 600 = 30분 (Stray 처리 + SLPK + 발행)

    const poll = setInterval(async () => {
      pollCount++;
      if (pollCount > MAX_POLLS) {
        clearInterval(poll);
        setUploadState("error", title, 0, 0, "시간 초과");
        return;
      }
      try {
        const sr = await fetch(`/app/3dupload/status.py?job_id=${jobId}`, { cache: "no-store" });
        const sd = await sr.json();
        const step = Math.min(sd.step || 0, LAST_STEP);
        window._lastStatusMsg = sd.message || "";
        setUploadState("processing", title, step, STEP_PCTS[step], (sd.step_name || STEP_NAMES[step]) + "...");

        if (sd.status === "done") {
          clearInterval(poll);
          window._lastStatusMsg = "";
          setUploadState("done", title, LAST_STEP, 100, "");
          _doneSceneId = sd.scene_item_id || null;
          _doneGlbUrl  = sd.glb_url || null;
          setTimeout(() => {
            const dm = document.getElementById("doneModal");
            if (dm) {
              document.getElementById("doneModalTitle").textContent = "✓ 처리 완료!";
              document.getElementById("doneModalMsg").innerHTML =
                `<strong style="color:var(--text)">${title}</strong> 스캔이 처리되어 지도에 등록되었습니다.` +
                (sd.scene_item_id ? "" : "<br><span style='color:var(--text3)'>Scene 레이어(SLPK)는 생성되지 않아 GLB 뷰어로만 볼 수 있습니다.</span>") +
                (sd.message && sd.message !== "처리 완료" ? `<br><span style='color:var(--text3)'>${sd.message}</span>` : "");
              dm.classList.add("show");
            } else {
              if (sd.scene_item_id) location.href = `/app/3dscan/?select=${sd.scene_item_id}`;
              else location.reload();
            }
          }, 1200);
        } else if (sd.status === "failed") {
          clearInterval(poll);
          setUploadState("error", title, 0, 0, sd.message || "처리 실패");
        }
      } catch(e) {}
    }, 3000);

  } catch(err) {
    setUploadState("error", title, 0, 0, err.message);
  }
}
