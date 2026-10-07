"""Host-Python runner for the isolated windowed atlas tests (Windows)."""
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
startup = subprocess.STARTUPINFO()
startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
startup.wShowWindow = subprocess.SW_HIDE
failures = []
for case in ('cancel', 'cancel-late', 'error', 'success'):
    log = root / 'debug-logs' / ('material-atlas-modal-' + case + '.log')
    errors = log.with_name(log.stem + '-error.log')
    with log.open('w') as output, errors.open('w') as err:
        process = subprocess.Popen([
            str(root / 'build/bin/RangeEngine.exe'), '--factory-startup',
            '--python-exit-code', '1', '--python',
            str(root / 'tools/test_material_atlas_modal.py'), '--', '--case', case,
        ], cwd=root, stdout=output, stderr=err, startupinfo=startup)
        try:
            result = process.wait(timeout=60)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            result = 'TIMEOUT'
    passed = result == 0 and ('ANASTACIO_ATLAS_MODAL_PASS ' + case) in log.read_text(errors='replace')
    print('{}: exit={}, passed={}'.format(case, result, passed), flush=True)
    if not passed:
        failures.append(case)
        print(errors.read_text(errors='replace')[-2000:], flush=True)
sys.exit(bool(failures))
