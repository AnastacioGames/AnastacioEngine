"""Testes do servidor local do botao 'Abrir no navegador'. Sem bpy, sem navegador."""

import os
import sys
import tempfile
import time
import unittest
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "source", "release", "scripts", "modules"))

from range_web import local_server  # noqa: E402


def make_package(tmp):
    for name, data in (("index.html", b"<html>ok</html>"), ("a.wasm", b"\0asm"), ("manifest.json", b"{}")):
        with open(os.path.join(tmp, name), "wb") as f:
            f.write(data)


class LocalServerTest(unittest.TestCase):
    def tearDown(self):
        local_server.stop()

    def test_serves_with_wasm_mime_and_no_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_package(tmp)
            url = local_server.start(tmp)
            self.assertRegex(url, r"^http://localhost:\d+/$")
            with urllib.request.urlopen(url) as r:
                self.assertEqual(r.status, 200)
                self.assertEqual(r.headers["Cache-Control"], "no-store")
            with urllib.request.urlopen(url + "a.wasm") as r:
                self.assertEqual(r.headers["Content-Type"], "application/wasm")

    def test_same_dir_reuses_and_stop_frees(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_package(tmp)
            self.assertEqual(local_server.start(tmp), local_server.start(tmp))
            self.assertTrue(local_server.stop())
            self.assertIsNone(local_server.url())
            self.assertFalse(local_server.stop())

    def test_package_problem(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIn("Exportar Web", local_server.package_problem(tmp))
            make_package(tmp)
            self.assertIsNone(local_server.package_problem(tmp))
            src = os.path.join(tmp, "jogo.range")
            open(src, "w").close()
            future = time.time() + 100
            os.utime(src, (future, future))
            self.assertIn("desatualizado", local_server.package_problem(tmp, src))


if __name__ == "__main__":
    unittest.main()
