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

/** \file CM_LogBuffer.h
 *  \ingroup common
 */

#ifndef __CM_LOGBUFFER_H__
#define __CM_LOGBUFFER_H__

#include <deque>
#include <mutex>
#include <string>
#include <vector>

enum class CM_LogLevel
{
	MESSAGE,
	WARNING,
	ERROR_,
	DEBUG
};

struct CM_LogLine
{
	CM_LogLevel level;
	std::string text;
};

/** Thread-safe ring buffer holding the most recent engine log lines, fed by
 *  a std::cout tee (see CM_LogBuffer.cpp) so it mirrors CM_Error/CM_Warning/...
 *  output without disturbing the real console (colors included). Used to
 *  display the log in the in-game ImGui console window (KX_ConsoleWindow). */
class CM_LogBuffer
{
private:
	std::mutex m_mutex;
	std::deque<CM_LogLine> m_lines;
	size_t m_capacity;

	CM_LogBuffer();

public:
	static CM_LogBuffer& Get();

	void Push(CM_LogLevel level, const std::string& text);
	std::vector<CM_LogLine> GetLines();
	void Clear();
};

#endif  // __CM_LOGBUFFER_H__
