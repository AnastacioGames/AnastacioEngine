import re

import pytest

import net_menu_logic as L
import net_api_stub
from conftest import RANGE


# ---------------------------------------------------------------- state machine

def test_initial_and_basic_navigation():
	s = L.MenuState()
	assert s.screen == L.MAIN
	assert s.go(L.HOST) and s.screen == L.HOST
	assert not s.go(L.PAUSE)  # not allowed from host
	assert s.back() == L.MAIN


def test_every_screen_has_transitions_and_targets_exist():
	for src, targets in L.TRANSITIONS.items():
		assert src in L.SCREENS
		assert targets <= set(L.SCREENS)
	assert set(L.TRANSITIONS) == set(L.SCREENS) - set()  # all screens covered


def test_hidden_screens_blocked():
	s = L.MenuState(hidden_screens=[L.LAN])
	assert not s.go(L.LAN)
	assert s.go(L.JOIN)


def test_unknown_screen_rejected():
	assert not L.MenuState().go("nope")


def test_settings_returns_to_origin():
	s = L.MenuState()
	s.go(L.SETTINGS)
	assert s.back() == L.MAIN
	s.screen = L.PAUSE
	s.go(L.SETTINGS)
	assert s.back() == L.PAUSE


def test_connect_flow_to_lobby_and_game():
	s = L.MenuState()
	s.go(L.JOIN)
	s.on_connecting()
	assert s.status == "connecting"
	s.on_connected()
	assert s.screen == L.LOBBY and s.status is None
	s.on_game_started()
	assert s.screen == L.CLOSED and not s.visible


def test_pause_toggle_only_when_connected():
	s = L.MenuState()
	s.screen = L.CLOSED
	assert s.back(connected=False) == L.CLOSED
	assert s.back(connected=True) == L.PAUSE
	assert s.back(connected=True) == L.CLOSED


@pytest.mark.parametrize("reason,key", [(1, "reject_version"), (3, "reject_full"),
	(6, "reject_in_progress"), (99, "reject_unknown")])
def test_reject_notice(reason, key):
	s = L.MenuState()
	s.go(L.JOIN)
	s.on_connecting()
	s.on_rejected(reason, "x")
	assert s.notice == key and s.notice_detail == "x" and s.status is None
	assert s.screen == L.JOIN
	s.back()  # first back dismisses notice
	assert s.notice is None and s.screen == L.JOIN


def test_disconnect_notice_and_return_to_main():
	s = L.MenuState()
	s.screen = L.CLOSED
	s.on_disconnected(2)
	assert s.notice == "disc_timeout" and s.screen == L.MAIN and s.visible
	s.dismiss_notice()
	s.on_disconnected(1)  # user quit: no modal
	assert s.notice is None


def test_all_reason_keys_translated():
	for key in list(L.REJECT_REASONS.values()) + list(L.DISCONNECT_REASONS.values()) + \
			["reject_unknown", "disc_unknown"]:
		for lang in L.LANGUAGES:
			assert key in L.STRINGS[lang]


# ---------------------------------------------------------------- validation

@pytest.mark.parametrize("v,exp", [("7777", 7777), (1, 1), (65535, 65535), ("0", None),
	("65536", None), ("abc", None), ("", None), (" 80 ", 80), ("-1", None), (True, None),
	("123456", None)])
def test_validate_port(v, exp):
	assert L.validate_port(v) == exp


@pytest.mark.parametrize("v,exp", [("127.0.0.1", "127.0.0.1"), ("::1", "::1"),
	("localhost", "localhost"), ("My-Host.lan", "my-host.lan"), ("999.1.1.1", None),
	("bad_host", None), ("-x.com", None), ("", None), ("a" * 64, None)])
def test_validate_host(v, exp):
	assert L.validate_host(v) == exp


@pytest.mark.parametrize("v,exp", [
	("10.0.0.2", ("10.0.0.2", 7777)),
	("10.0.0.2:9000", ("10.0.0.2", 9000)),
	("[::1]:9000", ("::1", 9000)),
	("::1", ("::1", 7777)),
	("host.lan:0", None),
	("10.0.0.2:", None),
	("[::1", None),
	("[::1]x", None),
])
def test_parse_address(v, exp):
	assert L.parse_address(v, 7777) == exp


@pytest.mark.parametrize("v,exp", [("ab12", "AB12"), ("AB-12-CD", "AB12CD"), ("abc", None),
	("ABCDEFGHI", None), ("AB!2", None), ("", None)])
def test_room_code(v, exp):
	assert L.normalize_room_code(v) == exp


def test_join_target():
	assert L.parse_join_target("k3x9", 7777) == ("code", "K3X9")
	assert L.parse_join_target("localhost", 7777) == ("addr", ("localhost", 7777))
	assert L.parse_join_target("1.2.3.4:5", 7777) == ("addr", ("1.2.3.4", 5))
	assert L.parse_join_target("!!", 7777) is None
	assert L.parse_join_target("", 7777) is None


def test_names_players_chat():
	assert L.validate_player_name(" Ana ") == "Ana"
	assert L.validate_player_name("") is None
	assert L.validate_player_name("x" * 17) is None
	assert L.validate_player_name("a\x01") is None
	assert L.validate_max_players("8") == 8
	assert L.validate_max_players(1) is None and L.validate_max_players(65) is None
	assert L.validate_max_players("x") is None
	long = "é" * 150  # 300 bytes
	out = L.validate_chat(long)
	assert len(out.encode("utf-8")) <= 200 and out == "é" * 100
	assert L.validate_chat("   ") is None


# ---------------------------------------------------------------- languages

def test_language_tables_complete():
	keys = set(L.STRINGS["en"])
	assert set(L.LANGUAGES) == set(L.STRINGS)
	for lang in L.LANGUAGES:
		assert set(L.STRINGS[lang]) == keys, lang
		for k, v in L.STRINGS[lang].items():
			assert isinstance(v, str) and v.strip(), (lang, k)


def test_all_keys_used_by_menu_exist():
	import pathlib
	src = (pathlib.Path(L.__file__).parent / "net_menu.py").read_text(encoding="utf-8")
	used = set(re.findall(r'_t\("([a-z_]+)"\)', src))
	used |= set(re.findall(r'_button\("([a-z_]+)"\)', src))
	used |= set(re.findall(r'_input\("[a-z_]+", "([a-z_]+)"', src))
	missing = used - set(L.STRINGS["en"])
	assert not missing, missing


def test_tr_fallback():
	assert L.tr("pt", "join") == "Entrar"
	assert L.tr("xx", "join") == "Join"
	assert L.tr("es", "nope") == "nope"


# ---------------------------------------------------------------- theme / layout / input helpers

def test_theme_from_args():
	t = L.build_theme({"accent_color": "#FF0000", "text_color": (0, 1, 0), "focus_color": "zz"})
	assert t["accent"] == (1.0, 0.0, 0.0, 1.0)
	assert t["text"] == (0.0, 1.0, 0.0, 1.0)
	assert t["focus"] == L.DEFAULT_THEME["focus"]
	assert L.parse_color("#00000080", None)[3] == pytest.approx(128 / 255)


@pytest.mark.parametrize("w,h", [(320, 240), (800, 480), (1920, 1080), (3840, 2160)])
def test_touch_buttons_min_48(w, h):
	lay = L.compute_layout(w, h, touch=True)
	assert lay["button_h"] >= 48
	assert lay["win_w"] <= w and lay["win_h"] <= h


def test_layout_scales_with_screen():
	small = L.compute_layout(1280, 720)
	big = L.compute_layout(2560, 1440)
	assert big["scale"] == pytest.approx(2 * small["scale"])
	assert big["button_h"] > small["button_h"]


def test_detect_touch():
	assert L.detect_touch("emscripten")
	assert L.detect_touch("linux-android")
	assert not L.detect_touch("win32")
	assert L.detect_touch("win32", "on")
	assert not L.detect_touch("emscripten", "off")


def test_onscreen_keyboard():
	k = L.OnScreenKeyboard()
	k.open("address", "1", max_length=4)
	for key in ("A", L.KEY_SHIFT, "B", ".", "C"):
		k.press(key)
	assert k.text == "1aB."  # max length reached, C dropped
	k.press(L.KEY_BACKSPACE)
	assert k.press(L.KEY_DONE) == ("address", "1aB")
	assert not k.active
	assert k.rows()[-1][-1] == L.KEY_DONE


def test_focus_nav():
	f = L.FocusNav()
	for frame in range(2):
		f.begin_frame()
		f.item("a"), f.item("b"), f.item("c")
	f.handle(L.NAV_UP)
	assert f.index == 2
	f.handle(L.NAV_DOWN)
	assert f.index == 0
	f.handle(L.NAV_ACCEPT)
	f.begin_frame()
	f.item("a")
	assert f.consume_accept("a")
	assert not f.consume_accept("a")


# ---------------------------------------------------------------- stub API

def _stub():
	return net_api_stub._StubNetwork(seed=1)


def test_stub_join_connects():
	n = _stub()
	got = []
	n.on_connect(got.append)
	n.join("1.2.3.4:7777")
	n._tick(0.2)
	assert not got
	n._tick(0.5)
	assert got == [2] and n.isConnected and len(n.clients) == 3


@pytest.mark.parametrize("host,reason", [("full.test", 3), ("old.test", 1), ("banned.test", 5)])
def test_stub_rejects(host, reason):
	n = _stub()
	got = []
	n.on_reject(lambda r, d: got.append(r))
	n.join(host + ":7777")
	n._tick(1.0)
	assert got == [reason]


def test_stub_timeout_and_host_and_disconnect():
	n = _stub()
	got = []
	n.on_disconnect(lambda r, d: got.append(r))
	n.join("timeout.test")
	n._tick(3.1)
	assert got == [2]
	n.host(7777)
	assert n.isServer and n.clients[0].isHost
	n._tick(1.1)
	assert len(n.clients) == 2
	n.disconnect()
	assert got == [2, 1] and not n.isServer
	with pytest.raises(ValueError):
		n.host(0)


def test_load_network_falls_back_to_stub():
	assert net_api_stub.load_network() is net_api_stub.get()


# ---------------------------------------------------------------- component smoke (mocked imgui)

def _menu(**args):
	import net_menu
	net_api_stub._instance = net_api_stub._StubNetwork(seed=3)
	m = net_menu.NetworkMenu()
	base = {k: (sorted(v)[0] if isinstance(v, set) else v) for k, v in net_menu.NetworkMenu.args.items()}
	base["language"] = "en"
	base["touch"] = "off"
	base.update(args)
	m.start(base)
	return m


def test_component_draws_every_screen():
	m = _menu()
	for screen in L.SCREENS:
		m.state.screen = screen
		m.update()
	RANGE.imgui.begin.assert_called()


def test_component_join_flow_with_stub():
	m = _menu()
	m.state.go(L.JOIN)
	m.fields["address"] = "full.test"
	m._call = None
	# simulate clicking "connect": validate + join directly through logic path
	target = L.parse_join_target(m.fields["address"], m.default_port)
	m.state.on_connecting()
	m.net.join("{}:{}".format(*target[1]))
	m.net._tick(1.0)
	assert m.state.notice == "reject_full"
	m.state.dismiss_notice()
	m.net.join("10.0.0.1:7777")
	m.net._tick(1.0)
	assert m.state.screen == L.LOBBY
	m._leave()
	assert m.state.screen == L.MAIN and not m.net.isConnected


def test_component_host_validation_errors():
	m = _menu()
	m.state.go(L.HOST)
	m.fields["port"] = "99999"
	m.fields["room_name"] = ""
	RANGE.imgui.button.side_effect = lambda label, w=0, h=0: label.endswith("##create")
	try:
		m.update()
	finally:
		RANGE.imgui.button.side_effect = None
	assert m.errors == {"port": "err_port", "room_name": "err_name"}
	assert not m.net.isServer


def test_component_host_success_goes_to_lobby():
	m = _menu()
	m.state.go(L.HOST)
	RANGE.imgui.button.side_effect = lambda label, w=0, h=0: label.endswith("##create")
	try:
		m.update()
	finally:
		RANGE.imgui.button.side_effect = None
	assert m.net.isServer and m.state.screen == L.LOBBY


def test_component_touch_uses_onscreen_keyboard():
	m = _menu(touch="on")
	m.state.go(L.JOIN)
	RANGE.imgui.button.side_effect = lambda label, w=0, h=0: label.endswith("##kb_address")
	try:
		m.update()
	finally:
		RANGE.imgui.button.side_effect = None
	assert m.osk.active and m.osk.field == "address"
	assert m.layout["button_h"] >= 48
