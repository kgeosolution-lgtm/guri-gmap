"""우리동네 찾기 '시즌·겨울' 심볼(72×72, 색 원 + 흰 그림): safety-icons.py 의 도형 도구를 그대로 써서 같은 결로 그린다.
   python3 scripts/winter-icons.py <출력폴더>  → winter_shelter·saltbox·icyroad·icyroad_p.png (public/maps/sym/theme/ 에 넣고 theme.html SYM_FILES 에 키 추가)"""
import os, sys, math, importlib.util
HERE=os.path.dirname(os.path.abspath(__file__))
def load(name):
    spec=importlib.util.spec_from_file_location(name.replace('-','_'), os.path.join(HERE,name+'.py')); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
sh=load('shadow-icons'); sf=load('safety-icons')
seg,poly,circ,rrect=sf.seg,sf.poly,sf.circ,sf.rrect
def flake(x,y,cx,cy,r,w):
    """눈송이: 세 축 + 끝 가지"""
    for i in range(3):
        a=math.pi/2+i*math.pi/3; dx,dy=math.cos(a),math.sin(a)
        if seg(x,y,cx-dx*r,cy-dy*r,cx+dx*r,cy+dy*r,w): return True
        for s in (1,-1):                                    # 양 끝의 가지
            ex,ey=cx+dx*r*s,cy+dy*r*s; bx,by=cx+dx*r*0.55*s,cy+dy*r*0.55*s
            for t in (1,-1):
                px,py=-dy*t,dx*t
                if seg(x,y,bx,by,bx+px*r*0.3+dx*r*0.12*s,by+py*r*0.3+dy*r*0.12*s,w*0.85): return True
    return circ(x,y,cx,cy,w*0.9)
ICONS={
 # 한파쉼터: 집 + 문, 지붕 위 작은 굴뚝 — 추위를 피해 들어가는 곳
 'winter_shelter':('#2F6FE4', lambda x,y: (poly(x,y,[(36,15),(56,33),(16,33)]) or rrect(x,y,21,33,51,56,2)) and not rrect(x,y,31,40,41,56,1.5) or rrect(x,y,44,18,49,28,1)),
 # 제설함: 뚜껑 열린 상자 + 안의 삽 자루
 'winter_saltbox':('#E8940F', lambda x,y: (rrect(x,y,18,32,54,56,3) and not rrect(x,y,22,36,50,52,2)) or rrect(x,y,15,26,57,33,2.5) or seg(x,y,36,52,36,38,3.6) or seg(x,y,30,40,42,40,3.2) or circ(x,y,30,46,2.6) or circ(x,y,41,47,2.6) or circ(x,y,36,44,2.2)),
 # 결빙취약구간: 눈송이
 'winter_icyroad':('#2A8FBD', lambda x,y: flake(x,y,36,36,20,3.4)),
 # 시종점: 깃발
 'winter_icyroad_p':('#5B6C7E', lambda x,y: seg(x,y,25,16,25,57,3.6) or poly(x,y,[(27,17),(52,24),(27,33)]) or seg(x,y,19,57,31,57,3.4)),
}
if __name__=='__main__':
    out=sys.argv[1]; os.makedirs(out,exist_ok=True)
    for k,(color,glyph) in ICONS.items():
        sh.write_png(os.path.join(out,k+'.png'),sf.S,sf.S,sf.render(color,glyph)); print(k,color)
