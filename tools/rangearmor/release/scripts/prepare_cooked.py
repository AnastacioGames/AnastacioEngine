"""Prepare the protected snapshot with the local host runtime before packaging."""

import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path
from common import resolve_runtime


def prepare(data):
    project = data['CurPath'].resolve()
    data_dir = (project / 'data').resolve()
    main = (data_dir / data['MainFile']).resolve()
    if data_dir not in main.parents or not main.is_file():
        raise RuntimeError('MainFile must exist inside data/: ' + str(main))
    host = 'Windows64' if platform.system() == 'Windows' else 'Linux64'
    name = 'AnastacioRuntime.exe' if host == 'Windows64' else 'RangeRuntime'
    configured = os.environ.get('RANGEARMOR_COOK_RUNTIME')
    candidates = [Path(configured)] if configured else []
    candidates += [Path(__file__).resolve().parents[3] / name,
                   Path(data['EngineExecutables'].get(host, project / 'engine' / host / name))]
    runtime = next((resolve_runtime(p).resolve() for p in candidates if resolve_runtime(p).is_file()), None)
    if runtime is None:
        raise RuntimeError('Host runtime needed to cook; set RANGEARMOR_COOK_RUNTIME')
    target = main.with_suffix('.cooked')
    with tempfile.TemporaryDirectory(prefix='rangearmor_cook_') as work:
        fresh = Path(work) / 'game.cooked'
        env = dict(os.environ, ANASTACIO_COOK=str(fresh))
        print('> Cooking protected snapshot:', main, flush=True)
        result = subprocess.run([str(runtime), '-w', '320', '180', str(main)],
                                cwd=str(data_dir), env=env, capture_output=True,
                                text=True, errors='replace', timeout=600)
        if result.returncode:
            raise RuntimeError('Cook failed (%d): %s' % (result.returncode, result.stdout + result.stderr))
        if fresh.is_file():
            with fresh.open('rb') as stream:
                if stream.read(8) != b'ANACOOK2':
                    raise RuntimeError('Unknown cooked format; export stopped')
            staged = target.with_suffix('.cooked.export-tmp')
            try:
                shutil.copy2(str(fresh), str(staged))
                os.replace(str(staged), str(target))
            finally:
                if staged.exists():
                    staged.unlink()
            print('> Prepared cooked companion:', target.name)
        elif target.exists():
            target.unlink()
            print('> Empty cook: removed previous companion')
