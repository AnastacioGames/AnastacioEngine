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

/** \file KX_PlanarReflector.cpp
 *  \ingroup ketsji
 */

#include "KX_PlanarReflector.h"

#include "GPU_texture.h"

#include "DNA_texture_types.h"

#include "KX_Camera.h"

#include "CM_Message.h"

#include <cstring>

/// KX_TextureRenderer reads its settings from an EnvMap; the node has none, so fill one here
/// (same trick as KX_LightProbe::probe_env for the cube map probe).
static EnvMap *planar_env(float clipEnd)
{
	static EnvMap env;
	memset(&env, 0, sizeof(env));
	env.clipsta = 0.1f;
	env.clipend = clipEnd;
	env.lodfactor = 1.0f;
	env.flag = ENVMAP_AUTO_UPDATE;
	return &env;
}

KX_PlanarReflector::KX_PlanarReflector(KX_GameObject *viewpoint, int size, float clipEnd)
	:KX_PlanarMap(planar_env(clipEnd), viewpoint),
	m_tex(nullptr),
	m_size(size),
	m_viewProjection(mt::mat4::Identity())
{
}

KX_PlanarReflector::~KX_PlanarReflector()
{
	if (m_tex) {
		// Detaching clears the face framebuffer, so ~RAS_TextureRenderer has nothing left to detach.
		for (Face& face : m_faces) {
			face.DetachTexture(m_tex);
		}
		GPU_texture_free(m_tex);
	}
}

std::string KX_PlanarReflector::GetName()
{
	return "KX_PlanarReflector";
}

GPUTexture *KX_PlanarReflector::GetTexture() const
{
	return m_tex;
}

const mt::mat4& KX_PlanarReflector::GetViewProjection() const
{
	return m_viewProjection;
}

bool KX_PlanarReflector::SetupCamera(KX_Camera *sceneCamera, KX_Camera *camera)
{
	// Created here and not in BeginRender: returning false skips the capture if the texture failed.
	if (!m_tex) {
		char err[256] = "";
#ifdef __EMSCRIPTEN__
		// WebGL2 can't render to half float without EXT_color_buffer_float.
		m_tex = GPU_texture_create_2D(m_size, m_size, nullptr, GPU_HDR_NONE, err);
#else
		m_tex = GPU_texture_create_2D(m_size, m_size, nullptr, GPU_HDR_HALF_FLOAT, err);
#endif
		if (!m_tex) {
			CM_Error("planar reflector: " << err);
			return false;
		}

		for (Face& face : m_faces) {
			face.AttachTexture(m_tex);
		}
	}

	return KX_PlanarMap::SetupCamera(sceneCamera, camera);
}

void KX_PlanarReflector::BeginRender(RAS_Rasterizer *)
{
	// The texture is owned here, not taken from a material texture user like KX_PlanarMap does.
}

void KX_PlanarReflector::EndRender(RAS_Rasterizer *)
{
	// No mip chain: the node samples a single screen-space UV, no roughness-based LOD like probes.
}

void KX_PlanarReflector::SetFrameViewProjection(const mt::mat4& view, const mt::mat4& projection)
{
	m_viewProjection = projection * view;
}
