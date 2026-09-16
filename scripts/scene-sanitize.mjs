/* 웹씬 JSON 정리 — 포털(/gmap)에 기대는 부분을 우리 사이트·지도 서버 주소로 바꾼다.
   fetch-scene.mjs(자동 스냅샷)와 수동 스냅샷 교체 때 같이 쓴다. */
const SYM_BASE = '/maps/sym/scene/'; // 배포 시 build-deploy 가 /app/guri/maps/... 로 바꾼다

export function sanitizeScene(j) {
  const log = [];
  for (const l of j.operationalLayers || []) {
    // ① 포털 아이템 스타일의 벡터타일 → 지도 서버 벡터타일
    if (
      l.layerType === 'VectorTileLayer' &&
      /sharing\/rest\/content\/items/.test(l.styleUrl || '') &&
      /Korea_Boundary/.test(l.title || '')
    ) {
      delete l.styleUrl;
      delete l.itemId;
      l.url = 'https://www.guri.go.kr/gmapsvr/rest/services/Hosted/Korea_Boundary/VectorTileServer';
      log.push('Korea_Boundary 스타일 → 지도 서버');
    }
    // ② 명소·축제 심볼: 포털 아이템 상대 경로(./resources/symbols/...) → 사이트의 PNG
    const r =
      l.layerDefinition && l.layerDefinition.drawingInfo && l.layerDefinition.drawingInfo.renderer;
    if (r && r.type === 'uniqueValue' && (l.title === '명소' || l.title === '축제')) {
      let n = 0;
      for (const u of r.uniqueValueInfos || []) {
        for (const sl of (u.symbol && u.symbol.symbolLayers) || []) {
          const href = sl.resource && sl.resource.href;
          if (
            href &&
            /\.png$/i.test(href) &&
            !/^https?:\/\//.test(href) &&
            !href.startsWith(SYM_BASE)
          ) {
            sl.resource.href = SYM_BASE + href.split('/').pop();
            n++;
          }
        }
      }
      // 이름이 렌더러에 없는 항목: 작은 초록 핀 (다른 아이콘과 같은 띄움·연결선)
      const ref =
        (r.uniqueValueInfos && r.uniqueValueInfos[0] && r.uniqueValueInfos[0].symbol) || {};
      r.defaultSymbol = {
        type: 'PointSymbol3D',
        symbolLayers: [
          {
            type: 'Icon',
            size: 18,
            anchor: 'bottom',
            resource: { href: SYM_BASE + 'pin.png' },
            occludedVisibility: { mode: 'hidden' },
          },
        ],
        verticalOffset: ref.verticalOffset || { screenLength: 20, maxWorldLength: 200 },
        callout: ref.callout || { type: 'line', color: [0, 0, 0], size: 0.75 },
      };
      r.defaultLabel = '기타';
      // 이름 레이블: 아이콘 위에, 겹치면 자동으로 숨김(static deconfliction)
      const field = l.title === '축제' ? '축제명' : '이름';
      const color = l.title === '축제' ? [138, 47, 81, 255] : [122, 59, 18, 255];
      l.layerDefinition.drawingInfo.labelingInfo = [
        {
          name: '이름',
          labelExpressionInfo: { expression: `$feature.${field}` },
          labelPlacement: 'esriServerPointLabelPlacementAboveCenter',
          deconflictionStrategy: 'static',
          symbol: {
            type: 'LabelSymbol3D',
            symbolLayers: [
              {
                type: 'Text',
                size: 11,
                font: { family: 'Pretendard GOV, Noto Sans KR, sans-serif', weight: 'bold' },
                material: { color },
                halo: { color: [255, 255, 255, 235], size: 1.4 },
              },
            ],
            verticalOffset: ref.verticalOffset || { screenLength: 20, maxWorldLength: 200 },
            callout: { type: 'line', color: [0, 0, 0, 0], size: 0.1 },
          },
        },
      ];
      l.showLabels = true;
      log.push(`${l.title} 레이블(${field}) 설정`);
      if (n) log.push(`${l.title} 심볼 ${n}개 → ${SYM_BASE}`);
    }
    // ③ 축제 팝업: 빈 필드 표 제거, 참고에서 관리용 문장 제거, 공식페이지는 실제 페이지일 때만
    if (l.title === '축제' && l.popupInfo) {
      const els = l.popupInfo.popupElements || [];
      const before = els.length;
      l.popupInfo.popupElements = els.filter(
        (e) => !(e.type === 'fields' && !(e.fieldInfos && e.fieldInfos.length)),
      );
      if (l.popupInfo.popupElements.length !== before) log.push('축제 팝업 빈 필드 표 제거');
      for (const e of l.popupInfo.popupElements) {
        if (e.type !== 'expression' || !e.expressionInfo) continue;
        let x = e.expressionInfo.expression;
        if (!/function NoteClean/.test(x)) {
          x = x.replace(
            /var html = '';/,
            `function NoteClean(v) {
  var t = C(v); if (t == '') { return '' }
  var parts = Split(t, '. ');
  var out = '';
  for (var i in parts) {
    var s = Trim(parts[i]);
    if (s == '') { continue }
    if (Find('개최장소', s) >= 0 || Find('장소 사용', s) >= 0 || Find('위치 근거', s) >= 0 || Find('위치근거', s) >= 0 || Find('데이터의 연속성', s) >= 0) { continue }
    out = IIf(out == '', s, out + '. ' + s);
  }
  return out
}
function LinkOK(v) {
  var u = C(v); if (u == '') { return false }
  if (Find('http', u) != 0) { return false }
  var rest = Replace(Replace(u, 'https://', ''), 'http://', '');
  var slash = Find('/', rest);
  if (slash == -1) { return false }
  var path = Trim(Mid(rest, slash + 1, Count(rest)));
  if (path == '' || path == 'www' || path == 'www/' || Lower(path) == 'index.do' || Lower(path) == 'index.html') { return false }
  return true
}

var html = '';`,
          );
          x = x.replace(
            "Row('ℹ️', '참고', Brief(비고, 100))",
            "Row('ℹ️', '참고', Brief(NoteClean(비고), 100))",
          );
          x = x.replace("if (C(공식페이지) != '') {", 'if (LinkOK(공식페이지)) {');
          e.expressionInfo.expression = x;
          log.push('축제 팝업 참고·공식페이지 조건 보강');
        }
      }
    }
  }
  return log;
}
