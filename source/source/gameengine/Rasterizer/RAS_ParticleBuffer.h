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

/** \file RAS_ParticleBuffer.h
 *  \ingroup bgerast
 *
 * Fase C: camera-facing billboard rendering (instanced quads, view-space offset,
 * age-based fade) replacing the raw GL_POINTS draw from Fase B. Simulation (velocity,
 * gravity, age/lifetime, respawn) over a fixed-size particle pool via transform feedback
 * is unchanged, still with hardcoded emitter/physics parameters -- no Python API yet
 * (Fase D). Builds on the ping-pong buffer pipeline proven in Fase A -- see
 * relatorio-melhorias-anastacioengine.md.
 */

#ifndef __RAS_PARTICLEBUFFER_H__
#define __RAS_PARTICLEBUFFER_H__

#include "RAS_ParticleShaderCache.h"
#include "mathfu.h"

#include <memory>
#include <string>
#include <vector>

class RAS_ParticleBuffer
{
private:
	unsigned int m_vbo[2];
	unsigned int m_vao[2];
	/// Instanced-draw VAOs: quad corners (divisor 0, from m_quadVbo) + particle position/age
	/// (divisor 1, from m_vbo[i]). One per ping-pong index, rebuilt on the same buffers as m_vao.
	unsigned int m_drawVao[2];
	unsigned int m_quadVbo;
	unsigned int m_particleCount;
	/// Index of the buffer holding the most recently updated (and currently drawable) particle state.
	unsigned int m_readIndex;

	/// Fase J: compiled programs + uniform locations are shared across every emitter instead
	/// of each buffer compiling its own copy of identical GLSL source -- see
	/// RAS_ParticleShaderCache. Refcounted, so it's freed once the last emitter using it is
	/// destroyed and recompiled on demand afterward.
	std::shared_ptr<RAS_ParticleShaderCache> m_shaderCache;

	/// Accumulated simulation time, only used to vary the per-vertex respawn hash seed across cycles.
	float m_simTime;

	bool m_valid;

	float m_gravity[3];
	float m_lifetime;
	float m_emitterPos[3];
	float m_emitterRadius;
	float m_velocityBase[3];
	float m_velocityRandomness;
	float m_billboardSize;
	float m_color[4];
	/// Fase G: end-of-life color/size, lerped against m_color/m_billboardSize by particle age.
	/// Defaulted equal to the start values in the constructor, so no gradient is visible until
	/// a script sets them explicitly.
	float m_endColor[4];
	float m_endSize;
	/// Fase G: directional cone emission. m_emissionAngle is a half-angle in degrees; the
	/// existing cube jitter (m_velocityRandomness around m_velocityBase) is used unchanged when
	/// it is >= 180 (default), so existing scenes keep their exact current look.
	float m_emissionDir[3];
	float m_emissionAngle;
	/// Fase L: mirrors RangeGPUParticleSettings.use_debug_ui (set once at SetupGPUParticles time).
	bool m_debugUI = false;

	/// Fase N: runtime on/off, independent of the owning object's visibility. When false,
	/// Update()/Draw() are no-ops -- no simulation step, no draw call.
	bool m_enabled = true;

	/// Fase M: mirrors RangeGPUParticleSettings.blend_mode (GPU_PARTICLE_BLEND_*). Only affects
	/// the glBlendFunc used in Draw() -- no shader/uniform involved.
	short m_blendMode = 0;

	/// Mirrors RangeGPUParticleSettings.billboard_mode (GPU_PARTICLE_BILLBOARD_*). Passed to the
	/// draw shader as a uniform to select the vertex-shader billboard orientation branch.
	short m_billboardMode = 0;

	/// Mirrors RangeGPUParticleSettings.use_backface_culling. Toggles GL_CULL_FACE around the
	/// particle draw call -- off by default (both sides visible, matches pre-existing behavior).
	bool m_backfaceCulling = false;

	/// Fase O: collision. GPU_PARTICLE_COLLISION_NONE/GROUND/DEPTH, see DNA_object_types.h.
	short m_collisionMode = 0;
	float m_collisionHeight = 0.0f;
	float m_collisionBounce = 0.4f;
	float m_collisionFriction = 0.9f;

	/// Fase R: vortex/cone motion (tornado funnel), see RangeGPUParticleSettings.use_vortex in
	/// DNA_object_types.h and the u_useVortex branch in RAS_ParticleShaderCache's update shader.
	bool m_useVortex = false;
	float m_vortexRotationSpeed = 0.0f;
	float m_vortexRadiusTop = 0.0f;
	float m_vortexHeight = 1.0f;

	/// Fase E: optional sprite texture, GL bindcode of a GPUTexture owned by the loaded Image
	/// datablock (0 = untextured, falls back to the procedural round mask). Path kept only so
	/// the Python getter can round-trip what was set.
	unsigned int m_texture;
	std::string m_texturePath;

	/// Fase K: optional curve-driven size/color over lifetime, baked into small 1D lookup
	/// textures at game-start (see BakeSizeCurve/BakeColorCurve). GL bindcode 0 == not baked,
	/// falls back to the linear mix(start, end) in the draw shader.
	bool m_useSizeCurve;
	bool m_useColorCurve;
	unsigned int m_sizeCurveTexture;
	unsigned int m_colorCurveTexture;

	/// Fase P: optional user-supplied GLSL fragment "main" body (see drawFragmentPreamble in
	/// RAS_ParticleShaderCache.cpp), replacing the built-in sprite color/mask logic entirely.
	/// Empty = default look. Changing it swaps m_shaderCache for a differently-keyed one (see
	/// SetCustomFragShader) rather than mutating the shared cache in place.
	std::string m_customFragShader;

	/// Fase P: source path for m_customFragShader, hot-reloaded from disk (see
	/// PollFragShaderReload). Empty when no external script is in use.
	std::string m_fragShaderPath;
	/// Last seen mtime of m_fragShaderPath (0 if never successfully loaded), used to detect
	/// on-disk edits without re-reading the file's contents every poll.
	long m_fragShaderMTime = 0;
	/// Seconds since the last hot-reload check, so PollFragShaderReload only stats the file a
	/// few times a second instead of every Update() call.
	float m_fragShaderPollAccum = 0.0f;

	/// Builds a staggered-age initial pool (position/velocity/age, 7 floats/particle) for
	/// `count` particles, same layout as Create()'s inline version -- shared with Resize().
	std::vector<float> BuildInitialPool(unsigned int count) const;

public:
	RAS_ParticleBuffer(unsigned int particleCount);
	~RAS_ParticleBuffer();

	/// Compiles the shaders and allocates the double-buffered VBOs/VAOs with a staggered-age pool.
	bool Create();

	/// Runs one transform feedback pass (gravity integration + age/respawn) and swaps the read buffer.
	/// worldOrigin is the owning object's world position (or (0,0,0) for a scene-fixed emitter);
	/// the actual emission point uploaded to the shader is worldOrigin + m_emitterPos, so
	/// m_emitterPos itself stays a local-space offset editable via Get/SetEmitterPos without
	/// drifting as the owner moves.
	void Update(float deltaTime, const mt::vec3 &worldOrigin);

	/// Draws the current particle set as camera-facing billboards (instanced quads, view-space
	/// offset so the quad always faces the camera without needing separate right/up uniforms).
	void Draw(const mt::mat4 &view, const mt::mat4 &projection);

	bool Ok() const
	{
		return m_valid;
	}

	/// Fase D: Python-tunable emitter/physics/appearance parameters. Setters just write the
	/// member -- Update()/Draw() re-upload every uniform each call, so no recompile/recreate needed.
	const float *GetGravity() const { return m_gravity; }
	void SetGravity(const float *v) { m_gravity[0] = v[0]; m_gravity[1] = v[1]; m_gravity[2] = v[2]; }

	float GetLifetime() const { return m_lifetime; }
	void SetLifetime(float v) { m_lifetime = v; }

	/// Local-space offset from the owning object's world position (see Update()), not an
	/// absolute world position.
	const float *GetEmitterPos() const { return m_emitterPos; }
	void SetEmitterPos(const float *v) { m_emitterPos[0] = v[0]; m_emitterPos[1] = v[1]; m_emitterPos[2] = v[2]; }

	float GetEmitterRadius() const { return m_emitterRadius; }
	void SetEmitterRadius(float v) { m_emitterRadius = v; }

	const float *GetVelocityBase() const { return m_velocityBase; }
	void SetVelocityBase(const float *v) { m_velocityBase[0] = v[0]; m_velocityBase[1] = v[1]; m_velocityBase[2] = v[2]; }

	float GetVelocityRandomness() const { return m_velocityRandomness; }
	void SetVelocityRandomness(float v) { m_velocityRandomness = v; }

	float GetBillboardSize() const { return m_billboardSize; }
	void SetBillboardSize(float v) { m_billboardSize = v; }

	const float *GetColor() const { return m_color; }
	void SetColor(const float *v) { m_color[0] = v[0]; m_color[1] = v[1]; m_color[2] = v[2]; m_color[3] = v[3]; }

	/// Fase G: end-of-life color/size gradient and directional cone emission.
	const float *GetEndColor() const { return m_endColor; }
	void SetEndColor(const float *v) { m_endColor[0] = v[0]; m_endColor[1] = v[1]; m_endColor[2] = v[2]; m_endColor[3] = v[3]; }

	float GetEndSize() const { return m_endSize; }
	void SetEndSize(float v) { m_endSize = v; }

	const float *GetEmissionDirection() const { return m_emissionDir; }
	void SetEmissionDirection(const float *v) { m_emissionDir[0] = v[0]; m_emissionDir[1] = v[1]; m_emissionDir[2] = v[2]; }

	float GetEmissionAngle() const { return m_emissionAngle; }

	/// Fase L: whether "Live Debug UI" was checked on this emitter's settings at conversion time.
	bool GetDebugUI() const { return m_debugUI; }
	void SetDebugUI(bool v) { m_debugUI = v; }

	/// Fase N: runtime on/off, independent of the owning object's visibility (see KX_GameObject
	/// GetVisible() -- both gates are checked before Update()/Draw() run).
	bool GetEnabled() const { return m_enabled; }
	void SetEnabled(bool v) { m_enabled = v; }
	void SetEmissionAngle(float v) { m_emissionAngle = v; }

	/// Fase M: GPU_PARTICLE_BLEND_ALPHA (default) or GPU_PARTICLE_BLEND_ADDITIVE, see DNA_object_types.h.
	short GetBlendMode() const { return m_blendMode; }
	void SetBlendMode(short v) { m_blendMode = v; }

	/// GPU_PARTICLE_BILLBOARD_CAMERA_FACING (default) or GPU_PARTICLE_BILLBOARD_VERTICAL, see DNA_object_types.h.
	short GetBillboardMode() const { return m_billboardMode; }
	void SetBillboardMode(short v) { m_billboardMode = v; }

	bool GetBackfaceCulling() const { return m_backfaceCulling; }
	void SetBackfaceCulling(bool v) { m_backfaceCulling = v; }

	/// Fase O: collision. See GPU_PARTICLE_COLLISION_* in DNA_object_types.h.
	short GetCollisionMode() const { return m_collisionMode; }
	void SetCollisionMode(short v) { m_collisionMode = v; }

	float GetCollisionHeight() const { return m_collisionHeight; }
	void SetCollisionHeight(float v) { m_collisionHeight = v; }

	float GetCollisionBounce() const { return m_collisionBounce; }
	void SetCollisionBounce(float v) { m_collisionBounce = v; }

	float GetCollisionFriction() const { return m_collisionFriction; }
	void SetCollisionFriction(float v) { m_collisionFriction = v; }

	/// Fase R: vortex/cone motion. See RangeGPUParticleSettings.use_vortex in DNA_object_types.h.
	bool GetUseVortex() const { return m_useVortex; }
	void SetUseVortex(bool v) { m_useVortex = v; }

	float GetVortexRotationSpeed() const { return m_vortexRotationSpeed; }
	void SetVortexRotationSpeed(float v) { m_vortexRotationSpeed = v; }

	float GetVortexRadiusTop() const { return m_vortexRadiusTop; }
	void SetVortexRadiusTop(float v) { m_vortexRadiusTop = v; }

	float GetVortexHeight() const { return m_vortexHeight; }
	void SetVortexHeight(float v) { m_vortexHeight = v; }

	/// Fase F: pool size, resizable at runtime via Resize() (respecifies m_vbo[2] in place,
	/// VAOs/programs untouched -- see Resize()).
	unsigned int GetParticleCount() const { return m_particleCount; }

	/// Respecifies m_vbo[2] for a new particle count with a freshly staggered-age pool (same
	/// layout as Create()). Returns false and leaves the buffer unchanged if newCount == 0.
	/// No-op if newCount == m_particleCount. Must be called after Create() succeeded.
	bool Resize(unsigned int newCount);

	/// Fase E: sprite texture. glBindcode 0 clears it (back to the procedural round mask).
	unsigned int GetTexture() const { return m_texture; }
	const std::string &GetTexturePath() const { return m_texturePath; }
	void SetTexture(unsigned int glBindcode, const std::string &path) { m_texture = glBindcode; m_texturePath = path; }

	/// Loads (or clears, for an empty path) the sprite texture from a Blender-relative
	/// filepath via BKE_image_load_exists + GPU_texture_from_blender, then calls SetTexture().
	/// Shared by KX_ParticleSystem::pyattr_set_texture and the DNA gpu_particles
	/// bridging at scene conversion time. Returns false (buffer left unchanged) on load failure.
	bool LoadTextureFromPath(const std::string &path);

	/// Fase K: bakes a Blender CurveMapping into a small lookup texture sampled by lifeFrac in
	/// the draw shader. Safe to call repeatedly (e.g. every SetupGPUParticles()) -- reuses the
	/// existing GL texture name if already allocated.
	void BakeSizeCurve(const struct CurveMapping *cumap);
	void BakeColorCurve(const struct CurveMapping *cumap);
	/// Disables curve sampling (falls back to linear mix) without freeing the GL texture, so a
	/// later re-enable doesn't need to reallocate.
	void ClearSizeCurve() { m_useSizeCurve = false; }
	void ClearColorCurve() { m_useColorCurve = false; }

	/// Fase P: custom fragment shader script. See drawFragmentPreamble in
	/// RAS_ParticleShaderCache.cpp for the varyings/uniforms available to the script and the
	/// contract (must write `fragColor`). Empty string restores the default look.
	const std::string &GetCustomFragShader() const { return m_customFragShader; }
	/// Recompiles (or looks up an already-compiled cache for identical text) immediately, so a
	/// failed compile is reported right away rather than silently on the next Draw(). Returns
	/// false (buffer's shader cache left unchanged) if compilation fails; check CM_Error output
	/// for the GLSL compiler log.
	bool SetCustomFragShader(const std::string &source);

	/// Fase P: loads (or clears, for an empty path) the custom fragment shader from an external
	/// .glsl file -- path may use Blender's blend-relative "//" convention, same as
	/// LoadTextureFromPath. Returns false (buffer's shader cache left unchanged) on read or
	/// compile failure. Subsequent Update() calls poll the file's mtime and hot-reload on change
	/// (see PollFragShaderReload).
	bool LoadFragShaderFromPath(const std::string &path);
	const std::string &GetFragShaderPath() const { return m_fragShaderPath; }

	/// Checks (at most a few times a second) whether m_fragShaderPath changed on disk since it
	/// was last loaded, and reloads it if so. Called from Update(); failures are logged and
	/// leave the currently-compiled shader in place rather than falling back to the default look,
	/// so a saved-but-broken edit doesn't make the effect flicker back and forth.
	void PollFragShaderReload(float deltaTime);
};

#endif // __RAS_PARTICLEBUFFER_H__
