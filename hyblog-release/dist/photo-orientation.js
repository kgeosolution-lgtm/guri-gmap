// Normalize JPEG EXIF exactly once before drawing; shared by Worker and fallback.
(()=>{
 function exif(buffer){
  const v=new DataView(buffer),found=[];
  if(v.byteLength<4||v.getUint16(0)!==0xffd8)return found;
  let p=2;
  while(p+4<=v.byteLength){
   if(v.getUint8(p)!==255)break;
   const marker=v.getUint8(p+1);if(marker===0xda||marker===0xd9)break;
   const len=v.getUint16(p+2),end=p+2+len;if(len<2||end>v.byteLength)break;
   if(marker===0xe1&&len>=16&&v.getUint32(p+4)===0x45786966&&v.getUint16(p+8)===0){
    const t=p+10,order=v.getUint16(t),le=order===0x4949;
    if((le||order===0x4d4d)&&v.getUint16(t+2,le)===42){
     const ifd=t+v.getUint32(t+4,le);
     if(ifd>=t+8&&ifd+2<=end){const count=v.getUint16(ifd,le);
      for(let i=0;i<count;i++){const q=ifd+2+i*12;if(q+12>end)break;
       if(v.getUint16(q,le)===0x112&&v.getUint16(q+2,le)===3&&v.getUint32(q+4,le)===1){const value=v.getUint16(q+8,le);if(value>=1&&value<=8)found.push({offset:q+8,le,value});}
      }
     }
    }
   }
   p=end;
  }
  return found;
 }
 async function source(file){
  const buffer=await file.arrayBuffer(),tags=exif(buffer),orientation=tags[0]?.value||1;
  if(!tags.length)return {blob:file,orientation};
  const view=new DataView(buffer);for(const tag of tags)view.setUint16(tag.offset,1,tag.le);
  return {blob:new Blob([buffer],{type:file.type||'image/jpeg'}),orientation};
 }
 function dimensions(width,height,orientation=1,turns=0,max=1600){
  if(!(width>0&&height>0)||width*height>100000000)throw Error('사진 해상도를 확인해주세요.');
  const scale=Math.min(1,max/Math.max(width,height)),w=Math.max(1,Math.round(width*scale)),h=Math.max(1,Math.round(height*scale));
  const swap=(orientation>=5)!==((turns%2+2)%2===1);return {w,h,width:swap?h:w,height:swap?w:h};
 }
 function draw(canvas,image,orientation=1,turns=0){
  turns=((turns%4)+4)%4;
  const {w,h,width,height}=dimensions(image.width||image.naturalWidth,image.height||image.naturalHeight,orientation,turns);
  canvas.width=width;canvas.height=height;const ctx=canvas.getContext('2d');
  ctx.fillStyle='#fff';ctx.fillRect(0,0,width,height);ctx.save();
  if(turns===1){ctx.translate(width,0);ctx.rotate(Math.PI/2);}
  if(turns===2){ctx.translate(width,height);ctx.rotate(Math.PI);}
  if(turns===3){ctx.translate(0,height);ctx.rotate(-Math.PI/2);}
  const m={1:[1,0,0,1,0,0],2:[-1,0,0,1,w,0],3:[-1,0,0,-1,w,h],4:[1,0,0,-1,0,h],5:[0,1,1,0,0,0],6:[0,1,-1,0,h,0],7:[0,-1,-1,0,h,w],8:[0,-1,1,0,0,w]}[orientation]||[1,0,0,1,0,0];
  ctx.transform(...m);ctx.drawImage(image,0,0,w,h);ctx.restore();return {width,height};
 }
 globalThis.MangnaPhoto=Object.freeze({exif,source,dimensions,draw});
})();
