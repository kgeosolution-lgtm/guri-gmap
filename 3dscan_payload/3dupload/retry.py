"""GET /app/3dupload/retry.py?job_id=xxxxxxxx -> 실패한 작업을 다시 대기열에 넣는다 (워커 결과·SLPK 는 재사용)"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_config, query_params, respond, safe_job_id  # noqa: E402


def main():
    job_id = safe_job_id(query_params().get("job_id"))
    if not job_id:
        return respond({"error": "job_id 형식 오류"}, "400 Bad Request")
    path = os.path.join(load_config()["jobs_dir"], job_id + ".json")
    if not os.path.exists(path):
        return respond({"error": "없는 작업"}, "404 Not Found")
    with open(path, "r", encoding="utf-8") as f:
        q = json.load(f)
    if q.get("status") not in ("failed", "done"):
        return respond({"error": f"상태가 {q.get('status')} 인 작업은 재시도할 수 없습니다"}, "409 Conflict")
    q.update(status="pending", step=0, message="재시도 대기 중", error_detail=None, scene_item_id=None,
             updated_at=time.strftime("%Y-%m-%d %H:%M:%S"))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(q, f, ensure_ascii=False, indent=2)
    respond({"job_id": job_id, "status": "pending"})


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        respond({"error": f"서버 오류: {e}"}, "500 Internal Server Error")
