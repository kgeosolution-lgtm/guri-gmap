/* Seoul021 time map. All statements come from the selected source map attributes. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const number = value => new Intl.NumberFormat('ko-KR').format(value);
  const areaLabel = value => value >= 1000000 ? `${(value / 1000000).toFixed(2)} km²` : `${number(Math.round(value))} m²`;
  const years = [2006, 2011, 2022, 2025];
  const palette = TimeMapAnalysis.categories;
  const dataCache = new Map(), pending = new Map(), groups = new Map(), summaries = new Map(), failures = new Map();
  const compareGroups = new Map();
  let compareYear = 2006, viewMode = 'swipe', activeCategory = null, chartMetric = 'buildings', compareToken = 0, syncing = false;
  let meta, year = 2025, selection = null, selectionToken = 0, yearToken = 0, selectedName = '', worker;
  let regionLayer, overlayLayer, labelLayer, highlightLayer, drawing = null, toastTimer;
  let compareRegion, compareLabels, compareHighlight;
  const mapOptions = { zoomControl: false, preferCanvas: true, minZoom: 13, maxZoom: 20, zoomAnimation: false, markerZoomAnimation: false };
  const map = L.map('map', { ...mapOptions, attributionControl: true }).setView([37.694, 126.763], 16);
  const compareMap = L.map('compareMap', { ...mapOptions, attributionControl: false }).setView([37.694, 126.763], 16);
  map.attributionControl.setPrefix(false);
  map.attributionControl.addAttribution('<a href="https://map.ngii.go.kr/" target="_blank" rel="noopener">국토지리정보원</a> · 서울021 | <a href="https://leafletjs.com">Leaflet</a>');
  L.control.zoom({ position: 'topright' }).addTo(map);
  for (const view of [map, compareMap]) for (const [name, z] of [['boundaryPane', 300], ['dataPane', 310], ['latestPane', 360], ['selectionPane', 390], ['labelsPane', 410]]) {
    view.createPane(name); view.getPane(name).style.zIndex = z;
    if (['labelsPane','boundaryPane','latestPane','selectionPane'].includes(name)) view.getPane(name).style.pointerEvents = 'none';
  }
  function syncView(from, to) { if (syncing) return; syncing = true; to.setView(from.getCenter(), from.getZoom(), { animate: false }); syncing = false; }
  map.on('move zoom', () => syncView(map, compareMap));
  compareMap.on('move zoom', () => syncView(compareMap, map));
  const isComparing = () => viewMode === 'swipe' && year > 2006 && !drawing;
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
    if (p.theme === '건물') { const group = TimeMapAnalysis.useCategory(p.use); const dim = activeCategory && activeCategory !== group.id; return { color: dim ? '#b7c0c4' : group.color, weight: dim ? 0.3 : 1, fillColor: group.color, fillOpacity: dim ? 0.09 : 0.88, opacity: dim ? 0.25 : 1 }; }
    if (p.theme === '도로중심선') return { color: '#b1aaa0', weight: 0.9, opacity: 0.65 };
    if (p.theme === '도로경계') return { color: '#b6afa4', weight: 0.6, fillColor: '#fffdfa', fillOpacity: 0.5 };
    if (p.theme.startsWith('하천')) return { color: '#81b1c1', weight: 1, fillColor: '#b3d6de', fillOpacity: 0.65 };
    return { color: p.theme === '경지' ? '#8ab16d' : '#aabda3', weight: 0.6, fillColor: p.theme === '경지' ? '#b9d593' : '#d6e2cf', fillOpacity: p.theme === '경지' ? 0.75 : 0.2 };
  }
  function featureHTML(feature, sourceYear = year) {
    const p = feature.properties;
    const entries = [['종류', p.theme], ['용도', p.use], ['이름', p.name], ['지도 표기', p.note], ['구분', p.land], ['층수', p.floors], ['도로 폭', p.width ? `${p.width} m` : null]];
    return `<div class="popup-title">${escape(p.name || p.note || p.use || p.theme)}</div>${entries.filter(([, v]) => v !== undefined && v !== null && v !== '').map(([k, v]) => `<div class="popup-row"><b>${k}</b><span>${escape(v)}</span></div>`).join('')}<p class="popup-meta">${sourceYear}년 제작본 · ${escape(p.sourceLayer)}<br>원본 도형 ID ${escape(p.sourceRecord)}${p.qualityNote ? `<br>${escape(p.qualityNote)}` : ''}</p>`;
  }
  function inspectFeature(feature, latlng, sourceYear = year, view = map) {
    if (drawing) return;
    if (highlightLayer) map.removeLayer(highlightLayer);
    if (compareHighlight) compareMap.removeLayer(compareHighlight);
    const highlighted = L.geoJSON(feature, { pane: 'selectionPane', interactive: false, style: { color: '#223e57', weight: 3, fillOpacity: 0.15 }, pointToLayer: (f, ll) => L.circleMarker(ll, { radius: 5 }) }).addTo(view);
    if (view === map) highlightLayer = highlighted; else compareHighlight = highlighted;
    $('featureDetails').innerHTML = `<div class="section-label">선택한 지도 도형 · ${sourceYear}년</div>${featureHTML(feature, sourceYear)}`;
    $('featureDetails').hidden = false;
    L.popup({ maxWidth: 260 }).setLatLng(latlng || L.geoJSON(feature).getBounds().getCenter()).setContent(featureHTML(feature, sourceYear)).openOn(view);
  }
  function createGroups(collection, sourceYear, view = map) {
    const result = {};
    for (const key of ['land', 'water', 'roads', 'buildings']) {
      result[key] = L.geoJSON(collection, {
        filter: feature => category(feature.properties.theme) === key,
        pane: 'dataPane', style,
        pointToLayer: (feature, latlng) => L.circleMarker(latlng, { radius: 2, ...style(feature), pane: 'dataPane' }),
        onEachFeature(feature, layer) { layer.on('click', event => { if (!drawing) { L.DomEvent.stopPropagation(event); inspectFeature(feature, event.latlng, sourceYear, view); } }); }
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
    for (const [value, set] of compareGroups) for (const [key, layer] of Object.entries(set)) {
      const visible = isComparing() && value === compareYear && $(`show${key[0].toUpperCase()}${key.slice(1)}`).checked;
      if (visible && !compareMap.hasLayer(layer)) layer.addTo(compareMap);
      if (!visible && compareMap.hasLayer(layer)) compareMap.removeLayer(layer);
    }
    updateLabels();
  }
  function updateLabels() {
    if (labelLayer) map.removeLayer(labelLayer);
    if (compareLabels) compareMap.removeLayer(compareLabels);
    if (!$('showBuildings').checked || map.getZoom() < 15) return;
    function labelsFor(value, view) {
    const seen = new Set(), labels = L.layerGroup();
    for (const feature of dataCache.get(value)?.features || []) {
      const p = feature.properties, name = p.name || p.note;
      if (p.theme !== '건물' || !name || !/역$|초교|초등학교|중학교|고등학교|제작센터|제니스신축/.test(name) || seen.has(name)) continue;
      const center = L.geoJSON(feature).getBounds().getCenter();
      if (!view.getBounds().contains(center) || seen.size >= 16) continue;
      seen.add(name);
      L.marker(center, { pane: 'labelsPane', interactive: false, keyboard: false, icon: L.divIcon({ className: 'map-label', html: `<span>${escape(name)}</span>`, iconSize: [160, 20], iconAnchor: [80, 10] }) }).addTo(labels);
    }
    return labels.addTo(view);
    }
    labelLayer = labelsFor(year, map);
    if (isComparing()) compareLabels = labelsFor(compareYear, compareMap);
  }
  async function updateOverlay() {
    if (overlayLayer) { map.removeLayer(overlayLayer); overlayLayer = null; }
    $('overlayLatest').disabled = year === 2025 || isComparing();
    if (year === 2025 || isComparing() || !$('overlayLatest').checked) return;
    try {
      const collection = await loadYear(2025);
      if (year === 2025 || isComparing() || !$('overlayLatest').checked) return;
      overlayLayer = L.geoJSON(collection, { filter: f => f.properties.theme === '건물', pane: 'latestPane', interactive: false, style: { color: '#d46b3d', weight: 1.4, fill: false, opacity: 0.9 } }).addTo(map);
    } catch (_) { $('overlayLatest').checked = false; toast('2025년 겹치기 자료를 불러오지 못했습니다. 다시 선택해 주세요.'); }
  }
  async function switchYear(value) {
    const token = ++yearToken;
    $('loading').hidden = false; $('loadingText').textContent = `${value}년 지도를 불러오고 있습니다`; $('errorBox').hidden = true;
    try {
      const collection = await loadYear(value);
      if (token !== yearToken) return;
      if (!groups.has(value)) groups.set(value, createGroups(collection, value));
      year = value;
      if (highlightLayer) map.removeLayer(highlightLayer);
      if (compareHighlight) compareMap.removeLayer(compareHighlight);
      $('featureDetails').hidden = true; map.closePopup(); compareMap.closePopup();
      document.querySelectorAll('[data-year]').forEach(button => button.setAttribute('aria-pressed', String(Number(button.dataset.year) === year)));
      $('mapYear').innerHTML = `${year}<span>년</span>`;
      const source = meta.yearMeta[year];
      $('mapDateDetail').textContent = `촬영 ${source['촬영년도']} · 조사 ${source['조사년도']}${year === 2025 ? ' · 최신 제작본' : ''}`;
      if (compareYear >= year && year > 2006) compareYear = 2006;
      updateLayers(); updateComparison(); updateOverlay(); renderSummary(); renderYearCounts(); renderInsights();
      document.querySelectorAll('[data-story-year]').forEach(button => button.setAttribute('aria-pressed', String(Number(button.dataset.storyYear) === year)));
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
    renderYearCounts(); renderInsights(); if (value === year) renderSummary();
  }
  function receiveFailure(value, token, message) {
    if (token !== selectionToken) return;
    failures.set(value, message); renderYearCounts(); renderInsights(); if (value === year) renderSummary();
  }
  function setSelection(feature, name, fit = false) {
    selection = feature; selectedName = name; const token = ++selectionToken;
    summaries.clear(); failures.clear();
    if (regionLayer) map.removeLayer(regionLayer);
    if (compareRegion) compareMap.removeLayer(compareRegion);
    if (highlightLayer) map.removeLayer(highlightLayer);
    if (compareHighlight) compareMap.removeLayer(compareHighlight);
    map.closePopup(); compareMap.closePopup();
    $('featureDetails').hidden = true;
    if (feature) {
      const options = { pane: 'selectionPane', interactive: false, style: { color: '#263c5d', weight: 2, dashArray: '7 5', fillOpacity: 0 } };
      regionLayer = L.geoJSON(feature, options).addTo(map);
      compareRegion = L.geoJSON(feature, options).addTo(compareMap);
    }
    $('selectionName').textContent = feature ? name : '영역을 선택해 주세요';
    $('selectionArea').textContent = feature ? `선택 면적 ${areaLabel(turf.area(feature))}` : '지도 위에 사각형 또는 다각형을 그려보세요';
    $('clearSelection').disabled = !feature; $('fitSelection').disabled = !feature;
    if (fit && feature) fitRegion();
    const presetId = $('preset').value;
    $('storySection').hidden = presetId !== 'zenith';
    $('storyZenith').setAttribute('aria-pressed', String(presetId === 'zenith'));
    $('storySbs').setAttribute('aria-pressed', String(presetId === 'sbs'));
    renderSummary(); renderYearCounts(); renderInsights();
    if (!feature) return;
    [year, ...years.filter(value => value !== year)].forEach(value => loadYear(value).then(() => requestAnalysis(value, token)).catch(error => receiveFailure(value, token, error.message)));
  }
  function fitRegion() {
    if (!selection) return;
    const mobile = window.innerWidth < 700;
    map.fitBounds(L.geoJSON(selection).getBounds(), { paddingTopLeft: [mobile ? 25 : 65, mobile ? 110 : 100], paddingBottomRight: [mobile ? 25 : 65, mobile ? 185 : 210], maxZoom: 17, animate: false });
  }
  function applyPreset(id) {
    cancelDrawing();
    if (id === 'full') setSelection(meta.sheetBoundary, '서울021 전체 영역', true);
    else { const preset = meta.presets.find(item => item.id === id); if (preset) setSelection(turf.bboxPolygon(preset.bbox), preset.shortName, true); }
  }
  function renderYearCounts() {
    const maximum = Math.max(1, ...[...summaries.values()].map(item => item[chartMetric] || 0));
    $('yearCounts').innerHTML = years.map(value => {
      const result = summaries.get(value), amount = result?.[chartMetric];
      const count = typeof amount === 'number' ? (chartMetric === 'buildings' ? number(amount) : `${(amount/10000).toFixed(2)}`) : failures.has(value) ? '오류' : selection && !result ? '…' : '—';
      return `<button class="year-bar" data-count-year="${value}" aria-pressed="${year === value}" aria-label="${value}년 ${count}${chartMetric === 'buildings' ? '개' : '헥타르'}, 해당 연도로 이동"><b>${count}</b><i style="height:${typeof amount === 'number' ? Math.max(2, amount / maximum * 65) : 2}px;background:${chartMetric === 'landArea' ? '#8ab16d' : chartMetric === 'footprintArea' ? '#578eda' : '#e89952'}"></i><span>${value}</span></button>`;
    }).join('');
  }
  function renderSummary() {
    $('summaryYear').textContent = year; $('yearBadge').textContent = year === 2025 ? '최신 제작본' : '과거 기록';
    const result = summaries.get(year);
    $('recordSection').setAttribute('aria-busy', String(!!selection && !result && !failures.has(year)));
    $('exportButton').disabled = !result || !result.featureIds.length;
    $('buildingCount').textContent = result ? number(result.buildings) : '—';
    renderCategories(result);
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
    $('useList').innerHTML = result.uses.length ? result.uses.map(item => `<div class="use-row"><span>${escape(item.label)}</span><div class="use-bar"><i style="width:${item.count / result.buildings * 100}%;background:${TimeMapAnalysis.useCategory(item.label).color}"></i></div><b>${number(item.count)}</b></div>`).join('') : '<span class="muted">이 영역에 기록된 건물 도형이 없습니다.</span>';
    $('landList').innerHTML = result.land.map(item => `<span class="land-chip"><b>${escape(item.label)}</b> ${areaLabel(item.area)}</span>`).join('');
    $('evidenceList').innerHTML = result.names.length ? result.names.slice(0, 12).map(item => `<button class="evidence-item" data-feature="${item.id}"><span>${escape(item.label)}</span><small>${escape(item.use || item.theme)} ↗</small></button>`).join('') + (result.names.length > 12 ? `<p class="stat-caption">총 ${number(result.names.length)}개 표기 중 12개 표시</p>` : '') : '<span class="muted">이 영역에서 이름·주기 표기를 찾지 못했습니다.</span>';
  }
  function updateSwipePosition() {
    const width = $('map').clientWidth;
    const x = 22 + Math.max(0, width - 44) * Number($('swipeRange').value) / 100;
    $('compareClip').style.clipPath = `inset(0 ${Math.max(0, width - x)}px 0 0)`;
    $('swipeLine').style.left = `${x}px`;
    $('swipeRange').setAttribute('aria-valuetext', `${compareYear}년 지도 ${Math.round(x / width * 100)}%, ${year}년 지도 ${100 - Math.round(x / width * 100)}%`);
  }
  async function updateComparison() {
    const token = ++compareToken, active = isComparing();
    $('singleView').setAttribute('aria-pressed', String(!active));
    $('swipeView').setAttribute('aria-pressed', String(active));
    $('swipeView').disabled = year === 2006;
    $('swipeView').title = year === 2006 ? '2011년 이후를 고르면 이전 기록과 비교할 수 있습니다.' : '두 시점을 같은 위치에서 밀어서 비교';
    $('timelineAction').textContent = active ? '오른쪽 지도' : '지도';
    $('compareYear').value = String(compareYear);
    for (const option of $('compareYear').options) { option.disabled = Number(option.value) >= year; option.hidden = option.disabled; }
    $('compareCurrentLabel').textContent = `${year}년`;
    for (const id of ['compareClip','comparisonLabels','swipeLine','swipeRange','swipeHint']) $(id).hidden = true;
    document.querySelector('.map-date').hidden = false;
    updateOverlay();
    if (!active || !meta) { updateLayers(); return; }
    try {
      const collection = await loadYear(compareYear);
      if (token !== compareToken || !isComparing()) return;
      if (!compareGroups.has(compareYear)) compareGroups.set(compareYear, createGroups(collection, compareYear, compareMap));
      for (const id of ['compareClip','comparisonLabels','swipeLine','swipeRange','swipeHint']) $(id).hidden = false;
      document.querySelector('.map-date').hidden = true;
      syncing = true; compareMap.invalidateSize({ pan: false }); compareMap.setView(map.getCenter(), map.getZoom(), { animate: false }); syncing = false;
      updateSwipePosition(); updateLayers();
    } catch (_) {
      if (token !== compareToken) return;
      viewMode = 'single'; updateComparison(); toast('비교 지도를 불러오지 못했습니다. ‘밀어서 비교’를 다시 눌러 주세요.');
    }
  }
  function renderCategories(result) {
    $('donutCount').textContent = result ? number(result.buildings) : '—';
    let offset = 0;
    const segments = (result?.categories || []).filter(item => item.count > 0).map(item => {
      const start = offset; offset += item.count / result.buildings * 100;
      return `${item.color} ${start}% ${offset}%`;
    });
    $('useDonut').style.background = segments.length ? `conic-gradient(${segments.join(',')})` : '#e5e9eb';
    $('useDonut').setAttribute('aria-label', result ? result.categories.map(item => `${item.label} ${item.count}개`).join(', ') : '건물 용도를 계산 중입니다.');
    $('categoryList').innerHTML = palette.map(item => {
      const count = result?.categories.find(group => group.id === item.id)?.count;
      const percent = result?.buildings && typeof count === 'number' ? Math.round(count / result.buildings * 100) : 0;
      return `<button data-category="${item.id}" aria-pressed="${activeCategory === item.id}" style="--category:${item.color}"><i></i><span>${item.label}</span><b>${count === undefined ? '—' : number(count)}</b><small>${percent}%</small></button>`;
    }).join('');
    $('mapLegend').innerHTML = palette.map(item => `<button data-category="${item.id}" aria-pressed="${activeCategory === item.id}" style="--category:${item.color}"><i></i>${item.label}</button>`).join('') + '<span class="field-legend"><i></i>경지</span>';
    $('clearFilter').hidden = !activeCategory;
    $('filterHint').textContent = activeCategory ? `지도에서 ‘${palette.find(item => item.id === activeCategory).label}’ 강조 중 · 통계는 전체 용도 기준` : '용도를 누르면 지도에서 해당 색이 강조됩니다.';
  }
  function chooseCategory(id) {
    activeCategory = activeCategory === id ? null : id;
    for (const cache of [groups, compareGroups]) for (const layers of cache.values()) layers.buildings.setStyle(style);
    renderCategories(summaries.get(year));
  }
  function renderInsights() {
    const before = summaries.get(compareYear), after = summaries.get(year);
    $('insightPeriod').textContent = year > 2006 ? `${compareYear} → ${year} · ${year - compareYear}년` : '2006 · 첫 번째 기록';
    $('changeMetrics').innerHTML = '';
    if (!selection) { $('insightTitle').textContent = '어느 곳의 변화가 궁금한가요?'; $('insightText').textContent = '지도에 영역을 그리면 같은 장소의 두 시점을 비교합니다.'; return; }
    if (year === 2006) { $('insightTitle').textContent = '변화의 시작점을 살펴보세요.'; $('insightText').textContent = '2006년은 제공하는 가장 오래된 기록입니다. 아래에서 이후 연도를 골라 땅과 건물의 변화를 확인하세요.'; return; }
    if (failures.has(compareYear) || failures.has(year)) { $('insightTitle').textContent = '비교 자료를 확인하지 못했습니다.'; $('insightText').textContent = '선택 영역의 자료를 다시 불러오면 비교를 이어갈 수 있습니다.'; return; }
    if (!before || !after) { $('insightTitle').textContent = '같은 땅의 두 시점을 읽고 있습니다.'; $('insightText').textContent = '건물과 경지의 겹치는 면적을 계산합니다.'; return; }
    if (after.coveredArea < 1) { $('insightTitle').textContent = '제공 범위 바깥입니다.'; $('insightText').textContent = '서울021 도엽 안으로 영역을 다시 골라 주세요.'; return; }
    if (before.errors || after.errors || before.footprintArea === null || after.footprintArea === null || before.landArea === null || after.landArea === null) { $('insightTitle').textContent = '일부 도형은 비교에서 확인이 필요합니다.'; $('insightText').textContent = '계산 오류가 있는 상태에서는 면적 변화의 결론을 표시하지 않습니다.'; return; }
    const builtChange = after.footprintArea - before.footprintArea, landChange = after.landArea - before.landArea;
    const builtRatio = before.footprintArea > 0 ? after.footprintArea / before.footprintArea : null;
    const landPct = before.landArea > 0 ? landChange / before.landArea * 100 : null;
    let title = '같은 장소에 남은, 서로 다른 기록.';
    if (landPct !== null && landPct < -20 && builtRatio > 1.2 && before.landArea > 1000) title = '경지는 줄고, 건물의 자리는 넓어졌습니다.';
    else if (builtRatio > 1.2) title = '건물의 윤곽이 더 넓은 면적에 기록됐습니다.';
    else if (builtRatio !== null && builtRatio < 0.8) title = '기록된 건물의 윤곽 면적이 줄었습니다.';
    else if (landPct !== null && landPct > 20 && before.landArea > 1000) title = '경지로 기록된 면적이 늘었습니다.';
    else if (Math.abs(builtChange) < 10 && Math.abs(landChange) < 10) title = '두 시점의 면적 차이가 크지 않습니다.';
    $('insightTitle').textContent = title;
    const validArea = after.coveredArea < after.selectedArea * 0.995 ? '도엽 안에 포함된 면적에서 ' : '같은 선택 영역에서 ';
    $('insightText').textContent = `${validArea}건물 윤곽의 점유 비율은 ${(before.footprintArea / before.coveredArea * 100).toFixed(1)}%에서 ${(after.footprintArea / after.coveredArea * 100).toFixed(1)}%로 바뀌었습니다.`;
    const builtLabel = builtRatio === null ? `+${areaLabel(builtChange)}` : builtRatio >= 1.05 ? `${builtRatio.toFixed(1)}배` : `${Math.abs((builtRatio - 1) * 100).toFixed(1)}% ${builtRatio < 1 ? '감소' : '증가'}`;
    const landLabel = landPct === null ? (after.landArea > 0 ? `+${areaLabel(after.landArea)}` : '기록 없음') : `${Math.abs(landPct).toFixed(1)}% ${landChange < 0 ? '감소' : '증가'}`;
    const difference = after.buildings - before.buildings;
    $('changeMetrics').innerHTML = `<div class="change-card built"><span>건물 윤곽 면적</span><strong>${builtLabel}</strong><small>${(before.footprintArea / 10000).toFixed(2)} → ${(after.footprintArea / 10000).toFixed(2)} ha</small></div><div class="change-card field"><span>기록된 경지 면적</span><strong>${landLabel}</strong><small>${(before.landArea / 10000).toFixed(2)} → ${(after.landArea / 10000).toFixed(2)} ha</small></div><div class="change-detail"><span>건물 도형 <b>${difference > 0 ? '+' : ''}${number(difference)}개</b></span><small>1 ha = 10,000 m² · 신축·철거 건수 아님</small></div>`;
  }
  function startDrawing(mode) {
    cancelDrawing(); map.closePopup();
    drawing = { mode, points: [], preview: L.layerGroup().addTo(map) };
    map.doubleClickZoom.disable(); map.getContainer().classList.add('draw-cursor');
    $('drawRect').setAttribute('aria-pressed', String(mode === 'rect')); $('drawPolygon').setAttribute('aria-pressed', String(mode === 'polygon'));
    $('drawHelp').hidden = false; $('finishPolygon').hidden = mode !== 'polygon'; $('finishPolygon').disabled = true;
    $('drawMessage').textContent = mode === 'rect' ? '지도의 두 모서리를 차례로 클릭하세요.' : '지도를 눌러 꼭짓점을 찍고 ‘영역 완성’을 누르세요.';
    updateComparison();
  }
  function cancelDrawing() {
    if (drawing) map.removeLayer(drawing.preview);
    drawing = null; map.doubleClickZoom.enable(); map.getContainer().classList.remove('draw-cursor');
    $('drawHelp').hidden = true; $('drawRect').setAttribute('aria-pressed', 'false'); $('drawPolygon').setAttribute('aria-pressed', 'false');
    updateComparison();
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
  compareMap.on('moveend zoomend', updateLabels);
  $('swipeRange').min = '0'; $('swipeRange').max = '100';
  $('swipeRange').oninput = updateSwipePosition;
  $('singleView').onclick = () => { viewMode = 'single'; updateComparison(); };
  $('swipeView').onclick = () => { viewMode = 'swipe'; updateComparison(); };
  $('compareYear').onchange = event => { compareYear = Number(event.target.value); compareMap.closePopup(); if (compareHighlight) compareMap.removeLayer(compareHighlight); updateComparison(); renderInsights(); };
  for (const id of ['categoryList', 'mapLegend']) $(id).onclick = event => { const button = event.target.closest('[data-category]'); if (button) chooseCategory(button.dataset.category); };
  $('clearFilter').onclick = () => { if (activeCategory) chooseCategory(activeCategory); };
  document.querySelectorAll('[data-metric]').forEach(button => { button.onclick = () => {
    chartMetric = button.dataset.metric;
    document.querySelectorAll('[data-metric]').forEach(item => item.setAttribute('aria-pressed', String(item.dataset.metric === chartMetric)));
    $('chartCaption').textContent = chartMetric === 'buildings' ? '영역에 걸친 건물 도형 수 · 신축·철거 건수가 아닙니다.' : chartMetric === 'footprintArea' ? '단위 ha · 영역 안 건물 윤곽의 중첩을 제거한 면적. 연면적·법적 건폐율이 아닙니다.' : '단위 ha · 영역 안 경지 레이어의 중첩을 제거한 면적. 법적 지목이 아닙니다.';
    renderYearCounts();
  }; });
  $('storyZenith').onclick = () => { $('preset').value = 'zenith'; compareYear = 2006; viewMode = 'swipe'; applyPreset('zenith'); switchYear(2025); };
  $('storySbs').onclick = () => { $('preset').value = 'sbs'; compareYear = 2022; viewMode = 'swipe'; applyPreset('sbs'); switchYear(2025); };
  document.querySelectorAll('[data-story-year]').forEach(button => { button.onclick = () => { viewMode = 'single'; switchYear(Number(button.dataset.storyYear)); }; });
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
        worker = new Worker('analysis-worker.js?v=3df0415fb01f');
        worker.onmessage = ({ data }) => data.type === 'result' ? receiveResult(data.year, data.token, data.result) : receiveFailure(data.year, data.token, data.message);
        worker.onerror = () => { worker.terminate(); worker = null; for (const value of years) if (dataCache.has(value) && !summaries.has(value)) requestAnalysis(value, selectionToken); };
      } catch (_) { worker = null; }
      for (const view of [map, compareMap]) {
        L.geoJSON(meta.sheetBoundary, { pane: 'boundaryPane', interactive: false, style: { color: '#6f8681', weight: 1.5, dashArray: '4 5', fill: false } }).addTo(view);
        view.setMaxBounds(L.geoJSON(meta.sheetBoundary).getBounds().pad(1.2));
      }
      $('aboutDialog').insertAdjacentHTML('beforeend', '<h3>변화 요약과 색상 기준</h3><p>건물 윤곽 면적은 선택 영역과 도엽 안에서 건물 도형을 잘라 겹치는 부분을 합친 면적입니다. 연면적·법적 건폐율이 아닙니다. 경지 면적도 같은 방법으로 D001 레이어의 중첩을 제거합니다. 색상은 원본 용도를 5개 묶음으로 표현한 화면용 분류이며, 공공 소유나 법적 용도를 판정하지 않습니다. 연도별 원본 분류 체계의 차이가 있어 색의 변화만으로 실제 용도 전환을 단정할 수 없습니다.</p>');
      applyPreset('zenith'); await switchYear(2025);
    } catch (error) { $('loading').hidden = true; $('errorText').textContent = error.message; $('errorBox').hidden = false; }
  }
  new ResizeObserver(() => { map.invalidateSize(); if (isComparing()) { syncing = true; compareMap.invalidateSize({pan:false}); compareMap.setView(map.getCenter(), map.getZoom(), {animate:false}); syncing = false; } updateSwipePosition(); }).observe($('map'));
  initialize();
})();
