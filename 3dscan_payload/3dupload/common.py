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


# 사진 3D 고화질 (2026-11-17 사용자: "옵션을 켜야만 이 모드로, 켜면 노트북에서 한 시간 작업한다고 안내")
# 기본은 빠른 설정(약 6분). 기록 주인이 edit.py op=splat_hq 로 고르면 GPU 워커가 방 전용 설정(원본 해상도·2만 회·
# 100만 점·자세 보정·LiDAR 깊이, 노트북 RTX 4060 에서 약 1시간)으로 다시 만든다. 큐 splat_hq = requested|done|failed
SPLAT_HQ_MINUTES = 60
SPLAT_HQ_WAIT_MSG = "고화질 사진 3D 대기 중 (노트북 GPU, 약 1시간)"
SPLAT_HQ_RUN_MSG = "고화질 사진 3D 만드는 중 (노트북 GPU, 약 1시간)"


def splat_hq_block(q, meta):
    """고화질로 만들 수 없으면 사용자에게 보일 이유, 만들 수 있으면 None. LiDAR(stray) 방·현장 기록만 (물체·영상·사진·VR 제외)"""
    mode = q.get("mode") or meta.get("mode")
    obj = q.get("object") or meta.get("object")
    if mode != "stray" or (isinstance(obj, dict) and obj.get("mode", 1)):
        return "LiDAR로 찍은 방·현장 기록만 고화질로 만들 수 있어요"
    if q.get("status") != "done":
        return "기록 처리가 끝난 뒤에 고를 수 있어요"
    z = meta.get("scan_zip")
    if not (z and os.path.exists(z)):
        return "원본 스캔 파일이 서버에 없어 다시 만들 수 없어요"
    return None
