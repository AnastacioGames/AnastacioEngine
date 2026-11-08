/*******************************************************************************
 * Anastacio Engine: API C do microfone e dos efeitos de voz.
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

#define AUD_CAPI_IMPLEMENTATION
#include "AUD_Microphone.h"

#include "Exception.h"
#include "devices/Microphone.h"
#include "fx/VoiceFX.h"

#include <algorithm>
#include <cassert>
#include <cstring>

using namespace aud;

typedef std::shared_ptr<Microphone> MicP;

static Microphone* mic(AUD_Microphone* m)
{
	assert(m);
	return reinterpret_cast<MicP*>(m)->get();
}

AUD_API AUD_Microphone* AUD_Microphone_create(const char* device, int rate, int channels, const char* backend, float seconds)
{
	Specs specs;
	specs.rate = SampleRate(rate > 0 ? rate : RATE_22050);
	specs.channels = channels == 2 ? CHANNELS_STEREO : CHANNELS_MONO;
	try
	{
		return new MicP(std::make_shared<Microphone>(device ? device : "", specs, backend ? backend : "",
		                                             seconds > 0.0f ? seconds : 2.0f));
	}
	catch(Exception&)
	{
		return nullptr;
	}
}

AUD_API void AUD_Microphone_free(AUD_Microphone* m)
{
	delete reinterpret_cast<MicP*>(m);
}

AUD_API int AUD_Microphone_start(AUD_Microphone* m) { return mic(m)->start() ? 1 : 0; }
AUD_API void AUD_Microphone_stop(AUD_Microphone* m) { mic(m)->stop(); }
AUD_API void AUD_Microphone_poll(AUD_Microphone* m) { mic(m)->poll(); }
AUD_API int AUD_Microphone_isActive(AUD_Microphone* m) { return mic(m)->isActive() ? 1 : 0; }
AUD_API int AUD_Microphone_getState(AUD_Microphone* m) { return int(mic(m)->getState()); }
AUD_API float AUD_Microphone_getLevel(AUD_Microphone* m) { return mic(m)->getLevel(); }
AUD_API float AUD_Microphone_getPeak(AUD_Microphone* m) { return mic(m)->getPeak(); }
AUD_API int AUD_Microphone_getDropped(AUD_Microphone* m) { return mic(m)->getDropped(); }
AUD_API int AUD_Microphone_getRate(AUD_Microphone* m) { return int(mic(m)->getSpecs().rate); }
AUD_API void AUD_Microphone_recordStart(AUD_Microphone* m) { mic(m)->startRecording(); }
AUD_API int AUD_Microphone_isRecording(AUD_Microphone* m) { return mic(m)->isRecording() ? 1 : 0; }
AUD_API float AUD_Microphone_getRecordingSeconds(AUD_Microphone* m) { return mic(m)->getRecordingSeconds(); }

AUD_API void AUD_Microphone_getError(AUD_Microphone* m, char* buffer, int size)
{
	if(!buffer || size <= 0)
		return;
	const std::string error = mic(m)->getError();
	std::strncpy(buffer, error.c_str(), size - 1);
	buffer[size - 1] = '\0';
}

AUD_API AUD_Sound* AUD_Microphone_recordStop(AUD_Microphone* m)
{
	std::shared_ptr<ISound> sound = mic(m)->stopRecording();
	return sound ? new std::shared_ptr<ISound>(sound) : nullptr;
}

AUD_API AUD_Sound* AUD_Microphone_live(AUD_Microphone* m)
{
	try
	{
		return new std::shared_ptr<ISound>(mic(m)->createLiveSound());
	}
	catch(Exception&)
	{
		return nullptr;
	}
}

AUD_API AUD_Sound* AUD_Sound_voiceFx(AUD_Sound* sound, const char* preset, float amount)
{
	assert(sound);
	try
	{
		return new std::shared_ptr<ISound>(VoiceFX::apply(*sound, preset ? preset : "NONE", amount));
	}
	catch(Exception&)
	{
		return nullptr;
	}
}

AUD_API int AUD_Sound_voiceFxNeedsRecorded(const char* preset)
{
	return (preset && VoiceFX::needsRecorded(preset)) ? 1 : 0;
}

AUD_API int AUD_Sound_voiceFxIsPreset(const char* preset)
{
	if(!preset)
		return 0;
	const std::vector<std::string> names = VoiceFX::presetNames();
	return std::find(names.begin(), names.end(), std::string(preset)) != names.end() ? 1 : 0;
}

AUD_API AUD_Sound* AUD_Sound_edit(AUD_Sound* sound, float start, float end, float fade_in, float fade_out, int normalize)
{
	assert(sound);
	try
	{
		return new std::shared_ptr<ISound>(VoiceFX::edit(*sound, start, end, fade_in, fade_out, normalize != 0));
	}
	catch(Exception&)
	{
		return nullptr;
	}
}

AUD_API float AUD_Sound_peak(AUD_Sound* sound)
{
	assert(sound);
	try
	{
		return VoiceFX::peak(*sound);
	}
	catch(Exception&)
	{
		return 0.0f;
	}
}

AUD_API float AUD_Sound_duration(AUD_Sound* sound)
{
	assert(sound);
	try
	{
		return VoiceFX::duration(*sound);
	}
	catch(Exception&)
	{
		return -1.0f;
	}
}

AUD_API int AUD_Sound_saveWAV(AUD_Sound* sound, const char* path, float max_seconds)
{
	assert(sound && path);
	try
	{
		VoiceFX::saveWAV(*sound, path, max_seconds > 0.0f ? max_seconds : 600.0f);
		return 1;
	}
	catch(Exception&)
	{
		return 0;
	}
}
