#!/usr/bin/env python3
"""
簡易モード用: 静的ファイル配信 + LiveKit トークン発行.
環境変数: LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET（.env.local があれば読み込む）
使い方: python serve.py
        ブラウザで http://localhost:8765/
"""
import os
from pathlib import Path as _Path

# .env.local を同じディレクトリまたは LiveTalkAiAgent 直上で探して読み込む
def _load_dotenv():
    for d in [_Path(__file__).resolve().parent, _Path(__file__).resolve().parent.parent]:
        env = d / ".env.local"
        if env.is_file():
            for line in env.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    k, v = k.strip(), v.strip().strip('"').strip("'")
                    if k and k not in os.environ:
                        os.environ[k] = v
            break
_load_dotenv()
import json
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

try:
    from livekit.api import AccessToken, VideoGrants
except ImportError:
    AccessToken = VideoGrants = None

PORT = int(os.environ.get("SIMPLE_MODE_PORT", "8765"))
ROOM_DEFAULT = os.environ.get("LIVEKIT_ROOM", "simple-mode")
ROOT = Path(__file__).resolve().parent


def make_token(room_name: str):
    url = os.environ.get("LIVEKIT_URL")
    key = os.environ.get("LIVEKIT_API_KEY")
    secret = os.environ.get("LIVEKIT_API_SECRET")
    if not all((url, key, secret)):
        raise ValueError("LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET を設定してください")
    if AccessToken is None:
        raise ValueError("livekit-api をインストールしてください: pip install livekit-api")
    token = AccessToken(key, secret)
    token.with_identity("simple-mode-user").with_name("SimpleMode").with_grants(
        VideoGrants(room_join=True, room=room_name)
    )
    return token.to_jwt(), url


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urllib.parse.unquote(urllib.parse.urlparse(self.path).path)
        if path == "/token":
            self.serve_token(path)
            return
        if path == "/" or path == "":
            path = "/index.html"
        self.serve_static(path.lstrip("/"))

    def serve_token(self, _path):
        try:
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            room = (qs.get("room") or [ROOM_DEFAULT])[0]
            token, url = make_token(room)
            body = json.dumps({"token": token, "url": url}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            body = json.dumps({"error": str(e)}).encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def serve_static(self, name):
        if ".." in name:
            self.send_error(404)
            return
        path = ROOT / name
        if not path.is_file():
            path = ROOT / "index.html"
        if not path.is_file():
            self.send_error(404)
            return
        suffix = path.suffix.lower()
        types = {
            ".html": "text/html; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
        }
        ct = types.get(suffix, "application/octet-stream")
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        print("[serve] " + format % args)


def main():
    if not os.environ.get("LIVEKIT_URL"):
        print("環境変数 LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET を設定してください")
        print("例: .env.local を読み込むか、export で設定")
        return 1
    server = HTTPServer(("", PORT), Handler)
    print("簡易モード UI: http://localhost:%s/" % PORT)
    print("終了: Ctrl+C")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    exit(main() or 0)
