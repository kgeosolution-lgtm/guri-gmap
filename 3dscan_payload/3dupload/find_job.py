"""GET /app/3dupload/find_job.py?client_id=<앱이 보낸 녹화 고유 ID>  -> 그 녹화로 만들어진 작업 {job_id, status, step, ...} (없으면 404)
   GET /app/3dupload/find_job.py?recent=10                          -> 최근 작업 요약 목록 (진단용)

앱이 업로드 중 '연결 끊김' 오류를 받았을 때, 서버에는 이미 작업이 만들어졌는지 확인해 재업로드 대신 폴링을 이어가기 위한 것.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_config, query_params, respond  # noqa: E402

STEP_NAMES = ["대기 중", "입력 준비", "융합·텍스처", "좌표·LAS", "GLB 준비", "SLPK 생성", "Portal 발행", "완료"]
SUMMARY_KEYS = ("job_id", "title", "mode", "scan_type", "status", "step", "message", "created_at", "updated_at",
                "scene_item_id", "glb_url", "thumb_url", "app", "client_id", "source_name")


def load_jobs(jobs_dir):
    out = []
    try:
        names = os.listdir(jobs_dir)
    except OSError:
        return out
    for n in names:
        if not n.endswith(".json"):
            continue
        p = os.path.join(jobs_dir, n)
        try:
            with open(p, "r", encoding="utf-8") as f:
                q = json.load(f)
            q["_mtime"] = os.path.getmtime(p)
            out.append(q)
        except Exception:
            continue
    out.sort(key=lambda q: q.get("_mtime", 0), reverse=True)
    return out


def summary(q):
    d = {k: q.get(k) for k in SUMMARY_KEYS}
    step = int(q.get("step", 0) or 0)
    d["step_name"] = STEP_NAMES[min(step, len(STEP_NAMES) - 1)]
    return d


def main():
    params = query_params()
    cfg = load_config()
    jobs = load_jobs(cfg["jobs_dir"])
    client_id = (params.get("client_id") or "").strip()[:64]
    if client_id:
        matches = [q for q in jobs if q.get("client_id") == client_id]
        if not matches:
            return respond({"error": "없는 작업", "client_id": client_id}, "404 Not Found")
        live = [q for q in matches if q.get("status") != "failed"] or matches
        return respond(summary(live[0]))
    try:
        n = max(1, min(int(params.get("recent") or 10), 50))
    except ValueError:
        n = 10
    respond({"jobs": [summary(q) for q in jobs[:n]]})


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        respond({"error": f"서버 오류: {e}"}, "500 Internal Server Error")
