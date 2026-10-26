"""
POST /app/3dupload/upload.py  (multipart/form-data)

  공통 필드 : title (필수), note, scan_type (home=홈스캔 | survey=현장조사, 기본 home)
  mode=stray: scan_zip (Stray Scanner 녹화 폴더 zip), lon, lat (필수), elev, heading
  mode=legacy (기본): las_file, glb_file (Scaniverse 등에서 내보낸 LAS + GLB)

응답: {"job_id": "..."}  또는 {"error": "..."}
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

import msvcrt

msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # python -I 에서도 common.py 를 찾도록
from common import load_config, respond  # noqa: E402

MAX_TITLE = 100
MAX_BODY = 1024 * 1024 * 1024  # 1 GB (web.config 의 maxAllowedContentLength 와 맞춤)
ALLOWED = {"scan_zip": (".zip",), "las_file": (".las", ".laz"), "glb_file": (".glb", ".gltf")}


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
            files[name] = (filename, payload)
        else:
            fields[name] = payload.decode("utf-8", "replace").strip()
    return fields, files


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
    if mode not in ("stray", "legacy"):
        return respond({"error": "mode는 stray 또는 legacy"}, "400 Bad Request")
    scan_type = (fields.get("scan_type") or "home").lower()
    if scan_type not in ("home", "survey"):
        return respond({"error": "scan_type은 home 또는 survey"}, "400 Bad Request")

    job_id = uuid.uuid4().hex[:8]
    job_dir = os.path.join(cfg["data_root"], job_id)
    os.makedirs(job_dir, exist_ok=True)
    os.makedirs(cfg["jobs_dir"], exist_ok=True)

    meta = {
        "job_id": job_id, "title": title, "note": note, "mode": mode, "scan_type": scan_type, "job_dir": job_dir,
        "author": cfg.get("portal_user", ""), "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    try:
        if mode == "stray":
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
                raise ValueError("Stray Scanner zip 파일을 선택해 주세요")
        else:
            meta["las_path"] = save_upload(files.get("las_file"), job_dir, "las_file")
            meta["glb_path"] = save_upload(files.get("glb_file"), job_dir, "glb_file")
            if not meta["las_path"] or not meta["glb_path"]:
                raise ValueError("LAS와 GLB 파일을 모두 선택해 주세요")
    except ValueError as e:
        return respond({"error": str(e)}, "400 Bad Request")

    with open(os.path.join(job_dir, "job.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    queue = {"job_id": job_id, "title": title, "job_dir": job_dir, "mode": mode, "scan_type": scan_type,
             "status": "pending", "step": 0, "message": "대기 중", "created_at": meta["created_at"]}
    with open(os.path.join(cfg["jobs_dir"], job_id + ".json"), "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)
    respond({"job_id": job_id, "mode": mode, "scan_type": scan_type})


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # never let IIS return a bare 502
        respond({"error": f"서버 오류: {e}"}, "500 Internal Server Error")
