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
 * The Original Code is Copyright (C) 2026 by Range Engine.
 * All rights reserved.
 *
 * The Original Code is: all of this file.
 *
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file KX_ParticleDebugUI.h
 *  \ingroup ketsji
 *
 * Fase L: automatic in-game ImGui overlay for objects with
 * gpu_particles.use_debug_ui checked -- no KX_PythonComponent needed. Drawn straight from
 * KX_KetsjiEngine::EndFrame() for every object in KX_Scene::GetGpuParticleObjects() whose
 * RAS_ParticleBuffer has GetDebugUI() true. See relatorio-melhorias-anastacioengine.md.
 */

#ifndef __KX_PARTICLEDEBUGUI_H__
#define __KX_PARTICLEDEBUGUI_H__

class KX_GameObject;
class RAS_ParticleBuffer;

namespace KX_ParticleDebugUI {

/// Draws the ImGui window for one emitter object, writing slider/color-picker changes straight
/// into the RAS_ParticleBuffer (visible next frame, no recompile/recreate needed). Returns true
/// on the frame the "Apply to .blend" button is clicked.
bool Draw(KX_GameObject *gameobj, RAS_ParticleBuffer *buffer);

/// Pushes the buffer's current values back into bpy.data.objects[name].gpu_particles when the
/// "bpy" module is importable (embedded editor Play, same process as Blender), or into a
/// gpu_particles_debug.json sidecar next to the .blend otherwise (standalone RangeRuntime.exe,
/// no bpy there) -- picked up by properties_particle.py's load_post handler / "Import Debug
/// Values" operator.
void ApplyToBlend(KX_GameObject *gameobj, RAS_ParticleBuffer *buffer);

}  // namespace KX_ParticleDebugUI

#endif  // __KX_PARTICLEDEBUGUI_H__
