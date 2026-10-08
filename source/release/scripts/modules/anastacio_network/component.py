"""Attach anastacio_network.component.AnastacioNetworkComponent to a persistent object.
All engine/ImGui imports other than the component base are deferred until execution.
Icons are ForkAwesome glyphs. The menu draws with imgui.load_default_font(), the engine
font with those icons merged; fonts from imgui.load_font() do not carry them.
"""
from collections import OrderedDict
import time
from Range import types

# ForkAwesome code points (IconsForkAwesome.h), present in the default engine font.
ICON_USERS = ''
ICON_USER = ''
ICON_USER_PLUS = ''
ICON_STAR = ''
ICON_CHECK_CIRCLE = ''
ICON_CIRCLE_O = ''
ICON_PLAY = ''
ICON_SIGN_OUT = ''
ICON_SEARCH = ''
ICON_PLUS = ''
ICON_LINK = ''
ICON_TIMES = ''
ICON_CHECK = ''
ICON_COMMENT = ''
ICON_SEND = ''
ICON_WARNING = ''
ICON_ENVELOPE = ''
ICON_STEAM = ''
ICON_WIFI = ''
ICON_SERVER = ''
ICON_GLOBE = ''
ICON_SPINNER = ''

FONT_SIZE = 16.0
WINDOW_WIDTH = 540.0
WINDOW_PADDING = (16.0, 14.0)
ITEM_SPACING = (8.0, 8.0)
CONTENT_WIDTH = WINDOW_WIDTH - 2.0 * WINDOW_PADDING[0]
CHAT_SEND_WIDTH = 110.0
HALF_WIDTH = (CONTENT_WIDTH - ITEM_SPACING[0]) / 2.0  # Two buttons on one line.

TEXT_MUTED = (0.62, 0.66, 0.74, 1.0)
TEXT_ACCENT = (0.45, 0.70, 1.0, 1.0)
TEXT_SUCCESS = (0.40, 0.85, 0.50, 1.0)
TEXT_WARNING = (1.0, 0.76, 0.30, 1.0)
TEXT_ERROR = (1.0, 0.45, 0.45, 1.0)

BUTTON_PRIMARY = ((0.20, 0.36, 0.62, 1.0), (0.26, 0.45, 0.76, 1.0), (0.17, 0.30, 0.52, 1.0))
BUTTON_SUCCESS = ((0.17, 0.48, 0.28, 1.0), (0.22, 0.60, 0.35, 1.0), (0.14, 0.40, 0.23, 1.0))
BUTTON_DANGER = ((0.52, 0.18, 0.20, 1.0), (0.68, 0.24, 0.26, 1.0), (0.42, 0.14, 0.16, 1.0))
BUTTON_MUTED = ((0.18, 0.20, 0.26, 1.0), (0.24, 0.27, 0.34, 1.0), (0.15, 0.17, 0.22, 1.0))

STATE_TEXT = {
    'creating': 'Criando sala',
    'searching': 'Buscando salas',
    'joining': 'Entrando na sala',
    'connecting': 'Conectando ao host',
    'returning': 'Voltando para a sala',
}


class AnastacioNetworkComponent(types.KX_PythonComponent):
    args = OrderedDict([
        ('title', 'Multiplayer'), ('open_on_start', True), ('default_port', 7777),
        ('max_players', 8), ('steam_app_id', 0),
        ('steam_dll', '//complements/steam/AnastacioSteam.dll'),
        ('game_id', 'anastacio-game'), ('build', '1'), ('force_relay', False),
        ('enable_steam', False), ('enable_lan', True),
    ])

    def start(self, args):
        from Range import network, imgui
        from .controller import get_controller
        self.cfg = dict(args)
        self.net = network
        self.imgui = imgui
        self.controller = get_controller({
            'port': args.get('default_port', 7777), 'app_id': args.get('steam_app_id', 0),
            'steam_dll': args.get('steam_dll', '//complements/steam/AnastacioSteam.dll'),
            'game_id': args.get('game_id', 'anastacio-game'), 'build': args.get('build', '1'),
            'force_relay': args.get('force_relay', False)})
        self.visible = args.get('open_on_start', True)
        self._last_state = self.controller.state
        self.mode = 'steam' if args.get('enable_steam', False) else 'lan'
        self.room_name = 'Sala'
        self.capacity = str(args.get('max_players', 8))
        self.address = ''
        self.player_name = network.playerName
        self.chat_text = ''
        self.friends = True
        self.lan_rooms = []
        self.lan_search = False
        self.lan_refresh = 0
        self._invite_confirmation = 0
        self._lan_addresses = None

    def connected(self):
        """Game adapter hook: generic menu keeps showing the native room."""
        pass

    def start_match(self):
        return self.controller.start_match()

    def show(self):
        """Game-controlled access to the menu, including during a match."""
        self.visible = True

    def hide(self):
        self.visible = False
        self.imgui.set_game_ui_open(False)

    def return_to_lobby(self, scene=None):
        """Host returns the session; optionally wait for a menu scene to load."""
        result = self.controller.return_to_lobby(scene)
        if result and self.controller.state == 'lobby': self.show()
        return result

    def _tick_controller(self):
        self.controller.tick()

    def update(self):
        self._tick_controller()
        if self._last_state in ('playing', 'returning') and self.controller.state == 'lobby': self.visible = True
        if self.net.isConnected: self.connected()
        if self.controller.state == 'playing' and self._last_state != 'playing': self.hide()
        self._last_state = self.controller.state
        if not self.visible or self.net.headless: return
        ui = self.imgui
        ui.set_game_ui_open(True)
        width, height = ui.get_display_size()
        ui.set_next_window_pos(max((width - WINDOW_WIDTH) * 0.5, 0.0), max(height * 0.10, 0.0), ui.COND_ALWAYS)
        ui.set_next_window_size(WINDOW_WIDTH, 0.0, ui.COND_ALWAYS)  # Height 0 = fit content.
        pushed = self._push_theme()
        pushed_vars = self._push_style()
        font = self._font()
        if font is not None: ui.push_font(font)
        try:
            shown, _ = ui.begin(ICON_USERS + '  ' + str(self.cfg.get('title', 'Multiplayer')) + '###anastacio_network')
            try:
                if shown: self.draw()
            finally:
                ui.end()
        finally:
            if font is not None: ui.pop_font()
            if pushed_vars: ui.pop_style_var(pushed_vars)
            ui.pop_style_color(pushed)

    # ------------------------------------------------------------------ style helpers
    def _push_theme(self):
        ui = self.imgui
        colors = [
            (ui.COL_WINDOW_BG, (0.08, 0.09, 0.12, 0.96)),
            (ui.COL_TITLE_BG, (0.10, 0.12, 0.17, 1.0)),
            (ui.COL_TITLE_BG_ACTIVE, (0.13, 0.17, 0.25, 1.0)),
            (ui.COL_BORDER, (0.25, 0.28, 0.36, 0.60)),
            (ui.COL_FRAME_BG, (0.14, 0.16, 0.21, 1.0)),
            (ui.COL_FRAME_BG_HOVERED, (0.19, 0.22, 0.29, 1.0)),
            (ui.COL_FRAME_BG_ACTIVE, (0.22, 0.26, 0.35, 1.0)),
            (ui.COL_BUTTON, BUTTON_PRIMARY[0]),
            (ui.COL_BUTTON_HOVERED, BUTTON_PRIMARY[1]),
            (ui.COL_BUTTON_ACTIVE, BUTTON_PRIMARY[2]),
            (ui.COL_CHECK_MARK, TEXT_ACCENT),
            (ui.COL_SLIDER_GRAB, (0.30, 0.52, 0.86, 1.0)),
            (ui.COL_SLIDER_GRAB_ACTIVE, TEXT_ACCENT),
        ]
        for index, rgba in colors:
            ui.push_style_color(index, *rgba)
        return len(colors)

    def _font(self):
        """Engine font with icons at FONT_SIZE; None on the first frame or on older engines."""
        loader = getattr(self.imgui, 'load_default_font', None)
        return loader(FONT_SIZE) if loader else None

    def _push_style(self):
        ui = self.imgui
        if not hasattr(ui, 'push_style_var'):
            return 0
        values = [
            (ui.STYLE_WINDOW_ROUNDING, (10.0,)),
            (ui.STYLE_FRAME_ROUNDING, (6.0,)),
            (ui.STYLE_GRAB_ROUNDING, (6.0,)),
            (ui.STYLE_WINDOW_BORDER_SIZE, (1.0,)),
            (ui.STYLE_WINDOW_PADDING, WINDOW_PADDING),
            (ui.STYLE_FRAME_PADDING, (10.0, 7.0)),
            (ui.STYLE_ITEM_SPACING, ITEM_SPACING),
        ]
        for index, value in values:
            ui.push_style_var(index, *value)
        return len(values)

    def colored(self, text, rgba):
        ui = self.imgui
        ui.push_style_color(ui.COL_TEXT, *rgba)
        try:
            ui.text(text)
        finally:
            ui.pop_style_color(1)

    def styled_button(self, label, palette=BUTTON_PRIMARY, width=CONTENT_WIDTH, height=0.0):
        ui = self.imgui
        ui.push_style_color(ui.COL_BUTTON, *palette[0])
        ui.push_style_color(ui.COL_BUTTON_HOVERED, *palette[1])
        ui.push_style_color(ui.COL_BUTTON_ACTIVE, *palette[2])
        try:
            return ui.button(label, width, height)
        finally:
            ui.pop_style_color(3)

    def section(self, icon, title):
        self.imgui.separator()
        self.colored(icon + '  ' + title, TEXT_ACCENT)

    def item_width(self, width):
        """Width of the next widget; engines without set_next_item_width keep ImGui's default."""
        set_width = getattr(self.imgui, 'set_next_item_width', None)
        if set_width is not None: set_width(width)

    def field(self, label, name, limit=255):
        """Label above a full-width input field; the field itself uses a hidden id."""
        self.colored(label, TEXT_MUTED)
        self.item_width(CONTENT_WIDTH)
        changed, value = self.imgui.input_text('##' + name, getattr(self, name), limit)
        if changed: setattr(self, name, value)
        return changed

    # ------------------------------------------------------------------ actions
    def _accept_invite(self):
        c = self.controller
        lobby = c.invite
        c.leave()
        c.join('steam', lobby)
        c.invite = 0
        self._invite_confirmation = 0

    def _host_lan_addresses(self):
        if self._lan_addresses is None:
            import socket
            try:
                self._lan_addresses = sorted({entry[4][0] for entry in
                    socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET, socket.SOCK_DGRAM)
                    if not entry[4][0].startswith('127.') and entry[4][0] != '0.0.0.0'})
            except OSError:
                self._lan_addresses = []
        port = self.controller.config.get('port', 7777)
        for address in self._lan_addresses:
            self.colored(ICON_WIFI + '  Endereço LAN: {}:{}'.format(address, port), TEXT_MUTED)
        if not self._lan_addresses:
            self.colored(ICON_WIFI + '  Porta LAN: {} (consulte o IP nas configurações de rede)'.format(port), TEXT_MUTED)

    # ------------------------------------------------------------------ drawing
    def draw(self):
        c = self.controller
        if c.error:
            self.colored(ICON_WARNING + '  ' + str(c.error), TEXT_ERROR)
        if c.invite:
            self.draw_invite()
        if self.net.isConnected:
            self.draw_room()
            return
        if c.state != 'idle':
            self.draw_waiting()
            return
        self.draw_setup()

    def draw_invite(self):
        ui, c = self.imgui, self.controller
        self.section(ICON_ENVELOPE, 'Convite Steam recebido')
        if self._invite_confirmation and self._invite_confirmation == c.invite:
            self.colored('Sair da sessão atual para aceitar este convite?', TEXT_WARNING)
            if self.styled_button(ICON_CHECK + '  Trocar de sala##invite_confirm', BUTTON_SUCCESS, HALF_WIDTH):
                self._accept_invite()
            ui.same_line()
            if self.styled_button(ICON_TIMES + '  Ficar##invite_stay', BUTTON_MUTED, HALF_WIDTH):
                self._invite_confirmation = 0
        else:
            if self.styled_button(ICON_CHECK + '  Entrar##invite_accept', BUTTON_SUCCESS, HALF_WIDTH):
                if self.net.isConnected or c.state != 'idle':
                    self._invite_confirmation = c.invite
                else:
                    self._accept_invite()
            ui.same_line()
            if self.styled_button(ICON_TIMES + '  Recusar##invite_decline', BUTTON_MUTED, HALF_WIDTH):
                c.invite = 0; self._invite_confirmation = 0
        ui.separator()

    def draw_waiting(self):
        c = self.controller
        dots = '.' * (int(time.monotonic() * 3) % 4)
        self.colored(ICON_SPINNER + '  ' + STATE_TEXT.get(c.state, c.state) + dots, TEXT_ACCENT)
        self.imgui.separator()
        if self.styled_button(ICON_TIMES + '  Cancelar##waiting_cancel', BUTTON_MUTED):
            c.leave()

    def draw_room(self):
        ui, c, net = self.imgui, self.controller, self.net
        transport = (ICON_STEAM + '  Steam') if c.lobby else (ICON_WIFI + '  LAN / IP')
        self.colored(ICON_USERS + '  ' + str(net.roomName), TEXT_ACCENT)
        ui.same_line()
        self.colored('  ' + transport, TEXT_MUTED)
        if net.isServer and c.mode == 'lan': self._host_lan_addresses()

        players = list(net.clients)
        self.section(ICON_USER, 'Jogadores ({})'.format(len(players)))
        for player in players:
            mark, color = (ICON_CHECK_CIRCLE, TEXT_SUCCESS) if player.ready else (ICON_CIRCLE_O, TEXT_MUTED)
            self.colored(mark, color)
            ui.same_line()
            ui.text(str(player.name))
            if player.isHost:
                ui.same_line()
                self.colored(ICON_STAR + ' Host', TEXT_WARNING)

        ui.separator()
        playing = c.state == 'playing'
        ready_label = (ICON_TIMES + '  Não estou pronto') if c.ready else (ICON_CHECK + '  Estou pronto')
        if net.isServer and not playing:
            if self.styled_button(ready_label + '##ready', BUTTON_MUTED if c.ready else BUTTON_PRIMARY, HALF_WIDTH):
                c.ready = not c.ready; net.set_ready(c.ready)
            ui.same_line()
            if self.styled_button(ICON_PLAY + '  Iniciar partida##start', BUTTON_SUCCESS, HALF_WIDTH):
                self.start_match()
        elif not playing:
            if self.styled_button(ready_label + '##ready', BUTTON_MUTED if c.ready else BUTTON_PRIMARY):
                c.ready = not c.ready; net.set_ready(c.ready)
        if c.lobby and self.styled_button(ICON_USER_PLUS + '  Convidar amigos##invite_friends', BUTTON_PRIMARY):
            c._call(net.steam.invite_friends)

        self.section(ICON_COMMENT, 'Chat')
        names = {player.id: player.name for player in players}
        if not c.chat:
            self.colored('Nenhuma mensagem ainda.', TEXT_MUTED)
        for client, message in c.chat[-8:]:
            self.colored(str(names.get(client, 'Jogador {}'.format(client))) + ':', TEXT_ACCENT)
            ui.same_line()
            ui.text(str(message))
        self.item_width(CONTENT_WIDTH - CHAT_SEND_WIDTH - ITEM_SPACING[0])
        changed, value = ui.input_text('##chat_text', self.chat_text, 200)
        if changed: self.chat_text = value
        ui.same_line()
        if ui.button(ICON_SEND + '  Enviar##chat_send', CHAT_SEND_WIDTH, 0.0) and self.chat_text.strip():
            net.send_chat(self.chat_text.strip()); self.chat_text = ''

        ui.separator()
        if self.styled_button(ICON_SIGN_OUT + '  Sair da sala##leave', BUTTON_DANGER):
            c.leave()

    def draw_setup(self):
        ui, c = self.imgui, self.controller
        lan_enabled = self.cfg.get('enable_lan', True)
        steam_enabled = self.cfg.get('enable_steam', False)
        if lan_enabled and steam_enabled:
            lan_palette = BUTTON_PRIMARY if self.mode == 'lan' else BUTTON_MUTED
            steam_palette = BUTTON_PRIMARY if self.mode == 'steam' else BUTTON_MUTED
            if self.styled_button(ICON_WIFI + '  LAN / IP##mode_lan', lan_palette, HALF_WIDTH): self.mode = 'lan'
            ui.same_line()
            if self.styled_button(ICON_STEAM + '  Steam##mode_steam', steam_palette, HALF_WIDTH): self.mode = 'steam'
        elif steam_enabled:
            self.mode = 'steam'
        else:
            self.mode = 'lan'

        self.section(ICON_USER, 'Jogador')
        if self.field('Seu nome', 'player_name', 64): self.net.playerName = self.player_name

        self.section(ICON_PLUS, 'Criar sala')
        self.field('Nome da sala', 'room_name')
        self.colored('Jogadores', TEXT_MUTED)
        self.item_width(CONTENT_WIDTH)
        changed, capacity = ui.slider_int('##capacity', int(self.capacity), 2, 64)
        if changed: self.capacity = str(capacity)
        if self.mode == 'steam':
            changed, value = ui.checkbox('Somente amigos', self.friends)
            if changed: self.friends = value
        if self.styled_button(ICON_PLUS + '  Hospedar##host', BUTTON_SUCCESS):
            try: capacity = int(self.capacity)
            except ValueError: c.error = 'Número de jogadores inválido'
            else: c.host(self.mode, self.room_name, capacity, self.friends)

        self.section(ICON_LINK, 'Entrar em uma sala')
        self.field('ID da sala' if self.mode == 'steam' else 'IP:porta', 'address')
        if self.styled_button(ICON_LINK + '  Entrar##join', BUTTON_PRIMARY):
            c.join(self.mode, self.address)

        if self.mode == 'steam':
            self.section(ICON_GLOBE, 'Salas disponíveis')
            if self.styled_button(ICON_SEARCH + '  Buscar salas##search_steam', BUTTON_MUTED): c.search()
            for room in c.rooms:
                label = '{}  {}   ({}/{})##room{}'.format(ICON_USERS, room['name'] or 'Sala',
                                                        room['members'], room['capacity'], room['lobby_id'])
                if self.styled_button(label, BUTTON_MUTED): c.join('steam', room['lobby_id'])
        else:
            self.section(ICON_SERVER, 'Salas na rede local')
            if self.styled_button(ICON_SEARCH + '  Buscar na LAN##search_lan', BUTTON_MUTED):
                self.lan_search = True
                self.lan_refresh = 0
            if self.lan_search and time.monotonic() >= self.lan_refresh:
                self.lan_rooms = self.net.discover_lan()
                self.lan_refresh = time.monotonic() + 1
            if self.lan_search and not self.lan_rooms:
                self.colored('Nenhuma sala encontrada ainda.', TEXT_MUTED)
            for room in self.lan_rooms:
                label = '{}  {}   {}:{}##lan{}'.format(ICON_SERVER, room['name'], room['address'],
                                                      room['port'], room['address'])
                if self.styled_button(label, BUTTON_MUTED):
                    c.join('lan', '{}:{}'.format(room['address'], room['port']))

    def dispose(self):
        # Closing an overlay must keep the session alive for the game behind it.
        if hasattr(self, 'imgui'): self.imgui.set_game_ui_open(False)
