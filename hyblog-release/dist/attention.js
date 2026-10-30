(function(root){
 function from(message,terminal=false){
  const s=String(message||'');
  if(/추가.*(보안|인증)|보안 확인|CAPTCHA/.test(s))return {code:'naver_security',title:'네이버 보안 확인이 필요해요',action:'PC의 Edge에서 네이버 추가 확인을 마쳐주세요. 완료 후 아래 버튼으로 진행 상태를 다시 확인할 수 있어요.',waiting:!terminal};
  if(/계정이 달라|로그인.*(필요|만료)|101507kim으로 로그인/.test(s))return {code:'naver_login',title:'아내 네이버 로그인을 확인해주세요',action:'PC의 Edge에서 101507kim 계정으로 로그인을 완료해주세요. 다른 계정에는 글을 입력하지 않아요.',waiting:!terminal};
  if(!terminal)return null;
  if(/연결|초안을 받지/.test(s))return {code:'pc_connection',title:'PC 연결을 확인해주세요',action:'PC가 켜져 있고 Edge의 망나 모먼트 네이버 연결이 켜져 있는지 확인해주세요. 기존 확장 이름은 한편으로 표시될 수 있어요.',waiting:false};
  return {code:'naver_editor',title:'네이버 작성 화면을 확인해주세요',action:'PC의 Edge에 열린 작성 화면과 임시저장 목록을 확인해주세요. 이미 저장된 제목이 있는지 먼저 보고, 저장되지 않았을 때만 다시 전송해주세요.',waiting:false};
 }
 root.HyblogAttention=Object.freeze({from});
})(typeof window==='undefined'?globalThis:window);

