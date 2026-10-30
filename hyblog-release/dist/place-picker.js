// Public Naver search results; selection is explicit and scoped to this draft/query.
let placeSearch={owner:null,query:'',busy:false,items:[],error:'',searched:false,request:0};
function locationFields(){
 const relevant=placeSearch.owner===state.id, search=relevant?placeSearch:{}, selected=state.locationConfirmed&&state.mapName&&state.mapAddress;
 return `<section class="location-fields" id="location-picker"><h3 class="place-result-title">${selected?'선택한 지점':search.busy?'지점 검색 중':search.items?.length?'방문한 지점을 선택해주세요':'검색한 지점이 여기에 표시돼요'}</h3>
 <div class="place-search-status" role="status">${search.busy?'<span class="spinner"></span> 네이버에서 지점을 찾고 있어요…':search.error?esc(search.error):search.searched&&!search.items?.length?'검색 결과가 없어요. 식당 이름에 동네를 붙여 다시 찾아주세요.':''}</div>
 ${search.items?.length?`<ul class="place-results">${search.items.map((p,i)=>`<li><button type="button" class="place-result" data-action="place-select" data-index="${i}" ${jobId||submitting?'disabled':''}><span><strong>${esc(p.name)}</strong><small>${esc(p.address)}</small></span><span class="place-select-label">이 장소 선택</span></button><a href="https://map.naver.com/p/entry/place/${esc(p.placeId)}" target="_blank" rel="noopener noreferrer" aria-label="${esc(p.name)} 지도 확인">지도 ↗</a></li>`).join('')}</ul>`:''}
 ${selected?`<div class="selected-place"><span class="selected-check">✓ 이 지점으로 글을 작성해요</span><strong>${esc(state.mapName)}</strong><span>${esc(state.mapAddress)}</span><div><a href="${/^\d+$/.test(state.mapPlaceId||'')?'https://map.naver.com/p/entry/place/'+state.mapPlaceId:naverMapUrl()}" target="_blank" rel="noopener noreferrer">지도에서 확인 ↗</a><button type="button" class="muted-link" data-action="place-clear">선택 해제</button></div></div>`:''}
 <details class="place-manual"><summary>검색에서 못 찾았나요? 직접 입력하기</summary>${field('mapName','지도에 표시된 상호','예: 더차돌')}${field('mapAddress','도로명 주소','예: 경기 과천시 뒷골2로 5 1층')}<label class="check-line"><input type="checkbox" id="location-confirmed" ${state.locationConfirmed?'checked':''} ${jobId||submitting?'disabled':''}>방문한 지점이 맞아요 · 글 끝에 위치 넣기</label></details></section>`;
}
function refreshPlacePicker(){const el=document.getElementById('location-picker');if(el)el.outerHTML=locationFields();}
async function searchPlaces(){
 if(jobId||submitting)return;
 const query=state.place.trim();
 if(query.length<2)return toast('식당 이름에 지역이나 지점을 함께 입력해주세요.');
 const request=placeSearch.request+1,owner=state.id;
 placeSearch={owner,query,request,busy:true,items:[],error:'',searched:true};refreshPlacePicker();
 try{
  const response=await apiFetch('/api/places/search',{method:'POST',headers:{'Content-Type':'application/json','X-Meal-Note':'1'},body:JSON.stringify({query}),signal:AbortSignal.timeout(12000)});
  const result=await response.json();if(!response.ok)throw Error(result.error||'검색을 마치지 못했어요.');
  if(request!==placeSearch.request||owner!==state.id||query!==state.place.trim())return;
  placeSearch.items=(result.places||[]).filter(p=>/^\d+$/.test(p.placeId)&&typeof p.name==='string'&&typeof p.address==='string').slice(0,6);
 }catch(e){if(request===placeSearch.request&&owner===state.id)placeSearch.error=e.name==='TimeoutError'?'검색 연결이 지연돼요. 잠시 후 다시 눌러주세요.':e.message;}
 finally{if(request===placeSearch.request){placeSearch.busy=false;refreshPlacePicker();}}
}
function invalidatePlace(field){
 if(['place','area'].includes(field)){placeSearch={owner:state.id,query:'',busy:false,items:[],error:'',searched:false,request:placeSearch.request+1};}
 if(['place','mapName','mapAddress'].includes(field)){state.locationConfirmed=false;delete state.mapPlaceId;}
 // Keep the manual address field and its selection alive while the user types.
 if(['place','area'].includes(field))refreshPlacePicker();
 else if(['mapName','mapAddress'].includes(field)){document.querySelector('.selected-place')?.remove();const check=document.getElementById('location-confirmed');if(check)check.checked=false;}
}
document.addEventListener('keydown',e=>{if(e.key==='Enter'&&['place','area'].includes(e.target.id)){e.preventDefault();searchPlaces();}});
document.addEventListener('click',e=>{
 const button=e.target.closest('[data-action]');if(!button||button.disabled||jobId||submitting)return;
 if(button.dataset.action==='place-select'){
  if(placeSearch.owner!==state.id)return;
  const p=placeSearch.items[Number(button.dataset.index)];if(!p)return;
  forkInput();state.mapName=p.name;state.mapAddress=p.address;state.mapPlaceId=p.placeId;state.locationConfirmed=true;state.area='';
  // Preserve the user's branch wording; map identity comes from the chosen card.
  placeSearch={...placeSearch,owner:state.id,items:[],searched:false};scheduleSave();refreshPlacePicker();toast('상호와 주소를 담았어요. 글 마지막에도 이 위치를 넣어요.');
 }
 if(button.dataset.action==='place-clear'){forkInput();state.locationConfirmed=false;delete state.mapPlaceId;scheduleSave();refreshPlacePicker();}
});
