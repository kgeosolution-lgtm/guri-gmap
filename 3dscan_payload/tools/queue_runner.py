r"""
kgeoScan Queue Runner (v2, 2026-10)
  - 웹 루트 밖(D:\kgeoHub\tools\3dscan)에 두고 작업 스케줄러로 실행한다.
  - 설정은 D:\kgeoHub\config\kgeoscan.json (환경변수 KGEOSCAN_CONFIG 로 바꿀 수 있음)
  - arcpy 없이 동작한다. SLPK/Portal 단계는 pipeline.py 안에서 선택적으로 실행된다.
  - jobs\<id>.json 의 status: pending → processing → done | failed
"""
import json
import logging
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.environ.get("KGEOSCAN_CONFIG", r"D:\kgeoHub\config\kgeoscan.json")

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CFG = json.load(f)
JOB_DIR = CFG["jobs_dir"]
LOG_FILE = os.path.join(CFG.get("log_dir", os.path.join(CFG["data_root"], "logs")), "queue_runner.log")
os.makedirs(JOB_DIR, exist_ok=True)
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler(sys.stdout)])
log = logging.getLogger("runner")


def pending_jobs():
    jobs = []
    for name in os.listdir(JOB_DIR):
        if not name.endswith(".json"):
            continue
        path = os.path.join(JOB_DIR, name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            log.warning(f"큐 파일 읽기 실패 {name}: {e}")
            continue
        if data.get("status") == "pending":
            jobs.append((os.path.getmtime(path), path, data))
    jobs.sort()
    return [(p, d) for _, p, d in jobs]


def set_status(path, **fields):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.update(fields)
    data["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def run_pipeline(queue_path, data):
    job_id = data.get("job_id", "?")
    meta_path = os.path.join(data.get("job_dir", ""), "job.json")
    if not os.path.exists(meta_path):
        set_status(queue_path, status="failed", message="job.json 없음")
        return
    log.info(f"[{job_id}] 시작: {data.get('title')} ({data.get('mode')})")
    set_status(queue_path, status="processing", step=1, message="처리 시작")
    cmd = [CFG["worker_python"], "-I", os.path.join(HERE, "pipeline.py"), meta_path, queue_path]
    env = dict(os.environ, KGEOSCAN_CONFIG=CONFIG_PATH, PYTHONIOENCODING="utf-8")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=CFG.get("pipeline_timeout_sec", 1800), env=env)
    except subprocess.TimeoutExpired:
        log.error(f"[{job_id}] 시간 초과")
        set_status(queue_path, status="failed", message="처리 시간 초과")
        return
    if proc.stdout:
        for line in proc.stdout.rstrip().splitlines()[-40:]:
            log.info(f"[{job_id}] {line}")
    if proc.returncode == 0:
        log.info(f"[{job_id}] 완료")
        # pipeline.py 가 status=done 을 기록한다. 혹시 못 했으면 여기서 보정
        with open(queue_path, "r", encoding="utf-8") as f:
            if json.load(f).get("status") != "done":
                set_status(queue_path, status="done", message="처리 완료")
    else:
        err = ((proc.stderr or "") + "\n" + (proc.stdout or "")).strip()[-1200:]
        log.error(f"[{job_id}] 실패:\n{err}")
        # pipeline.py 가 이미 자기 오류 메시지를 큐 파일에 적었으면 그대로 둔다
        with open(queue_path, "r", encoding="utf-8") as f:
            cur = json.load(f)
        if cur.get("status") == "failed" and str(cur.get("message", "")).startswith("실패:"):
            return
        fail_line = next((l for l in reversed(err.splitlines()) if l.strip() and ("실패" in l or "Error" in l or "error" in l)), None)
        set_status(queue_path, status="failed", message=(fail_line or "처리 실패")[:300], error_detail=err)


def main():
    log.info("=" * 60)
    log.info(f"kgeoScan Queue Runner v2  jobs={JOB_DIR}  worker={CFG['worker_python']}")
    log.info("=" * 60)
    interval = int(CFG.get("poll_interval_sec", 10))
    once = "--once" in sys.argv
    while True:
        try:
            for path, data in pending_jobs():
                run_pipeline(path, data)
        except Exception as e:
            log.error(f"루프 오류: {e}")
        if once:
            break
        time.sleep(interval)


if __name__ == "__main__":
    main()
