"""GET /app/3dupload/status.py?job_id=xxxxxxxx -> 큐 파일 내용 (status, step, step_name, message, title, scan_type, scene_item_id, glb_url, thumb_url)"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_config, query_params, respond, safe_job_id  # noqa: E402

STEP_NAMES = ["대기 중", "입력 준비", "융합·텍스처", "좌표·LAS", "GLB 준비", "SLPK 생성", "Portal 발행", "완료"]


def main():
    job_id = safe_job_id(query_params().get("job_id"))
    if not job_id:
        return respond({"error": "job_id 형식 오류"}, "400 Bad Request")
    path = os.path.join(load_config()["jobs_dir"], job_id + ".json")
    if not os.path.exists(path):
        return respond({"error": "없는 작업"}, "404 Not Found")
    with open(path, "r", encoding="utf-8") as f:
        q = json.load(f)
    step = int(q.get("step", 0))
    respond({
        "job_id": job_id, "status": q.get("status", "pending"), "step": step,
        "title": q.get("title"), "mode": q.get("mode"), "scan_type": q.get("scan_type"), "thumb_url": q.get("thumb_url"),
        "step_name": STEP_NAMES[min(step, len(STEP_NAMES) - 1)], "message": q.get("message", ""),
        "scene_item_id": q.get("scene_item_id"), "glb_url": q.get("glb_url"),
        "updated_at": q.get("updated_at"), "error_detail": q.get("error_detail"),
    })


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        respond({"error": f"서버 오류: {e}"}, "500 Internal Server Error")
