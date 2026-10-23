/* 고양특례시 인허가 사전검토 — 판정 기준 데이터 & 판정 엔진
 * 조례 수치는 research/*.md 조사 결과(조문·별표 근거)에 따라 갱신한다.
 * 각 수치 옆 주석에 근거 조문을 남긴다.
 */
var GY = (function(){
"use strict";

// ─────────────────────────────────────────────
// 1. 근거 법령 (원문 링크·기준일)
// ─────────────────────────────────────────────
var src = {
  urban:    {name:"고양시 도시계획 조례", date:"확인 중", url:"https://www.law.go.kr/자치법규/고양시도시계획조례"},
  building: {name:"고양시 건축 조례", date:"확인 중", url:"https://www.law.go.kr/자치법규/고양시건축조례"},
  parking:  {name:"고양시 주차장 설치 및 관리 조례", date:"확인 중", url:"https://www.law.go.kr/자치법규/고양시주차장설치및관리조례"},
  extra: []
};

// ─────────────────────────────────────────────
// 2. 용도지역별 건폐율·용적률·층수
//    b: 건폐율(%)  f: 용적률(%)  h: 층수 제한(0=없음)
// ─────────────────────────────────────────────
// 국토계획법 시행령 제84조(건폐율)·제85조(용적률) 법정 상한
var national = {
  "제1종전용주거":{b:50,f:100},"제2종전용주거":{b:50,f:150},"제1종일반주거":{b:60,f:200},"제2종일반주거":{b:60,f:250},"제3종일반주거":{b:50,f:300},"준주거":{b:70,f:500},
  "중심상업":{b:90,f:1500},"일반상업":{b:80,f:1300},"근린상업":{b:70,f:900},"유통상업":{b:80,f:1100},
  "전용공업":{b:70,f:300},"일반공업":{b:70,f:350},"준공업":{b:70,f:400},
  "보전녹지":{b:20,f:80},"생산녹지":{b:20,f:100},"자연녹지":{b:20,f:100},
  "보전관리":{b:20,f:80},"생산관리":{b:20,f:80},"계획관리":{b:40,f:100},"농림":{b:20,f:80},"자연환경보전":{b:20,f:80}
};
// 고양시 조례 값 — research/01_도시계획조례 반영 전까지 법정 상한으로 초기화
var zones = {};
Object.keys(national).forEach(function(k){ zones[k]={b:national[k].b,f:national[k].f,h:0,bArt:"시행령 제84조",fArt:"시행령 제85조",hNote:""}; });

// ─────────────────────────────────────────────
// 3. 용도지역별 건축 가능 용도 (ok/cond/no + 조건)
// ─────────────────────────────────────────────
var useZone = {};

// ─────────────────────────────────────────────
// 4. 건축 조례 / 주차장 조례 기준
// ─────────────────────────────────────────────
var ord = {
  committee: null,      // function(P,S) → [사유]
  fee: null,            // function(ta,isHouse) → 원
  safetyDeposit: null,  // {minArea, rate}
  landscape: null,      // function(sa,ta,zone,use) → {req,pct,text}
  publicSpace: null,    // function(ta,zone,use) → {req,pct,text}
  setback: null,        // function(use,ta,zone) → {line,adj}
  minSite: null,        // {주거:..}
  artwork: null,        // {minArea, rate}
  landscapeReview: null // function(P,S) → [사유]
};
var parking = { rules:{}, note:"" };   // use → {rate, text}
var departments = {};                  // 역할 → 부서명

// ─────────────────────────────────────────────
// 5. 법령 매핑 (토지이용규제 → 근거 법령)
// ─────────────────────────────────────────────
var LAW_KW = [
  [/개발제한구역/,"개발제한구역의 지정 및 관리에 관한 특별조치법","제12조"],
  [/군사|비행안전|대공방어|통제보호|제한보호/,"군사기지 및 군사시설 보호법","제9조"],
  [/문화재|문화유산|국가유산|역사문화/,"국가유산영향진단법",""],
  [/상수원/,"수도법","제7조"],
  [/토지거래/,"부동산 거래신고 등에 관한 법률","제10조"],
  [/과밀억제|성장관리권역|자연보전권역/,"수도권정비계획법","제6조"],
  [/가축사육/,"가축분뇨의 관리 및 이용에 관한 법률","제8조"],
  [/농업진흥/,"농지법","제32조"],
  [/보전산지|임업용|공익용/,"산지관리법","제12조"],
  [/하천/,"하천법","제38조"],
  [/지구단위계획/,"국토의 계획 및 이용에 관한 법률","제52조"],
  [/성장관리계획/,"국토의 계획 및 이용에 관한 법률","제75조의3"],
  [/대공원|공원/,"도시공원 및 녹지 등에 관한 법률","제24조"],
  [/교육환경|학교/,"교육환경 보호에 관한 법률","제9조"],
  [/도로|소로|중로|대로|광로/,"국토의 계획 및 이용에 관한 법률","제64조"],
  [/비오톱|생태/,"자연환경보전법",""],
  [/소음/,"공항소음 방지 및 소음대책지역 지원에 관한 법률",""]
];
function lawFor(name,code){
  if(/^UQA|^UQB|^UQC|^UQD/.test(code||"")) return {law:"국토의 계획 및 이용에 관한 법률 시행령",art:"제71조"};
  for(var i=0;i<LAW_KW.length;i++) if(LAW_KW[i][0].test(name||"")) return {law:LAW_KW[i][1],art:LAW_KW[i][2]};
  if(/^UQS|^UQT/.test(code||"")) return {law:"국토의 계획 및 이용에 관한 법률",art:"제64조"};
  return {law:"국토의 계획 및 이용에 관한 법률",art:""};
}
// API 설명 보정 (고양시 맥락)
function regNote(name){
  if(/과밀억제권역/.test(name)) return "수도권정비계획법상 과밀억제권역 — 공장 신·증설 및 대학 등 인구집중유발시설 제한. 과밀부담금은 서울특별시에만 부과되므로 고양시는 해당 없음.";
  if(/개발제한구역/.test(name)) return "원칙적으로 건축물의 건축·용도변경·형질변경 금지. 개발제한구역법 시행령 별표1의 허용 행위만 허가 가능.";
  return "";
}

// ─────────────────────────────────────────────
// 6. 판정 엔진
// ─────────────────────────────────────────────
// 용도변경 시설군 — 건축법 시행령 제14조⑤ (1 자동차관련 … 9 그 밖의 시설군). 세부용도는 SUB 데이터의 fg 사용
var USE_GROUP = {"단독주택":8,"공동주택":8,"업무시설":8,"제1종근린생활시설":7,"제2종근린생활시설":7,"문화및집회시설":4,"판매시설":5,"숙박시설":5,"운동시설":5,"공장":2,"창고시설":2,"교육연구시설":6,"의료시설":6,"기타":7};
var USE_GROUP_NAME = {1:"자동차 관련 시설군",2:"산업 등 시설군",3:"전기통신시설군",4:"문화집회시설군",5:"영업시설군",6:"교육 및 복지시설군",7:"근린생활시설군",8:"주거업무시설군",9:"그 밖의 시설군"};
// 세부용도 77종 (research/06_세부용도 → gy_data.js)
var SUB=(typeof GY_DATA!=="undefined"&&GY_DATA.sub)||null;
var subByKey={}, subParents=[];
if(SUB){
  SUB.uses.forEach(function(u){ subByKey[u.k]=u; if(subParents.indexOf(u.p)<0) subParents.push(u.p); });
  if(SUB.fgNames) Object.keys(SUB.fgNames).forEach(function(k){ USE_GROUP_NAME[k]=SUB.fgNames[k]; });
}
function fgOf(subKey,parent){ var u=subKey&&subByKey[subKey]; return u&&u.fg || USE_GROUP[parent] || 0; }
var DEV_SIZE = { // 국토계획법 시행령 제55조① 개발행위허가 규모
  "주거":10000,"상업":10000,"자연녹지":10000,"생산녹지":10000,"공업":30000,"보전녹지":5000,"관리":30000,"농림":30000,"자연환경보전":5000
};
function zoneCat(z){ if(!z) return ""; if(/주거/.test(z)) return "주거"; if(/상업/.test(z)) return "상업"; if(/공업/.test(z)) return "공업"; if(/녹지/.test(z)) return "녹지"; if(/관리/.test(z)) return "관리"; if(z==="농림") return "농림"; if(z==="자연환경보전") return "자연환경보전"; return ""; }
function isUrban(z){ return /주거|상업|공업|녹지/.test(z||""); }

var LAW = {
  bld:"https://www.law.go.kr/법령/건축법", bldE:"https://www.law.go.kr/법령/건축법시행령",
  plan:"https://www.law.go.kr/법령/국토의계획및이용에관한법률", planE:"https://www.law.go.kr/법령/국토의계획및이용에관한법률시행령",
  park:"https://www.law.go.kr/법령/주차장법", farm:"https://www.law.go.kr/법령/농지법", forest:"https://www.law.go.kr/법령/산지관리법",
  gb:"https://www.law.go.kr/법령/개발제한구역의지정및관리에관한특별조치법", fire:"https://www.law.go.kr/법령/소방시설설치및관리에관한법률시행령",
  acc:"https://www.law.go.kr/법령/장애인ㆍ노인ㆍ임산부등의편의증진보장에관한법률시행령", green:"https://www.law.go.kr/법령/녹색건축물조성지원법시행령",
  art:"https://www.law.go.kr/법령/문화예술진흥법", traffic:"https://www.law.go.kr/법령/도시교통정비촉진법시행령",
  military:"https://www.law.go.kr/법령/군사기지및군사시설보호법", school:"https://www.law.go.kr/법령/학교용지확보등에관한특례법",
  mil:"https://www.law.go.kr/법령/군사기지및군사시설보호법"
};
function L(t,l,u){ return {t:t,l:l,u:u||null}; }
function ordSrc(key,label){ var s=src[key]; return L("ord",label||s.name,s.url); }

function judge(S,P,fx){
  var C=[], z=S.zone, zm=S.zm, sa=+S.area||0, jm=(S.jimok||"").replace(/\s/g,""), F=S.flags||{};
  var n0=fx.n0, n1=fx.n1;
  var bldEx=S.bld||null, exBa=bldEx?parseFloat(bldEx.archArea)||0:0, exTa=bldEx?parseFloat(bldEx.totArea)||0:0, exFa=bldEx?parseFloat(bldEx.vlRatEstmTotArea)||exTa:0;
  if(S.bldAll&&S.bldAll.length>1){ exBa=0;exTa=0;exFa=0; S.bldAll.forEach(function(b){ exBa+=parseFloat(b.archArea)||0; exTa+=parseFloat(b.totArea)||0; exFa+=parseFloat(b.vlRatEstmTotArea)||parseFloat(b.totArea)||0; }); }
  var isNew=P.act==="신축", isAdd=P.act==="증축", grow=isNew||isAdd||P.act==="개축"||P.act==="재축";

  // ── 입지·규제 ──
  if(F.gb) gbCheck(S,P,fx).forEach(function(c){ C.push(c); });
  if(F.facility&&F.facility.length){
    var full=F.facility.filter(function(x){return x.c==="포함";});
    C.push({g:"site",n:"도시·군계획시설 "+(full.length?"포함":"일부 저촉"),st:full.length?"fail":"warn",v:full.length?"시설 부지 포함":F.facility.length+"건 일부 저촉",
      calc:F.facility.map(function(x){return x.n+" ("+x.c+")";}).join("\n"),
      d:"도시·군계획시설 부지에서는 시설사업 외의 건축이 제한됩니다(국토계획법 제64조).\n"+(full.length?"필지 전체가 시설 부지에 포함되어 있어 일반 건축이 어렵습니다. 시설 결정·집행 현황을 확인하세요.":"저촉 부분을 제외한 면적으로 건축계획을 세우거나, 시설 결정 현황(실시계획·보상 여부)을 확인하세요."),
      src:[L("auto","토지이용규제정보"),L("law","국토계획법 제64조",LAW.plan+"/제64조")]});
  }
  if(F.military&&F.military.length) militaryCheck(S,P,fx).forEach(function(c){ C.push(c); });
  if(F.culture&&F.culture.length){
    C.push({g:"site",n:"문화유산 주변 규제",st:"warn",v:"현상변경 검토",
      calc:F.culture.join("\n"),
      d:"국가유산(문화유산) 보존구역 및 역사문화환경 보존지역 내 건설공사는 현상변경 허가 또는 허용기준 검토가 필요합니다. 고양시 문화유산 관련 부서·국가유산청 협의 대상입니다.",
      src:[L("auto","토지이용규제정보"),L("law","문화유산법 제35조","https://www.law.go.kr/법령/문화유산의보존및활용에관한법률/제35조")]});
  }
  if(F.dup&&F.dup.length&&S.dupList&&S.dupList.length) dupCheck(S,P,fx).forEach(function(c){ C.push(c); });
  else if(F.dup&&F.dup.length){
    C.push({g:"site",n:"지구단위계획구역",st:"warn",v:"결정 내용 우선",
      calc:F.dup.join(", "),
      d:"지구단위계획구역에서는 지구단위계획에서 정한 용도·건폐율·용적률·높이·배치·형태 기준이 조례 기준보다 우선 적용됩니다(국토계획법 제54조).\n해당 획지의 결정도·시행지침을 고양시 도시계획과 또는 토지이음에서 확인하세요.",
      src:[L("auto","토지이용규제정보"),L("law","국토계획법 제52조·제54조",LAW.plan+"/제54조")]});
  }
  if(F.river&&F.river.length) C.push({g:"site",n:"하천 관련 구역",st:"warn",v:"점용허가 검토",calc:F.river.join(", "),d:"하천구역 내 건축은 하천점용허가 대상이며 원칙적으로 제한됩니다(하천법 제33조·제38조).",src:[L("auto","토지이용규제정보"),L("law","하천법 제38조","https://www.law.go.kr/법령/하천법/제38조")]});
  // 침수 이력 (침수흔적도) — 지정 구역은 아니지만 지하층·저층부 계획에 영향
  if(S.flood&&S.flood.n>0){
    var fy=S.flood.years.join("·");
    C.push({g:"site",n:"침수 이력",st:"warn",v:fy+"년 침수"+(S.flood.depth>0?" · 최대 "+S.flood.depth+"m":""),
      calc:"침수흔적도 "+S.flood.n+"건이 필지와 겹침\n침수 연도: "+fy+(S.flood.depth>0?"\n기록된 최대 침수심: "+S.flood.depth+"m":""),
      d:"상습 침수·침수 우려 지역에서는 허가권자가 건축위원회 심의를 거쳐 지하층 등에 거실을 두는 건축허가를 하지 않을 수 있습니다(건축법 제11조④).\n지하층·기계실·전기실은 침수 높이 위로 배치하거나 차수판·역류방지 설비를 계획하세요. 방재지구·자연재해위험개선지구의 연면적 1만㎡ 이상 건축물은 물막이설비 설치 대상입니다(건축물의 설비기준 등에 관한 규칙 제17조의2).",
      src:[L("auto","침수흔적도 (행정안전부·고양시)"),L("law","건축법 제11조",LAW.bld+"/제11조"),L("law","건축물설비기준규칙 제17조의2","https://www.law.go.kr/법령/건축물의설비기준등에관한규칙/제17조의2")]});
  }
  districtChecks(S,P).forEach(function(c){ C.push(c); });
  if(F.landDeal) C.push({g:"site",n:"토지거래허가구역",st:"info",v:"거래 시 허가",d:"토지 매매 시 사전 허가가 필요합니다. 건축 행위 자체를 제한하지는 않습니다.",src:[L("law","부동산거래신고법 제11조","https://www.law.go.kr/법령/부동산거래신고등에관한법률/제11조")]});

  // 농지·산지 전용
  var isFarm=/^(전|답|과|과수원)$/.test(jm), isForest=/^(임|임야)$/.test(jm);
  if(isFarm&&grow){
    var inZone=F.farmZone&&F.farmZone.length, fr=inZone?0.3:0.2;
    var fee=sa&&S.price? Math.min(S.price*fr,50000)*sa : 0;
    C.push({g:"site",n:"농지전용허가",st:inZone?"fail":"warn",v:inZone?"농업진흥지역 — 전용 제한":"전용허가 필요 (지목 "+fx.jimokFull(jm)+")",
      calc:"지목이 농지("+fx.jimokFull(jm)+")이므로 건축 시 농지전용허가(신고)가 필요합니다."+(fee?"\n\n농지보전부담금 추정: "+n0(fee)+"원\n= 대지면적 "+n1(sa)+"㎡ × min(공시지가×"+(fr*100)+"%, 50,000원/㎡)\n("+(inZone?"농업진흥지역 30%":"농업진흥지역 밖 20%")+", 농지법 시행령 제53조)":""),
      d:(F.farmZone&&F.farmZone.length?"⚠ 농업진흥지역 — 농업인 주택·농업용 시설 등만 허용(농지법 제32조)\n":"")+"건축허가 신청 시 의제 처리 가능(건축법 제11조⑤).",
      src:[L("auto","지목: 연속지적도"),L("law","농지법 제34조·제38조",LAW.farm+"/제34조")]});
  }
  if(isForest&&grow){
    C.push({g:"site",n:"산지전용허가",st:"warn",v:"전용허가 필요 (임야)",
      calc:"지목이 임야이므로 산지전용허가(신고)가 필요합니다. 대체산림자원조성비 납부 및 복구비 예치 대상입니다.",
      d:(F.forest&&F.forest.length?"⚠ 보전산지("+F.forest.join(", ")+") — 전용 행위 제한(산지관리법 제12조)\n":"")+(ord.devStd?ord.devStd+altitudeNote(S.dong):"고양시 개발행위허가 기준(경사도·입목축적)도 함께 충족해야 합니다."),
      src:[L("auto","지목: 연속지적도"),L("law","산지관리법 제14조·제19조",LAW.forest+"/제14조")]});
  }

  // 접도
  var road6 = P.ta>=2000 && P.use!=="공장" || P.ta>=3000;
  var needW=road6?6:4, needC=road6?4:2, RI=S.roadInfo;
  var rst="info", rv=road6?"6m 도로에 4m 접도":"2m 이상 접도", rcalc=road6?"연면적 "+n0(P.ta)+"㎡ ≥ 2,000㎡(공장 3,000㎡) → 너비 6m 이상 도로에 4m 이상 접해야 함":"건축물 대지는 너비 4m 이상 도로에 2m 이상 접해야 함";
  if(RI){
    var okW=RI.maxW>=needW, okC=RI.contact>=needC;
    rcalc+="\n\n지적도·수치지형도 1:1,000 측정 결과\n· 도로에 접한 길이: 약 "+n1(RI.contact)+"m (필요 "+needC+"m 이상)"+
      (RI.contactLegal?"\n  - 인접 도로 필지(지목 '도') 경계: "+n1(RI.contactLegal)+"m"+(RI.roadParcels&&RI.roadParcels.length?" ("+RI.roadParcels.join(", ")+")":""):"")+
      (RI.contactPhys?"\n  - 현황 도로면 경계: "+n1(RI.contactPhys)+"m":"")+
      (RI.roads.length?"\n· 인접 도로: "+RI.roads.map(function(r){return (r.name||"이름 없음")+" 폭 "+r.w+"m";}).join(", "):"\n· 인접 도로: 확인되지 않음");
    if(!RI.contact&&!RI.roads.length){ rst="warn"; rv="도로 접함 확인 안 됨 (맹지 가능성)"; rcalc+="\n→ 농로·구거·사도 등 현황 통로가 있어도 건축법상 도로가 아니면 건축허가를 받을 수 없습니다. 진입도로 확보(사도개설·도로지정) 여부를 확인하세요."; }
    else if(okW&&okC){ rst="ok"; rv="폭 "+RI.maxW+"m 도로 · 접도 "+n1(RI.contact)+"m"; }
    else { rst="warn"; rv=(!okW?"도로 폭 "+RI.maxW+"m < "+needW+"m":"접도 "+n1(RI.contact)+"m < "+needC+"m"); }
  }
  C.push({g:"site",n:"대지와 도로의 관계",st:rst,v:rv,calc:rcalc,
    d:(RI?"수치지형도의 도로는 현황 도로입니다. 건축법상 도로(지정·고시된 도로, 너비 4m 이상)인지는 지적도·도로대장으로 확인해야 합니다.\n":"도로 현황 분석 중이거나 확인하지 못했습니다.\n")+(S.road?"도로명주소상 도로: "+S.road:""),
    src:[L("auto","도로: 수치지형도 1:1,000"),L("law","건축법 제44조",LAW.bld+"/제44조"),L("law","시행령 제28조",LAW.bldE+"/제28조")]});

  // ── 용도 ──
  var cell=z&&P.sub&&SUB&&SUB.matrix[z]&&SUB.matrix[z][P.sub], su=P.sub&&subByKey[P.sub];
  if(cell){
    var stS={ok:"ok",cond:"warn",no:"fail"}[cell.s]||"info";
    C.push({g:"use",n:"용도지역 내 건축 가능 여부",st:stS,v:{ok:"건축 가능",cond:"조건부 가능",no:"건축 불가"}[cell.s],
      calc:z+"지역에서 '"+P.sub+"' ("+P.use+")"+(cell.c?"\n→ "+cell.c:""),
      d:(cell.s==="no"?"용도지역 안에서 건축할 수 없는 건축물입니다. 용도지역 변경(지구단위계획 등) 없이는 불가합니다.\n":cell.s==="cond"?"조례·시행령이 정한 조건(규모·층수·입지)을 충족해야 합니다.\n":"")+(su?"\n용도 정의: "+su.def+" ("+su.ref+")":""),
      src:[L("auto","용도지역: 토지이용규제"),ordSrc("urban",cell.art||src.urban.name)]});
  }else if(z){
    var u=useZone[z]&&useZone[z][P.use];
    if(u){
      var st={ok:"ok",cond:"warn",no:"fail"}[u.s]||"info";
      C.push({g:"use",n:"용도지역 내 건축 가능 여부",st:st,v:{ok:"건축 가능",cond:"조건부 가능",no:"건축 불가"}[u.s],
        calc:z+"지역에서 '"+P.use+"'"+(u.c?"\n→ "+u.c:""),
        d:u.s==="no"?"용도지역 안에서 건축할 수 없는 건축물입니다. 용도지역 변경(지구단위계획 등) 없이는 불가합니다.":(u.s==="cond"?"조례로 정한 조건(규모·층수·세부 용도)을 충족해야 합니다.":""),
        src:[L("auto","용도지역: 토지이용규제"),ordSrc("urban",src.urban.name+" "+(u.art||"별표"))]});
    }else{
      C.push({g:"use",n:"용도지역 내 건축 가능 여부",st:"info",v:"세부 확인",calc:z+"지역에서 '"+P.use+"'",d:"세부 용도(시행령 별표1의 세분)에 따라 판단이 달라집니다.",src:[ordSrc("urban")]});
    }
  }
  if(P.act==="용도변경"){
    var to=fgOf(P.sub,P.use)||7, from=fgOf(P.from,P.fromParent||P.from)||0, kind;
    if(!from) kind="변경 전 용도를 선택하세요";
    else if(from===to) kind="같은 시설군 → 건축물대장 기재내용 변경 신청";
    else if(to<from) kind="하위군 → 상위군 이동 → 허가";
    else kind="상위군 → 하위군 이동 → 신고";
    C.push({g:"proc",n:"용도변경 절차",st:from?"info":"warn",v:from?(to<from?"허가":from===to?"기재변경":"신고"):"확인 필요",key:"permitType",
      calc:(P.from||"?")+" (제"+(from||"?")+"군 "+(USE_GROUP_NAME[from]||"")+")\n→ "+(P.sub||P.use)+" (제"+to+"군 "+USE_GROUP_NAME[to]+")\n\n"+kind,
      d:"시설군 순위: 1 자동차 관련 → 2 산업 등 → 3 전기통신 → 4 문화집회 → 5 영업 → 6 교육 및 복지 → 7 근린생활 → 8 주거업무 → 9 그 밖의 시설군\n(숫자가 작을수록 상위군 — 상위군으로 변경은 허가, 하위군으로 변경은 신고)\n\n용도변경 후 용도 기준으로 주차장·소방·장애인편의·정화조 기준을 다시 충족해야 합니다.",
      src:[L("input","용도: 입력값"),L("law","건축법 제19조",LAW.bld+"/제19조"),L("law","시행령 제14조",LAW.bldE+"/제14조")]});
  }

  // ── 규모·밀도 ──
  if(zm&&sa){
    var limB=zm.b, limF=zm.f;
    if(P.ba>0){
      var ba=isAdd?P.ba+exBa:P.ba, r=ba/sa*100, ok=r<=limB;
      C.push({g:"scale",n:"건폐율"+(isAdd?" (기존 합산)":""),st:ok?"ok":"fail",v:n1(r)+"% / "+limB+"%",bar:{p:r/limB*100},
        calc:(isAdd?"기존 "+n1(exBa)+"㎡ + 증축 "+n1(P.ba)+"㎡ = "+n1(ba)+"㎡\n":"")+"건축면적 "+n1(ba)+"㎡ ÷ 대지면적 "+n1(sa)+"㎡ = "+n1(r)+"%\n한도 "+limB+"% ("+z+"지역) → 최대 "+n0(sa*limB/100)+"㎡",
        d:ok?"건폐율 기준을 충족합니다.":"한도를 "+n1(r-limB)+"%p 초과합니다. 건축면적을 "+n0(ba-sa*limB/100)+"㎡ 줄여야 합니다.",
        src:[L("auto","대지면적: 지적도"),L("input","건축면적: 입력값"),ordSrc("urban",src.urban.name+" "+zm.bArt)]});
    }
    if(P.fa>0){
      var fa=isAdd?P.fa+exFa:P.fa, r2=fa/sa*100, ok2=r2<=limF;
      C.push({g:"scale",n:"용적률"+(isAdd?" (기존 합산)":""),st:ok2?"ok":"fail",v:n1(r2)+"% / "+limF+"%",bar:{p:r2/limF*100},
        calc:(isAdd?"기존 "+n1(exFa)+"㎡ + 증축 "+n1(P.fa)+"㎡ = "+n1(fa)+"㎡\n":"")+"용적률 산정 연면적 "+n1(fa)+"㎡ ÷ 대지면적 "+n1(sa)+"㎡ = "+n1(r2)+"%\n한도 "+limF+"% ("+z+"지역) → 최대 "+n0(sa*limF/100)+"㎡",
        d:(ok2?"용적률 기준을 충족합니다.":"한도를 "+n1(r2-limF)+"%p 초과합니다.")+"\n※ 지하층·지상 주차용·피난안전구역 면적은 용적률 산정에서 제외됩니다."+(zm.fNote?"\n※ "+zm.fNote+" (조례 제61조)":"")+(zm.adj&&zm.adj.length?"\n※ 지구·구역 조정: "+zm.adj.join(", "):""),
        src:[L("auto","대지면적: 지적도"),L("input","연면적: 입력값"),ordSrc("urban",src.urban.name+" "+zm.fArt)]});
    }
    if(P.fl>0&&zm.h){
      var ok3=P.fl<=zm.h;
      C.push({g:"scale",n:"층수 제한",st:ok3?"ok":"fail",v:P.fl+"층 / "+zm.h+"층 이하",calc:z+"지역 → "+zm.h+"층 이하"+(zm.hNote?" ("+zm.hNote+")":""),d:ok3?"":"층수 제한을 초과합니다.",src:[L("input","층수: 입력값"),ordSrc("urban",src.urban.name+(zm.hArt?" "+String(zm.hArt).replace(/^조례\s*/,""):""))]});
    }
    if(isAdd&&!bldEx) C.push({g:"scale",n:"기존 건축물 확인",st:"warn",v:"대장 미확인",d:"증축은 기존 건축물과 합산하여 건폐율·용적률을 산정합니다. 건축물대장 조회 결과가 없어 신청 면적만으로 계산했습니다.",src:[L("auto","건축물대장(건축HUB)")]});
  }
  if(!z) C.push({g:"scale",n:"용도지역",st:"warn",v:"확인 필요",d:"용도지역을 확인하지 못해 밀도 검토를 생략했습니다. 토지이음에서 토지이용계획을 확인하세요.",src:[L("auto","토지이용규제정보")]});

  // 일조 (전용·일반주거지역)
  if(P.ht>0 && /전용주거|일반주거/.test(z||"")){
    var need=P.ht<=10?1.5:Math.ceil(P.ht/2*10)/10;
    C.push({g:"scale",n:"일조 확보 (정북방향 이격)",st:"info",v:"정북 인접대지 "+need+"m 이상",
      calc:"높이 "+P.ht+"m → "+(P.ht<=10?"10m 이하 부분 1.5m 이상":"10m 초과 부분 높이의 1/2 = "+need+"m 이상"),
      d:(ord.sunlight||"전용주거지역·일반주거지역에서 적용됩니다.")+"\n공동주택은 채광 방향 인동거리 기준이 별도로 적용됩니다.",
      src:[L("law","건축법 제61조",LAW.bld+"/제61조"),L("law","시행령 제86조",LAW.bldE+"/제86조"),ordSrc("building")]});
  }
  // 건축선·대지 안의 공지
  if(ord.setback){
    var sb=ord.setback(P.use,P.ta,z||"");
    if(sb) C.push({g:"scale",n:"대지 안의 공지",st:"info",v:"건축선 "+sb.line,calc:"건축선으로부터: "+sb.line+"\n인접 대지경계선으로부터: "+sb.adj+(sb.cond?"\n적용: "+sb.cond:""),d:"용도·규모별 이격거리입니다. 상업지역·지구단위계획구역 등은 별도 기준이 적용될 수 있습니다.",src:[L("law","건축법 제58조",LAW.bld+"/제58조"),ordSrc("building",src.building.name+" "+(sb.art||""))]});
  }

  // ── 절차 ──
  var pt="허가", pr="건축법 제11조에 따른 건축허가 대상";
  var nonUrban=/관리|농림|자연환경보전/.test(z||"");
  if(isNew||P.act==="개축"||P.act==="재축"||isAdd){
    if((isAdd||P.act==="개축"||P.act==="재축")&&P.ta>0&&P.ta<=85){ pt="신고"; pr="바닥면적 합계 85㎡ 이내 "+P.act+" → 건축신고 (건축법 제14조①1호)"; }
    else if(isNew&&nonUrban&&P.ta>0&&P.ta<200&&P.fl>0&&P.fl<3&&!(F.dup&&F.dup.length)){ pt="신고"; pr="관리·농림·자연환경보전지역 연면적 200㎡ 미만 + 3층 미만 → 건축신고 (건축법 제14조①2호)"; }
    else if(P.ta>0&&P.ta<=100){ pt="신고"; pr="연면적 합계 100㎡ 이하 → 건축신고 (건축법 제14조①5호, 시행령 제11조③)"; }
  }else if(P.act==="대수선"){
    if(P.ta>0&&P.ta<200&&P.fl>0&&P.fl<3){ pt="신고"; pr="연면적 200㎡ 미만 + 3층 미만 건축물의 대수선 → 건축신고 (건축법 제14조①4호)"; }
    else { pr="연면적 200㎡ 이상 또는 3층 이상 건축물의 대수선 → 허가 (주요구조부 해체 없는 대수선은 신고 가능)"; }
  }
  if(P.act!=="용도변경"){
    C.push({g:"proc",n:"허가·신고 구분",st:"info",v:"건축"+pt,key:"permitType",calc:pr,
      d:"신청: 세움터(www.eais.go.kr) 전자 접수\n"+(authority(S,P).text),
      src:[L("input","행위·규모: 입력값"),L("law","건축법 제11조",LAW.bld+"/제11조"),L("law","건축법 제14조",LAW.bld+"/제14조")]});
  }
  if(P.act==="대수선"){
    C.push({g:"proc",n:"대수선 해당 범위",st:"info",v:"범위 확인",calc:"① 내력벽 30㎡ 이상 ② 기둥·보·지붕틀 각 3개 이상\n③ 방화벽·방화구획 ④ 주계단·피난계단\n⑤ 다가구·다세대 경계벽 ⑥ 외벽 마감재료(일정 규모 이상)\n의 증설·해체·수선·변경",d:"위 범위에 해당하지 않는 수선은 대수선이 아닙니다.",src:[L("law","건축법 시행령 제3조의2",LAW.bldE+"/제3조의2")]});
  }
  // 건축위원회 심의
  if(ord.committee){
    var cr=ord.committee(P,S);
    var onlyMulti=cr&&cr.length===1&&/다중이용/.test(cr[0]);
    if(cr&&cr.length) C.push({g:"proc",n:"건축위원회 심의",st:onlyMulti?"info":"warn",v:onlyMulti?"지정지역 여부 확인":"심의 대상",calc:cr.join("\n"),d:"건축허가 전 고양시 건축위원회 심의를 받아야 합니다. 심의 일정(월 1~2회)을 고려하세요.",src:[L("law","건축법 제4조의2",LAW.bld+"/제4조의2"),ordSrc("building",src.building.name+" "+(ord.committeeArt||""))]});
  }
  // 경관심의
  if(ord.landscapeReview){
    var lr=ord.landscapeReview(P,S);
    if(lr&&lr.length) C.push({g:"proc",n:"경관 심의",st:"warn",v:"심의 대상",calc:lr.join("\n"),d:"경관위원회(또는 건축위원회 공동) 심의 대상입니다.",src:[L("law","경관법 제28조","https://www.law.go.kr/법령/경관법/제28조")].concat(ord.landscapeReviewSrc?[ord.landscapeReviewSrc]:[])});
  }
  // 개발행위허가
  if(grow&&sa){
    var formChange = jm!=="대" && !/^(장|학|창|종|주|체|잡)$/.test(jm);
    var cat=zoneCat(z), limit=DEV_SIZE[z]||DEV_SIZE[cat]||null;
    var st4=formChange?"warn":"ok";
    var txt=formChange?"지목 '"+fx.jimokFull(jm)+"' → 토지 형질변경 수반 → 개발행위허가 대상 (건축허가 시 의제)":"지목 '"+fx.jimokFull(jm)+"' → 형질변경 없는 건축은 개발행위허가 불요 (절·성토 50cm 초과 시 필요)";
    if(formChange&&limit&&sa>=limit){ st4="fail"; txt+="\n⚠ 대지면적 "+n0(sa)+"㎡ ≥ 허가 규모 "+n0(limit)+"㎡ → 개발행위 규모 초과(도시계획위원회 심의·지구단위계획 등 필요)"; }
    // 지형 기준 — 고양시 도시계획 조례 제19조·별표29 (경사도 15° 미만, 산지 포함 시 법정동별 표고)
    var T=S.terrain, forestish=/^(임|임야)$/.test(jm)||(F.forest&&F.forest.length);
    if(T&&(formChange||forestish)){
      var tl=[], tst="ok", lim=ALT[S.dong];
      if(T.slope!=null){ tl.push("평균경사 약 "+T.slope.toFixed(1)+"° (기준 15° 미만)"); if(T.slope>=15){ tst="warn"; tl.push("→ 15° 이상: 고양시 도시계획위원회 심의를 거쳐야 허가 가능"); } }
      else tl.push("필지 안을 지나는 5m 등고선 없음 → 높이차 5m 미만의 완만한 지형");
      if(T.max!=null) tl.push("표고 약 "+(T.min===T.max?T.min:T.min+"~"+T.max)+"m");
      if(forestish&&lim){ tl.push(S.dong+" 표고 기준 "+lim+"m 이하 (산지 포함 개발행위)"); if(T.max>lim){ tst="fail"; tl.push("→ 기준 초과 구간 있음: 원칙 불허 (초과면적 10% 이하 잔여임야 등은 도계위 심의)"); } }
      C.push({g:"proc",n:"개발행위 지형 기준 (경사·표고)",st:tst,v:tst==="fail"?"표고 기준 초과":tst==="warn"?"경사 15° 이상":"기준 이내",
        calc:tl.join("\n"),
        d:"고양시 5m 등고선(서버 Goyang_Contour_5m)으로 추정한 값입니다. 평균경사 = 등고선 간격 × 필지 안 등고선 길이 ÷ 필지 면적. 허가 신청 시에는 측량 성과(경사도 조사서)로 확인합니다.",
        src:[L("auto","지형: 고양시 5m 등고선"),ordSrc("urban",src.urban.name+" 제19조·별표29")]});
    }
    C.push({g:"proc",n:"개발행위허가",st:st4,v:formChange?(st4==="fail"?"규모 초과":"대상"):"해당 없음",
      calc:txt+(limit?"\n\n"+(z||"")+"지역 개발행위허가 규모: "+n0(limit)+"㎡ 미만":""),
      d:(ord.devStd||"")+(formChange?"\n개발행위허가 기준: 경사도·입목축적·기반시설 등 고양시 도시계획 조례 기준 충족 필요":""),
      src:[L("auto","지목: 지적도"),L("law","국토계획법 제56조",LAW.plan+"/제56조"),L("law","시행령 제55조",LAW.planE+"/제55조"),ordSrc("urban",src.urban.name+(ord.devArt?" "+ord.devArt:""))]});
  }
  // 교통영향평가
  if(GYX.traffic){ var tr=GYX.traffic(P); if(tr) C.push({g:"proc",n:"교통영향평가",st:"warn",v:"평가 대상",calc:tr,d:"건축허가 전 교통영향평가 심의를 받아야 합니다.",src:[L("law","도시교통정비 촉진법 시행령 별표1",LAW.traffic)]}); }

  // ── 설치의무·부담 ──
  // 조경
  if(ord.landscape&&sa){
    var ls=ord.landscape(sa,P.ta,z||"",P.use);
    if(ls&&ls.req) C.push({g:"duty",n:"대지 안의 조경",st:"info",v:n0(sa*ls.pct/100)+"㎡ ("+ls.pct+"%)",calc:"대지면적 "+n1(sa)+"㎡ × "+ls.pct+"% = "+n0(sa*ls.pct/100)+"㎡\n"+(ls.text||""),d:ls.detail||"",src:[L("law","건축법 제42조",LAW.bld+"/제42조"),ordSrc("building",src.building.name+" "+(ls.art||""))]});
    else if(ls&&ls.text) C.push({g:"duty",n:"대지 안의 조경",st:"ok",v:"설치 제외",calc:ls.text,src:[L("law","건축법 제42조",LAW.bld+"/제42조"),ordSrc("building")]});
  }
  // 공개공지
  if(ord.publicSpace&&P.ta){
    var ps=ord.publicSpace(P.ta,z||"",P.use);
    if(ps&&ps.req) C.push({g:"duty",n:"공개공지 확보",st:"warn",v:"대지면적의 "+ps.pct+"%"+(sa?" ("+n0(sa*ps.pct/100)+"㎡)":""),calc:ps.text||"",d:ps.detail||"",src:[L("law","건축법 제43조",LAW.bld+"/제43조"),ordSrc("building",src.building.name+" "+(ps.art||""))]});
  }
  // 주차
  if(P.ta>0){
    var pk=parkingCalc(P);
    if(pk) C.push({g:"duty",n:"부설주차장",st:"info",v:typeof pk.cnt==="number"?pk.cnt+"대 이상":pk.cnt,calc:pk.calc,d:pk.detail,src:[L("input","용도·면적: 입력값"),L("law","주차장법 제19조",LAW.park+"/제19조"),ordSrc("parking",src.parking.name+" "+(pk.art||""))]});
  }
  // 소방 — 소방시설법 시행령 제7조(건축허가 동의)·별표4 (research/07)
  if(P.ta>0||P.fl>0){
    var fi=[], u=P.use, sb=P.sub||"", ta=P.ta, fl=P.fl;
    var lodge=/숙박/.test(u), apt=/아파트|기숙사/.test(sb)||(u==="공동주택"&&!/연립|다세대|도시형/.test(sb));
    var consent= ta>=400 || fl>=6 || u==="공동주택" || lodge || (/교육연구/.test(u)&&ta>=100) || /의원/.test(sb) || P.uf>0;
    if(consent) fi.push("건축허가 동의 대상 — 연면적 400㎡ 이상·6층 이상·공동주택·숙박시설·주차용 층 등 (영 제7조)");
    if(fl>=6) fi.push("스프링클러 — 6층 이상 모든 층");
    else if((lodge||/의료/.test(u))&&ta>=600) fi.push("스프링클러 — "+u+" 바닥면적 합계 600㎡ 이상 모든 층");
    else if((/판매|창고/.test(u))&&ta>=5000) fi.push("스프링클러 — "+u+" 바닥면적 합계 5,000㎡ 이상");
    else if(/연립|다세대/.test(sb)) fi.push("간이스프링클러 — 연립·다세대주택");
    else if(/근린생활/.test(u)&&ta>=1000) fi.push("간이스프링클러 — 근린생활시설 바닥면적 합계 1,000㎡ 이상 모든 층");
    else if(lodge&&ta>=300) fi.push("간이스프링클러 — 숙박시설 300~600㎡");
    var hydrant= ta>=3000 || (/근린|판매|업무|숙박|의료|공장|창고/.test(u)&&ta>=1500);
    if(hydrant) fi.push("옥내소화전 — 연면적 3,000㎡ 이상 (근생·판매·업무·숙박·의료·공장·창고 등은 1,500㎡ 이상)");
    var afd= apt||lodge||fl>=6 || (/근린생활|의료|위락|장례/.test(u)&&ta>=600) || (/문화및집회|종교|판매|운수|운동|업무|공장|창고/.test(u)&&ta>=1000) || (/교육연구|수련/.test(u)&&ta>=2000);
    if(afd) fi.push("자동화재탐지설비 — "+(apt?"아파트·기숙사 모든 층":lodge?"숙박시설 모든 층":fl>=6?"6층 이상 모든 층":"용도별 기준 면적 이상 (근생 600㎡, 업무·판매 1,000㎡ 등)"));
    if(ta>=3500||fl>=11||P.uf>=3) fi.push("비상방송설비 — 연면적 3,500㎡ 이상·11층 이상·지하 3층 이상");
    if(fl>=11) fi.push("비상콘센트 — 11층 이상의 층");
    if((fl>=5&&ta>=6000)||(fl+P.uf)>=7) fi.push("연결송수관 — 5층 이상·6,000㎡ 이상 또는 지하 포함 7층 이상");
    if(ta>=5000) fi.push("상수도 소화용수 — 연면적 5,000㎡ 이상");
    if(fl>=30||P.ht>=120||ta>=200000||(u==="공동주택"&&(fl>=50||P.ht>=200))) fi.push("성능위주설계 대상 — 30층·120m 이상(아파트 50층·200m) 또는 연면적 20만㎡ 이상");
    var fireSt = FIRE_ST[S.gu]||FIRE_ST["일산동구"];
    if(fi.length) C.push({g:"duty",n:"소방시설",st:"info",v:fi.length+"개 항목",calc:fi.map(function(x,i){return (i+1)+". "+x;}).join("\n"),d:"세부 층별 면적·수용인원에 따라 추가될 수 있습니다. 건축허가 동의: "+fireSt,src:[L("law","소방시설법 시행령 제7조·별표4",LAW.fire)]});
  }
  // 장애인 등 편의시설 — 장애인등편의법 시행령 별표1 (research/07)
  var acc=accTarget(P);
  if(acc) C.push({g:"duty",n:"장애인 등 편의시설",st:acc.yes?"warn":"ok",v:acc.yes?"설치 대상":"대상 아님",calc:acc.text,d:acc.yes?"주출입구 접근로, 장애인 전용 주차구획, 출입구·복도, 승강기(해당 시), 화장실 등 설치와 사용승인 전 적합성 확인이 필요합니다.":"",src:[L("law","장애인등편의법 시행령 별표1",LAW.acc)]});
  // 에너지 — 녹색건축법 시행령 제10조, 에너지절약설계기준 (research/07)
  if(P.ta>=500&&grow){
    var en=["에너지절약계획서 제출 — 연면적 합계 500㎡ 이상 (녹색건축법 시행령 제10조)"];
    if(P.ta>=1000) en.push("에너지절약설계기준 필수항목 적용 — 연면적 1,000㎡ 이상 신축·재축·별동증축 (에너지성능지표 65점 이상)");
    en.push("제로에너지건축물 인증은 공공건축물만 의무 — 민간 건축물은 의무 없음");
    C.push({g:"duty",n:"에너지 절약 설계",st:"info",v:P.ta>=1000?"설계기준 필수항목":"계획서 제출",calc:en.join("\n"),d:ord.green||"",src:[L("law","녹색건축법 시행령 제10조",LAW.green+"/제10조")]});
  }
  // 미술작품
  if(ord.artwork&&P.ta>=ord.artwork.minArea&&!/단독주택/.test(P.use)){
    C.push({g:"duty",n:"건축물 미술작품",st:"warn",v:"설치 대상",calc:"연면적 "+n0(P.ta)+"㎡ ≥ "+n0(ord.artwork.minArea)+"㎡\n"+(ord.artwork.rate||""),d:ord.artwork.detail||"미술작품 설치 또는 문화예술진흥기금 출연 중 선택",src:[L("law","문화예술진흥법 제9조",LAW.art+"/제9조"),ord.artwork.src||ordSrc("building")]});
  }
  // 안전관리예치금
  if(ord.safetyDeposit&&P.ta>=ord.safetyDeposit.minArea&&grow){
    C.push({g:"duty",n:"안전관리예치금",st:"info",v:"착공 전 예치",calc:"연면적 "+n0(P.ta)+"㎡ ≥ "+n0(ord.safetyDeposit.minArea)+"㎡ → 대상\n"+(ord.safetyDeposit.rate||""),d:"공사 중단 시 안전조치 비용 확보를 위해 착공신고 전 예치(현금·보증서)",src:[L("law","건축법 제13조",LAW.bld+"/제13조"),ordSrc("building",src.building.name+" "+(ord.safetyDeposit.art||""))]});
  }
  // 수수료
  if(ord.fee&&P.ta>0){
    var fe=ord.fee(P.ta,P.use==="단독주택");
    if(fe!=null) C.push({g:"duty",n:"건축허가 수수료",st:"info",v:n0(fe)+"원",calc:"연면적 "+n0(P.ta)+"㎡ · "+(P.use==="단독주택"?"단독주택":"그 외 건축물")+" 기준",src:[L("law","건축법 제17조",LAW.bld+"/제17조"),ordSrc("building",src.building.name+" "+(ord.feeArt||""))]});
  }
  // 부담금
  var ch=GYX.charges? GYX.charges(P,S) : [];
  if(ch.length) C.push({g:"duty",n:"부담금 (개략)",st:"info",v:ch.length+"개 항목",calc:ch.map(function(x,i){return (i+1)+". "+x;}).join("\n"),d:"부과 여부·금액은 사업계획 확정 후 각 부과기관에서 산정합니다.",src:[L("law","학교용지법 제5조",LAW.school+"/제5조"),L("ord","고양시 하수도 사용 조례","https://www.law.go.kr/자치법규/고양시하수도사용조례")]});

  return C;
}

// ─────────────────────────────────────────────
// 지구단위계획 — research/04 (34개 구역, 시행지침·결정고시)
//   서버 폴리곤(이름 없음) → polyMap 후보 ∩ 법정동 후보 → 구역 확정
// ─────────────────────────────────────────────
var DUPD=(typeof GY_DATA!=="undefined"&&GY_DATA.dup)||null;
function hav(lon1,lat1,lon2,lat2){ var R=6371000,t=Math.PI/180,a=Math.pow(Math.sin((lat2-lat1)*t/2),2)+Math.cos(lat1*t)*Math.cos(lat2*t)*Math.pow(Math.sin((lon2-lon1)*t/2),2); return 2*R*Math.asin(Math.sqrt(a)); }
function dupDistricts(objectids,dong,jibun,lon,lat){
  if(!DUPD) return [];
  var poly=[]; (objectids||[]).forEach(function(o){ (DUPD.polyMap[o]||[]).forEach(function(i){ if(poly.indexOf(i)<0) poly.push(i); }); });
  var byDong=[]; DUPD.districts.forEach(function(z,i){ if((z.dongs||[]).indexOf(dong)>=0) byDong.push(i); });
  var spotOk=function(i){ var sp=DUPD.spot&&DUPD.spot[i]; return sp && sp.dong===dong && String(jibun||"").indexOf(sp.jibunPrefix)===0; };
  var isSpot=function(i){ return !!(DUPD.spot&&DUPD.spot[i]); };
  // 특별계획구역 같은 지점형 구역은 지번이 맞을 때만 남김
  poly=poly.filter(function(i){ return !isSpot(i)||spotOk(i); });
  byDong=byDong.filter(function(i){ return !isSpot(i)||spotOk(i); });
  var both=poly.filter(function(i){return byDong.indexOf(i)>=0;});
  var base=both.length?both:poly;            // 폴리곤으로 확인된 구역
  var spots=base.filter(isSpot), plain=base.filter(function(i){return !isSpot(i);});
  if(base.length&&plain.length<=1) // 확정: 일반 구역 1개 (+ 그 안의 특별계획구역)
    return spots.concat(plain).map(function(i){ return {idx:i,z:DUPD.districts[i],certain:true}; });
  // 폴리곤 정보가 없고 그 동에 조사된 구역이 하나뿐이면 '동 기준 추정'
  var plainDong=byDong.filter(function(i){return !isSpot(i);});
  if(!base.length&&plainDong.length===1)
    return byDong.filter(isSpot).concat(plainDong).map(function(i){ return {idx:i,z:DUPD.districts[i],certain:"dong"}; });
  // 같은 동에 여러 구역: 대표 지번 위치와의 거리로 추정 (700m 이내 + 다음 후보보다 1.8배 이상 가까울 때만)
  if(!base.length&&plainDong.length>1&&lon&&DUPD.repPoints){
    var dist=plainDong.map(function(i){ var ps=DUPD.repPoints[i]||[]; var d=Infinity; ps.forEach(function(p){ var dd=hav(lon,lat,p[0],p[1]); if(dd<d) d=dd; }); return {i:i,d:d}; }).sort(function(a,b){return a.d-b.d;});
    if(dist[0].d<700&&(dist.length<2||dist[1].d>=dist[0].d*1.8))
      return byDong.filter(isSpot).concat([dist[0].i]).map(function(i){ return {idx:i,z:DUPD.districts[i],certain:"near",dist:Math.round(dist[0].d)}; });
  }
  var cands=base.length?base:byDong;         // 미확정: 후보만 제시
  return cands.map(function(i){ return {idx:i,z:DUPD.districts[i],certain:false}; });
}
function blockMatches(b,P,zone){
  var t=(b.type||"")+" "+(b.use||""), u=P.use;
  var useOk = u==="단독주택"?/단독/.test(t) : u==="공동주택"?/아파트|공동|연립|복합|주상/.test(t) : /근린생활/.test(u)?/근린생활|단독|상업|점포/.test(t) : /판매|업무|숙박|문화|의료|운동|교육/.test(u)?/상업|업무|복합|지원|공공|교육|의료|종교/.test(t) : /공장|창고/.test(u)?/산업|공장|도시지원|자족|기업|유통|물류/.test(t) : true;
  var zz=(b.zone||"")+" "+(b.type||"");
  var zoneOk = !zone || !b.zone ? true : (zone.indexOf("상업")>=0? (/상업/.test(zz)&&(zz.indexOf(zone.replace("상업",""))>=0||!/근린|일반|중심/.test(zz))) : /주거/.test(zone)? /주거|단독|연립|아파트|근린생활/.test(zz) : true);
  return useOk&&zoneOk;
}
function floorsMax(s){ if(!s) return null; var m=String(s).match(/최고\s*(\d+)\s*층|(\d+)\s*층\s*이하/); return m?+(m[1]||m[2]):null; }
function dupCheck(S,P,fx){
  var out=[], n1=fx.n1, list=S.dupList||[];
  if(!list.length) return out;
  if(!list[0].certain){
    out.push({g:"site",n:"지구단위계획구역 — 구역 확인 필요",st:"warn",v:"후보 "+list.length+"곳",
      calc:"이 필지가 속한 지구단위계획구역을 자동으로 특정하지 못했습니다.\n같은 동의 조사된 구역(후보): "+list.map(function(c){return c.z.name.replace(/\(.*$/,"").trim();}).join(", "),
      d:"토지이음 토지이용계획에서 구역명과 결정도를 확인한 뒤, 상단 후보 버튼에서 해당 구역의 블록 기준을 보세요. 조사 범위 밖의 소규모 구역일 수도 있습니다.",
      src:[L("auto","토지이음에서 구역 확인","https://www.eum.go.kr/web/ar/lu/luLandDet.jsp?pnu="+S.pnu+"&mode=search&isNoScr=script&selGbn=umd")]});
    return out;
  }
  list.slice(0,3).forEach(function(c){
    var z=c.z, sa=+S.area||0, bcr=sa?P.ba/sa*100:0, far=sa?P.fa/sa*100:0;
    var cand=(z.blocks||[]).filter(function(b){return blockMatches(b,P,S.zone);});
    var probs=[], lines=[];
    cand.slice(0,6).forEach(function(b){
      var fm=b.far&&(b.far.max||b.far.allowed||b.far.base), fl=floorsMax(b.floors);
      lines.push("· "+b.type+(b.zone?" ["+b.zone+"]":"")+" — 건폐율 "+(b.bcr!=null?b.bcr+"%":"조례 준용")+" · 용적률 "+(fm?(b.far.base&&b.far.max&&b.far.base!==b.far.max?b.far.base+"/"+(b.far.allowed||"-")+"/"+b.far.max+"%(기준/허용/상한)":fm+"%"):"조례 준용")+" · "+(b.floors||"층수 별도 없음"));
      if(cand.length===1){
        if(b.bcr!=null&&P.ba&&bcr>b.bcr) probs.push("건폐율 "+n1(bcr)+"% > "+b.bcr+"%");
        if(fm&&P.fa&&far>fm) probs.push("용적률 "+n1(far)+"% > "+fm+"%");
        if(fl&&P.fl&&P.fl>fl) probs.push("층수 "+P.fl+"층 > "+fl+"층");
      }
    });
    var b0=cand[0];
    // 필지의 실제 블록은 결정도로만 확정되므로 비교 결과는 '해당 블록이라면'으로 안내
    if(probs.length) probs=probs.map(function(p){ return "'"+b0.type+"' 블록이라면 "+p; });
    var st="warn";
    var v=probs.length?"해당 블록이면 기준 초과":(cand.length?cand.length+"개 블록 유형 해당 가능":"블록 기준 확인 필요");
    var dec=z.decision||{};
    out.push({g:"site",n:"지구단위계획 — "+z.name.replace(/\(.*$/,"").trim(),st:st,v:v,
      calc:(c.certain==="dong"?"※ 법정동 기준 추정 — 이 동에서 조사된 지구단위계획구역은 이 구역뿐입니다 (조사 밖 소규모 구역일 수 있음)\n":c.certain==="near"?"※ 위치 기준 추정 — 구역 대표 지점에서 약 "+c.dist+"m (토지이음에서 구역명 확인 권장)\n":"")+(lines.length?lines.join("\n"):"이 용도에 해당하는 블록 기준을 찾지 못했습니다.")+(probs.length?"\n\n✕ "+probs.join("\n✕ "):""),
      d:(b0&&(b0.allowed||b0.prohibited)?"허용: "+String(b0.allowed||"-").slice(0,220)+(b0.prohibited?"\n불허: "+String(b0.prohibited).slice(0,160):"")+"\n":"")+(b0&&b0.shop?"점포 비율: "+b0.shop+"\n":"")+(b0&&b0.hh?"가구 수: "+b0.hh+"\n":"")+(b0&&b0.notes?"비고: "+String(b0.notes).slice(0,200)+"\n":"")+
        "\n필지가 속한 블록(획지)은 결정도로 확인해야 정확합니다."+(z.status==="partial"?" 이 구역은 조사 범위가 일부입니다.":"")+(dec.no?"\n최신 결정: "+dec.no+" ("+(dec.date||"")+")":""),
      src:[L("auto","지구단위계획구역: 토지이용규제")].concat(dec.url?[L("ord",dec.no||"결정 고시",dec.url)]:[]).concat(typeof z.guideline==="string"&&/^https?:/.test(z.guideline.split(" ")[0])?[L("ord","시행지침",z.guideline.split(" ")[0])]:[])});
  });
  if(DUPD&&DUPD.renewal&&list.some(function(c){return /일산 지구단위계획\(일산신도시/.test(c.z.name);}))
    out.push({g:"site",n:"일산신도시 재정비 (노후계획도시특별법)",st:"info",v:"기본계획 수립 · 특별정비구역 미지정",calc:String(DUPD.renewal.note||"").slice(0,600),src:[L("law","노후계획도시정비법","https://www.law.go.kr/법령/노후계획도시정비및지원에관한특별법")]});
  return out;
}

// ─────────────────────────────────────────────
// 군사기지·군사시설 보호구역 — research/07 (군사기지법 제9·10·13·14조, 영 제13·14조)
//   토지이용규제 명칭의 "(고도 N m 위임지역)" = 관할부대가 고양시에 협의를 위탁한 높이 한도
// ─────────────────────────────────────────────
var DELEG_RE=/\((해발)?고도\s?(\d+(?:\.\d+)?)\s?m\s?(위임지역)?\)/;
var AIR_RE=/위탁고도\s?:?\s?(\d+)\s?-\s?(\d+)\s?m/;
function militaryCheck(S,P,fx){
  var out=[], names=(S.regNames||[]).filter(function(n){return /보호구역|비행안전|대공방어|민간인통제/.test(n)&&!/문화|유산|상수원|수산|어린이|노인|장애인|생태|습지|야생|교육환경|상대보호|절대보호/.test(n);});
  if(!names.length) return out;
  var lawSrc=L("law","군사기지법 제13조·제14조",LAW.mil+"/제13조"), ht=P.ht||0, grow=/신축|증축|개축|재축/.test(P.act);
  var seen={};
  names.forEach(function(nm){
    var base=nm.replace(/<[^>]*>/g,"").trim(); if(seen[base]) return; seen[base]=1;
    var m=base.match(DELEG_RE), deleg=m?parseFloat(m[2]):null, sea=m&&!!m[1];
    var partial=m&&names.some(function(x){ return x!==nm && x.replace(/\([^)]*위임지역\)/,"").replace(/<[^>]*>/g,"").trim()===base.replace(/\([^)]*위임지역\)/,"").trim(); });
    var st="warn", v="관할부대 협의", calc=base, d="";
    if(/^통제보호구역|민간인통제/.test(base)){ st="fail"; v="원칙적 신축 금지"; d="통제보호구역에서는 건축물 신축이 원칙적으로 금지됩니다. 예외(공공사업, 관할부대장이 인정한 창고·동식물관련시설·농업용 가설건축물 200㎡ 이하)도 협의가 필요합니다(법 제9조①1호)."; }
    else if(/^비행안전제1구역/.test(base)){ st="fail"; v="건축 불가"; d="비행안전 제1구역(장애제거구역)은 군사시설 외 건축물·공작물을 설치할 수 없습니다(법 제10조①1호)."; }
    else if(/^비행안전제\d구역/.test(base)){ v="표면높이 확인·협의"; d="구역별 장애물 표면높이 이상은 건축할 수 없고, 저촉 우려가 있으면 관할부대 협의 대상입니다(법 제10조, 제13조②1호). 표면높이는 기지 기준표면에서 계산하므로 부대 확인이 필요합니다."+(/헬기/.test(base)?"\n수색비행장은 2026.9.29. 헬기전용 작전기지로 변경되어 제1~3구역만 적용됩니다(국방부 고시 제2026-35호).":""); }
    else if(/^대공방어협조구역/.test(base)){ var a=base.match(AIR_RE); v=a?"위탁고도 "+a[1]+"~"+a[2]+"m":"높이 협의"; d="위탁고도 이하는 고양시 자체 처리, 초과하면 관할부대 협의(법 제13조②2호)."; if(a&&ht&&ht<=+a[1]){ st="ok"; v="위탁고도 이하 — 협의 생략"; } }
    else if(/폭발물/.test(base)){ v="관할부대 협의 (개축·대수선 포함)"; d="폭발물 관련 제한보호구역은 개축·재축·대수선·가설건축물·건축신고·용도변경신고도 협의 대상입니다(영 제13조③ 단서)."; }
    else if(/^제한보호구역/.test(base)){
      if(deleg!=null){
        if(!ht){ v="높이 입력 필요 ("+(sea?"해발 ":"")+deleg+"m 위임)"; d="계획 높이를 입력하면 협의 필요 여부를 판정합니다."; }
        else if(sea){ v="해발 "+deleg+"m 기준 확인"; d="해발고도 기준 위임입니다. 지반 표고 + 건물 높이 ≤ "+deleg+"m 이면 고양시 자체 처리, 초과하면 관할부대 협의."; }
        else if(ht<=deleg){ st="ok"; v="위임고도 이하 — 군 협의 생략"; d="계획 높이 "+ht+"m ≤ 위임고도 "+deleg+"m → 관할부대 협의 없이 고양시가 자체 처리합니다(법 제14조, 영 제14조)."; }
        else { v="위임고도 초과 — 부대 협의"; d="계획 높이 "+ht+"m > 위임고도 "+deleg+"m → 관할부대 협의 필요(통상 30일, 사전상담 시 20일)."; }
        if(partial) d+="\n※ 같은 구역이 위임 없이도 표시되어 있어 필지 일부만 위임지역일 수 있습니다.";
      }else{
        v=grow?"부대 협의 (위임고도 확인)":v;
        d=(grow?"신축·증축·공작물 설치·용도변경은 관할부대 협의 대상입니다(법 제13조①).\n단, 토지이음 토지이용계획에 '(고도 N m 위임지역)'이 표기된 필지는 그 높이 이하면 군 협의 없이 고양시가 처리합니다. 고양시 위임고도는 지역별 8~85m입니다(덕은동 8m, 용두·현천동 15m, 오금동 20m 등).":"")+"\n개축·재축·대수선·가설건축물·건축신고·용도변경신고는 협의가 생략됩니다(영 제13조③). 협의 기간 통상 30일.";
        if(!grow&&!/폭발물/.test(base)){ st="info"; v="협의 생략 대상"; }
      }
    }
    out.push({g:"site",n:"군사시설 보호구역",st:st,v:v,calc:calc,d:d,src:[L("auto","토지이용규제정보"),lawSrc,L("auto","토지이음에서 위임고도 확인","https://www.eum.go.kr/web/ar/lu/luLandDet.jsp?pnu="+S.pnu+"&mode=search&isNoScr=script&selGbn=umd")]});
  });
  return out;
}

// ─────────────────────────────────────────────
// 개발제한구역 판정 — research/05 (법 2026.6.2. / 시행령 2026.9.18. 기준)
//   1) 취락지구 여부 → 2) 별표1 허용 시설 여부 → 3) 주택·근생 규모(별표2·영 제26조)
//   4) 신고/허가/위원회(영 제19조 등) → 5) 보전부담금
// ─────────────────────────────────────────────
var GBD=(typeof GY_DATA!=="undefined"&&GY_DATA.gb)||null;
var GB_NEIGH=/슈퍼마켓|소매점|휴게음식점|제과점|일반음식점|이용원|미용원|세탁소|의원|치과|한의원|탁구장|체육도장|기원|당구장|금융업소|사무소|부동산|정비|사진관|표구점|학원|장의사|동물병원|목공소|방앗간|독서실/;
function gbCheck(S,P,fx){
  var n0=fx.n0, n1=fx.n1, out=[], sa=+S.area||0, names=S.regNames||[], jm=(S.jimok||"").trim();
  var village=names.some(function(n){return /취락지구/.test(n);});
  var gbLaw=L("law","개발제한구역법 시행령 별표1·별표2",GBD?GBD.law.decreeUrl:LAW.gb);
  var isHouse=P.use==="단독주택", isNeigh=/근린생활/.test(P.use);
  var build=/신축|증축|개축|재축/.test(P.act);
  var exTa=0; if(S.bldAll) S.bldAll.forEach(function(b){ exTa+=parseFloat(b.totArea)||0; });
  var total=P.act==="증축"? P.ta+exTa : P.ta;
  if(!GBD){ out.push({g:"site",n:"개발제한구역",st:"fail",v:"원칙적 건축 금지",d:"시행령 별표1의 허용 시설만 가능합니다.",src:[gbLaw]}); return out; }

  // ① 주택·근린생활시설
  if((isHouse||isNeigh)&&(build||P.act==="대수선")){
    var probs=[], notes=[], st="ok";
    if(isHouse&&P.sub&&P.sub!=="단독주택"){ probs.push("GB 주택은 건축법상 '단독주택'만 가능 — "+P.sub+"(다가구·다중·공관) 신축 불가"); }
    if(isNeigh&&P.sub&&!GB_NEIGH.test(P.sub)){ probs.push("'"+P.sub+"'는 GB 근린생활시설 신축 허용 용도(슈퍼마켓·음식점·이용원·의원·학원 등 11종)에 없음"); }
    if(isNeigh&&/음식점|제과점/.test(P.sub||"")) notes.push("휴게·일반음식점·제과점은 5년 이상 거주자 또는 지정당시거주자만 가능");
    if(P.act==="신축"&&jm!=="대") probs.push("신축은 GB 지정 당시 지목이 '대'였거나 기존 주택이 있던 토지만 가능 (현재 지목: "+fx.jimokFull(jm)+")");
    else if(P.act==="신축") notes.push("GB 지정 당시에도 지목이 '대'였는지(또는 기존 주택 부지인지) 토지대장으로 확인 필요");
    if(isNeigh&&P.act==="증축") notes.push("근린생활시설 증축은 주택을 용도변경한 근생 또는 1999.6.24. 이후 신축된 근생만 가능");
    // 규모: 건폐율 60%안(3층·300%·연면적 상한) 또는 저건폐안(밖 20% / 취락 40%, 3층·100%, 면적 상한 없음)
    var bcr=sa?(P.ba/sa*100):0, far=sa?(P.fa/sa*100):0;
    var lowB=village?40:20, cap=village?300:(P.gbResident?300:232);
    var optLow = P.fl<=3 && bcr<=lowB && far<=100;
    var optHigh= P.fl<=3 && bcr<=60 && far<=300 && total<=cap;
    if(P.fl>3) probs.push("층수 "+P.fl+"층 > 3층 이하");
    else if(!optLow&&!optHigh){
      if(bcr>60) probs.push("건폐율 "+n1(bcr)+"% > 60%");
      else if(total>cap&&!(bcr<=lowB&&far<=100)) probs.push("연면적(기존 포함) "+n0(total)+"㎡ > "+cap+"㎡"+(village?" (취락지구)":P.gbResident?" (지정당시거주자)":" — 지정당시거주자는 300㎡(1회)")+". 건폐율 "+lowB+"% 이하로 낮추면 상한 없이 용적률 100%까지 가능");
      else probs.push("용적률 "+n1(far)+"% 초과 (60%안 300% / 저건폐안 100%)");
    }
    if(probs.length) st="fail"; else if(notes.length) st="warn";
    var proc= (P.act!=="신축"&&(total<=100||P.ta<=85)) ? "신고 (기존 포함 100㎡ 이하 또는 증축·개축·대수선 85㎡ 이하 — 영 제19조제1호)" : "개발제한구역 행위허가 + 건축허가 (본청 건축정책과)";
    out.push({g:"site",n:"개발제한구역 — "+(isHouse?"주택":"근린생활시설")+" "+P.act,st:st,v:st==="fail"?"기준 미충족":st==="warn"?"조건부 가능":"허용 범위",
      calc:(village?"취락지구 안":"취락지구 밖")+" 개발제한구역\n"+
        "· 건폐율 60% 이하안: 3층·용적률 300%·연면적 "+cap+"㎡ 이하 "+(optHigh?"✓":"✕")+"\n"+
        "· 건폐율 "+lowB+"% 이하안: 3층·용적률 100%·면적 상한 없음 "+(optLow?"✓":"✕")+"\n"+
        "계획: 건폐율 "+n1(bcr)+"% · 용적률 "+n1(far)+"% · "+P.fl+"층 · 연면적"+(P.act==="증축"?"(기존 포함) ":" ")+n0(total)+"㎡\n\n절차: "+proc,
      d:(probs.length?"✕ "+probs.join("\n✕ ")+"\n":"")+(notes.length?"! "+notes.join("\n! ")+"\n":"")+"\n지정당시거주자 여부는 입력란에서 선택하세요. 주택 내부 수리·지붕 개량 등 경미한 행위는 허가·신고 없이 가능(시행규칙 별표4).",
      src:[L("auto","개발제한구역: 토지이용규제"),gbLaw,L("law","시행령 제19조·제26조",GBD.law.decreeUrl)]});
  }else if(P.act==="용도변경"){
    out.push({g:"site",n:"개발제한구역 — 용도변경",st:"warn",v:"허용 범위 확인",
      calc:"GB에서는 시행령 제18조에 정한 범위의 용도변경만 가능합니다.\n"+(village?"취락지구: 주택·공장 등을 제1·2종 근린생활시설(단란주점·안마시술소 제외), 세차장, 병원 등으로 변경 가능":"주택 ↔ 근린생활시설 등 시행령 제18조 범위"),
      d:"변경 후 용도가 별표1 허용 시설이고 규모 기준(별표2)을 충족해야 합니다.",src:[gbLaw,L("law","시행령 제18조",GBD.law.decreeUrl)]});
  }else if(build){
    // ② 그 밖의 시설: 별표1에서 같은 용도의 허용 항목 찾기
    var hits=GBD.allowed.filter(function(a){ return a.use===P.use && (a.acts||[]).some(function(x){return x===P.act||x==="설치";}); });
    if(hits.length){
      out.push({g:"site",n:"개발제한구역 — 허용 시설 해당 여부",st:"warn",v:hits.length+"개 유형만 가능",
        calc:hits.slice(0,5).map(function(a){ return "· "+a.n+" — 주체: "+a.who+(a.max?" · "+n0(a.max)+"㎡ 이하":"")+(a.fl?" · "+a.fl+"층 이하":""); }).join("\n"),
        d:"별표1에 정한 위 유형·주체·규모에 해당할 때만 허가 가능합니다. 일반적인 "+P.use+" 건축은 불가합니다.\n"+hits.slice(0,3).map(function(a){return "["+a.n+"] "+String(a.c||"").slice(0,160);}).join("\n"),
        src:[gbLaw].concat(hits[0].art?[L("law",hits[0].art,GBD.law.decreeUrl)]:[])});
    }else{
      out.push({g:"site",n:"개발제한구역 — 허용 시설 아님",st:"fail",v:"건축 불가",
        calc:"'"+(P.sub||P.use)+"'은(는) 개발제한구역법 시행령 별표1의 허용 시설이 아닙니다.",
        d:"GB에서는 별표1에 열거된 시설만 건축할 수 있습니다(법 제12조①). 예외: 대지가 GB 경계에 걸쳐 1/2 미만 편입된 경우 등(영 제13조②).",
        src:[L("auto","개발제한구역: 토지이용규제"),gbLaw]});
    }
  }
  if(total>=1500||sa>=5000) out.push({g:"proc",n:"개발제한구역 — 도시계획위원회",st:"warn",v:"심의 대상",calc:"연면적 1,500㎡ 이상 또는 형질변경 5,000㎡ 이상 → 고양시 도시계획위원회(도시건축공동위원회) 심의·주민의견청취"+(total>=3000?"\n연면적 3,000㎡ 이상 → 개발제한구역 관리계획에 반영되어야 함":""),src:[gbLaw]});
  out.push({g:"duty",n:"개발제한구역 보전부담금",st:"info",v:(isHouse||isNeigh)?"주민 주택·근생은 0원":"부과 대상 (농림업 시설 0원)",calc:"(GB 밖 같은 지목 평균 공시지가 − 해당 토지 공시지가) × (형질변경 면적 × 부과율 + 바닥면적 × 2 × 부과율)\n주민의 주택·근린생활시설·농림업시설은 부과율 0",src:[L("law","개발제한구역법 제21조",LAW.gb+"/제21조")]});
  return out;
}

// 관할 소방서 (research/07, 2026-10-21 소방서 누리집)
var FIRE_ST={
  "덕양구":"고양소방서 화재예방과 소방민원팀 ☎ 031-931-0321",
  "일산동구":"일산소방서 화재예방과 소방민원팀 ☎ 031-930-0321",
  "일산서구":"일산소방서 화재예방과 소방민원팀 ☎ 031-930-0321"
};
// 장애인등편의법 시행령 별표1 대상 기준 (세부용도 → [기준면적㎡ 또는 0=면적무관 또는 null=대상아님, 설명])
var ACC=[
  [/소매점/,50,"1종근생 소매점: 바닥면적 50㎡ 이상"],[/휴게음식점·제과점 300㎡ 미만/,50,"휴게음식점·제과점: 50㎡ 이상"],[/휴게음식점·제과점 300㎡ 이상/,0,"휴게음식점·제과점 300㎡ 이상: 전부"],
  [/이용원|미용원/,50,"이용원·미용원: 50㎡ 이상"],[/의원/,0,"의원·치과의원·한의원: 면적 무관 (100㎡ 미만은 증축 등만)"],[/지역아동센터|공공시설/,0,"지역아동센터·공공시설: 면적 무관"],
  [/일반음식점/,50,"일반음식점: 50㎡ 이상"],[/학원·교습소 500/,0,"학원·교습소(2종근생): 전부"],[/독서실|동물병원|안마시술소/,0,"면적 무관"],
  [/^공연장$|관람장/,0,"공연장·관람장: 면적 무관"],[/집회장|전시장/,500,"집회장·전시장: 500㎡ 이상"],[/동·식물원/,300,"동·식물원: 300㎡ 이상"],[/^종교시설$/,500,"종교집회장: 500㎡ 이상"],
  [/도매시장|소매시장|상점/,1000,"판매시설: 1,000㎡ 이상"],[/병원/,0,"병원: 면적 무관"],[/^학교$/,0,"학교: 면적 무관"],[/^학원$/,500,"학원 등: 500㎡ 이상"],[/도서관/,1000,"도서관: 1,000㎡ 이상"],
  [/아동관련|노인복지/,0,"노유자시설: 면적 무관"],[/운동시설/,500,"운동시설: 500㎡ 이상"],[/공공업무/,0,"공공청사: 면적 무관"],[/일반업무|오피스텔/,500,"일반업무시설·오피스텔: 500㎡ 이상"],
  [/관광숙박/,0,"관광숙박시설: 전부"],[/일반숙박|생활숙박/,"room30","일반·생활숙박: 객실 30실 이상"],[/^주차장$/,0,"주차장: 면적 무관"],[/방송통신/,1000,"방송통신시설: 1,000㎡ 이상"],[/장례/,500,"장례식장: 500㎡ 이상"],
  [/아파트/,0,"아파트: 전부"],[/연립주택|다세대주택/,"hh10","연립·다세대: 10세대 이상"],[/기숙사/,"p30","기숙사: 30인 이상"]
];
function accTarget(P){
  var key=P.sub||P.use;
  for(var i=0;i<ACC.length;i++){ var r=ACC[i]; if(!r[0].test(key)) continue;
    var yes = r[1]===0 ? true : r[1]==="hh10" ? P.hh>=10 : r[1]==="room30" ? (P.hh?P.hh>=30:null) : r[1]==="p30" ? null : P.ta>=r[1];
    return {yes:yes!==false, text:r[2]+(yes===null?" — 세대·객실·인원 수 입력 시 판정":"")+"\n계획: "+key+(P.ta?" · "+n0x(P.ta)+"㎡":"")+(P.hh?" · "+P.hh+"세대(실)":"")};
  }
  return /단독주택|공장|창고|축사/.test(key)? null : {yes:false,text:"'"+key+"'은(는) 별표1 대상시설 목록에 없거나 규모 기준 미만으로 보입니다 (세부 확인 권장)"};
}

function parkingCalc(P){
  var r=parking.rules[P.use]||parking.rules["기타"];
  if(P.use==="공동주택"){
    var t=parking.apt||"";
    if(P.hh){ var per=P.ua&&P.ua>85?1:(parking.aptMin||1); var cnt=Math.ceil(P.hh*per); return {cnt:cnt,calc:"세대수 "+P.hh+" × 세대당 "+per+"대 = "+cnt+"대 (세대당 최소 기준)\n"+t,detail:"공동주택은 주택건설기준 등에 관한 규정 제27조(전용면적 합계 기준)와 세대당 기준 중 큰 값이 적용됩니다.",art:r&&r.art}; }
    return {cnt:"세대수 입력",calc:t||"세대수를 입력하면 산정합니다.",detail:"주택건설기준 등에 관한 규정 제27조",art:r&&r.art};
  }
  if(!r||!r.rate) return null;
  var cnt2=Math.max(1,Math.ceil(P.ta/r.rate));
  return {cnt:cnt2,calc:"시설면적 "+n0x(P.ta)+"㎡ ÷ "+r.rate+"㎡ = "+cnt2+"대\n기준: "+r.text,detail:(parking.note||"")+"\n※ 시설면적은 주차장 면적을 제외한 바닥면적 합계 기준입니다.",art:r.art};
}
function n0x(v){ return Math.round(v).toLocaleString("ko-KR"); }

function authority(S,P){
  var a=GYX.authority? GYX.authority(S,P) : null;
  return a||{text:"허가권자: 고양특례시장 (접수·처리: "+(S.gu||"관할")+"청 건축과)"};
}
function authorityHtml(S){
  var gu=S.gu||"관할 구", gb=S.flags&&S.flags.gb;
  var h='<div class="rows">';
  if(gb) h+='<div class="row"><div class="rn"><b>고양특례시 건축정책과 (본청) <span class="tag fail">개발제한구역</span></b><small>개발제한구역 내 건축은 규모와 관계없이 본청 처리 (사무위임 조례 별표1) · ☎ 031-8075-3130</small></div></div>';
  h+='<div class="row"><div class="rn"><b>'+gu+'청 건축과'+(GU_TEL[gu]?' <span style="font-weight:500;color:var(--muted)">☎ '+GU_TEL[gu]+'</span>':'')+'</b><small>'+(gb?'건축신고·가설건축물 등 구 위임 사무 ':'6층 이하·연면적 2천㎡ 이하 건축허가·신고, 용도변경, 사용승인 ')+'('+gu+' 소재 필지)</small></div></div>';
  (GYX.authorityRows||[]).forEach(function(r){ if(gb&&/본청/.test(r[0])) return; h+='<div class="row"><div class="rn"><b>'+r[0]+'</b><small>'+r[1]+'</small></div></div>'; });
  h+='<div class="row"><div class="rn"><b>세움터 전자접수</b><small>설계자(건축사)가 세움터를 통해 허가 신청</small></div><a href="https://www.eais.go.kr/" target="_blank" rel="noopener">세움터 ›</a></div>';
  return h+'</div>';
}
function consults(S){
  var F=S.flags||{}, jm=S.jimok||"", D=departments, cs=[];
  var d=function(k,def){ return D[k]||def; };
  cs.push({d:d("도시계획","도시계획과"),r:"용도지역·지구단위계획 저촉 검토",q:"필수",law:"국토의 계획 및 이용에 관한 법률",art:"제54조"});
  if(jm!=="대") cs.push({d:d("개발행위","도시개발과"),r:"개발행위허가(토지 형질변경) 협의",q:"필수",law:"국토의 계획 및 이용에 관한 법률",art:"제56조"});
  if(/^(전|답|과)$/.test(jm)) cs.push({d:d("농지","농업정책과"),r:"농지전용허가 (지목: "+jm+")",q:"필수",law:"농지법",art:"제34조"});
  if(/^임$/.test(jm)) cs.push({d:d("산지","산림 담당 부서"),r:"산지전용허가 (지목: 임야)",q:"필수",law:"산지관리법",art:"제14조"});
  if(F.gb) cs.push({d:d("개발제한","개발제한구역 담당 부서"),r:"개발제한구역 행위허가",q:"필수",law:"개발제한구역의 지정 및 관리에 관한 특별조치법",art:"제12조"});
  if(F.military&&F.military.length) cs.push({d:"관할 군부대",r:"군사기지·군사시설 보호구역 협의",q:"필수",law:"군사기지 및 군사시설 보호법",art:"제13조"});
  if(F.culture&&F.culture.length) cs.push({d:d("문화유산","문화유산 담당 부서")+" / 국가유산청",r:"문화유산 현상변경·영향 검토",q:"필수",law:"문화유산의 보존 및 활용에 관한 법률",art:"제35조"});
  if(F.facility&&F.facility.length) cs.push({d:d("도시계획","도시계획과"),r:"도시·군계획시설 저촉 검토",q:"필수",law:"국토의 계획 및 이용에 관한 법률",art:"제64조"});
  if(F.river&&F.river.length) cs.push({d:d("하천","하천 담당 부서"),r:"하천구역 점용허가",q:"필수",law:"하천법",art:"제33조"});
  cs.push({d:FIRE_ST[S.gu]||d("소방","관할 소방서"),r:"건축허가 동의·소방시설 협의",q:"해당 시",law:"소방시설 설치 및 관리에 관한 법률",art:"제6조"});
  cs.push({d:d("도로","도로 담당 부서"),r:"도로점용·진출입로·접도 확인",q:"해당 시",law:"도로법",art:"제61조"});
  cs.push({d:d("하수","하수도 담당 부서"),r:"배수설비·개인하수처리시설·원인자부담금",q:"해당 시",law:"하수도법",art:"제27조"});
  cs.push({d:d("교통","교통 담당 부서"),r:"교통영향평가·부설주차장",q:"해당 시",law:"도시교통정비 촉진법",art:"제15조"});
  return cs;
}

var flow=[
  ["사전검토 · 사전결정(선택)","대지 적합성·규제 확인. 필요 시 건축법 제10조 사전결정 신청"],
  ["설계 · 심의","건축위원회·경관·교통영향평가 등 심의 대상 시 선행"],
  ["건축허가·신고 신청","건축사가 세움터로 전자 접수 (의제 처리 서류 동시 제출)"],
  ["관계부서·기관 협의","도시계획·농지·산지·소방·도로·하수 등 의제 협의"],
  ["허가서 교부 · 착공신고","감리자 지정, 안전관리예치금 예치(해당 시)"],
  ["사용승인","현장조사·검사 후 건축물대장 생성"]
];
var deemed=[
  ["개발행위허가","국토의 계획 및 이용에 관한 법률","제56조"],["농지전용허가·신고","농지법","제34조"],["산지전용허가·신고","산지관리법","제14조"],
  ["도로점용허가","도로법","제61조"],["사도개설허가","사도법","제4조"],["하천점용허가","하천법","제33조"],
  ["배수설비 설치신고","하수도법","제27조"],["개인하수처리시설 설치신고","하수도법","제34조"],["공작물 설치·가설건축물","건축법","제20조"]
];
function sources(){ return [src.urban,src.building,src.parking].concat(src.extra||[]); }

var GYX={}; // 확장 훅 (교통영향평가·부담금·허가권자 등)

// ═════════════════════════════════════════════
// 고양시 도시계획 조례 — research/01_도시계획조례 → gy_data.js (2026.9.22. 제3023호)
// ═════════════════════════════════════════════
var U=(typeof GY_DATA!=="undefined"&&GY_DATA.urban)||null;
if(U){
  src.urban={name:U.ordinance.name,date:U.ordinance.date,url:U.ordinance.url};
  Object.keys(U.zones).forEach(function(k){ var z=U.zones[k]; zones[k]={b:z.b,f:z.f,h:z.h,bArt:z.bArt,fArt:z.fArt,hNote:z.h?"4층 이하"+(k==="제1종일반주거"?" (단지형 연립·다세대 5층)":""):"",hArt:z.useArt,fNote:z.fNote,useArt:z.useArt}; });
  Object.keys(U.useZone).forEach(function(k){ useZone[k]={}; var uz=U.useZone[k]; Object.keys(uz).forEach(function(u){ useZone[k][u]={s:uz[u].s,c:uz[u].c,art:(U.zones[k]&&U.zones[k].useArt)||"별표"}; }); });
}
// 개발행위허가 규모 — 고양시 도시계획 조례 제18조 (관리·농림은 시행령보다 강화), 도시지역은 시행령 제55조
DEV_SIZE["보전관리"]=5000; DEV_SIZE["생산관리"]=10000; DEV_SIZE["계획관리"]=30000; DEV_SIZE["농림"]=10000;
ord.devArt="제18조·제19조";
ord.devStd=U?("개발행위허가 기준 (고양시 도시계획 조례 제19조·별표29)\n· 경사도: 평균 15도 미만 (15도 이상은 도시계획위원회 심의)\n· 입목축적: ha당 시 평균 입목축적 이하, 50년 이상 활엽수림 75% 이하\n· 표고: 산지 포함 시 법정동별 기준 이하"):"";
var ALT=U&&U.devPermit&&U.devPermit.altitudeByDong||{};
function altitudeNote(dong){ return ALT[dong]? "\n· "+dong+" 표고 기준: "+ALT[dong]+"m 이하 (별표29)" : ""; }

// 용도지구·구역에 따른 밀도 조정 (조례 제57조·제59조·제29조의3)
function effective(zone,names){
  var base=zones[zone]; if(!base) return null;
  var z={b:base.b,f:base.f,h:base.h,bArt:base.bArt,fArt:base.fArt,hNote:base.hNote,hArt:base.hArt,fNote:base.fNote,adj:[]};
  var has=function(re){ return names.some(function(n){return re.test(n);}); };
  if(has(/자연취락지구/)){ if(z.b<50){ z.b=50; z.bArt="제57조제1호"; z.adj.push("자연취락지구 건폐율 50%"); } z.h=4; z.hNote="자연취락지구 4층 이하"; }
  if(has(/성장관리계획구역|성장관리방안/)){
    if(zone==="계획관리"){ z.b=50; z.f=125; z.bArt=z.fArt="제29조의3"; z.adj.push("성장관리계획구역 계획관리 건폐율 50%·용적률 125%"); }
    else if(/생산녹지|자연녹지|생산관리|농림/.test(zone)){ z.b=30; z.bArt="제29조의3"; z.adj.push("성장관리계획구역 건폐율 30%"); }
  }
  if(has(/방화지구/)&&/준주거|일반상업|근린상업|전용공업|일반공업|준공업/.test(zone)){ z.b=Math.max(z.b,80); z.bArt="제59조제1항"; z.adj.push("방화지구 건폐율 80%"); }
  if(has(/경관지구/)){ if(z.b>40){ z.b=40; z.bArt="제38조"; z.adj.push("경관지구 건폐율 40%"); } }
  if(has(/개발진흥지구/)){ if(zone==="자연녹지"){ z.b=30; } else if(!/주거|상업|공업|녹지/.test(zone)){ z.b=40; z.f=100; } z.adj.push("개발진흥지구 — 지구단위계획(개발계획) 우선"); }
  return z;
}
function districtChecks(S,P){
  var names=((S.reg||{}).all||[]).map(function(x){return x.name||"";}), out=[];
  var D=U&&U.districts||[];
  function rule(nm){ for(var i=0;i<D.length;i++) if(D[i].name===nm) return D[i]; return null; }
  [["자연경관지구",/자연경관지구/],["특화경관지구",/특화경관지구/],["시가지경관지구",/시가지경관지구/],["방재지구",/방재지구/],["역사문화환경보호지구",/역사문화환경보호지구/],["중요시설물보호지구",/중요시설물보호지구/],["특정용도제한지구",/특정용도제한지구/],["자연취락지구",/자연취락지구/],["개발진흥지구",/개발진흥지구/],["성장관리계획구역",/성장관리계획구역/]].forEach(function(d){
    if(!names.some(function(n){return d[1].test(n);})) return;
    var r=rule(d[0]); if(!r) return;
    var st=/경관|방재|보호|제한/.test(d[0])?"warn":"info";
    var v="지구 기준 적용";
    if(/경관지구/.test(d[0])&&(P.fl>5||P.ht>20)) { st="fail"; v="층수·높이 초과 가능"; }
    out.push({g:"site",n:d[0],st:st,v:v,calc:r.rule,d:"고양시 도시계획 조례 "+r.art,src:[L("auto","토지이용규제정보"),ordSrc("urban",src.urban.name+" "+r.art)]});
  });
  return out;
}

// ═════════════════════════════════════════════
// 고양시 건축 조례 등 — research/02_건축조례.md (2026-10-21 조사)
//   건축 조례 2025.1.10. 제2885호 / 경관 조례 2025.11.14. / 사무위임 조례 2026.3.16. 시행
// ═════════════════════════════════════════════
src.building={name:"고양시 건축 조례",date:"2025.1.10. 개정 (제2885호)",url:"https://www.law.go.kr/LSW/ordinInfoP.do?ordinSeq=2011341"};
src.extra.push(
  {name:"고양시 경관 조례",date:"2025.11.14. 개정 (제2968호)",url:"https://www.law.go.kr/LSW/ordinInfoP.do?ordinSeq=2086133"},
  {name:"고양시 사무위임 조례",date:"2026.3.16. 시행 (제2987호)",url:"https://www.law.go.kr/LSW/ordinInfoP.do?ordinSeq=2109925"},
  {name:"경기도 건축물 미술작품 설치 및 관리에 관한 조례",date:"2023.7.18. 개정",url:"https://www.law.go.kr/LSW/ordinInfoP.do?ordinSeq=1838999"}
);
var LANDSCAPE_ORD={name:"고양시 경관 조례",url:"https://www.law.go.kr/LSW/ordinInfoP.do?ordinSeq=2086133"};

// 다중이용·준다중이용 건축물 (건축법 시행령 제2조 제17호·제17호의2)
function multiUse(P){ return (/문화및집회|판매|숙박|의료/.test(P.use)&&P.ta>=5000) || P.fl>=16; }
function semiMultiUse(P){ return /문화및집회|판매|숙박|의료|교육연구|운동/.test(P.use)&&P.ta>=1000&&!multiUse(P); }
function aptPlanApproval(P){ return P.use==="공동주택"&&P.hh>=30; } // 주택법 제15조 사업계획승인(30세대 이상, 일부 50세대)

// 건축위원회 심의 — 건축 조례 제8조
ord.committeeArt="제8조";
ord.committee=function(P,S){
  var r=[];
  if(P.ta>=100000) r.push("연면적 합계 10만㎡ 이상 ("+n0x(P.ta)+"㎡)");
  if(P.sale&&P.ta>=3000) r.push("분양 목적 건축물 — 분양 바닥면적 합계 3천㎡ 이상");
  if(P.sale&&P.hh>=30) r.push("분양 목적 — 공동주택·오피스텔 세대(실) 합계 30 이상 ("+P.hh+")");
  if(aptPlanApproval(P)) r.push("주택법 제15조 사업계획승인 대상 공동주택 ("+P.hh+"세대)");
  if(P.uf>3) r.push("지하 3층 초과 굴착 (지하 "+P.uf+"층) — 구조안전 심의");
  if(multiUse(P)) r.push("다중이용 건축물 — 시장이 지정·공고한 지역인 경우 심의");
  return r;
};

// 건축허가 수수료 — 건축 조례 제23조 별표1 (구간: 이상~미만)
ord.feeArt="제23조 별표1";
var FEE=[[200,4000,9400],[1000,6000,20000],[5000,54000,54000],[10000,100000,100000],[30000,200000,200000],[100000,410000,410000],[300000,810000,810000],[Infinity,1620000,1620000]];
ord.fee=function(ta,isHouse){ for(var i=0;i<FEE.length;i++) if(ta<FEE[i][0]) return isHouse?FEE[i][1]:FEE[i][2]; return null; };

// 안전관리예치금 — 건축 조례 제20조 (2025.1.10. 개정)
ord.safetyDeposit={minArea:1000,art:"제20조",
  rate:"건축공사비(표준건축비×연면적)의 1만㎡ 미만 1.0% · 1만~3만㎡ 0.5% · 3만㎡ 이상 0.3%\n※ 국가·지자체 공용건축물 제외 / 증축은 증축 부분 1천㎡ 이상만"};

// 대지 안의 조경 — 건축법 제42조·시행령 제27조, 건축 조례 제33조
ord.landscape=function(sa,ta,zone,use){
  var dupHint="";
  if(sa<200) return {req:false,text:"대지면적 200㎡ 미만 → 조경 의무 없음 (건축법 제42조①)"};
  if(/녹지/.test(zone)) return {req:false,text:"녹지지역 건축물 → 조경 설치 제외 (시행령 제27조①1호)"};
  if(/관리|농림|자연환경보전/.test(zone)) return {req:false,text:"관리·농림·자연환경보전지역(지구단위계획구역 제외) → 조경 설치 제외 (시행령 제27조①)"};
  if(use==="공장"&&(sa<5000||ta<1500)) return {req:false,text:"대지 5천㎡ 미만 또는 연면적 1,500㎡ 미만 공장 → 조경 설치 제외 (시행령 제27조①2호)"};
  if(use==="창고시설"&&ta<1500&&!/주거|상업/.test(zone)) return {req:false,text:"연면적 1,500㎡ 미만 물류시설(주거·상업지역 외) → 조경 설치 제외"};
  var pct=ta>=2000?15:ta>=1000?10:5;
  return {req:true,pct:pct,art:"제33조",
    text:"연면적 "+n0x(ta)+"㎡ → "+(ta>=2000?"2천㎡ 이상: 15%":ta>=1000?"1천~2천㎡ 미만: 10%":"1천㎡ 미만: 5%")+" 이상",
    detail:"식재 기준은 국토교통부 「조경기준」 고시에 따릅니다(조례 제34조).\n식재 부적합 대지는 파고라·조각물·조경석·연못 등으로 대체 가능(제33조⑤).\n제외: 전통시장, 주차전용건축물, 관광시설, 골프장 등(제33조)"+dupHint};
};

// 공개공지 — 건축법 제43조·시행령 제27조의2, 건축 조례 제35조
ord.publicSpace=function(ta,zone,use){
  var zoneOk=/일반주거|준주거|상업|준공업/.test(zone);
  var useOk=/문화및집회|판매|업무|숙박|의료|운동/.test(use);
  if(!zoneOk||!useOk||ta<5000) return {req:false};
  var pct=ta>=30000?10:ta>=10000?7:5;
  return {req:true,pct:pct,art:"제35조",
    text:"대상 용도 바닥면적 합계 "+n0x(ta)+"㎡ ≥ 5,000㎡ → "+(ta>=30000?"3만㎡ 이상: 10%":ta>=10000?"1만~3만㎡: 7%":"5천~1만㎡: 5%")+" 이상",
    detail:"1개소 45㎡ 이상·최소 폭 5m, 최대 2개소. 필로티 구조는 1/2 이내 인정(높이 6m 이상).\n완화: 공개공지 설치 시 용적률·높이 1.2배 이하 완화 가능 (조례 제35조⑤ — 이 경우 건축위원회 심의).\n지구단위계획으로 정한 경우 그에 따름."};
};

// 대지 안의 공지 — 건축법 제58조, 건축 조례 별표4
ord.setback=function(use,ta,zone){
  var com=/상업/.test(zone), ind=/전용공업|일반공업/.test(zone), semi=/준공업/.test(zone);
  if(use==="공장"&&ta>=500&&!ind) return semi?{line:"1.5m (부속 1m)",adj:"1m",cond:"공장 500㎡ 이상 · 준공업지역",art:"별표4"}:{line:"3m (부속 1.5m)",adj:"1.5m",cond:"공장 500㎡ 이상",art:"별표4"};
  if(use==="창고시설"&&ta>=500&&!ind) return {line:semi?"1.5m (부속 1m)":"3m (부속 1.5m)",adj:"0.5m",cond:"창고 500㎡ 이상",art:"별표4"};
  if(/판매|숙박|문화및집회/.test(use)&&ta>=1000) return {line:"3m (부속 2m)",adj:com?"0.5m (상업지역)":"1.5m",cond:use+" 바닥면적 1,000㎡ 이상",art:"별표4"};
  if(multiUse({use:use,ta:ta,fl:0})) return {line:"3m (부속 2m)",adj:com?"0.5m (상업지역)":"1.5m",cond:"다중이용 건축물",art:"별표4"};
  if(use==="공동주택") return {line:"아파트 3m · 연립 2m · 다세대 1.5m",adj:com?"상업지역: 0.5m":"아파트 3m · 연립 2m · 다세대 1.5m",cond:"공동주택 유형별",art:"별표4"};
  return {line:"1m (부속 0.5m)",adj:"0.5m"+(/전용주거/.test(zone)?" (전용주거지역 1m)":""),cond:"그 밖의 건축물",art:"별표4"};
};

// 대지분할 제한 — 건축 조례 제38조
ord.minSite={"주거":60,"상업":150,"공업":150,"녹지":200,"기타":60,art:"제38조"};
// 일조 — 건축 조례 제41조
ord.sunlight="고양시 건축 조례 제41조: 2층 이하·높이 8m 이하로서 법 제61조③ 해당 시 적용 제외. 다세대주택은 채광창 벽면에서 인접대지경계선까지 1.5m 이상이면 일부 완화.\n공동주택 동간거리: 높이의 1배 이상(도시형생활주택 0.5배).";
ord.green="고양시 건축 조례 제3조③: 녹색건축 인증 등 기준 충족 시 용적률·높이 115/100 이하 완화 가능.";

// 경관 심의 — 고양시 경관 조례 제24조의2 별표
ord.landscapeReviewSrc=L("ord","고양시 경관 조례 제24조의2",LANDSCAPE_ORD.url);
ord.landscapeReview=function(P,S){
  var r=[], F=S.flags||{};
  if(P.act==="대수선"||P.act==="용도변경") return r;
  if(P.ta>0&&P.ta<=100) return r;
  if(F.landscape&&F.landscape.length) r.push("경관지구("+F.landscape.join(", ")+") — 정발산·장항습지 일대: 건축허가 대상 전부 / 공릉천·창릉천 일대: 3층 또는 11m 이상");
  if(multiUse(P)) r.push("다중이용 건축물");
  if(semiMultiUse(P)&&P.ta>2000) r.push("준다중이용 건축물 (연면적 2천㎡ 초과)");
  if(aptPlanApproval(P)) r.push("주택법 제15조 사업계획승인 대상 공동주택");
  if(isUrban(S.zone)&&(P.fl>=7||P.ta>2000)) r.push("폭 25m 이상 도로 경계 50m 이내인 경우 심의 대상 (7층 이상 또는 2천㎡ 초과) — 접도 현황 확인");
  return r;
};

// 건축물 미술작품 — 문화예술진흥법 시행령 제12조, 경기도 조례 제2조
ord.artwork={minArea:10000,src:L("ord","경기도 건축물 미술작품 조례 제2조","https://www.law.go.kr/LSW/ordinInfoP.do?ordinSeq=1838999"),
  uses:/공동주택|근린생활|문화및집회|판매|의료|업무|숙박/,
  rate:"공동주택: 건축비용의 1/1,000 · 그 밖의 건축물: 5/1,000",
  detail:"주차장·기계실·전기실 등 면적 제외 후 연면적 1만㎡ 이상(증축은 증축부분).\n착공신고 후 180일 이내 경기도에 심의 신청 또는 문화예술진흥기금 출연(고양시 자체 조례 없음 → 경기도 조례 적용)."};

// ═════════════════════════════════════════════
// 고양시 주차장 조례·부담금·교통영향평가 — research/03 (2026-10-21 조사)
// ═════════════════════════════════════════════
src.parking={name:"고양시 주차장 설치 및 관리 조례",date:"2026.7.10. 개정 (제3013호), 별표7 2025.7.11.",url:"https://www.law.go.kr/LSW/ordinInfoP.do?ordinSeq=2148065"};
// 별표7 부설주차장 설치기준 (시설면적 ㎡당 1대) — 주차장법 시행령 별표1보다 강화
parking.rules={
  "제1종근린생활시설":{rate:134,text:"제1종 근린생활시설 134㎡당 1대",art:"별표7"},
  "제2종근린생활시설":{rate:134,text:"제2종 근린생활시설 134㎡당 1대",art:"별표7"},
  "숙박시설":{rate:134,text:"숙박시설 134㎡당 1대 (생활숙박시설은 호실당 1대 이상)",art:"별표7"},
  "문화및집회시설":{rate:75,text:"문화 및 집회시설(관람장 제외) 75㎡당 1대",art:"별표7"},
  "판매시설":{rate:100,text:"판매시설 100㎡당 1대",art:"별표7"},
  "업무시설":{rate:100,text:"업무시설(오피스텔 제외) 100㎡당 1대",art:"별표7"},
  "의료시설":{rate:100,text:"의료시설(정신·요양·격리병원 제외) 100㎡당 1대",art:"별표7"},
  "운동시설":{rate:100,text:"운동시설(골프장·골프연습장·옥외수영장 제외) 100㎡당 1대",art:"별표7"},
  "공장":{rate:250,text:"공장 시설면적 1만㎡ 미만 250㎡당 1대 / 1만㎡ 이상 350㎡당 1대",art:"별표7"},
  "창고시설":{rate:300,text:"창고시설 300㎡당 1대",art:"별표7"},
  "교육연구시설":{rate:200,text:"그 밖의 건축물 200㎡당 1대 (교육연구시설 별도 항목 없음)",art:"별표7"},
  "기타":{rate:200,text:"그 밖의 건축물 200㎡당 1대",art:"별표7"}
};
parking.note="장애인 전용구획: 부설주차장의 4% 이상(10대 미만 제외, 조례 제31조)\n인근 설치: 150대 이하 직선 200m, 151~300대 직선 300m 이내(제23조)\n기계식: 상업지역·연면적 5천㎡ 이상 건축물만, 50대 초과분의 20% 이하(제22조③·별표11)";
function roundPk(x){ return Math.floor(x+0.5); } // 소수점 이하 0.5 이상은 1대
parkingCalc=function(P){
  var r=parking.rules[P.use]||parking.rules["기타"], cnt, calc;
  var su=P.sub&&subByKey[P.sub];
  // 별표7 비고1 다목 — 원본 HWP 확인(2026-10-23): 동물 및 식물관련시설(도축장·도계장 제외)은 설치하지 않을 수 있음
  if(su&&su.p==="동물및식물관련시설")
    return {cnt:"설치 면제 가능",calc:"고양시 주차장 조례 별표7 비고1 다목: 동물 및 식물관련시설(도축장·도계장은 제외)은 부설주차장을 설치하지 아니할 수 있습니다.\n도축장·도계장이면 그 밖의 건축물 200㎡당 1대.",detail:parking.note,art:"별표7 비고1"};
  if(su&&/다가구주택|오피스텔|생활숙박/.test(su.k)){
    var base=su.pr?roundPk(P.ta/su.pr):0;
    if(!P.hh) return {cnt:"호실 수 입력",calc:su.pn,detail:"세대(호실) 수를 입력하면 산정합니다.",art:"별표7"};
    cnt=Math.max(base,P.hh);
    return {cnt:cnt,calc:(base?"면적 기준 "+base+"대, ":"")+"세대(호실)당 1대 기준 "+P.hh+"대 → "+cnt+"대\n"+su.pn,detail:parking.note,art:"별표7"};
  }
  if(P.use==="단독주택"){
    var a=P.ta; cnt=a<=50?0:a<=100?1:1+roundPk((a-100)/87);
    return {cnt:cnt,calc:"단독주택(다가구 제외): 50㎡ 초과 100㎡ 이하 1대, 100㎡ 초과 시 1 + (시설면적−100)/87\n= "+cnt+"대",detail:"다가구주택은 공동주택 기준(세대당 1대 이상)을 적용합니다.",art:"별표7"};
  }
  if(P.use==="공동주택"&&P.sub!=="기숙사"){
    if(!P.hh) return {cnt:"세대수 입력",calc:"주택건설기준 등에 관한 규정 제27조①(수도권 시: 전용 85㎡ 이하 85㎡당 1대, 85㎡ 초과 70㎡당 1대) 산정대수와 세대당 1대 중 큰 값",detail:"세대수와 세대당 전용면적을 입력하면 산정합니다.",art:"별표7"};
    var ua=P.ua||84, ex=P.hh*ua, byArea=ua<=85? ex/85 : ex/70;
    cnt=Math.max(Math.ceil(byArea),P.hh);
    return {cnt:cnt,calc:"전용면적 합계 "+n0x(ex)+"㎡ ÷ "+(ua<=85?"85":"70")+"㎡ = "+n1x(byArea)+"대\n세대당 1대 기준 = "+P.hh+"대\n→ 큰 값 "+cnt+"대",detail:"고양시 조례 별표7: 주택건설기준 규정 제27조① 산정대수로 하되 세대당 1대 미만이면 세대당 1대 이상.\n도시형생활주택: 세대당 1대(전용 30~60㎡ 0.9대, 30㎡ 미만 0.6대).",art:"별표7"};
  }
  var rate=(su&&su.pr)||r.rate;
  if(P.use==="공장"&&P.ta>=10000&&rate===250) rate=350;
  if(su&&su.pn) r={text:su.pn,art:"별표7"};
  else if(su&&su.pr) r={text:su.k+" "+su.pr+"㎡당 1대",art:"별표7"};
  cnt=Math.max(1,roundPk(P.ta/rate));
  var dis=cnt>=10?Math.ceil(cnt*0.04):0;
  return {cnt:cnt,calc:"시설면적 "+n0x(P.ta)+"㎡ ÷ "+rate+"㎡ = "+n1x(P.ta/rate)+" → "+cnt+"대"+(dis?"\n장애인 전용 "+dis+"대 포함 (4%)":"")+"\n기준: "+r.text,detail:parking.note+"\n※ 시설면적은 주차장 면적을 제외한 바닥면적 합계 기준입니다.",art:r.art};
};
function n1x(v){ return (Math.round(v*10)/10).toLocaleString("ko-KR"); }

// 교통영향평가 대상 — 도시교통정비 촉진법 시행령 별표1 (도시교통정비지역 기준)
var TIA={"공동주택":60000,"제1종근린생활시설":12000,"제2종근린생활시설":15000,"문화및집회시설":15000,"판매시설":11000,"업무시설":25000,"숙박시설":40000,"공장":75000,"창고시설":55000,"의료시설":25000,"운동시설":10000,"교육연구시설":37000};
GYX.traffic=function(P){
  var t=TIA[P.use]; if(!t||P.ta<t) return null;
  return P.use+" 연면적 "+n0x(P.ta)+"㎡ ≥ "+n0x(t)+"㎡ (도시교통정비지역 기준)\n"+(P.use==="판매시설"?"※ 판매시설은 소매시장 6천㎡ · 상점 1.1만㎡ · 도매시장 1.3만㎡로 세분":"")+"\n협의: 고양시 교통정책과 (☎ 031-8075-2910)";
};

// 부담금 (개략) — 각 법령·고양시 조례
GYX.charges=function(P,S){
  var r=[], grow=/신축|증축|개축|재축/.test(P.act), sa=+S.area||0, jm=S.jimok||"";
  if(P.use==="공동주택"&&P.hh>=300) r.push("학교용지부담금 — 300세대 이상 분양 공동주택, 분양가격의 4/1,000 (2025.6.21. 개정 학교용지법 제5조)");
  if(P.use==="공동주택"&&P.hh>=20) r.push("광역교통시설부담금 — 수도권 20세대 이상 주택건설사업 등: 표준건축비 × 4% × 연면적 − 공제액 (대도시권광역교통법 제11조)");
  var bigWater = (P.use==="공동주택"&&(P.hh>=20||P.ta>=1000)) || (P.use==="숙박시설"&&P.ta>=600) || (/공장|창고/.test(P.use)&&P.ta>=1500) || P.ta>=2000;
  if(grow&&P.ta) r.push(bigWater? "상수도 원인자부담금(대규모) — 단위사업비 477,784원/㎥ × 1일 사용량 (2026 고시 제2026-186호)" : "상수도 원인자부담금 — 계량기 구경별 정액 (13mm 306천원 등, 급수공사 신청 시)");
  if(grow&&P.ta>=1000) r.push("하수도 원인자부담금 — 오수발생량 1일 10㎥ 이상 시: 오수량 × 단가(2024년 2,198,000원/㎥·일; 고양시 하수도 사용 조례 제25조)");
  var formChange=jm!=="대"&&!/^(장|학|창|종|주|체|잡)$/.test(jm);
  var urban=/주거|상업|공업|녹지/.test(S.zone||""), gb=S.flags&&S.flags.gb;
  var devMin=gb||!urban?1650:990;
  if(grow&&formChange&&sa>=devMin) r.push("개발부담금 — 토지 형질변경 수반 개발사업 "+n0x(devMin)+"㎡ 이상: 개발이익 × 20~25% (개발이익환수법 제13조)");
  if(/^임$/.test(jm)&&grow){ var bo=S.flags&&S.flags.forest&&S.flags.forest.some(function(n){return /보전산지|공익용|임업용/.test(n);});
    var unit=(bo?10840:8340)+Math.min((S.price||0)/1000,8340);
    r.push("대체산림자원조성비 — "+(bo?"보전산지 10,840":"준보전산지 8,340")+"원/㎡ + 공시지가×1/1,000 → 약 "+n0x(unit*sa)+"원 (산림청 고시 2026-16호)"); }
  if(P.ta>1000) r.push("교통유발부담금(매년) — 각 층 바닥면적 합계 1,000㎡ 초과 시설물 (고양시 교통유발부담금 조례)");
  return r;
};

// 허가권자 — 고양시 사무위임 조례 별표1 (2026.3.16. 시행)
var GU_TEL={"덕양구":"031-8075-5360","일산동구":"031-8075-6360","일산서구":"031-8075-7360"};
GYX.authority=function(S,P){
  var F=S.flags||{}, gu=S.gu||"관할 구";
  var city = F.gb || P.fl>=7 || P.ta>2000;
  var t = city ? "허가권자: 고양특례시장 — 본청 건축정책과 처리 (7층 이상·연면적 2천㎡ 초과 또는 개발제한구역, ☎ 031-8075-3130)"
               : "허가권자: "+gu+"청장 — "+gu+"청 건축과 처리 (6층 이하·연면적 2천㎡ 이하, ☎ "+(GU_TEL[gu]||"")+")";
  // 특례시: 도지사 사전승인은 51층 이상 또는 연면적 20만㎡ 이상만 (지방자치분권 및 균형성장에 관한 특별법 제59조제2호 — 2026.10.15. 제명 변경, 법제처 원문 2026-10-23 확인)
  if(P.fl>=51||P.ta>=200000) t+="\n※ 51층 이상 또는 연면적 20만㎡ 이상: 경기도지사 사전승인 대상 (특례시 — 지방자치분권 및 균형성장에 관한 특별법 제59조제2호, 건축법 제11조②)";
  else if(P.fl>=21||P.ta>=100000) t+="\n※ 21층·10만㎡ 이상이지만 고양시는 특례시라 도지사 사전승인 없이 시장이 처리 (51층·20만㎡ 미만)";
  return {text:t+"\n근거: 고양시 사무위임 조례 별표1 (건축정책과 1.1~1.3)",city:city};
};
GYX.authorityRows=[
  ["고양특례시 건축정책과 (본청)","7층 이상 또는 연면적 2천㎡ 초과, 개발제한구역 내 건축 · 건축위원회 · ☎ 031-8075-3130"],
  ["구청 건축과 위임 기준","6층 이하이면서 연면적 2천㎡ 이하 (개발제한구역 제외), 건축신고·가설건축물은 규모 무관 — 사무위임 조례 별표1"]
];
// 협의 부서 (고양시 업무검색 기준)
departments["도시계획"]="도시계획정책관 (☎ 031-8075-3070)";
departments["개발행위"]="도시개발과 (☎ 031-8075-3140)";
departments["농지"]="농업정책과 (☎ 031-8075-4231)";
departments["산지"]="녹지과·푸른도시사업소 (☎ 031-8075-4361)";
departments["하천"]="생태하천과·푸른도시사업소 (☎ 031-8075-2740)";
departments["하수"]="하수행정과·상하수도사업소 (☎ 031-8075-4560)";
departments["도로"]="도로정책과 (☎ 031-8075-2840) · 구청 안전건설과(도로점용)";
departments["교통"]="교통정책과 (☎ 031-8075-2910)";
departments["주차"]="주차교통과 (☎ 031-8075-2940)";
departments["경관"]="도시디자인담당관 (☎ 031-8075-2775)";
departments["문화예술"]="문화예술과 (☎ 031-8075-3383)";
departments["환경"]="환경정책과 (☎ 031-8075-2640)";
departments["소방"]="고양소방서 / 일산소방서 (관할)";
departments["개발제한"]="도시계획정책관 개발제한구역관리팀 (☎ 031-8075-3148) · 건축정책과(건축허가)";

return {
  brand:null, src:src, national:national, zones:zones, useZone:useZone, ord:ord, parking:parking, departments:departments,
  lawFor:lawFor, regNote:regNote, judge:judge, effective:effective,
  sub:SUB, subByKey:subByKey, subParents:subParents, dupDistricts:dupDistricts, dup:DUPD, authorityHtml:authorityHtml, consults:consults, guTel:GU_TEL, flow:flow, deemed:deemed, sources:sources, X:GYX,
  // 시연용 필지 — 용도지역·규제 유형별 (2026-10-21 토지이용규제 조회 기준)
  samples:[
    {label:"킨텍스 · 일반상업",addr:"일산서구 대화동 2600"},
    {label:"백석 업무지구 · 일반상업",addr:"일산동구 백석동 1299"},
    {label:"화정 · 제1종일반주거",addr:"덕양구 화정동 694-3"},
    {label:"화정 · 중심상업",addr:"덕양구 화정동 972"},
    {label:"원흥동 · 개발제한구역 농지",addr:"덕양구 원흥동 390"},
    {label:"가좌동 · 농업진흥구역",addr:"일산서구 가좌동 879-1"},
    {label:"벽제동 · 자연취락지구 임야",addr:"덕양구 벽제동 48"},
    {label:"풍동 · 성장관리 계획관리",addr:"일산동구 풍동 114-2"}
  ],
  introStats:[{k:"관할 면적",v:"268.15㎢"},{k:"인구 (2025.12)",v:"106만"},{k:"개발제한구역",v:"42.3%"}]
};
})();
