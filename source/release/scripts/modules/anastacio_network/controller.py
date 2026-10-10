"""Native session and optional Steam lobby state; no ImGui or game rules."""
import os
import time

class AnastacioNetworkController:
    def __init__(self, net, config, expand_path):
        self.net = net
        self.config = dict(config)
        self.expand_path = expand_path
        self.state = 'idle'
        self.error = ''
        self.mode = 'lan'
        self.lobby = 0
        self.rooms = []
        self.chat = []
        self.ready = False
        self.deadline = 0
        self.invite = 0
        self._return_scene = None
        self.lobby_scene = None  # Session scene at host time; the match returns here.
        self._hooks = []
        for name, callback in [('on_connect', self._connected), ('on_disconnect', self._disconnected),
                               ('on_reject', self._rejected), ('on_chat', self._chat), ('on_start', self._started),
                               ('on_lobby', self._returned), ('on_scene', self._scene_loaded)]:
            getattr(net, name)(callback)
            self._hooks.append((name, callback))

    def _connected(self, client):
        self.state = 'lobby'
        self.deadline = 0
    def _disconnected(self, reason, detail):
        self.error = detail or 'Conexão encerrada'
        self.state = 'idle'
        self.deadline = 0
        self._return_scene = None
        self._leave_steam()
    def _rejected(self, reason, detail):
        self._disconnected(reason, detail)
    def _chat(self, client, text):
        self.chat.append((client, text))
        self.chat = self.chat[-100:]
    def _started(self):
        self.state = 'playing'
        if self.lobby and self.net.isServer:
            self._call(self.net.steam.set_joinable, False)

    def _returned(self):
        self.state = 'lobby'
        self.ready = False
        self.deadline = 0
        self._return_scene = None
        if self.lobby and self.net.isServer:
            self._call(self.net.steam.set_joinable, True)

    def _scene_loaded(self, name):
        if name == self._return_scene and self.net.isServer:
            self._return_scene = None
            if not self._call(self.net.return_to_lobby):
                self.leave()
                self.error = self.error or 'Não foi possível retornar à sala'

    def return_to_lobby(self, scene=None):
        """Host ends the match; optionally reopen only after its menu scene loads."""
        if not self.net.isServer or not self.net.isConnected:
            return False
        if scene:
            self._return_scene = str(scene)
            self.state = 'returning'
            self.deadline = time.monotonic() + 15
            if self._call(self.net.change_scene, self._return_scene) is False:
                self._return_scene = None
                self.state = 'playing'
                self.deadline = 0
                return False
            return True
        return bool(self._call(self.net.return_to_lobby))

    def _call(self, fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (RuntimeError, ValueError, OverflowError, OSError) as error:
            self.error = str(error)
            return False

    def ensure_steam(self):
        steam = getattr(self.net, 'steam', None)
        if steam is None:
            self.error = 'Complemento Steam indisponível nesta engine'
            return False
        status = steam.status()
        if not status['ready']:
            if status['loaded']:
                self._call(steam.shutdown)
                if steam.status()['loaded']:
                    return False
            path = self.config.get('steam_dll', '//complements/steam/AnastacioSteam.dll')
            path = os.path.abspath(self.expand_path(path))
            if not self._call(steam.initialize, path, int(self.config.get('app_id', 0))):
                return False
        if self.config.get('force_relay') and not self.net.isConnected:
            if not self._call(steam.force_relay, True):
                return False
        return True

    def host(self, mode, name, capacity, friends=False):
        if self.net.isConnected or self.state in ('creating', 'joining', 'connecting', 'searching'):
            self.error = 'Saia da sala atual antes de criar outra'
            return False
        self.error = ''
        self.mode = mode
        self.ready = False
        capacity = int(capacity)
        if capacity < 2 or capacity > 64:
            self.error = 'Escolha entre 2 e 64 jogadores'
            return False
        port = int(self.config.get('port', 7777))
        if mode == 'steam':
            if not self.ensure_steam(): return False
            self.state = 'creating'
            if not self._call(self.net.steam.create_lobby, name=name, capacity=capacity, friends_only=friends,
                              game_id=self.config.get('game_id', 'anastacio-game'),
                              build=self.config.get('build', '1'), port=port):
                self.state = 'idle'; return False
            return True
        result = self._call(self.net.host, port=port, max_players=capacity, room_name=name)
        if not result: self.error = self.error or 'Não foi possível hospedar'; self.state = 'idle'
        else: self._remember_scene()
        return bool(result)

    def _remember_scene(self):
        try:
            from Range import logic
            self.lobby_scene = logic.getCurrentScene().name
        except Exception:
            self.lobby_scene = None

    def search(self):
        if self.net.isConnected or self.state != 'idle': return False
        if not self.ensure_steam(): return False
        self.mode = 'steam'; self.rooms = []; self.state = 'searching'; self.error = ''
        if not self._call(self.net.steam.list_lobbies, self.config.get('game_id', 'anastacio-game'), self.config.get('build', '1')):
            self.state = 'idle'; return False
        return True

    def join(self, mode, address):
        if self.net.isConnected or self.state != 'idle': return False
        self.mode = mode; self.error = ''; self.ready = False
        if mode == 'steam':
            if not self.ensure_steam(): return False
            try: lobby = int(address)
            except (ValueError, TypeError): self.error = 'ID da sala inválido'; return False
            self.state = 'joining'
            if not self._call(self.net.steam.join_lobby, lobby, self.config.get('game_id', 'anastacio-game'), self.config.get('build', '1')):
                self.state = 'idle'; return False
            return True
        self.state = 'connecting'; self.deadline = time.monotonic() + 15
        if not self._call(self.net.join, str(address)):
            self.state = 'idle'; self.error = self.error or 'Endereço inválido'; return False
        return True

    def _leave_steam(self):
        steam = getattr(self.net, 'steam', None)
        if steam and steam.status()['ready']:
            self._call(steam.leave_lobby)
        self.lobby = 0

    def leave(self):
        self.net.disconnect()
        self._leave_steam()
        self.state = 'idle'; self.ready = False; self.deadline = 0
        self._return_scene = None

    def start_match(self):
        if not self.net.isServer: return False
        if any(not player.ready for player in self.net.clients):
            self.error = 'Todos os jogadores precisam estar prontos'; return False
        if not self.net.start_game():
            self.error = 'Todos os jogadores precisam estar prontos'; return False
        return True

    def tick(self):
        steam = getattr(self.net, 'steam', None)
        if self.mode == 'steam' and steam and steam.status()['loaded'] and not steam.status()['ready']:
            self.leave(); self.error = 'Steam desconectada'; return
        if steam and steam.status()['ready']:
            for event in steam.poll_events():
                kind = event['type']
                if kind == 5:
                    self.invite = event['lobby_id']
                elif kind in (1, 2):
                    self.lobby = event['lobby_id']
                    self.state = 'connecting'; self.deadline = time.monotonic() + 15
                    if kind == 1:
                        result = self._call(self.net.host, port=event['port'], max_players=event['capacity']-1,
                                            room_name=event['name'], transport='steam', websocket_port=0)
                    else:
                        result = self._call(self.net.join, '{}:{}'.format(event['host_id'], event['port']), transport='steam')
                    if not result:
                        self.leave(); self.error = self.error or 'Falha ao conectar ao host Steam'
                    elif kind == 1:
                        self._remember_scene()
                elif kind == 3:
                    self.rooms.append(event)
                elif kind == 4:
                    if self.state == 'searching': self.state = 'idle'
                elif kind in (6, 7):
                    self.leave(); self.error = event['detail'] or 'Sala encerrada'
        if self.deadline and time.monotonic() > self.deadline:
            self.leave(); self.error = 'Tempo de conexão ao host esgotado'

    def dispose(self):
        for name, callback in self._hooks:
            callbacks = self.net._callbacks.get(name, [])
            if callback in callbacks: callbacks.remove(callback)
        self._hooks = []


def get_controller(config):
    from Range import logic, network
    key = '_anastacio_network_controller'
    controller = logic.globalDict.get(key)
    if controller is None or controller.net is not network:
        if controller is not None:
            controller.dispose()
        controller = AnastacioNetworkController(network, config, logic.expandPath)
        logic.globalDict[key] = controller
    elif not network.isConnected and controller.state == 'idle':
        controller.config = dict(config)
    return controller
