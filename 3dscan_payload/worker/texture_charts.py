r"""
사진 조각(차트) 텍스처 (2026-11-16) — LiDAR 메시를 사진처럼 선명하게

    python -I texture_charts.py --data <Stray 데이터셋> --mesh <mesh.ply> --out <dir>
           [--target-tris 120000] [--keyframes 100] [--tex-size 4096] [--jpeg-quality 85] [--no-gain]

texture_fast.py 와 다른 점
  - texture_fast 는 텍스처를 삼각형마다 같은 크기 칸(4096² 에 12만 삼각형이면 16 px)으로 나눠, 큰 벽이나 작은 물건이나
    같은 화소를 받고 삼각형 경계마다 칸 사이 틈이 생긴다(틈이 텍스처의 약 30 %).
  - 여기서는 같은 사진을 고른 이웃 삼각형 묶음(차트)을 그 사진에서 통째로 잘라 붙인다(사진측량 도구의 view chart 방식).
    · 사진에 보이는 크기에 비례해 자리를 받는다 → 가까이서 찍은 벽·물건이 사진 해상도에 가깝게 선명하다
    · 차트 안에는 이음매가 없고, 차트 둘레 여백은 사진의 실제 이웃 화소라 번지지 않는다
    · UV = 사진 위 투영 좌표(한 배율로 줄인 것) — 펼치기 계산이 없어 빠르다
  - 사진마다 노출 차이를 맞춘다: 같은 삼각형을 본 두 사진의 색 비로 사진별 이득(채널별)을 최소제곱으로 구한다
메시 준비·사진 고르기·면 방향은 texture_fast 와 같아서 모양·치수·좌표가 같다. 사진이 없는 삼각형은 융합 꼭짓점 색.
"""
import argparse
import json
import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from texture_fast import pick_keyframes, prepare_mesh, depth_maps, bilinear  # noqa: E402
from stray_to_mesh import read_odometry, read_frame_quality, F_ARKIT_TO_CV  # noqa: E402


def components(n, a, b):
    """간선 (a[i], b[i]) 로 이어진 묶음 번호 (scipy 없이: 최솟값 전파 + 포인터 건너뛰기)"""
    lab = np.arange(n)
    if len(a) == 0:
        return lab
    while True:
        old = lab
        m = np.minimum(lab[a], lab[b])
        lab = lab.copy()
        np.minimum.at(lab, a, m)
        np.minimum.at(lab, b, m)
        lab = lab[lab]
        lab = lab[lab]
        if np.array_equal(lab, old):
            return lab


def shelf_pack(ws, hs, T):
    """높이 순 선반 쌓기. 다 들어가면 (x, y) 배열, 아니면 None"""
    order = np.argsort(-hs, kind="stable")
    pos = np.zeros((len(ws), 2), np.int64)
    x = y = shelf = 0
    for i in order:
        if ws[i] > T:
            return None
        if x + ws[i] > T:
            x, y, shelf = 0, y + shelf, 0
        if y + hs[i] > T:
            return None
        pos[i] = (x, y)
        x += ws[i]
        shelf = max(shelf, hs[i])
    return pos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--mesh", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--target-tris", type=int, default=120000)
    ap.add_argument("--keyframes", type=int, default=100)
    ap.add_argument("--tex-size", type=int, default=4096)
    ap.add_argument("--cluster-voxel", type=float, default=0.02)
    ap.add_argument("--min-component", type=int, default=60)
    ap.add_argument("--depth-scale", type=float, default=0.25)
    ap.add_argument("--convention", choices=["cv", "arkit"], default="cv")
    ap.add_argument("--jpeg-quality", type=int, default=85)
    ap.add_argument("--vote-iters", type=int, default=8, help="이웃 삼각형을 같은 사진으로 모으는 반복 (클수록 차트가 커진다)")
    ap.add_argument("--pad", type=int, default=2, help="차트 둘레 여백 (텍스처 화소)")
    ap.add_argument("--max-scale", type=float, default=1.0, help="사진 해상도보다 크게 늘리지 않는다")
    ap.add_argument("--no-gain", action="store_true", help="사진별 노출 맞춤 끄기")
    # 2026-11-16 c3c1e8c7 방: 24 px·0.25(texture_fast 값) → 8 px·0.15 로 사진 받은 삼각형 66 → 72 % (키프레임 100 그대로)
    ap.add_argument("--margin", type=int, default=8, help="삼각형 중심이 사진 가장자리에서 떨어져야 하는 화소")
    ap.add_argument("--min-cos", type=float, default=0.15, help="면과 카메라 방향의 최소 cos (작을수록 비스듬한 사진도 쓴다)")
    ap.add_argument("--merge-overlap", type=float, default=0.25, help="같은 사진의 차트 상자가 이만큼(작은 쪽 넓이 대비) 겹치면 하나로 합친다")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    t0 = time.time()
    log = lambda m: print(f"[{time.time() - t0:6.1f}s] {m}", flush=True)

    mesh = prepare_mesh(args.mesh, args.cluster_voxel, args.min_component, args.target_tris, log)
    V = np.asarray(mesh.vertices, dtype=np.float64)
    Fc = np.asarray(mesh.triangles).copy()
    VC = np.asarray(mesh.vertex_colors) if mesh.has_vertex_colors() else np.full((len(V), 3), 0.5)
    TN = np.asarray(mesh.triangle_normals).copy()
    nF = len(Fc)

    _, frames = read_odometry(os.path.join(args.data, "odometry.csv"))
    keys = pick_keyframes(os.path.join(args.data, "rgb.mp4"), frames, args.keyframes, log, read_frame_quality(args.data))
    Fx = np.eye(4) if args.convention == "cv" else F_ARKIT_TO_CV
    imgs = [k[2] for k in keys]
    sharp = np.array([k[0] for k in keys], np.float64)
    Ks = [frames[k[1]]["K"] for k in keys]
    T_WCs = [frames[k[1]]["T_WC"] @ Fx for k in keys]
    h, w = imgs[0].shape[:2]
    nK = len(imgs)
    dmaps, sw, sh = depth_maps(mesh, Ks, T_WCs, w, h, args.depth_scale)
    log(f"keyframes {nK} x {w}x{h}; depth maps {sw}x{sh}")

    # ── 삼각형마다 사진 점수 (texture_fast 와 같은 규칙) ──
    cent = V[Fc].mean(axis=1)
    score = np.full((nF, nK), -1.0, np.float64)
    sharp_w = 0.6 + 0.4 * (sharp - sharp.min()) / max(1e-6, sharp.max() - sharp.min())
    for k in range(nK):
        T_CW = np.linalg.inv(T_WCs[k]); K = Ks[k]
        pc = cent @ T_CW[:3, :3].T + T_CW[:3, 3]
        z = pc[:, 2]
        ok = z > 0.15
        u = K[0, 0] * pc[:, 0] / np.where(ok, z, 1) + K[0, 2]
        v = K[1, 1] * pc[:, 1] / np.where(ok, z, 1) + K[1, 2]
        m = args.margin
        ok &= (u > m) & (u < w - m) & (v > m) & (v < h - m)
        # 세 꼭짓점이 모두 사진 안이어야 차트가 사진 밖으로 커지지 않는다
        Pv = V[Fc].reshape(-1, 3) @ T_CW[:3, :3].T + T_CW[:3, 3]
        zv = Pv[:, 2]
        uv_ = np.stack([K[0, 0] * Pv[:, 0] / np.maximum(zv, 1e-3) + K[0, 2], K[1, 1] * Pv[:, 1] / np.maximum(zv, 1e-3) + K[1, 2]], 1)
        inside = (zv > 0.05) & (uv_[:, 0] > 1) & (uv_[:, 0] < w - 2) & (uv_[:, 1] > 1) & (uv_[:, 1] < h - 2)
        ok &= inside.reshape(-1, 3).all(axis=1)
        ui = np.clip((u * args.depth_scale).astype(int), 0, sw - 1)
        vi = np.clip((v * args.depth_scale).astype(int), 0, sh - 1)
        ok &= z <= dmaps[k][vi, ui] + 0.03 + 0.02 * z
        to_cam = T_WCs[k][:3, 3] - cent
        to_cam /= np.linalg.norm(to_cam, axis=1, keepdims=True) + 1e-9
        cosang = np.abs((TN * to_cam).sum(axis=1))
        ok &= cosang > args.min_cos
        border = np.minimum(np.minimum(u, w - u), np.minimum(v, h - v)) / (0.25 * min(w, h))
        score[:, k] = np.where(ok, cosang * (1.0 / (z + 0.3)) * sharp_w[k] * np.clip(border, 0.3, 1.0), -1.0)
    best = score.argmax(axis=1)
    smax = score.max(axis=1)
    has_view = smax > 0
    log(f"view selection: {has_view.mean() * 100:.1f}% of triangles have a photo view")

    e = np.sort(np.concatenate([Fc[:, [0, 1]], Fc[:, [1, 2]], Fc[:, [2, 0]]]), axis=1)
    e_tri = np.tile(np.arange(nF), 3)
    key = e[:, 0].astype(np.int64) * len(V) + e[:, 1]
    order = np.argsort(key, kind="stable")
    key_s, tri_s = key[order], e_tri[order]
    same = key_s[1:] == key_s[:-1]
    adj_a, adj_b = tri_s[:-1][same], tri_s[1:][same]
    for it in range(args.vote_iters):
        votes = np.zeros((nF, nK), np.float32)
        np.add.at(votes, (adj_a, best[adj_b]), 1.0)
        np.add.at(votes, (adj_b, best[adj_a]), 1.0)
        cand = np.where(score > 0, score + 0.5 * smax[:, None] * votes, -1.0)
        new_best = cand.argmax(axis=1)
        changed = (new_best != best) & has_view
        best = np.where(has_view, new_best, best)
        if changed.sum() < nF * 0.002:
            break
    log(f"view voting: {it + 1} iterations")

    # ── 면 방향 (texture_fast 와 같음): 텍스처를 준 카메라 쪽이 앞면 ──
    cams = np.array([T_[:3, 3] for T_ in T_WCs])
    face_cam = np.empty(nF, np.int64)
    face_cam[has_view] = best[has_view]
    nv = np.flatnonzero(~has_view)
    for s0 in range(0, len(nv), 20000):
        idx = nv[s0:s0 + 20000]
        face_cam[idx] = np.argmin(((cent[idx, None, :] - cams[None, :, :]) ** 2).sum(-1), axis=1)
    flip = ((cams[face_cam] - cent) * TN).sum(axis=1) < 0
    Fc[flip] = Fc[flip][:, [0, 2, 1]]
    TN = np.where(flip[:, None], -TN, TN)

    # ── 사진별 노출 맞춤: 같은 삼각형을 본 상위 두 사진의 색 비 → 사진별 log 이득 (채널별 최소제곱) ──
    gains = np.ones((nK, 3), np.float64)
    if not args.no_gain and nK > 1:
        two = np.argsort(-score, axis=1)[:, :2]
        okp = (score[np.arange(nF), two[:, 0]] > 0) & (score[np.arange(nF), two[:, 1]] > 0)
        idx = np.flatnonzero(okp)
        rng = np.random.default_rng(0)
        if len(idx) > 40000:
            idx = rng.choice(idx, 40000, replace=False)
        cols = []
        for j in (0, 1):
            c = np.zeros((len(idx), 3))
            for k in np.unique(two[idx, j]):
                s_ = idx[two[idx, j] == k]
                T_CW = np.linalg.inv(T_WCs[k]); K = Ks[k]
                pc = cent[s_] @ T_CW[:3, :3].T + T_CW[:3, 3]
                u = K[0, 0] * pc[:, 0] / pc[:, 2] + K[0, 2]
                v = K[1, 1] * pc[:, 1] / pc[:, 2] + K[1, 2]
                c[two[idx, j] == k] = bilinear(cv2.blur(imgs[k], (5, 5)), u, v)
            cols.append(c)
        c1, c2 = cols[0] + 1.0, cols[1] + 1.0
        good = (c1.min(1) > 16) & (c2.min(1) > 16) & (c1.max(1) < 250) & (c2.max(1) < 250)
        d = np.log(c1) - np.log(c2)
        good &= np.abs(d).max(1) < 0.6
        k1, k2 = two[idx, 0][good], two[idx, 1][good]
        lam = 0.05 * max(1, good.sum()) / nK
        for ch in range(3):
            A = np.zeros((nK, nK)); bb = np.zeros(nK)
            dd = d[good, ch]
            # (g_k1 - g_k2) ≈ -dd  → 정규방정식
            np.add.at(A, (k1, k1), 1); np.add.at(A, (k2, k2), 1)
            np.add.at(A, (k1, k2), -1); np.add.at(A, (k2, k1), -1)
            np.add.at(bb, k1, -dd); np.add.at(bb, k2, dd)
            A += lam * np.eye(nK)
            g = np.linalg.solve(A, bb)
            gains[:, ch] = np.exp(np.clip(g - np.median(g), -0.35, 0.35))
        log(f"exposure gains from {int(good.sum())} pairs: min {gains.min():.3f} max {gains.max():.3f}")

    # ── 차트: 같은 사진을 고른, 변으로 이어진 삼각형 묶음 ──
    tv = has_view[adj_a] & has_view[adj_b] & (best[adj_a] == best[adj_b])
    lab = components(nF, adj_a[tv], adj_b[tv])
    vis = np.flatnonzero(has_view)
    uniq, chart_of = np.unique(lab[vis], return_inverse=True)
    nC = len(uniq)
    chart = np.full(nF, -1, np.int64)
    chart[vis] = chart_of
    chart_view = np.zeros(nC, np.int64)
    chart_view[chart_of] = best[vis]
    # 꼭짓점을 그 차트 사진에 투영
    uvp = np.zeros((nF, 3, 2), np.float64)
    for k in np.unique(best[vis]):
        s_ = vis[best[vis] == k]
        T_CW = np.linalg.inv(T_WCs[k]); K = Ks[k]
        P = V[Fc[s_]].reshape(-1, 3) @ T_CW[:3, :3].T + T_CW[:3, 3]
        z = np.maximum(P[:, 2], 0.05)
        uvp[s_] = np.stack([K[0, 0] * P[:, 0] / z + K[0, 2], K[1, 1] * P[:, 1] / z + K[1, 2]], 1).reshape(-1, 3, 2)
    lo = np.full((nC, 2), np.inf); hi = np.full((nC, 2), -np.inf)
    np.minimum.at(lo, chart[vis], uvp[vis].min(axis=1))
    np.maximum.at(hi, chart[vis], uvp[vis].max(axis=1))
    lo = np.floor(lo); hi = np.ceil(hi)
    # 같은 사진에서 상자가 많이 겹치는 차트는 하나로 합친다 (겹친 화소를 두 번 넣지 않아 배율이 올라간다)
    n_before = nC
    grp = np.arange(nC)
    for k in np.unique(chart_view):
        ids = np.flatnonzero(chart_view == k)
        if len(ids) < 2:
            continue
        boxes = [[lo[i, 0], lo[i, 1], hi[i, 0], hi[i, 1], [int(i)]] for i in ids]
        changed = True
        while changed:
            changed = False
            boxes.sort(key=lambda b: -(b[2] - b[0]) * (b[3] - b[1]))
            out = []
            for b in boxes:
                for o in out:
                    ix = min(b[2], o[2]) - max(b[0], o[0]); iy = min(b[3], o[3]) - max(b[1], o[1])
                    if ix > 0 and iy > 0:
                        small = min((b[2] - b[0]) * (b[3] - b[1]), (o[2] - o[0]) * (o[3] - o[1]))
                        if ix * iy >= args.merge_overlap * max(small, 1.0):
                            o[0], o[1] = min(o[0], b[0]), min(o[1], b[1])
                            o[2], o[3] = max(o[2], b[2]), max(o[3], b[3])
                            o[4] += b[4]
                            changed = True
                            break
                else:
                    out.append(b)
            boxes = out
        for b in boxes:
            r = b[4][0]
            grp[b[4]] = r
            lo[r] = b[0:2]; hi[r] = b[2:4]
    ug, ginv = np.unique(grp, return_inverse=True)
    lo, hi, chart_view = lo[ug], hi[ug], chart_view[ug]
    chart[vis] = ginv[chart[vis]]
    nC = len(ug)
    log(f"merged overlapping charts: {n_before} -> {nC}")
    cw, ch_ =np.maximum(hi[:, 0] - lo[:, 0], 1), np.maximum(hi[:, 1] - lo[:, 1], 1)
    e1, e2 = uvp[vis, 1] - uvp[vis, 0], uvp[vis, 2] - uvp[vis, 0]
    tri_area = 0.5 * np.abs(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0])
    fill = tri_area.sum() / (cw * ch_).sum()
    log(f"charts: {nC} (largest {int(cw.max())}x{int(ch_.max())} px), bbox fill {fill * 100:.0f}%")

    # 사진 없는 삼각형: 4 px 단색 칸
    n_nv = len(nv)
    cell = 4
    T = args.tex_size
    pad = args.pad
    total = float((cw * ch_).sum())
    scale = min(args.max_scale, np.sqrt(0.82 * (T * T - n_nv * cell * cell) / max(total, 1.0)))
    while True:
        ws = np.concatenate([np.ceil(cw * scale).astype(np.int64) + 2 * pad, np.full(n_nv, cell, np.int64)])
        hs = np.concatenate([np.ceil(ch_ * scale).astype(np.int64) + 2 * pad, np.full(n_nv, cell, np.int64)])
        pos = shelf_pack(ws, hs, T)
        if pos is not None:
            break
        scale *= 0.95
    log(f"packing: scale {scale:.3f} of photo resolution, {nC} charts + {n_nv} solid cells into {T}x{T}")

    # ── 텍스처 채우기 ──
    atlas = np.zeros((T, T, 3), np.uint8)
    for c in range(nC):
        k = chart_view[c]
        x, y = pos[c]
        wc, hc = ws[c], hs[c]
        M = np.array([[scale, 0, pad - lo[c, 0] * scale], [0, scale, pad - lo[c, 1] * scale]], np.float64)
        src = imgs[k]
        if scale < 0.75:                       # 크게 줄일 때 계단 무늬 방지
            sig = 0.5 / scale
            src = cv2.GaussianBlur(src, (0, 0), sig * 0.6)
        patch = cv2.warpAffine(src, M, (int(wc), int(hc)), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        if not args.no_gain:
            patch = np.clip(patch.astype(np.float32) * gains[k][None, None, :].astype(np.float32), 0, 255).astype(np.uint8)
        atlas[y:y + hc, x:x + wc] = patch
    tri_px = np.zeros((nF, 3, 2), np.float64)
    tri_px[vis] = (uvp[vis] - lo[chart[vis]][:, None, :]) * scale + pad + pos[chart[vis]][:, None, :]
    for j, f in enumerate(nv):
        x, y = pos[nC + j]
        atlas[y:y + cell, x:x + cell] = np.clip(VC[Fc[f]].mean(0) * 255, 0, 255).astype(np.uint8)
        tri_px[f] = [[x + 1, y + 1], [x + 3, y + 1], [x + 1, y + 3]]
    log(f"atlas filled; textured triangles {has_view.mean() * 100:.1f}%")
    cv2.imwrite(os.path.join(args.out, "atlas_thumb.jpg"),
                cv2.cvtColor(cv2.resize(atlas, (1024, 1024), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2BGR))

    # ── GLB (texture_fast 와 같은 방식: 모서리마다 UV, 평면 법선) ──
    import io
    import trimesh
    from PIL import Image
    uv = tri_px / T
    uv[..., 1] = 1.0 - uv[..., 1]
    Vs = V[Fc].reshape(-1, 3)
    Ns = np.repeat(TN, 3, axis=0)
    Fs = np.arange(len(Vs)).reshape(-1, 3)
    tex_img = Image.fromarray(atlas)
    if args.jpeg_quality > 0:
        buf = io.BytesIO()
        tex_img.save(buf, format="JPEG", quality=args.jpeg_quality)
        buf.seek(0)
        tex_img = Image.open(buf)
        tex_img.load()
    mat = trimesh.visual.material.PBRMaterial(baseColorTexture=tex_img, metallicFactor=0.0, roughnessFactor=1.0, doubleSided=False)
    tm = trimesh.Trimesh(vertices=Vs, faces=Fs, vertex_normals=Ns, visual=trimesh.visual.TextureVisuals(uv=uv.reshape(-1, 2), material=mat),
                         process=False)
    glb_path = os.path.join(args.out, "mesh_tex.glb")
    tm.export(glb_path)
    stats = dict(method="charts", triangles=int(nF), keyframes=nK, tex_size=T, charts=int(nC), scale=round(float(scale), 3),
                 bbox_fill=round(float(fill), 3), textured_triangles_pct=round(float(has_view.mean() * 100), 1),
                 gain_min=round(float(gains.min()), 3), gain_max=round(float(gains.max()), 3),
                 glb_bytes=os.path.getsize(glb_path), seconds_total=round(time.time() - t0, 1))
    with open(os.path.join(args.out, "stats_tex.json"), "w") as f:
        json.dump(stats, f, indent=2)
    log(json.dumps(stats))


if __name__ == "__main__":
    main()
