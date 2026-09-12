/*
 * ***** BEGIN GPL LICENSE BLOCK *****
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software Foundation,
 * Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
 *
 * The Original Code is Copyright (C) 2026 by Range Engine.
 *
 * The Original Code is: all of this file.
 *
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file KXImgui/KX_PythonImgui.cpp
 *  \ingroup ketsji
 */

#ifdef WITH_PYTHON

#include "KX_PythonImgui.h"

#include "implot.h"  // pulls in imgui.h
#include "imgui_impl_opengl3.h"

#include "KX_KetsjiEngine.h"
#include "KX_Globals.h"

#include <cstring>
#include <string>
#include <vector>

/* v1 widget set is a thin 1:1 wrapper over ImGui's immediate-mode API, mirroring how the
 * rest of BGE game logic is scripted from Python. Text always goes through "%s" to avoid
 * passing a Python-controlled string as a printf-style format string to ImGui. */

static PyObject *gPyImgui_Begin(PyObject *, PyObject *args, PyObject *kwds)
{
	const char *name;
	int closable = 0;
	static const char *kwlist[] = {"name", "closable", nullptr};
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "s|p:begin", (char **)kwlist, &name, &closable)) {
		return nullptr;
	}

	bool open = true;
	bool isOpen = ImGui::Begin(name, closable ? &open : nullptr);
	bool wantClose = closable && !open;

	PyObject *result = PyTuple_New(2);
	PyTuple_SET_ITEM(result, 0, PyBool_FromLong(isOpen));
	PyTuple_SET_ITEM(result, 1, PyBool_FromLong(wantClose));
	return result;
}

static PyObject *gPyImgui_End(PyObject *)
{
	ImGui::End();
	Py_RETURN_NONE;
}

static PyObject *gPyImgui_Text(PyObject *, PyObject *args)
{
	const char *text;
	if (!PyArg_ParseTuple(args, "s:text", &text)) {
		return nullptr;
	}
	ImGui::Text("%s", text);
	Py_RETURN_NONE;
}

static PyObject *gPyImgui_Button(PyObject *, PyObject *args, PyObject *kwds)
{
	const char *label;
	float width = 0.0f;
	float height = 0.0f;
	static const char *kwlist[] = {"label", "width", "height", nullptr};
	if (!PyArg_ParseTupleAndKeywords(
	        args, kwds, "s|ff:button", (char **)kwlist, &label, &width, &height)) {
		return nullptr;
	}

	bool clicked = ImGui::Button(label, ImVec2(width, height));
	return PyBool_FromLong(clicked);
}

static PyObject *gPyImgui_Checkbox(PyObject *, PyObject *args)
{
	const char *label;
	int value;
	if (!PyArg_ParseTuple(args, "sp:checkbox", &label, &value)) {
		return nullptr;
	}

	bool boolValue = value != 0;
	bool changed = ImGui::Checkbox(label, &boolValue);

	PyObject *result = PyTuple_New(2);
	PyTuple_SET_ITEM(result, 0, PyBool_FromLong(changed));
	PyTuple_SET_ITEM(result, 1, PyBool_FromLong(boolValue));
	return result;
}

static PyObject *gPyImgui_SliderFloat(PyObject *, PyObject *args)
{
	const char *label;
	float value;
	float min;
	float max;
	if (!PyArg_ParseTuple(args, "sfff:slider_float", &label, &value, &min, &max)) {
		return nullptr;
	}

	bool changed = ImGui::SliderFloat(label, &value, min, max);

	PyObject *result = PyTuple_New(2);
	PyTuple_SET_ITEM(result, 0, PyBool_FromLong(changed));
	PyTuple_SET_ITEM(result, 1, PyFloat_FromDouble(value));
	return result;
}

static PyObject *gPyImgui_SliderInt(PyObject *, PyObject *args)
{
	const char *label;
	int value;
	int min;
	int max;
	if (!PyArg_ParseTuple(args, "siii:slider_int", &label, &value, &min, &max)) {
		return nullptr;
	}

	bool changed = ImGui::SliderInt(label, &value, min, max);

	PyObject *result = PyTuple_New(2);
	PyTuple_SET_ITEM(result, 0, PyBool_FromLong(changed));
	PyTuple_SET_ITEM(result, 1, PyLong_FromLong(value));
	return result;
}

static PyObject *gPyImgui_InputText(PyObject *, PyObject *args, PyObject *kwds)
{
	const char *label;
	const char *value;
	int maxLength = 256;
	static const char *kwlist[] = {"label", "value", "max_length", nullptr};
	if (!PyArg_ParseTupleAndKeywords(
	        args, kwds, "ss|i:input_text", (char **)kwlist, &label, &value, &maxLength)) {
		return nullptr;
	}
	if (maxLength < 1) {
		PyErr_SetString(PyExc_ValueError, "max_length must be >= 1");
		return nullptr;
	}

	std::vector<char> buf(maxLength, '\0');
	strncpy(buf.data(), value, maxLength - 1);

	bool changed = ImGui::InputText(label, buf.data(), buf.size());

	PyObject *result = PyTuple_New(2);
	PyTuple_SET_ITEM(result, 0, PyBool_FromLong(changed));
	PyTuple_SET_ITEM(result, 1, PyUnicode_FromString(buf.data()));
	return result;
}

/* Shared helper: convert a Python sequence of strings into storage that outlives the
 * ImGui call (ImGui::Combo/ListBox only take a flat const char* const* array). */
static bool PyImgui_ParseStringList(PyObject *seq, std::vector<std::string> &storage,
                                     std::vector<const char *> &items)
{
	PyObject *fastSeq = PySequence_Fast(seq, "items must be a sequence of strings");
	if (!fastSeq) {
		return false;
	}
	Py_ssize_t n = PySequence_Fast_GET_SIZE(fastSeq);
	storage.reserve(n);
	items.reserve(n);
	for (Py_ssize_t i = 0; i < n; i++) {
		PyObject *item = PySequence_Fast_GET_ITEM(fastSeq, i);
		const char *str = PyUnicode_AsUTF8(item);
		if (!str) {
			Py_DECREF(fastSeq);
			return false;
		}
		storage.push_back(str);
	}
	Py_DECREF(fastSeq);
	for (const std::string &s : storage) {
		items.push_back(s.c_str());
	}
	return true;
}

static PyObject *gPyImgui_Combo(PyObject *, PyObject *args)
{
	const char *label;
	int currentItem;
	PyObject *itemsSeq;
	if (!PyArg_ParseTuple(args, "siO:combo", &label, &currentItem, &itemsSeq)) {
		return nullptr;
	}

	std::vector<std::string> storage;
	std::vector<const char *> items;
	if (!PyImgui_ParseStringList(itemsSeq, storage, items)) {
		return nullptr;
	}

	bool changed = ImGui::Combo(label, &currentItem, items.data(), (int)items.size());

	PyObject *result = PyTuple_New(2);
	PyTuple_SET_ITEM(result, 0, PyBool_FromLong(changed));
	PyTuple_SET_ITEM(result, 1, PyLong_FromLong(currentItem));
	return result;
}

static PyObject *gPyImgui_ListBox(PyObject *, PyObject *args, PyObject *kwds)
{
	const char *label;
	int currentItem;
	PyObject *itemsSeq;
	int heightItems = -1;
	static const char *kwlist[] = {"label", "current_item", "items", "height_items", nullptr};
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "siO|i:listbox", (char **)kwlist, &label,
	                                  &currentItem, &itemsSeq, &heightItems)) {
		return nullptr;
	}

	std::vector<std::string> storage;
	std::vector<const char *> items;
	if (!PyImgui_ParseStringList(itemsSeq, storage, items)) {
		return nullptr;
	}

	bool changed = ImGui::ListBox(
	    label, &currentItem, items.data(), (int)items.size(), heightItems);

	PyObject *result = PyTuple_New(2);
	PyTuple_SET_ITEM(result, 0, PyBool_FromLong(changed));
	PyTuple_SET_ITEM(result, 1, PyLong_FromLong(currentItem));
	return result;
}

static PyObject *gPyImgui_RadioButton(PyObject *, PyObject *args)
{
	const char *label;
	int active;
	if (!PyArg_ParseTuple(args, "sp:radio_button", &label, &active)) {
		return nullptr;
	}
	bool pressed = ImGui::RadioButton(label, active != 0);
	return PyBool_FromLong(pressed);
}

static PyObject *gPyImgui_ColorEdit3(PyObject *, PyObject *args)
{
	const char *label;
	float r, g, b;
	if (!PyArg_ParseTuple(args, "sfff:color_edit3", &label, &r, &g, &b)) {
		return nullptr;
	}
	float color[3] = {r, g, b};
	bool changed = ImGui::ColorEdit3(label, color);

	PyObject *result = PyTuple_New(4);
	PyTuple_SET_ITEM(result, 0, PyBool_FromLong(changed));
	PyTuple_SET_ITEM(result, 1, PyFloat_FromDouble(color[0]));
	PyTuple_SET_ITEM(result, 2, PyFloat_FromDouble(color[1]));
	PyTuple_SET_ITEM(result, 3, PyFloat_FromDouble(color[2]));
	return result;
}

static PyObject *gPyImgui_ColorEdit4(PyObject *, PyObject *args)
{
	const char *label;
	float r, g, b, a;
	if (!PyArg_ParseTuple(args, "sffff:color_edit4", &label, &r, &g, &b, &a)) {
		return nullptr;
	}
	float color[4] = {r, g, b, a};
	bool changed = ImGui::ColorEdit4(label, color);

	PyObject *result = PyTuple_New(5);
	PyTuple_SET_ITEM(result, 0, PyBool_FromLong(changed));
	PyTuple_SET_ITEM(result, 1, PyFloat_FromDouble(color[0]));
	PyTuple_SET_ITEM(result, 2, PyFloat_FromDouble(color[1]));
	PyTuple_SET_ITEM(result, 3, PyFloat_FromDouble(color[2]));
	PyTuple_SET_ITEM(result, 4, PyFloat_FromDouble(color[3]));
	return result;
}

static PyObject *gPyImgui_OpenPopup(PyObject *, PyObject *args)
{
	const char *name;
	if (!PyArg_ParseTuple(args, "s:open_popup", &name)) {
		return nullptr;
	}
	ImGui::OpenPopup(name);
	Py_RETURN_NONE;
}

static PyObject *gPyImgui_BeginPopupModal(PyObject *, PyObject *args, PyObject *kwds)
{
	const char *name;
	int closable = 0;
	static const char *kwlist[] = {"name", "closable", nullptr};
	if (!PyArg_ParseTupleAndKeywords(
	        args, kwds, "s|p:begin_popup_modal", (char **)kwlist, &name, &closable)) {
		return nullptr;
	}

	bool open = true;
	bool isOpen = ImGui::BeginPopupModal(name, closable ? &open : nullptr);
	bool wantClose = closable && !open;

	PyObject *result = PyTuple_New(2);
	PyTuple_SET_ITEM(result, 0, PyBool_FromLong(isOpen));
	PyTuple_SET_ITEM(result, 1, PyBool_FromLong(wantClose));
	return result;
}

static PyObject *gPyImgui_EndPopup(PyObject *)
{
	ImGui::EndPopup();
	Py_RETURN_NONE;
}

static PyObject *gPyImgui_CloseCurrentPopup(PyObject *)
{
	ImGui::CloseCurrentPopup();
	Py_RETURN_NONE;
}

static PyObject *gPyImgui_PushStyleColor(PyObject *, PyObject *args)
{
	int idx;
	float r, g, b, a;
	if (!PyArg_ParseTuple(args, "iffff:push_style_color", &idx, &r, &g, &b, &a)) {
		return nullptr;
	}
	if (idx < 0 || idx >= ImGuiCol_COUNT) {
		PyErr_SetString(PyExc_ValueError, "push_style_color: invalid color index");
		return nullptr;
	}
	ImGui::PushStyleColor((ImGuiCol)idx, ImVec4(r, g, b, a));
	Py_RETURN_NONE;
}

static PyObject *gPyImgui_PopStyleColor(PyObject *, PyObject *args)
{
	int count = 1;
	if (!PyArg_ParseTuple(args, "|i:pop_style_color", &count)) {
		return nullptr;
	}
	ImGui::PopStyleColor(count);
	Py_RETURN_NONE;
}

/* Loading a font rebuilds the shared font atlas texture (ImGui_ImplOpenGL3_CreateFontsTexture),
 * which is only safe between frames, not mid Begin/End -- call this once (e.g. from a
 * component's start()), not every update() tick. */
static PyObject *gPyImgui_LoadFont(PyObject *, PyObject *args)
{
	const char *path;
	float size;
	if (!PyArg_ParseTuple(args, "sf:load_font", &path, &size)) {
		return nullptr;
	}

	ImGuiIO &io = ImGui::GetIO();
	ImFont *font = io.Fonts->AddFontFromFileTTF(path, size);
	if (!font) {
		PyErr_Format(PyExc_IOError, "load_font: failed to load font '%s'", path);
		return nullptr;
	}
	io.Fonts->Build();
	ImGui_ImplOpenGL3_CreateFontsTexture();

	int fontId = io.Fonts->Fonts.Size - 1;
	return PyLong_FromLong(fontId);
}

static PyObject *gPyImgui_PushFont(PyObject *, PyObject *args)
{
	int fontId;
	if (!PyArg_ParseTuple(args, "i:push_font", &fontId)) {
		return nullptr;
	}
	ImGuiIO &io = ImGui::GetIO();
	if (fontId < 0 || fontId >= io.Fonts->Fonts.Size) {
		PyErr_SetString(PyExc_ValueError, "push_font: invalid font id");
		return nullptr;
	}
	ImGui::PushFont(io.Fonts->Fonts[fontId]);
	Py_RETURN_NONE;
}

static PyObject *gPyImgui_PopFont(PyObject *)
{
	ImGui::PopFont();
	Py_RETURN_NONE;
}

static PyObject *gPyImgui_GetDisplaySize(PyObject *)
{
	ImGuiIO &io = ImGui::GetIO();
	PyObject *result = PyTuple_New(2);
	PyTuple_SET_ITEM(result, 0, PyFloat_FromDouble(io.DisplaySize.x));
	PyTuple_SET_ITEM(result, 1, PyFloat_FromDouble(io.DisplaySize.y));
	return result;
}

/* Draws on the foreground draw list (always on top of every window) -- the primitive
 * fade-to-black/white transitions between menu screens are built from in Python, by
 * animating alpha over a few frames and covering imgui.get_display_size(). */
static PyObject *gPyImgui_DrawRectFilled(PyObject *, PyObject *args)
{
	float x1, y1, x2, y2, r, g, b, a;
	if (!PyArg_ParseTuple(
	        args, "ffffffff:draw_rect_filled", &x1, &y1, &x2, &y2, &r, &g, &b, &a)) {
		return nullptr;
	}
	ImU32 col = ImGui::ColorConvertFloat4ToU32(ImVec4(r, g, b, a));
	ImGui::GetForegroundDrawList()->AddRectFilled(ImVec2(x1, y1), ImVec2(x2, y2), col);
	Py_RETURN_NONE;
}

static PyObject *gPyImgui_Separator(PyObject *)
{
	ImGui::Separator();
	Py_RETURN_NONE;
}

static PyObject *gPyImgui_SameLine(PyObject *)
{
	ImGui::SameLine();
	Py_RETURN_NONE;
}

static PyObject *gPyImgui_SetNextWindowPos(PyObject *, PyObject *args)
{
	float x;
	float y;
	int cond = ImGuiCond_Always;
	if (!PyArg_ParseTuple(args, "ff|i:set_next_window_pos", &x, &y, &cond)) {
		return nullptr;
	}
	ImGui::SetNextWindowPos(ImVec2(x, y), (ImGuiCond)cond);
	Py_RETURN_NONE;
}

static PyObject *gPyImgui_SetNextWindowSize(PyObject *, PyObject *args)
{
	float w;
	float h;
	int cond = ImGuiCond_Always;
	if (!PyArg_ParseTuple(args, "ff|i:set_next_window_size", &w, &h, &cond)) {
		return nullptr;
	}
	ImGui::SetNextWindowSize(ImVec2(w, h), (ImGuiCond)cond);
	Py_RETURN_NONE;
}

static PyObject *gPyImgui_Image(PyObject *, PyObject *args)
{
	unsigned long textureId;
	float w;
	float h;
	if (!PyArg_ParseTuple(args, "kff:image", &textureId, &w, &h)) {
		return nullptr;
	}
    // Blender textures use the opposite vertical origin from ImGui images.
    ImGui::Image((ImTextureID)(intptr_t)textureId, ImVec2(w, h),
                 ImVec2(0.0f, 1.0f), ImVec2(1.0f, 0.0f));
	Py_RETURN_NONE;
}

static PyObject *gPyImgui_InvisibleButton(PyObject *, PyObject *args)
{
	const char *label;
	float width;
	float height;
	if (!PyArg_ParseTuple(args, "sff:invisible_button", &label, &width, &height)) {
		return nullptr;
	}
	return PyBool_FromLong(ImGui::InvisibleButton(label, ImVec2(width, height)));
}

static PyObject *gPyImgui_SetCursorPos(PyObject *, PyObject *args)
{
	float x;
	float y;
	if (!PyArg_ParseTuple(args, "ff:set_cursor_pos", &x, &y)) {
		return nullptr;
	}
	ImGui::SetCursorPos(ImVec2(x, y));
	Py_RETURN_NONE;
}

static PyObject *gPyImgui_GetCursorPos(PyObject *)
{
	const ImVec2 pos = ImGui::GetCursorPos();
	PyObject *result = PyTuple_New(2);
	PyTuple_SET_ITEM(result, 0, PyFloat_FromDouble(pos.x));
	PyTuple_SET_ITEM(result, 1, PyFloat_FromDouble(pos.y));
	return result;
}

static PyObject *gPyImgui_GetCursorScreenPos(PyObject *)
{
	const ImVec2 pos = ImGui::GetCursorScreenPos();
	PyObject *result = PyTuple_New(2);
	PyTuple_SET_ITEM(result, 0, PyFloat_FromDouble(pos.x));
	PyTuple_SET_ITEM(result, 1, PyFloat_FromDouble(pos.y));
	return result;
}

static PyObject *gPyImgui_GetIOWantCaptureMouse(PyObject *)
{
	return PyBool_FromLong(ImGui::GetIO().WantCaptureMouse);
}

static PyObject *gPyImgui_GetIOWantCaptureKeyboard(PyObject *)
{
	return PyBool_FromLong(ImGui::GetIO().WantCaptureKeyboard);
}

static PyObject *gPyImgui_SetGameUIOpen(PyObject *, PyObject *args)
{
	int open;
	if (!PyArg_ParseTuple(args, "p:set_game_ui_open", &open)) {
		return nullptr;
	}
	KX_GetActiveEngine()->SetFlag(KX_KetsjiEngine::SHOW_GAME_UI, open != 0);
	Py_RETURN_NONE;
}

static struct PyMethodDef imgui_methods[] = {
    {"begin", (PyCFunction)gPyImgui_Begin, METH_VARARGS | METH_KEYWORDS,
     "begin(name, closable=False) -> (is_open, want_close)"},
    {"end", (PyCFunction)gPyImgui_End, METH_NOARGS, "end()"},
    {"text", (PyCFunction)gPyImgui_Text, METH_VARARGS, "text(text)"},
    {"button", (PyCFunction)gPyImgui_Button, METH_VARARGS | METH_KEYWORDS,
     "button(label, width=0, height=0) -> bool"},
    {"checkbox", (PyCFunction)gPyImgui_Checkbox, METH_VARARGS,
     "checkbox(label, value) -> (changed, new_value)"},
    {"slider_float", (PyCFunction)gPyImgui_SliderFloat, METH_VARARGS,
     "slider_float(label, value, min, max) -> (changed, new_value)"},
    {"slider_int", (PyCFunction)gPyImgui_SliderInt, METH_VARARGS,
     "slider_int(label, value, min, max) -> (changed, new_value)"},
    {"input_text", (PyCFunction)gPyImgui_InputText, METH_VARARGS | METH_KEYWORDS,
     "input_text(label, value, max_length=256) -> (changed, new_value)"},
    {"combo", (PyCFunction)gPyImgui_Combo, METH_VARARGS,
     "combo(label, current_item, items) -> (changed, new_item)"},
    {"listbox", (PyCFunction)gPyImgui_ListBox, METH_VARARGS | METH_KEYWORDS,
     "listbox(label, current_item, items, height_items=-1) -> (changed, new_item)"},
    {"radio_button", (PyCFunction)gPyImgui_RadioButton, METH_VARARGS,
     "radio_button(label, active) -> pressed -- caller owns the group's selected index"},
    {"color_edit3", (PyCFunction)gPyImgui_ColorEdit3, METH_VARARGS,
     "color_edit3(label, r, g, b) -> (changed, r, g, b)"},
    {"color_edit4", (PyCFunction)gPyImgui_ColorEdit4, METH_VARARGS,
     "color_edit4(label, r, g, b, a) -> (changed, r, g, b, a)"},
    {"open_popup", (PyCFunction)gPyImgui_OpenPopup, METH_VARARGS, "open_popup(name)"},
    {"begin_popup_modal", (PyCFunction)gPyImgui_BeginPopupModal, METH_VARARGS | METH_KEYWORDS,
     "begin_popup_modal(name, closable=False) -> (is_open, want_close) -- "
     "only call end_popup() if is_open is True"},
    {"end_popup", (PyCFunction)gPyImgui_EndPopup, METH_NOARGS, "end_popup()"},
    {"close_current_popup", (PyCFunction)gPyImgui_CloseCurrentPopup, METH_NOARGS,
     "close_current_popup()"},
    {"push_style_color", (PyCFunction)gPyImgui_PushStyleColor, METH_VARARGS,
     "push_style_color(idx, r, g, b, a) -- idx is one of the imgui.COL_* constants"},
    {"pop_style_color", (PyCFunction)gPyImgui_PopStyleColor, METH_VARARGS,
     "pop_style_color(count=1)"},
    {"load_font", (PyCFunction)gPyImgui_LoadFont, METH_VARARGS,
     "load_font(path, size) -> font_id -- call once (e.g. from start()), not every frame"},
    {"push_font", (PyCFunction)gPyImgui_PushFont, METH_VARARGS, "push_font(font_id)"},
    {"pop_font", (PyCFunction)gPyImgui_PopFont, METH_NOARGS, "pop_font()"},
    {"get_display_size", (PyCFunction)gPyImgui_GetDisplaySize, METH_NOARGS,
     "get_display_size() -> (width, height)"},
    {"draw_rect_filled", (PyCFunction)gPyImgui_DrawRectFilled, METH_VARARGS,
     "draw_rect_filled(x1, y1, x2, y2, r, g, b, a) -- drawn above every window, for fades"},
    {"separator", (PyCFunction)gPyImgui_Separator, METH_NOARGS, "separator()"},
    {"same_line", (PyCFunction)gPyImgui_SameLine, METH_NOARGS, "same_line()"},
    {"set_next_window_pos", (PyCFunction)gPyImgui_SetNextWindowPos, METH_VARARGS,
     "set_next_window_pos(x, y, cond=COND_ALWAYS)"},
    {"set_next_window_size", (PyCFunction)gPyImgui_SetNextWindowSize, METH_VARARGS,
     "set_next_window_size(w, h, cond=COND_ALWAYS)"},
    {"image", (PyCFunction)gPyImgui_Image, METH_VARARGS,
     "image(texture_id, w, h) -- texture_id is a raw OpenGL bind code"},
    {"invisible_button", (PyCFunction)gPyImgui_InvisibleButton, METH_VARARGS,
     "invisible_button(label, width, height) -> bool"},
    {"set_cursor_pos", (PyCFunction)gPyImgui_SetCursorPos, METH_VARARGS,
     "set_cursor_pos(x, y) -- position relative to the current window"},
    {"get_cursor_pos", (PyCFunction)gPyImgui_GetCursorPos, METH_NOARGS,
     "get_cursor_pos() -> (x, y) -- position relative to the current window"},
    {"get_cursor_screen_pos", (PyCFunction)gPyImgui_GetCursorScreenPos, METH_NOARGS,
     "get_cursor_screen_pos() -> (x, y)"},
    {"get_io_want_capture_mouse", (PyCFunction)gPyImgui_GetIOWantCaptureMouse, METH_NOARGS,
     "get_io_want_capture_mouse() -> bool"},
    {"get_io_want_capture_keyboard", (PyCFunction)gPyImgui_GetIOWantCaptureKeyboard, METH_NOARGS,
     "get_io_want_capture_keyboard() -> bool"},
    {"set_game_ui_open", (PyCFunction)gPyImgui_SetGameUIOpen, METH_VARARGS,
     "set_game_ui_open(open) -- enable/disable input + free mouse for Python-drawn game UI"},
    {nullptr, nullptr, 0, nullptr},
};

static struct PyModuleDef Imgui_module_def = {
    PyModuleDef_HEAD_INIT,
    "imgui",     /* m_name */
    "Minimal Python bindings over Dear ImGui for in-game menus", /* m_doc */
    0,           /* m_size */
    imgui_methods, /* m_methods */
    0,           /* m_reload */
    0,           /* m_traverse */
    0,           /* m_clear */
    0,           /* m_free */
};

/* ImGuiCol_* constants for imgui.push_style_color() -- a representative subset covering the
 * colors most useful for theming a menu, not the full enum (Python code that needs a color
 * not listed here can still pass its raw ImGuiCol_* integer value). */
static void PyImgui_AddColorConstants(PyObject *m)
{
	PyModule_AddIntConstant(m, "COL_TEXT", ImGuiCol_Text);
	PyModule_AddIntConstant(m, "COL_WINDOW_BG", ImGuiCol_WindowBg);
	PyModule_AddIntConstant(m, "COL_POPUP_BG", ImGuiCol_PopupBg);
	PyModule_AddIntConstant(m, "COL_BORDER", ImGuiCol_Border);
	PyModule_AddIntConstant(m, "COL_FRAME_BG", ImGuiCol_FrameBg);
	PyModule_AddIntConstant(m, "COL_FRAME_BG_HOVERED", ImGuiCol_FrameBgHovered);
	PyModule_AddIntConstant(m, "COL_FRAME_BG_ACTIVE", ImGuiCol_FrameBgActive);
	PyModule_AddIntConstant(m, "COL_TITLE_BG", ImGuiCol_TitleBg);
	PyModule_AddIntConstant(m, "COL_TITLE_BG_ACTIVE", ImGuiCol_TitleBgActive);
	PyModule_AddIntConstant(m, "COL_BUTTON", ImGuiCol_Button);
	PyModule_AddIntConstant(m, "COL_BUTTON_HOVERED", ImGuiCol_ButtonHovered);
	PyModule_AddIntConstant(m, "COL_BUTTON_ACTIVE", ImGuiCol_ButtonActive);
	PyModule_AddIntConstant(m, "COL_CHECK_MARK", ImGuiCol_CheckMark);
	PyModule_AddIntConstant(m, "COL_SLIDER_GRAB", ImGuiCol_SliderGrab);
	PyModule_AddIntConstant(m, "COL_SLIDER_GRAB_ACTIVE", ImGuiCol_SliderGrabActive);
	PyModule_AddIntConstant(m, "COL_HEADER", ImGuiCol_Header);
	PyModule_AddIntConstant(m, "COL_HEADER_HOVERED", ImGuiCol_HeaderHovered);
	PyModule_AddIntConstant(m, "COL_HEADER_ACTIVE", ImGuiCol_HeaderActive);
	PyModule_AddIntConstant(m, "COL_SCROLLBAR_BG", ImGuiCol_ScrollbarBg);
	PyModule_AddIntConstant(m, "COL_SCROLLBAR_GRAB", ImGuiCol_ScrollbarGrab);
}

static void PyImgui_AddCondConstants(PyObject *m)
{
	/* Controla se set_next_window_pos/size reaplica todo frame (ALWAYS, o
	 * padrao do ImGui) ou so uma vez (FIRST_USE_EVER) -- ALWAYS trava o
	 * usuario de redimensionar/mover a janela pelo mouse, porque o valor do
	 * Python sobrescreve o resize manual no frame seguinte. */
	PyModule_AddIntConstant(m, "COND_ALWAYS", ImGuiCond_Always);
	PyModule_AddIntConstant(m, "COND_ONCE", ImGuiCond_Once);
	PyModule_AddIntConstant(m, "COND_FIRST_USE_EVER", ImGuiCond_FirstUseEver);
	PyModule_AddIntConstant(m, "COND_APPEARING", ImGuiCond_Appearing);
}

PyMODINIT_FUNC initImguiPythonBinding()
{
	PyObject *m = PyModule_Create(&Imgui_module_def);
	PyImgui_AddColorConstants(m);
	PyImgui_AddCondConstants(m);
	PyDict_SetItemString(PySys_GetObject("modules"), Imgui_module_def.m_name, m);
	return m;
}

#endif  // WITH_PYTHON
