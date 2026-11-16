r"""
끊겨도 이어 올리기 — 청크 업로드 (2026-11-16)

휴대폰에서 큰 촬영(영상·VR 투어 zip)을 한 번에 올리면 신호가 약할 때 처음부터 다시 올려야 했다(요청 하나, IIS 600초 제한).
이제 파일을 5 MB 조각으로 나눠 올리고, 끊기면 받은 조각은 두고 빠진 조각만 다시 보낸다. 다 올라가면 upload.py 에
chunked_files={필드: upload_id | [upload_id, ...]} 로 알려 주면 서버가 조각을 이어 붙여 예전과 똑같이 처리한다.

  POST upload_chunk.py?op=init            본문 JSON {filename, size, field, mime} → {upload_id, chunk_size, n_chunks}
  POST upload_chunk.py?op=chunk&upload_id=..&index=N   본문 = 조각 바이트 (마지막 조각 말고는 정확히 chunk_size)
  GET  upload_chunk.py?op=status&upload_id=..          → {received: [...], size, chunk_size, n_chunks, complete}

임시 폴더: <data_root>\uploads_tmp\<upload_id>\ (meta.json + part_00000 …). init 때마다 72시간 넘은 폴더를 지운다.
제한: 파일 1 GB, 조각 16 MB 이하, upload_id 는 secrets.token_urlsafe(18) 24자, index 는 0 ≤ index < n_chunks.
표준 라이브러리만 사용 (Python 3.14, python -I).
"""
import json
import os
import re
import secrets
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # python -I 에서도 common.py 를 찾도록
from common import load_config, query_params, respond  # noqa: E402

CHUNK_SIZE = 5 * 1024 * 1024            # 5 MB: 느린 LTE 에서도 한 조각이 IIS 실행 제한(600초) 안에 끝난다
MAX_CHUNK = 16 * 1024 * 1024
MAX_FILE = 1024 * 1024 * 1024            # upload.py 와 같은 1 GB
MAX_AGE_SEC = 72 * 3600
MAX_TMP_TOTAL = 30 * 1024 * 1024 * 1024  # 임시 폴더 전체 30 GB 넘으면 새로 받지 않는다 (디스크 보호)
FIELDS = ("scan_zip", "video_file", "photo_files", "pano_file", "las_file", "glb_file", "sensors_file", "marks_file")
ID_RE = re.compile(r"^[A-Za-z0-9_-]{24}$")


def chunk_size(cfg):
    """조각 크기: 기본 5 MB. 설정 upload_chunk_kb 로 바꿀 수 있다 (256 KB ~ 16 MB, 로컬 시험은 작게)"""
    try:
        kb = int(cfg.get("upload_chunk_kb") or 0)
    except (TypeError, ValueError):
        kb = 0
    return max(256 * 1024, min(MAX_CHUNK, kb * 1024)) if kb else CHUNK_SIZE


def tmp_root(cfg):
    return os.path.join(cfg["data_root"], "uploads_tmp")


def upload_dir(cfg, upload_id):
    """검사한 upload_id → 임시 폴더 경로. 형식이 틀리면 None (경로 조작 차단)"""
    if not upload_id or not ID_RE.match(upload_id):
        return None
    return os.path.join(tmp_root(cfg), upload_id)


def load_meta(d):
    try:
        with open(os.path.join(d, "meta.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def part_name(i):
    return f"part_{i:05d}"


def received(d, n):
    out = []
    for i in range(n):
        if os.path.exists(os.path.join(d, part_name(i))):
            out.append(i)
    return out


def expected_len(meta, i):
    n, cs, size = meta["n_chunks"], meta["chunk_size"], meta["size"]
    return size - cs * (n - 1) if i == n - 1 else cs


def cleanup_old(root):
    """72시간 넘은 임시 폴더를 지우고 남은 전체 크기를 돌려준다"""
    total, now = 0, time.time()
    try:
        names = os.listdir(root)
    except OSError:
        return 0
    for n in names:
        p = os.path.join(root, n)
        if not os.path.isdir(p) or not ID_RE.match(n):
            continue
        try:
            age = now - os.path.getmtime(p)
            if age > MAX_AGE_SEC:
                shutil.rmtree(p, ignore_errors=True)
                continue
            for f in os.listdir(p):
                try:
                    total += os.path.getsize(os.path.join(p, f))
                except OSError:
                    pass
        except OSError:
            pass
    return total


def read_body(limit):
    length = int(os.environ.get("CONTENT_LENGTH") or 0)
    if length < 0 or length > limit:
        raise ValueError("본문 크기가 허용 범위를 넘습니다")
    data = sys.stdin.buffer.read(length) if length else b""
    if len(data) != length:
        raise ValueError("본문을 끝까지 받지 못했습니다 (연결이 끊김)")
    return data


def op_init(cfg):
    try:
        body = json.loads(read_body(64 * 1024).decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return respond({"error": "init 본문은 JSON 이어야 합니다"}, "400 Bad Request")
    if not isinstance(body, dict):
        return respond({"error": "init 본문은 JSON 객체여야 합니다"}, "400 Bad Request")
    field = str(body.get("field") or "")
    if field not in FIELDS:
        return respond({"error": f"field 는 {', '.join(FIELDS)} 중 하나"}, "400 Bad Request")
    try:
        size = int(body.get("size"))
    except (TypeError, ValueError):
        return respond({"error": "size 는 숫자여야 합니다"}, "400 Bad Request")
    if size <= 0:
        return respond({"error": "빈 파일은 올릴 수 없습니다"}, "400 Bad Request")
    if size > MAX_FILE:
        return respond({"error": "파일이 너무 큽니다 (최대 1 GB)"}, "400 Bad Request")
    filename = os.path.basename(str(body.get("filename") or "upload.bin").replace("\\", "/"))
    filename = "".join(ch for ch in filename if ch.isprintable() and ch not in '<>:"/\\|?*')[:120] or "upload.bin"
    mime = str(body.get("mime") or "")[:80]
    root = tmp_root(cfg)
    os.makedirs(root, exist_ok=True)
    if cleanup_old(root) + size > MAX_TMP_TOTAL:
        return respond({"error": "서버 임시 공간이 부족합니다. 잠시 뒤 다시 올려 주세요"}, "507 Insufficient Storage")
    upload_id = secrets.token_urlsafe(18)
    d = os.path.join(root, upload_id)
    os.makedirs(d)
    cs = chunk_size(cfg)
    n = (size + cs - 1) // cs
    meta = {"upload_id": upload_id, "filename": filename, "field": field, "mime": mime, "size": size,
            "chunk_size": cs, "n_chunks": n, "created_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)
    respond({"upload_id": upload_id, "chunk_size": cs, "n_chunks": n})


def bad_id(p):
    """형식이 틀린 upload_id (경로 조작 시도 포함) → 400 응답을 보내고 True"""
    if not ID_RE.match(p.get("upload_id") or ""):
        respond({"error": "upload_id 형식이 맞지 않습니다"}, "400 Bad Request")
        return True
    return False


def op_chunk(cfg, p):
    if bad_id(p):
        return None
    d = upload_dir(cfg, p.get("upload_id"))
    meta = load_meta(d) if d else None
    if not meta:
        return respond({"error": "upload_id 가 없거나 만료되었습니다. 처음부터 다시 올립니다"}, "404 Not Found")
    try:
        i = int(p.get("index", ""))
    except ValueError:
        return respond({"error": "index 는 숫자여야 합니다"}, "400 Bad Request")
    if not 0 <= i < meta["n_chunks"]:
        return respond({"error": f"index 는 0~{meta['n_chunks'] - 1}"}, "400 Bad Request")
    want = expected_len(meta, i)
    try:
        data = read_body(MAX_CHUNK)
    except ValueError as e:
        return respond({"error": str(e)}, "400 Bad Request")
    if len(data) != want:
        return respond({"error": f"조각 {i} 크기가 맞지 않습니다 ({len(data)} ≠ {want})"}, "400 Bad Request")
    dest = os.path.join(d, part_name(i))
    tmp = dest + f".{secrets.token_hex(4)}.tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, dest)                   # 같은 조각을 다시 보내도 결과는 같다 (멱등)
    try:
        os.utime(d, None)                   # 올리는 중인 폴더는 72시간 정리에서 살린다
    except OSError:
        pass
    respond({"ok": True, "index": i, "received": len(received(d, meta["n_chunks"])), "n_chunks": meta["n_chunks"]})


def op_status(cfg, p):
    if bad_id(p):
        return None
    d = upload_dir(cfg, p.get("upload_id"))
    meta = load_meta(d) if d else None
    if not meta:
        return respond({"error": "upload_id 가 없거나 만료되었습니다"}, "404 Not Found")
    got = received(d, meta["n_chunks"])
    respond({"upload_id": meta["upload_id"], "received": got, "size": meta["size"], "chunk_size": meta["chunk_size"],
             "n_chunks": meta["n_chunks"], "complete": len(got) == meta["n_chunks"]})


def main():
    cfg = load_config()
    p = query_params()
    op = (p.get("op") or "").lower()
    method = os.environ.get("REQUEST_METHOD", "GET")
    if op == "status":
        return op_status(cfg, p)
    if method != "POST":
        return respond({"error": "POST only"}, "405 Method Not Allowed")
    if op == "init":
        return op_init(cfg)
    if op == "chunk":
        return op_chunk(cfg, p)
    respond({"error": "op 는 init|chunk|status"}, "400 Bad Request")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # IIS 가 맨 502 를 내지 않게
        respond({"error": f"서버 오류: {e}"}, "500 Internal Server Error")
