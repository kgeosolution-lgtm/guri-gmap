"""HTTP/2 POST 진단용 (임시): 본문을 다 읽고 받은 바이트 수를 JSON 으로 돌려준다. 3dupload 기본 설정(createCGIWithNewConsole=true)으로 실행."""
import json
import os
import sys

n = int(os.environ.get("CONTENT_LENGTH") or 0)
got = len(sys.stdin.buffer.read(n)) if n > 0 else 0
body = json.dumps({"ok": True, "method": os.environ.get("REQUEST_METHOD"), "content_length": n, "read": got,
                   "protocol": os.environ.get("SERVER_PROTOCOL"), "http2": os.environ.get("HTTP2")}).encode()
out = sys.stdout.buffer
out.write(b"Status: 200 OK\r\nContent-Type: application/json\r\nCache-Control: no-store\r\n")
out.write(f"Content-Length: {len(body)}\r\n\r\n".encode())
out.write(body)
out.flush()
