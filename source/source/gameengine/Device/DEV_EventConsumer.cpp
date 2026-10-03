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
 * Contributor(s): Tristan Porteries.
 *
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file gameengine/Device/DEV_EventConsumer.cpp
 *  \ingroup device
 */


#include "DEV_EventConsumer.h"
#include "DEV_InputDevice.h"

#include "GHOST_IEvent.h"
#include "GHOST_IWindow.h"
#include "GHOST_ISystem.h"

#include "RAS_ICanvas.h"

#include "BLI_string_utf8.h"

#include <iostream>

DEV_EventConsumer::DEV_EventConsumer(GHOST_ISystem *system, DEV_InputDevice *device, RAS_ICanvas *canvas)
	:m_device(device),
	m_canvas(canvas),
	m_focusGate(false),
	m_cursorInside(true)
{
	// Setup the default mouse position.
	int cursorx, cursory;
	system->getCursorPosition(cursorx, cursory);
	int x, y;
	m_canvas->ConvertMousePosition(cursorx, cursory, x, y, true);
	m_device->ConvertMoveEvent(x, y);
	UpdateCursorInside(x, y);
}

DEV_EventConsumer::~DEV_EventConsumer()
{
}

void DEV_EventConsumer::SetFocusGate(bool gate)
{
	m_focusGate = gate;
}

void DEV_EventConsumer::UpdateCursorInside(int x, int y)
{
	m_cursorInside = (x >= 0 && y >= 0 && x < m_canvas->GetWidth() && y < m_canvas->GetHeight());
}

void DEV_EventConsumer::HandleWindowEvent(GHOST_TEventType type)
{
	m_device->ConvertWindowEvent(type);
}

void DEV_EventConsumer::HandleKeyEvent(GHOST_TEventDataPtr data, bool down)
{
	GHOST_TEventKeyData *keyData = (GHOST_TEventKeyData *)data;
	unsigned int unicode = keyData->utf8_buf[0] ? BLI_str_utf8_as_unicode(keyData->utf8_buf) : keyData->ascii;
	m_device->ConvertKeyEvent(keyData->key, down, unicode);
}

void DEV_EventConsumer::HandleCursorEvent(GHOST_TEventDataPtr data, GHOST_IWindow *window)
{
	GHOST_TEventCursorData *cursorData = (GHOST_TEventCursorData *)data;
	int x, y;
	m_canvas->ConvertMousePosition(cursorData->x, cursorData->y, x, y, false);

	m_device->ConvertMoveEvent(x, y);
	UpdateCursorInside(x, y);
}

void DEV_EventConsumer::HandleWheelEvent(GHOST_TEventDataPtr data)
{
	GHOST_TEventWheelData *wheelData = (GHOST_TEventWheelData *)data;

	m_device->ConvertWheelEvent(wheelData->z);
}

void DEV_EventConsumer::HandleButtonEvent(GHOST_TEventDataPtr data, bool down)
{
	GHOST_TEventButtonData *buttonData = (GHOST_TEventButtonData *)data;

	m_device->ConvertButtonEvent(buttonData->button, down);
}

bool DEV_EventConsumer::processEvent(GHOST_IEvent *event)
{
	GHOST_TEventDataPtr eventData = ((GHOST_IEvent *)event)->getData();
	if (m_focusGate && !m_cursorInside) {
		switch (event->getType()) {
			case GHOST_kEventButtonDown:
			case GHOST_kEventWheel:
			case GHOST_kEventKeyDown:
				return true;
			default:
				break;
		}
	}
	switch (event->getType()) {
		case GHOST_kEventButtonDown:
		{
			HandleButtonEvent(eventData, true);
			break;
		}

		case GHOST_kEventButtonUp:
		{
			HandleButtonEvent(eventData, false);
			break;
		}

		case GHOST_kEventWheel:
		{
			HandleWheelEvent(eventData);
			break;
		}

		case GHOST_kEventCursorMove:
		{
			HandleCursorEvent(eventData, event->getWindow());
			break;
		}

		case GHOST_kEventKeyDown:
		{
			HandleKeyEvent(eventData, true);
			break;
		}
		case GHOST_kEventKeyUp:
		{
			HandleKeyEvent(eventData, false);
			break;
		}
		case GHOST_kEventWindowSize:
		case GHOST_kEventWindowClose:
		case GHOST_kEventQuit:
		{
			HandleWindowEvent(event->getType());
			break;
		}
		default:
		{
			break;
		}
	}

	return true;
}
