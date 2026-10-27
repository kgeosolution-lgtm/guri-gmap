r"""
배포 때 서버 설정(D:\kgeoHub\config\kgeoscan.json)을 예제 설정에 맞춰 보강한다 (있는 값은 바꾸지 않음).
  python -I config_patch.py <kgeoscan.json> <kgeoscan.example.json>

  - 예제에만 있는 최상위 키(예: "splat")를 추가한다. 예제의 값이 dict 이면 그 안의 빠진 키도 채운다.
  - 환경변수 KGEOSCAN_SPLAT_TOKEN 이 있으면 splat.worker_token 에 넣는다 (GitHub secret → 배포 워크플로).
  - 비밀번호(portal_password)는 건드리지 않는다.
"""
import json
import os
import sys


def merge_missing(dst, src, path=""):
    added = []
    for k, v in src.items():
        if k == "_comment":
            continue
        if k not in dst:
            dst[k] = v
            added.append(path + k)
        elif isinstance(v, dict) and isinstance(dst.get(k), dict):
            added += merge_missing(dst[k], v, path + k + ".")
    return added


def main():
    cfg_path, example_path = sys.argv[1], sys.argv[2]
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    with open(example_path, "r", encoding="utf-8") as f:
        example = json.load(f)
    added = merge_missing(cfg, example)
    notes = []
    tok = os.environ.get("KGEOSCAN_SPLAT_TOKEN", "").strip()
    if tok:
        cfg.setdefault("splat", {})["worker_token"] = tok
        notes.append(f"splat.worker_token set from secret (len {len(tok)})")
    elif str(cfg.get("splat", {}).get("worker_token", "")).startswith("<"):
        notes.append("splat.worker_token STILL PLACEHOLDER (set GitHub secret KGEOSCAN_SPLAT_TOKEN)")
    tmp = cfg_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, cfg_path)
    print("CONFIG PATCH: added " + (", ".join(added) if added else "nothing") + ("; " + "; ".join(notes) if notes else ""))


if __name__ == "__main__":
    main()
