/*
 * ***** BEGIN GPL LICENSE BLOCK *****
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 *
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file KX_CutsceneManager.h
 *  \ingroup ketsji
 *
 * Cutscene definitions and their runtime-only playback lifetime. The
 * dispatcher is added separately; its state must never leak back into Blender
 * DNA. Timeline events are kept in a stable, runtime-only schedule.
 */

#ifndef __KX_CUTSCENEMANAGER_H__
#define __KX_CUTSCENEMANAGER_H__

#include <cstddef>
#include <string>
#include <vector>

class KX_GameObject;

class KX_CutsceneManager
{
public:
	struct Event
	{
		std::string m_name;
		float m_time;
		int m_type;
		KX_GameObject *m_templateObject;
		KX_GameObject *m_spawnPoint;
		KX_GameObject *m_dependentObject;

		/* Generic reusable param slots for all 13 new action types. */
		std::string m_paramStrA;
		std::string m_paramStrB;
		float m_paramFloat;
		int m_paramInt;
		int m_paramBool;

		/* Dialog-specific: localized text and audio paths. */
		std::string m_textEn;
		std::string m_textPt;
		std::string m_textEs;
		std::string m_textRu;
		std::string m_audioPath;
	};

	struct Sequence
	{
		std::string m_name;
		std::vector<Event> m_events;
	};

	using Sequences = std::vector<Sequence>;
	using DispatchedEvents = std::vector<const Event *>;
	struct SpawnedObjects
	{
		KX_GameObject *m_primary;
		KX_GameObject *m_dependent;
	};
	using SpawnedObjectList = std::vector<SpawnedObjects>;

	enum WaitType { WAIT_NONE, WAIT_TIME, WAIT_TRIGGER, WAIT_CAMERA_END };

	explicit KX_CutsceneManager(Sequences sequences);

	const Sequences& GetSequences() const;

	/** Start the specified sequence. Returns false for an invalid index. */
	bool Start(int sequenceIndex);
	void Stop();
	bool Restart();

	/**
	 * Advance to an absolute runtime time in seconds and return each event crossed
	 * since the preceding call. Events with equal times retain their authoring
	 * order. Moving backwards restores the cursor without replaying events.
	 */
	DispatchedEvents Update(double time);
	double GetTime() const;

	bool IsPlaying() const;
	int GetActiveSequenceIndex() const;

	/** Track runtime instances until their owning scene removes them. */
	void RegisterSpawnedObjects(KX_GameObject *primary, KX_GameObject *dependent);
	SpawnedObjectList TakeSpawnedObjects();

	/* Wait state machine: pause timeline until condition is met */
	void StartWaitTime(double untilTime);
	void StartWaitTrigger(const std::string &triggerName);
	void StartWaitCameraEnd();
	void ClearWait();
	WaitType GetWaitType() const { return m_waitType; }
	const std::string& GetWaitTriggerName() const { return m_waitTriggerName; }
	double GetWaitUntilTime() const { return m_waitUntilTime; }

private:
	Sequences m_sequences;
	std::vector<std::size_t> m_eventOrder;
	int m_activeSequenceIndex;
	std::size_t m_nextEventIndex;
	double m_time;
	bool m_isPlaying;
	SpawnedObjectList m_spawnedObjects;

	/* Wait state: pause timeline during cutscene transitions */
	WaitType m_waitType;
	double m_waitUntilTime;
	std::string m_waitTriggerName;
};

#endif  // __KX_CUTSCENEMANAGER_H__
