r"""
kgeoScan 굴착 3D 기록 — 규정 서류·납품 파일 자동 작성 (docs/utility_contract.md v0.2 의 utilities.json → 산출물)

  python -I worker/utility_report.py --utilities <job>/out/utilities.json --job-dir <job> --out <dir>
         [--data <Stray 데이터셋 폴더>] [--title 사업명] [--surveyor 측량자] [--org 소속] [--stage "되메우기 전"]
         [--params '{"clear_min_mm": 300}'] [--no-video] [--no-photos]

  from utility_report import build_report          # worker/ 를 sys.path 에. numpy + cv2 (+ pyproj, PIL, laspy 있으면 씀)
  summary = build_report(utilities="utilities.json", job_dir="job", out_dir="out")

출력 (<out>/)
  report.html            A4 인쇄용 보고서(브라우저 → PDF 저장). 표지 · 개요·평면도 · 조서 총괄표 · 측점별 별표 38 ·
                         단면도 · 종단면도 · 이격·심도 검토 · 정확도 · 산출물·근거. 사진·그림은 모두 안에 넣는다(base64, 인라인 SVG).
  stations.csv           조서 총괄표와 같은 열 (UTF-8 BOM, 엑셀에서 바로 열림)
  utilities.dxf          R12 ASCII, UTM 52N(EPSG:32652). 종류별 레이어·색, 3D 중심선, 관 외곽, 측점·심도 글자, 굴착 경계, 이격
  utilities_tm.dxf       같은 내용을 조서 좌표계(GRS80 TM, 경도로 원점 자동 선택 — 보통 EPSG:5186 중부원점)로
  utilities.landxml      LandXML 1.2 PipeNetworks (관마다 PipeNetwork, 꺾임점마다 Struct, CircPipe 지름 mm) + PlanFeatures 3D 중심선
  utilities.geojson      LineString Z, EPSG:32652. 속성 = ArcGIS 필드(class, nominal_mm, top_depth_min/max/mean, slope_pct, ...)
  utilities_4326.geojson 같은 것을 경위도로 (RFC 7946)
  stations.geojson       측점 Point Z (EPSG:32652)
  submission.mp4         서울시 도로굴착 제출형 동영상: 소개 카드 → 촬영 영상(일시·위치·사업명·관 정보 자막, 미니맵, 관 위치 겹쳐
                         그리기) → 요약 카드. 1280×720. cv2.VideoWriter 로 쓰고, ffmpeg 이 있으면 H.264(+faststart)로 다시 압축
  photos/*.jpg           측점별 근경·원경·지거측량 기준점·관로 측량점 사진 (전자 보드판·측점 표시 포함)
  report.json            산출물 목록, 검사 결과(DXF 재해석·LandXML 구조 검사), 동영상 코덱

서식 근거 (공공측량 작업규정, 국토지리정보원 고시 제2025-2092호, 2025-04-23)
  별표 38 「노출관로 위치측량 조서」: 측점마다 한 쪽. 사업명 / 측량날짜·측점명 / 좌표(GRS80) X(N)·Y(E), 시설물종류, 재질, 관경,
    이격거리, 심도 / 사진 근경·원경·지거측량 기준점·관로 측량점 / "* 보드판을 활용한 사진촬영(휴대폰 어플 사용가능)"
    (law.go.kr 첨부 PDF 본문에서 확인)
  제184조③ 평면위치는 관로 중심선, 깊이는 지표면에서 시설물 상단까지 · ④ 간격 20 m 이하, 교차·분기·곡선 등은 따로
  제185조② 이격거리·깊이를 mm 단위까지 실측, 곡선·관종·관경 변경점은 별도 측정·근경/원경 사진, 사진은 별표 38 에 정리
  제186조③ 위치측량 허용오차 10 cm, 단위 m, 평면좌표 소수 셋째자리, 높이 소수 둘째자리

판단 (계약에 없는 것)
  - 지거측량 기준점: utilities.json 에 control_points 가 있으면 가장 가까운 것을 쓰고, 없으면 굴착 경계(원지반)에서 관 중심까지
    가장 가까운 점을 임시 기준으로 쓴다(보고서에 "임시" 표시). 경계석 같은 영구 기준점은 앱에서 지정하도록 계약 보강을 제안.
  - 측점이 없으면(엔진 v0.1) 여기서 만든다: 끝점, 20 m 이하 정규 측점(짧은 굴착은 관마다 최소 3점), 굴곡(≥12°), 교차.
  - clearances 가 없으면 중심선과 반지름으로 계산(관 겉면 사이 3D 최소 거리). 있으면 엔진 값을 쓴다.
  - 최소 토피·이격 기준은 참고 기본값이다(--params 로 관리기관 기준을 넣는다).
  - 케이블·다발 중심선: 엔진은 지금 윗면을 쓴다 → 그대로 따른다. 계약에 centerline_ref("axis"|"top")가 있으면 그것을 따른다.
  - 카메라 자세 규약: result.json fusion.convention 이 있으면 쓰고, 없으면 깊이 재투영으로 cv/arkit 을 고른다
    (kgeoScan 앱 = cv, 원래 Stray 앱 = arkit). 사진·동영상의 측점 위치는 깊이 지도로 가려짐을 검사한다.
  - 사진·관 겹쳐 그리기에 쓰는 로컬↔UTM 변환은 centerline ↔ centerline_local 쌍으로 맞추고(엔진과 같은 변환), 없으면 georef.
  - 시설물이 하나도 없으면 굴착만 기록하고 "시설물 없음" 중대 경고를 낸다.

동영상 코덱 (이 PC, 2026-11-10 확인)
  OpenCV 5.0 FFMPEG 백엔드는 openh264 DLL 이 없어 avc1 을 못 연다 → 자동으로 Media Foundation(MSMF) 이 H.264 Baseline 을 만든다
  (비트레이트 ≈ 1 bit/화소·조절 불가, moov 뒤). ffmpeg(.venv_gpu 의 imageio-ffmpeg 7.1 또는 PATH/KGEO_FFMPEG)이 있으면
  libx264 CRF 24 High + faststart 로 다시 압축(38 s ≈ 3.7 MB). 없으면 MSMF 출력을 15 fps 로 쓰고 moov 를 앞으로 옮긴다.
  mp4v 는 마지막 수단(브라우저 재생 안 됨).

로그는 ASCII 만 쓴다(cp949 콘솔). 산출 문서는 UTF-8.
"""
import argparse
import base64
import csv
import datetime as dt
import glob
import html
import io
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

import cv2
import numpy as np

try:
    from pyproj import Transformer
except Exception:          # pragma: no cover
    Transformer = None
try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:          # pragma: no cover
    Image = ImageDraw = ImageFont = None

VERSION = "0.1"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
KST = dt.timezone(dt.timedelta(hours=9))

# ─────────────────────────── 시설물 종류 (색은 기획서·뷰어와 같게) ───────────────────────────
# min_cover: 최소 토피 참고 기본값(m, 차도 가정). 법정 기준은 관리기관·관종마다 다르므로 --params '{"min_cover": {...}}' 로 바꾼다.
CLASS = {
    "water":   dict(ko="상수도", short="상수", color="#2563eb", aci=5, en="WATER", min_cover=1.2),
    "sewer":   dict(ko="하수도", short="하수", color="#16a34a", aci=3, en="SEWER", min_cover=1.0),
    "gas":     dict(ko="가스", short="가스", color="#ca8a04", aci=2, en="GAS", min_cover=1.2),
    "power":   dict(ko="전력", short="전력", color="#dc2626", aci=1, en="POWER", min_cover=1.0),
    "telecom": dict(ko="통신", short="통신", color="#ea580c", aci=30, en="TELECOM", min_cover=1.0),
    "heat":    dict(ko="난방(열수송)", short="난방", color="#9333ea", aci=6, en="HEAT", min_cover=1.2),
    "unknown": dict(ko="미확인", short="미확인", color="#6b7280", aci=8, en="UNKNOWN", min_cover=None),
}
KIND_KO = {"pipe": "관", "cable": "케이블", "conduit": "관로", "bundle": "케이블 다발", "unknown": "미상"}
ST_KIND_KO = {"regular": "정규", "bend": "굴곡", "change": "관경·관종 변화", "cross": "교차", "end": "끝점", "branch": "분기"}
ST_PRIORITY = {"end": 5, "cross": 4, "branch": 4, "change": 3, "bend": 2, "regular": 1}
PHOTO_TYPES = [("near", "근 경"), ("far", "원 경"), ("ref", "지거측량 기준점"), ("pt", "관로 측량점")]
IPHONE_NAMES = {"iPhone13,3": "iPhone 12 Pro", "iPhone13,4": "iPhone 12 Pro Max", "iPhone14,2": "iPhone 13 Pro",
                "iPhone14,3": "iPhone 13 Pro Max", "iPhone15,2": "iPhone 14 Pro", "iPhone15,3": "iPhone 14 Pro Max",
                "iPhone16,1": "iPhone 15 Pro", "iPhone16,2": "iPhone 15 Pro Max", "iPhone17,1": "iPhone 16 Pro", "iPhone17,2": "iPhone 16 Pro Max"}
TM_NAME = {5185: "GRS80 TM 서부원점", 5186: "GRS80 TM 중부원점", 5187: "GRS80 TM 동부원점", 5188: "GRS80 TM 동해원점"}

DEFAULTS = dict(
    station_step_m=20.0,     # 제184조④ 20 m 이하
    min_stations=3,          # 짧은 굴착에서도 관마다 이만큼 (끝점 2 + 가운데)
    bend_deg=12.0,           # 이보다 크게 꺾이면 굴곡 측점
    merge_m=0.25,            # 같은 관에서 이보다 가까운 측점은 하나로
    clear_min_mm=300,        # 관 사이 최소 이격 참고값 (가스배관-다른 시설물 0.3 m 등)
    clear_report_mm=1000,    # 이보다 가까운 쌍은 표에 싣는다
    min_cover=None,          # {"water": 1.2, ...} 로 CLASS 기본값을 덮어쓴다
    conf_warn=0.6,
    abs_tol_m=0.10,          # 제186조③ 허용오차
    photo_w=720, photo_h=480, photo_q=80,     # 별표 38 사진 칸(약 91×61 mm)과 같은 비율
    video_w=1280, video_h=720, video_fps=30, video_max_s=180.0, video_ar=True, intro_s=4.0, outro_s=4.0,
    tm_epsg=None,            # None → 경도로 자동
    slab_m=0.03,             # 단면에 그릴 점군 두께(±)
    page_rows=14,            # 총괄표 한 쪽 줄 수 (가로 A4)
)


def _log_default(m):
    print(str(m).encode("ascii", "replace").decode(), flush=True)


def esc(s):
    return html.escape("" if s is None else str(s), quote=True)


def fnum(v, nd=3, dash="—"):
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return dash
    return f"{v:,.{nd}f}"


def cls_info(c):
    return CLASS.get(c or "unknown", CLASS["unknown"])


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def hex_bgr(h):
    r, g, b = hex_rgb(h)
    return (b, g, r)


# ═══════════════════════════════════════════ 1) 글자 (PIL, 한글) ═══════════════════════════════════════════
FONT_FILES = {
    False: [r"C:\Windows\Fonts\malgun.ttf", "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
            "/System/Library/Fonts/AppleSDGothicNeo.ttc"],
    True: [r"C:\Windows\Fonts\malgunbd.ttf", "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
           "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
           "/System/Library/Fonts/AppleSDGothicNeo.ttc"],
}
_FONTS = {}
_SPRITES = {}


def font(size, bold=False):
    key = (int(size), bool(bold))
    if key in _FONTS:
        return _FONTS[key]
    f = None
    if ImageFont is not None:
        for p in FONT_FILES[bold] + FONT_FILES[False]:
            if os.path.exists(p):
                try:
                    f = ImageFont.truetype(p, int(size))
                    break
                except Exception:
                    pass
        if f is None:
            try:
                f = ImageFont.load_default()
            except Exception:
                f = None
    _FONTS[key] = f
    return f


def has_hangul_font():
    return any(os.path.exists(p) for p in FONT_FILES[False]) and ImageFont is not None


def sprite(text, size, color=(255, 255, 255), bold=False, bg=None, pad=(0, 0), radius=0, stroke=0, stroke_color=(0, 0, 0)):
    """글자 → RGBA 배열 (캐시). color/bg 는 RGB(A)."""
    key = (text, int(size), tuple(color), bold, None if bg is None else tuple(bg), tuple(pad), radius, stroke, tuple(stroke_color))
    if key in _SPRITES:
        return _SPRITES[key]
    f = font(size, bold)
    if f is None or Image is None:            # PIL 없음: ASCII 만
        t = text.encode("ascii", "replace").decode()
        sc = size / 30.0
        (tw, th), base = cv2.getTextSize(t, cv2.FONT_HERSHEY_SIMPLEX, sc, 1)
        w, h = tw + 2 * pad[0], th + base + 2 * pad[1]
        img = np.zeros((h, w, 4), np.uint8)
        if bg is not None:
            img[:] = (*bg[:3], bg[3] if len(bg) > 3 else 255)
        cv2.putText(img, t, (pad[0], pad[1] + th), cv2.FONT_HERSHEY_SIMPLEX, sc, (*color[:3], 255), 1, cv2.LINE_AA)
        _SPRITES[key] = img
        return img
    x0, y0, x1, y1 = f.getbbox(text, stroke_width=stroke)
    asc, desc = f.getmetrics()
    w = max(1, x1 - x0) + 2 * pad[0] + 2 * stroke
    h = asc + desc + 2 * pad[1] + 2 * stroke
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if bg is not None:
        bgc = tuple(bg) if len(bg) == 4 else (*bg, 255)
        if radius:
            d.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=bgc)
        else:
            d.rectangle([0, 0, w - 1, h - 1], fill=bgc)
    d.text((pad[0] - x0 + stroke, pad[1] + stroke), text, font=f, fill=(*color[:3], 255), stroke_width=stroke,
           stroke_fill=(*stroke_color[:3], 255))
    arr = np.array(im)
    _SPRITES[key] = arr
    return arr


def blit(dst_bgr, rgba, x, y, alpha=1.0):
    """RGBA 그림을 BGR 영상의 (x, y) 에 알파 합성 (잘림 처리)."""
    h, w = rgba.shape[:2]
    H, W = dst_bgr.shape[:2]
    x, y = int(round(x)), int(round(y))
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x1 <= x0 or y1 <= y0:
        return
    s = rgba[y0 - y:y1 - y, x0 - x:x1 - x]
    a = (s[..., 3:4].astype(np.float32) / 255.0) * alpha
    roi = dst_bgr[y0:y1, x0:x1].astype(np.float32)
    roi = roi * (1 - a) + s[..., 2::-1].astype(np.float32) * a
    dst_bgr[y0:y1, x0:x1] = roi.astype(np.uint8)


def wrap_text(text, size, max_w, bold=False):
    f = font(size, bold)
    if f is None:
        return [text]
    words, lines, cur = text.split(" "), [], ""
    for wd in words:
        t = (cur + " " + wd).strip()
        if f.getlength(t) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    out = []
    for ln in lines:                        # 띄어쓰기 없는 긴 줄은 글자 단위로
        while f.getlength(ln) > max_w and len(ln) > 1:
            k = len(ln)
            while k > 1 and f.getlength(ln[:k]) > max_w:
                k -= 1
            out.append(ln[:k])
            ln = ln[k:]
        out.append(ln)
    return out


# ═══════════════════════════════════════════ 2) 좌표 ═══════════════════════════════════════════
class LocalFrame:
    """UTM(E, N, H) ↔ 로컬(ARKit, Y 위).  [e, −n] = R(θ)·[x, z] + t,  h = y + c  (process_scan.py 와 같은 꼴)."""

    def __init__(self, theta, t, c, source, rms=None):
        self.theta, self.t, self.c, self.source, self.rms = float(theta), np.asarray(t, float), float(c), source, rms
        self.cs, self.sn = math.cos(self.theta), math.sin(self.theta)

    @classmethod
    def from_georef(cls, gr):
        lon, lat = float(gr["lon"]), float(gr["lat"])
        elev = float(gr.get("elev", 0.0) or 0.0)
        heading = float(gr.get("heading", gr.get("heading_deg", 0.0)) or 0.0)
        e0, n0 = Transformer.from_crs("EPSG:4326", "EPSG:32652", always_xy=True).transform(lon, lat)
        return cls(math.radians(heading), [e0, -n0], elev, "georef")

    @classmethod
    def fit(cls, local, utm):
        A = np.asarray(local, float)[:, [0, 2]]
        U = np.asarray(utm, float)
        B = np.column_stack([U[:, 0], -U[:, 1]])
        ma, mb = A.mean(0), B.mean(0)
        A0, B0 = A - ma, B - mb
        th = math.atan2(float(np.sum(A0[:, 0] * B0[:, 1] - A0[:, 1] * B0[:, 0])), float(np.sum(A0[:, 0] * B0[:, 0] + A0[:, 1] * B0[:, 1])))
        R = np.array([[math.cos(th), -math.sin(th)], [math.sin(th), math.cos(th)]])
        t = mb - R @ ma
        c = float(np.mean(U[:, 2] - np.asarray(local, float)[:, 1]))
        fr = cls(th, t, c, "fit")
        fr.rms = float(np.sqrt(np.mean(np.sum((fr.to_utm(local) - U) ** 2, 1))))
        return fr

    def to_utm(self, L):
        L = np.asarray(L, float).reshape(-1, 3)
        x, y, z = L[:, 0], L[:, 1], L[:, 2]
        e = self.cs * x - self.sn * z + self.t[0]
        mn = self.sn * x + self.cs * z + self.t[1]
        return np.column_stack([e, -mn, y + self.c])

    def to_local(self, U):
        U = np.asarray(U, float).reshape(-1, 3)
        e, mn = U[:, 0] - self.t[0], -U[:, 1] - self.t[1]
        x = self.cs * e + self.sn * mn
        z = -self.sn * e + self.cs * mn
        return np.column_stack([x, U[:, 2] - self.c, z])

    def dir_to_utm(self, D):
        D = np.asarray(D, float).reshape(-1, 3)
        x, y, z = D[:, 0], D[:, 1], D[:, 2]
        return np.column_stack([self.cs * x - self.sn * z, -(self.sn * x + self.cs * z), y])


def tm_epsg_for(lon):
    return 5185 if lon < 126 else 5186 if lon < 128 else 5187 if lon < 130 else 5188


class Geo:
    def __init__(self, center_utm, tm_epsg=None):
        self.ok = Transformer is not None
        self.lon = self.lat = None
        self.tm_epsg = tm_epsg
        if self.ok:
            self._wgs = Transformer.from_crs("EPSG:32652", "EPSG:4326", always_xy=True)
            self.lon, self.lat = self._wgs.transform(float(center_utm[0]), float(center_utm[1]))
            if not self.tm_epsg:
                self.tm_epsg = tm_epsg_for(self.lon)
            self._tm = Transformer.from_crs("EPSG:32652", f"EPSG:{self.tm_epsg}", always_xy=True)

    def tm(self, E, N):
        """→ (X=북, Y=동) GRS80 TM. 조서 표기 순서."""
        if not self.ok:
            return np.asarray(N, float), np.asarray(E, float)
        y, x = self._tm.transform(np.asarray(E, float), np.asarray(N, float))
        return np.asarray(x), np.asarray(y)

    def wgs(self, E, N):
        if not self.ok:
            return None, None
        return self._wgs.transform(np.asarray(E, float), np.asarray(N, float))


# ═══════════════════════════════════════════ 3) 입력 찾기 ═══════════════════════════════════════════
def _read_json(p):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def find_inputs(utilities_path, job_dir=None, data_dir=None):
    udir = os.path.dirname(os.path.abspath(utilities_path))
    jd = os.path.abspath(job_dir) if job_dir else os.path.dirname(udir)
    inf = dict(job_dir=jd, utilities=os.path.abspath(utilities_path))

    def first(paths):
        for p in paths:
            if p and os.path.exists(p):
                return p
        return None

    rp = first([os.path.join(jd, "out", "result.json"), os.path.join(jd, "result.json"), os.path.join(udir, "result.json")])
    jp = first([os.path.join(jd, "job.json"), os.path.join(jd, "out", "job.json"), os.path.join(udir, "job.json")])
    inf["result"] = _read_json(rp) if rp else None
    inf["job"] = _read_json(jp) if jp else None
    gr = None
    for src in (inf["job"], inf["result"]):
        if isinstance(src, dict) and isinstance(src.get("georef"), dict) and "lon" in src["georef"]:
            gr = src["georef"]
            break
    inf["georef"] = gr
    dd = None
    if data_dir and os.path.isdir(data_dir):
        dd = os.path.abspath(data_dir)
    if dd is None and isinstance(inf["result"], dict):
        cand = (inf["result"].get("fusion") or {}).get("dataset")
        if cand and os.path.isdir(cand):
            dd = cand
    if dd is None:
        for base in (jd, udir):
            if not os.path.isdir(base):
                continue
            for root, dirs, files in os.walk(base):
                if root[len(base):].count(os.sep) > 4:
                    dirs[:] = []
                    continue
                if "odometry.csv" in files or os.path.exists(os.path.join(root, "hires", "poses.json")):
                    dd = root
                    break
            if dd:
                break
    inf["data"] = dd
    inf["meta"] = _read_json(os.path.join(dd, "meta.json")) if dd else None
    inf["las"] = first([os.path.join(udir, "scan.las"), os.path.join(jd, "out", "scan.las"), os.path.join(jd, "scan.las")])
    inf["ortho"] = first([os.path.join(udir, "ortho", "ortho.json"), os.path.join(jd, "out", "ortho", "ortho.json")])
    inf["thumb"] = first([os.path.join(udir, "thumb.jpg"), os.path.join(jd, "out", "thumb.jpg"),
                          os.path.join(dd, "thumb.jpg") if dd else None])
    return inf


# ═══════════════════════════════════════════ 4) 기하 도우미 ═══════════════════════════════════════════
def chainage(P2):
    P2 = np.asarray(P2, float)
    if len(P2) < 2:
        return np.zeros(len(P2))
    return np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P2, axis=0), axis=1))])


def interp_poly(P, cum, s):
    s = float(np.clip(s, 0, cum[-1]))
    i = int(np.clip(np.searchsorted(cum, s) - 1, 0, len(cum) - 2))
    seg = cum[i + 1] - cum[i]
    f = 0.0 if seg <= 1e-12 else (s - cum[i]) / seg
    return P[i] + f * (P[i + 1] - P[i]), i


def project_poly(P2, cum, q):
    """평면 점 q 를 꺾은선에 투영 → (추가거리, 거리)."""
    best = (0.0, 1e18)
    for i in range(len(P2) - 1):
        a, b = P2[i], P2[i + 1]
        d = b - a
        L2 = float(d @ d)
        f = 0.0 if L2 < 1e-12 else float(np.clip((q - a) @ d / L2, 0, 1))
        p = a + f * d
        dist = float(np.linalg.norm(q - p))
        if dist < best[1]:
            best = (cum[i] + f * math.sqrt(L2), dist)
    return best


def dp_simplify(P, tol):
    P = np.asarray(P, float)
    if len(P) <= 2:
        return np.arange(len(P))
    keep = np.zeros(len(P), bool)
    keep[0] = keep[-1] = True
    stack = [(0, len(P) - 1)]
    while stack:
        i, j = stack.pop()
        a, b = P[i], P[j]
        d = b - a
        L = np.linalg.norm(d)
        seg = P[i + 1:j]
        if len(seg) == 0:
            continue
        if L < 1e-9:
            dist = np.linalg.norm(seg - a, axis=1)
        else:
            dist = np.linalg.norm(np.cross(seg - a, d / L), axis=1) if P.shape[1] == 3 else np.abs(np.cross(seg - a, d / L))
        k = int(np.argmax(dist))
        if dist[k] > tol:
            m = i + 1 + k
            keep[m] = True
            stack += [(i, m), (m, j)]
    return np.flatnonzero(keep)


def seg_intersect(p1, p2, q1, q2):
    d1, d2 = p2 - p1, q2 - q1
    den = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(den) < 1e-12:
        return None
    w = q1 - p1
    t = (w[0] * d2[1] - w[1] * d2[0]) / den
    u = (w[0] * d1[1] - w[1] * d1[0]) / den
    if 0 <= t <= 1 and 0 <= u <= 1:
        return t, u
    return None


def resample_poly(P, step):
    P = np.asarray(P, float)
    cum = chainage(P[:, :2]) if P.shape[1] >= 2 else chainage(P)
    cum3 = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    L = cum3[-1]
    n = max(2, int(math.ceil(L / step)) + 1)
    out = np.array([interp_poly(P, cum3, s)[0] for s in np.linspace(0, L, n)])
    return out


# ═══════════════════════════════════════════ 5) 시설물·측점 ═══════════════════════════════════════════
class Util:
    def __init__(self, d, frame, z_ref, order, cl_ref=None):
        self.d, self.order = d, order
        self.id = d.get("id", f"U{order + 1}")
        self.kind = d.get("kind", "unknown")
        self.cls = d.get("class", "unknown") if d.get("class") in CLASS else "unknown"
        self.info = cls_info(self.cls)
        self.cl = np.asarray(d["centerline"], float).reshape(-1, 3)
        self.diameter_mm = d.get("diameter_mm")
        self.nominal_mm = d.get("nominal_mm") or self.diameter_mm
        w_mm = d.get("width_mm") if self.kind in ("bundle", "cable") else None
        self.r = float((w_mm or self.diameter_mm or 50) / 2000.0)
        # 엔진 규약(현재): 관(pipe/conduit) 중심선 = 축, 케이블·다발 중심선 = 윗면.
        # 계약에 centerline_ref ("axis" | "top") 가 관마다 또는 맨 위에 있으면 그것을 따른다 (뷰어는 모두 축으로 봄 — 통일 요청 중)
        ref = d.get("centerline_ref") or cl_ref
        self.top_is_cl = (ref == "top") if ref in ("axis", "top") else self.kind in ("bundle", "cable")
        self.top_z = self.cl[:, 2] if self.top_is_cl else self.cl[:, 2] + self.r
        self.center_z = self.cl[:, 2] - self.r if self.top_is_cl else self.cl[:, 2]
        self.cum = chainage(self.cl[:, :2])
        self.length2d = float(self.cum[-1]) if len(self.cum) else 0.0
        self.length = float(d.get("length_m") or np.sum(np.linalg.norm(np.diff(self.cl, axis=0), axis=1)))
        self.material = d.get("material") or ""
        # 원지반 높이 (UTM): ground_local_z(로컬 y) → h = y + c; 없으면 z_ref; 그것도 없으면 평균 깊이로 역산
        gz = None
        glz = d.get("ground_local_z")
        if glz is not None and frame is not None and len(glz) == len(self.cl):
            gz = np.asarray(glz, float) + frame.c
        elif glz is not None and frame is not None and len(glz) >= 2:
            gz = np.interp(np.linspace(0, 1, len(self.cl)), np.linspace(0, 1, len(glz)), np.asarray(glz, float) + frame.c)
        if gz is None and z_ref is not None:
            gz = np.full(len(self.cl), float(z_ref))
            self.ground_src = "z_ref"
        elif gz is None:
            md = (d.get("top_depth_m") or {}).get("mean", 1.0)
            gz = self.top_z + md
            self.ground_src = "mean_depth"
        else:
            self.ground_src = "ground_local_z"
        self.ground_z = gz
        self.depth = self.ground_z - self.top_z
        td = d.get("top_depth_m") or {}
        self.depth_min = td.get("min", float(np.min(self.depth)))
        self.depth_max = td.get("max", float(np.max(self.depth)))
        self.depth_mean = td.get("mean", float(np.mean(self.depth)))
        self.local = None
        if d.get("centerline_local") is not None:
            self.local = np.asarray(d["centerline_local"], float).reshape(-1, 3)
        elif frame is not None:
            self.local = frame.to_local(self.cl)

    @property
    def label(self):
        return f"{self.id} {self.info['short']}"

    def dia_text(self, short=False):
        if self.kind in ("bundle", "cable"):
            w = self.d.get("width_mm") or self.diameter_mm
            n = self.d.get("count")
            if self.kind == "bundle":
                return f"폭 {w} mm" + (f" ({n}가닥)" if n and not short else "")
            return f"Ø{self.diameter_mm}" if self.diameter_mm else "—"
        return f"Ø{self.nominal_mm}" if self.nominal_mm else "—"

    def type_text(self):
        k = KIND_KO.get(self.kind, self.kind)
        return f"{self.info['ko']} {k}" if self.cls != "unknown" else f"미확인 {k}"

    def at(self, s):
        p, i = interp_poly(self.cl, self.cum, s)
        tz, _ = interp_poly(np.column_stack([self.top_z, self.ground_z, self.center_z]), self.cum, s)
        d2 = self.cl[i + 1, :2] - self.cl[i, :2]
        n = np.linalg.norm(d2)
        tan = d2 / n if n > 1e-9 else np.array([1.0, 0.0])
        return dict(xy=p[:2], top=float(tz[0]), ground=float(tz[1]), center=float(tz[2]), tan=tan, seg=i)


def build_utils(res, frame):
    z_ref = (res.get("ground") or {}).get("z_ref")
    return [Util(u, frame, z_ref, i, res.get("centerline_ref")) for i, u in enumerate(res.get("utilities") or [])
            if len(u.get("centerline") or []) >= 2]


def compute_clearances(utils, res, prm):
    """관 겉면 사이 3D 최소 거리. 엔진 clearances 가 있으면 그 값(min_mm)을 우선."""
    given = {}
    for c in res.get("clearances") or []:
        given[tuple(sorted((c.get("a"), c.get("b"))))] = c
    samples = {}
    for u in utils:
        L = max(u.length, 0.01)
        step = max(0.02, L / 1500)
        C = np.column_stack([u.cl[:, :2], u.center_z])
        samples[u.id] = resample_poly(C, step)
    out = []
    for i in range(len(utils)):
        for j in range(i + 1, len(utils)):
            a, b = utils[i], utils[j]
            A, B = samples[a.id], samples[b.id]
            best = (1e18, None, None)
            for k in range(0, len(A), 400):
                D = np.linalg.norm(A[k:k + 400, None, :] - B[None, :, :], axis=2)
                m = np.unravel_index(np.argmin(D), D.shape)
                if D[m] < best[0]:
                    best = (float(D[m]), A[k + m[0]], B[m[1]])
            gap = best[0] - a.r - b.r
            key = tuple(sorted((a.id, b.id)))
            src = "computed"
            if key in given and given[key].get("min_mm") is not None:
                gap_mm = float(given[key]["min_mm"])
                src = "engine"
            else:
                gap_mm = gap * 1000
            pa, pb = best[1], best[2]
            # 겉면 위의 가장 가까운 두 점
            v = pb - pa
            nv = np.linalg.norm(v)
            if nv > 1e-9:
                sa, sb = pa + v / nv * a.r, pb - v / nv * b.r
            else:
                sa = sb = pa
            at = given.get(key, {}).get("at_utm") or ((sa + sb) / 2).tolist()
            if gap_mm <= prm["clear_report_mm"]:
                out.append(dict(a=a.id, b=b.id, min_mm=round(gap_mm), at_utm=[float(x) for x in at], pa=sa, pb=sb, source=src,
                                crossing=bool(abs(v[2]) > 0.7 * nv) if nv > 1e-9 else False))
    out.sort(key=lambda c: c["min_mm"])
    return out


def build_stations(utils, res, prm, controls):
    by_id = {u.id: u for u in utils}
    raw = []
    given = res.get("stations")
    if given:
        for g in given:
            u = by_id.get(g.get("utility_id"))
            if u is None or g.get("xyz_utm") is None:
                continue
            xyz = np.asarray(g["xyz_utm"], float)
            s = g.get("station_m")
            if s is None:
                s = project_poly(u.cl[:, :2], u.cum, xyz[:2])[0]
            raw.append(dict(u=u, s=float(np.clip(s, 0, u.length2d)), kind=g.get("kind", "regular"),
                            depth_given=g.get("top_depth_m"), source="engine"))
        src = "engine"
    else:
        src = "report"
        step = prm["station_step_m"]
        for u in utils:
            L = u.length2d
            cand = [(0.0, "end"), (L, "end")]
            n = max(1, int(math.ceil(L / step)))
            cand += [(L * k / n, "regular") for k in range(1, n)]
            if n + 1 < prm["min_stations"] and L > 0.6:
                m = prm["min_stations"] - 1
                cand += [(L * k / m, "regular") for k in range(1, m)]
            idx = dp_simplify(u.cl[:, :2], 0.03)
            for a, b, c in zip(idx[:-2], idx[1:-1], idx[2:]):
                v1, v2 = u.cl[b, :2] - u.cl[a, :2], u.cl[c, :2] - u.cl[b, :2]
                ang = math.degrees(math.acos(np.clip(v1 @ v2 / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-12), -1, 1)))
                if ang >= prm["bend_deg"]:
                    cand.append((float(u.cum[b]), "bend"))
            for s, k in cand:
                raw.append(dict(u=u, s=float(s), kind=k, depth_given=None, source="report"))
        # 교차 (평면에서 두 중심선이 만나는 곳) — 두 관 모두에 측점
        for i in range(len(utils)):
            for j in range(i + 1, len(utils)):
                a, b = utils[i], utils[j]
                for p in range(len(a.cl) - 1):
                    for q in range(len(b.cl) - 1):
                        r = seg_intersect(a.cl[p, :2], a.cl[p + 1, :2], b.cl[q, :2], b.cl[q + 1, :2])
                        if r:
                            sa = a.cum[p] + r[0] * (a.cum[p + 1] - a.cum[p])
                            sb = b.cum[q] + r[1] * (b.cum[q + 1] - b.cum[q])
                            raw.append(dict(u=a, s=float(sa), kind="cross", depth_given=None, source="report", other=b.id))
                            raw.append(dict(u=b, s=float(sb), kind="cross", depth_given=None, source="report", other=a.id))
    # 같은 관의 가까운 측점 합치기 (우선순위 높은 쪽)
    merged = []
    for u in utils:
        rs = sorted([r for r in raw if r["u"] is u], key=lambda r: r["s"])
        keep = []
        for r in rs:
            near = abs(r["s"] - keep[-1]["s"]) if keep else 1e9
            if keep and r["kind"] == "cross" and keep[-1]["kind"] == "cross" and near >= 0.08:
                keep.append(r)          # 서로 다른 관과의 교차는 가까워도 따로 (제184조④ 교차 지점마다)
                continue
            if keep and near < prm["merge_m"]:
                if ST_PRIORITY.get(r["kind"], 0) > ST_PRIORITY.get(keep[-1]["kind"], 0):
                    if keep[-1]["kind"] == "end" or r["kind"] == "end":
                        r = dict(r, s=keep[-1]["s"] if keep[-1]["kind"] == "end" else r["s"])
                    keep[-1] = r
                continue
            keep.append(r)
        merged += keep
    stations = []
    for k, r in enumerate(merged):
        u = r["u"]
        g = u.at(r["s"])
        depth = float(r["depth_given"]) if r.get("depth_given") is not None else g["ground"] - g["top"]
        ground = g["top"] + depth
        st = dict(no=k + 1, name=f"No.{k + 1}", u=u, s=r["s"], kind=r["kind"], source=r["source"], xy=g["xy"], top=g["top"],
                  center=g["center"], ground=ground, depth=depth, tan=g["tan"], other=r.get("other"))
        st["sta"] = f"{u.id} STA {int(r['s'] // 1000)}+{r['s'] % 1000:07.3f}"
        st["ref"] = reference_point(st, res, controls)
        stations.append(st)
    return stations, src


def reference_point(st, res, controls):
    """지거측량 기준점 → dict(xyz, label, temp, offset_m)."""
    q = st["xy"]
    if controls:
        best = min(controls, key=lambda c: np.hypot(c["xyz"][0] - q[0], c["xyz"][1] - q[1]))
        d = float(np.hypot(best["xyz"][0] - q[0], best["xyz"][1] - q[1]))
        if d < 15:
            return dict(xyz=np.asarray(best["xyz"], float), label=best.get("id", "기준점"), temp=False, offset_m=d,
                        desc=best.get("desc") or "기준 표식")
    ol = ((res.get("trench") or {}).get("outline"))
    if ol and len(ol) >= 3:
        O = np.asarray(ol, float)
        best = (1e18, None)
        for i in range(len(O) - 1):
            a, b = O[i, :2], O[i + 1, :2]
            dv = b - a
            L2 = float(dv @ dv)
            f = 0.0 if L2 < 1e-12 else float(np.clip((q - a) @ dv / L2, 0, 1))
            p = a + f * dv
            z = O[i, 2] + f * (O[i + 1, 2] - O[i, 2])
            dd = float(np.linalg.norm(q - p))
            if dd < best[0]:
                best = (dd, np.array([p[0], p[1], z]))
        return dict(xyz=best[1], label="R" + str(st["no"]), temp=True, offset_m=best[0], desc="굴착 경계(원지반) 임시 기준")
    return dict(xyz=np.array([q[0], q[1], st["ground"]]), label="—", temp=True, offset_m=None, desc="기준점 없음")


def section_hits(utils, st):
    """측점 단면(관 진행 방향에 직각인 연직면)과 다른 관들이 만나는 곳 → [(u, b, z_center)]."""
    c, t = st["xy"], st["tan"]
    n = np.array([-t[1], t[0]])
    hits = [(st["u"], 0.0, st["center"])]
    for u in utils:
        if u is st["u"]:
            continue
        P = u.cl[:, :2]
        s = (P - c) @ t
        b = (P - c) @ n
        zc = u.center_z
        found = None
        for i in range(len(P) - 1):
            if s[i] == 0 or s[i] * s[i + 1] < 0:
                f = 0.0 if s[i] == s[i + 1] else s[i] / (s[i] - s[i + 1])
                bb = b[i] + f * (b[i + 1] - b[i])
                zz = zc[i] + f * (zc[i + 1] - zc[i])
                if found is None or abs(bb) < abs(found[0]):
                    found = (bb, zz)
        if found is None:      # 끝점이 단면 바로 옆이면
            k = int(np.argmin(np.abs(s)))
            if abs(s[k]) < max(0.15, 2 * u.r):
                found = (b[k], zc[k])
        if found is not None and abs(found[0]) < 3.0:
            hits.append((u, float(found[0]), float(found[1])))
    return hits


def section_gaps(hits):
    """단면 안 관 겉면 사이 거리 (mm) → [(ua, ub, gap_mm, pa, pb)] (pa/pb = (b, z) 단면 좌표)."""
    out = []
    for i in range(len(hits)):
        for j in range(i + 1, len(hits)):
            ua, ba, za = hits[i]
            ub, bb, zb = hits[j]
            v = np.array([bb - ba, zb - za])
            d = float(np.linalg.norm(v))
            gap = d - ua.r - ub.r
            if d > 1e-9:
                pa = np.array([ba, za]) + v / d * ua.r
                pb = np.array([bb, zb]) - v / d * ub.r
            else:
                pa = pb = np.array([ba, za])
            out.append((ua, ub, gap * 1000, pa, pb))
    return out


# 엔진 quality.warnings 코드 → 조서 문구 (뷰어 utility.html 의 QWARN 과 같은 내용). "코드:N" 의 N 은 {n} 자리에 들어간다
QWARN_KO = {
    "low_coverage": "굴착 면 촬영이 부족함", "no_trench": "굴착을 찾지 못함", "rim_sparse": "굴착 둘레 지면이 적게 찍힘",
    "high_noise": "점 잡음이 큼 (흔들림·거리 확인)", "multiple_pits": "구덩이가 여럿 — 가장 큰 곳만 분석",
    "mesh_las_offset": "메시와 점군 위치가 어긋남", "georef_unreadable": "위치 정보를 읽지 못함",
    "no_georef_local": "로컬 좌표 없음 — 메시와 겹치지 않음",
    "soil_arc_rejected": "흙색 둥근 면 {n}곳 제외 (흙색 관이면 확인)",
    "user_mark_unmatched": "앱에서 탭한 관 종류 {n}개는 가까운 관이 없음",
}


def build_warnings(ctx):
    prm = ctx.prm
    W = []
    mc = {k: v["min_cover"] for k, v in CLASS.items()}
    if isinstance(prm.get("min_cover"), dict):
        mc.update(prm["min_cover"])
    for c in ctx.clearances:
        if c["min_mm"] < prm["clear_min_mm"]:
            a, b = ctx.umap[c["a"]], ctx.umap[c["b"]]
            W.append(dict(level="high", kind="이격 부족", what=f"{a.label} ↔ {b.label}",
                          detail=f"최소 이격 {c['min_mm']:.0f} mm < 기준 {prm['clear_min_mm']} mm", at=c["at_utm"]))
    for u in ctx.utils:
        m = mc.get(u.cls)
        if m and u.depth_min < m:
            W.append(dict(level="mid", kind="얕은 매설", what=u.label,
                          detail=f"최소 심도 {u.depth_min:.3f} m < 참고 기준 {m:.1f} m ({u.info['ko']})", at=None))
        if (u.d.get("confidence") or 0) < prm["conf_warn"]:
            W.append(dict(level="mid", kind="신뢰도 낮음", what=u.label,
                          detail=f"신뢰도 {u.d.get('confidence', 0):.2f} — 근경 사진으로 관경·위치 확인 권장", at=None))
        if u.cls == "unknown" or u.d.get("class_source") != "user":
            why = "종류 미확인" if u.cls == "unknown" else "색으로 추정(사람 확정 전)"
            W.append(dict(level="low", kind="종류 확인", what=u.label, detail=f"{why} — 현장에서 관 종류를 확정하세요", at=None))
    if not ctx.utils:
        W.append(dict(level="high", kind="시설물 없음", what="엔진", detail="노출 시설물을 찾지 못함 — 관이 보이게 다시 촬영하거나 수동으로 기록하세요", at=None))
    for w in (ctx.res.get("quality") or {}).get("warnings") or []:
        k, _, n = str(w).partition(":")
        W.append(dict(level="low", kind="스캔 품질", what="엔진", detail=QWARN_KO.get(k, str(w)).replace("{n}", n), at=None))
    acc = ctx.accuracy
    if acc["abs_m"] is None or acc["abs_m"] > prm["abs_tol_m"]:
        W.append(dict(level="mid", kind="절대 위치", what="좌표",
                      detail=(f"위치 정확도 약 ±{acc['abs_m']:.1f} m (GPS)" if acc["abs_m"] else "위치 정확도 미상")
                      + f" — 제186조③ 허용오차 {prm['abs_tol_m'] * 100:.0f} cm 를 맞추려면 기준점(표식) 측량 또는 RTK 필요", at=None))
    order = {"high": 0, "mid": 1, "low": 2}
    W.sort(key=lambda w: order[w["level"]])
    return W


# ═══════════════════════════════════════════ 6) 카메라·사진 ═══════════════════════════════════════════
def quat_to_R(qx, qy, qz, qw):
    n = math.sqrt(qx * qx + qy * qy + qz * qz + qw * qw) or 1.0
    x, y, z, w = qx / n, qy / n, qz / n, qw / n
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


class Views:
    """카메라 자세 모음 (카메라→월드). 안에서는 모두 OpenCV 카메라 규약(x 오른쪽·y 아래·+z 앞)으로 바꿔 둔다.
    kgeoScan 앱 odometry 는 'cv', 원래 Stray 앱은 'arkit'(x 오른쪽·y 위·−z 앞) — stray_to_mesh.py 처럼 데이터마다 고른다.
    video = rgb.mp4 프레임, hires = 면 모드 사진 (같은 규약)."""

    def __init__(self):
        self.R, self.C, self.K, self.W, self.H, self.kind, self.idx, self.path, self.t = [], [], [], [], [], [], [], [], []
        self.video = None
        self.depth_dir = None
        self.n_video = 0
        self.conv = None

    def finalize(self, conv="cv"):
        self.conv = conv
        self.R = np.array(self.R).reshape(-1, 3, 3)
        if conv == "arkit":
            self.R = self.R @ np.diag([1.0, -1.0, -1.0])
        self.C = np.array(self.C).reshape(-1, 3)
        self.K = np.array(self.K).reshape(-1, 3, 3)
        self.W = np.array(self.W, float)
        self.H = np.array(self.H, float)
        self.kind = np.array(self.kind)
        self.idx = np.array(self.idx, int)
        self.t = np.array(self.t, float)
        return self

    def __len__(self):
        return len(self.C)

    def project(self, X):
        """X (3,) 로컬 → (u, v, z) 모든 카메라."""
        d = np.asarray(X, float)[None, :] - self.C
        Xc = np.einsum("nji,nj->ni", self.R, d)            # Rᵀ d (OpenCV 카메라 좌표)
        x, y, z = Xc[:, 0], Xc[:, 1], Xc[:, 2]
        zz = np.where(z > 1e-6, z, 1e-6)
        u = self.K[:, 0, 0] * x / zz + self.K[:, 0, 2]
        v = self.K[:, 1, 1] * y / zz + self.K[:, 1, 2]
        return u, v, z

    def project_one(self, i, X):
        X = np.asarray(X, float).reshape(-1, 3)
        Xc = (X - self.C[i]) @ self.R[i]
        x, y, z = Xc[:, 0], Xc[:, 1], Xc[:, 2]
        zz = np.where(z > 1e-6, z, 1e-6)
        K = self.K[i]
        return np.column_stack([K[0, 0] * x / zz + K[0, 2], K[1, 1] * y / zz + K[1, 2]]), z

    def up_rot(self, i):
        """영상에서 세계 위(+Y)가 위로 오게 돌릴 횟수 k (0 없음, 1 반시계 90°, 2 180°, 3 시계 90°)."""
        uc = self.R[i][1, :]                  # Rᵀ·(0,1,0), OpenCV 카메라 좌표 (y 아래 = 영상 아래)
        dx, dy = uc[0], uc[1]
        if abs(dy) >= abs(dx):
            return 0 if dy < 0 else 2
        return 1 if dx > 0 else 3

    def depth_at(self, i, u, v):
        if self.kind[i] != "video" or not self.depth_dir:
            return None
        p = os.path.join(self.depth_dir, f"{self.idx[i]:06d}.png")
        if not os.path.exists(p):
            return None
        D = cv2.imread(p, cv2.IMREAD_UNCHANGED)
        if D is None:
            return None
        h, w = D.shape[:2]
        x = int(np.clip(u * w / self.W[i], 0, w - 1))
        y = int(np.clip(v * h / self.H[i], 0, h - 1))
        win = D[max(0, y - 1):y + 2, max(0, x - 1):x + 2].astype(float)
        win = win[win > 0]
        return float(np.median(win)) / 1000.0 if len(win) else None


def detect_convention(V, data_dir, pairs=6, gap_s=0.5):
    """odometry 카메라 규약 고르기 (stray_to_mesh.detect_convention 과 같은 생각, numpy 만):
    프레임 j 의 깊이 점을 두 규약으로 월드에 올려 프레임 i 에 투영하고, i 의 깊이와 얼마나 맞는지 비교한다."""
    vids = np.flatnonzero(V.kind == "video")
    if not V.depth_dir or len(vids) < 10:
        return None, {}
    score = {"cv": [], "arkit": []}
    picks = np.linspace(0, len(vids) - 1, pairs + 2).astype(int)[1:-1]
    for p in picks:
        i = vids[p]
        later = vids[(V.t[vids] >= V.t[i] + gap_s)]
        if not len(later):
            continue
        j = later[0]
        Di = cv2.imread(os.path.join(V.depth_dir, f"{V.idx[i]:06d}.png"), cv2.IMREAD_UNCHANGED)
        Dj = cv2.imread(os.path.join(V.depth_dir, f"{V.idx[j]:06d}.png"), cv2.IMREAD_UNCHANGED)
        if Di is None or Dj is None:
            continue
        h, w = Dj.shape[:2]
        sx = w / V.W[j]
        vv, uu = np.mgrid[0:h:3, 0:w:3]
        z = Dj[vv, uu].astype(float) / 1000.0
        m = (z > 0.2) & (z < 4.0)
        Kj, Ki = V.K[j] * sx, V.K[i] * (Di.shape[1] / V.W[i])
        Pc = np.column_stack([(uu[m] - Kj[0, 2]) / Kj[0, 0] * z[m], (vv[m] - Kj[1, 2]) / Kj[1, 1] * z[m], z[m]])
        for name, F in (("cv", np.eye(3)), ("arkit", np.diag([1.0, -1.0, -1.0]))):
            Rj, Ri = V.R[j] @ F, V.R[i] @ F
            Xw = Pc @ Rj.T + V.C[j]
            Xi = (Xw - V.C[i]) @ Ri
            ok = Xi[:, 2] > 0.2
            u = Ki[0, 0] * Xi[ok, 0] / Xi[ok, 2] + Ki[0, 2]
            v = Ki[1, 1] * Xi[ok, 1] / Xi[ok, 2] + Ki[1, 2]
            ins = (u >= 0) & (u < Di.shape[1] - 1) & (v >= 0) & (v < Di.shape[0] - 1)
            if ins.sum() < 50:
                score[name].append(1.0)
                continue
            d = Di[v[ins].astype(int), u[ins].astype(int)].astype(float) / 1000.0
            good = d > 0
            score[name].append(float(np.median(np.abs(d[good] - Xi[ok][ins][good, 2]))) if good.sum() > 50 else 1.0)
    if not score["cv"]:
        return None, {}
    s = {k: round(float(np.sum(v)), 4) for k, v in score.items()}
    return ("cv" if s["cv"] <= s["arkit"] else "arkit"), s


def load_views(data_dir, log, convention=None):
    V = Views()
    if not data_dir:
        return None
    odo = os.path.join(data_dir, "odometry.csv")
    mp4 = os.path.join(data_dir, "rgb.mp4")
    if os.path.exists(odo) and os.path.exists(mp4):
        cap = cv2.VideoCapture(mp4)
        vw, vh = cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        nfr = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        cap.release()
        Kcam = None
        cm = os.path.join(data_dir, "camera_matrix.csv")
        if os.path.exists(cm):
            try:
                Kcam = np.loadtxt(cm, delimiter=",")
            except Exception:
                Kcam = None
        with open(odo, newline="") as f:
            rd = csv.reader(f)
            hdr = [h.strip() for h in next(rd)]
            col = {h: i for i, h in enumerate(hdr)}
            rows = [r for r in rd if r and any(c.strip() for c in r)]
        n = 0
        for r in rows[:nfr if nfr > 0 else None]:
            g = lambda k: float(r[col[k]])
            R = quat_to_R(g("qx"), g("qy"), g("qz"), g("qw"))
            if "fx" in col and r[col["fx"]].strip():
                K = np.array([[g("fx"), 0, g("cx")], [0, g("fy"), g("cy")], [0, 0, 1.0]])
            elif Kcam is not None:
                K = Kcam / Kcam[2, 2]
            else:
                K = np.array([[vw, 0, vw / 2], [0, vw, vh / 2], [0, 0, 1.0]])
            V.R.append(R)
            V.C.append([g("x"), g("y"), g("z")])
            V.K.append(K)
            V.W.append(vw)
            V.H.append(vh)
            V.kind.append("video")
            V.idx.append(int(float(r[col["frame"]])) if "frame" in col else n)
            V.path.append(mp4)
            V.t.append(g("timestamp") if "timestamp" in col else n / fps)
            n += 1
        V.video = dict(path=mp4, w=int(vw), h=int(vh), frames=nfr, fps=fps)
        V.n_video = n
        dd = os.path.join(data_dir, "depth")
        V.depth_dir = dd if os.path.isdir(dd) else None
        log(f"video poses: {n} frames {int(vw)}x{int(vh)} @ {fps:.0f} fps, depth {'yes' if V.depth_dir else 'no'}")
    hp = os.path.join(data_dir, "hires", "poses.json")
    if os.path.exists(hp):
        pj = _read_json(hp) or {}
        nh = 0
        for k, im in enumerate(pj.get("images") or []):
            f = os.path.join(data_dir, im["file"]) if not os.path.isabs(im["file"]) else im["file"]
            if not os.path.exists(f):
                f2 = os.path.join(data_dir, "hires", os.path.basename(im["file"]))
                if not os.path.exists(f2):
                    continue
                f = f2
            T = np.array(im["transform"], float).reshape(4, 4, order="F")
            w, h = float(im.get("width", 0)), float(im.get("height", 0))
            try:
                with Image.open(f) as pim:
                    aw, ah = pim.size
            except Exception:
                aw, ah = w, h
            sx = aw / w if w else 1.0
            sy = ah / h if h else 1.0
            K = np.array([[im["fx"] * sx, 0, im["cx"] * sx], [0, im["fy"] * sy, im["cy"] * sy], [0, 0, 1.0]])
            V.R.append(T[:3, :3])
            V.C.append(T[:3, 3])
            V.K.append(K)
            V.W.append(aw)
            V.H.append(ah)
            V.kind.append("hires")
            V.idx.append(k)
            V.path.append(f)
            V.t.append(float(im.get("timestamp", 0)))
            nh += 1
        log(f"hires photos: {nh}")
    if not V.C:
        return None
    if convention not in ("cv", "arkit"):
        V.finalize("cv")
        det, sc = detect_convention(V, data_dir)
        convention = det or "cv"
        log(f"pose convention: {convention} (detected {sc})" if det else "pose convention: cv (default, kgeoScan app)")
        if convention == "cv":
            return V
        V.R = V.R @ np.diag([1.0, -1.0, -1.0])
        V.conv = "arkit"
        return V
    log(f"pose convention: {convention} (result.json)")
    return V.finalize(convention)


def rot_img(img, k):
    return img if k == 0 else cv2.rotate(img, {1: cv2.ROTATE_90_COUNTERCLOCKWISE, 2: cv2.ROTATE_180, 3: cv2.ROTATE_90_CLOCKWISE}[k])


def rot_pts(P, W, H, k):
    P = np.asarray(P, float).reshape(-1, 2)
    x, y = P[:, 0], P[:, 1]
    if k == 0:
        return P.copy()
    if k == 1:
        return np.column_stack([y, W - 1 - x])
    if k == 2:
        return np.column_stack([W - 1 - x, H - 1 - y])
    return np.column_stack([H - 1 - y, x])


class PhotoMap:
    def __init__(self, W, H, k, crop, out_w, out_h):
        self.W, self.H, self.k, self.crop, self.ow, self.oh = W, H, k, crop, out_w, out_h

    def map(self, P):
        R = rot_pts(P, self.W, self.H, self.k)
        x0, y0, cw, ch = self.crop
        return np.column_stack([(R[:, 0] - x0) * self.ow / cw, (R[:, 1] - y0) * self.oh / ch])


def fit_crop(cx, cy, cw, Wr, Hr, aspect=1.5):
    cw = float(min(cw, Wr, Hr * aspect))
    ch = cw / aspect
    x0 = float(np.clip(cx - cw / 2, 0, Wr - cw))
    y0 = float(np.clip(cy - ch / 2, 0, Hr - ch))
    return (x0, y0, cw, ch)


def select_photos(ctx, log):
    """측점마다 근경·원경·지거측량 기준점·관로 측량점 프레임을 고른다 → st['photos'][type] = dict(view, k, crop, score)."""
    V = ctx.views
    if V is None or not ctx.stations:
        return {}
    fr = ctx.frame
    corners = None
    ol = (ctx.res.get("trench") or {}).get("outline")
    if ol and fr is not None:
        corners = fr.to_local(np.asarray(ol, float)[:-1] if len(ol) > 3 else np.asarray(ol, float))
    fwd = V.R[:, :, 2]
    down = np.clip(-fwd[:, 1], 0, 1)
    is_hi = V.kind == "hires"
    cand_all = {}
    for st in ctx.stations:
        T = fr.to_local(np.array([[st["xy"][0], st["xy"][1], st["top"]]]))[0]
        Rf = fr.to_local(st["ref"]["xyz"].reshape(1, 3))[0]
        st["T_local"], st["R_local"] = T, Rf
        u, v, z = V.project(T)
        ur, vr, zr = V.project(Rf)

        def inview(uu, vv, zz, m):
            return (zz > 0.15) & (uu > m * V.W) & (uu < (1 - m) * V.W) & (vv > m * V.H) & (vv < (1 - m) * V.H)

        cen = 1 - np.clip(np.hypot((u - V.W / 2) / (V.W / 2), (v - V.H / 2) / (V.H / 2)), 0, 1.4) / 1.4
        vis = inview(u, v, z, 0.08)
        ncorn = np.zeros(len(V))
        if corners is not None:
            for cp in corners:
                cu, cv_, cz = V.project(cp)
                ncorn += inview(cu, cv_, cz, 0.0)
        scores = {
            "near": vis * (0.35 + cen) * np.exp(-((z - 0.75) / 0.45) ** 2) * (1 + 0.4 * is_hi),
            "far": inview(u, v, z, 0.04) * np.clip(z, 0.5, 6.0) * (0.4 + 0.6 * cen) * (1 + ncorn) / (1 + (len(corners) if corners is not None else 0)),
            "ref": vis * inview(ur, vr, zr, 0.06) * (0.3 + cen) * np.exp(-((z - 1.1) / 0.8) ** 2),
            "pt": vis * (cen ** 2) * (0.3 + down) * np.exp(-((z - 0.9) / 0.6) ** 2) * (1 + 0.3 * is_hi),
        }
        cand_all[st["no"]] = {}
        for typ, sc in scores.items():
            order = np.argsort(-sc)
            picks = []
            for i in order[:40]:
                if sc[i] <= 0:
                    break
                d = V.depth_at(i, u[i], v[i])       # 가려짐 검사 (깊이 지도가 있으면)
                if d is not None and z[i] > d + max(0.10, 0.05 * z[i]):
                    continue
                picks.append((int(i), float(sc[i])))
                if len(picks) >= 6:
                    break
            cand_all[st["no"]][typ] = picks
    need = sorted({i for c in cand_all.values() for p in c.values() for i, _ in p})
    if not need:
        log("photos: no station visible in any frame")
        return {}
    imgs = read_views(V, need, log)
    sharp = {}
    for i in need:
        im = imgs.get(i)
        if im is None:
            continue
        g = cv2.cvtColor(cv2.resize(im, (480, int(480 * im.shape[0] / im.shape[1]))), cv2.COLOR_BGR2GRAY)
        sharp[i] = float(cv2.Laplacian(g, cv2.CV_64F).var())
    med = float(np.median(list(sharp.values()))) if sharp else 1.0
    chosen = {}
    for st in ctx.stations:
        used = []
        st["photos"] = {}
        for typ, _ in PHOTO_TYPES:
            best = None
            for i, s in cand_all[st["no"]].get(typ, []):
                if i not in imgs or imgs[i] is None:
                    continue
                if any((V.kind[i] == V.kind[j]) and abs(int(V.idx[i]) - int(V.idx[j])) < (20 if V.kind[i] == "video" else 1) for j in used):
                    s *= 0.35
                f = s * math.sqrt(float(np.clip(sharp.get(i, med) / max(med, 1e-6), 0.3, 1.6)))
                if best is None or f > best[1]:
                    best = (i, f)
            if best is None:
                continue
            used.append(best[0])
            st["photos"][typ] = dict(view=best[0], score=best[1])
            chosen.setdefault(best[0], []).append((st["no"], typ))
    ctx.view_imgs = imgs
    log(f"photos: {sum(len(st['photos']) for st in ctx.stations)} of {4 * len(ctx.stations)} slots from {len(chosen)} frames")
    return chosen


def read_views(V, need, log):
    out = {}
    vids = [i for i in need if V.kind[i] == "video"]
    if vids and V.video:
        want = {int(V.idx[i]): i for i in vids}
        cap = cv2.VideoCapture(V.video["path"])
        last = max(want)
        k = 0
        while k <= last:
            ok = cap.grab()
            if not ok:
                break
            if k in want:
                ok, im = cap.retrieve()
                if ok:
                    out[want[k]] = im
            k += 1
        cap.release()
    for i in need:
        if V.kind[i] == "hires":
            try:
                out[i] = cv2.imdecode(np.fromfile(V.path[i], np.uint8), cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION)
            except Exception:
                out[i] = None
    return out


def render_photo(ctx, st, typ, out_path):
    """사진 하나: 회전·자르기 → 측점 표시·관 위치·보드판 → JPEG 저장 + base64."""
    p = (st.get("photos") or {}).get(typ)          # 측점을 비추는 사진이 하나도 없으면 select_photos 가 photos 를 만들지 않는다
    if not p:
        return None
    V = ctx.views
    i = p["view"]
    img = ctx.view_imgs.get(i)
    if img is None:
        return None
    prm = ctx.prm
    ow, oh = prm["photo_w"], prm["photo_h"]
    H0, W0 = img.shape[:2]
    if V.W[i] != W0:                    # 디코딩 크기와 자세 기준 크기가 다르면 맞춘다
        s = W0 / V.W[i]
        K = V.K[i].copy()
        K[:2] *= s
    k = V.up_rot(i)
    rimg = rot_img(img, k)
    Hr, Wr = rimg.shape[:2]
    Pt, tz = V.project_one(i, st["T_local"])
    tu, tv = Pt[0]
    tu, tv = tu * W0 / V.W[i], tv * H0 / V.H[i]
    T2 = rot_pts([[tu, tv]], W0, H0, k)[0]
    fpx = V.K[i][0, 0] * W0 / V.W[i]
    if typ == "near":
        crop = fit_crop(T2[0], T2[1], max(0.38 * Wr, fpx * 1.1 / max(tz[0], 0.2)), Wr, Hr, ow / oh)
    elif typ == "pt":
        crop = fit_crop(T2[0], T2[1], max(0.32 * Wr, fpx * 0.8 / max(tz[0], 0.2)), Wr, Hr, ow / oh)
    elif typ == "ref":
        Pr, rz = V.project_one(i, st["R_local"])
        ru, rv = Pr[0]
        R2 = rot_pts([[ru * W0 / V.W[i], rv * H0 / V.H[i]]], W0, H0, k)[0]
        mid = (T2 + R2) / 2
        span = max(abs(T2[0] - R2[0]) * 1.6, abs(T2[1] - R2[1]) * 1.6 * 1.44, 0.4 * Wr)
        crop = fit_crop(mid[0], mid[1], span, Wr, Hr, ow / oh)
    else:
        crop = fit_crop(T2[0], T2[1], Wr, Wr, Hr, ow / oh)
    x0, y0, cw, ch = crop
    sub = rimg[int(y0):int(y0 + ch), int(x0):int(x0 + cw)]
    sub = cv2.resize(sub, (ow, oh), interpolation=cv2.INTER_AREA)
    pm = PhotoMap(W0, H0, k, crop, ow, oh)
    sx, sy = W0 / V.W[i], H0 / V.H[i]

    def proj(Xl):
        P, z = V.project_one(i, Xl)
        P = P * [sx, sy]
        return pm.map(P), z

    pil = Image.fromarray(cv2.cvtColor(sub, cv2.COLOR_BGR2RGB)).convert("RGBA") if Image else None
    if pil is None:
        cv2.imwrite(out_path, sub, [cv2.IMWRITE_JPEG_QUALITY, prm["photo_q"]])
        return out_path
    ov = Image.new("RGBA", pil.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    u = st["u"]
    col = hex_rgb(u.info["color"])
    # 관 중심선 (이 사진에 보이는 모든 관, 이 측점의 관은 굵게)
    if typ in ("near", "pt", "far"):
        for uu in ctx.utils:
            if uu.local is None:
                continue
            Lp = resample_poly(uu.local, 0.05)
            Q, z = proj(Lp)
            ok = z > 0.1
            c2 = hex_rgb(uu.info["color"])
            wdt = 5 if uu is u else 3
            for a in range(len(Q) - 1):
                if ok[a] and ok[a + 1]:
                    d.line([tuple(Q[a]), tuple(Q[a + 1])], fill=(*c2, 150 if uu is u else 110), width=wdt)
    (tx, ty), = proj(st["T_local"])[0]
    if typ == "ref":
        (rx, ry), = proj(st["R_local"])[0]
        _dashed(d, (rx, ry), (tx, ty), (255, 255, 255, 230), 3, 10)
        _dashed(d, (rx, ry), (tx, ty), (20, 20, 20, 230), 1, 10)
        d.polygon([(rx, ry - 14), (rx - 11, ry + 7), (rx + 11, ry + 7)], fill=(255, 255, 255, 235), outline=(20, 20, 20, 255))
        lab = st["ref"]["label"] + (" (임시)" if st["ref"]["temp"] else "")
        _tag(d, rx + 14, ry - 10, lab, (30, 30, 30), (255, 255, 255))
        if st["ref"]["offset_m"] is not None:
            _tag(d, (rx + tx) / 2 + 8, (ry + ty) / 2 - 12, f"이격 {st['ref']['offset_m']:.3f} m", (255, 255, 255), (194, 65, 12))
    r = 16 if typ in ("near", "pt") else 11
    d.ellipse([tx - r - 2, ty - r - 2, tx + r + 2, ty + r + 2], outline=(255, 255, 255, 255), width=3)
    d.ellipse([tx - r, ty - r, tx + r, ty + r], outline=(*col, 255), width=3)
    d.line([tx - r - 8, ty, tx - 4, ty], fill=(255, 255, 255, 255), width=2)
    d.line([tx + 4, ty, tx + r + 8, ty], fill=(255, 255, 255, 255), width=2)
    d.line([tx, ty - r - 8, tx, ty - 4], fill=(255, 255, 255, 255), width=2)
    d.line([tx, ty + 4, tx, ty + r + 8], fill=(255, 255, 255, 255), width=2)
    _tag(d, tx + r + 10, ty - r - 4, f"{st['name']}  심도 {st['depth']:.3f} m", (255, 255, 255), col)
    # 보드판 (측점이 왼쪽 아래면 오른쪽 아래로)
    rows = [("공 사 명", ctx.title), ("측    점", f"{st['name']} ({st['sta']})"),
            ("시 설 물", f"{u.type_text()} {u.dia_text(short=True)}" + (f" {u.material}" if u.material else "")),
            ("심    도", f"{st['depth']:.3f} m (지표~관상단)"), ("일    자", ctx.date_text)]
    bw = int(ow * 0.5)
    right = tx < bw + 30 and ty > oh - 150
    _board(d, ow - bw - 10 if right else 10, oh - 10, bw, rows)
    pil = Image.alpha_composite(pil, ov).convert("RGB")
    pil.save(out_path, "JPEG", quality=prm["photo_q"], optimize=True)
    return out_path


def _dashed(d, p, q, fill, width, dash):
    p, q = np.array(p, float), np.array(q, float)
    L = float(np.linalg.norm(q - p))
    if L < 1:
        return
    v = (q - p) / L
    s = 0.0
    while s < L:
        a, b = p + v * s, p + v * min(L, s + dash)
        d.line([tuple(a), tuple(b)], fill=fill, width=width)
        s += 2 * dash


def _tag(d, x, y, text, fg, bg, size=15):
    f = font(size, True)
    if f is None:
        return
    x0, y0, x1, y1 = f.getbbox(text)
    w, h = x1 - x0 + 14, y1 - y0 + 10
    W, H = d.im.size
    x = float(np.clip(x, 2, W - w - 2))
    y = float(np.clip(y, 2, H - h - 2))
    d.rounded_rectangle([x, y, x + w, y + h], radius=5, fill=(*bg, 235))
    d.text((x + 7 - x0, y + 5 - y0), text, font=f, fill=(*fg, 255))


def _board(d, x, ybottom, w, rows, size=13):
    """공사 사진용 보드판(흑판) 흉내: 흰 바탕, 검은 칸."""
    f, fb = font(size), font(size, True)
    if f is None:
        return
    lh = size + 9
    lw = int(size * 5.2)
    h = lh * len(rows) + 4
    y = ybottom - h
    d.rectangle([x, y, x + w, y + h], fill=(250, 250, 246, 238), outline=(25, 30, 28, 255), width=2)
    for k, (lab, val) in enumerate(rows):
        yy = y + 2 + k * lh
        if k:
            d.line([x, yy, x + w, yy], fill=(25, 30, 28, 255), width=1)
        d.rectangle([x + 1, yy + 1, x + lw, yy + lh - 1], fill=(228, 232, 226, 255))
        d.text((x + 6, yy + 4), lab, font=fb, fill=(25, 30, 28, 255))
        t = str(val)
        while f.getlength(t) > w - lw - 12 and len(t) > 2:
            t = t[:-2] + "…"
        d.text((x + lw + 6, yy + 4), t, font=f, fill=(25, 30, 28, 255))
    d.line([x + lw, y, x + lw, y + h], fill=(25, 30, 28, 255), width=1)


# ═══════════════════════════════════════════ 7) 점군 (LAS, 있으면) ═══════════════════════════════════════════
def load_las(path, bounds, log, zmax=None):
    try:
        import laspy
    except Exception:
        return None
    try:
        las = laspy.read(path)
    except Exception as e:
        log(f"las read failed: {e}")
        return None
    x, y, z = np.asarray(las.x), np.asarray(las.y), np.asarray(las.z)
    (x0, y0), (x1, y1) = bounds
    m = (x >= x0) & (x <= x1) & (y >= y0) & (y <= y1)
    if zmax is not None:
        m &= z <= zmax
    P = np.column_stack([x[m], y[m], z[m]])
    try:
        rgb = np.column_stack([np.asarray(las.red)[m], np.asarray(las.green)[m], np.asarray(las.blue)[m]]).astype(np.float64)
        if rgb.max() > 255:
            rgb = rgb / 257.0
        rgb = np.clip(rgb, 0, 255).astype(np.uint8)
    except Exception:
        rgb = np.full((len(P), 3), 150, np.uint8)
    log(f"las: {len(P)} points in plan bounds")
    return dict(P=P, rgb=rgb)


def plan_raster(las, bounds, px_max=1000):
    (x0, y0), (x1, y1) = bounds
    res = max(x1 - x0, y1 - y0) / px_max
    W, H = int(math.ceil((x1 - x0) / res)), int(math.ceil((y1 - y0) / res))
    P, C = las["P"], las["rgb"]
    ix = ((P[:, 0] - x0) / res).astype(int)
    iy = ((y1 - P[:, 1]) / res).astype(int)
    ok = (ix >= 0) & (ix < W) & (iy >= 0) & (iy < H)
    o = np.argsort(P[ok, 2])
    img = np.zeros((H, W, 3), np.uint8)
    has = np.zeros((H, W), np.uint8)
    img[iy[ok][o], ix[ok][o]] = C[ok][o][:, ::-1]
    has[iy[ok][o], ix[ok][o]] = 255
    k = np.ones((3, 3), np.uint8)
    holes = cv2.dilate(has, k, iterations=2) & ~has
    if holes.any():
        img = cv2.inpaint(img, holes, 3, cv2.INPAINT_TELEA)
    fill = cv2.dilate(has, k, iterations=2)
    img[fill == 0] = (236, 238, 234)
    return img


def ortho_raster(ortho_json, bounds, px_max=1000):
    oj = _read_json(ortho_json) or {}
    base = os.path.dirname(ortho_json)
    imgf = os.path.join(base, (oj.get("files") or {}).get("image", "ortho.jpg"))
    jgw = os.path.splitext(imgf)[0] + ".jgw"
    if not (os.path.exists(imgf) and os.path.exists(jgw)):
        return None
    A, D, B, E, C, F = [float(v) for v in open(jgw).read().split()[:6]]
    im = cv2.imdecode(np.fromfile(imgf, np.uint8), cv2.IMREAD_COLOR)
    if im is None or abs(D) > 1e-12 or abs(B) > 1e-12:
        return None
    (x0, y0), (x1, y1) = bounds
    c0 = int(math.floor((x0 - C) / A))
    c1 = int(math.ceil((x1 - C) / A))
    r0 = int(math.floor((y1 - F) / E))
    r1 = int(math.ceil((y0 - F) / E))
    Hh, Ww = im.shape[:2]
    canvas = np.full((max(1, r1 - r0), max(1, c1 - c0), 3), (236, 238, 234), np.uint8)
    sx0, sy0, sx1, sy1 = max(0, c0), max(0, r0), min(Ww, c1), min(Hh, r1)
    if sx1 <= sx0 or sy1 <= sy0:
        return None
    canvas[sy0 - r0:sy1 - r0, sx0 - c0:sx1 - c0] = im[sy0:sy1, sx0:sx1]
    s = px_max / max(canvas.shape[:2])
    if s < 1:
        canvas = cv2.resize(canvas, (int(canvas.shape[1] * s), int(canvas.shape[0] * s)), interpolation=cv2.INTER_AREA)
    return canvas


def b64jpg(img, q=82):
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, q])
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()


# ═══════════════════════════════════════════ 8) 그림 (SVG) ═══════════════════════════════════════════
def plan_bounds(ctx, margin=0.5):
    pts = [u.cl[:, :2] for u in ctx.utils] or [np.zeros((0, 2))]
    ol = (ctx.res.get("trench") or {}).get("outline")
    if ol:
        pts.append(np.asarray(ol, float)[:, :2])
    P = np.vstack(pts)
    lo, hi = P.min(0) - margin, P.max(0) + margin
    return (lo, hi)


def clear_text(mm):
    return "접촉·겹침" if mm <= 0 else f"{mm:.0f} mm"


def plan_svg(ctx, W=700, H=520, labels=True, compact=False):
    (x0, y0), (x1, y1) = ctx.bounds
    s = min((W - 40) / (x1 - x0), (H - 40) / (y1 - y0))
    ox = (W - (x1 - x0) * s) / 2
    oy = (H - (y1 - y0) * s) / 2

    def X(e):
        return ox + (e - x0) * s

    def Y(n):
        return oy + (y1 - n) * s

    o = [f'<svg class="plan" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="평면도">']
    o.append('<defs><pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
             '<line x1="0" y1="0" x2="0" y2="6" stroke="#c2410c" stroke-width="1.2" opacity=".45"/></pattern></defs>')
    o.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="#eef1ec"/>')
    if ctx.plan_bg is not None:
        o.append(f'<image href="{ctx.plan_bg}" x="{X(x0):.1f}" y="{Y(y1):.1f}" width="{(x1 - x0) * s:.1f}" '
                 f'height="{(y1 - y0) * s:.1f}" preserveAspectRatio="none" opacity="0.9"/>')
    # 1 m 격자
    g = 1.0 if (x1 - x0) < 30 else 5.0
    for e in np.arange(math.ceil(x0 / g) * g, x1, g):
        o.append(f'<line x1="{X(e):.1f}" y1="{oy:.1f}" x2="{X(e):.1f}" y2="{H - oy:.1f}" stroke="#1d2321" stroke-width=".4" opacity=".18"/>')
    for n in np.arange(math.ceil(y0 / g) * g, y1, g):
        o.append(f'<line x1="{ox:.1f}" y1="{Y(n):.1f}" x2="{W - ox:.1f}" y2="{Y(n):.1f}" stroke="#1d2321" stroke-width=".4" opacity=".18"/>')
    ol = (ctx.res.get("trench") or {}).get("outline")
    if ol:
        pts = " ".join(f"{X(p[0]):.1f},{Y(p[1]):.1f}" for p in ol)
        o.append(f'<polygon points="{pts}" fill="url(#hatch)" stroke="#c2410c" stroke-width="2" stroke-dasharray="7 4"/>')
    for u in ctx.utils:
        pts = " ".join(f"{X(p[0]):.1f},{Y(p[1]):.1f}" for p in u.cl)
        wpx = max(3.0, 2 * u.r * s)
        o.append(f'<polyline points="{pts}" fill="none" stroke="#fff" stroke-width="{wpx + 3:.1f}" stroke-linecap="round" stroke-linejoin="round" opacity=".85"/>')
        o.append(f'<polyline points="{pts}" fill="none" stroke="{u.info["color"]}" stroke-width="{wpx:.1f}" stroke-linecap="round" stroke-linejoin="round" opacity=".9"/>')
        o.append(f'<polyline points="{pts}" fill="none" stroke="#1d2321" stroke-width=".8" stroke-dasharray="5 3" opacity=".7"/>')
        if labels:
            m = u.cl[len(u.cl) // 2]
            o.append(f'<text x="{X(m[0]) + 6:.1f}" y="{Y(m[1]) - 6:.1f}" class="pl-lab" fill="{u.info["color"]}">{esc(u.id)} {esc(u.info["short"])} {esc(u.dia_text(True))}</text>')
    placed = []

    def free(x, y, w, h):
        for (a, b, c, d) in placed:
            if x < c and x + w > a and y < d and y + h > b:
                return False
        return True
    for st in ctx.stations:
        x, y = X(st["xy"][0]), Y(st["xy"][1])
        o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{3.2 if compact else 4.2}" fill="#fff" stroke="#1d2321" stroke-width="1.5"/>')
    if labels and not compact:
        for st in ctx.stations:
            x, y = X(st["xy"][0]), Y(st["xy"][1])
            w = 7 * len(st["name"]) + 2
            for dx, dy in ((6, 4), (-w - 6, 4), (6, -14), (-w - 6, -14), (6, 14), (-w - 6, 14)):
                if free(x + dx, y + dy - 10, w, 12):
                    placed.append((x + dx, y + dy - 10, x + dx + w, y + dy + 2))
                    o.append(f'<text x="{x + dx:.1f}" y="{y + dy:.1f}" class="pl-st">{esc(st["name"])}</text>')
                    break
    bad = [c for c in ctx.clearances if c["min_mm"] < ctx.prm["clear_min_mm"]]
    for c in bad:
        a = c["at_utm"]
        o.append(f'<circle cx="{X(a[0]):.1f}" cy="{Y(a[1]):.1f}" r="9" fill="none" stroke="#dc2626" stroke-width="2.2"/>')
    if labels and not compact:
        for c in bad[:3]:
            a = c["at_utm"]
            t = f'{c["a"]}–{c["b"]} {clear_text(c["min_mm"])}'
            w = 6.6 * len(t)
            for dx, dy in ((12, 16), (12, -10), (-w - 12, 16), (-w - 12, -10)):
                if free(X(a[0]) + dx, Y(a[1]) + dy - 11, w, 13):
                    placed.append((X(a[0]) + dx, Y(a[1]) + dy - 11, X(a[0]) + dx + w, Y(a[1]) + dy + 2))
                    o.append(f'<text x="{X(a[0]) + dx:.1f}" y="{Y(a[1]) + dy:.1f}" class="pl-warn">{esc(t)}</text>')
                    break
    # 방위·축척
    o.append(f'<g transform="translate({W - 34},{40})"><circle r="17" fill="#fff" stroke="#1d2321" stroke-width="1"/>'
             '<path d="M0,-13 L6,8 L0,4 L-6,8 Z" fill="#1d2321"/><text y="-19" text-anchor="middle" class="pl-n">N</text></g>')
    sb = 1.0 if (x1 - x0) < 12 else 5.0 if (x1 - x0) < 60 else 20.0
    o.append(f'<g transform="translate({ox + 14:.1f},{H - oy - 16:.1f})"><rect x="-6" y="-16" width="{sb * s + 40:.1f}" height="24" rx="4" fill="#fff" opacity=".85"/>'
             f'<rect x="0" y="0" width="{sb * s / 2:.1f}" height="5" fill="#1d2321"/><rect x="{sb * s / 2:.1f}" y="0" width="{sb * s / 2:.1f}" height="5" fill="#fff" stroke="#1d2321" stroke-width=".8"/>'
             f'<text x="0" y="-4" class="pl-sc">0</text><text x="{sb * s:.1f}" y="-4" class="pl-sc" text-anchor="middle">{sb:g} m</text></g>')
    o.append(f'<text x="{ox + 4:.1f}" y="{oy + 12:.1f}" class="pl-co">E {x0 + (x1 - x0) * 0:,.1f} · N {y1:,.1f}</text>')
    o.append(f'<text x="{W - ox - 4:.1f}" y="{H - oy - 4:.1f}" class="pl-co" text-anchor="end">E {x1:,.1f} · N {y0:,.1f} (UTM 52N)</text>')
    o.append("</svg>")
    return "".join(o)


def section_svg(ctx, st, W=520, H=330):
    """측점 단면도 (관 진행 방향을 보고 선 단면). 점군이 있으면 단면 띠의 점을 같이 그린다."""
    u = st["u"]
    c, t = st["xy"], st["tan"]
    n = np.array([-t[1], t[0]])
    hits = section_hits(ctx.utils, st)
    st["hits"] = hits
    # 굴착 벽 (평면 경계와 단면선의 교점)
    bl, br = -0.6, 0.6
    ol = (ctx.res.get("trench") or {}).get("outline")
    if ol:
        O = np.asarray(ol, float)[:, :2]
        bs = []
        for i in range(len(O) - 1):
            a, b = O[i], O[i + 1]
            d = b - a
            den = n[0] * (-d[1]) - n[1] * (-d[0])
            if abs(den) < 1e-12:
                continue
            w = a - c
            tt = (w[0] * (-d[1]) - w[1] * (-d[0])) / den
            ss = (n[0] * w[1] - n[1] * w[0]) / den
            if 0 <= ss <= 1:
                bs.append(tt)
        neg, pos = [b for b in bs if b < 0], [b for b in bs if b > 0]
        if neg:
            bl = max(neg)
        if pos:
            br = min(pos)
    zg = st["ground"]
    dmax = float((ctx.res.get("trench") or {}).get("depth_max_m") or (st["depth"] + 2 * u.r + 0.2))
    zb = zg - dmax
    lo_b = min(bl, min(h[1] for h in hits) - 0.2) - 0.35
    hi_b = max(br, max(h[1] for h in hits) + 0.2) + 0.35
    zlo = min(zb, min(h[2] - h[0].r for h in hits)) - 0.12
    zhi = zg + 0.22
    pad_l, pad_r, pad_t, pad_b = 46, 14, 26, 30
    s = min((W - pad_l - pad_r) / (hi_b - lo_b), (H - pad_t - pad_b) / (zhi - zlo))

    def X(b):
        return pad_l + (b - lo_b) * s

    def Y(z):
        return pad_t + (zhi - z) * s

    o = [f'<svg class="sect" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="단면도 {esc(st["name"])}">']
    o.append('<defs><pattern id="soil" width="8" height="8" patternUnits="userSpaceOnUse"><rect width="8" height="8" fill="#e9dccb"/>'
             '<circle cx="2" cy="2" r=".9" fill="#b89470"/><circle cx="6" cy="5.5" r=".7" fill="#a07c58"/></pattern>'
             '<marker id="ar" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
             '<path d="M0,0 L10,5 L0,10 z" fill="#1d2321"/></marker></defs>')
    # 흙 (굴착 바깥), 굴착 빈 공간
    o.append(f'<rect x="{X(lo_b):.1f}" y="{Y(zg):.1f}" width="{(hi_b - lo_b) * s:.1f}" height="{(zg - zlo) * s:.1f}" fill="url(#soil)"/>')
    o.append(f'<path d="M{X(bl):.1f},{Y(zg):.1f} L{X(bl):.1f},{Y(zb):.1f} L{X(br):.1f},{Y(zb):.1f} L{X(br):.1f},{Y(zg):.1f} Z" fill="#fbfaf7" stroke="#8a6d4b" stroke-width="1.4"/>')
    # 점군 띠
    if ctx.las is not None:
        P = ctx.las["P"]
        d = P[:, :2] - c
        ss, bb = d @ t, d @ n
        m = (np.abs(ss) < ctx.prm["slab_m"]) & (bb > lo_b) & (bb < hi_b) & (P[:, 2] > zlo) & (P[:, 2] < zhi)
        idx = np.flatnonzero(m)
        if len(idx) > 2500:
            idx = idx[np.linspace(0, len(idx) - 1, 2500).astype(int)]
        if len(idx):
            pts = "".join(f"M{X(bb[k]):.1f},{Y(P[k, 2]):.1f}h.01" for k in idx)
            o.append(f'<path d="{pts}" stroke="#4b5563" stroke-width="2.2" stroke-linecap="round" opacity=".55"/>')
    # 원지반선
    o.append(f'<line x1="{X(lo_b):.1f}" y1="{Y(zg):.1f}" x2="{X(hi_b):.1f}" y2="{Y(zg):.1f}" stroke="#1d2321" stroke-width="1.6"/>')
    o.append(f'<text x="{X(lo_b) + 3:.1f}" y="{Y(zg) - 5:.1f}" class="s-t">원지반 EL.{zg:.2f}</text>')
    placed_pre = [(X(bl), Y(zg), X(bl) + 110, Y(zg) + 14)]
    placed = list(placed_pre)

    def place(w, h, cands):
        for bx, by in cands:
            if all(not (bx < c and bx + w > a and by - h < d and by > b_) for a, b_, c, d in placed) and 0 <= bx and bx + w <= W:
                placed.append((bx, by - h, bx + w, by))
                return bx, by
        return None
    # 심도 치수 자리는 먼저 잡아 둔다
    bx_dim = X(0) + max(10, u.r * s) + 14
    placed.append((bx_dim - 2, Y(zg), bx_dim + 92, Y(st["top"]) + 16))
    # 관
    for uu, b, zc in hits:
        col = uu.info["color"]
        if uu.kind == "bundle":
            nn = int(uu.d.get("count") or 3)
            rr = uu.r / max(1.6, nn ** 0.5 * 1.1)
            for k2 in range(nn):
                bx = b + (k2 - (nn - 1) / 2) * 2.05 * rr
                o.append(f'<circle cx="{X(bx):.1f}" cy="{Y(zc + uu.r - rr):.1f}" r="{rr * s:.1f}" fill="{col}" fill-opacity=".35" stroke="{col}" stroke-width="1.6"/>')
        else:
            o.append(f'<circle cx="{X(b):.1f}" cy="{Y(zc):.1f}" r="{max(2.5, uu.r * s):.1f}" fill="{col}" fill-opacity="{0.35 if uu is not u else 0.5}" stroke="{col}" stroke-width="{2.2 if uu is u else 1.4}"/>')
        placed.append((X(b) - uu.r * s, Y(zc + uu.r), X(b) + uu.r * s, Y(zc - uu.r)))
    for uu, b, zc in hits:
        col = uu.info["color"]
        t = f"{uu.id} {uu.dia_text(True)}"
        w = 6.4 * len(t) + 4
        rp = max(2.5, uu.r * s)
        cx, cy = X(b), Y(zc)
        pos = place(w, 11, [(cx - w / 2, cy + rp + 12), (cx + rp + 4, cy + 4), (cx - rp - 4 - w, cy + 4), (cx - w / 2, cy - rp - 4),
                            (cx + rp + 4, cy + 18), (cx - rp - 4 - w, cy + 18), (cx + rp + 4, cy - 10), (cx - rp - 4 - w, cy - 10)])
        if pos:
            o.append(f'<text x="{pos[0]:.1f}" y="{pos[1]:.1f}" class="s-u" fill="{col}">{esc(t)}</text>')
    # 심도 치수
    bx = bx_dim
    o.append(f'<line x1="{bx:.1f}" y1="{Y(zg):.1f}" x2="{bx:.1f}" y2="{Y(st["top"]):.1f}" stroke="#1d2321" stroke-width="1.2" marker-start="url(#ar)" marker-end="url(#ar)"/>')
    o.append(f'<line x1="{X(0) - 4:.1f}" y1="{Y(st["top"]):.1f}" x2="{bx + 4:.1f}" y2="{Y(st["top"]):.1f}" stroke="#1d2321" stroke-width=".8" stroke-dasharray="3 2"/>')
    o.append(f'<text x="{bx + 5:.1f}" y="{(Y(zg) + Y(st["top"])) / 2 + 4:.1f}" class="s-d">심도 {st["depth"]:.3f} m</text>')
    o.append(f'<text x="{bx + 5:.1f}" y="{Y(st["top"]) + 13:.1f}" class="s-t">관상단 EL.{st["top"]:.2f}</text>')
    # 단면 안 이격 (이 측점 관과 가장 가까운 두 관)
    gl = sorted([g for g in section_gaps(hits) if (g[0] is u or g[1] is u) and g[2] < 600], key=lambda g: g[2])[:2]
    for ua, ub, gap, pa, pb in gl:
        colr = "#dc2626" if gap < ctx.prm["clear_min_mm"] else "#1d2321"
        if gap > 0:
            o.append(f'<line x1="{X(pa[0]):.1f}" y1="{Y(pa[1]):.1f}" x2="{X(pb[0]):.1f}" y2="{Y(pb[1]):.1f}" stroke="{colr}" stroke-width="1.2" marker-start="url(#ar)" marker-end="url(#ar)"/>')
        t = clear_text(gap)
        w = 6.4 * len(t) + 4
        mx, my = (X(pa[0]) + X(pb[0])) / 2, (Y(pa[1]) + Y(pb[1])) / 2
        pos = place(w, 11, [(mx - w / 2, my - 6), (mx - w / 2, my + 16), (mx + 6, my - 14), (mx - w - 6, my - 14), (mx + 6, my + 22), (mx - w - 6, my + 22)])
        if pos:
            o.append(f'<text x="{pos[0]:.1f}" y="{pos[1]:.1f}" class="s-g" fill="{colr}">{esc(t)}</text>')
    # 너비·축척
    o.append(f'<text x="{X(bl) + 3:.1f}" y="{Y(zg) + 12:.1f}" class="s-t">← 굴착 폭 {br - bl:.2f} m →</text>')
    sb = 0.5
    o.append(f'<g transform="translate({W - pad_r - sb * s - 8:.1f},{H - 10})"><rect x="0" y="-5" width="{sb * s / 2:.1f}" height="4" fill="#1d2321"/>'
             f'<rect x="{sb * s / 2:.1f}" y="-5" width="{sb * s / 2:.1f}" height="4" fill="#fff" stroke="#1d2321" stroke-width=".7"/>'
             f'<text x="{sb * s:.1f}" y="-8" text-anchor="end" class="s-t">{sb:g} m</text></g>')
    for z in np.arange(math.ceil(zlo * 4) / 4, zhi, 0.25):
        o.append(f'<line x1="{pad_l - 4}" y1="{Y(z):.1f}" x2="{pad_l}" y2="{Y(z):.1f}" stroke="#1d2321" stroke-width=".7"/>'
                 f'<text x="{pad_l - 6}" y="{Y(z) + 3:.1f}" text-anchor="end" class="s-ax">{z:.2f}</text>')
    o.append(f'<text x="{pad_l}" y="14" class="s-h">{esc(st["name"])} · {esc(st["sta"])} · 진행 방향으로 본 단면</text>')
    o.append("</svg>")
    return "".join(o)


def profile_svg(ctx, u, W=720, H=230):
    """종단면도: 원지반·관 상단/하단·측점."""
    s_ = u.cum
    L = max(u.length2d, 0.1)
    zg, zt, zc = u.ground_z, u.top_z, u.center_z
    zbot = zc - u.r
    zlo, zhi = float(min(zbot.min(), (zg - u.depth_max - 0.3).min())) - 0.1, float(zg.max()) + 0.2
    pad_l, pad_r, pad_t, pad_b = 52, 16, 22, 30
    sx = (W - pad_l - pad_r) / L
    sz = (H - pad_t - pad_b) / (zhi - zlo)
    if sz < sx:                       # 짧은 관: 세로를 줄이지 않고 1:1 로 (가로를 좁힘)
        sx = sz
    ex = sz / sx

    def X(s):
        return pad_l + s * sx

    def Y(z):
        return pad_t + (zhi - z) * sz

    col = u.info["color"]
    o = [f'<svg class="prof" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="종단면도 {esc(u.id)}">']
    gpath = " ".join(f"{X(a):.1f},{Y(b):.1f}" for a, b in zip(s_, zg))
    o.append(f'<polygon points="{X(0):.1f},{Y(zlo):.1f} {gpath} {X(L):.1f},{Y(zlo):.1f}" fill="#efe6da"/>')
    o.append(f'<polyline points="{gpath}" fill="none" stroke="#1d2321" stroke-width="1.6"/>')
    band = " ".join(f"{X(a):.1f},{Y(b):.1f}" for a, b in zip(s_, zt)) + " " + " ".join(
        f"{X(a):.1f},{Y(b):.1f}" for a, b in zip(s_[::-1], zbot[::-1]))
    o.append(f'<polygon points="{band}" fill="{col}" fill-opacity=".45" stroke="{col}" stroke-width="1.6"/>')
    for st in ctx.stations:
        if st["u"] is not u:
            continue
        x = X(st["s"])
        o.append(f'<line x1="{x:.1f}" y1="{Y(st["ground"]):.1f}" x2="{x:.1f}" y2="{Y(st["top"]):.1f}" stroke="#1d2321" stroke-width="1" marker-start="url(#ar2)" marker-end="url(#ar2)"/>')
        right = x > X(L) - 50
        anc = ' text-anchor="end"' if right else ''
        o.append(f'<text x="{x - 3 if right else x + 3:.1f}" y="{(Y(st["ground"]) + Y(st["top"])) / 2:.1f}" class="s-d"{anc}>{st["depth"]:.3f}</text>')
        o.append(f'<text x="{x:.1f}" y="{H - 16}" text-anchor="middle" class="s-t">{esc(st["name"])}</text>'
                 f'<text x="{x:.1f}" y="{H - 5}" text-anchor="middle" class="s-ax">{st["s"]:.2f}</text>')
    o.insert(1, '<defs><marker id="ar2" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">'
                '<path d="M0,0 L10,5 L0,10 z" fill="#1d2321"/></marker></defs>')
    for z in np.arange(math.ceil(zlo * 4) / 4, zhi, 0.25 if zhi - zlo < 3 else 0.5):
        o.append(f'<line x1="{pad_l}" y1="{Y(z):.1f}" x2="{W - pad_r}" y2="{Y(z):.1f}" stroke="#1d2321" stroke-width=".3" opacity=".25"/>'
                 f'<text x="{pad_l - 5}" y="{Y(z) + 3:.1f}" text-anchor="end" class="s-ax">{z:.2f}</text>')
    o.append(f'<text x="{pad_l}" y="14" class="s-h">{esc(u.id)} {esc(u.type_text())} {esc(u.dia_text())} · 연장 {u.length:.2f} m · '
             f'경사 {u.d.get("slope_pct", 0):+.2f} % · 세로 과장 ×{ex:.1f}</text>')
    o.append("</svg>")
    return "".join(o)


# ═══════════════════════════════════════════ 9) 내보내기: CSV · DXF · LandXML · GeoJSON ═══════════════════════════════════════════
CSV_COLS = ["측점명", "시설물", "측점구분", "추가거리(m)", "X(N)", "Y(E)", "관상단표고(m)", "원지반표고(m)", "시설물종류", "재질",
            "관경(mm)", "이격거리(m)", "이격기준", "심도(m)", "인접관최소이격(mm)", "근경사진", "원경사진", "지거측량기준점사진",
            "관로측량점사진", "UTM_E", "UTM_N", "신뢰도", "측량일", "측량자", "비고"]


def station_row(ctx, st):
    u = st["u"]
    X, Y = ctx.geo.tm(st["xy"][0], st["xy"][1])
    gaps = [g for g in section_gaps(st.get("hits") or section_hits(ctx.utils, st)) if g[0] is u or g[1] is u]
    mg = min((g[2] for g in gaps), default=None)
    ph = st.get("photo_files", {})
    note = []
    if st["kind"] == "cross" and st.get("other"):
        note.append(f"{st['other']} 교차")
    if u.d.get("class_source") != "user":
        note.append("종류 색 추정" if u.cls != "unknown" else "종류 미확인")
    if st["ref"]["temp"]:
        note.append("지거 임시기준")
    return {
        "측점명": st["name"], "시설물": u.id, "측점구분": ST_KIND_KO.get(st["kind"], st["kind"]), "추가거리(m)": f"{st['s']:.3f}",
        "X(N)": f"{float(X):.3f}", "Y(E)": f"{float(Y):.3f}", "관상단표고(m)": f"{st['top']:.2f}", "원지반표고(m)": f"{st['ground']:.2f}",
        "시설물종류": u.type_text(), "재질": u.material, "관경(mm)": (u.d.get("width_mm") if u.kind == "bundle" else u.nominal_mm) or "",
        "이격거리(m)": "" if st["ref"]["offset_m"] is None else f"{st['ref']['offset_m']:.3f}", "이격기준": st["ref"]["desc"],
        "심도(m)": f"{st['depth']:.3f}", "인접관최소이격(mm)": "" if mg is None else f"{mg:.0f}",
        "근경사진": ph.get("near", ""), "원경사진": ph.get("far", ""), "지거측량기준점사진": ph.get("ref", ""), "관로측량점사진": ph.get("pt", ""),
        "UTM_E": f"{st['xy'][0]:.3f}", "UTM_N": f"{st['xy'][1]:.3f}", "신뢰도": u.d.get("confidence", ""),
        "측량일": ctx.date_iso, "측량자": ctx.surveyor or "", "비고": "; ".join(note),
    }


def write_csv(ctx, path):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLS)
        w.writeheader()
        for st in ctx.stations:
            w.writerow(station_row(ctx, st))


class DXF:
    """AutoCAD R12 ASCII (AC1009). 글자는 ASCII 만 (한글 글꼴·코드페이지 문제를 피한다)."""

    def __init__(self):
        self.ent = []
        self.layers = {}
        self.ext = [np.inf, np.inf, np.inf, -np.inf, -np.inf, -np.inf]

    def layer(self, name, color):
        self.layers[name] = int(color)

    def _g(self, code, val):
        if isinstance(val, float):
            val = f"{val:.4f}"
        self.ent.append(f"{code}\n{val}")

    def _xyz(self, p, base=10):
        x, y, z = float(p[0]), float(p[1]), float(p[2]) if len(p) > 2 else 0.0
        self.ext = [min(self.ext[0], x), min(self.ext[1], y), min(self.ext[2], z), max(self.ext[3], x), max(self.ext[4], y), max(self.ext[5], z)]
        self._g(base, x)
        self._g(base + 10, y)
        self._g(base + 20, z)

    def poly3d(self, layer, P, closed=False):
        self._g(0, "POLYLINE")
        self._g(8, layer)
        self._g(66, 1)
        self._xyz((0.0, 0.0, 0.0))
        self._g(70, 8 | (1 if closed else 0))
        for p in P:
            self._g(0, "VERTEX")
            self._g(8, layer)
            self._xyz(p)
            self._g(70, 32)
        self._g(0, "SEQEND")
        self._g(8, layer)

    def line(self, layer, a, b):
        self._g(0, "LINE")
        self._g(8, layer)
        self._xyz(a, 10)
        self._xyz(b, 11)

    def point(self, layer, p):
        self._g(0, "POINT")
        self._g(8, layer)
        self._xyz(p)

    def circle(self, layer, p, r):
        self._g(0, "CIRCLE")
        self._g(8, layer)
        self._xyz(p)
        self._g(40, float(r))

    def text(self, layer, p, h, s, rot=0.0):
        s = str(s).encode("ascii", "replace").decode()
        self._g(0, "TEXT")
        self._g(8, layer)
        self._xyz(p)
        self._g(40, float(h))
        self._g(1, s)
        self._g(50, float(rot))

    def write(self, path):
        e = self.ext if np.isfinite(self.ext[0]) else [0, 0, 0, 1, 1, 1]
        L = ["0\nSECTION\n2\nHEADER", "9\n$ACADVER\n1\nAC1009", "9\n$INSBASE\n10\n0.0\n20\n0.0\n30\n0.0",
             f"9\n$EXTMIN\n10\n{e[0]:.4f}\n20\n{e[1]:.4f}\n30\n{e[2]:.4f}", f"9\n$EXTMAX\n10\n{e[3]:.4f}\n20\n{e[4]:.4f}\n30\n{e[5]:.4f}",
             f"9\n$LIMMIN\n10\n{e[0]:.4f}\n20\n{e[1]:.4f}", f"9\n$LIMMAX\n10\n{e[3]:.4f}\n20\n{e[4]:.4f}",
             "9\n$TEXTSTYLE\n7\nSTANDARD", "9\n$CLAYER\n8\n0", "0\nENDSEC",
             "0\nSECTION\n2\nTABLES",
             "0\nTABLE\n2\nLTYPE\n70\n2",
             "0\nLTYPE\n2\nCONTINUOUS\n70\n0\n3\nSolid line\n72\n65\n73\n0\n40\n0.0",
             "0\nLTYPE\n2\nDASHED\n70\n0\n3\n__ __ __\n72\n65\n73\n2\n40\n0.15\n49\n0.1\n49\n-0.05",
             "0\nENDTAB",
             f"0\nTABLE\n2\nLAYER\n70\n{len(self.layers) + 1}",
             "0\nLAYER\n2\n0\n70\n0\n62\n7\n6\nCONTINUOUS"]
        for n, c in self.layers.items():
            lt = "DASHED" if n in ("TRENCH",) else "CONTINUOUS"
            L.append(f"0\nLAYER\n2\n{n}\n70\n0\n62\n{c}\n6\n{lt}")
        L += ["0\nENDTAB", "0\nTABLE\n2\nSTYLE\n70\n1",
              "0\nSTYLE\n2\nSTANDARD\n70\n0\n40\n0.0\n41\n1.0\n50\n0.0\n71\n0\n42\n0.2\n3\ntxt\n4\n", "0\nENDTAB", "0\nENDSEC",
              "0\nSECTION\n2\nENTITIES"]
        L += self.ent
        L += ["0\nENDSEC", "0\nEOF"]
        with open(path, "w", encoding="ascii", newline="\r\n") as f:
            f.write("\n".join(L) + "\n")


def write_dxf(ctx, path, crs="utm"):
    if crs == "utm":
        T = lambda P: np.asarray(P, float).reshape(-1, 3)
    else:
        def T(P):
            P = np.asarray(P, float).reshape(-1, 3)
            X, Y = ctx.geo.tm(P[:, 0], P[:, 1])
            return np.column_stack([np.asarray(Y), np.asarray(X), P[:, 2]])     # DXF x=동, y=북
    d = DXF()
    d.layer("TRENCH", 30)
    d.layer("STATION", 7)
    d.layer("STATION_TXT", 7)
    d.layer("CLEARANCE", 1)
    d.layer("TITLE", 8)
    used = sorted({u.cls for u in ctx.utils})
    for c in used:
        d.layer(f"UT_{CLASS[c]['en']}", CLASS[c]["aci"])
        d.layer(f"UT_{CLASS[c]['en']}_EDGE", CLASS[c]["aci"])
        d.layer(f"UT_{CLASS[c]['en']}_TXT", CLASS[c]["aci"])
    ol = (ctx.res.get("trench") or {}).get("outline")
    if ol:
        O = np.asarray(ol, float)
        if np.linalg.norm(O[0] - O[-1]) < 1e-6:
            O = O[:-1]
        d.poly3d("TRENCH", T(O), closed=True)
    th = 0.06
    for u in ctx.utils:
        ln = f"UT_{u.info['en']}"
        C = np.column_stack([u.cl[:, :2], u.center_z])
        d.poly3d(ln, T(C))
        # 관 외곽 (평면, ±r)
        P2 = u.cl[:, :2]
        nrm = np.zeros_like(P2)
        for i in range(len(P2)):
            a, b = P2[max(0, i - 1)], P2[min(len(P2) - 1, i + 1)]
            v = b - a
            v = v / (np.linalg.norm(v) + 1e-12)
            nrm[i] = [-v[1], v[0]]
        for sg in (1, -1):
            E = np.column_stack([P2 + sg * u.r * nrm, u.center_z])
            d.poly3d(ln + "_EDGE", T(E))
        m = len(C) // 2
        v = T(C[min(m + 1, len(C) - 1)]) - T(C[max(0, m - 1)])
        rot = math.degrees(math.atan2(v[0, 1], v[0, 0]))
        if rot > 90 or rot < -90:
            rot += 180
        lab = f"{u.id} {u.info['en']} {('W' + str(u.d.get('width_mm'))) if u.kind == 'bundle' else ('D' + str(u.nominal_mm))} L={u.length:.2f}m"
        d.text(ln + "_TXT", T(C[m] + [0, 0, 0])[0] + [0, 0, 0], th, lab, rot)
    for st in ctx.stations:
        p = T([[st["xy"][0], st["xy"][1], st["top"]]])[0]
        d.point("STATION", p)
        d.circle("STATION", p, 0.05)
        d.text("STATION_TXT", p + [0.07, 0.02, 0], 0.05, f"{st['name']} H={st['depth']:.3f}")
        rp = T(st["ref"]["xyz"].reshape(1, 3))[0]
        if st["ref"]["offset_m"]:
            d.line("STATION", rp, p)
    for c in ctx.clearances:
        if c["min_mm"] < ctx.prm["clear_min_mm"]:
            a, b = T(c["pa"])[0], T(c["pb"])[0]
            d.line("CLEARANCE", a, b)
            d.circle("CLEARANCE", T(c["at_utm"])[0], 0.08)
            d.text("CLEARANCE", T(c["at_utm"])[0] + [0.1, -0.1, 0], 0.05, f"{c['a']}-{c['b']} {c['min_mm']:.0f}mm")
    b = ctx.bounds
    tp = T([[b[0][0], b[0][1] - 0.15, ctx.utils[0].ground_z[0] if ctx.utils else 0]])[0]
    crsname = "EPSG:32652 UTM52N" if crs == "utm" else f"EPSG:{ctx.geo.tm_epsg}"
    d.text("TITLE", tp, 0.08, f"kgeoScan Dig {ctx.job_id} {ctx.date_iso} {crsname} m")
    d.write(path)
    return d


def parse_dxf(path):
    """DXF 재해석 검사: 짝(코드/값) 구조, 섹션, POLYLINE/VERTEX/SEQEND 균형, 숫자 → dict."""
    with open(path, encoding="ascii") as f:
        lines = f.read().splitlines()
    errs = []
    if len(lines) % 2:
        errs.append("odd line count")
    pairs = []
    for i in range(0, len(lines) - 1, 2):
        try:
            code = int(lines[i].strip())
        except ValueError:
            errs.append(f"bad group code at line {i + 1}: {lines[i]!r}")
            break
        pairs.append((code, lines[i + 1]))
    sections, ents, layers_def = [], {}, set()
    by_layer = {}
    cur_sec = None
    open_poly = 0
    nvert = 0
    bad_num = 0
    i = 0
    while i < len(pairs):
        c, v = pairs[i]
        if c == 0 and v == "SECTION":
            cur_sec = pairs[i + 1][1] if i + 1 < len(pairs) else None
            sections.append(cur_sec)
        elif c == 0 and v == "ENDSEC":
            cur_sec = None
        elif cur_sec == "TABLES" and c == 0 and v == "LAYER":
            j = i + 1
            while j < len(pairs) and pairs[j][0] != 0:
                if pairs[j][0] == 2:
                    layers_def.add(pairs[j][1])
                j += 1
        elif cur_sec == "ENTITIES" and c == 0:
            ents[v] = ents.get(v, 0) + 1
            j = i + 1
            lay = None
            while j < len(pairs) and pairs[j][0] != 0:
                cc, vv = pairs[j]
                if cc == 8:
                    lay = vv
                if 10 <= cc <= 59:
                    try:
                        if not math.isfinite(float(vv)):
                            bad_num += 1
                    except ValueError:
                        bad_num += 1
                j += 1
            if v != "VERTEX" and v != "SEQEND":
                by_layer[lay] = by_layer.get(lay, 0) + 1
            if lay is not None and lay not in layers_def and lay != "0":
                errs.append(f"layer {lay} not in table")
            if v == "POLYLINE":
                open_poly += 1
            elif v == "VERTEX":
                nvert += 1
                if open_poly != 1:
                    errs.append("VERTEX outside POLYLINE")
            elif v == "SEQEND":
                open_poly -= 1
        i += 1
    if pairs[-1] != (0, "EOF"):
        errs.append("missing EOF")
    if sections != ["HEADER", "TABLES", "ENTITIES"]:
        errs.append(f"sections {sections}")
    if open_poly != 0:
        errs.append("unbalanced POLYLINE/SEQEND")
    if bad_num:
        errs.append(f"{bad_num} non-numeric coordinates")
    return dict(ok=not errs, errors=sorted(set(errs))[:10], entities=ents, layers=by_layer, vertices=nvert, layers_defined=len(layers_def))


LX_NS = "http://www.landxml.org/schema/LandXML-1.2"


def write_landxml(ctx, path):
    ET.register_namespace("", LX_NS)
    now = dt.datetime.now(KST)
    root = ET.Element(f"{{{LX_NS}}}LandXML", {"version": "1.2", "date": now.strftime("%Y-%m-%d"), "time": now.strftime("%H:%M:%S"),
                                              "language": "Korean", "readOnly": "false"})
    units = ET.SubElement(root, f"{{{LX_NS}}}Units")
    ET.SubElement(units, f"{{{LX_NS}}}Metric", {"areaUnit": "squareMeter", "linearUnit": "meter", "volumeUnit": "cubicMeter",
                                                "temperatureUnit": "celsius", "pressureUnit": "milliBars", "diameterUnit": "millimeter",
                                                "angularUnit": "decimal degrees", "directionUnit": "decimal degrees"})
    ET.SubElement(root, f"{{{LX_NS}}}CoordinateSystem", {"name": "WGS 84 / UTM zone 52N", "epsgCode": "32652",
                                                         "horizontalDatum": "WGS84", "horizontalCoordinateSystemName": "UTM52N"})
    ET.SubElement(root, f"{{{LX_NS}}}Project", {"name": ctx.title, "desc": f"kgeoScan job {ctx.job_id}, {ctx.date_iso}"})
    ET.SubElement(root, f"{{{LX_NS}}}Application", {"name": "kgeoScan Dig", "manufacturer": "KgeoSolution", "version": VERSION,
                                                    "desc": "excavation utility record (utility_report.py)"})
    pn_all = ET.SubElement(root, f"{{{LX_NS}}}PipeNetworks", {"name": f"kgeoScan {ctx.job_id}"}) if ctx.utils else None
    net_type = {"water": "water", "sewer": "sanitary"}
    nets = []
    for u in ctx.utils:
        C = np.column_stack([u.cl[:, :2], u.center_z])
        keep = dp_simplify(C, 0.02)
        C = C[keep]
        gz = np.interp(chainage(C[:, :2]), chainage(np.column_stack([u.cl[:, :2]])[keep]) if False else chainage(C[:, :2]), u.ground_z[keep])
        net = ET.SubElement(pn_all, f"{{{LX_NS}}}PipeNetwork", {"name": f"{u.id} {u.info['ko']} {u.dia_text(True)}",
                                                               "pipeNetType": net_type.get(u.cls, "other"),
                                                               "desc": f"class={u.cls}; kind={u.kind}; confidence={u.d.get('confidence', '')}"})
        structs = ET.SubElement(net, f"{{{LX_NS}}}Structs")
        pipes = ET.SubElement(net, f"{{{LX_NS}}}Pipes")
        dia = float(u.d.get("width_mm") if u.kind == "bundle" and u.d.get("width_mm") else (u.nominal_mm or 2000 * u.r))
        names = [f"{u.id}-S{k + 1}" for k in range(len(C))]
        for k, p in enumerate(C):
            sname = names[k]
            s_el = ET.SubElement(structs, f"{{{LX_NS}}}Struct", {"name": sname, "elevRim": f"{gz[k]:.3f}", "elevSump": f"{p[2] - u.r:.3f}",
                                                                 "desc": "vertex"})
            ET.SubElement(s_el, f"{{{LX_NS}}}Center").text = f"{p[1]:.4f} {p[0]:.4f} {p[2]:.4f}"      # LandXML 은 N E Z
            ET.SubElement(s_el, f"{{{LX_NS}}}CircStruct", {"diameter": f"{dia:.1f}"})
            if k > 0:
                ET.SubElement(s_el, f"{{{LX_NS}}}Invert", {"elev": f"{p[2] - u.r:.3f}", "flowDir": "in", "refPipe": f"{u.id}-P{k}"})
            if k < len(C) - 1:
                ET.SubElement(s_el, f"{{{LX_NS}}}Invert", {"elev": f"{p[2] - u.r:.3f}", "flowDir": "out", "refPipe": f"{u.id}-P{k + 1}"})
        for k in range(len(C) - 1):
            a, b = C[k], C[k + 1]
            L = float(np.linalg.norm(b - a))
            hd = float(np.linalg.norm(b[:2] - a[:2]))
            slope = (b[2] - a[2]) / hd if hd > 1e-9 else 0.0
            p_el = ET.SubElement(pipes, f"{{{LX_NS}}}Pipe", {"name": f"{u.id}-P{k + 1}", "refStart": names[k], "refEnd": names[k + 1],
                                                             "length": f"{L:.3f}", "slope": f"{slope:.5f}",
                                                             "desc": f"{u.info['en'].lower()} {u.kind}"})
            attrs = {"diameter": f"{dia:.1f}"}
            ET.SubElement(p_el, f"{{{LX_NS}}}CircPipe", attrs)
            if k == 0:
                fe = ET.SubElement(p_el, f"{{{LX_NS}}}Feature", {"name": "kgeoScan", "code": "utility"})
                for kk, vv in (("id", u.id), ("class", u.cls), ("kind", u.kind), ("nominal_mm", u.nominal_mm),
                               ("material", u.material), ("top_depth_min", u.depth_min), ("top_depth_max", u.depth_max),
                               ("confidence", u.d.get("confidence"))):
                    ET.SubElement(fe, f"{{{LX_NS}}}Property", {"label": kk, "value": "" if vv is None else str(vv)})
        nets.append((u, C))
    pf_all = ET.SubElement(root, f"{{{LX_NS}}}PlanFeatures", {"name": "kgeoScan centerlines"}) if nets else None
    for u, C in nets:
        pf = ET.SubElement(pf_all, f"{{{LX_NS}}}PlanFeature", {"name": f"{u.id} {u.cls}", "desc": "pipe axis (center), UTM52N"})
        cg = ET.SubElement(pf, f"{{{LX_NS}}}CoordGeom")
        il = ET.SubElement(cg, f"{{{LX_NS}}}IrregularLine")
        ET.SubElement(il, f"{{{LX_NS}}}Start").text = f"{C[0, 1]:.4f} {C[0, 0]:.4f} {C[0, 2]:.4f}"
        ET.SubElement(il, f"{{{LX_NS}}}End").text = f"{C[-1, 1]:.4f} {C[-1, 0]:.4f} {C[-1, 2]:.4f}"
        ET.SubElement(il, f"{{{LX_NS}}}PntList3D").text = " ".join(f"{p[1]:.4f} {p[0]:.4f} {p[2]:.4f}" for p in C)
    tree = ET.ElementTree(root)
    ET.indent(tree, space=" ")
    tree.write(path, encoding="utf-8", xml_declaration=True)


LX_METRIC_REQ = {"areaUnit": {"squareMeter", "squareCentimeter", "hectare", "squareMillimeter", "squareKilometer"},
                 "linearUnit": {"meter", "millimeter", "centimeter", "kilometer"},
                 "volumeUnit": {"cubicMeter", "liter", "hectareMeter", "cubicCentimeter", "cubicMillimeter"},
                 "temperatureUnit": {"celsius", "kelvin"},
                 "pressureUnit": {"HPA", "milliBars", "mmHG", "millimeterHG"}}


def validate_landxml(path):
    """LandXML 1.2 구조 검사 (스키마 파일 없이, 쓰는 요소만): 이름공간·필수 속성·열거값·참조·숫자·순서."""
    errs = []
    ns = {"l": LX_NS}
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as e:
        return dict(ok=False, errors=[f"xml parse: {e}"])
    if root.tag != f"{{{LX_NS}}}LandXML":
        errs.append(f"root {root.tag}")
    for a in ("date", "time", "version"):
        if not root.get(a):
            errs.append(f"LandXML@{a} missing")
    if root.get("version") != "1.2":
        errs.append("version != 1.2")
    m = root.find("l:Units/l:Metric", ns)
    if m is None:
        errs.append("Units/Metric missing")
    else:
        for a, allowed in LX_METRIC_REQ.items():
            if m.get(a) not in allowed:
                errs.append(f"Metric@{a}={m.get(a)!r}")
        if m.get("diameterUnit") not in (None, "millimeter", "centimeter", "meter", "kilometer", "inch", "foot", "USSurveyFoot"):
            errs.append("Metric@diameterUnit")
    kids = [c.tag.split("}")[1] for c in root]
    if kids and kids[0] != "Units":
        errs.append("Units should come first")
    nnet = npipe = nstruct = 0
    for net in root.findall("l:PipeNetworks/l:PipeNetwork", ns):
        nnet += 1
        if not net.get("name"):
            errs.append("PipeNetwork@name")
        if net.get("pipeNetType") not in (None, "sanitary", "storm", "water", "other"):
            errs.append(f"pipeNetType {net.get('pipeNetType')}")
        order = [c.tag.split("}")[1] for c in net]
        if order[:2] != ["Structs", "Pipes"]:
            errs.append(f"PipeNetwork children {order}")
        snames = set()
        for s in net.findall("l:Structs/l:Struct", ns):
            nstruct += 1
            if not s.get("name"):
                errs.append("Struct@name")
            snames.add(s.get("name"))
            c = s.find("l:Center", ns)
            try:
                v = [float(x) for x in (c.text or "").split()]
                if len(v) != 3 or not all(math.isfinite(x) for x in v):
                    raise ValueError
            except Exception:
                errs.append(f"Struct {s.get('name')} Center")
            shapes = [x for x in s if x.tag.split("}")[1] in ("CircStruct", "RectStruct", "InletStruct", "OutletStruct", "Connection")]
            if len(shapes) != 1:
                errs.append(f"Struct {s.get('name')} shape count {len(shapes)}")
            sc = [c_.tag.split("}")[1] for c_ in s]
            if sc[0] != "Center":
                errs.append(f"Struct {s.get('name')} Center must be first")
        pnames = set()
        for p in net.findall("l:Pipes/l:Pipe", ns):
            npipe += 1
            pnames.add(p.get("name"))
            for a in ("name", "refStart", "refEnd"):
                if not p.get(a):
                    errs.append(f"Pipe@{a}")
            if p.get("refStart") not in snames or p.get("refEnd") not in snames:
                errs.append(f"Pipe {p.get('name')} ref to missing Struct")
            cp = p.find("l:CircPipe", ns)
            try:
                if cp is None or float(cp.get("diameter")) <= 0:
                    raise ValueError
            except Exception:
                errs.append(f"Pipe {p.get('name')} CircPipe@diameter")
        for inv in net.findall("l:Structs/l:Struct/l:Invert", ns):
            if inv.get("refPipe") not in pnames:
                errs.append(f"Invert refPipe {inv.get('refPipe')}")
            if inv.get("flowDir") not in ("in", "out"):
                errs.append("Invert@flowDir")
    for pl in root.findall("l:PlanFeatures/l:PlanFeature/l:CoordGeom/l:IrregularLine/l:PntList3D", ns):
        v = (pl.text or "").split()
        if len(v) % 3 or len(v) < 6:
            errs.append("PntList3D size")
    return dict(ok=not errs, errors=sorted(set(errs))[:10], networks=nnet, pipes=npipe, structs=nstruct)


def write_geojson(ctx, out_dir):
    feats, feats4326, sfeats = [], [], []
    cap = ctx.captured_iso
    for u in ctx.utils:
        C = np.column_stack([u.cl[:, :2], u.center_z])
        props = {"utility_id": u.id, "class": u.cls, "class_ko": u.info["ko"], "kind": u.kind, "class_source": u.d.get("class_source"),
                 "nominal_mm": u.nominal_mm, "diameter_mm": u.diameter_mm, "width_mm": u.d.get("width_mm"),
                 "top_depth_min": round(float(u.depth_min), 3), "top_depth_max": round(float(u.depth_max), 3),
                 "top_depth_mean": round(float(u.depth_mean), 3), "slope_pct": u.d.get("slope_pct"), "length_m": round(u.length, 2),
                 "confidence": u.d.get("confidence"), "material": u.material or None, "captured_at": cap, "job_id": ctx.job_id,
                 "z_ref": "pipe_axis", "color_hex": u.info["color"]}
        feats.append({"type": "Feature", "id": u.id, "properties": props,
                      "geometry": {"type": "LineString", "coordinates": [[round(p[0], 4), round(p[1], 4), round(p[2], 4)] for p in C]}})
        if ctx.geo.ok:
            lon, lat = ctx.geo.wgs(C[:, 0], C[:, 1])
            feats4326.append({"type": "Feature", "id": u.id, "properties": props,
                              "geometry": {"type": "LineString", "coordinates": [[round(float(a), 9), round(float(b), 9), round(float(z), 4)]
                                                                                 for a, b, z in zip(lon, lat, C[:, 2])]}})
    for st in ctx.stations:
        u = st["u"]
        sfeats.append({"type": "Feature", "id": st["name"], "properties": {
            "station": st["name"], "utility_id": u.id, "class": u.cls, "kind": st["kind"], "station_m": round(st["s"], 3),
            "top_depth_m": round(st["depth"], 3), "ground_z": round(st["ground"], 3), "top_z": round(st["top"], 3),
            "offset_m": None if st["ref"]["offset_m"] is None else round(st["ref"]["offset_m"], 3), "captured_at": cap, "job_id": ctx.job_id},
            "geometry": {"type": "Point", "coordinates": [round(st["xy"][0], 4), round(st["xy"][1], 4), round(st["top"], 4)]}})
    crs = {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::32652"}}
    files = {}
    for name, fs, c in (("utilities.geojson", feats, crs), ("utilities_4326.geojson", feats4326, None), ("stations.geojson", sfeats, crs)):
        if not fs and name != "utilities.geojson":
            continue
        doc = {"type": "FeatureCollection", "name": os.path.splitext(name)[0]}
        if c:
            doc["crs"] = c
        doc["features"] = fs
        p = os.path.join(out_dir, name)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
        files[name] = p
    return files


# ═══════════════════════════════════════════ 10) 동영상 ═══════════════════════════════════════════
def find_ffmpeg():
    for p in (os.environ.get("KGEO_FFMPEG"), shutil.which("ffmpeg")):
        if p and os.path.exists(p):
            return p
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    for g in (os.path.join(ROOT, ".venv_gpu", "Lib", "site-packages", "imageio_ffmpeg", "binaries", "ffmpeg*.exe"),
              os.path.join(ROOT, ".venv_gpu", "lib", "python*", "site-packages", "imageio_ffmpeg", "binaries", "ffmpeg*")):
        hits = sorted(glob.glob(g))
        if hits:
            return hits[-1]
    return None


def _mp4_boxes(b, off, end):
    while off + 8 <= end:
        sz, typ = struct.unpack(">I4s", b[off:off + 8])
        hdr = 8
        if sz == 1:
            sz = struct.unpack(">Q", b[off + 8:off + 16])[0]
            hdr = 16
        elif sz == 0:
            sz = end - off
        if sz < hdr:
            return
        yield typ.decode("latin1"), off, hdr, sz
        off += sz


def mp4_info(path):
    """MP4 머리 분석: 코덱(stsd), H.264 프로필, 크기, 길이, 프레임 수, moov 가 앞에 있는지."""
    b = open(path, "rb").read()
    info = dict(bytes=len(b), codec=None, profile=None, level=None, width=None, height=None, duration_s=None, frames=None, moov_first=None,
                keyframes=None)
    tops = list(_mp4_boxes(b, 0, len(b)))
    names = [t[0] for t in tops]
    if "moov" in names and "mdat" in names:
        info["moov_first"] = names.index("moov") < names.index("mdat")

    def walk(off, end):
        for typ, o, h, sz in _mp4_boxes(b, off, end):
            if typ in ("moov", "trak", "mdia", "minf", "stbl"):
                walk(o + h, o + sz)
            elif typ == "mvhd":
                ver = b[o + h]
                if ver == 1:
                    ts, du = struct.unpack(">IQ", b[o + h + 20:o + h + 32])
                else:
                    ts, du = struct.unpack(">II", b[o + h + 12:o + h + 20])
                info["duration_s"] = round(du / ts, 2) if ts else None
            elif typ == "stsd" and info["codec"] is None:
                e = o + h + 8
                info["codec"] = b[e + 4:e + 8].decode("latin1")
                info["width"], info["height"] = struct.unpack(">HH", b[e + 32:e + 36])
                i = b.find(b"avcC", e, o + sz)
                if i > 0:
                    info["profile"], info["level"] = b[i + 5], b[i + 7]
            elif typ == "stsz" and info["frames"] is None:
                info["frames"] = struct.unpack(">I", b[o + h + 8:o + h + 12])[0]
            elif typ == "stss" and info["keyframes"] is None:
                info["keyframes"] = struct.unpack(">I", b[o + h + 4:o + h + 8])[0]
    for typ, o, h, sz in tops:
        if typ == "moov":
            walk(o + h, o + sz)
    prof = {66: "Baseline", 77: "Main", 100: "High"}.get(info["profile"])
    info["profile_name"] = prof
    info["browser_playable"] = bool(info["codec"] in ("avc1", "avc3") and prof is not None)
    return info


def mp4_faststart(path):
    """moov 를 mdat 앞으로 옮긴다(웹에서 다 받기 전에 재생). stco/co64 오프셋을 moov 크기만큼 민다."""
    b = bytearray(open(path, "rb").read())
    tops = list(_mp4_boxes(b, 0, len(b)))
    names = [t[0] for t in tops]
    if "moov" not in names or "mdat" not in names or names.index("moov") < names.index("mdat"):
        return False
    mv = [t for t in tops if t[0] == "moov"][0]
    moov = bytearray(b[mv[1]:mv[1] + mv[3]])
    shift = len(moov)

    def patch(off, end):
        for typ, o, h, sz in _mp4_boxes(moov, off, end):
            if typ in ("trak", "mdia", "minf", "stbl"):
                patch(o + h, o + sz)
            elif typ == "stco":
                n = struct.unpack(">I", moov[o + h + 4:o + h + 8])[0]
                for k in range(n):
                    p = o + h + 8 + 4 * k
                    v = struct.unpack(">I", moov[p:p + 4])[0] + shift
                    if v >= 2 ** 32:
                        raise OverflowError
                    moov[p:p + 4] = struct.pack(">I", v)
            elif typ == "co64":
                n = struct.unpack(">I", moov[o + h + 4:o + h + 8])[0]
                for k in range(n):
                    p = o + h + 8 + 8 * k
                    moov[p:p + 8] = struct.pack(">Q", struct.unpack(">Q", moov[p:p + 8])[0] + shift)
    try:
        patch(mv[2], len(moov))
    except OverflowError:
        return False
    ft = [t for t in tops if t[0] == "ftyp"]
    head = bytes(b[:ft[0][1] + ft[0][3]]) if ft else b""
    rest = b[len(head):mv[1]] + b[mv[1] + mv[3]:]
    tmp = path + ".fs"
    with open(tmp, "wb") as f:
        f.write(head)
        f.write(moov)
        f.write(rest)
    os.replace(tmp, path)
    return True


def open_writer(path, fps, size, log):
    """avc1(H.264) 먼저, 안 되면 mp4v. 이 PC 의 OpenCV FFMPEG 백엔드는 openh264 DLL 이 없어 H.264 를 못 쓰고,
    Windows 에서는 Media Foundation(MSMF) 백엔드가 H.264 를 대신 만든다(비트레이트 ≈ 1 bit/화소, 조절 불가)."""
    tried = []
    for api, cc in ((cv2.CAP_ANY, "avc1"), (cv2.CAP_MSMF, "H264") if hasattr(cv2, "CAP_MSMF") else (None, None), (cv2.CAP_FFMPEG, "mp4v")):
        if api is None:
            continue
        try:
            w = cv2.VideoWriter(path, api, cv2.VideoWriter_fourcc(*cc), float(fps), size)
        except Exception:
            w = None
        ok = w is not None and w.isOpened()
        be = ""
        if ok:
            try:
                be = w.getBackendName()
            except Exception:
                be = "?"
        tried.append(f"{cc}/{be or api}:{'ok' if ok else 'no'}")
        if ok:
            log(f"video writer: {cc} via {be}")
            return w, dict(fourcc=cc, backend=be, tried=tried)
    return None, dict(fourcc=None, backend=None, tried=tried)


class VideoPainter:
    """제출 동영상 한 장면 그리기 (오른쪽 정보판 + 영상 위 자막·관 겹쳐 그리기)."""

    def __init__(self, ctx, rot_k, src_w, src_h):
        p = ctx.prm
        self.ctx, self.k = ctx, rot_k
        self.OW, self.OH = p["video_w"], p["video_h"]
        rw, rh = (src_h, src_w) if rot_k in (1, 3) else (src_w, src_h)
        s = self.OH / rh
        self.vw, self.vh = int(round(rw * s / 2) * 2), self.OH
        self.scale = s
        self.two = self.vw <= self.OW * 0.5
        if self.two:
            self.vx = (self.OW - self.vw) // 2
            self.panels = [(0, self.vx), (self.vx + self.vw, self.OW - self.vx - self.vw)]
        else:
            self.vx = 0
            self.panels = [(self.vw, self.OW - self.vw)]
        self.src_w, self.src_h = src_w, src_h
        self._static = self._render_static()
        self.loc_local = {u.id: (u.local if u.local is not None else None) for u in ctx.utils}
        self.samp = {u.id: resample_poly(u.local, 0.05) for u in ctx.utils if u.local is not None}

    # 지도 좌표 (UTM → 정보판 미니맵 화소). 굴착과 카메라 길을 함께 담는다
    def _map_setup(self, x, y, w, h, with_cams=True):
        (x0, y0), (x1, y1) = self.ctx.bounds
        if with_cams and getattr(self, "cam_utm", None) is not None and len(self.cam_utm):
            c = self.cam_utm
            x0, y0 = min(x0, float(c[:, 0].min())), min(y0, float(c[:, 1].min()))
            x1, y1 = max(x1, float(c[:, 0].max())), max(y1, float(c[:, 1].max()))
        m = 0.5
        x0, y0, x1, y1 = x0 - m, y0 - m, x1 + m, y1 + m
        s = min((w - 16) / (x1 - x0), (h - 16) / (y1 - y0))
        ox = x + (w - (x1 - x0) * s) / 2
        oy = y + (h - (y1 - y0) * s) / 2
        self.map_rect = (x, y, w, h)
        self.mp = lambda E, N: (ox + (np.asarray(E) - x0) * s, oy + (y1 - np.asarray(N)) * s)
        self.map_s = s

    def _draw_map(self, img, x, y, w, h, with_cams=True, labels=False):
        ctx = self.ctx
        self._map_setup(x, y, w, h, with_cams)
        cv2.rectangle(img, (x, y), (x + w, y + h), (35, 41, 37), -1)
        if with_cams and getattr(self, "cam_utm", None) is not None:
            X, Y = self.mp(self.cam_utm[:, 0], self.cam_utm[:, 1])
            cv2.polylines(img, [np.column_stack([X, Y]).astype(np.int32)], False, (90, 100, 95), 1, cv2.LINE_AA)
        ol = (ctx.res.get("trench") or {}).get("outline")
        if ol:
            O = np.asarray(ol, float)
            X, Y = self.mp(O[:, 0], O[:, 1])
            cv2.polylines(img, [np.column_stack([X, Y]).astype(np.int32)], True, (60, 140, 230), 2, cv2.LINE_AA)
        for u in ctx.utils:
            X, Y = self.mp(u.cl[:, 0], u.cl[:, 1])
            cv2.polylines(img, [np.column_stack([X, Y]).astype(np.int32)], False, hex_bgr(u.info["color"]),
                          max(2, int(2 * u.r * self.map_s)), cv2.LINE_AA)
            if labels:
                blit(img, sprite(u.id, 14, (255, 255, 255), bold=True), X[len(X) // 2] + 6, Y[len(Y) // 2] - 20)
        sb = 1.0 if (w / self.map_s) < 12 else 5.0
        cv2.line(img, (x + 10, y + h - 12), (x + 10 + int(sb * self.map_s), y + h - 12), (200, 205, 200), 2)
        blit(img, sprite(f"{sb:g} m", 11, (154, 165, 159)), x + 14 + int(sb * self.map_s), y + h - 20)
        blit(img, sprite("N↑", 12, (154, 165, 159)), x + w - 30, y + 6)

    def _render_static(self):
        ctx = self.ctx
        V = ctx.views
        vids = np.flatnonzero(V.kind == "video")
        self.cam_utm = ctx.frame.to_utm(V.C[vids]) if len(vids) else None
        img = np.zeros((self.OH, self.OW, 3), np.uint8)
        img[:] = (19, 21, 18)
        for px, pw in self.panels:
            cv2.rectangle(img, (px, 0), (px + pw, self.OH), (26, 30, 28), -1)
        ipx, ipw = self.panels[0]          # 정보(시계·사업명) 판
        mpx, mpw = self.panels[-1]         # 지도·관 목록 판
        cv2.line(img, (mpx, 0), (mpx, self.OH), (12, 65, 194), 3)
        if self.two:
            cv2.line(img, (ipx + ipw, 0), (ipx + ipw, self.OH), (12, 65, 194), 3)
        x = ipx + 18
        y = 22
        blit(img, sprite("kgeoScan Dig · 굴착 3D 기록", 16 if self.two else 15, (251, 146, 60), bold=True), x, y)
        y += 30
        blit(img, sprite(f" {ctx.stage} ", 16, (255, 255, 255), bold=True, bg=(194, 65, 12), pad=(6, 3), radius=6), x, y)
        y += 40
        self.clock_xy = (x, y)
        self.clock_big = 34 if self.two else 26
        y += 22 + self.clock_big + 14
        tsz = 21 if self.two else 17
        for ln in wrap_text(ctx.title, tsz, ipw - 36, bold=True)[:3 if self.two else 2]:
            blit(img, sprite(ln, tsz, (231, 236, 232), bold=True), x, y)
            y += tsz + 9
        y += 6
        ssz = 15 if self.two else 13
        if ctx.geo.lat is not None:
            blit(img, sprite(f"위치 {ctx.geo.lat:.6f}°N {ctx.geo.lon:.6f}°E", ssz, (154, 165, 159)), x, y)
            y += ssz + 8
        cx, cy = ctx.center_tm
        blit(img, sprite(f"TM X {cx:,.2f}  Y {cy:,.2f}", ssz, (154, 165, 159)), x, y)
        y += ssz + 8
        if self.two:
            blit(img, sprite(f"굴착 {ctx.trench_text}", ssz, (154, 165, 159)), x, y)
            y += ssz + 8
            blit(img, sprite(f"시설물 {len(ctx.utils)}개 · 측점 {len(ctx.stations)}개", ssz, (154, 165, 159)), x, y)
            y += ssz + 8
            blit(img, sprite(ctx.device_text, 13, (110, 120, 115)), x, self.OH - 50)
            y = 22
        else:
            y += 8
        mx = mpx + 16
        mw = mpw - 32
        mh = int(min(mw, 320 if self.two else 230))
        self._draw_map(img, mx, y, mw, mh)
        y += mh + 14
        self.rows = []
        lsz = 15 if self.two else 14
        for u in ctx.utils[:8]:
            t = f"{u.id} {u.info['short']} {u.dia_text(True)}  심도 {u.depth_min:.2f}~{u.depth_max:.2f} m"
            self.rows.append((u.id, sprite(t, lsz, (231, 236, 232), bold=True), sprite(t, lsz, (120, 130, 125)), hex_bgr(u.info["color"]), y, mx))
            y += lsz + 12
        blit(img, sprite(f"작업 {ctx.job_id} · {ctx.org or 'kgeoScan'}", 12, (110, 120, 115)), mx, self.OH - 26)
        return img

    def footage(self, frame_bgr, view_i, t_text):
        ctx, V = self.ctx, self.ctx.views
        out = self._static.copy()
        fr = rot_img(frame_bgr, self.k)
        fr = cv2.resize(fr, (self.vw, self.vh), interpolation=cv2.INTER_AREA)
        visible = set()
        H0, W0 = frame_bgr.shape[:2]
        sx, sy = W0 / V.W[view_i], H0 / V.H[view_i]
        best = None
        if ctx.prm["video_ar"]:
            lay = fr.copy()
            for u in ctx.utils:
                L = self.samp.get(u.id)
                if L is None:
                    continue
                P, z = V.project_one(view_i, L)
                P = rot_pts(P * [sx, sy], W0, H0, self.k) * (self.vw / (H0 if self.k in (1, 3) else W0))
                ok = (z > 0.1) & (P[:, 0] > -50) & (P[:, 0] < self.vw + 50) & (P[:, 1] > -50) & (P[:, 1] < self.vh + 50)
                if ok.sum() < 2:
                    continue
                inside = ok & (P[:, 0] >= 0) & (P[:, 0] < self.vw) & (P[:, 1] >= 0) & (P[:, 1] < self.vh)
                if inside.any():
                    visible.add(u.id)
                    dc = np.hypot(P[inside, 0] - self.vw / 2, P[inside, 1] - self.vh / 2).min()
                    if best is None or dc < best[0]:
                        best = (dc, u)
                col = hex_bgr(u.info["color"])
                th = max(3, int(round(u.r * 2 * ctx.views.K[view_i][0, 0] * self.scale / max(float(np.median(z[ok])), 0.3))))
                th = int(min(th, 40))
                segs = []
                cur = []
                for a in range(len(P)):
                    if ok[a]:
                        cur.append(P[a])
                    elif cur:
                        segs.append(cur)
                        cur = []
                if cur:
                    segs.append(cur)
                for sg in segs:
                    if len(sg) >= 2:
                        pts = np.array(sg, np.int32).reshape(-1, 1, 2)
                        cv2.polylines(lay, [pts], False, (255, 255, 255), th + 4, cv2.LINE_AA)
                        cv2.polylines(lay, [pts], False, col, th, cv2.LINE_AA)
                if inside.any():
                    k2 = np.flatnonzero(inside)
                    kk = k2[len(k2) // 2]
                    tag = sprite(f" {u.id} {u.info['short']} {u.dia_text(True)} · {u.depth_mean:.2f} m ", 15, (255, 255, 255),
                                 bold=True, bg=(*hex_rgb(u.info["color"]), 225), pad=(4, 3), radius=5)
                    self._pending = getattr(self, "_pending", [])
                    self._pending.append((tag, P[kk, 0] + 10, P[kk, 1] - 34))
            fr = cv2.addWeighted(lay, 0.55, fr, 0.45, 0)
        out[:, self.vx:self.vx + self.vw] = fr
        boxes = []
        for tag, x, y in getattr(self, "_pending", []):      # 관 이름표: 서로 겹치지 않게 위아래로 민다
            th, tw = tag.shape[:2]
            x = float(np.clip(x, 4, self.vw - tw - 4))
            y = float(np.clip(y, 60, self.vh - 120))
            for _ in range(12):
                hit = [b for b in boxes if x < b[2] and x + tw > b[0] and y < b[3] and y + th > b[1]]
                if not hit:
                    break
                y = hit[0][1] - th - 4 if hit[0][1] - th - 4 >= 60 else hit[0][3] + 4
            boxes.append((x, y, x + tw, y + th))
            blit(out, tag, self.vx + x, y)
        self._pending = []
        # 왼쪽 위: 일시·사업명 (영상 위 반투명 띠)
        band = np.zeros((54, self.vw, 3), np.uint8)
        out[0:54, self.vx:self.vx + self.vw] = cv2.addWeighted(out[0:54, self.vx:self.vx + self.vw], 0.45, band, 0.55, 0)
        blit(out, sprite(t_text, 20, (255, 255, 255), bold=True), self.vx + 14, 6)
        blit(out, sprite(f"{ctx.title} · {ctx.stage}", 13, (220, 226, 222)), self.vx + 14, 33)
        # 아래 자막: 화면 가운데에 가장 가까운 관
        if best is not None:
            u = best[1]
            cap = (f"{u.id} · {u.type_text()} {u.dia_text()}" + (f" · {u.material}" if u.material else "")
                   + f" · 심도 {u.depth_min:.2f}~{u.depth_max:.2f} m · 경사 {u.d.get('slope_pct', 0):+.1f} % · 연장 {u.length:.1f} m")
        else:
            cap = f"굴착 {ctx.trench_text} · 시설물 {len(ctx.utils)}개 · 측점 {len(ctx.stations)}개"
        cs = sprite(cap, 17, (255, 255, 255), bold=True, bg=(18, 20, 19, 200), pad=(12, 7), radius=8)
        if cs.shape[1] > self.vw - 20 and " · 심도" in cap:          # 좁은(세로) 영상이면 두 줄로
            a_, b_ = cap.split(" · 심도", 1)
            l1 = sprite(a_, 16, (255, 255, 255), bold=True, bg=(18, 20, 19, 200), pad=(10, 5), radius=7)
            l2 = sprite("심도" + b_, 16, (255, 255, 255), bold=True, bg=(18, 20, 19, 200), pad=(10, 5), radius=7)
            blit(out, l2, self.vx + max(4, (self.vw - l2.shape[1]) / 2), self.vh - l2.shape[0] - 12)
            blit(out, l1, self.vx + max(4, (self.vw - l1.shape[1]) / 2), self.vh - l2.shape[0] - l1.shape[0] - 16)
        else:
            blit(out, cs, self.vx + (self.vw - cs.shape[1]) / 2, self.vh - cs.shape[0] - 14)
        # 정보판: 시계, 카메라 위치, 보이는 관 강조
        blit(out, sprite(t_text.split(" ")[0], 15, (154, 165, 159)), self.clock_xy[0], self.clock_xy[1])
        blit(out, sprite(t_text.split(" ")[1] if " " in t_text else "", self.clock_big, (255, 255, 255), bold=True), self.clock_xy[0], self.clock_xy[1] + 20)
        c_utm = ctx.frame.to_utm(ctx.views.C[view_i].reshape(1, 3))[0]
        f_utm = ctx.frame.dir_to_utm(ctx.views.R[view_i][:, 2].reshape(1, 3))[0]
        cx, cy = self.mp(c_utm[0], c_utm[1])
        mx, my, mw, mh = self.map_rect
        cx, cy = float(np.clip(cx, mx + 6, mx + mw - 6)), float(np.clip(cy, my + 6, my + mh - 6))
        ang = math.atan2(-f_utm[1], f_utm[0])
        fov = math.radians(32)
        tri = np.array([[cx, cy], [cx + 34 * math.cos(ang - fov), cy + 34 * math.sin(ang - fov)],
                        [cx + 34 * math.cos(ang + fov), cy + 34 * math.sin(ang + fov)]], np.int32)
        ov = out.copy()
        cv2.fillPoly(ov, [tri], (60, 146, 251))
        out[:] = cv2.addWeighted(ov, 0.4, out, 0.6, 0)
        cv2.circle(out, (int(cx), int(cy)), 5, (255, 255, 255), -1, cv2.LINE_AA)
        cv2.circle(out, (int(cx), int(cy)), 5, (12, 65, 194), 2, cv2.LINE_AA)
        for uid, on, off, col, y, x0 in self.rows:
            cv2.rectangle(out, (x0, y + 5), (x0 + 10, y + 17), col, -1)
            blit(out, on if uid in visible else off, x0 + 16, y)
        return out

    def card(self, kind, alpha=1.0):
        ctx = self.ctx
        img = np.zeros((self.OH, self.OW, 3), np.uint8)
        img[:] = (19, 21, 18)
        cv2.rectangle(img, (0, 0), (self.OW, 8), (12, 65, 194), -1)
        x = 70
        if kind == "intro":
            blit(img, sprite("kgeoScan Dig · 굴착 3D 기록 · 제출 동영상", 20, (251, 146, 60), bold=True), x, 60)
            y = 100
            for ln in wrap_text(ctx.title, 40, 760, bold=True)[:2]:
                blit(img, sprite(ln, 40, (255, 255, 255), bold=True), x, y)
                y += 56
            y += 10
            blit(img, sprite(f" {ctx.stage} ", 22, (255, 255, 255), bold=True, bg=(194, 65, 12), pad=(8, 4), radius=8), x, y)
            y += 62
            rows = [("촬영 일시", ctx.datetime_text), ("위치", f"{ctx.geo.lat:.6f}°N, {ctx.geo.lon:.6f}°E" if ctx.geo.lat is not None else "—"),
                    ("좌표", f"{TM_NAME.get(ctx.geo.tm_epsg, 'TM')} X {ctx.center_tm[0]:,.2f} · Y {ctx.center_tm[1]:,.2f}"),
                    ("굴착", ctx.trench_text), ("시설물", f"{len(ctx.utils)}개 · 측점 {len(ctx.stations)}개"),
                    ("장비", ctx.device_text)]
            for a, b in rows:
                blit(img, sprite(a, 18, (154, 165, 159), bold=True), x, y)
                blit(img, sprite(b, 18, (231, 236, 232)), x + 120, y)
                y += 34
            blit(img, sprite("서울시 도로굴착 준공 제출용 기록(굴착 직후 · 매설 현황 · 되메우기 전) — 자동 생성 초안", 14, (110, 120, 115)), x, self.OH - 46)
        else:
            blit(img, sprite("기록 요약", 32, (255, 255, 255), bold=True), x, 60)
            y = 120
            for u in ctx.utils[:8]:
                cv2.rectangle(img, (x, y + 6), (x + 16, y + 22), hex_bgr(u.info["color"]), -1)
                t = (f"{u.id}  {u.type_text()} {u.dia_text()}  ·  심도 {u.depth_min:.2f}~{u.depth_max:.2f} m  ·  경사 {u.d.get('slope_pct', 0):+.1f} %"
                     f"  ·  연장 {u.length:.2f} m  ·  신뢰도 {u.d.get('confidence', 0):.2f}")
                blit(img, sprite(t, 19, (231, 236, 232)), x + 28, y)
                y += 36
            y += 14
            hi = [w for w in ctx.warnings if w["level"] == "high"]
            if hi:
                blit(img, sprite("경고", 20, (248, 113, 113), bold=True), x, y)
                y += 32
                for w in hi[:4]:
                    blit(img, sprite(f"· {w['kind']}: {w['what']} — {w['detail']}", 17, (254, 202, 202)), x, y)
                    y += 28
            blit(img, sprite(f"kgeoScan · 작업 {ctx.job_id} · 생성 {ctx.generated_text} · 측량사 확인 전 초안", 14, (110, 120, 115)), x, self.OH - 46)
        # 오른쪽 위치도
        keep = (getattr(self, "map_rect", None), getattr(self, "mp", None), getattr(self, "map_s", None))
        mx, my, mw, mh = self.OW - 380, 150, 320, 320
        self._draw_map(img, mx, my, mw, mh, with_cams=False, labels=True)
        blit(img, sprite("평면 (북쪽 위)", 13, (154, 165, 159)), mx, my + mh + 8)
        self.map_rect, self.mp, self.map_s = keep
        if alpha < 1:
            img = (img.astype(np.float32) * alpha).astype(np.uint8)
        return img


def make_video(ctx, out_path, log):
    V = ctx.views
    prm = ctx.prm
    info = dict(ok=False)
    if V is None or V.video is None:
        info["reason"] = "rgb.mp4 + odometry.csv 없음"
        return info
    vids = np.flatnonzero(V.kind == "video")
    if not len(vids):
        info["reason"] = "영상 자세 없음"
        return info
    ks = [V.up_rot(i) for i in vids[::10]]
    rot_k = max(set(ks), key=ks.count)
    ff = find_ffmpeg()
    fps_src = V.video["fps"] or 30
    out_fps = prm["video_fps"] if ff else min(prm["video_fps"], 15)     # MSMF 만 있으면 크기 때문에 15 fps
    step = max(1, int(round(fps_src / out_fps)))
    out_fps = fps_src / step
    n_src = min(V.video["frames"], len(vids))
    if n_src / fps_src > prm["video_max_s"]:
        step = int(math.ceil(n_src / (prm["video_max_s"] * out_fps)))
    painter = VideoPainter(ctx, rot_k, V.video["w"], V.video["h"])
    size = (prm["video_w"], prm["video_h"])
    tmpdir = tempfile.mkdtemp(prefix="kgeo_vid_", dir=os.path.dirname(out_path))
    raw = os.path.join(tmpdir, "raw.mp4") if ff else out_path
    w, winfo = open_writer(raw, out_fps, size, log)
    info.update(writer=winfo)
    if w is None:
        info["reason"] = "VideoWriter 를 열 수 없음"
        return info
    t0 = time.time()
    nwr = 0
    n_in = int(prm["intro_s"] * out_fps)
    for f in range(n_in):
        a = min(1.0, (f + 1) / max(1, out_fps * 0.6))
        w.write(painter.card("intro", a))
        nwr += 1
    cap = cv2.VideoCapture(V.video["path"])
    start = ctx.start_dt
    t_first = V.t[vids[0]]
    k = 0
    while k < n_src:
        ok = cap.grab()
        if not ok:
            break
        if k % step == 0:
            ok, fr = cap.retrieve()
            if not ok:
                break
            vi = vids[k]
            tt = start + dt.timedelta(seconds=float(V.t[vi] - t_first)) if start else None
            t_text = tt.strftime("%Y-%m-%d %H:%M:%S") if tt else f"+{(V.t[vi] - t_first):.1f}s"
            w.write(painter.footage(fr, vi, t_text))
            nwr += 1
        k += 1
    cap.release()
    n_out = int(prm["outro_s"] * out_fps)
    for f in range(n_out):
        a = min(1.0, (n_out - f) / max(1, out_fps * 0.5))
        w.write(painter.card("outro", a))
        nwr += 1
    w.release()
    info["frames_written"] = nwr
    info["fps"] = round(out_fps, 3)
    info["render_s"] = round(time.time() - t0, 1)
    info["source_frames"] = n_src
    info["rotation_k"] = rot_k
    raw_info = mp4_info(raw)
    info["cv2_output"] = {k_: raw_info[k_] for k_ in ("codec", "profile_name", "bytes", "moov_first", "browser_playable")}
    if ff:
        cmd = [ff, "-y", "-loglevel", "error", "-i", raw, "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-pix_fmt", "yuv420p",
               "-profile:v", "high", "-movflags", "+faststart", "-an", out_path]
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=900)
            if r.returncode != 0 or not os.path.exists(out_path):
                raise RuntimeError(r.stderr.decode(errors="replace")[-300:])
            info["reencode"] = dict(ffmpeg=ff, crf=24, preset="veryfast")
        except Exception as e:
            log(f"ffmpeg re-encode failed: {str(e)[:200]}; keeping cv2 output")
            shutil.copyfile(raw, out_path)
            info["reencode_error"] = str(e)[:300]
    if os.path.exists(tmpdir):
        shutil.rmtree(tmpdir, ignore_errors=True)
    mi = mp4_info(out_path)
    if mi["codec"] in ("avc1", "avc3") and not mi["moov_first"]:
        info["faststart"] = mp4_faststart(out_path)
        mi = mp4_info(out_path)
    info.update(ok=True, file=os.path.basename(out_path), codec=mi["codec"], profile=mi["profile_name"], width=mi["width"],
                height=mi["height"], duration_s=mi["duration_s"], bytes=mi["bytes"], moov_first=mi["moov_first"],
                browser_playable=mi["browser_playable"], keyframes=mi["keyframes"],
                mbps=round(mi["bytes"] * 8 / 1e6 / max(mi["duration_s"] or 1, 0.1), 2))
    log(f"video: {nwr} frames, {mi['codec']} {mi['profile_name']}, {mi['bytes'] / 1e6:.1f} MB, {mi['duration_s']} s, "
        f"browser={mi['browser_playable']} ({info['render_s']} s)")
    return info


# ═══════════════════════════════════════════ 11) 보고서 HTML ═══════════════════════════════════════════
CSS = r"""
:root{--ink:#1d2321;--muted:#5d6762;--line:#d9ded8;--line2:#aeb6b0;--paper:#fff;--bg:#e4e8e3;--acc:#c2410c;--acc2:#fff4ec;--chip:#eef1ec;
--hi:#dc2626;--mid:#d97706;--low:#64748b;--ok:#15803d}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg);color:var(--ink);font-family:"Pretendard","Malgun Gothic","맑은 고딕","Apple SD Gothic Neo","Noto Sans KR",sans-serif;
font-size:9.6pt;line-height:1.45;-webkit-print-color-adjust:exact;print-color-adjust:exact}
.bar{position:sticky;top:0;z-index:9;display:flex;gap:12px;align-items:center;padding:10px 18px;background:#1d2321;color:#e7ece8;font-size:13px}
.bar b{color:#fb923c}.bar .sp{flex:1}.bar button{font:inherit;padding:6px 14px;border:0;border-radius:6px;background:#c2410c;color:#fff;cursor:pointer}
.bar a{color:#cbd5d0;text-decoration:none;margin-left:10px}
.page{width:210mm;height:297mm;margin:14px auto;padding:13mm 13mm 15mm;background:var(--paper);position:relative;overflow:hidden;
box-shadow:0 2px 14px rgba(0,0,0,.18);break-after:page;page-break-after:always}
.page.land{width:297mm;height:210mm;page:land}
.pf{position:absolute;left:13mm;right:13mm;bottom:7mm;display:flex;justify-content:space-between;font-size:7.5pt;color:var(--muted);
border-top:1px solid var(--line);padding-top:2mm}
@page{size:A4;margin:0}
@page land{size:A4 landscape;margin:0}
@media print{html,body{background:#fff}.bar{display:none}.page{margin:0;box-shadow:none}}
h1{font-size:20pt;margin:0;letter-spacing:-.5px}
h2{font-size:13.5pt;margin:0 0 3mm;padding-bottom:1.6mm;border-bottom:2px solid var(--ink);display:flex;gap:8px;align-items:baseline}
h2 .n{color:var(--acc);font-size:11pt}
h3{font-size:10.5pt;margin:4mm 0 2mm}
.muted{color:var(--muted)}.small{font-size:8pt}.r{text-align:right}.c{text-align:center}.nw{white-space:nowrap}
table{border-collapse:collapse;width:100%}
.t th,.t td{border:1px solid var(--line2);padding:1.3mm 1.6mm;vertical-align:middle}
.t th{background:#f0f2ee;font-weight:700;font-size:8.6pt}
.t td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.chip{display:inline-flex;align-items:center;gap:5px;font-weight:700}
.chip i{display:inline-block;width:10px;height:10px;border-radius:2px}
.lv{display:inline-block;padding:0 6px;border-radius:9px;font-size:7.8pt;font-weight:700;color:#fff;white-space:nowrap}
.lv.high{background:var(--hi)}.lv.mid{background:var(--mid)}.lv.low{background:var(--low)}
/* 표지 */
.cover{padding:0}
.cv-top{background:#1d2321;color:#e7ece8;padding:14mm 14mm 10mm;position:relative}
.cv-top .brand{font-size:10pt;color:#fb923c;font-weight:700;letter-spacing:.3px}
.cv-top h1{font-size:25pt;color:#fff;margin:5mm 0 2mm;line-height:1.2}
.cv-top .sub{font-size:10.5pt;color:#b9c3bd}
.cv-top .site{margin-top:6mm;font-size:15pt;font-weight:700;color:#fff}
.stamp{position:absolute;right:14mm;top:14mm;border:2.5px solid #fb923c;color:#fb923c;padding:2mm 4mm;border-radius:2mm;font-weight:800;
font-size:10pt;transform:rotate(4deg);text-align:center;line-height:1.3}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:3mm;padding:6mm 14mm 0}
.kpi{border:1px solid var(--line);border-radius:2.5mm;padding:3mm 3.5mm;background:#fafbf9}
.kpi .v{font-size:17pt;font-weight:800;letter-spacing:-.5px}.kpi .l{font-size:8pt;color:var(--muted)}
.kpi.warn .v{color:var(--hi)}
.cv-map{margin:5mm 14mm 0;border:1px solid var(--line);border-radius:2.5mm;overflow:hidden;position:relative}
.cv-map .cap{position:absolute;left:3mm;top:2.5mm;background:rgba(255,255,255,.88);padding:1mm 2.5mm;border-radius:1.5mm;font-weight:700;font-size:8.5pt}
.cv-info{display:grid;grid-template-columns:1.25fr 1fr;gap:5mm;margin:5mm 14mm 0;align-items:start}
.kv td{padding:1.1mm 0;border-bottom:1px solid var(--line);font-size:8.8pt}.kv td:first-child{color:var(--muted);width:27mm}
.thumb{width:100%;height:46mm;object-fit:cover;border-radius:2mm;border:1px solid var(--line);display:block}
.cv-foot{position:absolute;left:14mm;right:14mm;bottom:9mm;font-size:7.6pt;color:var(--muted);display:flex;justify-content:space-between}
svg.plan{width:100%;height:auto;display:block}
.pl-lab{font-size:12px;font-weight:800;paint-order:stroke;stroke:#fff;stroke-width:3px}
.pl-st{font-size:10px;font-weight:700;fill:#1d2321;paint-order:stroke;stroke:#fff;stroke-width:3px}
.pl-warn{font-size:11px;font-weight:800;fill:#dc2626;paint-order:stroke;stroke:#fff;stroke-width:3px}
.pl-n{font-size:11px;font-weight:800}.pl-sc{font-size:10px}.pl-co{font-size:9px;fill:#1d2321;paint-order:stroke;stroke:#fff;stroke-width:3px}
svg.sect,svg.prof{width:100%;height:auto;display:block;background:#fff}
.s-t{font-size:10px;fill:#1d2321}.s-ax{font-size:9px;fill:#5d6762}.s-d{font-size:11px;font-weight:800;fill:#1d2321;paint-order:stroke;stroke:#fff;stroke-width:3px}
.s-u{font-size:10px;font-weight:800;paint-order:stroke;stroke:#fff;stroke-width:3px}.s-g{font-size:10px;font-weight:800;paint-order:stroke;stroke:#fff;stroke-width:3px}
.s-h{font-size:11px;font-weight:800;fill:#1d2321}
/* 별표 38 */
.f38 .tag{font-size:9pt}
.f38 .title{text-align:center;font-size:19pt;font-weight:800;letter-spacing:6px;margin:1mm 0 3mm}
.f38 .hdr{display:grid;grid-template-columns:1fr 1fr;border:1.5px solid var(--ink);border-bottom:0}
.f38 .hdr>div{padding:2mm 3mm;border-bottom:1px solid var(--ink);font-size:10pt}
.f38 .hdr .full{grid-column:1/3}
.f38 .hdr .l{font-weight:700;margin-right:3mm}
.f38 .hdr>div+div:not(.full){border-left:1px solid var(--ink)}
.f38 table.form{border:1.5px solid var(--ink)}
.f38 table.form th,.f38 table.form td{border:1px solid var(--ink);text-align:center;padding:1.6mm 1mm;font-size:9.4pt}
.f38 table.form th{background:#f3f4f1}
.f38 table.form td{font-variant-numeric:tabular-nums;font-weight:600}
.f38 .ph{display:grid;grid-template-columns:1fr 1fr;border:1.5px solid var(--ink);border-top:0}
.f38 .ph>div{border-top:1px solid var(--ink)}
.f38 .ph>div:nth-child(2n){border-left:1px solid var(--ink)}
.f38 .ph .img{aspect-ratio:720/480;display:flex;align-items:center;justify-content:center;background:#f6f7f4;overflow:hidden}
.f38 .ph .img img{width:100%;height:100%;object-fit:cover;display:block}
.f38 .ph .img .none{color:var(--muted);font-size:8.5pt;text-align:center;padding:4mm}
.f38 .ph .cap{text-align:center;padding:.7mm;font-weight:700;letter-spacing:3px;border-top:1px solid var(--ink);font-size:9.6pt}
.f38 .note{font-size:8.4pt;margin-top:1.5mm}
.f38 .aux{margin-top:2.5mm;display:grid;grid-template-columns:1.35fr 1fr;gap:3mm;border:1px dashed var(--line2);border-radius:2mm;padding:2mm}
.f38 .aux h4{margin:0 0 1.2mm;font-size:8.8pt;color:var(--acc)}
.f38 .aux .kv td{font-size:7.8pt;padding:.35mm 0;line-height:1.3}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:4mm}
.card{border:1px solid var(--line);border-radius:2mm;padding:2mm;break-inside:avoid}
.warnbox{border-left:4px solid var(--hi);background:#fef2f2;padding:2.5mm 3.5mm;border-radius:1mm;margin:2mm 0}
.okbox{border-left:4px solid var(--ok);background:#f0fdf4;padding:2.5mm 3.5mm;border-radius:1mm;margin:2mm 0}
.infobox{border-left:4px solid var(--acc);background:var(--acc2);padding:2.5mm 3.5mm;border-radius:1mm;margin:2mm 0}
.sum td,.sum th{font-size:8.6pt}
.land .t th,.land .t td{font-size:8.1pt;padding:1.1mm 1.2mm}
.sign{display:grid;grid-template-columns:repeat(3,1fr);gap:4mm;margin-top:4mm}
.sign div{border:1px solid var(--line2);height:24mm;padding:2mm;font-size:8.5pt;color:var(--muted);position:relative}
.sign div span{position:absolute;right:3mm;bottom:2mm}
ul.tight{margin:1mm 0;padding-left:5mm}ul.tight li{margin:.6mm 0}
"""


def _img_tag(path, alt):
    if not path or not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        b = base64.b64encode(f.read()).decode()
    return f'<img src="data:image/jpeg;base64,{b}" alt="{esc(alt)}">'


def build_html(ctx):
    P = ctx.prm
    pages = []

    def page(body, cls="", land=False):
        pages.append((body, cls + (" land" if land else "")))

    trench = ctx.res.get("trench") or {}
    n_hi = sum(1 for w in ctx.warnings if w["level"] == "high")
    # ── 표지 ──
    thumb = None
    if ctx.inputs.get("thumb"):
        im = cv2.imdecode(np.fromfile(ctx.inputs["thumb"], np.uint8), cv2.IMREAD_COLOR)
        if im is not None:
            s = 520 / max(im.shape[:2])
            im = cv2.resize(im, (int(im.shape[1] * s), int(im.shape[0] * s)), interpolation=cv2.INTER_AREA) if s < 1 else im
            thumb = b64jpg(im, 80)
    loc = f"{ctx.geo.lat:.6f}°N, {ctx.geo.lon:.6f}°E" if ctx.geo.lat is not None else "—"
    kv = [("사업명", ctx.title), ("측량 일시", ctx.datetime_text), ("작업 단계", ctx.stage), ("위치(WGS84)", loc),
          ("좌표계", f"{TM_NAME.get(ctx.geo.tm_epsg, 'TM')} (EPSG:{ctx.geo.tm_epsg}) · UTM 52N (EPSG:32652)"),
          ("측량 장비", ctx.device_text), ("측량자", ctx.surveyor or "(서명)"), ("작업 번호", ctx.job_id)]
    body = f"""
<div class="cv-top"><div class="brand">kgeoScan Dig · 굴착 3D 기록</div>
<h1>노출 지하시설물<br>위치측량 성과 보고서</h1>
<div class="sub">공공측량 작업규정 제184~186조 · 별표 38 「노출관로 위치측량 조서」 서식 · 자동 작성 초안</div>
<div class="site">{esc(ctx.title)}</div>
<div class="stamp">초 안<br><span style="font-size:7.5pt;font-weight:700">측량사 검토·서명 전</span></div></div>
<div class="kpis">
<div class="kpi"><div class="v">{len(ctx.utils)}</div><div class="l">노출 시설물</div></div>
<div class="kpi"><div class="v">{len(ctx.stations)}</div><div class="l">측점 (별표 38 조서)</div></div>
<div class="kpi"><div class="v">{fnum(trench.get('length_m'), 1)}×{fnum(trench.get('width_m'), 1)}<span style="font-size:10pt">×{fnum(trench.get('depth_max_m'), 2)} m</span></div><div class="l">굴착 길이×폭×최대 깊이</div></div>
<div class="kpi{' warn' if n_hi else ''}"><div class="v">{len(ctx.warnings)}<span style="font-size:10pt"> (중대 {n_hi})</span></div><div class="l">검토 항목</div></div></div>
<div class="cv-map"><div class="cap">위치도 · 평면 (북쪽 위, UTM 52N)</div>{plan_svg(ctx, 760, 330, labels=True, compact=True)}</div>
<div class="cv-info"><table class="kv">{''.join(f'<tr><td>{esc(a)}</td><td>{esc(b)}</td></tr>' for a, b in kv)}</table>
<div>{f'<img class="thumb" src="{thumb}" alt="스캔 미리보기">' if thumb else '<div class="infobox small">스캔 미리보기 없음</div>'}
<div class="small muted" style="margin-top:2mm">시설물 정보는 공개가 제한될 수 있습니다. 내부 검토용으로 다루세요.</div></div></div>
<div class="cv-foot"><span>kgeoScan utility_report v{VERSION} · 생성 {esc(ctx.generated_text)}</span><span>{esc(ctx.org or 'KgeoSolution')}</span></div>"""
    page(body, "cover")

    # ── 1. 개요 ──
    rows = []
    for u in ctx.utils:
        cs = u.d.get("class_source")
        rows.append(f"""<tr><td><span class="chip"><i style="background:{u.info['color']}"></i>{esc(u.id)}</span></td>
<td>{esc(u.type_text())}<div class="small muted">{'사람 확정' if cs == 'user' else '색 추정' if cs == 'color' else '미확인'}</div></td>
<td class="c">{esc(u.dia_text())}</td><td>{esc(u.material or '—')}</td><td class="num">{u.length:.2f}</td>
<td class="num">{u.depth_min:.3f}</td><td class="num">{u.depth_mean:.3f}</td><td class="num">{u.depth_max:.3f}</td>
<td class="num">{u.d.get('slope_pct', 0):+.2f}</td><td class="num">{u.d.get('confidence', 0):.2f}</td></tr>""")
    wl = "".join(f'<tr><td><span class="lv {w["level"]}">{ {"high": "중대", "mid": "주의", "low": "확인"}[w["level"]]}</span></td>'
                 f'<td class="nw">{esc(w["kind"])}</td><td class="nw">{esc(w["what"])}</td><td>{esc(w["detail"])}</td></tr>' for w in ctx.warnings[:6])
    more = f'<div class="small muted">외 {len(ctx.warnings) - 6}건은 6장에.</div>' if len(ctx.warnings) > 6 else ""
    gr = ctx.res.get("ground") or {}
    body = f"""<h2><span class="n">1</span>개요 · 평면도</h2>
<div class="grid2" style="grid-template-columns:1fr 1fr"><table class="t kv" style="border:0">
<tr><td>굴착 크기</td><td>길이 {fnum(trench.get('length_m'), 2)} m · 폭 {fnum(trench.get('width_m'), 2)} m · 최대 깊이 {fnum(trench.get('depth_max_m'), 2)} m</td></tr>
<tr><td>굴착 체적</td><td>{fnum(trench.get('volume_m3'), 2)} m³ (원지반 아래)</td></tr>
<tr><td>원지반</td><td>{esc(gr.get('method', '—'))} · EL.{fnum(gr.get('z_ref'), 2)} · 잔차 {fnum(gr.get('rms_mm'), 1)} mm · 경사 {fnum(gr.get('slope_deg'), 1)}°</td></tr>
<tr><td>측점</td><td>{len(ctx.stations)}개 ({'엔진' if ctx.station_src == 'engine' else '보고서에서 생성'}) · 간격 ≤ {P['station_step_m']:g} m + 끝점·굴곡·교차</td></tr></table>
<table class="t kv" style="border:0"><tr><td>스캔 범위</td><td>굴착 {fnum((ctx.res.get('quality') or {}).get('trench_coverage_pct'), 1)} % · 가장자리 {fnum((ctx.res.get('quality') or {}).get('rim_coverage_pct'), 1)} %</td></tr>
<tr><td>사진</td><td>{ctx.photo_count}장 (근경·원경·지거측량 기준점·관로 측량점)</td></tr>
<tr><td>처리</td><td>엔진 {fnum(ctx.res.get('seconds'), 1)} s · 점 {(ctx.res.get('quality') or {}).get('points_used', '—'):,}</td></tr>
<tr><td>좌표 연결</td><td>{esc(ctx.frame_text)}</td></tr></table></div>
<h3>노출 시설물</h3>
<table class="t sum"><tr><th>ID</th><th>종류</th><th>관경</th><th>재질</th><th>연장(m)</th><th>심도 최소</th><th>평균</th><th>최대(m)</th><th>경사(%)</th><th>신뢰도</th></tr>{''.join(rows)}</table>
<div class="card" style="margin-top:3mm">{plan_svg(ctx, 760, 300)}</div>
<h3>검토 요약</h3>{'<table class="t sum">' + wl + '</table>' + more if wl else '<div class="okbox">검토 항목 없음</div>'}"""
    page(body)

    # ── 2. 조서 총괄표 (가로) ──
    head = ("<tr><th rowspan=2>측점명</th><th rowspan=2>시설물</th><th rowspan=2>구분</th><th rowspan=2>추가거리<br>(m)</th>"
            "<th colspan=2>좌표 (GRS80)</th><th rowspan=2>관상단<br>표고(m)</th><th rowspan=2>시설물종류</th><th rowspan=2>재질</th>"
            "<th rowspan=2>관경<br>(mm)</th><th rowspan=2>이격거리<br>(m)</th><th rowspan=2>심도<br>(m)</th><th rowspan=2>인접관<br>이격(mm)</th>"
            "<th rowspan=2>사진</th><th rowspan=2>비고</th></tr><tr><th>X(N)</th><th>Y(E)</th></tr>")
    rows = [station_row(ctx, st) for st in ctx.stations]
    chunks = [rows[i:i + P["page_rows"]] for i in range(0, max(1, len(rows)), P["page_rows"])]
    for ci, ch in enumerate(chunks):
        trs = []
        for r in ch:
            nph = sum(1 for k in ("근경사진", "원경사진", "지거측량기준점사진", "관로측량점사진") if r[k])
            low = r["인접관최소이격(mm)"] and float(r["인접관최소이격(mm)"]) < P["clear_min_mm"]
            trs.append(f"<tr><td class='c nw'><b>{esc(r['측점명'])}</b></td><td class='c'>{esc(r['시설물'])}</td><td class='c nw'>{esc(r['측점구분'])}</td>"
                       f"<td class='num'>{esc(r['추가거리(m)'])}</td><td class='num'>{esc(r['X(N)'])}</td><td class='num'>{esc(r['Y(E)'])}</td>"
                       f"<td class='num'>{esc(r['관상단표고(m)'])}</td><td>{esc(r['시설물종류'])}</td><td>{esc(r['재질'] or '—')}</td>"
                       f"<td class='num'>{esc(r['관경(mm)'])}</td><td class='num'>{esc(r['이격거리(m)'] or '—')}</td><td class='num'><b>{esc(r['심도(m)'])}</b></td>"
                       f"<td class='num' style='{'color:#dc2626;font-weight:800' if low else ''}'>{esc(r['인접관최소이격(mm)'] or '—')}</td>"
                       f"<td class='c'>{nph}/4</td><td class='small'>{esc(r['비고'])}</td></tr>")
        body = (f"<h2><span class='n'>2</span>노출관로 위치측량 조서 — 총괄표 {f'({ci + 1}/{len(chunks)})' if len(chunks) > 1 else ''}</h2>"
                f"<div class='small muted' style='margin:-1mm 0 2mm'>사업명 {esc(ctx.title)} · 측량일 {esc(ctx.date_text)} · 좌표 {TM_NAME.get(ctx.geo.tm_epsg, 'TM')} "
                f"(EPSG:{ctx.geo.tm_epsg}), 평면 소수 셋째·높이 둘째 자리(제186조③) · 심도 = 원지반 ~ 관 상단(제184조③), mm 단위(제185조②)</div>"
                f"<table class='t'>{head}{''.join(trs)}</table>"
                f"<div class='small muted' style='margin-top:2mm'>이격거리: 지거측량 기준점에서 관 중심까지 수평거리. 기준점이 없으면 굴착 경계(원지반)를 임시 기준으로 씀 — "
                f"경계석 등 영구 기준점을 지정하면 다시 계산됩니다. 인접관 이격: 측점 단면에서 관 겉면 사이 최소 거리.</div>")
        page(body, land=True)

    # ── 3. 측점별 별표 38 ──
    for st in ctx.stations:
        u = st["u"]
        X, Y = ctx.geo.tm(st["xy"][0], st["xy"][1])
        cells = []
        for typ, lab in PHOTO_TYPES:
            f = st.get("photo_paths", {}).get(typ)
            tag = _img_tag(f, f"{st['name']} {lab}") if f else None
            why = "해당 시점의 사진 없음" if ctx.views is not None else "스캔에 영상·사진이 없음"
            cells.append(f"<div><div class='img'>{tag or f'<div class=none>{why}<br>현장 사진을 붙이세요</div>'}</div><div class='cap'>{lab}</div></div>")
        gaps = [g for g in section_gaps(st.get("hits") or []) if g[0] is u or g[1] is u]
        gtxt = ", ".join(f"{(g[1] if g[0] is u else g[0]).id} {g[2]:.0f} mm" for g in sorted(gaps, key=lambda g: g[2])[:3]) or "단면 안 다른 관 없음"
        offs = "—" if st["ref"]["offset_m"] is None else f"{st['ref']['offset_m']:.3f}"
        body = f"""<div class="f38"><div class="tag">[ 별표 38 ]</div><div class="title">노출관로 위치측량 조서</div>
<div class="hdr"><div class="full"><span class="l">사 업 명 :</span>{esc(ctx.title)}</div>
<div><span class="l">측량날짜</span>{ctx.date_parts[0]} 년 {ctx.date_parts[1]} 월 {ctx.date_parts[2]} 일</div><div><span class="l">측점명</span>{esc(st['name'])} <span class="muted small">({esc(st['sta'])})</span></div></div>
<table class="form"><tr><th colspan="2">좌표 (GRS80)</th><th rowspan="2">시설물종류</th><th rowspan="2">재질</th><th rowspan="2">관경</th><th rowspan="2">이격거리</th><th rowspan="2">심도</th></tr>
<tr><th>X(N)</th><th>Y(E)</th></tr>
<tr><td>{float(X):,.3f}</td><td>{float(Y):,.3f}</td><td>{esc(u.type_text())}</td><td>{esc(u.material or '')}</td><td>{esc(u.dia_text(True))}</td><td>{offs} m</td><td>{st['depth']:.3f} m</td></tr></table>
<div class="ph">{''.join(cells)}</div>
<div class="note">* 보드판을 활용한 사진촬영(휴대폰 어플 사용가능) — 전자 보드판 자동 기입(kgeoScan)</div>
<div class="aux"><div>{section_svg(ctx, st, 470, 190)}</div><div><h4>보조 정보 (kgeoScan 자동, 조서 서식 밖)</h4><table class="kv">
<tr><td>측점 구분</td><td>{esc(ST_KIND_KO.get(st['kind'], st['kind']))}{' · ' + esc(st['other']) + ' 교차' if st.get('other') else ''}</td></tr>
<tr><td>관상단 표고</td><td>EL. {st['top']:.2f} m (원지반 EL. {st['ground']:.2f})</td></tr>
<tr><td>UTM 52N</td><td>E {st['xy'][0]:,.3f} · N {st['xy'][1]:,.3f}</td></tr>
<tr><td>지거 기준</td><td>{esc(st['ref']['desc'])} {esc(st['ref']['label'])}</td></tr>
<tr><td>인접관 이격</td><td>{esc(gtxt)}</td></tr>
<tr><td>관경 실측</td><td>{esc(u.diameter_mm)} mm ± {esc(u.d.get('diameter_rms_mm') or '—')} · 보이는 호 {esc(u.d.get('visible_arc_deg') or '—')}°</td></tr>
<tr><td>신뢰도</td><td>{u.d.get('confidence', 0):.2f} · 종류 {'사람 확정' if u.d.get('class_source') == 'user' else '색 추정 — 확인 필요'}</td></tr>
<tr><td>측량자</td><td>{esc(ctx.surveyor or '')}&nbsp;</td></tr></table></div></div></div>"""
        page(body)

    # ── 4. 단면도 (한 쪽 8개) ──
    for i in range(0, len(ctx.stations), 8):
        grp = ctx.stations[i:i + 8]
        cards = "".join(f"<div class='card'>{section_svg(ctx, st, 520, 320)}</div>" for st in grp)
        page(f"<h2><span class='n'>4</span>측점 단면도 {f'({i // 8 + 1}/{math.ceil(len(ctx.stations) / 8)})' if len(ctx.stations) > 8 else ''}</h2>"
             f"<div class='small muted' style='margin:-1mm 0 2mm'>관 진행 방향(시점→종점)으로 본 연직 단면. 회색 점 = 단면 ±{P['slab_m'] * 100:.0f} cm 안의 스캔 점, "
             f"갈색 = 원지반 밖 흙, 숫자 = 관 겉면 사이 거리(빨강은 기준 {P['clear_min_mm']} mm 미만).</div><div class='grid2'>{cards}</div>")
    # ── 5. 종단면도 ──
    for i in range(0, len(ctx.utils), 4):
        grp = ctx.utils[i:i + 4]
        page(f"<h2><span class='n'>5</span>종단면도</h2>" + "".join(f"<div class='card' style='margin-bottom:3mm'>{profile_svg(ctx, u, 760, 225)}</div>" for u in grp))
    # ── 6. 이격·심도 검토 ──
    mc = {k: v["min_cover"] for k, v in CLASS.items()}
    if isinstance(P.get("min_cover"), dict):
        mc.update(P["min_cover"])
    crow = "".join(f"<tr><td>{esc(c['a'])} ↔ {esc(c['b'])}</td><td>{esc(ctx.umap[c['a']].type_text())} / {esc(ctx.umap[c['b']].type_text())}</td>"
                   f"<td class='num' style='{'color:#dc2626;font-weight:800' if c['min_mm'] < P['clear_min_mm'] else ''}'>{esc(clear_text(c['min_mm']).replace(' mm', ''))}</td>"
                   f"<td class='num'>{P['clear_min_mm']}</td><td>{'위아래' if c.get('crossing') else '옆'}</td><td class='small'>E {c['at_utm'][0]:,.2f} · N {c['at_utm'][1]:,.2f}</td>"
                   f"<td>{'엔진' if c['source'] == 'engine' else '계산'}</td></tr>" for c in ctx.clearances)
    drow = "".join(f"<tr><td><span class='chip'><i style='background:{u.info['color']}'></i>{esc(u.id)}</span></td><td>{esc(u.type_text())}</td>"
                   f"<td class='num'>{u.depth_min:.3f}</td><td class='num'>{u.depth_mean:.3f}</td><td class='num'>{u.depth_max:.3f}</td>"
                   f"<td class='num'>{fnum(mc.get(u.cls), 1)}</td><td>{'<b style=color:#d97706>부족</b>' if mc.get(u.cls) and u.depth_min < mc[u.cls] else ('—' if not mc.get(u.cls) else '충족')}</td></tr>"
                   for u in ctx.utils)
    wl = "".join(f'<tr><td><span class="lv {w["level"]}">{ {"high": "중대", "mid": "주의", "low": "확인"}[w["level"]]}</span></td>'
                 f'<td class="nw">{esc(w["kind"])}</td><td class="nw">{esc(w["what"])}</td><td>{esc(w["detail"])}</td></tr>' for w in ctx.warnings)
    page(f"""<h2><span class="n">6</span>이격거리 · 매설 깊이 검토</h2>
<div class="infobox small">기준값은 참고 기본값입니다(이격 {P['clear_min_mm']} mm, 최소 토피는 종류별 차도 가정). 관리기관·관종 기준으로 바꾸려면
<code>--params '{{"clear_min_mm": 300, "min_cover": {{"water": 1.2}}}}'</code>. 검토 결과는 측량사·관리기관이 확정합니다.</div>
<h3>관 사이 최소 이격 (겉면 사이 3D 거리, {P['clear_report_mm']} mm 이내 쌍)</h3>
{'<table class="t"><tr><th>쌍</th><th>종류</th><th>최소 이격(mm)</th><th>기준(mm)</th><th>배치</th><th>위치(UTM)</th><th>출처</th></tr>' + crow + '</table>' if crow else '<div class="okbox">1 m 안에 가까운 관 쌍 없음</div>'}
<h3>매설 깊이 (원지반 ~ 관 상단)</h3>
<table class="t"><tr><th>ID</th><th>종류</th><th>최소(m)</th><th>평균(m)</th><th>최대(m)</th><th>참고 최소 토피(m)</th><th>판정</th></tr>{drow}</table>
<div class="small muted" style="margin-top:2mm">'위아래' = 가장 가까운 곳에서 한 관이 다른 관 위를 지남(교차), '옆' = 나란히 놓임. 접촉·겹침은 0 mm 이하.</div>""")
    wrows = [w for w in ctx.warnings]
    for i in range(0, max(1, len(wrows)), 20):
        part = wrows[i:i + 20]
        trs = "".join(f'<tr><td><span class="lv {w["level"]}">{ {"high": "중대", "mid": "주의", "low": "확인"}[w["level"]]}</span></td>'
                      f'<td class="nw">{esc(w["kind"])}</td><td class="nw">{esc(w["what"])}</td><td>{esc(w["detail"])}</td></tr>' for w in part)
        page(f"<h2><span class='n'>6</span>검토 항목 전체 {f'({i // 20 + 1}/{math.ceil(len(wrows) / 20)})' if len(wrows) > 20 else ''}</h2>"
             + (f'<table class="t sum"><tr><th>등급</th><th>항목</th><th>대상</th><th>내용</th></tr>{trs}</table>' if trs else '<div class="okbox">검토 항목 없음</div>')
             + '<div class="small muted" style="margin-top:2mm">중대 = 기준 위반 가능(현장 확인 필수) · 주의 = 기준 근처·정확도 문제 · 확인 = 사람이 확정할 항목</div>')
    # ── 7. 정확도 ──
    acc = ctx.accuracy
    urow = "".join(f"<tr><td>{esc(u.id)}</td><td class='num'>{esc(u.diameter_mm)}</td><td class='num'>{esc(u.d.get('diameter_rms_mm') or '—')}</td>"
                   f"<td class='num'>{esc(u.d.get('visible_arc_deg') or '—')}</td><td class='num'>{esc(u.d.get('fit_rms_mm') or '—')}</td>"
                   f"<td class='num'>{u.d.get('confidence', 0):.2f}</td><td class='small'>{esc(u.d.get('notes') or '')}</td></tr>" for u in ctx.utils)
    cps = acc["checkpoints"]
    cprow = "".join(f"<tr><td>{esc(c.get('id'))}</td><td class='num'>{c['dE'] * 1000:+.0f}</td><td class='num'>{c['dN'] * 1000:+.0f}</td>"
                    f"<td class='num'>{c['dZ'] * 1000:+.0f}</td><td class='num'>{c['dH'] * 1000:.0f}</td></tr>" for c in cps)
    verdict = ("<div class='okbox'>검사점 수평 RMSE {:.1f} cm ≤ 허용 {:.0f} cm (제186조③) — 충족</div>".format(acc["rmse_h"] * 100, P["abs_tol_m"] * 100)
               if cps and acc["rmse_h"] is not None and acc["rmse_h"] <= P["abs_tol_m"] else
               "<div class='warnbox'>검사점 잔차가 허용오차보다 큼 — 기준점 재측량 필요</div>" if cps else
               f"<div class='warnbox'><b>검사점 없음.</b> 절대 위치는 {esc(acc['abs_src'])} 수준(약 ±{fnum(acc['abs_m'], 1)} m)입니다. "
               f"제186조③의 10 cm 를 맞추려면 기준 표식(AprilTag) 3~4개를 TS·GNSS로 측량하거나 RTK(VRS)를 연결하세요. "
               f"심도·관경·이격 같은 <b>상대 측정</b>은 같은 스캔 안의 값이라 절대 위치 오차와 무관합니다.</div>")
    page(f"""<h2><span class="n">7</span>정확도</h2>
<h3>측량 방법</h3><ul class="tight">
<li>장비: {esc(ctx.device_text)} — LiDAR 깊이 + ARKit 시각·관성 위치추정으로 굴착부를 3D 스캔 (되메우기 전 노출 상태, 제179·185조)</li>
<li>처리: 메시 → 원지반 추정({esc((ctx.res.get('ground') or {}).get('method', '—'))}, 잔차 {fnum((ctx.res.get('ground') or {}).get('rms_mm'), 1)} mm) → 단면 원호 맞춤 → 중심선·공칭경 → 관 상단 깊이 (utility_extract.py)</li>
<li>좌표: 스캔 로컬 → UTM 52N ({esc(ctx.frame_text)}) → {TM_NAME.get(ctx.geo.tm_epsg, 'TM')} (pyproj)</li>
<li>사진: 스캔 영상·고해상도 사진 중 측점이 보이는 프레임을 자세로 골라(가려짐은 깊이 지도로 검사) 자르고 측점을 표시</li></ul>
<h3>위치 정확도 (제186조③ 허용오차 {P['abs_tol_m'] * 100:.0f} cm)</h3>
{('<table class="t"><tr><th>검사점</th><th>ΔE(mm)</th><th>ΔN(mm)</th><th>ΔZ(mm)</th><th>수평(mm)</th></tr>' + cprow + '</table>') if cps else ''}
{verdict}
<table class="t kv" style="border:0"><tr><td>위치 출처</td><td>{esc(acc['abs_src'])}</td></tr><tr><td>GPS 수평 정확도</td><td>{fnum(acc['gps_h'], 1)} m</td></tr>
<tr><td>로컬↔UTM 맞춤</td><td>{esc(ctx.frame_text)}</td></tr></table>
<h3>관 맞춤 품질 (상대 측정)</h3>
<table class="t"><tr><th>ID</th><th>관경(mm)</th><th>관경 RMS(mm)</th><th>보이는 호(°)</th><th>맞춤 잔차(mm)</th><th>신뢰도</th><th>비고</th></tr>{urow}</table>
<div class="small muted" style="margin-top:2mm">예상 정확도(기획서 05): 관 중심선 상대 ±1~2 cm, 깊이 ±1~2 cm, 관경 ±1~3 cm(공칭경 스냅). 실측 검증 전 값입니다.</div>""")
    # ── 8. 산출물·근거·서명 ──
    frow = "".join(f"<tr><td><code>{esc(k)}</code></td><td>{esc(v[0])}</td><td class='num'>{esc(v[1])}</td></tr>" for k, v in ctx.files_table.items())
    page(f"""<h2><span class="n">8</span>산출물 · 좌표계 · 근거 규정</h2>
<table class="t"><tr><th>파일</th><th>내용</th><th>크기</th></tr>{frow}</table>
<h3>좌표계</h3><ul class="tight"><li>조서 좌표: {TM_NAME.get(ctx.geo.tm_epsg, 'TM')} (EPSG:{ctx.geo.tm_epsg}), X=북·Y=동, m</li>
<li>DXF·GeoJSON·LandXML: UTM 52N (EPSG:32652), Z 위, m · <code>utilities_tm.dxf</code> 는 EPSG:{ctx.geo.tm_epsg} · <code>utilities_4326.geojson</code> 은 경위도</li>
<li>높이: 스캔 기준 높이(georef elev). 검사점·수준측량으로 보정 전에는 참고값</li></ul>
<h3>근거 (공공측량 작업규정, 국토지리정보원 고시 제2025-2092호)</h3><ul class="tight">
<li>제179조 — 공사가 끝나기 전, 시설물이 노출된 상태에서 측량</li>
<li>제184조 — 평면위치는 관로 중심선, 깊이는 지표면에서 시설물 상단까지. 간격 20 m 이하, 교차·분기·곡선 등은 따로</li>
<li>제185조 — 되메우기 전 이격거리·깊이 mm 실측, 곡선·관종·관경 변경점 별도 측정, 근경·원경 사진, 사진은 별표 38 조서에 정리</li>
<li>제186조 — 위치측량 허용오차 10 cm, 평면좌표 소수 셋째·높이 소수 둘째 자리</li>
<li>서울시 도로굴착(2025-10~) — 굴착 직후·매설 현황·되메우기 전 동영상 제출 → <code>submission.mp4</code></li></ul>
<div class="infobox small">이 보고서는 스마트폰 3D 스캔에서 자동으로 만든 초안입니다. 작업규정은 점군·모바일 측량을 따로 정하지 않으므로, 공공측량 성과로 쓰려면
성과심사기관과 사전 협의하고 지하시설물측량 등록업체의 확인을 받으세요.</div>
<div class="sign"><div>측량자 (소속·성명)<span>(서명)</span></div><div>검토자<span>(서명)</span></div><div>확인자 (관리기관)<span>(서명)</span></div></div>""")

    total = len(pages)
    out = [f"<!doctype html><html lang='ko'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>"
           f"<title>노출관로 위치측량 보고서</title><style>{CSS}</style></head><body>"
           f"<div class='bar'><b>kgeoScan Dig</b><span>{esc(ctx.title)} · {total}쪽</span><span class='sp'></span>"
           f"<a href='stations.csv'>CSV</a><a href='utilities.dxf'>DXF</a><a href='utilities.landxml'>LandXML</a><a href='utilities.geojson'>GeoJSON</a>"
           f"<a href='submission.mp4'>동영상</a><button onclick='window.print()'>인쇄 · PDF 저장</button></div>"]
    for k, (b, cls) in enumerate(pages):
        foot = "" if "cover" in cls else f"<div class='pf'><span>kgeoScan Dig · {esc(ctx.title)} · {esc(ctx.job_id)}</span><span>{k + 1} / {total}</span></div>"
        out.append(f"<section class='page {cls}'>{b}{foot}</section>")
    out.append("</body></html>")
    return "".join(out), total


# ═══════════════════════════════════════════ 12) 묶기 ═══════════════════════════════════════════
class Ctx:
    pass


def _parse_time(s):
    if not s:
        return None
    try:
        t = dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=dt.timezone.utc)
        return t.astimezone(KST)
    except Exception:
        return None


def _hsize(n):
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB":
            return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024


def build_report(utilities, job_dir=None, out_dir="report", data=None, title=None, surveyor=None, org=None, stage="되메우기 전",
                 params=None, video=True, photos=True, log=_log_default):
    t0 = time.time()
    prm = dict(DEFAULTS)
    prm.update(params or {})
    os.makedirs(out_dir, exist_ok=True)
    res = _read_json(utilities)
    if not res:
        raise SystemExit(f"cannot read {utilities}")
    inf = find_inputs(utilities, job_dir, data)
    ctx = Ctx()
    ctx.res, ctx.prm, ctx.inputs = res, prm, inf
    ctx.job_id = str(res.get("job_id") or (inf["job"] or {}).get("job_id") or "")
    meta = inf["meta"] or {}
    job = inf["job"] or {}
    ctx.title = title or job.get("title") or job.get("site") or (meta.get("title") if meta.get("title") and "스캔" not in meta.get("title", "") else None) \
        or f"굴착 기록 {ctx.job_id}"
    ctx.surveyor, ctx.org, ctx.stage = surveyor, org, stage
    start = _parse_time(meta.get("created_at")) or _parse_time(job.get("created_at")) or _parse_time(res.get("captured_at"))
    if start is None:
        start = dt.datetime.fromtimestamp(os.path.getmtime(utilities), KST)
    ctx.start_dt = start
    ctx.captured_iso = start.isoformat(timespec="seconds")
    ctx.date_iso = start.strftime("%Y-%m-%d")
    ctx.date_text = start.strftime("%Y. %m. %d.")
    ctx.date_parts = (start.strftime("%Y"), start.strftime("%m"), start.strftime("%d"))
    ctx.datetime_text = start.strftime("%Y-%m-%d %H:%M") + " (KST)"
    ctx.generated_text = dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    dev = meta.get("device")
    dev_name = IPHONE_NAMES.get(dev, dev)
    ctx.device_text = (f"{dev_name} LiDAR · kgeoScan {meta.get('app_version', '')}".strip() if dev else "스마트폰 LiDAR 스캔 (kgeoScan)")
    # 좌표 연결: 중심선 쌍으로 맞춤(엔진과 같은 변환) → 없으면 georef
    frame = None
    pairs_l, pairs_u = [], []
    for u in res.get("utilities") or []:
        if u.get("centerline_local") and len(u["centerline_local"]) == len(u.get("centerline") or []):
            pairs_l += u["centerline_local"]
            pairs_u += u["centerline"]
    if len(pairs_l) >= 2:
        frame = LocalFrame.fit(pairs_l, pairs_u)
        ctx.frame_text = f"중심선 쌍 {len(pairs_l)}점 맞춤, 잔차 {frame.rms * 1000:.1f} mm"
        if frame.rms > 0.05 and inf["georef"] and Transformer:
            frame = LocalFrame.from_georef(inf["georef"])
            ctx.frame_text = "georef(lon/lat/heading) — 중심선 쌍 맞춤 잔차가 커서"
    elif inf["georef"] and Transformer:
        frame = LocalFrame.from_georef(inf["georef"])
        ctx.frame_text = "georef(lon/lat/heading)"
    else:
        ctx.frame_text = "로컬 좌표 없음 (사진·동영상 겹쳐 그리기 생략)"
    ctx.frame = frame
    ctx.utils = build_utils(res, frame)
    ctx.umap = {u.id: u for u in ctx.utils}
    ol_ = (res.get("trench") or {}).get("outline")
    if ctx.utils:
        allp = np.vstack([u.cl for u in ctx.utils])
    elif ol_:
        allp = np.asarray(ol_, float)
        log("no utilities: trench-only record")
    else:
        raise SystemExit("no utilities and no trench outline")
    ctx.geo = Geo(allp.mean(0), prm.get("tm_epsg"))
    cx, cy = ctx.geo.tm(allp[:, 0].mean(), allp[:, 1].mean())
    ctx.center_tm = (float(cx), float(cy))
    controls = [dict(id=c.get("id"), xyz=c.get("xyz_utm"), desc=c.get("desc")) for c in (res.get("control_points") or []) if c.get("xyz_utm")]
    ctx.clearances = compute_clearances(ctx.utils, res, prm)
    ctx.stations, ctx.station_src = build_stations(ctx.utils, res, prm, controls)
    tr = res.get("trench") or {}
    ctx.trench_text = f"{fnum(tr.get('length_m'), 1)}×{fnum(tr.get('width_m'), 1)} m, 깊이 {fnum(tr.get('depth_max_m'), 2)} m"
    # 정확도
    fx = meta.get("fix") or {}
    cps = []
    for c in (res.get("accuracy") or {}).get("checkpoints") or []:
        try:
            m_, r_ = np.asarray(c["measured_utm"], float), np.asarray(c["ref_utm"], float)
            d = m_ - r_
            cps.append(dict(id=c.get("id"), dE=d[0], dN=d[1], dZ=d[2], dH=float(np.hypot(d[0], d[1]))))
        except Exception:
            pass
    rtk = (res.get("accuracy") or {}).get("method") or ((res.get("georef") or {}).get("source"))
    gps_h = fx.get("h_acc")
    ctx.accuracy = dict(checkpoints=cps, rmse_h=float(np.sqrt(np.mean([c["dH"] ** 2 for c in cps]))) if cps else None,
                        gps_h=gps_h, abs_m=(float(np.sqrt(np.mean([c["dH"] ** 2 for c in cps]))) if cps else (gps_h if gps_h else None)),
                        abs_src=("검사점" if cps else (str(rtk) if rtk else ("폰 GPS" if gps_h else "미상"))))
    ctx.warnings = build_warnings(ctx)
    ctx.bounds = plan_bounds(ctx)
    # 배경: 정사영상 > 점군 위에서 본 그림
    ctx.las = None
    ctx.plan_bg = None
    zr = (res.get("ground") or {}).get("z_ref")
    if inf["las"]:
        ctx.las = load_las(inf["las"], ctx.bounds, log, zmax=(zr + 0.5) if zr is not None else None)
        if ctx.las is not None and len(ctx.las["P"]) < 50:
            ctx.las = None
    bg = ortho_raster(inf["ortho"], ctx.bounds) if inf["ortho"] else None
    if bg is None and ctx.las is not None:
        bg = plan_raster(ctx.las, ctx.bounds)
    if bg is not None:
        ctx.plan_bg = b64jpg(bg, 78)
    # 사진
    conv = ((inf["result"] or {}).get("fusion") or {}).get("convention")
    ctx.views = load_views(inf["data"], log, conv) if (photos or video) and frame is not None else None
    ctx.view_imgs = {}
    ctx.photo_count = 0
    if photos and ctx.views is not None:
        select_photos(ctx, log)
        pdir = os.path.join(out_dir, "photos")
        os.makedirs(pdir, exist_ok=True)
        for old in glob.glob(os.path.join(pdir, "No*_*.jpg")):      # 지난 실행의 사진이 섞이지 않게
            os.remove(old)
        for st in ctx.stations:
            st["photo_paths"], st["photo_files"] = {}, {}
            for typ, _ in PHOTO_TYPES:
                fn = f"{st['name'].replace('.', '')}_{typ}.jpg"
                pth = render_photo(ctx, st, typ, os.path.join(pdir, fn))
                if pth:
                    st["photo_paths"][typ] = pth
                    st["photo_files"][typ] = f"photos/{fn}"
                    ctx.photo_count += 1
    for st in ctx.stations:
        st.setdefault("photo_paths", {})
        st.setdefault("photo_files", {})
        st["hits"] = section_hits(ctx.utils, st)
    ctx.view_imgs = {}
    log(f"stations {len(ctx.stations)} ({ctx.station_src}), clearances {len(ctx.clearances)}, warnings {len(ctx.warnings)}, photos {ctx.photo_count}")
    # 내보내기
    checks = {}
    write_csv(ctx, os.path.join(out_dir, "stations.csv"))
    write_dxf(ctx, os.path.join(out_dir, "utilities.dxf"), "utm")
    checks["dxf"] = parse_dxf(os.path.join(out_dir, "utilities.dxf"))
    if ctx.geo.ok:
        write_dxf(ctx, os.path.join(out_dir, "utilities_tm.dxf"), "tm")
        checks["dxf_tm"] = parse_dxf(os.path.join(out_dir, "utilities_tm.dxf"))
    write_landxml(ctx, os.path.join(out_dir, "utilities.landxml"))
    checks["landxml"] = validate_landxml(os.path.join(out_dir, "utilities.landxml"))
    write_geojson(ctx, out_dir)
    vinfo = dict(ok=False, reason="--no-video")
    if video:
        try:
            vinfo = make_video(ctx, os.path.join(out_dir, "submission.mp4"), log)
        except Exception as e:
            import traceback
            log("video failed: " + traceback.format_exc()[-600:])
            vinfo = dict(ok=False, reason=f"error: {e}")
    desc = {"report.html": "A4 보고서 (브라우저 → PDF)", "stations.csv": "조서 총괄표 (엑셀, UTF-8 BOM)",
            "utilities.dxf": "CAD 평면 R12 · UTM 52N", "utilities_tm.dxf": f"CAD 평면 R12 · EPSG:{ctx.geo.tm_epsg}",
            "utilities.landxml": "LandXML 1.2 PipeNetworks (Civil 3D)", "utilities.geojson": "ArcGIS LineString Z · EPSG:32652",
            "utilities_4326.geojson": "경위도 LineString Z", "stations.geojson": "측점 Point Z · EPSG:32652",
            "submission.mp4": "제출 동영상 1280×720", "photos/": f"측점 사진 {ctx.photo_count}장"}
    ctx.files_table = {}
    for k, v in desc.items():
        p = os.path.join(out_dir, k)
        if k.endswith("/"):
            if os.path.isdir(p):
                n = sum(os.path.getsize(os.path.join(p, f)) for f in os.listdir(p))
                ctx.files_table[k] = (v, _hsize(n))
        elif os.path.exists(p) or k == "report.html":
            ctx.files_table[k] = (v, _hsize(os.path.getsize(p)) if os.path.exists(p) else "—")
    html_s, npages = build_html(ctx)
    with open(os.path.join(out_dir, "report.html"), "w", encoding="utf-8") as f:
        f.write(html_s)
    summ = dict(ok=True, version=VERSION, job_id=ctx.job_id, out=os.path.abspath(out_dir), pages=npages, utilities=len(ctx.utils),
                stations=len(ctx.stations), station_source=ctx.station_src, photos=ctx.photo_count, clearances=len(ctx.clearances),
                warnings=[f"{w['level']}:{w['kind']}:{w['what']}" for w in ctx.warnings], tm_epsg=ctx.geo.tm_epsg, frame=ctx.frame_text,
                checks=checks, video=vinfo, report_bytes=os.path.getsize(os.path.join(out_dir, "report.html")),
                hangul_font=has_hangul_font(), seconds=round(time.time() - t0, 1))
    with open(os.path.join(out_dir, "report.json"), "w", encoding="utf-8") as f:
        json.dump(summ, f, ensure_ascii=False, indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))
    log(f"done in {summ['seconds']} s: {npages} pages, dxf {checks['dxf']['ok']}, landxml {checks['landxml']['ok']}, video {vinfo.get('ok')}")
    return summ


def main():
    ap = argparse.ArgumentParser(description="kgeoScan excavation report: utilities.json -> report.html, CSV, DXF, LandXML, GeoJSON, video")
    ap.add_argument("--utilities", required=True)
    ap.add_argument("--job-dir")
    ap.add_argument("--out", required=True)
    ap.add_argument("--data", help="Stray dataset folder (rgb.mp4, odometry.csv, hires/) if not found under --job-dir")
    ap.add_argument("--title")
    ap.add_argument("--surveyor")
    ap.add_argument("--org")
    ap.add_argument("--stage", default="되메우기 전")
    ap.add_argument("--params", default="", help="JSON overriding DEFAULTS")
    ap.add_argument("--no-video", action="store_true")
    ap.add_argument("--no-photos", action="store_true")
    a = ap.parse_args()
    t0 = time.time()
    log = lambda m: print(f"[{time.time() - t0:6.1f}s] {m}".encode("ascii", "replace").decode(), flush=True)
    summ = build_report(a.utilities, a.job_dir, a.out, data=a.data, title=a.title, surveyor=a.surveyor, org=a.org, stage=a.stage,
                        params=json.loads(a.params) if a.params else None, video=not a.no_video, photos=not a.no_photos, log=log)
    short = dict(ok=summ["ok"], pages=summ["pages"], stations=summ["stations"], photos=summ["photos"],
                 dxf=summ["checks"]["dxf"]["ok"], landxml=summ["checks"]["landxml"]["ok"],
                 video={k: summ["video"].get(k) for k in ("ok", "codec", "profile", "bytes", "browser_playable", "reason")},
                 seconds=summ["seconds"])
    print(json.dumps(short, ensure_ascii=True))


if __name__ == "__main__":
    main()
