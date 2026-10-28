"""
kgeoScan worker: Stray Scanner zip -> fused mesh -> photo texture -> georeferenced LAS + GLB

  python -I process_scan.py --zip <scan.zip> --out <out_dir> --lon 127.0599 --lat 37.2873
         [--elev 58.7] [--heading 0] [--voxel 0.006] [--every 1] [--tex-tris 120000]
         [--keyframes 100] [--tex-size 4096] [--jpeg-quality 85] [--max-las-points 2000000]

Outputs in <out_dir>:
  mesh.ply       fused, cleaned mesh with vertex colours (local ARKit frame, metres, y up)
  mesh_tex.glb   photo-textured GLB (local frame, y up) -> existing "GLB 변환 / SLPK" steps
  scan.las       coloured point cloud in UTM 52N (EPSG:32652), metres -> existing "LAS 파싱" step
  result.json    stats, timings, origin/centroid coordinates

Georeferencing: the ARKit world frame is gravity aligned (y up). --lon/--lat/--elev give the position of the
ARKit origin (where the recording started); --heading is the compass direction (deg, clockwise from north)
the phone faced at the first frame. Without a heading the scan is placed with its initial view facing north.
"""
import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def log(msg, t0):
    print(f"[{time.time() - t0:6.1f}s] {msg}", flush=True)


def find_dataset_root(folder):
    for root, dirs, files in os.walk(folder):
        if "odometry.csv" in files and "depth" in dirs and "rgb.mp4" in files:
            return root
    raise SystemExit("not a Stray Scanner dataset: odometry.csv, depth/ and rgb.mp4 not found")


def run(cmd, t0, log_path):
    log("run: " + " ".join(os.path.basename(c) if i == 0 else c for i, c in enumerate(cmd)), t0)
    with open(log_path, "a", encoding="utf-8") as lf:
        proc = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"step failed (exit {proc.returncode}); see {log_path}")


def write_las(ply_path, las_path, lon, lat, elev, heading_deg, max_points, t0):
    import numpy as np
    import open3d as o3d
    import laspy
    from pyproj import Transformer

    mesh = o3d.io.read_triangle_mesh(ply_path)
    P = np.asarray(mesh.vertices, dtype=np.float64)
    C = np.asarray(mesh.vertex_colors) if mesh.has_vertex_colors() else np.full((len(P), 3), 0.5)
    if len(P) > max_points:
        sel = np.random.default_rng(0).choice(len(P), max_points, replace=False)
        P, C = P[sel], C[sel]

    # ARKit local (x right, y up, -z forward) -> ENU with the initial forward direction at `heading`
    th = math.radians(heading_deg)
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    e = x * math.cos(th) - z * math.sin(th)
    n = -x * math.sin(th) - z * math.cos(th)
    h = y
    tf = Transformer.from_crs("EPSG:4326", "EPSG:32652", always_xy=True)
    e0, n0 = tf.transform(lon, lat)
    E, N, H = e + e0, n + n0, h + elev

    header = laspy.LasHeader(point_format=2, version="1.2")
    header.scales = np.array([0.001, 0.001, 0.001])
    header.offsets = np.array([math.floor(E.min()), math.floor(N.min()), math.floor(H.min())])
    las = laspy.LasData(header)
    las.x, las.y, las.z = E, N, H
    rgb = np.clip(C * 65535, 0, 65535).astype(np.uint16)
    las.red, las.green, las.blue = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    las.write(las_path)
    cen = [float(E.mean()), float(N.mean()), float(H.mean())]
    log(f"LAS: {len(E)} points, UTM52N origin ({e0:.2f}, {n0:.2f}, {elev:.2f}), centroid ({cen[0]:.2f}, {cen[1]:.2f}, {cen[2]:.2f})", t0)
    return dict(points=int(len(E)), origin_utm52n=[float(e0), float(n0), float(elev)], centroid_utm52n=cen,
                bbox_min=[float(E.min()), float(N.min()), float(H.min())], bbox_max=[float(E.max()), float(N.max()), float(H.max())])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--elev", type=float, default=0.0)
    ap.add_argument("--heading", type=float, default=0.0)
    ap.add_argument("--voxel", type=float, default=0.006)
    ap.add_argument("--every", type=int, default=1)
    ap.add_argument("--max-depth", type=float, default=4.0)
    ap.add_argument("--fuse-tris", type=int, default=600000)
    ap.add_argument("--tex-tris", type=int, default=120000)
    ap.add_argument("--keyframes", type=int, default=100)
    ap.add_argument("--tex-size", type=int, default=4096)
    ap.add_argument("--jpeg-quality", type=int, default=85)
    ap.add_argument("--max-las-points", type=int, default=2000000)
    ap.add_argument("--keep-extract", action="store_true")
    ap.add_argument("--object-mode", action="store_true", help="물체 영역만 남긴다 (현장조사 물체 모드)")
    ap.add_argument("--obj-center", default="", help="x,y,z (ARKit 월드). 없으면 카메라 시선 교점으로 자동")
    ap.add_argument("--obj-radius", default="", help="m. 없으면 LiDAR 로 추정")
    ap.add_argument("--area-mode", action="store_true", help="면 촬영: 정사영상(ortho/) 생성")
    ap.add_argument("--area-surface", default="auto", choices=["auto", "floor", "wall"])
    args = ap.parse_args()

    t0 = time.time()
    os.makedirs(args.out, exist_ok=True)
    log_path = os.path.join(args.out, "worker.log")
    extract = os.path.join(args.out, "_extract")
    if os.path.isdir(extract):
        shutil.rmtree(extract)
    with zipfile.ZipFile(args.zip) as zf:
        bad = [n for n in zf.namelist() if n.startswith("/") or ".." in n.split("/")]
        if bad:
            raise SystemExit("zip contains unsafe paths")
        zf.extractall(extract)
    data = find_dataset_root(extract)
    n_frames = len([f for f in os.listdir(os.path.join(data, "depth")) if f.endswith(".png")])
    log(f"dataset: {data} ({n_frames} depth frames)", t0)

    # 1) fusion (물체 모드: 더 촘촘한 복셀, 가까운 깊이만)
    voxel, max_depth = args.voxel, args.max_depth
    if args.object_mode:
        voxel, max_depth = min(voxel, 0.004), min(max_depth, 1.5)
    t1 = time.time()
    run([PY, "-I", os.path.join(HERE, "stray_to_mesh.py"), "--data", data, "--out", args.out,
         "--voxel", str(voxel), "--every", str(args.every), "--conf", "1", "--max-depth", str(max_depth),
         "--target-tris", str(args.fuse_tris)], t0, log_path)
    t_fuse = time.time() - t1
    ply = os.path.join(args.out, "mesh.ply")

    # 1b) 물체 모드: 영역(중심·반경·받침면)을 정하고 메시를 자른다. 너무 적게 남으면 자르지 않는다.
    region = None
    if args.object_mode:
        sys.path.insert(0, HERE)            # python -I 는 스크립트 폴더를 경로에 넣지 않는다
        import object_region
        region = object_region.resolve_region(data, args.obj_center or None, args.obj_radius or None)
        shutil.copy2(ply, os.path.join(args.out, "mesh_full.ply"))
        kept, total = object_region.crop_mesh_file(ply, ply, region)
        region["mesh_tris_kept"], region["mesh_tris_total"] = kept, total
        if kept < 500:
            shutil.copy2(os.path.join(args.out, "mesh_full.ply"), ply)
            region["cropped"] = False
            log(f"object region: only {kept} tris inside -> keep full mesh", t0)
        else:
            region["cropped"] = True
            log(f"object region: center {region['center']} r {region['radius']} floor {region['floor_y']} "
                f"({region['center_by']}/{region['radius_by']}) -> {kept}/{total} tris", t0)
        with open(os.path.join(args.out, "object_region.json"), "w", encoding="utf-8") as f:
            json.dump(region, f, ensure_ascii=False, indent=2)

    # 2) photo texture
    t2 = time.time()
    tex_args = ["--target-tris", str(args.tex_tris), "--keyframes", str(args.keyframes), "--tex-size", str(args.tex_size),
                "--jpeg-quality", str(args.jpeg_quality)]
    if region and region.get("cropped"):
        # 물체 모드: 기본 2 cm 정점 병합은 컵 같은 작은 물체를 수백 삼각형으로 뭉갠다 → 3 mm.
        # 텍스처는 2048 이면 충분하고 메모리가 1/4 (서버는 ArcGIS 가 메모리를 많이 써서 4096 에서 MemoryError 가 났다)
        tex_args = ["--target-tris", str(args.tex_tris), "--keyframes", str(args.keyframes),
                    "--tex-size", str(min(args.tex_size, 2048)), "--cluster-voxel", "0.003", "--min-component", "20",
                    "--jpeg-quality", str(args.jpeg_quality)]
    # (면 촬영 3D 텍스처를 고해상도 사진으로 입히는 texture_hires.py 는 첫 벽 시험(ee6c8922, 사진 12장)에서 경계가 더 보여 보류 —
    #  세부 기록은 정사영상이 맡는다. research/pgm/README.md 참고)
    run([PY, "-I", os.path.join(HERE, "texture_fast.py"), "--data", data, "--mesh", ply, "--out", args.out] + tex_args,
        t0, log_path)
    t_tex = time.time() - t2

    # 2b) thumbnail (optional: failure must not stop the job)
    thumb = os.path.join(args.out, "thumb.jpg")
    try:
        run([PY, "-I", os.path.join(HERE, "thumbnail.py"), "--data", data, "--out", thumb], t0, log_path)
    except SystemExit as e:
        log(f"thumbnail skipped: {e}", t0)

    # 3) georeferenced LAS
    t3 = time.time()
    las_info = write_las(ply, os.path.join(args.out, "scan.las"), args.lon, args.lat, args.elev, args.heading,
                         args.max_las_points, t0)
    t_las = time.time() - t3

    # 4) 면 촬영: 정사영상 (실패해도 작업은 계속)
    ortho = None
    if args.area_mode:
        t4 = time.time()
        odir = os.path.join(args.out, "ortho")
        try:
            run([PY, "-I", os.path.join(HERE, "orthophoto.py"), "--data", data, "--mesh", os.path.join(args.out, "mesh_full.ply")
                 if os.path.exists(os.path.join(args.out, "mesh_full.ply")) else ply, "--out", odir,
                 "--surface", args.area_surface, "--lon", str(args.lon), "--lat", str(args.lat), "--heading", str(args.heading)],
                t0, log_path)
            ortho = json.load(open(os.path.join(odir, "ortho.json"), encoding="utf-8"))
            log(f"ortho: {ortho['surface']} {ortho['width']}x{ortho['height']} {ortho['gsd_m'] * 1000:.2f} mm/px "
                f"({time.time() - t4:.0f}s)", t0)
        except SystemExit as e:
            log(f"ortho skipped: {e}", t0)

    fuse_stats = json.load(open(os.path.join(args.out, "stats.json")))
    tex_stats = json.load(open(os.path.join(args.out, "stats_tex.json")))
    result = dict(
        input_zip=os.path.abspath(args.zip), frames=n_frames, fusion=fuse_stats, texture=tex_stats, las=las_info,
        georef=dict(lon=args.lon, lat=args.lat, elev=args.elev, heading_deg=args.heading, crs="EPSG:32652"),
        outputs=dict(glb="mesh_tex.glb", las="scan.las", ply="mesh.ply", thumb="thumb.jpg" if os.path.exists(thumb) else None),
        object_region=region, ortho=ortho,
        seconds=dict(fusion=round(t_fuse, 1), texture=round(t_tex, 1), las=round(t_las, 1), total=round(time.time() - t0, 1)))
    with open(os.path.join(args.out, "result.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    if not args.keep_extract:
        shutil.rmtree(extract, ignore_errors=True)
    log(f"done: glb {os.path.getsize(os.path.join(args.out, 'mesh_tex.glb')) / 1e6:.1f} MB, "
        f"las {os.path.getsize(os.path.join(args.out, 'scan.las')) / 1e6:.1f} MB, total {result['seconds']['total']}s", t0)


if __name__ == "__main__":
    main()
