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

/** \file KX_2DFilter.h
*  \ingroup ketsji
*/

#ifndef __KX_2DFILTER_H__
#define __KX_2DFILTER_H__

#include "RAS_2DFilter.h"
#include "BL_Shader.h"

#include <map>

#ifdef _MSC_VER
/* KX_2DFilter uses a diamond inheritance from a virtual pure base class. Only one branch of the diamond
 * define these virtual pure functions and come in the final class with dominance. This behaviour is wanted
 * but MSVC warn about it, we just disable the warning.
 */
#  pragma warning(disable:4250)
#endif

class KX_2DFilter : public RAS_2DFilter, public BL_Shader
{
	Py_Header
public:
	KX_2DFilter(RAS_2DFilterData& data);
	virtual ~KX_2DFilter();

	virtual bool LinkProgram();

	/// Replace the bind code of an already set texture unit; unlike SetTexture it never raises Python errors.
	void UpdateTextureBindCode(int index, int bindCode);

	/// Recompile and set again the uniforms given to setUniform().
	virtual bool Recompile(const std::string& fragment);

	struct ActiveUniform {
		std::string name;
		unsigned int glType;
		int size;
	};
	/// Uniforms the linked program really uses (the driver drops unused ones).
	std::vector<ActiveUniform> GetActiveUniforms() const;

#ifdef WITH_PYTHON
	bool CheckTexture(int index, int bindCode, const std::string& prefix) const;
	bool SetTextureUniform(int index, const char *samplerName);
	void SetTexture(int index, int bindCode, char *samplerName);

	static PyObject *pyattr_get_mipmap(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int pyattr_set_mipmap(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);
	static PyObject *pyattr_get_offScreen(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_compileLog(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_sourceName(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_sourcePath(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_activeUniforms(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);

	EXP_PYMETHOD_DOC(KX_2DFilter, setTexture);
	EXP_PYMETHOD_DOC(KX_2DFilter, setCubeMap);
	EXP_PYMETHOD_DOC(KX_2DFilter, addOffScreen);
	EXP_PYMETHOD_DOC_NOARGS(KX_2DFilter, removeOffScreen);
	EXP_PYMETHOD_DOC(KX_2DFilter, recompile);
	EXP_PYMETHOD_DOC(KX_2DFilter, setUniform);

#endif

	/// Same as setUniform() from C++: float values, kept after a recompile. False if the uniform is not active.
	bool SetNamedUniform(const std::string& name, const std::vector<float>& values);

	/// Filters that get the same setUniform() values (the texture passes of the compositor tree).
	void AddUniformShare(KX_2DFilter *filter);

private:
	/// Values given to setUniform(), by name so they survive a recompile.
	struct UniformValue {
		bool isInt;
		std::vector<float> floats;
		std::vector<int> ints;
	};
	std::map<std::string, UniformValue> m_namedUniforms;
	std::vector<KX_2DFilter *> m_uniformShares;
	/// Gives the value to the shared filters that have the uniform; true if any had it.
	bool ShareNamedUniform(const std::string& name, const UniformValue& value);
	virtual void SetObjectUniform(const std::string& uniform, unsigned int loc, const std::string& objectName);
	bool ApplyNamedUniform(const std::string& name, const UniformValue& value);
};

#endif  // __KX_2DFILTER_H__
