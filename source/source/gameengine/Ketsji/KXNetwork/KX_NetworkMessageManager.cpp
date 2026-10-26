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
 * The Original Code is Copyright (C) 2001-2002 by NaN Holding BV.
 * All rights reserved.
 *
 * The Original Code is: all of this file.
 *
 * Contributor(s): none yet.
 *
 * ***** END GPL LICENSE BLOCK *****
 * Ketsji Logic Extension: Network Message Scene generic implementation
 */

/** \file gameengine/Ketsji/KXNetwork/KX_NetworkMessageManager.cpp
 *  \ingroup ketsjinet
 */

#include "KX_NetworkMessageManager.h"
#include <iostream>

KX_NetworkMessageManager::KX_NetworkMessageManager()
	:m_currentList(0)
{
}

KX_NetworkMessageManager::~KX_NetworkMessageManager()
{
	ClearMessages();
}

void KX_NetworkMessageManager::AddMessage(KX_NetworkMessageManager::Message message)
{
	// Put the new message in map for the given receiver and subject.
	m_messages[m_currentList][message.to][message.subject].push_back(message);
}

const std::vector<KX_NetworkMessageManager::Message> KX_NetworkMessageManager::GetMessages(std::string to, std::string subject)
{
	std::vector<KX_NetworkMessageManager::Message> messages;

	// Read with find: the read list must not gain empty entries for every query.
	const std::map<std::string, std::map<std::string, std::vector<Message> > >& list = m_messages[1 - m_currentList];
	const auto addReceiver = [&](const std::string& receiver) {
		const auto it = list.find(receiver);
		if (it == list.end()) {
			return;
		}
		if (subject.empty()) {
			for (const auto& pair : it->second) {
				messages.insert(messages.end(), pair.second.begin(), pair.second.end());
			}
		}
		else {
			const auto sit = it->second.find(subject);
			if (sit != it->second.end()) {
				messages.insert(messages.end(), sit->second.begin(), sit->second.end());
			}
		}
	};

	// Messages without receiver, then the ones for the given receiver.
	addReceiver("");
	// An empty receiver is the broadcast list itself: reading it twice duplicated every message.
	if (!to.empty()) {
		addReceiver(to);
	}

	return messages;
}

void KX_NetworkMessageManager::ClearMessages()
{
	// Clear previous list.
	m_messages[1 - m_currentList].clear();
	m_currentList = 1 - m_currentList;
}
