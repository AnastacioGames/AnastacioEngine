from bge import logic


def main(cont):
    own = cont.owner
    joy = logic.joysticks[0]
    button_a = cont.sensors["BotaoA"]

    if button_a.triggered:
        print("[pad] sensor A %s" % ("down" if button_a.positive else "up"))
        if button_a.positive:
            own.worldPosition.z = 1.5

    if joy:
        lx, ly = joy.axisValues[0], joy.axisValues[1]
        own.worldPosition.x = max(-4.0, min(4.0, own.worldPosition.x + lx * 0.08))
        own.worldPosition.y = max(-3.0, min(3.0, own.worldPosition.y - ly * 0.08))
    if own.worldPosition.z > 0.5:
        own.worldPosition.z = max(0.5, own.worldPosition.z - 0.05)
    own.color = (0.2, 0.8, 0.3, 1.0) if joy else (0.8, 0.2, 0.2, 1.0)

    own["frames"] += 1
    if own["frames"] % 30 == 0:
        if joy:
            print("[pad] connected=True name=%s axes=%s buttons=%s"
                  % (joy.name, [round(v, 2) for v in joy.axisValues], sorted(joy.activeButtons)))
        else:
            print("[pad] connected=False")


main(logic.getCurrentController())
