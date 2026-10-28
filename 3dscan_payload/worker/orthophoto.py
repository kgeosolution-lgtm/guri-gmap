r"""
kgeoScan 정사영상: 융합 메시 + 사진(고해상도 정지 사진 또는 영상 키프레임) -> 위/정면에서 본 실측 이미지

  python -I orthophoto.py --data <Stray dataset dir> --mesh <mesh.ply> --out <out_dir>
         [--surface auto|floor|wall] [--gsd 0.001] [--max-px 6000]
         [--lon 127.06 --lat 37.28 --heading 0 --utm-epsg 32652]      (바닥: 지도에 겹칠 좌표)

사진: <data>/hires/poses.json 이 있으면 고해상도 정지 사진(앱 면 촬영 모드), 없으면 rgb.mp4 키프레임.
  hires/poses.json 의 transform 은 odometry.csv 행과 같은 월드·같은 카메라 규약(앱이 같은 인코더로 씀).

바닥(floor): 위에서 수직으로 내려다본 영상. 격자는 동(E)·북(N) 방향이라 world file(.jgw)·.prj 로 UTM 좌표가 붙고,
  지도 오버레이용 네 모서리 경위도를 ortho.json 에 넣는다.
벽(wall): 메시에서 가장 큰 수직면을 찾아 정면에서 본 영상(가로 = 벽 방향, 세로 = 위). 좌표 없이 mm 축척만.
auto: 카메라들이 주로 아래를 봤으면 floor, 수평으로 봤으면 wall.

각 픽셀: 메시에 광선을 쏴 표면점을 얻고, 그 점을 가장 정면·가까이·선명하게 본 사진 하나에서 색을 가져온다
(가림은 사진별 레이캐스트 깊이로 판정). 메모리를 적게 쓰도록 큰 배열은 디스크(memmap)에 두고 사진을 하나씩 읽는다.

출력: ortho.jpg(원본 해상도), ortho_overlay.png(긴 변 ≤2048, 투명 배경), ortho.json, [바닥] ortho.jgw, ortho.prj
"""
import argparse
import csv
import gc
import json
import math
import os
import shutil
import sys
import time

import cv2
import numpy as np
import open3d as o3d
import open3d.core as o3c

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stray_to_mesh import read_odometry, F_ARKIT_TO_CV  # noqa: E402

TILE = 1024
UP = np.array([0.0, 1.0, 0.0])


# ── 사진 목록 ────────────────────────────────────────────────────────────────
def hires_views(data, Fx):
    p = os.path.join(data, "hires", "poses.json")
    if not os.path.exists(p):
        return None
    js = json.load(open(p, encoding="utf-8"))
    views = []
    for im in js.get("images", []):
        f = os.path.join(data, im["file"]) if not os.path.isabs(im["file"]) else im["file"]
        if not os.path.exists(f):
            continue
        T = np.array(im["transform"], dtype=np.float64).reshape(4, 4, order="F")
        K = np.array([[im["fx"], 0, im["cx"]], [0, im["fy"], im["cy"]], [0, 0, 1.0]])
        views.append(dict(path=f, T_WC=T @ Fx, K=K, w=int(im["width"]), h=int(im["height"])))
    return views or None


def video_views(data, frames, Fx, n_keep, tmp, log):
    """rgb.mp4 에서 창마다 가장 선명한 프레임을 골라 JPEG 로 저장 (메모리에 쌓지 않음)"""
    path = os.path.join(data, "rgb.mp4")
    cap = cv2.VideoCapture(path)
    n = min(int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), len(frames))
    win = max(1, n // n_keep)
    best = {}
    for i in range(n):
        ok, bgr = cap.read()
        if not ok:
            break
        s = cv2.Laplacian(cv2.cvtColor(cv2.resize(bgr, (480, 360)), cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
        w = i // win
        if w not in best or s > best[w][0]:
            best[w] = (s, i)
    cap.release()
    chosen = sorted(i for _, i in best.values())
    cap = cv2.VideoCapture(path)
    views, j = [], 0
    for i in range(n):
        ok, bgr = cap.read()
        if not ok:
            break
        if j < len(chosen) and i == chosen[j]:
            f = os.path.join(tmp, f"kf_{i:06d}.jpg")
            cv2.imwrite(f, bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])
            h, w = bgr.shape[:2]
            fr = frames[i]
            views.append(dict(path=f, T_WC=fr["T_WC"] @ Fx, K=fr["K"], w=w, h=h))
            j += 1
    cap.release()
    log(f"video keyframes: {len(views)} of {n} frames (window {win})")
    return views


def load_rgb(path):
    # 앱 hires/*.jpg 는 센서 방향 픽셀 + EXIF 회전값(6)이고 내부 파라미터도 센서 방향 기준이다.
    # IMREAD_COLOR 만 주면 OpenCV 가 EXIF 대로 돌려 버려(400x300 -> 300x400 확인) 자세와 어긋나므로 회전을 무시한다
    img = cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION)
    return None if img is None else cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def sharpness(img):
    small = cv2.resize(img, (480, int(480 * img.shape[0] / img.shape[1])), interpolation=cv2.INTER_AREA)
    return float(cv2.Laplacian(cv2.cvtColor(small, cv2.COLOR_RGB2GRAY), cv2.CV_64F).var())


# ── 투영 면 ─────────────────────────────────────────────────────────────────
def choose_surface(views, requested):
    if requested in ("floor", "wall"):
        return requested
    fwd_y = np.array([v["T_WC"][:3, 2] @ UP for v in views])        # OpenCV 카메라: +z 가 앞
    return "floor" if np.median(fwd_y) < -0.5 else "wall"


def wall_frame(mesh, views):
    """가장 큰 수직면의 법선(수평)과 그 면 위의 점 -> (n, u, v, p0)"""
    mesh.compute_triangle_normals()
    TN = np.asarray(mesh.triangle_normals); V = np.asarray(mesh.vertices); F = np.asarray(mesh.triangles)
    area = 0.5 * np.linalg.norm(np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]), axis=1)
    vert = np.abs(TN[:, 1]) < 0.3
    az = np.arctan2(TN[vert, 2], TN[vert, 0])
    hist, edges = np.histogram(np.mod(az, np.pi), bins=72, range=(0, np.pi), weights=area[vert])   # 앞뒤 법선을 같은 면으로
    k = int(hist.argmax()); a = (edges[k] + edges[k + 1]) / 2
    n = np.array([math.cos(a), 0.0, math.sin(a)])
    cams = np.array([v["T_WC"][:3, 3] for v in views])
    cen = V[F[vert]].mean(axis=1)
    sel = np.abs(np.abs((TN[vert] @ n)) - 1) < 0.15
    d = cen[sel] @ n
    d0 = float(np.median(d)) if len(d) else float((V @ n).mean())
    if (cams.mean(axis=0) @ n) < d0:                                 # 법선이 카메라 쪽을 보게
        n, d0 = -n, -d0
    u = np.cross(UP, n); u /= np.linalg.norm(u)
    return n, u, UP.copy(), d0


# ── 레이캐스트 ──────────────────────────────────────────────────────────────
def view_depth(scene, K, T_WC, w, h, scale):
    Ks = K.copy(); Ks[:2] *= scale
    sw, sh = max(8, int(w * scale)), max(8, int(h * scale))
    rays = scene.create_rays_pinhole(o3c.Tensor(Ks, o3c.float64), o3c.Tensor(np.linalg.inv(T_WC), o3c.float64), sw, sh)
    t = scene.cast_rays(rays)["t_hit"].numpy()
    d = rays.numpy()[..., 3:6]
    R_cw = np.linalg.inv(T_WC)[:3, :3]
    z = (t.reshape(-1) * (d.reshape(-1, 3) @ R_cw[2])).reshape(sh, sw)
    z[~np.isfinite(z)] = np.inf
    return z.astype(np.float32), sw, sh


def bilinear(img, u, v):
    h, w = img.shape[:2]
    u = np.clip(u, 0, w - 1.001); v = np.clip(v, 0, h - 1.001)
    x0 = u.astype(np.int32); y0 = v.astype(np.int32)
    fx = (u - x0)[:, None]; fy = (v - y0)[:, None]
    c = (img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x0 + 1] * fx * (1 - fy)
         + img[y0 + 1, x0] * (1 - fx) * fy + img[y0 + 1, x0 + 1] * fx * fy)
    return np.clip(c + 0.5, 0, 255).astype(np.uint8)


def estimate_gains(views, P, Nn, valid, scene, log, n_samples=150_000, slots=6, sigma_n=10.0, sigma_g=0.1):
    """사진별 RGB 밝기 배율 (OpenCV GainCompensator 와 같은 식):
    min Σ_ij N_ij [ (g_i·I_ij − g_j·I_ji)² / σn² + (1 − g_i)² / σg² ],  I_ij = 사진 i 가 j 와 함께 본 표본점들의 평균 색.
    표본: 표면 격자에서 고르게 뽑은 점, 색은 1/4 축소 사진(작은 어긋남·잡음에 강함), 포화(반사광)·너무 어두운 점은 뺀다."""
    t0 = time.time()
    Hh, W = valid.shape
    step = max(1, int(math.sqrt(valid.sum() / n_samples)))
    ys, xs = np.nonzero(valid[::step, ::step])
    ys, xs = ys * step, xs * step
    S, nV = len(ys), len(views)
    if S < 100 or nV < 2:
        return np.ones((nV, 3))
    pts = P[ys, xs].astype(np.float64)
    nrm = Nn[ys, xs].astype(np.float64)
    obs_v = np.full((S, slots), -1, np.int32)
    obs_c = np.zeros((S, slots, 3), np.float32)
    n_obs = np.zeros(S, np.int32)
    for vi, v in enumerate(views):
        img = cv2.imdecode(np.fromfile(v["path"], np.uint8), cv2.IMREAD_REDUCED_COLOR_4 | cv2.IMREAD_IGNORE_ORIENTATION)
        if img is None:
            continue
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h4, w4 = img.shape[:2]
        K = v["K"].copy()
        K[0] *= w4 / v["w"]
        K[1] *= h4 / v["h"]
        T_CW = np.linalg.inv(v["T_WC"])
        pc = pts @ T_CW[:3, :3].T + T_CW[:3, 3]
        z = pc[:, 2]
        good = z > 0.08
        u = K[0, 0] * pc[:, 0] / np.where(good, z, 1) + K[0, 2]
        vv = K[1, 1] * pc[:, 1] / np.where(good, z, 1) + K[1, 2]
        good &= (u > 4) & (u < w4 - 4) & (vv > 4) & (vv < h4 - 4)
        if not good.any():
            continue
        dz, sw, shh = view_depth(scene, K, v["T_WC"], w4, h4, 1.0)
        zd = dz[np.clip(vv.astype(int), 0, shh - 1), np.clip(u.astype(int), 0, sw - 1)]
        good &= z <= zd + 0.02 + 0.03 * z
        to_cam = v["T_WC"][:3, 3] - pts
        to_cam /= np.linalg.norm(to_cam, axis=1, keepdims=True) + 1e-9
        good &= np.abs((nrm * to_cam).sum(axis=1)) > 0.4
        idx = np.flatnonzero(good & (n_obs < slots))
        if len(idx) == 0:
            continue
        c = bilinear(img, u[idx], vv[idx]).astype(np.float32)
        ok = (c.max(axis=1) < 245) & (c.min(axis=1) > 8)
        idx, c = idx[ok], c[ok]
        obs_v[idx, n_obs[idx]] = vi
        obs_c[idx, n_obs[idx]] = c
        n_obs[idx] += 1
    # 쌍마다 겹친 표본 수 N_ij 와 평균 색 I_ij
    N = np.zeros((nV, nV))
    I = np.zeros((nV, nV, 3))
    for a_ in range(slots):
        for b_ in range(slots):
            if a_ == b_:
                continue
            m = (obs_v[:, a_] >= 0) & (obs_v[:, b_] >= 0)
            if not m.any():
                continue
            np.add.at(N, (obs_v[m, a_], obs_v[m, b_]), 1.0)
            np.add.at(I, (obs_v[m, a_], obs_v[m, b_]), obs_c[m, a_])
    I = I / np.maximum(N, 1)[..., None]
    gains = np.ones((nV, 3))
    for ch in range(3):
        A = np.zeros((nV, nV))
        b = np.zeros(nV)
        Ic = I[..., ch]
        for i in range(nV):
            for j in range(nV):
                if i == j or N[i, j] == 0:
                    continue
                A[i, i] += N[i, j] * (Ic[i, j] ** 2 / sigma_n ** 2 + 1 / sigma_g ** 2)
                A[i, j] -= N[i, j] * Ic[i, j] * Ic[j, i] / sigma_n ** 2
                b[i] += N[i, j] / sigma_g ** 2
        lone = A.diagonal() == 0                               # 겹친 데가 없는 사진은 1 그대로
        A[lone, lone] = 1.0
        b[lone] = 1.0
        gains[:, ch] = np.linalg.solve(A, b)
    pairs = int((N > 0).sum() // 2)
    log(f"gain compensation: {S} samples, {pairs} overlapping pairs, gains {gains.min():.2f}..{gains.max():.2f} ({time.time() - t0:.1f}s)")
    return np.clip(gains, 0.5, 2.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--mesh", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--surface", default="auto", choices=["auto", "floor", "wall"])
    ap.add_argument("--gsd", type=float, default=0.0, help="m/px (0 = 사진 해상도에 맞춰 자동)")
    ap.add_argument("--min-gsd", type=float, default=0.0003)
    ap.add_argument("--max-px", type=int, default=6000)
    ap.add_argument("--keyframes", type=int, default=90)
    ap.add_argument("--convention", choices=["cv", "arkit"], default="cv")
    ap.add_argument("--lon", type=float); ap.add_argument("--lat", type=float)
    ap.add_argument("--heading", type=float, default=0.0)
    ap.add_argument("--utm-epsg", type=int, default=32652)
    ap.add_argument("--jpeg-quality", type=int, default=90)
    ap.add_argument("--no-gain-comp", dest="gain_comp", action="store_false", help="사진별 밝기 맞춤 끄기")
    ap.add_argument("--blend-power", type=float, default=4.0, help="저주파 섞기 지수 (0 = 점수 1등 사진만, 클수록 1등 사진 쪽으로)")
    a = ap.parse_args()

    t0 = time.time()
    log = lambda m: print(f"[{time.time() - t0:6.1f}s] {m}", flush=True)
    os.makedirs(a.out, exist_ok=True)
    tmp = os.path.join(a.out, "_ortho_tmp")
    shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
    Fx = np.eye(4) if a.convention == "cv" else F_ARKIT_TO_CV

    mesh = o3d.io.read_triangle_mesh(a.mesh)
    mesh.remove_unreferenced_vertices()
    V = np.asarray(mesh.vertices)
    log(f"mesh: {len(V)} verts, {len(mesh.triangles)} tris")
    scene = o3d.t.geometry.RaycastingScene()
    scene.add_triangles(o3d.t.geometry.TriangleMesh.from_legacy(mesh))

    views = hires_views(a.data, Fx)
    source = "hires" if views else "video"
    if not views:
        _, frames = read_odometry(os.path.join(a.data, "odometry.csv"))
        views = video_views(a.data, frames, Fx, a.keyframes, tmp, log)
    log(f"views: {len(views)} ({source})")

    surface = choose_surface(views, a.surface)
    # 격자 좌표계: 원점 o, 가로 축 ex, 세로 축 ey(이미지 아래 방향), 광선 방향 ray
    if surface == "floor":
        th = math.radians(a.heading)
        c, s = math.cos(th), math.sin(th)
        # ARKit (x, z) <-> ENU (e, n): e = c x - s z, n = -s x - c z  (process_scan.write_las 와 같음; 자기 자신이 역행렬)
        east = np.array([c, 0.0, -s]); north = np.array([-s, 0.0, -c])
        cam_top = max(v["T_WC"][1, 3] for v in views)
        Vb = V[V[:, 1] < cam_top] if (V[:, 1] < cam_top).sum() > 100 else V     # 천장 제외한 범위
        E = Vb @ east; N = Vb @ north
        e0, e1, n0, n1 = E.min(), E.max(), N.min(), N.max()
        ex, ey = east, -north                      # 이미지: 오른쪽 = 동, 아래 = 남
        origin_uv = (e0, -n1)
        ext_u, ext_v = e1 - e0, n1 - n0
        ray = -UP
        # 광선은 카메라 높이 바로 위에서 쏜다: 메시 꼭대기에서 쏘면 천장을 먼저 맞힌다
        top = cam_top + 0.15
        plane_info = dict(axis_right="east", axis_down="south", heading_deg=a.heading)
    else:
        nrm, u_ax, v_ax, d0 = wall_frame(mesh, views)
        TN = np.asarray(mesh.triangle_normals); F = np.asarray(mesh.triangles)
        near = (np.abs(V @ nrm - d0) < 0.3)
        Vn = V[near] if near.sum() > 50 else V
        U = Vn @ u_ax; H = Vn @ v_ax
        ex, ey = u_ax, -v_ax                       # 오른쪽 = 벽을 따라, 아래 = 아래
        origin_uv = (U.min(), -H.max())
        ext_u, ext_v = U.max() - U.min(), H.max() - H.min()
        ray = -nrm
        front = d0 + 1.0
        plane_info = dict(normal=np.round(nrm, 4).tolist(), offset=round(d0, 4), axis_right=np.round(u_ax, 4).tolist())
    log(f"surface: {surface}, extent {ext_u:.2f} x {ext_v:.2f} m")

    # 해상도: 사진이 표면을 보는 거리 / 초점거리
    if a.gsd > 0:
        gsd = a.gsd
    else:
        dists = []
        for v in views[:: max(1, len(views) // 20)]:
            cam = v["T_WC"][:3, 3]; fwd = v["T_WC"][:3, 2]
            r = o3c.Tensor(np.concatenate([cam, fwd])[None].astype(np.float32))
            t = float(scene.cast_rays(r)["t_hit"].numpy()[0])
            if np.isfinite(t):
                dists.append(t / v["K"][0, 0])
        gsd = float(np.median(dists)) if dists else 0.002
    gsd = max(gsd, a.min_gsd, max(ext_u, ext_v) / a.max_px)
    W, Hh = max(1, int(math.ceil(ext_u / gsd))), max(1, int(math.ceil(ext_v / gsd)))
    log(f"gsd {gsd * 1000:.2f} mm/px -> {W} x {Hh} px")

    # ── 1) 표면점 (memmap) ──
    P = np.lib.format.open_memmap(os.path.join(tmp, "P.npy"), mode="w+", dtype=np.float32, shape=(Hh, W, 3))
    Nn = np.lib.format.open_memmap(os.path.join(tmp, "N.npy"), mode="w+", dtype=np.float16, shape=(Hh, W, 3))
    valid = np.zeros((Hh, W), bool)
    tiles = []
    for ty in range(0, Hh, TILE):
        for tx in range(0, W, TILE):
            h_, w_ = min(TILE, Hh - ty), min(TILE, W - tx)
            jj, ii = np.meshgrid(np.arange(tx, tx + w_) + 0.5, np.arange(ty, ty + h_) + 0.5)
            uu = origin_uv[0] + jj * gsd; vv = origin_uv[1] + ii * gsd          # 이미지 축 좌표 (m)
            if surface == "floor":
                pts = uu[..., None] * ex + vv[..., None] * ey
                pts[..., 1] = top
            else:
                pts = uu[..., None] * ex + vv[..., None] * ey + front * nrm
            rays = np.concatenate([pts.reshape(-1, 3), np.broadcast_to(ray, (h_ * w_, 3))], axis=1).astype(np.float32)
            hit = scene.cast_rays(o3c.Tensor(rays))
            t = hit["t_hit"].numpy().reshape(h_, w_)
            ok = np.isfinite(t)
            with np.errstate(invalid="ignore"):
                hp = pts + np.where(ok, t, 0)[..., None] * ray
            P[ty:ty + h_, tx:tx + w_] = np.where(ok[..., None], hp, 0).astype(np.float32)
            Nn[ty:ty + h_, tx:tx + w_] = hit["primitive_normals"].numpy().reshape(h_, w_, 3).astype(np.float16)
            valid[ty:ty + h_, tx:tx + w_] = ok
            if ok.any():
                q = hp[ok]
                corners = np.array([[x, y, z] for x in (q[:, 0].min(), q[:, 0].max())
                                    for y in (q[:, 1].min(), q[:, 1].max()) for z in (q[:, 2].min(), q[:, 2].max())])
                tiles.append((ty, tx, h_, w_, corners, q.mean(axis=0)))
    log(f"surface points: {valid.mean() * 100:.1f}% of {W}x{Hh}, {len(tiles)} tiles")

    # ── 1b) 사진별 밝기 맞춤 (겹치는 곳의 평균 색을 비교해 사진마다 RGB 배율) ──
    gains = estimate_gains(views, P, Nn, valid, scene, log) if a.gain_comp else np.ones((len(views), 3))

    # ── 2) 사진마다 맡을 픽셀 고르기 ──
    best = np.lib.format.open_memmap(os.path.join(tmp, "best.npy"), mode="w+", dtype=np.float32, shape=(Hh, W))
    best[:] = -1.0
    col = np.lib.format.open_memmap(os.path.join(tmp, "col.npy"), mode="w+", dtype=np.uint8, shape=(Hh, W, 3))
    col[:] = 0
    # 2대역 섞기(다중 대역 섞기의 간단판): 세부(고주파) = 점수 1등 사진의 (색 − 그 사진의 저주파),
    # 큰 흐름(저주파) = 여러 사진 저주파의 가중 평균(w = 점수^p, 1/4 해상도에 누적).
    # → 사진마다 다른 밝기·비네팅 경계는 사라지고, 글씨·균열은 한 장에서만 와서 이중으로 번지지 않는다(평균 섞기는 2~4 mm 어긋남으로 번졌다)
    blend = a.blend_power > 0
    if blend:
        Lb = np.lib.format.open_memmap(os.path.join(tmp, "Lb.npy"), mode="w+", dtype=np.uint8, shape=(Hh, W, 3))
        H4, W4 = (Hh + 3) // 4, (W + 3) // 4
        accL = np.zeros((H4 * W4, 3), np.float64)
        wL = np.zeros(H4 * W4, np.float64)
    used = 0
    for vi, v in enumerate(views):
        img = load_rgb(v["path"])
        if img is None:
            continue
        h, w = img.shape[:2]
        K = v["K"].copy()
        if (w, h) != (v["w"], v["h"]):                     # 저장 해상도가 다르면 내부 파라미터 맞춤
            K[0] *= w / v["w"]; K[1] *= h / v["h"]
        T_CW = np.linalg.inv(v["T_WC"]); cam = v["T_WC"][:3, 3]
        sh_w = 0.6 + 0.4 * min(1.0, sharpness(img) / 800.0)
        if blend:                                          # 사진의 저주파: 1/4 축소 + 가우시안(σ 4 → 원본 약 16 px)
            img_low = cv2.GaussianBlur(cv2.resize(img, (w // 4, h // 4), interpolation=cv2.INTER_AREA), (0, 0), 4)
        dz, sw, shh = view_depth(scene, K, v["T_WC"], w, h, 800.0 / max(w, h))
        dscale = sw / w
        touched = False
        for (ty, tx, h_, w_, corners, cen) in tiles:
            pc = corners @ T_CW[:3, :3].T + T_CW[:3, 3]
            zc = pc[:, 2]
            if (zc <= 0.05).all():
                continue
            uc = K[0, 0] * pc[:, 0] / np.maximum(zc, 1e-3) + K[0, 2]
            vc = K[1, 1] * pc[:, 1] / np.maximum(zc, 1e-3) + K[1, 2]
            if uc.max() < 0 or uc.min() > w or vc.max() < 0 or vc.min() > h:
                continue
            ok = valid[ty:ty + h_, tx:tx + w_]
            if not ok.any():
                continue
            pts = P[ty:ty + h_, tx:tx + w_][ok].astype(np.float64)
            nr = Nn[ty:ty + h_, tx:tx + w_][ok].astype(np.float64)
            pc = pts @ T_CW[:3, :3].T + T_CW[:3, 3]
            z = pc[:, 2]
            good = z > 0.08
            u = K[0, 0] * pc[:, 0] / np.where(good, z, 1) + K[0, 2]
            vv = K[1, 1] * pc[:, 1] / np.where(good, z, 1) + K[1, 2]
            m = 8
            good &= (u > m) & (u < w - m) & (vv > m) & (vv < h - m)
            if not good.any():
                continue
            zd = dz[np.clip((vv * dscale).astype(int), 0, shh - 1), np.clip((u * dscale).astype(int), 0, sw - 1)]
            good &= z <= zd + 0.03 + 0.05 * z      # 깊이 지도 해상도·메시 오차 여유 (너무 빡빡하면 점박이 구멍)
            to_cam = cam - pts
            to_cam /= np.linalg.norm(to_cam, axis=1, keepdims=True) + 1e-9
            cosang = np.abs((nr * to_cam).sum(axis=1))
            good &= cosang > 0.3
            border = np.minimum(np.minimum(u, w - u), np.minimum(vv, h - vv)) / (0.2 * min(w, h))
            sc = cosang ** 2 / (z + 0.2) * sh_w * np.clip(border, 0.25, 1.0)
            sc = np.where(good, sc, -1.0).astype(np.float32)
            bt = best[ty:ty + h_, tx:tx + w_]
            if blend and good.any():
                # 저주파 누적: 이 사진이 보는 모든 표면 픽셀 → 1/4 격자
                gi = np.flatnonzero(ok.reshape(-1))[good]
                g_r, g_c = np.unravel_index(gi, ok.shape)
                lowv = bilinear(img_low, u[good] / 4.0, vv[good] / 4.0).astype(np.float64) * gains[vi]
                q = ((ty + g_r) // 4) * W4 + (tx + g_c) // 4
                wq = np.power(sc[good].astype(np.float64), a.blend_power)
                for ch in range(3):
                    accL[:, ch] += np.bincount(q, weights=wq * lowv[:, ch], minlength=H4 * W4)
                wL[:] += np.bincount(q, weights=wq, minlength=H4 * W4)
            cur = bt[ok]
            win = sc > cur
            if not win.any():
                continue
            idx = np.flatnonzero(ok.reshape(-1))[win]
            rows, cols_ = np.unravel_index(idx, ok.shape)
            colv = bilinear(img, u[win], vv[win])
            if np.any(gains[vi] != 1.0):
                colv = np.clip(colv.astype(np.float32) * gains[vi] + 0.5, 0, 255).astype(np.uint8)
            bt[rows, cols_] = sc[win]
            ct = col[ty:ty + h_, tx:tx + w_]
            ct[rows, cols_] = colv
            if blend:                                      # 1등 사진의 저주파도 같이 기억 (세부 = 색 − 이것)
                lb = bilinear(img_low, u[win] / 4.0, vv[win] / 4.0)
                if np.any(gains[vi] != 1.0):
                    lb = np.clip(lb.astype(np.float32) * gains[vi] + 0.5, 0, 255).astype(np.uint8)
                Lt = Lb[ty:ty + h_, tx:tx + w_]
                Lt[rows, cols_] = lb
            touched = True
        used += touched
        if (vi + 1) % 20 == 0:
            log(f"  views {vi + 1}/{len(views)}")
    if blend:                                              # 색 = 1등 사진 색 − 1등 사진 저주파 + 섞인 저주파 (줄 단위)
        L4 = (accL / np.maximum(wL, 1e-300)[:, None]).reshape(H4, W4, 3).astype(np.float32)
        has4 = (wL > 0).reshape(H4, W4)
        L4[~has4] = 0
        for y0 in range(0, Hh, TILE):
            y1 = min(Hh, y0 + TILE)
            qa, qb = max(0, y0 // 4 - 1), min(H4, (y1 + 3) // 4 + 1)
            up = cv2.resize(L4[qa:qb], (W4 * 4, (qb - qa) * 4), interpolation=cv2.INTER_LINEAR)[y0 - qa * 4:y1 - qa * 4, :W]
            hu = cv2.resize(has4[qa:qb].astype(np.uint8), (W4 * 4, (qb - qa) * 4), interpolation=cv2.INTER_NEAREST)[y0 - qa * 4:y1 - qa * 4, :W] > 0
            c_ = col[y0:y1].astype(np.float32)
            out = c_ - Lb[y0:y1].astype(np.float32) + up
            col[y0:y1] = np.where(hu[..., None], np.clip(out + 0.5, 0, 255), c_).astype(np.uint8)
        del L4, up, hu, accL, wL
        Lt = None
        del Lb
    covered = (best[:] > 0) & valid
    log(f"colored {covered.sum() / max(1, valid.sum()) * 100:.1f}% of surface pixels using {used} views")
    # 작은 구멍 메우기: 칠해진 픽셀 가까이(4 px)의 빈 표면 픽셀만 주변 색으로 채운다
    near = cv2.dilate(covered.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
    holes = valid & ~covered & near
    if holes.any():
        filled = cv2.inpaint(cv2.cvtColor(np.array(col), cv2.COLOR_RGB2BGR), holes.astype(np.uint8), 3, cv2.INPAINT_TELEA)
        col[holes] = cv2.cvtColor(filled, cv2.COLOR_BGR2RGB)[holes]
        covered |= holes
        log(f"filled {holes.sum()} small-hole pixels")

    # ── 3) 저장 ──
    out_img = np.array(col)
    out_img[~covered] = 24
    cv2.imwrite(os.path.join(a.out, "ortho.jpg"), cv2.cvtColor(out_img, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, a.jpeg_quality])
    s = min(1.0, 2048.0 / max(W, Hh))
    ov = cv2.resize(out_img, (max(1, int(W * s)), max(1, int(Hh * s))), interpolation=cv2.INTER_AREA)
    al = cv2.resize(covered.astype(np.uint8) * 255, (ov.shape[1], ov.shape[0]), interpolation=cv2.INTER_AREA)
    cv2.imwrite(os.path.join(a.out, "ortho_overlay.png"), np.dstack([cv2.cvtColor(ov, cv2.COLOR_RGB2BGR), al]))

    meta = dict(surface=surface, source=source, views=len(views), views_used=used, gsd_m=gsd, width=W, height=Hh,
                extent_m=[round(ext_u, 4), round(ext_v, 4)], coverage_pct=round(float(covered.sum() / max(1, valid.sum()) * 100), 1),
                plane=plane_info, files=dict(image="ortho.jpg", overlay="ortho_overlay.png"))
    if surface == "floor" and a.lon is not None and a.lat is not None:
        from pyproj import CRS, Transformer
        tf = Transformer.from_crs("EPSG:4326", f"EPSG:{a.utm_epsg}", always_xy=True)
        E0, N0 = tf.transform(a.lon, a.lat)
        left, top_n = E0 + e0, N0 + n1
        with open(os.path.join(a.out, "ortho.jgw"), "w") as f:      # world file: 픽셀 중심 기준
            f.write(f"{gsd}\n0\n0\n{-gsd}\n{left + gsd / 2}\n{top_n - gsd / 2}\n")
        open(os.path.join(a.out, "ortho.prj"), "w").write(CRS.from_epsg(a.utm_epsg).to_wkt())
        inv = Transformer.from_crs(f"EPSG:{a.utm_epsg}", "EPSG:4326", always_xy=True)
        cx = lambda E_, N_: [round(t, 8) for t in inv.transform(E_, N_)]
        meta["georef"] = dict(crs=f"EPSG:{a.utm_epsg}", world_file="ortho.jgw",
                              corners_lonlat=dict(top_left=cx(left, top_n), top_right=cx(left + W * gsd, top_n),
                                                  bottom_right=cx(left + W * gsd, top_n - Hh * gsd), bottom_left=cx(left, top_n - Hh * gsd)))
    meta["seconds"] = round(time.time() - t0, 1)
    json.dump(meta, open(os.path.join(a.out, "ortho.json"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    # memmap 과 그 조각(bt, ct)이 하나라도 살아 있으면 Windows 에서 파일이 안 지워져 작업마다 ~150 MB 가 남는다
    del P, Nn, best, col
    bt = ct = Lt = None
    gc.collect()
    shutil.rmtree(tmp, ignore_errors=True)
    if os.path.exists(tmp):
        log(f"warning: temp folder not removed: {tmp}")
    log(f"done: {W}x{Hh}, {meta['coverage_pct']}% colored, {meta['seconds']}s")


if __name__ == "__main__":
    main()
