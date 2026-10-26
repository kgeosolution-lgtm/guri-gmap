'use strict';
const $=s=>document.querySelector(s),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const icons={bookmark:'<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z"/></svg>',link:'<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m10 13 4-4M8 15l-2 2a4 4 0 0 1-6-6l4-4m12 2 2-2a4 4 0 0 0-6-6l-2 2" transform="translate(2 2)"/></svg>',read:'<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M3 4h7l2 2 2-2h7v15h-7l-2 2-2-2H3zM12 6v15"/></svg>'};
const symbols={'레시피':'♨','장소':'⌖','생활':'✳','제품':'◇','지식':'✧','기타':'⌁'},cats=Object.keys(symbols);
const categoryLabels={'전체':'전체 보물','레시피':'맛있는 레시피','장소':'가고 싶은 곳','생활':'생활 꿀팁','제품':'위시리스트','지식':'알아둘 것','기타':'그 외의 발견'};
let items=[],category='전체',query='',favoritesOnly=false,sort='newest',homeScroll=0,toastTimer;
function readLocal(k,fallback){try{return JSON.parse(localStorage.getItem(k))??fallback;}catch{return fallback;}}
const mobileQuery=matchMedia('(max-width:720px)');
const favorites=new Set(readLocal('kong:favorites',[]));
function saveLocal(k,v){try{localStorage.setItem(k,JSON.stringify(v));}catch{toast('이 브라우저에서는 변경 사항이 임시로만 유지돼요.');}}
function toast(text){$('#toast').textContent=text;$('#toast').classList.add('visible');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').classList.remove('visible'),2600);}
function date(s){return new Date(s).toLocaleDateString('ko-KR',{year:'numeric',month:'2-digit',day:'2-digit'});}
function imageURL(item){return typeof item.image==='string'&&new RegExp('^images/'+item.id+'\\.jpg$').test(item.image)?item.image:null;}
function sourceURL(item){try{const u=new URL(item.source);return u.protocol==='https:'&&['www.instagram.com','instagram.com','m.instagram.com'].includes(u.hostname)&&!u.username&&!u.password?u.href:null;}catch{return null;}}
function cover(item,eager=false){const url=imageURL(item);return url?`<img src="${esc(url)}" alt="${esc(item.title)} 원본 대표 화면" loading="${eager?'eager':'lazy'}">`:`<div class="cover-fallback category-${esc(item.category)}"><span class="cover-symbol" aria-hidden="true">${symbols[item.category]||'⌁'}</span><small>${item.isRecipe?'RECIPE NOTE':'COLLECTION NOTE'}</small></div>`;}
function tags(item){return (item.tags||[]).slice(0,3).map(t=>`<span class="tag">${esc(t)}</span>`).join('');}
function savedButton(item,detail=false){const saved=favorites.has(item.id);return `<button class="${detail?'action-button':'card-save'}${saved?' saved':''}" data-save="${item.id}" aria-pressed="${saved}" aria-label="${esc(item.title)} 즐겨찾기 ${saved?'해제':'추가'}">${icons.bookmark}${detail?'<span>즐겨찾기</span>':''}</button>`;}
function renderFeature(){if(mobileQuery.matches){$('#featured').innerHTML='';document.querySelector('.hero-charm')?.remove();return;}if(!document.querySelector('.hero-charm')){const charm=document.createElement('img');charm.className='hero-charm';charm.src='./brand/hayeon-charms.png';charm.alt='';charm.setAttribute('aria-hidden','true');document.querySelector('.intro').prepend(charm);}const item=items.find(i=>imageURL(i))||items[0];if(!item)return;$('#featured').innerHTML=`<a class="feature-card" href="#item=${item.id}">${cover(item,true)}<span class="feature-label">NEW TREASURE ♡</span><div class="feature-copy"><small>${esc(item.category)} · HAYEON’S PICK</small><h2>${esc(item.title)}</h2><span class="feature-arrow" aria-hidden="true">↗</span></div></a>`;}
function renderFilters(){const all=['전체',...cats];$('#filters').innerHTML=all.map(c=>`<button class="filter-chip${category===c?' active':''}" data-category="${c}" aria-pressed="${category===c}">${categoryLabels[c]}<span>${c==='전체'?items.length:items.filter(i=>i.category===c).length}</span></button>`).join('')+`<button class="filter-chip${favoritesOnly?' active':''}" data-favorites aria-pressed="${favoritesOnly}">즐겨찾기<span>${items.filter(i=>favorites.has(i.id)).length}</span></button>`;}
function renderList(){
 renderFilters();$('#total-count').textContent=items.length;$('#nav-fav-count').textContent=items.filter(i=>favorites.has(i.id)).length;
 const words=query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
 const shown=items.filter(i=>(category==='전체'||i.category===category)&&(!favoritesOnly||favorites.has(i.id))&&words.every(w=>JSON.stringify([i.title,i.summary,i.tags,i.ingredients,i.steps,i.sections]).toLocaleLowerCase().includes(w)));
 shown.sort((a,b)=>sort==='title'?a.title.localeCompare(b.title,'ko'):sort==='oldest'?a.createdAt.localeCompare(b.createdAt):b.createdAt.localeCompare(a.createdAt));
 $('#cards').innerHTML=shown.map((i,index)=>`<article class="card">${mobileQuery.matches?'':`<a class="card-cover" href="#item=${i.id}" aria-label="${esc(i.title)} 상세 보기">${cover(i)}<span class="card-type">${esc(i.category)}</span></a>`}${savedButton(i)}<div class="card-info"><div class="card-origin"><span class="card-index">${String(index+1).padStart(2,'0')}</span><span class="card-kind">${esc(i.category)}</span><span class="source-label">${i.source?'INSTAGRAM':'보내둔 기록'}</span><span class="origin-dot"></span><span class="processed-label">정리 완료</span>${i.isRecipe&&!i.steps?.length?'<span class="incomplete">내용 일부</span>':''}</div><h3><a href="#item=${i.id}">${esc(i.title)}</a></h3><p class="card-summary">${esc(i.summary)}</p><div class="card-bottom"><div class="tags">${tags(i)}</div><time datetime="${esc(i.createdAt)}">${date(i.createdAt)}</time></div></div></article>`).join('');
 $('#cards').setAttribute('aria-busy','false');$('#empty-state').hidden=shown.length>0;
 $('#empty-state h3').textContent=items.length?'찾는 정보가 아직 없어요.':'첫 번째 발견을 담아보세요.';
 $('#empty-state p').textContent=items.length?'다른 키워드나 분류로 다시 찾아보세요. 즐겨찾기는 이 브라우저에 저장돼요.':'텔레그램으로 자료를 보내면 정리가 끝난 뒤 이곳에 쌓입니다.';
 $('#result-label').textContent=(favoritesOnly?'이 브라우저의 즐겨찾기 · ':'')+(query?'“'+query+'” 검색 · ':'')+shown.length+'개의 발견';
 $('#clear-filter').hidden=!query&&category==='전체'&&!favoritesOnly;
}
function section(title,body){return `<section class="detail-section"><div class="section-heading"><h2>${title}</h2></div>${body}</section>`;}
function detail(item){
 const checks=readLocal('kong:checked:'+item.id,[]),source=sourceURL(item);
 const ingredients=item.ingredients?.length?`<section class="detail-section"><div class="section-heading"><h2>준비할 재료</h2><small>준비한 재료를 체크해 보세요</small></div><div class="ingredients">${item.ingredients.map((x,n)=>`<label class="ingredient" title="${esc(x.evidence||'')}"><input type="checkbox" data-ingredient="${n}" ${checks.includes(n)?'checked':''}><span>${esc(x.name)}</span><strong>${esc(x.amount)}</strong></label>`).join('')}</div></section>`:'';
 const steps=item.steps?.length?section(item.isRecipe?'만드는 순서':'따라 해보기',`<ol class="steps">${item.steps.map((s,n)=>`<li class="step"><span class="step-number">${String(n+1).padStart(2,'0')}</span><p>${esc(s)}</p></li>`).join('')}</ol>`):item.isRecipe?section('만드는 순서','<p class="detail-missing">보내주신 자료에서 조리 순서가 확인되지 않았어요.<br>확인된 재료만 기록했습니다.</p>'):'';
 const other=(item.sections||[]).map(s=>section(esc(s.heading),`<div class="content-section"><ul>${s.items.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div>`)).join('');
 const tips=item.tips?.length?section('기억해 두면 좋은 것',`<div class="tip-box"><strong>원본에 담긴 팁</strong><ul>${item.tips.map(t=>`<li>${esc(t)}</li>`).join('')}</ul></div>`):'';
 const media=mobileQuery.matches&&imageURL(item)?`<div class="mobile-image"><div class="detail-cover">${cover(item,true)}</div></div>`:'';
 const uncertain=item.uncertain?.length?`<details class="uncertain-box"><summary>읽기 전에 확인해 주세요 · ${item.uncertain.length}가지</summary><ul>${item.uncertain.map(t=>`<li>${esc(t)}</li>`).join('')}</ul></details>`:'';
 $('#detail-view').innerHTML=`<div class="detail-nav"><a class="back-button" href="#collection">← 보관함으로</a><div class="detail-actions">${savedButton(item,true)}<button class="action-button" id="copy-link" aria-label="이 정보 링크 복사">${icons.link}<span>링크 복사</span></button><button class="action-button" id="reading-toggle" aria-label="크게 읽기 전환" aria-pressed="${document.body.classList.contains('reading-mode')}">${icons.read}<span>크게 읽기</span></button></div></div><div class="detail-layout">${mobileQuery.matches?'':`<aside class="detail-aside"><div class="detail-cover">${cover(item,true)}</div><div class="source-panel"><span class="eyebrow">FROM THE ORIGINAL</span><strong>${source?'인스타그램에서 발견했어요':'텔레그램에 보내둔 기록'}</strong><p>자료에서 확인한 내용을 읽기 좋게 정리했어요. 확인이 필요한 부분은 아래에 따로 표시했어요.</p>${source?`<a href="${esc(source)}" target="_blank" rel="noopener noreferrer">원본 보러 가기 <span>↗</span></a>`:''}</div></aside>`}<article>${media}<div class="detail-title"><span class="eyebrow">${esc(item.category)} · MY COLLECTION</span><h1>${esc(item.title)}</h1><p>${esc(item.summary)}</p><div class="detail-meta"><time datetime="${esc(item.createdAt)}">${date(item.createdAt)} 담음</time>${source?`<a href="${esc(source)}" target="_blank" rel="noopener noreferrer">원본 보기 ↗</a>`:''}<div class="tags">${tags(item)}</div></div></div>${ingredients}${steps}${other}${tips}${uncertain}<p class="reading-note">원본에 없는 수치나 내용을 추측해 채우지 않았어요.<br>즐겨찾기와 재료 체크는 현재 브라우저에 저장됩니다.</p></article></div>`;
 $('#copy-link').onclick=async()=>{try{await navigator.clipboard.writeText(location.href);toast('이 정보의 링크를 복사했어요.');}catch{toast('주소창의 링크를 복사해 주세요.');}};
 $('#reading-toggle').onclick=()=>{const active=document.body.classList.toggle('reading-mode');$('#reading-toggle').setAttribute('aria-pressed',active);toast(active?'큰 글씨로 편하게 읽어보세요.':'기본 화면으로 돌아왔어요.');};
 $('#detail-view').querySelectorAll('[data-ingredient]').forEach(el=>el.onchange=()=>saveLocal('kong:checked:'+item.id,[...$('#detail-view').querySelectorAll('[data-ingredient]:checked')].map(x=>Number(x.dataset.ingredient))));
}
function route(){
 const match=/^#item=([a-f0-9]{24})$/.exec(location.hash),showDetail=!!match;
 if(showDetail){if(!$('#home-view').hidden)homeScroll=scrollY;$('#home-view').hidden=true;$('#detail-view').hidden=false;const item=items.find(i=>i.id===match[1]);if(item){detail(item);document.title=item.title+' — 하연스타의 보물창고';}else{$('#detail-view').innerHTML='<a class="back-button" href="#collection">← 보관함으로</a><div class="empty-state"><h1>이 기록을 찾지 못했어요.</h1><p>보관함에서 다른 발견을 찾아보세요.</p></div>';document.title='기록을 찾지 못했어요 — 하연스타의 보물창고';}scrollTo(0,0);$('#detail-view').focus({preventScroll:true});}
 else{const wasDetail=!$('#detail-view').hidden;$('#detail-view').hidden=true;$('#home-view').hidden=false;document.body.classList.remove('reading-mode');document.title='하연스타의 보물창고 — 반짝이는 발견을 모아두는 곳';if(wasDetail)requestAnimationFrame(()=>scrollTo(0,homeScroll));else if(location.hash==='#collection')requestAnimationFrame(()=>$('#collection').scrollIntoView());}
}
async function load(){
 $('#error-state').hidden=true;$('#cards').setAttribute('aria-busy','true');
 try{const r=await fetch('./data/library.json',{cache:'no-cache'});if(!r.ok)throw Error();const data=await r.json();if(data.version!==1||!Array.isArray(data.items))throw Error();items=data.items.filter(i=>/^[a-f0-9]{24}$/.test(i.id)&&typeof i.title==='string');renderFeature();renderList();$('#sync-time').textContent=data.updatedAt?'마지막 담은 날 '+date(data.updatedAt):'';route();}
 catch{$('#error-state').hidden=false;$('#cards').setAttribute('aria-busy','false');$('#result-label').textContent='연결 상태를 확인해 주세요.';}
}
document.addEventListener('click',e=>{
 const save=e.target.closest('[data-save]');if(save){const id=save.dataset.save;favorites.has(id)?favorites.delete(id):favorites.add(id);saveLocal('kong:favorites',[...favorites]);renderList();if(!$('#detail-view').hidden){const item=items.find(i=>location.hash==='#item='+i.id);if(item)detail(item);}toast(favorites.has(id)?'이 브라우저의 즐겨찾기에 담았어요.':'즐겨찾기에서 꺼냈어요.');}
 const chip=e.target.closest('[data-category]');if(chip){category=chip.dataset.category;renderList();}
 if(e.target.closest('[data-favorites]')){favoritesOnly=!favoritesOnly;renderList();}
});
$('#nav-favorites').onclick=()=>{favoritesOnly=true;category='전체';renderList();location.hash='collection';};
$('#search').oninput=e=>{query=e.target.value;renderList();};$('#sort').onchange=e=>{sort=e.target.value;renderList();};
$('#clear-filter').onclick=()=>{category='전체';query='';favoritesOnly=false;$('#search').value='';renderList();};$('#retry').onclick=load;
document.addEventListener('keydown',e=>{if(e.key==='/'&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)&&$('#detail-view').hidden){e.preventDefault();$('#search').focus();}});
mobileQuery.addEventListener('change',()=>{renderFeature();renderList();const item=items.find(i=>location.hash==='#item='+i.id);if(item)detail(item);});
window.addEventListener('hashchange',route);load();
