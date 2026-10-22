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
#include <map>

#ifdef _WIN32
#  ifndef NOMINMAX
#    define NOMINMAX
#  endif
#  include <windows.h>
#  ifndef PSAPI_VERSION
#    define PSAPI_VERSION 2 /* GetProcessMemoryInfo from kernel32, no psapi.lib */
#  endif
#  include <psapi.h>
#else
#  include <unistd.h>
#endif
#include <mutex>
#include <sstream>

namespace {

const struct {
	const char *name;
	int bit;
} moduleNames[] = {
	{"load", CM_TRACE_LOAD},
	{"usage", CM_TRACE_USAGE},
	{"frames", CM_TRACE_FRAMES},
	{"sector", CM_TRACE_SECTOR},
	{"work", CM_TRACE_WORK},
	{"scripts", CM_TRACE_SCRIPTS},
	{"runtime", CM_TRACE_RUNTIME},
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

namespace {
/// Script time of the current frame: name -> (ms, calls). Scripts run on the main thread.
std::map<std::string, std::pair<double, int>>& ScriptSums()
{
	static std::map<std::string, std::pair<double, int>> sums;
	return sums;
}

double TraceNowMs()
{
	return std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now().time_since_epoch()).count();
}
}  // namespace

void CM_TraceScriptAdd(const std::string& name, double ms)
{
	std::pair<double, int>& sum = ScriptSums()[name];
	sum.first += ms;
	sum.second++;
}

void CM_TraceScriptsFlush()
{
	std::map<std::string, std::pair<double, int>>& sums = ScriptSums();
	if (sums.empty()) {
		return;
	}
	std::string fields = "\"c\":{";
	bool first = true;
	char buf[64];
	for (const auto& item : sums) {
		// Below 0.02 ms per frame it is noise; the report sums the frames for the session totals.
		if (item.second.first < 0.02) {
			continue;
		}
		snprintf(buf, sizeof(buf), ":[%.3f,%d]", item.second.first, item.second.second);
		fields += (first ? "" : ",") + CM_TraceStr(item.first) + buf;
		first = false;
	}
	sums.clear();
	if (!first) {
		CM_TraceEvent("scripts", fields + "}");
	}
}

void CM_TraceMemorySample()
{
	static double last = -1.0;
	const double now = TraceNowMs();
	if (last >= 0.0 && now - last < 1000.0) {
		return;
	}
	last = now;
	double mb = 0.0;
#ifdef _WIN32
	PROCESS_MEMORY_COUNTERS counters;
	if (GetProcessMemoryInfo(GetCurrentProcess(), &counters, sizeof(counters))) {
		mb = counters.WorkingSetSize / (1024.0 * 1024.0);
	}
#else
	FILE *statm = fopen("/proc/self/statm", "r");
	if (statm) {
		long pages = 0, resident = 0;
		if (fscanf(statm, "%ld %ld", &pages, &resident) == 2) {
			mb = resident * (double)sysconf(_SC_PAGESIZE) / (1024.0 * 1024.0);
		}
		fclose(statm);
	}
#endif
	char buf[48];
	snprintf(buf, sizeof(buf), "\"mb\":%.1f", mb);
	CM_TraceEvent("memory", buf);
}

CM_TraceScriptScope::CM_TraceScriptScope(const std::string& name)
    :m_name(CM_TraceOn(CM_TRACE_SCRIPTS) ? &name : nullptr),
    m_start(m_name ? TraceNowMs() : 0.0)
{
}

CM_TraceScriptScope::~CM_TraceScriptScope()
{
	if (m_name) {
		CM_TraceScriptAdd(*m_name, TraceNowMs() - m_start);
	}
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
