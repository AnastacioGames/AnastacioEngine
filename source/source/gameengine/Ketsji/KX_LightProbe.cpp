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

/** \file KX_LightProbe.cpp
 *  \ingroup ketsji
 */

#include "KX_LightProbe.h"

#include "GPU_texture.h"

#include "DNA_texture_types.h"

#include "KX_Camera.h"

#ifdef __EMSCRIPTEN__
#  include "RAS_WebGLCompat.h"
#endif

#include "CM_Message.h"

#include <cmath>
#include <cstdlib>
#include <cstring>

/// KX_TextureRenderer reads its settings from an EnvMap; a probe has none, so fill one here.
static EnvMap *probe_env(float clipEnd, bool realtime)
{
	static EnvMap env;
	memset(&env, 0, sizeof(env));
	env.clipsta = 0.1f;
	env.clipend = clipEnd;
	env.lodfactor = 1.0f;
	env.flag = realtime ? ENVMAP_AUTO_UPDATE : 0;
	return &env;
}

KX_LightProbe::KX_LightProbe(KX_GameObject *viewpoint, float radius, int size, float clipEnd, bool realtime)
	:KX_CubeMap(probe_env(clipEnd, realtime), viewpoint),
	m_cube(nullptr),
	m_size(size),
	m_radius(radius),
	m_maxLod(std::log2((float)size)),
	m_shReader(nullptr),
	m_shValid(false)
{
}

KX_LightProbe::~KX_LightProbe()
{
	if (m_cube) {
		// Detaching clears the face framebuffers, so ~RAS_TextureRenderer has nothing left to detach.
		for (Face& face : m_faces) {
			face.DetachTexture(m_cube);
		}
		GPU_texture_free(m_cube);
	}
	if (m_shReader) {
		GPU_cube_sh9_reader_free(m_shReader);
	}
}

std::string KX_LightProbe::GetName()
{
	return "KX_LightProbe";
}

float KX_LightProbe::GetRadius() const
{
	return m_radius;
}

GPUTexture *KX_LightProbe::GetCubeTexture() const
{
	return m_cube;
}

float KX_LightProbe::GetMaxLod() const
{
	return m_maxLod;
}

const float (*KX_LightProbe::GetSH())[3]
{
	if (m_shReader && GPU_cube_sh9_reader_poll(m_shReader, m_sh)) {
		m_shValid = true;
	}
	return m_shValid ? m_sh : nullptr;
}

bool KX_LightProbe::SetupCamera(KX_Camera *sceneCamera, KX_Camera *camera)
{
	// Created here and not in BeginRender: returning false skips the capture if the texture failed.
	if (!m_cube) {
		char err[256] = "";
#ifdef __EMSCRIPTEN__
		// WebGL2 can't render to half float without EXT_color_buffer_float; RGBA8 clips the bright
		// emitters, so the SH9 comes out dimmer than on desktop.
		m_cube = GPU_texture_create_cube(m_size, RAS_FloatRenderTargetSupported() ? GPU_HDR_HALF_FLOAT : GPU_HDR_NONE, err);
#else
		m_cube = GPU_texture_create_cube(m_size, GPU_HDR_HALF_FLOAT, err);
#endif
		if (!m_cube) {
			CM_Error("light probe: " << err);
			return false;
		}

		for (Face& face : m_faces) {
			face.AttachTexture(m_cube);
		}
	}

	// The World capture has no viewpoint: the background depends only on the face direction.
	if (!GetViewpointObject()) {
		camera->NodeSetWorldPosition(mt::zero3);
		return true;
	}

	return KX_CubeMap::SetupCamera(sceneCamera, camera);
}

void KX_LightProbe::BeginRender(RAS_Rasterizer *)
{
	// The cube map is owned here, not taken from a material texture like RAS_TextureRenderer does.
}

void KX_LightProbe::EndRender(RAS_Rasterizer *)
{
	// Mips blur the reflection by roughness (env_probe_mirror).
	GPU_texture_bind(m_cube, 0);
	GPU_texture_generate_mipmap(m_cube);
	GPU_texture_unbind(m_cube);
	/* Smooth diffuse light from a 16 px readback. A realtime probe keeps the last SH9 while a copy
	 * is pending, so the ambient trails the capture by a few frames. */
	static const bool shOff = getenv("RANGE_PROBE_SH9_OFF") != nullptr;
	if (shOff) {
		return;
	}
	if (!m_shReader) {
		m_shReader = GPU_cube_sh9_reader_create();
	}
	GPU_cube_sh9_reader_request(m_shReader, m_cube);
}
