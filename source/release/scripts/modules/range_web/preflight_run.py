# Pre-voo automatico (marco E): serve um pacote Web numa porta local, abre um Chrome/Edge sem
# janela e espera a pagina (?preflight=1&post=1) enviar o relatorio por POST /__preflight.
# Nao usa node nem CDP. Fecha so o processo que abriu. Falha de ambiente (sem navegador, sem
# resposta) nao vira erro do jogo: devolve (None, motivo).

import functools
import http.server
import json
import os
import shutil
import subprocess
import tempfile
import threading

from .preflight import check_preflight
from .i18n import _

_BROWSER_NAMES = ("chrome", "google-chrome", "chromium", "chromium-browser", "msedge", "microsoft-edge")
_WINDOWS_BROWSERS = (
    r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
    r"%LocalAppData%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
    r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
)


def find_browser():
    """Caminho de um navegador Chromium, ou None. RANGE_WEB_BROWSER tem precedência."""
    env = os.environ.get("RANGE_WEB_BROWSER")
    if env and os.path.isfile(env):
        return env
    for name in _BROWSER_NAMES:
        found = shutil.which(name)
        if found:
            return found
    for template in _WINDOWS_BROWSERS:
        path = os.path.expandvars(template)
        if os.path.isfile(path):
            return path
    return None


class _Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".wasm": "application/wasm",
        ".js": "text/javascript",
        ".data": "application/octet-stream",
        ".range": "application/octet-stream",
    }
    received = None  # threading.Event + lista, injetados por serve_package

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_POST(self):
        if self.path != "/__preflight":
            self.send_error(404)
            return
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        try:
            self.server.report_box.append(json.loads(body.decode("utf-8")))
        except ValueError:
            self.server.report_box.append(None)
        self.send_response(204)
        self.end_headers()
        self.server.got_report.set()

    def log_message(self, *args):
        pass


def serve_package(directory):
    """Servidor em 127.0.0.1:<porta livre>; devolve (server, thread). Pare com server.shutdown()."""
    handler = functools.partial(_Handler, directory=directory)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server.report_box = []
    server.got_report = threading.Event()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _launch_browser(browser, url, profile_dir):
    cmd = [browser, "--headless=new", "--user-data-dir=" + profile_dir, "--enable-unsafe-swiftshader",
           "--no-first-run", "--no-default-browser-check", "--disable-extensions", url]
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def run_preflight(package_dir, browser=None, timeout=60, delay=12, launcher=_launch_browser):
    """Roda o pre-voo num pacote. Devolve (findings, None) ou (None, motivo se nao rodou).

    `delay` é o tempo, em segundos, que a pagina deixa o jogo rodar antes de reportar.
    `launcher(browser, url, profile_dir)` devolve um Popen; existe para os testes.
    """
    if not os.path.isfile(os.path.join(package_dir, "index.html")):
        return None, "Pasta sem index.html: %s" % package_dir
    browser = browser or find_browser()
    if browser is None:
        return None, "Nenhum Chrome/Edge encontrado (defina RANGE_WEB_BROWSER)."
    server, _thread = serve_package(package_dir)
    proc = None
    try:
        url = "http://127.0.0.1:%d/?preflight=1&post=1&delay=%d" % (server.server_address[1], delay)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as profile:
            try:
                proc = launcher(browser, url, profile)
            except OSError as exc:
                return None, _("Could not open the browser: %s") % exc
            try:
                got = server.got_report.wait(timeout)
            finally:
                proc.terminate()
                try:
                    proc.wait(10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
        if not got:
            return None, _("The browser did not send the report within %d s.") % timeout
        data = server.report_box[0]
        if data is None:
            return None, _("Unreadable preflight report.")
        return check_preflight(data), None
    finally:
        server.shutdown()
        server.server_close()
