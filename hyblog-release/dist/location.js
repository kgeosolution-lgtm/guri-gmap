(function(root){
 const text=(v,n)=>typeof v==='string'?v.trim().slice(0,n):'';
 function validate(value){
  if(!value||value.confirmed!==true)return null;
  const name=text(value.name,120),address=text(value.address,240);
  if(!name||address.length<6)throw Error('지도에 표시된 상호와 도로명 주소를 확인해주세요.');
  return {name,address,confirmed:true};
 }
 const addressKey=s=>String(s||'').replace(/경기도/g,'경기').replace(/서울특별시/g,'서울').replace(/부산광역시/g,'부산').replace(/\s+/g,'').replace(/[,()]/g,'');
 function matches(label,value){const l=String(label||'');return l.replace(/\s+/g,'').includes(value.name.replace(/\s+/g,''))&&addressKey(l.replace(value.name,'').trim()).includes(addressKey(value.address));}
 root.HyblogLocation=Object.freeze({validate,addressKey,matches});
})(typeof window==='undefined'?globalThis:window);
