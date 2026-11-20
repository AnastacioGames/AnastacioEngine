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

/** \file gameengine/BlenderRoutines/BL_PreviewParticles.cpp
 *  \ingroup blroutines
 *
 * The buffer setup mirrors KX_GameObject::SetupGPUParticlesBuffer / ApplyGPUParticleParams and the per-frame
 * step mirrors KX_GameObject::UpdateParticles; keep them in sync when those change.
 */

#include "BL_PreviewParticles.h"

#include "RAS_ParticleBuffer.h"
#include "RAS_ParticleShaderCache.h"
#include "KX_Globals.h"
#include "CM_Message.h"
#include "mathfu.h"

#include "DNA_mesh_types.h"
#include "DNA_meshdata_types.h"
#include "DNA_object_types.h"
#include "DNA_scene_types.h"

#include "BKE_global.h"
#include "BKE_main.h"

#include "PIL_time.h"

#include <algorithm>
#include <cstring>
#include <map>
#include <memory>
#include <vector>

namespace {

struct PreviewEmitter {
	RangeGPUParticleSettings settings;
	RangeGPUParticleSettings settingsMix;
	unsigned int flags;
	std::unique_ptr<RAS_ParticleBuffer> buffer;
	std::unique_ptr<RAS_ParticleBuffer> bufferMix;
	bool seen;
};

std::map<Object *, PreviewEmitter> g_emitters;
double g_lastTime = 0.0;

void apply_params(RAS_ParticleBuffer *buffer, const RangeGPUParticleSettings &settings)
{
	buffer->SetGravity(settings.gravity);
	buffer->SetLifetime(settings.lifetime);
	buffer->SetEmitterPos(settings.emitter_position);
	buffer->SetEmitterRadius(settings.emitter_radius);
	buffer->SetVelocityBase(settings.velocity);
	buffer->SetVelocityRandomness(settings.velocity_randomness);
	buffer->SetBillboardSize(settings.size);
	buffer->SetColor(settings.color);
	buffer->SetEndColor(settings.end_color);
	buffer->SetEndSize(settings.end_size);
	buffer->SetEmissionDirection(settings.emission_direction);
	buffer->SetEmissionAngle(settings.emission_angle);
	buffer->SetDebugUI(false);
	buffer->SetBlendMode(settings.blend_mode);
	buffer->SetBillboardMode(settings.billboard_mode);
	buffer->SetBackfaceCulling(settings.use_backface_culling != 0);
	buffer->SetEnabled(settings.disable_emission == 0);
	buffer->SetCollisionMode(settings.collision_mode);
	buffer->SetCollisionHeight(settings.collision_height);
	buffer->SetCollisionBounce(settings.collision_bounce);
	buffer->SetCollisionFriction(settings.collision_friction);
	buffer->SetUseVortex(settings.use_vortex != 0);
	buffer->SetVortexRotationSpeed(settings.vortex_rotation_speed);
	buffer->SetVortexRadiusTop(settings.vortex_radius_top);
	buffer->SetVortexHeight(settings.vortex_height);
	buffer->SetUseObjectRotation(settings.use_object_rotation != 0);
	buffer->SetBurstMode(settings.emission_mode == GPU_PARTICLE_EMISSION_BURST);
	buffer->SetBurstInterval(settings.burst_interval);
	buffer->SetDrag(settings.drag);
	const float cycles = (settings.flipbook_cycles > 0.0f || settings.flipbook_random) ? settings.flipbook_cycles : 1.0f;
	buffer->SetFlipbook(settings.flipbook_cols, settings.flipbook_rows, cycles, settings.flipbook_random != 0);
}

void setup_buffer(std::unique_ptr<RAS_ParticleBuffer> &slot, Object *ob, const RangeGPUParticleSettings &settings)
{
	slot.reset(new RAS_ParticleBuffer(settings.particle_count > 0 ? settings.particle_count : 1));
	if (!slot->Create()) {
		slot.reset();
		return;
	}

	apply_params(slot.get(), settings);

	if (settings.emit_from == GPU_PARTICLE_EMIT_VERTICES) {
		Mesh *me = (ob->type == OB_MESH) ? (Mesh *)ob->data : nullptr;
		if (me && me->mvert && me->totvert > 0) {
			std::vector<float> positions(me->totvert * 3);
			for (int i = 0; i < me->totvert; ++i) {
				positions[i * 3 + 0] = me->mvert[i].co[0];
				positions[i * 3 + 1] = me->mvert[i].co[1];
				positions[i * 3 + 2] = me->mvert[i].co[2];
			}
			slot->SetStaticPositions(positions);
			slot->SetModelMatrix((const float *)ob->obmat);
		}
	}

	if (settings.use_custom_frag_shader && settings.frag_shader_path[0] != '\0') {
		slot->LoadFragShaderFromPath(settings.frag_shader_path);
	}
	if (settings.particle_look != GPU_PARTICLE_LOOK_DEFAULT) {
		slot->SetCustomFragShader(RAS_GetBuiltinParticleLookSource(settings.particle_look));
	}
	slot->SetPrewarm(settings.particle_look == GPU_PARTICLE_LOOK_SMOKE ||
	                 settings.particle_look == GPU_PARTICLE_LOOK_FIRE);
	if (settings.emission_mode == GPU_PARTICLE_EMISSION_BURST && (settings.burst_flags & GPU_PARTICLE_BURST_ON_START)) {
		slot->Burst();
	}
	if (settings.texture_path[0] != '\0') {
		slot->LoadTextureFromPath(settings.texture_path);
	}
	if (settings.use_size_curve && settings.size_curve) {
		slot->BakeSizeCurve(settings.size_curve);
	}
	else {
		slot->ClearSizeCurve();
	}
	if (settings.use_color_curve && settings.color_curve) {
		slot->BakeColorCurve(settings.color_curve);
	}
	else {
		slot->ClearColorCurve();
	}
}

void step_buffer(RAS_ParticleBuffer *buffer, Object *ob, float dt, bool ground)
{
	if (!buffer) {
		return;
	}
	if (buffer->IsStatic()) {
		buffer->SetModelMatrix((const float *)ob->obmat);
	}
	if (ground && ob->gpu_particles.collision_ground_object) {
		buffer->SetCollisionHeight(ob->gpu_particles.collision_ground_object->obmat[3][2]);
	}
	/* world orientation without the scale, as KX_GameObject::NodeGetWorldOrientation */
	mt::mat3 rot = mt::mat3::Identity();
	for (int c = 0; c < 3; ++c) {
		const float len = sqrtf(ob->obmat[c][0] * ob->obmat[c][0] + ob->obmat[c][1] * ob->obmat[c][1] +
		                        ob->obmat[c][2] * ob->obmat[c][2]);
		const float inv = (len > 1e-8f) ? 1.0f / len : 0.0f;
		for (int r = 0; r < 3; ++r) {
			rot(r, c) = ob->obmat[c][r] * inv;
		}
	}
	buffer->Update(dt, mt::vec3(ob->obmat[3][0], ob->obmat[3][1], ob->obmat[3][2]), rot);
}

}  // namespace

int BL_preview_particles_draw(Scene *scene, unsigned int layers, const float viewmat[4][4], const float winmat[4][4])
{
	if (!scene || !G.main) {
		return 0;
	}
	/* relative texture/shader paths ("//") resolve against the .blend, like in the game */
	KX_SetMainPath(std::string(G.main->name));

	const double now = PIL_check_seconds_timer();
	float dt = (g_lastTime > 0.0) ? (float)(now - g_lastTime) : 0.0f;
	if (dt >= 0.002f || g_lastTime == 0.0) {
		g_lastTime = now;
	}
	else {
		dt = 0.0f;  /* a second viewport of the same frame: do not step twice */
	}
	dt = std::min(dt, 0.1f);

	for (auto &it : g_emitters) {
		it.second.seen = false;
	}

	std::vector<Object *> drawn;
	for (Base *base = (Base *)scene->base.first; base; base = base->next) {
		Object *ob = base->object;
		const unsigned int flags = ob->gameflag2 & (OB_GPU_PARTICLES | OB_GPU_PARTICLES_MIX);
		if (!flags || !(base->lay & layers) || (ob->restrictflag & OB_RESTRICT_VIEW)) {
			continue;
		}
		PreviewEmitter &em = g_emitters[ob];
		em.seen = true;
		bool fresh = false;

		const bool changed = em.flags != flags ||
		                     ((flags & OB_GPU_PARTICLES) && std::memcmp(&em.settings, &ob->gpu_particles, sizeof(em.settings)) != 0) ||
		                     ((flags & OB_GPU_PARTICLES_MIX) && std::memcmp(&em.settingsMix, &ob->gpu_particles_mix, sizeof(em.settingsMix)) != 0);
		if (changed || (!em.buffer && !em.bufferMix)) {
			em.flags = flags;
			em.settings = ob->gpu_particles;
			em.settingsMix = ob->gpu_particles_mix;
			em.buffer.reset();
			em.bufferMix.reset();
			fresh = true;
			if (flags & OB_GPU_PARTICLES) {
				setup_buffer(em.buffer, ob, ob->gpu_particles);
			}
			if (flags & OB_GPU_PARTICLES_MIX) {
				setup_buffer(em.bufferMix, ob, ob->gpu_particles_mix);
			}
		}

		if (dt > 0.0f || fresh) {
			step_buffer(em.buffer.get(), ob, dt, true);
			step_buffer(em.bufferMix.get(), ob, dt, false);
		}
		drawn.push_back(ob);
	}

	/* emitters that were deleted or turned off: free their GL buffers */
	for (auto it = g_emitters.begin(); it != g_emitters.end();) {
		it = it->second.seen ? std::next(it) : g_emitters.erase(it);
	}

	if (drawn.empty()) {
		return 0;
	}

	const mt::mat4 view((const float *)viewmat);
	const mt::mat4 proj((const float *)winmat);
	for (Object *ob : drawn) {
		PreviewEmitter &em = g_emitters[ob];
		if (em.buffer) {
			em.buffer->Draw(view, proj, 0);
		}
		if (em.bufferMix) {
			em.bufferMix->Draw(view, proj, 0);
		}
	}
	return (int)drawn.size();
}

void BL_preview_particles_free(void)
{
	g_emitters.clear();
	g_lastTime = 0.0;
}
