"""GET /app/3dupload/check_title.py?title=... -> {"exists": true|false}  (scan_points 공개 조회, 토큰 불필요)"""
import json
import os
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_config, query_params, respond  # noqa: E402


def main():
    title = (query_params().get("title") or "").strip()
    if not title:
        return respond({"exists": False})
    cfg = load_config()
    where = "scan_title = '" + title.replace("'", "''") + "'"
    q = urllib.parse.urlencode({"where": where, "returnCountOnly": "true", "f": "json"})
    with urllib.request.urlopen(cfg["points_layer_url"] + "/query?" + q, timeout=15) as r:
        data = json.loads(r.read().decode("utf-8"))
    respond({"exists": int(data.get("count", 0)) > 0})


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        respond({"exists": False, "error": f"확인 실패: {e}"})
