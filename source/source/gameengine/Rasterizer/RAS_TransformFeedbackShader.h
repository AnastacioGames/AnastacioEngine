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

/** \file RAS_TransformFeedbackShader.h
 *  \ingroup bgerast
 */

#ifndef __RAS_TRANSFORMFEEDBACKSHADER_H__
#define __RAS_TRANSFORMFEEDBACKSHADER_H__

#include <string>
#include <utility>
#include <vector>

/** Minimal vertex-shader-only program compiler for GPU particle simulation via
 * transform feedback. GPU_shader_create (source/blender/gpu) links its program without
 * ever calling glTransformFeedbackVaryings() beforehand, so it cannot produce a program
 * usable as a transform feedback target -- this class exists to fill that gap without
 * touching gpu_shader.c, which is shared with the Blender editor.
 */
class RAS_TransformFeedbackShader
{
private:
	unsigned int m_program;
	bool m_valid;

public:
	RAS_TransformFeedbackShader();
	~RAS_TransformFeedbackShader();

	/** Compile the vertex shader, register the transform feedback varyings and link.
	 * \param vertexSource GLSL source of the vertex shader (the only stage; rasterization
	 * is discarded during the update dispatch, see RAS_ParticleBuffer::Update).
	 * \param varyings Names of the vertex shader's \c out variables to capture, in the
	 * exact order they should be interleaved in the destination buffer.
	 * \param attribLocations Optional (location, attribute name) pairs bound via
	 * glBindAttribLocation before linking, so callers can rely on a stable location
	 * across separately-linked programs (e.g. this update program and a draw program
	 * sharing the same VAO) without needing GLSL layout qualifiers -- those require
	 * GL_ARB_explicit_attrib_location under the #version 130 shaders this class targets.
	 */
	bool Create(const char *vertexSource, const std::vector<std::string> &varyings,
	            const std::vector<std::pair<int, std::string>> &attribLocations = {});

	unsigned int GetProgram() const
	{
		return m_program;
	}
	bool Ok() const
	{
		return m_valid;
	}

	int GetAttribLocation(const std::string &name) const;
};

#endif // __RAS_TRANSFORMFEEDBACKSHADER_H__
