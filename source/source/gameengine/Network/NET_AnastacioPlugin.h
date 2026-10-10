/* SPDX-License-Identifier: GPL-2.0-or-later */
#pragma once
#include "NET_AnastacioPluginABI.h"
#include <string>
namespace net {
/* RAII library owner. One instance per service, confined to its owner thread.
 * The process service is attached to the engine runtime. */
class AnastacioPlugin {
public:
    AnastacioPlugin() = default;
    ~AnastacioPlugin();
    AnastacioPlugin(const AnastacioPlugin &) = delete;
    AnastacioPlugin &operator=(const AnastacioPlugin &) = delete;
    bool load(const std::string &absolutePath);
    bool initialize(uint32_t appId);
    void pump();
    void unload();
    const AnastacioPluginAPI *api() const { return m_api; }
    void *context() const { return m_context; }
    void retainTransport() { ++m_transports; }
    void releaseTransport() { --m_transports; }
    bool busy() const { return m_transports != 0; }
    bool ready() const;
    uint64_t identity() const;
    bool loaded() const { return m_context != nullptr; }
    const std::string &error() const { return m_error; }
private:
    unsigned int m_transports = 0;
    void *m_library = nullptr;
    const AnastacioPluginAPI *m_api = nullptr;
    void *m_context = nullptr;
    bool m_initialized = false;
    std::string m_error;
};
// Process service; only the active engine thread may access it. Engine stop releases it.
AnastacioPlugin &anastacioSteamService();
}
