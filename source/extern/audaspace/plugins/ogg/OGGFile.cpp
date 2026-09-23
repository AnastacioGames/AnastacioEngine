#include "OGGFile.h"

#include "IReader.h"

#define STB_VORBIS_NO_STDIO
#define STB_VORBIS_NO_PUSHDATA_API
#include "stb_vorbis.c"

#include <cstdint>
#include <memory>
#include <vector>

AUD_NAMESPACE_BEGIN

namespace {

class OGGReader : public IReader
{
public:
	explicit OGGReader(std::vector<uint8_t> data) : m_data(std::move(data)) {}

	/** false se nao for Ogg Vorbis suportado; nao lanca (o Emscripten roda sem excecoes). */
	bool init()
	{
		int error = 0;
		m_vorbis = stb_vorbis_open_memory(m_data.data(), int(m_data.size()), &error, nullptr);
		if (!m_vorbis) {
			return false;
		}
		stb_vorbis_info info = stb_vorbis_get_info(m_vorbis);
		if (info.channels < 1 || info.channels > 2 || info.sample_rate == 0) {
			return false;
		}
		m_specs.rate = SampleRate(info.sample_rate);
		m_specs.channels = Channels(info.channels);
		m_length = int(stb_vorbis_stream_length_in_samples(m_vorbis));
		return true;
	}

	~OGGReader()
	{
		if (m_vorbis) {
			stb_vorbis_close(m_vorbis);
		}
	}

	virtual bool isSeekable() const { return true; }

	virtual void seek(int position)
	{
		if (position < 0) {
			position = 0;
		}
		if (position > m_length) {
			position = m_length;
		}
		if (position == 0) {
			stb_vorbis_seek_start(m_vorbis);
			m_position = 0;
		}
		else if (stb_vorbis_seek(m_vorbis, (unsigned int)position)) {
			m_position = position;
		}
	}

	virtual int getLength() const { return m_length; }
	virtual int getPosition() const { return m_position; }
	virtual Specs getSpecs() const { return m_specs; }

	virtual void read(int &length, bool &eos, sample_t *buffer)
	{
		int want = length < 0 ? 0 : length;
		int channels = int(m_specs.channels);
		int got = 0;
		while (got < want) {
			int n = stb_vorbis_get_samples_float_interleaved(m_vorbis, channels, buffer + got * channels, (want - got) * channels);
			if (n <= 0) {
				break;
			}
			got += n;
		}
		m_position += got;
		eos = got < want;
		length = got;
	}

private:
	std::vector<uint8_t> m_data;
	stb_vorbis *m_vorbis = nullptr;
	int m_length = 0;
	int m_position = 0;
	Specs m_specs;
};

}  // namespace

std::shared_ptr<IReader> createOGGReader(std::vector<uint8_t> data)
{
	std::shared_ptr<OGGReader> reader(new OGGReader(std::move(data)));
	if (!reader->init()) {
		return nullptr;
	}
	return reader;
}

AUD_NAMESPACE_END
