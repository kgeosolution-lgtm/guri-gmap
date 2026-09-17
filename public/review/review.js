/* ==========================================================================
   구리 생활지도 · 수정 요청 위젯 (review.js)
   - 헤더 "테마 찾기" 옆에 "수정 요청" 메뉴를 붙이고, 클릭하면 창이 열려요.
   - 화면 캡처는 드래그로 원하는 부분만 잘라 담아요(전체는 전체 드래그).
   - 여러 명이 올린 요청이 구글 시트 한 장에 모이고, 상태(수정전/수정완료)를 함께 봐요. (서버 없음 — docs/review/README.md)
   - 오픈할 때는 이 스크립트 <script> 한 줄만 빼면 깨끗이 사라져요.

   설정: 아래 API / ADMIN 두 줄만 확인하세요.
   관리자(수정완료 체크)는 주소 뒤에 ?review=guri 를 붙여 열면 돼요.
   ========================================================================== */
(function () {
  'use strict';
  /* 저장소: 구글 시트 + Apps Script 웹 앱 (docs/review/Code.gs 를 배포한 URL 을 아래에 넣으세요)
     서버 없이 시트 한 장에 쌓이고, 캡처는 드라이브 폴더에 저장됩니다. */
  var API = 'PASTE_APPS_SCRIPT_WEB_APP_URL';      // 예: https://script.google.com/macros/s/AKfy.../exec
  var ADMIN_PARAM = 'review';                    // 관리자 모드 URL 파라미터 이름
  var ADMIN_VALUE = 'guri';                      // 이 값과 같아야 관리자 (Code.gs 의 ADMIN_KEY 와 동일)
  var API_READY = /^https?:\/\//.test(API);

  var KEY = new URLSearchParams(location.search).get(ADMIN_PARAM) || '';
  var IS_ADMIN = KEY === ADMIN_VALUE;
  var SENDKEY = IS_ADMIN ? ADMIN_VALUE : '';     // 서버로 보낼 관리자 암호

  /* 접수자 본인 표시용 토큰 (로그인 대신) */
  var MYTOKEN = '';
  try { MYTOKEN = localStorage.getItem('guri_review_token') || ''; if (!MYTOKEN) { MYTOKEN = 'u' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8); localStorage.setItem('guri_review_token', MYTOKEN); } } catch (e) { MYTOKEN = 'u' + Date.now().toString(36); }

  /* 현재 화면 자동 추정 */
  function guessScreen() {
    var p = location.pathname.toLowerCase();
    if (p.indexOf('theme') >= 0) return '테마지도';
    if (p.indexOf('animal') >= 0) return '유기동물 찾기';
    if (p.indexOf('aerial') >= 0) return '시계열 항공사진';
    if (p.indexOf('3d') >= 0 || p.indexOf('scene') >= 0) return '3D 지도';
    return '메인';
  }

  var sel = { screen: guessScreen(), type: '', sev: '' }, pending = '', items = [], filter = 'all', tab = 'write';

  /* ── 스타일 (gr- 접두사로 페이지 CSS와 분리) ── */
  var css = ''
   + '.gr-navlink{cursor:pointer}'
   + '.gr-fab{position:fixed;right:18px;bottom:18px;z-index:9998;background:#018058;color:#fff;font-weight:700;font-size:14px;border:none;border-radius:24px;padding:12px 18px;box-shadow:0 4px 16px rgba(1,128,88,.35);cursor:pointer;font-family:inherit}'
   + '.gr-fab:hover{background:#01573C}'
   + '.gr-modal{position:fixed;inset:0;z-index:9999;background:rgba(15,25,20,.45);display:none;align-items:flex-start;justify-content:center;padding:24px 14px;overflow:auto}'
   + '.gr-modal.on{display:flex}'
   + '.gr-box{background:#fff;color:#1E3229;width:100%;max-width:560px;border-radius:16px;box-shadow:0 20px 60px rgba(0,0,0,.25);font-family:Pretendard,-apple-system,"Malgun Gothic",sans-serif;overflow:hidden;margin:auto}'
   + '.gr-head{display:flex;align-items:center;gap:8px;padding:16px 18px;border-bottom:1px solid #E0EAE4}'
   + '.gr-head h3{font-size:17px;font-weight:800;margin:0}'
   + '.gr-adm{background:#1E3229;color:#fff;border-radius:20px;padding:2px 9px;font-size:11px;font-weight:700}'
   + '.gr-x{margin-left:auto;width:30px;height:30px;border:none;background:#F0F3F1;border-radius:8px;font-size:17px;cursor:pointer;color:#5B6C66}'
   + '.gr-tabs{display:flex;gap:6px;padding:12px 18px 0}'
   + '.gr-tab{border:none;background:none;font-size:14px;font-weight:700;color:#93A69C;padding:6px 4px;cursor:pointer;border-bottom:2px solid transparent}'
   + '.gr-tab.on{color:#018058;border-color:#018058}'
   + '.gr-body{padding:16px 18px 18px;max-height:70vh;overflow:auto}'
   + '.gr-g{margin-bottom:13px}'
   + '.gr-l{display:block;font-weight:700;font-size:13px;margin-bottom:7px}'
   + '.gr-l span{color:#93A69C;font-weight:500;font-size:11.5px;margin-left:4px}'
   + '.gr-chips{display:flex;flex-wrap:wrap;gap:6px}'
   + '.gr-chips button{border:1.5px solid #E0EAE4;background:#fff;border-radius:18px;padding:6px 12px;font-size:13px;font-weight:600;color:#5B6C66;cursor:pointer;font-family:inherit}'
   + '.gr-chips button.on{background:#018058;border-color:#018058;color:#fff}'
   + '.gr-chips.sev button.on[data-v="높음"]{background:#C8442E;border-color:#C8442E}'
   + '.gr-chips.sev button.on[data-v="보통"]{background:#B26A00;border-color:#B26A00}'
   + '.gr-in,.gr-ta{width:100%;border:1.5px solid #E0EAE4;border-radius:9px;padding:10px 12px;font-size:14.5px;font-family:inherit;color:#1E3229;outline:none;box-sizing:border-box}'
   + '.gr-ta{resize:vertical;min-height:72px}'
   + '.gr-in:focus,.gr-ta:focus{border-color:#018058}'
   + '.gr-cap{display:flex;gap:10px;align-items:center;flex-wrap:wrap}'
   + '.gr-capbtn{display:inline-flex;align-items:center;gap:6px;border:1.5px dashed #E0EAE4;background:#fff;border-radius:9px;padding:9px 13px;font-size:13.5px;font-weight:600;color:#5B6C66;cursor:pointer;font-family:inherit}'
   + '.gr-capbtn:hover{border-color:#018058;color:#018058}'
   + '.gr-hint{color:#93A69C;font-size:12px}'
   + '.gr-pend{position:relative;width:90px;height:66px;border-radius:8px;overflow:hidden;border:1px solid #E0EAE4;flex:none}'
   + '.gr-pend img{width:100%;height:100%;object-fit:cover}'
   + '.gr-pend button{position:absolute;top:2px;right:2px;width:19px;height:19px;border-radius:50%;background:rgba(0,0,0,.6);color:#fff;font-size:12px;border:none;cursor:pointer;line-height:1}'
   + '.gr-submit{width:100%;background:#018058;color:#fff;font-weight:700;font-size:15px;border:none;border-radius:10px;padding:13px;margin-top:6px;cursor:pointer;font-family:inherit}'
   + '.gr-submit:hover{background:#01573C}.gr-submit:disabled{opacity:.6;cursor:default}'
   + '.gr-fil{display:flex;gap:6px;margin-bottom:12px;flex-wrap:wrap}'
   + '.gr-fil button{border:1px solid #E0EAE4;background:#fff;border-radius:16px;padding:5px 11px;font-size:12px;font-weight:600;color:#5B6C66;cursor:pointer;font-family:inherit}'
   + '.gr-fil button.on{background:#1E3229;border-color:#1E3229;color:#fff}'
   + '.gr-fil .sp{flex:1}'
   + '.gr-item{border:1px solid #E0EAE4;border-radius:11px;padding:12px;margin-bottom:9px;display:flex;gap:10px}'
   + '.gr-item.done{opacity:.62}'
   + '.gr-st{flex:none}.gr-st .d{width:24px;height:24px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:800}'
   + '.gr-st.todo .d{background:#FBF1DF;color:#B26A00}.gr-st.done .d{background:#018058;color:#fff}'
   + '.gr-st button{display:block;font-size:10.5px;color:#93A69C;margin-top:4px;background:none;border:none;cursor:pointer;width:100%;font-family:inherit}'
   + '.gr-m{flex:1;min-width:0}'
   + '.gr-bd{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:5px}'
   + '.gr-b{border-radius:16px;padding:2px 9px;font-size:11.5px;font-weight:700}'
   + '.gr-b.todo{background:#FBF1DF;color:#B26A00}.gr-b.done{background:#E3F3EE;color:#018058}'
   + '.gr-b.scr{background:#EAF3FB;color:#2A6DB0}.gr-b.typ{background:#EDEFF2;color:#455}.gr-b.loc{background:#EEF6F2;color:#3A6E58}'
   + '.gr-b.sv-높음{background:#FBE7E3;color:#C8442E}.gr-b.sv-보통{background:#FBF1DF;color:#B26A00}'
   + '.gr-tx{font-size:14px;white-space:pre-wrap;word-break:break-word}'
   + '.gr-item.done .gr-tx{text-decoration:line-through;color:#93A69C}'
   + '.gr-dt{color:#93A69C;font-size:11px;margin-top:4px}.gr-dt .mine{color:#018058;font-weight:700;margin-left:5px}'
   + '.gr-r{display:flex;flex-direction:column;align-items:flex-end;gap:6px;flex:none}'
   + '.gr-th{width:92px;height:64px;object-fit:cover;border-radius:8px;border:1px solid #E0EAE4;cursor:zoom-in}'
   + '.gr-del{color:#93A69C;font-size:12px;background:none;border:none;cursor:pointer;font-family:inherit}'
   + '.gr-empty{color:#93A69C;font-size:13.5px;text-align:center;padding:26px 0}'
   + '.gr-crop{position:fixed;inset:0;z-index:10001;background:rgba(15,25,20,.92);display:none;flex-direction:column;padding:14px}'
   + '.gr-crop.on{display:flex}'
   + '.gr-crop .t{color:#fff;text-align:center;font-size:14px;font-weight:600;padding:6px 0 10px}'
   + '.gr-stage{flex:1;display:flex;align-items:center;justify-content:center;overflow:auto;min-height:0}'
   + '.gr-holder{position:relative;display:inline-block;line-height:0}'
   + '.gr-holder img{max-width:100%;max-height:72vh;user-select:none;-webkit-user-drag:none}'
   + '.gr-sel{position:absolute;border:2px solid #fff;background:rgba(1,128,88,.18);box-shadow:0 0 0 9999px rgba(0,0,0,.5);pointer-events:none}'
   + '.gr-cbar{display:flex;gap:10px;justify-content:center;padding-top:12px;flex-wrap:wrap}'
   + '.gr-cbar button{border-radius:9px;padding:11px 18px;font-size:14px;font-weight:700;border:none;cursor:pointer;font-family:inherit}'
   + '.gr-cbar .gh{background:rgba(255,255,255,.16);color:#fff}.gr-cbar .pr{background:#018058;color:#fff}.gr-cbar .pr:disabled{opacity:.5;cursor:default}'
   + '.gr-lb{position:fixed;inset:0;z-index:10002;background:rgba(0,0,0,.82);display:none;align-items:center;justify-content:center;padding:20px}'
   + '.gr-lb.on{display:flex}.gr-lb img{max-width:100%;max-height:92vh;border-radius:8px}'
   + '.gr-toast{position:fixed;left:50%;bottom:22px;transform:translateX(-50%);background:#1E3229;color:#fff;font-size:13.5px;padding:10px 16px;border-radius:9px;opacity:0;pointer-events:none;transition:opacity .2s;z-index:10003;max-width:90%;text-align:center;font-family:Pretendard,sans-serif}'
   + '.gr-toast.on{opacity:1}';

  function el(tag, attrs, html) { var e = document.createElement(tag); if (attrs) for (var k in attrs) e.setAttribute(k, attrs[k]); if (html != null) e.innerHTML = html; return e; }
  function esc(s) { return (s || '').replace(/[&<>]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]; }); }
  function fmt(ts) { var d = new Date(ts), p = function (n) { return ('0' + n).slice(-2); }; return d.getFullYear() + '.' + p(d.getMonth() + 1) + '.' + p(d.getDate()) + ' ' + p(d.getHours()) + ':' + p(d.getMinutes()); }
  var $ = function (id) { return document.getElementById(id); };
  function toast(m) { var t = $('grToast'); t.textContent = m; t.classList.add('on'); clearTimeout(t._h); t._h = setTimeout(function () { t.classList.remove('on'); }, 2600); }

  /* ── DOM 만들기 ── */
  function build() {
    document.head.appendChild(el('style', null, css));

    var chipRow = function (id, cls, arr) {
      return '<div class="gr-chips ' + (cls || '') + '" id="' + id + '">' + arr.map(function (v) { return '<button type="button" data-v="' + v + '">' + v + '</button>'; }).join('') + '</div>';
    };
    var modal = el('div', { class: 'gr-modal', id: 'grModal' });
    modal.innerHTML =
      '<div class="gr-box">'
      + '<div class="gr-head"><h3>수정 요청</h3>' + (IS_ADMIN ? '<span class="gr-adm">관리자</span>' : '') + '<button class="gr-x" id="grClose">×</button></div>'
      + '<div class="gr-tabs"><button class="gr-tab on" id="grTabWrite">적기</button><button class="gr-tab" id="grTabList">목록 <span id="grCount"></span></button></div>'
      + '<div class="gr-body" id="grWrite">'
      + '<div class="gr-g"><span class="gr-l">어느 화면</span>' + chipRow('grScreens', '', ['메인', '테마지도', '유기동물 찾기', '시계열 항공사진', '3D 지도', '기타']) + '</div>'
      + '<div class="gr-g"><span class="gr-l">종류 <span>선택</span></span>' + chipRow('grTypes', '', ['오타·문구', '정보 오류', '위치 이상', '디자인·화면', '기능 오류', '추가 요청']) + '</div>'
      + '<div class="gr-g"><span class="gr-l">위치·시설 이름 <span>선택</span></span><input type="text" class="gr-in" id="grLoc" placeholder="예: 인창공영주차장"></div>'
      + '<div class="gr-g"><span class="gr-l">무엇을 어떻게 고칠까요</span><textarea class="gr-ta" id="grText" placeholder="예: 전화번호가 예전 번호예요. 031-550-0000 으로 바꿔주세요"></textarea></div>'
      + '<div class="gr-g"><span class="gr-l">중요도 <span>선택</span></span>' + chipRow('grSev', 'sev', ['높음', '보통', '낮음']) + '</div>'
      + '<div class="gr-g"><span class="gr-l">화면 캡처 <span>선택 · 원하는 부분만 드래그</span></span>'
      + '<div class="gr-cap"><button type="button" class="gr-capbtn" id="grCap">📷 화면 캡처</button>'
      + '<div class="gr-pend" id="grPend" hidden><img id="grPendImg" alt=""><button type="button" id="grPendDel">×</button></div>'
      + '<span class="gr-hint">캡처 후 드래그로 영역 선택 · Ctrl+V 붙여넣기도 돼요</span></div></div>'
      + '<button type="button" class="gr-submit" id="grAdd">＋ 보내기</button>'
      + '</div>'
      + '<div class="gr-body" id="grList" style="display:none">'
      + '<div class="gr-fil" id="grFil"><button class="on" data-f="all">전체</button><button data-f="todo">수정전</button><button data-f="done">수정완료</button><span class="sp"></span><button data-f="_refresh" style="color:#93A69C">새로고침</button></div>'
      + '<div id="grItems"><div class="gr-empty">불러오는 중…</div></div>'
      + '</div>'
      + '</div>';
    document.body.appendChild(modal);

    var crop = el('div', { class: 'gr-crop', id: 'grCrop' });
    crop.innerHTML = '<div class="t">캡처할 부분을 드래그해서 선택하세요</div>'
      + '<div class="gr-stage"><div class="gr-holder" id="grHolder"><img id="grCropImg" alt=""><div class="gr-sel" id="grSel" hidden></div></div></div>'
      + '<div class="gr-cbar"><button class="gh" id="grCropCancel">취소</button><button class="gh" id="grCropFull">전체 사용</button><button class="pr" id="grCropUse" disabled>선택 영역 사용</button></div>';
    document.body.appendChild(crop);

    document.body.appendChild(el('div', { class: 'gr-lb', id: 'grLb' }, '<img id="grLbImg" alt="">'));
    document.body.appendChild(el('div', { class: 'gr-toast', id: 'grToast' }));

    /* 메뉴/버튼 붙이기: 헤더 nav 있으면 "수정 요청" 링크, 없으면 떠있는 버튼 */
    var navs = document.querySelectorAll('.service-nav, header nav');
    var placed = false;
    navs.forEach(function (nav) {
      var a = el('a', { class: 'gr-navlink', role: 'button', tabindex: '0' }, '수정 요청');
      a.addEventListener('click', function (ev) { ev.preventDefault(); open(); });
      nav.appendChild(a); placed = true;
    });
    if (!placed) {
      var fab = el('button', { class: 'gr-fab', type: 'button' }, '✍ 수정 요청');
      fab.addEventListener('click', open);
      document.body.appendChild(fab);
    }
  }

  /* ── 열기/닫기/탭 ── */
  function open() { $('grModal').classList.add('on'); preselectScreen(); if (tab === 'list') loadList(); }
  function close() { $('grModal').classList.remove('on'); }
  function preselectScreen() {
    var g = $('grScreens'); [].forEach.call(g.children, function (b) { b.classList.toggle('on', b.getAttribute('data-v') === sel.screen); });
  }
  function switchTab(t) {
    tab = t;
    $('grTabWrite').classList.toggle('on', t === 'write');
    $('grTabList').classList.toggle('on', t === 'list');
    $('grWrite').style.display = t === 'write' ? '' : 'none';
    $('grList').style.display = t === 'list' ? '' : 'none';
    if (t === 'list') loadList();
  }

  /* ── 칩 ── */
  function chipGroup(id, key) {
    $(id).addEventListener('click', function (e) {
      var b = e.target.closest('button'); if (!b) return;
      var on = b.classList.contains('on');
      [].forEach.call($(id).children, function (x) { x.classList.remove('on'); });
      if (!on) { b.classList.add('on'); sel[key] = b.getAttribute('data-v'); } else { sel[key] = ''; }
    });
  }

  /* ── 미리보기/축소 ── */
  function setPending(url) { pending = url; $('grPendImg').src = url || ''; $('grPend').hidden = !url; }
  function shrink(dataUrl, maxW, cb) {
    var img = new Image();
    img.onload = function () { var w = img.width, h = img.height; if (w > maxW) { h = Math.round(h * maxW / w); w = maxW; } var c = document.createElement('canvas'); c.width = w; c.height = h; c.getContext('2d').drawImage(img, 0, 0, w, h); cb(c.toDataURL('image/jpeg', 0.78)); };
    img.src = dataUrl;
  }

  /* ── 크롭 ── */
  var cropNat = { w: 0, h: 0 }, drag = null, selRect = null;
  function openCrop(dataUrl) { var img = $('grCropImg'); img.onload = function () { cropNat = { w: img.naturalWidth, h: img.naturalHeight }; }; img.src = dataUrl; selRect = null; $('grSel').hidden = true; $('grCropUse').disabled = true; $('grCrop').classList.add('on'); }
  function closeCrop() { $('grCrop').classList.remove('on'); drag = null; }
  function relPos(ev) { var r = $('grCropImg').getBoundingClientRect(); var cx = ev.touches ? ev.touches[0].clientX : ev.clientX; var cy = ev.touches ? ev.touches[0].clientY : ev.clientY; return { x: Math.min(Math.max(cx - r.left, 0), r.width), y: Math.min(Math.max(cy - r.top, 0), r.height), rect: r }; }
  function drawSel() { if (!selRect) { $('grSel').hidden = true; return; } var s = $('grSel'); s.hidden = false; s.style.left = selRect.x + 'px'; s.style.top = selRect.y + 'px'; s.style.width = selRect.w + 'px'; s.style.height = selRect.h + 'px'; }
  function startDrag(ev) { ev.preventDefault(); var p = relPos(ev); drag = { x0: p.x, y0: p.y }; selRect = null; drawSel(); }
  function moveDrag(ev) { if (!drag) return; ev.preventDefault(); var p = relPos(ev); selRect = { x: Math.min(drag.x0, p.x), y: Math.min(drag.y0, p.y), w: Math.abs(p.x - drag.x0), h: Math.abs(p.y - drag.y0), dispW: p.rect.width, dispH: p.rect.height }; drawSel(); }
  function endDrag() { if (!drag) return; drag = null; $('grCropUse').disabled = !(selRect && selRect.w > 6 && selRect.h > 6); }

  /* ── 화면 캡처 ── */
  function doCapture() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getDisplayMedia) { toast('이 브라우저는 화면 캡처를 지원 안 해요. Win+Shift+S로 캡처 후 Ctrl+V로 붙여넣어 주세요'); return; }
    navigator.mediaDevices.getDisplayMedia({ video: true, audio: false }).then(function (stream) {
      var video = document.createElement('video'); video.srcObject = stream; video.muted = true;
      video.play().then(function () {
        setTimeout(function () {
          var c = document.createElement('canvas'); c.width = video.videoWidth; c.height = video.videoHeight;
          c.getContext('2d').drawImage(video, 0, 0, c.width, c.height);
          stream.getTracks().forEach(function (t) { t.stop(); });
          openCrop(c.toDataURL('image/jpeg', 0.92));
        }, 350);
      });
    }).catch(function () { });
  }

  /* ── 서버 ── */
  /* Apps Script 웹 앱: GET ?action=list / ?action=shot&id=… , POST 는 본문을 JSON 문자열로(헤더를 붙이면 브라우저가 사전 요청을 보내 막힙니다) */
  function apiGet(params) { if (!API_READY) return Promise.reject('API 주소가 아직 설정되지 않았어요'); return fetch(API + '?' + params + '&_=' + Date.now(), { cache: 'no-store', redirect: 'follow' }).then(function (r) { if (!r.ok) throw '서버 응답 오류'; return r.json(); }).then(function (j) { if (j && j.error) throw j.error; return j; }); }
  function apiPost(action, body) { if (!API_READY) return Promise.reject('API 주소가 아직 설정되지 않았어요'); var b = {}; for (var k in body) b[k] = body[k]; b.action = action; return fetch(API, { method: 'POST', body: JSON.stringify(b), redirect: 'follow' }).then(function (r) { return r.json().catch(function () { throw '서버 응답 오류'; }); }).then(function (j) { if (!j || j.error) throw ((j && j.error) || '오류'); return j; }); }
  var shotCache = {};
  function loadShots() {
    [].forEach.call($('grItems').querySelectorAll('img[data-shot]'), function (img) {
      var id = img.getAttribute('data-shot');
      if (shotCache[id]) { img.src = shotCache[id]; return; }
      apiGet('action=shot&id=' + encodeURIComponent(id)).then(function (j) { if (j && j.data) { shotCache[id] = j.data; img.src = j.data; } }).catch(function () { img.style.display = 'none'; });
    });
  }

  function loadList() {
    $('grItems').innerHTML = '<div class="gr-empty">불러오는 중…</div>';
    apiGet('action=list').then(function (data) { items = data; render(); loadShots(); }).catch(function (err) { $('grItems').innerHTML = '<div class="gr-empty">목록을 불러오지 못했어요.<br>' + esc(String(err)) + '</div>'; });
  }
  function render() {
    var doneN = items.filter(function (i) { return i.status === 'done'; }).length;
    $('grCount').textContent = items.length ? '(' + doneN + '/' + items.length + ')' : '';
    var show = items;
    if (filter === 'todo') show = items.filter(function (i) { return i.status !== 'done'; });
    if (filter === 'done') show = items.filter(function (i) { return i.status === 'done'; });
    if (!items.length) { $('grItems').innerHTML = '<div class="gr-empty">아직 올라온 요청이 없어요.</div>'; return; }
    if (!show.length) { $('grItems').innerHTML = '<div class="gr-empty">해당하는 항목이 없어요.</div>'; return; }
    $('grItems').innerHTML = show.map(function (it) {
      var done = it.status === 'done', mine = it.owner && it.owner === MYTOKEN, canDel = mine || IS_ADMIN;
      return '<div class="gr-item ' + (done ? 'done' : '') + '">'
        + '<div class="gr-st ' + (done ? 'done' : 'todo') + '"><div class="d">' + (done ? '✓' : '!') + '</div>'
        + (IS_ADMIN ? '<button data-toggle="' + it.id + '" data-to="' + (done ? 'todo' : 'done') + '">' + (done ? '되돌리기' : '완료') + '</button>' : '') + '</div>'
        + '<div class="gr-m"><div class="gr-bd">'
        + '<span class="gr-b ' + (done ? 'done' : 'todo') + '">' + (done ? '수정완료' : '수정전') + '</span>'
        + (it.screen ? '<span class="gr-b scr">' + esc(it.screen) + '</span>' : '')
        + (it.type ? '<span class="gr-b typ">' + esc(it.type) + '</span>' : '')
        + (it.sev && it.sev !== '낮음' ? '<span class="gr-b sv-' + esc(it.sev) + '">' + esc(it.sev) + '</span>' : '')
        + (it.loc ? '<span class="gr-b loc">📍 ' + esc(it.loc) + '</span>' : '')
        + '</div><div class="gr-tx">' + esc(it.content) + '</div>'
        + '<div class="gr-dt">' + fmt(it.created_at) + (it.who ? ' · ' + esc(it.who) : '') + (mine ? '<span class="mine">내 요청</span>' : '') + '</div></div>'
        + '<div class="gr-r">' + (it.shot_id ? '<img class="gr-th" data-shot="' + esc(it.shot_id) + '" data-full="' + it.id + '" alt="캡처">' : '') + (canDel ? '<button class="gr-del" data-del="' + it.id + '">삭제</button>' : '') + '</div>'
        + '</div>';
    }).join('');
  }

  /* ── 이벤트 ── */
  function wire() {
    chipGroup('grScreens', 'screen'); chipGroup('grTypes', 'type'); chipGroup('grSev', 'sev');
    $('grClose').addEventListener('click', close);
    $('grModal').addEventListener('click', function (e) { if (e.target === $('grModal')) close(); });
    $('grTabWrite').addEventListener('click', function () { switchTab('write'); });
    $('grTabList').addEventListener('click', function () { switchTab('list'); });
    $('grPendDel').addEventListener('click', function () { setPending(''); });
    $('grCap').addEventListener('click', doCapture);

    $('grHolder').addEventListener('mousedown', startDrag);
    window.addEventListener('mousemove', moveDrag); window.addEventListener('mouseup', endDrag);
    $('grHolder').addEventListener('touchstart', startDrag, { passive: false });
    $('grHolder').addEventListener('touchmove', moveDrag, { passive: false });
    $('grHolder').addEventListener('touchend', endDrag);
    $('grCropCancel').addEventListener('click', closeCrop);
    $('grCropFull').addEventListener('click', function () { shrink($('grCropImg').src, 1400, function (u) { setPending(u); closeCrop(); toast('전체 화면을 담았어요'); }); });
    $('grCropUse').addEventListener('click', function () {
      if (!selRect) return;
      var sx = cropNat.w / selRect.dispW, sy = cropNat.h / selRect.dispH;
      var cw = Math.round(selRect.w * sx), ch = Math.round(selRect.h * sy);
      var c = document.createElement('canvas'); c.width = cw; c.height = ch; var img = new Image();
      img.onload = function () { c.getContext('2d').drawImage(img, Math.round(selRect.x * sx), Math.round(selRect.y * sy), cw, ch, 0, 0, cw, ch); shrink(c.toDataURL('image/jpeg', 0.9), 1400, function (u) { setPending(u); closeCrop(); toast('선택 영역을 담았어요'); }); };
      img.src = $('grCropImg').src;
    });

    window.addEventListener('paste', function (e) {
      if (!$('grModal').classList.contains('on')) return;
      if ($('grCrop').classList.contains('on')) return;
      var arr = (e.clipboardData || {}).items || [];
      var it = [].slice.call(arr).find(function (x) { return x.type && x.type.indexOf('image/') === 0; });
      if (!it) return;
      var f = it.getAsFile(); var r = new FileReader(); r.onload = function (ev) { openCrop(ev.target.result); }; r.readAsDataURL(f);
    });

    $('grAdd').addEventListener('click', function () {
      var content = $('grText').value.trim();
      if (!content) { toast('고칠 내용을 적어주세요'); $('grText').focus(); return; }
      $('grAdd').disabled = true;
      apiPost('add', { screen: sel.screen, type: sel.type, sev: sel.sev, loc: $('grLoc').value.trim(), content: content, who: '', shot: pending, owner: MYTOKEN, page_url: location.href })
        .then(function () {
          $('grText').value = ''; $('grLoc').value = ''; setPending(''); sel.type = ''; sel.sev = '';
          ['grTypes', 'grSev'].forEach(function (g) { [].forEach.call($(g).children, function (x) { x.classList.remove('on'); }); });
          toast('보냈어요. 고맙습니다'); switchTab('list');
        })
        .catch(function (err) { toast(String(err)); })
        .then(function () { $('grAdd').disabled = false; });
    });

    $('grFil').addEventListener('click', function (e) {
      var b = e.target.closest('button'); if (!b) return;
      var f = b.getAttribute('data-f');
      if (f === '_refresh') { loadList(); return; }
      filter = f; [].forEach.call($('grFil').querySelectorAll('button'), function (x) { if (x.getAttribute('data-f') !== '_refresh') x.classList.remove('on'); }); b.classList.add('on'); render();
    });
    $('grItems').addEventListener('click', function (e) {
      var tg = e.target.closest('[data-toggle]');
      if (tg) { apiPost('status', { id: tg.getAttribute('data-toggle'), status: tg.getAttribute('data-to'), key: SENDKEY }).then(loadList).catch(function (err) { toast(String(err)); }); return; }
      var del = e.target.closest('[data-del]');
      if (del) { if (!confirm('이 요청을 지울까요?')) return; apiPost('delete', { id: del.getAttribute('data-del'), owner: MYTOKEN, key: SENDKEY }).then(loadList).catch(function (err) { toast(String(err)); }); return; }
      var img = e.target.closest('[data-full]');
      if (img) { var it = items.find(function (x) { return String(x.id) === img.getAttribute('data-full'); }); var src = it && it.shot_id && shotCache[it.shot_id]; if (src) { $('grLbImg').src = src; $('grLb').classList.add('on'); } }
    });
    $('grLb').addEventListener('click', function () { $('grLb').classList.remove('on'); });
  }

  function init() { build(); wire(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
