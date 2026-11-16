/* kgeoScan 끊겨도 이어 올리기 — 기기 저장 대기열 + 조각(청크) 업로드 (2026-11-16)
 *
 * 사용자: "용량 대비 인터넷 속도가 안 나오면 중간에 끊기더라 … 폰에 저장하고 온라인 괜찮은 곳에서 올리게"
 *
 * - 촬영을 이 기기 IndexedDB(kgeo_upload_queue)에 먼저 보관하고, 5 MB 조각으로 upload_chunk.py 에 올린다.
 *   끊기면 서버가 이미 받은 조각(op=status)은 건너뛰고 빠진 조각만 다시 보낸다 (1초 → 60초 늘려 가며 재시도).
 *   인터넷이 끊기면(offline) 기다렸다가 online 이 되면, 페이지를 다시 열면 저절로 이어서 올린다.
 * - 다 올라가면 upload.py 에 필드 + chunked_files={필드: upload_id | [...]} 로 마무리 → edit_key 는 localStorage['kgeo_keys'].
 * - VR 투어(capture_pano.html)는 사진·영상이 이미 그 페이지의 IndexedDB(kgeoscan_pano/shots)에 있으므로 복사하지 않고
 *   키만 적어 두었다가 올릴 때 같은 zip 을 다시 만든다 (80 MB 영상을 두 번 저장하지 않게). 그 키는 pinned() 로 알려 준다.
 * - 아이폰 사파리는 화면이 꺼지거나 다른 앱으로 가면 업로드가 멈춘다(뒤에서 올리기 불가). 화면 꺼짐 방지(Wake Lock)를 켜고,
 *   다시 열면 이어서 올라간다고 솔직하게 알려 준다.
 *
 * 쓰는 법 (페이지):
 *   var fd = KgeoUpload.form(); fd.append('title', '...'); fd.append('video_file', blob, 'a.mp4');   // FormData 와 같은 꼴
 *   fd.appendZip('pano_file', 'pano_x.zip', entries, { db: 'kgeoscan_pano', store: 'shots' });          // VR 투어 묶음
 *   KgeoUpload.enqueue({ page, kind, title, form: fd, summary, viewUrl, recent, later }).then(id => KgeoUpload.start(id, { onProgress }))
 *   KgeoUpload.renderPending(el)  → '올리지 못한 촬영 N개' (지금 올리기 · 📥 폰에 파일로 저장 · 지우기)
 */
(function () {
  'use strict';
  if (window.KgeoUpload) return;
  var MB = 1024 * 1024;
  var API = window.KGEO_UPLOAD_API || '/app/3dupload/';
  var DB_NAME = 'kgeo_upload_queue', KEYS_KEY = 'kgeo_keys', DONE_KEY = 'kgeo_upq_done';
  var INLINE_FIELDS = { sensors_file: 1, marks_file: 1 }, INLINE_MAX = 4 * MB;   // 작은 부속 JSON 은 마무리 요청에 함께
  var BACKOFF_MAX = 60000, STALL_MS = 60000, CHUNK_TIMEOUT = 240000, FINISH_TIMEOUT = 600000;
  var IS_IOS = /iP(hone|ad|od)/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  var HINT = '이 화면을 켜 둔 채 기다려 주세요. 다른 앱으로 가거나 화면이 꺼지면 멈추고, 앱을 다시 열면 받은 부분부터 이어서 올라가요.' +
    (IS_IOS ? ' (아이폰은 뒤에서 올리기가 안 돼요)' : '');
  function noop() { }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function fmtSize(b) { b = b || 0; return b < MB ? Math.max(1, Math.round(b / 1024)) + ' KB' : b >= 1024 * MB ? (b / 1024 / MB).toFixed(2) + ' GB' : b >= 100 * MB ? Math.round(b / MB) + ' MB' : (b / MB).toFixed(1) + ' MB'; }
  function fmtEta(s) { if (!isFinite(s) || s < 0) return ''; s = Math.round(s); return s < 60 ? '약 ' + s + '초 남음' : s < 3600 ? '약 ' + Math.ceil(s / 60) + '분 남음' : '약 ' + (s / 3600).toFixed(1) + '시간 남음'; }
  function fmtWhen(t) { var d = new Date(t); return (d.getMonth() + 1) + '월 ' + d.getDate() + '일 ' + ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2); }
  function lsGet(k, d) { try { var v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } }
  function lsSet(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { } }
  function err(msg, kind) { var e = new Error(msg); if (kind) e[kind] = true; return e; }
  function pausedErr() { return err('일시정지했어요. 이 폰에 보관돼 있어요 — ‘지금 올리기’를 누르면 이어서 올라가요.', 'paused'); }

  /* ── 이벤트 (페이지·위젯·다른 탭) ── */
  var LIS = { change: [], done: [], progress: [] };
  function on(type, fn) { (LIS[type] = LIS[type] || []).push(fn); return function () { LIS[type] = LIS[type].filter(function (f) { return f !== fn; }); }; }
  function emit(type) { var a = [].slice.call(arguments, 1); (LIS[type] || []).slice().forEach(function (f) { try { f.apply(null, a); } catch (e) { setTimeout(function () { throw e; }); } }); }
  var BC = null; try { BC = new BroadcastChannel('kgeo-upload'); BC.onmessage = function () { reload().then(function () { emit('change'); }); }; } catch (e) { BC = null; }
  function changed() { reload().then(function () { emit('change'); }); try { if (BC) BC.postMessage('change'); } catch (e) { } }

  /* ── IndexedDB (없거나 실패하면 메모리만 — 그 항목에 경고를 붙인다) ── */
  var DBP = null;
  function openDb() {
    if (DBP) return DBP;
    DBP = new Promise(function (res) {
      if (!window.indexedDB) return res(null);
      var rq; try { rq = indexedDB.open(DB_NAME, 1); } catch (e) { return res(null); }
      rq.onupgradeneeded = function () { var d = rq.result; if (!d.objectStoreNames.contains('items')) d.createObjectStore('items', { keyPath: 'id' }); if (!d.objectStoreNames.contains('blobs')) d.createObjectStore('blobs'); };
      rq.onsuccess = function () { var d = rq.result; d.onversionchange = function () { d.close(); DBP = null; }; res(d); };
      rq.onerror = function () { res(null); };
      rq.onblocked = function () { res(null); };
    });
    return DBP;
  }
  function tx(store, mode, fn) {
    return openDb().then(function (d) {
      if (!d) throw err('IndexedDB 를 쓸 수 없습니다', 'nodb');
      return new Promise(function (res, rej) {
        var t, r; try { t = d.transaction(store, mode); r = fn(t.objectStore(store)); } catch (e) { return rej(e); }
        t.oncomplete = function () { var v; try { v = r && r.result; } catch (e) { v = undefined; } res(v); };
        t.onerror = function () { rej(t.error || err('IndexedDB 오류')); };
        t.onabort = function () { rej(t.error || err('IndexedDB 중단')); };
      });
    });
  }
  var MEM = { items: {}, blobs: {} };      // 기기에 저장하지 못한 항목 (이 화면을 닫으면 사라짐)
  var ITEMS = [];                          // 마지막으로 읽은 목록 (동기 조회용: pinned·count)
  function reload() {
    return tx('items', 'readonly', function (s) { return s.getAll(); }).catch(function () { return []; }).then(function (l) {
      var m = Object.keys(MEM.items).map(function (k) { return MEM.items[k]; });
      ITEMS = (l || []).filter(function (it) { return !MEM.items[it.id]; }).concat(m).sort(function (a, b) { return a.created - b.created; });
      return ITEMS;
    });
  }
  function getItem(id) {
    if (MEM.items[id]) return Promise.resolve(MEM.items[id]);
    return tx('items', 'readonly', function (s) { return s.get(id); }).catch(function () { return null; });
  }
  function saveItem(it) {
    if (it.mem) { MEM.items[it.id] = it; return Promise.resolve(); }
    return tx('items', 'readwrite', function (s) { return s.put(it); }).catch(noop);
  }
  function getOwnBlob(it, key) {
    if (it.mem) return Promise.resolve(MEM.blobs[key] || null);
    return tx('blobs', 'readonly', function (s) { return s.get(key); }).catch(function () { return null; });
  }
  function ownKeys(it) {
    var k = []; it.files.forEach(function (f) { if (f.key) k.push(f.key); if (f.zip) f.zip.entries.forEach(function (e) { if (e.own) k.push(e.own); }); });
    return k;
  }
  function dropItem(it) {
    var keys = ownKeys(it);
    delete MEM.items[it.id]; keys.forEach(function (k) { delete MEM.blobs[k]; }); delete CACHE[it.id];
    if (it.mem) return Promise.resolve();
    return tx('blobs', 'readwrite', function (s) { keys.forEach(function (k) { s.delete(k); }); }).catch(noop)
      .then(function () { return tx('items', 'readwrite', function (s) { s.delete(it.id); }).catch(noop); });
  }

  /* ── 다른 페이지 IndexedDB (VR 투어 사진·영상) — 없는 DB 를 새로 만들지 않게 upgrade 를 취소한다 ── */
  function foreign(src, fn) {
    return new Promise(function (res) {
      if (!window.indexedDB || !src) return res(null);
      var rq; try { rq = indexedDB.open(src.db); } catch (e) { return res(null); }
      rq.onupgradeneeded = function () { try { rq.transaction.abort(); } catch (e) { } };
      rq.onerror = function () { res(null); };
      rq.onblocked = function () { res(null); };
      rq.onsuccess = function () {
        var d = rq.result;
        if (!d.objectStoreNames.contains(src.store)) { d.close(); return res(null); }
        var t = d.transaction(src.store, 'readonly'), out = fn(t.objectStore(src.store));
        t.oncomplete = function () { d.close(); res(out); };
        t.onerror = t.onabort = function () { d.close(); res(null); };
      };
    });
  }
  function foreignKeys(src) {
    var box = {};
    return foreign(src, function (st) { var r = st.getAllKeys(); r.onsuccess = function () { box.keys = r.result; }; return box; })
      .then(function () { return new Set(box.keys || []); });
  }
  function foreignGet(src, keys) {
    var out = {};
    return foreign(src, function (st) { keys.forEach(function (k) { var r = st.get(k); r.onsuccess = function () { if (r.result) out[k] = r.result; }; }); return out; })
      .then(function () { return out; });
  }

  /* ── CRC·zip (압축 없음, capture_pano.html 의 buildZip 과 같은 바이트) ── */
  var CRC_T = (function () { var t = new Uint32Array(256); for (var n = 0; n < 256; n++) { var c = n; for (var k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
  function crcUpd(c, u) { for (var i = 0; i < u.length; i++) c = CRC_T[(c ^ u[i]) & 0xFF] ^ (c >>> 8); return c; }
  function crc32Bytes(u) { return (crcUpd(0xFFFFFFFF, u) ^ 0xFFFFFFFF) >>> 0; }
  function crc32Blob(blob) {
    var c = 0xFFFFFFFF, off = 0, CH = 4 * MB;
    function step() {
      if (off >= blob.size) return Promise.resolve((c ^ 0xFFFFFFFF) >>> 0);
      return blob.slice(off, off + CH).arrayBuffer().then(function (b) { var u = new Uint8Array(b); c = crcUpd(c, u); off += u.length; return new Promise(function (r) { setTimeout(r, 0); }).then(step); });
    }
    return step();
  }
  function dosTime(t) { var d = new Date(t); return [((d.getHours() << 11) | (d.getMinutes() << 5) | (d.getSeconds() >> 1)) & 0xFFFF, (((d.getFullYear() - 1980) << 9) | ((d.getMonth() + 1) << 5) | d.getDate()) & 0xFFFF]; }
  function u16(v) { return [v & 255, (v >>> 8) & 255]; }
  function u32(v) { return [v & 255, (v >>> 8) & 255, (v >>> 16) & 255, (v >>> 24) & 255]; }
  var ENC = new TextEncoder();
  function zipSize(entries) { var n = 22; entries.forEach(function (e) { var l = ENC.encode(e.name).length; n += 30 + l + e.size + 46 + l; }); return n; }
  function buildZip(entries, datas) {    // entries [{name, crc, size, t}], datas: Blob 배열
    var parts = [], cd = [], off = 0;
    entries.forEach(function (e, i) {
      var nm = ENC.encode(e.name), dt = dosTime(e.t);
      var lh = [].concat(u32(0x04034b50), u16(20), u16(0x0800), u16(0), u16(dt[0]), u16(dt[1]), u32(e.crc), u32(e.size), u32(e.size), u16(nm.length), u16(0));
      parts.push(new Uint8Array(lh), nm, datas[i]);
      cd.push(new Uint8Array([].concat(u32(0x02014b50), u16(20), u16(20), u16(0x0800), u16(0), u16(dt[0]), u16(dt[1]), u32(e.crc), u32(e.size), u32(e.size), u16(nm.length), u16(0), u16(0), u16(0), u16(0), u32(0), u32(off))), nm);
      off += lh.length + nm.length + e.size;
    });
    var cdSize = cd.reduce(function (a, p) { return a + p.length; }, 0);
    var eocd = new Uint8Array([].concat(u32(0x06054b50), u16(0), u16(0), u16(entries.length), u16(entries.length), u32(cdSize), u32(off), u16(0)));
    return new Blob(parts.concat(cd, [eocd]), { type: 'application/zip' });
  }

  /* ── FormData 흉내: 페이지의 fd.append(...) 를 그대로 받는다 ── */
  function Form() { this.fields = {}; this.files = []; }
  Form.prototype.append = function (k, v, name) {
    if (v instanceof Blob) this.files.push({ field: k, blob: v, name: String(name || v.name || 'file.bin'), mime: v.type || '' });
    else this.fields[k] = String(v);
  };
  Form.prototype.appendZip = function (field, name, entries, src) {   // entries: [{name, text} | {name, key, blob, crc, size, t}]
    this.files.push({ field: field, name: name, mime: 'application/zip', zip: { src: src || null, entries: entries.map(function (e) {
      var o = { name: e.name, crc: e.crc >>> 0, size: e.size, t: e.t || Date.now() };
      if (e.text != null) { var b = ENC.encode(e.text); o.text = e.text; o.size = b.length; o.crc = crc32Bytes(b); }
      else { o.key = e.key || null; o.blob = e.blob || null; if (o.blob) o.size = o.blob.size; }
      return o;
    }) } });
  };

  /* ── 대기열에 넣기 ── */
  var CACHE = {};        // id → { files: [Blob|null], z: {key: Blob} } 이번 화면에서 이미 가진 파일 (다시 읽지 않게)
  var persistAsked = false;
  function storageFits(bytes) {
    try { if (!persistAsked && navigator.storage && navigator.storage.persist) { persistAsked = true; navigator.storage.persist().catch(noop); } } catch (e) { }
    if (!bytes || !(navigator.storage && navigator.storage.estimate)) return Promise.resolve(true);
    return navigator.storage.estimate().then(function (e) { return !e.quota || (e.quota - (e.usage || 0)) > bytes * 1.1 + 30 * MB; }, function () { return true; });
  }
  function putBlobs(list) {      // 하나씩 (큰 파일을 한 트랜잭션에 몰지 않게, 공간 부족을 바로 알게)
    var i = 0;
    function next() { if (i >= list.length) return Promise.resolve(); var b = list[i++]; return tx('blobs', 'readwrite', function (s) { return s.put(b.blob, b.key); }).then(next); }
    return next();
  }
  function enqueue(o) {
    var id = 'u' + Date.now().toString(36) + Math.random().toString(36).slice(2, 7), form = o.form;
    var own = [], cache = { files: [], z: {} };
    return READY.then(function () {
      return Promise.all(form.files.map(function (f, i) {
        if (!f.zip) return null;
        return (f.zip.src ? foreignKeys(f.zip.src) : Promise.resolve(new Set())).then(function (have) {
          f.zip.entries.forEach(function (e, j) {
            if (e.text != null) return;
            if (e.blob && e.key) cache.z[e.key] = e.blob;
            if (e.key && have.has(e.key)) return;                       // 이미 그 페이지 DB 에 있음 → 가리키기만
            if (!e.blob) throw err('임시 저장에서 파일을 찾지 못했습니다: ' + e.name + ' — 그 부분을 다시 찍어 주세요');
            e.own = id + '/' + i + '/' + j; own.push({ key: e.own, blob: e.blob }); cache.z[e.own] = e.blob;
          });
        });
      }));
    }).then(function () {
      var files = [], total = 0;
      form.files.forEach(function (f, i) {
        var r = { field: f.field, name: f.name, mime: f.mime, upload_id: null, chunk_size: 0, n_chunks: 0, done: false };
        if (f.zip) {
          r.zip = { src: f.zip.src, entries: f.zip.entries.map(function (e) { var x = { name: e.name, crc: e.crc, size: e.size, t: e.t }; if (e.text != null) x.text = e.text; if (e.key) x.key = e.key; if (e.own) x.own = e.own; return x; }) };
          r.size = zipSize(r.zip.entries); cache.files[i] = null;
        } else { r.key = id + '/f' + i; r.size = f.blob.size; own.push({ key: r.key, blob: f.blob }); cache.files[i] = f.blob; }
        if (INLINE_FIELDS[f.field] && r.size <= INLINE_MAX) r.inline = true;
        total += r.size; files.push(r);
      });
      var it = { id: id, v: 1, page: o.page || '', kind: o.kind || '', title: String(o.title || form.fields.title || '제목 없음').slice(0, 100), created: Date.now(),
        status: o.later ? 'later' : 'active', fields: form.fields, files: files, size: total, summary: o.summary || '', viewUrl: o.viewUrl || '',
        recent: o.recent || null, error: '', mem: false, warn: '' };
      var ownBytes = own.reduce(function (a, b) { return a + b.blob.size; }, 0);
      function toMem(why) { it.mem = true; it.warn = why; own.forEach(function (b) { MEM.blobs[b.key] = b.blob; }); MEM.items[id] = it; }
      return openDb().then(function (d) {
        if (!d) return toMem('이 브라우저는 기기에 보관할 수 없어요 — 이 화면을 닫으면 사라집니다. 지금 올리거나 ‘📥 폰에 파일로 저장’을 눌러 두세요.');
        return storageFits(ownBytes).then(function (fits) {
          if (!fits) return toMem('폰 저장 공간이 모자라 보관하지 못했어요 — 이 화면을 닫으면 사라집니다. 지금 올리거나 ‘📥 폰에 파일로 저장’을 눌러 두세요.');
          return putBlobs(own).then(function () { return tx('items', 'readwrite', function (s) { return s.put(it); }); }).catch(function () {
            tx('blobs', 'readwrite', function (s) { own.forEach(function (b) { s.delete(b.key); }); }).catch(noop);
            toMem('폰 저장 공간이 모자라 보관하지 못했어요 — 이 화면을 닫으면 사라집니다. 지금 올리거나 ‘📥 폰에 파일로 저장’을 눌러 두세요.');
          });
        });
      }).then(function () { CACHE[id] = cache; changed(); return id; });
    });
  }

  /* ── 파일 꺼내기 (보관한 Blob, 또는 VR 투어 zip 다시 만들기) ── */
  function fileBlob(it, i) {
    var c = CACHE[it.id] || (CACHE[it.id] = { files: [], z: {} }), f = it.files[i];
    if (c.files[i]) return Promise.resolve(c.files[i]);
    if (!f.zip) return getOwnBlob(it, f.key).then(function (b) { if (!b) throw err('보관한 파일을 이 폰에서 찾지 못했습니다 (저장 공간 정리로 지워졌을 수 있어요). 다시 찍어 주세요', 'perm'); c.files[i] = b; return b; });
    var es = f.zip.entries, needF = [], needO = [];
    es.forEach(function (e) { if (e.text != null) return; var k = e.own || e.key; if (c.z[k]) return; (e.own ? needO : needF).push(k); });
    return Promise.all([
      needF.length ? foreignGet(f.zip.src, needF) : {},
      Promise.all(needO.map(function (k) { return getOwnBlob(it, k).then(function (b) { return [k, b]; }); }))
    ]).then(function (r) {
      Object.keys(r[0]).forEach(function (k) { c.z[k] = r[0][k]; });
      r[1].forEach(function (p) { if (p[1]) c.z[p[0]] = p[1]; });
      var lost = es.filter(function (e) { return e.text == null && !c.z[e.own || e.key]; });
      if (lost.length) throw err('촬영 파일 ' + lost.length + '개를 이 폰에서 찾지 못했습니다 (지웠거나 다시 찍은 지점). 그 지점을 다시 찍어 새로 올려 주세요', 'perm');
      var z = buildZip(es, es.map(function (e) { return e.text != null ? new Blob([e.text]) : c.z[e.own || e.key]; }));
      if (z.size !== f.size) throw err('VR 투어 묶음 크기가 달라졌습니다. 다시 올려 주세요', 'perm');
      c.files[i] = z; return z;
    });
  }

  /* ── 올리기 엔진 ── */
  var RUN = {}, CHAIN = Promise.resolve(), LAST = {};
  function progress(ctl, p) {
    if (p.sent == null && ctl.total && ctl.base && ctl.base.length) { p.sent = Math.min(ctl.total, ctl.base.reduce(function (a, b) { return a + (b || 0); }, 0)); p.total = ctl.total; }
    p.id = ctl.id; p.at = Date.now(); ctl.p = p; LAST[ctl.id] = p;
    ctl.hs.forEach(function (h) { if (h && h.onProgress) try { h.onProgress(p); } catch (e) { } });
    emit('progress', ctl.id, p);
  }
  function sendProgress(ctl, force) {
    var now = Date.now(); if (!force && now - (ctl.lastEmit || 0) < 250) return; ctl.lastEmit = now;
    var sent = ctl.base.reduce(function (a, b) { return a + (b || 0); }, 0) + (ctl.cur || 0), s = ctl.samples;
    s.push([now, ctl.sessionSent + (ctl.cur || 0)]); while (s.length > 2 && now - s[0][0] > 8000) s.shift();
    var dt = (now - s[0][0]) / 1000, rate = dt >= 1 ? (s[s.length - 1][1] - s[0][1]) / dt : null;
    progress(ctl, { phase: 'send', sent: Math.min(sent, ctl.total), total: ctl.total, rate: rate && rate > 0 ? rate : null });
  }
  function sleep(ctl, ms, phase) {
    return new Promise(function (res) {
      var until = Date.now() + ms, tick = null;
      function done() { clearTimeout(t); clearInterval(tick); ctl.kick = null; res(); }
      var t = setTimeout(done, ms);
      ctl.kick = done;
      if (phase) { phase.until = until; progress(ctl, phase); tick = setInterval(function () { progress(ctl, phase); }, 1000); }
    });
  }
  function netErr(why) { return err(why, 'net'); }
  function req(ctl, method, path, body, ctype, onUp, timeout) {
    return new Promise(function (res, rej) {
      var x = new XMLHttpRequest(), last = Date.now(), stall = null;
      ctl.xhr = x;
      function end() { clearInterval(stall); if (ctl.xhr === x) ctl.xhr = null; }
      x.open(method, API + path, true);
      x.timeout = timeout || 60000;
      if (ctype) x.setRequestHeader('Content-Type', ctype);
      if (onUp && x.upload) {
        x.upload.onprogress = function (e) { last = Date.now(); onUp(e.loaded); };
        stall = setInterval(function () { if (Date.now() - last > STALL_MS) { ctl.stalled = true; x.abort(); } }, 5000);     // 한동안 한 바이트도 못 보내면 끊고 다시
      }
      x.onload = function () { end(); var j = null; try { j = JSON.parse(x.responseText); } catch (e) { } res({ status: x.status, json: j || {} }); };
      x.onerror = function () { end(); rej(netErr('network')); };
      x.ontimeout = function () { end(); rej(netErr('timeout')); };
      x.onabort = function () { end(); if (ctl.stopped) rej(pausedErr()); else { ctl.stalled = false; rej(netErr('stall')); } };
      x.send(body == null ? null : body);
    });
  }
  function retry(ctl, fn) {      // 네트워크·5xx 는 1초 → 2 → 4 … 60초 간격으로 계속, 오프라인이면 online 을 기다림
    var attempt = 0;
    function go() {
      if (ctl.stopped) return Promise.reject(pausedErr());
      if (navigator.onLine === false) return sleep(ctl, 20000, { phase: 'offline' }).then(function () { attempt = 0; return go(); });
      return fn().then(function (r) {
        if (r.status === 0 || r.status >= 500 || r.status === 408 || r.status === 429) throw netErr('HTTP ' + r.status);
        return r;
      }).catch(function (e) {
        if (!e.net || ctl.stopped) throw ctl.stopped ? pausedErr() : e;
        attempt++;
        var d = Math.round(Math.min(BACKOFF_MAX, 1000 * Math.pow(2, attempt - 1)) * (0.85 + Math.random() * 0.3));
        ctl.cur = 0;
        if (navigator.onLine === false) return go();
        return sleep(ctl, d, { phase: 'retry', attempt: attempt }).then(go);
      });
    }
    return go();
  }
  function session(ctl, it, i, blob) {      // → 서버가 이미 받은 조각 번호 Set
    var f = it.files[i];
    if (f.upload_id) {
      return retry(ctl, function () { return req(ctl, 'GET', 'upload_chunk.py?op=status&upload_id=' + encodeURIComponent(f.upload_id)); }).then(function (r) {
        if (r.status === 200 && r.json.size === blob.size && Array.isArray(r.json.received)) { f.chunk_size = r.json.chunk_size; f.n_chunks = r.json.n_chunks; return new Set(r.json.received); }
        f.upload_id = null; f.done = false;          // 만료(72시간)·크기 다름 → 처음부터
        return session(ctl, it, i, blob);
      });
    }
    return retry(ctl, function () {
      return req(ctl, 'POST', 'upload_chunk.py?op=init', JSON.stringify({ filename: f.name, size: blob.size, field: f.field, mime: f.mime }), 'application/json');
    }).then(function (r) {
      if (r.status !== 200 || !r.json.upload_id) throw err(r.json.error || '서버가 업로드를 시작하지 못했습니다 (HTTP ' + r.status + ')', 'perm');
      f.upload_id = r.json.upload_id; f.chunk_size = r.json.chunk_size; f.n_chunks = r.json.n_chunks; f.done = false;
      return saveItem(it).then(function () { return new Set(); });
    });
  }
  function sendFile(ctl, it, i) {
    var f = it.files[i], resets = 0;
    if (f.done && f.upload_id) { ctl.base[i] = f.size; return Promise.resolve(); }
    progress(ctl, { phase: 'prepare' });
    return fileBlob(it, i).then(function (blob) {
      if (blob.size !== f.size) { f.size = blob.size; f.upload_id = null; }
      return session(ctl, it, i, blob).then(function loop(have) {
        var cs = f.chunk_size, n = f.n_chunks, k = 0;
        ctl.base[i] = 0; have.forEach(function (j) { ctl.base[i] += Math.min(cs, blob.size - j * cs); });
        sendProgress(ctl, true);
        function next() {
          while (k < n && have.has(k)) k++;
          if (k >= n) { f.done = true; return saveItem(it); }
          var idx = k, part = blob.slice(idx * cs, Math.min(blob.size, (idx + 1) * cs));
          return retry(ctl, function () {
            ctl.cur = 0;
            return req(ctl, 'POST', 'upload_chunk.py?op=chunk&upload_id=' + encodeURIComponent(f.upload_id) + '&index=' + idx, part, 'application/octet-stream',
              function (loaded) { ctl.cur = loaded; sendProgress(ctl); }, CHUNK_TIMEOUT);
          }).then(function (r) {
            ctl.cur = 0;
            if (r.status === 200) { have.add(idx); ctl.base[i] += part.size; ctl.sessionSent += part.size; sendProgress(ctl, true); return next(); }
            if ((r.status === 404 || r.status === 400) && resets < 2) {       // 만료·조각 크기 다름 → 서버 상태를 다시 묻고 이어서
              resets++; if (r.status === 404) f.upload_id = null;
              return session(ctl, it, i, blob).then(loop);
            }
            throw err(r.json.error || '서버가 조각을 받지 않았습니다 (HTTP ' + r.status + ')', 'perm');
          });
        }
        return next();
      });
    });
  }
  function finish(ctl, it) {
    progress(ctl, { phase: 'finish', sent: ctl.total, total: ctl.total });
    var spec = {}, inl = [];
    it.files.forEach(function (f, i) { if (f.inline) inl.push(i); else (spec[f.field] = spec[f.field] || []).push(f.upload_id); });
    Object.keys(spec).forEach(function (k) { if (spec[k].length === 1 && k !== 'photo_files') spec[k] = spec[k][0]; });
    return Promise.all(inl.map(function (i) { return fileBlob(it, i); })).then(function (blobs) {
      return retry(ctl, function () {
        var fd = new FormData();
        Object.keys(it.fields).forEach(function (k) { fd.append(k, it.fields[k]); });
        fd.append('chunked_files', JSON.stringify(spec));
        inl.forEach(function (i, j) { fd.append(it.files[i].field, blobs[j], it.files[i].name); });
        return req(ctl, 'POST', 'upload.py', fd, null, null, FINISH_TIMEOUT);
      });
    }).then(function (r) {
      if (r.status >= 200 && r.status < 300 && r.json.job_id) return r.json;
      var msg = r.json.error || (r.status === 413 || r.status === 404 ? '서버가 받지 않았습니다 (HTTP ' + r.status + ')' : '서버 응답 오류 (HTTP ' + r.status + ')');
      if (r.status === 400 && /조각|만료/.test(msg) && (ctl.refinish = (ctl.refinish || 0) + 1) <= 2) {   // 조각이 빠졌거나 만료 → 다시 확인하고 이어서
        it.files.forEach(function (f) { f.done = false; if (/만료/.test(msg)) f.upload_id = null; });
        return saveItem(it).then(function () { return pass(ctl, it); });
      }
      throw err(msg, 'perm');
    });
  }
  function pass(ctl, it) {
    ctl.base = it.files.map(function () { return 0; }); ctl.cur = 0;
    var i = 0;
    function next() { if (i >= it.files.length) return finish(ctl, it); var j = i++; return it.files[j].inline ? next() : sendFile(ctl, it, j).then(next); }
    return next();
  }
  function complete(it, d) {
    if (d.edit_key) { var o = lsGet(KEYS_KEY, {}); if (!o || typeof o !== 'object' || Array.isArray(o)) o = {}; o[d.job_id] = d.edit_key; lsSet(KEYS_KEY, o); }
    if (it.recent && it.recent.key) {
      var l = lsGet(it.recent.key, []); l = (Array.isArray(l) ? l : []).filter(function (j) { return j.job_id !== d.job_id; });
      var e = {}; Object.keys(it.recent.entry || {}).forEach(function (k) { e[k] = it.recent.entry[k]; });
      e.job_id = d.job_id; e.t = e.t || Date.now(); if (d.visibility && 'vis' in e) e.vis = d.visibility;
      l.unshift(e); lsSet(it.recent.key, l.slice(0, it.recent.max || 20));
    }
    var dl = lsGet(DONE_KEY, []); dl = (Array.isArray(dl) ? dl : []).filter(function (x) { return Date.now() - x.t < 3 * 86400e3 && x.job_id !== d.job_id; });
    dl.unshift({ job_id: d.job_id, title: it.title, kind: it.kind, view: it.viewUrl ? it.viewUrl + encodeURIComponent(d.job_id) : '', t: Date.now(), dup: !!d.duplicate });
    lsSet(DONE_KEY, dl.slice(0, 5));
    return dropItem(it);
  }
  function withLock(id, fn) {
    if (navigator.locks && navigator.locks.request) {
      return navigator.locks.request('kgeo-upload-' + id, { ifAvailable: true }, function (lock) { if (!lock) throw err('다른 창에서 이 촬영을 올리는 중이에요', 'busy'); return fn(); });
    }
    return fn();
  }
  function start(id, h) {
    if (RUN[id]) { if (h) RUN[id].hs.push(h); if (RUN[id].p) progress(RUN[id], RUN[id].p); return RUN[id].promise; }
    var ctl = RUN[id] = { id: id, hs: h ? [h] : [], stopped: false, xhr: null, base: [], cur: 0, total: 0, samples: [], sessionSent: 0 }, it = null;
    progress(ctl, { phase: Object.keys(RUN).length > 1 ? 'queued' : 'prepare' });
    ctl.promise = new Promise(function (res, rej) {
      CHAIN = CHAIN.catch(noop).then(function () {
        if (ctl.stopped) throw pausedErr();
        return withLock(id, function () {
          return getItem(id).then(function (x) {
            if (!x) throw err('대기열에서 이 촬영을 찾지 못했습니다', 'perm');
            it = x; it.status = 'active'; it.error = '';
            ctl.total = it.files.reduce(function (a, f) { return a + (f.inline ? 0 : f.size); }, 0);
            return saveItem(it);
          }).then(function () { wake(true); changed(); return pass(ctl, it); }).then(function (d) {
            return complete(it, d).then(function () { return d; });
          });
        });
      }).then(function (d) {
        end(); progress(ctl, { phase: 'done', sent: ctl.total, total: ctl.total });
        ctl.hs.forEach(function (x) { if (x && x.onDone) try { x.onDone(d, it); } catch (e) { } });
        emit('done', d, it); changed(); res(d);
      }, function (e) {
        end();
        var save = it && !e.busy ? getItem(id).then(function (x) { if (!x) return; x.status = e.paused ? 'paused' : 'error'; x.error = e.paused ? '' : e.message; return saveItem(x); }) : Promise.resolve();
        save.then(function () { progress(ctl, { phase: e.paused ? 'paused' : 'error', msg: e.message }); changed(); rej(e); });
      });
      function end() { delete RUN[id]; delete LAST[id]; if (!Object.keys(RUN).length) wake(false); }
    });
    return ctl.promise;
  }
  function pause(id) {
    var c = RUN[id]; if (!c) return Promise.resolve();
    c.stopped = true; if (c.xhr) try { c.xhr.abort(); } catch (e) { } if (c.kick) c.kick();
    return c.promise.then(noop, noop);
  }
  function remove(id) {
    return pause(id).then(function () { return getItem(id); }).then(function (it) { if (it) return dropItem(it); }).then(changed);
  }
  function kickAll() { Object.keys(RUN).forEach(function (k) { if (RUN[k].kick) RUN[k].kick(); }); }
  function resumeActive() {
    return reload().then(function (l) { l.forEach(function (it) { if (it.status === 'active' && !RUN[it.id]) start(it.id).catch(noop); }); });
  }

  /* ── 화면 꺼짐 방지·화면 전환 (아이폰은 뒤에서 못 올린다) ── */
  var WL = null, savedTitle = null;
  function wake(on) {
    if (on) {
      if (WL || !navigator.wakeLock || document.hidden) return;
      navigator.wakeLock.request('screen').then(function (l) { WL = l; l.addEventListener('release', function () { WL = null; }); }).catch(noop);
    } else if (WL) { try { WL.release(); } catch (e) { } WL = null; }
  }
  document.addEventListener('visibilitychange', function () {
    var busy = Object.keys(RUN).length > 0;
    if (document.hidden) {
      if (busy && savedTitle == null) { savedTitle = document.title; document.title = '⏸ 업로드 멈춤 — 다시 열면 이어서'; }
    } else {
      if (savedTitle != null) { document.title = savedTitle; savedTitle = null; }
      if (busy) { wake(true); kickAll(); notice('다시 열었어요 — 받은 부분부터 이어서 올라가요'); }
    }
  });
  window.addEventListener('online', function () { kickAll(); resumeActive(); });
  window.addEventListener('offline', function () { Object.keys(RUN).forEach(function (k) { var c = RUN[k]; if (c.xhr) try { c.xhr.abort(); } catch (e) { } }); });

  function notice(msg) {
    css();
    var el = document.getElementById('kqNotice');
    if (!el) { el = document.createElement('div'); el.id = 'kqNotice'; el.className = 'kq-notice'; document.body.appendChild(el); }
    el.textContent = msg; el.classList.add('on'); clearTimeout(notice.t); notice.t = setTimeout(function () { el.classList.remove('on'); }, 4200);
  }

  /* ── 📥 폰에 파일로 저장 ── */
  function safeName(s) { return (String(s || 'kgeoscan').replace(/[\\/:*?"<>|\s]+/g, '_').slice(0, 40) || 'kgeoscan'); }
  function download(blob, name) {
    var a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; a.rel = 'noopener';
    document.body.appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 60000);
    return 'download';
  }
  function deliver(blob, name, mime) {
    var file = null; try { file = new File([blob], name, { type: mime || blob.type || 'application/octet-stream' }); } catch (e) { }
    if (IS_IOS && file && navigator.share && navigator.canShare) {       // 아이폰: 공유 시트 → '파일에 저장'·'비디오 저장'
      try {
        if (navigator.canShare({ files: [file] })) return navigator.share({ files: [file], title: name }).then(function () { return 'shared'; }, function (e) { return e && e.name === 'AbortError' ? 'cancel' : download(blob, name); });
      } catch (e) { }
    }
    return Promise.resolve(download(blob, name));
  }
  function exportItem(id) {
    var it;
    return getItem(id).then(function (x) {
      if (!x) throw err('대기열에서 이 촬영을 찾지 못했습니다');
      it = x; return Promise.all(it.files.map(function (f, i) { return fileBlob(it, i); }));
    }).then(function (blobs) {
      var stamp = new Date(it.created), ts = stamp.getFullYear() + ('0' + (stamp.getMonth() + 1)).slice(-2) + ('0' + stamp.getDate()).slice(-2) + '_' + ('0' + stamp.getHours()).slice(-2) + ('0' + stamp.getMinutes()).slice(-2);
      if (blobs.length === 1) { var f = it.files[0], ext = (f.name.match(/\.[A-Za-z0-9]{1,5}$/) || [''])[0]; return deliver(blobs[0], safeName(it.title) + '_' + ts + ext, f.mime); }
      // 여러 파일(사진 여러 장·부속 JSON): 압축 없이 한 zip 으로 + 올릴 때 쓰는 정보(upload_fields.json)
      var meta = ENC.encode(JSON.stringify({ title: it.title, kind: it.kind, created: new Date(it.created).toISOString(), fields: it.fields,
        files: it.files.map(function (f) { return { field: f.field, name: f.name, size: f.size }; }) }, null, 1));
      var used = {}, names = it.files.map(function (f) { var n = f.name, k = 1; while (used[n]) n = f.name.replace(/(\.[^.]*)?$/, '_' + (k++) + '$1'); used[n] = 1; return n; });
      return Promise.all(blobs.map(crc32Blob)).then(function (crcs) {
        var entries = [{ name: 'upload_fields.json', size: meta.length, crc: crc32Bytes(meta), t: it.created }], datas = [new Blob([meta])];
        blobs.forEach(function (b, j) { entries.push({ name: names[j], size: b.size, crc: crcs[j], t: it.created }); datas.push(b); });
        return deliver(buildZip(entries, datas), safeName(it.title) + '_' + ts + '.zip', 'application/zip');
      });
    });
  }

  /* ── 진행 표시 문구 (페이지 진행 막대·위젯 공용) ── */
  function describe(p) {
    p = p || {};
    var pct = p.total ? Math.min(100, (p.sent || 0) / p.total * 100) : 0;
    var left = p.total ? Math.floor(pct) + '% · ' + fmtSize(p.sent || 0) + ' / ' + fmtSize(p.total) : '';
    switch (p.phase) {
      case 'queued': return { main: '차례를 기다리는 중… 앞의 촬영을 올린 뒤 이어서 올려요', left: '', right: '', pct: 0, indet: true };
      case 'prepare': return { main: '올릴 준비 중…', left: left, right: '', pct: pct, indet: !p.total };
      case 'send': return { main: '올리는 중… 끊겨도 받은 부분부터 이어서 올라가요', left: left, right: p.rate ? (p.rate / MB).toFixed(2) + ' MB/s · ' + fmtEta((p.total - p.sent) / p.rate) : '속도 재는 중…', pct: pct };
      case 'retry': return { main: '연결이 불안정해요 — ' + Math.max(1, Math.ceil(((p.until || 0) - Date.now()) / 1000)) + '초 뒤 다시 시도 (' + p.attempt + '번째)', left: left, right: '받은 부분은 서버에 남아 있어요', pct: pct, warn: true };
      case 'offline': return { main: '인터넷이 끊겼어요 — 연결되면 저절로 이어서 올라가요', left: left, right: '받은 부분은 서버에 남아 있어요', pct: pct, warn: true };
      case 'finish': return { main: '서버가 받은 조각을 이어 붙여 저장하는 중…', left: p.total ? '100% · ' + fmtSize(p.total) : '', right: '큰 파일은 1분쯤 걸릴 수 있어요', pct: 100, indet: true };
      case 'done': return { main: '✓ 업로드 완료', left: p.total ? fmtSize(p.total) : '', right: '', pct: 100, done: true };
      case 'paused': return { main: '⏸ 일시정지 — 이 폰에 보관돼 있어요', left: '', right: '', pct: pct };
      case 'error': return { main: '✕ ' + (p.msg || '올리지 못했습니다'), left: '', right: '', pct: 0, bad: true };
      default: return { main: '', left: '', right: '', pct: 0 };
    }
  }
  function renderer(els) {      // {bar, main, left, right, hint} — 페이지의 기존 진행 막대(.bar > i)
    return function (p) {
      var d = describe(p);
      if (els.bar) { els.bar.className = 'bar' + (d.done ? ' done' : d.indet ? ' indet' : ''); var i = els.bar.firstElementChild; if (i) i.style.width = (d.indet ? 100 : d.pct).toFixed(1) + '%'; }
      if (els.main) els.main.textContent = d.main;
      if (els.left) els.left.textContent = d.left;
      if (els.right) els.right.textContent = d.right;
      if (els.hint) els.hint.textContent = d.done || p.phase === 'paused' || p.phase === 'error' ? '' : HINT;
    };
  }

  /* ── '올리지 못한 촬영 N개' 위젯 ── */
  var CSS = '.kq{margin:0 0 14px;padding:14px;border-radius:14px;background:var(--s2,#121820);border:1px solid var(--acc-o,#fb923c);color:var(--text,#f0f6ff);font-size:14px;line-height:1.5}' +
    '.kq[hidden]{display:none!important}.kq-h{display:flex;align-items:center;gap:8px;font-size:16px;font-weight:700}.kq-h .n{color:var(--acc-o,#fb923c)}' +
    '.kq-tip{color:var(--text2,#94a3b8);font-size:13px;margin:4px 0 8px}' +
    '.kq-it{padding:12px 0 4px;border-top:1px solid var(--border2,rgba(255,255,255,.12))}.kq-it:first-of-type{border-top:0}' +
    '.kq-t{font-weight:700;word-break:break-all}.kq-s{color:var(--text2,#94a3b8);font-size:13px}' +
    '.kq-st{font-size:13px;margin-top:4px}.kq-st.warn{color:var(--acc-o,#fb923c)}.kq-st.bad{color:var(--acc-r,#f87171)}.kq-st.ok{color:var(--acc-g,#34d399)}' +
    '.kq-w{font-size:13px;color:var(--acc-o,#fb923c);margin-top:4px}' +
    '.kq-bar{height:8px;border-radius:5px;background:rgba(255,255,255,.08);overflow:hidden;margin:6px 0 2px}.kq-bar i{display:block;height:100%;width:0;background:var(--accent,#38bdf8);transition:width .3s}' +
    '.kq-b{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}' +
    '.kq-b button,.kq-b a{flex:1 1 auto;min-height:48px;padding:10px 14px;border-radius:12px;border:1px solid var(--border2,rgba(255,255,255,.12));background:var(--s3,#18212d);color:var(--text,#f0f6ff);font:inherit;font-size:15px;font-weight:600;cursor:pointer;text-decoration:none;text-align:center}' +
    '.kq-b .go{background:var(--acc-g,#34d399);border-color:transparent;color:#05261a;flex:2 1 100%}.kq-b .del{flex:0 1 auto;color:var(--acc-r,#f87171)}.kq-b button:disabled{opacity:.5}' +
    '.kq-done{padding:8px 0;font-size:14px;color:var(--acc-g,#34d399)}.kq-done a{color:var(--accent,#38bdf8);margin-left:6px}' +
    '.kq-notice{position:fixed;left:50%;bottom:24px;transform:translate(-50%,20px);opacity:0;z-index:9999;max-width:92vw;padding:12px 16px;border-radius:12px;background:#0f2a1f;color:#d1fae5;border:1px solid #34d399;font-size:15px;transition:.25s;pointer-events:none}.kq-notice.on{opacity:1;transform:translate(-50%,0)}' +
    '.kq-badge{display:inline-block;min-width:20px;padding:0 6px;margin-left:6px;border-radius:10px;background:var(--acc-o,#fb923c);color:#1a0d00;font-size:12px;font-weight:800;line-height:20px;text-align:center}.kq-badge[hidden]{display:none}';
  function css() { if (document.getElementById('kqCss')) return; var s = document.createElement('style'); s.id = 'kqCss'; s.textContent = CSS; document.head.appendChild(s); }
  function stLine(it) {
    var p = LAST[it.id];
    if (p) { var d = describe(p); return { cls: d.bad ? 'bad' : d.warn ? 'warn' : d.done ? 'ok' : '', txt: d.main + (d.left ? ' · ' + d.left : '') + (d.right && p.phase === 'send' ? ' · ' + d.right : ''), pct: d.indet ? null : d.pct }; }
    if (it.status === 'error') return { cls: 'bad', txt: '✕ ' + (it.error || '올리지 못했습니다') + ' — 다시 올리거나 파일로 저장해 두세요' };
    if (it.status === 'active') return { cls: 'warn', txt: '올리다 멈췄어요 — ‘지금 올리기’를 누르면 받은 부분부터 이어서 올라가요' };
    if (it.status === 'paused') return { cls: 'warn', txt: '⏸ 일시정지 — 이어서 올릴 수 있어요' };
    return { cls: '', txt: '📦 이 폰에 보관 중 — 와이파이가 되는 곳에서 올려 주세요' };
  }
  function renderPending(box, opts) {
    if (!box) return null;
    opts = opts || {}; css();
    box.classList.add('kq'); box.hidden = true;
    function draw() {
      return reload().then(function (items) {
        var done = (lsGet(DONE_KEY, []) || []).filter(function (x) { return x && Date.now() - x.t < 3 * 86400e3; }).slice(0, opts.doneMax == null ? 3 : opts.doneMax);
        box.hidden = !items.length && !done.length;
        if (box.hidden) { box.innerHTML = ''; return; }
        box.innerHTML = (items.length ? '<div class="kq-h">📦 올리지 못한 촬영 <span class="n">' + items.length + '개</span></div>' +
          '<div class="kq-tip">' + (Object.keys(RUN).length ? esc(HINT) : '이 폰에 보관돼 있어요. 와이파이가 되는 곳에서 ‘지금 올리기’를 누르세요 — 끊겨도 받은 부분부터 이어서 올라가요.') + '</div>' : '') +
          items.map(function (it) {
            var s = stLine(it), run = !!RUN[it.id];
            return '<div class="kq-it" data-id="' + esc(it.id) + '"><div class="kq-t">' + esc(it.title) + '</div>' +
              '<div class="kq-s">' + esc([it.kind, fmtSize(it.size), fmtWhen(it.created), it.summary].filter(Boolean).join(' · ')) + '</div>' +
              (it.warn ? '<div class="kq-w">⚠ ' + esc(it.warn) + '</div>' : '') +
              '<div class="kq-bar"' + (s.pct == null && !run ? ' hidden' : '') + '><i style="width:' + (s.pct || 0).toFixed(1) + '%"></i></div>' +
              '<div class="kq-st ' + s.cls + '">' + esc(s.txt) + '</div>' +
              '<div class="kq-b">' + (run ? '<button type="button" data-a="pause">⏸ 일시정지</button>' : '<button type="button" class="go" data-a="up">지금 올리기 (와이파이 권장)</button>') +
              '<button type="button" data-a="save">📥 폰에 파일로 저장</button><button type="button" class="del" data-a="del">지우기</button></div></div>';
          }).join('') +
          done.map(function (x) { return '<div class="kq-done">✓ ‘' + esc(x.title) + '’ 올렸어요' + (x.dup ? ' (이미 받은 자료)' : '') + (x.view ? '<a href="' + esc(x.view) + '">결과 보기</a>' : '') + '</div>'; }).join('');
      });
    }
    function upd(id, p) {
      var row = box.querySelector('.kq-it[data-id="' + id + '"]'); if (!row) return;
      var d = describe(p), st = row.querySelector('.kq-st'), bar = row.querySelector('.kq-bar');
      st.className = 'kq-st ' + (d.bad ? 'bad' : d.warn ? 'warn' : d.done ? 'ok' : '');
      st.textContent = d.main + (d.left ? ' · ' + d.left : '') + (d.right && p.phase === 'send' ? ' · ' + d.right : '');
      bar.hidden = false; bar.firstElementChild.style.width = (d.indet ? 100 : d.pct).toFixed(1) + '%';
      var b = row.querySelector('[data-a="up"]');
      if (b && RUN[id]) b.outerHTML = '<button type="button" data-a="pause">⏸ 일시정지</button>';
    }
    box.addEventListener('click', function (e) {
      var b = e.target.closest('button[data-a]'); if (!b) return;
      var row = b.closest('.kq-it'), id = row && row.getAttribute('data-id'), a = b.getAttribute('data-a');
      var it = ITEMS.filter(function (x) { return x.id === id; })[0]; if (!it) return;
      if (a === 'up') {
        var conn = navigator.connection;
        if (conn && conn.type === 'cellular' && it.size > 100 * MB && !window.confirm('모바일 데이터로 ' + fmtSize(it.size) + '를 올립니다.\n요금이 나올 수 있어요. 계속할까요?')) return;
        start(id).catch(function (er) { if (!er.paused && !er.busy) notice(er.message); else if (er.busy) notice(er.message); });
        draw();
      } else if (a === 'pause') { pause(id).then(draw); }
      else if (a === 'save') {
        var t = b.textContent; b.disabled = true; b.textContent = '파일 만드는 중…';
        exportItem(id).then(function (r) { if (r === 'download') notice('📥 내려받기를 시작했어요 — ‘다운로드’ 폴더(아이폰은 ‘파일’ 앱)에 저장돼요'); }, function (er) { notice(er.message); })
          .then(function () { b.disabled = false; b.textContent = t; });
      } else if (a === 'del') {
        if (!window.confirm('‘' + it.title + '’ 촬영을 이 폰에서 지울까요?\n아직 올리지 않은 촬영이라 지우면 되돌릴 수 없어요.')) return;
        remove(id);
      }
    });
    on('change', draw); on('progress', upd);
    draw();
    return { refresh: draw };
  }
  function pendingCount() { return READY.then(reload).then(function (l) { return l.length; }); }
  function pinned(db, store) {
    var s = new Set();
    ITEMS.forEach(function (it) { it.files.forEach(function (f) { if (f.zip && f.zip.src && f.zip.src.db === db && f.zip.src.store === store) f.zip.entries.forEach(function (e) { if (e.key && !e.own) s.add(e.key); }); }); });
    return s;
  }
  function findClient(cid) {
    return READY.then(reload).then(function (l) { var it = l.filter(function (x) { return x.fields && x.fields.client_id === cid; })[0]; return it ? it.id : null; });
  }
  function badge(el) {        // ☰ 시작 같은 버튼 옆 숫자
    if (!el) return; css();
    function upd() { pendingCount().then(function (n) { el.hidden = !n; el.textContent = n ? String(n) : ''; el.title = n ? '올리지 못한 촬영 ' + n + '개' : ''; }); }
    on('change', upd); upd();
  }

  var READY = openDb().then(reload).catch(function () { return []; });
  READY.then(function () { setTimeout(resumeActive, 1200); });     // 올리다 멈춘 것은 페이지를 다시 열면 이어서

  window.KgeoUpload = {
    form: function () { return new Form(); }, enqueue: enqueue, start: start, pause: pause, remove: remove, exportItem: exportItem,
    list: function () { return READY.then(reload); }, pendingCount: pendingCount, findClient: findClient, pinned: pinned, ready: function () { return READY; },
    renderPending: renderPending, badge: badge, describe: describe, renderer: renderer, on: on, isRunning: function (id) { return !!RUN[id]; },
    notice: notice, hint: HINT, fmtSize: fmtSize, _buildZip: buildZip, _crc32Blob: crc32Blob
  };
})();
