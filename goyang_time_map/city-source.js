/* Per-sheet loading. A failed request never silently becomes an empty map. */
(function(root) {
  'use strict';
  const T=root.turf, cache=new Map(), pending=new Map();
  let catalog;
  const overlaps=(a,b)=>a[0]<=b[2]&&a[2]>=b[0]&&a[1]<=b[3]&&a[3]>=b[1];
  async function json(path) { const r=await fetch(path); if(!r.ok) throw new Error(`자료 요청 실패 (${r.status})`);return r.json(); }
  async function init() { catalog=await json('data/catalog.json');return catalog; }
  function candidates(region) {
    const b=T.bbox(region);
    return catalog.sheets.filter(s=>overlaps(s.bbox,b)&&T.booleanIntersects(region,s.boundary));
  }
  async function tile(sheet,year) {
    const key=`${sheet.number}/${year}`, status=sheet.years[year];
    if(cache.has(key)){const value=cache.get(key);cache.delete(key);cache.set(key,value);return value;}
    if(pending.has(key))return pending.get(key);
    const p=json(status.path).then(value=>{cache.set(key,value);while(cache.size>28)cache.delete(cache.keys().next().value);return value;}).finally(()=>pending.delete(key));
    pending.set(key,p);return p;
  }
  async function load(year,region) {
    const sheets=candidates(region), ready=sheets.filter(s=>s.years[year]?.ready), features=[], boundaries=[];
    // Four concurrent requests keep selection loads bounded on ordinary clients.
    for(let i=0;i<ready.length;i+=4) {
      const batch=await Promise.all(ready.slice(i,i+4).map(async s=>({s,fc:await tile(s,year)})));
      for(const {s,fc} of batch){features.push(...fc.features);boundaries.push(s.years[year].coverage);}
    }
    const coverage=boundaries.length>1?T.union(T.featureCollection(boundaries)):boundaries[0]||null;
    const mapOnlyAreas=ready.filter(s=>s.years[year].statisticsComparable===false).map(s=>s.years[year].coverage);
    return {type:'FeatureCollection',features,coverage,mapOnlyAreas,sheets:ready.map(s=>s.number),missing:sheets.filter(s=>!s.years[year]?.ready).map(s=>({number:s.number,name:s.name,status:s.years[year]?.status||'미확보'}))};
  }
  function signature(region){return candidates(region).map(s=>s.number).join(',');}
  root.CitySource={init,load,candidates,signature};
})(globalThis);
