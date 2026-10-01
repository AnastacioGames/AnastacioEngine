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
 * The Original Code is Copyright (C) 2001-2002 by NaN Holding BV.
 * All rights reserved.
 *
 * The Original Code is: all of this file.
 *
 * Contributor(s): none yet.
 *
 * ***** END GPL LICENSE BLOCK *****
 */

/** \file KX_Mesh.h
 *  \ingroup ketsji
 */

#ifndef __KX_MESH_H__
#define __KX_MESH_H__

#include "RAS_Mesh.h"

#include <memory>

#include "BL_Resource.h"

#include "EXP_Value.h"

class KX_Mesh;
class SCA_LogicManager;
class KX_Scene;

#ifdef WITH_PYTHON
// utility conversion function
bool ConvertPythonToMesh(SCA_LogicManager *logicmgr, PyObject *value, KX_Mesh **object, bool py_none_ok, const char *error_prefix);

#endif  // WITH_PYTHON

class KX_Mesh : public EXP_Value, public BL_Resource, public RAS_Mesh
{
	Py_Header

public:
	/// Glyph placement of a 2.4x bitmap font, see matrixGlyph().
	struct BitmapGlyph {
		float centerx, centery, sizex, sizey, transx, transy, movex, movey, advance;
	};

	/// A 2.4x TexFace "Text" face, drawn as one quad per character of the "Text" property.
	struct BitmapTextFace {
		RAS_DisplayArray *array;
		/// First vertex of the glyph slots, each slot uses numVerts vertices.
		unsigned int firstVertex;
		unsigned short numVerts;
		mt::vec3 co[4];
		mt::vec2 uv[4];
		/// Glyphs for characters 0-255, other characters are drawn as '?'.
		std::shared_ptr<std::vector<BitmapGlyph> > glyphs;
	};

	/// Maximum characters drawn per bitmap text face.
	static const unsigned int BitmapTextMaxChars = 256;

private:
	KX_Scene *m_scene;

	std::vector<BitmapTextFace> m_bitmapTextFaces;
	std::string m_bitmapText;
	bool m_bitmapTextValid;

public:
	KX_Mesh(KX_Scene *scene, Mesh *mesh, const LayersInfo& layersInfo);
	KX_Mesh(KX_Scene *scene, const std::string& name, const LayersInfo& layersInfo);
	KX_Mesh(const KX_Mesh& other);
	virtual ~KX_Mesh();

	// stuff for cvalue related things
	virtual std::string GetName();

	KX_Scene *GetScene() const;

	void SetBitmapTextFaces(const std::vector<BitmapTextFace>& faces);
	bool HasBitmapText() const;
	/// Rebuild the glyph quads of the bitmap text faces when the text changed.
	void UpdateBitmapText(const std::string& text);
	void ReplaceScene(KX_Scene *scene);

#ifdef WITH_PYTHON

	EXP_PYMETHOD(KX_Mesh, GetMaterialName);
	EXP_PYMETHOD(KX_Mesh, GetTextureName);

	// both take materialid (int)
	EXP_PYMETHOD(KX_Mesh, GetVertexArrayLength);
	EXP_PYMETHOD(KX_Mesh, GetVertex);
	EXP_PYMETHOD(KX_Mesh, GetPolygon);
	EXP_PYMETHOD(KX_Mesh, Transform);
	EXP_PYMETHOD(KX_Mesh, TransformUV);
	EXP_PYMETHOD(KX_Mesh, ReplaceMaterial);
	EXP_PYMETHOD_NOARGS(KX_Mesh, Copy);
	EXP_PYMETHOD(KX_Mesh, ConstructBvh);
	EXP_PYMETHOD_NOARGS(KX_Mesh, Destruct);

	static PyObject *pyattr_get_materials(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_numMaterials(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_numPolygons(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_polygons(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);

	unsigned int py_get_polygons_size();
	PyObject *py_get_polygons_item(unsigned int index);

#endif  // WITH_PYTHON
};

#endif  // __KX_MESH_H__
