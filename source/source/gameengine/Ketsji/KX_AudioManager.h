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

/** \file KX_AudioManager.h
 *  \ingroup ketsji
 *  \brief World Sound: plays the sound modules of the World (music and ambient) by name.
 *
 * The manager belongs to the launcher, not to a scene, so what it plays goes on when the scene
 * changes. The modules come from World.sound_modules (World Sound tab) of every scene that
 * becomes active and stay registered after the scene is gone. Python: Range.audio.
 */

#ifndef __KX_AUDIOMANAGER_H__
#define __KX_AUDIOMANAGER_H__

#include "EXP_Python.h"

#include <memory>
#include <string>
#include <unordered_set>
#include <vector>

struct RangeReverbAreaSettings;
struct World;

class KX_AudioManager
{
public:
	/// \param enabled false on a headless server: the modules exist but nothing plays.
	explicit KX_AudioManager(bool enabled);
	~KX_AudioManager();

	/// Add the sound modules of a World, once per World. A module whose name is already
	/// registered only receives the sounds it does not have, so what is playing keeps playing.
	void RegisterWorld(const World *world);

	/// Once per rendered frame: fades, playlist advance and reverb of the playing sounds.
	void Update();

	/** The reverb area of the listener, from KX_Scene::UpdateReverbAreas(). With several
	 * scenes reporting in a frame the strongest wins. Kept until the next report; dropped when
	 * no scene reports for a while (the scene with the areas ended).
	 * \param area nullptr when the camera is in no area.
	 */
	void SetAreaReverb(const RangeReverbAreaSettings *area, float influence);

	/** Start a sound of the module, or resume the module when it is paused.
	 * \param sound Empty: music plays the current track, ambient plays every layer.
	 * \param fade Seconds, negative uses the fade time of the module.
	 * \return false when the module or the sound does not exist.
	 */
	bool Play(const std::string& module, const std::string& sound, float fade);
	/// Stop the module, or only one of its sounds when \a sound is not empty.
	bool Stop(const std::string& module, const std::string& sound, float fade);
	bool Pause(const std::string& module);
	bool Resume(const std::string& module);
	/// Music: cross to the next (step 1) or previous (step -1) track.
	bool Step(const std::string& module, int step);

	bool SetVolume(const std::string& module, float volume);
	/// \return negative when the module does not exist.
	float GetVolume(const std::string& module) const;
	bool IsPlaying(const std::string& module) const;
	/// Names of the sounds playing now (music: the current track).
	std::vector<std::string> GetPlaying(const std::string& module) const;
	std::vector<std::string> GetModuleNames() const;
	std::vector<std::string> GetSoundNames(const std::string& module) const;
	bool HasModule(const std::string& module) const;

	/// Stop everything now, without fade.
	void StopAll();

private:
	struct Sound;
	struct Voice;
	struct Module;

	Module *FindModule(const std::string& name) const;
	/// Start (or bring back from a fade out) one sound. \return false when it cannot play.
	bool StartVoice(Module& module, int soundIndex, float fade);
	/// \param soundIndex -1 for every sound of the module.
	void FadeOutVoices(Module& module, int soundIndex, float fade);
	void UpdateModule(Module& module, float dt);
	void UpdateVoiceReverb(const Module& module, Voice& voice);
	void StopVoice(Voice& voice);
	/// \param wrap Go around the ends even without Loop (the player asked for next/previous).
	int NextTrack(const Module& module, int step, bool wrap) const;

	bool m_enabled;
	std::vector<std::unique_ptr<Module> > m_modules;
	std::unordered_set<const World *> m_worlds;

	double m_lastUpdate;

	/// Copy of the area settings, the scene's object may be gone on the next frame.
	std::unique_ptr<RangeReverbAreaSettings> m_reverb;
	/// Identity of the area the copy came from: tells "same area, fade moved" from "new area".
	const RangeReverbAreaSettings *m_reverbSource;
	float m_reverbInfluence;
	double m_reverbTime;
	bool m_reverbActive;
	/// Changes on every new area, see Voice::reverbSerial.
	unsigned int m_reverbSerial;

	/// Strongest report since the last Update().
	std::unique_ptr<RangeReverbAreaSettings> m_pendingReverb;
	const RangeReverbAreaSettings *m_pendingSource;
	float m_pendingInfluence;
	bool m_pendingValid;
};

#ifdef WITH_PYTHON
PyMODINIT_FUNC initAudioPythonBinding(void);
#endif

#endif  // __KX_AUDIOMANAGER_H__
