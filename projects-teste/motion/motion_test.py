import bge
from bge import logic, events
from mathutils import Euler


def main(cont):
    own = cont.owner
    scene = logic.getCurrentScene()
    m = logic.motion

    if logic.mouse.inputs[events.LEFTMOUSE].activated:
        print("[motion] calibrate:", m.calibrate())

    tx, ty = m.tilt
    own.worldOrientation = Euler((-ty * 0.4, tx * 0.4, 0.0)).to_matrix()
    ball = scene.objects["Bola"]
    ball.worldPosition = (tx * 2.6, ty * 1.6, 0.45)
    own.color = (0.2, 0.8, 0.3, 1.0) if m.available else (0.8, 0.2, 0.2, 1.0)

    own["frames"] += 1
    if own["frames"] % 60 == 0:
        print("[motion] available=%s tilt=(%.2f, %.2f) gravity=%s gyro=%s orientation=%s"
              % (m.available, tx, ty, tuple(round(v, 2) for v in m.gravity),
                 tuple(round(v, 2) for v in m.gyroscope), tuple(round(v) for v in m.orientation)))


main(logic.getCurrentController())
