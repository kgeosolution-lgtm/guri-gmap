#!/usr/bin/env python
"""kgeoScan 균열 기준 카드 — 인쇄물 생성 + 벽면(area) 정사영상의 축척·폭 검증.

카드: AprilTag 36h11 두 개(20 mm, 중심 간격 80 mm), 100 mm 자, 균열폭 게이지 선
(0.1 0.2 0.3 0.5 1.0 2.0 mm, 길이 30 mm), 인쇄 배율 확인용 50 mm 막대.
기하는 site/3dscan/targets/crack_card.json 에 정의되고 검출기는 그 파일만 읽는다.

    python -I worker/scale_target.py --ortho X_ortho.jpg --meta X_ortho.json [--card crack_card.json] [--debug dbg.jpg]
    python -I worker/scale_target.py --make-card site/3dscan/targets      # PDF/PNG/JSON 재생성
    python -I worker/scale_target.py --ortho X_ortho.jpg --meta X_ortho.json --markers     # 모든 36h11 태그
    python -I worker/scale_target.py --make-markers site/3dscan/targets/kgeoscan_markers_example --site "예시 장소" --ids 10,11,12,13

API:  check_scale(ortho_jpg_path, ortho_meta, card_json_path) -> dict
      ortho_jpg_path 는 파일 경로 또는 BGR/회색 ndarray.  반환 키는 check_scale 문서 참고.
      check_scale 의 px 좌표는 OpenCV 규약(픽셀 중심 = 정수).
      detect_markers(img_bgr_or_path, gsd_m, ids=None) -> [{id, center_px, corners_px, size_mm_measured, refined}]
      detect_markers 의 px 좌표는 hazards 계약 규약(픽셀 중심 = 정수 + 0.5).
      make_marker_sheet(out_path, site_name, ids=[10, 11, 12, 13]) -> {pdf, png, ...}  장소 고정 표식 스티커 A4
      detect_board(bgr, board_json) -> [{id, board, slot, corners_px, center_px, obj_mm, refined}]  굴착 기준판 (영상 프레임)
      board_pose(dets, K) -> {distance_m, tvec_m, R, reproj_rms_px, ...}  내부 파라미터를 알 때 한 장 PnP (확인용)
      detect_board / board_pose 의 px 는 기본 OpenCV 규약(pixel_center=0.0), COLMAP 규약이면 pixel_center=0.5.
    python -I worker/scale_target.py --make-trench-board site/3dscan/targets
    python -I worker/scale_target.py --detect-board frame.jpg [--fx 1400]

좌표 규약 (crack_card.json "frame"):
  카드 좌표계 = 첫 태그(tag_ids[0]) 중심이 원점, +x 는 둘째 태그 중심 방향, +y 는 아래(영상과 같은 오른손 계), 단위 mm.
  태그 꼭짓점 순서는 OpenCV aruco 와 같은 TL, TR, BR, BL.
"""
import argparse
import json
import math
import os
import sys
import time
import zlib

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CARD_JSON = os.path.normpath(os.path.join(HERE, "..", "site", "3dscan", "targets", "crack_card.json"))
FONT_REG = r"C:\Windows\Fonts\malgun.ttf"
FONT_BOLD = r"C:\Windows\Fonts\malgunbd.ttf"

# ────────────────────────────── 카드 기하 정의 ──────────────────────────────
# 배치는 카드 왼쪽 위 기준(layout, mm)으로 잡고 JSON 에는 태그 기준 좌표로 쓴다.
_CARD_W, _CARD_H = 130.0, 85.0
_TAG0 = (25.0, 30.0)                 # 첫 태그 중심 (layout)
_TAG_MM, _TAG_DIST = 20.0, 80.0
_GAUGE_W = [0.1, 0.2, 0.3, 0.5, 1.0, 2.0]
_GAUGE_X = [45.0, 53.0, 61.0, 69.0, 77.0, 85.0]
_GAUGE_Y = (15.0, 45.0)
_RULER = dict(x0=15.0, length=100.0, y=53.0, base=0.25, tick_w=0.15, len1=2.0, len5=3.0, len10=4.0)
_BAR = (15.0, 64.0, 65.0, 70.0)       # 50 mm x 6 mm
_BLACK_REF = (18.0, 66.0, 62.0, 68.0)  # 막대 안쪽 (가장자리에서 2 mm)
_WHITE_REF = (18.0, 71.6, 62.0, 73.6)  # 막대 바로 아래 흰 띠
_VARIANTS = [("A", (0, 1)), ("B", (2, 3))]
_PAGE = (210.0, 297.0)
_CARD_ON_PAGE = [(40.0, 28.0), (40.0, 128.0)]


def _tf(x, y):
    return [round(x - _TAG0[0], 4), round(y - _TAG0[1], 4)]


def _rect_tf(r):
    return [_tf(r[0], r[1]), _tf(r[2], r[3])]


def build_card_spec():
    """crack_card.json 내용(dict). 모든 좌표는 카드 좌표계(첫 태그 중심 원점, mm)."""
    h = _TAG_MM / 2
    corners = []
    for cx in (0.0, _TAG_DIST):
        corners.append([[cx - h, -h], [cx + h, -h], [cx + h, h], [cx - h, h]])
    gauges = [dict(nominal_mm=w, p0_mm=_tf(x, _GAUGE_Y[0]), p1_mm=_tf(x, _GAUGE_Y[1]),
                   length_mm=_GAUGE_Y[1] - _GAUGE_Y[0], axis="y")
              for w, x in zip(_GAUGE_W, _GAUGE_X)]
    R = _RULER
    return {
        "name": "kgeoScan crack reference card",
        "title_ko": "kgeoScan 균열 기준 카드",
        "version": 1,
        "units": "mm",
        "frame": "origin = center of tag slot 0 (tag_ids[0]); +x toward the slot-1 tag center; +y down "
                 "(image convention). Tag corner order TL,TR,BR,BL as cv2.aruco returns them.",
        "dictionary": "DICT_APRILTAG_36h11",
        "tag_size_mm": _TAG_MM,
        "tag_size_definition": "outer edge of the black border (8 modules = 6 data + 2 border); "
                               "white quiet zone >= 3.5 mm around each tag",
        "tag_modules": 8,
        "tag_center_distance_mm": _TAG_DIST,
        "variants": [{"label": lb, "tag_ids": list(ids)} for lb, ids in _VARIANTS],
        "tag_centers_mm": [[0.0, 0.0], [_TAG_DIST, 0.0]],
        "tag_corners_mm": corners,
        "card_outline_mm": _rect_tf((0.0, 0.0, _CARD_W, _CARD_H)),
        "gauge_lines": gauges,
        "gauge_measure_span": [0.1, 0.9],
        "gauge_note": "black lines on white, centered on p0-p1, width = nominal_mm across x",
        "ruler": {"start_mm": _tf(R["x0"], R["y"]), "end_mm": _tf(R["x0"] + R["length"], R["y"]),
                  "length_mm": R["length"], "baseline_thickness_mm": R["base"], "tick_width_mm": R["tick_w"],
                  "tick_length_mm": {"1": R["len1"], "5": R["len5"], "10": R["len10"]},
                  "ticks_go": "+y from the baseline bottom edge"},
        "scale_bar_50mm": {"rect_mm": _rect_tf(_BAR), "length_mm": 50.0},
        "black_ref_rect_mm": _rect_tf(_BLACK_REF),
        "white_ref_rect_mm": _rect_tf(_WHITE_REF),
        "layout": {
            "card_size_mm": [_CARD_W, _CARD_H],
            "tag0_center_from_card_top_left_mm": list(_TAG0),
            "page": "A4", "page_size_mm": list(_PAGE), "png_dpi": 300,
            "cards_on_page": [{"label": lb, "tag_ids": list(ids), "card_top_left_on_page_mm": list(pos)}
                              for (lb, ids), pos in zip(_VARIANTS, _CARD_ON_PAGE)],
        },
        "files": {"pdf": "kgeoscan_crack_card.pdf", "png": "kgeoscan_crack_card.png"},
    }


# ────────────────────────────── 그리기 (벡터 원소) ──────────────────────────────
# 원소: ("rect", x0, y0, x1, y1, dark)  /  ("text", x, y, size_mm, text, bold, anchor, dark)
# dark: 0 = 흰색, 1 = 검정.  좌표는 mm, y 아래 방향.

def _aruco_dict(name="DICT_APRILTAG_36h11"):
    return cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, name))


def _tag_rects(d, tid, x0, y0, size, nb=8):
    """AprilTag 하나의 검은 모듈을 사각형 원소로. (x0, y0) = 태그 왼쪽 위(검은 테두리 바깥), size = 한 변(mm)."""
    m = size / nb
    bits = cv2.aruco.generateImageMarker(d, int(tid), nb, borderBits=1) < 128   # True = 검정
    runs = []                                        # 행마다 검정 구간 → 같은 구간이 이어지면 세로로 합친다
    for r in range(nb):
        row = bits[r]
        c = 0
        while c < nb:
            if row[c]:
                c1 = c
                while c1 < nb and row[c1]:
                    c1 += 1
                runs.append([c, c1, r, r + 1])
                c = c1
            else:
                c += 1
    merged = []
    for c0, c1, r0, r1 in runs:
        for mm in merged:
            if mm[0] == c0 and mm[1] == c1 and mm[3] == r0:
                mm[3] = r1
                break
        else:
            merged.append([c0, c1, r0, r1])
    return [("rect", x0 + c0 * m, y0 + r0 * m, x0 + c1 * m, y0 + r1 * m, 1.0) for c0, c1, r0, r1 in merged]


def card_primitives(spec, variant=0, texts=True):
    """카드 좌표계(태그0 중심 원점) 원소 목록."""
    var = spec["variants"][variant]
    ids = var["tag_ids"]
    d = _aruco_dict(spec["dictionary"])
    nb = int(spec["tag_modules"])
    prims = []
    for slot, tid in enumerate(ids):
        (x0, y0) = spec["tag_corners_mm"][slot][0]
        prims += _tag_rects(d, tid, x0, y0, spec["tag_size_mm"], nb)
    for g in spec["gauge_lines"]:
        x, ya = g["p0_mm"]
        yb = g["p1_mm"][1]
        w = g["nominal_mm"]
        prims.append(("rect", x - w / 2, ya, x + w / 2, yb, 1.0))
    R = spec["ruler"]
    xs, yb0 = R["start_mm"]
    tw, base = R["tick_width_mm"], R["baseline_thickness_mm"]
    prims.append(("rect", xs - tw / 2, yb0, xs + R["length_mm"] + tw / 2, yb0 + base, 1.0))
    tl = R["tick_length_mm"]
    for i in range(int(round(R["length_mm"])) + 1):
        L = tl["10"] if i % 10 == 0 else tl["5"] if i % 5 == 0 else tl["1"]
        prims.append(("rect", xs + i - tw / 2, yb0 + base, xs + i + tw / 2, yb0 + base + L, 1.0))
    (bx0, by0), (bx1, by1) = spec["scale_bar_50mm"]["rect_mm"]
    prims.append(("rect", bx0, by0, bx1, by1, 1.0))
    if texts:
        T = lambda x, y, sz, s, bold=False, anc="la", dk=1.0: prims.append(("text", *_tf(x, y), sz, s, bold, anc, dk))
        T(6.0, 3.0, 4.6, spec.get("title_ko", "kgeoScan 균열 기준 카드"), True)
        T(124.0, 4.2, 2.8, f"카드 {var['label']} · ID {ids[0]}/{ids[1]}", True, "ra")
        T(65.0, 10.5, 2.4, "균열폭 게이지 (mm)", False, "ma")
        for g in spec["gauge_lines"]:
            T(g["p0_mm"][0] + _TAG0[0], 46.3, 2.3, f"{g['nominal_mm']:.1f}", True, "ma")
        for slot, tid in enumerate(ids):
            T(spec["tag_centers_mm"][slot][0] + _TAG0[0], 43.6, 2.3, f"ID {tid}", False, "ma")
        for k in range(0, 11):
            T(_RULER["x0"] + 10 * k, 57.9, 1.9, f"{10 * k}", False, "ma")
        T(117.5, 53.0, 1.9, "mm", False, "la")
        T(68.0, 63.8, 2.4, "← 50 mm 막대", True, "la")
        T(68.0, 67.3, 1.9, "자로 재어 50 mm가 아니면 '실제 크기 100%'로 다시 인쇄", False, "la")
        T(6.0, 78.6, 1.8, "AprilTag 36h11 · 태그 20 mm · 중심 간격 80 mm · 균열 옆 벽면에 평평하게 부착", False, "la", 0.75)
        T(124.0, 78.6, 1.8, "kgeodata.com", False, "ra", 0.75)
    return prims


def _shift(prims, dx, dy):
    out = []
    for p in prims:
        if p[0] == "rect":
            out.append(("rect", p[1] + dx, p[2] + dy, p[3] + dx, p[4] + dy, p[5]))
        else:
            out.append(("text", p[1] + dx, p[2] + dy) + tuple(p[3:]))
    return out


def _dashed_rect(x0, y0, x1, y1, t=0.2, on=2.0, off=1.4, dk=0.45):
    out = []
    for (a, b, fixed, horiz) in ((x0, x1, y0, True), (x0, x1, y1, True), (y0, y1, x0, False), (y0, y1, x1, False)):
        p = a
        while p < b:
            q = min(b, p + on)
            if horiz:
                out.append(("rect", p, fixed - t / 2, q, fixed + t / 2, dk))
            else:
                out.append(("rect", fixed - t / 2, p, fixed + t / 2, q, dk))
            p = q + off
    return out


def page_primitives(spec):
    """A4 한 장(카드 2매) 원소 목록, 페이지 좌표(mm, 왼쪽 위 원점)."""
    prims = []
    (ox0, oy0), (ox1, oy1) = spec["card_outline_mm"]
    for vi, c in enumerate(spec["layout"]["cards_on_page"]):
        px, py = c["card_top_left_on_page_mm"]
        dx, dy = px - ox0, py - oy0
        prims += _shift(card_primitives(spec, vi), dx, dy)
        prims += _dashed_rect(px, py, px + (ox1 - ox0), py + (oy1 - oy0))
    T = lambda x, y, sz, s, bold=False, dk=1.0: prims.append(("text", x, y, sz, s, bold, "la", dk))
    T(20.0, 9.0, 4.2, "kgeoScan 균열 기준 카드  (A4 · 2매)", True)
    T(20.0, 16.0, 2.8, "인쇄 설정: '실제 크기' 또는 배율 100%  —  '용지에 맞춤 / 축소' 사용 금지 · 레이저 프린터, 흰 무광 용지 권장")
    y = 224.0
    T(20.0, y, 3.2, "사용 방법", True)
    lines = [
        "1. 각 카드의 50 mm 막대를 자로 재어 정확히 50 mm인지 확인합니다 (±0.5 mm). 다르면 배율 100%로 다시 인쇄합니다.",
        "2. 점선을 따라 자릅니다. 태그(검은 사각형) 둘레의 흰 여백은 자르거나 가리지 마세요.",
        "3. 균열 바로 옆 벽면에 평평하게 붙입니다. 휘거나 들뜨지 않게, 태그와 게이지가 그림자에 가리지 않게 합니다.",
        "4. 벽면(area) 모드로 스캔하면 정사영상에서 카드를 자동 인식해 축척(mm)과 균열폭 측정값을 검증합니다.",
        "카드 A(ID 0/1)와 B(ID 2/3)는 한 장면에 함께 붙여도 서로 구분됩니다.",
        "참고: 인쇄된 게이지 선의 실제 굵기는 프린터에 따라 ±0.05 mm 정도 달라질 수 있습니다 (정밀 검증은 균열 스케일로 확인).",
    ]
    for i, s in enumerate(lines):
        T(20.0, y + 6.0 + 5.2 * i, 2.6, s, False, 1.0 if i < 4 else 0.7)
    return prims


# ────────────────────────────── 장소 고정 표식 (스티커) ──────────────────────────────
# hazards 계약 5절: ID 0~3 은 균열 카드, ID 10 이상은 장소 표식. 태그 20 mm + 둘레 흰 여백 4 mm 이상.
MARKER_TAG_MM = 20.0
MARKER_MIN_ID = 10
_DICT_SIZE_36H11 = 587


def _text_width_mm(text, size_mm, bold):
    f = _font(round(size_mm * 20), bold)
    l, _, r, _ = f.getbbox(text, anchor="la")
    return (r - l) / 20.0


def _fit_text(text, size_mm, bold, max_w, min_size=1.6):
    """max_w(mm) 안에 들어가게 글자 크기를 줄이고, 그래도 넘치면 뒤를 … 로 자른다."""
    w = _text_width_mm(text, size_mm, bold)
    if w <= max_w:
        return text, size_mm
    s = max(min_size, size_mm * max_w / w * 0.98)
    t = text
    while len(t) > 1 and _text_width_mm(t if t == text else t + "…", s, bold) > max_w:
        t = t[:-1]
    return (t if t == text else t + "…"), s


def marker_sticker_size(tag_mm=MARKER_TAG_MM):
    side = max(10.0, tag_mm / 2)                     # 태그 좌우 여백
    return tag_mm + 2 * side, tag_mm + 20.0          # (폭, 높이) mm: 위 5 + 태그 + 아래 글자 15


def marker_sticker_primitives(tid, site_name, tag_mm=MARKER_TAG_MM):
    """스티커 한 장 (왼쪽 위 원점, mm). 태그 중심 = (폭/2, 5 + tag/2)."""
    W, H = marker_sticker_size(tag_mm)
    x0, y0 = (W - tag_mm) / 2, 5.0
    prims = _tag_rects(_aruco_dict(), tid, x0, y0, tag_mm, 8)
    ty = y0 + tag_mm + 4.3                           # 태그 아래 흰 여백 4.3 mm 뒤 글자
    s1, z1 = _fit_text(f"kgeoScan 표식 #{tid}", 2.7, True, W - 3.0)
    s2, z2 = _fit_text(site_name or "", 2.4, False, W - 3.0)
    prims.append(("text", W / 2, ty, z1, s1, True, "ma", 1.0))
    if s2:
        prims.append(("text", W / 2, ty + 4.1, z2, s2, False, "ma", 0.8))
    return prims


def marker_sheet_pages(site_name, ids, tag_mm=MARKER_TAG_MM):
    """A4 페이지별 원소 목록과 스티커 배치 [(page, id, tag_center_on_page_mm)]."""
    PW, PH = _PAGE
    W, H = marker_sticker_size(tag_mm)
    gap, margin = 8.0, 10.0
    cols = max(1, int((PW - 2 * margin + gap) // (W + gap)))
    top, bottom_reserved = 32.0, 62.0
    rows = max(1, int((PH - top - bottom_reserved + gap) // (H + gap)))
    per = cols * rows
    pages, placed = [], []
    chunks = [ids[i:i + per] for i in range(0, len(ids), per)] or [[]]
    for pi, chunk in enumerate(chunks):
        prims = []
        T = lambda x, y, sz, s, bold=False, dk=1.0, anc="la": prims.append(("text", x, y, sz, s, bold, anc, dk))
        title, tz = _fit_text(f"kgeoScan 장소 표식 — {site_name}", 4.2, True, PW - 40)
        T(20.0, 9.0, tz, title, True)
        id_txt = ", ".join(str(i) for i in ids)
        sub, sz = _fit_text(f"AprilTag 36h11 · 태그 {tag_mm:g} mm · ID {id_txt}"
                            + (f"  ({pi + 1}/{len(chunks)}쪽)" if len(chunks) > 1 else ""), 2.8, False, PW - 40)
        T(20.0, 16.0, sz, sub)
        T(20.0, 21.5, 2.6, "인쇄 설정: '실제 크기' 또는 배율 100%  —  '용지에 맞춤 / 축소' 사용 금지", False, 0.75)
        n = len(chunk)
        used_cols = min(cols, max(1, n))
        x0 = (PW - (used_cols * W + (used_cols - 1) * gap)) / 2
        y_end = top
        for k, tid in enumerate(chunk):
            r, c = divmod(k, cols)
            x, y = x0 + c * (W + gap), top + r * (H + gap)
            prims += _shift(marker_sticker_primitives(tid, site_name, tag_mm), x, y)
            prims += _dashed_rect(x, y, x + W, y + H)
            placed.append(dict(page=pi, id=int(tid), tag_center_on_page_mm=[round(x + W / 2, 3), round(y + 5.0 + tag_mm / 2, 3)]))
            y_end = y + H
        y = y_end + 14.0
        T(20.0, y, 3.2, "사용 방법", True)
        lines = [
            "1. 50 mm 막대를 자로 재어 정확히 50 mm인지 확인합니다. 점선을 따라 자릅니다 (태그 둘레 흰 여백은 남김).",
            "2. 균열·손상 주변 벽면에 2~4개를 서로 떨어뜨려 평평하게 붙입니다. 다음 점검까지 떼지 않습니다.",
            "3. 점검할 때마다 표식이 함께 찍히게 스캔합니다. 표식 위치로 지난 점검과 정확히 겹쳐 비교합니다.",
            "4. ID는 장소마다 겹치지 않게 서버가 나눠 줍니다. 다른 장소의 표식을 옮겨 쓰지 마세요.",
            "실외·습한 곳은 방수 라벨지나 무광 코팅을 권장합니다 (광택 코팅은 반사로 인식이 떨어집니다).",
        ]
        for i, s in enumerate(lines):
            T(20.0, y + 6.0 + 5.0 * i, 2.5, s, False, 1.0 if i < 4 else 0.7)
        by = y + 6.0 + 5.0 * len(lines) + 3.0
        prims.append(("rect", 20.0, by, 70.0, by + 5.0, 1.0))
        T(74.0, by + 0.6, 2.4, "← 50 mm 막대 (인쇄 배율 확인)", True)
        pages.append(prims)
    return pages, placed


def make_marker_sheet(out_path, site_name, ids=(10, 11, 12, 13), tag_mm=MARKER_TAG_MM, dpi=300, allow_reserved=False):
    """장소 표식 스티커 시트: <stem>.pdf (A4 벡터, 여러 쪽 가능) 와 <stem>.png (300 dpi, 2쪽부터 <stem>_p2.png ...).

    out_path: 'dir/name' 또는 'dir/name.pdf' / '.png'.  ids: 정수 목록 (중복 불가, 10~586).
    반환: {pdf, png: [...], site_name, ids, tag_mm, stickers: [{page, id, tag_center_on_page_mm}]}
    """
    from PIL import Image
    ids = [int(i) for i in ids]
    if not ids:
        raise ValueError("ids is empty")
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate ids")
    bad = [i for i in ids if not (0 <= i < _DICT_SIZE_36H11)]
    if bad:
        raise ValueError(f"ids out of AprilTag 36h11 range 0..{_DICT_SIZE_36H11 - 1}: {bad}")
    reserved = [i for i in ids if i < MARKER_MIN_ID]
    if reserved and not allow_reserved:
        raise ValueError(f"ids {reserved} are reserved (0-3 crack card, 4-9 spare); site markers use >= {MARKER_MIN_ID}")
    stem = out_path[:-4] if out_path.lower().endswith((".pdf", ".png")) else out_path
    d = os.path.dirname(stem)
    if d:
        os.makedirs(d, exist_ok=True)
    pages, placed = marker_sheet_pages(site_name, ids, tag_mm)
    write_pdf(stem + ".pdf", pages)
    s = dpi / 25.4
    Wp, Hp = int(round(_PAGE[0] * s)), int(round(_PAGE[1] * s))
    pngs = []
    for pi, prims in enumerate(pages):
        ink = render_ink(prims, s, (Hp, Wp))
        p = stem + (".png" if pi == 0 else f"_p{pi + 1}.png")
        Image.fromarray(np.clip(255.0 * (1.0 - ink) + 0.5, 0, 255).astype(np.uint8), "L").save(p, dpi=(dpi, dpi), optimize=True)
        pngs.append(p)
    return dict(pdf=stem + ".pdf", png=pngs, site_name=site_name, ids=ids, tag_mm=tag_mm, stickers=placed)


# ────────────────────────────── 굴착 기준판 (웹 영상 실측 축척) ──────────────────────────────
# web_trench_contract.md 2절. A4 가로, 네 귀퉁이에 75 mm AprilTag 36h11, 가운데 세로 띠에 글자·50 mm 막대.
# ID 는 사이트 표식(ID >= 10, 서버 자동 묶기)과 겹치지 않게 사전 끝 쪽 576~583 을 쓴다.
_TB_PAGE = (297.0, 210.0)
_TB_TAG = 75.0
_TB_MARGIN = 12.0
_TB_BOARDS = [("1", (576, 577, 578, 579)), ("2", (580, 581, 582, 583))]


def build_trench_board_spec():
    """trench_board.json 내용. 좌표는 판 좌표계(판 가운데 원점, mm)."""
    W, H = _TB_PAGE
    t, m = _TB_TAG, _TB_MARGIN
    cx0, cx1 = m + t / 2, W - m - t / 2
    cy0, cy1 = m + t / 2, H - m - t / 2
    ox, oy = W / 2, H / 2
    centers = [(cx0, cy0), (cx1, cy0), (cx1, cy1), (cx0, cy1)]          # 슬롯 0 TL, 1 TR, 2 BR, 3 BL
    tc = [[round(x - ox, 4), round(y - oy, 4)] for x, y in centers]
    h = t / 2
    corners = [[[x - h, y - h], [x + h, y - h], [x + h, y + h], [x - h, y + h]] for x, y in tc]
    dx, dy = tc[1][0] - tc[0][0], tc[3][1] - tc[0][1]
    bar = (ox - 25.0, 42.0, ox + 25.0, 48.0)
    return {
        "name": "kgeoScan trench reference board",
        "title_ko": "kgeoScan 굴착 기준판",
        "version": 1,
        "units": "mm",
        "frame": "origin = board centre (centre of the 4 tag centres = page centre); +x right as printed "
                 "(slot 0 -> slot 1), +y down (slot 0 -> slot 3), +z into the board (right-handed); board plane z = 0. "
                 "Tag corner order TL,TR,BR,BL as cv2.aruco returns them.",
        "dictionary": "DICT_APRILTAG_36h11",
        "tag_size_mm": t,
        "tag_size_definition": "outer edge of the black border (8 modules = 6 data + 2 border); "
                               "white quiet zone >= 12 mm (1.3 modules) around each tag",
        "tag_modules": 8,
        "boards": [{"label": lb, "tag_ids": list(ids)} for lb, ids in _TB_BOARDS],
        "id_note": "ids 576-583 sit at the end of the 36h11 dictionary (0-586) so they never collide with "
                   "crack-card ids 0-3 or server-assigned site markers (>= 10)",
        "slots": ["top-left", "top-right", "bottom-right", "bottom-left"],
        "tag_centers_mm": tc,
        "tag_corners_mm": corners,
        "center_distances_mm": {"horizontal": round(dx, 4), "vertical": round(dy, 4),
                                "diagonal": round(math.hypot(dx, dy), 4)},
        "board_outline_mm": [[-ox, -oy], [ox, oy]],
        "scale_bar_50mm": {"rect_mm": [[round(bar[0] - ox, 4), round(bar[1] - oy, 4)],
                                       [round(bar[2] - ox, 4), round(bar[3] - oy, 4)]], "length_mm": 50.0},
        "detection": {
            "expected_tag_px": "fx * 0.075 / distance_m  (iPhone 1080p fx~1400: 70 px at 1.5 m, 42 px at 2.5 m; "
                               "times cos(view angle from the board normal) across the foreshortened axis)",
            "min_tag_px": 12,
        },
        "page": {"size": "A4 landscape", "size_mm": list(_TB_PAGE), "png_dpi": 300,
                 "page_top_left_in_board_mm": [-ox, -oy]},
        "files": {"pdf": "trench_board.pdf", "png": ["trench_board.png", "trench_board_p2.png"]},
    }


def trench_board_primitives(spec, board=0):
    """A4 가로 한 장(판 하나) 원소 목록, 페이지 좌표(mm, 왼쪽 위 원점)."""
    W, H = spec["page"]["size_mm"]
    ox, oy = W / 2, H / 2
    b = spec["boards"][board]
    d = _aruco_dict(spec["dictionary"])
    t = spec["tag_size_mm"]
    prims = []
    for slot, tid in enumerate(b["tag_ids"]):
        x0, y0 = spec["tag_corners_mm"][slot][0]
        prims += _tag_rects(d, tid, x0 + ox, y0 + oy, t, int(spec["tag_modules"]))
    (bx0, by0), (bx1, by1) = spec["scale_bar_50mm"]["rect_mm"]
    prims.append(("rect", bx0 + ox, by0 + oy, bx1 + ox, by1 + oy, 1.0))
    T = lambda x, y, sz, s, bold=False, anc="la", dk=1.0: prims.append(("text", x, y, sz, s, bold, anc, dk))
    cd = spec["center_distances_mm"]
    q = 1.3 * t / 8                                                        # 글자는 태그에서 1.3 모듈 넘게 떨어뜨린다
    xl, xr = spec["tag_corners_mm"][0][1][0] + ox + q, spec["tag_corners_mm"][1][0][0] + ox - q
    colw = xr - xl
    s, z = _fit_text(f"kgeoScan 굴착 기준판 {b['label']}", 7.5, True, colw)
    T(ox, 13.0, z, s, True, "ma")
    s, z = _fit_text("AprilTag 36h11 · ID " + " ".join(str(i) for i in b["tag_ids"]), 3.6, False, colw)
    T(ox, 25.0, z, s, False, "ma")
    s, z = _fit_text(f"태그 {t:g} mm · 중심 간격 가로 {cd['horizontal']:g} mm · 세로 {cd['vertical']:g} mm", 3.2, False, colw)
    T(ox, 31.5, z, s, False, "ma", 0.8)
    T(ox, by1 + oy + 2.0, 3.0, "↑ 50 mm 막대 — 자로 재어 확인", True, "ma")
    T(xl, 60.0, 3.8, "사용 방법", True)
    lines = [
        "1. 배율 100%(실제 크기)로 인쇄합니다.",
        f"2. 50 mm 막대와 가로 태그 간격 {cd['horizontal']:g} mm를 자로 확인합니다.",
        "3. 두꺼운 판지에 붙여 휘지 않게 합니다 (무광 코팅 권장).",
        "4. 굴착 가장자리 지면이나 굴착 바닥에 평평하게 놓습니다.",
        "5. 1.5~2.5 m 거리에서 판 전체가 여러 번 화면에 들어오게 찍습니다.",
        "6. 태그를 흙·발·그림자로 가리지 않습니다.",
    ]
    for i, ln in enumerate(lines):
        s, z = _fit_text(ln, 3.0, False, colw)
        T(xl, 67.0 + 6.2 * i, z, s)
    s, z = _fit_text("판 1과 판 2는 한 현장에 함께 놓아도 서로 구분됩니다.", 2.8, False, colw)
    T(xl, 67.0 + 6.2 * len(lines) + 3.0, z, s, False, "la", 0.65)
    T(ox, H - 16.0, 2.6, "kgeodata.com · 굴착 기준판 v1", False, "ma", 0.6)
    # 태그 ID 표시 (조용한 여백 바깥: 위 태그 아래 / 아래 태그 위)
    for slot, tid in enumerate(b["tag_ids"]):
        cxp = spec["tag_centers_mm"][slot][0] + ox
        if slot in (0, 1):
            T(cxp, spec["tag_corners_mm"][slot][3][1] + oy + q + 0.3, 3.0, f"▲ ID {tid}", False, "ma", 0.7)
        else:
            T(cxp, spec["tag_corners_mm"][slot][0][1] + oy - q - 4.2, 3.0, f"▼ ID {tid}", False, "ma", 0.7)
    return prims


def make_trench_board_files(out_dir, dpi=300):
    """trench_board.json, trench_board.pdf (A4 가로 2쪽: 판 1, 판 2), trench_board.png / trench_board_p2.png."""
    from PIL import Image
    os.makedirs(out_dir, exist_ok=True)
    spec = build_trench_board_spec()
    spec["page"]["png_dpi"] = dpi
    with open(os.path.join(out_dir, "trench_board.json"), "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=1, ensure_ascii=False)
    pages = [trench_board_primitives(spec, i) for i in range(len(spec["boards"]))]
    write_pdf(os.path.join(out_dir, spec["files"]["pdf"]), pages, page_mm=tuple(spec["page"]["size_mm"]))
    s = dpi / 25.4
    W, H = int(round(spec["page"]["size_mm"][0] * s)), int(round(spec["page"]["size_mm"][1] * s))
    for prims, name in zip(pages, spec["files"]["png"]):
        ink = render_ink(prims, s, (H, W))
        Image.fromarray(np.clip(255.0 * (1.0 - ink) + 0.5, 0, 255).astype(np.uint8), "L").save(
            os.path.join(out_dir, name), dpi=(dpi, dpi), optimize=True)
    return spec


# ────────────────────────────── 래스터 렌더 ──────────────────────────────
_font_cache = {}


def _font(size_px, bold):
    from PIL import ImageFont
    key = (int(size_px), bool(bold))
    if key not in _font_cache:
        path = FONT_BOLD if bold else FONT_REG
        try:
            _font_cache[key] = ImageFont.truetype(path, max(1, int(size_px)))
        except OSError:
            _font_cache[key] = ImageFont.load_default()
    return _font_cache[key]


def _text_mask(text, size_px, bold, anchor):
    """(coverage float32 0..1, dx, dy): 마스크 왼쪽 위의 기준점 대비 위치(px)."""
    from PIL import Image, ImageDraw
    f = _font(round(size_px), bold)
    l, t, r, b = f.getbbox(text, anchor=anchor)
    img = Image.new("L", (int(r - l) + 2, int(b - t) + 2), 0)
    ImageDraw.Draw(img).text((-l + 1, -t + 1), text, font=f, fill=255, anchor=anchor)
    return np.asarray(img, np.float32) / 255.0, l - 1, t - 1


def render_ink(prims, px_per_mm, shape, origin_mm=(0.0, 0.0)):
    """잉크 농도(0..1) 래스터. 픽셀 (i, j) 는 mm [ox + i/s, ox + (i+1)/s] 를 덮는다 (사각형은 면적 정확)."""
    H, W = shape
    s = float(px_per_mm)
    ox, oy = origin_mm
    ink = np.zeros((H, W), np.float32)
    for p in prims:
        if p[0] == "rect":
            _, x0, y0, x1, y1, dk = p
            X0, X1, Y0, Y1 = (x0 - ox) * s, (x1 - ox) * s, (y0 - oy) * s, (y1 - oy) * s
            i0, i1 = max(0, int(math.floor(X0))), min(W, int(math.ceil(X1)))
            j0, j1 = max(0, int(math.floor(Y0))), min(H, int(math.ceil(Y1)))
            if i0 >= i1 or j0 >= j1:
                continue
            ii = np.arange(i0, i1, dtype=np.float64)
            jj = np.arange(j0, j1, dtype=np.float64)
            cx = np.clip(np.minimum(X1, ii + 1) - np.maximum(X0, ii), 0, 1)
            cy = np.clip(np.minimum(Y1, jj + 1) - np.maximum(Y0, jj), 0, 1)
            ink[j0:j1, i0:i1] += (dk * np.outer(cy, cx)).astype(np.float32)
        else:
            _, x, y, size, txt, bold, anchor, dk = p
            m, dx, dy = _text_mask(txt, size * s, bold, anchor)
            X = int(round((x - ox) * s + dx))
            Y = int(round((y - oy) * s + dy))
            h, w = m.shape
            a0, b0 = max(0, Y), max(0, X)
            a1, b1 = min(H, Y + h), min(W, X + w)
            if a0 < a1 and b0 < b1:
                sub = ink[a0:a1, b0:b1]
                np.maximum(sub, dk * m[a0 - Y:a1 - Y, b0 - X:b1 - X], out=sub)
    return np.clip(ink, 0, 1)


# ────────────────────────────── PDF (벡터) ──────────────────────────────
def _fmt(v):
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def write_pdf(path, pages, page_mm=_PAGE, text_dpi=1200):
    """원소 목록(페이지 mm 좌표) → PDF. 사각형은 벡터, 글자는 1200 dpi 스텐실 마스크."""
    K = 72.0 / 25.4
    Wpt, Hpt = page_mm[0] * K, page_mm[1] * K
    objs = [None, None]                                   # 1: Catalog, 2: Pages

    def add(b):
        objs.append(b)
        return len(objs)

    kids = []
    tpx = text_dpi / 25.4
    for prims in pages:
        ops = [f"{_fmt(K)} 0 0 {_fmt(-K)} 0 {_fmt(Hpt)} cm"]   # 이후 단위 mm, y 아래
        xo = {}
        cur = None
        for p in prims:
            if p[0] == "rect":
                _, x0, y0, x1, y1, dk = p
                g = round(1.0 - dk, 3)
                if g != cur:
                    ops.append(f"{_fmt(g)} g")
                    cur = g
                ops.append(f"{_fmt(x0)} {_fmt(y0)} {_fmt(x1 - x0)} {_fmt(y1 - y0)} re f")
            else:
                _, x, y, size, txt, bold, anchor, dk = p
                m, dx, dy = _text_mask(txt, size * tpx, bold, anchor)
                h, w = m.shape
                bits = np.packbits(m < 0.5, axis=1)          # 1 = 배경(칠 안 함), 0 = 글자
                data = zlib.compress(bits.tobytes(), 9)
                name = f"T{len(xo)}"
                oid = add(b"<< /Type /XObject /Subtype /Image /Width %d /Height %d /ImageMask true "
                          b"/BitsPerComponent 1 /Decode [0 1] /Filter /FlateDecode /Length %d >>\nstream\n"
                          % (w, h, len(data)) + data + b"\nendstream")
                xo[name] = oid
                X, Y, Wm, Hm = x + dx / tpx, y + dy / tpx, w / tpx, h / tpx
                ops.append(f"q {_fmt(round(1.0 - dk, 3))} g {_fmt(Wm)} 0 0 {_fmt(-Hm)} {_fmt(X)} {_fmt(Y + Hm)} cm /{name} Do Q")
        content = zlib.compress("\n".join(ops).encode("ascii"), 9)
        cid = add(b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(content) + content + b"\nendstream")
        res = " ".join(f"/{k} {v} 0 R" for k, v in xo.items())
        pid = add(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {_fmt(Wpt)} {_fmt(Hpt)}] "
                  f"/Resources << /XObject << {res} >> >> /Contents {cid} 0 R >>".encode("ascii"))
        kids.append(pid)
    objs[0] = b"<< /Type /Catalog /Pages 2 0 R /ViewerPreferences << /PrintScaling /None >> >>"
    objs[1] = (f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {len(kids)} >>").encode("ascii")
    info = add(b"<< /Title (kgeoScan crack reference card) /Creator (kgeoScan worker/scale_target.py) >>")
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offs = []
    for i, b in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n" % i + b + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for o in offs:
        out += b"%010d 00000 n \n" % o
    out += b"trailer\n<< /Size %d /Root 1 0 R /Info %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, info, xref)
    with open(path, "wb") as f:
        f.write(out)


def make_card_files(out_dir):
    """crack_card.json, kgeoscan_crack_card.pdf, kgeoscan_crack_card.png (300 dpi) 생성."""
    from PIL import Image
    os.makedirs(out_dir, exist_ok=True)
    spec = build_card_spec()
    with open(os.path.join(out_dir, "crack_card.json"), "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=1, ensure_ascii=False)
    prims = page_primitives(spec)
    write_pdf(os.path.join(out_dir, spec["files"]["pdf"]), [prims])
    dpi = spec["layout"]["png_dpi"]
    s = dpi / 25.4
    W, H = int(round(_PAGE[0] * s)), int(round(_PAGE[1] * s))
    ink = render_ink(prims, s, (H, W))
    img = Image.fromarray(np.clip(255.0 * (1.0 - ink) + 0.5, 0, 255).astype(np.uint8), "L")
    img.save(os.path.join(out_dir, spec["files"]["png"]), dpi=(dpi, dpi), optimize=True)
    return spec


# ────────────────────────────── 검출 ──────────────────────────────
_SRGB_LUT = None


def _lin_lut():
    global _SRGB_LUT
    if _SRGB_LUT is None:
        c = np.arange(256, dtype=np.float64) / 255.0
        _SRGB_LUT = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4).astype(np.float32)
    return _SRGB_LUT


def _to_linear(img, linearize=True):
    """BGR/회색 uint8 → 선형광 휘도 float32 (0..1)."""
    if not linearize:
        g = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return g.astype(np.float32) / 255.0
    lut = _lin_lut()
    if img.ndim == 2:
        return lut[img]
    return 0.0722 * lut[img[..., 0]] + 0.7152 * lut[img[..., 1]] + 0.2126 * lut[img[..., 2]]


def _imread(path):
    data = np.fromfile(path, np.uint8)                       # 한글 경로 대응
    return cv2.imdecode(data, cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION)


def _detector(dict_name, min_rate, refine, win):
    p = cv2.aruco.DetectorParameters()
    p.minMarkerPerimeterRate = float(min_rate)
    p.maxMarkerPerimeterRate = 4.0
    if refine:
        p.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        p.cornerRefinementWinSize = int(win)
        p.cornerRefinementMaxIterations = 60
        p.cornerRefinementMinAccuracy = 0.005
    return cv2.aruco.ArucoDetector(_aruco_dict(dict_name), p)


def _detect(gray, tag_px, dict_name, refine=True, win=4):
    h, w = gray.shape[:2]
    rate = max(0.002, 0.5 * 4.0 * tag_px / max(h, w))         # 예상 크기의 절반까지 허용
    corners, ids, _ = _detector(dict_name, rate, refine, win).detectMarkers(gray)
    if ids is None:
        return []
    return [(int(i), c.reshape(4, 2).astype(np.float64)) for c, i in zip(corners, ids.ravel())]


def _dedupe(dets, tol):
    out = []
    for i, c in dets:
        ctr = c.mean(0)
        if any(j == i and np.linalg.norm(d.mean(0) - ctr) < tol for j, d in out):
            continue
        out.append((i, c))
    return out


def _detect_tiled(gray, tag_px, dict_name, tile=2048, refine=True, win=4):
    h, w = gray.shape[:2]
    if max(h, w) <= int(tile * 1.25):
        return _detect(gray, tag_px, dict_name, refine, win)
    ov = int(3 * tag_px + 32)
    step = max(64, tile - ov)
    res = []
    for y0 in range(0, max(1, h - ov), step):
        for x0 in range(0, max(1, w - ov), step):
            sub = gray[y0:y0 + tile, x0:x0 + tile]
            res += [(i, c + [x0, y0]) for i, c in _detect(sub, tag_px, dict_name, refine, win)]
    return _dedupe(res, tag_px * 0.5)


def _sample(img, pts):
    """쌍선형 표본. pts (..., 2) → (...). 2차원 이상 배열로 넘길 것 (remap 크기 제한 32767)."""
    shp = pts.shape[:-1]
    p2 = pts.reshape(shp[0], -1, 2) if len(shp) >= 2 else pts.reshape(1, -1, 2)
    v = cv2.remap(img, p2[..., 0].astype(np.float32), p2[..., 1].astype(np.float32),
                  cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    return v.reshape(shp)


def _fit_line(pts):
    """총최소제곱 직선: (점, 단위방향). 2.5σ 이상치 1회 제거."""
    for _ in range(2):
        c = pts.mean(0)
        _, _, vt = np.linalg.svd(pts - c, full_matrices=False)
        d = vt[0]
        nrm = np.array([-d[1], d[0]])
        r = (pts - c) @ nrm
        sd = r.std() + 1e-9
        keep = np.abs(r) < 2.5 * sd
        if keep.all() or keep.sum() < 6:
            break
        pts = pts[keep]
    return c, d


def _intersect(c1, d1, c2, d2):
    A = np.array([d1, -d2]).T
    t = np.linalg.solve(A, c2 - c1)
    return c1 + t[0] * d1


def _refine_tag_edges(lin, corners, module_px, iters=1, max_shift=None, max_side_ratio=None, local_levels=False, stats=None):
    """검은 테두리 바깥 모서리 4개를 50% 교차점 직선 맞춤으로 다시 구해 꼭짓점을 교점으로 만든다.
    번짐(대칭 PSF)에 대해 편향이 없다. 실패하면 None.
    iters: 앞 결과에서 다시 맞추는 횟수.  max_shift: 처음 꼭짓점에서 허용하는 최대 이동(px, 기본 max(2, 0.5 모듈)).
    max_side_ratio: 네 변 길이 최대/최소 상한 (None = 검사 안 함).  check_scale 은 기본값(1회, 2 px)을 쓴다."""
    c0 = np.asarray(corners, np.float64)
    c = c0
    for _ in range(max(1, int(iters))):
        if stats is not None:
            del stats[:]                                      # 마지막 반복의 잔차만 남긴다
        r = _refine_edges_once(lin, c, module_px, local_levels, stats) if local_levels else _refine_edges_once(lin, c, module_px)
        if r is None:
            return None
        c = r
    if max_shift is None:
        lim = max(2.0, 0.5 * (min(_quad_modules(c0)) if module_px is None else module_px))
    else:
        lim = max_shift
    if np.abs(c - c0).max() > lim:
        return None
    if max_side_ratio is not None:
        sides = [np.linalg.norm(c[(k + 1) % 4] - c[k]) for k in range(4)]
        if max(sides) > max_side_ratio * min(sides):
            return None
    return c


def _quad_modules(c, nb=8):
    """각 변에 수직인 방향의 모듈 크기(px) = (사각형 넓이 / 변 길이) / nb. 비스듬히 본(원근) 태그용."""
    x, y = c[:, 0], c[:, 1]
    area = 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))
    return [area / max(np.linalg.norm(c[(k + 1) % 4] - c[k]), 1e-9) / nb for k in range(4)]


def _running_median(v, k=7):
    if len(v) < k:
        return np.full_like(v, np.median(v))
    pad = k // 2
    vp = np.pad(v, pad, mode="edge")
    return np.median(np.lib.stride_tricks.sliding_window_view(vp, k), axis=1)


def _refine_edges_once(lin, corners, module_px, local_levels=False, stats=None):
    """module_px: 숫자(네 변 같은 모듈) 또는 None(현재 사각형에서 변마다 계산 — 원근으로 눌린 태그).
    local_levels: 검정/흰색 수준을 변 전체가 아니라 표본 줄마다(이동 중앙값) 잡는다 — 그림자가 태그를 가로지를 때.
    stats: 리스트를 주면 변마다 직선 잔차 RMS(px)를 덧붙인다."""
    if local_levels:
        return _refine_edges_local(lin, corners, module_px, stats)
    c = np.asarray(corners, np.float64)
    ctr = c.mean(0)
    mods = _quad_modules(c) if module_px is None else [module_px] * 4
    lines = []
    for k in range(4):
        mk = mods[k]
        a, b = c[k], c[(k + 1) % 4]
        L = np.linalg.norm(b - a)
        if L < 8:
            return None
        u = (b - a) / L
        n = np.array([-u[1], u[0]])
        if n @ (ctr - (a + b) / 2) > 0:
            n = -n                                            # 바깥쪽
        ts = np.arange(0.18 * L, 0.82 * L, 0.5)
        reach = 0.85 * mk
        ss = np.arange(-reach, reach + 1e-9, 0.25)
        P = a + ts[:, None, None] * u + ss[None, :, None] * n
        prof = _sample(lin, P)
        inner = (ss < -0.4 * mk) & (ss > -0.65 * mk)
        outer = ss > 0.45 * mk
        if inner.sum() < 1 or outer.sum() < 1:
            return None
        B = float(np.median(prof[:, inner]))
        Wt = float(np.median(prof[:, outer]))
        if Wt - B < 0.03:
            return None
        half = 0.5 * (B + Wt)
        pts = []
        above = prof >= half
        for r in range(len(ts)):
            tr = np.nonzero(~above[r, :-1] & above[r, 1:])[0]
            if len(tr) == 0:
                continue
            j = tr[np.argmin(np.abs(ss[tr]))]
            f0, f1 = prof[r, j], prof[r, j + 1]
            e = ss[j] + (half - f0) / (f1 - f0 + 1e-12) * (ss[j + 1] - ss[j])
            pts.append(a + ts[r] * u + e * n)
        if len(pts) < 6:
            return None
        lines.append(_fit_line(np.array(pts)))
    return np.array([_intersect(*lines[(k - 1) % 4], *lines[k]) for k in range(4)])


def _refine_edges_local(lin, corners, module_px, stats=None):
    """_refine_edges_once 와 같되 표본 줄마다 검정/흰색 수준을 잡고(이동 중앙값), 대비가 약한 줄은 버린다."""
    c = np.asarray(corners, np.float64)
    ctr = c.mean(0)
    mods = _quad_modules(c) if module_px is None else [module_px] * 4
    lines = []
    for k in range(4):
        mk = mods[k]
        a, b = c[k], c[(k + 1) % 4]
        L = np.linalg.norm(b - a)
        if L < 8:
            return None
        u = (b - a) / L
        n = np.array([-u[1], u[0]])
        if n @ (ctr - (a + b) / 2) > 0:
            n = -n
        ts = np.arange(0.18 * L, 0.82 * L, 0.5)
        reach = 0.85 * mk
        ss = np.arange(-reach, reach + 1e-9, 0.25)
        P = a + ts[:, None, None] * u + ss[None, :, None] * n
        prof = _sample(lin, P)
        inner = (ss < -0.4 * mk) & (ss > -0.65 * mk)
        outer = ss > 0.45 * mk
        if inner.sum() < 1 or outer.sum() < 1:
            return None
        Br = _running_median(np.median(prof[:, inner], axis=1))
        Wr = _running_median(np.median(prof[:, outer], axis=1))
        con = Wr - Br
        cmed = float(np.median(con))
        if cmed < 0.03:
            return None
        half = 0.5 * (Br + Wr)[:, None]                       # 줄마다 50 % 수준 (벡터화)
        trans = (prof[:, :-1] < half) & (prof[:, 1:] >= half)
        dist = np.where(trans, np.abs(ss[:-1])[None, :], np.inf)
        j = np.argmin(dist, axis=1)
        rows = np.arange(len(ts))
        ok = np.isfinite(dist[rows, j]) & (con >= 0.4 * cmed)
        if ok.sum() < 6:
            return None
        rows, j = rows[ok], j[ok]
        f0, f1 = prof[rows, j], prof[rows, j + 1]
        e = ss[j] + (half[rows, 0] - f0) / (f1 - f0 + 1e-12) * (ss[j + 1] - ss[j])
        pts = a + ts[rows, None] * u + e[:, None] * n
        cc, dd = _fit_line(pts)
        if stats is not None:
            nr = np.array([-dd[1], dd[0]])
            stats.append(float(np.sqrt(np.mean(((pts - cc) @ nr) ** 2))))
        lines.append((cc, dd))
    return np.array([_intersect(*lines[(k - 1) % 4], *lines[k]) for k in range(4)])


def _diag_center(c):
    return _intersect(c[0], c[2] - c[0], c[1], c[3] - c[1])


def _fit_affine(src_mm, dst_px):
    """mm → px 2x3 아핀 (최소제곱) 과 잔차 RMS(px)."""
    src = np.asarray(src_mm, np.float64)
    dst = np.asarray(dst_px, np.float64)
    X = np.hstack([src, np.ones((len(src), 1))])
    M, *_ = np.linalg.lstsq(X, dst, rcond=None)
    A = M.T
    rms = float(np.sqrt(np.mean(np.sum((X @ M - dst) ** 2, axis=1))))
    return A, rms


def _apply(A, pts):
    pts = np.asarray(pts, np.float64)
    return pts @ A[:, :2].T + A[:, 2]


def _rect_median(lin, A, rect_mm, step_px=0.5):
    (x0, y0), (x1, y1) = rect_mm
    mm_per_px = 1.0 / np.linalg.norm(A[:, 0])
    st = step_px * mm_per_px
    xs = np.arange(x0, x1, st)
    ys = np.arange(y0, y1, st)
    if len(xs) < 1 or len(ys) < 1:
        return float("nan")
    gx, gy = np.meshgrid(xs, ys)
    P = _apply(A, np.stack([gx.ravel(), gy.ravel()], 1)).reshape(len(ys), len(xs), 2)
    return float(np.median(_sample(lin, P)))


def _gauge_clearance_mm(spec, gi):
    """게이지 선 gi 의 중심에서 x 방향으로 가장 가까운 다른 잉크(이웃 게이지·태그) 가장자리까지 거리."""
    g = spec["gauge_lines"][gi]
    x = g["p0_mm"][0]
    feats = [(o["p0_mm"][0] - o["nominal_mm"] / 2, o["p0_mm"][0] + o["nominal_mm"] / 2)
             for j, o in enumerate(spec["gauge_lines"]) if j != gi]
    h = spec["tag_size_mm"] / 2
    feats += [(c[0] - h, c[0] + h) for c in spec["tag_centers_mm"]]
    d = [a - x if a > x else x - b for a, b in feats if a > x or b < x]
    return min(d) if d else 10.0


def _measure_gauge(lin, A, g, span, gsd_mm, ratio, clear_mm=10.0, n_seg=8):
    """게이지 선 하나의 폭 (px 단위 결과들). 프로파일은 영상에서 선에 수직.
    흰색 기준 띠는 선 가장자리에서 번짐이 빠진 곳부터, 이웃 잉크의 번짐이 닿기 전까지."""
    P0, P1 = _apply(A, [g["p0_mm"], g["p1_mm"]])
    d = P1 - P0
    L = np.linalg.norm(d)
    u = d / L
    n = np.array([-u[1], u[0]])
    w_px = g["nominal_mm"] / gsd_mm
    g_out = min(w_px / 2 + max(2.8 / gsd_mm, 6.0), clear_mm / gsd_mm - 2.5)
    g_in = min(w_px / 2 + max(1.2 / gsd_mm, 3.0), g_out - 1.5)
    ds = 0.25
    ss = np.arange(-g_out, g_out + 1e-9, ds)
    ts = np.arange(span[0] * L, span[1] * L, 0.5)
    P = P0 + ts[:, None, None] * u + ss[None, :, None] * n
    h, w = lin.shape
    if P[..., 0].min() < 0 or P[..., 1].min() < 0 or P[..., 0].max() > w - 1 or P[..., 1].max() > h - 1:
        return None
    prof = _sample(lin, P)
    wm = np.abs(ss) >= g_in
    im = ~wm
    area, fwhm, th50, peak = [], [], [], []
    for idx in np.array_split(np.arange(len(ts)), n_seg):
        if len(idx) == 0:
            continue
        p = prof[idx].mean(0)
        cb = np.polyfit(ss[wm], p[wm], 1)
        Wl = np.polyval(cb, ss)
        dk = (Wl - p) / np.maximum(Wl * (1.0 - ratio), 1e-6)  # 0 = 흰 종이, 1 = 인쇄 검정
        area.append(float(dk[im].sum() * ds))
        sub = np.where(im, dk, -1.0)
        k = int(np.argmax(sub))
        pk = float(dk[k])
        peak.append(pk)

        def cross(level):
            if pk < level:
                return 0.0
            l = k
            while l > 0 and dk[l] >= level:
                l -= 1
            r = k
            while r < len(dk) - 1 and dk[r] >= level:
                r += 1
            sl = ss[l] + (level - dk[l]) / (dk[l + 1] - dk[l] + 1e-12) * ds
            sr = ss[r] - (level - dk[r]) / (dk[r - 1] - dk[r] + 1e-12) * ds
            return float(sr - sl)

        fwhm.append(cross(0.5 * pk) if pk > 0.05 else float("nan"))
        th50.append(cross(0.5))
    return dict(area_px=float(np.mean(area)), area_seg_std_px=float(np.std(area)),
                fwhm_px=float(np.nanmedian(fwhm)) if np.isfinite(fwhm).any() else None,
                th50_px=float(np.median(th50)), peak=float(np.mean(peak)),
                line_px=[P0.tolist(), P1.tolist()])


def _detect_cards(gray, spec, gsd_mm, tile=2048):
    """태그 검출(필요하면 축소/타일) → ([(id, corners_px_fullres)], tag_px)"""
    return _detect_all(gray, spec["tag_size_mm"] / gsd_mm, spec["dictionary"], tile)


def _detect_all(gray, tag_px, dn, tile=2048):
    """예상 태그 크기 tag_px 에 맞춰 원본/축소/확대 + 타일 검출. OpenCV 좌표(픽셀 중심 = 정수)."""
    win = int(np.clip(round(tag_px / 8 * 0.55), 2, 12))
    if tag_px > 120:                                          # 크게 찍힌 태그: 축소해 찾고 원본 ROI 에서 다시
        s = 64.0 / tag_px
        small = cv2.resize(gray, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        coarse = _detect_tiled(small, tag_px * s, dn, tile, refine=False)
        dets = []
        for i, c in coarse:
            cf = (c + 0.5) / s - 0.5
            m = 0.6 * tag_px
            x0, y0 = np.floor(cf.min(0) - m).astype(int)
            x1, y1 = np.ceil(cf.max(0) + m).astype(int)
            x0, y0 = max(0, x0), max(0, y0)
            sub = gray[y0:y1, x0:x1]
            best = None
            for j, c2 in _detect(sub, tag_px, dn, True, win):
                c2 = c2 + [x0, y0]
                if j == i and np.linalg.norm(c2.mean(0) - cf.mean(0)) < 0.3 * tag_px:
                    best = c2
            dets.append((i, best if best is not None else cf))
        return dets, tag_px
    if tag_px < 28:                                           # 작은 태그: 확대해서 찾는다
        s = min(3.0, 36.0 / tag_px)
        big = cv2.resize(gray, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC)
        dets = _detect_tiled(big, tag_px * s, dn, tile, True, int(np.clip(round(tag_px * s / 8 * 0.55), 2, 12)))
        return [(i, (c + 0.5) / s - 0.5) for i, c in dets], tag_px
    return _detect_tiled(gray, tag_px, dn, tile, True, win), tag_px


def check_scale(ortho_jpg_path, ortho_meta, card_json_path=DEFAULT_CARD_JSON, linearize=True,
                refine_edges=True, debug_path=None):
    """정사영상에서 기준 카드를 찾아 축척 오차와 게이지 선 폭을 잰다.

    반환 (found=True 일 때):
      found, card ('A'/'B'), tag_ids, nominal_mm (태그 중심 간격 정의값), measured_mm (meta gsd 로 잰 값),
      scale_error_pct = (measured/nominal - 1)*100  (+ 면 정사영상이 길이를 크게 잰다),
      scale_factor = nominal/measured  (정사영상에서 잰 길이·폭에 곱하면 보정),
      gsd_mm (meta), gsd_mm_corrected = gsd_mm*scale_factor,
      tag_size_mm [태그0, 태그1] (테두리 한 변 평균), fit_rms_px (태그 꼭짓점 아핀 잔차),
      black_white_ratio (인쇄 검정/종이 흰색, 선형광),
      gauge: [{nominal_mm, measured_mm (면적법, 카드 축척 보정), measured_mm_raw (meta gsd),
               fwhm_mm, thresh50_mm, peak_contrast, seg_std_mm, line_px}],
      card_px_bbox [x0, y0, x1, y1], tag_corners_px {id: 4x2}, cards (찾은 카드 전부), seconds
    found=False 면 reason 과 tags_detected 가 있다.
    """
    t0 = time.time()
    with open(card_json_path, encoding="utf-8") as f:
        spec = json.load(f)
    try:
        gsd_mm = float(ortho_meta["gsd_m"]) * 1000.0
    except (KeyError, TypeError, ValueError):
        return dict(found=False, reason="meta has no gsd_m")
    img = ortho_jpg_path if isinstance(ortho_jpg_path, np.ndarray) else _imread(ortho_jpg_path)
    if img is None:
        return dict(found=False, reason="cannot read image")
    gray = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    dets, tag_px = _detect_cards(gray, spec, gsd_mm)
    nominal = float(spec["tag_center_distance_mm"])
    nom_px = nominal / gsd_mm
    cards = []
    used = set()
    for var in spec["variants"]:
        ia, ib = var["tag_ids"]
        best = None
        for ka, (i, ca) in enumerate(dets):
            if i != ia or ka in used:
                continue
            for kb, (j, cb) in enumerate(dets):
                if j != ib or kb in used:
                    continue
                v = cb.mean(0) - ca.mean(0)
                dist = np.linalg.norm(v)
                ex = ca[1] - ca[0]                            # 태그0 의 +x (TL→TR)
                cosang = (v @ ex) / (dist * np.linalg.norm(ex) + 1e-9)
                err = abs(dist / nom_px - 1)
                if err < 0.35 and cosang > 0.94 and (best is None or err < best[0]):
                    best = (err, ka, kb)
        if best:
            used.update(best[1:])
            cards.append((var, dets[best[1]][1], dets[best[2]][1]))
    if not cards:
        return dict(found=False, reason="no card (tag pair) found", tags_detected=sorted({i for i, _ in dets}),
                    gsd_mm=gsd_mm, expected_tag_px=round(tag_px, 1), seconds=round(time.time() - t0, 2))

    results = []
    H, W = gray.shape[:2]
    for var, ca, cb in cards:
        src = np.array(spec["tag_corners_mm"]).reshape(8, 2)
        A0, _ = _fit_affine(src, np.vstack([ca, cb]))
        (ox0, oy0), (ox1, oy1) = spec["card_outline_mm"]
        box = _apply(A0, [[ox0, oy0], [ox1, oy0], [ox1, oy1], [ox0, oy1]])
        mpx = 4.0 / gsd_mm
        x0, y0 = np.floor(box.min(0) - mpx).astype(int)
        x1, y1 = np.ceil(box.max(0) + mpx).astype(int)
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
        lin = _to_linear(img[y0:y1, x0:x1], linearize)
        off = np.array([x0, y0], np.float64)
        tc = []
        refined = []
        for c in (ca, cb):
            r = _refine_tag_edges(lin, c - off, tag_px / 8) if refine_edges else None
            refined.append(r is not None)
            tc.append((r + off) if r is not None else c)
        A, rms = _fit_affine(src, np.vstack(tc))
        ctr = [_diag_center(c) for c in tc]
        dist_px = float(np.linalg.norm(ctr[1] - ctr[0]))
        measured = dist_px * gsd_mm
        scale_factor = nominal / measured
        side = [float(np.mean([np.linalg.norm(c[(k + 1) % 4] - c[k]) for k in range(4)]) * gsd_mm) for c in tc]
        Ar = A.copy()
        Ar[:, 2] -= off
        blk = _rect_median(lin, Ar, spec["black_ref_rect_mm"])
        wht = _rect_median(lin, Ar, spec["white_ref_rect_mm"])
        ratio = float(np.clip(blk / wht, 0.0, 0.9)) if wht > 1e-4 else 0.9
        gauges = []
        for gi, g in enumerate(spec["gauge_lines"]):
            m = _measure_gauge(lin, Ar, g, spec.get("gauge_measure_span", [0.1, 0.9]), gsd_mm, ratio,
                               _gauge_clearance_mm(spec, gi))
            if m is None:
                gauges.append(dict(nominal_mm=g["nominal_mm"], measured_mm=None, reason="outside image"))
                continue
            raw = m["area_px"] * gsd_mm
            gauges.append(dict(
                nominal_mm=g["nominal_mm"],
                measured_mm=round(raw * scale_factor, 4),
                measured_mm_raw=round(raw, 4),
                fwhm_mm=None if m["fwhm_px"] is None else round(m["fwhm_px"] * gsd_mm * scale_factor, 4),
                thresh50_mm=round(m["th50_px"] * gsd_mm * scale_factor, 4),
                peak_contrast=round(m["peak"], 3),
                seg_std_mm=round(m["area_seg_std_px"] * gsd_mm * scale_factor, 4),
                line_px=[[round(v + o, 2) for v, o in zip(p, off)] for p in m["line_px"]],
            ))
        bb = _apply(A, [[ox0, oy0], [ox1, oy0], [ox1, oy1], [ox0, oy1]])
        results.append(dict(
            found=True, card=var["label"], tag_ids=list(var["tag_ids"]),
            nominal_mm=nominal, measured_mm=round(measured, 4),
            scale_error_pct=round((measured / nominal - 1.0) * 100.0, 4),
            scale_factor=round(scale_factor, 6),
            gsd_mm=round(gsd_mm, 6), gsd_mm_corrected=round(gsd_mm * scale_factor, 6),
            tag_size_mm=[round(v, 4) for v in side], tag_size_nominal_mm=spec["tag_size_mm"],
            fit_rms_px=round(rms, 3), edges_refined=refined,
            black_white_ratio=round(ratio, 4),
            gauge=gauges,
            card_px_bbox=[round(float(v), 1) for v in (*bb.min(0), *bb.max(0))],
            tag_corners_px={str(var["tag_ids"][k]): np.round(tc[k], 3).tolist() for k in range(2)},
            tag_centers_px=[np.round(c, 3).tolist() for c in ctr],
        ))
    out = dict(results[0])
    out["cards"] = [{k: r[k] for k in ("card", "tag_ids", "measured_mm", "scale_error_pct", "scale_factor", "card_px_bbox")}
                    for r in results]
    out["seconds"] = round(time.time() - t0, 2)
    if debug_path:
        _debug_overlay(img, results, debug_path)
    return out


def detect_markers(img_bgr_or_path, gsd_m, ids=None, tag_mm=MARKER_TAG_MM, linearize=True, refine_edges=True):
    """정사영상 위의 AprilTag 36h11 태그를 ID 와 상관없이 모두 찾는다 (카드용 ID 0~3 도 포함 — 거르기는 호출 쪽).

    gsd_m: 정사영상 m/px (meta["gsd_m"]; meta dict 를 그대로 줘도 된다). 태그 크기 예상(tag_mm)은 검출 축척에만 쓰며
           실제 크기가 절반~네 배 사이면 찾는다.  ids: 이 ID 들만 돌려준다 (None = 전부).
    좌표는 hazards 계약 규약 — 픽셀 중심 = 정수 + 0.5 (= OpenCV 좌표 + 0.5).
    반환: [{id, center_px [x, y], corners_px [TL, TR, BR, BL], size_mm_measured, refined}]  (id, y, x 순)
      center_px = 꼭짓점 대각선 교점, size_mm_measured = 네 변 평균 × gsd (축척 보정 전).
      같은 ID 가 두 번 보이면 둘 다 돌려준다.
    """
    if isinstance(gsd_m, dict):
        gsd_m = gsd_m.get("gsd_m")
    gsd_mm = float(gsd_m) * 1000.0
    img = img_bgr_or_path if isinstance(img_bgr_or_path, np.ndarray) else _imread(img_bgr_or_path)
    if img is None:
        return []
    gray = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    dets, _ = _detect_all(gray, tag_mm / gsd_mm, "DICT_APRILTAG_36h11")
    want = None if ids is None else {int(i) for i in ids}
    H, W = gray.shape[:2]
    out = []
    for i, c in dets:
        if want is not None and i not in want:
            continue
        side = float(np.mean([np.linalg.norm(c[(k + 1) % 4] - c[k]) for k in range(4)]))
        r = None
        if refine_edges and side >= 8:
            m = 0.6 * side
            x0, y0 = np.floor(c.min(0) - m).astype(int)
            x1, y1 = np.ceil(c.max(0) + m).astype(int)
            x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
            off = np.array([x0, y0], np.float64)
            # 작은·기울어진 태그는 번짐으로 aruco 꼭짓점이 2 px 넘게 안쪽으로 깎일 수 있어 반복 맞춤 + 넓은 허용
            r = _refine_tag_edges(_to_linear(img[y0:y1, x0:x1], linearize), c - off, side / 8,
                                  iters=3, max_shift=max(3.5, 0.9 * side / 8), max_side_ratio=1.3)
            if r is not None:
                r = r + off
        cc = r if r is not None else c
        ctr = _diag_center(cc)
        size = float(np.mean([np.linalg.norm(cc[(k + 1) % 4] - cc[k]) for k in range(4)])) * gsd_mm
        out.append(dict(id=int(i), center_px=[round(float(v) + 0.5, 3) for v in ctr],
                        corners_px=[[round(float(v) + 0.5, 3) for v in p] for p in cc],
                        size_mm_measured=round(size, 3), refined=r is not None))
    out.sort(key=lambda d: (d["id"], d["center_px"][1], d["center_px"][0]))
    return out


DEFAULT_BOARD_JSON = os.path.normpath(os.path.join(HERE, "..", "site", "3dscan", "targets", "trench_board.json"))


def load_board(board_json=DEFAULT_BOARD_JSON):
    if isinstance(board_json, dict):
        return board_json
    with open(board_json, encoding="utf-8") as f:
        return json.load(f)


def _board_detector(dict_name, min_rate):
    """영상 프레임용 aruco 설정: 번짐·그림자에 강하게 (칸 가운데만 읽기, 큰 문턱 창, 둥근 꼭짓점 허용)."""
    p = cv2.aruco.DetectorParameters()
    p.minMarkerPerimeterRate = float(min_rate)
    p.maxMarkerPerimeterRate = 4.0
    p.adaptiveThreshWinSizeMax = 53
    p.perspectiveRemovePixelPerCell = 8
    p.perspectiveRemoveIgnoredMarginPerCell = 0.3
    p.polygonalApproxAccuracyRate = 0.06
    p.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    p.cornerRefinementWinSize = 3
    p.cornerRefinementMaxIterations = 60
    p.cornerRefinementMinAccuracy = 0.005
    return cv2.aruco.ArucoDetector(_aruco_dict(dict_name), p)


def _board_candidates(gray, spec, min_tag_px, ids, upsample):
    h, w = gray.shape[:2]
    det = _board_detector(spec["dictionary"], 2.0 * min_tag_px * 4 / max(h, w) / 2)
    out = []

    def run(g, s):
        c, i, _ = det.detectMarkers(g)
        if i is None:
            return
        for cc, ii in zip(c, i.ravel()):
            ii = int(ii)
            if ii not in ids:
                continue
            cc = (cc.reshape(4, 2).astype(np.float64) + 0.5) / s - 0.5
            side = np.mean([np.linalg.norm(cc[(k + 1) % 4] - cc[k]) for k in range(4)])
            if any(j == ii and np.linalg.norm(d.mean(0) - cc.mean(0)) < 0.3 * side for j, d in out):
                continue
            out.append((ii, cc))

    run(gray, 1.0)
    if upsample:
        per = {}
        for ii, _ in out:
            for bi, b in enumerate(spec["boards"]):
                if ii in b["tag_ids"]:
                    per[bi] = per.get(bi, 0) + 1
        if not per or max(per.values()) < 4:                 # 판 하나의 태그 4개를 다 못 찾았으면 1.5배로 한 번 더
            up = cv2.resize(cv2.GaussianBlur(gray, (0, 0), 0.7), None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
            run(up, 1.5)
    return out


def detect_board(bgr, board_json=DEFAULT_BOARD_JSON, pixel_center=0.0, refine_edges=True, min_tag_px=12, linearize=True,
                 fast=False):
    """영상 프레임(원근 있음)에서 굴착 기준판 태그를 찾는다. 기준판 JSON 에 있는 ID 만 돌려준다.

    bgr: BGR/회색 ndarray 또는 파일 경로.  board_json: trench_board.json 경로 또는 dict.
    pixel_center: 0.0 = OpenCV 규약(픽셀 중심 = 정수, 기본) / 0.5 = COLMAP 규약(픽셀 중심 = 정수 + 0.5).
                  내부 파라미터 K 와 같은 규약을 고를 것.
    반환: [{id, board ('1'/'2'), board_index, slot (0 TL,1 TR,2 BR,3 BL), corners_px [TL,TR,BR,BL],
            center_px (대각선 교점), side_px, obj_mm [[x,y,0] x4] (판 좌표, mm), refined}]  (board_index, slot 순)
    같은 ID 가 두 번 보이면 둘 다 돌려준다 (duplicate=True).
    refined=False 인 태그는 aruco 꼭짓점 그대로라 번짐이 크면 수 px 틀릴 수 있다 — 축척에는 refined=True 만 쓰는 것을 권장.
    fast=True 면 1.5배 확대 재검출을 건너뛴다 (프레임당 약 0.1 s, 기본은 못 찾은 태그가 있을 때만 약 0.2 s 더).
    """
    spec = load_board(board_json)
    img = bgr if isinstance(bgr, np.ndarray) else _imread(bgr)
    if img is None:
        return []
    gray = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    where = {}
    for bi, b in enumerate(spec["boards"]):
        for slot, tid in enumerate(b["tag_ids"]):
            where[int(tid)] = (bi, b["label"], slot)
    dets = _board_candidates(gray, spec, min_tag_px, where, upsample=not fast)
    H, W = gray.shape[:2]
    out = []
    for i, c in dets:
        r = None
        if refine_edges:
            side = max(np.linalg.norm(c[(k + 1) % 4] - c[k]) for k in range(4))
            m = 0.6 * side
            x0, y0 = np.floor(c.min(0) - m).astype(int)
            x1, y1 = np.ceil(c.max(0) + m).astype(int)
            x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
            off = np.array([x0, y0], np.float64)
            mod = min(_quad_modules(c))
            st_ = []
            if mod >= 1.2:
                r = _refine_tag_edges(_to_linear(img[y0:y1, x0:x1], linearize), c - off, None,
                                      iters=3, max_shift=max(3.5, 0.9 * mod), max_side_ratio=4.0,
                                      local_levels=True, stats=st_)
                if r is not None:
                    r = r + off
        cc = r if r is not None else c
        bi, lb, slot = where[i]
        obj = [[float(x), float(y), 0.0] for x, y in spec["tag_corners_mm"][slot]]
        out.append(dict(id=int(i), board=lb, board_index=bi, slot=slot,
                        corners_px=[[round(float(v) + pixel_center, 3) for v in p] for p in cc],
                        center_px=[round(float(v) + pixel_center, 3) for v in _diag_center(cc)],
                        side_px=round(float(np.mean([np.linalg.norm(cc[(k + 1) % 4] - cc[k]) for k in range(4)])), 2),
                        obj_mm=obj, refined=r is not None,
                        edge_rms_px=round(max(st_), 3) if (r is not None and st_) else None))
    seen = {}
    for d in out:
        seen[d["id"]] = seen.get(d["id"], 0) + 1
    for d in out:
        if seen[d["id"]] > 1:
            d["duplicate"] = True
    out.sort(key=lambda d: (d["board_index"], d["slot"], d["center_px"][1]))
    return out


def board_pose(dets, K, dist=None, board=None, prefer_refined=True):
    """detect_board 결과 + 내부 파라미터 K (3x3, detections 와 같은 픽셀 규약) → 판의 카메라 자세 (PnP, 확인용).

    board: '1'/'2' 또는 None(태그를 가장 많이 찾은 판).  같은 ID 가 두 번 보이면 그 ID 는 뺀다.
    prefer_refined: 그 판에 refined=True 태그가 하나라도 있으면 그것만 쓴다.
    반환: {ok, board, n_tags, reliable (n_tags >= 3), ids, rvec, tvec_m, R (판→카메라), camera_center_board_m,
           distance_m (카메라→판 가운데), view_angle_deg (시선과 판 법선 사이), reproj_rms_px, reproj_max_px, corners_cam_m {id: 4x3}}
    합성 시험: 태그 4개 거리 오차 P95 0.09 %, 3개 0.21 %, 2개 2 %, 1개 4 % — 확인에는 reliable=True 만 쓸 것.
    한 장으로 얻는 실측 기준: 카메라에서 판까지 거리·판 꼭짓점의 카메라 좌표(m). K 오차 1 % ≈ 거리 오차 1 %.
    """
    dets = [d for d in dets if not d.get("duplicate")]
    if board is None:
        cnt = {}
        for d in dets:
            cnt[d["board"]] = cnt.get(d["board"], 0) + 1
        if not cnt:
            return dict(ok=False, reason="no board tags")
        board = max(cnt, key=lambda k: cnt[k])
    sel = [d for d in dets if d["board"] == str(board)]
    if not sel:
        return dict(ok=False, reason=f"no tags of board {board}")
    if prefer_refined and any(d.get("refined") for d in sel):
        sel = [d for d in sel if d.get("refined")]
    obj = np.array([p for d in sel for p in d["obj_mm"]], np.float64) / 1000.0
    img = np.array([p for d in sel for p in d["corners_px"]], np.float64)
    K = np.asarray(K, np.float64)
    D = np.zeros(5) if dist is None else np.asarray(dist, np.float64)
    ok, rvec, tvec = cv2.solvePnP(obj, img, K, D, flags=cv2.SOLVEPNP_IPPE)
    if not ok:
        return dict(ok=False, reason="solvePnP failed", board=str(board), n_tags=len(sel))
    rvec, tvec = cv2.solvePnPRefineLM(obj, img, K, D, rvec, tvec)
    proj, _ = cv2.projectPoints(obj, rvec, tvec, K, D)
    e = np.linalg.norm(proj.reshape(-1, 2) - img, axis=1)
    R, _ = cv2.Rodrigues(rvec)
    t = tvec.reshape(3)
    nrm = R @ np.array([0.0, 0.0, 1.0])
    ang = math.degrees(math.acos(min(1.0, abs(float(nrm @ (t / np.linalg.norm(t)))))))
    cam = (R @ obj.T).T + t
    return dict(ok=True, board=str(board), n_tags=len(sel), reliable=len(sel) >= 3, ids=[d["id"] for d in sel],
                rvec=rvec.reshape(3).tolist(), tvec_m=t.tolist(), R=R.tolist(),
                camera_center_board_m=(-R.T @ t).tolist(), distance_m=float(np.linalg.norm(t)), view_angle_deg=ang,
                reproj_rms_px=float(np.sqrt((e ** 2).mean())), reproj_max_px=float(e.max()),
                corners_cam_m={str(d["id"]): cam[4 * k:4 * k + 4].tolist() for k, d in enumerate(sel)})


def _debug_overlay(img, results, path):
    vis = img.copy() if img.ndim == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    for r in results:
        for c in r["tag_corners_px"].values():
            cv2.polylines(vis, [np.round(np.array(c) * 4).astype(np.int32)], True, (0, 255, 0), 1, cv2.LINE_AA, 2)
        a, b = r["tag_centers_px"]
        cv2.line(vis, tuple(np.round(np.array(a) * 4).astype(int)), tuple(np.round(np.array(b) * 4).astype(int)),
                 (255, 128, 0), 1, cv2.LINE_AA, 2)
        for g in r["gauge"]:
            if g.get("line_px"):
                p, q = g["line_px"]
                cv2.line(vis, tuple(np.round(np.array(p) * 4).astype(int)), tuple(np.round(np.array(q) * 4).astype(int)),
                         (0, 0, 255), 1, cv2.LINE_AA, 2)
        x0, y0, x1, y1 = r["card_px_bbox"]
        cv2.rectangle(vis, (int(x0), int(y0)), (int(x1), int(y1)), (0, 220, 255), 1)
    r0 = results[0]
    x0, y0, x1, y1 = [int(v) for v in r0["card_px_bbox"]]
    m = 20
    crop = vis[max(0, y0 - m):y1 + m, max(0, x0 - m):x1 + m]
    ok, buf = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 92])
    if ok:
        buf.tofile(path)


def main():
    ap = argparse.ArgumentParser(description="kgeoScan crack reference card: scale / width check on a wall orthophoto")
    ap.add_argument("--ortho", help="X_ortho.jpg")
    ap.add_argument("--meta", help="X_ortho.json (gsd_m)")
    ap.add_argument("--card", default=DEFAULT_CARD_JSON, help="crack_card.json")
    ap.add_argument("--debug", help="write an overlay crop (jpg) of the detected card")
    ap.add_argument("--no-linearize", action="store_true", help="measure in sRGB values instead of linear light")
    ap.add_argument("--make-card", metavar="DIR", help="(re)generate crack_card.json / PDF / PNG into DIR")
    ap.add_argument("--markers", action="store_true", help="with --ortho/--meta: list every 36h11 tag (detect_markers)")
    ap.add_argument("--make-markers", metavar="OUT", help="write a site marker sheet OUT.pdf / OUT.png")
    ap.add_argument("--site", default="", help="site name printed on the marker stickers")
    ap.add_argument("--ids", default="10,11,12,13", help="marker ids, comma separated (>= 10)")
    ap.add_argument("--make-trench-board", metavar="DIR", help="(re)generate trench_board.json / PDF / PNG into DIR")
    ap.add_argument("--detect-board", metavar="IMAGE", help="find trench-board tags in a video frame / photo")
    ap.add_argument("--board-json", default=None, help="trench_board.json (default: site/3dscan/targets)")
    ap.add_argument("--fx", type=float, help="with --detect-board: focal length px -> also print board_pose")
    ap.add_argument("--cx", type=float)
    ap.add_argument("--cy", type=float)
    a = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if a.make_card:
        spec = make_card_files(a.make_card)
        print(json.dumps({"written": a.make_card, "files": spec["files"]}, ensure_ascii=False))
        return
    if a.make_trench_board:
        spec = make_trench_board_files(a.make_trench_board)
        print(json.dumps({"written": a.make_trench_board, "files": spec["files"]}, ensure_ascii=False))
        return
    if a.detect_board:
        img = _imread(a.detect_board)
        dets = detect_board(img, a.board_json or DEFAULT_BOARD_JSON)
        res = {"detections": dets}
        if a.fx and img is not None:
            h, w = img.shape[:2]
            K = [[a.fx, 0, a.cx if a.cx is not None else (w - 1) / 2], [0, a.fx, a.cy if a.cy is not None else (h - 1) / 2], [0, 0, 1]]
            res["pose"] = board_pose(dets, K)
        print(json.dumps(res, indent=1))
        return
    if a.make_markers:
        r = make_marker_sheet(a.make_markers, a.site, [int(v) for v in a.ids.split(",") if v.strip()])
        print(json.dumps({k: r[k] for k in ("pdf", "png", "site_name", "ids")}, ensure_ascii=False))
        return
    if not a.ortho or not a.meta:
        ap.error("--ortho and --meta are required")
    with open(a.meta, encoding="utf-8") as f:
        meta = json.load(f)
    if a.markers:
        print(json.dumps(detect_markers(a.ortho, meta["gsd_m"], linearize=not a.no_linearize), indent=1))
        return
    res = check_scale(a.ortho, meta, a.card, linearize=not a.no_linearize, debug_path=a.debug)
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
