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

/** \file RAS_ParticleShaderCache.h
 *  \ingroup bgerast
 *
 * Fase J: the GLSL source for the particle update (transform feedback) and draw programs is
 * identical across every RAS_ParticleBuffer instance -- only per-instance uniform *values*
 * (emitter position, gravity, color, ...) differ. This class compiles both programs once and
 * is shared (refcounted) across every emitter, instead of each RAS_ParticleBuffer::Create()
 * recompiling the same source from scratch.
 */

#ifndef __RAS_PARTICLESHADERCACHE_H__
#define __RAS_PARTICLESHADERCACHE_H__

#include "RAS_TransformFeedbackShader.h"

#include <memory>
#include <string>

class RAS_ParticleShaderCache
{
private:
	std::unique_ptr<RAS_TransformFeedbackShader> m_updateShader;
	unsigned int m_drawProgram;

	int m_drawViewLoc, m_drawProjLoc, m_drawLifetimeLoc, m_drawSizeLoc, m_drawColorLoc;
	int m_drawTextureLoc, m_drawUseTextureLoc, m_drawEndColorLoc, m_drawEndSizeLoc;
	int m_drawBillboardModeLoc;
	/// Fase P: animated custom fragment scripts (see custom_frag_shader below) can read this.
	int m_drawTimeLoc;

	/// Fase K: optional curve-driven size/color over lifetime.
	int m_drawUseSizeCurveLoc, m_drawSizeCurveTexLoc, m_drawUseColorCurveLoc, m_drawColorCurveTexLoc;

	int m_deltaTimeLoc, m_lifetimeLoc, m_emitterRadiusLoc, m_velocityRandomnessLoc;
	int m_timeLoc, m_gravityLoc, m_emitterPosLoc, m_velocityBaseLoc;
	int m_emissionDirLoc, m_emissionAngleLoc;

	/// Fase O: collision (Ground Plane / Screen-Space).
	int m_collisionModeLoc, m_collisionHeightLoc, m_collisionBounceLoc, m_collisionFrictionLoc;
	int m_collisionViewProjLoc, m_collisionDepthTexLoc, m_collisionDepthTexValidLoc;

	bool m_valid;

	/// Fase P: compiles both programs, with an optional user-supplied GLSL fragment "main" body
	/// (see custom_frag_shader in DNA_object_types.h) replacing the built-in sprite color/mask
	/// logic. Empty = default draw fragment shader, unchanged from before Fase P. Only called by
	/// Get() -- use Get() to obtain an instance.
	explicit RAS_ParticleShaderCache(const std::string &customFragShader);

public:
	~RAS_ParticleShaderCache();

	bool Ok() const { return m_valid; }

	unsigned int GetUpdateProgram() const { return m_updateShader->GetProgram(); }
	unsigned int GetDrawProgram() const { return m_drawProgram; }

	int GetDrawViewLoc() const { return m_drawViewLoc; }
	int GetDrawProjLoc() const { return m_drawProjLoc; }
	int GetDrawLifetimeLoc() const { return m_drawLifetimeLoc; }
	int GetDrawSizeLoc() const { return m_drawSizeLoc; }
	int GetDrawColorLoc() const { return m_drawColorLoc; }
	int GetDrawTextureLoc() const { return m_drawTextureLoc; }
	int GetDrawUseTextureLoc() const { return m_drawUseTextureLoc; }
	int GetDrawBillboardModeLoc() const { return m_drawBillboardModeLoc; }
	int GetDrawEndColorLoc() const { return m_drawEndColorLoc; }
	int GetDrawEndSizeLoc() const { return m_drawEndSizeLoc; }
	int GetDrawTimeLoc() const { return m_drawTimeLoc; }

	int GetDrawUseSizeCurveLoc() const { return m_drawUseSizeCurveLoc; }
	int GetDrawSizeCurveTexLoc() const { return m_drawSizeCurveTexLoc; }
	int GetDrawUseColorCurveLoc() const { return m_drawUseColorCurveLoc; }
	int GetDrawColorCurveTexLoc() const { return m_drawColorCurveTexLoc; }

	int GetDeltaTimeLoc() const { return m_deltaTimeLoc; }
	int GetLifetimeLoc() const { return m_lifetimeLoc; }
	int GetEmitterRadiusLoc() const { return m_emitterRadiusLoc; }
	int GetVelocityRandomnessLoc() const { return m_velocityRandomnessLoc; }
	int GetTimeLoc() const { return m_timeLoc; }
	int GetGravityLoc() const { return m_gravityLoc; }
	int GetEmitterPosLoc() const { return m_emitterPosLoc; }
	int GetVelocityBaseLoc() const { return m_velocityBaseLoc; }
	int GetEmissionDirLoc() const { return m_emissionDirLoc; }
	int GetEmissionAngleLoc() const { return m_emissionAngleLoc; }

	int GetCollisionModeLoc() const { return m_collisionModeLoc; }
	int GetCollisionHeightLoc() const { return m_collisionHeightLoc; }
	int GetCollisionBounceLoc() const { return m_collisionBounceLoc; }
	int GetCollisionFrictionLoc() const { return m_collisionFrictionLoc; }
	int GetCollisionViewProjLoc() const { return m_collisionViewProjLoc; }
	int GetCollisionDepthTexLoc() const { return m_collisionDepthTexLoc; }
	int GetCollisionDepthTexValidLoc() const { return m_collisionDepthTexValidLoc; }

	/// Returns a shared cache for the given custom fragment script text (empty = the default
	/// built-in look). Compiles on first call for that exact script text (or the first call
	/// after every previous RAS_ParticleBuffer referencing it was destroyed); a later call with
	/// the same text reuses the compiled program instead of recompiling. Returns nullptr if
	/// compilation fails; a later call retries rather than staying poisoned.
	static std::shared_ptr<RAS_ParticleShaderCache> Get(const std::string &customFragShader = std::string());
};

#endif // __RAS_PARTICLESHADERCACHE_H__
