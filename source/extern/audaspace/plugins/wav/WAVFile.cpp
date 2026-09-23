#include "WAVFile.h"

#include "Exception.h"
#include "IReader.h"
#include "file/FileManager.h"
#include "util/Buffer.h"
#include "../mp3/MP3File.h"
#include "../ogg/OGGFile.h"

#include <cstdint>
#include <cstring>
#include <fstream>
#include <vector>

AUD_NAMESPACE_BEGIN

namespace {

uint16_t rd16(const uint8_t *p)
{
	return uint16_t(p[0] | (p[1] << 8));
}

uint32_t rd32(const uint8_t *p)
{
	return uint32_t(p[0]) | (uint32_t(p[1]) << 8) | (uint32_t(p[2]) << 16) | (uint32_t(p[3]) << 24);
}

/** Decodifica o arquivo inteiro para float na abertura; sons de jogo sao curtos e o Audaspace
 *  tambem os coloca em memoria (StacksSound/BufferReader). */
class WAVReader : public IReader
{
public:
	explicit WAVReader(const std::vector<uint8_t> &data)
	{
		if (data.size() < 12 || memcmp(data.data(), "RIFF", 4) != 0 || memcmp(data.data() + 8, "WAVE", 4) != 0) {
			return;  // Not a RIFF/WAVE file (sem excecao: o runtime Web nao tem unwinding)
		}

		uint16_t format = 0, channels = 0, bits = 0;
		uint32_t rate = 0;
		const uint8_t *pcm = nullptr;
		size_t pcm_size = 0;
		bool have_fmt = false;

		size_t pos = 12;
		while (pos + 8 <= data.size()) {
			const uint8_t *chunk = data.data() + pos;
			size_t size = rd32(chunk + 4);
			const uint8_t *body = chunk + 8;
			size_t avail = data.size() - (pos + 8);
			if (size > avail) {
				size = avail;  // cabecalho truncado ou tamanho 0xFFFFFFFF de streaming
			}
			if (memcmp(chunk, "fmt ", 4) == 0 && size >= 16) {
				format = rd16(body);
				channels = rd16(body + 2);
				rate = rd32(body + 4);
				bits = rd16(body + 14);
				if (format == 0xFFFE && size >= 26) {
					format = rd16(body + 24);  // SubFormat GUID: primeiros 2 bytes
				}
				have_fmt = true;
			}
			else if (memcmp(chunk, "data", 4) == 0) {
				pcm = body;
				pcm_size = size;
			}
			pos += 8 + size + (size & 1);
		}

		if (!have_fmt || !pcm) {
			return;  // WAV file without fmt or data chunk (sem excecao: o runtime Web nao tem unwinding)
		}
		if (channels < 1 || channels > 8 || rate == 0) {
			return;  // Unsupported WAV channel count or sample rate (sem excecao: o runtime Web nao tem unwinding)
		}
		const bool is_float = (format == 3);
		if (!((format == 1 && (bits == 8 || bits == 16 || bits == 24 || bits == 32)) ||
		      (is_float && (bits == 32 || bits == 64))))
		{
			return;  // Unsupported WAV sample format (only PCM 8/16/24/32 and float 32/64) (sem excecao: o runtime Web nao tem unwinding)
		}

		const size_t bytes = bits / 8;
		const size_t total = pcm_size / bytes;
		m_length = int(total / channels);
		m_samples.resize(size_t(m_length) * channels);

		for (size_t i = 0; i < m_samples.size(); i++) {
			const uint8_t *s = pcm + i * bytes;
			float v;
			if (is_float) {
				if (bits == 32) {
					float f;
					memcpy(&f, s, 4);
					v = f;
				}
				else {
					double d;
					memcpy(&d, s, 8);
					v = float(d);
				}
			}
			else if (bits == 8) {
				v = (int(s[0]) - 128) / 128.0f;
			}
			else if (bits == 16) {
				v = int16_t(rd16(s)) / 32768.0f;
			}
			else if (bits == 24) {
				int32_t x = int32_t(uint32_t(s[0]) << 8 | uint32_t(s[1]) << 16 | uint32_t(s[2]) << 24) >> 8;
				v = x / 8388608.0f;
			}
			else {
				v = int32_t(rd32(s)) / 2147483648.0f;
			}
			m_samples[i] = v;
		}

		m_specs.rate = rate;
		m_specs.channels = Channels(channels);
		m_ok = true;
	}

	/** false quando o cabecalho e invalido; o construtor nao lanca (Wasm sem excecoes). */
	bool ok() const { return m_ok; }

	virtual bool isSeekable() const { return true; }

	virtual void seek(int position)
	{
		if (position < 0) {
			position = 0;
		}
		m_position = position > m_length ? m_length : position;
	}

	virtual int getLength() const { return m_length; }
	virtual int getPosition() const { return m_position; }
	virtual Specs getSpecs() const { return m_specs; }

	virtual void read(int &length, bool &eos, sample_t *buffer)
	{
		int left = m_length - m_position;
		int n = length < left ? length : left;
		if (n < 0) {
			n = 0;
		}
		if (n > 0) {
			memcpy(buffer, m_samples.data() + size_t(m_position) * m_specs.channels, size_t(n) * m_specs.channels * sizeof(sample_t));
		}
		m_position += n;
		eos = n < length;
		length = n;
	}

private:
	bool m_ok = false;
	std::vector<float> m_samples;
	int m_length = 0;
	int m_position = 0;
	Specs m_specs;
};

}  // namespace

WAVFile::WAVFile()
{
}

void WAVFile::registerPlugin()
{
	FileManager::registerInput(std::shared_ptr<WAVFile>(new WAVFile));
}

/** Dado que nao e RIFF/WAVE: tenta OGG ("OggS") e MP3 sem lancar (Emscripten sem excecoes); so lanca se nada servir. */
static std::shared_ptr<IReader> makeReader(std::vector<uint8_t> data)
{
	if (data.size() >= 12 && memcmp(data.data(), "RIFF", 4) == 0 && memcmp(data.data() + 8, "WAVE", 4) == 0) {
		std::shared_ptr<WAVReader> wav(new WAVReader(data));
		return wav->ok() ? std::shared_ptr<IReader>(wav) : std::shared_ptr<IReader>();
	}
	std::shared_ptr<IReader> decoded;
	if (data.size() >= 4 && memcmp(data.data(), "OggS", 4) == 0) {
		decoded = createOGGReader(std::move(data));
	}
	else {
		decoded = createMP3Reader(std::move(data));
	}
	if (!decoded) {
		/* The browser build has no C++ exception unwinder.  Report an
		 * unsupported codec as a failed reader instead of aborting Wasm. */
		return nullptr;
	}
	return decoded;
}

std::shared_ptr<IReader> WAVFile::createReader(std::string filename)
{
	std::ifstream in(filename, std::ios::binary);
	if (!in) {
		return nullptr;
	}
	std::vector<uint8_t> data((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
	return makeReader(std::move(data));
}

std::shared_ptr<IReader> WAVFile::createReader(std::shared_ptr<Buffer> buffer)
{
	const uint8_t *p = reinterpret_cast<const uint8_t *>(buffer->getBuffer());
	std::vector<uint8_t> data(p, p + buffer->getSize());
	return makeReader(std::move(data));
}

AUD_NAMESPACE_END
