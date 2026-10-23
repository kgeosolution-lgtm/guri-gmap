/* 고양특례시 건축 인허가 사전검토 — app.js
 * 지도/조회/렌더링. 조례 수치·판정 기준은 rules.js(GY)에 있음.
 */
(function(){
"use strict";

// ═══ 설정 ═══
var API = "/app/regulation/api.py";
var ZONE_PROXY = "/app/regulation/zone_proxy.py";
var PORTAL = "https://kgeodata.com/portal";
var HOST = "https://kgeodata.com/server/rest/services/Hosted/";
// 배경지도 = 포털 웹 지도: 일반(바로e맵 Std) · 수치지형도(1:5,000 전국 주제별 레이어 + 바로e맵) · 위성
var BM = { general:"a177f5017b52486b930463f900da4d71", ngii:"cffd232c6fdd4ce5be34d38868fcb282", satellite:"d6e738240ab2402095b4bb11c28ef320" };
var URL_ = {
  boundary: HOST+encodeURIComponent("고양시경계")+"/FeatureServer/0",
  gu: HOST+encodeURIComponent("센서스용행정구역경계_시군구_2024년")+"/FeatureServer/4",
  cadastral: HOST+encodeURIComponent("연속지적도형정보_20260208")+"/FeatureServer/14",
  zone: HOST+encodeURIComponent("용도지역_VW")+"/FeatureServer/",
  gb: HOST+encodeURIComponent("개발제한구역_ALL")+"/FeatureServer/8",
  culture: HOST+encodeURIComponent("LSMD_CONT_UO301_문화재_문화재보호")+"/FeatureServer/4",
  farm: HOST+encodeURIComponent("용도지역지구_FS")+"/FeatureServer/1",
  livestock: HOST+encodeURIComponent("용도지역지구_FS")+"/FeatureServer/5",
  dup: HOST+encodeURIComponent("지구단위계획")+"/FeatureServer/4",
  permits: HOST+"kgeodata_permit/FeatureServer/4",
  flood: HOST+encodeURIComponent("침수흔적도_2025")+"/FeatureServer/0"
};
var GOYANG_SGG = "41280";
var GU = { "41281":"덕양구", "41285":"일산동구", "41287":"일산서구" };
var GU_CENSUS = { "31101":"덕양구", "31103":"일산동구", "31104":"일산서구" };
var BLD_KEY = "VoPvixR66zdLB0V1%2BSjPkIaS8WW96VBQsi4Kxz5VdLyPoAvYroUouW1f5AJWOiC7pKkqPtluTmVphNA%2FLoKInw%3D%3D";
var BLD_API = {
  title:"https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo",
  recap:"https://apis.data.go.kr/1613000/BldRgstHubService/getBrRecapTitleInfo",
  floor:"https://apis.data.go.kr/1613000/BldRgstHubService/getBrFlrOulnInfo"
};
var JIMOK = {"대":"대지","전":"전","답":"답","과":"과수원","목":"목장용지","임":"임야","광":"광천지","염":"염전","장":"공장용지","학":"학교용지","주":"주차장","도":"도로","하":"하천","구":"구거","유":"유지","체":"체육용지","수":"수도용지","공":"공원","철":"철도용지","제":"제방","묘":"묘지","사":"사적지","종":"종교용지","잡":"잡종지","양":"양어장","원":"유원지","창":"창고용지","천":"하천"};
var ZONE_COLOR = {
  "제1종전용주거":"#FFFFBE","제2종전용주거":"#FFFF00","제1종일반주거":"#FFE14D","제2종일반주거":"#FFB547","제3종일반주거":"#FF8C1A",
  "준주거":"#FF9E9E","중심상업":"#E01E5A","일반상업":"#FF5C8A","근린상업":"#FF8FB1","유통상업":"#FFB3C7",
  "전용공업":"#6C63FF","일반공업":"#9C95FF","준공업":"#C7B8FF",
  "보전녹지":"#1E7B34","생산녹지":"#46A85B","자연녹지":"#8FD18F",
  "보전관리":"#C9A27E","생산관리":"#DEC08F","계획관리":"#F3D9B5","농림":"#9BC59D","자연환경보전":"#3CB371"
};
var ZONE_CODE = {
  UQA111:"제1종전용주거",UQA112:"제2종전용주거",UQA121:"제1종일반주거",UQA122:"제2종일반주거",UQA123:"제3종일반주거",UQA130:"준주거",
  UQA210:"중심상업",UQA220:"일반상업",UQA230:"근린상업",UQA240:"유통상업",UQA310:"전용공업",UQA320:"일반공업",UQA330:"준공업",
  UQA410:"보전녹지",UQA420:"생산녹지",UQA430:"자연녹지",UQB100:"계획관리",UQB200:"생산관리",UQB300:"보전관리",UQC001:"농림",UQD001:"자연환경보전"
};
var USES = [
  {g:"주거",items:["단독주택","공동주택"]},
  {g:"근린생활",items:["제1종근린생활시설","제2종근린생활시설"]},
  {g:"상업·업무",items:["판매시설","업무시설","숙박시설","문화및집회시설"]},
  {g:"산업",items:["공장","창고시설"]},
  {g:"공공·기타",items:["교육연구시설","의료시설","운동시설","기타"]}
];
var ACTS = ["신축","증축","개축","재축","대수선","용도변경"];

// ═══ 상태 ═══
var S = null;               // 현재 필지
var view, map, cadastral, gfxSel, gfxNear, goyangGeom = null, goyangExtent = null, guLayer;
var layers = {};
var E = {};                 // esri 모듈

// ═══ 유틸 ═══
function $(id){ return document.getElementById(id); }
function esc(s){ return String(s==null?"":s).replace(/[&<>"']/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];}); }
function n0(v){ return Math.round(v).toLocaleString("ko-KR"); }
function n1(v){ return (Math.round(v*10)/10).toLocaleString("ko-KR"); }
function toast(m,ms){ var t=$("toast"); t.textContent=m; t.classList.add("on"); clearTimeout(toast._t); toast._t=setTimeout(function(){t.classList.remove("on");},ms||2800); }
function loading(on,msg){ $("loading").classList.toggle("on",!!on); if(msg) $("loading").querySelector("span").textContent=msg; }
function jimokFull(j){ return JIMOK[j]||j||"-"; }
function guOf(pnu){ return GU[(pnu||"").substring(0,5)]||""; }
function fmtDate(s){ s=String(s||""); return s.length>=8? s.substring(0,4)+"."+s.substring(4,6)+"."+s.substring(6,8) : (s||"-"); }
// api.py는 CP949 바이트를 utf-8로 선언해서 내려줌 → 바이트를 직접 판별해 디코딩
function decodeJson(buf){
  var txt;
  try{ txt=new TextDecoder("utf-8",{fatal:true}).decode(buf); }
  catch(e){ txt=new TextDecoder("euc-kr").decode(buf); }
  return JSON.parse(txt);
}
function getJson(url){ return fetch(url).then(function(r){ return r.arrayBuffer(); }).then(decodeJson); }
function api(p){ return getJson(API+"?"+Object.keys(p).map(function(k){return k+"="+encodeURIComponent(p[k]);}).join("&")); }
function lawLink(name,art){ return "https://www.law.go.kr/법령/"+encodeURIComponent(name)+(art?"/"+encodeURIComponent(art):""); }
function ordLink(name){ return "https://www.law.go.kr/자치법규/"+encodeURIComponent(name); }
function openModal(html){ $("modalBody").innerHTML=html; $("modal").hidden=false; }
function closeModal(){ $("modal").hidden=true; }

// ═══ 지도 ═══
require([
  "esri/config","esri/Map","esri/WebMap","esri/views/MapView","esri/layers/FeatureLayer","esri/layers/GraphicsLayer",
  "esri/Graphic","esri/geometry/Polygon","esri/geometry/Point","esri/geometry/geometryEngine","esri/widgets/Home","esri/widgets/ScaleBar",
  "esri/layers/VectorTileLayer","esri/layers/TileLayer","esri/geometry/Polyline"
], function(esriConfig,Map,WebMap,MapView,FeatureLayer,GraphicsLayer,Graphic,Polygon,Point,geometryEngine,Home,ScaleBar,VectorTileLayer,TileLayer,Polyline){
  E={Graphic:Graphic,Polygon:Polygon,Polyline:Polyline,Point:Point,ge:geometryEngine,FeatureLayer:FeatureLayer};
  esriConfig.portalUrl=PORTAL;

  map=new Map({basemap:"gray-vector"});
  setBasemap("general");

  // ── 용도지역 (용도지역_VW: 도시/관리/농림/자연환경보전) ──
  var zuv=[]; Object.keys(ZONE_CODE).forEach(function(c){ zuv.push({value:c,symbol:{type:"simple-fill",color:ZONE_COLOR[ZONE_CODE[c]],outline:{color:[60,60,60,0.35],width:0.4}}}); });
  layers.zone=[37,38,3,13].map(function(id){
    return new FeatureLayer({url:URL_.zone+id,outFields:["code","description"],definitionExpression:"col_adm_se='"+GOYANG_SGG+"'",
      renderer:{type:"unique-value",field:"code",uniqueValueInfos:zuv,defaultSymbol:{type:"simple-fill",color:[200,200,200,0.4],outline:{color:[90,90,90,0.4],width:0.4}}},
      labelingInfo:[{labelExpressionInfo:{expression:"$feature.description"},symbol:{type:"text",color:"#222",haloColor:"#fff",haloSize:1.2,font:{size:9,weight:"bold"}},minScale:20000}],
      opacity:0.5,visible:false,title:"용도지역"});
  });
  function regLayer(url,fill,line,style,title,defExp){
    return new FeatureLayer({url:url,definitionExpression:defExp||null,visible:false,opacity:0.7,title:title,
      renderer:{type:"simple",symbol:{type:"simple-fill",color:fill,outline:{color:line,width:2,style:style||"solid"}}}});
  }
  layers.gb=regLayer(URL_.gb,[229,56,59,0.22],[196,38,42],"solid","개발제한구역","col_adm_se='"+GOYANG_SGG+"'");
  layers.dup=regLayer(URL_.dup,[47,111,222,0.12],[47,111,222],"dash","지구단위계획구역","signgu_se='"+GOYANG_SGG+"'");
  layers.culture=regLayer(URL_.culture,[224,123,0,0.25],[201,106,0],"dash","문화유산 보호구역");
  layers.farm=regLayer(URL_.farm,[46,160,90,0.25],[30,120,60],"solid","농업진흥지역","col_adm_se='"+GOYANG_SGG+"'");
  layers.livestock=regLayer(URL_.livestock,[245,180,0,0.2],[210,140,0],"dash","가축사육제한구역","col_adm_se='"+GOYANG_SGG+"'");
  layers.flood=regLayer(URL_.flood,[47,111,222,0.35],[30,80,190],"solid","침수흔적","adm_cd_w LIKE '4128%'");

  // ── 연속지적도 (고양시만) ──
  cadastral=new FeatureLayer({
    url:URL_.cadastral,definitionExpression:"a7='"+GOYANG_SGG+"'",
    outFields:["a1","a3","a4","a5","SHAPE__Area"],minScale:12000,title:"연속지적도",
    renderer:{type:"simple",symbol:{type:"simple-fill",color:[0,0,0,0],outline:{color:[255,255,255,0.75],width:0.7}}},
    labelingInfo:[{labelExpressionInfo:{expression:"var s=$feature.a5;if(IsEmpty(s))return '';return s"},
      symbol:{type:"text",color:[255,255,255],haloColor:[20,30,40,0.85],haloSize:1.1,font:{size:9,family:"sans-serif"}},minScale:3000,labelPlacement:"always-horizontal",deconflictionStrategy:"static"}]
  });

  // ── 행정구 경계: 정적 사본(gy_bounds.js) — 서버 서비스가 바뀌어도 지도 틀은 유지 ──
  guLayer=new GraphicsLayer({title:"행정구"});
  var guLabels=[];
  if(window.GY_BOUNDS) GY_BOUNDS.gu.forEach(function(g){
    var geom=new Polygon({spatialReference:{wkid:102100},rings:g.rings});
    guLayer.add(new Graphic({geometry:geom,attributes:{cd:g.cd,nm:g.nm},symbol:{type:"simple-fill",color:[0,0,0,0],outline:{color:[255,255,255,0.9],width:1.6,style:"dash"}}}));
    var lbl=new Graphic({geometry:geom.centroid,symbol:{type:"text",text:g.nm,color:"#fff",haloColor:[0,60,70,0.9],haloSize:2,font:{size:15,weight:"bold",family:"sans-serif"}}});
    guLayer.add(lbl); guLabels.push(lbl);
  });

  // ── 수치지형도 1:1,000 (고양시 피처 서비스) ──
  layers.ngii={};
  NGII_UI.forEach(function(n){
    var o={url:HOST+n.svc+"/FeatureServer/0",title:n.n,visible:false,minScale:n.minScale||0,outFields:n.out||[],renderer:n.r,popupEnabled:false};
    if(n.lbl){
      var li={labelExpressionInfo:{expression:n.lbl.expr},maxScale:0,minScale:n.lbl.max||0, // minScale: 이 축척보다 확대했을 때만 글자 표시
        symbol:{type:"text",color:n.lbl.color,haloColor:[255,255,255,0.95],haloSize:1.3,font:{size:n.lbl.size||9,weight:"bold",family:"sans-serif"}}};
      if(n.svc.indexOf("N1L")>=0) li.labelPlacement="center-along";
      o.labelingInfo=[li];
    }
    layers.ngii[n.id]=new FeatureLayer(o);
  });
  // ── 음영기복 (고양시 DEM) ──
  layers.hill=new TileLayer({url:HOST+"Hillshade_Goyang/MapServer",title:"음영기복",visible:false,opacity:0.45,blendMode:"multiply"});

  var gfxMask=new GraphicsLayer({title:"고양시 외곽"}), gfxBnd=new GraphicsLayer({title:"고양시 경계"});
  gfxSel=new GraphicsLayer({title:"선택 필지"}); gfxNear=new GraphicsLayer({title:"주변사례"});
  var ngiiList=NGII_UI.map(function(n){return layers.ngii[n.id];});
  map.addMany([layers.hill].concat(layers.zone,[layers.farm,layers.livestock,layers.gb,layers.culture,layers.dup,layers.flood],ngiiList,[cadastral,gfxMask,guLayer,gfxBnd,gfxNear,gfxSel]));

  view=new MapView({container:"viewDiv",map:map,center:[126.835,37.66],zoom:12,
    constraints:{minZoom:10,maxZoom:20,rotationEnabled:false},
    popup:{autoOpenEnabled:false},ui:{components:["zoom"]}});
  view.ui.move("zoom","top-right");
  var homeWidget=new Home({view:view});
  view.ui.add(homeWidget,"top-right");
  view.ui.add(new ScaleBar({view:view,unit:"metric"}),"bottom-right");

  // 구 이름: 너무 확대하거나(필지 단위) 너무 축소하면(휴대폰 전체 화면에서 겹침) 숨김
  view.watch("scale",function(s){ var on=s>30000&&s<250000; guLabels.forEach(function(l){ l.visible=on; }); });

  // ── 고양시 경계: 외곽 마스크 + 경계선 + 이동 제한 (정적 사본 우선, 없으면 서비스) ──
  var bnd = window.GY_BOUNDS
    ? Promise.resolve({features:[{geometry:new Polygon({spatialReference:{wkid:102100},rings:GY_BOUNDS.boundary})}]})
    : new FeatureLayer({url:URL_.boundary}).queryFeatures({where:"1=1",returnGeometry:true,outSpatialReference:{wkid:102100}});
  bnd.then(function(fs){
    if(!fs.features.length) return;
    goyangGeom=fs.features[0].geometry;
    goyangExtent=goyangGeom.extent;
    var world=new Polygon({spatialReference:{wkid:102100},rings:[[[-20037508,-20037508],[-20037508,20037508],[20037508,20037508],[20037508,-20037508],[-20037508,-20037508]]]});
    var outside=geometryEngine.difference(world,goyangGeom);
    gfxMask.add(new Graphic({geometry:outside,symbol:{type:"simple-fill",color:[12,22,32,0.58],outline:null}}));
    gfxBnd.add(new Graphic({geometry:goyangGeom,symbol:{type:"simple-fill",color:[0,0,0,0],outline:{color:hexA(cssVar("--brand-accent"),0.45),width:9}}}));
    gfxBnd.add(new Graphic({geometry:goyangGeom,symbol:{type:"simple-fill",color:[0,0,0,0],outline:{color:hexA(cssVar("--brand"),1),width:2.6}}}));
    view.constraints.geometry=goyangExtent.clone().expand(1.5);
    homeExtent=goyangExtent.clone().expand(1.08);
    view.when(function(){
      view.goTo(homeExtent,{duration:0}).then(function(){ homeWidget.viewpoint=view.viewpoint.clone(); });
    });
  }).catch(function(e){ console.warn("고양시 경계 로드 실패",e); });

  view.on("click",function(e){ if(e.button===2||(window.GY_TOOLS&&GY_TOOLS.busy())) return; selectAtPoint(e.mapPoint,true); }); // 오른쪽 버튼은 메뉴, 재기·그리기 중에는 필지 선택 안 함
  // 안내 문구: 필지 선택 전에만, 축척에 맞춰
  view.watch("scale",updateHint);
  view.when(updateHint);

  buildLayerPanel();
  window.__gy={view:view,map:map,layers:layers};
  // scene3d.js(3D 규모 검토)에 넘겨줄 것
  window.GYAPP={map:map,view:view,S:function(){return S;},act:function(){return plan.act;},selectAtPoint:selectAtPoint,toast:toast,loading:loading};
  // 지도 도구(tools.js): 내 위치·거리·면적·오른쪽 버튼 메뉴, 3D 분석
  if(window.GY_TOOLS) GY_TOOLS.init({map:map,view2d:view,
    setMode:function(m){ return window.GY3D?GY3D.setMode(m):Promise.resolve(); },
    select:function(pt){ selectAtPoint(pt,true); },
    note:function(t,ms){ if(t) toast(t,ms); }});
  view.when(function(){ setTimeout(openFromUrl,300); });
});
var homeExtent=null;
function updateHint(){
  var el=$("mapHint"); if(!el||!view) return;
  if(S){ el.classList.add("off"); return; }
  el.textContent=view.scale>12000?"확대하거나 주소를 검색하세요":"필지를 누르면 검토를 시작합니다";
  el.classList.remove("off");
}

function cssVar(n){ return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }
function hexA(hex,a){ hex=(hex||"#00A0B0").replace("#",""); if(hex.length===3)hex=hex.split("").map(function(c){return c+c;}).join(""); return [parseInt(hex.substr(0,2),16),parseInt(hex.substr(2,2),16),parseInt(hex.substr(4,2),16),a]; }

// 배경에 따라 지적선·글자 색 바꿈 (위성: 흰 선 / 일반·지형도: 진회색 선)
function styleForBasemap(t){
  if(!cadastral) return;
  var dark=t!=="satellite";
  cadastral.renderer={type:"simple",symbol:{type:"simple-fill",color:[0,0,0,0],outline:{color:dark?[70,80,90,0.75]:[255,255,255,0.75],width:dark?0.6:0.7}}};
  var li=cadastral.labelingInfo&&cadastral.labelingInfo[0];
  if(li){ li=li.clone(); li.symbol.color=dark?[40,50,60]:[255,255,255]; li.symbol.haloColor=dark?[255,255,255,0.9]:[20,30,40,0.85]; cadastral.labelingInfo=[li]; }
  if(guLayer) guLayer.graphics.forEach(function(g){ var s=g.symbol&&g.symbol.clone(); if(!s) return;
    if(s.type==="simple-fill") s.outline.color=dark?[2,87,79,0.9]:[255,255,255,0.9];
    else if(s.type==="text"){ s.color=dark?[2,61,55]:[255,255,255]; s.haloColor=dark?[255,255,255,0.95]:[0,60,70,0.9]; }
    g.symbol=s; });
}
// 웹 지도 한 번만 읽어 둠: 배경(basemap)과, 수치지형도는 주제 레이어 묶음(토지이용·지형·수계·건물·교통·행정경계·시설·지명·도곽)
var bmCache={}, bmSeq=0, ngiiGroup=null;
function loadBm(t){
  if(!bmCache[t]) bmCache[t]=new Promise(function(res,rej){
    require(["esri/WebMap"],function(WebMap){
      var wm=new WebMap({portalItem:{id:BM[t]}});
      wm.load().then(function(){
        var grp=t==="ngii"?wm.layers.getItemAt(0):null;
        if(grp){ wm.layers.remove(grp); grp.listMode="hide"; }
        res({basemap:wm.basemap,group:grp});
      }).catch(function(e){ bmCache[t]=null; rej(e); });
    },rej);
  });
  return bmCache[t];
}
function setBasemap(t){
  var my=++bmSeq;
  document.querySelectorAll("#bmSeg button").forEach(function(b){ b.classList.toggle("active",b.dataset.bm===t); });
  styleForBasemap(t);
  loadBm(t).then(function(r){
    if(my!==bmSeq) return; // 그사이 다른 배경을 누름
    map.basemap=r.basemap;
    if(ngiiGroup&&ngiiGroup!==r.group) map.remove(ngiiGroup);
    ngiiGroup=r.group;
    if(ngiiGroup&&!map.layers.includes(ngiiGroup)) map.add(ngiiGroup,0); // 수치지형도 주제 레이어는 규제·지적 레이어 아래
  }).catch(function(){
    if(my!==bmSeq) return;
    if(ngiiGroup){ map.remove(ngiiGroup); ngiiGroup=null; }
    if(t==="ngii"){ toast("수치지형도를 불러오지 못해 일반 지도로 보여 드립니다"); setBasemap("general"); return; }
    map.basemap=t==="satellite"?"satellite":"gray-vector";
  });
}

// ═══ 레이어 패널 ═══
// 수치지형도 1:1,000 — 고양시 (서버 호스팅 피처, 국토지리정보원 원천)
//   ※ 포털의 1:5,000 벡터타일(NGII5000_*)은 고양 일부(킨텍스·주엽 등) z14~16 타일이 비어 있어 사용하지 않음 (2026-10-22 확인)
var NGII_UI=[
  {id:"ng_road",svc:"goyang_N1A_A0010000_road_boundary",n:"도로 (도로경계)",c:"#C9CED4",minScale:20000,
    r:{type:"simple",symbol:{type:"simple-fill",color:[236,239,242,0.55],outline:{color:[120,130,140,0.9],width:0.6}}}},
  {id:"ng_cl",svc:"goyang_N1L_A0020000_road_centerline",n:"도로중심선 (도로명·폭)",c:"#F0A020",minScale:12000,out:["도로명","도로폭","차로수"],
    r:{type:"simple",symbol:{type:"simple-line",color:[240,160,32,0.85],width:1.2,style:"dash"}},
    lbl:{expr:"var n=Trim($feature.도로명); var w=$feature.도로폭; return IIF(IsEmpty(n)||n=='',''+w+'m',n+' '+w+'m')",color:[150,90,0],max:4000}},
  {id:"ng_bldg",svc:"goyang_N1A_B0010000_building",n:"건물 (층수)",c:"#B98A52",minScale:8000,out:["층수","용도","명칭"],
    r:{type:"simple",symbol:{type:"simple-fill",color:[214,170,110,0.55],outline:{color:[150,105,50,0.9],width:0.6}}},
    lbl:{expr:"IIF($feature.층수>1, $feature.층수+'층', '')",color:[90,55,10],max:2500}},
  {id:"ng_contour",svc:"goyang_N1L_F0010000_contour",n:"등고선",c:"#A16207",minScale:15000,out:["등고수치","구분"],
    r:{type:"simple",symbol:{type:"simple-line",color:[161,98,7,0.75],width:0.8}},
    lbl:{expr:"$feature.등고수치+'m'",color:[140,80,0],max:6000}},
  {id:"ng_river",svc:"goyang_N1A_E0032111_river",n:"하천 (실폭하천)",c:"#0EA5E9",minScale:150000,
    r:{type:"simple",symbol:{type:"simple-fill",color:[14,165,233,0.35],outline:{color:[2,132,199,0.9],width:0.8}}}},
  {id:"ng_label",svc:"goyang_N1P_H0040000_place_name",n:"지명",c:"#3D4A57",minScale:40000,out:["명칭"],
    r:{type:"simple",symbol:{type:"simple-marker",size:3,color:[61,74,87,0.8],outline:null}},
    lbl:{expr:"$feature.명칭",color:[30,40,50],max:0,size:10}}
];
var LAYER_UI=[
  {g:"기본"},
  {id:"cadastral",n:"연속지적도",c:"#ffffff",on:true,line:true},
  {id:"gu",n:"행정구 경계",c:"#ffffff",on:true,line:true},
  {g:"수치지형도 1:1,000 (고양시)"}
].concat(NGII_UI.map(function(n){ return {id:n.id,n:n.n,c:n.c}; }),[
  {id:"hill",n:"음영기복 (고양시 DEM)",c:"linear-gradient(135deg,#ddd,#777)"},
  {g:"도시계획"},
  {id:"zone",n:"용도지역",c:"linear-gradient(135deg,#FFB547,#FF5C8A 50%,#8FD18F)"},
  {id:"dup",n:"지구단위계획구역",c:"#2F6FDE"},
  {g:"규제"},
  {id:"gb",n:"개발제한구역",c:"#E5383B"},
  {id:"culture",n:"문화유산 보호구역",c:"#E07B00"},
  {id:"farm",n:"농업진흥지역",c:"#2EA05A"},
  {id:"livestock",n:"가축사육제한구역",c:"#F5B400"},
  {g:"재해"},
  {id:"flood",n:"침수흔적 (2006~2024)",c:"#2F6FDE"}
]);
function layerObj(id){ return id==="cadastral"?cadastral:id==="gu"?guLayer:/^ng_/.test(id)?layers.ngii[id]:layers[id]; }
function buildLayerPanel(){
  var h="";
  LAYER_UI.forEach(function(l){
    if(l.g){ h+='<div class="lyr-g">'+l.g+'</div>'; return; }
    h+='<label class="lyr"><i class="sw" style="background:'+l.c+(l.line?';border:2px solid #6b7785':'')+'"></i><span>'+l.n+'</span>'+
       '<span class="tgl"><input type="checkbox" data-lyr="'+l.id+'"'+(l.on?" checked":"")+'><b></b></span></label>';
  });
  h+='<div class="opa">투명도<input type="range" min="15" max="90" value="55" id="opaRange"></div>';
  $("layerBody").innerHTML=h;
  $("layerBody").addEventListener("change",function(e){
    var id=e.target.dataset.lyr; if(!id) return;
    var on=e.target.checked, L=layerObj(id);
    (Array.isArray(L)?L:[L]).forEach(function(x){ if(x) x.visible=on; });
    if(id==="zone") renderLegend(on);
  });
  $("opaRange").addEventListener("input",function(e){
    var o=e.target.value/100;
    layers.zone.forEach(function(z){z.opacity=o;});
    ["gb","culture","farm","livestock","dup","flood"].forEach(function(k){ layers[k].opacity=Math.min(1,o+0.15); });
  });
  $("layerHead").onclick=function(){ $("layerCard").classList.toggle("collapsed"); };
  if(window.innerWidth<820) $("layerCard").classList.add("collapsed");
  checkLayerHealth();
}
// 서버 서비스가 다른 자료로 덮어써지는 경우가 있어, 로드 실패한 레이어는 패널에서 비활성화
function checkLayerHealth(){
  LAYER_UI.forEach(function(l){
    if(!l.id||l.id==="gu") return;
    var L=layerObj(l.id); if(!L) return;
    Promise.all((Array.isArray(L)?L:[L]).map(function(x){ return x.load(); })).catch(function(e){
      console.warn("레이어 서비스 오류:",l.n,e&&e.message);
      var inp=document.querySelector('[data-lyr="'+l.id+'"]'); if(!inp) return;
      inp.checked=false; inp.disabled=true;
      var row=inp.closest(".lyr"); row.style.opacity=.45; row.title="서비스 점검 중";
      row.querySelector("span").textContent=l.n+" (점검 중)";
      (Array.isArray(L)?L:[L]).forEach(function(x){ x.visible=false; });
      if(l.id==="dup") window.__dupBroken=true;
    });
  });
}
function renderLegend(on){
  var el=$("legendCard"); if(!on){ el.hidden=true; return; }
  var h='<h4>용도지역</h4>';
  Object.keys(ZONE_COLOR).forEach(function(k){ h+='<div class="lg"><i style="background:'+ZONE_COLOR[k]+'"></i>'+k+'</div>'; });
  el.innerHTML=h; el.hidden=false;
}

// ═══ 필지 선택 ═══
function selectAtPoint(mapPoint,fromClick){
  if(goyangGeom && E.ge){
    var p=mapPoint;
    if(p.spatialReference && p.spatialReference.isWGS84){
      require(["esri/geometry/support/webMercatorUtils"],function(wmu){ var q=wmu.geographicToWebMercator(p); if(!E.ge.intersects(goyangGeom,q)){ toast("고양특례시 관할 구역의 필지만 검토할 수 있습니다"); return; } go(); });
      return;
    }
    if(!E.ge.intersects(goyangGeom,p)){ toast("고양특례시 관할 구역의 필지만 검토할 수 있습니다"); return; }
  }
  go();
  function go(){
    loading(true,"필지 정보를 불러오는 중");
    cadastral.queryFeatures({geometry:mapPoint,spatialRelationship:"intersects",outFields:["a1","a3","a4","a5","SHAPE__Area"],returnGeometry:true,outSpatialReference:view.spatialReference})
    .then(function(fs){
      if(!fs.features.length){ loading(false); toast("해당 위치에서 필지를 찾지 못했습니다"); return; }
      var f=fs.features[0];
      // 공시지가 등(VWorld)은 좌표로 조회되므로, 경계 근처 오조회를 막기 위해 필지 내부 점 사용
      var c=f.geometry&&f.geometry.centroid, inner=(c&&E.ge.contains(f.geometry,c))?c:mapPoint;
      var lon=inner.longitude, lat=inner.latitude;
      loadParcel(f,lon,lat,!fromClick);
    }).catch(function(e){ loading(false); console.error(e); toast("지적도 조회 중 오류가 발생했습니다"); });
  }
}

function loadParcel(feat,lon,lat,zoomTo){
  var a=feat.attributes, pnu=a.a1||"";
  var raw=a.a5||"", jm=raw.replace(/[0-9\-산\s]/g,"").trim();
  var area=a.SHAPE__Area? Math.round(parseFloat(a.SHAPE__Area)*Math.pow(Math.cos(lat*Math.PI/180),2)*10)/10 : 0; // Web Mercator 면적 보정
  highlight(feat.geometry);
  // 검색했거나, 클릭했어도 필지가 잘 안 보일 만큼 축소된 상태면 필지로 확대
  if(window.GY3D&&GY3D.is3d()){ /* 3D에서는 scene3d.js가 카메라를 옮김 */ }
  else if(zoomTo||view.scale>4000) view.goTo({target:feat.geometry.extent.clone().expand(3.2)},{duration:700});
  else view.goTo({center:[lon,lat]},{duration:400});

  Promise.all([
    api({action:"get_regulation",pnu:pnu}).catch(function(){return {};}),
    api({action:"get_all",lon:lon,lat:lat}).catch(function(){return {};})
  ]).then(function(res){
    loading(false);
    var reg=res[0]||{}, all=res[1]||{}, prc=(all.parcel&&all.parcel.pnu===pnu)?all.parcel:{};
    S={
      pnu:pnu, gu:guOf(pnu), lon:lon, lat:lat, geom:feat.geometry,
      addr:"고양시 "+(a.a3||"").replace(/^(경기도\s*)?고양시\s*/,"")+" "+(a.a4||""),
      dong:(a.a3||"").split(" ").pop(), jibun:a.a4||"", jimok:jm,
      area:parseFloat(prc.area)||area, price:prc.price||null, priceYear:prc.price_year||"",
      road:prc.road_name||"", reg:reg, station:all.station||null, bld:null
    };
    analyzeZones();
    renderParcel(); renderReviewForm(); renderReg(); renderProc();
    $("tab-bld").innerHTML=bldSkeleton(); fetchBuilding(pnu);
    $("tab-near").innerHTML=""; gfxNear.removeAll(); nearSel=-1;
    $("intro").hidden=true; $("result").hidden=false; switchTab("review"); $("panelScroll").scrollTop=0;
    if(!S.zone||!S.price) zoneFallback();
    if(S.flags.dup.length) resolveDup();
    updateHint(); setShareUrl(); analyzeTerrain(); analyzeRoads(); analyzeFlood();
    if(window.GY3D) GY3D.parcelChanged();
  }).catch(function(e){ loading(false); console.error(e); toast("필지 정보 조회에 실패했습니다"); });
}

function highlight(geom){
  gfxSel.removeAll(); if(!geom) return;
  gfxSel.add(new E.Graphic({geometry:geom,symbol:{type:"simple-fill",color:hexA(cssVar("--brand-accent"),0.3),outline:{color:[255,255,255,1],width:6}}}));
  gfxSel.add(new E.Graphic({geometry:geom,symbol:{type:"simple-fill",color:[0,0,0,0],outline:{color:hexA(cssVar("--brand-accent"),1),width:3}}}));
}

// ── 용도지역 판별: '포함' 우선 (접함은 인접 용도지역) ──
function normZone(nm){
  if(!nm) return "";
  var n=nm.replace(/\s/g,"").replace(/지역$/,"");
  if(GY.zones[n]) return n;
  for(var k in GY.zones){ if(n.indexOf(k)>=0) return k; }
  return "";
}
function analyzeZones(){
  var r=S.reg||{}, list=(r.zones||[]).slice();
  (r.all||[]).forEach(function(x){ if((x.code||"").match(/^UQ[A-D]/) && !list.some(function(z){return z.code===x.code;})) list.push(x); });
  var inc=list.filter(function(z){return z.conflict==="포함"||z.conflict_code==="1";}).map(function(z){return normZone(z.name);}).filter(Boolean);
  var part=list.filter(function(z){return z.conflict==="저촉"||z.conflict_code==="2";}).map(function(z){return normZone(z.name);}).filter(Boolean);
  var adj=list.filter(function(z){return z.conflict==="접함"||z.conflict_code==="3";}).map(function(z){return normZone(z.name);}).filter(Boolean);
  var all=inc.concat(part);
  S.zone=all[0]||"";
  S.zoneMulti=uniq(all);
  S.zoneAdj=uniq(adj).filter(function(z){return S.zoneMulti.indexOf(z)<0;});
  // 규제 플래그
  var names=(r.all||[]).map(function(x){return x.name||"";});
  S.regNames=names;
  S.zm=S.zone?GY.effective(S.zone,names):null;
  S.flags={
    gb: names.some(function(n){return n.indexOf("개발제한구역")>=0;}),
    military: names.filter(function(n){return /군사|보호구역|비행안전|비행장|대공방어/.test(n)&&!/문화|유산|상수원|수산|어린이|노인|장애인|생태|습지|야생|교육환경|상대보호|절대보호/.test(n);}),
    culture: names.filter(function(n){return /문화재|문화유산|국가유산|역사문화/.test(n);}),
    water: names.filter(function(n){return /상수원|수질보전|수변구역/.test(n);}),
    dup: names.filter(function(n){return /지구단위계획/.test(n);}),
    landDeal: names.some(function(n){return /토지거래/.test(n);}),
    farmZone: names.filter(function(n){return /농업진흥/.test(n);}),
    forest: names.filter(function(n){return /보전산지|공익용산지|임업용산지/.test(n);}),
    river: names.filter(function(n){return /하천구역|소하천|홍수관리/.test(n);}),
    facility:(r.all||[]).filter(function(x){return /^UQS|^UQT/.test(x.code||"") && (x.conflict==="저촉"||x.conflict_code==="2"||x.conflict==="포함"||x.conflict_code==="1");}).map(function(x){return {n:x.name,c:(x.conflict==="포함"||x.conflict_code==="1")?"포함":"저촉"};}),
    overcrowd: names.some(function(n){return /과밀억제/.test(n);}),
    growth: names.filter(function(n){return /성장관리/.test(n);}),
    landscape: names.filter(function(n){return /경관지구/.test(n);}),
    height: names.filter(function(n){return /고도지구/.test(n);})
  };
}
function uniq(a){ return a.filter(function(v,i){return a.indexOf(v)===i;}); }
// ═══ 지형 분석: 고양시 5m 등고선으로 표고·평균경사 추정 ═══
// 평균경사 (Wentworth): tanθ ≈ 등고선간격 × 필지 안 등고선 총길이 ÷ 필지 면적
var contourLayer=null;
function analyzeTerrain(){
  if(!S||!S.geom||!E.ge) return;
  var pnu=S.pnu, g=S.geom, k=Math.cos(S.lat*Math.PI/180);
  contourLayer=contourLayer||new E.FeatureLayer({url:HOST+"Goyang_Contour_5m/FeatureServer/0"});
  var area=E.ge.buffer(g,100/k,"meters"); // 평지는 필지 안에 등고선이 없어 주변 100m 등고선으로 표고 범위를 잡음
  contourLayer.queryFeatures({geometry:area,spatialRelationship:"intersects",outFields:["contour"],returnGeometry:true,outSpatialReference:view.spatialReference,maxAllowableOffset:0.5})
  .then(function(fs){
    if(!S||S.pnu!==pnu) return;
    var inside=[], around=[], L=0;
    fs.features.forEach(function(f){
      var v=f.attributes.contour; around.push(v);
      var c=E.ge.intersect(f.geometry,g);
      if(c){ var len=E.ge.planarLength(c,"meters")*k; if(len>0.5){ L+=len; inside.push(v); } }
    });
    var t={n:inside.length};
    var vals=inside.length?inside:around;
    if(vals.length){ t.min=Math.min.apply(null,vals); t.max=Math.max.apply(null,vals); }
    if(inside.length){ t.slope=Math.atan(5*L/S.area)*180/Math.PI; }
    else { t.flat=true; t.slopeLt=Math.atan(5/Math.sqrt(S.area))*180/Math.PI; } // 5m 등고선이 지나지 않음 → 높이차 5m 미만
    S.terrain=t;
    renderParcel(); judge(true);
  }).catch(function(e){ console.warn("지형 분석 실패",e&&e.message); });
}
// ═══ 침수 이력: 침수흔적도(2006~2024 기록) 중 필지와 겹치는 것 — 연도·최대 침수심 ═══
function analyzeFlood(){
  if(!S||!S.geom||!layers.flood) return;
  var pnu=S.pnu;
  layers.flood.queryFeatures({geometry:S.geom,spatialRelationship:"intersects",outFields:["flud_year_","flud_year1","indd_s"],returnGeometry:false})
  .then(function(fs){
    if(!S||S.pnu!==pnu) return;
    var ys={}, d=0;
    fs.features.forEach(function(f){ var a=f.attributes; [a.flud_year_,a.flud_year1].forEach(function(y){ y=String(y||"").trim(); if(/^\d{4}$/.test(y)) ys[y]=1; }); d=Math.max(d,+a.indd_s||0); });
    S.flood={n:fs.features.length,years:Object.keys(ys).sort(),depth:Math.round(d*100)/100};
    renderParcel(); judge(true);
  }).catch(function(e){ console.warn("침수 이력 조회 실패",e&&e.message); if(S&&S.pnu===pnu){ S.flood={err:true}; renderParcel(); } });
}
// ═══ 접도 분석: 수치지형도 1:1,000 도로경계(면)·도로중심선(폭) ═══
//   접도 길이 = 필지 경계 중 도로경계면에서 1m 이내인 부분, 도로 폭 = 필지에서 (폭/2+2m) 안에 있는 중심선의 도로폭
var roadBndLayer=null, roadClLayer=null;
function analyzeRoads(){
  if(!S||!S.geom||!E.ge) return;
  var pnu=S.pnu, g=S.geom, k=Math.cos(S.lat*Math.PI/180);
  roadBndLayer=roadBndLayer||new E.FeatureLayer({url:HOST+"goyang_N1A_A0010000_road_boundary/FeatureServer/0"});
  roadClLayer=roadClLayer||new E.FeatureLayer({url:HOST+"goyang_N1L_A0020000_road_centerline/FeatureServer/0"});
  var q=function(L,d,f,where){ return L.queryFeatures({where:where||"1=1",geometry:E.ge.buffer(g,d/k,"meters"),spatialRelationship:"intersects",outFields:f,returnGeometry:true,outSpatialReference:view.spatialReference}); };
  Promise.all([
    q(roadBndLayer,3,["objectid"]),                                   // 현황 도로면
    q(cadastral,0.5,["a1","a5"],"a7='"+GOYANG_SGG+"' AND a5 LIKE '%도'"), // 인접 지목 '도로' 필지
    q(roadClLayer,45,["도로명","도로폭","차로수","도로구분"])
  ]).then(function(r){
    if(!S||S.pnu!==pnu) return;
    var edge=new E.Polyline({paths:g.rings,spatialReference:g.spatialReference});
    function touchLen(feats,tol){
      var gs=feats.map(function(f){return f.geometry;}).filter(function(x){return x;}); if(!gs.length) return 0;
      var t=E.ge.intersect(edge,E.ge.buffer(E.ge.union(gs),tol/k,"meters"));
      return t? E.ge.planarLength(t,"meters")*k : 0;
    }
    var roadParcels=r[1].features.filter(function(f){return f.attributes.a1!==pnu;});
    var contactLegal=touchLen(roadParcels,0.5), contactPhys=touchLen(r[0].features,2);
    var contact=Math.max(contactLegal,contactPhys);
    var adj=[];
    r[2].features.forEach(function(f){
      var a=f.attributes, w=parseFloat(a.도로폭)||0; if(!w) return;
      var d=E.ge.distance(g,f.geometry,"meters")*k;
      if(d<=w/2+8) adj.push({name:(a.도로명||"").trim(),w:w,lanes:a.차로수,kind:a.도로구분,d:d});
    });
    adj.sort(function(a,b){return b.w-a.w;});
    var seen={}, list=adj.filter(function(x){ var key=(x.name||"-")+x.w; if(seen[key]) return false; seen[key]=1; return true; }).slice(0,4);
    S.roadInfo={contact:contact,contactLegal:contactLegal,contactPhys:contactPhys,roads:list,maxW:list.length?list[0].w:0,roadParcels:roadParcels.map(function(f){return (f.attributes.a5||"").trim();}).slice(0,4)};
    renderParcel(); // 입지 요약의 접도
    if(S.lastP) judge(true);
  }).catch(function(e){ console.warn("접도 분석 실패",e&&e.message); });
}
function terrainText(t){
  if(!t) return {elev:"분석 중",slope:"분석 중"};
  var elev = t.min==null ? "평지" : (t.min===t.max ? t.min+"m" : t.min+"~"+t.max+"m");
  var slope = t.flat ? "완만" : t.slope.toFixed(1)+"°";
  return {elev:elev,slope:slope};
}
// ═══ 공유 링크 (?pnu=) ═══
function setShareUrl(){ try{ history.replaceState(null,"",location.pathname+"?pnu="+S.pnu); }catch(_){ } }
function openFromUrl(){
  var pnu=(new URLSearchParams(location.search)).get("pnu");
  if(!pnu||!/^4128\d{15}$/.test(pnu)) return;
  loading(true,"공유된 필지를 여는 중");
  cadastral.queryFeatures({where:"a1='"+pnu+"'",outFields:["a1","a3","a4","a5","SHAPE__Area"],returnGeometry:true,outSpatialReference:view.spatialReference}).then(function(fs){
    if(!fs.features.length){ loading(false); toast("공유된 필지를 찾지 못했습니다"); return; }
    var f=fs.features[0], c=f.geometry.centroid;
    loadParcel(f,c.longitude,c.latitude,true);
  }).catch(function(){ loading(false); });
}
// 지구단위계획 구역 식별: 서버 폴리곤(objectid) + 법정동 → rules.js dupDistricts
function resolveDup(){
  var pnu=S.pnu, g=S.geom, pt=(g&&g.centroid&&E.ge.contains(g,g.centroid))?g.centroid:g;
  function done(ids){ if(!S||S.pnu!==pnu) return; S.dupList=GY.dupDistricts(ids,S.dong,S.jibun,S.lon,S.lat); renderParcel(); }
  // 폴리곤 서비스가 없거나 실패하면 법정동 기준으로만 판별
  if(window.__dupBroken){ done([]); return; }
  layers.dup.queryFeatures({geometry:pt,spatialRelationship:"intersects",outFields:["objectid"],returnGeometry:false})
    .then(function(fs){ done(fs.features.map(function(f){return f.attributes.objectid;})); })
    .catch(function(e){ console.warn("지구단위계획 폴리곤 조회 실패 → 법정동 기준",e&&e.message); window.__dupBroken=true; done([]); });
}
function dupModal(i){
  var c=(S.dupList||[])[i]; if(!c) return; var z=c.z, dec=z.decision||{};
  var h='<h3>'+esc(z.name)+'</h3><div class="sub">'+esc((z.gu||[]).join("·"))+' · '+esc((z.dongs||[]).join(", "))+(dec.no?' · 최신 결정 '+esc(dec.no)+' ('+esc(dec.date||"")+')':'')+(z.status==="partial"?' · <b style="color:var(--warn)">일부 조사</b>':'')+'</div>';
  h+='<table class="tb"><tr><th>블록 유형</th><th>건폐율</th><th>용적률</th><th>층수·높이</th></tr>';
  (z.blocks||[]).forEach(function(b){ var f=b.far||{};
    h+='<tr><td><b>'+esc(b.type)+'</b>'+(b.zone?'<br><small style="color:var(--muted)">'+esc(b.zone)+'</small>':'')+(b.allowed?'<br><small>허용: '+esc(String(b.allowed).slice(0,120))+'</small>':'')+'</td><td>'+(b.bcr!=null?b.bcr+'%':'<small>조례</small>')+'</td><td>'+(f.max||f.allowed||f.base?esc([f.base,f.allowed,f.max].filter(Boolean).join(" / "))+'%':'<small>조례</small>')+'</td><td><small>'+esc(b.floors||b.height||"-")+'</small></td></tr>'; });
  h+='</table><p class="hint" style="margin-top:10px">필지가 속한 블록은 결정도로 확인하세요. 「조례」는 시행지침이 도시계획 조례를 준용하는 항목입니다.'+(dec.url?' <a href="'+esc(dec.url)+'" target="_blank" rel="noopener">결정 고시 ›</a>':'')+'</p>';
  openModal(h);
}
function zoneFallback(){
  getJson(ZONE_PROXY+"?pnu="+S.pnu).then(function(d){
    if(!S||d.pnu!==S.pnu) return;
    var changed=false;
    if(!S.price&&parseFloat(d.price)){ S.price=parseFloat(d.price); S.priceYear="토지특성"; changed=true; }
    var z=!S.zone&&normZone(d.zone_name||"");
    if(z){ S.zone=z; S.zoneMulti=[z]; S.zm=GY.effective(z,S.regNames||[]); S.zoneSrc="토지특성정보"; renderReviewFormKeep(); changed=true; }
    if(changed) renderParcel();
  }).catch(function(){});
}

// ═══ 탭 ═══
function switchTab(t){
  document.querySelectorAll("#tabs .tab").forEach(function(b){ b.classList.toggle("active",b.dataset.tab===t); });
  document.querySelectorAll(".tab-body").forEach(function(b){ b.classList.toggle("active",b.id==="tab-"+t); });
  if(t==="near" && S && !$("tab-near").innerHTML) renderNear();
}

// ═══ 필지 카드 ═══
function renderParcel(){
  var p=S, zm=p.zm, h='';
  h+='<div class="pc-top"><div class="pc-tags"><span class="tag brand">'+esc(p.gu||"고양시")+'</span><span class="tag">'+esc(p.dong)+'</span><span class="tag">'+esc(jimokFull(p.jimok))+'</span>'+(p.road?'<span class="tag">'+esc(p.road)+'</span>':'')+'</div>';
  h+='<div class="pc-addr">'+esc(p.addr)+'</div>';
  h+='<div class="pc-sub">PNU '+esc(p.pnu)+'<span class="pc-actions"><button data-act="copyPnu">복사</button><button data-act="share">🔗 공유</button><button data-mode="3d" title="최대 건축 가능 규모를 3D로 봅니다">▲ 3D 규모</button></span></div></div>';
  var tt=terrainText(p.terrain);
  h+='<div class="pc-facts"><div class="pc-fact"><span>대지면적</span><b>'+(p.area?n0(p.area)+'㎡':'-')+'</b><small>'+(p.area?n0(p.area/3.3058)+'평':'')+'</small></div>';
  h+='<div class="pc-fact"><span>공시지가</span><b>'+(p.price?n0(p.price/10000)+'만원':'-')+'</b><small>'+(p.price?'㎡당'+(p.priceYear&&/^\d+$/.test(p.priceYear)?' · '+esc(p.priceYear):''):'')+'</small></div>';
  h+='<div class="pc-fact"><span>표고</span><b>'+esc(tt.elev)+'</b><small>등고선 추정</small></div>';
  h+='<div class="pc-fact"><span>평균경사</span><b>'+esc(tt.slope)+'</b><small>'+(p.terrain&&p.terrain.flat?'높이차 5m 미만':p.terrain&&p.terrain.slope>=15?'<span style="color:var(--fail)">15° 이상</span>':'개발행위 기준 15°')+'</small></div></div>';
  // 입지 요약: 가까운 역(규제 API) · 침수 이력(침수흔적도) · 접도(수치지형도)
  var loc=[], st=p.station&&p.station.closest, ri=p.roadInfo;
  if(st) loc.push(["","🚇",esc(st.name)+"역 "+(st.line?esc(st.line)+(/^\d+$/.test(st.line)?"호선":"")+" ":"")+n0(st.distance)+"m"+(p.station.grade?" · "+esc(p.station.grade):"")]);
  if(p.flood) loc.push(p.flood.err?["","💧","침수 이력 확인 불가"]:p.flood.n?["warn","💧",esc(p.flood.years.join("·"))+"년 침수 이력"]:["ok","💧","침수 이력 없음"]);
  if(ri) loc.push(ri.contact?["ok","🛣",(ri.maxW?"폭 "+n1(ri.maxW)+"m 도로":"도로")+"에 접함"]:["warn","🛣","접도 확인 필요"]);
  if(loc.length) h+='<div class="pc-loc">'+loc.map(function(x){ return '<span class="'+x[0]+'"><i>'+x[1]+'</i>'+x[2]+'</span>'; }).join("")+'</div>';

  h+='<div class="zone-band">';
  if(p.zone){
    h+='<div class="zone-name"><i class="zone-sw" style="background:'+(ZONE_COLOR[p.zone]||"#ddd")+'"></i>'+esc(p.zone)+'지역'+
      (p.zoneMulti.length>1?'<span class="zone-also">걸침: '+esc(p.zoneMulti.slice(1).join(", "))+'</span>':(p.zoneAdj.length?'<span class="zone-also">인접: '+esc(p.zoneAdj.join(", "))+'</span>':''))+'</div>';
    h+='<div class="kpis">'+kpi("건폐율",zm.b,"%",zm.bArt)+kpi("용적률",zm.f,"%",zm.fArt)+kpi("층수",zm.h||"—",zm.h?"층":"",zm.h?zm.hNote:"용도지역 층수제한 없음")+'</div>';
    if(zm.adj&&zm.adj.length) h+='<div class="zone-src" style="color:var(--info)"><span>지구·구역 조정: '+esc(zm.adj.join(" · "))+'</span></div>';
    h+='<div class="zone-src"><span>'+esc(GY.src.urban.name)+(S.zoneSrc?' · '+esc(S.zoneSrc):'')+'</span><a href="#" data-act="zoneTable">고양시 기준표 ›</a></div>';
  }else{
    h+='<div class="zone-name"><i class="zone-sw"></i><span style="color:var(--muted)">용도지역 확인 중…</span></div>';
  }
  h+='</div>';
  // 경고 배너
  var al=[];
  if(p.flags.gb) al.push(["fail","⛔","개발제한구역","시행령 별표1의 허용 시설·규모만 가능 (주택·근생은 3층·232㎡ 등) — 사전검토에서 계획별로 판정합니다"]);
  if(p.flags.facility.length){ var fullF=p.flags.facility.some(function(x){return x.c==="포함";});
    al.push([fullF?"fail":"warn","⚠","도시·군계획시설 "+(fullF?"포함":"일부 저촉"),"시설 부지는 결정 목적 외 건축 제한 — "+p.flags.facility.slice(0,3).map(function(x){return x.n+"("+x.c+")";}).join(", ")]); }
  if(p.flags.military.length){ var dm=p.flags.military.map(function(n){var m=n.match(/\((해발)?고도\s?(\d+(?:\.\d+)?)\s?m/);return m?(m[1]?"해발 ":"")+m[2]+"m":null;}).filter(Boolean);
    al.push(["warn","🛡","군사시설 보호구역",(dm.length?"위임고도 "+dm.join("·")+" 이하는 고양시 자체 처리, 초과 시 관할부대 협의":"신축·증축 등은 관할부대 협의 필요")+" — "+p.flags.military[0].replace(/<[^>]*>/g,"")]); }
  if(p.flags.culture.length) al.push(["warn","🏛","문화유산 영향 구역","국가유산 현상변경 검토 필요 — "+p.flags.culture.slice(0,2).join(", ")]);
  var dupHtml="";
  if(p.flags.dup.length){
    if(p.dupList&&p.dupList.length) dupHtml=p.dupList.slice(0,3).map(function(c,i){ return '<button class="chip" style="margin:6px 4px 0 0;padding:4px 10px;font-size:12px" data-dup="'+i+'">'+esc(c.z.name.replace(/\(.*$/,"").trim())+(c.certain===true?'':c.certain==="dong"?' (동 기준)':c.certain==="near"?' (위치 추정)':' (후보)')+' ›</button>'; }).join("");
    al.push(["info","ℹ","지구단위계획구역","결정 내용(용도·건폐율·용적률·높이)이 조례보다 우선 적용됩니다"+(p.dupList&&!p.dupList.length?" — 조사된 34개 구역 밖이니 토지이음에서 결정도를 확인하세요":""),true]);
  }
  al.forEach(function(a){ h+='<div class="alert '+a[0]+'"><span class="a-ico">'+a[1]+'</span><div><b>'+a[2]+'</b>'+esc(a[3])+(a[4]?'<div>'+dupHtml+'</div>':'')+'</div></div>'; });
  $("parcelCard").innerHTML=h;
}
function kpi(label,val,unit,note){ return '<div class="kpi"><span>'+label+'</span><b>'+val+'<small>'+unit+'</small></b><em>'+esc(note||"")+'</em></div>'; }

function zoneTable(){
  var cats=[["주거지역",["제1종전용주거","제2종전용주거","제1종일반주거","제2종일반주거","제3종일반주거","준주거"]],["상업지역",["중심상업","일반상업","근린상업","유통상업"]],["공업지역",["전용공업","일반공업","준공업"]],["녹지지역",["보전녹지","생산녹지","자연녹지"]],["관리·농림·자연환경보전",["보전관리","생산관리","계획관리","농림","자연환경보전"]]];
  var h='<h3>고양특례시 용도지역별 건축 기준</h3><div class="sub">'+esc(GY.src.urban.name)+' ('+esc(GY.src.urban.date)+') · 국토계획법 시행령 제84조·제85조</div>';
  h+='<table class="tb"><tr><th>용도지역</th><th>건폐율</th><th>용적률</th><th>법정 상한</th><th>층수</th></tr>';
  cats.forEach(function(c){
    h+='<tr><td colspan="5" style="font-weight:800;color:var(--muted);background:var(--bg)">'+c[0]+'</td></tr>';
    c[1].forEach(function(k){ var z=GY.zones[k], nat=GY.national[k]||{};
      h+='<tr'+(S&&S.zone===k?' class="sel"':'')+'><td><i class="dot" style="background:'+ZONE_COLOR[k]+'"></i>'+k+'</td><td>'+z.b+'%</td><td><b>'+z.f+'%</b></td><td style="color:var(--muted)">'+(nat.b||"-")+'% / '+(nat.f||"-")+'%</td><td>'+(z.h?z.h+'층':'—')+'</td></tr>'; });
  });
  h+='</table><p class="hint" style="margin-top:10px">지구단위계획구역·개발진흥지구 등은 별도 결정 내용이 우선합니다. <a href="'+GY.src.urban.url+'" target="_blank" rel="noopener">조례 원문 ›</a></p>';
  openModal(h);
}

// ═══ 사전검토 입력 ═══
var plan={act:"신축",use:"제1종근린생활시설",sub:"소매점 1천㎡ 미만"};
var PER_UNIT=/다가구주택|오피스텔|생활숙박/;
// 세부용도 목록 (research/06 — 건축법 시행령 별표1 기준 77종). 데이터가 없으면 13개 대분류로 동작
function parentList(){ return GY.subParents&&GY.subParents.length? GY.subParents : USES.reduce(function(a,g){return a.concat(g.items);},[]); }
function subsOf(parent){ return GY.sub? GY.sub.uses.filter(function(u){return u.p===parent;}) : []; }
function needUnits(){ return plan.use==="공동주택"||PER_UNIT.test(plan.sub||""); }
function renderReviewForm(){
  var h='<div class="card" id="planForm"><div class="card-t">건축계획 입력<small>필수: 면적 또는 층수 중 1개 이상</small></div>';
  h+='<div class="field"><label>행위 구분</label><div class="chips" id="actChips">';
  ACTS.forEach(function(a){ h+='<button class="chip'+(plan.act===a?' on':'')+'" data-v="'+a+'">'+a+'</button>'; });
  h+='</div></div>';
  var subs=subsOf(plan.use);
  if(subs.length&&!subs.some(function(u){return u.k===plan.sub;})) plan.sub=subs[0].k;
  h+='<div class="field"><label>건축물 용도 <span style="font-weight:500;color:var(--muted)">'+(plan.act==="용도변경"?"(변경 후 용도)":"")+'</span></label>';
  h+='<div class="grid2" style="grid-template-columns:1fr 1.25fr;gap:6px"><select class="select" id="inPar" aria-label="대분류">';
  parentList().forEach(function(p){ h+='<option'+(plan.use===p?' selected':'')+'>'+esc(p)+'</option>'; });
  h+='</select><select class="select" id="inUse" aria-label="세부 용도">';
  if(subs.length) subs.forEach(function(u){ h+='<option value="'+esc(u.k)+'"'+(plan.sub===u.k?' selected':'')+'>'+esc(u.k)+'</option>'; });
  else h+='<option value="">(세부 구분 없음)</option>';
  h+='</select></div><div class="hint" id="useHint"></div></div>';
  if(plan.act==="용도변경"){
    var cur=(S.bld&&S.bld.mainPurpsCdNm)||"", pick="";
    if(cur&&GY.sub){ var hit=GY.sub.uses.filter(function(u){return cur.indexOf(u.k)>=0;})[0]||GY.sub.uses.filter(function(u){return u.p===cur||cur.indexOf(u.p.replace("시설",""))>=0;})[0]; pick=hit?hit.k:""; }
    h+='<div class="field"><label>현재(변경 전) 용도</label><select class="select" id="inFrom"><option value="">선택</option>';
    if(GY.sub) parentList().forEach(function(p){ h+='<optgroup label="'+esc(p)+'">'; subsOf(p).forEach(function(u){ h+='<option value="'+esc(u.k)+'"'+(pick===u.k?' selected':'')+'>'+esc(u.k)+'</option>'; }); h+='</optgroup>'; });
    else parentList().forEach(function(p){ h+='<option>'+esc(p)+'</option>'; });
    h+='</select><div class="hint">건축물대장 주용도: '+esc(cur||"조회 전/없음")+'</div></div>';
  }
  // 증축: 면적은 '증축 부분'(기존과 합산해 판정), 층수·높이는 '증축 후 전체'
  var add=plan.act==="증축"?"증축 ":"";
  if(add){ var eb=S.bld; h+='<div class="hint" style="margin:-4px 0 10px 4px">기존 건물(건축물대장): '+(eb?'지상 '+(eb.grndFlrCnt||"?")+'층 · 건축면적 '+(eb.archArea?n1(eb.archArea)+'㎡':'?')+' · 연면적 '+(eb.totArea?n1(eb.totArea)+'㎡':'?'):'조회 전/없음')+'<br>면적은 <b>늘어나는 부분만</b>, 층수는 <b>증축 후 전체 층수</b>를 넣으세요.</div>'; }
  h+='<div class="grid2"><div class="field"><label for="inBa">'+add+'건축면적</label><div class="num"><input type="number" id="inBa" min="0" inputmode="decimal" placeholder="0"><i>㎡</i></div></div>';
  h+='<div class="field"><label for="inTa">'+add+'연면적 (지상+지하)</label><div class="num"><input type="number" id="inTa" min="0" inputmode="decimal" placeholder="0"><i>㎡</i></div></div>';
  h+='<div class="field"><label for="inFa">'+add+'용적률 산정 연면적</label><div class="num"><input type="number" id="inFa" min="0" inputmode="decimal" placeholder="미입력 시 연면적"><i>㎡</i></div></div>';
  h+='<div class="field"><label for="inFl">'+(add?'증축 후 ':'')+'지상 층수 / 높이</label><div class="grid2" style="gap:6px"><div class="num"><input type="number" id="inFl" min="0" placeholder="0" aria-label="지상 층수"><i>층</i></div><div class="num"><input type="number" id="inHt" min="0" placeholder="0" aria-label="높이(m)"><i>m</i></div></div></div>';
  h+='<div class="field"><label for="inUf">지하 층수</label><div class="num"><input type="number" id="inUf" min="0" placeholder="0"><i>층</i></div></div>';
  h+='<div class="field"><label>분양 목적</label><label class="lyr" style="padding:9px 10px;border:1.5px solid var(--line);border-radius:var(--r-sm);background:#fff"><span>분양 목적 건축물</span><span class="tgl"><input type="checkbox" id="inSale"><b></b></span></label></div>';
  if(S.flags&&S.flags.gb) h+='<div class="field" style="grid-column:1/-1"><label>개발제한구역 거주 요건</label><label class="lyr" style="padding:9px 10px;border:1.5px solid var(--line);border-radius:var(--r-sm);background:#fff"><span>개발제한구역 지정 당시부터 거주 (지정당시거주자)</span><span class="tgl"><input type="checkbox" id="inGbRes"><b></b></span></label></div>';
  if(needUnits()) h+='<div class="field"><label>세대(호실) 수 / 세대당 전용면적</label><div class="grid2" style="gap:6px"><div class="num"><input type="number" id="inHh" min="0" placeholder="0" aria-label="세대(호실) 수"><i>세대</i></div><div class="num"><input type="number" id="inUa" min="0" placeholder="84" aria-label="세대당 전용면적"><i>㎡</i></div></div></div>';
  h+='</div>';
  if(S.area&&S.zm) h+='<div class="hint" style="margin:-4px 0 10px 4px">최대 건축면적 약 <b>'+n0(S.area*S.zm.b/100)+'㎡</b> · 최대 용적률 연면적 약 <b>'+n0(S.area*S.zm.f/100)+'㎡</b> <button data-act="fillMax">최대치 채우기</button></div>';
  h+='<button class="btn-primary block" data-act="judge">사전검토 실행</button></div><div id="reviewOut"></div>';
  $("tab-review").innerHTML=h;
  updateUseHint();
}
function updateUseHint(){
  var el=$("useHint"); if(!el||!S) return;
  var u=$("inUse").value, r=S.zone&&GY.sub&&GY.sub.matrix[S.zone]&&GY.sub.matrix[S.zone][u];
  if(!r) r=S.zone&&GY.useZone[S.zone]&&GY.useZone[S.zone][plan.use];
  if(!r){ el.innerHTML=""; return; }
  var map_={ok:["ok","건축 가능"],cond:["warn","조건부 가능"],no:["fail","건축 불가"]}[r.s]||["na","확인 필요"];
  el.innerHTML='<span class="tag '+map_[0]+'">'+S.zone+' · '+map_[1]+'</span> '+esc(r.c||"");
}
function val(id){ var e=$(id); return e?parseFloat(e.value)||0:0; }

// ═══ 판정 엔진 ═══
// silent: 지형·접도 분석이 나중에 끝났을 때 이미 실행한 검토를 조용히 갱신
function judge(silent){
  if(!S) return;
  if(silent&&(!S.lastP||!$("reviewOut")||!$("reviewOut").innerHTML)) return;
  var from=$("inFrom")?$("inFrom").value:"", fromSub=GY.subByKey&&GY.subByKey[from];
  var P={act:plan.act,use:plan.use,sub:$("inUse").value,from:from,fromParent:fromSub?fromSub.p:from,ba:val("inBa"),ta:val("inTa"),fa:val("inFa"),fl:Math.round(val("inFl")),ht:val("inHt"),hh:Math.round(val("inHh")),ua:val("inUa"),uf:Math.round(val("inUf")),sale:!!($("inSale")&&$("inSale").checked),gbResident:!!($("inGbRes")&&$("inGbRes").checked)};
  if(!P.fa) P.fa=P.ta;
  if(!P.ba&&!P.ta&&!P.fl){ if(!silent) toast("건축면적·연면적·층수 중 하나 이상 입력하세요"); return; }
  plan.sub=P.sub; S.lastP=P;
  var C=GY.judge(S,P,{jimokFull:jimokFull,n0:n0,n1:n1});
  renderVerdict(C,P,silent);
  if(window.GY3D) GY3D.refresh();
}

var GROUPS=[["site","입지·규제"],["use","용도"],["scale","규모·밀도"],["proc","절차"],["duty","설치의무·부담"]];
function renderVerdict(C,P,silent){
  var cnt={fail:0,warn:0,ok:0};
  C.forEach(function(c){ if(cnt[c.st]!=null) cnt[c.st]++; });
  var ov=cnt.fail?"fail":cnt.warn?"warn":"ok";
  var title={fail:"건축 곤란 항목 있음",warn:"조건부 가능 · 확인 필요",ok:"사전검토 적합"}[ov];
  var desc={fail:"부적합 항목을 해소하지 않으면 허가가 어렵습니다. 아래 상세 근거를 확인하세요.",warn:"기준은 충족하나 협의·추가 확인이 필요한 항목이 있습니다.",ok:"입력한 계획이 주요 기준을 충족합니다. 세부 설계 시 관계 법령을 재확인하세요."}[ov];
  var permit=C.filter(function(c){return c.key==="permitType";})[0];
  var h='<div class="print-only" style="margin-bottom:10px"><b style="font-size:16px">고양특례시 건축 인허가 사전검토 결과</b><br><span style="font-size:12px;color:#666">'+esc(S.addr)+' · PNU '+S.pnu+' · '+new Date().toLocaleString("ko-KR")+'</span><br><span style="font-size:12px">계획: '+esc(P.act+" / "+(P.sub||P.use)+" / 건축면적 "+n0(P.ba)+"㎡ / 연면적 "+n0(P.ta)+"㎡ / "+P.fl+"층")+'</span>'+
    '<div id="printMap" style="margin-top:8px"></div></div>';
  h+='<div class="verdict '+ov+'"><div class="verdict-k">'+esc(S.zone?S.zone+"지역":"")+' · '+esc(P.act)+' · '+esc(P.use)+'</div><div class="verdict-v">'+title+'</div><div class="verdict-d">'+desc+'</div>';
  h+='<div class="verdict-cnt"><span>부적합 '+cnt.fail+'</span><span>확인 '+cnt.warn+'</span><span>적합 '+cnt.ok+'</span>'+(permit?'<span>'+esc(permit.v)+'</span>':'')+'</div>';
  h+='<div class="verdict-act"><button data-act="print">🖨 검토서 인쇄·PDF</button><button data-act="openAll">전체 펼치기</button><button data-act="onlyIssues">확인 필요 항목만</button></div></div>';
  h+=role==="officer"?officerCard(C,P,permit,cnt,title):citizenCard(C,P,permit);
  GROUPS.forEach(function(g){
    var items=C.filter(function(c){return c.g===g[0];}); if(!items.length) return;
    h+='<div class="grp"><div class="grp-t"><b>'+g[1]+'</b>'+items.length+'</div>';
    items.forEach(function(c){ h+=chkHtml(c); });
    h+='</div>';
  });
  h+='<p class="hint" style="padding:0 4px 12px">본 결과는 공간정보·조례 기준에 따른 <b>참고용 사전검토</b>이며 법적 효력이 없습니다. 실제 허가 여부는 관할 구청 건축부서의 검토로 결정됩니다.</p>';
  $("reviewOut").innerHTML=h;
  if(!silent) $("reviewOut").scrollIntoView({behavior:"smooth",block:"start"});
}
// ═══ 사용자 구분: 민원인(신청 준비) / 담당 공무원(접수·검토) ═══
var role=(function(){ try{ return localStorage.getItem("gy_role")==="officer"?"officer":"citizen"; }catch(e){ return "citizen"; } })();
var HERO={citizen:'필지 하나만 고르면<br><em>고양시 조례 기준</em>으로 바로 검토합니다',
  officer:'신청 필지의 규제·기준을 한 번에 확인하고<br><em>검토 의견 초안</em>까지 만듭니다'};
function applyRole(r){
  role=r; try{ localStorage.setItem("gy_role",r); }catch(e){}
  document.body.classList.toggle("role-officer",r==="officer");
  document.querySelectorAll("#roleSeg button").forEach(function(b){ b.classList.toggle("active",b.dataset.role===r); });
  var h2=document.querySelector(".intro-hero h2"); if(h2) h2.innerHTML=HERO[r];
  if(S&&S.lastP) judge(true);
}
var ST_WORD={ok:"적합",warn:"확인 필요",fail:"부적합",info:"참고",na:"-"};
// 민원인: 인허가 종류·접수처·준비 서류 (이 필지의 협의 항목에서 의제 서류를 더함)
function docList(P,pv){
  var docs=[], act=P.act;
  if(act==="용도변경"){
    if(/기재변경/.test(pv)) docs.push(["건축물대장 기재내용 변경 신청서","같은 시설군 안의 변경 (건축법 제19조④)"]);
    else docs.push([/허가/.test(pv)?"건축·대수선·용도변경 허가신청서":"건축·대수선·용도변경 신고서","건축법 시행규칙 제12조의2"]);
    docs.push(["변경하려는 층의 변경 전·후 평면도",""],["용도변경에 따른 내화·방화·피난·건축설비 관련 도서","해당 시"]);
  }else if(/신고/.test(pv)){
    docs.push(["건축·대수선·용도변경 신고서 (별지 제6호서식)","건축법 시행규칙 제12조"],["배치도·평면도·입면도·단면도",""]);
  }else{
    docs.push(["건축·대수선·용도변경 허가신청서 (별지 제1호의4서식)","건축법 시행규칙 제6조"],["설계도서 — 건축계획서·배치도·평면도·입면도·단면도·구조도·소방설비도 등","시행규칙 별표2 · 건축사 작성"]);
  }
  docs.push(["대지 소유·사용 권한 증명 (토지 등기사항증명서 또는 토지사용승낙서)",""]);
  GY.consults(S).filter(function(c){ return c.q==="필수"&&!/용도지역/.test(c.r); }).forEach(function(c){ docs.push([c.r+" 관련 서류",c.d+" 협의 · 건축허가와 함께 의제 처리"]); });
  return docs;
}
function citizenCard(C,P,permit){
  var pv=permit?permit.v:"", gu=S.gu||"관할 구", tel=GY.guTel&&GY.guTel[gu], gb=S.flags&&S.flags.gb;
  var h='<div class="card role-card"><div class="card-t">신청 준비 안내<small>민원인</small></div><ol class="rc-steps">';
  h+='<li><b>인허가 종류</b><span>'+esc(pv||"확인 필요")+(P.act==="용도변경"?" (용도변경)":"")+'</span></li>';
  h+='<li><b>접수처</b><span>'+(gb?'고양특례시 건축정책과 (개발제한구역 · 본청) ☎ 031-8075-3130':esc(gu)+'청 건축과'+(tel?' ☎ '+tel:''))+'</span></li>';
  h+='<li><b>설계·접수</b><span>'+(/허가/.test(pv)?'건축사가 설계하고 세움터(eais.go.kr)로 전자 접수합니다 (건축법 제23조).':'규모에 따라 건축사 설계가 필요할 수 있습니다. 세움터로 접수합니다.')+'</span></li></ol>';
  h+='<div class="rc-sub">준비 서류 <small>체크하며 준비하세요 · 개략 목록</small></div><ul class="doc-list">';
  docList(P,pv).forEach(function(d){ h+='<li><label><input type="checkbox"><span>'+esc(d[0])+(d[1]?'<small>'+esc(d[1])+'</small>':'')+'</span></label></li>'; });
  h+='</ul><div class="rc-foot">상담 갈 때 이 검토서를 인쇄하거나 링크를 보여 주면 빠릅니다.<span><button data-act="print">인쇄</button><button data-act="share">공유 링크</button></span></div></div>';
  return h;
}
// 담당 공무원: 검토 의견 초안(복사) · 협의 요청 대상 · 신청서 대조 포인트
function opinionText(C,P,cnt,title){
  var L=[], b=S.bld;
  L.push("[건축 인허가 사전검토 의견(초안)]");
  L.push("○ 대지위치: "+S.addr+" (PNU "+S.pnu+")");
  L.push("○ 지역·지구: "+(S.zone?S.zone+"지역":"확인 필요")+(S.flags&&S.flags.dup.length?" / 지구단위계획구역":"")+(S.flags&&S.flags.gb?" / 개발제한구역":"")+" · 지목 "+jimokFull(S.jimok)+" · 대지면적 "+n1(S.area)+"㎡");
  L.push("○ 신청 내용: "+P.act+" / "+(P.sub||P.use)+(P.ba?" / 건축면적 "+n1(P.ba)+"㎡":"")+(P.ta?" / 연면적 "+n1(P.ta)+"㎡":"")+(P.fl?" / 지상 "+P.fl+"층":""));
  if(b&&P.act!=="신축") L.push("○ 기존 건축물(대장): "+(b.mainPurpsCdNm||"-")+" · 지상 "+(b.grndFlrCnt||"-")+"층 · 건축면적 "+(b.archArea||"-")+"㎡ · 연면적 "+(b.totArea||"-")+"㎡");
  L.push("○ 검토 결과: "+title+" (부적합 "+cnt.fail+" · 확인 "+cnt.warn+" · 적합 "+cnt.ok+")");
  var i=0;
  GROUPS.forEach(function(g){ C.filter(function(c){ return c.g===g[0]; }).forEach(function(c){
    var law=(c.src||[]).filter(function(s){ return s.t!=="auto"&&s.t!=="input"; }).map(function(s){ return s.l; }).slice(0,2).join(", ");
    L.push("  "+(++i)+". "+c.n+": "+c.v+" → "+ST_WORD[c.st]+(law?" ("+law+")":""));
  }); });
  var cs=GY.consults(S).filter(function(c){ return c.q==="필수"; }).map(function(c){ return c.d; });
  if(cs.length) L.push("○ 협의 필요: "+cs.filter(function(x,j){ return cs.indexOf(x)===j; }).join(", "));
  L.push("○ 비고: 공간정보·조례 기반 자동 사전검토 결과임. 현장 확인 및 관계 부서 협의 후 확정.");
  L.push("  ("+new Date().toLocaleDateString("ko-KR")+" · 고양특례시 건축 인허가 사전검토)");
  return L.join("\n");
}
function officerCard(C,P,permit,cnt,title){
  var b=S.bld, ri=S.roadInfo, pts=[];
  pts.push(["대지면적","지적 "+n1(S.area)+"㎡ — 신청서 대지면적·측량성과와 일치하는지"]);
  if(S.jimok!=="대") pts.push(["지목","'"+jimokFull(S.jimok)+"' — 대지가 아니면 형질변경(개발행위) 의제 서류 확인"]);
  if(b) pts.push(["건축물대장","기존 "+(b.mainPurpsCdNm||"-")+" · 지상 "+(b.grndFlrCnt||"-")+"층 · 건축면적 "+(b.archArea||"-")+"㎡"+(P.act==="신축"?" — 신축이면 멸실신고 여부":" — 신청서의 기존 규모와 대조")]);
  else pts.push(["건축물대장","등재 건축물 없음 — "+(P.act==="신축"?"나대지 신축":"기존 건축물이 필요한 행위인지 확인")]);
  if(P.act==="용도변경"&&b) pts.push(["용도","대장 주용도 '"+(b.mainPurpsCdNm||"-")+"' → 신청 '"+(P.sub||P.use)+"'"]);
  pts.push(["접도",ri?(ri.contact?"도로에 접함"+(ri.maxW?" · 최대 폭 "+n1(ri.maxW)+"m":"")+" — 배치도의 진입로·도로 폭과 대조":"지도상 접도 미확인 — 현황측량·사도 여부 확인"):"분석 중"]);
  if(S.flood&&S.flood.n) pts.push(["침수 이력",S.flood.years.join("·")+"년 — 지하층 거실·설비 배치 확인"]);
  var h='<div class="card role-card officer"><div class="card-t">검토 의견 초안<small>담당 공무원</small></div>';
  h+='<pre class="opinion" id="opinionTxt">'+esc(opinionText(C,P,cnt,title))+'</pre>';
  h+='<div class="rc-btns"><button class="pri" data-act="copyOpinion">📋 의견 복사</button><button data-act="print">🖨 검토서 인쇄</button></div>';
  h+='<div class="rc-sub">신청서 대조 포인트</div><ul class="pt-list">';
  pts.forEach(function(p){ h+='<li><b>'+esc(p[0])+'</b><span>'+esc(p[1])+'</span></li>'; });
  h+='</ul><div class="rc-sub">협의 요청 대상 <small>필수는 미리 체크됨</small></div><ul class="doc-list">';
  GY.consults(S).forEach(function(c){ h+='<li><label><input type="checkbox"'+(c.q==="필수"?" checked":"")+'><span>'+esc(c.d)+' <em class="tag '+(c.q==="필수"?"fail":"warn")+'">'+esc(c.q)+'</em><small>'+esc(c.r)+'</small></span></label></li>'; });
  return h+'</ul></div>';
}
function copyOpinion(){
  var t=$("opinionTxt"); if(!t) return;
  var txt=t.textContent;
  (navigator.clipboard?navigator.clipboard.writeText(txt):Promise.reject()).then(function(){ toast("검토 의견을 복사했습니다"); })
    .catch(function(){ var r=document.createRange(); r.selectNodeContents(t); var s=getSelection(); s.removeAllRanges(); s.addRange(r); toast("Ctrl+C로 복사하세요"); });
}
function chkHtml(c){
  var sym={ok:"✓",warn:"!",fail:"✕",info:"i",na:"–"}[c.st]||"–";
  var h='<div class="chk '+c.st+'"><button class="chk-h" data-act="toggle"><span class="st '+c.st+'">'+sym+'</span><span class="chk-n">'+esc(c.n)+'</span><span class="chk-v '+c.st+'">'+esc(c.v)+'</span><i class="chev"></i></button><div class="chk-d">';
  if(c.bar) h+='<div class="bar"><i style="width:'+Math.min(100,c.bar.p)+'%;background:var(--'+(c.bar.p>100?"fail":c.bar.p>90?"warn":"ok")+')"></i></div><div class="hint" style="margin-bottom:8px">한도 대비 '+n1(c.bar.p)+'% 사용</div>';
  if(c.calc) h+='<div class="calc">'+esc(c.calc)+'</div>';
  if(c.d) h+='<div class="det">'+esc(c.d)+'</div>';
  if(c.src&&c.src.length){ h+='<div class="srcs">'; c.src.forEach(function(s){ h+= s.u? '<a class="src '+s.t+'" href="'+esc(s.u)+'" target="_blank" rel="noopener">'+esc(s.l)+'</a>' : '<span class="src '+s.t+'">'+esc(s.l)+'</span>'; }); h+='</div>'; }
  return h+'</div></div>';
}

// ═══ 토지이용규제 탭 ═══
function renderReg(){
  var r=S.reg||{}, all=r.all||[];
  if(!all.length){ $("tab-reg").innerHTML='<div class="card"><div class="empty-s">이 필지의 토지이용규제 정보가 없습니다</div></div>'; return; }
  var groups=[["용도지역","^UQA|^UQB|^UQC|^UQD"],["용도지구·구역","^UQF|^UQQ|^UQB|^UQR"],["도시·군계획시설","^UQS|^UQT"],["다른 법령 규제","."]];
  var used={}, h='';
  var imp={restrict:["fail","제한"],review:["warn","검토"],allow:["ok","허용"]};
  h+='<div class="card"><div class="card-t">토지이용규제 현황<small>총 '+all.length+'건 · 토지이용규제정보서비스</small></div>';
  h+='<div class="hint" style="margin:-6px 0 4px">포함: 필지가 해당 구역 안 · 저촉: 일부 걸침 · 접함: 경계에 접함</div></div>';
  groups.forEach(function(g){
    var re=new RegExp(g[1]);
    var items=all.filter(function(x,i){ if(used[i]) return false; if(re.test(x.code||"")){ used[i]=1; return true; } return false; });
    if(!items.length) return;
    h+='<div class="card"><div class="card-t">'+g[0]+'<small>'+items.length+'</small></div><div class="rows">';
    items.forEach(function(x){
      var d=x.reg_detail||{}, im=imp[d.impact]||["na",""];
      var zk=/^UQ[A-D]/.test(x.code||"")&&normZone(x.name), zz=zk&&GY.zones[zk];
      var detail=GY.regNote(x.name)||(zz?"고양시 도시계획 조례: 건폐율 "+zz.b+"% · 용적률 "+zz.f+"%"+(zz.h?" · "+zz.h+"층 이하":"")+" (법정 상한 "+GY.national[zk].b+"% · "+GY.national[zk].f+"%)":"")||d.detail||"";
      var cf=x.conflict||"";
      h+='<div class="row"><div class="rn"><b>'+esc(x.name)+' <span class="tag '+(cf==="포함"?"brand":cf==="저촉"?"warn":"")+'">'+esc(cf)+'</span>'+(im[1]?' <span class="tag '+im[0]+'">'+im[1]+'</span>':'')+'</b>'+(detail?'<small>'+esc(detail)+'</small>':'')+'</div><a href="'+lawUrl(x)+'" target="_blank" rel="noopener">법령 ›</a></div>';
    });
    h+='</div></div>';
  });
  h+='<div class="card"><div class="card-t">외부 열람</div><div class="rows">';
  h+=extRow("토지이용계획확인원 (토지이음)","https://www.eum.go.kr/web/ar/lu/luLandDet.jsp?pnu="+S.pnu+"&mode=search&isNoScr=script&selGbn=umd");
  h+=extRow("고양시 도시계획 조례","ordLink");
  h+=extRow("고양시 건축 조례",GY.src.building.url);
  h+='</div></div>';
  $("tab-reg").innerHTML=h.replace('href="ordLink"','href="'+GY.src.urban.url+'"');
}
function extRow(n,u){ return '<div class="row"><div class="rn"><b>'+n+'</b></div><a href="'+u+'" target="_blank" rel="noopener">바로가기 ›</a></div>'; }
function lawUrl(x){
  var n=x.name||"", c=x.code||"";
  var m=GY.lawFor(n,c);
  return lawLink(m.law,m.art);
}

// ═══ 건축물대장 ═══
function bldSkeleton(){ return '<div class="card"><div class="card-t">건축물대장 조회 중…</div><div class="skel"></div><div class="skel" style="width:70%"></div><div class="skel" style="width:85%"></div></div>'; }
function parsePNU(pnu){ if(!pnu||pnu.length<19) return null; return {sigunguCd:pnu.substring(0,5),bjdongCd:pnu.substring(5,10),platGbCd:pnu.charAt(10)==="2"?"1":"0",bun:pnu.substring(11,15),ji:pnu.substring(15,19)}; }
function bldUrl(ep,pp){ return ep+"?serviceKey="+BLD_KEY+"&sigunguCd="+pp.sigunguCd+"&bjdongCd="+pp.bjdongCd+"&platGbCd="+pp.platGbCd+"&bun="+pp.bun+"&ji="+pp.ji+"&_type=json&numOfRows=100&pageNo=1"; }
function bldFetch(url){ return fetch(url).then(function(r){return r.json();}).then(function(d){ var b=d&&d.response&&d.response.body, it=b&&b.items&&b.items.item; if(!it||!(parseInt(b.totalCount)>0)) return []; return Array.isArray(it)?it:[it]; }).catch(function(){ return []; }); }
function fetchBuilding(pnu){
  var pp=parsePNU(pnu); if(!pp){ $("tab-bld").innerHTML='<div class="card"><div class="empty-s">PNU 확인 불가</div></div>'; return; }
  Promise.all([bldFetch(bldUrl(BLD_API.title,pp)),bldFetch(bldUrl(BLD_API.recap,pp)),bldFetch(bldUrl(BLD_API.floor,pp))]).then(function(r){
    if(!S||S.pnu!==pnu) return;
    var titles=r[0], recaps=r[1], floors=r[2];
    // 주건축물 우선 정렬 (연면적 큰 순)
    titles.sort(function(a,b){ return (parseFloat(b.totArea)||0)-(parseFloat(a.totArea)||0); });
    S.bld=titles[0]||recaps[0]||null; S.bldAll=titles; S.bldRecap=recaps[0]||null;
    if(window.GY3D) GY3D.refresh(); // 3D 기존 건물 높이(대장 높이·층수)
    var h='';
    if(!titles.length&&!recaps.length){ h='<div class="card"><div class="empty-s">🏗 이 필지에 등록된 건축물대장이 없습니다<br><small>나대지이거나 미등재 건축물일 수 있습니다</small></div></div>'; }
    if(recaps.length){ var c=recaps[0];
      h+='<div class="card"><div class="card-t">총괄표제부<small>'+esc(c.bldNm||"")+'</small></div><table class="kv">'+
        kvr("대지면적",c.platArea&&n1(c.platArea)+" ㎡")+kvr("건축면적 / 건폐율",(c.archArea?n1(c.archArea)+" ㎡":"-")+" / "+(c.bcRat?c.bcRat+"%":"-"))+kvr("연면적 / 용적률",(c.totArea?n1(c.totArea)+" ㎡":"-")+" / "+(c.vlRat?c.vlRat+"%":"-"))+
        kvr("주·부속 건축물",(c.mainBldCnt||0)+"동 / "+(c.atchBldCnt||0)+"동")+kvr("세대수",c.hhldCnt)+kvr("총 주차",c.totPkngCnt&&c.totPkngCnt+"대")+'</table></div>'; }
    titles.slice(0,6).forEach(function(b,i){
      h+='<div class="card"><div class="card-t">'+esc((b.dongNm?b.dongNm+" · ":"")+(b.bldNm||"건축물 "+(i+1)))+'<small>'+esc(b.mainAtchGbCdNm||"")+'</small></div>';
      h+='<div class="pc-tags" style="margin-bottom:10px"><span class="tag info">'+esc(b.mainPurpsCdNm||"용도 미상")+'</span><span class="tag">'+esc(b.strctCdNm||"")+'</span><span class="tag">지상 '+(b.grndFlrCnt||0)+'층 / 지하 '+(b.ugrndFlrCnt||0)+'층</span></div>';
      h+='<table class="kv">'+kvr("대지면적",b.platArea&&parseFloat(b.platArea)?n1(b.platArea)+" ㎡":"")+kvr("건축면적 / 건폐율",(b.archArea?n1(b.archArea)+" ㎡":"-")+" / "+(parseFloat(b.bcRat)?b.bcRat+"%":"-"))+
        kvr("연면적 / 용적률",(b.totArea?n1(b.totArea)+" ㎡":"-")+" / "+(parseFloat(b.vlRat)?b.vlRat+"%":"-"))+kvr("높이",parseFloat(b.heit)?b.heit+" m":"")+
        kvr("세대 / 가구",(b.hhldCnt||0)+" / "+(b.fmlyCnt||0))+kvr("승강기","승용 "+(b.rideUseElvtCnt||0)+" · 비상용 "+(b.emgenUseElvtCnt||0))+
        kvr("허가일",fmtDate(b.pmsDay))+kvr("사용승인일",'<b style="color:var(--brand-700)">'+fmtDate(b.useAprDay)+'</b>',true)+kvr("내진설계",b.rserthqkDsgnApplyYn==="1"?"적용":(b.rserthqkDsgnApplyYn==="0"?"미적용":""))+'</table></div>';
    });
    if(titles.length>6) h+='<div class="hint" style="padding:0 6px 10px">외 '+(titles.length-6)+'동은 세움터에서 확인하세요.</div>';
    if(floors.length){
      floors.sort(function(a,b){ var f=function(x){ return (x.flrGbCdNm||"").indexOf("지하")>=0?-(parseInt(x.flrNo)||0):(parseInt(x.flrNo)||0)+100; }; return (a.dongNm||"").localeCompare(b.dongNm||"")||f(a)-f(b); });
      h+='<div class="card"><div class="card-t">층별 개요<small>'+floors.length+'건</small></div><table class="tb"><tr><th>동</th><th>층</th><th>용도</th><th style="text-align:right">면적(㎡)</th></tr>';
      floors.slice(0,40).forEach(function(f){ h+='<tr><td>'+esc(f.dongNm||"")+'</td><td>'+esc((f.flrGbCdNm||"").replace("지상","")+(f.flrNo||""))+'</td><td>'+esc(f.mainPurpsCdNm||f.etcPurps||"-")+'</td><td style="text-align:right">'+(f.area?n1(f.area):"-")+'</td></tr>'; });
      h+='</table></div>';
    }
    h+='<div class="card"><div class="card-t">공식 열람·발급</div><div class="rows">'+extRow("건축물대장 열람 (세움터)","https://www.eais.go.kr/")+extRow("건축물대장 발급 (정부24)","https://www.gov.kr/mw/AA020InfoCappView.do?HighCtgCD=A09006&CappBizCD=15000000066")+'</div></div>';
    $("tab-bld").innerHTML=h;
    if(plan.act==="용도변경"||plan.act==="증축") renderReviewFormKeep();
  });
}
function kvr(k,v,raw){ if(v==null||v===""||v==="undefined") return ""; return '<tr><td>'+k+'</td><td>'+(raw?v:esc(v))+'</td></tr>'; }
// 입력값·결과를 유지한 채 폼 재구성 (행위·용도 변경, 건축물대장 도착 시)
var FORM_IDS=["inBa","inTa","inFa","inFl","inHt","inUf","inHh","inUa"];
function renderReviewFormKeep(){
  var keep={}, sale=$("inSale")&&$("inSale").checked, gbr=$("inGbRes")&&$("inGbRes").checked, out=$("reviewOut")&&$("reviewOut").innerHTML;
  FORM_IDS.forEach(function(id){ if($(id)) keep[id]=$(id).value; });
  renderReviewForm();
  for(var k in keep) if($(k)) $(k).value=keep[k];
  if($("inSale")) $("inSale").checked=!!sale;
  if($("inGbRes")) $("inGbRes").checked=!!gbr;
  if(out) $("reviewOut").innerHTML=out;
}

// ═══ 협의·절차 탭 ═══
function renderProc(){
  var h='<div class="card"><div class="card-t">허가권자 · 접수처</div>'+GY.authorityHtml(S)+'</div>';
  var cs=GY.consults(S);
  h+='<div class="card"><div class="card-t">협의 대상 부서·기관<small>'+cs.length+'곳</small></div><div class="rows">';
  cs.forEach(function(c){ h+='<div class="row"><div class="rn"><b>'+esc(c.d)+' <span class="tag '+(c.q==="필수"?"fail":"warn")+'">'+esc(c.q)+'</span></b><small>'+esc(c.r)+'</small></div>'+(c.law?'<a href="'+lawLink(c.law,c.art)+'" target="_blank" rel="noopener">근거 ›</a>':'')+'</div>'; });
  h+='</div></div>';
  h+='<div class="card"><div class="card-t">인허가 진행 절차</div><ol class="flow">';
  GY.flow.forEach(function(f){ h+='<li><b>'+esc(f[0])+'</b><small>'+esc(f[1])+'</small></li>'; });
  h+='</ol></div>';
  h+='<div class="card"><div class="card-t">건축허가 의제 처리 (건축법 제11조⑤)</div><div class="rows">';
  GY.deemed.forEach(function(x){ h+='<div class="row"><div class="rn"><b>'+esc(x[0])+'</b></div><a href="'+lawLink(x[1],x[2])+'" target="_blank" rel="noopener">'+esc(x[1].replace(/의 계획 및 이용에 관한 법률/,"계획법"))+' '+esc(x[2])+' ›</a></div>'; });
  h+='</div></div>';
  $("tab-proc").innerHTML=h;
}

// ═══ 주변사례 ═══
var nearData=null, nearSel=-1, nearRadius=1000;
function renderNear(){
  $("tab-near").innerHTML='<div class="card"><div class="card-t">주변 건축 인허가 사례</div><div class="skel"></div><div class="skel" style="width:60%"></div></div>';
  var p=nearData? Promise.resolve(nearData) : fetch(URL_.permits+"/query?where="+encodeURIComponent("sigungu_cd_nm LIKE '고양시%'")+"&outFields=*&f=json").then(function(r){return r.json();}).then(function(d){ nearData=(d.features||[]).map(function(f){return f.attributes;}).filter(function(a){return a.x_lon&&a.y_lat;}); return nearData; });
  p.then(function(rows){ drawNear(rows); }).catch(function(){ $("tab-near").innerHTML='<div class="card"><div class="empty-s">주변사례 데이터를 불러오지 못했습니다</div></div>'; });
}
function hav(lon1,lat1,lon2,lat2){ var R=6371000,t=Math.PI/180,dl=(lat2-lat1)*t,dn=(lon2-lon1)*t,a=Math.sin(dl/2)*Math.sin(dl/2)+Math.cos(lat1*t)*Math.cos(lat2*t)*Math.sin(dn/2)*Math.sin(dn/2); return 2*R*Math.asin(Math.sqrt(a)); }
function drawNear(rows){
  var list=rows.map(function(a){ return {a:a,d:hav(S.lon,S.lat,parseFloat(a.x_lon),parseFloat(a.y_lat))}; }).filter(function(x){return x.d<=nearRadius;}).sort(function(x,y){return x.d-y.d;});
  S.near=list;
  var h='<div class="card"><div class="card-t">주변 건축 인허가 사례<small>반경 '+(nearRadius>=1000?nearRadius/1000+"km":nearRadius+"m")+' · '+list.length+'건</small></div>';
  h+='<div class="chips" id="nearR">'+[500,1000,2000,3000].map(function(r){return '<button class="chip'+(r===nearRadius?' on':'')+'" data-r="'+r+'">'+(r>=1000?r/1000+"km":r+"m")+'</button>';}).join("")+'</div></div>';
  if(!list.length){ h+='<div class="card"><div class="empty-s">반경 내 수집된 인허가 사례가 없습니다.<br><small>현재 고양시 사례 '+rows.length+'건 수집됨 · 반경을 넓혀 보세요</small></div></div>'; }
  else{
    var bcr=list.filter(function(x){return parseFloat(x.a.bcrat)>0;}), far=list.filter(function(x){return parseFloat(x.a.vlrat)>0;});
    var avg=function(arr,k){ return arr.length? arr.reduce(function(s,x){return s+parseFloat(x.a[k]);},0)/arr.length : 0; };
    h+='<div class="intro-stats" style="margin-bottom:12px"><div class="stat"><b>'+list.length+'</b><span>사례 수</span></div><div class="stat"><b>'+(bcr.length?n1(avg(bcr,"bcrat"))+'%':'-')+'</b><span>평균 건폐율</span></div><div class="stat"><b>'+(far.length?n0(avg(far,"vlrat"))+'%':'-')+'</b><span>평균 용적률</span></div></div>';
    h+='<div id="nearPick"></div>'; // 행을 누르면 고른 사례 상세가 여기 (지도는 그 필지 경계를 보여 줌)
    h+='<div class="card" style="padding:8px 10px"><table class="tb"><tr><th>허가일</th><th>구분</th><th>용도</th><th style="text-align:right">거리</th></tr>';
    list.slice(0,60).forEach(function(x,i){ var a=x.a;
      h+='<tr class="clk'+(i===nearSel?' on':'')+'" data-near="'+i+'"><td>'+esc(fmtDate(a.arch_pms_date))+'</td><td><i class="dot" style="background:'+nearColor(a.arch_gb_cd_nm)+'"></i>'+esc(a.arch_gb_cd_nm||"-")+'</td><td>'+esc(a.main_prpos_cd_nm||"-")+'</td><td style="text-align:right">'+n0(x.d)+'m</td></tr>'; });
    h+='</table></div><p class="hint" style="padding:0 6px">출처: 건축인허가 정보(국토교통부) 수집분 · 행을 누르면 지도에 그 필지 경계를 표시</p>';
  }
  $("tab-near").innerHTML=h;
  drawNearMap(list);
  if(nearSel>=0&&list[nearSel]) renderNearPick(nearSel);
}
function nearColor(t){ return {"신축":"#00A0B0","증축":"#2F6FDE","대수선":"#0E9F6E","용도변경":"#8E44AD","개축":"#E07B00","재축":"#795548"}[t]||"#8795A1"; }
// 사례 위치점 → 연속지적도 필지: 점 둘레 30m 안에서 지번(본번-부번)이 같은 필지, 없으면 점이 놓인 필지
var nearParcel={}; // 사례 objectid → {geom, jibun} | null (한 번 찾은 것은 다시 묻지 않음)
function nearJibun(a){ var m=+a.mnnm||0, s=+a.slno||0; return m? m+(s?"-"+s:"") : ""; }
function findNearParcel(a){
  var key=a.objectid;
  if(key in nearParcel) return Promise.resolve(nearParcel[key]);
  var pt=new E.Point({longitude:parseFloat(a.x_lon),latitude:parseFloat(a.y_lat)}), jb=nearJibun(a);
  var q=function(dist){ var o={geometry:pt,spatialRelationship:"intersects",outFields:["a1","a5"],returnGeometry:true,outSpatialReference:view.spatialReference};
    if(dist){ o.distance=dist; o.units="meters"; } return cadastral.queryFeatures(o).then(function(fs){ return fs.features; }).catch(function(){ return []; }); };
  var lot=function(f){ var m=String(f.attributes.a5||"").replace(/^산\s*/,"").match(/^\d+(-\d+)?/); return m?m[0]:""; };
  return Promise.all([q(0),q(30)]).then(function(r){
    var f=(jb&&(r[0].filter(function(f){return lot(f)===jb;})[0]||r[1].filter(function(f){return lot(f)===jb;})[0]))||r[0][0]||null;
    nearParcel[key]=f?{geom:f.geometry,jibun:String(f.attributes.a5||""),exact:!!jb&&lot(f)===jb}:null;
    return nearParcel[key];
  });
}
function drawNearMap(list){
  gfxNear.removeAll();
  var sel=nearSel>=0&&list[nearSel]?list[nearSel]:null, par=sel?nearParcel[sel.a.objectid]:null;
  list.forEach(function(x,i){ var c=hexA(nearColor(x.a.arch_gb_cd_nm),1);
    if(i===nearSel&&par) return; // 고른 사례는 점 대신 필지 경계
    gfxNear.add(new E.Graphic({geometry:{type:"point",longitude:parseFloat(x.a.x_lon),latitude:parseFloat(x.a.y_lat)},symbol:{type:"simple-marker",size:i===nearSel?16:9,color:c,outline:{color:[255,255,255],width:i===nearSel?3:1.2}}}));
  });
  if(par){
    var c=nearColor(sel.a.arch_gb_cd_nm);
    gfxNear.add(new E.Graphic({geometry:par.geom,symbol:{type:"simple-fill",color:[0,0,0,0],outline:{color:[255,255,255,0.95],width:5.5}}}));
    gfxNear.add(new E.Graphic({geometry:par.geom,symbol:{type:"simple-fill",color:hexA(c,0.32),outline:{color:hexA(c,1),width:2.6}}}));
    gfxNear.add(new E.Graphic({geometry:par.geom.centroid,symbol:{type:"text",text:sel.a.arch_gb_cd_nm||"사례",color:hexA(c,1),haloColor:[255,255,255,0.95],haloSize:2,font:{size:11,weight:"bold",family:"sans-serif"}}}));
  }
}
function nearDetail(i){
  var x=S.near[i]; if(!x) return; var a=x.a; nearSel=i;
  document.querySelectorAll("#tab-near tr.clk").forEach(function(tr){ tr.classList.toggle("on",+tr.dataset.near===i); });
  drawNearMap(S.near); renderNearPick(i);
  findNearParcel(a).then(function(par){
    if(nearSel!==i||S.near[i]!==x) return; // 그사이 다른 행을 누름
    drawNearMap(S.near); renderNearPick(i);
    var go=par? par.geom.extent.clone().expand(3.5) : {center:[parseFloat(a.x_lon),parseFloat(a.y_lat)],zoom:Math.max(view.zoom,17)};
    if(window.GY3D&&GY3D.is3d()&&GY3D._view()) GY3D._view().goTo(go,{duration:700}).catch(function(){});
    else view.goTo(go,{duration:600}).catch(function(){});
  });
}
function renderNearPick(i){
  var el=$("nearPick"), x=S.near&&S.near[i]; if(!el||!x) return; var a=x.a, par=nearParcel[a.objectid];
  var where=(a.bjdong_cd_nm||"")+" "+nearJibun(a);
  var pst=!(a.objectid in nearParcel)?'<span class="np-st">필지 경계를 찾는 중…</span>'
    : par?'<span class="np-st ok">지도에 필지 경계 표시'+(par.exact?'':' (위치점이 놓인 필지: '+esc(par.jibun)+')')+'</span>'
    : '<span class="np-st">지적도에서 필지를 찾지 못해 위치점으로 표시</span>';
  el.innerHTML='<div class="card near-pick"><div class="card-t"><i class="dot" style="background:'+nearColor(a.arch_gb_cd_nm)+'"></i>'+esc(a.bld_nm||a.main_prpos_cd_nm||"인허가 사례")+
    '<button class="np-x" data-near-close aria-label="사례 닫기">×</button></div><div class="np-sub">'+esc(where)+' · 현재 필지에서 '+n0(x.d)+'m</div>'+pst+'<table class="kv">'+
    kvr("건축구분",a.arch_gb_cd_nm)+kvr("허가/신고",a.pms_decl_gb_cd_nm)+kvr("허가일",fmtDate(a.arch_pms_date))+kvr("주용도",a.main_prpos_cd_nm)+kvr("기타용도",a.etc_prpos_cntt)+
    kvr("대지면적",a.plat_area&&n1(a.plat_area)+" ㎡")+kvr("건축면적",a.arch_area&&n1(a.arch_area)+" ㎡")+kvr("연면적",a.totarea&&n1(a.totarea)+" ㎡")+kvr("건폐율",parseFloat(a.bcrat)?n1(a.bcrat)+" %":"")+kvr("용적률",parseFloat(a.vlrat)?n1(a.vlrat)+" %":"")+
    kvr("착공",fmtDate(a.real_stcns_date))+kvr("사용승인",fmtDate(a.useapr_date))+'</table></div>';
  el.scrollIntoView({block:"nearest",behavior:"smooth"});
}

// ═══ 인쇄 ═══
// 검토서 인쇄: 필지 지도 화면을 찍어 검토서 머리에 넣고 인쇄(PDF 저장)
function printReport(){
  document.querySelectorAll("#reviewOut .chk").forEach(function(c){c.classList.add("open");});
  var box=$("printMap"), go=function(){ setTimeout(function(){ window.print(); },150); };
  if(!box||!view||!S||!S.geom){ go(); return; }
  loading(true,"검토서를 준비하는 중");
  view.goTo(S.geom.extent.clone().expand(2.6),{duration:0}).then(function(){ return view.takeScreenshot({width:1100,height:560,format:"jpg",quality:88}); })
    .then(function(shot){ box.innerHTML='<img src="'+shot.dataUrl+'" alt="필지 위치도" style="width:100%;border:1px solid #ccc;border-radius:6px"><div style="font-size:10px;color:#777;margin-top:2px">필지 위치도 · 배경: 지도 화면 그대로</div>'; })
    .catch(function(){}).then(function(){ loading(false); go(); });
}
// 공유: 링크 복사 + QR 코드 (행사장에서 휴대폰으로 바로 열기)
function shareModal(){
  var u=location.origin+location.pathname+"?pnu="+S.pnu;
  try{ navigator.clipboard.writeText(u); }catch(_){}
  openModal('<h3>이 필지 공유</h3><div class="sub">'+esc(S.addr)+'</div>'+
    '<div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap"><div id="qrBox" style="width:168px;height:168px;background:#fff;padding:8px;border:1px solid var(--line);border-radius:12px"></div>'+
    '<div style="flex:1;min-width:200px"><p style="font-size:13px;line-height:1.6;margin-bottom:8px">휴대폰 카메라로 QR을 비추면 같은 필지가 열립니다.<br>링크는 클립보드에 복사했습니다.</p>'+
    '<input class="select" readonly value="'+esc(u)+'" onclick="this.select()" style="font-size:12px"></div></div>');
  var draw=function(){ try{ new QRCode($("qrBox"),{text:u,width:150,height:150,colorDark:"#023D37",colorLight:"#ffffff",correctLevel:QRCode.CorrectLevel.M}); }catch(e){ $("qrBox").textContent="QR 생성 실패"; } };
  if(window.QRCode) draw();
  else { var s=document.createElement("script"); s.src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"; s.onload=draw; s.onerror=function(){ $("qrBox").textContent="QR을 불러오지 못했습니다"; }; document.head.appendChild(s); }
}

// ═══ 검색 ═══
function doSearch(q){
  q=(q||"").trim(); if(!q) return;
  var full=/고양/.test(q)? q : "경기도 고양시 "+q;
  loading(true,"주소를 찾는 중");
  api({action:"geocode",address:full}).then(function(d){
    if(d.status!=="ok"||!d.lon){ loading(false); toast("주소를 찾을 수 없습니다. 동·지번을 확인해 주세요"); return; }
    require(["esri/geometry/Point"],function(Point){ selectAtPoint(new Point({longitude:d.lon,latitude:d.lat}),false); });
  }).catch(function(){ loading(false); toast("주소 검색 중 오류가 발생했습니다"); });
}

// ═══ 구 이동 ═══
function goGu(code){
  document.querySelectorAll(".gu-btn").forEach(function(b){ b.classList.toggle("active",b.dataset.gu===code); });
  if(code==="all"){ if(homeExtent) view.goTo(homeExtent,{duration:700}); return; }
  var g=guLayer.graphics.find(function(x){ return x.attributes&&x.attributes.cd===code; });
  if(g) view.goTo(g.geometry.extent.clone().expand(1.15),{duration:700});
}

// ═══ 도움말 ═══
function help(){
  openModal('<h3>이용 안내</h3><div class="sub">고양특례시 건축 인허가 사전검토 서비스</div>'+
  '<ol class="flow"><li><b>필지 선택</b><small>상단 검색창에 동·지번 또는 도로명 주소를 입력하거나 지도에서 필지를 클릭합니다. 고양시 외 지역은 선택되지 않습니다.</small></li>'+
  '<li><b>대지 정보 확인</b><small>용도지역, 고양시 조례 기준 건폐율·용적률·층수, 토지이용규제, 기존 건축물대장을 자동으로 조회합니다.</small></li>'+
  '<li><b>건축계획 입력</b><small>행위(신축·증축 등), 용도, 면적, 층수를 입력하고 사전검토를 실행합니다.</small></li>'+
  '<li><b>결과 확인·출력</b><small>항목별 판정과 법령·조례 근거를 확인하고 검토서를 인쇄(PDF 저장)할 수 있습니다.</small></li></ol>'+
  '<div class="card" style="background:var(--bg);box-shadow:none;margin:6px 0 8px"><div class="card-t" style="margin-bottom:6px">활용 데이터</div><div class="intro-src" style="color:var(--ink-2)">'+
  ["토지이용규제정보(국토교통부)","연속지적도","건축물대장(건축HUB)","수치지형도 1:5,000(국토지리정보원)","고양시 5m 등고선·음영기복","지구단위계획 시행지침(고양시)","건축인허가 정보"].map(function(x){return '<span>'+x+'</span>';}).join("")+
  '</div></div>'+
  '<div class="card" style="background:var(--bg);box-shadow:none;margin:6px 0 0"><div class="card-t" style="margin-bottom:6px">적용 기준</div><div class="rows">'+
  GY.sources().map(function(s){return '<div class="row"><div class="rn"><b>'+esc(s.name)+'</b><small>'+esc(s.date)+'</small></div><a href="'+s.url+'" target="_blank" rel="noopener">원문 ›</a></div>';}).join("")+
  '</div></div><p class="hint" style="margin-top:10px">본 서비스는 참고용 사전검토 도구로 법적 효력이 없습니다. 지구단위계획·개별 법령에 따라 결과가 달라질 수 있습니다.</p>');
}

// ═══ 이벤트 ═══
document.addEventListener("click",function(e){
  var rb=e.target.closest("[data-role]"); if(rb){ applyRole(rb.dataset.role); return; }
  var t=e.target.closest("[data-act],[data-tab],[data-gu],[data-bm],[data-close],.chip,[data-near],[data-near-close],[data-sample],[data-dup]");
  if(t&&t.hasAttribute("data-near-close")){ nearSel=-1; $("nearPick").innerHTML=""; document.querySelectorAll("#tab-near tr.clk.on").forEach(function(tr){ tr.classList.remove("on"); }); drawNearMap(S.near||[]); return; }
  if(!t) return;
  if(t.dataset.dup!==undefined){ dupModal(+t.dataset.dup); return; }
  if(t.dataset.close!==undefined||t.id==="modal"){ closeModal(); return; }
  if(t.dataset.tab){ switchTab(t.dataset.tab); return; }
  if(t.dataset.gu){ goGu(t.dataset.gu); return; }
  if(t.dataset.bm){ setBasemap(t.dataset.bm); return; }
  if(t.dataset.sample){ $("exMenu").hidden=true; $("addrInput").value=t.dataset.sample; doSearch(t.dataset.sample); return; }
  if(t.dataset.near){ nearDetail(+t.dataset.near); return; }
  if(t.dataset.r){ nearRadius=+t.dataset.r; nearSel=-1; drawNear(nearData||[]); return; }
  if(t.parentElement&&t.parentElement.id==="actChips"){ plan.act=t.dataset.v; plan.sub=$("inUse").value; renderReviewFormKeep(); if(window.GY3D) GY3D.refresh(); return; }
  var a=t.dataset.act;
  if(a==="judge") judge();
  else if(a==="toggle") t.closest(".chk").classList.toggle("open");
  else if(a==="openAll") document.querySelectorAll("#reviewOut .chk").forEach(function(c){c.classList.add("open");});
  else if(a==="print") printReport();
  else if(a==="copyOpinion") copyOpinion();
  else if(a==="onlyIssues"){ var ro=$("reviewOut"), on=ro.classList.toggle("only-issues"); t.textContent=on?"전체 항목 보기":"확인 필요 항목만"; }
  else if(a==="zoneTable"){ e.preventDefault(); zoneTable(); }
  else if(a==="copyPnu"){ try{ navigator.clipboard.writeText(S.pnu); toast("PNU를 복사했습니다"); }catch(_){ } }
  else if(a==="share") shareModal();
  else if(a==="fillMax"){ // 증축은 남은 여유(최대 − 기존)만
    var eb=plan.act==="증축"&&S.bld||null, exB=eb&&+eb.archArea||0, exT=eb&&+(eb.vlRatEstmTotArea||eb.totArea)||0;
    $("inBa").value=Math.max(0,Math.floor(S.area*S.zm.b/100-exB)); $("inTa").value=Math.max(0,Math.floor(S.area*S.zm.f/100-exT)); }
});
document.addEventListener("change",function(e){
  if(e.target.id==="inPar"){ plan.use=e.target.value; plan.sub=""; renderReviewFormKeep(); }
  if(e.target.id==="inUse"){ plan.sub=e.target.value; if(needUnits()!==!!$("inHh")) renderReviewFormKeep(); else updateUseHint(); }
});
$("modal").addEventListener("click",function(e){ if(e.target.id==="modal") closeModal(); });
document.addEventListener("keydown",function(e){ if(e.key==="Escape") closeModal(); });
$("searchForm").addEventListener("submit",function(e){ e.preventDefault(); doSearch($("addrInput").value); });
$("btnHelp").onclick=help;

// 샘플 필지 + 소개 통계
// 예시 필지: 시작 화면 격자 + 검색창 '예시' 메뉴
function sampleBtn(s){
  var p=s.label.split(" · "), kind=p[1]||"", col="#ccc";
  Object.keys(ZONE_COLOR).forEach(function(z){ if(kind.indexOf(z)>=0) col=ZONE_COLOR[z]; });
  if(/개발제한/.test(kind)) col="#E5383B"; else if(/농업진흥/.test(kind)) col="#2EA05A"; else if(/임야|취락/.test(kind)) col="#46A85B"; else if(/성장관리|계획관리/.test(kind)) col=ZONE_COLOR["계획관리"];
  return '<button class="sample" data-sample="'+esc(s.addr)+'"><i style="background:'+col+'"></i><span>'+esc(p[0])+'<small>'+esc(kind)+'</small></span></button>';
}
$("samples").innerHTML=GY.samples.map(sampleBtn).join("");
$("exMenu").innerHTML=GY.samples.map(sampleBtn).join("");
$("exBtn").onclick=function(e){ e.stopPropagation(); var m=$("exMenu"); m.hidden=!m.hidden; this.setAttribute("aria-expanded",String(!m.hidden)); };
document.addEventListener("click",function(e){ if(!e.target.closest("#exMenu,#exBtn")) $("exMenu").hidden=true; });
$("introStats").innerHTML=GY.introStats.map(function(s){ return '<div class="stat"><b>'+esc(s.v)+'</b><span>'+esc(s.k)+'</span></div>'; }).join("");
applyRole(role);
// 시작 화면 용도지역 미니 표: 시민이 자주 묻는 지역만 (건폐율 · 용적률 막대는 일반상업 기준 비율)
(function(){
  var el=$("zoneMini"); if(!el||!GY.zones) return;
  var keys=["제1종일반주거","제2종일반주거","제3종일반주거","준주거","일반상업","근린상업","자연녹지","계획관리"].filter(function(k){ return GY.zones[k]; });
  var top=Math.max.apply(null,keys.map(function(k){ return GY.zones[k].f; }));
  el.innerHTML='<div class="zm-row zm-head"><span>용도지역</span><span class="zb">건폐율</span><span>용적률</span></div>'+keys.map(function(k){ var z=GY.zones[k];
    return '<div class="zm-row"><span class="zn"><i style="background:'+ZONE_COLOR[k]+'"></i>'+k+'</span><span class="zb">'+z.b+'%</span><span class="zf">'+z.f+'%<em style="--w:'+Math.max(4,Math.round(z.f/top*100))+'%"></em></span></div>'; }).join("");
})();
// 브랜드 색 적용
if(GY.brand){ var rs=document.documentElement.style; for(var k in GY.brand) rs.setProperty(k,GY.brand[k]); }

})();
