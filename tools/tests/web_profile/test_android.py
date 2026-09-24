"""Testes puros do export Android (range_web/android.py). Sem bpy, sem Gradle e sem aparelho."""

import hashlib
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "source", "release", "scripts", "modules"))

from range_web import android  # noqa: E402

EXE = ".exe" if os.name == "nt" else ""


def touch(path, data=b""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def config(**kw):
    c = dict(android.DEFAULTS, applicationId="com.estudio.jogo", appName="Jogo")
    c.update(kw)
    return c


def make_web_package(root):
    files = {"index.html": b"<html>", "manifest.json": None, "RangeRuntime.wasm": b"wasm",
             "game/jogo.range": b"BLENDER", "serve.py": b"#", "HOSTING.md": b"#"}
    listed = {rel: {"sha256": hashlib.sha256(data).hexdigest()} for rel, data in files.items() if data}
    files["manifest.json"] = json.dumps({"name": "jogo", "version": "1", "files": listed}).encode()
    for rel, data in files.items():
        touch(os.path.join(root, rel), data)
    sums = ["%s  %s" % (hashlib.sha256(data).hexdigest(), rel) for rel, data in sorted(files.items())]
    touch(os.path.join(root, "SHA256SUMS.txt"), ("\n".join(sums) + "\n").encode())


class ConfigTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(android.config_problems(config()), [])

    def test_app_id(self):
        for bad in ("", "jogo", "com..jogo", "1com.jogo", "com.jogo-x"):
            self.assertTrue(android.config_problems(config(applicationId=bad)), bad)

    def test_version_code(self):
        for bad in (0, -1, "3", True, 2100000001):
            self.assertTrue(android.config_problems(config(versionCode=bad)), bad)

    def test_release_blocked_for_now(self):
        self.assertTrue(android.config_problems(config(buildType="release")))

    def test_icon_must_be_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = os.path.join(tmp, "icone.png")
            touch(fake, b"GIF89a")
            self.assertTrue(android.config_problems(config(icon=fake)))
            touch(fake, b"\x89PNG\r\n\x1a\n...")
            self.assertEqual(android.config_problems(config(icon=fake)), [])
            self.assertTrue(android.config_problems(config(icon=os.path.join(tmp, "nao.png"))))

    def test_load_resolves_icon_relative_to_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, android.CONFIG_NAME)
            android.save_config(config(icon="icone.png"), path)
            loaded = android.load_config(path)
            self.assertEqual(loaded["icon"], os.path.join(tmp, "icone.png"))
            self.assertEqual(loaded["applicationId"], "com.estudio.jogo")


class ToolchainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def jdk(self, name):
        path = os.path.join(self.root, name)
        touch(os.path.join(path, "bin", "java" + EXE))
        touch(os.path.join(path, "bin", "javac" + EXE))
        return path

    def sdk(self, name, platform=True):
        path = os.path.join(self.root, name)
        os.makedirs(os.path.join(path, "platforms"))
        if platform:
            os.makedirs(os.path.join(path, "platforms", "android-%d.0" % android.COMPILE_SDK))
        os.makedirs(os.path.join(path, "build-tools", "36.0.0"))
        return path

    def find(self, environ, studio=(), studio_sdk=(), jdk="", sdk=""):
        return android.find_toolchain(jdk, sdk, environ=environ, studio_dirs=list(studio),
                                      studio_sdk_dirs=list(studio_sdk))

    def test_nothing_found_is_clear_error(self):
        with self.assertRaises(android.AndroidError) as ctx:
            self.find({})
        self.assertIn("Nothing was installed", str(ctx.exception))

    def test_order_env_then_studio_then_panel(self):
        env_jdk, env_sdk = self.jdk("envjdk"), self.sdk("envsdk")
        studio = os.path.join(self.root, "studio")
        self.jdk(os.path.join("studio", "jbr"))
        studio_sdk = self.sdk("studiosdk")
        panel_jdk, panel_sdk = self.jdk("paneljdk"), self.sdk("panelsdk")

        tc = self.find({"JAVA_HOME": env_jdk, "ANDROID_HOME": env_sdk}, [studio], [studio_sdk], panel_jdk, panel_sdk)
        self.assertEqual((tc.java_home, tc.sdk_dir), (env_jdk, env_sdk))
        tc = self.find({}, [studio], [studio_sdk], panel_jdk, panel_sdk)
        self.assertEqual((tc.java_source, tc.sdk_source), ("Android Studio", "Android Studio"))
        tc = self.find({"JAVA_HOME": os.path.join(self.root, "invalido")}, [], [], panel_jdk, panel_sdk)
        self.assertEqual((tc.java_home, tc.sdk_dir), (panel_jdk, panel_sdk))

    def test_missing_platform(self):
        with self.assertRaises(android.AndroidError) as ctx:
            self.find({"JAVA_HOME": self.jdk("j"), "ANDROID_HOME": self.sdk("s", platform=False)})
        self.assertIn("platform %d" % android.COMPILE_SDK, str(ctx.exception))


class WebPackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pkg = os.path.join(self.tmp.name, "web")
        make_web_package(self.pkg)

    def tearDown(self):
        self.tmp.cleanup()

    def test_ok(self):
        self.assertEqual(android.verify_web_package(self.pkg)["name"], "jogo")

    def test_missing_package(self):
        with self.assertRaises(android.AndroidError):
            android.verify_web_package(os.path.join(self.tmp.name, "nada"))

    def test_changed_file(self):
        touch(os.path.join(self.pkg, "game", "jogo.range"), b"outro")
        with self.assertRaisesRegex(android.AndroidError, "game/jogo.range"):
            android.verify_web_package(self.pkg)

    def test_missing_file(self):
        os.remove(os.path.join(self.pkg, "RangeRuntime.wasm"))
        with self.assertRaisesRegex(android.AndroidError, "RangeRuntime.wasm"):
            android.verify_web_package(self.pkg)


@unittest.skipIf(android.template_dir() is None, "template Android ausente")
class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pkg = os.path.join(self.tmp.name, "web")
        make_web_package(self.pkg)
        self.icon = os.path.join(self.tmp.name, "icone.png")
        touch(self.icon, b"\x89PNG\r\n\x1a\nxx")

    def tearDown(self):
        self.tmp.cleanup()

    def read(self, *parts):
        with open(os.path.join(self.work, *parts), encoding="utf-8") as f:
            return f.read()

    def test_prepare(self):
        self.work = os.path.join(self.tmp.name, "proj")
        c = config(appName="Rock'n <Roll> & \"Co\"", versionName="2.1", versionCode=7,
                   orientation="landscape", icon=self.icon)
        android.prepare_project(android.template_dir(), self.pkg, c, self.work)

        gradle = self.read("app", "build.gradle.kts")
        self.assertIn('applicationId = "com.estudio.jogo"', gradle)
        self.assertIn('namespace = "%s"' % android.TEMPLATE_NAMESPACE, gradle)
        self.assertIn("versionCode = 7", gradle)
        self.assertIn('versionName = "2.1"', gradle)
        strings = self.read("app", "src", "main", "res", "values", "strings.xml")
        self.assertIn(r"Rock\'n &lt;Roll&gt; &amp; \"Co\"", strings)
        manifest = self.read("app", "src", "main", "AndroidManifest.xml")
        self.assertIn('android:screenOrientation="sensorLandscape"', manifest)
        self.assertIn('android:icon="@mipmap/ic_launcher"', manifest)
        self.assertTrue(os.path.isfile(os.path.join(
            self.work, "app", "src", "main", "res", "mipmap-xxxhdpi", "ic_launcher.png")))

        www = os.path.join(self.work, "app", "src", "main", "assets", "www")
        self.assertTrue(os.path.isfile(os.path.join(www, "game", "jogo.range")))
        self.assertFalse(os.path.exists(os.path.join(www, "serve.py")))
        self.assertFalse(os.path.exists(os.path.join(www, "HOSTING.md")))
        for skipped in ("build", ".gradle", "local.properties"):
            self.assertFalse(os.path.exists(os.path.join(self.work, skipped)), skipped)

    def test_without_icon_keeps_default(self):
        self.work = os.path.join(self.tmp.name, "proj")
        android.prepare_project(android.template_dir(), self.pkg, config(), self.work)
        self.assertNotIn("android:icon", self.read("app", "src", "main", "AndroidManifest.xml"))
        self.assertIn('android:screenOrientation="fullUser"', self.read("app", "src", "main", "AndroidManifest.xml"))


if __name__ == "__main__":
    unittest.main()
