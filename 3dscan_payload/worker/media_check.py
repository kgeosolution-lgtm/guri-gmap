r"""
웹 3D 현장조사 업로드 품질 검사 — GPU 에 넘기기 전에 1분 안에: 영상 하나 또는 사진 여러 장 → quality.json (+ 썸네일)
  python -I media_check.py (--video X.mp4 | --photos DIR) --out quality.json [--thumb thumb.jpg]

검사 (docs/video3d_contract.md 1c):
  영상: 길이, 해상도, 흔들림 비율(라플라시안 선명도가 상위 대비 낮은 프레임), 움직임 속도(광류: 0.25초에 화면 폭의 몇 %),
        거의 안 움직임(누적 이동이 화면 폭의 몇 배), 밝기·급변
  사진: 장수, 해상도, 흔들림 비율, 이웃 사진 겹침(ORB 대응 + RANSAC 인라이어), 밝기
결과: grade good|fair|poor, score 0~100, summary(한 줄), checks[{key,label,value,ok}], tips[...]
"""
import argparse
import glob
import json
import os
import time

import cv2
import numpy as np

PHOTO_EXT = (".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp")


def _gray_small(img, w=640):
    g = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    s = w / max(1, g.shape[1])
    return cv2.resize(g, (w, max(1, int(g.shape[0] * s))), interpolation=cv2.INTER_AREA) if s < 1 else g


def _sharp(g):
    return float(cv2.Laplacian(g, cv2.CV_64F).var())


def _blur_ratio(sh):
    sh = np.asarray(sh, float)
    if not len(sh):
        return 0.0, np.zeros(0, bool)
    ref = np.percentile(sh, 90)
    # 같은 촬영의 선명한 쪽 대비 35 % 미만 = 번짐. 전부 흐린 촬영도 잡도록 절대 기준(긴 변 640~800 px 회색에서 라플라시안 분산 15)을 함께 쓴다
    bad = (sh < 0.35 * ref) | (sh < 15.0)
    return float(bad.mean()), bad


def _write_thumb(img, path, size=640):
    h, w = img.shape[:2]
    s = size / max(h, w)
    if s < 1:
        img = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 82])
    if ok:
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        with open(path, "wb") as f:
            f.write(buf.tobytes())


def check_video(path, thumb=None, max_samples=240):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return None, "영상을 열 수 없습니다 (코덱·파일 손상)"
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    dur = n / fps if fps > 0 and n > 0 else 0.0
    step = max(1, int(round(fps / 4.0)))                   # 초당 4장
    if n and n / step > max_samples:
        step = int(np.ceil(n / max_samples))
    sh, br, smalls, fulls, i = [], [], [], [], 0
    shape = None
    while True:
        if not cap.grab():
            break
        if i % step == 0:
            ok, fr = cap.retrieve()
            if ok:
                shape = shape or fr.shape[:2]
                g = _gray_small(fr)
                sh.append(_sharp(g)); br.append(float(g.mean())); smalls.append(cv2.resize(g, (320, int(320 * g.shape[0] / g.shape[1]))))
                if thumb and len(fulls) < 400:
                    fulls.append((len(sh) - 1, cv2.resize(fr, (960, int(960 * fr.shape[0] / fr.shape[1])), interpolation=cv2.INTER_AREA)))
        i += 1
    cap.release()
    if not sh:
        return None, "영상에서 화면을 읽지 못했습니다"
    if not dur:
        dur = i / fps
    blur, bad = _blur_ratio(sh)
    dt = step / fps
    flows = []
    for a, b in zip(smalls[:-1], smalls[1:]):
        f = cv2.calcOpticalFlowFarneback(a, b, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        flows.append(float(np.median(np.linalg.norm(f, axis=2))) / a.shape[1])      # 화면 폭 대비
    flows = np.asarray(flows) * (0.25 / dt) if flows else np.zeros(0)                # 0.25 초 기준으로 환산
    fast = float((flows > 0.15).mean()) if len(flows) else 0.0
    travel = float(flows.sum() * (dt / 0.25)) if len(flows) else 0.0                 # 누적 이동 (화면 폭 단위)
    br = np.asarray(br)
    jumps = int((np.abs(np.diff(br)) > 12).sum()) if len(br) > 1 else 0
    short = min(shape) if shape else 0
    if thumb and fulls:                                    # 썸네일: 가운데 쪽의 선명한 화면
        mid = len(sh) / 2
        k, img = max(fulls, key=lambda t: sh[t[0]] * (1.0 - 0.5 * abs(t[0] - mid) / max(1, mid)))
        _write_thumb(img, thumb)
    checks = [
        dict(key="duration", label="길이", value=f"{dur:.0f}초", ok=10 <= dur <= 120),
        dict(key="resolution", label="해상도", value=f"{shape[1]}×{shape[0]}" if shape else "?", ok=short >= 1080),
        dict(key="blur", label="흔들림", value=f"화면의 {blur * 100:.0f} %", ok=blur <= 0.15),
        dict(key="speed", label="움직임 속도", value=f"너무 빠른 구간 {fast * 100:.0f} %", ok=fast <= 0.15),
        dict(key="travel", label="움직인 거리", value=f"화면 폭의 {travel:.1f}배", ok=travel >= 1.5),
        dict(key="light", label="밝기", value=f"평균 {br.mean():.0f}/255, 급변 {jumps}번", ok=br.mean() >= 60 and jumps <= 3),
    ]
    tips = []
    if dur < 10:
        tips.append("20~60초 동안 대상 주위를 천천히 한 바퀴 돌며 찍어 주세요")
    if short < 1080:
        tips.append("카메라 설정에서 영상 해상도를 1080p 또는 4K 로 올려 주세요")
    if blur > 0.15 or fast > 0.15:
        tips.append("더 천천히(초당 30 cm 정도) 움직이고, 손떨림 보정(슈퍼 스테디·향상된 안정화)은 꺼 주세요")
    if travel < 1.5:
        tips.append("제자리에서 돌지 말고 대상 주위를 걸으며 여러 방향에서 찍어 주세요")
    if br.mean() < 60:
        tips.append("더 밝은 곳에서 찍거나 조명을 켜 주세요")
    if jumps > 3:
        tips.append("화면을 길게 눌러 노출·초점을 고정한 뒤 찍어 주세요")
    score = 100 - (20 if dur < 10 else 0) - (15 if short < 1080 else 0) - (45 if blur > 0.4 else 30 if blur > 0.3 else 15 if blur > 0.15 else 0) \
        - (20 if fast > 0.3 else 10 if fast > 0.15 else 0) - (25 if travel < 1.5 else 0) - (15 if br.mean() < 60 else 0) - (10 if jumps > 3 else 0)
    return dict(kind="video", score=max(0, score), checks=checks, tips=tips, frames_checked=len(sh), duration_s=round(dur, 1)), None


def check_photos(folder, thumb=None):
    files = sorted(f for f in glob.glob(os.path.join(folder, "*")) if f.lower().endswith(PHOTO_EXT))
    if not files:
        return None, "사진이 없습니다"
    sh, br, grays, sizes, ok_files = [], [], [], [], []
    for f in files:
        img = cv2.imdecode(np.fromfile(f, np.uint8), cv2.IMREAD_COLOR)        # EXIF 회전 적용 (검사용)
        if img is None:
            continue                                      # HEIC 등 OpenCV 가 못 여는 형식은 장수만 센다
        sizes.append(img.shape[:2])
        g = _gray_small(img, 800)
        sh.append(_sharp(g)); br.append(float(g.mean())); grays.append(g); ok_files.append(f)
    n = len(files)
    readable = len(ok_files)
    blur, bad = _blur_ratio(sh)
    orb = cv2.ORB_create(1500)
    feats = [orb.detectAndCompute(g, None) for g in grays]
    bf = cv2.BFMatcher(cv2.NORM_HAMMING)
    weak = 0
    pairs = 0
    for (k1, d1), (k2, d2) in zip(feats[:-1], feats[1:]):       # 고른 순서(대개 촬영 순서)의 이웃끼리 겹침
        pairs += 1
        if d1 is None or d2 is None or len(k1) < 50 or len(k2) < 50:
            weak += 1
            continue
        m = [a for a, b in (x for x in bf.knnMatch(d1, d2, k=2) if len(x) == 2) if a.distance < 0.8 * b.distance]
        if len(m) < 30:
            weak += 1
            continue
        src = np.float32([k1[a.queryIdx].pt for a in m]); dst = np.float32([k2[a.trainIdx].pt for a in m])
        _, inl = cv2.findHomography(src, dst, cv2.RANSAC, 6.0)
        if inl is None or int(inl.sum()) < 25:
            weak += 1
    weak_frac = weak / max(1, pairs)
    short = min(min(s) for s in sizes) if sizes else 0
    br = np.asarray(br) if br else np.array([0.0])
    if thumb and grays:
        k = int(np.argmax(sh))
        img = cv2.imdecode(np.fromfile(ok_files[k], np.uint8), cv2.IMREAD_COLOR)
        if img is not None:
            _write_thumb(img, thumb)
    checks = [
        dict(key="count", label="장수", value=f"{n}장", ok=n >= 30),
        dict(key="resolution", label="해상도", value=f"짧은 변 {short} px" if short else "읽지 못함", ok=short >= 1500),
        dict(key="blur", label="흔들림", value=f"사진의 {blur * 100:.0f} %", ok=blur <= 0.15),
        dict(key="overlap", label="이웃 사진 겹침", value=f"겹침 부족 {weak}/{pairs}쌍", ok=weak_frac <= 0.2),
        dict(key="light", label="밝기", value=f"평균 {br.mean():.0f}/255", ok=br.mean() >= 60),
    ]
    if readable < n:
        checks.append(dict(key="format", label="형식", value=f"{n - readable}장은 서버 검사에서 열지 못함(HEIC 등)", ok=True))
    tips = []
    if n < 30:
        tips.append("사진을 40~80장 찍어 주세요 (한 걸음에 한 장, 이웃 사진과 2/3 겹치게)")
    if short and short < 1500:
        tips.append("원본 크기 그대로 올려 주세요 (메신저로 받은 사진은 줄어 있음)")
    if blur > 0.15:
        tips.append("찍을 때 잠깐 멈춰서 찍어 주세요 (걸으면서 누르면 번집니다)")
    if weak_frac > 0.2:
        tips.append("사진 사이 간격을 줄여 더 많이 겹치게 찍어 주세요 (한 번에 조금씩 옆으로)")
    if br.mean() < 60:
        tips.append("더 밝은 곳에서 찍거나 조명을 켜 주세요")
    score = 100 - (50 if n < 15 else 15 if n < 30 else 0) - (15 if short and short < 1500 else 0) \
        - (45 if blur > 0.4 else 30 if blur > 0.3 else 15 if blur > 0.15 else 0) - (30 if weak_frac > 0.4 else 15 if weak_frac > 0.2 else 0) - (15 if br.mean() < 60 else 0)
    return dict(kind="photos", score=max(0, score), checks=checks, tips=tips, frames_checked=readable, photo_count=n), None


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--video"); g.add_argument("--photos")
    ap.add_argument("--out", required=True)
    ap.add_argument("--thumb")
    a = ap.parse_args()
    t0 = time.time()
    res, err = check_video(a.video, a.thumb) if a.video else check_photos(a.photos, a.thumb)
    if res is None:
        q = dict(grade="poor", score=0, summary=err, checks=[], tips=["다른 영상·사진으로 다시 올려 주세요"], frames_checked=0)
    else:
        for c in res["checks"]:
            c["ok"] = bool(c["ok"])                        # numpy bool → JSON
        sc = int(res["score"])
        res["score"] = sc
        grade = "good" if sc >= 75 else "fair" if sc >= 50 else "poor"
        bad = [c["label"] for c in res["checks"] if not c["ok"]]
        summary = {"good": "3D 를 만들기 좋은 촬영입니다",
                   "fair": "3D 가 만들어지지만 " + ", ".join(bad) + " 때문에 흐릴 수 있습니다",
                   "poor": ", ".join(bad) + " 문제로 3D 가 실패하거나 많이 흐릴 수 있습니다. 다시 찍기를 권합니다"}[grade]
        q = dict(res, grade=grade, summary=summary)
    q["seconds"] = round(time.time() - t0, 1)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(q, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: q[k] for k in ("grade", "score", "seconds")}))


if __name__ == "__main__":
    main()
