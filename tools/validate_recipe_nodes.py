"""Generate reviewed copies and check real player logs (Windows, no screenshots).

Run: python tools/validate_recipe_nodes.py
The engine needs to be already built. Each player exits after 120 logic ticks.
This verifies shader compilation/execution, not visual quality.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / 'demos' / 'revisados'
EDITOR = ROOT / 'build' / 'bin' / 'AnastacioEngine.exe'
PLAYER = ROOT / 'build' / 'bin' / 'AnastacioRuntime.exe'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    originals = {p: digest(p) for p in (ROOT / 'demos').glob('*.range')}
    run = subprocess.run([str(EDITOR), '-b', '--python-exit-code', '1', '--python',
                          str(ROOT / 'tools' / 'review_recipe_nodes.py'), '--', '--validate-runtime'],
                         cwd=str(ROOT), capture_output=True, timeout=120)
    if run.returncode:
        raise RuntimeError(run.stdout.decode('utf-8', errors='replace') +
                           run.stderr.decode('utf-8', errors='replace'))
    report = json.loads((DEST / 'validation.json').read_text(encoding='utf-8'))
    logdir = Path(tempfile.mkdtemp(prefix='anastacio_recipe_logs_'))
    print('Logs:', logdir, flush=True)
    failures = []
    for item in report:
        work = logdir / item['demo']
        work.mkdir()
        env = dict(os.environ, TEMP=str(work), TMP=str(work), RANGE_NO_CRASH_DIALOG='1')
        runtime = Path(item.pop('runtime_file'))
        try:
            player = subprocess.run([str(PLAYER), '-w', '640', '360', str(runtime)],
                                    cwd=str(ROOT / 'build' / 'bin'), env=env,
                                    capture_output=True, timeout=60)
            logpath = work / 'range_runtime.log.txt'
            log = logpath.read_text(encoding='utf-8', errors='replace') if logpath.exists() else ''
            (work / 'stdout.txt').write_bytes(player.stdout + player.stderr)
            errors = re.findall(r'^.*(?:Traceback|Error:|ERROR|CM_Error|shader.*failed|'
                                r'not supported in the game|EXCEPTION_ACCESS_VIOLATION).*$',
                                log, flags=re.MULTILINE | re.IGNORECASE)
            if item['demo'] == 'toon':
                errors += re.findall(r'^.*no (?:vertices|primitives) for material.*$', log,
                                     flags=re.MULTILINE)
            marker = 'ANASTACIO_REVIEW_RUNTIME_PASS: ' + item['demo']
            ok = player.returncode == 0 and marker in log and not errors
            item['runtime'] = 'PASS' if ok else 'FAIL'
            item['errors'] = errors
            item['exit_code'] = player.returncode
            item['runtime_log'] = str(logpath)
            if not ok:
                failures.append(item['demo'])
            print(item['demo'] + ': ' + item['runtime'], flush=True)
        except subprocess.TimeoutExpired:
            item['runtime'] = 'TIMEOUT'
            failures.append(item['demo'])
            print(item['demo'] + ': TIMEOUT', flush=True)
        finally:
            runtime.unlink(missing_ok=True)
    assert all(digest(p) == value for p, value in originals.items()), 'Original modificado!'
    (DEST / 'validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    if failures:
        raise RuntimeError('Falhas no player: ' + ', '.join(failures) + '; logs: ' + str(logdir))
    print('PASS: 11 demos; originais preservados; nenhuma falha de shader/Python.', flush=True)


if __name__ == '__main__':
    main()
