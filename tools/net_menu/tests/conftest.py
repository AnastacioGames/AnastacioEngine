"""Mock Range / Range.imgui so net_menu imports without the engine."""

import os
import sys
import types
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class _Component:
	def __init__(self, obj=None):
		self.object = obj


def _install_range_mock():
	rng = types.ModuleType("Range")
	rng.__path__ = []
	imgui = mock.MagicMock(name="Range.imgui")
	imgui.get_display_size.return_value = (1280.0, 720.0)
	imgui.begin.return_value = (True, False)
	imgui.begin_popup_modal.return_value = (True, False)
	imgui.button.return_value = False
	imgui.input_text.side_effect = lambda label, value, max_length=256: (False, value)
	imgui.slider_int.side_effect = lambda label, v, lo, hi: (False, v)
	imgui.combo.side_effect = lambda label, cur, items: (False, cur)
	imgui.listbox.side_effect = lambda label, cur, items, h=-1: (False, cur)
	imgui.get_io_want_capture_keyboard.return_value = False
	rng.imgui = imgui
	rng.types = types.SimpleNamespace(KX_PythonComponent=_Component)
	rng.logic = types.SimpleNamespace(joysticks=[], endGame=mock.Mock(), expandPath=lambda p: p)
	sys.modules["Range"] = rng
	sys.modules["Range.imgui"] = imgui
	sys.modules["Range.types"] = rng.types
	return rng


RANGE = _install_range_mock()
