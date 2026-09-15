import Range


def test():

    cont = Range.logic.getCurrentController()
    own = cont.owner
    scene = Range.logic.getCurrentScene()
    message = Range.logic.sendMessage

    sensor = cont.sensors['mySensor']
    actuator = cont.actuators['myActuator']
    
    #_______________________________________#

    if sensor.positive:
        cont.activate(actuator)
    else:
        cont.deactivate(actuator)
        
           
#_______________________________________________#
#_______________________________________________#