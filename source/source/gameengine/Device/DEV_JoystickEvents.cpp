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
 * Contributor(s): snailrose.
 *
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file gameengine/Device/DEV_JoystickEvents.cpp
 *  \ingroup device
 */

#include "DEV_Joystick.h"
#include "DEV_JoystickPrivate.h"

#include "CM_Message.h"

#ifdef __EMSCRIPTEN__
#  include <emscripten.h>

/* Module.rangePad is written by the page's on-screen controls (package-web.py): active, axes[6] in -1..1 (triggers
 * 0..1, SDL GameController order) and buttons as a bitmask in SDL_GameControllerButton order. Returns 0 while the
 * page shows no pad. */
EM_JS(int, dev_virtualpad_web_read, (int *axes, int count, unsigned int *buttons), {
	var p = (typeof Module !== 'undefined') ? Module.rangePad : null;
	var base = axes >> 2;
	for (var i = 0; i < count; i++) HEAP32[base + i] = 0;
	HEAP32[buttons >> 2] = 0;
	if (!p || !p.active) return 0;
	for (var i = 0; i < count; i++) {
		var v = p.axes ? +p.axes[i] : 0;
		if (!isFinite(v)) v = 0;
		v = Math.max(-1, Math.min(1, v));
		HEAP32[base + i] = Math.round(v * (v < 0 ? 32768 : 32767));
	}
	HEAP32[buttons >> 2] = p.buttons | 0;
	return 1;
});
#endif

void DEV_Joystick::ReadVirtualPad()
{
#ifdef __EMSCRIPTEN__
	s_padActive = dev_virtualpad_web_read(s_padAxis, JOYAXIS_MAX, &s_padButtons) != 0;
#else
	s_padActive = false;
#endif
}

#ifdef WITH_SDL
void DEV_Joystick::OnAxisEvent(SDL_Event *sdl_event)
{
	if (sdl_event->caxis.axis >= JOYAXIS_MAX) {
		return;
	}

	m_axis_array[sdl_event->caxis.axis] = sdl_event->caxis.value;
	m_istrig_axis = 1;
}

/* See notes below in the event loop */
void DEV_Joystick::OnButtonEvent(SDL_Event *sdl_event)
{
	m_istrig_button = 1;
}


void DEV_Joystick::OnNothing(SDL_Event *sdl_event)
{
	m_istrig_axis = m_istrig_button = 0;
}

/* The sensors only evaluate when IsTrigAxis()/IsTrigButton() is set, and those were only set by
 * consuming an SDL event. On the Web build GHOST's unfiltered SDL_PollEvent() can drain the
 * controller events first (see below), so a press or a release could be missed: the axis sensor
 * then either needed several presses or never saw the release (input stuck active, cube spinning).
 * The live state is authoritative (same source GetAxisPosition()/aButtonPressIsPositive() read),
 * so any change since the previous frame raises the flags even if the event itself was lost. */
void DEV_Joystick::SyncLiveState()
{
	if (!m_private->m_gamecontroller && !HasVirtualPad()) {
		return;
	}

	/* Merged state (physical + on-screen pad), so the virtual pad also triggers the sensors. */
	for (int i = 0; i < JOYAXIS_MAX && i < SDL_CONTROLLER_AXIS_MAX; i++) {
		const int value = GetAxisPosition(i);
		if (value != m_live_axis[i]) {
			m_live_axis[i] = value;
			m_istrig_axis = 1;
		}
	}

	for (int i = 0; i < 32 && i < SDL_CONTROLLER_BUTTON_MAX; i++) {
		const bool down = aButtonPressIsPositive(i);
		if (down != m_live_button[i]) {
			m_live_button[i] = down;
			m_istrig_button = 1;
		}
	}
}

/* SDL has a single process-wide event queue. GHOST_SystemSDL::processEvents() also
 * polls that same queue for keyboard/mouse/window events. A bare SDL_PollEvent() loop
 * here would drain and silently discard every pending event of every type (see the
 * `default:` case below), starving GHOST whenever this runs first - confirmed as the
 * root cause of keyboard input never reaching the Web/Emscripten build, where sdlew's
 * dynamically-resolved SDL_PollEvent ends up bound to the same real SDL event queue
 * GHOST uses (unlike native Windows, where sdlew loads a separate SDL2.dll instance).
 * SDL_PeepEvents() restricted to the joystick/controller type ranges only removes the
 * events this code actually owns, leaving everything else in the queue for GHOST. */
static int DEV_Joystick_NextEvent(SDL_Event *sdl_event)
{
	if (SDL_PeepEvents(sdl_event, 1, SDL_GETEVENT, SDL_JOYAXISMOTION, SDL_JOYDEVICEREMOVED) > 0) {
		return 1;
	}
	return SDL_PeepEvents(sdl_event, 1, SDL_GETEVENT, SDL_CONTROLLERAXISMOTION, SDL_CONTROLLERSENSORUPDATE);
}

bool DEV_Joystick::HandleEvents(short(&addrem)[JOYINDEX_MAX])
{
	SDL_Event sdl_event;
	bool remap = false;

	if (SDL_PumpEvents == (void *)0 || SDL_PeepEvents == (void *)0) {
		return 0;
	}

	for (int i = 0; i < JOYINDEX_MAX; i++) {
		if (DEV_Joystick::m_instance[i]) {
			DEV_Joystick::m_instance[i]->OnNothing(&sdl_event);
		}
	}

	SDL_PumpEvents();

	while (DEV_Joystick_NextEvent(&sdl_event) > 0) {
		/* Note! m_instance[instance]
		 * will segfault if over JOYINDEX_MAX, not too nice but what are the chances? */

		/* Note!, with buttons, this wont care which button is pressed,
		 * only to set 'm_istrig_button', actual pressed buttons are detected by SDL_ControllerGetButton */

		/* Note!, if you manage to press and release a button within 1 logic tick
		 * it wont work as it should */

		/* Note!, we need to use SDL_JOYDEVICE ADDED to find new controllers as SDL_CONTROLLERDEVICEADDED
		 * doesn't report about all devices connected at beginning. Additionally we capture all devices this
		 * way and we can inform properly (with ways to solve it) if the joystick it is not a game controller */

		switch (sdl_event.type) {
			case SDL_JOYDEVICEADDED:
			{
				if (sdl_event.jdevice.which < JOYINDEX_MAX) {
					DEV_Joystick *existing = DEV_Joystick::m_instance[sdl_event.jdevice.which];
					if (existing && existing->IsVirtualOnly()) {
						/* A physical controller arrives where the on-screen pad was alone: open it in the same
						 * instance, both keep working merged. */
						if (!existing->CreateJoystickDevice()) {
							/* Not a game controller: CreateJoystickDevice() zeroed the ranges, the pad still needs them. */
							existing->m_axismax = SDL_CONTROLLER_AXIS_MAX;
							existing->m_buttonmax = SDL_CONTROLLER_BUTTON_MAX;
						}
						addrem[sdl_event.jdevice.which] = 1;
						remap = true;
					}
					else if (!existing) {
						DEV_Joystick::m_instance[sdl_event.jdevice.which] = new DEV_Joystick(sdl_event.jdevice.which);
						DEV_Joystick::m_instance[sdl_event.jdevice.which]->CreateJoystickDevice();
						addrem[sdl_event.jdevice.which] = 1;
						remap = true;
						break;
					}
					else {
						CM_Warning("conflicts with Joysticks trying to use the same index."
						           << " Please, reconnect Joysticks in different order than before");
					}
				}
				else {
					CM_Warning("maximum quantity (8) of Game Controllers connected. It is not possible to set up additional ones.");
				}
				break;
			}
			case SDL_CONTROLLERDEVICEREMOVED:
			{
				for (int i = 0; i < JOYINDEX_MAX; i++) {
					if (DEV_Joystick::m_instance[i]) {
						if (sdl_event.cdevice.which == DEV_Joystick::m_instance[i]->m_private->m_instance_id) {
							DEV_Joystick::m_instance[i]->ReleaseInstance(i);
							addrem[i] = 2;
							remap = true;
							break;
						}
					}
				}
				break;
			}
			case SDL_CONTROLLERBUTTONDOWN:
			case SDL_CONTROLLERBUTTONUP:
			{
				for (int i = 0; i < JOYINDEX_MAX; i++) {
					if (DEV_Joystick::m_instance[i]) {
						if (sdl_event.cdevice.which == DEV_Joystick::m_instance[i]->m_private->m_instance_id) {
							DEV_Joystick::m_instance[i]->OnButtonEvent(&sdl_event);
							break;
						}
					}
				}
				break;
			}
			case SDL_CONTROLLERAXISMOTION:
			{
				for (int i = 0; i < JOYINDEX_MAX; i++) {
					if (DEV_Joystick::m_instance[i]) {
						if (sdl_event.cdevice.which == DEV_Joystick::m_instance[i]->m_private->m_instance_id) {
							DEV_Joystick::m_instance[i]->OnAxisEvent(&sdl_event);
							break;
						}
					}
				}
				break;
			}
			/* PS4 Touchpad, in case we want to implement it in Range at some point. Warning: It seems not included in Linux :/ */
			//case SDL_CONTROLLERTOUCHPADMOTION:
			//{
			//	//printf("PS4 Touchpad: X: %f, Y: %f\n", sdl_event.ctouchpad.x, sdl_event.ctouchpad.y);
			//	break;
			//}
			default:
			{
				/* ignore old SDL_JOYSTICKS events */
				break;
			}
		}
	}

	/* On-screen pad: index 0 exists while the page shows it, even with no physical controller. */
	DEV_Joystick::ReadVirtualPad();
	DEV_Joystick *first = DEV_Joystick::m_instance[0];
	if (s_padActive && !first) {
		first = DEV_Joystick::m_instance[0] = new DEV_Joystick(0);
		first->m_axismax = SDL_CONTROLLER_AXIS_MAX;
		first->m_buttonmax = SDL_CONTROLLER_BUTTON_MAX;
		addrem[0] = 1;
		remap = true;
	}
	else if (!s_padActive && first && first->IsVirtualOnly()) {
		first->ReleaseInstance(0);
		addrem[0] = 2;
		remap = true;
	}

	for (int i = 0; i < JOYINDEX_MAX; i++) {
		if (DEV_Joystick::m_instance[i]) {
			DEV_Joystick::m_instance[i]->SyncLiveState();
		}
	}

	return remap;
}
#endif /* WITH_SDL */
