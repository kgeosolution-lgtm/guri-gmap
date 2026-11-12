"""POST /app/3dupload/edit.py  (JSON) — 올린 사람이 관리 키로 기록을 고친다 (docs/share_contract.md 2·3절)

  헤더 X-Edit-Key: <관리 키>  (또는 본문 edit_key)
  {"op": "visibility", "job_id": "xxxxxxxx", "visibility": "public|link|private"}
      → {ok, job_id, visibility, sync: "queued|later|none"}
      끝난 작업이면 큐 kind=visibility_sync 로 지도(scan_points) 등록·삭제를 맞춘다. 처리 중이면 끝난 뒤 맞춘다
  {"op": "title", "job_id": "...", "title": "..."}            → {ok, job_id, title, sync}
  {"op": "pano_meta", "job_id": "...", "placements": {...}, "hotspots": [...], "info": {...}}
      → {ok, job_id, meta_url}   <glb_serve_dir>/<job>_pano/meta.json (tour.json 옆, pano.html·tour.html 이 읽음)

  관리 키가 없거나 틀리면 403 {error}. 형식 오류는 400 {error: 한국어 문구}. 본문 256 KB 까지.
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # python -I 에서도 common.py 를 찾도록
from common import (VISIBILITIES, check_edit_key, job_visibility, load_config, load_job_files, read_edit_key,  # noqa: E402
                    respond, safe_job_id, write_json_atomic)

MAX_BODY = 256 * 1024
MAX_HOTSPOTS = 200
MAX_SPOTS = 30
SPOT_ID = re.compile(r"^s\d{2}$")
# HTML·스크립트로 쓰일 수 있는 글자는 받지 않는다 (공유 페이지가 글자로만 그리더라도 한 번 더 막는다)
BAD_TEXT = re.compile(r"[<>]|javascript\s*:|data\s*:\s*text/html|on\w+\s*=", re.I)


class Bad(ValueError):
    pass


def text(v, limit, name, required=False):
    if v is None:
        if required:
            raise Bad(f"{name} 이(가) 필요합니다")
        return ""
    if not isinstance(v, str):
        raise Bad(f"{name} 은(는) 글자여야 합니다")
    v = "".join(ch for ch in v if ch.isprintable() or ch in "\n\t").strip()
    if len(v) > limit:
        raise Bad(f"{name} 은(는) {limit}자까지입니다")
    if BAD_TEXT.search(v):
        raise Bad(f"{name} 에 쓸 수 없는 글자(<, >, 스크립트)가 있습니다")
    return v


def num(v, lo, hi, name, allow_none=False):
    if v is None and allow_none:
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v or not (lo <= v <= hi):
        raise Bad(f"{name} 은(는) {lo}~{hi} 사이 숫자여야 합니다")
    return round(float(v), 4)


def clean_pano_meta(body):
    pl, hs, info = body.get("placements") or {}, body.get("hotspots") or [], body.get("info") or {}
    if not isinstance(pl, dict) or not isinstance(hs, list) or not isinstance(info, dict):
        raise Bad("placements 는 객체, hotspots 는 배열, info 는 객체여야 합니다")
    if len(pl) > MAX_SPOTS:
        raise Bad(f"지점 위치는 {MAX_SPOTS}곳까지입니다")
    if len(hs) > MAX_HOTSPOTS:
        raise Bad(f"설명 표시는 {MAX_HOTSPOTS}개까지입니다")
    placements = {}
    for sid, p in pl.items():
        if not isinstance(sid, str) or not SPOT_ID.match(sid):
            raise Bad("지점 id 는 s01 같은 형식이어야 합니다")
        if p is None:
            continue                                   # 위치 지우기
        if not isinstance(p, dict):
            raise Bad(f"{sid} 위치 형식이 맞지 않습니다")
        xy = p.get("xy")
        if not (isinstance(xy, list) and len(xy) == 2):
            raise Bad(f"{sid} 위치(xy)는 [x, y] 여야 합니다")
        placements[sid] = {"xy": [num(xy[0], -1e6, 1e6, f"{sid} x"), num(xy[1], -1e6, 1e6, f"{sid} y")],
                           "yaw_on_plan": num(p.get("yaw_on_plan", 0), -360, 360, f"{sid} 방향")}
    hotspots = []
    for i, h in enumerate(hs, 1):
        if not isinstance(h, dict):
            raise Bad(f"설명 표시 {i}번 형식이 맞지 않습니다")
        spot = h.get("spot")
        if not isinstance(spot, str) or not SPOT_ID.match(spot):
            raise Bad(f"설명 표시 {i}번의 지점(spot)이 맞지 않습니다")
        hotspots.append({"spot": spot, "yaw": num(h.get("yaw"), -360, 360, f"설명 표시 {i}번 yaw"),
                         "pitch": num(h.get("pitch"), -90, 90, f"설명 표시 {i}번 pitch"),
                         "title": text(h.get("title"), 60, f"설명 표시 {i}번 제목", required=True),
                         "text": text(h.get("text"), 500, f"설명 표시 {i}번 설명")})
    rooms = info.get("rooms")
    if rooms is not None and (isinstance(rooms, bool) or not isinstance(rooms, int) or not (0 <= rooms <= 100)):
        raise Bad("방 개수(rooms)는 0~100 정수여야 합니다")
    clean_info = {"title": text(info.get("title"), 100, "매물 제목"),
                  "area_m2": num(info.get("area_m2"), 0, 100000, "면적(m²)", allow_none=True),
                  "rooms": rooms, "note": text(info.get("note"), 1000, "설명")}
    return {"version": 1, "placements": placements, "hotspots": hotspots, "info": clean_info,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}


def update_both(qp, mp, **fields):
    """큐와 job.json 을 같이 고친다 (읽고-바꾸고-쓰기, pipeline 의 Queue.update 와 같은 방식)"""
    for path in (mp, qp):
        if not path or not os.path.exists(path):
            continue
        d = read_json(path)
        d.update(fields)
        if path == qp:
            d["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        write_json_atomic(path, d)


def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def queue_sync(qp, q):
    """끝난 작업: 대기열에 visibility_sync 로 넣고 원래 상태를 resume_* 에 둔다. 처리 중: 끝난 뒤 맞추게 표시만. → sync 값"""
    st = q.get("status")
    if st == "done":
        d = read_json(qp)
        if d.get("kind") in ("trench_post", "rebuild_glb"):   # 다른 후처리가 기다리는 중 → 끝난 뒤 맞춘다
            d["visibility_sync_pending"] = True
            write_json_atomic(qp, d)
            return "later"
        d.update(kind="visibility_sync", status="pending", resume_status="done", resume_step=d.get("step", 7),
                 resume_message=d.get("message") or "처리 완료", updated_at=time.strftime("%Y-%m-%d %H:%M:%S"))
        write_json_atomic(qp, d)
        return "queued"
    if st in ("pending", "processing"):
        d = read_json(qp)
        d["visibility_sync_pending"] = True
        write_json_atomic(qp, d)
        return "later"
    return "none"                                          # 실패한 작업: 지도에 올라간 것이 없다


def read_body():
    if os.environ.get("REQUEST_METHOD", "GET") != "POST":
        raise PermissionError("POST only")
    n = int(os.environ.get("CONTENT_LENGTH") or 0)
    if n <= 0:
        raise Bad("빈 요청입니다")
    if n > MAX_BODY:
        raise Bad("요청이 너무 큽니다 (256 KB 까지)")
    raw = sys.stdin.buffer.read(n)
    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise Bad("JSON 형식이 아닙니다")
    if not isinstance(body, dict):
        raise Bad("JSON 객체여야 합니다")
    return body


def main():
    try:
        body = read_body()
    except PermissionError:
        return respond({"error": "POST only"}, "405 Method Not Allowed")
    except Bad as e:
        return respond({"error": str(e)}, "400 Bad Request")
    job_id = safe_job_id(body.get("job_id"))
    if not job_id:
        return respond({"error": "job_id 형식 오류"}, "400 Bad Request")
    cfg = load_config()
    qp, q, mp, meta = load_job_files(cfg, job_id)
    if not qp:
        return respond({"error": "없는 작업"}, "404 Not Found")
    if not check_edit_key(meta, read_edit_key(body)):
        return respond({"error": "관리 키가 맞지 않습니다. 업로드할 때 받은 관리 링크로 열어 주세요."}, "403 Forbidden")
    op = body.get("op")
    try:
        if op == "visibility":
            v = body.get("visibility")
            if v not in VISIBILITIES:
                raise Bad("visibility 는 public, link, private 중 하나")
            before = job_visibility(meta if meta.get("visibility") else q)
            update_both(qp, mp, visibility=v)
            sync = "none"
            if v != before:                                # 지도 점 등록·삭제와 Portal 아이템 공유를 맞춘다
                sync = queue_sync(qp, read_json(qp))       # (파일을 닫은 뒤 바꾼다 — 윈도는 열린 파일을 os.replace 못 함)
            return respond({"ok": True, "job_id": job_id, "visibility": v, "sync": sync})
        if op == "title":
            t = text(body.get("title"), 100, "제목", required=True)
            if not t:
                raise Bad("제목을 입력해 주세요")
            update_both(qp, mp, title=t)
            sync = "none"
            if q.get("objectid") and job_visibility(meta if meta.get("visibility") else q) == "public":
                sync = queue_sync(qp, read_json(qp))       # 지도 점의 제목도 맞춘다
            return respond({"ok": True, "job_id": job_id, "title": t, "sync": sync})
        if op == "pano_meta":
            doc = clean_pano_meta(body)
            serve = os.path.join(cfg["glb_serve_dir"], f"{job_id}_pano")
            if q.get("mode") != "pano" or not os.path.exists(os.path.join(serve, "tour.json")):
                return respond({"error": "VR 투어가 아직 없는 작업입니다"}, "409 Conflict")
            write_json_atomic(os.path.join(serve, "meta.json"), doc)
            meta_url = f"{cfg['glb_serve_url']}/{job_id}_pano/meta.json"
            update_both(qp, None, pano_meta_url=meta_url)
            return respond({"ok": True, "job_id": job_id, "meta_url": meta_url,
                            "placements": len(doc["placements"]), "hotspots": len(doc["hotspots"])})
        raise Bad("op 는 visibility, title, pano_meta 중 하나")
    except Bad as e:
        return respond({"error": str(e)}, "400 Bad Request")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # never let IIS return a bare 502
        respond({"error": f"서버 오류: {e}"}, "500 Internal Server Error")
