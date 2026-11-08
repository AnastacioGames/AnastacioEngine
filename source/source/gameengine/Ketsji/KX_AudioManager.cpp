/*
 * ***** BEGIN GPL LICENSE BLOCK *****
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software Foundation,
 * Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
 *
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file gameengine/Ketsji/KX_AudioManager.cpp
 *  \ingroup ketsji
 */

#include "KX_AudioManager.h"
#include "CM_Trace.h"

#ifdef WITH_AUDASPACE
typedef float sample_t;
#  include <AUD_Sound.h>
#  include <AUD_Special.h>
#  include <AUD_Device.h>
#  include <AUD_Handle.h>
#  include <GEEffects/AUD_OpenALEffect.h>
#  include <AUD_Microphone.h>
#  ifdef WITH_PYTHON
#    include <python/PyAPI.h>
#    include <python/PyMicrophone.h>
#  endif
#endif

#include "KX_Globals.h"

#ifdef __EMSCRIPTEN__
#  include <emscripten.h>
#endif
#include "KX_KetsjiEngine.h"

#include "EXP_PyObjectPlus.h"  // PyUnicode_FromStdString

#include "DNA_ID.h"
#include "DNA_object_types.h"
#include "DNA_world_types.h"

#include "BLI_blenlib.h"
#include "PIL_time.h"

#include "CM_Message.h"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstdlib>

/// Seconds without a report from a scene before the area reverb is dropped.
static const double REVERB_TIMEOUT = 0.5;
/// Rain loops under a rain_shelter: volume, and seconds to go from the open to it.
static const float RAIN_COVERED_GAIN = 0.35f;
static const float RAIN_COVER_FADE = 0.6f;

struct KX_AudioManager::Sound
{
	std::string name;
	std::string path;
	float volume;
	float pitch;
	/// WO_SOUND_EVENT_*.
	int event;
	/// The file could not be opened: warned once, not tried again.
	bool missing;
#ifdef WITH_AUDASPACE
	/// Created on the first play, the file is streamed and not kept in memory.
	AUD_Sound *sound;
#endif
};

struct KX_AudioManager::Voice
{
	int sound;
	/// 0..1, multiplies the volume.
	float fade;
	/// Effects: multiplies the volume (PlayEvent gain).
	float gain;
	/// Effects: a Rain loop, stopped when the rain ends.
	bool rain;
	/// Per second: positive fades in, negative fades out and ends the voice, 0 holds.
	float fadeSpeed;
	float volume;
	/// The area reverb is on this handle.
	bool reverb;
	unsigned int reverbSerial;
	int reverbFilter;
	float reverbInfluence;
	/// Vozes do microfone/gravações: recebe o reverb da área (as dos módulos usam Module::useReverb).
	bool wantReverb = false;
#ifdef WITH_AUDASPACE
	AUD_Handle *handle;
#endif
};

struct KX_AudioManager::Module
{
	std::string name;
	short type;
	float volume;
	float fadeTime;
	bool shuffle;
	bool loop;
	bool mute;
	bool useReverb;
	bool paused;
	/// Music: the playlist goes on when the track ends.
	bool playing;
	/// Music: track playing or to play, -1 before the first.
	int current;
	std::vector<Sound> sounds;
	std::vector<Voice> voices;

	int FindSound(const std::string& soundName) const
	{
		for (unsigned int i = 0, size = sounds.size(); i < size; ++i) {
			if (sounds[i].name == soundName) {
				return i;
			}
		}
		return -1;
	}

	float VoiceVolume(const Voice& voice) const
	{
		return mute ? 0.0f : volume * sounds[voice.sound].volume * voice.fade * voice.gain;
	}
};

KX_AudioManager::KX_AudioManager(bool enabled)
	:m_enabled(enabled),
	m_lastUpdate(0.0),
	m_reverb(new RangeReverbAreaSettings()),
	m_reverbSource(nullptr),
	m_reverbInfluence(0.0f),
	m_reverbTime(0.0),
	m_reverbActive(false),
	m_reverbSerial(0),
	m_pendingReverb(new RangeReverbAreaSettings()),
	m_pendingSource(nullptr),
	m_pendingInfluence(0.0f),
	m_pendingValid(false),
	m_rainTime(0.0),
	m_rainPlaying(false),
	m_rainOpenReport(false),
	m_rainCoveredReport(false),
	m_rainCoverGain(1.0f),
	m_microphone(nullptr),
	m_microphoneByScript(false),
	m_microphoneUsers(0),
	m_voiceModule(new Module()),
	m_liveVoice(-1)
{
	m_voiceModule->name = "__voice";
	m_voiceModule->type = 0;
	m_voiceModule->volume = 1.0f;
	m_voiceModule->fadeTime = 0.0f;
	m_voiceModule->shuffle = false;
	m_voiceModule->loop = false;
	m_voiceModule->mute = false;
	m_voiceModule->useReverb = true;
	m_voiceModule->paused = false;
	m_voiceModule->playing = false;
	m_voiceModule->current = -1;
}

KX_AudioManager::~KX_AudioManager()
{
	StopAll();
	CloseMicrophone();
#ifdef WITH_AUDASPACE
	for (std::unique_ptr<Module>& module : m_modules) {
		for (Sound& sound : module->sounds) {
			if (sound.sound) {
				AUD_Sound_free(sound.sound);
			}
		}
	}
#endif
}

KX_AudioManager::Module *KX_AudioManager::FindModule(const std::string& name) const
{
	for (const std::unique_ptr<Module>& module : m_modules) {
		if (module->name == name) {
			return module.get();
		}
	}
	return nullptr;
}

void KX_AudioManager::RegisterWorld(const World *world)
{
	if (!world || !m_worlds.insert(world).second) {
		return;
	}

	const char *basePath = world->id.lib ? world->id.lib->filepath : KX_GetMainPath().c_str();

	for (const WorldSoundModule *dnaModule = (const WorldSoundModule *)world->sound_modules.first; dnaModule;
	     dnaModule = dnaModule->next)
	{
		Module *module = FindModule(dnaModule->name);
		const bool created = (module == nullptr);
		if (created) {
			module = new Module();
			module->name = dnaModule->name;
			module->type = dnaModule->type;
			module->volume = dnaModule->volume;
			module->fadeTime = dnaModule->fade_time;
			module->shuffle = (dnaModule->flag & WO_SOUND_SHUFFLE) != 0;
			module->loop = (dnaModule->flag & WO_SOUND_LOOP) != 0;
			module->mute = (dnaModule->flag & WO_SOUND_MUTE) != 0;
			module->useReverb = (dnaModule->flag & WO_SOUND_USE_REVERB) != 0;
			module->paused = false;
			module->playing = false;
			module->current = -1;
			m_modules.emplace_back(module);
		}

		for (const WorldSoundEntry *entry = (const WorldSoundEntry *)dnaModule->sounds.first; entry; entry = entry->next) {
			if (module->FindSound(entry->name) != -1) {
				continue;
			}
			char path[FILE_MAX];
			BLI_strncpy(path, entry->filepath, sizeof(path));
			BLI_path_abs(path, basePath);

			Sound sound;
			sound.name = entry->name;
			// Effects slots are made without a file: they stay silent until one is picked.
			sound.path = entry->filepath[0] ? path : "";
			sound.event = entry->event;
			sound.volume = entry->volume;
			sound.pitch = (entry->pitch > 0.0f) ? entry->pitch : 1.0f;
			sound.missing = false;
#ifdef WITH_AUDASPACE
			sound.sound = nullptr;
#endif
			module->sounds.push_back(sound);
		}

		if (created && (dnaModule->flag & WO_SOUND_AUTOPLAY)) {
			Play(module->name, "", -1.0f);
		}
	}
}

void KX_AudioManager::StopVoice(Voice& voice)
{
#ifdef WITH_AUDASPACE
	if (voice.handle) {
		if (voice.reverb && AUD_EFFECT_hasEffect(voice.handle)) {
			AUD_EFFECT_removeEffect(voice.handle);
		}
		// Frees the handle too.
		AUD_Handle_stop(voice.handle);
		voice.handle = nullptr;
	}
#else
	(void)voice;
#endif
}

bool KX_AudioManager::StartVoice(Module& module, int soundIndex, float fade)
{
	// A voice of this sound fading out comes back instead of starting over.
	for (Voice& voice : module.voices) {
		if (voice.sound == soundIndex) {
			voice.fadeSpeed = (fade > 0.0f) ? 1.0f / fade : 0.0f;
			if (fade <= 0.0f) {
				voice.fade = 1.0f;
			}
			return true;
		}
	}

#ifdef WITH_AUDASPACE
	Sound& sound = module.sounds[soundIndex];
	if (!m_enabled || sound.missing || sound.path.empty()) {
		return false;
	}

	if (!sound.sound) {
		sound.sound = BLI_exists(sound.path.c_str()) ? AUD_Sound_file(sound.path.c_str()) : nullptr;
	}

	AUD_Handle *handle = nullptr;
	if (sound.sound) {
		AUD_Device *device = AUD_Device_getCurrent();
		if (device) {
			handle = AUD_Device_play(device, sound.sound, false);
			if (CM_TraceOn(CM_TRACE_RUNTIME)) {
				CM_TraceEvent("sound", "\"name\":" + CM_TraceStr(BLI_path_basename(sound.path.c_str())) + ",\"from\":\"world\"");
			}
			AUD_Device_free(device);
		}
	}
	if (!handle) {
		CM_Warning("World Sound: cannot play \"" << sound.name << "\" of module \"" << module.name << "\" ("
		           << sound.path << ")");
		sound.missing = true;
		return false;
	}

	// Ambient layers and a single music track loop without a gap; a playlist advances in UpdateModule().
	if (module.type == WO_SOUND_MODULE_AMBIENT || (module.loop && module.sounds.size() == 1)) {
		AUD_Handle_setLoopCount(handle, -1);
	}
	AUD_Handle_setPitch(handle, sound.pitch);

	Voice voice;
	voice.sound = soundIndex;
	voice.fade = (fade > 0.0f) ? 0.0f : 1.0f;
	voice.fadeSpeed = (fade > 0.0f) ? 1.0f / fade : 0.0f;
	voice.gain = 1.0f;
	voice.rain = false;
	voice.reverb = false;
	voice.reverbSerial = 0;
	voice.reverbFilter = 0;
	voice.reverbInfluence = 0.0f;
	voice.handle = handle;
	voice.volume = module.VoiceVolume(voice);
	AUD_Handle_setVolume(handle, voice.volume);
	if (module.paused) {
		AUD_Handle_pause(handle);
	}
	module.voices.push_back(voice);
	return true;
#else
	(void)fade;
	return false;
#endif
}

void KX_AudioManager::FadeOutVoices(Module& module, int soundIndex, float fade)
{
	for (std::vector<Voice>::iterator it = module.voices.begin(); it != module.voices.end();) {
		if (soundIndex != -1 && it->sound != soundIndex) {
			++it;
		}
		else if (fade <= 0.0f) {
			StopVoice(*it);
			it = module.voices.erase(it);
		}
		else {
			it->fadeSpeed = -1.0f / fade;
			++it;
		}
	}
}

int KX_AudioManager::NextTrack(const Module& module, int step, bool wrap) const
{
	const int size = module.sounds.size();
	if (size == 0) {
		return -1;
	}
	if (module.shuffle && size > 1) {
		int index = rand() % size;
		if (index == module.current) {
			index = (index + 1) % size;
		}
		return index;
	}
	if (module.current < 0) {
		return (step >= 0) ? 0 : size - 1;
	}

	const int index = module.current + step;
	if (index >= 0 && index < size) {
		return index;
	}
	if (!module.loop && !wrap) {
		return -1;
	}
	return (index < 0) ? size - 1 : 0;
}

#ifdef WITH_AUDASPACE
static void apply_reverb_settings(AUD_Handle *handle, const RangeReverbAreaSettings& area, float influence, bool all)
{
	// Same fade as KX_Speaker::ApplyAreaReverb: the effect gain follows the influence and the
	// filter goes from "no filtering" (1.0) at the edge to the gains of the area.
	if (all) {
		AUD_EFFECT_setReverbDensity(handle, area.density);
		AUD_EFFECT_setReverbDiffusion(handle, area.diffusion);
		AUD_EFFECT_setReverbGainHF(handle, area.gain_hf);
		AUD_EFFECT_setReverbDecayTime(handle, area.decay_time);
		AUD_EFFECT_setReverbDecayHFRatio(handle, area.decay_hf_ratio);
		AUD_EFFECT_setReverbReflectionsGain(handle, area.reflections_gain);
		AUD_EFFECT_setReverbReflectionsDelay(handle, area.reflections_delay);
		AUD_EFFECT_setReverbLateReverbGain(handle, area.late_reverb_gain);
		AUD_EFFECT_setReverbLateReverbDelay(handle, area.late_reverb_delay);
		AUD_EFFECT_setReverbAirAbsorptionGainHF(handle, area.air_absorption_gain_hf);
		AUD_EFFECT_setReverbRoomRolloffFactor(handle, area.room_rolloff_factor);
		AUD_EFFECT_setReverbDecayLimitHF(handle, area.decay_limit_hf);
	}
	AUD_EFFECT_setReverbGain(handle, area.gain * influence);
	if (AUD_EFFECT_getFilterType(handle)) {
		AUD_EFFECT_setFilterGain(handle, 1.0f - influence * (1.0f - area.filter_gain));
		AUD_EFFECT_setFilterGainLF(handle, 1.0f - influence * (1.0f - area.filter_gain_lf));
		AUD_EFFECT_setFilterGainHF(handle, 1.0f - influence * (1.0f - area.filter_gain_hf));
	}
}
#endif

void KX_AudioManager::UpdateVoiceReverb(const Module& module, Voice& voice)
{
#ifdef WITH_AUDASPACE
	if (!module.useReverb || !m_reverbActive) {
		if (voice.reverb) {
			if (AUD_EFFECT_hasEffect(voice.handle)) {
				AUD_EFFECT_removeEffect(voice.handle);
			}
			voice.reverb = false;
		}
		return;
	}

	const RangeReverbAreaSettings& area = *m_reverb;
	const int filterType = area.use_filter ? area.filter_type : 0;

	if (!voice.reverb || voice.reverbFilter != filterType || !AUD_EFFECT_hasEffect(voice.handle)) {
		if (AUD_EFFECT_hasEffect(voice.handle)) {
			AUD_EFFECT_removeEffect(voice.handle);
		}
		AUD_EFFECT_setEffect(voice.handle, 1 /* aud::AUDIO_EFFECT_REVERB */, filterType);
		apply_reverb_settings(voice.handle, area, m_reverbInfluence, true);
	}
	else if (voice.reverbSerial != m_reverbSerial) {
		apply_reverb_settings(voice.handle, area, m_reverbInfluence, true);
	}
	else if (std::fabs(voice.reverbInfluence - m_reverbInfluence) > 1e-3f) {
		apply_reverb_settings(voice.handle, area, m_reverbInfluence, false);
	}
	else {
		return;
	}

	voice.reverb = true;
	voice.reverbSerial = m_reverbSerial;
	voice.reverbFilter = filterType;
	voice.reverbInfluence = m_reverbInfluence;
#else
	(void)module;
	(void)voice;
#endif
}

void KX_AudioManager::UpdateModule(Module& module, float dt)
{
	if (module.paused) {
		return;
	}

#ifdef WITH_AUDASPACE
	for (std::vector<Voice>::iterator it = module.voices.begin(); it != module.voices.end();) {
		Voice& voice = *it;

		// The sound reached its end: the device dropped it, only our handle is left.
		if (AUD_Handle_getStatus(voice.handle) == AUD_STATUS_INVALID) {
			AUD_Handle_free(voice.handle);
			it = module.voices.erase(it);
			continue;
		}

		if (voice.fadeSpeed != 0.0f) {
			voice.fade += voice.fadeSpeed * dt;
			if (voice.fade <= 0.0f && voice.fadeSpeed < 0.0f) {
				StopVoice(voice);
				it = module.voices.erase(it);
				continue;
			}
			if (voice.fade >= 1.0f) {
				voice.fade = 1.0f;
				voice.fadeSpeed = 0.0f;
			}
		}

		const float volume = module.VoiceVolume(voice);
		if (volume != voice.volume) {
			AUD_Handle_setVolume(voice.handle, volume);
			voice.volume = volume;
		}

		UpdateVoiceReverb(module, voice);
		++it;
	}
#endif

	if (module.type != WO_SOUND_MODULE_MUSIC || !module.playing) {
		return;
	}
	for (const Voice& voice : module.voices) {
		if (voice.fadeSpeed >= 0.0f) {
			return;
		}
	}

	// The track ended: go on with the playlist, skipping what cannot play.
	for (unsigned int tries = 0, size = module.sounds.size(); tries < size; ++tries) {
		const int next = NextTrack(module, 1, false);
		if (next == -1) {
			break;
		}
		module.current = next;
		if (StartVoice(module, next, 0.0f)) {
			return;
		}
	}
	module.playing = false;
}

void KX_AudioManager::Update()
{
	const double now = PIL_check_seconds_timer();
	const float dt = (m_lastUpdate > 0.0) ? (float)std::min(std::max(now - m_lastUpdate, 0.0), 0.1) : 0.0f;
	m_lastUpdate = now;

	// Events waiting for their time (thunder after the flash).
	for (unsigned int i = 0; i < m_delayedEvents.size();) {
		if (m_delayedEvents[i].time <= now) {
			const DelayedEvent delayed = m_delayedEvents[i];
			m_delayedEvents.erase(m_delayedEvents.begin() + i);
			PlayEvent(delayed.event, delayed.gain);
		}
		else {
			++i;
		}
	}

	if (m_pendingValid) {
		m_reverbActive = (m_pendingSource != nullptr);
		if (m_reverbActive) {
			if (m_pendingSource != m_reverbSource) {
				++m_reverbSerial;
			}
			*m_reverb = *m_pendingReverb;
			m_reverbInfluence = m_pendingInfluence;
		}
		m_reverbSource = m_pendingSource;
		m_reverbTime = now;
		m_pendingValid = false;
		m_pendingSource = nullptr;
		m_pendingInfluence = 0.0f;
	}
	else if (m_reverbActive && now - m_reverbTime > REVERB_TIMEOUT) {
		m_reverbActive = false;
		m_reverbSource = nullptr;
	}

	// No scene with rain for a while: the rain loops fade out.
	if (m_rainPlaying && now - m_rainTime > REVERB_TIMEOUT) {
		m_rainPlaying = false;
		for (std::unique_ptr<Module>& module : m_modules) {
			for (Voice& voice : module->voices) {
				if (voice.rain) {
					voice.fadeSpeed = -0.5f;
				}
			}
		}
	}

	// Under a roof the rain is heard quieter; any camera in the open (split screen) keeps it full.
	{
		const float target = (m_rainCoveredReport && !m_rainOpenReport) ? RAIN_COVERED_GAIN : 1.0f;
		const float step = dt / RAIN_COVER_FADE;
		m_rainCoverGain = (target < m_rainCoverGain) ? std::max(target, m_rainCoverGain - step) :
		                                               std::min(target, m_rainCoverGain + step);
		m_rainOpenReport = m_rainCoveredReport = false;
		for (std::unique_ptr<Module>& module : m_modules) {
			for (Voice& voice : module->voices) {
				if (voice.rain) {
					voice.gain = m_rainCoverGain;
				}
			}
		}
	}

	for (std::unique_ptr<Module>& module : m_modules) {
		UpdateModule(*module, dt);
	}

	UpdateMicrophoneVoices();
}

void KX_AudioManager::SetAreaReverb(const RangeReverbAreaSettings *area, float influence)
{
	if (!area || influence <= 0.0f) {
		area = nullptr;
		influence = 0.0f;
	}
	if (m_pendingValid && influence <= m_pendingInfluence) {
		return;
	}
	m_pendingValid = true;
	m_pendingSource = area;
	m_pendingInfluence = influence;
	if (area) {
		*m_pendingReverb = *area;
	}
}

bool KX_AudioManager::Play(const std::string& moduleName, const std::string& soundName, float fade)
{
	Module *module = FindModule(moduleName);
	if (!module) {
		return false;
	}
	if (fade < 0.0f) {
		fade = module->fadeTime;
	}

	int index = -1;
	if (!soundName.empty()) {
		index = module->FindSound(soundName);
		if (index == -1) {
			return false;
		}
	}

	if (module->paused) {
		Resume(moduleName);
	}

	if (module->type == WO_SOUND_MODULE_EFFECTS) {
		// One-shots are played one at a time, by name.
		return (index != -1) && StartOneShot(*module, index, 1.0f, false, 0.0f);
	}

	if (module->type == WO_SOUND_MODULE_MUSIC) {
		if (index == -1) {
			if (IsPlaying(moduleName)) {
				return true;
			}
			index = (module->current >= 0) ? module->current : NextTrack(*module, 1, true);
			if (index == -1) {
				return false;
			}
		}
		else if (index == module->current && IsPlaying(moduleName)) {
			return true;
		}

		// Crossfade: everything else fades out while the new track fades in.
		for (Voice& voice : module->voices) {
			if (voice.sound != index) {
				voice.fadeSpeed = (fade > 0.0f) ? -1.0f / fade : -1.0e6f;
			}
		}
		module->current = index;
		module->playing = StartVoice(*module, index, fade);
		return module->playing;
	}

	if (index != -1) {
		return StartVoice(*module, index, fade);
	}
	bool started = false;
	for (unsigned int i = 0, size = module->sounds.size(); i < size; ++i) {
		started |= StartVoice(*module, i, fade);
	}
	return started;
}

bool KX_AudioManager::Stop(const std::string& moduleName, const std::string& soundName, float fade)
{
	Module *module = FindModule(moduleName);
	if (!module) {
		return false;
	}
	if (fade < 0.0f) {
		fade = module->fadeTime;
	}

	int index = -1;
	if (!soundName.empty()) {
		index = module->FindSound(soundName);
		if (index == -1) {
			return false;
		}
	}

	// A paused module makes no sound and does not fade: end it now.
	FadeOutVoices(*module, index, module->paused ? 0.0f : fade);
	if (index == -1 || index == module->current) {
		module->playing = false;
	}
	if (index == -1) {
		module->paused = false;
	}
	return true;
}

bool KX_AudioManager::Pause(const std::string& moduleName)
{
	Module *module = FindModule(moduleName);
	if (!module) {
		return false;
	}
	if (!module->paused) {
		module->paused = true;
#ifdef WITH_AUDASPACE
		for (Voice& voice : module->voices) {
			AUD_Handle_pause(voice.handle);
		}
#endif
	}
	return true;
}

bool KX_AudioManager::Resume(const std::string& moduleName)
{
	Module *module = FindModule(moduleName);
	if (!module) {
		return false;
	}
	if (module->paused) {
		module->paused = false;
#ifdef WITH_AUDASPACE
		for (Voice& voice : module->voices) {
			AUD_Handle_resume(voice.handle);
		}
#endif
	}
	return true;
}

bool KX_AudioManager::Step(const std::string& moduleName, int step)
{
	Module *module = FindModule(moduleName);
	if (!module || module->type != WO_SOUND_MODULE_MUSIC) {
		return false;
	}
	const int next = NextTrack(*module, step, true);
	if (next == -1) {
		return false;
	}
	return Play(moduleName, module->sounds[next].name, -1.0f);
}

bool KX_AudioManager::SetVolume(const std::string& moduleName, float volume)
{
	Module *module = FindModule(moduleName);
	if (!module) {
		return false;
	}
	module->volume = std::min(std::max(volume, 0.0f), 1.0f);
	return true;
}

float KX_AudioManager::GetVolume(const std::string& moduleName) const
{
	const Module *module = FindModule(moduleName);
	return module ? module->volume : -1.0f;
}

bool KX_AudioManager::IsPlaying(const std::string& moduleName) const
{
	const Module *module = FindModule(moduleName);
	if (!module || module->paused) {
		return false;
	}
	for (const Voice& voice : module->voices) {
		if (voice.fadeSpeed >= 0.0f) {
			return true;
		}
	}
	return false;
}

std::vector<std::string> KX_AudioManager::GetPlaying(const std::string& moduleName) const
{
	std::vector<std::string> names;
	const Module *module = FindModule(moduleName);
	if (module && !module->paused) {
		for (const Voice& voice : module->voices) {
			if (voice.fadeSpeed >= 0.0f) {
				names.push_back(module->sounds[voice.sound].name);
			}
		}
	}
	return names;
}

std::vector<std::string> KX_AudioManager::GetModuleNames() const
{
	std::vector<std::string> names;
	for (const std::unique_ptr<Module>& module : m_modules) {
		names.push_back(module->name);
	}
	return names;
}

std::vector<std::string> KX_AudioManager::GetSoundNames(const std::string& moduleName) const
{
	std::vector<std::string> names;
	const Module *module = FindModule(moduleName);
	if (module) {
		for (const Sound& sound : module->sounds) {
			names.push_back(sound.name);
		}
	}
	return names;
}

bool KX_AudioManager::HasModule(const std::string& moduleName) const
{
	return FindModule(moduleName) != nullptr;
}

bool KX_AudioManager::StartOneShot(Module& module, int soundIndex, float gain, bool loop, float fade, float pitchScale)
{
#ifdef WITH_AUDASPACE
	Sound& sound = module.sounds[soundIndex];
	if (!m_enabled || sound.missing || sound.path.empty()) {
		return false;
	}

	// Many blasts at once: the oldest voice goes, not the new one.
	static const unsigned int MAX_VOICES = 32;
	if (module.voices.size() >= MAX_VOICES) {
		StopVoice(module.voices.front());
		module.voices.erase(module.voices.begin());
	}

	if (!sound.sound) {
		sound.sound = BLI_exists(sound.path.c_str()) ? AUD_Sound_file(sound.path.c_str()) : nullptr;
	}
	AUD_Handle *handle = nullptr;
	if (sound.sound) {
		AUD_Device *device = AUD_Device_getCurrent();
		if (device) {
			handle = AUD_Device_play(device, sound.sound, false);
			if (CM_TraceOn(CM_TRACE_RUNTIME)) {
				CM_TraceEvent("sound", "\"name\":" + CM_TraceStr(BLI_path_basename(sound.path.c_str())) + ",\"from\":\"world\"");
			}
			AUD_Device_free(device);
		}
	}
	if (!handle) {
		CM_Warning("World Sound: cannot play \"" << sound.name << "\" of module \"" << module.name << "\" ("
		           << sound.path << ")");
		sound.missing = true;
		return false;
	}
	if (loop) {
		AUD_Handle_setLoopCount(handle, -1);
	}
	AUD_Handle_setPitch(handle, sound.pitch * pitchScale);

	Voice voice;
	voice.sound = soundIndex;
	voice.fade = (fade > 0.0f) ? 0.0f : 1.0f;
	voice.fadeSpeed = (fade > 0.0f) ? 1.0f / fade : 0.0f;
	voice.gain = gain;
	voice.rain = loop;
	voice.reverb = false;
	voice.reverbSerial = 0;
	voice.reverbFilter = 0;
	voice.reverbInfluence = 0.0f;
	voice.handle = handle;
	voice.volume = module.VoiceVolume(voice);
	AUD_Handle_setVolume(handle, voice.volume);
	if (module.paused) {
		AUD_Handle_pause(handle);
	}
	module.voices.push_back(voice);
	return true;
#else
	(void)module;
	(void)soundIndex;
	(void)gain;
	(void)loop;
	(void)fade;
	(void)pitchScale;
	return false;
#endif
}

bool KX_AudioManager::PlayEvent(int event, float gain)
{
	if (event <= WO_SOUND_EVENT_NONE || gain <= 0.0f) {
		return false;
	}

	std::vector<std::pair<Module *, int> > candidates;
	for (std::unique_ptr<Module>& module : m_modules) {
		if (module->type != WO_SOUND_MODULE_EFFECTS) {
			continue;
		}
		for (unsigned int i = 0, size = module->sounds.size(); i < size; ++i) {
			const Sound& sound = module->sounds[i];
			if (sound.event == event && !sound.missing && !sound.path.empty()) {
				candidates.emplace_back(module.get(), i);
			}
		}
	}
	if (candidates.empty()) {
		return false;
	}

	// A variation at random, never the last one twice in a row.
	if (m_lastEvent.size() <= (size_t)event) {
		m_lastEvent.resize(event + 1, std::pair<const Module *, int>(nullptr, -1));
	}
	std::pair<const Module *, int>& last = m_lastEvent[event];
	unsigned int pick = rand() % candidates.size();
	if (candidates.size() > 1 && candidates[pick].first == last.first && candidates[pick].second == last.second) {
		pick = (pick + 1 + rand() % (candidates.size() - 1)) % candidates.size();
	}
	last = candidates[pick];

	// Each one sounds a little different: pitch +-12% and up to 15% quieter.
	const float pitch = 0.88f + 0.24f * (float)rand() / (float)RAND_MAX;
	const float level = 0.85f + 0.15f * (float)rand() / (float)RAND_MAX;
	return StartOneShot(*candidates[pick].first, candidates[pick].second, gain * level, false, 0.0f, pitch);
}

void KX_AudioManager::PlayEventDelayed(int event, float gain, float delay)
{
	if (delay <= 0.0f) {
		PlayEvent(event, gain);
		return;
	}
	m_delayedEvents.push_back({PIL_check_seconds_timer() + delay, event, gain});
}

void KX_AudioManager::ReportRain(bool covered)
{
	m_rainTime = PIL_check_seconds_timer();
	(covered ? m_rainCoveredReport : m_rainOpenReport) = true;
	if (m_rainPlaying) {
		return;
	}
	m_rainPlaying = true;

	// Every Rain sound is a layer (light rain, roof, gutter...), faded in.
	for (std::unique_ptr<Module>& module : m_modules) {
		if (module->type != WO_SOUND_MODULE_EFFECTS) {
			continue;
		}
		for (unsigned int i = 0, size = module->sounds.size(); i < size; ++i) {
			if (module->sounds[i].event == WO_SOUND_EVENT_RAIN) {
				StartOneShot(*module, i, m_rainCoverGain, true, 2.0f);
			}
		}
	}
}

void KX_AudioManager::StopAll()
{
	for (std::unique_ptr<Module>& module : m_modules) {
		FadeOutVoices(*module, -1, 0.0f);
		module->playing = false;
		module->paused = false;
	}
	m_rainPlaying = false;
	m_delayedEvents.clear();
}

/* ---- Microfone ---------------------------------------------------------- */

void KX_AudioManager::UpdateMicrophoneVoices()
{
#ifdef WITH_AUDASPACE
	if (m_microphone) {
		AUD_Microphone_poll(m_microphone);
	}

	std::vector<Voice>& voices = m_voiceModule->voices;
	for (unsigned int i = 0; i < voices.size();) {
		Voice& voice = voices[i];
		if (AUD_Handle_getStatus(voice.handle) == AUD_STATUS_INVALID) {
			AUD_Handle_free(voice.handle);
			voices.erase(voices.begin() + i);
			if (m_liveVoice == (int)i) {
				m_liveVoice = -1;
			}
			else if (m_liveVoice > (int)i) {
				--m_liveVoice;
			}
			continue;
		}
		if (voice.wantReverb || voice.reverb) {
			// The voice module always has useReverb on; a dry voice drops a reverb it had.
			m_voiceModule->useReverb = voice.wantReverb;
			UpdateVoiceReverb(*m_voiceModule, voice);
			m_voiceModule->useReverb = true;
		}
		++i;
	}
#endif
}

void KX_AudioManager::StopMicrophoneVoices()
{
	for (Voice& voice : m_voiceModule->voices) {
		StopVoice(voice);
	}
	m_voiceModule->voices.clear();
	m_liveVoice = -1;
}

void KX_AudioManager::CloseMicrophone()
{
	StopMicrophoneVoices();
#ifdef WITH_AUDASPACE
	for (std::pair<const std::string, void *>& recording : m_recordings) {
		AUD_Sound_free(recording.second);
	}
	m_recordings.clear();
	if (m_microphone) {
		AUD_Microphone_stop(m_microphone);
		AUD_Microphone_free(m_microphone);
		m_microphone = nullptr;
	}
#endif
	m_microphoneUsers = 0;
	m_microphoneByScript = false;
}

/// Create on first use and start. Light voice: mono 22050 Hz, 2 s queue (survives loading hitches).
static bool microphone_open(void *&microphone, bool enabled, const std::string& device)
{
#ifdef WITH_AUDASPACE
	if (!enabled) {
		return false;
	}
	if (!microphone) {
		microphone = AUD_Microphone_create(device.c_str(), 22050, 1, nullptr, 2.0f);
		if (!microphone) {
			CM_Warning("Microphone: cannot create the microphone");
			return false;
		}
	}
	if (AUD_Microphone_isActive(microphone)) {
		return true;
	}
	if (!AUD_Microphone_start(microphone)) {
		char error[256];
		AUD_Microphone_getError(microphone, error, sizeof(error));
		CM_Warning("Microphone: " << error);
		return false;
	}
	return true;
#else
	(void)microphone;
	(void)enabled;
	(void)device;
	return false;
#endif
}

bool KX_AudioManager::MicrophoneStart(const std::string& device)
{
	m_microphoneByScript = true;
	return microphone_open(m_microphone, m_enabled, device);
}

void KX_AudioManager::MicrophoneStop()
{
	m_microphoneByScript = false;
#ifdef WITH_AUDASPACE
	if (m_microphone && m_microphoneUsers <= 0) {
		StopLive();
		AUD_Microphone_stop(m_microphone);
	}
#endif
}

void KX_AudioManager::MicrophoneAcquire()
{
	++m_microphoneUsers;
	microphone_open(m_microphone, m_enabled, "");
}

void KX_AudioManager::MicrophoneRelease()
{
	if (m_microphoneUsers > 0 && --m_microphoneUsers == 0 && !m_microphoneByScript) {
#ifdef WITH_AUDASPACE
		if (m_microphone && !AUD_Microphone_isRecording(m_microphone) && m_liveVoice < 0) {
			AUD_Microphone_stop(m_microphone);
		}
#endif
	}
}

std::string KX_AudioManager::MicrophoneState() const
{
#ifdef WITH_AUDASPACE
	if (m_microphone) {
		switch (AUD_Microphone_getState(m_microphone)) {
			case AUD_MICROPHONE_PENDING: return "pending";
			case AUD_MICROPHONE_GRANTED: return "granted";
			case AUD_MICROPHONE_DENIED: return "denied";
			case AUD_MICROPHONE_ERROR: return "error";
			default: break;
		}
	}
#endif
	return "closed";
}

std::string KX_AudioManager::MicrophoneError() const
{
#ifdef WITH_AUDASPACE
	if (m_microphone) {
		char error[256];
		AUD_Microphone_getError(m_microphone, error, sizeof(error));
		return error;
	}
#endif
	return m_enabled ? "" : "audio is off (headless server)";
}

float KX_AudioManager::MicrophoneLevel() const
{
#ifdef WITH_AUDASPACE
	return m_microphone ? AUD_Microphone_getLevel(m_microphone) : 0.0f;
#else
	return 0.0f;
#endif
}

float KX_AudioManager::MicrophonePeak() const
{
#ifdef WITH_AUDASPACE
	return m_microphone ? AUD_Microphone_getPeak(m_microphone) : 0.0f;
#else
	return 0.0f;
#endif
}

int KX_AudioManager::MicrophoneDropped() const
{
#ifdef WITH_AUDASPACE
	return m_microphone ? AUD_Microphone_getDropped(m_microphone) : 0;
#else
	return 0;
#endif
}

bool KX_AudioManager::MicrophoneRecordStart()
{
	if (!microphone_open(m_microphone, m_enabled, "")) {
		return false;
	}
#ifdef WITH_AUDASPACE
	AUD_Microphone_recordStart(m_microphone);
	return true;
#else
	return false;
#endif
}

bool KX_AudioManager::MicrophoneRecordStop(const std::string& slot)
{
#ifdef WITH_AUDASPACE
	if (!m_microphone || !AUD_Microphone_isRecording(m_microphone)) {
		return false;
	}
	AUD_Sound *sound = AUD_Microphone_recordStop(m_microphone);
	if (!sound) {
		return false;
	}
	SetRecording(slot.empty() ? "last" : slot, sound);
	AUD_Sound_free(sound);
	return true;
#else
	(void)slot;
	return false;
#endif
}

bool KX_AudioManager::MicrophoneIsRecording() const
{
#ifdef WITH_AUDASPACE
	return m_microphone && AUD_Microphone_isRecording(m_microphone);
#else
	return false;
#endif
}

float KX_AudioManager::MicrophoneRecordingSeconds() const
{
#ifdef WITH_AUDASPACE
	return m_microphone ? AUD_Microphone_getRecordingSeconds(m_microphone) : 0.0f;
#else
	return 0.0f;
#endif
}

void *KX_AudioManager::GetMicrophone() const
{
	return m_microphone;
}

void *KX_AudioManager::GetRecording(const std::string& slot) const
{
	std::map<std::string, void *>::const_iterator it = m_recordings.find(slot);
	return (it != m_recordings.end()) ? it->second : nullptr;
}

void KX_AudioManager::SetRecording(const std::string& slot, void *sound)
{
#ifdef WITH_AUDASPACE
	if (!sound) {
		return;
	}
	AUD_Sound *copy = AUD_Sound_copy(sound);
	std::map<std::string, void *>::iterator it = m_recordings.find(slot);
	if (it != m_recordings.end()) {
		AUD_Sound_free(it->second);
		it->second = copy;
	}
	else {
		m_recordings[slot] = copy;
	}
#else
	(void)slot;
	(void)sound;
#endif
}

bool KX_AudioManager::RemoveRecording(const std::string& slot)
{
	std::map<std::string, void *>::iterator it = m_recordings.find(slot);
	if (it == m_recordings.end()) {
		return false;
	}
#ifdef WITH_AUDASPACE
	AUD_Sound_free(it->second);
#endif
	m_recordings.erase(it);
	return true;
}

std::vector<std::string> KX_AudioManager::GetRecordingNames() const
{
	std::vector<std::string> names;
	for (const std::pair<const std::string, void *>& recording : m_recordings) {
		names.push_back(recording.first);
	}
	return names;
}

/// Relative names ("fala.wav", "//fala.wav") go to the game folder; on the Web to /saves (IndexedDB).
static std::string microphone_save_path(const std::string& path)
{
	std::string name = path;
	if (name.compare(0, 2, "//") == 0) {
		name = name.substr(2);
	}
	else if (name[0] == '/' || name[0] == '\\' || (name.size() > 1 && name[1] == ':')) {
		return name;
	}
#ifdef __EMSCRIPTEN__
	return "/saves/" + name;
#else
	const std::string& base = KX_GetOrigPath();
	const size_t dirlen = BLI_path_basename(base.c_str()) - base.c_str();
	return base.substr(0, dirlen) + name;
#endif
}

bool KX_AudioManager::SaveRecording(const std::string& slot, const std::string& path)
{
#ifdef WITH_AUDASPACE
	void *sound = GetRecording(slot);
	if (!sound || path.empty()) {
		return false;
	}
	const std::string target = microphone_save_path(path);
	if (!AUD_Sound_saveWAV(sound, target.c_str(), 600.0f)) {
		CM_Warning("Microphone: cannot save \"" << slot << "\" to " << target);
		return false;
	}
#ifdef __EMSCRIPTEN__
	EM_ASM({
		FS.syncfs(false, function(err) {
			if (err) {
				console.error('[web-save] syncfs (microphone) failed:', err);
			}
		});
	});
#endif
	return true;
#else
	(void)slot;
	(void)path;
	return false;
#endif
}

bool KX_AudioManager::PlaySound(void *sound, const std::string& preset, float amount, float volume, bool reverb)
{
#ifdef WITH_AUDASPACE
	if (!m_enabled || !sound) {
		return false;
	}
	AUD_Sound *played = AUD_Sound_voiceFx(sound, preset.empty() ? "NONE" : preset.c_str(), amount);
	if (!played) {
		CM_Warning("Voice: unknown effect \"" << preset << "\"");
		return false;
	}
	AUD_Handle *handle = nullptr;
	AUD_Device *device = AUD_Device_getCurrent();
	if (device) {
		handle = AUD_Device_play(device, played, false);
		AUD_Device_free(device);
	}
	AUD_Sound_free(played);
	if (!handle) {
		return false;
	}
	AUD_Handle_setVolume(handle, volume);

	Voice voice;
	voice.sound = -1;
	voice.fade = 1.0f;
	voice.fadeSpeed = 0.0f;
	voice.gain = 1.0f;
	voice.rain = false;
	voice.volume = volume;
	voice.reverb = false;
	voice.reverbSerial = 0;
	voice.reverbFilter = 0;
	voice.reverbInfluence = 0.0f;
	voice.wantReverb = reverb;
	voice.handle = handle;
	m_voiceModule->voices.push_back(voice);
	if (reverb) {
		UpdateVoiceReverb(*m_voiceModule, m_voiceModule->voices.back());
	}
	return true;
#else
	(void)sound;
	(void)preset;
	(void)amount;
	(void)volume;
	(void)reverb;
	return false;
#endif
}

bool KX_AudioManager::PlayRecording(const std::string& slot, const std::string& preset, float amount, float volume, bool reverb)
{
	void *sound = GetRecording(slot);
	if (!sound) {
		CM_Warning("Voice: no recording \"" << slot << "\"");
		return false;
	}
	return PlaySound(sound, preset, amount, volume, reverb);
}

bool KX_AudioManager::PlayLive(const std::string& preset, float amount, float volume, bool reverb)
{
#ifdef WITH_AUDASPACE
	if (AUD_Sound_voiceFxNeedsRecorded(preset.c_str())) {
		CM_Warning("Voice: \"" << preset << "\" needs a recorded sound, not the live microphone");
		return false;
	}
	StopLive();
	if (!microphone_open(m_microphone, m_enabled, "")) {
		return false;
	}
	AUD_Sound *live = AUD_Microphone_live(m_microphone);
	if (!live) {
		return false;
	}
	const bool played = PlaySound(live, preset, amount, volume, reverb);
	AUD_Sound_free(live);
	if (played) {
		m_liveVoice = (int)m_voiceModule->voices.size() - 1;
	}
	return played;
#else
	(void)preset;
	(void)amount;
	(void)volume;
	(void)reverb;
	return false;
#endif
}

void KX_AudioManager::StopLive()
{
	if (m_liveVoice >= 0 && m_liveVoice < (int)m_voiceModule->voices.size()) {
		StopVoice(m_voiceModule->voices[m_liveVoice]);
		m_voiceModule->voices.erase(m_voiceModule->voices.begin() + m_liveVoice);
	}
	m_liveVoice = -1;
}

bool KX_AudioManager::IsLive() const
{
	return m_liveVoice >= 0;
}

/// Split a command on spaces; "double quotes" keep names with spaces together.
static std::vector<std::string> split_command(const std::string& text)
{
	std::vector<std::string> tokens;
	std::string current;
	bool quoted = false;
	bool hasToken = false;
	for (const char c : text) {
		if (c == '"') {
			quoted = !quoted;
			hasToken = true;
		}
		else if (!quoted && (c == ' ' || c == '\t' || c == '\n' || c == '\r')) {
			if (hasToken) {
				tokens.push_back(current);
				current.clear();
				hasToken = false;
			}
		}
		else {
			current += c;
			hasToken = true;
		}
	}
	if (hasToken) {
		tokens.push_back(current);
	}
	return tokens;
}

static bool parse_float(const std::string& text, float& value)
{
	if (text.empty()) {
		return false;
	}
	char *end = nullptr;
	const float result = std::strtof(text.c_str(), &end);
	if (end == text.c_str() || *end != '\0') {
		return false;
	}
	value = result;
	return true;
}

bool KX_AudioManager::ExecuteCommand(const std::string& command)
{
	std::vector<std::string> args = split_command(command);
	if (args.empty()) {
		CM_Warning("World Sound: empty \"audio\" message");
		return false;
	}

	std::string verb = args[0];
	std::transform(verb.begin(), verb.end(), verb.begin(), [](unsigned char c) { return std::tolower(c); });

	if (verb == "stopall") {
		StopAll();
		return true;
	}

	if (args.size() < 2) {
		CM_Warning("World Sound: \"" << command << "\" needs a module name");
		return false;
	}
	const std::string& module = args[1];
	if (!HasModule(module)) {
		CM_Warning("World Sound: \"" << command << "\": no module \"" << module << "\"");
		return false;
	}

	// Optional "fade=seconds" anywhere after the module; the other word is the sound.
	float fade = -1.0f;
	std::string sound;
	for (size_t i = 2; i < args.size(); ++i) {
		if (args[i].compare(0, 5, "fade=") == 0) {
			if (!parse_float(args[i].substr(5), fade)) {
				CM_Warning("World Sound: \"" << command << "\": bad fade \"" << args[i] << "\"");
				return false;
			}
		}
		else if (sound.empty()) {
			sound = args[i];
		}
	}

	bool ok;
	if (verb == "play") {
		ok = Play(module, sound, fade);
	}
	else if (verb == "stop") {
		ok = Stop(module, sound, fade);
	}
	else if (verb == "pause") {
		ok = Pause(module);
	}
	else if (verb == "resume") {
		ok = Resume(module);
	}
	else if (verb == "next") {
		ok = Step(module, 1);
	}
	else if (verb == "prev" || verb == "previous") {
		ok = Step(module, -1);
	}
	else if (verb == "volume") {
		float volume;
		if (!parse_float(sound, volume)) {
			CM_Warning("World Sound: \"" << command << "\" needs a number, e.g. \"volume " << module << " 0.5\"");
			return false;
		}
		ok = SetVolume(module, volume);
	}
	else {
		CM_Warning("World Sound: unknown command \"" << args[0] << "\" (play, stop, pause, resume, next, prev, "
		           "volume, stopall)");
		return false;
	}

	// A headless server plays nothing: not a mistake in the command, no warning.
	if (!ok && m_enabled) {
		CM_Warning("World Sound: \"" << command << "\" failed (sound not found?)");
	}
	return ok;
}

#ifdef WITH_PYTHON

/* ------------------------------------------------------------------------- */
/* Python module Range.audio (alias bge.audio)                                */
/* ------------------------------------------------------------------------- */

static KX_AudioManager *py_audio_manager()
{
	KX_KetsjiEngine *engine = KX_GetActiveEngine();
	KX_AudioManager *manager = engine ? engine->GetAudioManager() : nullptr;
	if (!manager) {
		PyErr_SetString(PyExc_RuntimeError, "Range.audio: the game engine is not running");
	}
	return manager;
}

static PyObject *py_audio_names(const std::vector<std::string>& names)
{
	PyObject *list = PyList_New(names.size());
	for (unsigned int i = 0, size = names.size(); i < size; ++i) {
		PyList_SET_ITEM(list, i, PyUnicode_FromStdString(names[i]));
	}
	return list;
}

PyDoc_STRVAR(py_audio_play_doc,
             "play(module, sound=\"\", fade=-1.0)\n"
             "Play a sound of a World Sound module, or resume the module when it is paused.\n"
             "Without sound, Music plays the current track and Ambient plays every layer.\n"
             "fade is in seconds; negative uses the Fade of the module.\n"
             "Returns False when the module or the sound does not exist or cannot play."
             );
static PyObject *py_audio_play(PyObject *, PyObject *args, PyObject *kwds)
{
	static const char *kwlist[] = {"module", "sound", "fade", nullptr};
	const char *module;
	const char *sound = "";
	float fade = -1.0f;
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "s|sf:play", (char **)kwlist, &module, &sound, &fade)) {
		return nullptr;
	}
	KX_AudioManager *manager = py_audio_manager();
	if (!manager) {
		return nullptr;
	}
	return PyBool_FromLong(manager->Play(module, sound, fade));
}

PyDoc_STRVAR(py_audio_stop_doc,
             "stop(module, sound=\"\", fade=-1.0)\n"
             "Stop a World Sound module, or only one of its sounds.\n"
             "fade is in seconds; negative uses the Fade of the module."
             );
static PyObject *py_audio_stop(PyObject *, PyObject *args, PyObject *kwds)
{
	static const char *kwlist[] = {"module", "sound", "fade", nullptr};
	const char *module;
	const char *sound = "";
	float fade = -1.0f;
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "s|sf:stop", (char **)kwlist, &module, &sound, &fade)) {
		return nullptr;
	}
	KX_AudioManager *manager = py_audio_manager();
	if (!manager) {
		return nullptr;
	}
	return PyBool_FromLong(manager->Stop(module, sound, fade));
}

#define PY_AUDIO_MODULE_CALL(pyname, call) \
	static PyObject *py_audio_##pyname(PyObject *, PyObject *args) \
	{ \
		const char *module; \
		if (!PyArg_ParseTuple(args, "s:" #pyname, &module)) { \
			return nullptr; \
		} \
		KX_AudioManager *manager = py_audio_manager(); \
		if (!manager) { \
			return nullptr; \
		} \
		return call; \
	}

PY_AUDIO_MODULE_CALL(pause, PyBool_FromLong(manager->Pause(module)))
PY_AUDIO_MODULE_CALL(resume, PyBool_FromLong(manager->Resume(module)))
PY_AUDIO_MODULE_CALL(next, PyBool_FromLong(manager->Step(module, 1)))
PY_AUDIO_MODULE_CALL(previous, PyBool_FromLong(manager->Step(module, -1)))
PY_AUDIO_MODULE_CALL(isPlaying, PyBool_FromLong(manager->IsPlaying(module)))
PY_AUDIO_MODULE_CALL(playing, py_audio_names(manager->GetPlaying(module)))
PY_AUDIO_MODULE_CALL(sounds, py_audio_names(manager->GetSoundNames(module)))

#undef PY_AUDIO_MODULE_CALL

static PyObject *py_audio_setVolume(PyObject *, PyObject *args)
{
	const char *module;
	float volume;
	if (!PyArg_ParseTuple(args, "sf:setVolume", &module, &volume)) {
		return nullptr;
	}
	KX_AudioManager *manager = py_audio_manager();
	if (!manager) {
		return nullptr;
	}
	return PyBool_FromLong(manager->SetVolume(module, volume));
}

static PyObject *py_audio_getVolume(PyObject *, PyObject *args)
{
	const char *module;
	if (!PyArg_ParseTuple(args, "s:getVolume", &module)) {
		return nullptr;
	}
	KX_AudioManager *manager = py_audio_manager();
	if (!manager) {
		return nullptr;
	}
	const float volume = manager->GetVolume(module);
	if (volume < 0.0f) {
		Py_RETURN_NONE;
	}
	return PyFloat_FromDouble(volume);
}

static PyObject *py_audio_modules(PyObject *, PyObject *Py_UNUSED(ignored))
{
	KX_AudioManager *manager = py_audio_manager();
	if (!manager) {
		return nullptr;
	}
	return py_audio_names(manager->GetModuleNames());
}

/* ---- Range.audio: microfone e voz ---------------------------------------- */

static PyObject *py_audio_microphoneStart(PyObject *, PyObject *args, PyObject *kwds)
{
	static const char *kwlist[] = {"device", nullptr};
	const char *device = "";
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "|s:microphoneStart", const_cast<char **>(kwlist), &device)) {
		return nullptr;
	}
	KX_AudioManager *manager = py_audio_manager();
	if (!manager) {
		return nullptr;
	}
	return PyBool_FromLong(manager->MicrophoneStart(device));
}

static PyObject *py_audio_microphoneStop(PyObject *, PyObject *Py_UNUSED(ignored))
{
	KX_AudioManager *manager = py_audio_manager();
	if (!manager) {
		return nullptr;
	}
	manager->MicrophoneStop();
	Py_RETURN_NONE;
}

static PyObject *py_audio_microphoneState(PyObject *, PyObject *Py_UNUSED(ignored))
{
	KX_AudioManager *manager = py_audio_manager();
	return manager ? PyUnicode_FromStdString(manager->MicrophoneState()) : nullptr;
}

static PyObject *py_audio_microphoneError(PyObject *, PyObject *Py_UNUSED(ignored))
{
	KX_AudioManager *manager = py_audio_manager();
	return manager ? PyUnicode_FromStdString(manager->MicrophoneError()) : nullptr;
}

static PyObject *py_audio_microphoneLevel(PyObject *, PyObject *Py_UNUSED(ignored))
{
	KX_AudioManager *manager = py_audio_manager();
	return manager ? PyFloat_FromDouble(manager->MicrophoneLevel()) : nullptr;
}

static PyObject *py_audio_microphonePeak(PyObject *, PyObject *Py_UNUSED(ignored))
{
	KX_AudioManager *manager = py_audio_manager();
	return manager ? PyFloat_FromDouble(manager->MicrophonePeak()) : nullptr;
}

static PyObject *py_audio_microphoneDropped(PyObject *, PyObject *Py_UNUSED(ignored))
{
	KX_AudioManager *manager = py_audio_manager();
	return manager ? PyLong_FromLong(manager->MicrophoneDropped()) : nullptr;
}

static PyObject *py_audio_microphoneRecordStart(PyObject *, PyObject *Py_UNUSED(ignored))
{
	KX_AudioManager *manager = py_audio_manager();
	return manager ? PyBool_FromLong(manager->MicrophoneRecordStart()) : nullptr;
}

static PyObject *py_audio_recording(PyObject *, PyObject *args);

static PyObject *py_audio_microphoneRecordStop(PyObject *, PyObject *args, PyObject *kwds)
{
	static const char *kwlist[] = {"slot", nullptr};
	const char *slot = "last";
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "|s:microphoneRecordStop", const_cast<char **>(kwlist), &slot)) {
		return nullptr;
	}
	KX_AudioManager *manager = py_audio_manager();
	if (!manager) {
		return nullptr;
	}
	if (!manager->MicrophoneRecordStop(slot)) {
		Py_RETURN_NONE;
	}
	PyObject *name = Py_BuildValue("(s)", slot);
	PyObject *result = py_audio_recording(nullptr, name);
	Py_DECREF(name);
	return result;
}

static PyObject *py_audio_microphoneIsRecording(PyObject *, PyObject *Py_UNUSED(ignored))
{
	KX_AudioManager *manager = py_audio_manager();
	return manager ? PyBool_FromLong(manager->MicrophoneIsRecording()) : nullptr;
}

static PyObject *py_audio_microphoneRecordingSeconds(PyObject *, PyObject *Py_UNUSED(ignored))
{
	KX_AudioManager *manager = py_audio_manager();
	return manager ? PyFloat_FromDouble(manager->MicrophoneRecordingSeconds()) : nullptr;
}

static PyObject *py_audio_microphone(PyObject *, PyObject *Py_UNUSED(ignored))
{
	KX_AudioManager *manager = py_audio_manager();
	if (!manager) {
		return nullptr;
	}
#ifdef WITH_AUDASPACE
	if (manager->GetMicrophone()) {
		return Microphone_fromSharedPointer(manager->GetMicrophone());
	}
#endif
	Py_RETURN_NONE;
}

static PyObject *py_audio_microphoneSave(PyObject *, PyObject *args)
{
	const char *slot, *path;
	if (!PyArg_ParseTuple(args, "ss:microphoneSave", &slot, &path)) {
		return nullptr;
	}
	KX_AudioManager *manager = py_audio_manager();
	return manager ? PyBool_FromLong(manager->SaveRecording(slot, path)) : nullptr;
}

static PyObject *py_audio_recordings(PyObject *, PyObject *Py_UNUSED(ignored))
{
	KX_AudioManager *manager = py_audio_manager();
	return manager ? py_audio_names(manager->GetRecordingNames()) : nullptr;
}

static PyObject *py_audio_recording(PyObject *, PyObject *args)
{
	const char *slot;
	if (!PyArg_ParseTuple(args, "s:recording", &slot)) {
		return nullptr;
	}
	KX_AudioManager *manager = py_audio_manager();
	if (!manager) {
		return nullptr;
	}
#ifdef WITH_AUDASPACE
	void *sound = manager->GetRecording(slot);
	if (sound) {
		return AUD_getPythonSound(sound);
	}
#endif
	Py_RETURN_NONE;
}

static PyObject *py_audio_setRecording(PyObject *, PyObject *args)
{
	const char *slot;
	PyObject *object;
	if (!PyArg_ParseTuple(args, "sO:setRecording", &slot, &object)) {
		return nullptr;
	}
	KX_AudioManager *manager = py_audio_manager();
	if (!manager) {
		return nullptr;
	}
	if (object == Py_None) {
		return PyBool_FromLong(manager->RemoveRecording(slot));
	}
#ifdef WITH_AUDASPACE
	void *sound = AUD_getSoundFromPython(object);
	if (!sound) {
		return nullptr;
	}
	manager->SetRecording(slot, sound);
	AUD_Sound_free(sound);
#endif
	Py_RETURN_TRUE;
}

static PyObject *py_audio_play_sound_impl(KX_AudioManager *manager, PyObject *object, const char *slot,
                                          const char *preset, float amount, float volume, int reverb)
{
#ifdef WITH_AUDASPACE
	if (slot) {
		return PyBool_FromLong(manager->PlayRecording(slot, preset, amount, volume, reverb != 0));
	}
	void *sound = AUD_getSoundFromPython(object);
	if (!sound) {
		return nullptr;
	}
	const bool played = manager->PlaySound(sound, preset, amount, volume, reverb != 0);
	AUD_Sound_free(sound);
	return PyBool_FromLong(played);
#else
	(void)manager;
	(void)object;
	(void)slot;
	(void)preset;
	(void)amount;
	(void)volume;
	(void)reverb;
	Py_RETURN_FALSE;
#endif
}

PyDoc_STRVAR(py_audio_playVoice_doc,
             "playVoice(sound, effect=\"NONE\", amount=1.0, volume=1.0, reverb=False)\n"
             "Play a recording name (str) or an aud.Sound with a voice effect\n"
             "(see voicePresets()). reverb=True uses the reverb of the area/World.\n"
             "Returns False when the recording or the effect does not exist."
             );

static PyObject *py_audio_playVoice(PyObject *, PyObject *args, PyObject *kwds)
{
	static const char *kwlist[] = {"sound", "effect", "amount", "volume", "reverb", nullptr};
	PyObject *object;
	const char *preset = "NONE";
	float amount = 1.0f, volume = 1.0f;
	int reverb = 0;
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "O|sffp:playVoice", const_cast<char **>(kwlist), &object, &preset,
	                                 &amount, &volume, &reverb)) {
		return nullptr;
	}
	KX_AudioManager *manager = py_audio_manager();
	if (!manager) {
		return nullptr;
	}
	const char *slot = PyUnicode_Check(object) ? PyUnicode_AsUTF8(object) : nullptr;
	return py_audio_play_sound_impl(manager, object, slot, preset, amount, volume, reverb);
}

PyDoc_STRVAR(py_audio_playLive_doc,
             "playLive(effect=\"NONE\", amount=1.0, volume=1.0, reverb=False)\n"
             "Hear the microphone now with a voice effect (one at a time; calling again swaps the\n"
             "effect). Use headphones: speakers feed back into the microphone."
             );

static PyObject *py_audio_playLive(PyObject *, PyObject *args, PyObject *kwds)
{
	static const char *kwlist[] = {"effect", "amount", "volume", "reverb", nullptr};
	const char *preset = "NONE";
	float amount = 1.0f, volume = 1.0f;
	int reverb = 0;
	if (!PyArg_ParseTupleAndKeywords(args, kwds, "|sffp:playLive", const_cast<char **>(kwlist), &preset, &amount,
	                                 &volume, &reverb)) {
		return nullptr;
	}
	KX_AudioManager *manager = py_audio_manager();
	return manager ? PyBool_FromLong(manager->PlayLive(preset, amount, volume, reverb != 0)) : nullptr;
}

static PyObject *py_audio_stopLive(PyObject *, PyObject *Py_UNUSED(ignored))
{
	KX_AudioManager *manager = py_audio_manager();
	if (!manager) {
		return nullptr;
	}
	manager->StopLive();
	Py_RETURN_NONE;
}

static PyObject *py_audio_isLive(PyObject *, PyObject *Py_UNUSED(ignored))
{
	KX_AudioManager *manager = py_audio_manager();
	return manager ? PyBool_FromLong(manager->IsLive()) : nullptr;
}

/// Calls aud.<name>(*args, **kwds): voiceFx/edit/voicePresets are the same table as the aud module.
static PyObject *py_audio_call_aud(const char *name, PyObject *args, PyObject *kwds)
{
	PyObject *aud = PyImport_ImportModule("aud");
	if (!aud) {
		return nullptr;
	}
	PyObject *function = PyObject_GetAttrString(aud, name);
	Py_DECREF(aud);
	if (!function) {
		return nullptr;
	}
	PyObject *result = PyObject_Call(function, args, kwds);
	Py_DECREF(function);
	return result;
}

static PyObject *py_audio_voiceFx(PyObject *, PyObject *args, PyObject *kwds)
{
	return py_audio_call_aud("voice_fx", args, kwds);
}

static PyObject *py_audio_edit(PyObject *, PyObject *args, PyObject *kwds)
{
	return py_audio_call_aud("edit", args, kwds);
}

static PyObject *py_audio_voicePresets(PyObject *, PyObject *args, PyObject *kwds)
{
	return py_audio_call_aud("voice_presets", args, kwds);
}

static PyMethodDef py_audio_methods[] = {
	{"play", (PyCFunction)py_audio_play, METH_VARARGS | METH_KEYWORDS, py_audio_play_doc},
	{"stop", (PyCFunction)py_audio_stop, METH_VARARGS | METH_KEYWORDS, py_audio_stop_doc},
	{"pause", py_audio_pause, METH_VARARGS, "pause(module)\nPause every sound of the module where it is."},
	{"resume", py_audio_resume, METH_VARARGS, "resume(module)\nGo on from where pause(module) stopped."},
	{"next", py_audio_next, METH_VARARGS, "next(module)\nMusic: cross to the next track."},
	{"previous", py_audio_previous, METH_VARARGS, "previous(module)\nMusic: cross to the previous track."},
	{"setVolume", py_audio_setVolume, METH_VARARGS, "setVolume(module, volume)\nVolume of the module, 0.0 to 1.0."},
	{"getVolume", py_audio_getVolume, METH_VARARGS,
	 "getVolume(module)\nVolume of the module, None when it does not exist."},
	{"isPlaying", py_audio_isPlaying, METH_VARARGS, "isPlaying(module)\nTrue while a sound of the module plays."},
	{"playing", py_audio_playing, METH_VARARGS,
	 "playing(module)\nNames of the sounds playing now (Music: the current track)."},
	{"sounds", py_audio_sounds, METH_VARARGS, "sounds(module)\nNames of the sounds of the module."},
	{"modules", py_audio_modules, METH_NOARGS, "modules()\nNames of the World Sound modules loaded so far."},
	{"microphoneStart", (PyCFunction)py_audio_microphoneStart, METH_VARARGS | METH_KEYWORDS,
	 "microphoneStart(device=\"\")\nTurn the microphone on (Web: after a click/touch). False when it cannot open."},
	{"microphoneStop", py_audio_microphoneStop, METH_NOARGS,
	 "microphoneStop()\nTurn the microphone off."},
	{"microphoneState", py_audio_microphoneState, METH_NOARGS,
	 "microphoneState()\n'closed', 'pending', 'granted', 'denied' or 'error'."},
	{"microphoneError", py_audio_microphoneError, METH_NOARGS,
	 "microphoneError()\nWhy it did not open."},
	{"microphoneLevel", py_audio_microphoneLevel, METH_NOARGS,
	 "microphoneLevel()\nVoice level now, 0..1."},
	{"microphonePeak", py_audio_microphonePeak, METH_NOARGS,
	 "microphonePeak()\nPeak with a slow fall, 0..1."},
	{"microphoneDropped", py_audio_microphoneDropped, METH_NOARGS,
	 "microphoneDropped()\nTimes audio was lost because the game hitched."},
	{"microphoneRecordStart", py_audio_microphoneRecordStart, METH_NOARGS,
	 "microphoneRecordStart()\nStart recording."},
	{"microphoneRecordStop", (PyCFunction)py_audio_microphoneRecordStop, METH_VARARGS | METH_KEYWORDS,
	 "microphoneRecordStop(slot=\"last\")\nStop and keep the recording as slot; returns the aud.Sound or None."},
	{"microphoneIsRecording", py_audio_microphoneIsRecording, METH_NOARGS,
	 "microphoneIsRecording()"},
	{"microphoneRecordingSeconds", py_audio_microphoneRecordingSeconds, METH_NOARGS,
	 "microphoneRecordingSeconds()\nLength of the recording in progress."},
	{"microphoneSave", py_audio_microphoneSave, METH_VARARGS,
	 "microphoneSave(slot, path)\nSave a recording as WAV; relative paths go to the game folder (Web: /saves)."},
	{"microphone", py_audio_microphone, METH_NOARGS,
	 "microphone()\nThe aud.Microphone in use (None before it starts), for advanced use."},
	{"recordings", py_audio_recordings, METH_NOARGS,
	 "recordings()\nNames of the recordings kept so far."},
	{"recording", py_audio_recording, METH_VARARGS,
	 "recording(slot)\nThe aud.Sound of a recording, or None."},
	{"setRecording", py_audio_setRecording, METH_VARARGS,
	 "setRecording(slot, sound)\nKeep an aud.Sound under a name (None removes it)."},
	{"playVoice", (PyCFunction)py_audio_playVoice, METH_VARARGS | METH_KEYWORDS,
	 py_audio_playVoice_doc},
	{"playLive", (PyCFunction)py_audio_playLive, METH_VARARGS | METH_KEYWORDS,
	 py_audio_playLive_doc},
	{"stopLive", py_audio_stopLive, METH_NOARGS,
	 "stopLive()\nStop hearing the microphone."},
	{"isLive", py_audio_isLive, METH_NOARGS,
	 "isLive()"},
	{"voiceFx", (PyCFunction)py_audio_voiceFx, METH_VARARGS | METH_KEYWORDS,
	 "voiceFx(sound, preset, amount=1.0)\nSame as aud.voice_fx."},
	{"edit", (PyCFunction)py_audio_edit, METH_VARARGS | METH_KEYWORDS,
	 "edit(sound, start=0, end=-1, fade_in=0, fade_out=0, normalize=False)\nSame as aud.edit."},
	{"voicePresets", (PyCFunction)py_audio_voicePresets, METH_VARARGS | METH_KEYWORDS,
	 "voicePresets(live=False)\nNames of the voice effects."},
	{nullptr, nullptr, 0, nullptr}
};

PyDoc_STRVAR(py_audio_module_doc,
             "World Sound: plays the sound modules of the World (World Sound tab) by name.\n"
             "The modules keep playing when the scene changes."
             );

static struct PyModuleDef py_audio_module_def = {
	PyModuleDef_HEAD_INIT,
	"audio",  /* m_name */
	py_audio_module_doc,  /* m_doc */
	0,  /* m_size */
	py_audio_methods,  /* m_methods */
	nullptr,  /* m_reload */
	nullptr,  /* m_traverse */
	nullptr,  /* m_clear */
	nullptr,  /* m_free */
};

PyMODINIT_FUNC initAudioPythonBinding()
{
	return PyModule_Create(&py_audio_module_def);
}

#endif  // WITH_PYTHON
