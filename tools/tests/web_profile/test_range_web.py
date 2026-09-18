"""Testes puros do nucleo range_web (marco B). Sem bpy.

    python -m unittest discover -s tools/tests/web_profile -v
    build/bin/RangeEngine.exe -b --python tools/tests/web_profile/test_range_web.py  (Python do motor, 3.11)
"""

import hashlib
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "source", "release", "scripts", "modules"))

from range_web import (  # noqa: E402
    EVIDENCE_CONFIRMED, EVIDENCE_POTENTIAL, EVIDENCE_UNVALIDATED,
    SEVERITY_ERROR, SEVERITY_WARNING, Finding, Report,
)
from range_web import manifest as mf  # noqa: E402
from range_web import rules_files as rf  # noqa: E402
from range_web import rules_python as rp  # noqa: E402

STDLIB = {"sys", "os", "math", "time", "random", "json"}


def ids(findings):
    return sorted(f.rule_id for f in findings)


def one(findings, rule_id):
    found = [f for f in findings if f.rule_id == rule_id]
    assert len(found) == 1, (rule_id, findings)
    return found[0]


def analyze(src, required=True, available=STDLIB):
    return rp.analyze_source(src, "ctrl.py", required=required, available_modules=available)


class ResultsTest(unittest.TestCase):
    def test_error_needs_proof(self):
        with self.assertRaises(ValueError):
            Finding("X", SEVERITY_ERROR, EVIDENCE_POTENTIAL, "m")

    def test_summary_never_guarantees(self):
        r = Report()
        self.assertEqual(r.summary(), "Nenhuma incompatibilidade detectada")
        self.assertNotIn("garant", r.summary().lower())
        r.add(Finding("X", SEVERITY_WARNING, EVIDENCE_POTENTIAL, "m"))
        self.assertFalse(r.blocks_export)
        r.add(Finding("Y", SEVERITY_ERROR, EVIDENCE_CONFIRMED, "m"))
        self.assertTrue(r.blocks_export)
        self.assertEqual(json.loads(r.to_json())["findings"][1]["rule_id"], "Y")


class ManifestTest(unittest.TestCase):
    def good(self):
        return {
            "schema": mf.MANIFEST_SCHEMA, "schema_version": mf.MANIFEST_SCHEMA_VERSION,
            "runtime_id": "web-runtime-release", "engine_revision": "abc",
            "python": {"version": "3.11.7", "modules": ["sys"], "pyc_magic": "a70d0d0a"},
            "artifacts": {"RangeRuntime.wasm": {"bytes": 3, "sha256": hashlib.sha256(b"abc").hexdigest()}},
            "capabilities": {
                "audio": {"state": "disabled"},
                "save": {"state": "validated", "evidence": ["verify-save.cjs 2026-09-18"]},
                "physics": {"state": "unvalidated"},
            },
        }

    def test_valid(self):
        self.assertEqual(mf.validate_manifest(self.good()), [])

    def test_invalid_variants(self):
        d = self.good(); d["schema_version"] = 99
        self.assertTrue(mf.validate_manifest(d))
        d = self.good(); del d["capabilities"]
        self.assertTrue(mf.validate_manifest(d))
        d = self.good(); d["capabilities"]["save"] = {"state": "validated"}
        self.assertIn("sem evidence", mf.validate_manifest(d)[0])
        d = self.good(); d["capabilities"]["x"] = {"state": "on"}
        self.assertTrue(mf.validate_manifest(d))
        d = self.good(); d["python"]["pyc_magic"] = "zz"
        self.assertTrue(mf.validate_manifest(d))
        self.assertTrue(mf.validate_manifest([]))

    def test_load_missing_and_corrupt_single_finding(self):
        with tempfile.TemporaryDirectory() as t:
            m, f = mf.load_manifest(os.path.join(t, "nope.json"))
            self.assertIsNone(m)
            self.assertEqual(ids(f), ["WEB-PKG-001"])
            bad = os.path.join(t, "bad.json")
            with open(bad, "w") as fh:
                fh.write("{")
            m, f = mf.load_manifest(bad)
            self.assertIsNone(m)
            self.assertEqual(len(f), 1)

    def test_load_and_verify_artifacts(self):
        with tempfile.TemporaryDirectory() as t:
            path = os.path.join(t, mf.MANIFEST_FILENAME)
            with open(path, "w") as fh:
                json.dump(self.good(), fh)
            m, f = mf.load_manifest(path)
            self.assertEqual(f, [])
            self.assertEqual(ids(mf.verify_artifacts(m, t)), ["WEB-PKG-001"])  # ausente
            with open(os.path.join(t, "RangeRuntime.wasm"), "wb") as fh:
                fh.write(b"abc")
            self.assertEqual(mf.verify_artifacts(m, t), [])
            with open(os.path.join(t, "RangeRuntime.wasm"), "wb") as fh:
                fh.write(b"abd")  # mesmo tamanho, hash diferente
            self.assertIn("Hash", mf.verify_artifacts(m, t)[0].message)

    def test_capability_three_states(self):
        m = self.good()
        self.assertIsNone(mf.capability_finding(m, "save", "WEB-SAVE-001", "Save"))
        dis = mf.capability_finding(m, "audio", "WEB-MEDIA-001", "Sound")
        self.assertEqual((dis.severity, dis.evidence), (SEVERITY_ERROR, EVIDENCE_CONFIRMED))
        unv = mf.capability_finding(m, "physics", "WEB-SIM-001", "Bullet")
        self.assertEqual((unv.severity, unv.evidence), ("INFO", EVIDENCE_UNVALIDATED))
        absent = mf.capability_finding(m, "nada", "WEB-X", "X")
        self.assertEqual(absent.evidence, EVIDENCE_UNVALIDATED)  # ausente nunca e suportado


class FilesTest(unittest.TestCase):
    def test_host_paths(self):
        self.assertEqual(ids(rf.check_runtime_path("C:\\Users\\a\\tex.png", "s.py", 3)), ["WEB-PKG-004"])
        self.assertEqual(ids(rf.check_runtime_path("/home/x/a.png", "s.py")), ["WEB-PKG-004"])
        self.assertEqual(rf.check_runtime_path("//textures/a.png", "s.py"), [])
        self.assertEqual(rf.check_runtime_path("assets/a.png", "s.py"), [])

    def test_normalize(self):
        self.assertEqual(rf.normalize_virtual_path("a\\b/./c.png"), ("a/b/c.png", None))
        self.assertIsNotNone(rf.normalize_virtual_path("../x")[1])
        self.assertIsNotNone(rf.normalize_virtual_path("a/../../x")[1])
        self.assertIsNotNone(rf.normalize_virtual_path("/etc/x")[1])
        self.assertIsNotNone(rf.normalize_virtual_path("D:\\x")[1])

    def test_destinations(self):
        ok = rf.check_destinations([("a/x.png", "s1"), ("a/y.png", "s2")])
        self.assertEqual(ok, [])
        self.assertEqual(ids(rf.check_destinations([("a/x.png", "s1"), ("a/./x.png", "s2")])), ["WEB-PKG-005"])
        self.assertEqual(ids(rf.check_destinations([("a/x.png", "s1"), ("a/X.png", "s2")])), ["WEB-PKG-006"])
        self.assertEqual(ids(rf.check_destinations([("../out.png", "s1")])), ["WEB-PKG-005"])

    def test_reference_case(self):
        avail = ["tex/Wall.png"]
        self.assertEqual(rf.check_reference_case("tex/Wall.png", avail, "s"), [])
        self.assertEqual(ids(rf.check_reference_case("tex/wall.png", avail, "s")), ["WEB-PKG-006"])
        self.assertEqual(rf.check_reference_case("tex/other.png", avail, "s"), [])  # ausente e outra regra

    def test_within_roots(self):
        with tempfile.TemporaryDirectory() as t:
            root = os.path.join(t, "proj")
            os.mkdir(root)
            inside = os.path.join(root, "a.txt")
            open(inside, "w").close()
            outside = os.path.join(t, "b.txt")
            open(outside, "w").close()
            self.assertEqual(rf.check_within_roots(inside, [root]), [])
            self.assertEqual(ids(rf.check_within_roots(outside, [root])), ["WEB-PKG-005"])
            self.assertEqual(ids(rf.check_within_roots(os.path.join(root, "..", "b.txt"), [root])), ["WEB-PKG-005"])
            link = os.path.join(root, "link.txt")
            try:
                os.symlink(outside, link)
            except (OSError, NotImplementedError):
                return  # sem privilegio de symlink (Windows): o resto ja cobre o escape
            self.assertEqual(ids(rf.check_within_roots(link, [root])), ["WEB-PKG-005"])

    def test_file_kind(self):
        self.assertEqual(ids(rf.check_file_kind("x.pyd", b"MZ\x90\x00")), ["WEB-PKG-008"])
        self.assertEqual(rf.check_file_kind("x.pyd", b"MZ\x90\x00")[0].severity, SEVERITY_ERROR)
        weak = rf.check_file_kind("x.so", b"text")[0]
        self.assertEqual((weak.severity, weak.evidence), (SEVERITY_WARNING, EVIDENCE_POTENTIAL))
        self.assertEqual(rf.check_file_kind("data.dll.txt", b"MZ"), [])
        self.assertEqual(ids(rf.check_file_kind("g.rasec", b"RASE")), ["WEB-PKG-009"])
        magic = bytes.fromhex("a70d0d0a")
        self.assertEqual(rf.check_file_kind("m.pyc", magic, expected_pyc_magic=magic), [])
        self.assertEqual(rf.check_file_kind("m.pyc", b"\x00\x00\x0d\x0a", expected_pyc_magic=magic)[0].severity,
                         SEVERITY_ERROR)
        self.assertEqual(rf.check_file_kind("m.pyc", magic)[0].severity, SEVERITY_WARNING)  # sem magic do runtime


class PythonTest(unittest.TestCase):
    def test_syntax_error(self):
        f = analyze("def x(:\n  pass\n").findings
        self.assertEqual(ids(f), ["WEB-PY-008"])
        self.assertEqual(f[0].location["line"], 1)

    def test_clean_script(self):
        r = analyze("import math\n\ndef main(c):\n    c.owner.position.x += math.sin(1)\n")
        self.assertEqual(r.findings, [])

    def test_import_alone_is_silent(self):
        self.assertEqual(analyze("import subprocess\n", available={"subprocess"}).findings, [])

    def test_process_call_toplevel_is_error(self):
        f = one(analyze("import subprocess\nsubprocess.run(['ls'])\n", available={"subprocess"}).findings, "WEB-PY-002")
        self.assertEqual((f.severity, f.evidence), (SEVERITY_ERROR, EVIDENCE_CONFIRMED))
        self.assertEqual(f.location["line"], 2)

    def test_process_call_in_function_is_warning(self):
        f = one(analyze("import os\ndef go():\n    os.system('x')\n").findings, "WEB-PY-002")
        self.assertEqual((f.severity, f.evidence), (SEVERITY_WARNING, EVIDENCE_POTENTIAL))

    def test_not_required_downgrades(self):
        f = one(analyze("import os\nos.system('x')\n", required=False).findings, "WEB-PY-002")
        self.assertEqual(f.severity, SEVERITY_WARNING)

    def test_aliases(self):
        f = analyze("import subprocess as sp\nfrom os import system as s\nsp.Popen('a')\ns('b')\n",
                    available={"subprocess", "os"}).findings
        self.assertEqual(ids(f), ["WEB-PY-002", "WEB-PY-002"])

    def test_rebinding_drops_alias(self):
        f = analyze("import os\nos = FakeOS()\nos.system('x')\n").findings
        self.assertEqual(f, [])

    def test_param_shadowing(self):
        f = analyze("import os\ndef f(os):\n    os.system('x')\n").findings
        self.assertEqual(f, [])

    def test_desktop_guard_resolved(self):
        src = "import sys, subprocess\nif sys.platform == 'win32':\n    subprocess.run('x')\n"
        self.assertEqual(analyze(src, available=STDLIB | {"subprocess"}).findings, [])
        src = "import sys, subprocess\nif sys.platform != 'win32':\n    subprocess.run('x')\n"
        self.assertEqual(ids(analyze(src, available=STDLIB | {"subprocess"}).findings), ["WEB-PY-002"])
        src = "import os, subprocess\nif os.name == 'nt':\n    subprocess.run('x')\n"
        self.assertEqual(analyze(src, available=STDLIB | {"subprocess"}).findings, [])
        src = "import sys, subprocess\nif sys.platform.startswith('win'):\n    subprocess.run('x')\nelse:\n    pass\n"
        self.assertEqual(analyze(src, available=STDLIB | {"subprocess"}).findings, [])
        src = "import sys, subprocess\nif not sys.platform.startswith(('win', 'linux')):\n    subprocess.run('x')\n"
        self.assertEqual(ids(analyze(src, available=STDLIB | {"subprocess"}).findings), ["WEB-PY-002"])

    def test_unknown_guard_downgrades(self):
        src = "import os\nif DEBUG:\n    os.system('x')\n"
        f = one(analyze(src).findings, "WEB-PY-002")
        self.assertEqual(f.severity, SEVERITY_WARNING)

    def test_ctypes_and_threads(self):
        f = analyze("import ctypes, threading\nctypes.CDLL('x.dll')\nthreading.Thread(target=f).start()\n",
                    available={"ctypes", "threading"}).findings
        self.assertEqual(ids(f), ["WEB-PY-003", "WEB-PY-004"])
        # import de threading sem criar thread nao e prova
        self.assertEqual(analyze("import threading\nlock = threading.Lock()\n", available={"threading"}).findings, [])

    def test_editor_api(self):
        f = one(analyze("import bpy\n").findings, "WEB-PY-007")
        self.assertEqual(f.severity, SEVERITY_ERROR)
        guarded = "try:\n    import bpy\nexcept ImportError:\n    bpy = None\n"
        self.assertEqual(analyze(guarded).findings, [])
        f = one(analyze("def tool():\n    import bpy\n").findings, "WEB-PY-007")
        self.assertEqual(f.severity, SEVERITY_WARNING)

    def test_unresolved_import(self):
        f = one(analyze("import inexistente\n").findings, "WEB-PY-001")
        self.assertEqual(f.severity, SEVERITY_ERROR)
        self.assertEqual(analyze("import inexistente\n", available=None).findings, [])
        opt = "try:\n    import inexistente\nexcept ImportError:\n    pass\n"
        self.assertEqual(analyze(opt).findings, [])
        f = one(analyze("def f():\n    import inexistente\n").findings, "WEB-PY-001")
        self.assertEqual(f.severity, SEVERITY_WARNING)
        self.assertEqual(analyze("import mod_do_jogo\n", available=STDLIB | {"mod_do_jogo"}).findings, [])

    def test_records_imports(self):
        r = analyze("import math\ntry:\n    import json\nexcept ImportError:\n    pass\n")
        self.assertEqual(r.imports, [("math", 1, False), ("json", 3, True)])

    def test_blocking(self):
        f = analyze("import time\ndef f():\n    time.sleep(1)\n").findings
        self.assertEqual((f[0].rule_id, f[0].severity), ("WEB-PY-006", SEVERITY_WARNING))
        f = analyze("while True:\n    x = 1\n").findings
        self.assertEqual(ids(f), ["WEB-PY-006"])
        # laco com saida nao e proibido
        self.assertEqual(analyze("while True:\n    if x:\n        break\n").findings, [])
        self.assertEqual(analyze("while cond:\n    pass\n").findings, [])
        # break de laco interno nao encerra o externo
        self.assertEqual(ids(analyze("while True:\n    for i in y:\n        break\n").findings), ["WEB-PY-006"])

    def test_dynamic_is_partial_coverage_never_error(self):
        r = analyze("import importlib\nname = get()\nimportlib.import_module(name)\neval('1')\n",
                    available={"importlib"})
        self.assertEqual(ids(r.findings), ["WEB-PKG-007", "WEB-PY-009", "WEB-PY-009"])
        self.assertTrue(all(f.severity == SEVERITY_WARNING for f in r.findings))
        self.assertTrue(r.has_dynamic)

    def test_dynamic_import_with_constant_resolves(self):
        r = analyze("m = __import__('inexistente')\n")
        self.assertEqual(ids(r.findings), ["WEB-PY-001"])

    def test_never_executes_source(self):
        marker = os.path.join(tempfile.gettempdir(), "range_web_should_not_exist_%d" % os.getpid())
        src = "open(%r, 'w').write('x')\nimport os; os.remove(%r)\n" % (marker, marker)
        analyze(src)
        self.assertFalse(os.path.exists(marker))

    def test_main_loop(self):
        self.assertEqual(rp.check_python_main_loop(""), [])
        self.assertEqual(ids(rp.check_python_main_loop("loop.py")), ["WEB-PY-005"])
        self.assertEqual(rp.check_python_main_loop("loop.py", adapter_validated=True), [])


if __name__ == "__main__":
    # argv fixo: dentro do motor, sys.argv carrega os argumentos do executavel.
    unittest.main(argv=sys.argv[:1], verbosity=2)
