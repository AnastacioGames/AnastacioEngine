/* SPDX-License-Identifier: GPL-2.0-or-later
 * Anastacio Material Atlas. Bake orchestration lives in C++; the Properties panel
 * only invokes this operator. Source materials and the Lightmap UV are never edited.
 */

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

extern "C" {
#include "MEM_guardedalloc.h"
#include "DNA_image_types.h"
#include "DNA_material_types.h"
#include "DNA_mesh_types.h"
#include "DNA_meshdata_types.h"
#include "DNA_node_types.h"
#include "DNA_object_types.h"
#include "DNA_scene_types.h"
#include "DNA_windowmanager_types.h"
#include "BLI_dynlib.h"
#include "BLI_math.h"
#include "BLI_path_util.h"
#include "BLI_string.h"
#include "BLI_utildefines.h"
#include "BKE_appdir.h"
#include "BKE_animsys.h"
#include "BKE_context.h"
#include "BKE_customdata.h"
#include "BKE_depsgraph.h"
#include "BKE_global.h"
#include "BKE_image.h"
#include "BKE_idprop.h"
#include "BKE_library.h"
#include "BKE_main.h"
#include "BKE_material.h"
#include "BKE_mesh.h"
#include "BKE_node.h"
#include "BKE_object.h"
#include "BKE_report.h"
#include "BKE_scene.h"
#include "IMB_imbuf_types.h"
#include "IMB_colormanagement.h"
#include "RNA_access.h"
#include "RNA_define.h"
#include "RNA_types.h"
#include "RE_engine.h"
#include "ED_screen.h"
#include "WM_api.h"
#include "WM_types.h"
int ED_object_bake_job_start(bContext *C, wmOperator *op, int *result_out);
}

namespace {
constexpr const char *atlas_uv = "AnastacioAtlas";
constexpr const char *backup_key = "_anastacio_atlas_source";
constexpr const char *backup_slot_key = "_anastacio_atlas_source_slot";
bool atlas_busy = false;
const char *map_inputs[] = {"Base Color", "Roughness", "Metallic", "Specular"};
const char *map_names[] = {"BaseColor", "Roughness", "Metallic", "Specular", "Normal"};

void require(bool condition, const std::string &message)
{
  if (!condition) {
    throw std::runtime_error(message);
  }
}

bNodeSocket *socket(bNode *node, const char *name, int direction = SOCK_IN)
{
  bNodeSocket *sock = nodeFindSocket(node, direction, name);
  require(sock != nullptr, std::string("Missing socket: ") + name);
  return sock;
}

bNodeLink *input_link(bNodeTree *tree, bNodeSocket *sock)
{
  for (bNodeLink *link = static_cast<bNodeLink *>(tree->links.first); link; link = link->next) {
    if (link->tosock == sock) {
      return link;
    }
  }
  return nullptr;
}

void connect(bNodeTree *tree, bNode *from, const char *output, bNode *to, const char *input)
{
  nodeAddLink(tree, from, socket(from, output, SOCK_OUT), to, socket(to, input));
}

bNode *surface_shader(Material *mat, bNode **r_output = nullptr)
{
  require(mat && mat->use_nodes && mat->nodetree,
          "Use PBR node materials (convert legacy materials to PBR first)");
  bNodeTree *tree = mat->nodetree;
  bNode *output = nullptr;
  for (bNode *n = static_cast<bNode *>(tree->nodes.first); n; n = n->next) {
    if (n->type == SH_NODE_OUTPUT_MATERIAL && (n->flag & NODE_DO_OUTPUT)) {
      output = n;
      break;
    }
  }
  require(output != nullptr, "Material has no active Material Output");
  bNodeLink *surface = input_link(tree, socket(output, "Surface"));
  require(surface && surface->fromnode->type == SH_NODE_BSDF_PRINCIPLED,
          "This version needs a Principled BSDF connected directly to Material Output");
  require(!input_link(tree, socket(output, "Volume")) &&
              !input_link(tree, socket(output, "Displacement")),
          "Volume and displacement cannot be flattened by this atlas version");
  if (r_output) {
    *r_output = output;
  }
  return surface->fromnode;
}

void validate_material(Material *mat, bNode *reference, Mesh *mesh)
{
  require(mat && mat->game.alpha_blend == GEMAT_SOLID && mat->alpha == 1.0f,
          "Only opaque materials are supported; separate transparent materials first");
  bNode *shader = surface_shader(mat);
  require(!BKE_animdata_from_id(&mat->id), "Animated materials cannot be baked to a static atlas");
  require(!BKE_animdata_from_id(&mat->nodetree->id), "Animated node trees cannot be baked to a static atlas");
  require(!mat->fragcode && !mat->vertcode && !mat->group && mat->foliage_strength == 0,
          "Custom shaders, light groups and foliage need a separate atlas implementation");
  for (bNodeSocket *sock = static_cast<bNodeSocket *>(shader->inputs.first); sock; sock = sock->next) {
    bool baked = STREQ(sock->identifier, "Normal");
    for (const char *name : map_inputs) {
      baked |= STREQ(sock->identifier, name);
    }
    if (baked) {
      continue;
    }
    require(!input_link(mat->nodetree, sock),
            std::string("Unbaked linked input: ") + sock->name);
    bNodeSocket *ref = socket(reference, sock->identifier);
    if (sock->type == SOCK_FLOAT) {
      float value = static_cast<bNodeSocketValueFloat *>(sock->default_value)->value;
      float other = static_cast<bNodeSocketValueFloat *>(ref->default_value)->value;
      require(std::fabs(value - other) < 1e-6f,
              std::string("Materials differ in unbaked input: ") + sock->name);
      if (STREQ(sock->identifier, "Transmission") || STREQ(sock->identifier, "Subsurface")) {
        require(value == 0.0f, "Transmission and subsurface materials are not supported yet");
      }
    }
    else if (sock->type == SOCK_RGBA) {
      float *a = static_cast<bNodeSocketValueRGBA *>(sock->default_value)->value;
      float *b = static_cast<bNodeSocketValueRGBA *>(ref->default_value)->value;
      for (int i = 0; i < 4; i++) {
        require(std::fabs(a[i] - b[i]) < 1e-6f,
                std::string("Materials differ in unbaked input: ") + sock->name);
      }
    }
    else if (sock->type == SOCK_VECTOR) {
      float *a = static_cast<bNodeSocketValueVector *>(sock->default_value)->value;
      float *b = static_cast<bNodeSocketValueVector *>(ref->default_value)->value;
      for (int i = 0; i < 3; i++) {
        require(std::fabs(a[i] - b[i]) < 1e-6f,
                std::string("Materials differ in unbaked input: ") + sock->name);
      }
    }
  }
  require(shader->custom1 == reference->custom1 && shader->custom2 == reference->custom2,
          "Principled distribution/subsurface methods must match");
  const bool has_source_uv = CustomData_get_render_layer_index(&mesh->ldata, CD_MLOOPUV) >= 0;
  /* Conservative first version: only static input graphs whose evaluation is
   * meaningful in both Cycles and the game. Never silently bake game-only nodes. */
  for (bNode *n = static_cast<bNode *>(mat->nodetree->nodes.first); n; n = n->next) {
    require(!n->id || !BKE_animdata_from_id(n->id), "Animated node data cannot be baked to a static atlas");
    switch (n->type) {
      case SH_NODE_OUTPUT_MATERIAL:
      case SH_NODE_BSDF_PRINCIPLED:
      case SH_NODE_TEX_IMAGE:
      case SH_NODE_UVMAP:
      case SH_NODE_TEX_COORD:
      case SH_NODE_MAPPING:
      case SH_NODE_NORMAL_MAP:
      case SH_NODE_BUMP:
      case SH_NODE_RGB:
      case SH_NODE_VALUE:
      case SH_NODE_MATH:
      case SH_NODE_VECT_MATH:
      case SH_NODE_MIX_RGB:
      case SH_NODE_VALTORGB:
      case SH_NODE_TEX_NOISE:
      case SH_NODE_TEX_VORONOI:
      case SH_NODE_TEX_MUSGRAVE:
      case SH_NODE_TEX_WAVE:
      case SH_NODE_TEX_MAGIC:
      case SH_NODE_TEX_GRADIENT:
      case SH_NODE_TEX_CHECKER:
      case SH_NODE_TEX_BRICK:
        break;
      default:
        throw std::runtime_error(std::string("Unsupported node in material ") +
                                 (mat->id.name + 2) + ": " + n->name);
    }
    if (n->type == SH_NODE_TEX_IMAGE) {
      require(has_source_uv || input_link(mat->nodetree, socket(n, "Vector")),
              "Image texture has no source UV; create a UV map or connect explicit coordinates");
      Image *image = reinterpret_cast<Image *>(n->id);
      require(image && image->source != IMA_SRC_MOVIE && image->source != IMA_SRC_SEQUENCE,
              "Missing or animated image texture");
      void *lock;
      ImBuf *ibuf = BKE_image_acquire_ibuf(image, nullptr, &lock);
      const bool valid = ibuf && (ibuf->rect || ibuf->rect_float);
      BKE_image_release_ibuf(image, ibuf, lock);
      require(valid, std::string("Cannot load source image: ") + (image->id.name + 2));
    }
    if (n->type == SH_NODE_UVMAP || n->type == SH_NODE_NORMAL_MAP) {
      const char *name = n->type == SH_NODE_UVMAP ?
          static_cast<NodeShaderUVMap *>(n->storage)->uv_map :
          static_cast<NodeShaderNormalMap *>(n->storage)->uv_map;
      if (n->type == SH_NODE_UVMAP || n->custom1 == SHD_SPACE_TANGENT) {
        require(name[0] ? CustomData_get_layer_named(&mesh->ldata, CD_MLOOPUV, name) != nullptr : has_source_uv,
                std::string("Missing source UV for node: ") + n->name);
      }
    }
    if (n->type == SH_NODE_TEX_COORD) {
      for (bNodeLink *link = static_cast<bNodeLink *>(mat->nodetree->links.first); link; link = link->next) {
        if (link->fromnode == n) {
          require(STREQ(link->fromsock->identifier, "UV") || STREQ(link->fromsock->identifier, "Generated"),
                  "This version supports only UV and Generated texture coordinates");
          require(!STREQ(link->fromsock->identifier, "UV") || has_source_uv,
                  "Texture Coordinate UV has no source render UV");
        }
      }
    }
  }
}

void update_object(Main *main, Object *ob)
{
  BKE_mesh_tessface_clear(static_cast<Mesh *>(ob->data));
  BKE_object_free_derived_caches(ob);
  DAG_id_tag_update(&ob->id, OB_RECALC_DATA);
  DAG_relations_tag_update(main);
}

void pack_uv(Mesh *mesh, Object *ob, int size, int margin)
{
  char path[FILE_MAX];
  BLI_strncpy(path, BKE_appdir_program_path(), sizeof(path));
  BLI_parent_dir(path);
#ifdef _WIN32
  BLI_path_append(path, sizeof(path), "ae_uvatlas.dll");
#else
  BLI_path_append(path, sizeof(path), "libae_uvatlas.so");
#endif
  DynamicLibrary *lib = BLI_dynlib_open(path);
  require(lib != nullptr, "Missing ae_uvatlas library beside the executable");
  struct LibraryGuard {
    DynamicLibrary *lib;
    ~LibraryGuard() { BLI_dynlib_close(lib); }
  } guard{lib};
  using Pack = int (*)(int, const int *, const float *, const int *, const unsigned int *,
                       int, int, int, float *);
  Pack pack = reinterpret_cast<Pack>(BLI_dynlib_find_symbol(lib, "ae_uvatlas"));
  require(pack != nullptr, "ae_uvatlas has no compatible entry point");
  const int triangles = mesh->totloop - 2 * mesh->totpoly;
  require(triangles > 0, "Mesh has no triangles");
  std::vector<MLoopTri> tris(triangles);
  BKE_mesh_recalc_looptri(mesh->mloop, mesh->mpoly, mesh->mvert,
                         mesh->totloop, mesh->totpoly, tris.data());
  std::vector<float> positions(mesh->totvert * 3);
  std::vector<unsigned int> indices(triangles * 3);
  std::vector<float> output(triangles * 6);
  for (int i = 0; i < mesh->totvert; i++) {
    mul_v3_mat3_m4v3(&positions[i * 3], ob->obmat, mesh->mvert[i].co);
  }
  for (int i = 0; i < triangles; i++) {
    for (int j = 0; j < 3; j++) {
      indices[i * 3 + j] = mesh->mloop[tris[i].tri[j]].v;
    }
  }
  int vertices = mesh->totvert;
  require(pack(1, &vertices, positions.data(), &triangles, indices.data(),
               size, margin, 0, output.data()) == 0, "UV atlas packing failed");
  MLoopUV *uv = static_cast<MLoopUV *>(CustomData_add_layer_named(
      &mesh->ldata, CD_MLOOPUV, CD_CALLOC, nullptr, mesh->totloop, atlas_uv));
  require(uv != nullptr, "Cannot create atlas UV layer");
  CustomData_add_layer_named(&mesh->pdata, CD_MTEXPOLY, CD_CALLOC, nullptr, mesh->totpoly, atlas_uv);
  std::vector<bool> seen(mesh->totloop, false);
  for (int i = 0; i < triangles; i++) {
    for (int j = 0; j < 3; j++) {
      int loop = tris[i].tri[j];
      const float *corner = &output[(i * 3 + j) * 2];
      require(std::isfinite(corner[0]) && std::isfinite(corner[1]) &&
                  corner[0] >= 0 && corner[0] <= 1 && corner[1] >= 0 && corner[1] <= 1,
              "Packed UV outside the atlas");
      if (seen[loop]) {
        require(std::fabs(uv[loop].uv[0] - corner[0]) < 1e-5f &&
                    std::fabs(uv[loop].uv[1] - corner[1]) < 1e-5f,
                "Atlas needs a seam inside an ngon; triangulate that face first");
      }
      copy_v2_v2(uv[loop].uv, corner);
      seen[loop] = true;
    }
  }
  BKE_mesh_update_customdata_pointers(mesh, false);
  CustomData_set_layer_active_index(&mesh->ldata, CD_MLOOPUV,
      CustomData_get_named_layer_index(&mesh->ldata, CD_MLOOPUV, atlas_uv));
  CustomData_set_layer_active_index(&mesh->pdata, CD_MTEXPOLY,
      CustomData_get_named_layer_index(&mesh->pdata, CD_MTEXPOLY, atlas_uv));
}

struct StageMaterial {
  Material *material;
  bNode *shader, *output, *target, *emission;
};

struct SavedSelection {
  Base *base;
  int base_flags, object_flags;
};

void evaluate_scene(Main *main, Scene *scene)
{
  EvaluationContext eval = {};
  eval.mode = DAG_EVAL_VIEWPORT;
  eval.ctime = float(scene->r.cfra);
  BKE_scene_update_tagged(&eval, main, scene);
}

/* RAII owns only data created by this execution. Existing IDs are never removed. */
struct AtlasTransaction {
  Main *main;
  Scene *scene;
  Object *ob;
  Mesh *source, *work = nullptr;
  Material **object_materials;
  char *object_matbits;
  short slots, active_slot;
  RenderData render;
  PointerRNA cycles;
  int samples, device;
  std::vector<SavedSelection> selection;
  std::vector<StageMaterial> materials;
  std::vector<Image *> images;
  Material *result = nullptr;
  bool applied = false;

  AtlasTransaction(bContext *C)
      : main(CTX_data_main(C)), scene(CTX_data_scene(C)), ob(CTX_data_active_object(C)),
        source(static_cast<Mesh *>(ob->data)), object_materials(ob->mat),
        object_matbits(ob->matbits), slots(ob->totcol), active_slot(ob->actcol), render(scene->r)
  {
    PointerRNA ptr;
    RNA_id_pointer_create(&scene->id, &ptr);
    cycles = RNA_pointer_get(&ptr, "cycles");
    require(cycles.data != nullptr, "Enable the Cycles addon before baking an atlas");
    samples = RNA_int_get(&cycles, "samples");
    device = RNA_enum_get(&cycles, "device");
    for (Base *base = static_cast<Base *>(scene->base.first); base; base = base->next) {
      selection.push_back({base, base->flag, base->object->flag});
    }
  }

  void restore_object()
  {
    if (ob->mat != object_materials) {
      MEM_freeN(ob->mat);
      MEM_freeN(ob->matbits);
    }
    ob->mat = object_materials;
    ob->matbits = object_matbits;
    ob->totcol = slots;
    ob->actcol = active_slot;
    ob->data = source;
    update_object(main, ob);
  }

  ~AtlasTransaction()
  {
    if (!applied) {
      restore_object();
    }
    scene->r = render;
    RNA_int_set(&cycles, "samples", samples);
    RNA_enum_set(&cycles, "device", device);
    for (auto &entry : selection) {
      entry.base->flag = entry.base_flags;
      entry.base->object->flag = entry.object_flags;
    }
    for (auto &entry : materials) {
      BKE_libblock_free(main, entry.material);
    }
    if (!applied) {
      if (result) BKE_libblock_free(main, result);
      if (work) BKE_libblock_free(main, work);
      for (Image *image : images) BKE_libblock_free(main, image);
    }
  }
};

void stage_materials(bContext *C, AtlasTransaction &tx)
{
  tx.work = BKE_mesh_copy(tx.main, tx.source);
  for (int i = 0; i < tx.slots; i++) {
    Material *copy = BKE_material_copy(tx.main, give_current_material(tx.ob, i + 1));
    bNode *out;
    bNode *shader = surface_shader(copy, &out);
    tx.materials.push_back({copy, shader, out, nullptr, nullptr});
    StageMaterial &stage = tx.materials.back();
    stage.target = nodeAddStaticNode(C, copy->nodetree, SH_NODE_TEX_IMAGE);
    nodeSetActive(copy->nodetree, stage.target);
    stage.emission = nodeAddStaticNode(C, copy->nodetree, SH_NODE_EMISSION);
    /* A normal map with an implicit UV must keep using the source render UV. */
    int render_index = CustomData_get_render_layer_index(&tx.source->ldata, CD_MLOOPUV);
    for (bNode *n = static_cast<bNode *>(copy->nodetree->nodes.first); n; n = n->next) {
      if (n->type == SH_NODE_NORMAL_MAP && render_index >= 0) {
        NodeShaderNormalMap *normal = static_cast<NodeShaderNormalMap *>(n->storage);
        if (!normal->uv_map[0]) {
          BLI_strncpy(normal->uv_map, tx.source->ldata.layers[render_index].name, sizeof(normal->uv_map));
        }
      }
    }
  }
  tx.ob->mat = static_cast<Material **>(MEM_callocN(sizeof(Material *) * tx.slots, "Atlas overrides"));
  tx.ob->matbits = static_cast<char *>(MEM_callocN(tx.slots, "Atlas links"));
  for (int i = 0; i < tx.slots; i++) {
    tx.ob->mat[i] = tx.materials[i].material;
    tx.ob->matbits[i] = 1;
  }
  tx.ob->data = tx.work;
  for (auto &entry : tx.selection) {
    Base *base = entry.base;
    base->flag = (base->flag & ~SELECT) | (base->object == tx.ob ? SELECT : 0);
    base->object->flag = base->flag;
  }
}

void route_pass(AtlasTransaction &tx, int pass, Image *image)
{
  for (auto &stage : tx.materials) {
    bNodeTree *tree = stage.material->nodetree;
    nodeRemSocketLinks(tree, socket(stage.output, "Surface"));
    nodeRemSocketLinks(tree, socket(stage.emission, "Color"));
    if (pass < 4) {
      bNodeSocket *input = socket(stage.shader, map_inputs[pass]);
      bNodeLink *link = input_link(tree, input);
      if (link) {
        nodeAddLink(tree, link->fromnode, link->fromsock, stage.emission, socket(stage.emission, "Color"));
      }
      else {
        float *color = static_cast<bNodeSocketValueRGBA *>(socket(stage.emission, "Color")->default_value)->value;
        if (input->type == SOCK_RGBA) {
          copy_v4_v4(color, static_cast<bNodeSocketValueRGBA *>(input->default_value)->value);
        }
        else {
          float v = static_cast<bNodeSocketValueFloat *>(input->default_value)->value;
          color[0] = color[1] = color[2] = v;
          color[3] = 1;
        }
      }
      connect(tree, stage.emission, "Emission", stage.output, "Surface");
    }
    else {
      connect(tree, stage.shader, "BSDF", stage.output, "Surface");
    }
    stage.target->id = &image->id;
    id_us_plus(&image->id);
    nodeSetActive(tree, stage.target);
    ntreeUpdateTree(tx.main, tree);
    DAG_id_tag_update(&stage.material->id, 0);
  }
  update_object(tx.main, tx.ob);
  evaluate_scene(tx.main, tx.scene);
}

int start_bake_pass(bContext *C, wmOperator *op, AtlasTransaction &tx, int pass, int size,
                    int margin, int *result_out = nullptr, ReportList *reports = nullptr,
                    const bool *cancel_requested = nullptr)
{
  const float clear[4] = {0, 0, 0, 0};
  std::string name = std::string("AnastacioAtlas_") + map_names[pass];
  Image *image = BKE_image_add_generated(tx.main, size, size, name.c_str(), 32, true,
                                        IMA_GENTYPE_BLANK, clear, false);
  require(image != nullptr, "Cannot allocate atlas image");
  tx.images.push_back(image);
  /* Float bake targets are scene-linear; scalar/normal images are explicitly data.
   * EMIT passes avoid illumination and avoid the diffuse-metallic black bake trap. */
  BLI_strncpy(image->colorspace_settings.name, pass == 0 ? "Linear" : "Non-Color",
              sizeof(image->colorspace_settings.name));
  void *target_lock;
  ImBuf *target_buffer = BKE_image_acquire_ibuf(image, nullptr, &target_lock);
  if (target_buffer) {
    IMB_colormanagement_assign_float_colorspace(target_buffer, image->colorspace_settings.name);
    target_buffer->foptions.flag |= PNG_16BIT;
  }
  BKE_image_release_ibuf(image, target_buffer, target_lock);
  route_pass(tx, pass, image);
  if (cancel_requested && *cancel_requested) {
    *result_out = OPERATOR_CANCELLED;
    return OPERATOR_CANCELLED;
  }
  PointerRNA props;
  WM_operator_properties_create(&props, "OBJECT_OT_bake");
  RNA_enum_set(&props, "type", pass == 4 ? SCE_PASS_NORMAL : SCE_PASS_EMIT);
  RNA_enum_set(&props, "save_mode", R_BAKE_SAVE_INTERNAL);
  RNA_int_set(&props, "margin", margin);
  RNA_boolean_set(&props, "use_clear", true);
  RNA_boolean_set(&props, "use_selected_to_active", false);
  RNA_boolean_set(&props, "use_cage", false);
  RNA_string_set(&props, "uv_layer", atlas_uv);
  RNA_enum_set(&props, "normal_space", R_BAKE_SPACE_TANGENT);
  RNA_enum_set(&props, "normal_r", R_BAKE_POSX);
  RNA_enum_set(&props, "normal_g", R_BAKE_POSY);
  RNA_enum_set(&props, "normal_b", R_BAKE_POSZ);
  wmOperator child = {};
  child.type = WM_operatortype_find("OBJECT_OT_bake", false);
  child.ptr = &props;
  child.reports = reports ? reports : op->reports;
  const int status = result_out ? ED_object_bake_job_start(C, &child, result_out) :
                                 child.type->exec(C, &child);
  WM_operator_properties_free(&props);
  return status;
}

void finish_bake_pass(AtlasTransaction &tx, int pass, int size, int status)
{
  Image *image = tx.images.back();
  for (auto &stage : tx.materials) {
    stage.target->id = nullptr;
    id_us_min(&image->id);
  }
  require(status & OPERATOR_FINISHED, std::string("Bake failed: ") + map_names[pass]);
  void *lock;
  ImBuf *ibuf = BKE_image_acquire_ibuf(image, nullptr, &lock);
  bool covered = false, finite = ibuf && ibuf->rect_float, representable = true;
  if (finite) {
    for (int i = 0; i < size * size; i++) {
      const float *pixel = &ibuf->rect_float[i * 4];
      covered |= pixel[3] > 0.5f;
      for (int c = 0; c < 4; c++) finite &= std::isfinite(pixel[c]);
      if (pixel[3] > 0.5f) {
        for (int c = 0; c < 3; c++) {
          representable &= pixel[c] >= -1e-5f && pixel[c] <= 1.00001f;
        }
      }
    }
  }
  BKE_image_release_ibuf(image, ibuf, lock);
  require(covered && finite, std::string("Empty or invalid bake: ") + map_names[pass]);
  require(representable, std::string("Map values outside 0-1 cannot be preserved in PNG: ") + map_names[pass]);
  /* Pack as 16-bit PNG, preserving linear/data encoding with bounded quantization.
   * The API baker has already filled the gutters; never blur material maps. */
  BKE_image_memorypack(image);
  require(BKE_image_has_packedfile(image), "Cannot pack the atlas image");
}

void bake_pass(bContext *C, wmOperator *op, AtlasTransaction &tx, int pass, int size, int margin)
{
  const int status = start_bake_pass(C, op, tx, pass, size, margin);
  finish_bake_pass(tx, pass, size, status);
}

void build_result(bContext *C, AtlasTransaction &tx)
{
  tx.result = BKE_material_add(tx.main, "AnastacioAtlas");
  Material *mat = tx.result;
  mat->use_nodes = true;
  mat->game = tx.materials[0].material->game;
  mat->mode = tx.materials[0].material->mode;
  mat->mode2 = tx.materials[0].material->mode2;
  mat->constflag = tx.materials[0].material->constflag;
  mat->shade_flag = tx.materials[0].material->shade_flag;
  /* Material node trees are embedded IDs, not standalone entries in Main. */
  mat->nodetree = ntreeAddTree(nullptr, "AnastacioAtlas", "ShaderNodeTree");
  bNodeTree *tree = mat->nodetree;
  bNode *output = nodeAddStaticNode(C, tree, SH_NODE_OUTPUT_MATERIAL);
  bNode *shader = nodeAddStaticNode(C, tree, SH_NODE_BSDF_PRINCIPLED);
  shader->custom1 = tx.materials[0].shader->custom1;
  shader->custom2 = tx.materials[0].shader->custom2;
  for (bNodeSocket *sock = static_cast<bNodeSocket *>(shader->inputs.first); sock; sock = sock->next) {
    bNodeSocket *source = socket(tx.materials[0].shader, sock->identifier);
    if (sock->type == SOCK_FLOAT) {
      *static_cast<bNodeSocketValueFloat *>(sock->default_value) =
          *static_cast<bNodeSocketValueFloat *>(source->default_value);
    }
    else if (sock->type == SOCK_RGBA) {
      *static_cast<bNodeSocketValueRGBA *>(sock->default_value) =
          *static_cast<bNodeSocketValueRGBA *>(source->default_value);
    }
    else if (sock->type == SOCK_VECTOR) {
      *static_cast<bNodeSocketValueVector *>(sock->default_value) =
          *static_cast<bNodeSocketValueVector *>(source->default_value);
    }
  }
  bNode *uv = nodeAddStaticNode(C, tree, SH_NODE_UVMAP);
  BLI_strncpy(static_cast<NodeShaderUVMap *>(uv->storage)->uv_map, atlas_uv, 64);
  uv->locx = -800;
  output->locx = 500;
  shader->locx = 180;
  connect(tree, shader, "BSDF", output, "Surface");
  for (int i = 0; i < 5; i++) {
    bNode *tex = nodeAddStaticNode(C, tree, SH_NODE_TEX_IMAGE);
    tex->id = &tx.images[i]->id;
    id_us_plus(tex->id);
    tex->locx = -550;
    tex->locy = -i * 250;
    static_cast<NodeTexImage *>(tex->storage)->color_space = i == 0 ? SHD_COLORSPACE_COLOR : SHD_COLORSPACE_NONE;
    connect(tree, uv, "UV", tex, "Vector");
    if (i < 4) {
      connect(tree, tex, "Color", shader, map_inputs[i]);
    }
    else {
      bNode *normal = nodeAddStaticNode(C, tree, SH_NODE_NORMAL_MAP);
      BLI_strncpy(static_cast<NodeShaderNormalMap *>(normal->storage)->uv_map, atlas_uv, 64);
      normal->locx = -180;
      normal->locy = -600;
      connect(tree, tex, "Color", normal, "Color");
      connect(tree, normal, "Normal", shader, "Normal");
    }
  }
  ntreeUpdateTree(tx.main, tree);
  BKE_material_clear_id(tx.main, &tx.work->id, false);
  BKE_material_append_id(tx.main, &tx.work->id, mat);
  id_us_min(&mat->id); /* append now owns the new material's initial user. */
  for (Image *image : tx.images) id_us_min(&image->id); /* result texture nodes own them. */
  for (int i = 0; i < tx.work->totpoly; i++) tx.work->mpoly[i].mat_nr = 0;
  /* Commit only after every pass, packing and material construction succeeded. */
  IDProperty *properties = IDP_GetProperties(&tx.work->id, true);
  IDPropertyTemplate source_value = {};
  source_value.id = &tx.source->id;
  IDP_ReplaceInGroup(properties, IDP_New(IDP_ID, &source_value, backup_key));
  IDPropertyTemplate slot_value = {};
  slot_value.i = tx.active_slot;
  IDP_ReplaceInGroup(properties, IDP_New(IDP_INT, &slot_value, backup_slot_key));
  tx.restore_object();
  id_fake_user_set(&tx.source->id);
  id_us_min(&tx.source->id);
  tx.ob->data = tx.work;
  BKE_material_resize_object(tx.main, tx.ob, 0, true);
  BKE_material_resize_object(tx.main, tx.ob, 1, false);
  tx.ob->matbits[0] = 0;
  tx.ob->actcol = 1;
  tx.applied = true;
  update_object(tx.main, tx.ob);
}

bool atlas_poll(bContext *C)
{
  Object *ob = CTX_data_active_object(C);
  return !atlas_busy && ob && ob->type == OB_MESH && ob->mode == OB_MODE_OBJECT &&
         !ob->id.lib && !static_cast<Mesh *>(ob->data)->id.lib && !G.is_rendering;
}

Mesh *source_backup(Mesh *mesh)
{
  IDProperty *properties = IDP_GetProperties(&mesh->id, false);
  if (!properties) return nullptr;
  IDProperty *property = IDP_GetPropertyTypeFromGroup(properties, backup_key, IDP_ID);
  ID *id = property ? IDP_Id(property) : nullptr;
  return id && GS(id->name) == ID_ME && id != &mesh->id ? reinterpret_cast<Mesh *>(id) : nullptr;
}

bool restore_poll(bContext *C)
{
  if (!atlas_poll(C)) return false;
  Mesh *mesh = static_cast<Mesh *>(CTX_data_active_object(C)->data);
  Mesh *source = source_backup(mesh);
  return source && !source->id.lib;
}

int restore_exec(bContext *C, wmOperator *op)
{
  Object *ob = CTX_data_active_object(C);
  Mesh *atlas = static_cast<Mesh *>(ob->data);
  Mesh *source = source_backup(atlas);
  if (!source || source->id.lib) {
    BKE_report(op->reports, RPT_ERROR, "No local source backup recorded for this mesh");
    return OPERATOR_CANCELLED;
  }
  if (ob->modifiers.first || atlas->key) {
    BKE_report(op->reports, RPT_ERROR, "Remove modifiers and shape keys before restoring the source mesh");
    return OPERATOR_CANCELLED;
  }
  for (int i = 0; i < ob->totcol; i++) {
    if (ob->matbits && ob->matbits[i]) {
      BKE_report(op->reports, RPT_ERROR, "Use data-linked slots before restoring the source mesh");
      return OPERATOR_CANCELLED;
    }
  }
  IDProperty *slot = IDP_GetPropertyTypeFromGroup(
      IDP_GetProperties(&atlas->id, false), backup_slot_key, IDP_INT);
  const int active_slot = slot ? IDP_Int(slot) : 1;
  Main *main = CTX_data_main(C);
  /* Preserve both variants. Do not remove images/materials used by another object. */
  id_fake_user_set(&atlas->id);
  id_us_plus(&source->id);
  id_us_min(&atlas->id);
  ob->data = source;
  BKE_material_resize_object(main, ob, 0, true);
  BKE_material_resize_object(main, ob, source->totcol, false);
  for (int i = 0; i < ob->totcol; i++) ob->matbits[i] = 0;
  ob->actcol = source->totcol ? std::max(1, std::min(active_slot, int(source->totcol))) : 0;
  update_object(main, ob);
  WM_event_add_notifier(C, NC_OBJECT | ND_DRAW, ob);
  WM_event_add_notifier(C, NC_MATERIAL | ND_SHADING, nullptr);
  BKE_report(op->reports, RPT_INFO, "Source mesh restored; atlas kept as backup. Rebake lighting if baked after the atlas");
  return OPERATOR_FINISHED;
}

std::unique_ptr<AtlasTransaction> prepare_atlas(bContext *C, wmOperator *op)
{
    Scene *scene = CTX_data_scene(C);
    evaluate_scene(CTX_data_main(C), scene);
    Object *ob = CTX_data_active_object(C);
    Mesh *mesh = static_cast<Mesh *>(ob->data);
    require(scene->gm.flag & GAME_USE_SHADING_NODES, "Enable PBR Shading Nodes before baking materials");
    RenderEngineType *engine = RE_engines_find("CYCLES");
    require(engine && STREQ(engine->idname, "CYCLES"), "Enable the Cycles addon before baking an atlas");
    require(mesh->totpoly > 0 && ob->totcol > 0, "Select a mesh with materials and faces");
    require(!ob->modifiers.first && !mesh->key,
            "This version needs a mesh without modifiers or shape keys");
    require(!CustomData_get_layer_named(&mesh->ldata, CD_MLOOPUV, atlas_uv),
            "AnastacioAtlas UV already exists; restore the source mesh or rename that UV first");
    require(CustomData_number_of_layers(&mesh->ldata, CD_MLOOPUV) < 8, "No free UV layer slot");
    for (int i = 0; i < mesh->totpoly; i++) {
      require(mesh->mpoly[i].mat_nr < ob->totcol, "Face references an invalid material slot");
    }
    Material *first = give_current_material(ob, 1);
    bNode *reference = surface_shader(first);
    for (int i = 0; i < ob->totcol; i++) {
      require(!ob->matbits || !ob->matbits[i],
              "Use data-linked material slots so the source mesh backup remains complete");
      Material *mat = give_current_material(ob, i + 1);
      try {
        validate_material(mat, reference, mesh);
        require(mat->game.flag == first->game.flag &&
                    mat->game.face_orientation == first->game.face_orientation &&
                    mat->mode == first->mode && mat->mode2 == first->mode2 &&
                    mat->constflag == first->constflag && mat->shade_flag == first->shade_flag,
                "Materials have different rendering flags");
      }
      catch (const std::exception &error) {
        throw std::runtime_error(std::string(mat ? mat->id.name + 2 : "Empty slot") + ": " + error.what());
      }
    }
    const int size = RNA_int_get(op->ptr, "resolution");
    const int margin = RNA_int_get(op->ptr, "margin");
    require((size & (size - 1)) == 0, "Resolution must be a power of two");
    require(margin * 4 < size, "Margin is too large for this resolution");
    std::unique_ptr<AtlasTransaction> transaction(new AtlasTransaction(C));
    AtlasTransaction &tx = *transaction;
    stage_materials(C, tx);
    pack_uv(tx.work, ob, size, margin);
    BLI_strncpy(scene->r.engine, "CYCLES", sizeof(scene->r.engine));
    RNA_int_set(&tx.cycles, "samples", RNA_int_get(op->ptr, "samples"));
    if (!RNA_boolean_get(op->ptr, "use_configured_device")) {
      RNA_enum_set_identifier(C, &tx.cycles, "device", "CPU");
    }
    return transaction;
}

struct AtlasModal {
  std::unique_ptr<AtlasTransaction> tx;
  wmWindowManager *wm = nullptr;
  wmWindow *window = nullptr;
  wmTimer *timer = nullptr;
  ReportList reports = {};
  int size = 0, margin = 0, pass = 0, result = OPERATOR_RUNNING_MODAL;
  bool cancelled = false, locked_before = false;

  AtlasModal() { BKE_reports_init(&reports, RPT_STORE); }
  ~AtlasModal() { BKE_reports_clear(&reports); }
};
AtlasModal *active_atlas = nullptr;

void request_cancel(AtlasModal &state)
{
  state.cancelled = true;
  G.is_break = true;
  WM_jobs_stop(state.wm, state.tx->scene, nullptr);
}

bool cancel_poll(bContext *) { return active_atlas != nullptr; }

int cancel_exec(bContext *, wmOperator *op)
{
  request_cancel(*active_atlas);
  BKE_report(op->reports, RPT_INFO, "Cancelling atlas; waiting for the baker to stop");
  return OPERATOR_FINISHED;
}

/* All Main/mesh/node operations stay on the UI thread. Only the existing baker
 * runs in a worker, while the interface and competing atlas operators are locked. */
void modal_cleanup(bContext *C, wmOperator *op)
{
  AtlasModal *state = static_cast<AtlasModal *>(op->customdata);
  if (!state) return;
  Scene *scene = state->tx->scene;
  if (WM_jobs_test(state->wm, scene, WM_JOB_TYPE_OBJECT_BAKE)) {
    G.is_break = true;
    WM_jobs_kill_type(state->wm, scene, WM_JOB_TYPE_OBJECT_BAKE);
  }
  if (state->timer) WM_event_remove_timer(state->wm, state->window, state->timer);
  const bool locked_before = state->locked_before;
  wmWindowManager *wm = state->wm;
  wmWindow *window = state->window;
  active_atlas = nullptr;
  delete state; /* Rollback only after the job has finished/joined. */
  op->customdata = nullptr;
  atlas_busy = false;
  G.is_break = false;
  WM_set_locked_interface(wm, locked_before);
  WM_progress_clear(window);
  WM_event_add_notifier(C, NC_OBJECT | ND_DRAW, CTX_data_active_object(C));
  WM_event_add_notifier(C, NC_MATERIAL | ND_SHADING, nullptr);
}

void modal_start_pass(bContext *C, wmOperator *op, AtlasModal &state)
{
  state.result = OPERATOR_RUNNING_MODAL;
  printf("Anastacio Material Atlas: baking %s (%d/5), Escape cancels\n",
         map_names[state.pass], state.pass + 1);
  fflush(stdout);
  const int status = start_bake_pass(C, op, *state.tx, state.pass, state.size,
                                    state.margin, &state.result, &state.reports, &state.cancelled);
  require((status & OPERATOR_RUNNING_MODAL) || state.cancelled, "Cannot start atlas bake job");
}

int atlas_async_exec(bContext *C, wmOperator *op)
{
  try {
    std::unique_ptr<AtlasModal> state(new AtlasModal());
    state->tx = prepare_atlas(C, op);
    state->wm = CTX_wm_manager(C);
    state->window = CTX_wm_window(C);
    state->locked_before = state->wm->is_interface_locked;
    state->size = RNA_int_get(op->ptr, "resolution");
    state->margin = RNA_int_get(op->ptr, "margin");
    state->timer = WM_event_add_timer(state->wm, state->window, TIMER, 0.1);
    require(state->timer != nullptr, "Cannot create atlas bake timer");
    op->customdata = state.release();
    active_atlas = static_cast<AtlasModal *>(op->customdata);
    atlas_busy = true;
    WM_set_locked_interface(CTX_wm_manager(C), true);
    modal_start_pass(C, op, *static_cast<AtlasModal *>(op->customdata));
    WM_event_add_modal_handler(C, op);
    return OPERATOR_RUNNING_MODAL;
  }
  catch (const std::exception &error) {
    modal_cleanup(C, op);
    BKE_report(op->reports, RPT_ERROR, error.what());
    return OPERATOR_CANCELLED;
  }
}

int atlas_modal(bContext *C, wmOperator *op, const wmEvent *event)
{
  AtlasModal *state = static_cast<AtlasModal *>(op->customdata);
  if (event->type == ESCKEY && event->val == KM_PRESS) {
    request_cancel(*state);
    BKE_report(op->reports, RPT_INFO, "Cancelling atlas; waiting for the baker to stop");
    return OPERATOR_RUNNING_MODAL;
  }
  if (event->type != TIMER || event->customdata != state->timer) {
    /* Job timers must reach WM, but edits must not reach scene/UI handlers. */
    return event->type == TIMERJOBS ? OPERATOR_PASS_THROUGH : OPERATOR_RUNNING_MODAL;
  }
  if (WM_jobs_test(state->wm, state->tx->scene, WM_JOB_TYPE_OBJECT_BAKE)) {
    return OPERATOR_RUNNING_MODAL;
  }
  try {
    for (Report *report = static_cast<Report *>(state->reports.list.first); report; report = report->next) {
      BKE_report(op->reports, ReportType(report->type), report->message);
    }
    BKE_reports_clear(&state->reports);
    if (state->cancelled || G.is_break || state->result == OPERATOR_CANCELLED) {
      modal_cleanup(C, op);
      BKE_report(op->reports, RPT_INFO, "Atlas cancelled; original mesh and settings restored");
      return OPERATOR_CANCELLED;
    }
    finish_bake_pass(*state->tx, state->pass, state->size, state->result);
    if (++state->pass < 5) {
      modal_start_pass(C, op, *state);
      return OPERATOR_RUNNING_MODAL;
    }
    build_result(C, *state->tx);
    BKE_report(op->reports, RPT_INFO, "Atlas complete: 5 packed maps; source mesh kept as backup");
    modal_cleanup(C, op);
    return OPERATOR_FINISHED;
  }
  catch (const std::exception &error) {
    modal_cleanup(C, op);
    BKE_report(op->reports, RPT_ERROR, error.what());
    return OPERATOR_CANCELLED;
  }
}

void atlas_cancel(bContext *C, wmOperator *op)
{
  modal_cleanup(C, op);
}

int atlas_exec(bContext *C, wmOperator *op)
{
  if (!G.background && CTX_wm_window(C) && RNA_boolean_get(op->ptr, "use_async")) {
    return atlas_async_exec(C, op);
  }
  try {
    std::unique_ptr<AtlasTransaction> transaction = prepare_atlas(C, op);
    AtlasTransaction &tx = *transaction;
    const int size = RNA_int_get(op->ptr, "resolution");
    const int margin = RNA_int_get(op->ptr, "margin");
    for (int pass = 0; pass < 5; pass++) {
      if (!G.background && CTX_wm_window(C)) WM_progress_set(CTX_wm_window(C), float(pass) / 5.0f);
      printf("Anastacio Material Atlas: baking %s (%d/5)\n", map_names[pass], pass + 1);
      bake_pass(C, op, tx, pass, size, margin);
    }
    build_result(C, tx);
    BKE_reportf(op->reports, RPT_INFO, "Atlas complete: 5 maps, %dx%d; original mesh kept as %s",
                size, size, tx.source->id.name + 2);
  }
  catch (const std::exception &error) {
    if (!G.background && CTX_wm_window(C)) WM_progress_clear(CTX_wm_window(C));
    BKE_report(op->reports, RPT_ERROR, error.what());
    WM_event_add_notifier(C, NC_OBJECT | ND_DRAW, CTX_data_active_object(C));
    return OPERATOR_CANCELLED;
  }
  if (!G.background && CTX_wm_window(C)) WM_progress_clear(CTX_wm_window(C));
  WM_event_add_notifier(C, NC_OBJECT | ND_DRAW, CTX_data_active_object(C));
  WM_event_add_notifier(C, NC_MATERIAL | ND_SHADING, nullptr);
  return OPERATOR_FINISHED;
}

int atlas_invoke(bContext *C, wmOperator *op, const wmEvent *)
{
  RNA_boolean_set(op->ptr, "use_async", true);
  return WM_operator_props_dialog_popup(C, op, 420, 320);
}
}  // namespace

extern "C" void MATERIAL_OT_anastacio_atlas_bake(wmOperatorType *ot)
{
  ot->name = "Bake Material Atlas";
  ot->idname = "MATERIAL_OT_anastacio_atlas_bake";
  ot->description = "Bake opaque Principled materials to one PBR material, keeping source mesh and Lightmap UV";
  ot->poll = atlas_poll;
  ot->exec = atlas_exec;
  ot->invoke = atlas_invoke;
  ot->modal = atlas_modal;
  ot->cancel = atlas_cancel;
  ot->flag = OPTYPE_REGISTER | OPTYPE_UNDO | OPTYPE_LOCK_BYPASS;
  PropertyRNA *async = RNA_def_boolean(ot->srna, "use_async", false, "Cancellable Bake",
                                      "Use native bake jobs in a windowed editor; Escape cancels");
  RNA_def_property_flag(async, PropertyFlag(PROP_HIDDEN | PROP_SKIP_SAVE));
  RNA_def_int(ot->srna, "resolution", 1024, 64, 4096, "Resolution", "Power of two, in pixels", 64, 4096);
  RNA_def_int(ot->srna, "margin", 4, 1, 64, "Margin", "Padding between UV islands, in pixels", 1, 32);
  RNA_def_int(ot->srna, "samples", 32, 1, 1024, "Samples", "Cycles samples per bake", 1, 128);
  RNA_def_boolean(ot->srna, "use_configured_device", false, "Use Configured Cycles Device",
                  "Use the current Cycles CPU/GPU configuration; disabled uses CPU");
}

extern "C" void MATERIAL_OT_anastacio_atlas_restore(wmOperatorType *ot)
{
  ot->name = "Restore Original Materials";
  ot->idname = "MATERIAL_OT_anastacio_atlas_restore";
  ot->description = "Restore the recorded source mesh and materials, keeping the atlas as a backup; later mesh edits are not transferred";
  ot->poll = restore_poll;
  ot->exec = restore_exec;
  ot->flag = OPTYPE_REGISTER | OPTYPE_UNDO;
}

extern "C" void MATERIAL_OT_anastacio_atlas_cancel(wmOperatorType *ot)
{
  ot->name = "Cancel Material Atlas";
  ot->idname = "MATERIAL_OT_anastacio_atlas_cancel";
  ot->description = "Request cancellation of the running atlas and restore its original mesh and settings";
  ot->poll = cancel_poll;
  ot->exec = cancel_exec;
  ot->flag = OPTYPE_LOCK_BYPASS;
}
