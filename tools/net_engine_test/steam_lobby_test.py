"""Online Steam lobby smoke test in a minimal runtime scene. Uses development AppID 480."""
import os
import time
import traceback
from Range import logic, network as net
steam = net.steam

def check(ok, text):
    if not ok: raise AssertionError(text)
    print('STEAMLOBBY ok ' + text, flush=True)

def wait_events(kind, seconds=20):
    events = []
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        logic.NextFrame()
        for event in steam.poll_events():
            events.append(event)
            if event['type'] == 6: raise RuntimeError(event['detail'])
            if event['type'] == kind: return events
        time.sleep(.005)
    raise AssertionError('callback timeout ' + str(kind))

try:
    steam.initialize(os.environ['ANASTACIO_STEAM_DLL'], 480)
    if os.environ.get('ANASTACIO_EXPECT_INVITE'):
        expected = int(os.environ['ANASTACIO_EXPECT_INVITE'])
        check(any(event['type'] == 5 and event['lobby_id'] == expected for event in steam.poll_events()),
              'cold launch invite read from process argv')
    check(steam.force_relay(True), 'forced relay configuration before transport')
    check(steam.language() != '', 'shared Steam language available')
    game_id = 'anastacio-smoke-' + str(os.getpid())
    try:
        steam.create_lobby('Invalid virtual port', port=0, game_id=game_id, build='test')
    except RuntimeError:
        pass
    else:
        raise AssertionError('zero lobby port accepted despite native zero-as-scene-default contract')
    check(steam.create_lobby('Anastacio SDK smoke', capacity=4, friends_only=False, game_id=game_id, build='test'), 'create requested')
    created = wait_events(1)[-1]
    check(created['lobby_id'] > 0 and created['host_id'] == steam.status()['steam_id'], 'lobby owner and identity exact')
    check(created['capacity'] == 4 and created['port'] == 7777, 'lobby metadata')
    check(net.host(port=7777, max_players=3, room_name='Steam test', transport='steam', websocket_port=0), 'native host listens through SDK')
    try: steam.shutdown()
    except RuntimeError: pass
    else: raise AssertionError('unload accepted during native session')
    check(net.isServer and net.isConnected, 'native host session active')
    check(steam.connection_routes() == [], 'no relay claimed without a remote connection')
    net.set_ready(True)
    check(net.start_game(), 'native ready/start state')
    steam.set_joinable(False)
    steam.set_joinable(True)
    net.disconnect()
    check(not net.isConnected, 'native Steam host disconnects')
    # Give lobby metadata a chance to propagate before querying its public list.
    for i in range(60): logic.NextFrame()
    check(steam.list_lobbies(game_id, 'test'), 'list requested with game/build/protocol filters')
    listed = wait_events(4)
    own = [entry for entry in listed if entry['type'] == 3 and entry['lobby_id'] == created['lobby_id']]
    check(bool(own), 'public lobby appears in filtered results')
    steam.leave_lobby()
    check(steam.create_lobby('Cancel smoke', capacity=2, game_id=game_id, build='test'), 'cancelable request')
    steam.leave_lobby()
    check(steam.create_lobby('Retry without waiting', capacity=2, game_id=game_id, build='test'),
          'new create accepted immediately after cancellation')
    retry = wait_events(1)[-1]
    check(retry['lobby_id'] > 0, 'retry callback belongs to new request')
    steam.leave_lobby()
    for i in range(120):
        logic.NextFrame(); time.sleep(.005)
    check(not any(event['type'] == 1 for event in steam.poll_events()), 'canceled request cannot emit created lobby')
    steam.shutdown()
    print('STEAMLOBBY PASS', flush=True)
except Exception:
    traceback.print_exc()
    print('STEAMLOBBY FAIL', flush=True)
finally:
    net.disconnect()
    if steam.status()['ready']: steam.leave_lobby()
    steam.shutdown()
    logic.endGame(); logic.NextFrame()
