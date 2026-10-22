// 지도 도구 (tools.js): 내 위치, 거리·면적 재기, 오른쪽 버튼(휴대폰은 길게 누르기) 메뉴,
// 3D 분석(가시권·가시선·일조·그림자 시간·횡단면·신축 건물·측정·단면).
// ngii5000(수치지형도 1:5,000) tools.js 와 같은 구성·동작을 고양 인허가 화면 모양으로 옮김.
//   - 위치 검색은 왼쪽 주소 검색(필지 선택)이 맡으므로 지도 위 검색창은 두지 않음
//   - 오른쪽 버튼 메뉴에 '이 자리 필지 검토' 추가
// app.js 가 GY_TOOLS.init(ctx) 로 시작하고, scene3d.js 가 2D·3D 를 바꿀 때마다 GY_TOOLS.attach(view) 를 부름.
(function () {
  "use strict";
  const T = window.GY_TOOLS = {};
  const EYE = 1.6;  // 가시권·가시선 관측 눈높이(m)
  const FLOOR_M = 3;  // 신축 건물 층 높이(m), ngii5000 과 같은 기준
  const KST = 9;  // 일조·그림자 시각은 한국 시간

  let ctx = null, M = null, M3 = null, view = null;
  let busy = false;  // 그리기·측정 중에는 지도 클릭(필지 선택)을 하지 않음
  let active = null;  // 지금 켜 둔 도구 { key, end() }
  const ui = {};
  const locators = new WeakMap();  // 뷰마다 내 위치 도우미
  let simLayer = null, sims = [], simSeq = 0;

  const ICON = {
    x: '<path d="M6 6l12 12M18 6 6 18"/>',
    locate: '<circle cx="12" cy="12" r="3.2"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3"/><circle cx="12" cy="12" r="7"/>',
    distance: '<path d="M4 18 18 4"/><path d="m6.5 13.5 1.5 1.5M9.5 10.5l1.5 1.5M12.5 7.5l1.5 1.5"/><circle cx="4" cy="18" r="1.6"/><circle cx="18" cy="4" r="1.6"/>',
    area: '<path d="M5 8 11 4l8 5-2 10H7z"/><circle cx="5" cy="8" r="1.4"/><circle cx="11" cy="4" r="1.4"/><circle cx="19" cy="9" r="1.4"/><circle cx="17" cy="19" r="1.4"/><circle cx="7" cy="19" r="1.4"/>',
    cube: '<path d="m12 3 8 4.5v9L12 21l-8-4.5v-9z"/><path d="m4 7.5 8 4.5 8-4.5M12 12v9"/>',
    eye: '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/>',
    viewshed: '<path d="M12 20 4 8a11 11 0 0 1 16 0z"/><circle cx="12" cy="20" r="1.4"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2.5M12 19v2.5M2.5 12H5M19 12h2.5M5.3 5.3l1.8 1.8M16.9 16.9l1.8 1.8M5.3 18.7l1.8-1.8M16.9 7.1l1.8-1.8"/>',
    shadow: '<path d="M8 4h5v12H8z"/><path d="M13 16 20 20H9l-1-4"/>',
    profile: '<path d="M3 19h18"/><path d="m3 15 4-5 4 3 4-7 6 9"/>',
    building: '<path d="M5 21V8l6-4v17M11 21V9l8 3v9M8 10v.01M8 14v.01M15 14v.01M15 17v.01"/><path d="M3 21h18"/>',
    slice: '<path d="M4 20 20 4"/><path d="M7 4h13v13" stroke-dasharray="2 2.5"/>',
    copy: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5.5A1.5 1.5 0 0 0 14.5 4h-9A1.5 1.5 0 0 0 4 5.5v9A1.5 1.5 0 0 0 5.5 16H8"/>',
    trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
    pin: '<path d="M12 21s-6.5-5.6-6.5-11.2a6.5 6.5 0 0 1 13 0C18.5 15.4 12 21 12 21z"/><circle cx="12" cy="9.8" r="2.3"/>',
    parcel: '<path d="M4 7.5 12 4l8 3.5v9L12 20l-8-3.5z"/><path d="m9 11 2 2 4-4"/>'
  };
  const icon = (k) => '<svg class="i" viewBox="0 0 24 24" aria-hidden="true">' + ICON[k] + "</svg>";
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const is3d = () => !!(view && view.type === "3d");
  const note = (t, ms) => ctx && ctx.note && ctx.note(t, ms);

  function load(names) {  // SDK 모듈을 이름(마지막 경로)으로
    return new Promise(function (res, rej) {
      require(names, function () {
        const args = arguments, out = {};
        names.forEach(function (n, i) { out[n.split("/").pop()] = args[i]; });
        res(out);
      }, rej);
    });
  }
  function need3dTools() {
    if (!M3) M3 = load(["esri/analysis/ViewshedAnalysis", "esri/analysis/Viewshed", "esri/widgets/LineOfSight", "esri/widgets/Daylight",
      "esri/widgets/ShadowCast", "esri/widgets/ElevationProfile", "esri/widgets/Slice", "esri/widgets/Sketch/SketchViewModel"]);
    return M3;
  }

  // ---------- 버튼 말풍선: 아이콘 버튼에 마우스를 올리거나 키보드로 오면 도구 이름 (브라우저 기본 title 말풍선 대신) ----------
  // 지도 위 버튼·Esri 버튼(확대·나침반 등)에 같은 모양. 글자가 이미 보이는 버튼(예: 배경 '일반')에는 띄우지 않음
  function initTips() {
    const tip = document.createElement("div");
    tip.className = "ngii-tip";
    tip.setAttribute("role", "tooltip");
    tip.id = "ngiiTip";
    document.body.appendChild(tip);
    const SEL = "button, .esri-widget--button, [role=button]";
    let cur = null, timer = 0, warm = 0;
    function textOf(el) {
      if (el.getAttribute("title")) { el.dataset.tip = el.getAttribute("title"); el.removeAttribute("title"); }  // 기본 말풍선이 겹치지 않게
      const t = (el.dataset.tip || el.getAttribute("aria-label") || "").trim();
      const vis = (el.innerText || "").trim();
      if (!t || (vis && (t === vis || t.endsWith(vis)))) return "";
      return t;
    }
    function place(el) {
      const r = el.getBoundingClientRect(), w = tip.offsetWidth, h = tip.offsetHeight, gap = 10;
      let side = el.dataset.tipSide;
      if (!side) side = r.left < innerWidth * 0.45 && r.right + gap + w < innerWidth - 8 && r.top > 64 ? "right" :
        r.top < 150 ? "bottom" : r.left - gap - w > 8 ? "left" : "top";
      let x = side === "right" ? r.right + gap : side === "left" ? r.left - gap - w : r.left + r.width / 2 - w / 2;
      let y = side === "bottom" ? r.bottom + gap : side === "top" ? r.top - gap - h : r.top + r.height / 2 - h / 2;
      x = Math.max(8, Math.min(x, innerWidth - w - 8));
      y = Math.max(8, Math.min(y, innerHeight - h - 8));
      tip.dataset.side = side;
      tip.style.left = Math.round(x) + "px";
      tip.style.top = Math.round(y) + "px";
    }
    function show(el) {
      const t = textOf(el);
      if (!t || !document.contains(el)) return;
      tip.textContent = t;
      tip.classList.remove("on");
      place(el);
      el.setAttribute("aria-describedby", "ngiiTip");
      void tip.offsetWidth;  // 다시 나타날 때도 움직임이 처음부터
      tip.classList.add("on");
    }
    function hide() {
      clearTimeout(timer);
      if (tip.classList.contains("on")) warm = Date.now() + 500;  // 옆 버튼으로 옮기면 바로 보여 줌
      tip.classList.remove("on");
      if (cur) cur.removeAttribute("aria-describedby");
      cur = null;
    }
    document.addEventListener("pointerover", function (e) {
      if (e.pointerType === "touch") return;
      const el = e.target.closest ? e.target.closest(SEL) : null;
      if (el === cur) return;
      hide();
      if (!el || !el.closest(".map-wrap, .ctx-menu")) return;
      cur = el;
      timer = setTimeout(function () { show(el); }, Date.now() < warm ? 0 : 320);
    });
    document.addEventListener("pointerout", function (e) {
      if (cur && !(e.relatedTarget && cur.contains(e.relatedTarget))) hide();
    });
    document.addEventListener("pointerdown", hide, true);
    document.addEventListener("focusin", function (e) {
      const el = e.target.closest ? e.target.closest(SEL) : null;
      if (el && el.closest(".map-wrap, .ctx-menu") && el.matches(":focus-visible")) { hide(); cur = el; show(el); }
    });
    document.addEventListener("focusout", hide);
    window.addEventListener("scroll", hide, true);
    window.addEventListener("resize", hide);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initTips); else initTips();

  // ---------- 시작 ----------
  T.init = async function (c) {
    ctx = c;
    M = await load(["esri/Graphic", "esri/layers/GraphicsLayer", "esri/widgets/Locate/LocateViewModel", "esri/widgets/Measurement"]);
    buildTools();
    buildPanel();
    buildMenu();
    T.attach(c.view2d);
  };
  T.busy = function () { return busy; };
  T.close = function () { endTool(); };
  T.view = function () { return view; };  // 지금 뷰 (점검용)
  // 3D 패널의 바로가기(일조권 분석 등)에서 도구를 바로 엶
  T.run = function (a, opts) {
    if (!ctx) return;
    if (a === "distance" || a === "area") measure(a);
    else if (a === "list") analysisList();
    else startAnalysis(a, null, opts || {});
  };

  // 2D·3D 를 바꾸면: 지도 위 도구를 새 뷰로 옮기고, 켜 둔 도구는 끔 (2D 측정은 3D 에서, 3D 분석은 2D 에서 못 씀)
  T.attach = function (v) {
    if (!ui.tools) return;  // 아직 시작 전 (init 이 끝나면 2D 뷰에 붙음)
    endTool();
    closeMenu();
    if (view) [ui.tools, ui.panel].forEach(function (el) { view.ui.remove(el); });
    view = v;
    v.ui.add(ui.tools, { position: "top-right", index: 2 });
    v.ui.add(ui.panel, { position: "top-right", index: 9 });
    ui.tools.querySelectorAll(".only3d").forEach(function (b) { b.hidden = !is3d(); });
    ui.tools.querySelectorAll("[data-t=distance]").forEach(function (b) {
      b.dataset.tip = is3d() ? "거리·높이 재기" : "거리 재기";
      b.setAttribute("aria-label", b.dataset.tip);
    });
    if (simLayer) simLayer.visible = is3d();  // 신축 건물(시연)은 3D 에서만
    if (!v._gyTools) {
      v._gyTools = true;
      watchRightClick(v);
    }
  };

  // ---------- 지도 위 도구 버튼 ----------
  function buildTools() {
    const bar = ui.tools = document.createElement("div");
    bar.className = "map-tools esri-widget";
    bar.setAttribute("role", "toolbar");
    bar.setAttribute("aria-label", "지도 도구");
    bar.innerHTML = btn("locate", "내 위치") + btn("distance", "거리 재기") + btn("area", "면적 재기") +
      btn("analysis", "3D 분석 도구", "only3d", "cube");
    bar.querySelector("[data-t=locate]").onclick = locate;
    bar.querySelector("[data-t=distance]").onclick = function () { toggle("distance", function () { measure("distance"); }); };
    bar.querySelector("[data-t=area]").onclick = function () { toggle("area", function () { measure("area"); }); };
    bar.querySelector("[data-t=analysis]").onclick = function () { toggle("list", analysisList); };
  }
  function btn(t, label, cls, ic) {
    return '<button type="button" data-t="' + t + '" class="' + (cls || "") + '" title="' + label + '" aria-label="' + label + '" aria-pressed="false">' +
      icon(ic || t) + "</button>";
  }
  function pressed(key) {
    ui.tools.querySelectorAll("button[data-t]").forEach(function (b) {
      if (b.dataset.t !== "locate") b.setAttribute("aria-pressed", String(b.dataset.t === key || (key === "list" && b.dataset.t === "analysis")));
    });
  }
  function toggle(key, start) { if (active && active.key === key) endTool(); else start(); }

  async function locate() {
    let vm = locators.get(view);
    if (!vm) { vm = new M.LocateViewModel({ view: view, scale: 2257 }); locators.set(view, vm); }
    const b = ui.tools.querySelector("[data-t=locate]");
    b.classList.add("busy");
    try { await vm.locate(); }
    catch (e) { note("내 위치를 찾지 못했습니다. 브라우저에서 위치 권한을 허용했는지 확인해 주세요.", 6000); }
    finally { b.classList.remove("busy"); }
  }

  // ---------- 떠 있는 도구 창 ----------
  function buildPanel() {
    const p = ui.panel = document.createElement("section");
    p.className = "tool-panel esri-widget";
    p.hidden = true;
    p.setAttribute("aria-live", "polite");
    p.innerHTML = '<header><span class="tp-ico"></span><h3></h3><button type="button" class="tp-x" aria-label="도구 닫기">' + icon("x") +
      '</button></header><div class="tp-body"></div>';
    p.querySelector(".tp-x").onclick = function () { endTool(); };
  }
  function placePanel(wide) {
    if (!view) return;
    view.ui.remove(ui.panel);
    view.ui.add(ui.panel, wide ? { position: "bottom-left", index: 0 } : { position: "top-right", index: 9 });
    document.body.classList.toggle("tp-wide", !!wide);  // 넓은 창(횡단면)은 왼쪽 아래 3D 규모 패널 자리를 씀
  }
  function openPanel(title, ic, wide) {
    const p = ui.panel;
    if (p.classList.contains("wide") !== !!wide) placePanel(!!wide);
    p.querySelector("h3").textContent = title;
    p.querySelector(".tp-ico").innerHTML = icon(ic);
    p.classList.toggle("wide", !!wide);
    const body = p.querySelector(".tp-body");
    body.innerHTML = "";
    p.hidden = false;
    document.body.classList.add("tool-open");  // 3D 규모 패널은 제목만 남겨 도구 창을 가리지 않게
    return body;
  }
  function endTool() {
    if (active) {
      const a = active;
      active = null;
      try { a.end(); } catch (e) { /* 이미 정리됨 */ }
    }
    busy = false;
    document.body.classList.remove("tool-open");
    if (ui.panel) {
      ui.panel.hidden = true;
      if (ui.panel.classList.contains("wide")) { ui.panel.classList.remove("wide"); placePanel(false); }
      ui.panel.querySelector(".tp-body").innerHTML = "";
    }
    if (ui.tools) pressed(null);
  }
  function setActive(key, end) { active = { key: key, end: end }; pressed(key); }
  function hint(body, text) { body.insertAdjacentHTML("afterbegin", '<p class="tp-hint">' + text + "</p>"); }

  // ---------- 재기 (2D: 거리·면적 / 3D: 직선 거리·높이·면적) ----------
  function measure(kind) {
    endTool();
    const body = openPanel(kind === "area" ? "면적 재기" : (is3d() ? "거리·높이 재기" : "거리 재기"), kind);
    hint(body, kind === "area" ? "지도를 차례로 눌러 둘레를 그리고, 두 번 눌러 마치세요." :
      (is3d() ? "두 곳을 차례로 누르면 직선 거리와 높이 차이를 알려 드립니다." : "지도를 차례로 눌러 선을 그리고, 두 번 눌러 마치세요."));
    const host = document.createElement("div");
    body.appendChild(host);
    const w = new M.Measurement({ view: view, container: host, linearUnit: "metric", areaUnit: "metric" });
    w.activeTool = kind === "area" ? "area" : (is3d() ? "direct-line" : "distance");
    busy = true;
    setActive(kind, function () { w.clear(); w.destroy(); });
  }

  // ---------- 오른쪽 버튼 메뉴 ----------
  function buildMenu() {
    const m = ui.menu = document.createElement("div");
    m.className = "ctx-menu";
    m.setAttribute("role", "menu");
    m.hidden = true;
    document.body.appendChild(m);
    document.addEventListener("pointerdown", function (e) { if (!m.hidden && !m.contains(e.target)) closeMenu(); }, true);
    document.addEventListener("keydown", function (e) {
      if (e.key !== "Escape") return;
      if (!m.hidden) closeMenu();
      else if (active && busy) endTool();
    });
    window.addEventListener("resize", closeMenu);
  }
  function closeMenu() { if (ui.menu) ui.menu.hidden = true; }
  function watchRightClick(v) {
    let down = null;
    v.container.addEventListener("contextmenu", function (e) { e.preventDefault(); });
    v.on("pointer-down", function (e) { if (e.button === 2) down = { x: e.x, y: e.y }; });
    v.on("pointer-up", function (e) {
      if (e.button !== 2 || !down || view !== v) return;
      const moved = Math.hypot(e.x - down.x, e.y - down.y);
      down = null;
      if (moved <= 5) openMenuAt(v, e);  // 끌었으면 회전·기울이기라 메뉴를 띄우지 않음
    });
    v.on("hold", function (e) { if (view === v && e.native && e.native.pointerType === "touch") openMenuAt(v, e); });
  }
  // 3D 에서 누른 자리: 건물(경기도 LOD·매스·신축 건물)을 눌렀으면 그 지붕, 아니면 정밀 지형 높이.
  // 화면에 그린 지형은 처음엔 거칠어(주변 산 높이가 섞임) 땅에 닿은 높이를 그대로 쓰면 관측점이 공중에 뜸
  async function pickPoint(v, x, y) {
    if (v.type !== "3d") { const p = v.toMap({ x: x, y: y }); return p ? { pt: p, bare: null, top: null } : null; }
    const h = await v.hitTest({ x: x, y: y });
    const hit = h.results.filter(function (r) { return r.type === "graphic" && r.mapPoint; })[0];
    const g = h.ground && h.ground.mapPoint;
    const pt = (hit && hit.mapPoint) || g || v.toMap({ x: x, y: y });
    if (!pt) return null;
    let bare = null;
    try { bare = (await v.map.ground.queryElevation(pt.clone())).geometry.z; } catch (err) { bare = null; }
    let z = bare != null ? bare : pt.z;
    if (hit) z = hit.mapPoint.z;
    const q = pt.clone();
    q.z = z;
    return { pt: q, bare: bare, top: bare != null && z - bare > 2.5 ? z - bare : null };
  }
  async function openMenuAt(v, e) {
    let pick = null;
    try { pick = await pickPoint(v, e.x, e.y); } catch (err) { pick = null; }
    if (!pick) return;
    const pt = pick.pt;
    const lat = pt.latitude.toFixed(5), lon = pt.longitude.toFixed(5);
    const items = [["parcel", "이 자리 필지 검토", "누른 자리의 필지를 사전검토"], "-"];
    if (v.type === "3d") {
      items.push(["viewshed", "가시권 보기", "이 자리에서 보이는 범위"], ["eye", "가시선", "이 자리에서 목표까지 보이는지"],
        ["sun", "일조 보기", "날짜·시각별 해와 그림자"], ["shadow", "그림자 시간", "하루 중 그늘진 시간"],
        ["profile", "횡단면", "지형·건물 높이 단면"], ["building", "신축 건물 그려 보기", "층수로 세워 일조·그림자 확인"], "-",
        ["distance", "거리·높이 재기"], ["area", "면적 재기"], ["slice", "단면 보기", "건물 속을 잘라 보기"]);
    } else {
      items.push(["cube", "여기서 3D 분석", "3D로 바꿔 이 자리부터"], "-", ["distance", "거리 재기"], ["area", "면적 재기"]);
    }
    items.push("-", ["copy", "좌표 복사", lat + ", " + lon]);
    if (active) items.push(["trash", "켜 둔 도구 끄기"]);
    const m = ui.menu;
    m.innerHTML = '<div class="cm-h">' + icon("pin") + "<span>" + lat + ", " + lon + (pick.bare != null ? " · 지면 해발 " + Math.round(pick.bare) + " m" : "") +
      (pick.top != null ? " · 건물 위 " + Math.round(pick.top) + " m" : "") +
      "</span></div>" + items.map(function (it) {
        return it === "-" ? '<hr role="separator">' : '<button type="button" role="menuitem" data-a="' + it[0] + '">' + icon(it[0]) +
          '<span class="cm-t">' + esc(it[1]) + (it[2] ? '<span class="cm-d">' + esc(it[2]) + "</span>" : "") + "</span></button>";
      }).join("");
    m.hidden = false;
    const r = m.getBoundingClientRect(), nx = e.native ? e.native.clientX : r.left, ny = e.native ? e.native.clientY : r.top;
    m.style.left = Math.max(8, Math.min(nx, innerWidth - r.width - 8)) + "px";
    m.style.top = Math.max(8, Math.min(ny, innerHeight - r.height - 8)) + "px";
    const first = m.querySelector("button");
    if (first) first.focus({ preventScroll: true });
    m.querySelectorAll("button[data-a]").forEach(function (b) {
      b.onclick = function () { closeMenu(); runFromMenu(b.dataset.a, pt, lat + ", " + lon); };
    });
  }
  async function runFromMenu(a, pt, coord) {
    if (a === "copy") {
      try { await navigator.clipboard.writeText(coord); note("좌표를 복사했습니다: " + coord, 3000); }
      catch (e) { note("좌표: " + coord, 8000); }
      return;
    }
    if (a === "parcel") { if (ctx.select) ctx.select(pt); return; }
    if (a === "trash") { endTool(); return; }
    if (a === "distance" || a === "area") { measure(a); return; }
    if (a === "cube") {  // 2D -> 3D: 이 자리를 가운데로 3D 를 열고 분석 목록을 띄움
      await ctx.view2d.goTo({ target: pt }, { animate: false }).catch(function () {});
      await ctx.setMode("3d");
      if (is3d()) analysisList();
      return;
    }
    startAnalysis(a, pt);
  }

  // ---------- 3D 분석 ----------
  const ANALYSES = [["viewshed", "가시권 보기"], ["eye", "가시선"], ["sun", "일조 보기"], ["shadow", "그림자 시간"], ["profile", "횡단면"],
    ["building", "신축 건물 그려 보기"], ["distance", "거리·높이 재기"], ["area", "면적 재기"], ["slice", "단면 보기"]];
  function analysisList() {
    endTool();
    const body = openPanel("3D 분석", "cube");
    hint(body, "도구를 고르세요. 지도에서 <b>오른쪽 버튼</b>(휴대폰은 길게 누르기)을 누르면 그 자리에서 바로 시작합니다.");
    const grid = document.createElement("div");
    grid.className = "tp-grid";
    grid.innerHTML = ANALYSES.map(function (a) {
      return '<button type="button" data-a="' + a[0] + '">' + icon(a[0]) + "<span>" + a[1] + "</span></button>";
    }).join("");
    body.appendChild(grid);
    grid.querySelectorAll("button").forEach(function (b) {
      b.onclick = function () {
        const a = b.dataset.a;
        if (a === "distance" || a === "area") measure(a); else startAnalysis(a, null);
      };
    });
    setActive("list", function () {});
  }
  async function startAnalysis(a, pt, opts) {
    opts = opts || {};
    if (!is3d()) return;
    endTool();
    let X;
    try { X = await need3dTools(); } catch (e) { note("3D 분석 기능을 불러오지 못했습니다", 6000); return; }
    const v = view;
    const eye = function (p) { const q = p.clone(); q.z = (isFinite(p.z) ? p.z : 0) + EYE; return q; };
    if (a === "viewshed") return viewshed(X, v, pt ? eye(pt) : null);
    if (a === "eye") {
      const body = openPanel("가시선", "eye");
      hint(body, pt ? "보려는 곳을 차례로 누르세요. 보이는 구간은 초록, 가려진 구간은 빨강입니다." :
        "관측할 자리를 먼저 누르고, 보려는 곳을 차례로 누르세요. 보이는 구간은 초록, 가려진 구간은 빨강입니다.");
      const host = document.createElement("div");
      body.appendChild(host);
      const w = new X.LineOfSight({ view: v, container: host });
      if (pt) { w.viewModel.observer = eye(pt); w.viewModel.continue(); } else w.viewModel.start();
      busy = true;
      setActive("eye", function () { w.viewModel.clear(); w.destroy(); });
      return;
    }
    if (a === "sun") {
      const body = openPanel(opts.title || "일조 보기", "sun");
      hint(body, opts.hint || "날짜와 시각을 바꾸거나 ▶ 를 누르면 해의 위치와 그림자가 움직입니다.");
      const host = document.createElement("div");
      body.appendChild(host);
      const before = v.environment.lighting.clone();
      // 해 조명으로 바꾸고 그림자 켬 (기본은 오늘 지금, 3D 규모 패널의 '일조권 분석'은 동지 12월 22일)
      v.environment.lighting = { type: "sun", date: opts.date || new Date(), directShadowsEnabled: true, displayUTCOffset: KST };
      const w = new X.Daylight({ view: v, container: host, dateOrSeason: "date", visibleElements: { header: false, timezone: false } });
      w.viewModel.utcOffset = KST;  // 경도로 짐작하면 중국 시간(UTC+8)이 됨
      setActive("sun", function () { w.destroy(); v.environment.lighting = before; });
      return;
    }
    if (a === "shadow") {
      const body = openPanel(opts.title || "그림자 시간", "shadow");
      hint(body, opts.hint || "고른 날의 시간 범위 동안 그늘이 지는 시간을 색으로 보여 줍니다. 지도 위에 올리면 그 자리의 그늘 시간이 나옵니다.");
      const host = document.createElement("div");
      body.appendChild(host);
      const w = new X.ShadowCast({ view: v, container: host, visibleElements: { timezone: false } });
      w.viewModel.utcOffset = KST;
      if (opts.date) { try { w.viewModel.date = opts.date; } catch (e) { /* 날짜는 위젯에서 고름 */ } }
      setActive("shadow", function () { w.destroy(); });
      return;
    }
    if (a === "profile") {
      const body = openPanel("횡단면", "profile", true);
      hint(body, "지도를 차례로 눌러 선을 그리고, 두 번 눌러 마치세요. 선을 따라 지형 높이와 건물을 포함한 높이를 그립니다.");
      const host = document.createElement("div");
      host.className = "tp-profile";
      body.appendChild(host);
      const w = new X.ElevationProfile({ view: v, container: host, profiles: [{ type: "ground", title: "지형 높이" },
        { type: "view", title: "건물 포함 높이" }], visibleElements: { selectButton: false } });
      w.viewModel.start();
      busy = true;
      setActive("profile", function () { w.viewModel.clear && w.viewModel.clear(); w.destroy(); });
      return;
    }
    if (a === "slice") {
      const body = openPanel("단면 보기", "slice");
      hint(body, "건물이나 지형을 누르면 그 면으로 잘라 속을 보여 줍니다. 손잡이를 끌어 자르는 위치를 옮길 수 있습니다.");
      const host = document.createElement("div");
      body.appendChild(host);
      const w = new X.Slice({ view: v, container: host });
      w.viewModel.start();
      busy = true;
      setActive("slice", function () { w.viewModel.clear(); w.destroy(); });
      return;
    }
    if (a === "building") return newBuildings(X, v);
  }

  async function viewshed(X, v, obs) {
    const body = openPanel("가시권 보기", "viewshed");
    let placing = null;  // 놓는 중인 작업 (도구를 끄면 멈춤)
    const vs =new X.Viewshed({ observer: obs || undefined, farDistance: 250, heading: v.camera.heading, tilt: 90,
      horizontalFieldOfView: 120, verticalFieldOfView: 90 });
    const an = new X.ViewshedAnalysis({ viewsheds: obs ? [vs] : [] });
    v.analyses.add(an);
    setActive("viewshed", function () { if (placing) placing.abort(); v.analyses.remove(an); });
    const av = await v.whenAnalysisView(an);
    av.interactive = true;
    hint(body, "보이는 곳은 초록, 가려진 곳은 빨강입니다. 지도 위 손잡이를 끌어 방향·거리를 바꿀 수도 있습니다.");
    const rows = [["farDistance", "거리", 20, 1500, 10, "m"], ["heading", "방향", 0, 359, 1, "°"], ["horizontalFieldOfView", "좌우 시야", 10, 360, 5, "°"],
      ["verticalFieldOfView", "상하 시야", 10, 180, 5, "°"], ["tilt", "기울기", 0, 180, 1, "°"]];
    const form = document.createElement("div");
    form.className = "tp-form";
    form.innerHTML = rows.map(function (r) {
      return '<label class="tp-row"><span>' + r[1] + '</span><input type="range" data-k="' + r[0] + '" min="' + r[2] + '" max="' + r[3] + '" step="' + r[4] +
        '"><output></output></label>';
    }).join("") + '<div class="tp-btns"><button type="button" class="tp-b" data-do="place">' + icon("pin") + "다른 자리에 놓기</button>" +
      '<button type="button" class="tp-b" data-do="clear">' + icon("trash") + "지우기</button></div>";
    body.appendChild(form);
    const cur = function () { return av.selectedViewshed || an.viewsheds.getItemAt(an.viewsheds.length - 1); };
    const unitOf = {};
    rows.forEach(function (r) { unitOf[r[0]] = r[5]; });
    function sync() {
      const s = cur();
      form.querySelectorAll("input[data-k]").forEach(function (inp) {
        inp.disabled = !s;
        if (!s) return;
        inp.value = Math.round(s[inp.dataset.k]);
        inp.nextElementSibling.textContent = inp.value + unitOf[inp.dataset.k];
      });
    }
    form.querySelectorAll("input[data-k]").forEach(function (inp) {
      inp.oninput = function () {
        const s = cur();
        if (!s) return;
        s[inp.dataset.k] = Number(inp.value);
        inp.nextElementSibling.textContent = inp.value + unitOf[inp.dataset.k];
      };
    });
    // 한 개 놓기: 4.34 는 place(), 이 앱이 쓰는 4.31 은 createViewsheds()(취소할 때까지 계속 놓음)
    //   → 관측점이 생긴 뒤 다음 클릭(방향 끝)에서 멈춤. 멈춰도 놓은 가시권은 남음 (2026-10-23 확인)
    function placeOne() {
      if (typeof av.place === "function") return av.place();
      const ac = placing = new AbortController(), n0 = an.viewsheds.length;
      let added = false;
      const h = v.on("immediate-click", function () {
        setTimeout(function () {
          if (!added) added = an.viewsheds.length > n0;
          else ac.abort();
        }, 60);
      });
      return av.createViewsheds({ signal: ac.signal })
        .catch(function (e) { if (!e || e.name !== "AbortError") throw e; })
        .finally(function () { h.remove(); if (placing === ac) placing = null; });
    }
    async function place() {
      if (placing) placing.abort();
      busy = true;
      note("관측할 자리를 누른 뒤, 볼 방향의 끝을 누르세요", 6000);
      try { await placeOne(); } catch (e) { /* 취소 */ }
      busy = false;
      sync();
    }
    form.querySelector("[data-do=place]").onclick = place;
    form.querySelector("[data-do=clear]").onclick = function () { an.viewsheds.removeAll(); sync(); };
    if (obs) av.selectedViewshed = vs;
    sync();
    if (!obs) place();
    const h = setInterval(function () { if (!active || active.key !== "viewshed") clearInterval(h); else if (!busy) sync(); }, 700);  // 손잡이로 바꾼 값 따라가기
  }

  function newBuildings(X, v) {
    if (!simLayer) {
      simLayer = new M.GraphicsLayer({ title: "신축 건물(시연)", listMode: "hide", elevationInfo: { mode: "on-the-ground" } });
      ctx.map.add(simLayer);
    }
    simLayer.visible = true;
    const body = openPanel("신축 건물 그려 보기", "building");
    hint(body, "층수(또는 높이)를 정하고 [그리기]를 누른 뒤 땅에 건물 바닥을 그리세요. 두 번 눌러 마치면 그 높이로 세워집니다. " +
      "다 그린 뒤 일조 보기·그림자 시간·가시권으로 확인해 보세요.");
    const box = document.createElement("div");
    box.className = "tp-form";
    box.innerHTML = '<div class="tp-seg" role="group" aria-label="높이 정하는 방법"><button type="button" data-u="floor" aria-pressed="true">층수</button>' +
      '<button type="button" data-u="m" aria-pressed="false">높이(m)</button></div>' +
      '<label class="tp-row"><span>다음 건물</span><input type="range" id="simH" min="1" max="60" step="1" value="10"><output></output></label>' +
      '<div class="tp-btns"><button type="button" class="tp-b pri" data-do="draw">' + icon("building") + "그리기</button>" +
      '<button type="button" class="tp-b" data-do="clear">' + icon("trash") + "모두 지우기</button></div>" +
      '<div class="tp-sub">그린 건물 <b class="n">0</b></div><ul class="tp-list"></ul>';
    body.appendChild(box);
    let unit = "floor";
    const rng = box.querySelector("#simH"), out = rng.nextElementSibling;
    const heightOf = function () { return unit === "floor" ? Number(rng.value) * FLOOR_M : Number(rng.value); };
    const label = function () {
      return unit === "floor" ? rng.value + "층 (" + heightOf() + "m)" : rng.value + "m (약 " + Math.max(1, Math.round(heightOf() / FLOOR_M)) + "층)";
    };
    const paintOut = function () { out.textContent = label(); };
    box.querySelectorAll("[data-u]").forEach(function (b) {
      b.onclick = function () {
        const h = heightOf();
        unit = b.dataset.u;
        box.querySelectorAll("[data-u]").forEach(function (x) { x.setAttribute("aria-pressed", String(x === b)); });
        rng.min = unit === "floor" ? 1 : 3; rng.max = unit === "floor" ? 60 : 200; rng.step = 1;
        rng.value = unit === "floor" ? Math.max(1, Math.round(h / FLOOR_M)) : h;
        paintOut();
      };
    });
    rng.oninput = paintOut;
    paintOut();
    const sym = function (h, on) {
      return { type: "polygon-3d", symbolLayers: [{ type: "extrude", size: h, material: { color: on ? [234, 88, 12, 0.92] : [251, 191, 36, 0.92] },
        edges: { type: "solid", color: [120, 53, 15, 0.85], size: 1 } }] };
    };
    const svm = new X.SketchViewModel({ view: v, layer: simLayer, polygonSymbol: sym(heightOf(), true), updateOnGraphicClick: false,
      defaultUpdateOptions: { tool: "reshape", enableZ: false } });
    function paintList() {
      box.querySelector(".n").textContent = sims.length;
      box.querySelector(".tp-list").innerHTML = sims.length ? sims.map(function (g, i) {
        return '<li><span>건물 ' + g.attributes.n + " · " + esc(g.attributes.label) + '</span><button type="button" class="tp-del" data-i="' + i +
          '" aria-label="건물 ' + g.attributes.n + ' 지우기">' + icon("trash") + "</button></li>";
      }).join("") : '<li class="none">아직 없습니다. 위에서 그려 보세요.</li>';
      box.querySelectorAll(".tp-del").forEach(function (b) {
        b.onclick = function () { const g = sims.splice(Number(b.dataset.i), 1)[0]; simLayer.remove(g); paintList(); };
      });
    }
    svm.on("create", function (e) {
      if (e.state === "complete") {
        const h = heightOf();
        e.graphic.symbol = sym(h, false);
        e.graphic.attributes = { n: ++simSeq, height: h, label: label() };
        sims.push(e.graphic);
        paintList();
        busy = false;
      } else if (e.state === "cancel") busy = false;
    });
    box.querySelector("[data-do=draw]").onclick = function () {
      svm.polygonSymbol = sym(heightOf(), true);
      busy = true;
      svm.create("polygon");
    };
    box.querySelector("[data-do=clear]").onclick = function () { svm.cancel(); sims.forEach(function (g) { simLayer.remove(g); }); sims = []; paintList(); };
    paintList();
    setActive("building", function () { svm.cancel(); svm.destroy(); });  // 그린 건물은 남겨 두어 다른 분석에 씀
  }
})();
