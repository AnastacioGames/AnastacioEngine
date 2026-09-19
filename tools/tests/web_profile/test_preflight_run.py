"""Testes do pre-voo automatico (marco E) com um 'navegador' falso. Sem bpy, sem Chrome."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "source", "release", "scripts", "modules"))

from range_web import preflight_run  # noqa: E402

_FAKE = (
    "import json, sys, urllib.request\n"
    "url, payload = sys.argv[1], sys.argv[2]\n"
    "base = url.split('/?')[0]\n"
    "urllib.request.urlopen(base + '/index.html').read()\n"
    "if payload != 'none':\n"
    "    urllib.request.urlopen(urllib.request.Request(base + '/__preflight', data=payload.encode(), method='POST'))\n"
)


def fake_launcher(payload):
    def launch(browser, url, profile_dir):
        return subprocess.Popen([sys.executable, "-c", _FAKE, url, payload])
    return launch


def make_package(d):
    with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as fh:
        fh.write("<html></html>")
    with open(os.path.join(d, "a.wasm"), "wb") as fh:
        fh.write(b"\0asm")


class RunPreflightTests(unittest.TestCase):
    def run_with(self, payload, **kw):
        with tempfile.TemporaryDirectory() as d:
            make_package(d)
            return preflight_run.run_preflight(d, browser="fake", launcher=fake_launcher(payload), **kw)

    def test_clean_report_gives_no_findings(self):
        good = json.dumps({"schema": "range-web-preflight", "schema_version": 1})
        self.assertEqual(self.run_with(good, timeout=20), ([], None))

    def test_report_findings_are_returned(self):
        bad = json.dumps({"schema": "range-web-preflight", "schema_version": 1, "context_lost": True})
        found, note = self.run_with(bad, timeout=20)
        self.assertIsNone(note)
        self.assertEqual([f.rule_id for f in found], ["WEB-DEPLOY-003"])

    def test_unreadable_report_is_not_a_game_error(self):
        found, note = self.run_with("{nao json", timeout=20)
        self.assertIsNone(found)
        self.assertIn("ilegível", note)

    def test_no_report_times_out_with_reason(self):
        found, note = self.run_with("none", timeout=2)
        self.assertIsNone(found)
        self.assertIn("não enviou", note)

    def test_missing_browser_and_index(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIn("index.html", preflight_run.run_preflight(d, browser="x")[1])
            make_package(d)
            old = os.environ.get("RANGE_WEB_BROWSER")
            try:
                os.environ["RANGE_WEB_BROWSER"] = os.path.join(d, "nao-existe")
                real_find = preflight_run.find_browser
                preflight_run.find_browser = lambda: None
                self.assertIn("Nenhum", preflight_run.run_preflight(d)[1])
            finally:
                preflight_run.find_browser = real_find
                if old is None:
                    os.environ.pop("RANGE_WEB_BROWSER", None)
                else:
                    os.environ["RANGE_WEB_BROWSER"] = old

    def test_server_serves_wasm_mime_and_stops(self):
        with tempfile.TemporaryDirectory() as d:
            make_package(d)
            server, _t = preflight_run.serve_package(d)
            try:
                url = "http://127.0.0.1:%d/a.wasm" % server.server_address[1]
                self.assertEqual(urllib.request.urlopen(url).headers["Content-Type"], "application/wasm")
            finally:
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    unittest.main()
