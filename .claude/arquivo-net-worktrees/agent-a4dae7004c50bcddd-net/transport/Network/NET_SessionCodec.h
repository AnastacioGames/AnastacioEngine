/* PROVISIONAL (Frente B): the only encode/decode surface NET_Session needs.
 * Byte layout follows docs/multiplayer-protocol.md sections 4.3 and 5. When
 * NET_Messages (Frente A) lands, this file can forward to it; NET_Session only
 * includes this header. */

#pragma once

#include "NET_Types.h"

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace net {
namespace codec {

struct HelloMsg {
	uint32_t magic = kProtocolMagic;
	uint16_t protocolVersion = kProtocolVersion;
	std::string gameId;
	uint32_t gameVersion = 0;
	uint64_t sceneHash = 0;
	std::string playerName;
	uint64_t token = 0;
};

struct WelcomeMsg {
	ClientId clientId = 0;
	uint16_t tickRate = 0;
	uint16_t snapshotRate = 0;
	uint32_t serverTick = 0;
	uint16_t maxClients = 0;
	std::string sceneName;
};

struct RejectMsg {
	RejectReason reason = RejectReason::VersionMismatch;
	std::string detail;
};

struct DisconnectMsg {
	DisconnectReason reason = DisconnectReason::Quit;
};

struct PingMsg {
	uint32_t seq = 0;
	uint32_t senderTimeMs = 0;
};

struct PongMsg {
	uint32_t seq = 0;
	uint32_t echoTimeMs = 0;
	uint32_t serverTick = 0;
};

/* Appends one message (header of section 4.3 + body). Returns false if the
 * body is larger than a 3-byte varint can describe or a string exceeds 255. */
bool appendMessage(std::vector<uint8_t> &out, MessageType type, const uint8_t *body, size_t size);

bool encode(std::vector<uint8_t> &out, const HelloMsg &);
bool encode(std::vector<uint8_t> &out, const WelcomeMsg &);
bool encode(std::vector<uint8_t> &out, const RejectMsg &);
bool encode(std::vector<uint8_t> &out, const DisconnectMsg &);
bool encode(std::vector<uint8_t> &out, const PingMsg &);
bool encode(std::vector<uint8_t> &out, const PongMsg &);

/* Bodies only (without the header). Return false on invalid/truncated input. */
bool decode(const uint8_t *body, size_t size, HelloMsg &);
bool decode(const uint8_t *body, size_t size, WelcomeMsg &);
bool decode(const uint8_t *body, size_t size, RejectMsg &);
bool decode(const uint8_t *body, size_t size, DisconnectMsg &);
bool decode(const uint8_t *body, size_t size, PingMsg &);
bool decode(const uint8_t *body, size_t size, PongMsg &);

/* Iterates the messages of a packet (section 4.3). */
struct MessageView {
	uint8_t type;
	const uint8_t *body;
	size_t size;
};

class PacketReader {
public:
	PacketReader(const uint8_t *data, size_t size) : m_data(data), m_size(size) {}
	/* Returns false at the end or on a malformed header / len past the end
	 * (then error() is true). */
	bool next(MessageView &out);
	bool error() const
	{
		return m_error;
	}

private:
	const uint8_t *m_data;
	size_t m_size;
	size_t m_pos = 0;
	bool m_error = false;
};

}  // namespace codec
}  // namespace net
