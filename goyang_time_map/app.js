/* Seoul021 time map. All statements come from the selected source map attributes. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const number = value => new Intl.NumberFormat('ko-KR').format(value);
  const areaLabel = value => value >= 1000000 ? `${(value / 1000000).toFixed(2)} km²` : `${number(Math.round(value))} m²`;
  const years = [2006, 2011, 2022, 2025];
  const dataCache = new Map(), pending = new Map(), groups = new Map(), summaries = new Map(), failures = new Map();
  let meta, year = 2025, selection = null, selectionToken = 0, yearToken = 0, selectedName = '', worker;
  let regionLayer, overlayLayer, labelLayer, highlightLayer, drawing = null, toastTimer;
  const map = L.map('map', { zoomControl: false, preferCanvas: true, minZoom: 13, maxZoom: 20, attributionControl: true }).setView([37.694, 126.763], 16);
  map.attributionControl.setPrefix(false);
  map.attributionControl.addAttribution('<a href="https://map.ngii.go.kr/" target="_blank" rel="noopener">국토지리정보원</a> · 서울021 | <a href="https://leafletjs.com">Leaflet</a>');
  L.control.zoom({ position: 'topright' }).addTo(map);
  for (const [name, z] of [['landPane', 310], ['waterPane', 320], ['roadsPane', 330], ['buildingsPane', 340], ['latestPane', 360], ['selectionPane', 390], ['labelsPane', 410]]) {
    map.createPane(name); map.getPane(name).style.zIndex = z;
    if (name === 'labelsPane') map.getPane(name).style.pointerEvents = 'none';
  }
  function toast(message) { clearTimeout(toastTimer); $('toast').textContent = message; $('toast').hidden = false; toastTimer = setTimeout(() => { $('toast').hidden = true; }, 4500); }
  async function fetchJSON(path) { const response = await fetch(path); if (!response.ok) throw new Error(`자료 요청 실패 (${response.status})`); return response.json(); }
  async function loadYear(value) {
    if (dataCache.has(value)) return dataCache.get(value);
    if (pending.has(value)) return pending.get(value);
    const promise = fetchJSON(`data/${value}.json`).then(collection => {
      dataCache.set(value, collection);
      if (worker) worker.postMessage({ type: 'cache', year: value, collection });
      return collection;
    }).finally(() => pending.delete(value));
    pending.set(value, promise); return promise;
  }
  function category(theme) { return theme === '건물' ? 'buildings' : theme.startsWith('도로') ? 'roads' : theme.startsWith('하천') ? 'water' : 'land'; }
  function style(feature) {
    const p = feature.properties;
    if (p.theme === '건물') return { color: '#48757f', weight: 0.8, fillColor: '#628e98', fillOpacity: 0.75 };
    if (p.theme === '도로중심선') return { color: '#ad9279', weight: 1.25, opacity: 0.8 };
    if (p.theme === '도로경계') return { color: '#a28f7b', weight: 0.7, fillColor: '#e9e2d7', fillOpacity: 0.32 };
    if (p.theme.startsWith('하천')) return { color: '#81b1c1', weight: 1, fillColor: '#b3d6de', fillOpacity: 0.65 };
    return { color: p.theme === '경지' ? '#9aa975' : '#a7b9a1', weight: 0.6, fillColor: p.land === '밭' ? '#d9d9a5' : p.land === '논' ? '#c6d4a7' : '#cfddc5', fillOpacity: p.theme === '경지' ? 0.65 : 0.25 };
  }
  function featureHTML(feature) {
    const p = feature.properties;
    const entries = [['종류', p.theme], ['용도', p.use], ['이름', p.name], ['지도 표기', p.note], ['구분', p.land], ['층수', p.floors], ['도로 폭', p.width ? `${p.width} m` : null]];
    return `<div class="popup-title">${escape(p.name || p.note || p.use || p.theme)}</div>${entries.filter(([, v]) => v !== undefined && v !== null && v !== '').map(([k, v]) => `<div class="popup-row"><b>${k}</b><span>${escape(v)}</span></div>`).join('')}<p class="popup-meta">${year}년 제작본 · ${escape(p.sourceLayer)}<br>원본 도형 ID ${escape(p.sourceRecord)}${p.qualityNote ? `<br>${escape(p.qualityNote)}` : ''}</p>`;
  }
  function inspectFeature(feature, latlng) {
    if (drawing) return;
    if (highlightLayer) map.removeLayer(highlightLayer);
    highlightLayer = L.geoJSON(feature, { pane: 'selectionPane', interactive: false, style: { color: '#ce653d', weight: 3, fillOpacity: 0.15 }, pointToLayer: (f, ll) => L.circleMarker(ll, { radius: 5 }) }).addTo(map);
    $('featureDetails').innerHTML = `<div class="section-label">선택한 지도 도형</div>${featureHTML(feature)}`;
    $('featureDetails').hidden = false;
    L.popup({ maxWidth: 280 }).setLatLng(latlng || L.geoJSON(feature).getBounds().getCenter()).setContent(featureHTML(feature)).openOn(map);
  }
  function createGroups(collection) {
    const result = {};
    for (const key of ['land', 'water', 'roads', 'buildings']) {
      result[key] = L.geoJSON(collection, {
        filter: feature => category(feature.properties.theme) === key,
        pane: `${key}Pane`, style,
        pointToLayer: (feature, latlng) => L.circleMarker(latlng, { radius: 2, ...style(feature), pane: `${key}Pane` }),
        onEachFeature(feature, layer) { layer.on('click', event => { if (!drawing) { L.DomEvent.stopPropagation(event); inspectFeature(feature, event.latlng); } }); }
      });
    }
    return result;
  }
  function updateLayers() {
    for (const [value, set] of groups) for (const [key, layer] of Object.entries(set)) {
      const visible = value === year && $(`show${key[0].toUpperCase()}${key.slice(1)}`).checked;
      if (visible && !map.hasLayer(layer)) layer.addTo(map);
      if (!visible && map.hasLayer(layer)) map.removeLayer(layer);
    }
    updateLabels();
  }
  function updateLabels() {
    if (labelLayer) map.removeLayer(labelLayer);
    if (!dataCache.has(year) || !$('showBuildings').checked || map.getZoom() < 15) return;
    const seen = new Set(); labelLayer = L.layerGroup();
    for (const feature of dataCache.get(year).features) {
      const p = feature.properties, name = p.name || p.note;
      if (p.theme !== '건물' || !name || !/역$|초교|초등학교|중학교|고등학교|제작센터|제니스신축/.test(name) || seen.has(name)) continue;
      const center = L.geoJSON(feature).getBounds().getCenter();
      if (!map.getBounds().contains(center) || seen.size >= 16) continue;
      seen.add(name);
      L.marker(center, { pane: 'labelsPane', interactive: false, icon: L.divIcon({ className: 'map-label', html: `<span>${escape(name)}</span>`, iconSize: [160, 20], iconAnchor: [80, 10] }) }).addTo(labelLayer);
    }
    labelLayer.addTo(map);
  }
  async function updateOverlay() {
    if (overlayLayer) { map.removeLayer(overlayLayer); overlayLayer = null; }
    $('overlayLatest').disabled = year === 2025;
    if (year === 2025 || !$('overlayLatest').checked) return;
    try {
      const collection = await loadYear(2025);
      if (year === 2025 || !$('overlayLatest').checked) return;
      overlayLayer = L.geoJSON(collection, { filter: f => f.properties.theme === '건물', pane: 'latestPane', interactive: false, style: { color: '#d46b3d', weight: 1.4, fill: false, opacity: 0.9 } }).addTo(map);
    } catch (_) { $('overlayLatest').checked = false; toast('2025년 겹치기 자료를 불러오지 못했습니다. 다시 선택해 주세요.'); }
  }
  async function switchYear(value) {
    const token = ++yearToken;
    $('loading').hidden = false; $('loadingText').textContent = `${value}년 지도를 불러오고 있습니다`; $('errorBox').hidden = true;
    try {
      const collection = await loadYear(value);
      if (token !== yearToken) return;
      if (!groups.has(value)) groups.set(value, createGroups(collection));
      year = value;
      if (highlightLayer) map.removeLayer(highlightLayer);
      $('featureDetails').hidden = true; map.closePopup();
      document.querySelectorAll('[data-year]').forEach(button => button.setAttribute('aria-pressed', String(Number(button.dataset.year) === year)));
      $('mapYear').innerHTML = `${year}<span>년</span>`;
      const source = meta.yearMeta[year];
      $('mapDateDetail').textContent = `촬영 ${source['촬영년도']} · 조사 ${source['조사년도']}${year === 2025 ? ' · 최신 제작본' : ''}`;
      updateLayers(); updateOverlay(); renderSummary(); renderYearCounts();
    } catch (error) {
      if (token !== yearToken) return;
      $('errorText').textContent = `${value}년 자료: ${error.message}. 인터넷 연결을 확인해 주세요.`;
      $('errorBox').hidden = false; $('retryButton').dataset.year = value;
    } finally { if (token === yearToken) $('loading').hidden = true; }
  }
  function requestAnalysis(value, token) {
    if (token !== selectionToken || !selection) return;
    if (worker) worker.postMessage({ type: 'analyze', year: value, token, selection, sheet: meta.sheetBoundary });
    else setTimeout(() => {
      if (token !== selectionToken) return;
      try { receiveResult(value, token, TimeMapAnalysis.analyze(dataCache.get(value), selection, meta.sheetBoundary)); }
      catch (error) { receiveFailure(value, token, error.message); }
    }, 0);
  }
  function receiveResult(value, token, result) {
    if (token !== selectionToken) return;
    summaries.set(value, result); failures.delete(value);
    renderYearCounts(); if (value === year) renderSummary();
  }
  function receiveFailure(value, token, message) {
    if (token !== selectionToken) return;
    failures.set(value, message); renderYearCounts(); if (value === year) renderSummary();
  }
  function setSelection(feature, name, fit = false) {
    selection = feature; selectedName = name; const token = ++selectionToken;
    summaries.clear(); failures.clear();
    if (regionLayer) map.removeLayer(regionLayer);
    if (highlightLayer) map.removeLayer(highlightLayer);
    $('featureDetails').hidden = true;
    if (feature) regionLayer = L.geoJSON(feature, { pane: 'selectionPane', interactive: false, style: { color: '#ca683e', weight: 2.5, dashArray: '7 5', fillColor: '#e9af69', fillOpacity: 0.05 } }).addTo(map);
    $('selectionName').textContent = feature ? name : '영역을 선택해 주세요';
    $('selectionArea').textContent = feature ? `선택 면적 ${areaLabel(turf.area(feature))}` : '지도 위에 사각형 또는 다각형을 그려보세요';
    $('clearSelection').disabled = !feature; $('fitSelection').disabled = !feature;
    if (fit && feature) fitRegion();
    renderSummary(); renderYearCounts();
    if (!feature) return;
    [year, ...years.filter(value => value !== year)].forEach(value => loadYear(value).then(() => requestAnalysis(value, token)).catch(error => receiveFailure(value, token, error.message)));
  }
  function fitRegion() {
    if (!selection) return;
    const mobile = window.innerWidth < 700;
    map.fitBounds(L.geoJSON(selection).getBounds(), { paddingTopLeft: [35, mobile ? 130 : 100], paddingBottomRight: [mobile ? 35 : 180, mobile ? 200 : 220], maxZoom: 17, animate: false });
  }
  function applyPreset(id) {
    cancelDrawing();
    if (id === 'full') setSelection(meta.sheetBoundary, '서울021 전체 영역', true);
    else { const preset = meta.presets.find(item => item.id === id); if (preset) setSelection(turf.bboxPolygon(preset.bbox), preset.shortName, true); }
  }
  function renderYearCounts() {
    const maximum = Math.max(1, ...[...summaries.values()].map(item => item.buildings));
    $('yearCounts').innerHTML = years.map(value => {
      const result = summaries.get(value), count = result ? number(result.buildings) : failures.has(value) ? '오류' : selection ? '…' : '—';
      return `<button class="year-bar" data-count-year="${value}" aria-pressed="${year === value}" aria-label="${value}년 건물 도형 ${count}개, 해당 연도로 이동"><b>${count}</b><i style="height:${result ? Math.max(2, result.buildings / maximum * 48) : 2}px"></i><span>${value}</span></button>`;
    }).join('');
  }
  function renderSummary() {
    $('summaryYear').textContent = year; $('yearBadge').textContent = year === 2025 ? '최신 제작본' : '과거 기록';
    const result = summaries.get(year);
    $('recordSection').setAttribute('aria-busy', String(!!selection && !result && !failures.has(year)));
    $('exportButton').disabled = !result || !result.featureIds.length;
    $('buildingCount').textContent = result ? number(result.buildings) : '—';
    $('roadCount').textContent = result ? number(result.roads) : '—';
    $('landSection').hidden = !result?.land.length;
    $('coverageNotice').hidden = true;
    if (!result) {
      $('narrative').textContent = !selection ? '선택한 영역의 당시 모습을 지도 기록으로 살펴볼 수 있습니다.' : failures.has(year) ? '이 연도의 영역 분석에 실패했습니다. 아래 다시 불러오기를 눌러 주세요.' : '선택한 영역의 기록을 분석하고 있습니다.';
      $('useList').innerHTML = failures.has(year) ? '<button id="retryAnalysis" class="small-link">영역 자료 다시 불러오기</button>' : `<span class="muted">${selection ? '계산 중' : '영역 선택 후 확인할 수 있습니다.'}</span>`;
      $('evidenceList').innerHTML = '<span class="muted">선택 영역의 지도 표기가 여기에 표시됩니다.</span>'; return;
    }
    const notices = [];
    if (result.coveredArea < 1) notices.push('서울021 도엽 바깥입니다. 주황색 영역을 지도 자료가 있는 안쪽으로 다시 선택해 주세요.');
    else if (result.coveredArea < result.selectedArea * 0.995) notices.push(`선택 면적의 ${(result.coveredArea / result.selectedArea * 100).toFixed(1)}%가 제공 범위에 포함됩니다. 그 안의 자료만 집계했습니다.`);
    if (result.errors) notices.push(`도형 계산 오류 ${result.errors}건이 있어 일부 집계가 제외되었습니다.`);
    if (notices.length) { $('coverageNotice').textContent = notices.join(' '); $('coverageNotice').hidden = false; }
    const construction = result.names.find(item => /신축|공사/.test(item.label));
    let narrative = result.coveredArea < 1 ? '이 영역에는 제공할 지도 기록이 없습니다.' : result.buildings ? `선택한 영역에 건물 도형 ${number(result.buildings)}개가 기록되어 있습니다.` : '선택한 영역에서 건물 도형을 찾지 못했습니다. 빈 곳의 실제 이용 상태를 뜻하지는 않습니다.';
    if (construction) narrative = `지도에 ‘${construction.label}’라는 공사 관련 표기가 남아 있습니다.`;
    else if (result.land.length) narrative += ` 영역 일부에는 ‘${result.land.map(item => item.label).slice(0, 2).join('·')}’으로 기록된 경지가 있습니다.`;
    else if (result.uses.length) narrative += ` 가장 많은 용도 표기는 ‘${result.uses[0].label}’입니다.`;
    $('narrative').textContent = narrative;
    $('useList').innerHTML = result.uses.length ? result.uses.slice(0, 6).map(item => `<div class="use-row"><span>${escape(item.label)}</span><div class="use-bar"><i style="width:${item.count / result.buildings * 100}%"></i></div><b>${number(item.count)}</b></div>`).join('') + (result.uses.length > 6 ? `<p class="stat-caption">그 외 ${result.uses.length - 6}개 용도는 내려받은 자료에서 확인할 수 있습니다.</p>` : '') : '<span class="muted">이 영역에 기록된 건물 도형이 없습니다.</span>';
    $('landList').innerHTML = result.land.map(item => `<span class="land-chip"><b>${escape(item.label)}</b> ${areaLabel(item.area)}</span>`).join('');
    $('evidenceList').innerHTML = result.names.length ? result.names.slice(0, 12).map(item => `<button class="evidence-item" data-feature="${item.id}"><span>${escape(item.label)}</span><small>${escape(item.use || item.theme)} ↗</small></button>`).join('') + (result.names.length > 12 ? `<p class="stat-caption">총 ${number(result.names.length)}개 표기 중 12개 표시</p>` : '') : '<span class="muted">이 영역에서 이름·주기 표기를 찾지 못했습니다.</span>';
  }
  function startDrawing(mode) {
    cancelDrawing(); map.closePopup();
    drawing = { mode, points: [], preview: L.layerGroup().addTo(map) };
    map.doubleClickZoom.disable(); map.getContainer().classList.add('draw-cursor');
    $('drawRect').setAttribute('aria-pressed', String(mode === 'rect')); $('drawPolygon').setAttribute('aria-pressed', String(mode === 'polygon'));
    $('drawHelp').hidden = false; $('finishPolygon').hidden = mode !== 'polygon'; $('finishPolygon').disabled = true;
    $('drawMessage').textContent = mode === 'rect' ? '지도의 두 모서리를 차례로 클릭하세요.' : '지도를 눌러 꼭짓점을 찍고 ‘영역 완성’을 누르세요.';
  }
  function cancelDrawing() {
    if (drawing) map.removeLayer(drawing.preview);
    drawing = null; map.doubleClickZoom.enable(); map.getContainer().classList.remove('draw-cursor');
    $('drawHelp').hidden = true; $('drawRect').setAttribute('aria-pressed', 'false'); $('drawPolygon').setAttribute('aria-pressed', 'false');
  }
  function previewDrawing(cursor) {
    if (!drawing) return;
    drawing.preview.clearLayers(); const points = drawing.points;
    const opts = { pane: 'selectionPane', interactive: false, color: '#ca683e', weight: 2, dashArray: '5 5', fillOpacity: 0.1 };
    if (drawing.mode === 'rect' && points.length && cursor) L.rectangle([points[0], cursor], opts).addTo(drawing.preview);
    if (drawing.mode === 'polygon' && points.length) L.polyline(cursor ? [...points, cursor] : points, opts).addTo(drawing.preview);
    points.forEach(point => L.circleMarker(point, { ...opts, radius: 4, dashArray: null, fillColor: '#fff', fillOpacity: 1 }).addTo(drawing.preview));
  }
  function finishDrawing() {
    if (!drawing) return;
    const points = drawing.points;
    let feature;
    if (drawing.mode === 'rect' && points.length === 2) feature = turf.bboxPolygon([Math.min(points[0].lng, points[1].lng), Math.min(points[0].lat, points[1].lat), Math.max(points[0].lng, points[1].lng), Math.max(points[0].lat, points[1].lat)]);
    else if (points.length >= 3) {
      const coordinates = points.map(point => [point.lng, point.lat]);
      feature = turf.polygon([[...coordinates, coordinates[0]]]);
      if (turf.kinks(feature).features.length) { toast('선이 교차하지 않도록 다시 그려주세요.'); return; }
    } else return;
    if (turf.area(feature) < 10) { toast('영역이 너무 작습니다. 조금 넓게 선택해 주세요.'); if (drawing.mode === 'rect') { drawing.points = []; drawing.preview.clearLayers(); } return; }
    const name = drawing.mode === 'rect' ? '직접 선택한 사각형' : '직접 선택한 다각형';
    cancelDrawing(); $('preset').selectedIndex = -1; setSelection(feature, name); toast('영역을 선택했습니다. 연도를 바꿔 비교해 보세요.');
  }
  map.on('click', event => {
    if (!drawing) return;
    const previous = drawing.points.at(-1);
    if (previous && map.distance(previous, event.latlng) < 0.3) return;
    drawing.points.push(event.latlng); previewDrawing();
    if (drawing.mode === 'rect' && drawing.points.length === 2) finishDrawing();
    else { $('finishPolygon').disabled = drawing.points.length < 3; if (drawing.mode === 'rect') $('drawMessage').textContent = '반대쪽 모서리를 클릭하세요.'; }
  });
  map.on('mousemove', event => previewDrawing(event.latlng));
  map.on('moveend zoomend', updateLabels);
  $('drawRect').onclick = () => startDrawing('rect'); $('drawPolygon').onclick = () => startDrawing('polygon');
  $('cancelDraw').onclick = cancelDrawing; $('finishPolygon').onclick = finishDrawing;
  document.addEventListener('keydown', event => { if (event.key === 'Escape' && drawing) cancelDrawing(); });
  $('preset').onchange = event => applyPreset(event.target.value);
  $('fitSelection').onclick = fitRegion;
  $('clearSelection').onclick = () => { cancelDrawing(); $('preset').selectedIndex = -1; setSelection(null, ''); };
  document.querySelectorAll('[data-year]').forEach(button => { button.onclick = () => switchYear(Number(button.dataset.year)); });
  $('yearCounts').onclick = event => { const button = event.target.closest('[data-count-year]'); if (button) switchYear(Number(button.dataset.countYear)); };
  $('evidenceList').onclick = event => {
    const button = event.target.closest('[data-feature]');
    if (!button) return;
    const feature = dataCache.get(year)?.features.find(item => item.id === Number(button.dataset.feature));
    if (feature) { const bounds = L.geoJSON(feature).getBounds(); map.fitBounds(bounds.pad(0.5), { maxZoom: 18 }); inspectFeature(feature, bounds.getCenter()); }
  };
  $('useList').onclick = event => { if (event.target.closest('#retryAnalysis')) setSelection(selection, selectedName); };
  ['showBuildings', 'showRoads', 'showLand', 'showWater'].forEach(id => { $(id).onchange = updateLayers; });
  $('overlayLatest').onchange = updateOverlay;
  $('retryButton').onclick = () => meta ? switchYear(Number($('retryButton').dataset.year) || year) : initialize();
  $('aboutButton').onclick = () => $('aboutDialog').showModal(); $('closeAbout').onclick = () => $('aboutDialog').close();
  $('aboutDialog').addEventListener('click', event => { if (event.target === $('aboutDialog')) { const r = $('aboutDialog').getBoundingClientRect(); if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) $('aboutDialog').close(); } });
  $('exportButton').onclick = () => {
    const result = summaries.get(year); if (!result || !selection) return;
    const ids = new Set(result.featureIds);
    const output = { type: 'FeatureCollection', metadata: { sheet: meta.sheet, sheetNumber: meta.sheetNumber, productionYear: year, photoYear: meta.yearMeta[year]['촬영년도'], source: meta.source, selection, note: '선택 영역 및 도엽 범위에 걸친 원본 도형 전체입니다. 경계로 잘라낸 도형이 아닙니다. WGS84 경위도.' }, features: dataCache.get(year).features.filter(feature => ids.has(feature.id)) };
    const url = URL.createObjectURL(new Blob([JSON.stringify(output)], { type: 'application/geo+json' }));
    const link = document.createElement('a'); link.href = url; link.download = `서울021_${year}_선택영역.geojson`; document.body.appendChild(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 10000);
    toast(`${year}년 도형 ${number(output.features.length)}개를 내려받습니다.`);
  };
  async function initialize() {
    $('loading').hidden = false; $('errorBox').hidden = true;
    try {
      meta = await fetchJSON('data/meta.json');
      try {
        worker = new Worker('analysis-worker.js?v=c3402f6730b0');
        worker.onmessage = ({ data }) => data.type === 'result' ? receiveResult(data.year, data.token, data.result) : receiveFailure(data.year, data.token, data.message);
        worker.onerror = () => { worker.terminate(); worker = null; for (const value of years) if (dataCache.has(value) && !summaries.has(value)) requestAnalysis(value, selectionToken); };
      } catch (_) { worker = null; }
      L.geoJSON(meta.sheetBoundary, { interactive: false, style: { color: '#6f8681', weight: 1.5, dashArray: '4 5', fill: false } }).addTo(map);
      map.setMaxBounds(L.geoJSON(meta.sheetBoundary).getBounds().pad(1.2));
      applyPreset('zenith'); await switchYear(2025);
    } catch (error) { $('loading').hidden = true; $('errorText').textContent = error.message; $('errorBox').hidden = false; }
  }
  new ResizeObserver(() => map.invalidateSize()).observe($('map'));
  initialize();
})();
