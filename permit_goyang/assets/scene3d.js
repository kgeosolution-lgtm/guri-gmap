/* 고양특례시 인허가 사전검토 — 3D 규모 검토 (scene3d.js)
 * ngii5000(수치지형도 1:5,000) 3D 보기 방식을 따름:
 *   같은 Map을 2D MapView ↔ 3D SceneView로 바꿔 끼움, 지형 = Terrain3D + NGII_DEM_5m,
 *   WebGL2·GPU 가속 미리 판정, 브이월드 건물 메시는 kgeodata.com 출처에서만.
 * 고양 전용: 주변 건물 = 수치지형도 1:1,000 건물(층수×3m), 필지에 '최대 건축 가능 규모'와 '입력 계획'을 매스로 세움,
 *   동지 일조(그림자) 시뮬레이션.
 * app.js가 window.GYAPP 으로 지도·상태를 넘겨줌.
 */
(function(){
"use strict";
var A=function(){ return window.GYAPP; };
var HOST="https://kgeodata.com/server/rest/services/Hosted/";
var ELEV=["https://elevation3d.arcgis.com/arcgis/rest/services/WorldElevation3D/Terrain3D/ImageServer",HOST+"NGII_DEM_5m/ImageServer"];
var MESH_URL="https://kgeodata.com/app/test/test/portal-height-study/dem/tileset.json"; // ngii5000과 같은 브이월드 전국 건물 메시
var FLOOR_H=3.3;     // 매스 층고(m) — 근생·업무 기준 개략값
var BLDG_FLOOR=3;    // 주변 건물 층고(m) — ngii5000과 같은 지상 층수×3m

var M=null, view3d=null, mode="2d", massLayer=null, bldgLayer=null, meshLayer=null, meshOk=false, bldgKind="ngii";
var sun={on:false,hour:12};

function $(id){ return document.getElementById(id); }
function n0(v){ return Math.round(v).toLocaleString("ko-KR"); }

// SDK와 같은 판정: GPU 가속 없는 WebGL이면 SceneView가 열리지 않음 (ngii5000 no3dReason)
function no3dReason(){
  try{
    if(typeof WebGL2RenderingContext==="undefined") return "이 브라우저는 3D에 필요한 WebGL2를 지원하지 않습니다. 최신 Chrome·Edge에서 열어 주세요.";
    var c=document.createElement("canvas"), g=c.getContext("webgl2",{failIfMajorPerformanceCaveat:true}), why="";
    if(!g){ g=c.getContext("webgl2"); why=g?"그래픽 가속(GPU) 없이 그리고 있어 3D를 열 수 없습니다. 브라우저 설정에서 '그래픽 가속 사용'을 켜 주세요.":"이 브라우저에서 WebGL2를 쓸 수 없어 3D를 열 수 없습니다."; }
    var lose=g&&g.getExtension("WEBGL_lose_context"); if(lose) lose.loseContext();
    return why;
  }catch(e){ return ""; }
}
var NO3D=no3dReason();

function need(){
  return new Promise(function(res,rej){
    var t=setTimeout(function(){ rej(new Error("3D 기능을 불러오지 못했습니다")); },40000);
    require(["esri/views/SceneView","esri/layers/ElevationLayer","esri/Ground","esri/layers/FeatureLayer","esri/layers/GraphicsLayer","esri/Graphic",
             "esri/geometry/geometryEngine","esri/geometry/Polygon","esri/layers/IntegratedMesh3DTilesLayer"],
      function(SceneView,ElevationLayer,Ground,FeatureLayer,GraphicsLayer,Graphic,ge,Polygon,Mesh){
        clearTimeout(t); res({SceneView:SceneView,ElevationLayer:ElevationLayer,Ground:Ground,FeatureLayer:FeatureLayer,GraphicsLayer:GraphicsLayer,Graphic:Graphic,ge:ge,Polygon:Polygon,Mesh:Mesh});
      }, function(e){ clearTimeout(t); rej(e); });
  });
}

async function init(){
  M=await need();
  var app=A();
  app.map.ground=new M.Ground({layers:ELEV.map(function(u){ return new M.ElevationLayer({url:u}); })});
  massLayer=new M.GraphicsLayer({title:"3D 매스",elevationInfo:{mode:"on-the-ground"},listMode:"hide"});
  // 주변 건물: 수치지형도 1:1,000 건물 (층수×3m)
  bldgLayer=new M.FeatureLayer({url:HOST+"goyang_N1A_B0010000_building/FeatureServer/0",title:"주변 건물",outFields:["층수","용도","명칭"],
    elevationInfo:{mode:"on-the-ground"},popupEnabled:false,minScale:12000,listMode:"hide",
    renderer:{type:"simple",symbol:{type:"polygon-3d",symbolLayers:[{type:"extrude",material:{color:[232,226,214,1]},edges:{type:"solid",color:[110,100,85,0.5],size:0.5}}]},
      visualVariables:[{type:"size",valueExpression:"Max(1,$feature.층수)*"+BLDG_FLOOR,valueUnit:"meters"}]}});
  view3d=new M.SceneView({map:app.map,viewingMode:"global",qualityProfile:"high",popupEnabled:false,
    environment:{atmosphereEnabled:true,starsEnabled:false,lighting:{type:"virtual"}},
    ui:{components:["zoom","navigation-toggle","compass"]}});
  try{ view3d.highlightOptions={color:[174,182,27,1],haloOpacity:0.9,fillOpacity:0.2}; }catch(e){}
  view3d.on("click",function(e){ if(e.mapPoint) app.selectAtPoint(e.mapPoint,true); });
  // 브이월드 메시: kgeodata.com 출처에서만 열림 (ngii5000과 같은 조건)
  meshOk=self.origin==="https://kgeodata.com" && await fetch(MESH_URL,{method:"GET"}).then(function(r){return r.ok;}).catch(function(){return false;});
  renderPanel();
}

function setBldg(kind){
  bldgKind=kind;
  var app=A();
  if(bldgLayer) bldgLayer.visible=kind==="ngii";
  if(kind==="mesh"&&meshOk){
    if(!meshLayer){ meshLayer=new M.Mesh({url:MESH_URL,title:"브이월드 건물"}); }
    if(!app.map.layers.includes(meshLayer)) app.map.layers.add(meshLayer);
    meshLayer.visible=true;
  }else if(meshLayer) meshLayer.visible=false;
  renderPanel();
}

// ── 매스 계산: 필지를 안쪽으로 줄여 목표 바닥면적을 맞춤 (평면 버퍼를 이분 탐색) ──
function insetTo(geom,targetArea,minInset,k){
  var area=function(g){ return g? M.ge.planarArea(g,"square-meters")*k*k : 0; };
  var base=minInset>0? M.ge.buffer(geom,-minInset/k,"meters") : geom;
  if(!base||area(base)<=0) base=geom;
  if(area(base)<=targetArea) return base;
  var lo=0, hi=Math.sqrt(area(base)), best=base;
  for(var i=0;i<22;i++){
    var mid=(lo+hi)/2, g=M.ge.buffer(base,-mid/k,"meters"), a=area(g);
    if(!g||a<=0){ hi=mid; continue; }
    if(a>targetArea){ lo=mid; best=g; } else { hi=mid; best=g; }
    if(Math.abs(a-targetArea)/targetArea<0.01) break;
  }
  return best;
}
function masses(){
  var app=A(), S=app.S(); if(!S||!S.zm||!S.geom) return null;
  var k=Math.cos(S.lat*Math.PI/180), zm=S.zm, sa=+S.area||0;
  // 최대 규모: 건폐율 한도 바닥 × 층수 = min(용적률/건폐율, 층수 제한)
  var maxFloors=Math.max(1,Math.floor(zm.f/zm.b));
  if(zm.h) maxFloors=Math.min(maxFloors,zm.h);
  var maxBa=sa*zm.b/100;
  var setback=0.5; // 대지 안의 공지 최소(인접대지 0.5m) 개략
  var out={max:{geom:insetTo(S.geom,maxBa,setback,k),floors:maxFloors,ba:maxBa,ta:Math.min(sa*zm.f/100,maxBa*maxFloors)}};
  out.max.h=maxFloors*FLOOR_H;
  var P=S.lastP;
  if(P&&P.ba>0&&(P.fl>0||P.ht>0)){
    var fl=P.fl||Math.max(1,Math.round(P.ht/FLOOR_H));
    out.plan={geom:insetTo(S.geom,Math.min(P.ba,sa),setback,k),floors:fl,ba:P.ba,ta:P.ta,h:P.ht||fl*FLOOR_H};
  }
  return out;
}
// 선택 필지 안의 기존 건물은 감춰 매스가 보이게 (필지를 0.5m 안쪽으로 줄여 경계 옆 건물은 남김)
function hideExistingOnParcel(){
  var S=A().S(); if(!view3d||!bldgLayer) return;
  // 3D 레이어뷰는 공간 필터 대신 속성(where) 필터로: 필지 안 건물 objectid를 찾아 제외
  view3d.whenLayerView(bldgLayer).then(function(lv){
    if(!S||!S.geom){ lv.filter=null; return; }
    var k=Math.cos(S.lat*Math.PI/180), inner=M.ge.buffer(S.geom,-0.5/k,"meters")||S.geom;
    return bldgLayer.queryObjectIds({geometry:inner,spatialRelationship:"intersects"}).then(function(ids){
      lv.filter=ids&&ids.length?{where:"objectid NOT IN ("+ids.join(",")+")"}:null;
    });
  }).catch(function(e){ console.warn("기존 건물 숨김 실패",e&&e.message); });
}
function drawMasses(){
  if(!massLayer) return;
  massLayer.removeAll();
  hideExistingOnParcel();
  var ms=masses(); if(!ms) { renderPanel(); return; }
  var add=function(m,color,edge,label){
    if(!m||!m.geom) return;
    // 층마다 얇은 띠를 두어 층수가 보이게 (층 슬래브)
    massLayer.add(new M.Graphic({geometry:m.geom,attributes:{label:label},symbol:{type:"polygon-3d",symbolLayers:[{type:"extrude",size:m.h,material:{color:color},edges:{type:"solid",color:edge,size:1}}]}}));
  };
  var showMax=$("m3Max")?$("m3Max").checked:true, showPlan=$("m3Plan")?$("m3Plan").checked:true;
  if(showMax) add(ms.max,[174,182,27,ms.plan&&showPlan?0.28:0.55],[120,126,10,0.9],"최대");
  if(showPlan&&ms.plan) add(ms.plan,[2,87,79,0.88],[255,255,255,0.9],"계획");
  renderPanel(ms);
}

// ── 동지 일조: 12월 22일, 시각 슬라이더 (그림자 켬) ──
function applySun(){
  if(!view3d) return;
  if(!sun.on){ view3d.environment.lighting={type:"virtual"}; return; }
  var h=Math.floor(sun.hour), m=Math.round((sun.hour-h)*60);
  var d=new Date(Date.UTC(2026,11,22,h-9,m)); // KST = UTC+9
  view3d.environment.lighting={type:"sun",date:d,directShadowsEnabled:true,displayUTCOffset:9};
}

function renderPanel(ms){
  var el=$("m3Panel"); if(!el) return;
  var S=A().S();
  if(mode!=="3d"){ el.hidden=true; return; }
  el.hidden=false;
  ms=ms||masses();
  var h='<div class="m3-h">3D 규모 검토</div>';
  if(!S){ h+='<div class="m3-empty">필지를 선택하면 최대 건축 가능 규모를 3D로 세워 보여 줍니다.</div>'; }
  else if(!ms){ h+='<div class="m3-empty">용도지역을 확인하는 중입니다…</div>'; }
  else{
    h+='<label class="m3-row"><input type="checkbox" id="m3Max"'+(($("m3Max")?$("m3Max").checked:true)?" checked":"")+'><i class="m3-sw" style="background:rgba(174,182,27,.55);border-color:#7e8610"></i><span><b>최대 건축 가능 규모</b><small>건폐율 '+S.zm.b+'% · '+ms.max.floors+'층 · 높이 약 '+Math.round(ms.max.h)+'m · 연면적 약 '+n0(ms.max.ta)+'㎡</small></span></label>';
    if(ms.plan) h+='<label class="m3-row"><input type="checkbox" id="m3Plan"'+(($("m3Plan")?$("m3Plan").checked:true)?" checked":"")+'><i class="m3-sw" style="background:#02574F;border-color:#fff"></i><span><b>입력한 건축계획</b><small>건축면적 '+n0(ms.plan.ba)+'㎡ · '+ms.plan.floors+'층 · 높이 약 '+Math.round(ms.plan.h)+'m</small></span></label>';
    else h+='<div class="m3-note">사전검토 탭에서 계획(건축면적·층수)을 입력·실행하면 계획 매스도 함께 세웁니다.</div>';
  }
  h+='<div class="m3-sub">주변 건물</div><div class="m3-seg">'+
     '<button data-b3="ngii" class="'+(bldgKind==="ngii"?"on":"")+'">수치지형도 (층수)</button>'+
     '<button data-b3="mesh" class="'+(bldgKind==="mesh"?"on":"")+'"'+(meshOk?"":" disabled title=\"kgeodata.com에서 열었을 때만 쓸 수 있습니다\"")+'>브이월드 메시</button>'+
     '<button data-b3="none" class="'+(bldgKind==="none"?"on":"")+'">없음</button></div>';
  h+='<label class="m3-row m3-sun"><input type="checkbox" id="m3Sun"'+(sun.on?" checked":"")+'><span><b>동지 일조 (12월 22일)</b><small>그림자로 북쪽 이웃 일조 영향 확인</small></span></label>';
  if(sun.on) h+='<div class="m3-time"><input type="range" id="m3Hour" min="9" max="15" step="0.25" value="'+sun.hour+'"><span>'+fmtHour(sun.hour)+'</span></div>';
  h+='<div class="m3-act"><button data-a3="fly">필지로 이동</button><button data-a3="top">위에서 보기</button></div>';
  h+='<div class="m3-foot">매스는 층고 '+FLOOR_H+'m · 대지경계 0.5m 이격 기준 개략 형태입니다. 높이·사선·지구단위계획 제한은 반영되지 않습니다.</div>';
  el.innerHTML=h;
}
function fmtHour(x){ var h=Math.floor(x), m=Math.round((x-h)*60); return (h<12?"오전 ":"오후 ")+(h>12?h-12:h)+"시"+(m?" "+m+"분":""); }

function flyToParcel(top){
  var S=A().S(); if(!view3d||!S||!S.geom) return;
  var ms=masses(), hgt=ms?Math.max(ms.max.h,(ms.plan||{}).h||0):30;
  var ext=S.geom.extent.clone().expand(top?3:2.2);
  view3d.goTo(top?{target:ext,tilt:0}:{target:S.geom,tilt:62,heading:200,zoom:Math.max(17,Math.min(19,19-Math.log2(Math.max(1,Math.sqrt(S.area)/40+hgt/80))))},{duration:1200}).catch(function(){});
}

async function setMode(m){
  if(m===mode) return;
  var app=A(), b2=$("mode2d"), b3=$("mode3d");
  if(m==="3d"){
    if(NO3D){ app.toast(NO3D); return; }
    b3.disabled=true; app.loading(true,"3D 보기를 준비하는 중");
    try{ if(!view3d) await init(); }
    catch(e){ app.loading(false); b3.disabled=false; app.toast("3D 보기를 열지 못했습니다: "+(e&&e.message||e)); return; }
    var vp=app.view.viewpoint.clone();
    if(!app.map.layers.includes(bldgLayer)) app.map.layers.add(bldgLayer);
    if(!app.map.layers.includes(massLayer)) app.map.layers.add(massLayer);
    setBldg(bldgKind);
    app.view.container=null;
    view3d.container="viewDiv";
    mode="3d";
    document.body.classList.add("is3d");
    await view3d.when();
    var S=app.S();
    if(S&&S.geom){ await view3d.goTo({target:vp.targetGeometry,scale:vp.scale,tilt:0},{animate:false}).catch(function(){}); drawMasses(); flyToParcel(false); }
    else await view3d.goTo({target:vp.targetGeometry,scale:vp.scale,tilt:0},{animate:false}).catch(function(){});
    app.loading(false); b3.disabled=false;
    applySun();
    app.toast(matchMedia("(pointer: coarse)").matches?"두 손가락으로 끌면 기울이거나 돌려 볼 수 있습니다":"마우스 오른쪽 버튼으로 끌면 기울이거나 돌려 볼 수 있습니다");
  }else{
    var vp3=view3d.viewpoint?view3d.viewpoint.clone():null;
    view3d.container=null;
    app.map.layers.remove(bldgLayer); app.map.layers.remove(massLayer); if(meshLayer) app.map.layers.remove(meshLayer);
    app.view.container="viewDiv";
    if(vp3&&vp3.targetGeometry){ app.view.goTo({target:vp3.targetGeometry,scale:Math.max(vp3.scale,500)},{animate:false}).catch(function(){}); }
    mode="2d";
    document.body.classList.remove("is3d");
  }
  if(b2) b2.classList.toggle("active",mode==="2d");
  if(b3) b3.classList.toggle("active",mode==="3d");
  renderPanel();
}

// ── 이벤트 ──
document.addEventListener("click",function(e){
  var t=e.target.closest("[data-mode],[data-b3],[data-a3]"); if(!t) return;
  if(t.dataset.mode){ setMode(t.dataset.mode); return; }
  if(t.dataset.b3){ setBldg(t.dataset.b3); return; }
  if(t.dataset.a3==="fly") flyToParcel(false);
  else if(t.dataset.a3==="top") flyToParcel(true);
});
document.addEventListener("change",function(e){
  if(e.target.id==="m3Max"||e.target.id==="m3Plan") drawMasses();
  else if(e.target.id==="m3Sun"){ sun.on=e.target.checked; applySun(); renderPanel(); }
});
document.addEventListener("input",function(e){
  if(e.target.id==="m3Hour"){ sun.hour=+e.target.value; applySun(); var s=e.target.nextElementSibling; if(s) s.textContent=fmtHour(sun.hour); }
});

// app.js가 필지·계획이 바뀔 때 부름
window.GY3D={
  is3d:function(){ return mode==="3d"; },
  _view:function(){ return view3d; }, // 점검용
  open:function(){ return setMode("3d"); },
  refresh:function(){ if(mode==="3d"){ drawMasses(); } },
  parcelChanged:function(){ if(mode==="3d"){ drawMasses(); flyToParcel(false); } },
  unavailable:NO3D
};
if(NO3D){ var b=$("mode3d"); if(b){ b.classList.add("na"); b.title=NO3D; } }
})();
