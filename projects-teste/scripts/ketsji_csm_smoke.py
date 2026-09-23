"""Bounded runtime smoke test for the first Ketsji modernization correction.

Run from the repository root after building both executables:
  build/bin/RangeRuntime.exe -w 640 360 -d gpu \
    -p projects-teste/scripts/ketsji_csm_smoke.py \
    "projects-teste/Teste de nova luz e sombra.range"

Use a scene with CSM enabled and both static and dynamic shadow casters.
The script renders, toggles rendering/shadows, and restarts once in the same
process. It only changes runtime state; it never saves the scene or globalDict.
Require the final PASS marker as well as exit code 0: the launcher may swallow
Python exceptions. This tests execution, not image quality or the private CSM
counter's exact value; those still need visual/debugger verification.
"""

import time
import traceback

from Range import logic


def run():
    cycle_key = "_ketsji_csm_smoke_cycle"
    cycle = logic.globalDict.get(cycle_key, 0)
    assert cycle in (0, 1), "Unexpected restart count"
    scene = logic.getCurrentScene()
    assert scene.active_camera is not None, "A camera is required"
    assert len(scene.lights) > 0, "A CSM test light is required"

    draws = [0]

    def post_draw():
        draws[0] += 1

    scene.post_draw.append(post_draw)
    for light in scene.lights:
        light.staticShadow = True

    def step():
        stopped = logic.NextFrame()
        assert not stopped, "Engine stopped before completing the test"

    def render_draws(count):
        target = draws[0] + count
        deadline = time.monotonic() + 20.0
        while draws[0] < target:
            assert time.monotonic() < deadline, "Timed out waiting for scene draws"
            step()

    logic.setRender(False)
    for _ in range(20):
        step()
        time.sleep(0.005)
    assert draws[0] == 0, "Scene drew while rendering was disabled"

    logic.setRender(True)
    logic.setMaxPhysicsFrame(1)  # Legacy flag currently controls shadow rendering.
    render_draws(30)
    logic.setMaxPhysicsFrame(0)
    render_draws(10)
    logic.setMaxPhysicsFrame(1)
    render_draws(30)
    scene.post_draw.remove(post_draw)
    print("KETSJI_CSM_SMOKE: cycle={} draws={} PASS".format(cycle, draws[0]), flush=True)

    if cycle == 0:
        logic.globalDict[cycle_key] = 1
        logic.restartGame()
    else:
        del logic.globalDict[cycle_key]
        logic.endGame()
    stopped = logic.NextFrame()
    assert stopped, "Engine did not honor the exit/restart request"
    if cycle == 1:
        print("KETSJI_CSM_SMOKE: render/toggle/restart PASS", flush=True)


try:
    run()
except Exception:
    print("KETSJI_CSM_SMOKE: FAIL", flush=True)
    traceback.print_exc()
    logic.endGame()
    logic.NextFrame()
