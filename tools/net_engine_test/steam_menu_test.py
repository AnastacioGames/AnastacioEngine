"""Exercise the attached engine component and its Steam room flow in the real player."""
import os
import time
import traceback
from Range import logic
try:
    for i in range(4): logic.NextFrame()
    comp=next(c for c in logic.getCurrentScene().objects['Camera'].components if hasattr(c,'controller'))
    ctrl=comp.controller
    ctrl.config.update(app_id=480, steam_dll=os.environ['ANASTACIO_STEAM_DLL'], game_id='anastacio-component-smoke', build='test')
    assert ctrl.host('steam','Component smoke',4,False)
    deadline=time.monotonic()+20
    while ctrl.state not in ('lobby','idle') and time.monotonic()<deadline:
        logic.NextFrame(); time.sleep(.005)
    assert ctrl.state == 'lobby', (ctrl.state,ctrl.error)
    assert ctrl.lobby and comp.net.isServer
    comp.net.set_ready(True)
    assert comp.start_match()
    assert ctrl.state == 'playing'
    logic.NextFrame()
    comp.show()
    logic.NextFrame()
    assert comp.visible, 'game may explicitly open menu during a match'
    comp.hide()
    assert not comp.visible
    assert comp.return_to_lobby()
    assert ctrl.state == 'lobby' and not ctrl.ready
    assert not any(player.ready for player in comp.net.clients)
    logic.NextFrame()
    assert comp.visible
    assert not ctrl.error, ctrl.error
    # Lobby metadata and joinability publish asynchronously at Steam's backend.
    for i in range(120):
        logic.NextFrame(); time.sleep(.005)
    assert comp.net.steam.list_lobbies(ctrl.config['game_id'], ctrl.config['build'])
    deadline = time.monotonic() + 20
    while not any(room['lobby_id'] == ctrl.lobby for room in ctrl.rooms) and time.monotonic() < deadline:
        logic.NextFrame(); time.sleep(.005)
    assert any(room['lobby_id'] == ctrl.lobby for room in ctrl.rooms), 'returned lobby remains closed to search'
    assert ctrl.state == 'lobby'
    comp.net.set_ready(True)
    assert comp.start_match() and ctrl.state == 'playing'
    assert ctrl.return_to_lobby()
    ctrl.leave()
    assert not comp.net.isConnected and ctrl.state == 'idle'
    print('STEAMMENU runtime PASS (component callbacks; visual review pending)',flush=True)
except Exception:
    traceback.print_exc();print('STEAMMENU runtime FAIL',flush=True)
finally:
    logic.endGame();logic.NextFrame()
