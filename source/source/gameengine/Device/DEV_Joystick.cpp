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
 * The Original Code is Copyright (C) 2001-2002 by NaN Holding BV.
 * All rights reserved.
 *
 * The Original Code is: all of this file.
 *
 * Contributor(s): snailrose, lordloki
 *
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file gameengine/Device/DEV_Joystick.cpp
 *  \ingroup device
 */

#if defined(WITH_SDL) && defined(_MSC_VER)
#  include <excpt.h>
#endif

#ifdef WITH_SDL
#  include <SDL.h>

extern "C" {
#  include "BKE_appdir.h"
#  include "BLI_path_util.h"
}
#endif

#include <cmath>

#include "DEV_Joystick.h"
#include "DEV_JoystickPrivate.h"

#include "CM_Message.h"

#ifdef WITH_SDL
#  define SDL_CHECK(x) ((x) != (void *)0)
#endif

#if defined(WITH_SDL) && defined(_MSC_VER)
/* Some physical controllers trip a crash *inside* SDL2.dll itself while it
 * enumerates/initializes joystick hardware during SDL_InitSubSystem(), before
 * our code gets any chance to react (observed with a "G-Shark GS-GP702" pad:
 * the whole engine, editor included, hard-closed on "P" with the crash log
 * pointing into SDL_InitSubSystem via DEV_Joystick::Init). Unplugging the
 * controller avoided it, confirming the fault is in SDL's HID/XInput
 * enumeration path for that device, not in our logic. We can't fix SDL2
 * here, but we can keep one bad controller from taking down the whole
 * engine by catching the structured exception and disabling joystick
 * support for this session instead of crashing.
 * This helper must stay a "leaf" function with no C++ objects that need
 * unwinding, since __try/__except cannot coexist with automatic
 * destructible objects in the same function on MSVC. */
static bool DEV_Joystick_SEH_InitSubSystem(Uint32 flags)
{
	__try {
		return (SDL_InitSubSystem(flags) != -1);
	}
	__except (EXCEPTION_EXECUTE_HANDLER) {
		CM_Error("SDL_InitSubSystem(joystick) crashed (structured exception) - "
		         "disabling joystick support for this session. "
		         "This usually means a connected controller is not "
		         "handled correctly by SDL2; unplugging it works around it.");
		return false;
	}
}
#endif

DEV_Joystick::DEV_Joystick(short index)
	:
	m_joyindex(index),
	m_prec(3200),
	m_axismax(-1),
	m_buttonmax(-1),
	m_isinit(0),
	m_istrig_axis(0),
	m_istrig_button(0)
{
	for (int i = 0; i < JOYAXIS_MAX; i++) {
		m_axis_array[i] = 0;
		m_live_axis[i] = 0;
	}
	for (int i = 0; i < 32; i++) {
		m_live_button[i] = false;
	}

#ifdef WITH_SDL
	m_private = new PrivateData();
#endif
}


DEV_Joystick::~DEV_Joystick()
{
}

DEV_Joystick *DEV_Joystick::m_instance[JOYINDEX_MAX];

bool DEV_Joystick::s_padActive = false;
int DEV_Joystick::s_padAxis[JOYAXIS_MAX] = {0};
unsigned int DEV_Joystick::s_padButtons = 0;


void DEV_Joystick::Init()
{
#ifdef WITH_SDL

	if (!(SDL_CHECK(SDL_InitSubSystem)) ||
	    !(SDL_CHECK(SDL_GameControllerAddMapping)) ||
	    !(SDL_CHECK(SDL_GameControllerAddMappingsFromRW))) {
		return;
	}

	/* Initializing Game Controller related subsystems.
	 * Emscripten's SDL2 port has no haptic/force-feedback backend, so requesting
	 * SDL_INIT_HAPTIC there fails the whole SDL_InitSubSystem call and silently
	 * disables joystick support in the Web build (confirmed via
	 * "SDL not built with haptic (force feedback) support" in the browser console). */
#ifdef __EMSCRIPTEN__
	Uint32 controller_init_flags = SDL_INIT_GAMECONTROLLER;
#else
	Uint32 controller_init_flags = SDL_INIT_GAMECONTROLLER | SDL_INIT_HAPTIC;
#endif
#ifdef _MSC_VER
	bool success = DEV_Joystick_SEH_InitSubSystem(controller_init_flags);
#else
	bool success = (SDL_InitSubSystem(controller_init_flags) != -1);
#endif

	if (success) {
		// Loading mapping file from blender datafiles directory
		const char *path = BKE_appdir_folder_id(BLENDER_DATAFILES, "gamecontroller");
		if (path) {
			char fullpath[FILE_MAX];
			BLI_join_dirfile(fullpath, sizeof(fullpath), path, "gamecontrollerdb.txt");

			if ((SDL_GameControllerAddMappingsFromFile(fullpath)) == -1) {
				CM_Error("gamecontrollerdb.txt not loaded");
			}
		}
	}
	else {
		CM_Error("initializing SDL Game Controller: " << SDL_GetError());
	}
#endif
}

void DEV_Joystick::Close()
{
#ifdef WITH_SDL
	/* Closing possible connected Joysticks */
	for (int i = 0; i < JOYINDEX_MAX; i++) {
		if (m_instance[i]) {
			m_instance[i]->ReleaseInstance(i);
		}
	}

	/* Closing SDL Game controller system */
	if (SDL_CHECK(SDL_QuitSubSystem)) {
#ifdef __EMSCRIPTEN__
		SDL_QuitSubSystem(SDL_INIT_GAMECONTROLLER);
#else
		SDL_QuitSubSystem(SDL_INIT_GAMECONTROLLER | SDL_INIT_HAPTIC);
#endif
	}
#endif
}

DEV_Joystick *DEV_Joystick::GetInstance(short joyindex)
{
#ifndef WITH_SDL
	return nullptr;
#else  /* WITH_SDL */

	if (joyindex < 0 || joyindex >= JOYINDEX_MAX) {
		CM_Error("invalid joystick index: " << joyindex);
		return nullptr;
	}

	return m_instance[joyindex];
#endif /* WITH_SDL */
}

void DEV_Joystick::ReleaseInstance(short joyindex)
{
#ifdef WITH_SDL
	if (m_instance[joyindex]) {
		m_instance[joyindex]->DestroyJoystickDevice();
		delete m_private;
		delete m_instance[joyindex];
	}
	m_instance[joyindex] = nullptr;
#endif /* WITH_SDL */
}

void DEV_Joystick::cSetPrecision(int val)
{
	m_prec = val;
}


bool DEV_Joystick::aAxisPairIsPositive(int axis)
{
	return (pAxisTest(axis) > m_prec) ? true : false;
}

bool DEV_Joystick::aAxisPairDirectionIsPositive(int axis, int dir)
{

	int res;

	if (dir == JOYAXIS_UP || dir == JOYAXIS_DOWN) {
		res = pGetAxis(axis, 1);
	}
	else { /* JOYAXIS_LEFT || JOYAXIS_RIGHT */
		res = pGetAxis(axis, 0);
	}

	if (dir == JOYAXIS_DOWN || dir == JOYAXIS_RIGHT) {
		return (res > m_prec) ? true : false;
	}
	else { /* JOYAXIS_UP || JOYAXIS_LEFT */
		return (res < -m_prec) ? true : false;
	}
}

bool DEV_Joystick::aAxisIsPositive(int axis_single)
{
	return std::abs(GetAxisPosition(axis_single)) > m_prec ? true : false;
}

bool DEV_Joystick::aAnyButtonPressIsPositive(void)
{
#ifdef WITH_SDL
	if (!(SDL_CHECK(SDL_GameControllerGetButton))) {
		return false;
	}

	/* this is needed for the "all events" option
	 * so we know if there are no buttons pressed */
	for (int i = 0; i < m_buttonmax; i++) {
		if (aButtonPressIsPositive(i)) {
			return true;
		}
	}
#endif
	return false;
}

bool DEV_Joystick::IsVirtualOnly() const
{
#ifdef WITH_SDL
	return m_joyindex == 0 && !m_private->m_gamecontroller;
#else
	return false;
#endif
}

bool DEV_Joystick::PhysicalButton(int button)
{
#ifdef WITH_SDL
	return m_private->m_gamecontroller && SDL_CHECK(SDL_GameControllerGetButton) &&
	       SDL_GameControllerGetButton(m_private->m_gamecontroller, (SDL_GameControllerButton)button);
#else
	return false;
#endif
}

bool DEV_Joystick::aButtonPressIsPositive(int button)
{
	if (PhysicalButton(button)) {
		return true;
	}
	return HasVirtualPad() && button >= 0 && button < 32 && (s_padButtons & (1u << button));
}


/* Reads the axis value live from SDL instead of the m_axis_array cache
 * populated by OnAxisEvent(). On the Web build, GHOST_SystemSDL::processEvents()
 * and DEV_Joystick::HandleEvents() each pump the single shared SDL event queue
 * once per frame; GHOST's unfiltered SDL_PollEvent() can silently drain
 * SDL_CONTROLLERAXISMOTION events before our filtered SDL_PeepEvents() call
 * sees them, leaving m_axis_array stuck on a stale value (confirmed via
 * browser-vs-OnAxisEvent diagnostic logs showing most axis updates never
 * reaching OnAxisEvent). SDL_GameControllerGetAxis() reads the controller's
 * internal state directly, the same way the button methods already do,
 * bypassing the event queue race entirely. */
int DEV_Joystick::PhysicalAxis(int index)
{
	if (index < 0 || index >= JOYAXIS_MAX) {
		return 0;
	}
#ifdef WITH_SDL
	if (!m_private->m_gamecontroller) {
		return 0;
	}
	if (SDL_CHECK(SDL_GameControllerGetAxis)) {
		return SDL_GameControllerGetAxis(m_private->m_gamecontroller, (SDL_GameControllerAxis)index);
	}
#endif
	return m_axis_array[index];
}

/* Physical controller and on-screen pad share index 0: the input pushed furthest wins, so either one moves the
 * player and neither cancels the other. */
int DEV_Joystick::GetAxisPosition(int index)
{
	const int physical = PhysicalAxis(index);
	if (!HasVirtualPad() || index < 0 || index >= JOYAXIS_MAX) {
		return physical;
	}
	const int pad = s_padAxis[index];
	return (std::abs(pad) > std::abs(physical)) ? pad : physical;
}

bool DEV_Joystick::aButtonReleaseIsPositive(int button)
{
	return !aButtonPressIsPositive(button);
}

bool DEV_Joystick::CreateJoystickDevice(void)
{
	bool joy_error = false;

#ifndef WITH_SDL
	m_isinit = true;
	joy_error = true;
#else /* WITH_SDL */
	if (!m_isinit) {

		if (!(SDL_CHECK(SDL_IsGameController) &&
		      SDL_CHECK(SDL_GameControllerOpen) &&
		      SDL_CHECK(SDL_GameControllerEventState) &&
		      SDL_CHECK(SDL_GameControllerGetJoystick) &&
		      SDL_CHECK(SDL_JoystickInstanceID))) {
			joy_error = true;
		}

		if (!joy_error && !SDL_IsGameController(m_joyindex)) {
			/* mapping instruccions if joystick is not a game controller */
			CM_Error("Game Controller index " << m_joyindex << ": Could not be initialized\n"
			                                  << "Please, generate Xbox360 compatible mapping using Antimicro (https://github.com/AntiMicro/antimicro)\n"
			                                  << "or SDL2 Gamepad Tool (http://www.generalarcade.com/gamepadtool) or Steam big mode applications\n"
			                                  << "and after, set the SDL controller variable before you launch the executable, i.e:\n"
			                                  << "export SDL_GAMECONTROLLERCONFIG=\"[the string you received from controllermap]\"");
			/* Need this so python args can return empty lists */
			joy_error = true;
		}

		if (!joy_error) {
			m_private->m_gamecontroller = SDL_GameControllerOpen(m_joyindex);
			if (!m_private->m_gamecontroller) {
				joy_error = true;
			}
		}

		SDL_Joystick *joy;
		if (!joy_error) {
			joy = SDL_GameControllerGetJoystick(m_private->m_gamecontroller);
			if (!joy) {
				joy_error = true;
			}
		}

		if (!joy_error) {
			m_private->m_instance_id = SDL_JoystickInstanceID(joy);
			if (m_private->m_instance_id < 0) {
				joy_error = true;
				CM_Error("joystick instanced failed: " << SDL_GetError());
			}
		}

		if (!joy_error) {
			CM_Debug("Game Controller (" << GetName() << ") with index " << m_joyindex << " initialized");

			/* A Game Controller has:
			 *
			 * 6 axis availables:	   AXIS_LEFTSTICK_X, AXIS_LEFTSTICK_Y,
			 * (in order from 0 to 5)  AXIS_RIGHTSTICK_X, AXIS_RIGHTSTICK_Y,
			 *						   AXIS_TRIGGERLEFT and AXIS_TRIGGERRIGHT.
			 *
			 * 15 buttons availables:  BUTTON_A, BUTTON_B, BUTTON_X, BUTTON_Y,
			 * (in order from 0 to 14) BUTTON_BACK, BUTTON_GUIDE, BUTTON_START,
			 *						   BUTTON_LEFTSTICK, BUTTON_RIGHTSTICK,
			 *						   BUTTON_LEFTSHOULDER, BUTTON_RIGHTSHOULDER,
			 *						   BUTTON_DPAD_UP, BUTTON_DPAD_DOWN,
			 *						   BUTTON_DPAD_LEFT and BUTTON_DPAD_RIGHT.
			 */
			m_axismax = SDL_CONTROLLER_AXIS_MAX;
			m_buttonmax = SDL_CONTROLLER_BUTTON_MAX;
		}

		/* Haptic configuration. Emscripten's SDL2 port never initializes the haptic
		 * subsystem (no force-feedback backend there, see DEV_Joystick::Init()), so
		 * calling SDL_HapticOpen() on Web is unsupported and must be skipped rather
		 * than attempted - confirmed as a crash source when a real controller is
		 * connected in the browser. */
#ifndef __EMSCRIPTEN__
		if (!joy_error && SDL_CHECK(SDL_HapticOpen)) {
			m_private->m_haptic = SDL_HapticOpen(m_joyindex);
			if (!m_private->m_haptic) {
				CM_Warning("Game Controller (" << GetName() << ") with index " << m_joyindex
				                               << " has not force feedback (vibration) available");
			}
		}
#endif
	}
#endif /* WITH_SDL */

	if (joy_error) {
		m_axismax = m_buttonmax = 0;
		return false;
	}
	else {
		m_isinit = true;
		return true;
	}
}


void DEV_Joystick::DestroyJoystickDevice(void)
{
#ifdef WITH_SDL
	if (m_isinit) {

		if (m_private->m_haptic && SDL_CHECK(SDL_HapticClose)) {
			SDL_HapticClose(m_private->m_haptic);
			m_private->m_haptic = nullptr;
		}

		if (m_private->m_gamecontroller && SDL_CHECK(SDL_GameControllerClose)) {
			CM_Debug("Game Controller (" << GetName() << ") with index " << m_joyindex << " closed");
			SDL_GameControllerClose(m_private->m_gamecontroller);
			m_private->m_gamecontroller = nullptr;
		}

		m_isinit = false;
	}
#endif /* WITH_SDL */
}

int DEV_Joystick::Connected(void)
{
	if (HasVirtualPad()) {
		return 1;
	}
#ifdef WITH_SDL
	if (m_isinit &&
	    (SDL_CHECK(SDL_GameControllerGetAttached) &&
	     SDL_GameControllerGetAttached(m_private->m_gamecontroller))) {
		return 1;
	}
#endif
	return 0;
}

int DEV_Joystick::pGetAxis(int axisnum, int udlr)
{
#ifdef WITH_SDL
	return GetAxisPosition((axisnum * 2) + udlr);
#endif
	return 0;
}

int DEV_Joystick::pAxisTest(int axisnum)
{
#ifdef WITH_SDL
	/* Use ints instead of shorts here to avoid problems when we get -32768.
	 * When we take the negative of that later, we should get 32768, which is greater
	 * than what a short can hold. In other words, abs(MIN_SHORT) > MAX_SHRT. */
	int i1 = GetAxisPosition(axisnum * 2);
	int i2 = GetAxisPosition((axisnum * 2) + 1);

	/* long winded way to do:
	 * return max_ff(absf(i1), absf(i2))
	 * ...avoid abs from math.h */
	if (i1 < 0) {
		i1 = -i1;
	}
	if (i2 < 0) {
		i2 = -i2;
	}
	if (i1 < i2) {
		return i2;
	}
	else {
		return i1;
	}
#else /* WITH_SDL */
	return 0;
#endif /* WITH_SDL */
}

const std::string DEV_Joystick::GetName()
{
#ifdef WITH_SDL
	if (!m_private->m_gamecontroller) {
		return IsVirtualOnly() ? "Range Virtual Pad" : "";
	}
	const char *name = (SDL_CHECK(SDL_GameControllerName)) ? SDL_GameControllerName(m_private->m_gamecontroller) : nullptr;
	return name ? name : "";
#else /* WITH_SDL */
	return "";
#endif /* WITH_SDL */
}
