/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "NET_AnastacioPlugin.h"
#include <filesystem>
#ifdef _WIN32
# define WIN32_LEAN_AND_MEAN
# define NOMINMAX
# include <windows.h>
#else
# include <dlfcn.h>
#endif
namespace net {
AnastacioPlugin &anastacioSteamService()
{
    static AnastacioPlugin service;
    return service;
}
AnastacioPlugin::~AnastacioPlugin() { unload(); }
void AnastacioPlugin::unload()
{
    if (busy()) { m_error = "Disconnect Steam sessions before unloading the complement"; return; }
    if (m_context) {
        m_api->shutdown(m_context);
        m_api->destroy(m_context);
    }
    m_context = nullptr;
    m_api = nullptr;
    m_initialized = false;
    if (m_library) {
#ifdef _WIN32
        FreeLibrary(static_cast<HMODULE>(m_library));
#else
        dlclose(m_library);
#endif
        m_library = nullptr;
    }
}
bool AnastacioPlugin::load(const std::string &absolutePath)
{
    if (busy()) { m_error = "Steam transports still active"; return false; }
    unload();
    m_error.clear();
    std::error_code ec;
    auto path = std::filesystem::u8path(absolutePath);
    if (!path.is_absolute() || !std::filesystem::is_regular_file(path, ec)) {
        m_error = "Complement requires an existing absolute library path";
        return false;
    }
#ifdef _WIN32
    // DLL_LOAD_DIR dependency lookup requires native Windows separators.
    path.make_preferred();
    m_library = LoadLibraryExW(path.c_str(), nullptr,
        LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_SYSTEM32);
#else
    m_library = dlopen(path.c_str(), RTLD_NOW | RTLD_LOCAL);
#endif
    if (!m_library) {
        m_error = "Unable to load complement library";
#ifdef _WIN32
        m_error += " (Windows error " + std::to_string(GetLastError()) + ")";
#else
        const char *detail = dlerror();
        if (detail) m_error += std::string(": ") + detail;
#endif
        return false;
    }
#ifdef _WIN32
    auto getApi = reinterpret_cast<AnastacioPluginGetAPI>(
        GetProcAddress(static_cast<HMODULE>(m_library), "AnastacioSteam_GetApi"));
#else
    auto getApi = reinterpret_cast<AnastacioPluginGetAPI>(dlsym(m_library, "AnastacioSteam_GetApi"));
#endif
    const auto *api = getApi ? getApi(ANASTACIO_PLUGIN_ABI_VERSION) : nullptr;
    if (!api || api->size < sizeof(AnastacioPluginAPI) ||
        api->version != ANASTACIO_PLUGIN_ABI_VERSION || !api->create || !api->destroy ||
        !api->initialize || !api->shutdown || !api->state || !api->identity || !api->pump) {
        m_error = "Complement ABI incompatible or incomplete";
        unload();
        return false;
    }
    m_api = api;
    m_context = m_api->create();
    if (!m_context) {
        m_error = "Complement context creation failed";
        unload();
        return false;
    }
    return true;
}
bool AnastacioPlugin::initialize(uint32_t appId)
{
    m_error.clear();
    if (!m_context) { m_error = "Complement is not loaded"; return false; }
    if (m_initialized) { m_error = "Complement already initialized"; return false; }
    char error[512] = {};
    if (!m_api->initialize(m_context, appId, error, sizeof(error))) {
        error[sizeof(error) - 1] = '\0';
        m_error = error[0] ? error : "Complement initialization failed";
        m_api->shutdown(m_context);
        return false;
    }
    m_initialized = true;
    return true;
}
void AnastacioPlugin::pump() { if (m_initialized) m_api->pump(m_context); }
bool AnastacioPlugin::ready() const { return m_initialized && m_api->state(m_context) == 1; }
uint64_t AnastacioPlugin::identity() const { return ready() ? m_api->identity(m_context) : 0; }
}
