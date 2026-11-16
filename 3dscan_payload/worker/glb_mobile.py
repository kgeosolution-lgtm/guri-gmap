r"""폰용 가벼운 GLB 만들기 (2026-11-16 기술 점검: 기록 하나 열 때 GLB 9.6 MB, 텍스처 4096² 는 폰 GPU 메모리 64 MB+)

    python -I glb_mobile.py <원본.glb> [<출력_m.glb>] [--tex 2048] [--quality 82]

바꾸는 것 (새 패키지 없이: numpy·Pillow 만)
  - 텍스처: 긴 변을 2048 로 줄여 JPEG 82 로 다시 저장 (투명이 있으면 PNG)
  - 위치: float32 → int16 정수 + 노드 축척·이동 (KHR_mesh_quantization). 정규화하지 않는다:
    사이트의 three.js r128 은 정규화 정수를 CPU(거리 재기·경계 상자)에서 되돌리지 않아 값이 틀어진다.
    정수 + 노드 변환이면 세계 좌표가 맞다. 한 칸 = 모델 크기/65000 (방 10 m 면 0.15 mm)
  - UV: float → uint16 정규화 (0~1 일 때만)
  - 법선: 텍스처가 있는 재질은 사이트가 조명 없이 그리므로 뺀다. 그 밖은 int8 정규화
  - 색(COLOR_0): float 이면 uint8 정규화
  - 인덱스: 0,1,2,… 그대로면 뺀다(삼각형마다 꼭짓점이 따로인 메시). 아니면 가능한 작은 형식
지원하지 않는 구조(스킨·모프·희소 접근자·노드 변환이 이미 있는 메시)면 만들지 않고 None 을 돌려준다 (원본만 쓰게)
"""
import io
import json
import os
import struct
import sys

import numpy as np

CT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}


def _read_glb(path):
    with open(path, "rb") as f:
        b = f.read()
    if b[:4] != b"glTF":
        raise ValueError("GLB 가 아님")
    jlen = struct.unpack("<I", b[12:16])[0]
    j = json.loads(b[20:20 + jlen].decode("utf-8"))
    off = 20 + jlen
    bin_ = b""
    if off + 8 <= len(b):
        blen, btype = struct.unpack("<II", b[off:off + 8])
        if btype == 0x004E4942:
            bin_ = b[off + 8:off + 8 + blen]
    return j, bin_


def _accessor(j, bin_, i):
    a = j["accessors"][i]
    if "sparse" in a:
        raise ValueError("sparse accessor")
    bv = j["bufferViews"][a["bufferView"]]
    dt = np.dtype(CT[a["componentType"]])
    n, c = a["count"], NC[a["type"]]
    start = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    stride = bv.get("byteStride") or dt.itemsize * c
    raw = np.frombuffer(bin_, dtype=np.uint8, count=stride * (n - 1) + dt.itemsize * c, offset=start)
    if stride == dt.itemsize * c:
        arr = raw.view(dt).reshape(n, c)
    else:
        arr = np.lib.stride_tricks.as_strided(raw, shape=(n, dt.itemsize * c), strides=(stride, 1)).copy().view(dt).reshape(n, c)
    if a.get("normalized"):
        arr = arr.astype(np.float32) / float(np.iinfo(dt).max)
    return arr.copy()


def _image_bytes(j, bin_, img):
    bv = j["bufferViews"][img["bufferView"]]
    s = bv.get("byteOffset", 0)
    return bin_[s:s + bv["byteLength"]]


def make_mobile(src, dst=None, tex=2048, quality=82, log=print):
    from PIL import Image
    dst = dst or (src[:-4] + "_m.glb")
    j, bin_ = _read_glb(src)
    if j.get("skins") or any(m.get("weights") for m in j.get("meshes", [])) or "uri" in json.dumps(j.get("buffers", [])):
        log("glb_mobile: 지원하지 않는 구조(스킨·모프·외부 버퍼) → 건너뜀")
        return None
    out_bin = bytearray()
    views, accs = [], []

    def add_view(data, target=None, stride=None):
        while len(out_bin) % 4:
            out_bin.append(0)
        v = {"buffer": 0, "byteOffset": len(out_bin), "byteLength": len(data)}
        if target:
            v["target"] = target
        if stride:
            v["byteStride"] = stride
        out_bin.extend(data)
        views.append(v)
        return len(views) - 1

    def add_acc(view, ctype, typ, count, normalized=False, mn=None, mx=None):
        a = {"bufferView": view, "componentType": ctype, "type": typ, "count": int(count)}
        if normalized:
            a["normalized"] = True
        if mn is not None:
            a["min"], a["max"] = [int(x) if ctype != 5126 else float(x) for x in mn], [int(x) if ctype != 5126 else float(x) for x in mx]
        accs.append(a)
        return len(accs) - 1

    textured = set()
    for mi, mat in enumerate(j.get("materials", [])):
        if (mat.get("pbrMetallicRoughness") or {}).get("baseColorTexture") is not None:
            textured.add(mi)

    # 메시마다 위치 범위를 모아 노드 축척·이동을 정한다 (그 메시를 쓰는 노드에 변환이 없어야 한다)
    mesh_q = {}
    for ni, node in enumerate(j.get("nodes", [])):
        if "mesh" in node and any(k in node for k in ("matrix", "translation", "rotation", "scale")):
            log("glb_mobile: 메시 노드에 이미 변환이 있음 → 건너뜀")
            return None
    new_meshes = []
    for mi, mesh in enumerate(j.get("meshes", [])):
        pos_all = [_accessor(j, bin_, p["attributes"]["POSITION"]).astype(np.float64) for p in mesh["primitives"]]
        lo = np.min([p.min(axis=0) for p in pos_all], axis=0)
        hi = np.max([p.max(axis=0) for p in pos_all], axis=0)
        t = (lo + hi) / 2.0
        s = max(float((hi - lo).max()) / 65000.0, 1e-9)
        mesh_q[mi] = (t, s)
        prims = []
        for p, pos in zip(mesh["primitives"], pos_all):
            if p.get("targets") or p.get("mode", 4) != 4:
                log("glb_mobile: 모프·삼각형 아닌 프리미티브 → 건너뜀")
                return None
            attrs = {}
            q = np.clip(np.round((pos - t) / s), -32767, 32767).astype(np.int16)
            q4 = np.zeros((len(q), 4), np.int16)
            q4[:, :3] = q
            attrs["POSITION"] = add_acc(add_view(q4.tobytes(), 34962, 8), 5122, "VEC3", len(q), mn=q.min(axis=0), mx=q.max(axis=0))
            a_ = p["attributes"]
            if "TEXCOORD_0" in a_:
                uv = _accessor(j, bin_, a_["TEXCOORD_0"]).astype(np.float64)
                if uv.min() >= -1e-6 and uv.max() <= 1 + 1e-6:
                    u16 = np.clip(np.round(uv * 65535.0), 0, 65535).astype(np.uint16)
                    attrs["TEXCOORD_0"] = add_acc(add_view(u16.tobytes(), 34962), 5123, "VEC2", len(u16), normalized=True)
                else:
                    attrs["TEXCOORD_0"] = add_acc(add_view(uv.astype(np.float32).tobytes(), 34962), 5126, "VEC2", len(uv))
            if "NORMAL" in a_ and p.get("material") not in textured:
                nrm = _accessor(j, bin_, a_["NORMAL"]).astype(np.float64)
                n8 = np.zeros((len(nrm), 4), np.int8)
                n8[:, :3] = np.clip(np.round(nrm * 127.0), -127, 127)
                attrs["NORMAL"] = add_acc(add_view(n8.tobytes(), 34962, 4), 5120, "VEC3", len(nrm), normalized=True)
            if "COLOR_0" in a_:
                col = _accessor(j, bin_, a_["COLOR_0"])
                typ = "VEC4" if col.shape[1] == 4 else "VEC3"
                c8 = np.clip(np.round(np.asarray(col, np.float64) * (255.0 if col.dtype.kind == "f" else 1.0)), 0, 255).astype(np.uint8)
                if typ == "VEC3":
                    c4 = np.zeros((len(c8), 4), np.uint8); c4[:, :3] = c8
                    attrs["COLOR_0"] = add_acc(add_view(c4.tobytes(), 34962, 4), 5121, "VEC3", len(c8), normalized=True)
                else:
                    attrs["COLOR_0"] = add_acc(add_view(c8.tobytes(), 34962), 5121, "VEC4", len(c8), normalized=True)
            np_ = {"attributes": attrs, "mode": 4}
            if "material" in p:
                np_["material"] = p["material"]
            if "indices" in p:
                idx = _accessor(j, bin_, p["indices"]).reshape(-1).astype(np.int64)
                if not (len(idx) == len(pos) and np.array_equal(idx, np.arange(len(idx)))):   # 0,1,2,… 아니면 남긴다
                    if idx.max() < 65535:
                        np_["indices"] = add_acc(add_view(idx.astype(np.uint16).tobytes(), 34963), 5123, "SCALAR", len(idx))
                    else:
                        np_["indices"] = add_acc(add_view(idx.astype(np.uint32).tobytes(), 34963), 5125, "SCALAR", len(idx))
            prims.append(np_)
        nm = {"primitives": prims}
        if mesh.get("name"):
            nm["name"] = mesh["name"]
        new_meshes.append(nm)

    # 텍스처 줄이기
    new_images = []
    for img in j.get("images", []):
        data = _image_bytes(j, bin_, img)
        im = Image.open(io.BytesIO(data))
        im.load()
        w, h = im.size
        k = min(1.0, tex / float(max(w, h)))
        if k < 1.0:
            im = im.resize((max(1, round(w * k)), max(1, round(h * k))), Image.LANCZOS)
        buf = io.BytesIO()
        alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
        if alpha:
            im.save(buf, format="PNG", optimize=True); mime = "image/png"
        else:
            im.convert("RGB").save(buf, format="JPEG", quality=quality, optimize=True, progressive=False); mime = "image/jpeg"
        new_images.append({"bufferView": add_view(buf.getvalue()), "mimeType": mime})

    nj = {k: v for k, v in j.items() if k not in ("accessors", "bufferViews", "buffers", "meshes", "images")}
    nj["meshes"], nj["accessors"], nj["bufferViews"] = new_meshes, accs, views
    if new_images:
        nj["images"] = new_images
    nodes = [dict(n) for n in j.get("nodes", [])]
    for n in nodes:
        if "mesh" in n:
            t, s = mesh_q[n["mesh"]]
            n["translation"] = [float(x) for x in t]
            n["scale"] = [s, s, s]
    nj["nodes"] = nodes
    for k in ("extensionsUsed", "extensionsRequired"):
        nj[k] = sorted(set(j.get(k, [])) | {"KHR_mesh_quantization"})
    nj.setdefault("asset", {"version": "2.0"})
    nj["asset"]["generator"] = (nj["asset"].get("generator", "") + " +kgeoScan glb_mobile").strip()
    while len(out_bin) % 4:
        out_bin.append(0)
    nj["buffers"] = [{"byteLength": len(out_bin)}]
    js = json.dumps(nj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    js += b" " * ((4 - len(js) % 4) % 4)
    total = 12 + 8 + len(js) + 8 + len(out_bin)
    tmp = dst + ".tmp"
    with open(tmp, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, total))
        f.write(struct.pack("<II", len(js), 0x4E4F534A)); f.write(js)
        f.write(struct.pack("<II", len(out_bin), 0x004E4942)); f.write(out_bin)
    os.replace(tmp, dst)
    log(f"glb_mobile: {os.path.basename(src)} {os.path.getsize(src) / 1e6:.1f} MB -> {os.path.basename(dst)} {os.path.getsize(dst) / 1e6:.1f} MB")
    return dst


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="폰용 가벼운 GLB")
    ap.add_argument("src")
    ap.add_argument("dst", nargs="?")
    ap.add_argument("--tex", type=int, default=2048, help="텍스처 긴 변 최대 픽셀")
    ap.add_argument("--quality", type=int, default=82, help="JPEG 품질")
    a = ap.parse_args()
    sys.exit(0 if make_mobile(a.src, a.dst, a.tex, a.quality) else 1)
