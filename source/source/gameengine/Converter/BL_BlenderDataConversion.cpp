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
 * Convert blender data to ketsji
 */

/** \file gameengine/Converter/BL_BlenderDataConversion.cpp
 *  \ingroup bgeconv
 */

#ifdef _MSC_VER
#  pragma warning (disable:4786)
#endif

/* Since threaded object update we've disabled in-place
 * curve evaluation (in cases when applying curve modifier
 * with target curve non-evaluated yet).
 *
 * This requires game engine to take care of DAG and object
 * evaluation (currently it's designed to export only objects
 * it able to render).
 *
 * This workaround will make sure that curve_cache for curves
 * is up-to-date.
 */
#define THREADED_DAG_WORKAROUND

#include <math.h>
#include <vector>
#include <algorithm>
#include <memory>


#include "mathfu.h"

#include "PHY_IPhysicsEnvironment.h"
#include "PHY_IVehicle.h"

#ifdef WITH_BULLET
#  include "CcdPhysicsEnvironment.h"
#  include "CcdGraphicController.h"
#endif

#include "RAS_Rasterizer.h"
#include "RAS_ILightObject.h"

#include "RAS_ICanvas.h"
#include "RAS_BucketManager.h"
#include "RAS_BoundingBoxManager.h"
#include "RAS_IMaterial.h"

#include "SG_Node.h"
#include "SG_BBox.h"

#include "SCA_LogicManager.h"
#include "SCA_TimeEventManager.h"

#include "KX_AnimationEvent.h"
#include "KX_AnimationEventManager.h"
#include "KX_BlenderMaterial.h"
#include "KX_BoneParentNodeRelationship.h"
#include "KX_Camera.h"
#include "KX_ClientObjectInfo.h"
#include "KX_EmptyObject.h"
#include "KX_FontObject.h"
#include "KX_GameObject.h"
#include "KX_CutsceneManager.h"
#include "KX_Globals.h"
#include "KX_KetsjiEngine.h"
#include "KX_LightObject.h"
#include "KX_LodManager.h"
#include "KX_Mesh.h"
#include "KX_MotionState.h"
#include "KX_NavMeshObject.h"
#include "KX_NodeRelationships.h"
#include "KX_ObstacleSimulation.h"
#include "KX_PyConstraintBinding.h"
#include "KX_PythonComponent.h"
#include "KX_Scene.h"
#include "KX_SoftBodyDeformer.h"
#include "KX_Speaker.h"
#include "KX_TextureRendererManager.h"
#include "KX_WorldInfo.h"

#include "BL_ActionData.h"
#include "BL_ArmatureObject.h"
#include "BL_BlenderDataConversion.h"
#include "BL_ConvertActuators.h"
#include "BL_ConvertControllers.h"
#include "BL_ConvertObjectInfo.h"
#include "BL_ConvertProperties.h"
#include "BL_ConvertSensors.h"
#include "BL_MeshDeformer.h"
#include "BL_ModifierDeformer.h"
#include "BL_SceneConverter.h"
#include "BL_ShapeDeformer.h"
#include "BL_SkinDeformer.h"
#include "BL_Texture.h"

#include "CM_Message.h"

#include "GPU_texture.h"

// This little block needed for linking to Blender...
#ifdef WIN32
#include "BLI_winstuff.h"
#endif

#include "BLI_utildefines.h"
#include "BLI_listbase.h"
#include "BLI_math.h"
#include "BLI_threads.h"

#include "DNA_action_types.h"
#include "DNA_actuator_types.h"
#include "DNA_armature_types.h"
#include "DNA_camera_types.h"
#include "DNA_constraint_types.h"
#include "DNA_controller_types.h"
#include "DNA_group_types.h"
#include "DNA_image_types.h"
#include "DNA_key_types.h"
#include "DNA_lamp_types.h"
#include "DNA_material_types.h"
#include "DNA_mesh_types.h"
#include "DNA_meshdata_types.h"
#include "DNA_object_force_types.h"
#include "DNA_object_types.h"
#include "DNA_property_types.h"
#include "DNA_python_component_types.h"
#include "DNA_scene_types.h"
#include "DNA_sensor_types.h"
#include "DNA_sound_types.h"
#include "DNA_speaker_types.h"
#include "DNA_text_types.h"
#include "DNA_texture_types.h"
#include "DNA_view3d_types.h"
#include "DNA_world_types.h"

#include "MEM_guardedalloc.h"

#include "BKE_main.h"
#include "BKE_global.h"
#include "BKE_object.h"
#include "BKE_python_component.h"
#include "BKE_key.h"
#include "BKE_mesh.h"

#ifdef WITH_AUDASPACE
typedef float sample_t;
#  include <AUD_Sound.h>
#  include <AUD_Special.h>
#  include <AUD_Device.h>
#  include <AUD_Handle.h>
#endif

extern "C" {
#  include "BKE_scene.h"
#  include "BKE_customdata.h"
#  include "BKE_cdderivedmesh.h"
#  include "BKE_DerivedMesh.h"
#  include "BKE_material.h" // Needed for give_current_material.
#  include "BKE_image.h"
#  include "IMB_imbuf_types.h"
#  include "BKE_displist.h"

extern Material defmaterial;
}

#include "wm_event_types.h"

// For construction to find shared vertices.
struct BL_SharedVertex {
	RAS_DisplayArray *array;
	unsigned int offset;
};

using BL_SharedVertexList = std::vector<BL_SharedVertex>;
using BL_SharedVertexMap = std::vector<BL_SharedVertexList>;

class BL_SharedVertexPredicate
{
private:
	RAS_DisplayArray *m_array;
	mt::vec3_packed m_normal;
	mt::vec4_packed m_tangent;
	mt::vec2_packed m_uvs[RAS_Texture::MaxUnits];
	unsigned int m_colors[RAS_Texture::MaxUnits];

public:
	BL_SharedVertexPredicate(RAS_DisplayArray *array, const mt::vec3_packed& normal, const mt::vec4_packed& tangent, mt::vec2_packed uvs[], unsigned int colors[])
		:m_array(array),
		m_normal(normal),
		m_tangent(tangent)
	{
		const RAS_DisplayArray::Format& format = m_array->GetFormat();

		for (unsigned short i = 0, size = format.uvSize; i < size; ++i) {
			m_uvs[i] = uvs[i];
		}

		for (unsigned short i = 0, size = format.colorSize; i < size; ++i) {
			m_colors[i] = colors[i];
		}
	}

	bool operator()(const BL_SharedVertex& sharedVert) const
	{
		RAS_DisplayArray *otherArray = sharedVert.array;
		if (m_array != otherArray) {
			return false;
		}

		const unsigned int offset = sharedVert.offset;

		static const float eps = FLT_EPSILON;
		if (!compare_v3v3(m_array->GetNormal(offset).data, m_normal.data, eps) ||
			!compare_v3v3(m_array->GetTangent(offset).data, m_tangent.data, eps))
		{
			return false;
		}

		const RAS_DisplayArray::Format& format = m_array->GetFormat();
		for (unsigned short i = 0, size = format.uvSize; i < size; ++i) {
			if (!compare_v2v2(m_array->GetUv(offset, i).data, m_uvs[i].data, eps)) {
				return false;
			}
		}

		for (unsigned short i = 0, size = format.colorSize; i < size; ++i) {
			if (m_array->GetRawColor(offset, i) != m_colors[i]) {
				return false;
			}
		}

		return true;
	}
};

/* The reverse table. In order to not confuse ourselves, we
 * immediately convert all events that come in to KX codes. */
static std::map<int, SCA_IInputDevice::SCA_EnumInputs> gReverseKeyTranslateTable = {
	{LEFTMOUSE, SCA_IInputDevice::LEFTMOUSE},
	{MIDDLEMOUSE, SCA_IInputDevice::MIDDLEMOUSE},
	{RIGHTMOUSE, SCA_IInputDevice::RIGHTMOUSE},
	{BUTTON4MOUSE, SCA_IInputDevice::LEFTTHUMBMOUSE},
	{BUTTON5MOUSE, SCA_IInputDevice::RIGHTTHUMBMOUSE},
	{BUTTON6MOUSE, SCA_IInputDevice::BUTTON6MOUSE},
	{BUTTON7MOUSE, SCA_IInputDevice::BUTTON7MOUSE},
	{WHEELUPMOUSE, SCA_IInputDevice::WHEELUPMOUSE},
	{WHEELDOWNMOUSE, SCA_IInputDevice::WHEELDOWNMOUSE},
	{MOUSEMOVE, SCA_IInputDevice::MOUSEX},
	{ACTIONMOUSE, SCA_IInputDevice::MOUSEY},
	// Standard keyboard.
	{AKEY, SCA_IInputDevice::AKEY},
	{BKEY, SCA_IInputDevice::BKEY},
	{CKEY, SCA_IInputDevice::CKEY},
	{DKEY, SCA_IInputDevice::DKEY},
	{EKEY, SCA_IInputDevice::EKEY},
	{FKEY, SCA_IInputDevice::FKEY},
	{GKEY, SCA_IInputDevice::GKEY},
	{HKEY, SCA_IInputDevice::HKEY_},
	{IKEY, SCA_IInputDevice::IKEY},
	{JKEY, SCA_IInputDevice::JKEY},
	{KKEY, SCA_IInputDevice::KKEY},
	{LKEY, SCA_IInputDevice::LKEY},
	{MKEY, SCA_IInputDevice::MKEY},
	{NKEY, SCA_IInputDevice::NKEY},
	{OKEY, SCA_IInputDevice::OKEY},
	{PKEY, SCA_IInputDevice::PKEY},
	{QKEY, SCA_IInputDevice::QKEY},
	{RKEY, SCA_IInputDevice::RKEY},
	{SKEY, SCA_IInputDevice::SKEY},
	{TKEY, SCA_IInputDevice::TKEY},
	{UKEY, SCA_IInputDevice::UKEY},
	{VKEY, SCA_IInputDevice::VKEY},
	{WKEY, SCA_IInputDevice::WKEY},
	{XKEY, SCA_IInputDevice::XKEY},
	{YKEY, SCA_IInputDevice::YKEY},
	{ZKEY, SCA_IInputDevice::ZKEY},

	{ZEROKEY, SCA_IInputDevice::ZEROKEY},
	{ONEKEY, SCA_IInputDevice::ONEKEY},
	{TWOKEY, SCA_IInputDevice::TWOKEY},
	{THREEKEY, SCA_IInputDevice::THREEKEY},
	{FOURKEY, SCA_IInputDevice::FOURKEY},
	{FIVEKEY, SCA_IInputDevice::FIVEKEY},
	{SIXKEY, SCA_IInputDevice::SIXKEY},
	{SEVENKEY, SCA_IInputDevice::SEVENKEY},
	{EIGHTKEY, SCA_IInputDevice::EIGHTKEY},
	{NINEKEY, SCA_IInputDevice::NINEKEY},

	{CAPSLOCKKEY, SCA_IInputDevice::CAPSLOCKKEY},

	{LEFTCTRLKEY, SCA_IInputDevice::LEFTCTRLKEY},
	{LEFTALTKEY, SCA_IInputDevice::LEFTALTKEY},
	{RIGHTALTKEY, SCA_IInputDevice::RIGHTALTKEY},
	{RIGHTCTRLKEY, SCA_IInputDevice::RIGHTCTRLKEY},
	{RIGHTSHIFTKEY, SCA_IInputDevice::RIGHTSHIFTKEY},
	{LEFTSHIFTKEY, SCA_IInputDevice::LEFTSHIFTKEY},

	{ESCKEY, SCA_IInputDevice::ESCKEY},
	{TABKEY, SCA_IInputDevice::TABKEY},
	{RETKEY, SCA_IInputDevice::RETKEY},
	{SPACEKEY, SCA_IInputDevice::SPACEKEY},
	{LINEFEEDKEY, SCA_IInputDevice::LINEFEEDKEY},
	{BACKSPACEKEY, SCA_IInputDevice::BACKSPACEKEY},
	{DELKEY, SCA_IInputDevice::DELKEY},
	{SEMICOLONKEY, SCA_IInputDevice::SEMICOLONKEY},
	{PERIODKEY, SCA_IInputDevice::PERIODKEY},
	{COMMAKEY, SCA_IInputDevice::COMMAKEY},
	{QUOTEKEY, SCA_IInputDevice::QUOTEKEY},
	{ACCENTGRAVEKEY, SCA_IInputDevice::ACCENTGRAVEKEY},
	{MINUSKEY, SCA_IInputDevice::MINUSKEY},
	{SLASHKEY, SCA_IInputDevice::SLASHKEY},
	{BACKSLASHKEY, SCA_IInputDevice::BACKSLASHKEY},
	{EQUALKEY, SCA_IInputDevice::EQUALKEY},
	{LEFTBRACKETKEY, SCA_IInputDevice::LEFTBRACKETKEY},
	{RIGHTBRACKETKEY, SCA_IInputDevice::RIGHTBRACKETKEY},

	{LEFTARROWKEY, SCA_IInputDevice::LEFTARROWKEY},
	{DOWNARROWKEY, SCA_IInputDevice::DOWNARROWKEY},
	{RIGHTARROWKEY, SCA_IInputDevice::RIGHTARROWKEY},
	{UPARROWKEY, SCA_IInputDevice::UPARROWKEY},

	{PAD2, SCA_IInputDevice::PAD2},
	{PAD4, SCA_IInputDevice::PAD4},
	{PAD6, SCA_IInputDevice::PAD6},
	{PAD8, SCA_IInputDevice::PAD8},

	{PAD1, SCA_IInputDevice::PAD1},
	{PAD3, SCA_IInputDevice::PAD3},
	{PAD5, SCA_IInputDevice::PAD5},
	{PAD7, SCA_IInputDevice::PAD7},
	{PAD9, SCA_IInputDevice::PAD9},

	{PADPERIOD, SCA_IInputDevice::PADPERIOD},
	{PADSLASHKEY, SCA_IInputDevice::PADSLASHKEY},
	{PADASTERKEY, SCA_IInputDevice::PADASTERKEY},

	{PAD0, SCA_IInputDevice::PAD0},
	{PADMINUS, SCA_IInputDevice::PADMINUS},
	{PADENTER, SCA_IInputDevice::PADENTER},
	{PADPLUSKEY, SCA_IInputDevice::PADPLUSKEY},

	{F1KEY, SCA_IInputDevice::F1KEY},
	{F2KEY, SCA_IInputDevice::F2KEY},
	{F3KEY, SCA_IInputDevice::F3KEY},
	{F4KEY, SCA_IInputDevice::F4KEY},
	{F5KEY, SCA_IInputDevice::F5KEY},
	{F6KEY, SCA_IInputDevice::F6KEY},
	{F7KEY, SCA_IInputDevice::F7KEY},
	{F8KEY, SCA_IInputDevice::F8KEY},
	{F9KEY, SCA_IInputDevice::F9KEY},
	{F10KEY, SCA_IInputDevice::F10KEY},
	{F11KEY, SCA_IInputDevice::F11KEY},
	{F12KEY, SCA_IInputDevice::F12KEY},
	{F13KEY, SCA_IInputDevice::F13KEY},
	{F14KEY, SCA_IInputDevice::F14KEY},
	{F15KEY, SCA_IInputDevice::F15KEY},
	{F16KEY, SCA_IInputDevice::F16KEY},
	{F17KEY, SCA_IInputDevice::F17KEY},
	{F18KEY, SCA_IInputDevice::F18KEY},
	{F19KEY, SCA_IInputDevice::F19KEY},

	{OSKEY, SCA_IInputDevice::OSKEY},

	{PAUSEKEY, SCA_IInputDevice::PAUSEKEY},
	{INSERTKEY, SCA_IInputDevice::INSERTKEY},
	{HOMEKEY, SCA_IInputDevice::HOMEKEY},
	{PAGEUPKEY, SCA_IInputDevice::PAGEUPKEY},
	{PAGEDOWNKEY, SCA_IInputDevice::PAGEDOWNKEY},
	{ENDKEY, SCA_IInputDevice::ENDKEY}
};

SCA_IInputDevice::SCA_EnumInputs BL_ConvertKeyCode(int key_code)
{
	return gReverseKeyTranslateTable[key_code];
}

static void BL_GetUvRgba(const RAS_Mesh::LayersInfo& layersInfo, std::vector<MLoopUV *>& uvLayers,
                         std::vector<MLoopCol *>& colorLayers, unsigned int loop, mt::vec2_packed uvs[RAS_Texture::MaxUnits],
                         unsigned int rgba[RAS_Texture::MaxUnits])
{
	// No need to initialize layers to zero as all the converted layer are all the layers needed.

	for (const RAS_Mesh::Layer& layer : layersInfo.colorLayers) {
		const unsigned short index = layer.index;
		const MLoopCol& col = colorLayers[index][loop];

		union Convert
		{
			// Color isn't swapped in MLoopCol.
			MLoopCol col;
			unsigned int val;
		};
		Convert con;
		con.col = col;

		rgba[index] = con.val;
	}

	for (const RAS_Mesh::Layer& layer : layersInfo.uvLayers) {
		const unsigned short index = layer.index;
		const MLoopUV& uv = uvLayers[index][loop];
		uvs[index] = mt::vec2_packed(uv.uv);
	}

	/* All vertices have at least one uv and color layer accessible to the user
	 * even if it they are not used in any shaders. Initialize this layer to zero
	 * when no uv or color layer exist.
	 */
	if (layersInfo.uvLayers.empty()) {
		uvs[0] = mt::zero2;
	}
	if (layersInfo.colorLayers.empty()) {
		rgba[0] = 0xFFFFFFFF;
	}
}

static RAS_MaterialBucket *BL_ConvertMaterial(Material *ma, KX_Scene *scene, BL_SceneConverter& converter)
{
	KX_BlenderMaterial *mat = converter.FindMaterial(ma);

	if (!mat) {
		std::string name = ma->id.name;
		// Always ensure that the name of a material start with "MA" prefix due to video texture name check.
		if (name.empty()) {
			name = "MA";
		}

		mat = new KX_BlenderMaterial(ma, name, scene);

		// this is needed to free up memory afterwards.
		converter.RegisterMaterial(mat, ma);
	}

	// see if a bucket was reused or a new one was created
	// this way only one KX_BlenderMaterial object has to exist per bucket
	bool bucketCreated;
	RAS_MaterialBucket *bucket = scene->GetBucketManager()->FindBucket(mat, bucketCreated);

	return bucket;
}

/* blenderobj can be nullptr, make sure its checked for */
KX_Mesh *BL_ConvertMesh(Mesh *me, Object *blenderobj, KX_Scene *scene, BL_SceneConverter& converter)
{
	KX_Mesh *meshobj;

	const bool debugNav = blenderobj && (blenderobj->gameflag & OB_NAVMESH);
	if (debugNav) {
	}

	// Without checking names, we get some reuse we don't want that can cause
	// problems with material LoDs.
	if (blenderobj && ((meshobj = converter.FindGameMesh(me)) != nullptr)) {
		const std::string bge_name = meshobj->GetName();
		const std::string blender_name = ((ID *)blenderobj->data)->name + 2;
		if (bge_name == blender_name) {
			return meshobj;
		}
	}

	if (debugNav) {
	}
	// Get DerivedMesh data.
	DerivedMesh *dm = CDDM_from_mesh(me);
	if (debugNav) {
	}

	/* Extract available layers.
	 * Get the active color and uv layer. */
	const short activeUv = CustomData_get_active_layer(&dm->loopData, CD_MLOOPUV);
	const short activeColor = CustomData_get_active_layer(&dm->loopData, CD_MLOOPCOL);
	const unsigned short uvCount = CustomData_number_of_layers(&dm->loopData, CD_MLOOPUV);
	const unsigned short colorCount = CustomData_number_of_layers(&dm->loopData, CD_MLOOPCOL);

	RAS_Mesh::LayersInfo layersInfo;
	layersInfo.activeUv = (activeUv == -1) ? 0 : activeUv;
	layersInfo.activeColor = (activeColor == -1) ? 0 : activeColor;

	// Extract UV loops.
	for (unsigned short i = 0; i < uvCount; ++i) {
		const std::string name = CustomData_get_layer_name(&dm->loopData, CD_MLOOPUV, i);
		layersInfo.uvLayers.push_back({i, name});
	}
	// Extract color loops.
	for (unsigned short i = 0; i < colorCount; ++i) {
		const std::string name = CustomData_get_layer_name(&dm->loopData, CD_MLOOPCOL, i);
		layersInfo.colorLayers.push_back({i, name});
	}

	// Initialize vertex format with used uv and color layers.
	RAS_DisplayArray::Format vertformat;
	vertformat.uvSize = max_ii(1, uvCount);
	vertformat.colorSize = max_ii(1, colorCount);

	const bool bMayHaveBoneData = (blenderobj && me->dvert && blenderobj->defbase.first &&
	                                BL_ModifierDeformer::HasArmatureDeformer(blenderobj));

	meshobj = new KX_Mesh(scene, me, layersInfo);

	const unsigned short totmat = max_ii(me->totcol, 1);
	std::vector<BL_MeshMaterial> mats(totmat);
	// Convert all the materials contained in the mesh.
	for (unsigned short i = 0; i < totmat; ++i) {
		Material *ma = nullptr;
		if (blenderobj) {
			ma = give_current_material(blenderobj, i + 1);
		}
		else {
			ma = me->mat ? me->mat[i] : nullptr;
		}
		// Check for blender material
		if (!ma) {
			ma = &defmaterial;
		}

		/* Only reserve the bone index/weight attributes (32 extra bytes/vertex) for materials
		 * that actually opt into GPU skinning. A CPU-skinned character (the common case) never
		 * reads these attributes, so paying for the wider vertex format there is pure waste that
		 * measurably slows down the whole scene once any character in it uses GPU skinning. */
		RAS_DisplayArray::Format matVertformat = vertformat;
		matVertformat.hasBoneData = bMayHaveBoneData && (ma->shade_flag & MA_SKINNING) != 0;

		RAS_MaterialBucket *bucket = BL_ConvertMaterial(ma, scene, converter);
		RAS_MeshMaterial *meshmat = meshobj->AddMaterial(bucket, i, matVertformat);
		RAS_IMaterial *mat = meshmat->GetBucket()->GetMaterial();

		mats[i] = {meshmat->GetDisplayArray(), bucket, mat->IsVisible(), mat->IsTwoSided(), mat->IsCollider(), mat->IsWire()};
	}

	BL_ConvertDerivedMeshToArray(dm, me, blenderobj, mats, layersInfo);

	meshobj->EndConversion(scene->GetBoundingBoxManager());

	dm->release(dm);

	// Needed for python scripting.
	scene->GetLogicManager()->RegisterMeshName(meshobj->GetName(), meshobj);
	converter.RegisterGameMesh(meshobj, me);

	return meshobj;
}

/** Pick the top 4 vertex-group weights for a vertex (GPU skinning budget), renormalized to sum to 1,
 * and expressed as (def_nr, weight) pairs padded with (0, 0) for unused slots.
 */
static void BL_ComputeVertexBoneData(const MDeformVert& dv, unsigned short defbaseTot,
                                      mt::vec4_packed& boneIndices, mt::vec4_packed& boneWeights)
{
	float indices[4] = {0.0f, 0.0f, 0.0f, 0.0f};
	float weights[4] = {0.0f, 0.0f, 0.0f, 0.0f};
	unsigned short numPicked = 0;

	for (unsigned int i = 0; i < dv.totweight; ++i) {
		const MDeformWeight& dw = dv.dw[i];
		if (dw.def_nr >= defbaseTot || dw.weight <= 0.0f) {
			continue;
		}

		// Insert keeping the 4 highest weights, smallest first.
		if (numPicked < 4) {
			indices[numPicked] = (float)dw.def_nr;
			weights[numPicked] = dw.weight;
			++numPicked;
		}
		else if (dw.weight > weights[0]) {
			indices[0] = (float)dw.def_nr;
			weights[0] = dw.weight;
		}
		else {
			continue;
		}

		// Bubble the just-inserted entry into sorted (ascending) position.
		for (int j = numPicked - 1; j > 0 && weights[j] < weights[j - 1]; --j) {
			std::swap(weights[j], weights[j - 1]);
			std::swap(indices[j], indices[j - 1]);
		}
	}

	float totalWeight = 0.0f;
	for (unsigned short i = 0; i < 4; ++i) {
		totalWeight += weights[i];
	}
	if (totalWeight > 0.0f) {
		for (unsigned short i = 0; i < 4; ++i) {
			weights[i] /= totalWeight;
		}
	}

	boneIndices = mt::vec4_packed(indices);
	boneWeights = mt::vec4_packed(weights);
}

void BL_ConvertDerivedMeshToArray(DerivedMesh *dm, Mesh *me, Object *blenderobj, const std::vector<BL_MeshMaterial>& mats,
                                  const RAS_Mesh::LayersInfo& layersInfo)
{
	const bool bMayHaveBoneData = (blenderobj && me->dvert && blenderobj->defbase.first &&
	                                BL_ModifierDeformer::HasArmatureDeformer(blenderobj));
	const unsigned short defbaseTot = bMayHaveBoneData ? BLI_listbase_count(&blenderobj->defbase) : 0;
	const MVert *mverts = dm->getVertArray(dm);
	const int totverts = dm->getNumVerts(dm);
	const MPoly *mpolys = (MPoly *)dm->getPolyArray(dm);
	const MLoopTri *mlooptris = (MLoopTri *)dm->getLoopTriArray(dm);
	const MLoop *mloops = (MLoop *)dm->getLoopArray(dm);
	const MEdge *medges = (MEdge *)dm->getEdgeArray(dm);
	const unsigned int numpolys = dm->getNumPolys(dm);

	if (CustomData_get_layer_index(&dm->loopData, CD_NORMAL) == -1) {
		dm->calcLoopNormals(dm, (me->flag & ME_AUTOSMOOTH), me->smoothresh);
	}
	const float(*normals)[3] = (float(*)[3])dm->getLoopDataArray(dm, CD_NORMAL);

	float(*tangent)[4] = nullptr;
	if (!layersInfo.uvLayers.empty()) {
		if (CustomData_get_layer_index(&dm->loopData, CD_TANGENT) == -1) {
			DM_calc_loop_tangents(dm, true, nullptr, 0);
		}
		tangent = (float(*)[4])dm->getLoopDataArray(dm, CD_TANGENT);
	}

	// List of MLoopUV per uv layer index.
	std::vector<MLoopUV *> uvLayers(layersInfo.uvLayers.size());
	// List of MLoopCol per color layer index.
	std::vector<MLoopCol *> colorLayers(layersInfo.colorLayers.size());

	for (const RAS_Mesh::Layer& layer : layersInfo.uvLayers) {
		const unsigned short index = layer.index;
		uvLayers[index] = (MLoopUV *)CustomData_get_layer_n(&dm->loopData, CD_MLOOPUV, index);
	}
	for (const RAS_Mesh::Layer& layer : layersInfo.colorLayers) {
		const unsigned short index = layer.index;
		colorLayers[index] = (MLoopCol *)CustomData_get_layer_n(&dm->loopData, CD_MLOOPCOL, index);
	}

	BL_SharedVertexMap sharedMap(totverts);

	// Tracked vertices during a mpoly conversion, should never be used by the next mpoly.
	std::vector<unsigned int> vertices(totverts, -1);

	for (unsigned int i = 0; i < numpolys; ++i) {
		const MPoly& mpoly = mpolys[i];

		const BL_MeshMaterial& mat = mats[mpoly.mat_nr];
		RAS_DisplayArray *array = mat.array;

		// Mark face as flat, so vertices are split.
		const bool flat = (mpoly.flag & ME_SMOOTH) == 0;

		const unsigned int lpstart = mpoly.loopstart;
		const unsigned int totlp = mpoly.totloop;
		for (unsigned int j = lpstart; j < lpstart + totlp; ++j) {
			const MLoop& mloop = mloops[j];
			const unsigned int vertid = mloop.v;
			const MVert& mvert = mverts[vertid];

			static const float dummyTangent[4] = {0.0f, 0.0f, 0.0f, 0.0f};
			const mt::vec4_packed tan(tangent ? tangent[j] : dummyTangent);
			const mt::vec3_packed nor(normals[j]);
			const mt::vec3_packed pos(mvert.co);
			mt::vec2_packed uvs[RAS_Texture::MaxUnits];
			unsigned int rgba[RAS_Texture::MaxUnits];

			BL_GetUvRgba(layersInfo, uvLayers, colorLayers, j, uvs, rgba);

			BL_SharedVertexList& sharedList = sharedMap[vertid];
			BL_SharedVertexList::iterator it = std::find_if(sharedList.begin(), sharedList.end(),
					BL_SharedVertexPredicate(array, nor, tan, uvs, rgba));

			unsigned int offset;
			if (it != sharedList.end()) {
				offset = it->offset;
			}
			else {
				mt::vec4_packed boneIndices(mt::zero4);
				mt::vec4_packed boneWeights(mt::zero4);
				if (bMayHaveBoneData && array->GetFormat().hasBoneData) {
					BL_ComputeVertexBoneData(me->dvert[vertid], defbaseTot, boneIndices, boneWeights);
				}
				offset = array->AddVertex(pos, nor, tan, uvs, rgba, vertid, flat, boneIndices, boneWeights);
				sharedList.push_back({array, offset});
			}

			// Add tracked vertices by the mpoly.
			vertices[vertid] = offset;
		}

		const unsigned int ltstart = poly_to_tri_count(i, mpoly.loopstart);
		const unsigned int lttot = ME_POLY_TRI_TOT(&mpoly);

		if (mat.visible) {
			if (mat.wire) {
				// Convert to edges if material is rendering wire.
				for (unsigned int j = lpstart; j < (lpstart + totlp); ++j) {
					const MLoop& mloop = mloops[j];
					const MEdge& edge = medges[mloop.e];
					array->AddPrimitiveIndex(vertices[edge.v1]);
					array->AddPrimitiveIndex(vertices[edge.v2]);
				}
			}
			else {
				for (unsigned int j = ltstart; j < (ltstart + lttot); ++j) {
					const MLoopTri& mlooptri = mlooptris[j];
					for (unsigned short k = 0; k < 3; ++k) {
						array->AddPrimitiveIndex(vertices[mloops[mlooptri.tri[k]].v]);
					}
				}
			}
		}

		for (unsigned int j = ltstart; j < (ltstart + lttot); ++j) {
			const MLoopTri& mlooptri = mlooptris[j];
			for (unsigned short k = 0; k < 3; ++k) {
				// Add triangle index into display array.
				array->AddTriangleIndex(vertices[mloops[mlooptri.tri[k]].v]);
			}
		}
	}
}

RAS_Deformer *BL_ConvertDeformer(KX_GameObject *object, KX_Mesh *meshobj)
{
	Mesh *mesh = meshobj->GetMesh();

	if (!mesh) {
		return nullptr;
	}

	KX_Scene *scene = object->GetScene();
	Scene *blenderScene = scene->GetBlenderScene();
	// We must create a new deformer but which one?
	KX_GameObject *parentobj = object->GetParent();
	/* Object that owns the mesh. If this is not the current blender object, look at one of the object registered
	 * along the blender mesh. */
	Object *meshblendobj;
	Object *blenderobj = object->GetBlenderObject();
	if (blenderobj->data != mesh) {
		meshblendobj = static_cast<Object *>(scene->GetLogicManager()->FindBlendObjByGameMeshName(meshobj->GetName()));
	}
	else {
		meshblendobj = blenderobj;
	}

	const bool isParentArmature = parentobj && parentobj->GetGameObjectType() == SCA_IObject::OBJ_ARMATURE;
	const bool bHasModifier = BL_ModifierDeformer::HasCompatibleDeformer(blenderobj);
	const bool bHasShapeKey = mesh->key && mesh->key->type == KEY_RELATIVE;
	const bool bHasDvert = mesh->dvert && blenderobj->defbase.first;
	const bool bHasArmature = BL_ModifierDeformer::HasArmatureDeformer(blenderobj) &&
	                          isParentArmature && meshblendobj && bHasDvert;
#ifdef WITH_BULLET
	const bool bHasSoftBody = (!parentobj && (blenderobj->gameflag & OB_SOFT_BODY));
#endif

	if (!meshblendobj) {
		if (bHasModifier || bHasShapeKey || bHasDvert || bHasArmature) {
			CM_FunctionWarning("new mesh is not used in an object from the current scene, you will get incorrect behavior.");
			return nullptr;
		}
	}

	RAS_Deformer *deformer = nullptr;
	if (bHasModifier) {
		if (isParentArmature) {
			BL_ModifierDeformer *modifierDeformer = new BL_ModifierDeformer(object, blenderScene, meshblendobj, blenderobj,
			                                                                meshobj, static_cast<BL_ArmatureObject *>(parentobj));
			modifierDeformer->LoadShapeDrivers(parentobj);
			deformer = modifierDeformer;
		}
		else {
			deformer = new BL_ModifierDeformer(object, blenderScene, meshblendobj, blenderobj, meshobj, nullptr);
		}
	}
	else if (bHasShapeKey) {
		if (isParentArmature) {
			BL_ShapeDeformer *shapeDeformer = new BL_ShapeDeformer(object, meshblendobj, blenderobj, meshobj,
			                                                       static_cast<BL_ArmatureObject *>(parentobj));
			shapeDeformer->LoadShapeDrivers(parentobj);
			deformer = shapeDeformer;
		}
		else {
			deformer = new BL_ShapeDeformer(object, meshblendobj, blenderobj, meshobj, nullptr);
		}
	}
	else if (bHasArmature) {
		deformer = new BL_SkinDeformer(object, meshblendobj, blenderobj, meshobj,
		                                 static_cast<BL_ArmatureObject *>(parentobj));
	}
	else if (bHasDvert) {
		deformer = new BL_MeshDeformer(object, meshblendobj, meshobj);
	}
#ifdef WITH_BULLET
	else if (bHasSoftBody) {
		deformer = new KX_SoftBodyDeformer(meshobj, object);
	}
#endif

	if (deformer) {
		deformer->InitializeDisplayArrays();
	}

	return deformer;
}

BL_ActionData *BL_ConvertAction(bAction *action, KX_Scene *scene, BL_SceneConverter& converter)
{
	BL_ActionData *data = new BL_ActionData(action);
	converter.RegisterActionData(data);
	scene->GetLogicManager()->RegisterActionName(action->id.name + 2, data);

	return data;
}

void BL_ConvertActions(KX_Scene *scene, Main *maggie, BL_SceneConverter& converter)
{
	// Convert all actions and register.
	for (bAction *act = (bAction *)maggie->action.first; act; act = (bAction *)act->id.next) {
		BL_ConvertAction(act, scene, converter);
	}
}

static void BL_CreateGraphicObjectNew(KX_GameObject *gameobj, KX_Scene *kxscene, bool isActive, e_PhysicsEngine physics_engine)
{
	switch (physics_engine) {
#ifdef WITH_BULLET
		case UseBullet:
		{
			CcdPhysicsEnvironment *env = (CcdPhysicsEnvironment *)kxscene->GetPhysicsEnvironment();
			BLI_assert(env);
			PHY_IMotionState *motionstate = new KX_MotionState(gameobj->GetNode());
			CcdGraphicController *ctrl = new CcdGraphicController(env, motionstate);
			gameobj->SetGraphicController(ctrl);
			ctrl->SetNewClientInfo(&gameobj->GetClientInfo());
			if (isActive) {
                // add first, this will create the proxy handle, only if the object is visible or occluder
                if (gameobj->GetVisible() || gameobj->GetOccluder()) {
					env->AddCcdGraphicController(ctrl);
				}
			}
			break;
		}
#endif
		default:
		{
			break;
		}
	}
}

static void BL_CreatePhysicsObjectNew(KX_GameObject *gameobj, Object *blenderobject, KX_Mesh *meshobj,
                                      KX_Scene *kxscene, int activeLayerBitInfo, BL_SceneConverter& converter, bool processCompoundChildren)

{
	// Object has physics representation?
	if (!(blenderobject->gameflag & OB_COLLISION)) {
		return;
	}

	Object *parent = blenderobject->parent;

	bool isCompoundChild = false;
	bool hasCompoundChildren = false;

	// Pretend for compound parent or child if the object has compound option and use a physics type with solid shape.
	if ((blenderobject->gameflag & (OB_CHILD)) && (blenderobject->gameflag & (OB_DYNAMIC | OB_COLLISION | OB_RIGID_BODY)) &&
	    !(blenderobject->gameflag & OB_SOFT_BODY)) {
		hasCompoundChildren = true;
		while (parent) {
			if ((parent->gameflag & OB_CHILD) && (parent->gameflag & (OB_COLLISION | OB_DYNAMIC | OB_RIGID_BODY)) &&
			    !(parent->gameflag & OB_SOFT_BODY)) {
				// Found a parent in the tree with compound shape.
				isCompoundChild = true;
				/* The object is not a parent compound shape if it has a parent
				 * object with compound shape. */
				hasCompoundChildren = false;
				break;
			}
			parent = parent->parent;
		}
	}

	if (processCompoundChildren != isCompoundChild) {
		return;
	}

	PHY_IMotionState *motionstate = new KX_MotionState(gameobj->GetNode());

	PHY_IPhysicsEnvironment *phyenv = kxscene->GetPhysicsEnvironment();
	phyenv->ConvertObject(converter, gameobj, meshobj, kxscene, motionstate, activeLayerBitInfo,
	                      isCompoundChild, hasCompoundChildren);

	bool isActor = (blenderobject->gameflag & OB_ACTOR) != 0;
	bool isSensor = (blenderobject->gameflag & OB_SENSOR) != 0;
	gameobj->GetClientInfo().m_type =
		(isSensor) ? ((isActor) ? KX_ClientObjectInfo::OBACTORSENSOR : KX_ClientObjectInfo::OBSENSOR) :
		(isActor) ? KX_ClientObjectInfo::ACTOR : KX_ClientObjectInfo::STATIC;
}

static KX_LodManager *BL_LodManagerFromBlenderObject(Object *ob, KX_Scene *scene, BL_SceneConverter& converter)
{
	if (BLI_listbase_count(&ob->lodlevels) <= 1) {
		return nullptr;
	}

	KX_LodManager *lodManager = new KX_LodManager(ob, scene, converter);
	// The lod manager is useless ?
	if (lodManager->GetLevelCount() <= 1) {
		lodManager->Release();
		return nullptr;
	}

	return lodManager;
}

static KX_AnimationEventManager *BL_AnimationEventManagerFromBlenderObject(Object *ob)
{
	if (BLI_listbase_count(&ob->animevents) < 1) {
		return nullptr;
	}

	KX_AnimationEventManager *animationEventManager = new KX_AnimationEventManager(ob);

	return animationEventManager;
}

/** Convert the object activity culling settings from blender to a KX_GameObject::ActivityCullingInfo.
 * \param ob The object to convert the activity culling settings from.
 */
static KX_GameObject::ActivityCullingInfo activityCullingInfoFromBlenderObject(Object *ob)
{
	KX_GameObject::ActivityCullingInfo cullingInfo;
	const ObjectActivityCulling& blenderInfo = ob->activityCulling;
	// Convert the flags.
	if (blenderInfo.flags & OB_ACTIVITY_PHYSICS) {
		// Enable physics culling.
		cullingInfo.m_flags = (KX_GameObject::ActivityCullingInfo::Flag)(
			cullingInfo.m_flags | KX_GameObject::ActivityCullingInfo::ACTIVITY_PHYSICS);
	}
	if (blenderInfo.flags & OB_ACTIVITY_PHYSICS_SLEEPVELOCITY) {
		// Enable physics only stop culling.
		cullingInfo.m_flags = (KX_GameObject::ActivityCullingInfo::Flag)(
			cullingInfo.m_flags | KX_GameObject::ActivityCullingInfo::ACTIVITY_PHYSICS_SLEEPVELOCITY);
	}
	if (blenderInfo.flags & OB_ACTIVITY_LOGIC) {
		// Enable logic culling.
		cullingInfo.m_flags = (KX_GameObject::ActivityCullingInfo::Flag)(
			cullingInfo.m_flags | KX_GameObject::ActivityCullingInfo::ACTIVITY_LOGIC);
	}
	if (blenderInfo.flags & OB_ACTIVITY_LOGIC_COMPONENTS) {
		// Enable logic components culling.
		cullingInfo.m_flags = (KX_GameObject::ActivityCullingInfo::Flag)(
			cullingInfo.m_flags | KX_GameObject::ActivityCullingInfo::ACTIVITY_LOGIC_COMPONENTS);
	}

	// Set culling radius.
	cullingInfo.m_physicsRadius = blenderInfo.physicsRadius * blenderInfo.physicsRadius;
	cullingInfo.m_logicRadius = blenderInfo.logicRadius * blenderInfo.logicRadius;

	return cullingInfo;
}

static KX_LightObject *BL_GameLightFromBlenderLamp(Lamp *la, unsigned int layerflag, KX_Scene *kxscene, RAS_Rasterizer *rasterizer)
{
	RAS_ILightObject *lightobj = rasterizer->CreateLight();

	lightobj->m_att1 = la->att1;
	lightobj->m_att2 = (la->mode & LA_QUAD) ? la->att2 : 0.0f;
	lightobj->m_coeff_const = la->coeff_const;
	lightobj->m_coeff_lin = la->coeff_lin;
	lightobj->m_coeff_quad = la->coeff_quad;
	lightobj->m_color = mt::vec3(la->r, la->g, la->b);
	lightobj->m_distance = la->dist;
	lightobj->m_energy = la->energy;
	lightobj->m_shadowclipstart = la->clipsta;
	lightobj->m_shadowclipend = la->clipend;
	lightobj->m_shadowbias = la->bias;
	lightobj->m_shadowbleedbias = la->bleedbias;
	lightobj->m_shadowmaptype = la->shadowmap_type;
	lightobj->m_shadowfrustumsize = la->shadow_frustum_size;
	lightobj->m_shadowcascadecount = la->shadow_cascade_count;
	lightobj->m_cascadeproportionnear = la->shadow_cascade_proportion_near;
	lightobj->m_cascadeproportionmiddle = la->shadow_cascade_proportion_middle;
	lightobj->m_shadowcolor = mt::vec3(la->shdwr, la->shdwg, la->shdwb);
	lightobj->m_layer = layerflag;
	lightobj->m_spotblend = la->spotblend;
	lightobj->m_spotsize = la->spotsize;
	lightobj->m_staticShadow = la->mode & LA_STATIC_SHADOW;
	lightobj->m_useCullDistance = (la->mode & LA_CULL_DISTANCE) != 0;
	lightobj->m_cullDistance = la->cull_distance;
	lightobj->m_glowScale = la->glow_scale;
	// Set to true to make at least one shadow render in static mode.
	lightobj->m_requestShadowUpdate = true;

	lightobj->m_nodiffuse = (la->mode & LA_NO_DIFF) != 0;
	lightobj->m_nospecular = (la->mode & LA_NO_SPEC) != 0;

	switch (la->type) {
		case LA_SUN:
		{
			lightobj->m_type = RAS_ILightObject::LIGHT_SUN;
			break;
		}
		case LA_SPOT:
		{
			lightobj->m_type = RAS_ILightObject::LIGHT_SPOT;
			break;
		}
		case LA_HEMI:
		{
			lightobj->m_type = RAS_ILightObject::LIGHT_HEMI;
			break;
		}
		default:
		{
			lightobj->m_type = RAS_ILightObject::LIGHT_NORMAL;
		}
	}

	KX_LightObject *gamelight = new KX_LightObject(kxscene, KX_Scene::m_callbacks, rasterizer, lightobj);

	gamelight->SetShowShadowFrustum((la->mode & LA_SHOW_SHADOW_BOX) && (la->mode & LA_SHAD_RAY));

	return gamelight;
}

static KX_Camera *BL_GameCameraFromBlenderCamera(Object *ob, KX_Scene *kxscene, RAS_ICanvas *canvas, float camZoom)
{
	Camera *ca = static_cast<Camera *>(ob->data);
	RAS_CameraData camdata(ca->lens, ca->ortho_scale, ca->sensor_x, ca->sensor_y, ca->sensor_fit, ca->shiftx, ca->shifty, ca->clipsta, ca->clipend, ca->type == CAM_PERSP, ca->YF_dofdist, camZoom);
	KX_Camera *gamecamera;

	gamecamera = new KX_Camera(kxscene, KX_Scene::m_callbacks, camdata);
	gamecamera->SetName(ca->id.name + 2);

	if (ca->gameflag & GAME_CAM_VIEWPORT) {
		const GameCameraViewportSettings& settings = ca->gameviewport;
		if (settings.leftratio > settings.rightratio || settings.bottomratio > settings.topratio) {
			CM_Warning("\"" << gamecamera->GetName() << "\" uses invalid custom viewport ratios, disabling custom viewport.");
		}
		else {
			gamecamera->EnableViewport(true);
			const int maxx = canvas->GetMaxX();
			const int maxy = canvas->GetMaxY();
			gamecamera->SetViewport(maxx * settings.leftratio, maxy * settings.bottomratio,
			                        maxx * settings.rightratio, maxy * settings.topratio);
		}
	}

	gamecamera->SetShowCameraFrustum(ca->gameflag & GAME_CAM_SHOW_FRUSTUM);
	gamecamera->SetLodDistanceFactor(ca->lodfactor);
	gamecamera->SetCSMCacheMaxStaleFrames(ca->csmCacheMaxStaleFrames);

	gamecamera->SetActivityCulling(ca->gameflag & GAME_CAM_OBJECT_ACTIVITY_CULLING);

	if (ca->gameflag & GAME_CAM_OVERRIDE_CULLING) {
		if (kxscene->GetOverrideCullingCamera()) {
			CM_Warning("\"" << gamecamera->GetName() << "\" sets for culling override whereas \""
			                << kxscene->GetOverrideCullingCamera()->GetName() << "\" is already used for culling override.");
		}
		else {
			kxscene->SetOverrideCullingCamera(gamecamera);
		}
	}

	return gamecamera;
}

static KX_Speaker *BL_SpeakerFromBlenderSpeaker(Object *ob, KX_Scene *kxscene, int ob_lay, unsigned int activelayer)
{
  Speaker *speaker = static_cast<Speaker *>(ob->data);

  if (speaker->sound) {
#ifdef WITH_AUDASPACE
    AUD_Sound *snd_sound = speaker->sound->playback_handle;
#endif  // WITH_AUDASPACE
    bool is3d = (speaker->flag & SPK_USE_3DSOUND);

#ifdef WITH_AUDASPACE
	// if sound shall be 3D but isn't mono, we have to make it mono!
    if (is3d) {
      snd_sound = AUD_Sound_rechannel(snd_sound, AUD_CHANNELS_MONO);
    }
#endif  // WITH_AUDASPACE

    KX_SpeakerSoundSettings settings;
    settings.start_at = speaker->start_at;
    settings.destroy_after = (speaker->flag & SPK_DESTROY_AFTER);
    settings.cache_sound = (speaker->flag & SPK_SOUND_CACHE);

    settings.cone_inner_angle = speaker->cone_angle_inner;
    settings.cone_outer_angle = speaker->cone_angle_outer;
    settings.cone_outer_gain = speaker->cone_volume_outer;
    settings.max_distance = speaker->distance_max;
    settings.max_gain = speaker->volume_max;
    settings.min_gain = speaker->volume_min;
    settings.reference_distance = speaker->distance_reference;
    settings.rolloff_factor = speaker->attenuation;

	/* Sound Effect Parameters */
	settings.active_effect_type = 0;  // null
	settings.active_filter_type = 0;  // null

	/* Sound Reverb Parameters, Default values ​​based on OpenAL default values */
	settings.reverb_density = 1.0f;
	settings.reverb_diffusion = 1.0f;
	settings.reverb_gain = 0.32f;
	settings.reverb_gain_hf = 0.89f;
	settings.reverb_decay_time = 1.49f;
	settings.reverb_decay_hf_ratio = 0.83f;
	settings.reverb_reflections_gain = 0.05f;
	settings.reverb_reflections_delay = 0.007f;
	settings.reverb_late_reverb_delay = 0.011f;
	settings.reverb_late_reverb_gain = 1.26f;
	settings.reverb_air_absorption_gain_hf = 0.994f;
	settings.reverb_room_rolloff_factor = 0.0f;
	settings.reverb_decay_limit_hf = 1;

	settings.filter_gain = 1.0f;
	settings.filter_gainlf = 1.0f;
	settings.filter_gainhf = 1.0f;

    KX_Speaker::KX_SPEAKER_TYPE soundSpeakerType = KX_Speaker::KX_SPEAKER_NODEF;

    switch (speaker->type) {
      case SPEAKER_PLAY_END_SOUND: {
        soundSpeakerType = KX_Speaker::KX_SPEAKER_PLAYEND;
        break;
      }
      case SPEAKER_LOOP_END_SOUND: {
        soundSpeakerType = KX_Speaker::KX_SPEAKER_LOOPEND;
        break;
      }
      case SPEAKER_LOOP_BIDIRECTIONAL_SOUND: {
        soundSpeakerType = KX_Speaker::KX_SPEAKER_LOOPBIDIRECTIONAL;
        break;
      }
      default:
        /* This is an error!!! */
        soundSpeakerType = KX_Speaker::KX_SPEAKER_NODEF;
    }

    KX_Speaker *KX_speaker = new KX_Speaker(kxscene,
                                            KX_Scene::m_callbacks,
#ifdef WITH_AUDASPACE
                                            snd_sound,
#endif  // WITH_AUDASPACE
                                            speaker->volume,
                                            speaker->pitch,
                                            (speaker->flag & SPK_START_INIT),
                                            is3d,
                                            settings,
                                            soundSpeakerType);

#ifdef WITH_AUDASPACE
	// if we made it mono, we have to free it
    if (snd_sound != speaker->sound->playback_handle) {
		AUD_Sound_free(snd_sound);
	}
#endif  // WITH_AUDASPACE
	return KX_speaker;
  }
  return nullptr;
}

static KX_GameObject *BL_GameObjectFromBlenderObject(Object *ob, KX_Scene *kxscene, RAS_Rasterizer *rendertools,
                                                     RAS_ICanvas *canvas, BL_SceneConverter &converter, float camZoom)
{
	KX_GameObject *gameobj = nullptr;
	Scene *blenderscene = kxscene->GetBlenderScene();

	switch (ob->type) {
		case OB_LAMP:
		{
			KX_LightObject *gamelight = BL_GameLightFromBlenderLamp(static_cast<Lamp *>(ob->data), ob->lay, kxscene, rendertools);
			gameobj = gamelight;
			gamelight->AddRef();
			kxscene->GetLightList()->Add(gamelight);

			// world sun
			if (ob == blenderscene->world_sun) {
				kxscene->SetWorldSun(gamelight);
			}

			break;
		}

		case OB_CAMERA:
		{
			KX_Camera *gamecamera = BL_GameCameraFromBlenderCamera(ob, kxscene, canvas, camZoom);
			gameobj = gamecamera;

			kxscene->GetCameraList()->Add(CM_AddRef(gamecamera));

			break;
		}

		case OB_SPEAKER: 
		{
			KX_Speaker *gamespeaker = BL_SpeakerFromBlenderSpeaker(ob, kxscene, ob->lay, kxscene->GetBlenderScene()->lay);
			gameobj = gamespeaker;

			if (gamespeaker)
				kxscene->GetSpeakerList()->Add(CM_AddRef(gamespeaker));
			break;
		}

		case OB_MESH:
		{
			Mesh *mesh = static_cast<Mesh *>(ob->data);
			if (ob->gameflag & OB_NAVMESH) {
			}
			KX_Mesh *meshobj = BL_ConvertMesh(mesh, ob, kxscene, converter);
			if (ob->gameflag & OB_NAVMESH) {
			}

			if (ob->gameflag & OB_NAVMESH) {
				gameobj = new KX_NavMeshObject(kxscene, KX_Scene::m_callbacks);
				gameobj->AddMesh(meshobj);
				break;
			}


			KX_GameObject *deformableGameObj = new KX_GameObject(kxscene, KX_Scene::m_callbacks);
			gameobj = deformableGameObj;

			// set transformation
			gameobj->AddMesh(meshobj);

			// gather levels of detail
			KX_LodManager *lodManager = BL_LodManagerFromBlenderObject(ob, kxscene, converter);
			gameobj->SetLodManager(lodManager);
			if (lodManager) {
				lodManager->Release();
			}

			gameobj->SetOccluder((ob->gameflag & OB_OCCLUDER) != 0, false);
			gameobj->SetActivityCullingInfo(activityCullingInfoFromBlenderObject(ob));
			break;
		}

		case OB_ARMATURE:
		{
			gameobj = new BL_ArmatureObject(kxscene, KX_Scene::m_callbacks, ob, kxscene->GetBlenderScene());

			break;
		}

		case OB_EMPTY:
		{
			gameobj = new KX_EmptyObject(kxscene, KX_Scene::m_callbacks);

			break;
		}

		case OB_FONT:
		{
			bool do_color_management = BKE_scene_check_color_management_enabled(blenderscene);
			// Font objects have no bounding box.
			KX_FontObject *fontobj = new KX_FontObject(kxscene, KX_Scene::m_callbacks, rendertools,
			                                           kxscene->GetBoundingBoxManager(), ob, do_color_management);
			gameobj = fontobj;

			kxscene->GetFontList()->Add(CM_AddRef(fontobj));
			break;
		}

#ifdef THREADED_DAG_WORKAROUND
		case OB_CURVE:
		{
			if (ob->curve_cache == nullptr) {
				BKE_displist_make_curveTypes(blenderscene, ob, false);
			}
			/* We can convert curves as empty for experimental purposes in 2.7
			 * and to prepare transition to 2.8.
			 * Note: if we use eevee render in 2.8, to finalize stuff about curves,
			 * see : https://github.com/youle31/EEVEEinUPBGE/commit/ff11e0fdea4dfc121a7eaa7b7d48183eaf5fd9f6
			 * for comments about culling.
			 */
			gameobj = new KX_EmptyObject(kxscene, KX_Scene::m_callbacks);
			break;
		}
#endif
	}
	if (gameobj) {
		gameobj->SetLayer(ob->lay);
		gameobj->SetPassIndex(ob->index);
		BL_ConvertObjectInfo *info = converter.GetObjectInfo(ob);
		gameobj->SetConvertObjectInfo(info);
		gameobj->SetObjectColor(mt::vec4(ob->col));
		// Set the visibility state based on the objects render option in the outliner.
		if (ob->restrictflag & OB_RESTRICT_RENDER) {
			gameobj->SetVisible(false, false);
		}

		// Get animation events
		KX_AnimationEventManager *AnimationEventManager = BL_AnimationEventManagerFromBlenderObject(ob);
		if (AnimationEventManager) {
			gameobj->SetAnimationEventManager(AnimationEventManager);
		}

		// Fase I.2: per-object GPU particle emitter, opt-in via Object.use_gpu_particles.
		if (ob->gameflag2 & OB_GPU_PARTICLES) {
			gameobj->SetupGPUParticles(ob->gpu_particles);
			kxscene->AddGpuParticleObject(gameobj);
		}

		// Fase Q: second "Mix GPU Particle System" emitter, opt-in via use_gpu_particles_mix,
		// drawn together with the one above (KX_RenderPipeline draws both for the same object).
		if (ob->gameflag2 & OB_GPU_PARTICLES_MIX) {
			gameobj->SetupGPUParticlesMix(ob->gpu_particles_mix);
			if (!(ob->gameflag2 & OB_GPU_PARTICLES)) {
				kxscene->AddGpuParticleObject(gameobj);
			}
		}

		// GPU particle Screen-Space collision: opt-in per object via use_gpu_particle_collider.
		if (ob->gameflag2 & OB_GPU_PARTICLE_COLLIDER) {
			kxscene->AddGpuParticleColliderObject(gameobj);
		}

		// Sun/CSM static shadow cache: auto-classify by Physics Type. Static/No Collision
		// objects are assumed not to move at runtime and go in the cached static list, unless
		// use_force_dynamic_shadow overrides that (e.g. a scripted moving platform with Static
		// physics). Everything else (Rigid Body, Dynamic, Character, Soft Body, ...) is dynamic.
		const bool forceDynamicShadow = (ob->gameflag2 & OB_FORCE_DYNAMIC_SHADOW) != 0;
		const bool staticPhysics = (ob->body_type == OB_BODY_TYPE_STATIC || ob->body_type == OB_BODY_TYPE_NO_COLLISION);
		if (staticPhysics && !forceDynamicShadow) {
			kxscene->AddStaticShadowCasterObject(gameobj);
		}
		else {
			kxscene->AddDynamicShadowCasterObject(gameobj);
		}
	}

	return gameobj;
}

struct BL_ParentChildLink {
	struct Object *m_blenderchild;
	SG_Node *m_gamechildnode;
};


static bPoseChannel *BL_GetActivePoseChannel(Object *ob)
{
	bArmature *arm = (bArmature *)ob->data;
	bPoseChannel *pchan;

	/* find active */
	for (pchan = (bPoseChannel *)ob->pose->chanbase.first; pchan; pchan = pchan->next) {
		if (pchan->bone && (pchan->bone == arm->act_bone) && (pchan->bone->layer & arm->layer)) {
			return pchan;
		}
	}

	return nullptr;
}

static ListBase *BL_GetActiveConstraint(Object *ob)
{
	if (!ob) {
		return nullptr;
	}

	// XXX - shouldnt we care about the pose data and not the mode???
	if (ob->mode & OB_MODE_POSE) {
		bPoseChannel *pchan;

		pchan = BL_GetActivePoseChannel(ob);
		if (pchan) {
			return &pchan->constraints;
		}
	}
	else {
		return &ob->constraints;
	}

	return nullptr;
}

// Copy base layer to object layer like in BKE_scene_set_background
static void BL_SetBlenderSceneBackground(Scene *blenderscene)
{
	Scene *it;
	Base *base;

	for (SETLOOPER(blenderscene, it, base)) {
		base->object->lay = base->lay;
		base->object->flag = base->flag;
	}
}

static void BL_ConvertComponentsObject(KX_GameObject *gameobj, Object *blenderobj)
{
#ifdef WITH_PYTHON
	PythonComponent *pc = (PythonComponent *)blenderobj->components.first;
	PyObject *arg_dict = nullptr, *args = nullptr, *mod = nullptr, *cls = nullptr, *pycomp = nullptr, *ret = nullptr;

	if (!pc) {
		return;
	}

	EXP_ListValue<KX_PythonComponent> *components = new EXP_ListValue<KX_PythonComponent>();

	while (pc) {
		// Make sure to clean out anything from previous loops
		Py_XDECREF(args);
		Py_XDECREF(arg_dict);
		Py_XDECREF(mod);
		Py_XDECREF(cls);
		Py_XDECREF(ret);
		Py_XDECREF(pycomp);
		args = arg_dict = mod = cls = pycomp = ret = nullptr;

		// Grab the module
		mod = PyImport_ImportModule(pc->module);

		if (mod == nullptr) {
			if (PyErr_Occurred()) {
				PyErr_Print();
			}
			CM_Error("coulding import the module '" << pc->module << "'");
			pc = pc->next;
			continue;
		}

		// Grab the class object
		cls = PyObject_GetAttrString(mod, pc->name);
		if (cls == nullptr) {
			if (PyErr_Occurred()) {
				PyErr_Print();
			}
			CM_Error("python module found, but failed to find the component '" << pc->name << "'");
			pc = pc->next;
			continue;
		}

		// Lastly make sure we have a class and it's an appropriate sub type
		if (!PyType_Check(cls) || !PyObject_IsSubclass(cls, (PyObject *)&KX_PythonComponent::Type)) {
			CM_Error(pc->module << "." << pc->name << " is not a KX_PythonComponent subclass");
			pc = pc->next;
			continue;
		}

		// Every thing checks out, now generate the args dictionary and init the component
		args = PyTuple_Pack(1, gameobj->GetProxy());

		pycomp = PyObject_Call(cls, args, nullptr);

		if (PyErr_Occurred()) {
			// The component is invalid, drop it
			PyErr_Print();
		}
		else {
			KX_PythonComponent *comp = static_cast<KX_PythonComponent *>(EXP_PROXY_REF(pycomp));
			comp->SetBlenderPythonComponent(pc);
			comp->SetGameObject(gameobj);
			components->Add(comp);
		}

		pc = pc->next;
	}

	Py_XDECREF(args);
	Py_XDECREF(mod);
	Py_XDECREF(cls);
	Py_XDECREF(pycomp);

	gameobj->SetComponents(components);
#endif  // WITH_PYTHON
}

/* helper for BL_ConvertBlenderObjects, avoids code duplication
 * note: all var names match args are passed from the caller */
static void bl_ConvertBlenderObject_Single(BL_SceneConverter& converter,
                                           Object *blenderobject,
                                           std::vector<BL_ParentChildLink> &vec_parent_child,
                                           EXP_ListValue<KX_GameObject> *logicbrick_conversionlist,
                                           EXP_ListValue<KX_GameObject> *objectlist, EXP_ListValue<KX_GameObject> *inactivelist,
                                           KX_Scene *kxscene, KX_GameObject *gameobj,
                                           SCA_LogicManager *logicmgr, SCA_TimeEventManager *timemgr,
                                           bool isInActiveLayer)
{
	const mt::vec3 pos(
		blenderobject->loc[0] + blenderobject->dloc[0],
		blenderobject->loc[1] + blenderobject->dloc[1],
		blenderobject->loc[2] + blenderobject->dloc[2]);

	float rotmat[3][3];
	BKE_object_rot_to_mat3(blenderobject, rotmat, false);
	const mt::mat3 rotation(rotmat);

	const mt::vec3 scale(
		blenderobject->size[0] * blenderobject->dscale[0],
		blenderobject->size[1] * blenderobject->dscale[1],
		blenderobject->size[2] * blenderobject->dscale[2]);

	gameobj->NodeSetLocalPosition(pos);
	gameobj->NodeSetLocalOrientation(rotation);
	gameobj->NodeSetLocalScale(scale);
	gameobj->NodeUpdate();

	BL_ConvertProperties(blenderobject, gameobj, timemgr, kxscene, isInActiveLayer);

	gameobj->SetName(blenderobject->id.name + 2);

	// Update children/parent hierarchy.
	if (blenderobject->parent != 0) {
		// Blender has an additional 'parentinverse' offset in each object.
		SG_Callbacks callback(nullptr, nullptr, nullptr, KX_Scene::KX_ScenegraphUpdateFunc, KX_Scene::KX_ScenegraphRescheduleFunc);
		SG_Node *parentinversenode = new SG_Node(nullptr, kxscene, callback);

		// Define a normal parent relationship for this node.
		KX_NormalParentRelation *parent_relation = new KX_NormalParentRelation();
		parentinversenode->SetParentRelation(parent_relation);

		BL_ParentChildLink pclink;
		pclink.m_blenderchild = blenderobject;
		pclink.m_gamechildnode = parentinversenode;
		vec_parent_child.push_back(pclink);

		// Extract location, orientation and scale out of the inverse parent matrix.
		float invp_loc[3], invp_rot[3][3], invp_size[3];
		mat4_to_loc_rot_size(invp_loc, invp_rot, invp_size, blenderobject->parentinv);

		parentinversenode->SetLocalPosition(mt::vec3(invp_loc));
		parentinversenode->SetLocalOrientation(mt::mat3(invp_rot));
		parentinversenode->SetLocalScale(mt::vec3(invp_size));
		parentinversenode->AddChild(gameobj->GetNode());
	}

	// Needed for python scripting.
	logicmgr->RegisterGameObjectName(gameobj->GetName(), gameobj);

	// Needed for group duplication.
	logicmgr->RegisterGameObj(blenderobject, gameobj);
	for (RAS_Mesh *meshobj : gameobj->GetMeshList()) {
		logicmgr->RegisterGameMeshName(meshobj->GetName(), blenderobject);
	}

	converter.RegisterGameObject(gameobj, blenderobject);

	logicbrick_conversionlist->Add(CM_AddRef(gameobj));

	// Only draw/use objects in active 'blender' layers.
	if (isInActiveLayer) {
		objectlist->Add(CM_AddRef(gameobj));

		gameobj->NodeUpdate();
	}
	else {
		// We must store this object otherwise it will be deleted at the end of this function if it is not a root object.
		inactivelist->Add(CM_AddRef(gameobj));
	}
}

static void BL_ConvertCutscene(KX_Scene *kxscene, Scene *blenderscene, const BL_SceneConverter& converter)
{
	const CutsceneSettings *settings = blenderscene->cutscene_settings;
	if (!settings || BLI_listbase_is_empty(&settings->sequences)) {
		return;
	}

	KX_CutsceneManager::Sequences sequences;
	LISTBASE_FOREACH (const CutsceneSequence *, blenderSequence, &settings->sequences) {
		KX_CutsceneManager::Sequence sequence;
		sequence.m_name = blenderSequence->name;

		LISTBASE_FOREACH (const CutsceneEvent *, blenderEvent, &blenderSequence->events) {
			KX_CutsceneManager::Event event;
			event.m_name = blenderEvent->name;
			event.m_time = blenderEvent->time;
			event.m_type = blenderEvent->type;
			event.m_templateObject = converter.FindGameObject(blenderEvent->template_object);
			event.m_spawnPoint = converter.FindGameObject(blenderEvent->spawn_point);
			event.m_dependentObject = converter.FindGameObject(blenderEvent->dependent_object);
			event.m_paramStrA = blenderEvent->param_str_a;
			event.m_paramStrB = blenderEvent->param_str_b;
			event.m_paramFloat = blenderEvent->param_float;
			event.m_paramInt = blenderEvent->param_int;
			event.m_paramBool = blenderEvent->param_bool;
			event.m_textEn = blenderEvent->text_en;
			event.m_textPt = blenderEvent->text_pt;
			event.m_textEs = blenderEvent->text_es;
			event.m_textRu = blenderEvent->text_ru;
			event.m_audioPath = blenderEvent->audio_path;
			sequence.m_events.push_back(event);
		}

		sequences.push_back(sequence);
	}

	kxscene->SetCutsceneManager(std::unique_ptr<KX_CutsceneManager>(new KX_CutsceneManager(std::move(sequences))));
}

/// Convert blender objects into ketsji gameobjects.
void BL_ConvertBlenderObjects(struct Main *maggie,
                              KX_Scene *kxscene,
                              KX_KetsjiEngine *ketsjiEngine,
                              e_PhysicsEngine physics_engine,
                              RAS_Rasterizer *rendertools,
                              RAS_ICanvas *canvas,
                              BL_SceneConverter& converter,
                              bool alwaysUseExpandFraming,
							  float camZoom,
                              bool libloading)
{

#ifdef __EMSCRIPTEN__
#  define WEB_CONVERT_TRACE(message) fprintf(stderr, "[web-convert] %s\n", message)
#  define WEB_CONVERT_TRACE_OBJECT(object) \
	fprintf(stderr, "[web-convert] object begin: %.64s type=%d\n", (object)->id.name + 2, (object)->type)
#else
#  define WEB_CONVERT_TRACE(message) ((void)0)
#  define WEB_CONVERT_TRACE_OBJECT(object) ((void)0)
#endif
	WEB_CONVERT_TRACE("begin");

#define BL_CONVERTBLENDEROBJECT_SINGLE                                 \
	bl_ConvertBlenderObject_Single(converter,                          \
	                               blenderobject,                      \
	                               vec_parent_child,                   \
	                               logicbrick_conversionlist,          \
	                               objectlist, inactivelist, \
	                               kxscene, gameobj,                   \
	                               logicmgr, timemgr,                  \
	                               isInActiveLayer                     \
	                               )



	Scene *blenderscene = kxscene->GetBlenderScene();

	// List of groups to be converted
	std::set<Group *> grouplist;
	// All objects converted.
	std::set<Object *> allblobj;
	// Objects from groups (never in active layer).
	std::set<Object *> groupobj;

	/* We have to ensure that group definitions are only converted once
	 * push all converted group members to this set.
	 * This will happen when a group instance is made from a linked group instance
	 * and both are on the active layer. */
	EXP_ListValue<KX_GameObject> *convertedlist = new EXP_ListValue<KX_GameObject>();


	// Get the frame settings of the canvas.
	// Get the aspect ratio of the canvas as designed by the user.
	RAS_FrameSettings::RAS_FrameType frame_type;
	int aspect_width;
	int aspect_height;

	if (alwaysUseExpandFraming) {
		frame_type = RAS_FrameSettings::e_frame_extend;
		aspect_width = canvas->GetWidth();
		aspect_height = canvas->GetHeight();
	}
	else {
		if (blenderscene->gm.framing.type == SCE_GAMEFRAMING_BARS) {
			frame_type = RAS_FrameSettings::e_frame_bars;
		}
		else if (blenderscene->gm.framing.type == SCE_GAMEFRAMING_EXTEND) {
			frame_type = RAS_FrameSettings::e_frame_extend;
		}
		else {
			frame_type = RAS_FrameSettings::e_frame_scale;
		}

		aspect_width  = (int)(blenderscene->r.xsch * blenderscene->r.xasp);
		aspect_height = (int)(blenderscene->r.ysch * blenderscene->r.yasp);
	}

	RAS_FrameSettings frame_settings(
		frame_type,
		blenderscene->gm.framing.col[0],
		blenderscene->gm.framing.col[1],
		blenderscene->gm.framing.col[2],
		aspect_width,
		aspect_height);
	kxscene->SetFramingType(frame_settings);

	kxscene->SetGravity(mt::vec3(0.0f, 0.0f, -blenderscene->gm.gravity));

	// Set activity culling parameters.
	kxscene->SetActivityCulling((blenderscene->gm.mode & WO_ACTIVITY_CULLING) != 0);
	kxscene->SetDbvtCulling((blenderscene->gm.mode & WO_DBVT_CULLING) != 0);

	// No occlusion culling by default.
	kxscene->SetDbvtOcclusionRes(0);

	if (blenderscene->gm.lodflag & SCE_LOD_USE_HYST) {
		kxscene->SetLodHysteresis(true);
		kxscene->SetLodHysteresisValue(blenderscene->gm.scehysteresis);
	}

	// Convert world.
	WEB_CONVERT_TRACE("world begin");
	KX_WorldInfo *worldinfo = new KX_WorldInfo(blenderscene, blenderscene->world);
	worldinfo->UpdateWorldSettings(rendertools);
	worldinfo->UpdateBackGround(rendertools, nullptr);
	if (blenderscene->world) {
		BL_ConvertWorldProperties(blenderscene->world, worldinfo);
	}
	kxscene->SetWorldInfo(worldinfo);
	WEB_CONVERT_TRACE("world end");

	const bool showObstacleSimulation = (blenderscene->gm.flag & GAME_SHOW_OBSTACLE_SIMULATION) != 0;
	KX_ObstacleSimulation *obstacleSimulation = nullptr;
	switch (blenderscene->gm.obstacleSimulation) {
		case OBSTSIMULATION_TOI_rays:
		{
			obstacleSimulation = new KX_ObstacleSimulationTOI_rays(blenderscene->gm.levelHeight, showObstacleSimulation);
			break;
		}
		case OBSTSIMULATION_TOI_cells:
		{
			obstacleSimulation = new KX_ObstacleSimulationTOI_cells(blenderscene->gm.levelHeight, showObstacleSimulation);
			break;
		}
	}
	kxscene->SetObstacleSimulation(obstacleSimulation);

	int activeLayerBitInfo = blenderscene->lay;

	std::vector<BL_ParentChildLink> vec_parent_child;

	EXP_ListValue<KX_GameObject> *objectlist = kxscene->GetObjectList();
	EXP_ListValue<KX_GameObject> *inactivelist = kxscene->GetInactiveList();
	EXP_ListValue<KX_GameObject> *parentlist = kxscene->GetRootParentList();

	SCA_LogicManager *logicmgr = kxscene->GetLogicManager();
	SCA_TimeEventManager *timemgr = kxscene->GetTimeEventManager();

	EXP_ListValue<KX_GameObject> *logicbrick_conversionlist = new EXP_ListValue<KX_GameObject>();

	BL_SetBlenderSceneBackground(blenderscene);

	/* Let's support scene set.
	 * Beware of name conflict in linked data, it will not crash but will create confusion
	 * in Python scripting and in certain actuators (replace mesh). Linked scene *should* have
	 * no conflicting name for Object, Object data and Action.
	 */
	Scene *sce_iter;
	Base *base;
	for (SETLOOPER(blenderscene, sce_iter, base)) {
		Object *blenderobject = base->object;
		WEB_CONVERT_TRACE_OBJECT(blenderobject);
		allblobj.insert(blenderobject);

		KX_GameObject *gameobj = (blenderobject->gameflag & OB_TASK_CONVERT) ?
						BL_GameObjectFromBlenderObject(base->object, kxscene, rendertools, canvas, converter, camZoom)
						:nullptr;

		if (gameobj) {
			bool isInActiveLayer = (blenderobject->lay & activeLayerBitInfo) != 0;

			// Macro calls object conversion funcs.
			BL_CONVERTBLENDEROBJECT_SINGLE;
			WEB_CONVERT_TRACE("object single converted");

			if (gameobj->IsDupliGroup()) {
				grouplist.insert(blenderobject->dup_group);
			}

			/* Note about memory leak issues:
			 * When a EXP_Value derived class is created, m_refcount is initialized to 1
			 * so the class must be released after being used to make sure that it won't
			 * hang in memory. If the object needs to be stored for a long time,
			 * use AddRef() so that this Release() does not free the object.
			 * Make sure that for any AddRef() there is a Release()!!!!
			 * Do the same for any object derived from EXP_Value, EXP_Expression and NG_NetworkMessage
			 */
			gameobj->Release();
		}
		WEB_CONVERT_TRACE("object end");
	}
	WEB_CONVERT_TRACE("main object loop end");

	if (!grouplist.empty()) {
		/* Now convert the group referenced by dupli group object
		 * keep track of all groups already converted. */
		std::set<Group *> allgrouplist = grouplist;
		std::set<Group *> tempglist;
		while (!grouplist.empty()) {
			tempglist.clear();
			tempglist.swap(grouplist);
			for (Group *group : tempglist) {
				for (GroupObject *go = (GroupObject *)group->gobject.first; go; go = (GroupObject *)go->next) {
					Object *blenderobject = go->ob;
					if (!converter.FindGameObject(blenderobject)) {
						allblobj.insert(blenderobject);
						groupobj.insert(blenderobject);
						KX_GameObject *gameobj = BL_GameObjectFromBlenderObject(blenderobject, kxscene, rendertools, canvas, converter, camZoom);

						bool isInActiveLayer = false;
						if (gameobj) {
							/* Insert object to the constraint game object list
							 * so we can check later if there is a instance in the scene or
							 * an instance and its actual group definition. */
							convertedlist->Add(CM_AddRef(gameobj));

							// Macro calls object conversion funcs.
							BL_CONVERTBLENDEROBJECT_SINGLE;

							if (gameobj->IsDupliGroup()) {
								if (allgrouplist.insert(blenderobject->dup_group).second) {
									grouplist.insert(blenderobject->dup_group);
								}
							}

							gameobj->Release();
						}
					}
				}
			}
		}
	}

	// Non-camera objects not supported as camera currently.
	if (blenderscene->camera && blenderscene->camera->type == OB_CAMERA) {
		KX_Camera *gamecamera = static_cast<KX_Camera *>(converter.FindGameObject(blenderscene->camera));
		if (gamecamera) {
			kxscene->SetActiveCamera(gamecamera);
		}
	}

	// Create hierarchy information.
	for (const BL_ParentChildLink& link : vec_parent_child) {

		Object *blenderchild = link.m_blenderchild;
		Object *blenderparent = blenderchild->parent;
		KX_GameObject *parentobj = converter.FindGameObject(blenderparent);
		KX_GameObject *childobj = converter.FindGameObject(blenderchild);

		BLI_assert(childobj);

		if (!parentobj || objectlist->SearchValue(childobj) != objectlist->SearchValue(parentobj)) {
			/* Special case: the parent and child object are not in the same layer.
			 * This weird situation is used in Apricot for test purposes.
			 * Resolve it by not converting the child
			 */
			childobj->GetNode()->DisconnectFromParent();
			delete link.m_gamechildnode;
			/* Now destroy the child object but also all its descendent that may already be linked
			 * Remove the child reference in the local list!
			 * Note: there may be descendents already if the children of the child were processed
			 * by this loop before the child. In that case, we must remove the children also
			 */
			std::vector<KX_GameObject *> childrenlist = childobj->GetChildrenRecursive();
			// The returned list by GetChildrenRecursive is not owned by anyone and must not own items, so no AddRef().
			childrenlist.push_back(childobj);
			for (KX_GameObject *obj : childrenlist) {
				if (logicbrick_conversionlist->RemoveValue(obj)) {
					obj->Release();
				}
				if (convertedlist->RemoveValue(obj)) {
					obj->Release();
				}
				// Every descendant was registered individually during conversion; unregister
				// each one here too, otherwise m_map_blender_to_gameobject keeps dangling
				// entries pointing at objects just released above.
				converter.UnregisterGameObject(obj);
			}

			kxscene->RemoveObject(childobj);

			continue;
		}

		switch (blenderchild->partype) {
			case PARVERT1:
			{
				// Create a new vertex parent relationship for this node.
				KX_VertexParentRelation *vertex_parent_relation = new KX_VertexParentRelation();
				link.m_gamechildnode->SetParentRelation(vertex_parent_relation);
				break;
			}
			case PARSLOW:
			{
				// Create a new slow parent relationship for this node.
				KX_SlowParentRelation *slow_parent_relation = new KX_SlowParentRelation(blenderchild->sf);
				link.m_gamechildnode->SetParentRelation(slow_parent_relation);
				break;
			}
			case PARBONE:
			{
				// Parent this to a bone.
				Bone *parent_bone = BKE_armature_find_bone_name(BKE_armature_from_object(blenderchild->parent),
				                                                blenderchild->parsubstr);

				if (parent_bone) {
					KX_BoneParentRelation *bone_parent_relation = new KX_BoneParentRelation(parent_bone);
					link.m_gamechildnode->SetParentRelation(bone_parent_relation);
				}

				break;
			}
			default:
			{
				// Unhandled.
				break;
			}
		}

		parentobj->GetNode()->AddChild(link.m_gamechildnode);
	}
	vec_parent_child.clear();

	const std::vector<KX_GameObject *>& sumolist = converter.GetObjects();

	// Find 'root' parents (object that has not parents in SceneGraph).
	for (KX_GameObject *gameobj : sumolist) {
		if (!gameobj->GetNode()->GetParent()) {
			parentlist->Add(CM_AddRef(gameobj));
			gameobj->NodeUpdate();
		}
	}

	for (KX_GameObject *gameobj : objectlist) {
		// Init mesh users, mesh slots and deformers.
		gameobj->AddMeshUser();

		// Add active armature for update.
		if (gameobj->GetGameObjectType() == SCA_IObject::OBJ_ARMATURE) {
			kxscene->AddAnimatedObject(gameobj);
		}
	}
	WEB_CONVERT_TRACE("mesh users end");

	// Create graphic controller for culling.
	if (kxscene->GetDbvtCulling()) {
		bool occlusion = false;
		for (KX_GameObject *gameobj : sumolist) {
			// The object can't be culled ?
			if (gameobj->GetMeshList().empty() && gameobj->GetGameObjectType() != SCA_IObject::OBJ_TEXT) {
				continue;
			}

			bool isactive = objectlist->SearchValue(gameobj);
			BL_CreateGraphicObjectNew(gameobj, kxscene, isactive, physics_engine);
			if (gameobj->GetOccluder()) {
				occlusion = true;
			}
		}
		if (occlusion) {
			kxscene->SetDbvtOcclusionRes(blenderscene->gm.occlusionRes);
		}
	}

	if (blenderscene->world) {
		kxscene->GetPhysicsEnvironment()->SetNumTimeSubSteps(blenderscene->gm.physubstep);
	}

	for (KX_GameObject *gameobj : sumolist) {
		/* Now that the scenegraph is complete, let's instantiate the deformers.
		* We need that to create reusable derived mesh and physic shapes.
		*/
		if (gameobj->GetDeformer()) {
			gameobj->GetDeformer()->UpdateBuckets();
		}

		// Set up armature constraints and shapekey drivers.
		if (gameobj->GetGameObjectType() == SCA_IObject::OBJ_ARMATURE) {
			BL_ArmatureObject *armobj = static_cast<BL_ArmatureObject *>(gameobj);
			armobj->LoadConstraints(converter);

			const std::vector<KX_GameObject *> children = armobj->GetChildren();
			for (KX_GameObject *child : children) {
				BL_ShapeDeformer *deformer = dynamic_cast<BL_ShapeDeformer *>(child->GetDeformer());
				if (deformer) {
					deformer->LoadShapeDrivers(armobj);
				}
			}
		}

		// Ground Plane collision: resolve the optional height-reference object now that every
		// object in the scene has a KX_GameObject counterpart (it may point to an object
		// converted later in the main per-object loop above).
		if (gameobj->GetParticleBuffer()) {
			Object *blenderobject = gameobj->GetBlenderObject();
			if (blenderobject && blenderobject->gpu_particles.collision_ground_object) {
				KX_GameObject *groundgameobj = converter.FindGameObject(blenderobject->gpu_particles.collision_ground_object);
				if (groundgameobj) {
					gameobj->SetCollisionGroundObject(groundgameobj);
				}
			}
		}
	}
	WEB_CONVERT_TRACE("deformers end");

	// Create physics information.
	for (unsigned short i = 0; i < 2; ++i) {
		const bool processCompoundChildren = (i == 1);
		const bool processCustomMesh = (i == 1);
		for (KX_GameObject *gameobj : sumolist) {
			Object *blenderobject = gameobj->GetBlenderObject();
			int layerMask = (groupobj.find(blenderobject) == groupobj.end()) ? activeLayerBitInfo : 0;

			/* Custom Mesh Process. */
			// This object depends on another object, we will do physics on it later.
			if (blenderobject->collision_bound && !processCustomMesh) {
				continue;
			}
			// We create the physics information of these objects now because they depend on other objects (other objects it's already calculated in last loop).
			else if (blenderobject->collision_bound) {
				KX_GameObject *gameobjmesh = converter.FindGameObject(blenderobject->collision_bound);

				if (!gameobjmesh) continue;

				const std::vector<KX_Mesh *>& meshes = gameobjmesh->GetMeshList();
				KX_Mesh *meshobj = (meshes.empty()) ? nullptr : meshes.front();

				BL_CreatePhysicsObjectNew(gameobj, blenderobject, meshobj, kxscene, layerMask, converter, false);
				continue;
			}

			/* Normal and CompoundChildren Process. */
			const std::vector<KX_Mesh *>& meshes = gameobj->GetMeshList();
			KX_Mesh *meshobj = (meshes.empty()) ? nullptr : meshes.front();

			BL_CreatePhysicsObjectNew(gameobj, blenderobject, meshobj, kxscene, layerMask, converter, processCompoundChildren);
		}
	}
	WEB_CONVERT_TRACE("physics objects end");

	// Create and set bounding volume.
	for (KX_GameObject *gameobj : sumolist) {
		Object *blenderobject = gameobj->GetBlenderObject();
		Mesh *predifinedBoundMesh = blenderobject->gamePredefinedBound;

		if (predifinedBoundMesh) {
			KX_Mesh *meshobj = converter.FindGameMesh(predifinedBoundMesh);
			// In case of mesh taken in a other scene.
			if (!meshobj) {
				continue;
			}

			gameobj->SetAutoUpdateBounds(false);

			// AABB Box : min/max.
			mt::vec3 aabbMin;
			mt::vec3 aabbMax;
			// Get the mesh bounding box for none deformer.
			RAS_BoundingBox *boundingBox = meshobj->GetBoundingBox();
			// Get the AABB.
			boundingBox->GetAabb(aabbMin, aabbMax);
			gameobj->SetBoundsAabb(aabbMin, aabbMax);
		}
		else {
			// The object allow AABB auto update only if there's no predefined bound.
			gameobj->SetAutoUpdateBounds(true);

			gameobj->UpdateBounds(true);
		}
	}

	// Create physics joints.
	for (KX_GameObject *gameobj : sumolist) {
		PHY_IPhysicsEnvironment *physEnv = kxscene->GetPhysicsEnvironment();
		Object *blenderobject = gameobj->GetBlenderObject();
		ListBase *conlist = BL_GetActiveConstraint(blenderobject);

		if (!conlist) {
			continue;
		}

		BL_ConvertObjectInfo *info = gameobj->GetConvertObjectInfo();

		for (bConstraint *curcon = (bConstraint *)conlist->first; curcon; curcon = (bConstraint *)curcon->next) {
			if (curcon->type != CONSTRAINT_TYPE_RIGIDBODYJOINT) {
				continue;
			}

			bRigidBodyJointConstraint *dat = (bRigidBodyJointConstraint *)curcon->data;

			// Skip if no target or a child object is selected or constraints are deactivated.
			if (!dat->tar || dat->child || (curcon->flag & CONSTRAINT_OFF)) {
				continue;
			}

			// Store constraints of grouped and instanced objects for all layers.
			info->m_constraints.push_back(dat);

			/** if it's during libload we only add constraints in the object but
			 * doesn't create it. Constraint will be replicated later in scene->MergeScene
			 */
			if (libloading) {
				continue;
			}

			/* Skipped already converted constraints.
			 * This will happen when a group instance is made from a linked group instance
			 * and both are on the active layer. */
			if (convertedlist->FindValue(gameobj->GetName())) {
				continue;
			}

			for (KX_GameObject *gotar : sumolist) {
				if (gotar->GetName() == (dat->tar->id.name + 2) &&
					(gotar->GetLayer() & activeLayerBitInfo) && gotar->GetPhysicsController() &&
					(gameobj->GetLayer() & activeLayerBitInfo) && gameobj->GetPhysicsController())
				{
					physEnv->SetupObjectConstraints(gameobj, gotar, dat);
					break;
				}
			}
		}
	}

	// Create native vehicles from game.is_vehicle/vehicle_wheels (DNA/RNA/UI marker).
	{
		const float kDefaultSuspensionRestLength = 0.3f;
		const float kDefaultWheelRadius = 0.3f;
		const float kMaxSaneWheelRadius = 1.7f;
		const float kMaxSaneSuspensionRestLength = 0.6f;
		PHY_IPhysicsEnvironment *physEnv = kxscene->GetPhysicsEnvironment();

		for (KX_GameObject *gameobj : sumolist) {
			Object *blenderobject = gameobj->GetBlenderObject();

			if (!(blenderobject->gameflag2 & OB_VEHICLE)) {
				continue;
			}

			if (!(blenderobject->gameflag & OB_RIGID_BODY) || !gameobj->GetPhysicsController()) {
				CM_Warning("\"" << gameobj->GetName() << "\" has game.is_vehicle set but is not a "
				           "Rigid Body with an active physics controller; skipping native vehicle creation.");
				continue;
			}

			if (!blenderobject->vehicle_wheels.first) {
				continue;
			}

			// Resolve every wheel object first; skip the whole chassis (no partial vehicle)
			// if any reference is missing, matching KX_ApplyVehiclePreset's all-or-nothing rule.
			std::vector<std::pair<KX_GameObject *, bWheelSettings *>> wheels;
			bool wheelsValid = true;
			for (bWheelSettings *wheel = (bWheelSettings *)blenderobject->vehicle_wheels.first; wheel; wheel = wheel->next) {
				KX_GameObject *wheelGameobj = wheel->ob ? converter.FindGameObject(wheel->ob) : nullptr;
				if (!wheelGameobj) {
					CM_Warning("\"" << gameobj->GetName() << "\": vehicle_wheels has an unresolved wheel "
					           "object; skipping native vehicle creation for this chassis.");
					wheelsValid = false;
					break;
				}
				wheels.push_back({wheelGameobj, wheel});
			}

			if (!wheelsValid || wheels.empty()) {
				continue;
			}

			PHY_IVehicle *vehicle = physEnv->CreateVehicle(gameobj->GetPhysicsController());
			if (!vehicle) {
				CM_Warning("\"" << gameobj->GetName() << "\": could not create native vehicle.");
				continue;
			}

			const mt::vec3 chassisWorldPos = gameobj->NodeGetWorldPosition();
			const mt::mat3 chassisWorldOri = gameobj->NodeGetWorldOrientation();
			const mt::vec3 down(0.0f, 0.0f, -1.0f);
			// With down=(0,0,-1), btRaycastVehicle::updateWheelTransform computes the wheel's rolling
			// "forward" as up.cross(axle). axle=(1,0,0) gives fwd=(0,1,0), matching this project's
			// Y+ = front convention so the wheel mesh spins the correct way as the chassis moves.
			const mt::vec3 axle(1.0f, 0.0f, 0.0f);

			for (auto &entry : wheels) {
				KX_GameObject *wheelGameobj = entry.first;
				bWheelSettings *wheel = entry.second;

				const mt::vec3 connectionPointCS = chassisWorldOri.Transpose() *
				                                    (wheelGameobj->NodeGetWorldPosition() - chassisWorldPos);
				const float radius = (wheel->radius > 0.0f) ? wheel->radius : kDefaultWheelRadius;
				const float restLength = (wheel->suspension_rest_length > 0.0f) ?
				                          wheel->suspension_rest_length : kDefaultSuspensionRestLength;
				const bool hasSteering = (wheel->has_steering != 0);

				if (radius > kMaxSaneWheelRadius) {
					CM_Warning("\"" << gameobj->GetName() << "\": wheel \"" << wheelGameobj->GetName() <<
					           "\" has a radius of " << radius << "m, which is larger than " <<
					           kMaxSaneWheelRadius << "m; please check the wheel radius (did you mean "
					           "centimeters instead of meters?).");
				}
				if (restLength > kMaxSaneSuspensionRestLength) {
					CM_Warning("\"" << gameobj->GetName() << "\": wheel \"" << wheelGameobj->GetName() <<
					           "\" has a suspension rest length of " << restLength << "m, which is larger "
					           "than " << kMaxSaneSuspensionRestLength << "m; please check the suspension "
					           "value (did you mean centimeters instead of meters?).");
				}

				vehicle->AddWheel(new KX_MotionState(wheelGameobj->GetNode()), connectionPointCS,
				                   down, axle, restLength, radius, hasSteering);

				const int wheelIndex = vehicle->GetNumWheels() - 1;
				vehicle->SetWheelIsDriveWheel(wheelIndex, wheel->has_drive != 0);
				if (wheel->suspension_stiffness > 0.0f) {
					vehicle->SetSuspensionStiffness(wheel->suspension_stiffness, wheelIndex);
				}
				if (wheel->suspension_damping > 0.0f) {
					vehicle->SetSuspensionDamping(wheel->suspension_damping, wheelIndex);
				}
				if (wheel->suspension_compression > 0.0f) {
					vehicle->SetSuspensionCompression(wheel->suspension_compression, wheelIndex);
				}
				if (wheel->friction > 0.0f) {
					vehicle->SetWheelFriction(wheel->friction, wheelIndex);
				}
				if (wheel->roll_influence > 0.0f) {
					vehicle->SetRollInfluence(wheel->roll_influence, wheelIndex);
				}
				if (wheel->max_suspension_travel_cm > 0.0f) {
					vehicle->SetMaxSuspensionTravel(wheel->max_suspension_travel_cm, wheelIndex);
				}
				if (wheel->max_suspension_force > 0.0f) {
					vehicle->SetMaxSuspensionForce(wheel->max_suspension_force, wheelIndex);
				}
			}

			if (blenderobject->vehicle_ray_cast_mask > 0) {
				vehicle->SetRayCastMask((short)blenderobject->vehicle_ray_cast_mask);
			}

			gameobj->SetVehicleConstraintId(vehicle->GetUserConstraintId());

			gameobj->SetVehicleMaxTorque(blenderobject->vehicle_max_torque);
			gameobj->SetVehicleMaxRPM(blenderobject->vehicle_max_rpm);

			gameobj->SetVehicleGearboxType(blenderobject->gearbox_type);
			std::vector<float> gearRatios;
			for (bGearRatio *gear = (bGearRatio *)blenderobject->vehicle_gears.first; gear; gear = gear->next) {
				gearRatios.push_back(gear->ratio);
			}
			gameobj->SetVehicleGearRatios(gearRatios);

			if (blenderobject->vehicle_steering_wheel) {
				KX_GameObject *steeringWheelObj = converter.FindGameObject(blenderobject->vehicle_steering_wheel);
				if (steeringWheelObj) {
					gameobj->SetVehicleSteeringWheelName(steeringWheelObj->GetName());
				}
				else {
					CM_Warning("\"" << gameobj->GetName() << "\": game.vehicle_steering_wheel points to an "
					           "unresolved object; steering wheel visual rotation will be unavailable.");
				}
			}
		}
	}

	// Create object representations for obstacle simulation.
	KX_ObstacleSimulation *obssimulation = kxscene->GetObstacleSimulation();
	if (obssimulation) {
		for (KX_GameObject *gameobj : objectlist) {
			Object *blenderobject = gameobj->GetBlenderObject();
			if (blenderobject->gameflag & OB_HASOBSTACLE) {
				obssimulation->AddObstacleForObj(gameobj);
			}
		}
	}

	// Process navigation mesh objects.
	for (KX_GameObject *gameobj : objectlist) {
		Object *blenderobject = gameobj->GetBlenderObject();
		if (blenderobject->type == OB_MESH && (blenderobject->gameflag & OB_NAVMESH)) {
			KX_NavMeshObject *navmesh = static_cast<KX_NavMeshObject *>(gameobj);
			navmesh->SetVisible(false, true);
			navmesh->BuildNavMesh();
		}
	}
	for (KX_GameObject *gameobj : inactivelist) {
		Object *blenderobject = gameobj->GetBlenderObject();
		if (blenderobject->type == OB_MESH && (blenderobject->gameflag & OB_NAVMESH)) {
			KX_NavMeshObject *navmesh = static_cast<KX_NavMeshObject *>(gameobj);
			navmesh->SetVisible(false, true);
		}
	}

	// Convert logic bricks, sensors, controllers and actuators.
	for (KX_GameObject *gameobj : logicbrick_conversionlist) {
		Object *blenderobj = gameobj->GetBlenderObject();
		int layerMask = (groupobj.find(blenderobj) == groupobj.end()) ? activeLayerBitInfo : 0;
		bool isInActiveLayer = (blenderobj->lay & layerMask) != 0;
		BL_ConvertActuators(maggie->name, blenderobj, gameobj, logicmgr, kxscene, ketsjiEngine, layerMask, isInActiveLayer, converter);
	}
	WEB_CONVERT_TRACE("actuators end");

	for (KX_GameObject *gameobj : logicbrick_conversionlist) {
		Object *blenderobj = gameobj->GetBlenderObject();
		int layerMask = (groupobj.find(blenderobj) == groupobj.end()) ? activeLayerBitInfo : 0;
		bool isInActiveLayer = (blenderobj->lay & layerMask) != 0;
		BL_ConvertControllers(blenderobj, gameobj, logicmgr, layerMask, isInActiveLayer, converter, libloading);
	}
	WEB_CONVERT_TRACE("controllers end");

	for (KX_GameObject *gameobj : logicbrick_conversionlist) {
		Object *blenderobj = gameobj->GetBlenderObject();
		int layerMask = (groupobj.find(blenderobj) == groupobj.end()) ? activeLayerBitInfo : 0;
		bool isInActiveLayer = (blenderobj->lay & layerMask) != 0;
		BL_ConvertSensors(blenderobj, gameobj, logicmgr, kxscene, ketsjiEngine, layerMask, isInActiveLayer, canvas, converter);
		// Set the init state to all objects.
		gameobj->SetInitState((blenderobj->init_state) ? blenderobj->init_state : blenderobj->state);
	}
	WEB_CONVERT_TRACE("sensors end");

	// Apply the initial state to controllers, only on the active objects as this registers the sensors.
	for (KX_GameObject *gameobj : objectlist) {
		gameobj->ResetState();
	}

	BL_ConvertCutscene(kxscene, blenderscene, converter);

	// Cleanup converted set of group objects.
	convertedlist->Release();
	logicbrick_conversionlist->Release();
	WEB_CONVERT_TRACE("end");
#undef WEB_CONVERT_TRACE
#undef WEB_CONVERT_TRACE_OBJECT
}

void BL_PostConvertBlenderObjects(KX_Scene *kxscene, const BL_SceneConverter& sceneconverter)
{
	const std::vector<KX_GameObject *>& sumolist = sceneconverter.GetObjects();
	EXP_ListValue<KX_GameObject> *objectlist = kxscene->GetObjectList();

#ifdef WITH_PYTHON

	// Convert the python components of each object.
	for (KX_GameObject *gameobj : sumolist) {
		Object *blenderobj = gameobj->GetBlenderObject();
		BL_ConvertComponentsObject(gameobj, blenderobj);
	}

	for (KX_GameObject *gameobj : objectlist) {
		if (gameobj->GetComponents()) {
			// Register object for component update.
			kxscene->GetPythonComponentManager().RegisterObject(gameobj);
		}
	}

#endif  // WITH_PYTHON
	//culling and render list stuff by kitsuy last fixed on 7-14-2025
	for (KX_GameObject *gameobj : objectlist) {
		if (gameobj->GetActivityCullingInfo().m_flags != KX_GameObject::ActivityCullingInfo::ACTIVITY_NONE) {
			kxscene->AddCullingObject(gameobj);
		}
		if (gameobj->GetVisible()) {
			kxscene->GetRenderList()->Add(CM_AddRef(gameobj));
		}
	}

	// Init textures for all materials.
	for (KX_BlenderMaterial *mat : sceneconverter.GetMaterials()) {
		mat->InitTextures();
	}

	// Look at every material texture and ask to create realtime map.
	for (KX_GameObject *gameobj : sumolist) {
		for (KX_Mesh *mesh : gameobj->GetMeshList()) {
			for (RAS_MeshMaterial *meshmat : mesh->GetMeshMaterialList()) {
				RAS_IMaterial *mat = meshmat->GetBucket()->GetMaterial();

				for (unsigned short k = 0; k < RAS_Texture::MaxUnits; ++k) {
					RAS_Texture *tex = mat->GetTexture(k);
					if (!tex || !tex->Ok()) {
						continue;
					}

					EnvMap *env = tex->GetTex()->env;
					if (!env || env->stype != ENV_REALT) {
						continue;
					}

					KX_GameObject *viewpoint = gameobj;
					if (env->object) {
						KX_GameObject *obj = sceneconverter.FindGameObject(env->object);
						if (obj) {
							viewpoint = obj;
						}
					}

					KX_TextureRendererManager::RendererType type = tex->IsCubeMap() ? KX_TextureRendererManager::CUBE : KX_TextureRendererManager::PLANAR;
					kxscene->GetTextureRendererManager()->AddRenderer(type, tex, viewpoint);
				}
			}
		}
	}

	/* Instantiate dupli group, we will loop trough the object
	 * that are in active layers. Note that duplicating group
	 * has the effect of adding objects at the end of objectlist.
	 * Only loop through the first part of the list.
	 */
	const unsigned int objcount = objectlist->GetCount();
	for (unsigned int i = 0; i < objcount; ++i) {
		KX_GameObject *gameobj = objectlist->GetValue(i);
		if (gameobj->IsDupliGroup()) {
			kxscene->DupliGroupRecurse(gameobj, 0);
		}
	}
}

void BL_ConvertCustomMouseCursor(KX_Scene *kxscene, Main *maggie, KX_KetsjiEngine *ketsjiEngine, const char *filepath)
{
	Scene *blenderscene = kxscene->GetBlenderScene();

	if (filepath[0] == '\0')
		return;

	Image *cursorImage = BKE_image_load_exists(maggie, filepath);
	if (cursorImage) {
		GPUTexture *m_tex = GPU_texture_from_blender(cursorImage, nullptr, RAS_Texture::GetTexture2DType(), false, 0.0, true);

		KX_KetsjiEngine::CustomMouseCursor *customCursor = new KX_KetsjiEngine::CustomMouseCursor;
		customCursor->m_tex = m_tex;
		customCursor->m_size = blenderscene->gm.cursor_size;
		customCursor->m_offset_X = blenderscene->gm.cursor_offset_x;
		customCursor->m_offset_Y = blenderscene->gm.cursor_offset_y;
		customCursor->m_mipmap = (blenderscene->gm.flag & GAME_CURSOR_USE_MIPMAP) == 0;
		customCursor->m_visible = false;

		ketsjiEngine->SetCustomMouseCursor(customCursor);
	}
}
