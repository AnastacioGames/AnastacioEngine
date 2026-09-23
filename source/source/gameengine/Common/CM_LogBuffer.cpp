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

/** \file CM_LogBuffer.cpp
 *  \ingroup common
 */

#include "CM_LogBuffer.h"

#include <iostream>

namespace {

/** Mirrors every byte written to std::cout into the owning CM_LogBuffer,
 *  one line at a time, while still forwarding it untouched to the real
 *  console streambuf. On Windows, termcolor colorizes std::cout by calling
 *  SetConsoleTextAttribute() directly (not by writing escape bytes), so the
 *  captured text is naturally plain -- no color codes to strip. */
class CM_TeeStreamBuf : public std::streambuf
{
private:
	std::streambuf* m_dest;
	CM_LogBuffer* m_owner;
	std::string m_line;

	static CM_LogLevel DetectLevel(const std::string& line)
	{
		if (line.compare(0, 7, "Error: ") == 0) {
			return CM_LogLevel::ERROR_;
		}
		if (line.compare(0, 9, "Warning: ") == 0) {
			return CM_LogLevel::WARNING;
		}
		if (line.compare(0, 7, "Debug: ") == 0) {
			return CM_LogLevel::DEBUG;
		}
		return CM_LogLevel::MESSAGE;
	}

protected:
	int overflow(int c) override
	{
		if (c != EOF) {
			if (c == '\n') {
				m_owner->Push(DetectLevel(m_line), m_line);
				m_line.clear();
			}
			else {
				m_line += static_cast<char>(c);
			}
		}
		return m_dest->sputc(static_cast<char>(c));
	}

	int sync() override
	{
		return m_dest->pubsync();
	}

public:
	CM_TeeStreamBuf(std::streambuf* dest, CM_LogBuffer* owner) : m_dest(dest), m_owner(owner)
	{
	}
};

}  // namespace

CM_LogBuffer::CM_LogBuffer()
	: m_capacity(1000)
{
	static CM_TeeStreamBuf tee(std::cout.rdbuf(), this);
	std::cout.rdbuf(&tee);
}

CM_LogBuffer& CM_LogBuffer::Get()
{
	static CM_LogBuffer instance;
	return instance;
}

void CM_LogBuffer::Push(CM_LogLevel level, const std::string& text)
{
	std::lock_guard<std::mutex> lock(m_mutex);
	m_lines.push_back({level, text});
	if (m_lines.size() > m_capacity) {
		m_lines.pop_front();
	}
}

std::vector<CM_LogLine> CM_LogBuffer::GetLines()
{
	std::lock_guard<std::mutex> lock(m_mutex);
	return std::vector<CM_LogLine>(m_lines.begin(), m_lines.end());
}

void CM_LogBuffer::Clear()
{
	std::lock_guard<std::mutex> lock(m_mutex);
	m_lines.clear();
}

// Force the tee to be installed at static-init time, before any engine code
// runs, so nothing is missed while nothing else has called Get() yet.
namespace {
struct CM_LogBufferAutoInstall
{
	CM_LogBufferAutoInstall()
	{
		CM_LogBuffer::Get();
	}
} g_cmLogBufferAutoInstall;
}  // namespace
