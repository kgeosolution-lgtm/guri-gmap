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
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.environ.get("KGEOSCAN_CONFIG", r"D:\kgeoHub\config\kgeoscan.json"), "r", encoding="utf-8"))
T0 = time.time()
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
    names = {"ortho.jpg": base + ".jpg", "ortho_overlay.png": base + ".png", "ortho.jgw": base + ".jgw", "ortho.prj": base + ".prj"}
    for a, b in names.items():
        if os.path.exists(os.path.join(src, a)):
            shutil.copy2(os.path.join(src, a), os.path.join(CFG["glb_serve_dir"], b))
    m["files"] = {"image": f"{CFG['glb_serve_url']}/{base}.jpg", "overlay": f"{CFG['glb_serve_url']}/{base}.png"}
    if m.get("georef"):
        m["georef"]["world_file_url"] = f"{CFG['glb_serve_url']}/{base}.jgw"
    with open(os.path.join(CFG["glb_serve_dir"], base + ".json"), "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=2)
    url = f"{CFG['glb_serve_url']}/{base}.json"
    log(f"정사영상: {url} ({m.get('surface')} {m.get('width')}x{m.get('height')}, {m.get('gsd_m', 0) * 1000:.2f} mm/px)")
    return url


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
                      {"everyone": "true", "org": "true", "f": "json", "token": token})
        except Exception as e:
            log(f"공유 설정 생략 ({iid}): {e}")
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
                  {"everyone": "true", "org": "true", "f": "json", "token": token})
    log(f"Scene 아이템: {scene_item_id} → {scene_url}")
    return slpk_item_id, scene_item_id, scene_url


def step_register(meta, las_info, glb_url, slpk_item_id, scene_item_id, scene_url, thumb_url="", ortho_url=""):
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
    out = http_json(layer + "/addFeatures", {"features": json.dumps([feature]), "f": "json", "token": token})
    res = out["addResults"][0]
    if not res.get("success"):
        raise RuntimeError("scan_points 등록 실패: " + str(res.get("error")))
    log(f"scan_points OID {res.get('objectId')} ({lon:.5f}, {lat:.5f})")
    return res.get("objectId")


def splat_wanted(meta):
    """GPU 스플랫 워커에 넘길 작업인가: 설정 splat.enabled, Stray 원본, 유형이 splat.scan_types 에 있거나 업로드 때 splat=1 요청"""
    sp = CFG.get("splat") or {}
    if not sp.get("enabled") or meta.get("mode") not in ("stray", "objcap"):
        return False
    if meta.get("splat_requested"):
        return True
    return (meta.get("scan_type") or "home") in (sp.get("scan_types") or ["survey"])


def splat_fields(meta, q):
    """완료 시 큐 파일에 넣을 스플랫 필드. 이미 진행·완료된 스플랫(재시도)은 건드리지 않는다."""
    if q.read().get("splat_status") in ("pending", "processing", "done"):
        return {}
    if splat_wanted(meta):
        log("스플랫: GPU 워커 대기열에 등록 (splat_status=pending)")
        return {"splat_status": "pending", "splat_message": "스플랫 대기 중 (GPU 워커)"}
    return {}


def main():
    meta_path, queue_path = sys.argv[1], sys.argv[2]
    meta = json.load(open(meta_path, "r", encoding="utf-8"))
    q = Queue(queue_path)
    job_id, out_dir = meta["job_id"], os.path.join(meta["job_dir"], "out")
    os.makedirs(out_dir, exist_ok=True)
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
    q.update(step=4, message="SLPK 생성 중", glb_url=glb_url, thumb_url=thumb_url or None, ortho_url=ortho_url or None)
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
