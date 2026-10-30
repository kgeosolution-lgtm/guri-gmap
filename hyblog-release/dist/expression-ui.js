// Optional review-informed wording stays outside exports until the author chooses it.
let expressionSectionId='';
function expressionSections(){return (state.draft?.sections||[]).filter(s=>MangnaExpressions.forSection(state.draft,s).length);}
function expressionCards(section){
  return MangnaExpressions.forSection(state.draft,section).map(item=>{
    const added=section.body.includes(item.text),receipt=state.draft.expressionApplications?.[item.id];
    return `<div class="expression-card ${added?'is-added':''}"><span class="expression-label">${esc(item.label||item.menu)}</span><p class="expression-text">${esc(item.text)}</p><details class="expression-source"><summary>참고한 후기 보기</summary><p>${esc(item.evidence)}</p><a href="${esc(MangnaExpressions.sourceUrl(item.source.url))}" target="_blank" rel="noopener noreferrer">${esc(item.source.title)} ↗</a><small>${esc(item.source.date)} · ${item.source.sponsored==='yes'?'협찬 표시 있음':item.source.sponsored==='no'?'직접 결제 명시':'협찬 여부 미확인'}</small></details>${!added&&item.insertAfter&&section.body.includes(item.insertAfter)?`<details class="expression-source"><summary>바꿀 문단 미리 보기</summary><p class="expression-original">${esc(item.insertAfter)}</p></details>`:''}<div class="expression-buttons"><button class="button ${added?'':'soft'}" data-action="expression-add" data-id="${esc(item.id)}" data-target="${esc(section.id)}" ${added?'disabled':''}>${added?'본문에 넣었어요':'내 느낌과 같아요 · 덧붙이기'}</button>${!added&&item.insertAfter&&section.body.includes(item.insertAfter)?`<button class="muted-link" data-action="expression-replace" data-id="${esc(item.id)}" data-target="${esc(section.id)}">이 문단 대신 쓰기</button>`:''}${receipt?`<button class="muted-link" data-action="expression-undo" data-id="${esc(item.id)}" data-target="${esc(section.id)}">되돌리기</button>`:''}<button class="muted-link" data-action="expression-copy" data-id="${esc(item.id)}" data-target="${esc(section.id)}">표현 복사</button></div></div>`;
  }).join('');
}
function expressionSidebar(){
  if(preview)return '';
  const sections=expressionSections(),section=sections.find(s=>s.id===expressionSectionId)||sections[0];
  return `<div id="expression-sidebar" class="expression-sidebar"><div class="expression-panel-title"><span>내 글에 한 줄 더</span><h3>표현 참고</h3></div><p class="expression-help">후기를 참고해 새로 쓴 문장이에요.<br>내가 느낀 맛과 맞을 때만 골라주세요.</p>${section?`<label class="expression-menu-label">어느 메뉴를 다듬을까요?<select id="expression-menu">${sections.map(s=>`<option value="${esc(s.id)}" ${s.id===section.id?'selected':''}>${esc(s.heading)}</option>`).join('')}</select></label><div class="expression-choices">${expressionCards(section)}</div><p class="expression-footnote">선택하면 이 메뉴의 이야기 안에 추가돼요.<br>넣은 뒤에도 자유롭게 고칠 수 있어요.</p>`:'<p class="expression-empty">확인된 메뉴별 표현이 아직 없어요. 후기 참고를 켜고 새 초안을 만들면 여기에 표시됩니다.</p>'}</div>`;
}
function expressionInline(section){
  const items=MangnaExpressions.forSection(state.draft,section);
  return preview||!items.length?'':`<details class="expression-inline" data-expression-section="${esc(section.id)}"><summary>표현 참고 <span>${items.length}개</span></summary><p class="expression-help">후기를 참고해 새로 쓴 문장이에요. 내 느낌과 맞는 표현만 골라 이 메뉴의 이야기에 넣어보세요.</p><div class="expression-choices">${expressionCards(section)}</div></details>`;
}
function refreshExpressionPanels(){
  const side=document.getElementById('expression-sidebar');if(side)side.outerHTML=expressionSidebar();
  for(const wrapper of document.querySelectorAll('[data-expression-section]')){const section=state.draft?.sections.find(s=>s.id===wrapper.dataset.expressionSection);if(section)wrapper.querySelector('.expression-choices').innerHTML=expressionCards(section);}
}
document.addEventListener('focusin',e=>{if(e.target.dataset.section&&expressionSectionId!==e.target.dataset.section){expressionSectionId=e.target.dataset.section;const side=document.getElementById('expression-sidebar');if(side)side.outerHTML=expressionSidebar();}});
document.addEventListener('change',e=>{if(e.target.id==='expression-menu'){expressionSectionId=e.target.value;refreshExpressionPanels();}});
async function expressionAction(action,button){
  if(jobId||submitting)return toast('진행 중인 작업이 끝난 뒤 수정해주세요.');
  const d=state.draft,section=d?.sections.find(s=>s.id===button.dataset.target),item=section&&MangnaExpressions.forSection(d,section).find(s=>s.id===button.dataset.id);if(!item)return;
  if(action==='expression-copy'){await navigator.clipboard.writeText(item.text);toast('추천 표현을 복사했어요.');return;}
  d.expressionApplications??={};
  const result=action==='expression-add'?MangnaExpressions.insert(section.body,item):action==='expression-replace'?MangnaExpressions.replace(section.body,item):MangnaExpressions.revert(section.body,d.expressionApplications[item.id]);
  if(!result.changed){toast(action==='expression-add'?'이미 문단에 들어 있는 표현이에요.':'추가 후 문장을 고치셨네요. 본문에서 직접 지워주세요.');return;}
  section.body=result.body;expressionSectionId=section.id;
  if(action!=='expression-undo')d.expressionApplications[item.id]={inserted:result.inserted,suffix:result.suffix,original:result.original};else delete d.expressionApplications[item.id];
  for(const el of document.querySelectorAll('[data-prop="body"]'))if(el.dataset.section===section.id){el.value=section.body;grow(el);el.classList.add('expression-updated');el.scrollIntoView({behavior:'smooth',block:'center'});setTimeout(()=>el.classList.remove('expression-updated'),2200);}
  refreshExpressionPanels();scheduleSave();const count=document.getElementById('char-count');if(count)count.textContent=plainText().length.toLocaleString()+'자';
  toast(action==='expression-replace'?'이 표현으로 문단을 바꿨어요. 되돌리기로 원래 문단을 되돌릴 수 있어요.':action==='expression-add'?(result.placement==='context'?'이 메뉴의 이야기 안에 추가했어요. 자유롭게 다듬어주세요.':'문단을 수정하셔서 표현을 끝에 추가했어요. 위치를 확인해주세요.'):'추가한 표현을 되돌렸어요.');
}
