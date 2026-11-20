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

/** \file view3d_particles.cpp
 *  \ingroup spview3d
 *
 * Game Preview > Particles: the GPU particle emitters of the scene (Object > Particles, plus the Mix
 * emitter) in the 3D View. It runs the game's own RAS_ParticleBuffer, configured by the same
 * RAS_ParticleBuffer::Configure the game uses, so the simulation and the look are the game's; only the
 * clock (real time between redraws) and the owner's transform (obmat) come from the editor.
 */

#include <algorithm>
#include <cmath>
#include <cstring>
#include <memory>
#include <vector>

#include "DNA_object_types.h"
#include "DNA_scene_types.h"
#include "DNA_view3d_types.h"
#include "DNA_gpu_types.h"
#include "DNA_mesh_types.h"

#include "PIL_time.h"
#include "DNA_property_types.h"
extern "C" {
#include "BKE_property.h"
}

#include "GPU_glew.h"

#ifdef WITH_GAMEENGINE

#include "RAS_ParticleBuffer.h"

namespace {

struct Emitter {
	const Object *ob;
	const RegionView3D *rv3d;
	bool mix;
	RangeGPUParticleSettings settings; /* as the buffer was built */
	std::unique_ptr<RAS_ParticleBuffer> buffer;
	double last_time;
	bool seen;
};

std::vector<Emitter> g_emitters;

/* Snapshot of the scene depth under the particles (soft particles): copied from the bound framebuffer
 * right before drawing, as the game's depth blit does. */
GLuint g_depth_tex = 0;
int g_depth_w = 0, g_depth_h = 0;

bool depth_snapshot(const GLint vp[4])
{
	if (vp[2] <= 0 || vp[3] <= 0) {
		return false;
	}
	while (glGetError() != GL_NO_ERROR) {}
	if (!g_depth_tex) {
		glGenTextures(1, &g_depth_tex);
		g_depth_w = g_depth_h = 0;
	}
	GLint prev_tex = 0;
	glGetIntegerv(GL_TEXTURE_BINDING_2D, &prev_tex);
	glBindTexture(GL_TEXTURE_2D, g_depth_tex);
	if (g_depth_w != vp[2] || g_depth_h != vp[3]) {
		glTexImage2D(GL_TEXTURE_2D, 0, GL_DEPTH_COMPONENT24, vp[2], vp[3], 0, GL_DEPTH_COMPONENT, GL_FLOAT, nullptr);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_COMPARE_MODE, GL_NONE);
		g_depth_w = vp[2];
		g_depth_h = vp[3];
	}
	glCopyTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, vp[0], vp[1], vp[2], vp[3]);
	glBindTexture(GL_TEXTURE_2D, prev_tex);
	return glGetError() == GL_NO_ERROR; /* e.g. a multisampled source fails: no soft fade, still drawn */
}

bool emitter_wanted(const Object *ob, bool mix)
{
	return (ob->gameflag2 & (mix ? OB_GPU_PARTICLES_MIX : OB_GPU_PARTICLES)) != 0;
}

/* Rotation of the object without its scale, as the game's NodeGetWorldOrientation. */
mt::mat3 object_rotation(const Object *ob)
{
	float m[9];
	for (int c = 0; c < 3; c++) {
		const float *col = ob->obmat[c];
		const float len = sqrtf(col[0] * col[0] + col[1] * col[1] + col[2] * col[2]);
		const float inv = len > 1e-8f ? 1.0f / len : 0.0f;
		m[c * 3 + 0] = col[0] * inv;
		m[c * 3 + 1] = col[1] * inv;
		m[c * 3 + 2] = col[2] * inv;
	}
	return mt::mat3(m);
}

Emitter *emitter_find(const Object *ob, const RegionView3D *rv3d, bool mix)
{
	for (Emitter &e : g_emitters) {
		if (e.ob == ob && e.rv3d == rv3d && e.mix == mix) {
			return &e;
		}
	}
	return nullptr;
}

void emitter_build(Emitter &e, const Object *ob, const RangeGPUParticleSettings &settings)
{
	e.settings = settings;
	e.buffer.reset(new RAS_ParticleBuffer(settings.particle_count > 0 ? settings.particle_count : 1));
	if (!e.buffer->Create()) {
		e.buffer.reset();
		return;
	}
	const Mesh *me = (ob->type == OB_MESH) ? (const Mesh *)ob->data : nullptr;
	e.buffer->Configure(settings, me, &ob->obmat[0][0]);
	e.last_time = PIL_check_seconds_timer();
}

} // namespace

extern "C" {

bool view3d_gpu_particles_active(const Scene *scene, const View3D *v3d)
{
	if (!(v3d->fx_settings.fx_flag2 & GPU_FX2_PARTICLES)) {
		return false;
	}
	for (const Base *base = (const Base *)scene->base.first; base; base = base->next) {
		const Object *ob = base->object;
		if ((base->lay & v3d->lay) &&
		    (emitter_wanted(ob, false) || emitter_wanted(ob, true) ||
		     (ob->type == OB_LAMP && BKE_bproperty_object_get((Object *)ob, "light_flicker"))))
		{
			return true;
		}
	}
	return false;
}

void view3d_gpu_particles_free(void)
{
	g_emitters.clear();
	if (g_depth_tex) {
		glDeleteTextures(1, &g_depth_tex);
		g_depth_tex = 0;
	}
}

void view3d_draw_gpu_particles(Scene *scene, View3D *v3d, RegionView3D *rv3d)
{
	if (!(v3d->fx_settings.fx_flag2 & GPU_FX2_PARTICLES)) {
		for (size_t i = g_emitters.size(); i-- > 0;) {
			if (g_emitters[i].rv3d == rv3d) {
				g_emitters.erase(g_emitters.begin() + i);
			}
		}
		return;
	}

	for (Emitter &e : g_emitters) {
		if (e.rv3d == rv3d) {
			e.seen = false;
		}
	}

	const mt::mat4 view(&rv3d->viewmat[0][0]);
	const mt::mat4 proj(&rv3d->winmat[0][0]);
	const double now = PIL_check_seconds_timer();
	bool any = false;

	GLint vp[4] = {0, 0, 0, 0};
	glGetIntegerv(GL_VIEWPORT, vp);
	GLint prev_prog = 0, prev_vao = 0, prev_vbo = 0;
	glGetIntegerv(GL_CURRENT_PROGRAM, &prev_prog);
	glGetIntegerv(GL_VERTEX_ARRAY_BINDING, &prev_vao);
	glGetIntegerv(GL_ARRAY_BUFFER_BINDING, &prev_vbo);
	unsigned int soft_tex = 0;
	{
		bool wanted = false;
		for (const Emitter &e : g_emitters) {
			wanted = wanted || (e.rv3d == rv3d);
		}
		/* Emitters created in this very pass are not in the list yet: any wanted emitter qualifies. */
		for (const Base *base = (const Base *)scene->base.first; base && !wanted; base = base->next) {
			wanted = (base->lay & v3d->lay) && (emitter_wanted(base->object, false) || emitter_wanted(base->object, true));
		}
		if (wanted && depth_snapshot(vp)) {
			soft_tex = g_depth_tex;
		}
	}
	glPushAttrib(GL_ENABLE_BIT | GL_DEPTH_BUFFER_BIT | GL_COLOR_BUFFER_BIT | GL_CURRENT_BIT);
	for (const Base *base = (const Base *)scene->base.first; base; base = base->next) {
		const Object *ob = base->object;
		if (!(base->lay & v3d->lay) || (ob->restrictflag & OB_RESTRICT_VIEW)) {
			continue;
		}
		for (int m = 0; m < 2; m++) {
			const bool mix = (m == 1);
			if (!emitter_wanted(ob, mix)) {
				continue;
			}
			const RangeGPUParticleSettings &settings = mix ? ob->gpu_particles_mix : ob->gpu_particles;
			Emitter *e = emitter_find(ob, rv3d, mix);
			if (!e) {
				g_emitters.emplace_back();
				e = &g_emitters.back();
				e->ob = ob;
				e->rv3d = rv3d;
				e->mix = mix;
				memset(&e->settings, 0, sizeof(e->settings));
				e->last_time = now;
				emitter_build(*e, ob, settings);
			}
			else if (memcmp(&e->settings, &settings, sizeof(settings)) != 0) {
				emitter_build(*e, ob, settings);
			}
			e->seen = true;
			if (!e->buffer) {
				continue;
			}
			/* The real clock between redraws, capped so a long pause does not jump the simulation. */
			const float dt = (float)std::min(0.1, std::max(0.0, now - e->last_time));
			e->last_time = now;

			if (e->buffer->IsStatic()) {
				e->buffer->SetModelMatrix(&ob->obmat[0][0]);
			}
			const mt::vec3 pos(ob->obmat[3][0], ob->obmat[3][1], ob->obmat[3][2]);
			e->buffer->Update(dt, pos, object_rotation(ob));
			e->buffer->SetSoftDepthOrigin((float)vp[0], (float)vp[1]);
			e->buffer->Draw(view, proj, soft_tex);
			any = true;
		}
	}
	glPopAttrib();
	glUseProgram(prev_prog);
	glBindVertexArray(prev_vao);
	glBindBuffer(GL_ARRAY_BUFFER, prev_vbo);
	(void)any;

	/* Emitters that left the view, the scene or the layers free their buffers. */
	for (size_t i = g_emitters.size(); i-- > 0;) {
		if (g_emitters[i].rv3d == rv3d && !g_emitters[i].seen) {
			g_emitters.erase(g_emitters.begin() + i);
		}
	}
}

} /* extern "C" */

#else /* WITH_GAMEENGINE */

extern "C" {
bool view3d_gpu_particles_active(const Scene *, const View3D *) { return false; }
void view3d_gpu_particles_free(void) {}
void view3d_draw_gpu_particles(Scene *, View3D *, RegionView3D *) {}
}

#endif
