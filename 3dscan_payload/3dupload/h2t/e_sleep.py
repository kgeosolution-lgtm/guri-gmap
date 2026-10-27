"""HTTP/2 POST 진단용 (임시, 변형 e_sleep.py): 본문을 다 읽고 바이트 수와 sha256 을 돌려준다. h2t/web.config 는 createCGIWithNewConsole=false."""
import hashlib
import time
import json
import os
import sys

time.sleep(0.6)
n = int(os.environ.get("CONTENT_LENGTH") or 0)
data = sys.stdin.buffer.read(n) if n > 0 else b""
body = json.dumps({"ok": True, "method": os.environ.get("REQUEST_METHOD"), "content_length": n, "read": len(data),
                   "sha256": hashlib.sha256(data).hexdigest()[:16]}).encode()
out = sys.stdout.buffer
out.write(b"Status: 200 OK\r\nContent-Type: application/json\r\nCache-Control: no-store\r\n")
out.write(f"Content-Length: {len(body)}\r\n\r\n".encode())
out.write(body)
out.flush()
