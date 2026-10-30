import {GIFEncoder,quantize,applyPalette} from './gifenc.js';
let gif;
self.onmessage=async({data:{id,op,...data}})=>{
 try{
  let result;
  if(op==='photo'){
   const bitmap=await createImageBitmap(data.file);
   try{
    if(bitmap.width*bitmap.height>100000000)throw Error('사진 해상도가 너무 높아요.');
    const scale=Math.min(1,1600/Math.max(bitmap.width,bitmap.height));
    const c=new OffscreenCanvas(Math.max(1,Math.round(bitmap.width*scale)),Math.max(1,Math.round(bitmap.height*scale))),ctx=c.getContext('2d');
    ctx.fillStyle='#fff';ctx.fillRect(0,0,c.width,c.height);ctx.drawImage(bitmap,0,0,c.width,c.height);
    result=await c.convertToBlob({type:'image/jpeg',quality:.82});
   }finally{bitmap.close();}
  }else if(op==='gif-start'){gif=GIFEncoder();result=true;}
  else if(op==='gif-frame'){
   if(!gif)throw Error('움짤 준비를 다시 시작해주세요.');
   const rgba=new Uint8ClampedArray(data.rgba),palette=quantize(rgba,128);
   gif.writeFrame(applyPalette(rgba,palette),data.width,data.height,{palette,delay:125,repeat:0});result=true;
  }else if(op==='gif-end'){
   if(!gif)throw Error('움짤 준비를 다시 시작해주세요.');
   gif.finish();result=new Blob([gif.bytes()],{type:'image/gif'});gif=null;
  }else throw Error('알 수 없는 미디어 작업');
  self.postMessage({id,result});
 }catch(e){self.postMessage({id,error:e.message||'미디어 준비를 마치지 못했어요.'});}
};
