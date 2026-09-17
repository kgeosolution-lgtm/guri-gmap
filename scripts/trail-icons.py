#!/usr/bin/env python3
"""3D 지도용 둘레길·등산로 시설물 심볼: 테마지도의 원형 픽토그램(sym/scene/src/*.png, 72×72)에서 흰 그림만 떼어 내
   코스 색 바탕의 둥근 배지(흰 테두리)로 다시 그리고, 부드러운 그림자를 입혀 sym/scene/trail/ 에 저장한다.
   순수 파이썬(외부 라이브러리 없음). 원본이나 색을 바꾸면 `python3 scripts/trail-icons.py` 로 다시 생성."""
import os, sys, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('shadow_icons', os.path.join(HERE, 'shadow-icons.py'))
shadow = importlib.util.module_from_spec(spec); spec.loader.exec_module(shadow)

SRC = os.path.join(HERE, '..', 'public', 'maps', 'sym', 'scene', 'src')
DST = os.path.join(HERE, '..', 'public', 'maps', 'sym', 'scene', 'trail')
SIZE, SS = 96, 4                     # 배지 한 변(px), 원 테두리 안티앨리어싱 샘플 수
RING, RIM = 5.0, 1.2                 # 흰 테두리 두께, 테두리 바깥의 옅은 외곽선
# 테마지도 COURSE_INFO / COURSE_COLORS 와 같은 색 (둘레길 시설물은 코스 색으로 물들인다)
COURSE = {1: '#6AA84F', 2: '#E07B27', 3: '#4A96B8', 4: '#D96B7B', 5: '#D9538A', 6: '#00A9C0', 7: '#8B5E34', 8: '#E5533C'}
JOBS = [('culture_dulle_fac.png', 'dulle_fac_0.png', '#6C9E3E')] + \
       [('culture_dulle_fac.png', f'dulle_fac_{n}.png', c) for n, c in COURSE.items()] + \
       [('culture_hiking_fac.png', 'hiking_fac.png', '#8A9C50')]

def hex_rgb(h): h = h.lstrip('#'); return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def glyph_mask(w, h, px):
    """원형 픽토그램에서 흰 그림만: 바탕색(가장 흔한 불투명 색)보다 밝은 정도를 0~1 로"""
    from collections import Counter
    cnt = Counter()
    for i in range(w * h):
        r, g, b, a = px[i*4:i*4+4]
        if a > 250 and min(r, g, b) < 200: cnt[(r, g, b)] += 1
    bg = cnt.most_common(1)[0][0]; mn = min(bg)
    m = [0.0] * (w * h)
    for i in range(w * h):
        r, g, b, a = px[i*4:i*4+4]
        if a == 0: continue
        m[i] = max(0.0, min(1.0, (min(r, g, b) - mn) / (255.0 - mn))) * (a / 255.0)
    return m

def sample(m, w, h, x, y):
    """양선형 보간"""
    x = max(0.0, min(w - 1.001, x)); y = max(0.0, min(h - 1.001, y))
    x0, y0 = int(x), int(y); fx, fy = x - x0, y - y0
    a = m[y0*w+x0]; b = m[y0*w+x0+1]; c = m[(y0+1)*w+x0]; d = m[(y0+1)*w+x0+1]
    return (a*(1-fx) + b*fx)*(1-fy) + (c*(1-fx) + d*fx)*fy

def badge(mask, mw, mh, color):
    S = SIZE; cx = cy = S / 2.0; R = S / 2.0 - RIM; fill = hex_rgb(color)
    dark = tuple(int(c * 0.72) for c in fill)         # 배지 아래쪽에 살짝 어두운 그러데이션
    out = bytearray(S * S * 4)
    for y in range(S):
        for x in range(S):
            cov_o = cov_i = 0.0                         # 바깥 원(외곽선 포함)·안쪽 색 원의 덮임 비율
            for sy in range(SS):
                for sx in range(SS):
                    px_ = x + (sx + .5) / SS - cx; py_ = y + (sy + .5) / SS - cy
                    d = (px_*px_ + py_*py_) ** .5
                    if d <= R + RIM: cov_o += 1
                    if d <= R - RING: cov_i += 1
            cov_o /= SS*SS; cov_i /= SS*SS
            if cov_o == 0: continue
            t = y / (S - 1.0)                           # 위→아래 그러데이션
            base = tuple(int(fill[c]*(1-t*.35) + dark[c]*t*.35) for c in range(3))
            ring = (255, 255, 255)
            # 색 원 위에 흰 테두리, 테두리 바깥은 옅은 회색 외곽선
            r, g, b = [int(ring[c]*(1-cov_i) + base[c]*cov_i) for c in range(3)]
            if cov_o < 1: r, g, b = int(r*cov_o + 60*(1-cov_o)), int(g*cov_o + 70*(1-cov_o)), int(b*cov_o + 60*(1-cov_o))
            a = cov_o
            # 그림(흰색) 합성: 원본 72px 을 배지 안쪽에 맞춰 확대
            gx = (x - cx) / (R - RING) * (mw / 2.0) * 1.08 + mw / 2.0
            gy = (y - cy) / (R - RING) * (mh / 2.0) * 1.08 + mh / 2.0
            gm = sample(mask, mw, mh, gx, gy) * cov_i
            r, g, b = int(r*(1-gm) + 255*gm), int(g*(1-gm) + 255*gm), int(b*(1-gm) + 255*gm)
            i = (y*S + x) * 4; out[i:i+4] = bytes((r, g, b, int(a * 255)))
    return S, S, out

if __name__ == '__main__':
    os.makedirs(DST, exist_ok=True); masks = {}
    for src, dst, color in JOBS:
        if src not in masks:
            w, h, px = shadow.read_png(os.path.join(SRC, src)); masks[src] = (glyph_mask(w, h, px), w, h)
        m, mw, mh = masks[src]
        S, _, bpx = badge(m, mw, mh, color)
        W, H, out = shadow.shadowed(S, S, bpx, PAD=10, OFF_Y=5, RADIUS=4, OPACITY=0.5)
        shadow.write_png(os.path.join(DST, dst), W, H, out)
        print(f'{dst}: {W}x{H} {color}')
