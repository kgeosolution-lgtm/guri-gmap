r"""
kgeoScan 물체 모드: 물체 영역(중심 + 반경) 정하기와 메시 자르기

  python -I object_region.py --zip <scan.zip> [--center x,y,z] [--radius 0.25] [--debug-image out.jpg]
  python -I object_region.py --data <dataset_dir> ...

좌표계: ARKit 월드(= odometry.csv, y 위, 미터). 앱이 탭으로 지정한 중심(obj_center)이 있으면 그대로 쓰고,
없으면 카메라 광축들이 가장 가깝게 모이는 점(최소제곱)을 중심으로 잡는다. 물체를 한 바퀴 돌며 찍으면
모든 카메라가 물체를 보고 있으므로 이 점이 물체 중심 근처가 된다.

반경: 앱 값(obj_radius) → 없으면 중심에서 LiDAR 로 본 물체 표면까지 거리로 추정 → 실패하면 0.25 m.
자르기 영역은 구(중심, 반경)이고, 아래쪽은 받침면 2 cm 까지만 남긴다(바닥·책상을 넓게 남기지 않기 위함).

다른 스크립트에서 쓰는 함수: resolve_region(), crop_mesh_file(), crop_splat_file(), keep_mask(), fit_footprint()
물체 몸통 좁히기: 구로 자른 메시에서 받침면 위 덩어리 중 중심축에 닿는 것을 물체로 보고 그 둘레 + 3 cm 원기둥(footprint)만 남긴다.
"""
import argparse
import csv
import json
import math
import os
import shutil
import sys
import tempfile
import zipfile

import numpy as np

DEFAULT_RADIUS = 0.25
MIN_RADIUS, MAX_RADIUS = 0.06, 1.5
AUTO_MIN_RADIUS = 0.12   # 자동 추정의 하한: 투명 물체는 LiDAR 가 표면을 못 봐 작게 나오므로 탁상 물체 크기를 기본으로 보장
BASE_KEEP = 0.02          # 받침면 아래로 남길 두께 (m)


def quat_to_mat(qx, qy, qz, qw):
    n = math.sqrt(qx * qx + qy * qy + qz * qz + qw * qw) or 1.0
    qx, qy, qz, qw = qx / n, qy / n, qz / n, qw / n
    return np.array([
        [1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qz * qw), 2 * (qx * qz + qy * qw)],
        [2 * (qx * qy + qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qx * qw)],
        [2 * (qx * qz - qy * qw), 2 * (qy * qz + qx * qw), 1 - 2 * (qx * qx + qy * qy)],
    ])


def read_poses(odometry_csv):
    """-> list of dict(idx, pos(3), R(3x3) camera->world, K(3x3 or None))  (OpenCV 카메라: x 오른쪽, y 아래, z 앞)"""
    out = []
    with open(odometry_csv, newline="") as f:
        rd = csv.reader(f)
        header = [h.strip() for h in next(rd)]
        col = {h: i for i, h in enumerate(header)}
        for r in rd:
            if not r or not any(c.strip() for c in r):
                continue
            g = lambda k: float(r[col[k]])
            K = None
            if "fx" in col and r[col["fx"]].strip():
                K = np.array([[g("fx"), 0, g("cx")], [0, g("fy"), g("cy")], [0, 0, 1.0]])
            out.append(dict(idx=int(g("frame")) if "frame" in col else len(out),
                            pos=np.array([g("x"), g("y"), g("z")]),
                            R=quat_to_mat(g("qx"), g("qy"), g("qz"), g("qw")), K=K))
    return out


def rays_closest_point(origins, dirs):
    """광선들(origin + t·dir, t>0)에 가장 가까운 점 (최소제곱). -> (점, 조건수)"""
    A = np.zeros((3, 3)); b = np.zeros(3)
    for o, d in zip(origins, dirs):
        d = d / np.linalg.norm(d)
        P = np.eye(3) - np.outer(d, d)
        A += P; b += P @ o
    try:
        p = np.linalg.solve(A, b)
    except np.linalg.LinAlgError:
        return None, float("inf")
    return p, float(np.linalg.cond(A))


def load_depth(data_dir, idx, conf_min=1):
    import cv2
    d = cv2.imread(os.path.join(data_dir, "depth", f"{idx:06d}.png"), cv2.IMREAD_UNCHANGED)
    if d is None:
        return None
    d = d.astype(np.float32) / 1000.0
    c = cv2.imread(os.path.join(data_dir, "confidence", f"{idx:06d}.png"), cv2.IMREAD_UNCHANGED)
    if c is not None and conf_min > 0:
        d[c < conf_min] = 0
    return d


def auto_center(poses, data_dir=None, step=None):
    """카메라 광축 교점. 광축이 거의 평행하면(한 방향만 찍음) 카메라 앞 LiDAR 깊이 중앙값 지점들의 평균으로 대신한다."""
    step = step or max(1, len(poses) // 120)
    sel = poses[::step]
    origins = np.array([p["pos"] for p in sel]); dirs = np.array([p["R"][:, 2] for p in sel])
    p, cond = rays_closest_point(origins, dirs)
    if p is not None:
        t = np.einsum("ij,ij->i", p - origins, dirs)            # 각 카메라 앞쪽 거리
        if cond < 1e4 and np.median(t) > 0.05 and np.median(t) < 4.0 and (t > 0).mean() > 0.8:
            return p, "rays", dict(cond=round(cond, 1), median_dist=round(float(np.median(t)), 3))
    # 대안: 카메라 + 광축 × (이미지 가운데 LiDAR 깊이 중앙값)
    aims = []
    if data_dir:
        for q in sel:
            d = load_depth(data_dir, q["idx"])
            if d is None:
                continue
            h, w = d.shape
            patch = d[h // 3: 2 * h // 3, w // 3: 2 * w // 3]
            if (patch > 0).any():
                aims.append(q["pos"] + q["R"][:, 2] * float(np.median(patch[patch > 0])))
    if aims:
        return np.mean(aims, axis=0), "depth", dict(n=len(aims))
    return origins.mean(axis=0) + dirs.mean(axis=0) * 0.5, "fallback", {}


def estimate_radius(poses, center, data_dir, step=None):
    """중심을 지나는 시선에서 LiDAR 가 처음 만나는 표면까지의 거리(=중심에서 앞 표면까지) 중앙값 × 2 + 3 cm (하한 AUTO_MIN_RADIUS).
    투명 물체는 깊이가 뒤 배경에 찍혀 음수가 되므로 그런 프레임은 버린다."""
    step = step or max(1, len(poses) // 60)
    gaps = []
    for q in poses[::step]:
        if q["K"] is None:
            continue
        pc = q["R"].T @ (center - q["pos"])                     # 카메라 좌표
        if pc[2] <= 0.05:
            continue
        d = load_depth(data_dir, q["idx"])
        if d is None:
            continue
        h, w = d.shape
        sx, sy = w / (q["K"][0, 2] * 2), h / (q["K"][1, 2] * 2)  # RGB → 깊이 해상도
        u = int(round((q["K"][0, 0] * pc[0] / pc[2] + q["K"][0, 2]) * sx))
        v = int(round((q["K"][1, 1] * pc[1] / pc[2] + q["K"][1, 2]) * sy))
        if not (2 <= u < w - 2 and 2 <= v < h - 2):
            continue
        patch = d[v - 2: v + 3, u - 2: u + 3]
        if not (patch > 0).any():
            continue
        z = float(np.median(patch[patch > 0]))
        dist = float(np.linalg.norm(center - q["pos"]))
        gap = dist - z                                           # 중심 앞 표면까지
        if 0.005 < gap < MAX_RADIUS:
            gaps.append(gap)
    if len(gaps) < 5:
        return DEFAULT_RADIUS, "default", {}
    r = float(np.clip(np.median(gaps) * 2.0 + 0.03, AUTO_MIN_RADIUS, MAX_RADIUS))
    return r, "lidar", dict(n=len(gaps), median_gap=round(float(np.median(gaps)), 3))


def support_floor_y(data_dir, poses, center, radius, step=None):
    """중심 아래 받침면(책상·바닥) 높이: 영역 안 LiDAR 점 중 중심보다 아래에 많이 모인 높이. 없으면 None"""
    step = step or max(1, len(poses) // 40)
    ys = []
    for q in poses[::step]:
        if q["K"] is None:
            continue
        d = load_depth(data_dir, q["idx"], conf_min=2)
        if d is None:
            continue
        h, w = d.shape
        sx, sy = w / (q["K"][0, 2] * 2), h / (q["K"][1, 2] * 2)
        vv, uu = np.nonzero(d > 0)
        if len(vv) == 0:
            continue
        sel = np.random.default_rng(q["idx"]).choice(len(vv), min(4000, len(vv)), replace=False)
        vv, uu = vv[sel], uu[sel]
        z = d[vv, uu]
        x = (uu / sx - q["K"][0, 2]) / q["K"][0, 0] * z
        y = (vv / sy - q["K"][1, 2]) / q["K"][1, 1] * z
        pw = (q["R"] @ np.stack([x, y, z])).T + q["pos"]
        inside = np.linalg.norm(pw - center, axis=1) < radius
        below = pw[:, 1] < center[1]
        ys.append(pw[inside & below, 1])
    if not ys:
        return None
    ys = np.concatenate(ys)
    if len(ys) < 200:
        return None
    hist, edges = np.histogram(ys, bins=max(10, int((ys.max() - ys.min()) / 0.005) + 1))
    k = int(hist.argmax())
    if hist[k] < 0.15 * len(ys):                                  # 뚜렷한 평면이 없음
        return None
    return float((edges[k] + edges[k + 1]) / 2)


def parse_center(s):
    if not s:
        return None
    try:
        v = [float(t) for t in str(s).replace(" ", "").split(",")]
    except ValueError:
        return None
    return np.array(v) if len(v) == 3 and all(math.isfinite(t) for t in v) else None


def find_dataset_root(folder):
    for root, dirs, files in os.walk(folder):
        if "odometry.csv" in files and "depth" in dirs:
            return root
    raise SystemExit("odometry.csv / depth 가 없음")


def resolve_region(data_dir, center=None, radius=None):
    """-> dict(center[3], radius, floor_y|None, center_by, radius_by, info)"""
    poses = read_poses(os.path.join(data_dir, "odometry.csv"))
    c = parse_center(center) if isinstance(center, str) else (np.asarray(center, float) if center is not None else None)
    info = {}
    if c is None:
        c, center_by, info["center"] = auto_center(poses, data_dir)
    else:
        center_by = "app"
    try:
        r = float(radius) if radius not in (None, "") else None
    except ValueError:
        r = None
    if r is None or not (MIN_RADIUS <= r <= MAX_RADIUS):
        r, radius_by, info["radius"] = estimate_radius(poses, c, data_dir)
    else:
        radius_by = "app"
    floor_y = support_floor_y(data_dir, poses, c, r)
    return dict(center=[round(float(t), 4) for t in c], radius=round(float(r), 3),
                floor_y=None if floor_y is None else round(floor_y, 4),
                center_by=center_by, radius_by=radius_by, info=info)


def keep_mask(points, region):
    """points (N,3) 중 물체 영역 안: 구 안이고, 받침면이 있으면 그 아래 BASE_KEEP 보다 위.
    footprint_r 이 있으면(메시에서 물체 몸통을 찾아 좁힌 경우) 그 수직 원기둥 안만 — 책상 원판·옆 물건을 뺀다."""
    c = np.asarray(region["center"]); r = float(region["radius"])
    m = np.linalg.norm(points - c, axis=1) <= r
    if region.get("floor_y") is not None:
        m &= points[:, 1] >= region["floor_y"] - BASE_KEEP
    fr = region.get("footprint_r")
    if fr:
        fc = region.get("footprint_center") or [c[0], c[2]]
        m &= np.hypot(points[:, 0] - fc[0], points[:, 2] - fc[1]) <= float(fr)
    return m


LIFT = 0.015          # 받침면 위 이 높이부터를 물체 몸통으로 본다
FOOT_MARGIN = 0.03    # 몸통 둘레에 남길 여유 (m)


def fit_footprint(V, T, region, log=None):
    """구로 자른 메시(V, T)에서 받침면 위로 솟은 덩어리 중 중심축에 닿는 것(=물체)을 찾아
    region 에 footprint_center([x, z]), footprint_r 을 넣는다. 받침면을 모르거나 덩어리를 못 찾으면 그대로 둔다."""
    import open3d as o3d
    fy = region.get("floor_y")
    if fy is None or len(T) == 0:
        return region
    above_v = V[:, 1] > fy + LIFT
    above_t = above_v[T].all(axis=1)
    if above_t.sum() < 100:
        return region
    sub = o3d.geometry.TriangleMesh(o3d.utility.Vector3dVector(V), o3d.utility.Vector3iVector(T[above_t]))
    with o3d.utility.VerbosityContextManager(o3d.utility.VerbosityLevel.Error):
        labels, counts, _ = sub.cluster_connected_triangles()
    labels = np.asarray(labels)
    c = np.asarray(region["center"]); r = float(region["radius"])
    rc = max(0.03, 0.25 * r)                                   # 중심축 둘레 원기둥: 여기에 닿는 덩어리가 물체
    keep_vert = np.zeros(len(V), bool)
    T_above = T[above_t]
    for k in range(len(counts)):
        tv = np.unique(T_above[labels == k])
        if len(tv) == 0:
            continue
        dmin = np.hypot(V[tv, 0] - c[0], V[tv, 2] - c[2]).min()
        if dmin <= rc and counts[k] >= 20:
            keep_vert[tv] = True
    if keep_vert.sum() < 50:
        return region
    P = V[keep_vert]
    fc = [float(np.median(P[:, 0])), float(np.median(P[:, 2]))]
    d = np.hypot(P[:, 0] - fc[0], P[:, 2] - fc[1])
    fr = float(min(np.percentile(d, 98) + FOOT_MARGIN, r))
    region["footprint_center"] = [round(fc[0], 4), round(fc[1], 4)]
    region["footprint_r"] = round(fr, 3)
    region["object_top_y"] = round(float(P[:, 1].max()), 4)
    if log:
        log(f"footprint: center {region['footprint_center']} r {region['footprint_r']} (sphere r {r}), height {P[:, 1].max() - fy:.3f} m")
    return region


def crop_mesh_file(ply_in, ply_out, region, tighten=True):
    """삼각형의 세 꼭짓점이 모두 영역 안인 것만 남긴다 -> (남은 삼각형 수, 원래 삼각형 수).
    tighten: 먼저 구로 자른 메시에서 물체 몸통을 찾아 region 에 footprint 를 기록하고(스플랫 자르기도 같은 값을 씀) 그 원기둥으로 자른다."""
    import open3d as o3d
    mesh = o3d.io.read_triangle_mesh(ply_in)
    V = np.asarray(mesh.vertices); T = np.asarray(mesh.triangles)
    if tighten and not region.get("footprint_r"):
        in_sphere = keep_mask(V, region)
        fit_footprint(V, T[in_sphere[T].all(axis=1)], region)
    keep_v = keep_mask(V, region)
    keep_t = keep_v[T].all(axis=1)
    n0 = len(T)
    mesh.remove_triangles_by_mask(~keep_t)
    mesh.remove_unreferenced_vertices()
    o3d.io.write_triangle_mesh(ply_out, mesh)
    return int(keep_t.sum()), int(n0)


SPLAT_RECORD = np.dtype([("pos", "<f4", 3), ("scale", "<f4", 3), ("rgba", "u1", 4), ("rot", "u1", 4)])   # antimatter15 .splat, 32 B


def crop_splat_file(splat_in, splat_out, region):
    """.splat 에서 물체 영역 안의 가우시안만 남긴다 -> (남은 수, 원래 수). 좌표계는 학습 월드 = odometry 월드"""
    rec = np.fromfile(splat_in, dtype=SPLAT_RECORD)
    keep = keep_mask(rec["pos"].astype(np.float64), region)
    rec[keep].tofile(splat_out)
    return int(keep.sum()), int(len(rec))


def debug_image(data_dir, poses, region, out_path):
    """가장 선명한 프레임 하나에 영역(구)의 윤곽과 중심을 그려 저장"""
    import cv2
    cap = cv2.VideoCapture(os.path.join(data_dir, "rgb.mp4"))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    best = None
    for i in np.linspace(0, n - 1, 16).astype(int):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i)); ok, fr = cap.read()
        if not ok:
            continue
        s = cv2.Laplacian(cv2.cvtColor(cv2.resize(fr, (480, 360)), cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
        if best is None or s > best[0]:
            best = (s, int(i), fr)
    cap.release()
    if best is None:
        return
    _, idx, fr = best
    q = min(poses, key=lambda p: abs(p["idx"] - idx))
    c = np.asarray(region["center"]); r = region["radius"]
    pc = q["R"].T @ (c - q["pos"])
    if pc[2] > 0 and q["K"] is not None:
        u = q["K"][0, 0] * pc[0] / pc[2] + q["K"][0, 2]; v = q["K"][1, 1] * pc[1] / pc[2] + q["K"][1, 2]
        rad = q["K"][0, 0] * r / pc[2]
        cv2.circle(fr, (int(u), int(v)), int(rad), (0, 0, 255), 6)
        cv2.drawMarker(fr, (int(u), int(v)), (0, 255, 255), cv2.MARKER_CROSS, 60, 6)
    ok, buf = cv2.imencode(".jpg", cv2.resize(fr, (fr.shape[1] // 2, fr.shape[0] // 2)), [cv2.IMWRITE_JPEG_QUALITY, 80])
    open(out_path, "wb").write(buf.tobytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data"); ap.add_argument("--zip")
    ap.add_argument("--center"); ap.add_argument("--radius")
    ap.add_argument("--debug-image")
    ap.add_argument("--out-json")
    a = ap.parse_args()
    tmp = None
    try:
        data = a.data
        if a.zip:
            tmp = tempfile.mkdtemp(prefix="objreg_")
            with zipfile.ZipFile(a.zip) as zf:
                names = [n for n in zf.namelist() if not (n.startswith("/") or ".." in n.split("/"))]
                want = [n for n in names if n.endswith(("odometry.csv", "rgb.mp4")) or "/depth/" in n or "/confidence/" in n
                        or n.startswith(("depth/", "confidence/"))]
                zf.extractall(tmp, members=want)
            data = find_dataset_root(tmp)
        region = resolve_region(data, a.center, a.radius)
        print(json.dumps(region, ensure_ascii=False))
        if a.out_json:
            json.dump(region, open(a.out_json, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        if a.debug_image:
            debug_image(data, read_poses(os.path.join(data, "odometry.csv")), region, a.debug_image)
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
