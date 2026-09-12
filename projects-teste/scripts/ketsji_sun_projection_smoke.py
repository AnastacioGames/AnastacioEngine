"""Smoke test for Ketsji Plano 1A, item 4 (safe Sun projection).

Run from the repository root after building both executables:
  build/bin/RangeRuntime.exe -w 640 360 -d gpu \
      -p projects-teste/scripts/ketsji_sun_projection_smoke.py \
      "projects-teste/ketsji_sun_projection_smoke.range"

The dedicated scene (built by _setup_sun_projection_scene.py from
"Teste de nova luz e sombra.range") has its worldSun assigned, which is
required for KX_KetsjiEngine::PostRenderScene to enter the sun-projection
block at all. This test enables Light Scattering at runtime, then points the
active camera directly at the sun, directly away from it, and along two
exact perpendiculars to it -- the three angles PostRenderScene's screenPos.w
guard exists for (sun in front, sun behind camera, sun parallel to the view
plane). It only asserts that the engine keeps running without an exception
or an early stop; the shader uniforms fed by sunPos are not readable from
Python, so this does not confirm pixel output, only execution safety.
"""

import traceback

import mathutils
from Range import logic


def face_direction(obj, direction):
    obj.alignAxisToVect(-direction, 2, 1.0)


def run():
    scene = logic.getCurrentScene()
    cam = scene.active_camera
    assert cam is not None, "A camera is required"

    sun = scene.worldSun
    assert sun is not None, "Scene must have worldSun assigned (see _setup_sun_projection_scene.py)"

    scene.filterManager.changeLightScatterValues(1, 32, 0.15, 0.75, 0.2)

    sun_z = sun.worldOrientation.col[2]
    sun_travel_dir = mathutils.Vector((-sun_z.x, -sun_z.y, -sun_z.z)).normalized()
    apparent_sun_dir = -sun_travel_dir

    up_hint = mathutils.Vector((0.0, 0.0, 1.0))
    if abs(apparent_sun_dir.dot(up_hint)) > 0.99:
        up_hint = mathutils.Vector((0.0, 1.0, 0.0))
    perp1 = apparent_sun_dir.cross(up_hint).normalized()
    perp2 = apparent_sun_dir.cross(perp1).normalized()

    test_directions = [
        ("facing_sun", apparent_sun_dir),
        ("facing_away_from_sun", -apparent_sun_dir),
        ("perpendicular_1", perp1),
        ("perpendicular_2", perp2),
    ]

    def step():
        stopped = logic.NextFrame()
        assert not stopped, "Engine stopped before completing the test"

    for label, direction in test_directions:
        face_direction(cam, direction)
        for _ in range(5):
            step()
        print("KETSJI_SUN_PROJECTION_SMOKE: {} ok".format(label), flush=True)

    # Recovery check: a normal, well-conditioned angle still renders fine afterwards.
    face_direction(cam, apparent_sun_dir)
    for _ in range(5):
        step()

    print("KETSJI_SUN_PROJECTION_SMOKE: PASS", flush=True)
    logic.endGame()
    logic.NextFrame()


try:
    run()
except Exception:
    print("KETSJI_SUN_PROJECTION_SMOKE: FAIL", flush=True)
    traceback.print_exc()
    logic.endGame()
    logic.NextFrame()
