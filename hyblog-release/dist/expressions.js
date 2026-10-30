(function(root){
  const clean=(s,n=400)=>typeof s==='string'?s.trim().slice(0,n):'';
  const sourceUrl=value=>{try{const u=new URL(value);return u.protocol==='https:'&&!u.username&&!u.password&&(/(^|\.)blog\.naver\.com$|(^|\.)place\.naver\.com$|(^|\.)tistory\.com$|(^|\.)diningcode\.com$|(^|\.)siksinhot\.com$|(^|\.)google\.(com|co\.kr)$/.test(u.hostname))?u.href:'';}catch{return '';}};
  function prepare(items,sections,references){
    const seen=new Set();return (Array.isArray(items)?items:[]).slice(0,12).flatMap(item=>{
      const section=sections[item.sectionIndex],source=references[item.sourceIndex],note=source?.menuNotes?.[item.noteIndex];
      const text=clean(item.text,320),url=sourceUrl(source?.url);
      if(section?.kind!=='food'||!section.photoIds?.[0]||!note||!url||!text||seen.has(text))return [];
      const paragraphs=section.body.split(/\n\s*\n/).filter(p=>p.trim());
      const after=Number.isInteger(item.afterParagraph)&&item.afterParagraph>=0?Math.min(item.afterParagraph,paragraphs.length-1):0;
      seen.add(text);return [{id:'expression-'+seen.size,targetPhotoId:section.photoIds[0],label:clean(item.label,35),text,insertAfter:paragraphs[after]||'',menu:clean(note.menu,70),evidence:clean(note.point,220),source:{url,title:clean(source.title,180),date:clean(source.date,10),sponsored:source.sponsored}}];
    });
  }
  function forSection(draft,section){return (Array.isArray(draft?.expressionSuggestions)?draft.expressionSuggestions:[]).filter(s=>s&&typeof s.text==='string'&&sourceUrl(s.source?.url)&&section.photoIds.includes(s.targetPhotoId));}
  function append(body,text){if(!text||body.includes(text))return {body,changed:false};const suffix=(body.trim()?'\n\n':'')+text;return {body:body+suffix,changed:true,suffix};}
  function undo(body,suffix){return suffix&&body.endsWith(suffix)?{body:body.slice(0,-suffix.length),changed:true}:{body,changed:false};}
  function insert(body,item){
    if(!item.text||body.includes(item.text))return {body,changed:false};
    const anchor=item.insertAfter,at=anchor&&body.indexOf(anchor),valid=anchor&&at>=0&&body.indexOf(anchor,at+anchor.length)<0;
    if(!valid){const result=append(body,item.text);return {...result,at:body.length,inserted:result.suffix,placement:'end'};}
    const end=at+anchor.length,inserted='\n\n'+item.text;
    return {body:body.slice(0,end)+inserted+body.slice(end),changed:true,at:end,inserted,placement:'context'};
  }
  function revert(body,receipt){
    if(!receipt?.inserted)return undo(body,receipt?.suffix);
    const at=body.indexOf(receipt.inserted);
    if(at<0||body.indexOf(receipt.inserted,at+receipt.inserted.length)>=0)return {body,changed:false};
    return {body:body.slice(0,at)+(receipt.original||'')+body.slice(at+receipt.inserted.length),changed:true};
  }
  function replace(body,item){
    const anchor=item.insertAfter,at=anchor&&body.indexOf(anchor);
    if(!anchor||at<0||body.indexOf(anchor,at+anchor.length)>=0||body.includes(item.text))return {body,changed:false};
    return {body:body.slice(0,at)+item.text+body.slice(at+anchor.length),changed:true,inserted:item.text,original:anchor,placement:'replace'};
  }
  root.MangnaExpressions={prepare,forSection,append,undo,insert,revert,replace,sourceUrl};
})(globalThis);
