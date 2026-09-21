"""Falhas injetadas no relatorio de pre-voo: shader, Python estruturado e versao desconhecida. Sem bpy."""

import os
import json
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "source", "release", "scripts", "modules"))

from range_web import preflight  # noqa: E402


def report(**kw):
    d = {"schema": preflight.PREFLIGHT_SCHEMA, "schema_version": preflight.PREFLIGHT_SCHEMA_VERSION}
    d.update(kw)
    return d


def shader_report(stage, operation, log, material="MAMaterial"):
    return report(
        shader_errors=[{"material": material, "stage": stage, "operation": operation, "log": log,
                        "structured": True}],
        diagnostics=[{"version": 1, "category": "shader", "severity": "error", "operation": operation,
                      "stage": stage, "origin": material, "log": log}])


class ShaderFailureTests(unittest.TestCase):
    def check_shader(self, stage, operation):
        log = "ERROR: 0:12: 'foo' : undeclared identifier"
        found = preflight.check_preflight(shader_report(stage, operation, log))
        self.assertEqual([f.rule_id for f in found], ["WEB-GFX-002"])
        self.assertIn("estágio %s" % stage, found[0].message)
        self.assertIn("MAMaterial", found[0].message)
        self.assertEqual(found[0].fix, log)
        self.assertEqual(found[0].location["source"], "MAMaterial")

    def test_vertex_compile(self):
        self.check_shader("vertex", "compile")

    def test_fragment_compile(self):
        self.check_shader("fragment", "compile")

    def test_link(self):
        self.check_shader("link", "link")

    def test_link_event_without_stage_keeps_material_and_log(self):
        fixture = os.path.join(os.path.dirname(__file__), "fixtures", "preflight-link.json")
        with open(fixture, "r") as handle:
            found = preflight.check_preflight(json.load(handle))
        self.assertEqual([f.rule_id for f in found], ["WEB-GFX-002"])
        self.assertIn("MatQuebradoLink", found[0].message)
        self.assertNotIn("link, material", found[0].message)
        self.assertEqual(found[0].fix, "ERROR: 0: program link failed")

    def test_shader_without_material_still_reported(self):
        found = preflight.check_preflight(shader_report("vertex", "compile", "bad", material=""))
        self.assertEqual([f.rule_id for f in found], ["WEB-GFX-002"])
        self.assertNotIn("material", found[0].message)


class PythonFailureTests(unittest.TestCase):
    def test_structured_import_error(self):
        found = preflight.check_preflight(report(python_errors=[
            {"kind": "ModuleNotFoundError", "module": "numpy", "file": "", "text": "No module named 'numpy'",
             "origin": "Cube", "context": "controller", "traceback": "Traceback...", "structured": True}]))
        self.assertEqual([f.rule_id for f in found], ["WEB-PY-001"])
        self.assertIn("numpy", found[0].message)

    def test_structured_import_error_without_module_uses_text(self):
        found = preflight.check_preflight(report(python_errors=[
            {"kind": "ImportError", "text": "cannot import name 'x'", "structured": True}]))
        self.assertEqual([f.rule_id for f in found], ["WEB-PY-001"])
        self.assertIn("cannot import name", found[0].message)

    def test_structured_syntax_error_keeps_origin_and_traceback(self):
        found = preflight.check_preflight(report(python_errors=[
            {"kind": "SyntaxError", "text": "invalid syntax (script.py, line 3)", "origin": "Cube",
             "context": "controller", "traceback": "File \"script.py\", line 3", "structured": True}]))
        self.assertEqual([f.rule_id for f in found], ["WEB-PY-009"])
        self.assertIn("SyntaxError", found[0].message)
        self.assertIn("controller em Cube", found[0].message)
        self.assertEqual(found[0].location["source"], "Cube")
        self.assertEqual(found[0].fix, "File \"script.py\", line 3")

    def test_syntax_error_deduplicated_per_origin(self):
        rec = {"kind": "SyntaxError", "text": "bad", "origin": "Cube", "context": "controller"}
        found = preflight.check_preflight(report(python_errors=[rec, dict(rec), dict(rec, origin="Sphere")]))
        self.assertEqual(len(found), 2)


class UnknownVersionTests(unittest.TestCase):
    def test_unknown_version_degrades_to_single_finding(self):
        for version in (99, 0, None, "2", [2]):
            data = report(schema_version=version, shader_errors=[{"stage": "vertex", "log": "x"}],
                          python_errors=[{"kind": "ValueError", "text": "x"}])
            found = preflight.check_preflight(data)
            self.assertEqual([f.rule_id for f in found], ["WEB-DEPLOY-002"], version)

    def test_missing_version_degrades(self):
        data = {"schema": preflight.PREFLIGHT_SCHEMA}
        self.assertEqual([f.rule_id for f in preflight.check_preflight(data)], ["WEB-DEPLOY-002"])

    def test_unknown_schema_and_non_dict_degrade(self):
        for data in ({"schema": "outro", "schema_version": 2}, [], None, "x"):
            self.assertEqual([f.rule_id for f in preflight.check_preflight(data)], ["WEB-DEPLOY-002"])

    def test_unknown_fields_are_ignored(self):
        found = preflight.check_preflight(report(campo_futuro={"a": 1}, diagnostics=[{"version": 9, "category": "nova"}]))
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
