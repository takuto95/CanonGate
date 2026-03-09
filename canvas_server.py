import http.server
import socketserver
import threading
import os
from pathlib import Path

def start_canvas_server(port, directory):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(directory), **kwargs)

    def run_server():
        try:
            with socketserver.TCPServer(("", port), Handler) as httpd:
                print(f"[INFO] LiveCanvas server running on port {port} (DIR: {directory})")
                httpd.serve_forever()
        except Exception as e:
            print(f"[ERROR] LiveCanvas server failed: {e}")

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    return server_thread
