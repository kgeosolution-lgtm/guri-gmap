(function (root) {
  'use strict';
  const T = root.turf;
  const categories = [
    { id: 'home', label: '주거', color: '#e89952', uses: ['주거','주택'] },
    { id: 'life', label: '상업·생활', color: '#578eda', uses: ['근린생활시설','판매시설','업무시설','숙박시설','목욕탕','약국','학원','협동조합','은행','기타금융기관','여관','호텔'] },
    { id: 'industry', label: '산업·교통', color: '#9b79c9', uses: ['자동차관련시설','자동차정비수리소','운수시설','시외버스터미널','위험물저장및처리시설','주유소','세차장','창고','창고시설','공장','동물및식물관련시설','축사','변전소','방송통신시설','TV방송국','한국통신공사'] },
    { id: 'public', label: '공공·교육 등', color: '#40a99c', uses: ['학교','교육연구시설','노유자(노인및어린이)시설','장애인재활시설','부녀·사회복지관','유치원/유아원','노인복지회관','일반병원','의료시설','동사무소','우체국','경찰서','소방서','파출소/지서','구청','공회당','교회','성당','절','종교시설','운동시설','문화및집회시설','체육관','수련시설','묘지관련시설','장례시설'] },
    { id: 'other', label: '기타·미상', color: '#a4adb9', uses: [] }
  ];
  function useCategory(use) { return categories.find(item => item.uses.includes(use)) || categories.at(-1); }
  function unionArea(polygons) {
    if (!polygons.length) return 0;
    const merged = polygons.length === 1 ? polygons[0] : T.union(T.featureCollection(polygons));
    return merged ? T.area(merged) : 0;
  }
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
    const result = { selectedArea, coveredArea: region ? T.area(region) : 0, buildings: 0, roads: 0, footprintArea: 0, landArea: 0, uses: [], categories: [], land: [], names: [], featureIds: [], errors: 0 };
    if (!region || result.coveredArea < 1) return result;
    const extent = bbox(region), uses = new Map(), names = new Map(), land = new Map(), footprints = [], allLand = [], counts = new Map();
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
          const group = useCategory(p.use).id;
          counts.set(group, (counts.get(group) || 0) + 1);
          if (/Polygon/.test(feature.geometry.type)) {
            try { const clipped = intersection(feature, region); if (clipped) footprints.push(clipped); }
            catch (_) { result.footprintArea = null; result.errors++; }
          }
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
            allLand.push(clipped);
          }
        }
      } catch (_) { result.errors++; }
    }
    result.uses = [...uses].map(([label, count]) => ({ label, count })).sort((a, b) => b.count - a.count);
    result.categories = categories.map(({id, label, color}) => ({id, label, color, count: counts.get(id) || 0}));
    try { if (result.footprintArea !== null) result.footprintArea = unionArea(footprints); }
    catch (_) { result.footprintArea = null; result.errors++; }
    try { result.landArea = unionArea(allLand); }
    catch (_) { result.landArea = null; result.errors++; }
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
  root.TimeMapAnalysis = { analyze, intersection, overlaps, categories, useCategory, unionArea };
})(globalThis);
