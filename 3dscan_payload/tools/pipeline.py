r"""
kgeoScan pipeline v2:  python -I pipeline.py <job_dir>\job.json <jobs>\<id>.json

단계 (status.py 의 STEP_NAMES 와 같은 번호)
  1 입력 준비   : stray → 워커(process_scan.py)로 GLB·LAS 생성 / legacy → 올라온 LAS·GLB 사용
  2 좌표·LAS   : LAS에서 중심·범위(UTM 52N) 읽기
  3 GLB 준비   : 서빙 폴더로 복사 → glb_url, 썸네일(thumb.jpg) 복사 → thumb_url (없으면 zip 에서 생성, 실패해도 계속)
  4 SLPK 생성  : arcpy (선택: slpk_enabled 이고 arcgis_python 이 있을 때만, 실패해도 계속)
  5 Portal 발행: SLPK 아이템 추가 → Scene 서비스 발행 → 공개 (SLPK 가 있을 때만)
  6 scan_points 등록
  7 완료  (+ 설정 splat.enabled 이고 유형이 splat.scan_types 에 있으면 큐 파일에 splat_status=pending → 외부 GPU 워커가 가져감)
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.environ.get("KGEOSCAN_CONFIG", r"D:\kgeoHub\config\kgeoscan.json"), "r", encoding="utf-8"))
T0 = time.time()
_SHARE_EVERYONE = True          # Portal Scene·SLPK 아이템을 모두에게 공유할지 (공개 범위 public 일 때만, main 에서 정함)
VISIBILITIES = ("public", "link", "private")


def current_visibility(meta):
    """지금의 공개 범위 (docs/share_contract.md 1절). edit.py 가 처리 중에 바꿀 수 있어 job.json 을 다시 읽는다.
    필드가 없는 예전 작업은 public (지금까지처럼 지도에 나온다)"""
    v = meta.get("visibility")
    try:
        with open(os.path.join(meta["job_dir"], "job.json"), "r", encoding="utf-8") as f:
            v = json.load(f).get("visibility", v)
    except Exception:
        pass
    return v if v in VISIBILITIES else "public"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # 러너가 UTF-8 로 읽는다 (cp949 깨짐 방지)


def log(msg):
    print(f"[{time.time() - T0:6.1f}s] {msg}", flush=True)


class Queue:
    def __init__(self, path):
        self.path = path

    def read(self):
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def update(self, **fields):
        with open(self.path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data.update(fields)
        data["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)


# ── Portal REST ──────────────────────────────────────────────────────────────
def http_json(url, data=None, files=None, timeout=600):
    """POST (form or multipart) / GET and parse JSON. `files` = {field: (filename, bytes)}"""
    if files:
        boundary = "----kgeoscan" + str(int(time.time() * 1000))
        body = b""
        for k, v in (data or {}).items():
            body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode("utf-8")
        for k, (fname, blob) in files.items():
            body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{fname}\"\r\n"
                     f"Content-Type: application/octet-stream\r\n\r\n").encode("utf-8") + blob + b"\r\n"
        body += f"--{boundary}--\r\n".encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    elif data is not None:
        req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode("utf-8"))
    else:
        req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        out = json.loads(r.read().decode("utf-8"))
    if isinstance(out, dict) and "error" in out:
        raise RuntimeError(f"ArcGIS 오류: {out['error']}")
    return out


def get_token(referer):
    out = http_json(CFG["portal_url"] + "/sharing/rest/generateToken",
                    {"username": CFG["portal_user"], "password": CFG["portal_password"],
                     "referer": referer, "expiration": 120, "f": "json"})
    return out["token"]


def wgs84_from_utm(x, y, epsg):
    from pyproj import Transformer
    lon, lat = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True).transform(x, y)
    return lon, lat


# ── 단계 구현 ────────────────────────────────────────────────────────────────
def step_prepare(meta, out_dir):
    if meta["mode"] == "objcap":
        done_las, done_glb = os.path.join(out_dir, "scan.las"), os.path.join(out_dir, "mesh_tex.glb")
        if os.path.exists(done_las) and os.path.exists(done_glb) and os.path.exists(os.path.join(out_dir, "result.json")):
            log("워커 결과가 이미 있어 재사용 (재시도)")
            return done_las, done_glb
        g = meta["georef"]
        cmd = [CFG["worker_python"], "-I", os.path.join(CFG["worker_dir"], "process_objcap.py"),
               "--zip", meta["scan_zip"], "--out", out_dir, "--lon", str(g["lon"]), "--lat", str(g["lat"]),
               "--elev", str(g.get("elev", 0.0)), "--heading", str(g.get("heading", 0.0)),
               "--utm-epsg", str(CFG.get("utm_epsg", 32652))]
        log("워커 실행: process_objcap.py (Object Capture 모델)")
        with open(os.path.join(out_dir, "worker_stdout.log"), "a", encoding="utf-8") as lf:
            proc = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, text=True)
        if proc.returncode != 0:
            raise RuntimeError("Object Capture 모델 변환 실패 (worker_stdout.log 확인)")
        return done_las, done_glb
    if meta["mode"] == "stray":
        done_las, done_glb = os.path.join(out_dir, "scan.las"), os.path.join(out_dir, "mesh_tex.glb")
        if os.path.exists(done_las) and os.path.exists(done_glb) and os.path.exists(os.path.join(out_dir, "result.json")):
            log("워커 결과가 이미 있어 재사용 (재시도)")
            return done_las, done_glb
        g = meta["georef"]
        fu, tx = CFG.get("fusion", {}), CFG.get("texture", {})
        cmd = [CFG["worker_python"], "-I", os.path.join(CFG["worker_dir"], "process_scan.py"),
               "--zip", meta["scan_zip"], "--out", out_dir,
               "--lon", str(g["lon"]), "--lat", str(g["lat"]), "--elev", str(g.get("elev", 0.0)),
               "--heading", str(g.get("heading", 0.0)),
               "--voxel", str(fu.get("voxel", 0.006)), "--every", str(fu.get("every", 1)),
               "--max-depth", str(fu.get("max_depth", 4.0)), "--fuse-tris", str(fu.get("fuse_tris", 600000)),
               "--tex-tris", str(tx.get("tris", 120000)), "--keyframes", str(tx.get("keyframes", 100)),
               "--tex-size", str(tx.get("tex_size", 4096)), "--jpeg-quality", str(tx.get("jpeg_quality", 85))]
        obj = meta.get("object") or None
        if obj:
            cmd += ["--object-mode"]
            if obj.get("center"):
                cmd += ["--obj-center", ",".join(str(v) for v in obj["center"])]
            if obj.get("radius"):
                cmd += ["--obj-radius", str(obj["radius"])]
        area = meta.get("area") or None
        if area:
            cmd += ["--area-mode", "--area-surface", area.get("surface", "auto")]
        log("워커 실행: process_scan.py" + (" (물체 모드)" if obj else "") + (" (면 촬영·정사영상)" if area else ""))
        with open(os.path.join(out_dir, "worker_stdout.log"), "a", encoding="utf-8") as lf:
            proc = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, text=True)
        if proc.returncode != 0:
            raise RuntimeError("워커 실패 (worker_stdout.log 확인)")
        return os.path.join(out_dir, "scan.las"), os.path.join(out_dir, "mesh_tex.glb")
    return meta["las_path"], meta["glb_path"]


def step_las(las_path):
    import laspy
    import numpy as np
    with laspy.open(las_path) as f:
        las = f.read()
    x, y, z = np.asarray(las.x), np.asarray(las.y), np.asarray(las.z)
    info = dict(points=int(len(x)), coord_x=float(x.mean()), coord_y=float(y.mean()), coord_z=float(z.mean()),
                bbox=[float(x.min()), float(y.min()), float(z.min()), float(x.max()), float(y.max()), float(z.max())])
    log(f"LAS: {info['points']} 점, 중심 ({info['coord_x']:.2f}, {info['coord_y']:.2f}, {info['coord_z']:.2f})")
    return info


def step_glb(glb_path, job_id):
    os.makedirs(CFG["glb_serve_dir"], exist_ok=True)
    dest = os.path.join(CFG["glb_serve_dir"], f"{job_id}.glb")
    shutil.copy2(glb_path, dest)
    url = f"{CFG['glb_serve_url']}/{job_id}.glb"
    log(f"GLB 서빙: {url} ({os.path.getsize(dest) / 1e6:.1f} MB)")
    return url


def step_thumb(meta, out_dir, job_id):
    """워커가 만든 out	humb.jpg 를 서빙 폴더로 복사 → thumb_url. 없으면(재시도·옛 결과) zip 에서 바로 만든다. 실패하면 ''"""
    src = os.path.join(out_dir, "thumb.jpg")
    if not os.path.exists(src) and meta.get("mode") == "stray" and meta.get("scan_zip") and os.path.exists(meta["scan_zip"]):
        cmd = [CFG["worker_python"], "-I", os.path.join(CFG["worker_dir"], "thumbnail.py"), "--zip", meta["scan_zip"], "--out", src]
        try:
            with open(os.path.join(out_dir, "worker_stdout.log"), "a", encoding="utf-8") as lf:
                subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, text=True, timeout=300)
        except Exception as e:
            log(f"썸네일 생성 생략: {e}")
    if not os.path.exists(src):
        log("썸네일 없음 (legacy 업로드이거나 생성 실패)")
        return ""
    os.makedirs(CFG["glb_serve_dir"], exist_ok=True)
    dest = os.path.join(CFG["glb_serve_dir"], f"{job_id}.jpg")
    shutil.copy2(src, dest)
    url = f"{CFG['glb_serve_url']}/{job_id}.jpg"
    log(f"썸네일: {url} ({os.path.getsize(dest) / 1e3:.0f} KB)")
    return url


def step_ortho(out_dir, job_id):
    """워커가 만든 out/ortho/ 를 서빙 폴더로 복사 -> ortho_url(메타 JSON 주소). 없으면 ''"""
    src = os.path.join(out_dir, "ortho")
    meta_p = os.path.join(src, "ortho.json")
    if not os.path.exists(meta_p):
        return ""
    m = json.load(open(meta_p, "r", encoding="utf-8"))
    base = f"{job_id}_ortho"
    names = {"ortho.jpg": base + ".jpg", "ortho_overlay.png": base + ".png", "ortho.jgw": base + ".jgw", "ortho.prj": base + ".prj",
             "ortho_height.bin": base + "_h.bin", "ortho_height.jpg": base + "_h.jpg",
             "ortho_cracks.json": base + "_cracks.json", "ortho_cracks.dxf": base + "_cracks.dxf"}
    for a, b in names.items():
        if os.path.exists(os.path.join(src, a)):
            shutil.copy2(os.path.join(src, a), os.path.join(CFG["glb_serve_dir"], b))
    files = {"image": f"{CFG['glb_serve_url']}/{base}.jpg", "overlay": f"{CFG['glb_serve_url']}/{base}.png"}
    hm = m.get("height_map") or (m.get("height") if isinstance(m.get("height"), dict) else None)
    if hm and os.path.exists(os.path.join(src, "ortho_height.bin")):   # 높이 지도 (int16 mm) + 색 미리보기
        files["height_bin"] = f"{CFG['glb_serve_url']}/{base}_h.bin"
        files["height_image"] = f"{CFG['glb_serve_url']}/{base}_h.jpg"
    if os.path.exists(os.path.join(src, "ortho_cracks.json")):            # 균열 자동 분석 (목록 JSON + 외관조사망도 DXF)
        files["cracks"] = f"{CFG['glb_serve_url']}/{base}_cracks.json"
        if os.path.exists(os.path.join(src, "ortho_cracks.dxf")):
            files["cracks_dxf"] = f"{CFG['glb_serve_url']}/{base}_cracks.dxf"
    if os.path.exists(os.path.join(src, "hazards.json")):                # 위험요소 공통 목록 (step_hazards 가 작업 정보를 채워 둔다)
        files["hazards"] = f"{CFG['glb_serve_url']}/{job_id}_hazards.json"
    m["files"] = files
    if m.get("georef"):
        m["georef"]["world_file_url"] = f"{CFG['glb_serve_url']}/{base}.jgw"
    with open(os.path.join(CFG["glb_serve_dir"], base + ".json"), "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=2)
    url = f"{CFG['glb_serve_url']}/{base}.json"
    log(f"정사영상: {url} ({m.get('surface')} {m.get('width')}x{m.get('height')}, {m.get('gsd_m', 0) * 1000:.2f} mm/px)")
    return url


FLOORPLAN_FILES = ("floorplan.json", "floorplan.svg", "floorplan.png", "floorplan.dxf")


def floorplan_wanted(meta):
    """집·방 스캔(앱 LiDAR, 유형 home)만 평면도를 만든다 — 굴착·현장조사·물체 모드는 벽이 없거나 의미가 없다"""
    return meta.get("mode") == "stray" and (meta.get("scan_type") or "home") == "home"


def step_floorplan(meta, out_dir, job_id, timeout=600):
    """worker/floorplan.py(메시 → 벽·문·창·치수·방 면적) → 서빙 <job>_floorplan/ (json·svg·png·dxf) 와
    <job>_floorplan.json (걸어보기 walk.js·스플랫 페이지·VR 투어 미니맵이 GLB 옆에서 찾는 이름) → floorplan_url. 실패·방 없음이면 ''
    부가 단계라 예외를 밖으로 내지 않는다(호출부도 감싼다)."""
    mesh = next((p for p in (os.path.join(out_dir, "mesh_full.ply"), os.path.join(out_dir, "mesh.ply")) if os.path.exists(p)), "")
    fp_py = os.path.join(CFG["worker_dir"], "floorplan.py")
    if not mesh or not os.path.exists(fp_py):
        log("평면도 생략: " + ("메시 없음" if not mesh else "floorplan.py 없음"))
        return ""
    dest = os.path.join(out_dir, "floorplan")
    shutil.rmtree(dest, ignore_errors=True)
    cmd = [CFG["worker_python"], "-I", fp_py, "--mesh", mesh, "--out", dest, "--title", f"{meta.get('title') or job_id} 평면도",
           "--scan-name", job_id, "--no-debug"]
    t0 = time.time()
    try:
        with open(os.path.join(out_dir, "floorplan_stdout.log"), "w", encoding="utf-8") as lf:
            rc = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, text=True, timeout=timeout).returncode
    except subprocess.TimeoutExpired:
        log(f"평면도 생략: {timeout}초 안에 끝나지 않음")
        return ""
    src_json = os.path.join(dest, "floorplan.json")
    if rc != 0 or not os.path.exists(src_json):
        log(f"평면도 생략: floorplan.py 종료 코드 {rc} (out/floorplan_stdout.log)")
        return ""
    fp = json.load(open(src_json, "r", encoding="utf-8"))
    rooms = [r for r in fp.get("rooms", []) if not r.get("partial")] or fp.get("rooms", [])
    if not rooms:
        log("평면도 생략: 방을 찾지 못함 (벽이 충분히 찍히지 않음)")
        return ""
    serve = os.path.join(CFG["glb_serve_dir"], f"{job_id}_floorplan")
    shutil.rmtree(serve, ignore_errors=True)
    os.makedirs(serve, exist_ok=True)
    for n in FLOORPLAN_FILES:
        if os.path.exists(os.path.join(dest, n)):
            shutil.copy2(os.path.join(dest, n), os.path.join(serve, n))
    base_url = f"{CFG['glb_serve_url']}/{job_id}_floorplan"
    fp["urls"] = {k: f"{base_url}/{n}" for k, n in (("json", "floorplan.json"), ("svg", "floorplan.svg"), ("png", "floorplan.png"),
                                                       ("dxf", "floorplan.dxf")) if os.path.exists(os.path.join(serve, n))}
    fp["job_id"] = job_id
    with open(os.path.join(CFG["glb_serve_dir"], f"{job_id}_floorplan.json"), "w", encoding="utf-8") as f:   # GLB 옆 (walk.js 규약)
        json.dump(fp, f, ensure_ascii=False, indent=1)
    total = sum(r.get("area_m2", 0) for r in rooms)
    url = f"{CFG['glb_serve_url']}/{job_id}_floorplan.json"
    log(f"평면도: {url} (방 {len(rooms)}개, {total:.2f} m², {time.time() - t0:.1f}s)")
    return url


# ── 위험요소 이력: 관리 대상(장소) + 직전 점검과 변화 비교 (docs/hazards_contract.md) ─────────────────────
def sites_dir():
    d = os.path.join(CFG["data_root"], "sites")
    os.makedirs(d, exist_ok=True)
    return d


def site_load(site_id):
    p = os.path.join(sites_dir(), f"{site_id}.json")
    if not site_id or not os.path.exists(p):
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def site_save(site):
    p = os.path.join(sites_dir(), f"{site['site_id']}.json")
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(site, f, ensure_ascii=False, indent=2)
    os.replace(p + ".tmp", p)


def step_hazards(meta, out_dir, job_id):
    """워커의 out/ortho/hazards.json 에 작업 정보를 채워 서빙 폴더에 두고, 장소(site)에 이 점검을 기록한 뒤
    같은 장소의 직전 점검과 변화를 비교한다 → (hazards_url, changes_url, site_id). 장소는 업로드의 site_id, 없으면 고정 표식 ID 로 찾는다"""
    src = os.path.join(out_dir, "ortho", "hazards.json")
    if not os.path.exists(src):
        return "", "", None
    serve, url = CFG["glb_serve_dir"], CFG["glb_serve_url"]
    doc = json.load(open(src, "r", encoding="utf-8"))
    # 고정 표식 = ID 10~575. 0~9 는 균열 카드, 576~583 은 굴착 기준판(옮겨 다니는 판이라 장소 묶기에 쓰면 안 됨)
    mids = sorted({int(m["id"]) for m in doc.get("markers", []) if 10 <= int(m.get("id", 0)) < 576})
    site = site_load(meta.get("site_id"))
    if site is None and mids:                              # 자동 묶기: 고정 표식 ID 가 가장 많이 겹치는 장소
        best = (0, None)
        for n in os.listdir(sites_dir()):
            if n.endswith(".json"):
                try:
                    s_ = json.load(open(os.path.join(sites_dir(), n), "r", encoding="utf-8"))
                except Exception:
                    continue
                k = len(set(s_.get("marker_ids", [])) & set(mids))
                if k > best[0]:
                    best = (k, s_)
        site = best[1]
        if site:
            log(f"장소 자동 묶기: 표식 {mids} → {site['site_id']} ({site.get('name')})")
    doc.update(job_id=job_id, site_id=site["site_id"] if site else None, captured_at=meta.get("created_at"))
    doc["frame"]["image"] = f"{url}/{job_id}_ortho.jpg"
    with open(os.path.join(serve, f"{job_id}_hazards.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
    hazards_url = f"{url}/{job_id}_hazards.json"
    log(f"위험요소: {doc.get('summary', {}).get('counts')} → {hazards_url}")
    changes_url = ""
    if site:
        scans = [s_ for s_ in site.get("scans", []) if s_.get("job_id") != job_id]
        prev = next((s_ for s_ in sorted(scans, key=lambda s_: s_.get("captured_at") or "", reverse=True)
                     if os.path.exists(os.path.join(serve, f"{s_['job_id']}_hazards.json"))), None)
        if prev:
            pj = prev["job_id"]
            out_p = os.path.join(out_dir, "changes.json")
            cmd = [CFG["worker_python"], "-I", os.path.join(CFG["worker_dir"], "hazard_change.py"),
                   "--prev", os.path.join(serve, f"{pj}_hazards.json"), "--prev-img", os.path.join(serve, f"{pj}_ortho.jpg"),
                   "--cur", os.path.join(serve, f"{job_id}_hazards.json"), "--cur-img", os.path.join(serve, f"{job_id}_ortho.jpg"),
                   "--out", out_p]
            if not os.path.exists(cmd[2]):
                log("변화 비교 모듈(hazard_change.py)이 아직 없음 → 건너뜀")
            else:
                proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
                if proc.returncode == 0 and os.path.exists(out_p):
                    ch = json.load(open(out_p, "r", encoding="utf-8"))
                    ch.update(site_id=site["site_id"], prev_job=pj, cur_job=job_id,
                              prev_captured_at=prev.get("captured_at"), cur_captured_at=meta.get("created_at"))
                    with open(os.path.join(serve, f"{job_id}_changes.json"), "w", encoding="utf-8") as f:
                        json.dump(ch, f, ensure_ascii=False)
                    changes_url = f"{url}/{job_id}_changes.json"
                    log(f"변화 비교 ({pj} → {job_id}): {ch.get('summary')}")
                else:
                    log("변화 비교 실패: " + (proc.stderr or proc.stdout or "")[-500:])
        entry = dict(job_id=job_id, captured_at=meta.get("created_at"), title=meta.get("title"), hazards_url=hazards_url,
                     ortho_url=f"{url}/{job_id}_ortho.json", changes_url=changes_url or None,
                     thumb_url=f"{url}/{job_id}_thumb.jpg", counts=doc.get("summary", {}).get("counts"))
        site["scans"] = scans + [entry]
        site["marker_ids"] = sorted(set(site.get("marker_ids", [])) | set(mids))
        site["last_scan_at"], site["last_job_id"] = meta.get("created_at"), job_id
        site_save(site)
        # 정사영상 메타에도 위험요소·변화 주소를 적어 뷰어가 바로 찾게 한다
        op = os.path.join(serve, f"{job_id}_ortho.json")
        if os.path.exists(op):
            m = json.load(open(op, "r", encoding="utf-8"))
            m.setdefault("files", {})["hazards"] = hazards_url
            if changes_url:
                m["files"]["changes"] = changes_url
            m["site"] = dict(site_id=site["site_id"], name=site.get("name"))
            with open(op, "w", encoding="utf-8") as f:
                json.dump(m, f, ensure_ascii=False, indent=2)
    return hazards_url, changes_url, site["site_id"] if site else None


# ── 굴착 기록: 드러난 지하시설물 자동 추출 + 산출물 (docs/utility_contract.md) ─────────────────────
def _extract_dataset(zip_path, dest):
    """산출물(제출 동영상·사진 쪽)과 관 종류 표시용 Stray 원본을 푼다 (process_scan 은 다 쓴 뒤 지운다). confidence/ 는 뺀다.
    → odometry.csv 가 있는 데이터 폴더 또는 None"""
    if not zip_path or not os.path.exists(zip_path):
        return None
    shutil.rmtree(dest, ignore_errors=True)
    try:
        with zipfile.ZipFile(zip_path) as zf:   # extractall 은 절대 경로·'..' 을 걸러 낸다
            zf.extractall(dest, members=[n for n in zf.namelist() if "/confidence/" not in "/" + n.replace("\\", "/")])
    except (zipfile.BadZipFile, OSError) as e:
        log(f"굴착 기록: 원본 zip 풀기 실패 ({e}) → 동영상·사진·관 종류 표시 없이 진행")
        return None
    for root, dirs, files in os.walk(dest):
        if "odometry.csv" in files:
            return root
    return None


def _dist_polyline(p, line):
    """점 p 와 3D 폴리라인 사이 최소 거리 (m)"""
    best = float("inf")
    if not line:
        return best
    for a, b in list(zip(line, line[1:])) or [(line[0], line[0])]:
        ab = [b[i] - a[i] for i in range(3)]
        ap = [p[i] - a[i] for i in range(3)]
        L2 = sum(v * v for v in ab)
        t = max(0.0, min(1.0, sum(ab[i] * ap[i] for i in range(3)) / L2)) if L2 > 0 else 0.0
        best = min(best, sum((ap[i] - t * ab[i]) ** 2 for i in range(3)) ** 0.5)
    return best


def apply_user_marks(u, marks_path):
    """앱 미리보기에서 관을 탭해 고른 종류(marks.json kind=utility, ARKit 월드 = centerline_local 좌표)를 가장 가까운 관에 입힌다.
    색 추정보다 우선한다 (class_source="user"). 관 표면을 탭하므로 축에서 반지름 + 0.2 m 안이면 그 관이다. → (맞춘 수, 못 맞춘 수)"""
    try:
        marks = (json.load(open(marks_path, "r", encoding="utf-8")) or {}).get("marks") or []
    except (OSError, ValueError):
        return 0, 0
    marks = [m for m in marks if m.get("kind") == "utility" and m.get("class")
             and all(isinstance(m.get(k), (int, float)) for k in ("x", "y", "z"))]
    hit = miss = 0
    for m in marks:                                                 # 같은 관에 여러 번 탭하면 마지막 것이 이긴다
        p = (m["x"], m["y"], m["z"])
        best = None
        for x in u.get("utilities", []):
            line = x.get("centerline_local") or []
            if not line:
                continue
            d = _dist_polyline(p, line)
            if d <= (x.get("diameter_mm") or 100) / 2000 + 0.20 and (best is None or d < best[0]):
                best = (d, x)
        if best is None:
            miss += 1
            u.setdefault("user_marks_unmatched", []).append({"class": m["class"], "local": [round(v, 4) for v in p]})
            continue
        x = best[1]
        if x.get("class") != m["class"] and x.get("class_source") != "user":
            x["class_auto"] = x.get("class")                      # 자동 추정값은 남겨 둔다 (뷰어·보고서 비교용)
        x.update({"class": m["class"], "class_source": "user", "class_confidence": 1.0})
        if x.get("kind") == "pipe" and m["class"] in ("power", "telecom"):
            x["kind"] = "conduit"                                    # 전력·통신은 관이 아니라 관로 (엔진 _kind_for 와 같은 규칙)
        elif x.get("kind") == "conduit" and m["class"] not in ("power", "telecom", "unknown"):
            x["kind"] = "pipe"
        hit += 1
    if miss:
        u.setdefault("quality", {}).setdefault("warnings", []).append(f"user_mark_unmatched:{miss}")
    return hit, miss


def step_utilities(meta, out_dir, job_id, las=None, mesh=None, data_dir=None, georef=None):
    """굴착 기록(trench) 작업: utility_extract.py → utilities.json, utility_report.py → 조서·DXF·LandXML·GeoJSON·제출 동영상.
    서빙: <job>_utilities.json, <job>_util/<파일>. 모듈이 아직 없으면 건너뛴다 → (utilities_url, report_url)
    웹 굴착 기록(trench_post)은 GPU 워커 실측 묶음의 las·mesh·데이터 폴더·georef.json 을 넘긴다 (기본값 = 앱 녹화 경로)"""
    if not (meta.get("trench") or {}).get("mode"):
        return "", ""
    wd = CFG["worker_dir"]
    ext_py, rep_py = os.path.join(wd, "utility_extract.py"), os.path.join(wd, "utility_report.py")
    if not os.path.exists(ext_py):
        log("굴착 기록: 추출 모듈(utility_extract.py)이 아직 없음 → 건너뜀")
        return "", ""
    udir = os.path.join(out_dir, "utilities")
    os.makedirs(udir, exist_ok=True)
    jm = georef or os.path.join(meta["job_dir"], "job.json")
    if mesh is None:
        mesh = os.path.join(out_dir, "mesh_full.ply") if os.path.exists(os.path.join(out_dir, "mesh_full.ply")) else os.path.join(out_dir, "mesh.ply")
    cmd = [CFG["worker_python"], "-I", ext_py, "--las", las or os.path.join(out_dir, "scan.las"), "--georef", jm, "--out", udir]
    if mesh and os.path.exists(mesh):                               # 메시가 있으면 메시 경로(천장 구분·밀도 고름), 없으면 LAS
        cmd += ["--mesh", mesh]
    with open(os.path.join(out_dir, "utility_stdout.log"), "a", encoding="utf-8") as lf:
        proc = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, text=True, timeout=1800)
    up = os.path.join(udir, "utilities.json")
    if proc.returncode != 0 or not os.path.exists(up):
        log("굴착 기록: 관 추출 실패 (utility_stdout.log 확인)")
        return "", ""
    u = json.load(open(up, "r", encoding="utf-8"))
    own_data = not data_dir
    data = data_dir if data_dir else _extract_dataset(meta.get("scan_zip"), os.path.join(udir, "_data"))
    if data and os.path.exists(os.path.join(data, "marks.json")):
        hit, miss = apply_user_marks(u, os.path.join(data, "marks.json"))
        if hit or miss:
            log(f"굴착 기록: 촬영 때 고른 관 종류 {hit}개 반영" + (f", {miss}개는 가까운 관 없음" if miss else ""))
    u["job_id"] = job_id
    u.setdefault("local", {})["glb"] = f"{job_id}.glb"             # utilities.json 과 같은 폴더 기준 상대 주소 (계약 v0.2)
    if meta.get("title"):
        u["title"] = meta["title"]
    permit = meta.get("permit") or {}
    if permit:
        u["permit"] = permit                                        # 굴착 허가 번호·관리기관·작업자 (업로드 필드)
    serve, url = CFG["glb_serve_dir"], CFG["glb_serve_url"]
    for path in (up, os.path.join(serve, f"{job_id}_utilities.json")):   # 산출물 생성기도 같은 내용을 읽게 한다
        with open(path, "w", encoding="utf-8") as f:
            json.dump(u, f, ensure_ascii=False)
    util_url = f"{url}/{job_id}_utilities.json"
    log(f"굴착 기록: 관 {len(u.get('utilities', []))}개 → {util_url}")
    report_url = ""
    if not u.get("utilities") and not u.get("trench"):
        log("굴착 기록: 굴착·관을 찾지 못함 → 산출물 생략")       # 조서에 쓸 내용이 없다 (실패 아님)
    elif os.path.exists(rep_py):
        rdir = os.path.join(udir, "report")
        cmd = [CFG["worker_python"], "-I", rep_py, "--utilities", up, "--job-dir", meta["job_dir"], "--out", rdir]
        if data:
            cmd += ["--data", data]                                 # 제출 동영상(rgb.mp4)·현장 사진(hires/)
        title = meta.get("title") or ""
        if permit.get("permit_no"):
            title = (title + " · " if title else "") + f"굴착 허가 {permit['permit_no']}"
        if permit.get("owner_org"):
            title += f" ({permit['owner_org']})"
        if title:
            cmd += ["--title", title]
        if permit.get("surveyor"):
            cmd += ["--surveyor", permit["surveyor"]]
        if permit.get("org"):
            cmd += ["--org", permit["org"]]
        with open(os.path.join(out_dir, "utility_stdout.log"), "a", encoding="utf-8") as lf:
            proc = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, text=True, timeout=1800)
        if proc.returncode == 0 and os.path.isdir(rdir):
            dest = os.path.join(serve, f"{job_id}_util")
            shutil.rmtree(dest, ignore_errors=True)
            shutil.copytree(rdir, dest)
            if os.path.exists(os.path.join(dest, "report.html")):
                report_url = f"{url}/{job_id}_util/report.html"
            log(f"굴착 기록: 산출물 {sorted(os.listdir(dest))}")
        else:
            log("굴착 기록: 산출물 생성 실패 (utility_stdout.log 확인)")
    if data and own_data:
        shutil.rmtree(os.path.join(udir, "_data"), ignore_errors=True)   # 원본은 scan zip 에 그대로 있다
    return util_url, report_url


# ── 웹 굴착 기록: GPU 워커 실측 묶음 → 굴착 후처리 (docs/web_trench_contract.md 3·4절) ─────────────────
BUNDLE_FILES = {"rgb.mp4", "odometry.csv", "frame_quality.csv", "camera_matrix.csv", "mesh.ply", "mesh.glb", "scan.las",
                "marks.json", "scale.json", "georef.json"}               # splat_jobs.py 와 같은 목록 (업로드 때 이미 검사함)
BUNDLE_DIRS = {"hires": (".jpg", ".jpeg", ".png", ".json")}
TP_SKIP_SCALE = "기준판을 찾지 못해 실측 산출물을 만들지 않았습니다 — 3D 보기만 제공"


def _unpack_bundle(zip_path, dest):
    """trench_bundle.zip 을 dest 에 푼다. 허용 목록 밖·절대 경로·'..' 는 ValueError (splat_jobs.check_bundle 과 같은 규칙)"""
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest)
    with zipfile.ZipFile(zip_path) as zf:
        members = []
        for zi in zf.infolist():
            n = zi.filename.replace("\\", "/")
            parts = n.split("/")
            if n.startswith("/") or (len(n) > 1 and n[1] == ":") or ".." in parts or "." in parts:
                raise ValueError(f"묶음에 허용되지 않는 경로: {zi.filename!r}")
            if zi.is_dir():
                if n.rstrip("/") not in BUNDLE_DIRS:
                    raise ValueError(f"묶음에 허용되지 않는 폴더: {zi.filename!r}")
                continue
            ok = (len(parts) == 1 and n in BUNDLE_FILES) or (
                len(parts) == 2 and parts[0] in BUNDLE_DIRS and parts[1] and not parts[1].startswith(".")
                and os.path.splitext(parts[1])[1].lower() in BUNDLE_DIRS[parts[0]])
            if not ok:
                raise ValueError(f"묶음에 허용되지 않는 파일: {zi.filename!r}")
            members.append(zi)
        zf.extractall(dest, members=members)
    return dest


def step_update_point(oid, attrs):
    """scan_points 의 기존 점(objectid) 속성을 고친다 (레이어에 있는 필드만)"""
    layer = CFG["points_layer_url"]
    token = get_token(CFG["server_url"])
    info = http_json(layer, {"f": "json", "token": token})
    fields = {f.get("name", "").lower() for f in info.get("fields", [])}
    a = {k: v for k, v in attrs.items() if k.lower() in fields}
    a["objectid"] = int(oid)
    out = http_json(layer + "/updateFeatures", {"features": json.dumps([{"attributes": a}]), "f": "json", "token": token})
    res = (out.get("updateResults") or [{}])[0]
    if not res.get("success"):
        raise RuntimeError("scan_points 갱신 실패: " + str(res.get("error")))
    log(f"scan_points OID {oid} 갱신: {sorted(a)}")


def trench_post(meta, q):
    """큐 kind=trench_post: GPU 워커가 올린 실측 묶음(trench_bundle.zip)으로
    ① mesh.glb 서빙(<job>.glb, 메시 탭) ② 지도 점 glb_url 갱신 ③ 축척이 있으면 관 추출·조서.
    스플랫·3D 보기는 이미 끝난 작업이므로 여기서 실패해도 status 는 done 으로 두고 trench_post=failed 로 알린다."""
    job_id, job_dir = meta["job_id"], meta["job_dir"]
    out_dir = os.path.join(job_dir, "out")
    os.makedirs(out_dir, exist_ok=True)
    qd = q.read()
    q.update(status="processing", step=7, trench_post="processing", trench_post_message="굴착 산출물 만드는 중",
             message="굴착 산출물 만드는 중 (3D 는 먼저 볼 수 있음)")
    upd = {}
    try:
        bundle = qd.get("trench_bundle_path") or os.path.join(job_dir, "trench_bundle.zip")
        data = _unpack_bundle(bundle, os.path.join(out_dir, "trench_data"))
        scale = json.load(open(os.path.join(data, "scale.json"), "r", encoding="utf-8"))
        gj = os.path.join(data, "georef.json")
        geo = json.load(open(gj, "r", encoding="utf-8"))
        old = meta.get("georef") or {}
        g = {"lon": float(geo.get("lon", old.get("lon"))), "lat": float(geo.get("lat", old.get("lat"))),
             "elev": float(geo.get("elev", old.get("elev", 0.0)) or 0.0), "heading": float(geo.get("heading", old.get("heading", 0.0)) or 0.0)}
        meta.setdefault("georef_upload", old)                       # 촬영 페이지가 보낸 첫 위치는 남겨 둔다
        meta["georef"] = g                                          # 워커가 GPS 평균·나침반으로 다시 정한 값 (조서도 이것을 읽는다)
        meta["trench"] = dict(meta.get("trench") or {"mode": 1}, scale_method=scale.get("method"),
                              scale_residual_mm=scale.get("residual_mm"), georef_source=geo.get("source"))
        with open(os.path.join(job_dir, "job.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        glb_url = step_glb(os.path.join(data, "mesh.glb"), job_id)
        upd["glb_url"] = glb_url
        las = os.path.join(data, "scan.las")
        las_info = step_las(las) if os.path.exists(las) else None
        if CFG.get("portal_enabled", True):
            try:
                oid = qd.get("objectid")
                if oid:
                    attrs = {"glb_url": glb_url}
                    if las_info:
                        attrs.update(coord_x=las_info["coord_x"], coord_y=las_info["coord_y"], coord_z=las_info["coord_z"])
                    step_update_point(oid, attrs)
                elif las_info:
                    upd["objectid"] = step_register(meta, las_info, glb_url, "", "", "", qd.get("thumb_url") or "")
            except Exception as e:                                  # 지도 점은 부가 — 산출물은 계속 만든다
                log(f"지도 점 갱신 생략: {e}")
        method = (scale.get("method") or "none").lower()
        if method == "none" or not las_info:
            state = "skipped"
            msg = TP_SKIP_SCALE if method == "none" else "실측 점군(scan.las)이 묶음에 없어 관 추출을 하지 않았습니다 — 3D 보기만 제공"
            log("굴착 후처리: " + msg)
            # 앞선 묶음이 만든 산출물이 남아 있으면 지운다 (사이트가 <job>_utilities.json 이 있으면 ⛏ 탭을 보이므로)
            serve = CFG["glb_serve_dir"]
            stale = os.path.join(serve, f"{job_id}_utilities.json")
            if os.path.exists(stale):
                os.remove(stale)
            shutil.rmtree(os.path.join(serve, f"{job_id}_util"), ignore_errors=True)
            upd.update(utilities_url=None, utility_report_url=None)
        else:
            mesh = os.path.join(data, "mesh.ply")
            util_url, rep_url = step_utilities(meta, out_dir, job_id, las=las, mesh=mesh if os.path.exists(mesh) else "",
                                               data_dir=data, georef=gj)
            upd.update(utilities_url=util_url or None, utility_report_url=rep_url or None)
            if util_url:
                try:
                    n = len(json.load(open(os.path.join(CFG["glb_serve_dir"], f"{job_id}_utilities.json"), "r", encoding="utf-8")).get("utilities") or [])
                except Exception:
                    n = 0
                state = "done"
                msg = f"굴착 산출물 완료 — 관 {n}개" + ("" if rep_url else " (조서 없음: 굴착·관을 찾지 못함)")
            else:
                state, msg = "failed", "관 추출에 실패했습니다 (서버 로그 확인)"
        upd.update(trench=dict(qd.get("trench") or {"mode": 1}, scale_method=method))
        q.update(status="done", step=7, kind=None, trench_post=state, trench_post_message=msg, message=msg, **upd)
        log(f"굴착 후처리 {state}: {msg}")
    except Exception as e:
        import traceback
        log("굴착 후처리 실패: " + str(e))
        print(traceback.format_exc(), flush=True)
        q.update(status="done", step=7, kind=None, trench_post="failed",
                 trench_post_message=("굴착 산출물을 만들지 못했습니다: " + str(e))[:300], message="3D 완료 (굴착 산출물 실패)", **upd)


def step_slpk(glb_path, out_dir, las_info, service_name, heading=0.0):
    """GLB → OBJ(heading 회전) → arcpy Import3DFiles(LAS 범위 중심에 배치) → SLPK. 실패하면 None."""
    py = CFG.get("arcgis_python", "")
    if not CFG.get("slpk_enabled", True) or not py or not os.path.exists(py):
        log("SLPK 건너뜀 (slpk_enabled=false 또는 ArcGIS Python 없음)")
        return None
    prev = [f for f in os.listdir(out_dir) if f.endswith(".slpk") and os.path.getsize(os.path.join(out_dir, f)) > 100_000]
    if prev:
        slpk = os.path.join(out_dir, sorted(prev)[-1])
        log(f"SLPK 가 이미 있어 재사용 (재시도): {os.path.basename(slpk)}")
        return slpk
    obj_dir = os.path.join(out_dir, "obj")
    conv = [CFG["worker_python"], "-I", os.path.join(CFG["worker_dir"], "glb_to_obj.py"), "--glb", glb_path,
            "--out", obj_dir, "--heading", str(heading), "--jpeg-quality", str(CFG.get("texture", {}).get("jpeg_quality", 85))]
    b = las_info["bbox"]
    cx, cy, cz = (b[0] + b[3]) / 2, (b[1] + b[4]) / 2, (b[2] + b[5]) / 2
    slpk = os.path.join(out_dir, service_name + ".slpk")
    cmd = [py, os.path.join(HERE, "slpk_step.py"), obj_dir, slpk, str(cx), str(cy), str(cz), str(CFG.get("utm_epsg", 32652))]
    with open(os.path.join(out_dir, "slpk_step.log"), "a", encoding="utf-8") as lf:
        proc = subprocess.run(conv, stdout=lf, stderr=subprocess.STDOUT, text=True, timeout=600)
        if proc.returncode != 0:
            log("GLB→OBJ 변환 실패 → SLPK 건너뜀 (slpk_step.log 확인)")
            return None
        proc = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, text=True, timeout=1500,
                              env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    if proc.returncode != 0 or not os.path.exists(slpk):
        log("SLPK 생성 실패 → 건너뜀 (slpk_step.log 확인)")
        return None
    log(f"SLPK: {slpk} ({os.path.getsize(slpk) / 1e6:.1f} MB)")
    return slpk


def find_items(token, service_name, slpk_name):
    """발행 뒤 Portal 에서 SLPK 아이템과 Scene 서비스 아이템을 찾는다 → (slpk_item_id, scene_item_id, scene_url)"""
    user, portal = CFG["portal_user"], CFG["portal_url"]
    found = http_json(f"{portal}/sharing/rest/search",
                      {"q": f'owner:{user} AND (type:"Scene Package" OR type:"Scene Service")', "num": 100,
                       "sortField": "modified", "sortOrder": "desc", "f": "json", "token": token})
    slpk_id = scene_id = scene_url = ""
    # SLPK 는 SharePackage 가 올린 것('ArcGIS Pro' 키워드)을 우선
    pkgs = [r for r in found.get("results", []) if r.get("type") == "Scene Package" and r.get("name") == slpk_name]
    pkgs.sort(key=lambda r: 0 if "ArcGIS Pro" in (r.get("typeKeywords") or []) else 1)
    if pkgs:
        slpk_id = pkgs[0]["id"]
    for r in found.get("results", []):
        if r.get("type") == "Scene Service" and (r.get("title") == service_name or service_name in (r.get("url") or "")) and not scene_id:
            scene_id, scene_url = r["id"], r.get("url", "")
    return slpk_id, scene_id, scene_url


def scan_folder_id(token):
    """Portal 사용자 폴더(설정 portal_folder, 기본 'kgeoscan')의 id. 없으면 만든다. 스캔 아이템은 모두 여기에 모은다"""
    user, portal, name = CFG["portal_user"], CFG["portal_url"], CFG.get("portal_folder", "kgeoscan")
    info = http_json(f"{portal}/sharing/rest/content/users/{user}", {"f": "json", "num": 1, "token": token})
    for f in info.get("folders", []):
        if f.get("title") == name:
            return f["id"]
    return http_json(f"{portal}/sharing/rest/content/users/{user}/createFolder", {"title": name, "f": "json", "token": token})["folder"]["id"]


def move_to_scan_folder(token, item_ids):
    """SharePackage 는 사용자 루트 폴더에 올린다 → 발행 뒤 스캔 폴더로 옮긴다 (아이템 id·서비스 주소는 그대로)"""
    ids = [i for i in item_ids if i]
    if not ids:
        return
    user, portal = CFG["portal_user"], CFG["portal_url"]
    fid = scan_folder_id(token)
    out = http_json(f"{portal}/sharing/rest/content/users/{user}/moveItems",
                    {"items": ",".join(ids), "folder": fid, "f": "json", "token": token})
    bad = [r for r in out.get("results", []) if not r.get("success")]
    log(f"Portal 폴더 '{CFG.get('portal_folder', 'kgeoscan')}' 로 이동: {len(ids) - len(bad)}/{len(ids)}" + (f" 실패 {bad}" if bad else ""))


def step_publish(slpk, service_name, title):
    user, portal = CFG["portal_user"], CFG["portal_url"]
    token = get_token(portal)
    slpk_name = os.path.basename(slpk)
    # 이미 발행돼 있으면(재시도) 재사용
    slpk_item_id, scene_item_id, scene_url = find_items(token, service_name, slpk_name)
    if scene_item_id:
        log(f"Scene 아이템 재사용: {scene_item_id}")
    else:
        py = CFG.get("arcgis_python", "")
        if not py or not os.path.exists(py):
            raise RuntimeError("ArcGIS Python 이 없어 발행할 수 없습니다")
        env = dict(os.environ, PYTHONIOENCODING="utf-8", KGEOSCAN_PORTAL_URL=portal, KGEOSCAN_PORTAL_USER=user,
                   KGEOSCAN_PORTAL_PASSWORD=CFG["portal_password"])
        out_dir = os.path.dirname(slpk)
        with open(os.path.join(out_dir, "publish.log"), "a", encoding="utf-8") as lf:
            proc = subprocess.run([py, os.path.join(HERE, "slpk_step.py"), "--publish", slpk, title],
                                  stdout=lf, stderr=subprocess.STDOUT, text=True, timeout=1500, env=env)
        if proc.returncode != 0:
            tail = open(os.path.join(out_dir, "publish.log"), encoding="utf-8", errors="replace").read()[-800:]
            raise RuntimeError("SharePackage 발행 실패: " + tail.strip().splitlines()[-1] if tail.strip() else "SharePackage 발행 실패")
        log(f"SharePackage 발행 완료 ({service_name})")
        for _ in range(12):   # 색인 반영 대기
            slpk_item_id, scene_item_id, scene_url = find_items(token, service_name, slpk_name)
            if scene_item_id:
                break
            time.sleep(10)
        if not scene_item_id:
            raise RuntimeError("발행은 됐지만 Portal 에서 Scene 아이템을 찾지 못함: " + service_name)
    for iid in [i for i in (slpk_item_id, scene_item_id) if i]:
        try:
            http_json(f"{portal}/sharing/rest/content/users/{user}/items/{iid}/share",
                      {"everyone": "true" if _SHARE_EVERYONE else "false", "org": "true", "f": "json", "token": token})
        except Exception as e:
            log(f"공유 설정 생략 ({iid}): {e}")
    try:
        move_to_scan_folder(token, [slpk_item_id, scene_item_id])
    except Exception as e:                                 # 폴더 정리는 부가 기능 — 실패해도 스캔은 계속
        log(f"Portal 폴더 이동 생략: {e}")
    log(f"Scene 아이템: {scene_item_id} → {scene_url}")
    return slpk_item_id, scene_item_id, scene_url


def step_publish_rest(slpk, service_name, title):
    """(미사용) REST publish 는 이 Enterprise 에서 'Unable to determine Service Type' 을 내서 SharePackage 로 대체"""
    user, portal = CFG["portal_user"], CFG["portal_url"]
    token = get_token(portal)
    folder = CFG.get("portal_folder_id", "")
    base = f"{portal}/sharing/rest/content/users/{user}" + (f"/{folder}" if folder else "")
    # 재시도 때 같은 SLPK 아이템이 이미 올라가 있으면 재사용 (중복 아이템 방지)
    slpk_item_id = None
    try:
        found = http_json(f"{portal}/sharing/rest/search",
                          {"q": f'owner:{user} AND type:"Scene Package"', "num": 100, "sortField": "modified",
                           "sortOrder": "desc", "f": "json", "token": token})
        match = next((r for r in found.get("results", []) if r.get("name") == os.path.basename(slpk)), None)
        if match:
            slpk_item_id = match["id"]
            log(f"SLPK 아이템 재사용: {slpk_item_id}")
    except Exception as e:
        log(f"아이템 검색 생략: {e}")
    if not slpk_item_id:
        with open(slpk, "rb") as f:
            blob = f.read()
        item = http_json(base + "/addItem", {"title": title, "type": "Scene Package", "typeKeywords": "slpk,Scene Package",
                                             "tags": "kgeoScan,LiDAR", "f": "json", "token": token},
                         files={"file": (os.path.basename(slpk), blob)})
        slpk_item_id = item["id"]
        log(f"SLPK 아이템: {slpk_item_id}")
    # fileType 은 소문자 'scenepackage' (대소문자가 다르면 'Unable to determine Service Type')
    pub = http_json(f"{portal}/sharing/rest/content/users/{user}/publish",
                    {"itemID": slpk_item_id, "fileType": "scenepackage", "f": "json", "token": token,
                     "publishParameters": json.dumps({"name": service_name})})
    svc = pub["services"][0]
    scene_item_id, job_id = svc.get("serviceItemId"), svc.get("jobId")
    # 발행 완료 대기
    for _ in range(90):
        st = http_json(f"{portal}/sharing/rest/content/users/{user}/items/{scene_item_id}/status",
                       {"jobId": job_id, "jobType": "publish", "f": "json", "token": token})
        if st.get("status") == "completed":
            break
        if st.get("status") == "failed":
            raise RuntimeError("Scene 서비스 발행 실패: " + str(st.get("statusMessage")))
        time.sleep(10)
    scene = http_json(f"{portal}/sharing/rest/content/items/{scene_item_id}", {"f": "json", "token": token})
    scene_url = scene.get("url", "")
    for iid in (slpk_item_id, scene_item_id):
        http_json(f"{portal}/sharing/rest/content/users/{user}/items/{iid}/share",
                  {"everyone": "true" if _SHARE_EVERYONE else "false", "org": "true", "f": "json", "token": token})
    log(f"Scene 아이템: {scene_item_id} → {scene_url}")
    return slpk_item_id, scene_item_id, scene_url


def step_register(meta, las_info, glb_url, slpk_item_id, scene_item_id, scene_url, thumb_url="", ortho_url="", pano_url=""):
    vis = current_visibility(meta)
    if vis != "public":                                   # 링크 공유·비공개: 지도·목록에 넣지 않는다 (산출물은 그대로 서빙)
        log(f"공개 범위 {vis}: 지도(scan_points) 등록 안 함")
        return None
    layer = CFG["points_layer_url"]
    token = get_token(CFG["server_url"])
    info = http_json(layer, {"f": "json", "token": token})
    layer_fields = {f.get("name", "").lower() for f in info.get("fields", [])}   # 새 필드(scan_type, thumb_url)가 아직 없어도 등록되게
    wkid = (info.get("extent", {}).get("spatialReference") or info.get("spatialReference") or {}).get("latestWkid") \
        or (info.get("extent", {}).get("spatialReference") or {}).get("wkid", 4326)
    lon, lat = wgs84_from_utm(las_info["coord_x"], las_info["coord_y"], CFG.get("utm_epsg", 32652))
    if int(wkid) in (102100, 3857):
        from pyproj import Transformer
        gx, gy = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True).transform(lon, lat)
    else:
        gx, gy, wkid = lon, lat, 4326
    feature = {"geometry": {"x": gx, "y": gy, "spatialReference": {"wkid": int(wkid)}},
               "attributes": {"scan_title": meta["title"], "author": meta.get("author", CFG["portal_user"]),
                              "pub_date": int(time.time() * 1000), "note": meta.get("note", ""),
                              "coord_x": las_info["coord_x"], "coord_y": las_info["coord_y"], "coord_z": las_info["coord_z"],
                              "scene_item_id": scene_item_id, "scene_url": scene_url,
                              "slpk_item_id": slpk_item_id, "glb_url": glb_url}}
    if "scan_type" in layer_fields:
        feature["attributes"]["scan_type"] = meta.get("scan_type") or "home"
    if "thumb_url" in layer_fields:
        feature["attributes"]["thumb_url"] = thumb_url or None
    if "ortho_url" in layer_fields and ortho_url:
        feature["attributes"]["ortho_url"] = ortho_url
    if "pano_url" in layer_fields and pano_url:            # 레이어에 필드가 없으면 뷰어가 thumb_url(<job>.jpg)에서 <job>_pano/tour.json 을 찾는다
        feature["attributes"]["pano_url"] = pano_url
    out = http_json(layer + "/addFeatures", {"features": json.dumps([feature]), "f": "json", "token": token})
    res = out["addResults"][0]
    if not res.get("success"):
        raise RuntimeError("scan_points 등록 실패: " + str(res.get("error")))
    log(f"scan_points OID {res.get('objectId')} ({lon:.5f}, {lat:.5f})")
    return res.get("objectId")


def splat_wanted(meta):
    """GPU 스플랫 워커에 넘길 작업인가: 설정 splat.enabled, Stray 원본, 유형이 splat.scan_types 에 있거나 업로드 때 splat=1 요청"""
    sp = CFG.get("splat") or {}
    if not sp.get("enabled") or meta.get("mode") not in ("stray", "objcap", "video", "photos"):
        return False
    if meta.get("splat_requested") or meta.get("mode") in ("video", "photos"):
        return True
    return (meta.get("scan_type") or "home") in (sp.get("scan_types") or ["survey"])


def splat_fields(meta, q):
    """완료 시 큐 파일에 넣을 스플랫 필드. 이미 진행·완료된 스플랫(재시도)은 건드리지 않는다."""
    if q.read().get("splat_status") in ("pending", "processing", "done"):
        return {}
    if splat_wanted(meta):
        log("스플랫: GPU 워커 대기열에 등록 (splat_status=pending)")
        if meta.get("mode") in ("video", "photos"):        # 영상·사진만 있음: 워커가 카메라 위치(SfM)부터 계산한다
            return {"splat_status": "pending", "splat_kind": "video", "splat_message": "3D 생성 대기 중 (GPU: 카메라 위치 계산 → 스플랫)"}
        return {"splat_status": "pending", "splat_message": "스플랫 대기 중 (GPU 워커)"}
    if meta.get("mode") in ("video", "photos"):
        log("스플랫이 꺼져 있어(splat.enabled=false) 영상 3D 를 만들 수 없음")
        return {"splat_status": "failed", "splat_message": "3D 생성 기능이 꺼져 있습니다 (서버 설정)"}
    return {}


def video_job(meta, q, out_dir, job_id):
    """mode=video (웹 3D 현장조사): 영상 썸네일 → GPS 위치에 지도 점 등록 → GPU 스플랫 대기열.
    서버는 융합·GLB·SLPK 를 만들지 않는다 (LiDAR·카메라 자세가 없어서 GPU 워커가 SfM 부터 한다, docs/video3d_contract.md)"""
    is_video = meta.get("mode") == "video"
    q.update(step=1, message=("영상" if is_video else "사진") + " 품질 검사 중")
    thumb = os.path.join(out_dir, "thumb.jpg")
    # 업로드 직후 품질 검사 (흔들림·속도·겹침·밝기) → 큐의 quality 로 바로 알린다: 촬영 페이지가 "다시 찍기"를 권할 수 있게
    qp = os.path.join(out_dir, "quality.json")
    src = ["--video", meta["video_path"]] if is_video else ["--photos", meta.get("photos_dir", "")]
    try:
        with open(os.path.join(out_dir, "worker_stdout.log"), "a", encoding="utf-8") as lf:
            subprocess.run([CFG["worker_python"], "-I", os.path.join(CFG["worker_dir"], "media_check.py")] + src + ["--out", qp, "--thumb", thumb],
                           stdout=lf, stderr=subprocess.STDOUT, text=True, timeout=600)
        quality = json.load(open(qp, "r", encoding="utf-8"))
        q.update(quality=quality)
        log(f"품질 검사: {quality.get('grade')} ({quality.get('score')}) {quality.get('summary')}")
    except Exception as e:
        log(f"품질 검사 생략: {e}")
    if not os.path.exists(thumb) and is_video and meta.get("video_path") and os.path.exists(meta["video_path"]):
        cmd = [CFG["worker_python"], "-I", os.path.join(CFG["worker_dir"], "thumbnail.py"), "--video", meta["video_path"], "--out", thumb]
        try:
            with open(os.path.join(out_dir, "worker_stdout.log"), "a", encoding="utf-8") as lf:
                subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, text=True, timeout=300)
        except Exception as e:
            log(f"영상 썸네일 생략: {e}")
    thumb_url = step_thumb(meta, out_dir, job_id)
    g = meta["georef"]
    from pyproj import Transformer
    x, y = Transformer.from_crs("EPSG:4326", f"EPSG:{CFG.get('utm_epsg', 32652)}", always_xy=True).transform(g["lon"], g["lat"])
    z = float(g.get("elev", 0.0))
    las_info = dict(points=0, coord_x=x, coord_y=y, coord_z=z, bbox=[x, y, z, x, y, z])
    oid = None
    if CFG.get("portal_enabled", True):
        q.update(step=6, message="지도에 등록 중", thumb_url=thumb_url or None)
        oid = step_register(meta, las_info, "", "", "", "", thumb_url)
    extra = {"objectid": oid} if oid else {}
    extra.update(splat_fields(meta, q))
    with open(os.path.join(out_dir, "pipeline_result.json"), "w", encoding="utf-8") as f:
        json.dump(dict(job_id=job_id, mode=meta.get("mode"), thumb_url=thumb_url, objectid=oid, seconds=round(time.time() - T0, 1)), f, ensure_ascii=False, indent=2)
    what = "영상" if is_video else f"사진 {meta.get('photo_count', '')}장"
    q.update(step=7, status="done", message=f"{what} 등록 완료 — 3D 생성 대기(GPU)" if extra.get("splat_status") == "pending" else f"{what} 등록 완료",
             thumb_url=thumb_url or None, **extra)
    log(f"웹 3D 작업 완료 {round(time.time() - T0, 1)}s")


def _run_stitch(cmd, q, log_path, timeout):
    """pano_stitch.py 실행: stdout 의 'PROGRESS <0-100> <문구>' 를 큐 메시지로 (1초에 한 번까지). → (종료 코드, stderr 마지막 줄)"""
    import threading
    err_path = log_path + ".err"
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    with open(log_path, "a", encoding="utf-8") as lf, open(err_path, "w", encoding="utf-8") as ef:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=ef, text=True, encoding="utf-8", errors="replace", env=env)
        killed = []

        def _kill():
            killed.append(1)
            proc.kill()
        timer = threading.Timer(timeout, _kill)
        timer.start()
        last = 0.0
        try:
            for line in proc.stdout:
                lf.write(line)
                if line.startswith("PROGRESS "):
                    parts = line.rstrip("\r\n").split(" ", 2)
                    try:
                        pct = max(0, min(100, int(float(parts[1]))))
                    except (IndexError, ValueError):
                        continue
                    text = parts[2] if len(parts) > 2 else ""
                    if time.time() - last >= 1.0 or pct >= 100:
                        last = time.time()
                        q.update(message=f"VR 투어 만드는 중 {pct}% — {text}"[:200], pano_message=text[:200], pano_progress=pct)
            rc = proc.wait()
        finally:
            timer.cancel()
    try:
        tail = [l.strip() for l in open(err_path, "r", encoding="utf-8", errors="replace") if l.strip()]
    except OSError:
        tail = []
    _run_stitch.tail = tail[-20:]                     # 실패 원인 보기용 (status.py pano_stderr)
    if killed:
        return -1, "VR 투어 만들기가 시간 안에 끝나지 않았습니다"
    return rc, (tail[-1] if tail else "")


def pano_job(meta, q, out_dir, job_id):
    """mode=pano (VR 투어, docs/pano_contract.md 2절): worker/pano_stitch.py 로 지점마다 360° 등장방형 → <job>_pano/ 서빙
    → GPS 위치에 지도 점 등록 (GLB 없음). 일부 지점 실패는 성공으로 두고 tour.json.failed 로 알린다."""
    pano_out = os.path.join(out_dir, "pano")
    shutil.rmtree(pano_out, ignore_errors=True)
    n_spots = int((meta.get("pano") or {}).get("spots") or 1)
    q.update(step=1, message=f"VR 투어 만드는 중 (지점 {n_spots}곳, 지점마다 30초 안팎)", pano_status="processing",
             pano_message="360° 사진 이어 붙이는 중", pano_progress=0)
    cmd = [CFG["worker_python"], "-I", os.path.join(CFG["worker_dir"], "pano_stitch.py"), meta["pano_zip"],
           "--out", pano_out, "--title", meta.get("title") or ""]
    # 지점당 240초: 이 PC 실측 20~35초(초광각 10~20초), 서버 CPU 가 느려도 여유 (pano 세션 권고 2026-11-12)
    timeout = int(min(max(600, 240 * n_spots), max(600, CFG.get("pipeline_timeout_sec", 1800) - 120)))
    rc, last_err = _run_stitch(cmd, q, os.path.join(out_dir, "pano_stdout.log"), timeout)
    tour_path = os.path.join(pano_out, "tour.json")
    if rc != 0 or not os.path.exists(tour_path):
        msg = last_err if rc == 2 and last_err else (last_err if rc == -1 else "VR 투어를 만들지 못했습니다 (이어 붙이기 오류)")
        q.update(pano_status="failed", pano_message=msg[:300],
                 pano_stderr=(f"exit {rc}\n" + "\n".join(getattr(_run_stitch, "tail", []) or []))[-4000:])
        log(f"pano_stitch 실패 (종료 코드 {rc}): {last_err}")
        raise RuntimeError(msg)
    tour = json.load(open(tour_path, "r", encoding="utf-8"))
    spots, failed = tour.get("spots") or [], tour.get("failed") or []
    if not spots:
        msg = "모든 지점을 이어 붙이지 못했습니다 — " + "; ".join(str(f.get("error") or "") for f in failed[:2])[:200]
        q.update(pano_status="failed", pano_message=msg)
        raise RuntimeError(msg)
    serve = os.path.join(CFG["glb_serve_dir"], f"{job_id}_pano")
    shutil.rmtree(serve, ignore_errors=True)
    shutil.copytree(pano_out, serve)
    pano_url = f"{CFG['glb_serve_url']}/{job_id}_pano/tour.json"
    log(f"VR 투어 서빙: {pano_url} (지점 {len(spots)}곳, 실패 {len(failed)}곳)")
    first = next((s for s in spots if s.get("id") == tour.get("start")), spots[0])
    if first.get("thumb") and os.path.exists(os.path.join(pano_out, first["thumb"])):
        shutil.copy2(os.path.join(pano_out, first["thumb"]), os.path.join(out_dir, "thumb.jpg"))
    thumb_url = step_thumb(meta, out_dir, job_id)
    g = meta["georef"]
    from pyproj import Transformer
    x, y = Transformer.from_crs("EPSG:4326", f"EPSG:{CFG.get('utm_epsg', 32652)}", always_xy=True).transform(g["lon"], g["lat"])
    z = float(g.get("elev", 0.0))
    las_info = dict(points=0, coord_x=x, coord_y=y, coord_z=z, bbox=[x, y, z, x, y, z])
    oid = None
    if CFG.get("portal_enabled", True):
        q.update(step=6, message="지도에 등록 중", thumb_url=thumb_url or None)
        oid = step_register(meta, las_info, "", "", "", "", thumb_url, pano_url=pano_url)
    msg = f"VR 투어 완료 — 지점 {len(spots)}곳" + (f" (이어 붙이지 못한 지점 {len(failed)}곳)" if failed else "")
    with open(os.path.join(out_dir, "pipeline_result.json"), "w", encoding="utf-8") as f:
        json.dump(dict(job_id=job_id, mode="pano", pano_url=pano_url, thumb_url=thumb_url, objectid=oid, spots=len(spots),
                       failed=len(failed), seconds=round(time.time() - T0, 1)), f, ensure_ascii=False, indent=2)
    q.update(step=7, status="done", message=msg, pano_status="done", pano_message=msg, pano_url=pano_url, pano_progress=100,
             thumb_url=thumb_url or None, **({"objectid": oid} if oid else {}))
    log(f"VR 투어 작업 완료 {round(time.time() - T0, 1)}s")


def step_delete_point(oid):
    layer = CFG["points_layer_url"]
    token = get_token(CFG["server_url"])
    out = http_json(layer + "/deleteFeatures", {"objectIds": str(int(oid)), "f": "json", "token": token})
    res = (out.get("deleteResults") or [{}])[0]
    if not res.get("success"):
        raise RuntimeError("scan_points 삭제 실패: " + str(res.get("error")))
    log(f"scan_points OID {oid} 삭제 (공개 범위 바뀜)")


def _point_oids_for_job(job_id):
    """scan_points 에서 이 작업의 점 objectid 들 (thumb_url·glb_url·splat_url 에 작업 번호가 든 것).
    재처리(retry)로 큐의 objectid 를 잃은 옛 점까지 찾는다 (2026-11-12 82f7603b 가 지도에 남은 일)"""
    if not re.fullmatch(r"[0-9a-f]{8}", str(job_id or "")):
        return []
    layer = CFG["points_layer_url"]
    token = get_token(CFG["server_url"])
    where = " OR ".join(f"{f} LIKE '%{job_id}%'" for f in ("thumb_url", "glb_url"))
    out = http_json(layer + "/query", {"where": where, "outFields": "objectid", "returnGeometry": "false", "f": "json", "token": token})
    return [int(f["attributes"]["objectid"]) for f in out.get("features") or [] if (f.get("attributes") or {}).get("objectid") is not None]


def share_scene_items(item_ids, everyone):
    user, portal = CFG["portal_user"], CFG["portal_url"]
    token = get_token(portal)
    for iid in [i for i in item_ids if i]:
        try:
            http_json(f"{portal}/sharing/rest/content/users/{user}/items/{iid}/share",
                      {"everyone": "true" if everyone else "false", "org": "true", "f": "json", "token": token})
            log(f"Portal 아이템 {iid} 공유: {'모두' if everyone else '조직만'}")
        except Exception as e:
            log(f"공유 설정 생략 ({iid}): {e}")


def _las_info_for(meta, result):
    """다시 등록할 때의 좌표: 처리 결과(pipeline_result.json)의 las, 없으면 업로드 위치(georef)"""
    if isinstance(result.get("las"), dict) and result["las"].get("coord_x") is not None:
        return result["las"]
    g = meta.get("georef") or {}
    from pyproj import Transformer
    x, y = Transformer.from_crs("EPSG:4326", f"EPSG:{CFG.get('utm_epsg', 32652)}", always_xy=True).transform(g["lon"], g["lat"])
    z = float(g.get("elev", 0.0))
    return dict(points=0, coord_x=x, coord_y=y, coord_z=z, bbox=[x, y, z, x, y, z])


def visibility_sync(meta, q, resume=True):
    """큐 kind=visibility_sync (edit.py 가 넣음) 또는 처리 중 바뀐 공개 범위 따라잡기:
    public 인데 점이 없으면 scan_points 에 등록, public 이 아닌데 점이 있으면 지운다. Portal Scene 아이템 공유도 맞춘다.
    공개 상태에서 제목이 바뀌었으면 점의 scan_title 도 고친다. 끝나면 원래 상태(resume_*)로 되돌린다"""
    qd = q.read()
    vis = current_visibility(meta)
    oid = qd.get("objectid")
    upd, err = {}, None
    try:
        result = {}
        rp = os.path.join(meta["job_dir"], "out", "pipeline_result.json")
        if os.path.exists(rp):
            result = json.load(open(rp, "r", encoding="utf-8"))
        if not CFG.get("portal_enabled", True):
            log("portal_enabled=false: 공개 범위 지도 반영 건너뜀 (로컬 시험)")
        elif vis == "public" and not oid:
            oid = step_register(meta, _las_info_for(meta, result), qd.get("glb_url") or result.get("glb_url") or "",
                                result.get("slpk_item_id") or "", qd.get("scene_item_id") or result.get("scene_item_id") or "",
                                result.get("scene_url") or "", qd.get("thumb_url") or "", qd.get("ortho_url") or "",
                                pano_url=qd.get("pano_url") or "")
            upd["objectid"] = oid
            if oid and qd.get("splat_url"):
                try:
                    step_update_point(oid, {"splat_url": qd["splat_url"]})
                except Exception as e:
                    log(f"splat_url 반영 생략: {e}")
        elif vis != "public":
            oids = set([int(oid)] if oid else [])
            try:
                oids |= set(_point_oids_for_job(meta.get("job_id") or qd.get("job_id")))
            except Exception as e:
                log(f"작업 번호로 점 찾기 생략: {e}")
            for o in sorted(oids):
                step_delete_point(o)
            upd["objectid"] = None
        elif vis == "public" and oid and qd.get("title"):
            step_update_point(oid, {"scan_title": qd["title"]})
        if CFG.get("portal_enabled", True) and (qd.get("scene_item_id") or result.get("slpk_item_id")):
            share_scene_items([qd.get("scene_item_id") or result.get("scene_item_id"), result.get("slpk_item_id")], vis == "public")
        log(f"공개 범위 반영: {vis} (objectid {upd.get('objectid', oid)})")
    except Exception as e:
        err = str(e)[:300]
        log(f"공개 범위 반영 실패: {err}")
    fix = dict(visibility=vis, visibility_sync_pending=False, visibility_sync_error=err, **upd)
    if resume:
        fix.update(kind=None, status=qd.get("resume_status") or "done", step=qd.get("resume_step") if qd.get("resume_step") is not None else 7,
                   message=qd.get("resume_message") or "처리 완료", resume_status=None, resume_step=None, resume_message=None)
    q.update(**fix)


def rebuild_glb(meta, q):
    """대기열 항목 kind=rebuild_glb: 끝난 Stray 스캔을 지금의 워커로 다시 처리해 서빙 GLB(+면 촬영 정사영상)만 바꾼다.
    Portal Scene·LAS·점 속성은 그대로(같은 glb_url). out → out_prev 로 한 세대만 남긴다.
    (maintenance.py rebuild-glb 가 대기열에 넣는다. 대기열 처리기는 오래 떠 있는 프로세스라 배포만으로 새 코드가 안 들어가므로
     작업마다 새로 뜨는 pipeline.py 에서 처리한다)"""
    job_id, job_dir = meta["job_id"], meta["job_dir"]
    new_out = os.path.join(job_dir, "out_rebuild")
    shutil.rmtree(new_out, ignore_errors=True)
    os.makedirs(new_out)
    q.update(status="processing", step=1, message=f"{job_id} 다시 처리 중")
    _, glb = step_prepare(meta, new_out)
    url = step_glb(glb, job_id)
    if meta.get("area"):
        step_ortho(new_out, job_id)
    old, prev = os.path.join(job_dir, "out"), os.path.join(job_dir, "out_prev")
    shutil.rmtree(prev, ignore_errors=True)
    if os.path.exists(old):
        os.replace(old, prev)
    os.replace(new_out, old)
    q.update(status="done", step=7, message=f"GLB 다시 만듦: {url}")
    log(f"rebuild-glb {job_id}: {url}")


def main():
    meta_path, queue_path = sys.argv[1], sys.argv[2]
    meta = json.load(open(meta_path, "r", encoding="utf-8"))
    q = Queue(queue_path)
    global _SHARE_EVERYONE
    _SHARE_EVERYONE = current_visibility(meta) == "public"
    if q.read().get("kind") == "visibility_sync":           # 공개 범위·제목 바꿈 (edit.py, docs/share_contract.md 2절)
        return visibility_sync(meta, q)
    run_job(meta, q)
    if q.read().get("visibility_sync_pending"):              # 처리 중에 공개 범위가 바뀌었다 → 끝난 뒤 지도 반영을 맞춘다
        visibility_sync(meta, q, resume=False)


def run_job(meta, q):
    if q.read().get("kind") == "rebuild_glb":
        return rebuild_glb(meta, q)
    if q.read().get("kind") == "trench_post":                # 웹 굴착 기록: GPU 실측 묶음이 들어온 뒤 (splat_jobs.py op=upload|bundle)
        return trench_post(meta, q)
    job_id, out_dir = meta["job_id"], os.path.join(meta["job_dir"], "out")
    os.makedirs(out_dir, exist_ok=True)
    if meta.get("mode") in ("video", "photos"):              # 웹 3D 현장조사
        return video_job(meta, q, out_dir, job_id)
    if meta.get("mode") == "pano":                           # VR 투어 (지점마다 360° 실사 사진)
        return pano_job(meta, q, out_dir, job_id)
    service_name = "kgeoscan_" + time.strftime("%Y%m%d_%H%M%S")
    prev_slpk = [f for f in os.listdir(out_dir) if f.endswith(".slpk")]
    if prev_slpk:
        service_name = os.path.splitext(sorted(prev_slpk)[-1])[0]   # 재시도: 이전 SLPK 이름 유지

    q.update(step=1, message="입력 준비" + (" (융합·텍스처 처리 중, 몇 분 걸립니다)" if meta["mode"] == "stray"
                                          else " (고화질 모델 변환 중)" if meta["mode"] == "objcap" else ""))
    las_path, glb_path = step_prepare(meta, out_dir)
    region_path = os.path.join(out_dir, "object_region.json")
    if os.path.exists(region_path):
        try:
            q.update(object_region=json.load(open(region_path, "r", encoding="utf-8")))
        except Exception as e:
            log(f"물체 영역 기록 생략: {e}")
    q.update(step=2, message="좌표·LAS 읽는 중")
    las_info = step_las(las_path)
    q.update(step=3, message="GLB 준비")
    glb_url = step_glb(glb_path, job_id)
    thumb_url = step_thumb(meta, out_dir, job_id)
    ortho_url = step_ortho(out_dir, job_id)
    hz = {}
    if ortho_url:
        try:
            hazards_url, changes_url, site_id = step_hazards(meta, out_dir, job_id)
            hz = dict(hazards_url=hazards_url or None, changes_url=changes_url or None, site_id=site_id)
        except Exception as e:                             # 위험요소 이력은 부가 기능 — 실패해도 발행은 계속
            log(f"위험요소 이력 생략: {e}")
    if floorplan_wanted(meta):                             # 📐 집·방 평면도 (부동산 연계, 2026-11-12) — 실패해도 발행은 계속
        try:
            q.update(message="평면도 만드는 중")
            fp_url = step_floorplan(meta, out_dir, job_id)
            if fp_url:
                hz["floorplan_url"] = fp_url
        except Exception as e:
            log(f"평면도 생략: {e}")
    if (meta.get("trench") or {}).get("mode"):
        try:
            q.update(message="굴착 기록: 관 자동 추출 중")
            util_url, rep_url = step_utilities(meta, out_dir, job_id)
            hz.update(utilities_url=util_url or None, utility_report_url=rep_url or None, trench=meta.get("trench"))
        except Exception as e:                             # 굴착 기록도 부가 단계 — 3D·지도 발행은 계속
            log(f"굴착 기록 생략: {e}")
    q.update(step=4, message="SLPK 생성 중", glb_url=glb_url, thumb_url=thumb_url or None, ortho_url=ortho_url or None, **hz)
    heading = float(meta.get("georef", {}).get("heading", 0.0)) if meta["mode"] in ("stray", "objcap") else 0.0
    slpk = step_slpk(glb_path, out_dir, las_info, service_name, heading)
    slpk_item_id = scene_item_id = scene_url = ""
    if slpk and CFG.get("portal_enabled", True):
        q.update(step=5, message="Portal 발행 중")
        slpk_item_id, scene_item_id, scene_url = step_publish(slpk, service_name, meta["title"])
    oid = None
    if CFG.get("portal_enabled", True):
        q.update(step=6, message="지도에 등록 중")
        oid = step_register(meta, las_info, glb_url, slpk_item_id, scene_item_id, scene_url, thumb_url, ortho_url)
    else:
        log("portal_enabled=false: 발행·등록 건너뜀 (로컬 테스트)")
    result = dict(job_id=job_id, las=las_info, glb_url=glb_url, thumb_url=thumb_url, slpk=slpk, slpk_item_id=slpk_item_id,
                  scene_item_id=scene_item_id, scene_url=scene_url, objectid=oid, seconds=round(time.time() - T0, 1))
    with open(os.path.join(out_dir, "pipeline_result.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    extra = {"objectid": oid} if oid else {}
    extra.update(splat_fields(meta, q))
    q.update(step=7, status="done", message="처리 완료" + ("" if slpk else " (SLPK 없이)"),
             scene_item_id=scene_item_id or None, glb_url=glb_url, thumb_url=thumb_url or None, **extra)
    log(f"완료 {result['seconds']}s")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        try:
            meta_dir = os.path.dirname(os.path.abspath(sys.argv[1]))
            with open(os.path.join(meta_dir, "out", "pipeline_error.log"), "a", encoding="utf-8") as f:
                f.write(time.strftime("%Y-%m-%d %H:%M:%S") + "\n" + tb + "\n")
        except Exception:
            pass
        try:
            Queue(sys.argv[2]).update(status="failed", message=("실패: " + str(e))[:300], error_detail=tb[-1500:])
        except Exception:
            pass
        log("실패: " + str(e))
        print(tb, flush=True)
        sys.exit(1)
