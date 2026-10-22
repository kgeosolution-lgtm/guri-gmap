/* 고양특례시 인허가 사전검토 — 3D 보기 (scene3d.js)
 * ngii5000(수치지형도 1:5,000) 3D 보기 방식을 따름:
 *   같은 Map을 2D MapView ↔ 3D SceneView로 바꿔 끼움, 지형 = Terrain3D + NGII_DEM_5m,
 *   WebGL2·GPU 가속 미리 판정, 3D 분석 도구는 tools.js(GY_TOOLS)를 새 뷰에 붙임.
 * 3D 건물 = 포털의 경기도 LOD 씬 레이어(LOD2 상세 / LOD1 블록)만.
 * 고양 전용: 필지에 '최대 건축 가능 규모'와 '입력 계획'을 매스로 세움, 동지 일조·그림자 바로가기.
 * app.js가 window.GYAPP 으로 지도·상태를 넘겨줌.
 */
(function(){
"use strict";
var A=function(){ return window.GYAPP; };
var HOST="https://kgeodata.com/server/rest/services/Hosted/";
var ELEV=["https://elevation3d.arcgis.com/arcgis/rest/services/WorldElevation3D/Terrain3D/ImageServer",HOST+"NGII_DEM_5m/ImageServer"];
// 경기도 3D 건물 (포털 씬 레이어, 2025-08-12 자료)
//   LOD1 = 전 건물(블록), LOD2 = 일부 건물만 상세 (노드 46개, 고양 일대는 수십 동 — 2026-10-22 nodepages 확인)
var LOD={
  lod1:{url:HOST+"LOD1_GGD_3D_Buildings_250812_2/SceneServer/layers/0",label:"LOD1",pnu:"pnu"},
  lod2:{url:HOST+"LOD2_GGD_3D_Buildings_250812_2/SceneServer/layers/0",label:"LOD2",pnu:"pnu_no"}
};
var FLOOR_H=3.3;     // 매스 층고(m) — 근생·업무 기준 개략값
var WINTER=new Date(Date.UTC(2026,11,22,3,0)); // 동지 12월 22일 정오(KST)

var M=null, view3d=null, mode="2d", massLayer=null, bldgGroup=null, bldgKind="lod1";
var bldgLayers={};

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
    require(["esri/views/SceneView","esri/layers/ElevationLayer","esri/Ground","esri/layers/SceneLayer","esri/layers/GroupLayer","esri/layers/GraphicsLayer","esri/Graphic",
             "esri/geometry/geometryEngine"],
      function(SceneView,ElevationLayer,Ground,SceneLayer,GroupLayer,GraphicsLayer,Graphic,ge){
        clearTimeout(t); res({SceneView:SceneView,ElevationLayer:ElevationLayer,Ground:Ground,SceneLayer:SceneLayer,GroupLayer:GroupLayer,GraphicsLayer:GraphicsLayer,Graphic:Graphic,ge:ge});
      }, function(e){ clearTimeout(t); rej(e); });
  });
}

async function init(){
  M=await need();
  var app=A();
  app.map.ground=new M.Ground({layers:ELEV.map(function(u){ return new M.ElevationLayer({url:u}); })});
  massLayer=new M.GraphicsLayer({title:"3D 매스",elevationInfo:{mode:"on-the-ground"},listMode:"hide"});
  bldgGroup=new M.GroupLayer({title:"3D 건물",listMode:"hide"});
  view3d=new M.SceneView({map:app.map,viewingMode:"global",qualityProfile:"high",popupEnabled:false,
    environment:{atmosphereEnabled:true,starsEnabled:false},
    ui:{components:["zoom","navigation-toggle","compass"]}});
  view3d.ui.move(["zoom","navigation-toggle","compass"],"top-right"); // 왼쪽 위는 레이어 카드 자리 (2D와 같은 쪽)
  try{ view3d.highlightOptions={color:[174,182,27,1],haloOpacity:0.9,fillOpacity:0.2}; }catch(e){}
  view3d.on("click",function(e){ if(e.button===2||(window.GY_TOOLS&&GY_TOOLS.busy())) return; if(e.mapPoint) app.selectAtPoint(e.mapPoint,true); });
}

// 경기도 LOD 건물: 고른 것 하나만 세움
function lodLayer(k){
  if(!bldgLayers[k]){
    // 건물 높이(z)가 지면 0 기준이라 그대로(절대 높이) 두면 지형 아래 묻힘 → 지형 위에 얹음 (2026-10-22 확인)
    var l=new M.SceneLayer({url:LOD[k].url,title:"경기도 3D 건물 ("+LOD[k].label+")",popupEnabled:false,elevationInfo:{mode:"relative-to-ground"},
      renderer:{type:"simple",symbol:{type:"mesh-3d",symbolLayers:[{type:"fill",material:{color:[236,231,222,1],colorMixMode:"replace"},
        edges:{type:"solid",color:[90,84,74,0.45],size:0.6}}]}}});
    l._k=k; bldgLayers[k]=l; bldgGroup.add(l);
  }
  return bldgLayers[k];
}
function setBldg(kind){
  bldgKind=kind;
  if(M&&LOD[kind]) lodLayer(kind);
  Object.keys(bldgLayers).forEach(function(k){ bldgLayers[k].visible=k===kind; });
  hideExistingOnParcel();
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
  var app=A(), S=app.S(); if(!S||!S.zm||!S.geom||!M) return null;
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
// 선택 필지 안의 기존 LOD 건물은 감춰 매스가 보이게 (필지를 0.5m 안쪽으로 줄여 경계 옆 건물은 남김)
function hideExistingOnParcel(){
  var S=A().S(), l=bldgLayers[bldgKind]; if(!view3d||!l) return;
  Object.keys(bldgLayers).forEach(function(k){ if(k!==bldgKind) view3d.whenLayerView(bldgLayers[k]).then(function(lv){ lv.filter=null; }).catch(function(){}); });
  view3d.whenLayerView(l).then(function(lv){
    if(!S||!S.geom||!masses()){ lv.filter=null; return; }
    var k=Math.cos(S.lat*Math.PI/180), inner=M.ge.buffer(S.geom,-0.5/k,"meters")||S.geom;
    lv.filter={geometry:inner,spatialRelationship:"disjoint"};
  }).catch(function(e){ console.warn("기존 건물 숨김 실패",e&&e.message); });
}
function drawMasses(){
  if(!massLayer) return;
  massLayer.removeAll();
  hideExistingOnParcel();
  var ms=masses(); if(!ms) { renderPanel(); return; }
  var add=function(m,color,edge,label){
    if(!m||!m.geom) return;
    massLayer.add(new M.Graphic({geometry:m.geom,attributes:{label:label},symbol:{type:"polygon-3d",symbolLayers:[{type:"extrude",size:m.h,material:{color:color},edges:{type:"solid",color:edge,size:1}}]}}));
  };
  var showMax=$("m3Max")?$("m3Max").checked:true, showPlan=$("m3Plan")?$("m3Plan").checked:true;
  if(showMax) add(ms.max,[174,182,27,ms.plan&&showPlan?0.28:0.55],[120,126,10,0.9],"최대");
  if(showPlan&&ms.plan) add(ms.plan,[2,87,79,0.88],[255,255,255,0.9],"계획");
  renderPanel(ms);
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
  h+='<div class="m3-sub">경기도 3D 건물</div><div class="m3-seg">'+
     '<button data-b3="lod1" class="'+(bldgKind==="lod1"?"on":"")+'" title="경기도 전 건물 (블록 모형)">LOD1 전체</button>'+
     '<button data-b3="lod2" class="'+(bldgKind==="lod2"?"on":"")+'" title="지붕 모양까지 만든 상세 모형 — 고양시는 일부 건물만 있음">LOD2 일부</button>'+
     '<button data-b3="none" class="'+(bldgKind==="none"?"on":"")+'">끄기</button></div>';
  h+='<div class="m3-sub">일조 확인</div><div class="m3-act">'+
     '<button data-a3="winter">동지 일조</button><button data-a3="shadow">그림자 시간</button><button data-a3="tools">3D 분석</button></div>';
  h+='<div class="m3-act"><button data-a3="fly">필지로 이동</button><button data-a3="top">위에서 보기</button></div>';
  h+='<div class="m3-foot">매스는 층고 '+FLOOR_H+'m · 대지경계 0.5m 이격 기준 개략 형태입니다. 높이·사선·지구단위계획 제한은 반영되지 않습니다. 건물: 경기도 3D 건물(2025.8).</div>';
  el.innerHTML=h;
}

function flyToParcel(top){
  var S=A().S(); if(!view3d||!S||!S.geom) return;
  var ms=masses(), hgt=ms?Math.max(ms.max.h,(ms.plan||{}).h||0):30;
  // 필지와 주변 블록이 함께 보이게: 필지 크기·매스 높이에 맞춰 범위를 넓힘 (작은 필지도 최소 약 250m 폭)
  var w=Math.max(S.geom.extent.width,S.geom.extent.height,1), f=Math.max(top?3:4,(250+hgt*3)/w);
  var ext=S.geom.extent.clone().expand(f);
  view3d.goTo(top?{target:ext,tilt:0}:{target:ext,tilt:58,heading:200},{duration:1200}).catch(function(){});
}

async function setMode(m){
  if(m===mode) return;
  var app=A(), b2=$("mode2d"), b3=$("mode3d");
  if(m==="3d"){
    if(NO3D){ app.toast(NO3D,8000); return; }
    b3.disabled=true; app.loading(true,"3D 보기를 준비하는 중");
    try{ if(!view3d) await init(); }
    catch(e){ app.loading(false); b3.disabled=false; app.toast("3D 보기를 열지 못했습니다: "+(e&&e.message||e)); return; }
    var vp=app.view.viewpoint.clone();
    if(!app.map.layers.includes(bldgGroup)) app.map.layers.add(bldgGroup);
    if(!app.map.layers.includes(massLayer)) app.map.layers.add(massLayer);
    setBldg(bldgKind);
    app.view.container=null;
    view3d.container="viewDiv";
    mode="3d";
    document.body.classList.add("is3d");
    if(window.GY_TOOLS) GY_TOOLS.attach(view3d);
    try{ await view3d.when(); }
    catch(e){ app.loading(false); b3.disabled=false; await setMode("2d"); app.toast("3D 보기를 열지 못했습니다: "+(e&&e.message||e),8000); return; }
    var S=app.S();
    await view3d.goTo({target:vp.targetGeometry,scale:vp.scale,tilt:0},{animate:false}).catch(function(){});
    if(S&&S.geom){ drawMasses(); flyToParcel(false); }
    app.loading(false); b3.disabled=false;
    app.toast(matchMedia("(pointer: coarse)").matches?"두 손가락으로 끌면 기울이거나 돌려 볼 수 있습니다":"마우스 오른쪽 버튼으로 끌면 기울이거나 돌려 볼 수 있습니다 · 오른쪽 클릭: 3D 분석 메뉴",5000);
  }else{
    var vp3=view3d&&view3d.viewpoint?view3d.viewpoint.clone():null;
    if(view3d) view3d.container=null;
    app.map.layers.remove(bldgGroup); app.map.layers.remove(massLayer); // 3D 건물·매스는 2D 지도에 그릴 수 없음
    app.view.container="viewDiv";
    if(vp3&&vp3.targetGeometry){ app.view.goTo({target:vp3.targetGeometry,scale:Math.max(vp3.scale,500)},{animate:false}).catch(function(){}); }
    mode="2d";
    document.body.classList.remove("is3d");
    if(window.GY_TOOLS) GY_TOOLS.attach(app.view);
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
  var a=t.dataset.a3;
  if(a==="fly") flyToParcel(false);
  else if(a==="top") flyToParcel(true);
  else if(a==="winter"&&window.GY_TOOLS) GY_TOOLS.run("sun",{date:WINTER,title:"동지 일조 (12월 22일)",hint:"동지 정오 기준으로 해와 그림자를 보여 줍니다. 시각 막대를 끌거나 ▶ 를 눌러 9시~15시 그림자를 확인하세요 (건축법 시행령 제86조 일조 기준 참고)."});
  else if(a==="shadow"&&window.GY_TOOLS) GY_TOOLS.run("shadow",{date:WINTER,hint:"동지(12월 22일) 하루 동안 그늘이 지는 시간을 색으로 보여 줍니다. 날짜와 시간 범위를 바꿔 볼 수 있습니다."});
  else if(a==="tools"&&window.GY_TOOLS) GY_TOOLS.run("list");
});
document.addEventListener("change",function(e){
  if(e.target.id==="m3Max"||e.target.id==="m3Plan") drawMasses();
});

// app.js가 필지·계획이 바뀔 때 부름
window.GY3D={
  is3d:function(){ return mode==="3d"; },
  _view:function(){ return view3d; }, // 점검용
  setMode:setMode,
  open:function(){ return setMode("3d"); },
  refresh:function(){ if(mode==="3d"){ drawMasses(); } },
  parcelChanged:function(){ if(mode==="3d"){ drawMasses(); flyToParcel(false); } },
  unavailable:NO3D
};
if(NO3D){ var b=$("mode3d"); if(b){ b.classList.add("na"); b.title=NO3D; } }
})();
