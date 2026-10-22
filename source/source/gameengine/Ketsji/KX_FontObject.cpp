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

/** \file gameengine/Ketsji/KX_FontObject.cpp
 *  \ingroup ketsji
 */

#include "KX_FontObject.h"
#include <exception>
#include "DNA_curve_types.h"
#include "DNA_vfont_types.h"
#include "DNA_image_types.h"
#include "KX_Scene.h"
#include "KX_Globals.h"
#include "KX_PythonInit.h"
#include "KX_PyMath.h"
#include "KX_KetsjiEngine.h"
#include "BL_Converter.h"
#include "BLI_math.h"
#include "EXP_StringValue.h"
#include "RAS_Rasterizer.h"
#include "RAS_BucketManager.h"
#include "RAS_MaterialBucket.h"
#include "RAS_BoundingBox.h"
#include "RAS_TextUser.h"

/* paths needed for font load */
#include "BLI_blenlib.h"
#include "BLI_string_utf8.h"
#include "GPU_glew.h"
#include "GPU_texture.h"
#include "BKE_global.h"
#include "BKE_font.h"
#include "BKE_main.h"
#include "DNA_packedFile_types.h"

extern "C" {
#include "BLF_api.h"
}

#include "CM_Message.h"

#define BGE_FONT_RES 100

/* proptotype */
int GetFontId(VFont *font);

KX_LocaleState& KX_GetLocale()
{
	static KX_LocaleState state;
	return state;
}

void KX_ResetLocale()
{
	KX_LocaleState& locale = KX_GetLocale();
	locale.table.clear();
	locale.font.clear();
	locale.atlas.clear();
	++locale.version;
}

/// Datablock by name (without the 2 letter ID code) in the game file, then in libloaded files.
static ID *find_game_id(const std::string& name, ListBase *(*base)(Main *))
{
	if (ID *id = (ID *)BLI_findstring(base(G.main), name.c_str(), offsetof(ID, name) + 2)) {
		return id;
	}
	KX_KetsjiEngine *engine = KX_GetActiveEngine();
	BL_Converter *converter = engine ? engine->GetConverter() : nullptr;
	if (converter) {
		for (Main *maggie : converter->GetMainList()) {
			if (maggie != G.main) {
				if (ID *id = (ID *)BLI_findstring(base(maggie), name.c_str(), offsetof(ID, name) + 2)) {
					return id;
				}
			}
		}
	}
	return nullptr;
}

static ListBase *main_vfonts(Main *bmain)
{
	return &bmain->vfont;
}

static ListBase *main_curves(Main *bmain)
{
	return &bmain->curve;
}

static bool curve_has_atlas(const Curve *cu)
{
	return cu && (cu->flag & CU_BITMAP_ATLAS) && cu->atlas_image && cu->atlas_glyphs &&
	       cu->atlas_count > 0 && cu->atlas_size > 0.0f && cu->atlas_cell > 0.0f;
}

static std::vector<std::string> split_string(std::string str)
{
	std::vector<std::string> text = std::vector<std::string>();

	// Split the string upon new lines
	int begin = 0, end = 0;
	while (end < str.size()) {
		if (str[end] == '\n') {
			text.push_back(str.substr(begin, end - begin));
			begin = end + 1;
		}
		end++;
	}
	// Now grab the last line
	text.push_back(str.substr(begin, end - begin));

	return text;
}

KX_FontObject::KX_FontObject(void *sgReplicationInfo,
                             SG_Callbacks callbacks,
                             RAS_Rasterizer *rasterizer,
                             RAS_BoundingBoxManager *boundingBoxManager,
                             Object *ob,
                             bool do_color_management)
	:KX_GameObject(sgReplicationInfo, callbacks),
	m_object(ob),
	m_dpi(72),
	m_resolution(1.0f),
	m_rasterizer(rasterizer),
	m_do_color_management(do_color_management),
	m_curve(static_cast<Curve *>(ob->data)),
	m_atlasTexture(nullptr),
	m_atlasTextureTried(false),
	m_atlasCurve(nullptr),
	m_localeVersion(0)
{
	Curve *text = static_cast<Curve *> (ob->data);

	SetAtlasCurve(text);
	m_localeKey = text->locale_key;
	m_localeFont = (text->flag & CU_LOCALE_FONT) != 0;
	m_fsize = text->fsize;
	m_line_spacing = text->linedist;
	m_offset = mt::vec3(text->xof, text->yof, 0.0f);
	m_text_offset = mt::vec3(text->xof, text->yof, 0.0f);
	m_spacemode = (alignType)text->spacemode;
	m_spacemode_y = (alignType_y)text->align_y;
	m_fontid = GetFontId(text->vfont);

	m_use_shadow = text->use_shadows;
	m_shadow_offset = mt::vec2(text->shadow_offx, text->shadow_offy);
	m_shadow_color = mt::vec4(text->shadow_col[0], text->shadow_col[1], text->shadow_col[2], text->shadow_col[3]);

	m_boundingBox = new RAS_BoundingBox(boundingBoxManager);

	// Initialize text alignment.
	if (m_spacemode != TEXT_ALIGN_X_LEFT || m_spacemode_y != TEXT_ALIGN_Y_TOP_BASELINE) {
		// Set text string here too (GetTextAabb needs this)
		m_text = text->str;
		m_texts = split_string(text->str);
		GetTextAabb(m_textAABB_min, m_textAABB_max);
	}

	SetText(text->str);
}

KX_FontObject::~KX_FontObject()
{
	if (m_fontid != -1) {
		BLF_unload_id(m_fontid);
	}
}

EXP_Value *KX_FontObject::GetReplica()
{
	KX_FontObject *replica = new KX_FontObject(*this);
	replica->ProcessReplica();
	return replica;
}

void KX_FontObject::ProcessReplica()
{
	KX_GameObject::ProcessReplica();

	if (m_fontid != -1) {
		BLF_addref_id(m_fontid);
	}

	m_boundingBox = m_boundingBox->GetReplica();
	// Added objects: the template (inactive layer) may still have an older language.
	UpdateLocale();
}

void KX_FontObject::AddMeshUser()
{
	m_meshUser = new RAS_TextUser(&m_clientInfo, m_boundingBox);

	RAS_BucketManager *bucketManager = GetScene()->GetBucketManager();
	RAS_DisplayArrayBucket *arrayBucket = bucketManager->GetTextDisplayArrayBucket();

	m_meshUser->SetMatrix(mt::mat4::FromAffineTransform(NodeGetWorldTransform()));
	m_meshUser->SetFrontFace(!IsNegativeScaling());

	m_meshUser->NewMeshSlot(arrayBucket);
}

void KX_FontObject::SetAtlasCurve(Curve *cu)
{
	m_atlasLookup.clear();
	m_atlasCurve = curve_has_atlas(cu) ? cu : nullptr;
	if (m_atlasCurve) {
		for (int i = 0; i < cu->atlas_count; ++i) {
			m_atlasLookup[(unsigned int)cu->atlas_glyphs[i].code] = i;
		}
	}
	// The GPU texture is cached on the Image: only fetch it again at the next draw.
	m_atlasTexture = nullptr;
	m_atlasTextureTried = false;
}

void KX_FontObject::SetVFont(VFont *vfont)
{
	if (!vfont) {
		vfont = m_curve->vfont;
	}
	const int fontid = vfont ? GetFontId(vfont) : -1;
	if (fontid == -1) {
		return;
	}
	if (m_fontid != -1) {
		BLF_unload_id(m_fontid);
	}
	m_fontid = fontid;
}

void KX_FontObject::SetTextOrProperty(const std::string& text)
{
	/* Allow for some logic brick control */
	EXP_Value *tprop = GetProperty("Text");
	if (tprop) {
		EXP_Value *newstringprop = new EXP_StringValue(text, "Text");
		SetProperty("Text", newstringprop);
		newstringprop->Release();
	}
	else {
		SetText(text);
	}
}

void KX_FontObject::UpdateLocale()
{
	if ((!m_localeKey.empty() || m_localeFont) && m_localeVersion != KX_GetLocale().version) {
		ApplyLocale();
	}
}

void KX_FontObject::ApplyLocale()
{
	const KX_LocaleState& locale = KX_GetLocale();
	m_localeVersion = locale.version;

	if (m_localeFont) {
		VFont *vfont = locale.font.empty() ? nullptr : (VFont *)find_game_id(locale.font, main_vfonts);
		if (!locale.font.empty() && !vfont) {
			CM_Warning("Range.locale: font \"" << locale.font << "\" not found in the game file");
		}
		SetVFont(vfont);

		Curve *atlas = m_curve;
		if (locale.atlas == "-") {
			atlas = nullptr;
		}
		else if (!locale.atlas.empty()) {
			atlas = (Curve *)find_game_id(locale.atlas, main_curves);
			if (!curve_has_atlas(atlas)) {
				CM_Warning("Range.locale: atlas \"" << locale.atlas << "\" not found (text data with a bitmap atlas)");
				atlas = nullptr;
			}
		}
		SetAtlasCurve(atlas);
	}

	if (!m_localeKey.empty()) {
		const auto it = locale.table.find(m_localeKey);
		if (it != locale.table.end()) {
			SetTextOrProperty(it->second);
			return;
		}
	}
	// New font/atlas: the glyphs and the alignment change.
	SetText(m_text);
}

void KX_FontObject::UpdateBuckets()
{
	RAS_TextUser *textUser = static_cast<RAS_TextUser *>(m_meshUser);

	UpdateLocale();

	// Update datas and add mesh slot to be rendered only if the object is not culled.
	if (m_sgNode->IsDirty(SG_Node::DIRTY_RENDER)) {
		m_meshUser->SetMatrix(mt::mat4::FromAffineTransform(NodeGetWorldTransform()));
		m_meshUser->SetFrontFace(!IsNegativeScaling());
		m_sgNode->ClearDirty(SG_Node::DIRTY_RENDER);
	}

	// Font Objects don't use the glsl shader, this color management code is copied from gpu_shader_material.glsl
	float color[4];
	if (m_do_color_management) {
		linearrgb_to_srgb_v4(color, m_objectColor.Data());
	}
	else {
		m_objectColor.Pack(color);
	}

	// HARDCODED MULTIPLICATION FACTOR - this will affect the render resolution directly
	const float RES = BGE_FONT_RES * m_resolution;

	const float size = fabs(m_fsize * RES);
	const float aspect = m_fsize / size;

	// Account for offset
	mt::vec3 offset = NodeGetWorldOrientation() * m_text_offset * NodeGetWorldScaling();
	// Orient the spacing vector
	mt::vec3 spacing = NodeGetWorldOrientation() * mt::vec3(0.0f, m_fsize * m_line_spacing, 0.0f) * NodeGetWorldScaling()[1];

	textUser->SetLayer(m_layer);
	textUser->SetColor(mt::vec4(color));
	textUser->SetFontId(m_fontid);
	textUser->SetSize(size);
	textUser->SetDpi(m_dpi);
	textUser->SetAspect(aspect);
	textUser->SetOffset(offset);
	textUser->SetSpacing(spacing);
	textUser->SetTexts(m_texts);
	textUser->SetUseShadows(m_use_shadow);
	textUser->SetShadowOffset(m_shadow_offset);
	textUser->SetShadowColor(m_shadow_color);

	if (UseAtlas() && !m_atlasTextureTried) {
		// GL context needed, so fetched here and not at conversion (cached on the Image).
		ImageUser iuser = {nullptr};
		iuser.ok = 1;
		iuser.frames = 1;
		iuser.sfra = 1;
		m_atlasTexture = GPU_texture_from_blender(m_atlasCurve->atlas_image, &iuser, GL_TEXTURE_2D, false, 0.0, true);
		m_atlasTextureTried = true;
	}
	textUser->SetAtlas(m_atlasTexture, m_atlasTexture ? &m_atlasQuads : nullptr,
	                  m_atlasCurve && (m_atlasCurve->flag & CU_ATLAS_HARD_EDGE) != 0);
	textUser->ActivateMeshSlots();
}

void KX_FontObject::BuildAtlasQuads()
{
	const Curve *cu = m_atlasCurve;
	// Atlas pixels to text space: the font em (atlas_size) maps to the Size of the text.
	const float s = m_fsize / cu->atlas_size;
	const float cell = cu->atlas_cell * s;
	const float pad = cu->atlas_pad * s;
	const float baseline = cu->atlas_baseline * s;
	const float lineSpacing = m_fsize * m_line_spacing;

	m_atlasQuads.clear();
	m_atlasMin = mt::vec2(FLT_MAX);
	m_atlasMax = mt::vec2(-FLT_MAX);
	/* Aligned on the ink of the letters, like the BLF text, not on the cells: they carry the padding
	 * and the empty space above and below each letter, which moved every aligned text. */
	const float (*ink)[4] = BKE_text_atlas_ink(m_atlasCurve);
	mt::vec2 inkMin(FLT_MAX);
	mt::vec2 inkMax(-FLT_MAX);

	for (unsigned short i = 0, count = m_texts.size(); i < count; ++i) {
		const std::string& line = m_texts[i];
		const float top = baseline - lineSpacing * i;
		float pen = 0.0f;
		size_t index = 0;
		while (index < line.size()) {
			const unsigned int code = BLI_str_utf8_as_unicode_step(line.c_str(), &index);
			const auto it = m_atlasLookup.find(code);
			if (it == m_atlasLookup.end()) {
				// Not in the atlas: leave a gap so the rest of the line keeps its place.
				pen += cell * 0.5f;
				continue;
			}
			const TextAtlasGlyph& g = cu->atlas_glyphs[it->second];
			const float x0 = pen - pad;
			const float x1 = x0 + cell;
			const float y0 = top - cell;
			const float quad[16] = {
				x0, y0, g.u0, g.v0,
				x1, y0, g.u1, g.v0,
				x1, top, g.u1, g.v1,
				x0, top, g.u0, g.v1,
			};
			m_atlasQuads.insert(m_atlasQuads.end(), quad, quad + 16);
			if (ink && ink[it->second][2] >= ink[it->second][0]) {
				const float *box = ink[it->second];
				inkMin.x = std::min(inkMin.x, x0 + box[0] * s);
				inkMin.y = std::min(inkMin.y, y0 + box[1] * s);
				inkMax.x = std::max(inkMax.x, x0 + box[2] * s);
				inkMax.y = std::max(inkMax.y, y0 + box[3] * s);
			}
			pen += g.advance * s;
		}
		m_atlasMin.x = std::min(m_atlasMin.x, 0.0f);
		m_atlasMax.x = std::max(m_atlasMax.x, pen);
		m_atlasMin.y = std::min(m_atlasMin.y, top - cell);
		m_atlasMax.y = std::max(m_atlasMax.y, top);
	}
	if (inkMax.x >= inkMin.x) {
		m_atlasMin = inkMin;
		m_atlasMax = inkMax;
	}
}

void KX_FontObject::SetText(const std::string& text)
{
	m_text = text;
	m_texts = split_string(text);
	if (UseAtlas()) {
		BuildAtlasQuads();
	}

	if (m_spacemode != TEXT_ALIGN_X_LEFT || m_spacemode_y != TEXT_ALIGN_Y_TOP_BASELINE) {
		m_text_offset = m_offset;

		// needs an extra update before apply AABB in m_boundingBox.
		GetTextAabb(m_textAABB_min, m_textAABB_max);

		ApplyTextAlignment();
	}

	GetTextAabb(m_textAABB_min, m_textAABB_max);
	m_boundingBox->SetAabb(mt::vec3(m_textAABB_min.x, m_textAABB_min.y, 0.0f), mt::vec3(m_textAABB_max.x, m_textAABB_max.y, 0.0f));
}

void KX_FontObject::ApplyTextAlignment()
{
	switch(m_spacemode) {
		case TEXT_ALIGN_X_LEFT:
			break;
		case TEXT_ALIGN_X_MIDDLE:
			m_text_offset.x -= ((m_textAABB_min.x + m_textAABB_max.x) - m_offset.x) / 2;
			break;
		case TEXT_ALIGN_X_RIGHT:
			m_text_offset.x -= m_textAABB_max.x - m_offset.x;
			break;
		default:
			break;
	}

	switch(m_spacemode_y) {
		case TEXT_ALIGN_Y_TOP_BASELINE:
			break;
		case TEXT_ALIGN_Y_TOP:
			m_text_offset.y -= m_textAABB_max.y - m_offset.y;
			break;
		case TEXT_ALIGN_Y_CENTER:
			m_text_offset.y -= ((m_textAABB_min.y + m_textAABB_max.y) / 2) - m_offset.y;
			break;
		case TEXT_ALIGN_Y_BOTTOM:
			m_text_offset.y -= m_textAABB_min.y - m_offset.y;
			break;
		default:
			break;
	}
}

void KX_FontObject::UpdateTextFromProperty()
{
	// Allow for some logic brick control
	EXP_Value *prop = GetProperty("Text");
	EXP_Value *propR = GetProperty("Text-Res");
	
	if (prop && prop->GetText() != m_text) {
		SetText(prop->GetText());
	}
	if (propR) {
		const std::string resolutionText = propR->GetText();
		if (resolutionText != m_res) {
			try {
				float resolution = std::stof(resolutionText);
				CLAMP(resolution, 0.1f, 18.0f);
				m_resolution = resolution;
			}
			catch (const std::exception &) {
				// Ignore non-numeric logic brick value, keep previous resolution.
			}
			// Cache the input text, including invalid values, rather than converting the
			// numeric resolution to a single character through std::string::operator=.
			m_res = resolutionText;
		}
	}
}

const mt::vec2 KX_FontObject::GetTextDimensions()
{
	mt::vec2 min;
	mt::vec2 max;
	GetTextAabb(min, max);

	// Scale the width and height by the object's scale
	const mt::vec3& scale = NodeGetLocalScaling();

	return mt::vec2((max.x - min.x) * fabs(scale.x), (max.y - min.y) * fabs(scale.y));
}

void KX_FontObject::GetTextAabb(mt::vec2& min, mt::vec2& max)
{
	if (UseAtlas()) {
		if (m_atlasQuads.empty() && !m_texts.empty()) {
			BuildAtlasQuads();
		}
		min = m_atlasMin + mt::vec2(m_text_offset.x, m_text_offset.y);
		max = m_atlasMax + mt::vec2(m_text_offset.x, m_text_offset.y);
		return;
	}

	const float RES = BGE_FONT_RES * m_resolution;

	const float size = m_fsize * RES;
	const float aspect = m_fsize / size;
	const float lineSpacing = m_line_spacing / aspect;

	BLF_size(m_fontid, size, m_dpi);

	min = mt::vec2(FLT_MAX);
	max = mt::vec2(-FLT_MAX);

	for (unsigned short i = 0, count = m_texts.size(); i < count; ++i) {
		rctf box;
		const std::string& text = m_texts[i];
		BLF_boundbox(m_fontid, text.c_str(), text.size(), &box);
		min.x = std::min(min.x, box.xmin);
		min.y = std::min(min.y, box.ymin - lineSpacing * i);
		max.x = std::max(max.x, box.xmax);
		max.y = std::max(max.y, box.ymax - lineSpacing * i);
	}

	/* offset AABB influence */
	min.x += m_text_offset.x * size;
	max.x += m_text_offset.x * size;
	min.y += m_text_offset.y * size;
	max.y += m_text_offset.y * size;

	min *= aspect;
	max *= aspect;
}

int GetFontId(VFont *vfont)
{
	PackedFile *packedfile = nullptr;
	int fontid = -1;

	if (vfont->packedfile) {
		packedfile = vfont->packedfile;
		fontid = BLF_load_mem(vfont->name, (unsigned char *)packedfile->data, packedfile->size);

		if (fontid == -1) {
			CM_Error("packed font \"" << vfont->name << "\" could not be loaded");
			fontid = BLF_load("default");
		}
		return fontid;
	}

	// once we have packed working we can load the builtin font
	if (BKE_vfont_is_builtin(vfont)) {
		fontid = BLF_load("default");
		return fontid;
	}

	// convert from relative to absolute
	char expanded[FILE_MAX];
	BLI_strncpy(expanded, vfont->name, FILE_MAX);

	char libpath[FILE_MAX];
	// Use library path if available and ensure it is absolute.
	if (vfont->id.lib) {
		BLI_strncpy(libpath, vfont->id.lib->name, FILE_MAX);
		BLI_path_abs(libpath, KX_GetMainPath().c_str());
	}
	else {
		BLI_strncpy(libpath, KX_GetMainPath().c_str(), FILE_MAX);
	}
	BLI_path_abs(expanded, libpath);

	fontid = BLF_load(expanded);

	// fallback
	if (fontid == -1) {
		fontid = BLF_load("default");
		CM_Warning("failed loading font \"" << vfont->name << "\"");
	}

	return fontid;
}

#ifdef WITH_PYTHON

/* ------------------------------------------------------------------------- */
/* Python Integration Hooks					                                 */
/* ------------------------------------------------------------------------- */

PyTypeObject KX_FontObject::Type = {
	PyVarObject_HEAD_INIT(nullptr, 0)
	"KX_FontObject",
	sizeof(EXP_PyObjectPlus_Proxy),
	0,
	py_base_dealloc,
	0,
	0,
	0,
	0,
	py_base_repr,
	0,
	&KX_GameObject::Sequence,
	&KX_GameObject::Mapping,
	0, 0, 0,
	nullptr,
	nullptr,
	0,
	Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
	0, 0, 0, 0, 0, 0, 0,
	Methods,
	0,
	0,
	&KX_GameObject::Type,
	0, 0, 0, 0, 0, 0,
	py_base_new
};

PyMethodDef KX_FontObject::Methods[] = {
	{nullptr, nullptr} //Sentinel
};

PyAttributeDef KX_FontObject::Attributes[] = {
	EXP_PYATTRIBUTE_RW_FUNCTION("text", KX_FontObject, pyattr_get_text, pyattr_set_text),
	EXP_PYATTRIBUTE_RO_FUNCTION("dimensions", KX_FontObject, pyattr_get_dimensions),
	EXP_PYATTRIBUTE_FLOAT_RW("size", 0.0001f, 40.0f, KX_FontObject, m_fsize),
	// Clamped from the historical 50.0f: above ~10x the glyph atlas/FreeType rasterization
	// cost grows quadratically for no visible gain, and each new resolution value used at
	// runtime creates a glyph cache entry that is never evicted until the font is unloaded.
	EXP_PYATTRIBUTE_FLOAT_RW("resolution", 0.1f, 10.0f, KX_FontObject, m_resolution),
    EXP_PYATTRIBUTE_RW_FUNCTION("useShadows", KX_FontObject, pyattr_get_use_shadows, pyattr_set_use_shadows),
    EXP_PYATTRIBUTE_RW_FUNCTION("shadowOffset", KX_FontObject, pyattr_get_shadow_offset, pyattr_set_shadow_offset),
    EXP_PYATTRIBUTE_RW_FUNCTION("shadowColor", KX_FontObject, pyattr_get_shadow_color, pyattr_set_shadow_color),
	EXP_PYATTRIBUTE_RW_FUNCTION("font", KX_FontObject, pyattr_get_font, pyattr_set_font),
	EXP_PYATTRIBUTE_RW_FUNCTION("atlas", KX_FontObject, pyattr_get_atlas, pyattr_set_atlas),
	EXP_PYATTRIBUTE_RW_FUNCTION("translationKey", KX_FontObject, pyattr_get_locale_key, pyattr_set_locale_key),
	EXP_PYATTRIBUTE_RW_FUNCTION("useLanguageFont", KX_FontObject, pyattr_get_locale_font, pyattr_set_locale_font),
	/* EXP_PYATTRIBUTE_INT_RW("dpi", 0, 10000, false, KX_FontObject, m_dpi), */// no real need for expose this I think
	EXP_PYATTRIBUTE_NULL    //Sentinel
};

PyObject *KX_FontObject::pyattr_get_font(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_FontObject *self = static_cast<KX_FontObject *>(self_v);
	VFont *vfont = self->m_curve->vfont;
	if (!vfont) {
		Py_RETURN_NONE;
	}
	return PyUnicode_FromString(vfont->id.name + 2);
}

int KX_FontObject::pyattr_set_font(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_FontObject *self = static_cast<KX_FontObject *>(self_v);
	VFont *vfont = nullptr;
	if (value != Py_None) {
		if (!PyUnicode_Check(value)) {
			PyErr_SetString(PyExc_TypeError, "KX_FontObject.font = str: name of a font in the game file, or None");
			return PY_SET_ATTR_FAIL;
		}
		vfont = (VFont *)find_game_id(_PyUnicode_AsString(value), main_vfonts);
		if (!vfont) {
			PyErr_Format(PyExc_ValueError, "KX_FontObject.font: no font named \"%s\" in the game file "
			             "(the font name shown in the Text properties)", _PyUnicode_AsString(value));
			return PY_SET_ATTR_FAIL;
		}
	}
	self->SetVFont(vfont);
	self->SetText(self->m_text);
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_FontObject::pyattr_get_atlas(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_FontObject *self = static_cast<KX_FontObject *>(self_v);
	if (!self->m_atlasCurve) {
		Py_RETURN_NONE;
	}
	return PyUnicode_FromString(self->m_atlasCurve->id.name + 2);
}

int KX_FontObject::pyattr_set_atlas(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_FontObject *self = static_cast<KX_FontObject *>(self_v);
	Curve *cu = nullptr;
	if (value != Py_None) {
		if (!PyUnicode_Check(value)) {
			PyErr_SetString(PyExc_TypeError, "KX_FontObject.atlas = str: name of the text data holding a "
			                "bitmap atlas, \"\" for the own atlas, or None for no atlas");
			return PY_SET_ATTR_FAIL;
		}
		const std::string name = _PyUnicode_AsString(value);
		cu = name.empty() ? self->m_curve : (Curve *)find_game_id(name, main_curves);
		if (!name.empty() && !curve_has_atlas(cu)) {
			PyErr_Format(PyExc_ValueError, "KX_FontObject.atlas: no text data named \"%s\" with a bitmap atlas",
			             name.c_str());
			return PY_SET_ATTR_FAIL;
		}
	}
	self->SetAtlasCurve(cu);
	self->SetText(self->m_text);
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_FontObject::pyattr_get_locale_key(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_FontObject *self = static_cast<KX_FontObject *>(self_v);
	return PyUnicode_FromStdString(self->m_localeKey);
}

int KX_FontObject::pyattr_set_locale_key(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_FontObject *self = static_cast<KX_FontObject *>(self_v);
	if (!PyUnicode_Check(value)) {
		PyErr_SetString(PyExc_TypeError, "KX_FontObject.translationKey = str");
		return PY_SET_ATTR_FAIL;
	}
	self->m_localeKey = _PyUnicode_AsString(value);
	self->m_localeVersion = KX_GetLocale().version - 1;  // apply at the next draw
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_FontObject::pyattr_get_locale_font(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_FontObject *self = static_cast<KX_FontObject *>(self_v);
	return PyBool_FromLong(self->m_localeFont);
}

int KX_FontObject::pyattr_set_locale_font(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_FontObject *self = static_cast<KX_FontObject *>(self_v);
	const int param = PyObject_IsTrue(value);
	if (param == -1) {
		PyErr_SetString(PyExc_TypeError, "KX_FontObject.useLanguageFont = bool");
		return PY_SET_ATTR_FAIL;
	}
	self->m_localeFont = param;
	self->m_localeVersion = KX_GetLocale().version - 1;
	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_FontObject::pyattr_get_text(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_FontObject *self = static_cast<KX_FontObject *>(self_v);
	return PyUnicode_FromStdString(self->m_text);
}

int KX_FontObject::pyattr_set_text(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_FontObject *self = static_cast<KX_FontObject *>(self_v);
	if (!PyUnicode_Check(value)) {
		return PY_SET_ATTR_FAIL;
	}
	self->SetTextOrProperty(_PyUnicode_AsString(value));

	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_FontObject::pyattr_get_dimensions(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_FontObject *self = static_cast<KX_FontObject *>(self_v);
	return PyObjectFrom(self->GetTextDimensions());
}

PyObject *KX_FontObject::pyattr_get_use_shadows(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_FontObject *self = static_cast<KX_FontObject *>(self_v);
	return PyBool_FromLong(self->m_use_shadow);
}

int KX_FontObject::pyattr_set_use_shadows(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_FontObject *self = static_cast<KX_FontObject *>(self_v);
	int param = PyObject_IsTrue(value);

	if (param == -1) {
		PyErr_SetString(PyExc_AttributeError, "KX_FontObject.useShadows = bool: expected True or False");
		return PY_SET_ATTR_FAIL;
	}

	self->m_use_shadow = param;

	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_FontObject::pyattr_get_shadow_offset(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_FontObject *self = static_cast<KX_FontObject *>(self_v);
	return Py_BuildValue("(ff)", self->m_shadow_offset.x, self->m_shadow_offset.y);
}

int KX_FontObject::pyattr_set_shadow_offset(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_FontObject *self = static_cast<KX_FontObject *>(self_v);
	mt::vec2 offset;
	if (!PyVecTo(value, offset)) {
		return PY_SET_ATTR_FAIL;
	}

	self->m_shadow_offset = offset;

	return PY_SET_ATTR_SUCCESS;
}

PyObject *KX_FontObject::pyattr_get_shadow_color(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef)
{
	KX_FontObject *self = static_cast<KX_FontObject *>(self_v);
	return Py_BuildValue("(ffff)", self->m_shadow_color.x, self->m_shadow_color.y, self->m_shadow_color.z, self->m_shadow_color.w);
}

int KX_FontObject::pyattr_set_shadow_color(EXP_PyObjectPlus *self_v, const EXP_PYATTRIBUTE_DEF *attrdef, PyObject *value)
{
	KX_FontObject *self = static_cast<KX_FontObject *>(self_v);
	mt::vec4 color;
	if (!PyVecTo(value, color)) {
		return PY_SET_ATTR_FAIL;
	}

	self->m_shadow_color = color;

	return PY_SET_ATTR_SUCCESS;
}

#endif // WITH_PYTHON
