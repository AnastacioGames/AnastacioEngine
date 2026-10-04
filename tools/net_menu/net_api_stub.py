"""
Stand-in for Range.network (plan section 6.2) while the native module does not exist.

Same surface the menu uses: host(port), join(addr), disconnect(), isServer, clients,
on_connect(fn) / on_disconnect(fn) registration. Extras the plan leaves for later
(on_reject, LAN discovery, ready/chat/start) are optional: the menu checks them with
getattr so the real module can omit them.

Simulation (advance with _tick(dt), the menu calls it every frame when present):
- join("full.test") -> Reject ServerFull; "old.test" -> Reject VersionMismatch;
  "banned.test" -> Reject Banned; "timeout.test" -> Disconnect Timeout after 3 s;
  anything else connects after 0.5 s and two bots join with varying ping.
- host(port) connects immediately as server.
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
		self.isServer = False
		self.isConnected = False
		self.clients = []
		self.localId = None
		self._pending = None  # (kind, time_left, data)
		self._time = 0.0
		self.playerName = "Player"

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
		self._reset()
		host = str(addr).split(":")[0].strip("[]").lower()
		if host in _FAKE_REJECTS:
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

	def send_chat(self, text):
		self._emit(self._chat_cbs, self.localId, text)

	def start_game(self):
		if self.isServer:
			self._emit(self._start_cbs)

	def discover_lan(self):
		"""Returns list of dicts: name, address, players, max_players, ping."""
		return [
			{"name": "Sala do Ana", "address": "192.168.0.10:7777", "players": 2,
				"max_players": 8, "ping": 12},
			{"name": "Full room", "address": "full.test:7777", "players": 8,
				"max_players": 8, "ping": 30},
		]

	# --- simulation ----------------------------------------------------------
	def _tick(self, dt):
		self._time += dt
		for c in self.clients:
			if c.id != self.localId:
				c.ping = max(1, int(c.ping + self._rng.randint(-3, 3)))
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
