"""우리동네 찾기 '치안안심' 그룹의 새 심볼(72×72, 색 원 + 흰 그림): 기존 safety_* 심볼과 같은 결.
   python3 scripts/safety-icons.py <출력폴더>  → safety_bell·parcel·police·lamp·patrol·mirror·default.png (theme.html SYM 에 base64 로 넣는다)"""
import os, sys, math, importlib.util
HERE=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location('shadow', os.path.join(HERE,'shadow-icons.py')); sh=importlib.util.module_from_spec(spec); spec.loader.exec_module(sh)
S=72; SS=4; R=35.0; C=36.0
def seg(px,py,ax,ay,bx,by,w):
    vx,vy=bx-ax,by-ay; L=vx*vx+vy*vy; t=0 if L==0 else max(0,min(1,((px-ax)*vx+(py-ay)*vy)/L)); return math.hypot(px-(ax+vx*t),py-(ay+vy*t))<=w/2
def poly(px,py,pts):
    inside=False; n=len(pts)
    for i in range(n):
        x1,y1=pts[i]; x2,y2=pts[(i+1)%n]
        if (y1>py)!=(y2>py) and px<(x2-x1)*(py-y1)/(y2-y1+1e-9)+x1: inside=not inside
    return inside
def circ(px,py,cx,cy,r): return math.hypot(px-cx,py-cy)<=r
def rrect(px,py,x0,y0,x1,y1,r):
    if px<x0 or px>x1 or py<y0 or py>y1: return False
    cx=min(max(px,x0+r),x1-r); cy=min(max(py,y0+r),y1-r); return math.hypot(px-cx,py-cy)<=r
def star(cx,cy,ro,ri,n=5,rot=-math.pi/2):
    pts=[]
    for i in range(2*n):
        a=rot+i*math.pi/n; r=ro if i%2==0 else ri; pts.append((cx+r*math.cos(a),cy+r*math.sin(a)))
    return pts
ICONS={
 'safety_bell':('#E8464A', lambda x,y: (poly(x,y,[(22,46),(26,42),(26,32),(36,21),(46,32),(46,42),(50,46)]) and not (seg(x,y,27,40,45,40,0) )) or circ(x,y,36,21,4) or rrect(x,y,31,48,41,53,2.5) or seg(x,y,36,15,36,20,3) or seg(x,y,16,22,20,25,2.4) or seg(x,y,56,22,52,25,2.4) or seg(x,y,13,30,18,30,2.4) or seg(x,y,59,30,54,30,2.4)),
 'safety_parcel':('#C75A24', lambda x,y: (rrect(x,y,18,26,54,54,3) and not (seg(x,y,36,26,36,54,2.2) or seg(x,y,18,38,54,38,2.2))) or poly(x,y,[(18,26),(24,17),(48,17),(54,26)]) and not seg(x,y,36,17,36,26,2.2)),
 'safety_police':('#2A6DB0', lambda x,y: (poly(x,y,[(36,14),(54,20),(54,34),(50,46),(36,56),(22,46),(18,34),(18,20)]) and not circ(x,y,36,34,12.5)) or poly(x,y,star(36,34,9.5,4.2))),
 'safety_lamp':('#F0A02C', lambda x,y: seg(x,y,38,30,38,56,3.6) or seg(x,y,30,57,46,57,3.6) or poly(x,y,[(24,16),(44,16),(50,28),(18,28)]) or circ(x,y,34,33,4.5) or seg(x,y,22,36,26,40,2.4) or seg(x,y,46,36,42,40,2.4) or seg(x,y,34,42,34,47,2.4)),
 'safety_patrol':('#8B5E34', lambda x,y: circ(x,y,36,17,5) or seg(x,y,36,22,36,38,5) or seg(x,y,36,38,29,54,4.5) or seg(x,y,36,38,43,54,4.5) or seg(x,y,36,27,25,34,4) or seg(x,y,36,27,47,36,4) or circ(x,y,49,38,6) and not circ(x,y,49,38,2.6)),
 'safety_mirror':('#5B6C7E', lambda x,y: (circ(x,y,36,30,15) and not circ(x,y,36,30,10.5)) or circ(x,y,36,30,6) or seg(x,y,36,45,36,58,4) or seg(x,y,29,58,43,58,4)),
 'safety_default':('#D3422C', lambda x,y: poly(x,y,[(36,13),(53,19),(53,31),(48,44),(36,54),(24,44),(19,31),(19,19)]) and not poly(x,y,[(36,18),(49,22.5),(49,31),(45,41),(36,49),(27,41),(23,31),(23,22.5)]) or seg(x,y,29,33,34,38,3.4) or seg(x,y,34,38,44,27,3.4)),
}
def hex_rgb(h): h=h.lstrip('#'); return tuple(int(h[i:i+2],16) for i in (0,2,4))
def render(color,glyph):
    fill=hex_rgb(color); out=bytearray(S*S*4)
    for y in range(S):
        for x in range(S):
            c_o=c_g=0
            for sy in range(SS):
                for sx in range(SS):
                    px=x+(sx+.5)/SS; py=y+(sy+.5)/SS
                    if circ(px,py,C,C,R):
                        c_o+=1
                        if glyph(px,py): c_g+=1
            if not c_o: continue
            a=c_o/(SS*SS); g=c_g/c_o
            i=(y*S+x)*4; out[i:i+4]=bytes(tuple(int(fill[k]*(1-g)+255*g) for k in range(3))+(int(a*255),))
    return out
if __name__=='__main__':
    out=sys.argv[1]; os.makedirs(out,exist_ok=True)
    for k,(color,glyph) in ICONS.items():
        sh.write_png(os.path.join(out,k+'.png'),S,S,render(color,glyph)); print(k,color)
