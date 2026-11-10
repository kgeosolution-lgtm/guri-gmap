r"""
kgeoScan 굴착 지하시설물 자동 추출 (docs/utility_contract.md §2 utilities.json)

  python -I worker/utility_extract.py --las scan.las --out <dir> [--mesh mesh.ply --georef job.json]
         [--job-id ID] [--params '{"min_arc_deg": 100}'] [--no-debug]

  from utility_extract import extract, extract_files, DEFAULTS      # worker/ 를 sys.path 에. numpy + cv2 + open3d
  res = extract(P_utm, rgb, normals=None, params=None, log=print, job_id="", debug_png=None)
  res = extract_files(las="scan.las", mesh=None, georef=None, out_dir="out", job_id=None, params=None)

입력
  - scan.las (UTM 52N, Z 위, 색) — process_scan.py 가 메시 정점을 옮겨 쓴 것(최대 200 만 점, 무작위 솎음).
  - --mesh + --georef 가 있으면 메시를 쓴다: 정점을 process_scan.py 와 같은 식으로 UTM 으로 옮기고
    (e = x·cosθ − z·sinθ, n = −x·sinθ − z·cosθ, h = y), 면을 6 mm 간격으로 고르게 다시 뽑는다.
    줄인(decimation) 메시의 정점은 평평한 곳에서 성기고 굽은 곳에서 촘촘한데, 면에서 다시 뽑으면 밀도가 고르고
    면 법선(관측 쪽을 향함)을 그대로 쓴다. LAS 만 있으면 점마다 넓이 가중치(kNN)로 밀도 차이를 보정한다.

방법
  1) 원지반·굴착: 2.5 cm 격자 높이(셀 10 % 분위 = 가장 낮은 면). 수평에 가까운 평면을 RANSAC 으로 차례로 찾아
     지지가 비슷하면 높은 쪽을 지면으로 고른다. 지면보다 0.2 m 넘게 낮은 셀을 씨앗으로, 0.05 m 넘게 낮은 셀로 키워
     (이력 문턱) 가장 큰 덩어리를 굴착으로 본다. 둘레 띠(가장자리 바깥 0.3–1.5 m, 깨진 가장자리 제외)의 셀 중앙값으로
     지면을 다시 맞춘다: RANSAC 평면(rim_plane, 띠의 국소 기울기 중앙값 ±3 % 안 — 연석·보도를 비스듬히 잇지 않게),
     잔차가 크면 2차 곡면(rim_quad, 횡단 경사·볼록 노면), 그래도 크면 강건 국소 평면 보간면(rim_tin, 이동 최소제곱).
     굴착 밖 점의 15 % 넘게 지면보다 0.3 m 아래면 지면을 믿지 않는다(ground_ambiguous).
  2) 관: 굴착 안 점(지면 3 cm 아래)을 방향 후보마다 0.2 m 두께로 자른다(굴착 축, 그 직각, 법선 쌍 투표로 찾은 방향).
     조각마다 2D 원 RANSAC(세 점, 여러 크기의 이웃에서 뽑기 + LO 다듬기). 원 하나를 받아들이는 조건:
     보이는 호 ≥ 90°, 호를 따라 점이 고르게 있음, 원 안이 비어 있음, 호가 아래를 보지 않음(오목한 모서리 배제),
     호가 140° 보다 작으면 양 끝이 접선으로 이어지지 않음(흙 턱·판자 모서리 배제).
     조각 사이 원을 이어(틈 0.6 m 까지) 길이 ≥ 0.35 m·반지름 일정·중심 매끈한 것을 남긴 뒤, 중심점으로 축을 다시 잡아
     0.15 m 조각으로 다시 맞춘다(지름 = 조각 지름의 중앙값). 같은 관이 여러 방향에서 나오면 하나만 남긴다.
     양 끝이 모두 굴착 안에서 끊긴(벽·흙으로 들어가지 않는) 짧은 원통은 공구·자재로 보고 뺀다.
  3) 가는 선형 물체(케이블·다발): 관 점을 뺀 굴착 바닥 높이도(1 cm)를 0.25 m 열림 연산 바닥과 비교해 솟은 띠를 찾고,
     단면 높이 분포의 봉우리 수로 다발(bundle, 가닥 수)·케이블(cable)을 가른다.
  4) 깊이: 중심선 점마다 원지반 높이 − 관 윗면. 경사 % 는 중심선 순서(서→동, 동서가 같으면 남→북) 방향 오르막이 +.
  5) 종류: 관 표면 점의 색(HSV) → COLOR_TABLE (잠정. 국내 관 피복 색 규정 조사 후 확정). class_source="color".
     색은 사전확률로만 쓴다(class_confidence 낮음). 사용자가 현장에서 고친다.
  6) 공칭경: 외경 후보(NOMINAL_OD, 재질별)마다 반지름을 고정해 맞춘 잔차가 가장 작은 것 → nominal_mm(DN)·nominal_od_mm.
     diameter_mm 는 기본으로 실측 외경(params diameter_mode="nominal" 이면 공칭 외경). DN ≠ 외경이라 DN 숫자로 바로 맞추지 않는다.
  7) v0.2: 중심선은 모두 축(centerline_ref "axis"), stations·clearances, georef 가 있으면 ARKit 로컬 필드.
     photo_remeasure_targets(): 4K 사진 재측정 연결 지점(축 점 + 축 방향·수평 직각·위).

로그는 ASCII 만 쓴다(cp949 콘솔). utilities.json 은 UTF-8.
"""
import argparse
import json
import math
import os
import sys
import time

import cv2
import numpy as np

VERSION = 1

# ─────────────────────────── 색 → 시설물 종류 (잠정 표, 한 곳에서만 고친다) ───────────────────────────
# 기획 세션 잠정 대응(2026-11-10): 황 → 가스, 청 → 상수, 적 → 전력, 주황 → 통신, 녹 → 하수, 흑·회 → unknown(덕타일 상수관도 흑색).
# 색은 진흙·조명 때문에 '사전확률'로만 쓴다 → class_conf 를 낮게 둔다. 현장에서 사용자가 고친다(class_source="user").
# hue 는 도(0–360). 범위가 0 을 넘어가면 (lo > hi). s_min/v_min 은 0–1.
# 흙(갈색 H 20–40°, S 0.3–0.55)이 주황·노랑으로 읽히지 않게 주황·노랑·빨강의 s_min 을 높게 둔다.
# TODO(site): 국내 지하시설물 관 피복 색 규정 조사 결과로 확정.
COLOR_TABLE = {
    "yellow": {"hue": (40, 68), "s_min": 0.50, "v_min": 0.25, "class": "gas", "candidates": ["gas"], "class_conf": 0.60},
    "orange": {"hue": (16, 40), "s_min": 0.62, "v_min": 0.25, "class": "telecom", "candidates": ["telecom", "power"],
               "class_conf": 0.40},
    "red":    {"hue": (340, 16), "s_min": 0.50, "v_min": 0.20, "class": "power", "candidates": ["power", "telecom"],
               "class_conf": 0.50},
    "green":  {"hue": (75, 165), "s_min": 0.25, "v_min": 0.20, "class": "sewer", "candidates": ["sewer", "telecom"],
               "class_conf": 0.40},
    "blue":   {"hue": (180, 255), "s_min": 0.30, "v_min": 0.20, "class": "water", "candidates": ["water"], "class_conf": 0.55},
    "purple": {"hue": (255, 340), "s_min": 0.25, "v_min": 0.20, "class": "unknown", "candidates": ["water"], "class_conf": 0.20},
    # 무채색 (채도 < 위 s_min 들): v 로 나눈다
    "black":  {"v_max": 0.22, "class": "unknown", "candidates": ["water", "sewer", "power", "heat"], "class_conf": 0.20},
    "gray":   {"v_max": 0.75, "class": "unknown", "candidates": ["sewer", "water", "telecom", "power"], "class_conf": 0.20},
    "white":  {"v_max": 1.01, "class": "unknown", "candidates": ["telecom", "power", "sewer"], "class_conf": 0.20},
}
CHROMATIC_ORDER = ["yellow", "orange", "red", "green", "blue", "purple"]
ACHROMATIC_ORDER = ["black", "gray", "white"]

# ─────────────────────────── 공칭경 → 외경 후보 (잠정, mm) ───────────────────────────
# 공칭경(DN)은 외경이 아니다: DN100 = 강관 114.3, PE 110, 덕타일 주철 118. 그래서 외경을 DN 숫자로 바로 맞추지 않고,
# 재질별 외경 후보마다 반지름을 고정해 맞춰 잔차가 가장 작은 외경을 고른 뒤 그 DN 을 nominal_mm 으로 낸다.
# 흄관·이중벽 파형관처럼 내경이 호칭인 관은 표에 없다(외경 = 내경 + 2×두께). TODO(site): KS 표로 확인·보강.
NOMINAL_OD = {
    "steel/PVC": {15: 21.7, 20: 27.2, 25: 34.0, 32: 42.7, 40: 48.6, 50: 60.5, 65: 76.3, 80: 89.1, 100: 114.3, 125: 139.8,
                  150: 165.2, 200: 216.3, 250: 267.4, 300: 318.5, 350: 355.6, 400: 406.4, 450: 457.2, 500: 508.0, 600: 609.6},
    "PE":        {20: 25, 25: 32, 32: 40, 40: 50, 50: 63, 65: 75, 80: 90, 100: 110, 125: 140, 150: 160, 200: 225, 250: 280,
                  300: 315, 350: 355, 400: 400, 450: 450, 500: 500, 600: 630},
    "DCIP":      {80: 98, 100: 118, 150: 170, 200: 222, 250: 274, 300: 326, 350: 378, 400: 429, 450: 480, 500: 532, 600: 635},
}


DEFAULTS = dict(
    # ── 지면·굴착 ──
    cell=0.025,             # 높이 격자 (m)
    pit_seed=0.20,          # 굴착 씨앗: 지면보다 이만큼 넘게 낮은 셀
    pit_grow=0.05,          # 굴착 키움 문턱
    pit_min_area=0.25,      # m²
    pit_min_depth=0.30,     # 굴착 최대 깊이가 이보다 얕으면 굴착이 아니다
    max_below_outside=0.15,  # 굴착 밖 점 가운데 지면보다 0.3 m 넘게 낮은 비율이 이보다 크면 지면을 믿지 않는다
    rim_inner=0.30, rim_outer=1.50,   # 지면 맞춤에 쓰는 둘레 띠 (굴착 가장자리에서 m). 안쪽 0.3 m 는 굴착으로 깨진 곳
    rim_inner_min=0.06, rim_min_area=0.8,
    ground_grad_tol=0.03,   # 지면 평면 기울기는 둘레 국소 기울기 중앙값에서 이만큼(3 %) 안   # 띠 넓이가 rim_min_area m² 보다 작으면 안쪽을 rim_inner_min 까지 줄인다
    ground_tol=0.03,        # RANSAC 평면 정상치 (m)
    max_tilt_deg=25.0,      # 지면 평면 최대 기울기
    local_ground_rms=0.012, # 평면 잔차가 이보다 크면 국소 보간면(rim_tin)을 시험
    mls_sigma=0.45,         # rim_tin 가우스 폭 (m)
    below_ground=0.03,      # 관 찾기에 쓰는 점: 지면보다 이만큼 아래
    # ── 점 준비 ──
    voxel=0.006,            # 굴착 안 점 솎음 (m)
    normal_radius=0.03,
    mesh_spacing=0.006,     # 메시에서 다시 뽑는 간격
    # ── 조각 원 찾기 ──
    slab_len=0.20, slab_step=0.10, bin=0.005,
    n_hyp=1200,
    scales=[0.025, 0.05, 0.10, 0.18, 0.32],
    r_min=0.016, r_max=0.40,
    tau_frac=0.08, tau_min=0.006, tau_max=0.010,   # 원 정상치 폭 = clip(frac·r, min, max)
    min_arc_deg=90.0,
    edge_test_arc_deg=140.0,   # 이보다 좁은 호는 양 끝 접선 연속(판자·흙 턱 모서리) 검사
    min_density=0.45,          # 호 위 실제 넓이 ÷ 기대 넓이 (r·호각·조각 두께)
    bin_cover=0.30,            # 10° 칸이 '덮였다' = 기대 넓이의 이 비율 이상
    min_uniform=0.75,          # 호 안 칸 가운데 기대의 35 % 이상인 칸 비율
    max_bins=4000,             # 조각 2D 칸이 이보다 많으면 칸을 키운다
    max_circles=12, max_tries=30, top_k=30,
    normal_axis_max=0.5,       # |법선·관 방향| 이 이보다 크면 그 방향 조각에서 뺀다
    # ── 이어 붙이기 ──
    max_gap=0.6, min_len=0.35, min_slabs=3, r_cv_max=0.25, max_slope=0.35,
    # ── 방향 후보 ──
    dir_merge_deg=6.0, max_dirs=4, dir_peak=1.4,   # 법선 쌍 투표 봉우리: 배경(중앙값)의 이 배 이상
    cross_fan_deg=[-20.0, -10.0, 10.0, 20.0],       # 굴착 직각 방향 둘레에 늘 더 보는 방향
    # ── 다듬기 ──
    ref_slab=0.15, ref_step=0.075, ref_passes=6,
    free_end_max_len=2.0,      # 양 끝이 굴착 안에서 끊긴 원통은 이 길이 미만이면 공구·자재로 뺀다
    soil_arc_max=200.0,        # 호가 이보다 좁고 바로 옆 흙과 색이 같으면 흙 턱으로 본다:
    min_contrast=10.0,         #   관 표면 중앙값 색과 이웃 중앙값 색의 ΔE 가 이보다 작거나
    soil_like_max=0.35,        #   이웃 점 가운데 관 색과 ΔE < 15 인 점이 이 비율 이상
    rim_edge_depth=0.06,       # 윗면 깊이가 이보다 얕고 가장자리를 따라가면 굴착 모서리로 뺀다
    # ── 가는 선형 물체 ──
    lin_cell=0.01, lin_open=0.25, lin_min_h=0.007, lin_max_h=0.12, lin_min_len=0.40, lin_max_w=0.30,
    # ── 출력 ──
    centerline_step=0.10,
    seed=0,
    diameter_mode="measured",   # "measured": diameter_mm = 맞춘 외경 / "nominal": 공칭 스냅 외경 (둘 다 diameter_fit_mm·nominal_* 은 남김)
    threads=0,              # 방향별 스레드 수 (0 = min(4, CPU 절반)). 스레드마다 원 가설 행렬 ~100 MB
)

DRAW_BGR = {"gas": (0, 215, 255), "water": (255, 120, 30), "sewer": (60, 110, 150), "power": (40, 40, 230),
            "telecom": (60, 200, 60), "heat": (0, 140, 255), "unknown": (220, 80, 220)}


# ═══════════════════════════════════════════ 작은 도구 ═══════════════════════════════════════════
def _ascii_log(log):
    def f(msg):
        if log is None:
            return
        try:
            log(str(msg).encode("ascii", "replace").decode("ascii"))
        except Exception:
            pass
    return f


def _cell_quantile(keys, z, q, n_cells):
    """셀 번호(keys)마다 z 의 q 분위(가장 가까운 순위). 점 없는 셀은 NaN."""
    order = np.lexsort((z, keys))
    ks, zs = keys[order], z[order]
    cnt = np.bincount(ks, minlength=n_cells)
    start = np.concatenate([[0], np.cumsum(cnt)[:-1]])
    out = np.full(n_cells, np.nan)
    has = cnt > 0
    idx = start[has] + np.floor(q * (cnt[has] - 1) + 0.5).astype(np.int64)
    out[has] = zs[idx]
    return out, cnt


def _hysteresis(seed, grow):
    n, lab = cv2.connectedComponents(grow.astype(np.uint8), connectivity=8)
    keep = np.zeros(n, bool)
    keep[np.unique(lab[seed & grow])] = True
    keep[0] = False
    return keep[lab]


def _fill_holes(mask):
    inv = (~mask).astype(np.uint8)
    n, lab = cv2.connectedComponents(inv, connectivity=4)
    border = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    holes = inv.astype(bool) & ~np.isin(lab, border)
    return mask | holes


def _lsq_plane(X, w=None):
    """z = a x + b y + c (가중 최소제곱)."""
    A = np.column_stack([X[:, 0], X[:, 1], np.ones(len(X))])
    if w is None:
        w = np.ones(len(X))
    Aw = A * w[:, None]
    coef = np.linalg.lstsq(Aw.T @ A + 1e-12 * np.eye(3), Aw.T @ X[:, 2], rcond=None)[0]
    return coef


def _ransac_plane(X, tol, iters, rng, max_tilt_deg=25.0, grad_prior=None):
    """수평에 가까운 평면 RANSAC → (a, b, c), 정상치 마스크. X: (n,3).
    grad_prior=(gx, gy, tol): 평면 기울기(z = a x + b y + c 의 a, b)가 이 국소 기울기에서 tol 넘게 다르면 버린다
    (연석·보도처럼 단이 진 둘레에서 양쪽 다른 높이를 비스듬히 잇는 평면을 막는다)."""
    n = len(X)
    if n < 10:
        return None, np.zeros(n, bool)
    idx = rng.integers(0, n, size=(iters, 3))
    p1, p2, p3 = X[idx[:, 0]], X[idx[:, 1]], X[idx[:, 2]]
    nrm = np.cross(p2 - p1, p3 - p1)
    nn = np.linalg.norm(nrm, axis=1)
    ok = nn > 1e-9
    nrm[ok] /= nn[ok, None]
    nrm[nrm[:, 2] < 0] *= -1
    ok &= nrm[:, 2] >= math.cos(math.radians(max_tilt_deg))
    if grad_prior is not None:
        ga, gb = -nrm[:, 0] / np.maximum(nrm[:, 2], 1e-6), -nrm[:, 1] / np.maximum(nrm[:, 2], 1e-6)
        ok &= np.hypot(ga - grad_prior[0], gb - grad_prior[1]) <= grad_prior[2]
    if not ok.any():
        return None, np.zeros(n, bool)
    p1, nrm = p1[ok], nrm[ok]
    sub = X if n <= 20000 else X[rng.choice(n, 20000, replace=False)]
    best, best_s = None, -1
    for i in range(0, len(p1), 64):
        d = np.abs(np.einsum("hnk,hk->hn", sub[None, :, :] - p1[i:i + 64, None, :], nrm[i:i + 64]))
        s = (d < tol).sum(1)
        j = int(np.argmax(s))
        if s[j] > best_s:
            best_s, best = s[j], (p1[i + j], nrm[i + j])
    p, nv = best
    inl = np.abs((X - p) @ nv) < tol
    coef = _lsq_plane(X[inl])
    for _ in range(2):
        res = X[:, 2] - (coef[0] * X[:, 0] + coef[1] * X[:, 1] + coef[2])
        inl = np.abs(res) < tol
        if inl.sum() < 3:
            break
        coef = _lsq_plane(X[inl])
    return coef, inl


class Ground:
    """원지반 높이 z(x, y). method: rim_plane | rim_tin | scan_plane."""

    def __init__(self, method, coef=None, grid=None, fallback=None, quad=None):
        self.method, self.coef, self.grid, self.fallback, self.quad = method, coef, grid, fallback, quad

    def z(self, x, y):
        x = np.asarray(x, float)
        y = np.asarray(y, float)
        if self.quad is not None:
            cx, cy, q = self.quad
            dx, dy = x - cx, y - cy
            return q[0] + q[1] * dx + q[2] * dy + q[3] * dx * dx + q[4] * dx * dy + q[5] * dy * dy
        if self.grid is None:
            a, b, c = self.coef
            return a * x + b * y + c
        x0, y0, step, Z = self.grid
        fx = np.clip((x - x0) / step, 0, Z.shape[1] - 1.001)
        fy = np.clip((y - y0) / step, 0, Z.shape[0] - 1.001)
        ix, iy = np.floor(fx).astype(int), np.floor(fy).astype(int)
        tx, ty = fx - ix, fy - iy
        z00, z01 = Z[iy, ix], Z[iy, ix + 1]
        z10, z11 = Z[iy + 1, ix], Z[iy + 1, ix + 1]
        return (z00 * (1 - tx) + z01 * tx) * (1 - ty) + (z10 * (1 - tx) + z11 * tx) * ty

    def slope_deg(self, x=None, y=None):
        if (self.grid is None and self.quad is None) or x is None:
            a, b, _ = self.coef
            return math.degrees(math.atan(math.hypot(a, b)))
        h = 0.25
        gx = (self.z(x + h, y) - self.z(x - h, y)) / (2 * h)
        gy = (self.z(x, y + h) - self.z(x, y - h)) / (2 * h)
        return math.degrees(math.atan(math.hypot(float(gx), float(gy))))


def _robust_quad(S, cx, cy, iters=6):
    """z = q0 + q1 dx + q2 dy + q3 dx² + q4 dx dy + q5 dy² (Tukey IRLS). → (q, 정상치 rms) 또는 (None, inf)."""
    if len(S) < 30:
        return None, float("inf")
    dx, dy = S[:, 0] - cx, S[:, 1] - cy
    A = np.column_stack([np.ones(len(S)), dx, dy, dx * dx, dx * dy, dy * dy])
    w = np.ones(len(S))
    for _ in range(iters):
        q = np.linalg.lstsq(A * w[:, None], S[:, 2] * w, rcond=None)[0]
        r = S[:, 2] - A @ q
        sc = 1.4826 * np.median(np.abs(r)) + 1e-4
        w = np.clip(1 - (r / (4.685 * sc)) ** 2, 0, 1) ** 2
    inl = np.abs(r) < max(0.025, 3 * sc)
    return q, float(np.sqrt(np.mean(r[inl] ** 2))) if inl.any() else float("inf")


def _mls_surface(S, nodes, sigma, fallback_coef):
    """이동 최소제곱 국소 평면: 노드마다 가우스 가중 평면의 노드 높이. S: (n,3) 둘레 표본."""
    out = np.empty(len(nodes))
    for i in range(0, len(nodes), 256):
        q = nodes[i:i + 256]
        dx = S[None, :, 0] - q[:, None, 0]
        dy = S[None, :, 1] - q[:, None, 1]
        w = np.exp(-(dx * dx + dy * dy) / (2 * sigma * sigma))
        sw = w.sum(1)
        sx, sy = (w * dx).sum(1), (w * dy).sum(1)
        sxx, sxy, syy = (w * dx * dx).sum(1), (w * dx * dy).sum(1), (w * dy * dy).sum(1)
        z = S[None, :, 2]
        sz, sxz, syz = (w * z).sum(1), (w * dx * z).sum(1), (w * dy * z).sum(1)
        lam = 1e-3 * sw + 1e-9
        A = np.stack([np.stack([sxx + lam, sxy, sx], -1), np.stack([sxy, syy + lam, sy], -1),
                      np.stack([sx, sy, sw + 1e-12], -1)], -2)
        bvec = np.stack([sxz, syz, sz], -1)
        sol = np.linalg.solve(A, bvec[..., None])[..., 0]
        zz = sol[:, 2]
        far = sw < 1e-3
        if far.any():
            zz[far] = fallback_coef[0] * q[far, 0] + fallback_coef[1] * q[far, 1] + fallback_coef[2]
        out[i:i + 256] = zz
    return out


# ═══════════════════════════════════════════ 1) 지면·굴착 ═══════════════════════════════════════════
class _HGrid:
    def __init__(self, P, cell):
        self.cell = cell
        self.x0, self.y0 = float(P[:, 0].min()) - cell, float(P[:, 1].min()) - cell
        self.nx = int((P[:, 0].max() - self.x0) / cell) + 2
        self.ny = int((P[:, 1].max() - self.y0) / cell) + 2
        self.ix = ((P[:, 0] - self.x0) / cell).astype(np.int64)
        self.iy = ((P[:, 1] - self.y0) / cell).astype(np.int64)
        self.key = self.iy * self.nx + self.ix
        self.cx = self.x0 + (np.arange(self.nx) + 0.5) * cell
        self.cy = self.y0 + (np.arange(self.ny) + 0.5) * cell
        self.CX, self.CY = np.meshgrid(self.cx, self.cy)

    def quantile(self, z, q):
        v, cnt = _cell_quantile(self.key, z, q, self.nx * self.ny)
        return v.reshape(self.ny, self.nx), cnt.reshape(self.ny, self.nx)

    def to_xy(self, ix, iy):
        return self.x0 + (np.asarray(ix) + 0.5) * self.cell, self.y0 + (np.asarray(iy) + 0.5) * self.cell


def _local_grad_prior(Z, valid, rim, prm):
    """둘레 띠 셀의 국소 기울기 중앙값 (단·턱 셀 제외) → (gx, gy, tol) 또는 None."""
    cell = prm["cell"]
    m = valid.astype(np.float32)
    Z0 = np.where(valid, Z, 0).astype(np.float32)
    a = cv2.GaussianBlur(Z0, (9, 9), 2.0)
    b = cv2.GaussianBlur(m, (9, 9), 2.0)
    Zs = np.where(b > 0.5, a / np.maximum(b, 1e-6), np.nan)
    gy, gx = np.gradient(Zs, cell)
    ok = rim & np.isfinite(gx) & np.isfinite(gy) & (np.hypot(gx, gy) < 0.25)
    if ok.sum() < 50:
        return None
    return float(np.median(gx[ok])), float(np.median(gy[ok])), prm["ground_grad_tol"]


def _pit_mask(D, valid, prm):
    seed = valid & (D > prm["pit_seed"])
    grow = valid & (D > prm["pit_grow"])
    m = _hysteresis(seed, grow)
    m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8)).astype(bool)
    m = _fill_holes(m)
    m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)).astype(bool)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8), connectivity=8)
    comps = []
    for i in range(1, n):
        area = stats[i, cv2.CC_STAT_AREA] * prm["cell"] ** 2
        if area < prm["pit_min_area"]:
            continue
        sel = lab == i
        dmax = np.nanpercentile(np.where(sel & valid, D, np.nan), 99) if (sel & valid).any() else 0
        if dmax < prm["pit_min_depth"]:
            continue
        comps.append((area, i, dmax))
    comps.sort(reverse=True)
    return lab, comps


def find_ground_trench(P, prm, log, rng, Nrm=None):
    """→ dict(ground, grid, mask, trench geometry ...) 또는 굴착이 없으면 trench=None."""
    g = _HGrid(P, prm["cell"])
    lo, cnt = g.quantile(P[:, 2], 0.10)
    med, _ = g.quantile(P[:, 2], 0.50)
    valid = cnt >= 2
    out = dict(grid=g, lo=lo, med=med, valid=valid, warnings=[])
    X = np.column_stack([g.CX[valid], g.CY[valid], med[valid]])
    if len(X) < 50:
        out.update(ground=None, trench=None)
        out["warnings"].append("scan_too_small")
        return out
    # 차례 RANSAC 으로 수평 평면 후보
    planes, rest = [], np.ones(len(X), bool)
    for _ in range(3):
        if rest.sum() < 0.05 * len(X):
            break
        coef, inl = _ransac_plane(X[rest], prm["ground_tol"], 400, rng, prm["max_tilt_deg"])
        if coef is None or inl.sum() < 0.05 * len(X):
            break
        idx = np.flatnonzero(rest)
        res_all = X[:, 2] - (coef[0] * X[:, 0] + coef[1] * X[:, 1] + coef[2])
        sup = int((np.abs(res_all) < prm["ground_tol"]).sum())
        zc = coef[0] * X[:, 0].mean() + coef[1] * X[:, 1].mean() + coef[2]
        planes.append(dict(coef=coef, support=sup, zc=zc))
        rest[idx[inl]] = False
        rest &= np.abs(res_all) > 2 * prm["ground_tol"]
    if not planes:
        out.update(ground=None, trench=None)
        out["warnings"].append("no_ground_plane")
        return out
    if Nrm is not None:
        # 메시 법선은 관측한 쪽을 본다(TSDF): 지면은 위를 보고, 천장은 아래를 본다. 아래를 보는 평면은 지면 후보가 아니다.
        sub = rng.choice(len(P), min(len(P), 60000), replace=False)
        for pl in planes:
            a, b, c = pl["coef"]
            on = np.abs(P[sub, 2] - (a * P[sub, 0] + b * P[sub, 1] + c)) < prm["ground_tol"]
            pl["up"] = float(np.median(Nrm[sub[on], 2])) if on.sum() >= 50 else 1.0
        down = [pl for pl in planes if pl["up"] < 0]
        planes = [pl for pl in planes if pl["up"] >= 0]
        if down:
            log("ground candidates facing down (ceiling?): " + ", ".join(f"z{p_['zc']:.2f} nz{p_['up']:.2f}" for p_ in down))
        if not planes:
            out.update(ground=None, trench=None)
            out["warnings"].append("ground_faces_down")
            return out
    planes.sort(key=lambda p: -p["support"])
    gp = planes[0]
    for p in planes[1:]:
        if p["support"] >= 0.4 * gp["support"] and p["zc"] > gp["zc"] + 0.25:
            gp = p
    coef = gp["coef"]
    log(f"ground candidates: " + ", ".join(f"z{p['zc']:.2f}/{p['support']}" for p in planes) + f" -> z {gp['zc']:.2f}")

    ground = Ground("scan_plane", coef=coef)
    best = None
    for it in range(2):
        D = ground.z(g.CX, g.CY) - lo
        lab, comps = _pit_mask(D, valid, prm)
        if not comps:
            break
        if best is None:
            sel = comps[0][1]
        else:  # 첫 굴착과 가장 많이 겹치는 덩어리
            ov = [((lab == c[1]) & best).sum() for c in comps]
            sel = comps[int(np.argmax(ov))][1]
        mask = lab == sel
        all_pits = np.isin(lab, [c[1] for c in comps])
        if len(comps) > 1 and it == 1:
            out["warnings"].append("multiple_pits")
        # 둘레 띠: 굴착 가장자리 바깥 rim_inner–rim_outer. 굴착으로 깨진 가장자리(안쪽 0.3 m)는 뺀다.
        # 스캔 여유가 좁아 띠가 모자라면 안쪽을 rim_inner_min 까지 줄인다.
        dist = cv2.distanceTransform((~mask).astype(np.uint8), cv2.DIST_L2, 5) * prm["cell"]
        rim = valid & ~mask & (dist >= prm["rim_inner"]) & (dist <= prm["rim_outer"])
        if rim.sum() * prm["cell"] ** 2 < prm["rim_min_area"]:
            rim = valid & ~mask & (dist >= prm["rim_inner_min"]) & (dist <= prm["rim_outer"])
            if it == 1 and "rim_narrow" not in out["warnings"]:
                out["warnings"].append("rim_narrow")
        S = np.column_stack([g.CX[rim], g.CY[rim], med[rim]])
        if len(S) < 30:
            out["warnings"].append("rim_too_small")
            best = mask
            break
        gp = _local_grad_prior(med, valid, rim, prm)
        rcoef, rinl = _ransac_plane(S, prm["ground_tol"], 400, rng, prm["max_tilt_deg"], grad_prior=gp)
        if rcoef is None:
            rcoef, rinl = _ransac_plane(S, prm["ground_tol"], 400, rng, prm["max_tilt_deg"])
        if rcoef is None:
            best = mask
            break
        if gp is not None and np.hypot(rcoef[0] - gp[0], rcoef[1] - gp[1]) > gp[2]:
            # 최소제곱 다듬기가 기울기를 끌고 가면 사전 기울기 안의 RANSAC 해로 되돌린다
            rcoef = _lsq_plane(S[rinl & (np.abs(S[:, 2] - (gp[0] * S[:, 0] + gp[1] * S[:, 1])
                                                - np.median(S[rinl, 2] - gp[0] * S[rinl, 0] - gp[1] * S[rinl, 1])) < prm["ground_tol"])])
        res = S[:, 2] - (rcoef[0] * S[:, 0] + rcoef[1] * S[:, 1] + rcoef[2])
        rms_plane = float(np.sqrt(np.mean(res[rinl] ** 2)))
        inl_frac = float(rinl.mean())
        ground = Ground("rim_plane", coef=rcoef)
        rms_used, n_rim = rms_plane, int(rinl.sum())
        if rms_plane > prm["local_ground_rms"] or inl_frac < 0.6:
            keep = np.abs(res) < 0.08
            # 2차 곡면 (횡단 경사·노면 볼록): 굴착 중심 기준, 강건 IRLS
            iy_, ix_ = np.nonzero(mask)
            qcx, qcy = float(g.CX[iy_, ix_].mean()), float(g.CY[iy_, ix_].mean())
            qc, qrms = _robust_quad(S[keep], qcx, qcy)
            if qc is not None and qrms < 0.75 * rms_used:
                ground = Ground("rim_quad", coef=rcoef, quad=(qcx, qcy, qc))
                rms_used, n_rim = qrms, int(keep.sum())
        if rms_used > prm["local_ground_rms"] or inl_frac < 0.6:
            # 국소 보간면(이동 최소제곱 평면). 강건하게 두 번 걸러 낸다.
            keep = np.abs(res) < 0.08
            Ss = S[keep]
            if len(Ss) > 2500:
                Ss = Ss[rng.choice(len(Ss), 2500, replace=False)]
            ok = np.ones(len(Ss), bool)
            for _ in range(3):
                zf = _mls_surface(Ss[ok], Ss[:, :2], prm["mls_sigma"], rcoef)
                r2 = Ss[:, 2] - zf
                mad = 1.4826 * np.median(np.abs(r2[ok] - np.median(r2[ok]))) + 1e-4
                ok = np.abs(r2) < max(0.025, 3 * mad)
            rms_local = float(np.sqrt(np.mean(r2[ok] ** 2)))
            if rms_local < 0.75 * rms_used:
                step = 0.05
                xs = np.arange(g.x0, g.x0 + g.nx * g.cell + step, step)
                ys = np.arange(g.y0, g.y0 + g.ny * g.cell + step, step)
                NX, NY = np.meshgrid(xs, ys)
                Zg = _mls_surface(Ss[ok], np.column_stack([NX.ravel(), NY.ravel()]), prm["mls_sigma"], rcoef)
                ground = Ground("rim_tin", coef=rcoef, grid=(xs[0], ys[0], step, Zg.reshape(NX.shape)))
                rms_used, n_rim = rms_local, int(ok.sum())
                if "ground_local_model" not in out["warnings"]:
                    out["warnings"].append("ground_local_model")
            if inl_frac < 0.6 and "rim_irregular" not in out["warnings"]:
                out["warnings"].append("rim_irregular")
        best = mask
        out.update(rim_mask=rim, rim_rms=rms_used, rim_inlier_frac=inl_frac, rim_n=n_rim, rim_rms_plane=rms_plane)
    if best is None:
        out.update(ground=ground, trench=None)
        out["warnings"].append("no_trench")
        return out
    # 지면이 맞는지: 굴착 밖에서 지면보다 크게 낮은 곳이 많으면(천장을 지면으로 잡은 실내 스캔 등) 굴착으로 보지 않는다
    near_pits = cv2.dilate(all_pits.astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool)
    okp = (g.ix >= 0) & (g.ix < g.nx) & (g.iy >= 0) & (g.iy < g.ny)
    outp = np.ones(len(P), bool)
    outp[okp] = ~near_pits[g.iy[okp], g.ix[okp]]
    below = float((outp & (P[:, 2] < ground.z(P[:, 0], P[:, 1]) - 0.3)).sum() / max(1, len(P)))
    out["below_outside_frac"] = below
    if below > prm["max_below_outside"]:
        log(f"ground ambiguous: {below * 100:.0f}% of points outside the pits are >0.3 m below the ground -> no trench")
        out.update(ground=ground, trench=None)
        out["warnings"].append("ground_ambiguous")
        return out
    out.update(ground=ground, mask=best)
    # 가장자리 둘러싸임 (스캔 끝에 걸친 굴착은 둘레가 모자란다)
    ring = cv2.dilate(best.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool) & ~best
    out["rim_coverage"] = float((ring & valid).sum() / max(1, ring.sum()))
    if out["rim_coverage"] < 0.6:
        out["warnings"].append("rim_partial")
    return out


def trench_geometry(gt, P_floor_keys=None):
    g, mask, ground = gt["grid"], gt["mask"], gt["ground"]
    cell = g.cell
    cs, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(cs, key=cv2.contourArea)
    ap = cv2.approxPolyDP(c, 1.0, True)[:, 0, :]
    ox, oy = g.to_xy(ap[:, 0], ap[:, 1])
    ring = np.column_stack([ox, oy])
    rect = cv2.minAreaRect(np.column_stack(g.to_xy(c[:, 0, 0], c[:, 0, 1])).astype(np.float32))
    (w, h) = rect[1]
    iy, ix = np.nonzero(mask)
    mx, my = g.to_xy(ix, iy)
    M = np.column_stack([mx, my])
    cen = M.mean(0)
    ev, evec = np.linalg.eigh(np.cov((M - cen).T))
    axis = evec[:, np.argmax(ev)]
    if axis[0] < 0 or (abs(axis[0]) < 1e-9 and axis[1] < 0):
        axis = -axis
    contour_m = np.column_stack(g.to_xy(c[:, 0, 0], c[:, 0, 1])).astype(np.float32)
    return dict(ring=ring, length=float(max(w, h)), width=float(min(w, h)), axis=axis, center=cen,
                contour=contour_m, area=float(mask.sum() * cell * cell))


# ═══════════════════════════════════════════ 2) 굴착 안 점 ═══════════════════════════════════════════
def _knn_area_weights(Pt, Nt, k=8, kq=14):
    """점 하나가 대표하는 겉넓이: 이웃까지 거리를 접평면에 투영해 잰다(두께 방향 잡음이 넓이를 부풀리지 않게)."""
    import open3d.core as o3c
    T = o3c.Tensor(Pt.astype(np.float32))
    nns = o3c.nns.NearestNeighborSearch(T)
    nns.knn_index()
    out = np.empty(len(Pt))
    for i in range(0, len(Pt), 200000):
        idx, _ = nns.knn_search(o3c.Tensor(Pt[i:i + 200000].astype(np.float32)), kq + 1)
        idx = idx.numpy()[:, 1:].astype(np.int64)
        V = (Pt[idx] - Pt[i:i + 200000, None, :]).astype(np.float32)
        n = Nt[i:i + 200000, None, :].astype(np.float32)
        dn = (V * n).sum(-1)
        d2 = np.maximum((V * V).sum(-1) - dn * dn, 0)
        d2.sort(axis=1)
        out[i:i + 200000] = math.pi * d2[:, k - 1] / k
    med = np.median(out)
    return np.clip(out, 0.2 * med, 5 * med)


def _noise_sigma(Pt, Nt, n=6000, k=60, seed=0):
    """점 잡음(면 법선 방향) 어림: 이웃 k 점의 접평면 거리 RMS 의 중앙값. 흙 질감도 조금 들어간다."""
    import open3d.core as o3c
    if len(Pt) < 100:
        return 0.005
    rng = np.random.default_rng(seed)
    sel = rng.choice(len(Pt), min(n, len(Pt)), replace=False)
    T = o3c.Tensor(Pt.astype(np.float32))
    nns = o3c.nns.NearestNeighborSearch(T)
    nns.knn_index()
    idx, _ = nns.knn_search(o3c.Tensor(Pt[sel].astype(np.float32)), k)
    idx = idx.numpy().astype(np.int64)
    V = Pt[idx] - Pt[idx].mean(1, keepdims=True)
    C = np.einsum("nki,nkj->nij", V, V) / k
    ev = np.linalg.eigvalsh(C)
    planar = ev[:, 1] > 4 * ev[:, 0]
    s = np.sqrt(np.maximum(ev[planar, 0] if planar.any() else ev[:, 0], 0))
    # 이웃 평균을 빼서 구한 잔차는 점 하나의 잡음보다 작다 (k 점 평면 맞춤) → 보정
    return float(np.median(s) * math.sqrt(k / (k - 3)))


def trench_points(P, C, Nrm, gt, prm, log):
    import open3d as o3d
    g, mask, ground = gt["grid"], gt["mask"], gt["ground"]
    dm = cv2.dilate(mask.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    ok = (g.ix >= 0) & (g.ix < g.nx) & (g.iy >= 0) & (g.iy < g.ny)
    inside = np.zeros(len(P), bool)
    inside[ok] = dm[g.iy[ok], g.ix[ok]]
    inside &= P[:, 2] < ground.z(P[:, 0], P[:, 1]) - prm["below_ground"]
    idx = np.flatnonzero(inside)
    pcd = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(P[idx]))
    pcd.colors = o3d.utility.Vector3dVector(C[idx].astype(np.float64) / 255.0)
    if Nrm is not None:
        pcd.normals = o3d.utility.Vector3dVector(Nrm[idx])
    if prm["voxel"] > 0:
        pcd = pcd.voxel_down_sample(prm["voxel"])
    Pt = np.asarray(pcd.points).copy()
    Ct = np.clip(np.asarray(pcd.colors) * 255 + 0.5, 0, 255).astype(np.uint8)
    if Nrm is None or not pcd.has_normals():
        pcd.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=prm["normal_radius"], max_nn=30))
    Nt = np.asarray(pcd.normals).copy()
    Nt /= np.linalg.norm(Nt, axis=1, keepdims=True) + 1e-12
    if Nrm is None:      # 추정 법선은 부호가 없다 → 위를 보게 (굴착 안은 위에서 찍는다)
        Nt[Nt[:, 2] < 0] *= -1
    Wt = _knn_area_weights(Pt, Nt) if len(Pt) > 20 else np.full(len(Pt), prm["voxel"] ** 2)
    log(f"trench points: {len(idx)} -> {len(Pt)} (voxel {prm['voxel'] * 1000:.0f} mm), median area/pt "
        f"{np.median(Wt) * 1e6:.1f} mm2")
    return Pt, Ct, Nt, Wt


# ═══════════════════════════════════════════ 3) 방향 후보 ═══════════════════════════════════════════
def candidate_directions(Pt, axis_phi, prm, log):
    import open3d as o3d
    import open3d.core as o3c
    dirs = [axis_phi % math.pi, (axis_phi + math.pi / 2) % math.pi]
    fan = [(axis_phi + math.pi / 2 + math.radians(f)) % math.pi for f in prm["cross_fan_deg"]]
    # 두 크기(1 cm 점·2.5 cm 법선 = 가는 관, 2 cm·6 cm = 굵은 관)로 따로 세어 정규화해 더한다
    h = np.zeros(180)
    for vox, rad in ((0.01, 0.025), (0.02, 0.06)):
        pcd = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(Pt)).voxel_down_sample(vox)
        if len(pcd.points) < 100:
            continue
        pcd.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=rad, max_nn=40))
        Q, Nn = np.asarray(pcd.points), np.asarray(pcd.normals)
        T = o3c.Tensor(Q.astype(np.float32))
        nns = o3c.nns.NearestNeighborSearch(T)
        nns.knn_index()
        k = 16
        idx, _ = nns.knn_search(T, k)
        idx = idx.numpy().astype(np.int64)
        i = np.repeat(np.arange(len(Q)), k - 1)
        j = idx[:, 1:].ravel()
        c = np.cross(Nn[i], Nn[j])
        s = np.linalg.norm(c, axis=1)
        ok = s > math.sin(math.radians(12))
        d = c[ok] / s[ok, None]
        ok2 = np.abs(d[:, 2]) < 0.3
        phi = np.mod(np.arctan2(d[ok2, 1], d[ok2, 0]), math.pi)
        hh = np.bincount((phi / math.pi * 180).astype(int) % 180, minlength=180).astype(float)
        h += hh / (np.median(hh) + 1e-9)
    if not h.any():
        return dirs + fan, []
    ker = np.exp(-0.5 * (np.arange(-8, 9) / 2.5) ** 2)
    hs = np.convolve(np.concatenate([h[-8:], h, h[:8]]), ker / ker.sum(), mode="same")[8:-8]
    bg = np.median(hs) + 1e-9
    peaks = []
    for a in range(180):
        win = [hs[(a + o) % 180] for o in range(-4, 5)]
        if hs[a] >= max(win) and hs[a] >= prm["dir_peak"] * bg and hs[a] >= 0.05 * hs.max():
            peaks.append((hs[a] / bg, math.radians(a + 0.5)))
    peaks.sort(reverse=True)
    n_base = len(dirs)
    for strength, p in peaks:
        if len(dirs) - n_base >= prm["max_dirs"]:
            break
        if all(abs(((p - q + math.pi / 2) % math.pi) - math.pi / 2) > math.radians(prm["dir_merge_deg"]) for q in dirs):
            dirs.append(p)
    # 가로지르는 관은 굴착 축에 꼭 직각이 아니다 → 직각 ± 부채꼴도 본다 (투표로 못 찾는 가는 관)
    for p in fan:
        if all(abs(((p - q + math.pi / 2) % math.pi) - math.pi / 2) > math.radians(prm["dir_merge_deg"]) for q in dirs):
            dirs.append(p)
    log("directions (deg): " + ", ".join(f"{math.degrees(q):.0f}" for q in dirs) +
        "  peaks " + ", ".join(f"{math.degrees(p):.0f}x{s_:.1f}" for s_, p in peaks[:6]))
    return dirs, peaks


# ═══════════════════════════════════════════ 4) 2D 원 ═══════════════════════════════════════════
def _tau(r, prm):
    return np.clip(prm["tau_frac"] * r, prm["tau_min"], prm["tau_max"])


def _circle3(A, B, Cc):
    ax, ay, bx, by, cx, cy = A[:, 0], A[:, 1], B[:, 0], B[:, 1], Cc[:, 0], Cc[:, 1]
    d = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    a2, b2, c2 = ax * ax + ay * ay, bx * bx + by * by, cx * cx + cy * cy
    with np.errstate(divide="ignore", invalid="ignore"):
        ux = (a2 * (by - cy) + b2 * (cy - ay) + c2 * (ay - by)) / d
        uy = (a2 * (cx - bx) + b2 * (ax - cx) + c2 * (bx - ax)) / d
    return ux, uy, np.hypot(ax - ux, ay - uy)


def _cos_min(r):
    """법선-지름 방향 허용 각: 작은 관(법선이 뭉개짐) 60°, r ≥ 8 cm 는 41° (묻힌 선의 바닥 점을 빼려고)."""
    return np.clip(0.5 + (np.asarray(r) - 0.04) * 6.25, 0.5, 0.75)


def _radial_ok(dv0, dv1, d, N2, UP, r=0.0):
    """법선이 지름 방향(부호 없이)이고, 위를 보는 점(UP > 0.5)은 원의 아래쪽에 있지 않을 것."""
    ok = np.abs((dv0 * N2[..., 0] + dv1 * N2[..., 1]) / d) > _cos_min(r)
    if UP is not None:
        ok &= ~((UP > 0.5) & (dv1 / d < -0.3))
    return ok


def _fit_circle(Q, w, c, r, tau, iters=10, r_lo=0.0, r_hi=1e9, N2=None, UP=None):
    """가중 기하 원 맞춤(가우스-뉴턴 + Huber). N2 가 있으면 법선이 지름 방향이 아닌 점(바닥·벽)은 뺀다. → (c, r) 또는 None."""
    c = np.array(c, float)
    r = float(r)
    for it in range(iters):
        dv = Q - c
        d = np.hypot(dv[:, 0], dv[:, 1]) + 1e-12
        res = d - r
        thr = (3.0 if it < 3 else 2.0) * tau
        m = np.abs(res) < thr
        if N2 is not None:
            m &= _radial_ok(dv[:, 0], dv[:, 1], d, N2, UP, r)
        if m.sum() < 5:
            return None
        ar = np.abs(res[m])
        ww = w[m] * np.where(ar <= tau, 1.0, tau / np.maximum(ar, 1e-12))
        J = np.column_stack([-dv[m, 0] / d[m], -dv[m, 1] / d[m], -np.ones(int(m.sum()))])
        JW = J * ww[:, None]
        H = J.T @ JW + 1e-14 * np.eye(3)
        gvec = JW.T @ res[m]
        try:
            delta = -np.linalg.solve(H, gvec)
        except np.linalg.LinAlgError:
            return None
        step = np.abs(delta).max()
        if step > max(0.5 * r, 0.02):
            delta *= max(0.5 * r, 0.02) / step
        c = c + delta[:2]
        r = float(np.clip(r + delta[2], r_lo, r_hi))
        if np.abs(delta).max() < 2e-5:
            break
    return c, r


def _arc_run(ang, w, exp_bin, nb=36, frac=0.2):
    """각도별 가중 막대 → 가장 긴 연속 호 (한 칸 빈틈은 메운다). → span_deg, run 칸 마스크(nb), 가운데 각."""
    b = (np.mod(ang, 2 * math.pi) / (2 * math.pi) * nb).astype(int) % nb
    h = np.bincount(b, weights=w, minlength=nb)
    cov = h >= frac * exp_bin
    cov2 = cov | (np.roll(cov, 1) & np.roll(cov, -1))
    if cov2.all():
        return 360.0, np.ones(nb, bool), 0.0, b
    z = int(np.argmin(cov2))
    rolled = np.roll(cov2, -z)
    best_len, best_start, cur, start = 0, 0, 0, 0
    for i in range(nb):
        if rolled[i]:
            if cur == 0:
                start = i
            cur += 1
            if cur > best_len:
                best_len, best_start = cur, start
        else:
            cur = 0
    run = np.zeros(nb, bool)
    for i in range(best_start, best_start + best_len):
        run[(i + z) % nb] = True
    mid_bin = (best_start + z + best_len / 2.0) % nb
    return best_len * 360.0 / nb, run, mid_bin / nb * 2 * math.pi, b


def _evaluate_circle(Q, W, N2, alive, c, r, L, prm, tau=None, check=True, inside_pts=None, UP=None):
    """원 하나를 조각 점에 비추어 판정. → dict(ok, why, span, support, density, rms, inl(mask), ...)."""
    tau = float(_tau(r, prm)) if tau is None else tau
    dv = Q - c
    d = np.hypot(dv[:, 0], dv[:, 1]) + 1e-12
    res = d - r
    radial = _radial_ok(dv[:, 0], dv[:, 1], d, N2, UP, r)
    inl = (np.abs(res) < tau) & radial & alive
    out = dict(ok=False, why="few", c=c, r=r, tau=tau, inl=inl)
    if inl.sum() < 5:
        return out
    ang = np.arctan2(dv[inl, 1], dv[inl, 0])
    exp_bin = r * (2 * math.pi / 36) * L
    span, run, mid, bins = _arc_run(ang, W[inl], exp_bin, frac=prm["bin_cover"])
    in_run = np.zeros(len(Q), bool)
    in_run[np.flatnonzero(inl)[run[bins]]] = True
    support = float(W[in_run].sum())
    expected = r * math.radians(span) * L
    density = support / max(expected, 1e-12)
    rr = res[in_run]
    ww = W[in_run]
    rms = float(np.sqrt((ww * rr * rr).sum() / max(ww.sum(), 1e-12))) if in_run.any() else 1.0
    hb = np.bincount(bins, weights=W[inl], minlength=36)
    uniform = float((hb[run] >= 0.35 * exp_bin).mean()) if run.any() else 0.0
    out.update(span=span, support=support, density=density, rms=rms, mid=mid, inl=in_run, uniform=uniform)
    if not check:
        out["ok"] = True
        return out
    if span < prm["min_arc_deg"]:
        out["why"] = "arc"
        return out
    if density < prm["min_density"] or uniform < prm["min_uniform"]:
        out["why"] = "density"
        return out
    if math.sin(mid) < -0.35:          # 호가 아래를 본다 = 오목한 모서리(바닥-벽)
        out["why"] = "concave"
        return out
    # 호의 두 반쪽이 각각 굽어 있어야 한다 (곧은 면 조각 여럿을 이은 가짜 원 배제)
    if span < 300:
        Pi = Q[in_run]
        wi = W[in_run]
        rel = np.mod(np.arctan2(Pi[:, 1] - c[1], Pi[:, 0] - c[0]) - mid + math.pi, 2 * math.pi) - math.pi
        sag = r * (1 - math.cos(math.radians(span) / 4))
        for half in (rel < 0, rel >= 0):
            if half.sum() < 8:
                continue
            ph, wh = Pi[half], wi[half]
            mu = (ph * wh[:, None]).sum(0) / wh.sum()
            cov = ((ph - mu) * wh[:, None]).T @ (ph - mu) / wh.sum()
            line_rms = math.sqrt(max(np.linalg.eigvalsh(cov)[0], 0))
            rc = res[in_run][half]
            circ_rms = math.sqrt(float((wh * rc * rc).sum() / wh.sum()))
            curv = 0.3 * sag
            if curv < 1.0 * circ_rms:
                continue
            expect = math.hypot(circ_rms, curv)
            if line_rms < circ_rms + 0.4 * (expect - circ_rms):
                out["why"] = "straight"
                return out
    Qi = Q if inside_pts is None else inside_pts[0]
    Wi = W if inside_pts is None else inside_pts[1]
    if r > 2.5 * tau:
        di = np.hypot(Qi[:, 0] - c[0], Qi[:, 1] - c[1])
        inside = float(Wi[di < r - max(2.0 * tau, 0.3 * r)].sum())
        if inside > 0.12 * support:
            out["why"] = "filled"
            return out
    if span < prm["edge_test_arc_deg"]:
        # 양 끝에서 접선 방향으로 점이 이어지면 원통이 아니라 꺾인 면의 둥근 모서리
        half = math.radians(span) / 2
        occ = []
        for ae, sg in ((mid - half, -1.0), (mid + half, 1.0)):
            pe = c + r * np.array([math.cos(ae), math.sin(ae)])
            t = sg * np.array([-math.sin(ae), math.cos(ae)])
            lam = np.array([0.5, 0.9, 1.3]) * max(r, 0.02)
            probes = pe[None, :] + lam[:, None] * t[None, :]
            dd = np.hypot(Qi[None, :, 0] - probes[:, None, 0], Qi[None, :, 1] - probes[:, None, 1]).min(1)
            occ.append(float((dd < tau).mean()))
        out["edge_occ"] = occ
        if min(occ) >= 0.66:
            out["why"] = "edge"
            return out
    out["ok"] = True
    out["why"] = ""
    return out


def _bin_slab(u, z, n_u, n_z, w, binsz):
    """조각 점 → 2D 칸 (무게중심, 넓이 합, 법선은 각도 두 배 평균)."""
    iu = np.floor(u / binsz).astype(np.int64)
    iz = np.floor(z / binsz).astype(np.int64)
    key = (iu - iu.min()) * (iz.max() - iz.min() + 1) + (iz - iz.min())
    uk, inv = np.unique(key, return_inverse=True)
    m = len(uk)
    W = np.bincount(inv, weights=w, minlength=m)
    Qu = np.bincount(inv, weights=w * u, minlength=m) / W
    Qz = np.bincount(inv, weights=w * z, minlength=m) / W
    th2 = 2 * np.arctan2(n_z, n_u)
    cx = np.bincount(inv, weights=w * np.cos(th2), minlength=m)
    sx = np.bincount(inv, weights=w * np.sin(th2), minlength=m)
    th = 0.5 * np.arctan2(sx, cx)
    up = np.bincount(inv, weights=w * n_z, minlength=m) / W
    return np.column_stack([Qu, Qz]), W, np.column_stack([np.cos(th), np.sin(th)]), up


def _arc_quality(Q, W, cu, cz, rr, inl, L, frac):
    """가설 K 개를 한꺼번에: 가장 긴 연속 호의 각도와 그 안 넓이 합. inl: (K, M) bool."""
    K = len(cu)
    rows, cols = np.nonzero(inl)
    if len(rows) == 0:
        return np.zeros(K), np.zeros(K)
    ang = np.arctan2(Q[cols, 1] - cz[rows], Q[cols, 0] - cu[rows])
    b = (np.mod(ang, 2 * math.pi) / (2 * math.pi) * 36).astype(np.int64) % 36
    H = np.bincount(rows * 36 + b, weights=W[cols], minlength=K * 36).reshape(K, 36)
    exp_bin = rr * (2 * math.pi / 36) * L
    cov = H >= frac * exp_bin[:, None]
    cov2 = cov | (np.roll(cov, 1, 1) & np.roll(cov, -1, 1))
    D2 = np.concatenate([cov2, cov2], 1)
    Hd = np.concatenate([H, H], 1)
    run = np.zeros(D2.shape, np.int32)
    run[:, 0] = D2[:, 0]
    for j in range(1, 72):
        run[:, j] = (run[:, j - 1] + 1) * D2[:, j]
    run = np.minimum(run, 36)
    end = run.argmax(1)
    ln = run[np.arange(K), end]
    cs = np.concatenate([np.zeros((K, 1)), np.cumsum(Hd, 1)], 1)
    sup = cs[np.arange(K), end + 1] - cs[np.arange(K), end + 1 - ln]
    full = cov2.all(1)
    sup[full] = H[full].sum(1)
    return ln * 10.0, sup


def slab_circles(Q, W, N2, L, prm, rng, UP=None):
    """한 조각(2D)의 원들. Q: (M,2) [가로, 높이]."""
    M = len(Q)
    if M < 15:
        return []
    H = int(min(prm["n_hyp"], 3 * M))
    Qf = Q.astype(np.float32)
    seeds = rng.integers(0, M, H)
    rho = np.asarray(prm["scales"], np.float32)[rng.integers(0, len(prm["scales"]), H)]
    Ds = np.hypot(Qf[seeds, None, 0] - Qf[None, :, 0], Qf[seeds, None, 1] - Qf[None, :, 1])
    ring = (Ds >= 0.35 * rho[:, None]) & (Ds <= rho[:, None])
    del Ds
    R = rng.random((H, M), dtype=np.float32)
    R *= ring
    j = R.argmax(1)
    R[np.arange(H), j] = 0
    k = R.argmax(1)
    ok = ring[np.arange(H), j] & ring[np.arange(H), k]
    del R, ring
    ok &= np.hypot(Q[j, 0] - Q[k, 0], Q[j, 1] - Q[k, 1]) > 0.3 * rho
    ux, uz, r = _circle3(Q[seeds], Q[j], Q[k])
    ok &= np.isfinite(r) & (r >= prm["r_min"]) & (r <= prm["r_max"])
    if not ok.any():
        return []
    cu, cz, rr = ux[ok], uz[ok], r[ok]
    tau = _tau(rr, prm).astype(np.float32)
    dx = Qf[None, :, 0] - cu[:, None].astype(np.float32)
    dz = Qf[None, :, 1] - cz[:, None].astype(np.float32)
    dd = np.hypot(dx, dz) + np.float32(1e-9)
    inl = np.abs(dd - rr[:, None].astype(np.float32)) < tau[:, None]
    inl &= np.abs((dx * N2[None, :, 0].astype(np.float32) + dz * N2[None, :, 1].astype(np.float32)) / dd) >         _cos_min(rr)[:, None].astype(np.float32)
    if UP is not None:
        inl &= ~((UP[None, :] > 0.5) & (dz / dd < -0.3))
    del dx, dz, dd
    inlf = inl.astype(np.float32)
    alive = np.ones(M, bool)
    dead = np.zeros(len(rr), bool)
    found = []
    for _ in range(prm["max_tries"]):
        if len(found) >= prm["max_circles"]:
            break
        score = inlf @ (W * alive).astype(np.float32)
        score[dead] = -1
        top = np.argsort(-score)[:prm["top_k"]]
        top = top[score[top] > 0]
        if len(top) == 0:
            break
        span, sup = _arc_quality(Q, W, cu[top], cz[top], rr[top], inl[top] & alive[None, :], L, prm["bin_cover"])
        q = np.where(span >= 0.8 * prm["min_arc_deg"], sup, 0.0)
        if q.max() <= 0:
            dead[top] = True
            continue
        h = top[int(np.argmax(q))]
        c0, r0 = np.array([cu[h], cz[h]]), float(rr[h])
        t0 = float(_tau(r0, prm))
        m = alive & (np.abs(np.hypot(Q[:, 0] - c0[0], Q[:, 1] - c0[1]) - r0) < 3 * t0)
        fit = _fit_circle(Q[m], W[m], c0, r0, t0, r_lo=prm["r_min"] * 0.8, r_hi=prm["r_max"], N2=N2[m],
                          UP=None if UP is None else UP[m]) if m.sum() >= 5 else None
        ev = _evaluate_circle(Q, W, N2, alive, fit[0], fit[1], L, prm, inside_pts=(Q, W), UP=UP)             if fit is not None else dict(ok=False)
        near = (np.hypot(cu - c0[0], cz - c0[1]) < 0.4 * r0 + 0.005) & (np.abs(rr - r0) < 0.3 * r0 + 0.004)
        dead |= near
        dead[h] = True
        if ev.get("ok"):
            found.append(dict(u=float(ev["c"][0]), z=float(ev["c"][1]), r=float(ev["r"]), span=ev["span"],
                              support=ev["support"], density=ev["density"], rms=ev["rms"]))
            dI = np.hypot(Q[:, 0] - ev["c"][0], Q[:, 1] - ev["c"][1])
            alive &= ~(ev["inl"] | (dI < ev["r"] - ev["tau"]))
            dead |= (np.hypot(cu - ev["c"][0], cz - ev["c"][1]) < 0.4 * ev["r"] + 0.005)
    return found


# ═══════════════════════════════════════════ 5) 방향별 조각 → 이어 붙이기 ═══════════════════════════════════════════
def _frame(phi):
    d = np.array([math.cos(phi), math.sin(phi), 0.0])
    e = np.array([-math.sin(phi), math.cos(phi), 0.0])
    return d, e


def detect_direction(Pt, Nt, Wt, phi, prm, rng, log=None):
    d, e = _frame(phi)
    s = Pt @ d
    keep = np.abs(Nt @ d) < prm["normal_axis_max"]
    s_k, u_k, z_k = s[keep], (Pt @ e)[keep], Pt[keep, 2]
    nu_k, nz_k, w_k = (Nt @ e)[keep], Nt[keep, 2], Wt[keep]
    order = np.argsort(s_k)
    s_k, u_k, z_k, nu_k, nz_k, w_k = s_k[order], u_k[order], z_k[order], nu_k[order], nz_k[order], w_k[order]
    if len(s_k) < 50:
        return []
    L, step = prm["slab_len"], prm["slab_step"]
    s0, s1 = np.percentile(s_k, 0.2), np.percentile(s_k, 99.8)
    starts = np.arange(s0 - L / 2, s1, step)
    circles = []
    for kk, a in enumerate(starts):
        i0, i1 = np.searchsorted(s_k, [a, a + L])
        if i1 - i0 < 30:
            continue
        Q, W, N2, UP = _bin_slab(u_k[i0:i1], z_k[i0:i1], nu_k[i0:i1], nz_k[i0:i1], w_k[i0:i1], prm["bin"])
        if len(Q) > prm["max_bins"]:
            Q, W, N2, UP = _bin_slab(u_k[i0:i1], z_k[i0:i1], nu_k[i0:i1], nz_k[i0:i1], w_k[i0:i1],
                                     prm["bin"] * math.sqrt(len(Q) / prm["max_bins"]))
        for c in slab_circles(Q, W, N2, L, prm, rng, UP=UP):
            c.update(k=kk, s=float(a + L / 2))
            circles.append(c)
    tracks = link_circles(circles, prm)
    out = []
    for t in tracks:
        X = np.array([[c["s"], c["u"], c["z"]] for c in t])
        P3 = X[:, 0:1] * d + X[:, 1:2] * e + np.array([0, 0, 1.0]) * X[:, 2:3]
        out.append(dict(phi=phi, circles=t, centers=P3, r=float(np.median([c["r"] for c in t]))))
    if log:
        log(f"  dir {math.degrees(phi):5.1f}: {len(starts)} slabs, {len(circles)} circles, {len(out)} tracks")
    return out


def link_circles(circles, prm):
    step = prm["slab_step"]
    max_gap = int(round(prm["max_gap"] / step))
    by_k = {}
    for c in circles:
        by_k.setdefault(c["k"], []).append(c)
    tracks = []
    for k in sorted(by_k):
        used = set()
        for c in sorted(by_k[k], key=lambda c: -c["support"]):
            best, best_cost = None, 1e9
            for ti, t in enumerate(tracks):
                if ti in used:
                    continue
                last = t[-1]
                gap = k - last["k"]
                if gap < 1 or gap > max_gap + 1:
                    continue
                pu, pz = last["u"], last["z"]
                if len(t) >= 2:  # 선형 외삽
                    prev = t[-2]
                    ds = last["s"] - prev["s"]
                    if ds > 0:
                        pu += (last["u"] - prev["u"]) / ds * (c["s"] - last["s"])
                        pz += (last["z"] - prev["z"]) / ds * (c["s"] - last["s"])
                r = max(c["r"], last["r"])
                tol = max(0.02, 0.3 * r) + 0.01 * (gap - 1)
                tol_r = max(0.008, 0.3 * r)
                du, dz, dr = abs(c["u"] - pu), abs(c["z"] - pz), abs(c["r"] - last["r"])
                if du > tol or dz > tol or dr > tol_r:
                    continue
                cost = du / tol + dz / tol + dr / tol_r + 0.3 * (gap - 1)
                if cost < best_cost:
                    best, best_cost = ti, cost
            if best is None:
                tracks.append([c])
                used.add(len(tracks) - 1)
            else:
                tracks[best].append(c)
                used.add(best)
    good = []
    for t in tracks:
        if len(t) < prm["min_slabs"]:
            continue
        s = np.array([c["s"] for c in t])
        length = s.max() - s.min() + prm["slab_len"]
        if length < prm["min_len"]:
            continue
        r = np.array([c["r"] for c in t])
        rm = np.median(r)
        if 1.4826 * np.median(np.abs(r - rm)) / rm > prm["r_cv_max"]:
            continue
        u = np.array([c["u"] for c in t])
        z = np.array([c["z"] for c in t])
        A = np.column_stack([s, np.ones_like(s)])
        cu_ = np.linalg.lstsq(A, u, rcond=None)[0]
        cz_ = np.linalg.lstsq(A, z, rcond=None)[0]
        resid = np.sqrt(np.mean((u - A @ cu_) ** 2 + (z - A @ cz_) ** 2))
        if resid > max(0.015, 0.25 * rm):
            continue
        if abs(cz_[0]) > prm["max_slope"]:
            continue
        good.append(t)
    return good


# ═══════════════════════════════════════════ 6) 다듬기 ═══════════════════════════════════════════
def _axis_frame(dirv):
    z = np.array([0, 0, 1.0])
    e1 = np.cross(dirv, z)
    if np.linalg.norm(e1) < 1e-6:
        e1 = np.array([1.0, 0, 0])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(e1, dirv)
    e2 /= np.linalg.norm(e2)
    if e2[2] < 0:
        e1, e2 = -e1, -e2
    return e1, e2


def _robust_poly(t, y, w, deg):
    deg = min(deg, max(0, len(t) - 2))
    ww = w.copy()
    for _ in range(4):
        A = np.vander(t, deg + 1)
        coef = np.linalg.lstsq(A * ww[:, None], y * ww, rcond=None)[0]
        res = y - A @ coef
        s = 1.4826 * np.median(np.abs(res)) + 1e-4
        ww = w * np.where(np.abs(res) < 2.5 * s, 1.0, 2.5 * s / (np.abs(res) + 1e-12))
    return coef


def refine_track(tr, Pt, Nt, Wt, prm, rng):
    X = tr["centers"]
    r0 = tr["r"]
    p0 = X.mean(0)
    if len(X) >= 3:
        _, _, vt = np.linalg.svd(X - p0)
        dirv = vt[0]
    else:
        dirv = np.array([math.cos(tr["phi"]), math.sin(tr["phi"]), 0.0])
    d0 = np.array([math.cos(tr["phi"]), math.sin(tr["phi"]), 0.0])
    if dirv @ d0 < 0:
        dirv = -dirv
    if abs(dirv[2]) > 0.35:
        return None
    prev_ends = None
    for _pass in range(prm["ref_passes"]):
        # 축 둘레 점만 골라 둔다 (조각마다 전체 점을 훑지 않게). 구간이 자라면 다시 고른다.
        lo_b, hi_b = X.min(0) - (r0 + 0.7), X.max(0) + (r0 + 0.7)
        sub = np.flatnonzero(np.all((Pt >= lo_b) & (Pt <= hi_b), axis=1))
        PtS, NtS, WtS = Pt[sub], Nt[sub], Wt[sub]
        e1, e2 = _axis_frame(dirv)
        V = PtS - p0
        t = V @ dirv
        a, b = V @ e1, V @ e2
        rad = np.hypot(a, b)
        tau = float(_tau(r0, prm))
        band = max(3 * tau, 0.35 * r0) + 0.01
        tX = (X - p0) @ dirv
        ext = 0.6
        sel = (np.abs(rad - r0) < band) & (t > tX.min() - ext) & (t < tX.max() + ext) & \
              (np.abs(NtS @ dirv) < prm["normal_axis_max"])
        idx = np.flatnonzero(sel)
        if len(idx) < 30:
            return None
        ti, ai, bi = t[idx], a[idx], b[idx]
        L, step = prm["ref_slab"], prm["ref_step"]
        starts = np.arange(ti.min(), ti.max() - L * 0.5, step)
        rows = []
        inl_idx = []
        nb_idx = []
        ctx = np.flatnonzero((rad < r0 + band + 0.06) & (t > tX.min() - ext - L) & (t < tX.max() + ext + L))
        ctx = ctx[np.argsort(t[ctx])]
        t_ctx = t[ctx]
        for st in starts:
            m = (ti >= st) & (ti < st + L)
            if m.sum() < 12:
                rows.append(None)
                continue
            Q = np.column_stack([ai[m], bi[m]])
            W = WtS[idx[m]]
            nn = NtS[idx[m]]
            N2 = np.column_stack([nn @ e1, nn @ e2])
            N2 /= np.linalg.norm(N2, axis=1, keepdims=True) + 1e-12
            UPr = nn[:, 2]
            fit = _fit_circle(Q, W, np.zeros(2), r0, tau, iters=12, r_lo=0.6 * r0, r_hi=1.45 * r0, N2=N2, UP=UPr)
            if fit is None:
                rows.append(None)
                continue
            c, r = fit
            if np.hypot(*c) > band:
                rows.append(None)
                continue
            # 안쪽 비움·모서리 검사에는 조각 안 둘레 점 모두 (띠 바깥 포함)
            i0, i1 = np.searchsorted(t_ctx, [st, st + L])
            cs_ = ctx[i0:i1]
            Qall = np.column_stack([a[cs_], b[cs_]])
            ev = _evaluate_circle(Q, W, N2, np.ones(len(Q), bool), c, r, L, prm,
                                  inside_pts=(Qall, WtS[cs_]), UP=UPr)
            if not ev["ok"]:
                rows.append(None)
                continue
            rows.append(dict(t=st + L / 2, c=c, r=r, span=ev["span"], support=ev["support"], rms=ev["rms"],
                             density=ev["density"], Q=Q, W=W, N2=N2, UP=UPr))
            inl_idx.append(sub[idx[m][ev["inl"]]])
            dc = np.hypot(a[cs_] - c[0], b[cs_] - c[1])
            nb_m = (dc > r + 2 * tau + 0.005) & (dc < r + 2 * tau + 0.05)
            nb_idx.append(sub[cs_[nb_m]])
        valid = np.array([rw is not None for rw in rows])
        if valid.sum() < 2:
            return None
        # 가장 많이 받쳐 주는 연속 구간 (틈 ≤ max_gap)
        vk = np.flatnonzero(valid)
        max_gap_k = int(round(prm["max_gap"] / step))
        groups, cur = [], [vk[0]]
        for q in vk[1:]:
            if q - cur[-1] <= max_gap_k + 1:
                cur.append(q)
            else:
                groups.append(cur)
                cur = [q]
        groups.append(cur)
        grp = max(groups, key=lambda g_: sum(rows[q]["support"] for q in g_))
        R = [rows[q] for q in grp]
        tt = np.array([rw["t"] for rw in R])
        ca = np.array([rw["c"][0] for rw in R])
        cb = np.array([rw["c"][1] for rw in R])
        rr = np.array([rw["r"] for rw in R])
        wsup = np.array([rw["support"] for rw in R])
        # 축을 중심점으로 다시 잡는다
        C3 = p0 + tt[:, None] * dirv + ca[:, None] * e1 + cb[:, None] * e2
        if len(C3) >= 3:
            pm = (C3 * wsup[:, None]).sum(0) / wsup.sum()
            _, _, vt = np.linalg.svd((C3 - pm) * np.sqrt(wsup)[:, None])
            nd = vt[0] if vt[0] @ dirv > 0 else -vt[0]
        else:
            pm, nd = p0, dirv
        r0 = float(np.median(rr))
        X = C3
        p0 = pm
        if abs(nd[2]) > 0.35:
            return None
        ends = np.vstack([C3[0], C3[-1]])
        # 축과 끝을 새로 잡았으면 끝이 더 자라지 않을 때까지 되풀이 (관이 여러 조각 흔적으로 끊겨 찾혀도 끝까지 잇는다)
        if _pass >= 1 and prev_ends is not None and np.linalg.norm(ends - prev_ends, axis=1).max() < 0.03                 and abs(nd @ dirv) > 0.9995:
            break
        prev_ends = ends
        dirv = nd / np.linalg.norm(nd)
    t_lo = tt.min() - prm["ref_slab"] / 2
    t_hi = tt.max() + prm["ref_slab"] / 2
    length = float(t_hi - t_lo)
    n_span = int(round((tt.max() - tt.min()) / prm["ref_step"])) + 1
    coverage = len(R) / max(1, n_span)
    deg = 2 if length > 1.5 else 1
    w = np.sqrt(wsup)
    ka = _robust_poly(tt, ca, w, deg)
    kb = _robust_poly(tt, cb, w, deg)
    n = max(2, int(math.ceil(length / prm["centerline_step"])) + 1)
    ts = np.linspace(t_lo, t_hi, n)
    cl = p0 + ts[:, None] * dirv + np.polyval(ka, ts)[:, None] * e1 + np.polyval(kb, ts)[:, None] * e2
    fitres = np.sqrt(np.mean((ca - np.polyval(ka, tt)) ** 2 + (cb - np.polyval(kb, tt)) ** 2))
    inl = np.unique(np.concatenate(inl_idx)) if inl_idx else np.zeros(0, int)
    nbr = np.unique(np.concatenate(nb_idx)) if nb_idx else np.zeros(0, int)
    nbr = np.setdiff1d(nbr, inl)
    D = 2 * float(np.median(rr))
    snap = _nominal_snap(R, D, float(_tau(D / 2, prm)))
    return dict(centerline=cl, dir=dirv, r=D / 2, diameter=D, diameter_rms=float(np.sqrt(np.mean((2 * rr - D) ** 2))),
                snap=snap,
                arc=float(np.median([rw["span"] for rw in R])), rms=float(np.median([rw["rms"] for rw in R])),
                length=length, coverage=float(min(1.0, coverage)), support=float(wsup.sum()), n_slabs=len(R),
                center_fit_rms=float(fitres), inliers=inl, neighbours=nbr, kind_src="circle", phi=tr["phi"])


def _nominal_snap(R, D_fit, tau):
    """공칭경 스냅: 외경 후보(NOMINAL_OD)마다 반지름을 고정해 조각별 중심만 다시 맞추고, 잘린 제곱 잔차가 가장 작은 외경.
    → dict(nominal_mm, od_mm, family, margin) 또는 None. margin = (둘째 비용 − 최소 비용) / 최소 비용."""
    cands = {}
    for fam, tab in NOMINAL_OD.items():
        for dn, od in tab.items():
            if abs(od / 1000.0 - D_fit) <= max(0.25 * D_fit, 0.012):
                cands.setdefault(od, []).append((dn, fam))
    if not cands or not R:
        return None
    cap = (2 * tau) ** 2
    costs = {}
    for od in sorted(cands):
        rc = od / 2000.0
        tot = wsum = 0.0
        for rw in R:
            Q, W = rw["Q"], rw["W"]
            fit = _fit_circle(Q, W, rw["c"], rc, tau, iters=8, r_lo=rc, r_hi=rc, N2=rw["N2"], UP=rw["UP"])
            wsum += W.sum()
            if fit is None:
                tot += cap * W.sum()
                continue
            c = fit[0]
            dv = Q - c
            d = np.hypot(dv[:, 0], dv[:, 1]) + 1e-12
            ok = _radial_ok(dv[:, 0], dv[:, 1], d, rw["N2"], rw["UP"], rc)
            e2 = np.where(ok, np.minimum((d - rc) ** 2, cap), cap)
            tot += float((W * e2).sum())
        costs[od] = tot / max(wsum, 1e-12)
    order = sorted(costs, key=costs.get)
    best = order[0]
    margin = (costs[order[1]] - costs[best]) / max(costs[best], 1e-12) if len(order) > 1 else 1.0
    dn, fam = sorted(cands[best])[0]
    return dict(nominal_mm=int(dn), od_mm=float(best), family="/".join(sorted({f for _, f in cands[best]})),
                margin=round(float(margin), 3))


# ═══════════════════════════════════════════ 7) 케이블·다발 (솟은 띠) ═══════════════════════════════════════════
def _nan_smooth(Z, sigma):
    m = np.isfinite(Z).astype(np.float32)
    Z0 = np.where(m > 0, Z, 0).astype(np.float32)
    k = int(2 * round(2 * sigma) + 1)
    a = cv2.GaussianBlur(Z0, (k, k), sigma)
    b = cv2.GaussianBlur(m, (k, k), sigma)
    out = np.where(b > 0.2, a / np.maximum(b, 1e-6), np.nan)
    return out


def detect_linear_small(Pt, Nt, Wt, excl, gt, prm, log):
    """관이 아닌 가는 선형 물체(바닥 위). → 후보 목록."""
    keep = ~excl & (Nt[:, 2] > 0.35)
    P = Pt[keep]
    if len(P) < 200:
        return []
    cell = prm["lin_cell"]
    x0, y0 = P[:, 0].min() - 0.3, P[:, 1].min() - 0.3
    nx = int((P[:, 0].max() + 0.3 - x0) / cell) + 1
    ny = int((P[:, 1].max() + 0.3 - y0) / cell) + 1
    ix = ((P[:, 0] - x0) / cell).astype(int)
    iy = ((P[:, 1] - y0) / cell).astype(int)
    top, cnt = _cell_quantile(iy * nx + ix, P[:, 2], 0.8, nx * ny)
    top = top.reshape(ny, nx)
    Zs = _nan_smooth(top, 1.0)
    big = np.nanmax(Zs) + 1.0 if np.isfinite(Zs).any() else 1.0
    Zf = np.where(np.isfinite(Zs), Zs, big).astype(np.float32)
    ks = int(round(prm["lin_open"] / cell)) | 1
    floor = cv2.dilate(cv2.erode(Zf, np.ones((ks, ks), np.uint8)), np.ones((ks, ks), np.uint8))
    prot = np.where(np.isfinite(Zs), Zs - floor, 0)
    obj = (prot > prm["lin_min_h"]) & (prot < prm["lin_max_h"])
    obj = cv2.morphologyEx(obj.astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    obj = cv2.morphologyEx(obj, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(obj, connectivity=8)
    cands = []
    ground = gt["ground"]
    for i in range(1, n):
        area = stats[i, cv2.CC_STAT_AREA] * cell * cell
        if area < prm["lin_min_len"] * 0.012:
            continue
        yy, xx = np.nonzero(lab == i)
        M = np.column_stack([x0 + (xx + 0.5) * cell, y0 + (yy + 0.5) * cell])
        cen = M.mean(0)
        ev, evec = np.linalg.eigh(np.cov((M - cen).T))
        ax = evec[:, 1]
        mn = evec[:, 0]
        pa, pb = (M - cen) @ ax, (M - cen) @ mn
        Lc = np.percentile(pa, 99) - np.percentile(pa, 1)
        Wc = area / max(Lc, 1e-6)
        if Lc < prm["lin_min_len"] or Wc > prm["lin_max_w"] or Lc / max(Wc, 1e-3) < 4:
            continue
        # 중심선: 0.1 m 칸마다 가로 중앙값
        edges = np.arange(pa.min(), pa.max() + 0.1, 0.1)
        cl = []
        for e0 in edges[:-1]:
            mm = (pa >= e0) & (pa < e0 + 0.1)
            if mm.sum() >= 3:
                cl.append((e0 + 0.05, float(np.median(pb[mm]))))
        if len(cl) < 3:
            continue
        cl = np.array(cl)
        # 단면 분석 (원 점 사용)
        Va = (Pt[:, :2] - cen) @ ax
        Vb = (Pt[:, :2] - cen) @ mn
        fx = np.clip(((Pt[:, 0] - x0) / cell).astype(int), 0, nx - 1)
        fy = np.clip(((Pt[:, 1] - y0) / cell).astype(int), 0, ny - 1)
        fl = floor[fy, fx]
        peaks_l, heights, widths, tops, sec_xy, spacings = [], [], [], [], [], []
        for (ta, tb) in cl:
            m = (np.abs(Va - ta) < 0.05) & (np.abs(Vb - tb) < Wc / 2 + 0.04) & ~excl & (fl < big - 0.5)
            if m.sum() < 15:
                continue
            o = Vb[m] - tb
            h = Pt[m, 2] - fl[m]
            ob = np.floor((o + 0.2) / 0.003).astype(int)
            prof = np.full(ob.max() + 1, np.nan)
            for q in np.unique(ob):
                hh = h[ob == q]
                if len(hh) >= 2:
                    prof[q] = np.percentile(hh, 75)
            pv = np.where(np.isfinite(prof), prof, 0)
            pv = np.convolve(pv, [0.25, 0.5, 0.25], mode="same")
            above = pv > 0.005
            if not above.any():
                continue
            # 가장 긴 연속 구간 = 폭
            runs, cur, st = [], 0, 0
            for q, v in enumerate(above):
                if v:
                    if cur == 0:
                        st = q
                    cur += 1
                else:
                    if cur:
                        runs.append((cur, st))
                    cur = 0
            if cur:
                runs.append((cur, st))
            rl, rs = max(runs)
            seg = pv[rs:rs + rl]
            widths.append(rl * 0.003)
            hmax = float(seg.max())
            heights.append(hmax)
            fl_c = float(np.median(fl[m][np.abs(o) < 0.02])) if (np.abs(o) < 0.02).any() else float(np.median(fl[m]))
            tops.append(fl_c + hmax)
            sec_xy.append(cen + ta * ax + tb * mn)
            # 봉우리: 양쪽 골보다 max(3 mm, 0.2·높이) 넘게 솟은 것 (평평한 판자는 1 개)
            prom = max(0.003, 0.2 * hmax, 0.5 * prm.get("_sigma", 0.0))
            pk = []
            for q in range(1, len(seg) - 1):
                if seg[q] >= seg[q - 1] and seg[q] > seg[q + 1] and seg[q] > 0.5 * hmax:
                    lo_l = seg[max(0, q - 8):q].min()
                    lo_r = seg[q + 1:q + 9].min()
                    if seg[q] - lo_l >= prom and seg[q] - lo_r >= prom:
                        pk.append(q)
            npk = len(pk)
            peaks_l.append(max(1, npk))
            if npk >= 2:
                spacings.append(float(np.median(np.diff(pk))) * 0.003)
        if len(heights) < 3:
            continue
        # 튀는 단면(벽 끝·바닥 열림 실패)은 뺀다
        hv = np.array(heights)
        mad = 1.4826 * np.median(np.abs(hv - np.median(hv))) + 0.002
        good = np.abs(hv - np.median(hv)) < 3 * mad
        if good.sum() < 3:
            continue
        heights = list(hv[good])
        widths = [w_ for w_, g_ in zip(widths, good) if g_]
        tops = [t_ for t_, g_ in zip(tops, good) if g_]
        sec_xy = [q_ for q_, g_ in zip(sec_xy, good) if g_]
        peaks_l = [k_ for k_, g_ in zip(peaks_l, good) if g_]
        hmed, wmed = float(np.median(heights)), float(np.median(widths))
        npk = int(round(np.median(peaks_l)))
        multi = float(np.mean(np.array(peaks_l) >= 2))
        pts2 = cen + cl[:, 0:1] * ax + cl[:, 1:2] * mn
        topz = np.array(tops)
        cands.append(dict(xy=pts2, top=float(np.median(topz)), tops=topz, sec_xy=np.array(sec_xy), h=hmed, width=wmed,
                          peaks=npk, multi=multi, length=float(Lc),
                          w_cv=float(1.4826 * np.median(np.abs(np.array(widths) - wmed)) / max(wmed, 1e-3)),
                          spacing=float(np.median(spacings)) if spacings else hmed,
                          n_sec=len(heights), h_cv=float(1.4826 * np.median(np.abs(np.array(heights) - hmed)) / max(hmed, 1e-3)),
                          axis=ax, cen=cen, Wc=Wc))
    log(f"linear small objects: {len(cands)} candidates")
    return cands


# ═══════════════════════════════════════════ 8) 색 → 종류 ═══════════════════════════════════════════
def classify_color(rgb):
    """rgb: (n,3) uint8. → dict(color_rgb, color_name, class, candidates, class_confidence)."""
    if len(rgb) == 0:
        return dict(color_rgb=[0, 0, 0], color_name="none", cls="unknown", candidates=[], class_conf=0.0)
    hsv = cv2.cvtColor(rgb.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_RGB2HSV_FULL).reshape(-1, 3).astype(float)
    hdeg = hsv[:, 0] * 360.0 / 256.0
    s, v = hsv[:, 1] / 255.0, hsv[:, 2] / 255.0
    lit = v >= 0.12
    if lit.sum() < 0.3 * len(rgb):
        lit = np.ones(len(rgb), bool)
    smin_all = min(COLOR_TABLE[n]["s_min"] for n in CHROMATIC_ORDER)
    chrom = lit & (s >= smin_all)

    def in_hue(hh, lo, hi):
        return (hh >= lo) & (hh < hi) if lo <= hi else (hh >= lo) | (hh < hi)

    best = None
    if chrom.sum() >= 0.3 * lit.sum():
        for name in CHROMATIC_ORDER:
            t = COLOR_TABLE[name]
            m = chrom & in_hue(hdeg, *t["hue"]) & (s >= t["s_min"]) & (v >= t["v_min"])
            frac = m.sum() / max(1, lit.sum())
            if best is None or frac > best[1]:
                best = (name, frac, m)
    if best is not None and best[1] >= 0.25:
        name, frac, m = best
        med = np.median(rgb[m], axis=0)
        sat = float(np.median(s[m]))
        t = COLOR_TABLE[name]
        conf = t["class_conf"] * min(1.0, frac / 0.6) * min(1.0, 0.5 + sat)
    else:
        med = np.median(rgb[lit], axis=0)
        vv = float(np.median(v[lit]))
        name = next(n for n in ACHROMATIC_ORDER if vv < COLOR_TABLE[n]["v_max"])
        t = COLOR_TABLE[name]
        conf = t["class_conf"]
    return dict(color_rgb=[int(round(x)) for x in med], color_name=name, cls=t["class"], candidates=list(t["candidates"]),
                class_conf=round(float(conf), 2))


def _soil_likeness(Ct, inl, nbr):
    """(관 표면 중앙값 색 ↔ 이웃 중앙값 색 ΔE, 이웃 점 가운데 관 색과 비슷한 비율)."""
    if len(inl) < 20 or len(nbr) < 20:
        return 99.0, 0.0
    lab_in = _lab(np.median(Ct[inl], axis=0))
    labs = cv2.cvtColor(Ct[nbr].reshape(-1, 1, 3), cv2.COLOR_RGB2LAB).reshape(-1, 3).astype(float)
    dE_med = float(np.linalg.norm(lab_in - np.median(labs, axis=0)))
    sim = float((np.linalg.norm(labs - lab_in, axis=1) < 15).mean())
    return dE_med, sim


def _lab(rgb):
    return cv2.cvtColor(np.array(rgb, np.uint8).reshape(1, 1, 3), cv2.COLOR_RGB2LAB).reshape(3).astype(float)


# ═══════════════════════════════════════════ 9) 본체 ═══════════════════════════════════════════
def _polyline_dist(Pq, PL):
    """점들 → 꺾은선까지 최소 거리 (3D)."""
    best = np.full(len(Pq), np.inf)
    for a, b in zip(PL[:-1], PL[1:]):
        ab = b - a
        L2 = ab @ ab
        t = np.clip(((Pq - a) @ ab) / max(L2, 1e-12), 0, 1)
        d = np.linalg.norm(Pq - (a + t[:, None] * ab), axis=1)
        best = np.minimum(best, d)
    return best


def _near_polyline(P, PL, radius):
    """P 가운데 꺾은선 PL 에서 radius 안의 점 (상자로 먼저 거른다)."""
    lo = PL.min(0) - radius
    hi = PL.max(0) + radius
    box = np.all((P >= lo) & (P <= hi), axis=1)
    out = np.zeros(len(P), bool)
    idx = np.flatnonzero(box)
    if len(idx):
        out[idx] = _polyline_dist(P[idx], PL) < radius
    return out


def _end_state(endp, out_dir, r, top_z, contour, gt, prm):
    """끝점이 벽에 닿는지(wall), 흙으로 들어가는지(buried), 굴착 안에서 끊기는지(free)."""
    dist_in = cv2.pointPolygonTest(contour, (float(endp[0]), float(endp[1])), True)
    if dist_in < max(0.15, r + 0.10):
        return "wall"
    g, lo = gt["grid"], gt["lo"]
    hits, higher = 0, 0
    for lam in (0.08, 0.15, 0.25):
        q = endp[:2] + out_dir[:2] * lam
        ix, iy = int((q[0] - g.x0) / g.cell), int((q[1] - g.y0) / g.cell)
        if 0 <= ix < g.nx and 0 <= iy < g.ny and np.isfinite(lo[iy, ix]):
            hits += 1
            if lo[iy, ix] >= top_z - 0.02:
                higher += 1
    if hits and higher / hits >= 0.6:
        return "buried"
    if hits == 0:
        return "unseen"
    return "free"


def _geom_conf(p, prm):
    """원통 맞춤 신뢰도: 보이는 호, 잔차, 길이, 조각 덮임, 지름 일관성의 기하 평균."""
    D = p["diameter"]
    tau = float(_tau(p["r"], prm))
    f_arc = np.clip((p["arc"] - 60) / 120, 0.1, 1)
    f_rms = np.clip(1.4 - p["rms"] / (tau * 0.8), 0.1, 1)
    f_len = np.clip(p["length"] / 0.8, 0.1, 1)
    f_cov = np.clip(p["coverage"], 0.1, 1)
    f_rc = np.clip(1 - (p["diameter_rms"] / max(D, 1e-3)) / 0.25, 0.1, 1)
    return float((f_arc * f_rms * f_len * f_cov * f_rc) ** 0.2)


STATION_PRIORITY = {"end": 4, "cross": 3, "bend": 2, "change": 1, "regular": 0}


def _resample_polyline(X, step):
    seg = np.linalg.norm(np.diff(X, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    n = max(2, int(math.ceil(s[-1] / step)) + 1)
    ss = np.linspace(0, s[-1], n)
    return np.column_stack([np.interp(ss, s, X[:, k]) for k in range(3)]), ss


def _add_stations_clearances(res, utils, origin, bend_deg=12.0, max_spacing=20.0, merge_m=0.15):
    """v0.2 stations[] (끝점·정규 ≤ 20 m·꺾임 ≥ 12°·평면 교차) 와 clearances[] (관 겉면 사이 3D 최소 거리).
    stations[].xyz_utm = 관 윗면 점(토피를 잰 곳), axis_utm = 축 점. station_m = 그 관 중심선 첫 점(서→동)부터 3D 거리."""
    by_id = {u["id"]: u for u in utils}
    marks = {u["id"]: [] for u in utils}          # (s, kind)
    # 평면 교차 (두 관 모두에 측점)
    ids = [u["id"] for u in utils]
    for i in range(len(ids)):
        A = by_id[ids[i]]["centerline"]
        sA = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(A, axis=0), axis=1))])
        for j in range(i + 1, len(ids)):
            B = by_id[ids[j]]["centerline"]
            sB = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(B, axis=0), axis=1))])
            for a in range(len(A) - 1):
                p, r_ = A[a, :2], A[a + 1, :2] - A[a, :2]
                for b in range(len(B) - 1):
                    q, s_ = B[b, :2], B[b + 1, :2] - B[b, :2]
                    den = r_[0] * s_[1] - r_[1] * s_[0]
                    if abs(den) < 1e-12:
                        continue
                    t = ((q[0] - p[0]) * s_[1] - (q[1] - p[1]) * s_[0]) / den
                    u = ((q[0] - p[0]) * r_[1] - (q[1] - p[1]) * r_[0]) / den
                    if 0 <= t <= 1 and 0 <= u <= 1:
                        marks[ids[i]].append((sA[a] + t * (sA[a + 1] - sA[a]), "cross"))
                        marks[ids[j]].append((sB[b] + u * (sB[b + 1] - sB[b]), "cross"))
    stations = []
    for u in utils:
        X = u["centerline"]
        dep = np.asarray(u["top_depth"], float)
        s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(X, axis=0), axis=1))])
        L = float(s[-1])
        mk = list(marks[u["id"]]) + [(0.0, "end"), (L, "end")]
        n = max(2 if L >= 1.0 else 1, int(math.ceil(L / max_spacing)))
        mk += [(L * k / n, "regular") for k in range(1, n)]
        for k in range(1, len(X) - 1):            # 꺾임: 앞뒤 3 점 창의 방향 차
            a0, a1 = X[max(0, k - 3)], X[k]
            b1 = X[min(len(X) - 1, k + 3)]
            v1, v2 = a1 - a0, b1 - a1
            if np.linalg.norm(v1) > 1e-6 and np.linalg.norm(v2) > 1e-6:
                ang = math.degrees(math.acos(np.clip(v1 @ v2 / np.linalg.norm(v1) / np.linalg.norm(v2), -1, 1)))
                if ang >= bend_deg:
                    mk.append((float(s[k]), "bend"))
        mk.sort()
        merged = []
        for sv, kd in mk:
            if merged and sv - merged[-1][0] < merge_m:
                if STATION_PRIORITY[kd] > STATION_PRIORITY[merged[-1][1]]:
                    merged[-1] = (merged[-1][0] if merged[-1][1] == "end" else sv, kd)
                continue
            merged.append((sv, kd))
        r = u["diameter_mm"] / 2000.0
        for sv, kd in merged:
            ax = np.array([np.interp(sv, s, X[:, q]) for q in range(3)])
            top = ax + np.array([0, 0, r])
            stations.append(dict(station_m=round(float(sv), 3), utility_id=u["id"], kind=kd,
                                 xyz_utm=[round(float(v), 3) for v in top + origin],
                                 axis_utm=[round(float(v), 3) for v in ax + origin],
                                 top_depth_m=round(float(np.interp(sv, s, dep)), 3)))
    res["stations"] = stations
    # 이격: 축 사이 최소 거리 − 두 반지름 (다발은 폭/2 를 반지름으로: 보수적)
    clr = []
    for i in range(len(utils)):
        for j in range(i + 1, len(utils)):
            ua, ub = utils[i], utils[j]
            A, _ = _resample_polyline(ua["centerline"], 0.02)
            B, _ = _resample_polyline(ub["centerline"], 0.02)
            D = np.linalg.norm(A[:, None, :] - B[None, :, :], axis=2)
            k = np.unravel_index(int(np.argmin(D)), D.shape)
            pa, pb = A[k[0]], B[k[1]]
            ra = (ua.get("width_mm") or ua["diameter_mm"]) / 2000.0 if ua["kind"] == "bundle" else ua["diameter_mm"] / 2000.0
            rb = (ub.get("width_mm") or ub["diameter_mm"]) / 2000.0 if ub["kind"] == "bundle" else ub["diameter_mm"] / 2000.0
            dv = pb - pa
            dn = float(np.linalg.norm(dv))
            unit = dv / dn if dn > 1e-9 else np.array([0, 0, 1.0])
            sa, sb = pa + ra * unit, pb - rb * unit
            clr.append(dict(a=ua["id"], b=ub["id"], min_mm=int(round((dn - ra - rb) * 1000)),
                            at_utm=[round(float(v), 3) for v in (sa + sb) / 2 + origin],
                            a_utm=[round(float(v), 3) for v in sa + origin], b_utm=[round(float(v), 3) for v in sb + origin],
                            axis_mm=int(round(dn * 1000))))
    clr.sort(key=lambda c: c["min_mm"])
    res["clearances"] = clr


def photo_remeasure_targets(rec, step=0.25, georef=None):
    """4K 사진 재측정 연결 지점: 관 하나(utilities.json 의 utility 레코드)의 축을 따라 step m 마다
    축 점·축 방향·수평 직각·연직 위·예상 지름을 낸다. 사진 쪽은 이 점을 투영해 축에 직각인 폭(가장자리 사이)을 잰다.
    georef 가 있으면 ARKit 로컬 좌표(xyz_local, 법선류는 회전만)도 붙인다. → list[dict]"""
    X = np.asarray(rec["centerline"], float)
    if len(X) < 2:
        return []
    Xs, ss = _resample_polyline(X, step)
    out = []
    for i, (p, sv) in enumerate(zip(Xs, ss)):
        a, b = Xs[max(0, i - 1)], Xs[min(len(Xs) - 1, i + 1)]
        t = (b - a) / (np.linalg.norm(b - a) + 1e-12)
        h = np.cross([0, 0, 1.0], t)
        h = h / (np.linalg.norm(h) + 1e-12)
        up = np.cross(t, h)
        d = dict(utility_id=rec.get("id"), station_m=round(float(sv), 3), axis_utm=[round(float(v), 3) for v in p],
                 tangent=[round(float(v), 4) for v in t], perp_h=[round(float(v), 4) for v in h],
                 up=[round(float(v), 4) for v in up], diameter_mm=rec.get("diameter_mm"), kind=rec.get("kind"))
        if georef is not None:
            d["axis_local"] = [round(float(v), 4) for v in utm_to_arkit(p[None], georef)[0]]
            V = utm_to_arkit(np.vstack([t, h, up]), georef, vectors=True)
            d["tangent_local"], d["perp_h_local"], d["up_local"] = [[round(float(v), 4) for v in r] for r in V]
        out.append(d)
    return out


def utm_to_arkit(X, gr, vectors=False):
    """arkit_to_utm 의 역. X: (n,3) UTM(E, N, H) → ARKit 로컬 (x, y, z), Y 위. vectors=True 면 회전만."""
    X = np.asarray(X, float)
    if vectors:
        e, n, h = X[:, 0], X[:, 1], X[:, 2]
    else:
        from pyproj import Transformer
        tf = Transformer.from_crs("EPSG:4326", "EPSG:32652", always_xy=True)
        e0, n0 = tf.transform(gr["lon"], gr["lat"])
        e, n, h = X[:, 0] - e0, X[:, 1] - n0, X[:, 2] - gr["elev"]
    th = math.radians(gr["heading"])
    c, s = math.cos(th), math.sin(th)
    return np.column_stack([e * c - n * s, h, -e * s - n * c])


def _add_local(res, utils, ground, geo, origin, gr):
    """v0.2 로컬(ARKit, Y 위) 필드: local, centerline_local, ground_local_z, outline_local, ground_plane_local,
    stations[].xyz_local/axis_local, clearances[].at_local."""
    def loc(L):
        return [[round(float(v), 4) for v in p] for p in utm_to_arkit(np.asarray(L, float), gr)]
    res["local"] = {"frame": "arkit", "up": "+Y", "units": "m",
                    "glb": f"{res['job_id']}.glb" if res.get("job_id") else ""}
    for rec, u in zip(res["utilities"], utils):
        rec["centerline_local"] = loc(rec["centerline"])
        cl = np.asarray(rec["centerline"], float)
        gz = ground.z(cl[:, 0] - origin[0], cl[:, 1] - origin[1]) + origin[2] - gr["elev"]
        rec["ground_local_z"] = [round(float(v), 4) for v in gz]
    tr = res.get("trench")
    if tr:
        tr["outline_local"] = loc(tr["outline"])
        a, b, _ = ground.coef
        cx, cy = geo["center"]
        nu = np.array([-a, -b, 1.0])
        nu /= np.linalg.norm(nu)
        p_utm = np.array([[cx + origin[0], cy + origin[1], float(ground.z(cx, cy)) + origin[2]]])
        nl = utm_to_arkit(nu[None], gr, vectors=True)[0]
        pl = utm_to_arkit(p_utm, gr)[0]
        tr["ground_plane_local"] = {"normal": [round(float(v), 6) for v in nl], "d": round(float(-nl @ pl), 4)}
    for st in res.get("stations", []):
        st["xyz_local"] = loc([st["xyz_utm"]])[0]
        st["axis_local"] = loc([st["axis_utm"]])[0]
    for c in res.get("clearances", []):
        c["at_local"] = loc([c["at_utm"]])[0]


def _kind_for(cls, D):
    if cls in ("power", "telecom"):
        return "cable" if D < 0.04 else "conduit"
    return "cable" if D < 0.035 else "pipe"


def extract(points, colors=None, normals=None, params=None, log=print, job_id="", debug_png=None, source="las",
            georef=None):
    """points: (N,3) UTM(EPSG:32652) m, Z 위. colors: (N,3) uint8 (또는 0–1 float). normals: (N,3) 또는 None.
    georef: dict(lon, lat, elev, heading) 이면 v0.2 로컬(ARKit) 필드도 쓴다.
    → utilities.json dict (계약 §2, v0.2) + 몇 가지 덧붙인 항목."""
    t0 = time.time()
    log = _ascii_log(log)
    prm = dict(DEFAULTS)
    if params:
        prm.update(params)
    rng = np.random.default_rng(prm["seed"])
    P = np.asarray(points, np.float64)
    if colors is None:
        C = np.full((len(P), 3), 128, np.uint8)
    else:
        C = np.asarray(colors)
        C = np.clip(C * 255 + 0.5, 0, 255).astype(np.uint8) if C.dtype.kind == "f" and C.max() <= 1.0 else C.astype(np.uint8)
    origin = np.array([math.floor(np.median(P[:, 0])), math.floor(np.median(P[:, 1])), 0.0])
    PL = P - origin
    res = dict(version=VERSION, contract="0.2", job_id=job_id or "", crs="EPSG:32652", units="m", up="+Z",
               centerline_ref="axis", ground=None, trench=None, utilities=[], stations=[], clearances=[],
               quality=dict(points_used=0, trench_coverage_pct=0, warnings=[]), seconds=0)
    if georef is not None:
        res["local"] = {"frame": "arkit", "up": "+Y", "units": "m", "glb": f"{job_id}.glb" if job_id else ""}
    warnings = res["quality"]["warnings"]
    log(f"points: {len(P)} ({source}), origin {origin[0]:.0f} {origin[1]:.0f}")

    gt = find_ground_trench(PL, prm, log, rng, Nrm=None if normals is None else np.asarray(normals, np.float64))
    warnings.extend(gt["warnings"])
    ground = gt.get("ground")

    def to_utm(X):
        X = np.asarray(X, float) + origin
        return [[round(float(x), 3), round(float(y), 3), round(float(z), 3)] for x, y, z in X]

    if ground is not None:
        cxy = PL[:, :2].mean(0)
        res["ground"] = dict(method=ground.method, z_ref=round(float(ground.z(cxy[0], cxy[1])), 3),
                             rms_mm=round(float(gt.get("rim_rms", 0.0)) * 1000, 1),
                             slope_deg=round(ground.slope_deg(), 2))
    if gt.get("mask") is None:
        if "no_trench" not in warnings:
            warnings.append("no_trench")
        res["seconds"] = round(time.time() - t0, 1)
        log("no trench found")
        if debug_png:
            try:
                render_debug(debug_png, PL, C, gt, None, [], prm)
            except Exception as e:  # 그림 실패는 결과를 막지 않는다
                log(f"debug render failed: {e}")
        return res

    geo = trench_geometry(gt)
    cen = geo["center"]
    res["ground"]["z_ref"] = round(float(ground.z(cen[0], cen[1])), 3)
    res["ground"]["slope_deg"] = round(ground.slope_deg(cen[0], cen[1]), 2)
    log(f"trench: {geo['length']:.2f} x {geo['width']:.2f} m, ground {ground.method} rms {gt.get('rim_rms', 0) * 1000:.1f} mm")

    Nrm = None if normals is None else np.asarray(normals, np.float64)
    Pt, Ct, Nt, Wt = trench_points(PL, C, Nrm, gt, prm, log)
    res["quality"]["points_used"] = int(len(Pt))
    # 잡음에 맞춰 원 정상치 폭·케이블 문턱을 넓힌다 (사용자가 params 로 준 값은 그대로)
    sig = _noise_sigma(Pt, Nt)
    res["quality"]["noise_mm"] = round(sig * 1000, 1)
    given = set((params or {}).keys())
    if "tau_min" not in given:
        prm["tau_min"] = max(prm["tau_min"], 1.3 * sig)
    if "tau_max" not in given:
        prm["tau_max"] = max(prm["tau_max"], 2.0 * sig)
    if "lin_min_h" not in given:
        prm["lin_min_h"] = max(prm["lin_min_h"], 1.6 * sig)
    prm["_sigma"] = sig
    log(f"noise ~{sig * 1000:.1f} mm -> tau {prm['tau_min'] * 1000:.1f}-{prm['tau_max'] * 1000:.1f} mm, "
        f"cable ridge >= {prm['lin_min_h'] * 1000:.1f} mm")
    if sig > 0.007:
        warnings.append("high_noise")

    # ── 관 (원통) ──
    axis_phi = math.atan2(geo["axis"][1], geo["axis"][0])
    dirs, _ = candidate_directions(Pt, axis_phi, prm, log)
    # 방향마다 따로 (numpy 큰 연산은 GIL 을 풀어 스레드로 겹친다). 방향마다 씨앗을 따로 둬 결과가 실행 순서와 무관하다.
    from concurrent.futures import ThreadPoolExecutor
    nthreads = max(1, min(len(dirs), prm["threads"] or min(4, max(1, (os.cpu_count() or 2) // 2))))
    seeds = [prm["seed"] * 1000 + 17 * i + 1 for i in range(len(dirs))]
    if nthreads > 1:
        with ThreadPoolExecutor(nthreads) as ex:
            parts = list(ex.map(lambda a: detect_direction(Pt, Nt, Wt, a[0], prm, np.random.default_rng(a[1]), log),
                                zip(dirs, seeds)))
    else:
        parts = [detect_direction(Pt, Nt, Wt, phi, prm, np.random.default_rng(sd), log) for phi, sd in zip(dirs, seeds)]
    tracks = [t for part in parts for t in part]
    log(f"tracks: {len(tracks)}")
    cands = []
    for tr in tracks:
        rf = refine_track(tr, Pt, Nt, Wt, prm, rng)
        if rf is None or rf["length"] < prm["min_len"]:
            continue
        cands.append(rf)
    for c in cands:
        c["quality"] = _geom_conf(c, prm) * math.sqrt(c["support"])
    cands.sort(key=lambda c: -c["quality"])
    pipes = []
    for c in cands:
        dup = False
        for p in pipes:
            if len(c["inliers"]) and len(p["inliers"]):
                shared = np.isin(c["inliers"], p["inliers"], assume_unique=True).mean()
                if shared > 0.3:
                    dup = True
                    break
            dd = _polyline_dist(c["centerline"], p["centerline"])
            tol = 0.5 * max(c["r"], p["r"]) + 0.02
            if (dd < tol).mean() >= 0.5 and abs(c["diameter"] - p["diameter"]) < 0.35 * max(c["diameter"], p["diameter"]) + 0.01:
                dup = True
                break
        if not dup:
            pipes.append(c)
    log(f"pipes after merge: {len(pipes)} (from {len(cands)} refined)")

    # 공구·모서리 걸러 내기
    kept, rejected = [], []
    for p in pipes:
        cl = p["centerline"]
        topz = cl[:, 2] + p["r"] * math.sqrt(max(0.0, 1 - p["dir"][2] ** 2))
        depth = ground.z(cl[:, 0], cl[:, 1]) - topz
        p["depth"] = depth
        ends = []
        for endp, od, tz in ((cl[0], -p["dir"], topz[0]), (cl[-1], p["dir"], topz[-1])):
            ends.append(_end_state(endp, od, p["r"], tz, geo["contour"], gt, prm))
        p["ends"] = ends
        near_edge = np.array([cv2.pointPolygonTest(geo["contour"], (float(x), float(y)), True) for x, y in cl[:, :2]])
        if np.mean(depth) < prm["rim_edge_depth"] and np.mean(near_edge < p["r"] + 0.08) > 0.6:
            rejected.append(("rim_edge", p))
            continue
        if ends.count("free") == 2 and p["length"] < prm["free_end_max_len"]:
            rejected.append(("free_object", p))
            continue
        p["contrast"], p["soil_like"] = _soil_likeness(Ct, p["inliers"], p["neighbours"])
        if p["arc"] < prm["soil_arc_max"] and (p["contrast"] < prm["min_contrast"] or p["soil_like"] >= prm["soil_like_max"]):
            rejected.append(("soil_arc", p))
            continue
        kept.append(p)
    for why, p in rejected:
        if p is not None:
            log(f"rejected {why}: D {p['diameter'] * 1000:.0f} mm, L {p['length']:.2f} m, arc {p['arc']:.0f}, "
                f"contrast {p.get('contrast', -1):.1f}, soil-like {p.get('soil_like', -1):.2f}")
    pipes = kept

    # ── 케이블·다발 ──
    excl = np.zeros(len(Pt), bool)
    for p in pipes:
        excl |= _near_polyline(Pt, p["centerline"], p["r"] + max(0.015, 0.15 * p["r"]))
    lins = detect_linear_small(Pt, Nt, Wt, excl, gt, prm, log)
    bundles = []
    for lc in lins:
        xy = lc["xy"]
        zz = np.full(len(xy), lc["top"])
        cl3 = np.column_stack([xy, zz])
        # 관과 겹치면 관이 이긴다 (관 윗면도 솟은 띠로 보인다)
        over = False
        for p in pipes:
            dd = _polyline_dist(cl3, p["centerline"])
            if (dd < p["r"] + 0.05).mean() > 0.4:
                over = True
                break
        if over:
            continue
        ends = []
        dxy = lc["xy"][-1] - lc["xy"][0]
        dxy = dxy / (np.linalg.norm(dxy) + 1e-12)
        for endp, od in ((lc["xy"][0], -dxy), (lc["xy"][-1], dxy)):
            ep3 = np.array([endp[0], endp[1], lc["top"]])
            ends.append(_end_state(ep3, np.array([od[0], od[1], 0.0]), lc["width"] / 2, lc["top"], geo["contour"], gt, prm))
        lc["ends"] = ends
        # 바닥에 놓인 것만: 기울기 25 % 넘게 벽을 타거나 원지반 높이까지 올라오면 벽 질감·굴착 모서리다
        tz = np.asarray(lc["tops"])
        sxy = np.asarray(lc["sec_xy"])
        run_xy = float(np.linalg.norm(sxy[-1] - sxy[0])) if len(sxy) >= 2 else 0.0
        if run_xy > 0.1 and abs(tz[-1] - tz[0]) / run_xy > 0.25:
            continue
        if np.min(ground.z(sxy[:, 0], sxy[:, 1]) - tz) < prm["rim_edge_depth"]:
            continue
        # 가는 선형 물체는 더 엄격히: 한쪽 끝이라도 굴착 안에서 끊기면(공구·호스·뿌리) 뺀다
        if ends.count("free") >= 1 and lc["length"] < prm["free_end_max_len"]:
            log(f"rejected free linear object: L {lc['length']:.2f} m, h {lc['h'] * 1000:.0f} mm, ends {ends}")
            rejected.append(("free_object", None))
            continue
        is_bundle = lc["peaks"] >= 2 and lc["multi"] >= 0.5 and lc["w_cv"] <= 0.4
        # 가닥 지름: 한 층이면 높이, 여러 층이면 봉우리 간격이 더 작다 → 둘 가운데 작은 값 (어림값)
        member = min(lc["h"], lc["spacing"]) if is_bundle else min(lc["h"], lc["width"])
        if not is_bundle and lc["width"] > 0.08:
            continue    # 넓고 낮은 판·흙더미
        if lc["h_cv"] > 0.6:
            continue
        bundles.append(dict(lc=lc, bundle=is_bundle, member=member))
    for why in ("free_object", "soil_arc"):
        n_ = sum(1 for w, _ in rejected if w == why)
        if n_:
            warnings.append(f"{why}_rejected:{n_}")
    # 다발과 겹치는 가는 관(원 찾기가 가닥 하나를 잡은 것)은 다발이 이긴다
    if bundles:
        keep2 = []
        for p in pipes:
            hit = False
            for b in bundles:
                cl3 = np.column_stack([b["lc"]["xy"], np.full(len(b["lc"]["xy"]), b["lc"]["top"])])
                dd = _polyline_dist(p["centerline"], cl3)
                if p["diameter"] < 0.06 and (dd < b["lc"]["width"] / 2 + 0.03).mean() > 0.5:
                    hit = True
            if not hit:
                keep2.append(p)
        pipes = keep2

    # ── 결과 조립 ──
    soil_mask = ~excl
    soil_rgb = np.median(Ct[soil_mask], axis=0) if soil_mask.any() else np.array([110, 90, 70])
    soil_lab = _lab(soil_rgb)
    utils = []
    for p in pipes:
        cl = p["centerline"].copy()
        if (cl[-1, 0] - cl[0, 0]) < -1e-6 or (abs(cl[-1, 0] - cl[0, 0]) <= 1e-6 and cl[-1, 1] < cl[0, 1]):
            cl = cl[::-1]
            p["depth"] = p["depth"][::-1]
        depth = p["depth"]
        hd = np.hypot(cl[-1, 0] - cl[0, 0], cl[-1, 1] - cl[0, 1])
        slope = 100.0 * (cl[-1, 2] - cl[0, 2]) / max(hd, 1e-6)
        col = classify_color(Ct[p["inliers"]]) if len(p["inliers"]) else classify_color(np.zeros((0, 3), np.uint8))
        notes = []
        dE = float(np.linalg.norm(_lab(col["color_rgb"]) - soil_lab))
        if dE < 12 and col["color_name"] not in ("yellow", "blue", "red"):
            notes.append("관 색이 흙과 비슷함(흙이 묻었을 수 있음)")
            col["class_conf"] = round(col["class_conf"] * 0.5, 2)
        D = p["diameter"]
        conf = _geom_conf(p, prm)
        if p["ends"].count("free") == 1:
            notes.append("한쪽 끝이 굴착 안에서 끊김")
            conf *= 0.85
        if p["arc"] < 110:
            notes.append(f"보이는 호가 좁음({p['arc']:.0f}°)")
        kind = _kind_for(col["cls"], D)
        snap = p.get("snap")
        D_out = D
        if prm["diameter_mode"] == "nominal" and snap is not None:
            D_out = snap["od_mm"] / 1000.0          # 공칭 외경 (DN 숫자가 아니라 그 재질의 외경)
        remeasure = D < 0.05 or p["arc"] < 120
        if remeasure:
            notes.append("가는 관이거나 보이는 호가 좁음: 4K 사진 재측정 권장")
        utils.append(dict(
            kind=kind, cls=col["cls"], class_source="color" if col["cls"] != "unknown" else "none",
            centerline=cl, diameter_mm=round(D_out * 1000), diameter_fit_mm=round(D * 1000, 1), snap=snap,
            remeasure=remeasure, r_top=D_out / 2,
            diameter_rms_mm=round(p["diameter_rms"] * 1000, 1),
            visible_arc_deg=round(p["arc"]), length_m=round(p["length"], 2),
            top_depth=depth, slope_pct=round(float(slope), 2), color=col, confidence=round(conf, 2),
            notes=notes, ends=p["ends"], fit_rms_mm=round(p["rms"] * 1000, 1), inl=p["inliers"]))
    for b in bundles:
        lc = b["lc"]
        xy = lc["xy"]
        # 윗면 높이: 단면마다 (바닥 + 솟은 높이)를 중심선 점에 옮긴다
        sxy, stop = lc["sec_xy"], lc["tops"]
        zt = np.array([stop[int(np.argmin(np.hypot(*(sxy - q).T)))] for q in xy])
        cl = np.column_stack([xy, zt])
        if (cl[-1, 0] - cl[0, 0]) < 0:
            cl = cl[::-1]
        depth = ground.z(cl[:, 0], cl[:, 1]) - cl[:, 2]
        # 중심선은 관과 같이 축으로: z = 윗면 − 가닥 지름/2 (뷰어·보고서가 '원지반 − (z + 반지름)'으로 토피를 다시 구해도 같게)
        cl[:, 2] -= b["member"] / 2
        hd = np.hypot(cl[-1, 0] - cl[0, 0], cl[-1, 1] - cl[0, 1])
        near = np.zeros(len(Pt), bool)
        for q, zq in zip(xy, zt):
            near |= (np.hypot(Pt[:, 0] - q[0], Pt[:, 1] - q[1]) < lc["width"] / 2) & ~excl & \
                (Pt[:, 2] > zq - 0.4 * lc["h"])          # 가닥 윗부분만 (사이 흙 빼기)
        col = classify_color(Ct[near])
        # 50 mm 미만 케이블은 3D 형상만으로는 가늠 수준 → 신뢰도 상한 0.5, 사진 재측정 대상
        conf = float(np.clip(0.35 + 0.1 * lc["n_sec"] ** 0.5, 0.3, 0.5) * (1 - min(0.5, lc["h_cv"])))
        notes = []
        if b["bundle"]:
            notes.append(f"케이블 다발: 보이는 가닥 약 {lc['peaks']}개, 폭 {lc['width'] * 1000:.0f} mm")
        dE = float(np.linalg.norm(_lab(col["color_rgb"]) - soil_lab))
        if dE < 10:
            conf *= 0.6
            notes.append("색이 흙과 비슷함")
        utils.append(dict(
            kind="bundle" if b["bundle"] else "cable",
            cls=col["cls"] if col["cls"] in ("power", "telecom") else "unknown",
            class_source="color" if col["cls"] in ("power", "telecom") else "none",
            centerline=cl, diameter_mm=round(b["member"] * 1000), diameter_rms_mm=None, visible_arc_deg=None,
            length_m=round(lc["length"], 2), top_depth=depth,
            slope_pct=round(float(100 * (cl[-1, 2] - cl[0, 2]) / max(hd, 1e-6)), 2), color=col,
            confidence=round(conf, 2), notes=notes, ends=lc.get("ends"), fit_rms_mm=None, inl=np.flatnonzero(near),
            count=int(lc["peaks"]) if b["bundle"] else 1, width_mm=round(lc["width"] * 1000),
            diameter_fit_mm=round(b["member"] * 1000, 1), snap=None, remeasure=True, r_top=b["member"] / 2))
    utils.sort(key=lambda u: float(np.mean(u["top_depth"])))
    for i, u in enumerate(utils):
        dpt = u["top_depth"]
        rec = dict(id=f"U{i + 1}", kind=u["kind"], **{"class": u["cls"]}, class_source=u["class_source"],
                   centerline=to_utm(u["centerline"]), diameter_mm=u["diameter_mm"],
                   diameter_rms_mm=u["diameter_rms_mm"], visible_arc_deg=u["visible_arc_deg"], length_m=u["length_m"],
                   top_depth_m=dict(min=round(float(np.min(dpt)), 3), max=round(float(np.max(dpt)), 3),
                                    mean=round(float(np.mean(dpt)), 3)),
                   slope_pct=u["slope_pct"], color_rgb=u["color"]["color_rgb"], confidence=u["confidence"],
                   notes="; ".join(u["notes"]),
                   # ── 계약 §2 밖 (제안) ──
                   class_confidence=u["color"]["class_conf"], class_candidates=u["color"]["candidates"],
                   color_name=u["color"]["color_name"], fit_rms_mm=u["fit_rms_mm"], ends=u["ends"],
                   diameter_fit_mm=u.get("diameter_fit_mm"),
                   nominal_mm=(u.get("snap") or {}).get("nominal_mm"), nominal_od_mm=(u.get("snap") or {}).get("od_mm"),
                   nominal_family=(u.get("snap") or {}).get("family"), nominal_margin=(u.get("snap") or {}).get("margin"),
                   top_z_m=dict(min=round(float(np.min(u["centerline"][:, 2] + u["r_top"] + origin[2])), 3),
                                max=round(float(np.max(u["centerline"][:, 2] + u["r_top"] + origin[2])), 3),
                                mean=round(float(np.mean(u["centerline"][:, 2] + u["r_top"] + origin[2])), 3)),
                   remeasure=bool(u.get("remeasure")))
        if u["kind"] in ("bundle", "cable") and "count" in u:
            rec["count"] = u["count"]
            rec["width_mm"] = u["width_mm"]
        res["utilities"].append(rec)
        u["id"] = rec["id"]

    # ── 굴착 크기 ──
    g = gt["grid"]
    mask = gt["mask"]
    util_pts = np.zeros(len(Pt), bool)
    for u in utils:
        util_pts[u["inl"]] = True
    for p in pipes:   # 관 둘레 전체 (원 정상치가 아닌 점도)
        util_pts |= _near_polyline(Pt, p["centerline"], p["r"] + 0.02)
    fp = Pt[~util_pts]
    fix = ((fp[:, 0] - g.x0) / g.cell).astype(int)
    fiy = ((fp[:, 1] - g.y0) / g.cell).astype(int)
    okk = (fix >= 0) & (fix < g.nx) & (fiy >= 0) & (fiy < g.ny)
    # 부피용 바닥: 셀 중앙값 (벽·턱에 걸친 셀을 맨 아래로 치지 않게), 관 점은 빼고 빈 곳은 메운다
    floor, fcnt = _cell_quantile(fiy[okk] * g.nx + fix[okk], fp[okk, 2], 0.5, g.nx * g.ny)
    floor = floor.reshape(g.ny, g.nx)
    has = np.isfinite(floor) & mask
    aix = ((Pt[:, 0] - g.x0) / g.cell).astype(int)
    aiy = ((Pt[:, 1] - g.y0) / g.cell).astype(int)
    oka = (aix >= 0) & (aix < g.nx) & (aiy >= 0) & (aiy < g.ny)
    seen = np.zeros_like(mask)
    seen[aiy[oka], aix[oka]] = True
    cover = float((seen & mask).sum() / max(1, mask.sum()))
    fl = np.where(np.isfinite(floor), floor, 0).astype(np.float32)
    hole = (mask & ~np.isfinite(floor)).astype(np.uint8)
    if hole.any():
        fl = cv2.inpaint(fl, hole, 3, cv2.INPAINT_TELEA)
    Gz = ground.z(g.CX, g.CY)
    dep = np.where(mask, np.maximum(0, Gz - fl), 0)
    vol = float(dep[mask].sum() * g.cell * g.cell)
    dlo = np.where(mask & gt["valid"], Gz - gt["lo"], np.nan)
    dmax = float(np.nanpercentile(dlo, 99.5)) if np.isfinite(dlo).any() else 0.0
    ring = geo["ring"]
    rz = ground.z(ring[:, 0], ring[:, 1])
    ring3 = np.column_stack([ring, rz])
    ring3 = np.vstack([ring3, ring3[:1]])
    res["trench"] = dict(outline=to_utm(ring3), length_m=round(geo["length"], 2), width_m=round(geo["width"], 2),
                         depth_max_m=round(dmax, 2), volume_m3=round(vol, 2),
                         axis_deg=round(math.degrees(math.atan2(geo["axis"][1], geo["axis"][0])), 1),
                         area_m2=round(geo["area"], 2))
    res["quality"]["trench_coverage_pct"] = round(100 * cover, 1)
    if cover < 0.7:
        warnings.append("low_coverage")
    res["quality"]["rim_coverage_pct"] = round(100 * gt.get("rim_coverage", 0), 1)
    # ── v0.2: 측점·이격·로컬 좌표 ──
    _add_stations_clearances(res, utils, origin)
    if georef is not None:
        try:
            _add_local(res, utils, ground, geo, origin, georef)
        except Exception as e:      # pyproj 없음 등: 로컬 필드만 빠진다
            warnings.append("local_frame_failed")
            log(f"local frame failed: {e}")
    else:
        warnings.append("no_georef_local")
    res["seconds"] = round(time.time() - t0, 1)
    log(f"done: {len(res['utilities'])} utilities, trench {geo['length']:.2f}x{geo['width']:.2f} m "
        f"depth {dmax:.2f} vol {vol:.2f} m3, {res['seconds']} s")
    for r_ in res["utilities"]:
        log(f"  {r_['id']} {r_['kind']:7s} {r_['class']:7s} D {r_['diameter_mm']} mm  L {r_['length_m']} m  "
            f"top {r_['top_depth_m']['mean']:.3f} m  arc {r_['visible_arc_deg']}  conf {r_['confidence']}")
    if debug_png:
        try:
            render_debug(debug_png, PL, C, gt, geo, utils, prm)
        except Exception as e:
            log(f"debug render failed: {e}")
    return res


# ═══════════════════════════════════════════ 10) 그림 ═══════════════════════════════════════════
def _put(img, text, org, scale=0.45, color=(255, 255, 255), th=1):
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), th + 2, cv2.LINE_AA)
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color, th, cv2.LINE_AA)


def render_debug(path, PL, C, gt, geo, utils, prm):
    ground = gt.get("ground")
    if geo is not None:
        cen, ax = geo["center"], geo["axis"]
        half = geo["length"] / 2 + 0.6
    else:
        cen = PL[:, :2].mean(0)
        ax = np.array([1.0, 0])
        half = None
    xmin, ymin = PL[:, 0].min(), PL[:, 1].min()
    xmax, ymax = PL[:, 0].max(), PL[:, 1].max()
    span = max(xmax - xmin, ymax - ymin)
    px = max(0.004, span / 1100)
    Wd, Ht = int((xmax - xmin) / px) + 1, int((ymax - ymin) / px) + 1
    ix = ((PL[:, 0] - xmin) / px).astype(int)
    iy = ((ymax - PL[:, 1]) / px).astype(int)
    key = iy * Wd + ix
    order = np.argsort(PL[:, 2])
    img = np.zeros((Ht * Wd, 3), np.uint8)
    img[key[order]] = C[order][:, ::-1]
    img = img.reshape(Ht, Wd, 3)
    if ground is not None:
        zt = np.full(Ht * Wd, np.nan)
        zt[key[order]] = PL[order, 2]
        gz = ground.z(xmin + (np.arange(Wd) + 0.5) * px, ymax - (np.arange(Ht)[:, None] + 0.5) * px)
        dd = gz - zt.reshape(Ht, Wd)
        shade = np.clip(1 - 0.5 * np.nan_to_num(dd, nan=0) / 1.5, 0.45, 1.0)
        img = (img * shade[..., None]).astype(np.uint8)

    def w2i(X):
        return np.column_stack([(X[:, 0] - xmin) / px, (ymax - X[:, 1]) / px]).astype(np.int32)

    if geo is not None:
        cv2.polylines(img, [w2i(geo["ring"])], True, (255, 255, 0), 1, cv2.LINE_AA)
    sec_pos = [0.25, 0.5, 0.75]
    perp = np.array([-ax[1], ax[0]])
    if geo is not None:
        for f in sec_pos:
            c0 = cen + ax * (f - 0.5) * geo["length"]
            a = c0 - perp * (geo["width"] / 2 + 0.5)
            b = c0 + perp * (geo["width"] / 2 + 0.5)
            cv2.line(img, tuple(w2i(a[None])[0]), tuple(w2i(b[None])[0]), (200, 200, 200), 1, cv2.LINE_AA)
        a = cen - ax * half
        b = cen + ax * half
        cv2.line(img, tuple(w2i(a[None])[0]), tuple(w2i(b[None])[0]), (160, 160, 160), 1, cv2.LINE_AA)
    for u in utils:
        col = DRAW_BGR.get(u["cls"], DRAW_BGR["unknown"])
        pts = w2i(u["centerline"][:, :2])
        th = max(2, int(round(u["diameter_mm"] / 1000 / px)))
        cv2.polylines(img, [pts], False, (0, 0, 0), th + 2, cv2.LINE_AA)
        cv2.polylines(img, [pts], False, col, th, cv2.LINE_AA)
        m = pts[len(pts) // 2]
        _put(img, f"{u['id']} {u['kind']} {u['cls']} D{u['diameter_mm']} d{np.mean(u['top_depth']):.2f}m",
             (int(m[0]) + 6, int(m[1]) - 6), 0.45, col)
    _put(img, "top view (UTM, north up)  cyan=trench outline  grey=sections", (8, 18), 0.5)
    panels = [img]

    if geo is not None:
        secs = []
        for f in sec_pos:
            c0 = cen + ax * (f - 0.5) * geo["length"]
            secs.append(_section_img(PL, C, ground, utils, c0, ax, perp, geo["width"] / 2 + 0.5, f"cross {int(f * 100)}%"))
        row = _hstack(secs)
        panels.append(row)
        panels.append(_section_img(PL, C, ground, utils, cen, perp, ax, half, "long section (axis)", scale=180))
    W = max(p.shape[1] for p in panels)
    out = [cv2.copyMakeBorder(p, 4, 4, 0, W - p.shape[1], cv2.BORDER_CONSTANT, value=(30, 30, 30)) for p in panels]
    cv2.imwrite(path, np.vstack(out))


def _hstack(imgs):
    H = max(i.shape[0] for i in imgs)
    return np.hstack([cv2.copyMakeBorder(i, 0, H - i.shape[0], 0, 6, cv2.BORDER_CONSTANT, value=(30, 30, 30)) for i in imgs])


def _section_img(PL, C, ground, utils, c0, nrm2, hor2, half, title, scale=300, thick=0.025):
    """단면: 평면 법선 nrm2 (수평 2D), 가로축 hor2. scale px/m."""
    n3 = np.array([nrm2[0], nrm2[1], 0.0])
    s = (PL[:, :2] - c0) @ nrm2
    u = (PL[:, :2] - c0) @ hor2
    m = (np.abs(s) < thick) & (np.abs(u) < half)
    gz0 = ground.z(c0[0], c0[1])
    zlo = min(PL[m, 2].min() if m.any() else gz0 - 1.5, gz0 - 0.3) - 0.1
    zhi = gz0 + 0.25
    Wd = int(2 * half * scale) + 1
    Ht = int((zhi - zlo) * scale) + 1
    img = np.full((Ht, Wd, 3), 25, np.uint8)
    ii = ((u[m] + half) * scale).astype(int)
    jj = ((zhi - PL[m, 2]) * scale).astype(int)
    for (a, b), cc in zip(np.column_stack([ii, jj]), C[m][:, ::-1]):
        cv2.circle(img, (int(a), int(b)), 1, tuple(int(x) for x in cc), -1)
    uu = np.linspace(-half, half, 200)
    gx = c0[0] + uu * hor2[0]
    gy = c0[1] + uu * hor2[1]
    gzz = ground.z(gx, gy)
    gp = np.column_stack([(uu + half) * scale, (zhi - gzz) * scale]).astype(np.int32)
    cv2.polylines(img, [gp], False, (80, 220, 80), 1, cv2.LINE_AA)
    for uobj in utils:
        cl = uobj["centerline"]
        sv = (cl[:, :2] - c0) @ nrm2
        for i in range(len(cl) - 1):
            if sv[i] == sv[i + 1] or np.sign(sv[i]) == np.sign(sv[i + 1]) and sv[i] != 0:
                continue
            t = sv[i] / (sv[i] - sv[i + 1])
            q = cl[i] + t * (cl[i + 1] - cl[i])
            dvec = cl[i + 1] - cl[i]
            dvec = dvec / (np.linalg.norm(dvec) + 1e-12)
            uq = (q[:2] - c0) @ hor2
            if abs(uq) > half:
                continue
            r = uobj["diameter_mm"] / 2000.0
            cosang = abs(dvec @ n3)
            ru = r / max(cosang, 0.2)
            col = DRAW_BGR.get(uobj["cls"], DRAW_BGR["unknown"])
            center = (int((uq + half) * scale), int((zhi - q[2]) * scale))
            if uobj["kind"] in ("bundle", "cable"):
                hw, hh = int(uobj.get("width_mm", 20) / 2000 * scale), max(1, int(uobj["diameter_mm"] / 2000 * scale))
                cv2.rectangle(img, (center[0] - hw, center[1] - hh), (center[0] + hw, center[1] + hh), col, 1)
                topz = q[2] + uobj["diameter_mm"] / 2000.0
            else:
                cv2.ellipse(img, center, (max(1, int(ru * scale)), max(1, int(r * scale))), 0, 0, 360, col, 1, cv2.LINE_AA)
                topz = q[2] + r
            gq = ground.z(q[0], q[1])
            x = center[0]
            cv2.line(img, (x, int((zhi - gq) * scale)), (x, int((zhi - topz) * scale)), (230, 230, 230), 1)
            _put(img, f"{uobj['id']} D{uobj['diameter_mm']} d{gq - topz:.2f}", (x + 4, int((zhi - topz) * scale) - 4),
                 0.4, col)
    _put(img, title, (6, 16), 0.5)
    return img


# ═══════════════════════════════════════════ 11) 파일 입출력 ═══════════════════════════════════════════
def read_las(path):
    import laspy
    las = laspy.read(path)
    P = np.column_stack([np.asarray(las.x), np.asarray(las.y), np.asarray(las.z)]).astype(np.float64)
    try:
        rgb = np.column_stack([np.asarray(las.red), np.asarray(las.green), np.asarray(las.blue)]).astype(np.float64)
        if rgb.max() > 255:
            rgb = rgb / 257.0
        C = np.clip(rgb + 0.5, 0, 255).astype(np.uint8)
    except Exception:
        C = np.full((len(P), 3), 128, np.uint8)
    return P, C


def read_georef(path_or_dict):
    """job.json / result.json 의 georef. → dict(lon, lat, elev, heading)."""
    d = path_or_dict
    if isinstance(d, str):
        with open(d, encoding="utf-8") as f:
            d = json.load(f)
    g = d.get("georef", d)
    lon = g.get("lon", g.get("longitude"))
    lat = g.get("lat", g.get("latitude"))
    if lon is None or lat is None:
        raise ValueError("georef: lon/lat missing")
    return dict(lon=float(lon), lat=float(lat), elev=float(g.get("elev", g.get("elevation", 0.0)) or 0.0),
                heading=float(g.get("heading", g.get("heading_deg", 0.0)) or 0.0))


def arkit_to_utm(X, gr, vectors=False):
    """process_scan.write_las 와 같은 변환. vectors=True 면 회전만(법선)."""
    th = math.radians(gr["heading"])
    x, y, z = X[:, 0], X[:, 1], X[:, 2]
    e = x * math.cos(th) - z * math.sin(th)
    n = -x * math.sin(th) - z * math.cos(th)
    out = np.column_stack([e, n, y])
    if vectors:
        return out
    from pyproj import Transformer
    tf = Transformer.from_crs("EPSG:4326", "EPSG:32652", always_xy=True)
    e0, n0 = tf.transform(gr["lon"], gr["lat"])
    return out + np.array([e0, n0, gr["elev"]])


def read_mesh_utm(path, gr, spacing=0.006, log=print):
    import open3d as o3d
    mesh = o3d.io.read_triangle_mesh(path)
    if len(mesh.triangles) == 0:
        raise ValueError(f"mesh has no triangles: {path}")
    mesh.compute_triangle_normals()
    area = mesh.get_surface_area()
    n = int(min(6_000_000, max(10000, area / (spacing * spacing))))
    pcd = mesh.sample_points_uniformly(number_of_points=n, use_triangle_normal=True)
    Pl = np.asarray(pcd.points)
    Nl = np.asarray(pcd.normals) if pcd.has_normals() else None
    Cl = np.asarray(pcd.colors) if pcd.has_colors() else np.full((len(Pl), 3), 0.5)
    P = arkit_to_utm(Pl, gr)
    N = arkit_to_utm(Nl, gr, vectors=True) if Nl is not None else None
    log(f"mesh: {len(mesh.triangles)} tris, {area:.1f} m2 -> {n} samples")
    return P, np.clip(Cl * 255 + 0.5, 0, 255).astype(np.uint8), N


def extract_files(las=None, mesh=None, georef=None, out_dir=".", job_id=None, params=None, log=print, debug=True):
    t0 = time.time()
    alog = _ascii_log(log)
    os.makedirs(out_dir, exist_ok=True)
    P = C = N = None
    source = None
    warn = []
    gr, jd = None, {}
    if georef:
        try:
            gr = read_georef(georef)
            if isinstance(georef, str):
                with open(georef, encoding="utf-8") as f:
                    jd = json.load(f)
            elif isinstance(georef, dict):
                jd = georef
        except Exception as e:
            alog(f"georef unreadable ({e}); local (ARKit) fields will be missing")
            warn.append("georef_unreadable")
    if mesh and gr is not None:
        try:
            P, C, N = read_mesh_utm(mesh, gr, (params or {}).get("mesh_spacing", DEFAULTS["mesh_spacing"]), alog)
            source = "mesh"
            if las and os.path.exists(las):   # 같은 자리인지 확인
                PL_, _ = read_las(las)
                # 범위(2–98 %)로 비교: 면에서 고르게 뽑은 점과 줄인 정점은 중앙값이 다를 수 있다
                off = np.abs(np.percentile(P, [2, 98], axis=0) - np.percentile(PL_, [2, 98], axis=0)).max()
                if off > 0.5:
                    warn.append("mesh_las_offset")
                    alog(f"warning: mesh vs las extent differs by {off:.2f} m (georef mismatch?)")
        except Exception as e:
            alog(f"mesh path failed ({e}); falling back to las")
            P = None
    if P is None:
        if not las:
            raise SystemExit("need --las (or --mesh with --georef)")
        P, C = read_las(las)
        source = "las"
    if job_id is None:
        job_id = ""
        for cand in (georef, os.path.join(os.path.dirname(os.path.abspath(las or mesh)), "..", "job.json")):
            try:
                if isinstance(cand, str) and os.path.exists(cand):
                    with open(cand, encoding="utf-8") as f:
                        jd = json.load(f)
                    job_id = str(jd.get("job_id", jd.get("id", "")) or "")
                    if job_id:
                        break
            except Exception:
                pass
    dbg = os.path.join(out_dir, "utilities_debug.png") if debug else None
    res = extract(P, C, normals=N, params=params, log=log, job_id=job_id, debug_png=dbg, source=source, georef=gr)
    res["quality"]["warnings"].extend(warn)
    res["quality"]["source"] = source
    # 맨 위 날짜·제목 (뷰어 PNG·DXF, 보고서가 쓴다): captured_at = 촬영(job.json created_at), created_at = 이 결과를 만든 때
    if jd.get("created_at") or jd.get("captured_at"):
        res["captured_at"] = jd.get("captured_at") or jd.get("created_at")
    if jd.get("title"):
        res["title"] = jd["title"]
    res["created_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    res["seconds"] = round(time.time() - t0, 1)
    with open(os.path.join(out_dir, "utilities.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    return res


def main():
    ap = argparse.ArgumentParser(description="kgeoScan excavation utility extraction -> utilities.json")
    ap.add_argument("--las")
    ap.add_argument("--mesh")
    ap.add_argument("--georef", help="job.json / result.json with georef {lon, lat, elev, heading}")
    ap.add_argument("--out", required=True)
    ap.add_argument("--job-id")
    ap.add_argument("--params", default="", help="JSON overriding DEFAULTS")
    ap.add_argument("--no-debug", action="store_true")
    a = ap.parse_args()
    t0 = time.time()
    log = lambda m: print(f"[{time.time() - t0:6.1f}s] {m}".encode("ascii", "replace").decode(), flush=True)
    params = json.loads(a.params) if a.params else None
    res = extract_files(las=a.las, mesh=a.mesh, georef=a.georef, out_dir=a.out, job_id=a.job_id, params=params,
                        log=log, debug=not a.no_debug)
    summ = dict(ok=True, utilities=len(res["utilities"]), trench=res["trench"] is not None,
                kinds=[u["kind"] for u in res["utilities"]], seconds=res["seconds"], warnings=res["quality"]["warnings"])
    print(json.dumps(summ, ensure_ascii=True))


if __name__ == "__main__":
    main()
