(function(root){
  function dateLabel(value){
    if(!/^\d{4}-\d{2}-\d{2}$/.test(value||''))return '';
    const [y,m,d]=value.split('-').map(Number),date=new Date(Date.UTC(y,m-1,d));
    if(date.getUTCFullYear()!==y||date.getUTCMonth()!==m-1||date.getUTCDate()!==d)return '';
    return `${m}월 ${d}일`;
  }
  function daypart(value){
    if(!/^([01]\d|2[0-3]):[0-5]\d$/.test(value||''))return '';
    const hour=Number(value.slice(0,2));
    return hour<6?'새벽':hour<11?'오전':hour<14?'점심 무렵':hour<17?'오후':hour<21?'저녁':'밤';
  }
  function visitPhrase(date,time){return [dateLabel(date),daypart(time)].filter(Boolean).join(' ');}
  const api={dateLabel,daypart,visitPhrase};
  if(typeof module!=='undefined')module.exports=api;
  else root.HanpyeonVisit=api;
})(typeof window!=='undefined'?window:globalThis);
