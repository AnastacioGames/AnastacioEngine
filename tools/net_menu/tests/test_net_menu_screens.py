"""Pause, Settings and LAN screens (front I): logic, stub and keyboard/gamepad navigation."""

import json
import types
from collections import defaultdict

import pytest

import net_menu_logic as L
import net_api_stub
from conftest import RANGE


# ---------------------------------------------------------------- input mocks

JUST = 1
KEYS = {"up": "UPARROWKEY", "down": "DOWNARROWKEY", "left": "LEFTARROWKEY", "right": "RIGHTARROWKEY",
	"accept": "RETKEY", "back": "ESCKEY"}
PAD = {"up": "JOYSTICKPADUP", "down": "JOYSTICKPADDOWN", "left": "JOYSTICKPADLEFT",
	"right": "JOYSTICKPADRIGHT", "accept": "JOYSTICKA", "back": "JOYSTICKB"}


class _Input:
	def __init__(self):
		self.queue = []


class _Keyboard:
	def __init__(self):
		self.inputs = defaultdict(_Input)


@pytest.fixture
def devices():
	"""Installs a keyboard and joystick 0 on the Range mock."""
	kb = _Keyboard()
	joy = types.SimpleNamespace(activeButtons=[])
	RANGE.events = types.SimpleNamespace(**{name: i + 1 for i, name in enumerate(KEYS.values())})
	RANGE.logic.keyboard = kb
	RANGE.logic.KX_INPUT_JUST_ACTIVATED = JUST
	RANGE.logic.joysticks = [joy]
	for i, name in enumerate(PAD.values()):
		setattr(RANGE.logic, name, 100 + i)
	yield kb, joy
	del RANGE.events
	del RANGE.logic.keyboard
	RANGE.logic.joysticks = []


def keys(m, kb, *actions):
	"""One frame per key press."""
	for act in actions:
		code = getattr(RANGE.events, KEYS[act])
		kb.inputs[code].queue = [JUST]
		m.update()
		kb.inputs[code].queue = []


def pad(m, joy, *actions):
	"""Press and release each gamepad button (two frames each)."""
	for act in actions:
		joy.activeButtons = [getattr(RANGE.logic, PAD[act])]
		m.update()
		joy.activeButtons = []
		m.update()


def _menu(**args):
	import net_menu
	net_api_stub._instance = net_api_stub._StubNetwork(seed=5)
	m = net_menu.NetworkMenu()
	base = {k: (sorted(v)[0] if isinstance(v, set) else v) for k, v in net_menu.NetworkMenu.args.items()}
	base["language"] = "en"
	base["touch"] = "off"
	base.update(args)
	m.start(base)
	return m


def focused(m):
	f = m.state.focus
	items = f._items
	return items[f.index] if 0 <= f.index < len(items) else None


def connect_as_client(m):
	m.state.go(L.JOIN)
	m.net.join("10.0.0.1:7777")
	m.net._tick(1.0)
	assert m.state.screen == L.LOBBY


# ---------------------------------------------------------------- logic

def test_step_value_and_cycle():
	assert L.step_value(1.0, 2, 0.75, 2.0, 0.25) == 1.5
	assert L.step_value(1.9, 5, 0.75, 2.0, 0.25) == 2.0
	assert L.step_value(0, -1, 0, 500, 25) == 0
	assert L.step_value(30, 1, 0, 500, 25) == 50  # snapped to the grid
	assert isinstance(L.step_value(10, 1, 0, 50, 1), int)
	assert L.step_value("x", 1, 0, 50, 1) == 1
	assert L.cycle(("a", "b", "c"), "c") == "a"
	assert L.cycle(("a", "b", "c"), "a", -1) == "c"
	assert L.cycle(("a", "b"), "zz") == "a"


def test_focus_left_right_only_on_focused_item():
	f = L.FocusNav()
	for _ in range(2):
		f.begin_frame()
		f.item("a"), f.item("b")
	f.handle(L.NAV_DOWN)
	f.handle(L.NAV_RIGHT)
	f.handle(L.NAV_RIGHT)
	f.begin_frame()
	f.item("a")
	assert f.consume_adjust("a") == 0
	f.item("b")
	assert f.consume_adjust("b") == 2
	assert f.consume_adjust("b") == 0
	f.handle(L.NAV_LEFT)
	f.end_frame()
	assert f.pending_adjust == 0


@pytest.mark.parametrize("entry,ok", [
	({"name": "A", "address": "10.0.0.2", "port": 7777, "players": 1, "max_players": 4, "ping": 5}, True),
	({"name": "B", "address": "10.0.0.2:7000"}, True),  # stub format of front D
	({"address": "10.0.0.2"}, False),  # no port
	({"address": "bad host", "port": 1}, False),
	({"address": "10.0.0.2", "port": 70000}, False),
	("not a dict", False),
	(None, False),
])
def test_normalize_lan_entry(entry, ok):
	n = L.normalize_lan_entry(entry)
	assert (n is not None) == ok
	if n:
		assert set(n) == {"name", "address", "port", "ws_port", "players", "max_players", "ping",
			"password", "scene", "full"}


def test_lan_servers_sorted_and_deduplicated():
	raw = [
		{"name": "Full", "address": "10.0.0.3", "port": 1, "players": 4, "max_players": 4, "ping": 1},
		{"name": "Slow", "address": "10.0.0.1", "port": 1, "players": 1, "max_players": 4, "ping": 90},
		{"name": "Fast", "address": "10.0.0.2", "port": 1, "players": 1, "max_players": 4, "ping": 9},
		{"name": "Fast", "address": "10.0.0.2", "port": 1, "players": 1, "max_players": 4, "ping": 7},
		{"garbage": True},
		{"name": "Huge", "address": "10.0.0.9", "port": 1, "players": -5, "max_players": 10 ** 9,
			"ping": "x", "password": 1},
	]
	out = L.lan_servers(raw)
	assert [e["name"] for e in out] == ["Huge", "Fast", "Slow", "Full"]
	assert out[1]["ping"] == 7
	assert out[0]["players"] == 0 and out[0]["max_players"] == 65535 and out[0]["password"] is True
	assert out[-1]["full"]
	row = L.format_lan_row(out[-1], "pt")
	assert "Cheia" in row and "4/4" in row
	assert "[Senha]" in L.format_lan_row(out[0], "pt")
	assert L.lan_join_address(out[1]) == "10.0.0.2:1"


def test_settings_validation_and_files(tmp_path):
	s = L.validate_settings({"player_name": "  Bia ", "language": "es", "ui_scale": 1.5, "touch": "on",
		"sim_latency": 100, "sim_loss": 99, "sim_jitter": True})
	assert s["player_name"] == "Bia" and s["language"] == "es" and s["ui_scale"] == 1.5
	assert s["touch"] == "on" and s["sim_latency"] == 100
	assert s["sim_loss"] == 0 and s["sim_jitter"] == 0  # out of range / wrong type
	assert L.validate_settings("junk") == L.DEFAULT_SETTINGS
	assert L.validate_settings({"ui_scale": 9})["ui_scale"] == 1.0

	path = tmp_path / "s.json"
	assert L.load_settings(str(path), {"language": "pt"})["language"] == "pt"  # no file
	assert L.save_settings(str(path), s)
	assert L.load_settings(str(path)) == s
	path.write_text("{broken", encoding="utf-8")
	assert L.load_settings(str(path)) == L.DEFAULT_SETTINGS
	assert not L.save_settings(str(tmp_path / "missing" / "s.json"), s)


def test_languages_complete_for_new_screens():
	new_keys = ["searching", "full", "locked", "room_password", "servers_found", "ui_scale", "touch_mode",
		"touch_auto", "touch_on", "touch_off", "jitter", "reset_defaults", "confirm_disconnect", "yes", "no",
		"lang_en", "lang_pt", "lang_es", "room", "reject_password", "pause", "resume",
		"connected_players", "disconnect", "net_sim", "latency", "loss", "refresh", "no_servers"]
	for lang in L.LANGUAGES:
		for key in new_keys:
			assert L.STRINGS[lang].get(key, "").strip(), (lang, key)
	# Every language name is written in its own language, the same in every table.
	for lang in L.LANGUAGES:
		assert L.STRINGS[lang]["lang_pt"] == "Português"
	assert L.tr("es", "confirm_disconnect").startswith("¿")
	assert L.REJECT_REASONS[7] == "reject_password"


def test_confirm_question_cancelled_by_back():
	s = L.MenuState()
	s.screen = L.PAUSE
	s.ask("confirm_disconnect")
	assert s.back(connected=True) == L.PAUSE and s.confirm is None


# ---------------------------------------------------------------- stub

def test_stub_lan_chat_ready_start():
	n = net_api_stub._StubNetwork(seed=2)
	assert n.discover_lan() == []
	n._tick(0.5)
	assert len(n.discover_lan()) == 2
	n._tick(0.5)
	rooms = n.discover_lan()
	assert [r["name"] for r in rooms] == ["Sala da Ana", "Full room", "Private"]
	assert all(L.normalize_lan_entry(r) for r in rooms)

	chats, starts, rejects = [], [], []
	n.on_chat(lambda cid, text: chats.append((cid, text)))
	n.on_start(lambda: starts.append(1))
	n.on_reject(lambda r, d: rejects.append(r))
	n.send_chat("offline")
	assert chats == []  # not connected
	n.join("192.168.0.11:7790", password="nope")
	n._tick(1.0)
	assert rejects == [net_api_stub.REJECT_WRONG_PASSWORD]
	n.join("192.168.0.11:7790", password="1234")
	n._tick(1.0)
	assert n.isConnected
	n.send_chat("oi")
	assert chats == [(2, "oi")]
	n.set_ready(True)
	n._tick(1.0)
	assert not starts
	n._tick(0.6)
	assert starts == [1]

	n.host(7777)
	assert not n.start_game() or all(c.ready for c in n.clients)
	n.set_ready(True)
	n._tick(1.2)  # the bot joins...
	n._tick(0.1)  # ...and gets ready
	assert n.start_game() and starts == [1, 1]
	n.set_simulation(100, 10, 2)
	assert n.simulation == (100, 10, 2.0)


# ---------------------------------------------------------------- pause screen

def test_pause_keyboard_disconnect_with_confirmation(devices):
	kb, _joy = devices
	m = _menu()
	connect_as_client(m)
	m.state.screen = L.CLOSED
	keys(m, kb, "back")  # Esc in game opens the pause
	assert m.state.screen == L.PAUSE
	assert m.state.focus._items == ["resume", "settings", "disconnect"]
	keys(m, kb, "down", "down")
	assert focused(m) == "disconnect"
	keys(m, kb, "accept")
	assert m.state.confirm == "confirm_disconnect" and m.net.isConnected
	m.update()
	assert m.state.focus._items == ["yes", "no"]
	keys(m, kb, "back")  # Esc cancels the question
	assert m.state.confirm is None and m.state.screen == L.PAUSE
	keys(m, kb, "down", "down", "accept")
	m.update()
	keys(m, kb, "accept")  # yes
	assert m.state.screen == L.MAIN and not m.net.isConnected


def test_pause_gamepad_resume_and_settings(devices):
	_kb, joy = devices
	m = _menu()
	connect_as_client(m)
	m.state.screen = L.PAUSE
	m.update()
	pad(m, joy, "accept")
	assert m.state.screen == L.CLOSED
	pad(m, joy, "back")
	assert m.state.screen == L.PAUSE
	pad(m, joy, "down", "accept")
	assert m.state.screen == L.SETTINGS
	pad(m, joy, "back")
	assert m.state.screen == L.PAUSE


def test_pause_lists_players_and_room():
	m = _menu()
	m.net.host(7777, max_players=4, room_name="Sala 1")
	m.state.screen = L.PAUSE
	RANGE.imgui.text.reset_mock()
	m.update()
	texts = [c.args[0] for c in RANGE.imgui.text.call_args_list]
	assert "Room: Sala 1" in texts
	assert any(t.startswith("Connected players (1/4)") for t in texts)
	assert any("(host)" in t for t in texts)


# ---------------------------------------------------------------- settings screen

def test_settings_keyboard_changes_and_saves(devices, tmp_path):
	kb, _joy = devices
	path = tmp_path / "net.json"
	RANGE.logic.expandPath = lambda p: str(tmp_path / p.lstrip("/"))
	m = _menu(settings_file="//net.json", dev_build=True)
	sims = []
	m.net.set_simulation = lambda *a: sims.append(a)
	m.state.go(L.SETTINGS)
	m.update()
	assert m.state.focus._items == ["kb_player_name", "language", "ui_scale", "touch_mode", "sim_latency", "sim_jitter",
		"sim_loss", "reset_defaults", "back"]
	keys(m, kb, "down", "right")  # language: en -> pt
	assert m.lang == "pt" and m.settings["language"] == "pt"
	keys(m, kb, "down", "right", "right")  # ui scale 1.0 -> 1.5
	assert m.settings["ui_scale"] == 1.5
	m.update()
	assert m.layout["scale"] == pytest.approx(1.5)
	keys(m, kb, "down", "left")  # touch: off -> on (previous option)
	assert m.settings["touch"] == "on" and m.touch
	keys(m, kb, "right")
	assert m.settings["touch"] == "off" and not m.touch
	keys(m, kb, "down", "right", "right")  # latency 0 -> 50
	assert m.settings["sim_latency"] == 50 and sims[-1] == (50, 0, 0)
	keys(m, kb, "down", "down", "accept")  # loss: accept steps up
	assert m.settings["sim_loss"] == 1
	m.fields["player_name"] = "Bia"
	keys(m, kb, "back")  # Esc saves and goes back
	assert m.state.screen == L.MAIN
	saved = json.loads(path.read_text(encoding="utf-8"))
	assert saved["language"] == "pt" and saved["player_name"] == "Bia" and saved["sim_latency"] == 50
	assert m.net.playerName == "Bia"

	# A new menu starts with the saved settings.
	m2 = _menu(settings_file="//net.json", dev_build=True)
	assert m2.lang == "pt" and m2.fields["player_name"] == "Bia" and m2.settings["ui_scale"] == 1.5
	RANGE.logic.expandPath = lambda p: p


def test_settings_invalid_name_stays_and_reset(devices):
	_kb, joy = devices
	m = _menu()
	m.state.go(L.SETTINGS)
	m.update()
	m.fields["player_name"] = ""
	pad(m, joy, "back")
	assert m.state.screen == L.SETTINGS and m.errors["player_name"] == "err_name"
	m.settings["language"] = m.lang = "es"
	m.settings["ui_scale"] = 2.0
	m.update()
	assert focused(m) == "kb_player_name"
	pad(m, joy, "down", "down", "down", "down")
	assert focused(m) == "reset_defaults"
	pad(m, joy, "accept")
	assert m.lang == "en" and m.settings["ui_scale"] == 1.0 and m.fields["player_name"] == "Player"
	pad(m, joy, "down", "accept")
	assert m.state.screen == L.MAIN


def test_settings_mouse_stepper_buttons():
	m = _menu()
	m.state.go(L.SETTINGS)
	RANGE.imgui.button.side_effect = lambda label, w=0, h=0: label == "+##ui_scale_inc"
	try:
		m.update()
	finally:
		RANGE.imgui.button.side_effect = None
	assert m.settings["ui_scale"] == 1.25
	# The simulator rows only exist in development builds.
	assert "sim_latency" not in m.state.focus._items


# ---------------------------------------------------------------- LAN screen

def _open_lan(m):
	m.state.go(L.LAN)
	m.net.discover_lan()  # starts the simulated search
	m.net._tick(1.0)
	m.lan_next_refresh = 0.0
	m.update()
	assert len(m.lan_list) == 3


def test_lan_lists_rooms_and_gamepad_joins(devices):
	_kb, joy = devices
	m = _menu()
	_open_lan(m)
	assert [e["name"] for e in m.lan_list] == ["Sala da Ana", "Private", "Full room"]
	assert m.state.focus._items == ["lan_0", "lan_1", "lan_2", "refresh", "back"]
	pad(m, joy, "accept")  # select
	assert m.lan_sel == 0 and not m.state.status
	assert "connect" in m.state.focus._items
	pad(m, joy, "accept")  # second press joins
	assert m.state.status == "connecting"
	m.net._tick(1.0)
	assert m.state.screen == L.LOBBY


def test_lan_full_room_shows_notice(devices):
	kb, _joy = devices
	m = _menu()
	_open_lan(m)
	keys(m, kb, "down", "down", "accept", "accept")
	assert m.state.notice == "reject_full" and m.state.notice_detail == "8/8"
	keys(m, kb, "back")
	assert m.state.notice is None and m.state.screen == L.LAN


def test_lan_password_room(devices):
	kb, _joy = devices
	m = _menu()
	_open_lan(m)
	keys(m, kb, "down", "accept", "accept")
	assert m.lan_password_for is not None and m.lan_password_for["name"] == "Private"
	m.update()
	assert m.state.focus._items == ["kb_lan_password", "connect", "back"]
	m.fields["lan_password"] = "wrong"
	keys(m, kb, "down", "accept")
	m.net._tick(1.0)
	assert m.state.notice == "reject_password"
	keys(m, kb, "back")  # dismiss
	assert m.state.notice is None and m.state.screen == L.LAN and m.lan_sel == 1
	m.update()
	assert focused(m) == "lan_1"
	keys(m, kb, "accept")  # the selected row asks again
	assert m.lan_password_for is not None
	keys(m, kb, "back")  # Esc leaves the password prompt only
	assert m.lan_password_for is None and m.state.screen == L.LAN
	m.update()
	assert focused(m) == "lan_1"
	keys(m, kb, "accept")
	m.update()
	keys(m, kb, "accept")  # accept on the text field opens the on-screen keyboard
	assert m.osk.active and m.osk.field == "lan_password"
	for k in "1234":
		m.osk.press(k)
	m.fields.update([m.osk.press(L.KEY_DONE)])
	keys(m, kb, "down", "accept")
	m.net._tick(1.0)
	assert m.state.screen == L.LOBBY


def test_lan_mouse_double_click_and_refresh_keeps_selection():
	m = _menu()
	_open_lan(m)
	m.lan_sel = 1
	m._refresh_lan()
	assert m.lan_list[m.lan_sel]["name"] == "Private"
	RANGE.imgui.button.side_effect = lambda label, w=0, h=0: label.endswith("##lan_0")
	try:
		m.update()
		assert m.lan_sel == 0
		m.update()
	finally:
		RANGE.imgui.button.side_effect = None
	assert m.state.status == "connecting"


def test_lan_empty_list_text():
	m = _menu()
	m.state.go(L.LAN)
	RANGE.imgui.text.reset_mock()
	m.update()
	texts = [c.args[0] for c in RANGE.imgui.text.call_args_list]
	assert "Searching..." in texts and "No servers found" in texts


@pytest.mark.parametrize("lang", L.LANGUAGES)
def test_new_screens_draw_in_every_language(lang):
	m = _menu(language=lang, dev_build=True)
	connect_as_client(m)
	for screen in (L.PAUSE, L.SETTINGS, L.LAN):
		m.state.screen = screen
		m.update()
	m.state.ask("confirm_disconnect")
	m.update()
	m.lan_password_for = {"name": "x", "address": "10.0.0.1", "port": 1}
	m.state.confirm = None
	m.state.screen = L.LAN
	m.update()


# ---------------------------------------------------------------- fuzz (fixed seed)

def _random_value(rng):
	kind = rng.randrange(8)
	if kind == 0:
		return rng.randint(-10 ** 6, 10 ** 6)
	if kind == 1:
		return rng.uniform(-1e6, 1e6)
	if kind == 2:
		return "".join(chr(rng.randrange(0x20, 0x2FF)) for _ in range(rng.randrange(0, 80)))
	if kind == 3:
		return None
	if kind == 4:
		return rng.random() < 0.5
	if kind == 5:
		return [rng.randrange(256) for _ in range(rng.randrange(4))]
	if kind == 6:
		return "{}.{}.{}.{}:{}".format(*(rng.randrange(-5, 300) for _ in range(5)))
	return float("nan")


def test_fuzz_lan_entries_and_settings():
	import random
	rng = random.Random(0xF1)
	lan_keys = ["name", "address", "port", "ws_port", "players", "max_players", "ping", "password", "scene"]
	set_keys = list(L.DEFAULT_SETTINGS)
	valid = 0
	for _ in range(100000):
		entry = {k: _random_value(rng) for k in lan_keys if rng.random() < 0.7}
		if rng.random() < 0.5:
			entry["address"] = "10.{}.{}.{}".format(rng.randrange(256), rng.randrange(256), rng.randrange(256))
			entry["port"] = rng.randrange(-10, 70000)
		n = L.normalize_lan_entry(entry)
		if n is not None:
			valid += 1
			assert 1 <= n["port"] <= 65535 and 0 <= n["players"] <= 65535 and len(n["name"]) <= 64
			L.format_lan_row(n, "pt")
		data = {k: _random_value(rng) for k in set_keys if rng.random() < 0.5}
		s = L.validate_settings(data)
		assert set(s) == set(L.DEFAULT_SETTINGS) and s["language"] in L.LANGUAGES
		assert L.UI_SCALE_MIN <= s["ui_scale"] <= L.UI_SCALE_MAX
	assert valid > 1000


def test_fuzz_regressions():
	# Found by the fuzz test: non-ASCII digits and non-string values.
	assert L.validate_port("²") is None and L.validate_port("٣٣") is None
	assert L.validate_player_name(3.5) is None and L.validate_host(None) is None
	assert L.parse_address(7777, 1) is None and L.parse_join_target(b"x", 1) is None
	assert L.validate_chat(["x"]) is None and L.normalize_room_code(12345) is None
