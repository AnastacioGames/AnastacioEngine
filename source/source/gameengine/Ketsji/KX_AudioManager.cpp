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
#endif

#include "KX_Globals.h"
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
	m_rainCoverGain(1.0f)
{
}

KX_AudioManager::~KX_AudioManager()
{
	StopAll();
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

	if (!ok) {
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
