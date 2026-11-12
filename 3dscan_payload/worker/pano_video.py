r"""kgeoScan VR 투어 — 영상 지점("제자리 두 바퀴") → 스티처 입력.  계약: docs/pano_contract.md 1.2절

촬영 페이지는 지점마다 sNN/video.mp4(또는 .webm) 하나와 spots.json 의 spot.video(녹화 정보 + IMU 자세 시계열)를 보낸다.
pano_stitch.stitch_spot 이 이 모듈로 영상을 '사진 목록'으로 바꾼 뒤 사진 모드와 같은 길(SIFT·묶음 조정·이음선·다중대역 합성)을 탄다.

  1) 1차 해독 (분석 해상도 960 px): 프레임 시각(PTS)·선명도(라플라시안 분산)·앞 프레임에서 화면이 움직인 양(위상 상관)
  2) 시각 맞춤: 영상에서 잰 움직임 ↔ IMU 회전으로 예측한 움직임이 가장 잘 맞는 시차 δ(±600 ms)와 화면 회전(0/90/180/270°)
  3) 핵심 프레임: 방향 칸(위·가운데·아래 띠 × yaw step°, 천장 띠는 90°)마다 '선명도 × 회전 속도' 점수가 가장 좋은 프레임.
     스티처의 가운데 가중 이음선은 화소마다 광축이 가장 가까운 프레임을 쓰므로, 이음선 양쪽 프레임의 위치 차이가
     (몸을 축으로 돌아도) 반지름 × step 정도로 작다 → 가까운 물체가 두 번 나오는 일이 크게 준다
  4) 2차 해독 (원본 해상도): 핵심 프레임마다 앞뒤 이웃 중 선명한 프레임을 IMU 회전 호모그래피 → ECC → DIS 광류로 맞춰
     견고 평균 (차이가 큰 화소 = 어긋남·지나간 사람은 자동으로 빠진다) → 잡음·압축 흔적이 준다
"""
import math
import os
import shutil
import tempfile
import time

import cv2
import numpy as np

D2R = math.pi / 180.0
AN_LONG = 960          # 분석 해상도 (긴 변)
PC_LONG = 480          # 위상 상관 해상도


def _fail(ps, msg):
    raise ps.InputError(msg)


# ───────────────────────── IMU ─────────────────────────
def imu_table(video, ps):
    """spot.video.imu → (T ms, Q (n,4) w,x,y,z 부호 연속, RATE °/s 또는 nan)"""
    rows = video.get("imu") or []
    T, Q, RT = [], [], []
    for r in rows:
        try:
            if isinstance(r, dict):
                t, q, rate = r.get("t"), r.get("q"), r.get("rate")
            else:
                t, q, rate = r[0], r[1:5], (r[5] if len(r) > 5 else None)
            q = [float(a) for a in q]
            if len(q) != 4 or not all(math.isfinite(a) for a in q):
                continue
            T.append(float(t))
            Q.append(q)
            RT.append(float(rate) if isinstance(rate, (int, float)) else float("nan"))
        except Exception:
            continue
    if len(T) < 10:
        _fail(ps, "영상 지점에 자세 기록(video.imu)이 없거나 너무 짧습니다")
    o = np.argsort(T, kind="stable")
    T = np.asarray(T, float)[o]
    Q = np.asarray(Q, float)[o]
    RT = np.asarray(RT, float)[o]
    Q /= np.maximum(np.linalg.norm(Q, axis=1, keepdims=True), 1e-12)
    for k in range(1, len(Q)):
        if Q[k] @ Q[k - 1] < 0:
            Q[k] = -Q[k]
    keep = np.concatenate([[True], np.diff(T) > 0])
    return T[keep], Q[keep], RT[keep]


def q_interp(T, Q, t):
    t = np.clip(np.asarray(t, float), T[0], T[-1])
    i = np.clip(np.searchsorted(T, t), 1, len(T) - 1)
    a = ((t - T[i - 1]) / np.maximum(T[i] - T[i - 1], 1e-9))[..., None]
    q = Q[i - 1] * (1 - a) + Q[i] * a
    return q / np.maximum(np.linalg.norm(q, axis=-1, keepdims=True), 1e-12)


def quats_to_R(q):
    w, x, y, z = q[..., 0], q[..., 1], q[..., 2], q[..., 3]
    R = np.empty(q.shape[:-1] + (3, 3))
    R[..., 0, 0] = 1 - 2 * (y * y + z * z)
    R[..., 0, 1] = 2 * (x * y - w * z)
    R[..., 0, 2] = 2 * (x * z + w * y)
    R[..., 1, 0] = 2 * (x * y + w * z)
    R[..., 1, 1] = 1 - 2 * (x * x + z * z)
    R[..., 1, 2] = 2 * (y * z - w * x)
    R[..., 2, 0] = 2 * (x * z - w * y)
    R[..., 2, 1] = 2 * (y * z + w * x)
    R[..., 2, 2] = 1 - 2 * (x * x + y * y)
    return R


def rate_at(T, Q, RT, t):
    """°/s. 기록된 rate 가 있으면 그것, 없으면 자세 차이로"""
    if np.isfinite(RT).sum() > 0.8 * len(RT):
        ok = np.isfinite(RT)
        return np.interp(t, T[ok], RT[ok])
    h = 25.0
    Ra = quats_to_R(q_interp(T, Q, np.asarray(t) - h))
    Rb = quats_to_R(q_interp(T, Q, np.asarray(t) + h))
    c = (np.einsum("...ij,...ij->...", Ra, Rb) - 1) / 2
    return np.degrees(np.arccos(np.clip(c, -1, 1))) / (2 * h / 1000.0)


# ───────────────────────── 1차 해독 ─────────────────────────
def _rot_img(img, k):
    if k == 0:
        return img
    return cv2.rotate(img, {1: cv2.ROTATE_90_CLOCKWISE, 2: cv2.ROTATE_180, 3: cv2.ROTATE_90_COUNTERCLOCKWISE}[k])


def analyse(path, ps, prog, max_frames=5400, keep=None):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        _fail(ps, "영상을 열 수 없습니다 (코덱?)")
    fr = []
    prev = None
    win = None
    size = None
    fps_hint = cap.get(cv2.CAP_PROP_FPS) or 30.0
    k = 0
    while k < max_frames:
        ok, img = cap.read()
        if not ok:
            break
        pts = cap.get(cv2.CAP_PROP_POS_MSEC)
        h, w = img.shape[:2]
        if size is None:
            size = (w, h)
        s = AN_LONG / max(w, h)
        small = cv2.resize(img, (max(1, round(w * s)), max(1, round(h * s))), interpolation=cv2.INTER_AREA)
        g = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        hh, ww = g.shape
        c = g[hh // 10: hh - hh // 10, ww // 10: ww - ww // 10]
        lap = cv2.Laplacian(c, cv2.CV_32F, ksize=3)
        sharp = float(lap.var()) / max(1.0, float(c.mean())) ** 0.5          # 밝기 영향 약하게
        ps_ = PC_LONG / max(w, h)
        pc8 = cv2.resize(g, (max(8, round(w * ps_)), max(8, round(h * ps_))), interpolation=cv2.INTER_AREA)
        if keep is not None:
            keep.append(pc8)                     # 띠 모자이크: 흐름·노출 맞추기용 (480 px 회색, 900 프레임 ≈ 120 MB)
        pc = pc8.astype(np.float32)
        if win is None:
            win = cv2.createHanningWindow((pc.shape[1], pc.shape[0]), cv2.CV_32F)
        if prev is not None:
            (dx, dy), resp = cv2.phaseCorrelate(prev, pc, win)
        else:
            dx = dy = resp = 0.0
        fr.append({"pts": float(pts), "sharp": sharp, "dx": float(dx), "dy": float(dy), "resp": float(resp), "lum": float(g.mean())})
        prev = pc
        k += 1
        if k % 60 == 0:
            prog(min(3.0, 1 + k / 600.0), f"영상 읽는 중 ({k}프레임)")
    cap.release()
    if len(fr) < 10:
        _fail(ps, f"영상 프레임이 너무 적습니다 ({len(fr)})")
    t = np.array([f["pts"] for f in fr])
    if not np.all(np.diff(t) > 0):                  # PTS 를 못 주면 fps 로
        t = np.arange(len(fr)) * 1000.0 / fps_hint
        for f, tt in zip(fr, t):
            f["pts"] = float(tt)
    return fr, size, PC_LONG / max(size)


# ───────────────────────── 시각 맞춤 ─────────────────────────
def predicted_shift(Ra, Rb, f):
    """a 의 화면 가운데 내용이 b 에서 가 있는 자리 (px, 가운데 기준) — phaseCorrelate(a, b) 와 같은 부호"""
    d = np.einsum("...ji,...j->...i", Rb, Ra[..., :, 2])
    z = np.maximum(d[..., 2], 0.2)
    return f * d[..., 0] / z, f * d[..., 1] / z


def sync(fr, T, Q, f_pc, rots, search_ms=600.0):
    t = np.array([f["pts"] for f in fr])
    m = np.array([[f["dx"], f["dy"]] for f in fr])
    resp = np.array([f["resp"] for f in fr])
    sel = np.nonzero((resp > 0.08) & (np.arange(len(fr)) > 0))[0]
    if len(sel) < 20:
        return 0.0, 0, 0.0
    best = (-2.0, 0.0, 0)

    def score(delta, rk):
        Ra = quats_to_R(q_interp(T, Q, t[sel - 1] + delta))
        Rb = quats_to_R(q_interp(T, Q, t[sel] + delta))
        px, py = predicted_shift(Ra, Rb, f_pc)
        mx, my = m[sel, 0], m[sel, 1]
        for _ in range(rk):                       # 해독 화면을 시계 방향 90° 돌리면 움직임 (dx,dy) → (−dy, dx)
            mx, my = -my, mx
        num = (px * mx + py * my).sum()
        den = math.sqrt(float((px * px + py * py).sum() * (mx * mx + my * my).sum())) or 1.0
        return num / den
    for rk in rots:
        for delta in np.arange(-search_ms, search_ms + 1, 20.0):
            s = score(delta, rk)
            if s > best[0]:
                best = (s, float(delta), rk)
    s0, d0, rk = best
    for delta in np.arange(d0 - 20, d0 + 21, 2.0):
        s = score(delta, rk)
        if s > s0:
            s0, d0 = s, float(delta)
    return d0, rk, s0


# ───────────────────────── 핵심 프레임 ─────────────────────────
def select_keyframes(Rs, score, ok, step, zen_step=90.0, pole=62.0, band=12.0):
    ax = Rs[:, :, 2]
    yaw = np.degrees(np.arctan2(ax[:, 0], ax[:, 1])) % 360.0
    pitch = np.degrees(np.arcsin(np.clip(ax[:, 2], -1, 1)))
    cells = {}
    for k in np.nonzero(ok)[0]:
        p = pitch[k]
        if p < -pole:
            continue                               # 바로 아래(발·몸) — 스티처가 바닥을 메운다
        if p > pole:
            b, st = "zenith", zen_step
        elif p >= band:
            b, st = "up", step
        elif p <= -band:
            b, st = "down", step
        else:
            b, st = "mid", step
        yb = int(yaw[k] // st)
        cen = (yb + 0.5) * st
        dyaw = abs((yaw[k] - cen + 180) % 360 - 180) / (0.5 * st)
        v = score[k] * (0.7 + 0.3 * math.exp(-0.5 * dyaw * dyaw))
        key = (b, yb)
        if key not in cells or v > cells[key][0]:
            cells[key] = (v, int(k))
    keys = sorted(k for _, k in cells.values())
    # 띠마다 칸 수 (보고용)
    bands = {}
    for (b, _), _v in cells.items():
        bands[b] = bands.get(b, 0) + 1
    return keys, bands, yaw, pitch


def pick_neighbours(keys, Rs, sharp, ok, n_extra, span):
    out = {}
    N = len(Rs)
    for k in keys:
        cand = []
        for j in range(max(0, k - span), min(N, k + span + 1)):
            if j == k or not ok[j] or sharp[j] < 0.85 * sharp[k]:
                continue
            c = (np.trace(Rs[j].T @ Rs[k]) - 1) / 2
            if math.degrees(math.acos(max(-1.0, min(1.0, c)))) > 4.0:
                continue
            cand.append((-sharp[j], abs(j - k), j))
        cand.sort()
        out[k] = [c[2] for c in cand[:n_extra]]
    return out


# ───────────────────────── 합치기 ─────────────────────────
def _Kmat(f, w, h):
    return np.array([[f, 0, (w - 1) / 2.0], [0, f, (h - 1) / 2.0], [0, 0, 1.0]])


def align_fuse(key_img, neigh, Rk, Rn, f_full, sigma=9.0):
    """key_img: 핵심 프레임(BGR, 원본 해상도). neigh: [BGR], Rn: [3x3]. 반환 (합친 BGR, 쓴 이웃 수, 평균 가중)"""
    h, w = key_img.shape[:2]
    s = AN_LONG / max(w, h)
    ws, hs = max(1, round(w * s)), max(1, round(h * s))
    gk = cv2.cvtColor(cv2.resize(key_img, (ws, hs), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    Ks = _Kmat(f_full * s, ws, hs)
    S = np.diag([s, s, 1.0])
    acc = key_img.astype(np.float32)
    wsum = np.ones((h, w), np.float32)
    Yk = cv2.GaussianBlur(cv2.cvtColor(key_img, cv2.COLOR_BGR2GRAY).astype(np.float32), (0, 0), 1.2)
    dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    used, wmean = 0, []
    gx, gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    for img, Rj in zip(neigh, Rn):
        Hs = Ks @ Rj.T @ Rk @ np.linalg.inv(Ks)           # 핵심 화소 → 이웃 화소 (분석 해상도)
        Hs = (Hs / Hs[2, 2]).astype(np.float32)
        gj = cv2.cvtColor(cv2.resize(img, (ws, hs), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
        try:
            cc, Hs2 = cv2.findTransformECC(gk.astype(np.float32), gj.astype(np.float32), Hs.copy(), cv2.MOTION_HOMOGRAPHY,
                                           (cv2.TERM_CRITERIA_COUNT | cv2.TERM_CRITERIA_EPS, 60, 1e-5), None, 3)
            if cc > 0.6:
                Hs = Hs2
        except cv2.error:
            pass
        gjw = cv2.warpPerspective(gj, Hs, (ws, hs), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REPLICATE)
        fl = dis.calc(gk, gjw, None)                       # gjw(x + fl) ≈ gk(x)
        np.clip(fl, -12, 12, out=fl)
        Hf = np.linalg.inv(S) @ Hs.astype(np.float64) @ S
        flf = cv2.resize(fl, (w, h), interpolation=cv2.INTER_LINEAR) / s
        X = gx + flf[..., 0]
        Y = gy + flf[..., 1]
        del flf
        den = Hf[2, 0] * X + Hf[2, 1] * Y + Hf[2, 2]
        mx = ((Hf[0, 0] * X + Hf[0, 1] * Y + Hf[0, 2]) / den).astype(np.float32)
        my = ((Hf[1, 0] * X + Hf[1, 1] * Y + Hf[1, 2]) / den).astype(np.float32)
        del X, Y, den
        valid = (mx >= 0) & (mx <= w - 1) & (my >= 0) & (my <= h - 1)
        wj = cv2.remap(img, mx, my, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        del mx, my
        Yj = cv2.GaussianBlur(cv2.cvtColor(wj, cv2.COLOR_BGR2GRAY).astype(np.float32), (0, 0), 1.2)
        d = (Yj - Yk) / sigma
        wt = np.exp(-0.5 * d * d) * valid
        del d, Yj
        acc += wj.astype(np.float32) * wt[..., None]
        wsum += wt
        wmean.append(float(wt.mean()))
        used += 1
        del wj, wt
    out = np.clip(acc / wsum[..., None] + 0.5, 0, 255).astype(np.uint8)
    return out, used, (float(np.mean(wmean)) if wmean else 0.0)


# ───────────────────────── 입구 ─────────────────────────
def load_video_spot(src, spot, opts, prog, ps):
    """반환: imgs(list BGR), shots(list dict: file,q,t,w,h,src,lens,...), info(dict)"""
    t_start = time.time()
    v = spot.get("video") or {}
    name = v.get("file")
    if not name:
        _fail(ps, "영상 지점에 video.file 이 없습니다")
    T, Q, RT = imu_table(v, ps)
    tmpdir = None
    try:
        if src.zf is None:
            path = os.path.join(src.path, *name.replace("\\", "/").split("/"))
            if not os.path.isfile(path):
                _fail(ps, f"영상 파일이 없습니다: {name}")
        else:
            tmpdir = tempfile.mkdtemp(prefix="pano_video_")
            ext = os.path.splitext(name)[1].lower() or ".mp4"
            path = os.path.join(tmpdir, "video" + ext)
            try:
                data = src.read(name)
            except KeyError:
                _fail(ps, f"zip 안에 영상이 없습니다: {name}")
            with open(path, "wb") as fh:
                fh.write(data)
            del data
        prog(1, "영상 읽는 중")
        fr, (w0, h0), pc_scale = analyse(path, ps, prog)
        t_an = time.time() - t_start
        # 화면 회전 후보: 기록된 크기와 가로세로가 다르면 90/270, 같으면 0
        ew, eh = v.get("w"), v.get("h")
        if isinstance(ew, (int, float)) and isinstance(eh, (int, float)) and ew > 0 and eh > 0:
            rots = (0,) if (ew >= eh) == (w0 >= h0) else (1, 3)
        else:
            rots = (0, 1, 3)
        lens = v.get("lens") or (spot.get("cam") or {}).get("lens") or "wide"
        f_ratio = v.get("f_ratio") or (spot.get("cam") or {}).get("f_ratio")
        if not (isinstance(f_ratio, (int, float)) and 0.2 < f_ratio < 1.5):
            f_ratio = 0.40 if lens == "ultra" else 0.72
        if getattr(opts, "f_ratio", None):
            f_ratio = opts.f_ratio
        long0 = max(w0, h0)
        f_pc = f_ratio * long0 * pc_scale
        prog(3.2, "영상·자세 시각 맞추는 중")
        delta, rk, sync_score = sync(fr, T, Q, f_pc, rots)
        if rk in (1, 3):
            w, h = h0, w0
        else:
            w, h = w0, h0
        t = np.array([f["pts"] for f in fr]) + delta
        Rs = quats_to_R(q_interp(T, Q, t))
        rate = rate_at(T, Q, RT, t)
        sharp = np.array([f["sharp"] for f in fr])
        inside = (t >= T[0] - 50) & (t <= T[-1] + 50)
        # 선명도는 장면마다 달라 ±1 초 창의 중앙값으로 나눈다
        tw = 1000.0
        rel = np.empty(len(fr))
        for k in range(len(fr)):
            a, b = np.searchsorted(t, [t[k] - tw, t[k] + tw])
            rel[k] = sharp[k] / max(1e-6, float(np.median(sharp[a:b])))
        score = rel / (1.0 + (rate / 45.0) ** 2)
        lum = np.array([f["lum"] for f in fr])
        ok = inside & (score > 0.35 * np.median(score[inside] if inside.any() else score)) & (lum > 12)
        step = float(getattr(opts, "video_step", 12.0) or 12.0)
        keys, bands, yaw, pitch = select_keyframes(Rs, score, ok, step)
        vmax = int(getattr(opts, "video_max", 96) or 96)
        while len(keys) > vmax and step < 40:
            step *= 1.2
            keys, bands, yaw, pitch = select_keyframes(Rs, score, ok, step)
        if len(keys) < ps.MIN_SHOTS:
            _fail(ps, f"영상에서 쓸 만한 프레임이 {len(keys)}개뿐입니다 (흔들림·어두움?)")
        n_extra = max(0, int(getattr(opts, "video_fuse", 3) or 1) - 1)
        span = max(2, int(round(0.22 * 1000.0 / max(1.0, float(np.median(np.diff(t)))))))     # ±0.22 초
        neigh = pick_neighbours(keys, Rs, sharp, ok, n_extra, span) if n_extra else {k: [] for k in keys}
        need = {}
        for k in keys:
            for j in [k] + neigh[k]:
                need.setdefault(j, []).append(k)
        last_need = {k: max([k] + neigh[k]) for k in keys}
        prog(4, f"핵심 프레임 {len(keys)}개 합치는 중")
        # 2차 해독: 원본 해상도
        t2 = time.time()
        cap = cv2.VideoCapture(path)
        buf = {}
        imgs, shots = {}, {}
        fused_n, fused_w = [], []
        f_full = f_ratio * long0
        idx = 0
        done = 0
        max_need = max(need) if need else -1
        ended = False
        while idx <= max_need + 1:
            if idx <= max_need and cap.grab():
                if idx in need:
                    ok_, img = cap.retrieve()
                    if ok_:
                        buf[idx] = _rot_img(img, rk)
            else:
                ended = True                       # 영상이 먼저 끝남: 남은 핵심 프레임은 있는 이웃만으로
            for k in [k for k in keys if (last_need[k] == idx or ended) and k not in imgs]:
                if k not in buf:
                    continue
                nb = [j for j in neigh[k] if j in buf]
                if nb:
                    out, used, wm = align_fuse(buf[k], [buf[j] for j in nb], Rs[k], [Rs[j] for j in nb], f_full)
                else:
                    out, used, wm = buf[k], 0, 0.0
                imgs[k] = out
                fused_n.append(used + 1)
                fused_w.append(wm)
                y_, p_, r_ = ps.R_to_ypr(Rs[k])
                shots[k] = {"file": f"{name}#{k}", "t": int(round(t[k])), "w": int(w), "h": int(h), "src": "video", "lens": lens,
                            "q": [round(float(a), 7) for a in ps.R_to_quat(Rs[k])], "yaw": round(y_, 2), "pitch": round(p_, 2), "roll": round(r_, 2),
                            "rate": round(float(rate[k]), 1), "sharp_rel": round(float(rel[k]), 2), "fused": used + 1}
                done += 1
                if done % 6 == 0:
                    prog(4 + done / max(1, len(keys)), f"핵심 프레임 합치는 중 {done}/{len(keys)}")
            # 더 안 쓰는 프레임 버리기
            for j in [j for j in buf if all(kk in imgs for kk in need.get(j, []))]:
                del buf[j]
            if ended:
                break
            idx += 1
        cap.release()
        order = [k for k in keys if k in imgs]
        info = {
            "file": name, "frames": len(fr), "decoded_size": [int(w0), int(h0)], "size": [int(w), int(h)], "rotate_deg": rk * 90,
            "fps": round(1000.0 / max(1e-3, float(np.median(np.diff(t)))), 2), "dur_s": round((t[-1] - t[0]) / 1000.0, 2),
            "sync_ms": round(delta, 1), "sync_score": round(float(sync_score), 3),
            "keyframes": len(order), "bands": bands, "step_deg": round(step, 1),
            "fused_med": float(np.median(fused_n)) if fused_n else 1.0, "fuse_weight_mean": round(float(np.mean(fused_w)) if fused_w else 0.0, 3),
            "rate_med_dps": round(float(np.median(rate[inside])), 1) if inside.any() else None,
            "rate_p90_dps": round(float(np.percentile(rate[inside], 90)), 1) if inside.any() else None,
            "usable_frac": round(float(ok.mean()), 3), "f_ratio": f_ratio,
            "sec_analyse": round(t_an, 1), "sec_fuse": round(time.time() - t2, 1),
            "pitch_range": [round(float(pitch[ok].min()), 1), round(float(pitch[ok].max()), 1)] if ok.any() else None,
        }
        if info["sync_score"] < 0.5:
            ps.log(f"[{spot.get('id')}] 영상·자세 시각 맞춤이 약함 (일치 {info['sync_score']}) — 자세 초기값이 덜 정확할 수 있음")
        return [imgs[k] for k in order], [shots[k] for k in order], info
    finally:
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ═════════════════════ 띠 모자이크 (영상 기본) ═════════════════════
# 핵심 프레임(12° 간격) 대신 거의 모든 프레임을 1.5° 간격으로 쓰고, 화소마다 광축 yaw 가 가장 가까운 두 프레임을 섞는다.
# 이웃 프레임은 위치 차이가 몸 반지름 × 1.5° ≈ 8 mm 라 가까운 물체도 겹쳐 보이지 않는다 (12° 간격은 6 cm).
# 회전은 IMU(짧은 시간 상대 회전이 정확) + 선형 흐름(drift)·초점 배율을 '같은 yaw 의 위·아래 바퀴 짝'으로만 맞춘다
# — 같은 yaw 면 몸 방향이 같아 카메라 위치도 같으므로 시차가 없다 (같은 바퀴 안 이웃 짝은 시차를 '확대'로 흡수해 쓰지 않음).

def _rodr(w):
    return cv2.Rodrigues(np.asarray(w, np.float64).reshape(3, 1))[0]


def _smooth(a):
    a = np.clip(a, 0.0, 1.0)
    return a * a * (3 - 2 * a)


def _feats(cache, i, g, sift):
    if i not in cache:
        kp, de = sift.detectAndCompute(g, None)
        cache[i] = (np.float32([k.pt for k in kp]) if kp else np.zeros((0, 2), np.float32), de)
    return cache[i]


def _match_pair(ga, gb, ia, ib, Ra, Rb, f, sift, cache, tol=12.0):
    pa, da = _feats(cache, ia, ga, sift)
    pb, db = _feats(cache, ib, gb, sift)
    if da is None or db is None or len(pa) < 12 or len(pb) < 12:
        return None
    h, w = ga.shape
    K = _Kmat(f, w, h)
    Ki = np.linalg.inv(K)
    ra = np.c_[pa, np.ones(len(pa))] @ Ki.T
    cb = (ra @ Ra.T) @ Rb                                  # Rbᵀ Ra r (행 벡터)
    zb = np.maximum(cb[:, 2], 1e-3)
    pred = np.c_[K[0, 0] * cb[:, 0] / zb + K[0, 2], K[1, 1] * cb[:, 1] / zb + K[1, 2]]
    mm = cv2.BFMatcher(cv2.NORM_L2).knnMatch(da, db, k=2)
    A, B = [], []
    for m in mm:
        if len(m) < 2 or m[0].distance > 0.8 * m[1].distance:
            continue
        i, j = m[0].queryIdx, m[0].trainIdx
        if cb[i, 2] > 0.1 and float(np.hypot(*(pred[i] - pb[j]))) < tol:
            A.append(i)
            B.append(j)
    if len(A) < 12:
        return None
    a, b = pa[A], pb[B]
    Hh, inl = cv2.findHomography(a, b, cv2.RANSAC, 2.5)
    if Hh is None or inl is None or inl.sum() < 12:
        return None
    inl = inl.ravel() > 0
    return a[inl], b[inl]


def fit_drift_focal(pairs, f0, size, sig_c=0.0025, sig_s=0.06, iters=12):
    """pairs: [(pa, pb, Ra, Rb, ta, tb)] (분석 해상도 px, 시각 s). 모형: R' = exp([c·t]×) R, f = f0·e^ls.
    반환 c (rad/s, 3), s, 잔차 중앙값(px), 짝 수"""
    w, h = size
    if len(pairs) < 3:
        return np.zeros(3), 1.0, None, 0

    def resid(x):
        c, s = x[:3], math.exp(x[3])
        K = _Kmat(f0 * s, w, h)
        Ki = np.linalg.inv(K)
        out = []
        for pa, pb, Ra, Rb, ta, tb in pairs:
            A = _rodr(c * ta) @ Ra
            B = _rodr(c * tb) @ Rb
            for p, q, P, Q_ in ((pa, pb, A, B), (pb, pa, B, A)):
                r = np.c_[p, np.ones(len(p))] @ Ki.T
                cc = (r @ P.T) @ Q_
                z = np.maximum(cc[:, 2], 1e-3)
                out.append(np.c_[K[0, 0] * cc[:, 0] / z + K[0, 2] - q[:, 0], K[1, 1] * cc[:, 1] / z + K[1, 2] - q[:, 1]])
        return np.concatenate(out)
    x = np.zeros(4)
    prior = np.array([1 / sig_c] * 3 + [1 / sig_s])
    for _ in range(iters):
        r = resid(x)
        e = np.hypot(r[:, 0], r[:, 1])
        wh = np.sqrt(np.where(e < 2.0, 1.0, 2.0 / np.maximum(e, 1e-9)))[:, None]
        rv = (r * wh).ravel()
        J = np.zeros((len(rv), 4))
        for k in range(4):
            dx = np.zeros(4)
            dx[k] = 1e-5 if k < 3 else 1e-4
            J[:, k] = ((resid(x + dx) * wh).ravel() - rv) / dx[k]
        Hm = J.T @ J + np.diag(prior ** 2)
        g = J.T @ rv + prior ** 2 * x
        step = -np.linalg.solve(Hm, g)
        x = x + step
        if np.abs(step).max() < 1e-7:
            break
    r = resid(x)
    e = np.hypot(r[:, 0], r[:, 1])
    return x[:3], math.exp(x[3]), float(np.median(e)), int(len(e) // 2)


def _warp_to(ga, gb, Ra, Rb, f):
    """b 를 a 자리로 (순수 회전 호모그래피). 반환 (b 를 돌린 회색, 겹침)"""
    h, w = ga.shape
    K = _Kmat(f, w, h)
    Hh = (K @ Rb.T @ Ra @ np.linalg.inv(K)).astype(np.float32)
    gbw = cv2.warpPerspective(gb, Hh, (w, h), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderValue=0)
    val = cv2.warpPerspective(np.full((h, w), 255, np.uint8), Hh, (w, h), flags=cv2.INTER_NEAREST | cv2.WARP_INVERSE_MAP, borderValue=0) > 0
    return gbw, val


def _logratio(ga, gbw, val):
    m = val & (ga > 10) & (ga < 245) & (gbw > 10) & (gbw < 245)
    if int(m.sum()) < 400:
        return None
    return math.log(max(1.0, float(gbw[m].mean())) / max(1.0, float(ga[m].mean())))


def _extract(src, name, ps):
    if src.zf is None:
        path = os.path.join(src.path, *name.replace("\\", "/").split("/"))
        if not os.path.isfile(path):
            _fail(ps, f"영상 파일이 없습니다: {name}")
        return path, None
    tmpdir = tempfile.mkdtemp(prefix="pano_video_")
    path = os.path.join(tmpdir, "video" + (os.path.splitext(name)[1].lower() or ".mp4"))
    try:
        data = src.read(name)
    except KeyError:
        shutil.rmtree(tmpdir, ignore_errors=True)
        _fail(ps, f"zip 안에 영상이 없습니다: {name}")
    with open(path, "wb") as fh:
        fh.write(data)
    return path, tmpdir


def render_strip_spot(src, spot, out_dir, opts, prog, ps):
    t_start = time.time()
    sid = spot.get("id") or "s01"
    v = spot.get("video") or {}
    name = v.get("file")
    if not name:
        _fail(ps, "영상 지점에 video.file 이 없습니다")
    T, Q, RT = imu_table(v, ps)
    path, tmpdir = _extract(src, name, ps)
    try:
        prog(1, f"{sid} 영상 읽는 중")
        grays = []
        fr, (w0, h0), pc_scale = analyse(path, ps, prog, keep=grays)
        t_an = time.time() - t_start
        ew, eh = v.get("w"), v.get("h")
        if isinstance(ew, (int, float)) and isinstance(eh, (int, float)) and ew > 0 and eh > 0:
            rots = (0,) if (ew >= eh) == (w0 >= h0) else (1, 3)
        else:
            rots = (0, 1, 3)
        lens = v.get("lens") or (spot.get("cam") or {}).get("lens") or "wide"
        f_ratio = v.get("f_ratio") or (spot.get("cam") or {}).get("f_ratio")
        if not (isinstance(f_ratio, (int, float)) and 0.2 < f_ratio < 1.5):
            f_ratio = 0.40 if lens == "ultra" else 0.72
        if getattr(opts, "f_ratio", None):
            f_ratio = opts.f_ratio
        long0 = max(w0, h0)
        f_pc = f_ratio * long0 * pc_scale
        prog(3.2, f"{sid} 영상·자세 시각 맞추는 중")
        delta, rk, sync_score = sync(fr, T, Q, f_pc, rots)
        w, h = (h0, w0) if rk in (1, 3) else (w0, h0)
        if rk:
            grays = [_rot_img(g, rk) for g in grays]
        gsize = (grays[0].shape[1], grays[0].shape[0])
        t = np.array([f["pts"] for f in fr]) + delta
        Rs = quats_to_R(q_interp(T, Q, t))
        rate = rate_at(T, Q, RT, t)
        sharp = np.array([f["sharp"] for f in fr])
        lum = np.array([f["lum"] for f in fr])
        inside = (t >= T[0] - 50) & (t <= T[-1] + 50)
        rel = np.empty(len(fr))
        for k in range(len(fr)):
            a, b = np.searchsorted(t, [t[k] - 1000.0, t[k] + 1000.0])
            rel[k] = sharp[k] / max(1e-6, float(np.median(sharp[a:b])))
        score = rel / (1.0 + (rate / 45.0) ** 2)
        ok = inside & (score > 0.35 * np.median(score[inside] if inside.any() else score)) & (lum > 12)
        ts = (t - float(np.median(t))) / 1000.0
        ax = Rs[:, :, 2]
        pitch = np.degrees(np.arcsin(np.clip(ax[:, 2], -1, 1)))
        yaw = np.degrees(np.arctan2(ax[:, 0], ax[:, 1]))
        tn = {}
        for tt_ in v.get("turns") or []:
            if isinstance(tt_, dict) and isinstance(tt_.get("t0"), (int, float)) and tt_.get("name"):
                tn.setdefault(str(tt_["name"]), float(tt_["t0"]))
        turns_used = all(k in tn for k in ("turn1", "tilt", "turn2", "ceil"))
        if turns_used:
            t_end = tn.get("end", float(t[-1]) + 1)
            up = ok & (t >= tn["turn1"]) & (t <= tn["tilt"]) & (pitch > -5) & (pitch <= 65)
            dn = ok & (t >= tn["turn2"]) & (t <= tn["ceil"]) & (pitch < 5) & (pitch >= -65)
            zen = ok & (t >= tn["ceil"]) & (t <= t_end) & (pitch > 55)
        else:
            up = ok & (pitch >= 10) & (pitch <= 62)
            dn = ok & (pitch <= -10) & (pitch >= -62)
            zen = ok & (pitch > 62)
        # ── 흐름·초점: 위·아래 바퀴 같은 yaw 짝 + 같은 바퀴 시작·끝 짝 (둘 다 카메라 위치가 같아 시차 없음)
        prog(3.6, f"{sid} 자세 흐름 맞추는 중")
        sift = cv2.SIFT_create(nfeatures=1200, contrastThreshold=0.02)
        cache = {}
        pairs, pinfo = [], []

        def best_near(mask, y0, tol):
            d = np.abs((yaw - y0 + 180) % 360 - 180)
            c = np.nonzero(mask & (d < tol))[0]
            return int(c[np.argmax(score[c])]) if len(c) else None
        f_g0 = f_ratio * max(gsize)
        if up.any() and dn.any():
            for y0 in np.arange(-180, 180, 15.0):
                a = best_near(up, y0, 3.0)
                if a is None:
                    continue
                b = best_near(dn, yaw[a], 4.0)
                if b is None:
                    continue
                r = _match_pair(grays[a], grays[b], a, b, Rs[a], Rs[b], f_g0, sift, cache)
                if r is not None:
                    pairs.append((r[0], r[1], Rs[a], Rs[b], ts[a], ts[b]))
                    pinfo.append(("cross", a, b, int(len(r[0]))))
        for band in (up, dn):
            idx = np.nonzero(band)[0]
            if len(idx) < 10:
                continue
            first = idx[t[idx] < t[idx[0]] + 2500]
            for a in first[:: max(1, len(first) // 3)]:
                b = best_near(band & (t > t[a] + 5000), yaw[a], 2.0)
                if b is None:
                    continue
                r = _match_pair(grays[a], grays[b], int(a), b, Rs[a], Rs[b], f_g0, sift, cache)
                if r is not None:
                    pairs.append((r[0], r[1], Rs[a], Rs[b], ts[a], ts[b]))
                    pinfo.append(("loop", int(a), b, int(len(r[0]))))
        c_drift, s_f, fit_res, fit_n = fit_drift_focal(pairs, f_g0, gsize)
        if np.linalg.norm(c_drift) > 0.5 * D2R:
            ps.log(f"[{sid}] 흐름 {np.degrees(np.linalg.norm(c_drift)):.2f}°/s — 너무 커서 쓰지 않음")
            c_drift, s_f = np.zeros(3), 1.0
        if not (0.9 <= s_f <= 1.1):
            s_f = 1.0
        Rc = np.stack([_rodr(c_drift * ts[k]) @ Rs[k] for k in range(len(Rs))])
        f_full = f_ratio * long0 * s_f
        f_g = f_g0 * s_f
        # 짝마다 남은 상대 회전(빛살 Kabsch)을 반씩 두 프레임 시각에 두고, 시각으로 보간해 모든 프레임에 (IMU 의 느린 흔들림 0.2~0.4°)
        Kg = _Kmat(f_g, gsize[0], gsize[1])
        Kgi = np.linalg.inv(Kg)
        e_t, e_v = [], []
        for (pa, pb, _Ra, _Rb, _ta, _tb), (_kind, a, b, _n) in zip(pairs, pinfo):
            ra = np.c_[pa, np.ones(len(pa))] @ Kgi.T
            rb = np.c_[pb, np.ones(len(pb))] @ Kgi.T
            ra /= np.linalg.norm(ra, axis=1, keepdims=True)
            rb /= np.linalg.norm(rb, axis=1, keepdims=True)
            U, _S, Vt = np.linalg.svd(rb.T @ ra)
            dd = np.sign(np.linalg.det(Vt.T @ U.T))
            R_ab = Vt.T @ np.diag([1, 1, dd]) @ U.T              # ra ≈ R_ab rb
            e = cv2.Rodrigues(Rc[a] @ R_ab @ Rc[b].T)[0].ravel()
            if np.linalg.norm(e) > 3 * D2R:
                continue
            e_t += [ts[a], ts[b]]
            e_v += [-e / 2, e / 2]
        corr_deg = 0.0
        if len(e_t) >= 6:
            o = np.argsort(e_t)
            E_t = np.asarray(e_t)[o]
            E_v = np.asarray(e_v)[o]
            if len(E_v) >= 5:                                   # 이웃 3개 중앙값으로 튀는 값 누르기
                E_v = np.stack([np.median(E_v[max(0, i - 1):i + 2], axis=0) for i in range(len(E_v))])
            for k in range(len(Rc)):
                ek = np.array([np.interp(ts[k], E_t, E_v[:, c]) for c in range(3)])
                Rc[k] = _rodr(ek) @ Rc[k]
            corr_deg = float(np.degrees(np.percentile(np.linalg.norm(E_v, axis=1), 90)))
        ax = Rc[:, :, 2]
        pitch = np.degrees(np.arcsin(np.clip(ax[:, 2], -1, 1)))
        yaw = np.degrees(np.arctan2(ax[:, 0], ax[:, 1]))
        # ── 띠 프레임: 띠마다 yaw step° 칸에서 점수가 가장 좋은 것
        step = float(getattr(opts, "strip_step", 1.5) or 1.5)
        bands = {}
        for bn, m in (("up", up), ("down", dn)):
            idx = np.nonzero(m)[0]
            if len(idx) < 20:
                continue
            yu = np.degrees(np.unwrap(np.radians(yaw[idx])))
            if yu[-1] < yu[0]:
                yu = -yu                                       # 왼쪽으로 돈 바퀴
            cs = np.concatenate([[0.0], np.cumsum(score[idx])])
            best, j = None, 0
            for i in range(len(idx)):                           # 360° 를 덮는 가장 짧은 구간들 중 점수 합이 큰 것
                while j < len(idx) and yu[j] - yu[i] < 360.0:
                    j += 1
                if j >= len(idx):
                    break
                sc_ = cs[j] - cs[i]
                if best is None or sc_ > best[0]:
                    best = (sc_, i, j)
            if best is not None:
                i0, j0 = best[1], best[2]
            else:
                i0, j0 = 0, len(idx)                           # 한 바퀴가 안 됨: 있는 만큼
            win, yw = idx[i0:j0], yu[i0:j0] - yu[i0]
            cells = {}
            for k, y_ in zip(win, yw):
                c = int(y_ // step)
                if c not in cells or score[k] > score[cells[c]]:
                    cells[c] = int(k)
            sel = np.array(sorted(cells.values(), key=lambda kk: yaw[kk]))
            bands[bn] = {"frames": sel, "pitch": float(np.median(pitch[idx])), "span": float(yu[-1] - yu[0]), "window": [int(win[0]), int(win[-1])]}
        if not bands:
            _fail(ps, "영상에서 위·아래 바퀴를 찾지 못했습니다 (폰을 30° 위·아래로 기울여 돌아 주세요)")
        zsel = []
        if zen.any():
            cells = {}
            for k in np.nonzero(zen)[0]:
                c = int((yaw[k] + 180) // 30)
                if c not in cells or score[k] > score[cells[c]]:
                    cells[c] = int(k)
            zsel = sorted(cells.values())
        # ── 노출: 이웃 띠 프레임·위아래 짝 밝기 비로 log 이득 (자동 노출이 천천히 바뀌는 것을 편다)
        prog(3.8, f"{sid} 노출 맞추는 중")
        allk = sorted(set(int(k) for b in bands.values() for k in b["frames"]) | set(zsel))
        pos = {k: i for i, k in enumerate(allk)}
        rows, strip_res, strip_raw = [], [], []
        dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_FAST)
        dism = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
        use_morph = bool(getattr(opts, "strip_morph", True))
        gh, gw = grays[0].shape
        CW = max(24, int(round(gw * 0.15)))                       # 보관할 가운데 띠 반폭 (분석 px, ≈ ±10°)
        gcx = gw // 2
        pflow = {}
        gxx, gyy = np.meshgrid(np.arange(gw, dtype=np.float32), np.arange(gh, dtype=np.float32))
        for bn, b in bands.items():
            fs_ = b["frames"]
            for i in range(len(fs_)):
                a, c = int(fs_[i]), int(fs_[(i + 1) % len(fs_)])
                if a == c:
                    continue
                gbw, val = _warp_to(grays[a], grays[c], Rc[a], Rc[c], f_g)
                r = _logratio(grays[a], gbw, val)
                if r is not None:
                    rows.append((pos[a], pos[c], r, 1.0))
                F = None
                if use_morph:
                    F = dism.calc(grays[a], gbw, None)          # gbw(x + F) ≈ ga(x)
                    F[~val] = 0
                    F = cv2.medianBlur(F, 5)
                    F = cv2.GaussianBlur(F, (0, 0), 1.5)
                    np.clip(F, -48, 48, out=F)
                    pflow[(a, c)] = F[:, max(0, gcx - CW):gcx + CW].astype(np.float16)
                if i % 4 == 0:                                   # 띠 경계 어긋남 표본 (가운데): 맞추기 전 / 광류로 맞춘 뒤
                    x0, x1, y0, y1 = int(gw * 0.3), int(gw * 0.7), int(gh * 0.15), int(gh * 0.85)
                    vv = val[y0:y1, x0:x1]
                    if vv.mean() > 0.8:
                        fl = dis.calc(np.ascontiguousarray(grays[a][y0:y1, x0:x1]), np.ascontiguousarray(gbw[y0:y1, x0:x1]), None)
                        strip_raw.append(float(np.median(np.hypot(fl[..., 0], fl[..., 1])[vv])))
                        if F is not None:
                            gbf = cv2.remap(gbw, gxx + F[..., 0], gyy + F[..., 1], cv2.INTER_LINEAR)
                            fl2 = dis.calc(np.ascontiguousarray(grays[a][y0:y1, x0:x1]), np.ascontiguousarray(gbf[y0:y1, x0:x1]), None)
                            strip_res.append(float(np.median(np.hypot(fl2[..., 0], fl2[..., 1])[vv])))
                        else:
                            strip_res.append(strip_raw[-1])
        if "up" in bands and "down" in bands:
            dn_f = bands["down"]["frames"]
            for a in bands["up"]["frames"][::3]:
                a = int(a)
                d = np.abs((yaw[dn_f] - yaw[a] + 180) % 360 - 180)
                if d.min() > 3:
                    continue
                c = int(dn_f[int(np.argmin(d))])
                gbw, val = _warp_to(grays[a], grays[c], Rc[a], Rc[c], f_g)
                r = _logratio(grays[a], gbw, val)
                if r is not None:
                    rows.append((pos[a], pos[c], r, 2.0))
        if "up" in bands:
            uf = bands["up"]["frames"]
            for zk in zsel:
                d = np.abs((yaw[uf] - yaw[zk] + 180) % 360 - 180)
                c = int(uf[int(np.argmin(d))])
                gbw, val = _warp_to(grays[zk], grays[c], Rc[zk], Rc[c], f_g)
                r = _logratio(grays[zk], gbw, val)
                if r is not None:
                    rows.append((pos[zk], pos[c], r, 1.0))
        Ng = len(allk)
        A = np.eye(Ng) * 0.02
        bb = np.zeros(Ng)
        for i, j, r, wgt in rows:                               # g_i − g_j = r_ij  (I_i·e^gi = I_j·e^gj)
            A[i, i] += wgt
            A[j, j] += wgt
            A[i, j] -= wgt
            A[j, i] -= wgt
            bb[i] += wgt * r
            bb[j] -= wgt * r
        try:
            lg = np.clip(np.linalg.solve(A, bb), -0.7, 0.7)
        except np.linalg.LinAlgError:
            lg = np.zeros(Ng)
        lg -= float(np.median(lg))
        gain = {k: math.exp(lg[pos[k]]) for k in allk}
        del grays, cache
        # ── 그리기
        W = ps.pick_size(opts.size, f_full)
        H = W // 2
        vhalf = math.degrees(math.atan((h / 2.0) / f_full)) - 2.0
        vfc = float(getattr(opts, "video_floor_cut", 72.0) or 0.0)
        floor = -(vfc - 1) if vfc > 0 else -90.0
        lat = 90.0 - (np.arange(H) + 0.5) * 180.0 / H
        lon = (np.arange(W) + 0.5) * 360.0 / W - 180.0
        has_up, has_dn = "up" in bands, "down" in bands
        p_up = bands["up"]["pitch"] if has_up else None
        p_dn = bands["down"]["pitch"] if has_dn else None
        bw = 8.0
        mid = None
        if has_up and has_dn:
            mid = (p_up + p_dn) / 2.0
            ov = (p_dn + vhalf) - (p_up - vhalf)
            bw = max(2.0, min(8.0, ov / 2.0 - 2.0))
            wu = _smooth((lat - (mid - bw)) / (2 * bw))
        else:
            wu = np.ones(H) if has_up else np.zeros(H)
        z_lo = (p_up + vhalf - 10.0) if has_up else 60.0
        if zsel:
            Wz = 512
            zc = []
            for la_ in np.arange(40.0, 89.0, 1.0):
                dz = ps.eq_dirs(np.arange(Wz, dtype=np.float32), np.full(Wz, (90.0 - la_) / 180.0 * (Wz // 2), np.float32), Wz, Wz // 2)
                cov_ = np.zeros(Wz, bool)
                for zk in zsel:
                    _x, _y, okz = ps.project(dz, ps.Cam(Rc[zk], f_full, 0.0, w, h), margin=-0.04 * h)
                    cov_ |= okz
                zc.append((la_, float(cov_.mean())))
            good_ = [la_ for la_, c_ in zc if c_ >= 0.97]
            if good_:                                          # 그 위로 모두 덮이는 가장 낮은 위도
                lo_ok = 89.0
                for la_, c_ in reversed(zc):
                    if c_ < 0.97:
                        break
                    lo_ok = la_
                z_lo = float(np.clip(lo_ok + 1.0, 52.0, z_lo))
        # 천장 훑기 프레임은 덮는 곳마다 화소 단위로 (52° 위, 프레임 가장자리는 부드럽게). 천장에 가까운 형광등은
        # 띠마다 다른 자리에서 봐 비틀린 줄무늬가 되는데, 한 자리에서 찍은 천장 프레임은 곧게 보인다
        zcap = float(getattr(opts, "video_zenith_from", 52.0) or 52.0)
        zramp = _smooth((lat - zcap) / 8.0).astype(np.float32) if zsel else np.zeros(H, np.float32)
        zr0 = int(np.nonzero(zramp > 0)[0][-1]) + 1 if zramp.any() else 0       # 위에서부터 zr0 줄까지가 천장 띠
        Zcov = np.zeros((zr0, W), np.float32)

        def zen_weight(px_, py_, okz_, cosang_, rows_sl):
            ef = np.minimum(np.minimum(px_, w - 1 - px_), np.minimum(py_, h - 1 - py_)) / (0.07 * h)
            return (_smooth(ef) * okz_ * zramp[rows_sl][:, None] * np.clip(cosang_, 0, 1) ** 8).astype(np.float32)
        if zr0:
            dzz = ps.eq_dirs(np.arange(W, dtype=np.float32)[None, :], np.arange(zr0, dtype=np.float32)[:, None], W, H)
            for zk in zsel:
                zx_, zy_, zok_ = ps.project(dzz, ps.Cam(Rc[zk], f_full, 0.0, w, h))
                Zcov = np.maximum(Zcov, zen_weight(zx_, zy_, zok_, np.ones_like(zx_), slice(0, zr0)))
            del dzz, zx_, zy_, zok_
        wz = np.zeros(H, np.float32)
        band_w = {}
        if has_up:
            m = (lat >= p_up - vhalf) & (lat <= p_up + vhalf) & (lat >= floor)
            band_w["up"] = np.where(m, np.maximum(wu, 1e-3) * (1 - wz), 0.0).astype(np.float32)
        if has_dn:
            m = (lat >= max(floor, p_dn - vhalf)) & (lat <= p_dn + vhalf)
            band_w["down"] = np.where(m, np.maximum(1 - wu, 1e-3), 0.0).astype(np.float32)
        # 이음 띠 행: 두 바퀴를 따로 모은다 (본 누적에서는 뺀다)
        if has_up and has_dn:
            top_ = max(mid + bw + 1.0, min(p_dn + vhalf - 1.0, mid + bw + 1.0 + float(getattr(opts, "video_move_band", 18.0))))
            trow = np.nonzero((lat >= mid - bw - 1.0) & (lat <= top_) & (band_w["up"] > 0) & (band_w["down"] > 0))[0]
        else:
            trow = np.zeros(0, int)
        tv0, tv1 = (int(trow[0]), int(trow[-1]) + 1) if len(trow) else (0, 0)
        if tv1 > tv0:
            for bn in ("up", "down"):
                band_w[bn][tv0:tv1] = 0.0
        accT = {bn: np.zeros((tv1 - tv0, W, 3), np.float32) for bn in bands} if tv1 > tv0 else {}
        wT = {bn: np.zeros((tv1 - tv0, W), np.float32) for bn in bands} if tv1 > tv0 else {}
        colmap = {}
        for bn, b in bands.items():                             # 열마다 (앞 프레임, 뒤 프레임, 뒤 가중)
            fs_ = b["frames"]
            ys = yaw[fs_]
            ys_e = np.concatenate([ys - 360, ys, ys + 360])
            id_e = np.concatenate([fs_, fs_, fs_])
            j = np.clip(np.searchsorted(ys_e, lon), 1, len(ys_e) - 1)
            y0, y1 = ys_e[j - 1], ys_e[j]
            wl = np.clip((lon - y0) / np.maximum(y1 - y0, 1e-6), 0, 1)
            blend = float(getattr(opts, "strip_blend", 1.0) or 1.0)      # 두 프레임을 섞는 폭 (칸 간격 비율). 좁을수록 선명, 넓을수록 이음 부드러움
            w1 = _smooth((wl - 0.5) / max(0.05, blend) + 0.5) if blend < 0.999 else wl
            colmap[bn] = (id_e[j - 1], id_e[j], w1.astype(np.float32), wl.astype(np.float32))
        need = {}
        for bn in bands:
            k0, k1, _w1, _wl = colmap[bn]
            for k in np.unique(np.concatenate([k0, k1])):
                need.setdefault(int(k), []).append(bn)
        for zk in zsel:
            need.setdefault(int(zk), []).append("zen")
        acc = np.zeros((H, W, 3), np.float32)
        wsum = np.zeros((H, W), np.float32)
        s_g = gw / float(w)                                       # 원본 px → 분석 px
        Kf = _Kmat(f_full, w, h)
        Kfi = np.linalg.inv(Kf)
        prog(5, f"{sid} 띠 {len(need)}개 그리는 중 ({W}×{H})")
        t_r = time.time()
        cap = cv2.VideoCapture(path)
        idx, done, max_need = 0, 0, max(need)
        z_axes = {zk: Rc[zk][:, 2] for zk in zsel}
        clipped_avoided = 0
        while idx <= max_need:
            if not cap.grab():
                break
            if idx in need:
                ok_, img = cap.retrieve()
                if ok_:
                    img = _rot_img(img, rk)
                    g = gain.get(idx, 1.0)
                    cam = ps.Cam(Rc[idx], f_full, 0.0, w, h)
                    gray_full = None
                    jobs_ = []
                    for bn in need[idx]:
                        if bn == "zen":
                            rows_ = np.arange(zr0)
                            if len(rows_):
                                jobs_.append((bn, None, rows_, [(0, W)], None))
                            continue
                        k0, k1, w1, wl = colmap[bn]
                        rows_ = np.nonzero(band_w[bn] > 0)[0]
                        if tv1 > tv0:
                            rows_ = np.union1d(rows_, np.arange(tv0, tv1))
                        if not len(rows_):
                            continue
                        for role, sel_ in (("L", k0 == idx), ("R", k1 == idx)):
                            cols = np.nonzero(sel_ & ((1 - w1 if role == "L" else w1) > 0))[0]
                            if not len(cols):
                                continue
                            br = np.nonzero(np.diff(cols) > 1)[0]
                            starts = np.r_[cols[0], cols[br + 1]]
                            ends = np.r_[cols[br], cols[-1]] + 1
                            jobs_.append((bn, role, rows_, list(zip(starts.tolist(), ends.tolist())), (k0, k1, w1, wl)))
                    for bn, role, rows_, runs, cm in jobs_:
                        v0, v1 = int(rows_[0]), int(rows_[-1]) + 1
                        for (u0, u1) in runs:
                            us = np.arange(u0, u1, dtype=np.float32)
                            vs = np.arange(v0, v1, dtype=np.float32)
                            d = ps.eq_dirs(us[None, :], vs[:, None], W, H)
                            if role is None:
                                px, py, okp = ps.project(d, cam)
                                colw = None
                            else:
                                k0, k1, w1, wl = cm
                                colw = (1 - w1) if role == "L" else w1
                                m_ = wl[u0:u1][None, :].astype(np.float32)
                                if role == "L":                              # 이 프레임 = 앞(a). a 에서 x − m·F(x)
                                    pa_, pc_ = idx, int(k1[u0])
                                    px, py, okp = ps.project(d, cam)
                                    F = pflow.get((pa_, pc_))
                                    if F is not None:
                                        fx = cv2.remap(F[..., 0].astype(np.float32), (px * s_g - (gcx - CW)).astype(np.float32), (py * s_g).astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
                                        fy = cv2.remap(F[..., 1].astype(np.float32), (px * s_g - (gcx - CW)).astype(np.float32), (py * s_g).astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
                                        px = px - m_ * fx / s_g
                                        py = py - m_ * fy / s_g
                                else:                                        # 이 프레임 = 뒤(c). a 자리 x + (1−m)·F(x) 를 c 로 옮겨 뽑는다
                                    pa_, pc_ = int(k0[u0]), idx
                                    cam_a = ps.Cam(Rc[pa_], f_full, 0.0, w, h)
                                    qx, qy, okq = ps.project(d, cam_a)
                                    F = pflow.get((pa_, pc_))
                                    if F is not None:
                                        fx = cv2.remap(F[..., 0].astype(np.float32), (qx * s_g - (gcx - CW)).astype(np.float32), (qy * s_g).astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
                                        fy = cv2.remap(F[..., 1].astype(np.float32), (qx * s_g - (gcx - CW)).astype(np.float32), (qy * s_g).astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
                                        qx = qx + (1 - m_) * fx / s_g
                                        qy = qy + (1 - m_) * fy / s_g
                                    Hm_ = Kf @ Rc[idx].T @ Rc[pa_] @ Kfi
                                    X = Hm_[0, 0] * qx + Hm_[0, 1] * qy + Hm_[0, 2]
                                    Y = Hm_[1, 0] * qx + Hm_[1, 1] * qy + Hm_[1, 2]
                                    Z = Hm_[2, 0] * qx + Hm_[2, 1] * qy + Hm_[2, 2]
                                    Zs = np.where(Z > 1e-6, Z, 1e-6)
                                    px, py = X / Zs, Y / Zs
                                    okp = okq & (Z > 1e-6) & (px >= -0.5) & (px <= w - 0.5) & (py >= -0.5) & (py <= h - 0.5)
                            samp = cv2.remap(img, px.astype(np.float32), py.astype(np.float32), cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
                            if bn == "zen":
                                cosang = d @ z_axes[idx].astype(np.float32)
                                wgt = zen_weight(px, py, okp, cosang, slice(v0, v1))
                            else:
                                wgt = colw[u0:u1][None, :] * band_w[bn][v0:v1, None] * okp
                                if bn == "up" and v0 < zr0:                 # 천장 프레임이 덮는 만큼 띠를 덜 쓴다
                                    zz1 = min(v1, zr0)
                                    wgt = wgt.astype(np.float32)
                                    wgt[:zz1 - v0] *= (1 - Zcov[v0:zz1, u0:u1])
                                clip = samp.max(2) >= 250                 # 날아간 화소: 다른 바퀴가 덮으면 그쪽을 쓴다 (유사 HDR)
                                if has_up and has_dn and clip.any():
                                    wgt = np.where(clip, wgt * 1e-4, wgt)
                                    clipped_avoided += int(clip.sum())
                            wgt = wgt.astype(np.float32)
                            acc[v0:v1, u0:u1] += samp.astype(np.float32) * (wgt * g)[..., None]
                            wsum[v0:v1, u0:u1] += wgt
                            if bn != "zen" and tv1 > tv0 and v0 < tv1 and v1 > tv0:      # 이음 띠: 바퀴별로 따로 (띠 가중 없이)
                                a0, a1 = max(v0, tv0), min(v1, tv1)
                                wt = (colw[u0:u1][None, :] * okp[a0 - v0:a1 - v0]).astype(np.float32)
                                accT[bn][a0 - tv0:a1 - tv0, u0:u1] += samp[a0 - v0:a1 - v0].astype(np.float32) * (wt * g)[..., None]
                                wT[bn][a0 - tv0:a1 - tv0, u0:u1] += wt
                    done += 1
                    if done % 40 == 0:
                        prog(5 + 80 * done / max(1, len(need)), f"{sid} 띠 그리는 중 {done}/{len(need)}")
            idx += 1
        cap.release()
        t_render = time.time() - t_r
        covered = wsum > 1e-6
        eq = np.zeros((H, W, 3), np.uint8)
        eq[covered] = np.clip(acc[covered] / wsum[covered][:, None] + 0.5, 0, 255).astype(np.uint8)
        del acc
        # ── 이음 띠: 위 바퀴 ↔ 아래 바퀴 광류로 반씩 맞춰 섞는다 (손목 축 시차·남은 자세 오차)
        seam, seam_raw = [], []
        moving_px, n_moving, row_gain, n_clone = 0, 0, None, 0
        if tv1 > tv0:
            prog(88, f"{sid} 위·아래 바퀴 이음 맞추는 중")
            U_ = accT["up"] / np.maximum(wT["up"], 1e-6)[..., None]
            D_ = accT["down"] / np.maximum(wT["down"], 1e-6)[..., None]
            vu, vd = wT["up"] > 1e-3, wT["down"] > 1e-3
            hT = tv1 - tv0
            sc = 2 if W >= 4096 else 1
            gu = cv2.resize(cv2.cvtColor(np.clip(U_, 0, 255).astype(np.uint8), cv2.COLOR_BGR2GRAY), (W // sc, max(8, hT // sc)), interpolation=cv2.INTER_AREA)
            gd = cv2.resize(cv2.cvtColor(np.clip(D_, 0, 255).astype(np.uint8), cv2.COLOR_BGR2GRAY), (W // sc, max(8, hT // sc)), interpolation=cv2.INTER_AREA)
            dm = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
            F = dm.calc(gu, gd, None)                          # gd(x + F) ≈ gu(x)
            Fb = dm.calc(gd, gu, None)
            hh, ww = gu.shape
            gx, gy = np.meshgrid(np.arange(ww, dtype=np.float32), np.arange(hh, dtype=np.float32))
            cons = np.hypot(F[..., 0] + cv2.remap(Fb, gx + F[..., 0], gy + F[..., 1], cv2.INTER_LINEAR)[..., 0],
                            F[..., 1] + cv2.remap(Fb, gx + F[..., 0], gy + F[..., 1], cv2.INTER_LINEAR)[..., 1])
            corner = cv2.cornerMinEigenVal(gu, 7, 3) > ps.CORNER_MIN
            both_s = cv2.resize((vu & vd).astype(np.uint8), (ww, hh), interpolation=cv2.INTER_NEAREST) > 0
            lat_t0 = cv2.resize(lat[tv0:tv1].astype(np.float32)[:, None], (1, hh), interpolation=cv2.INTER_LINEAR)
            selm = both_s & corner & (cons < 1.5) & (np.abs(lat_t0 - mid) <= bw + 1.0)
            if selm.sum() > 30:
                seam_raw = (np.hypot(F[..., 0], F[..., 1])[selm] * sc * 360.0 / W).tolist()
            F = np.where(cons[..., None] < 3.0, F, 0).astype(np.float32)
            F = cv2.GaussianBlur(F, (0, 0), 2.0)
            np.clip(F, -40.0 / sc, 40.0 / sc, out=F)
            Ff = cv2.resize(F, (W, hT), interpolation=cv2.INTER_LINEAR) * sc
            wrow = wu[tv0:tv1].astype(np.float32)[:, None]      # 위 바퀴 가중
            # 움직인 물체(지나가는 사람): 광류로 맞춘 뒤에도 두 바퀴가 크게 다른 덩어리는 아래 바퀴로 통째로 —
            # 사람은 바닥에 서 있어 몸이 아래 바퀴에만 보이는 줄에 걸치므로, 아래 바퀴를 쓰면 '몸 전체' 아니면 '없음'이 된다
            # (위 바퀴 머리 + 아래 바퀴 빈 몸 = 떠 있는 머리, 실촬영 cfb5229d s02). 날아간 화소도 아래 바퀴가 멀쩡하면 아래로
            gdw = cv2.remap(gd, gx + F[..., 0], gy + F[..., 1], cv2.INTER_LINEAR)
            # 무늬(고주파) 차이로 찾는다 — 화이트보드·유리처럼 보는 각도에 따라 밝기만 다른 곳은 빼고, 사람 윤곽·옷 무늬는 잡는다
            gu_f, gd_f = gu.astype(np.float32), gdw.astype(np.float32)
            hp_u = gu_f - cv2.GaussianBlur(gu_f, (0, 0), 6.0)
            hp_d = gd_f - cv2.GaussianBlur(gd_f, (0, 0), 6.0)
            dtex = cv2.GaussianBlur(np.abs(hp_u - hp_d), (0, 0), 3.0)
            dlum = np.abs(cv2.GaussianBlur(gu_f, (0, 0), 2.0) - cv2.GaussianBlur(gd_f, (0, 0), 2.0))
            wr_s = cv2.resize(np.broadcast_to(wrow, (hT, 1)).astype(np.float32), (1, hh), interpolation=cv2.INTER_LINEAR)
            thr = float(getattr(opts, "video_move_diff", 28.0))
            dlow = np.abs(cv2.GaussianBlur(gu_f, (0, 0), 5.0) - cv2.GaussianBlur(gd_f, (0, 0), 5.0))     # 사람은 둘레와 밝기·색이 달라 흐려도 남는다
            Mv = ((dlow > thr) & (dlum > thr) & both_s & (wr_s > 0.02)).astype(np.uint8)
            Mv = cv2.morphologyEx(Mv, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
            Mv = cv2.morphologyEx(Mv, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
            n_, lab_, st_, _c = cv2.connectedComponentsWithStats(Mv, connectivity=8)
            min_area = max(60, int(0.6 * (W / 360.0 / sc) ** 2 * 4))          # 약 2°×2° 보다 작은 점은 무시
            keep_ = np.zeros(n_, bool)
            keep_[1:] = st_[1:, cv2.CC_STAT_AREA] >= min_area
            Mv = keep_[lab_].astype(np.uint8)
            cnts, _h = cv2.findContours(Mv, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)       # 덩어리 안 구멍 메우기 (머리카락처럼 무늬 없는 속)
            if cnts:
                cv2.drawContours(Mv, cnts, -1, 1, thickness=cv2.FILLED)
            Mv = cv2.dilate(Mv, np.ones((7, 7), np.uint8))
            moving_px = int(Mv.sum()) * sc * sc
            n_moving = int(keep_.sum())
            # 덩어리는 따로: 360° 끝에 걸친 것만 부드럽게 바꾸고, 나머지는 아래에서 포아송 붙이기(seamlessClone)
            n2_, lab2_, st2_, _c2 = cv2.connectedComponentsWithStats(Mv, connectivity=8)
            wrapc = np.zeros(n2_, bool)
            for ci in range(1, n2_):
                x_, w_ = st2_[ci, cv2.CC_STAT_LEFT], st2_[ci, cv2.CC_STAT_WIDTH]
                wrapc[ci] = x_ <= 2 or x_ + w_ >= ww - 2
            Mwrap = wrapc[lab2_].astype(np.float32)
            Mf = cv2.GaussianBlur(Mwrap, (0, 0), 2.0)
            Mf = np.clip(cv2.resize(Mf, (W, hT), interpolation=cv2.INTER_LINEAR) * 2.0, 0, 1)
            clipU = U_.max(2) >= 250
            clipD = D_.max(2) >= 250
            Mf = np.maximum(Mf, (clipU & ~clipD & vd).astype(np.float32))
            # 줄마다 두 바퀴 밝기 비 (비네팅: 같은 곳을 위 바퀴는 화면 아래쪽, 아래 바퀴는 위쪽에서 본다) → 위 바퀴가 주인인 줄에서 아래 바퀴를 맞춘다
            okm = both_s & (Mv == 0) & (gu > 20) & (gu < 235) & (gdw > 20) & (gdw < 235)
            rr_ = np.ones(hh, np.float32)
            for yy in range(hh):
                mm_ = okm[yy]
                if mm_.sum() > ww * 0.05:
                    rr_[yy] = float(np.median(gu_f[yy][mm_] / np.maximum(gd_f[yy][mm_], 1.0)))
            rr_ = np.clip(cv2.GaussianBlur(rr_.reshape(-1, 1), (0, 0), 4.0).ravel() if hh > 8 else rr_, 0.8, 1.25)
            rr_full = cv2.resize(rr_.reshape(-1, 1), (1, hT), interpolation=cv2.INTER_LINEAR).ravel()
            sD = (1 + (rr_full - 1) * wrow[:, 0]).astype(np.float32)
            D_ = D_ * sD[:, None, None]
            row_gain = [round(float(rr_.min()), 3), round(float(rr_.max()), 3)]
            ntop = max(2, int(round(1.0 / (180.0 / H))))           # 맨 위 1° 는 서서히 (아래 바퀴가 못 본 위쪽과 이어지게)
            Mf[:ntop] *= np.linspace(0, 1, ntop, dtype=np.float32)[:, None]
            X, Y = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(hT, dtype=np.float32))
            Uw = cv2.remap(U_.astype(np.float32), X - (1 - wrow) * Ff[..., 0], Y - (1 - wrow) * Ff[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
            Dw = cv2.remap(D_.astype(np.float32), X + wrow * Ff[..., 0], Y + wrow * Ff[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
            vuw = cv2.remap(vu.astype(np.float32), X - (1 - wrow) * Ff[..., 0], Y - (1 - wrow) * Ff[..., 1], cv2.INTER_NEAREST, borderMode=cv2.BORDER_WRAP) > 0.5
            vdw = cv2.remap(vd.astype(np.float32), X + wrow * Ff[..., 0], Y + wrow * Ff[..., 1], cv2.INTER_NEAREST, borderMode=cv2.BORDER_WRAP) > 0.5
            if getattr(opts, "debug", False):                 # 이음 띠 점검: 위 바퀴 / 아래 바퀴 / 바꾼 곳
                dd_ = os.path.join(out_dir, sid)
                os.makedirs(dd_, exist_ok=True)
                cv2.imwrite(os.path.join(dd_, "debug_band_up.jpg"), np.clip(U_, 0, 255).astype(np.uint8)[::2, ::2])
                cv2.imwrite(os.path.join(dd_, "debug_band_down.jpg"), np.clip(D_, 0, 255).astype(np.uint8)[::2, ::2])
                cv2.imwrite(os.path.join(dd_, "debug_band_move.png"), (Mv * 255).astype(np.uint8))
            # 바꾼 곳은 아래 바퀴를 광류 없이 그대로 (움직인 물체·반복 무늬에서 광류는 엉터리라 물결이 생긴다)
            mfc = np.clip(Mf, 0, 1)[..., None]
            Dw = Dw * (1 - mfc) + D_.astype(np.float32) * mfc
            vdw = vdw | ((Mf > 0.5) & vd)
            wrb = np.broadcast_to(wrow, vuw.shape)
            wa = np.where(vuw, wrb * (1 - Mf), 0.0)
            wb = np.where(vdw, (1 - wrb) + wrb * Mf, 0.0)
            ws_ = wa + wb
            out = (Uw * wa[..., None] + Dw * wb[..., None]) / np.maximum(ws_, 1e-6)[..., None]
            cov_t = ws_ > 1e-6
            blk = eq[tv0:tv1]
            blk[cov_t] = np.clip(out[cov_t] + 0.5, 0, 255).astype(np.uint8)
            eq[tv0:tv1] = blk
            covered[tv0:tv1] |= cov_t
            del out
            # 움직인 물체 덩어리: 아래 바퀴를 포아송 붙이기 — 가장자리 밝기가 둘레와 꼭 맞아 화이트보드·유리의 밝기 차이가 '조각'으로 안 보인다
            D8 = np.clip(D_ + 0.5, 0, 255).astype(np.uint8)
            pad = 12
            n_clone = 0
            for ci in range(1, n2_):
                if wrapc[ci]:
                    continue
                x_, y_, w_, h_ = (int(v_) for v_ in st2_[ci, :4])
                mk = cv2.resize((lab2_[y_:y_ + h_, x_:x_ + w_] == ci).astype(np.uint8), (w_ * sc, h_ * sc), interpolation=cv2.INTER_NEAREST)
                Y0, X0 = y_ * sc, x_ * sc
                Y1, X1 = min(hT, Y0 + mk.shape[0]), min(W, X0 + mk.shape[1])
                mk = mk[:Y1 - Y0, :X1 - X0] & vd[Y0:Y1, X0:X1].astype(np.uint8)
                mk[: max(0, ntop - Y0)] = 0                      # 맨 위 1° 는 붙이지 않음 (위쪽과 이어짐)
                if mk.sum() < 64:
                    continue
                R0, R1, C0, C1 = tv0 + Y0 - pad, tv0 + Y1 + pad, X0 - pad, X1 + pad
                if R0 < 0 or R1 > H or C0 < 0 or C1 > W:
                    continue
                dst = eq[R0:R1, C0:C1].copy()
                src = dst.copy()
                src[pad:pad + (Y1 - Y0), pad:pad + (X1 - X0)][mk > 0] = D8[Y0:Y1, X0:X1][mk > 0]
                mcrop = np.zeros(dst.shape[:2], np.uint8)
                mcrop[pad:pad + (Y1 - Y0), pad:pad + (X1 - X0)] = mk * 255
                bx, by, bw_, bh_ = cv2.boundingRect(mcrop)
                try:
                    eq[R0:R1, C0:C1] = cv2.seamlessClone(src, dst, mcrop, (bx + bw_ // 2, by + bh_ // 2), cv2.NORMAL_CLONE)
                    n_clone += 1
                except cv2.error:
                    pass
            del D8
            # 맞춘 뒤 어긋남 (가운데 줄 기준: 반씩 옮긴 두 바퀴 사이)
            Um = cv2.remap(U_.astype(np.float32), X - 0.5 * Ff[..., 0], Y - 0.5 * Ff[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
            Dm = cv2.remap(D_.astype(np.float32), X + 0.5 * Ff[..., 0], Y + 0.5 * Ff[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
            g1 = cv2.resize(cv2.cvtColor(np.clip(Um, 0, 255).astype(np.uint8), cv2.COLOR_BGR2GRAY), (ww, hh), interpolation=cv2.INTER_AREA)
            g2 = cv2.resize(cv2.cvtColor(np.clip(Dm, 0, 255).astype(np.uint8), cv2.COLOR_BGR2GRAY), (ww, hh), interpolation=cv2.INTER_AREA)
            R1 = dm.calc(g1, g2, None)
            R2 = dm.calc(g2, g1, None)
            cons2 = np.hypot(R1[..., 0] + cv2.remap(R2, gx + R1[..., 0], gy + R1[..., 1], cv2.INTER_LINEAR)[..., 0],
                             R1[..., 1] + cv2.remap(R2, gx + R1[..., 0], gy + R1[..., 1], cv2.INTER_LINEAR)[..., 1])
            lat_t = cv2.resize(lat[tv0:tv1].astype(np.float32)[:, None], (1, hh), interpolation=cv2.INTER_LINEAR)
            inb = np.abs(lat_t - mid) <= bw + 1.0
            sel2 = both_s & inb & (cv2.cornerMinEigenVal(g1, 7, 3) > ps.CORNER_MIN) & (cons2 < 1.5) & (Mv[:hh, :ww] == 0)
            if sel2.sum() > 30:
                seam = (np.hypot(R1[..., 0], R1[..., 1])[sel2] * sc * 360.0 / W).tolist()
            del accT, wT, U_, D_, Uw, Dw, X, Y, Ff, Mf
        # ── 품질: 위·아래 바퀴 이음(맞춘 뒤) + 띠 경계 잔차
        strip_deg = [r / f_g / D2R for r in strip_res]
        # 등급은 더 나쁜 쪽으로: 위·아래 바퀴 이음(맞춘 뒤)과 이웃 띠 사이 잔차(시차·자세 오차 — 섞이면 살짝 흐려짐)
        parts = [x for x in (seam, strip_deg) if x]
        if parts:
            s_med = max(float(np.median(x)) for x in parts)
            s_p90 = max(float(np.percentile(x, 90)) for x in parts)
        else:
            s_med = s_p90 = None
        vlim = int(H * (0.5 + 60 / 180))
        coverage = float(covered[:vlim].mean())
        amt = float(getattr(opts, "video_sharpen", 0.0) or 0.0)
        if amt > 0:                                              # 영상 프레임은 흔들림·압축으로 사진보다 무르다 — 가볍게 또렷하게 (언샤프 마스크)
            sig = max(0.8, W / 8192.0 * 1.6)
            bl = cv2.GaussianBlur(eq, (0, 0), sig)
            eq = cv2.addWeighted(eq, 1 + amt, bl, -amt, 0)
            del bl
        prog(90, f"{sid} 바닥·천장 메우는 중")
        eq, nadir_r = ps.fill_pole(eq, covered, "nadir", opts.nadir, opts.nadir_radius, cut_deg=(90 - vfc) if vfc > 0 else 0)
        if not covered[: max(1, H // 18)].all():
            eq, _ = ps.fill_pole(eq, covered, "zenith", "blur", 0)
        eq = ps.fill_small_holes(eq, covered)
        ps.write_spot_outputs(eq, out_dir, sid, W, opts)
        grade = "poor"
        if s_med is not None:
            if s_med <= 0.25 and s_p90 <= 1.0 and coverage >= 0.98:
                grade = "good"
            elif s_med <= 1.0 and s_p90 <= 5.0 and coverage >= 0.93:
                grade = "fair"
        if sync_score < 0.5:
            grade = "poor"
        nfr = len(need)
        drift_total = float(np.degrees(np.linalg.norm(c_drift)) * float(np.abs(ts).max()))
        quality = {
            "grade": grade, "mode": "video", "shots": int(len(fr)), "used": int(nfr), "linked": int(nfr), "coverage": round(coverage, 4),
            "seam_px_med": None if s_med is None else round(s_med * W / 360.0, 2), "seam_px_p90": None if s_p90 is None else round(s_p90 * W / 360.0, 2),
            "match_px_med": None if fit_res is None else round(fit_res / pc_scale, 2), "match_px_p90": None,
            "focal_px": [round(f_full, 1)], "sensor_fix_deg_med": round(drift_total / 2, 2), "sensor_fix_deg_max": round(drift_total, 2),
            "nadir_deg": round(nadir_r, 1),
            "seam_deg_med": None if s_med is None else round(s_med, 2), "seam_deg_p90": None if s_p90 is None else round(s_p90, 2),
            "rowseam_deg_med": round(float(np.median(seam)), 3) if seam else None, "rowseam_deg_p90": round(float(np.percentile(seam, 90)), 3) if seam else None,
            "rowseam_raw_deg_med": round(float(np.median(seam_raw)), 3) if seam_raw else None, "rowseam_raw_deg_p90": round(float(np.percentile(seam_raw, 90)), 3) if seam_raw else None,
            "strip_raw_deg_med": round(float(np.median(strip_raw)) / f_g / D2R, 3) if strip_raw else None,
            "strip_raw_deg_p90": round(float(np.percentile(strip_raw, 90)) / f_g / D2R, 3) if strip_raw else None,
            "strip_deg_med": round(float(np.median(strip_deg)), 3) if strip_deg else None,
            "strip_deg_p90": round(float(np.percentile(strip_deg, 90)), 3) if strip_deg else None,
            "guards": ([] if sync_score >= 0.5 else ["sync_weak"]),
        }
        up_set = set(bands["up"]["frames"].tolist()) if has_up else set()
        images = []
        for k in allk:
            y_, p_, r_ = ps.R_to_ypr(Rc[k])
            images.append({"file": f"{name}#{k}", "q": [round(float(a), 6) for a in ps.R_to_quat(Rc[k])], "yaw": round(y_, 2), "pitch": round(p_, 2), "roll": round(r_, 2),
                           "band": "zen" if k in zsel else ("up" if k in up_set else "down"), "gain": round(gain.get(k, 1.0), 3)})
        video_info = {
            "render": "strip", "file": name, "turns_used": turns_used, "morph": use_morph, "moving_regions": n_moving, "moving_px": moving_px, "moving_cloned": n_clone, "band_row_gain": row_gain, "zenith_from_deg": zcap if zsel else None, "zenith_cover": round(float(Zcov.mean()), 3) if zr0 else None,
            "band_windows": {bn: b.get("window") for bn, b in bands.items()}, "band_span_deg": {bn: round(b.get("span", 0), 1) for bn, b in bands.items()}, "frames": len(fr), "decoded_size": [int(w0), int(h0)], "size": [int(w), int(h)], "rotate_deg": rk * 90,
            "fps": round(1000.0 / max(1e-3, float(np.median(np.diff(t)))), 2), "dur_s": round((t[-1] - t[0]) / 1000.0, 2),
            "sync_ms": round(delta, 1), "sync_score": round(float(sync_score), 3), "strip_step_deg": step,
            "strips": {bn: int(len(b["frames"])) for bn, b in bands.items()}, "zenith_frames": len(zsel),
            "band_pitch": {bn: round(b["pitch"], 1) for bn, b in bands.items()}, "blend_band_deg": round(bw, 1),
            "drift_dps": [round(float(np.degrees(a)), 4) for a in c_drift], "focal_scale": round(s_f, 4), "local_fix_deg_p90": round(corr_deg, 3), "fit_pairs": len(pairs), "fit_matches": fit_n,
            "fit_px_med": None if fit_res is None else round(fit_res, 2), "pairs_info": [list(p) for p in pinfo[:40]],
            "gain_range": [round(float(np.exp(lg.min())), 3), round(float(np.exp(lg.max())), 3)] if Ng else None,
            "rate_med_dps": round(float(np.median(rate[inside])), 1) if inside.any() else None,
            "rate_p90_dps": round(float(np.percentile(rate[inside], 90)), 1) if inside.any() else None,
            "usable_frac": round(float(ok.mean()), 3), "f_ratio": f_ratio, "clipped_avoided_px": clipped_avoided,
            "sec_analyse": round(t_an, 1), "sec_render": round(t_render, 1),
        }
        ps.log(f"[{sid}] 영상 띠 {nfr}개 (위 {video_info['strips'].get('up', 0)}·아래 {video_info['strips'].get('down', 0)}·천장 {len(zsel)}), "
               f"시각 {video_info['sync_ms']} ms, 흐름 {np.degrees(np.linalg.norm(c_drift)):.3f}°/s, 초점 ×{s_f:.3f}, 짝 {len(pairs)}")
        report = {"id": sid, "width": W, "height": H, "seconds": round(time.time() - t_start, 1), "quality": quality,
                  "pairs": len(pairs), "pair_candidates": len(pairs), "matches": fit_n,
                  "groups": [{"w": int(w), "h": int(h), "src": "video", "f_px": round(f_full, 2), "f0_px": round(f_ratio * long0, 2), "k1": 0.0}],
                  "images": images, "skipped": [], "seams": [], "video": video_info}
        return W, H, quality, report
    finally:
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)
