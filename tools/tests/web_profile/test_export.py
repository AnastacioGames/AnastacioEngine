"""Testes puros do export Web (marco F). Sem bpy."""

import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "source", "release", "scripts", "modules"))

from range_web import Finding, Report, export  # noqa: E402


def make_report(error=False):
    r = Report()
    if error:
        r.add(Finding("WEB-PKG-001", "ERROR", "CONFIRMED", "x"))
    return r


def writer(text):
    def build(tmp):
        with open(os.path.join(tmp, "index.html"), "w") as f:
            f.write(text)
        open(os.path.join(tmp, "manifest.json"), "w").close()
    return build


def read(dest):
    with open(os.path.join(dest, "index.html")) as f:
        return f.read()


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dest = os.path.join(self.tmp.name, "web")

    def tearDown(self):
        self.tmp.cleanup()

    def test_first_export_and_replace(self):
        export.export_package(make_report(), self.dest, writer("v1"))
        export.export_package(make_report(), self.dest, writer("v2"))
        self.assertEqual(read(self.dest), "v2")
        self.assertEqual(sorted(os.listdir(self.tmp.name)), ["web"])

    def test_errors_block_and_keep_previous(self):
        export.export_package(make_report(), self.dest, writer("v1"))
        with self.assertRaises(export.ExportBlocked):
            export.export_package(make_report(error=True), self.dest, writer("v2"))
        self.assertEqual(read(self.dest), "v1")

    def test_build_failure_keeps_previous(self):
        export.export_package(make_report(), self.dest, writer("v1"))

        def boom(tmp):
            open(os.path.join(tmp, "partial"), "w").close()
            raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            export.export_package(make_report(), self.dest, boom)
        self.assertEqual(read(self.dest), "v1")
        self.assertEqual(sorted(os.listdir(self.tmp.name)), ["web"])

    def test_empty_build_and_missing_report(self):
        with self.assertRaises(RuntimeError):
            export.export_package(make_report(), self.dest, lambda tmp: None)
        self.assertFalse(os.path.exists(self.dest))
        with self.assertRaises(ValueError):
            export.export_package(None, self.dest, writer("x"))

    def test_refuses_folder_with_other_files(self):
        os.makedirs(self.dest)
        other = os.path.join(self.dest, "importante.txt")
        open(other, "w").close()
        with self.assertRaises(ValueError):
            export.export_package(make_report(), self.dest, writer("v1"))
        self.assertTrue(os.path.isfile(other))

    def test_refuses_folder_containing_project(self):
        os.makedirs(self.dest)
        game = os.path.join(self.dest, "jogo.range")
        open(game, "w").close()
        with self.assertRaises(ValueError):
            export.export_package(make_report(), self.dest, writer("v1"), protected=(game,))
        self.assertTrue(os.path.isfile(game))

    def test_refuses_drive_root(self):
        root = os.path.abspath(os.sep)
        with self.assertRaises(ValueError):
            export.check_destination(root)


if __name__ == "__main__":
    unittest.main()
