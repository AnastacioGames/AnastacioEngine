/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "NET_AnastacioPluginABI.h"
#include "steam/steam_api.h"
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <deque>
#include <map>
#include <memory>
#include <new>
#include <set>
#include <string>
#include <vector>
#include <type_traits>
#include <array>
#define NOMINMAX
#include <windows.h>
#include <shellapi.h>
#include <cwchar>
#include <cerrno>
namespace {
constexpr uint32_t maxReliable = 65536, maxUnreliable = 1200;
uint64_t commandLobby(const wchar_t *command)
{
    int argc = 0;
    wchar_t **argv = CommandLineToArgvW(command, &argc);
    uint64_t lobby = 0;
    if (!argv) return 0;
    for (int i = 1; i + 1 < argc; ++i) {
        if (std::wcscmp(argv[i], L"+connect_lobby") != 0) continue;
        wchar_t *end = nullptr; errno = 0;
        const auto id = std::wcstoull(argv[i + 1], &end, 10);
        if (argv[i + 1][0] >= L'0' && argv[i + 1][0] <= L'9' &&
            errno != ERANGE && end && !*end && CSteamID(id).IsLobby()) lobby = id;
    }
    LocalFree(argv); return lobby;
}
bool acceptSequence(uint32_t channel, int64 number, std::array<int64, 4> &last)
{
    if (channel >= 4) return false;
    if (channel < 2) return true;
    if (number <= last[channel]) return false;
    last[channel] = number; return true;
}
struct Endpoint;
void closeEndpoint(Endpoint *);
struct Context {
    bool initialized = false;
    std::set<Endpoint *> endpoints;
    CSteamID lobby;
    uint64_t lobbyHost = 0;
    AnastacioLobbyRequest request = {};
    uint32_t pending = 0;
    bool canceled = false;
    SteamAPICall_t pendingCall = k_uAPICallInvalid;
    // Cancel() unregisters the callback, not the backend operation. Reap late
    // create/join results independently so cancellation cannot orphan a lobby.
    std::vector<std::pair<SteamAPICall_t, uint32_t>> abandoned;
    std::chrono::steady_clock::time_point deadline;
    std::deque<AnastacioLobbyEvent> events;
    CCallResult<Context, LobbyCreated_t> created;
    CCallResult<Context, LobbyEnter_t> entered;
    CCallResult<Context, LobbyMatchList_t> listed;
    CCallback<Context, SteamNetConnectionStatusChangedCallback_t> connections;
    CCallback<Context, GameLobbyJoinRequested_t> invites;
    CCallback<Context, LobbyChatUpdate_t> members;
    Context() : connections(this, &Context::connection), invites(this, &Context::invite),
                members(this, &Context::member) {}
    void connection(SteamNetConnectionStatusChangedCallback_t *);
    void invite(GameLobbyJoinRequested_t *);
    void member(LobbyChatUpdate_t *);
    void onCreated(LobbyCreated_t *, bool);
    void onEntered(LobbyEnter_t *, bool);
    void onListed(LobbyMatchList_t *, bool);
    void cancelPending() {
        if (pendingCall != k_uAPICallInvalid && (pending == 1 || pending == 3))
            abandoned.emplace_back(pendingCall, pending);
        created.Cancel(); entered.Cancel(); listed.Cancel();
        pending = 0; pendingCall = k_uAPICallInvalid; canceled = true;
    }
    void reapAbandoned();
    void acceptPending();
    void expirePending() {
        if (pending && !canceled && std::chrono::steady_clock::now() > deadline) {
            cancelPending(); fail("Steam lobby operation timed out; retry available");
        }
    }
    void push(const AnastacioLobbyEvent &event) {
        if (events.size() < 256) events.push_back(event);
    }
    void fail(const char *text) {
        AnastacioLobbyEvent event = {}; event.type = 6;
        std::snprintf(event.detail, sizeof(event.detail), "%s", text); push(event);
    }
};
Context *owner = nullptr;
struct Endpoint {
    Context *ctx;
    HSteamListenSocket listener = k_HSteamListenSocket_Invalid;
    HSteamNetPollGroup group = k_HSteamNetPollGroup_Invalid;
    uint32_t limit = 64, nextPeer = 1;
    std::map<uint32_t, HSteamNetConnection> peers;
    std::map<uint32_t, std::array<int64, 4>> received;
    std::map<HSteamNetConnection, std::chrono::steady_clock::time_point> awaitingMembers;
    std::deque<AnastacioTransportEvent> events;
    explicit Endpoint(Context *context) : ctx(context) {}
    uint32_t find(HSteamNetConnection connection) const {
        for (const auto &item : peers) if (item.second == connection) return item.first;
        return 0;
    }
    uint32_t add(HSteamNetConnection connection) {
        if (peers.size() >= limit || nextPeer == 0 || events.size() >= 256) return 0;
        int priorities[4] = {0, 0, 0, 0}; uint16 weights[4] = {4, 2, 4, 2};
        if (SteamNetworkingSockets()->ConfigureConnectionLanes(connection, 4, priorities, weights) != k_EResultOK ||
            !SteamNetworkingSockets()->SetConnectionPollGroup(connection, group)) return 0;
        const auto peer = nextPeer++; peers.emplace(peer, connection);
        received.emplace(peer, std::array<int64, 4>{}); return peer;
    }
    void event(uint32_t type, uint32_t peer, uint64_t identity, const char *detail = "") {
        // Never drop lifecycle events. Received payloads do not use this queue.
        AnastacioTransportEvent event = {}; event.type = type; event.peer = peer;
        event.identity = identity;
        std::snprintf(event.detail, sizeof(event.detail), "%s", detail); events.push_back(event);
    }
};
void errorText(char *error, uint32_t capacity, const char *text)
{ if (capacity && error) std::snprintf(error, capacity, "%s", text); }
void closePeer(Endpoint *endpoint, uint32_t peer, const char *reason)
{
    auto it = endpoint->peers.find(peer);
    if (it == endpoint->peers.end()) return;
    SteamNetworkingSockets()->CloseConnection(it->second, 1000, reason, false);
    endpoint->peers.erase(it);
    endpoint->received.erase(peer);
    endpoint->event(2, peer, 0, reason);
}
void Context::connection(SteamNetConnectionStatusChangedCallback_t *change)
{
    if (!initialized) return;
    for (auto *endpoint : endpoints) {
        auto peer = endpoint->find(change->m_hConn);
        if (!peer && endpoint->listener != k_HSteamListenSocket_Invalid &&
            change->m_info.m_hListenSocket == endpoint->listener &&
            change->m_info.m_eState == k_ESteamNetworkingConnectionState_Connecting) {
            if (endpoint->peers.size() + endpoint->awaitingMembers.size() >= endpoint->limit) {
                SteamNetworkingSockets()->CloseConnection(change->m_hConn, 1001, "Room full", false);
                return;
            }
            // Lobby-backed hosts only accept current members. Direct SteamID sessions are allowed
            // without a lobby and still pass the native version/scene/password handshake.
            bool memberAllowed = !lobby.IsValid();
            if (lobby.IsValid()) {
                for (int i = 0; i < SteamMatchmaking()->GetNumLobbyMembers(lobby); ++i)
                    if (SteamMatchmaking()->GetLobbyMemberByIndex(lobby, i) == change->m_info.m_identityRemote.GetSteamID())
                        memberAllowed = true;
            }
            if (!memberAllowed && endpoint->peers.size() + endpoint->awaitingMembers.size() < endpoint->limit &&
                endpoint->events.size() < 256) {
                endpoint->awaitingMembers.emplace(change->m_hConn,
                    std::chrono::steady_clock::now() + std::chrono::seconds(3));
                return;
            }
            peer = memberAllowed ? endpoint->add(change->m_hConn) : 0;
            if (!peer || SteamNetworkingSockets()->AcceptConnection(change->m_hConn) != k_EResultOK) {
                if (peer) { endpoint->peers.erase(peer); endpoint->received.erase(peer); }
                SteamNetworkingSockets()->CloseConnection(change->m_hConn, 1001, "Room full or not a lobby member", false);
                return;
            }
        }
        if (!peer) {
            if (endpoint->awaitingMembers.erase(change->m_hConn))
                SteamNetworkingSockets()->CloseConnection(change->m_hConn, 1000, "Pending connection ended", false);
            continue;
        }
        if (change->m_info.m_eState == k_ESteamNetworkingConnectionState_Connected) {
            endpoint->event(1, peer, change->m_info.m_identityRemote.GetSteamID64());
        } else if (change->m_info.m_eState == k_ESteamNetworkingConnectionState_ClosedByPeer ||
                   change->m_info.m_eState == k_ESteamNetworkingConnectionState_ProblemDetectedLocally) {
            closePeer(endpoint, peer, change->m_info.m_szEndDebug);
        }
        return;
    }
}
void Context::acceptPending()
{
    for (auto *endpoint : endpoints) {
        for (auto it = endpoint->awaitingMembers.begin(); it != endpoint->awaitingMembers.end();) {
            SteamNetConnectionInfo_t info = {};
            bool allowed = false;
            if (lobby.IsValid() && SteamNetworkingSockets()->GetConnectionInfo(it->first, &info)) {
                for (int i = 0; i < SteamMatchmaking()->GetNumLobbyMembers(lobby); ++i)
                    if (SteamMatchmaking()->GetLobbyMemberByIndex(lobby, i) == info.m_identityRemote.GetSteamID())
                        allowed = true;
            }
            if (!allowed && lobby.IsValid() && std::chrono::steady_clock::now() < it->second) { ++it; continue; }
            const auto peer = allowed ? endpoint->add(it->first) : 0;
            if (!peer || SteamNetworkingSockets()->AcceptConnection(it->first) != k_EResultOK) {
                if (peer) { endpoint->peers.erase(peer); endpoint->received.erase(peer); }
                SteamNetworkingSockets()->CloseConnection(it->first, 1001, "Room full or not a lobby member", false);
            }
            it = endpoint->awaitingMembers.erase(it);
        }
    }
}
void closeEndpoint(Endpoint *endpoint)
{
    if (!endpoint || !endpoint->ctx->initialized) return;
    for (const auto &item : endpoint->peers)
        SteamNetworkingSockets()->CloseConnection(item.second, 1000, "Session ended", false);
    for (const auto &item : endpoint->awaitingMembers)
        SteamNetworkingSockets()->CloseConnection(item.first, 1000, "Session ended", false);
    endpoint->awaitingMembers.clear();
    endpoint->peers.clear(); endpoint->received.clear(); endpoint->events.clear();
    if (endpoint->listener) SteamNetworkingSockets()->CloseListenSocket(endpoint->listener);
    if (endpoint->group) SteamNetworkingSockets()->DestroyPollGroup(endpoint->group);
    endpoint->listener = 0; endpoint->group = 0;
}
void *ANASTACIO_PLUGIN_CALL create() { try { return new Context; } catch (...) { return nullptr; } }
void ANASTACIO_PLUGIN_CALL shutdown(void *context)
{
    auto *ctx = static_cast<Context *>(context);
    if (ctx && ctx->initialized) {
        for (auto *endpoint : ctx->endpoints) closeEndpoint(endpoint);
        ctx->created.Cancel(); ctx->entered.Cancel(); ctx->listed.Cancel();
        if (ctx->lobby.IsValid()) SteamMatchmaking()->LeaveLobby(ctx->lobby);
        ctx->lobby = CSteamID(); ctx->pending = 0; ctx->pendingCall = k_uAPICallInvalid;
        ctx->abandoned.clear(); ctx->events.clear();
        SteamAPI_Shutdown(); ctx->initialized = false; owner = nullptr;
    }
}
void ANASTACIO_PLUGIN_CALL destroy(void *context)
{ shutdown(context); delete static_cast<Context *>(context); }
int32_t ANASTACIO_PLUGIN_CALL initialize(void *context, uint32_t appId, char *error, uint32_t capacity)
{
    auto *ctx = static_cast<Context *>(context);
    if (!ctx || !appId) { errorText(error, capacity, "A nonzero game AppID is required"); return 0; }
    if (owner || SteamAPI_GetHSteamUser() != 0) {
        errorText(error, capacity, "Steam runtime already initialized; disable the legacy Steam initializer"); return 0;
    }
    if (!SteamAPI_IsSteamRunning()) { errorText(error, capacity, "Steam client is not running"); return 0; }
    if (!SteamAPI_Init()) {
        errorText(error, capacity, "Steam initialization failed: check login, game access and launch AppID"); return 0;
    }
    ctx->initialized = true; owner = ctx;
    if (!SteamUser() || !SteamUtils() || !SteamUser()->BLoggedOn()) {
        errorText(error, capacity, "Steam account is not logged on"); shutdown(ctx); return 0;
    }
    if (SteamUtils()->GetAppID() != appId) {
        errorText(error, capacity, "Requested AppID differs from Steam launch/development AppID"); shutdown(ctx); return 0;
    }
    if (!SteamNetworkingSockets() || !SteamMatchmaking()) {
        errorText(error, capacity, "Required Steam interfaces unavailable"); shutdown(ctx); return 0;
    }
    SteamNetworkingUtils()->InitRelayNetworkAccess();
    SteamUserStats()->RequestCurrentStats();
    char command[2048] = {};
    SteamApps()->GetLaunchCommandLine(command, sizeof(command));
    const char *invite = std::strstr(command, "+connect_lobby ");
    uint64_t launchLobby = 0;
    if (invite) {
        unsigned long long id = 0;
        if (std::sscanf(invite + 15, "%llu", &id) == 1 && CSteamID(id).IsLobby()) {
            launchLobby = id;
        }
    }
    // Steam may supply the invite through the actual process arguments instead.
    // Read only in the optional Windows DLL; the engine ABI stays SDK-independent.
    const auto processLobby = commandLobby(GetCommandLineW());
    if (processLobby) launchLobby = processLobby;
    if (launchLobby) {
        AnastacioLobbyEvent event = {}; event.type = 5; event.lobby = launchLobby; ctx->push(event);
    }
    return 1;
}
uint32_t ANASTACIO_PLUGIN_CALL state(void *context)
{ auto *ctx = static_cast<Context *>(context); return ctx && ctx->initialized && SteamUser() && SteamUser()->BLoggedOn() ? 1u : 0u; }
uint64_t ANASTACIO_PLUGIN_CALL identity(void *context)
{ return state(context) ? SteamUser()->GetSteamID().ConvertToUint64() : 0; }
void ANASTACIO_PLUGIN_CALL pump(void *context)
{
    auto *ctx = static_cast<Context *>(context);
    if (!ctx->initialized) return;
    SteamAPI_RunCallbacks();
    ctx->acceptPending();
    ctx->reapAbandoned();
    ctx->expirePending();
}
void *ANASTACIO_PLUGIN_CALL transportCreate(void *context)
{
    if (!state(context)) return nullptr;
    try {
        auto endpoint = std::make_unique<Endpoint>(static_cast<Context *>(context));
        endpoint->ctx->endpoints.insert(endpoint.get());
        endpoint->group = SteamNetworkingSockets()->CreatePollGroup();
        if (!endpoint->group) { endpoint->ctx->endpoints.erase(endpoint.get()); return nullptr; }
        return endpoint.release();
    } catch (...) { return nullptr; }
}
void ANASTACIO_PLUGIN_CALL transportDestroy(void *transport)
{
    auto *endpoint = static_cast<Endpoint *>(transport); closeEndpoint(endpoint);
    endpoint->ctx->endpoints.erase(endpoint); delete endpoint;
}
int32_t ANASTACIO_PLUGIN_CALL listen(void *transport, uint32_t port, uint32_t maxPeers)
{
    auto *endpoint = static_cast<Endpoint *>(transport);
    if (endpoint->listener || !endpoint->peers.empty() || port > 65535 || maxPeers < 1 || maxPeers > 80) return 0;
    endpoint->limit = maxPeers;
    endpoint->listener = SteamNetworkingSockets()->CreateListenSocketP2P(int(port), 0, nullptr);
    return endpoint->listener != 0;
}
int32_t ANASTACIO_PLUGIN_CALL connect(void *transport, uint64_t id, uint32_t port)
{
    auto *endpoint = static_cast<Endpoint *>(transport);
    if (endpoint->listener || !endpoint->peers.empty() || port > 65535 || !CSteamID(id).IsValid()) return 0;
    SteamNetworkingIdentity remote; remote.SetSteamID64(id);
    const auto connection = SteamNetworkingSockets()->ConnectP2P(remote, int(port), 0, nullptr);
    if (!connection) return 0;
    if (!endpoint->add(connection)) { SteamNetworkingSockets()->CloseConnection(connection, 1000, "Setup failed", false); return 0; }
    return 1;
}
int32_t ANASTACIO_PLUGIN_CALL send(void *transport, uint32_t peer, uint32_t channel, const uint8_t *data, uint32_t size)
{
    auto *endpoint = static_cast<Endpoint *>(transport);
    const auto found = endpoint->peers.find(peer);
    if (found == endpoint->peers.end() || channel > 3 || !data || size == 0 ||
        size > (channel < 2 ? maxReliable : maxUnreliable)) return 0;
    SteamNetConnectionRealTimeStatus_t status = {};
    if (SteamNetworkingSockets()->GetConnectionRealTimeStatus(found->second, &status, 0, nullptr) != k_EResultOK ||
        status.m_cbPendingReliable + status.m_cbPendingUnreliable > 4 * 1024 * 1024) {
        closePeer(endpoint, peer, "Steam send queue exceeded"); return 0;
    }
    auto *message = SteamNetworkingUtils()->AllocateMessage(int(size + 2));
    if (!message) { closePeer(endpoint, peer, "Packet allocation failed"); return 0; }
    auto *bytes = static_cast<uint8_t *>(message->m_pData);
    bytes[0] = 1; bytes[1] = uint8_t(channel); std::memcpy(bytes + 2, data, size);
    message->m_conn = found->second;
    message->m_nFlags = channel < 2 ? k_nSteamNetworkingSend_Reliable : k_nSteamNetworkingSend_Unreliable;
    message->m_idxLane = uint16(channel);
    int64 result = 0; SteamNetworkingSockets()->SendMessages(1, &message, &result);
    if (result < 0) { closePeer(endpoint, peer, "Steam packet send failed"); return 0; }
    return 1;
}
void ANASTACIO_PLUGIN_CALL disconnect(void *transport, uint32_t peer)
{ closePeer(static_cast<Endpoint *>(transport), peer, "Disconnected"); }
int32_t ANASTACIO_PLUGIN_CALL poll(void *transport, AnastacioTransportEvent *event, uint8_t *data, uint32_t capacity)
{
    auto *endpoint = static_cast<Endpoint *>(transport);
    if (!endpoint->events.empty()) { *event = endpoint->events.front(); endpoint->events.pop_front(); return 1; }
    SteamNetworkingMessage_t *message = nullptr;
    if (SteamNetworkingSockets()->ReceiveMessagesOnPollGroup(endpoint->group, &message, 1) <= 0) return 0;
    const uint32_t peer = endpoint->find(message->m_conn);
    const auto *bytes = static_cast<const uint8_t *>(message->m_pData);
    const bool valid = peer && message->m_cbSize > 2 && bytes[0] == 1 && bytes[1] < 4 &&
        message->m_idxLane == bytes[1] &&
        uint32_t(message->m_cbSize - 2) <= (bytes[1] < 2 ? maxReliable : maxUnreliable) &&
        uint32_t(message->m_cbSize - 2) <= capacity;
    if (!valid) {
        message->Release(); if (peer) closePeer(endpoint, peer, "Invalid Steam packet"); return -1;
    }
    // SDK message numbers are monotonic per lane. Match ENet's unreliable
    // sequenced delivery without imposing ordering between independent channels.
    if (!acceptSequence(bytes[1], message->m_nMessageNumber, endpoint->received.at(peer))) {
        message->Release(); return -1;
    }
    *event = {}; event->type = 3; event->peer = peer; event->channel = bytes[1];
    event->size = uint32_t(message->m_cbSize - 2); std::memcpy(data, bytes + 2, event->size);
    message->Release(); return 1;
}
int32_t ANASTACIO_PLUGIN_CALL socketPair(void *first, void *second)
{
    auto *a = static_cast<Endpoint *>(first); auto *b = static_cast<Endpoint *>(second);
    if (a == b || !a->peers.empty() || !b->peers.empty() || a->listener || b->listener) return 0;
    HSteamNetConnection x = 0, y = 0;
    if (!SteamNetworkingSockets()->CreateSocketPair(&x, &y, true, nullptr, nullptr)) return 0;
    auto p = a->add(x), q = b->add(y);
    if (!p || !q) {
        if (p) a->peers.erase(p); if (q) b->peers.erase(q);
        SteamNetworkingSockets()->CloseConnection(x, 1000, "Pair failed", false);
        SteamNetworkingSockets()->CloseConnection(y, 1000, "Pair failed", false); return 0;
    }
    a->event(1, p, identity(a->ctx)); b->event(1, q, identity(b->ctx)); return 1;
}
AnastacioLobbyEvent lobbyInfo(Context *ctx, CSteamID lobby, uint32_t type)
{
    AnastacioLobbyEvent event = {}; event.type = type; event.lobby = lobby.ConvertToUint64();
    auto *mm = SteamMatchmaking(); event.host = mm->GetLobbyOwner(lobby).ConvertToUint64();
    event.members = uint32_t(mm->GetNumLobbyMembers(lobby)); event.capacity = uint32_t(mm->GetLobbyMemberLimit(lobby));
    const auto *port = mm->GetLobbyData(lobby, "anastacio_port"); unsigned int value = 0;
    if (std::sscanf(port, "%u", &value) == 1 && value <= 65535) event.port = value;
    std::snprintf(event.name, sizeof(event.name), "%s", mm->GetLobbyData(lobby, "anastacio_name"));
    (void)ctx; return event;
}
bool compatible(Context *ctx, CSteamID lobby)
{
    auto *mm = SteamMatchmaking();
    return std::strcmp(mm->GetLobbyData(lobby, "anastacio_game"), ctx->request.game) == 0 &&
           std::strcmp(mm->GetLobbyData(lobby, "anastacio_build"), ctx->request.build) == 0 &&
           std::strcmp(mm->GetLobbyData(lobby, "anastacio_protocol"), "2") == 0 &&
           std::strcmp(mm->GetLobbyData(lobby, "anastacio_open"), "1") == 0;
}
void Context::onCreated(LobbyCreated_t *result, bool io)
{
    pending = 0; pendingCall = k_uAPICallInvalid;
    if (io || result->m_eResult != k_EResultOK) { if (!canceled) fail("Unable to create Steam lobby"); return; }
    CSteamID id(result->m_ulSteamIDLobby);
    if (canceled) { SteamMatchmaking()->LeaveLobby(id); return; }
    lobby = id; lobbyHost = identity(this); auto *mm = SteamMatchmaking();
    char port[16]; std::snprintf(port, sizeof(port), "%u", request.port);
    bool ok = mm->SetLobbyData(id, "anastacio_game", request.game) &&
        mm->SetLobbyData(id, "anastacio_build", request.build) &&
        mm->SetLobbyData(id, "anastacio_protocol", "2") &&
        mm->SetLobbyData(id, "anastacio_name", request.name) &&
        mm->SetLobbyData(id, "anastacio_port", port) &&
        mm->SetLobbyData(id, "anastacio_open", "1");
    if (!ok) { mm->LeaveLobby(id); lobby = CSteamID(); fail("Unable to publish lobby metadata"); return; }
    push(lobbyInfo(this, id, 1));
}
void Context::onEntered(LobbyEnter_t *result, bool io)
{
    pending = 0; pendingCall = k_uAPICallInvalid;
    CSteamID id(result->m_ulSteamIDLobby);
    if (io || result->m_EChatRoomEnterResponse != k_EChatRoomEnterResponseSuccess) {
        if (!canceled) fail("Steam lobby unavailable, full or access denied"); return;
    }
    if (canceled || !compatible(this, id)) {
        SteamMatchmaking()->LeaveLobby(id); if (!canceled) fail("Lobby game/build/protocol incompatible or match already started"); return;
    }
    lobby = id; lobbyHost = SteamMatchmaking()->GetLobbyOwner(id).ConvertToUint64();
    push(lobbyInfo(this, id, 2));
}
void Context::onListed(LobbyMatchList_t *result, bool io)
{
    pending = 0; pendingCall = k_uAPICallInvalid;
    if (canceled) return;
    if (io) { fail("Unable to list Steam lobbies"); return; }
    for (uint32_t i = 0; i < std::min(result->m_nLobbiesMatching, 128u); ++i)
        push(lobbyInfo(this, SteamMatchmaking()->GetLobbyByIndex(int(i)), 3));
    AnastacioLobbyEvent event = {}; event.type = 4; push(event);
}
void Context::reapAbandoned()
{
    auto *utils = SteamUtils();
    for (auto it = abandoned.begin(); it != abandoned.end();) {
        bool io = false;
        if (!utils->IsAPICallCompleted(it->first, &io)) { ++it; continue; }
        CSteamID id;
        if (!io && it->second == 1) {
            LobbyCreated_t result = {};
            if (utils->GetAPICallResult(it->first, &result, sizeof(result), LobbyCreated_t::k_iCallback, &io) &&
                !io && result.m_eResult == k_EResultOK) id = CSteamID(result.m_ulSteamIDLobby);
        } else if (!io && it->second == 3) {
            LobbyEnter_t result = {};
            if (utils->GetAPICallResult(it->first, &result, sizeof(result), LobbyEnter_t::k_iCallback, &io) &&
                !io && result.m_EChatRoomEnterResponse == k_EChatRoomEnterResponseSuccess)
                id = CSteamID(result.m_ulSteamIDLobby);
        }
        if (id.IsValid() && id != lobby) SteamMatchmaking()->LeaveLobby(id);
        it = abandoned.erase(it);
    }
}
void Context::invite(GameLobbyJoinRequested_t *invite)
{ AnastacioLobbyEvent event = {}; event.type = 5; event.lobby = invite->m_steamIDLobby.ConvertToUint64(); push(event); }
void Context::member(LobbyChatUpdate_t *change)
{
    if (!lobby.IsValid() || change->m_ulSteamIDLobby != lobby.ConvertToUint64()) return;
    if (SteamMatchmaking()->GetLobbyOwner(lobby).ConvertToUint64() != lobbyHost ||
        (change->m_ulSteamIDUserChanged == lobbyHost &&
         (change->m_rgfChatMemberStateChange & (k_EChatMemberStateChangeLeft | k_EChatMemberStateChangeDisconnected |
                                               k_EChatMemberStateChangeKicked | k_EChatMemberStateChangeBanned)))) {
        auto event = lobbyInfo(this, lobby, 7); std::snprintf(event.detail, sizeof(event.detail), "Host left; match ended"); push(event);
        SteamMatchmaking()->LeaveLobby(lobby); lobby = CSteamID();
    }
}
int32_t ANASTACIO_PLUGIN_CALL lobbyRequest(void *context, const AnastacioLobbyRequest *request, char *error, uint32_t capacity)
{
    auto *ctx = static_cast<Context *>(context);
    if (!state(ctx) || !request) { errorText(error, capacity, "Steam unavailable"); return 0; }
    auto *mm = SteamMatchmaking();
    if (request->operation == 4) {
        // Drop stale lobby results but keep unread invites: accepting one leaves first.
        ctx->cancelPending();
        ctx->events.erase(std::remove_if(ctx->events.begin(), ctx->events.end(),
            [](const AnastacioLobbyEvent &event) { return event.type != 5; }), ctx->events.end());
        if (ctx->lobby.IsValid()) mm->LeaveLobby(ctx->lobby);
        ctx->lobby = CSteamID(); ctx->lobbyHost = 0; return 1;
    }
    if (request->operation == 5 || request->operation == 6) {
        if (!ctx->lobby.IsValid()) { errorText(error, capacity, "Not in a Steam lobby"); return 0; }
        if (request->operation == 5) {
            if (!SteamUtils()->IsOverlayEnabled()) { errorText(error, capacity, "Steam overlay unavailable"); return 0; }
            SteamFriends()->ActivateGameOverlayInviteDialog(ctx->lobby); return 1;
        }
        if (mm->GetLobbyOwner(ctx->lobby) != SteamUser()->GetSteamID()) {
            errorText(error, capacity, "Only host can update lobby state"); return 0;
        }
        return mm->SetLobbyJoinable(ctx->lobby, request->capacity != 0) &&
               mm->SetLobbyData(ctx->lobby, "anastacio_open", request->capacity ? "1" : "0");
    }
    if (ctx->pending || (ctx->lobby.IsValid() && request->operation != 2)) { errorText(error, capacity, "Leave existing lobby or wait for pending request"); return 0; }
    if (ctx->abandoned.size() >= 64) {
        errorText(error, capacity, "Too many unfinished Steam operations; reconnect Steam"); return 0;
    }
    if (!request->game[0] || !request->build[0] || request->operation < 1 || request->operation > 3 ||
        !std::memchr(request->name, 0, sizeof(request->name)) ||
        !std::memchr(request->game, 0, sizeof(request->game)) || !std::memchr(request->build, 0, sizeof(request->build))) {
        errorText(error, capacity, "Invalid lobby request"); return 0;
    }
    ctx->request = *request; ctx->canceled = false; ctx->pending = request->operation;
    ctx->deadline = std::chrono::steady_clock::now() + std::chrono::seconds(20);
    SteamAPICall_t call = k_uAPICallInvalid;
    if (request->operation == 1) {
        if (request->capacity < 2 || request->capacity > 64 || request->port < 1 || request->port > 65535) {
            ctx->pending = 0; errorText(error, capacity, "Lobby capacity must be 2..64 and port 1..65535"); return 0;
        }
        call = mm->CreateLobby(request->friends_only ? k_ELobbyTypeFriendsOnly : k_ELobbyTypePublic, int(request->capacity));
        ctx->created.Set(call, ctx, &Context::onCreated);
    } else if (request->operation == 2) {
        mm->AddRequestLobbyListStringFilter("anastacio_game", request->game, k_ELobbyComparisonEqual);
        mm->AddRequestLobbyListStringFilter("anastacio_build", request->build, k_ELobbyComparisonEqual);
        mm->AddRequestLobbyListStringFilter("anastacio_protocol", "2", k_ELobbyComparisonEqual);
        mm->AddRequestLobbyListStringFilter("anastacio_open", "1", k_ELobbyComparisonEqual);
        mm->AddRequestLobbyListDistanceFilter(k_ELobbyDistanceFilterWorldwide);
        mm->AddRequestLobbyListResultCountFilter(128); mm->AddRequestLobbyListFilterSlotsAvailable(1);
        call = mm->RequestLobbyList(); ctx->listed.Set(call, ctx, &Context::onListed);
    } else {
        if (!CSteamID(request->lobby).IsLobby()) { ctx->pending = 0; errorText(error, capacity, "Invalid lobby ID"); return 0; }
        call = mm->JoinLobby(CSteamID(request->lobby)); ctx->entered.Set(call, ctx, &Context::onEntered);
    }
    if (call == k_uAPICallInvalid) { ctx->pending = 0; errorText(error, capacity, "Steam rejected lobby operation"); return 0; }
    ctx->pendingCall = call;
    return 1;
}
int32_t ANASTACIO_PLUGIN_CALL lobbyPoll(void *context, AnastacioLobbyEvent *event)
{
    auto *ctx = static_cast<Context *>(context);
    if (ctx->events.empty()) return 0; *event = ctx->events.front(); ctx->events.pop_front(); return 1;
}
const char *ANASTACIO_PLUGIN_CALL language(void *context)
{ return state(context) ? SteamApps()->GetCurrentGameLanguage() : ""; }
int32_t ANASTACIO_PLUGIN_CALL achievement(void *context, const char *name, uint32_t unlock)
{
    if (!state(context) || !name || !*name) return 0;
    if (unlock) return SteamUserStats()->SetAchievement(name) && SteamUserStats()->StoreStats();
    bool value = false; return SteamUserStats()->GetAchievement(name, &value) && value;
}
int32_t ANASTACIO_PLUGIN_CALL relayMode(void *context, uint32_t force)
{
    if (!state(context) || !static_cast<Context *>(context)->endpoints.empty()) return 0;
    return SteamNetworkingUtils()->SetGlobalConfigValueInt32(k_ESteamNetworkingConfig_P2P_Transport_ICE_Enable,
        force ? k_nSteamNetworkingConfig_P2P_Transport_ICE_Enable_Disable : k_nSteamNetworkingConfig_P2P_Transport_ICE_Enable_Default);
}
int32_t ANASTACIO_PLUGIN_CALL route(void *transport, uint32_t peer)
{
    auto *endpoint = static_cast<Endpoint *>(transport); const auto found = endpoint->peers.find(peer);
    SteamNetConnectionInfo_t info = {};
    if (found == endpoint->peers.end() || !SteamNetworkingSockets()->GetConnectionInfo(found->second, &info) ||
        info.m_eState != k_ESteamNetworkingConnectionState_Connected) return 0;
    return info.m_idPOPRelay ? 2 : 1;
}


int32_t ANASTACIO_PLUGIN_CALL connectionInfo(void *context, uint32_t index, AnastacioConnectionInfo *info)
{
    auto *ctx = static_cast<Context *>(context);
    for (auto *endpoint : ctx->endpoints) for (const auto &peer : endpoint->peers) {
        if (index-- != 0) continue;
        SteamNetConnectionInfo_t sdkInfo = {};
        if (!SteamNetworkingSockets()->GetConnectionInfo(peer.second, &sdkInfo)) return 0;
        *info = {}; info->peer = peer.first; info->remote = sdkInfo.m_identityRemote.GetSteamID64();
        info->route = uint32_t(route(endpoint, peer.first)); return 1;
    }
    return 0;
}
// No exception may escape the DLL, including allocation failures in callbacks.
template<typename> struct Guard;
template<typename R, typename... Args> struct Guard<R (ANASTACIO_PLUGIN_CALL *)(Args...)> {
    template<R (ANASTACIO_PLUGIN_CALL *Function)(Args...)>
    static R ANASTACIO_PLUGIN_CALL invoke(Args... args) noexcept {
        try { return Function(args...); }
        catch (...) { if constexpr (!std::is_void_v<R>) return R{}; }
    }
};
#define GUARDED(function) &Guard<decltype(&function)>::invoke<&function>
const AnastacioPluginAPI api = { sizeof(AnastacioPluginAPI), ANASTACIO_PLUGIN_ABI_VERSION,
    GUARDED(create), GUARDED(destroy), GUARDED(initialize), GUARDED(shutdown), GUARDED(state), GUARDED(identity), GUARDED(pump),
    GUARDED(transportCreate), GUARDED(transportDestroy), GUARDED(listen), GUARDED(connect), GUARDED(send), GUARDED(disconnect), GUARDED(poll), GUARDED(socketPair),
    GUARDED(lobbyRequest), GUARDED(lobbyPoll), GUARDED(language), GUARDED(achievement), GUARDED(relayMode), GUARDED(route), GUARDED(connectionInfo) };
}
extern "C" __declspec(dllexport) const AnastacioPluginAPI *ANASTACIO_PLUGIN_CALL
AnastacioSteam_GetApi(uint32_t version)
{ return version == ANASTACIO_PLUGIN_ABI_VERSION ? &api : nullptr; }
