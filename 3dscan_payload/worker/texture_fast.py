"""
Fast photo texturing for a fused Stray Scanner mesh (no UV unwrapping, no Open3D projection).

  python -I scripts/texture_fast.py --data <dataset_dir> --mesh <mesh.ply> --out <out_dir>
         [--target-tris 120000] [--keyframes 100] [--tex-size 4096] [--cluster-voxel 0.02]

Method
  * atlas layout: one square cell per pair of triangles (deterministic, instant)
  * per triangle: pick the best keyframe = visible (depth test against a ray-cast depth map),
    facing the camera, close, sharp
  * per texel: barycentric -> 3D point -> project into the chosen keyframe -> bilinear sample
  * triangles seen by no keyframe fall back to the fused vertex colours
  * GLB export with the texture embedded (metallic 0, roughness 1)
"""
import argparse
import json
import os
import sys
import time

import cv2
import numpy as np
import open3d as o3d
import open3d.core as o3c

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stray_to_mesh import read_odometry, F_ARKIT_TO_CV  # noqa: E402


def pick_keyframes(video_path, frames, n_keep, log):
    """Read the video once; within each window keep the sharpest frame (variance of Laplacian)."""
    cap = cv2.VideoCapture(video_path)
    n = min(int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), len(frames))
    win = max(1, n // n_keep)
    best = {}  # window -> (score, idx, rgb)
    i = 0
    t0 = time.time()
    while i < n:
        ok, bgr = cap.read()
        if not ok:
            break
        small = cv2.cvtColor(cv2.resize(bgr, (480, 360), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
        score = cv2.Laplacian(small, cv2.CV_64F).var()
        w = i // win
        if w not in best or score > best[w][0]:
            best[w] = (score, i, cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        i += 1
    cap.release()
    keys = sorted(best.values(), key=lambda t: t[1])
    log(f"keyframes: {len(keys)} of {n} frames (window {win}); sharpness "
        f"min {min(k[0] for k in keys):.0f} max {max(k[0] for k in keys):.0f} ({time.time() - t0:.1f}s)")
    return keys


def prepare_mesh(path, cluster_voxel, min_component, target_tris, log):
    mesh = o3d.io.read_triangle_mesh(path)
    log(f"input mesh: {len(mesh.vertices)} verts, {len(mesh.triangles)} tris")
    if cluster_voxel > 0:
        mesh = mesh.simplify_vertex_clustering(
            voxel_size=cluster_voxel, contraction=o3d.geometry.SimplificationContraction.Average)
    if min_component > 0:
        with o3d.utility.VerbosityContextManager(o3d.utility.VerbosityLevel.Error):
            cl, n_tri, _ = mesh.cluster_connected_triangles()
        cl, n_tri = np.asarray(cl), np.asarray(n_tri)
        mesh.remove_triangles_by_mask(n_tri[cl] < min_component)
        mesh.remove_unreferenced_vertices()
    if len(mesh.triangles) > target_tris:
        mesh = mesh.simplify_quadric_decimation(target_number_of_triangles=target_tris)
    mesh.remove_degenerate_triangles()
    mesh.remove_duplicated_triangles()
    mesh.remove_unreferenced_vertices()
    mesh.compute_vertex_normals()
    mesh.compute_triangle_normals()
    log(f"prepared mesh: {len(mesh.vertices)} verts, {len(mesh.triangles)} tris")
    return mesh


def bilinear(img, u, v):
    """Bilinear sample of an (H,W,3) uint8 image at float pixel coords (N,) -> (N,3) uint8."""
    h, w = img.shape[:2]
    u = np.clip(u, 0, w - 1.001); v = np.clip(v, 0, h - 1.001)
    x0 = u.astype(np.int32); y0 = v.astype(np.int32)
    fx = (u - x0)[:, None]; fy = (v - y0)[:, None]
    c00 = img[y0, x0].astype(np.float32); c01 = img[y0, x0 + 1].astype(np.float32)
    c10 = img[y0 + 1, x0].astype(np.float32); c11 = img[y0 + 1, x0 + 1].astype(np.float32)
    c = (c00 * (1 - fx) + c01 * fx) * (1 - fy) + (c10 * (1 - fx) + c11 * fx) * fy
    return np.clip(c + 0.5, 0, 255).astype(np.uint8)


def depth_maps(mesh, Ks, T_WCs, w, h, scale):
    """Ray-cast depth maps of the mesh from every keyframe at reduced resolution."""
    scene = o3d.t.geometry.RaycastingScene()
    scene.add_triangles(o3d.t.geometry.TriangleMesh.from_legacy(mesh))
    sw, sh = int(w * scale), int(h * scale)
    maps = np.empty((len(Ks), sh, sw), np.float32)
    for i, (K, T_WC) in enumerate(zip(Ks, T_WCs)):
        Ks_ = K.copy(); Ks_[:2] *= scale
        rays = scene.create_rays_pinhole(o3c.Tensor(Ks_, o3c.float64), o3c.Tensor(np.linalg.inv(T_WC), o3c.float64), sw, sh)
        hit = scene.cast_rays(rays)
        t = hit["t_hit"].numpy()                       # distance along the ray
        d = rays.numpy()[..., 3:6]                     # ray directions (not unit length)
        # convert ray distance to z depth: t * dir_z_in_camera; dir in world -> rotate to camera
        R_cw = np.linalg.inv(T_WC)[:3, :3]
        dz = d.reshape(-1, 3) @ R_cw[2]
        z = (t.reshape(-1) * dz).reshape(sh, sw)
        z[~np.isfinite(z)] = np.inf
        maps[i] = z
    return maps, sw, sh


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
    ap.add_argument("--depth-scale", type=float, default=0.25, help="depth-map resolution relative to the photo")
    ap.add_argument("--convention", choices=["cv", "arkit"], default="cv")
    ap.add_argument("--jpeg-quality", type=int, default=0, help="embed the texture as JPEG at this quality (0 = PNG)")
    ap.add_argument("--no-normals", action="store_true", help="omit vertex normals from the GLB (smaller file)")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    t0 = time.time()
    log = lambda m: print(f"[{time.time() - t0:6.1f}s] {m}", flush=True)

    mesh = prepare_mesh(args.mesh, args.cluster_voxel, args.min_component, args.target_tris, log)
    V = np.asarray(mesh.vertices, dtype=np.float64)
    Fc = np.asarray(mesh.triangles)
    VC = np.asarray(mesh.vertex_colors) if mesh.has_vertex_colors() else np.full((len(V), 3), 0.5)
    TN = np.asarray(mesh.triangle_normals)
    nF = len(Fc)

    # keyframes
    _, frames = read_odometry(os.path.join(args.data, "odometry.csv"))
    keys = pick_keyframes(os.path.join(args.data, "rgb.mp4"), frames, args.keyframes, log)
    Fx = np.eye(4) if args.convention == "cv" else F_ARKIT_TO_CV
    imgs = [k[2] for k in keys]
    sharp = np.array([k[0] for k in keys], np.float64)
    Ks = [frames[k[1]]["K"] for k in keys]
    T_WCs = [frames[k[1]]["T_WC"] @ Fx for k in keys]
    h, w = imgs[0].shape[:2]
    nK = len(imgs)
    log(f"keyframes ready: {nK} x {w}x{h}")

    # depth maps for visibility
    dmaps, sw, sh = depth_maps(mesh, Ks, T_WCs, w, h, args.depth_scale)
    log(f"depth maps: {nK} x {sw}x{sh}")

    # ---- best view per triangle ------------------------------------------------------------
    cent = V[Fc].mean(axis=1)                                   # (F,3)
    score = np.full((nF, nK), -1.0, np.float64)
    sharp_w = 0.6 + 0.4 * (sharp - sharp.min()) / max(1e-6, sharp.max() - sharp.min())
    for k in range(nK):
        T_CW = np.linalg.inv(T_WCs[k]); K = Ks[k]
        pc = cent @ T_CW[:3, :3].T + T_CW[:3, 3]               # camera coords
        z = pc[:, 2]
        ok = z > 0.15
        u = K[0, 0] * pc[:, 0] / np.where(ok, z, 1) + K[0, 2]
        v = K[1, 1] * pc[:, 1] / np.where(ok, z, 1) + K[1, 2]
        m = 24
        ok &= (u > m) & (u < w - m) & (v > m) & (v < h - m)
        # visibility: compare with the ray-cast depth
        ui = np.clip((u * args.depth_scale).astype(int), 0, sw - 1)
        vi = np.clip((v * args.depth_scale).astype(int), 0, sh - 1)
        dz = dmaps[k][vi, ui]
        ok &= z <= dz + 0.03 + 0.02 * z
        # facing: angle between triangle normal and direction to the camera
        cam = T_WCs[k][:3, 3]
        to_cam = cam - cent
        to_cam /= np.linalg.norm(to_cam, axis=1, keepdims=True) + 1e-9
        cosang = np.abs((TN * to_cam).sum(axis=1))
        ok &= cosang > 0.25
        # closer + more frontal + sharper is better; border pixels slightly penalised
        border = np.minimum(np.minimum(u, w - u), np.minimum(v, h - v)) / (0.25 * min(w, h))
        s = cosang * (1.0 / (z + 0.3)) * sharp_w[k] * np.clip(border, 0.3, 1.0)
        score[:, k] = np.where(ok, s, -1.0)
    best = score.argmax(axis=1)
    smax = score.max(axis=1)
    has_view = smax > 0
    log(f"view selection: {has_view.mean() * 100:.1f}% of triangles have a photo view")

    # neighbour voting: pull adjacent triangles onto the same photo to reduce seams
    e = np.sort(np.concatenate([Fc[:, [0, 1]], Fc[:, [1, 2]], Fc[:, [2, 0]]]), axis=1)
    e_tri = np.tile(np.arange(nF), 3)
    key = e[:, 0].astype(np.int64) * len(V) + e[:, 1]
    order = np.argsort(key, kind="stable")
    key_s, tri_s = key[order], e_tri[order]
    same = key_s[1:] == key_s[:-1]
    adj_a, adj_b = tri_s[:-1][same], tri_s[1:][same]            # pairs of edge-adjacent triangles
    for it in range(4):
        votes = np.zeros((nF, nK), np.float32)
        np.add.at(votes, (adj_a, best[adj_b]), 1.0)
        np.add.at(votes, (adj_b, best[adj_a]), 1.0)
        bonus = 0.5 * smax[:, None] * votes                      # up to +1.5x own best score (3 neighbours)
        cand = np.where(score > 0, score + bonus, -1.0)
        new_best = cand.argmax(axis=1)
        changed = (new_best != best) & has_view
        best = np.where(has_view, new_best, best)
        log(f"  vote iteration {it + 1}: {changed.sum()} triangles switched view")
        if changed.sum() < nF * 0.002:
            break

    # ---- face orientation: front side = the side the camera saw ----------------------------------
    # The fused mesh's winding is mixed (only 55-70% of faces point at the scanner), so a single-sided viewer showed
    # ceilings from above and walls from outside. Facing every triangle toward the camera that textured it (or the
    # nearest keyframe camera when none did) gives a Scaniverse-style "dollhouse": from outside/above, walls and ceilings
    # are back faces and get culled, so you look into the room.
    cams = np.array([T_[:3, 3] for T_ in T_WCs])
    face_cam = np.empty(nF, np.int64)
    face_cam[has_view] = best[has_view]
    nv = np.flatnonzero(~has_view)
    for s0 in range(0, len(nv), 20000):
        idx = nv[s0:s0 + 20000]
        face_cam[idx] = np.argmin(((cent[idx, None, :] - cams[None, :, :]) ** 2).sum(-1), axis=1)
    flip = ((cams[face_cam] - cent) * TN).sum(axis=1) < 0
    Fc = Fc.copy()
    Fc[flip] = Fc[flip][:, [0, 2, 1]]
    TN = np.where(flip[:, None], -TN, TN)
    log(f"face orientation: flipped {flip.mean() * 100:.1f}% of triangles to face their camera")

    # ---- atlas layout: one square cell per two triangles ------------------------------------
    T = args.tex_size
    n_cells = int(np.ceil(np.sqrt(np.ceil(nF / 2))))
    s = T / n_cells
    g = min(1.5, s * 0.12)
    tri_id = np.arange(nF)
    cell = tri_id // 2
    cy, cx = np.divmod(cell, n_cells)
    x0, y0 = cx * s, cy * s
    lower = (tri_id % 2) == 0
    gd = g * 1.42                                              # keeps the two hypotenuses 2g apart across the diagonal
    A = np.stack([x0 + g, y0 + g], 1); B = np.stack([x0 + s - g - gd, y0 + g], 1); C = np.stack([x0 + g, y0 + s - g - gd], 1)
    D = np.stack([x0 + s - g, y0 + s - g], 1); C2 = np.stack([x0 + g + gd, y0 + s - g], 1); B2 = np.stack([x0 + s - g, y0 + g + gd], 1)
    tri_px = np.where(lower[:, None, None], np.stack([A, B, C], 1), np.stack([D, C2, B2], 1))  # (F,3,2) pixel coords
    log(f"atlas: {n_cells}x{n_cells} cells of {s:.1f}px")

    # ---- per-texel: triangle id + barycentric (clamped so gutters get the nearest triangle colour)
    atlas = np.zeros((T, T, 3), np.uint8)
    ys, xs = np.mgrid[0:T, 0:T]
    xs = xs.astype(np.float32) + 0.5; ys = ys.astype(np.float32) + 0.5
    cxi = np.minimum((xs / s).astype(np.int64), n_cells - 1); cyi = np.minimum((ys / s).astype(np.int64), n_cells - 1)
    cell_t = cyi * n_cells + cxi
    lx = xs - cxi * s; ly = ys - cyi * s
    is_lower = (lx + ly) < s
    tid = cell_t * 2 + np.where(is_lower, 0, 1)
    valid = tid < nF
    tid = np.where(valid, tid, 0)
    # barycentric w.r.t. the (inset) triangle corners
    P0 = tri_px[tid, 0]; P1 = tri_px[tid, 1]; P2 = tri_px[tid, 2]
    d00 = ((P1 - P0) ** 2).sum(-1); d01 = ((P1 - P0) * (P2 - P0)).sum(-1); d11 = ((P2 - P0) ** 2).sum(-1)
    px = np.stack([xs, ys], -1) - P0
    d20 = (px * (P1 - P0)).sum(-1); d21 = (px * (P2 - P0)).sum(-1)
    den = d00 * d11 - d01 * d01
    b1 = (d11 * d20 - d01 * d21) / den; b2 = (d00 * d21 - d01 * d20) / den
    b1 = np.clip(b1, 0, 1); b2 = np.clip(b2, 0, 1)
    ssum = np.maximum(b1 + b2, 1e-6)
    over = ssum > 1
    b1 = np.where(over, b1 / ssum, b1); b2 = np.where(over, b2 / ssum, b2)
    b0 = 1 - b1 - b2
    del ssum, over
    del P0, P1, P2, d00, d01, d11, px, d20, d21, den, lx, ly, cell_t, cxi, cyi
    log("texel -> triangle/barycentric done")

    # 3D point of every texel
    tv = Fc[tid]                                               # (T,T,3) vertex ids
    P = (b0[..., None] * V[tv[..., 0]] + b1[..., None] * V[tv[..., 1]] + b2[..., None] * V[tv[..., 2]]).astype(np.float32)
    # fallback colour from fused vertex colours
    fb = (b0[..., None] * VC[tv[..., 0]] + b1[..., None] * VC[tv[..., 1]] + b2[..., None] * VC[tv[..., 2]])
    atlas[:] = np.clip(fb * 255, 0, 255).astype(np.uint8)
    del fb, tv, b0, b1, b2
    log("texel 3D points done")

    # ---- sample photos, grouped by chosen view ------------------------------------------------
    view_of_texel = np.where(valid & has_view[tid], best[tid], -1)
    textured = 0
    for k in range(nK):
        sel = view_of_texel == k
        n = int(sel.sum())
        if n == 0:
            continue
        T_CW = np.linalg.inv(T_WCs[k]); K = Ks[k]
        pts = P[sel] @ T_CW[:3, :3].T.astype(np.float32) + T_CW[:3, 3].astype(np.float32)
        z = np.maximum(pts[:, 2], 1e-3)
        u = (K[0, 0] * pts[:, 0] / z + K[0, 2]).astype(np.float32)
        v = (K[1, 1] * pts[:, 1] / z + K[1, 2]).astype(np.float32)
        atlas[sel] = bilinear(imgs[k], u, v)
        textured += n
    log(f"sampled {textured / (T * T) * 100:.1f}% of texels from photos")
    cv2.imwrite(os.path.join(args.out, "atlas.png"), cv2.cvtColor(atlas, cv2.COLOR_RGB2BGR))
    cv2.imwrite(os.path.join(args.out, "atlas_thumb.jpg"), cv2.cvtColor(cv2.resize(atlas, (1024, 1024), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2BGR))

    # ---- GLB with per-corner UVs (OBJ convention: v up) --------------------------------------
    import trimesh
    from PIL import Image
    uv = tri_px / T
    uv[..., 1] = 1.0 - uv[..., 1]
    Vs = V[Fc].reshape(-1, 3)
    Ns = np.repeat(TN, 3, axis=0)                              # flat normals that agree with the (re-oriented) winding
    Fs = np.arange(len(Vs)).reshape(-1, 3)
    tex_img = Image.fromarray(atlas)
    if args.jpeg_quality > 0:
        import io
        buf = io.BytesIO()
        tex_img.save(buf, format="JPEG", quality=args.jpeg_quality)
        buf.seek(0)
        tex_img = Image.open(buf)          # keeps format=JPEG so the GLB embeds JPEG instead of PNG
        tex_img.load()
    mat = trimesh.visual.material.PBRMaterial(
        baseColorTexture=tex_img, metallicFactor=0.0, roughnessFactor=1.0, doubleSided=False)
    vis = trimesh.visual.TextureVisuals(uv=uv.reshape(-1, 2), material=mat)
    tm = trimesh.Trimesh(vertices=Vs, faces=Fs, vertex_normals=None if args.no_normals else Ns, visual=vis, process=False)
    glb_path = os.path.join(args.out, "mesh_tex.glb")
    tm.export(glb_path)
    stats = dict(triangles=int(nF), keyframes=nK, tex_size=T, cell_px=round(float(s), 1),
                 textured_triangles_pct=round(float(has_view.mean() * 100), 1),
                 glb_bytes=os.path.getsize(glb_path), seconds_total=round(time.time() - t0, 1))
    with open(os.path.join(args.out, "stats_tex.json"), "w") as f:
        json.dump(stats, f, indent=2)
    log(json.dumps(stats))


if __name__ == "__main__":
    main()
