"""Smoke test for Ketsji Plano 1A, item 5 (custom mouse cursor lifetime).

Run from the repository root after building both executables:
  build/bin/RangeRuntime.exe -w 640 360 -d gpu \
    -p projects-teste/scripts/ketsji_cursor_lifetime_smoke.py \
    "projects-teste/Teste de nova luz e sombra.range"

Any scene works: this test does not touch rendering or shadows. It calls
render.setCustomMouse() repeatedly with different and identical image paths to
exercise KX_KetsjiEngine::SetCustomMouseCursor's cursor-replacement path
(FreeCustomMouseCursor freeing the previous CustomMouseCursor struct instead of
leaking it; the GPUTexture itself is never freed here, since it is cached and
owned by the source Image, not by the cursor) many times in a row without a
crash, then relies on
logic.endGame() to exit through the engine destructor, which now also frees
the last live cursor. There is no Python entry point that ever passes a null
cursor to the setter, so this test cannot directly exercise that guard; it
only confirms (via code review) that the fix compiles and that repeated
construct/replace/destroy cycles are crash-free.
"""

import os
import traceback

from Range import logic
from Range import render

REPO_ROOT = os.getcwd()
IMAGE_A = os.path.join(REPO_ROOT, "projects-teste", "smoke2.png")
IMAGE_B = os.path.join(REPO_ROOT, "projects-teste", "joystick_controller.png")


def run():
    assert os.path.isfile(IMAGE_A), "Missing test image: {}".format(IMAGE_A)
    assert os.path.isfile(IMAGE_B), "Missing test image: {}".format(IMAGE_B)

    # First assignment: m_CustomMouseCursor starts null, exercises the
    # no-previous-cursor branch of SetCustomMouseCursor.
    render.setCustomMouse(IMAGE_A)
    logic.NextFrame()

    # Repeated replacement: exercises FreeCustomMouseCursor on a live cursor,
    # alternating images and mipmap flag, several times in a row.
    for i in range(10):
        path = IMAGE_A if i % 2 == 0 else IMAGE_B
        render.setCustomMouse(path, bool(i % 2))
        stopped = logic.NextFrame()
        assert not stopped, "Engine stopped during cursor replacement (iteration {})".format(i)

    # Replacing with the same path back-to-back (old == new content, still a
    # distinct CustomMouseCursor/GPUTexture instance under the hood).
    render.setCustomMouse(IMAGE_A)
    render.setCustomMouse(IMAGE_A)
    logic.NextFrame()

    print("KETSJI_CURSOR_LIFETIME_SMOKE: PASS", flush=True)
    logic.endGame()
    logic.NextFrame()


try:
    run()
except Exception:
    print("KETSJI_CURSOR_LIFETIME_SMOKE: FAIL", flush=True)
    traceback.print_exc()
    logic.endGame()
    logic.NextFrame()
