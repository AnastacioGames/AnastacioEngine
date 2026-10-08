"""Offline regression for game adapter ordering and destructive invite confirmation.

Run: python tools/net_engine_test/network_adapter_review_test.py GAME_DIRECTORY
"""
import importlib
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

root = Path(__file__).resolve().parents[2]
game = Path(sys.argv[1]).resolve()
sys.path[:0] = [str(root / 'source/release/scripts/modules'), str(game)]
range_module = ModuleType('Range')
range_module.types = SimpleNamespace(KX_PythonComponent=object)
range_module.logic = SimpleNamespace(globalDict={}, getSceneList=lambda: [])
range_module.network = ModuleType('Range.network')
range_module.network.rpc = lambda **kwargs: lambda callback: callback
sys.modules['Range'] = range_module
sys.modules['Range.network'] = range_module.network

Manager = importlib.import_module('scripts.NetworkManager').NetworkManager
Menu = importlib.import_module('scripts.net_menu').NetworkMenu
Steam = importlib.import_module('scripts.SteamComponent').SteamComponent
settings = importlib.import_module('scripts.network_settings').NETWORK_CONFIG
Component = importlib.import_module('anastacio_network.component').AnastacioNetworkComponent

class Controller:
    state = 'lobby'
    error = ''
    starts = ticks = leaves = 0
    invite = 123
    lobby = 0
    mode = 'steam'
    ready = False
    chat = [(7, 'hello')]
    def start_match(self):
        self.starts += 1
        # on_start is deliberately deferred until after the whole menu call.
        return self.starts == 1
    def tick(self): self.ticks += 1
    def leave(self): self.leaves += 1
    def join(self, mode, lobby): self.joined = (mode, lobby)

c = Controller()
scenes = []
native = SimpleNamespace(isServer=True, isConnected=True, roomName='Room',
    clients=[SimpleNamespace(id=7, name='Alice', isHost=True, ready=True)],
    call=lambda *args: None, change_scene=scenes.append)
manager = Manager()
manager._net = lambda: native
manager._controller = lambda: c
manager.selected_track = 'Pista_1'
menu = Menu()
menu.controller = c
range_module.logic.globalDict['NetworkManager'] = manager
assert menu.start_match() is True
assert c.starts == 1 and scenes == ['Pista_1']

range_module.logic.globalDict['Steam_Component'] = SimpleNamespace(active=True)
menu._tick_controller()
assert c.ticks == 0
range_module.logic.globalDict.pop('Steam_Component')
menu._tick_controller()
assert c.ticks == 1
steam = Steam()
steam.active = True
steam.steam = None
range_module.logic.globalDict['_anastacio_network_controller'] = c
steam.update()
assert c.ticks == 2

previous = settings['enable_steam']
settings['enable_steam'] = False
try:
    steam.initialized = False
    steam.initialize_steam()
    assert not steam.initialized and steam.steam is None
finally:
    settings['enable_steam'] = previous

class UI:
    clicked = ''
    text_lines = []
    def button(self, label): return label == self.clicked
    def text(self, value): self.text_lines.append(value)
    def same_line(self): pass
    def input_text(self, label, value, limit): return False, value

ui = UI()
component = Component()
component.controller, component.net, component.imgui = c, native, ui
component._invite_confirmation = 0
component.chat_text = ''
ui.clicked = 'Entrar pelo convite'
component.draw()
assert c.leaves == 0 and component._invite_confirmation == 123
assert 'Alice: hello' in ui.text_lines
ui.clicked = 'Continuar na sessao atual'
component.draw()
assert c.leaves == 0 and component._invite_confirmation == 0
ui.clicked = 'Entrar pelo convite'
component.draw()
ui.clicked = 'Confirmar troca de sala'
component.draw()
assert c.leaves == 1 and c.joined == ('steam', 123) and c.invite == 0
print('NETWORK adapter review PASS (deferred start, single tick owner, disabled Steam, invite confirmation and chat names)')
