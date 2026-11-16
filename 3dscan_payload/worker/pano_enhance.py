r"""kgeoScan VR 투어 — 자동 보정 (docs/share_contract.md 4절, pano_contract.md 3.2절)

pano_stitch.main 이 모든 지점을 이은 뒤 지점마다 한 번 돌린다(sNN/pano.jpg 를 읽어 고친 뒤 pano·preview·thumb·tiles 를 다시 쓴다).

  1) 지점 사이 밝기·색 맞춤: 지점마다 중간 밝기 화소의 채널 중앙값 → 지점들의 중앙값에 맞춘다
     (흰색 균형은 끝까지, 밝기는 절반만 — 어두운 방은 조금 어둡게 남긴다). 지점이 하나면 하지 않는다.
  2) 잡음 줄이기: 밝기 잡음 σ 를 평탄한 곳의 라플라시안 MAD 로 재고, 색 잡음(Cr·Cb)은 늘 가볍게,
     밝기는 σ 가 클 때만 양방향 필터로.
  3) 톤 매핑(한 장 노출): log 밝기를 바탕(저해상도 양방향 필터)과 결로 나눠, 밝은 바탕은 누르고(창밖·조명 둘레 계조)
     어두운 바탕은 조금 올리고, 결은 살짝 키운다. 완전히 날아간 덩어리(창)는 회색이 되지 않게 누르지 않는다.
     → 날아간 정보는 되살릴 수 없다. 여러 노출을 이미 가진 영상 지점은 스티처가 겹침에서 안 날아간 쪽을 고른다.
  4) 얼굴 흐림 (기본 켬, blur_faces=0 이면 끔): OpenCV FaceDetectorYN(YuNet, opencv_zoo, MIT) 모델 파일이 있을 때만.
     등장방형의 위도 −50°~+45° 띠를 4096 폭으로 줄여 찾고(360° 끝은 이어 붙여), 찾은 얼굴을 타원으로 강하게 흐린다.
"""
import math
import os

import cv2
import numpy as np

FACE_MODEL_NAME = "face_detection_yunet_2023mar.onnx"


def default_face_model():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", FACE_MODEL_NAME)


def _band_mask(H, W, lo=-55.0, hi=55.0):
    lat = 90.0 - (np.arange(H) + 0.5) * 180.0 / H
    return (lat >= lo) & (lat <= hi)


def spot_stats(img):
    """중간 밝기 화소(날아가지도 너무 어둡지도 않은)의 채널 중앙값 (B, G, R)"""
    H, W = img.shape[:2]
    s = 1024.0 / W
    sm = cv2.resize(img, (1024, max(8, int(round(H * s)))), interpolation=cv2.INTER_AREA)
    rows = _band_mask(sm.shape[0], sm.shape[1])
    px = sm[rows].reshape(-1, 3).astype(np.float32)
    mx = px.max(1)
    mn = px.min(1)
    ok = (mx < 245) & (mn > 12)
    if ok.sum() < 1000:
        ok = mx < 250
    med = np.median(px[ok], axis=0)
    return [float(v) for v in med]


def match_gains(stats, lum_frac=0.5, max_lum=0.25, max_wb=0.08):
    """stats: {sid: [B,G,R]} → {sid: [gB,gG,gR]}"""
    if len(stats) < 2:
        return {k: [1.0, 1.0, 1.0] for k in stats}
    S = {k: np.maximum(np.array(v, float), 1.0) for k, v in stats.items()}
    lum = {k: 0.0722 * v[0] + 0.7152 * v[1] + 0.2126 * v[2] for k, v in S.items()}
    chrom = {k: np.log(v / lum[k]) for k, v in S.items()}           # 밝기에 대한 채널 비 (log)
    t_lum = float(np.median([math.log(v) for v in lum.values()]))
    t_chr = np.median(np.stack(list(chrom.values())), axis=0)
    out = {}
    for k in S:
        gl = math.exp(np.clip((t_lum - math.log(lum[k])) * lum_frac, math.log(1 - max_lum), math.log(1 + max_lum)))
        gc = np.exp(np.clip(t_chr - chrom[k], math.log(1 - max_wb), math.log(1 + max_wb)))
        # 흰색 균형 이득이 밝기를 바꾸지 않게 정규화
        gc = gc / (0.0722 * gc[0] + 0.7152 * gc[1] + 0.2126 * gc[2])
        out[k] = [float(gl * g) for g in gc]
    return out


def noise_sigma(img):
    """밝기 잡음 σ (8 bit) — 평탄한 곳의 라플라시안 MAD"""
    H, W = img.shape[:2]
    y0, y1 = int(H * 0.3), int(H * 0.7)
    Y = cv2.cvtColor(img[y0:y1], cv2.COLOR_BGR2GRAY).astype(np.float32)
    # Immerkær(1996): σ = √(π/2)·mean|I∗N|/6, N = [[1,−2,1],[−2,4,−2],[1,−2,1]] — 평탄한 곳만 (윤곽은 잡음이 아님)
    N = np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]], np.float32)
    R = np.abs(cv2.filter2D(Y, cv2.CV_32F, N))
    g = cv2.GaussianBlur(np.abs(cv2.Sobel(Y, cv2.CV_32F, 1, 0)) + np.abs(cv2.Sobel(Y, cv2.CV_32F, 0, 1)), (0, 0), 2)
    flat = (g < np.percentile(g, 40)) & (Y > 20) & (Y < 235)
    if flat.sum() < 1000:
        return 0.0
    return float(math.sqrt(math.pi / 2) * float(R[flat].mean()) / 6.0)


def denoise(img, sigma):
    ycc = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
    Y, Cr, Cb = cv2.split(ycc)
    luma = sigma >= 1.6
    if luma:
        Y = cv2.bilateralFilter(Y, 5, max(6.0, 2.5 * sigma), 1.5)
    cs = 1.0 + min(1.5, sigma * 0.4)
    Cr = cv2.bilateralFilter(Cr, 7, 10.0, cs * 2)
    Cb = cv2.bilateralFilter(Cb, 7, 10.0, cs * 2)
    return cv2.cvtColor(cv2.merge([Y, Cr, Cb]), cv2.COLOR_YCrCb2BGR), {"noise_sigma": round(sigma, 2), "luma": luma, "chroma": True}


def neutral_wb(img, frac=0.6, lim=0.07):
    """밝고 무채색에 가까운 곳(흰 벽·천장)이 회색이 되게 채널 이득 (일부만, ±7 %)"""
    H, W = img.shape[:2]
    sm = cv2.resize(img, (1024, max(8, int(round(H * 1024.0 / W)))), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    rows = _band_mask(sm.shape[0], sm.shape[1], -55, 75)
    px = sm[rows].reshape(-1, 3)
    L = 0.0722 * px[:, 0] + 0.7152 * px[:, 1] + 0.2126 * px[:, 2]
    mx, mn = px.max(1), px.min(1)
    sat = (mx - mn) / np.maximum(mx, 1e-3)
    ok = (L > 0.45) & (mx < 0.93) & (sat < 0.12)
    if ok.sum() < 2000:
        return [1.0, 1.0, 1.0]
    m = px[ok].mean(0)
    g = np.exp(np.clip(np.log(m.mean() / np.maximum(m, 1e-3)) * frac, math.log(1 - lim), math.log(1 + lim)))
    g = g / (0.0722 * g[0] + 0.7152 * g[1] + 0.2126 * g[2])
    return [float(v) for v in g]


def tone_map(img, hi_knee=0.55, hi_keep=0.55, lo_knee=0.16, lo_keep=0.72, detail=1.15, target=0.46, ev_frac=0.6, vib=0.12):
    """log 밝기 바탕/결 분리. 밝은 바탕은 (1-hi_keep) 만큼 누르고 어두운 바탕은 올린다. 날아간 덩어리는 그대로"""
    H, W = img.shape[:2]
    f = img.astype(np.float32) * (1.0 / 255.0)
    L = 0.0722 * f[..., 0] + 0.7152 * f[..., 1] + 0.2126 * f[..., 2]
    eps = 1.0 / 512
    lg = np.log2(L + eps)
    sw, sh = max(64, W // 8), max(32, H // 8)
    small = cv2.resize(lg, (sw, sh), interpolation=cv2.INTER_AREA)
    base_s = cv2.bilateralFilter(small, 0, 0.6, 5)
    clip_s = cv2.resize((img.max(2) >= 250).astype(np.float32), (sw, sh), interpolation=cv2.INTER_AREA)
    clip_s = cv2.GaussianBlur(clip_s, (0, 0), 3)
    base = cv2.resize(base_s, (W, H), interpolation=cv2.INTER_LINEAR)
    clipf = np.clip(cv2.resize(clip_s, (W, H), interpolation=cv2.INTER_LINEAR) * 1.6, 0, 1)
    k_hi, k_lo = math.log2(hi_knee), math.log2(lo_knee)
    rows_ = _band_mask(sh, sw, -55, 60)
    med_lg = float(np.median(base_s[rows_]))                     # 방의 밝기 (log2) → 목표 쪽으로 일부 노출 보정
    ev = float(np.clip((math.log2(target) - med_lg) * ev_frac, 0.0, 0.5))          # 어두운 방만 밝힌다 (밝은 방을 어둡게 하지 않음)
    base = base + ev
    over = np.maximum(base - k_hi, 0.0)
    b2 = base - over * (1 - hi_keep) * (1 - clipf)               # 완전히 날아간 창은 누르지 않는다 (회색이 됨)
    under = np.minimum(b2 - k_lo, 0.0)
    b2 = b2 - under * (1 - lo_keep)
    lg2 = b2 + (lg - (base - ev)) * detail
    L2 = np.exp2(lg2) - eps
    ratio = np.clip((L2 + eps) / (L + eps), 0.4, 2.5)
    out = f * ratio[..., None]
    if vib > 0:                                                  # 채도 낮은 색만 조금 살린다 (이미 진한 색은 그대로)
        Lo = (0.0722 * out[..., 0] + 0.7152 * out[..., 1] + 0.2126 * out[..., 2])[..., None]
        mxo, mno = out.max(-1, keepdims=True), out.min(-1, keepdims=True)
        sat = (mxo - mno) / np.maximum(mxo, 1e-3)
        out = Lo + (out - Lo) * (1 + vib * (1 - sat))
    out = np.clip(out, 0, 1)
    out8 = (out * 255.0 + 0.5).astype(np.uint8)
    rows = _band_mask(H, W, -60, 70)
    before = float((img[rows].max(-1) >= 250).mean())
    after = float((out8[rows].max(-1) >= 250).mean())
    near_b = float(((img[rows].max(-1) >= 225) & (img[rows].max(-1) < 250)).mean())
    gb = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)[rows]
    ga = cv2.cvtColor(out8, cv2.COLOR_BGR2GRAY)[rows]
    return out8, {"ev": round(ev, 2), "median_before": int(np.median(gb)), "median_after": int(np.median(ga)),
                  "dark_before": round(float((gb < 40).mean()), 4), "dark_after": round(float((ga < 40).mean()), 4),
                  "clipped_before": round(before, 4), "clipped_after": round(after, 4), "near_clip_before": round(near_b, 4),
                  "hi_knee": hi_knee, "hi_keep": hi_keep, "lo_knee": lo_knee, "lo_keep": lo_keep, "detail": detail, "vibrance": vib}


def find_faces(img, model_path, score=0.5):
    """등장방형에서 얼굴 상자 [(x, y, w, h, score)] (원본 px). 모델이 없으면 None.
    2026-11-16 실사진 82f7603b·cfb5229d: 원본 해상도(8192)·문턱 0.5 에서 찾은 4개 모두 사람(옆얼굴·칸막이 뒤 포함),
    0.35 로 내리면 1개 더 찾지만 거짓 4개(모니터·서랍·손·시계). 4096 으로 줄이면 칸막이 뒤 얼굴을 놓친다.
    옆으로 돌리거나 뒤통수만 보이는 사람은 못 찾을 수 있다(알아보기도 어렵다)"""
    if not model_path or not os.path.isfile(model_path) or not hasattr(cv2, "FaceDetectorYN"):
        return None
    H, W = img.shape[:2]
    Wd = min(8192, W)
    s = Wd / float(W)
    lat_hi, lat_lo = 45.0, -50.0
    r0 = int((90 - lat_hi) / 180.0 * H)
    r1 = int((90 - lat_lo) / 180.0 * H)
    band = img[r0:r1] if Wd == W else cv2.resize(img[r0:r1], (Wd, max(16, int(round((r1 - r0) * s)))), interpolation=cv2.INTER_AREA)
    pad = int(Wd * 0.04)
    band = np.hstack([band[:, -pad:], band, band[:, :pad]])            # 360° 끝에 걸친 얼굴
    bh, bw = band.shape[:2]
    det = cv2.FaceDetectorYN.create(model_path, "", (bw, bh), score, 0.3, 5000)
    det.setInputSize((bw, bh))
    _r, faces = det.detect(band)
    out = []
    if faces is None:
        return out
    for fc in faces:
        x, y, w, h, sc = float(fc[0]) - pad, float(fc[1]), float(fc[2]), float(fc[3]), float(fc[-1])
        if w < 4 or h < 4:
            continue
        cx = (x + w / 2) % Wd
        out.append(((cx - w / 2) / s, y / s + r0, w / s, h / s, sc))
    # 겹친 것(끝 이음에서 두 번 찾음) 정리
    keep = []
    for f in sorted(out, key=lambda q: -q[4]):
        if all(abs((f[0] + f[2] / 2) - (k[0] + k[2] / 2)) > 0.5 * k[2] or abs((f[1] + f[3] / 2) - (k[1] + k[3] / 2)) > 0.5 * k[3] for k in keep):
            keep.append(f)
    return keep


def blur_faces(img, faces, grow=1.45):
    H, W = img.shape[:2]
    for x, y, w, h, _sc in faces:
        cx, cy = x + w / 2, y + h / 2
        rw, rh = w * grow / 2, h * grow * 1.15 / 2
        x0, x1 = int(cx - rw - 4), int(cx + rw + 5)
        y0, y1 = max(0, int(cy - rh - 4)), min(H, int(cy + rh + 5))
        cols = np.arange(x0, x1) % W
        roi = img[y0:y1][:, cols]
        k = max(3, int(max(w, h) / 3) | 1)
        bl = cv2.GaussianBlur(cv2.resize(cv2.resize(roi, (max(2, roi.shape[1] // 8), max(2, roi.shape[0] // 8)), interpolation=cv2.INTER_AREA),
                                         (roi.shape[1], roi.shape[0]), interpolation=cv2.INTER_LINEAR), (k, k), 0)
        m = np.zeros(roi.shape[:2], np.float32)
        cv2.ellipse(m, (int(cx - x0), int(cy - y0)), (int(rw), int(rh)), 0, 0, 360, 1.0, -1)
        m = cv2.GaussianBlur(m, (0, 0), max(1.0, min(rw, rh) * 0.15))[..., None]
        img[y0:y1, cols] = (roi * (1 - m) + bl * m + 0.5).astype(np.uint8)
    return img


def enhance_spot(img, gains, opts, blur_on, model_path):
    info = {}
    sig = noise_sigma(img)
    if getattr(opts, "enhance_denoise", True):
        img, info["denoise"] = denoise(img, sig)
    else:
        info["denoise"] = {"noise_sigma": round(sig, 2), "luma": False, "chroma": False}
    wb = neutral_wb(img)
    g_all = np.array(wb, np.float32) * np.array(gains or [1, 1, 1], np.float32)
    if np.any(np.abs(g_all - 1) > 0.005):
        img = np.clip(img.astype(np.float32) * g_all[None, None, :] + 0.5, 0, 255).astype(np.uint8)
    info["wb_gain_bgr"] = [round(g, 4) for g in wb]
    info["match_gain_bgr"] = [round(g, 4) for g in (gains or [1, 1, 1])]
    if getattr(opts, "enhance_tone", True):
        img, info["tone"] = tone_map(img)
    if blur_on:
        faces = find_faces(img, model_path)
        if faces is None:
            info["faces"] = {"enabled": True, "applied": False, "reason": f"얼굴 모델이 없음 ({FACE_MODEL_NAME})"}
        else:
            img = blur_faces(img, faces)
            info["faces"] = {"enabled": True, "applied": True, "detector": "YuNet 2023mar (OpenCV FaceDetectorYN)", "count": len(faces)}
    else:
        info["faces"] = {"enabled": False, "applied": False}
    return img, info
