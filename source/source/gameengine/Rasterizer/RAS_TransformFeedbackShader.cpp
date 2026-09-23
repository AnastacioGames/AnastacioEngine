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

/** \file RAS_TransformFeedbackShader.cpp
 *  \ingroup bgerast
 */

#include "RAS_TransformFeedbackShader.h"

#include "CM_Message.h"

#include "GPU_glew.h"

#ifdef __EMSCRIPTEN__
#include <emscripten.h>
/* Best-effort bridge to Module.onDiagnostic (version 1); never alters normal error handling. */
EM_JS(void, tf_shader_web_diagnostic,
      (const char *operation, const char *stage, const char *origin, const char *log),
      {
        if (typeof Module === 'undefined' || typeof Module.onDiagnostic !== 'function') return;
        try {
          Module.onDiagnostic({version: 1, category: 'shader', severity: 'error',
                               operation: UTF8ToString(operation), stage: UTF8ToString(stage),
                               origin: UTF8ToString(origin), log: UTF8ToString(log)});
        } catch (e) {}
      });
#endif

RAS_TransformFeedbackShader::RAS_TransformFeedbackShader()
	:m_program(0),
	m_valid(false)
{
}

RAS_TransformFeedbackShader::~RAS_TransformFeedbackShader()
{
	if (m_program) {
		glDeleteProgram(m_program);
	}
}

bool RAS_TransformFeedbackShader::Create(const char *vertexSource, const std::vector<std::string> &varyings,
                                          const std::vector<std::pair<int, std::string>> &attribLocations)
{
	GLuint vertexShader = glCreateShader(GL_VERTEX_SHADER);
	glShaderSource(vertexShader, 1, &vertexSource, nullptr);
	glCompileShader(vertexShader);

	GLint status;
	GLchar log[2048];
	GLsizei length = 0;

	glGetShaderiv(vertexShader, GL_COMPILE_STATUS, &status);
	if (!status) {
		glGetShaderInfoLog(vertexShader, sizeof(log), &length, log);
#ifdef __EMSCRIPTEN__
		tf_shader_web_diagnostic("compile", "vertex", "particle-transform-feedback", log);
#endif
		CM_Error("particle transform feedback shader compile failed:\n" << log);
		glDeleteShader(vertexShader);
		return false;
	}

	m_program = glCreateProgram();
	glAttachShader(m_program, vertexShader);

	// Must happen before glLinkProgram, same as glTransformFeedbackVaryings below -- keeps
	// attribute locations stable across separately-linked programs sharing one VAO.
	for (const std::pair<int, std::string> &binding : attribLocations) {
		glBindAttribLocation(m_program, binding.first, binding.second.c_str());
	}

	std::vector<const char *> varyingNames;
	varyingNames.reserve(varyings.size());
	for (const std::string &name : varyings) {
		varyingNames.push_back(name.c_str());
	}
	// Must happen before glLinkProgram -- this is exactly the step GPU_shader_create is missing.
	glTransformFeedbackVaryings(m_program, (GLsizei)varyingNames.size(), varyingNames.data(), GL_INTERLEAVED_ATTRIBS);

	glLinkProgram(m_program);
	glGetProgramiv(m_program, GL_LINK_STATUS, &status);

	// The shader object is refcounted by the program once attached; safe to delete now regardless of link result.
	glDeleteShader(vertexShader);

	if (!status) {
		glGetProgramInfoLog(m_program, sizeof(log), &length, log);
#ifdef __EMSCRIPTEN__
		tf_shader_web_diagnostic("link", "", "particle-transform-feedback", log);
#endif
		CM_Error("particle transform feedback program link failed:\n" << log);
		glDeleteProgram(m_program);
		m_program = 0;
		return false;
	}

	m_valid = true;
	return true;
}

int RAS_TransformFeedbackShader::GetAttribLocation(const std::string &name) const
{
	return glGetAttribLocation(m_program, name.c_str());
}
