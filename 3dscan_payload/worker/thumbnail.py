"""
Stray Scanner dataset -> thumb.jpg  (대표 이미지: 고르게 뽑은 N 프레임 중 가장 선명한 것, 자세로 똑바로 세움)

  python -I thumbnail.py --data <dataset_dir> --out <thumb.jpg> [--samples 12] [--size 640] [--convention cv|arkit]
  python -I thumbnail.py --zip  <scan.zip>    --out <thumb.jpg>      (rgb.mp4 · odometry.csv 만 풀어서 처리)

실패하면 0 이 아닌 코드로 끝난다. 호출하는 쪽(process_scan / pipeline / maintenance)은 썸네일을 선택 사항으로 다룬다.
"""
import argparse
import csv
import json
import math
import os
import shutil
import sys
import tempfile
import zipfile

import cv2
import numpy as np


def quat_to_mat(qx, qy, qz, qw):
    n = math.sqrt(qx * qx + qy * qy + qz * qz + qw * qw) or 1.0
    qx, qy, qz, qw = qx / n, qy / n, qz / n, qw / n
    return np.array([
        [1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qz * qw), 2 * (qx * qz + qy * qw)],
        [2 * (qx * qy + qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qx * qw)],
        [2 * (qx * qz - qy * qw), 2 * (qy * qz + qx * qw), 1 - 2 * (qx * qx + qy * qy)],
    ])


def read_rotations(path):
    """odometry.csv -> {frame_index: R_world_from_camera}"""
    out = {}
    with open(path, newline="") as f:
        reader = csv.reader(f)
        header = [h.strip() for h in next(reader)]
        col = {n: i for i, n in enumerate(header)}
        if not all(k in col for k in ("qx", "qy", "qz", "qw")):
            return out
        for r in reader:
            if not r or not any(c.strip() for c in r):
                continue
            g = lambda k: float(r[col[k]])
            idx = int(g("frame")) if "frame" in col else len(out)
            out[idx] = quat_to_mat(g("qx"), g("qy"), g("qz"), g("qw"))
    return out


def upright_rotation(R, convention):
    """ARKit 월드는 중력 정렬(y 위). 영상의 오른쪽 방향(R[:,0])이 위/아래를 가리키면 세로로 든 것 → 90° 회전.
    영상의 위쪽 방향은 OpenCV 규약이면 -R[:,1], ARKit 규약이면 +R[:,1]."""
    up = np.array([0.0, 1.0, 0.0])
    right = R[:, 0]
    img_up = -R[:, 1] if convention == "cv" else R[:, 1]
    dr, du = float(right @ up), float(img_up @ up)
    if dr > 0.6:
        return cv2.ROTATE_90_COUNTERCLOCKWISE
    if dr < -0.6:
        return cv2.ROTATE_90_CLOCKWISE
    if du < -0.6:
        return cv2.ROTATE_180
    return None


def pick_frame(video_path, samples):
    cap = cv2.VideoCapture(video_path)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if not cap.isOpened() or n <= 0:
        raise SystemExit("rgb.mp4 를 열 수 없음")
    if samples <= 1 or n < 3:
        idxs = [n // 2]
    else:
        idxs = sorted({int(round((n - 1) * (0.1 + 0.8 * k / (samples - 1)))) for k in range(samples)})
    best = None
    for i in idxs:
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, frame = cap.read()
        if not ok or frame is None:
            continue
        h, w = frame.shape[:2]
        small = cv2.resize(frame, (480, max(1, int(480 * h / w))), interpolation=cv2.INTER_AREA)
        sharp = cv2.Laplacian(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
        center_w = 0.7 + 0.3 * (1.0 - abs(i / max(1, n - 1) - 0.5) * 2.0)   # 녹화 중간을 조금 선호
        score = sharp * center_w
        if best is None or score > best[0]:
            best = (score, i, frame, sharp)
    cap.release()
    if best is None:
        raise SystemExit("프레임을 읽지 못함")
    return best[1], best[2], best[3], n


def extract_from_zip(zip_path, tmp_dir):
    """zip 에서 rgb.mp4 와 odometry.csv 만 꺼낸다 (하위 폴더 어디에 있어도)."""
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        if any(n.startswith("/") or ".." in n.split("/") for n in names):
            raise SystemExit("zip 에 안전하지 않은 경로가 있음")
        for want in ("rgb.mp4", "odometry.csv"):
            cand = [n for n in names if n.split("/")[-1] == want]
            if not cand:
                if want == "rgb.mp4":
                    raise SystemExit("zip 에 rgb.mp4 가 없음")
                continue
            cand.sort(key=lambda s: s.count("/"))
            with zf.open(cand[0]) as src, open(os.path.join(tmp_dir, want), "wb") as dst:
                shutil.copyfileobj(src, dst, 1 << 20)
    return tmp_dir


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data")
    ap.add_argument("--zip")
    ap.add_argument("--out", required=True)
    ap.add_argument("--samples", type=int, default=12)
    ap.add_argument("--size", type=int, default=640)
    ap.add_argument("--quality", type=int, default=82)
    ap.add_argument("--convention", choices=["cv", "arkit"], default="cv")
    args = ap.parse_args()
    if not args.data and not args.zip:
        raise SystemExit("--data 또는 --zip 이 필요")

    tmp = None
    data = args.data
    try:
        if args.zip:
            tmp = tempfile.mkdtemp(prefix="thumb_", dir=os.path.dirname(os.path.abspath(args.out)) or None)
            data = extract_from_zip(args.zip, tmp)
        video = os.path.join(data, "rgb.mp4")
        if not os.path.exists(video):
            raise SystemExit("rgb.mp4 없음: " + data)
        idx, frame, sharp, n = pick_frame(video, args.samples)
        rot, R = None, None
        odo = os.path.join(data, "odometry.csv")
        if os.path.exists(odo):
            rots = read_rotations(odo)
            if rots:
                key = idx if idx in rots else min(rots, key=lambda k: abs(k - idx))
                R = rots[key]
                rot = upright_rotation(R, args.convention)
        if rot is not None:
            frame = cv2.rotate(frame, rot)
        h, w = frame.shape[:2]
        s = args.size / max(h, w)
        if s < 1.0:
            frame = cv2.resize(frame, (max(1, int(w * s)), max(1, int(h * s))), interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, args.quality])
        if not ok:
            raise SystemExit("JPEG 인코딩 실패")
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "wb") as f:
            f.write(buf.tobytes())   # cv2.imwrite 는 비ASCII 경로에서 실패하므로 직접 쓴다
        print(json.dumps(dict(frame=idx, of=n, sharpness=round(float(sharp), 1),
                              rotate={None: "none", cv2.ROTATE_90_CLOCKWISE: "cw90", cv2.ROTATE_90_COUNTERCLOCKWISE: "ccw90",
                                      cv2.ROTATE_180: "180"}[rot],
                              size=[int(frame.shape[1]), int(frame.shape[0])], bytes=len(buf)), ensure_ascii=False))
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
