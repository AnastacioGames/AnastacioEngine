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

/** \file RAS_ParticleBuffer.cpp
 *  \ingroup bgerast
 */

#include "RAS_ParticleBuffer.h"

#include "CM_Message.h"

#include "GPU_glew.h"

#include "BKE_colortools.h"
#include "BKE_global.h"
#include "BKE_image.h"
#include "GPU_texture.h"
#include "RAS_Texture.h"
#include "DNA_color_types.h"
#include "DNA_image_types.h"
#include "MEM_guardedalloc.h"

namespace {

// Hardcoded simulation/emitter parameters for Fase B/C -- no Python API yet (Fase D).
// World up is Z (Blender convention), matching the Fase A test grid's layout.
const float kGravityReal[3]             = {0.0f, 0.0f, -9.8f};
const float kLifetimeReal                = 3.0f;
const float kEmitterPosReal[3]          = {0.0f, 5.0f, 10.0f};
const float kEmitterRadiusReal           = 1.0f;
const float kVelocityBaseReal[3]        = {0.0f, 0.0f, 4.0f};
const float kVelocityRandomnessReal      = 2.0f;
const float kBillboardSizeReal           = 0.35f;

const unsigned int kFloatsPerParticle = 7; // position(3) + velocity(3) + age(1)

} // namespace

std::vector<float> RAS_ParticleBuffer::BuildInitialPool(unsigned int count) const
{
	// Initialize particles far below the world to avoid visible spawning on startup.
	// Stagger age per particle to spread deaths/respawns over ~m_lifetime seconds
	// instead of the whole pool falling as a rigid block and respawning in one burst.
	std::vector<float> initial(count * kFloatsPerParticle);
	for (unsigned int i = 0; i < count; ++i) {
		float *p = &initial[i * kFloatsPerParticle];
		p[0] = 0.0f;
		p[1] = 0.0f;
		p[2] = -10000.0f;
		p[3] = m_velocityBase[0];
		p[4] = m_velocityBase[1];
		p[5] = m_velocityBase[2];
		p[6] = ((float)i / (float)count) * m_lifetime;
	}
	return initial;
}

RAS_ParticleBuffer::RAS_ParticleBuffer(unsigned int particleCount)
	:m_quadVbo(0),
	m_particleCount(particleCount),
	m_readIndex(0),
	m_simTime(0.0f),
	m_valid(false)
{
	m_vbo[0] = m_vbo[1] = 0;
	m_vao[0] = m_vao[1] = 0;
	m_drawVao[0] = m_drawVao[1] = 0;

	for (int i = 0; i < 3; ++i) {
		m_gravity[i] = kGravityReal[i];
		m_emitterPos[i] = kEmitterPosReal[i];
		m_velocityBase[i] = kVelocityBaseReal[i];
	}
	m_lifetime = kLifetimeReal;
	m_emitterRadius = kEmitterRadiusReal;
	m_velocityRandomness = kVelocityRandomnessReal;
	m_billboardSize = kBillboardSizeReal;
	m_texture = 0;

	m_useSizeCurve = false;
	m_useColorCurve = false;
	m_sizeCurveTexture = 0;
	m_colorCurveTexture = 0;

	// Matches the shader's previous hardcoded vec4(1.0, 0.2, 0.8, 1.0).
	m_color[0] = 1.0f;
	m_color[1] = 0.2f;
	m_color[2] = 0.8f;
	m_color[3] = 1.0f;

	// Fase G: end-of-life color/size default equal to the start values, so no gradient is
	// visible until a script sets them explicitly -- existing scenes look unchanged.
	for (int i = 0; i < 4; ++i) {
		m_endColor[i] = m_color[i];
	}
	m_endSize = m_billboardSize;

	// Fase G: emissionAngle >= 180 keeps the existing cube-jitter velocity randomization
	// unchanged (see updateVertexSource) -- cone emission is opt-in.
	m_emissionDir[0] = 0.0f;
	m_emissionDir[1] = 0.0f;
	m_emissionDir[2] = 1.0f;
	m_emissionAngle = 180.0f;
}

RAS_ParticleBuffer::~RAS_ParticleBuffer()
{
	if (m_vao[0]) {
		glDeleteVertexArrays(2, m_vao);
	}
	if (m_drawVao[0]) {
		glDeleteVertexArrays(2, m_drawVao);
	}
	if (m_vbo[0]) {
		glDeleteBuffers(2, m_vbo);
	}
	if (m_quadVbo) {
		glDeleteBuffers(1, &m_quadVbo);
	}
	if (m_sizeCurveTexture) {
		glDeleteTextures(1, &m_sizeCurveTexture);
	}
	if (m_colorCurveTexture) {
		glDeleteTextures(1, &m_colorCurveTexture);
	}
}

bool RAS_ParticleBuffer::Create()
{
	m_shaderCache = RAS_ParticleShaderCache::Get();
	if (!m_shaderCache) {
		return false;
	}

	const std::vector<float> initial = BuildInitialPool(m_particleCount);

	glGenBuffers(2, m_vbo);
	glGenVertexArrays(2, m_vao);

	const GLsizeiptr bufferSize = (GLsizeiptr)(m_particleCount * kFloatsPerParticle * sizeof(float));
	const GLsizei stride = (GLsizei)(kFloatsPerParticle * sizeof(float));

	for (int i = 0; i < 2; ++i) {
		glBindBuffer(GL_ARRAY_BUFFER, m_vbo[i]);
		glBufferData(GL_ARRAY_BUFFER, bufferSize, (i == 0) ? initial.data() : nullptr, GL_STREAM_COPY);

		glBindVertexArray(m_vao[i]);
		glBindBuffer(GL_ARRAY_BUFFER, m_vbo[i]);
		glEnableVertexAttribArray(0);
		glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, (const void *)0);
		glEnableVertexAttribArray(1);
		glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, stride, (const void *)(3 * sizeof(float)));
		glEnableVertexAttribArray(2);
		glVertexAttribPointer(2, 1, GL_FLOAT, GL_FALSE, stride, (const void *)(6 * sizeof(float)));
	}
	glBindVertexArray(0);
	glBindBuffer(GL_ARRAY_BUFFER, 0);

	// Static unit quad (triangle strip: BL, BR, TL, TR) shared by both draw VAOs -- the
	// per-instance particle position/age come from m_vbo[i] instead.
	static const float kQuadCorners[8] = {
		-0.5f, -0.5f,
		 0.5f, -0.5f,
		-0.5f,  0.5f,
		 0.5f,  0.5f,
	};
	glGenBuffers(1, &m_quadVbo);
	glBindBuffer(GL_ARRAY_BUFFER, m_quadVbo);
	glBufferData(GL_ARRAY_BUFFER, sizeof(kQuadCorners), kQuadCorners, GL_STATIC_DRAW);

	glGenVertexArrays(2, m_drawVao);
	for (int i = 0; i < 2; ++i) {
		glBindVertexArray(m_drawVao[i]);

		glBindBuffer(GL_ARRAY_BUFFER, m_quadVbo);
		glEnableVertexAttribArray(0);
		glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 2 * sizeof(float), (const void *)0);
		glVertexAttribDivisorARB(0, 0);

		glBindBuffer(GL_ARRAY_BUFFER, m_vbo[i]);
		glEnableVertexAttribArray(1);
		glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, stride, (const void *)0);
		glVertexAttribDivisorARB(1, 1);
		glEnableVertexAttribArray(2);
		glVertexAttribPointer(2, 1, GL_FLOAT, GL_FALSE, stride, (const void *)(6 * sizeof(float)));
		glVertexAttribDivisorARB(2, 1);
	}
	glBindVertexArray(0);
	glBindBuffer(GL_ARRAY_BUFFER, 0);

	m_valid = true;
	return true;
}

void RAS_ParticleBuffer::Update(float deltaTime, const mt::vec3 &worldOrigin)
{
	if (!m_valid || !m_enabled) {
		return;
	}

	m_simTime += deltaTime;

	const unsigned int writeIndex = 1 - m_readIndex;

	const float emitterPos[3] = {
		worldOrigin[0] + m_emitterPos[0],
		worldOrigin[1] + m_emitterPos[1],
		worldOrigin[2] + m_emitterPos[2]
	};

	glEnable(GL_RASTERIZER_DISCARD);
	glUseProgram(m_shaderCache->GetUpdateProgram());

	glUniform1f(m_shaderCache->GetDeltaTimeLoc(), deltaTime);
	glUniform1f(m_shaderCache->GetLifetimeLoc(), m_lifetime);
	glUniform1f(m_shaderCache->GetEmitterRadiusLoc(), m_emitterRadius);
	glUniform1f(m_shaderCache->GetVelocityRandomnessLoc(), m_velocityRandomness);
	glUniform1f(m_shaderCache->GetTimeLoc(), m_simTime);
	glUniform3fv(m_shaderCache->GetGravityLoc(), 1, m_gravity);
	glUniform3fv(m_shaderCache->GetEmitterPosLoc(), 1, emitterPos);
	glUniform3fv(m_shaderCache->GetVelocityBaseLoc(), 1, m_velocityBase);
	glUniform3fv(m_shaderCache->GetEmissionDirLoc(), 1, m_emissionDir);
	glUniform1f(m_shaderCache->GetEmissionAngleLoc(), m_emissionAngle);

	glUniform1i(m_shaderCache->GetCollisionModeLoc(), (int)m_collisionMode);
	glUniform1f(m_shaderCache->GetCollisionHeightLoc(), m_collisionHeight);
	glUniform1f(m_shaderCache->GetCollisionBounceLoc(), m_collisionBounce);
	glUniform1f(m_shaderCache->GetCollisionFrictionLoc(), m_collisionFriction);

	if (m_collisionMode == 2 /* GPU_PARTICLE_COLLISION_DEPTH */) {
		// Reuses the dedicated collider depth texture populated by objects flagged
		// use_gpu_particle_collider (KX_KetsjiEngine::RenderCollisionDepthBuffer) -- necessarily
		// one frame behind, since that pass runs during render, after this simulation step.
		// Degrades to no-op (handled in the shader via u_collisionDepthTexValid) when no
		// collider object exists in the scene yet this session.
		float viewProj[16];
		const int valid = GPU_texture_get_global_collider_depth_viewproj(viewProj);
		glUniform1i(m_shaderCache->GetCollisionDepthTexValidLoc(), valid);
		if (valid) {
			glUniformMatrix4fv(m_shaderCache->GetCollisionViewProjLoc(), 1, GL_FALSE, viewProj);
			GPUTexture *depthTex = *GPU_texture_global_collider_depth_ptr();
			glActiveTexture(GL_TEXTURE3);
			glBindTexture(GL_TEXTURE_2D, GPU_texture_opengl_bindcode(depthTex));
			glUniform1i(m_shaderCache->GetCollisionDepthTexLoc(), 3);
			glActiveTexture(GL_TEXTURE0);
		}
	}
	else {
		glUniform1i(m_shaderCache->GetCollisionDepthTexValidLoc(), 0);
	}

	glBindVertexArray(m_vao[m_readIndex]);
	glBindBufferBase(GL_TRANSFORM_FEEDBACK_BUFFER, 0, m_vbo[writeIndex]);

	glBeginTransformFeedback(GL_POINTS);
	glDrawArrays(GL_POINTS, 0, m_particleCount);
	glEndTransformFeedback();

	glBindBufferBase(GL_TRANSFORM_FEEDBACK_BUFFER, 0, 0);
	glBindVertexArray(0);
	glUseProgram(0);
	glDisable(GL_RASTERIZER_DISCARD);

	m_readIndex = writeIndex;
}

void RAS_ParticleBuffer::Draw(const mt::mat4 &view, const mt::mat4 &projection)
{
	if (!m_valid || !m_enabled) {
		return;
	}

	glUseProgram(m_shaderCache->GetDrawProgram());
	glUniformMatrix4fv(m_shaderCache->GetDrawViewLoc(), 1, GL_FALSE, (const float *)view.Data());
	glUniformMatrix4fv(m_shaderCache->GetDrawProjLoc(), 1, GL_FALSE, (const float *)projection.Data());
	glUniform1f(m_shaderCache->GetDrawLifetimeLoc(), m_lifetime);
	glUniform1f(m_shaderCache->GetDrawSizeLoc(), m_billboardSize);
	glUniform1f(m_shaderCache->GetDrawEndSizeLoc(), m_endSize);
	glUniform4fv(m_shaderCache->GetDrawColorLoc(), 1, m_color);
	glUniform4fv(m_shaderCache->GetDrawEndColorLoc(), 1, m_endColor);
	glUniform1i(m_shaderCache->GetDrawBillboardModeLoc(), (int)m_billboardMode);
	glUniform1i(m_shaderCache->GetDrawUseTextureLoc(), m_texture != 0 ? 1 : 0);
	if (m_texture != 0) {
		glActiveTexture(GL_TEXTURE0);
		glBindTexture(GL_TEXTURE_2D, m_texture);
		glUniform1i(m_shaderCache->GetDrawTextureLoc(), 0);
	}

	glUniform1i(m_shaderCache->GetDrawUseSizeCurveLoc(), m_useSizeCurve ? 1 : 0);
	if (m_useSizeCurve) {
		glActiveTexture(GL_TEXTURE1);
		glBindTexture(GL_TEXTURE_2D, m_sizeCurveTexture);
		glUniform1i(m_shaderCache->GetDrawSizeCurveTexLoc(), 1);
	}

	glUniform1i(m_shaderCache->GetDrawUseColorCurveLoc(), m_useColorCurve ? 1 : 0);
	if (m_useColorCurve) {
		glActiveTexture(GL_TEXTURE2);
		glBindTexture(GL_TEXTURE_2D, m_colorCurveTexture);
		glUniform1i(m_shaderCache->GetDrawColorCurveTexLoc(), 2);
	}
	glActiveTexture(GL_TEXTURE0);

	// Keep depth testing (occluded by scene geometry) but don't write depth, so overlapping
	// particles blend instead of z-fighting/occluding each other. Additive (GPU_PARTICLE_BLEND_ADDITIVE
	// in DNA_object_types.h, value 1) glows onto the scene for fire/sparks/electricity presets;
	// alpha (value 0, default) is opaque mix for smoke/dust.
	glEnable(GL_BLEND);
	if (m_blendMode == 1) {
		glBlendFunc(GL_SRC_ALPHA, GL_ONE);
	}
	else {
		glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
	}
	glDepthMask(GL_FALSE);

	if (m_backfaceCulling) {
		glEnable(GL_CULL_FACE);
	}

	glBindVertexArray(m_drawVao[m_readIndex]);
	glDrawArraysInstancedARB(GL_TRIANGLE_STRIP, 0, 4, m_particleCount);
	glBindVertexArray(0);

	if (m_backfaceCulling) {
		glDisable(GL_CULL_FACE);
	}

	glDepthMask(GL_TRUE);
	glDisable(GL_BLEND);
	if (m_texture != 0) {
		glBindTexture(GL_TEXTURE_2D, 0);
	}

	glUseProgram(0);
}

bool RAS_ParticleBuffer::Resize(unsigned int newCount)
{
	if (!m_valid || newCount == 0) {
		return false;
	}
	if (newCount == m_particleCount) {
		return true;
	}

	const std::vector<float> initial = BuildInitialPool(newCount);
	const GLsizeiptr bufferSize = (GLsizeiptr)(newCount * kFloatsPerParticle * sizeof(float));

	// Respecify both ping-pong buffers in place (same GL names) -- the VAOs built in Create()
	// reference these buffers by ID, not by size, so their attrib bindings stay valid. Buffer 0
	// gets the freshly staggered pool, buffer 1 is left uninitialized (it's a write target on
	// the next Update() call).
	glBindBuffer(GL_ARRAY_BUFFER, m_vbo[0]);
	glBufferData(GL_ARRAY_BUFFER, bufferSize, initial.data(), GL_STREAM_COPY);
	glBindBuffer(GL_ARRAY_BUFFER, m_vbo[1]);
	glBufferData(GL_ARRAY_BUFFER, bufferSize, nullptr, GL_STREAM_COPY);
	glBindBuffer(GL_ARRAY_BUFFER, 0);

	m_particleCount = newCount;
	m_readIndex = 0;
	return true;
}

bool RAS_ParticleBuffer::LoadTextureFromPath(const std::string &path)
{
	if (path.empty()) {
		SetTexture(0, "");
		return true;
	}

	// BKE_image_load_exists dedups by path against already-loaded Image datablocks;
	// GPU_texture_from_blender caches the GPUTexture on the Image itself, so re-loading
	// the same path repeatedly does not reload/re-upload the texture.
	Image *image = BKE_image_load_exists(G.main, path.c_str());
	if (!image) {
		CM_Error("could not load particle texture image '" << path << "'");
		return false;
	}

	GPUTexture *gputex = GPU_texture_from_blender(image, nullptr, RAS_Texture::GetTexture2DType(), false, 0.0, true);
	if (!gputex) {
		CM_Error("could not create GPU texture from particle texture image '" << path << "'");
		return false;
	}

	SetTexture((unsigned int)GPU_texture_opengl_bindcode(gputex), path);
	return true;
}

void RAS_ParticleBuffer::BakeSizeCurve(const CurveMapping *cumap)
{
	const int N = 64;
	float samples[N];

	// curvemapping_evaluateF requires the curve's table to have been built first; it's a
	// no-op if already up to date, so safe to call every bake.
	CurveMapping *mutable_cumap = const_cast<CurveMapping *>(cumap);
	curvemapping_initialize(mutable_cumap);
	for (int i = 0; i < N; ++i) {
		const float t = (float)i / (float)(N - 1);
		samples[i] = curvemapping_evaluateF(cumap, 0, t);
	}

	if (!m_sizeCurveTexture) {
		glGenTextures(1, &m_sizeCurveTexture);
	}
	glBindTexture(GL_TEXTURE_2D, m_sizeCurveTexture);
	glTexImage2D(GL_TEXTURE_2D, 0, GL_R32F, N, 1, 0, GL_RED, GL_FLOAT, samples);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
	glBindTexture(GL_TEXTURE_2D, 0);

	m_useSizeCurve = true;
}

void RAS_ParticleBuffer::BakeColorCurve(const CurveMapping *cumap)
{
	CurveMapping *mutable_cumap = const_cast<CurveMapping *>(cumap);
	curvemapping_initialize(mutable_cumap);

	float *table = nullptr;
	int size = 0;
	curvemapping_table_RGBA(cumap, &table, &size);

	if (!m_colorCurveTexture) {
		glGenTextures(1, &m_colorCurveTexture);
	}
	glBindTexture(GL_TEXTURE_2D, m_colorCurveTexture);
	glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA32F, size, 1, 0, GL_RGBA, GL_FLOAT, table);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
	glBindTexture(GL_TEXTURE_2D, 0);
	MEM_freeN(table);

	m_useColorCurve = true;
}
