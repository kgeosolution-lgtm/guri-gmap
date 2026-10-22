(function () {
  'use strict';

  const L = window.FORM_LAYOUT;
  const SVGNS = 'http://www.w3.org/2000/svg';
  const SX = L.img.w / L.img.srcW;
  const SY = L.img.h / L.img.srcH;
  const X = x => L.img.x + x * SX;   // 원본 그림 px → A4 설계 px
  const Y = y => L.img.y + y * SY;
  const STORE_KEY = 'bp-food-survey:draft:v1';
  const CHOICES = [
    { v: 'yes', label: '적합' },
    { v: 'no', label: '부적합' },
    { v: 'na', label: '해당없음' }
  ];
  // 원본 글자 높이(원본 그림 px). 글꼴 크기는 이 높이에 맞춰 계산한다.
  const GLYPH_H = { cell: 10.2, header: 10.2, title: 13.6, subtitle: 12.6 };
  const GLYPH_SX = 0.86;

  const $ = id => document.getElementById(id);
  const paper = $('paper');
  const hotspots = $('hotspots');
  const page = $('page');
  const pageWrap = $('pageWrap');
  const popover = $('popover');

  let state = load() || blank();
  let metrics = null;

  // ── 상태 저장 ───────────────────────────────────────────
  function blank() {
    return { shop: {}, items: {}, date: today(), signName: '', signature: '', savedAt: null };
  }
  function today() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }
  function load() {
    try {
      const raw = localStorage.getItem(STORE_KEY);
      return raw ? Object.assign(blank(), JSON.parse(raw)) : null;
    } catch (e) { return null; }
  }
  function save() {
    state.savedAt = new Date().toISOString();
    let ok = true;
    try { localStorage.setItem(STORE_KEY, JSON.stringify(state)); } catch (e) { ok = false; }
    const t = new Date(state.savedAt);
    $('saveState').textContent = ok
      ? `이 기기에 자동 저장됨 ${String(t.getHours()).padStart(2, '0')}:${String(t.getMinutes()).padStart(2, '0')}`
      : '이 기기에 저장할 수 없음 (제출 전까지 창을 닫지 마세요)';
  }
  function item(id) { return state.items[id] || (state.items[id] = { v: '', note: '' }); }

  // ── 종이 그리기 ─────────────────────────────────────────
  function el(name, attrs, parent) {
    const n = document.createElementNS(SVGNS, name);
    for (const k in attrs) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }

  function measureFont(weight) {
    const ctx = document.createElement('canvas').getContext('2d');
    ctx.font = `${weight} 100px "Nanum Gothic", sans-serif`;
    const m = ctx.measureText('영업준수');
    return { h: (m.actualBoundingBoxAscent + m.actualBoundingBoxDescent) / 100, asc: m.actualBoundingBoxAscent / 100, desc: m.actualBoundingBoxDescent / 100 };
  }

  // 원본에서 잰 글자 영역(box)에 같은 높이·같은 폭으로 글자를 놓는다.
  // 원본 글꼴은 나눔고딕보다 글자가 좁고 자간이 넓어서, 글자를 가로로 GLYPH_SX만큼 좁힌 뒤 남는 폭을 자간으로 채운다.
  function boxText(parent, str, box, glyphH, opts) {
    const m = metrics[opts.weight];
    const fs = (glyphH * SY) / m.h;
    const cy = Y((box[2] + box[3]) / 2);
    const t = el('text', {
      x: 0,
      y: (cy + (m.asc - m.desc) / 2 * fs).toFixed(2),
      transform: `translate(${X(box[0]).toFixed(2)} 0) scale(${GLYPH_SX} 1)`,
      'font-size': fs.toFixed(2),
      'font-weight': opts.weight,
      fill: opts.fill,
      textLength: ((X(box[1]) - X(box[0])) / GLYPH_SX).toFixed(2),
      lengthAdjust: 'spacing'
    }, parent);
    t.textContent = str;
    return t;
  }

  function drawPaper() {
    paper.textContent = '';
    const c = L.colors;
    const g = el('g', {}, paper);

    // 제목, 제목 오른쪽 가는 선, 부제, 3색 띠
    boxText(g, L.title.text, L.title.box, GLYPH_H.title, { weight: 800, fill: c.title });
    el('line', { x1: X(L.titleLine.x0), x2: X(L.titleLine.x1), y1: Y(L.titleLine.y), y2: Y(L.titleLine.y), stroke: c.titleLine, 'stroke-width': 1.4 }, g);
    boxText(g, L.subtitle.text, L.subtitle.box, GLYPH_H.subtitle, { weight: 800, fill: c.subtitle });
    for (const [x0, x1, key] of L.bar.segments) {
      el('rect', { x: X(x0), y: Y(L.bar.y0), width: X(x1) - X(x0), height: Y(L.bar.y1) - Y(L.bar.y0), fill: c[key] }, g);
    }

    // 표
    const xs = L.xLines, ys = L.yLines;
    el('rect', { x: X(xs[0]), y: Y(ys[0]), width: X(xs[5]) - X(xs[0]), height: Y(ys[1]) - Y(ys[0]), fill: c.headerFill }, g);

    const grid = el('g', { stroke: c.grid, 'stroke-width': 1.25, 'shape-rendering': 'geometricPrecision' }, g);
    for (let i = 1; i < xs.length - 1; i++) el('line', { x1: X(xs[i]), x2: X(xs[i]), y1: Y(ys[0]), y2: Y(ys[ys.length - 1]) }, grid);
    el('line', { x1: X(xs[0]), x2: X(xs[5]), y1: Y(ys[1]), y2: Y(ys[1]) }, grid);
    L.items.forEach((it, r) => {
      if (r === 0) return;
      const prev = L.items[r - 1];
      const start = prev.group !== it.group ? 0 : prev.sub !== it.sub ? 1 : 2;  // 병합 셀은 선을 건너뛴다
      el('line', { x1: X(xs[start]), x2: X(xs[5]), y1: Y(ys[r + 1]), y2: Y(ys[r + 1]) }, grid);
    });
    el('rect', {
      x: X(xs[0]), y: Y(ys[0]), width: X(xs[5]) - X(xs[0]), height: Y(ys[ys.length - 1]) - Y(ys[0]),
      fill: 'none', stroke: c.gridOuter, 'stroke-width': 1.6
    }, g);

    for (const h of L.header) boxText(g, h.text, h.box, GLYPH_H.header, { weight: 800, fill: c.text });
    for (const t of L.groupTexts) boxText(g, t.text, t.box, GLYPH_H.cell, { weight: 800, fill: c.text });
    for (const it of L.items) {
      if (it.subBox) boxText(g, it.sub, it.subBox, GLYPH_H.cell, { weight: 800, fill: c.text });
      boxText(g, it.text, it.box, GLYPH_H.cell, { weight: 800, fill: c.text });
    }

    // 날짜·성명 줄 (함초롬바탕 16pt)
    const f = L.footer;
    const serif = { class: 'serif', 'font-size': f.fontSize, fill: '#000' };
    const put = (str, attrs) => { el('text', Object.assign({}, serif, attrs), g).textContent = str; };
    // 연도는 인쇄된 글자처럼 그리되, 값은 render()에서 조사 날짜의 연도로 채운다
    put('', { id: 'yearText', x: f.date.year.x, y: f.date.baseline, textLength: f.date.year.w, lengthAdjust: 'spacingAndGlyphs' });
    f.date.dots.forEach(x => put('.', { x, y: f.date.baseline, 'text-anchor': 'middle' }));
    put(f.sign.name.text, { x: f.sign.name.x, y: f.sign.baseline, textLength: f.sign.name.w, lengthAdjust: 'spacingAndGlyphs' });
    put(':', { x: f.sign.colon, y: f.sign.baseline, 'text-anchor': 'middle' });
    put(f.sign.mark.text, { x: f.sign.mark.x, y: f.sign.baseline, textLength: f.sign.mark.w, lengthAdjust: 'spacingAndGlyphs' });

    el('g', { id: 'ink' }, paper);
  }

  // ── 입력 영역 ───────────────────────────────────────────
  function hot(cls, left, top, width, height, label, onTap) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = `hot ${cls}`;
    Object.assign(b.style, { left: `${left}px`, top: `${top}px`, width: `${width}px`, height: `${height}px` });
    b.setAttribute('aria-label', label);
    if (onTap) b.addEventListener('click', e => { e.stopPropagation(); onTap(b); });
    hotspots.appendChild(b);
    return b;
  }

  const hotRefs = {};
  function buildHotspots() {
    const xs = L.xLines, ys = L.yLines;
    L.items.forEach((it, r) => {
      const top = Y(ys[r + 1]), h = Y(ys[r + 2]) - top;
      hotRefs[it.id] = {
        check: hot('hot--check', X(xs[3]), top, X(xs[4]) - X(xs[3]), h, `${it.text} 확인 (두 번 누르면 적합)`, null),
        note: hot('hot--note', X(xs[4]), top, X(xs[5]) - X(xs[4]), h, `${it.text} 비고`, () => openNote(it))
      };
      bindCheck(it, hotRefs[it.id].check);
    });
    const f = L.footer;
    hot('hot--date', 360, f.date.baseline - 34, 190, 46, '조사 날짜', openDate);
    hot('hot--name', 470, f.sign.baseline - 38, 170, 52, '성명', openName);
    hot('hot--sign', 640, f.sign.baseline - 48, 90, 66, '서명', openSign);
  }

  function markSvg(v) {
    if (v === 'yes') return '<svg class="mark mark--yes" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5"/></svg>';
    if (v === 'no') return '<svg class="mark mark--no" viewBox="0 0 24 24"><path d="M5 5 19 19M19 5 5 19"/></svg>';
    if (v === 'na') return '<svg class="mark mark--na" viewBox="0 0 24 24"><path d="M5 12h14"/></svg>';
    return '';
  }

  function render() {
    let done = 0;
    for (const it of L.items) {
      const s = item(it.id), ref = hotRefs[it.id];
      if (s.v) done++;
      ref.check.innerHTML = markSvg(s.v);
      ref.check.classList.toggle('is-empty', !s.v);
      ref.note.textContent = '';
      if (s.note) {
        const span = document.createElement('span');
        span.className = 'note-text' + (s.note.length <= 9 ? ' is-single' : '');
        span.textContent = s.note;
        ref.note.appendChild(span);
      }
    }
    $('progress').textContent = `확인 ${done} / ${L.items.length}`;
    $('shopLabel').textContent = state.shop.name || '미입력';

    // 펜으로 적은 날짜·성명·서명
    const ink = $('ink');
    ink.textContent = '';
    const f = L.footer;
    $('yearText').textContent = (state.date || today()).slice(0, 4);
    const pen =(str, x, y, size) => { const t = el('text', { class: 'pen', x, y, 'font-size': size, 'text-anchor': 'middle' }, ink); t.textContent = str; };
    if (state.date) {
      const [, m, d] = state.date.split('-');
      pen(String(+m), (f.date.dots[0] + f.date.dots[1]) / 2, f.date.baseline + 3, 40);
      pen(String(+d), f.date.dots[1] + 24, f.date.baseline + 3, 40);
    }
    if (state.signName) pen(state.signName, 590, f.sign.baseline, 36);
    if (state.signature) {
      el('image', { href: state.signature, x: 628, y: f.sign.baseline - 50, width: 120, height: 66, preserveAspectRatio: 'xMidYMid meet' }, ink);
    }
  }

  // ── 확인 칸 손동작 ──────────────────────────────────────
  // 한 번 누르기 → 선택 팝오버, 두 번 누르기 → 적합,
  // 확인 칸을 위아래로 끌기 → 지나간 빈 칸을 적합 (이미 ✕·—인 칸은 그대로 둔다)
  const DOUBLE_TAP_MS = 280;
  const DRAG_PX = 8;
  let lastTap = { id: null, t: 0 };
  let tapTimer = null;

  // 빠르게 끌면 중간 칸을 건너뛰므로, 앞서 지난 칸부터 지금 칸까지 사이를 모두 채운다
  function fillYes(fromIdx, toIdx) {
    const [a, b] = fromIdx < toIdx ? [fromIdx, toIdx] : [toIdx, fromIdx];
    let changed = false;
    for (let i = a; i <= b; i++) {
      const s = item(L.items[i].id);
      if (!s.v) { s.v = 'yes'; changed = true; }
    }
    if (changed) render();
  }

  function bindCheck(it, btn) {
    const idx = L.items.indexOf(it);
    btn.dataset.idx = idx;
    // 키보드(Enter·Space)로 누른 경우에만 click으로 처리하고, 손가락·마우스는 아래 pointer 이벤트가 맡는다
    btn.addEventListener('click', e => { e.stopPropagation(); if (e.detail === 0) openCheck(it, btn); });
    btn.addEventListener('pointerdown', e => {
      if (e.button !== 0) return;
      e.preventDefault();
      const x0 = e.clientX, y0 = e.clientY;
      let dragging = false;
      let lastIdx = idx;
      const move = ev => {
        if (!dragging) {
          if (Math.hypot(ev.clientX - x0, ev.clientY - y0) < DRAG_PX) return;
          dragging = true;
          clearTimeout(tapTimer);
          closePopover();
          fillYes(idx, idx);
        }
        const hit = document.elementFromPoint(ev.clientX, ev.clientY);
        const cell = hit && hit.closest('.hot--check');
        if (cell) {
          const to = +cell.dataset.idx;
          fillYes(lastIdx, to);
          lastIdx = to;
        }
      };
      const up = () => {
        removeEventListener('pointermove', move);
        removeEventListener('pointerup', up);
        removeEventListener('pointercancel', up);
        if (dragging) { save(); return; }
        const now = Date.now();
        clearTimeout(tapTimer);
        if (lastTap.id === it.id && now - lastTap.t < DOUBLE_TAP_MS) {
          lastTap = { id: null, t: 0 };
          closePopover();
          item(it.id).v = 'yes';
          save(); render();
        } else {
          lastTap = { id: it.id, t: now };
          tapTimer = setTimeout(() => openCheck(it, btn), DOUBLE_TAP_MS);
        }
      };
      addEventListener('pointermove', move);
      addEventListener('pointerup', up);
      addEventListener('pointercancel', up);
    });
  }

  // ── 확인 선택 ───────────────────────────────────────────
  let activeHot = null;
  function closePopover() {
    popover.hidden = true;
    if (activeHot) activeHot.classList.remove('is-active');
    activeHot = null;
  }
  function openCheck(it, btn) {
    closePopover();
    activeHot = btn;
    btn.classList.add('is-active');
    const cur = item(it.id).v;
    popover.innerHTML = '';
    const add = (v, label, html, extra) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = `popover__btn ${extra || ''} ${cur && cur === v ? 'is-on' : ''}`;
      b.innerHTML = html;
      b.appendChild(document.createTextNode(label));
      b.addEventListener('click', e => {
        e.stopPropagation();
        item(it.id).v = v;
        save(); render(); closePopover();
      });
      popover.appendChild(b);
    };
    for (const ch of CHOICES) add(ch.v, ch.label, markSvg(ch.v));
    add('', '지우기', '<span style="font-size:18px;line-height:22px">⌫</span>', 'popover__btn--clear');
    popover.hidden = false;

    const r = btn.getBoundingClientRect();
    const pw = popover.offsetWidth, ph = popover.offsetHeight;
    let left = r.left - pw - 8;
    if (left < 8) left = Math.min(r.right + 8, innerWidth - pw - 8);
    let top = r.top + r.height / 2 - ph / 2;
    top = Math.max(60, Math.min(top, innerHeight - ph - 70));
    Object.assign(popover.style, { left: `${left}px`, top: `${top}px` });
  }
  document.addEventListener('click', e => { if (!popover.hidden && !popover.contains(e.target)) closePopover(); });
  addEventListener('scroll', closePopover, { passive: true });

  // ── 바텀시트 ────────────────────────────────────────────
  const sheet = $('sheet');
  let sheetCleanup = null;
  function openSheet(title, body, actions, onClose) {
    closePopover();
    closeSheet();
    sheetCleanup = onClose || null;
    $('sheetTitle').textContent = title;
    const sb = $('sheetBody'), sa = $('sheetActions');
    sb.innerHTML = ''; sa.innerHTML = '';
    sb.appendChild(body);
    for (const a of actions) {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = `btn ${a.cls || ''}`;
      b.textContent = a.label;
      b.addEventListener('click', () => { if (a.onClick() !== false) closeSheet(); });
      sa.appendChild(b);
    }
    sheet.hidden = false;
    const first = sb.querySelector('input, textarea');
    if (first) setTimeout(() => first.focus(), 50);
  }
  function closeSheet() {
    sheet.hidden = true;
    if (sheetCleanup) { const fn = sheetCleanup; sheetCleanup = null; fn(); }
  }
  sheet.addEventListener('click', e => { if (e.target.closest('[data-close]')) closeSheet(); });

  function html(str) {
    const d = document.createElement('div');
    d.innerHTML = str;
    return d;
  }
  function field(label, input) {
    const wrap = document.createElement('label');
    wrap.className = 'field';
    const s = document.createElement('span');
    s.className = 'field__label';
    s.textContent = label;
    wrap.append(s, input);
    return wrap;
  }
  function input(type, value, attrs) {
    const i = document.createElement(type === 'textarea' ? 'textarea' : 'input');
    if (type !== 'textarea') i.type = type;
    i.value = value || '';
    Object.assign(i, attrs || {});
    return i;
  }

  function openNote(it) {
    const s = item(it.id);
    const ta = input('textarea', s.note, { placeholder: '비고 내용을 입력하세요' });
    const body = document.createElement('div');
    const hint = document.createElement('p');
    hint.className = 'sheet__hint';
    hint.textContent = `${it.group} › ${it.sub} › ${it.text}`;
    body.append(hint, field('비고', ta));
    openSheet('비고', body, [
      { label: '지우기', cls: 'btn--ghost', onClick: () => { s.note = ''; save(); render(); } },
      { label: '저장', cls: 'btn--primary', onClick: () => { s.note = ta.value.trim(); save(); render(); } }
    ]);
  }

  function openDate() {
    const d = input('date', state.date);
    openSheet('조사 날짜', field('날짜', d), [
      { label: '저장', cls: 'btn--primary', onClick: () => { state.date = d.value; save(); render(); } }
    ]);
  }

  function openName() {
    const n = input('text', state.signName, { placeholder: '성명', autocomplete: 'off' });
    openSheet('성명', field('성명', n), [
      { label: '저장', cls: 'btn--primary', onClick: () => { state.signName = n.value.trim(); save(); render(); } }
    ]);
  }

  function openSign() {
    const body = document.createElement('div');
    const hint = document.createElement('p');
    hint.className = 'sheet__hint';
    hint.textContent = '아래 칸에 손가락이나 펜으로 서명하세요.';
    const cv = document.createElement('canvas');
    cv.className = 'sign-pad';
    body.append(hint, cv);

    let ctx, drawing = false, dirty = false;
    const setup = () => {
      const r = cv.getBoundingClientRect(), dpr = devicePixelRatio || 1;
      cv.width = r.width * dpr; cv.height = r.height * dpr;
      ctx = cv.getContext('2d');
      ctx.scale(dpr, dpr);
      Object.assign(ctx, { lineWidth: 3.2, lineCap: 'round', lineJoin: 'round', strokeStyle: '#13285e' });
    };
    const pt = e => { const r = cv.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
    cv.addEventListener('pointerdown', e => { cv.setPointerCapture(e.pointerId); drawing = true; dirty = true; const [x, y] = pt(e); ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + 0.1, y + 0.1); ctx.stroke(); });
    cv.addEventListener('pointermove', e => { if (!drawing) return; const [x, y] = pt(e); ctx.lineTo(x, y); ctx.stroke(); });
    const end = () => { drawing = false; };
    cv.addEventListener('pointerup', end);
    cv.addEventListener('pointercancel', end);

    openSheet('서명', body, [
      { label: '다시 쓰기', cls: 'btn--ghost', onClick: () => { ctx.clearRect(0, 0, cv.width, cv.height); dirty = false; return false; } },
      { label: '서명 지우기', cls: 'btn--ghost', onClick: () => { state.signature = ''; save(); render(); } },
      { label: '저장', cls: 'btn--primary', onClick: () => { if (dirty) { state.signature = trimCanvas(cv); save(); render(); } } }
    ]);
    requestAnimationFrame(setup);
  }

  // 서명 둘레의 빈 여백을 잘라 낸다
  function trimCanvas(cv) {
    const ctx = cv.getContext('2d');
    const { width: w, height: h } = cv;
    const data = ctx.getImageData(0, 0, w, h).data;
    let x0 = w, y0 = h, x1 = 0, y1 = 0;
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      if (data[(y * w + x) * 4 + 3] > 0) { if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
    }
    if (x1 < x0) return '';
    const pad = 8, out = document.createElement('canvas');
    out.width = x1 - x0 + pad * 2; out.height = y1 - y0 + pad * 2;
    out.getContext('2d').drawImage(cv, x0 - pad, y0 - pad, out.width, out.height, 0, 0, out.width, out.height);
    return out.toDataURL('image/png');
  }

  // ── 업소 정보 (원본 양식에 없는 항목이라 종이 바깥에서 받는다) ──
  function openShop() {
    const s = state.shop;
    const f = {
      name: input('text', s.name), owner: input('text', s.owner), addr: input('text', s.addr),
      bizNo: input('text', s.bizNo), induty: input('text', s.induty), surveyor: input('text', s.surveyor)
    };
    const body = document.createElement('div');
    const row = (a, b) => { const d = document.createElement('div'); d.className = 'field-row'; d.append(a, b); return d; };
    // 위치: 부평구 포털 기본지도를 눌러 찍거나, GPS로 현재 위치를 찍는다
    const pick = document.createElement('div');
    pick.className = 'map-pick';
    const mapEl = document.createElement('div');
    mapEl.className = 'map-pick__map';
    const bar = document.createElement('div');
    bar.className = 'gps';
    const gpsBtn = document.createElement('button');
    gpsBtn.type = 'button'; gpsBtn.className = 'btn'; gpsBtn.textContent = '현재 위치로';
    const gpsStatus = document.createElement('span');
    gpsStatus.className = 'gps__status';
    bar.append(gpsBtn, gpsStatus);
    pick.append(mapEl, bar);
    // <label>로 감싸면 지도를 누를 때마다 안의 버튼이 눌리므로 div로 만든다
    const locField = document.createElement('div');
    locField.className = 'field';
    const locLabel = document.createElement('span');
    locLabel.className = 'field__label';
    locLabel.textContent = '위치';
    locField.append(locLabel, pick);

    let loc = s.lat != null ? { lat: s.lat, lon: s.lon, acc: s.acc ?? null, locSrc: s.locSrc || 'gps' } : null;
    let picker = null;
    const showLoc = () => {
      if (!loc) { gpsStatus.textContent = '지도를 눌러 업소 위치를 찍으세요'; return; }
      const how = loc.locSrc === 'map' ? '지도에서 지정' : `GPS ±${Math.round(loc.acc)}m`;
      gpsStatus.textContent = `${loc.lat.toFixed(6)}, ${loc.lon.toFixed(6)} (${how})`;
    };
    showLoc();
    gpsBtn.addEventListener('click', () => {
      if (!navigator.geolocation) { gpsStatus.textContent = '이 기기는 위치를 지원하지 않습니다'; return; }
      gpsStatus.textContent = '위치 확인 중…';
      navigator.geolocation.getCurrentPosition(
        p => {
          loc = { lat: p.coords.latitude, lon: p.coords.longitude, acc: p.coords.accuracy, locSrc: 'gps' };
          showLoc();
          if (picker) picker.set(loc, true);
        },
        err => { gpsStatus.textContent = `위치를 가져오지 못했습니다 (${err.message})`; },
        { enableHighAccuracy: true, timeout: 15000 }
      );
    });

    body.append(
      field('업소명', f.name),
      row(field('대표자', f.owner), field('영업신고번호', f.bizNo)),
      field('소재지', f.addr),
      row(field('업종', f.induty), field('조사자', f.surveyor)),
      locField
    );
    openSheet('업소 정보', body, [
      {
        label: '저장', cls: 'btn--primary', onClick: () => {
          for (const k in f) s[k] = f[k].value.trim();
          if (loc) Object.assign(s, loc);
          save(); render();
        }
      }
    ], () => { if (picker) picker.destroy(); });

    createPickMap(mapEl, loc, p => { loc = { lat: p.lat, lon: p.lon, acc: null, locSrc: 'map' }; showLoc(); })
      .then(m => { picker = m; })
      .catch(() => { mapEl.classList.add('is-error'); mapEl.textContent = '지도를 불러오지 못했습니다. 인터넷 연결을 확인하거나 「현재 위치로」를 쓰세요.'; });
  }

  // ── 위치 찍기 지도 (부평구 GIS 포털 기본지도) ────────────
  // 기본지도는 포털 설정(portals/self)의 defaultBasemap을 그대로 써서, Survey123 지도와 같은 지도가 나오게 한다.
  const PORTAL_URL = 'https://gis.icbp.go.kr/portal';
  const ARCGIS_JS = 'https://js.arcgis.com/4.31';
  const BUPYEONG_CENTER = [126.7219, 37.5070];   // 부평구청
  // Survey123 「식품 제조·가공업체 준수사항 현장조사」의 응답 레이어와, 포털 로그인(OAuth)용으로 등록한 앱
  const SURVEY_LAYER_URL = 'https://gis.icbp.go.kr/server/rest/services/Hosted/survey123_a1f4521e47ac416f80ee2e7ac1e253d3_form/FeatureServer/0';
  const OAUTH_APP_ID = 'vhdoSztYEKTNxcWW';
  let arcgisModules = null;

  function loadArcGIS() {
    if (arcgisModules) return arcgisModules;
    arcgisModules = new Promise((resolve, reject) => {
      const css = document.createElement('link');
      css.rel = 'stylesheet';
      css.href = `${ARCGIS_JS}/esri/themes/light/main.css`;
      document.head.appendChild(css);
      const js = document.createElement('script');
      js.src = `${ARCGIS_JS}/`;
      js.onload = () => window.require(
        ['esri/config', 'esri/Map', 'esri/views/MapView', 'esri/Basemap', 'esri/Graphic', 'esri/identity/OAuthInfo', 'esri/identity/IdentityManager'],
        (esriConfig, Map, MapView, Basemap, Graphic, OAuthInfo, IdentityManager) => {
          esriConfig.portalUrl = PORTAL_URL;
          // 태블릿에서 팝업이 막히지 않도록 같은 창에서 포털 로그인 화면으로 넘어갔다 돌아온다
          IdentityManager.registerOAuthInfos([new OAuthInfo({ appId: OAUTH_APP_ID, portalUrl: PORTAL_URL, popup: false, flowType: 'authorization-code' })]);
          resolve({ Map, MapView, Basemap, Graphic, IdentityManager });
        },
        reject
      );
      js.onerror = reject;
      document.head.appendChild(js);
    }).catch(err => { arcgisModules = null; throw err; });
    return arcgisModules;
  }

  let portalBasemap = null;
  function loadPortalBasemap() {
    portalBasemap = portalBasemap || fetch(`${PORTAL_URL}/sharing/rest/portals/self?f=json`)
      .then(r => r.json())
      .then(d => d.defaultBasemap)
      .catch(err => { portalBasemap = null; throw err; });
    return portalBasemap;
  }

  async function createPickMap(container, loc, onPick) {
    const [{ Map, MapView, Basemap, Graphic }, basemapJson] = await Promise.all([loadArcGIS(), loadPortalBasemap()]);
    const view = new MapView({
      container,
      map: new Map({ basemap: Basemap.fromJSON(basemapJson) }),
      center: loc ? [loc.lon, loc.lat] : BUPYEONG_CENTER,
      zoom: loc ? 18 : 15,
      ui: { components: ['zoom', 'attribution'] }
    });
    const marker = {
      type: 'simple-marker', style: 'circle', size: 16,
      color: [198, 40, 40, 0.95], outline: { color: [255, 255, 255, 1], width: 2.5 }
    };
    const set = (p, goTo) => {
      view.graphics.removeAll();
      view.graphics.add(new Graphic({ geometry: { type: 'point', longitude: p.lon, latitude: p.lat }, symbol: marker }));
      if (goTo) view.goTo({ center: [p.lon, p.lat], zoom: Math.max(view.zoom, 18) }).catch(() => {});
    };
    if (loc) set(loc, false);
    view.on('click', e => {
      const p = { lat: e.mapPoint.latitude, lon: e.mapPoint.longitude };
      set(p, false);
      onPick(p);
    });
    return { set, destroy: () => view.destroy() };
  }

  // ── 제출 (Survey123 피처레이어에 넣을 형태로 정리) ───────
  function buildFeature() {
    const s = state.shop;
    const a = {
      bsn_nm: s.name || null, rprsv_nm: s.owner || null, addr: s.addr || null, bsn_no: s.bizNo || null,
      induty: s.induty || null, srvyr_nm: s.surveyor || null,
      srvy_date: state.date ? new Date(`${state.date}T00:00:00+09:00`).getTime() : null,
      sign_nm: state.signName || null,
      nonconf_cnt: 0
    };
    for (const it of L.items) {
      const v = item(it.id);
      a[it.id] = v.v || null;
      a[`${it.id}_rmk`] = v.note || null;
      if (v.v === 'no') a.nonconf_cnt++;
    }
    return {
      attributes: a,
      geometry: s.lat != null ? { x: s.lon, y: s.lat, spatialReference: { wkid: 4326 } } : null
    };
  }

  // 포털 로그인 상태. interactive면 로그인 화면으로 넘어가고, 돌아오면 제출 창을 다시 연다.
  const RESUME_KEY = 'bp-food-survey:resume-submit';
  async function portalCredential(interactive) {
    const { IdentityManager } = await loadArcGIS();
    const sharing = `${PORTAL_URL}/sharing`;
    try {
      return await IdentityManager.checkSignInStatus(sharing);
    } catch (e) {
      if (!interactive) return null;
      try { sessionStorage.setItem(RESUME_KEY, '1'); } catch (err) { /* 돌아와서 제출 창이 자동으로 안 열릴 뿐이다 */ }
      return IdentityManager.getCredential(sharing);
    }
  }

  async function postForm(url, params) {
    const fd = new FormData();
    for (const k in params) fd.append(k, params[k]);
    fd.append('f', 'json');
    const r = await fetch(url, { method: 'POST', body: fd });
    return r.json();
  }

  // 응답 레이어에 1건 추가하고, 서명은 Survey123과 같은 키워드(signature)의 첨부로 붙인다
  async function sendToSurvey(cred) {
    const feature = buildFeature();
    const add = await postForm(`${SURVEY_LAYER_URL}/addFeatures`, { token: cred.token, features: JSON.stringify([feature]) });
    const res = add.addResults && add.addResults[0];
    if (!res || !res.success) throw new Error((res && res.error && res.error.description) || (add.error && add.error.message) || '응답 레이어에 저장하지 못했습니다');
    let signSaved = !state.signature;
    if (state.signature) {
      const blob = await (await fetch(state.signature)).blob();
      const att = await postForm(`${SURVEY_LAYER_URL}/${res.objectId}/addAttachment`, { token: cred.token, keywords: 'signature', attachment: new File([blob], 'signature.png', { type: 'image/png' }) });
      signSaved = !!(att.addAttachmentResult && att.addAttachmentResult.success);
    }
    return { objectId: res.objectId, globalId: res.globalId, signSaved, at: new Date().toISOString() };
  }

  async function openSubmit() {
    const required = [], missing = [];
    if (!state.shop.name) required.push('업소 정보 — 업소명');
    if (state.shop.lat == null) required.push('업소 정보 — 위치');
    if (!state.date) required.push('날짜');
    const empty = L.items.filter(it => !item(it.id).v).map(it => it.id.slice(1) * 1);
    if (empty.length) missing.push(`확인 미기재 ${empty.length}개 항목 (${empty.join(', ')}번)`);
    if (!state.signName) missing.push('성명');
    if (!state.signature) missing.push('서명');

    const body = document.createElement('div');
    body.className = 'summary';
    const list = (title, items, cls) => {
      const p = document.createElement('p');
      p.innerHTML = `<b class="${cls}"></b>`;
      p.firstChild.textContent = title;
      const ul = document.createElement('ul');
      for (const m of items) { const li = document.createElement('li'); li.textContent = m; ul.appendChild(li); }
      body.append(p, ul);
    };

    if (state.submitted) {
      const t = new Date(state.submitted.at);
      list('이미 제출한 조사입니다.', [
        `제출 번호 ${state.submitted.objectId} (${t.toLocaleString('ko-KR')})`,
        '고칠 내용이 있으면 Survey123의 데이터 화면에서 수정하세요.'
      ], '');
      openSheet('제출 완료', body, [
        { label: '닫기', cls: 'btn--ghost', onClick: () => {} },
        { label: '새 조사 시작', cls: 'btn--primary', onClick: () => { state = blank(); save(); render(); } }
      ]);
      return;
    }

    if (required.length) list('반드시 입력해야 제출할 수 있습니다.', required, 'warn');
    if (missing.length) list('아직 입력하지 않은 항목 (이대로도 제출할 수 있습니다)', missing, '');
    if (!required.length && !missing.length) list('모든 항목이 입력되었습니다.', [], '');

    const who = document.createElement('p');
    who.className = 'sheet__hint';
    who.style.marginTop = '14px';
    who.textContent = '포털 로그인 상태 확인 중…';
    body.appendChild(who);
    const status = document.createElement('p');
    status.className = 'sheet__hint';
    body.appendChild(status);

    let cred = null, busy = false;
    openSheet('제출', body, [
      { label: '닫기', cls: 'btn--ghost', onClick: () => {} },
      {
        label: '부평구 포털에 제출', cls: 'btn--primary', onClick: () => {
          if (busy || required.length) return false;
          busy = true;
          (async () => {
            try {
              if (!cred) { status.textContent = '포털 로그인 화면으로 이동합니다…'; cred = await portalCredential(true); }
              status.textContent = '제출 중…';
              state.submitted = await sendToSurvey(cred);
              save();
              closeSheet();
              openSubmit();
              if (!state.submitted.signSaved) alert('조사 내용은 저장됐지만 서명 이미지는 올라가지 않았습니다. Survey123 데이터 화면에서 확인해 주세요.');
            } catch (e) {
              status.innerHTML = '<b class="warn"></b>';
              status.firstChild.textContent = `제출하지 못했습니다: ${e.message || e}`;
            } finally { busy = false; }
          })();
          return false;
        }
      }
    ]);
    const submitBtn = $('sheetActions').lastChild;
    submitBtn.disabled = required.length > 0;

    try { cred = await portalCredential(false); } catch (e) { cred = null; }
    who.textContent = cred ? `로그인: ${cred.userId}` : '제출하면 부평구 포털 로그인 화면으로 넘어갔다가 돌아옵니다.';
  }

  function openReset() {
    openSheet('초기화', html('<p class="sheet__hint">입력한 업소 정보, 확인·비고, 날짜, 성명, 서명이 모두 지워집니다.</p>'), [
      { label: '취소', cls: 'btn--ghost', onClick: () => {} },
      { label: '모두 지우기', cls: 'btn--danger', onClick: () => { state = blank(); save(); render(); } }
    ]);
  }

  // ── 화면 맞춤 ───────────────────────────────────────────
  function fit() {
    const avail = document.documentElement.clientWidth - 32;
    const s = Math.min(avail / L.page.w, 1.5);
    page.style.transform = `scale(${s})`;
    pageWrap.style.width = `${L.page.w * s}px`;
    pageWrap.style.height = `${L.page.h * s}px`;
    closePopover();
  }

  // 원본과 겹쳐 비교 (?overlay=1 : 체크리스트 그림, ?overlay=page : 한글 미리보기 전체 쪽)
  function devOverlay() {
    const mode = new URLSearchParams(location.search).get('overlay');
    if (!mode) return;
    const img = document.createElement('img');
    img.className = 'dev-overlay';
    if (mode === 'page') {
      img.src = 'assets/dev/page_preview.png';
      Object.assign(img.style, { left: 0, top: 0, width: `${L.page.w}px`, height: `${L.page.h}px` });
    } else {
      img.src = 'assets/dev/form_image.png';
      Object.assign(img.style, { left: `${L.img.x}px`, top: `${L.img.y}px`, width: `${L.img.w}px`, height: `${L.img.h}px` });
    }
    page.appendChild(img);
    const panel = document.createElement('div');
    panel.className = 'dev-panel';
    panel.innerHTML = '원본 겹쳐보기 <input type="range" min="0" max="100" value="50">';
    panel.querySelector('input').addEventListener('input', e => { img.style.opacity = e.target.value / 100; });
    document.body.appendChild(panel);
  }

  async function init() {
    try {
      await Promise.all(['700 16px "Nanum Gothic"', '800 16px "Nanum Gothic"', '16px "Nanum Myeongjo"', '16px "Nanum Pen Script"']
        .map(f => document.fonts.load(f, '영업준수')));
    } catch (e) { /* 글꼴을 못 받아도 기본 글꼴로 그린다 */ }
    metrics = { 700: measureFont(700), 800: measureFont(800) };
    drawPaper();
    buildHotspots();
    devOverlay();
    fit();
    render();
    if (state.savedAt) save();
    $('btnShop').addEventListener('click', openShop);
    $('btnSubmit').addEventListener('click', openSubmit);
    $('btnReset').addEventListener('click', openReset);
    addEventListener('resize', fit);

    // 포털 로그인에서 돌아온 경우: 로그인 결과를 받아 두고 제출 창을 다시 연다
    let resume = false;
    try { resume = sessionStorage.getItem(RESUME_KEY) === '1'; sessionStorage.removeItem(RESUME_KEY); } catch (e) { /* 없음 */ }
    if (resume || /[?&]code=/.test(location.search)) {
      try { await portalCredential(false); } catch (e) { /* 제출 창에서 다시 로그인한다 */ }
      if (/[?&](code|state)=/.test(location.search)) history.replaceState(null, '', location.pathname);
      if (resume) openSubmit();
    }
  }

  init();
})();
