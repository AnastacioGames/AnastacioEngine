"""TAA test in the real player (docs/plano-taa.md).

    TAA_OUT=/tmp/taa xvfb-run -a -s "-screen 0 1280x720x24" \
        AnastacioRuntime -w 960 540 -p tools/debug/teste_taa.py <scene>.range

Takes screenshots of the scene from its active camera:
  off.png        TAA and FXAA off (the camera is held still from here on)
  on_a.png/on_b  TAA on, still camera, two frames apart (should match: converged history)
  turn.png       TAA on while the camera turns slowly (no smear, no black)
  cut.png        right after a camera jump (history thrown away, no ghost of the old view)
Prints "TAATEST ..." lines and "TAATEST PASS|FAIL". Compare off.png and on_a.png zoomed on an edge;
RANGE_TAA_OFF=1 keeps the pass but drops the history (A/B: the edges must alias again).
"""

import os
import sys
import traceback

from Range import logic, render

OUT = os.environ.get("TAA_OUT", "/tmp/taa")
os.makedirs(OUT, exist_ok=True)
ok = True


def log(msg):
    print("TAATEST " + msg)
    sys.stdout.flush()


# The camera of a test scene may be animated: hold it on the pose below unless a step moves it.
hold = {}


def frames(n, step=None):
    for _ in range(n):
        if step:
            step()
        if "cam" in hold:
            hold["cam"].worldPosition = hold["pos"]
            hold["cam"].worldOrientation = hold["ori"]
        logic.NextFrame()


def shot(name):
    render.makeScreenshot(os.path.join(OUT, name + ".png"))
    # The screenshot is written at the end of a frame.
    frames(3)


try:
    scene = logic.getCurrentScene()
    cam = scene.active_camera
    fm = scene.filterManager
    log("scene=%s camera=%s taa=%s sharpen=%.2f fxaa=%s" % (scene.name, cam.name, fm.taaEnabled, fm.taaSharpen,
                                                           fm.fxaaEnabled))
    frames(30)
    # Silence the camera's own logic (a mouse look script in teste_efeitos) by moving it to an unused state.
    cam.state = 1 << 29
    hold.update(cam=cam, pos=cam.worldPosition.copy(), ori=cam.worldOrientation.copy())
    fm.fxaaEnabled = False
    fm.taaEnabled = False
    frames(5)
    shot("off")

    fm.taaEnabled = True
    if not fm.taaEnabled:
        ok = False
        log("taaEnabled did not turn on")
    frames(40)
    shot("on_a")
    frames(2)
    shot("on_b")

    def turn():
        cam.applyRotation((0.0, 0.0, 0.004), False)
        hold["ori"] = cam.worldOrientation.copy()
    frames(40, turn)
    render.makeScreenshot(os.path.join(OUT, "turn.png"))
    frames(1, turn)
    frames(2)

    hold["pos"] = cam.worldPosition + cam.worldOrientation.col[2] * 3.0
    cam.applyRotation((0.0, 0.0, 1.2), False)
    hold["ori"] = cam.worldOrientation.copy()
    frames(1)
    render.makeScreenshot(os.path.join(OUT, "cut.png"))
    frames(3)

    fm.taaSharpen = 0.0
    if abs(fm.taaSharpen) > 1e-6:
        ok = False
        log("taaSharpen not stored")
    frames(5)
except Exception:
    ok = False
    log("exception:\n" + traceback.format_exc())

log("PASS" if ok else "FAIL")
logic.endGame()
