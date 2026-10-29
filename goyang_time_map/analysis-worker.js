'use strict';
importScripts('vendor/turf.min.js', 'analysis-core.js?v=f3859fedc8fe');
const cache = new Map();
self.onmessage = ({ data }) => {
  if (data.type === 'cache') { cache.set(data.year, data.collection); return; }
  if (data.type !== 'analyze') return;
  try {
    const result = TimeMapAnalysis.analyze(cache.get(data.year), data.selection, data.sheet);
    self.postMessage({ type: 'result', year: data.year, token: data.token, result });
  } catch (error) {
    self.postMessage({ type: 'error', year: data.year, token: data.token, message: error.message });
  }
};
