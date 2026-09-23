#!/usr/bin/env python3
"""Servidor local para testar o pacote Web: python serve.py [porta] (0 = porta livre)"""
import functools
import http.server
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".wasm": "application/wasm",
        ".js": "text/javascript",
        ".data": "application/octet-stream",
        ".range": "application/octet-stream",
    }

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080  # 0 escolhe uma porta livre
handler = functools.partial(Handler, directory=ROOT)
server = http.server.ThreadingHTTPServer(("", port), handler)
print(f"Servindo em http://localhost:{server.server_address[1]}/  (Ctrl+C para parar)", flush=True)
server.serve_forever()
