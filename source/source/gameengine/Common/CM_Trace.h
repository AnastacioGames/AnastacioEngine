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

/** \file CM_Trace.h
 *  \ingroup common
 *
 * Range Trace: opt-in session log of what the game loads and what it actually uses.
 * RANGE_TRACE=<folder> turns it on and writes <folder>/trace.jsonl, one JSON event per line;
 * RANGE_TRACE_MODULES=load,usage,... picks the modules ("all" or unset = every module).
 * tools/debug/relatorio_trace.py turns the folder into a report. Off, each hook costs one branch.
 * See docs/range-trace.md.
 */

#ifndef __CM_TRACE_H__
#define __CM_TRACE_H__

#include <string>

enum CM_TraceModule {
	/// Everything converted at load (scenes, objects, meshes, materials) and its cost.
	CM_TRACE_LOAD = 1 << 0,
	/// First time each object is drawn (camera or shadow) and each image is sent to the GPU.
	CM_TRACE_USAGE = 1 << 1,
	/// One line per frame with its time by profiler category (spikes and sector costs).
	CM_TRACE_FRAMES = 1 << 2,
	/// Camera on a curve at constant speed, set by RANGE_TRACE_RAIL=scene;curve;camera;seconds[;reverse|forward[;auto|none|object[;KEY+seconds]]].
	CM_TRACE_SECTOR = 1 << 3,
};

/// Bit mask of the modules on; 0 when RANGE_TRACE is unset.
int CM_TraceModules();

inline bool CM_TraceOn(CM_TraceModule module)
{
	return (CM_TraceModules() & module) != 0;
}

/// Frame number written with each event (set once per frame by the engine).
void CM_TraceSetFrame(long frame);

/** Writes one event: {"t":seconds,"f":frame,"ev":event,<fields>}.
 * \param fields JSON members without the braces, e.g. "\"name\":\"Cube\",\"ms\":1.5" (may be empty).
 */
void CM_TraceEvent(const char *event, const std::string& fields);

/// JSON string literal (quoted and escaped).
std::string CM_TraceStr(const std::string& text);

/// Marks the end of a game run (the editor may start another one in the same file).
void CM_TraceEnd();

#endif  // __CM_TRACE_H__
