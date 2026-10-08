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

/** \file gameengine/Converter/BL_Converter.cpp
 *  \ingroup bgeconv
 */

#ifdef _MSC_VER
#  pragma warning (disable:4786)  // suppress stl-MSVC debug info warning
#endif

#include "KX_Scene.h"
#include "KX_GameObject.h"
#include "SCA_LogicManager.h"
#include "KX_Mesh.h"
#include "RAS_BucketManager.h"
#include "KX_PhysicsEngineEnums.h"
#include "KX_KetsjiEngine.h"
#include "KX_PythonInit.h" // So we can handle adding new text datablocks for Python to import
#include "KX_LibLoadStatus.h"
#include "KX_NodeRelationships.h"
#include "KX_BoneParentNodeRelationship.h"
#include "BL_ActionData.h"
#include "BL_Converter.h"
#include "BL_SceneConverter.h"
#include "BL_BlenderDataConversion.h"
#include "BL_ConvertObjectInfo.h"
#include "BL_LoadStats.h"

#include <sstream>
#include "BL_ActionActuator.h"
#include "KX_BlenderMaterial.h"
#include "KX_2DFilterManager.h"
#include "KX_WorldInfo.h"

#include "LA_SystemCommandLine.h"

#include "DummyPhysicsEnvironment.h"

#ifdef WITH_BULLET
#  include "CcdPhysicsEnvironment.h"
#  include "CcdCookedData.h"
#endif

#include "EXP_StringValue.h"

#ifdef WITH_PYTHON
#  include "Texture.h" // For FreeAllTextures.
#endif  // WITH_PYTHON

// This list includes only data type definitions
#include "DNA_scene_types.h"
#include "BKE_main.h"

extern "C" {
#  include "DNA_mesh_types.h"
#  include "DNA_material_types.h"
#  include "DNA_object_types.h"
#  include "BLI_blenlib.h"
#  include "BLI_linklist.h"
#  include "BLO_readfile.h"
#  include "BKE_global.h"
#  include "BKE_library.h"
#  include "BKE_material.h" // BKE_material_copy
#  include "BKE_mesh.h" // BKE_mesh_copy
#  include "BKE_idcode.h"
#  include "BKE_report.h"
#  include "BKE_scene.h" // BKE_scene_add, BKE_scene_base_add
#  include "BKE_object.h" // BKE_object_to_mat4, BKE_object_free_derived_caches
#  include "BKE_armature.h" // BKE_armature_from_object, BKE_armature_find_bone_name
#  include "DNA_armature_types.h"
#  include "BKE_customdata.h"
#  include "BLI_math.h"
#  include "DNA_mesh_types.h"
#  include "MEM_guardedalloc.h"
}

#include "BLI_task.h"
#include "CM_Message.h"

#include "GPU_material.h" // GPU_shader_cache_stats
#include "GPU_shader.h" // GPU_shader_binary_cache_set

#include <algorithm>
#include <cfloat>
#include <cstring>
#include <memory>
#include <set>

BL_Converter::SceneSlot::SceneSlot() = default;

BL_Converter::SceneSlot::SceneSlot(const BL_SceneConverter& converter)
{
	Merge(converter);
}

BL_Converter::SceneSlot::~SceneSlot() = default;

void BL_Converter::SceneSlot::Merge(BL_Converter::SceneSlot& other)
{
	m_materials.insert(m_materials.begin(),
	                   std::make_move_iterator(other.m_materials.begin()),
	                   std::make_move_iterator(other.m_materials.end()));
	m_meshobjects.insert(m_meshobjects.begin(),
	                     std::make_move_iterator(other.m_meshobjects.begin()),
	                     std::make_move_iterator(other.m_meshobjects.end()));
	m_objectInfos.insert(m_objectInfos.begin(),
	                     std::make_move_iterator(other.m_objectInfos.begin()),
	                     std::make_move_iterator(other.m_objectInfos.end()));
	m_actions.insert(m_actions.begin(),
					 std::make_move_iterator(other.m_actions.begin()),
					 std::make_move_iterator(other.m_actions.end()));
}

void BL_Converter::SceneSlot::Merge(const BL_SceneConverter& converter)
{
	for (KX_BlenderMaterial *mat : converter.m_materials) {
		m_materials.emplace_back(mat);
	}
	for (KX_Mesh *meshobj : converter.m_meshobjects) {
		m_meshobjects.emplace_back(meshobj);
	}
	for (BL_ConvertObjectInfo *info : converter.m_objectInfos) {
		m_objectInfos.emplace_back(info);
	}
	for (BL_ActionData *action : converter.m_actions) {
		m_actions.emplace_back(action);
	}
}

BL_Converter::BL_Converter(Main *maggie, KX_KetsjiEngine *engine, bool alwaysUseExpandFraming, float camZoom)
	:m_maggie(maggie),
	m_ketsjiEngine(engine),
	m_alwaysUseExpandFraming(alwaysUseExpandFraming),
	m_camZoom(camZoom)
{
	// ~half a 60 Hz frame: the game keeps its frame rate while libraries merge.
	m_mergeFrameBudget = 0.008;
	BKE_main_id_tag_all(maggie, LIB_TAG_DOIT, false);  // avoid re-tagging later on
	m_threadinfo.m_pool = BLI_task_pool_create(engine->GetTaskScheduler(), nullptr);

	m_maggies.push_back(m_maggie);

#ifdef WITH_BULLET
	CcdCookedData::Open(maggie->name, GPU_shader_binary_device_key());
	GPU_shader_binary_cache_set(CcdCookedData::FindShader, CcdCookedData::AddShader);
	/* First start of an exported game on this GPU/driver: every shader is compiled once (once per file and
	 * process, so a cache that can't be written doesn't restart the game forever). */
	static std::set<std::string> warmedUp;
	BL_SetShaderWarmUp(CcdCookedData::NeedsWarmUp() && warmedUp.insert(maggie->name).second);
	if (BL_ShaderWarmUp()) {
		CM_Message("[Cooked] compiling every shader once for this GPU/driver, then restarting");
	}
#endif
}

BL_Converter::~BL_Converter()
{
	// free any data that was dynamically loaded
	while (!m_dynamicMaggies.empty()) {
		FreeBlendFile(m_dynamicMaggies.front());
	}

	/* Thread infos like mutex must be freed after FreeBlendFile function.
	   Because it needs to lock the mutex, even if there's no active task when it's
	   in the scene converter destructor. */
	BLI_task_pool_free(m_threadinfo.m_pool);

#ifdef WITH_BULLET
	GPU_shader_binary_cache_set(nullptr, nullptr);
	CcdCookedData::Close();
	BL_SetShaderWarmUp(false);
#endif
}

Scene *BL_Converter::GetBlenderSceneForName(const std::string &name)
{
	for (Main *maggie : m_maggies) {
		Scene *sce = (Scene *)BLI_findstring(&maggie->scene, name.c_str(), offsetof(ID, name) + 2);
		if (sce) {
			return sce;
		}
	}

	return nullptr;
}

EXP_ListValue<EXP_StringValue> *BL_Converter::GetInactiveSceneNames()
{
	EXP_ListValue<EXP_StringValue> *list = new EXP_ListValue<EXP_StringValue>();

	for (Scene *sce = (Scene *)m_maggie->scene.first; sce; sce = (Scene *)sce->id.next) {
		const char *name = sce->id.name + 2;
		if (m_ketsjiEngine->CurrentScenes()->FindValue(name)) {
			continue;
		}
		EXP_StringValue *item = new EXP_StringValue(name, name);
		list->Add(item);
	}

	return list;
}

KX_GameObject *BL_Converter::FindOrConvertMainObject(const std::string& name, KX_Scene *scene_merge)
{
	Object *ob = (Object *)BLI_findstring(&m_maggie->object, name.c_str(), offsetof(ID, name) + 2);
	/* Only linked objects: a local one already belongs to a scene (active layer or a scene that
	 * isn't running) and converting it here would add a second object with the same name. */
	if (!ob || !ob->id.lib) {
		return nullptr;
	}

	/* Wrap the object in a throwaway Scene just long enough to run it through the regular
	 * conversion pipeline (physics, logic, bounding volumes...), the same trick used by
	 * LinkBlendFilePath() for group="Scene" libloading -- only skipping the disk read since
	 * the object is already resident in bmain (see WM_OT_link_to_libload). Layer 0 keeps it
	 * off the temp scene's active layer so it lands in the inactive list like any other
	 * object addObject() can replicate. */
	Scene *tempScene = BKE_scene_add(m_maggie, "..LibLoadMainObject..");
	tempScene->lay = 0;
	BKE_scene_base_add(tempScene, ob);
	/* BKE_scene_base_add() doesn't touch ob->id.us, but BKE_libblock_free() below decrements it
	 * for every object referenced by the temp scene's base list (its generic ID-link walker
	 * treats scene->base->object as a real user reference). Mirror that with an explicit
	 * increment here so freeing the temp scene doesn't leave the object under-referenced. */
	id_us_plus(&ob->id);

	KX_Scene *kxTempScene = m_ketsjiEngine->CreateScene(tempScene);
	BL_SceneConverter sceneConverter(kxTempScene, BL_Resource::Library(m_maggie));
	ConvertScene(sceneConverter, true, false);

	MergeScene(scene_merge, sceneConverter);

	BKE_libblock_free(m_maggie, tempScene);

	return scene_merge->FindInactiveObjectByName(name);
}

bool BL_Converter::IsChildOf(Object *ob, Object *parent)
{
	for (Object *par = ob->parent; par; par = par->parent) {
		if (par == parent) {
			return true;
		}
	}
	return false;
}

Object *BL_Converter::FindSceneObject(Scene *blscene, const std::string& name)
{
	Scene *sce_iter;
	Base *base;
	for (SETLOOPER(blscene, sce_iter, base)) {
		if (STREQ(base->object->id.name + 2, name.c_str())) {
			return base->object;
		}
	}
	return nullptr;
}

KX_GameObject *BL_Converter::ConvertSceneObject(KX_Scene *scene, const std::string& name, bool children, std::string& error)
{
	Scene *blscene = scene->GetBlenderScene();
	SCA_LogicManager *logicmgr = scene->GetLogicManager();

	Object *target = FindSceneObject(blscene, name);
	if (!target) {
		error = "object not found in the scene";
		return nullptr;
	}
	KX_GameObject *existing = static_cast<KX_GameObject *>(logicmgr->FindGameObjByBlendObj(target));
	if (existing) {
		return existing;
	}
	if (IsObjectDataFreed(target)) {
		error = "its mesh data was released by freeUnconvertedData()";
		return nullptr;
	}
	if (target->gameflag & OB_TASK_EDITOR_ONLY) {
		error = "its Load Mode is Editor Only";
		return nullptr;
	}

	int lay = blscene->lay;
	if (BKE_scene_collections_game_exclude_any(blscene)) {
		lay &= ~SCECOL_GAME_LAYER;
	}

	/* At load a child whose parent isn't converted, or sits on the other side of the active
	 * layers, is dropped: refuse the same cases instead of silently converting nothing. */
	Object *parentOb = target->parent;
	KX_GameObject *liveParent = nullptr;
	if (parentOb) {
		liveParent = static_cast<KX_GameObject *>(logicmgr->FindGameObjByBlendObj(parentOb));
		if (!liveParent) {
			error = "its parent is not converted, convert the parent instead";
			return nullptr;
		}
		const bool targetActive = (target->lay & lay) != 0;
		const bool parentActive = scene->GetObjectList()->SearchValue(liveParent);
		if (targetActive != parentActive) {
			error = "it and its parent are not both on active (or both on inactive) layers";
			return nullptr;
		}
	}

	std::vector<std::pair<Object *, int> > objects;
	Scene *sce_iter;
	Base *base;
	for (SETLOOPER(blscene, sce_iter, base)) {
		Object *ob = base->object;
		if ((ob == target || (children && IsChildOf(ob, target))) &&
		    !logicmgr->FindGameObjByBlendObj(ob) && !IsObjectDataFreed(ob) && !(ob->gameflag & OB_TASK_EDITOR_ONLY))
		{
			objects.emplace_back(ob, ob->gameflag);
		}
	}

	// Same throwaway scene trick as FindOrConvertMainObject(), keeping the layers of the source scene.
	Scene *tempScene = BKE_scene_add(m_maggie, "..ConvertSceneObject..");
	tempScene->lay = lay;
	for (const std::pair<Object *, int>& item : objects) {
		BKE_scene_base_add(tempScene, item.first);
		id_us_plus(&item.first->id);
		item.first->gameflag |= OB_TASK_CONVERT;
	}

	// Converted as a root (the parent lives in the other scene), linked back after the merge.
	target->parent = nullptr;
	KX_Scene *kxTempScene = m_ketsjiEngine->CreateScene(tempScene);
	BL_SceneConverter sceneConverter(kxTempScene, BL_Resource::Library(m_maggie));
	ConvertScene(sceneConverter, true, false);
	target->parent = parentOb;
	for (const std::pair<Object *, int>& item : objects) {
		item.first->gameflag = item.second;
	}

	MergeScene(scene, sceneConverter);
	BKE_libblock_free(m_maggie, tempScene);

	KX_GameObject *gameobj = static_cast<KX_GameObject *>(logicmgr->FindGameObjByBlendObj(target));
	if (!gameobj) {
		error = "conversion failed";
		return nullptr;
	}

	if (liveParent) {
		// SetParent() handles the root list and compound shapes, then the node chain is rebuilt as
		// at load: parent -> parent-inverse node (carrying the vertex/slow/bone relation) -> child.
		gameobj->SetParent(liveParent, true, false);

		SG_ParentRelation *relation = nullptr;
		switch (target->partype) {
			case PARVERT1:
				relation = new KX_VertexParentRelation();
				break;
			case PARSLOW:
				relation = new KX_SlowParentRelation(target->sf);
				break;
			case PARBONE:
			{
				bArmature *arm = BKE_armature_from_object(parentOb);
				Bone *bone = arm ? BKE_armature_find_bone_name(arm, target->parsubstr) : nullptr;
				if (bone) {
					relation = new KX_BoneParentRelation(bone);
				}
				break;
			}
		}
		if (!relation) {
			relation = new KX_NormalParentRelation();
		}

		SG_Callbacks callback(nullptr, nullptr, nullptr, KX_Scene::KX_ScenegraphUpdateFunc, KX_Scene::KX_ScenegraphRescheduleFunc);
		SG_Node *inverseNode = new SG_Node(nullptr, scene, callback);
		inverseNode->SetParentRelation(relation);
		float loc[3], rot[3][3], size[3];
		mat4_to_loc_rot_size(loc, rot, size, target->parentinv);
		inverseNode->SetLocalPosition(mt::vec3(loc));
		inverseNode->SetLocalOrientation(mt::mat3(rot));
		inverseNode->SetLocalScale(mt::vec3(size));

		SG_Node *childNode = gameobj->GetNode();
		childNode->DisconnectFromParent();
		inverseNode->AddChild(childNode);
		liveParent->GetNode()->AddChild(inverseNode);

		// The child keeps its own Blender transform, below the parent-inverse node.
		float local[4][4];
		BKE_object_to_mat4(target, local);
		mat4_to_loc_rot_size(loc, rot, size, local);
		gameobj->NodeSetLocalPosition(mt::vec3(loc));
		gameobj->NodeSetLocalOrientation(mt::mat3(rot));
		gameobj->NodeSetLocalScale(mt::vec3(size));
		inverseNode->UpdateWorldData();
	}

	return gameobj;
}

/// The embedded player converts the editor's own Main: its data must never be released.
static bool s_mainOwnedByGame = false;

void BL_Converter::SetMainOwnedByGame(bool owned)
{
	s_mainOwnedByGame = owned;
}

bool BL_Converter::IsObjectDataFreed(Object *ob) const
{
	return m_freedObjects.count(ob) != 0;
}

size_t BL_Converter::FreeUnconvertedData(Scene *blscene, std::string& error)
{
	if (!s_mainOwnedByGame) {
		error = "only available in the standalone player (the embedded one shares the editor data)";
		return 0;
	}

	EXP_ListValue<KX_Scene> *scenes = m_ketsjiEngine->CurrentScenes();
	auto isConverted = [scenes](Object *ob) {
		for (KX_Scene *scene : scenes) {
			if (scene->GetLogicManager()->FindGameObjByBlendObj(ob)) {
				return true;
			}
		}
		return false;
	};

	// Mesh objects of blscene left out by the Convert flag and not converted anywhere.
	std::set<Object *> candidates;
	Scene *sce_iter;
	Base *base;
	for (SETLOOPER(blscene, sce_iter, base)) {
		Object *ob = base->object;
		if (ob->type == OB_MESH && !(ob->gameflag & OB_TASK_CONVERT) && !isConverted(ob)) {
			candidates.insert(ob);
		}
	}

	// A mesh is released only when every user is a candidate (no other scene or ID uses it).
	std::map<Mesh *, int> users;
	for (Object *ob = (Object *)m_maggie->object.first; ob; ob = (Object *)ob->id.next) {
		if (ob->type == OB_MESH && ob->data) {
			int& count = users[(Mesh *)ob->data];
			count = (count < 0 || !candidates.count(ob)) ? -1 : count + 1;
		}
	}

	const size_t before = MEM_get_memory_in_use();
	for (const std::pair<Mesh * const, int>& item : users) {
		Mesh *me = item.first;
		const int idUsers = me->id.us - ((me->id.flag & LIB_FAKEUSER) ? 1 : 0);
		if (item.second <= 0 || item.second != idUsers || m_freedMeshes.count(me)) {
			continue;
		}
		CustomData_free(&me->vdata, me->totvert);
		CustomData_free(&me->edata, me->totedge);
		CustomData_free(&me->fdata, me->totface);
		CustomData_free(&me->ldata, me->totloop);
		CustomData_free(&me->pdata, me->totpoly);
		me->totvert = me->totedge = me->totface = me->totloop = me->totpoly = me->totselect = 0;
		MEM_SAFE_FREE(me->mselect);
		BKE_mesh_update_customdata_pointers(me, false);
		m_freedMeshes.insert(me);
	}
	for (Object *ob : candidates) {
		if (m_freedMeshes.count((Mesh *)ob->data)) {
			BKE_object_free_derived_caches(ob);
			m_freedObjects.insert(ob);
		}
	}
	const size_t after = MEM_get_memory_in_use();
	return (before > after) ? before - after : 0;
}

/// Milliseconds, for the "[Load]" console report (see BL_LoadStats.h).
static int load_ms(double seconds)
{
	return (int)(seconds * 1000.0 + 0.5);
}

/* Parallel shader compile (GL_ARB_parallel_shader_compile): the material programs are sent to the driver before
 * they are built one by one (ReloadMaterial), so the driver threads compile them together and each build only takes
 * its finished program. RANGE_NO_PARALLEL_SHADERS=1 keeps the one by one compile. */
static bool parallel_shaders()
{
	static const bool disabled = getenv("RANGE_NO_PARALLEL_SHADERS") != nullptr;
	if (disabled || !GPU_shader_prefetch_begin()) {
		return false;
	}
	GPU_shader_prefetch_end();
	return true;
}

/// Sends all the materials at once, for a compile that waits anyway (ReloadShaders).
template <class List>
static void prefetch_shaders(const List& materials)
{
	if (!parallel_shaders()) {
		return;
	}
	GPU_shader_prefetch_begin();
	for (const auto& mat : materials) {
		mat->PrefetchMaterial();
	}
	GPU_shader_prefetch_end();
}

/* One frame of an async compile, until deadline: first sends all the materials to the driver, then builds them in
 * the same order, by then mostly compiled. Spread over frames so the loading screen keeps drawing; a single call can
 * still take a while (sending waits while the driver queue is full, building waits for its program). Not "build when
 * ready": GL_COMPLETION_STATUS_ARB blocks until the compile ends on AMD drivers. Without parallel compile, builds one
 * by one. send(i) / build(i) act on material i. Returns true when all count are built. */
template <class Send, class Build>
static bool step_shaders(unsigned int count, unsigned int& built, unsigned int& sent, double deadline, Send send,
                         Build build)
{
	const bool parallel = parallel_shaders();
	while (built < count) {
		if (parallel && sent < count) {
			GPU_shader_prefetch_begin();
			send(sent++);
			GPU_shader_prefetch_end();
		}
		else {
			build(built++);
		}
		if (PIL_check_seconds_timer() >= deadline) {
			break;
		}
	}
	if (built < count) {
		return false;
	}
	if (parallel) {
		GPU_shader_prefetch_clear();
	}
	return true;
}

/// Clears the shader cache counters before a shader stage.
static void reset_load_shader_stats()
{
	int reused, compiled;
	double compileTime;
	GPU_shader_cache_stats(&reused, &compiled, &compileTime, true);
}

static void print_load_shaders(KX_Scene *scene, const char *stage, size_t materials, double textures, double merge,
                               double shaders)
{
	int reused, compiled;
	double compileTime;
	GPU_shader_cache_stats(&reused, &compiled, &compileTime, true);
	std::ostringstream detail;
	detail << "textures " << load_ms(textures)
	       << "ms, merge " << load_ms(merge) << "ms, shaders " << load_ms(shaders) << "ms ("
	       << materials << " materials x " << scene->GetLightList()->GetCount() << " lights; compiled "
	       << compiled << " " << load_ms(compileTime) << "ms, reused " << reused << ")";
	CM_Message("[Load] " << stage << " \"" << scene->GetName() << "\": " << detail.str());
	BL_LoadLog::Add(scene->GetName(), std::string(stage) + " textures", textures, detail.str());
	if (merge > 0.0) {
		BL_LoadLog::Add(scene->GetName(), std::string(stage) + " merge", merge, detail.str());
	}
	BL_LoadLog::Add(scene->GetName(), std::string(stage) + " shaders", shaders, detail.str());
}

void BL_Converter::ConvertScene(KX_Scene *scene, bool compileShaders)
{
	BL_SceneConverter converter(scene, BL_Resource::Library(m_maggie));
	ConvertScene(converter, false, true);
	const double texturesStart = PIL_check_seconds_timer();
	PostConvertScene(converter);
	const double texturesEnd = PIL_check_seconds_timer();
	/* An Add Object actuator can convert an external object into this scene while
	 * its regular conversion is still in progress. That merge creates the scene
	 * slot first, so append the local conversion instead of silently discarding
	 * it through a failed emplace(). */
	m_sceneSlots[scene].Merge(converter);
	reset_load_shader_stats();
	if (!compileShaders) {
		return;
	}
	ReloadShaders(scene);
	print_load_shaders(scene, "scene", m_sceneSlots[scene].m_materials.size(), texturesEnd - texturesStart, 0.0, PIL_check_seconds_timer() - texturesEnd);
}

/* Materials with "constant world/mist" bake the GPUWorld values into the shader at compile time. A compilation
 * spread over frames (async addScene/LibLoad) sees GPUWorld left by the last scene rendered (the loading screen),
 * so the destination scene's world is applied again before each step, as conversion did before compiling. */
void BL_Converter::UseSceneWorld(KX_Scene *scene)
{
	KX_WorldInfo *world = scene->GetWorldInfo();
	if (world) {
		world->UpdateWorldSettings(m_ketsjiEngine->GetRasterizer());
		world->UpdateBackGround(m_ketsjiEngine->GetRasterizer(), nullptr);
	}
}

bool BL_Converter::CompileSceneShaders(KX_Scene *scene, unsigned int& next, unsigned int& sent, double deadline)
{
	UniquePtrList<KX_BlenderMaterial>& materials = m_sceneSlots[scene].m_materials;
	KX_2DFilterManager *filters = scene->Get2DFilterManager();
	UseSceneWorld(scene);
	// Step 0 is the Camera FX passes, built here instead of at the first frame that uses them.
	return step_shaders((unsigned int)materials.size() + 1, next, sent, deadline,
	                    [&](unsigned int i) {
		if (i == 0) {
			if (filters) {
				filters->PrefetchCameraFX(scene);
			}
		}
		else {
			materials[i - 1]->PrefetchMaterial();
		}
	},
	                    [&](unsigned int i) {
		if (i == 0) {
			if (filters) {
				filters->PrepareCameraFX(scene);
			}
		}
		else {
			materials[i - 1]->ReloadMaterial();
		}
	});
}

void BL_Converter::ConvertScene(BL_SceneConverter& converter, bool libloading, bool actions)
{
	KX_Scene *scene = converter.GetScene();
	// Find out which physics engine
	Scene *blenderscene = scene->GetBlenderScene();

	BL_LoadStats& loadStats = BL_LoadStats::Get();
	loadStats.Reset();
	const double convertStart = PIL_check_seconds_timer();

	// Materiais com blend "Alpha Blend Hashed" (GPU_BLEND_ALPHA_TO_COVERAGE) caem para um
	// dither por shader (gpu_material.c, shade_dither) quando gm.aasamples <= 1, em vez de
	// usar alpha-to-coverage real via MSAA. Alguns drivers (ex.: NVIDIA proprietario) honram
	// literalmente "0 amostras" pedidas e entregam framebuffer single-sample, expondo esse
	// dither cru como ruido tipo "chiado de TV" em qualquer objeto com esse material (ex.:
	// arvores/grama) -- o Mesa/Intel mascara isso por padrao mesmo sem pedido explicito.
	// Forcamos um minimo aqui, por cena (cobre a cena inicial e as adicionadas em runtime via
	// LibLoad/AddScene, ja que cada uma tem seu proprio Scene->gm.aasamples independente),
	// para sempre passar pelo caminho de alpha-to-coverage real.
	if (blenderscene->gm.aasamples <= 1) {
		blenderscene->gm.aasamples = 2;
	}

	PHY_IPhysicsEnvironment *phy_env = nullptr;

	e_PhysicsEngine physics_engine = UseBullet;

	// This doesn't really seem to do anything except cause potential issues
	// when doing threaded conversion, so it's disabled for now.
	// SG_SetActiveStage(SG_STAGE_CONVERTER);

	switch (blenderscene->gm.physicsEngine) {
#ifdef WITH_BULLET
		case WOPHY_BULLET:
		{
			SYS_SystemHandle syshandle = SYS_GetSystem(); /*unused*/
			int visualizePhysics = SYS_GetCommandLineInt(syshandle, "show_physics", 0);

			phy_env = CcdPhysicsEnvironment::Create(blenderscene, visualizePhysics);
			physics_engine = UseBullet;
			break;
		}
#endif
		default:
		case WOPHY_NONE:
		{
			// We should probably use some sort of factory here
			phy_env = new DummyPhysicsEnvironment();
			physics_engine = UseNone;
			break;
		}
	}

	scene->SetPhysicsEnvironment(phy_env);

	BL_ConvertBlenderObjects(
		m_maggie,
		scene,
		m_ketsjiEngine,
		physics_engine,
		m_ketsjiEngine->GetRasterizer(),
		m_ketsjiEngine->GetCanvas(),
		converter,
		m_alwaysUseExpandFraming,
		m_camZoom,
		libloading);

	// Handle actions.
	if (actions) {
		BL_ConvertActions(scene, m_maggie, converter);
	}

	const double convertTime = PIL_check_seconds_timer() - convertStart;
	// Objects of the scene left out by their Load Mode (or by an ancestor's).
	int leftOut = 0, editorOnly = 0;
	{
		Scene *sce_iter;
		Base *base;
		for (SETLOOPER(scene->GetBlenderScene(), sce_iter, base)) {
			if (!converter.FindGameObject(base->object)) {
				++leftOut;
				editorOnly += (base->object->gameflag & OB_TASK_EDITOR_ONLY) != 0;
			}
		}
	}
	std::ostringstream detail;
	detail << converter.GetObjects().size() << " objects, " << leftOut << " left out (" << editorOnly
	       << " editor only), meshes " << loadStats.meshes << " (+"
	       << loadStats.meshesReused << " reused, " << loadStats.meshesCooked << " cooked "
	       << load_ms(loadStats.meshCooked) << "ms) " << load_ms(loadStats.mesh) << "ms, mesh batch "
	       << loadStats.meshesPrepared << " " << load_ms(loadStats.meshBatch) << "ms, tangents "
	       << loadStats.tangentMeshes << " " << load_ms(loadStats.tangent) << "ms, normals/tangents copied "
	       << loadStats.loopDataReused << " (hash " << load_ms(loadStats.loopHash) << "ms), physics "
	       << load_ms(loadStats.physics) << "ms (bvh " << load_ms(loadStats.bvh) << "ms; mesh: dm " << load_ms(loadStats.meshDm) << "ms, normals "
	       << load_ms(loadStats.normals) << "ms, end " << load_ms(loadStats.meshEnd) << "ms), objects " << load_ms(loadStats.objects) << "ms, logic "
	       << load_ms(loadStats.logic) << "ms, mesh users " << load_ms(loadStats.meshUsers) << "ms, culling "
	       << load_ms(loadStats.culling) << "ms, bounds " << load_ms(loadStats.bounds) << "ms";
	CM_Message("[Load] convert \"" << scene->GetName() << "\": " << load_ms(convertTime) << "ms, " << detail.str());
	BL_LoadLog::Add(scene->GetName(), "convert", convertTime, detail.str());
}

void BL_Converter::PostConvertScene(const BL_SceneConverter& converter)
{
	BL_PostConvertBlenderObjects(converter.GetScene(), converter);
}

void BL_Converter::RemoveScene(KX_Scene *scene)
{
#ifdef WITH_PYTHON
	Texture::FreeAllTextures(scene);
#endif  // WITH_PYTHON

	/* Delete the meshes as some one of them depends to the data owned by the scene
	 * e.g the display array bucket owned by the meshes and needed to be unregistered
	 * from the bucket manager in the scene.
	 */
	SceneSlot& sceneSlot = m_sceneSlots[scene];
	sceneSlot.m_meshobjects.clear();

	// Delete the scene.
	scene->Release();

	m_sceneSlots.erase(scene);

	// Its pending light reload has no scene left to recompile.
	const auto reload = m_reloads.find(scene);
	if (reload != m_reloads.end()) {
		for (KX_LibLoadStatus *status : reload->second.m_waiting) {
			status->Finish();
		}
		m_reloads.erase(reload);
	}
}

void BL_Converter::ConvertCustomMouseCursor(KX_Scene *start_scene, const char *filepath)
{
	BL_ConvertCustomMouseCursor(start_scene, m_maggie, m_ketsjiEngine, filepath);
}

void BL_Converter::RegisterMesh(KX_Scene *scene, KX_Mesh *mesh)
{
	scene->GetLogicManager()->RegisterMeshName(mesh->GetName(), mesh);
	m_sceneSlots[scene].m_meshobjects.emplace_back(mesh);
}

void BL_Converter::UnregisterMesh(KX_Scene *scene, KX_Mesh *mesh)
{
	scene->GetLogicManager()->UnregisterMeshName(mesh->GetName(), mesh);
	std::array<EXP_ListValue<KX_GameObject> *, 2> objLists{{scene->GetObjectList(), scene->GetInactiveList()}};
	for (EXP_ListValue<KX_GameObject> *list : objLists) {
		for (KX_GameObject *gameobj : list) {
			for (KX_Mesh *objmesh : gameobj->GetMeshList()) {
				if (objmesh == mesh) {
					gameobj->RemoveMeshes();
					break;
				}
			}
		}
	}
	UniquePtrList<KX_Mesh>& meshes = m_sceneSlots[scene].m_meshobjects;
	UniquePtrList<KX_Mesh>::iterator it = std::find_if(meshes.begin(), meshes.end(),
			[mesh](std::unique_ptr<KX_Mesh>& item){ return (mesh == item.get()); });
	if (it != meshes.end()) {
		meshes.erase(it);
	}
}

Main *BL_Converter::CreateLibrary(const std::string& path)
{
	Main *maggie = BKE_main_new();
	strncpy(maggie->name, path.c_str(), sizeof(maggie->name) - 1);
	m_dynamicMaggies.push_back(maggie);

	return maggie;
}

bool BL_Converter::ExistLibrary(const std::string& path) const
{
	for (Main *maggie : m_dynamicMaggies) {
		if (BLI_path_cmp(maggie->name, path.c_str()) == 0) {
			return true;
		}
	}

	return false;
}

std::vector<std::string> BL_Converter::GetLibraryNames() const
{
	std::vector<std::string> names;
	for (Main *maggie : m_dynamicMaggies) {
		names.push_back(maggie->name);
	}

	return names;
}

/// Main thread time spent per frame merging async libraries, the loading screen draws in between.

/// Async LibLoad progress of a scene: conversion in the thread, textures, shaders, then the merge.
static const float progress_converted = 0.6f;
static const float progress_textures = 0.7f;
static const float progress_shaders = 0.95f;

static void set_scene_progress(KX_LibLoadStatus *status, unsigned int scene, float fraction)
{
	const float count = (float)std::max<size_t>(status->GetSceneConverters().size(), 1);
	status->SetProgress(((float)scene + fraction) / count);
}

/// Merged lamps get a base in the target Blender scene and every material shader loops over those bases.
static bool has_new_lights(const BL_SceneConverter& converter)
{
	for (KX_GameObject *gameobj : converter.GetObjects()) {
		if (gameobj->GetGameObjectType() == SCA_IObject::OBJ_LIGHT) {
			return true;
		}
	}
	return false;
}

bool BL_Converter::StepMerge(PendingMerge& merge, double deadline)
{
	KX_LibLoadStatus *status = merge.m_status;
	KX_Scene *mergeScene = status->GetMergeScene();
	std::vector<BL_SceneConverter>& converters = status->GetSceneConverters();

	while (merge.m_scene < converters.size()) {
		BL_SceneConverter& converter = converters[merge.m_scene];
		switch (merge.m_stage) {
			case PendingMerge::STAGE_TEXTURES:
			{
				const double start = PIL_check_seconds_timer();
				PostConvertScene(converter);
				const double texturesTime = PIL_check_seconds_timer() - start;
				CM_Message("[Load] async textures \"" << converter.GetScene()->GetName() << "\": "
				           << load_ms(texturesTime) << "ms");
				BL_LoadLog::Add(converter.GetScene()->GetName(), "async textures", texturesTime);
				set_scene_progress(status, merge.m_scene, progress_textures);
				merge.m_stage = PendingMerge::STAGE_SHADERS;
				merge.m_material = 0;
				break;
			}
			case PendingMerge::STAGE_SHADERS:
			{
				/* Compile the new materials against the destination scene before their objects join it,
				 * one per step. New lights recompile everything later anyway (StepReloads()), but this
				 * way the new objects never draw without shader meanwhile. */
				const std::vector<KX_BlenderMaterial *>& materials = converter.GetMaterials();
				UseSceneWorld(mergeScene);
				const bool done = step_shaders((unsigned int)materials.size(), merge.m_material, merge.m_sent, deadline,
					[&](unsigned int i) {
						materials[i]->ReplaceScene(mergeScene);
						materials[i]->PrefetchMaterial();
					},
					[&](unsigned int i) {
						materials[i]->ReplaceScene(mergeScene);
						materials[i]->ReloadMaterial();
						set_scene_progress(status, merge.m_scene, progress_textures + (progress_shaders - progress_textures) *
						                   (float)(i + 1) / (float)materials.size());
					});
				if (!done) {
					// Out of time or waiting for the driver: next frame.
					return false;
				}
				merge.m_stage = PendingMerge::STAGE_MERGE;
				merge.m_sent = 0;
				break;
			}
			case PendingMerge::STAGE_MERGE:
			{
				if (has_new_lights(converter)) {
					// Restart the scene reload: materials already redone miss these lights.
					PendingReload& reload = m_reloads[mergeScene];
					reload.m_material = 0;
					reload.m_sent = 0;
					if (std::find(reload.m_waiting.begin(), reload.m_waiting.end(), status) == reload.m_waiting.end()) {
						reload.m_waiting.push_back(status);
					}
				}
				MergeScene(mergeScene, converter, false);
				++merge.m_scene;
				merge.m_stage = PendingMerge::STAGE_TEXTURES;
				merge.m_material = 0;
				if (merge.m_scene < converters.size()) {
					set_scene_progress(status, merge.m_scene, 0.0f);
				}
				break;
			}
		}

		if (PIL_check_seconds_timer() >= deadline) {
			break;
		}
	}

	return (merge.m_scene >= converters.size());
}

bool BL_Converter::IsWaitingReload(KX_LibLoadStatus *status) const
{
	for (const auto& item : m_reloads) {
		const std::vector<KX_LibLoadStatus *>& waiting = item.second.m_waiting;
		if (std::find(waiting.begin(), waiting.end(), status) != waiting.end()) {
			return true;
		}
	}
	return false;
}

void BL_Converter::StepReloads(double deadline)
{
	for (auto it = m_reloads.begin(); it != m_reloads.end();) {
		PendingReload& reload = it->second;
		// Backwards: the latest merged materials, compiled without the other new lights, come first.
		UniquePtrList<KX_BlenderMaterial>& materials = m_sceneSlots[it->first].m_materials;
		const float total = (float)std::max<size_t>(materials.size(), 1);
		UseSceneWorld(it->first);
		const unsigned int count = (unsigned int)materials.size();
		const bool done = step_shaders(count, reload.m_material, reload.m_sent, deadline,
			[&](unsigned int i) { materials[count - 1 - i]->PrefetchMaterial(); },
			[&](unsigned int i) {
				materials[count - 1 - i]->ReloadMaterial();
				for (KX_LibLoadStatus *status : reload.m_waiting) {
					const unsigned int lastScene = (unsigned int)std::max<size_t>(status->GetSceneConverters().size(), 1) - 1;
					set_scene_progress(status, lastScene, progress_shaders + (1.0f - progress_shaders) *
					                   (float)(i + 1) / total);
				}
			});
		if (!done) {
			return;
		}
		CM_Message("[Load] async light reload \"" << it->first->GetName() << "\": " << materials.size()
		           << " materials for " << reload.m_waiting.size() << " libraries");
		for (KX_LibLoadStatus *status : reload.m_waiting) {
			status->Finish();
		}
		it = m_reloads.erase(it);
	}
}

void BL_Converter::SetMergeFrameBudget(double seconds)
{
	m_mergeFrameBudget = seconds;
}

double BL_Converter::GetMergeFrameBudget() const
{
	return m_mergeFrameBudget;
}

void BL_Converter::ProcessScheduledLibraries()
{
	m_threadinfo.m_mutex.Lock();
	for (KX_LibLoadStatus *libload : m_mergequeue) {
		m_merging.push_back({libload, 0, PendingMerge::STAGE_TEXTURES, 0});
	}
	m_mergequeue.clear();
	m_threadinfo.m_mutex.Unlock();

	// Merge in loading order, at least one step per frame even when a step outlasts the budget.
	const double deadline = PIL_check_seconds_timer() + m_mergeFrameBudget;
	while (!m_merging.empty()) {
		if (!StepMerge(m_merging.front(), deadline)) {
			break;
		}
		KX_LibLoadStatus *libload = m_merging.front().m_status;
		m_merging.erase(m_merging.begin());
		if (!IsWaitingReload(libload)) {
			libload->Finish();
		}
		if (PIL_check_seconds_timer() >= deadline) {
			break;
		}
	}

	// Recompile for new lights only once nothing else is merging, a later library would restart it.
	if (m_merging.empty()) {
		StepReloads(deadline);
	}

	for (Main *maggie : m_freeQueue) {
		FreeBlendFileData(maggie);
	}
	m_freeQueue.clear();
}

void BL_Converter::FinalizeAsyncLoads()
{
	// Finish all loading libraries.
	BLI_task_pool_work_and_wait(m_threadinfo.m_pool);
	// Merge all libraries data in the current scene, to avoid memory leak of unmerged scenes.
	m_threadinfo.m_mutex.Lock();
	for (KX_LibLoadStatus *libload : m_mergequeue) {
		m_merging.push_back({libload, 0, PendingMerge::STAGE_TEXTURES, 0});
	}
	m_mergequeue.clear();
	m_threadinfo.m_mutex.Unlock();

	for (PendingMerge& merge : m_merging) {
		StepMerge(merge, DBL_MAX);
		if (!IsWaitingReload(merge.m_status)) {
			merge.m_status->Finish();
		}
	}
	m_merging.clear();
	StepReloads(DBL_MAX);

	ProcessScheduledLibraries();
}

void BL_Converter::AddScenesToMergeQueue(KX_LibLoadStatus *status)
{
	m_threadinfo.m_mutex.Lock();
	m_mergequeue.push_back(status);
	m_threadinfo.m_mutex.Unlock();
}

void BL_Converter::AsyncConvertTask(TaskPool *pool, void *ptr, int UNUSED(threadid))
{
	KX_LibLoadStatus *status = static_cast<KX_LibLoadStatus *>(ptr);
	BL_Converter *converter = status->GetConverter();

	std::vector<BL_SceneConverter>& converters = status->GetSceneConverters();
	for (unsigned int i = 0; i < converters.size(); ++i) {
		BL_SceneConverter& sceneConverter = converters[i];
		sceneConverter.SetProgressCallback([status, i](float fraction) {
			set_scene_progress(status, i, fraction * progress_converted);
		});
		converter->ConvertScene(sceneConverter, true, false);
		sceneConverter.SetProgressCallback(nullptr);
		set_scene_progress(status, i, progress_converted);
	}

	status->GetConverter()->AddScenesToMergeQueue(status);
}

KX_LibLoadStatus *BL_Converter::GetLibLoadStatus(const std::string& path)
{
	Main *maggie = GetLibraryPath(path);
	if (!maggie) {
		return nullptr;
	}
	const auto it = m_libloadStatus.find(maggie);
	return (it != m_libloadStatus.end()) ? it->second.get() : nullptr;
}

Main *BL_Converter::GetLibraryPath(const std::string& path)
{
	for (Main *maggie : m_dynamicMaggies) {
		if (BLI_path_cmp(maggie->name, path.c_str()) == 0) {
			return maggie;
		}
	}

	return nullptr;
}

KX_LibLoadStatus *BL_Converter::LinkBlendFileMemory(void *data, int length, const char *path, char *group, KX_Scene *scene_merge, char **err_str, short options)
{
	BlendHandle *blendlib = BLO_blendhandle_from_memory(data, length);

	// Error checking is done in LinkBlendFile
	return LinkBlendFile(blendlib, path, group, scene_merge, err_str, options);
}

KX_LibLoadStatus *BL_Converter::LinkBlendFilePath(const char *filepath, char *group, KX_Scene *scene_merge, char **err_str, short options)
{
	const double openStart = PIL_check_seconds_timer();
	BlendHandle *blendlib = BLO_blendhandle_from_file(filepath, nullptr);
	const double openTime = PIL_check_seconds_timer() - openStart;
	CM_Message("[Load] open \"" << filepath << "\": " << load_ms(openTime) << "ms");
	BL_LoadLog::Add(filepath, "open file", openTime);

	// Error checking is done in LinkBlendFile
	return LinkBlendFile(blendlib, filepath, group, scene_merge, err_str, options);
}

static void load_datablocks(Main *main_tmp, BlendHandle *blendlib, const char *path, int idcode)
{
	LinkNode *names = nullptr;

	int totnames_dummy;
	names = BLO_blendhandle_get_datablock_names(blendlib, idcode, &totnames_dummy);

	int i = 0;
	LinkNode *n = names;
	while (n) {
		BLO_library_link_named_part(main_tmp, &blendlib, idcode, (char *)n->link);
		n = (LinkNode *)n->next;
		i++;
	}
	BLI_linklist_free(names, free); // free linklist *and* each node's data
}

KX_LibLoadStatus *BL_Converter::LinkBlendFile(BlendHandle *blendlib, const char *path, char *group, KX_Scene *scene_merge, char **err_str, short options)
{
	const int idcode = BKE_idcode_from_name(group);
	static char err_local[255];

	// only scene and mesh supported right now
	if (!ELEM(idcode, ID_SCE, ID_ME, ID_AC)) {
		snprintf(err_local, sizeof(err_local), "invalid ID type given \"%s\"\n", group);
		*err_str = err_local;
		BLO_blendhandle_close(blendlib);
		return nullptr;
	}

	if (ExistLibrary(path)) {
		snprintf(err_local, sizeof(err_local), "blend file already open \"%s\"\n", path);
		*err_str = err_local;
		BLO_blendhandle_close(blendlib);
		return nullptr;
	}

	if (blendlib == nullptr) {
		snprintf(err_local, sizeof(err_local), "could not open blendfile \"%s\"\n", path);
		*err_str = err_local;
		return nullptr;
	}

	Main *main_newlib = BKE_main_new();

	ReportList reports;
	BKE_reports_init(&reports, RPT_STORE);

	const double linkStart = PIL_check_seconds_timer();

	// Created only for linking, then freed.
	Main *main_tmp = BLO_library_link_begin(main_newlib, &blendlib, path);
	load_datablocks(main_tmp, blendlib, path, idcode);

	// In case of scene, optionally link texts and actions.
	if (idcode == ID_SCE) {
		if (options & LIB_LOAD_LOAD_SCRIPTS) {
			load_datablocks(main_tmp, blendlib, path, ID_TXT);
		}
		if (options & LIB_LOAD_LOAD_ACTIONS) {
			load_datablocks(main_tmp, blendlib, path, ID_AC);
		}
	}

	// Don't need any special options.
	const short flag = 0;
	BLO_library_link_end(main_tmp, &blendlib, flag, nullptr, nullptr);
	BLO_blendhandle_close(blendlib);

	BKE_reports_clear(&reports);

	BLI_strncpy(main_newlib->name, path, sizeof(main_newlib->name));

	const double linkTime = PIL_check_seconds_timer() - linkStart;
	CM_Message("[Load] link \"" << path << "\" (" << group << "): " << load_ms(linkTime) << "ms");
	BL_LoadLog::Add(path, std::string("link (") + group + ")", linkTime);

	// Debug data to load.
	if (options & LIB_LOAD_VERBOSE) {
		if (idcode == ID_AC || (options & LIB_LOAD_LOAD_ACTIONS && idcode == ID_SCE)) {
			for (bAction *act = (bAction *)main_newlib->action.first; act; act = (bAction *)act->id.next) {
				CM_Debug("action name: " << act->id.name + 2);
			}
		}
		if (ELEM(idcode, ID_ME, ID_SCE)) {
			for (Mesh *mesh = (Mesh *)main_newlib->mesh.first; mesh; mesh = (Mesh *)mesh->id.next) {
				CM_Debug("mesh name: " << mesh->id.name + 2);
			}
		}
		if (idcode == ID_SCE) {
			for (Scene *bscene = (Scene *)main_newlib->scene.first; bscene; bscene = (Scene *)bscene->id.next) {
				CM_Debug("scene name: " << bscene->id.name + 2);
			}
		}
	}

	// Linking done.

	KX_LibLoadStatus *status = new KX_LibLoadStatus(this, m_ketsjiEngine, scene_merge, path);

	const BL_Resource::Library libraryId(main_newlib);

	switch (idcode) {
		case ID_ME:
		{
			BL_SceneConverter sceneConverter(scene_merge, libraryId);
			// Convert all new meshes into BGE meshes
			for (Mesh *mesh = (Mesh *)main_newlib->mesh.first; mesh; mesh = (Mesh *)mesh->id.next) {
				BL_ConvertMesh((Mesh *)mesh, nullptr, scene_merge, sceneConverter);
			}

			// Merge the meshes and materials in the targeted scene.
			MergeSceneData(scene_merge, sceneConverter);
			// Load shaders for new created materials, a mesh library has no lamps.
			ReloadShaders(sceneConverter);
			break;
		}
		case ID_AC:
		{
			BL_SceneConverter sceneConverter(scene_merge, libraryId);
			// Convert all actions and register.
			BL_ConvertActions(scene_merge, main_newlib, sceneConverter);
			// Merge the actions in the targeted scene.
			MergeSceneData(scene_merge, sceneConverter);
			break;
		}
		case ID_SCE:
		{
			// Merge all new linked scenes into the existing one

			if (options & LIB_LOAD_LOAD_SCRIPTS) {
#ifdef WITH_PYTHON
				// Handle any text datablocks
				addImportMain(main_newlib);
#endif
			}

			/** Actions aren't owned by scenes, to merge them in the targeted scene,
			 * a global scene converter is created and register every action, then this
			 * converter is merged into the targeted scene.
			 */
			if (options & LIB_LOAD_LOAD_ACTIONS) {
				BL_SceneConverter sceneConverter(scene_merge, libraryId);
				// Convert all actions and register.
				BL_ConvertActions(scene_merge, main_newlib, sceneConverter);
				// Merge the actions in the targeted scene.
				MergeSceneData(scene_merge, sceneConverter);
			}

			for (Scene *bscene = (Scene *)main_newlib->scene.first; bscene; bscene = (Scene *)bscene->id.next) {
				KX_Scene *scene = m_ketsjiEngine->CreateScene(bscene);

				// Schedule conversion and merge.
				if (options & LIB_LOAD_ASYNC) {
					status->AddSceneConverter(scene, libraryId);
				}
				// Or proceed direct conversion and merge.
				else {
					BL_SceneConverter sceneConverter(scene, libraryId);
					ConvertScene(sceneConverter, true, false);
					MergeScene(scene_merge, sceneConverter);
				}
			}
			break;
		}
	}

	if (options & LIB_LOAD_ASYNC) {
		BLI_task_pool_push(m_threadinfo.m_pool, AsyncConvertTask, (void *)status, false, TASK_PRIORITY_LOW);
	}
	else {
		status->Finish();
	}

	// Register new library.
	m_dynamicMaggies.push_back(main_newlib);
	m_maggies.push_back(main_newlib);

	// Register associated KX_LibLoadStatus.
	m_libloadStatus[main_newlib].reset(status);

	return status;
}

bool BL_Converter::FreeBlendFileData(Main *maggie)
{
	// Indentifier used to recognize ressources of this library.
	const BL_Resource::Library libraryId(maggie);

	// If the file was lib loaded (not created by LibNew).
	const auto it = m_libloadStatus.find(maggie);
	if (it != m_libloadStatus.end()) {
		KX_LibLoadStatus *status = it->second.get();
		// If the given library is currently in loading, we do nothing.
		m_threadinfo.m_mutex.Lock();
		const bool finished = status->IsFinished();
		m_threadinfo.m_mutex.Unlock();

		if (!finished) {
			CM_Error("Library (" << maggie->name << ") is currently being loaded asynchronously, and cannot be freed until this process is done");
			return false;
		}
	}

	// For each scene try to remove any usage of ressources from the library.
	for (KX_Scene *scene : m_ketsjiEngine->CurrentScenes()) {
		// Both list containing all the scene objects.
		std::array<EXP_ListValue<KX_GameObject> *, 2> allObjects{{scene->GetObjectList(), scene->GetInactiveList()}};

		for (EXP_ListValue<KX_GameObject> *objectList : allObjects) {
			for (KX_GameObject *gameobj : objectList) {
				BL_ConvertObjectInfo *info = gameobj->GetConvertObjectInfo();
				// Object as default camera are not linked to a blender resource.
				if (!info) {
					continue;
				}

				// Free object directly depending on blender object of the library.
				if (info->Belong(libraryId)) {
					scene->DelayedRemoveObject(gameobj);
				}
				// Else try to remove used ressource (e.g actions, meshes, materials...).
				else {
					gameobj->RemoveRessources(libraryId);
				}
			}
		}

		scene->RemoveEuthanasyObjects();
	}

	// Free ressources belonging to the library and unregister them.
	for (auto& pair : m_sceneSlots) {
		KX_Scene *scene = pair.first;
		SCA_LogicManager *logicmgr = scene->GetLogicManager();
		SceneSlot& sceneSlot = pair.second;

		// Free all new events to not cause a crash for invalid interactions.
		logicmgr->ClearAllEvents();

		// Free meshes.
		for (UniquePtrList<KX_Mesh>::iterator it =  sceneSlot.m_meshobjects.begin(); it !=  sceneSlot.m_meshobjects.end(); ) {
			KX_Mesh *mesh = it->get();
			if (mesh->Belong(libraryId)) {
				logicmgr->UnregisterMesh(mesh);
				it = sceneSlot.m_meshobjects.erase(it);
			}
			else {
				++it;
			}
		}

		// Free materials.
		for (UniquePtrList<KX_BlenderMaterial>::iterator it = sceneSlot.m_materials.begin(); it != sceneSlot.m_materials.end(); ) {
			KX_BlenderMaterial *mat = it->get();
			if (mat->Belong(libraryId)) {
				scene->GetBucketManager()->RemoveMaterial(mat);
				it = sceneSlot.m_materials.erase(it);
			}
			else {
				++it;
			}
		}

		// Free actions.
		for (UniquePtrList<BL_ActionData>::iterator it = sceneSlot.m_actions.begin(); it != sceneSlot.m_actions.end(); ) {
			BL_ActionData *act = it->get();
			if (act->Belong(libraryId)) {
				logicmgr->UnregisterAction(act);
				it = sceneSlot.m_actions.erase(it);
			}
			else {
				++it;
			}
		}

		// Free object infos.
		for (UniquePtrList<BL_ConvertObjectInfo>::iterator it = sceneSlot.m_objectInfos.begin(); it != sceneSlot.m_objectInfos.end(); ) {
			BL_ConvertObjectInfo *info = it->get();
			if (info->Belong(libraryId)) {
				it = sceneSlot.m_objectInfos.erase(it);
			}
			else {
				++it;
			}
		}

		// Reload materials cause they used lamps removed now.
		scene->GetBucketManager()->ReloadMaterials();
	}

	// Remove and destruct the KX_LibLoadStatus associated to the just free library.
	m_libloadStatus.erase(maggie);

	// Actual free of the blender library.
	FreeBlendFile(maggie);

	return true;
}

void BL_Converter::FreeBlendFile(Main *maggie)
{
#ifdef WITH_PYTHON
	/* make sure this maggie is removed from the import list if it's there
	 * (this operation is safe if it isn't in the list) */
	removeImportMain(maggie);
#endif

	// Remove the library from lists.
	CM_ListRemoveIfFound(m_maggies, maggie);
	CM_ListRemoveIfFound(m_dynamicMaggies, maggie);

	BKE_main_free(maggie);
}

bool BL_Converter::FreeBlendFile(const std::string& path)
{
	Main *maggie = GetLibraryPath(path);
	if (!maggie) {
		return false;
	}

	// Delay library free in ProcessScheduledLibraries.
	m_freeQueue.push_back(maggie);
	return true;
}

void BL_Converter::MergeSceneData(KX_Scene *to, const BL_SceneConverter& converter)
{
	for (KX_Mesh *mesh : converter.m_meshobjects) {
		mesh->ReplaceScene(to);
	}

	// Do this after lights are available (scene merged) so materials can use the lights in shaders.
	for (KX_BlenderMaterial *mat : converter.m_materials) {
		mat->ReplaceScene(to);
	}

	m_sceneSlots[to].Merge(converter);
}

void BL_Converter::MergeScene(KX_Scene *to, const BL_SceneConverter& converter, bool postConvert)
{
	const double texturesStart = PIL_check_seconds_timer();
	if (postConvert) {
		PostConvertScene(converter);
	}
	const double mergeStart = PIL_check_seconds_timer();

	MergeSceneData(to, converter);

	// Only new lights make the existing materials recompile (see has_new_lights()).
	const bool newLights = has_new_lights(converter);

	KX_Scene *from = converter.GetScene();
	to->MergeScene(from);

	// The async merge compiles the shaders itself, spread over frames (StepMerge()).
	if (postConvert) {
		const double shadersStart = PIL_check_seconds_timer();
		reset_load_shader_stats();
		if (newLights) {
			ReloadShaders(to);
		}
		else {
			ReloadShaders(converter);
		}
		print_load_shaders(to, newLights ? "merge into" : "merge into (new materials only)",
		                   newLights ? m_sceneSlots[to].m_materials.size() : converter.m_materials.size(),
		                   mergeStart - texturesStart, shadersStart - mergeStart, PIL_check_seconds_timer() - shadersStart);
	}

	delete from;
}

void BL_Converter::ReloadShaders(KX_Scene *scene)
{
	KX_2DFilterManager *filters = scene->Get2DFilterManager();
	if (filters && parallel_shaders()) {
		GPU_shader_prefetch_begin();
		filters->PrefetchCameraFX(scene);
		GPU_shader_prefetch_end();
	}
	prefetch_shaders(m_sceneSlots[scene].m_materials);
	if (filters) {
		filters->PrepareCameraFX(scene);
	}
	for (std::unique_ptr<KX_BlenderMaterial>& mat : m_sceneSlots[scene].m_materials) {
		mat->ReloadMaterial();
	}
	GPU_shader_prefetch_clear();
}

void BL_Converter::ReloadShaders(const BL_SceneConverter& converter)
{
	prefetch_shaders(converter.m_materials);
	for (KX_BlenderMaterial *mat : converter.m_materials) {
		mat->ReloadMaterial();
	}
	GPU_shader_prefetch_clear();
}

/** This function merges a mesh from the current scene into another main
 * it does not convert */
KX_Mesh *BL_Converter::ConvertMeshSpecial(KX_Scene *kx_scene, Main *maggie, const std::string& name)
{
	Main *from_maggie;
	ID *me = nullptr;
	for (Main *main : m_maggies) {
		me = static_cast<ID *>(BLI_findstring(&main->mesh, name.c_str(), offsetof(ID, name) + 2));
		if (me) {
			from_maggie = main;
			break;
		}
	}

	if (me == nullptr) {
		CM_Error("could not be found \"" << name << "\"");
		return nullptr;
	}
	if (m_freedMeshes.count((Mesh *)me)) {
		CM_Error("mesh data was released by freeUnconvertedData() \"" << name << "\"");
		return nullptr;
	}

	// Watch this!, if its used in the original scene can cause big troubles
	if (me->us > 0) {
#ifdef DEBUG
		CM_Debug("mesh has a user \"" << name << "\"");
#endif  // DEBUG
		me = (ID *)BKE_mesh_copy(from_maggie, (Mesh *)me);
		id_us_min(me);
	}
	BLI_remlink(&from_maggie->mesh, me); // even if we made the copy it needs to be removed
	BLI_addtail(&maggie->mesh, me);

	// Must copy the materials this uses else we cant free them
	{
		Mesh *mesh = (Mesh *)me;

		// ensure all materials are tagged
		for (int i = 0; i < mesh->totcol; i++) {
			if (mesh->mat[i]) {
				mesh->mat[i]->id.tag &= ~LIB_TAG_DOIT;
			}
		}

		for (int i = 0; i < mesh->totcol; i++) {
			Material *mat_old = mesh->mat[i];

			// if its tagged its a replaced material
			if (mat_old && (mat_old->id.tag & LIB_TAG_DOIT) == 0) {
				Material *mat_new = BKE_material_copy(from_maggie, mat_old);

				mat_new->id.tag |= LIB_TAG_DOIT;
				id_us_min(&mat_old->id);

				BLI_remlink(&from_maggie->mat, mat_new); // BKE_material_copy uses G.main, and there is no BKE_material_copy_ex
				BLI_addtail(&maggie->mat, mat_new);

				mesh->mat[i] = mat_new;

				// the same material may be used twice
				for (int j = i + 1; j < mesh->totcol; j++) {
					if (mesh->mat[j] == mat_old) {
						mesh->mat[j] = mat_new;
						id_us_plus(&mat_new->id);
						id_us_min(&mat_old->id);
					}
				}
			}
		}
	}

	BL_SceneConverter sceneConverter(kx_scene, BL_Resource::Library(maggie));

	KX_Mesh *meshobj = BL_ConvertMesh((Mesh *)me, nullptr, kx_scene, sceneConverter);

	MergeSceneData(kx_scene, sceneConverter);
	ReloadShaders(sceneConverter);

	return meshobj;
}

void BL_Converter::PrintStats()
{
	CM_Message("BGE STATS");
	CM_Message(std::endl << "Assets:");

	unsigned int nummat = 0;
	unsigned int nummesh = 0;
	unsigned int numacts = 0;

	for (const auto& pair : m_sceneSlots) {
		KX_Scene *scene = pair.first;
		const SceneSlot& sceneSlot = pair.second;

		nummat += sceneSlot.m_materials.size();
		nummesh += sceneSlot.m_meshobjects.size();
		numacts += sceneSlot.m_actions.size();

		CM_Message("\tscene: " << scene->GetName())
		CM_Message("\t\t materials: " << sceneSlot.m_materials.size());
		CM_Message("\t\t meshes: " << sceneSlot.m_meshobjects.size());
		CM_Message("\t\t actions: " << sceneSlot.m_actions.size());
	}

	CM_Message(std::endl << "Total:");
	CM_Message("\t scenes: " << m_sceneSlots.size());
	CM_Message("\t materials: " << nummat);
	CM_Message("\t meshes: " << nummesh);
	CM_Message("\t actions: " << numacts);
}
