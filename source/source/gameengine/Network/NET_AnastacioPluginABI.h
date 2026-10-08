/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef ANASTACIO_PLUGIN_ABI_H
#define ANASTACIO_PLUGIN_ABI_H
#include <stdint.h>
#ifdef _WIN32
# define ANASTACIO_PLUGIN_CALL __cdecl
#else
# define ANASTACIO_PLUGIN_CALL
#endif
#ifdef __cplusplus
extern "C" {
#endif
/* All calls run on the owner thread. Plugins must not throw across this ABI.
 * Error buffers are caller-owned, UTF-8 and NUL terminated when capacity > 0.
 * destroy handles partially initialized contexts; shutdown is idempotent.
 * API tables remain valid until library unload. No callbacks survive destroy. */
#define ANASTACIO_PLUGIN_ABI_VERSION 2u

/* Packet payloads remain the native ANET protocol. SDK types never cross the ABI. */
typedef struct AnastacioTransportEvent {
    uint32_t type; /* 1 connected, 2 disconnected, 3 received */
    uint32_t peer;
    uint32_t channel;
    uint32_t size;
    uint64_t identity;
    char detail[256];
} AnastacioTransportEvent;
typedef struct AnastacioLobbyEvent {
    uint32_t type; /* 1 created, 2 entered, 3 list entry, 4 list end, 5 invite, 6 error, 7 host left */
    uint32_t members;
    uint32_t capacity;
    uint32_t port;
    uint64_t lobby;
    uint64_t host;
    char name[256];
    char detail[256];
} AnastacioLobbyEvent;
typedef struct AnastacioLobbyRequest {
    uint32_t operation; /* 1 create, 2 list, 3 join, 4 leave/cancel, 5 invite overlay, 6 joinable */
    uint32_t capacity;
    uint32_t port;
    uint32_t friends_only;
    uint64_t lobby;
    char name[256];
    char game[128];
    char build[128];
} AnastacioLobbyRequest;
typedef struct AnastacioConnectionInfo {
    uint32_t peer;
    uint32_t route; /* 0 unknown, 1 direct, 2 Steam relay */
    uint64_t remote;
} AnastacioConnectionInfo;
typedef struct AnastacioPluginAPI {
    uint32_t size;
    uint32_t version;
    void *(ANASTACIO_PLUGIN_CALL *create)(void);
    void (ANASTACIO_PLUGIN_CALL *destroy)(void *context);
    int32_t (ANASTACIO_PLUGIN_CALL *initialize)(void *context, uint32_t app_id,
                                              char *error, uint32_t capacity);
    void (ANASTACIO_PLUGIN_CALL *shutdown)(void *context);
    uint32_t (ANASTACIO_PLUGIN_CALL *state)(void *context); /* 0 offline, 1 ready */
    uint64_t (ANASTACIO_PLUGIN_CALL *identity)(void *context);
    void (ANASTACIO_PLUGIN_CALL *pump)(void *context);
    void *(ANASTACIO_PLUGIN_CALL *transport_create)(void *context);
    void (ANASTACIO_PLUGIN_CALL *transport_destroy)(void *transport);
    int32_t (ANASTACIO_PLUGIN_CALL *listen)(void *transport, uint32_t port, uint32_t max_peers);
    int32_t (ANASTACIO_PLUGIN_CALL *connect)(void *transport, uint64_t identity, uint32_t port);
    int32_t (ANASTACIO_PLUGIN_CALL *send)(void *transport, uint32_t peer, uint32_t channel,
                                        const uint8_t *data, uint32_t size);
    void (ANASTACIO_PLUGIN_CALL *disconnect)(void *transport, uint32_t peer);
    int32_t (ANASTACIO_PLUGIN_CALL *poll)(void *transport, AnastacioTransportEvent *event,
                                        uint8_t *data, uint32_t capacity);
    /* Diagnostic SDK socket pair; does not prove Internet connectivity or relay. */
    int32_t (ANASTACIO_PLUGIN_CALL *socket_pair)(void *first, void *second);
    int32_t (ANASTACIO_PLUGIN_CALL *lobby_request)(void *context, const AnastacioLobbyRequest *request,
                                                 char *error, uint32_t capacity);
    int32_t (ANASTACIO_PLUGIN_CALL *lobby_poll)(void *context, AnastacioLobbyEvent *event);
    const char *(ANASTACIO_PLUGIN_CALL *language)(void *context);
    int32_t (ANASTACIO_PLUGIN_CALL *achievement)(void *context, const char *name, uint32_t unlock);
    int32_t (ANASTACIO_PLUGIN_CALL *relay_mode)(void *context, uint32_t force_relay);
    int32_t (ANASTACIO_PLUGIN_CALL *route)(void *transport, uint32_t peer); /* 0 unknown, 1 direct, 2 relay */
    int32_t (ANASTACIO_PLUGIN_CALL *connections)(void *context, uint32_t index, AnastacioConnectionInfo *info);
} AnastacioPluginAPI;
typedef const AnastacioPluginAPI *(ANASTACIO_PLUGIN_CALL *AnastacioPluginGetAPI)(uint32_t version);
/* Complement export: AnastacioSteam_GetApi(version). Null means unsupported ABI. */
#ifdef __cplusplus
}
#endif
#endif
