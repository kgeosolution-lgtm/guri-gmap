"""
arcpy 로 OBJ → 멀티패치 → 3D Object Scene Layer Package (SLPK)
  "<ArcGIS Pro python>" slpk_step.py <obj_folder> <out.slpk> <cx> <cy> <cz> <epsg>

  - obj_folder 안의 model.obj (+model.mtl, texture.jpg) 를 Import 3D Files 로 읽는다 (glb 는 이 도구가 못 읽음).
  - (cx, cy, cz) 는 모델 경계상자의 중심을 놓을 투영 좌표. Import 3D Files 는 배치점에 모델의 경계상자 중심을 맞추므로
    LAS 범위의 중심을 주면 LAS 와 정확히 겹친다 (OBJ 는 이미 heading 만큼 회전되어 있어야 한다).
  - 심볼 필드에는 전체 경로가 아니라 파일 이름(model.obj)만 넣어야 배치점이 적용된다 (전체 경로를 주면 원점에 놓인다).
  - ArcGIS Pro 라이선스(명명 사용자 로그인 또는 오프라인 인증)가 있어야 arcpy 가 로드된다.
"""
import os
import sys
import tempfile
import time


def publish(slpk, title):
    """SLPK 를 Portal 에 올리고 Scene 서비스로 발행 (ArcGIS Pro 의 '패키지 공유'와 동일).
    자격 증명은 환경변수 KGEOSCAN_PORTAL_URL / USER / PASSWORD 로 받는다 (명령줄에 노출하지 않음)."""
    import json
    import arcpy
    url, user, pw = os.environ["KGEOSCAN_PORTAL_URL"], os.environ["KGEOSCAN_PORTAL_USER"], os.environ["KGEOSCAN_PORTAL_PASSWORD"]
    t0 = time.time()
    arcpy.SignInToPortal(url, user, pw)
    print(f"signed in: {arcpy.GetActivePortalURL()}", flush=True)
    res = arcpy.management.SharePackage(slpk, "", "", title, "kgeoScan,LiDAR,3D scan", "KgeoSolution",
                                        "EVERYBODY", None, "EVERYBODY", "TRUE")
    print(arcpy.GetMessages(), flush=True)
    outs = []
    for i in range(res.outputCount):
        try:
            outs.append(str(res.getOutput(i)))
        except Exception:
            pass
    print("PUBLISH_RESULT " + json.dumps({"outputs": outs, "seconds": round(time.time() - t0, 1)}, ensure_ascii=False), flush=True)


def main():
    if sys.argv[1] == "--publish":
        return publish(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else os.path.basename(sys.argv[2]))
    folder, out_slpk = sys.argv[1], sys.argv[2]
    cx, cy, cz, epsg = float(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5]), int(sys.argv[6])
    t0 = time.time()
    import arcpy
    arcpy.env.overwriteOutput = True
    sr = arcpy.SpatialReference(epsg)
    arcpy.env.outputCoordinateSystem = sr
    work = tempfile.mkdtemp(prefix="kgeoscan_slpk_")
    gdb = arcpy.management.CreateFileGDB(work, "scan.gdb").getOutput(0)
    pts = arcpy.management.CreateFeatureclass(gdb, "placement", "POINT", spatial_reference=sr, has_z="ENABLED").getOutput(0)
    arcpy.management.AddField(pts, "model", "TEXT", field_length=128)
    with arcpy.da.InsertCursor(pts, ["SHAPE@", "model"]) as cur:
        cur.insertRow([arcpy.PointGeometry(arcpy.Point(cx, cy, cz), sr, has_z=True), "model.obj"])
    mp = os.path.join(gdb, "scan_mp")
    print(f"Import3DFiles {folder} -> center ({cx:.2f}, {cy:.2f}, {cz:.2f}) EPSG:{epsg}", flush=True)
    arcpy.ddd.Import3DFiles(in_files=folder, out_featureClass=mp, root_per_feature="ONE_FILE_ONE_FEATURE",
                            spatial_reference=sr, y_is_up="Y_IS_UP", in_featureClass=pts, symbol_field="model")
    d = arcpy.Describe(mp)
    print(f"multipatch extent X[{d.extent.XMin:.2f},{d.extent.XMax:.2f}] Y[{d.extent.YMin:.2f},{d.extent.YMax:.2f}] "
          f"Z[{d.extent.ZMin:.2f},{d.extent.ZMax:.2f}] ({time.time() - t0:.0f}s)", flush=True)
    arcpy.management.Create3DObjectSceneLayerPackage(in_dataset=mp, out_slpk=out_slpk, out_coor_system=sr,
                                                      texture_optimization="Desktop")
    size = os.path.getsize(out_slpk)
    print(f"SLPK: {out_slpk} {size / 1e6:.1f} MB ({time.time() - t0:.0f}s)", flush=True)
    if size < 100_000:
        raise SystemExit("SLPK 가 비어 있습니다 (100 KB 미만)")


if __name__ == "__main__":
    main()
