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

/** \file KX_SimulationPipeline.h
 *  \ingroup ketsji
 *
 * Plano 7, unidade 1: extração pura (sem mudança de comportamento) do laço de
 * simulação por cena de KX_KetsjiEngine::NextFrame() -- atividade, animação,
 * lógica, as tres passadas de UpdateParents(), física e partículas GPU -- para
 * a classe KX_SimulationPipeline abaixo, no mesmo padrão de KX_ShadowRenderer
 * (Plano 5) e KX_RenderPipeline (Plano 6): reaproveita getters existentes de
 * KX_KetsjiEngine e usa friend class para o restante do estado compartilhado
 * ainda sem getter. Ordem e comportamento permanecem idênticos aos anteriores;
 * gerenciamento de cenas agendadas (ProcessScheduledScenes) e debug-render
 * ficam fora desta unidade (próximas unidades do Plano 7).
 */

#ifndef __KX_SIMULATIONPIPELINE_H__
#define __KX_SIMULATIONPIPELINE_H__

class KX_Scene;
class KX_KetsjiEngine;

/** Owns the per-frame, per-scene simulation loop extracted out of KX_KetsjiEngine (Plano 7 of
 * the Ketsji modernization program, see docs/ketsji-engine-modernization-plan.md): object
 * activity, animation, logic (sensors/controllers/actuators), the three interleaved
 * SG_Node::UpdateParents() passes, physics stepping and GPU particle emitter update.
 *
 * This is a pure extraction: behavior and call order are unchanged from the previous
 * KX_KetsjiEngine::NextFrame() loop. It still reaches back into KX_KetsjiEngine for shared
 * engine state (profiling logger, animation/physics timers, needsAnimation/needsParents flags)
 * rather than owning independent copies. */
class KX_SimulationPipeline
{
	KX_KetsjiEngine *m_engine;

public:
	explicit KX_SimulationPipeline(KX_KetsjiEngine *engine);
	~KX_SimulationPipeline() = default;

	/// Run one simulation frame for every scene: activity, animation, logic, scenegraph and
	/// physics update, then GPU particle emitters.
	void Update();
};

#endif  // __KX_SIMULATIONPIPELINE_H__
