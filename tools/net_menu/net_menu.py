"""
NetworkMenu: ready-made multiplayer menu (plan section 6.4) drawn with Range.imgui.

Usage: copy net_menu.py, net_menu_logic.py and net_api_stub.py next to the game's
scripts, then add the component "net_menu.NetworkMenu" to any object (e.g. the camera).
Uses Range.network when it exists, otherwise net_api_stub (simulated session).

Screen logic lives in net_menu_logic (tested without the engine); this file only
draws and forwards input.
"""

from collections import OrderedDict
import sys
import time

import Range
import Range.imgui as imgui

import net_menu_logic as L
import net_api_stub

COL_TEXT = getattr(imgui, "COL_TEXT", 0)
COL_WINDOW_BG = getattr(imgui, "COL_WINDOW_BG", 2)
COL_POPUP_BG = getattr(imgui, "COL_POPUP_BG", 4)
COL_BUTTON = getattr(imgui, "COL_BUTTON", 21)
COL_BUTTON_HOVERED = getattr(imgui, "COL_BUTTON_HOVERED", 22)
COL_BUTTON_ACTIVE = getattr(imgui, "COL_BUTTON_ACTIVE", 23)
COND_ALWAYS = getattr(imgui, "COND_ALWAYS", 1)

NOTICE_POPUP = "##net_notice"


def _brighter(c, k=1.2):
	return (min(1.0, c[0] * k), min(1.0, c[1] * k), min(1.0, c[2] * k), c[3])


class NetworkMenu(Range.types.KX_PythonComponent):
	args = OrderedDict([
		("title", "Multiplayer"),
		("language", {"en", "pt", "es"}),
		("default_port", 7777),
		("max_players", 8),
		("touch", {"auto", "on", "off"}),
		("ui_scale", 1.0),
		("font_path", ""),
		("font_size", 18.0),
		("accent_color", "#338CF2"),
		("window_bg_color", "#16181CF0"),
		("text_color", "#F2F2F7"),
		("button_color", "#2E333D"),
		("focus_color", "#FFCC33"),
		("show_lan", True),
		("show_settings", True),
		("dev_build", False),
		("open_on_start", True),
	])

	def start(self, args):
		self.cfg = dict(args)
		lang = args.get("language", "en")
		self.lang = lang if lang in L.LANGUAGES else "en"
		hidden = []
		if not args.get("show_lan", True):
			hidden.append(L.LAN)
		if not args.get("show_settings", True):
			hidden.append(L.SETTINGS)
		self.state = L.MenuState(hidden)
		if not args.get("open_on_start", True):
			self.state.screen = L.CLOSED
		self.theme = L.build_theme(args)
		self.touch = L.detect_touch(sys.platform, args.get("touch", "auto"))
		self.osk = L.OnScreenKeyboard()
		self.font = None
		path = args.get("font_path") or ""
		if path:
			try:
				self.font = imgui.load_font(Range.logic.expandPath(path), float(args.get("font_size", 18.0)))
			except (IOError, OSError) as e:
				print("[NetworkMenu] font:", e)

		self.default_port = L.validate_port(args.get("default_port", 7777)) or 7777
		self.fields = {
			"room_name": "Room",
			"max_players": int(args.get("max_players", 8)),
			"port": str(self.default_port),
			"password": "",
			"address": "",
			"chat": "",
			"player_name": "Player",
		}
		self.errors = {}
		self.lan_list = []
		self.lan_sel = -1
		self.lan_last_click = (-1, 0.0)
		self.chat_log = []
		self.ready = False
		self.sim_latency = 0
		self.sim_loss = 0
		self._prev_buttons = set()
		self._last_time = time.monotonic()

		self.net = net_api_stub.load_network()
		self._register_events()

	# ------------------------------------------------------------------ network
	def _register_events(self):
		net = self.net
		for name, fn in (("on_connect", self._ev_connect), ("on_disconnect", self._ev_disconnect),
				("on_reject", self._ev_reject), ("on_chat", self._ev_chat),
				("on_start", self._ev_start)):
			reg = getattr(net, name, None)
			if callable(reg):
				reg(fn)

	def _ev_connect(self, client_id=None):
		self.state.on_connected()

	def _ev_disconnect(self, reason=1, detail=""):
		self.state.on_disconnected(reason, detail)

	def _ev_reject(self, reason=0, detail=""):
		self.state.on_rejected(reason, detail)

	def _ev_chat(self, client_id, text):
		self.chat_log.append("{}: {}".format(self._client_name(client_id), text))
		del self.chat_log[:-8]

	def _ev_start(self):
		self.state.on_game_started()

	def _client_name(self, cid):
		for c in getattr(self.net, "clients", []) or []:
			if getattr(c, "id", None) == cid:
				return getattr(c, "name", str(cid))
		return str(cid)

	def _connected(self):
		return bool(getattr(self.net, "isConnected", False) or getattr(self.net, "isServer", False))

	# ------------------------------------------------------------------ input
	def _read_nav(self):
		actions = []
		kb = getattr(Range.logic, "keyboard", None)
		ev = getattr(Range, "events", None)
		just = getattr(Range.logic, "KX_INPUT_JUST_ACTIVATED", None)
		if kb is not None and ev is not None and not imgui.get_io_want_capture_keyboard():
			for key, act in (("UPARROWKEY", L.NAV_UP), ("DOWNARROWKEY", L.NAV_DOWN),
					("RETKEY", L.NAV_ACCEPT), ("ESCKEY", L.NAV_BACK)):
				code = getattr(ev, key, None)
				if code is not None and just in kb.inputs[code].queue:
					actions.append(act)
		joys = getattr(Range.logic, "joysticks", None) or []
		joy = joys[0] if joys else None
		if joy is not None:
			now = set(joy.activeButtons)
			pressed = now - self._prev_buttons
			self._prev_buttons = now
			for name, act in (("JOYSTICKPADUP", L.NAV_UP), ("JOYSTICKPADDOWN", L.NAV_DOWN),
					("JOYSTICKA", L.NAV_ACCEPT), ("JOYSTICKB", L.NAV_BACK)):
				code = getattr(Range.logic, name, None)
				if code is not None and code in pressed:
					actions.append(act)
		return actions

	# ------------------------------------------------------------------ frame
	def update(self):
		now = time.monotonic()
		dt, self._last_time = now - self._last_time, now
		tick = getattr(self.net, "_tick", None)
		if callable(tick):
			tick(dt)

		for act in self._read_nav():
			if act == L.NAV_BACK:
				if self.osk.active:
					self.osk.field = None
				elif self.state.screen == L.LOBBY:
					self._leave()
				else:
					self.state.back(connected=self._connected())
			else:
				self.state.focus.handle(act)

		if not self.state.visible:
			imgui.set_game_ui_open(False)
			return
		imgui.set_game_ui_open(True)
		self._draw()

	def _t(self, key):
		return L.tr(self.lang, key)

	def _draw(self):
		w, h = imgui.get_display_size()
		self.layout = L.compute_layout(w, h, self.touch, self.cfg.get("ui_scale", 1.0))
		lay = self.layout
		th = self.theme
		self.state.focus.begin_frame()

		if self.font is not None:
			imgui.push_font(self.font)
		imgui.push_style_color(COL_WINDOW_BG, *th["window_bg"])
		imgui.push_style_color(COL_POPUP_BG, *th["window_bg"])
		imgui.push_style_color(COL_TEXT, *th["text"])
		imgui.push_style_color(COL_BUTTON, *th["button"])
		imgui.push_style_color(COL_BUTTON_HOVERED, *th["accent"])
		imgui.push_style_color(COL_BUTTON_ACTIVE, *_brighter(th["accent"]))

		if self.state.screen != L.CLOSED:
			imgui.set_next_window_pos(lay["win_x"], lay["win_y"], COND_ALWAYS)
			imgui.set_next_window_size(lay["win_w"], lay["win_h"], COND_ALWAYS)
			title = self.cfg.get("title") or self._t("title")
			is_open, _ = imgui.begin("{}###net_menu".format(title))
			if is_open:
				if self.osk.active:
					self._draw_keyboard()
				else:
					getattr(self, "_screen_" + self.state.screen)()
			imgui.end()

		self._draw_notice()
		imgui.pop_style_color(6)
		if self.font is not None:
			imgui.pop_font()

	# ------------------------------------------------------------------ widgets
	def _button(self, key, label=None, width=0.0):
		lay = self.layout
		label = label or self._t(key)
		focused = self.state.focus.item(key)
		if focused:
			imgui.push_style_color(COL_BUTTON, *self.theme["focus"])
			imgui.push_style_color(COL_TEXT, 0.05, 0.05, 0.05, 1.0)
		w = width or (lay["win_w"] - 2 * lay["spacing"])
		clicked = imgui.button("{}##{}".format(label, key), w, lay["button_h"])
		if focused:
			imgui.pop_style_color(2)
		return clicked or self.state.focus.consume_accept(key)

	def _input(self, field, label_key, max_length=64):
		value = str(self.fields[field])
		if self.touch:
			if self._button("kb_" + field, "{}: {}".format(self._t(label_key), value or "...")):
				self.osk.open(field, value, max_length)
			return
		changed, value = imgui.input_text("{}##{}".format(self._t(label_key), field), value, max_length)
		if changed:
			self.fields[field] = value
		err = self.errors.get(field)
		if err:
			imgui.text(self._t(err))

	def _draw_keyboard(self):
		lay = self.layout
		imgui.text(self._t("keyboard"))
		imgui.text("> " + self.osk.text + "_")
		imgui.separator()
		key_w = (lay["win_w"] - 2 * lay["spacing"]) / 10.0 - 4
		for r, row in enumerate(self.osk.rows()):
			for i, k in enumerate(row):
				if i:
					imgui.same_line()
				label = {L.KEY_SPACE: self._t("space"), L.KEY_DONE: self._t("done")}.get(k, k)
				wide = key_w * (2.5 if r == 4 else 1)
				if imgui.button("{}##osk{}_{}".format(label, r, i), wide, lay["button_h"]):
					done = self.osk.press(k)
					if done:
						self.fields[done[0]] = done[1]

	# ------------------------------------------------------------------ screens
	def _screen_main(self):
		if self._button("host"):
			self.state.go(L.HOST)
		if self._button("join"):
			self.state.go(L.JOIN)
		if L.LAN not in self.state.hidden and self._button("lan"):
			if self.state.go(L.LAN):
				self._refresh_lan()
		if L.SETTINGS not in self.state.hidden and self._button("settings"):
			self.state.go(L.SETTINGS)
		if self._button("quit"):
			Range.logic.endGame()

	def _screen_host(self):
		self._input("room_name", "room_name", 32)
		changed, n = imgui.slider_int(self._t("max_players"), int(self.fields["max_players"]), 2, 64)
		if changed:
			self.fields["max_players"] = n
		self._input("port", "port", 6)
		self._input("password", "password", 32)
		imgui.separator()
		if self._button("create"):
			self.errors = {}
			room = L.validate_room_name(self.fields["room_name"])
			port = L.validate_port(self.fields["port"])
			maxp = L.validate_max_players(self.fields["max_players"])
			if room is None:
				self.errors["room_name"] = "err_name"
			if port is None:
				self.errors["port"] = "err_port"
			if maxp is None:
				self.errors["max_players"] = "err_max_players"
			if not self.errors:
				self._call_host(port, maxp, room, self.fields["password"])
		if self._button("back"):
			self.state.back()

	def _call_host(self, port, maxp, room, password):
		try:
			self.net.host(port, max_players=maxp, room_name=room, password=password)
		except TypeError:
			self.net.host(port)  # minimal 6.2 signature
		if self._connected():
			self.state.on_connected()

	def _screen_join(self):
		self._input("address", "address", 64)
		if self.state.status == "connecting":
			imgui.text(self._t("connecting"))
		if self._button("connect"):
			self.errors = {}
			target = L.parse_join_target(self.fields["address"], self.default_port)
			if target is None:
				self.errors["address"] = "err_address"
			else:
				kind, value = target
				if kind == "code":
					addr = value
				else:
					fmt = "[{}]:{}" if ":" in value[0] else "{}:{}"
					addr = fmt.format(*value)
				self.state.on_connecting()
				self.net.join(addr)
		if self._button("back"):
			self.state.back()

	def _refresh_lan(self):
		discover = getattr(self.net, "discover_lan", None)
		self.lan_list = list(discover()) if callable(discover) else []
		self.lan_sel = -1

	def _screen_lan(self):
		if not self.lan_list:
			imgui.text(self._t("no_servers"))
		else:
			items = ["{}  {}/{}  {} ms".format(s["name"], s["players"], s["max_players"], s["ping"])
				for s in self.lan_list]
			changed, sel = imgui.listbox("##lan", self.lan_sel, items, min(8, len(items)))
			if changed:
				last, t = self.lan_last_click
				now = time.monotonic()
				self.lan_sel = sel
				if last == sel and now - t < 0.4:  # double click joins
					self._join_lan(sel)
				self.lan_last_click = (sel, now)
		if self._button("refresh"):
			self._refresh_lan()
		if self.lan_sel >= 0 and self._button("connect"):
			self._join_lan(self.lan_sel)
		if self._button("back"):
			self.state.back()

	def _join_lan(self, index):
		self.state.on_connecting()
		self.net.join(self.lan_list[index]["address"])

	def _player_rows(self):
		rows = []
		for c in getattr(self.net, "clients", []) or []:
			tag = " ({})".format(self._t("host_tag")) if getattr(c, "isHost", False) else ""
			ready = self._t("ready") if getattr(c, "ready", False) else self._t("not_ready")
			rows.append("{}{}  {} ms  {}".format(getattr(c, "name", "?"), tag, getattr(c, "ping", 0), ready))
		return rows

	def _screen_lobby(self):
		imgui.text(self._t("players"))
		for row in self._player_rows():
			imgui.text("  " + row)
		imgui.separator()
		imgui.text(self._t("chat"))
		for line in self.chat_log:
			imgui.text("  " + line)
		self._input("chat", "chat", 200)
		if self._button("send"):
			text = L.validate_chat(self.fields["chat"])
			send = getattr(self.net, "send_chat", None)
			if text and callable(send):
				send(text)
			self.fields["chat"] = ""
		imgui.separator()
		if self._button("ready", self._t("not_ready") if self.ready else self._t("ready")):
			self.ready = not self.ready
			setter = getattr(self.net, "set_ready", None)
			if callable(setter):
				setter(self.ready)
		if getattr(self.net, "isServer", False) and self._button("start"):
			starter = getattr(self.net, "start_game", None)
			if callable(starter):
				starter()
			else:
				self.state.on_game_started()
		if self._button("leave"):
			self._leave()

	def _leave(self):
		self.net.disconnect()
		self.state.screen = L.MAIN
		self.state.focus.reset()

	def _screen_pause(self):
		if self._button("resume"):
			self.state.go(L.CLOSED)
		imgui.text(self._t("connected_players"))
		for row in self._player_rows():
			imgui.text("  " + row)
		if L.SETTINGS not in self.state.hidden and self._button("settings"):
			self.state.go(L.SETTINGS)
		if self._button("disconnect"):
			self._leave()

	def _screen_settings(self):
		self._input("player_name", "player_name", 16)
		changed, idx = imgui.combo(self._t("language"), L.LANGUAGES.index(self.lang), list(L.LANGUAGES))
		if changed:
			self.lang = L.LANGUAGES[idx]
		if self.cfg.get("dev_build", False):
			imgui.separator()
			imgui.text(self._t("net_sim"))
			_, self.sim_latency = imgui.slider_int(self._t("latency"), self.sim_latency, 0, 500)
			_, self.sim_loss = imgui.slider_int(self._t("loss"), self.sim_loss, 0, 50)
		if self._button("back"):
			name = L.validate_player_name(self.fields["player_name"])
			if name is None:
				self.errors["player_name"] = "err_name"
			else:
				self.errors.pop("player_name", None)
				if hasattr(self.net, "playerName"):
					self.net.playerName = name
				self.state.back()

	def _screen_closed(self):
		pass

	# ------------------------------------------------------------------ notices
	def _draw_notice(self):
		if not self.state.notice:
			return
		imgui.open_popup(NOTICE_POPUP)
		is_open, _ = imgui.begin_popup_modal("{}{}".format(self._t("notice"), NOTICE_POPUP))
		if is_open:
			imgui.text(self._t(self.state.notice))
			if self.state.notice_detail:
				imgui.text(self.state.notice_detail)
			if self._button("ok", width=self.layout["win_w"] * 0.5):
				self.state.dismiss_notice()
				imgui.close_current_popup()
			imgui.end_popup()
