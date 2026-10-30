// Shared article layout for preview, export and the Naver delivery adapter.
// These functions arrange supplied text; they never invent captions or tasting notes.
(()=>{
 const disclosure=value=>value==='self'?'내돈내산 · 직접 결제하고 다녀온 후기예요.':value==='provided'?'이 글은 식사를 제공받아 작성한 후기입니다.':'';
 function beats(section){
  const ids=section.photoIds||[],paragraphs=String(section.body||'').split(/\n\s*\n/).filter(p=>p.trim());
  const count=Math.max(1,Math.ceil(ids.length/2)),out=[];
  for(let i=0;i<count;i++)out.push({heading:i===0?section.heading:'',photoIds:ids.slice(i*2,i*2+2),body:paragraphs.slice(Math.ceil(i*paragraphs.length/count),Math.ceil((i+1)*paragraphs.length/count)).join('\n\n')});
  return out;
 }
 function fit(width,height,{gif=false,sticker=false}={}){
  if(!(width>0&&height>0))throw Error('사진 크기를 확인하지 못했어요.');
  const maxWidth=sticker?180:gif?480:620,maxHeight=sticker?180:gif?400:520;
  const scale=Math.min(1,maxWidth/width,maxHeight/height);
  return {width:Math.max(1,Math.floor(width*scale)),height:Math.max(1,Math.floor(height*scale))};
 }
 const shopHeading=place=>place?'「 '+String(place).trim().replace(/[「」\r\n]/g,'')+' 」':'';
 const sectionHeading=(heading,index)=>heading?`${index+1}. ${String(heading).replace(/^\d+[.)]\s*/, '')}`:'';
 // Old developer fixture notices must never leak into a reader-facing article.
 const cleanArticleText=value=>String(value||'').replace(/기능\s*시험용\s*임시저장입니다\.?\s*(?:공개\s*발행하지\s*않습니다\.?)?/g,'').replace(/\n{3,}/g,'\n\n').trim();
 globalThis.MangnaComposition=Object.freeze({disclosure,beats,fit,shopHeading,sectionHeading,cleanArticleText});
})();
