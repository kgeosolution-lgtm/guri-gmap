"""
kgeoScan 유지보수 (서버에서 워커 venv 파이썬으로 실행; 설정의 Portal 계정 사용)
  python -I maintenance.py --actions <actions.json>   배포 워크플로가 호출 (파일의 작업을 순서대로 실행)
  python -I maintenance.py cleanup-orphans             scan_points 가 참조하지 않는 REST 업로드 흔적(Scene Package) 삭제
  python -I maintenance.py delete-scan <objectid>      점 + Scene 서비스 + SLPK 아이템 + 서빙 GLB 삭제
  python -I maintenance.py list                         현재 스캔 목록
  python -I maintenance.py add-fields                   scan_points 에 scan_type, thumb_url, splat_url 필드 추가 (없을 때만)
  python -I maintenance.py backfill-thumbs              썸네일 없는 스캔에 zip 에서 썸네일 생성·등록
  python -I maintenance.py set-scan-type [home]         scan_type 이 비어 있는 스캔을 채움
  python -I maintenance.py queue-splat <job_id>         완료된 Stray 작업을 GPU 스플랫 대기열에 넣음 (큐 파일 splat_status=pending)
  python -I maintenance.py backfill-splats              서빙 폴더에 <job>.splat 이 있는데 splat_url 이 빈 스캔을 등록

actions.json 예:  {"actions": [{"op": "cleanup-orphans"}, {"op": "delete-scan", "objectid": 41}], "once_id": "2026-10-26-1"}
  once_id 가 같은 파일은 다시 실행하지 않는다 (<data_root>\\maintenance_done.txt 에 기록).
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.environ.get("KGEOSCAN_CONFIG", r"D:\kgeoHub\config\kgeoscan.json"), "r", encoding="utf-8"))
PORTAL, USER = CFG["portal_url"], CFG["portal_user"]


def http_json(url, data=None, timeout=120):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode("utf-8") if data is not None else None)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        out = json.loads(r.read().decode("utf-8"))
    if isinstance(out, dict) and "error" in out:
        raise RuntimeError(f"ArcGIS 오류: {out['error']}")
    return out


def token(referer):
    return http_json(PORTAL + "/sharing/rest/generateToken",
                     {"username": USER, "password": CFG["portal_password"], "referer": referer, "expiration": 60, "f": "json"})["token"]


def features(stoken):
    out = http_json(CFG["points_layer_url"] + "/query",
                    {"where": "1=1", "outFields": "*", "returnGeometry": "false", "f": "json", "token": stoken})
    return [f["attributes"] for f in out.get("features", [])]


def my_items(ptoken, q):
    out = http_json(PORTAL + "/sharing/rest/search", {"q": f"owner:{USER} AND ({q})", "num": 100, "f": "json", "token": ptoken})
    return out.get("results", [])


def delete_item(ptoken, iid):
    try:
        http_json(f"{PORTAL}/sharing/rest/content/users/{USER}/items/{iid}/delete", {"f": "json", "token": ptoken})
        print(f"  삭제: 아이템 {iid}")
        return True
    except Exception as e:
        print(f"  삭제 실패: 아이템 {iid} - {e}")
        return False


def cleanup_orphans():
    ptoken, stoken = token(PORTAL), token(CFG["server_url"])
    feats = features(stoken)
    referenced = {a.get("slpk_item_id") for a in feats} | {a.get("scene_item_id") for a in feats}
    titles = {a.get("scan_title") for a in feats}
    removed = 0
    for it in my_items(ptoken, 'type:"Scene Package"'):
        kw = it.get("typeKeywords") or []
        # 파이프라인이 REST addItem 으로 올렸던 흔적: 'ArcGIS Pro' 키워드가 없고, 어느 점도 참조하지 않으며, 제목이 스캔 제목과 같은 것
        if it["id"] in referenced or "ArcGIS Pro" in kw or it.get("title") not in titles:
            continue
        print(f"고아 Scene Package: {it['id']} '{it.get('title')}' name={it.get('name')}")
        removed += delete_item(ptoken, it["id"])
    print(f"cleanup-orphans: {removed}개 삭제")


def fix_slpk_refs():
    """같은 이름의 Scene Package 가 둘이면 'ArcGIS Pro'(SharePackage 로 올린 것)를 남기고 scan_points 참조를 그쪽으로 고친 뒤 나머지 삭제"""
    ptoken, stoken = token(PORTAL), token(CFG["server_url"])
    feats = features(stoken)
    items = my_items(ptoken, 'type:"Scene Package"')
    by_name = {}
    for it in items:
        by_name.setdefault(it.get("name"), []).append(it)
    for name, group in by_name.items():
        if len(group) < 2:
            continue
        keep = next((g for g in group if "ArcGIS Pro" in (g.get("typeKeywords") or [])), group[0])
        print(f"중복 SLPK {name}: {len(group)}개 → 유지 {keep['id']}")
        for a in feats:
            if a.get("slpk_item_id") in {g["id"] for g in group} and a.get("slpk_item_id") != keep["id"]:
                upd = http_json(CFG["points_layer_url"] + "/updateFeatures",
                                {"features": json.dumps([{"attributes": {"objectid": a["objectid"], "slpk_item_id": keep["id"]}}]),
                                 "f": "json", "token": stoken})
                print(f"  OID {a['objectid']} slpk_item_id → {keep['id']}: {upd.get('updateResults')}")
        for g in group:
            if g["id"] != keep["id"]:
                delete_item(ptoken, g["id"])


def delete_scan(objectid=None, title=None):
    ptoken, stoken = token(PORTAL), token(CFG["server_url"])
    feats = features(stoken)
    if objectid is not None:
        feat = next((a for a in feats if int(a.get("objectid", -1)) == int(objectid)), None)
    else:
        feat = next((a for a in feats if a.get("scan_title") == title), None)
    if not feat:
        print(f"delete-scan: 대상 없음 (oid={objectid}, title={title})")
        return
    objectid = feat["objectid"]
    print(f"delete-scan: OID {objectid} '{feat.get('scan_title')}'")
    for iid in (feat.get("scene_item_id"), feat.get("slpk_item_id")):
        if iid:
            delete_item(ptoken, iid)
    glb = feat.get("glb_url") or ""
    if glb:
        base = os.path.splitext(os.path.basename(glb))[0]
        for name in (os.path.basename(glb), base + ".jpg", base + ".splat", base + ".splat.json", base + ".spz", base + ".spz.json"):   # 서빙 GLB + 썸네일 + 스플랫
            p = os.path.join(CFG["glb_serve_dir"], name)
            if os.path.exists(p):
                os.remove(p)
                print(f"  삭제: {p}")
    out = http_json(CFG["points_layer_url"] + "/deleteFeatures", {"objectIds": str(objectid), "f": "json", "token": stoken})
    print("  점 삭제:", out.get("deleteResults"))


NEW_FIELDS = [
    {"name": "scan_type", "type": "esriFieldTypeString", "alias": "스캔 유형", "length": 20, "nullable": True, "editable": True},
    {"name": "thumb_url", "type": "esriFieldTypeString", "alias": "썸네일 URL", "length": 300, "nullable": True, "editable": True},
    {"name": "splat_url", "type": "esriFieldTypeString", "alias": "스플랫 URL", "length": 300, "nullable": True, "editable": True},
]


def layer_fields(stoken):
    info = http_json(CFG["points_layer_url"], {"f": "json", "token": stoken})
    return {f.get("name", "").lower() for f in info.get("fields", [])}


def add_fields():
    """호스티드 피처 레이어 관리자 REST(addToDefinition)로 새 필드를 추가한다. 이미 있으면 건너뜀."""
    stoken = token(CFG["server_url"])
    have = layer_fields(stoken)
    missing = [f for f in NEW_FIELDS if f["name"].lower() not in have]
    if not missing:
        print("add-fields: scan_type, thumb_url, splat_url 모두 있음")
        return
    admin = CFG["points_layer_url"].replace("/rest/services/", "/rest/admin/services/")
    out = http_json(admin + "/addToDefinition", {"addToDefinition": json.dumps({"fields": missing}), "f": "json", "token": stoken})
    print(f"add-fields: {[f['name'] for f in missing]} → {out}")


def update_attrs(stoken, objectid, attrs):
    upd = http_json(CFG["points_layer_url"] + "/updateFeatures",
                    {"features": json.dumps([{"attributes": dict(attrs, objectid=objectid)}]), "f": "json", "token": stoken})
    return upd.get("updateResults")


def backfill_thumbs():
    """thumb_url 이 비어 있고 작업 폴더에 Stray zip 이 남아 있는 스캔: 썸네일을 만들어 서빙 폴더에 두고 필드를 채운다."""
    import subprocess
    stoken = token(CFG["server_url"])
    if "thumb_url" not in layer_fields(stoken):
        print("backfill-thumbs: thumb_url 필드가 없음 (add-fields 먼저)")
        return
    done = 0
    for a in features(stoken):
        if a.get("thumb_url") or not a.get("glb_url"):
            continue
        job_id = os.path.splitext(os.path.basename(a["glb_url"]))[0]
        job_dir = os.path.join(CFG["data_root"], job_id)
        meta_path = os.path.join(job_dir, "job.json")
        if not os.path.exists(meta_path):
            print(f"  OID {a.get('objectid')}: 작업 폴더 없음 ({job_id}) → 건너뜀")
            continue
        meta = json.load(open(meta_path, "r", encoding="utf-8"))
        zip_path = meta.get("scan_zip") or ""
        thumb = os.path.join(job_dir, "out", "thumb.jpg")
        if not os.path.exists(thumb):
            if not (zip_path and os.path.exists(zip_path)):
                print(f"  OID {a.get('objectid')}: zip 없음 (legacy) → 건너뜀")
                continue
            os.makedirs(os.path.dirname(thumb), exist_ok=True)
            cmd = [CFG["worker_python"], "-I", os.path.join(CFG["worker_dir"], "thumbnail.py"), "--zip", zip_path, "--out", thumb]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if proc.returncode != 0 or not os.path.exists(thumb):
                print(f"  OID {a.get('objectid')}: 썸네일 생성 실패: {(proc.stderr or proc.stdout)[-300:]}")
                continue
        os.makedirs(CFG["glb_serve_dir"], exist_ok=True)
        import shutil
        shutil.copy2(thumb, os.path.join(CFG["glb_serve_dir"], job_id + ".jpg"))
        url = f"{CFG['glb_serve_url']}/{job_id}.jpg"
        print(f"  OID {a.get('objectid')} '{a.get('scan_title')}' thumb_url → {url}: {update_attrs(stoken, a['objectid'], {'thumb_url': url})}")
        done += 1
    print(f"backfill-thumbs: {done}개 등록")


def set_scan_type(value="home"):
    stoken = token(CFG["server_url"])
    if "scan_type" not in layer_fields(stoken):
        print("set-scan-type: scan_type 필드가 없음 (add-fields 먼저)")
        return
    n = 0
    for a in features(stoken):
        if not a.get("scan_type"):
            update_attrs(stoken, a["objectid"], {"scan_type": value})
            n += 1
    print(f"set-scan-type: {n}개 → {value}")


def tail_job_logs(job_id, lines=60):
    """작업 폴더의 로그 끝부분을 출력 (배포 로그에서 읽기 위함)"""
    job_id = "".join(c for c in str(job_id) if c in "0123456789abcdef")[:8]
    out = os.path.join(CFG["data_root"], job_id, "out")
    for name in ("worker_stdout.log", "worker.log", "pipeline_error.log"):
        p = os.path.join(out, name)
        if os.path.exists(p):
            txt = open(p, encoding="utf-8", errors="replace").read().splitlines()
            print(f"--- {job_id}/{name} (last {lines} of {len(txt)})")
            for line in txt[-lines:]:
                print("  " + line)
        else:
            print(f"--- {job_id}/{name}: 없음")


def list_scans():
    for a in sorted(features(token(CFG["server_url"])), key=lambda a: a.get("objectid", 0)):
        print(f"  OID {a.get('objectid'):>4}  [{a.get('scan_type') or '-'}] {a.get('scan_title')}  scene={a.get('scene_item_id')}  "
              f"slpk={a.get('slpk_item_id')}  glb={a.get('glb_url')}  thumb={'O' if a.get('thumb_url') else '-'}  splat={'O' if a.get('splat_url') else '-'}")


def _queue_file(job_id):
    p = os.path.join(CFG["jobs_dir"], str(job_id) + ".json")
    return (p, json.load(open(p, "r", encoding="utf-8"))) if os.path.exists(p) else (p, None)


def queue_splat(job_id, force=False):
    """완료된 Stray 작업의 큐 파일에 splat_status=pending 을 써서 GPU 워커가 가져가게 한다."""
    p, q = _queue_file(job_id)
    if not q:
        print(f"queue-splat: 큐 파일 없음 ({job_id})"); return
    if q.get("status") != "done" or q.get("mode") != "stray":
        print(f"queue-splat: {job_id} 는 완료된 Stray 작업이 아님 (status={q.get('status')}, mode={q.get('mode')})"); return
    if q.get("splat_status") in ("pending", "processing") and not force:
        print(f"queue-splat: {job_id} 이미 {q.get('splat_status')}"); return
    q.update(splat_status="pending", splat_message="스플랫 대기 중 (maintenance)", updated_at=time.strftime("%Y-%m-%d %H:%M:%S"))
    with open(p, "w", encoding="utf-8") as f:
        json.dump(q, f, ensure_ascii=False, indent=2)
    print(f"queue-splat: {job_id} '{q.get('title')}' → pending")


def backfill_splats():
    """서빙 폴더에 <job>.splat(.spz) 이 있는데 scan_points.splat_url 이 비어 있는 스캔: 필드를 채우고 큐 파일도 맞춘다."""
    stoken = token(CFG["server_url"])
    if "splat_url" not in layer_fields(stoken):
        print("backfill-splats: splat_url 필드가 없음 (add-fields 먼저)"); return
    n = 0
    for a in features(stoken):
        if a.get("splat_url") or not a.get("glb_url"):
            continue
        job_id = os.path.splitext(os.path.basename(a["glb_url"]))[0]
        for ext in (".splat", ".spz", ".ksplat"):
            if os.path.exists(os.path.join(CFG["glb_serve_dir"], job_id + ext)):
                url = f"{CFG['glb_serve_url']}/{job_id}{ext}"
                print(f"  OID {a.get('objectid')} '{a.get('scan_title')}' splat_url → {url}: {update_attrs(stoken, a['objectid'], {'splat_url': url})}")
                p, q = _queue_file(job_id)
                if q:
                    q.update(splat_status="done", splat_url=url, splat_registered=True, updated_at=time.strftime("%Y-%m-%d %H:%M:%S"))
                    with open(p, "w", encoding="utf-8") as f:
                        json.dump(q, f, ensure_ascii=False, indent=2)
                n += 1
                break
    print(f"backfill-splats: {n}개 등록")


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--actions":
        spec = json.load(open(sys.argv[2], "r", encoding="utf-8"))
        once = spec.get("once_id")
        done_file = os.path.join(CFG["data_root"], "maintenance_done.txt")
        done = open(done_file, encoding="utf-8").read().split() if os.path.exists(done_file) else []
        if once and once in done:
            print(f"maintenance: {once} 는 이미 실행됨, 건너뜀")
            return
        for act in spec.get("actions", []):
            op = act.get("op")
            try:
                if op == "cleanup-orphans":
                    cleanup_orphans()
                elif op == "fix-slpk-refs":
                    fix_slpk_refs()
                elif op == "delete-scan":
                    delete_scan(act.get("objectid"), act.get("title"))
                elif op == "list":
                    list_scans()
                elif op == "tail-log":
                    tail_job_logs(act.get("job_id", ""), int(act.get("lines", 60)))
                elif op == "add-fields":
                    add_fields()
                elif op == "backfill-thumbs":
                    backfill_thumbs()
                elif op == "set-scan-type":
                    set_scan_type(act.get("value", "home"))
                elif op == "queue-splat":
                    queue_splat(act.get("job_id"), bool(act.get("force")))
                elif op == "backfill-splats":
                    backfill_splats()
                else:
                    print(f"알 수 없는 작업: {op}")
            except Exception as e:
                print(f"작업 실패 {op}: {e}")
        if once:
            with open(done_file, "a", encoding="utf-8") as f:
                f.write(once + "\n")
        return
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "cleanup-orphans":
        cleanup_orphans()
    elif cmd == "fix-slpk-refs":
        fix_slpk_refs()
    elif cmd == "delete-scan":
        delete_scan(sys.argv[2])
    elif cmd == "add-fields":
        add_fields()
    elif cmd == "backfill-thumbs":
        backfill_thumbs()
    elif cmd == "set-scan-type":
        set_scan_type(sys.argv[2] if len(sys.argv) > 2 else "home")
    elif cmd == "queue-splat":
        queue_splat(sys.argv[2], "--force" in sys.argv)
    elif cmd == "backfill-splats":
        backfill_splats()
    else:
        list_scans()


if __name__ == "__main__":
    main()
