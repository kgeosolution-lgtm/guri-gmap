(function (root) {
  'use strict';
  const T = root.turf;
  const boxes = new WeakMap();
  function bbox(feature) {
    if (!boxes.has(feature)) boxes.set(feature, T.bbox(feature));
    return boxes.get(feature);
  }
  function overlaps(a, b) { return a[0] <= b[2] && a[2] >= b[0] && a[1] <= b[3] && a[3] >= b[1]; }
  function intersection(a, b) { return T.intersect(T.featureCollection([a, b])); }
  function analyze(collection, selection, sheet) {
    const selectedArea = T.area(selection);
    const region = intersection(selection, sheet);
    const result = { selectedArea, coveredArea: region ? T.area(region) : 0, buildings: 0, roads: 0, uses: [], land: [], names: [], featureIds: [], errors: 0 };
    if (!region || result.coveredArea < 1) return result;
    const extent = bbox(region), uses = new Map(), names = new Map(), land = new Map();
    for (const feature of collection.features) {
      if (!overlaps(extent, bbox(feature))) continue;
      try {
        if (!T.booleanIntersects(region, feature)) continue;
        result.featureIds.push(feature.id);
        const p = feature.properties;
        if (p.theme === '건물') {
          result.buildings++;
          const label = p.use || '용도 정보 없음';
          uses.set(label, (uses.get(label) || 0) + 1);
        }
        if (p.theme === '도로중심선') result.roads++;
        for (const value of [p.name, p.note]) {
          if (value && !names.has(value)) names.set(value, { label: value, id: feature.id, theme: p.theme, use: p.use || p.type || '' });
        }
        if (p.theme === '경지' && /Polygon/.test(feature.geometry.type)) {
          const clipped = intersection(feature, region);
          if (clipped) {
            const label = p.land || p.type || '구분 정보 없음';
            if (!land.has(label)) land.set(label, []);
            land.get(label).push(clipped);
          }
        }
      } catch (_) { result.errors++; }
    }
    result.uses = [...uses].map(([label, count]) => ({ label, count })).sort((a, b) => b.count - a.count);
    result.names = [...names.values()].sort((a, b) => Number(/신축|공사/.test(b.label)) - Number(/신축|공사/.test(a.label)) || Number(/^\d+동$/.test(a.label)) - Number(/^\d+동$/.test(b.label)) || a.label.localeCompare(b.label, 'ko'));
    for (const [label, polygons] of land) {
      try {
        const merged = polygons.length === 1 ? polygons[0] : T.union(T.featureCollection(polygons));
        const area = merged ? T.area(merged) : 0;
        if (area > 1) result.land.push({ label, area });
      } catch (_) { result.errors++; }
    }
    result.land.sort((a, b) => b.area - a.area);
    return result;
  }
  root.TimeMapAnalysis = { analyze, intersection, overlaps };
})(globalThis);
