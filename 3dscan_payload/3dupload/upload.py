r"""
POST /app/3dupload/upload.py  (multipart/form-data)

  공통 필드 : title (필수), note, scan_type (home=홈스캔 | survey=현장조사, 기본 home), splat (1 이면 유형과 무관하게 GPU 스플랫 요청)
  물체 모드 : object_mode=1, obj_center="x,y,z"(ARKit 월드 = odometry.csv 좌표, m; 없으면 서버가 카메라 시선 교점으로 자동),
             obj_radius (m), obj_coverage (촬영 방위 커버리지 %) → 메시·스플랫을 물체 영역으로 자른다
  mode=stray: scan_zip (Stray Scanner 녹화 폴더 zip), lon, lat (필수), elev, heading
  mode=legacy (기본): las_file, glb_file (Scaniverse 등에서 내보낸 LAS + GLB)
  굴착 기록: trench_mode=1 (+ scan_type=survey). 웹 촬영(mode=video|photos)은 docs/web_trench_contract.md 1절:
             sensors_file (sensors.json ≤5 MB), marks_file (marks2d.json ≤1 MB) — 둘 다 선택, JSON 이어야 한다
  굴착 허가 정보(모든 모드, 선택): permit_no, owner_org, surveyor, org (각 100자) → job.json permit → 조서

응답: {"job_id": "..."}  또는 {"error": "..."}
중복 방지: 같은 제목·같은 원본 파일 이름으로 24시간 안에 만든 작업(실패 제외)이 있으면 새로 만들지 않고 그 job_id 를 돌려준다
          (앱의 백그라운드 전송이 재시도돼 같은 녹화가 여러 번 올라오는 경우).
작업 폴더: <data_root>\<job_id>\  (업로드 원본 + job.json)
큐 파일  : <jobs_dir>\<job_id>.json  (status: pending → 러너가 처리)

표준 라이브러리만 사용한다 (cgi 모듈은 Python 3.13 에서 제거됨 → email 파서로 multipart 처리).
"""
import email
import email.policy
import json
import os
import sys
import time
import uuid

# msvcrt.setmode 는 쓰지 않는다: 파이썬은 Windows 에서 표준 입출력을 이미 바이너리로 연다(확인함).
# IIS 에서 HTTP/2 요청일 때 stdin/stdout 에 setmode 를 부르면 응답이 끊기고(RST), GET 에서는 502 가 났다.

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # python -I 에서도 common.py 를 찾도록
from common import load_config, respond  # noqa: E402

MAX_TITLE = 100
MAX_BODY = 1024 * 1024 * 1024  # 1 GB (web.config 의 maxAllowedContentLength 와 맞춤)
ALLOWED = {"scan_zip": (".zip",), "las_file": (".las", ".laz"), "glb_file": (".glb", ".gltf"),
           "video_file": (".mp4", ".mov", ".m4v", ".webm", ".3gp"),   # video: 웹 3D 현장조사 (기본 카메라 영상 → GPU 스플랫)
           "photo_files": (".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp")}   # photos: 같은 현장조사의 사진 여러 장 (화질 권장)
MIN_PHOTOS, MAX_PHOTOS = 10, 300
# 웹 굴착 기록 부속 파일 (docs/web_trench_contract.md 1절): 필드 이름 → (저장 이름, 최대 바이트)
TRENCH_FILES = {"sensors_file": ("sensors.json", 5 * 1024 * 1024), "marks_file": ("marks2d.json", 1024 * 1024)}
PERMIT_FIELDS = ("permit_no", "owner_org", "surveyor", "org")
MAX_PERMIT = 100


def clean_text(value, limit):
    """제어 문자(줄바꿈 포함)를 빼고 앞뒤 공백을 지운 뒤 limit 자로 자른다"""
    s = "".join(ch for ch in (value or "") if ch.isprintable())
    return s.strip()[:limit]


def parse_permit(fields):
    """굴착 허가·작업자 정보 → dict (값이 있는 것만) 또는 None"""
    p = {k: clean_text(fields.get(k), MAX_PERMIT) for k in PERMIT_FIELDS}
    p = {k: v for k, v in p.items() if v}
    return p or None


def save_trench_json(item, job_dir, field):
    """웹 굴착 기록 부속 JSON (sensors.json / marks2d.json) 저장 → 경로 또는 None. 크기·JSON 형식이 틀리면 ValueError"""
    if not item or not item[1]:
        return None
    name, limit = TRENCH_FILES[field]
    payload = item[1]
    if len(payload) > limit:
        raise ValueError(f"{field}: 파일이 너무 큽니다 (최대 {limit // (1024 * 1024)} MB)")
    try:
        data = json.loads(payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError):
        raise ValueError(f"{field}: JSON 형식이 아닙니다")
    if not isinstance(data, dict):
        raise ValueError(f"{field}: JSON 객체여야 합니다")
    if field == "marks_file" and not isinstance(data.get("marks", []), list):
        raise ValueError("marks_file: marks 는 배열이어야 합니다")
    dest = os.path.join(job_dir, name)
    with open(dest, "wb") as out:
        out.write(payload)
    return dest


def parse_multipart():
    """stdin 의 multipart/form-data → (fields: {name: str}, files: {name: (filename, bytes)})"""
    ctype = os.environ.get("CONTENT_TYPE", "")
    length = int(os.environ.get("CONTENT_LENGTH") or 0)
    if not ctype.lower().startswith("multipart/form-data") or length <= 0:
        raise ValueError("multipart/form-data 요청이 아닙니다")
    if length > MAX_BODY:
        raise ValueError("업로드 크기 초과 (최대 1 GB)")
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
            files.setdefault(name, (filename, payload))        # 같은 이름이 여러 개면 첫 파일 (기존 호출 그대로)
            files.setdefault(name + "*", []).append((filename, payload))   # 전부 (사진 모드 photo_files)
        else:
            fields[name] = payload.decode("utf-8", "replace").strip()
    return fields, files


def find_recent_duplicate(cfg, title, mode, source_name, client_id="", max_age_sec=86400):
    """같은 녹화를 다시 올린 것이면 기존 큐 항목을 돌려준다 (실패한 작업은 제외).
    판정: 앱이 보낸 client_id(녹화마다 고유)가 같거나, 같은 제목·모드·원본 파일 이름"""
    if not source_name and not client_id:
        return None
    jobs_dir = cfg["jobs_dir"]
    now = time.time()
    try:
        names = os.listdir(jobs_dir)
    except OSError:
        return None
    best = None
    for n in names:
        if not n.endswith(".json"):
            continue
        p = os.path.join(jobs_dir, n)
        try:
            if now - os.path.getmtime(p) > max_age_sec:
                continue
            with open(p, "r", encoding="utf-8") as f:
                q = json.load(f)
        except Exception:
            continue
        if q.get("status") == "failed":
            continue
        same_client = bool(client_id) and q.get("client_id") == client_id
        same_file = bool(source_name) and q.get("title") == title and q.get("mode") == mode and q.get("source_name") == source_name
        if same_client or same_file:
            if best is None or (q.get("created_at") or "") > (best.get("created_at") or ""):
                best = q
    return best


def parse_object_fields(fields):
    """object_mode=1 이면 {mode, center|None, radius|None, coverage|None}, 아니면 None. 잘못된 값은 None 으로 (자동 계산)"""
    if (fields.get("object_mode") or "").strip().lower() not in ("1", "true", "yes", "on"):
        return None
    center = None
    try:
        v = [float(t) for t in (fields.get("obj_center") or "").replace(" ", "").split(",") if t != ""]
        if len(v) == 3 and all(abs(t) < 10000 for t in v):
            center = [round(t, 4) for t in v]
    except ValueError:
        center = None
    def num(name, lo, hi):
        try:
            x = float(fields.get(name) or "")
            return round(x, 4) if lo <= x <= hi else None
        except ValueError:
            return None
    return {"mode": 1, "center": center, "radius": num("obj_radius", 0.03, 3.0), "coverage": num("obj_coverage", 0, 100)}


def save_upload(item, job_dir, name):
    if not item:
        return None
    filename, payload = item
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED[name]:
        raise ValueError(f"{name}: 허용되지 않는 확장자 {ext}")
    if not payload:
        raise ValueError(f"{name}: 빈 파일")
    dest = os.path.join(job_dir, name + ext)
    with open(dest, "wb") as out:
        out.write(payload)
    return dest


def main():
    if os.environ.get("REQUEST_METHOD", "GET") != "POST":
        return respond({"error": "POST only"}, "405 Method Not Allowed")
    cfg = load_config()
    try:
        fields, files = parse_multipart()
    except ValueError as e:
        return respond({"error": str(e)}, "400 Bad Request")

    title = (fields.get("title") or "")[:MAX_TITLE]
    if not title:
        return respond({"error": "제목을 입력해 주세요"}, "400 Bad Request")
    note = (fields.get("note") or "")[:500]
    mode = (fields.get("mode") or "legacy").lower()
    if mode not in ("stray", "legacy", "objcap", "video", "photos"):
        return respond({"error": "mode는 stray, objcap, video, photos 또는 legacy"}, "400 Bad Request")
    web3d = mode in ("video", "photos")                  # 웹 3D 현장조사 (기본 카메라, LiDAR 없음)
    scan_type = (fields.get("scan_type") or ("survey" if web3d else "home")).lower()
    if scan_type not in ("home", "survey"):
        return respond({"error": "scan_type은 home 또는 survey"}, "400 Bad Request")
    splat_requested = web3d or (fields.get("splat") or "").lower() in ("1", "true", "yes", "on")
    obj = parse_object_fields(fields)
    area = None
    if (fields.get("area_mode") or "").strip().lower() in ("1", "true", "yes", "on"):
        surf = (fields.get("area_surface") or "auto").strip().lower()
        area = {"mode": 1, "surface": surf if surf in ("auto", "floor", "wall") else "auto"}
    # 굴착 기록: 드러난 배관·케이블 → 서버가 관 자동 추출 (docs/utility_contract.md). 위에서 본 정사영상·깊이 지도도 같이 만든다
    trench = None
    if (fields.get("trench_mode") or "").strip().lower() in ("1", "true", "yes", "on"):
        trench = {"mode": 1}
        if web3d:
            trench["source"] = "web"              # 웹 촬영: GPU 워커가 실측 묶음을 돌려준 뒤 굴착 후처리 (web_trench_contract.md)
        else:
            area = area or {"mode": 1, "surface": "floor"}   # LiDAR 녹화만: 위에서 본 정사영상·깊이 지도
    permit = parse_permit(fields)

    # 관리 대상(장소): site_id 가 있으면 그 장소, 없고 site_name 만 있으면(앱이 오프라인에서 고른 새 장소) 여기서 만든다
    site_id = None
    try:
        from sites import safe_site_id, sites_dir
        sid = safe_site_id(fields.get("site_id"))
        if sid and os.path.exists(os.path.join(sites_dir(cfg), sid + ".json")):
            site_id = sid
        elif not sid and (fields.get("site_name") or "").strip():
            def _num(v, lo, hi):
                try:
                    x = float(v)
                    return x if lo <= x <= hi else None
                except (TypeError, ValueError):
                    return None
            s_ = {"site_id": "s_" + uuid.uuid4().hex[:8], "name": fields["site_name"].strip()[:60],
                  "lat": _num(fields.get("lat"), -90, 90), "lon": _num(fields.get("lon"), -180, 180), "note": "",
                  "created_at": time.strftime("%Y-%m-%d %H:%M:%S"), "marker_ids": [], "scans": []}
            sp = os.path.join(sites_dir(cfg), s_["site_id"] + ".json")
            with open(sp, "w", encoding="utf-8") as f:
                json.dump(s_, f, ensure_ascii=False, indent=2)
            site_id = s_["site_id"]
    except Exception:
        site_id = None                                     # 장소 연결은 부가 기능 — 업로드는 막지 않는다

    source_name = (files.get("scan_zip") or files.get("video_file") or files.get("photo_files") or files.get("las_file") or ("", b""))[0] or ""
    if mode == "photos":                                   # 사진 모드: 첫 파일 이름 + 장수로 중복 판정
        source_name = f"{source_name}+{len(files.get('photo_files*', []))}"
    client_id = (fields.get("client_id") or "")[:64]
    dup = find_recent_duplicate(cfg, title, mode, source_name, client_id)
    if dup:
        return respond({"job_id": dup["job_id"], "mode": mode, "scan_type": dup.get("scan_type", scan_type), "duplicate": True})

    job_id = uuid.uuid4().hex[:8]
    job_dir = os.path.join(cfg["data_root"], job_id)
    os.makedirs(job_dir, exist_ok=True)
    os.makedirs(cfg["jobs_dir"], exist_ok=True)

    meta = {
        "job_id": job_id, "title": title, "note": note, "mode": mode, "scan_type": scan_type, "job_dir": job_dir,
        "author": cfg.get("portal_user", ""), "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "splat_requested": splat_requested, "object": obj, "area": area, "site_id": site_id, "trench": trench,
        "permit": permit,
    }
    try:
        if trench and web3d:                  # 웹 굴착 기록 부속 파일 (선택)
            trench["sensors_path"] = save_trench_json(files.get("sensors_file"), job_dir, "sensors_file")
            trench["marks2d_path"] = save_trench_json(files.get("marks_file"), job_dir, "marks_file")
        if web3d:                            # 웹 3D 현장조사: 영상 하나 또는 사진 여러 장 (LiDAR·포즈 없음) → GPU 워커가 SfM + 스플랫
            lon, lat = fields.get("lon"), fields.get("lat")
            if not lon or not lat:
                raise ValueError("촬영 위치(lon, lat)가 필요합니다. 위치 권한을 허용하거나 좌표를 입력해 주세요")
            meta["georef"] = {
                "lon": float(lon), "lat": float(lat),
                "elev": float(fields.get("elev") or cfg.get("default_elev", 0.0)),
                "heading": float(fields.get("heading") or 0.0),
            }
            if mode == "video":
                meta["video_path"] = save_upload(files.get("video_file"), job_dir, "video_file")
                if not meta["video_path"]:
                    raise ValueError("영상 파일을 선택해 주세요")
            else:
                photos = files.get("photo_files*") or []
                if len(photos) < MIN_PHOTOS:
                    raise ValueError(f"사진이 {len(photos)}장입니다. 3D 를 만들려면 {MIN_PHOTOS}장 이상(권장 40~80장) 필요합니다")
                if len(photos) > MAX_PHOTOS:
                    raise ValueError(f"사진은 최대 {MAX_PHOTOS}장까지 올릴 수 있습니다 ({len(photos)}장)")
                pdir = os.path.join(job_dir, "photos")
                os.makedirs(pdir, exist_ok=True)
                for i, (fn, payload) in enumerate(photos, 1):
                    ext = os.path.splitext(fn)[1].lower()
                    if ext not in ALLOWED["photo_files"]:
                        raise ValueError(f"사진 형식이 아닙니다: {fn}")
                    if not payload:
                        raise ValueError(f"빈 사진 파일: {fn}")
                    with open(os.path.join(pdir, f"{i:04d}{ext}"), "wb") as out:
                        out.write(payload)
                meta["photos_dir"], meta["photo_count"] = pdir, len(photos)
        elif mode in ("stray", "objcap"):    # objcap: Apple Object Capture zip (model/ OBJ + images/ + poses.json)
            lon, lat = fields.get("lon"), fields.get("lat")
            if not lon or not lat:
                raise ValueError("스캔 위치(lon, lat)가 필요합니다. 지도에서 위치를 찍어 주세요")
            meta["georef"] = {
                "lon": float(lon), "lat": float(lat),
                "elev": float(fields.get("elev") or cfg.get("default_elev", 0.0)),
                "heading": float(fields.get("heading") or 0.0),
            }
            meta["scan_zip"] = save_upload(files.get("scan_zip"), job_dir, "scan_zip")
            if not meta["scan_zip"]:
                raise ValueError("녹화 zip 파일을 선택해 주세요")
        else:
            meta["las_path"] = save_upload(files.get("las_file"), job_dir, "las_file")
            meta["glb_path"] = save_upload(files.get("glb_file"), job_dir, "glb_file")
            if not meta["las_path"] or not meta["glb_path"]:
                raise ValueError("LAS와 GLB 파일을 모두 선택해 주세요")
    except ValueError as e:
        return respond({"error": str(e)}, "400 Bad Request")

    with open(os.path.join(job_dir, "job.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    # 큐 파일은 status.py 로 공개되므로 서버 경로는 빼고 있음/없음만 둔다
    q_trench = None
    if trench:
        q_trench = {k: v for k, v in trench.items() if not k.endswith("_path")}
        if web3d:
            q_trench.update(sensors=bool(trench.get("sensors_path")), marks2d=bool(trench.get("marks2d_path")))
    queue = {"job_id": job_id, "title": title, "job_dir": job_dir, "mode": mode, "scan_type": scan_type,
             "source_name": source_name, "client_id": client_id, "app": (fields.get("app") or "")[:60],
             "splat_requested": splat_requested, "object": obj, "area": area, "site_id": site_id, "trench": q_trench,
             "status": "pending", "step": 0, "message": "대기 중", "created_at": meta["created_at"]}
    with open(os.path.join(cfg["jobs_dir"], job_id + ".json"), "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)
    respond({"job_id": job_id, "mode": mode, "scan_type": scan_type, "object_mode": bool(obj), "site_id": site_id,
             "trench": q_trench, "permit": bool(permit)})


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # never let IIS return a bare 502
        respond({"error": f"서버 오류: {e}"}, "500 Internal Server Error")
