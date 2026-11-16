r"""스플랫 .splat → .spz (Niantic SPZ v2, gzip) — 폰에서 '사진 3D' 를 빨리 열려고 (2026-11-16)

    python -I splat_to_spz.py <a.splat> [<a.spz>]

.splat 은 점 하나에 32 바이트(float 위치·크기)라 gzip 해도 6 % 밖에 안 준다 (50만 점 = 16 MB).
SPZ v2 는 점 하나에 19 바이트(위치 24비트 고정소수, 투명도·색·크기·회전 각 1바이트)를 gzip 한다.
사이트 뷰어(@mkkellogg/gaussian-splats-3d 0.4.7 SpzLoader, 버전 1~2)가 그대로 읽는다. 좌표는 바꾸지 않는다(.splat 과 같은 축).
  위치: round(p × 2^12) 24비트 (±2048 m, 0.24 mm 단위)     투명도: .splat 의 A 그대로(sigmoid×255)
  색: SH DC = (rgb−0.5)/C0, 바이트 = (dc×0.15+0.5)×255       크기: (ln s + 10)×16
  회전: w ≥ 0 으로 맞춘 단위 사원수의 xyz, (x+1)×127.5
"""
import gzip
import os
import struct
import sys

import numpy as np

SPZ_MAGIC = 0x5053474E          # "NGSP"
SH_C0 = 0.28209479177387814
COLOR_SCALE = 0.15
FRACTIONAL_BITS = 12


def splat_to_spz(src, dst=None, log=print):
    dst = dst or (os.path.splitext(src)[0] + ".spz")
    raw = np.fromfile(src, dtype=np.uint8)
    if raw.size % 32:
        raise ValueError(f".splat 크기가 32 의 배수가 아님: {raw.size}")
    n = raw.size // 32
    rows = raw.reshape(n, 32)
    pos = rows[:, 0:12].copy().view(np.float32).reshape(n, 3).astype(np.float64)
    scl = rows[:, 12:24].copy().view(np.float32).reshape(n, 3).astype(np.float64)
    rgba = rows[:, 24:28].astype(np.float64)
    rot = (rows[:, 28:32].astype(np.float64) - 128.0) / 128.0          # .splat 은 w,x,y,z 순서

    lim = (1 << 23) - 1
    q = np.clip(np.round(pos * (1 << FRACTIONAL_BITS)), -lim, lim).astype(np.int64)
    q &= 0xFFFFFF                                                     # 2의 보수 24비트
    pos_b = np.empty((n, 3, 3), np.uint8)
    pos_b[:, :, 0] = q & 0xFF
    pos_b[:, :, 1] = (q >> 8) & 0xFF
    pos_b[:, :, 2] = (q >> 16) & 0xFF

    alpha_b = rgba[:, 3].astype(np.uint8)
    dc = (rgba[:, :3] / 255.0 - 0.5) / SH_C0
    col_b = np.clip(np.round((dc * COLOR_SCALE + 0.5) * 255.0), 0, 255).astype(np.uint8)
    scl_b = np.clip(np.round((np.log(np.maximum(scl, 1e-30)) + 10.0) * 16.0), 0, 255).astype(np.uint8)

    nrm = np.linalg.norm(rot, axis=1, keepdims=True)
    rot = np.where(nrm > 1e-12, rot / np.maximum(nrm, 1e-12), np.array([[1.0, 0, 0, 0]]))
    rot = np.where(rot[:, :1] < 0, -rot, rot)                        # w ≥ 0
    rot_b = np.clip(np.round((rot[:, 1:4] + 1.0) * 127.5), 0, 255).astype(np.uint8)

    header = struct.pack("<IIIBBBB", SPZ_MAGIC, 2, n, 0, FRACTIONAL_BITS, 0, 0)
    body = header + pos_b.tobytes() + alpha_b.tobytes() + col_b.tobytes() + scl_b.tobytes() + rot_b.tobytes()
    tmp = dst + ".tmp"
    with open(tmp, "wb") as f:
        f.write(gzip.compress(body, compresslevel=9, mtime=0))
    os.replace(tmp, dst)
    log(f"splat_to_spz: {os.path.basename(src)} {os.path.getsize(src) / 1e6:.1f} MB ({n:,} splats) -> {os.path.basename(dst)} {os.path.getsize(dst) / 1e6:.1f} MB")
    return dst


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    splat_to_spz(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
