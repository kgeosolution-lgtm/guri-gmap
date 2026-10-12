"""우리동네 찾기 '노포식당' 심볼(72×72): 테라코타 원 + 흰 김 나는 뚝배기. 기존 심볼(와구리맛집 주황 원)과 같은 결."""
import os, sys, math, importlib.util
spec=importlib.util.spec_from_file_location('shadow', os.path.join('scripts','shadow-icons.py')); sh=importlib.util.module_from_spec(spec); spec.loader.exec_module(sh)
S=72; SS=4; FILL=(0xB5,0x45,0x2F); R=35.0; cx=cy=36.0
def seg_d(px,py,ax,ay,bx,by):
    vx,vy=bx-ax,by-ay; L=vx*vx+vy*vy; t=0 if L==0 else max(0,min(1,((px-ax)*vx+(py-ay)*vy)/L)); return math.hypot(px-(ax+vx*t),py-(ay+vy*t))
def steam(px,py,x0):
    pts=[(x0+2.2*math.sin(k/8*math.pi*2),18+k/8*13) for k in range(9)]
    return min(seg_d(px,py,*pts[i],*pts[i+1]) for i in range(8))<1.8
def glyph(px,py):
    # 뚝배기: 아래 반원 + 손잡이 테두리 + 받침
    if math.hypot(px-36,py-39.5)<=15.5 and py>=39.5: return True
    if 36.6<=py<=41.6 and 18.5<=px<=53.5 and (18.5+2.5<=px<=53.5-2.5 or math.hypot(px-(21 if px<36 else 51),py-39.1)<=2.5): return True
    if 55<=py<=58.6 and 27<=px<=45: return True
    return any(steam(px,py,x) for x in (28.5,36,43.5))
out=bytearray(S*S*4)
for y in range(S):
    for x in range(S):
        c_o=c_g=0
        for sy in range(SS):
            for sx in range(SS):
                px=x+(sx+.5)/SS; py=y+(sy+.5)/SS
                if math.hypot(px-cx,py-cy)<=R:
                    c_o+=1
                    if glyph(px,py): c_g+=1
        if not c_o: continue
        a=c_o/(SS*SS); g=c_g/max(c_o,1)
        r,gg,b=[int(FILL[i]*(1-g)+255*g) for i in range(3)]
        i=(y*S+x)*4; out[i:i+4]=bytes((r,gg,b,int(a*255)))
sh.write_png(sys.argv[1],S,S,out); print('written',sys.argv[1])
