/*******************************************************************************
 * Anastacio Engine: captura de microfone por OpenAL (desktop).
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

#include "OpenALMicrophone.h"
#include "devices/Microphone.h"
#include "Exception.h"

#include <al.h>
#include <alc.h>

#include <cstdint>
#include <cstring>
#include <vector>

AUD_NAMESPACE_BEGIN

namespace {

class OpenALMicrophoneBackend : public IMicrophoneBackend
{
	ALCdevice* m_device;
	Specs m_specs;
	int m_capacity;
	std::vector<int16_t> m_temp;

public:
	OpenALMicrophoneBackend(const std::string& name, Specs specs, int capacity) :
		m_device(nullptr), m_specs(specs), m_capacity(capacity)
	{
		if(m_specs.channels != CHANNELS_STEREO)
			m_specs.channels = CHANNELS_MONO;

		/* Buffer do OpenAL do tamanho da fila (~2 s): aguenta travadas e carregamentos. */
		m_device = alcCaptureOpenDevice(name.empty() ? nullptr : name.c_str(), ALCuint(m_specs.rate),
		                                m_specs.channels == CHANNELS_MONO ? AL_FORMAT_MONO16 : AL_FORMAT_STEREO16,
		                                ALCsizei(m_capacity));
		if(!m_device)
			AUD_THROW(DeviceException, "The microphone couldn't be opened with OpenAL.");

		alcCaptureStart(m_device);
	}

	~OpenALMicrophoneBackend()
	{
		if(m_device)
		{
			alcCaptureStop(m_device);
			alcCaptureCloseDevice(m_device);
		}
	}

	Specs getSpecs() const override { return m_specs; }

	MicrophoneState getState() const override
	{
		return m_device ? MICROPHONE_STATE_GRANTED : MICROPHONE_STATE_ERROR;
	}

	int capacity() const override { return m_capacity; }

	int available() override
	{
		ALCint frames = 0;
		alcGetIntegerv(m_device, ALC_CAPTURE_SAMPLES, 1, &frames);
		return frames;
	}

	void read(int frames, sample_t* buffer) override
	{
		const int count = frames * m_specs.channels;
		m_temp.resize(count);
		alcCaptureSamples(m_device, m_temp.data(), frames);
		for(int i = 0; i < count; i++)
			buffer[i] = m_temp[i] / 32768.0f;
	}
};

} // namespace

int OpenALMicrophone::getPriority()
{
	return 10;
}

std::vector<std::string> OpenALMicrophone::getDeviceNames()
{
	std::vector<std::string> names;
	/* Lista separada por '\0', terminada por "\0\0". */
	const ALCchar* list = alcGetString(nullptr, ALC_CAPTURE_DEVICE_SPECIFIER);
	while(list && *list)
	{
		names.push_back(list);
		list += std::strlen(list) + 1;
	}
	return names;
}

std::shared_ptr<IMicrophoneBackend> OpenALMicrophone::open(const std::string& device, Specs specs, int capacity_frames)
{
	return std::make_shared<OpenALMicrophoneBackend>(device, specs, capacity_frames);
}

void OpenALMicrophone::registerPlugin()
{
	Microphone::registerBackend("OpenAL", std::make_shared<OpenALMicrophone>());
}

AUD_NAMESPACE_END
