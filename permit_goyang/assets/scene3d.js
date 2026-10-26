/* 고양특례시 인허가 사전검토 — 3D 보기 (scene3d.js)
 * ngii5000(수치지형도 1:5,000) 3D 보기 방식을 따름:
 *   같은 Map을 2D MapView ↔ 3D SceneView로 바꿔 끼움, 지형 = Terrain3D + NGII_DEM_5m,
 *   WebGL2·GPU 가속 미리 판정, 3D 분석 도구는 tools.js(GY_TOOLS)를 새 뷰에 붙임.
 * 3D 건물 = 포털의 경기도 LOD1 씬 레이어만.
 * 고양 전용: 필지에 '최대 건축 가능 규모'와 '입력 계획'을 매스로 세움, 일조권 분석(동지)·그림자 바로가기.
 * app.js가 window.GYAPP 으로 지도·상태를 넘겨줌.
 */
(function(){
"use strict";
var A=function(){ return window.GYAPP; };
var HOST="https://kgeodata.com/server/rest/services/Hosted/";
var ELEV=["https://elevation3d.arcgis.com/arcgis/rest/services/WorldElevation3D/Terrain3D/ImageServer",HOST+"NGII_DEM_5m/ImageServer"];
// 경기도 3D 건물 LOD1 (포털, 2025-08-12 자료) — 같은 자료의 피처 서비스(바닥 모양 + 건물높이 bldg_hgt)를 지면 위로 세움.
//   씬 레이어(3D 모형)는 바닥 높이가 건물마다 섞여 있어(0 기준 / 해발 기준) 어떤 배치로도 일부가 뜨거나 묻힘 (2026-10-26 확인)
//   → 바닥 모양 × 높이로 세우면 모든 건물이 지형에 붙음. 고양 106,922동 중 99.2%가 높이 있음, 없으면 지상층수×층고
//   LOD2는 일부 건물만 있어(노드 46개, 고양 일대 수십 동 — 2026-10-22 nodepages 확인) 넣지 않음
var LOD={
  lod1:{url:HOST+"LOD1_GGD_3D_Buildings_250812_2/FeatureServer/0",label:"LOD1",pnu:"pnu"}
};
var FLOOR_H=3.3;     // 매스 층고(m) — 근생·업무 기준 개략값
var WINTER=new Date(Date.UTC(2026,11,22,3,0)); // 동지 12월 22일 정오(KST)

var M=null, view3d=null, mode="2d", massLayer=null, upLayer=null, bldgGroup=null, bldgKind="lod1"; // upLayer: 지붕 위 수직 증축 (지면 기준 높이로 띄움)
var bldgLayers={}, m3min=false; // m3min: 3D 규모 패널을 제목만 남겨 접음

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
             "esri/geometry/geometryEngine","esri/layers/FeatureLayer"],
      function(SceneView,ElevationLayer,Ground,SceneLayer,GroupLayer,GraphicsLayer,Graphic,ge,FeatureLayer){
        clearTimeout(t); res({SceneView:SceneView,ElevationLayer:ElevationLayer,Ground:Ground,SceneLayer:SceneLayer,GroupLayer:GroupLayer,GraphicsLayer:GraphicsLayer,Graphic:Graphic,ge:ge,FeatureLayer:FeatureLayer});
      }, function(e){ clearTimeout(t); rej(e); });
  });
}

async function init(){
  M=await need();
  var app=A();
  app.map.ground=new M.Ground({layers:ELEV.map(function(u){ return new M.ElevationLayer({url:u}); })});
  massLayer=new M.GraphicsLayer({title:"3D 매스",elevationInfo:{mode:"on-the-ground"},listMode:"hide"});
  upLayer=new M.GraphicsLayer({title:"3D 매스 (수직 증축)",elevationInfo:{mode:"relative-to-ground"},listMode:"hide"});
  bldgGroup=new M.GroupLayer({title:"3D 건물",listMode:"hide"});
  view3d=new M.SceneView({map:app.map,viewingMode:"global",qualityProfile:"high",popupEnabled:false,
    environment:{atmosphereEnabled:true,starsEnabled:false},
    ui:{components:["zoom","navigation-toggle","compass"]}});
  view3d.ui.move(["zoom","navigation-toggle","compass"],"top-right"); // 왼쪽 위는 레이어 카드 자리 (2D와 같은 쪽)
  try{ view3d.highlightOptions={color:[174,182,27,1],haloOpacity:0.9,fillOpacity:0.2}; }catch(e){}
  view3d.on("click",function(e){ if(e.button===2||(window.GY_TOOLS&&GY_TOOLS.busy())) return; if(e.mapPoint) app.selectAtPoint(e.mapPoint,true); });
  view3d.watch("stationary",function(s){ if(s) refreshLod(); }); // 카메라가 멈출 때마다 둘레 건물 받기
}

// 경기도 LOD1 건물: 서비스는 3D(멀티패치)라 API가 그대로 그리면 같은 z 문제가 생김 → REST로 바닥 모양만(z 없이) 받아
//   클라이언트 레이어에 넣고 높이만큼 지면에서 세움. 카메라 둘레 400m 칸 단위로 받아 두고, 멀어진 칸은 지움 (ngii5000 건물과 같은 방식)
var TILE=400, LOD_MAX=25000, lodTiles=new Map(), lodBusy=Promise.resolve();
function lodLayer(k){
  if(!bldgLayers[k]){
    var l=new M.FeatureLayer({title:"경기도 3D 건물 ("+LOD[k].label+")",popupEnabled:false,source:[],objectIdField:"oid",geometryType:"polygon",
      spatialReference:{wkid:102100},fields:[{name:"oid",type:"oid"},{name:"sid",type:"integer"},{name:"hgt",type:"double"}],outFields:["*"],
      elevationInfo:{mode:"on-the-ground"},
      renderer:{type:"simple",symbol:{type:"polygon-3d",symbolLayers:[{type:"extrude",material:{color:[236,231,222,1]},edges:{type:"solid",color:[90,84,74,0.45],size:0.6}}]},
        visualVariables:[{type:"size",field:"hgt",valueUnit:"meters"}]}});
    l._k=k; bldgLayers[k]=l; bldgGroup.add(l);
  }
  return bldgLayers[k];
}
function refreshLod(){ lodBusy=lodBusy.then(syncLod).catch(function(e){ console.warn("3D 건물 불러오기 실패",e&&e.message); }); return lodBusy; }
async function syncLod(){
  var l=bldgLayers.lod1; if(!l||!view3d||mode!=="3d"||!view3d.ready) return;
  var sc=view3d.scale, want=new Set();
  if(sc<=25000){
    var c=view3d.center, x=c.x, y=c.y;
    if(c.spatialReference&&c.spatialReference.isGeographic){ x=c.longitude*20037508.34/180; y=Math.log(Math.tan((90+c.latitude)*Math.PI/360))*20037508.34/Math.PI; }
    var r=sc<=6000?800:1400, tx=Math.floor(x/TILE), ty=Math.floor(y/TILE), n=Math.ceil(r/TILE);
    for(var dx=-n;dx<=n;dx++) for(var dy=-n;dy<=n;dy++) want.add((tx+dx)+"/"+(ty+dy));
  }
  var del=[], count=0;
  lodTiles.forEach(function(oids,key){ if(!want.has(key)){ oids.forEach(function(o){ del.push({objectId:o}); }); lodTiles.delete(key); } else count+=oids.length; });
  if(del.length) await l.applyEdits({deleteFeatures:del});
  // 가까운 칸부터 8개씩 동시에 받아 바로바로 세움
  var cx0=Math.floor(x/TILE), cy0=Math.floor(y/TILE);
  var todo=[...want].filter(function(k){ return !lodTiles.has(k); }).sort(function(a,b){
    var p=a.split("/"), q=b.split("/"); return Math.hypot(p[0]-cx0,p[1]-cy0)-Math.hypot(q[0]-cx0,q[1]-cy0); });
  for(var i=0;i<todo.length&&count<LOD_MAX;i+=8){
    var batch=todo.slice(i,i+8); batch.forEach(function(k){ lodTiles.set(k,[]); });
    var got=await Promise.all(batch.map(loadLodTile));
    var adds=[], keys=[];
    got.forEach(function(gs,j){ gs.forEach(function(g){ adds.push(g); keys.push(batch[j]); }); });
    if(!adds.length) continue;
    var res=await l.applyEdits({addFeatures:adds});
    (res.addFeatureResults||[]).forEach(function(a,j){ if(!a.error){ var t=lodTiles.get(keys[j]); if(t){ t.push(a.objectId); count++; } } });
    hideExistingOnParcel();
    if(mode!=="3d") return;
  }
}
// 한 칸(400m)의 건물 바닥 → 높이 붙인 그래픽. 칸 경계에 걸친 건물이 두 번 들어가지 않게 중심이 이 칸에 있는 것만
function loadLodTile(key){
  var p=key.split("/").map(Number), env=[p[0]*TILE,p[1]*TILE,(p[0]+1)*TILE,(p[1]+1)*TILE].join(",");
  return fetch(LOD.lod1.url+"/query?"+new URLSearchParams({geometry:env,geometryType:"esriGeometryEnvelope",inSR:"102100",spatialRel:"esriSpatialRelEnvelopeIntersects",
    outFields:"objectid,bldg_hgt,grnd_nofl",returnGeometry:"true",returnZ:"false",outSR:"102100",maxAllowableOffset:"0.3",resultRecordCount:"4000",f:"json"}))
  .then(function(r){ return r.json(); }).then(function(d){
    var out=[];
    (d.features||[]).forEach(function(f){
      var g=f.geometry; if(!g||!g.rings||!g.rings.length) return;
      var rg=g.rings.map(function(ring){ return ring.map(function(v){ return [v[0],v[1]]; }); }), r0=rg[0], cx=0, cy=0;
      r0.forEach(function(v){ cx+=v[0]; cy+=v[1]; }); cx/=r0.length; cy/=r0.length;
      if(Math.floor(cx/TILE)!==p[0]||Math.floor(cy/TILE)!==p[1]) return;
      var a=f.attributes, h=a.bldg_hgt>0?a.bldg_hgt:(a.grnd_nofl>0?a.grnd_nofl*FLOOR_H:3);
      out.push(new M.Graphic({geometry:{type:"polygon",rings:rg,spatialReference:{wkid:102100}},attributes:{sid:a.objectid,hgt:h}}));
    });
    return out;
  }).catch(function(){ lodTiles.delete(key); return []; }); // 실패한 칸은 다음에 다시
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
// ── 기존 건물: 바닥 = 수치지형도 1:1,000 건물(고양, 필지 안), 높이 = 건축물대장 높이 → 대장 지상층수×층고 → 수치지형도 층수×층고 ──
//   행위 구분마다 3D 표현이 다름: 신축은 기존 건물 철거 가정, 증축은 기존 건물 위·옆에 덧붙임,
//   개축·재축은 종전 규모 안에서 다시 지음, 대수선·용도변경은 기존 건물 그대로(대상 건물 강조)
// 기존 건물 바닥: GIS건물통합정보(고양, 2025.10) — 건물관리번호 앞 19자리가 PNU라 그 필지 건물만 정확히 가져옴.
//   없으면(누락·신축 직후) 수치지형도 1:1,000 건물을 필지 안에서 찾음
var BLDG_INTG=HOST+encodeURIComponent("GIS건물통합_AL_D010_Goyang_2510")+"/FeatureServer/1";
var NGII_BLDG=HOST+"goyang_N1A_B0010000_building/FeatureServer/0";
var exFoot={pnu:null,st:"",fs:[]};
function loadFootprints(S){
  if(!M||exFoot.pnu===S.pnu) return;
  var cur=exFoot={pnu:S.pnu,st:"loading",fs:[],src:""};
  var k=Math.cos(S.lat*Math.PI/180), inner=M.ge.buffer(S.geom,-0.5/k,"meters")||S.geom, sr=S.geom.spatialReference;
  var parts=function(r,flField,clip){
    return r.features.map(function(f){ var g=clip?M.ge.intersect(f.geometry,S.geom):f.geometry; return g?{g:g,fl:+f.attributes[flField]||0,a:M.ge.planarArea(g,"square-meters")*k*k}:null; })
      .filter(function(x){ return x&&x.a>=5; }).sort(function(a,b){ return b.a-a.a; });
  };
  new M.FeatureLayer({url:BLDG_INTG}).queryFeatures({where:"bd_mgt_sn LIKE '"+S.pnu+"%'",outFields:["gro_flo_co"],returnGeometry:true,outSpatialReference:sr})
    .then(function(r){ cur.fs=parts(r,"gro_flo_co",false); cur.src="건물통합정보"; })
    .catch(function(){ cur.fs=[]; })
    .then(function(){
      if(cur.fs.length) return;
      return new M.FeatureLayer({url:NGII_BLDG}).queryFeatures({geometry:inner,spatialRelationship:"intersects",outFields:["층수"],returnGeometry:true,outSpatialReference:sr})
        .then(function(r){ cur.fs=parts(r,"층수",true); cur.src="수치지형도 건물"; }).catch(function(){ cur.fs=[]; });
    })
    .then(function(){ cur.st="done"; if(exFoot===cur&&mode==="3d") drawMasses(); });
}
function existing(S,k){
  if(exFoot.pnu!==S.pnu||exFoot.st!=="done") return null; // 아직 찾는 중
  var fs=exFoot.fs, b=S.bld||null, bFl=b&&+b.grndFlrCnt||0, bH=b&&+b.heit||0, bA=b&&+b.archArea||0;
  if(!fs.length&&!(bA>0)) return {none:true};
  var main=fs[0], fl=bFl||(main&&main.fl)||1, h=bH>2?bH:fl*FLOOR_H;
  var foot=fs.length? (fs.length>1?M.ge.union(fs.map(function(x){return x.g;})):main.g) : insetTo(S.geom,Math.min(bA,+S.area||bA),0.5,k);
  return {foot:foot,main:main?main.g:foot,parts:fs.length?fs:[{g:foot,fl:fl,a:bA}],fl:fl,h:h,area:M.ge.planarArea(foot,"square-meters")*k*k,
    hSrc:bH>2?"대장 높이":bFl?"대장 "+bFl+"층×"+FLOOR_H+"m":exFoot.src+" 층수",fSrc:fs.length?exFoot.src+" "+fs.length+"동":"대장 건축면적으로 추정"};
}
function curAct(){ var a=A(); return a.act?a.act():"신축"; }
function masses(){
  var app=A(), S=app.S(); if(!S||!S.zm||!S.geom||!M) return null;
  var k=Math.cos(S.lat*Math.PI/180), zm=S.zm, sa=+S.area||0, act=curAct();
  loadFootprints(S);
  // 최대 규모: 건폐율 한도 바닥 × 층수 = min(용적률/건폐율, 층수 제한)
  var maxFloors=Math.max(1,Math.floor(zm.f/zm.b));
  if(zm.h) maxFloors=Math.min(maxFloors,zm.h);
  var maxBa=sa*zm.b/100;
  var setback=0.5; // 대지 안의 공지 최소(인접대지 0.5m) 개략
  var out={act:act,ex:existing(S,k),max:{geom:insetTo(S.geom,maxBa,setback,k),floors:maxFloors,ba:maxBa,ta:Math.min(sa*zm.f/100,maxBa*maxFloors)}};
  out.max.h=maxFloors*FLOOR_H;
  var P=S.lastP&&S.lastP.act===act?S.lastP:null, ex=out.ex&&!out.ex.none?out.ex:null;
  if(act==="증축"){
    if(ex&&P){
      // 수직 증축: 계획 층수(증축 후 전체)가 기존보다 많으면 주 건물 위에 그 층만큼
      var topH=P.ht>ex.h?P.ht:(P.fl>ex.fl?ex.h+(P.fl-ex.fl)*FLOOR_H:0);
      if(topH>ex.h) out.up={geom:ex.main,base:ex.h,h:topH-ex.h,floors:P.fl>ex.fl?P.fl-ex.fl:Math.round((topH-ex.h)/FLOOR_H)};
      // 수평 증축: 증축 건축면적만큼 기존 건물 옆으로 (기존+증축 면적의 바닥에서 기존 바닥을 뺀 부분)
      if(P.ba>0){
        var env=insetTo(S.geom,Math.min(ex.area+P.ba,sa),setback,k), side=env&&M.ge.difference(env,ex.foot);
        var sideA=side?M.ge.planarArea(side,"square-meters")*k*k:0;
        if(sideA>=1) out.side={geom:side,h:ex.h,ba:P.ba,area:sideA};
      }
    }
  }else if(act==="대수선"||act==="용도변경"){
    // 규모 변화 없음: 기존 건물만
  }else if(P&&(P.ba>0||ex)&&(P.fl>0||P.ht>0)){
    // 신축·개축·재축: 계획 매스 (개축·재축은 종전 건물 자리에서 다시 지음)
    var fl=P.fl||Math.max(1,Math.round(P.ht/FLOOR_H)), ba=P.ba||(ex?ex.area:0), base=S.geom;
    if(act!=="신축"&&ex) base=ba<=ex.area*1.02?ex.foot:S.geom;
    out.plan={geom:insetTo(base,Math.min(ba,sa),base===S.geom?setback:0,k),floors:fl,ba:ba,ta:P.ta,h:P.ht||fl*FLOOR_H};
  }
  return out;
}
// 선택 필지 안 기존 건물: LOD(불투명)는 감추고, 같은 자리에 기존 건물을 반투명 '유리'로 다시 그려
//   새 매스와 겹쳐도 둘 다 보이게 함 (drawMasses). 필지를 0.5m 안쪽으로 줄여 경계 옆 이웃 건물은 그대로
function hideExistingOnParcel(){
  var S=A().S(), l=bldgLayers[bldgKind]; if(!view3d||!l) return;
  view3d.whenLayerView(l).then(function(lv){
    if(!S||!S.geom){ lv.filter=null; return; }
    var k=Math.cos(S.lat*Math.PI/180), inner=M.ge.buffer(S.geom,-0.5/k,"meters")||S.geom;
    // 3D 피처 레이어뷰는 공간 필터가 전체를 가리는 경우가 있어, 서버에서 필지 안 건물 objectid(sid)를 찾아 속성 필터로 제외
    return fetch(LOD.lod1.url+"/query",{method:"POST",body:new URLSearchParams({geometry:JSON.stringify(inner.toJSON()),geometryType:"esriGeometryPolygon",spatialRel:"esriSpatialRelIntersects",returnIdsOnly:"true",f:"json"})})
      .then(function(r){ return r.json(); }).then(function(d){
        if(A().S()!==S) return;
        var ids=d.objectIds||[];
        lv.filter=ids.length?{where:"sid NOT IN ("+ids.join(",")+")"}:null;
      });
  }).catch(function(e){ console.warn("기존 건물 숨김 실패",e&&e.message); });
}
// 체크 상태: 행위 구분이 바뀌면 그 행위의 기본값으로 (최대 규모는 신축에서만 처음부터 켬)
var chk={}, chkAct=null;
function isOn(id,def){ return id in chk?chk[id]:def; }
function syncChecks(act){
  if(act!==chkAct){ chk={}; chkAct=act; return; }
  ["m3Max","m3Plan","m3Ex"].forEach(function(id){ var e=$(id); if(e) chk[id]=e.checked; });
}
var C_PLAN=[2,87,79,0.62], C_MAX=[174,182,27,0.45]; // 기존 건물과 겹쳐도 서로 보이게 반투명
function drawMasses(){
  if(!massLayer) return;
  massLayer.removeAll(); upLayer.removeAll();
  var ms=masses(); if(!ms) { hideExistingOnParcel(); renderPanel(); return; }
  syncChecks(ms.act);
  hideExistingOnParcel();
  var ext=function(geom,h,color,edge,lyr,dash){
    if(!geom||!(h>0)) return;
    (lyr||massLayer).add(new M.Graphic({geometry:geom,symbol:{type:"polygon-3d",symbolLayers:[{type:"extrude",size:h,material:{color:color},edges:{type:"solid",color:edge,size:dash?1.5:1}}]}}));
  };
  var ex=ms.ex&&!ms.ex.none?ms.ex:null, act=ms.act;
  if(isOn("m3Max",act==="신축")) ext(ms.max.geom,ms.max.h,[C_MAX[0],C_MAX[1],C_MAX[2],ms.plan||ms.up||ms.side?0.2:C_MAX[3]],[120,126,10,0.9]);
  // 기존 건물 (반투명 유리): 대수선·용도변경은 대상 건물이라 라임색으로 강조
  if(ex&&isOn("m3Ex",true)){
    var hl=act==="대수선"||act==="용도변경";
    ex.parts.forEach(function(p,i){ ext(p.g,i===0?ex.h:Math.max(1,p.fl||1)*FLOOR_H,hl?[174,182,27,0.5]:[205,200,190,0.38],hl?[110,116,8,1]:[70,64,55,0.95]); });
  }
  if(isOn("m3Plan",true)){
    if(ms.plan) ext(ms.plan.geom,ms.plan.h,C_PLAN,[255,255,255,0.9]);
    if(ms.side) ext(ms.side.geom,ms.side.h,C_PLAN,[255,255,255,0.9]);
    if(ms.up){ // 기존 건물 지붕 높이에서 시작 (지면 기준 높이로 띄움)
      var g=ms.up.geom, up={type:"polygon",hasZ:true,spatialReference:g.spatialReference,rings:g.rings.map(function(r){ return r.map(function(p){ return [p[0],p[1],ms.up.base]; }); })};
      ext(up,ms.up.h,C_PLAN,[255,255,255,0.9],upLayer);
    }
  }
  renderPanel(ms);
}

function renderPanel(ms){
  var el=$("m3Panel"); if(!el) return;
  var S=A().S();
  if(mode!=="3d"){ el.hidden=true; return; }
  el.hidden=false;
  ms=ms||masses();
  el.classList.toggle("min",m3min);
  var h='<button class="m3-h" data-a3="min" aria-expanded="'+!m3min+'" title="패널 접기·펴기">3D 규모 검토<i class="m3-chev"></i></button>';
  if(!S){ h+='<div class="m3-empty">필지를 선택하면 최대 건축 가능 규모를 3D로 세워 보여 줍니다.</div>'; }
  else if(!ms){ h+='<div class="m3-empty">용도지역을 확인하는 중입니다…</div>'; }
  else{
    var act=ms.act, ex=ms.ex, P=S.lastP&&S.lastP.act===act;
    var row=function(id,def,sw,title,sub){ return '<label class="m3-row"><input type="checkbox" id="'+id+'"'+(isOn(id,def)?" checked":"")+'><i class="m3-sw" style="'+sw+'"></i><span><b>'+title+'</b><small>'+sub+'</small></span></label>'; };
    var SW_PLAN="background:#02574F;border-color:#fff", SW_EX="background:rgba(205,200,190,.5);border-color:#46403a";
    var exTxt=ex&&!ex.none?ex.fl+'층 · 높이 약 '+Math.round(ex.h)+'m ('+ex.hSrc+') · 바닥 약 '+n0(ex.area)+'㎡ ('+ex.fSrc+')':'';
    h+='<div class="m3-act-k">행위 구분 <b>'+act+'</b><span>사전검토 탭에서 바꿀 수 있습니다</span></div>';
    if(act!=="신축"&&!ex) h+='<div class="m3-empty">필지 안 기존 건물을 찾는 중입니다…</div>';
    else if(act!=="신축"&&ex.none) h+='<div class="m3-note">이 필지에서 기존 건물(수치지형도 건물·건축물대장)을 찾지 못했습니다. '+act+'은 기존 건물이 있어야 하는 행위입니다.</div>';
    // 기존 건물: 그대로 두고 매스와 겹쳐 보여 줌 (끄면 감춤)
    var exRow=function(title){ return row("m3Ex",true,act==="대수선"||act==="용도변경"?"background:rgba(174,182,27,.5);border-color:#6e7408":SW_EX,title,exTxt); };
    if(act==="신축"){
      if(ex&&!ex.none) h+=exRow("기존 건물 (겹쳐 보기)");
      if(ms.plan) h+=row("m3Plan",true,SW_PLAN,"신축 계획",'건축면적 '+n0(ms.plan.ba)+'㎡ · '+ms.plan.floors+'층 · 높이 약 '+Math.round(ms.plan.h)+'m');
      else h+='<div class="m3-note">사전검토 탭에서 계획(건축면적·층수)을 입력·실행하면 계획 매스도 함께 세웁니다.</div>';
    }else if(act==="증축"&&ex&&!ex.none){
      h+=exRow("기존 건물 (유지)");
      if(ms.up||ms.side) h+=row("m3Plan",true,SW_PLAN,"증축 부분",[ms.up?'수직 +'+ms.up.floors+'층 (높이 약 '+Math.round(ms.up.base+ms.up.h)+'m까지)':'',ms.side?'수평 +'+n0(ms.side.ba)+'㎡':''].filter(Boolean).join(' · '));
      else h+='<div class="m3-note">'+(P?'증축 층수가 기존('+ex.fl+'층) 이하이고 증축 건축면적이 없어 덧붙일 부분이 없습니다.':'사전검토 탭에 <b>증축 건축면적</b>(옆으로 넓힘)이나 <b>증축 후 지상 층수</b>(위로 올림)를 넣고 실행하면 기존 건물에 덧붙여 보여 줍니다.')+'</div>';
    }else if((act==="개축"||act==="재축")&&ex&&!ex.none){
      h+=exRow("종전 건물 (겹쳐 보기)");
      if(ms.plan) h+=row("m3Plan",true,SW_PLAN,act+" 계획",'건축면적 '+n0(ms.plan.ba)+'㎡ · '+ms.plan.floors+'층 · 높이 약 '+Math.round(ms.plan.h)+'m'+(ms.plan.h>ex.h+0.5||ms.plan.ba>ex.area*1.02?' · <span class="m3-warn">종전 규모 초과 → 증축·신축 검토</span>':''));
      else h+='<div class="m3-note">'+act+'은 종전 규모 범위 안에서 다시 짓는 행위입니다. 계획(건축면적·층수)을 입력·실행하면 종전 규모와 비교해 세웁니다.</div>';
    }else if(ex&&!ex.none){ // 대수선·용도변경
      h+=exRow(act+" 대상 건물 (강조)");
      h+='<div class="m3-note">'+(act==="대수선"?'대수선은 기존 건물의 주요구조부를 고치는 행위로 규모(바닥·층수·높이)는 바뀌지 않습니다.':'용도변경은 건물 규모는 그대로 두고 쓰임만 바꿉니다. 바뀐 용도 기준의 주차·소방·피난 기준은 사전검토 탭을 확인하세요.')+'</div>';
    }
    h+=row("m3Max",act==="신축",'background:rgba(174,182,27,.55);border-color:#7e8610',"최대 건축 가능 규모",'건폐율 '+S.zm.b+'% · '+ms.max.floors+'층 · 높이 약 '+Math.round(ms.max.h)+'m · 연면적 약 '+n0(ms.max.ta)+'㎡');
  }
  h+='<div class="m3-sub">일조·분석</div><div class="m3-act">'+
     '<button data-a3="winter">일조권 분석</button><button data-a3="shadow">그림자 시간</button><button data-a3="tools">3D 분석</button></div>';
  h+='<div class="m3-act"><button data-a3="fly">필지로 이동</button><button data-a3="top">위에서 보기</button></div>';
  h+='<div class="m3-foot">매스는 층고 '+FLOOR_H+'m · 대지경계 0.5m 이격 기준 개략 형태입니다. 높이·사선·지구단위계획 제한은 반영되지 않습니다. 건물: 경기도 3D 건물 LOD1(2025.8).</div>';
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

function cadLabels(on){
  var c=A().map.layers.find(function(l){ return l.title==="연속지적도"; });
  if(c) c.labelsVisible=on;
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
    if(!app.map.layers.includes(upLayer)) app.map.layers.add(upLayer);
    setBldg(bldgKind);
    cadLabels(false); // 3D에서는 지번 글자가 땅에 깔려 건물·매스를 가림 → 지적선만
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
    refreshLod();
    app.toast(matchMedia("(pointer: coarse)").matches?"두 손가락으로 끌면 기울이거나 돌려 볼 수 있습니다":"마우스 오른쪽 버튼으로 끌면 기울이거나 돌려 볼 수 있습니다 · 오른쪽 클릭: 3D 분석 메뉴",5000);
  }else{
    var vp3=view3d&&view3d.viewpoint?view3d.viewpoint.clone():null;
    if(view3d) view3d.container=null;
    app.map.layers.removeMany([bldgGroup,massLayer,upLayer]); // 3D 건물·매스는 2D 지도에 그릴 수 없음
    cadLabels(true);
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
  var t=e.target.closest("[data-mode],[data-a3]"); if(!t) return;
  if(t.dataset.mode){ setMode(t.dataset.mode); return; }
  var a=t.dataset.a3;
  if(a==="min"){
    if(document.body.classList.contains("tool-open")&&window.GY_TOOLS) GY_TOOLS.close(); // 도구 때문에 접혀 있으면 도구를 닫고 펼침
    else m3min=!m3min;
    renderPanel(); return;
  }
  if(a==="fly") flyToParcel(false);
  else if(a==="top") flyToParcel(true);
  else if(a==="winter"&&window.GY_TOOLS) GY_TOOLS.run("sun",{date:WINTER,title:"일조권 분석 (동지 12월 22일)",hint:"일조권 검토 기준일인 동지 정오의 해와 그림자를 보여 줍니다. 시각 막대를 끌거나 ▶ 를 눌러 9시~15시 그림자를 확인하세요 (건축법 시행령 제86조 일조 기준 참고)."});
  else if(a==="shadow"&&window.GY_TOOLS) GY_TOOLS.run("shadow",{date:WINTER,hint:"동지(12월 22일) 하루 동안 그늘이 지는 시간을 색으로 보여 줍니다. 날짜와 시간 범위를 바꿔 볼 수 있습니다."});
  else if(a==="tools"&&window.GY_TOOLS) GY_TOOLS.run("list");
});
document.addEventListener("change",function(e){
  if(e.target.id==="m3Max"||e.target.id==="m3Plan"||e.target.id==="m3Ex") drawMasses();
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
