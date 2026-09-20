# Servidor local do pacote Web para o botao "Abrir no navegador". Sem bpy: roda numa thread
# daemon do proprio editor (morre com ele, sem processo orfao) numa porta livre.

import functools
import http.server
import os
import threading

from .i18n import _

_SERVER = None  # (ThreadingHTTPServer, directory)


class _Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".wasm": "application/wasm",
        ".js": "text/javascript",
        ".data": "application/octet-stream",
        ".range": "application/octet-stream",
    }

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *args):
        pass


def package_problem(package_dir, source_file=None):
    """Motivo pelo qual o pacote nao pode ser servido/esta velho, ou None."""
    if not os.path.isfile(os.path.join(package_dir, "index.html")):
        return _("Package not found at %s. Click Export Web first.") % package_dir
    manifest = os.path.join(package_dir, "manifest.json")
    if source_file and os.path.isfile(source_file) and os.path.isfile(manifest) \
            and os.path.getmtime(source_file) > os.path.getmtime(manifest):
        return _("The package is older than the saved .range. Click Export Web first.")
    return None


def start(package_dir):
    """Serve package_dir e devolve a URL. Reusa o servidor se ja serve a mesma pasta."""
    global _SERVER
    package_dir = os.path.abspath(package_dir)
    if _SERVER is not None and _SERVER[1] == package_dir:
        return url()
    stop()
    handler = functools.partial(_Handler, directory=package_dir)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    _SERVER = (server, package_dir)
    return url()


def url():
    if _SERVER is None:
        return None
    return "http://localhost:%d/" % _SERVER[0].server_address[1]


def stop():
    global _SERVER
    if _SERVER is None:
        return False
    server = _SERVER[0]
    _SERVER = None
    server.shutdown()
    server.server_close()
    return True
