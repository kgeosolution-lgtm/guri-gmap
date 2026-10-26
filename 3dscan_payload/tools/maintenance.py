"""
kgeoScan 유지보수 (서버에서 워커 venv 파이썬으로 실행; 설정의 Portal 계정 사용)
  python -I maintenance.py --actions <actions.json>   배포 워크플로가 호출 (파일의 작업을 순서대로 실행)
  python -I maintenance.py cleanup-orphans             scan_points 가 참조하지 않는 REST 업로드 흔적(Scene Package) 삭제
  python -I maintenance.py delete-scan <objectid>      점 + Scene 서비스 + SLPK 아이템 + 서빙 GLB 삭제
  python -I maintenance.py list                         현재 스캔 목록

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


def delete_scan(objectid):
    ptoken, stoken = token(PORTAL), token(CFG["server_url"])
    feat = next((a for a in features(stoken) if int(a.get("objectid", -1)) == int(objectid)), None)
    if not feat:
        print(f"delete-scan: OID {objectid} 없음")
        return
    print(f"delete-scan: OID {objectid} '{feat.get('scan_title')}'")
    for iid in (feat.get("scene_item_id"), feat.get("slpk_item_id")):
        if iid:
            delete_item(ptoken, iid)
    glb = feat.get("glb_url") or ""
    if glb:
        p = os.path.join(CFG["glb_serve_dir"], os.path.basename(glb))
        if os.path.exists(p):
            os.remove(p)
            print(f"  삭제: {p}")
    out = http_json(CFG["points_layer_url"] + "/deleteFeatures", {"objectIds": str(objectid), "f": "json", "token": stoken})
    print("  점 삭제:", out.get("deleteResults"))


def list_scans():
    for a in sorted(features(token(CFG["server_url"])), key=lambda a: a.get("objectid", 0)):
        print(f"  OID {a.get('objectid'):>4}  {a.get('scan_title')}  scene={a.get('scene_item_id')}  slpk={a.get('slpk_item_id')}  glb={a.get('glb_url')}")


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
                elif op == "delete-scan":
                    delete_scan(act["objectid"])
                elif op == "list":
                    list_scans()
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
    elif cmd == "delete-scan":
        delete_scan(sys.argv[2])
    else:
        list_scans()


if __name__ == "__main__":
    main()
