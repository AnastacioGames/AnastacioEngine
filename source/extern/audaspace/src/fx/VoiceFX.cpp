/*******************************************************************************
 * Anastacio Engine: efeitos de voz (presets).
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

#include "fx/VoiceFX.h"
#include "respec/ChannelMapper.h"
#include "fx/Delay.h"
#include "fx/Fader.h"
#include "fx/Highpass.h"
#include "fx/Limiter.h"
#include "fx/Lowpass.h"
#include "fx/Modulator.h"
#include "fx/Pitch.h"
#include "fx/Reverse.h"
#include "fx/Volume.h"
#include "generator/Sine.h"
#include "devices/Microphone.h"
#include "sequence/Superpose.h"
#include "IReader.h"
#include "Exception.h"

#include <algorithm>
#include <cmath>

AUD_NAMESPACE_BEGIN

namespace {

typedef std::shared_ptr<ISound> SoundP;

SoundP vol(SoundP s, float v) { return SoundP(new Volume(s, v)); }
SoundP mix(SoundP a, SoundP b) { return SoundP(new Superpose(a, b)); }
SoundP delay(SoundP s, float t) { return SoundP(new Delay(s, t)); }
float lerp(float a, float b, float t) { return a + (b - a) * t; }

/* Eco com N repetições: seco + cópias atrasadas cada vez mais baixas. */
SoundP echoes(SoundP s, const float* times, const float* gains, int count, float amount)
{
	SoundP out = s;
	for(int i = 0; i < count; i++)
		out = mix(out, vol(delay(s, times[i]), gains[i] * amount));
	return out;
}

}

std::vector<std::string> VoiceFX::presetNames()
{
	return {"NONE", "CHIPMUNK", "GIANT", "ROBOT", "RADIO", "ECHO", "CAVE", "REVERSE"};
}

bool VoiceFX::needsRecorded(const std::string& preset)
{
	return preset == "REVERSE";
}

SoundP VoiceFX::apply(SoundP s, const std::string& preset, float amount)
{
	if(!s)
		AUD_THROW(StateException, "VoiceFX: no sound.");
	const float a = std::max(0.0f, std::min(1.0f, amount));

	if(preset == "NONE" || preset.empty() || a <= 0.0f)
		return s;
	if(preset == "CHIPMUNK")
		return SoundP(new Pitch(s, lerp(1.0f, 1.6f, a)));
	if(preset == "GIANT")
		return SoundP(new Lowpass(SoundP(new Pitch(s, lerp(1.0f, 0.65f, a))), lerp(8000.0f, 2500.0f, a)));
	if(preset == "ROBOT")
	{
		/* Modulação em anel por um seno de 60 Hz, na taxa do próprio som. */
		DeviceSpecs specs;
		specs.format = FORMAT_FLOAT32;
		specs.rate = RATE_22050;
		specs.channels = CHANNELS_MONO;
		try { specs.specs = s->createReader()->getSpecs(); } catch(Exception&) {}
		SoundP sine(new Sine(60.0f, specs.rate));
		if(specs.channels != CHANNELS_MONO)  // o Modulator exige o mesmo número de canais
			sine = SoundP(new ChannelMapper(sine, specs));
		SoundP ring(new Modulator(s, sine));
		return mix(vol(s, 1.0f - 0.7f * a), vol(ring, 1.4f * a));
	}
	if(preset == "RADIO")
	{
		SoundP f(new Highpass(s, lerp(80.0f, 400.0f, a)));
		f = SoundP(new Lowpass(f, lerp(9000.0f, 3000.0f, a)));
		return vol(f, lerp(1.0f, 1.4f, a));
	}
	if(preset == "ECHO")
	{
		const float t = lerp(0.12f, 0.25f, a);
		const float times[] = {t, 2.0f * t};
		const float gains[] = {0.5f, 0.25f};
		return echoes(s, times, gains, 2, a);
	}
	if(preset == "CAVE")
	{
		/* Reverb barato: ecos curtos densos + abafado. No jogo, o reverb
		 * do mundo/área (KX_AudioManager) é a opção de qualidade. */
		const float times[] = {0.043f, 0.071f, 0.113f, 0.167f, 0.239f};
		const float gains[] = {0.45f, 0.38f, 0.3f, 0.22f, 0.15f};
		SoundP wet = echoes(s, times, gains, 5, a);
		return vol(SoundP(new Lowpass(wet, lerp(9000.0f, 4000.0f, a))), lerp(1.0f, 0.75f, a));
	}
	if(preset == "REVERSE")
		return SoundP(new Reverse(s));

	AUD_THROW(StateException, ("VoiceFX: unknown preset '" + preset + "'.").c_str());
}

float VoiceFX::duration(SoundP s)
{
	auto reader = s->createReader();
	const int length = reader->getLength();
	if(length < 0)
		return -1.0f;
	return float(length) / float(reader->getSpecs().rate);
}

float VoiceFX::peak(SoundP s, float max_seconds)
{
	auto reader = s->createReader();
	const Specs specs = reader->getSpecs();
	const int block = 4096;
	std::vector<sample_t> buffer(block * specs.channels);
	long long remaining = (long long)(max_seconds * specs.rate);
	float result = 0.0f;
	bool eos = false;

	while(!eos && remaining > 0)
	{
		int length = int(std::min<long long>(block, remaining));
		reader->read(length, eos, buffer.data());
		if(length <= 0)
			break;
		const int count = length * specs.channels;
		for(int i = 0; i < count; i++)
		{
			const float v = buffer[i] < 0.0f ? -buffer[i] : buffer[i];
			if(v > result)
				result = v;
		}
		remaining -= length;
	}
	return result;
}

SoundP VoiceFX::edit(SoundP s, float start, float end, float fade_in, float fade_out, bool normalize)
{
	if(!s)
		AUD_THROW(StateException, "VoiceFX: no sound.");
	start = std::max(0.0f, start);
	SoundP out = s;
	if(start > 0.0f || end >= 0.0f)
		out = SoundP(new Limiter(out, start, end >= 0.0f ? std::max(end, start) : -1.0));

	if(fade_in > 0.0f)
		out = SoundP(new Fader(out, FADE_IN, 0.0, fade_in));
	if(fade_out > 0.0f)
	{
		const float length = duration(out);
		if(length > 0.0f)
			out = SoundP(new Fader(out, FADE_OUT, std::max(0.0f, length - fade_out), std::min(fade_out, length)));
	}
	if(normalize)
	{
		const float p = peak(out);
		if(p > 1e-4f)
			out = vol(out, 0.95f / p);
	}
	return out;
}

void VoiceFX::saveWAV(SoundP s, const std::string& path, float max_seconds)
{
	if(!s)
		AUD_THROW(StateException, "VoiceFX: no sound.");
	auto reader = s->createReader();
	const Specs specs = reader->getSpecs();
	const int block = 4096;
	const long long limit = (long long)(max_seconds * specs.rate);
	std::vector<sample_t> data;
	bool eos = false;
	long long total = 0;

	while(!eos && total < limit)
	{
		int length = int(std::min<long long>(block, limit - total));
		const size_t offset = data.size();
		data.resize(offset + size_t(length) * specs.channels);
		reader->read(length, eos, data.data() + offset);
		data.resize(offset + size_t(std::max(length, 0)) * specs.channels);
		if(length <= 0)
			break;
		total += length;
	}
	Microphone::writeWAV(path, data.data(), int(total), specs);
}

AUD_NAMESPACE_END
