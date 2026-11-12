r"""
kgeoScan 집 평면도 자동 작성 (프로토타입 v0.1) — 실내 LiDAR 스캔 → 벽·문·창·치수·방 면적

  python -I worker/floorplan.py --mesh mesh.ply --out <dir> [--name 거실] [--slice 1.0,1.5] [--params '{"grid": 0.02}']
  python -I worker/floorplan.py --las scan.las --out <dir>          # LAS(UTM 52N, z 위)만 있을 때

  from floorplan import floorplan_files, floorplan, DEFAULTS       # worker/ 를 sys.path 에. numpy + cv2 + open3d (+ PIL 미리보기)
  res = floorplan_files(mesh="mesh.ply", out_dir="out", name="거실")

입력
  - mesh.ply: stray_to_mesh.py / process_scan.py 결과 (ARKit 월드, y 위, m, 중력 정렬). 면에서 1 cm 간격으로 고르게 다시 뽑고
    면 법선을 쓴다(줄인 메시의 정점은 평평한 곳에서 성기다). 법선이 방 가운데를 등지면 모두 뒤집는다.
  - scan.las: process_scan.py 가 메시 정점을 UTM 으로 옮긴 것(z 위). 법선은 이웃 점으로 추정하고 방 가운데를 향하게 맞춘다.
    점마다 넓이 가중치(k 번째 이웃 거리)로 밀도 차이를 보정한다.

평면 좌표
  메시: X = x, Y = −z (위에서 내려다본 오른손 좌표). 그다음 벽이 축과 나란하도록 θ 만큼 돌린 (u, v) 가 평면도 좌표다.
  u = X cosθ + Y sinθ,  v = −X sinθ + Y cosθ.  floorplan.json 의 frame.plan_to_input 으로 ARKit (x, z) 로 되돌린다(y = 바닥).

방법
  1) 바닥·천장: 위를 보는 면의 높이 분포(1 cm)에서 넓은 봉우리 중 가장 낮은 것 = 바닥, 아래를 보는 면 중 가장 높은 것 = 천장.
  2) 주 방향: 수직 면 법선 각도의 4배 각 평균 → 벽이 축과 나란하게 돌린다(한국 아파트는 거의 직교. 사선 벽은 다각형에 그대로 남는다).
  3) 실내 증거: 바닥·천장·가구 윗면(0.25–1.3 m)이 보인 2 cm 칸. 닫기 + 3 m² 보다 작은 구멍 채움(가구 밑).
  4) 벽: 바닥 위 1.0–1.5 m 수평 단면의 수직 면 점을 법선 방향(±u, ±v)별로 위치 히스토그램(1 cm) → 평면 후보 → 단면을 따라 이어진 구간.
     벽 뒤(법선 반대편 5–25 cm)에 실내 증거가 거의 없어야 벽이다(가구 앞면 제외). 벽 위치 = 실내 쪽 면 = 안목.
  5) 방: 실내 증거에서 벽 바로 뒤 얇은 띠(6 cm)를 지운 연결 성분. 같은 벽 평면의 구간 사이 틈은 1.3 m 이하이거나
     위(인방)·아래(창턱)에 벽이 있으면 막는다 → 문·창에서 방이 나뉜다. 큰 방은 거리 변환으로 좁은 목(< 0.9 m)에서 한 번 더 나눈다.
  6) 다각형: 방 윤곽 → approxPolyDP(6 cm) → 변을 u/v 축 방향으로 정리(짧은 턱 제거) → 변마다 가까운 벽 평면(바깥쪽으로 −10…+30 cm,
     같은 방향, 겹침 30 % 이상) 중 가장 바깥 것에 붙인다. 붙지 않은 변 = 스캔 경계(점선, 면적은 최소값).
  7) 문·창: 벽 변을 따라 벽면 띠(±5 cm)의 높이별 점유(2 cm × 5 cm)를 보고 가운데 높이(0.9–1.8 m)가 빈 구간을 찾는다.
     바닥까지 비면 문(폭 ≤ 1.3 m)/개구부, 아래가 막히면 창(창턱·창 머리 높이). 벽 너머가 보이거나(투과) 양옆이 벽이어야 받아들인다.
  8) 출력: floorplan.json · floorplan.svg (한글) · floorplan.dxf (R12, ASCII 글자) · floorplan.png (미리보기) · floorplan_debug.png

한계(프로토타입)
  - 닫힌 문은 벽처럼 보여 놓칠 수 있다(문틀 턱만 남음). 커튼으로 가린 창은 벽으로 본다. 붙박이장은 벽으로 본다.
  - 면적은 실내 쪽 벽면을 이은 안목 면적이다. 공동주택 전용면적도 안목치수 기준이지만, 여기 값은 참고용이고 공부(건축물대장)가 우선이다.
  - 벽 두께는 한쪽만 보이므로 알 수 없다(그림은 0.12 m 로 가정해 그린다).

로그는 ASCII 만 쓴다(cp949 콘솔). JSON·SVG 는 UTF-8.
"""
import argparse
import json
import math
import os
import sys
import time

import cv2
import numpy as np

VERSION = "floorplan-0.1"

DEFAULTS = dict(
    sample_m=0.01,          # 메시 면 재표본 간격 (m)
    seed=0,
    max_points=3_000_000,
    grid=0.02,              # 평면 격자 (m)
    slice_lo=1.0,           # 벽 단면 (바닥 위 m)
    slice_hi=1.5,
    up_cos=0.85,            # 수평면: |n_up| > up_cos
    wall_sin=0.30,          # 수직면: |n_up| < wall_sin
    axis_tol_deg=15.0,      # 벽 법선이 주 방향에서 벗어나도 되는 각
    floor_min_m2=0.25,
    ceil_min_m2=0.15,
    ceil_range=(1.9, 4.0),
    plane_bin=0.01,
    plane_min_m2=0.04,      # 단면 띠(0.5 m) 안 벽 후보 최소 넓이 → 길이 약 8 cm
    plane_halfwidth=0.03,
    plane_nms=0.04,
    seg_gap=0.16,           # 같은 평면 구간을 잇는 틈(가림)
    wall_min_len=0.30,
    behind_lo=0.05, behind_hi=0.25,
    behind_max=0.60,        # 벽 뒤에 실내 증거가 있는 칸 비율 상한(넘으면 가구 앞면)
    aux_bands=((1.5, 2.2), (0.3, 1.0), (2.2, 9.9)),   # 주 단면에서 벽이 가려졌을 때 보충할 높이 띠(마지막 = 창·문 위 벽, 천장 아래까지)
    fill_depth=1.0,         # 벽면~실내 증거 사이 가려진 띠를 채우는 최대 깊이
    barrier=0.06,
    door_close_max=1.3,     # 같은 벽 평면의 틈을 막는 최대 폭(문)
    room_min_m2=1.0,
    hole_fill_m2=3.0,
    neck_m=0.90,            # 거리 변환 방 나누기: 이보다 좁은 목에서 나눈다
    split_min_m2=2.5,
    partial_ratio=0.25,     # 벽 확인 비율이 이보다 낮은 두 번째 이후 공간 = 문 너머로 일부만 보인 옆 공간(합계에서 뺀다)
    approx_eps=0.06,
    jog_max=0.12,
    snap_out=0.30, snap_in=0.10,
    snap_overlap=0.30,
    band=0.05,              # 문·창: 벽면 띠 반폭
    open_min=0.45, open_max=4.0,
    door_max=1.3,
    wall_draw_t=0.12,       # 그림용 벽 두께(가정)
    dim_offset=0.40,
)

PY_PER_M2 = 1.0 / 3.305785     # 1평 = 400/121 m²


def _log_ascii(log):
    def f(msg):
        try:
            log(str(msg).encode("ascii", "replace").decode())
        except Exception:
            pass
    return f


# ═══════════════════════════════════════════ 1) 입력 ═══════════════════════════════════════════

def load_mesh_points(path, prm, log):
    import open3d as o3d
    m = o3d.io.read_triangle_mesh(path)
    if len(m.triangles) == 0:
        raise ValueError("mesh has no triangles: " + path)
    m.compute_triangle_normals()
    area = float(m.get_surface_area())
    n = int(np.clip(area / prm["sample_m"] ** 2, 200_000, prm["max_points"]))
    try:
        o3d.utility.random.seed(int(prm.get("seed", 0)))      # 같은 입력 → 같은 평면도
    except Exception:
        pass
    pc = m.sample_points_uniformly(number_of_points=n, use_triangle_normal=True)
    P = np.asarray(pc.points)
    N = np.asarray(pc.normals)
    w = np.full(len(P), area / n)
    # ARKit (x 오른쪽, y 위, z 뒤) → 평면 (X = x, Y = −z, H = y)
    Q = np.column_stack([P[:, 0], -P[:, 2], P[:, 1]])
    NQ = np.column_stack([N[:, 0], -N[:, 2], N[:, 1]])
    log(f"[load] mesh {os.path.basename(path)}: {len(m.triangles)} tris, area {area:.1f} m2 -> {n} samples")
    return Q, NQ, w, dict(kind="mesh", path=os.path.abspath(path), triangles=len(m.triangles),
                          surface_m2=round(area, 2), samples=n, offset=[0.0, 0.0, 0.0], up="y")


def load_las_points(path, prm, log):
    import laspy
    import open3d as o3d
    las = laspy.read(path)
    P = np.column_stack([np.asarray(las.x), np.asarray(las.y), np.asarray(las.z)]).astype(np.float64)
    off = np.round(np.median(P, 0), 0)
    Q = P - off
    pc = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(Q))
    pc.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=0.06, max_nn=30))
    ctr = np.median(Q, 0)
    ctr[2] = np.percentile(Q[:, 2], 5) + 1.3
    pc.orient_normals_towards_camera_location(ctr)
    N = np.asarray(pc.normals)
    kd = o3d.geometry.KDTreeFlann(pc)
    k = 8
    r2 = np.empty(len(Q))
    step = max(1, len(Q) // 200_000)
    idx = np.arange(0, len(Q), step)
    for i in idx:
        _, _, d2 = kd.search_knn_vector_3d(Q[i], k + 1)
        r2[i] = d2[-1]
    if step > 1:     # 듬성듬성 계산한 값을 이웃 순서대로 채운다(가중치는 대략이면 된다)
        r2 = np.interp(np.arange(len(Q)), idx, r2[idx])
    w = np.pi * r2 / k
    w = np.clip(w, 0, np.percentile(w, 99))
    log(f"[load] las {os.path.basename(path)}: {len(Q)} points (normals estimated)")
    return Q, N, w, dict(kind="las", path=os.path.abspath(path), samples=len(Q), offset=off.tolist(), up="z")


# ═══════════════════════════════════════════ 2) 바닥·천장·방향 ═══════════════════════════════════════════

def _peaks(hist, centers, min_mass, nms_bins=5):
    hs = np.convolve(hist, np.ones(5), "same")
    out = []
    taken = np.zeros(len(hs), bool)
    for i in np.argsort(-hs):
        if hs[i] < min_mass:
            break
        if taken[max(0, i - nms_bins): i + nms_bins + 1].any():
            continue
        taken[i] = True
        out.append((float(centers[i]), float(hs[i])))
    return out


def find_levels(Q, NQ, w, prm, log):
    H, nh = Q[:, 2], NQ[:, 2]
    # 법선 방향 확인: 대부분의 면이 방 가운데를 향해야 한다(스캐너는 방 안에 있었다)
    ctr = np.median(Q, 0)
    s = np.sum(w * np.einsum("ij,ij->i", NQ, ctr - Q))
    flipped = bool(s < 0)
    if flipped:
        NQ *= -1.0
        nh = NQ[:, 2]
        log("[levels] normals face away from the room centre -> flipped")
    up, dn = nh > prm["up_cos"], nh < -prm["up_cos"]
    lo, hi = np.percentile(H, [0.05, 99.95])
    edges = np.arange(lo - 0.05, hi + 0.06, 0.01)
    cen = 0.5 * (edges[1:] + edges[:-1])
    hu, _ = np.histogram(H[up], edges, weights=w[up])
    hd, _ = np.histogram(H[dn], edges, weights=w[dn])
    # 바닥 = 점 높이 중앙값보다 아래의 위를 보는 넓은 면 중 가장 낮은 것.
    # (자세가 흐른 스캔은 천장이 두 겹으로 생겨 위층 면이 위를 본다 — 그것을 바닥으로 잡지 않게)
    hmed = float(np.median(H))
    pk = [(h, m) for h, m in _peaks(hu, cen, prm["floor_min_m2"]) if h < hmed]
    if not pk:
        raise ValueError("no floor found (no large up-facing surface below the median height)")
    big = max(m for _, m in pk)
    floor_h = min(h for h, m in pk if m >= 0.15 * big)
    sel = up & (np.abs(H - floor_h) < 0.03)
    floor_h = float(np.median(H[sel]))
    A = np.column_stack([Q[sel, 0], Q[sel, 1], np.ones(sel.sum())])
    coef, *_ = np.linalg.lstsq(A, H[sel], rcond=None)
    tilt = float(np.degrees(np.arctan(np.hypot(coef[0], coef[1]))))
    floor_m2 = float(w[sel].sum())
    # 천장: 아래를 보는 넓은 면의 높이 단(우물천장·우물 둘레·내린 천장). 대표 천장고 = 넓이가 최대의 절반 이상인 단 중 가장 낮은 것
    ceil_h, ceil_m2, levels = None, 0.0, []
    hor = up | dn               # 천장 단은 법선 부호를 보지 않는다(두 겹 천장의 윗면이 위를 본다)
    hd, _ = np.histogram(H[hor], edges, weights=w[hor])
    pkd = [(h, m) for h, m in _peaks(hd, cen, prm["ceil_min_m2"])
           if prm["ceil_range"][0] <= h - floor_h <= prm["ceil_range"][1]]
    if pkd:
        bigd = max(m for _, m in pkd)
        for h0, m0 in sorted(pkd):
            if m0 < 0.10 * bigd:
                continue
            seld = hor & (np.abs(H - h0) < 0.03)
            levels.append(dict(h=float(np.median(H[seld])), m2=float(w[seld].sum())))
        main = min((lv_ for lv_ in levels if lv_["m2"] >= 0.5 * max(x["m2"] for x in levels)), key=lambda x: x["h"])
        ceil_h, ceil_m2 = main["h"], sum(x["m2"] for x in levels)
    lv = dict(floor_h=floor_h, ceiling_h=ceil_h,
              ceiling_height_m=(round(ceil_h - floor_h, 3) if ceil_h is not None else None),
              ceiling_levels_m=[dict(height_m=round(x["h"] - floor_h, 3), seen_m2=round(x["m2"], 2)) for x in levels],
              ceiling_levels_h=[x["h"] for x in levels],
              floor_tilt_deg=round(tilt, 2), floor_seen_m2=round(floor_m2, 2), ceiling_seen_m2=round(ceil_m2, 2),
              normals_flipped=flipped)
    log(f"[levels] floor {floor_h:.3f} (seen {floor_m2:.1f} m2, tilt {tilt:.2f} deg)  ceiling "
        + (f"{ceil_h:.3f} -> height {ceil_h - floor_h:.3f} m; levels "
           + ", ".join(f"{x['h'] - floor_h:.2f} m ({x['m2']:.1f} m2)" for x in levels) if ceil_h is not None else "not found"))
    return lv, NQ


def dominant_angle(NQ, h, w, top, prm):
    vert = (np.abs(NQ[:, 2]) < prm["wall_sin"]) & (h > 0.2) & (h < top - 0.2)
    phi = np.arctan2(NQ[vert, 1], NQ[vert, 0])
    ww = w[vert] * np.hypot(NQ[vert, 0], NQ[vert, 1])
    z = np.sum(ww * np.exp(4j * phi))
    th = np.angle(z) / 4.0
    res = (phi - th + np.pi / 4) % (np.pi / 2) - np.pi / 4
    k = np.abs(res) < np.radians(5)
    if k.sum() > 100:
        th += float(np.sum(ww[k] * res[k]) / np.sum(ww[k]))
    res = (phi - th + np.pi / 4) % (np.pi / 2) - np.pi / 4
    k = np.abs(res) < np.radians(prm["axis_tol_deg"])
    manh = float(np.sum(ww[k]) / max(np.sum(ww), 1e-9))
    spread = float(np.degrees(np.sqrt(np.sum(ww[k] * res[k] ** 2) / max(np.sum(ww[k]), 1e-9))))
    return float(th), manh, spread


# ═══════════════════════════════════════════ 3) 격자 ═══════════════════════════════════════════

class Grid:
    def __init__(self, umin, vmin, umax, vmax, res):
        self.res = res
        self.u0, self.v0 = umin, vmin
        self.W = int(math.ceil((umax - umin) / res)) + 1
        self.H = int(math.ceil((vmax - vmin) / res)) + 1

    def ij(self, u, v):
        iu = np.clip(((u - self.u0) / self.res).astype(int), 0, self.W - 1)
        iv = np.clip(((v - self.v0) / self.res).astype(int), 0, self.H - 1)
        return iv, iu

    def raster(self, u, v, w=None):
        img = np.zeros((self.H, self.W), np.float64)
        iv, iu = self.ij(u, v)
        np.add.at(img, (iv, iu), 1.0 if w is None else w)
        return img

    def uv(self, iv, iu):
        return self.u0 + (np.asarray(iu) + 0.5) * self.res, self.v0 + (np.asarray(iv) + 0.5) * self.res

    def coords(self):
        uu = self.u0 + (np.arange(self.W) + 0.5) * self.res
        vv = self.v0 + (np.arange(self.H) + 0.5) * self.res
        return np.meshgrid(uu, vv)


def _disk(r_px):
    r = max(1, int(round(r_px)))
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))


def _fill_small_holes(mask, max_px):
    inv = (~mask).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(inv, connectivity=4)
    out = mask.copy()
    H, W = mask.shape
    for k in range(1, n):
        x, y, w_, h_, a = st[k]
        touches = x == 0 or y == 0 or x + w_ >= W or y + h_ >= H
        if not touches and a <= max_px:
            out[lab == k] = True
    return out


def _remove_small(mask, min_px):
    n, lab, st, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    keep = np.zeros(n, bool)
    keep[1:] = st[1:, 4] >= min_px
    return keep[lab]


def interior_evidence(U, V, h, nh, w, g, lv, prm):
    hor = np.abs(nh) > prm["up_cos"]           # 수평면은 부호를 보지 않는다(줄인 메시·두 겹 면의 뒤집힌 법선)
    m = hor & (np.abs(h) < 0.04)
    m |= hor & (h > 0.25) & (h < 1.3)          # 가구 윗면·아랫면: 방 안
    for ch in lv.get("ceiling_levels_h") or []:
        m |= hor & (np.abs(h - (ch - lv["floor_h"])) < 0.06)
    occ = g.raster(U[m], V[m], w[m]) > 0.25 * g.res ** 2
    E = cv2.morphologyEx(occ.astype(np.uint8), cv2.MORPH_CLOSE, _disk(0.10 / g.res)) > 0
    E = _fill_small_holes(E, prm["hole_fill_m2"] / g.res ** 2)
    E = cv2.morphologyEx(E.astype(np.uint8), cv2.MORPH_OPEN, _disk(0.03 / g.res)) > 0
    E = _remove_small(E, 0.3 / g.res ** 2)
    return E


def fill_to_walls(E, walls, g, prm):
    """벽면과 그 앞 실내 증거 사이 빈 띠(벽에 붙은 가구로 바닥·천장이 가려진 곳)를 채운다.
    벽면에서 법선 쪽으로 fill_depth 안에 증거가 있을 때만, 벽면부터 처음 만나는 증거까지."""
    E = E.copy()
    dmax = int(round(prm["fill_depth"] / g.res))
    for wl in walls:
        if wl["fam"] == 0:           # u = c 평면, 줄(iv) 마다 u 방향으로
            ic = int(round((wl["c"] - g.u0) / g.res))
            r0, r1 = (int((wl["b0"] - g.v0) / g.res), int((wl["b1"] - g.v0) / g.res) + 1)
            r0, r1 = max(r0, 0), min(r1, g.H)
            for iv in range(r0, r1):
                line = E[iv, :]
                rng = range(ic, min(g.W, ic + dmax)) if wl["s"] > 0 else range(ic, max(-1, ic - dmax), -1)
                rng = list(rng)
                hit = next((k for k, j in enumerate(rng) if 0 <= j < g.W and line[j]), None)
                if hit is not None and hit > 0:
                    for j in rng[:hit]:
                        if 0 <= j < g.W:
                            E[iv, j] = True
        else:                        # v = c 평면, 열(iu) 마다 v 방향으로
            ic = int(round((wl["c"] - g.v0) / g.res))
            c0, c1 = (int((wl["b0"] - g.u0) / g.res), int((wl["b1"] - g.u0) / g.res) + 1)
            c0, c1 = max(c0, 0), min(c1, g.W)
            for iu in range(c0, c1):
                col = E[:, iu]
                rng = list(range(ic, min(g.H, ic + dmax)) if wl["s"] > 0 else range(ic, max(-1, ic - dmax), -1))
                hit = next((k for k, j in enumerate(rng) if 0 <= j < g.H and col[j]), None)
                if hit is not None and hit > 0:
                    for j in rng[:hit]:
                        if 0 <= j < g.H:
                            E[j, iu] = True
    return E


# ═══════════════════════════════════════════ 4) 벽 평면 ═══════════════════════════════════════════

def _runs(occ, gap_bins):
    """True 구간 [i0, i1) 목록, gap_bins 이하의 틈은 잇는다."""
    idx = np.flatnonzero(occ)
    if len(idx) == 0:
        return []
    out = []
    s = p = idx[0]
    for i in idx[1:]:
        if i - p - 1 > gap_bins:
            out.append((s, p + 1))
            s = i
        p = i
    out.append((s, p + 1))
    return out


def find_wall_planes(U, V, h, NU, NV, nh, w, prm, log, top=2.4):
    """주 단면(1.0–1.5 m)에서 벽 평면 구간을 찾고, 그 높이가 가려진 곳(주방 상부장·가전·가구)은 보조 띠로 보충한다."""
    bands = [(prm["slice_lo"], prm["slice_hi"])] + [tuple(b) for b in prm["aux_bands"]]
    segs = []
    for bi, (lo, hi) in enumerate(bands):
        hi = min(hi, top - 0.08)
        if hi - lo < 0.2:
            continue
        for sg in _planes_in_band(U, V, h, NU, NV, nh, w, prm, lo, hi):
            sg["band"] = bi
            segs.append(sg)
    segs = _merge_segments(segs, prm)
    for sg in segs:
        sg["top_only"] = all(bands[i][0] >= 2.0 for i in sg["bands"])
    nb = sum(1 for sg in segs if 0 in sg["bands"])
    log(f"[walls] {len(segs)} vertical plane segments ({nb} in main slice {prm['slice_lo']:.2f}-{prm['slice_hi']:.2f} m, "
        f"{len(segs) - nb} only in aux bands)")
    return segs


def _merge_segments(segs, prm):
    out = []
    for sg in sorted(segs, key=lambda x: (x["band"], -x["mass"])):
        hit = None
        for o in out:
            if o["fam"] == sg["fam"] and o["s"] == sg["s"] and abs(o["c"] - sg["c"]) < 0.04                     and min(o["b1"], sg["b1"]) - max(o["b0"], sg["b0"]) > -prm["seg_gap"]:
                hit = o
                break
        if hit is None:
            sg = dict(sg)
            sg["bands"] = [sg.pop("band")]
            out.append(sg)
        else:
            if 0 not in hit["bands"]:      # 주 단면 값이 있으면 위치는 그것을 쓴다
                tot = hit["mass"] + sg["mass"]
                hit["c"] = (hit["c"] * hit["mass"] + sg["c"] * sg["mass"]) / tot
            hit["b0"], hit["b1"] = min(hit["b0"], sg["b0"]), max(hit["b1"], sg["b1"])
            hit["length"] = hit["b1"] - hit["b0"]
            hit["mass"] += sg["mass"]
            if sg["band"] not in hit["bands"]:
                hit["bands"].append(sg["band"])
    return out


def _planes_in_band(U, V, h, NU, NV, nh, w, prm, band_lo, band_hi):
    sl = (np.abs(nh) < prm["wall_sin"]) & (h >= band_lo) & (h <= band_hi)
    ct = math.cos(math.radians(prm["axis_tol_deg"]))
    pb, hw = prm["plane_bin"], prm["plane_halfwidth"]
    bb_bin = 0.02
    full = bb_bin * (band_hi - band_lo)
    min_mass = prm["plane_min_m2"] * (band_hi - band_lo) / 0.5
    segs = []
    for fam in (0, 1):
        A, B, NA = (U, V, NU) if fam == 0 else (V, U, NV)
        for s in (1, -1):
            m = sl & (s * NA > ct)
            if m.sum() < 50:
                continue
            am, bm, wm = A[m], B[m], w[m]
            lo = am.min()
            ib = ((am - lo) / pb).astype(int)
            hist = np.bincount(ib, weights=wm)
            cen = lo + (np.arange(len(hist)) + 0.5) * pb
            for c0, mass in _peaks(hist, cen, min_mass, nms_bins=int(round(prm["plane_nms"] / pb))):
                inb = np.abs(am - c0) < hw
                if inb.sum() < 30:
                    continue
                c = float(np.median(am[inb]))
                inb = np.abs(am - c) < hw
                b, wb = bm[inb], wm[inb]
                b0 = b.min()
                occ_mass = np.bincount(((b - b0) / bb_bin).astype(int), weights=wb)
                occ = occ_mass > 0.15 * full
                for i0, i1 in _runs(occ, int(round(prm["seg_gap"] / bb_bin))):
                    L = (i1 - i0) * bb_bin
                    if L < prm["wall_min_len"]:
                        continue
                    lo_b, hi_b = b0 + i0 * bb_bin, b0 + i1 * bb_bin
                    k = (b >= lo_b) & (b < hi_b)
                    a_k = am[inb][k]
                    rms = float(np.sqrt(np.average((a_k - c) ** 2, weights=wb[k])))
                    segs.append(dict(fam=fam, s=s, c=c, b0=float(lo_b), b1=float(hi_b), length=float(L),
                                     mass=float(wb[k].sum()), rms_mm=round(rms * 1000, 1),
                                     fill=float(occ[i0:i1].mean())))
    return segs


def _side_frac(E, g, seg, d0, d1, per_bin=False):
    """벽면에서 법선 쪽으로 d0..d1 (음수 = 뒤) 띠의 실내 증거 비율.
    per_bin: 벽을 따라 칸마다 띠의 증거 비율이 0.5 이상인 칸의 비율(문 옆 짧은 벽에서 비스듬히 보인 옆방 바닥에 덜 흔들린다)."""
    UU, VV = g.coords()
    A, B = (UU, VV) if seg["fam"] == 0 else (VV, UU)
    d = seg["s"] * (A - seg["c"])
    k = (d >= d0) & (d <= d1) & (B >= seg["b0"]) & (B <= seg["b1"])
    if not k.any():
        return 0.0
    if not per_bin:
        return float(E[k].mean())
    ax = 0 if seg["fam"] == 0 else 1       # fam 0: 벽을 따라 = v = 줄
    num = (E & k).sum(axis=1 - ax)
    den = k.sum(axis=1 - ax)
    ok = den > 0
    return float(np.mean(num[ok] / den[ok] >= 0.5))


def classify_walls(segs, E, g, prm, log):
    walls = []
    for sg in segs:
        sg["behind"] = _side_frac(E, g, sg, -prm["behind_hi"], -prm["behind_lo"], per_bin=True)
        sg["front"] = _side_frac(E, g, sg, prm["behind_lo"], 0.40)
        sg["is_wall"] = bool(sg["behind"] <= prm["behind_max"])
        if sg["is_wall"]:
            walls.append(sg)
    for i, wl in enumerate(walls):
        wl["id"] = f"W{i + 1}"
    log(f"[walls] {len(walls)} wall segments kept (behind-evidence share <= {prm['behind_max']}), {len(segs) - len(walls)} rejected as furniture faces")
    return walls


def _band_profile(U, V, h, wl, b0, b1, prm, top):
    """벽면 띠(±band)의 (b 2 cm × h 5 cm) 점유와 벽 너머(투과) 점 개수."""
    A, B = (U, V) if wl["fam"] == 0 else (V, U)
    d = wl["s"] * (A - wl["c"])
    kb = (B >= b0) & (B < b1)
    nb = max(1, int(math.ceil((b1 - b0) / 0.02)))
    nh_ = max(1, int(math.ceil(top / 0.05)))
    k = kb & (np.abs(d) < prm["band"]) & (h > 0.0) & (h < top)
    occ = np.zeros((nh_, nb), bool)
    ib = np.clip(((B[k] - b0) / 0.02).astype(int), 0, nb - 1)
    ih = np.clip((h[k] / 0.05).astype(int), 0, nh_ - 1)
    cnt = np.zeros((nh_, nb))
    np.add.at(cnt, (ih, ib), 1)
    occ = cnt >= 3
    kt = kb & (d < -0.12) & (h > -0.05) & (h < 2.2)
    beyond = np.bincount(np.clip(((B[kt] - b0) / 0.02).astype(int), 0, nb - 1), minlength=nb)
    kf = kb & (d > 0.10) & (d < 1.0) & (h > 0.9) & (h < 1.8)
    front = np.bincount(np.clip(((B[kf] - b0) / 0.02).astype(int), 0, nb - 1), minlength=nb)
    return occ, beyond, front


def close_gaps(walls, U, V, h, prm, top):
    """같은 평면(같은 fam·s·c)의 이웃 구간 사이 틈: 문 폭 이하이거나 인방·창턱이 보이면 막는다."""
    closes = []
    groups = {}
    for wl in walls:
        key = (wl["fam"], wl["s"], round(wl["c"] / 0.03))
        groups.setdefault(key, []).append(wl)
    for key, L in groups.items():
        L.sort(key=lambda x: x["b0"])
        for a, b in zip(L[:-1], L[1:]):
            gap = b["b0"] - a["b1"]
            if gap <= 0:
                continue
            ok = gap <= prm["door_close_max"]
            if not ok and gap <= prm["open_max"]:
                occ = _band_profile(U, V, h, a, a["b1"], b["b0"], prm, top)[0]
                hb = np.arange(occ.shape[0]) * 0.05
                sill = occ[(hb > 0.1) & (hb < 0.8)].mean(0) > 0.4
                head = occ[(hb > 2.0)].mean(0) > 0.4 if (hb > 2.0).any() else np.zeros(occ.shape[1], bool)
                ok = float((sill | head).mean()) > 0.5
            if ok:
                closes.append(dict(fam=a["fam"], s=a["s"], c=0.5 * (a["c"] + b["c"]), b0=a["b1"], b1=b["b0"]))
    return closes


def barrier_mask(walls, closes, g, prm):
    UU, VV = g.coords()
    bar = np.zeros((g.H, g.W), bool)
    for wl in list(walls) + list(closes):
        A, B = (UU, VV) if wl["fam"] == 0 else (VV, UU)
        d = wl["s"] * (A - wl["c"])
        ext = 0.10
        bar |= (d <= 0.0) & (d >= -prm["barrier"]) & (B >= wl["b0"] - ext) & (B <= wl["b1"] + ext)
    return bar


# ═══════════════════════════════════════════ 5) 방 나누기 ═══════════════════════════════════════════

def split_rooms(E, bar, g, prm, log):
    # 벽(장벽)과 실내 증거로 둘러싸인 구멍(바닥·천장이 함께 가려진 곳: 키 큰 가구, 사람, 덜 찍힌 곳)은 방에 넣는다
    E = _fill_small_holes(E | bar, prm["hole_fill_m2"] / g.res ** 2) & ~bar | (E & ~bar)
    free = E & ~bar
    free = cv2.morphologyEx(free.astype(np.uint8), cv2.MORPH_OPEN, _disk(0.02 / g.res)) > 0
    n, lab = cv2.connectedComponents(free.astype(np.uint8), connectivity=4)
    rooms = []
    min_px = prm["room_min_m2"] / g.res ** 2
    for k in range(1, n):
        comp = lab == k
        if comp.sum() < min_px:
            continue
        parts = _neck_split(comp, g, prm)
        rooms.extend(p for p in parts if p.sum() >= min_px)
    rooms.sort(key=lambda m: -m.sum())
    log(f"[rooms] {len(rooms)} spaces >= {prm['room_min_m2']} m2")
    return rooms


def _neck_split(comp, g, prm):
    dt = cv2.distanceTransform(comp.astype(np.uint8), cv2.DIST_L2, 5) * g.res
    core = dt > prm["neck_m"] / 2
    n, lab, st, _ = cv2.connectedComponentsWithStats(core.astype(np.uint8), connectivity=8)
    seeds = [k for k in range(1, n) if st[k, 4] * g.res ** 2 >= 0.5]
    if len(seeds) < 2:
        return [comp]
    L = np.zeros(comp.shape, np.int32)
    for i, k in enumerate(seeds):
        L[lab == k] = i + 1
    ker = np.ones((3, 3), np.uint8)
    for _ in range(int(2.0 / g.res)):
        grown = L.copy()
        for i in range(1, len(seeds) + 1):
            d = cv2.dilate((L == i).astype(np.uint8), ker) > 0
            grown[d & comp & (grown == 0)] = i
        if np.array_equal(grown, L):
            break
        L = grown
    parts = [L == i for i in range(1, len(seeds) + 1)]
    rest = comp & (L == 0)
    if rest.any():
        parts[0] = parts[0] | rest
    big = [p for p in parts if p.sum() * g.res ** 2 >= prm["split_min_m2"]]
    if len(big) < 2:
        return [comp]
    small = [p for p in parts if p.sum() * g.res ** 2 < prm["split_min_m2"]]
    for p in small:              # 작은 조각은 가장 길게 닿은 큰 조각에 붙인다
        d = cv2.dilate(p.astype(np.uint8), ker) > 0
        j = int(np.argmax([np.sum(d & q) for q in big]))
        big[j] = big[j] | p
    return big


# ═══════════════════════════════════════════ 6) 직교 다각형 ═══════════════════════════════════════════

def _poly_area(P):
    x, y = P[:, 0], P[:, 1]
    return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))


def _line_isect(p, d, q, e):
    M = np.array([[d[0], -e[0]], [d[1], -e[1]]])
    if abs(np.linalg.det(M)) < 1e-9:
        return None
    t = np.linalg.solve(M, q - p)
    return p + t[0] * d


def room_polygon(mask, g, walls, prm):
    cs, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(cs, key=cv2.contourArea)
    ap = cv2.approxPolyDP(c, prm["approx_eps"] / g.res, True)[:, 0, :]
    # 격자 칸 경계 쪽으로: 윤곽은 칸 중심이므로 바깥으로 반 칸
    P = np.column_stack(g.uv(ap[:, 1], ap[:, 0]))
    if _poly_area(P) < 0:
        P = P[::-1]
    cpts = np.column_stack(g.uv(c[:, 0, 1], c[:, 0, 0]))
    tan = math.tan(math.radians(25))
    edges = []
    n = len(P)
    for i in range(n):
        a, b = P[i], P[(i + 1) % n]
        d = b - a
        if abs(d[1]) <= tan * abs(d[0]):
            o = "H"     # u 방향 변 → v = const (fam 1 평면)
        elif abs(d[0]) <= tan * abs(d[1]):
            o = "V"     # v 방향 변 → u = const (fam 0 평면)
        else:
            o = "D"
        edges.append(dict(o=o, a=a.copy(), b=b.copy()))
    edges = _merge_edges(edges, prm)
    # 변의 위치(직교 좌표) = 윤곽 점의 중앙값
    for e in edges:
        if e["o"] == "D":
            continue
        k = 1 if e["o"] == "H" else 0
        j = 1 - k
        lo, hi = sorted([e["a"][j], e["b"][j]])
        sel = (cpts[:, j] >= lo) & (cpts[:, j] <= hi) & (np.abs(cpts[:, k] - 0.5 * (e["a"][k] + e["b"][k])) < 0.12)
        pos = float(np.median(cpts[sel, k])) if sel.sum() >= 3 else 0.5 * (e["a"][k] + e["b"][k])
        # 바깥 방향(반시계 다각형의 오른쪽)
        d = e["b"] - e["a"]
        out = np.array([d[1], -d[0]])
        e["out"] = int(np.sign(out[k])) or 1
        e["pos"] = pos + e["out"] * 0.5 * g.res
        e["lo"], e["hi"] = lo, hi
    # 벽 평면에 붙이기
    for e in edges:
        e["wall"] = None
        if e["o"] == "D":
            continue
        fam = 1 if e["o"] == "H" else 0
        need_s = -e["out"]
        best = None
        for wl in walls:
            if wl["fam"] != fam or wl["s"] != need_s:
                continue
            dd = e["out"] * (wl["c"] - e["pos"])
            if dd < -prm["snap_in"] or dd > prm["snap_out"]:
                continue
            ov = min(e["hi"], wl["b1"]) - max(e["lo"], wl["b0"])
            L = e["hi"] - e["lo"]
            if ov < min(prm["snap_overlap"] * L, 0.3) and ov < 0.5 * (wl["b1"] - wl["b0"]):
                continue
            # 주 단면(1.0–1.5 m)에서 찾은 평면을 먼저: 천장 아래 띠의 평면은 커튼박스·보·몰딩으로 벽보다 바깥에 있을 수 있다
            score = (1 if 0 in wl.get("bands", [0]) else 0, 0 if wl.get("top_only") else 1, dd + 0.02 * min(ov, 2.0))
            if best is None or score > best[0]:
                best = (score, wl)
        if best is not None:
            e["pos"] = best[1]["c"]
            e["wall"] = best[1]["id"]
            e["evidence"] = ("main_slice" if 0 in best[1].get("bands", [0]) else
                             ("top_band_only" if best[1].get("top_only") else "other_band"))
    # 꼭짓점 다시 만들기 (이웃 변의 교점)
    for _ in range(3):
        verts = []
        m = len(edges)
        for i in range(m):
            e0, e1 = edges[i - 1], edges[i]
            verts.append(_corner(e0, e1))
        for i in range(len(edges)):
            edges[i]["a"], edges[i]["b"] = verts[i], verts[(i + 1) % len(edges)]
        keep = [e for e in edges if np.linalg.norm(e["b"] - e["a"]) > 0.03]
        if len(keep) == len(edges):
            break
        edges = _merge_edges(keep, prm, recompute=True)
    V = np.array([e["a"] for e in edges])
    return V, edges


def _corner(e0, e1):
    def line(e):
        if e["o"] == "H":
            return np.array([0.0, e["pos"]]), np.array([1.0, 0.0])
        if e["o"] == "V":
            return np.array([e["pos"], 0.0]), np.array([0.0, 1.0])
        return e["a"], (e["b"] - e["a"]) / max(np.linalg.norm(e["b"] - e["a"]), 1e-9)
    p, d = line(e0)
    q, f = line(e1)
    x = _line_isect(p, d, q, f)
    if x is None:          # 나란한 두 변: 앞 변 끝에서 수직으로 잇는다
        return e1["a"].copy()
    return x


def _merge_edges(edges, prm, recompute=False):
    changed = True
    while changed and len(edges) > 3:
        changed = False
        # 같은 방향 연속 변 합치기
        out = []
        for e in edges:
            if out and out[-1]["o"] == e["o"] and e["o"] != "D":
                out[-1]["b"] = e["b"]
                if recompute and "pos" in out[-1] and "pos" in e:
                    L0 = abs(out[-1]["hi"] - out[-1]["lo"]) if "hi" in out[-1] else 1.0
                    L1 = abs(e["hi"] - e["lo"]) if "hi" in e else 1.0
                    if out[-1].get("wall") is None and e.get("wall") is not None:
                        out[-1]["pos"], out[-1]["wall"] = e["pos"], e["wall"]
                    elif not (out[-1].get("wall") is not None and e.get("wall") is None):
                        out[-1]["pos"] = (out[-1]["pos"] * L0 + e["pos"] * L1) / max(L0 + L1, 1e-9)
                changed = True
            else:
                out.append(e)
        if len(out) > 1 and out[0]["o"] == out[-1]["o"] and out[0]["o"] != "D":
            out[0]["a"] = out[-1]["a"]
            out.pop()
            changed = True
        edges = out
        # 짧은 턱(두 나란한 변 사이의 짧은 변) 지우기
        m = len(edges)
        for i in range(m):
            e = edges[i]
            L = np.linalg.norm(e["b"] - e["a"])
            p, q = edges[i - 1], edges[(i + 1) % m]
            if L < prm["jog_max"] and p["o"] == q["o"] and p["o"] != "D" and p["o"] != e["o"] and m > 4:
                edges = [x for j, x in enumerate(edges) if j != i]
                changed = True
                break
    return edges


# ═══════════════════════════════════════════ 7) 문·창 ═══════════════════════════════════════════

def find_openings(edges, walls_by_id, U, V, h, prm, top):
    """벽 변을 따라 2 cm 칸마다: 문 = 가운데·아래가 비고 벽 너머가 보임, 창 = 가운데가 비고 아래(창턱)가 보이거나
    앞을 가린 것 없이 위(인방)만 보임(유리는 LiDAR 가 거의 돌아오지 않는다). 앞에 가구가 있으면 '가려짐'으로 보고 넘긴다."""
    ops = []
    for ei, e in enumerate(edges):
        if e["wall"] is None:
            continue
        wl = walls_by_id[e["wall"]]
        j = 0 if e["o"] == "H" else 1
        lo, hi = sorted([e["a"][j], e["b"][j]])
        if hi - lo < prm["open_min"] + 0.1:
            continue
        pad = 0.2
        occ, beyond, front = _band_profile(U, V, h, wl, lo - pad, hi + pad, prm, top)
        hb = (np.arange(occ.shape[0]) + 0.5) * 0.05
        nb = occ.shape[1]
        low = occ[(hb > 0.1) & (hb < 0.8)].mean(0)
        mid = occ[(hb > 0.9) & (hb < 1.8)].mean(0)
        hsel = (hb > 2.0) & (hb < top - 0.1)
        high = occ[hsel].mean(0) if hsel.any() else np.zeros(nb)
        bpos = lo - pad + (np.arange(nb) + 0.5) * 0.02
        inside = (bpos >= lo) & (bpos <= hi)
        gap = (mid < 0.2) & inside
        see_b = cv2.dilate((beyond > 2).astype(np.uint8)[None, :], np.ones((1, 5), np.uint8))[0] > 0
        occl_b = front > 3
        door_b = gap & (low < 0.25) & see_b
        win_b = gap & ~door_b & ((low >= 0.25) | (~occl_b & (high >= 0.4)))
        for kind, mask in (("door", door_b), ("window", win_b)):
            for i0, i1 in _runs(mask, 4):
                width = (i1 - i0) * 0.02
                if width < prm["open_min"] or width > prm["open_max"]:
                    continue
                at_lo, at_hi = bpos[i0] - lo < 0.12, hi - bpos[i1 - 1] < 0.12
                real_l = mid[max(0, i0 - 10): i0].max(initial=0) >= 0.4
                real_r = mid[i1: i1 + 10].max(initial=0) >= 0.4
                see = float(see_b[i0:i1].mean())
                run = occ[:, i0:i1].mean(1)
                if kind == "door":
                    typ = "door" if width <= prm["door_max"] else "opening"
                    head = next((float(hb[k] - 0.025) for k in range(len(hb)) if hb[k] > 1.75 and run[k] > 0.4), None)
                    sill = 0.0
                    conf = 0.5 + 0.3 * min(1.0, see / 0.6) + 0.1 * (real_l or at_lo) + 0.1 * (real_r or at_hi)
                else:
                    if not ((real_l or at_lo) and (real_r or at_hi)):
                        continue                 # 양옆이 벽(또는 모서리)이 아니면 덜 찍힌 곳
                    if float(occl_b[i0:i1].mean()) > 0.3:
                        continue                 # 앞을 가구가 가렸다 = 벽이 안 보였을 뿐
                    lowm = float(np.median(low[i0:i1]))
                    sill = (next((float(hb[k] - 0.025) for k in range(len(hb)) if hb[k] > 0.3 and run[k] < 0.4), None)
                            if lowm >= 0.25 else None)
                    head = next((float(hb[k] - 0.025) for k in range(len(hb))
                                 if hb[k] > max(1.5, (sill or 0) + 0.3) and run[k] > 0.4), None)
                    if (sill is not None and sill < 0.25) or (sill is None and head is None):
                        continue
                    typ = "window"
                    conf = 0.35 + 0.25 * (sill is not None) + 0.2 * (head is not None) + 0.2 * min(1.0, see / 0.6)
                c_b = 0.5 * (bpos[i0] + bpos[i1 - 1])
                center = [c_b, e["pos"]] if e["o"] == "H" else [e["pos"], c_b]
                ops.append(dict(type=typ, edge=ei, wall=e["wall"], center=[round(float(x), 3) for x in center],
                                b0=float(bpos[i0] - 0.01), b1=float(bpos[i1 - 1] + 0.01), width_m=round(width, 3),
                                sill_m=(round(sill, 2) if sill is not None else None),
                                head_m=(round(head, 2) if head is not None else None),
                                see_through=round(see, 2), confidence=round(min(conf, 1.0), 2)))
    return ops


# ═══════════════════════════════════════════ 8) 그리기 (SVG · PNG · DXF 공통 목록) ═══════════════════════════════════════════

class Sheet:
    def __init__(self):
        self.items = []

    def line(self, a, b, layer, w=0.01, color="#222", dash=None):
        self.items.append(("line", dict(a=np.asarray(a, float), b=np.asarray(b, float), layer=layer, w=w, color=color, dash=dash)))

    def poly(self, pts, layer, closed=True, w=0.0, color=None, fill=None, opacity=1.0, dash=None):
        self.items.append(("poly", dict(pts=np.asarray(pts, float), layer=layer, closed=closed, w=w, color=color,
                                        fill=fill, opacity=opacity, dash=dash)))

    def arc(self, c, r, a0, a1, layer, w=0.01, color="#222"):
        self.items.append(("arc", dict(c=np.asarray(c, float), r=r, a0=a0, a1=a1, layer=layer, w=w, color=color)))

    def text(self, p, size, s, layer, color="#222", rot=0.0, bold=False, ascii_s=None):
        self.items.append(("text", dict(p=np.asarray(p, float), size=size, s=s, layer=layer, color=color, rot=rot,
                                        bold=bold, ascii=ascii_s if ascii_s is not None else s)))

    def bounds(self):
        pts = []
        for k, it in self.items:
            if k == "line":
                pts += [it["a"], it["b"]]
            elif k == "poly":
                pts += list(it["pts"])
            elif k == "arc":
                pts += [it["c"] - it["r"], it["c"] + it["r"]]
            elif k == "text":
                pts.append(it["p"])
        P = np.array(pts)
        return P.min(0), P.max(0)


def _fmt_mm(L):
    return f"{int(round(L * 100.0)) * 10:,}"


def _dim(sh, a, b, out, off, label=None, size=0.13):
    """a–b 치수선. out = 바깥 단위 벡터, off = 거리."""
    a, b, out = np.asarray(a, float), np.asarray(b, float), np.asarray(out, float)
    pa, pb = a + out * off, b + out * off
    sh.line(a + out * 0.05, pa + out * 0.08, "DIM", 0.006, "#c2410c")
    sh.line(b + out * 0.05, pb + out * 0.08, "DIM", 0.006, "#c2410c")
    sh.line(pa, pb, "DIM", 0.008, "#c2410c")
    d = (pb - pa) / max(np.linalg.norm(pb - pa), 1e-9)
    t = (d + out) / math.sqrt(2) * 0.06
    sh.line(pa - t, pa + t, "DIM", 0.012, "#c2410c")
    sh.line(pb - t, pb + t, "DIM", 0.012, "#c2410c")
    ang = math.degrees(math.atan2(d[1], d[0]))
    if ang > 90.1 or ang < -89.9:
        ang += 180.0
    ang = (ang + 180) % 360 - 180
    mid = 0.5 * (pa + pb) + out * (size * 0.75)
    L = float(np.linalg.norm(b - a))
    sh.text(mid, size, label or _fmt_mm(L), "DIM", "#c2410c", rot=ang)


ROOM_FILL = ["#dbeafe", "#dcfce7", "#fef3c7", "#fce7f3", "#e0e7ff", "#ccfbf1", "#fee2e2"]


def build_sheet(res, prm):
    sh = Sheet()
    T = prm["wall_draw_t"]
    for ri, rm in enumerate(res["rooms"]):
        P = np.array(rm["polygon"])
        sh.poly(P, "ROOM", True, 0.0, None, "#eef1ec" if rm["partial"] else ROOM_FILL[ri % len(ROOM_FILL)], 1.0)
    for ri, rm in enumerate(res["rooms"]):
        P = np.array(rm["polygon"])
        n = len(P)
        ops = [o for o in res["openings"] if o["room"] == rm["id"]]
        for ei, e in enumerate(rm["edges"]):
            a, b = np.array(e["a"]), np.array(e["b"])
            d = b - a
            L = np.linalg.norm(d)
            if L < 1e-6:
                continue
            d /= L
            out = np.array([d[1], -d[0]])
            if e["kind"] != "wall":
                sh.line(a, b, "SCAN_EDGE", 0.012, "#8a8f8c", dash=(0.08, 0.06))
                continue
            # 이웃 변이 벽이고 볼록 모서리면 두께만큼 늘인다
            prv, nxt = rm["edges"][ei - 1], rm["edges"][(ei + 1) % len(rm["edges"])]
            ext0 = T if (prv["kind"] == "wall" and _convex(prv, e)) else 0.0
            ext1 = T if (nxt["kind"] == "wall" and _convex(e, nxt)) else 0.0
            cuts = sorted([(o, _proj(o, a, d)) for o in ops if o["edge"] == ei], key=lambda x: x[1][0])
            t0 = -ext0
            pieces = []
            for o, (s0, s1) in cuts:
                pieces.append((t0, max(t0, s0)))
                t0 = s1
            pieces.append((t0, L + ext1))
            for s0, s1 in pieces:
                if s1 - s0 < 1e-3:
                    continue
                q0, q1 = a + d * s0, a + d * s1
                weak = e.get("evidence") == "top_band_only"
                sh.poly([q0, q1, q1 + out * T, q0 + out * T], "WALL", True, 0.004, "#1d2321", "#a3aaa6" if weak else "#3a403d", 1.0)
            for o, (s0, s1) in cuts:
                q0, q1 = a + d * s0, a + d * s1
                if o["type"] == "window":
                    for f in (0.0, 0.5, 1.0):
                        sh.line(q0 + out * T * f, q1 + out * T * f, "WINDOW", 0.008, "#2563eb")
                    sh.line(q0, q0 + out * T, "WINDOW", 0.008, "#2563eb")
                    sh.line(q1, q1 + out * T, "WINDOW", 0.008, "#2563eb")
                elif o["type"] == "door":
                    w_ = s1 - s0
                    hinge = q0
                    leaf = hinge - out * w_
                    sh.line(hinge, leaf, "DOOR", 0.012, "#0f766e")
                    a0 = math.degrees(math.atan2(-out[1], -out[0]))
                    a1 = math.degrees(math.atan2(d[1], d[0]))
                    lo_, hi_ = _arc_span(a0, a1)
                    sh.arc(hinge, w_, lo_, hi_, "DOOR", 0.006, "#0f766e")
                else:
                    sh.line(q0, q1, "OPENING", 0.008, "#7c3aed", dash=(0.06, 0.05))
                    sh.line(q0 + out * T, q1 + out * T, "OPENING", 0.008, "#7c3aed", dash=(0.06, 0.05))
                lab = {"door": "D", "window": "W", "opening": "O"}[o["type"]] + " " + _fmt_mm(o["width_m"])
                if o["type"] == "window":
                    lab += f" (sill {o['sill_m']:.2f})" if o.get("sill_m") is not None else " (sill ?)"
                ang = math.degrees(math.atan2(d[1], d[0]))
                if ang > 90.1 or ang < -89.9:
                    ang += 180.0
                ang = (ang + 180) % 360 - 180
                sh.text(0.5 * (q0 + q1) - out * 0.16, 0.10, lab, "OPENING_TXT", "#0f766e", rot=ang)
            if L >= 0.25:
                _dim(sh, a, b, out, T + prm["dim_offset"])
            if e.get("evidence") == "top_band_only" and L >= 0.8:
                ang = math.degrees(math.atan2(d[1], d[0]))
                ang = ang + 180.0 if (ang > 90.1 or ang < -89.9) else ang
                ang = (ang + 180) % 360 - 180
                sh.text(0.5 * (a + b) - out * 0.16, 0.09, "위쪽 벽만 확인 · 창일 수 있음", "OPENING_TXT", "#6b7280", rot=ang,
                        ascii_s="upper wall only (window?)")
        for ei, e in enumerate(rm["edges"]):
            if e["kind"] == "wall" or rm["partial"]:
                continue
            a, b = np.array(e["a"]), np.array(e["b"])
            d = b - a
            L = np.linalg.norm(d)
            if L < 1.0:
                continue
            d /= L
            out = np.array([d[1], -d[0]])
            _dim(sh, a, b, out, prm["dim_offset"] * 0.6, label=_fmt_mm(L) + "?")
        c = rm["label_at"]
        if rm["partial"]:
            sh.text([c[0], c[1]], 0.13, rm["name"], "ROOM_TXT", "#5d6762", ascii_s=rm["id"] + " (partial)")
            continue
        sh.text([c[0], c[1] + 0.22], 0.20, rm["name"], "ROOM_TXT", "#1d2321", bold=True, ascii_s=rm["id"])
        sh.text([c[0], c[1] - 0.02], 0.16, f"{rm['area_m2']:.2f} m² ({rm['area_pyeong']:.2f}평)", "ROOM_TXT", "#1d2321",
                ascii_s=f"{rm['area_m2']:.2f} m2")
        sub = f"{rm['width_m']:.2f} × {rm['depth_m']:.2f} m"
        if res["levels"]["ceiling_height_m"]:
            sub += f" · 천장 {res['levels']['ceiling_height_m']:.2f} m"
            hi_ = max(x["height_m"] for x in res["levels"]["ceiling_levels_m"])
            if hi_ - res["levels"]["ceiling_height_m"] > 0.05:
                sub += f" (우물 {hi_:.2f})"
        sh.text([c[0], c[1] - 0.24], 0.11, sub, "ROOM_TXT", "#5d6762",
                ascii_s=f"{rm['width_m']:.2f} x {rm['depth_m']:.2f} m")
        if rm["closed_ratio"] < 0.9:
            sh.text([c[0], c[1] - 0.42], 0.10, f"벽 확인 {rm['closed_ratio'] * 100:.0f}% · 점선 = 스캔 경계(면적은 최소값)",
                    "ROOM_TXT", "#b45309", ascii_s=f"walls {rm['closed_ratio'] * 100:.0f}% (dashed = scan edge)")
    return sh


def _convex(e0, e1):
    d0 = np.array(e0["b"]) - np.array(e0["a"])
    d1 = np.array(e1["b"]) - np.array(e1["a"])
    return d0[0] * d1[1] - d0[1] * d1[0] > 0      # 반시계 다각형에서 왼쪽으로 꺾이면 볼록


def _proj(o, a, d):
    s0 = float(np.dot(_pt_on(o, o["b0"]) - a, d))
    s1 = float(np.dot(_pt_on(o, o["b1"]) - a, d))
    return (min(s0, s1), max(s0, s1))


def _pt_on(o, bval):
    c = o["center"]
    return np.array([bval, c[1]]) if o["_o"] == "H" else np.array([c[0], bval])


def _arc_span(a0, a1):
    """두 각(도) 사이 90° 호의 반시계 시작·끝."""
    d = (a1 - a0) % 360
    return (a0, a0 + d) if d <= 180 else (a1, a1 + (360 - d))


# ── SVG ──
def write_svg(sh, path, title, subtitle, scale=100.0, margin=0.8):
    lo, hi = sh.bounds()
    lo = lo - margin
    hi = hi + margin
    head_h = 0.9
    W = (hi[0] - lo[0]) * scale
    H = (hi[1] - lo[1] + head_h) * scale

    def X(p):
        return (p[0] - lo[0]) * scale

    def Y(p):
        return (hi[1] - p[1] + head_h) * scale

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.1f} {H:.1f}" width="{W:.0f}" height="{H:.0f}" '
           f'font-family="Pretendard, \'Malgun Gothic\', \'Noto Sans KR\', sans-serif">',
           f'<rect width="{W:.1f}" height="{H:.1f}" fill="#ffffff"/>',
           f'<text x="{0.3 * scale:.1f}" y="{0.42 * scale:.1f}" font-size="{0.24 * scale:.1f}" font-weight="700" fill="#1d2321">{_esc(title)}</text>',
           f'<text x="{0.3 * scale:.1f}" y="{0.70 * scale:.1f}" font-size="{0.12 * scale:.1f}" fill="#5d6762">{_esc(subtitle)}</text>']
    order = {"ROOM": 0, "SCAN_EDGE": 1, "WALL": 2, "WINDOW": 3, "DOOR": 3, "OPENING": 3, "DIM": 4}
    items = sorted(sh.items, key=lambda kv: order.get(kv[1]["layer"], 5))
    for k, it in items:
        dash = f' stroke-dasharray="{it["dash"][0] * scale:.1f} {it["dash"][1] * scale:.1f}"' if it.get("dash") else ""
        if k == "line":
            out.append(f'<line x1="{X(it["a"]):.1f}" y1="{Y(it["a"]):.1f}" x2="{X(it["b"]):.1f}" y2="{Y(it["b"]):.1f}" '
                       f'stroke="{it["color"]}" stroke-width="{max(it["w"] * scale, 0.6):.1f}" stroke-linecap="round"{dash}/>')
        elif k == "poly":
            pts = " ".join(f"{X(p):.1f},{Y(p):.1f}" for p in it["pts"])
            tag = "polygon" if it["closed"] else "polyline"
            fill = it["fill"] or "none"
            stroke = f' stroke="{it["color"]}" stroke-width="{max(it["w"] * scale, 0.6):.1f}"' if it["color"] else ""
            out.append(f'<{tag} points="{pts}" fill="{fill}" fill-opacity="{it["opacity"]}"{stroke}{dash}/>')
        elif k == "arc":
            c, r = it["c"], it["r"]
            p0 = c + r * np.array([math.cos(math.radians(it["a0"])), math.sin(math.radians(it["a0"]))])
            p1 = c + r * np.array([math.cos(math.radians(it["a1"])), math.sin(math.radians(it["a1"]))])
            large = 1 if (it["a1"] - it["a0"]) % 360 > 180 else 0
            out.append(f'<path d="M {X(p0):.1f} {Y(p0):.1f} A {r * scale:.1f} {r * scale:.1f} 0 {large} 0 {X(p1):.1f} {Y(p1):.1f}" '
                       f'fill="none" stroke="{it["color"]}" stroke-width="{max(it["w"] * scale, 0.6):.1f}"/>')
        elif k == "text":
            p = it["p"]
            fw = ' font-weight="700"' if it["bold"] else ""
            rot = f' transform="rotate({-it["rot"]:.1f} {X(p):.1f} {Y(p):.1f})"' if abs(it["rot"]) > 0.1 else ""
            out.append(f'<text x="{X(p):.1f}" y="{Y(p):.1f}" font-size="{it["size"] * scale:.1f}" fill="{it["color"]}" '
                       f'text-anchor="middle" dominant-baseline="middle"{fw}{rot}>{_esc(it["s"])}</text>')
    # 축척 막대 1 m
    x0, y0 = 0.3 * scale, H - 0.3 * scale
    out.append(f'<rect x="{x0:.1f}" y="{y0 - 6:.1f}" width="{scale:.1f}" height="6" fill="#1d2321"/>')
    out.append(f'<text x="{x0 + scale / 2:.1f}" y="{y0 - 12:.1f}" font-size="{0.11 * scale:.1f}" text-anchor="middle" fill="#1d2321">1 m</text>')
    out.append("</svg>")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ── PNG (PIL) ──
def _font(size_px, bold=False):
    from PIL import ImageFont
    cands = (["C:/Windows/Fonts/malgunbd.ttf"] if bold else []) + [
        "C:/Windows/Fonts/malgun.ttf", "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc"]
    for c in cands:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, max(8, int(size_px))), True
            except Exception:
                pass
    return ImageFont.load_default(), False


def write_png(sh, path, title, subtitle, scale=110.0, margin=0.8):
    from PIL import Image, ImageDraw
    lo, hi = sh.bounds()
    lo = lo - margin
    hi = hi + margin
    head_h = 0.9
    W = int((hi[0] - lo[0]) * scale)
    H = int((hi[1] - lo[1] + head_h) * scale)
    img = Image.new("RGB", (W, H), "white")
    dr = ImageDraw.Draw(img)

    def XY(p):
        return ((p[0] - lo[0]) * scale, (hi[1] - p[1] + head_h) * scale)

    def dashed(a, b, col, wpx, dash):
        a, b = np.array(XY(a)), np.array(XY(b))
        L = np.linalg.norm(b - a)
        if L < 1:
            return
        d = (b - a) / L
        on, off = dash[0] * scale, dash[1] * scale
        t = 0.0
        while t < L:
            t1 = min(L, t + on)
            dr.line([tuple(a + d * t), tuple(a + d * t1)], fill=col, width=wpx)
            t = t1 + off

    order = {"ROOM": 0, "SCAN_EDGE": 1, "WALL": 2, "WINDOW": 3, "DOOR": 3, "OPENING": 3, "DIM": 4}
    texts = []
    for k, it in sorted(sh.items, key=lambda kv: order.get(kv[1]["layer"], 5)):
        if k == "line":
            wpx = max(1, int(round(it["w"] * scale)))
            if it.get("dash"):
                dashed(it["a"], it["b"], it["color"], wpx, it["dash"])
            else:
                dr.line([XY(it["a"]), XY(it["b"])], fill=it["color"], width=wpx)
        elif k == "poly":
            pts = [XY(p) for p in it["pts"]]
            if it["fill"]:
                dr.polygon(pts, fill=it["fill"])
            if it["color"]:
                wpx = max(1, int(round(it["w"] * scale)))
                seq = pts + ([pts[0]] if it["closed"] else [])
                dr.line(seq, fill=it["color"], width=wpx)
        elif k == "arc":
            c, r = XY(it["c"]), it["r"] * scale
            dr.arc([c[0] - r, c[1] - r, c[0] + r, c[1] + r], start=-it["a1"], end=-it["a0"], fill=it["color"],
                   width=max(1, int(round(it["w"] * scale))))
        elif k == "text":
            texts.append(it)
    any_ko = True
    for it in texts:
        f, ok = _font(it["size"] * scale, it["bold"])
        s = it["s"] if ok else it["ascii"]
        any_ko &= ok
        bb = dr.textbbox((0, 0), s, font=f)
        tw, th = bb[2] - bb[0] + 4, bb[3] - bb[1] + 6
        tim = Image.new("RGBA", (tw, th), (255, 255, 255, 0))
        ImageDraw.Draw(tim).text((2 - bb[0], 3 - bb[1]), s, font=f, fill=it["color"])
        if abs(it["rot"]) > 0.1:
            tim = tim.rotate(it["rot"], expand=True)
        x, y = XY(it["p"])
        img.paste(tim, (int(x - tim.width / 2), int(y - tim.height / 2)), tim)
    f, ok = _font(0.24 * scale, True)
    dr.text((0.3 * scale, 0.22 * scale), title if ok else "kgeoScan floor plan", font=f, fill="#1d2321")
    f2, ok2 = _font(0.12 * scale)
    dr.text((0.3 * scale, 0.58 * scale), subtitle if ok2 else "auto floor plan (reference only)", font=f2, fill="#5d6762")
    x0, y0 = 0.3 * scale, H - 0.3 * scale
    dr.rectangle([x0, y0 - 6, x0 + scale, y0], fill="#1d2321")
    dr.text((x0 + scale / 2 - 10, y0 - 26), "1 m", font=f2, fill="#1d2321")
    img.save(path)


# ── DXF (R12 ASCII) ──
DXF_LAYERS = {"WALL": 7, "SCAN_EDGE": 8, "DOOR": 3, "WINDOW": 5, "OPENING": 6, "OPENING_TXT": 3, "DIM": 30,
              "ROOM": 254, "ROOM_TXT": 7, "ROOM_OUTLINE": 4}


def write_dxf(sh, res, path):
    ent = []

    def g(code, val):
        if isinstance(val, float):
            val = f"{val:.4f}"
        ent.append(f"{code}\n{val}")

    def xyz(p, base=10, z=0.0):
        g(base, float(p[0]))
        g(base + 10, float(p[1]))
        g(base + 20, float(z))

    for k, it in sh.items:
        lay = it["layer"]
        if k == "line":
            g(0, "LINE"); g(8, lay); xyz(it["a"]); xyz(it["b"], 11)
        elif k == "poly":
            if lay == "ROOM":
                continue           # 채움은 ROOM_OUTLINE 으로 따로 쓴다
            g(0, "POLYLINE"); g(8, lay); g(66, 1); xyz((0, 0)); g(70, 1 if it["closed"] else 0)
            for p in it["pts"]:
                g(0, "VERTEX"); g(8, lay); xyz(p)
            g(0, "SEQEND"); g(8, lay)
        elif k == "arc":
            g(0, "ARC"); g(8, lay); xyz(it["c"]); g(40, float(it["r"])); g(50, float(it["a0"] % 360)); g(51, float(it["a1"] % 360))
        elif k == "text":
            s = str(it["ascii"]).encode("ascii", "replace").decode()
            g(0, "TEXT"); g(8, lay); xyz(it["p"]); g(40, float(it["size"] * 0.8)); g(1, s); g(50, float(it["rot"]))
            g(72, 1); g(73, 2); xyz(it["p"], 11)
    for rm in res["rooms"]:
        g(0, "POLYLINE"); g(8, "ROOM_OUTLINE"); g(66, 1); xyz((0, 0)); g(70, 1)
        for p in rm["polygon"]:
            g(0, "VERTEX"); g(8, "ROOM_OUTLINE"); xyz(p)
        g(0, "SEQEND"); g(8, "ROOM_OUTLINE")
    lo, hi = sh.bounds()
    L = ["0\nSECTION\n2\nHEADER", "9\n$ACADVER\n1\nAC1009", "9\n$INSUNITS\n70\n6",
         f"9\n$EXTMIN\n10\n{lo[0]:.4f}\n20\n{lo[1]:.4f}\n30\n0.0", f"9\n$EXTMAX\n10\n{hi[0]:.4f}\n20\n{hi[1]:.4f}\n30\n0.0",
         "0\nENDSEC", "0\nSECTION\n2\nTABLES",
         "0\nTABLE\n2\nLTYPE\n70\n2",
         "0\nLTYPE\n2\nCONTINUOUS\n70\n0\n3\nSolid line\n72\n65\n73\n0\n40\n0.0",
         "0\nLTYPE\n2\nDASHED\n70\n0\n3\n__ __ __\n72\n65\n73\n2\n40\n0.14\n49\n0.08\n49\n-0.06",
         "0\nENDTAB", f"0\nTABLE\n2\nLAYER\n70\n{len(DXF_LAYERS) + 1}", "0\nLAYER\n2\n0\n70\n0\n62\n7\n6\nCONTINUOUS"]
    for n, c in DXF_LAYERS.items():
        lt = "DASHED" if n in ("SCAN_EDGE", "OPENING") else "CONTINUOUS"
        L.append(f"0\nLAYER\n2\n{n}\n70\n0\n62\n{c}\n6\n{lt}")
    L += ["0\nENDTAB", "0\nTABLE\n2\nSTYLE\n70\n1",
          "0\nSTYLE\n2\nSTANDARD\n70\n0\n40\n0.0\n41\n1.0\n50\n0.0\n71\n0\n42\n0.2\n3\ntxt\n4\n", "0\nENDTAB", "0\nENDSEC",
          "0\nSECTION\n2\nENTITIES"]
    L += ent
    L += ["0\nENDSEC", "0\nEOF"]
    with open(path, "w", encoding="ascii", newline="\r\n") as f:
        f.write("\n".join(L) + "\n")


def check_dxf(path):
    """짝 구조·섹션·POLYLINE/SEQEND 균형·숫자 검사."""
    with open(path, encoding="ascii") as f:
        lines = f.read().splitlines()
    errs = []
    if len(lines) % 2:
        errs.append("odd line count")
    pairs = []
    for i in range(0, len(lines) - 1, 2):
        try:
            pairs.append((int(lines[i].strip()), lines[i + 1]))
        except ValueError:
            errs.append(f"bad code at line {i + 1}")
            break
    secs = [pairs[i + 1][1] for i, (c, v) in enumerate(pairs) if c == 0 and v == "SECTION"]
    n_poly = sum(1 for c, v in pairs if c == 0 and v == "POLYLINE")
    n_seq = sum(1 for c, v in pairs if c == 0 and v == "SEQEND")
    bad = 0
    for c, v in pairs:
        if 10 <= c <= 59:
            try:
                if not math.isfinite(float(v)):
                    bad += 1
            except ValueError:
                bad += 1
    if secs != ["HEADER", "TABLES", "ENTITIES"]:
        errs.append(f"sections {secs}")
    if n_poly != n_seq:
        errs.append("POLYLINE/SEQEND mismatch")
    if bad:
        errs.append(f"{bad} bad numbers")
    if not pairs or pairs[-1] != (0, "EOF"):
        errs.append("missing EOF")
    ents = {}
    in_ent = False
    for c, v in pairs:
        if c == 0 and v == "SECTION":
            in_ent = False
        if c == 2 and v == "ENTITIES":
            in_ent = True
        elif in_ent and c == 0 and v not in ("ENDSEC", "EOF", "VERTEX", "SEQEND"):
            ents[v] = ents.get(v, 0) + 1
    return dict(ok=not errs, errors=errs, entities=ents)


# ── 확인용 그림 ──
def write_debug(path, U, V, h, g, E, rooms, walls, segs, res, prm):
    sl = (h >= prm["slice_lo"]) & (h <= prm["slice_hi"])
    dens = g.raster(U[sl], V[sl])
    s = np.percentile(dens[dens > 0], 90) if (dens > 0).any() else 1
    base = 255 - np.clip(dens / s * 255, 0, 255).astype(np.uint8)
    img = cv2.cvtColor(base, cv2.COLOR_GRAY2BGR)
    tint = img.copy()
    tint[E] = (0.6 * tint[E] + 0.4 * np.array([250, 200, 140])).astype(np.uint8)
    img = tint
    cols = [(60, 180, 75), (200, 130, 0), (180, 30, 145), (0, 140, 255), (75, 25, 230), (128, 128, 0)]
    for i, m in enumerate(rooms):
        cs, _ = cv2.findContours(m.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        cv2.drawContours(img, cs, -1, cols[i % len(cols)], 1)
    up = 2
    img = cv2.resize(img, (g.W * up, g.H * up), interpolation=cv2.INTER_NEAREST)

    def px(u, v):
        return (int((u - g.u0) / g.res * up), int((v - g.v0) / g.res * up))

    for sg in segs:
        if sg.get("is_wall"):
            continue
        a, b = ((sg["c"], sg["b0"]), (sg["c"], sg["b1"])) if sg["fam"] == 0 else ((sg["b0"], sg["c"]), (sg["b1"], sg["c"]))
        cv2.line(img, px(*a), px(*b), (160, 160, 160), 1)
    for wl in walls:
        a, b = ((wl["c"], wl["b0"]), (wl["c"], wl["b1"])) if wl["fam"] == 0 else ((wl["b0"], wl["c"]), (wl["b1"], wl["c"]))
        cv2.line(img, px(*a), px(*b), (0, 0, 220), 2)
    for rm in res["rooms"]:
        P = np.array(rm["polygon"])
        for i in range(len(P)):
            e = rm["edges"][i]
            col = (0, 160, 0) if e["kind"] == "wall" else (0, 200, 255)
            cv2.line(img, px(*P[i]), px(*P[(i + 1) % len(P)]), col, 2)
    for o in res["openings"]:
        c = px(*o["center"])
        col = {"door": (128, 128, 0), "window": (255, 80, 0), "opening": (200, 0, 200)}[o["type"]]
        cv2.circle(img, c, 7, col, 2)
    img = cv2.flip(img, 0)      # v 위로
    cv2.putText(img, "grey: slice %.1f-%.1f m  blue tint: interior evidence  red: wall planes  green: plan  yellow: scan edge"
                % (prm["slice_lo"], prm["slice_hi"]), (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (30, 30, 30), 1, cv2.LINE_AA)
    cv2.imwrite(path, img)


# ═══════════════════════════════════════════ 9) 전체 ═══════════════════════════════════════════

def floorplan(Q, NQ, w, prm=None, log=print, name=None):
    prm = dict(DEFAULTS, **(prm or {}))
    log = _log_ascii(log)
    t0 = time.time()
    lv, NQ = find_levels(Q, NQ, w, prm, log)
    h = Q[:, 2] - lv["floor_h"]
    top = lv["ceiling_height_m"] or 2.4
    th, manh, spread = dominant_angle(NQ, h, w, top, prm)
    c, s = math.cos(th), math.sin(th)
    U = Q[:, 0] * c + Q[:, 1] * s
    V = -Q[:, 0] * s + Q[:, 1] * c
    NU = NQ[:, 0] * c + NQ[:, 1] * s
    NV = -NQ[:, 0] * s + NQ[:, 1] * c
    nh = NQ[:, 2]
    log(f"[axis] theta {math.degrees(th):.2f} deg, manhattan share {manh * 100:.0f}%, normal spread {spread:.2f} deg")
    keep = (h > -0.3) & (h < top + 0.3)
    m = 0.6
    g = Grid(np.percentile(U[keep], 0.1) - m, np.percentile(V[keep], 0.1) - m,
             np.percentile(U[keep], 99.9) + m, np.percentile(V[keep], 99.9) + m, prm["grid"])
    E = interior_evidence(U, V, h, nh, w, g, lv, prm)
    log(f"[interior] evidence {E.sum() * g.res ** 2:.1f} m2 on {g.W}x{g.H} grid")
    segs = find_wall_planes(U, V, h, NU, NV, nh, w, prm, log, top=top)
    walls = classify_walls(segs, E, g, prm, log)
    E = fill_to_walls(E, walls, g, prm)
    closes = close_gaps(walls, U, V, h, prm, top)
    bar = barrier_mask(walls, closes, g, prm)
    room_masks = split_rooms(E, bar, g, prm, log)
    walls_by_id = {wl["id"]: wl for wl in walls}
    rooms, openings = [], []
    for ri, mk in enumerate(room_masks):
        try:
            P, edges = room_polygon(mk, g, walls, prm)
        except Exception as ex:      # noqa: BLE001
            log(f"[rooms] polygon failed for space {ri + 1}: {ex}")
            continue
        area = _poly_area(P)
        if area < prm["room_min_m2"] * 0.5:
            continue
        per = sum(np.linalg.norm(e["b"] - e["a"]) for e in edges)
        wall_len = sum(np.linalg.norm(e["b"] - e["a"]) for e in edges if e["wall"] is not None)
        partial = bool(rooms) and wall_len / max(per, 1e-9) < prm["partial_ratio"]
        rid = f"R{len(rooms) + 1}"
        ops = find_openings(edges, walls_by_id, U, V, h, prm, top)
        for o in ops:
            o["room"] = rid
            o["_o"] = edges[o["edge"]]["o"]
        dt = cv2.distanceTransform(mk.astype(np.uint8), cv2.DIST_L2, 5)
        iv, iu = np.unravel_index(np.argmax(dt), dt.shape)
        lab = g.uv(iv, iu)
        bbox = P.max(0) - P.min(0)
        rooms.append(dict(
            id=rid, name=(name if (name and not rooms) else ("옆 공간(일부)" if partial else f"공간 {len(rooms) + 1}")),
            partial=partial,
            polygon=[[round(float(x), 4), round(float(y), 4)] for x, y in P],
            area_m2=round(area, 2), area_pyeong=round(area * PY_PER_M2, 2), perimeter_m=round(per, 3),
            width_m=round(float(bbox[0]), 3), depth_m=round(float(bbox[1]), 3),
            closed_ratio=round(wall_len / max(per, 1e-9), 3),
            evidence_m2=round(float(mk.sum() * g.res ** 2), 2),
            label_at=[round(float(lab[0]), 3), round(float(lab[1]), 3)],
            edges=[dict(a=[round(float(e["a"][0]), 4), round(float(e["a"][1]), 4)], b=[round(float(e["b"][0]), 4), round(float(e["b"][1]), 4)],
                        length_m=round(float(np.linalg.norm(e["b"] - e["a"])), 3), axis=e["o"],
                        kind=("wall" if e["wall"] is not None else "scan_edge"), wall=e["wall"],
                        evidence=(None if e["wall"] is None else e.get("evidence", "main_slice")))
                   for e in edges]))
        openings.extend(ops)
    for i, o in enumerate(openings):
        o["id"] = f"O{i + 1}"
    rms = [wl["rms_mm"] for wl in walls if wl["length"] >= 0.8]
    used = {e["wall"] for rm in rooms for e in rm["edges"] if e["wall"]}
    res = dict(
        version=VERSION,
        units="m",
        frame=dict(theta_deg=round(math.degrees(th), 3),
                   plan_from_input="X=x, Y=-z (ARKit y-up) or X=E, Y=N (LAS); u = X cos(t) + Y sin(t), v = -X sin(t) + Y cos(t)",
                   plan_to_input=[[round(c, 6), round(-s, 6)], [round(s, 6), round(c, 6)]],
                   floor_level=round(lv["floor_h"], 4)),
        levels=lv,
        rooms=rooms,
        walls=[dict(id=wl["id"], axis=("u" if wl["fam"] == 0 else "v"), pos=round(wl["c"], 4), normal=wl["s"],
                    extent=[round(wl["b0"], 3), round(wl["b1"], 3)], length_m=round(wl["length"], 3),
                    plane_rms_mm=wl["rms_mm"], behind_evidence=round(wl["behind"], 2), in_plan=wl["id"] in used,
                    main_slice=0 in wl["bands"], top_band_only=bool(wl["top_only"])) for wl in walls],
        openings=openings,
        quality=dict(manhattan_share=round(manh, 3), wall_normal_spread_deg=round(spread, 2),
                     wall_plane_rms_mm_median=(round(float(np.median(rms)), 1) if rms else None),
                     walls_found=len(walls), furniture_faces_rejected=len(segs) - len(walls),
                     seconds=round(time.time() - t0, 1)),
        notes=["면적은 실내 쪽 벽면을 이은 안목 면적이며 참고용입니다. 거래·광고에는 건축물대장(공부) 면적을 씁니다.",
               "점선 변은 벽이 확인되지 않은 스캔 경계입니다. 그 방의 면적은 최소값입니다.",
               "닫힌 문, 커튼으로 가린 창, 붙박이장은 벽으로 보일 수 있습니다. 벽 두께는 알 수 없어 그림에서 0.12 m 로 가정했습니다."],
    )
    total = sum(r["area_m2"] for r in rooms if not r["partial"])
    log(f"[done] {len(rooms)} rooms, total {total:.2f} m2, {len(openings)} openings, {res['quality']['seconds']} s")
    return res, dict(U=U, V=V, h=h, g=g, E=E, rooms=room_masks, walls=walls, segs=segs)


def floorplan_files(mesh=None, las=None, out_dir="out", name=None, params=None, log=print, debug=True, title=None, scan_name=None):
    prm = dict(DEFAULTS, **(params or {}))
    os.makedirs(out_dir, exist_ok=True)
    L = _log_ascii(log)
    if mesh:
        Q, NQ, w, src = load_mesh_points(mesh, prm, L)
    elif las:
        Q, NQ, w, src = load_las_points(las, prm, L)
    else:
        raise ValueError("mesh or las required")
    res, dbg = floorplan(Q, NQ, w, prm, log, name=name)
    res["source"] = src
    res["params"] = {k: (list(v) if isinstance(v, tuple) else v) for k, v in prm.items()}
    sh = build_sheet(res, prm)
    total = sum(r["area_m2"] for r in res["rooms"] if not r["partial"])
    ttl = title or "kgeoScan 자동 평면도"
    ch = res["levels"]["ceiling_height_m"]
    sub = (f"스캔 {scan_name or os.path.basename(os.path.dirname(src['path']))} · 공간 {sum(1 for r in res['rooms'] if not r['partial'])}개 · 합계 {total:.2f} m² ({total * PY_PER_M2:.2f}평)"
           + (f" · 천장 {ch:.2f} m" if ch else "") + " · 안목 기준 참고용 · 치수 mm")
    paths = dict(json=os.path.join(out_dir, "floorplan.json"), svg=os.path.join(out_dir, "floorplan.svg"),
                 dxf=os.path.join(out_dir, "floorplan.dxf"), png=os.path.join(out_dir, "floorplan.png"))
    write_svg(sh, paths["svg"], ttl, sub)
    write_dxf(sh, res, paths["dxf"])
    res["dxf_check"] = check_dxf(paths["dxf"])
    try:
        write_png(sh, paths["png"], ttl, sub)
    except Exception as ex:      # noqa: BLE001  (PIL 없으면 미리보기만 빠진다)
        L(f"[png] skipped: {ex}")
        paths.pop("png")
    if debug:
        paths["debug"] = os.path.join(out_dir, "floorplan_debug.png")
        write_debug(paths["debug"], dbg["U"], dbg["V"], dbg["h"], dbg["g"], dbg["E"], dbg["rooms"], dbg["walls"], dbg["segs"], res, prm)
    for o in res["openings"]:
        o.pop("_o", None)
    res["files"] = {k: os.path.basename(v) for k, v in paths.items()}
    with open(paths["json"], "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=_json_default)
    return res


def _json_default(o):
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o).__name__)


def main(argv=None):
    ap = argparse.ArgumentParser(description="kgeoScan floor plan from an indoor LiDAR scan (mesh.ply y-up or scan.las z-up)")
    ap.add_argument("--mesh")
    ap.add_argument("--las")
    ap.add_argument("--out", required=True)
    ap.add_argument("--name", default=None, help="name of the largest room (UTF-8)")
    ap.add_argument("--title", default=None)
    ap.add_argument("--scan-name", default=None, help="scan id shown in the subtitle (default: mesh folder name)")
    ap.add_argument("--slice", default=None, help="wall slice band above floor, e.g. 1.0,1.5")
    ap.add_argument("--params", default=None, help="JSON overrides of DEFAULTS")
    ap.add_argument("--no-debug", action="store_true")
    a = ap.parse_args(argv)
    prm = json.loads(a.params) if a.params else {}
    if a.slice:
        lo, hi = (float(x) for x in a.slice.split(","))
        prm.update(slice_lo=lo, slice_hi=hi)
    res = floorplan_files(mesh=a.mesh, las=a.las, out_dir=a.out, name=a.name, params=prm, debug=not a.no_debug, title=a.title,
                          scan_name=a.scan_name)
    for rm in res["rooms"]:
        print(f"  {rm['id']}: {rm['area_m2']:.2f} m2  {rm['width_m']:.2f} x {rm['depth_m']:.2f} m  walls {rm['closed_ratio'] * 100:.0f}%")
    for o in res["openings"]:
        print(f"  {o['id']} {o['type']}: width {o['width_m']:.2f} m  sill {o['sill_m']}  head {o['head_m']}  see {o['see_through']}")
    print("  dxf check:", "ok" if res["dxf_check"]["ok"] else res["dxf_check"]["errors"], res["dxf_check"]["entities"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
