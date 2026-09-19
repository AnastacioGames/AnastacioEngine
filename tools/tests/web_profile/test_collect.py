"""Testes puros da resolucao de dependencias (marco C). Sem bpy.

    python -m unittest discover -s tools/tests/web_profile -v
"""

import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "source", "release", "scripts", "modules"))

from range_web import collect  # noqa: E402
from range_web.collect import KIND_MODULE, KIND_TEXT, Reference, Snapshot  # noqa: E402

STDLIB = {"sys", "os", "math", "random", "subprocess", "importlib"}


def ref(kind, target, required=True):
    return Reference(kind, target, ["fase.range", "Porta", "Abrir"], scene="Cena",
                     object="Porta", datablock="Controller:Abrir", required=required)


def finder(files):
    def find(name):
        src = files.get(name)
        return None if src is None else ("/proj/%s.py" % name.replace(".", "/"), src)
    return find


def snap(refs, files=None, texts=None, tops=None):
    files = files or {}
    tops = {n.split(".")[0] for n in files} if tops is None else tops
    return Snapshot(refs, texts=texts, find_module=finder(files), project_tops=tops, stdlib=STDLIB)


def ids(findings):
    return sorted(f.rule_id for f in findings)


class ResolveTests(unittest.TestCase):
    def test_module_controller_ok(self):
        findings, visited = collect.resolve(snap([ref(KIND_MODULE, "door.open")], {"door": "import math\n"}))
        self.assertEqual(findings, [])
        self.assertIn(("module", "door"), visited)

    def test_missing_module_reports_chain(self):
        findings, _ = collect.resolve(snap([ref(KIND_MODULE, "door_logic.open")]))
        self.assertEqual(ids(findings), ["WEB-PKG-003"])
        loc = findings[0].location
        self.assertEqual(loc["chain"], "fase.range > Porta > Abrir")
        self.assertEqual(loc["object"], "Porta")
        self.assertEqual(loc["source"], "door_logic")

    def test_internal_text_takes_precedence_and_ok(self):
        findings, _ = collect.resolve(snap([ref(KIND_TEXT, "door.py")], texts={"door.py": "x = 1\n"}))
        self.assertEqual(findings, [])

    def test_missing_text_and_empty_text(self):
        findings, _ = collect.resolve(snap([ref(KIND_TEXT, "gone.py"), ref(KIND_TEXT, "")]))
        self.assertEqual(ids(findings), ["WEB-PKG-003", "WEB-PKG-003"])
        self.assertIn("sem Text definido", findings[1].message)

    def test_transitive_missing_import_is_py001_not_duplicated(self):
        files = {"a": "import b\n", "b": "import nao_existe\n"}
        findings, visited = collect.resolve(snap([ref(KIND_MODULE, "a.f")], files))
        self.assertEqual(ids(findings), ["WEB-PY-001"])
        self.assertIn(("module", "b"), visited)
        self.assertEqual(findings[0].location["source"], "/proj/b.py")
        self.assertEqual(findings[0].location["chain"], "fase.range > Porta > Abrir > b")

    def test_cycle_terminates_and_analyzes_once(self):
        files = {"a": "import b\nimport subprocess\nsubprocess.run(['x'])\n", "b": "import a\n"}
        findings, visited = collect.resolve(snap([ref(KIND_MODULE, "a.f")], files))
        self.assertEqual(ids(findings), ["WEB-PY-002"])
        self.assertEqual(len([k for k in visited if k[0] == "module"]), 2)

    def test_shared_dependency_from_two_roots_analyzed_once(self):
        files = {"a": "import c\n", "b": "import c\n", "c": "import subprocess\nsubprocess.run(['x'])\n"}
        findings, _ = collect.resolve(snap([ref(KIND_MODULE, "a.f"), ref(KIND_MODULE, "b.f")], files))
        self.assertEqual(ids(findings), ["WEB-PY-002"])

    def test_dynamic_import_is_warning_only(self):
        files = {"a": "import importlib\nimportlib.import_module(name)\n"}
        findings, _ = collect.resolve(snap([ref(KIND_MODULE, "a.f")], files))
        self.assertEqual(ids(findings), ["WEB-PKG-007", "WEB-PY-009"])
        self.assertTrue(all(f.severity == "WARNING" for f in findings))

    def test_guarded_optional_import_not_followed(self):
        files = {"a": "try:\n    import opt\nexcept ImportError:\n    opt = None\n", "opt": "import subprocess\nsubprocess.run(['x'])\n"}
        findings, visited = collect.resolve(snap([ref(KIND_MODULE, "a.f")], files))
        self.assertEqual(findings, [])
        self.assertNotIn(("module", "opt"), visited)

    def test_stdlib_component_module_not_missing(self):
        findings, visited = collect.resolve(snap([ref(KIND_MODULE, "math.Thing")]))
        self.assertEqual(findings, [])
        self.assertEqual(visited[("module", "math")], "runtime")

    def test_package_dotted_module(self):
        files = {"game.logic": "import math\n"}
        findings, _ = collect.resolve(snap([ref(KIND_MODULE, "game.logic.Comp")], files))
        self.assertEqual(findings, [])

    def test_from_package_import_submodule_is_followed(self):
        files = {"a": "from pkg import util, CONST\n", "pkg": "CONST = 1\n",
                 "pkg.util": "import subprocess\nsubprocess.run(['x'])\n"}
        findings, visited = collect.resolve(snap([ref(KIND_MODULE, "a.f")], files))
        self.assertEqual(ids(findings), ["WEB-PY-002"])
        self.assertIn(("module", "pkg.util"), visited)
        self.assertNotIn(("module", "pkg.CONST"), visited)

    def test_syntax_error_in_dependency(self):
        findings, _ = collect.resolve(snap([ref(KIND_MODULE, "a.f")], {"a": "def (:\n"}))
        self.assertEqual(ids(findings), ["WEB-PY-008"])


class AssetTests(unittest.TestCase):
    def test_missing_asset_error_with_origin(self):
        origin = {"datablock": "Image:wall", "chain": "Imagem > wall"}
        findings = collect.check_assets([("Imagem", "/x/wall.png", origin)], lambda p: False)
        self.assertEqual(ids(findings), ["WEB-PKG-003"])
        self.assertEqual(findings[0].location["datablock"], "Image:wall")

    def test_present_asset_ok(self):
        self.assertEqual(collect.check_assets([("Som", "/x/a.ogg", {})], lambda p: True), [])

    def test_asset_outside_project_root_is_pkg005(self):
        import tempfile
        with tempfile.TemporaryDirectory() as proj, tempfile.TemporaryDirectory() as other:
            inside, outside = os.path.join(proj, "a.png"), os.path.join(other, "b.png")
            for p in (inside, outside):
                open(p, "wb").close()
            findings = collect.check_assets([("Imagem", inside, {}), ("Imagem", outside, {})],
                                            os.path.isfile, roots=(proj,))
            self.assertEqual(ids(findings), ["WEB-PKG-005"])


if __name__ == "__main__":
    unittest.main()
