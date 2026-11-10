"""관리 대상(장소) API — 같은 벽·구역을 날짜별로 다시 찍어 위험요소 변화를 비교하기 위한 묶음 (docs/hazards_contract.md 4절)

GET  sites.py?lat=37.1&lon=127.0&radius_m=300 -> {"sites": [...]} (거리순; 위치 없으면 전체, 최근 점검순)
GET  sites.py?site_id=s_xxxxxxxx               -> {"site": {...}, "scans": [...]}  (점검 이력, 최신순)
POST sites.py  (form 또는 JSON: name 필수, lat, lon, note) -> {"site_id": "s_xxxxxxxx", "name": "..."}
저장: <data_root>/sites/<site_id>.json  (파이프라인이 점검을 끝낼 때 scans·marker_ids 를 더한다)
"""
import json
import math
import os
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_config, query_params, respond  # noqa: E402

MAX_BODY = 64 * 1024


def sites_dir(cfg):
    d = os.path.join(cfg["data_root"], "sites")
    os.makedirs(d, exist_ok=True)
    return d


def safe_site_id(v):
    v = (v or "").strip()
    return v if len(v) == 10 and v.startswith("s_") and all(c in "0123456789abcdef" for c in v[2:]) else None


def load_all(cfg):
    out = []
    d = sites_dir(cfg)
    for n in os.listdir(d):
        if n.endswith(".json"):
            try:
                with open(os.path.join(d, n), "r", encoding="utf-8") as f:
                    out.append(json.load(f))
            except Exception:
                continue
    return out


def dist_m(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def summary(s, cfg):
    scans = sorted(s.get("scans", []), key=lambda x: x.get("captured_at") or "")
    last = scans[-1] if scans else {}
    return {"site_id": s["site_id"], "name": s.get("name"), "lat": s.get("lat"), "lon": s.get("lon"), "note": s.get("note", ""),
            "created_at": s.get("created_at"), "scans": len(scans), "last_scan_at": last.get("captured_at"),
            "last_job_id": last.get("job_id"), "last_thumb_url": last.get("thumb_url"), "last_ortho_url": last.get("ortho_url"),
            "marker_ids": s.get("marker_ids", [])}


def read_post():
    ctype = os.environ.get("CONTENT_TYPE", "").lower()
    length = int(os.environ.get("CONTENT_LENGTH") or 0)
    if ctype.startswith("multipart/form-data"):
        from upload import parse_multipart
        fields, _ = parse_multipart()
        return fields
    if length <= 0 or length > MAX_BODY:
        raise ValueError("본문이 없거나 너무 큽니다")
    body = sys.stdin.buffer.read(length).decode("utf-8", errors="replace")
    if ctype.startswith("application/json"):
        return {k: (v if isinstance(v, str) else json.dumps(v)) if v is not None else "" for k, v in json.loads(body).items()}
    from urllib.parse import parse_qs
    return {k: v[0] for k, v in parse_qs(body).items()}


def num(v, lo, hi):
    try:
        x = float(v)
        return x if lo <= x <= hi else None
    except (TypeError, ValueError):
        return None


def main():
    cfg = load_config()
    if os.environ.get("REQUEST_METHOD", "GET") == "POST":
        try:
            f = read_post()
        except ValueError as e:
            return respond({"error": str(e)}, "400 Bad Request")
        name = (f.get("name") or "").strip()[:60]
        if not name:
            return respond({"error": "장소 이름(name)을 입력해 주세요"}, "400 Bad Request")
        site = {"site_id": "s_" + uuid.uuid4().hex[:8], "name": name, "lat": num(f.get("lat"), -90, 90), "lon": num(f.get("lon"), -180, 180),
                "note": (f.get("note") or "")[:300], "created_at": time.strftime("%Y-%m-%d %H:%M:%S"), "marker_ids": [], "scans": []}
        p = os.path.join(sites_dir(cfg), site["site_id"] + ".json")
        with open(p + ".tmp", "w", encoding="utf-8") as fp:
            json.dump(site, fp, ensure_ascii=False, indent=2)
        os.replace(p + ".tmp", p)
        return respond({"site_id": site["site_id"], "name": name})

    q = query_params()
    if q.get("site_id"):
        sid = safe_site_id(q.get("site_id"))
        p = os.path.join(sites_dir(cfg), f"{sid}.json") if sid else ""
        if not sid or not os.path.exists(p):
            return respond({"error": "없는 장소"}, "404 Not Found")
        with open(p, "r", encoding="utf-8") as fp:
            s = json.load(fp)
        scans = sorted(s.get("scans", []), key=lambda x: x.get("captured_at") or "", reverse=True)
        return respond({"site": summary(s, cfg), "scans": scans})
    lat, lon = num(q.get("lat"), -90, 90), num(q.get("lon"), -180, 180)
    radius = num(q.get("radius_m"), 1, 100000) or 300.0
    items = []
    for s in load_all(cfg):
        it = summary(s, cfg)
        if lat is not None and lon is not None:
            if it["lat"] is None or it["lon"] is None:
                continue
            it["distance_m"] = round(dist_m(lat, lon, it["lat"], it["lon"]), 1)
            if it["distance_m"] > radius:
                continue
        items.append(it)
    if lat is not None and lon is not None:
        items.sort(key=lambda x: x["distance_m"])
    else:
        items.sort(key=lambda x: x.get("last_scan_at") or x.get("created_at") or "", reverse=True)
    respond({"sites": items[:200]})


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        respond({"error": f"서버 오류: {e}"}, "500 Internal Server Error")
