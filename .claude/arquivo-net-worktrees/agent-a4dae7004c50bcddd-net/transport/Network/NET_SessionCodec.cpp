/* PROVISIONAL (Frente B): see NET_SessionCodec.h. */

#include "NET_SessionCodec.h"

namespace net {
namespace codec {

namespace {

constexpr size_t kMaxVarLen = (size_t(1) << 21) - 1; /* 3-byte LEB128 */

class Writer {
public:
	void u8(uint8_t v)
	{
		buf.push_back(v);
	}
	void u16(uint16_t v)
	{
		for (int i = 0; i < 2; i++) {
			buf.push_back(uint8_t(v >> (8 * i)));
		}
	}
	void u32(uint32_t v)
	{
		for (int i = 0; i < 4; i++) {
			buf.push_back(uint8_t(v >> (8 * i)));
		}
	}
	void u64(uint64_t v)
	{
		for (int i = 0; i < 8; i++) {
			buf.push_back(uint8_t(v >> (8 * i)));
		}
	}
	void varu(uint64_t v)
	{
		do {
			uint8_t b = uint8_t(v & 0x7f);
			v >>= 7;
			buf.push_back(v ? uint8_t(b | 0x80) : b);
		} while (v);
	}
	void str(const std::string &s)
	{
		if (s.size() > 255) {
			ok = false;
			return;
		}
		varu(s.size());
		buf.insert(buf.end(), s.begin(), s.end());
	}
	std::vector<uint8_t> buf;
	bool ok = true;
};

class Reader {
public:
	Reader(const uint8_t *d, size_t s) : data(d), size(s) {}
	bool has(size_t n)
	{
		if (!ok || size - pos < n) {
			ok = false;
			return false;
		}
		return true;
	}
	uint64_t le(int bytes)
	{
		if (!has(size_t(bytes))) {
			return 0;
		}
		uint64_t v = 0;
		for (int i = 0; i < bytes; i++) {
			v |= uint64_t(data[pos++]) << (8 * i);
		}
		return v;
	}
	uint8_t u8()
	{
		return uint8_t(le(1));
	}
	uint16_t u16()
	{
		return uint16_t(le(2));
	}
	uint32_t u32()
	{
		return uint32_t(le(4));
	}
	uint64_t u64()
	{
		return le(8);
	}
	uint64_t varu(int maxBytes = 10)
	{
		uint64_t v = 0;
		for (int i = 0; i < maxBytes; i++) {
			if (!has(1)) {
				return 0;
			}
			const uint8_t b = data[pos++];
			v |= uint64_t(b & 0x7f) << (7 * i);
			if (!(b & 0x80)) {
				return v;
			}
		}
		ok = false;
		return 0;
	}
	void str(std::string &out)
	{
		const uint64_t n = varu();
		if (n > 255 || !has(size_t(n))) {
			ok = false;
			return;
		}
		out.assign(reinterpret_cast<const char *>(data + pos), size_t(n));
		pos += size_t(n);
	}
	/* Strict: the whole body must be consumed. */
	bool done() const
	{
		return ok && pos == size;
	}
	const uint8_t *data;
	size_t size;
	size_t pos = 0;
	bool ok = true;
};

bool finish(std::vector<uint8_t> &out, MessageType type, const Writer &w)
{
	return w.ok && appendMessage(out, type, w.buf.data(), w.buf.size());
}

}  // namespace

bool appendMessage(std::vector<uint8_t> &out, MessageType type, const uint8_t *body, size_t size)
{
	if (size > kMaxVarLen) {
		return false;
	}
	Writer w;
	w.u8(uint8_t(type));
	w.varu(size);
	out.insert(out.end(), w.buf.begin(), w.buf.end());
	if (size) {
		out.insert(out.end(), body, body + size);
	}
	return true;
}

bool encode(std::vector<uint8_t> &out, const HelloMsg &m)
{
	Writer w;
	w.u32(m.magic);
	w.u16(m.protocolVersion);
	w.str(m.gameId);
	w.u32(m.gameVersion);
	w.u64(m.sceneHash);
	w.str(m.playerName);
	w.u64(m.token);
	return finish(out, MessageType::Hello, w);
}

bool encode(std::vector<uint8_t> &out, const WelcomeMsg &m)
{
	Writer w;
	w.u16(m.clientId);
	w.u16(m.tickRate);
	w.u16(m.snapshotRate);
	w.u32(m.serverTick);
	w.u16(m.maxClients);
	w.str(m.sceneName);
	return finish(out, MessageType::Welcome, w);
}

bool encode(std::vector<uint8_t> &out, const RejectMsg &m)
{
	Writer w;
	w.u8(uint8_t(m.reason));
	w.str(m.detail);
	return finish(out, MessageType::Reject, w);
}

bool encode(std::vector<uint8_t> &out, const DisconnectMsg &m)
{
	Writer w;
	w.u8(uint8_t(m.reason));
	return finish(out, MessageType::Disconnect, w);
}

bool encode(std::vector<uint8_t> &out, const PingMsg &m)
{
	Writer w;
	w.u32(m.seq);
	w.u32(m.senderTimeMs);
	return finish(out, MessageType::Ping, w);
}

bool encode(std::vector<uint8_t> &out, const PongMsg &m)
{
	Writer w;
	w.u32(m.seq);
	w.u32(m.echoTimeMs);
	w.u32(m.serverTick);
	return finish(out, MessageType::Pong, w);
}

bool decode(const uint8_t *body, size_t size, HelloMsg &m)
{
	Reader r(body, size);
	m.magic = r.u32();
	m.protocolVersion = r.u16();
	r.str(m.gameId);
	m.gameVersion = r.u32();
	m.sceneHash = r.u64();
	r.str(m.playerName);
	m.token = r.u64();
	return r.done();
}

bool decode(const uint8_t *body, size_t size, WelcomeMsg &m)
{
	Reader r(body, size);
	m.clientId = r.u16();
	m.tickRate = r.u16();
	m.snapshotRate = r.u16();
	m.serverTick = r.u32();
	m.maxClients = r.u16();
	r.str(m.sceneName);
	return r.done();
}

bool decode(const uint8_t *body, size_t size, RejectMsg &m)
{
	Reader r(body, size);
	m.reason = RejectReason(r.u8());
	r.str(m.detail);
	return r.done();
}

bool decode(const uint8_t *body, size_t size, DisconnectMsg &m)
{
	Reader r(body, size);
	m.reason = DisconnectReason(r.u8());
	return r.done();
}

bool decode(const uint8_t *body, size_t size, PingMsg &m)
{
	Reader r(body, size);
	m.seq = r.u32();
	m.senderTimeMs = r.u32();
	return r.done();
}

bool decode(const uint8_t *body, size_t size, PongMsg &m)
{
	Reader r(body, size);
	m.seq = r.u32();
	m.echoTimeMs = r.u32();
	m.serverTick = r.u32();
	return r.done();
}

bool PacketReader::next(MessageView &out)
{
	if (m_error || m_pos >= m_size) {
		return false;
	}
	Reader r(m_data + m_pos, m_size - m_pos);
	const uint8_t type = r.u8();
	const uint64_t len = r.varu(3);
	if (!r.ok || len > r.size - r.pos) {
		m_error = true;
		return false;
	}
	out.type = type;
	out.body = r.data + r.pos;
	out.size = size_t(len);
	m_pos += r.pos + size_t(len);
	return true;
}

}  // namespace codec
}  // namespace net
