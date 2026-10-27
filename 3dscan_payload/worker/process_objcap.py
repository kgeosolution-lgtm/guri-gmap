r"""
kgeoScan worker: Apple Object Capture 업로드(mode=objcap) -> GLB + LAS + 썸네일

  python -I process_objcap.py --zip <scan.zip> --out <out_dir> --lon 127.06 --lat 37.28 [--elev 0] [--heading 0]

zip 규약 (앱이 만든다):
  <root>/model/      PhotogrammetrySession 이 디렉터리로 쓴 OBJ + MTL + 텍스처 (필수)
  <root>/images/     촬영 사진 JPEG (스플랫 워커용, 여기서는 썸네일 대체용으로만)
  <root>/poses.json  사진별 카메라 자세 (스플랫 워커용)
  <root>/thumb.jpg   대표 사진
  <root>/meta.json   앱 메타

모델 좌표: 미터, y 위(중력). 원점·수평 방향은 임의라 물체 바닥 중심을 GPS 위치에 놓고,
--heading 은 모델 -z 축이 바라보는 방위(모르면 0 = 북쪽)로 쓴다.

출력 (<out_dir>): mesh_tex.glb, scan.las, thumb.jpg, result.json  (process_scan.py 와 같은 이름 → pipeline 이 그대로 처리)
"""
import argparse
import glob
import json
import math
import os
import shutil
import sys
import time
import zipfile

import numpy as np

MAX_TEX = 4096


def log(msg, t0):
    print(f"[{time.time() - t0:6.1f}s] {msg}", flush=True)


def safe_extract(zip_path, dest):
    with zipfile.ZipFile(zip_path) as zf:
        bad = [n for n in zf.namelist() if n.startswith("/") or ".." in n.split("/") or ":" in n]
        if bad:
            raise SystemExit("zip contains unsafe paths")
        zf.extractall(dest)


def find_root(folder):
    for root, dirs, files in os.walk(folder):
        if "model" in dirs and glob.glob(os.path.join(root, "model", "*.obj")):
            return root
    objs = glob.glob(os.path.join(folder, "**", "*.obj"), recursive=True)
    if objs:
        return os.path.dirname(os.path.dirname(objs[0]))
    raise SystemExit("objcap zip 에 model/*.obj 가 없습니다 (PhotogrammetrySession 디렉터리 출력 필요)")


def load_model(root, t0):
    import trimesh
    obj = sorted(glob.glob(os.path.join(root, "model", "*.obj")))[0]
    scene = trimesh.load(obj, force="scene", process=False)
    meshes = [g for g in scene.dump() if isinstance(g, trimesh.Trimesh) and len(g.faces)]
    if not meshes:
        raise SystemExit("OBJ 에 메시가 없습니다")
    log(f"model: {os.path.basename(obj)} {len(meshes)} part(s), {sum(len(m.faces) for m in meshes)} tris", t0)
    return meshes


def shrink_texture(mesh, t0):
    """텍스처가 MAX_TEX 보다 크면 줄인다 (웹 뷰어·메모리)"""
    from PIL import Image
    vis = mesh.visual
    mat = getattr(vis, "material", None)
    img = None
    for attr in ("baseColorTexture", "image"):
        img = getattr(mat, attr, None) if mat is not None else None
        if img is not None:
            break
    if img is None or max(img.size) <= MAX_TEX:
        return
    s = MAX_TEX / max(img.size)
    small = img.resize((int(img.size[0] * s), int(img.size[1] * s)), Image.LANCZOS)
    if hasattr(mat, "baseColorTexture"):
        mat.baseColorTexture = small
    else:
        mat.image = small
    log(f"texture {img.size} -> {small.size}", t0)


def to_pbr(mesh):
    """glTF 에서 어둡게 보이지 않도록 금속성 0, 거칠기 1 (process_scan 의 GLB 와 같은 설정)"""
    import trimesh
    vis = mesh.visual
    if not hasattr(vis, "uv") or vis.uv is None:
        return
    mat = vis.material
    tex = getattr(mat, "baseColorTexture", None) or getattr(mat, "image", None)
    mesh.visual = trimesh.visual.TextureVisuals(
        uv=vis.uv, material=trimesh.visual.material.PBRMaterial(
            baseColorTexture=tex, metallicFactor=0.0, roughnessFactor=1.0, doubleSided=False))


def vertex_colors(mesh):
    try:
        c = mesh.visual.to_color().vertex_colors
        return np.asarray(c)[:, :3].astype(np.float64) / 255.0
    except Exception:
        return np.full((len(mesh.vertices), 3), 0.6)


def write_las(points, colors, las_path, lon, lat, elev, heading_deg, utm_epsg, t0):
    import laspy
    from pyproj import Transformer
    th = math.radians(heading_deg)
    x, y, z = points[:, 0], points[:, 1], points[:, 2]
    e = x * math.cos(th) - z * math.sin(th)
    n = -x * math.sin(th) - z * math.cos(th)
    tf = Transformer.from_crs("EPSG:4326", f"EPSG:{utm_epsg}", always_xy=True)
    e0, n0 = tf.transform(lon, lat)
    E, N, H = e + e0, n + n0, y + elev
    header = laspy.LasHeader(point_format=2, version="1.2")
    header.scales = np.array([0.001, 0.001, 0.001])
    header.offsets = np.array([math.floor(E.min()), math.floor(N.min()), math.floor(H.min())])
    las = laspy.LasData(header)
    las.x, las.y, las.z = E, N, H
    rgb = np.clip(colors * 65535, 0, 65535).astype(np.uint16)
    las.red, las.green, las.blue = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    las.write(las_path)
    log(f"LAS: {len(E)} points, UTM {utm_epsg} origin ({e0:.2f}, {n0:.2f}, {elev:.2f})", t0)
    return dict(points=int(len(E)), origin_utm=[float(e0), float(n0), float(elev)],
                bbox_min=[float(E.min()), float(N.min()), float(H.min())], bbox_max=[float(E.max()), float(N.max()), float(H.max())])


def make_thumb(root, out_path):
    import cv2
    src = os.path.join(root, "thumb.jpg")
    if not os.path.exists(src):
        imgs = sorted(glob.glob(os.path.join(root, "images", "*.jp*g")))
        if not imgs:
            return False
        src = imgs[len(imgs) // 2]
    img = cv2.imdecode(np.fromfile(src, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return False
    h, w = img.shape[:2]
    s = 640 / max(h, w)
    if s < 1:
        img = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 82])
    if ok:
        open(out_path, "wb").write(buf.tobytes())
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--elev", type=float, default=0.0)
    ap.add_argument("--heading", type=float, default=0.0)
    ap.add_argument("--utm-epsg", type=int, default=32652)
    ap.add_argument("--max-las-points", type=int, default=2000000)
    ap.add_argument("--keep-extract", action="store_true")
    a = ap.parse_args()

    import trimesh
    t0 = time.time()
    os.makedirs(a.out, exist_ok=True)
    extract = os.path.join(a.out, "_extract")
    shutil.rmtree(extract, ignore_errors=True)
    safe_extract(a.zip, extract)
    root = find_root(extract)
    meshes = load_model(root, t0)

    # 바닥 중심을 원점으로 (y 위). 여러 부품이면 함께 옮긴다.
    allv = np.concatenate([m.vertices for m in meshes])
    lo, hi = allv.min(0), allv.max(0)
    shift = np.array([-(lo[0] + hi[0]) / 2, -lo[1], -(lo[2] + hi[2]) / 2])
    for m in meshes:
        m.apply_translation(shift)
        shrink_texture(m, t0)
        to_pbr(m)
    size = (hi - lo)
    log(f"size (m): {np.round(size, 3).tolist()}", t0)

    glb = os.path.join(a.out, "mesh_tex.glb")
    trimesh.Scene(meshes).export(glb)
    log(f"GLB {os.path.getsize(glb) / 1e6:.1f} MB", t0)

    pts = np.concatenate([m.vertices for m in meshes])
    cols = np.concatenate([vertex_colors(m) for m in meshes])
    if len(pts) < 20000:      # 정점이 적으면 표면에서 더 뽑는다 (점군이 너무 성기지 않게)
        extra, cols_extra = [], []
        for m in meshes:
            p, fi = trimesh.sample.sample_surface(m, 40000)
            extra.append(p)
            fc = vertex_colors(m)[m.faces[fi]].mean(axis=1)
            cols_extra.append(fc)
        pts = np.concatenate([pts] + extra); cols = np.concatenate([cols] + cols_extra)
    if len(pts) > a.max_las_points:
        sel = np.random.default_rng(0).choice(len(pts), a.max_las_points, replace=False)
        pts, cols = pts[sel], cols[sel]
    las_info = write_las(pts, cols, os.path.join(a.out, "scan.las"), a.lon, a.lat, a.elev, a.heading, a.utm_epsg, t0)

    thumb = os.path.join(a.out, "thumb.jpg")
    has_thumb = make_thumb(root, thumb)

    meta_app = {}
    try:
        meta_app = json.load(open(os.path.join(root, "meta.json"), encoding="utf-8"))
    except Exception:
        pass
    n_images = len(glob.glob(os.path.join(root, "images", "*.jp*g")))
    result = dict(input_zip=os.path.abspath(a.zip), capture="objcap", images=n_images,
                  poses=os.path.exists(os.path.join(root, "poses.json")),
                  model=dict(parts=len(meshes), triangles=int(sum(len(m.faces) for m in meshes)), size_m=np.round(size, 4).tolist()),
                  las=las_info, georef=dict(lon=a.lon, lat=a.lat, elev=a.elev, heading_deg=a.heading, crs=f"EPSG:{a.utm_epsg}"),
                  outputs=dict(glb="mesh_tex.glb", las="scan.las", thumb="thumb.jpg" if has_thumb else None),
                  app=meta_app.get("objcap"), seconds=dict(total=round(time.time() - t0, 1)))
    json.dump(result, open(os.path.join(a.out, "result.json"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    if not a.keep_extract:
        shutil.rmtree(extract, ignore_errors=True)
    log(f"done: {result['seconds']['total']}s", t0)


if __name__ == "__main__":
    main()
