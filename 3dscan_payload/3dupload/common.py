"""Shared helpers for the kgeoScan upload CGI scripts (IIS, Python CGI)."""
import hashlib
import hmac
import json
import os
import secrets
import sys

CONFIG_PATH = os.environ.get("KGEOSCAN_CONFIG", r"D:\kgeoHub\config\kgeoscan.json")


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def respond(obj, status="200 OK"):
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    out = sys.stdout.buffer
    out.write(f"Status: {status}\r\n".encode("ascii"))
    out.write(b"Content-Type: application/json; charset=utf-8\r\n")
    out.write(b"Cache-Control: no-store\r\n")
    out.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii"))
    out.write(body)
    out.flush()


def query_params():
    from urllib.parse import parse_qs
    return {k: v[0] for k, v in parse_qs(os.environ.get("QUERY_STRING", "")).items()}


def safe_job_id(value):
    value = (value or "").strip()
    if len(value) != 8 or any(c not in "0123456789abcdef" for c in value):
        return None
    return value


# ── 공개 범위·관리 키 (docs/share_contract.md 1·2절, 2026-11-12) ──
VISIBILITIES = ("public", "link", "private")


def job_visibility(d):
    """큐·job.json 의 공개 범위. 필드가 없는 예전 작업은 public (지금까지처럼 지도에 나온다)"""
    v = (d or {}).get("visibility")
    return v if v in VISIBILITIES else "public"


def new_edit_key():
    """관리 키 원문 (24자). 업로드 응답으로 한 번만 나가고 서버에는 해시만 남긴다"""
    return secrets.token_urlsafe(18)


def hash_edit_key(key):
    return hashlib.sha256((key or "").strip().encode("utf-8")).hexdigest()


def check_edit_key(meta, key):
    """job.json 의 edit_key_sha256 와 비교 (상수 시간). 해시가 없는 예전 작업은 늘 False"""
    h = (meta or {}).get("edit_key_sha256")
    if not h or not key:
        return False
    return hmac.compare_digest(str(h), hash_edit_key(key))


def read_edit_key(body=None):
    """관리 키: 헤더 X-Edit-Key → JSON 본문 edit_key → 쿼리 key 순서"""
    k = os.environ.get("HTTP_X_EDIT_KEY") or ""
    if not k and isinstance(body, dict):
        k = str(body.get("edit_key") or "")
    if not k:
        k = query_params().get("key") or ""
    return k.strip()[:100]


def load_job_files(cfg, job_id):
    """(queue_path, queue, meta_path, meta). 없으면 (None, None, None, None)"""
    qp = os.path.join(cfg["jobs_dir"], job_id + ".json")
    if not os.path.exists(qp):
        return None, None, None, None
    with open(qp, "r", encoding="utf-8") as f:
        q = json.load(f)
    mp = os.path.join(q.get("job_dir") or os.path.join(cfg["data_root"], job_id), "job.json")
    meta = {}
    if os.path.exists(mp):
        with open(mp, "r", encoding="utf-8") as f:
            meta = json.load(f)
    return qp, q, mp, meta


def write_json_atomic(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
