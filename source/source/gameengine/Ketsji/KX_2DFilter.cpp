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
 * Contributor(s): Ulysse Martin, Tristan Porteries.
 *
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file gameengine/Ketsji/KX_2DFilter.cpp
 *  \ingroup ketsji
 */

#include "KX_2DFilter.h"
#include "KX_2DFilterOffScreen.h"
#include "RAS_Texture.h" // for RAS_Texture::MaxUnits

#include "CM_Message.h"
#include "KX_2DFilterManager.h"

#include "GPU_glew.h"
#include "GPU_shader.h"

#include <functional>

KX_2DFilter::KX_2DFilter(RAS_2DFilterData& data)
	:RAS_2DFilter(data),
	BL_Shader(nullptr)
{
}

KX_2DFilter::~KX_2DFilter()
{
}

bool KX_2DFilter::LinkProgram()
{
	return RAS_2DFilter::LinkProgram();
}

void KX_2DFilter::UpdateTextureBindCode(int index, int bindCode)
{
	const auto it = m_textures.find(index);
	if (it != m_textures.end()) {
		it->second.second = bindCode;
	}
}

/// Uniform type of a GL type and its number of components, UNI_NONE if setUniform() can't set it.
static int uniform_type(unsigned int glType, int& components, bool& isInt)
{
	isInt = false;
	switch (glType) {
		case GL_FLOAT: components = 1; return RAS_Shader::RAS_Uniform::UNI_FLOAT;
		case GL_FLOAT_VEC2: components = 2; return RAS_Shader::RAS_Uniform::UNI_FLOAT2;
		case GL_FLOAT_VEC3: components = 3; return RAS_Shader::RAS_Uniform::UNI_FLOAT3;
		case GL_FLOAT_VEC4: components = 4; return RAS_Shader::RAS_Uniform::UNI_FLOAT4;
		case GL_FLOAT_MAT3: components = 9; return RAS_Shader::RAS_Uniform::UNI_MAT3;
		case GL_FLOAT_MAT4: components = 16; return RAS_Shader::RAS_Uniform::UNI_MAT4;
		case GL_BOOL:
		case GL_INT:
		case GL_SAMPLER_2D:
		case GL_SAMPLER_CUBE:
			isInt = true; components = 1; return RAS_Shader::RAS_Uniform::UNI_INT;
		case GL_BOOL_VEC2:
		case GL_INT_VEC2: isInt = true; components = 2; return RAS_Shader::RAS_Uniform::UNI_INT2;
		case GL_BOOL_VEC3:
		case GL_INT_VEC3: isInt = true; components = 3; return RAS_Shader::RAS_Uniform::UNI_INT3;
		case GL_BOOL_VEC4:
		case GL_INT_VEC4: isInt = true; components = 4; return RAS_Shader::RAS_Uniform::UNI_INT4;
	}
	components = 0;
	return RAS_Shader::RAS_Uniform::UNI_NONE;
}

static const char *uniform_type_name(unsigned int glType)
{
	switch (glType) {
		case GL_FLOAT: return "float";
		case GL_FLOAT_VEC2: return "vec2";
		case GL_FLOAT_VEC3: return "vec3";
		case GL_FLOAT_VEC4: return "vec4";
		case GL_FLOAT_MAT3: return "mat3";
		case GL_FLOAT_MAT4: return "mat4";
		case GL_BOOL: return "bool";
		case GL_INT: return "int";
		case GL_INT_VEC2: return "ivec2";
		case GL_INT_VEC3: return "ivec3";
		case GL_INT_VEC4: return "ivec4";
		case GL_SAMPLER_2D: return "sampler2D";
		case GL_SAMPLER_CUBE: return "samplerCube";
	}
	return "other";
}

std::vector<KX_2DFilter::ActiveUniform> KX_2DFilter::GetActiveUniforms() const
{
	std::vector<ActiveUniform> result;
	if (!m_shader) {
		return result;
	}
	const unsigned int program = GPU_shader_program(m_shader);
	GLint count = 0;
	glGetProgramiv(program, GL_ACTIVE_UNIFORMS, &count);
	for (GLint i = 0; i < count; ++i) {
		char name[256];
		GLsizei length = 0;
		GLint size = 0;
		GLenum type = 0;
		glGetActiveUniform(program, i, sizeof(name), &length, &size, &type, name);
		std::string str(name, length);
		// Arrays are reported as "name[0]".
		const size_t bracket = str.find('[');
		if (bracket != std::string::npos) {
			str.erase(bracket);
		}
		if (str.compare(0, 3, "gl_") == 0) {
			continue;
		}
		result.push_back({str, (unsigned int)type, size});
	}
	return result;
}

bool KX_2DFilter::ApplyNamedUniform(const std::string& name, const UniformValue& value)
{
	for (const ActiveUniform& info : GetActiveUniforms()) {
		if (info.name != name) {
			continue;
		}
		int components;
		bool isInt;
		const int type = uniform_type(info.glType, components, isInt);
		const int loc = GetUniformLocation(name, false);
		if (type == RAS_Shader::RAS_Uniform::UNI_NONE || loc == -1) {
			return false;
		}
		const unsigned int count = (isInt ? value.ints.size() : value.floats.size()) / components;
		if (count == 0) {
			return false;
		}
		if (isInt) {
			SetUniformiv(loc, type, value.ints.data(), sizeof(int) * components * count, count);
		}
		else {
			SetUniformfv(loc, type, value.floats.data(), sizeof(float) * components * count, count);
		}
		return true;
	}
	return false;
}

bool KX_2DFilter::Recompile(const std::string& fragment)
{
	if (!RAS_2DFilter::Recompile(fragment)) {
		return false;
	}
	for (const auto& pair : m_namedUniforms) {
		ApplyNamedUniform(pair.first, pair.second);
	}
	return true;
}

#ifdef WITH_PYTHON

bool KX_2DFilter::CheckTexture(int index, int bindCode, const std::string& prefix) const
{
	if (!m_shader) {
		PyErr_Format(PyExc_ValueError, "%s: KX_2DFilter, No valid shader found", prefix.c_str());
		return false;
	}
	if (index < 0 || index >= RAS_Texture::MaxUnits) {
		PyErr_Format(PyExc_ValueError, "%s: KX_2DFilter, index out of range [0, %i]", prefix.c_str(), (RAS_Texture::MaxUnits - 1));
		return false;
	}
	if (bindCode < 0) {
		PyErr_Format(PyExc_ValueError, "%s: KX_2DFilter, bindCode negative", prefix.c_str());
		return false;
	}

	return true;
}

bool KX_2DFilter::SetTextureUniform(int index, const char *samplerName)
{
	if (samplerName) {
		if (GetError()) {
			return false;
		}
		int loc = GetUniformLocation(samplerName);

		if (loc != -1) {
#ifdef SORT_UNIFORMS
			SetUniformiv(loc, RAS_Shader::RAS_Uniform::UNI_INT, &index, (sizeof(int)), 1);
#else
			SetUniform(loc, index);
#endif
		}
	}

	return true;
}

void KX_2DFilter::SetTexture(int index, int bindCode, char *samplerName)
{
	if (!CheckTexture(index, bindCode, "setTexture(index, bindCode, samplerName)")) {
		return;
	}

	if (!SetTextureUniform(index, samplerName)) {
		return;
	}

	m_textures[index] = {RAS_Texture::GetTexture2DType(), bindCode};
}

PyTypeObject KX_2DFilter::Type = {
	PyVarObject_HEAD_INIT(nullptr, 0)
	"KX_2DFilter",
	sizeof(EXP_PyObjectPlus_Proxy),
	0,
	py_base_dealloc,
	0,
	0,
	0,
	0,
	py_base_repr,
	0, 0, 0, 0, 0, 0, 0, 0, 0,
	Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
	0, 0, 0, 0, 0, 0, 0,
	Methods,
	0,
	0,
	&BL_Shader::Type,
	0, 0, 0, 0, 0, 0,
	py_base_new
};

PyMethodDef KX_2DFilter::Methods[] = {
	EXP_PYMETHODTABLE(KX_2DFilter, setTexture),
	EXP_PYMETHODTABLE(KX_2DFilter, setCubeMap),
	EXP_PYMETHODTABLE_KEYWORDS(KX_2DFilter, addOffScreen),
	EXP_PYMETHODTABLE_NOARGS(KX_2DFilter, removeOffScreen),
	EXP_PYMETHODTABLE(KX_2DFilter, recompile),
	EXP_PYMETHODTABLE(KX_2DFilter, setUniform),
	{nullptr, nullptr} // Sentinel
};

PyAttributeDef KX_2DFilter::Attributes[] = {
	EXP_PYATTRIBUTE_RW_FUNCTION("mipmap", KX_2DFilter, pyattr_get_mipmap, pyattr_set_mipmap),
	EXP_PYATTRIBUTE_RO_FUNCTION("offScreen", KX_2DFilter, pyattr_get_offScreen),
	EXP_PYATTRIBUTE_RO_FUNCTION("compileLog", KX_2DFilter, pyattr_get_compileLog),
	EXP_PYATTRIBUTE_RO_FUNCTION("sourceName", KX_2DFilter, pyattr_get_sourceName),
	EXP_PYATTRIBUTE_RO_FUNCTION("sourcePath", KX_2DFilter, pyattr_get_sourcePath),
	EXP_PYATTRIBUTE_RO_FUNCTION("activeUniforms", KX_2DFilter, pyattr_get_activeUniforms),
	EXP_PYATTRIBUTE_NULL // Sentinel
};

PyObject *KX_2DFilter::pyattr_get_mipmap(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_2DFilter *self = static_cast<KX_2DFilter *>(self_v);
	return PyBool_FromLong(self->GetMipmap());
}

int KX_2DFilter::pyattr_set_mipmap(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_2DFilter *self = static_cast<KX_2DFilter *>(self_v);
	int param = PyObject_IsTrue(value);
	if (param == -1) {
		PyErr_SetString(PyExc_AttributeError, "shader.enabled = bool: BL_Shader, expected True or False");
		return PY_SET_ATTR_FAIL;
	}

	self->SetMipmap(param);
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_2DFilter::pyattr_get_offScreen(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_2DFilter *self = static_cast<KX_2DFilter *>(self_v);
	RAS_2DFilterOffScreen *offScreen = self->GetOffScreen();
	return offScreen ? static_cast<KX_2DFilterOffScreen *>(offScreen)->GetProxy() : Py_None;
}

PyObject *KX_2DFilter::pyattr_get_compileLog(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_2DFilter *self = static_cast<KX_2DFilter *>(self_v);
	return PyUnicode_FromStdString(self->GetCompileLog());
}

PyObject *KX_2DFilter::pyattr_get_sourceName(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_2DFilter *self = static_cast<KX_2DFilter *>(self_v);
	return PyUnicode_FromStdString(self->GetSourceName());
}

PyObject *KX_2DFilter::pyattr_get_sourcePath(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_2DFilter *self = static_cast<KX_2DFilter *>(self_v);
	return PyUnicode_FromStdString(self->GetSourcePath());
}

PyObject *KX_2DFilter::pyattr_get_activeUniforms(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_2DFilter *self = static_cast<KX_2DFilter *>(self_v);
	const std::vector<ActiveUniform> uniforms = self->GetActiveUniforms();
	PyObject *list = PyList_New(uniforms.size());
	for (unsigned int i = 0, size = uniforms.size(); i < size; ++i) {
		const ActiveUniform& info = uniforms[i];
		PyList_SET_ITEM(list, i, Py_BuildValue("(ssi)", info.name.c_str(), uniform_type_name(info.glType), info.size));
	}
	return list;
}

EXP_PYMETHODDEF_DOC(KX_2DFilter, recompile, "recompile(fragmentProgram=None): compile a new source, or read the external text file again. Returns True on success, else see compileLog.")
{
	char *frag = nullptr;
	if (!PyArg_ParseTuple(args, "|z:recompile", &frag)) {
		return nullptr;
	}

	bool ok;
	if (frag) {
		ok = Recompile(std::string(frag));
	}
	else if (!GetSourcePath().empty()) {
		ok = KX_2DFilterManager::ReloadSource(this);
	}
	else {
		ok = Recompile(m_progs[FRAGMENT_PROGRAM]);
	}
	return PyBool_FromLong(ok);
}

EXP_PYMETHODDEF_DOC(KX_2DFilter, setUniform, "setUniform(name, value): set a uniform by name, the type comes from the shader (float, vec2-4, int, ivec2-4, bool, mat3, mat4 or arrays of them). The value is kept after a recompile.")
{
	char *name;
	PyObject *pyvalue;
	if (!PyArg_ParseTuple(args, "sO:setUniform", &name, &pyvalue)) {
		return nullptr;
	}

	// Flatten numbers, sequences and sequences of sequences (matrices, arrays of vectors).
	std::vector<double> numbers;
	std::function<bool(PyObject *, int)> flatten = [&numbers, &flatten](PyObject *item, int depth) -> bool {
		if (PyNumber_Check(item) && !PySequence_Check(item)) {
			const double value = PyFloat_AsDouble(item);
			if (value == -1.0 && PyErr_Occurred()) {
				return false;
			}
			numbers.push_back(value);
			return true;
		}
		if (depth < 2 && PySequence_Check(item)) {
			const Py_ssize_t size = PySequence_Size(item);
			for (Py_ssize_t i = 0; i < size; ++i) {
				PyObject *sub = PySequence_GetItem(item, i);
				const bool ok = sub && flatten(sub, depth + 1);
				Py_XDECREF(sub);
				if (!ok) {
					return false;
				}
			}
			return true;
		}
		PyErr_SetString(PyExc_TypeError, "filter.setUniform(name, value): KX_2DFilter, value must be a number or a sequence of numbers");
		return false;
	};
	if (!flatten(pyvalue, 0)) {
		return nullptr;
	}

	for (const ActiveUniform& info : GetActiveUniforms()) {
		if (info.name != name) {
			continue;
		}
		int components;
		bool isInt;
		if (uniform_type(info.glType, components, isInt) == RAS_Shader::RAS_Uniform::UNI_NONE) {
			PyErr_Format(PyExc_TypeError, "filter.setUniform(name, value): KX_2DFilter, uniform \"%s\" has an unsupported type", name);
			return nullptr;
		}
		if (numbers.empty() || numbers.size() % components != 0 || numbers.size() / components > (size_t)info.size) {
			PyErr_Format(PyExc_ValueError, "filter.setUniform(name, value): KX_2DFilter, uniform \"%s\" (%s[%i]) expects a multiple of %i values, got %i",
			             name, uniform_type_name(info.glType), info.size, components, (int)numbers.size());
			return nullptr;
		}
		UniformValue value;
		value.isInt = isInt;
		for (double number : numbers) {
			value.floats.push_back((float)number);
			value.ints.push_back((int)number);
		}
		// GL wants column major matrices, Python (mathutils) gives rows.
		if (components == 9 || components == 16) {
			const int n = (components == 9) ? 3 : 4;
			for (size_t m = 0; m < value.floats.size(); m += components) {
				const std::vector<float> tmp(value.floats.begin() + m, value.floats.begin() + m + components);
				for (int r = 0; r < n; ++r) {
					for (int c = 0; c < n; ++c) {
						value.floats[m + c * n + r] = tmp[r * n + c];
					}
				}
			}
		}
		ApplyNamedUniform(name, value);
		m_namedUniforms[name] = value;
		Py_RETURN_NONE;
	}

	PyErr_Format(PyExc_KeyError, "filter.setUniform(name, value): KX_2DFilter, no active uniform \"%s\" (the driver removes unused uniforms, see activeUniforms)", name);
	return nullptr;
}

EXP_PYMETHODDEF_DOC(KX_2DFilter, setTexture, "setTexture(index, bindCode, samplerName)")
{
	int index = 0;
	int bindCode = 0;
	char *samplerName = nullptr;

	if (!PyArg_ParseTuple(args, "ii|s:setTexture", &index, &bindCode, &samplerName)) {
		return nullptr;
	}

	SetTexture(index, bindCode, samplerName);

	Py_RETURN_NONE;
}

EXP_PYMETHODDEF_DOC(KX_2DFilter, setCubeMap, "setCubeMap(index, bindCode, samplerName)")
{
	int index = 0;
	int bindCode = 0;
	char *samplerName = nullptr;

	if (!PyArg_ParseTuple(args, "ii|s:setCubeMap", &index, &bindCode, &samplerName)) {
		return nullptr;
	}

	if (!CheckTexture(index, bindCode, "setCubeMap(index, bindCode, samplerName)")) {
		return nullptr;
	}

	if (!SetTextureUniform(index, samplerName)) {
		return nullptr;
	}

	m_textures[index] = {RAS_Texture::GetCubeMapTextureType(), bindCode};
	Py_RETURN_NONE;
}

EXP_PYMETHODDEF_DOC(KX_2DFilter, addOffScreen, " addOffScreen(slots, depth, width, height, hdr,  mipmap)")
{
	int slots;
	int depth = 0;
	int width = -1;
	int height = -1;
	int hdr = RAS_Rasterizer::RAS_HDR_NONE;
	int mipmap = 0;
	int flag = 0;

	if (!EXP_ParseTupleArgsAndKeywords(args, kwds, "i|iiiii:addOffScreen",
	                                   {"slots", "depth", "width", "height", "hdr", "mipmap", 0},
	                                   &slots, &depth, &width, &height, &hdr, &mipmap)) {
		return nullptr;
	}

	if (GetOffScreen()) {
		PyErr_SetString(PyExc_TypeError, "filter.addOffScreen(...): KX_2DFilter, custom off screen already exists.");
		return nullptr;
	}

	if (slots < 0 || slots >= 8) {
		PyErr_SetString(PyExc_TypeError, "filter.addOffScreen(...): KX_2DFilter, slots must be between 0 and 8 excluded.");
		return nullptr;
	}

	if (hdr < 0 || hdr > RAS_Rasterizer::RAS_HDR_MAX) {
		PyErr_SetString(PyExc_TypeError, "filter.addOffScreen(...): KX_2DFilter, invalid hdr value.");
		return nullptr;
	}

	if (width < -1 || height < -1 || width == 0 || height == 0) {
		PyErr_SetString(PyExc_TypeError, "filter.addOffScreen(...): KX_2DFilter, invalid size values.");
		return nullptr;
	}

	if (slots == 0 && !depth) {
		PyErr_SetString(PyExc_TypeError, "filter.addOffScreen(...): KX_2DFilter, empty off screen, slots must be at least to 1 or depth to True.");
		return nullptr;
	}

	if (width == -1 || height == -1) {
		flag |= RAS_2DFilterOffScreen::RAS_VIEWPORT_SIZE;
	}

	if (mipmap) {
		flag |= RAS_2DFilterOffScreen::RAS_MIPMAP;
	}

	if (depth) {
		flag |= RAS_2DFilterOffScreen::RAS_DEPTH;
	}

	KX_2DFilterOffScreen *offScreen = new KX_2DFilterOffScreen(slots, (RAS_2DFilterOffScreen::Flag)flag, width, height,
	                                                           (RAS_Rasterizer::HdrType)hdr);

	SetOffScreen(offScreen);

	return offScreen->GetProxy();
}

EXP_PYMETHODDEF_DOC_NOARGS(KX_2DFilter, removeOffScreen, " removeOffScreen()")
{
	SetOffScreen(nullptr);
	Py_RETURN_NONE;
}

#endif  // WITH_PYTHON
