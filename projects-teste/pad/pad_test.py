from bge import events, logic

KEYS = ("WKEY", "AKEY", "SKEY", "DKEY", "SPACEKEY", "RETKEY",
        "UPARROWKEY", "DOWNARROWKEY", "LEFTARROWKEY", "RIGHTARROWKEY")


def held(name):
    return logic.keyboard.inputs[getattr(events, name)].active


def main(cont):
    own = cont.owner
    joy = logic.joysticks[0]
    button_a = cont.sensors["BotaoA"]

    maps = logic.inputSystem.inputMaps
    mouse = logic.mouse
    if own["frames"] == 0:
        print("[pad] codes W=%d SPACE=%d UPARROW=%d LEFTMOUSE=%d"
              % (events.WKEY, events.SPACEKEY, events.UPARROWKEY, events.LEFTMOUSE))
        print("[pad] maps %s" % sorted(maps))
        mouse.visible = False
    else:
        dx, dy = mouse.deltaPosition
        own["look_x"] += dx
        own["look_y"] += dy
    mouse.reCenter()
    left = mouse.inputs[events.LEFTMOUSE]
    if left.activated:
        print("[pad] mouse LEFT down")
    if left.released:
        print("[pad] mouse LEFT up")
    jump = maps.get("Pad", {}).get("Pular")
    if jump is not None and jump.activated:
        print("[pad] map Pular down")
    for name in KEYS:
        ev = logic.keyboard.inputs[getattr(events, name)]
        if ev.activated:
            print("[pad] key %s down" % name[:-3])
        if ev.released:
            print("[pad] key %s up" % name[:-3])

    if button_a.triggered:
        print("[pad] sensor A %s" % ("down" if button_a.positive else "up"))
        if button_a.positive:
            own.worldPosition.z = 1.5
    if logic.keyboard.inputs[events.SPACEKEY].activated:
        own.worldPosition.z = 1.5

    lx = (held("DKEY") or held("RIGHTARROWKEY")) - (held("AKEY") or held("LEFTARROWKEY"))
    ly = (held("SKEY") or held("DOWNARROWKEY")) - (held("WKEY") or held("UPARROWKEY"))
    if joy:
        lx, ly = lx or joy.axisValues[0], ly or joy.axisValues[1]
    if lx or ly:
        own.worldPosition.x = max(-4.0, min(4.0, own.worldPosition.x + lx * 0.08))
        own.worldPosition.y = max(-3.0, min(3.0, own.worldPosition.y - ly * 0.08))
    if own.worldPosition.z > 0.5:
        own.worldPosition.z = max(0.5, own.worldPosition.z - 0.05)
    own.color = (0.2, 0.8, 0.3, 1.0) if joy else (0.8, 0.2, 0.2, 1.0)

    own["frames"] += 1
    if own["frames"] % 30 == 0:
        if own["look_x"] or own["look_y"]:
            print("[pad] look dx=%.3f dy=%.3f" % (own["look_x"], own["look_y"]))
            own["look_x"] = own["look_y"] = 0.0
        if joy:
            print("[pad] connected=True name=%s axes=%s buttons=%s"
                  % (joy.name, [round(v, 2) for v in joy.axisValues], sorted(joy.activeButtons)))
        else:
            print("[pad] connected=False")


main(logic.getCurrentController())
