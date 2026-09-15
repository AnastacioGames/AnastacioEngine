// dear imgui: Platform Backend for Range Engine
#pragma once
#include "imgui.h"      // IMGUI_IMPL_API

// RangeEngine Implementation
#include "SCA_IInputDevice.h"

struct SDL_Window;
struct SDL_Renderer;
typedef union SDL_Event SDL_Event;

IMGUI_IMPL_API bool     KX_ImGui_Impl_Inputs_InitForOpenGL(SCA_IInputDevice* m_inputDevice, void* sdl_gl_context);

IMGUI_IMPL_API void     KX_ImGui_Impl_Inputs_Shutdown();
IMGUI_IMPL_API void     KX_ImGui_Impl_Inputs_NewFrame();
//IMGUI_IMPL_API bool     ImGui_ImplSDL2_ProcessEvent(const SDL_Event* event);
IMGUI_IMPL_API void     KX_ImGui_Impl_Inputs_ProcessEvent();

#ifndef IMGUI_DISABLE_OBSOLETE_FUNCTIONS
static inline void ImGui_ImplSDL2_NewFrame(SDL_Window*) { KX_ImGui_Impl_Inputs_NewFrame(); } // 1.84: removed unnecessary parameter
#endif
