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

/** \file gameengine/Common/CM_Trace.cpp
 *  \ingroup common
 */

#include "CM_Trace.h"

#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <mutex>
#include <sstream>

namespace {

const struct {
	const char *name;
	int bit;
} moduleNames[] = {
	{"load", CM_TRACE_LOAD},
	{"usage", CM_TRACE_USAGE},
};

struct TraceState
{
	std::mutex mutex;
	FILE *file = nullptr;
	int modules = 0;
	std::atomic<long> frame{0};
	std::chrono::steady_clock::time_point origin = std::chrono::steady_clock::now();

	TraceState()
	{
		const char *dir = getenv("RANGE_TRACE");
		if (!dir || !dir[0]) {
			return;
		}

		const char *list = getenv("RANGE_TRACE_MODULES");
		std::string names = (list && list[0]) ? list : "all";
		if (names == "all") {
			for (const auto& entry : moduleNames) {
				modules |= entry.bit;
			}
		}
		else {
			std::stringstream stream(names);
			std::string name;
			while (std::getline(stream, name, ',')) {
				for (const auto& entry : moduleNames) {
					if (name == entry.name) {
						modules |= entry.bit;
					}
				}
			}
		}
		if (!modules) {
			return;
		}

		std::error_code ec;
		std::filesystem::create_directories(dir, ec);
		const std::string path = (std::filesystem::path(dir) / "trace.jsonl").string();
		file = fopen(path.c_str(), "w");
		if (!file) {
			modules = 0;
			return;
		}

		std::string on;
		for (const auto& entry : moduleNames) {
			if (modules & entry.bit) {
				on += std::string(on.empty() ? "" : ",") + CM_TraceStr(entry.name);
			}
		}
		fprintf(file, "{\"t\":0,\"f\":0,\"ev\":\"session\",\"version\":1,\"modules\":[%s]}\n", on.c_str());
		fflush(file);
	}
};

TraceState& GetTrace()
{
	static TraceState state;
	return state;
}

}  // namespace

int CM_TraceModules()
{
	static const int modules = GetTrace().modules;
	return modules;
}

void CM_TraceSetFrame(long frame)
{
	GetTrace().frame.store(frame, std::memory_order_relaxed);
}

void CM_TraceEvent(const char *event, const std::string& fields)
{
	TraceState& trace = GetTrace();
	const double t = std::chrono::duration<double>(std::chrono::steady_clock::now() - trace.origin).count();
	std::lock_guard<std::mutex> lock(trace.mutex);
	if (!trace.file) {
		return;
	}
	fprintf(trace.file, "{\"t\":%.4f,\"f\":%ld,\"ev\":\"%s\"%s%s}\n", t, trace.frame.load(std::memory_order_relaxed),
	        event, fields.empty() ? "" : ",", fields.c_str());
	// Flushed per event so a crash keeps the log; events are rare (load and first uses).
	fflush(trace.file);
}

std::string CM_TraceStr(const std::string& text)
{
	std::string out = "\"";
	for (const unsigned char c : text) {
		switch (c) {
			case '"': out += "\\\""; break;
			case '\\': out += "\\\\"; break;
			case '\n': out += "\\n"; break;
			case '\r': out += "\\r"; break;
			case '\t': out += "\\t"; break;
			default:
				if (c < 0x20) {
					char buf[8];
					snprintf(buf, sizeof(buf), "\\u%04x", c);
					out += buf;
				}
				else {
					out += (char)c;
				}
		}
	}
	return out + "\"";
}

void CM_TraceEnd()
{
	if (CM_TraceModules()) {
		CM_TraceEvent("end", "");
	}
}
