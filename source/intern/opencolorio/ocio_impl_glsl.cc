/*
 * Adapted from OpenColorIO with this license:
 *
 * Copyright (c) 2003-2010 Sony Pictures Imageworks Inc., et al.
 * All Rights Reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are
 * met:
 * * Redistributions of source code must retain the above copyright
 *   notice, this list of conditions and the following disclaimer.
 * * Redistributions in binary form must reproduce the above copyright
 *   notice, this list of conditions and the following disclaimer in the
 *   documentation and/or other materials provided with the distribution.
 * * Neither the name of Sony Pictures Imageworks nor the names of its
 *   contributors may be used to endorse or promote products derived from
 *   this software without specific prior written permission.
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 * "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 * LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
 * A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
 * OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
 * SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
 * LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
 * DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
 * THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 * (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 *
 * Modifications Copyright 2013, Blender Foundation.
 */

#include <limits>
#include <sstream>
#include <string.h>

#include "glew-mx.h"

#ifdef _MSC_VER
#  pragma warning(push)
#  pragma warning(disable : 4251 4275)
#endif
#include <OpenColorIO/OpenColorIO.h>
#ifdef _MSC_VER
#  pragma warning(pop)
#endif


using namespace OCIO_NAMESPACE;

#include "MEM_guardedalloc.h"

#include "ocio_impl.h"

#if OCIO_VERSION_HEX >= 0x02000000
#  include <vector>
#  include "ocio_impl_v2.h"
#endif

static const int LUT3D_EDGE_SIZE = 64;

extern "C" char datatoc_gpu_shader_display_transform_glsl[];

/* **** OpenGL drawing routines using GLSL for color space transform ***** */

#ifdef OCIO_V2
/* 2.x hands out its LUTs (any number of 1D/2D/3D textures) and uniforms through
 * the shader description instead of one baked 3D LUT. */
static const int OCIO_V2_FIRST_TEXTURE_UNIT = 3;  /* 0 image, 1 unused, 2 curve mapping */

struct OCIO_GLSLTexture {
	GLuint texture;
	GLenum target;
	std::string sampler;
};

struct OCIO_GLSLStateV2 {
	GpuShaderDescRcPtr desc;  /* keeps the uniform getters alive */
	std::vector<OCIO_GLSLTexture> textures;
};
#endif

typedef struct OCIO_GLSLDrawState {
	bool lut3d_texture_allocated;  /* boolean flag indicating whether
	                                * lut texture is allocated
	                                */
	bool lut3d_texture_valid;

	GLuint lut3d_texture;  /* OGL texture ID for 3D LUT */

	float *lut3d;  /* 3D LUT table */

	bool dither_used;

	bool curve_mapping_used;
	bool curve_mapping_texture_allocated;
	bool curve_mapping_texture_valid;
	GLuint curve_mapping_texture;
	size_t curve_mapping_cache_id;

	bool predivide_used;

	bool texture_size_used;

	/* Cache */
	std::string lut3dcacheid;
	std::string shadercacheid;

	/* GLSL stuff */
	GLuint ocio_shader;
	GLuint program;

	/* Previous OpenGL state. */
	GLint last_texture, last_texture_unit;

#ifdef OCIO_V2
	OCIO_GLSLStateV2 *v2;
#endif
} OCIO_GLSLDrawState;

static GLuint compileShaderText(GLenum shaderType, const char *text)
{
	GLuint shader;
	GLint stat;

	shader = glCreateShader(shaderType);
	glShaderSource(shader, 1, (const GLchar **) &text, NULL);
	glCompileShader(shader);
	glGetShaderiv(shader, GL_COMPILE_STATUS, &stat);

	if (!stat) {
		GLchar log[1000];
		GLsizei len;
		glGetShaderInfoLog(shader, 1000, &len, log);
		fprintf(stderr, "Shader compile error:\n%s\n", log);
		return 0;
	}

	return shader;
}

static GLuint linkShaders(GLuint ocio_shader)
{
	if (!ocio_shader)
		return 0;

	GLuint program = glCreateProgram();

	glAttachShader(program, ocio_shader);

	glLinkProgram(program);

	/* check link */
	{
		GLint stat;
		glGetProgramiv(program, GL_LINK_STATUS, &stat);
		if (!stat) {
			GLchar log[1000];
			GLsizei len;
			glGetProgramInfoLog(program, 1000, &len, log);
			fprintf(stderr, "Shader link error:\n%s\n", log);
			return 0;
		}
	}

	return program;
}

static OCIO_GLSLDrawState *allocateOpenGLState(void)
{
	OCIO_GLSLDrawState *state;

	/* Allocate memory for state. */
	state = (OCIO_GLSLDrawState *) MEM_callocN(sizeof(OCIO_GLSLDrawState),
	                                           "OCIO OpenGL State struct");

	/* Call constructors on new memory. */
	new (&state->lut3dcacheid) std::string("");
	new (&state->shadercacheid) std::string("");
#ifdef OCIO_V2
	state->v2 = new OCIO_GLSLStateV2();
#endif

	return state;
}

#ifndef OCIO_V2
/* Ensure LUT texture and array are allocated */
static bool ensureLUT3DAllocated(OCIO_GLSLDrawState *state)
{
	int num_3d_entries = 3 * LUT3D_EDGE_SIZE * LUT3D_EDGE_SIZE * LUT3D_EDGE_SIZE;

	if (state->lut3d_texture_allocated)
		return state->lut3d_texture_valid;

	glGenTextures(1, &state->lut3d_texture);

	state->lut3d = (float *) MEM_callocN(sizeof(float) * num_3d_entries, "OCIO GPU 3D LUT");

	glActiveTexture(GL_TEXTURE1);
	glBindTexture(GL_TEXTURE_3D, state->lut3d_texture);
	glTexParameteri(GL_TEXTURE_3D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
	glTexParameteri(GL_TEXTURE_3D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
	glTexParameteri(GL_TEXTURE_3D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
	glTexParameteri(GL_TEXTURE_3D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
	glTexParameteri(GL_TEXTURE_3D, GL_TEXTURE_WRAP_R, GL_CLAMP_TO_EDGE);

	/* clean glError buffer */
	while (glGetError() != GL_NO_ERROR) {}

	glTexImage3D(GL_TEXTURE_3D, 0, GL_RGB16F_ARB,
	             LUT3D_EDGE_SIZE, LUT3D_EDGE_SIZE, LUT3D_EDGE_SIZE,
	             0, GL_RGB, GL_FLOAT, state->lut3d);

	state->lut3d_texture_allocated = true;

	/* GL_RGB16F_ARB could be not supported at some drivers
	 * in this case we could not use GLSL display
	 */
	state->lut3d_texture_valid = glGetError() == GL_NO_ERROR;

	return state->lut3d_texture_valid;
}
#endif

static bool ensureCurveMappingAllocated(OCIO_GLSLDrawState *state, OCIO_CurveMappingSettings *curve_mapping_settings)
{
	if (state->curve_mapping_texture_allocated)
		return state->curve_mapping_texture_valid;

	glGenTextures(1, &state->curve_mapping_texture);

	glActiveTexture(GL_TEXTURE2);
	glBindTexture(GL_TEXTURE_1D, state->curve_mapping_texture);
	glTexParameteri(GL_TEXTURE_1D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
	glTexParameteri(GL_TEXTURE_1D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
	glTexParameteri(GL_TEXTURE_1D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
	glTexParameteri(GL_TEXTURE_1D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
	glTexParameteri(GL_TEXTURE_1D, GL_TEXTURE_WRAP_R, GL_CLAMP_TO_EDGE);

	/* clean glError buffer */
	while (glGetError() != GL_NO_ERROR) {}

	glTexImage1D(GL_TEXTURE_1D, 0, GL_RGBA16F_ARB, curve_mapping_settings->lut_size,
	             0, GL_RGBA, GL_FLOAT, curve_mapping_settings->lut);

	state->curve_mapping_texture_allocated = true;

	/* GL_RGB16F_ARB could be not supported at some drivers
	 * in this case we could not use GLSL display
	 */
	state->curve_mapping_texture_valid = glGetError() == GL_NO_ERROR;

	return state->curve_mapping_texture_valid;
}

/* Detect if we can support GLSL drawing */
bool OCIOImpl::supportGLSLDraw()
{
	/* uses GL_RGB16F_ARB */
	return GLEW_VERSION_3_0 || GLEW_ARB_texture_float;
}

static bool supportGLSL13()
{
	const char *version = (const char*)glGetString(GL_SHADING_LANGUAGE_VERSION);
	int major = 1, minor = 0;

	if (version && sscanf(version, "%d.%d", &major, &minor) == 2)
		return (major > 1 || (major == 1 && minor >= 30));

	return false;
}

#ifdef OCIO_V2
static void freeTexturesV2(OCIO_GLSLStateV2 *v2)
{
	for (const OCIO_GLSLTexture &tex : v2->textures)
		glDeleteTextures(1, &tex.texture);
	v2->textures.clear();
}

static GLuint createTextureV2(GLenum target, Interpolation interpolation)
{
	GLuint texture;
	const GLint filter = (interpolation == INTERP_NEAREST) ? GL_NEAREST : GL_LINEAR;

	glGenTextures(1, &texture);
	glBindTexture(target, texture);
	glTexParameteri(target, GL_TEXTURE_MIN_FILTER, filter);
	glTexParameteri(target, GL_TEXTURE_MAG_FILTER, filter);
	glTexParameteri(target, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
	glTexParameteri(target, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
	glTexParameteri(target, GL_TEXTURE_WRAP_R, GL_CLAMP_TO_EDGE);
	return texture;
}

/* Upload every LUT of the shader description. False when the driver refuses a
 * float texture (same fallback as the 1.x path). */
static bool uploadTexturesV2(OCIO_GLSLStateV2 *v2, const char *shader_text)
{
	const GpuShaderDescRcPtr &desc = v2->desc;
	const std::string text = shader_text;

	freeTexturesV2(v2);

	/* clean glError buffer */
	while (glGetError() != GL_NO_ERROR) {}

	for (unsigned i = 0; i < desc->getNum3DTextures(); i++) {
		const char *texture_name, *sampler_name;
		unsigned edgelen;
		Interpolation interpolation;
		const float *values;
		desc->get3DTexture(i, texture_name, sampler_name, edgelen, interpolation);
		desc->get3DTextureValues(i, values);

		glActiveTexture(GL_TEXTURE0 + OCIO_V2_FIRST_TEXTURE_UNIT + (GLenum)v2->textures.size());
		GLuint texture = createTextureV2(GL_TEXTURE_3D, interpolation);
		glTexImage3D(GL_TEXTURE_3D, 0, GL_RGB16F_ARB, edgelen, edgelen, edgelen, 0, GL_RGB, GL_FLOAT, values);
		v2->textures.push_back({texture, GL_TEXTURE_3D, sampler_name});
	}

	for (unsigned i = 0; i < desc->getNumTextures(); i++) {
		const char *texture_name, *sampler_name;
		unsigned width, height;
		GpuShaderDesc::TextureType channel;
		Interpolation interpolation;
		const float *values;
		desc->getTexture(i, texture_name, sampler_name, width, height, channel, interpolation);
		desc->getTextureValues(i, values);

		/* 2.1 declares 1D LUTs as sampler2D; later versions may use sampler1D when height is 1. */
		const bool is_1d = text.find(std::string("sampler1D ") + sampler_name) != std::string::npos;
		const GLenum target = is_1d ? GL_TEXTURE_1D : GL_TEXTURE_2D;
		const bool red = (channel == GpuShaderDesc::TEXTURE_RED_CHANNEL);
		const GLint internal_format = red ? GL_R16F : GL_RGB16F_ARB;
		const GLenum format = red ? GL_RED : GL_RGB;

		glActiveTexture(GL_TEXTURE0 + OCIO_V2_FIRST_TEXTURE_UNIT + (GLenum)v2->textures.size());
		GLuint texture = createTextureV2(target, interpolation);
		if (is_1d)
			glTexImage1D(GL_TEXTURE_1D, 0, internal_format, width, 0, format, GL_FLOAT, values);
		else
			glTexImage2D(GL_TEXTURE_2D, 0, internal_format, width, height, 0, format, GL_FLOAT, values);
		v2->textures.push_back({texture, target, sampler_name});
	}

	return glGetError() == GL_NO_ERROR;
}

static void bindTexturesV2(OCIO_GLSLStateV2 *v2, GLuint program)
{
	for (size_t i = 0; i < v2->textures.size(); i++) {
		const OCIO_GLSLTexture &tex = v2->textures[i];
		const GLint unit = OCIO_V2_FIRST_TEXTURE_UNIT + (GLint)i;
		glActiveTexture(GL_TEXTURE0 + unit);
		glBindTexture(tex.target, tex.texture);
		glUniform1i(glGetUniformLocation(program, tex.sampler.c_str()), unit);
	}
}

/* Dynamic properties are not requested, so configs normally have none; set
 * whatever the description reports anyway. */
static void setUniformsV2(OCIO_GLSLStateV2 *v2, GLuint program)
{
	const GpuShaderDescRcPtr &desc = v2->desc;

	for (unsigned i = 0; i < desc->getNumUniforms(); i++) {
		GpuShaderDesc::UniformData data;
		const char *name = desc->getUniform(i, data);
		const GLint location = glGetUniformLocation(program, name);
		if (location == -1)
			continue;

		switch (data.m_type) {
			case UNIFORM_DOUBLE:
				glUniform1f(location, (float)data.m_getDouble());
				break;
			case UNIFORM_BOOL:
				glUniform1i(location, data.m_getBool() ? 1 : 0);
				break;
			case UNIFORM_FLOAT3:
				glUniform3fv(location, 1, data.m_getFloat3().data());
				break;
			case UNIFORM_VECTOR_FLOAT:
				glUniform1fv(location, (GLsizei)data.m_vectorFloat.m_getSize(), data.m_vectorFloat.m_getVector());
				break;
			case UNIFORM_VECTOR_INT:
				glUniform1iv(location, (GLsizei)data.m_vectorInt.m_getSize(), data.m_vectorInt.m_getVector());
				break;
			default:
				break;
		}
	}
}
#endif

/**
 * Setup OpenGL contexts for a transform defined by processor using GLSL
 * All LUT allocating baking and shader compilation happens here.
 *
 * Once this function is called, callee could start drawing images
 * using regular 2D texture.
 *
 * When all drawing is finished, finishGLSLDraw shall be called to
 * restore OpenGL context to it's pre-GLSL draw state.
 */
bool OCIOImpl::setupGLSLDraw(OCIO_GLSLDrawState **state_r, OCIO_ConstProcessorRcPtr *processor,
                             OCIO_CurveMappingSettings *curve_mapping_settings,
                             float dither, bool use_predivide)
{
#ifdef OCIO_V2
	ConstProcessorRcPtr ocio_processor = ((OCIO_ProcessorV2 *) processor)->processor;
#else
	ConstProcessorRcPtr ocio_processor = *(ConstProcessorRcPtr *) processor;
#endif
	bool use_curve_mapping = curve_mapping_settings != NULL;
	bool use_dither = dither > std::numeric_limits<float>::epsilon();

	/* Create state if needed. */
	OCIO_GLSLDrawState *state;
	if (!*state_r)
		*state_r = allocateOpenGLState();
	state = *state_r;

	glGetIntegerv(GL_TEXTURE_BINDING_2D, &state->last_texture);
	glGetIntegerv(GL_ACTIVE_TEXTURE, &state->last_texture_unit);

#ifndef OCIO_V2
	if (!ensureLUT3DAllocated(state)) {
		glActiveTexture(state->last_texture_unit);
		glBindTexture(GL_TEXTURE_2D, state->last_texture);

		return false;
	}
#endif

	if (use_curve_mapping) {
		if (!ensureCurveMappingAllocated(state, curve_mapping_settings)) {
			glActiveTexture(state->last_texture_unit);
			glBindTexture(GL_TEXTURE_2D, state->last_texture);

			return false;
		}
	}
	else {
		if (state->curve_mapping_texture_allocated) {
			glDeleteTextures(1, &state->curve_mapping_texture);
			state->curve_mapping_texture_allocated = false;
		}
	}

#ifndef OCIO_V2
	/* Step 1: Create a GPU Shader Description */
	GpuShaderDesc shaderDesc;
	shaderDesc.setLanguage(GPU_LANGUAGE_GLSL_1_3);
	shaderDesc.setFunctionName("OCIODisplay");
	shaderDesc.setLut3DEdgeLen(LUT3D_EDGE_SIZE);

#endif

	if (use_curve_mapping) {
		if (state->curve_mapping_cache_id != curve_mapping_settings->cache_id) {
			glActiveTexture(GL_TEXTURE2);
			glBindTexture(GL_TEXTURE_1D, state->curve_mapping_texture);
			glTexSubImage1D(GL_TEXTURE_1D, 0, 0, curve_mapping_settings->lut_size,
			                GL_RGBA, GL_FLOAT, curve_mapping_settings->lut);
		}
	}

#ifdef OCIO_V2
	/* Step 2: The GPU processor gives the shader and its LUTs together */
	ConstGPUProcessorRcPtr gpu_processor = ocio_processor->getDefaultGPUProcessor();
	std::string shaderCacheID = gpu_processor->getCacheID();
#else
	/* Step 2: Compute the 3D LUT */
	std::string lut3dCacheID = ocio_processor->getGpuLut3DCacheID(shaderDesc);
	if (lut3dCacheID != state->lut3dcacheid) {
		state->lut3dcacheid = lut3dCacheID;
		ocio_processor->getGpuLut3D(state->lut3d, shaderDesc);

		glActiveTexture(GL_TEXTURE1);
		glBindTexture(GL_TEXTURE_3D, state->lut3d_texture);
		glTexSubImage3D(GL_TEXTURE_3D, 0, 0, 0, 0,
		                LUT3D_EDGE_SIZE, LUT3D_EDGE_SIZE, LUT3D_EDGE_SIZE,
		                GL_RGB, GL_FLOAT, state->lut3d);
	}

	/* Step 3: Compute the Shader */
	std::string shaderCacheID = ocio_processor->getGpuShaderTextCacheID(shaderDesc);
#endif
	if (state->program == 0 ||
	    shaderCacheID != state->shadercacheid ||
	    use_predivide != state->predivide_used ||
	    use_curve_mapping != state->curve_mapping_used ||
	    use_dither != state->dither_used)
	{
		state->shadercacheid = shaderCacheID;

		if (state->program) {
			glDeleteProgram(state->program);
		}

		if (state->ocio_shader) {
			glDeleteShader(state->ocio_shader);
		}

		std::ostringstream os;

		if (supportGLSL13()) {
			os << "#version 130\n";
		}
		else {
			os << "#define USE_TEXTURE_SIZE\n";
			state->texture_size_used = use_dither;
		}

		if (use_predivide) {
			os << "#define USE_PREDIVIDE\n";
		}

		if (use_dither) {
			os << "#define USE_DITHER\n";
		}

		if (use_curve_mapping) {
			os << "#define USE_CURVE_MAPPING\n";
		}

#ifdef OCIO_V2
		os << "#define OCIO_V2\n";

		state->v2->desc = GpuShaderDesc::CreateShaderDesc();
		state->v2->desc->setLanguage(GPU_LANGUAGE_GLSL_1_3);
		state->v2->desc->setFunctionName("OCIODisplay");
		state->v2->desc->setResourcePrefix("ocio_");
		gpu_processor->extractGpuShaderInfo(state->v2->desc);

		const char *shader_text = state->v2->desc->getShaderText();
		if (!uploadTexturesV2(state->v2, shader_text)) {
			/* Forget the cache so the next draw tries again. */
			freeTexturesV2(state->v2);
			state->shadercacheid.clear();
			state->program = 0;
			state->ocio_shader = 0;
			glActiveTexture(state->last_texture_unit);
			glBindTexture(GL_TEXTURE_2D, state->last_texture);
			return false;
		}
		os << shader_text << "\n";
#else
		os << ocio_processor->getGpuShaderText(shaderDesc) << "\n";
#endif
		os << datatoc_gpu_shader_display_transform_glsl;

		state->ocio_shader = compileShaderText(GL_FRAGMENT_SHADER, os.str().c_str());

		if (state->ocio_shader) {
			state->program = linkShaders(state->ocio_shader);
		}

		state->curve_mapping_used = use_curve_mapping;
		state->dither_used = use_dither;
		state->predivide_used = use_predivide;
	}

	if (state->program) {
#ifdef OCIO_V2
		glUseProgram(state->program);
		bindTexturesV2(state->v2, state->program);
		setUniformsV2(state->v2, state->program);
#else
		glActiveTexture(GL_TEXTURE1);
		glBindTexture(GL_TEXTURE_3D, state->lut3d_texture);
#endif

		if (use_curve_mapping) {
			glActiveTexture(GL_TEXTURE2);
			glBindTexture(GL_TEXTURE_1D, state->curve_mapping_texture);
		}

		glActiveTexture(GL_TEXTURE0);

		glUseProgram(state->program);

		glUniform1i(glGetUniformLocation(state->program, "image_texture"), 0);
#ifndef OCIO_V2
		glUniform1i(glGetUniformLocation(state->program, "lut3d_texture"), 1);
#endif

		if (state->texture_size_used) {
			/* we use textureSize() if possible for best performance, if not
			 * supported we query the size and pass it as uniform variables */
			GLint width, height;

			glGetTexLevelParameteriv(GL_TEXTURE_2D, 0, GL_TEXTURE_WIDTH, &width);
			glGetTexLevelParameteriv(GL_TEXTURE_2D, 0, GL_TEXTURE_HEIGHT, &height);

			glUniform1f(glGetUniformLocation(state->program, "image_texture_width"), (float)width);
			glUniform1f(glGetUniformLocation(state->program, "image_texture_height"), (float)height);
		}

		if (use_dither) {
			glUniform1f(glGetUniformLocation(state->program, "dither"), dither);
		}

		if (use_curve_mapping) {
			glUniform1i(glGetUniformLocation(state->program, "curve_mapping_texture"), 2);
			glUniform1i(glGetUniformLocation(state->program, "curve_mapping_lut_size"), curve_mapping_settings->lut_size);
			glUniform4iv(glGetUniformLocation(state->program, "use_curve_mapping_extend_extrapolate"), 1, curve_mapping_settings->use_extend_extrapolate);
			glUniform4fv(glGetUniformLocation(state->program, "curve_mapping_mintable"), 1, curve_mapping_settings->mintable);
			glUniform4fv(glGetUniformLocation(state->program, "curve_mapping_range"), 1, curve_mapping_settings->range);
			glUniform4fv(glGetUniformLocation(state->program, "curve_mapping_ext_in_x"), 1, curve_mapping_settings->ext_in_x);
			glUniform4fv(glGetUniformLocation(state->program, "curve_mapping_ext_in_y"), 1, curve_mapping_settings->ext_in_y);
			glUniform4fv(glGetUniformLocation(state->program, "curve_mapping_ext_out_x"), 1, curve_mapping_settings->ext_out_x);
			glUniform4fv(glGetUniformLocation(state->program, "curve_mapping_ext_out_y"), 1, curve_mapping_settings->ext_out_y);
			glUniform4fv(glGetUniformLocation(state->program, "curve_mapping_first_x"), 1, curve_mapping_settings->first_x);
			glUniform4fv(glGetUniformLocation(state->program, "curve_mapping_first_y"), 1, curve_mapping_settings->first_y);
			glUniform4fv(glGetUniformLocation(state->program, "curve_mapping_last_x"), 1, curve_mapping_settings->last_x);
			glUniform4fv(glGetUniformLocation(state->program, "curve_mapping_last_y"), 1, curve_mapping_settings->last_y);
			glUniform3fv(glGetUniformLocation(state->program, "curve_mapping_black"), 1, curve_mapping_settings->black);
			glUniform3fv(glGetUniformLocation(state->program, "curve_mapping_bwmul"), 1, curve_mapping_settings->bwmul);
		}

		return true;
	}
	else {
		glActiveTexture(state->last_texture_unit);
		glBindTexture(GL_TEXTURE_2D, state->last_texture);

		return false;
	}
}

void OCIOImpl::finishGLSLDraw(OCIO_GLSLDrawState *state)
{
	glActiveTexture(state->last_texture_unit);
	glBindTexture(GL_TEXTURE_2D, state->last_texture);
	glUseProgram(0);
}

void OCIOImpl::freeGLState(struct OCIO_GLSLDrawState *state)
{
	using std::string;

	if (state->lut3d_texture_allocated)
		glDeleteTextures(1, &state->lut3d_texture);

	if (state->lut3d)
		MEM_freeN(state->lut3d);

	if (state->program)
		glDeleteProgram(state->program);

	if (state->ocio_shader)
		glDeleteShader(state->ocio_shader);

#ifdef OCIO_V2
	freeTexturesV2(state->v2);
	delete state->v2;
#endif

	state->lut3dcacheid.~string();
	state->shadercacheid.~string();

	MEM_freeN(state);
}
