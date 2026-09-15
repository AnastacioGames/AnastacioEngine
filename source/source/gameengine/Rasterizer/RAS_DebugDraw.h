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
 * Contributor(s): Tristan Porteries.
 *
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file RAS_DebugDraw.h
 *  \ingroup bgerast
 */

#ifndef __RAS_DEBUG_DRAW_H__
#define __RAS_DEBUG_DRAW_H__

#include "mathfu.h"

#include <string>
#include <vector>
#include <array>
#include <memory>

class RAS_Rasterizer;
class RAS_ICanvas;

class RAS_DebugDraw
{
	friend class RAS_OpenGLDebugDraw;

private:
	struct Shape
	{
		Shape(const mt::vec4& color);
		float m_color[4];
	};

	struct Line
	{
		Line(const mt::vec3& from, const mt::vec3& to, const mt::vec4& color);
		float m_color[4];
		float m_from[3];
		float m_color2[4];
		float m_to[3];
	};

	struct Aabb : Shape
	{
		Aabb(const mt::vec3& pos, const mt::mat3& rot, const mt::vec3& min, const mt::vec3& max, const mt::vec4& color);
		float m_mat[16];
	};

	struct Frustum
	{
		Frustum(const mt::mat4& persmat, const mt::vec4& insideColor, const mt::vec4& outsideColor, const mt::vec4& wireColor);
		float m_persMat[16];
		float m_wireColor[4];
		float m_insideColor[4];
		float m_outsideColor[4];
	};

	struct Text2d : Shape
	{
		Text2d(const std::string& text, const mt::vec2& pos, const mt::vec4& color);
		std::string m_text;
		float m_pos[2];
	};

	struct Box2d : Shape
	{
		Box2d(const mt::vec2& pos, const mt::vec2& size, const mt::vec4& color);
		union {
			struct {
				float m_pos[2];
				float m_size[2];
			};
			float m_trans[4];
		};
	};

	/* Camera-facing radial glow billboard, used as a distant-light impostor when a lamp gets
	 * culled out by distance (see KX_LightObject::UpdateDistanceCulling / GetCullFadeAlpha).
	 * Orientation (always facing the camera) is computed at draw time from the camera's
	 * right/up vectors (RAS_OpenGLDebugDraw::Flush), not stored here. */
	struct LightGlow : Shape
	{
		LightGlow(const mt::vec3& pos, float size, const mt::vec4& color);
		float m_pos[3];
		float m_size;
	};

	std::vector<Line> m_lines;
	std::vector<Aabb> m_aabbs;
	std::vector<Frustum> m_frustums;
	std::vector<Text2d> m_texts2d;
	std::vector<Box2d> m_boxes2d;
	std::vector<LightGlow> m_lightGlows;

public:
	RAS_DebugDraw();
	~RAS_DebugDraw();

	void DrawLine(const mt::vec3 &from, const mt::vec3 &to, const mt::vec4& color);
	/** Draw a box depends on minimal and maximal corner.
	 * \param pos The box's position.
	 * \param rot The box's orientation.
	 * \param min The box's minimal corner.
	 * \param max The box's maximal corner.
	 * \param color The box's color.
	 */
	void DrawAabb(const mt::vec3& pos, const mt::mat3& rot,
				  const mt::vec3& min, const mt::vec3& max, const mt::vec4& color);
	/** Draw a box representing a camera frustum volume.
	 * \param projmat The camera perspective matrix.
	 */
	void DrawCameraFrustum(const mt::mat4& persmat);

	void RenderBox2d(const mt::vec2& pos, const mt::vec2& size, const mt::vec4& color);

	void RenderText2d(const std::string& text, const mt::vec2& pos, const mt::vec4& color);

	/** Queue a camera-facing glow billboard (distant-light impostor).
	 * \param pos World-space position (the light's position).
	 * \param size Billboard half-size in world units.
	 * \param color RGBA tint; alpha should already carry the desired fade (0 = invisible).
	 */
	void DrawLightGlow(const mt::vec3& pos, float size, const mt::vec4& color);

	void Flush(RAS_Rasterizer *rasty, RAS_ICanvas *canvas);
};

#endif  // __RAS_DEBUG_DRAW_H__
