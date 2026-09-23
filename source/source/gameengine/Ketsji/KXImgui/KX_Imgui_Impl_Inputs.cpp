// dear imgui: Platform Backend for Range Engine
#include <iostream>

#include "imgui.h"
#include "KX_Imgui_Impl_Inputs.h"

// RangeEngine Implementation
#include "SCA_IInputDevice.h"

#include "KX_Globals.h"
#include "KX_KetsjiEngine.h"

// SDL
#include <SDL.h>
#include <SDL_syswm.h>
#if defined(__APPLE__)
#include <TargetConditionals.h>
#endif

#if SDL_VERSION_ATLEAST(2,0,4) && !defined(__EMSCRIPTEN__) && !defined(__ANDROID__) && !(defined(__APPLE__) && TARGET_OS_IOS) && !defined(__amigaos4__)
#define SDL_HAS_CAPTURE_AND_GLOBAL_MOUSE    1
#else
#define SDL_HAS_CAPTURE_AND_GLOBAL_MOUSE    0
#endif
#define SDL_HAS_VULKAN                      SDL_VERSION_ATLEAST(2,0,6)

// SDL Data
struct ImGui_ImplSDL2_Data
{
    SDL_Window*     Window;
    SDL_Renderer*   Renderer;
    Uint64          Time;
    SCA_IInputDevice* m_inputDevice;
    int             MouseButtonsDown;
    SDL_Cursor*     MouseCursors[ImGuiMouseCursor_COUNT];
    int             PendingMouseLeaveFrame;
    char*           ClipboardTextData;
    bool            MouseCanUseGlobalState;
    SDL_GameController* GameController;

    ImGui_ImplSDL2_Data()   { memset((void*)this, 0, sizeof(*this)); }
};

// Backend data stored in io.BackendPlatformUserData to allow support for multiple Dear ImGui contexts
// It is STRONGLY preferred that you use docking branch with multi-viewports (== single Dear ImGui context + multiple windows) instead of multiple Dear ImGui contexts.
// FIXME: multi-context support is not well tested and probably dysfunctional in this backend.
// FIXME: some shared resources (mouse cursor shape, gamepad) are mishandled when using multi-context.
static ImGui_ImplSDL2_Data* ImGui_ImplSDL2_GetBackendData()
{
    return ImGui::GetCurrentContext() ? (ImGui_ImplSDL2_Data*)ImGui::GetIO().BackendPlatformUserData : nullptr;
}

// Functions
static const char* ImGui_ImplSDL2_GetClipboardText(void*)
{
    ImGui_ImplSDL2_Data* bd = ImGui_ImplSDL2_GetBackendData();
    if (bd->ClipboardTextData)
        SDL_free(bd->ClipboardTextData);
    bd->ClipboardTextData = SDL_GetClipboardText();
    return bd->ClipboardTextData;
}

static void ImGui_ImplSDL2_SetClipboardText(void*, const char* text)
{
    SDL_SetClipboardText(text);
}

static ImGuiKey ImGui_Impl_KeycodeToImGuiKey(SCA_IInputDevice::SCA_EnumInputs keycode)
{
    switch (keycode)
    {
        case SCA_IInputDevice::NOKEY: return ImGuiKey_None;
        case SCA_IInputDevice::WINCLOSE: return ImGuiKey_None;
        case SCA_IInputDevice::WINQUIT: return ImGuiKey_None;
        case SCA_IInputDevice::TABKEY: return ImGuiKey_Tab;
        case SCA_IInputDevice::LEFTARROWKEY: return ImGuiKey_LeftArrow;
        case SCA_IInputDevice::RIGHTARROWKEY: return ImGuiKey_RightArrow;
        case SCA_IInputDevice::UPARROWKEY: return ImGuiKey_UpArrow;
        case SCA_IInputDevice::DOWNARROWKEY: return ImGuiKey_DownArrow;
        case SCA_IInputDevice::PAGEUPKEY: return ImGuiKey_PageUp;
        case SCA_IInputDevice::PAGEDOWNKEY: return ImGuiKey_PageDown;
        case SCA_IInputDevice::HOMEKEY: return ImGuiKey_Home;
        case SCA_IInputDevice::ENDKEY: return ImGuiKey_End;
        case SCA_IInputDevice::INSERTKEY: return ImGuiKey_Insert;
        case SCA_IInputDevice::DELKEY: return ImGuiKey_Delete;
        case SCA_IInputDevice::BACKSPACEKEY: return ImGuiKey_Backspace;
        case SCA_IInputDevice::SPACEKEY: return ImGuiKey_Space;
        case SCA_IInputDevice::RETKEY: return ImGuiKey_Enter;
        case SCA_IInputDevice::ESCKEY: return ImGuiKey_Escape;
        case SCA_IInputDevice::QUOTEKEY: return ImGuiKey_Apostrophe;
        case SCA_IInputDevice::COMMAKEY: return ImGuiKey_Comma;
        case SCA_IInputDevice::MINUSKEY: return ImGuiKey_Minus;
        case SCA_IInputDevice::PERIODKEY: return ImGuiKey_Period;
        case SCA_IInputDevice::SLASHKEY: return ImGuiKey_Slash;
        case SCA_IInputDevice::SEMICOLONKEY: return ImGuiKey_Semicolon;
        case SCA_IInputDevice::EQUALKEY: return ImGuiKey_Equal;
        case SCA_IInputDevice::LEFTBRACKETKEY: return ImGuiKey_LeftBracket;
        case SCA_IInputDevice::BACKSLASHKEY: return ImGuiKey_Backslash;
        case SCA_IInputDevice::RIGHTBRACKETKEY: return ImGuiKey_RightBracket;
        case SCA_IInputDevice::ACCENTGRAVEKEY: return ImGuiKey_GraveAccent;
        case SCA_IInputDevice::CAPSLOCKKEY: return ImGuiKey_CapsLock;
        case SCA_IInputDevice::PAUSEKEY: return ImGuiKey_Pause;
        case SCA_IInputDevice::PAD0: return ImGuiKey_Keypad0;
        case SCA_IInputDevice::PAD1: return ImGuiKey_Keypad1;
        case SCA_IInputDevice::PAD2: return ImGuiKey_Keypad2;
        case SCA_IInputDevice::PAD3: return ImGuiKey_Keypad3;
        case SCA_IInputDevice::PAD4: return ImGuiKey_Keypad4;
        case SCA_IInputDevice::PAD5: return ImGuiKey_Keypad5;
        case SCA_IInputDevice::PAD6: return ImGuiKey_Keypad6;
        case SCA_IInputDevice::PAD7: return ImGuiKey_Keypad7;
        case SCA_IInputDevice::PAD8: return ImGuiKey_Keypad8;
        case SCA_IInputDevice::PAD9: return ImGuiKey_Keypad9;
        case SCA_IInputDevice::PADPERIOD: return ImGuiKey_KeypadDecimal;
        case SCA_IInputDevice::LINEFEEDKEY: return ImGuiKey_KeypadDivide;
        case SCA_IInputDevice::PADASTERKEY: return ImGuiKey_KeypadMultiply;
        case SCA_IInputDevice::PADMINUS: return ImGuiKey_KeypadSubtract;
        case SCA_IInputDevice::PADPLUSKEY: return ImGuiKey_KeypadAdd;
        case SCA_IInputDevice::PADENTER: return ImGuiKey_KeypadEnter;
        case SCA_IInputDevice::LEFTCTRLKEY: return ImGuiKey_LeftCtrl;
        case SCA_IInputDevice::LEFTSHIFTKEY: return ImGuiKey_LeftShift;
        case SCA_IInputDevice::LEFTALTKEY: return ImGuiKey_LeftAlt;
        case SCA_IInputDevice::RIGHTCTRLKEY: return ImGuiKey_RightCtrl;
        case SCA_IInputDevice::RIGHTSHIFTKEY: return ImGuiKey_RightShift;
        case SCA_IInputDevice::RIGHTALTKEY: return ImGuiKey_RightAlt;
        case SCA_IInputDevice::OSKEY: return ImGuiKey_Menu;
        case SCA_IInputDevice::ZEROKEY: return ImGuiKey_0;
        case SCA_IInputDevice::ONEKEY: return ImGuiKey_1;
        case SCA_IInputDevice::TWOKEY: return ImGuiKey_2;
        case SCA_IInputDevice::THREEKEY: return ImGuiKey_3;
        case SCA_IInputDevice::FOURKEY: return ImGuiKey_4;
        case SCA_IInputDevice::FIVEKEY: return ImGuiKey_5;
        case SCA_IInputDevice::SIXKEY: return ImGuiKey_6;
        case SCA_IInputDevice::SEVENKEY: return ImGuiKey_7;
        case SCA_IInputDevice::EIGHTKEY: return ImGuiKey_8;
        case SCA_IInputDevice::NINEKEY: return ImGuiKey_9;
        case SCA_IInputDevice::AKEY: return ImGuiKey_A;
        case SCA_IInputDevice::BKEY: return ImGuiKey_B;
        case SCA_IInputDevice::CKEY: return ImGuiKey_C;
        case SCA_IInputDevice::DKEY: return ImGuiKey_D;
        case SCA_IInputDevice::EKEY: return ImGuiKey_E;
        case SCA_IInputDevice::FKEY: return ImGuiKey_F;
        case SCA_IInputDevice::GKEY: return ImGuiKey_G;
        case SCA_IInputDevice::HKEY_: return ImGuiKey_H;
        case SCA_IInputDevice::IKEY: return ImGuiKey_I;
        case SCA_IInputDevice::JKEY: return ImGuiKey_J;
        case SCA_IInputDevice::KKEY: return ImGuiKey_K;
        case SCA_IInputDevice::LKEY: return ImGuiKey_L;
        case SCA_IInputDevice::MKEY: return ImGuiKey_M;
        case SCA_IInputDevice::NKEY: return ImGuiKey_N;
        case SCA_IInputDevice::OKEY: return ImGuiKey_O;
        case SCA_IInputDevice::PKEY: return ImGuiKey_P;
        case SCA_IInputDevice::QKEY: return ImGuiKey_Q;
        case SCA_IInputDevice::RKEY: return ImGuiKey_R;
        case SCA_IInputDevice::SKEY: return ImGuiKey_S;
        case SCA_IInputDevice::TKEY: return ImGuiKey_T;
        case SCA_IInputDevice::UKEY: return ImGuiKey_U;
        case SCA_IInputDevice::VKEY: return ImGuiKey_V;
        case SCA_IInputDevice::WKEY: return ImGuiKey_W;
        case SCA_IInputDevice::XKEY: return ImGuiKey_X;
        case SCA_IInputDevice::YKEY: return ImGuiKey_Y;
        case SCA_IInputDevice::ZKEY: return ImGuiKey_Z;
        case SCA_IInputDevice::F1KEY: return ImGuiKey_F1;
        case SCA_IInputDevice::F2KEY: return ImGuiKey_F2;
        case SCA_IInputDevice::F3KEY: return ImGuiKey_F3;
        case SCA_IInputDevice::F4KEY: return ImGuiKey_F4;
        case SCA_IInputDevice::F5KEY: return ImGuiKey_F5;
        case SCA_IInputDevice::F6KEY: return ImGuiKey_F6;
        case SCA_IInputDevice::F7KEY: return ImGuiKey_F7;
        case SCA_IInputDevice::F8KEY: return ImGuiKey_F8;
        case SCA_IInputDevice::F9KEY: return ImGuiKey_F9;
        case SCA_IInputDevice::F10KEY: return ImGuiKey_F10;
        case SCA_IInputDevice::F11KEY: return ImGuiKey_F11;
        case SCA_IInputDevice::F12KEY: return ImGuiKey_F12;
        case SCA_IInputDevice::F13KEY: return ImGuiKey_None;
        case SCA_IInputDevice::PADSLASHKEY: return ImGuiKey_None;
        case SCA_IInputDevice::F14KEY: return ImGuiKey_None;
        case SCA_IInputDevice::F15KEY: return ImGuiKey_None;
        case SCA_IInputDevice::F16KEY: return ImGuiKey_None;
        case SCA_IInputDevice::F17KEY: return ImGuiKey_None;
        case SCA_IInputDevice::F18KEY: return ImGuiKey_None;
        case SCA_IInputDevice::F19KEY: return ImGuiKey_None;
        case SCA_IInputDevice::MOUSEX: return ImGuiKey_None;
        case SCA_IInputDevice::MOUSEY: return ImGuiKey_None;
        case SCA_IInputDevice::ENDWIN: return ImGuiKey_None;
        case SCA_IInputDevice::ENDMOUSE: return ImGuiKey_None;
        case SCA_IInputDevice::ENDMOUSEBUTTONS: return ImGuiKey_None;
        case SCA_IInputDevice::MAX_KEYS: return ImGuiKey_None;
        case SCA_IInputDevice::WHEELUPMOUSE: return ImGuiKey_None;
        case SCA_IInputDevice::WHEELDOWNMOUSE: return ImGuiKey_None;
        case SCA_IInputDevice::BEGINWIN: return ImGuiKey_None;
        case SCA_IInputDevice::WINRESIZE: return ImGuiKey_None;
        case SCA_IInputDevice::LEFTTHUMBMOUSE: return ImGuiKey_None;
        case SCA_IInputDevice::RIGHTTHUMBMOUSE: return ImGuiKey_None;
        case SCA_IInputDevice::LEFTMOUSE: return ImGuiKey_None;
        case SCA_IInputDevice::MIDDLEMOUSE: return ImGuiKey_None;
        case SCA_IInputDevice::RIGHTMOUSE: return ImGuiKey_None;
        case SCA_IInputDevice::BUTTON6MOUSE: return ImGuiKey_None;
        case SCA_IInputDevice::BUTTON7MOUSE: return ImGuiKey_None;
        case SCA_IInputDevice::BEGINMOUSE: return ImGuiKey_None;
        case SCA_IInputDevice::BEGINMOUSEBUTTONS: return ImGuiKey_None;
        case SCA_IInputDevice::BEGINKEY: return ImGuiKey_None;
    }
    return ImGuiKey_None;
}

static void ImGui_Impl_UpdateKeyModifiers()
{
    ImGuiIO& io = ImGui::GetIO();
    ImGui_ImplSDL2_Data* bd = ImGui_ImplSDL2_GetBackendData();

    bool ctrl = bd->m_inputDevice->GetInput(SCA_IInputDevice::LEFTCTRLKEY).Find(SCA_InputEvent::ACTIVE);
    bool shift = bd->m_inputDevice->GetInput(SCA_IInputDevice::LEFTSHIFTKEY).Find(SCA_InputEvent::ACTIVE);
    io.AddKeyEvent(ImGuiMod_Ctrl, ctrl);
    io.AddKeyEvent(ImGuiMod_Shift, shift);
    //io.AddKeyEvent(ImGuiMod_Alt, (sdl_key_mods & KMOD_ALT) != 0);
    //io.AddKeyEvent(ImGuiMod_Super, (sdl_key_mods & KMOD_GUI) != 0);
}

// You can read the io.WantCaptureMouse, io.WantCaptureKeyboard flags to tell if dear imgui wants to use your inputs.
// - When io.WantCaptureMouse is true, do not dispatch mouse input data to your main application, or clear/overwrite your copy of the mouse data.
// - When io.WantCaptureKeyboard is true, do not dispatch keyboard input data to your main application, or clear/overwrite your copy of the keyboard data.
// Generally you may always pass all inputs to dear imgui, and hide them from your application based on those two flags.
// If you have multiple SDL events and some of them are not meant to be used by dear imgui, you may need to filter events based on their windowID field.
void KX_ImGui_Impl_Inputs_ProcessEvent()
{
    ImGuiIO& io = ImGui::GetIO();
    ImGui_ImplSDL2_Data* bd = ImGui_ImplSDL2_GetBackendData();

    /* Mouse Left */
    bool mouseLeftActive = bd->m_inputDevice->GetInput(SCA_IInputDevice::LEFTMOUSE).Find(SCA_InputEvent::ACTIVE);
    bool mouseLeftPressed = bd->m_inputDevice->GetInput(SCA_IInputDevice::LEFTMOUSE).Find(SCA_InputEvent::NONE);
    // std::cout << mouseLeftPressed;
    if (mouseLeftActive || mouseLeftPressed) {
        io.AddMouseButtonEvent(0, mouseLeftActive);
    }

    /* Mouse Right */
    bool mouseRightActive = bd->m_inputDevice->GetInput(SCA_IInputDevice::RIGHTMOUSE).Find(SCA_InputEvent::ACTIVE);
    bool mouseRightPressed = bd->m_inputDevice->GetInput(SCA_IInputDevice::RIGHTMOUSE).Find(SCA_InputEvent::NONE);
    if (mouseRightActive || mouseRightPressed) {
        io.AddMouseButtonEvent(1, mouseRightActive);
    }

    /* Mouse Wheel */
    int mouseWheelUp = bd->m_inputDevice->GetInput(SCA_IInputDevice::WHEELUPMOUSE).Find(SCA_InputEvent::ACTIVE);
    int mouseWheelDown = bd->m_inputDevice->GetInput(SCA_IInputDevice::WHEELDOWNMOUSE).Find(SCA_InputEvent::ACTIVE);
    //std::cout << mouseWheelUp;
    if (mouseWheelUp || mouseWheelDown) {
        io.AddMouseWheelEvent(0, mouseWheelUp - mouseWheelDown);
    }

    // Keyboard inputs
    for (int i = SCA_IInputDevice::BEGINKEY; i <= SCA_IInputDevice::ENDKEY; i++) {
        SCA_InputEvent& input = bd->m_inputDevice->GetInput((SCA_IInputDevice::SCA_EnumInputs)i);

        ImGuiKey key = ImGui_Impl_KeycodeToImGuiKey((SCA_IInputDevice::SCA_EnumInputs)i);
        io.AddKeyEvent(key, input.Find(SCA_InputEvent::ACTIVE));
        
        if (io.WantTextInput && input.Find(SCA_InputEvent::JUSTACTIVATED)) {
            bool shift = bd->m_inputDevice->GetInput(SCA_IInputDevice::LEFTSHIFTKEY).Find(SCA_InputEvent::ACTIVE);


            const char k[4] = { 
                SCA_IInputDevice::ConvertKeyToChar((SCA_IInputDevice::SCA_EnumInputs)i, shift)
            };
            io.AddInputCharactersUTF8(k);
        }
    }
    // UpdateKeyModifiers
    ImGui_Impl_UpdateKeyModifiers();
}

static bool KX_ImGui_Impl_Inputs_Init(SCA_IInputDevice* m_inputDevice, SDL_Renderer* renderer)
{
    ImGuiIO& io = ImGui::GetIO();
    IM_ASSERT(io.BackendPlatformUserData == nullptr && "Already initialized a platform backend!");

    // Check and store if we are on a SDL backend that supports global mouse position
    // ("wayland" and "rpi" don't support it, but we chose to use a white-list instead of a black-list)
    bool mouse_can_use_global_state = true;
#if SDL_HAS_CAPTURE_AND_GLOBAL_MOUSE // not needed RangeEngine
    /*const char* sdl_backend = SDL_GetCurrentVideoDriver();
    const char* global_mouse_whitelist[] = { "windows", "cocoa", "x11", "DIVE", "VMAN" };
    for (int n = 0; n < IM_ARRAYSIZE(global_mouse_whitelist); n++)
        if (strncmp(sdl_backend, global_mouse_whitelist[n], strlen(global_mouse_whitelist[n])) == 0)
            mouse_can_use_global_state = true;*/
#endif

    // Setup backend capabilities flags
    ImGui_ImplSDL2_Data* bd = IM_NEW(ImGui_ImplSDL2_Data)();
    io.BackendPlatformUserData = (void*)bd;
    io.BackendPlatformName = "imgui_impl_sdl";
    io.BackendFlags |= ImGuiBackendFlags_HasMouseCursors;       // We can honor GetMouseCursor() values (optional)
    io.BackendFlags |= ImGuiBackendFlags_HasSetMousePos;        // We can honor io.WantSetMousePos requests (optional, rarely used)

    //bd->Window = window;
    bd->Renderer = renderer;
    bd->MouseCanUseGlobalState = mouse_can_use_global_state;

    // Range Engine SCA_IInputDevice
    bd->m_inputDevice = m_inputDevice;

    io.SetClipboardTextFn = ImGui_ImplSDL2_SetClipboardText;
    io.GetClipboardTextFn = ImGui_ImplSDL2_GetClipboardText;
    io.ClipboardUserData = nullptr;

    // Load mouse cursors
    bd->MouseCursors[ImGuiMouseCursor_Arrow] = SDL_CreateSystemCursor(SDL_SYSTEM_CURSOR_ARROW);
    bd->MouseCursors[ImGuiMouseCursor_TextInput] = SDL_CreateSystemCursor(SDL_SYSTEM_CURSOR_IBEAM);
    bd->MouseCursors[ImGuiMouseCursor_ResizeAll] = SDL_CreateSystemCursor(SDL_SYSTEM_CURSOR_SIZEALL);
    bd->MouseCursors[ImGuiMouseCursor_ResizeNS] = SDL_CreateSystemCursor(SDL_SYSTEM_CURSOR_SIZENS);
    bd->MouseCursors[ImGuiMouseCursor_ResizeEW] = SDL_CreateSystemCursor(SDL_SYSTEM_CURSOR_SIZEWE);
    bd->MouseCursors[ImGuiMouseCursor_ResizeNESW] = SDL_CreateSystemCursor(SDL_SYSTEM_CURSOR_SIZENESW);
    bd->MouseCursors[ImGuiMouseCursor_ResizeNWSE] = SDL_CreateSystemCursor(SDL_SYSTEM_CURSOR_SIZENWSE);
    bd->MouseCursors[ImGuiMouseCursor_Hand] = SDL_CreateSystemCursor(SDL_SYSTEM_CURSOR_HAND);
    bd->MouseCursors[ImGuiMouseCursor_NotAllowed] = SDL_CreateSystemCursor(SDL_SYSTEM_CURSOR_NO);

    // Set platform dependent data in viewport
#ifdef _WIN32
    /*SDL_SysWMinfo info; // not needed RangeEngine
    SDL_VERSION(&info.version);
    if (SDL_GetWindowWMInfo(window, &info)) // Not necessary, RangeEngine
        ImGui::GetMainViewport()->PlatformHandleRaw = (void*)info.info.win.window;*/
#else
    //(void)window;
#endif

    // From 2.0.5: Set SDL hint to receive mouse click events on window focus, otherwise SDL doesn't emit the event.
    // Without this, when clicking to gain focus, our widgets wouldn't activate even though they showed as hovered.
    // (This is unfortunately a global SDL setting, so enabling it might have a side-effect on your application.
    // It is unlikely to make a difference, but if your app absolutely needs to ignore the initial on-focus click:
    // you can ignore SDL_MOUSEBUTTONDOWN events coming right after a SDL_WINDOWEVENT_FOCUS_GAINED)
#ifdef SDL_HINT_MOUSE_FOCUS_CLICKTHROUGH
    SDL_SetHint(SDL_HINT_MOUSE_FOCUS_CLICKTHROUGH, "1");
#endif

    // From 2.0.22: Disable auto-capture, this is preventing drag and drop across multiple windows (see #5710)
#ifdef SDL_HINT_MOUSE_AUTO_CAPTURE
    SDL_SetHint(SDL_HINT_MOUSE_AUTO_CAPTURE, "0");
#endif

    return true;
}

bool KX_ImGui_Impl_Inputs_InitForOpenGL(SCA_IInputDevice *m_inputDevice, void *sdl_gl_context)
{
    IM_UNUSED(sdl_gl_context); // Viewport branch will need this.
    return KX_ImGui_Impl_Inputs_Init(m_inputDevice, nullptr);
}

void KX_ImGui_Impl_Inputs_Shutdown()
{
    ImGui_ImplSDL2_Data* bd = ImGui_ImplSDL2_GetBackendData();
    IM_ASSERT(bd != nullptr && "No platform backend to shutdown, or already shutdown?");
    /* In Release builds IM_ASSERT is a no-op, so without this early-out a null
     * bd (backend already shut down, or the current ImGui context isn't the one
     * that ran Init) falls through to bd->ClipboardTextData below and crashes.
     * This is what was closing the whole editor on ESC after "P". */
    if (bd == nullptr)
        return;
    ImGuiIO& io = ImGui::GetIO();

    if (bd->ClipboardTextData)
        SDL_free(bd->ClipboardTextData);
    for (ImGuiMouseCursor cursor_n = 0; cursor_n < ImGuiMouseCursor_COUNT; cursor_n++)
        SDL_FreeCursor(bd->MouseCursors[cursor_n]);
    if (bd->GameController)
        SDL_GameControllerClose(bd->GameController);

    io.BackendPlatformName = nullptr;
    io.BackendPlatformUserData = nullptr;
    IM_DELETE(bd);
}

static void ImGui_ImplSDL2_UpdateMouseData()
{
    ImGui_ImplSDL2_Data* bd = ImGui_ImplSDL2_GetBackendData();
    ImGuiIO& io = ImGui::GetIO();

    // We forward mouse input when hovered or captured (via SDL_MOUSEMOTION) or when focused (below)
#if SDL_HAS_CAPTURE_AND_GLOBAL_MOUSE
    // SDL_CaptureMouse() let the OS know e.g. that our imgui drag outside the SDL window boundaries shouldn't e.g. trigger other operations outside
    //SDL_CaptureMouse((bd->MouseButtonsDown != 0 && ImGui::GetDragDropPayload() == nullptr) ? SDL_TRUE : SDL_FALSE);
    //SDL_Window* focused_window = SDL_GetKeyboardFocus();
    //const bool is_app_focused = (bd->Window == focused_window);
    const bool is_app_focused = true;
#else
    const bool is_app_focused = (SDL_GetWindowFlags(bd->Window) & SDL_WINDOW_INPUT_FOCUS) != 0; // SDL 2.0.3 and non-windowed systems: single-viewport only
#endif
    if (is_app_focused)
    {
        // (Optional) Set OS mouse position from Dear ImGui if requested (rarely used, only when ImGuiConfigFlags_NavEnableSetMousePos is enabled by user)
        if (io.WantSetMousePos)
            SDL_WarpMouseInWindow(bd->Window, (int)io.MousePos.x, (int)io.MousePos.y);

        // (Optional) Fallback to provide mouse position when focused (SDL_MOUSEMOTION already provides this when hovered or captured)
        if (bd->MouseCanUseGlobalState && bd->MouseButtonsDown == 0)
        {
            // Update Mouse Position
            const int mousex = bd->m_inputDevice->GetInput(SCA_IInputDevice::MOUSEX).m_values[0];
            const int mousey = bd->m_inputDevice->GetInput(SCA_IInputDevice::MOUSEY).m_values[0];

            io.AddMousePosEvent((float)(mousex), (float)(mousey));
        }
    }
}

/* Gamepad menu navigation. Digital buttons (face/shoulder/dpad/stick-click) and analog
 * sticks/triggers are read straight from SDL_GameController here -- deliberately NOT going
 * through Range Engine's own DEV_Joystick (used by game-logic joystick sensors), because that
 * class's axis cache (m_axis_array, fed by OnAxisEvent/HandleEvents) is never actually
 * populated anywhere in DEV_Joystick.cpp; going through it would silently give menu
 * navigation a dead analog stick. Opening a second SDL_GameController handle to the same
 * physical device index is safe -- SDL keeps them in sync -- and keeps this backend
 * self-contained, matching how it already talks to SDL directly for mouse cursors/clipboard
 * above. Standard mapping, ported from Dear ImGui's own imgui_impl_sdl2.cpp backend. */
static void ImGui_ImplSDL2_UpdateGamepads()
{
    ImGuiIO& io = ImGui::GetIO();
    ImGui_ImplSDL2_Data* bd = ImGui_ImplSDL2_GetBackendData();

    if (!(io.ConfigFlags & ImGuiConfigFlags_NavEnableGamepad)) {
        return;
    }

    // (Re)acquire the first available game controller if we don't have one, or it disconnected.
    if (bd->GameController == nullptr || !SDL_GameControllerGetAttached(bd->GameController)) {
        if (bd->GameController) {
            SDL_GameControllerClose(bd->GameController);
            bd->GameController = nullptr;
        }
        for (int i = 0; i < SDL_NumJoysticks(); i++) {
            if (SDL_IsGameController(i)) {
                bd->GameController = SDL_GameControllerOpen(i);
                break;
            }
        }
    }

    io.BackendFlags &= ~ImGuiBackendFlags_HasGamepad;
    if (!bd->GameController) {
        return;
    }
    io.BackendFlags |= ImGuiBackendFlags_HasGamepad;

#define IM_SAT(V) (V < 0.0f ? 0.0f : V > 1.0f ? 1.0f : V)
#define MAP_BUTTON(KEY_NO, BUTTON_NO) \
    { io.AddKeyEvent(KEY_NO, SDL_GameControllerGetButton(bd->GameController, BUTTON_NO) != 0); }
#define MAP_ANALOG(KEY_NO, AXIS_NO, V0, V1) \
    { \
        float vn = (float)(SDL_GameControllerGetAxis(bd->GameController, AXIS_NO) - V0) / (float)(V1 - V0); \
        vn = IM_SAT(vn); \
        io.AddKeyAnalogEvent(KEY_NO, vn > 0.1f, vn); \
    }
    const int thumb_dead_zone = 8000;  // suggested by SDL_gamecontroller.h
    MAP_BUTTON(ImGuiKey_GamepadStart, SDL_CONTROLLER_BUTTON_START);
    MAP_BUTTON(ImGuiKey_GamepadBack, SDL_CONTROLLER_BUTTON_BACK);
    MAP_BUTTON(ImGuiKey_GamepadFaceDown, SDL_CONTROLLER_BUTTON_A);
    MAP_BUTTON(ImGuiKey_GamepadFaceRight, SDL_CONTROLLER_BUTTON_B);
    MAP_BUTTON(ImGuiKey_GamepadFaceLeft, SDL_CONTROLLER_BUTTON_X);
    MAP_BUTTON(ImGuiKey_GamepadFaceUp, SDL_CONTROLLER_BUTTON_Y);
    MAP_BUTTON(ImGuiKey_GamepadDpadLeft, SDL_CONTROLLER_BUTTON_DPAD_LEFT);
    MAP_BUTTON(ImGuiKey_GamepadDpadRight, SDL_CONTROLLER_BUTTON_DPAD_RIGHT);
    MAP_BUTTON(ImGuiKey_GamepadDpadUp, SDL_CONTROLLER_BUTTON_DPAD_UP);
    MAP_BUTTON(ImGuiKey_GamepadDpadDown, SDL_CONTROLLER_BUTTON_DPAD_DOWN);
    MAP_BUTTON(ImGuiKey_GamepadL1, SDL_CONTROLLER_BUTTON_LEFTSHOULDER);
    MAP_BUTTON(ImGuiKey_GamepadR1, SDL_CONTROLLER_BUTTON_RIGHTSHOULDER);
    MAP_ANALOG(ImGuiKey_GamepadL2, SDL_CONTROLLER_AXIS_TRIGGERLEFT, 0.0f, 32767);
    MAP_ANALOG(ImGuiKey_GamepadR2, SDL_CONTROLLER_AXIS_TRIGGERRIGHT, 0.0f, 32767);
    MAP_BUTTON(ImGuiKey_GamepadL3, SDL_CONTROLLER_BUTTON_LEFTSTICK);
    MAP_BUTTON(ImGuiKey_GamepadR3, SDL_CONTROLLER_BUTTON_RIGHTSTICK);
    MAP_ANALOG(ImGuiKey_GamepadLStickLeft, SDL_CONTROLLER_AXIS_LEFTX, -thumb_dead_zone, -32768);
    MAP_ANALOG(ImGuiKey_GamepadLStickRight, SDL_CONTROLLER_AXIS_LEFTX, thumb_dead_zone, 32767);
    MAP_ANALOG(ImGuiKey_GamepadLStickUp, SDL_CONTROLLER_AXIS_LEFTY, -thumb_dead_zone, -32768);
    MAP_ANALOG(ImGuiKey_GamepadLStickDown, SDL_CONTROLLER_AXIS_LEFTY, thumb_dead_zone, 32767);
    MAP_ANALOG(ImGuiKey_GamepadRStickLeft, SDL_CONTROLLER_AXIS_RIGHTX, -thumb_dead_zone, -32768);
    MAP_ANALOG(ImGuiKey_GamepadRStickRight, SDL_CONTROLLER_AXIS_RIGHTX, thumb_dead_zone, 32767);
    MAP_ANALOG(ImGuiKey_GamepadRStickUp, SDL_CONTROLLER_AXIS_RIGHTY, -thumb_dead_zone, -32768);
    MAP_ANALOG(ImGuiKey_GamepadRStickDown, SDL_CONTROLLER_AXIS_RIGHTY, thumb_dead_zone, 32767);
#undef MAP_BUTTON
#undef MAP_ANALOG
}

static void ImGui_ImplSDL2_UpdateMouseCursor()
{
    ImGuiIO& io = ImGui::GetIO();
    if (io.ConfigFlags & ImGuiConfigFlags_NoMouseCursorChange)
        return;
    ImGui_ImplSDL2_Data* bd = ImGui_ImplSDL2_GetBackendData();

    ImGuiMouseCursor imgui_cursor = ImGui::GetMouseCursor();
    if (io.MouseDrawCursor || imgui_cursor == ImGuiMouseCursor_None)
    {
        // Hide OS mouse cursor if imgui is drawing it or if it wants no cursor
        SDL_ShowCursor(SDL_FALSE);
    }
    else
    {
        // Show OS mouse cursor
        SDL_SetCursor(bd->MouseCursors[imgui_cursor] ? bd->MouseCursors[imgui_cursor] : bd->MouseCursors[ImGuiMouseCursor_Arrow]);
        SDL_ShowCursor(SDL_TRUE);
    }
}

void KX_ImGui_Impl_Inputs_NewFrame()
{
    ImGui_ImplSDL2_Data* bd = ImGui_ImplSDL2_GetBackendData();
    IM_ASSERT(bd != nullptr && "Did you call ImGui_ImplSDL2_Init()?");
    ImGuiIO& io = ImGui::GetIO();
    
    // Setup display size (every frame to accommodate for window resizing) // not needed RangeEngine
    /*int w, h;
    int display_w, display_h;
    SDL_GetWindowSize(bd->Window, &w, &h);
    if (SDL_GetWindowFlags(bd->Window) & SDL_WINDOW_MINIMIZED)
        w = h = 0;
    if (bd->Renderer != nullptr)
        SDL_GetRendererOutputSize(bd->Renderer, &display_w, &display_h);
    else
        SDL_GL_GetDrawableSize(bd->Window, &display_w, &display_h);
    io.DisplaySize = ImVec2((float)w, (float)h);
    if (w > 0 && h > 0)
        io.DisplayFramebufferScale = ImVec2((float)display_w / w, (float)display_h / h);*/

    // Setup time step (we don't use SDL_GetTicks() because it is using millisecond resolution)
    static Uint64 frequency = SDL_GetPerformanceFrequency();
    Uint64 current_time = SDL_GetPerformanceCounter();
    io.DeltaTime = bd->Time > 0 ? (float)((double)(current_time - bd->Time) / frequency) : (float)(1.0f / 60.0f);
    bd->Time = current_time;

    if (bd->PendingMouseLeaveFrame && bd->PendingMouseLeaveFrame >= ImGui::GetFrameCount() && bd->MouseButtonsDown == 0)
    {
        io.AddMousePosEvent(-FLT_MAX, -FLT_MAX);
        bd->PendingMouseLeaveFrame = 0;
    }

    ImGui_ImplSDL2_UpdateMouseData();
    ImGui_ImplSDL2_UpdateMouseCursor();

    // Update game controllers (if enabled and available)
    ImGui_ImplSDL2_UpdateGamepads();
}
