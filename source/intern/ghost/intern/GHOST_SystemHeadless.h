/*
 * ***** BEGIN GPL LICENSE BLOCK *****
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 *
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file ghost/intern/GHOST_SystemHeadless.h
 *  \ingroup GHOST
 *
 * Runtime-selected headless system for the game player's --server mode (Linux):
 * no display connection and no window. The GL context is an EGL "surfaceless"
 * context (EGL_MESA_platform_surfaceless), so the engine still gets a current
 * OpenGL context for GPU_init/scene conversion without X11 or xvfb.
 *
 * libEGL is opened with dlopen, so the player does not link against it and a
 * machine without EGL only fails when --server is actually used.
 */

#ifndef __GHOST_SYSTEMHEADLESS_H__
#define __GHOST_SYSTEMHEADLESS_H__

#include <chrono>
#include <cstdio>
#include <dlfcn.h>

#include "GHOST_Context.h"
#include "GHOST_SystemNULL.h"
#include "GHOST_WindowNULL.h"
#include "GHOST_WindowManager.h"

/* Minimal EGL declarations: avoids depending on the EGL headers at build time. */
namespace GHOST_HeadlessEGL {
typedef void *Display;
typedef void *Config;
typedef void *Context;
typedef int Int;
typedef unsigned int Boolean;
typedef unsigned int Enum;

enum : Int {
	NONE = 0x3038,
	SURFACE_TYPE = 0x3033,
	PBUFFER_BIT = 0x0001,
	RENDERABLE_TYPE = 0x3040,
	OPENGL_BIT = 0x0008,
	CONTEXT_OPENGL_PROFILE_MASK = 0x30FD,
	CONTEXT_OPENGL_COMPATIBILITY_PROFILE_BIT = 0x0002,
};
enum : Enum {
	OPENGL_API = 0x30A2,
	PLATFORM_SURFACELESS_MESA = 0x31DD,
};

struct Api {
	void *lib = nullptr;
	void *(*getProcAddress)(const char *) = nullptr;
	Display (*getPlatformDisplayEXT)(Enum, void *, const Int *) = nullptr;
	Boolean (*initialize)(Display, Int *, Int *) = nullptr;
	Boolean (*terminate)(Display) = nullptr;
	Boolean (*bindAPI)(Enum) = nullptr;
	Boolean (*chooseConfig)(Display, const Int *, Config *, Int, Int *) = nullptr;
	Context (*createContext)(Display, Config, Context, const Int *) = nullptr;
	Boolean (*destroyContext)(Display, Context) = nullptr;
	Boolean (*makeCurrent)(Display, void *, void *, Context) = nullptr;
	Int (*getError)() = nullptr;

	bool load()
	{
		lib = dlopen("libEGL.so.1", RTLD_NOW | RTLD_GLOBAL);
		if (!lib) {
			lib = dlopen("libEGL.so", RTLD_NOW | RTLD_GLOBAL);
		}
		if (!lib) {
			return false;
		}
		getProcAddress = (void *(*)(const char *))dlsym(lib, "eglGetProcAddress");
		initialize = (Boolean (*)(Display, Int *, Int *))dlsym(lib, "eglInitialize");
		terminate = (Boolean (*)(Display))dlsym(lib, "eglTerminate");
		bindAPI = (Boolean (*)(Enum))dlsym(lib, "eglBindAPI");
		chooseConfig = (Boolean (*)(Display, const Int *, Config *, Int, Int *))dlsym(lib, "eglChooseConfig");
		createContext = (Context (*)(Display, Config, Context, const Int *))dlsym(lib, "eglCreateContext");
		destroyContext = (Boolean (*)(Display, Context))dlsym(lib, "eglDestroyContext");
		makeCurrent = (Boolean (*)(Display, void *, void *, Context))dlsym(lib, "eglMakeCurrent");
		getError = (Int (*)())dlsym(lib, "eglGetError");
		if (getProcAddress) {
			getPlatformDisplayEXT = (Display (*)(Enum, void *, const Int *))getProcAddress("eglGetPlatformDisplayEXT");
		}
		return getProcAddress && getPlatformDisplayEXT && initialize && terminate && bindAPI && chooseConfig &&
		       createContext && destroyContext && makeCurrent && getError;
	}
};
}  // namespace GHOST_HeadlessEGL

class GHOST_ContextHeadless : public GHOST_Context {
public:
	GHOST_ContextHeadless() : GHOST_Context(false, 0) {}

	~GHOST_ContextHeadless()
	{
		if (m_context) {
			m_egl.makeCurrent(m_display, nullptr, nullptr, nullptr);
			m_egl.destroyContext(m_display, m_context);
		}
		if (m_display) {
			m_egl.terminate(m_display);
		}
		/* libEGL stays loaded: Mesa does not like being unloaded mid-process. */
	}

	/* There is no surface: nothing to present. */
	GHOST_TSuccess swapBuffers() { return GHOST_kSuccess; }

	GHOST_TSuccess activateDrawingContext()
	{
		return m_egl.makeCurrent(m_display, nullptr, nullptr, m_context) ? GHOST_kSuccess : GHOST_kFailure;
	}

	GHOST_TSuccess initializeDrawingContext()
	{
		using namespace GHOST_HeadlessEGL;
		if (!m_egl.load()) {
			fprintf(stderr, "GHOST headless: libEGL (with eglGetPlatformDisplayEXT) not found\n");
			return GHOST_kFailure;
		}
		m_display = m_egl.getPlatformDisplayEXT(PLATFORM_SURFACELESS_MESA, nullptr, nullptr);
		Int major, minor;
		if (!m_display || !m_egl.initialize(m_display, &major, &minor)) {
			fprintf(stderr, "GHOST headless: EGL surfaceless platform unavailable (needs Mesa)\n");
			m_display = nullptr;
			return GHOST_kFailure;
		}
		if (!m_egl.bindAPI(OPENGL_API)) {
			fprintf(stderr, "GHOST headless: EGL has no desktop OpenGL API\n");
			return GHOST_kFailure;
		}
		const Int configAttribs[] = {SURFACE_TYPE, PBUFFER_BIT, RENDERABLE_TYPE, OPENGL_BIT, NONE};
		Config config = nullptr;
		Int numConfigs = 0;
		m_egl.chooseConfig(m_display, configAttribs, &config, 1, &numConfigs);
		const Int contextAttribs[] = {
			CONTEXT_OPENGL_PROFILE_MASK, CONTEXT_OPENGL_COMPATIBILITY_PROFILE_BIT, NONE};
		/* EGL_KHR_no_config_context: Mesa accepts a null config when none matched. */
		m_context = m_egl.createContext(m_display, numConfigs ? config : nullptr, nullptr, contextAttribs);
		if (!m_context) {
			fprintf(stderr, "GHOST headless: eglCreateContext failed (0x%x)\n", (unsigned int)m_egl.getError());
			return GHOST_kFailure;
		}
		if (activateDrawingContext() != GHOST_kSuccess) {
			fprintf(stderr, "GHOST headless: eglMakeCurrent failed (0x%x)\n", (unsigned int)m_egl.getError());
			return GHOST_kFailure;
		}
		/* GLEW resolves through glXGetProcAddress; with libglvnd those entry points dispatch
		 * to whatever context is current, EGL included. */
		initContextGLEW();
		return GHOST_kSuccess;
	}

	GHOST_TSuccess releaseNativeHandles() { return GHOST_kSuccess; }

private:
	GHOST_HeadlessEGL::Api m_egl;
	GHOST_HeadlessEGL::Display m_display = nullptr;
	GHOST_HeadlessEGL::Context m_context = nullptr;
};

class GHOST_WindowHeadless : public GHOST_WindowNULL {
public:
	GHOST_WindowHeadless(GHOST_SystemNULL *system, const STR_String& title, GHOST_TUns32 width, GHOST_TUns32 height,
	                     GHOST_TDrawingContextType type)
		:GHOST_WindowNULL(system, title, 0, 0, width, height, GHOST_kWindowStateNormal, 0, type, false, 1),
		m_width(width),
		m_height(height)
	{
		setDrawingContextType(type);
	}

	bool getValid() const { return const_cast<GHOST_WindowHeadless *>(this)->getDrawingContextType() == GHOST_kDrawingContextTypeOpenGL; }
	void getClientBounds(GHOST_Rect& bounds) const { bounds.set(0, 0, m_width, m_height); }
	GHOST_TSuccess swapBuffers() { return GHOST_Window::swapBuffers(); }
	GHOST_TSuccess activateDrawingContext() { return GHOST_Window::activateDrawingContext(); }

private:
	GHOST_TUns32 m_width;
	GHOST_TUns32 m_height;

	GHOST_Context *newDrawingContext(GHOST_TDrawingContextType type)
	{
		if (type != GHOST_kDrawingContextTypeOpenGL) {
			return nullptr;
		}
		GHOST_Context *context = new GHOST_ContextHeadless();
		if (context->initializeDrawingContext() == GHOST_kSuccess) {
			return context;
		}
		delete context;
		return nullptr;
	}
};

class GHOST_SystemHeadless : public GHOST_SystemNULL {
public:
	GHOST_TUns64 getMilliSeconds() const
	{
		using namespace std::chrono;
		return duration_cast<milliseconds>(steady_clock::now().time_since_epoch()).count();
	}

	GHOST_IWindow *createWindow(const STR_String& title, GHOST_TInt32, GHOST_TInt32, GHOST_TUns32 width,
	                            GHOST_TUns32 height, GHOST_TWindowState, GHOST_TDrawingContextType type,
	                            GHOST_GLSettings, bool, const GHOST_TEmbedderWindowID)
	{
		GHOST_WindowHeadless *window = new GHOST_WindowHeadless(this, title, width, height, type);
		if (!window->getValid()) {
			delete window;
			return nullptr;
		}
		m_windowManager->addWindow(window);
		m_windowManager->setActiveWindow(window);
		return window;
	}
};

#endif  /* __GHOST_SYSTEMHEADLESS_H__ */
