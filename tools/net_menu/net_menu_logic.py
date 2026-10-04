"""
NetworkMenu logic (no imgui, no Range): screen state machine, input validation,
language table, theme/scale helpers, on-screen keyboard and focus navigation.

Everything here is pure Python so tests run without the engine. net_menu.py only
draws what this module decides.
"""

import ipaddress
import re

# ---------------------------------------------------------------------------
# Screens and transitions (plan section 6.4)
# ---------------------------------------------------------------------------

MAIN = "main"
HOST = "host"
JOIN = "join"
LAN = "lan"
LOBBY = "lobby"
PAUSE = "pause"
SETTINGS = "settings"
CLOSED = "closed"  # in game, menu hidden (no imgui window drawn)

SCREENS = (MAIN, HOST, JOIN, LAN, LOBBY, PAUSE, SETTINGS, CLOSED)

# Allowed screen -> screen transitions. "back" targets come from BACK below.
TRANSITIONS = {
	MAIN: {HOST, JOIN, LAN, SETTINGS, CLOSED},
	HOST: {MAIN, LOBBY},
	JOIN: {MAIN, LOBBY},
	LAN: {MAIN, LOBBY, JOIN},
	SETTINGS: {MAIN, PAUSE},
	LOBBY: {MAIN, CLOSED},
	CLOSED: {PAUSE, MAIN},
	PAUSE: {CLOSED, MAIN, SETTINGS},
}

BACK = {
	HOST: MAIN,
	JOIN: MAIN,
	LAN: MAIN,
	LOBBY: MAIN,  # leaving the lobby disconnects
	PAUSE: CLOSED,  # Esc in pause resumes the game
	MAIN: MAIN,
	CLOSED: PAUSE,  # Esc in game opens pause (only when connected)
}

# Notice (modal) kinds, mapped from protocol RejectReason / DisconnectReason.
REJECT_REASONS = {
	1: "reject_version",
	2: "reject_scene",
	3: "reject_full",
	4: "reject_token",
	5: "reject_banned",
	6: "reject_in_progress",
	7: "reject_password",  # provisional, proposed in NOTES-D.md
}
DISCONNECT_REASONS = {
	1: "disc_quit",
	2: "disc_timeout",
	3: "disc_kicked",
	4: "disc_violation",
	5: "disc_shutdown",
}


class MenuState:
	"""Screen stack + pending notice. Pure state, no drawing."""

	def __init__(self, hidden_screens=()):
		self.screen = MAIN
		self.previous = None
		self.hidden = set(hidden_screens)
		self.notice = None  # string key in STRINGS or None
		self.notice_detail = ""
		self.status = None  # e.g. "connecting"
		self.settings_return = MAIN
		self.confirm = None  # string key of a yes/no question, or None
		self.focus = FocusNav()

	def can_go(self, target):
		if target not in SCREENS:
			return False
		if target in self.hidden:
			return False
		return target in TRANSITIONS.get(self.screen, set())

	def go(self, target):
		if not self.can_go(target):
			return False
		if target == SETTINGS:
			self.settings_return = self.screen if self.screen in (MAIN, PAUSE) else MAIN
		self.previous = self.screen
		self.screen = target
		self.focus.reset()
		return True

	def back(self, connected=False):
		if self.notice:
			self.dismiss_notice()
			return self.screen
		if self.confirm:
			self.confirm = None
			return self.screen
		if self.screen == SETTINGS:
			target = self.settings_return
		elif self.screen == CLOSED and not connected:
			return self.screen
		else:
			target = BACK.get(self.screen, MAIN)
		if target != self.screen:
			self.previous = self.screen
			self.screen = target
			self.focus.reset()
		return self.screen

	# --- network events ---------------------------------------------------
	def on_connecting(self):
		self.status = "connecting"

	def on_connected(self):
		self.status = None
		if self.screen in (HOST, JOIN, LAN):
			self.go(LOBBY)

	def on_game_started(self):
		if self.screen == LOBBY:
			self.go(CLOSED)

	def on_rejected(self, reason, detail=""):
		self.status = None
		self.show_notice(REJECT_REASONS.get(reason, "reject_unknown"), detail)

	def on_disconnected(self, reason, detail=""):
		self.status = None
		if reason != 1:  # Quit is user initiated: no modal
			self.show_notice(DISCONNECT_REASONS.get(reason, "disc_unknown"), detail)
		self.previous = self.screen
		self.screen = MAIN
		self.focus.reset()

	def show_notice(self, key, detail=""):
		self.notice = key
		self.notice_detail = detail or ""

	def dismiss_notice(self):
		self.notice = None
		self.notice_detail = ""

	def ask(self, key):
		"""Opens a yes/no question (e.g. "confirm_disconnect"); answered by the draw code."""
		self.confirm = key
		self.focus.reset()

	@property
	def visible(self):
		return self.screen != CLOSED or self.notice is not None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

ROOM_CODE_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
ROOM_CODE_MIN = 4
ROOM_CODE_MAX = 8
_HOST_LABEL = re.compile(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)$")


def validate_port(value):
	"""Return int port 1..65535 or None. Accepts int or digit string."""
	if isinstance(value, bool):
		return None
	if isinstance(value, int):
		port = value
	else:
		text = str(value).strip()
		if not text.isascii() or not text.isdigit() or len(text) > 5:
			return None
		port = int(text)
	return port if 1 <= port <= 65535 else None


def validate_host(text):
	"""IPv4, IPv6 or DNS hostname. Returns normalized string or None."""
	if not isinstance(text, str):
		return None
	text = (text or "").strip()
	if not text:
		return None
	try:
		return str(ipaddress.ip_address(text))
	except ValueError:
		pass
	if len(text) > 253:
		return None
	labels = text.rstrip(".").split(".")
	if all(_HOST_LABEL.match(l) for l in labels):
		# Dotted all-numeric strings that failed ip parsing (e.g. 999.1.1.1) are invalid.
		if all(l.isdigit() for l in labels):
			return None
		return text.rstrip(".").lower()
	return None


def parse_address(text, default_port):
	"""'host', 'host:port', '[v6]:port' or bare v6. Returns (host, port) or None."""
	if not isinstance(text, str):
		return None
	text = (text or "").strip()
	if not text:
		return None
	host, port = text, default_port
	if text.startswith("["):
		end = text.find("]")
		if end < 0:
			return None
		host = text[1:end]
		rest = text[end + 1:]
		if rest:
			if not rest.startswith(":"):
				return None
			port = rest[1:]
	elif text.count(":") == 1:
		host, port = text.split(":")
	h = validate_host(host)
	p = validate_port(port)
	if h is None or p is None:
		return None
	return h, p


def normalize_room_code(text):
	"""Base-36 short room code. Returns upper-case code or None."""
	if not isinstance(text, str):
		return None
	code = (text or "").strip().upper().replace("-", "").replace(" ", "")
	if not ROOM_CODE_MIN <= len(code) <= ROOM_CODE_MAX:
		return None
	if any(c not in ROOM_CODE_ALPHABET for c in code):
		return None
	return code


def parse_join_target(text, default_port):
	"""Join field accepts an address or a room code.

	Returns ("addr", (host, port)), ("code", code) or None. A string that is a
	valid code and has no dot/colon is treated as a code.
	"""
	if not isinstance(text, str):
		return None
	text = (text or "").strip()
	if not text:
		return None
	if "." not in text and ":" not in text and text.lower() != "localhost":
		code = normalize_room_code(text)
		if code:
			return ("code", code)
	addr = parse_address(text, default_port)
	if addr:
		return ("addr", addr)
	return None


def validate_player_name(text, max_len=16):
	if not isinstance(text, str):
		return None
	name = (text or "").strip()
	if not 1 <= len(name) <= max_len:
		return None
	if any(ord(c) < 32 for c in name):
		return None
	return name


def validate_room_name(text, max_len=32):
	return validate_player_name(text, max_len)


def validate_max_players(value, limit=64):
	try:
		n = int(value)
	except (TypeError, ValueError):
		return None
	return n if 2 <= n <= limit else None


def validate_chat(text, max_bytes=200):
	"""Protocol Chat is <= 200 bytes UTF-8; trim on a character boundary."""
	if not isinstance(text, str):
		return None
	text = (text or "").strip()
	if not text:
		return None
	data = text.encode("utf-8")[:max_bytes]
	return data.decode("utf-8", "ignore")


# ---------------------------------------------------------------------------
# Language table
# ---------------------------------------------------------------------------

LANGUAGES = ("en", "pt", "es")

STRINGS = {
	"en": {
		"title": "Multiplayer",
		"host": "Host", "join": "Join", "lan": "LAN Servers", "settings": "Settings",
		"quit": "Quit", "back": "Back",
		"room_name": "Room name", "max_players": "Max players", "port": "Port",
		"password": "Password (optional)", "create": "Create",
		"address": "IP:port or room code", "connect": "Connect", "connecting": "Connecting...",
		"refresh": "Refresh", "no_servers": "No servers found", "players": "Players", "ping": "Ping",
		"lobby": "Lobby", "ready": "Ready", "not_ready": "Not ready", "start": "Start",
		"leave": "Leave", "chat": "Chat", "send": "Send",
		"pause": "Paused", "resume": "Resume", "connected_players": "Connected players",
		"disconnect": "Disconnect",
		"player_name": "Player name", "language": "Language", "net_sim": "Network simulator",
		"latency": "Latency (ms)", "loss": "Packet loss (%)",
		"ok": "OK", "notice": "Notice", "keyboard": "Keyboard", "done": "Done", "space": "Space",
		"err_address": "Invalid address or room code",
		"err_port": "Port must be 1-65535", "err_name": "Invalid name",
		"err_max_players": "Max players must be 2-64",
		"reject_version": "Incompatible version", "reject_scene": "Different scene on server",
		"reject_full": "Room is full", "reject_token": "Invalid reconnect token",
		"reject_banned": "You are banned from this server",
		"reject_in_progress": "Game already in progress", "reject_unknown": "Connection refused",
		"reject_password": "Wrong password",
		"disc_quit": "Disconnected", "disc_timeout": "Connection timed out",
		"disc_kicked": "Kicked by host", "disc_violation": "Disconnected: protocol violation",
		"disc_shutdown": "Server shut down", "disc_unknown": "Disconnected",
		"host_tag": "host",
		"searching": "Searching...", "full": "Full", "locked": "Password", "room_password": "Room password",
		"servers_found": "Servers found", "ui_scale": "UI scale", "touch_mode": "Touch controls",
		"touch_auto": "Auto", "touch_on": "On", "touch_off": "Off", "jitter": "Jitter (ms)",
		"reset_defaults": "Reset to defaults", "confirm_disconnect": "Leave the game?", "yes": "Yes",
		"no": "No", "lang_en": "English", "lang_pt": "Português", "lang_es": "Español",
		"room": "Room", "all_ready": "Everyone is ready", "waiting_ready": "Waiting for players",
	},
	"pt": {
		"title": "Multijogador",
		"host": "Hospedar", "join": "Entrar", "lan": "Servidores LAN", "settings": "Configurações",
		"quit": "Sair", "back": "Voltar",
		"room_name": "Nome da sala", "max_players": "Máximo de jogadores", "port": "Porta",
		"password": "Senha (opcional)", "create": "Criar",
		"address": "IP:porta ou código da sala", "connect": "Conectar", "connecting": "Conectando...",
		"refresh": "Atualizar", "no_servers": "Nenhum servidor encontrado", "players": "Jogadores",
		"ping": "Ping",
		"lobby": "Sala", "ready": "Pronto", "not_ready": "Não pronto", "start": "Iniciar",
		"leave": "Sair", "chat": "Chat", "send": "Enviar",
		"pause": "Pausado", "resume": "Continuar", "connected_players": "Jogadores conectados",
		"disconnect": "Desconectar",
		"player_name": "Nome do jogador", "language": "Idioma", "net_sim": "Simulador de rede",
		"latency": "Latência (ms)", "loss": "Perda de pacotes (%)",
		"ok": "OK", "notice": "Aviso", "keyboard": "Teclado", "done": "Pronto", "space": "Espaço",
		"err_address": "Endereço ou código de sala inválido",
		"err_port": "A porta deve ser de 1 a 65535", "err_name": "Nome inválido",
		"err_max_players": "Máximo de jogadores deve ser de 2 a 64",
		"reject_version": "Versão incompatível", "reject_scene": "Cena diferente no servidor",
		"reject_full": "Sala cheia", "reject_token": "Token de reconexão inválido",
		"reject_banned": "Você está banido deste servidor",
		"reject_in_progress": "Partida já em andamento", "reject_unknown": "Conexão recusada",
		"reject_password": "Senha incorreta",
		"disc_quit": "Desconectado", "disc_timeout": "Tempo de conexão esgotado",
		"disc_kicked": "Removido pelo host", "disc_violation": "Desconectado: violação de protocolo",
		"disc_shutdown": "Servidor encerrado", "disc_unknown": "Desconectado",
		"host_tag": "host",
		"searching": "Procurando...", "full": "Cheia", "locked": "Senha", "room_password": "Senha da sala",
		"servers_found": "Servidores encontrados", "ui_scale": "Escala da interface",
		"touch_mode": "Controles de toque", "touch_auto": "Automático", "touch_on": "Ligado",
		"touch_off": "Desligado", "jitter": "Variação (ms)", "reset_defaults": "Restaurar padrões",
		"confirm_disconnect": "Sair da partida?", "yes": "Sim", "no": "Não", "lang_en": "English",
		"lang_pt": "Português", "lang_es": "Español", "room": "Sala", "all_ready": "Todos prontos",
		"waiting_ready": "Esperando jogadores",
	},
	"es": {
		"title": "Multijugador",
		"host": "Crear partida", "join": "Unirse", "lan": "Servidores LAN", "settings": "Ajustes",
		"quit": "Salir", "back": "Volver",
		"room_name": "Nombre de la sala", "max_players": "Máximo de jugadores", "port": "Puerto",
		"password": "Contraseña (opcional)", "create": "Crear",
		"address": "IP:puerto o código de sala", "connect": "Conectar", "connecting": "Conectando...",
		"refresh": "Actualizar", "no_servers": "No se encontraron servidores",
		"players": "Jugadores", "ping": "Ping",
		"lobby": "Sala", "ready": "Listo", "not_ready": "No listo", "start": "Iniciar",
		"leave": "Salir", "chat": "Chat", "send": "Enviar",
		"pause": "En pausa", "resume": "Continuar", "connected_players": "Jugadores conectados",
		"disconnect": "Desconectar",
		"player_name": "Nombre del jugador", "language": "Idioma", "net_sim": "Simulador de red",
		"latency": "Latencia (ms)", "loss": "Pérdida de paquetes (%)",
		"ok": "OK", "notice": "Aviso", "keyboard": "Teclado", "done": "Listo", "space": "Espacio",
		"err_address": "Dirección o código de sala no válido",
		"err_port": "El puerto debe ser de 1 a 65535", "err_name": "Nombre no válido",
		"err_max_players": "El máximo de jugadores debe ser de 2 a 64",
		"reject_version": "Versión incompatible", "reject_scene": "Escena diferente en el servidor",
		"reject_full": "La sala está llena", "reject_token": "Token de reconexión no válido",
		"reject_banned": "Estás vetado en este servidor",
		"reject_in_progress": "La partida ya está en curso", "reject_unknown": "Conexión rechazada",
		"reject_password": "Contraseña incorrecta",
		"disc_quit": "Desconectado", "disc_timeout": "Tiempo de conexión agotado",
		"disc_kicked": "Expulsado por el anfitrión",
		"disc_violation": "Desconectado: violación de protocolo",
		"disc_shutdown": "Servidor cerrado", "disc_unknown": "Desconectado",
		"host_tag": "anfitrión",
		"searching": "Buscando...", "full": "Llena", "locked": "Contraseña",
		"room_password": "Contraseña de la sala", "servers_found": "Servidores encontrados",
		"ui_scale": "Escala de la interfaz", "touch_mode": "Controles táctiles", "touch_auto": "Automático",
		"touch_on": "Activado", "touch_off": "Desactivado", "jitter": "Variación (ms)",
		"reset_defaults": "Restablecer valores", "confirm_disconnect": "¿Salir de la partida?", "yes": "Sí",
		"no": "No", "lang_en": "English", "lang_pt": "Português", "lang_es": "Español", "room": "Sala",
		"all_ready": "Todos listos", "waiting_ready": "Esperando jugadores",
	},
}


def tr(lang, key):
	"""Translate; falls back to English, then to the key itself."""
	table = STRINGS.get(lang) or STRINGS["en"]
	return table.get(key) or STRINGS["en"].get(key, key)


# ---------------------------------------------------------------------------
# Theme and scale
# ---------------------------------------------------------------------------

DEFAULT_THEME = {
	"accent": (0.20, 0.55, 0.95, 1.0),
	"window_bg": (0.08, 0.09, 0.11, 0.94),
	"text": (0.95, 0.95, 0.97, 1.0),
	"button": (0.18, 0.20, 0.24, 1.0),
	"focus": (1.0, 0.80, 0.20, 1.0),
}


def parse_color(value, fallback):
	"""Accept (r,g,b[,a]) floats 0..1 or '#RRGGBB[AA]'."""
	if isinstance(value, str):
		s = value.strip().lstrip("#")
		if len(s) in (6, 8) and all(c in "0123456789abcdefABCDEF" for c in s):
			parts = [int(s[i:i + 2], 16) / 255.0 for i in range(0, len(s), 2)]
			if len(parts) == 3:
				parts.append(1.0)
			return tuple(parts)
		return fallback
	try:
		parts = [float(v) for v in value]
	except (TypeError, ValueError):
		return fallback
	if len(parts) == 3:
		parts.append(1.0)
	if len(parts) != 4:
		return fallback
	return tuple(min(1.0, max(0.0, p)) for p in parts)


def build_theme(args):
	theme = dict(DEFAULT_THEME)
	for key in DEFAULT_THEME:
		arg = args.get(key + "_color") if args else None
		if arg is not None:
			theme[key] = parse_color(arg, DEFAULT_THEME[key])
	return theme


BASE_HEIGHT = 720.0
TOUCH_MIN_BUTTON = 48.0
DESKTOP_BUTTON = 32.0


def compute_layout(display_w, display_h, touch=False, user_scale=1.0):
	"""Scale from screen height (720p = 1.0); touch enforces >= 48 px buttons."""
	h = max(1.0, float(display_h))
	w = max(1.0, float(display_w))
	scale = max(0.5, min(3.0, (h / BASE_HEIGHT) * float(user_scale or 1.0)))
	button_h = DESKTOP_BUTTON * scale
	spacing = 8.0 * scale
	if touch:
		button_h = max(TOUCH_MIN_BUTTON, button_h * 1.25)
		spacing = max(12.0, spacing * 1.5)
	win_w = min(w - 2 * spacing, max(320.0, 480.0 * scale))
	win_h = min(h - 2 * spacing, max(360.0, 560.0 * scale))
	return {
		"scale": scale,
		"button_h": button_h,
		"spacing": spacing,
		"win_w": win_w,
		"win_h": win_h,
		"win_x": (w - win_w) * 0.5,
		"win_y": (h - win_h) * 0.5,
	}


def detect_touch(platform_name, force=None):
	if force is not None and force != "auto":
		return bool(force) if not isinstance(force, str) else force == "on"
	p = (platform_name or "").lower()
	return any(k in p for k in ("android", "ios", "emscripten", "web"))


# ---------------------------------------------------------------------------
# On-screen keyboard
# ---------------------------------------------------------------------------

KEYBOARD_ROWS = (
	"1234567890",
	"QWERTYUIOP",
	"ASDFGHJKL.",
	"ZXCVBNM:-_",
)
KEY_BACKSPACE = "<-"
KEY_SPACE = " "
KEY_DONE = "OK"
KEY_SHIFT = "Aa"


class OnScreenKeyboard:
	"""Simple ImGui-drawn keyboard for touch platforms; edits one field."""

	def __init__(self):
		self.field = None
		self.text = ""
		self.max_length = 64
		self.lower = True

	@property
	def active(self):
		return self.field is not None

	def open(self, field, text, max_length=64):
		self.field = field
		self.text = text or ""
		self.max_length = max_length

	def press(self, key):
		"""Returns (field, text) when finished, else None."""
		if not self.active:
			return None
		if key == KEY_DONE:
			result = (self.field, self.text)
			self.field = None
			return result
		if key == KEY_BACKSPACE:
			self.text = self.text[:-1]
		elif key == KEY_SHIFT:
			self.lower = not self.lower
		elif len(self.text) < self.max_length:
			ch = key.lower() if self.lower and key.isalpha() else key
			self.text += ch
		return None

	def rows(self):
		rows = [[(k.lower() if self.lower and k.isalpha() else k) for k in r] for r in KEYBOARD_ROWS]
		rows.append([KEY_SHIFT, KEY_SPACE, KEY_BACKSPACE, KEY_DONE])
		return rows


# ---------------------------------------------------------------------------
# Focus navigation (keyboard / gamepad)
# ---------------------------------------------------------------------------

NAV_UP = "up"
NAV_DOWN = "down"
NAV_ACCEPT = "accept"
NAV_BACK = "back"
NAV_LEFT = "left"
NAV_RIGHT = "right"


class FocusNav:
	"""Focus index over the activatable items registered this frame.

	The draw code calls item(id) for each button in order; the one equal to
	focused() gets a highlight and activates on NAV_ACCEPT.
	"""

	def __init__(self):
		self.index = 0
		self.count = 0
		self._items = []
		self.pending_accept = False
		self.pending_adjust = 0

	def reset(self):
		self.index = 0
		self.pending_accept = False
		self.pending_adjust = 0

	def begin_frame(self):
		self.count = len(self._items)
		self._items = []

	def item(self, item_id):
		self._items.append(item_id)
		return len(self._items) - 1 == self.index

	def handle(self, action):
		n = max(self.count, len(self._items))
		if action == NAV_DOWN and n:
			self.index = (self.index + 1) % n
		elif action == NAV_UP and n:
			self.index = (self.index - 1) % n
		elif action == NAV_ACCEPT:
			self.pending_accept = True
		elif action == NAV_LEFT:
			self.pending_adjust -= 1
		elif action == NAV_RIGHT:
			self.pending_adjust += 1

	def consume_accept(self, item_id):
		"""True once if accept is pending and item_id is focused."""
		if self.pending_accept and self._items and self._items[-1] == item_id \
				and len(self._items) - 1 == self.index:
			self.pending_accept = False
			return True
		return False

	def consume_adjust(self, item_id):
		"""Left/right presses (-n..n) pending for item_id when it is focused, else 0."""
		if self.pending_adjust and self._items and self._items[-1] == item_id \
				and len(self._items) - 1 == self.index:
			n, self.pending_adjust = self.pending_adjust, 0
			return n
		return 0

	def end_frame(self):
		"""Drops left/right presses no focused item took (e.g. on a plain button)."""
		self.pending_adjust = 0


def step_value(value, delta, lo, hi, step):
	"""value + delta * step clamped to [lo, hi], snapped to the step grid from lo."""
	try:
		v = float(value)
	except (TypeError, ValueError):
		v = float(lo)
	v = min(float(hi), max(float(lo), v + delta * step))
	n = round((v - lo) / step)
	v = lo + n * step
	return type(step)(v) if isinstance(step, int) else round(v, 4)


def cycle(options, current, delta=1):
	"""Next (or previous) item of options after current; the first one if current is unknown."""
	options = list(options)
	if current not in options:
		return options[0]
	return options[(options.index(current) + delta) % len(options)]


# ---------------------------------------------------------------------------
# LAN servers (format of NET_LanDiscovery, front H)
# ---------------------------------------------------------------------------

def _int(value, default=0, lo=0, hi=65535):
	try:
		n = int(value)
	except (TypeError, ValueError):
		return default
	return min(hi, max(lo, n))


def normalize_lan_entry(entry):
	"""Dict from discover_lan() -> dict with every key, or None when unusable.

	Keys: name, address (IPv4), port (ENet), ws_port, players, max_players, ping (ms),
	password (bool), scene, full (bool). An address with ":port" and no "port" key is split.
	"""
	if not isinstance(entry, dict):
		return None
	address = str(entry.get("address") or "").strip()
	port = entry.get("port")
	if port is None and address.count(":") == 1:
		address, port = address.split(":")
	host = validate_host(address)
	port = validate_port(port if port is not None else 0)
	if host is None or port is None:
		return None
	players = _int(entry.get("players"))
	max_players = _int(entry.get("max_players"))
	name = str(entry.get("name") or host)[:64]
	return {
		"name": name,
		"address": host,
		"port": port,
		"ws_port": _int(entry.get("ws_port")),
		"players": players,
		"max_players": max_players,
		"ping": _int(entry.get("ping"), 0, 0, 9999),
		"password": bool(entry.get("password", False)),
		"scene": str(entry.get("scene") or ""),
		"full": max_players > 0 and players >= max_players,
	}


def lan_servers(raw):
	"""Valid entries, one per address:port, open rooms first, then by ping and name."""
	seen = {}
	for e in raw or []:
		n = normalize_lan_entry(e)
		if n is None:
			continue
		key = (n["address"], n["port"])
		if key not in seen or n["ping"] < seen[key]["ping"]:
			seen[key] = n
	return sorted(seen.values(), key=lambda n: (n["full"], n["ping"], n["name"].lower()))


def lan_join_address(entry):
	return "{}:{}".format(entry["address"], entry["port"])


def format_lan_row(entry, lang):
	"""One row: name, players/max, ping and tags (full, password)."""
	tags = []
	if entry["full"]:
		tags.append(tr(lang, "full"))
	if entry["password"]:
		tags.append(tr(lang, "locked"))
	row = "{}  {}/{}  {} ms".format(entry["name"], entry["players"], entry["max_players"], entry["ping"])
	if tags:
		row += "  [" + ", ".join(tags) + "]"
	return row


# ---------------------------------------------------------------------------
# Settings (persisted as JSON when the component has a settings_file)
# ---------------------------------------------------------------------------

TOUCH_MODES = ("auto", "on", "off")
UI_SCALE_MIN, UI_SCALE_MAX, UI_SCALE_STEP = 0.75, 2.0, 0.25
SIM_LIMITS = {
	"sim_latency": (0, 500, 25),
	"sim_jitter": (0, 200, 10),
	"sim_loss": (0, 50, 1),
}

DEFAULT_SETTINGS = {
	"player_name": "Player",
	"language": "en",
	"ui_scale": 1.0,
	"touch": "auto",
	"sim_latency": 0,
	"sim_jitter": 0,
	"sim_loss": 0,
}


def validate_settings(data, defaults=None):
	"""Settings dict with every key valid; bad or missing values take the default."""
	base = dict(DEFAULT_SETTINGS)
	if defaults:
		base.update(defaults)
	out = dict(base)
	if not isinstance(data, dict):
		return out
	name = validate_player_name(data.get("player_name"))
	if name:
		out["player_name"] = name
	if data.get("language") in LANGUAGES:
		out["language"] = data["language"]
	if data.get("touch") in TOUCH_MODES:
		out["touch"] = data["touch"]
	try:
		scale = float(data.get("ui_scale"))
		if UI_SCALE_MIN <= scale <= UI_SCALE_MAX:
			out["ui_scale"] = scale
	except (TypeError, ValueError):
		pass
	for key, (lo, hi, _step) in SIM_LIMITS.items():
		value = data.get(key)
		if isinstance(value, int) and not isinstance(value, bool) and lo <= value <= hi:
			out[key] = value
	return out


def load_settings(path, defaults=None):
	"""Reads settings JSON; missing or broken file -> defaults."""
	import json
	try:
		with open(path, "r", encoding="utf-8") as f:
			data = json.load(f)
	except (OSError, ValueError):
		data = None
	return validate_settings(data, defaults)


def save_settings(path, settings):
	"""Writes settings JSON. Returns False when the file cannot be written."""
	import json
	try:
		with open(path, "w", encoding="utf-8") as f:
			json.dump(validate_settings(settings), f, indent=1, sort_keys=True)
		return True
	except OSError:
		return False
