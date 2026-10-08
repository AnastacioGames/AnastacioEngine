/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "NET_TransportSteam.h"
#include "NET_AnastacioPlugin.h"
#include <array>
#include <charconv>
namespace net {
class AnastacioSteamTransport final : public ITransport {
public:
    AnastacioPlugin &service;
    void *endpoint;
    bool diagnostic = false;
    AnastacioSteamTransport(AnastacioPlugin &owner, void *handle) : service(owner), endpoint(handle)
    { service.retainTransport(); }
    ~AnastacioSteamTransport() override { shutdown(); service.releaseTransport(); }
    bool listen(uint16_t port, int maxPeers) override {
        return endpoint && maxPeers > 0 && (diagnostic || service.api()->listen(endpoint, port, uint32_t(maxPeers)));
    }
    bool connect(const std::string &host, uint16_t port) override {
        if (diagnostic) return endpoint != nullptr;
        uint64_t id = 0;
        auto parsed = std::from_chars(host.data(), host.data() + host.size(), id);
        return endpoint && parsed.ec == std::errc() && parsed.ptr == host.data() + host.size() &&
            id != 0 && service.api()->connect(endpoint, id, port);
    }
    void send(PeerId peer, Channel channel, const uint8_t *data, size_t size) override {
        if (endpoint && size <= UINT32_MAX && !service.api()->send(endpoint, peer, uint32_t(channel), data, uint32_t(size)))
            service.api()->disconnect(endpoint, peer);
    }
    void disconnect(PeerId peer) override { if (endpoint) service.api()->disconnect(endpoint, peer); }
    void poll(std::vector<TransportEvent> &events) override {
        if (!endpoint) return;
        std::array<uint8_t, 65536> data;
        size_t bytes = 0;
        for (int i = 0; i < 256 && bytes < 1024 * 1024; ++i) {
            AnastacioTransportEvent raw = {};
            const int result = service.api()->poll(endpoint, &raw, data.data(), uint32_t(data.size()));
            if (result == 0) break;
            if (result < 0) continue;
            TransportEvent event; event.peer = raw.peer;
            if (raw.type == 1) event.type = TransportEvent::Type::Connected;
            else if (raw.type == 2) event.type = TransportEvent::Type::Disconnected;
            else if (raw.type == 3 && raw.channel < kChannelCount && raw.size <= data.size()) {
                event.type = TransportEvent::Type::Received; event.channel = Channel(raw.channel);
                event.data.assign(data.begin(), data.begin() + raw.size); bytes += raw.size;
            } else continue;
            events.push_back(std::move(event));
        }
    }
    void shutdown() override {
        if (endpoint) { service.api()->transport_destroy(endpoint); endpoint = nullptr; }
    }
    bool reliableAll() const override { return false; }
};
std::unique_ptr<ITransport> createAnastacioSteamTransport(AnastacioPlugin &service)
{
    const auto *api = service.api();
    if (!service.ready() || !api->transport_create || !api->transport_destroy || !api->listen ||
        !api->connect || !api->send || !api->disconnect || !api->poll) return nullptr;
    void *endpoint = api->transport_create(service.context());
    if (!endpoint) return nullptr;
    return std::unique_ptr<ITransport>(new AnastacioSteamTransport(service, endpoint));
}
bool createAnastacioSteamSocketPair(AnastacioPlugin &service,
    std::unique_ptr<ITransport> &first, std::unique_ptr<ITransport> &second)
{
    auto a = createAnastacioSteamTransport(service), b = createAnastacioSteamTransport(service);
    if (!a || !b || !service.api()->socket_pair || !service.api()->socket_pair(
            static_cast<AnastacioSteamTransport *>(a.get())->endpoint,
            static_cast<AnastacioSteamTransport *>(b.get())->endpoint)) return false;
    static_cast<AnastacioSteamTransport *>(a.get())->diagnostic = true;
    static_cast<AnastacioSteamTransport *>(b.get())->diagnostic = true;
    first = std::move(a); second = std::move(b); return true;
}
}
