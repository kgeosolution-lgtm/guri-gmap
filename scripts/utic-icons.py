"""교통 공사·통제(UTIC) 원본 심볼(32~39px, 투명 여백 3px)을 다른 심볼과 같은 72×72 캔버스에 꽉 차게 잘라 키운다(양선형 보간).
   python3 scripts/utic-icons.py <원본 폴더> <출력 폴더>  → theme.html SYM 의 utic_* 를 바꿔 넣는다"""
import os, sys, importlib.util
HERE=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location('shadow', os.path.join(HERE,'shadow-icons.py')); sh=importlib.util.module_from_spec(spec); spec.loader.exec_module(sh)
S=72; PAD=1.5   # 다른 심볼처럼 테두리 1~2px 여백만
def bbox(w,h,px,thr=24):
    xs=[x for y in range(h) for x in range(w) if px[(y*w+x)*4+3]>thr]; ys=[y for y in range(h) for x in range(w) if px[(y*w+x)*4+3]>thr]
    return min(xs),min(ys),max(xs)+1,max(ys)+1
def sample(w,h,px,x,y):
    """알파 가중 양선형 보간(투명 픽셀의 색이 번지지 않게)"""
    x=max(0.0,min(w-1.001,x)); y=max(0.0,min(h-1.001,y)); x0,y0=int(x),int(y); fx,fy=x-x0,y-y0
    acc=[0.0]*4
    for (xx,yy,wt) in ((x0,y0,(1-fx)*(1-fy)),(x0+1,y0,fx*(1-fy)),(x0,y0+1,(1-fx)*fy),(x0+1,y0+1,fx*fy)):
        i=(yy*w+xx)*4; a=px[i+3]/255.0*wt; acc[0]+=px[i]*a; acc[1]+=px[i+1]*a; acc[2]+=px[i+2]*a; acc[3]+=a
    if acc[3]<=0: return (0,0,0,0)
    return (int(acc[0]/acc[3]),int(acc[1]/acc[3]),int(acc[2]/acc[3]),int(min(1.0,acc[3])*255))
def fit(src,dst):
    w,h,px=sh.read_png(src); x0,y0,x1,y1=bbox(w,h,px); cw,ch=x1-x0,y1-y0
    sc=(S-2*PAD)/max(cw,ch); ox=(S-cw*sc)/2; oy=(S-ch*sc)/2   # 비율 유지, 가운데
    out=bytearray(S*S*4); SS=3
    for y in range(S):
        for x in range(S):
            r=g=b=a=0
            for sy in range(SS):
                for sx in range(SS):
                    px_=x0+(x+(sx+.5)/SS-ox)/sc-0.5; py_=y0+(y+(sy+.5)/SS-oy)/sc-0.5
                    if px_<x0-0.5 or py_<y0-0.5 or px_>x1-0.5 or py_>y1-0.5: continue
                    rr,gg,bb,aa=sample(w,h,px,px_,py_); r+=rr*aa; g+=gg*aa; b+=bb*aa; a+=aa
            n=SS*SS; i=(y*S+x)*4
            if a: out[i:i+4]=bytes((int(r/a),int(g/a),int(b/a),int(a/n)))
    sh.write_png(dst,S,S,out)
if __name__=='__main__':
    src,dst=sys.argv[1],sys.argv[2]; os.makedirs(dst,exist_ok=True)
    for k in ['utic_accident','utic_work','utic_event','utic_weather','utic_control','utic_disaster','utic_etc']:
        fit(os.path.join(src,k+'.png'),os.path.join(dst,k+'.png')); print(k,'→ 72x72')
