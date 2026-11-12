"""rgb.mp4 디코딩 프레임 ↔ odometry.csv 행 짝짓기 (2026-11-11)

앱(kgeoScan, Stray 계열) rgb.mp4 는 첫 패킷 PTS 가 -1 이다. 편집 목록이 그 패킷을 감추고 디코더(cv2·ffmpeg)는
둘째 패킷부터 내놓는다. 작업 영상 10개 모두 패킷 수 = odometry 행 수, 디코딩 = 하나 적음, 패킷 PTS 간격 = odometry
시각 간격이었다. 디코딩 순서 j 를 행 j 와 짝지으면 한 프레임(30 Hz 면 33 ms) 늦은 자세를 쓰게 된다. 메시 색·텍스처·
정사영상·굴착 조서 사진이 흐려지고 어긋난다(트렌치 시험 촬영: 스플랫 학습 PSNR +3.2 dB, 자세 회전 잔차 1.14° → 0.65°).

그래서 패킷 PTS 순서 = 행 번호로 보고, 디코딩된 프레임의 PTS 로 행을 찾는다.
  - PTS 로 못 찾으면 j + 감춰진 패킷 수
  - ffmpeg(imageio-ffmpeg) 이 없으면 예전처럼 j
GPU 워커 worker_gpu/splat_common.iter_video_rows 와 같은 규칙이다.
"""
import bisect
import functools
import os
import subprocess

import cv2


@functools.lru_cache(maxsize=8)
def _packet_pts_cached(path, mtime, size):
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None, None
    try:
        r = subprocess.run([exe, "-hide_banner", "-v", "error", "-i", path, "-map", "0:v:0",
                            "-c", "copy", "-f", "framecrc", "-"], capture_output=True, text=True, timeout=600)
    except Exception:
        return None, None
    tb, pts = None, []
    for ln in r.stdout.splitlines():
        if ln.startswith("#tb 0:"):
            a, b = ln.split(":", 1)[1].strip().split("/")
            tb = float(a) / float(b)
        elif ln and not ln.startswith("#"):
            p = ln.split(",")
            if len(p) > 2 and p[0].strip() == "0":
                try:
                    pts.append(int(p[2]))
                except ValueError:
                    pass
    return (tuple(sorted(pts)), tb) if pts and tb else (None, None)


def packet_pts(path):
    """영상 패킷 PTS(오름차순, 디코더가 감추는 것 포함)와 시간 기준(초/틱). ffmpeg 을 못 쓰면 (None, None)"""
    try:
        st = os.stat(path)
    except OSError:
        return None, None
    return _packet_pts_cached(os.path.abspath(path), st.st_mtime_ns, st.st_size)


def row_offset_info(path):
    """(감춰진 패킷 수, 패킷 수). ffmpeg 이 없으면 (0, None)"""
    pts, _ = packet_pts(path)
    if not pts:
        return 0, None
    return sum(1 for p in pts if p < 0), len(pts)


def iter_video_grabs(path, log=None):
    """rgb.mp4 를 grab() 하며 (odometry 행 번호, cap) 을 낸다. 그림이 필요하면 cap.retrieve() 를 부른다."""
    pts, tb = packet_pts(path)
    hidden = sum(1 for p in pts if p < 0) if pts else 0
    base = pts[hidden] if pts and hidden < len(pts) else 0
    if log:
        if pts:
            log(f"video rows: packets {len(pts)}, hidden before start {hidden} → frame row = packet PTS order")
        else:
            log("video rows: ffmpeg 없음 → decode order = row (예전 방식)")
    cap = cv2.VideoCapture(path)
    j = 0
    try:
        while cap.grab():
            r = j
            if pts:
                tick = int(round(cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0 / tb)) + base
                k = bisect.bisect_left(pts, tick)
                r = k if (k < len(pts) and pts[k] == tick) else j + hidden
            j += 1
            yield r, cap
    finally:
        cap.release()


def iter_video_rows(path, log=None):
    """rgb.mp4 를 디코딩하며 (odometry 행 번호, bgr) 를 낸다."""
    for r, cap in iter_video_grabs(path, log):
        ok, bgr = cap.retrieve()
        if not ok:
            break
        yield r, bgr
