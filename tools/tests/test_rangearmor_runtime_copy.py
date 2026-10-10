"""Verify the actual runtime copy retains dependencies and excludes editors."""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest import mock


class RuntimeCopy(unittest.TestCase):
    def test_portable_installation_is_found_without_environment_overrides(self):
        source_scripts = Path(__file__).resolve().parents[1] / 'rangearmor/release/scripts'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scripts = root / 'installation/rangearmor/release/scripts'
            scripts.mkdir(parents=True)
            for name in ('common.py', 'get_rangeengine_currentplatform.py'):
                shutil.copy2(source_scripts / name, scripts / name)
            (root / 'installation/AnastacioRuntime.exe').write_bytes(b'portable runtime')
            project = root / 'project'
            (project / 'launcher').mkdir(parents=True)
            config = project / 'launcher/config.json'
            config.write_text(json.dumps({'EngineWindows64': './engine/Windows64/RangeRuntime.exe'}))
            env = {key: value for key, value in os.environ.items() if not key.startswith('RANGEARMOR_ENGINE_DIR')}
            result = subprocess.run([sys.executable, str(scripts / 'get_rangeengine_currentplatform.py'),
                                     '--project', str(config), '--platform', 'Windows64'],
                                    cwd=project, env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((project / 'engine/Windows64/AnastacioRuntime.exe').read_bytes(), b'portable runtime')

    def test_cli_missing_runtime_returns_error_and_keeps_previous(self):
        script = Path(__file__).resolve().parents[1] / 'rangearmor/release/scripts/get_rangeengine_currentplatform.py'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'launcher').mkdir()
            target = root / 'engine/Windows64'
            target.mkdir(parents=True)
            previous = target / 'RangeRuntime.exe'
            previous.write_bytes(b'previous runtime')
            config = root / 'launcher/config.json'
            config.write_text(json.dumps({'EngineWindows64': './engine/Windows64/RangeRuntime.exe'}))
            env = dict(os.environ, RANGEARMOR_ENGINE_DIR_WINDOWS64=str(root / 'missing'))
            result = subprocess.run([sys.executable, str(script), '--project', str(config),
                                     '--platform', 'Windows64'], env=env, capture_output=True,
                                    text=True, timeout=30)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Could not find a Windows64', result.stdout)
            self.assertEqual(previous.read_bytes(), b'previous runtime')
            invalid = subprocess.run([sys.executable, str(script), '--project', str(config),
                                      '--platform', 'Windows32'], env=env, capture_output=True,
                                     text=True, timeout=30)
            self.assertNotEqual(invalid.returncode, 0)
            self.assertIn('Unsupported runtime platform', invalid.stdout)

    def test_copy_keeps_runtime_crt_and_python_without_editors(self):
        script = Path(__file__).resolve().parents[1] / 'rangearmor/release/scripts/get_rangeengine_currentplatform.py'
        common = mock.Mock()
        common.getArgs.return_value = {}
        common.getProjectData.return_value = {}
        with mock.patch.dict('sys.modules', {'common': common}):
            spec = importlib.util.spec_from_file_location('armor_copy', script)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        # Use the real compatibility resolver while isolating the CLI globals.
        scripts = str(script.parent)
        with mock.patch.object(sys, 'path', [scripts] + sys.path):
            import common as real_common
        common.resolve_runtime.side_effect = real_common.resolve_runtime
        with tempfile.TemporaryDirectory(prefix='Armor cópia ') as directory:
            root = Path(directory)
            source = root / 'installation'
            source.mkdir()
            kept = ['AnastacioRuntime.exe', 'library.dll', 'blender.crt/blender.crt.manifest',
                    'blender.crt/msvcr90.dll', '2.79/python/bin/python.exe']
            excluded = ['AnastacioEngine.exe', 'RangeEngine.exe', 'ANASTACIOENGINE.EXE',
                        'rangearmor/panel.exe']
            for name in kept + excluded:
                path = source / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'fixture')
            module.data = {'CurPath': root / 'project'}
            module.copy_runtime(source, 'Windows64')
            target = root / 'project/engine/Windows64'
            for name in kept:
                self.assertEqual((target / name).read_bytes(), b'fixture')
            for name in excluded:
                self.assertFalse((target / name).exists())
            with mock.patch.object(module.shutil, 'copytree', side_effect=OSError('copy failed')):
                with self.assertRaises(OSError):
                    module.copy_runtime(source, 'Windows64')
            self.assertTrue((target / 'AnastacioRuntime.exe').exists())
            (target / 'old-runtime.txt').write_text('previous')
            module.copy_runtime(source, 'Windows64')
            self.assertFalse((target / 'old-runtime.txt').exists())
            backups = list(target.parent.glob('Windows64.previous-*/old-runtime.txt'))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(), 'previous')
            rename = Path.rename
            def fail_publish(path, destination):
                if path.parent.name.startswith('.runtime-copy-'):
                    raise OSError('publish failed')
                return rename(path, destination)
            with mock.patch.object(Path, 'rename', fail_publish):
                with self.assertRaises(OSError):
                    module.copy_runtime(source, 'Windows64')
            self.assertEqual((target / 'AnastacioRuntime.exe').read_bytes(), b'fixture')
            self.assertFalse(list(target.parent.glob('.runtime-copy-*')))


if __name__ == '__main__':
    unittest.main()
