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
#  include <tlhelp32.h>
#  include <dxgi1_4.h>
#  include <pdh.h>
#  include <pdhmsg.h>
#else
#  include <dirent.h>
#  include <sys/syscall.h>
#  include <time.h>
#  include <unistd.h>
#endif
#include <algorithm>
#include <condition_variable>
#include <cstring>
#include <mutex>
#include <thread>
#include <vector>
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
	{"threads", CM_TRACE_THREADS},
};

} // namespace

const char *CM_TraceGetEnv(const char *name, const char *oldName)
{
	const char *value = getenv(name);
	return (value && value[0]) ? value : getenv(oldName);
}

namespace {

struct TraceState
{
	std::mutex mutex;
	FILE *file = nullptr;
	int modules = 0;
	std::atomic<long> frame{0};
	/// Seconds since origin of the last fflush.
	double lastFlush = 0.0;
	std::chrono::steady_clock::time_point origin = std::chrono::steady_clock::now();

	TraceState()
	{
		const char *dir = CM_TraceGetEnv("GAME_TRACE", "RANGE_TRACE");
		if (!dir || !dir[0]) {
			return;
		}

		const char *list = CM_TraceGetEnv("GAME_TRACE_MODULES", "RANGE_TRACE_MODULES");
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
	/* Flushed at most every 0.25 s (and at the end), so a crash loses only the last moment. Flushing
	 * every event cost ~1.7 ms per frame with the per-frame modules, which skewed what they measure. */
	if (t - trace.lastFlush >= 0.25 || strcmp(event, "end") == 0) {
		fflush(trace.file);
		trace.lastFlush = t;
	}
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

#ifndef __EMSCRIPTEN__
namespace {

/* GPU memory and 3D engine use of this process, read once per second on a thread of its own
 * (the Windows counters can take a few ms). Negative values mean "not known here".
 * Windows: DXGI QueryVideoMemoryInfo (local = VRAM, non local = system memory the GPU uses) and
 * the "GPU Engine" counters (the same as Task Manager), both loaded at run time.
 * Linux: /proc/self/fdinfo drm-* fields (AMD, Intel; the NVIDIA driver does not write them). */
struct GpuReading
{
	double vram = -1.0, shared = -1.0, busy = -1.0;
	int integrated = -1;
};

#ifdef _WIN32
struct GpuReaderWin
{
	HMODULE dxgi = nullptr, pdh = nullptr;
	IDXGIFactory1 *factory = nullptr;
	PDH_HQUERY query = nullptr;
	PDH_HCOUNTER counter = nullptr;
	decltype(&PdhCollectQueryData) collect = nullptr;
	decltype(&PdhGetFormattedCounterArrayW) array = nullptr;
	decltype(&PdhCloseQuery) close = nullptr;
	bool primed = false;

	GpuReaderWin()
	{
		dxgi = LoadLibraryW(L"dxgi.dll");
		if (dxgi) {
			typedef HRESULT(WINAPI * CreateFactoryFn)(REFIID, void **);
			CreateFactoryFn create = (CreateFactoryFn)GetProcAddress(dxgi, "CreateDXGIFactory1");
			if (!create || FAILED(create(__uuidof(IDXGIFactory1), (void **)&factory))) {
				factory = nullptr;
			}
		}
		pdh = LoadLibraryW(L"pdh.dll");
		if (pdh) {
			auto open = (decltype(&PdhOpenQueryW))GetProcAddress(pdh, "PdhOpenQueryW");
			auto add = (decltype(&PdhAddEnglishCounterW))GetProcAddress(pdh, "PdhAddEnglishCounterW");
			collect = (decltype(&PdhCollectQueryData))GetProcAddress(pdh, "PdhCollectQueryData");
			array = (decltype(&PdhGetFormattedCounterArrayW))GetProcAddress(pdh, "PdhGetFormattedCounterArrayW");
			close = (decltype(&PdhCloseQuery))GetProcAddress(pdh, "PdhCloseQuery");
			wchar_t path[128];
			swprintf(path, 128, L"\\GPU Engine(pid_%lu_*engtype_3D)\\Utilization Percentage", GetCurrentProcessId());
			if (!(open && add && collect && array && close && open(nullptr, 0, &query) == ERROR_SUCCESS)) {
				query = nullptr;
			}
			else if (add(query, path, 0, &counter) != ERROR_SUCCESS) {
				close(query);
				query = nullptr;
			}
		}
	}

	~GpuReaderWin()
	{
		if (query) {
			close(query);
		}
		if (factory) {
			factory->Release();
		}
		if (pdh) {
			FreeLibrary(pdh);
		}
		if (dxgi) {
			FreeLibrary(dxgi);
		}
	}

	GpuReading Read()
	{
		GpuReading r;
		if (factory) {
			// Sum over the adapters (a hybrid notebook may use both); the adapter with the most
			// local memory in use says whether the game runs on an integrated GPU.
			double vram = 0.0, shared = 0.0, most = -1.0;
			bool any = false;
			IDXGIAdapter1 *adapter = nullptr;
			for (UINT i = 0; factory->EnumAdapters1(i, &adapter) != DXGI_ERROR_NOT_FOUND; ++i) {
				DXGI_ADAPTER_DESC1 desc;
				IDXGIAdapter3 *adapter3 = nullptr;
				if (SUCCEEDED(adapter->GetDesc1(&desc)) && !(desc.Flags & DXGI_ADAPTER_FLAG_SOFTWARE) &&
				    SUCCEEDED(adapter->QueryInterface(__uuidof(IDXGIAdapter3), (void **)&adapter3)))
				{
					DXGI_QUERY_VIDEO_MEMORY_INFO local, nonLocal;
					if (SUCCEEDED(adapter3->QueryVideoMemoryInfo(0, DXGI_MEMORY_SEGMENT_GROUP_LOCAL, &local)) &&
					    SUCCEEDED(adapter3->QueryVideoMemoryInfo(0, DXGI_MEMORY_SEGMENT_GROUP_NON_LOCAL, &nonLocal)))
					{
						any = true;
						vram += local.CurrentUsage / (1024.0 * 1024.0);
						shared += nonLocal.CurrentUsage / (1024.0 * 1024.0);
						const double used = (double)local.CurrentUsage + nonLocal.CurrentUsage;
						if (used > most) {
							most = used;
							// Integrated GPUs get at most a small carve-out as dedicated memory.
							r.integrated = desc.DedicatedVideoMemory < (size_t)512 * 1024 * 1024 ? 1 : 0;
						}
					}
					adapter3->Release();
				}
				adapter->Release();
			}
			if (any) {
				r.vram = vram;
				r.shared = shared;
			}
		}
		if (query && collect(query) == ERROR_SUCCESS) {
			if (primed) {
				DWORD size = 0, count = 0;
				if (array(counter, PDH_FMT_DOUBLE, &size, &count, nullptr) == PDH_MORE_DATA && size) {
					std::vector<unsigned char> buffer(size);
					PDH_FMT_COUNTERVALUE_ITEM_W *items = (PDH_FMT_COUNTERVALUE_ITEM_W *)buffer.data();
					if (array(counter, PDH_FMT_DOUBLE, &size, &count, items) == ERROR_SUCCESS) {
						// One instance per 3D engine of each adapter; the busiest is the GPU in use.
						double busy = 0.0;
						for (DWORD i = 0; i < count; ++i) {
							if (items[i].FmtValue.CStatus == ERROR_SUCCESS) {
								busy = std::max(busy, items[i].FmtValue.doubleValue);
							}
						}
						r.busy = std::min(busy, 100.0);
					}
				}
			}
			primed = true;  // rates need two collects
		}
		return r;
	}
};
#else
struct GpuReaderLinux
{
	double lastNs = -1.0, lastWall = 0.0;

	static double ToMb(double value, const char *unit)
	{
		if (strncmp(unit, "GiB", 3) == 0) {
			return value * 1024.0;
		}
		if (strncmp(unit, "MiB", 3) == 0) {
			return value;
		}
		if (strncmp(unit, "KiB", 3) == 0) {
			return value / 1024.0;
		}
		return value / (1024.0 * 1024.0);  // bytes
	}

	GpuReading Read()
	{
		GpuReading r;
		DIR *dir = opendir("/proc/self/fdinfo");
		if (!dir) {
			return r;
		}
		// One DRM client can be open in several fds: count each client id once.
		std::vector<unsigned long long> clients;
		double vram = 0.0, shared = 0.0, ns = 0.0;
		bool anyMem = false, anyEngine = false;
		while (dirent *item = readdir(dir)) {
			if (item->d_name[0] == '.') {
				continue;
			}
			const std::string path = std::string("/proc/self/fdinfo/") + item->d_name;
			FILE *f = fopen(path.c_str(), "r");
			if (!f) {
				continue;
			}
			char line[256];
			unsigned long long client = 0;
			bool hasClient = false;
			double fdVram = 0.0, fdShared = 0.0, fdNs = 0.0;
			bool fdMem = false, fdEngine = false;
			while (fgets(line, sizeof(line), f)) {
				char key[96], unit[16] = "";
				double value = 0.0;
				if (sscanf(line, "%95[^:]: %lf %15s", key, &value, unit) < 2) {
					continue;
				}
				if (strcmp(key, "drm-client-id") == 0) {
					client = (unsigned long long)value;
					hasClient = true;
				}
				else if (strcmp(key, "drm-engine-gfx") == 0 || strcmp(key, "drm-engine-render") == 0) {
					fdNs += value;
					fdEngine = true;
				}
				else if (strncmp(key, "drm-memory-vram", 15) == 0 || strncmp(key, "drm-total-vram", 14) == 0 ||
				         strncmp(key, "drm-total-local", 15) == 0)
				{
					fdVram = std::max(fdVram, ToMb(value, unit));
					fdMem = true;
				}
				else if (strncmp(key, "drm-memory-gtt", 14) == 0 || strncmp(key, "drm-total-gtt", 13) == 0 ||
				         strncmp(key, "drm-total-system", 16) == 0)
				{
					fdShared = std::max(fdShared, ToMb(value, unit));
					fdMem = true;
				}
			}
			fclose(f);
			if (!hasClient || std::find(clients.begin(), clients.end(), client) != clients.end()) {
				continue;
			}
			clients.push_back(client);
			vram += fdVram;
			shared += fdShared;
			ns += fdNs;
			anyMem |= fdMem;
			anyEngine |= fdEngine;
		}
		closedir(dir);
		if (anyMem) {
			r.vram = vram;
			r.shared = shared;
		}
		const double wall = TraceNowMs();
		if (anyEngine) {
			if (lastNs >= 0.0 && wall > lastWall) {
				r.busy = std::min(std::max((ns - lastNs) / 1e6 / (wall - lastWall) * 100.0, 0.0), 100.0);
			}
			lastNs = ns;
			lastWall = wall;
		}
		return r;
	}
};
#endif

struct GpuSampler
{
	std::atomic<double> vramMb{-1.0}, sharedMb{-1.0}, busy3d{-1.0};
	std::atomic<int> integrated{-1};
	std::mutex mutex;
	std::condition_variable wake;
	std::thread thread;
	bool stop = false;

	void Start()
	{
		if (thread.joinable()) {
			return;
		}
		stop = false;
		thread = std::thread([this]() {
#ifdef _WIN32
			GpuReaderWin reader;
#else
			GpuReaderLinux reader;
#endif
			std::unique_lock<std::mutex> lock(mutex);
			while (!stop) {
				lock.unlock();
				const GpuReading r = reader.Read();
				vramMb = r.vram;
				sharedMb = r.shared;
				busy3d = r.busy;
				integrated = r.integrated;
				lock.lock();
				wake.wait_for(lock, std::chrono::seconds(1), [this]() { return stop; });
			}
		});
	}

	void Stop()
	{
		if (!thread.joinable()) {
			return;
		}
		{
			std::lock_guard<std::mutex> lock(mutex);
			stop = true;
		}
		wake.notify_all();
		thread.join();
		vramMb = sharedMb = busy3d = -1.0;
		integrated = -1;
	}

	~GpuSampler()
	{
		Stop();
	}
};

GpuSampler& GetGpuSampler()
{
	static GpuSampler sampler;
	return sampler;
}

}  // namespace
#endif

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
	std::string fields;
	char buf[48];
	snprintf(buf, sizeof(buf), "\"mb\":%.1f", mb);
	fields = buf;
#ifndef __EMSCRIPTEN__
	GpuSampler& gpu = GetGpuSampler();
	gpu.Start();
	const double vram = gpu.vramMb.load(), shared = gpu.sharedMb.load(), busy = gpu.busy3d.load();
	if (vram >= 0.0) {
		snprintf(buf, sizeof(buf), ",\"vram\":%.1f", vram);
		fields += buf;
	}
	if (shared >= 0.0) {
		snprintf(buf, sizeof(buf), ",\"shared\":%.1f", shared);
		fields += buf;
	}
	if (busy >= 0.0) {
		snprintf(buf, sizeof(buf), ",\"gpu3d\":%.1f", busy);
		fields += buf;
	}
	if (gpu.integrated.load() >= 0) {
		fields += gpu.integrated.load() ? ",\"igpu\":1" : ",\"igpu\":0";
	}
#endif
	CM_TraceEvent("memory", fields);
}

namespace {

#ifdef _WIN32
double FileTimeMs(const FILETIME& time)
{
	return (((unsigned long long)time.dwHighDateTime << 32) | time.dwLowDateTime) / 10000.0;
}
#endif

/// CPU time (user + kernel) of every thread of the process, in ms, by thread id.
std::map<unsigned long, double> ThreadCpuTimes()
{
	std::map<unsigned long, double> times;
#ifdef _WIN32
	const DWORD pid = GetCurrentProcessId();
	HANDLE snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
	if (snapshot == INVALID_HANDLE_VALUE) {
		return times;
	}
	THREADENTRY32 entry;
	entry.dwSize = sizeof(entry);
	for (BOOL ok = Thread32First(snapshot, &entry); ok; ok = Thread32Next(snapshot, &entry)) {
		if (entry.th32OwnerProcessID != pid) {
			continue;
		}
		HANDLE thread = OpenThread(THREAD_QUERY_LIMITED_INFORMATION, FALSE, entry.th32ThreadID);
		if (!thread) {
			continue;
		}
		FILETIME creation, exit, kernel, user;
		if (GetThreadTimes(thread, &creation, &exit, &kernel, &user)) {
			times[entry.th32ThreadID] = FileTimeMs(kernel) + FileTimeMs(user);
		}
		CloseHandle(thread);
	}
#else
	DIR *dir = opendir("/proc/self/task");
	if (!dir) {
		return times;
	}
	const double tick = 1000.0 / sysconf(_SC_CLK_TCK);
	while (dirent *item = readdir(dir)) {
		const unsigned long tid = strtoul(item->d_name, nullptr, 10);
		if (tid == 0) {
			continue;
		}
		const std::string path = std::string("/proc/self/task/") + item->d_name + "/stat";
		FILE *stat = fopen(path.c_str(), "r");
		if (!stat) {
			continue;
		}
		char line[1024];
		if (fgets(line, sizeof(line), stat)) {
			// Fields after the ")" of the name: state is field 3, utime 14, stime 15.
			const char *rest = strrchr(line, ')');
			unsigned long utime = 0, stime = 0;
			if (rest && sscanf(rest + 2, "%*c %*d %*d %*d %*d %*d %*u %*u %*u %*u %*u %lu %lu", &utime, &stime) == 2) {
				times[tid] = (utime + stime) * tick;
			}
		}
		fclose(stat);
	}
	closedir(dir);
#endif
	return times;
}

unsigned long CurrentThreadId()
{
#ifdef _WIN32
	return GetCurrentThreadId();
#elif defined(__EMSCRIPTEN__)
	return (unsigned long)std::hash<std::thread::id>()(std::this_thread::get_id());
#else
	return (unsigned long)syscall(SYS_gettid);
#endif
}

}  // namespace

namespace {
/// One "threads" event per second. Only one thread calls it at a time (the sampler, or the main
/// thread on the Web).
void SampleThreads(unsigned long mainId)
{
	static double last = -1.0;
	static std::map<unsigned long, double> previous;
	const double now = TraceNowMs();
	if (last >= 0.0 && now - last < 1000.0) {
		return;
	}
	const std::map<unsigned long, double> current = ThreadCpuTimes();
	if (last >= 0.0) {
		// Busy ms of each thread in the interval; threads that started in it count from zero.
		double total = 0.0, mainMs = 0.0;
		std::vector<std::pair<double, unsigned long>> others;
		for (const std::pair<const unsigned long, double>& item : current) {
			const std::map<unsigned long, double>::const_iterator old = previous.find(item.first);
			const double ms = item.second - (old != previous.end() ? old->second : 0.0);
			total += ms;
			if (item.first == mainId) {
				mainMs = ms;
			}
			else if (ms > 0.0) {
				others.emplace_back(ms, item.first);
			}
		}
		std::sort(others.rbegin(), others.rend());
		std::ostringstream fields;
		fields.setf(std::ios::fixed);
		fields.precision(1);
		fields << "\"wall_ms\":" << now - last << ",\"cores\":" << std::thread::hardware_concurrency()
		       << ",\"count\":" << current.size() << ",\"process_ms\":" << total << ",\"main_ms\":" << mainMs
		       << ",\"others\":[";
		for (size_t i = 0; i < others.size() && i < 16; ++i) {
			fields << (i ? "," : "") << others[i].first;
		}
		fields << "]";
		CM_TraceEvent("threads", fields.str());
	}
	last = now;
	previous = current;
}

#ifndef __EMSCRIPTEN__
/* Listing the threads walks every thread of the system (Toolhelp on Windows): ~100 ms once per
 * second, a hitch every second when done on the main thread. A sampler thread does it instead. */
struct ThreadSampler
{
	std::mutex mutex;
	std::condition_variable wake;
	std::thread thread;
	bool stop = false;

	void Stop()
	{
		if (!thread.joinable()) {
			return;
		}
		{
			std::lock_guard<std::mutex> lock(mutex);
			stop = true;
		}
		wake.notify_all();
		thread.join();
	}

	// An exit without CM_TraceEnd() must not destroy a running std::thread (std::terminate).
	~ThreadSampler()
	{
		Stop();
	}
};

ThreadSampler& GetSampler()
{
	static ThreadSampler sampler;
	return sampler;
}
#endif
}  // namespace

void CM_TraceThreadsSample()
{
#ifdef __EMSCRIPTEN__
	SampleThreads(CurrentThreadId());
#else
	ThreadSampler& sampler = GetSampler();
	if (sampler.thread.joinable()) {
		return;
	}
	sampler.stop = false;
	const unsigned long mainId = CurrentThreadId();
	sampler.thread = std::thread([&sampler, mainId]() {
		std::unique_lock<std::mutex> lock(sampler.mutex);
		while (!sampler.stop) {
			lock.unlock();
			SampleThreads(mainId);
			lock.lock();
			sampler.wake.wait_for(lock, std::chrono::seconds(1), [&sampler]() { return sampler.stop; });
		}
	});
#endif
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
#ifndef __EMSCRIPTEN__
	GetSampler().Stop();
	GetGpuSampler().Stop();
#endif
	if (CM_TraceModules()) {
		CM_TraceEvent("end", "");
	}
}
