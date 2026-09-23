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

#include "KX_CutsceneManager.h"

#include <algorithm>
#include <utility>

KX_CutsceneManager::KX_CutsceneManager(Sequences sequences)
	: m_sequences(std::move(sequences)),
	  m_activeSequenceIndex(-1),
	  m_nextEventIndex(0),
	  m_time(0.0),
	  m_isPlaying(false),
	  m_waitType(WAIT_NONE),
	  m_waitUntilTime(0.0)
{
}

const KX_CutsceneManager::Sequences& KX_CutsceneManager::GetSequences() const
{
	return m_sequences;
}

bool KX_CutsceneManager::Start(int sequenceIndex)
{
	if (sequenceIndex < 0 || sequenceIndex >= static_cast<int>(m_sequences.size())) {
		return false;
	}

	m_activeSequenceIndex = sequenceIndex;
	m_eventOrder.clear();
	const std::vector<Event>& events = m_sequences[sequenceIndex].m_events;
	for (std::size_t index = 0; index < events.size(); ++index) {
		m_eventOrder.push_back(index);
	}
	std::stable_sort(m_eventOrder.begin(), m_eventOrder.end(), [&events](std::size_t left, std::size_t right) {
		return events[left].m_time < events[right].m_time;
	});
	m_nextEventIndex = 0;
	m_time = 0.0;
	m_isPlaying = true;
	return true;
}

void KX_CutsceneManager::Stop()
{
	m_activeSequenceIndex = -1;
	m_eventOrder.clear();
	m_nextEventIndex = 0;
	m_time = 0.0;
	m_isPlaying = false;
}

bool KX_CutsceneManager::Restart()
{
	const int sequenceIndex = m_activeSequenceIndex;
	Stop();
	return Start(sequenceIndex);
}

KX_CutsceneManager::DispatchedEvents KX_CutsceneManager::Update(double time)
{
	DispatchedEvents dispatchedEvents;
	if (!m_isPlaying || time < 0.0) {
		return dispatchedEvents;
	}

	const std::vector<Event>& events = m_sequences[m_activeSequenceIndex].m_events;
	if (time < m_time) {
		m_nextEventIndex = 0;
		while (m_nextEventIndex < m_eventOrder.size() &&
		       events[m_eventOrder[m_nextEventIndex]].m_time <= time) {
			++m_nextEventIndex;
		}
		m_time = time;
		return dispatchedEvents;
	}

	/* Pause timeline while waiting for condition */
	if (m_waitType != WAIT_NONE) {
		if (m_waitType == WAIT_TIME && time >= m_waitUntilTime) {
			m_waitType = WAIT_NONE;
		} else {
			m_time = time;
			return dispatchedEvents;
		}
	}

	while (m_nextEventIndex < m_eventOrder.size() &&
	       events[m_eventOrder[m_nextEventIndex]].m_time <= time) {
		const Event *event = &events[m_eventOrder[m_nextEventIndex]];
		dispatchedEvents.push_back(event);
		++m_nextEventIndex;

		/* Pause after WAIT_* events; will be resumed by scene check */
		if (event->m_type == 14 || event->m_type == 15 || event->m_type == 16) { // WAIT_TIME, WAIT_TRIGGER, WAIT_CAMERA_END
			break;
		}
	}
	m_time = time;
	return dispatchedEvents;
}

double KX_CutsceneManager::GetTime() const
{
	return m_time;
}

bool KX_CutsceneManager::IsPlaying() const
{
	return m_isPlaying;
}

int KX_CutsceneManager::GetActiveSequenceIndex() const
{
	return m_activeSequenceIndex;
}

void KX_CutsceneManager::RegisterSpawnedObjects(KX_GameObject *primary, KX_GameObject *dependent)
{
	if (primary) {
		m_spawnedObjects.push_back({primary, dependent});
	}
}

KX_CutsceneManager::SpawnedObjectList KX_CutsceneManager::TakeSpawnedObjects()
{
	SpawnedObjectList spawnedObjects;
	spawnedObjects.swap(m_spawnedObjects);
	return spawnedObjects;
}

void KX_CutsceneManager::StartWaitTime(double untilTime)
{
	m_waitType = WAIT_TIME;
	m_waitUntilTime = untilTime;
}

void KX_CutsceneManager::StartWaitTrigger(const std::string &triggerName)
{
	m_waitType = WAIT_TRIGGER;
	m_waitTriggerName = triggerName;
}

void KX_CutsceneManager::StartWaitCameraEnd()
{
	m_waitType = WAIT_CAMERA_END;
}

void KX_CutsceneManager::ClearWait()
{
	m_waitType = WAIT_NONE;
	m_waitUntilTime = 0.0;
	m_waitTriggerName.clear();
}
