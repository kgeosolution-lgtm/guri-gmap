// Read-only receipt recovery: a lost response must never start another job.
globalThis.MangnaJobRecovery=Object.freeze({
 async receipt(request,lookup,now=Date.now()){
  const response=await lookup(request.id);
  if(response.status===200&&/^[a-f0-9]{32}$/.test(response.body?.id))return response.body.id;
  if(response.status!==404){
   const error=Error(response.body?.error||'접수를 다시 확인하고 있어요.');
   error.permanent=response.status===401||response.status===403;throw error;
  }
  if(!Number.isFinite(request.startedAt)||now-request.startedAt>86400000){
   const error=Error('접수된 작업을 찾지 못했어요. 보관한 사진과 입력을 확인한 뒤 다시 시작해주세요.');
   error.permanent=true;throw error;
  }
  return null;
 },
 notice(accepted,saved,remote=true){
  if(!accepted)return {ready:false,title:'사진 전송·접수 확인 중 · 잠깐만 화면을 열어두세요',detail:'접수 완료 안내가 나오면 브라우저를 닫아도 됩니다.'};
  if(!saved)return {ready:false,title:'접수됐어요 · 이 기기에 이어보기 정보를 저장 중이에요',detail:'저장 완료를 기다려주세요. 저장 실패가 나오면 작업 파일로 보관해주세요.'};
  return {ready:true,title:'접수 완료 · 이제 브라우저를 닫아도 돼요',detail:remote?'연결된 PC가 계속 처리해요. 같은 휴대폰·브라우저로 다시 열면 결과를 불러옵니다. 완료 결과는 서버에 7일간 보관해요.':'연결된 PC가 계속 처리해요. 이 브라우저를 다시 열어 결과를 확인하세요.'};
 }
});
