"""GET /app/3dupload/status.py?job_id=xxxxxxxx -> 큐 파일 내용 (status, step, step_name, message, title, scan_type, scene_item_id, glb_url, thumb_url,
splat_status pending|processing|done|failed, splat_url, splat_message, ortho_url, area, pano_status, pano_message, pano_url, floorplan_url, visibility)

공개 범위 (docs/share_contract.md 1절): private 작업은 관리 키(헤더 X-Edit-Key 또는 ?key=)가 맞을 때만 산출물 주소를 준다.
키가 없거나 틀리면 {job_id, status, visibility: "private"} 만. can_edit 은 키가 맞을 때 true"""
import hmac
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (check_edit_key, job_visibility, load_config, load_job_files, query_params, read_edit_key,  # noqa: E402
                    respond, safe_job_id, splat_hq_block)

STEP_NAMES = ["대기 중", "입력 준비", "융합·텍스처", "좌표·LAS", "GLB 준비", "SLPK 생성", "Portal 발행", "완료"]


def worker_token_ok(cfg):
    """진단용: GPU 워커 토큰(헤더 X-Worker-Token)이 맞으면 실패 원인 원문도 준다 (splat_jobs.check_token 과 같은 값)"""
    want = (cfg.get("splat") or {}).get("worker_token") or ""
    got = os.environ.get("HTTP_X_WORKER_TOKEN") or ""
    return len(want) >= 16 and not want.startswith("<") and bool(got) and hmac.compare_digest(want.encode("utf-8"), got.encode("utf-8"))


def main():
    job_id = safe_job_id(query_params().get("job_id"))
    if not job_id:
        return respond({"error": "job_id 형식 오류"}, "400 Bad Request")
    cfg = load_config()
    qp, q, _mp, meta = load_job_files(cfg, job_id)
    if not qp:
        return respond({"error": "없는 작업"}, "404 Not Found")
    visibility = job_visibility(meta if meta.get("visibility") else q)
    key = read_edit_key()
    can_edit = bool(key) and check_edit_key(meta, key)
    if visibility == "private" and not can_edit:
        return respond({"job_id": job_id, "status": q.get("status", "pending"), "visibility": "private",
                        "message": "비공개 기록입니다. 관리 링크로 열어야 볼 수 있어요."})
    step = int(q.get("step", 0))
    # 실패 원인 원문(파이썬 추적·스티처 stderr)은 서버 경로가 드러나므로 관리 키나 워커 토큰이 있을 때만 (2026-11-16 기술 점검)
    diag = can_edit or worker_token_ok(cfg)
    respond({
        "visibility": visibility, "can_edit": can_edit,
        "job_id": job_id, "status": q.get("status", "pending"), "step": step,
        "title": q.get("title"), "mode": q.get("mode"), "scan_type": q.get("scan_type"), "thumb_url": q.get("thumb_url"),
        "step_name": STEP_NAMES[min(step, len(STEP_NAMES) - 1)], "message": q.get("message", ""),
        "scene_item_id": q.get("scene_item_id"), "glb_url": q.get("glb_url"),
        "splat_status": q.get("splat_status"), "splat_url": q.get("splat_url"), "splat_message": q.get("splat_message"),
        # 사진 3D 고화질 (2026-11-17): requested|done|failed, 고를 수 있는지는 관리 키가 있을 때만 알려 준다
        "splat_hq": q.get("splat_hq"), "splat_started_at": q.get("splat_started_at"),
        "splat_hq_ok": (splat_hq_block(q, meta) is None) if can_edit else None,
        "ortho_url": q.get("ortho_url"), "area": q.get("area"),
        "site_id": q.get("site_id"), "hazards_url": q.get("hazards_url"), "changes_url": q.get("changes_url"),
        "objectid": q.get("objectid"), "splat_kind": q.get("splat_kind"), "quality": q.get("quality"),
        "trench": q.get("trench"), "utilities_url": q.get("utilities_url"), "utility_report_url": q.get("utility_report_url"),
        # 웹 굴착 기록 후처리 (docs/web_trench_contract.md 4절): pending|processing|done|skipped|failed
        "trench_post": q.get("trench_post"), "trench_post_message": q.get("trench_post_message"),
        # VR 투어 (docs/pano_contract.md 2절): pending|processing|done|failed, pano_url = tour.json 공개 주소
        "pano_status": q.get("pano_status"), "pano_message": q.get("pano_message"), "pano_url": q.get("pano_url"),
        "pano_progress": q.get("pano_progress"), "pano": q.get("pano"),
        "pano_stderr": q.get("pano_stderr") if diag and q.get("pano_status") == "failed" else None,   # 실패 원인 (스티처 stderr 끝)
        # 📐 집·방 평면도 (worker/floorplan.py): <job>_floorplan.json (urls.svg·png·dxf 가 안에 있다)
        "floorplan_url": q.get("floorplan_url"),
        "updated_at": q.get("updated_at"), "error_detail": q.get("error_detail") if diag else None,
    })


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        sys.stderr.write(f"status error: {e!r}\n")
        respond({"error": "서버 오류입니다. 잠시 뒤 다시 시도해 주세요."}, "500 Internal Server Error")
