/*
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
 */

/** \file ghost/intern/GHOST_SystemSDL.cpp
 *  \ingroup GHOST
 */

#include <assert.h>

#include "GHOST_SystemSDL.h"
#include "GHOST_WindowSDL.h"

#include "GHOST_WindowManager.h"

#include "GHOST_EventCursor.h"
#include "GHOST_EventKey.h"
#include "GHOST_EventButton.h"
#include "GHOST_EventWheel.h"

#ifdef __EMSCRIPTEN__
#include <emscripten.h>
#include <emscripten/html5.h>

/* Web: the browser cannot warp the cursor (SDL's Emscripten_WarpMouse is unsupported), so
 * mouse.reCenter() did nothing and deltaPosition returned the cursor's distance from the center
 * on every frame: a mouse-look camera kept spinning while the cursor was off-center. While the
 * game hides the cursor (mouse-look), GHOST reports a virtual cursor driven by the relative motion
 * (pointer lock, plain mouse move or touch drag) and setCursorPosition() warps that virtual cursor.
 * With a visible cursor (menus) the real absolute position is used, as before. */
static bool web_virtual_cursor = false;
static int web_cursor_x = 0;
static int web_cursor_y = 0;
/* Last position reported to the engine; a warp to the same spot sends no event (like a native warp). */
static int web_reported_x = -1;
static int web_reported_y = -1;

/* Window size the virtual cursor refers to. When the canvas is resized (phone rotated), the cursor keeps
 * its relative position: left at the old center, mouse-look saw a jump and the camera turned. */
static int web_win_w = 0;
static int web_win_h = 0;

static void web_clamp_cursor(SDL_Window *sdl_win)
{
	int w, h;
	SDL_GetWindowSize(sdl_win, &w, &h);
	web_cursor_x = (web_cursor_x < 0) ? 0 : (web_cursor_x > w - 1) ? w - 1 : web_cursor_x;
	web_cursor_y = (web_cursor_y < 0) ? 0 : (web_cursor_y > h - 1) ? h - 1 : web_cursor_y;
}

/* On-screen look stick (tools/web/package-web.py): the page accumulates in Module.rangePad.look how far the view
 * should turn, in fractions of the window size, and the runtime takes it here each frame. It moves the virtual
 * cursor like a finger drag, so a mouse-look game (deltaPosition + reCenter) turns without any change. */
EM_JS(int, ghost_web_take_look, (float *out), {
	var p = (typeof Module !== 'undefined') ? Module.rangePad : null;
	if (!p || !p.active || !p.look) return 0;
	var x = +p.look[0] || 0, y = +p.look[1] || 0;
	p.look[0] = 0;
	p.look[1] = 0;
	if (!x && !y) return 0;
	HEAPF32[out >> 2] = x;
	HEAPF32[(out >> 2) + 1] = y;
	return 1;
});

/* Sub-pixel remainder of the look stick, so a slow turn is not lost to rounding. */
static float web_look_rest_x = 0.0f;
static float web_look_rest_y = 0.0f;
#endif

GHOST_SystemSDL::GHOST_SystemSDL()
    :
      GHOST_System()
{
#ifdef __EMSCRIPTEN__
	/* Emscripten's SDL2 port defaults SDL_HINT_EMSCRIPTEN_KEYBOARD_ELEMENT to "#window",
	 * but emscripten_set_keydown_callback on "#window" returns EMSCRIPTEN_RESULT_NOT_SUPPORTED
	 * in this build, so SDL's keyboard listener never actually attaches. "#canvas" works. */
	SDL_SetHint(SDL_HINT_EMSCRIPTEN_KEYBOARD_ELEMENT, "#canvas");
#endif
	if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_TIMER) != 0) {
		printf("Error initializing SDL:  %s\n", SDL_GetError());
	}

	/* SDL_GL_SetAttribute(SDL_GL_MULTISAMPLEBUFFERS, 1); */
	/* SDL_GL_SetAttribute(SDL_GL_MULTISAMPLESAMPLES, 4); */
	SDL_GL_SetAttribute(SDL_GL_DOUBLEBUFFER, 1);
	SDL_GL_SetAttribute(SDL_GL_DEPTH_SIZE, 24);
	SDL_GL_SetAttribute(SDL_GL_RED_SIZE, 8);
	SDL_GL_SetAttribute(SDL_GL_GREEN_SIZE, 8);
	SDL_GL_SetAttribute(SDL_GL_BLUE_SIZE, 8);
	SDL_GL_SetAttribute(SDL_GL_ALPHA_SIZE, 8);
}

GHOST_SystemSDL::~GHOST_SystemSDL()
{
	SDL_Quit();
}

GHOST_IWindow *
GHOST_SystemSDL::createWindow(const STR_String& title,
                              GHOST_TInt32 left,
                              GHOST_TInt32 top,
                              GHOST_TUns32 width,
                              GHOST_TUns32 height,
                              GHOST_TWindowState state,
                              GHOST_TDrawingContextType type,
                              GHOST_GLSettings glSettings,
                              const bool exclusive,
                              const GHOST_TEmbedderWindowID parentWindow
                              )
{
	GHOST_WindowSDL *window = NULL;

	window = new GHOST_WindowSDL(this, title,
	                             left, top, width, height,
	                             state, parentWindow, type,
	                             ((glSettings.flags & GHOST_glStereoVisual) != 0), exclusive,
	                             glSettings.numOfAASamples);

	if (window) {
		if (GHOST_kWindowStateFullScreen == state) {
			SDL_Window *sdl_win = window->getSDLWindow();
			SDL_DisplayMode mode;

			static_cast<GHOST_DisplayManagerSDL *> (m_displayManager)->getCurrentDisplayModeSDL(mode);

			SDL_SetWindowDisplayMode(sdl_win, &mode);
			SDL_ShowWindow(sdl_win);
			SDL_SetWindowFullscreen(sdl_win, SDL_TRUE);
		}

		if (window->getValid()) {
#ifdef __EMSCRIPTEN__
			SDL_GetWindowSize(window->getSDLWindow(), &web_win_w, &web_win_h);
#endif
			m_windowManager->addWindow(window);
			pushEvent(new GHOST_Event(getMilliSeconds(), GHOST_kEventWindowSize, window));
		}
		else {
			delete window;
			window = NULL;
		}
	}
	return window;
}

GHOST_TSuccess
GHOST_SystemSDL::init() {
	GHOST_TSuccess success = GHOST_System::init();

	if (success) {
		m_displayManager = new GHOST_DisplayManagerSDL(this);

		if (m_displayManager) {
			return GHOST_kSuccess;
		}
	}

	return GHOST_kFailure;
}

/**
 * Returns the dimensions of the main display on this system.
 * \return The dimension of the main display.
 */
void
GHOST_SystemSDL::getAllDisplayDimensions(GHOST_TUns32& width,
                                         GHOST_TUns32& height) const
{
	SDL_DisplayMode mode;
	SDL_GetDesktopDisplayMode(0, &mode); /* note, always 0 display */
	width = mode.w;
	height = mode.h;
}

void
GHOST_SystemSDL::getMainDisplayDimensions(GHOST_TUns32& width,
                                          GHOST_TUns32& height) const
{
	SDL_DisplayMode mode;
	SDL_GetCurrentDisplayMode(0, &mode); /* note, always 0 display */
	width = mode.w;
	height = mode.h;
}

GHOST_TUns8
GHOST_SystemSDL::getNumDisplays() const
{
	return SDL_GetNumVideoDisplays();
}

GHOST_TSuccess
GHOST_SystemSDL::getModifierKeys(GHOST_ModifierKeys& keys) const
{
	SDL_Keymod mod = SDL_GetModState();

	keys.set(GHOST_kModifierKeyLeftShift,    (mod & KMOD_LSHIFT) != 0);
	keys.set(GHOST_kModifierKeyRightShift,   (mod & KMOD_RSHIFT) != 0);
	keys.set(GHOST_kModifierKeyLeftControl,  (mod & KMOD_LCTRL) != 0);
	keys.set(GHOST_kModifierKeyRightControl, (mod & KMOD_RCTRL) != 0);
	keys.set(GHOST_kModifierKeyLeftAlt,      (mod & KMOD_LALT) != 0);
	keys.set(GHOST_kModifierKeyRightAlt,     (mod & KMOD_RALT) != 0);
	keys.set(GHOST_kModifierKeyOS,           (mod & (KMOD_LGUI | KMOD_RGUI)) != 0);

	return GHOST_kSuccess;
}

#define GXMAP(k, x, y) case x: k = y; break

static GHOST_TKey
convertSDLKey(SDL_Scancode key)
{
	GHOST_TKey type;

	if ((key >= SDL_SCANCODE_A) && (key <= SDL_SCANCODE_Z)) {
		type = GHOST_TKey(key - SDL_SCANCODE_A + int(GHOST_kKeyA));
	}
	else if ((key >= SDL_SCANCODE_1) && (key <= SDL_SCANCODE_0)) {
		type = (key == SDL_SCANCODE_0) ? GHOST_kKey0 : GHOST_TKey(key - SDL_SCANCODE_1 + int(GHOST_kKey1));
	}
	else if ((key >= SDL_SCANCODE_F1) && (key <= SDL_SCANCODE_F12)) {
		type = GHOST_TKey(key - SDL_SCANCODE_F1 + int(GHOST_kKeyF1));
	}
	else if ((key >= SDL_SCANCODE_F13) && (key <= SDL_SCANCODE_F24)) {
		type = GHOST_TKey(key - SDL_SCANCODE_F13 + int(GHOST_kKeyF13));
	}
	else {
		switch (key) {
			/* TODO SDL_SCANCODE_NONUSBACKSLASH */

			GXMAP(type, SDL_SCANCODE_BACKSPACE,      GHOST_kKeyBackSpace);
			GXMAP(type, SDL_SCANCODE_TAB,            GHOST_kKeyTab);
			GXMAP(type, SDL_SCANCODE_RETURN,         GHOST_kKeyEnter);
			GXMAP(type, SDL_SCANCODE_ESCAPE,         GHOST_kKeyEsc);
			GXMAP(type, SDL_SCANCODE_SPACE,          GHOST_kKeySpace);

			GXMAP(type, SDL_SCANCODE_SEMICOLON,      GHOST_kKeySemicolon);
			GXMAP(type, SDL_SCANCODE_PERIOD,         GHOST_kKeyPeriod);
			GXMAP(type, SDL_SCANCODE_COMMA,          GHOST_kKeyComma);
			GXMAP(type, SDL_SCANCODE_APOSTROPHE,     GHOST_kKeyQuote);
			GXMAP(type, SDL_SCANCODE_GRAVE,          GHOST_kKeyAccentGrave);
			GXMAP(type, SDL_SCANCODE_MINUS,          GHOST_kKeyMinus);
			GXMAP(type, SDL_SCANCODE_EQUALS,         GHOST_kKeyEqual);

			GXMAP(type, SDL_SCANCODE_SLASH,          GHOST_kKeySlash);
			GXMAP(type, SDL_SCANCODE_BACKSLASH,      GHOST_kKeyBackslash);
			GXMAP(type, SDL_SCANCODE_KP_EQUALS,      GHOST_kKeyEqual);
			GXMAP(type, SDL_SCANCODE_LEFTBRACKET,    GHOST_kKeyLeftBracket);
			GXMAP(type, SDL_SCANCODE_RIGHTBRACKET,   GHOST_kKeyRightBracket);
			GXMAP(type, SDL_SCANCODE_PAUSE,          GHOST_kKeyPause);

			GXMAP(type, SDL_SCANCODE_LSHIFT,         GHOST_kKeyLeftShift);
			GXMAP(type, SDL_SCANCODE_RSHIFT,         GHOST_kKeyRightShift);
			GXMAP(type, SDL_SCANCODE_LCTRL,          GHOST_kKeyLeftControl);
			GXMAP(type, SDL_SCANCODE_RCTRL,          GHOST_kKeyRightControl);
			GXMAP(type, SDL_SCANCODE_LALT,           GHOST_kKeyLeftAlt);
			GXMAP(type, SDL_SCANCODE_RALT,           GHOST_kKeyRightAlt);
			GXMAP(type, SDL_SCANCODE_LGUI,           GHOST_kKeyOS);
			GXMAP(type, SDL_SCANCODE_RGUI,           GHOST_kKeyOS);

			GXMAP(type, SDL_SCANCODE_INSERT,         GHOST_kKeyInsert);
			GXMAP(type, SDL_SCANCODE_DELETE,         GHOST_kKeyDelete);
			GXMAP(type, SDL_SCANCODE_HOME,           GHOST_kKeyHome);
			GXMAP(type, SDL_SCANCODE_END,            GHOST_kKeyEnd);
			GXMAP(type, SDL_SCANCODE_PAGEUP,         GHOST_kKeyUpPage);
			GXMAP(type, SDL_SCANCODE_PAGEDOWN,       GHOST_kKeyDownPage);

			GXMAP(type, SDL_SCANCODE_LEFT,           GHOST_kKeyLeftArrow);
			GXMAP(type, SDL_SCANCODE_RIGHT,          GHOST_kKeyRightArrow);
			GXMAP(type, SDL_SCANCODE_UP,             GHOST_kKeyUpArrow);
			GXMAP(type, SDL_SCANCODE_DOWN,           GHOST_kKeyDownArrow);

			GXMAP(type, SDL_SCANCODE_CAPSLOCK,       GHOST_kKeyCapsLock);
			GXMAP(type, SDL_SCANCODE_SCROLLLOCK,     GHOST_kKeyScrollLock);
			GXMAP(type, SDL_SCANCODE_NUMLOCKCLEAR,   GHOST_kKeyNumLock);
			GXMAP(type, SDL_SCANCODE_PRINTSCREEN,    GHOST_kKeyPrintScreen);

			/* keypad events */

			/* note, sdl defines a bunch of kp defines I never saw before like
			 * SDL_SCANCODE_KP_PERCENT, SDL_SCANCODE_KP_XOR - campbell */
			GXMAP(type, SDL_SCANCODE_KP_0,           GHOST_kKeyNumpad0);
			GXMAP(type, SDL_SCANCODE_KP_1,           GHOST_kKeyNumpad1);
			GXMAP(type, SDL_SCANCODE_KP_2,           GHOST_kKeyNumpad2);
			GXMAP(type, SDL_SCANCODE_KP_3,           GHOST_kKeyNumpad3);
			GXMAP(type, SDL_SCANCODE_KP_4,           GHOST_kKeyNumpad4);
			GXMAP(type, SDL_SCANCODE_KP_5,           GHOST_kKeyNumpad5);
			GXMAP(type, SDL_SCANCODE_KP_6,           GHOST_kKeyNumpad6);
			GXMAP(type, SDL_SCANCODE_KP_7,           GHOST_kKeyNumpad7);
			GXMAP(type, SDL_SCANCODE_KP_8,           GHOST_kKeyNumpad8);
			GXMAP(type, SDL_SCANCODE_KP_9,           GHOST_kKeyNumpad9);
			GXMAP(type, SDL_SCANCODE_KP_PERIOD,      GHOST_kKeyNumpadPeriod);

			GXMAP(type, SDL_SCANCODE_KP_ENTER,       GHOST_kKeyNumpadEnter);
			GXMAP(type, SDL_SCANCODE_KP_PLUS,        GHOST_kKeyNumpadPlus);
			GXMAP(type, SDL_SCANCODE_KP_MINUS,       GHOST_kKeyNumpadMinus);
			GXMAP(type, SDL_SCANCODE_KP_MULTIPLY,    GHOST_kKeyNumpadAsterisk);
			GXMAP(type, SDL_SCANCODE_KP_DIVIDE,      GHOST_kKeyNumpadSlash);

			/* Media keys in some keyboards and laptops with XFree86/Xorg */
			GXMAP(type, SDL_SCANCODE_AUDIOPLAY,      GHOST_kKeyMediaPlay);
			GXMAP(type, SDL_SCANCODE_AUDIOSTOP,      GHOST_kKeyMediaStop);
			GXMAP(type, SDL_SCANCODE_AUDIOPREV,      GHOST_kKeyMediaFirst);
			// GXMAP(type,XF86XK_AudioRewind,       GHOST_kKeyMediaFirst);
			GXMAP(type, SDL_SCANCODE_AUDIONEXT,      GHOST_kKeyMediaLast);

			default:
				printf("Unknown\n");
				type = GHOST_kKeyUnknown;
				break;
		}
	}

	return type;
}
#undef GXMAP

/**
 * Events don't always have valid windows,
 * but GHOST needs a window _always_. fallback to the GL window.
 */
static SDL_Window *SDL_GetWindowFromID_fallback(Uint32 id)
{
	SDL_Window *sdl_win = SDL_GetWindowFromID(id);
	if (sdl_win == NULL) {
		sdl_win = SDL_GL_GetCurrentWindow();
	}
	return sdl_win;
}

void
GHOST_SystemSDL::processEvent(SDL_Event *sdl_event)
{
	GHOST_Event *g_event = NULL;

	switch (sdl_event->type) {
		case SDL_WINDOWEVENT:
		{
			SDL_WindowEvent &sdl_sub_evt = sdl_event->window;
			GHOST_WindowSDL *window = findGhostWindow(SDL_GetWindowFromID_fallback(sdl_sub_evt.windowID));
			//assert(window != NULL); // can be NULL on close window.

			switch (sdl_sub_evt.event) {
				case SDL_WINDOWEVENT_EXPOSED:
					g_event = new GHOST_Event(getMilliSeconds(), GHOST_kEventWindowUpdate, window);
					break;
				case SDL_WINDOWEVENT_RESIZED:
					g_event = new GHOST_Event(getMilliSeconds(), GHOST_kEventWindowSize, window);
#ifdef __EMSCRIPTEN__
					if (window && web_virtual_cursor && web_win_w > 0 && web_win_h > 0 &&
					    sdl_sub_evt.data1 > 0 && sdl_sub_evt.data2 > 0)
					{
						SDL_Window *sdl_win = window->getSDLWindow();
						web_cursor_x = web_cursor_x * sdl_sub_evt.data1 / web_win_w;
						web_cursor_y = web_cursor_y * sdl_sub_evt.data2 / web_win_h;
						web_clamp_cursor(sdl_win);
						if (web_cursor_x != web_reported_x || web_cursor_y != web_reported_y) {
							int x_win, y_win;
							SDL_GetWindowPosition(sdl_win, &x_win, &y_win);
							web_reported_x = web_cursor_x;
							web_reported_y = web_cursor_y;
							pushEvent(new GHOST_EventCursor(getMilliSeconds(), GHOST_kEventCursorMove, window,
							                                web_cursor_x + x_win, web_cursor_y + y_win));
						}
					}
					web_win_w = sdl_sub_evt.data1;
					web_win_h = sdl_sub_evt.data2;
#endif
					break;
				case SDL_WINDOWEVENT_MOVED:
					g_event = new GHOST_Event(getMilliSeconds(), GHOST_kEventWindowMove, window);
					break;
				case SDL_WINDOWEVENT_FOCUS_GAINED:
					g_event = new GHOST_Event(getMilliSeconds(), GHOST_kEventWindowActivate, window);
					break;
				case SDL_WINDOWEVENT_FOCUS_LOST:
					g_event = new GHOST_Event(getMilliSeconds(), GHOST_kEventWindowDeactivate, window);
					break;
				case SDL_WINDOWEVENT_CLOSE:
					g_event = new GHOST_Event(getMilliSeconds(), GHOST_kEventWindowClose, window);
					break;
			}

			break;
		}
		case SDL_QUIT:
			g_event = new GHOST_Event(getMilliSeconds(), GHOST_kEventQuit, NULL);
			break;

		case SDL_MOUSEMOTION:
		{
			SDL_MouseMotionEvent &sdl_sub_evt = sdl_event->motion;
			SDL_Window *sdl_win = SDL_GetWindowFromID_fallback(sdl_sub_evt.windowID);
			GHOST_WindowSDL *window = findGhostWindow(sdl_win);
			assert(window != NULL);

			int x_win, y_win;
			SDL_GetWindowPosition(sdl_win, &x_win, &y_win);

			GHOST_TInt32 x_root = sdl_sub_evt.x + x_win;
			GHOST_TInt32 y_root = sdl_sub_evt.y + y_win;

#ifdef __EMSCRIPTEN__
			if (!window->getCursorVisibility()) {
				if (web_virtual_cursor) {
					/* xrel is 0 on the event that places a new touch, so a new finger does not jump. */
					web_cursor_x += sdl_sub_evt.xrel;
					web_cursor_y += sdl_sub_evt.yrel;
				}
				else {
					web_cursor_x = sdl_sub_evt.x;
					web_cursor_y = sdl_sub_evt.y;
					web_virtual_cursor = true;
				}
				web_clamp_cursor(sdl_win);
				x_root = web_cursor_x + x_win;
				y_root = web_cursor_y + y_win;
				web_reported_x = web_cursor_x;
				web_reported_y = web_cursor_y;
			}
			else {
				web_virtual_cursor = false;
			}
#endif

#if 0
			if (window->getCursorGrabMode() != GHOST_kGrabDisable && window->getCursorGrabMode() != GHOST_kGrabNormal)
			{
				GHOST_TInt32 x_new = x_root;
				GHOST_TInt32 y_new = y_root;
				GHOST_TInt32 x_accum, y_accum;
				GHOST_Rect bounds;

				/* fallback to window bounds */
				if (window->getCursorGrabBounds(bounds) == GHOST_kFailure)
					window->getClientBounds(bounds);

				/* could also clamp to screen bounds
				 * wrap with a window outside the view will fail atm  */
				bounds.wrapPoint(x_new, y_new, 8); /* offset of one incase blender is at screen bounds */
				window->getCursorGrabAccum(x_accum, y_accum);

				// cant use setCursorPosition because the mouse may have no focus!
				if (x_new != x_root || y_new != y_root) {
					if (1) {  //xme.time > m_last_warp) {
						/* when wrapping we don't need to add an event because the
						 * setCursorPosition call will cause a new event after */
						SDL_WarpMouseInWindow(sdl_win, x_new - x_win, y_new - y_win); /* wrap */
						window->setCursorGrabAccum(x_accum + (x_root - x_new), y_accum + (y_root - y_new));
						// m_last_warp= lastEventTime(xme.time);
					}
					else {
						// setCursorPosition(x_new, y_new); /* wrap but don't accumulate */
						SDL_WarpMouseInWindow(sdl_win, x_new - x_win, y_new - y_win);
					}

					g_event = new GHOST_EventCursor(getMilliSeconds(), GHOST_kEventCursorMove, window, x_new, y_new);
				}
				else {
					g_event = new GHOST_EventCursor(getMilliSeconds(), GHOST_kEventCursorMove, window, x_root + x_accum, y_root + y_accum);
				}
			}
			else
#endif
			{
				g_event = new GHOST_EventCursor(getMilliSeconds(), GHOST_kEventCursorMove, window, x_root, y_root);
			}
			break;
		}
		case SDL_MOUSEBUTTONUP:
		case SDL_MOUSEBUTTONDOWN:
		{
			SDL_MouseButtonEvent &sdl_sub_evt = sdl_event->button;
			GHOST_TButtonMask gbmask = GHOST_kButtonMaskLeft;
			GHOST_TEventType type = (sdl_sub_evt.state == SDL_PRESSED) ? GHOST_kEventButtonDown : GHOST_kEventButtonUp;

			GHOST_WindowSDL *window = findGhostWindow(SDL_GetWindowFromID_fallback(sdl_sub_evt.windowID));
			assert(window != NULL);

#ifdef __EMSCRIPTEN__
			/* Mouse-look: (re)lock the pointer on a real mouse click, e.g. after Esc released it.
			 * Deferred: the browser only grants it inside a user input handler. */
			if (type == GHOST_kEventButtonDown && sdl_sub_evt.which != SDL_TOUCH_MOUSEID &&
			    !window->getCursorVisibility())
			{
				EmscriptenPointerlockChangeEvent lock;
				if (emscripten_get_pointerlock_status(&lock) == EMSCRIPTEN_RESULT_SUCCESS && !lock.isActive) {
					emscripten_request_pointerlock("#canvas", 1);
				}
			}
#endif

			/* process rest of normal mouse buttons */
			if (sdl_sub_evt.button == SDL_BUTTON_LEFT)
				gbmask = GHOST_kButtonMaskLeft;
			else if (sdl_sub_evt.button == SDL_BUTTON_MIDDLE)
				gbmask = GHOST_kButtonMaskMiddle;
			else if (sdl_sub_evt.button == SDL_BUTTON_RIGHT)
				gbmask = GHOST_kButtonMaskRight;
			/* these buttons are untested! */
			else if (sdl_sub_evt.button == SDL_BUTTON_X1)
				gbmask = GHOST_kButtonMaskButton4;
			else if (sdl_sub_evt.button == SDL_BUTTON_X2)
				gbmask = GHOST_kButtonMaskButton5;
			else
				break;

			g_event = new GHOST_EventButton(getMilliSeconds(), type, window, gbmask);
			break;
		}
		case SDL_MOUSEWHEEL:
		{
			SDL_MouseWheelEvent &sdl_sub_evt = sdl_event->wheel;
			GHOST_WindowSDL *window = findGhostWindow(SDL_GetWindowFromID_fallback(sdl_sub_evt.windowID));
			assert(window != NULL);
			g_event = new GHOST_EventWheel(getMilliSeconds(), window, sdl_sub_evt.y);
			break;
		}
		case SDL_KEYDOWN:
		case SDL_KEYUP:
		{
			SDL_KeyboardEvent &sdl_sub_evt = sdl_event->key;
			SDL_Keycode sym = sdl_sub_evt.keysym.sym;
			GHOST_TEventType type = (sdl_sub_evt.state == SDL_PRESSED) ? GHOST_kEventKeyDown : GHOST_kEventKeyUp;

			GHOST_WindowSDL *window = findGhostWindow(SDL_GetWindowFromID_fallback(sdl_sub_evt.windowID));
			assert(window != NULL);

			GHOST_TKey gkey = convertSDLKey(sdl_sub_evt.keysym.scancode);
			/* note, the sdl_sub_evt.keysym.sym is truncated, for unicode support ghost has to be modified */
			/* printf("%d\n", sym); */
			if (sym > 127) {
				switch (sym) {
					case SDLK_KP_DIVIDE: sym = '/'; break;
					case SDLK_KP_MULTIPLY: sym = '*'; break;
					case SDLK_KP_MINUS: sym = '-'; break;
					case SDLK_KP_PLUS: sym = '+'; break;
					case SDLK_KP_1: sym = '1'; break;
					case SDLK_KP_2: sym = '2'; break;
					case SDLK_KP_3: sym = '3'; break;
					case SDLK_KP_4: sym = '4'; break;
					case SDLK_KP_5: sym = '5'; break;
					case SDLK_KP_6: sym = '6'; break;
					case SDLK_KP_7: sym = '7'; break;
					case SDLK_KP_8: sym = '8'; break;
					case SDLK_KP_9: sym = '9'; break;
					case SDLK_KP_0: sym = '0'; break;
					case SDLK_KP_PERIOD: sym = '.'; break;
					default: sym = 0; break;
				}
			}
			else {
				if (sdl_sub_evt.keysym.mod & (KMOD_LSHIFT | KMOD_RSHIFT)) {
					/* lame US keyboard assumptions */
					if (sym >= 'a' && sym <= ('a' + 32)) {
						sym -= 32;
					}
					else {
						switch (sym) {
							case '`': sym = '~'; break;
							case '1': sym = '!'; break;
							case '2': sym = '@'; break;
							case '3': sym = '#'; break;
							case '4': sym = '$'; break;
							case '5': sym = '%'; break;
							case '6': sym = '^'; break;
							case '7': sym = '&'; break;
							case '8': sym = '*'; break;
							case '9': sym = '('; break;
							case '0': sym = ')'; break;
							case '-': sym = '_'; break;
							case '=': sym = '+'; break;
							case '[': sym = '{'; break;
							case ']': sym = '}'; break;
							case '\\': sym = '|'; break;
							case ';': sym = ':'; break;
							case '\'': sym = '"'; break;
							case ',': sym = '<'; break;
							case '.': sym = '>'; break;
							case '/': sym = '?'; break;
							default:            break;
						}
					}
				}
			}

			g_event = new GHOST_EventKey(getMilliSeconds(), type, window, gkey, sym, NULL);
			break;
		}
	}

	if (g_event) {
		pushEvent(g_event);
	}
}

GHOST_TSuccess
GHOST_SystemSDL::getCursorPosition(GHOST_TInt32& x,
                                   GHOST_TInt32& y) const
{
	int x_win, y_win;
	SDL_Window *win = SDL_GetMouseFocus();
	SDL_GetWindowPosition(win, &x_win, &y_win);

	int xi, yi;
	SDL_GetMouseState(&xi, &yi);
	x = xi + x_win;
	y = yi + x_win;

	return GHOST_kSuccess;
}

GHOST_TSuccess
GHOST_SystemSDL::setCursorPosition(GHOST_TInt32 x,
                                   GHOST_TInt32 y)
{
	int x_win, y_win;
	SDL_Window *win = SDL_GetMouseFocus();
#ifdef __EMSCRIPTEN__
	/* Touch or a cursor outside the canvas leave no mouse focus; the Web build has one window. */
	GHOST_WindowSDL *window = static_cast<GHOST_WindowSDL *>(m_windowManager->getActiveWindow());
	if (!window && !m_windowManager->getWindows().empty()) {
		window = static_cast<GHOST_WindowSDL *>(m_windowManager->getWindows().front());
	}
	if (window && !window->getCursorVisibility()) {
		win = window->getSDLWindow();
		SDL_GetWindowPosition(win, &x_win, &y_win);
		web_cursor_x = x - x_win;
		web_cursor_y = y - y_win;
		web_virtual_cursor = true;
		web_clamp_cursor(win);
		/* A native warp produces a motion event only when the position changes; emulate that so the
		 * engine sees the new position without an event per reCenter() while the mouse is still. */
		if (web_cursor_x != web_reported_x || web_cursor_y != web_reported_y) {
			web_reported_x = web_cursor_x;
			web_reported_y = web_cursor_y;
			pushEvent(new GHOST_EventCursor(getMilliSeconds(), GHOST_kEventCursorMove, window,
			                                web_cursor_x + x_win, web_cursor_y + y_win));
		}
		return GHOST_kSuccess;
	}
	if (!win) {
		return GHOST_kFailure;
	}
#endif
	SDL_GetWindowPosition(win, &x_win, &y_win);

	SDL_WarpMouseInWindow(win, x - x_win, y - y_win);
	return GHOST_kSuccess;
}

bool
GHOST_SystemSDL::generateWindowExposeEvents()
{
	std::vector<GHOST_WindowSDL *>::iterator w_start = m_dirty_windows.begin();
	std::vector<GHOST_WindowSDL *>::const_iterator w_end = m_dirty_windows.end();
	bool anyProcessed = false;

	for (; w_start != w_end; ++w_start) {
		GHOST_Event *g_event = new
		                       GHOST_Event(
		                           getMilliSeconds(),
		                           GHOST_kEventWindowUpdate,
		                           *w_start
		                           );

		(*w_start)->validate();

		if (g_event) {
			//printf("Expose events pushed\n");
			pushEvent(g_event);
			anyProcessed = true;
		}
	}

	m_dirty_windows.clear();
	return anyProcessed;
}


bool
GHOST_SystemSDL::processEvents(bool waitForEvent)
{
	// Get all the current events -- translate them into
	// ghost events and call base class pushEvent() method.

	bool anyProcessed = false;

	do {
		GHOST_TimerManager *timerMgr = getTimerManager();

		if (waitForEvent && m_dirty_windows.empty() && !SDL_HasEvents(SDL_FIRSTEVENT, SDL_LASTEVENT)) {
			GHOST_TUns64 next = timerMgr->nextFireTime();

			if (next == GHOST_kFireTimeNever) {
				SDL_WaitEventTimeout(NULL, -1);
				//SleepTillEvent(m_display, -1);
			}
			else {
				GHOST_TInt64 maxSleep = next - getMilliSeconds();

				if (maxSleep >= 0) {
					SDL_WaitEventTimeout(NULL, next - getMilliSeconds());
					// SleepTillEvent(m_display, next - getMilliSeconds()); // X11
				}
			}
		}

		if (timerMgr->fireTimers(getMilliSeconds())) {
			anyProcessed = true;
		}

		SDL_Event sdl_event;
		while (SDL_PollEvent(&sdl_event)) {
			processEvent(&sdl_event);
			anyProcessed = true;
		}

#ifdef __EMSCRIPTEN__
		if (processWebLook()) {
			anyProcessed = true;
		}
#endif

		if (generateWindowExposeEvents()) {
			anyProcessed = true;
		}
	} while (waitForEvent && !anyProcessed);

	return anyProcessed;
}


#ifdef __EMSCRIPTEN__
bool
GHOST_SystemSDL::processWebLook()
{
	float look[2];
	if (!ghost_web_take_look(look)) {
		return false;
	}
	GHOST_WindowSDL *window = static_cast<GHOST_WindowSDL *>(m_windowManager->getActiveWindow());
	if (!window && !m_windowManager->getWindows().empty()) {
		window = static_cast<GHOST_WindowSDL *>(m_windowManager->getWindows().front());
	}
	/* Only in mouse-look (hidden cursor); with a visible cursor (menus) the stick does nothing. */
	if (!window || window->getCursorVisibility()) {
		web_look_rest_x = web_look_rest_y = 0.0f;
		return false;
	}
	SDL_Window *sdl_win = window->getSDLWindow();
	int w, h, x_win, y_win;
	SDL_GetWindowSize(sdl_win, &w, &h);
	SDL_GetWindowPosition(sdl_win, &x_win, &y_win);
	web_look_rest_x += look[0] * w;
	web_look_rest_y += look[1] * h;
	const int dx = (int)web_look_rest_x, dy = (int)web_look_rest_y;
	web_look_rest_x -= dx;
	web_look_rest_y -= dy;
	if (!web_virtual_cursor) {
		web_cursor_x = w / 2;
		web_cursor_y = h / 2;
		web_virtual_cursor = true;
	}
	web_cursor_x += dx;
	web_cursor_y += dy;
	web_clamp_cursor(sdl_win);
	if (web_cursor_x == web_reported_x && web_cursor_y == web_reported_y) {
		return false;
	}
	web_reported_x = web_cursor_x;
	web_reported_y = web_cursor_y;
	pushEvent(new GHOST_EventCursor(getMilliSeconds(), GHOST_kEventCursorMove, window,
	                                web_cursor_x + x_win, web_cursor_y + y_win));
	return true;
}
#endif

GHOST_WindowSDL *
GHOST_SystemSDL::findGhostWindow(SDL_Window *sdl_win)
{
	if (sdl_win == NULL) return NULL;

	// It is not entirely safe to do this as the backptr may point
	// to a window that has recently been removed.
	// We should always check the window manager's list of windows
	// and only process events on these windows.

	std::vector<GHOST_IWindow *> & win_vec = m_windowManager->getWindows();

	std::vector<GHOST_IWindow *>::iterator win_it = win_vec.begin();
	std::vector<GHOST_IWindow *>::const_iterator win_end = win_vec.end();

	for (; win_it != win_end; ++win_it) {
		GHOST_WindowSDL *window = static_cast<GHOST_WindowSDL *>(*win_it);
		if (window->getSDLWindow() == sdl_win) {
			return window;
		}
	}
	return NULL;
}


void
GHOST_SystemSDL::addDirtyWindow(GHOST_WindowSDL *bad_wind)
{
	GHOST_ASSERT((bad_wind != NULL), "addDirtyWindow() NULL ptr trapped (window)");

	m_dirty_windows.push_back(bad_wind);
}

bool
GHOST_SystemSDL::supportsNativeDialogs(void)
{
	return false;
}

GHOST_TSuccess GHOST_SystemSDL::getButtons(GHOST_Buttons& buttons) const
{
	Uint8 state = SDL_GetMouseState(NULL, NULL);
	buttons.set(GHOST_kButtonMaskLeft,   (state & SDL_BUTTON_LMASK) != 0);
	buttons.set(GHOST_kButtonMaskMiddle, (state & SDL_BUTTON_MMASK) != 0);
	buttons.set(GHOST_kButtonMaskRight,  (state & SDL_BUTTON_RMASK) != 0);

	return GHOST_kSuccess;
}

GHOST_TUns8 *
GHOST_SystemSDL::getClipboard(bool selection) const
{
	return (GHOST_TUns8 *)SDL_GetClipboardText();
}

void
GHOST_SystemSDL::putClipboard(GHOST_TInt8 *buffer, bool selection) const
{
	SDL_SetClipboardText(buffer);
}

GHOST_TUns64
GHOST_SystemSDL::getMilliSeconds()
{
	return GHOST_TUns64(SDL_GetTicks()); /* note, 32 -> 64bits */
}
