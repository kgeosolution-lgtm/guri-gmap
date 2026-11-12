#!/usr/bin/env python
r"""
kgeoScan 360° 실사 파노라마 스티처 — 계약: docs/pano_contract.md

  python worker/pano_stitch.py <pano_spots.zip | 폴더> --out <출력 폴더>
        [--size 8192] [--nadir logo|blur|none] [--nadir-radius 15] [--spots s01,s02] [--title 제목] [--debug]

입력: capture_pano.html 이 만든 pano_spots.zip (spots.json + s01/0001.jpg …) 또는 같은 구조의 폴더.
출력: <out>/tour.json, <out>/stitch_report.json, <out>/<spot>/pano.jpg·preview.jpg·thumb.jpg·tiles/<r>_<c>.jpg

지점마다:
  1) 촬영 때 기록한 자세(q, 카메라→세계)를 초기값으로
  2) SIFT 특징 — 초기 자세로 짝 사진과 상대 위치를 예측해 그 근처에서만 고른다(흰 벽·반복 무늬에 강함)
  3) 묶음 조정(numpy LM): 사진별 회전 + 크기 묶음별 초점·k1. 센서 자세는 약한 사전값(사진 짝이 없는 흰 벽도 제자리)
  4) 노출(사진별 채널 이득) → 이음선(가운데 가중 + 다른 사진과 다른 곳 피하기) → 다중대역 합성(경계 0°/360° 이어짐)
  5) 천저(바로 아래) 구멍: 흐림 메우기 + 로고 원, 나머지 작은 구멍: 흐림 메우기
  6) 품질: 특징점 오차(px), 이음선 양쪽 광류 어긋남(px, 출력 해상도), 덮인 비율

의존: numpy, opencv(SIFT, detail_MultiBandBlender, DIS 광류). scipy 없음. GPU 없음.
진행: stdout 에 'PROGRESS <0-100> <문구>'. 종료 코드 0 성공(일부 지점 실패 포함), 2 입력 오류, 1 그 밖의 오류.
"""
import argparse
import io
import json
import math
import os
import sys
import time
import zipfile

import numpy as np
import cv2

cv2.ocl.setUseOpenCL(False)          # detail_MultiBandBlender 의 OpenCL 경로가 이 빌드에서 깨진다(결과 0)
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

VERSION = "pano_stitch/0.1"
PI = math.pi
D2R = PI / 180.0
MIN_SHOTS = 6
TILE_COLS, TILE_ROWS = 4, 2
CORNER_MIN = 2e-4              # cornerMinEigenVal(7, 3) 문턱 — 이음선 품질은 모서리성 있는 곳에서만 잰다
SIZES = (2048, 3072, 4096, 6144, 8192, 12288, 16384)


class InputError(Exception):
    pass


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def progress(p, msg):
    print(f"PROGRESS {int(max(0, min(100, p)))} {msg}", flush=True)


# ───────────────────────── 회전 ─────────────────────────
def Rz(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], float)


def Rx(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], float)


def Ry(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], float)


C0 = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], float)   # 세계 +y 를 보는 수평 카메라 (열: x→동, y→아래, z→앞)


def ypr_to_R(yaw, pitch, roll):
    """계약 1.3: R_wc = Rz(-yaw)·Rx(pitch)·C0·Rz(roll) (도)"""
    return Rz(-yaw * D2R) @ Rx(pitch * D2R) @ C0 @ Rz(roll * D2R)


def R_to_ypr(R):
    f = R[:, 2]
    yaw = math.degrees(math.atan2(f[0], f[1]))
    pitch = math.degrees(math.asin(max(-1.0, min(1.0, f[2]))))
    M = C0.T @ Rx(-pitch * D2R) @ Rz(yaw * D2R) @ R
    roll = math.degrees(math.atan2(M[1, 0], M[0, 0]))
    return yaw, pitch, roll


def quat_to_R(q):
    w, x, y, z = [float(a) for a in q]
    n = math.sqrt(w * w + x * x + y * y + z * z) or 1.0
    w, x, y, z = w / n, x / n, y / n, z / n
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
                     [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
                     [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])


def R_to_quat(R):
    t = R[0, 0] + R[1, 1] + R[2, 2]
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        q = [0.25 * s, (R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s]
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = math.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2
        q = [(R[2, 1] - R[1, 2]) / s, 0.25 * s, (R[0, 1] + R[1, 0]) / s, (R[0, 2] + R[2, 0]) / s]
    elif R[1, 1] > R[2, 2]:
        s = math.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2
        q = [(R[0, 2] - R[2, 0]) / s, (R[0, 1] + R[1, 0]) / s, 0.25 * s, (R[1, 2] + R[2, 1]) / s]
    else:
        s = math.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2
        q = [(R[1, 0] - R[0, 1]) / s, (R[0, 2] + R[2, 0]) / s, (R[1, 2] + R[2, 1]) / s, 0.25 * s]
    if q[0] < 0:
        q = [-a for a in q]
    return q


def rodrigues(w):
    return cv2.Rodrigues(np.asarray(w, np.float64).reshape(3, 1))[0]


def rotvec(R):
    return cv2.Rodrigues(np.asarray(R, np.float64))[0].ravel()


def rot_angle_deg(Ra, Rb):
    return float(np.linalg.norm(rotvec(Ra @ Rb.T)) / D2R)


# ───────────────────────── 등장방형 ─────────────────────────
def eq_dirs(us, vs, W, H):
    """픽셀 (u,v) → 세계 방향. u 가운데 열 = yaw 0 (+y), 오른쪽 = 시계 방향(+x), 위 = +z"""
    lon = (np.asarray(us, np.float32) + 0.5) * np.float32(2 * PI / W) - np.float32(PI)
    lat = np.float32(PI / 2) - (np.asarray(vs, np.float32) + 0.5) * np.float32(PI / H)
    lon, lat = np.broadcast_arrays(lon, lat)
    cl = np.cos(lat)
    return np.stack([np.sin(lon) * cl, np.cos(lon) * cl, np.sin(lat)], -1)


def dir_to_eq(d, W, H):
    lon = np.arctan2(d[..., 0], d[..., 1])
    lat = np.arcsin(np.clip(d[..., 2], -1, 1))
    return (lon + PI) * (W / (2 * PI)) - 0.5, (PI / 2 - lat) * (H / PI) - 0.5


# ───────────────────────── 카메라 ─────────────────────────
class Cam:
    __slots__ = ("R", "f", "k1", "w", "h", "cx", "cy")

    def __init__(self, R, f, k1, w, h):
        self.R, self.f, self.k1, self.w, self.h = np.array(R, float), float(f), float(k1), int(w), int(h)
        self.cx, self.cy = (w - 1) / 2.0, (h - 1) / 2.0

    def scaled(self, s):
        c = Cam(self.R, self.f * s, self.k1, max(1, round(self.w * s)), max(1, round(self.h * s)))
        return c


def undistort_norm(x, y, k1):
    if np.all(np.abs(k1) < 1e-9):
        return x, y
    xu, yu = x.copy(), y.copy()
    for _ in range(6):
        d = 1 + k1 * (xu * xu + yu * yu)
        xu, yu = x / d, y / d
    return xu, yu


def cam_rays(pts, f, k1, cx, cy):
    """픽셀 → 카메라 좌표 단위 광선 (OpenCV 축)"""
    x = (pts[..., 0] - cx) / f
    y = (pts[..., 1] - cy) / f
    x, y = undistort_norm(x, y, k1)
    v = np.stack([x, y, np.ones_like(x)], -1)
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def project(dirs, cam, margin=0.0):
    """세계 방향 (…,3) → 픽셀 (px, py), 앞쪽이고 사진 안이면 ok"""
    c = dirs @ cam.R.astype(dirs.dtype)                    # R^T d
    z = c[..., 2]
    zs = np.where(z > 1e-4, z, 1e-4)
    x, y = c[..., 0] / zs, c[..., 1] / zs
    if abs(cam.k1) > 1e-9:
        d = 1 + cam.k1 * (x * x + y * y)
        x, y = x * d, y * d
    px, py = cam.f * x + cam.cx, cam.f * y + cam.cy
    ok = (z > 1e-3) & (px >= -0.5 - margin) & (px <= cam.w - 0.5 + margin) & (py >= -0.5 - margin) & (py <= cam.h - 0.5 + margin)
    return px, py, ok


def fov_diag(cam):
    return 2 * math.atan(math.hypot(cam.w, cam.h) / 2 / cam.f)


# ───────────────────────── 입력 ─────────────────────────
class Source:
    def __init__(self, path):
        self.path = path
        if os.path.isdir(path):
            self.zf = None
            p = os.path.join(path, "spots.json")
            if not os.path.isfile(p):
                raise InputError("폴더에 spots.json 이 없습니다")
            with open(p, "r", encoding="utf-8") as fh:
                self.meta = json.load(fh)
        else:
            try:
                self.zf = zipfile.ZipFile(path)
            except Exception as e:
                raise InputError(f"zip 을 열 수 없습니다: {e}")
            try:
                self.meta = json.loads(self.zf.read("spots.json").decode("utf-8"))
            except KeyError:
                raise InputError("zip 안에 spots.json 이 없습니다")
            except Exception as e:
                raise InputError(f"spots.json 을 읽을 수 없습니다: {e}")
        if not isinstance(self.meta, dict) or not isinstance(self.meta.get("spots"), list) or not self.meta["spots"]:
            raise InputError("spots.json 에 지점(spots)이 없습니다")

    def read(self, name):
        name = name.replace("\\", "/").lstrip("/")
        if ".." in name.split("/"):
            raise InputError(f"잘못된 파일 이름: {name}")
        if self.zf is not None:
            return self.zf.read(name)
        with open(os.path.join(self.path, *name.split("/")), "rb") as fh:
            return fh.read()


def decode_image(data):
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)   # EXIF 회전 적용
    if img is None:
        raise ValueError("사진을 읽을 수 없음")
    return img


def shot_R(s):
    if isinstance(s.get("q"), (list, tuple)) and len(s["q"]) == 4:
        return quat_to_R(s["q"])
    if all(isinstance(s.get(k), (int, float)) for k in ("yaw", "pitch")):
        return ypr_to_R(s["yaw"], s["pitch"], s.get("roll") or 0.0)
    raise ValueError("자세(q 또는 yaw/pitch)가 없음")


# ───────────────────────── 특징 ─────────────────────────
class Feats:
    __slots__ = ("pts", "desc")


def detect(img, work_long, sift):
    h, w = img.shape[:2]
    s = min(1.0, work_long / max(w, h))
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if s < 1:
        g = cv2.resize(g, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA)
    kp, d = sift.detectAndCompute(g, None)
    F = Feats()
    if d is None or not kp:
        F.pts, F.desc = np.zeros((0, 2), np.float64), np.zeros((0, 128), np.float32)
        return F
    d = d.astype(np.float32)
    d /= (np.abs(d).sum(1, keepdims=True) + 1e-7)                 # RootSIFT
    F.desc = np.sqrt(d).astype(np.float32)
    F.pts = (np.array([k.pt for k in kp], np.float64) + 0.5) / s - 0.5
    return F


def guided_match(fa, fb, ca, cb, tol_deg, ratio=0.85, single_max=0.55):
    """ca 의 특징이 cb 어디에 올지 현재 자세로 예측하고 그 반경 안에서만 짝을 고른다. 반환 (pa, pb) 정상 짝"""
    if len(fa.pts) < 8 or len(fb.pts) < 8:
        return None
    va = cam_rays(fa.pts, ca.f, ca.k1, ca.cx, ca.cy) @ ca.R.T
    tol_px = cb.f * math.tan(tol_deg * D2R)
    px, py, ok = project(va, cb, margin=tol_px)
    qa = np.nonzero(ok)[0]
    if len(qa) < 8:
        return None
    pred = np.stack([px[qa], py[qa]], 1)
    # 거리 행렬 (RootSIFT 는 단위 벡터 → d² = 2 − 2·내적)
    dot = fa.desc[qa] @ fb.desc.T
    d2 = np.maximum(0, 2 - 2 * dot)
    sp = ((pred[:, None, 0] - fb.pts[None, :, 0]) ** 2 + (pred[:, None, 1] - fb.pts[None, :, 1]) ** 2) <= tol_px * tol_px
    d2 = np.where(sp, d2, 9.0)
    if d2.shape[1] < 2:
        return None
    part = np.partition(d2, 1, axis=1)
    best, second = part[:, 0], part[:, 1]
    jb = np.argmin(d2, axis=1)
    single = second >= 9.0
    good = (best < 9.0) & ((~single & (best < (ratio ** 2) * second)) | (single & (best < single_max ** 2)))
    # 서로 가장 가까운 짝만 (b 쪽 중복 제거)
    colbest = np.argmin(d2, axis=0)
    good &= colbest[jb] == np.arange(len(qa))
    ia = qa[good]
    ib = jb[good]
    if len(ia) < 10:
        return None
    pa, pb = fa.pts[ia], fb.pts[ib]
    thr = 0.004 * max(cb.w, cb.h) + 1.5
    H, inl = cv2.findHomography(pa.astype(np.float32), pb.astype(np.float32), cv2.RANSAC, thr, maxIters=3000, confidence=0.999)
    if H is None or inl is None:
        return None
    inl = inl.ravel().astype(bool)
    if inl.sum() < 10:
        return None
    return pa[inl], pb[inl]


# ───────────────────────── 묶음 조정 ─────────────────────────
def skew(v):
    z = np.zeros(v.shape[0])
    return np.stack([np.stack([z, -v[:, 2], v[:, 1]], -1),
                     np.stack([v[:, 2], z, -v[:, 0]], -1),
                     np.stack([-v[:, 1], v[:, 0], z], -1)], 1)


def bundle_adjust(cams, R0, gid, M, F, sig_rot_deg=5.0, sig_f=0.15, sig_k=0.1, f0=None, iters=40, delta=2.0, fix_k1=False, fix_f=()):
    """cams 의 R·f·k1 을 고친다 (제자리). M: dict(ii, jj, pa, pb).
    잔차 = 양방향 재투영 오차(원본 px): a 의 광선을 b 사진에 투영한 자리 − b 의 점 (그 반대도).
    광선 차이 잔차는 초점→∞ 로 모든 광선을 한 점에 모으는 퇴화해가 있어 쓰지 않는다.
    반환: 짝마다 출력 등장방형 px 오차 (두 광선 사이 각 × F)"""
    N = len(cams)
    G = int(gid.max()) + 1
    ii, jj, pa, pb = M["ii"], M["jj"], M["pa"], M["pb"]
    nm = len(ii)
    P = 3 * N + 2 * G
    cx = np.array([c.cx for c in cams])
    cy = np.array([c.cy for c in cams])
    sig_p = sig_rot_deg * D2R
    gi, gj = gid[ii], gid[jj]
    first = [int(np.nonzero(gid == g)[0][0]) for g in range(G)]
    if f0 is None:
        f0 = np.array([cams[k].f for k in first])
    fixed_f = set(int(g) for g in fix_f)

    def unpack():
        return np.stack([c.R for c in cams]), np.array([cams[k].f for k in first]), np.array([cams[k].k1 for k in first])

    def evaluate(Rs, fs, ks):
        ua = cam_rays(pa, fs[gi], ks[gi], cx[ii], cy[ii])
        ub = cam_rays(pb, fs[gj], ks[gj], cx[jj], cy[jj])
        va = np.einsum("mij,mj->mi", Rs[ii], ua)
        vb = np.einsum("mij,mj->mi", Rs[jj], ub)
        wa = np.einsum("mji,mj->mi", Rs[jj], va)            # a 광선을 b 카메라 좌표로
        wb = np.einsum("mji,mj->mi", Rs[ii], vb)
        za = np.maximum(wa[:, 2], 0.05)
        zb = np.maximum(wb[:, 2], 0.05)
        r1 = fs[gj][:, None] * (wa[:, :2] / za[:, None] - ub[:, :2] / ub[:, 2:3])
        r2 = fs[gi][:, None] * (wb[:, :2] / zb[:, None] - ua[:, :2] / ua[:, 2:3])
        return np.concatenate([r1, r2], 1), va, vb, wa, wb, za, zb

    def priors(Rs, fs, ks):
        rp = np.stack([rotvec(Rs[k] @ R0[k].T) for k in range(N)]) / sig_p
        return rp, np.log(fs / f0) / sig_f, ks / sig_k

    def robust(r):
        e = np.concatenate([np.linalg.norm(r[:, :2], axis=1), np.linalg.norm(r[:, 2:], axis=1)])
        return np.where(e <= delta, 0.5 * e * e, delta * (e - 0.5 * delta)).sum()

    def cost_of(r, rp, rf, rk):
        return robust(r) + 0.5 * ((rp ** 2).sum() + (rf ** 2).sum() + (rk ** 2).sum())

    def Pi(w, z):
        J = np.zeros((len(w), 2, 3))
        J[:, 0, 0] = 1 / z
        J[:, 1, 1] = 1 / z
        J[:, 0, 2] = -w[:, 0] / z ** 2
        J[:, 1, 2] = -w[:, 1] / z ** 2
        return J

    Rs, fs, ks = unpack()
    r, va, vb, wa, wb, za, zb = evaluate(Rs, fs, ks)
    rp, rf, rk = priors(Rs, fs, ks)
    cost = cost_of(r, rp, rf, rk)
    lam = 1e-3
    rows = np.arange(nm)
    for it in range(iters):
        e1 = np.linalg.norm(r[:, :2], axis=1)
        e2 = np.linalg.norm(r[:, 2:], axis=1)
        w1 = np.sqrt(np.where(e1 <= delta, 1.0, delta / np.maximum(e1, 1e-12)))
        w2 = np.sqrt(np.where(e2 <= delta, 1.0, delta / np.maximum(e2, 1e-12)))
        sw = np.concatenate([np.repeat(w1[:, None], 2, 1), np.repeat(w2[:, None], 2, 1)], 1)     # (m,4)
        J = np.zeros((4 * nm + 3 * N + 2 * G, P))
        # 회전 (왼쪽 곱 섭동): d wa/dδi = −Rjᵀ[va]×, d wa/dδj = +Rjᵀ[va]×
        A1 = np.einsum("mki,mkl->mil", Rs[jj], skew(va))
        A2 = np.einsum("mki,mkl->mil", Rs[ii], skew(vb))
        J1 = fs[gj][:, None, None] * np.einsum("mab,mbc->mac", Pi(wa, za), A1)      # (m,2,3) — δj 에 대해 +, δi 에 대해 −
        J2 = fs[gi][:, None, None] * np.einsum("mab,mbc->mac", Pi(wb, zb), A2)      # δi 에 대해 +, δj 에 대해 −
        for comp in range(2):
            ra = 4 * rows + comp
            rb = 4 * rows + 2 + comp
            for k in range(3):
                J[ra, 3 * ii + k] += -J1[:, comp, k] * sw[:, comp]
                J[ra, 3 * jj + k] += J1[:, comp, k] * sw[:, comp]
                J[rb, 3 * jj + k] += -J2[:, comp, k] * sw[:, 2 + comp]
                J[rb, 3 * ii + k] += J2[:, comp, k] * sw[:, 2 + comp]
        eps = 1e-5
        for g in range(G):
            for which in (0, 1):
                if (which == 0 and g in fixed_f) or (which == 1 and fix_k1):
                    continue
                fs2, ks2 = fs.copy(), ks.copy()
                if which == 0:
                    fs2[g] *= math.exp(eps)
                else:
                    ks2[g] += eps
                r2_ = evaluate(Rs, fs2, ks2)[0]
                J[:4 * nm, 3 * N + 2 * g + which] = ((r2_ - r) / eps * sw).ravel()
        base = 4 * nm
        for k in range(N):
            J[base + 3 * k:base + 3 * k + 3, 3 * k:3 * k + 3] = np.eye(3) / sig_p
        base += 3 * N
        for g in range(G):
            J[base + g, 3 * N + 2 * g] = 1.0 / sig_f
            J[base + G + g, 3 * N + 2 * g + 1] = 1.0 / sig_k
        rv = np.concatenate([(r * sw).ravel(), rp.ravel(), rf, rk])
        Hm = J.T @ J
        gv = J.T @ rv
        fixed = [3 * N + 2 * g + 1 for g in range(G)] if fix_k1 else []
        fixed += [3 * N + 2 * g for g in fixed_f]
        for c in fixed:
            Hm[c, :] = 0
            Hm[:, c] = 0
            Hm[c, c] = 1
            gv[c] = 0
        improved, rel = False, 0.0
        for _ in range(8):
            A = Hm + lam * np.diag(np.diag(Hm) + 1e-9)
            try:
                dx = -np.linalg.solve(A, gv)
            except np.linalg.LinAlgError:
                lam *= 10
                continue
            Rn = np.stack([rodrigues(dx[3 * k:3 * k + 3]) @ Rs[k] for k in range(N)])
            fn = fs * np.exp(np.clip(dx[3 * N::2], -0.2, 0.2))
            kn = ks + (0 if fix_k1 else dx[3 * N + 1::2])
            for g in fixed_f:
                fn[g] = fs[g]
            out = evaluate(Rn, fn, kn)
            rp2, rf2, rk2 = priors(Rn, fn, kn)
            c2 = cost_of(out[0], rp2, rf2, rk2)
            if c2 < cost:
                rel = (cost - c2) / max(cost, 1e-12)
                Rs, fs, ks, cost = Rn, fn, kn, c2
                r, va, vb, wa, wb, za, zb = out
                rp, rf, rk = rp2, rf2, rk2
                lam = max(lam / 3, 1e-7)
                improved = True
                break
            lam *= 5
        if not improved or rel < 1e-7:
            break
    for k, c in enumerate(cams):
        c.R = Rs[k]
        c.f = float(fs[gid[k]])
        c.k1 = float(ks[gid[k]])
    return np.arccos(np.clip((va * vb).sum(1), -1, 1)) * F


# ───────────────────────── 투영 영역 ─────────────────────────
def image_roi(cam, W, H, margin, wrap_margin):
    """등장방형에서 이 사진이 덮는 직사각형 (u0,u1 은 0..W 밖으로 펼친 값, 극을 품으면 전체 폭)"""
    w, h = cam.w, cam.h
    t = np.linspace(0, 1, 64)
    pts = np.concatenate([np.stack([t * (w - 1), np.zeros_like(t)], 1), np.stack([np.full_like(t, w - 1), t * (h - 1)], 1),
                          np.stack([t * (w - 1), np.full_like(t, h - 1)], 1), np.stack([np.zeros_like(t), t * (h - 1)], 1)])
    d = cam_rays(pts, cam.f, cam.k1, cam.cx, cam.cy) @ cam.R.T
    u, v = dir_to_eq(d, W, H)
    _, _, zen = project(np.array([[0, 0, 1.0]]), cam)
    _, _, nad = project(np.array([[0, 0, -1.0]]), cam)
    zen, nad = bool(zen[0]), bool(nad[0])
    uc, _ = dir_to_eq(cam.R[:, 2], W, H)
    du = ((u - uc + W / 2) % W) - W / 2
    full = zen or nad or (du.max() - du.min()) > 0.8 * W
    if full:
        u0, u1 = -wrap_margin, W + wrap_margin
    else:
        u0 = int(math.floor(uc + du.min())) - margin
        u1 = int(math.ceil(uc + du.max())) + margin + 1
    v0 = 0 if zen else max(0, int(math.floor(v.min())) - margin)
    v1 = H if nad else min(H, int(math.ceil(v.max())) + margin + 1)
    return u0, u1, v0, v1, full


def warp_roi(img, cam, W, H, roi, want_img=True, interp=cv2.INTER_LINEAR):
    u0, u1, v0, v1 = roi[:4]
    us = np.arange(u0, u1, dtype=np.float32)
    vs = np.arange(v0, v1, dtype=np.float32)
    d = eq_dirs(us[None, :], vs[:, None], W, H)
    px, py, ok = project(d, cam)
    xn = (px - cam.cx) / (cam.w / 2.0)
    yn = (py - cam.cy) / (cam.h / 2.0)
    wgt = np.clip(1 - np.abs(xn), 0, 1) * np.clip(1 - np.abs(yn), 0, 1)
    wgt = np.where(ok, wgt, 0).astype(np.float32)
    out = None
    if want_img:
        out = cv2.remap(img, px.astype(np.float32), py.astype(np.float32), interp, borderMode=cv2.BORDER_REPLICATE)
    return out, ok, wgt


# ───────────────────────── 노출 ─────────────────────────
def gain_compensation(imgs, cams, rois_fn, Wg, Hg, sig_n=10.0, sig_g=0.1):
    """사진별 채널 이득 (OpenCV GainCompensator 식, 채널마다). 저해상도 등장방형 겹침 평균으로"""
    N = len(imgs)
    canv, vals = [], []
    for k in range(N):
        cs = cams[k]
        r = rois_fn(cs, Wg, Hg)
        small = cv2.resize(imgs[k], (max(8, cs.w), max(8, cs.h)), interpolation=cv2.INTER_AREA)
        wimg, ok, _ = warp_roi(small, cs, Wg, Hg, r)
        cols = np.arange(r[0], r[1]) % Wg
        cimg = np.zeros((Hg, Wg, 3), np.uint8)
        cval = np.zeros((Hg, Wg), bool)
        ok = ok & (wimg.max(-1) < 250) & (wimg.max(-1) > 4)
        cimg[r[2]:r[3], cols] = wimg
        cval[r[2]:r[3], cols] = ok
        canv.append(cimg)
        vals.append(cval)
    gains = np.ones((N, 3))
    Nij = np.zeros((N, N))
    Iij = np.zeros((N, N, 3))
    for i in range(N):
        for j in range(i + 1, N):
            both = vals[i] & vals[j]
            n = int(both.sum())
            if n < 50:
                continue
            Nij[i, j] = Nij[j, i] = n
            Iij[i, j] = canv[i][both].reshape(-1, 3).mean(0)
            Iij[j, i] = canv[j][both].reshape(-1, 3).mean(0)
    a, b = 1 / sig_n ** 2, 1 / sig_g ** 2
    for ch in range(3):
        A = np.zeros((N, N))
        bb = np.zeros(N)
        for i in range(N):
            A[i, i] += 1e-6
            for j in range(N):
                if i == j or Nij[i, j] == 0:
                    continue
                A[i, i] += Nij[i, j] * (Iij[i, j, ch] ** 2 * a + b)
                A[i, j] -= Nij[i, j] * a * Iij[i, j, ch] * Iij[j, i, ch]
                bb[i] += b * Nij[i, j]
        lone = np.nonzero(Nij.sum(1) == 0)[0]
        for i in lone:
            A[i, i] = 1
            bb[i] = 1
        try:
            gains[:, ch] = np.clip(np.linalg.solve(A, bb), 0.5, 2.0)
        except np.linalg.LinAlgError:
            pass
    return gains


def apply_gain(img, g):
    return np.clip(img.astype(np.float32) * g[None, None, :].astype(np.float32), 0, 255).astype(np.uint8)


# ───────────────────────── 구멍 메우기 ─────────────────────────
def pole_view_R(which):
    return np.diag([1.0, -1.0, -1.0]) if which == "nadir" else np.eye(3)


def fill_pole(eq, covered, which, mode, radius_deg, S=1536, fov_deg=110.0):
    """극 둘레를 직선 투영으로 펴서 구멍을 흐림 메우기(+천저 로고)한 뒤 등장방형으로 되돌린다"""
    H, W = eq.shape[:2]
    f = (S / 2) / math.tan(fov_deg / 2 * D2R)
    cam = Cam(pole_view_R(which), f, 0, S, S)
    g = np.arange(S, dtype=np.float32)
    rays = cam_rays(np.stack(np.meshgrid(g, g), -1).astype(np.float64), f, 0, cam.cx, cam.cy) @ cam.R.T
    mu, mv = dir_to_eq(rays.astype(np.float32), W, H)
    view = cv2.remap(eq, mu.astype(np.float32), mv.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
    hole = cv2.remap((~covered).astype(np.uint8) * 255, mu.astype(np.float32), mv.astype(np.float32), cv2.INTER_NEAREST, borderMode=cv2.BORDER_WRAP) > 127
    rr = np.hypot(g[None, :] - cam.cx, g[:, None] - cam.cy)
    ang = np.degrees(np.arctan(rr / f))
    # 극 둘레(35° 안)에 이어진 구멍만으로 반지름을 잰다 (먼 곳의 1 px 점은 fill_small_holes 가 메운다)
    hole_r = 0.0
    hc = cv2.morphologyEx(hole.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    if hc.any():
        n, lab, st, _ = cv2.connectedComponentsWithStats(hc, connectivity=8)
        cen = ang < 35
        for i in range(1, n):
            m = lab == i
            if (m & cen).any():
                hole_r = max(hole_r, float(ang[m].max()))
    hole_r = min(hole_r, 40.0)
    if not hole.any() and mode != "logo":
        return eq, 0.0
    # 흐림 메우기 (1/4 해상도 inpaint → 흐림)
    q = 4
    sv = cv2.resize(view, (S // q, S // q), interpolation=cv2.INTER_AREA)
    sh = cv2.resize(hole.astype(np.uint8) * 255, (S // q, S // q), interpolation=cv2.INTER_NEAREST)
    sh = cv2.dilate(sh, np.ones((3, 3), np.uint8))
    filled = cv2.inpaint(sv, sh, 5, cv2.INPAINT_TELEA) if sh.any() else sv
    filled = cv2.GaussianBlur(filled, (0, 0), 6)
    filled = cv2.resize(filled, (S, S), interpolation=cv2.INTER_CUBIC)
    alpha = cv2.GaussianBlur(cv2.dilate(hole.astype(np.uint8) * 255, np.ones((9, 9), np.uint8)).astype(np.float32) / 255, (0, 0), 6)
    patch = view.astype(np.float32) * (1 - alpha[..., None]) + filled.astype(np.float32) * alpha[..., None]
    logo_r = 0.0
    if mode == "logo" and which == "nadir":
        logo_r = max(radius_deg, hole_r + 1.5)
        rp = f * math.tan(logo_r * D2R)
        disc = np.clip((rp - rr) / 2.0 + 0.5, 0, 1).astype(np.float32)        # 경계 부드럽게
        logo = np.zeros((S, S, 3), np.float32)
        logo[:] = (23, 17, 13)                                               # #0d1117
        ring = np.clip(1 - np.abs(rr - rp * 0.93) / (rp * 0.025), 0, 1)
        logo += ring[..., None] * (np.array([248, 189, 56], np.float32) - logo) * 0.85
        dot = np.clip((rp * 0.13 - np.hypot(g[None, :] - cam.cx, g[:, None] - (cam.cy - rp * 0.28))) / 2 + 0.5, 0, 1)
        logo += dot[..., None] * (np.array([248, 189, 56], np.float32) - logo)
        lg = logo.astype(np.uint8)
        txt, fs_, th = "kgeoScan", rp / 150.0, max(1, int(rp / 70))
        (tw, tht), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_DUPLEX, fs_, th)
        cv2.putText(lg, txt, (int(cam.cx - tw / 2), int(cam.cy + tht * 0.9)), cv2.FONT_HERSHEY_DUPLEX, fs_, (255, 246, 240), th, cv2.LINE_AA)
        sub = "360 TOUR"
        fs2 = fs_ * 0.45
        (tw2, th2), _ = cv2.getTextSize(sub, cv2.FONT_HERSHEY_SIMPLEX, fs2, max(1, th // 2))
        cv2.putText(lg, sub, (int(cam.cx - tw2 / 2), int(cam.cy + tht * 0.9 + th2 * 2.6)), cv2.FONT_HERSHEY_SIMPLEX, fs2, (160, 140, 120), max(1, th // 2), cv2.LINE_AA)
        patch = patch * (1 - disc[..., None]) + lg.astype(np.float32) * disc[..., None]
        alpha = np.maximum(alpha, disc)
    # 등장방형으로 되돌리기 (보기 범위 안의 행만)
    lat_lim = 90 - fov_deg / 2 + 2
    if which == "nadir":
        v0, v1 = int(H * (0.5 + lat_lim / 180)), H
    else:
        v0, v1 = 0, int(math.ceil(H * (0.5 - lat_lim / 180)))
    patch = patch.astype(np.float32)
    us = np.arange(W, dtype=np.float32)[None, :]
    for c0 in range(v0, v1, 256):                 # 행 묶음마다 (8192 폭에서 메모리 절약)
        c1 = min(v1, c0 + 256)
        d = eq_dirs(us, np.arange(c0, c1, dtype=np.float32)[:, None], W, H)
        px, py, ok = project(d, cam)
        back = cv2.remap(patch, px.astype(np.float32), py.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        ab = cv2.remap(alpha, px.astype(np.float32), py.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT) * ok
        sub_eq = eq[c0:c1].astype(np.float32)
        eq[c0:c1] = np.clip(sub_eq * (1 - ab[..., None]) + back * ab[..., None], 0, 255).astype(np.uint8)
        covered[c0:c1] |= ab > 0.5
    return eq, logo_r if logo_r else hole_r


def fill_small_holes(eq, covered):
    if covered.all():
        return eq
    H, W = eq.shape[:2]
    q = 8
    sv = cv2.resize(eq, (W // q, H // q), interpolation=cv2.INTER_AREA)
    sh = cv2.resize((~covered).astype(np.uint8) * 255, (W // q, H // q), interpolation=cv2.INTER_AREA)
    sh = (sh > 0).astype(np.uint8) * 255
    sh = cv2.dilate(sh, np.ones((3, 3), np.uint8))
    filled = cv2.inpaint(sv, sh, 4, cv2.INPAINT_TELEA)
    filled = cv2.GaussianBlur(filled, (0, 0), 2)
    filled = cv2.resize(filled, (W, H), interpolation=cv2.INTER_CUBIC)
    alpha = cv2.GaussianBlur((~covered).astype(np.float32), (0, 0), 3)
    alpha = np.maximum(alpha, (~covered).astype(np.float32))
    return np.clip(eq * (1 - alpha[..., None]) + filled * alpha[..., None], 0, 255).astype(np.uint8)


# ───────────────────────── 이음선 품질 ─────────────────────────
def seam_metrics(label, store, W_out, Wm, Hm, band=6):
    """label: Hm×Wm 사진 번호. store[k] = (u0, v0, gray(h×w), valid(h×w)) 중간 해상도 등장방형 조각.
    서로 이웃한 두 사진의 이음선 띠에서 DIS 광류(앞뒤 일치 검사)로 어긋남을 잰다 → 출력 px"""
    dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    a = label
    bnd_h = (a != np.roll(a, -1, 1)) & (a >= 0) & (np.roll(a, -1, 1) >= 0)
    bnd_v = np.zeros_like(bnd_h)
    bnd_v[:-1] = (a[:-1] != a[1:]) & (a[:-1] >= 0) & (a[1:] >= 0)
    pairs = {}
    ys, xs = np.nonzero(bnd_h)
    for y, x in zip(ys, xs):
        k = (int(min(a[y, x], a[y, (x + 1) % Wm])), int(max(a[y, x], a[y, (x + 1) % Wm])))
        pairs.setdefault(k, []).append((y, x))
    ys, xs = np.nonzero(bnd_v)
    for y, x in zip(ys, xs):
        k = (int(min(a[y, x], a[y + 1, x])), int(max(a[y, x], a[y + 1, x])))
        pairs.setdefault(k, []).append((y, x))
    scale = W_out / Wm
    allv, per = [], []

    def crop(k, vv0, vv1, uu0, uu1):
        u0, v0, g, ok = store[k]
        h, w = g.shape
        out = np.zeros((vv1 - vv0, uu1 - uu0), np.float32)
        val = np.zeros((vv1 - vv0, uu1 - uu0), bool)
        for sh in (-Wm, 0, Wm):
            a0, a1 = max(uu0, u0 + sh), min(uu1, u0 + sh + w)
            b0, b1 = max(vv0, v0), min(vv1, v0 + h)
            if a1 <= a0 or b1 <= b0:
                continue
            out[b0 - vv0:b1 - vv0, a0 - uu0:a1 - uu0] = g[b0 - v0:b1 - v0, a0 - u0 - sh:a1 - u0 - sh]
            val[b0 - vv0:b1 - vv0, a0 - uu0:a1 - uu0] |= ok[b0 - v0:b1 - v0, a0 - u0 - sh:a1 - u0 - sh]
        return out, val

    for (i, j), pts in pairs.items():
        if len(pts) < 20 or i not in store or j not in store:
            continue
        pts = np.array(pts)
        yy, xx = pts[:, 0], pts[:, 1]
        # 0/360 경계를 넘으면 펼친다
        xc = xx[0]
        xu = xc + ((xx - xc + Wm // 2) % Wm) - Wm // 2
        pad = 24
        vv0, vv1 = max(0, yy.min() - pad), min(Hm, yy.max() + pad + 1)
        uu0, uu1 = int(xu.min() - pad), int(xu.max() + pad + 1)
        if (vv1 - vv0) * (uu1 - uu0) > 6e6:
            continue
        gi, oi = crop(i, vv0, vv1, uu0, uu1)
        gj, oj = crop(j, vv0, vv1, uu0, uu1)
        both = oi & oj
        if both.sum() < 200:
            continue
        g8i = np.clip(gi, 0, 255).astype(np.uint8)
        g8j = np.clip(gj, 0, 255).astype(np.uint8)
        fl = dis.calc(g8i, g8j, None)
        fb = dis.calc(g8j, g8i, None)
        hh, ww = g8i.shape
        gx, gy = np.meshgrid(np.arange(ww, dtype=np.float32), np.arange(hh, dtype=np.float32))
        back = cv2.remap(fb, gx + fl[..., 0], gy + fl[..., 1], cv2.INTER_LINEAR)
        cons = np.hypot(fl[..., 0] + back[..., 0], fl[..., 1] + back[..., 1])
        corner = cv2.cornerMinEigenVal(g8i, 7, 3) > CORNER_MIN      # 직선 경계는 경계 방향으로 미끄러지므로 2 방향 무늬만
        bmask = np.zeros((hh, ww), np.uint8)
        bmask[yy - vv0, xu - uu0] = 255
        bmask = cv2.dilate(bmask, np.ones((2 * band + 1, 2 * band + 1), np.uint8)) > 0
        er = cv2.erode(both.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
        sel = bmask & er & corner & (cons < 1.0)
        if sel.sum() < 30:
            continue
        mag = np.hypot(fl[..., 0], fl[..., 1])[sel] * scale
        allv.append(mag)
        per.append({"a": i, "b": j, "n": int(sel.sum()), "med": round(float(np.median(mag)), 2), "p90": round(float(np.percentile(mag, 90)), 2)})
    if not allv:
        return None, None, per
    v = np.concatenate(allv)
    return float(np.median(v)), float(np.percentile(v, 90)), per


# ───────────────────────── 지점 하나 ─────────────────────────
def pick_size(req, f_med):
    native = 2 * PI * f_med
    cand = [s for s in SIZES if s >= native * 0.9]
    s = cand[0] if cand else SIZES[-1]
    return int(min(req, max(2048, s)))


def stitch_spot(src, spot, out_dir, opts, prog=lambda p, m: None):
    t0 = time.time()
    sid = spot.get("id") or "s01"
    shots = [s for s in spot.get("shots") or [] if isinstance(s, dict) and s.get("file")]
    if len(shots) < MIN_SHOTS:
        raise InputError(f"사진이 {MIN_SHOTS}장보다 적습니다 ({len(shots)}장)")
    imgs, cams, R0, keys, used_shots, skipped = [], [], [], [], [], []
    for s in shots:
        try:
            img = decode_image(src.read(s["file"]))
            R = shot_R(s)
        except Exception as e:
            skipped.append({"file": s.get("file"), "error": str(e)})
            continue
        h, w = img.shape[:2]
        key = (w, h, s.get("src") or "video")
        if key not in keys:
            keys.append(key)
        imgs.append(img)
        R0.append(R)
        used_shots.append(s)
        cams.append((w, h, keys.index(key)))
    if len(imgs) < MIN_SHOTS:
        raise InputError(f"읽을 수 있는 사진이 {MIN_SHOTS}장보다 적습니다 ({len(imgs)}장)")
    gid = np.array([c[2] for c in cams])
    cam_meta = spot.get("cam") or {}
    f_hint = cam_meta.get("f_px")
    f_ratio = cam_meta.get("f_ratio")             # 촬영 페이지가 렌즈별로 준다 (초광각 0.37, 기본 0.72)
    if not (isinstance(f_ratio, (int, float)) and 0.2 < f_ratio < 1.5):
        f_ratio = 0.37 if cam_meta.get("lens") == "ultra" else None
    camobjs = []
    for (w, h, g), R in zip(cams, R0):
        if f_ratio:
            f0 = float(f_ratio) * max(w, h)
        elif isinstance(f_hint, (int, float)) and f_hint > 100:
            f0 = float(f_hint)
        else:
            f0 = opts.f0_ratio * max(w, h)
        camobjs.append(Cam(R, f0, 0.0, w, h))
    cams = camobjs
    R0 = np.stack(R0)
    N = len(cams)
    f0g = np.array([cams[np.nonzero(gid == g)[0][0]].f for g in range(int(gid.max()) + 1)])
    prog(5, f"{sid} 특징점 찾는 중 ({N}장)")
    sift = cv2.SIFT_create(nfeatures=opts.features, contrastThreshold=0.02, edgeThreshold=12)
    feats = [detect(im, opts.work_long, sift) for im in imgs]
    F = opts.size / (2 * PI)
    # 짝 후보: 광축 사이 각이 대각 시야 평균의 0.9 배 안
    axes = np.stack([c.R[:, 2] for c in cams])
    pairs = []
    for i in range(N):
        for j in range(i + 1, N):
            ang = math.acos(max(-1, min(1, float(axes[i] @ axes[j]))))
            if ang < 0.45 * (fov_diag(cams[i]) + fov_diag(cams[j])):
                pairs.append((i, j))
    rounds = [(opts.tol1, 0.85), (opts.tol2, 0.9)]
    M = None
    fix_f = set()
    n_reset = 0
    pair_stats = {}
    for rno, (tol, ratio) in enumerate(rounds):
        prog(10 + rno * 25, f"{sid} 사진 짝 맞추는 중 ({rno + 1}/2)")
        II, JJ, PA, PB = [], [], [], []
        pair_stats = {}
        for (i, j) in pairs:
            r = guided_match(feats[i], feats[j], cams[i], cams[j], tol, ratio)
            if r is None:
                continue
            pa, pb = r
            if len(pa) > opts.max_per_pair:
                sel = np.random.default_rng(i * 1000 + j).choice(len(pa), opts.max_per_pair, replace=False)
                pa, pb = pa[sel], pb[sel]
            II.append(np.full(len(pa), i))
            JJ.append(np.full(len(pa), j))
            PA.append(pa)
            PB.append(pb)
            pair_stats[(i, j)] = len(pa)
        if not II:
            M = None
            break
        M = {"ii": np.concatenate(II), "jj": np.concatenate(JJ), "pa": np.concatenate(PA), "pb": np.concatenate(PB)}
        prog(20 + rno * 25, f"{sid} 자세 맞추는 중 ({rno + 1}/2) — 짝 {len(pair_stats)}개")
        few = len(pair_stats) < N
        fix_k1 = few or opts.no_k1 or bool(fix_f)

        def ba(M, iters):
            return bundle_adjust(cams, R0, gid, M, F, sig_rot_deg=opts.sig_rot, f0=f0g, fix_k1=fix_k1, fix_f=tuple(sorted(fix_f)), iters=iters,
                                 sig_k=0.2 if (f_ratio and f_ratio < 0.5) else 0.1)
        e = ba(M, 40)
        # 이상치 빼고 한 번 더
        keep = e < max(6.0, 4 * float(np.median(e)))
        if keep.sum() < len(e):
            M = {k: v[keep] for k, v in M.items()}
            e = ba(M, 25)
        # 안전장치: 초점이 초기값에서 너무 멀거나(몸을 축으로 돈 시차 등), 센서 자세에서 크게 벗어난 사진 → 되돌리고 다시
        redo = False
        for g in range(len(f0g)):
            fr = cams[np.nonzero(gid == g)[0][0]].f / f0g[g]
            k1g = cams[np.nonzero(gid == g)[0][0]].k1
            k1_lim = 0.25 if (f_ratio and f_ratio < 0.5) else 0.06      # 초광각은 남은 왜곡이 클 수 있다
            if (not (opts.f_lo <= fr <= opts.f_hi) or abs(k1g) > k1_lim) and g not in fix_f:
                log(f"[{sid}] 초점 {fr:.3f}배·k1 {k1g:.3f} → 초기값으로 고정")
                fix_f.add(g)
                redo = True
        bad = [k for k in range(N) if rot_angle_deg(cams[k].R, R0[k]) > opts.max_fix]
        n_reset += len(bad)
        if bad:
            log(f"[{sid}] 센서 자세에서 {opts.max_fix}° 넘게 벗어난 사진 {len(bad)}장 → 센서 자세로 되돌림")
            badset = set(bad)
            keep = np.array([(a not in badset) and (b not in badset) for a, b in zip(M["ii"], M["jj"])])
            M = {k: v[keep] for k, v in M.items()}
            redo = True
        if redo:
            for k, c in enumerate(cams):
                c.R = R0[k].copy()                 # 센서 자세에서 깨끗이 다시 시작
                if gid[k] in fix_f:
                    c.f = float(f0g[gid[k]])
                    c.k1 = 0.0
            fix_k1 = True
            if len(M["ii"]) >= 10:
                e = ba(M, 40)
            else:
                M = None
                break
    match_err = e if M is not None else np.zeros(0)
    linked = np.zeros(N, bool)
    if M is not None:
        linked[M["ii"]] = True
        linked[M["jj"]] = True
    # 출력 크기 (원본 밀도보다 크게 늘리지 않음)
    f_med = float(np.median([c.f for c in cams]))
    W = pick_size(opts.size, f_med)
    H = W // 2
    Fo = W / (2 * PI)
    scale_err = W / opts.size
    # 원본이 출력보다 훨씬 촘촘하면 미리 줄인다 (앨리어싱 방지)
    for k in range(N):
        s = Fo * 1.15 / cams[k].f
        if s < 0.85:
            nw, nh = max(8, round(cams[k].w * s)), max(8, round(cams[k].h * s))
            imgs[k] = cv2.resize(imgs[k], (nw, nh), interpolation=cv2.INTER_AREA)
            c = cams[k]
            cams[k] = Cam(c.R, c.f * nw / c.w, c.k1, nw, nh)
    prog(55, f"{sid} 노출 맞추는 중")

    def roi_at(c, Wx, Hx, margin=2):
        return image_roi(c, Wx, Hx, margin, wrap_margin=0)

    Wg = 1024
    gains = gain_compensation(imgs, [c.scaled(Wg / W) for c in cams], lambda c, a, b: roi_at(c, a, b), Wg, Wg // 2)
    # 이음선 (2048 폭): 가운데 가중 × 다른 사진과 다르면 감점
    prog(62, f"{sid} 이음선 정하는 중")
    Ws = min(2048, W)
    Hs = Ws // 2
    sstore = []
    sum_g = np.zeros((Hs, Ws), np.float32)
    cnt = np.zeros((Hs, Ws), np.float32)
    for k in range(N):
        cs = cams[k].scaled(Ws / W)
        r = roi_at(cs, Ws, Hs)
        if r[4]:
            r = (0, Ws, r[2], r[3], True)
        small = cv2.resize(imgs[k], (cs.w, cs.h), interpolation=cv2.INTER_AREA)
        wimg, ok, wgt = warp_roi(small, cs, Ws, Hs, r)
        g = cv2.cvtColor(apply_gain(wimg, gains[k]), cv2.COLOR_BGR2GRAY).astype(np.float32)
        cols = np.arange(r[0], r[1]) % Ws
        sstore.append((r, cols, g, ok, wgt))
        sum_g[r[2]:r[3], cols] += np.where(ok, g, 0)
        cnt[r[2]:r[3], cols] += ok
    mean_g = sum_g / np.maximum(cnt, 1)
    best = np.full((Hs, Ws), -1.0, np.float32)
    label_s = np.full((Hs, Ws), -1, np.int16)
    for k, (r, cols, g, ok, wgt) in enumerate(sstore):
        sub_mean = mean_g[r[2]:r[3], cols]
        sub_cnt = cnt[r[2]:r[3], cols]
        pen = np.where(sub_cnt >= 3, np.exp(-np.abs(cv2.GaussianBlur(g - sub_mean, (0, 0), 2)) / 25.0), 1.0)
        wv = np.where(ok, wgt * pen + 1e-4, -1)
        cur = best[r[2]:r[3], cols]
        better = wv > cur
        best[r[2]:r[3], cols] = np.where(better, wv, cur)
        lab = label_s[r[2]:r[3], cols]
        label_s[r[2]:r[3], cols] = np.where(better, k, lab)
    del sstore, sum_g, cnt, mean_g, best
    # 전체 해상도 합성
    prog(70, f"{sid} 합성 중 ({W}×{H})")
    Mw = 384
    blender = cv2.detail_MultiBandBlender(0, opts.bands, cv2.CV_16S)
    blender.prepare((0, 0, W + 2 * Mw, H))
    Wm = W // 2
    Hm = Wm // 2
    mstore = {}
    for k in range(N):
        r = image_roi(cams[k], W, H, 2, wrap_margin=Mw)
        u0, u1, v0, v1, full = r
        wimg, ok, _ = warp_roi(imgs[k], cams[k], W, H, r, interp=cv2.INTER_CUBIC)
        wimg = apply_gain(wimg, gains[k])
        us = np.arange(u0, u1)
        vs = np.arange(v0, v1)
        lab = label_s[(vs * Hs // H)[:, None], ((us % W) * Ws // W)[None, :]]
        # 이음선 지도는 Ws 해상도라 경계 화소가 이 사진 밖일 수 있다 → 조금 넓혀 이웃 사진도 그 화소를 맡게 한다
        dil = 2 * (W // Ws) + 1
        mask = cv2.dilate((lab == k).astype(np.uint8), np.ones((dil, dil), np.uint8))
        mask = ((mask > 0) & ok).astype(np.uint8) * 255
        if mask.any():
            for sh in (-W, 0, W):
                a = u0 + sh + Mw
                b = u1 + sh + Mw
                lo, hi = max(a, 0), min(b, W + 2 * Mw)
                if hi - lo <= 0:
                    continue
                m = mask[:, lo - a:hi - a]
                if not m.any():
                    continue
                blender.feed(np.ascontiguousarray(wimg[:, lo - a:hi - a]).astype(np.int16), np.ascontiguousarray(m), (int(lo), int(v0)))
        # 품질 측정용 절반 해상도 조각 (출력 0..W 범위만)
        if full:
            a0 = Mw
            sub_img, sub_ok, su0 = wimg[:, a0:a0 + W], ok[:, a0:a0 + W], 0
        else:
            sub_img, sub_ok, su0 = wimg, ok, u0
        hh, ww = sub_img.shape[:2]
        g = cv2.cvtColor(cv2.resize(sub_img, (max(1, ww // 2), max(1, hh // 2)), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
        okh = cv2.resize(sub_ok.astype(np.uint8), (max(1, ww // 2), max(1, hh // 2)), interpolation=cv2.INTER_NEAREST) > 0
        mstore[k] = (su0 // 2, v0 // 2, g.astype(np.float32), okh)
        del wimg, ok, mask
        prog(70 + 18 * (k + 1) / N, f"{sid} 합성 중 {k + 1}/{N}")
    res, rmask = blender.blend(None, None)
    eq = np.clip(res[:, Mw:Mw + W], 0, 255).astype(np.uint8)
    covered = rmask[:, Mw:Mw + W] > 0
    del res, rmask, blender
    # 덮인 비율 (위도 −60° 위)
    vlim = int(H * (0.5 + 60 / 180))
    coverage = float(covered[:vlim].mean())
    # 이음선 품질
    prog(90, f"{sid} 이음선 검사 중")
    label_m = cv2.resize(label_s, (Wm, Hm), interpolation=cv2.INTER_NEAREST)
    s_med, s_p90, per_seam = seam_metrics(label_m, mstore, W, Wm, Hm)
    del mstore
    if opts.debug:
        os.makedirs(os.path.join(out_dir, sid), exist_ok=True)
        cv2.imwrite(os.path.join(out_dir, sid, "debug_covered.png"), cv2.resize(covered.astype(np.uint8) * 255, (1024, 512), interpolation=cv2.INTER_AREA))
    # 구멍 메우기
    eq, nadir_r = fill_pole(eq, covered, "nadir", opts.nadir, opts.nadir_radius)
    zen_hole = not covered[: max(1, H // 18)].all()
    if zen_hole:
        eq, _ = fill_pole(eq, covered, "zenith", "blur", 0)
    eq = fill_small_holes(eq, covered)
    # 저장
    d_spot = os.path.join(out_dir, sid)
    os.makedirs(os.path.join(d_spot, "tiles"), exist_ok=True)
    jp = [int(cv2.IMWRITE_JPEG_QUALITY), opts.quality, int(cv2.IMWRITE_JPEG_PROGRESSIVE), 1]
    cv2.imwrite(os.path.join(d_spot, "pano.jpg"), eq, jp)
    cv2.imwrite(os.path.join(d_spot, "preview.jpg"), cv2.resize(eq, (2048, 1024), interpolation=cv2.INTER_AREA), [int(cv2.IMWRITE_JPEG_QUALITY), 85, int(cv2.IMWRITE_JPEG_PROGRESSIVE), 1])
    cv2.imwrite(os.path.join(d_spot, "thumb.jpg"), cv2.resize(eq, (512, 256), interpolation=cv2.INTER_AREA), [int(cv2.IMWRITE_JPEG_QUALITY), 82])
    ts = W // TILE_COLS
    for rr in range(TILE_ROWS):
        for cc in range(TILE_COLS):
            cv2.imwrite(os.path.join(d_spot, "tiles", f"{rr}_{cc}.jpg"), eq[rr * ts:(rr + 1) * ts, cc * ts:(cc + 1) * ts], [int(cv2.IMWRITE_JPEG_QUALITY), 88])
    if opts.debug:
        vis = cv2.applyColorMap(((label_s.astype(np.int32) * 47) % 256).astype(np.uint8), cv2.COLORMAP_HSV)
        vis[label_s < 0] = 0
        cv2.imwrite(os.path.join(d_spot, "debug_labels.png"), vis)
    me = match_err * scale_err
    # 등급 (계약 4절): 8192 폭 px 기준을 출력 폭에 비례. 안전장치가 작동했으면(초점 고정·사진 되돌림 2장 이상) 나쁨
    k8 = W / 8192.0
    smed = s_med if s_med is not None else (float(np.median(me)) if len(me) else 99)
    sp = s_p90 if s_p90 is not None else (float(np.percentile(me, 90)) if len(me) else 99)
    grade = "poor"
    if smed <= 2.5 * k8 and sp <= 8 * k8 and coverage >= 0.98:
        grade = "good"
    elif smed <= 5 * k8 and sp <= 20 * k8 and coverage >= 0.93:
        grade = "fair"
    if fix_f or n_reset >= 2:
        grade = "poor"
    ypr = [R_to_ypr(c.R) for c in cams]
    rot_change = [rot_angle_deg(cams[k].R, R0[k]) for k in range(N)]
    quality = {
        "grade": grade, "shots": len(shots), "used": N, "linked": int(linked.sum()),
        "coverage": round(coverage, 4),
        "seam_px_med": None if s_med is None else round(s_med, 2), "seam_px_p90": None if s_p90 is None else round(s_p90, 2),
        "match_px_med": round(float(np.median(me)), 2) if len(me) else None,
        "match_px_p90": round(float(np.percentile(me, 90)), 2) if len(me) else None,
        "focal_px": [round(float(f), 1) for f in sorted({round(c.f * (keys[gid[k]][0] / c.w), 3) for k, c in enumerate(cams)})],
        "sensor_fix_deg_med": round(float(np.median(rot_change)), 2), "sensor_fix_deg_max": round(float(np.max(rot_change)), 2),
        "nadir_deg": round(nadir_r, 1),
        "guards": (["focal_fixed"] if fix_f else []) + ([f"reset_{n_reset}"] if n_reset else []),
    }
    report = {
        "id": sid, "width": W, "height": H, "seconds": round(time.time() - t0, 1), "quality": quality,
        "pairs": len(pair_stats), "pair_candidates": len(pairs), "matches": int(len(me)),
        "groups": [{"w": k[0], "h": k[1], "src": k[2], "f_px": round(float(cams[np.nonzero(gid == g)[0][0]].f * k[0] / cams[np.nonzero(gid == g)[0][0]].w), 2),
                    "f0_px": round(float(f0g[g]), 2), "k1": round(float(cams[np.nonzero(gid == g)[0][0]].k1), 4)} for g, k in enumerate(keys)],
        "images": [{"file": used_shots[k].get("file"), "q": [round(a, 6) for a in R_to_quat(cams[k].R)],
                    "yaw": round(ypr[k][0], 2), "pitch": round(ypr[k][1], 2), "roll": round(ypr[k][2], 2),
                    "sensor_fix_deg": round(rot_change[k], 2), "gain": [round(float(a), 3) for a in gains[k][::-1]], "linked": bool(linked[k])}
                   for k in range(N)],
        "skipped": skipped, "seams": per_seam[:200],
    }
    return W, H, quality, report


# ───────────────────────── 투어 ─────────────────────────
def wrap180(a):
    return (a + 180.0) % 360.0 - 180.0


def build_links(spots_meta, ok_ids):
    """계약 3.1: next 가 있으면 A→B 와 B→A(+180°), 없으면 순서대로 yaw=null"""
    links = {sid: [] for sid in ok_ids}
    order = [s.get("id") for s in spots_meta if s.get("id") in ok_ids]
    names = {s.get("id"): s.get("name") or s.get("id") for s in spots_meta}
    frames = {s.get("id"): s.get("frame", 1) for s in spots_meta}
    nxt = {s.get("id"): s.get("next") for s in spots_meta}
    for a, b in zip(order, order[1:]):
        n = nxt.get(a)
        same = frames.get(a) == frames.get(b)
        if isinstance(n, dict) and isinstance(n.get("yaw"), (int, float)) and same:
            ya = wrap180(float(n["yaw"]))
            links[a].append({"to": b, "yaw": round(ya, 2), "pitch": -18.0, "label": names.get(b)})
            links[b].append({"to": a, "yaw": round(wrap180(ya + 180), 2), "pitch": -18.0, "label": names.get(a)})
        else:
            links[a].append({"to": b, "yaw": None, "pitch": -18.0, "label": names.get(b)})
            links[b].append({"to": a, "yaw": None, "pitch": -18.0, "label": names.get(a)})
    return links


def main(argv=None):
    ap = argparse.ArgumentParser(description="kgeoScan 360° 파노라마 스티처 (docs/pano_contract.md)")
    ap.add_argument("src", help="pano_spots.zip 또는 spots.json 이 있는 폴더")
    ap.add_argument("--out", required=True)
    ap.add_argument("--size", type=int, default=8192, help="등장방형 폭 상한 (원본보다 크게 늘리지 않음)")
    ap.add_argument("--nadir", choices=("logo", "blur", "none"), default="logo")
    ap.add_argument("--nadir-radius", type=float, default=15.0, help="천저 로고 반지름 (°)")
    ap.add_argument("--spots", default="", help="일부 지점만 (쉼표)")
    ap.add_argument("--title", default="")
    ap.add_argument("--quality", type=int, default=90)
    ap.add_argument("--bands", type=int, default=5)
    ap.add_argument("--features", type=int, default=2500)
    ap.add_argument("--work-long", type=int, default=1280, help="특징점 찾을 때 긴 변 (px)")
    ap.add_argument("--f0-ratio", type=float, default=0.78, help="초점 초기값 = 긴 변 × 이 값 (폰 기본 카메라 ≈ 26 mm)")
    ap.add_argument("--sig-rot", type=float, default=5.0, help="센서 자세 사전값 표준편차 (°)")
    ap.add_argument("--tol1", type=float, default=8.0, help="1차 짝 예측 반경 (°)")
    ap.add_argument("--tol2", type=float, default=2.5, help="2차 짝 예측 반경 (°)")
    ap.add_argument("--max-per-pair", type=int, default=400)
    ap.add_argument("--no-k1", action="store_true")
    ap.add_argument("--f-lo", type=float, default=0.90, help="초점이 초기값의 이 배수보다 작아지면 초기값으로 고정")
    ap.add_argument("--f-hi", type=float, default=1.10)
    ap.add_argument("--max-fix", type=float, default=12.0, help="센서 자세에서 이만큼(°) 넘게 벗어난 사진은 센서 자세로 되돌린다")
    ap.add_argument("--debug", action="store_true")
    opts = ap.parse_args(argv)
    if opts.nadir == "none":
        opts.nadir = "blur"
    try:
        src = Source(opts.src)
    except InputError as e:
        log(str(e))
        return 2
    meta = src.meta
    os.makedirs(opts.out, exist_ok=True)
    want = {s.strip() for s in opts.spots.split(",") if s.strip()}
    spots_meta = [s for s in meta["spots"] if isinstance(s, dict) and (not want or s.get("id") in want)]
    if not spots_meta:
        log("고른 지점이 없습니다")
        return 2
    for k, s in enumerate(spots_meta):
        if not s.get("id"):
            s["id"] = f"s{k + 1:02d}"
    t0 = time.time()
    results, failed, reports = {}, [], []
    n = len(spots_meta)
    for k, s in enumerate(spots_meta):
        sid = s["id"]
        base = 100.0 * k / n
        span = 100.0 / n

        def prog(p, m, base=base, span=span):
            progress(base + span * p / 100.0 * 0.98, m)
        try:
            W, H, q, rep = stitch_spot(src, s, opts.out, opts, prog)
            results[sid] = (W, H, q)
            reports.append(rep)
            log(f"[{sid}] {W}x{H} {q['grade']} seam p90={q['seam_px_p90']} match med={q['match_px_med']} coverage={q['coverage']} ({rep['seconds']} s)")
        except InputError as e:
            failed.append({"id": sid, "error": str(e)})
            log(f"[{sid}] 실패: {e}")
        except Exception as e:      # 한 지점이 실패해도 나머지는 만든다
            import traceback
            traceback.print_exc()
            failed.append({"id": sid, "error": f"스티칭 오류: {e}"})
    ok_ids = [s["id"] for s in spots_meta if s["id"] in results]
    links = build_links(spots_meta, set(ok_ids))
    north = None
    tour_spots = []
    for s in spots_meta:
        sid = s["id"]
        if sid not in results:
            continue
        W, H, q = results[sid]
        if north is None and isinstance(s.get("north_yaw"), (int, float)):
            north = float(s["north_yaw"])
        tour_spots.append({
            "id": sid, "name": s.get("name") or sid,
            "pano": f"{sid}/pano.jpg", "preview": f"{sid}/preview.jpg", "thumb": f"{sid}/thumb.jpg",
            "width": W, "height": H,
            "tiles": {"url": f"{sid}/tiles/{{r}}_{{c}}.jpg", "cols": TILE_COLS, "rows": TILE_ROWS, "size": W // TILE_COLS},
            "start_yaw": round(wrap180(float(s.get("start_yaw") or 0.0)), 2), "start_pitch": 0.0,
            "north_yaw": s.get("north_yaw") if isinstance(s.get("north_yaw"), (int, float)) else None,
            "frame": s.get("frame", 1),
            "links": links.get(sid, []), "plan_xy": None, "pose3d": None, "quality": q,
        })
    if north is None and isinstance(meta.get("north_yaw"), (int, float)):
        north = float(meta["north_yaw"])
    tour = {
        "version": 1, "generator": VERSION,
        "title": opts.title or meta.get("title") or "",
        "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "north_yaw": north,
        "start": ok_ids[0] if ok_ids else None,
        "spots": tour_spots, "floorplan": None, "failed": failed,
    }
    with open(os.path.join(opts.out, "tour.json"), "w", encoding="utf-8") as fh:
        json.dump(tour, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(opts.out, "stitch_report.json"), "w", encoding="utf-8") as fh:
        json.dump({"generator": VERSION, "seconds": round(time.time() - t0, 1), "spots": reports, "failed": failed},
                  fh, ensure_ascii=False, indent=1)
    progress(100, f"완료 — 지점 {len(ok_ids)}개" + (f", 실패 {len(failed)}개" if failed else ""))
    if not ok_ids:
        log("만든 지점이 없습니다: " + "; ".join(f"{f['id']} {f['error']}" for f in failed))
        return 2 if all("오류" not in f["error"] for f in failed) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
