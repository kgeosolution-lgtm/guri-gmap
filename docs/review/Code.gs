/* ==========================================================================
   구리 생활지도 · 수정 요청 저장소 (Google Apps Script)
   - 구글 시트 한 장이 저장소입니다. 요청이 '수정요청' 시트에 한 줄씩 쌓이고, 캡처는 드라이브 폴더에 저장됩니다.
   - 시트에서 status 열을 done/todo 로 바꾸면 화면 목록에도 그대로 반영됩니다(관리자 화면의 '완료' 버튼과 같음).
   설치: 시트 → 확장 프로그램 → Apps Script → 이 파일 내용을 Code.gs 에 붙여넣기 → 배포 → 새 배포 →
         유형 '웹 앱', 실행 사용자 '나', 액세스 권한 '모든 사용자' → 웹 앱 URL 을 review.js 의 API 에 넣기.
   ========================================================================== */
var SHEET_NAME = '수정요청';
var FOLDER_NAME = '구리 생활지도 수정요청 캡처';
var ADMIN_KEY = 'guri'; // 관리자(완료 체크·남의 요청 삭제) 암호 — review.js 의 ADMIN_VALUE 와 같아야 합니다
var HEADERS = [
  'id',
  'created_at',
  'status',
  'done_at',
  'screen',
  'type',
  'sev',
  'loc',
  'content',
  'who',
  'owner',
  'shot_id',
  'page_url',
];

function sheet_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(SHEET_NAME) || ss.insertSheet(SHEET_NAME);
  if (sh.getLastRow() === 0) {
    sh.appendRow(HEADERS);
    sh.setFrozenRows(1);
    var rule = SpreadsheetApp.newDataValidation()
      .requireValueInList(['todo', 'done'], true)
      .setAllowInvalid(true)
      .build();
    sh.getRange(2, HEADERS.indexOf('status') + 1, 5000, 1).setDataValidation(rule);
  }
  return sh;
}
function folder_() {
  var it = DriveApp.getFoldersByName(FOLDER_NAME);
  return it.hasNext() ? it.next() : DriveApp.createFolder(FOLDER_NAME);
}
function out_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(
    ContentService.MimeType.JSON,
  );
}
function toIso_(v) {
  if (!v) return '';
  return v instanceof Date ? v.toISOString() : String(v);
}
function normStatus_(v) {
  return /done|완료/i.test(String(v || '')) ? 'done' : 'todo';
}

/* 시트 전체 읽기: 헤더 행 이름 기준(열 순서를 바꿔도 동작) */
function rows_() {
  var sh = sheet_();
  var v = sh.getDataRange().getValues();
  if (v.length < 2) return [];
  var h = v[0].map(String);
  var out = [];
  for (var i = 1; i < v.length; i++) {
    var r = { _row: i + 1 };
    for (var c = 0; c < h.length; c++) r[h[c]] = v[i][c];
    if (r.id) out.push(r);
  }
  return out;
}
function col_(name) {
  var h = sheet_().getRange(1, 1, 1, sheet_().getLastColumn()).getValues()[0].map(String);
  var i = h.indexOf(name);
  return i < 0 ? HEADERS.indexOf(name) + 1 : i + 1;
}
function list_() {
  return rows_()
    .map(function (r) {
      return {
        id: String(r.id),
        created_at: toIso_(r.created_at),
        status: normStatus_(r.status),
        done_at: toIso_(r.done_at),
        screen: r.screen || '',
        type: r.type || '',
        sev: r.sev || '',
        loc: r.loc || '',
        content: r.content || '',
        who: r.who || '',
        owner: r.owner || '',
        shot_id: r.shot_id || '',
        page_url: r.page_url || '',
      };
    })
    .sort(function (a, b) {
      return a.created_at < b.created_at ? 1 : -1;
    });
}
function find_(id) {
  var rows = rows_();
  for (var i = 0; i < rows.length; i++) if (String(rows[i].id) === String(id)) return rows[i];
  return null;
}

/* GET: ?action=list (목록) · ?action=shot&id=드라이브파일ID (캡처를 data URL 로) · ?action=ping */
function doGet(e) {
  var p = (e && e.parameter) || {};
  var action = p.action || 'list';
  try {
    if (action === 'list') return out_(list_());
    if (action === 'shot') {
      var b = DriveApp.getFileById(String(p.id)).getBlob();
      return out_({
        data: 'data:' + b.getContentType() + ';base64,' + Utilities.base64Encode(b.getBytes()),
      });
    }
    if (action === 'ping')
      return out_({ ok: true, sheet: SpreadsheetApp.getActiveSpreadsheet().getName() });
    return out_({ error: '알 수 없는 요청' });
  } catch (err) {
    return out_({ error: String((err && err.message) || err) });
  }
}
/* POST(본문은 JSON 문자열): {action:'add'|'status'|'delete', ...} */
function doPost(e) {
  var body = {};
  try {
    body = JSON.parse((e && e.postData && e.postData.contents) || '{}');
  } catch (x) {
    return out_({ error: '잘못된 요청' });
  }
  var lock = LockService.getScriptLock();
  lock.tryLock(10000);
  try {
    if (body.action === 'add') return out_(add_(body));
    if (body.action === 'status') return out_(status_(body));
    if (body.action === 'delete') return out_(del_(body));
    return out_({ error: '알 수 없는 요청' });
  } catch (err) {
    return out_({ error: String((err && err.message) || err) });
  } finally {
    lock.releaseLock();
  }
}
function add_(b) {
  var content = String(b.content || '').trim();
  if (!content) return { error: '내용이 비었어요' };
  var shotId = '';
  if (b.shot && /^data:image\//.test(b.shot)) {
    if (b.shot.length > 6000000) return { error: '이미지가 너무 커요' };
    var m = String(b.shot).match(/^data:(image\/[a-z]+);base64,(.*)$/);
    if (m) {
      var blob = Utilities.newBlob(
        Utilities.base64Decode(m[2]),
        m[1],
        'shot_' + Date.now() + (m[1] === 'image/png' ? '.png' : '.jpg'),
      );
      shotId = folder_().createFile(blob).getId();
    }
  }
  var id = Utilities.getUuid().slice(0, 8);
  sheet_().appendRow([
    id,
    new Date(),
    'todo',
    '',
    b.screen || '',
    b.type || '',
    b.sev || '',
    b.loc || '',
    content.slice(0, 2000),
    String(b.who || '').slice(0, 60),
    b.owner || '',
    shotId,
    String(b.page_url || '').slice(0, 300),
  ]);
  return { ok: true, id: id };
}
function status_(b) {
  if (b.key !== ADMIN_KEY) return { error: '관리자만 상태를 바꿀 수 있어요' };
  var r = find_(b.id);
  if (!r) return { error: '없는 항목이에요' };
  var done = b.status === 'done';
  var sh = sheet_();
  sh.getRange(r._row, col_('status')).setValue(done ? 'done' : 'todo');
  sh.getRange(r._row, col_('done_at')).setValue(done ? new Date() : '');
  return { ok: true };
}
function del_(b) {
  var r = find_(b.id);
  if (!r) return { error: '없는 항목이에요' };
  if (!(b.key && b.key === ADMIN_KEY) && String(r.owner || '') !== String(b.owner || ''))
    return { error: '본인이 올린 것만 지울 수 있어요' };
  if (r.shot_id) {
    try {
      DriveApp.getFileById(String(r.shot_id)).setTrashed(true);
    } catch (x) {}
  }
  sheet_().deleteRow(r._row);
  return { ok: true };
}
