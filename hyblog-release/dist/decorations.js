// Only the two Naver sticker sets selected by the user on 2026-10-30.
// No copied sticker artwork is hosted here. The native editor inserts its own assets.
(()=>{
 const catalog=Object.freeze({
  anticipation:{pack:'cafe_001',number:13,label:'하얀 고양이 · 반짝이는 기대'},
  delight:{pack:'cafe_001',number:9,label:'하얀 고양이 · 신나는 만족'},
  meal:{pack:'ogq_5ebebeedf0c9a',number:16,label:'밥먹고 합시다'},
  happy:{pack:'ogq_5ebebeedf0c9a',number:6,label:'너무너무 행복해'}
 });
 function enabled(d){return d?.stickers===true;}
 function plan(d){
  if(!enabled(d)||!d.sections?.length)return [];
  const sections=d.sections,food=sections.findIndex(s=>/주문|메뉴|코스|구이|주물럭|볶음|국수|밥|회|고기/.test(s.heading||''));
  const first=Math.max(0,food),all=[d.intro,...sections.map(s=>s.body),d.closing].join(' ');
  const result=[{...catalog.anticipation,afterSection:first}];
  // Be conservative: do not turn a mixed/negative experience into an excited endorsement.
  if(sections.length>1&&/맛있|좋았|만족|행복|잘 먹|배불/.test(all)&&!/맛없|실망|별로|불친절|아쉬|않았|없었/.test(all))result.push({...catalog.happy,afterSection:sections.length-1});
  return result;
 }
 globalThis.HanpyeonDecorations=Object.freeze({enabled,plan,catalog});
})();
