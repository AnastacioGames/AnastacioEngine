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

/** \file KX_FontObject.h
 *  \ingroup ketsji
 */

#ifndef __KX_FONTOBJECT_H__
#define  __KX_FONTOBJECT_H__

#include "KX_GameObject.h"

#include <string>
#include <unordered_map>
#include <vector>

class RAS_BoundingBox;
struct Curve;
struct GPUTexture;

/// Current language for game text (filled by the range_locale Python module, Range.locale).
struct KX_LocaleState {
	/// translation key -> text in the current language (fallbacks already resolved).
	std::unordered_map<std::string, std::string> table;
	/// Font (VFont name) and atlas (text Curve name) of the language; empty: the text's own.
	std::string font;
	std::string atlas;
	/// Bumped on every change; texts compare it with their own copy.
	unsigned int version = 0;
};
KX_LocaleState& KX_GetLocale();
void KX_ResetLocale();

class KX_FontObject : public KX_GameObject
{
public:
	Py_Header
	KX_FontObject(void *sgReplicationInfo,
	              SG_Callbacks callbacks,
	              RAS_Rasterizer *rasterizer,
				  RAS_BoundingBoxManager *boundingBoxManager,
	              Object *ob,
	              bool do_color_management);

	virtual ~KX_FontObject();

	virtual void AddMeshUser();
	virtual void UpdateBuckets();

	/**
	 * Inherited from EXP_Value -- return a new copy of this
	 * instance allocated on the heap. Ownership of the new
	 * object belongs with the caller.
	 */
	virtual EXP_Value *GetReplica();
	virtual void ProcessReplica();
	virtual int GetGameObjectType() const
	{
		return OBJ_TEXT;
	}

	// Update text and bounding box.
	void SetText(const std::string& text);
	// Apply text alignment
	void ApplyTextAlignment();
	/// Update text from property.
	void UpdateTextFromProperty();
	/// Return text dimensions in blender unit.
	const mt::vec2 GetTextDimensions();
	/// Take the current language (Range.locale) when it changed since the last call.
	void UpdateLocale();

protected:
	// similar to rna_curve -> prop_align_items
	enum alignType {
		TEXT_ALIGN_X_LEFT,
		TEXT_ALIGN_X_MIDDLE,
		TEXT_ALIGN_X_RIGHT
	};

	enum alignType_y {
		TEXT_ALIGN_Y_TOP_BASELINE,
		TEXT_ALIGN_Y_TOP,
		TEXT_ALIGN_Y_CENTER,
		TEXT_ALIGN_Y_BOTTOM
	};
	
	std::string m_text;
	std::string m_res;
	std::vector<std::string> m_texts;
	Object *m_object;
	int m_fontid;
	int m_dpi;
	float m_fsize;
	float m_resolution;
	float m_line_spacing;
	alignType m_spacemode; // Text align.
	alignType_y m_spacemode_y;
	mt::vec2 m_textAABB_min;
	mt::vec2 m_textAABB_max;
	mt::vec3 m_offset;
	mt::vec3 m_text_offset; // offset with alignment.
	/// shadows
	bool m_use_shadow;
	mt::vec2 m_shadow_offset;
	mt::vec4 m_shadow_color;

	/// Text bounding box for mesh/text user.
	RAS_BoundingBox *m_boundingBox;
	/// needed for drawing routine
	class RAS_Rasterizer *m_rasterizer;

	bool m_do_color_management;

	/// Bitmap atlas (CU_BITMAP_ATLAS): code point -> index in Curve::atlas_glyphs.
	Curve *m_curve;
	std::unordered_map<unsigned int, int> m_atlasLookup;
	/// Glyph quads in text space (x, y, u, v per vertex), rebuilt by SetText.
	std::vector<float> m_atlasQuads;
	mt::vec2 m_atlasMin;
	mt::vec2 m_atlasMax;
	GPUTexture *m_atlasTexture;
	bool m_atlasTextureTried;

	/// Curve whose bitmap atlas is drawn (the text's own, or another one set by language/Python).
	Curve *m_atlasCurve;

	/// Range.locale: translation key, follow the language font and last language version applied.
	std::string m_localeKey;
	bool m_localeFont;
	unsigned int m_localeVersion;

	/// Text Box (first box of the text data): width wraps the lines, height limits them in pages.
	/// 0: no limit. Object units, like the Text Boxes panel.
	mt::vec2 m_boxSize;
	/// Every line after the wrap (m_texts holds only the shown page).
	std::vector<std::string> m_allLines;
	int m_page;
	/// Typewriter: number of characters shown (-1: all), counted on the page.
	int m_visibleChars;

	/// Width of a line in text units (atlas advances or font metrics).
	float LineWidth(const std::string& line) const;
	/// Fill m_allLines from m_text (word wrap on m_boxSize.x) and m_texts with the page.
	void LayoutLines();
	int LinesPerPage() const;
	int PageCount() const;
	/// Characters on the current page (UTF-8 code points, without the line breaks).
	int PageCharCount() const;

	bool UseAtlas() const
	{
		return !m_atlasLookup.empty();
	}
	void BuildAtlasQuads();
	/// Draw with the atlas of cu (nullptr: no atlas, font glyphs).
	void SetAtlasCurve(Curve *cu);
	/// Load the font of vfont (nullptr: the text's own).
	void SetVFont(struct VFont *vfont);
	/// Set the text like Python text does (through the "Text" property when present).
	void SetTextOrProperty(const std::string& text);
	void ApplyLocale();
	void GetTextAabb(mt::vec2& min, mt::vec2& max);

#ifdef WITH_PYTHON
	static PyObject *pyattr_get_text(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int pyattr_set_text(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);
	static PyObject *pyattr_get_dimensions(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_use_shadows(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int pyattr_set_use_shadows(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);
	static PyObject *pyattr_get_shadow_offset(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int pyattr_set_shadow_offset(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);
	static PyObject *pyattr_get_shadow_color(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int pyattr_set_shadow_color(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);
	static PyObject *pyattr_get_font(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int pyattr_set_font(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);
	static PyObject *pyattr_get_atlas(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int pyattr_set_atlas(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);
	static PyObject *pyattr_get_locale_key(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int pyattr_set_locale_key(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);
	static PyObject *pyattr_get_text_box(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int pyattr_set_text_box(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);
	static PyObject *pyattr_get_lines(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_page(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int pyattr_set_page(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);
	static PyObject *pyattr_get_page_count(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_visible_chars(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int pyattr_set_visible_chars(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);
	static PyObject *pyattr_get_char_count(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static PyObject *pyattr_get_locale_font(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef);
	static int pyattr_set_locale_font(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value);
#endif
};

#endif  /* __KX_FONTOBJECT_H__ */
