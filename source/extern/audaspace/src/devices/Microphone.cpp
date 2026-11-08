/*******************************************************************************
 * Anastacio Engine: captura de microfone.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 ******************************************************************************/

#include "devices/Microphone.h"
#include "Exception.h"
#include "IReader.h"
#include "ISound.h"
#include "util/Buffer.h"
#include "util/StreamBuffer.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>

AUD_NAMESPACE_BEGIN

/* Gravacao para de crescer em 10 minutos para nao esgotar a memoria. */
static const float MAX_RECORDING_SECONDS = 600.0f;

/* Leitor ao vivo mais atrasado que isto pula para perto do fim (latencia baixa). */
static const float LIVE_MAX_LAG_SECONDS = 0.25f;
static const float LIVE_TARGET_LAG_SECONDS = 0.05f;

// ---------------------------------------------------------------------------
// Backend de teste: seno de 440 Hz no ritmo do relogio, para testes sem microfone.

namespace {

class TestMicrophoneBackend : public IMicrophoneBackend
{
	Specs m_specs;
	int m_capacity;
	std::chrono::steady_clock::time_point m_start;
	uint64_t m_produced;

	uint64_t elapsedFrames() const
	{
		double s = std::chrono::duration<double>(std::chrono::steady_clock::now() - m_start).count();
		return uint64_t(s * m_specs.rate);
	}

public:
	TestMicrophoneBackend(Specs specs, int capacity) :
		m_specs(specs), m_capacity(capacity), m_start(std::chrono::steady_clock::now()), m_produced(0)
	{
	}

	Specs getSpecs() const override { return m_specs; }
	MicrophoneState getState() const override { return MICROPHONE_STATE_GRANTED; }
	int capacity() const override { return m_capacity; }

	int available() override
	{
		uint64_t total = elapsedFrames();
		/* Ninguem leu a tempo: descarta o excesso, como uma placa de som real. */
		if(total - m_produced > uint64_t(m_capacity))
			m_produced = total - m_capacity;
		return int(total - m_produced);
	}

	void read(int frames, sample_t* buffer) override
	{
		const int channels = m_specs.channels;
		for(int i = 0; i < frames; i++)
		{
			double t = double(m_produced + i) / m_specs.rate;
			sample_t v = sample_t(0.5 * std::sin(6.283185307179586 * 440.0 * t));
			for(int c = 0; c < channels; c++)
				buffer[i * channels + c] = v;
		}
		m_produced += frames;
	}
};

class TestMicrophoneFactory : public IMicrophoneBackendFactory
{
public:
	/* Negativa: nunca e escolhida sozinha, so pelo nome "Test". */
	int getPriority() override { return -1; }
	std::vector<std::string> getDeviceNames() override { return {"Sine 440 Hz"}; }
	std::shared_ptr<IMicrophoneBackend> open(const std::string&, Specs specs, int capacity_frames) override
	{
		return std::make_shared<TestMicrophoneBackend>(specs, capacity_frames);
	}
};

// ---------------------------------------------------------------------------
// Som ao vivo: cada leitor tem seu cursor na fila do Microphone.

class MicrophoneLiveReader : public IReader
{
	std::shared_ptr<Microphone> m_mic;
	Specs m_specs;
	uint64_t m_cursor;
	int m_position;

public:
	MicrophoneLiveReader(std::shared_ptr<Microphone> mic) :
		m_mic(mic), m_specs(mic->getSpecs()), m_cursor(mic->liveStartPosition()), m_position(0)
	{
	}

	bool isSeekable() const override { return false; }
	void seek(int) override {}
	int getLength() const override { return -1; }
	int getPosition() const override { return m_position; }
	Specs getSpecs() const override { return m_specs; }

	void read(int& length, bool& eos, sample_t* buffer) override
	{
		int got = m_mic->readFrom(m_cursor, length, buffer);
		if(got < length)
		{
			m_mic->poll();
			got += m_mic->readFrom(m_cursor, length - got, buffer + got * m_specs.channels);
		}
		if(got < length)
			std::memset(buffer + got * m_specs.channels, 0, (length - got) * m_specs.channels * sizeof(sample_t));
		m_position += length;
		eos = false;
	}
};

class MicrophoneLiveSound : public ISound
{
	std::shared_ptr<Microphone> m_mic;

public:
	MicrophoneLiveSound(std::shared_ptr<Microphone> mic) : m_mic(mic) {}

	std::shared_ptr<IReader> createReader() override
	{
		return std::make_shared<MicrophoneLiveReader>(m_mic);
	}
};

} // namespace

// ---------------------------------------------------------------------------
// Registro de backends.

std::map<std::string, std::shared_ptr<IMicrophoneBackendFactory>>& Microphone::registry()
{
	static std::map<std::string, std::shared_ptr<IMicrophoneBackendFactory>> factories = {
		{"Test", std::make_shared<TestMicrophoneFactory>()}
	};
	return factories;
}

void Microphone::registerBackend(const std::string& name, std::shared_ptr<IMicrophoneBackendFactory> factory)
{
	registry()[name] = factory;
}

std::vector<std::string> Microphone::getBackendNames()
{
	std::vector<std::string> names;
	for(auto& entry : registry())
		names.push_back(entry.first);
	return names;
}

static std::shared_ptr<IMicrophoneBackendFactory> findFactory(
	std::map<std::string, std::shared_ptr<IMicrophoneBackendFactory>>& factories,
	const std::string& backend, std::string& found_name)
{
	if(!backend.empty())
	{
		auto it = factories.find(backend);
		if(it == factories.end())
			return nullptr;
		found_name = it->first;
		return it->second;
	}

	std::shared_ptr<IMicrophoneBackendFactory> best;
	for(auto& entry : factories)
	{
		int priority = entry.second->getPriority();
		if(priority < 0)
			continue;
		if(!best || priority > best->getPriority())
		{
			best = entry.second;
			found_name = entry.first;
		}
	}
	return best;
}

std::vector<std::string> Microphone::getDeviceNames(const std::string& backend)
{
	std::string name;
	auto factory = findFactory(registry(), backend, name);
	if(!factory)
		return {};
	return factory->getDeviceNames();
}

// ---------------------------------------------------------------------------

Microphone::Microphone(const std::string& device, Specs specs, const std::string& backend, float seconds) :
	m_device(device), m_backend_name(backend), m_requested(specs), m_specs(specs),
	m_seconds(std::max(seconds, 0.25f)), m_state(MICROPHONE_STATE_CLOSED),
	m_ring_frames(0), m_written(0), m_level(0), m_peak(0), m_dropped(0), m_recording(false)
{
	if(m_requested.channels != CHANNELS_STEREO)
		m_requested.channels = CHANNELS_MONO;
	if(m_requested.rate <= 0)
		m_requested.rate = RATE_22050;
	m_specs = m_requested;
	m_last_recording_specs = m_requested;
}

Microphone::~Microphone()
{
	stop();
}

bool Microphone::start()
{
	std::lock_guard<std::recursive_mutex> lock(m_mutex);

	if(m_backend)
		return true;

	std::string name;
	auto factory = findFactory(registry(), m_backend_name, name);
	if(!factory)
	{
		m_state = MICROPHONE_STATE_ERROR;
		m_error = m_backend_name.empty() ? "No microphone backend available" :
		                                   "Unknown microphone backend: " + m_backend_name;
		return false;
	}

	int capacity = int(m_requested.rate * m_seconds);
	try
	{
		m_backend = factory->open(m_device, m_requested, capacity);
	}
	catch(Exception& e)
	{
		m_backend.reset();
		m_state = MICROPHONE_STATE_ERROR;
		m_error = e.getMessage();
		return false;
	}

	m_backend_name = name;
	m_specs = m_backend->getSpecs();
	m_state = m_backend->getState();
	m_error.clear();

	int frames = std::max(int(m_specs.rate * m_seconds), 1024);
	if(frames != m_ring_frames || m_ring.size() != size_t(frames * m_specs.channels))
	{
		m_ring_frames = frames;
		m_ring.assign(size_t(frames) * m_specs.channels, 0);
	}
	return true;
}

void Microphone::stop()
{
	std::lock_guard<std::recursive_mutex> lock(m_mutex);
	m_backend.reset();
	m_state = MICROPHONE_STATE_CLOSED;
	m_level = 0;
}

bool Microphone::isActive() const
{
	std::lock_guard<std::recursive_mutex> lock(m_mutex);
	return m_backend != nullptr;
}

void Microphone::poll()
{
	std::lock_guard<std::recursive_mutex> lock(m_mutex);
	pollLocked();
}

void Microphone::pollLocked()
{
	if(!m_backend)
		return;

	m_state = m_backend->getState();
	if(m_state != MICROPHONE_STATE_GRANTED)
		return;

	int avail = m_backend->available();
	if(avail <= 0)
		return;
	if(avail >= m_backend->capacity())
		m_dropped++;

	const int channels = m_specs.channels;
	const size_t max_record = size_t(MAX_RECORDING_SECONDS * m_specs.rate) * channels;
	double sum = 0;
	float block_peak = 0;
	int total = 0;

	while(avail > 0)
	{
		int frames = std::min(avail, std::min(m_ring_frames, 4096));
		m_temp.resize(size_t(frames) * channels);
		m_backend->read(frames, m_temp.data());

		for(int i = 0; i < frames * channels; i++)
		{
			float v = m_temp[i];
			sum += double(v) * v;
			block_peak = std::max(block_peak, std::fabs(v));
		}

		for(int i = 0; i < frames; i++)
		{
			size_t slot = size_t((m_written + i) % uint64_t(m_ring_frames)) * channels;
			std::memcpy(&m_ring[slot], &m_temp[size_t(i) * channels], channels * sizeof(sample_t));
		}
		m_written += frames;

		if(m_recording && m_record.size() < max_record)
		{
			size_t n = std::min(m_temp.size(), max_record - m_record.size());
			m_record.insert(m_record.end(), m_temp.begin(), m_temp.begin() + n);
		}

		avail -= frames;
		total += frames;
	}

	m_level = std::min(1.0f, float(std::sqrt(sum / (double(total) * channels))));
	float decay = float(std::exp(-double(total) / m_specs.rate * 3.0));
	m_peak = std::min(1.0f, std::max(block_peak, m_peak * decay));
}

MicrophoneState Microphone::getState() const
{
	std::lock_guard<std::recursive_mutex> lock(m_mutex);
	return m_state;
}

std::string Microphone::getError() const
{
	std::lock_guard<std::recursive_mutex> lock(m_mutex);
	return m_error;
}

std::string Microphone::getBackendName() const
{
	std::lock_guard<std::recursive_mutex> lock(m_mutex);
	return m_backend_name;
}

Specs Microphone::getSpecs() const
{
	std::lock_guard<std::recursive_mutex> lock(m_mutex);
	return m_specs;
}

float Microphone::getLevel() const
{
	std::lock_guard<std::recursive_mutex> lock(m_mutex);
	return m_level;
}

float Microphone::getPeak() const
{
	std::lock_guard<std::recursive_mutex> lock(m_mutex);
	return m_peak;
}

int Microphone::getDropped() const
{
	std::lock_guard<std::recursive_mutex> lock(m_mutex);
	return m_dropped;
}

void Microphone::startRecording()
{
	std::lock_guard<std::recursive_mutex> lock(m_mutex);
	/* Descarta o que estava esperando no backend: a gravacao comeca agora. */
	pollLocked();
	m_record.clear();
	m_recording = true;
}

std::shared_ptr<ISound> Microphone::stopRecording()
{
	std::lock_guard<std::recursive_mutex> lock(m_mutex);
	pollLocked();
	m_recording = false;

	auto buffer = std::make_shared<Buffer>(int(m_record.size() * sizeof(sample_t)));
	if(!m_record.empty())
		std::memcpy(buffer->getBuffer(), m_record.data(), m_record.size() * sizeof(sample_t));
	m_record.clear();
	m_record.shrink_to_fit();

	m_last_recording_specs = m_specs;
	m_last_recording = std::make_shared<StreamBuffer>(buffer, m_specs);
	return m_last_recording;
}

bool Microphone::isRecording() const
{
	std::lock_guard<std::recursive_mutex> lock(m_mutex);
	return m_recording;
}

float Microphone::getRecordingSeconds() const
{
	std::lock_guard<std::recursive_mutex> lock(m_mutex);
	return float(m_record.size() / m_specs.channels) / float(m_specs.rate);
}

std::shared_ptr<ISound> Microphone::getLastRecording() const
{
	std::lock_guard<std::recursive_mutex> lock(m_mutex);
	return m_last_recording;
}

std::shared_ptr<ISound> Microphone::createLiveSound()
{
	return std::make_shared<MicrophoneLiveSound>(shared_from_this());
}

uint64_t Microphone::liveStartPosition()
{
	std::lock_guard<std::recursive_mutex> lock(m_mutex);
	return m_written;
}

int Microphone::readFrom(uint64_t& cursor, int frames, sample_t* buffer)
{
	std::lock_guard<std::recursive_mutex> lock(m_mutex);

	if(m_ring_frames <= 0 || frames <= 0)
		return 0;

	if(cursor > m_written)
		cursor = m_written;

	uint64_t lag = m_written - cursor;
	if(lag > uint64_t(m_ring_frames))
	{
		/* Leitor perdeu dados que ja foram sobrescritos. */
		m_dropped++;
		lag = uint64_t(LIVE_TARGET_LAG_SECONDS * m_specs.rate);
		cursor = m_written - std::min<uint64_t>(lag, m_written);
	}
	else if(lag > uint64_t(LIVE_MAX_LAG_SECONDS * m_specs.rate))
	{
		/* Atraso acumulado (silencios inseridos): volta para perto do fim. */
		lag = uint64_t(LIVE_TARGET_LAG_SECONDS * m_specs.rate);
		cursor = m_written - lag;
	}

	const int channels = m_specs.channels;
	int count = int(std::min<uint64_t>(uint64_t(frames), m_written - cursor));
	for(int i = 0; i < count; i++)
	{
		size_t slot = size_t((cursor + i) % uint64_t(m_ring_frames)) * channels;
		std::memcpy(buffer + size_t(i) * channels, &m_ring[slot], channels * sizeof(sample_t));
	}
	cursor += count;
	return count;
}

void Microphone::saveWAV(const std::string& path) const
{
	std::shared_ptr<StreamBuffer> sound;
	Specs specs;
	{
		std::lock_guard<std::recursive_mutex> lock(m_mutex);
		sound = std::static_pointer_cast<StreamBuffer>(m_last_recording);
		specs = m_last_recording_specs;
	}
	if(!sound)
		AUD_THROW(StateException, "Nothing was recorded yet.");

	auto buffer = sound->getBuffer();
	int frames = buffer->getSize() / int(sizeof(sample_t) * specs.channels);
	writeWAV(path, buffer->getBuffer(), frames, specs);
}

static void put_u32(unsigned char* p, uint32_t v)
{
	p[0] = v & 0xff; p[1] = (v >> 8) & 0xff; p[2] = (v >> 16) & 0xff; p[3] = (v >> 24) & 0xff;
}

static void put_u16(unsigned char* p, uint16_t v)
{
	p[0] = v & 0xff; p[1] = (v >> 8) & 0xff;
}

void Microphone::writeWAV(const std::string& path, const sample_t* data, int frames, Specs specs)
{
	const int channels = specs.channels;
	const uint32_t rate = uint32_t(specs.rate);
	const uint32_t data_bytes = uint32_t(frames) * channels * 2;

	unsigned char header[44];
	std::memcpy(header, "RIFF", 4);
	put_u32(header + 4, 36 + data_bytes);
	std::memcpy(header + 8, "WAVEfmt ", 8);
	put_u32(header + 16, 16);
	put_u16(header + 20, 1);                      /* PCM */
	put_u16(header + 22, uint16_t(channels));
	put_u32(header + 24, rate);
	put_u32(header + 28, rate * channels * 2);    /* bytes por segundo */
	put_u16(header + 32, uint16_t(channels * 2)); /* bytes por frame */
	put_u16(header + 34, 16);
	std::memcpy(header + 36, "data", 4);
	put_u32(header + 40, data_bytes);

	FILE* file = std::fopen(path.c_str(), "wb");
	if(!file)
		AUD_THROW(FileException, "The WAV file couldn't be opened for writing.");

	bool ok = std::fwrite(header, 1, sizeof(header), file) == sizeof(header);

	std::vector<unsigned char> block;
	const int chunk = 4096 * channels;
	const int total = frames * channels;
	for(int start = 0; ok && start < total; start += chunk)
	{
		int n = std::min(chunk, total - start);
		block.resize(size_t(n) * 2);
		for(int i = 0; i < n; i++)
		{
			float v = std::max(-1.0f, std::min(1.0f, data[start + i]));
			int16_t s = int16_t(std::lround(v * 32767.0f));
			put_u16(&block[size_t(i) * 2], uint16_t(s));
		}
		ok = std::fwrite(block.data(), 1, block.size(), file) == block.size();
	}

	if(std::fclose(file) != 0)
		ok = false;
	if(!ok)
		AUD_THROW(FileException, "The WAV file couldn't be written.");
}

AUD_NAMESPACE_END
