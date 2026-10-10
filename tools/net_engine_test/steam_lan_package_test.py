import traceback
from Range import logic,network as net
try:
    for i in range(3):logic.NextFrame()
    assert not net.steam.status()['loaded']
    assert net.host(port=37779,max_players=2,websocket_port=0)
    for i in range(4):logic.NextFrame()
    net.disconnect()
    assert not net.steam.status()['loaded']
    print('STEAMEXPORT LAN runtime PASS without Steam DLL',flush=True)
except Exception:
    traceback.print_exc();print('STEAMEXPORT LAN runtime FAIL',flush=True)
finally:
    logic.endGame();logic.NextFrame()
