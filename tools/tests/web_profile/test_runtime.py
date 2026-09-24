"""Testes puros da localizacao do runtime (marco D). Sem bpy.

    python -m unittest discover -s tools/tests/web_profile -v
"""

import hashlib
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "source", "release", "scripts", "modules"))

from range_web import manifest as mf, runtime  # noqa: E402


def write_runtime(directory, runtime_id="web-runtime-release", modules=("math",), content=b"wasm"):
    with open(os.path.join(directory, "RangeRuntime.wasm"), "wb") as f:
        f.write(content)
    data = {
        "schema": mf.MANIFEST_SCHEMA, "schema_version": mf.MANIFEST_SCHEMA_VERSION,
        "runtime_id": runtime_id, "engine_revision": "abc",
        "python": {"version": "3.11", "modules": list(modules)},
        "artifacts": {"RangeRuntime.wasm": {"bytes": 4, "sha256": hashlib.sha256(b"wasm").hexdigest()}},
        "capabilities": {"audio": {"state": "disabled"}},
    }
    with open(os.path.join(directory, mf.MANIFEST_FILENAME), "w", encoding="utf-8") as f:
        json.dump(data, f)


class FindRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_valid_runtime_is_usable_and_exposes_modules(self):
        write_runtime(self.dir, modules=("math", "Range"))
        info = runtime.find_runtime("web-runtime-release", ["/nao/existe", self.dir])
        self.assertTrue(info.usable)
        self.assertEqual(info.python_modules(), {"math", "Range"})
        self.assertEqual(info.directory, self.dir)

    def test_no_manifest_is_pkg001_listing_search_paths(self):
        info = runtime.find_runtime("web-runtime-release", [self.dir])
        self.assertFalse(info.usable)
        self.assertIsNone(info.python_modules())
        self.assertEqual([f.rule_id for f in info.findings], ["WEB-PKG-001"])
        self.assertIn(self.dir, info.findings[0].message)

    def test_no_candidates(self):
        info = runtime.find_runtime("web-runtime-release", [])
        self.assertEqual([f.rule_id for f in info.findings], ["WEB-PKG-001"])

    def test_runtime_id_mismatch_blocks_but_keeps_manifest(self):
        write_runtime(self.dir, runtime_id="web-runtime")
        info = runtime.find_runtime("web-runtime-release", [self.dir])
        self.assertFalse(info.usable)
        self.assertEqual([f.rule_id for f in info.findings], ["WEB-PKG-001"])
        self.assertIsNotNone(info.python_modules())

    def test_hash_divergence_is_pkg001(self):
        write_runtime(self.dir, content=b"wasm")
        with open(os.path.join(self.dir, "RangeRuntime.wasm"), "wb") as f:
            f.write(b"xxxx")
        info = runtime.find_runtime("web-runtime-release", [self.dir])
        self.assertFalse(info.usable)
        self.assertIn("Hash", info.findings[0].message)

    def test_invalid_manifest_gives_no_modules(self):
        with open(os.path.join(self.dir, mf.MANIFEST_FILENAME), "w") as f:
            f.write("{}")
        info = runtime.find_runtime("web-runtime-release", [self.dir])
        self.assertIsNone(info.python_modules())
        self.assertEqual([f.rule_id for f in info.findings], ["WEB-PKG-001"])


if __name__ == "__main__":
    unittest.main()
