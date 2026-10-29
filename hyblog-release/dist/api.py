"""Hyblog's bounded HTTPS queue. No AI credentials or execution live on the web server."""
import hashlib, hmac, http.cookies, json, os, re, secrets, sqlite3, sys, time
from pathlib import Path
from urllib.parse import parse_qs

ROOT = Path(__file__).resolve().parent
MAX_BODY = 52 * 1024 * 1024
ORIGIN = 'https://kgeodata.com'
COOKIE = 'HYBLOG_DEVICE'

class RequestError(Exception):
    def __init__(self, status, message): self.status, self.message = status, message

def digest(value): return hashlib.sha256(value.encode('utf8')).hexdigest()
def encode(value): return json.dumps(value, ensure_ascii=False, separators=(',', ':'))

class Queue:
    def __init__(self, root=Path('D:/services/hyblog/data')):
        self.root = Path(root)
        self.config = json.loads((self.root / 'config.json').read_text(encoding='utf-8-sig'))
        self.db = sqlite3.connect(str(self.root / 'hyblog.sqlite'), timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS devices(id TEXT PRIMARY KEY, code TEXT, name TEXT, state TEXT, created REAL, expires REAL);
          CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, owner TEXT, request_id TEXT, status TEXT, input TEXT, result TEXT, error TEXT, stage TEXT, created REAL, updated REAL, lease TEXT, cancel INTEGER DEFAULT 0, UNIQUE(owner, request_id));
          CREATE TABLE IF NOT EXISTS meta(id TEXT PRIMARY KEY, data TEXT);
          CREATE TABLE IF NOT EXISTS attempts(id TEXT PRIMARY KEY, count INTEGER, expires REAL);
        ''')
        self.db.execute('BEGIN IMMEDIATE')
        now = time.time()
        self.db.execute('DELETE FROM devices WHERE expires < ?', (now,))
        self.db.execute('DELETE FROM attempts WHERE expires < ?', (now,))
        self.db.execute('DELETE FROM jobs WHERE created < ?', (now-86400,))
        self.db.execute("UPDATE jobs SET status='failed',input=NULL,error=?,updated=? WHERE status IN ('queued','running') AND updated < ?", ('연결이 오래 끊겨 생성을 중단했어요. 입력은 브라우저에 남아 있습니다.', now, now-600))

    def worker(self, headers):
        return hmac.compare_digest(digest(headers.get('HTTP_X_HYBLOG_WORKER', '')), self.config['workerHash'])

    def device(self, headers):
        try:
            cookies = http.cookies.SimpleCookie(headers.get('HTTP_COOKIE', ''))
            token = cookies[COOKIE].value
            if not re.fullmatch('[a-f0-9]{64}', token): return None
            return self.db.execute('SELECT * FROM devices WHERE id=?', (digest(token),)).fetchone()
        except (KeyError, http.cookies.CookieError): return None

    def presence(self):
        row = self.db.execute("SELECT data FROM meta WHERE id='worker'").fetchone()
        item = json.loads(row['data']) if row else {}
        online = time.time()-item.get('at', 0) < 40
        return online, item

    def handle(self, route, method, body, headers):
        now = time.time()
        if route == '/api/health': return 200, {'application':'hyblog', 'version':1}, None
        if route.startswith('/worker/'):
            if not self.worker(headers): raise RequestError(403, '연결 권한이 없습니다.')
            return self.handle_worker(route, method, body, now)
        device = self.device(headers)
        if route == '/api/pair' and method == 'POST':
            if device: return 200, {'code':device['code'], 'approved':device['state']=='approved'}, None
            bucket = digest(headers.get('REMOTE_ADDR','') + str(int(now // 3600)))
            count = self.db.execute('SELECT count FROM attempts WHERE id=?', (bucket,)).fetchone()
            if count and count[0] >= 12: raise RequestError(429, '연결 요청이 많아요. 잠시 후 다시 시도해주세요.')
            self.db.execute('INSERT OR REPLACE INTO attempts VALUES (?,?,?)', (bucket, (count[0] if count else 0)+1, now+3600))
            token, code = secrets.token_hex(32), str(secrets.randbelow(900000)+100000)
            self.db.execute('INSERT INTO devices VALUES (?,?,?,?,?,?)', (digest(token), code, str(body.get('name','새 기기'))[:60], 'pending', now, now+900))
            cookie = COOKIE+'='+token+'; Path=/app/hyblog/; Max-Age=7776000; HttpOnly; Secure; SameSite=Strict'
            return 200, {'code':code, 'approved':False}, cookie
        if route == '/api/status' and method == 'GET':
            online, presence = self.presence()
            approved = bool(device and device['state']=='approved')
            return 200, {'ready': approved and online and bool(presence.get('ready')), 'authRequired':not approved, 'pairCode':device['code'] if device and not approved else None, 'workerOnline':online, 'message': '이 기기를 먼저 연결해주세요.' if not approved else ('초안 생성 PC와 연결되지 않았어요. PC에서 한편을 열어주세요.' if not online else presence.get('message','글쓰기 연결 확인 중'))}, None
        if not device or device['state'] != 'approved': raise RequestError(401, '이 기기를 먼저 연결해주세요.')
        if route == '/api/generate' and method == 'POST':
            request_id = str(body.get('requestId',''))
            if not re.fullmatch('[a-zA-Z0-9_-]{1,80}', request_id): raise RequestError(400, '요청 번호가 필요합니다.')
            old = self.db.execute('SELECT id FROM jobs WHERE owner=? AND request_id=?', (device['id'], request_id)).fetchone()
            if old: return 202, {'id':old['id']}, None
            online, presence = self.presence()
            if not online or not presence.get('ready'): raise RequestError(503, '초안 생성 PC의 연결과 Codex 사용 한도를 확인해주세요.')
            if not isinstance(body.get('place'),str) or not body['place'].strip(): raise RequestError(400, '식당 이름을 입력해주세요.')
            if not isinstance(body.get('photos'),list) or not 1 <= len(body['photos']) <= 24: raise RequestError(400, '사진은 1~24장 넣어주세요.')
            if self.db.execute("SELECT count(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0] >= 3: raise RequestError(409, '초안을 만들고 있어요. 잠시 후 다시 시도해주세요.')
            if self.db.execute("SELECT count(*) FROM jobs WHERE owner=? AND created>?", (device['id'],now-3600)).fetchone()[0] >= 10: raise RequestError(429, '한 시간에 10편까지 만들 수 있어요. 잠시 쉬었다 이어주세요.')
            job_id = secrets.token_hex(16)
            allowed = ['place','area','link','visitDate','notes','menus','facts','sponsorship','style','photos']
            payload = {k:body[k] for k in allowed if k in body}
            self.db.execute('INSERT INTO jobs(id,owner,request_id,status,input,stage,created,updated) VALUES(?,?,?,?,?,?,?,?)', (job_id,device['id'],request_id,'queued',encode(payload),'사진을 보내고 있어요',now,now))
            return 202, {'id':job_id}, None
        match = re.fullmatch('/api/jobs/([a-f0-9]{32})(/cancel)?',route)
        if match:
            job = self.db.execute('SELECT * FROM jobs WHERE id=? AND owner=?',(match[1],device['id'])).fetchone()
            if not job: raise RequestError(404,'작업이 만료됐어요. 입력은 브라우저에 남아 있습니다.')
            if match[2] and method=='POST':
                self.db.execute("UPDATE jobs SET cancel=1,status='cancelled',input=NULL,updated=? WHERE id=? AND status IN ('queued','running')",(now,job['id']))
                return 200, {'cancelled':True}, None
            if not match[2] and method=='GET':
                result = json.loads(job['result']) if job['result'] else {}
                return 200, {'id':job['id'],'status':job['status'],'stage':job['stage'],'error':job['error'],**result}, None
        raise RequestError(404,'요청을 찾지 못했어요.')

    def handle_worker(self, route, method, body, now):
        if route=='/worker/pairs' and method=='GET':
            rows = self.db.execute("SELECT id,code,name,state,created,expires FROM devices ORDER BY created DESC LIMIT 40").fetchall()
            return 200, {'devices':[dict(r) for r in rows]}, None
        if route=='/worker/approve' and method=='POST':
            item = self.db.execute("SELECT * FROM devices WHERE id=? AND code=? AND state='pending'",(body.get('id'),body.get('code'))).fetchone()
            if not item: raise RequestError(404,'대기 중인 연결을 찾지 못했습니다.')
            self.db.execute("UPDATE devices SET state='approved',expires=? WHERE id=?",(now+7776000,item['id']))
            return 200, {'approved':True}, None
        if route=='/worker/revoke' and method=='POST':
            self.db.execute('DELETE FROM devices WHERE id=?',(body.get('id'),))
            return 200, {'revoked':True}, None
        if route=='/worker/heartbeat' and method=='POST':
            self.db.execute("INSERT OR REPLACE INTO meta VALUES('worker',?)",(encode({'at':now,'ready':body.get('ready') is True,'message':str(body.get('message',''))[:200]}),))
            if body.get('id'):
                item = self.db.execute('SELECT cancel,status FROM jobs WHERE id=? AND lease=?',(body.get('id'),body.get('lease'))).fetchone()
                if item:
                    self.db.execute("UPDATE jobs SET stage=?,updated=? WHERE id=? AND status='running'",(str(body.get('stage','사진을 읽고 글을 만들고 있어요'))[:200],now,body['id']))
                    return 200, {'cancelled':bool(item['cancel']) or item['status']=='cancelled'}, None
            return 200, {'ok':True}, None
        if route=='/worker/claim' and method=='POST':
            if self.db.execute("SELECT id FROM jobs WHERE status='running'").fetchone(): return 200, {'job':None}, None
            item = self.db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
            if not item: return 200, {'job':None}, None
            lease=secrets.token_hex(16)
            self.db.execute("UPDATE jobs SET status='running',lease=?,updated=?,stage=? WHERE id=?",(lease,now,'사진을 읽고 글을 만들고 있어요',item['id']))
            return 200, {'job':{'id':item['id'],'lease':lease,'input':json.loads(item['input'])}}, None
        if route=='/worker/result' and method=='POST':
            item=self.db.execute('SELECT * FROM jobs WHERE id=? AND lease=?',(body.get('id'),body.get('lease'))).fetchone()
            if not item: raise RequestError(404,'작업을 찾지 못했습니다.')
            if item['status']=='running':
                result = {'draft':body['draft']} if isinstance(body.get('draft'),dict) else None
                self.db.execute('UPDATE jobs SET status=?,input=NULL,result=?,error=?,updated=?,stage=? WHERE id=?',('done' if result else 'failed',encode(result) if result else None,str(body.get('error','초안을 완성하지 못했어요.'))[:300] if not result else None,now,'초안이 완성됐어요' if result else '생성이 중단됐어요',item['id']))
            return 200, {'saved':True}, None
        raise RequestError(404,'요청을 찾지 못했습니다.')

def main():
    queue, cookie = None, None
    try:
        method = os.environ.get('REQUEST_METHOD','GET')
        if method not in ('GET','POST'): raise RequestError(405,'지원하지 않는 요청입니다.')
        if os.environ.get('HTTP_ORIGIN') not in (None, '', ORIGIN): raise RequestError(403,'요청 출처가 맞지 않습니다.')
        if os.environ.get('HTTP_SEC_FETCH_SITE') == 'cross-site': raise RequestError(403,'같은 사이트에서 이용해주세요.')
        if method=='POST' and (os.environ.get('HTTP_X_MEAL_NOTE')!='1' or not os.environ.get('CONTENT_TYPE','').startswith('application/json')): raise RequestError(403,'요청 형식이 맞지 않습니다.')
        size=int(os.environ.get('CONTENT_LENGTH','0') or '0')
        if not 0<=size<=MAX_BODY: raise RequestError(413,'사진 용량을 줄여주세요.')
        body=json.loads(sys.stdin.buffer.read(size).decode('utf8')) if size else {}
        if not isinstance(body,dict): raise RequestError(400,'입력 내용을 확인해주세요.')
        route=parse_qs(os.environ.get('QUERY_STRING','')).get('route',['/api/health'])[0]
        queue=Queue()
        code, result, cookie=queue.handle(route,method,body,os.environ)
        queue.db.commit()
    except RequestError as e:
        if queue: queue.db.commit()
        code,result=e.status,{'error':e.message}
    except Exception:
        if queue: queue.db.rollback()
        code,result=500,{'error':'서버 연결을 확인하고 있어요. 잠시 후 다시 시도해주세요.'}
    finally:
        if queue: queue.db.close()
    payload=encode(result).encode('utf8')
    headers='Status: '+str(code)+'\r\nContent-Type: application/json; charset=utf-8\r\nCache-Control: no-store\r\nContent-Length: '+str(len(payload))+'\r\n'
    if cookie: headers+='Set-Cookie: '+cookie+'\r\n'
    sys.stdout.buffer.write(headers.encode('ascii')+b'\r\n'+payload)

if __name__=='__main__': main()
