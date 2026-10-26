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

    # 1) fusion
    t1 = time.time()
    run([PY, "-I", os.path.join(HERE, "stray_to_mesh.py"), "--data", data, "--out", args.out,
         "--voxel", str(args.voxel), "--every", str(args.every), "--conf", "1", "--max-depth", str(args.max_depth),
         "--target-tris", str(args.fuse_tris)], t0, log_path)
    t_fuse = time.time() - t1
    ply = os.path.join(args.out, "mesh.ply")

    # 2) photo texture
    t2 = time.time()
    run([PY, "-I", os.path.join(HERE, "texture_fast.py"), "--data", data, "--mesh", ply, "--out", args.out,
         "--target-tris", str(args.tex_tris), "--keyframes", str(args.keyframes), "--tex-size", str(args.tex_size),
         "--jpeg-quality", str(args.jpeg_quality)], t0, log_path)
    t_tex = time.time() - t2

    # 3) georeferenced LAS
    t3 = time.time()
    las_info = write_las(ply, os.path.join(args.out, "scan.las"), args.lon, args.lat, args.elev, args.heading,
                         args.max_las_points, t0)
    t_las = time.time() - t3

    fuse_stats = json.load(open(os.path.join(args.out, "stats.json")))
    tex_stats = json.load(open(os.path.join(args.out, "stats_tex.json")))
    result = dict(
        input_zip=os.path.abspath(args.zip), frames=n_frames, fusion=fuse_stats, texture=tex_stats, las=las_info,
        georef=dict(lon=args.lon, lat=args.lat, elev=args.elev, heading_deg=args.heading, crs="EPSG:32652"),
        outputs=dict(glb="mesh_tex.glb", las="scan.las", ply="mesh.ply"),
        seconds=dict(fusion=round(t_fuse, 1), texture=round(t_tex, 1), las=round(t_las, 1), total=round(time.time() - t0, 1)))
    with open(os.path.join(args.out, "result.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    if not args.keep_extract:
        shutil.rmtree(extract, ignore_errors=True)
    log(f"done: glb {os.path.getsize(os.path.join(args.out, 'mesh_tex.glb')) / 1e6:.1f} MB, "
        f"las {os.path.getsize(os.path.join(args.out, 'scan.las')) / 1e6:.1f} MB, total {result['seconds']['total']}s", t0)


if __name__ == "__main__":
    main()
