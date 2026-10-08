/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "NET_AnastacioPlugin.h"
#include "NET_TransportSteam.h"
#include "NET_Session.h"
#include "NET_Replicator.h"
#include "NET_ReplicaClient.h"
#include <algorithm>
#include <cmath>
#include <chrono>
#include <iostream>
#include <stdexcept>
#include <thread>
using namespace net;
static void check(bool ok, const char *text) {
    if (!ok) throw std::runtime_error(text);
    std::cout << "STEAMPROBE ok " << text << std::endl;
}

class ProbeWorld : public IWorld {
public:
    std::map<NetId, ObjectState> objects;
    std::map<NetId, ClientId> owners;
    bool getTransform(NetId id, float p[3], float q[4]) const override {
        auto it = objects.find(id); if (it == objects.end()) return false;
        std::copy_n(it->second.position, 3, p); std::copy_n(it->second.rotation, 4, q); return true;
    }
    bool getVelocity(NetId id, float v[3], float a[3]) const override {
        auto it = objects.find(id); if (it == objects.end()) return false;
        std::copy_n(it->second.velocity, 3, v); std::copy_n(it->second.angularVelocity, 3, a); return true;
    }
    bool getProperties(NetId id, std::vector<PropValue> &p) const override {
        auto it = objects.find(id); if (it == objects.end()) return false; p = it->second.props; return true;
    }
    bool isSleeping(NetId) const override { return false; }
    void setTransform(NetId id, const float p[3], const float q[4]) override {
        std::copy_n(p, 3, objects[id].position); std::copy_n(q, 4, objects[id].rotation);
    }
    void setVelocity(NetId id, const float v[3], const float a[3]) override {
        std::copy_n(v, 3, objects[id].velocity); std::copy_n(a, 3, objects[id].angularVelocity);
    }
    void setProperties(NetId id, const std::vector<PropValue> &p) override { objects[id].props = p; }
    bool spawn(NetId id, const std::string &, ClientId owner, const ObjectState &state) override {
        objects[id] = state; objects[id].id = id; owners[id] = owner; return true;
    }
    void despawn(NetId id) override { objects.erase(id); owners.erase(id); }
    void setOwner(NetId id, ClientId owner) override { owners[id] = owner; }
    bool exists(NetId id) const override { return objects.count(id) != 0; }
};
int main(int argc, char **argv)
{
    try {
        check(argc >= 2, "DLL argument supplied");
        AnastacioPlugin service;
        check(service.load(argv[1]), "complement loaded");
        check(service.initialize(argc > 2 ? uint32_t(std::stoul(argv[2])) : 480), "SDK initialized");
        std::unique_ptr<ITransport> a, b;
        check(createAnastacioSteamSocketPair(service, a, b), "SDK network-loopback socket pair created");
        std::vector<TransportEvent> ea, eb; a->poll(ea); b->poll(eb);
        check(!ea.empty() && !eb.empty(), "connected events");
        service.unload(); check(service.loaded(), "live transport prevents library unload");
        for (int channel = 0; channel < 4; ++channel) {
            const size_t size = channel < 2 ? 65536 : 1200;
            std::vector<uint8_t> data(size, uint8_t(10 + channel));
            a->send(ea.front().peer, Channel(channel), data.data(), data.size());
        }
        bool seen[4] = {}; auto start = steadyClockMs();
        while (steadyClockMs() - start < 10000) {
            service.pump(); std::vector<TransportEvent> events; b->poll(events);
            for (const auto &event : events) if (event.type == TransportEvent::Type::Received) {
                const auto channel = int(event.channel);
                check(event.data.size() == size_t(channel < 2 ? 65536 : 1200) &&
                      event.data.front() == uint8_t(10 + channel) && event.data.back() == uint8_t(10 + channel), "channel payload preserved");
                seen[channel] = true;
            }
            if (seen[0] && seen[1] && seen[2] && seen[3]) break;
            std::this_thread::sleep_for(std::chrono::milliseconds(5));
        }
        check(seen[0] && seen[1] && seen[2] && seen[3], "all four channels at native payload limits");
        a.reset(); b.reset();
        check(createAnastacioSteamSocketPair(service, a, b), "fresh session pair");
        ServerConfig sc; sc.gameId = "steam-probe"; sc.gameVersion = 1; sc.sceneName = "Probe"; sc.sceneHash = 42;
        ClientConfig cc; cc.gameId = sc.gameId; cc.gameVersion = 1; cc.playerName = "Probe"; cc.sceneHash = 42;
        {
            ServerSession server(*a, sc); ClientSession client(*b, cc);
            check(server.start(7777), "native server started on SDK adapter");
            check(client.connect("diagnostic", 7777, steadyClockMs()), "native client started on SDK adapter");
            std::vector<SessionEvent> serverEvents, clientEvents; Tick tick = 1;
            start = steadyClockMs();
            while (steadyClockMs() - start < 5000 && client.state() != ClientSession::State::Connected) {
                service.pump(); const auto now = steadyClockMs();
                server.update(now, tick++, serverEvents); client.update(now, clientEvents);
                std::this_thread::sleep_for(std::chrono::milliseconds(5));
            }
            check(client.state() == ClientSession::State::Connected && client.clientId() == 1, "native Hello/Welcome handshake over SDK");
            client.sceneLoaded(42);
            ChatMsg chat; chat.text = "steam native chat"; client.send(Channel::Rpc, makePacket(chat));
            start = steadyClockMs(); bool gotChat = false;
            while (steadyClockMs() - start < 2000) {
                service.pump(); const auto now = steadyClockMs(); server.update(now, tick++, serverEvents); client.update(now, clientEvents);
                for (const auto &event : serverEvents) if (event.type == SessionEvent::Type::Message &&
                    event.messageType == uint8_t(MessageType::Chat)) gotChat = true;
                if (gotChat && server.client(1) && server.client(1)->ready) break;
                std::this_thread::sleep_for(std::chrono::milliseconds(5));
            }
            check(gotChat && server.client(1) && server.client(1)->ready, "scene ready and native chat");

            ProbeWorld sw, cw;
            sw.objects[42].id = 42; sw.objects[42].hasTransform = true;
            sw.objects[42].position[0] = 12.5f; sw.objects[42].props = {PropValue::makeInt(123)};
            cw.objects[42].id = 42;
            ReplicatedObjectDesc desc; desc.props = {{PropKind::Int, 0.0f, 0.0f, 0}};
            Replicator replicator(server, sw);
            check(replicator.addSceneObject(42, desc), "scene object registered");
            ReplicaClientConfig rc;
            rc.schema = [&desc](NetId, const std::string &) { return &desc.props; };
            ReplicaClient replica(client, cw, rc);
            auto advance = [&]() {
                for (int i = 0; i < 80; ++i) {
                    service.pump(); const auto now = steadyClockMs(); serverEvents.clear(); clientEvents.clear();
                    server.update(now, tick, serverEvents);
                    for (const auto &event : serverEvents) replicator.handleEvent(event);
                    replicator.update(tick++, now); client.update(now, clientEvents);
                    for (const auto &event : clientEvents) replica.handleEvent(event, now);
                    replica.applyLatest(); std::this_thread::sleep_for(std::chrono::milliseconds(5));
                }
            };
            advance();
            check(std::abs(cw.objects[42].position[0] - 12.5f) < .01f &&
                !cw.objects[42].props.empty() && cw.objects[42].props[0].i == 123, "transform and integer property replicated through SDK");
            desc.prototype = "ProbeSpawn";
            const NetId spawned = replicator.spawn(desc); check(spawned != 0, "server spawn");
            sw.objects[spawned] = sw.objects[42]; sw.objects[spawned].id = spawned;
            advance(); check(cw.exists(spawned), "client spawn through SDK");
            check(replicator.setOwner(spawned, 1), "server ownership change");
            advance(); check(replica.owner(spawned) == 1, "client ownership through SDK");
            check(replicator.despawn(spawned), "server despawn");
            advance(); check(!cw.exists(spawned), "client despawn through SDK");
            client.disconnect(); server.stop();
        }
        a.reset(); b.reset(); service.unload();
        check(!service.loaded(), "clean SDK shutdown");
        std::cout << "STEAMPROBE PASS (local SDK sockets; Internet/relay not proven)" << std::endl;
        return 0;
    } catch (const std::exception &error) {
        std::cerr << "STEAMPROBE FAIL " << error.what() << std::endl; return 1;
    }
}
