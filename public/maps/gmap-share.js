/* 링크 공유 — 지도 페이지 공용(우리동네 찾기·3D·항공).
   기기 공유창(navigator.share)이 있으면 그것을 쓰고, 없으면(카카오톡 안 브라우저·일부 PC) 같은 모양의 공유창을 페이지 안에 띄운다:
   주소 복사 · 카카오톡 · 문자 · 이메일. 모양은 gmap-shared.css 의 .gm-share-* (담당: 강민아) */
(function () {
  /* 카카오톡 단추는 카카오 개발자 앱의 JavaScript 키가 있어야 동작한다(없으면 단추를 숨기고 '복사해서 붙여넣기' 안내만).
     발급: developers.kakao.com → 내 애플리케이션 → 앱 추가 → [앱 키] JavaScript 키, [플랫폼 > Web] 사이트 도메인에
     https://kgeodata.com 과 최종 서비스 도메인 등록, [카카오 로그인]은 필요 없음. 키를 아래에 넣으면 단추가 살아난다. */
  const KAKAO_JS_KEY = '';
  const KAKAO_SDK = 'https://t1.kakaocdn.net/kakao_js_sdk/2.7.4/kakao.min.js';
  const enc = encodeURIComponent;
  const ICON = {
    kakao: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 4c-4.6 0-8 2.9-8 6.4 0 2.2 1.4 4.1 3.6 5.3L7 19l3.9-2.4c.4 0 .7.1 1.1.1 4.6 0 8-2.9 8-6.4S16.6 4 12 4Z"/></svg>',
    sms: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 5h16v11H8l-4 4V5Z"/><path d="M8 9h8M8 12h5"/></svg>',
    mail: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/></svg>',
    copy: '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a1 1 0 0 1 1-1h10"/></svg>',
  };
  let box = null;
  function ensure() {
    if (box) return box;
    box = document.createElement('div');
    box.id = 'gmShare';
    box.className = 'gm-share';
    box.innerHTML =
      '<div class="gm-share-bg"></div>' +
      '<div class="gm-share-box" role="dialog" aria-modal="true" aria-labelledby="gmShareTitle">' +
      '<div class="gm-share-hd"><b id="gmShareTitle">링크 공유</b><button type="button" class="gm-share-x" aria-label="닫기">✕</button></div>' +
      '<p class="gm-share-sub"></p>' +
      '<div class="gm-share-url"><input type="text" readonly aria-label="공유할 주소"><button type="button" class="gm-share-copy">' + ICON.copy + '복사</button></div>' +
      '<div class="gm-share-btns">' +
      '<button type="button" class="gm-share-kakao"><span>' + ICON.kakao + '</span>카카오톡</button>' +
      '<a class="gm-share-sms"><span>' + ICON.sms + '</span>문자</a>' +
      '<a class="gm-share-mail"><span>' + ICON.mail + '</span>이메일</a>' +
      '</div>' +
      '<p class="gm-share-tip"></p>' +
      '</div>';
    document.body.appendChild(box);
    const close = () => box.classList.remove('open');
    box.querySelector('.gm-share-bg').addEventListener('click', close);
    box.querySelector('.gm-share-x').addEventListener('click', close);
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') close(); });
    box.querySelector('.gm-share-copy').addEventListener('click', async function () {
      const input = box.querySelector('input');
      let ok = false;
      try { await navigator.clipboard.writeText(input.value); ok = true; } catch (e) {}
      if (!ok) { try { input.focus(); input.select(); ok = document.execCommand('copy'); } catch (e) {} }
      const btn = this;
      btn.classList.toggle('done', ok);
      btn.lastChild.textContent = ok ? '복사됨' : '복사 실패';
      setTimeout(() => { btn.classList.remove('done'); btn.lastChild.textContent = '복사'; }, 1600);
    });
    box.querySelector('.gm-share-kakao').addEventListener('click', function () { sendKakao(box._title, box._url, this); });
    return box;
  }
  /* 카카오 SDK 를 처음 누를 때만 불러와서 텍스트 메시지로 보낸다 */
  let sdkLoading = null;
  function loadKakao() {
    if (window.Kakao && window.Kakao.isInitialized && window.Kakao.isInitialized()) return Promise.resolve();
    if (!sdkLoading) {
      sdkLoading = new Promise((ok, fail) => {
        const sc = document.createElement('script');
        sc.src = KAKAO_SDK; sc.async = true;
        sc.onload = () => { try { window.Kakao.init(KAKAO_JS_KEY); ok(); } catch (e) { fail(e); } };
        sc.onerror = () => fail(new Error('sdk'));
        document.head.appendChild(sc);
      });
    }
    return sdkLoading;
  }
  async function sendKakao(title, url, btn) {
    btn.disabled = true;
    try {
      await loadKakao();
      window.Kakao.Share.sendDefault({ objectType: 'text', text: title, link: { mobileWebUrl: url, webUrl: url } });
    } catch (e) {
      box.querySelector('.gm-share-tip').textContent = '카카오톡 공유가 열리지 않았어요. 주소를 복사해 대화창에 붙여 넣어 주세요';
    }
    btn.disabled = false;
  }
  function openDialog(title, url) {
    const b = ensure();
    b.querySelector('.gm-share-sub').textContent = title;
    b.querySelector('input').value = url;
    b._title = title; b._url = url;
    const hasKakao = !!KAKAO_JS_KEY;
    b.querySelector('.gm-share-kakao').style.display = hasKakao ? '' : 'none';
    b.querySelector('.gm-share-tip').textContent = hasKakao
      ? '카카오톡 안에서 열었다면 오른쪽 위 ⋮ 메뉴의 ‘공유하기’로도 보낼 수 있어요'
      : '카카오톡으로 보내려면 ‘복사’한 주소를 대화창에 붙여 넣거나, 오른쪽 위 ⋮ 메뉴의 ‘공유하기’를 눌러 주세요';
    b.querySelector('.gm-share-sms').href = 'sms:?&body=' + enc(title + ' ' + url);
    b.querySelector('.gm-share-mail').href = 'mailto:?subject=' + enc(title) + '&body=' + enc(url);
    b.classList.add('open');
    b.querySelector('.gm-share-copy').focus();
  }
  /* 공유 시작: {title, url}. 기기 공유창 → 없거나 실패하면 페이지 안 공유창 */
  window.gmapShare = async function (o) {
    const url = (o && o.url) || location.href;
    const title = (o && o.title) || document.title;
    if (navigator.share && /^https?:/i.test(url)) {
      try { await navigator.share({ title: title, url: url }); return; }
      catch (e) { if (e && e.name === 'AbortError') return; }
    }
    openDialog(title, url);
  };
})();
