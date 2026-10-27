"""Run the generated ANI-01 scenes without windows and validate recorded game data."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
folder = Path(sys.argv[1]).resolve()
exe = ROOT / 'build/bin/AnastacioRuntime.exe'
summary = {'runtime_sha256': hashlib.sha256(exe.read_bytes()).hexdigest(), 'cases': {}}

for case in ('normal', 'restricted', 'half', 'slow_rate'):
    result = folder / ('result_anim_' + case + '.json')
    if result.exists():
        result.unlink()
    run = subprocess.run([str(exe), '--server', str(folder / ('anim_' + case + '.range'))],
                         capture_output=True, text=True, timeout=25)
    (folder / ('runtime_' + case + '.log')).write_text(run.stdout + run.stderr, encoding='utf-8')
    assert run.returncode == 0, (case, run.returncode)
    data = json.loads(result.read_text())
    assert 'error' not in data, (case, data.get('error'))
    rows, events = data['rows'], data['events']
    assert len(rows) == 56
    frames = [row['frame'] for row in rows]
    assert rows[-1]['bone_frame'] > 1
    triggers = [int(event['arg']) for event in events]
    assert len(triggers) == len(set(triggers)) and triggers, (case, triggers)
    assert triggers == list(range(2, max(triggers) + 1)), (case, triggers)
    zeros = sum(abs(b - a) < 1e-6 for a, b in zip(frames[2:], frames[3:]))
    if case == 'normal':
        assert triggers == list(range(2, 56))
        for index in (14, 15, 16, 17, 32, 33, 34, 35):
            before, after = rows[index - 1], rows[index]
            assert abs(after['frame'] - before['frame'] - 1) < 1e-5
            assert abs(after['bone_frame'] - before['bone_frame'] - 1) < 1e-5
            distance = sum((a - b) ** 2 for a, b in zip(after['bone_child'], before['bone_child'])) ** 0.5
            assert abs(distance - 0.01) < 1e-5, (index, distance)
        for event in events:
            assert abs(event['frame'] - rows[event['tick']]['frame']) < 1e-5
    else:
        # Existing global, per-scene and per-object rate limits still skip pose steps.
        assert zeros > 0, (case, 'rate restriction ignored')
    summary['cases'][case] = {'rows': len(rows), 'events': len(events), 'held_pose_pairs': zeros}
    print(case, summary['cases'][case])

(folder / 'validation-summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
print('ANI_PLAYER_ALL_CASES_PASSED')
