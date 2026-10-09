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

/** \file gameengine/Ketsji/KX_EngineProfiler.cpp
 *  \ingroup ketsji
 */

#include "KX_EngineProfiler.h"

#include "GPU_glew.h"
#include "GPU_shader.h"
#include "GPU_render_profile.h"

#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <vector>

namespace KX_EngineProfiler {

namespace {

const char *EnvPath()
{
	const char *env = getenv("RANGE_PROFILE");
	return (env && env[0]) ? env : nullptr;
}

const int maxStages = 64;
// Skip the first frames: loading and first shader compiles are expected to be slow.
const long warmupFrames = 30;
// Averages are written every ~2 s at 60 fps, spikes included, to see what a normal frame is made of.
const int avgFrames = 120;

struct State
{
	std::string path;
	double spikeMs = 25.0;
	bool sync = false;
	bool requested = false;

	std::vector<std::string> names;
	double cpu[maxStages] = {};
	double gpu[maxStages] = {};
	double sumCpu[maxStages] = {};
	double sumGpu[maxStages] = {};
	double sumCat[maxStages] = {};
	double sumRenderCalls[GPU_RENDER_PHASE_TOT] = {};
	double sumRenderCounts[GPU_RENDER_PHASE_TOT][GPU_RENDER_KIND_TOT] = {};
	double sumWall = 0.0;
	int sumCount = 0;
	std::string notes;

	double avgMs = 0.0;
	double lastNow = 0.0;
	long frame = 0;
	long lastCounterFrame[GPU_PROFILE_TOT] = {};

	State()
	{
		const char *env = EnvPath();
		requested = (env != nullptr);
		std::error_code ec;
		const std::filesystem::path abs = std::filesystem::absolute(env ? env : "range_profile.txt", ec);
		path = ec ? std::string(env ? env : "range_profile.txt") : abs.string();
		const char *ms = getenv("RANGE_PROFILE_SPIKE_MS");
		if (ms && atof(ms) > 0.0) {
			spikeMs = atof(ms);
		}
		const char *s = getenv("RANGE_PROFILE_SYNC");
		sync = s && atoi(s) != 0;
	}

	/// Restarts the warmup and the averages, so a run turned on mid-game starts clean.
	void Reset()
	{
		std::fill(std::begin(cpu), std::end(cpu), 0.0);
		std::fill(std::begin(gpu), std::end(gpu), 0.0);
		std::fill(std::begin(sumCpu), std::end(sumCpu), 0.0);
		std::fill(std::begin(sumGpu), std::end(sumGpu), 0.0);
		std::fill(std::begin(sumCat), std::end(sumCat), 0.0);
		std::fill(std::begin(sumRenderCalls), std::end(sumRenderCalls), 0.0);
		for (auto& counts : sumRenderCounts) std::fill(std::begin(counts), std::end(counts), 0.0);
		sumWall = 0.0;
		sumCount = 0;
		notes.clear();
		avgMs = 0.0;
		lastNow = 0.0;
		frame = 0;
	}
};

State& GetState()
{
	static State state;
	return state;
}

/* GPU timestamps at stage ends. Several frames are kept in flight so the results are read once
 * the GPU is done with them, without stalling; the GPU ms land in the frame they are read. */
struct GpuStamps
{
	static const int frames = 3;
	static const int maxStamps = 32;
	GLuint queries[frames][maxStamps] = {};
	int ids[frames][maxStamps] = {};
	int count[frames] = {};
	int current = 0;
	bool enabled = false;
	bool init = false;
	bool dropPending = false;

	void BeginFrame()
	{
		if (!init) {
			init = true;
			enabled = GLEW_ARB_timer_query;
			if (enabled) {
				glGenQueries(frames * maxStamps, &queries[0][0]);
			}
		}
		if (!enabled) {
			return;
		}
		if (dropPending) {
			// Turned off and on again: the queries in flight belong to an old run.
			dropPending = false;
			std::fill(std::begin(count), std::end(count), 0);
		}
		current = (current + 1) % frames;
		// Oldest frame in the ring: written `frames - 1` frames ago.
		State& state = GetState();
		const int n = count[current];
		for (int i = 1; i < n; ++i) {
			GLuint64 t0 = 0, t1 = 0;
			glGetQueryObjectui64v(queries[current][i - 1], GL_QUERY_RESULT, &t0);
			glGetQueryObjectui64v(queries[current][i], GL_QUERY_RESULT, &t1);
			state.gpu[ids[current][i]] += (double)(t1 - t0) * 1e-6;
		}
		count[current] = 0;
		Stamp(-1);
	}

	void Stamp(int id)
	{
		if (enabled && count[current] < maxStamps) {
			ids[current][count[current]] = id;
			glQueryCounter(queries[current][count[current]++], GL_TIMESTAMP);
		}
	}
};

GpuStamps& GetGpu()
{
	static GpuStamps gpu;
	return gpu;
}

void PrintStages(FILE *f, const State& state, const double *values, double scale, double minMs)
{
	for (size_t i = 0; i < state.names.size(); ++i) {
		const double ms = values[i] * scale;
		if (ms >= minMs) {
			fprintf(f, " %s=%.2f", state.names[i].c_str(), ms);
		}
	}
}

}  // namespace

bool g_enabled = (EnvPath() != nullptr);

void SetEnabled(bool enabled)
{
	GetState().requested = enabled;
}

bool IsRequested()
{
	return GetState().requested;
}

const std::string& GetPath()
{
	return GetState().path;
}

bool SyncGpu()
{
	return g_enabled && GetState().sync;
}

void SetSyncGpu(bool sync)
{
	GetState().sync = sync;
}

int Register(const char *name)
{
	State& state = GetState();
	for (size_t i = 0; i < state.names.size(); ++i) {
		if (state.names[i] == name) {
			return (int)i;
		}
	}
	if ((int)state.names.size() >= maxStages) {
		return maxStages - 1;
	}
	state.names.emplace_back(name);
	return (int)state.names.size() - 1;
}

double NowMs()
{
	using namespace std::chrono;
	return duration<double, std::milli>(steady_clock::now().time_since_epoch()).count();
}

void AddCpu(int id, double ms)
{
	GetState().cpu[id] += ms;
}

void BeginGpuFrame()
{
	GPU_render_profile_enabled = g_enabled;
	if (g_enabled) {
		GetGpu().BeginFrame();
	}
}

void GpuStamp(int id)
{
	GetGpu().Stamp(id);
}

void Note(const std::string& text)
{
	if (g_enabled) {
		GetState().notes += " " + text;
	}
}

void EndFrame(double nowSec, const double *categoryMs, const std::string *labels, int numCategories)
{
	State& state = GetState();
	// Toggled only here, between frames, so no stage is half measured.
	if (state.requested != g_enabled) {
		g_enabled = state.requested;
		GPU_render_profile_enabled = g_enabled;
		for (int phase = 0; phase < GPU_RENDER_PHASE_TOT; ++phase) {
			GPU_render_profile_calls[phase] = 0;
			std::fill(std::begin(GPU_render_profile_counts[phase]), std::end(GPU_render_profile_counts[phase]), 0);
		}
		if (g_enabled) {
			state.Reset();
			GetGpu().dropPending = true;
			if (FILE *f = fopen(state.path.c_str(), "a")) {
				fprintf(f, "START t=%.2fs spike>%.0fms%s\n", nowSec, state.spikeMs, state.sync ? " sync" : "");
				fclose(f);
			}
		}
		return;
	}
	if (!g_enabled) {
		return;
	}
	numCategories = std::min(numCategories, maxStages);

	const double wallMs = (state.lastNow > 0.0) ? (nowSec - state.lastNow) * 1000.0 : 0.0;
	state.lastNow = nowSec;
	++state.frame;
	double totalMs = 0.0;
	for (int i = 0; i < numCategories; ++i) {
		totalMs += categoryMs[i];
	}

	if (state.frame > warmupFrames && totalMs > state.spikeMs && totalMs > state.avgMs * 2.0) {
		if (FILE *f = fopen(state.path.c_str(), "a")) {
			fprintf(f, "SPIKE t=%.2fs frame=%ld wall=%.1fms profiled=%.1fms avg=%.1fms%s |", nowSec, state.frame, wallMs,
			        totalMs, state.avgMs, state.sync ? " sync" : "");
			for (int i = 0; i < numCategories; ++i) {
				if (categoryMs[i] >= 1.0) {
					fprintf(f, " %s=%.1f", labels[i].c_str(), categoryMs[i]);
				}
			}
			fprintf(f, " | cpu:");
			PrintStages(f, state, state.cpu, 1.0, 0.1);
			fprintf(f, " | gpu:");
			PrintStages(f, state, state.gpu, 1.0, 0.1);
			if (!state.notes.empty()) {
				fprintf(f, " | added:%s", state.notes.c_str());
			}
			fprintf(f, " | shaders=%d gputex=%d imgupload=%d | frames since: shader=%ld gputex=%ld imgupload=%ld\n",
			        GPU_profile_counters[GPU_PROFILE_SHADERS], GPU_profile_counters[GPU_PROFILE_TEXTURES],
			        GPU_profile_counters[GPU_PROFILE_IMAGE_UPLOADS],
			        state.frame - state.lastCounterFrame[0], state.frame - state.lastCounterFrame[1],
			        state.frame - state.lastCounterFrame[2]);
			fclose(f);
		}
	}

	if (state.frame > warmupFrames) {
		state.sumWall += wallMs;
		for (int phase = 0; phase < GPU_RENDER_PHASE_TOT; ++phase) {
			state.sumRenderCalls[phase] += GPU_render_profile_calls[phase];
			for (int kind = 0; kind < GPU_RENDER_KIND_TOT; ++kind) {
				state.sumRenderCounts[phase][kind] += GPU_render_profile_counts[phase][kind];
			}
		}
		for (int i = 0; i < numCategories; ++i) {
			state.sumCat[i] += categoryMs[i];
		}
		for (int i = 0; i < maxStages; ++i) {
			state.sumCpu[i] += state.cpu[i];
			state.sumGpu[i] += state.gpu[i];
		}
		if (++state.sumCount == avgFrames) {
			if (FILE *f = fopen(state.path.c_str(), "a")) {
				const double n = (double)avgFrames;
				fprintf(f, "AVG t=%.2fs frames=%d wall=%.1fms fps=%.1f%s |", nowSec, avgFrames, state.sumWall / n,
				        1000.0 * n / std::max(state.sumWall, 1.0), state.sync ? " sync" : "");
				for (int i = 0; i < numCategories; ++i) {
					if (state.sumCat[i] / n >= 0.1) {
						fprintf(f, " %s=%.1f", labels[i].c_str(), state.sumCat[i] / n);
					}
				}
				fprintf(f, " | cpu:");
				PrintStages(f, state, state.sumCpu, 1.0 / n, 0.05);
				fprintf(f, " | gpu:");
				PrintStages(f, state, state.sumGpu, 1.0 / n, 0.05);
				static const char *phases[] = {"object", "shadow", "lights", "probes", "damage", "skinning"};
				static const char *kinds[] = {"float1", "float2", "float3", "float4", "matrix3", "matrix4", "integer", "sampler", "mul", "inverse"};
				fprintf(f, " | uploads:");
				for (int phase = 0; phase < GPU_RENDER_PHASE_TOT; ++phase) {
					fprintf(f, " %s.calls=%.2f", phases[phase], state.sumRenderCalls[phase] / n);
					for (int kind = 0; kind < GPU_RENDER_KIND_TOT; ++kind) {
						fprintf(f, " %s.%s=%.2f", phases[phase], kinds[kind], state.sumRenderCounts[phase][kind] / n);
					}
				}
				fprintf(f, "\n");
				fclose(f);
			}
			std::fill(std::begin(state.sumRenderCalls), std::end(state.sumRenderCalls), 0.0);
			for (auto& counts : state.sumRenderCounts) std::fill(std::begin(counts), std::end(counts), 0.0);
			state.sumWall = 0.0;
			std::fill(std::begin(state.sumCat), std::end(state.sumCat), 0.0);
			std::fill(std::begin(state.sumCpu), std::end(state.sumCpu), 0.0);
			std::fill(std::begin(state.sumGpu), std::end(state.sumGpu), 0.0);
			state.sumCount = 0;
		}
	}

	std::fill(std::begin(state.cpu), std::end(state.cpu), 0.0);
	std::fill(std::begin(state.gpu), std::end(state.gpu), 0.0);
	state.notes.clear();
	for (int phase = 0; phase < GPU_RENDER_PHASE_TOT; ++phase) {
		GPU_render_profile_calls[phase] = 0;
		std::fill(std::begin(GPU_render_profile_counts[phase]), std::end(GPU_render_profile_counts[phase]), 0);
	}
	for (int i = 0; i < GPU_PROFILE_TOT; ++i) {
		if (GPU_profile_counters[i]) {
			state.lastCounterFrame[i] = state.frame;
		}
		GPU_profile_counters[i] = 0;
	}
	// Spikes barely move the average, so a run of them still stands out.
	state.avgMs = (state.avgMs == 0.0) ? totalMs : state.avgMs * 0.95 + std::min(totalMs, state.avgMs * 2.0) * 0.05;
}

}  // namespace KX_EngineProfiler
