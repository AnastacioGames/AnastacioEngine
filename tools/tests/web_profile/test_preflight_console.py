"""Execute the generated JavaScript console fallback, including successful load logs."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import unittest


@unittest.skipUnless(shutil.which('node'), 'Node is required to execute the page diagnostic code')
class ConsoleShaderTests(unittest.TestCase):
    def test_success_logs_and_actual_errors(self):
        path = Path(__file__).resolve().parents[2] / 'web' / 'package-web.py'
        spec = importlib.util.spec_from_file_location('package_web_console_test', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        page = module.INDEX_TEMPLATE
        code = page[page.index('  var pf ='):page.index('  function pfProbeGL()')]
        code += '''
const assert = require('node:assert/strict');
pfLine('[Load] scene "Scene": shaders 1026ms (compiled 2 1011ms, reused 0)');
pfLine('Shader compilation completed successfully');
assert.equal(pf.shaders.length, 0);
pfLine('Fragment shader compilation failed');
pfLine('ERROR: 0:3: invalid expression');
assert.equal(pf.shaders.length, 1);
assert.equal(pf.shaders[0].stage, 'fragment');
assert.match(pf.shaders[0].log, /invalid expression/);
pfDiagnostic({version: 1, category: 'shader', severity: 'error',
              origin: 'Material', stage: 'link', log: 'link diagnostic'});
assert.equal(pf.shaders.length, 2);
assert.equal(pf.shaders[1].structured, true);
'''
        result = subprocess.run([shutil.which('node'), '-e', code], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
