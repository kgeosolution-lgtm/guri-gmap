"""
GLB → OBJ(+MTL+JPEG)  for arcpy Import 3D Files

  python -I glb_to_obj.py --glb mesh_tex.glb --out <dir> [--heading 0] [--jpeg-quality 85]

  - 출력: <dir>\model.obj, model.mtl, texture.jpg
  - heading(도, 북 0°, 시계 방향)만큼 y(위) 축 기준으로 회전한다. 워커가 LAS 에 쓴 것과 같은 식:
        x' = x cosθ - z sinθ ,  z' = x sinθ + z cosθ   (y 그대로)
    → Import 3D Files 의 Y_IS_UP 으로 들어가면 X=x', Y=-z', Z=y 가 되어 LAS 와 같은 방향이 된다.
  - 좌표는 로컬(미터)로 둔다. 배치는 arcpy 쪽에서 포인트 피처(LAS 범위 중심)로 한다.
"""
import argparse
import math
import os

import numpy as np
import trimesh
from PIL import Image


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--heading", type=float, default=0.0)
    ap.add_argument("--jpeg-quality", type=int, default=85)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    m = trimesh.load(args.glb, force="mesh", process=False)
    V = np.asarray(m.vertices, dtype=np.float64)
    th = math.radians(args.heading)
    x, y, z = V[:, 0], V[:, 1], V[:, 2]
    Vr = np.stack([x * math.cos(th) - z * math.sin(th), y, x * math.sin(th) + z * math.cos(th)], axis=1)
    F = np.asarray(m.faces)
    uv = np.asarray(m.visual.uv) if hasattr(m.visual, "uv") and m.visual.uv is not None else None
    tex = getattr(getattr(m.visual, "material", None), "baseColorTexture", None)

    tex_name = None
    if tex is not None:
        tex_name = "texture.jpg"
        img = tex if isinstance(tex, Image.Image) else Image.open(tex)
        img.convert("RGB").save(os.path.join(args.out, tex_name), "JPEG", quality=args.jpeg_quality)

    with open(os.path.join(args.out, "model.mtl"), "w", encoding="ascii") as f:
        f.write("newmtl scan\nKa 1 1 1\nKd 1 1 1\nKs 0 0 0\nd 1\nillum 1\n")
        if tex_name:
            f.write(f"map_Kd {tex_name}\n")

    with open(os.path.join(args.out, "model.obj"), "w", encoding="ascii") as f:
        f.write("mtllib model.mtl\nusemtl scan\n")
        f.write("".join(f"v {a:.5f} {b:.5f} {c:.5f}\n" for a, b, c in Vr))
        if uv is not None:
            f.write("".join(f"vt {u:.6f} {v:.6f}\n" for u, v in uv))
            f.write("".join(f"f {a+1}/{a+1} {b+1}/{b+1} {c+1}/{c+1}\n" for a, b, c in F))
        else:
            f.write("".join(f"f {a+1} {b+1} {c+1}\n" for a, b, c in F))

    lo, hi = Vr.min(axis=0), Vr.max(axis=0)
    print(f"obj: {len(Vr)} verts, {len(F)} faces, texture={tex_name}, local bbox x[{lo[0]:.2f},{hi[0]:.2f}] "
          f"y[{lo[1]:.2f},{hi[1]:.2f}] z[{lo[2]:.2f},{hi[2]:.2f}], heading {args.heading}")


if __name__ == "__main__":
    main()
