"""
Stray Scanner dataset -> TSDF fusion (Open3D) -> cleaned mesh -> PLY + GLB

Usage:
  python -I scripts/stray_to_mesh.py --data <dataset_dir> --out <out_dir>
         [--voxel 0.01] [--every 2] [--conf 1] [--max-depth 4.0]
         [--target-tris 400000] [--max-frames N]

Dataset layout (Stray Scanner):
  rgb.mp4            HEVC video, one frame per depth map
  depth/000000.png   16-bit PNG, millimetres, 256x192
  confidence/*.png   8-bit PNG, 0..2
  odometry.csv       timestamp, frame, x, y, z, qx, qy, qz, qw [, fx, fy, cx, cy, ...]
  camera_matrix.csv  3x3 intrinsics of the RGB image (fallback)
"""
import argparse
import csv
import json
import math
import os
import sys
import time

import cv2
import numpy as np
import open3d as o3d
import open3d.core as o3c

# 기본 256x192(4:3). 16:9 영상 형식(앱 면 촬영 무음 4K, 2026-10-29)이면 깊이도 256x144 라 main() 이 첫 깊이 파일로 다시 정한다
DEPTH_W, DEPTH_H = 256, 192
# ARKit camera (x right, y up, z backward)  ->  OpenCV camera (x right, y down, z forward)
F_ARKIT_TO_CV = np.diag([1.0, -1.0, -1.0, 1.0])


def quat_to_mat(qx, qy, qz, qw):
    n = math.sqrt(qx * qx + qy * qy + qz * qz + qw * qw)
    qx, qy, qz, qw = qx / n, qy / n, qz / n, qw / n
    return np.array([
        [1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qz * qw), 2 * (qx * qz + qy * qw)],
        [2 * (qx * qy + qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qx * qw)],
        [2 * (qx * qz - qy * qw), 2 * (qy * qz + qx * qw), 1 - 2 * (qx * qx + qy * qy)],
    ])


def read_odometry(path):
    with open(path, newline="") as f:
        reader = csv.reader(f)
        header = [h.strip() for h in next(reader)]
        rows = [r for r in reader if r and any(c.strip() for c in r)]
    col = {name: i for i, name in enumerate(header)}
    frames = []
    for r in rows:
        g = lambda k: float(r[col[k]])
        T = np.eye(4)
        T[:3, :3] = quat_to_mat(g("qx"), g("qy"), g("qz"), g("qw"))
        T[:3, 3] = [g("x"), g("y"), g("z")]
        K = None
        if "fx" in col and r[col["fx"]].strip():
            K = np.array([[g("fx"), 0, g("cx")], [0, g("fy"), g("cy")], [0, 0, 1]])
        frames.append(dict(t=g("timestamp"), idx=int(g("frame")), T_WC=T, K=K))
    return header, frames


BAD_TRACKING = {"initializing", "relocalizing", "notAvailable"}


def read_frame_quality(data_dir):
    """앱의 선택 파일 frame_quality.csv (frame,timestamp,blur_px,tracking,...) -> {frame: (blur_px, tracking)}.
    없거나 읽을 수 없으면 {} (기존 녹화는 그대로 처리)"""
    path = os.path.join(data_dir, "frame_quality.csv")
    q = {}
    if not os.path.exists(path):
        return q
    try:
        with open(path, newline="") as f:
            for r in csv.DictReader(f):
                try:
                    q[int(float(r["frame"]))] = (float(r.get("blur_px") or 0.0), (r.get("tracking") or "normal").strip())
                except (KeyError, ValueError, TypeError):
                    continue
    except OSError:
        return {}
    return q


def blur_factor(qual, idx, blur_ok=4.0):
    """키프레임 점수 배율: 흔들림 예측(가로 1920 px 기준)이 blur_ok 를 넘으면 그 비율만큼 낮추고 (8 px -> 0.5),
    추적 불량이면 크게 낮춘다"""
    b, tr = qual.get(idx, (0.0, "normal"))
    f = 1.0 / (1.0 + max(0.0, b / blur_ok - 1.0))
    return f * (0.1 if tr in BAD_TRACKING else 1.0)


def scale_intrinsics(K, rgb_w, rgb_h):
    sx, sy = DEPTH_W / rgb_w, DEPTH_H / rgb_h
    return o3d.camera.PinholeCameraIntrinsic(
        DEPTH_W, DEPTH_H, K[0, 0] * sx, K[1, 1] * sy, K[0, 2] * sx, K[1, 2] * sy)


def load_depth(data_dir, i, conf_min, far_m=0.0, conf_far=2):
    """far_m > 0: beyond far_m metres keep only confidence >= conf_far. Medium-confidence LiDAR returns at 2-4 m
    (glass, dark walls, people) fused into huge spiky triangles in a restaurant scan (c3c1e8c7); near-range medium
    returns are fine and fill holes, so only the far ones are dropped."""
    d = cv2.imread(os.path.join(data_dir, "depth", f"{i:06d}.png"), cv2.IMREAD_UNCHANGED)
    if d is None:
        return None
    if d.dtype != np.uint16:
        d = d.astype(np.uint16)
    if conf_min > 0 or far_m > 0:
        c = cv2.imread(os.path.join(data_dir, "confidence", f"{i:06d}.png"), cv2.IMREAD_UNCHANGED)
        if c is not None:
            d = d.copy()
            d[c < conf_min] = 0
            if far_m > 0:
                d[(d > far_m * 1000) & (c < conf_far)] = 0
    return d


def backproject(depth_u16, intr, T_WC, max_depth):
    """depth (mm) -> world points, OpenCV camera convention"""
    z = depth_u16.astype(np.float32) / 1000.0
    v, u = np.mgrid[0:z.shape[0], 0:z.shape[1]]
    m = (z > 0.05) & (z < max_depth)
    fx, fy = intr.intrinsic_matrix[0, 0], intr.intrinsic_matrix[1, 1]
    cx, cy = intr.intrinsic_matrix[0, 2], intr.intrinsic_matrix[1, 2]
    x = (u[m] - cx) / fx * z[m]
    y = (v[m] - cy) / fy * z[m]
    p = np.stack([x, y, z[m], np.ones_like(x)], axis=1)
    return (T_WC @ p.T).T[:, :3]


def detect_convention(data_dir, frames, avail, intr_of, max_depth, pairs=6, gap_s=0.5):
    """Return 'cv' if odometry poses already use the OpenCV camera frame, 'arkit' otherwise.
    Compares overlap of back-projected clouds ~gap_s seconds apart under both conventions."""
    avail = [i for i in avail if i < len(frames)]
    score = {"cv": 0.0, "arkit": 0.0}
    picks = np.linspace(0, len(avail) - 1, pairs + 2).astype(int)[1:-1]
    for p in picks:
        i = avail[p]
        later = [k for k in avail if frames[k]["t"] >= frames[i]["t"] + gap_s]
        if not later:
            continue
        j = later[0]
        di, dj = load_depth(data_dir, i, 1), load_depth(data_dir, j, 1)
        if di is None or dj is None:
            continue
        for name, F in (("cv", np.eye(4)), ("arkit", F_ARKIT_TO_CV)):
            pi = backproject(di, intr_of(i), frames[i]["T_WC"] @ F, max_depth)
            pj = backproject(dj, intr_of(j), frames[j]["T_WC"] @ F, max_depth)
            a = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(pi)).voxel_down_sample(0.03)
            b = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(pj)).voxel_down_sample(0.03)
            dist = np.asarray(a.compute_point_cloud_distance(b))
            score[name] += float(np.median(dist)) if len(dist) else 1e9
    print(f"[convention] median NN distance sum: cv={score['cv']:.4f}  arkit={score['arkit']:.4f}")
    return "cv" if score["cv"] <= score["arkit"] else "arkit"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--voxel", type=float, default=0.01)
    ap.add_argument("--every", type=int, default=2)
    ap.add_argument("--conf", type=int, default=1, help="min confidence 0..2")
    ap.add_argument("--far", type=float, default=2.0, help="beyond this depth (m) require --conf-far (0 = off)")
    ap.add_argument("--conf-far", type=int, default=2)
    ap.add_argument("--max-depth", type=float, default=4.0)
    ap.add_argument("--target-tris", type=int, default=400000)
    ap.add_argument("--max-frames", type=int, default=0)
    ap.add_argument("--convention", choices=["auto", "cv", "arkit"], default="auto")
    ap.add_argument("--weight-thr", type=float, default=3.0, help="min TSDF weight for surface extraction")
    ap.add_argument("--block-count", type=int, default=50000)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    t0 = time.time()

    header, frames = read_odometry(os.path.join(args.data, "odometry.csv"))
    avail = sorted(int(f[:6]) for f in os.listdir(os.path.join(args.data, "depth"))
                   if f.endswith(".png") and f[:6].isdigit())
    avail_set = set(avail)
    n_depth = (max(avail) + 1) if avail else 0
    cap = cv2.VideoCapture(os.path.join(args.data, "rgb.mp4"))
    if not cap.isOpened():
        sys.exit("cannot open rgb.mp4 (HEVC decode unsupported?)")
    rgb_w, rgb_h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    n_video = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    K_fallback = np.loadtxt(os.path.join(args.data, "camera_matrix.csv"), delimiter=",")
    global DEPTH_W, DEPTH_H
    d0 = cv2.imread(os.path.join(args.data, "depth", f"{avail[0]:06d}.png"), cv2.IMREAD_UNCHANGED) if avail else None
    if d0 is not None:
        DEPTH_H, DEPTH_W = d0.shape[:2]
    n = min(len(frames), n_depth, n_video if n_video > 0 else 10**9)
    if args.max_frames:
        n = min(n, args.max_frames)
    print(f"odometry header: {header}")
    print(f"frames: odometry={len(frames)} depth_files={len(avail)} (max idx {n_depth - 1}) "
          f"video={n_video} -> range {n}; rgb {rgb_w}x{rgb_h} @ {fps:.1f} fps")

    def intr_of(i):
        K = frames[i]["K"] if frames[i]["K"] is not None else K_fallback
        return scale_intrinsics(K, rgb_w, rgb_h)

    conv = args.convention
    if conv == "auto":
        conv = detect_convention(args.data, frames, [i for i in avail if i < n], intr_of, args.max_depth)
    F = np.eye(4) if conv == "cv" else F_ARKIT_TO_CV
    print(f"[convention] using: {conv}")

    # Tensor-based TSDF (the legacy ScalableTSDFVolume produced empty output with open3d 0.20)
    dev = o3c.Device("CPU:0")
    vbg = o3d.t.geometry.VoxelBlockGrid(
        attr_names=("tsdf", "weight", "color"),
        attr_dtypes=(o3c.float32, o3c.float32, o3c.float32),
        attr_channels=((1), (1), (3)),
        voxel_size=args.voxel, block_resolution=8, block_count=args.block_count, device=dev)

    qual = read_frame_quality(args.data)
    if qual:
        bl = np.array([b for b, _ in qual.values()])
        print(f"frame_quality: {len(qual)} frames, blur>4px(1920 기준) {np.mean(bl > 4.0) * 100:.1f}%, "
              f"bad tracking {sum(tr in BAD_TRACKING for _, tr in qual.values())}")
    used = skipped_track = 0
    t1 = time.time()
    for i in range(n):
        ok, bgr = cap.read()
        if not ok:
            print(f"video ended early at frame {i}")
            break
        if i % args.every or i not in avail_set:
            continue
        if qual.get(frames[i]["idx"], (0, "normal"))[1] in BAD_TRACKING:
            skipped_track += 1   # 재위치 잡기·초기화 중 자세는 믿을 수 없어 TSDF 에 넣지 않는다
            continue
        d = load_depth(args.data, i, args.conf, args.far, args.conf_far)
        if d is None:
            continue
        rgb = cv2.cvtColor(cv2.resize(bgr, (DEPTH_W, DEPTH_H), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)
        T_WC = frames[i]["T_WC"] @ F
        depth_t = o3d.t.geometry.Image(o3c.Tensor(np.ascontiguousarray(d))).to(dev)
        color_t = o3d.t.geometry.Image(o3c.Tensor(np.ascontiguousarray(rgb))).to(dev)
        K_t = o3c.Tensor(intr_of(i).intrinsic_matrix, o3c.float64)
        ext_t = o3c.Tensor(np.linalg.inv(T_WC), o3c.float64)
        blocks = vbg.compute_unique_block_coordinates(depth_t, K_t, ext_t, 1000.0, args.max_depth)
        vbg.integrate(blocks, depth_t, color_t, K_t, K_t, ext_t, 1000.0, args.max_depth)
        used += 1
        if used % 100 == 0:
            print(f"  integrated {used} frames (frame {i}/{n}) {time.time() - t1:.1f}s")
    cap.release()
    print(f"integration: {used} frames in {time.time() - t1:.1f}s"
          + (f" (skipped {skipped_track} bad-tracking frames)" if skipped_track else ""))

    t2 = time.time()
    print(f"voxel blocks: {vbg.hashmap().size()}")
    mesh = vbg.extract_triangle_mesh(weight_threshold=args.weight_thr).to_legacy()
    raw_tris = len(mesh.triangles)
    print(f"raw mesh: {len(mesh.vertices)} verts, {raw_tris} tris ({time.time() - t2:.1f}s)")

    # drop small floating pieces
    with o3d.utility.VerbosityContextManager(o3d.utility.VerbosityLevel.Error):
        cl, n_tri, _ = mesh.cluster_connected_triangles()
    cl, n_tri = np.asarray(cl), np.asarray(n_tri)
    keep_min = max(300, int(0.0005 * raw_tris))
    mesh.remove_triangles_by_mask(n_tri[cl] < keep_min)
    mesh.remove_unreferenced_vertices()
    print(f"after cleanup: {len(mesh.triangles)} tris (removed clusters < {keep_min} tris)")

    if args.target_tris and len(mesh.triangles) > 4 * args.target_tris:
        t3 = time.time()
        mesh = mesh.simplify_vertex_clustering(
            voxel_size=args.voxel * 1.5, contraction=o3d.geometry.SimplificationContraction.Average)
        print(f"after vertex clustering: {len(mesh.triangles)} tris ({time.time() - t3:.1f}s)")
    if args.target_tris and len(mesh.triangles) > args.target_tris:
        t3 = time.time()
        mesh = mesh.simplify_quadric_decimation(target_number_of_triangles=args.target_tris)
        print(f"after decimation: {len(mesh.triangles)} tris ({time.time() - t3:.1f}s)")
    mesh.remove_degenerate_triangles()
    mesh.remove_duplicated_vertices()
    mesh.compute_vertex_normals()

    bbox = mesh.get_axis_aligned_bounding_box()
    ext = bbox.get_extent()
    ply_path = os.path.join(args.out, "mesh.ply")
    o3d.io.write_triangle_mesh(ply_path, mesh, write_ascii=False, compressed=False)

    import trimesh
    tm = trimesh.Trimesh(
        vertices=np.asarray(mesh.vertices),
        faces=np.asarray(mesh.triangles),
        vertex_normals=np.asarray(mesh.vertex_normals),
        vertex_colors=np.clip(np.asarray(mesh.vertex_colors) * 255, 0, 255).astype(np.uint8),
        process=False)
    glb_path = os.path.join(args.out, "mesh.glb")
    tm.export(glb_path)

    stats = dict(
        dataset=os.path.abspath(args.data), frames_total=n, frames_used=used, every=args.every,
        voxel_m=args.voxel, conf_min=args.conf, max_depth_m=args.max_depth, convention=conv,
        rgb_size=[rgb_w, rgb_h], fps=fps, raw_triangles=raw_tris,
        triangles=len(mesh.triangles), vertices=len(mesh.vertices),
        bbox_extent_m=[round(float(e), 3) for e in ext],
        glb_bytes=os.path.getsize(glb_path), ply_bytes=os.path.getsize(ply_path),
        seconds_total=round(time.time() - t0, 1))
    with open(os.path.join(args.out, "stats.json"), "w") as f:
        json.dump(stats, f, indent=2)
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
