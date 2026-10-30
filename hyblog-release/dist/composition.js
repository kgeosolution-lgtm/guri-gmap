// Shared article layout for preview, export and the Naver delivery adapter.
// These functions arrange supplied text; they never invent captions or tasting notes.
(()=>{
 const disclosure=value=>value==='self'?'내돈내산 · 직접 결제하고 다녀온 후기예요.':value==='provided'?'이 글은 식사를 제공받아 작성한 후기입니다.':'';
 function beats(section){
  const ids=section.photoIds||[],paragraphs=String(section.body||'').split(/\n\s*\n/).filter(p=>p.trim());
  if(isMenuSection(section))return [{heading:section.heading,photoIds:[...ids],body:paragraphs.join('\n\n')}];
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
 const sectionHeading=heading=>String(heading||'').replace(/^\s*\d+[.)]\s+/, '').trim();
 const isMenuSection=section=>section.kind==='menu'||(!section.kind&&/메뉴판|메뉴|주문/.test(section.heading||''));
 const escape=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 // Explicit blank paragraphs survive SmartEditor's paste sanitizer better than margins.
 function pasteHtml(value,{kind='body',before=0,after=1}={}){
  const base='text-align:center;font-family:나눔고딕,NanumGothic,sans-serif;color:#464646;line-height:1.9;';
  const gap='<p style="'+base+'font-size:16px"><br></p>';
  const paragraphs=String(value||'').trim().split(/\n\s*\n/).filter(p=>p.trim());
  if(!paragraphs.length)return '';
  return gap.repeat(before)+paragraphs.map(p=>'<p style="'+base+'font-size:'+(/^「.+」$/.test(p)?'22px;font-weight:bold':kind==='heading'?'19px;font-weight:bold':'16px')+'">'+escape(p).replace(/\n/g,'<br>')+'</p>').join(gap)+gap.repeat(after);
 }
 // Old developer fixture notices must never leak into a reader-facing article.
 const cleanArticleText=value=>String(value||'').replace(/기능\s*시험용\s*임시저장입니다\.?\s*(?:공개\s*발행하지\s*않습니다\.?)?/g,'').replace(/\n{3,}/g,'\n\n').trim();
 globalThis.MangnaComposition=Object.freeze({disclosure,beats,fit,shopHeading,sectionHeading,isMenuSection,pasteHtml,cleanArticleText});
})();
