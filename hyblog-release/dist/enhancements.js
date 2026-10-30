// Browser-only media and Naver handoff. Originals never enter the AI queue.
function normalizeState(s){
 s.visitTime=typeof s.visitTime==='string'?s.visitTime:'';s.alignment=s.alignment==='left'?'left':'center';s.reviewLinks=typeof s.reviewLinks==='string'?s.reviewLinks:'';s.useReviews=s.useReviews!==false;
 const imageOk=p=>p&&typeof p.id==='string'&&/^[a-zA-Z0-9_-]{1,80}$/.test(p.id)&&typeof p.data==='string'&&/^data:image\/(jpeg|png|webp);base64,[A-Za-z0-9+/=]+$/.test(p.data)&&p.data.length<2500000;
 s.receipts=Array.isArray(s.receipts)?s.receipts.filter(imageOk).slice(0,3):[];
 for(const p of s.photos){if(p.gifData&&!safeGif(p.gifData))delete p.gifData;if(p.videoData&&!/^data:video\/(mp4|webm|quicktime);base64,[A-Za-z0-9+/=]+$/.test(p.videoData))delete p.videoData;p.clipStart=Number.isFinite(Number(p.clipStart))?Number(p.clipStart):0;p.duration=Number.isFinite(Number(p.duration))?Number(p.duration):0;}
 return s;
}
function naverMapUrl(){return 'https://map.naver.com/p/search/'+encodeURIComponent([state.place,state.area].filter(Boolean).join(' '));}
function mapButton(){return `<button class="button map-button" data-action="map">${icon('pin')}네이버 지도 검색 ↗</button>`;}
function mediaView(p,cls='photo-img'){
 if(safeGif(p.gifData))return `<img class="${cls}" data-animated="true" style="max-width:min(100%,480px);max-height:400px;width:auto;height:auto;object-fit:contain" src="${p.gifData}" alt="${esc(p.note||p.name)}">`;
 if(p.kind==='video'&&/^data:video\/(mp4|webm|quicktime);base64,[A-Za-z0-9+/=]+$/.test(p.videoData||''))return `<video class="${cls}" src="${p.videoData}" poster="${p.data}" controls playsinline preload="metadata"></video>`;
 return `<img class="${cls}" src="${safeGif(p.gifData)?p.gifData:p.data}" alt="${esc(p.note||p.name)}">`;
}
function safeGif(s){return typeof s==='string'&&/^data:image\/gif;base64,R0lGOD[A-Za-z0-9+/=]+$/.test(s);}
function mediaTools(p){return p.kind==='video'?`<div class="media-tools"><strong>${currentGif(p)?'✓ 움짤 준비 완료':'움짤 변환 필요'}</strong><span>${currentGif(p)?`${(p.gifSeconds||Math.min(4,p.duration)).toFixed(1)}초 반복 · 네이버에는 이 움짤을 넣어요`:'초안 만들기 전에 자동으로 변환해요'}</span><label>움짤 시작(초)<input type="number" min="0" max="${Math.max(0,p.duration-.1)}" step="0.1" data-clip-start="${p.id}" value="${p.clipStart||0}" aria-label="움짤 시작 시간" ${photoBusy||jobId||submitting?'disabled':''}></label><button class="button" data-action="gif" data-id="${p.id}" ${photoBusy||jobId||submitting?'disabled':''}>${safeGif(p.gifData)?'이 구간으로 다시 만들기':'움짤 다시 시도'}</button>${safeGif(p.gifData)?`<button class="muted-link" data-action="media-download" data-id="${p.id}">움짤 다운로드</button>`:''}<details><summary>원본 동영상 보기 · ${Math.round(p.duration)}초</summary><video src="${p.videoData}" controls playsinline preload="none"></video></details></div>`:safeGif(p.gifData)?'<span class="media-label">반복 재생 움짤 GIF</span>':'';}

function receiptPanel(){const r=state.draft?.receipt;return `<section class="card receipt-card"><div class="card-heading"><h2>영수증으로 기억 보태기</h2><span class="optional">선택 · 최대 3장</span></div><p class="hint">영수증 사진은 글에 들어가지 않아요. 초안을 만들 때 메뉴·수량·금액을 읽고, 확인한 내용만 다음 초안에 반영할 수 있어요.</p><button class="button" data-action="receipt-upload">+ 영수증 사진</button><input id="receipt-picker" type="file" accept="image/*" multiple hidden><div class="receipts">${(state.receipts||[]).map(p=>`<figure><img src="${p.data}" alt="영수증 ${esc(p.name)}"><button class="muted-link" data-action="receipt-remove" data-id="${p.id}">삭제</button></figure>`).join('')}</div><p class="hint">카드·승인번호와 연락처는 가리고 올려주세요. 원본 이미지는 분석 시 Codex에 전달되며, 읽은 결과에는 메뉴와 결제 정보만 남깁니다.</p>${r&&state.receipts?.length?receiptResult(r):''}</section>`;}
function receiptResult(r){return `<div class="receipt-result"><h3>영수증에서 읽은 내용 · 확인 전</h3><p>${esc(r.merchant)} · ${esc(r.date)} ${esc(r.time)} 결제</p><label for="receipt-menu-review">메뉴 · 수량 · 금액 (수정 가능)</label><textarea id="receipt-menu-review">${esc((r.items||[]).map(i=>[i.name,i.quantity,i.amount?i.amount+'원':''].filter(Boolean).join(' · ')).join('\n'))}</textarea><label for="receipt-total-review">총 결제액 (원)</label><input id="receipt-total-review" value="${esc(r.total)}" inputmode="numeric"><p class="hint">결제 시각은 도착 시각과 달라요. 방문 시간은 직접 적어주세요. ${esc((r.warnings||[]).join(' '))}</p><button class="button" data-action="receipt-apply">확인한 메뉴·금액으로 새 초안 준비</button></div>`;}
function researchOptions(){return `<section class="card"><h2>같은 식당의 최근 후기 참고</h2><label class="check-line"><input type="checkbox" data-review-toggle ${state.useReviews!==false?'checked':''}>최근 6개월 원문에서 장점 찾아보기</label><p class="hint">같은 지점인지 확인한 후기를 참고해요. 다른 사람의 감상을 내 경험으로 바꾸지 않고, 외부 가격·영업시간·주차 조건은 가져오지 않아요.</p><label for="reviewLinks">참고할 후기 주소 <span class="optional">선택 · 최대 3개</span></label><textarea id="reviewLinks" data-field="reviewLinks" placeholder="네이버 블로그 또는 티스토리 글 주소를 한 줄씩">${esc(state.reviewLinks||'')}</textarea></section>`;}
function researchPanel(){const r=state.draft?.research;if(!r)return '';return `<section class="reference-panel"><h3>참고한 다른 방문자의 후기</h3><p>${esc(r.message)}</p>${(r.references||[]).map(s=>`<div class="reference"><a href="${safeWebUrl(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.title)} ↗</a><small>${esc(s.date)} · ${s.sponsored==='yes'?'협찬 표시 있음':s.sponsored==='no'?'직접 결제 명시':'협찬 여부 확인 안 됨'}</small><p>${esc(s.positivePoint)}</p></div>`).join('')}<p class="hint">후기는 작성 방향을 참고하는 자료예요. 본인이 겪은 맛과 분위기는 메모가 우선입니다.</p></section>`;}
function safeWebUrl(s){try{const u=new URL(s);return u.protocol==='https:'&&!u.username&&!u.password?esc(u.href):'#';}catch{return '#';}}
function alignmentControl(){return `<label class="alignment">글 정렬 <select id="article-alignment"><option value="center" ${state.alignment!=='left'?'selected':''}>가운데</option><option value="left" ${state.alignment==='left'?'selected':''}>왼쪽</option></select></label>`;}
const fileData=file=>new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=()=>reject(Error('파일을 읽지 못했어요.'));r.readAsDataURL(file);});
async function videoOpen(src){const v=document.createElement('video');v.muted=true;v.playsInline=true;v.preload='auto';await new Promise((resolve,reject)=>{const t=setTimeout(()=>reject(Error('동영상을 읽지 못했어요. H.264 MP4로 내보내 다시 넣어주세요.')),20000);v.onloadeddata=()=>{clearTimeout(t);resolve();};v.onerror=()=>{clearTimeout(t);reject(Error('이 브라우저에서 재생할 수 없어요. H.264 MP4 파일로 다시 넣어주세요.'));};v.src=src;});return v;}
async function videoSeek(v,time){if(Math.abs(v.currentTime-time)<.002&&v.readyState>=2)return;await new Promise((resolve,reject)=>{const t=setTimeout(()=>reject(Error('동영상 장면을 읽는 시간이 초과됐어요.')),10000);v.onseeked=()=>{clearTimeout(t);resolve();};v.currentTime=time;});}
function videoCanvas(v,width){const c=document.createElement('canvas'),scale=Math.min(1,width/Math.max(v.videoWidth,v.videoHeight));c.width=Math.max(1,Math.round(v.videoWidth*scale));c.height=Math.max(1,Math.round(v.videoHeight*scale));return c;}
async function prepareMedia(file){
 if(file.type.startsWith('video/')||/\.(mp4|mov|webm)$/i.test(file.name)){
  if(file.size>50*1024*1024)throw Error(`${file.name}: 동영상은 50MB 이하로 넣어주세요.`);
  if(state.photos.filter(p=>p.kind==='video').length>=4)throw Error('동영상은 한 글에 최대 4개까지 넣을 수 있어요.');
  const src=URL.createObjectURL(file);let v;
  try{v=await videoOpen(src);if(!Number.isFinite(v.duration)||v.duration>180)throw Error('3분 이하 영상으로 잘라서 넣어주세요.');await videoSeek(v,Math.min(.4,v.duration/2));const c=videoCanvas(v,1280);c.getContext('2d').drawImage(v,0,0,c.width,c.height);let videoData=await fileData(file);const mime=/\.mov$/i.test(file.name)?'quicktime':/\.webm$/i.test(file.name)?'webm':'mp4';videoData=videoData.replace(/^data:[^;]*;/,'data:video/'+mime+';');return {data:c.toDataURL('image/jpeg',.82),videoData,kind:'video',duration:v.duration,clipStart:0};}
  finally{if(v){v.removeAttribute('src');v.load();}URL.revokeObjectURL(src);}
 }
 if(!file.type.startsWith('image/'))throw Error(`${file.name}: 사진·GIF·동영상 파일을 선택해주세요.`);
 const data=await compressedImage(file);
 if(file.type==='image/gif'){if(file.size>12*1024*1024)throw Error('GIF는 12MB 이하로 넣어주세요.');return {data,gifData:await fileData(file),kind:'gif'};}
 return {data,kind:'image'};
}
async function addReceipts(files){if(jobId||submitting||photoBusy)return;const list=Array.from(files);if(!list.length)return;if((state.receipts||[]).length+list.length>3)return toast('영수증은 최대 3장까지 넣어주세요.');forkInput();state.receipts||=[];photoBusy=true;render();try{for(const f of list)state.receipts.push({id:crypto.randomUUID(),name:f.name,note:'비공개 영수증',data:await compressedImage(f)});}catch(e){error=e.message;}finally{photoBusy=false;await saveNow();render();}}
let mediaProgress='';
function mediaProgressView(){return `<div class="media-progress" role="status" aria-live="polite" ${photoBusy?'':'hidden'}><span class="media-spinner"></span><span id="media-progress-text">${esc(mediaProgress||'사진·움짤 준비 중')}</span></div>`;}
function updateMediaProgress(message){mediaProgress=message;const el=document.getElementById('media-progress-text');if(el)el.textContent=message;}
function currentGif(p){return safeGif(p.gifData)&&Math.abs((p.gifStart||0)-(Number(p.clipStart)||0))<.05;}
async function encodeVideoGif(p){
 if(!p.videoData)throw Error('원본 영상을 다시 넣어주세요.');let v;
 try{
  const {GIFEncoder,quantize,applyPalette}=await import('./gifenc.js');v=await videoOpen(p.videoData);
  const start=Math.max(0,Math.min(Math.max(0,v.duration-.1),Number(p.clipStart)||0));
  const c=videoCanvas(v,480),ctx=c.getContext('2d',{willReadFrequently:true}),gif=GIFEncoder();
  const length=Math.min(4,v.duration-start),frames=Math.max(2,Math.ceil(length*8));
  for(let i=0;i<frames;i++){
   updateMediaProgress(`${p.name||'동영상'} · 움짤 만드는 중 ${Math.round(i/frames*100)}%`);
   await videoSeek(v,Math.max(0,Math.min(v.duration-.03,start+i/8)));ctx.drawImage(v,0,0,c.width,c.height);
   const rgba=ctx.getImageData(0,0,c.width,c.height).data,palette=quantize(rgba,128);
   gif.writeFrame(applyPalette(rgba,palette),c.width,c.height,{palette,delay:125,repeat:0});
   await new Promise(r=>setTimeout(r,0));
  }
  gif.finish();const blob=new Blob([gif.bytes()],{type:'image/gif'});
  if(blob.size>12*1024*1024)throw Error('움짤이 너무 커요. 시작 장면을 바꿔 다시 만들어주세요.');
  p.gifData=await fileData(blob);p.gifStart=start;p.clipStart=start;p.gifSeconds=length;p.gifFrames=frames;
  updateMediaProgress('움짤 완성 · 움직이는 미리보기를 확인해주세요');
 }finally{if(v){v.removeAttribute('src');v.load();}}
}
async function createGif(id){
 if(jobId||submitting||photoBusy)return;const p=state.photos.find(x=>x.id===id);if(!p?.videoData)return;
 photoBusy=true;error='';render();try{await encodeVideoGif(p);toast('새 구간으로 움짤을 만들었어요.');}catch(e){error=e.message;}finally{photoBusy=false;mediaProgress='';await saveNow();render();}
}
async function ensureGifs(){
 const pending=state.photos.filter(p=>p.kind==='video'&&!currentGif(p));if(!pending.length)return true;
 photoBusy=true;error='';render();let ok=true;
 try{for(const p of pending){await encodeVideoGif(p);if(!await saveNow())throw Error('기기 저장 공간을 확인해주세요.');}}
 catch(e){ok=false;error=e.message+' 움짤 준비 후 다시 눌러주세요.';}
 finally{photoBusy=false;mediaProgress='';await saveNow();render();}return ok;
}
function paymentToggle(){return `<label class="check-line payment-toggle"><input type="checkbox" data-payment="self" ${state.sponsorship==='self'?'checked':''} ${jobId||submitting||photoBusy?'disabled':''}>내돈내산</label>`;}
function paymentFields(){return `<div class="payment-card"><h3>이 글의 비용 표시</h3>${paymentToggle()}<p class="hint">직접 결제한 방문이라면 체크해주세요. 글 상단에 내돈내산 문구가 들어가요.</p><label class="check-line provided-toggle"><input type="checkbox" data-payment="provided" ${state.sponsorship==='provided'?'checked':''} ${jobId||submitting||photoBusy?'disabled':''}>식사 제공 · 협찬을 받았어요</label></div>`;}
function disclosureMarkup(){const text=MangnaComposition.disclosure(state.sponsorship);return text?`<p class="payment-disclosure ${state.sponsorship==='self'?'self-paid':''}">${esc(text)}</p>`:'';}
function sectionPreview(s){return MangnaComposition.beats(s).map(b=>`<div class="article-images">${b.photoIds.map(id=>{const p=state.photos.find(p=>p.id===id);return p?mediaView(p,'article-media'):'';}).join('')}</div>${b.body?`<div class="read-text">${esc(b.body)}</div>`:''}`).join('');}
document.addEventListener('change',e=>{
 if(e.target.dataset.payment){
  if(jobId||submitting||photoBusy)return;
  state.sponsorship=e.target.checked?e.target.dataset.payment:'unknown';
  if(state.draft?.naver)state.draft.naver={...state.draft.naver,status:'needs_attention',message:'비용 표시를 바꿨어요. 현재 초안을 다시 임시저장하면 네이버에도 반영돼요.'};
  scheduleSave();render();
 }
});

function mediaBytes(data){const b64=data.split(',')[1],raw=atob(b64),out=new Uint8Array(raw.length);for(let i=0;i<raw.length;i++)out[i]=raw.charCodeAt(i);return out;}
function mediaDownload(id){const p=state.photos.find(x=>x.id===id);if(!p)return;download((p.name.replace(/\.[^.]+$/,'')||'움짤')+'.gif',mediaBytes(p.gifData),'image/gif');}
function naverBody(includeImages=false){
 const d=state.draft,align=state.alignment==='left'?'left':'center';
 const para=t=>String(t||'').split(/\n\s*\n/).filter(Boolean).map(p=>`<p style="text-align:${align};font-size:16px;line-height:2;margin:24px 0">${esc(p).replace(/\n/g,'<br>')}</p>`).join('');
 let count=0;
 return `<div style="text-align:${align};font-family:sans-serif">${para(MangnaComposition.disclosure(state.sponsorship))}${para(d.intro)}${d.sections.map((s,i)=>`<h2 style="text-align:${align};font-size:20px;margin:40px 0 24px">${esc(s.heading)}</h2>${MangnaComposition.beats(s).map(b=>`${b.photoIds.map(id=>{const p=state.photos.find(x=>x.id===id);if(!p)return '';count++;return includeImages?mediaView(p,'export-media'):para('[사진 '+String(count).padStart(2,'0')+' · '+(p.note||p.name)+']');}).join('')}${para(b.body)}`).join('')}${stickerMarkup(i,d)}`).join('')}${para(d.closing)}${para(d.tags.map(x=>'#'+x.replace(/^#/,'' )).join(' '))}</div>`;
}

async function copyNaver(){const html=naverBody(false);try{await navigator.clipboard.write([new ClipboardItem({'text/html':new Blob([html],{type:'text/html'}),'text/plain':new Blob([plainText()],{type:'text/plain'})})]);toast('가운데 정렬과 줄바꿈을 복사했어요. 네이버 본문에 붙여넣어주세요.');}catch{await navigator.clipboard.writeText(plainText());toast('텍스트로 복사했어요. 네이버에서 가운데 정렬을 선택해주세요.');}}
function naverOptions(){return `<section class="card naver-options"><div class="card-heading"><h2>완성 후 네이버에 임시저장</h2></div><label class="check-line"><input type="checkbox" id="naver-auto" ${state.naverAutoSave!==false?'checked':''}>101507kim 블로그에 이어 쓰기</label><p class="hint">${connection.naverConnected?'PC 네이버 연결 켜짐 · 제목과 본문, 사진·움짤을 옮기고 저장해요.':'Edge가 닫혀 있어도 PC가 켜져 있으면 전송할 때 열어요.'} 발행은 직접 합니다. 동영상은 자동으로 만든 최대 4초 움짤을 옮겨요. 준비되지 않으면 알려드려요.</p></section>`;}
function naverResult(){const n=state.draft?.naver;if(!n)return '';return `<section class="naver-result ${n.status==='saved'?'success':''}" aria-label="네이버 저장 상태"><h3>${n.status==='saved'?'네이버 임시저장을 마쳤어요':n.status==='setup_required'?'네이버 PC 연결이 필요해요':'네이버 작성 화면을 확인해주세요'}</h3><p>${esc(/Cannot read|undefined|not a function/.test(n.message||'')?'네이버 화면의 버튼을 확인하지 못해 전송이 멈췄어요. 초안은 보관했으니 PC 작성 화면을 확인해주세요.':n.message)}</p>${n.status!=='saved'?attentionCard(n.attention||HyblogAttention.from(n.message,true)):""}${n.status==='saved'?`<p class="hint">101507kim · ${esc(n.title||state.draft.title)}<br>휴대폰에서는 같은 계정으로 로그인해주세요. 임시저장 목록이 열리면 위 제목을 선택하면 돼요.</p><button class="button naver-button" data-action="naver-open">네이버에서 수정하기 ↗</button>`:`<button class="button naver-button" data-action="naver-save" ${connection.ready?'':'disabled'}>현재 초안 네이버에 임시저장</button><p class="hint">연결 후 이 버튼을 누르면 AI로 다시 만들지 않고 현재 수정본을 옮깁니다.</p>`}</section>`;}
async function startNaverSave(){
 if(jobId||submitting||photoBusy||!state.draft)return;
 if(!siteRemote)return toast('네이버 연결은 kgeodata.com의 작업실에서 사용할 수 있어요.');
 if(!connection.ready)return toast('PC의 파블 연결을 켜주세요. Edge는 전송할 때 열어드려요.');
 document.querySelector('dialog')?.close();if(!await ensureGifs())return;error='';jobStarted=Date.now();jobAttention=null;state.pendingRequest={id:crypto.randomUUID(),startedAt:jobStarted,kind:'naver'};
 if(!await saveNow()){delete state.pendingRequest;return;}
 view='input';submitting=true;jobStage='현재 수정본을 네이버에 옮기고 있어요';render();focusProgress();startClock();await submitGeneration();
}
function naverDialog(){showDialog(`<h2>하연의 네이버에 임시저장</h2><p class="naver-owner">MANGNA MOMENT · <b>101507kim</b></p><p>${connection.naverConnected?'현재 수정한 제목·본문·사진을 PC의 네이버 편집기로 옮겨 임시저장해요.':'PC가 연결되어 있으면 Edge를 열고 아내 계정을 확인한 뒤 임시저장해요.'}</p><div class="toolbar-mini"><button class="button primary" data-action="naver-save" ${connection.ready?'':'disabled'}>현재 초안 네이버에 임시저장</button><button class="button" data-action="naver-open">네이버에서 수정하기 ↗</button><button class="button" data-action="naver-copy">본문 서식 복사</button><button class="button" data-action="naver-bundle">사진·움짤 묶음 내려받기</button><button class="button" data-action="naver-title">제목 복사</button></div><p class="hint">네이버는 같은 계정으로 로그인해야 해요. 휴대폰에서 임시저장 목록이 열리면 같은 제목을 선택해주세요. 영수증은 블로그에 올리지 않고, 발행은 직접 합니다.</p><button class="button" data-action="close-dialog">닫기</button>`);}
// Minimal ZIP STORE writer, UTF-8 filenames. No remote file upload or third-party CDN.
function zipStore(files){const enc=new TextEncoder(),chunks=[],central=[];let offset=0;const crc=bytes=>{let n=-1;for(const b of bytes){n^=b;for(let k=0;k<8;k++)n=(n>>>1)^((n&1)?0xedb88320:0);}return (n^-1)>>>0;};for(const f of files){const name=enc.encode(f.name),data=typeof f.data==='string'?enc.encode(f.data):f.data,checksum=crc(data),head=new Uint8Array(30+name.length),v=new DataView(head.buffer);v.setUint32(0,0x04034b50,true);v.setUint16(4,20,true);v.setUint16(6,0x800,true);v.setUint32(14,checksum,true);v.setUint32(18,data.length,true);v.setUint32(22,data.length,true);v.setUint16(26,name.length,true);head.set(name,30);const c=new Uint8Array(46+name.length),d=new DataView(c.buffer);d.setUint32(0,0x02014b50,true);d.setUint16(4,20,true);d.setUint16(6,20,true);d.setUint16(8,0x800,true);d.setUint32(16,checksum,true);d.setUint32(20,data.length,true);d.setUint32(24,data.length,true);d.setUint16(28,name.length,true);d.setUint32(42,offset,true);c.set(name,46);central.push(c);chunks.push(head,data);offset+=head.length+data.length;}const size=central.reduce((n,c)=>n+c.length,0),end=new Uint8Array(22),e=new DataView(end.buffer);e.setUint32(0,0x06054b50,true);e.setUint16(8,files.length,true);e.setUint16(10,files.length,true);e.setUint32(12,size,true);e.setUint32(16,offset,true);return new Blob([...chunks,...central,end],{type:'application/zip'});}
function downloadBundle(){const files=[],ordered=state.draft.sections.flatMap(s=>s.photoIds).map(id=>state.photos.find(p=>p.id===id)).filter(Boolean);ordered.forEach((p,i)=>{const n=String(i+1).padStart(2,'0');files.push({name:n+(safeGif(p.gifData)?'.gif':'.jpg'),data:mediaBytes(safeGif(p.gifData)?p.gifData:p.data)});if(p.videoData)files.push({name:n+'-original.'+(p.videoData.startsWith('data:video/quicktime')?'mov':p.videoData.startsWith('data:video/webm')?'webm':'mp4'),data:mediaBytes(p.videoData)});});files.push({name:'본문.html',data:'<!doctype html><meta charset="utf-8"><h1>'+esc(state.draft.title)+'</h1>'+naverBody(false)},{name:'작성안내.txt',data:'대상 블로그: 101507kim\n제목: '+state.draft.title+'\n\n본문의 [사진 NN] 위치에 같은 번호 사진/GIF를 올려주세요. 원본 영상은 동영상 추가 메뉴로 넣을 수 있습니다. 영수증은 포함되지 않습니다. 저장 후 임시저장 목록에서 확인하세요. 발행 전 내용을 직접 검토해주세요.'});download(filename()+'-네이버.zip',zipStore(files),'application/zip');}
document.addEventListener('input',e=>{if(e.target.dataset.clipStart){const p=state.photos.find(x=>x.id===e.target.dataset.clipStart);if(p){p.clipStart=Number(e.target.value);scheduleSave();const card=e.target.closest('.media-tools');const label=card?.querySelector('strong');if(label)label.textContent=currentGif(p)?'✓ 움짤 준비 완료':'시작 구간 변경 · 다시 만들기를 눌러주세요';}}});
document.addEventListener('change',e=>{if(e.target.id==='receipt-picker')addReceipts(e.target.files);if(e.target.dataset.reviewToggle!==undefined){if(jobId||photoBusy)return;forkInput();state.useReviews=e.target.checked;scheduleSave();}if(e.target.id==='article-alignment'){state.alignment=e.target.value;scheduleSave();render();}});
document.addEventListener('click',async e=>{const b=e.target.closest('[data-action]');if(!b||b.disabled)return;const a=b.dataset.action;try{
 if(a==='map'){if(!state.place.trim())return toast('식당 이름과 지점을 먼저 입력해주세요.');window.open(naverMapUrl(),'_blank','noopener,noreferrer');}
 if(a==='receipt-upload')$('#receipt-picker')?.click();
 if(['receipt-remove','receipt-apply','gif'].includes(a)&&(jobId||photoBusy||submitting))return;
 if(a==='receipt-remove'){forkInput();state.receipts=state.receipts.filter(p=>p.id!==b.dataset.id);scheduleSave();render();}
 if(a==='receipt-apply'){const menus=$('#receipt-menu-review').value,total=$('#receipt-total-review').value,date=state.draft.receipt.date;forkInput();state.menus=menus;state.facts+=(state.facts?'\n':'')+(total?'영수증 확인: '+(date||'방문 당일')+' 총 결제액 '+total.replace(/원/g,'')+'원. 현재 가격이 아닌 당시 결제 금액.':'');view='input';await saveNow();render();toast('확인한 메뉴와 금액을 넣었어요. 초안 만들기를 누르면 반영돼요.');}
 if(a==='gif')await createGif(b.dataset.id);
 if(a==='media-download')mediaDownload(b.dataset.id);
 if(a==='naver')naverDialog();
 if(a==='naver-save')await startNaverSave();
 if(a==='naver-copy')await copyNaver();
 if(a==='naver-open')window.open('https://blog.naver.com/101507kim?Redirect=Write&','_blank','noopener,noreferrer');
 if(a==='naver-title'){await navigator.clipboard.writeText(state.draft.title);toast('제목을 복사했어요.');}
 if(a==='naver-bundle')downloadBundle();
 }catch(err){toast(err.message||'작업을 마치지 못했어요.');}});

document.addEventListener('change',e=>{if(e.target.id==='naver-auto'){if(jobId||submitting)return;state.naverAutoSave=e.target.checked;scheduleSave();}});

function visitPicker(){return `<section class="visit-picker" aria-label="방문 날짜와 시간"><div class="visit-heading">${icon('clock')}<div><strong>언제 다녀오셨나요?</strong><span>날짜와 시간을 글에 반영해요.</span></div><span class="optional">선택</span></div><div class="visit-fields">${field('visitDate','방문 날짜','','date')}${field('visitTime','방문 시간','','time')}</div><p id="visit-preview" class="visit-preview" aria-live="polite">${visitPreview()}</p></section>`;}
function visitPreview(){const phrase=HanpyeonVisit.visitPhrase(state.visitDate,state.visitTime);return phrase?'“'+esc(phrase)+(state.visitTime&&HanpyeonVisit.daypart(state.visitTime)!=='점심 무렵'?'쯤':'')+'에 다녀왔어요.” 이렇게 글에 녹여요.':'날짜와 시간을 고르면 도입부에 자연스럽게 담아드려요.';}
function updateVisitPreview(){const el=$('#visit-preview');if(el)el.innerHTML=visitPreview();}
function inputActions(){return `<section class="input-actions" aria-label="입력 마치고 초안 만들기"><div><h2>입력 마치기</h2><p data-save-status role="status">${esc(savedMessage())}</p></div><div class="input-action-buttons"><button class="button" data-action="save-input">${icon('check')}임시저장</button><button class="button primary" id="generate" data-action="generate" ${jobId||submitting||photoBusy?'disabled':''}>${icon('spark')}${jobId||submitting?'초안 만드는 중':state.draft?'새 버전 초안 만들기':'초안 만들기'}${icon('arrow')}</button></div><div class="input-action-foot"><label class="check-line"><input id="input-stickers" type="checkbox" ${state.stickers!==false?'checked':''}>지정한 네이버 스티커 1~2개 넣기</label><button class="muted-link" data-action="download-json">작업 파일 받기</button></div></section>`;}
function stickerMarkup(index,draft=state.draft){const item=HanpyeonDecorations.plan(draft).find(s=>s.afterSection===index);return item?'<div class="native-sticker-note">네이버 스티커 · '+esc(item.label)+'<small>네이버 임시저장 때 이 위치에 추가돼요.</small></div>':'';}

document.addEventListener('change',e=>{if(['draft-stickers','input-stickers'].includes(e.target.id)){if(jobId||submitting)return;e.target.id==='draft-stickers'?state.draft.stickers=e.target.checked:state.stickers=e.target.checked;scheduleSave();if(e.target.id==='draft-stickers')render();}});

function confirmedLocation(){return state.locationConfirmed?HyblogLocation.validate({name:state.mapName,address:state.mapAddress,confirmed:true}):null;}
function locationFields(){return '<section class="location-fields"><h3>글 마지막에 넣을 위치 <span class="optional">선택</span></h3><p class="hint">네이버 지도에서 지점을 찾고 상호와 도로명 주소를 옮겨주세요. 같은 장소를 확인한 뒤 글 끝에 지도 카드를 넣어요.</p>'+field('mapName','지도에 표시된 상호','예: 더차돌')+field('mapAddress','도로명 주소','예: 경기 과천시 뒷골2로 5 1층')+'<label class="check-line"><input type="checkbox" id="location-confirmed" '+(state.locationConfirmed?'checked':'')+'>방문한 지점이 맞아요 · 글 끝에 위치 넣기</label></section>';}
function locationPreview(value){let place;try{place=HyblogLocation.validate(value);}catch{return '';}return place?'<div class="article-location"><span>방문한 곳</span><strong>'+esc(place.name)+'</strong><p>'+esc(place.address)+'</p><a href="https://map.naver.com/p/search/'+encodeURIComponent(place.name+' '+place.address)+'" target="_blank" rel="noopener noreferrer">네이버 지도에서 보기 ↗</a><small>네이버 임시저장 시 장소 카드로 넣어요.</small></div>':'';}
function attentionCard(a){if(!a)return '';return '<section class="attention-card" role="alert"><strong>'+esc(a.title)+'</strong><p>'+esc(a.action)+'</p>'+(a.notification?.accepted===true?'<small>개인 Telegram으로 확인 요청을 보냈어요.</small>':'')+(a.waiting?'<button class="button" data-action="retry-job">확인했어요 · 진행 다시 확인</button><small>이 버튼은 상태를 다시 확인해요. 네이버의 보안 확인은 열린 네이버 화면에서 완료해주세요.</small>':'')+'</section>';}
document.addEventListener('change',e=>{if(e.target.id==='location-confirmed'){if(jobId||submitting)return;try{if(e.target.checked)HyblogLocation.validate({name:state.mapName,address:state.mapAddress,confirmed:true});state.locationConfirmed=e.target.checked;scheduleSave();}catch(err){e.target.checked=false;state.locationConfirmed=false;toast(err.message);}}});
