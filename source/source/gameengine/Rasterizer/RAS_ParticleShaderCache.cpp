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

/** \file RAS_ParticleShaderCache.cpp
 *  \ingroup bgerast
 */

#include "RAS_ParticleShaderCache.h"

#include "CM_Message.h"

#include "GPU_glew.h"

namespace {

const char *updateVertexSource =
	"#version 130\n"
	"in vec3 in_position;\n"
	"in vec3 in_velocity;\n"
	"in float in_age;\n"
	"out vec3 out_position;\n"
	"out vec3 out_velocity;\n"
	"out float out_age;\n"
	"uniform float u_deltaTime;\n"
	"uniform float u_lifetime;\n"
	"uniform float u_emitterRadius;\n"
	"uniform float u_velocityRandomness;\n"
	"uniform float u_time;\n"
	"uniform vec3 u_gravity;\n"
	"uniform vec3 u_emitterPos;\n"
	"uniform vec3 u_velocityBase;\n"
	// Fase G: opt-in directional cone emission. emissionAngle is a half-angle in degrees;
	// >= 180 keeps the original cube-jitter velocity randomization exactly as before.
	"uniform vec3 u_emissionDir;\n"
	"uniform float u_emissionAngle;\n"
	// Fase O: collision. 0 = None, 1 = Ground Plane, 2 = Screen-Space (depth buffer).
	"uniform int u_collisionMode;\n"
	"uniform float u_collisionHeight;\n"
	"uniform float u_collisionBounce;\n"
	"uniform float u_collisionFriction;\n"
	"uniform mat4 u_collisionViewProj;\n"
	"uniform sampler2D u_collisionDepthTex;\n"
	"uniform bool u_collisionDepthTexValid;\n"
	"float hash(float n) {\n"
	"	return fract(sin(n) * 43758.5453123);\n"
	"}\n"
	"void main() {\n"
	"	float age = in_age + u_deltaTime;\n"
	"	vec3 pos = in_position;\n"
	"	vec3 vel = in_velocity;\n"
	"	if (age >= u_lifetime) {\n"
	"		float seed = float(gl_VertexID) + u_time;\n"
	"		vec3 r = vec3(hash(seed), hash(seed + 1.0), hash(seed + 2.0)) * 2.0 - 1.0;\n"
	"		vec3 rv = vec3(hash(seed + 3.0), hash(seed + 4.0), hash(seed + 5.0)) * 2.0 - 1.0;\n"
	"		pos = u_emitterPos + r * u_emitterRadius;\n"
	"		if (u_emissionAngle >= 180.0) {\n"
	"			vel = u_velocityBase + rv * u_velocityRandomness;\n"
	"		} else {\n"
	// Uniform sampling within a cone of half-angle u_emissionAngle around u_emissionDir:
	// pick cos(theta) in [cos(maxAngle), 1] and a random azimuth, then rotate into an
	// orthonormal basis built from u_emissionDir.
	"			float a1 = hash(seed + 6.0);\n"
	"			float a2 = hash(seed + 7.0);\n"
	"			float cosMax = cos(radians(u_emissionAngle));\n"
	"			float cosTheta = mix(cosMax, 1.0, a1);\n"
	"			float sinTheta = sqrt(max(0.0, 1.0 - cosTheta * cosTheta));\n"
	"			float phi = 6.2831853 * a2;\n"
	"			vec3 fwd = normalize(u_emissionDir);\n"
	"			vec3 arbitrary = (abs(fwd.z) < 0.999) ? vec3(0.0, 0.0, 1.0) : vec3(1.0, 0.0, 0.0);\n"
	"			vec3 tangent = normalize(cross(arbitrary, fwd));\n"
	"			vec3 bitangent = cross(fwd, tangent);\n"
	"			vec3 coneDir = tangent * (sinTheta * cos(phi)) + bitangent * (sinTheta * sin(phi)) + fwd * cosTheta;\n"
	"			vel = u_velocityBase + coneDir * u_velocityRandomness;\n"
	"		}\n"
	// Propagate the remainder instead of zeroing -- staggered particles cross the lifetime
	// threshold on different frames, so discarding the remainder would drift their phase apart.
	"		age = mod(age, u_lifetime);\n"
	"	} else {\n"
	"		vel += u_gravity * u_deltaTime;\n"
	"		pos += vel * u_deltaTime;\n"
	// Fase O: collision response. Purely kinematic (no Bullet, no particle-particle) --
	// see RAS_ParticleShaderCache.h and the collision plan doc for the accepted limitations.
	"		if (u_collisionMode == 1) {\n"
	"			if (pos.z < u_collisionHeight && vel.z < 0.0) {\n"
	"				pos.z = u_collisionHeight;\n"
	"				vel.xy *= u_collisionFriction;\n"
	"				vel.z = -vel.z * u_collisionBounce;\n"
	"				if (abs(vel.z) < 0.01) {\n"
	"					vel.z = 0.0;\n"
	"				}\n"
	"			}\n"
	"		} else if (u_collisionMode == 2 && u_collisionDepthTexValid) {\n"
	"			vec4 clip = u_collisionViewProj * vec4(pos, 1.0);\n"
	"			if (clip.w > 0.0) {\n"
	"				vec3 ndc = clip.xyz / clip.w;\n"
	"				vec2 uv = ndc.xy * 0.5 + 0.5;\n"
	"				if (uv.x >= 0.0 && uv.x <= 1.0 && uv.y >= 0.0 && uv.y <= 1.0) {\n"
	"					float sceneDepth = texture2D(u_collisionDepthTex, uv).r;\n"
	"					float particleDepth = ndc.z * 0.5 + 0.5;\n"
	// particleDepth >= sceneDepth means the particle's projected position is at or behind
	// (farther than) the nearest visible surface at that screen pixel -- treated as a hit.
	// No real surface normal is available from a single depth sample, so the response
	// approximates it as world-up -- good for dust/sparks over mostly-horizontal ground/floors
	// seen on screen, documented as inaccurate on steep surfaces.
	"					if (particleDepth >= sceneDepth) {\n"
	"						pos -= vel * u_deltaTime;\n"
	"						vel.xy *= u_collisionFriction;\n"
	"						vel.z = abs(vel.z) * u_collisionBounce;\n"
	"						if (abs(vel.z) < 0.01) {\n"
	"							vel.z = 0.0;\n"
	"						}\n"
	"					}\n"
	"				}\n"
	"			}\n"
	"		}\n"
	"	}\n"
	"	out_position = pos;\n"
	"	out_velocity = vel;\n"
	"	out_age = age;\n"
	"}\n";

// Billboard quad corners, offset in view space so the quad always faces the camera without
// needing separate camera right/up uniforms (in view space those axes are always X/Y).
const char *drawVertexSource =
	"#version 130\n"
	"in vec2 in_corner;\n"
	"in vec3 in_particlePos;\n"
	"in float in_particleAge;\n"
	"out vec2 v_uv;\n"
	"out float v_alpha;\n"
	"out float v_lifeFrac;\n"
	"uniform mat4 u_view;\n"
	"uniform mat4 u_projection;\n"
	"uniform float u_lifetime;\n"
	"uniform float u_size;\n"
	"uniform float u_endSize;\n"
	"uniform sampler2D u_sizeCurveTex;\n"
	"uniform bool u_useSizeCurve;\n"
	"uniform int u_billboardMode;\n"
	"void main() {\n"
	"	float lifeFrac = clamp(in_particleAge / u_lifetime, 0.0, 1.0);\n"
	"	float size;\n"
	"	if (u_useSizeCurve) {\n"
	"		size = texture2D(u_sizeCurveTex, vec2(lifeFrac, 0.5)).r;\n"
	"	} else {\n"
	"		size = mix(u_size, u_endSize, lifeFrac);\n"
	"	}\n"
	"	if (u_billboardMode == 1) {\n"
	"		vec3 worldRight = vec3(u_view[0][0], u_view[1][0], u_view[2][0]);\n"
	"		vec3 up = vec3(0.0, 0.0, 1.0);\n"
	"		vec3 rightRaw = worldRight - dot(worldRight, up) * up;\n"
	"		vec3 right = (dot(rightRaw, rightRaw) > 0.0001) ? normalize(rightRaw) : vec3(1.0, 0.0, 0.0);\n"
	"		vec3 offset = right * (in_corner.x * size) + up * (in_corner.y * size);\n"
	"		gl_Position = u_projection * u_view * vec4(in_particlePos + offset, 1.0);\n"
	"	} else if (u_billboardMode == 2) {\n"
	"		vec3 offset = vec3(-in_corner.x * size, in_corner.y * size, 0.0);\n"
	"		gl_Position = u_projection * u_view * vec4(in_particlePos + offset, 1.0);\n"
	"	} else {\n"
	"		vec4 viewPos = u_view * vec4(in_particlePos, 1.0);\n"
	"		viewPos.xy += in_corner * size;\n"
	"		gl_Position = u_projection * viewPos;\n"
	"	}\n"
	"	v_uv = in_corner;\n"
	"	v_lifeFrac = lifeFrac;\n"
	// Fade in over the first 10% of life, fade out over the last 30% -- avoids a hard pop
	// on respawn/death.
	"	v_alpha = min(lifeFrac / 0.1, (1.0 - lifeFrac) / 0.3);\n"
	"	v_alpha = clamp(v_alpha, 0.0, 1.0);\n"
	"}\n";

const char *drawFragmentSource =
	"#version 130\n"
	"in vec2 v_uv;\n"
	"in float v_alpha;\n"
	"in float v_lifeFrac;\n"
	"out vec4 fragColor;\n"
	"uniform vec4 u_color;\n"
	"uniform vec4 u_endColor;\n"
	"uniform sampler2D u_texture;\n"
	"uniform bool u_useTexture;\n"
	"uniform sampler2D u_colorCurveTex;\n"
	"uniform bool u_useColorCurve;\n"
	"void main() {\n"
	"	vec4 baseColor;\n"
	"	if (u_useColorCurve) {\n"
	"		baseColor = texture2D(u_colorCurveTex, vec2(v_lifeFrac, 0.5));\n"
	"	} else {\n"
	"		baseColor = mix(u_color, u_endColor, v_lifeFrac);\n"
	"	}\n"
	"	vec3 rgb = baseColor.rgb;\n"
	"	float mask;\n"
	"	if (u_useTexture) {\n"
	// v_uv is in [-0.5, 0.5] (unit quad corners) -- shift to [0, 1] for sampling.
	"		vec4 texColor = texture2D(u_texture, v_uv + 0.5);\n"
	"		rgb *= texColor.rgb;\n"
	"		mask = texColor.a;\n"
	"	} else {\n"
	// Soft round sprite instead of a hard-edged square.
	"		float d = length(v_uv) * 2.0;\n"
	"		mask = smoothstep(1.0, 0.0, d);\n"
	"	}\n"
	"	float alpha = baseColor.a * mask * v_alpha;\n"
	"	if (alpha <= 0.001) {\n"
	"		discard;\n"
	"	}\n"
	"	fragColor = vec4(rgb, alpha);\n"
	"}\n";

unsigned int CompileDrawProgram()
{
	GLuint vert = glCreateShader(GL_VERTEX_SHADER);
	glShaderSource(vert, 1, &drawVertexSource, nullptr);
	glCompileShader(vert);

	GLuint frag = glCreateShader(GL_FRAGMENT_SHADER);
	glShaderSource(frag, 1, &drawFragmentSource, nullptr);
	glCompileShader(frag);

	GLint status;
	GLchar log[2048];
	GLsizei length = 0;

	glGetShaderiv(vert, GL_COMPILE_STATUS, &status);
	if (!status) {
		glGetShaderInfoLog(vert, sizeof(log), &length, log);
		CM_Error("particle draw vertex shader compile failed:\n" << log);
		glDeleteShader(vert);
		glDeleteShader(frag);
		return 0;
	}
	glGetShaderiv(frag, GL_COMPILE_STATUS, &status);
	if (!status) {
		glGetShaderInfoLog(frag, sizeof(log), &length, log);
		CM_Error("particle draw fragment shader compile failed:\n" << log);
		glDeleteShader(vert);
		glDeleteShader(frag);
		return 0;
	}

	GLuint program = glCreateProgram();
	glAttachShader(program, vert);
	glAttachShader(program, frag);
	// Locations must match the draw VAOs built in RAS_ParticleBuffer::Create: 0 = per-vertex
	// quad corner (divisor 0), 1/2 = per-instance particle position/age (divisor 1).
	glBindAttribLocation(program, 0, "in_corner");
	glBindAttribLocation(program, 1, "in_particlePos");
	glBindAttribLocation(program, 2, "in_particleAge");
	glLinkProgram(program);

	glGetProgramiv(program, GL_LINK_STATUS, &status);
	glDeleteShader(vert);
	glDeleteShader(frag);
	if (!status) {
		glGetProgramInfoLog(program, sizeof(log), &length, log);
		CM_Error("particle draw program link failed:\n" << log);
		glDeleteProgram(program);
		return 0;
	}

	return program;
}

std::weak_ptr<RAS_ParticleShaderCache> g_particleShaderCache;

} // namespace

RAS_ParticleShaderCache::RAS_ParticleShaderCache()
	:m_drawProgram(0),
	m_drawViewLoc(-1),
	m_drawProjLoc(-1),
	m_drawLifetimeLoc(-1),
	m_drawSizeLoc(-1),
	m_drawColorLoc(-1),
	m_drawTextureLoc(-1),
	m_drawUseTextureLoc(-1),
	m_drawEndColorLoc(-1),
	m_drawEndSizeLoc(-1),
	m_drawUseSizeCurveLoc(-1),
	m_drawSizeCurveTexLoc(-1),
	m_drawUseColorCurveLoc(-1),
	m_drawColorCurveTexLoc(-1),
	m_deltaTimeLoc(-1),
	m_lifetimeLoc(-1),
	m_emitterRadiusLoc(-1),
	m_velocityRandomnessLoc(-1),
	m_timeLoc(-1),
	m_gravityLoc(-1),
	m_emitterPosLoc(-1),
	m_velocityBaseLoc(-1),
	m_emissionDirLoc(-1),
	m_emissionAngleLoc(-1),
	m_collisionModeLoc(-1),
	m_collisionHeightLoc(-1),
	m_collisionBounceLoc(-1),
	m_collisionFrictionLoc(-1),
	m_collisionViewProjLoc(-1),
	m_collisionDepthTexLoc(-1),
	m_collisionDepthTexValidLoc(-1),
	m_valid(false)
{
	m_updateShader.reset(new RAS_TransformFeedbackShader());
	const std::vector<std::pair<int, std::string>> attribLocations = {
		{0, "in_position"}, {1, "in_velocity"}, {2, "in_age"}
	};
	if (!m_updateShader->Create(updateVertexSource, {"out_position", "out_velocity", "out_age"}, attribLocations)) {
		return;
	}

	m_drawProgram = CompileDrawProgram();
	if (!m_drawProgram) {
		return;
	}

	m_drawViewLoc = glGetUniformLocation(m_drawProgram, "u_view");
	m_drawProjLoc = glGetUniformLocation(m_drawProgram, "u_projection");
	m_drawLifetimeLoc = glGetUniformLocation(m_drawProgram, "u_lifetime");
	m_drawSizeLoc = glGetUniformLocation(m_drawProgram, "u_size");
	m_drawColorLoc = glGetUniformLocation(m_drawProgram, "u_color");
	m_drawTextureLoc = glGetUniformLocation(m_drawProgram, "u_texture");
	m_drawUseTextureLoc = glGetUniformLocation(m_drawProgram, "u_useTexture");
	m_drawBillboardModeLoc = glGetUniformLocation(m_drawProgram, "u_billboardMode");
	m_drawEndColorLoc = glGetUniformLocation(m_drawProgram, "u_endColor");
	m_drawEndSizeLoc = glGetUniformLocation(m_drawProgram, "u_endSize");
	m_drawUseSizeCurveLoc = glGetUniformLocation(m_drawProgram, "u_useSizeCurve");
	m_drawSizeCurveTexLoc = glGetUniformLocation(m_drawProgram, "u_sizeCurveTex");
	m_drawUseColorCurveLoc = glGetUniformLocation(m_drawProgram, "u_useColorCurve");
	m_drawColorCurveTexLoc = glGetUniformLocation(m_drawProgram, "u_colorCurveTex");

	const GLuint updateProgram = m_updateShader->GetProgram();
	m_deltaTimeLoc = glGetUniformLocation(updateProgram, "u_deltaTime");
	m_lifetimeLoc = glGetUniformLocation(updateProgram, "u_lifetime");
	m_emitterRadiusLoc = glGetUniformLocation(updateProgram, "u_emitterRadius");
	m_velocityRandomnessLoc = glGetUniformLocation(updateProgram, "u_velocityRandomness");
	m_timeLoc = glGetUniformLocation(updateProgram, "u_time");
	m_gravityLoc = glGetUniformLocation(updateProgram, "u_gravity");
	m_emitterPosLoc = glGetUniformLocation(updateProgram, "u_emitterPos");
	m_velocityBaseLoc = glGetUniformLocation(updateProgram, "u_velocityBase");
	m_emissionDirLoc = glGetUniformLocation(updateProgram, "u_emissionDir");
	m_emissionAngleLoc = glGetUniformLocation(updateProgram, "u_emissionAngle");

	m_collisionModeLoc = glGetUniformLocation(updateProgram, "u_collisionMode");
	m_collisionHeightLoc = glGetUniformLocation(updateProgram, "u_collisionHeight");
	m_collisionBounceLoc = glGetUniformLocation(updateProgram, "u_collisionBounce");
	m_collisionFrictionLoc = glGetUniformLocation(updateProgram, "u_collisionFriction");
	m_collisionViewProjLoc = glGetUniformLocation(updateProgram, "u_collisionViewProj");
	m_collisionDepthTexLoc = glGetUniformLocation(updateProgram, "u_collisionDepthTex");
	m_collisionDepthTexValidLoc = glGetUniformLocation(updateProgram, "u_collisionDepthTexValid");

	m_valid = true;
}

RAS_ParticleShaderCache::~RAS_ParticleShaderCache()
{
	if (m_drawProgram) {
		glDeleteProgram(m_drawProgram);
	}
}

std::shared_ptr<RAS_ParticleShaderCache> RAS_ParticleShaderCache::Get()
{
	std::shared_ptr<RAS_ParticleShaderCache> existing = g_particleShaderCache.lock();
	if (existing) {
		return existing;
	}

	std::shared_ptr<RAS_ParticleShaderCache> created(new RAS_ParticleShaderCache());
	if (!created->Ok()) {
		return nullptr;
	}

	g_particleShaderCache = created;
	return created;
}
