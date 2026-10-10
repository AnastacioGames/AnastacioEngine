"""Open the approved RA3 scene in background; save a timed benchmark copy.

Arguments after --: destination.range. RA3_BENCH_MODE=rest|motion and
RA3_BENCH_LOG select the runtime experiment. Counts post_draw callbacks rather
than logic ticks; 3 seconds warmup followed by at least 10 seconds measured.
"""
import bpy
import sys

scene = bpy.context.scene
scene.game_settings.use_frame_rate = False
scene.game_settings.vsync = 'OFF'
scene.game_settings.resolution_x = 1280
scene.game_settings.resolution_y = 720
text = bpy.data.texts['ra3_reference.py']
text.write('''
import time, json
_reference_tick = tick
_bench = {}
def _measure():
    now = time.perf_counter()
    elapsed = now - _bench['start']
    if elapsed < 3.0:
        return
    if 'first' not in _bench:
        _bench.update(first=now, previous=now, intervals=[])
        return
    _bench['intervals'].append(now - _bench['previous'])
    _bench['previous'] = now
    seconds = now - _bench['first']
    if seconds >= 10.0 and not _bench.get('done'):
        _bench['done'] = True
        intervals = sorted(_bench['intervals'])
        result = dict(mode=os.environ.get('RA3_BENCH_MODE', 'rest'),
            seconds=seconds, frames=len(intervals), fps=len(intervals)/seconds,
            frame_ms=1000*seconds/len(intervals),
            p95_ms=1000*intervals[int(0.95*(len(intervals)-1))],
            resolution=[1280,720], vsync='OFF', logic_hz=bge.logic.getLogicTicRate(),
            render_hz=bge.logic.getRenderRate(),
            profiler=bool(os.environ.get('RANGE_PROFILE')), marker='END')
        with open(os.environ['RA3_BENCH_LOG'], 'w') as output:
            json.dump(result, output, indent=2)
        bge.logic.endGame()
def tick(cont):
    if not _bench:
        _bench['start'] = time.perf_counter()
        bge.logic.setLogicTicRate(10000)
        bge.logic.setRenderRate(10000)
        bge.logic.setMaxLogicFrame(1)
        bge.logic.getCurrentScene().post_draw.append(_measure)
    if state:
        state['moving'] = False
        state['t'] = (time.perf_counter()-_bench['start']
                      if os.environ.get('RA3_BENCH_MODE') == 'motion' else 0.0)
    _reference_tick(cont)
''')
bpy.ops.wm.save_as_mainfile(filepath=sys.argv[sys.argv.index('--') + 1], check_existing=False)
