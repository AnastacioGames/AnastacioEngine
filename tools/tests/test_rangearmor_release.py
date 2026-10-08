"""Safety checks for RangeArmor release staging and cooking failures."""
import importlib.util
import pathlib
import sys
import tempfile
import unittest
import zipfile
import subprocess
import json
from unittest import mock

SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / 'rangearmor/release/scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('armor_release', SCRIPTS / 'build_release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseSafety(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        for name in ['data', 'launcher', 'engine/Windows64', 'release']:
            (self.root / name).mkdir(parents=True)
        for name in ['data/Game.rasec', 'data/Game.cooked', 'launcher/Launcher.exe',
                     'launcher/config.json', 'engine/Windows64/RangeRuntime.exe']:
            (self.root / name).write_bytes(b'test fixture')
        self.data = {'CurPath': self.root, 'GameName': 'Game', 'Version': '1',
                     'ProjectFile': self.root / 'launcher/config.json', 'MainFile': 'Game.rasec',
                     'EngineExecutables': {'Windows64': self.root / 'engine/Windows64/RangeRuntime.exe'}}
        self.destination = self.root / 'release/Game-1-Windows64'
        self.destination.mkdir()
        (self.destination / 'previous.txt').write_text('known good')

    def test_failed_cook_preserves_previous_delivery(self):
        with mock.patch.object(release.prepare_cooked, 'prepare', side_effect=RuntimeError('cook failed')):
            with self.assertRaises(RuntimeError):
                release.build(self.data, {'--target': 'All', '--compress': True})
        self.assertEqual((self.destination / 'previous.txt').read_text(), 'known good')
        self.assertFalse(list((self.root / 'release').glob('*.zip')))

    def test_legacy_config_exports_new_runtime_without_changing_author_config(self):
        old = self.root / 'engine/Windows64/RangeRuntime.exe'
        old.rename(old.with_name('AnastacioRuntime.exe'))
        config_path = self.root / 'launcher/config.json'
        config = {'GameName': 'Game', 'Version': '1', 'MainFile': 'Game.rasec',
                  'DataSource': './data', 'EngineWindows64': './engine/Windows64/RangeRuntime.exe'}
        original = json.dumps(config)
        config_path.write_text(original, encoding='utf-8')
        data = release.common.getProjectData(str(config_path))
        release.build(data, {'--target': 'Windows64', '--compress': True, '--no-cook': True})
        delivered = json.loads((self.destination / 'launcher/config.json').read_text(encoding='utf-8'))
        self.assertEqual(delivered['EngineWindows64'], './engine/Windows64/AnastacioRuntime.exe')
        self.assertTrue((self.destination / 'engine/Windows64/AnastacioRuntime.exe').is_file())
        self.assertFalse((self.destination / 'engine/Windows64/RangeRuntime.exe').exists())
        self.assertEqual(config_path.read_text(encoding='utf-8'), original)

    def test_new_config_accepts_legacy_installation_and_preserves_custom_paths(self):
        runtime = self.root / 'engine/Windows64/RangeRuntime.exe'
        configured = runtime.with_name('AnastacioRuntime.exe')
        self.assertEqual(release.common.resolve_runtime(configured), runtime)
        self.assertEqual(release.common.resolve_runtime(runtime.with_name('CustomRuntime.exe')),
                         runtime.with_name('CustomRuntime.exe'))
        configured.write_bytes(b'new runtime')
        self.assertEqual(release.common.resolve_runtime(configured), configured)
        self.assertEqual(release.common.resolve_runtime(runtime), runtime)

    def test_success_packages_companion_and_preserves_previous(self):
        with mock.patch.object(release.prepare_cooked, 'prepare'):
            release.build(self.data, {'--target': 'All', '--compress': True})
        with zipfile.ZipFile(self.root / 'release/Game-1-Windows64.zip') as archive:
            self.assertIn('Game-1-Windows64/data/Game.cooked', archive.namelist())
            self.assertTrue(all('\\' not in name for name in archive.namelist()))
        backups = list((self.root / 'release').glob('*.previous-*/Game-1-Windows64/previous.txt'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), 'known good')

    def test_invalid_version_cannot_escape_release(self):
        self.data['Version'] = '../../escape'
        with self.assertRaises(RuntimeError):
            release.build(self.data, {'--target': 'All'})
        self.assertTrue((self.destination / 'previous.txt').exists())

    def test_failed_runtime_preserves_previous_cache(self):
        with mock.patch.object(release.prepare_cooked.subprocess, 'run') as run:
            run.return_value = mock.Mock(returncode=5, stdout='failed', stderr='')
            with self.assertRaises(RuntimeError):
                release.prepare_cooked.prepare(self.data)
        self.assertEqual((self.root / 'data/Game.cooked').read_bytes(), b'test fixture')

    def test_timeout_preserves_previous_cache(self):
        with mock.patch.object(release.prepare_cooked.subprocess, 'run',
                               side_effect=subprocess.TimeoutExpired('runtime', 600)):
            with self.assertRaises(subprocess.TimeoutExpired):
                release.prepare_cooked.prepare(self.data)
        self.assertEqual((self.root / 'data/Game.cooked').read_bytes(), b'test fixture')

    def test_successful_empty_cook_removes_previous_cache(self):
        with mock.patch.object(release.prepare_cooked.subprocess, 'run') as run:
            run.return_value = mock.Mock(returncode=0)
            release.prepare_cooked.prepare(self.data)
        self.assertFalse((self.root / 'data/Game.cooked').exists())

    def test_export_without_cooking_keeps_source_cache_and_omits_packaged_cache(self):
        with mock.patch.object(release.prepare_cooked, 'prepare') as prepare:
            release.build(self.data, {'--target': 'All', '--no-cook': True})
        prepare.assert_not_called()
        self.assertFalse((self.destination / 'data/Game.cooked').exists())
        self.assertEqual((self.root / 'data/Game.cooked').read_bytes(), b'test fixture')


if __name__ == '__main__':
    unittest.main()
