r"""
kgeoScan 위험요소 검출 (면 모드) → hazards.json  (형식: docs/hazards_contract.md)

  균열(C)  : crack_analysis.py 결과(ortho_cracks.json)를 공통 형식으로 옮김
  변색(D)  : 정사영상 Lab 색을 주변 배경(큰 중앙값 필터)과 비교 — 백태(밝고 무채색), 젖음·누수(어두움), 녹물(노랑·주황)
  요철(S)  : 높이 지도(벽 = 맞춘 평면 대비 앞뒤, 바닥 = 기준 높이 대비) — 벽 패임(박락 의심)·돌출, 바닥 패임·돌출
  변형(G)  : 벽 기울기·평탄도(높이 지도 평면 맞춤), 바닥 경사·평탄도
orthophoto.py 가 균열 분석 뒤에 build() 를 부른다. 단독 실행:
  python -I hazard_detect.py --ortho X_ortho.jpg --meta X_ortho.json [--overlay X_ortho.png] [--height-bin X_ortho_h.bin]
                             [--cracks X_ortho_cracks.json] --out <dir>

한계: 변색은 색만 보므로 벽에 붙은 물건·포스터·그림자도 잡힐 수 있다(subtype 은 추정).
      요철은 LiDAR 융합 메시(약 ±1 cm)라 1~2 cm 넘는 패임·돌출만 믿을 만하다.
"""
import argparse
import json
import math
import os
import time

import cv2
import numpy as np

DEFAULTS = dict(
    stain_work_mm=2.0,          # 변색 분석 해상도 (mm/px)
    stain_bg_mm=150.0,          # 배경(중앙값) 창 크기
    stain_dL=10.0,              # 밝기 차 (L*)
    stain_rust_db=10.0, stain_rust_da=3.0,
    stain_min_area_mm2=1000.0,  # 10 cm² 미만 무시
    stain_min_side_mm=15.0,
    stain_max_frac=0.4,         # 표면의 40 % 넘게 덮으면 조명·재료 차이로 봄
    stain_dark_floor=40.0,      # 이보다 더 어두우면(L* 차) 그림자·구멍·검은 물체 (젖은 자국은 이만큼 어둡지 않다)
    stain_texture_ratio=2.5,    # 영역 안 결(라플라시안)이 표면 중앙값의 이 배수를 넘으면 물체·식물
    stain_edge_frac=0.3,        # 경계의 30 % 넘게가 빈 곳에 닿으면 재구성 가장자리
    relief_thr_mm=12.0,         # 요철: 이보다 깊거나 높은 곳 (LiDAR 잡음 ±1 cm 위)
    relief_min_area_mm2=1500.0,
    relief_max_abs_mm=150.0,    # 이보다 크면 가구·계단·물체로 봄
    relief_edge_frac=0.3,       # 경계의 30 % 넘게가 빈 곳(메시 가장자리·구멍)에 닿으면 버림
)
SUBTYPE_KO = dict(efflorescence="백태(흰 변색)", water="젖음·누수 흔적(어두운 변색)", rust="녹물(노랑·주황 변색)", unknown="변색",
                  spall="패임(박락 의심)", protrusion="돌출(물체·배부름)", depression="패임·침하", tilt="기울기", flatness="평탄도")


def _polys(mask, scale, off=0.0, eps=1.5):
    """bool 마스크 → 정사영상 px 다각형 고리 목록 (바깥 경계만)"""
    cs, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rings = []
    for c in cs:
        a = cv2.approxPolyDP(c, eps, True).reshape(-1, 2).astype(np.float64)
        if len(a) >= 3:
            rings.append([[round(float(x * scale + off), 1), round(float(y * scale + off), 1)] for x, y in a])
    return rings


def _bbox(rings):
    a = np.array([p for r in rings for p in r])
    return [round(float(a[:, 0].min()), 1), round(float(a[:, 1].min()), 1), round(float(a[:, 0].max()), 1), round(float(a[:, 1].max()), 1)]


# ── 변색 ─────────────────────────────────────────────────────────────────────
def stains(img_rgb, valid, gsd, log, p, sf=1.0):
    wg = max(gsd, p["stain_work_mm"] / 1000.0)
    f = gsd / wg
    H, W = img_rgb.shape[:2]
    w2, h2 = max(8, int(round(W * f))), max(8, int(round(H * f)))
    small = cv2.resize(img_rgb, (w2, h2), interpolation=cv2.INTER_AREA)
    vs = cv2.resize(valid.astype(np.uint8), (w2, h2), interpolation=cv2.INTER_NEAREST) > 0
    vs = cv2.erode(vs.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    if vs.sum() < 500:
        return []
    lab = cv2.cvtColor(small, cv2.COLOR_RGB2LAB)
    k = int(min(255, max(15, round(p["stain_bg_mm"] / (wg * 1000))))) | 1
    bg = np.empty_like(lab)
    for ch in range(3):                                   # 빈 곳은 표면 중앙값으로 채운 뒤 큰 중앙값 필터 = 주변 배경
        c = lab[..., ch].copy()
        c[~vs] = int(np.median(c[vs]))
        bg[..., ch] = cv2.medianBlur(c, k)
    L = lab[..., 0].astype(np.float32) * (100 / 255.0); Lb = bg[..., 0].astype(np.float32) * (100 / 255.0)
    da = lab[..., 1].astype(np.float32) - bg[..., 1]; db = lab[..., 2].astype(np.float32) - bg[..., 2]
    dL = L - Lb
    masks = {
        "efflorescence": (dL > p["stain_dL"]) & (np.abs(da) < 6) & (np.abs(db) < 8),
        "water": (dL < -p["stain_dL"]) & (dL > -p["stain_dark_floor"]) & (np.abs(da) < 8) & (db < p["stain_rust_db"]),
        "rust": (db > p["stain_rust_db"]) & (da > p["stain_rust_da"]),
    }
    # 결: 얼룩·변색은 매끈하고, 식물·물건·엉성한 재구성은 결이 거칠다
    tex = cv2.boxFilter(np.abs(cv2.Laplacian(L, cv2.CV_32F, ksize=3)), -1, (9, 9))
    tex_med = float(np.median(tex[vs])) + 1e-3
    hole_edge = cv2.dilate((~vs).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    px_mm2 = (wg * 1000.0 * sf) ** 2
    min_px = p["stain_min_area_mm2"] / px_mm2
    min_side = p["stain_min_side_mm"] / (wg * 1000.0 * sf)
    items, dropped = [], 0
    for sub, m in masks.items():
        m = m & vs
        m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))) > 0
        n, lab_, st, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8), connectivity=8)
        for c in range(1, n):
            area = st[c, cv2.CC_STAT_AREA]
            if area < min_px:
                continue
            comp = lab_ == c
            if area > p["stain_max_frac"] * vs.sum():
                dropped += 1
                continue
            cnt, _ = cv2.findContours(comp.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            (_, _), (rw, rh), _ = cv2.minAreaRect(max(cnt, key=cv2.contourArea))
            if min(rw, rh) < min_side or area / max(1.0, rw * rh) < 0.2:      # 가는 띠(균열·줄눈·모서리 그늘)는 변색이 아님
                dropped += 1
                continue
            if tex[comp].mean() > p["stain_texture_ratio"] * tex_med:          # 결이 거침 → 물체·식물
                dropped += 1
                continue
            edge = comp & ~cv2.erode(comp.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
            if edge.sum() and (edge & hole_edge).sum() / edge.sum() > p["stain_edge_frac"]:
                dropped += 1                                                   # 재구성 가장자리
                continue
            rings = _polys(comp, 1.0 / f)
            if not rings:
                continue
            items.append(dict(type="stain", subtype=sub, geom=dict(type="polygon", rings=rings), bbox=_bbox(rings),
                              metrics=dict(area_mm2=round(float(area * px_mm2), 0), dL=round(float(dL[comp].mean()), 1),
                                           da=round(float(da[comp].mean()), 1), db=round(float(db[comp].mean()), 1)),
                              severity=1, label=SUBTYPE_KO[sub]))
    log(f"hazards: stains {len(items)} (dropped {dropped} thin/huge), work {wg * 1000:.1f} mm/px, bg window {k} px")
    return items


# ── 요철 ─────────────────────────────────────────────────────────────────────
def relief(hm, grid, gsd, surface, log, p, sf=1.0, exclude=None):
    """hm = 높이 지도 정보, grid = int16 (h, w) mm. exclude = 정사영상 px bool (카드 자리 등)"""
    s = int(hm.get("step", 1))
    nod = hm.get("nodata", -32768)
    ok = grid != nod
    if ok.sum() < 200:
        return []
    h = grid.astype(np.float32)
    h[~ok] = 0
    h = cv2.medianBlur(h, 5)                              # 격자 잡음 줄이기
    cell_mm = s * gsd * 1000.0 * sf
    min_cells = p["relief_min_area_mm2"] / cell_mm ** 2
    if exclude is not None:
        ex = exclude[s // 2::s, s // 2::s][:grid.shape[0], :grid.shape[1]]
        ok = ok & ~ex
    border = cv2.dilate((~ok).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    items, dropped = [], 0
    for sign in (-1, 1):
        m = ok & (sign * h >= p["relief_thr_mm"])
        m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)) > 0
        n, lab_, st, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8), connectivity=8)
        for c in range(1, n):
            if st[c, cv2.CC_STAT_AREA] < min_cells:
                continue
            comp = lab_ == c
            vals = h[comp]
            peak = float(vals.min() if sign < 0 else vals.max())
            if abs(peak) > p["relief_max_abs_mm"] or comp.sum() > 0.3 * ok.sum():
                dropped += 1
                continue
            edge = comp & ~cv2.erode(comp.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
            if edge.sum() and (edge & border).sum() / edge.sum() > p["relief_edge_frac"]:
                dropped += 1                              # 메시 가장자리 잡음
                continue
            if surface == "wall":
                sub = "spall" if sign < 0 else "protrusion"
            else:
                sub = "depression" if sign < 0 else "protrusion"
            rings = _polys(comp, s, off=s / 2.0, eps=1.0)
            if not rings:
                continue
            area = float(comp.sum() * cell_mm ** 2)
            items.append(dict(type="relief", subtype=sub, geom=dict(type="polygon", rings=rings), bbox=_bbox(rings),
                              metrics=dict(area_mm2=round(area, 0), depth_max_mm=round(peak * sf, 1),
                                           volume_cm3=round(float(np.abs(vals).sum() * cell_mm ** 2 * sf) / 1000.0, 1)),
                              severity=2 if abs(peak) >= 20 else 1, label=SUBTYPE_KO[sub]))
    log(f"hazards: relief {len(items)} (dropped {dropped} objects/edges), cell {cell_mm:.1f} mm, threshold {p['relief_thr_mm']:.0f} mm")
    return items


# ── 변형 ─────────────────────────────────────────────────────────────────────
def deformation(hm, grid, gsd, surface):
    if hm.get("kind") == "relief" and hm.get("fit"):
        f = hm["fit"]
        return [dict(type="deformation", subtype="tilt", geom=None, bbox=None,
                     metrics=dict(lean_deg=f["lean_deg"], flatness_rms_mm=f["flatness_rms_mm"]),
                     severity=1 if abs(f["lean_deg"]) >= 1.0 else 0, label="벽 기울기·평탄도",
                     note="기울기는 ARKit 중력 방향 기준(약 ±0.5° 오차 추정). 위가 카메라 쪽으로 기울면 +")]
    if hm.get("kind") == "height":
        s = int(hm.get("step", 1)); nod = hm.get("nodata", -32768)
        yy, xx = np.nonzero((grid != nod) & (np.abs(grid.astype(np.int32)) < 30))
        if len(yy) < 200:
            return []
        cm = s * gsd
        A = np.c_[xx * cm, yy * cm, np.ones(len(yy))]
        z = grid[yy, xx].astype(np.float64) / 1000.0
        coef = np.linalg.lstsq(A, z, rcond=None)[0]
        res = z - A @ coef
        slope = math.degrees(math.atan(math.hypot(coef[0], coef[1])))
        return [dict(type="deformation", subtype="flatness", geom=None, bbox=None,
                     metrics=dict(slope_deg=round(slope, 3), flatness_rms_mm=round(float(np.sqrt(np.mean(res ** 2)) * 1000), 2)),
                     severity=0, label="바닥 경사·평탄도", note="기준 높이 ±30 mm 안의 바닥면으로 맞춘 평면")]
    return []


# ── 균열 → 공통 형식 ─────────────────────────────────────────────────────────
def crack_items(cdoc):
    out = []
    for c in (cdoc or {}).get("cracks", []):
        parts = [sg["polyline"] for sg in c["segments"] if len(sg["polyline"]) >= 2]
        if not parts:
            continue
        w = c["width_max_mm"]
        out.append(dict(type="crack", subtype=c.get("kind"), geom=dict(type="polyline", parts=parts), bbox=c["bbox"],
                        metrics=dict(length_mm=c["length_mm"], width_max_mm=w, width_median_mm=c["width_median_mm"],
                                     width_source=c["width_source"], orientation_deg=c["orientation_deg"]),
                        segments=[dict(part=i, width_max_mm=sg["width_max_mm"], bin=sg["bin"]) for i, sg in enumerate(c["segments"]) if len(sg["polyline"]) >= 2],
                        severity=3 if w >= 1.0 else 2 if w >= 0.3 else 1, label="균열", src_id=c["id"]))
    return out


def build(meta, img_rgb, covered, on_surface, hm, grid, out_dir, log, cracks_doc=None, markers=None, params=None, exclude=None):
    """정사영상·높이 지도·균열 결과 → hazards.json 저장, 요약 반환. job_id·site_id·captured_at 은 파이프라인이 채운다"""
    t0 = time.time()
    p = dict(DEFAULTS, **(params or {}))
    gsd = float(meta["gsd_m"])
    sf = float((cracks_doc or {}).get("scale_factor_applied") or 1.0)
    valid = covered & on_surface if on_surface is not None else covered.copy()
    if exclude is not None:
        valid &= ~exclude
    items = crack_items(cracks_doc)
    try:
        items += stains(img_rgb, valid, gsd, log, p, sf)
    except Exception as e:
        log(f"hazards: stains skipped: {e}")
    if hm is not None and grid is not None:
        try:
            items += relief(hm, grid, gsd, meta.get("surface", "wall"), log, p, sf, exclude)
            items += deformation(hm, grid, gsd, meta.get("surface", "wall"))
        except Exception as e:
            log(f"hazards: relief skipped: {e}")
    prefix = dict(crack="C", stain="D", relief="S", deformation="G")
    cnt = {}
    for it in items:
        cnt[it["type"]] = cnt.get(it["type"], 0) + 1
        it["id"] = f"{prefix[it['type']]}{cnt[it['type']]}"
    card = (cracks_doc or {}).get("scale_card")
    doc = dict(version=1, job_id=None, site_id=None, captured_at=None, surface=meta.get("surface"),
               frame=dict(type="ortho", gsd_m=gsd, width=meta["width"], height=meta["height"], grid=meta.get("grid"), image="ortho.jpg"),
               scale=dict(factor=sf, source="card" if card else "none", error_pct=card.get("scale_error_pct") if card else None),
               markers=markers or [], items=items,
               summary=dict(counts=cnt, severity_max=max((it.get("severity", 0) for it in items), default=0), seconds=round(time.time() - t0, 1),
                            notes="자동 검출 결과(안내용). 변색은 색만 보므로 물건·그림자가 섞일 수 있고, 요철은 LiDAR 정밀도(약 ±1 cm) 한계가 있음."))
    json.dump(doc, open(os.path.join(out_dir, "hazards.json"), "w", encoding="utf-8"), ensure_ascii=False)
    log(f"hazards: {cnt} -> hazards.json ({doc['summary']['seconds']}s)")
    return dict(counts=cnt, severity_max=doc["summary"]["severity_max"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ortho", required=True); ap.add_argument("--meta", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--overlay"); ap.add_argument("--height-bin"); ap.add_argument("--cracks")
    a = ap.parse_args()
    t0 = time.time()
    log = lambda m: print(f"[{time.time() - t0:6.1f}s] {m}", flush=True)
    os.makedirs(a.out, exist_ok=True)
    meta = json.load(open(a.meta, encoding="utf-8"))
    rgb = cv2.cvtColor(cv2.imdecode(np.fromfile(a.ortho, np.uint8), cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
    if a.overlay and os.path.exists(a.overlay):
        al = cv2.imdecode(np.fromfile(a.overlay, np.uint8), cv2.IMREAD_UNCHANGED)[..., 3]
        covered = cv2.resize(al, (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_NEAREST) > 128
    else:
        covered = np.abs(rgb.astype(np.int16) - 24).sum(axis=2) > 12
    hm = meta.get("height_map") or (meta.get("height") if isinstance(meta.get("height"), dict) else None)
    grid = on_surface = None
    if hm and a.height_bin and os.path.exists(a.height_bin):
        from crack_analysis import surface_mask_from_height
        raw = np.fromfile(a.height_bin, np.int16)
        grid = raw.reshape(hm["height"], hm["width"])
        on_surface = surface_mask_from_height(hm, raw, rgb.shape[:2], 20.0)
    cd = json.load(open(a.cracks, encoding="utf-8")) if a.cracks and os.path.exists(a.cracks) else None
    print(json.dumps(build(meta, rgb, covered, on_surface, hm, grid, a.out, log, cracks_doc=cd)))


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    main()
