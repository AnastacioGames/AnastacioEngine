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

#include "RAS_DisplayArray.h"
#include "RAS_DisplayArrayStorage.h"
#include "RAS_StorageVao.h"
#include "RAS_StorageVbo.h"
#include "GPU_vertex_array.h"

/* Core profile has no client-state/fixed-function attribute slots (glVertexPointer etc.), so
 * position/normal/color must bind to explicit attribute locations instead. These numbers are a
 * contract with gpu_shader_vertex.glsl, which must declare matching
 * layout(location = RAS_ATTR_LOC_POSITION) in vec3 position; (and normal/color) under
 * USE_CORE_PROFILE once it's migrated (Phase 3). Other generic attributes (UV, tangent, bone
 * data) keep using attrib.m_loc, queried by name per-material shader, so they never collide with
 * these fixed slots as long as the base vertex shader reserves them explicitly. */
#ifdef WITH_GL_PROFILE_CORE
#  define RAS_ATTR_LOC_POSITION 0
#  define RAS_ATTR_LOC_NORMAL 1
#  define RAS_ATTR_LOC_COLOR 2
#endif

struct AttribData {
	int size;
	GLenum type;
	bool normalized;
};

static const AttribData attribData[RAS_AttributeArray::RAS_ATTRIB_MAX] = {
	{3, GL_FLOAT, false}, // RAS_ATTRIB_POS
	{2, GL_FLOAT, false}, // RAS_ATTRIB_UV
	{3, GL_FLOAT, false}, // RAS_ATTRIB_NORM
	{4, GL_FLOAT, false}, // RAS_ATTRIB_TANGENT
	{4, GL_UNSIGNED_BYTE, true}, // RAS_ATTRIB_COLOR
	{4, GL_FLOAT, false}, // RAS_ATTRIB_BONE_INDEX
	{4, GL_FLOAT, false} // RAS_ATTRIB_BONE_WEIGHT
};

RAS_StorageVao::RAS_StorageVao(const RAS_DisplayArrayLayout &layout, RAS_DisplayArrayStorage *arrayStorage,
                               const RAS_AttributeArray::AttribList& attribList)
{
	GPU_create_vertex_arrays(1, &m_id);
	GPU_bind_vertex_array(m_id);

	RAS_StorageVbo *vbo = arrayStorage->GetVbo();
	vbo->BindVertexBuffer();
	vbo->BindIndexBuffer();

#ifdef WITH_GL_PROFILE_CORE
	glEnableVertexAttribArray(RAS_ATTR_LOC_POSITION);
	glVertexAttribPointer(RAS_ATTR_LOC_POSITION, 3, GL_FLOAT, GL_FALSE, 0, (const void *)layout.position);

	glEnableVertexAttribArray(RAS_ATTR_LOC_NORMAL);
	glVertexAttribPointer(RAS_ATTR_LOC_NORMAL, 3, GL_FLOAT, GL_FALSE, 0, (const void *)layout.normal);

	glEnableVertexAttribArray(RAS_ATTR_LOC_COLOR);
	glVertexAttribPointer(RAS_ATTR_LOC_COLOR, 4, GL_UNSIGNED_BYTE, GL_TRUE, 0, (const void *)layout.colors[0]);
#else
	glEnableClientState(GL_VERTEX_ARRAY);
	glVertexPointer(3, GL_FLOAT, 0, (const void *)layout.position);

	glEnableClientState(GL_NORMAL_ARRAY);
	glNormalPointer(GL_FLOAT, 0, (const void *)layout.normal);

	glEnableClientState(GL_COLOR_ARRAY);
	glColorPointer(4, GL_UNSIGNED_BYTE, 0, (const void *)layout.colors[0]);
#endif

	for (const RAS_AttributeArray::Attrib& attrib : attribList) {
		const RAS_AttributeArray::AttribType type = attrib.m_type;
		intptr_t offset = 0;
		switch (type) {
			case RAS_AttributeArray::RAS_ATTRIB_POS:
			{
				offset = layout.position;
				break;
			}
			case RAS_AttributeArray::RAS_ATTRIB_UV:
			{
				offset = layout.uvs[attrib.m_layer];
				break;
			}
			case RAS_AttributeArray::RAS_ATTRIB_NORM:
			{
				offset = layout.normal;
				break;
			}
			case RAS_AttributeArray::RAS_ATTRIB_TANGENT:
			{
				offset = layout.tangent;
				break;
			}
			case RAS_AttributeArray::RAS_ATTRIB_COLOR:
			{
				offset = layout.colors[attrib.m_layer];
				break;
			}
			case RAS_AttributeArray::RAS_ATTRIB_BONE_INDEX:
			{
				offset = layout.boneIndices;
				break;
			}
			case RAS_AttributeArray::RAS_ATTRIB_BONE_WEIGHT:
			{
				offset = layout.boneWeights;
				break;
			}
			default:
			{
				BLI_assert(false);
				break;
			}
		}

		const unsigned short loc = attrib.m_loc;
		const AttribData& data = attribData[type];

#ifdef WITH_GL_PROFILE_CORE
		/* Core profile has no fixed texture-unit client state; texcoords bind through the same
		 * generic attribute path as any other attribute. */
		(void)attrib.m_texco;
		glEnableVertexAttribArray(loc);
		glVertexAttribPointer(loc, data.size, data.type, data.normalized, 0, (const void *)offset);
#else
		if (attrib.m_texco) {
			glClientActiveTexture(GL_TEXTURE0 + loc);
			glEnableClientState(GL_TEXTURE_COORD_ARRAY);
			glTexCoordPointer(data.size, data.type, 0, (const void *)offset);
		}
		else {
			glEnableVertexAttribArray(loc);
			glVertexAttribPointer(loc, data.size, data.type, data.normalized, 0, (const void *)offset);
		}
#endif
	}

#ifndef WITH_GL_PROFILE_CORE
	glClientActiveTexture(GL_TEXTURE0);
#endif

	// VBO are not tracked by the VAO excepted for IBO.
	vbo->UnbindVertexBuffer();

	GPU_unbind_vertex_array();
}

RAS_StorageVao::~RAS_StorageVao()
{
	GPU_delete_vertex_arrays(1, &m_id);
}

void RAS_StorageVao::BindPrimitives()
{
	GPU_bind_vertex_array(m_id);
}

void RAS_StorageVao::UnbindPrimitives()
{
	GPU_unbind_vertex_array();
}
