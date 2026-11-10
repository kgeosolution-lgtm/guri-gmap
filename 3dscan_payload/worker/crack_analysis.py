r"""
kgeoScan 균열 자동 분석 (면 모드 정사영상)

  orthophoto.py 가 정사영상을 만든 직후 analyze() 를 부른다(표면점·사진 정보를 넘겨 원본 사진에서 폭을 다시 잰다).
  단독 실행(정사영상만, 원본 사진 재측정 없음):
    python -I crack_analysis.py --ortho X_ortho.jpg --meta X_ortho.json --out <dir> [--mask X_crack_mask.png]

방법
  1) 후보: 블랙햇(닫힘 − 원본) = 주변보다 어두운 가는 선 → 밝기로 나눈 상대 어두움 → 이력 임계값
     (사용자가 앱에서 탭한 균열 표시 주변은 임계값을 낮춘다). --mask(딥러닝 확률)가 있으면 그것과 합친다.
  2) 조각마다 세선화(Zhang-Suen) → 길이·가늘고 긴 정도로 거르기 → 가지(polyline)로 나눔
  3) 폭: 중심선에 수직인 밝기 단면.
     - 충분히 넓게 찍힌 균열(반치폭 ≥ 3 px)은 반치폭(FWHM) = 실제 폭
     - 가는 균열은 "어두움 면적 ÷ 균열 속 어두움"(광도 폭). 균열 속 밝기 비율 ρ 는 넓은 균열에서 추정, 없으면 기본값
     - 원본 사진 재측정: 표본점마다 그 자리를 가장 크게(px/m) 정면으로 본 사진에서 같은 단면을 m 단위로 잰다
  4) 출력: ortho_cracks.json (균열 목록·요약), ortho_cracks.dxf (mm 좌표, 폭 구간별 레이어)

한계: 균열 깊이는 겉 사진으로 알 수 없다. 0.1~0.2 mm 미세균열은 사진 해상도에 따라 검출만 되고 폭은 추정치.
"""
import argparse
import json
import math
import os
import time

import cv2
import numpy as np

WIDTH_BINS = [0.1, 0.2, 0.3, 0.5, 1.0]                      # mm 구간 경계 (6구간)
BIN_LABELS = ["<0.1", "0.1–0.2", "0.2–0.3", "0.3–0.5", "0.5–1.0", "≥1.0"]
BIN_COLORS = ["#4fc3f7", "#81c784", "#fff176", "#ffb74d", "#ff7043", "#d32f2f"]
DXF_LAYERS = ["CRACK_W_LT0.1", "CRACK_W_0.1-0.2", "CRACK_W_0.2-0.3", "CRACK_W_0.3-0.5", "CRACK_W_0.5-1.0", "CRACK_W_GE1.0"]
DXF_ACI = [4, 3, 2, 30, 1, 6]

DEFAULTS = dict(
    max_width_mm=6.0,       # 이보다 넓은 어두운 띠는 균열 후보로 보지 않음 (닫힘 크기)
    min_length_mm=20.0,     # 이보다 짧은 조각은 버림 (표시 근처는 mark_min_length_mm)
    mark_min_length_mm=8.0,
    mark_radius_mm=40.0,    # 앱 표시점 주변 반경: 임계값 완화
    min_elongation=4.0,     # 길이 ÷ 평균 폭
    hi_sigma=8.0, lo_sigma=4.0, hi_min=0.10, lo_min=0.05,
    rho_default=0.35,       # 균열 속 밝기 ÷ 주변 밝기 (가는 균열 광도 폭에 씀; 넓은 균열에서 다시 추정)
    sample_step_mm=4.0,     # 폭 표본 간격
    max_photo_samples=80,   # 균열 하나당 원본 사진 재측정 표본 수 상한
    surface_tol_mm=20.0,    # 높이 지도에서 기준면(바닥 높이·벽 평면)과 이만큼 넘게 떨어진 곳(물건·가구)은 분석하지 않음
    clutter_win_mm=40.0,    # 어수선함 창 크기: 이 안에서 후보 픽셀 비율이 clutter_frac 를 넘으면 무늬·물건으로 봄
    clutter_frac=0.12,
    max_density_m_per_m2=30.0,   # 덩어리 길이 ÷ 차지 면적(최소 0.1 m 사각형) — 이보다 촘촘하면 무늬
    max_median_width_mm=4.0,     # 정사영상에서 잰 중앙 폭이 이보다 넓으면 그늘·이음매·물체 경계
)


def width_bin(w_mm):
    return int(np.searchsorted(WIDTH_BINS, w_mm, side="right"))


# ── 1) 후보 ──────────────────────────────────────────────────────────────────
def relative_darkness(gray, valid, gsd, max_width_mm):
    k = int(max(5, round(max_width_mm * 1e-3 / gsd * 1.5))) | 1
    ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    g = cv2.GaussianBlur(gray, (0, 0), 0.7)
    close = cv2.morphologyEx(g, cv2.MORPH_CLOSE, ker)
    rel = cv2.subtract(close, g).astype(np.float32) / (close.astype(np.float32) + 8.0)
    rel[~valid] = 0
    return rel, k


def thresholds(rel, valid, p):
    v = rel[valid]
    if v.size > 2_000_000:
        v = v[:: v.size // 2_000_000]
    med = float(np.median(v)) if v.size else 0.0
    mad = float(np.median(np.abs(v - med))) * 1.4826 if v.size else 0.01
    hi = max(p["hi_min"], med + p["hi_sigma"] * mad)
    lo = max(p["lo_min"], med + p["lo_sigma"] * mad)
    return lo, min(hi, 0.6), med, mad


def thin(mask):
    """Zhang-Suen 세선화 (bool 2D)"""
    img = np.pad(mask.astype(np.uint8), 1)
    while True:
        changed = False
        for step in (0, 1):
            C = img[1:-1, 1:-1]
            P2, P3, P4, P5 = img[:-2, 1:-1], img[:-2, 2:], img[1:-1, 2:], img[2:, 2:]
            P6, P7, P8, P9 = img[2:, 1:-1], img[2:, :-2], img[1:-1, :-2], img[:-2, :-2]
            nb = [P2, P3, P4, P5, P6, P7, P8, P9]
            B = np.zeros(C.shape, np.int32)
            for q in nb:
                B += q
            A = np.zeros(C.shape, np.int32)
            seq = nb + [P2]
            for i in range(8):
                A += (seq[i] == 0) & (seq[i + 1] == 1)
            if step == 0:
                c1 = (P2 & P4 & P6) == 0; c2 = (P4 & P6 & P8) == 0
            else:
                c1 = (P2 & P4 & P8) == 0; c2 = (P2 & P6 & P8) == 0
            rm = (C == 1) & (B >= 2) & (B <= 6) & (A == 1) & c1 & c2
            if rm.any():
                C[rm] = 0
                changed = True
        if not changed:
            return img[1:-1, 1:-1].astype(bool)


NB8 = [(-1, 0), (0, 1), (1, 0), (0, -1), (-1, 1), (1, 1), (1, -1), (-1, -1)]   # 4-이웃 먼저


def branches(skel):
    """세선 → 가지 목록 [(N,2) (y,x) 순서 배열]. 갈림(이웃 ≥3) 덩어리를 떼어 단순 경로로 나눈 뒤, 끝을 갈림 중심에 잇는다"""
    sk = skel.astype(np.uint8)
    nbc = cv2.filter2D(sk, -1, np.ones((3, 3), np.float32), borderType=cv2.BORDER_CONSTANT) - sk
    junc = (sk > 0) & (nbc >= 3)
    jl_n, jl = cv2.connectedComponents(cv2.dilate(junc.astype(np.uint8), np.ones((3, 3), np.uint8)) & sk, connectivity=8)
    jcent = {}
    for j in range(1, jl_n):
        ys, xs = np.nonzero(jl == j)
        jcent[j] = (float(ys.mean()), float(xs.mean()))
    rest = (sk > 0) & (jl == 0)
    n, lab = cv2.connectedComponents(rest.astype(np.uint8), connectivity=8)
    out = []
    H, W = sk.shape
    for c in range(1, n):
        ys, xs = np.nonzero(lab == c)
        S = set(zip(ys.tolist(), xs.tolist()))
        if len(S) == 1:
            path = [next(iter(S))]
        else:
            def nbrs(p):
                return [(p[0] + dy, p[1] + dx) for dy, dx in NB8 if (p[0] + dy, p[1] + dx) in S]
            start = next((p for p in S if len(nbrs(p)) <= 1), next(iter(S)))
            path, seen, cur = [start], {start}, start
            while True:
                nx = [r for r in nbrs(cur) if r not in seen]
                if not nx:
                    break
                cur = nx[0]
                seen.add(cur); path.append(cur)
        arr = [(float(y), float(x)) for y, x in path]
        for end in (0, -1):                               # 끝이 갈림 덩어리에 닿으면 그 중심까지 잇는다
            y, x = path[end]
            js = {int(jl[yy, xx]) for yy in range(max(0, y - 1), min(H, y + 2)) for xx in range(max(0, x - 1), min(W, x + 2))} - {0}
            if js:
                cy, cx = jcent[js.pop()]
                if end == 0:
                    arr.insert(0, (cy, cx))
                else:
                    arr.append((cy, cx))
        out.append(np.array(arr, np.float64))
    return out, max(0, jl_n - 1)


def path_length(p):
    return float(np.linalg.norm(np.diff(p, axis=0), axis=1).sum()) if len(p) > 1 else 0.0


# ── 3) 폭: 밝기 단면 ─────────────────────────────────────────────────────────
def profile_stats(prof, ds):
    """단면(가운데가 균열 예상 위치) → dict(bg, core, depth, area, fwhm, off) 또는 None. ds = 표본 간격(px 또는 m)"""
    n = len(prof)
    q = max(2, n // 6)
    bg = float(np.median(np.r_[prof[:q], prof[-q:]]))
    c0, c1 = int(n * 0.2), int(n * 0.8)
    i0 = c0 + int(np.argmin(prof[c0:c1]))
    depth = bg - float(prof[i0])
    if bg <= 1 or depth < max(4.0, 0.06 * bg):
        return None
    thr = bg - 0.1 * depth
    a, b = i0, i0
    while a > 0 and prof[a - 1] < thr:
        a -= 1
    while b < n - 1 and prof[b + 1] < thr:
        b += 1
    seg = prof[a:b + 1]
    area = float(np.clip(bg - seg, 0, None).sum()) * ds
    half = bg - 0.5 * depth
    below = seg < half
    fw = float(below.sum())
    # 반치폭 가장자리 부분 픽셀 보간
    idx = np.flatnonzero(below)
    if idx.size:
        l, r = idx[0] + a, idx[-1] + a
        if l > 0 and prof[l - 1] != prof[l]:
            fw += float(np.clip((prof[l - 1] - half) / (prof[l - 1] - prof[l]), 0, 1)) - 0.5
        if r < n - 1 and prof[r + 1] != prof[r]:
            fw += float(np.clip((prof[r + 1] - half) / (prof[r + 1] - prof[r]), 0, 1)) - 0.5
    return dict(bg=bg, core=float(prof[i0]), depth=depth, area=area, fwhm=max(0.0, fw) * ds, off=(i0 - (n - 1) / 2) * ds)


def width_from_stats(st, px_per_unit, rho):
    """반치폭이 3 px 이상이면 반치폭, 아니면 광도 폭 (단위: ds 단위)"""
    if st["fwhm"] * px_per_unit >= 3.0:
        return st["fwhm"], "fwhm"
    return st["area"] / max(1e-6, st["bg"] * (1.0 - rho)), "photometric"


def sample_profiles(gray, pts, dirs, half_px, step=0.25):
    """gray(float32) 위 점들에서 방향 dirs 의 수직선 단면 (N, M)"""
    s = np.arange(-half_px, half_px + 1e-9, step, dtype=np.float32)
    nrm = np.stack([dirs[:, 1], -dirs[:, 0]], axis=1)          # dirs = (dy, dx) 단위벡터 → 수직 (dy', dx') = (dx, -dy)
    yy = (pts[:, 0:1] + nrm[:, 0:1] * s[None]).astype(np.float32)
    xx = (pts[:, 1:2] + nrm[:, 1:2] * s[None]).astype(np.float32)
    prof = cv2.remap(gray, xx, yy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    return prof, step, nrm


# ── 원본 사진 재측정 ─────────────────────────────────────────────────────────
def refine_with_photos(cracks, ctx, rho, log, p):
    P, Nn, views, scene = ctx["P"], ctx.get("Nn"), ctx["views"], ctx["scene"]
    ex, ey = np.asarray(ctx["ex"], float), np.asarray(ctx["ey"], float)
    plane_n = np.cross(ex, ey); plane_n /= np.linalg.norm(plane_n) + 1e-12
    S = []                                                  # (crack idx, sample idx, X, perp_world, w_est_m)
    for ci, c in enumerate(cracks):
        sm = c["_samples"]
        if not sm:
            continue
        pick = np.unique(np.linspace(0, len(sm) - 1, min(len(sm), p["max_photo_samples"])).astype(int))
        for si in pick:
            y, x, ny, nx, w_mm = (sm[si][k] for k in ("y", "x", "ny", "nx", "w"))
            X = np.asarray(P[int(round(y)), int(round(x))], np.float64)
            if not np.all(np.isfinite(X)) or not np.any(X):
                continue
            pw = ex * nx + ey * ny
            pw -= plane_n * (pw @ plane_n)
            nn = np.linalg.norm(pw)
            if nn < 1e-6:
                continue
            S.append((ci, si, X, pw / nn, max(w_mm, 0.1) * 1e-3))
    if not S:
        return rho
    X = np.array([s[2] for s in S]); PW = np.array([s[3] for s in S]); WE = np.array([s[4] for s in S])
    if Nn is not None:
        NR = np.array([np.asarray(Nn[int(round(cracks[s[0]]["_samples"][s[1]]["y"])), int(round(cracks[s[0]]["_samples"][s[1]]["x"]))], np.float64) for s in S])
        bad = np.linalg.norm(NR, axis=1) < 0.5
        NR[bad] = plane_n
        NR /= np.linalg.norm(NR, axis=1, keepdims=True)
    else:
        NR = np.broadcast_to(plane_n, X.shape)
    best_sc = np.zeros(len(S)); best_v = np.full(len(S), -1); best_ppm = np.zeros(len(S))
    for vi, v in enumerate(views):
        K = v["K"]; T_CW = np.linalg.inv(v["T_WC"]); w, h = v["w"], v["h"]
        pc = X @ T_CW[:3, :3].T + T_CW[:3, 3]
        z = pc[:, 2]
        ok = z > 0.08
        zs = np.where(ok, z, 1.0)
        u = K[0, 0] * pc[:, 0] / zs + K[0, 2]; vv = K[1, 1] * pc[:, 1] / zs + K[1, 2]
        ok &= (u > 24) & (u < w - 24) & (vv > 24) & (vv < h - 24)
        if not ok.any():
            continue
        dz, sw, shh = ctx["view_depth"](scene, K, v["T_WC"], w, h, 800.0 / max(w, h))
        dsc = sw / w
        zd = dz[np.clip((vv * dsc).astype(int), 0, shh - 1), np.clip((u * dsc).astype(int), 0, sw - 1)]
        ok &= z <= zd + 0.02 + 0.03 * z
        to_cam = v["T_WC"][:3, 3] - X
        to_cam /= np.linalg.norm(to_cam, axis=1, keepdims=True) + 1e-12
        cosang = np.abs((NR * to_cam).sum(axis=1))
        ok &= cosang > 0.5
        ppm = K[0, 0] / zs * cosang                       # 표면 1 m 가 사진에서 몇 px
        edge = np.minimum(np.minimum(u, w - u), np.minimum(vv, h - vv)) / (0.25 * min(w, h))
        sc = ppm * np.clip(edge, 0.4, 1.0)
        upd = ok & (sc > best_sc)
        best_sc[upd] = sc[upd]; best_v[upd] = vi; best_ppm[upd] = ppm[upd]
    n_done, got = 0, []
    NS = 241
    for vi in np.unique(best_v[best_v >= 0]):
        v = views[int(vi)]
        rgb = ctx["load_rgb"](v["path"])
        if rgb is None:
            continue
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
        hh, ww = gray.shape
        K = v["K"].copy()
        if (ww, hh) != (v["w"], v["h"]):
            K[0] *= ww / v["w"]; K[1] *= hh / v["h"]
        T_CW = np.linalg.inv(v["T_WC"])
        idx = np.flatnonzero(best_v == vi)
        L = np.maximum(0.006, 4 * WE[idx]) + 0.004            # 단면 반길이(m): 정사영상-사진 어긋남(수 mm) 여유 포함
        s = np.linspace(-1, 1, NS)[None, :] * L[:, None]       # (n, NS) m
        pts = X[idx, None, :] + s[..., None] * PW[idx, None, :]
        pc = pts @ T_CW[:3, :3].T + T_CW[:3, 3]
        zz = np.maximum(pc[..., 2], 1e-3)
        uu = (K[0, 0] * pc[..., 0] / zz + K[0, 2]).astype(np.float32)
        vv = (K[1, 1] * pc[..., 1] / zz + K[1, 2]).astype(np.float32)
        prof = cv2.remap(gray, uu, vv, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        for r, k in enumerate(idx):
            ds = 2 * L[r] / (NS - 1)
            st = profile_stats(prof[r], ds)
            if st is None:
                continue
            got.append((k, st, best_ppm[k] * (ww / v["w"]), int(vi)))
    # 사진은 해상도가 높아 넓게 찍힌 균열이 더 많다 → 균열 속 밝기 비율을 사진 표본에서 다시 추정
    rr = [st["core"] / st["bg"] for _, st, ppm, _ in got if st["fwhm"] * ppm >= 4.0 and st["core"] < 0.65 * st["bg"]]
    rho_p = float(np.clip(np.median(rr), 0.1, 0.6)) if len(rr) >= 5 else rho
    for k, st, ppm, vi in got:
        wm, how = width_from_stats(st, ppm, rho_p)
        ci, si = S[k][0], S[k][1]
        cracks[ci]["_photo"][si] = (wm * 1000.0, how, vi, float(ppm / 1000.0))   # mm, 방법, 사진, px/mm
        n_done += 1
    log(f"cracks: photo re-measure {n_done}/{len(S)} samples from {len(np.unique(best_v[best_v >= 0]))} photos, "
        f"rho {rho_p:.2f} ({'photo ' + str(len(rr)) if len(rr) >= 5 else 'from ortho'})")
    return rho_p


# ── 표시점 ───────────────────────────────────────────────────────────────────
def marks_to_px(marks_json, grid, gsd):
    """앱 marks.json(ARKit 월드) → 정사영상 픽셀. grid = dict(origin_uv, ex, ey)"""
    if not marks_json or not grid:
        return []
    ex, ey = np.asarray(grid["ex"], float), np.asarray(grid["ey"], float)
    ou, ov = grid["origin_uv"]
    to_px = lambda X: [float((np.asarray(X, float) @ ex - ou) / gsd - 0.5), float((np.asarray(X, float) @ ey - ov) / gsd - 0.5)]
    out = []
    for m in marks_json.get("marks", []):
        try:
            if m.get("kind") == "crack_line":
                out.append(dict(id=m.get("id"), kind="crack_line", p0=to_px(m["p0"]), p1=to_px(m["p1"]), label=m.get("label", "")))
            else:
                out.append(dict(id=m.get("id"), kind=m.get("kind", "crack"), px=to_px([m["x"], m["y"], m["z"]]), label=m.get("label", "")))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def marks_mask(shape, marks_px, radius_px):
    mk = np.zeros(shape, np.uint8)
    r = max(2, int(round(radius_px)))
    for m in marks_px:
        if m["kind"] == "crack_line":
            cv2.line(mk, tuple(int(round(t)) for t in m["p0"]), tuple(int(round(t)) for t in m["p1"]), 1, 2 * r)
        else:
            cv2.circle(mk, tuple(int(round(t)) for t in m["px"]), r, 1, -1)
    return mk > 0


# ── 출력 ─────────────────────────────────────────────────────────────────────
def write_dxf(path, cracks, W, H, gsd):
    """DXF R12 (ASCII). 좌표 mm, 원점 = 정사영상 왼쪽 아래, y 위쪽. 폭 구간별 레이어 + 라벨"""
    s = gsd * 1000.0
    X = lambda x: x * s
    Y = lambda y: (H - y) * s
    L = []
    add = lambda code, val: L.extend([str(code), str(val)])
    add(0, "SECTION"); add(2, "HEADER"); add(9, "$ACADVER"); add(1, "AC1009"); add(0, "ENDSEC")
    add(0, "SECTION"); add(2, "TABLES"); add(0, "TABLE"); add(2, "LAYER"); add(70, len(DXF_LAYERS) + 2)
    for name, col in list(zip(DXF_LAYERS, DXF_ACI)) + [("ORTHO_EXTENT", 8), ("CRACK_LABEL", 7)]:
        add(0, "LAYER"); add(2, name); add(70, 0); add(62, col); add(6, "CONTINUOUS")
    add(0, "ENDTAB"); add(0, "ENDSEC")
    add(0, "SECTION"); add(2, "ENTITIES")

    def poly(layer, pts, closed=False):
        add(0, "POLYLINE"); add(8, layer); add(66, 1); add(70, 1 if closed else 0)
        for x, y in pts:
            add(0, "VERTEX"); add(8, layer); add(10, f"{X(x):.3f}"); add(20, f"{Y(y):.3f}"); add(30, 0)
        add(0, "SEQEND"); add(8, layer)
    poly("ORTHO_EXTENT", [(0, 0), (W, 0), (W, H), (0, H)], closed=True)
    th = max(2.0, min(10.0, 0.012 * max(W, H) * s))
    for c in cracks:
        for sg in c["segments"]:
            if len(sg["polyline"]) >= 2:
                poly(DXF_LAYERS[sg["bin"]], sg["polyline"])
        x0, y0 = c["bbox"][0], c["bbox"][1]
        add(0, "TEXT"); add(8, "CRACK_LABEL"); add(10, f"{X(x0):.3f}"); add(20, f"{Y(y0) + th * 0.4:.3f}"); add(30, 0)
        add(40, f"{th:.2f}"); add(1, f"C{c['id']} L={c['length_mm']:.0f}mm Wmax={c['width_max_mm']:.2f}mm")
    add(0, "ENDSEC"); add(0, "EOF")
    with open(path, "w", encoding="ascii", errors="replace", newline="\r\n") as f:
        f.write("\n".join(L) + "\n")


# ── 본체 ─────────────────────────────────────────────────────────────────────
def surface_mask_from_height(hm_info, hbin, shape, tol_mm):
    """높이 지도(int16 mm, step 격자) → 기준면 ±tol 안의 픽셀 (정사영상 크기 bool)"""
    h = np.asarray(hbin, np.int16).reshape(hm_info["height"], hm_info["width"])
    ok = (h != hm_info.get("nodata", -32768)) & (np.abs(h.astype(np.int32)) <= tol_mm)
    st = int(hm_info.get("step", 1))
    up = np.repeat(np.repeat(ok, st, axis=0), st, axis=1)[:shape[0], :shape[1]]       # 격자 한 칸 = step px
    if up.shape != tuple(shape):
        up = np.pad(up, ((0, shape[0] - up.shape[0]), (0, shape[1] - up.shape[1])))
    return up


def card_summary(sc):
    """scale_target.check_scale 결과 → 뷰어·보고서용 요약 (found=False 면 None)"""
    if not sc or not sc.get("found"):
        return None
    return dict(card=sc.get("card"), scale_error_pct=sc.get("scale_error_pct"), scale_factor=sc.get("scale_factor"),
                fit_rms_px=sc.get("fit_rms_px"), card_px_bbox=sc.get("card_px_bbox"),
                cards=[dict(card=c["card"], scale_error_pct=c["scale_error_pct"], card_px_bbox=c["card_px_bbox"]) for c in sc.get("cards", [])],
                gauge=[dict(nominal_mm=g["nominal_mm"], measured_mm=g.get("measured_mm"), fwhm_mm=g.get("fwhm_mm")) for g in sc.get("gauge", [])])


def analyze(img_rgb, covered, gsd, out_dir, log, photo_ctx=None, marks_px=None, surface="wall", dl_mask=None, params=None, on_surface=None,
            scale_card=None):
    """정사영상(RGB uint8) + 칠해진 영역 → ortho_cracks.json/.dxf 저장, meta 용 요약 dict 반환.
    on_surface: 기준면 가까운 픽셀(bool, 높이 지도에서) — 물건·가구 위는 분석하지 않는다
    scale_card: scale_target.check_scale 결과 — 카드 자리는 분석에서 빼고(게이지 선이 균열로 잡히지 않게), 축척을 보정한다"""
    t0 = time.time()
    p = dict(DEFAULTS, **(params or {}))
    H, W = img_rgb.shape[:2]
    gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
    base = covered if on_surface is None else (covered & on_surface)
    if on_surface is not None:
        log(f"cracks: on-surface {base.sum() / max(1, covered.sum()) * 100:.1f}% of colored pixels (height within {p['surface_tol_mm']:.0f} mm)")
    card = card_summary(scale_card)
    sf = 1.0
    if card:
        base = base.copy()
        pad = 5.0 / (gsd * 1000.0)
        for cc in card["cards"] or [dict(card_px_bbox=card["card_px_bbox"])]:
            x0_, y0_, x1_, y1_ = cc["card_px_bbox"]
            base[max(0, int(y0_ - pad)):int(y1_ + pad) + 1, max(0, int(x0_ - pad)):int(x1_ + pad) + 1] = False
        if card["scale_factor"] and abs(card["scale_error_pct"]) < 5.0:      # 5 % 넘게 틀리면 카드 검출을 의심하고 보정하지 않는다
            sf = float(card["scale_factor"])
        log(f"cracks: reference card {card['card']} found, scale error {card['scale_error_pct']:+.2f}% -> factor {sf:.4f}")
    valid = cv2.erode(base.astype(np.uint8), np.ones((7, 7), np.uint8)) > 0          # 칠해진 영역 가장자리(경계 그늘) 제외
    rel, k = relative_darkness(gray, valid, gsd, p["max_width_mm"])
    e = k // 2 + 2                                         # 영상 테두리: 닫힘 연산이 테두리 밖을 못 봐 가짜 선이 생긴다
    for r_ in (rel, valid):
        r_[:e] = 0; r_[-e:] = 0; r_[:, :e] = 0; r_[:, -e:] = 0
    lo, hi, med, mad = thresholds(rel, valid, p)
    marks_px = marks_px or []
    near_mark = marks_mask((H, W), marks_px, p["mark_radius_mm"] * 1e-3 / gsd) if marks_px else np.zeros((H, W), bool)
    weak = (rel > lo) | (near_mark & (rel > 0.6 * lo))
    if dl_mask is not None:
        dm = dl_mask if dl_mask.shape == (H, W) else cv2.resize(dl_mask, (W, H), interpolation=cv2.INTER_LINEAR)
        weak |= (dm >= 128) & valid
    # 어수선함: 창 안 후보 픽셀 비율 (가는 균열은 창의 몇 %, 음식·식물·엉성한 재구성·거친 무늬는 훨씬 많다)
    cw = max(9, int(round(p["clutter_win_mm"] * 1e-3 / gsd))) | 1
    clutter = cv2.boxFilter(weak.astype(np.float32), -1, (cw, cw)) > p["clutter_frac"]
    n, lab, stats, _ = cv2.connectedComponentsWithStats(weak.astype(np.uint8), connectivity=8)
    strong = np.zeros(n, bool)
    strong[np.unique(lab[(rel > hi) | (near_mark & (rel > 0.75 * hi))])] = True
    if dl_mask is not None:
        strong[np.unique(lab[(dm >= 200) & valid])] = True
    strong[0] = False
    log(f"cracks: rel med {med:.3f} mad {mad:.3f} -> lo {lo:.3f} hi {hi:.3f}, closing {k} px, {int(strong.sum())} strong components")

    mm = gsd * 1000.0
    min_len_px = p["min_length_mm"] / mm
    gray_f = gray.astype(np.float32)
    cracks, rho_obs = [], []
    drop = dict(clutter=0, density=0, width=0)
    for c in np.flatnonzero(strong):
        x0, y0, bw, bh, area = stats[c]
        near = bool(near_mark[y0:y0 + bh, x0:x0 + bw][lab[y0:y0 + bh, x0:x0 + bw] == c].any()) if marks_px else False
        lim = (p["mark_min_length_mm"] / mm) if near else min_len_px
        if max(bw, bh) < 0.7 * lim:
            continue
        comp = lab[y0:y0 + bh, x0:x0 + bw] == c
        if not near and clutter[y0:y0 + bh, x0:x0 + bw][comp].mean() > 0.5:
            drop["clutter"] += 1
            continue
        sk = thin(comp)
        brs, n_junc = branches(sk)
        brs = [b + [y0, x0] for b in brs if len(b) >= 2]
        length_px = sum(path_length(b) for b in brs)
        if length_px < lim:
            continue
        mean_w_px = area / max(1.0, length_px)
        if length_px / max(1.0, mean_w_px) < (p["min_elongation"] * (0.75 if near else 1.0)) or mean_w_px * mm > p["max_width_mm"]:
            continue
        box_m2 = max(bw * mm * 1e-3, 0.1) * max(bh * mm * 1e-3, 0.1)
        if not near and length_px * mm * 1e-3 / box_m2 > p["max_density_m_per_m2"]:
            drop["density"] += 1
            continue
        # 폭 표본 (정사영상)
        step = max(3, int(round(p["sample_step_mm"] / mm)))
        half = max(6.0, 3.0 * mean_w_px + 3.0)
        pts, dirs, bix = [], [], []
        for bi, b in enumerate(brs):
            if len(b) < 5:
                continue
            arc = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(b, axis=0), axis=1))]
            margin = min(half, 0.25 * arc[-1])                # 가지 끝(갈림·교차 지점) 근처 단면은 옆 균열이 섞여 건너뜀
            for i in range(2, len(b) - 2, step):
                if arc[i] < margin or arc[i] > arc[-1] - margin:
                    continue
                d = b[min(len(b) - 1, i + 2)] - b[max(0, i - 2)]
                nd = np.linalg.norm(d)
                if nd > 0:
                    pts.append(b[i]); dirs.append(d / nd); bix.append(bi)
        samples = []
        if pts:
            pts_a, dirs_a = np.array(pts), np.array(dirs)
            prof, ds, nrm = sample_profiles(gray_f, pts_a, dirs_a, half)
            for r in range(len(pts_a)):
                st = profile_stats(prof[r], ds)
                if st is None:
                    continue
                if st["fwhm"] >= 3.0 and st["core"] < 0.65 * st["bg"]:     # 충분히 넓고 뚜렷한 균열에서만 속 밝기 비율 추정
                    rho_obs.append(st["core"] / st["bg"])
                samples.append(dict(y=float(pts_a[r, 0]), x=float(pts_a[r, 1]), ny=float(nrm[r, 0]), nx=float(nrm[r, 1]), st=st, bi=bix[r]))
        # 방향 (y 아래 → 각도는 가로 0°, 위로 갈수록 +)
        allp = np.concatenate(brs) if brs else np.zeros((1, 2))
        cy, cx = allp.mean(axis=0)
        cov = np.cov((allp - [cy, cx]).T) if len(allp) > 2 else np.eye(2)
        ev, evec = np.linalg.eigh(cov)
        vy, vx = evec[:, -1]
        ang = float(np.degrees(np.arctan2(-vy, vx))) % 180.0
        aspect = math.sqrt(max(ev[-1], 1e-9) / max(ev[0], 1e-9))
        if n_junc >= 3 and aspect < 2.5:
            kind = "망상"
        elif surface == "wall":
            kind = "가로" if (ang < 20 or ang > 160) else ("세로" if 70 < ang < 110 else "사선")
        else:
            kind = "선형"
        polys = []
        for b in brs:
            q = cv2.approxPolyDP(b[:, ::-1].astype(np.float32).reshape(-1, 1, 2), 0.8, False).reshape(-1, 2)
            polys.append([[round(float(x), 1), round(float(y), 1)] for x, y in q])
        cracks.append(dict(_samples=samples, _photo={}, _blen=[path_length(b) * mm for b in brs], length_mm=length_px * mm,
                           bbox=[int(x0), int(y0), int(x0 + bw), int(y0 + bh)],
                           polylines=polys, orientation_deg=round(ang, 1), kind=kind, junctions=int(n_junc), near_mark=near))
    rho = float(np.clip(np.median(rho_obs), 0.1, 0.6)) if len(rho_obs) >= 5 else p["rho_default"]
    for c in cracks:                                       # 정사영상 중앙 폭이 너무 넓으면 그늘·이음매·물체 경계
        ws_ = [width_from_stats(s_["st"], 1.0, rho)[0] * mm for s_ in c["_samples"]]
        if ws_ and not c["near_mark"] and float(np.median(ws_)) > p["max_median_width_mm"]:
            c["_drop"] = True
    drop["width"] = sum(1 for c in cracks if c.get("_drop"))
    cracks = [c for c in cracks if not c.get("_drop")]
    log(f"cracks: dropped clutter {drop['clutter']}, dense pattern {drop['density']}, too wide {drop['width']}")
    log(f"cracks: {len(cracks)} kept; rho {rho:.2f} ({'measured from ' + str(len(rho_obs)) + ' resolved samples' if len(rho_obs) >= 5 else 'default'})")

    # 정사영상 폭
    for c in cracks:
        for sm in c["_samples"]:
            wpx, sm["how"] = width_from_stats(sm["st"], 1.0, rho)
            sm["w"] = wpx * mm
    rho_photo = None
    if photo_ctx is not None and cracks:
        try:
            rho_photo = refine_with_photos(cracks, photo_ctx, rho, log, p)
        except Exception as e:                               # 재측정 실패해도 정사영상 폭으로 낸다
            log(f"cracks: photo re-measure skipped: {e}")
    # 자체 검증: 카드의 게이지 선(폭을 아는 검은 선)을 균열과 똑같은 원본 사진 단면으로 잰다
    gauge_check = None
    if card and photo_ctx is not None:
        try:
            pseudo = []
            for g in scale_card.get("gauge", []):
                lp = g.get("line_px")
                if not lp or len(lp) < 2:
                    continue
                (gx0, gy0), (gx1, gy1) = lp[0], lp[-1]
                L_ = math.hypot(gx1 - gx0, gy1 - gy0)
                if L_ < 5:
                    continue
                dy_, dx_ = (gy1 - gy0) / L_, (gx1 - gx0) / L_
                sm_ = [dict(y=gy0 + t * (gy1 - gy0), x=gx0 + t * (gx1 - gx0), ny=dx_, nx=-dy_, w=0.1, bi=0) for t in np.linspace(0.15, 0.85, 12)]
                pseudo.append(dict(_samples=sm_, _photo={}, nominal=g["nominal_mm"]))
            if pseudo:
                refine_with_photos(pseudo, photo_ctx, rho, lambda m: log("gauge " + m), dict(p, max_photo_samples=12))
                gauge_check = []
                for ps in pseudo:
                    v = [w for w, *_ in ps["_photo"].values()]
                    hows = [h for _, h, *_ in ps["_photo"].values()]
                    gauge_check.append(dict(nominal_mm=ps["nominal"], measured_mm=round(float(np.median(v)) * sf, 3) if v else None, n=len(v),
                                            method=max(set(hows), key=hows.count) if hows else None))
                log("cracks: gauge check " + ", ".join(f"{g['nominal_mm']}->{g['measured_mm']}" for g in gauge_check))
        except Exception as e:
            log(f"cracks: gauge check skipped: {e}")
    if card is not None:
        card["gauge_photo"] = gauge_check

    def stat(ws, srcs):
        """사진 재측정 표본이 3개 이상이면 그것만으로 (정사영상 폭은 해상도가 낮다) → (최대(90%), 중앙, 출처, 개수)"""
        wp = [w for w, s in zip(ws, srcs) if s == "photo"]
        use, src = (wp, "photo") if len(wp) >= 3 else (ws, "ortho")
        if not use:
            return None
        return float(np.percentile(use, 90)), float(np.median(use)), src, len(use)

    out = []
    for c in sorted(cracks, key=lambda c: -c["length_mm"]):
        c["length_mm"] *= sf                                  # 기준 카드 축척 보정 (없으면 1)
        c["_blen"] = [b * sf for b in c["_blen"]]
        ws, srcs, rows, per_b = [], [], [], {}
        for si, sm in enumerate(c["_samples"]):
            ph = c["_photo"].get(si)
            if ph is not None:
                w, s = ph[0] * sf, "photo"
                rows.append([round(sm["x"], 1), round(sm["y"], 1), round(w, 3), s, ph[1], ph[2], round(ph[3], 2), sm["bi"]])
            else:
                w, s = sm["w"] * sf, "ortho"
                rows.append([round(sm["x"], 1), round(sm["y"], 1), round(w, 3), s, sm["how"], None, round(1.0 / mm, 2), sm["bi"]])
            ws.append(w); srcs.append(s)
            per_b.setdefault(sm["bi"], ([], []))
            per_b[sm["bi"]][0].append(w); per_b[sm["bi"]][1].append(s)
        cs = stat(ws, srcs)
        if cs is None:
            continue
        wmax, wmed, src, nuse = cs
        if wmed > p["max_width_mm"]:                          # 사진으로 재 보니 균열보다 넓은 어두운 띠(그늘·이음매)
            continue
        # 가지마다 폭·구간 (서로 교차한 가는 균열과 굵은 균열이 한 덩어리여도 선마다 제 색)
        segs = []
        for bi, pl in enumerate(c["polylines"]):
            bs = stat(*per_b[bi]) if bi in per_b else None
            bmax, bmed = (bs[0], bs[1]) if bs else (wmed, wmed)
            segs.append(dict(polyline=pl, length_mm=round(c["_blen"][bi], 1), width_max_mm=round(bmax, 3), width_median_mm=round(bmed, 3),
                             bin=width_bin(bmax), measured=bs is not None))
        c2 = dict(id=len(out) + 1, length_mm=round(c["length_mm"], 1), width_max_mm=round(wmax, 3), width_median_mm=round(wmed, 3),
                  width_source=src, n_samples=nuse, bin=width_bin(wmax), bin_label=BIN_LABELS[width_bin(wmax)],
                  kind=c["kind"], orientation_deg=c["orientation_deg"], junctions=c["junctions"], near_mark=c["near_mark"],
                  bbox=c["bbox"], segments=segs, samples=rows[:400])
        out.append(c2)
    by_bin = [dict(label=BIN_LABELS[i], color=BIN_COLORS[i], count=sum(1 for c in out if c["bin"] == i),
                   length_mm=round(sum(c["length_mm"] for c in out if c["bin"] == i), 1)) for i in range(len(BIN_LABELS))]
    summary = dict(version=1, gsd_m=gsd, width=W, height=H, count=len(out), total_length_mm=round(sum(c["length_mm"] for c in out), 1),
                   max_width_mm=round(max((c["width_max_mm"] for c in out), default=0.0), 3), by_bin=by_bin,
                   rho=round(rho, 3), rho_source="measured" if len(rho_obs) >= 5 else "default",
                   rho_photo=round(rho_photo, 3) if rho_photo is not None else None,
                   photo_refined=sum(1 for c in out if c["width_source"] == "photo"), method="blackhat+hysteresis" + ("+dl" if dl_mask is not None else ""),
                   thresholds=dict(lo=round(lo, 4), hi=round(hi, 4)), dropped=drop, surface_only=on_surface is not None,
                   scale_card=card, scale_factor_applied=round(sf, 6),
                   marks=marks_px, seconds=round(time.time() - t0, 1),
                   note="폭은 원본 사진 단면(가능할 때) 또는 정사영상 단면으로 잰 값. 균열 깊이는 측정하지 않음. 0.2 mm 미만은 추정치.")
    doc = dict(summary, cracks=out, bins=dict(edges_mm=WIDTH_BINS, labels=BIN_LABELS, colors=BIN_COLORS))
    json.dump(doc, open(os.path.join(out_dir, "ortho_cracks.json"), "w", encoding="utf-8"), ensure_ascii=False)
    write_dxf(os.path.join(out_dir, "ortho_cracks.dxf"), out, W, H, gsd)
    log(f"cracks: {len(out)} cracks, total {summary['total_length_mm'] / 1000:.2f} m, max width {summary['max_width_mm']:.2f} mm "
        f"({summary['photo_refined']} photo-refined), {summary['seconds']}s")
    return {k: summary[k] for k in ("count", "total_length_mm", "max_width_mm", "by_bin", "photo_refined", "method", "rho", "rho_source",
                                    "scale_card", "scale_factor_applied")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ortho", required=True)
    ap.add_argument("--meta", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--mask", help="딥러닝 균열 확률 PNG (정사영상과 같은 격자, 0~255)")
    ap.add_argument("--overlay", help="ortho_overlay.png (투명 = 빈 곳). 없으면 배경색(24)으로 빈 곳 추정")
    ap.add_argument("--height-bin", help="ortho_height.bin (int16 mm) — 기준면에서 떨어진 물건 위는 분석하지 않음")
    a = ap.parse_args()
    t0 = time.time()
    log = lambda m: print(f"[{time.time() - t0:6.1f}s] {m}", flush=True)
    os.makedirs(a.out, exist_ok=True)
    meta = json.load(open(a.meta, encoding="utf-8"))
    bgr = cv2.imdecode(np.fromfile(a.ortho, np.uint8), cv2.IMREAD_COLOR)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    if a.overlay and os.path.exists(a.overlay):
        al = cv2.imdecode(np.fromfile(a.overlay, np.uint8), cv2.IMREAD_UNCHANGED)[..., 3]
        covered = cv2.resize(al, (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_NEAREST) > 128
    else:
        covered = np.abs(rgb.astype(np.int16) - 24).sum(axis=2) > 12
        covered = cv2.morphologyEx(covered.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)) > 0
    mask = cv2.imdecode(np.fromfile(a.mask, np.uint8), cv2.IMREAD_GRAYSCALE) if a.mask else None
    marks = meta.get("cracks_marks_px") or []
    hm = meta.get("height_map")
    on_surface = None
    if a.height_bin and hm and os.path.exists(a.height_bin):
        on_surface = surface_mask_from_height(hm, np.fromfile(a.height_bin, np.int16), rgb.shape[:2], DEFAULTS["surface_tol_mm"])
    s = analyze(rgb, covered, float(meta["gsd_m"]), a.out, log, marks_px=marks, surface=meta.get("surface", "wall"), dl_mask=mask,
                on_surface=on_surface)
    print(json.dumps(s))                                   # ASCII (Windows 콘솔 cp949 에서도 깨지지 않게)


if __name__ == "__main__":
    main()
