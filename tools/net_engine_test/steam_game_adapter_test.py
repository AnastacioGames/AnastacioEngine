import time
import traceback
from Range import logic,network as net
try:
    logic.globalDict['_SETTINGS_LOADED']=True
    for i in range(4):logic.NextFrame()
    steam_component=logic.globalDict['Steam_Component']
    assert steam_component.initialized
    assert steam_component.steam.GetCurrentGameLanguage()
    controller=logic.globalDict['_anastacio_network_controller']
    assert controller.host('steam','Rolima adapter smoke',4,True)
    deadline=time.monotonic()+20
    while controller.state not in ('lobby','idle') and time.monotonic()<deadline:
        logic.NextFrame();time.sleep(.005)
    assert controller.state=='lobby',controller.error
    manager=logic.globalDict['NetworkManager']
    assert manager.get_address()==str(controller.lobby)
    net.set_ready(True)
    manager.start_online_race('Pista_1')
    for i in range(20):logic.NextFrame()
    assert 'Pista_1' in [scene.name for scene in logic.getSceneList()]
    assert net.isServer
    # The minimal fixture replaces the camera with its copied components.
    # Resolve the live game manager after transition, not the destroyed proxy.
    manager = logic.globalDict['NetworkManager']
    assert manager.return_to_lobby('0_SCN_System')
    deadline = time.monotonic() + 15
    while controller.state != 'lobby' and time.monotonic() < deadline:
        logic.NextFrame(); time.sleep(.005)
    assert controller.state == 'lobby', controller.error
    assert '0_SCN_System' in [scene.name for scene in logic.getSceneList()]
    assert net.isServer and not any(player.ready for player in net.clients)
    print('STEAMGAME runtime PASS (adapters and scene transition; vehicles untested)',flush=True)
except Exception:
    traceback.print_exc();print('STEAMGAME runtime FAIL',flush=True)
finally:
    net.disconnect();logic.endGame();logic.NextFrame()
