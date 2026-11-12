r"""
/app/3dupload/splat_jobs.py — GPU 스플랫 워커(노트북 등 외부 GPU)용 작업 API. 토큰 인증.

인증: 요청 헤더 X-Worker-Token: <token>  (또는 ?token=)  — 서버 설정 kgeoscan.json 의 splat.worker_token 과 같아야 한다.
       토큰이 설정에 없거나 자리표시자(<SPLAT_TOKEN>)이면 모든 요청을 503 으로 거절한다.

  GET  ?op=list                         스플랫 대기(pending) 작업 목록 + 오래 걸린 processing(재할당 가능) 목록
  POST ?op=claim&job_id=&worker=        pending → processing (작업 메타 반환). 3시간 넘게 processing 인 작업도 다시 가져갈 수 있다
  GET  ?op=download&job_id=&file=zip    원본 Stray zip 스트리밍 (file=mesh 는 서버 융합 메시 out\mesh.ply,
                                        file=video 는 영상 작업의 원본 영상 job.json video_path — 2026-11-10 docs\video3d_contract.md)
  POST ?op=upload&job_id=               multipart: splat=<job>.splat (필수), stats=<json 문자열>(선택), thumb=<jpg>(선택, 영상 작업 대표 화면)
                                        → <glb_serve_dir>\<job>.splat, <job>.splat.json 저장, scan_points.splat_url 갱신, splat_status=done
                                        → thumb 가 있으면 <glb_serve_dir>\<job>.jpg 를 덮어씀 (scan_points.thumb_url 이 이미 그 주소)
  영상 작업(job.json mode=video, 큐 splat_kind=video): list/claim 이 mode, splat_kind, georef, video_bytes, video_ext 를 함께 돌려준다.
  사진 작업(job.json mode=photos, 큐 splat_kind=video, 계약 1b): list/claim 이 photo_count, photos_bytes 를 더 돌려주고,
      GET ?op=download&job_id=&file=photos 는 photos_dir 의 사진들을 무압축(STORE) zip 으로 보낸다 (Content-Length 있음).
  큐의 quality(계약 1c, 서버 media_check)는 list/claim 에 그대로 실어 보낸다 — 워커는 참고만 한다.
  웹 굴착 기록(job.json trench.mode=1, docs\web_trench_contract.md): list/claim 이 trench_mode, files{sensors, marks2d} 를 돌려주고,
      GET ?op=download&file=sensors|marks2d 로 촬영 페이지가 올린 sensors.json / marks2d.json 을 받는다.
      실측 묶음 trench_bundle.zip(계약 3절)은 두 가지로 올린다 — 받으면 큐를 status=pending, kind=trench_post 로 두어
      대기열 처리기 → pipeline.py 가 굴착 후처리(GLB 서빙·관 추출·조서)를 한다:
        · op=upload 의 multipart 파트 trench_bundle (요청 전체 512 MB 이하)
        · POST ?op=bundle&job_id=  본문 = zip 그대로 (Content-Type application/zip, 최대 1 GB = IIS 한도, 디스크로 바로 씀)
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

# msvcrt.setmode 는 쓰지 않는다: 파이썬은 Windows 에서 표준 입출력을 이미 바이너리로 연다(확인함).
# IIS 에서 HTTP/2 요청일 때 stdin/stdout 에 setmode 를 부르면 응답이 끊기고(RST), GET 에서는 502 가 났다.

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_config, query_params, respond, safe_job_id  # noqa: E402

MAX_BODY = 512 * 1024 * 1024          # .splat 업로드 상한 512 MB (가우시안 100만 ≈ 32 MB)
STALE_HOURS_DEFAULT = 3
MAX_THUMB = 8 * 1024 * 1024           # 영상 작업 대표 화면 jpg 상한
VIDEO_TYPES = {".mp4": "video/mp4", ".mov": "video/quicktime", ".m4v": "video/x-m4v", ".webm": "video/webm", ".3gp": "video/3gpp"}
PHOTO_EXTS = (".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp")          # 계약 1b
MIN_PHOTOS = 3                                                             # 이보다 적으면 사진 작업을 가져가지 않음 (업로드는 10장 이상)
MAX_BUNDLE = 1024 * 1024 * 1024       # 실측 묶음 상한 = IIS maxAllowedContentLength (web.config). 계약의 1.5 GB 는 IIS 한도를 올려야 함
BUNDLE_FILES = {"rgb.mp4", "odometry.csv", "frame_quality.csv", "camera_matrix.csv", "mesh.ply", "mesh.glb", "scan.las",
                "marks.json", "scale.json", "georef.json"}                 # 계약 3절 — zip 맨 위 (감싸는 폴더 없이)
BUNDLE_DIRS = {"hires": (".jpg", ".jpeg", ".png", ".json")}               # hires/*.jpg + hires/poses.json
BUNDLE_REQUIRED = ("scale.json", "georef.json", "mesh.glb")
BUNDLE_MAX_ENTRIES = 3000
BUNDLE_MAX_UNPACKED = 4 * 1024 * 1024 * 1024                               # 압축 폭탄 방지


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


def job_mode(q, meta):
    return q.get("mode") or meta.get("mode")


def is_photos(q, meta):
    """사진 작업 (기본 카메라 사진 여러 장 → SfM → 스플랫, 계약 1b). 큐 splat_kind 는 영상과 같은 video"""
    return job_mode(q, meta) == "photos"


def is_video(q, meta):
    """영상·사진 작업 (자세 없는 기본 카메라 → 워커가 SfM 부터). 사진 작업도 같은 흐름이다"""
    return job_mode(q, meta) in ("video", "photos") or q.get("splat_kind") == "video"


def photo_files(meta):
    """photos_dir 안의 사진 (허용 확장자, 이름순). 하위 폴더는 보지 않는다"""
    d = meta.get("photos_dir") or ""
    if not d or not os.path.isdir(d):
        return []
    out = []
    for n in sorted(os.listdir(d)):
        p = os.path.join(d, n)
        if os.path.splitext(n)[1].lower() in PHOTO_EXTS and os.path.isfile(p):
            out.append(p)
    return out


def video_file(meta):
    """(경로, 확장자) — 확장자가 허용 목록 밖이거나 파일이 없으면 ("", ext)"""
    path = meta.get("video_path") or ""
    ext = os.path.splitext(path)[1].lower()
    if not path or ext not in VIDEO_TYPES or not os.path.isfile(path):
        return "", ext
    return path, ext


def trench_info(q, meta):
    """웹 굴착 기록: (trench_mode, {sensors, marks2d} 파일 있음 여부, {이름: 서버 경로})"""
    t = meta.get("trench") or q.get("trench") or {}
    paths = {}
    for key, name in (("sensors_path", "sensors"), ("marks2d_path", "marks2d")):
        p = (meta.get("trench") or {}).get(key) or ""
        if p and os.path.isfile(p):
            paths[name] = p
    return bool(t.get("mode")), {"sensors": "sensors" in paths, "marks2d": "marks2d" in paths}, paths


def check_bundle(path):
    """trench_bundle.zip 검사 (계약 3절) → 이름 목록. 틀리면 ValueError (메시지는 워커 로그용)"""
    import zipfile
    try:
        zf = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as e:
        raise ValueError(f"trench_bundle: zip 이 아닙니다 ({e})")
    with zf:
        infos = zf.infolist()
        if len(infos) > BUNDLE_MAX_ENTRIES:
            raise ValueError(f"trench_bundle: 항목이 너무 많습니다 ({len(infos)})")
        total, names = 0, []
        for zi in infos:
            n = zi.filename.replace("\\", "/")
            parts = n.split("/")
            if n.startswith("/") or (len(n) > 1 and n[1] == ":") or ".." in parts or any(p in (".",) for p in parts):
                raise ValueError(f"trench_bundle: 허용되지 않는 경로 {zi.filename!r}")
            if zi.is_dir():
                if n.rstrip("/") not in BUNDLE_DIRS:
                    raise ValueError(f"trench_bundle: 허용되지 않는 폴더 {zi.filename!r}")
                continue
            if len(parts) == 1:
                if n not in BUNDLE_FILES:
                    raise ValueError(f"trench_bundle: 허용되지 않는 파일 {zi.filename!r}")
            elif len(parts) == 2 and parts[0] in BUNDLE_DIRS and parts[1] and not parts[1].startswith("."):
                if os.path.splitext(parts[1])[1].lower() not in BUNDLE_DIRS[parts[0]]:
                    raise ValueError(f"trench_bundle: 허용되지 않는 파일 {zi.filename!r}")
            else:
                raise ValueError(f"trench_bundle: 허용되지 않는 경로 {zi.filename!r}")
            total += zi.file_size
            names.append(n)
        if total > BUNDLE_MAX_UNPACKED:
            raise ValueError("trench_bundle: 풀었을 때 크기가 너무 큽니다")
        missing = [r for r in BUNDLE_REQUIRED if r not in names]
        if missing:
            raise ValueError("trench_bundle: 필수 파일 없음 " + ", ".join(missing))
        for jn in ("scale.json", "georef.json"):
            try:
                if not isinstance(json.loads(zf.read(jn).decode("utf-8-sig")), dict):
                    raise ValueError
            except Exception:
                raise ValueError(f"trench_bundle: {jn} 이 JSON 객체가 아닙니다")
    return names


def accept_bundle(qp, q, meta, tmp_path):
    """검사를 통과한 묶음을 <job_dir>\\trench_bundle.zip 으로 옮기고 큐를 굴착 후처리 대기로 둔다 → 큐"""
    dest = os.path.join(meta.get("job_dir") or os.path.dirname(tmp_path), "trench_bundle.zip")
    os.replace(tmp_path, dest)
    return update_queue(qp, status="pending", kind="trench_post", step=7, trench_post="pending",
                        trench_post_message="굴착 산출물 대기 중 (3D 는 먼저 볼 수 있음)", trench_bundle_path=dest,
                        trench_bundle_bytes=os.path.getsize(dest), message="굴착 산출물 대기 중")


def splat_summary(q, meta):
    zip_path = meta.get("scan_zip") or ""
    mesh = os.path.join(meta.get("job_dir") or "", "out", "mesh.ply")
    video = is_video(q, meta)
    photos = is_photos(q, meta)
    vpath, vext = video_file(meta) if video and not photos else ("", "")
    pfiles = photo_files(meta) if photos else []
    trench_mode, tfiles, _ = trench_info(q, meta)
    return {
        "trench_mode": trench_mode, "files": tfiles if trench_mode else None,          # 웹 굴착 기록 (web_trench_contract.md)
        "trench_post": q.get("trench_post"), "trench_post_message": q.get("trench_post_message"),
        "job_id": q.get("job_id"), "title": q.get("title"), "scan_type": q.get("scan_type"), "mode": job_mode(q, meta),
        "splat_kind": q.get("splat_kind") or ("video" if video else None),
        "georef": (meta.get("georef") or q.get("georef")) if video else None,
        "video_bytes": os.path.getsize(vpath) if vpath else 0, "video_ext": vext or None,
        "photo_count": len(pfiles) if photos else None, "photos_bytes": sum(os.path.getsize(p) for p in pfiles) if photos else None,
        "quality": q.get("quality") if video else None,                    # 계약 1c (서버 media_check) — 워커는 참고만
        "created_at": q.get("created_at"), "status": q.get("status"),
        "splat_status": q.get("splat_status"), "splat_url": q.get("splat_url"), "splat_worker": q.get("splat_worker"),
        "splat_started_at": q.get("splat_started_at"), "splat_done_at": q.get("splat_done_at"),
        "splat_message": q.get("splat_message"), "splat_requested": bool(meta.get("splat_requested")),
        "zip_bytes": os.path.getsize(zip_path) if zip_path and os.path.exists(zip_path) else 0,
        "mesh_available": os.path.exists(mesh), "objectid": q.get("objectid"),
        "object": q.get("object") or meta.get("object"), "object_region": q.get("object_region"),   # 물체 모드 (upload.py / pipeline.py 기록)
        "splat_full_url": q.get("splat_full_url"),
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
    video = is_video(q, meta)
    if video and is_photos(q, meta):
        if len(photo_files(meta)) < MIN_PHOTOS:
            update_queue(qp, splat_status="failed", splat_message="서버에 사진이 없거나 너무 적습니다")
            return respond({"error": "사진이 서버에 없거나 너무 적음 (photos_dir)"}, "410 Gone")
    elif video:
        if not video_file(meta)[0]:
            update_queue(qp, splat_status="failed", splat_message="원본 영상이 서버에 없습니다")
            return respond({"error": "원본 영상이 서버에 없음 (video_path)"}, "410 Gone")
    elif not (meta.get("scan_zip") and os.path.exists(meta["scan_zip"])):
        update_queue(qp, splat_status="failed", splat_message="원본 zip 이 서버에 없음")
        return respond({"error": "원본 zip 이 서버에 없음"}, "410 Gone")
    worker = (query_params().get("worker") or "")[:60]
    q = update_queue(qp, splat_status="processing", splat_worker=worker, splat_started_at=now_str(),
                     splat_message=("사진에서 3D 만드는 중 (GPU)" if is_photos(q, meta) else "영상에서 3D 만드는 중 (GPU)") if video else "GPU 워커 학습 중")
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
    elif which == "video":
        path, ext = video_file(meta)
        if not path:
            return respond({"error": f"영상 파일이 서버에 없음 (확장자 {ext or '없음'})"}, "404 Not Found")
        ctype, name = VIDEO_TYPES[ext], "video" + ext                 # 원래 확장자 (워커가 디코더를 고르는 데 씀)
    elif which == "photos":
        return download_photos(meta)
    elif which in ("sensors", "marks2d"):                         # 웹 굴착 기록 부속 파일
        path = trench_info(q, meta)[2].get(which, "")
        if not path:
            return respond({"error": f"{which} 파일이 서버에 없음"}, "404 Not Found")
        ctype, name = "application/json", which + ".json"
    else:
        return respond({"error": "file 은 zip, mesh, video, photos, sensors, marks2d 중 하나"}, "400 Bad Request")
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


def download_photos(meta):
    """photos_dir 의 사진들 → 무압축(STORE) zip 을 작업 폴더에 잠깐 만들고 Content-Length 와 함께 보낸 뒤 지운다.
    (사진은 이미 압축돼 있어 STORE 가 빠르고, 길이를 알아야 IIS·워커가 끊김을 알아챈다)"""
    import glob
    import zipfile
    files = photo_files(meta)
    if not files:
        return respond({"error": "사진이 서버에 없음 (photos_dir)"}, "404 Not Found")
    jd = meta.get("job_dir") or os.path.dirname(meta.get("photos_dir") or "")
    for old in glob.glob(os.path.join(jd, "_photos_dl_*.zip")):        # 끊긴 다운로드가 남긴 것 (1시간 지난 것만)
        try:
            if time.time() - os.path.getmtime(old) > 3600:
                os.remove(old)
        except OSError:
            pass
    tmp = os.path.join(jd, f"_photos_dl_{os.getpid()}_{int(time.time())}.zip")
    try:
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as zf:
            for p in files:
                zf.write(p, arcname=os.path.basename(p))                # 이름은 서버가 정한 0001.jpg … (경로 없음)
        size = os.path.getsize(tmp)
        out = sys.stdout.buffer
        out.write(b"Status: 200 OK\r\n")
        out.write(b"Content-Type: application/zip\r\n")
        out.write(f"Content-Length: {size}\r\n".encode("ascii"))
        out.write(b"Content-Disposition: attachment; filename=\"photos.zip\"\r\n")
        out.write(f"X-Photo-Count: {len(files)}\r\n".encode("ascii"))
        out.write(b"Cache-Control: no-store\r\n\r\n")
        with open(tmp, "rb") as f:
            shutil.copyfileobj(f, out, 1024 * 1024)
        out.flush()
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


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
    thumb_item = files.get("thumb")
    if thumb_item and thumb_item[1] and (len(thumb_item[1]) > MAX_THUMB or not thumb_item[1].startswith(b"\xff\xd8\xff")):
        return respond({"error": "thumb 는 8 MB 이하 JPEG 이어야 합니다"}, "400 Bad Request")   # 아무것도 쓰기 전에 검사
    bundle_tmp = None
    bundle_item = files.get("trench_bundle")
    if bundle_item and bundle_item[1]:                            # 웹 굴착 기록 실측 묶음 — 이것도 쓰기 전에 검사
        if not trench_info(q, meta)[0]:
            return respond({"error": "굴착 기록(trench_mode) 작업이 아닙니다"}, "409 Conflict")
        if q.get("status") != "done":
            return respond({"error": f"처리가 끝난 작업에만 묶음을 올릴 수 있습니다 (status={q.get('status')})"}, "409 Conflict")
        bundle_tmp = os.path.join(meta.get("job_dir") or cfg["data_root"], f"_bundle_{os.getpid()}.zip.tmp")
        with open(bundle_tmp, "wb") as f:
            f.write(bundle_item[1])
        try:
            check_bundle(bundle_tmp)
        except ValueError as e:
            os.remove(bundle_tmp)
            return respond({"error": str(e)}, "400 Bad Request")
    serve_dir, serve_url = cfg["glb_serve_dir"], cfg["glb_serve_url"]
    os.makedirs(serve_dir, exist_ok=True)
    dest = os.path.join(serve_dir, job_id + ext)
    with open(dest + ".tmp", "wb") as f:
        f.write(blob)
    os.replace(dest + ".tmp", dest)
    splat_url = f"{serve_url}/{job_id}{ext}"
    # 물체 모드: 자르기 전 전체 스플랫 <job>_full.splat (선택)
    full_url = None
    full_item = files.get("splat_full")
    if full_item and full_item[1]:
        fdest = os.path.join(serve_dir, job_id + "_full" + ext)
        with open(fdest + ".tmp", "wb") as f:
            f.write(full_item[1])
        os.replace(fdest + ".tmp", fdest)
        full_url = f"{serve_url}/{job_id}_full{ext}"
    else:
        for old in (os.path.join(serve_dir, job_id + "_full" + e) for e in (".splat", ".spz", ".ksplat")):
            if os.path.exists(old):
                os.remove(old)                                   # 전체 모드로 다시 만든 경우 옛 _full 제거
    # 영상 작업: 3D 에서 고른 대표 화면 (선택) → <job>.jpg 덮어쓰기 (scan_points.thumb_url 이 이미 이 주소)
    thumb_url = None
    if thumb_item and thumb_item[1]:
        tdest = os.path.join(serve_dir, job_id + ".jpg")
        with open(tdest + ".tmp", "wb") as f:
            f.write(thumb_item[1])
        os.replace(tdest + ".tmp", tdest)
        thumb_url = f"{serve_url}/{job_id}.jpg"
    video = is_video(q, meta)
    stats = None
    if fields.get("stats"):
        try:
            stats = json.loads(fields["stats"])
            with open(os.path.join(serve_dir, job_id + ext + ".json"), "w", encoding="utf-8") as f:
                json.dump({"job_id": job_id, "splat_url": splat_url, "splat_full_url": full_url, "view": stats.get("view"),
                           "gaussians": stats.get("gaussians"), "gaussians_full": stats.get("gaussians_full"),
                           "object_mode": bool(stats.get("object_mode")), "object_region": stats.get("object_region"),
                           "train_seconds": stats.get("train_seconds"), "test_psnr": stats.get("test_psnr"),
                           "test_psnr_object": stats.get("test_psnr_object"), "worker": stats.get("worker"), "created": now_str(),
                           # 영상 작업 (docs\video3d_contract.md 4절): 축척은 v1 에서 임의
                           "source": ("photos" if is_photos(q, meta) else "video") if video else stats.get("source"), "scale": stats.get("scale"),
                           "frames_used": stats.get("frames_used"), "frames_total": stats.get("frames_total"),
                           "registered": stats.get("registered"), "sfm_seconds": stats.get("sfm_seconds")},
                          f, ensure_ascii=False, indent=2)
        except Exception as e:
            stats = {"parse_error": str(e)}
    summary = None
    if isinstance(stats, dict):
        summary = {k: stats.get(k) for k in ("gaussians", "gaussians_full", "object_mode", "train_seconds", "total_seconds", "test_psnr",
                                             "test_psnr_object", "peak_vram_gb", "iters", "strategy", "cap_max", "keyframes_train",
                                             "worker", "splat_bytes", "splat_full_bytes", "frames_used", "frames_total", "registered",
                                             "sfm_seconds", "extract_seconds", "scale") if k in stats}
    registered, reg_msg, oid = False, "", q.get("objectid")
    try:
        oid = register_splat_url(cfg, q, splat_url)
        registered = True
    except Exception as e:
        reg_msg = str(e)[:300]
    extra = {}
    if isinstance(stats, dict) and stats.get("object_mode"):
        extra["splat_object_region"] = stats.get("object_region")   # 워커가 확정한 영역 (pipeline 의 object_region 은 건드리지 않음)
    if thumb_url:
        extra["splat_thumb_url"] = thumb_url
    done_msg = ("3D 완료 (사진)" if is_photos(q, meta) else "3D 완료 (영상)") if video else "스플랫 완료" + (" (물체 모드)" if extra.get("splat_object_region") else "")
    q = update_queue(qp, splat_status="done", splat_url=splat_url, splat_full_url=full_url, splat_done_at=now_str(), splat_stats=summary,
                     splat_registered=registered, objectid=oid or q.get("objectid"),
                     splat_message=done_msg + ("" if registered else " (scan_points 등록 실패: " + reg_msg + ")"),
                     **extra)
    if bundle_tmp:
        q = accept_bundle(qp, q, meta, bundle_tmp)
    respond({"job_id": job_id, "splat_url": splat_url, "splat_full_url": full_url, "bytes": len(blob), "registered": registered,
             "objectid": oid, "thumb_url": thumb_url, "message": q.get("splat_message"), "trench_post": q.get("trench_post")})


def op_bundle(cfg, job_id):
    """POST ?op=bundle&job_id= 본문 = trench_bundle.zip 그대로. 메모리에 다 올리지 않고 디스크로 바로 쓴다 (최대 1 GB)."""
    qp, q, meta = load_job(cfg, job_id)
    if not q:
        return respond({"error": "없는 작업"}, "404 Not Found")
    if not trench_info(q, meta)[0]:
        return respond({"error": "굴착 기록(trench_mode) 작업이 아닙니다"}, "409 Conflict")
    if q.get("status") != "done":
        return respond({"error": f"처리가 끝난 작업에만 묶음을 올릴 수 있습니다 (status={q.get('status')})"}, "409 Conflict")
    length = int(os.environ.get("CONTENT_LENGTH") or 0)
    if length <= 0:
        return respond({"error": "본문(zip)이 없습니다"}, "400 Bad Request")
    if length > MAX_BUNDLE:
        return respond({"error": "묶음이 너무 큽니다 (최대 1 GB)"}, "413 Payload Too Large")
    tmp = os.path.join(meta.get("job_dir") or cfg["data_root"], f"_bundle_{os.getpid()}.zip.tmp")
    left = length
    with open(tmp, "wb") as f:
        while left > 0:
            chunk = sys.stdin.buffer.read(min(left, 4 * 1024 * 1024))
            if not chunk:
                break
            f.write(chunk)
            left -= len(chunk)
    if left:
        os.remove(tmp)
        return respond({"error": f"본문이 끊겼습니다 ({length - left}/{length} 바이트)"}, "400 Bad Request")
    try:
        names = check_bundle(tmp)
    except ValueError as e:
        os.remove(tmp)
        return respond({"error": str(e)}, "400 Bad Request")
    q = accept_bundle(qp, q, meta, tmp)
    respond({"job_id": job_id, "bytes": length, "files": len(names), "trench_post": q.get("trench_post"),
             "message": q.get("trench_post_message")})


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
    video = is_video(q, meta)
    if video and is_photos(q, meta):
        if len(photo_files(meta)) < MIN_PHOTOS:
            return respond({"error": "사진(photos_dir)이 서버에 없거나 너무 적습니다"}, "409 Conflict")
    elif video:
        if not video_file(meta)[0]:
            return respond({"error": "원본 영상(video_path)이 서버에 없습니다"}, "409 Conflict")
    elif q.get("mode") not in ("stray", "objcap") or not (meta.get("scan_zip") and os.path.exists(meta["scan_zip"])):
        return respond({"error": "원본 zip(Stray 녹화 또는 Object Capture) 이 있는 작업만 스플랫을 만들 수 있습니다"}, "409 Conflict")
    if q.get("splat_status") in ("pending", "processing") and not force:
        return respond(splat_summary(q, meta))
    if video:                                                     # 영상 작업은 물체 모드가 없다
        q = update_queue(qp, splat_status="pending", splat_kind="video", splat_message="3D 생성 대기 (수동 요청)",
                         splat_worker=None, splat_started_at=None)
        return respond(splat_summary(q, meta))
    # 물체 모드 지정: ?object=1[&center=x,y,z][&radius=r] → 큐 파일 object (upload.py 와 같은 꼴). ?object=0 이면 전체 모드로
    p = query_params()
    extra = {}
    if p.get("object") in ("1", "true"):
        center = radius = None
        try:
            if p.get("center"):
                center = [float(t) for t in p["center"].split(",")]
                if len(center) != 3:
                    center = None
            if p.get("radius"):
                radius = float(p["radius"])
        except ValueError:
            center = radius = None
        extra["object"] = {"mode": 1, "center": center, "radius": radius, "coverage": None, "by": "queue"}
    elif p.get("object") in ("0", "false"):
        extra["object"] = None
    q = update_queue(qp, splat_status="pending", splat_message="스플랫 대기 중 (수동 요청" + (", 물체 모드" if extra.get("object") else "") + ")",
                     splat_worker=None, splat_started_at=None, **extra)
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
    if op == "bundle":
        return op_bundle(cfg, job_id)
    respond({"error": "op 는 list|claim|download|upload|bundle|fail|queue|status"}, "400 Bad Request")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        respond({"error": f"서버 오류: {e}"}, "500 Internal Server Error")
