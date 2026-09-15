import Range

cont = Range.logic.getCurrentController()
own = cont.owner
scene = Range.logic.getCurrentScene()
cam = scene.active_camera

sun = scene.objects["Lamp"]

def updateScreenPos():
    screenPos = cam.getScreenPosition(sun)
    own["sunX"] = screenPos[0]
    own["sunY"] = 1 - screenPos[1]
    dis = own.getDistanceTo(sun)
    ray = own.rayCast(sun, own, dis, "")
    if ray[0] == None:
        own["sundirect"] = 1.0
    else:
        own["sundirect"] = 0.0
    
    if cam.sphereInsideFrustum(sun.worldPosition, 15) != cam.OUTSIDE:
        owner["sundirect"] = 1.0
    else:
        owner["sundirect"] = 0.0