"""
Stand-in for Range.network (plan section 6.2) while the native module does not exist.

Same surface the menu uses: host(port), join(addr), disconnect(), isServer, clients,
on_connect(fn) / on_disconnect(fn) registration. Extras the plan leaves for later
(on_reject, LAN discovery, ready/chat/start) are optional: the menu checks them with
getattr so the real module can omit them.

Simulation (advance with _tick(dt), the menu calls it every frame when present):
- join("full.test") -> Reject ServerFull; "old.test" -> Reject VersionMismatch;
  "banned.test" -> Reject Banned; "timeout.test" -> Disconnect Timeout after 3 s;
  a LAN room with password rejects a wrong one (provisional reason 7, see NOTES-D.md);
  anything else connects after 0.5 s and two bots join with varying ping.
- host(port) connects immediately as server; bots join and get ready after a while.
- discover_lan(): LAN rooms answer over time (format of NET_LanDiscovery, front H).
- send_chat echoes to on_chat; set_ready on a client makes the host bot start the game
  1.5 s later (on_start); start_game() on the server needs every player ready.
- set_simulation(latency_ms, jitter_ms, loss_percent) adds to the shown pings.
"""

import random

SERVER = 0
IS_STUB = True

# Protocol reasons (docs/multiplayer-protocol.md section 5).
REJECT_VERSION_MISMATCH = 1
REJECT_SCENE_MISMATCH = 2
REJECT_SERVER_FULL = 3
REJECT_BAD_TOKEN = 4
REJECT_BANNED = 5
REJECT_GAME_IN_PROGRESS = 6
DISCONNECT_QUIT = 1
DISCONNECT_TIMEOUT = 2
DISCONNECT_KICKED = 3
DISCONNECT_PROTOCOL_VIOLATION = 4
DISCONNECT_SERVER_SHUTDOWN = 5
# Provisional: not in the contract yet (proposed in NOTES-D.md).
REJECT_WRONG_PASSWORD = 7

# Simulated LAN rooms: (seconds until they answer, entry).
_LAN_ROOMS = (
	(0.1, {"name": "Sala da Ana", "address": "192.168.0.10", "port": 7777, "ws_port": 7778,
		"players": 2, "max_players": 8, "ping": 12, "password": False, "scene": "Arena"}),
	(0.4, {"name": "Full room", "address": "192.168.0.12", "port": 7777, "ws_port": 0,
		"players": 8, "max_players": 8, "ping": 30, "password": False, "scene": "Arena"}),
	(0.8, {"name": "Private", "address": "192.168.0.11", "port": 7790, "ws_port": 0,
		"players": 1, "max_players": 4, "ping": 18, "password": True, "scene": "Docks"}),
)
_LAN_PASSWORDS = {"192.168.0.11": "1234"}

_FAKE_REJECTS = {
	"full.test": (REJECT_SERVER_FULL, "8/8"),
	"old.test": (REJECT_VERSION_MISMATCH, "server protocol 2"),
	"banned.test": (REJECT_BANNED, ""),
}


class StubClient:
	def __init__(self, client_id, name, ping, is_host=False):
		self.id = client_id
		self.name = name
		self.ping = ping
		self.ready = False
		self.isHost = is_host


class _StubNetwork:
	def __init__(self, seed=1234):
		self._rng = random.Random(seed)
		self._reset()
		self._connect_cbs = []
		self._disconnect_cbs = []
		self._reject_cbs = []
		self._chat_cbs = []
		self._start_cbs = []

	def _reset(self):
		name = getattr(self, "playerName", "Player")
		self.isServer = False
		self.isConnected = False
		self.clients = []
		self.localId = None
		self._pending = None  # (kind, time_left, data)
		self._time = 0.0
		self._start_in = None
		self._lan_since = None
		self.playerName = name
		self.maxPlayers = 0
		self.roomName = ""
		if not hasattr(self, "simulation"):
			self.simulation = (0, 0, 0)

	# --- events --------------------------------------------------------------
	def on_connect(self, fn):
		self._connect_cbs.append(fn)
		return fn

	def on_disconnect(self, fn):
		self._disconnect_cbs.append(fn)
		return fn

	def on_reject(self, fn):
		self._reject_cbs.append(fn)
		return fn

	def on_chat(self, fn):
		self._chat_cbs.append(fn)
		return fn

	def on_start(self, fn):
		self._start_cbs.append(fn)
		return fn

	@staticmethod
	def _emit(cbs, *args):
		for cb in list(cbs):
			cb(*args)

	# --- API -----------------------------------------------------------------
	def host(self, port, max_players=8, room_name="", password=""):
		if not 1 <= int(port) <= 65535:
			raise ValueError("port out of range")
		self._reset()
		self.isServer = True
		self.isConnected = True
		self.localId = 0
		self.maxPlayers = max_players
		self.roomName = room_name
		self.clients = [StubClient(0, self.playerName, 0, is_host=True)]
		self._emit(self._connect_cbs, 0)
		self._pending = ("bot", 1.0, None)

	def join(self, addr, password=""):
		lan_since = self._lan_since
		self._reset()
		self._lan_since = lan_since
		host = str(addr).split(":")[0].strip("[]").lower()
		if host in _LAN_PASSWORDS and password != _LAN_PASSWORDS[host]:
			self._pending = ("reject", 0.3, (REJECT_WRONG_PASSWORD, ""))
		elif host in _FAKE_REJECTS:
			self._pending = ("reject", 0.3, _FAKE_REJECTS[host])
		elif host == "timeout.test":
			self._pending = ("timeout", 3.0, None)
		else:
			self._pending = ("connect", 0.5, None)

	def disconnect(self):
		was = self.isConnected
		self._reset()
		if was:
			self._emit(self._disconnect_cbs, DISCONNECT_QUIT, "")

	def set_ready(self, ready):
		for c in self.clients:
			if c.id == self.localId:
				c.ready = bool(ready)
		if not self.isServer and self.isConnected:
			# The host bot starts once this client is ready.
			self._start_in = 1.5 if ready else None

	def send_chat(self, text):
		text = str(text)[:200]
		if text and self.isConnected:
			self._emit(self._chat_cbs, self.localId, text)

	def start_game(self):
		"""Server only, when every player is ready. Returns True when the game started."""
		if not self.isServer or not all(c.ready for c in self.clients):
			return False
		self._emit(self._start_cbs)
		return True

	def set_simulation(self, latency_ms=0, jitter_ms=0, loss_percent=0):
		self.simulation = (int(latency_ms), int(jitter_ms), float(loss_percent))

	def discover_lan(self):
		"""Rooms answered so far (non-blocking; the first call starts the search).

		List of dicts: name, address (IPv4), port (ENet), ws_port, players, max_players,
		ping (ms), password (bool), scene.
		"""
		if self._lan_since is None:
			self._lan_since = self._time
		age = self._time - self._lan_since
		out = []
		for delay, room in _LAN_ROOMS:
			if age >= delay:
				entry = dict(room)
				entry["ping"] = max(1, room["ping"] + self._rng.randint(-2, 2) + self.simulation[0])
				out.append(entry)
		return out

	# --- simulation ----------------------------------------------------------
	def _tick(self, dt):
		self._time += dt
		for c in self.clients:
			if c.id != self.localId:
				c.ping = max(1, int(c.ping + self._rng.randint(-3, 3)))
				if self._time > 1.0:
					c.ready = True  # bots get ready after a second
		if self._start_in is not None:
			self._start_in -= dt
			if self._start_in <= 0:
				self._start_in = None
				self._emit(self._start_cbs)
		if not self._pending:
			return
		kind, left, data = self._pending
		left -= dt
		if left > 0:
			self._pending = (kind, left, data)
			return
		self._pending = None
		if kind == "connect":
			self.isConnected = True
			self.localId = 2
			self.clients = [
				StubClient(0, "Host", 25, is_host=True),
				StubClient(1, "Bot", 60),
				StubClient(2, self.playerName, 0),
			]
			self._emit(self._connect_cbs, 2)
		elif kind == "reject":
			self._emit(self._reject_cbs, data[0], data[1])
		elif kind == "timeout":
			self._emit(self._disconnect_cbs, DISCONNECT_TIMEOUT, "")
		elif kind == "bot":
			self.clients.append(StubClient(len(self.clients), "Bot", 40))


_instance = _StubNetwork()


def get():
	return _instance


def load_network():
	"""Real Range.network when available, else this stub."""
	try:
		import Range.network as net  # noqa: F401
		return net
	except ImportError:
		return _instance
