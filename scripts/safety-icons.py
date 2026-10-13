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
 'safety_toilet':('#7A5FD0', lambda x,y: rrect(x,y,19,16,53,24,2.5) or seg(x,y,26,24,26,56,3.2) or seg(x,y,46,24,46,56,3.2) or poly(x,y,[(28,30),(44,30),(44,42),(36,48),(28,42)]) and not poly(x,y,[(31,33),(41,33),(41,41),(36,45),(31,41)]) or seg(x,y,33,38,36,41,2.6) or seg(x,y,36,41,40,35,2.6)),
 'safety_projector':('#5B6C7E', lambda x,y: rrect(x,y,18,20,46,38,4) or circ(x,y,38,29,6) and not circ(x,y,38,29,3) or seg(x,y,46,29,58,24,3) or seg(x,y,46,29,58,34,3) or seg(x,y,26,38,22,50,3.2) or seg(x,y,38,38,42,50,3.2) or seg(x,y,20,52,46,52,3.2)),
 'safety_sign':('#2F6FE4', lambda x,y: rrect(x,y,16,15,56,40,4) and not rrect(x,y,20,19,52,36,2.5) or seg(x,y,36,40,36,58,3.4) or seg(x,y,28,58,44,58,3.4) or seg(x,y,25,24,47,24,2.8) or seg(x,y,25,31,41,31,2.8)),
 'safety_firstaid':('#E5533C', lambda x,y: rrect(x,y,16,22,56,52,5) and not (seg(x,y,36,29,36,45,6) or seg(x,y,28,37,44,37,6)) or rrect(x,y,29,15,43,24,2.5) and not rrect(x,y,32,18,40,24,1)),
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
def recolor(src_png, color):
    """기존 심볼 PNG(색 원 + 흰 그림)의 원 색만 바꾼다: 흰 정도(m)와 알파는 그대로, 바탕색만 교체"""
    w,h,px=sh.read_png(src_png); fill=hex_rgb(color); out=bytearray(w*h*4)
    for i in range(w*h):
        r,g,b,a=px[i*4:i*4+4]
        if not a: continue
        m=max(0.0,min(1.0,(min(r,g,b)-60)/(255.0-60)))   # 흰 그림 정도(원 색은 채도가 높아 min 채널이 낮다)
        out[i*4:i*4+4]=bytes(tuple(int(fill[k]*(1-m)+255*m) for k in range(3))+(a,))
    return w,h,out
CCTV_VARIANTS={'safety_cctv_bell':'#E8464A','safety_cctv_parking':'#F0A02C','safety_cctv_disaster':'#0F8A8A','safety_cctv_plain':'#6C8296'}   # 방범용은 원래 파란 safety_cctv 그대로
def cctv_source(out_dir):
    """theme.html SYM 의 safety_cctv 를 PNG 로 꺼낸다"""
    import re,base64
    t=open(os.path.join(HERE,'..','public','maps','theme.html'),encoding='utf-8').read()
    m=re.search(r'"safety_cctv": "data:image/png;base64,([^"]+)"',t); p=os.path.join(out_dir,'safety_cctv.png')
    open(p,'wb').write(base64.b64decode(m.group(1))); return p
if __name__=='__main__':
    out=sys.argv[1]; os.makedirs(out,exist_ok=True)
    for k,(color,glyph) in ICONS.items():
        sh.write_png(os.path.join(out,k+'.png'),S,S,render(color,glyph)); print(k,color)
    src=cctv_source(out)
    for k,color in CCTV_VARIANTS.items():
        w,h,px=recolor(src,color); sh.write_png(os.path.join(out,k+'.png'),w,h,px); print(k,color,'(CCTV 색 변형)')
