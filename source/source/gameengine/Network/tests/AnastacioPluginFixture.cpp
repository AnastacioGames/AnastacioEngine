/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "NET_AnastacioPluginABI.h"
#include <cstdio>
#include <cstdlib>
struct Context { bool initialized = false; uint64_t frames = 0; };
static void *ANASTACIO_PLUGIN_CALL create() { return new Context; }
static void ANASTACIO_PLUGIN_CALL destroy(void *p)
{
    // Fail the process if the loader frees a live service before shutdown.
    if (static_cast<Context *>(p)->initialized) std::abort();
    delete static_cast<Context *>(p);
}
static int32_t ANASTACIO_PLUGIN_CALL initialize(void *p, uint32_t id, char *error, uint32_t capacity)
{
    if (!id) { if (capacity) std::snprintf(error, capacity, "AppID required"); return 0; }
    static_cast<Context *>(p)->initialized = true; return 1;
}
static void ANASTACIO_PLUGIN_CALL shutdown(void *p) { static_cast<Context *>(p)->initialized = false; }
static uint32_t ANASTACIO_PLUGIN_CALL state(void *p) { return static_cast<Context *>(p)->initialized ? 1u : 0u; }
static uint64_t ANASTACIO_PLUGIN_CALL identity(void *p) { return 76561198000000000ULL + static_cast<Context *>(p)->frames; }
static void ANASTACIO_PLUGIN_CALL pump(void *p)
{
    if (!static_cast<Context *>(p)->initialized) std::abort();
    ++static_cast<Context *>(p)->frames;
}
#ifndef FIXTURE_MODE
#define FIXTURE_MODE 0
#endif
static const AnastacioPluginAPI api = {
    FIXTURE_MODE == 2 ? 8u : sizeof(AnastacioPluginAPI),
    FIXTURE_MODE == 1 ? 99u : ANASTACIO_PLUGIN_ABI_VERSION,
    create, destroy, initialize, shutdown, state, identity, FIXTURE_MODE == 3 ? nullptr : pump
};
#ifdef _WIN32
#define FIXTURE_EXPORT __declspec(dllexport)
#else
#define FIXTURE_EXPORT __attribute__((visibility("default")))
#endif
extern "C" FIXTURE_EXPORT const AnastacioPluginAPI *ANASTACIO_PLUGIN_CALL AnastacioSteam_GetApi(uint32_t)
{ return &api; }
