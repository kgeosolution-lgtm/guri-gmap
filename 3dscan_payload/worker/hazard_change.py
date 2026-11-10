r"""
kgeoScan 위험요소 변화 비교 (같은 장소의 직전 스캔 ↔ 이번 스캔)

  from hazard_change import compare
  changes = compare(prev_hazards, cur_hazards, prev_img, cur_img, log=print)      # docs/hazards_contract.md §3
  CLI:
    python -I hazard_change.py --prev A_hazards.json --prev-img A_ortho.jpg --cur B_hazards.json --cur-img B_ortho.jpg \
                               --out changes.json [--debug dbg.jpg]

입력: 계약 §2 의 <job>_hazards.json 두 개(dict 또는 경로)와 두 정사영상(BGR ndarray 또는 경로, 없어도 됨 — 표식이 있으면).
좌표: 계약 §1 정사영상 픽셀(픽셀 중심 = 정수 + 0.5). 행렬은 이 좌표끼리 옮긴다(직전 → 이번).

방법
  1) 정합(직전 px → 이번 px)
     - 공통 고정 표식(markers[].id) 2개 이상: 표식 모서리로 닮음(2개) / 아핀(3개 이상, 한 줄로 늘어서지 않을 때).
       영상이 있으면 영상 특징으로 한 번 더 맞춰 서로 다르면(check_mm) 알린다(스티커를 옮겨 붙였을 수 있음).
     - 표식이 모자라면 영상 특징: 직전 영상을 gsd 비로 미리 맞춘 뒤 축소 영상에서 SIFT+비율 검사+RANSAC 닮음 →
       원해상도 타일(직전 영상을 이번 격자로 옮겨 놓고)에서 SIFT 를 다시 맞춰 아핀(기본)을 RANSAC 으로 구한다.
     - 두 정사영상은 모두 정사투영이라 서로 아핀 관계다. 사영(homography)은 params model="homography" 로만 쓴다.
     - ok = 정상치 수·잔차(rms_mm)·정상치 분포·축척(gsd 비와 비교)이 기준 안. 실패하면 모든 항목을 unmatched 로 둔다.
  2) 겹치는 영역: 두 영상의 칠해진 곳(배경색 24 가 아닌 곳)을 이번 좌표에서 겹친 곳. 한쪽에서만 보이는 항목은
     new/repaired 가 아니라 unmatched(reason outside_prev/outside_cur)다.
  3) 짝짓기
     - 균열: 중심선을 1 mm 간격 점으로 바꿔 서로 tol = max(3 mm, 2×폭) + 2×정합 rms 안에 드는 길이를 잰다.
       어느 한쪽 길이의 40 % 이상이 겹치면 연결한다. 연결된 덩어리(일대다·다대일 = 갈라짐·이어짐·가지)를 한 변화 단위로 본다.
       extension_mm = 이번 균열 가운데 직전 어느 균열에서도 tol 밖인 길이(겹친 영역 안만).
     - 변색·요철: 다각형을 1 mm 격자로 칠해 IoU ≥ 0.2 또는 작은 쪽의 50 % 이상 겹치면 연결.
     - 변형(G): 형상이 없으므로 subtype 끼리 값만 비교(정합 실패여도 비교한다).
  4) 판정(계약 §3 v1): 균열 폭 > max(0.05 mm, 15 %), 길이 > 5 mm(extension > 5 mm 이고 전체 길이도 2.5 mm 넘게 늘어남),
     면적 > 10 % 이고 > 100 mm². 줄어든 쪽도 같은 크기면 shrunk. 커짐과 작아짐이 함께면 grown.
     계약에 없는 기준(요철 깊이, 변형 기울기·평탄도)은 DEFAULTS 에 따로 두었다.

출력 항목 하나 = 변화 단위 하나. cur_id/prev_id 는 대표(가장 긴·넓은) 항목, cur_ids/prev_ids 는 그 단위의 전부.
prev_geom 은 직전 형상을 이번 정사영상 px 로 옮긴 것(보수됨 표시·회색 겹쳐 그리기용).
"""
import argparse
import json
import math
import os
import time
from itertools import combinations

import cv2
import numpy as np

VERSION = 1
TYPE_ORDER = ["crack", "stain", "relief", "deformation"]
STATUS_ORDER = ["new", "grown", "shrunk", "repaired", "stable", "unmatched"]

DEFAULTS = dict(
    # ── 정합 ──
    marker_max_rms_mm=2.0,        # 표식 모서리 잔차가 이보다 크면 ok=false
    marker_pair_tol_mm=3.0,       # 표식 둘 사이 거리가 두 스캔에서 max(이 값, 2 %) 넘게 다르면 어느 하나를 옮겨 붙인 것
    marker_pair_tol_rel=0.02,
    max_anisotropy=0.03,          # 표식 아핀의 두 축 배율 차가 이보다 크면 닮음으로 (정사영상끼리는 거의 닮음)
    marker_check_mm=3.0,          # 표식 정합과 영상 정합이 이보다 다르면 알림(영상 쪽이 강하면 영상 정합을 쓴다)
    feat_max_rms_mm=2.0,
    feat_min_inliers=30,          # 원해상도 타일 단계 정상치
    feat_min_inliers_coarse=12,   # 축소 단계 정상치
    feat_min_spread=0.03,         # 정상치 볼록껍질 넓이 ÷ 겹친 넓이
    coarse_max_px=(1800, 3200),   # 축소 단계 긴 변(실패하면 다음 크기로)
    coarse_thr_px=3.0,            # 축소 영상 px
    fine_thr_px=2.0,              # 원해상도 영상 px
    ratio=0.8,                    # Lowe 비율 검사
    sift_contrast=0.02,
    tile_px=640,
    max_tiles=30,
    model="affine",               # 영상 특징 최종 모형: affine | similarity | homography
    scale_tol=0.2,                # 맞춘 축척 ÷ (gsd_prev/gsd_cur) 가 1±이 값 밖이면 틀린 정합으로 본다
    fill_rgb=24,                  # 정사영상 빈 곳 색 (orthophoto.py)
    local_field=True,             # 전역 행렬 뒤에 남는 국소 어긋남(비강체)을 영상 짝으로 보정
    field_cell_mm=80.0,
    field_min_n=8,                # 칸마다 이만큼 짝이 있어야 그 칸 값을 쓴다
    field_smooth_cells=0.8,
    field_max_mm=8.0,             # 이보다 큰 잔차의 짝은 틀린 짝으로 보고 뺀다
    # ── 겹친 영역·짝짓기 ──
    cov_cell_mm=4.0,
    cov_margin_mm=5.0,            # 겹친 영역 가장자리에서 이만큼 안쪽만 "겹침"으로 본다
    crack_step_mm=1.0,
    crack_tol_mm=3.0,
    crack_tol_width_k=2.0,
    tol_reg_k=2.0,                # tol 에 더하는 정합 rms 배수
    crack_link_frac=0.4,
    poly_raster_mm=1.0,
    poly_link_iou=0.2,
    poly_link_cover=0.5,
    inside_frac=0.98,             # 이만큼 넘게 겹친 영역 안이면 잘림 없음(metrics 값으로 비교)
    new_inside_frac=0.5,          # new/repaired 로 부르려면 겹친 영역 안에 이 비율 이상, 또는
    new_inside_mm=30.0,           #   (균열) 이 길이 이상 / (면) new_inside_mm2 이상
    new_inside_mm2=300.0,
    # ── 의미 있는 변화 (계약 §3 v1) ──
    width_abs_mm=0.05, width_rel=0.15,
    length_mm=5.0,
    area_rel=0.10, area_abs_mm2=100.0,
    # ── 계약 v1 에 없는 기준 (임시) ──
    depth_abs_mm=5.0, depth_rel=0.25,            # 요철 최대 깊이(절댓값) 증가
    tilt_deg=0.5,                                # 변형: 기울기(절댓값) 변화 — ARKit 중력 방향 오차 ±0.5° 수준이라 그보다 작게 두지 않는다
    flatness_abs_mm=1.0, flatness_rel=0.2,       # 변형: 평탄도 rms 변화
    low_conf_reg_mm=1.5,                         # 정합(국소 보정 뒤) rms 가 이보다 크면 confidence low
)


# ───────────────────────── 작은 도구 ─────────────────────────
def _load_json(x):
    if x is None or isinstance(x, dict):
        return x
    with open(x, encoding="utf-8") as f:
        return json.load(f)


def _load_img(x):
    if x is None:
        return None
    if isinstance(x, np.ndarray):
        img = x
    else:
        img = cv2.imdecode(np.fromfile(str(x), np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"cannot read image: {x}")
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif img.shape[2] == 4:
        img = np.ascontiguousarray(img[..., :3])
    if img.dtype != np.uint8:
        img = np.clip(img, 0, 255).astype(np.uint8)
    return img


def _r(x, n=2):
    if x is None:
        return None
    x = float(x)
    if not math.isfinite(x):
        return None
    return round(x, n)


def _S(sx, sy=None):
    return np.diag([sx, sx if sy is None else sy, 1.0])


def _T(tx, ty):
    M = np.eye(3)
    M[0, 2], M[1, 2] = tx, ty
    return M


def _to_cv(M):
    """계약 좌표(픽셀 중심 +0.5) 행렬 → OpenCV 좌표(픽셀 중심 = 정수) 행렬"""
    return _T(-0.5, -0.5) @ M @ _T(0.5, 0.5)


def _apply(M, pts):
    pts = np.asarray(pts, float).reshape(-1, 2)
    q = pts @ M[:2, :2].T + M[:2, 2]
    if abs(M[2, 0]) > 0 or abs(M[2, 1]) > 0 or abs(M[2, 2] - 1) > 0:
        w = pts @ M[2, :2] + M[2, 2]
        q = q / w[:, None]
    return q


def _is_affine(M):
    return abs(M[2, 0]) < 1e-12 and abs(M[2, 1]) < 1e-12 and abs(M[2, 2] - 1) < 1e-12


def _warp(src, M, size, interp=cv2.INTER_LINEAR, border=0):
    """M: 계약 좌표 src px → dst px"""
    Mc = _to_cv(M)
    if _is_affine(M):
        return cv2.warpAffine(src, Mc[:2], size, flags=interp, borderMode=cv2.BORDER_CONSTANT, borderValue=border)
    return cv2.warpPerspective(src, Mc, size, flags=interp, borderMode=cv2.BORDER_CONSTANT, borderValue=border)


def _lin_scale(M):
    return float(math.sqrt(abs(np.linalg.det(M[:2, :2]))))


def _fit_similarity(src, dst):
    ms, md = src.mean(0), dst.mean(0)
    zs = (src[:, 0] - ms[0]) + 1j * (src[:, 1] - ms[1])
    zd = (dst[:, 0] - md[0]) + 1j * (dst[:, 1] - md[1])
    c = (np.conj(zs) * zd).sum() / max(1e-12, (np.abs(zs) ** 2).sum())
    M = np.eye(3)
    M[:2, :2] = [[c.real, -c.imag], [c.imag, c.real]]
    M[:2, 2] = md - M[:2, :2] @ ms
    return M


def _fit_affine(src, dst):
    A = np.hstack([src, np.ones((len(src), 1))])
    P, *_ = np.linalg.lstsq(A, dst, rcond=None)
    M = np.eye(3)
    M[:2, :] = P.T
    return M


def _min_dists(A, B, chunk=2_000_000):
    """A (n,2), B (m,2) → (A 의 각 점에서 B 까지 최소 거리, B 의 각 점에서 A 까지 최소 거리)"""
    n, m = len(A), len(B)
    dA = np.full(n, np.inf)
    dB = np.full(m, np.inf)
    if n == 0 or m == 0:
        return dA, dB
    step = max(1, chunk // max(1, m))
    for i in range(0, n, step):
        a = A[i:i + step]
        d = np.sqrt(((a[:, None, :] - B[None, :, :]) ** 2).sum(-1))
        dA[i:i + step] = d.min(1)
        dB = np.minimum(dB, d.min(0))
    return dA, dB


def _resample(parts, step_px):
    """폴리라인들 → 같은 간격 점(구간 가운데), 점마다 맡은 길이(px), 몇 번째 part 인지"""
    P, Wt, Id = [], [], []
    for k, part in enumerate(parts or []):
        a = np.asarray(part, float).reshape(-1, 2)
        if len(a) == 0:
            continue
        if len(a) > 1:
            seg = np.linalg.norm(np.diff(a, axis=0), axis=1)
            keep = np.concatenate([[True], seg > 1e-9])
            a = a[keep]
        if len(a) == 1:
            P.append(a)
            Wt.append(np.zeros(1))
            Id.append(np.full(1, k))
            continue
        seg = np.linalg.norm(np.diff(a, axis=0), axis=1)
        L = float(seg.sum())
        n = max(1, int(math.ceil(L / step_px)))
        t = (np.arange(n) + 0.5) * (L / n)
        cum = np.concatenate([[0.0], np.cumsum(seg)])
        P.append(np.stack([np.interp(t, cum, a[:, 0]), np.interp(t, cum, a[:, 1])], 1))
        Wt.append(np.full(n, L / n))
        Id.append(np.full(n, k))
    if not P:
        return np.zeros((0, 2)), np.zeros(0), np.zeros(0, int)
    return np.concatenate(P), np.concatenate(Wt), np.concatenate(Id)


def _parts(geom):
    if not geom:
        return []
    t = geom.get("type")
    if t == "polyline":
        return [p for p in geom.get("parts") or [] if len(p) >= 1]
    if t == "linestring":
        return [geom.get("coordinates") or []]
    return []


def _rings(geom):
    if not geom:
        return []
    t = geom.get("type")
    rings = []
    if t == "polygon":
        rings = geom.get("rings") or []
    elif t == "multipolygon":
        for poly in geom.get("polygons") or []:
            rings += poly
    return [np.asarray(r, float).reshape(-1, 2) for r in rings if len(r) >= 3]


def _fill(rings_px, x0, y0, r, w, h):
    """rings(px) → 칸 크기 r px 인 (h,w) 격자 위 mask(uint8). 겹친 고리는 짝홀(구멍) 규칙"""
    m = np.zeros((h, w), np.uint8)
    if not rings_px:
        return m
    cs = [np.round(((rg - [x0, y0]) / r - 0.5) * 8).astype(np.int32).reshape(-1, 1, 2) for rg in rings_px]
    cv2.fillPoly(m, cs, 1, lineType=cv2.LINE_8, shift=3)
    return m


def _simplify_parts(parts, eps=0.7):
    out = []
    for a in parts:
        a = np.asarray(a, np.float32).reshape(-1, 1, 2)
        if len(a) > 2:
            a = cv2.approxPolyDP(a, eps, False)
        out.append([[round(float(x), 1), round(float(y), 1)] for x, y in a.reshape(-1, 2)])
    return out


def _simplify_rings(rings, eps=0.7):
    out = []
    for a in rings:
        a = np.asarray(a, np.float32).reshape(-1, 1, 2)
        if len(a) > 3:
            a = cv2.approxPolyDP(a, eps, True)
        out.append([[round(float(x), 1), round(float(y), 1)] for x, y in a.reshape(-1, 2)])
    return out


# ───────────────────────── 스캔 하나 ─────────────────────────
class _Scan:
    def __init__(self, h, img, p, name):
        self.h, self.img, self.name = h, img, name
        fr = h.get("frame") or {}
        g = fr.get("gsd_m")
        if not g:
            raise ValueError(f"{name}: frame.gsd_m missing")
        sf = (h.get("scale") or {}).get("factor") or 1.0
        self.gsd = float(g) * 1000.0 * float(sf)                 # mm / 정사영상 px (축척 보정 포함)
        W, H = fr.get("width"), fr.get("height")
        if img is not None:
            Hi, Wi = img.shape[:2]
            if not W or not H:
                W, H = Wi, Hi
            self.kx, self.ky = Wi / float(W), Hi / float(H)        # 영상 px ÷ 정사영상(hazards 좌표) px
        else:
            if not W or not H:
                raise ValueError(f"{name}: frame.width/height missing and no image")
            self.kx = self.ky = 1.0
        self.W, self.H = int(W), int(H)
        self._gray = None
        # 칠해진 곳(배경색이 아닌 곳) — cell px 격자
        self.cell = max(1.0, p["cov_cell_mm"] / self.gsd)
        gw, gh = int(math.ceil(self.W / self.cell)), int(math.ceil(self.H / self.cell))
        if img is None:
            self.cov = np.ones((gh, gw), bool)
        else:
            sm = cv2.resize(img, (gw * 2, gh * 2), interpolation=cv2.INTER_AREA)
            d = np.abs(sm.astype(np.int16) - int(p["fill_rgb"])).sum(axis=2) > 12
            d = cv2.morphologyEx(d.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
            self.cov = cv2.resize(d.astype(np.float32), (gw, gh), interpolation=cv2.INTER_AREA) > 0.5
        self.cov_pct = float(self.cov.mean() * 100)

    @property
    def gray(self):
        if self._gray is None and self.img is not None:
            self._gray = cv2.cvtColor(self.img, cv2.COLOR_BGR2GRAY)
        return self._gray

    def work(self, cx, cy=None):
        """(정사영상 px → 작업 px) 배율 cx 로 줄인 회색 영상과 칠해진 곳 mask"""
        cy = cx if cy is None else cy
        Wt, Ht = max(8, int(round(self.W * cx))), max(8, int(round(self.H * cy)))
        g = self.gray
        interp = cv2.INTER_AREA if Wt < g.shape[1] else cv2.INTER_LINEAR
        gw = cv2.resize(g, (Wt, Ht), interpolation=interp) if (Wt, Ht) != (g.shape[1], g.shape[0]) else g
        m = cv2.resize(self.cov.astype(np.uint8) * 255, (Wt, Ht), interpolation=cv2.INTER_NEAREST)
        e = max(3, int(round(Wt / self.cov.shape[1] * 1.5)))
        m = cv2.erode(m, np.ones((e, e), np.uint8))
        return gw, m, Wt / self.W, Ht / self.H


# ───────────────────────── 정합 ─────────────────────────
_CLAHE = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))


def _sift(gray, mask, p, nfeat):
    sift = cv2.SIFT_create(nfeatures=int(nfeat), contrastThreshold=p["sift_contrast"])
    kps, des = sift.detectAndCompute(gray, mask)
    if des is None or not kps:
        return np.zeros((0, 2), np.float32), None
    return np.array([k.pt for k in kps], np.float32) + 0.5, des        # 계약 좌표(+0.5)


def _ratio_match(d1, d2, ratio):
    if d1 is None or d2 is None or len(d1) < 2 or len(d2) < 2:
        return np.zeros((0, 2), int)
    knn = None
    if len(d1) * len(d2) > 4_000_000:
        try:
            fl = cv2.FlannBasedMatcher(dict(algorithm=1, trees=5), dict(checks=64))
            knn = fl.knnMatch(d1, d2, k=2)
        except cv2.error:
            knn = None
    if knn is None:
        knn = cv2.BFMatcher(cv2.NORM_L2).knnMatch(d1, d2, k=2)
    good = [(m[0].queryIdx, m[0].trainIdx) for m in knn if len(m) == 2 and m[0].distance < ratio * m[1].distance]
    return np.array(good, int).reshape(-1, 2)


def _fit_robust(src, dst, model, thr):
    """RANSAC 으로 3×3 행렬과 정상치 mask. 실패하면 (None, None)"""
    if len(src) < 4:
        return None, None
    src = src.astype(np.float32).reshape(-1, 1, 2)
    dst = dst.astype(np.float32).reshape(-1, 1, 2)
    if model == "homography":
        H, inl = cv2.findHomography(src, dst, cv2.RANSAC, thr, maxIters=5000, confidence=0.999)
        if H is None:
            return None, None
        return H / H[2, 2], inl.ravel().astype(bool)
    fn = cv2.estimateAffinePartial2D if model == "similarity" else cv2.estimateAffine2D
    A, inl = fn(src, dst, method=cv2.RANSAC, ransacReprojThreshold=thr, maxIters=5000, confidence=0.999, refineIters=10)
    if A is None:
        return None, None
    M = np.eye(3)
    M[:2] = A
    return M, inl.ravel().astype(bool)


def _common(prev, cur, M, p):
    """이번 cell 격자 위에서 두 스캔이 모두 칠해진 곳(가장자리 여유만큼 깎음)"""
    Mg = _S(1.0 / cur.cell) @ M @ _S(prev.cell)
    gh, gw = cur.cov.shape
    pw = _warp(prev.cov.astype(np.uint8), Mg, (gw, gh), interp=cv2.INTER_NEAREST) > 0
    both = (cur.cov & pw).astype(np.uint8)
    e = int(math.ceil(p["cov_margin_mm"] / p["cov_cell_mm"]))
    if e > 0:
        both = cv2.erode(both, np.ones((2 * e + 1, 2 * e + 1), np.uint8), borderType=cv2.BORDER_CONSTANT, borderValue=0)
    return both > 0


def _inside(common, cell, pts):
    """이번 px 점들이 겹친 영역 안인지"""
    if len(pts) == 0:
        return np.zeros(0, bool)
    gh, gw = common.shape
    ix = np.floor(pts[:, 0] / cell).astype(int)
    iy = np.floor(pts[:, 1] / cell).astype(int)
    ok = (ix >= 0) & (iy >= 0) & (ix < gw) & (iy < gh)
    out = np.zeros(len(pts), bool)
    out[ok] = common[iy[ok], ix[ok]]
    return out


def _spread(Q, common, cell):
    if len(Q) < 3:
        return 0.0
    hull = cv2.convexHull(Q.astype(np.float32).reshape(-1, 1, 2))
    a = float(cv2.contourArea(hull))
    ca = float(common.sum()) * cell * cell
    return a / ca if ca > 0 else 0.0


def _markers(h, min_id=10):
    """장소 표식(ID ≥ 10, 계약 §5)만. 한 스캔에 같은 ID 가 두 번 보이면 어느 것인지 몰라 그 ID 는 쓰지 않는다"""
    out, seen = {}, {}
    for m in h.get("markers") or []:
        try:
            i = int(m["id"])
        except (KeyError, TypeError, ValueError):
            continue
        if i < min_id:
            continue
        seen[i] = seen.get(i, 0) + 1
        c = m.get("corners_px")
        if c is not None and len(c) == 4:
            out[i] = np.asarray(c, float).reshape(4, 2)
        elif m.get("center_px") is not None:
            out[i] = np.asarray(m["center_px"], float).reshape(1, 2)
    return {i: v for i, v in out.items() if seen[i] == 1}


def _consistent_markers(ids, mp, mc, prev, cur, p):
    """표식끼리 거리(mm)가 두 스캔에서 같은 가장 큰 묶음 — 떼어 다른 자리에 다시 붙인 표식을 뺀다"""
    cp = {i: mp[i].mean(0) * prev.gsd for i in ids}
    cc = {i: mc[i].mean(0) * cur.gsd for i in ids}

    def err(a, b):
        dp = float(np.linalg.norm(cp[a] - cp[b]))
        dc = float(np.linalg.norm(cc[a] - cc[b]))
        return abs(dc - dp), max(p["marker_pair_tol_mm"], p["marker_pair_tol_rel"] * dp)

    ids = ids[:8]
    for k in range(len(ids), 1, -1):
        cands = []
        for s in combinations(ids, k):
            e = [err(a, b) for a, b in combinations(s, 2)]
            if all(x <= t for x, t in e):
                cands.append((sum(x for x, _ in e), list(s)))
        if cands:
            return min(cands)[1]
    return []


def _register_markers(prev, cur, p, log):
    mp, mc = _markers(prev.h), _markers(cur.h)
    ids0 = sorted(set(mp) & set(mc))
    info = dict(common_ids=ids0)
    if len(ids0) < 2:
        return None, info
    ids = _consistent_markers(ids0, mp, mc, prev, cur, p)
    dropped = [i for i in ids0 if i not in ids]
    if dropped:
        log(f"registration: markers {dropped} moved relative to the others (pair distances differ) - not used")
    if len(ids) < 2:
        info["reason"] = f"common markers {ids0} disagree with each other (moved sticker?)"
        return dict(method="markers", ok=False, M=None, n=0, ids=ids0, dropped=dropped, rms_mm=None, scale=None,
                    reason=info["reason"]), info
    S, D, own = [], [], []
    for i in ids:
        a, b = mp[i], mc[i]
        if len(a) != len(b):
            a, b = a.mean(0, keepdims=True), b.mean(0, keepdims=True)
        S.append(a)
        D.append(b)
        own += [i] * len(a)
    S, D = np.concatenate(S), np.concatenate(D)
    model = "similarity"
    M = _fit_similarity(S, D)
    if len(ids) >= 3:
        cen = np.array([mc[i].mean(0) for i in ids])
        sv = np.linalg.svd(cen - cen.mean(0), compute_uv=False)
        if sv[0] > 0 and sv[1] / sv[0] > 0.15:                       # 한 줄로 늘어서지 않았으면 아핀
            Ma = _fit_affine(S, D)
            sva = np.linalg.svd(Ma[:2, :2], compute_uv=False)
            if sva[0] / sva[1] - 1 <= p["max_anisotropy"]:          # 정사영상끼리는 거의 닮음 — 크게 찌그러지면 닮음 유지
                M, model = Ma, "affine"
    res = np.linalg.norm(_apply(M, S) - D, axis=1)
    rms_mm = float(np.sqrt(np.mean(res ** 2))) * cur.gsd
    s0 = prev.gsd / cur.gsd
    sc = _lin_scale(M) / s0
    ok = rms_mm <= p["marker_max_rms_mm"] and abs(sc - 1) <= p["scale_tol"]
    reg = dict(method="markers", model=model, M=M, n=len(ids), ids=ids, dropped=dropped, rms_mm=rms_mm, marker_rms_mm=rms_mm,
               scale=sc, ok=ok)
    if not ok:
        reg["reason"] = f"marker rms {rms_mm:.2f} mm / scale {sc:.3f} out of range"
    log(f"registration: markers {ids} ({model}) rms {rms_mm:.2f} mm, scale vs gsd ratio {sc:.4f}")
    return reg, info


def _coarse(prev, cur, p, log):
    s0 = prev.gsd / cur.gsd                                       # 직전 px 하나가 이번 px 몇 개인지(예상)
    for cmax in p["coarse_max_px"]:
        cc = min(cmax / max(cur.W, cur.H), cur.kx, prev.kx / s0)  # 이번 작업 px / 이번 px
        cp = cc * s0                                              # 직전 작업 px / 직전 px (같은 mm/px)
        gc, mc_, cxc, cyc = cur.work(cc)
        gp, mp_, cxp, cyp = prev.work(cp)
        Pc, Dc = _sift(_CLAHE.apply(gc), mc_, p, 12000)
        Pp, Dp = _sift(_CLAHE.apply(gp), mp_, p, 12000)
        mt = _ratio_match(Dp, Dc, p["ratio"])
        log(f"registration: coarse {gc.shape[1]}x{gc.shape[0]} ({cur.gsd / cc:.2f} mm/px): "
            f"{len(Pp)}/{len(Pc)} keypoints, {len(mt)} ratio matches")
        if len(mt) < p["feat_min_inliers_coarse"]:
            continue
        src = Pp[mt[:, 0]] / [cxp, cyp]
        dst = Pc[mt[:, 1]] / [cxc, cyc]
        M, inl = _fit_robust(src, dst, "similarity", p["coarse_thr_px"] / cc)
        if M is None:
            continue
        n = int(inl.sum())
        sc = _lin_scale(M) / s0
        res = np.linalg.norm(_apply(M, src[inl]) - dst[inl], axis=1)
        rms = float(np.sqrt(np.mean(res ** 2))) if n else float("inf")
        log(f"registration: coarse similarity {n} inliers, rms {rms * cur.gsd:.2f} mm, scale vs gsd ratio {sc:.3f}, "
            f"rot {math.degrees(math.atan2(M[1, 0], M[0, 0])):.2f} deg")
        if n >= p["feat_min_inliers_coarse"] and abs(sc - 1) <= p["scale_tol"]:
            return dict(M=M, n=n, rms_px=rms, Q=dst[inl])
    return None


def _refine(prev, cur, M0, p, log, r_px=None, field=None, fit=True):
    """M0(+field) 로 직전 영상을 이번 격자의 타일마다 다시 표본화해 놓고 원해상도에서 SIFT 를 다시 맞춘다.
    반환: M(최종; fit=False 면 M0), 정상치 수·rms, 그리고 공간 제약을 통과한 모든 짝 P(직전 px)·Q(이번 px) — 국소 보정장에 쓴다"""
    s = _lin_scale(M0)
    cf = min(cur.kx, prev.kx / s)                                  # 이번 작업 px / 이번 px
    Wt, Ht = int(round(cur.W * cf)), int(round(cur.H * cf))
    g_cur = cur.gray
    if (Wt, Ht) != (g_cur.shape[1], g_cur.shape[0]):
        g_cur = cv2.resize(g_cur, (Wt, Ht), interpolation=cv2.INTER_AREA)
    sx, sy = Wt / cur.W, Ht / cur.H
    ratio = (prev.kx / s) / cf                                     # 직전 영상 px / 작업 px
    g_src = prev.gray if ratio < 1.3 else cv2.GaussianBlur(prev.gray, (0, 0), 0.45 * ratio)
    Minv = np.linalg.inv(M0)

    def to_prev(qc):                                               # 이번 px → 직전 px (보정장 역: q − F(q))
        if field:
            qc = qc - _field_eval(field, qc)
        return _apply(Minv, qc)

    common = _common(prev, cur, M0, p)
    cm = cv2.resize(common.astype(np.uint8), (Wt, Ht), interpolation=cv2.INTER_NEAREST)
    T = int(p["tile_px"])
    cand = []
    for y0 in range(0, max(1, Ht - T // 2), T):
        for x0 in range(0, max(1, Wt - T // 2), T):
            frac = float(cm[y0:y0 + T, x0:x0 + T].mean()) if cm[y0:y0 + T, x0:x0 + T].size else 0.0
            if frac >= 0.2:
                cand.append((x0, y0))
    if len(cand) > p["max_tiles"]:
        idx = np.round(np.linspace(0, len(cand) - 1, p["max_tiles"])).astype(int)
        cand = [cand[i] for i in idx]
    r = r_px if r_px is not None else 8.0
    P_all, Q_all = [], []
    for x0, y0 in cand:
        tc = g_cur[y0:y0 + T, x0:x0 + T]
        th_, tw_ = tc.shape
        jj, ii = np.mgrid[0:th_, 0:tw_]
        qc = np.stack([((x0 + ii + 0.5) / sx).ravel(), ((y0 + jj + 0.5) / sy).ravel()], 1)
        pp = to_prev(qc)
        mx = (pp[:, 0] * prev.kx - 0.5).reshape(th_, tw_).astype(np.float32)
        my = (pp[:, 1] * prev.ky - 0.5).reshape(th_, tw_).astype(np.float32)
        tp = cv2.remap(g_src, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        tm = cm[y0:y0 + T, x0:x0 + T] * 255
        Pc, Dc = _sift(_CLAHE.apply(tc), tm, p, 1500)
        Pp, Dp = _sift(_CLAHE.apply(tp), tm, p, 1500)
        mt = _ratio_match(Dp, Dc, max(p["ratio"], 0.85))
        if len(mt) == 0:
            continue
        a, b = Pp[mt[:, 0]], Pc[mt[:, 1]]
        near = np.linalg.norm(a - b, axis=1) < r
        P_all.append(a[near] + [x0, y0])
        Q_all.append(b[near] + [x0, y0])
    if not P_all:
        return None
    P = to_prev(np.concatenate(P_all) / [sx, sy])                  # 다시 표본화한 직전 → 직전 px
    Q = np.concatenate(Q_all) / [sx, sy]
    if not fit:
        return dict(M=M0, P=P, Q=Q, tiles=len(cand))
    model = p["model"]
    M, inl = _fit_robust(P, Q, model, p["fine_thr_px"] / cf)
    if M is None:
        return None
    n = int(inl.sum())
    res = np.linalg.norm(_apply(M, P[inl]) - Q[inl], axis=1)
    rms = float(np.sqrt(np.mean(res ** 2))) if n else float("inf")
    spread = _spread(Q[inl], _common(prev, cur, M, p), cur.cell)
    log(f"registration: fine {len(cand)} tiles at {cur.gsd / cf:.2f} mm/px: {len(P)} matches, {n} inliers ({model}), "
        f"inlier rms {rms * cur.gsd:.2f} mm, spread {spread:.2f}")
    return dict(M=M, n=n, rms_px=rms, spread=spread, model=model, tiles=len(cand), P=P, Q=Q)


def _register_features(prev, cur, p, log):
    s0 = prev.gsd / cur.gsd
    try:
        co = _coarse(prev, cur, p, log)
    except cv2.error as e:
        log(f"registration: coarse failed: {e}")
        co = None
    if co is None:
        return dict(method="features", ok=False, M=None, n=0, reason="no consistent image features")
    try:
        fi = _refine(prev, cur, co["M"], p, log, r_px=max(8.0, 4 * co["rms_px"] * min(cur.kx, prev.kx / _lin_scale(co["M"]))))
    except cv2.error as e:
        log(f"registration: fine failed: {e}")
        fi = None
    if fi is not None and fi["n"] >= p["feat_min_inliers"]:
        sc = _lin_scale(fi["M"]) / s0
        rms_mm = fi["rms_px"] * cur.gsd
        ok = rms_mm <= p["feat_max_rms_mm"] and fi["spread"] >= p["feat_min_spread"] and abs(sc - 1) <= p["scale_tol"]
        reg = dict(method="features", model=fi["model"], M=fi["M"], n=fi["n"], rms_mm=rms_mm, inlier_rms_mm=rms_mm,
                   spread=fi["spread"], scale=sc, ok=ok, tiles=fi["tiles"], coarse_inliers=co["n"], P=fi["P"], Q=fi["Q"])
        if not ok:
            reg["reason"] = f"rms {rms_mm:.2f} mm / spread {fi['spread']:.2f} / scale {sc:.3f} out of range"
        return reg
    rms_mm = co["rms_px"] * cur.gsd
    spread = _spread(co["Q"], _common(prev, cur, co["M"], p), cur.cell)
    sc = _lin_scale(co["M"]) / s0
    ok = rms_mm <= p["feat_max_rms_mm"] and spread >= p["feat_min_spread"] and co["n"] >= p["feat_min_inliers"]
    reg = dict(method="features", model="similarity", M=co["M"], n=co["n"], rms_mm=rms_mm, inlier_rms_mm=rms_mm, spread=spread,
               scale=sc, ok=ok, coarse_only=True)
    if not ok:
        reg["reason"] = f"only coarse match: {co['n']} inliers, rms {rms_mm:.2f} mm"
    return reg


def _disagree_mm(M1, M2, prev, cur, p):
    """같은 겹친 영역에서 두 행렬이 이번 px 를 얼마나 다르게 옮기는지(rms, max, mm)"""
    common = _common(prev, cur, M1, p)
    ys, xs = np.nonzero(common)
    if len(xs) == 0:
        return None, None
    if len(xs) > 4000:
        sel = np.linspace(0, len(xs) - 1, 4000).astype(int)
        xs, ys = xs[sel], ys[sel]
    q = (np.stack([xs, ys], 1) + 0.5) * cur.cell
    p2 = _apply(np.linalg.inv(M2), q)
    d = np.linalg.norm(_apply(M1, p2) - q, axis=1) * cur.gsd
    return float(np.sqrt(np.mean(d ** 2))), float(d.max())


# ── 국소 보정장: 전역 행렬 뒤에 남는 비강체 뒤틀림(메시 드리프트 등) ──
def _field_eval(field, pts):
    """보정장(이번 px 격자) 을 점에서 쌍선형 보간 → (n,2) px"""
    pts = np.asarray(pts, float).reshape(-1, 2)
    if not field or len(pts) == 0:
        return np.zeros_like(pts)
    cs = float(field["cell_px"])
    F = np.stack([np.asarray(field["dx"], float), np.asarray(field["dy"], float)], -1)
    gy, gx = F.shape[:2]
    u = np.clip(pts[:, 0] / cs - 0.5, 0, gx - 1)
    v = np.clip(pts[:, 1] / cs - 0.5, 0, gy - 1)
    i0, j0 = np.floor(u).astype(int), np.floor(v).astype(int)
    i1, j1 = np.minimum(i0 + 1, gx - 1), np.minimum(j0 + 1, gy - 1)
    tu, tv = (u - i0)[:, None], (v - j0)[:, None]
    return (F[j0, i0] * (1 - tu) * (1 - tv) + F[j0, i1] * tu * (1 - tv) + F[j1, i0] * (1 - tu) * tv + F[j1, i1] * tu * tv)


def _robust_rms(d):
    """2축 정규 잔차의 rms ≈ 1.2 × |잔차| 중앙값 (틀린 짝 몇 개에 흔들리지 않게)"""
    return float(1.2 * np.median(d)) if len(d) else None


def _fit_weighted(S, D, w, model):
    if model == "similarity":
        ws = w / w.sum()
        ms, md = (S * ws[:, None]).sum(0), (D * ws[:, None]).sum(0)
        zs = (S[:, 0] - ms[0]) + 1j * (S[:, 1] - ms[1])
        zd = (D[:, 0] - md[0]) + 1j * (D[:, 1] - md[1])
        c = (ws * np.conj(zs) * zd).sum() / max(1e-12, (ws * np.abs(zs) ** 2).sum())
        M = np.eye(3)
        M[:2, :2] = [[c.real, -c.imag], [c.imag, c.real]]
        M[:2, 2] = md - M[:2, :2] @ ms
        return M
    sw = np.sqrt(w)[:, None]
    A = np.hstack([S, np.ones((len(S), 1))]) * sw
    P_, *_ = np.linalg.lstsq(A, D * sw, rcond=None)
    M = np.eye(3)
    M[:2, :] = P_.T
    return M


def _refit_global(P, Q, M, model, cur, p):
    """RANSAC 행렬은 뒤틀림이 작은 한 구역에 맞춰지기 쉽다 → 모든 짝(잔차 < field_max)으로 Huber 가중 재적합(평균 행렬)"""
    if P is None or len(P) < 20 or model not in ("affine", "similarity"):
        return M
    keep = np.linalg.norm(Q - _apply(M, P), axis=1) < p["field_max_mm"] / cur.gsd
    if keep.sum() < 20:
        return M
    S, D = P[keep], Q[keep]
    for _ in range(6):
        d = np.linalg.norm(D - _apply(M, S), axis=1)
        k = max(1.0, 1.5 * float(np.median(d)))
        w = np.where(d <= k, 1.0, k / np.maximum(d, 1e-9))
        M = _fit_weighted(S, D, w, model)
    return M


def _field_grid(Pm, R, cur, p):
    """칸마다 중앙값 → 정규화 가우시안(좁게) + 데이터 없는 곳은 넓은 정규화 가우시안으로 이어 붙임(가장자리 외삽)"""
    cs = max(16.0, p["field_cell_mm"] / cur.gsd)
    gx, gy = int(math.ceil(cur.W / cs)), int(math.ceil(cur.H / cs))
    ix = np.clip(np.floor(Pm[:, 0] / cs).astype(int), 0, gx - 1)
    iy = np.clip(np.floor(Pm[:, 1] / cs).astype(int), 0, gy - 1)
    cell = iy * gx + ix
    order = np.argsort(cell, kind="stable")
    uq, st, cnt = np.unique(cell[order], return_index=True, return_counts=True)
    med = np.zeros((gy * gx, 2), np.float32)
    w = np.zeros(gy * gx, np.float32)
    for c, s_, n in zip(uq, st, cnt):
        if n >= p["field_min_n"]:
            med[c] = np.median(R[order[s_:s_ + n]], 0)
            w[c] = 1.0
    if w.sum() < 2:
        return None, None
    med, w = med.reshape(gy, gx, 2), w.reshape(gy, gx)
    F = np.zeros((gy, gx, 2), np.float32)
    den_s = cv2.GaussianBlur(w, (0, 0), p["field_smooth_cells"])
    den_l = cv2.GaussianBlur(w, (0, 0), 3.0)
    a = np.clip(den_s / 0.25, 0, 1)
    for k in range(2):
        mw = np.ascontiguousarray(med[..., k] * w)
        Fs = cv2.GaussianBlur(mw, (0, 0), p["field_smooth_cells"]) / np.maximum(den_s, 1e-6)
        Fl = np.where(den_l > 1e-4, cv2.GaussianBlur(mw, (0, 0), 3.0) / np.maximum(den_l, 1e-6), 0.0)
        F[..., k] = a * Fs + (1 - a) * Fl
    field = dict(cell_px=round(cs, 3), dx=np.round(F[..., 0], 3).tolist(), dy=np.round(F[..., 1], 3).tolist())
    return field, (med, w)


def _local_field(P, Q, M, cur, p):
    """짝 잔차(Q − M(P)) → 보정장. after_mm 은 짝을 반으로 나눠 한쪽으로 만든 장을 다른 쪽에 대 본 값(교차검증)"""
    if P is None or len(P) < 3 * p["field_min_n"]:
        return None, {}
    R = Q - _apply(M, P)
    d = np.linalg.norm(R, axis=1)
    keep = d < p["field_max_mm"] / cur.gsd
    if keep.sum() < 3 * p["field_min_n"]:
        return None, {}
    Pm, R, d = _apply(M, P[keep]), R[keep], d[keep]
    before = _robust_rms(d) * cur.gsd
    field, mw = _field_grid(Pm, R, cur, p)
    stats = dict(before_mm=before)
    if field is None:
        return None, stats
    med, w = mw
    stats["cells"] = int(w.sum())
    half = np.arange(len(Pm)) % 2 == 0
    cv_res = []
    for tr in (half, ~half):
        f_, _ = _field_grid(Pm[tr], R[tr], cur, p)
        if f_ is not None:
            cv_res.append(np.linalg.norm(R[~tr] - _field_eval(f_, Pm[~tr]), axis=1))
    after = _robust_rms(np.concatenate(cv_res)) * cur.gsd if cv_res else before
    F = np.stack([np.asarray(field["dx"]), np.asarray(field["dy"])], -1)
    stats.update(after_mm=after, max_mm=float(np.linalg.norm(F, axis=-1).max()) * cur.gsd)
    return field, stats


def register(prev, cur, p, log):
    """_Scan 두 개 → 정합 결과 dict (M: 3×3 직전 px → 이번 px, field: 국소 보정장 또는 None). 실패면 ok=False, M=None"""
    t0 = time.time()
    s0 = prev.gsd / cur.gsd
    have_img = prev.img is not None and cur.img is not None
    mk, info = _register_markers(prev, cur, p, log)
    ft = _register_features(prev, cur, p, log) if have_img else None
    if ft is not None and not ft["ok"]:
        log(f"registration: image features not usable ({ft.get('reason')})")

    def strong(f):
        return f is not None and f["ok"] and not f.get("coarse_only") and f["n"] >= 3 * p["feat_min_inliers"] and f["spread"] >= 0.2

    reg = None
    if mk is not None and mk["ok"]:
        reg = mk
        if ft is not None and ft["ok"]:
            rms_d, max_d = _disagree_mm(mk["M"], ft["M"], prev, cur, p)
            reg.update(check_mm=rms_d, check_max_mm=max_d)
            if rms_d is not None and rms_d > p["marker_check_mm"]:
                log(f"registration: markers and image disagree by {rms_d:.1f} mm (max {max_d:.1f})"
                    + (" - using image features" if strong(ft) else " - keeping markers (image match weak)"))
                if strong(ft):
                    reg = dict(ft, check_mm=rms_d, check_max_mm=max_d, warning="markers_disagree", marker_ids=mk["ids"])
                else:
                    reg["warning"] = "image_disagrees"
            elif ft.get("P") is not None:
                reg.update(P=ft["P"], Q=ft["Q"])
        elif ft is not None:
            reg["warning"] = "image_check_failed"
    elif ft is not None and ft["ok"]:
        reg = ft
        if mk is not None:
            reg["markers_rejected"] = mk.get("reason")
    if reg is None:
        reasons = [x.get("reason") for x in (mk, ft) if x is not None and x.get("reason")]
        if mk is None and len(info.get("common_ids", [])) < 2 and not have_img:
            reasons.append("fewer than 2 common markers and no images")
        elif mk is None and not have_img:
            reasons.append("no images")
        fail = dict(method="none", M=None, n=0, rms_mm=None, ok=False, markers_common=info.get("common_ids", []),
                    reason="; ".join(reasons) or "no registration")
        fail["seconds"] = time.time() - t0
        return fail
    # 전체 겹친 영역의 잔차(영상 짝 기준, 강건 rms)와 국소 보정장
    reg["field"] = None
    if reg.get("P") is not None:
        if reg["method"] == "features":
            M2 = _refit_global(reg["P"], reg["Q"], reg["M"], reg.get("model"), cur, p)
            if abs(_lin_scale(M2) / s0 - 1) <= p["scale_tol"]:
                reg["M"] = M2
        field, fs = _local_field(reg["P"], reg["Q"], reg["M"], cur, p)
        if fs.get("before_mm") is not None:
            reg["rms_mm"] = max(reg.get("rms_mm") or 0.0, fs["before_mm"]) if reg["method"] == "markers" else fs["before_mm"]
            reg["field_stats"] = fs
        if field is not None and p["local_field"] and fs["after_mm"] < 0.85 * fs["before_mm"] and fs["max_mm"] >= 0.25:
            # 2차: 보정장을 넣어 직전 영상을 다시 표본화하면 뒤틀림이 큰 곳의 짝도 공간 제약을 통과한다 → 보정장 다시
            try:
                r2 = _refine(prev, cur, reg["M"], p, lambda m: None, r_px=8.0, field=field, fit=False)
            except cv2.error:
                r2 = None
            if r2 is not None:
                f2, fs2 = _local_field(r2["P"], r2["Q"], reg["M"], cur, p)
                if f2 is not None and fs2.get("after_mm") is not None and fs2["after_mm"] < fs["after_mm"]:
                    field, fs = f2, dict(fs2, before_mm=max(fs["before_mm"], fs2["before_mm"]), passes=2)
            reg["field"] = field
            reg["field_stats"] = fs
            reg["local_rms_mm"] = fs["after_mm"]
            if reg["method"] != "markers":
                reg["rms_mm"] = fs["before_mm"]
            log(f"registration: local field {len(field['dx'][0])}x{len(field['dx'])} cells ({fs.get('passes', 1)} pass), "
                f"residual {fs['before_mm']:.2f} -> {fs['after_mm']:.2f} mm (max correction {fs['max_mm']:.2f} mm)")
    reg.pop("P", None)
    reg.pop("Q", None)
    reg["seconds"] = time.time() - t0
    return reg


def transform_points(registration, pts):
    """changes.json 의 registration(matrix + field) 으로 직전 정사영상 px → 이번 정사영상 px"""
    M = np.asarray(registration["matrix"], float)
    q = _apply(M, pts)
    if registration.get("field"):
        q = q + _field_eval(registration["field"], q)
    return q


# ───────────────────────── 항목 준비 ─────────────────────────
def _items(h, typ):
    return [it for it in h.get("items") or [] if it.get("type") == typ]


def _num(d, k):
    v = (d or {}).get(k)
    try:
        v = float(v)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def _crack_prep(it, scan, f, p, common, cur):
    """f: 직전 px → 이번 px 함수(직전 항목) 또는 None(이번 항목)"""
    parts = _parts(it.get("geom"))
    step = p["crack_step_mm"] / scan.gsd
    pts, w, pid = _resample(parts, step)
    w = w * scan.gsd                                                   # mm
    if f is not None:
        pts = f(pts)
        parts_c = [f(np.asarray(a, float).reshape(-1, 2)) for a in parts]
    else:
        parts_c = [np.asarray(a, float).reshape(-1, 2) for a in parts]
    m = it.get("metrics") or {}
    L = _num(m, "length_mm")
    geo_len = float(w.sum())
    inside = _inside(common, cur.cell, pts) if common is not None else np.zeros(len(pts), bool)
    bb = (pts.min(0), pts.max(0)) if len(pts) else (np.zeros(2), np.zeros(2))
    return dict(id=it.get("id"), it=it, pts=pts, w=w, pid=pid, parts=parts_c, len=L if L is not None else geo_len, geo_len=geo_len,
                wmax=_num(m, "width_max_mm"), wmed=_num(m, "width_median_mm"), src=m.get("width_source"),
                sev=it.get("severity"), inside=inside,
                fin=float(w[inside].sum() / geo_len) if geo_len > 0 else (1.0 if inside.all() and len(inside) else 0.0),
                lin=float(w[inside].sum()), bb=bb)


def _poly_prep(it, scan, f, p, common, cur):
    rings = _rings(it.get("geom"))
    if f is not None:
        rings = [f(rg) for rg in rings]
    m = it.get("metrics") or {}
    if rings:
        allp = np.concatenate(rings)
        bb = (allp.min(0), allp.max(0))
    else:
        bb = (np.zeros(2), np.zeros(2))
    d = dict(id=it.get("id"), it=it, rings=rings, bb=bb, sev=it.get("severity"), sub=it.get("subtype"),
             area=_num(m, "area_mm2"), m=m)
    # 기하 넓이와 겹친 영역 안 비율 (1 mm 격자)
    r = p["poly_raster_mm"] / cur.gsd
    if rings:
        x0, y0 = bb[0] - r
        w_, h_ = int(math.ceil((bb[1][0] - x0) / r)) + 2, int(math.ceil((bb[1][1] - y0) / r)) + 2
        mk = _fill(rings, x0, y0, r, w_, h_)
        ys, xs = np.nonzero(mk)
        cpts = np.stack([x0 + (xs + 0.5) * r, y0 + (ys + 0.5) * r], 1)
        ins = _inside(common, cur.cell, cpts) if common is not None else np.zeros(len(cpts), bool)
        n = len(xs)
        d["geo_area"] = n * p["poly_raster_mm"] ** 2
        d["ain"] = float(ins.sum()) * p["poly_raster_mm"] ** 2
        if n == 0:                                                        # 1 mm 보다 작은 다각형: 무게중심으로
            c = np.concatenate(rings).mean(0, keepdims=True)
            d["fin"] = float(_inside(common, cur.cell, c)[0]) if common is not None else 0.0
        else:
            d["fin"] = float(ins.mean())
    else:
        d["geo_area"], d["ain"], d["fin"] = 0.0, 0.0, 0.0
    if d["area"] is None:
        d["area"] = d["geo_area"]
    return d


class _UF:
    def __init__(self):
        self.p = {}

    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def _groups(n_prev, n_cur, links):
    uf = _UF()
    for i in range(n_prev):
        uf.find(("p", i))
    for j in range(n_cur):
        uf.find(("c", j))
    for i, j in links:
        uf.union(("p", i), ("c", j))
    g = {}
    for k in list(uf.p):
        g.setdefault(uf.find(k), ([], []))
        (g[uf.find(k)][0] if k[0] == "p" else g[uf.find(k)][1]).append(k[1])
    return [(sorted(a), sorted(b)) for a, b in g.values()]


def _bb_hit(a, b, m):
    return not (a[1][0] + m < b[0][0] or b[1][0] + m < a[0][0] or a[1][1] + m < b[0][1] or b[1][1] + m < a[0][1])


# ───────────────────────── 판정 ─────────────────────────
def _status_from(grow, shrink):
    if grow:
        return "grown"
    if shrink:
        return "shrunk"
    return "stable"


def _sev(items):
    v = [x["sev"] for x in items if isinstance(x.get("sev"), (int, float))]
    return int(max(v)) if v else None


def _unmatched_or(status, frac, amount, p, amount_min):
    """한쪽에만 있는 항목: 겹친 영역 안에 충분히 있으면 status(new/repaired), 아니면 unmatched"""
    if frac >= p["new_inside_frac"] or amount >= amount_min:
        return status, None
    return "unmatched", ("outside_prev" if status == "new" else "outside_cur")


def _compare_cracks(prev_it, cur_it, prev, cur, fmap, reg_rms, common, p, ok):
    P = [_crack_prep(it, prev, fmap, p, common if ok else None, cur) for it in prev_it]
    C = [_crack_prep(it, cur, None, p, common if ok else None, cur) for it in cur_it]
    out = []
    if not ok:
        for c in C:
            out.append(_crack_rec([], [c], "unmatched", reason="registration_failed"))
        for q in P:
            out.append(_crack_rec([q], [], "unmatched", reason="registration_failed", geom=False))
        return out
    covP = [np.zeros(len(q["pts"]), bool) for q in P]                  # 이번 어느 균열 tol 안
    covC = [np.zeros(len(c["pts"]), bool) for c in C]
    tolP, tolC = [0.0] * len(P), [0.0] * len(C)
    links, pair = [], {}
    for i, q in enumerate(P):
        for j, c in enumerate(C):
            wv = [x for x in (q["wmax"], c["wmax"]) if x is not None]
            tol_mm = max(p["crack_tol_mm"], p["crack_tol_width_k"] * (max(wv) if wv else 0.0)) + p["tol_reg_k"] * (reg_rms or 0.0)
            tol = tol_mm / cur.gsd
            if not _bb_hit(q["bb"], c["bb"], tol) or len(q["pts"]) == 0 or len(c["pts"]) == 0:
                continue
            dP, dC = _min_dists(q["pts"], c["pts"])
            hp, hc = dP <= tol, dC <= tol
            if not hp.any():
                continue
            covP[i] |= hp
            covC[j] |= hc
            tolP[i], tolC[j] = max(tolP[i], tol_mm), max(tolC[j], tol_mm)
            ovP, ovC = float(q["w"][hp].sum()), float(c["w"][hc].sum())
            fP = ovP / q["geo_len"] if q["geo_len"] > 0 else 0.0
            fC = ovC / c["geo_len"] if c["geo_len"] > 0 else 0.0
            min_ov = min(2 * tol_mm, 0.8 * min(q["geo_len"], c["geo_len"]))   # 교차만 하는 균열은 겹침이 ~2·tol 뿐
            if (fP >= p["crack_link_frac"] or fC >= p["crack_link_frac"]) and min(ovP, ovC) >= min_ov:
                links.append((i, j))
                pair[(i, j)] = dict(fP=fP, fC=fC, tol_mm=tol_mm, dist_mm=float(np.median(dP[hp])) * cur.gsd)
    for ip, jc in _groups(len(P), len(C), links):
        gp, gc = [P[i] for i in ip], [C[j] for j in jc]
        if gp and gc:
            ext = sum(_uncovered(c, covC[j], tolC[j]) for j, c in zip(jc, gc))
            ret = sum(_uncovered(q, covP[i], tolP[i]) for i, q in zip(ip, gp))
            clipped = any(x["fin"] < p["inside_frac"] for x in gp + gc)
            if clipped:
                Lp, Lc = sum(x["lin"] for x in gp), sum(x["lin"] for x in gc)
            else:
                Lp, Lc = sum(x["len"] for x in gp), sum(x["len"] for x in gc)
            wp = [x["wmax"] for x in gp if x["wmax"] is not None]
            wc = [x["wmax"] for x in gc if x["wmax"] is not None]
            Wp, Wc = (max(wp) if wp else None), (max(wc) if wc else None)
            dL = Lc - Lp
            dW = (Wc - Wp) if (Wp is not None and Wc is not None) else None
            thr_w = max(p["width_abs_mm"], p["width_rel"] * (Wp or 0.0))
            reasons, shrink = [], []
            if dW is not None and dW > thr_w:
                reasons.append("width")
            if ext > p["length_mm"] and dL > p["length_mm"]:        # 새로 자란 부분 > 5 mm 이고 전체 길이도 > 5 mm
                reasons.append("length")
            if dW is not None and dW < -thr_w:
                shrink.append("width")
            if ret > p["length_mm"] and dL < -p["length_mm"]:
                shrink.append("length")
            st = _status_from(reasons, shrink)
            mi = [pair[(i, j)] for i in ip for j in jc if (i, j) in pair]
            rec = _crack_rec(gp, gc, st, reasons=reasons or shrink,
                             delta=dict(length_mm=_r(dL, 1), width_max_mm=_r(dW, 3), extension_mm=_r(ext, 1), retraction_mm=_r(ret, 1)),
                             Lp=Lp, Lc=Lc, clipped=clipped,
                             match=dict(cover_prev=_r(max(m["fP"] for m in mi), 2), cover_cur=_r(max(m["fC"] for m in mi), 2),
                                        dist_mm=_r(float(np.median([m["dist_mm"] for m in mi])), 2), tol_mm=_r(mi[0]["tol_mm"], 2)))
            out.append(rec)
        elif gc:
            for c in gc:
                st, why = _unmatched_or("new", c["fin"], c["lin"], p, p["new_inside_mm"])
                out.append(_crack_rec([], [c], st, reason=why))
        else:
            for q in gp:
                st, why = _unmatched_or("repaired", q["fin"], q["lin"], p, p["new_inside_mm"])
                out.append(_crack_rec([q], [], st, reason=why))
    return out


def _uncovered(x, cov, tol_mm, min_run_mm=1.0):
    """덮이지 않은 길이(겹친 영역 안만). 덮인 점과 맞닿은 끝마다 tol 을 더한다 — 덮임 판정이 반경 tol 이라
    직전 끝에서 이어 자란 부분의 처음 tol 만큼은 '덮임'으로 잡혀 연장이 tol 만큼 짧게 나오는 것을 보정"""
    total = 0.0
    if len(x["pts"]) == 0:
        return 0.0
    unc = ~cov
    for k in np.unique(x["pid"]):
        idx = np.nonzero(x["pid"] == k)[0]
        d = np.diff(np.concatenate([[0], unc[idx].astype(np.int8), [0]]))
        for s, e in zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]):
            seg = idx[s:e]
            L = float(x["w"][seg][x["inside"][seg]].sum())
            if L < min_run_mm:
                continue
            adj = int(s > 0 and cov[idx[s - 1]]) + int(e < len(idx) and cov[idx[e]])
            total += L + adj * tol_mm
    return total


def _crack_side(g, L=None):
    if not g:
        return None
    w = [x["wmax"] for x in g if x["wmax"] is not None]
    wm = [x["wmed"] for x in g if x["wmed"] is not None]
    src = sorted({x["src"] for x in g if x["src"]})
    return dict(length_mm=_r(L if L is not None else sum(x["len"] for x in g), 1), width_max_mm=_r(max(w), 3) if w else None,
                width_median_mm=_r(float(np.median(wm)), 3) if wm else None, width_source="/".join(src) or None,
                severity=_sev(g), n=len(g))


def _crack_rec(gp, gc, status, reasons=None, delta=None, Lp=None, Lc=None, clipped=False, match=None, reason=None, geom=True):
    gp = sorted(gp, key=lambda x: -x["geo_len"])
    gc = sorted(gc, key=lambda x: -x["geo_len"])
    rec = dict(type="crack", cur_id=gc[0]["id"] if gc else None, prev_id=gp[0]["id"] if gp else None,
               cur_ids=[x["id"] for x in gc], prev_ids=[x["id"] for x in gp], status=status, reasons=reasons or [],
               delta=delta, prev=_crack_side(gp, Lp), cur=_crack_side(gc, Lc))
    if clipped:
        rec["clipped"] = True
    if match:
        rec["match"] = match
    if reason:
        rec["reason"] = reason
    if gp and geom:
        rec["prev_geom"] = dict(type="polyline", parts=sum((_simplify_parts(x["parts"]) for x in gp), []))
    return rec


def _compare_polys(typ, prev_it, cur_it, prev, cur, fmap, common, p, ok):
    P = [_poly_prep(it, prev, fmap, p, common if ok else None, cur) for it in prev_it]
    C = [_poly_prep(it, cur, None, p, common if ok else None, cur) for it in cur_it]
    out = []
    if not ok:
        out += [_poly_rec(typ, [], [c], "unmatched", reason="registration_failed") for c in C]
        out += [_poly_rec(typ, [q], [], "unmatched", reason="registration_failed", geom=False) for q in P]
        return out
    r = p["poly_raster_mm"] / cur.gsd
    links, pair = [], {}
    for i, q in enumerate(P):
        for j, c in enumerate(C):
            if not q["rings"] or not c["rings"] or not _bb_hit(q["bb"], c["bb"], r):
                continue
            x0 = min(q["bb"][0][0], c["bb"][0][0]) - r
            y0 = min(q["bb"][0][1], c["bb"][0][1]) - r
            w_ = int(math.ceil((max(q["bb"][1][0], c["bb"][1][0]) - x0) / r)) + 2
            h_ = int(math.ceil((max(q["bb"][1][1], c["bb"][1][1]) - y0) / r)) + 2
            a, b = _fill(q["rings"], x0, y0, r, w_, h_) > 0, _fill(c["rings"], x0, y0, r, w_, h_) > 0
            inter, uni = float((a & b).sum()), float((a | b).sum())
            if inter == 0:
                continue
            iou = inter / uni
            cover = inter / max(1.0, min(float(a.sum()), float(b.sum())))
            if iou >= p["poly_link_iou"] or cover >= p["poly_link_cover"]:
                links.append((i, j))
                pair[(i, j)] = dict(iou=iou, cover=cover)
    for ip, jc in _groups(len(P), len(C), links):
        gp, gc = [P[i] for i in ip], [C[j] for j in jc]
        if gp and gc:
            allb = [x["bb"] for x in gp + gc]
            x0 = min(b[0][0] for b in allb) - r
            y0 = min(b[0][1] for b in allb) - r
            w_ = int(math.ceil((max(b[1][0] for b in allb) - x0) / r)) + 2
            h_ = int(math.ceil((max(b[1][1] for b in allb) - y0) / r)) + 2
            a = _fill(sum((x["rings"] for x in gp), []), x0, y0, r, w_, h_) > 0
            b = _fill(sum((x["rings"] for x in gc), []), x0, y0, r, w_, h_) > 0
            ys, xs = np.nonzero(a | b)
            ins = np.zeros_like(a)
            ins[ys, xs] = _inside(common, cur.cell, np.stack([x0 + (xs + 0.5) * r, y0 + (ys + 0.5) * r], 1))
            px_mm2 = p["poly_raster_mm"] ** 2
            expn = float((b & ~a & ins).sum()) * px_mm2
            retr = float((a & ~b & ins).sum()) * px_mm2
            clipped = any(x["fin"] < p["inside_frac"] for x in gp + gc)
            if clipped:
                Ap, Ac = float((a & ins).sum()) * px_mm2, float((b & ins).sum()) * px_mm2
            else:
                Ap, Ac = sum(x["area"] for x in gp), sum(x["area"] for x in gc)
            dA = Ac - Ap
            thr = max(p["area_rel"] * Ap, p["area_abs_mm2"])
            reasons, shrink = [], []
            if dA > thr:
                reasons.append("area")
            if dA < -thr:
                shrink.append("area")
            delta = dict(area_mm2=_r(dA, 0), area_pct=_r(100 * dA / Ap, 1) if Ap > 0 else None, expansion_mm2=_r(expn, 0),
                         retraction_mm2=_r(retr, 0))
            if typ == "relief":
                dp = [_num(x["m"], "depth_max_mm") for x in gp]
                dc = [_num(x["m"], "depth_max_mm") for x in gc]
                dp = [v for v in dp if v is not None]
                dc = [v for v in dc if v is not None]
                if dp and dc:
                    Dp, Dc = max(dp, key=abs), max(dc, key=abs)
                    delta["depth_max_mm"] = _r(Dc - Dp, 1)
                    thr_d = max(p["depth_abs_mm"], p["depth_rel"] * abs(Dp))
                    if abs(Dc) - abs(Dp) > thr_d:
                        reasons.append("depth")
                    elif abs(Dc) - abs(Dp) < -thr_d:
                        shrink.append("depth")
                vp = [_num(x["m"], "volume_cm3") for x in gp]
                vc = [_num(x["m"], "volume_cm3") for x in gc]
                if all(v is not None for v in vp + vc) and vp and vc:
                    delta["volume_cm3"] = _r(sum(vc) - sum(vp), 1)
            if typ == "stain":
                for k in ("dL", "da", "db"):
                    a_, b_ = _num(gp[0]["m"], k), _num(gc[0]["m"], k)
                    if a_ is not None and b_ is not None:
                        delta[k] = _r(b_ - a_, 1)
            st = _status_from(reasons, shrink)
            mi = [pair[(i, j)] for i in ip for j in jc if (i, j) in pair]
            out.append(_poly_rec(typ, gp, gc, st, reasons=reasons or shrink, delta=delta, Ap=Ap, Ac=Ac, clipped=clipped,
                                 match=dict(iou=_r(max(m["iou"] for m in mi), 2), cover=_r(max(m["cover"] for m in mi), 2))))
        elif gc:
            for c in gc:
                st, why = _unmatched_or("new", c["fin"], c["ain"], p, p["new_inside_mm2"])
                out.append(_poly_rec(typ, [], [c], st, reason=why))
        else:
            for q in gp:
                st, why = _unmatched_or("repaired", q["fin"], q["ain"], p, p["new_inside_mm2"])
                out.append(_poly_rec(typ, [q], [], st, reason=why))
    return out


def _poly_side(typ, g, A=None):
    if not g:
        return None
    d = dict(area_mm2=_r(A if A is not None else sum(x["area"] for x in g), 0), subtype=g[0]["sub"], severity=_sev(g), n=len(g))
    if typ == "relief":
        dv = [_num(x["m"], "depth_max_mm") for x in g]
        dv = [v for v in dv if v is not None]
        d["depth_max_mm"] = _r(max(dv, key=abs), 1) if dv else None
        vv = [_num(x["m"], "volume_cm3") for x in g]
        d["volume_cm3"] = _r(sum(vv), 1) if vv and all(v is not None for v in vv) else None
    if typ == "stain":
        for k in ("dL", "da", "db"):
            d[k] = _r(_num(g[0]["m"], k), 1)
    return d


def _poly_rec(typ, gp, gc, status, reasons=None, delta=None, Ap=None, Ac=None, clipped=False, match=None, reason=None, geom=True):
    gp = sorted(gp, key=lambda x: -x["geo_area"])
    gc = sorted(gc, key=lambda x: -x["geo_area"])
    rec = dict(type=typ, cur_id=gc[0]["id"] if gc else None, prev_id=gp[0]["id"] if gp else None,
               cur_ids=[x["id"] for x in gc], prev_ids=[x["id"] for x in gp], status=status, reasons=reasons or [],
               delta=delta, prev=_poly_side(typ, gp, Ap), cur=_poly_side(typ, gc, Ac))
    if gp and gc and gp[0]["sub"] != gc[0]["sub"]:
        rec["subtype_changed"] = True
    if clipped:
        rec["clipped"] = True
    if match:
        rec["match"] = match
    if reason:
        rec["reason"] = reason
    if gp and geom:
        rec["prev_geom"] = dict(type="polygon", rings=sum((_simplify_rings(x["rings"]) for x in gp), []))
    return rec


def _compare_deform(prev_it, cur_it, p):
    out = []
    by_p, by_c = {}, {}
    for it in prev_it:
        by_p.setdefault(it.get("subtype"), []).append(it)
    for it in cur_it:
        by_c.setdefault(it.get("subtype"), []).append(it)
    for sub in sorted(set(by_p) | set(by_c), key=str):
        lp, lc = by_p.get(sub, []), by_c.get(sub, [])
        for k in range(max(len(lp), len(lc))):
            a = lp[k] if k < len(lp) else None
            b = lc[k] if k < len(lc) else None
            ma, mb = (a or {}).get("metrics") or {}, (b or {}).get("metrics") or {}
            rec = dict(type="deformation", subtype=sub, cur_id=(b or {}).get("id"), prev_id=(a or {}).get("id"),
                       cur_ids=[b["id"]] if b else [], prev_ids=[a["id"]] if a else [], reasons=[],
                       prev=dict(ma) if a else None, cur=dict(mb) if b else None, delta=None)
            if a and b:
                delta, reasons, shrink = {}, [], []
                for key in sorted(set(ma) & set(mb)):
                    va, vb = _num(ma, key), _num(mb, key)
                    if va is not None and vb is not None:
                        delta[key] = _r(vb - va, 3)
                for key in ("tilt_deg", "lean_deg", "slope_deg"):         # 계약 예시 tilt_deg, hazard_detect 는 벽 lean_deg·바닥 slope_deg
                    va, vb = _num(ma, key), _num(mb, key)
                    if va is not None and vb is not None:
                        d = abs(vb) - abs(va)
                        (reasons if d > p["tilt_deg"] else shrink if d < -p["tilt_deg"] else []).append(key[:-4])
                va, vb = _num(ma, "flatness_rms_mm"), _num(mb, "flatness_rms_mm")
                if va is not None and vb is not None:
                    thr = max(p["flatness_abs_mm"], p["flatness_rel"] * va)
                    d = vb - va
                    (reasons if d > thr else shrink if d < -thr else []).append("flatness")
                rec["status"] = _status_from(reasons, shrink)
                rec["reasons"] = reasons or shrink
                rec["delta"] = delta
            else:
                rec["status"] = "new" if b else "repaired"
            out.append(rec)
    return out


def _confidence(rec, reg_rms, p):
    """판정 믿음 정도: high/low 와 이유 코드 (계약 v1 에 없는 보조 정보)"""
    why = []
    if rec["status"] == "unmatched":
        return None, []
    if reg_rms is not None and reg_rms > p["low_conf_reg_mm"]:
        why.append("registration")
    if rec.get("clipped"):
        why.append("clipped")
    if rec["type"] == "crack":
        srcs = {(rec.get(k) or {}).get("width_source") for k in ("prev", "cur") if rec.get(k)}
        srcs.discard(None)
        if "width" in rec.get("reasons", []) or rec["status"] in ("new", "repaired", "stable"):
            if any(s_ != "photo" for s_ in srcs):
                why.append("ortho_width")             # 정사영상 단면 폭: 0.1 mm 단위 비교에는 부족
            if len(srcs) > 1:
                why.append("width_source_mixed")
        w = [(rec.get(k) or {}).get("width_max_mm") for k in ("prev", "cur")]
        if any(x is not None and x < 0.2 for x in w):
            why.append("thin")
    return ("low" if why else "high"), why


def _significant(rec):
    if rec["status"] in ("new", "grown", "shrunk", "repaired"):
        return True
    if rec["status"] == "stable":
        sp = (rec.get("prev") or {}).get("severity")
        sc = (rec.get("cur") or {}).get("severity")
        if isinstance(sp, (int, float)) and isinstance(sc, (int, float)) and sc > sp:
            return True
        return bool(rec.get("subtype_changed"))
    return False


def _safe_log(log):
    """로그 함수가 cp949 콘솔 print 여도 죽지 않게 (경로·예외 글에 한글이 섞일 수 있다)"""
    def f(m):
        try:
            log(m)
        except UnicodeEncodeError:
            log(m.encode("ascii", "backslashreplace").decode())
    return f


def _overlap_rings(common, cell, gsd, min_mm2=400.0):
    """겹친 영역(비교한 곳) 윤곽 — 이번 정사영상 px 다각형(바깥·구멍 고리, 짝홀 규칙). 표시용이라 min_mm2 보다 작은 조각·구멍은 뺀다"""
    cnts, _ = cv2.findContours(common.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    rings = []
    min_cells = min_mm2 / (cell * gsd) ** 2
    for c in cnts:
        if len(c) < 3 or cv2.contourArea(c) < min_cells:
            continue
        c = cv2.approxPolyDP(c, 1.0, True).reshape(-1, 2)
        rings.append([[round((float(x) + 0.5) * cell, 1), round((float(y) + 0.5) * cell, 1)] for x, y in c])
    return rings


# ───────────────────────── 본체 ─────────────────────────
def compare(prev_hazards, cur_hazards, prev_img=None, cur_img=None, log=print, params=None, debug=None):
    """직전·이번 hazards(dict 또는 경로)와 정사영상(BGR ndarray 또는 경로, 선택) → changes.json dict (계약 §3)
    params: DEFAULTS 덮어쓰기. debug: 확인용 그림 경로(jpg)."""
    t0 = time.time()
    log = _safe_log(log)
    p = dict(DEFAULTS, **(params or {}))
    ph, ch = _load_json(prev_hazards), _load_json(cur_hazards)
    imgs = []
    for nm, x in (("prev", prev_img), ("cur", cur_img)):
        try:
            imgs.append(_load_img(x))
        except (ValueError, OSError, cv2.error) as e:
            log(f"{nm} image not used: {e}")
            imgs.append(None)
    prev = _Scan(ph, imgs[0], p, "prev")
    cur = _Scan(ch, imgs[1], p, "cur")
    notes = []
    if ph.get("site_id") and ch.get("site_id") and ph["site_id"] != ch["site_id"]:
        notes.append(f"site_id 다름({ph['site_id']} ≠ {ch['site_id']})")
    if ph.get("surface") and ch.get("surface") and ph["surface"] != ch["surface"]:
        notes.append(f"면 종류 다름({ph['surface']} ≠ {ch['surface']})")
    log(f"compare: prev {ph.get('job_id')} {prev.W}x{prev.H} @ {prev.gsd:.3f} mm/px, cur {ch.get('job_id')} {cur.W}x{cur.H} "
        f"@ {cur.gsd:.3f} mm/px")

    reg = register(prev, cur, p, log)
    ok = bool(reg["ok"])
    M = reg["M"]
    field = reg.get("field")
    common = _common(prev, cur, M, p) if ok else None
    reg_rms = (reg.get("local_rms_mm") if field else reg.get("rms_mm")) or 0.0

    def fmap(pts):
        q = _apply(M, pts)
        return q + _field_eval(field, q) if field else q

    fm = fmap if ok else None
    items = []
    items += _compare_cracks(_items(ph, "crack"), _items(ch, "crack"), prev, cur, fm, reg_rms, common, p, ok)
    for typ in ("stain", "relief"):
        items += _compare_polys(typ, _items(ph, typ), _items(ch, typ), prev, cur, fm, common, p, ok)
    items += _compare_deform(_items(ph, "deformation"), _items(ch, "deformation"), p)
    known = set(TYPE_ORDER)
    other = sorted({it.get("type") for it in (ph.get("items") or []) + (ch.get("items") or [])} - known, key=str)
    if other:
        notes.append(f"비교하지 않은 유형: {', '.join(map(str, other))}")
    for rec in items:
        rec["significant"] = _significant(rec)
        if rec["type"] != "deformation":
            c, why = _confidence(rec, reg_rms if ok else None, p)
            if c:
                rec["confidence"] = c
                if why:
                    rec["confidence_why"] = why
    items.sort(key=lambda r: (TYPE_ORDER.index(r["type"]), STATUS_ORDER.index(r["status"]), str(r.get("cur_id") or r.get("prev_id"))))

    counts = {s: sum(1 for r in items if r["status"] == s) for s in STATUS_ORDER}
    by_type = {}
    for r in items:
        by_type.setdefault(r["type"], {s: 0 for s in STATUS_ORDER})[r["status"]] += 1
    if not ok:
        notes.insert(0, f"정합 실패({reg.get('reason', '')}) — 변화를 판정하지 않음(형상 없는 변형 항목만 비교)")
    else:
        mm = f"{reg['rms_mm']:.2f} mm" if reg.get("rms_mm") is not None else "-"
        notes.insert(0, f"정합 {reg['method']}({reg.get('model')}) n={reg['n']} rms {mm}")
        if reg.get("field"):
            notes.append(f"국소 보정 {reg['field_stats']['before_mm']:.2f} → {reg['local_rms_mm']:.2f} mm")
        if reg.get("dropped"):
            notes.append(f"고정 표식 {reg['dropped']} 은 다른 표식과 거리가 맞지 않아 뺌 — 옮겨 붙였는지 확인")
        if reg.get("warning") == "markers_disagree":
            notes.append(f"고정 표식과 영상 정합이 {reg['check_mm']:.1f} mm 다름 — 영상 정합을 씀, 표식을 옮겨 붙였는지 확인")
        elif reg.get("warning") == "image_disagrees":
            notes.append(f"영상 정합이 고정 표식과 {reg['check_mm']:.1f} mm 다름(영상 짝 약함) — 표식 정합을 씀")
        if abs(reg.get("scale", 1.0) - 1) > 0.03:
            notes.append(f"두 스캔 축척 차 {100 * (reg['scale'] - 1):+.1f}% (gsd 비 대비) — 한쪽 축척 오차 의심")
    if ok:
        ov = float(common.sum()) / max(1.0, float(cur.cov.sum())) * 100
        if ov < 30:
            notes.append(f"겹친 영역이 이번 스캔의 {ov:.0f}% 뿐")
    out = dict(
        version=VERSION,
        site_id=ch.get("site_id") or ph.get("site_id"),
        prev_job=ph.get("job_id"), cur_job=ch.get("job_id"),
        prev_captured_at=ph.get("captured_at"), cur_captured_at=ch.get("captured_at"),
        registration=dict(
            method=reg["method"],
            matrix=[[round(float(v), 9) for v in row] for row in M] if M is not None else None,
            rms_mm=_r(reg.get("rms_mm"), 3), n=int(reg.get("n") or 0), ok=ok,
            model=reg.get("model"), scale_vs_gsd=_r(reg.get("scale"), 5), spread=_r(reg.get("spread"), 3),
            inlier_rms_mm=_r(reg.get("inlier_rms_mm"), 3), marker_rms_mm=_r(reg.get("marker_rms_mm"), 3),
            local_rms_mm=_r(reg.get("local_rms_mm"), 3) if field else None,
            check_mm=_r(reg.get("check_mm"), 2), check_max_mm=_r(reg.get("check_max_mm"), 2), warning=reg.get("warning"),
            marker_ids=reg.get("ids") or reg.get("marker_ids"), markers_dropped=reg.get("dropped") or None,
            markers_rejected=reg.get("markers_rejected"),
            overlap_pct=_r(float(common.sum()) / max(1.0, float(cur.cov.sum())) * 100, 1) if ok else None,
            field=field, reason=reg.get("reason"), seconds=_r(reg.get("seconds"), 2),
        ),
        overlap=dict(rings=_overlap_rings(common, cur.cell, cur.gsd)) if ok else None,
        items=items,
        summary=dict(counts, by_type=by_type, significant=sum(1 for r in items if r["significant"]), note="; ".join(notes)),
        frame=dict(width=cur.W, height=cur.H, gsd_mm=_r(cur.gsd, 5), prev_gsd_mm=_r(prev.gsd, 5)),
        params={k: p[k] for k in ("width_abs_mm", "width_rel", "length_mm", "area_rel", "area_abs_mm2", "crack_tol_mm",
                                  "crack_tol_width_k", "tol_reg_k", "depth_abs_mm", "depth_rel", "tilt_deg", "flatness_abs_mm",
                                  "flatness_rel")},
        seconds=_r(time.time() - t0, 2),
    )
    out["registration"] = {k: v for k, v in out["registration"].items() if v is not None or k in ("matrix", "rms_mm", "field")}
    log("compare: " + ", ".join(f"{s} {counts[s]}" for s in STATUS_ORDER if counts[s])
        + f" | registration {reg['method']} ok={ok} rms={out['registration']['rms_mm']} mm ({out['seconds']}s)")
    if debug:
        try:
            draw_debug(out, ch, imgs[1], debug)
            log(f"compare: debug image {debug}")
        except Exception as e:                                   # 그림은 부가 기능 — 실패해도 결과는 낸다
            log(f"compare: debug image failed: {e}")
    return out


# ───────────────────────── 확인용 그림 ─────────────────────────
COLORS = dict(new=(40, 40, 230), grown=(0, 140, 255), stable=(60, 190, 60), shrunk=(200, 170, 0), repaired=(230, 110, 30),
              unmatched=(200, 60, 200), prev=(175, 175, 175), overlap=(0, 220, 255))


def _dashed(img, pts, color, th, on=8, off=6):
    pts = np.asarray(pts, float)
    if len(pts) < 2:
        return
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(seg)])
    L = cum[-1]
    s = 0.0
    while s < L:
        e = min(L, s + on)
        t = np.linspace(s, e, max(2, int((e - s) / 2) + 2))
        q = np.stack([np.interp(t, cum, pts[:, 0]), np.interp(t, cum, pts[:, 1])], 1)
        cv2.polylines(img, [np.round(q * 4).astype(np.int32).reshape(-1, 1, 2)], False, color, th, cv2.LINE_AA, shift=2)
        s += on + off


def _poly(img, pts, color, th, closed=False, dashed=False):
    pts = np.asarray(pts, float).reshape(-1, 2)
    if len(pts) < 2:
        return
    if dashed:
        _dashed(img, np.vstack([pts, pts[:1]]) if closed else pts, color, th)
    else:
        cv2.polylines(img, [np.round(pts * 4).astype(np.int32).reshape(-1, 1, 2)], closed, color, th, cv2.LINE_AA, shift=2)


def draw_debug(changes, cur_hazards, cur_img, path, max_px=2400):
    """이번 정사영상 위에 직전 형상(옮긴 것, 가는 회색)과 이번 항목(상태별 색), 보수됨(파란 점선)"""
    ch = _load_json(cur_hazards)
    fr = ch.get("frame") or {}
    img = _load_img(cur_img)
    W, H = int(fr.get("width") or img.shape[1]), int(fr.get("height") or img.shape[0])
    s = min(1.0, max_px / max(W, H))
    if img is None:
        vis = np.full((int(H * s), int(W * s), 3), 60, np.uint8)
    else:
        vis = cv2.resize(img, (int(round(W * s)), int(round(H * s))), interpolation=cv2.INTER_AREA)
        vis = (vis.astype(np.float32) * 0.75 + 30).clip(0, 255).astype(np.uint8)
    byid = {it.get("id"): it for it in ch.get("items") or []}
    th = 2 if s < 0.7 else 3

    def geom_draw(g, color, t, dashed=False):
        if not g:
            return
        if g.get("type") == "polyline":
            for a in g.get("parts") or []:
                _poly(vis, np.asarray(a, float) * s, color, t, dashed=dashed)
        elif g.get("type") == "polygon":
            for a in g.get("rings") or []:
                _poly(vis, np.asarray(a, float) * s, color, t, closed=True, dashed=dashed)

    for r in changes["items"]:                                     # 직전(회색, 가늘게)
        if r.get("prev_geom") and r["status"] != "repaired":
            geom_draw(r["prev_geom"], COLORS["prev"], 1)
    for rg in (changes.get("overlap") or {}).get("rings") or []:          # 비교한 곳(두 스캔이 겹친 곳)
        _poly(vis, np.asarray(rg, float) * s, (0, 220, 255), 1, closed=True)
    for m in ch.get("markers") or []:
        c = m.get("corners_px")
        if c:
            _poly(vis, np.asarray(c, float) * s, (255, 255, 0), 1, closed=True)
    for r in changes["items"]:
        col = COLORS[r["status"]]
        if r["status"] == "repaired":
            geom_draw(r.get("prev_geom"), col, th, dashed=True)
        for cid in r.get("cur_ids") or []:
            geom_draw((byid.get(cid) or {}).get("geom"), col, th)
        bb = None
        if r.get("cur_ids"):
            bbs = [byid[c]["bbox"] for c in r["cur_ids"] if c in byid and byid[c].get("bbox")]
            if bbs:
                bb = [min(b[0] for b in bbs), min(b[1] for b in bbs)]
        if bb is None and r.get("prev_geom"):
            g = r["prev_geom"]
            pts = np.concatenate([np.asarray(a, float) for a in (g.get("parts") or g.get("rings") or [])])
            bb = pts.min(0).tolist()
        if bb is None or r["type"] == "deformation":
            continue
        d = r.get("delta") or {}
        tag = r["status"]
        if r["status"] in ("grown", "shrunk"):
            if "width" in r["reasons"]:
                tag += f" w{d.get('width_max_mm', 0):+.2f}"
            if "length" in r["reasons"]:
                tag += f" +{d.get('extension_mm', 0):.0f}mm"
            if "area" in r["reasons"]:
                tag += f" {d.get('area_pct', 0):+.0f}%"
        label = f"{r.get('cur_id') or r.get('prev_id')} {tag}"
        org = (int(bb[0] * s), max(12, int(bb[1] * s) - 4))
        cv2.putText(vis, label, org, cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(vis, label, org, cv2.FONT_HERSHEY_SIMPLEX, 0.45, col, 1, cv2.LINE_AA)
    reg = changes["registration"]
    lines = [f"registration {reg['method']} ok={reg['ok']} n={reg['n']} rms={reg.get('rms_mm')} mm"]
    sm = changes["summary"]
    lines.append("  ".join(f"{k} {sm[k]}" for k in STATUS_ORDER if sm.get(k)))
    for i, k in enumerate(["new", "grown", "stable", "shrunk", "repaired", "unmatched", "prev", "overlap"]):
        lines.append(("  " if i else "") + k)
    y = 18
    cv2.rectangle(vis, (4, 4), (max(300, 8 * max(len(t) for t in lines[:2])), 18 * len(lines) + 6), (25, 25, 25), -1)
    for i, t in enumerate(lines):
        col = (255, 255, 255) if i < 2 else COLORS[t.strip()]
        if i >= 2:
            if t.strip() == "repaired":
                _dashed(vis, np.array([[10.0, y - 5], [40.0, y - 5]]), col, 2, on=5, off=3)
            else:
                cv2.line(vis, (10, y - 5), (40, y - 5), col, 1 if t.strip() in ("prev", "overlap") else 2)
            cv2.putText(vis, t.strip(), (48, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, col, 1, cv2.LINE_AA)
        else:
            cv2.putText(vis, t, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, col, 1, cv2.LINE_AA)
        y += 18
    ok, buf = cv2.imencode(".jpg", vis, [cv2.IMWRITE_JPEG_QUALITY, 88])
    buf.tofile(path)


def main():
    ap = argparse.ArgumentParser(description="kgeoScan hazard change comparison (prev scan -> current scan)")
    ap.add_argument("--prev", required=True, help="previous <job>_hazards.json")
    ap.add_argument("--prev-img", help="previous <job>_ortho.jpg")
    ap.add_argument("--cur", required=True, help="current <job>_hazards.json")
    ap.add_argument("--cur-img", help="current <job>_ortho.jpg")
    ap.add_argument("--out", required=True, help="<job>_changes.json")
    ap.add_argument("--debug", help="debug overlay jpg")
    ap.add_argument("--params", help="JSON object overriding DEFAULTS")
    a = ap.parse_args()
    t0 = time.time()
    log = lambda m: print(f"[{time.time() - t0:6.1f}s] {m}".encode("ascii", "replace").decode(), flush=True)
    res = compare(a.prev, a.cur, a.prev_img, a.cur_img, log=log, params=json.loads(a.params) if a.params else None, debug=a.debug)
    d = os.path.dirname(os.path.abspath(a.out))
    os.makedirs(d, exist_ok=True)
    tmp = a.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False)
    os.replace(tmp, a.out)
    s = res["summary"]
    print(json.dumps(dict(ok=res["registration"]["ok"], method=res["registration"]["method"], rms_mm=res["registration"]["rms_mm"],
                          **{k: s[k] for k in STATUS_ORDER})))


if __name__ == "__main__":
    main()
