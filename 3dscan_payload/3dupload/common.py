"""Shared helpers for the kgeoScan upload CGI scripts (IIS, Python CGI)."""
import json
import os
import sys

CONFIG_PATH = os.environ.get("KGEOSCAN_CONFIG", r"D:\kgeoHub\config\kgeoscan.json")


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def respond(obj, status="200 OK"):
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    out = sys.stdout.buffer
    out.write(f"Status: {status}\r\n".encode("ascii"))
    out.write(b"Content-Type: application/json; charset=utf-8\r\n")
    out.write(b"Cache-Control: no-store\r\n")
    out.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii"))
    out.write(body)
    out.flush()


def query_params():
    from urllib.parse import parse_qs
    return {k: v[0] for k, v in parse_qs(os.environ.get("QUERY_STRING", "")).items()}


def safe_job_id(value):
    value = (value or "").strip()
    if len(value) != 8 or any(c not in "0123456789abcdef" for c in value):
        return None
    return value
