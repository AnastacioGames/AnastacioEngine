#include "MP3File.h"

#include "IReader.h"

#define DR_MP3_IMPLEMENTATION
#define DR_MP3_NO_STDIO
#include "dr_mp3.h"

#include <cstdint>
#include <memory>
#include <vector>

AUD_NAMESPACE_BEGIN

namespace {

class MP3Reader : public IReader
{
public:
	explicit MP3Reader(std::vector<uint8_t> data) : m_data(std::move(data)) {}

	/** false se nao for um MP3 suportado; nao lanca (o Emscripten roda sem excecoes). */
	bool init()
	{
		if (m_data.empty() || !drmp3_init_memory(&m_mp3, m_data.data(), m_data.size(), nullptr)) {
			return false;
		}
		m_open = true;
		if (m_mp3.channels < 1 || m_mp3.channels > 2 || m_mp3.sampleRate == 0) {
			return false;
		}
		m_specs.rate = SampleRate(m_mp3.sampleRate);
		m_specs.channels = Channels(m_mp3.channels);
		m_length = int(drmp3_get_pcm_frame_count(&m_mp3));
		drmp3_seek_to_pcm_frame(&m_mp3, 0);
		return true;
	}

	~MP3Reader()
	{
		if (m_open) {
			drmp3_uninit(&m_mp3);
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
		if (drmp3_seek_to_pcm_frame(&m_mp3, drmp3_uint64(position))) {
			m_position = position;
		}
	}

	virtual int getLength() const { return m_length; }
	virtual int getPosition() const { return m_position; }
	virtual Specs getSpecs() const { return m_specs; }

	virtual void read(int &length, bool &eos, sample_t *buffer)
	{
		int want = length;
		if (want < 0) {
			want = 0;
		}
		int got = int(drmp3_read_pcm_frames_f32(&m_mp3, drmp3_uint64(want), buffer));
		m_position += got;
		eos = got < want;
		length = got;
	}

private:
	std::vector<uint8_t> m_data;
	drmp3 m_mp3;
	bool m_open = false;
	int m_length = 0;
	int m_position = 0;
	Specs m_specs;
};

}  // namespace

std::shared_ptr<IReader> createMP3Reader(std::vector<uint8_t> data)
{
	std::shared_ptr<MP3Reader> reader(new MP3Reader(std::move(data)));
	if (!reader->init()) {
		return nullptr;
	}
	return reader;
}

AUD_NAMESPACE_END
