"""
/app/3dupload/splat_jobs.py — GPU 스플랫 워커(노트북 등 외부 GPU)용 작업 API. 토큰 인증.

인증: 요청 헤더 X-Worker-Token: <token>  (또는 ?token=)  — 서버 설정 kgeoscan.json 의 splat.worker_token 과 같아야 한다.
       토큰이 설정에 없거나 자리표시자(<SPLAT_TOKEN>)이면 모든 요청을 503 으로 거절한다.

  GET  ?op=list                         스플랫 대기(pending) 작업 목록 + 오래 걸린 processing(재할당 가능) 목록
  POST ?op=claim&job_id=&worker=        pending → processing (작업 메타 반환). 3시간 넘게 processing 인 작업도 다시 가져갈 수 있다
  GET  ?op=download&job_id=&file=zip    원본 Stray zip 스트리밍 (file=mesh 는 서버 융합 메시 out\mesh.ply)
  POST ?op=upload&job_id=               multipart: splat=<job>.splat (필수), stats=<json 문자열>(선택)
                                        → <glb_serve_dir>\<job>.splat, <job>.splat.json 저장, scan_points.splat_url 갱신, splat_status=done
  POST ?op=fail&job_id=&message=        splat_status=failed (워커가 포기한 작업)
  POST ?op=queue&job_id=[&force=1]      완료된 작업을 스플랫 대기열에 넣는다 (소급 적용·재학습). force 없이는 done/failed 인 스플랫만 다시 넣음
  GET  ?op=status&job_id=               큐 파일의 스플랫 관련 필드

큐 파일(<jobs_dir>\<job>.json) 필드: splat_status (pending|processing|done|failed), splat_url, splat_worker,
  splat_started_at, splat_done_at, splat_message, splat_stats(요약), splat_registered(bool)
표준 라이브러리만 사용 (IIS CGI, Python 3.14).
"""
import email
import email.policy
import hmac
import json
import os
import shutil
import socket
import sys
import time
import urllib.parse
import urllib.request

import msvcrt

msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_config, query_params, respond, safe_job_id  # noqa: E402

MAX_BODY = 512 * 1024 * 1024          # .splat 업로드 상한 512 MB (가우시안 100만 ≈ 32 MB)
STALE_HOURS_DEFAULT = 3


# ── 공통 ─────────────────────────────────────────────────────────────────────
def now_str():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def update_queue(path, **fields):
    q = read_json(path)
    q.update(fields)
    q["updated_at"] = now_str()
    write_json(path, q)
    return q


def check_token(cfg):
    want = (cfg.get("splat") or {}).get("worker_token") or ""
    if not want or want.startswith("<") or len(want) < 16:
        return "worker token not configured on server (splat.worker_token)"
    got = os.environ.get("HTTP_X_WORKER_TOKEN") or query_params().get("token") or ""
    if not hmac.compare_digest(want.encode("utf-8"), got.encode("utf-8")):
        return "bad token"
    return None


def parse_multipart():
    """stdin 의 multipart/form-data → (fields: {name: str}, files: {name: (filename, bytes)})  (upload.py 와 같은 방식)"""
    ctype = os.environ.get("CONTENT_TYPE", "")
    length = int(os.environ.get("CONTENT_LENGTH") or 0)
    if not ctype.lower().startswith("multipart/form-data") or length <= 0:
        raise ValueError("multipart/form-data 요청이 아닙니다")
    if length > MAX_BODY:
        raise ValueError("업로드 크기 초과 (최대 512 MB)")
    body = sys.stdin.buffer.read(length)
    head = b"Content-Type: " + ctype.encode("latin-1", "replace") + b"\r\nMIME-Version: 1.0\r\n\r\n"
    msg = email.message_from_bytes(head + body, policy=email.policy.HTTP)
    fields, files = {}, {}
    for part in msg.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue
        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""
        if filename:
            files[name] = (filename, payload)
        else:
            fields[name] = payload.decode("utf-8", "replace").strip()
    return fields, files


def load_job(cfg, job_id):
    """(queue_path, queue, meta) 또는 (None, None, None)"""
    qp = os.path.join(cfg["jobs_dir"], job_id + ".json")
    if not os.path.exists(qp):
        return None, None, None
    q = read_json(qp)
    mp = os.path.join(q.get("job_dir") or os.path.join(cfg["data_root"], job_id), "job.json")
    meta = read_json(mp) if os.path.exists(mp) else {}
    return qp, q, meta


def splat_summary(q, meta):
    zip_path = meta.get("scan_zip") or ""
    mesh = os.path.join(meta.get("job_dir") or "", "out", "mesh.ply")
    return {
        "job_id": q.get("job_id"), "title": q.get("title"), "scan_type": q.get("scan_type"), "mode": q.get("mode"),
        "created_at": q.get("created_at"), "status": q.get("status"),
        "splat_status": q.get("splat_status"), "splat_url": q.get("splat_url"), "splat_worker": q.get("splat_worker"),
        "splat_started_at": q.get("splat_started_at"), "splat_done_at": q.get("splat_done_at"),
        "splat_message": q.get("splat_message"), "splat_requested": bool(meta.get("splat_requested")),
        "zip_bytes": os.path.getsize(zip_path) if zip_path and os.path.exists(zip_path) else 0,
        "mesh_available": os.path.exists(mesh), "objectid": q.get("objectid"),
    }


def is_stale(q, hours):
    if q.get("splat_status") != "processing":
        return False
    try:
        t = time.mktime(time.strptime(q.get("splat_started_at") or q.get("updated_at"), "%Y-%m-%d %H:%M:%S"))
    except Exception:
        return True
    return time.time() - t > hours * 3600


# ── scan_points 갱신 (REST, 표준 라이브러리) ───────────────────────────────────
def http_json(url, data=None, timeout=60):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode("utf-8") if data is not None else None)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        out = json.loads(r.read().decode("utf-8"))
    if isinstance(out, dict) and "error" in out:
        raise RuntimeError(f"ArcGIS 오류: {out['error']}")
    return out


def register_splat_url(cfg, q, splat_url):
    """scan_points 의 해당 점(objectid 또는 glb_url 로 찾음)에 splat_url 을 쓴다. 성공하면 objectid 를 돌려준다."""
    layer = cfg["points_layer_url"]
    token = http_json(cfg["portal_url"] + "/sharing/rest/generateToken",
                      {"username": cfg["portal_user"], "password": cfg["portal_password"],
                       "referer": cfg["server_url"], "expiration": 10, "f": "json"})["token"]
    info = http_json(layer, {"f": "json", "token": token})
    fields = {f.get("name", "").lower() for f in info.get("fields", [])}
    if "splat_url" not in fields:
        raise RuntimeError("scan_points 에 splat_url 필드가 없음 (maintenance add-fields 필요)")
    oid = q.get("objectid")
    if not oid and q.get("glb_url"):
        found = http_json(layer + "/query", {"where": "glb_url = '%s'" % q["glb_url"].replace("'", "''"),
                                             "outFields": "objectid", "returnGeometry": "false", "f": "json", "token": token})
        feats = found.get("features") or []
        if feats:
            oid = feats[-1]["attributes"].get("objectid")
    if not oid:
        raise RuntimeError("scan_points 에서 이 작업의 점을 찾지 못함 (objectid/glb_url 없음)")
    out = http_json(layer + "/updateFeatures",
                    {"features": json.dumps([{"attributes": {"objectid": int(oid), "splat_url": splat_url}}]), "f": "json", "token": token})
    res = (out.get("updateResults") or [{}])[0]
    if not res.get("success"):
        raise RuntimeError("updateFeatures 실패: " + str(res.get("error")))
    return int(oid)


# ── 작업별 처리 ───────────────────────────────────────────────────────────────
def op_list(cfg):
    stale_h = float((cfg.get("splat") or {}).get("stale_processing_hours", STALE_HOURS_DEFAULT))
    pending, stale = [], []
    try:
        names = sorted(os.listdir(cfg["jobs_dir"]))
    except OSError:
        names = []
    for n in names:
        if not n.endswith(".json"):
            continue
        job_id = n[:-5]
        if not safe_job_id(job_id):
            continue
        try:
            qp, q, meta = load_job(cfg, job_id)
        except Exception:
            continue
        if not q:
            continue
        if q.get("splat_status") == "pending" and q.get("status") == "done":
            pending.append(splat_summary(q, meta))
        elif is_stale(q, stale_h):
            stale.append(splat_summary(q, meta))
    pending.sort(key=lambda s: s.get("created_at") or "")
    respond({"pending": pending, "stale": stale, "server_time": now_str()})


def op_claim(cfg, job_id):
    qp, q, meta = load_job(cfg, job_id)
    if not q:
        return respond({"error": "없는 작업"}, "404 Not Found")
    stale_h = float((cfg.get("splat") or {}).get("stale_processing_hours", STALE_HOURS_DEFAULT))
    force = query_params().get("force") in ("1", "true")
    if not (q.get("splat_status") == "pending" or is_stale(q, stale_h) or force):
        return respond({"error": f"splat_status={q.get('splat_status')} 인 작업은 가져갈 수 없습니다"}, "409 Conflict")
    if q.get("status") != "done" and not force:
        return respond({"error": f"메시 처리가 끝나지 않은 작업 (status={q.get('status')})"}, "409 Conflict")
    if not (meta.get("scan_zip") and os.path.exists(meta["scan_zip"])):
        update_queue(qp, splat_status="failed", splat_message="원본 zip 이 서버에 없음")
        return respond({"error": "원본 zip 이 서버에 없음"}, "410 Gone")
    worker = (query_params().get("worker") or "")[:60]
    q = update_queue(qp, splat_status="processing", splat_worker=worker, splat_started_at=now_str(), splat_message="GPU 워커 학습 중")
    respond(splat_summary(q, meta))


def op_download(cfg, job_id):
    qp, q, meta = load_job(cfg, job_id)
    if not q:
        return respond({"error": "없는 작업"}, "404 Not Found")
    which = query_params().get("file") or "zip"
    if which == "zip":
        path, ctype, name = meta.get("scan_zip") or "", "application/zip", "scan_zip.zip"
    elif which == "mesh":
        path, ctype, name = os.path.join(meta.get("job_dir") or "", "out", "mesh.ply"), "application/octet-stream", "mesh.ply"
    else:
        return respond({"error": "file 은 zip 또는 mesh"}, "400 Bad Request")
    if not path or not os.path.exists(path):
        return respond({"error": f"{which} 파일이 서버에 없음"}, "404 Not Found")
    size = os.path.getsize(path)
    out = sys.stdout.buffer
    out.write(b"Status: 200 OK\r\n")
    out.write(f"Content-Type: {ctype}\r\n".encode("ascii"))
    out.write(f"Content-Length: {size}\r\n".encode("ascii"))
    out.write(f"Content-Disposition: attachment; filename=\"{name}\"\r\n".encode("ascii"))
    out.write(b"Cache-Control: no-store\r\n\r\n")
    with open(path, "rb") as f:
        shutil.copyfileobj(f, out, 1024 * 1024)
    out.flush()


def op_upload(cfg, job_id):
    qp, q, meta = load_job(cfg, job_id)
    if not q:
        return respond({"error": "없는 작업"}, "404 Not Found")
    try:
        fields, files = parse_multipart()
    except ValueError as e:
        return respond({"error": str(e)}, "400 Bad Request")
    item = files.get("splat")
    if not item or not item[1]:
        return respond({"error": "splat 파일이 없습니다"}, "400 Bad Request")
    fname, blob = item
    ext = os.path.splitext(fname)[1].lower()
    if ext not in (".splat", ".spz", ".ksplat"):
        return respond({"error": f"허용되지 않는 확장자 {ext}"}, "400 Bad Request")
    if ext == ".splat" and len(blob) % 32 != 0:
        return respond({"error": ".splat 길이가 32 바이트 배수가 아닙니다"}, "400 Bad Request")
    serve_dir, serve_url = cfg["glb_serve_dir"], cfg["glb_serve_url"]
    os.makedirs(serve_dir, exist_ok=True)
    dest = os.path.join(serve_dir, job_id + ext)
    with open(dest + ".tmp", "wb") as f:
        f.write(blob)
    os.replace(dest + ".tmp", dest)
    splat_url = f"{serve_url}/{job_id}{ext}"
    stats = None
    if fields.get("stats"):
        try:
            stats = json.loads(fields["stats"])
            with open(os.path.join(serve_dir, job_id + ext + ".json"), "w", encoding="utf-8") as f:
                json.dump({"job_id": job_id, "splat_url": splat_url, "view": stats.get("view"),
                           "gaussians": stats.get("gaussians"), "train_seconds": stats.get("train_seconds"),
                           "test_psnr": stats.get("test_psnr"), "worker": stats.get("worker"), "created": now_str()},
                          f, ensure_ascii=False, indent=2)
        except Exception as e:
            stats = {"parse_error": str(e)}
    summary = None
    if isinstance(stats, dict):
        summary = {k: stats.get(k) for k in ("gaussians", "train_seconds", "total_seconds", "test_psnr", "peak_vram_gb",
                                             "iters", "strategy", "keyframes_train", "worker", "splat_bytes") if k in stats}
    registered, reg_msg, oid = False, "", q.get("objectid")
    try:
        oid = register_splat_url(cfg, q, splat_url)
        registered = True
    except Exception as e:
        reg_msg = str(e)[:300]
    q = update_queue(qp, splat_status="done", splat_url=splat_url, splat_done_at=now_str(), splat_stats=summary,
                     splat_registered=registered, objectid=oid or q.get("objectid"),
                     splat_message="스플랫 완료" + ("" if registered else " (scan_points 등록 실패: " + reg_msg + ")"))
    respond({"job_id": job_id, "splat_url": splat_url, "bytes": len(blob), "registered": registered,
             "objectid": oid, "message": q.get("splat_message")})


def op_fail(cfg, job_id):
    qp, q, meta = load_job(cfg, job_id)
    if not q:
        return respond({"error": "없는 작업"}, "404 Not Found")
    msg = (query_params().get("message") or "워커 실패")[:300]
    q = update_queue(qp, splat_status="failed", splat_message=msg, splat_done_at=now_str())
    respond(splat_summary(q, meta))


def op_queue(cfg, job_id):
    qp, q, meta = load_job(cfg, job_id)
    if not q:
        return respond({"error": "없는 작업"}, "404 Not Found")
    force = query_params().get("force") in ("1", "true")
    if q.get("status") != "done":
        return respond({"error": f"메시 처리가 끝난 작업만 넣을 수 있습니다 (status={q.get('status')})"}, "409 Conflict")
    if q.get("mode") != "stray" or not (meta.get("scan_zip") and os.path.exists(meta["scan_zip"])):
        return respond({"error": "Stray 원본 zip 이 있는 작업만 스플랫을 만들 수 있습니다"}, "409 Conflict")
    if q.get("splat_status") in ("pending", "processing") and not force:
        return respond(splat_summary(q, meta))
    q = update_queue(qp, splat_status="pending", splat_message="스플랫 대기 중 (수동 요청)", splat_worker=None, splat_started_at=None)
    respond(splat_summary(q, meta))


def op_status(cfg, job_id):
    qp, q, meta = load_job(cfg, job_id)
    if not q:
        return respond({"error": "없는 작업"}, "404 Not Found")
    respond(splat_summary(q, meta))


def main():
    cfg = load_config()
    err = check_token(cfg)
    if err:
        return respond({"error": err}, "503 Service Unavailable" if "configured" in err else "403 Forbidden")
    p = query_params()
    op = (p.get("op") or "").lower()
    method = os.environ.get("REQUEST_METHOD", "GET")
    if op == "list":
        return op_list(cfg)
    job_id = safe_job_id(p.get("job_id"))
    if not job_id:
        return respond({"error": "job_id 형식 오류"}, "400 Bad Request")
    if op == "download":
        return op_download(cfg, job_id)
    if op == "status":
        return op_status(cfg, job_id)
    if method != "POST":
        return respond({"error": "POST only"}, "405 Method Not Allowed")
    if op == "claim":
        return op_claim(cfg, job_id)
    if op == "upload":
        return op_upload(cfg, job_id)
    if op == "fail":
        return op_fail(cfg, job_id)
    if op == "queue":
        return op_queue(cfg, job_id)
    respond({"error": "op 는 list|claim|download|upload|fail|queue|status"}, "400 Bad Request")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        respond({"error": f"서버 오류: {e}"}, "500 Internal Server Error")
