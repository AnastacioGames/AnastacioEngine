import Range


def main():

    cont = Range.logic.getCurrentController()
    own = cont.owner

    sens = cont.sensors["mySensor"]
    actu = cont.actuators["myActuator"]

    if sens.positive:
        cont.activate(actu)
    else:
        cont.deactivate(actu)


main()
