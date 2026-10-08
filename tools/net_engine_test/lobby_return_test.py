"""Two native processes: start twice, return/readiness, then rejoin after a match."""
import os
import time
import traceback
from Range import logic, network as net
role = os.environ['NET_ROLE']
port = int(os.environ['NET_PORT'])
events = []
net.on_connect(lambda client: events.append(('connect', client)))
net.on_start(lambda: events.append(('start',)))
net.on_lobby(lambda: events.append(('lobby',)))
net.on_player_join(lambda client, name: events.append(('join', client)))
net.on_reject(lambda reason, detail: events.append(('reject', reason)))
try:
    if role == 'server':
        assert net.host(port=port, max_players=3, websocket_port=0)
    else:
        assert net.join('127.0.0.1:' + str(port))
    deadline = time.monotonic() + (8 if role == 'server' else 7)
    phase = 0
    started_at = 0
    sent_ready = -1
    rejoined = False
    while time.monotonic() < deadline:
        starts = sum(event[0] == 'start' for event in events)
        returns = sum(event[0] == 'lobby' for event in events)
        if role == 'server':
            if phase < 2 and not started_at and any(player.ready and not player.isHost for player in net.clients):
                assert net.start_game()
                started_at = time.monotonic()
            if started_at and time.monotonic() - started_at > .3:
                assert net.return_to_lobby()
                assert not any(player.ready for player in net.clients)
                phase += 1
                started_at = 0
        elif net.isConnected:
            if returns >= 2 and not rejoined:
                net.disconnect()
                assert net.join('127.0.0.1:' + str(port))
                rejoined = True
            elif returns < 2 and sent_ready != returns:
                assert not net.return_to_lobby(), 'client may not end the match'
                net.set_ready(True)
                sent_ready = returns
        logic.NextFrame()
        time.sleep(.005)
    assert sum(event[0] == 'start' for event in events) == 2, events
    assert sum(event[0] == 'lobby' for event in events) == 2, events
    assert not any(event[0] == 'reject' for event in events), events
    if role == 'server': assert sum(event[0] == 'join' for event in events) >= 2, events
    else: assert rejoined and net.isConnected, events
    print('LOBBYRETURN ' + role + ' PASS', flush=True)
except Exception:
    traceback.print_exc()
    print('LOBBYRETURN ' + role + ' FAIL', flush=True)
finally:
    net.disconnect()
    logic.endGame()
    logic.NextFrame()
