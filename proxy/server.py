import json
import os
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("PORT", "10000"))
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "https://galbbb2772.github.io")
UPSTREAM = "https://api.tiingo.com"
MAX_BYTES = 12 * 1024 * 1024

ALLOWED_PREFIXES = (
    "/tiingo/daily/",
    "/tiingo/fundamentals/",
)


def cors_origin(origin: str) -> str:
    return ALLOWED_ORIGIN if origin == ALLOWED_ORIGIN else ""


class Handler(BaseHTTPRequestHandler):
    server_version = "MRTTiingoProxy/1.0"

    def log_message(self, fmt, *args):
        # Never include request headers/tokens in logs.
        super().log_message(fmt, *args)

    def _common_headers(self, status=200, content_type="application/json"):
        origin = cors_origin(self.headers.get("Origin", ""))
        self.send_response(status)
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "X-Tiingo-Token, Content-Type")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Type", content_type)

    def do_OPTIONS(self):
        self._common_headers(204, "text/plain; charset=utf-8")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path == "/health":
            body = b'{"ok":true,"service":"mrt-tiingo-proxy"}'
            self._common_headers(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if not parsed.path.startswith(ALLOWED_PREFIXES):
            self._json_error(404, "unsupported path")
            return

        token = (self.headers.get("X-Tiingo-Token") or "").strip()
        if not token or len(token) > 300:
            self._json_error(401, "missing Tiingo token")
            return

        # Strip the local /tiingo prefix and never forward a token query parameter.
        upstream_path = parsed.path[len("/tiingo"):]
        q = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        q = [(k, v) for k, v in q if k.lower() != "token"]
        upstream_url = UPSTREAM + upstream_path
        if q:
            upstream_url += "?" + urllib.parse.urlencode(q)

        req = urllib.request.Request(
            upstream_url,
            headers={
                "Authorization": f"Token {token}",
                "Accept": "application/json",
                "User-Agent": "MarketResearchTerminal/1.0",
            },
            method="GET",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read(MAX_BYTES + 1)
                if len(data) > MAX_BYTES:
                    self._json_error(502, "upstream response too large")
                    return
                ctype = resp.headers.get("Content-Type", "application/json")
                self._common_headers(resp.status, ctype)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.HTTPError as e:
            try:
                data = e.read(MAX_BYTES)
            except Exception:
                data = b""
            if not data:
                data = json.dumps({"error": f"Tiingo HTTP {e.code}"}).encode()
            self._common_headers(e.code, e.headers.get("Content-Type", "application/json"))
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self._json_error(502, "upstream request failed")

    def _json_error(self, status, message):
        data = json.dumps({"error": message}).encode()
        self._common_headers(status)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"MRT Tiingo proxy listening on :{PORT}")
    server.serve_forever()
