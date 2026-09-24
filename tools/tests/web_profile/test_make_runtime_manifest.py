"""Unit tests for the build-derived parts of make-runtime-manifest.py."""

import importlib.util
import os
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
PATH = os.path.join(ROOT, "tools", "web", "make-runtime-manifest.py")
SPEC = importlib.util.spec_from_file_location("make_runtime_manifest", PATH)
manifest = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(manifest)


class RuntimeManifestTests(unittest.TestCase):
    def cache(self, value):
        directory = tempfile.TemporaryDirectory()
        with open(os.path.join(directory.name, "CMakeCache.txt"), "w", encoding="utf-8") as f:
            f.write("WITH_AUDASPACE:BOOL=%s\n" % value)
        self.addCleanup(directory.cleanup)
        return manifest.Path(directory.name)

    def test_audaspace_adds_aud_and_marks_audio_unvalidated(self):
        build_dir = self.cache("ON")
        self.assertIn("aud", manifest.engine_modules(build_dir))
        self.assertEqual(manifest.capabilities(build_dir)["audio"]["state"], "unvalidated")

    def test_disabled_audaspace_omits_aud_and_marks_audio_disabled(self):
        build_dir = self.cache("OFF")
        self.assertNotIn("aud", manifest.engine_modules(build_dir))
        self.assertEqual(manifest.capabilities(build_dir)["audio"]["state"], "disabled")

    def test_bge_alias_is_always_listed(self):
        self.assertIn("bge", manifest.engine_modules(manifest.Path("missing-cache")))


if __name__ == "__main__":
    unittest.main()
