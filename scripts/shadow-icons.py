#!/usr/bin/env python3
"""3D 지도용 심볼: PNG 에 부드러운 그림자를 입혀 sym/scene/shadow/ 에 저장한다 (순수 파이썬, 외부 라이브러리 없음).
   입력은 8비트 RGBA·비인터레이스 PNG 여야 한다."""
import os, struct, zlib, sys
SRC = 'public/maps/sym/scene'
DST = os.path.join(SRC, 'shadow')
PAD, OFF_Y, RADIUS, OPACITY = 14, 7, 6, 0.55   # 여백, 그림자 아래 이동(px), 흐림 반경, 그림자 진하기

def read_png(path):
    b = open(path, 'rb').read(); assert b[:8] == b'\x89PNG\r\n\x1a\n', path
    pos, idat, ihdr = 8, b'', None
    while pos < len(b):
        ln, = struct.unpack('>I', b[pos:pos+4]); typ = b[pos+4:pos+8]; dat = b[pos+8:pos+8+ln]; pos += 12 + ln
        if typ == b'IHDR': ihdr = struct.unpack('>IIBBBBB', dat)
        elif typ == b'IDAT': idat += dat
    w, h, bd, ct, _, _, il = ihdr; assert bd == 8 and ct == 6 and il == 0, ('지원하지 않는 PNG', path, ihdr)
    raw = zlib.decompress(idat); bpp, stride = 4, w * 4
    px = bytearray(h * stride); prev = bytearray(stride); p = 0
    for y in range(h):
        f = raw[p]; line = bytearray(raw[p+1:p+1+stride]); p += 1 + stride
        for i in range(stride):
            a = line[i-bpp] if i >= bpp else 0; bb = prev[i]; c = prev[i-bpp] if i >= bpp else 0
            if f == 1: line[i] = (line[i] + a) & 255
            elif f == 2: line[i] = (line[i] + bb) & 255
            elif f == 3: line[i] = (line[i] + ((a + bb) >> 1)) & 255
            elif f == 4:
                pa, pb, pc = abs(bb - c), abs(a - c), abs(a + bb - 2 * c)
                pr = a if pa <= pb and pa <= pc else (bb if pb <= pc else c)
                line[i] = (line[i] + pr) & 255
        px[y*stride:(y+1)*stride] = line; prev = line
    return w, h, px

def write_png(path, w, h, px):
    stride = w * 4; raw = b''.join(b'\x00' + bytes(px[y*stride:(y+1)*stride]) for y in range(h))
    def chunk(t, d): return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    open(path, 'wb').write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))

def box_blur(a, w, h, r):
    """정수 배열 a(w*h) 를 반경 r 로 가로·세로 박스 블러 (두 번 돌리면 가우시안에 가깝다)"""
    out = [0] * (w * h)
    for y in range(h):
        row = a[y*w:(y+1)*w]; acc = sum(row[:r+1]); 
        for x in range(w):
            out[y*w+x] = acc // (2*r+1)
            if x + r + 1 < w: acc += row[x+r+1]
            if x - r >= 0: acc -= row[x-r]
    out2 = [0] * (w * h)
    for x in range(w):
        col = out[x::w]; acc = sum(col[:r+1])
        for y in range(h):
            out2[y*w+x] = acc // (2*r+1)
            if y + r + 1 < h: acc += col[y+r+1]
            if y - r >= 0: acc -= col[y-r]
    return out2

def shadowed(w, h, px, PAD=PAD, OFF_Y=OFF_Y, RADIUS=RADIUS, OPACITY=OPACITY):
    W, H = w + PAD*2, h + PAD*2 + OFF_Y
    alpha = [0] * (W * H)
    for y in range(h):
        for x in range(w):
            alpha[(y+PAD+OFF_Y)*W + (x+PAD)] = px[(y*w+x)*4+3]
    sh = box_blur(box_blur(alpha, W, H, RADIUS), W, H, RADIUS)
    out = bytearray(W * H * 4)
    for i in range(W * H):
        a = int(sh[i] * OPACITY)
        if a: out[i*4:i*4+4] = bytes((20, 30, 26, min(255, a)))
    # 아이콘을 그림자 위에 합성 (일반 알파 합성)
    for y in range(h):
        for x in range(w):
            si = ((y+PAD)*W + (x+PAD)) * 4; di = (y*w+x)*4
            sa = px[di+3] / 255.0
            if sa == 0: continue
            da = out[si+3] / 255.0; oa = sa + da * (1 - sa)
            for c in range(3):
                out[si+c] = int((px[di+c]*sa + out[si+c]*da*(1-sa)) / oa) if oa else 0
            out[si+3] = int(oa * 255)
    return W, H, out

if __name__ == '__main__':
    os.makedirs(DST, exist_ok=True); n = 0
    for f in sorted(os.listdir(SRC)):
        if not f.endswith('.png') or f == 'pin.png': continue
        w, h, px = read_png(os.path.join(SRC, f)); W, H, out = shadowed(w, h, px)
        write_png(os.path.join(DST, f), W, H, out); n += 1
    print(f'shadow icons: {n} → {DST} ({W}x{H})')
