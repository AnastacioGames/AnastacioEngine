"""Testes puros da leitura do relatorio de pre-voo (marco E). Sem bpy."""

import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "source", "release", "scripts", "modules"))

from range_web import preflight  # noqa: E402


def report(**kw):
    d = {"schema": preflight.PREFLIGHT_SCHEMA, "schema_version": 1}
    d.update(kw)
    return d


def ids(findings):
    return [f.rule_id for f in findings]


class PreflightTests(unittest.TestCase):
    def test_load_preflight_file(self):
        with tempfile.TemporaryDirectory() as d:
            good = os.path.join(d, "ok.json")
            with open(good, "w", encoding="utf-8") as fh:
                json.dump(report(context_lost=True), fh)
            bad = os.path.join(d, "bad.json")
            with open(bad, "w", encoding="utf-8") as fh:
                fh.write("{nao e json")
            self.assertEqual(ids(preflight.load_preflight(good)), ["WEB-DEPLOY-003"])
            self.assertEqual(ids(preflight.load_preflight(bad)), ["WEB-DEPLOY-002"])
            self.assertEqual(ids(preflight.load_preflight(os.path.join(d, "x.json"))), ["WEB-DEPLOY-002"])

    def test_clean_report_has_no_findings(self):
        data = report(cross_origin_isolated=True, webgl={"version": 2},
                      files=[{"name": "a.wasm", "status": 200, "mime": "application/wasm"}])
        self.assertEqual(preflight.check_preflight(data), [])

    def test_missing_or_bad_schema_is_error(self):
        self.assertEqual(ids(preflight.check_preflight(None)), ["WEB-DEPLOY-002"])
        self.assertEqual(ids(preflight.check_preflight({"schema": "x"})), ["WEB-DEPLOY-002"])
        self.assertEqual(ids(preflight.check_preflight(report(schema_version=9) | {"schema_version": 9})),
                         ["WEB-DEPLOY-002"])

    def test_threads_without_isolation(self):
        mf = {"capabilities": {"threads": {"state": "unvalidated"}}}
        self.assertEqual(ids(preflight.check_preflight(report(cross_origin_isolated=False), mf)),
                         ["WEB-DEPLOY-001"])
        # serial build or unprobed isolation: no finding
        serial = {"capabilities": {"threads": {"state": "disabled"}}}
        self.assertEqual(preflight.check_preflight(report(cross_origin_isolated=False), serial), [])
        self.assertEqual(preflight.check_preflight(report(), mf), [])

    def test_file_failures(self):
        data = report(files=[
            {"name": "g.data", "status": 404},
            {"name": "r.wasm", "status": 200, "mime": "text/html"},
            {"name": "r.js", "status": 200, "expected_sha256": "a", "sha256": "b"},
            {"name": "ok.js", "status": 200, "expected_sha256": "a", "sha256": "a"},
        ])
        found = preflight.check_preflight(data)
        self.assertEqual(ids(found), ["WEB-DEPLOY-002"] * 3)
        self.assertEqual([f.location["source"] for f in found], ["g.data", "r.wasm", "r.js"])

    def test_repeated_python_error_reported_once(self):
        e = {"kind": "ModuleNotFoundError", "module": "m", "file": "", "text": "No module named 'm'"}
        self.assertEqual(ids(preflight.check_preflight(report(python_errors=[e, dict(e), dict(e)]))),
                         ["WEB-PY-001"])

    def test_webgl_and_context(self):
        found = preflight.check_preflight(report(webgl={"version": 0, "error": "blocklisted"}, context_lost=True))
        self.assertEqual(ids(found), ["WEB-GFX-001", "WEB-DEPLOY-003"])
        found = preflight.check_preflight(report(webgl={"version": 2, "missing_extensions": ["EXT_x"]}))
        self.assertEqual(ids(found), ["WEB-GFX-001"])

    def test_shader_and_python_errors(self):
        found = preflight.check_preflight(report(
            shader_errors=[{"material": "Mat", "stage": "fragment", "log": "ERROR: 0:3"}],
            python_errors=[{"kind": "ModuleNotFoundError", "module": "numpy", "file": "a.py"},
                           {"kind": "FileNotFoundError", "file": "b.py"},
                           {"kind": "ValueError", "text": "x"}]))
        self.assertEqual(ids(found), ["WEB-GFX-002", "WEB-PY-001", "WEB-PKG-003", "WEB-PY-009"])
        self.assertTrue(all(f.severity == "ERROR" and f.evidence == "CONFIRMED" for f in found))


if __name__ == "__main__":
    unittest.main()
