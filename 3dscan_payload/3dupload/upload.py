"""
POST /app/3dupload/upload.py  (multipart/form-data)

  공통 필드 : title (필수), note
  mode=stray: scan_zip (Stray Scanner 녹화 폴더 zip), lon, lat (필수), elev, heading
  mode=legacy (기본): las_file, glb_file (Scaniverse 등에서 내보낸 LAS + GLB)

응답: {"job_id": "..."}  또는 {"error": "..."}
작업 폴더: <data_root>\<job_id>\  (업로드 원본 + job.json)
큐 파일  : <jobs_dir>\<job_id>.json  (status: pending → 러너가 처리)
"""
import json
import os
import sys
import time
import uuid
import warnings

import msvcrt

warnings.filterwarnings("ignore", category=DeprecationWarning)
import cgi  # noqa: E402  (3.11 에서 사용 가능; 3.13 에서 제거 예정)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # python -I 에서도 common.py 를 찾도록
from common import load_config, respond  # noqa: E402

msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)

MAX_TITLE = 100
ALLOWED = {"scan_zip": (".zip",), "las_file": (".las", ".laz"), "glb_file": (".glb", ".gltf")}


def save_upload(field, job_dir, name):
    if field is None or not getattr(field, "filename", None):
        return None
    ext = os.path.splitext(field.filename)[1].lower()
    if ext not in ALLOWED[name]:
        raise ValueError(f"{name}: 허용되지 않는 확장자 {ext}")
    dest = os.path.join(job_dir, name + ext)
    with open(dest, "wb") as out:
        while True:
            chunk = field.file.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
    return dest


def main():
    if os.environ.get("REQUEST_METHOD", "GET") != "POST":
        return respond({"error": "POST only"}, "405 Method Not Allowed")
    cfg = load_config()
    form = cgi.FieldStorage(fp=sys.stdin.buffer, environ=os.environ, keep_blank_values=True)

    title = (form.getfirst("title") or "").strip()
    if not title:
        return respond({"error": "제목을 입력해 주세요"}, "400 Bad Request")
    title = title[:MAX_TITLE]
    note = (form.getfirst("note") or "").strip()[:500]
    mode = (form.getfirst("mode") or "legacy").strip().lower()
    if mode not in ("stray", "legacy"):
        return respond({"error": "mode는 stray 또는 legacy"}, "400 Bad Request")

    job_id = uuid.uuid4().hex[:8]
    job_dir = os.path.join(cfg["data_root"], job_id)
    os.makedirs(job_dir, exist_ok=True)
    os.makedirs(cfg["jobs_dir"], exist_ok=True)

    meta = {
        "job_id": job_id, "title": title, "note": note, "mode": mode, "job_dir": job_dir,
        "author": cfg.get("portal_user", ""), "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    try:
        if mode == "stray":
            lon, lat = form.getfirst("lon"), form.getfirst("lat")
            if not lon or not lat:
                raise ValueError("스캔 위치(lon, lat)가 필요합니다. 지도에서 위치를 찍어 주세요")
            meta["georef"] = {
                "lon": float(lon), "lat": float(lat),
                "elev": float(form.getfirst("elev") or cfg.get("default_elev", 0.0)),
                "heading": float(form.getfirst("heading") or 0.0),
            }
            meta["scan_zip"] = save_upload(form["scan_zip"] if "scan_zip" in form else None, job_dir, "scan_zip")
            if not meta["scan_zip"]:
                raise ValueError("Stray Scanner zip 파일을 선택해 주세요")
        else:
            meta["las_path"] = save_upload(form["las_file"] if "las_file" in form else None, job_dir, "las_file")
            meta["glb_path"] = save_upload(form["glb_file"] if "glb_file" in form else None, job_dir, "glb_file")
            if not meta["las_path"] or not meta["glb_path"]:
                raise ValueError("LAS와 GLB 파일을 모두 선택해 주세요")
    except ValueError as e:
        return respond({"error": str(e)}, "400 Bad Request")

    with open(os.path.join(job_dir, "job.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    queue = {"job_id": job_id, "title": title, "job_dir": job_dir, "mode": mode,
             "status": "pending", "step": 0, "message": "대기 중", "created_at": meta["created_at"]}
    with open(os.path.join(cfg["jobs_dir"], job_id + ".json"), "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)
    respond({"job_id": job_id, "mode": mode})


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # never let IIS return a bare 502
        respond({"error": f"서버 오류: {e}"}, "500 Internal Server Error")
