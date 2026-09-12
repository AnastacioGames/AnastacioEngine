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
 * BKE_bad_level_calls function stubs
 */

/** \file blenderplayer/bad_level_call_stubs/stubs.c
 *  \ingroup blc
 */

#ifdef WITH_GAMEENGINE

#define ASSERT_STUBS 0
#if ASSERT_STUBS
#  include <assert.h>
#  define STUB_ASSERT(x) (assert(x))
#else
#  define STUB_ASSERT(x)
#endif


struct ARegion;
struct ARegionType;
struct BMEditMesh;
struct Base;
struct bContext;
struct BoundBox;
struct Brush;
struct CSG_FaceIteratorDescriptor;
struct CSG_VertexIteratorDescriptor;
struct ChannelDriver;
struct ColorBand;
struct Context;
struct Curve;
struct CurveMapping;
struct DerivedMesh;
struct EditBone;
struct EnvMap;
struct FCurve;
struct Heap;
struct HeapNode;
struct ID;
struct ImBuf;
struct Image;
struct ImageUser;
struct KeyingSet;
struct KeyingSetInfo;
struct MCol;
struct MTex;
struct Main;
struct Mask;
struct Material;
struct MenuType;
struct Mesh;
struct MetaBall;
struct Lattice;
struct ModifierData;
struct MovieClip;
struct MultiresModifierData;
struct HookModifierData;
struct NodeBlurData;
struct Nurb;
struct Object;
struct PBVHNode;
struct PyObject;
struct Render;
struct RenderEngine;
struct RenderEngineType;
struct RenderLayer;
struct RenderResult;
struct Scene;
struct Scene;
struct ScrArea;
struct SculptSession;
struct ShadeInput;
struct ShadeResult;
struct SpaceButs;
struct SpaceClip;
struct SpaceImage;
struct SpaceNode;
struct Tex;
struct TexResult;
struct Text;
struct ToolSettings;
struct View2D;
struct View3D;
struct bAction;
struct bArmature;
struct bConstraint;
struct bConstraintOb;
struct bConstraintTarget;
struct bContextDataResult;
struct bGPDlayer;
struct bNode;
struct bNodeType;
struct bNodeSocket;
struct bNodeSocketType;
struct bNodeTree;
struct bNodeTreeType;
struct bPoseChannel;
struct bPythonConstraint;
struct bTheme;
struct uiLayout;
struct wmEvent;
struct wmKeyConfig;
struct wmKeyMap;
struct wmOperator;
struct wmOperatorType;
struct wmWindow;
struct wmWindowManager;


/* -------------------------------------------------------------------- */
/* Declarations */

/* may cause troubles... enable for now so args match for certain */
#if 1
#if defined(__clang__)
#  pragma GCC diagnostic error "-Wmissing-prototypes"
#elif defined(__GNUC__)
#  pragma GCC diagnostic ignored "-Wmissing-prototypes"
#endif
#if defined(__GNUC__)
#  pragma GCC diagnostic ignored "-Wunused-parameter"
#endif

#include "../../intern/dualcon/dualcon.h"
#include "../../intern/elbeem/extern/elbeem.h"
#include "../blender/blenkernel/BKE_modifier.h"
#include "../blender/blenkernel/BKE_paint.h"
#include "../blender/compositor/COM_compositor.h"
#include "../blender/editors/include/ED_armature.h"
#include "../blender/editors/include/ED_anim_api.h"
#include "../blender/editors/include/ED_buttons.h"
#include "../blender/editors/include/ED_clip.h"
#include "../blender/editors/include/ED_curve.h"
#include "../blender/editors/include/ED_fileselect.h"
#include "../blender/editors/include/ED_gpencil.h"
#include "../blender/editors/include/ED_image.h"
#include "../blender/editors/include/ED_info.h"
#include "../blender/editors/include/ED_keyframes_edit.h"
#include "../blender/editors/include/ED_keyframing.h"
#include "../blender/editors/include/ED_lattice.h"
#include "../blender/editors/include/ED_mball.h"
#include "../blender/editors/include/ED_mesh.h"
#include "../blender/editors/include/ED_node.h"
#include "../blender/editors/include/ED_object.h"
#include "../blender/editors/include/ED_particle.h"
#include "../blender/editors/include/ED_render.h"
#include "../blender/editors/include/ED_screen.h"
#include "../blender/editors/include/ED_space_api.h"
#include "../blender/editors/include/ED_text.h"
#include "../blender/editors/include/ED_transform.h"
#include "../blender/editors/include/ED_transform_snap_object_context.h"
#include "../blender/editors/include/ED_uvedit.h"
#include "../blender/editors/include/ED_view3d.h"
#include "../blender/editors/include/UI_interface.h"
#include "../blender/editors/include/UI_interface_icons.h"
#include "../blender/editors/include/UI_resources.h"
#include "../blender/editors/include/UI_view2d.h"
#include "../blender/freestyle/FRS_freestyle.h"
#include "../blender/python/BPY_extern.h"
#include "../blender/render/extern/include/RE_engine.h"
#include "../blender/render/extern/include/RE_pipeline.h"
#include "../blender/render/extern/include/RE_render_ext.h"
#include "../blender/render/extern/include/RE_shader_ext.h"
#include "../blender/windowmanager/WM_api.h"


/* -------------------------------------------------------------------- */
/* Externs
 * (ideally we wouldn't have _any_ but we can't include all directly)
 */

/* bpy_operator_wrap.h */
extern void macro_wrapper(struct wmOperatorType *ot, void *userdata);
extern void operator_wrapper(struct wmOperatorType *ot, void *userdata);
/* bpy_rna.h */
extern bool pyrna_id_FromPyObject(struct PyObject *obj, struct ID **id);
extern const char *BPY_app_translations_py_pgettext(const char *msgctxt, const char *msgid);
extern const char *BPY_app_translations_py_pgettext(const char *msgctxt, const char *msgid);
extern struct PyObject *pyrna_id_CreatePyObject(struct ID *id);
extern bool pyrna_id_CheckPyObject(struct PyObject *obj);
/* bpy_interface.c */
#ifndef WITH_BLENDER /* duplicate: real impl now linked (BPY_string_is_keyword) */
bool BPY_string_is_keyword(const char *str) { return false; }
#endif

#endif
/* end declarations */


/* -------------------------------------------------------------------- */
/* Return Macro's */

#include <string.h>  /* memset */
#define RET_NULL {STUB_ASSERT(0); return (void *) NULL;}
#define RET_ZERO {STUB_ASSERT(0); return 0;}
#define RET_MINUSONE {STUB_ASSERT(0); return -1;}
#define RET_STRUCT(t) {struct t v; STUB_ASSERT(0); memset(&v, 0, sizeof(v)); return v;}
#define RET_ARG(arg) {STUB_ASSERT(0); return arg; }
#define RET_NONE {STUB_ASSERT(0);}


/* -------------------------------------------------------------------- */
/* Stubs */

#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_view3d_always_render_update) */
void ED_view3d_always_render_update(struct wmWindowManager *wm) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateScreenTabs) */
void uiTemplateScreenTabs(struct uiLayout *layout, struct bContext *C) RET_NONE
#endif

/*new render funcs */
#ifndef WITH_BLENDER /* duplicate: real impl now linked (EDBM_selectmode_set) */
void EDBM_selectmode_set(struct BMEditMesh *em) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (EDBM_mesh_load) */
void EDBM_mesh_load(struct Main *bmain, struct Object *ob) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (EDBM_mesh_make) */
void EDBM_mesh_make(struct Object *ob, const int select_mode, const bool use_key_index) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (EDBM_mesh_normals_update) */
void EDBM_mesh_normals_update(struct BMEditMesh *em) RET_NONE
#endif
void *g_system;
#ifndef WITH_BLENDER /* duplicate: real impl now linked (EDBM_uv_check) */
bool EDBM_uv_check(struct BMEditMesh *em) RET_ZERO
#endif

#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_RenderLayerGetPass) */
float *RE_RenderLayerGetPass(volatile struct RenderLayer *rl, const char *name, const char *viewname) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_filter_value) */
float RE_filter_value(int type, float x) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_GetRenderLayer) */
struct RenderLayer *RE_GetRenderLayer(struct RenderResult *rr, const char *name) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_texture_rng_init) */
void RE_texture_rng_init() RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_texture_rng_exit) */
void RE_texture_rng_exit() RET_NONE
#endif

#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_layers_have_name) */
bool RE_layers_have_name(struct RenderResult *result) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_engine_active_view_get) */
const char *RE_engine_active_view_get(struct RenderEngine *engine) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_engine_active_view_set) */
void RE_engine_active_view_set(struct RenderEngine *engine, const char *viewname) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_engine_get_camera_model_matrix) */
void RE_engine_get_camera_model_matrix(struct RenderEngine *engine, struct Object *camera, bool use_spherical_stereo, float *r_modelmat) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_engine_get_camera_shift_x) */
float RE_engine_get_camera_shift_x(struct RenderEngine *engine, struct Object *camera, bool use_spherical_stereo) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_engine_get_spherical_stereo) */
bool RE_engine_get_spherical_stereo(struct RenderEngine *engine, struct Object *camera) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_SetActiveRenderView) */
void RE_SetActiveRenderView(struct Render *re, const char *viewname) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_engine_update_render_passes) */
void RE_engine_update_render_passes(struct RenderEngine *engine, struct Scene *scene, struct SceneRenderLayer *srl,
                                    update_render_passes_cb_t callback, void *callback_data) RET_NONE
#endif

#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_pass_find_by_name) */
struct RenderPass *RE_pass_find_by_name(volatile struct RenderLayer *rl, const char *name, const char *viewname) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_pass_find_by_type) */
struct RenderPass *RE_pass_find_by_type(volatile struct RenderLayer *rl, int passtype, const char *viewname) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_HasCombinedLayer) */
bool RE_HasCombinedLayer(RenderResult *res) RET_ZERO
#endif

/* imagetexture.c stub */
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ibuf_sample) */
void ibuf_sample(struct ImBuf *ibuf, float fx, float fy, float dx, float dy, float *result) RET_NONE
#endif

/* Freestyle */
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_texture_context_check_linestyle) */
bool ED_texture_context_check_linestyle(const struct bContext *C) RET_ZERO
#endif
void FRS_free_view_map_cache(void) RET_NONE

/* texture.c */
#ifndef WITH_BLENDER /* duplicate: real impl now linked (multitex_ext) */
int	multitex_ext(struct Tex *tex, float texvec[3], float dxt[3], float dyt[3], int osatex, struct TexResult *texres, short thread, struct ImagePool *pool, bool scene_color_manage, const bool skip_load_image) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (multitex_ext_safe) */
int multitex_ext_safe(struct Tex *tex, float texvec[3], struct TexResult *texres, struct ImagePool *pool, bool scene_color_manage, const bool skip_load_image) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (multitex_nodes) */
int multitex_nodes(struct Tex *tex, float texvec[3], float dxt[3], float dyt[3], int osatex, struct TexResult *texres, const short thread, short which_output, struct ShadeInput *shi, struct MTex *mtex, struct ImagePool *pool) RET_ZERO
#endif

#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_sample_material_init) */
struct Material *RE_sample_material_init(struct Material *orig_mat, struct Scene *scene) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_sample_material_free) */
void RE_sample_material_free(struct Material *mat) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_sample_material_color) */
void RE_sample_material_color(
        struct Material *mat, float color[3], float *alpha, const float volume_co[3], const float surface_co[3],
        int tri_index, struct DerivedMesh *orcoDm, struct Object *ob) RET_NONE
#endif
/* nodes */
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_GetRender) */
struct Render *RE_GetRender(const char *name) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_GetSceneRender) */
struct Render *RE_GetSceneRender(const struct Scene *scene) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_GetCamera) */
struct Object *RE_GetCamera(struct Render *re) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_lamp_get_data) */
float RE_lamp_get_data(struct ShadeInput *shi, struct Object *lamp_obj, float col[4], float lv[3], float *dist, float shadow[4]) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_object_instance_get_matrix) */
const float (*RE_object_instance_get_matrix(struct ObjectInstanceRen *obi, int matrix_id))[4] RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_render_current_get_matrix) */
const float (*RE_render_current_get_matrix(int matrix_id))[4] RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_object_instance_get_object_pass_index) */
float RE_object_instance_get_object_pass_index(struct ObjectInstanceRen *obi) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_object_instance_get_random_id) */
float RE_object_instance_get_random_id(struct ObjectInstanceRen *obi) RET_ZERO
#endif

/* blenkernel */
#ifndef WITH_BLENDER /* duplicate: real impl now linked (BKE_paint_proj_mesh_data_check) */
bool BKE_paint_proj_mesh_data_check(struct Scene *scene, struct Object *ob, bool *uvs, bool *mat, bool *tex, bool *stencil) RET_ZERO
#endif

/* render */
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_FreeRenderResult) */
void RE_FreeRenderResult(struct RenderResult *res) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_FreeAllRenderResults) */
void RE_FreeAllRenderResults(void) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_MultilayerConvert) */
struct RenderResult *RE_MultilayerConvert(void *exrhandle, const char *colorspace, bool predivide, int rectx, int recty) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_GetScene) */
struct Scene *RE_GetScene(struct Render *re) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_Database_Free) */
void RE_Database_Free(struct Render *re) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_FreeRender) */
void RE_FreeRender(struct Render *re) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_DataBase_GetView) */
void RE_DataBase_GetView(struct Render *re, float mat[4][4]) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (externtex) */
int externtex(
        const struct MTex *mtex, const float vec[3], float *tin, float *tr, float *tg, float *tb, float *ta,
        const int thread, struct ImagePool *pool, const bool skip_load_image, const bool texnode_preview) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (texture_value_blend) */
float texture_value_blend(float tex, float out, float fact, float facg, int blendtype) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (texture_rgb_blend) */
void texture_rgb_blend(float in[3], const float tex[3], const float out[3], float fact, float facg, int blendtype) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (elbeemEstimateMemreq) */
double elbeemEstimateMemreq(int res, float sx, float sy, float sz, int refine, char *retstr) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_NewRender) */
struct Render *RE_NewRender(const char *name) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_NewSceneRender) */
struct Render *RE_NewSceneRender(const struct Scene *scene) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_SwapResult) */
void RE_SwapResult(struct Render *re, struct RenderResult **rr) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_BlenderFrame) */
void RE_BlenderFrame(struct Render *re, struct Main *bmain, struct Scene *scene, struct SceneRenderLayer *srl, struct Object *camera_override, unsigned int lay_override, int frame, const bool write_still) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_WriteEnvmapResult) */
bool RE_WriteEnvmapResult(struct ReportList *reports, struct Scene *scene, struct EnvMap *env, const char *relpath, const char imtype, float layout[12]) RET_ZERO
#endif

/* rna */
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_view3d_cursor3d_get) */
float *ED_view3d_cursor3d_get(struct Scene *scene, struct View3D *v3d) RET_NULL
#endif
void WM_menutype_free(void) RET_NONE
void WM_menutype_freelink(struct MenuType *mt) RET_NONE
bool WM_menutype_add(struct MenuType *mt) RET_ZERO
int WM_operator_props_dialog_popup(struct bContext *C, struct wmOperator *op, int width, int height) RET_ZERO
int WM_operator_confirm(struct bContext *C, struct wmOperator *op, const struct wmEvent *event) RET_ZERO
struct MenuType *WM_menutype_find(const char *idname, bool quiet) RET_NULL
void WM_operator_stack_clear(struct wmWindowManager *wm) RET_NONE
void WM_operator_handlers_clear(wmWindowManager *wm, struct wmOperatorType *ot) RET_NONE
bool WM_operator_is_repeat(const struct bContext *C, const struct wmOperator *op) RET_ZERO;

void WM_autosave_init(wmWindowManager *wm) RET_NONE
void WM_jobs_kill_all_except(struct wmWindowManager *wm, void *owner) RET_NONE

void WM_lib_reload(struct Library *lib, struct bContext *C, struct ReportList *reports) RET_NONE

char *WM_clipboard_text_get(bool selection, int *r_len) RET_NULL
char *WM_clipboard_text_get_firstline(bool selection, int *r_len) RET_NULL
void WM_clipboard_text_set(const char *buf, bool selection) RET_NONE

void WM_cursor_set(struct wmWindow *win, int curor) RET_NONE
void WM_cursor_modal_set(struct wmWindow *win, int curor) RET_NONE
void WM_cursor_modal_restore(struct wmWindow *win) RET_NONE
void WM_cursor_time(struct wmWindow *win, int nr) RET_NONE
void WM_cursor_warp(struct wmWindow *win, int x, int y) RET_NONE

struct wmJob *WM_jobs_get(struct wmWindowManager *wm, struct wmWindow *win, void *owner, const char *name, int flag, int job_type) RET_NULL
void WM_jobs_customdata_set(struct wmJob *job, void *customdata, void (*free)(void *)) RET_NONE
void WM_jobs_timer(struct wmJob *job, double timestep, unsigned int note, unsigned int endnote) RET_NONE

void WM_jobs_callbacks(struct wmJob *job,
                       void (*startjob)(void *, short *, short *, float *),
                       void (*initjob)(void *),
                       void (*update)(void *),
                       void (*endjob)(void *)) RET_NONE

void WM_jobs_start(struct wmWindowManager *wm, struct wmJob *job) RET_NONE
void WM_report(ReportType type, const char *message) RET_NONE

#ifdef WITH_INPUT_NDOF
    void WM_ndof_deadzone_set(float deadzone) RET_NONE
#endif

void                WM_uilisttype_init(void) RET_NONE
struct uiListType  *WM_uilisttype_find(const char *idname, bool quiet) RET_NULL
bool                WM_uilisttype_add(struct uiListType *ult) RET_ZERO
void                WM_uilisttype_freelink(struct uiListType *ult) RET_NONE
void                WM_uilisttype_free(void) RET_NONE

struct wmKeyMapItem *WM_keymap_item_find_id(struct wmKeyMap *keymap, int id) RET_NULL
struct wmKeyMapItem *WM_key_event_operator(
        const struct bContext *C, const char *opname, int opcontext,
        struct IDProperty *properties, const bool is_hotkey,
        struct wmKeyMap **r_keymap) RET_NULL
void WM_keyconfig_update(struct wmWindowManager *wm) RET_NONE

int WM_enum_search_invoke(struct bContext *C, struct wmOperator *op, const struct wmEvent *event) RET_ZERO
void WM_event_add_notifier(const struct bContext *C, unsigned int type, void *reference) RET_NONE
void WM_main_add_notifier(unsigned int type, void *reference) RET_NONE

/* -------------------------------------------------------------------- */
/* WM_api.h / WM_keymap.h stubs (bf_windowmanager not linked into RangeRuntime) */

const EnumPropertyItem *RNA_action_itemf(struct bContext *C, struct PointerRNA *ptr, struct PropertyRNA *prop, bool *r_free) RET_NULL
const EnumPropertyItem *RNA_group_itemf(struct bContext *C, struct PointerRNA *ptr, struct PropertyRNA *prop, bool *r_free) RET_NULL
const EnumPropertyItem *RNA_group_local_itemf(struct bContext *C, struct PointerRNA *ptr, struct PropertyRNA *prop, bool *r_free) RET_NULL
const EnumPropertyItem *RNA_image_itemf(struct bContext *C, struct PointerRNA *ptr, struct PropertyRNA *prop, bool *r_free) RET_NULL
const EnumPropertyItem *RNA_mask_itemf(struct bContext *C, struct PointerRNA *ptr, struct PropertyRNA *prop, bool *r_free) RET_NULL
const EnumPropertyItem *RNA_movieclip_itemf(struct bContext *C, struct PointerRNA *ptr, struct PropertyRNA *prop, bool *r_free) RET_NULL
const EnumPropertyItem *RNA_scene_itemf(struct bContext *C, struct PointerRNA *ptr, struct PropertyRNA *prop, bool *r_free) RET_NULL
const EnumPropertyItem *RNA_scene_local_itemf(struct bContext *C, struct PointerRNA *ptr, struct PropertyRNA *prop, bool *r_free) RET_NULL
const EnumPropertyItem *RNA_scene_without_active_itemf(struct bContext *C, struct PointerRNA *ptr, struct PropertyRNA *prop, bool *r_free) RET_NULL

const char *WM_bool_as_string(bool test) RET_NULL
void        WM_cursor_compatible_xy(wmWindow *win, int *x, int *y) RET_NONE
void        WM_cursor_grab_disable(struct wmWindow *win, const int mouse_ungrab_xy[2]) RET_NONE
void        WM_cursor_grab_enable(struct wmWindow *win, bool wrap, bool hide, int bounds[4]) RET_NONE
void        *WM_draw_cb_activate(
        struct wmWindow *win,
        void(*draw)(const struct wmWindow *, void *),
        void *customdata) RET_NULL
void        WM_draw_cb_exit(struct wmWindow *win, void *handle) RET_NONE
struct wmDropBox	*WM_dropbox_add(
        ListBase *lb, const char *idname, bool (*poll)(struct bContext *, struct wmDrag *, const struct wmEvent *event),
        void (*copy)(struct wmDrag *, struct wmDropBox *)) RET_NULL
ListBase	*WM_dropboxmap_find(const char *idname, int spaceid, int regionid) RET_NULL
struct wmEventHandler *WM_event_add_dropbox_handler(ListBase *handlers, ListBase *dropboxes) RET_NULL
struct wmEventHandler *WM_event_add_keymap_handler(ListBase *handlers, wmKeyMap *keymap) RET_NULL
struct wmEventHandler *WM_event_add_keymap_handler_bb(ListBase *handlers, wmKeyMap *keymap, const rcti *bb, const rcti *swinbb) RET_NULL
struct wmEventHandler *WM_event_add_keymap_handler_priority(ListBase *handlers, wmKeyMap *keymap, int priority) RET_NULL
void		WM_event_add_mousemove(const struct bContext *C) RET_NONE
struct wmTimer *WM_event_add_timer_notifier(struct wmWindowManager *wm, struct wmWindow *win, unsigned int type, double timestep) RET_NULL
struct wmEventHandler *WM_event_add_ui_handler(
        const struct bContext *C, ListBase *handlers,
        wmUIHandlerFunc ui_handle, wmUIHandlerRemoveFunc ui_remove,
        void *userdata, const char flag) RET_NULL
void				WM_event_drag_image(struct wmDrag *drag, struct ImBuf *ibuf, float scale, int sx, int sy) RET_NONE
void		WM_event_fileselect_event(struct wmWindowManager *wm, void *ophandle, int eventval) RET_NONE
void WM_event_free_ui_handler_all(
        struct bContext *C, ListBase *handlers,
        wmUIHandlerFunc ui_handle, wmUIHandlerRemoveFunc ui_remove) RET_NONE
bool        WM_event_is_ime_switch(const struct wmEvent *event) RET_ZERO
bool		WM_event_is_last_mousemove(const struct wmEvent *event) RET_ZERO
bool		WM_event_is_modal_tweak_exit(const struct wmEvent *event, int tweak_event) RET_ZERO
#ifdef WITH_INPUT_NDOF
void        WM_event_ndof_pan_get(const struct wmNDOFMotionData *ndof, float r_pan[3], const bool use_zoom) RET_NONE
void        WM_event_ndof_rotate_get(const struct wmNDOFMotionData *ndof, float r_rot[3]) RET_NONE
float       WM_event_ndof_to_axis_angle(const struct wmNDOFMotionData *ndof, float axis[3]) RET_ZERO
#endif
void WM_event_remove_area_handler(
        struct ListBase *handlers, void *area) RET_NONE
void		WM_event_remove_handlers(struct bContext *C, ListBase *handlers) RET_NONE
void		WM_event_remove_keymap_handler(ListBase *handlers, wmKeyMap *keymap) RET_NONE
void		WM_event_remove_timer_notifier(struct wmWindowManager *wm, struct wmWindow *win, struct wmTimer *timer) RET_NONE
void WM_event_remove_ui_handler(
        ListBase *handlers,
        wmUIHandlerFunc ui_handle, wmUIHandlerRemoveFunc ui_remove,
        void *userdata, const bool postpone) RET_NONE
void WM_event_set_keymap_handler_callback(
        struct wmEventHandler *handler,
        void (keymap_tag)(wmKeyMap *keymap, wmKeyMapItem *kmi, void *user_data),
        void *user_data) RET_NONE
struct wmDrag		*WM_event_start_drag(struct bContext *C, int icon, int type, void *poin, double value, unsigned int flags) RET_NULL
void        WM_event_timer_sleep(struct wmWindowManager *wm, struct wmWindow *win, struct wmTimer *timer, bool do_sleep) RET_NONE
void		WM_exit_ext			(struct bContext *C, const bool do_python) RET_NONE
void		WM_file_tag_modified(void) RET_NONE
int			WM_gesture_border_invoke	(struct bContext *C, struct wmOperator *op, const struct wmEvent *event) RET_ZERO
int			WM_gesture_border_modal	(struct bContext *C, struct wmOperator *op, const struct wmEvent *event) RET_ZERO
void		WM_gesture_border_cancel(struct bContext *C, struct wmOperator *op) RET_NONE
void		WM_gesture_circle_cancel(struct bContext *C, struct wmOperator *op) RET_NONE
int			WM_gesture_circle_invoke(struct bContext *C, struct wmOperator *op, const struct wmEvent *event) RET_ZERO
int			WM_gesture_circle_modal(struct bContext *C, struct wmOperator *op, const struct wmEvent *event) RET_ZERO
void		WM_gesture_lasso_cancel(struct bContext *C, struct wmOperator *op) RET_NONE
int			WM_gesture_lasso_invoke(struct bContext *C, struct wmOperator *op, const struct wmEvent *event) RET_ZERO
int			WM_gesture_lasso_modal(struct bContext *C, struct wmOperator *op, const struct wmEvent *event) RET_ZERO
const int (*WM_gesture_lasso_path_to_array(struct bContext *C, struct wmOperator *op, int *mcords_tot))[2] RET_NULL
void		WM_gesture_lines_cancel(struct bContext *C, struct wmOperator *op) RET_NONE
int			WM_gesture_lines_invoke(struct bContext *C, struct wmOperator *op, const struct wmEvent *event) RET_ZERO
int			WM_gesture_lines_modal(struct bContext *C, struct wmOperator *op, const struct wmEvent *event) RET_ZERO
void		WM_gesture_straightline_cancel(struct bContext *C, struct wmOperator *op) RET_NONE
int			WM_gesture_straightline_invoke(struct bContext *C, struct wmOperator *op, const struct wmEvent *event) RET_ZERO
int			WM_gesture_straightline_modal(struct bContext *C, struct wmOperator *op, const struct wmEvent *event) RET_ZERO
void		WM_gestures_remove(struct bContext *C) RET_NONE
bool		WM_is_draw_triple(struct wmWindow *win) RET_ZERO
void		WM_job_main_thread_lock_acquire(struct wmJob *job) RET_NONE
void		WM_job_main_thread_lock_release(struct wmJob *job) RET_NONE
void       *WM_jobs_customdata(struct wmWindowManager *wm, void *owner) RET_NULL
void       *WM_jobs_customdata_from_type(struct wmWindowManager *wm, int job_type) RET_NULL
void       *WM_jobs_customdata_get(struct wmJob *job) RET_NULL
bool        WM_jobs_is_running(struct wmJob *job) RET_ZERO
bool		WM_jobs_is_stopped(wmWindowManager *wm, void *owner) RET_ZERO
void		WM_jobs_kill(struct wmWindowManager *wm, void *owner, void (*startjob)(void *, short int *, short int *, float *)) RET_NONE
void		WM_jobs_kill_all(struct wmWindowManager *wm) RET_NONE
void		WM_jobs_kill_type(struct wmWindowManager *wm, void *owner, int job_type) RET_NONE
char       *WM_jobs_name(struct wmWindowManager *wm, void *owner) RET_NULL
float		WM_jobs_progress(struct wmWindowManager *wm, void *owner) RET_ZERO
double      WM_jobs_starttime(struct wmWindowManager *wm, void *owner) RET_ZERO
void		WM_jobs_stop(struct wmWindowManager *wm, void *owner, void *startjob) RET_NONE
bool        WM_jobs_test(struct wmWindowManager *wm, void *owner, int job_type) RET_ZERO
char *WM_key_event_operator_string(
        const struct bContext *C, const char *opname, int opcontext,
        struct IDProperty *properties, const bool is_strict,
        char *result, const int result_len) RET_NULL
const char *WM_key_event_string(const short type, const bool compact) RET_NULL
wmKeyMapItem *WM_keymap_add_menu(
        struct wmKeyMap *keymap, const char *idname, int type,
        int val, int modifier, int keymodifier) RET_NULL
wmKeyMapItem *WM_keymap_add_menu_pie(
        struct wmKeyMap *keymap, const char *idname, int type,
        int val, int modifier, int keymodifier) RET_NULL
wmKeyMap *WM_keymap_guess_opname(const struct bContext *C, const char *opname) RET_NULL
int         WM_keymap_item_to_string(wmKeyMapItem *kmi, const bool compact, char *result, const int result_len) RET_ZERO
wmKeyMapItem *WM_keymap_verify_item(
        struct wmKeyMap *keymap, const char *idname, int type,
        int val, int modifier, int keymodifier) RET_NULL
int			WM_menu_invoke			(struct bContext *C, struct wmOperator *op, const struct wmEvent *event) RET_ZERO
int			WM_menu_invoke_ex(struct bContext *C, struct wmOperator *op, int opcontext) RET_ZERO
bool                WM_menutype_poll(struct bContext *C, struct MenuType *mt) RET_ZERO
void		WM_modalkeymap_assign(struct wmKeyMap *km, const char *opname) RET_NONE
wmKeyMapItem *WM_modalkeymap_find_propvalue(wmKeyMap *km, const int propvalue) RET_NULL
wmKeyMap	*WM_modalkeymap_get(struct wmKeyConfig *keyconf, const char *idname) RET_NULL
int WM_modalkeymap_items_to_string(
        struct wmKeyMap *km, const int propvalue, const bool compact,
        char *result, const int result_len) RET_ZERO
char *WM_modalkeymap_operator_items_to_string_buf(
        struct wmOperatorType *ot, const int propvalue, const bool compact,
        const int max_len, int *r_available_len, char **r_result) RET_NULL
bool        WM_operator_check_ui_enabled(const struct bContext *C, const char *idname) RET_ZERO
int         WM_operator_confirm_message(struct bContext *C, struct wmOperator *op,
                                        const char *message) RET_ZERO
ID         *WM_operator_drop_load_path(struct bContext *C, struct wmOperator *op, const short idcode) RET_NULL
int			WM_operator_filesel		(struct bContext *C, struct wmOperator *op, const struct wmEvent *event) RET_ZERO
bool        WM_operator_filesel_ensure_ext_imtype(wmOperator *op, const struct ImageFormatData *im_format) RET_ZERO
void		WM_operator_free_all_after(wmWindowManager *wm, struct wmOperator *op) RET_NONE
wmOperator *WM_operator_last_redo(const struct bContext *C) RET_NULL
int			WM_operator_name_call(struct bContext *C, const char *opstring, short context, struct PointerRNA *properties) RET_ZERO
int         WM_operator_name_call_ptr(struct bContext *C, struct wmOperatorType *ot, short context, struct PointerRNA *properties) RET_ZERO
void        WM_operator_properties_border(struct wmOperatorType *ot) RET_NONE
void        WM_operator_properties_border_to_rctf(struct wmOperator *op, rctf *rect) RET_NONE
void        WM_operator_properties_border_to_rcti(struct wmOperator *op, struct rcti *rect) RET_NONE
void        WM_operator_properties_checker_interval(struct wmOperatorType *ot, bool nth_can_disable) RET_NONE
void        WM_operator_properties_checker_interval_from_op(
        struct wmOperator *op, struct CheckerIntervalParams *op_params) RET_NONE
bool        WM_operator_properties_checker_interval_test(
        const struct CheckerIntervalParams *op_params, int depth) RET_ZERO
void        WM_operator_properties_filesel(
        struct wmOperatorType *ot, int filter, short type, short action,
        short flag, short display, short sort) RET_NONE
void        WM_operator_properties_gesture_border(struct wmOperatorType *ot) RET_NONE
void        WM_operator_properties_gesture_border_ex(struct wmOperatorType *ot, bool deselect, bool extend) RET_NONE
void        WM_operator_properties_gesture_border_select(struct wmOperatorType *ot) RET_NONE
void        WM_operator_properties_gesture_border_zoom(struct wmOperatorType *ot) RET_NONE
void        WM_operator_properties_gesture_circle_select(struct wmOperatorType *ot) RET_NONE
void        WM_operator_properties_gesture_lasso(struct wmOperatorType *ot) RET_NONE
void        WM_operator_properties_gesture_lasso_select(struct wmOperatorType *ot) RET_NONE
void        WM_operator_properties_gesture_straightline(struct wmOperatorType *ot, int cursor) RET_NONE
void        WM_operator_properties_mouse_select(struct wmOperatorType *ot) RET_NONE
void        WM_operator_properties_select_action(struct wmOperatorType *ot, int default_action) RET_NONE
void        WM_operator_properties_select_all(struct wmOperatorType *ot) RET_NONE
void        WM_operator_properties_select_random(struct wmOperatorType *ot) RET_NONE
int         WM_operator_properties_select_random_seed_increment_get(wmOperator *op) RET_ZERO
int			WM_operator_props_popup_confirm(struct bContext *C, struct wmOperator *op, const struct wmEvent *event) RET_ZERO
bool         WM_operator_pystring_abbreviate(char *str, int str_len_max) RET_ZERO
int			WM_operator_redo_popup	(struct bContext *C, struct wmOperator *op) RET_ZERO
int			WM_operator_repeat		(struct bContext *C, struct wmOperator *op) RET_ZERO
bool        WM_operator_repeat_check(const struct bContext *C, struct wmOperator *op) RET_ZERO
int			WM_operator_smooth_viewtx_get(const struct wmOperator *op) RET_ZERO
void		WM_operator_type_set(struct wmOperator *op, struct wmOperatorType *ot) RET_NONE
void		WM_operator_view3d_unit_defaults(struct bContext *C, struct wmOperator *op) RET_NONE
bool			WM_operator_winactive	(struct bContext *C) RET_ZERO
void WM_operatortype_append(void (*opfunc)(struct wmOperatorType *)) RET_NONE
struct wmOperatorType *WM_operatortype_append_macro(const char *idname, const char *name, const char *description, int flag) RET_NULL
struct wmPaintCursor *WM_paint_cursor_activate(
        struct wmWindowManager *wm,
        bool (*poll)(struct bContext *C),
        void (*draw)(struct bContext *C, int, int, void *customdata),
        void *customdata) RET_NULL
bool		WM_paint_cursor_end(struct wmWindowManager *wm, struct wmPaintCursor *handle) RET_ZERO
void		WM_paint_cursor_tag_redraw(struct wmWindow *win, struct ARegion *ar) RET_NONE
struct PanelType   *WM_paneltype_find(const char *idname, bool quiet) RET_NULL
char		*WM_prop_pystring_assign(struct bContext *C, struct PointerRNA *ptr, struct PropertyRNA *prop, int index) RET_NULL
void		WM_redraw_windows(struct bContext *C) RET_NONE
void        WM_report_banner_show(void) RET_NONE
void        WM_reportf(ReportType type, const char *format, ...) RET_NONE
void        WM_set_locked_interface(struct wmWindowManager *wm, bool lock) RET_NONE
bool		WM_stereo3d_enabled(struct wmWindow *win, bool only_fullscreen_test) RET_ZERO
void WM_tooltip_clear(struct bContext *C, struct wmWindow *win) RET_NONE
void WM_tooltip_refresh(struct bContext *C, struct wmWindow *win) RET_NONE
void WM_tooltip_timer_clear(struct bContext *C, struct wmWindow *win) RET_NONE
void WM_tooltip_timer_init(
        struct bContext *C, struct wmWindow *win, struct ARegion *ar,
        wmTooltipInitFn init) RET_NONE
int			WM_userdef_event_type_from_keymap_type(int kmitype) RET_ZERO
struct wmWindow	*WM_window_open(struct bContext *C, const struct rcti *rect) RET_NULL
struct wmWindow *WM_window_open_temp(struct bContext *C, int x, int y, int sizex, int sizey, int type) RET_NULL
int			WM_window_pixels_x		(struct wmWindow *win) RET_ZERO
int			WM_window_pixels_y		(struct wmWindow *win) RET_ZERO
void             WM_window_set_dpi(wmWindow *win) RET_NONE
void		wmFrustum			(float x1, float x2, float y1, float y2, float n, float f) RET_NONE
void		wmOrtho				(float x1, float x2, float y1, float y2, float n, float f) RET_NONE
void		wmOrtho2			(float x1, float x2, float y1, float y2) RET_NONE
void		wmOrtho2_region_pixelspace(const struct ARegion *ar) RET_NONE
void		wmSubWindowScissorSet	(struct wmWindow *win, int swinid, const struct rcti *srct, bool srct_pad) RET_NONE
void		wmSubWindowSet			(struct wmWindow *win, int swinid) RET_NONE
struct wmEvent *wm_event_add(
        struct wmWindow *win, const struct wmEvent *event_to_add) RET_NULL
void wm_event_init_from_window(struct wmWindow *win, struct wmEvent *event) RET_NONE

/* -------------------------------------------------------------------- */
/* wm_window.h / wm_subwindow.h / wm_draw.h / wm_event_system.h stubs (internal headers, not exposed via WM_api.h) */

struct ARegion;
struct rcti;
struct wmEvent;

void wm_cursor_position_from_ghost(struct wmWindow *win, int *x, int *y) RET_NONE
void wm_draw_region_clear(struct wmWindow *win, struct ARegion *ar) RET_NONE
void wm_event_free_all(struct wmWindow *win) RET_NONE
void wm_get_screensize(int *r_width, int *r_height) RET_NONE
void wm_subwindow_close(struct wmWindow *win, int swinid) RET_NONE
void wm_subwindow_matrix_get(struct wmWindow *win, int swinid, float mat[4][4]) RET_NONE
int  wm_subwindow_open(struct wmWindow *win, const struct rcti *winrct, bool activate) RET_ZERO
void wm_subwindow_position(struct wmWindow *win, int swinid, const struct rcti *winrct, bool activate) RET_NONE
void wm_subwindow_rect_set(struct wmWindow *win, int swinid, const struct rcti *rect) RET_NONE
void wm_subwindow_size_get(struct wmWindow *win, int swinid, int *x, int *y) RET_NONE
void wm_window_IME_begin(struct wmWindow *win, int x, int y, int w, int h, bool complete) RET_NONE
void wm_window_IME_end(struct wmWindow *win) RET_NONE
void wm_window_lower(struct wmWindow *win) RET_NONE
void wm_window_make_drawable(struct wmWindowManager *wm, struct wmWindow *win) RET_NONE
void wm_window_raise(struct wmWindow *win) RET_NONE
void wm_window_set_order(struct wmWindow *win, int order) RET_NONE
void wm_window_set_swap_interval(struct wmWindow *win, int interval) RET_NONE
void wm_window_swap_buffers(struct wmWindow *win) RET_NONE
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_armature_bone_rename) */
void ED_armature_bone_rename(struct Main *bmain, struct bArmature *arm, const char *oldnamep, const char *newnamep) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_armature_transform) */
void ED_armature_transform(struct Main *bmain, struct bArmature *arm, float mat[4][4], const bool do_props) RET_NONE
#endif
struct wmEventHandler *WM_event_add_modal_handler(struct bContext *C, struct wmOperator *op) RET_NULL
struct wmTimer *WM_event_add_timer(struct wmWindowManager *wm, struct wmWindow *win, int event_type, double timestep) RET_NULL
void WM_event_remove_timer(struct wmWindowManager *wm, struct wmWindow *win, struct wmTimer *timer) RET_NONE
float WM_event_tablet_data(const struct wmEvent *event, int *pen_flip, float tilt[2]) RET_ZERO
bool WM_event_is_tablet(const struct wmEvent *event) RET_ZERO
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_armature_ebone_remove) */
void ED_armature_ebone_remove(struct bArmature *arm, struct EditBone *exBone) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (object_test_constraints) */
void object_test_constraints(struct Main *bmain, struct Object *owner) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_armature_ebone_to_mat4) */
void ED_armature_ebone_to_mat4(struct EditBone *ebone, float mat[4][4]) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_armature_ebone_from_mat4) */
void ED_armature_ebone_from_mat4(EditBone *ebone, float mat[4][4]) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_object_parent) */
void ED_object_parent(struct Object *ob, struct Object *par, int type, const char *substr) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_object_constraint_set_active) */
void ED_object_constraint_set_active(struct Object *ob, struct bConstraint *con) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_node_composit_default) */
void ED_node_composit_default(const struct bContext *C, struct Scene *scene) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_region_draw_cb_activate) */
void *ED_region_draw_cb_activate(struct ARegionType *art, void(*draw)(const struct bContext *, struct ARegion *, void *), void *custumdata, int type) RET_ZERO /* XXX this one looks weird */
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_region_draw_cb_customdata) */
void *ED_region_draw_cb_customdata(void *handle) RET_ZERO /* XXX This one looks wrong also */
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_region_draw_cb_exit) */
void ED_region_draw_cb_exit(struct ARegionType *art, void *handle) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_area_headerprint) */
void ED_area_headerprint(struct ScrArea *sa, const char *str) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_gpencil_parent_location) */
void ED_gpencil_parent_location(struct bGPDlayer *gpl, float diff_mat[4][4]) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (UI_view2d_region_to_view) */
void UI_view2d_region_to_view(struct View2D *v2d, float x, float y, float *viewx, float *viewy) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (UI_view2d_view_to_region_clip) */
bool UI_view2d_view_to_region_clip(struct View2D *v2d, float x, float y, int *regionx, int *regiony) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (UI_view2d_view_to_region) */
void UI_view2d_view_to_region(struct View2D *v2d, float x, float y, int *regionx, int *region_y) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (UI_view2d_sync) */
void UI_view2d_sync(struct bScreen *screen, struct ScrArea *sa, struct View2D *v2dcur, int flag) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (UI_style_get) */
struct uiStyle *UI_style_get(void) RET_NULL;
#endif

#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_armature_ebone_get_mirrored) */
struct EditBone *ED_armature_ebone_get_mirrored(const struct ListBase *edbo, EditBone *ebo) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_armature_ebone_add) */
struct EditBone *ED_armature_ebone_add(struct bArmature *arm, const char *name) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (get_active_constraints) */
struct ListBase *get_active_constraints (struct Object *ob) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (get_constraint_lb) */
struct ListBase *get_constraint_lb(struct Object *ob, struct bConstraint *con, struct bPoseChannel **r_pchan) RET_NULL
#endif

#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_space_image_show_uvedit) */
bool ED_space_image_show_uvedit(struct SpaceImage *sima, struct Object *obedit) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_space_image_show_render) */
bool ED_space_image_show_render(struct SpaceImage *sima) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_space_image_show_paint) */
bool ED_space_image_show_paint(struct SpaceImage *sima) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_space_image_paint_update) */
void ED_space_image_paint_update(struct Main *bmain, struct wmWindowManager *wm, struct Scene *scene) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_space_image_set) */
void ED_space_image_set(struct Main *bmain, struct SpaceImage *sima, struct Scene *scene, struct Object *obedit, struct Image *ima) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_space_image_uv_sculpt_update) */
void ED_space_image_uv_sculpt_update(struct Main *bmain, struct wmWindowManager *wm, struct Scene *scene) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_space_image_scopes_update) */
void ED_space_image_scopes_update(const struct bContext *C, struct SpaceImage *sima, struct ImBuf *ibuf, bool use_view_settings) RET_NONE
#endif

#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_uvedit_get_aspect) */
void ED_uvedit_get_aspect(struct Scene *scene, struct Object *ob, struct BMesh *em, float *aspx, float *aspy) RET_NONE
#endif

#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_screen_set_scene) */
void ED_screen_set_scene(struct bContext *C, struct bScreen *screen, struct Scene *scene) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_space_clip_get_clip) */
struct MovieClip *ED_space_clip_get_clip(struct SpaceClip *sc) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_space_clip_set_clip) */
void ED_space_clip_set_clip(struct bContext *C, struct bScreen *screen, struct SpaceClip *sc, struct MovieClip *clip) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_space_clip_set_mask) */
void ED_space_clip_set_mask(struct bContext *C, struct SpaceClip *sc, struct Mask *mask) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_space_image_set_mask) */
void ED_space_image_set_mask(struct bContext *C, struct SpaceImage *sima, struct Mask *mask) RET_NONE
#endif

#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_area_tag_redraw_regiontype) */
void ED_area_tag_redraw_regiontype(struct ScrArea *sa, int regiontype) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_render_engine_changed) */
void ED_render_engine_changed(struct Main *bmain) RET_NONE
#endif

#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_file_read_bookmarks) */
void ED_file_read_bookmarks(void) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_file_change_dir) */
void ED_file_change_dir(struct bContext *C) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_preview_kill_jobs) */
void ED_preview_kill_jobs(struct wmWindowManager *wm, struct Main *bmain) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_fsmenu_get) */
struct FSMenu *ED_fsmenu_get(void) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_fsmenu_get_category) */
struct FSMenuEntry *ED_fsmenu_get_category(struct FSMenu *fsmenu, FSMenuCategory category) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_fsmenu_get_nentries) */
int ED_fsmenu_get_nentries(struct FSMenu *fsmenu, FSMenuCategory category) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_fsmenu_get_entry) */
struct FSMenuEntry *ED_fsmenu_get_entry(struct FSMenu *fsmenu, FSMenuCategory category, int index) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_fsmenu_entry_get_path) */
char *ED_fsmenu_entry_get_path(struct FSMenuEntry *fsentry) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_fsmenu_entry_set_path) */
void ED_fsmenu_entry_set_path(struct FSMenuEntry *fsentry, const char *name) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_fsmenu_entry_get_name) */
char *ED_fsmenu_entry_get_name(struct FSMenuEntry *fsentry) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_fsmenu_entry_set_name) */
void ED_fsmenu_entry_set_name(struct FSMenuEntry *fsentry, const char *name) RET_NONE
#endif

#ifndef WITH_BLENDER /* duplicate: real impl now linked (PE_get_current) */
struct PTCacheEdit *PE_get_current(struct Main *bmain, struct Scene *scene, struct Object *ob) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (PE_current_changed) */
void PE_current_changed(struct Main *bmain, struct Scene *scene, struct Object *ob) RET_NONE
#endif

/* rna keymap */
struct wmKeyMap *WM_keymap_active(struct wmWindowManager *wm, struct wmKeyMap *keymap) RET_NULL
struct wmKeyMap *WM_keymap_ensure(struct wmKeyConfig *keyconf, const char *idname, int spaceid, int regionid) RET_NULL
struct wmKeyMapItem *WM_keymap_add_item(struct wmKeyMap *keymap, const char *idname, int type,  int val, int modifier, int keymodifier) RET_NULL
struct wmKeyMap *WM_keymap_list_find(ListBase *lb, const char *idname, int spaceid, int regionid) RET_NULL
struct wmKeyConfig *WM_keyconfig_new(struct wmWindowManager *wm, const char *idname) RET_NULL
struct wmKeyConfig *WM_keyconfig_new_user(struct wmWindowManager *wm, const char *idname) RET_NULL
bool WM_keyconfig_remove(struct wmWindowManager *wm, struct wmKeyConfig *keyconf) RET_ZERO
bool WM_keymap_remove(struct wmKeyConfig *keyconfig, struct wmKeyMap *keymap) RET_ZERO
void WM_keyconfig_set_active(struct wmWindowManager *wm, const char *idname) RET_NONE
bool WM_keymap_remove_item(struct wmKeyMap *keymap, struct wmKeyMapItem *kmi) RET_ZERO
void WM_keymap_restore_to_default(struct wmKeyMap *keymap, struct bContext *C) RET_NONE
void WM_keymap_restore_item_to_default(struct bContext *C, struct wmKeyMap *keymap, struct wmKeyMapItem *kmi) RET_NONE
void WM_keymap_properties_reset(struct wmKeyMapItem *kmi, struct IDProperty *properties) RET_NONE
void WM_keyconfig_update_tag(struct wmKeyMap *keymap, struct wmKeyMapItem *kmi) RET_NONE
bool WM_keymap_item_compare(struct wmKeyMapItem *k1, struct wmKeyMapItem *k2) RET_ZERO
int	WM_keymap_map_type_get(struct wmKeyMapItem *kmi) RET_ZERO


/* rna editors */

#ifndef WITH_BLENDER /* duplicate: real impl now linked (verify_fcurve) */
struct FCurve *verify_fcurve(struct bAction *act, const char group[], struct PointerRNA *ptr, const char rna_path[], const int array_index, short add) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (insert_vert_fcurve) */
int insert_vert_fcurve(struct FCurve *fcu, float x, float y, eBezTriple_KeyframeType keytype, eInsertKeyFlags flag) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (delete_fcurve_key) */
void delete_fcurve_key(struct FCurve *fcu, int index, bool do_recalc) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ANIM_keyingset_info_find_name) */
struct KeyingSetInfo *ANIM_keyingset_info_find_name (const char name[]) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ANIM_scene_get_active_keyingset) */
struct KeyingSet *ANIM_scene_get_active_keyingset (struct Scene *scene) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ANIM_scene_get_keyingset_index) */
int ANIM_scene_get_keyingset_index(struct Scene *scene, struct KeyingSet *ks) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ANIM_id_update) */
void ANIM_id_update(struct Scene *scene, struct ID *id) RET_NONE
#endif
struct ListBase builtin_keyingsets;
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ANIM_keyingset_info_register) */
void ANIM_keyingset_info_register(struct KeyingSetInfo *ksi) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ANIM_keyingset_info_unregister) */
void ANIM_keyingset_info_unregister(struct Main *bmain, KeyingSetInfo *ksi) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ANIM_validate_keyingset) */
short ANIM_validate_keyingset(struct bContext *C, struct ListBase *dsources, struct KeyingSet *ks) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ANIM_add_driver) */
int ANIM_add_driver(struct ReportList *reports, struct ID *id, const char rna_path[], int array_index, short flag, int type) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ANIM_remove_driver) */
bool ANIM_remove_driver(struct ReportList *reports, struct ID *id, const char rna_path[], int array_index, short flag) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_space_image_release_buffer) */
void ED_space_image_release_buffer(struct SpaceImage *sima, struct ImBuf *ibuf, void *lock) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_space_image_acquire_buffer) */
struct ImBuf *ED_space_image_acquire_buffer(struct SpaceImage *sima, void **r_lock) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_space_image_get_zoom) */
void ED_space_image_get_zoom(struct SpaceImage *sima, struct ARegion *ar, float *zoomx, float *zoomy) RET_NONE
#endif
const char *ED_info_stats_string(struct Scene *scene) RET_NULL
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_area_tag_redraw) */
void ED_area_tag_redraw(struct ScrArea *sa) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_area_tag_refresh) */
void ED_area_tag_refresh(struct ScrArea *sa) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_area_newspace) */
void ED_area_newspace(struct bContext *C, struct ScrArea *sa, int type, const bool skip_ar_exit) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_region_tag_redraw) */
void ED_region_tag_redraw(struct ARegion *ar) RET_NONE
#endif
void WM_event_add_fileselect(struct bContext *C, struct wmOperator *op) RET_NONE
void WM_cursor_wait(bool val) RET_NONE
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_node_texture_default) */
void ED_node_texture_default(const struct bContext *C, struct Tex *tex) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_node_tag_update_id) */
void ED_node_tag_update_id(struct ID *id) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_node_tag_update_nodetree) */
void ED_node_tag_update_nodetree(struct Main *bmain, struct bNodeTree *ntree, struct bNode *node) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_node_tree_update) */
void ED_node_tree_update(const struct bContext *C) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_node_set_tree_type) */
void ED_node_set_tree_type(struct SpaceNode *snode, struct bNodeTreeType *typeinfo) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_init_custom_node_type) */
void ED_init_custom_node_type(struct bNodeType *ntype) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_init_custom_node_socket_type) */
void ED_init_custom_node_socket_type(struct bNodeSocketType *stype) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_init_standard_node_socket_type) */
void ED_init_standard_node_socket_type(struct bNodeSocketType *stype) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_init_node_socket_type_virtual) */
void ED_init_node_socket_type_virtual(struct bNodeSocketType *stype) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_node_tree_path_length) */
int ED_node_tree_path_length(struct SpaceNode *snode) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_node_tree_path_get) */
void ED_node_tree_path_get(struct SpaceNode *snode, char *value) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_node_tree_path_get_fixedbuf) */
void ED_node_tree_path_get_fixedbuf(struct SpaceNode *snode, char *value, int max_length) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_node_tree_start) */
void ED_node_tree_start(struct SpaceNode *snode, struct bNodeTree *ntree, struct ID *id, struct ID *from) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_node_tree_push) */
void ED_node_tree_push(struct SpaceNode *snode, struct bNodeTree *ntree, struct bNode *gnode) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_node_tree_pop) */
void ED_node_tree_pop(struct SpaceNode *snode) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_view3d_scene_layer_set) */
int ED_view3d_scene_layer_set(int lay, const bool *values, int *active) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_view3d_quadview_update) */
void ED_view3d_quadview_update(struct ScrArea *sa, struct ARegion *ar, bool do_clip) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_view3d_from_m4) */
void ED_view3d_from_m4(float mat[4][4], float ofs[3], float quat[4], float *dist) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_view3d_background_image_new) */
struct BGpic *ED_view3d_background_image_new(struct View3D *v3d) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_view3d_background_image_remove) */
void ED_view3d_background_image_remove(struct View3D *v3d, struct BGpic *bgpic) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_view3d_background_image_clear) */
void ED_view3d_background_image_clear(struct View3D *v3d) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_view3d_update_viewmat) */
void ED_view3d_update_viewmat(struct Scene *scene, struct View3D *v3d, struct ARegion *ar, float viewmat[4][4], float winmat[4][4], const struct rcti *rect) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_view3d_grid_scale) */
float ED_view3d_grid_scale(struct Scene *scene, struct View3D *v3d, const char **grid_unit) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_view3d_shade_update) */
void ED_view3d_shade_update(struct Main *bmain, struct View3D *v3d, struct ScrArea *sa) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_node_shader_default) */
void ED_node_shader_default(const struct bContext *C, struct ID *id) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_screen_animation_timer_update) */
void ED_screen_animation_timer_update(struct bScreen *screen, int redraws, int refresh) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_screen_animation_playing) */
struct bScreen *ED_screen_animation_playing(const struct wmWindowManager *wm) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_base_object_select) */
void ED_base_object_select(struct Base *base, short mode) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_object_modifier_remove) */
bool ED_object_modifier_remove(struct ReportList *reports, struct Main *bmain, struct Object *ob, struct ModifierData *md) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_object_modifier_add) */
struct ModifierData *ED_object_modifier_add(struct ReportList *reports, struct Main *bmain, struct Scene *scene, struct Object *ob, const char *name, int type) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_object_modifier_clear) */
void ED_object_modifier_clear(struct Main *bmain, struct Object *ob) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_object_editmode_enter) */
bool ED_object_editmode_enter(struct bContext *C, int flag) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_object_editmode_exit) */
bool ED_object_editmode_exit(struct bContext *C, int flag) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_object_editmode_load) */
bool ED_object_editmode_load(struct Main *bmain, struct Object *obedit) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_object_check_force_modifiers) */
void ED_object_check_force_modifiers(struct Main *bmain, struct Scene *scene, struct Object *object) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiLayoutGetActive) */
bool uiLayoutGetActive(struct uiLayout *layout) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiLayoutGetActivateInit) */
bool uiLayoutGetActivateInit(struct uiLayout *layout) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiLayoutGetOperatorContext) */
int uiLayoutGetOperatorContext(struct uiLayout *layout) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiLayoutGetAlignment) */
int uiLayoutGetAlignment(struct uiLayout *layout) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiLayoutGetEnabled) */
bool uiLayoutGetEnabled(struct uiLayout *layout) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiLayoutGetScaleX) */
float uiLayoutGetScaleX(struct uiLayout *layout) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiLayoutGetScaleY) */
float uiLayoutGetScaleY(struct uiLayout *layout) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiLayoutGetUnitsX) */
float uiLayoutGetUnitsX(struct uiLayout *layout) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiLayoutGetUnitsY) */
float uiLayoutGetUnitsY(struct uiLayout *layout) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiLayoutSetUnitsX) */
void uiLayoutSetUnitsX(struct uiLayout *layout, float unit) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiLayoutSetUnitsY) */
void uiLayoutSetUnitsY(struct uiLayout *layout, float unit) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiLayoutSetActive) */
void uiLayoutSetActive(struct uiLayout *layout, bool active) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiLayoutSetOperatorContext) */
void uiLayoutSetOperatorContext(struct uiLayout *layout, int opcontext) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiLayoutSetEnabled) */
void uiLayoutSetEnabled(struct uiLayout *layout, bool enabled) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiLayoutSetActivateInit) */
void uiLayoutSetActivateInit(struct uiLayout *layout, bool active) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiLayoutSetAlignment) */
void uiLayoutSetAlignment(uiLayout *layout, char alignment) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiLayoutSetScaleX) */
void uiLayoutSetScaleX(struct uiLayout *layout, float scale) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiLayoutSetScaleY) */
void uiLayoutSetScaleY(struct uiLayout *layout, float scale) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateIconView) */
void uiTemplateIconView(struct uiLayout *layout, struct PointerRNA *ptr, const char *propname, bool show_labels, float icon_scale) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_base_object_free_and_unlink) */
void ED_base_object_free_and_unlink(struct Main *bmain, struct Scene *scene, struct Base *base) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_mesh_update) */
void ED_mesh_update(struct Mesh *mesh, struct bContext *C, bool calc_edges, bool calc_tessface) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_mesh_vertices_add) */
void ED_mesh_vertices_add(struct Mesh *mesh, struct ReportList *reports, int count) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_mesh_edges_add) */
void ED_mesh_edges_add(struct Mesh *mesh, struct ReportList *reports, int count) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_mesh_tessfaces_add) */
void ED_mesh_tessfaces_add(struct Mesh *mesh, struct ReportList *reports, int count) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_mesh_loops_add) */
void ED_mesh_loops_add(struct Mesh *mesh, struct ReportList *reports, int count) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_mesh_polys_add) */
void ED_mesh_polys_add(struct Mesh *mesh, struct ReportList *reports, int count) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_mesh_vertices_remove) */
void ED_mesh_vertices_remove(struct Mesh *mesh, struct ReportList *reports, int count) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_mesh_edges_remove) */
void ED_mesh_edges_remove(struct Mesh *mesh, struct ReportList *reports, int count) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_mesh_faces_remove) */
void ED_mesh_faces_remove(struct Mesh *mesh, struct ReportList *reports, int count) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_mesh_color_add) */
int ED_mesh_color_add(struct Mesh *me, const char *name, const bool active_set) RET_MINUSONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_mesh_uv_texture_add) */
int ED_mesh_uv_texture_add(struct Mesh *me, const char *name, const bool active_set) RET_MINUSONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_mesh_color_remove_named) */
bool ED_mesh_color_remove_named(struct Mesh *me, const char *name) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_mesh_uv_texture_remove_named) */
bool ED_mesh_uv_texture_remove_named(struct Mesh *me, const char *name) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_object_constraint_dependency_update) */
void ED_object_constraint_dependency_update(struct Main *bmain, struct Object *ob) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_object_constraint_dependency_tag_update) */
void ED_object_constraint_dependency_tag_update(struct Main *bmain, struct Object *ob, struct bConstraint *con) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_object_constraint_update) */
void ED_object_constraint_update(struct Main *bmain, struct Object *ob) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_object_constraint_tag_update) */
void ED_object_constraint_tag_update(struct Main *bmain, struct Object *ob, struct bConstraint *con) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_vgroup_vert_add) */
void ED_vgroup_vert_add(struct Object *ob, struct bDeformGroup *dg, int vertnum, float weight, int assignmode) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_vgroup_vert_remove) */
void ED_vgroup_vert_remove(struct Object *ob, struct bDeformGroup *dg, int vertnum) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_vgroup_vert_weight) */
float ED_vgroup_vert_weight(struct Object *ob, struct bDeformGroup *dg, int vertnum) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_mesh_mirror_topo_table) */
int ED_mesh_mirror_topo_table(struct Object *ob, struct DerivedMesh *dm, char mode) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_mesh_mirror_spatial_table) */
int ED_mesh_mirror_spatial_table(struct Object *ob, struct BMEditMesh *em, struct DerivedMesh *dm, const float co[3], char mode) RET_ZERO
#endif

#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_armature_ebone_roll_to_vector) */
float ED_armature_ebone_roll_to_vector(const EditBone *bone, const float new_up_axis[3], const bool axis_only) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_space_image_get_size) */
void ED_space_image_get_size(struct SpaceImage *sima, int *width, int *height) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_space_image_check_show_maskedit) */
bool ED_space_image_check_show_maskedit(struct Scene *scene, struct SpaceImage *sima) RET_ZERO
#endif

#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_texture_context_check_world) */
bool ED_texture_context_check_world(const struct bContext *C) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_texture_context_check_material) */
bool ED_texture_context_check_material(const struct bContext *C) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_texture_context_check_lamp) */
bool ED_texture_context_check_lamp(const struct bContext *C) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_texture_context_check_particles) */
bool ED_texture_context_check_particles(const struct bContext *C) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_texture_context_check_others) */
bool ED_texture_context_check_others(const struct bContext *C) RET_ZERO
#endif

#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_text_region_location_from_cursor) */
bool ED_text_region_location_from_cursor(SpaceText *st, ARegion *ar, const int cursor_co[2], int r_pixel_co[2]) RET_ZERO
#endif

#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_transform_snap_object_context_create) */
SnapObjectContext *ED_transform_snap_object_context_create(
        struct Main *bmain, struct Scene *scene, int flag) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_transform_snap_object_context_create_view3d) */
SnapObjectContext *ED_transform_snap_object_context_create_view3d(
        struct Main *bmain, struct Scene *scene, int flag,
        const struct ARegion *ar, const struct View3D *v3d) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_transform_snap_object_context_destroy) */
void ED_transform_snap_object_context_destroy(SnapObjectContext *sctx) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_transform_snap_object_project_ray_ex) */
bool ED_transform_snap_object_project_ray_ex(
        struct SnapObjectContext *sctx,
        const struct SnapObjectParams *params,
        const float ray_start[3], const float ray_normal[3], float *ray_depth,
        /* return args */
        float r_loc[3], float r_no[3], int *r_index,
        struct Object **r_ob, float r_obmat[4][4]) RET_ZERO
#endif

#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_curve_editnurb_load) */
void ED_curve_editnurb_load(struct Main *bmain, struct Object *obedit) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_curve_editnurb_make) */
void ED_curve_editnurb_make(struct Object *obedit) RET_NONE
#endif

#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiItemR) */
void uiItemR(uiLayout *layout, struct PointerRNA *ptr, const char *propname, int flag, const char *name, int icon) RET_NONE
#endif

#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiItemFullO) */
void uiItemFullO(uiLayout *layout, const char *idname, const char *name, int icon, struct IDProperty *properties, int context, int flag, struct PointerRNA *r_opptr) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiItemFullO_ptr) */
void uiItemFullO_ptr(struct uiLayout *layout, struct wmOperatorType *ot, const char *name, int icon, struct IDProperty *properties, int context, int flag, struct PointerRNA *r_opptr) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiItemFullOMenuHold_ptr) */
void uiItemFullOMenuHold_ptr( uiLayout *layout, struct wmOperatorType *ot, const char *name, int icon, struct IDProperty *properties, int context, int flag, const char *menu_id,  /* extra menu arg. */ PointerRNA *r_opptr) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiLayoutRow) */
struct uiLayout *uiLayoutRow(struct uiLayout *layout, bool align) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiLayoutColumn) */
struct uiLayout *uiLayoutColumn(uiLayout *layout, bool align) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiLayoutColumnFlow) */
struct uiLayout *uiLayoutColumnFlow(uiLayout *layout, int number, bool align) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiLayoutBox) */
struct uiLayout *uiLayoutBox(struct uiLayout *layout) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiLayoutSplit) */
struct uiLayout *uiLayoutSplit(uiLayout *layout, float percentage, bool align) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiLayoutGetRedAlert) */
bool uiLayoutGetRedAlert(struct uiLayout *layout) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiLayoutSetRedAlert) */
void uiLayoutSetRedAlert(uiLayout *layout, bool redalert) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiItemsEnumR) */
void uiItemsEnumR(uiLayout *layout, struct PointerRNA *ptr, const char *propname) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiItemMenuEnumR_prop) */
void uiItemMenuEnumR_prop(uiLayout *layout, struct PointerRNA *ptr, PropertyRNA *prop, const char *name, int icon) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiItemMenuEnumR) */
void uiItemMenuEnumR(uiLayout *layout, struct PointerRNA *ptr, const char *propname, const char *name, int icon) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiItemEnumR_string_prop) */
void uiItemEnumR_string_prop(uiLayout *layout, struct PointerRNA *ptr, PropertyRNA *prop, const char *value, const char *name, int icon) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiItemEnumR_string) */
void uiItemEnumR_string(uiLayout *layout, struct PointerRNA *ptr, const char *propname, const char *value, const char *name, int icon) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiItemPointerR_prop) */
void uiItemPointerR_prop(uiLayout *layout, struct PointerRNA *ptr, PropertyRNA *prop, struct PointerRNA *searchptr, PropertyRNA *searchprop, const char *name, int icon) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiItemPointerR) */
void uiItemPointerR(uiLayout *layout, struct PointerRNA *ptr, const char *propname, struct PointerRNA *searchptr, const char *searchpropname, const char *name, int icon) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiItemsEnumO) */
void uiItemsEnumO(uiLayout *layout, const char *opname, const char *propname) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiItemEnumO_string) */
void uiItemEnumO_string(uiLayout *layout, const char *name, int icon, const char *opname, const char *propname, const char *value) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiItemMenuEnumO) */
void uiItemMenuEnumO(uiLayout *layout, struct bContext *C, const char *opname, const char *propname, const char *name, int icon) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiItemMenuEnumO_ptr) */
void uiItemMenuEnumO_ptr(uiLayout *layout, struct bContext *C, struct wmOperatorType *ot, const char *propname, const char *name, int icon) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiItemBooleanO) */
void uiItemBooleanO(uiLayout *layout, const char *name, int icon, const char *opname, const char *propname, int value) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiItemIntO) */
void uiItemIntO(uiLayout *layout, const char *name, int icon, const char *opname, const char *propname, int value) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiItemFloatO) */
void uiItemFloatO(uiLayout *layout, const char *name, int icon, const char *opname, const char *propname, float value) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiItemStringO) */
void uiItemStringO(uiLayout *layout, const char *name, int icon, const char *opname, const char *propname, const char *value) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiItemL) */
void uiItemL(struct uiLayout *layout, const char *name, int icon) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiItemM) */
void uiItemM(uiLayout *layout, const char *menuname, const char *name, int icon) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiItemS_ex) */
void uiItemS_ex(uiLayout* layout, float factor) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiItemS) */
void uiItemS(struct uiLayout *layout) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiItemFullR) */
void uiItemFullR(uiLayout *layout, struct PointerRNA *ptr, struct PropertyRNA *prop, int index, int value, int flag, const char *name, int icon) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiLayoutSetContextPointer) */
void uiLayoutSetContextPointer(uiLayout *layout, const char *name, struct PointerRNA *ptr) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (UI_reinit_font) */
void UI_reinit_font(void) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (UI_rnaptr_icon_get) */
int UI_rnaptr_icon_get(struct bContext *C, struct PointerRNA *ptr, int rnaicon, const bool big) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (UI_GetTheme) */
struct bTheme *UI_GetTheme(void) RET_NULL
#endif

/* rna template */
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateAnyID) */
void uiTemplateAnyID(uiLayout *layout, struct PointerRNA *ptr, const char *propname, const char *proptypename, const char *text) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplatePathBuilder) */
void uiTemplatePathBuilder(uiLayout *layout, struct PointerRNA *ptr, const char *propname, struct PointerRNA *root_ptr, const char *text) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateHeader) */
void uiTemplateHeader(struct uiLayout *layout, struct bContext *C) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateLayerLayout) */
void uiTemplateLayerLayout(
                           struct uiLayout *layout,
                           struct PointerRNA *ptr,
                           const char *propname,
                           PointerRNA *used_ptr,
                           const char *used_propname,
                           int active_layer,
                           const int group,
                           const int column) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateLayerLayoutObject) */
void uiTemplateLayerLayoutObject(
                           struct uiLayout *layout,
                           struct bContext *C,
                           const int group,
                           const int column) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateLayerLayoutBone) */
void uiTemplateLayerLayoutBone(
                           struct uiLayout *layout,
                           struct PointerRNA *ptr,
                           const char *propname,
                           const int group,
                           const int column) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateID) */
void uiTemplateID(uiLayout *layout, struct bContext *C, struct PointerRNA *ptr, const char *propname, const char *newop, const char *openop, const char *unlinkop, int filter) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateModifier) */
struct uiLayout *uiTemplateModifier(uiLayout *layout, struct bContext *C, struct PointerRNA *ptr) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateConstraint) */
struct uiLayout *uiTemplateConstraint(struct uiLayout *layout, struct PointerRNA *ptr) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplatePreview) */
void uiTemplatePreview(struct uiLayout *layout, struct bContext *C, struct ID *id, bool show_buttons, struct ID *parent,
                       struct MTex *slot, const char *preview_id) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateIDPreview) */
void uiTemplateIDPreview(uiLayout *layout, struct bContext *C, struct PointerRNA *ptr, const char *propname, const char *newop, const char *openop, const char *unlinkop, int rows, int cols, int filter) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateCurveMapping) */
void uiTemplateCurveMapping(uiLayout *layout, struct PointerRNA *ptr, const char *propname, int type, bool levels, bool brush, bool neg_slope) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateColorRamp) */
void uiTemplateColorRamp(uiLayout *layout, struct PointerRNA *ptr, const char *propname, bool expand) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateLayers) */
void uiTemplateLayers(uiLayout *layout, struct PointerRNA *ptr, const char *propname, PointerRNA *used_ptr, const char *used_propname, int active_layer) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateImageLayers) */
void uiTemplateImageLayers(struct uiLayout *layout, struct bContext *C, struct Image *ima, struct ImageUser *iuser) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateList) */
void uiTemplateList(struct uiLayout *layout, struct bContext *C, const char *listtype_name, const char *list_id,
                    PointerRNA *dataptr, const char *propname, PointerRNA *active_dataptr, const char *active_propname,
                    const char *item_dyntip_propname, int rows, int maxrows, int layout_type, int columns) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateRunningJobs) */
void uiTemplateRunningJobs(struct uiLayout *layout, struct bContext *C) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateOperatorSearch) */
void uiTemplateOperatorSearch(struct uiLayout *layout) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateHeader3D_mode) */
void uiTemplateHeader3D_mode(struct uiLayout *layout, struct bContext *C) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateHeader3D) */
void uiTemplateHeader3D(struct uiLayout *layout, struct bContext *C) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateEditModeSelection) */
void uiTemplateEditModeSelection(struct uiLayout *layout, struct bContext *C) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateImage) */
void uiTemplateImage(uiLayout *layout, struct bContext *C, struct PointerRNA *ptr, const char *propname, struct PointerRNA *userptr, bool compact, bool multiview, bool cubemap) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateColorPicker) */
void uiTemplateColorPicker(uiLayout *layout, struct PointerRNA *ptr, const char *propname, bool value_slider, bool lock, bool lock_luminosity, bool cubic) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateHistogram) */
void uiTemplateHistogram(uiLayout *layout, struct PointerRNA *ptr, const char *propname) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateReportsBanner) */
void uiTemplateReportsBanner(uiLayout *layout, struct bContext *C) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateWaveform) */
void uiTemplateWaveform(uiLayout *layout, struct PointerRNA *ptr, const char *propname) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateVectorscope) */
void uiTemplateVectorscope(uiLayout *layout, struct PointerRNA *ptr, const char *propname) RET_NONE
#endif
void uiTemplateNodeLink(struct uiLayout *layout, struct bNodeTree *ntree, struct bNode *node, struct bNodeSocket *input) RET_NONE
void uiTemplateNodeView(struct uiLayout *layout, struct bContext *C, struct bNodeTree *ntree, struct bNode *node, struct bNodeSocket *input) RET_NONE
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateTextureUser) */
void uiTemplateTextureUser(struct uiLayout *layout, struct bContext *C) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateTextureShow) */
void uiTemplateTextureShow(struct uiLayout *layout, struct bContext *C, struct PointerRNA *ptr, struct PropertyRNA *prop) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateKeymapItemProperties) */
void uiTemplateKeymapItemProperties(struct uiLayout *layout, struct PointerRNA *ptr) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateMovieClip) */
void uiTemplateMovieClip(struct uiLayout *layout, struct bContext *C, struct PointerRNA *ptr, const char *propname, bool compact) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateMovieclipInformation) */
void uiTemplateMovieclipInformation(struct uiLayout *layout, struct PointerRNA *ptr, const char *propname, struct PointerRNA *userptr) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateTrack) */
void uiTemplateTrack(struct uiLayout *layout, struct PointerRNA *ptr, const char *propname) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateMarker) */
void uiTemplateMarker(struct uiLayout *layout, struct PointerRNA *ptr, const char *propname, PointerRNA *userptr, PointerRNA *trackptr, bool compact) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateImageSettings) */
void uiTemplateImageSettings(uiLayout *layout, struct PointerRNA *imfptr, bool color_management) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateColorspaceSettings) */
void uiTemplateColorspaceSettings(struct uiLayout *layout, struct PointerRNA *ptr, const char *propname) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateColormanagedViewSettings) */
void uiTemplateColormanagedViewSettings(struct uiLayout *layout, struct bContext *C, struct PointerRNA *ptr, const char *propname) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateComponentMenu) */
void uiTemplateComponentMenu(struct uiLayout *layout, struct PointerRNA *ptr, const char *propname, const char *name) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateNodeSocket) */
void uiTemplateNodeSocket(struct uiLayout *layout, struct bContext *C, float *color) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplatePalette) */
void uiTemplatePalette(struct uiLayout *layout, struct PointerRNA *ptr, const char *propname, bool color) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateImageStereo3d) */
void uiTemplateImageStereo3d(struct uiLayout *layout, struct PointerRNA *stereo3d_format_ptr) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateCacheFile) */
void uiTemplateCacheFile(uiLayout *layout, struct bContext *C, struct PointerRNA *ptr, const char *propname) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateRecentFiles) */
int	 uiTemplateRecentFiles(uiLayout *layout, int rows) RET_ZERO
#endif

/* rna render */
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_engine_begin_result) */
struct RenderResult *RE_engine_begin_result(RenderEngine *engine, int x, int y, int w, int h, const char *layername, const char *viewname) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_AcquireResultRead) */
struct RenderResult *RE_AcquireResultRead(struct Render *re) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_AcquireResultWrite) */
struct RenderResult *RE_AcquireResultWrite(struct Render *re) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_engine_get_result) */
struct RenderResult *RE_engine_get_result(struct RenderEngine *re) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_GetStats) */
struct RenderStats *RE_GetStats(struct Render *re) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_engine_get_render_data) */
struct RenderData *RE_engine_get_render_data(struct Render *re) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_engine_update_result) */
void RE_engine_update_result(struct RenderEngine *engine, struct RenderResult *result) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_engine_update_progress) */
void RE_engine_update_progress(struct RenderEngine *engine, float progress) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_engine_set_error_message) */
void RE_engine_set_error_message(RenderEngine *engine, const char *msg) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_engine_add_pass) */
void RE_engine_add_pass(RenderEngine *engine, const char *name, int channels, const char *chan_id, const char *layername) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_engine_end_result) */
void RE_engine_end_result(RenderEngine *engine, struct RenderResult *result, bool cancel, bool highlight, bool merge_results) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_engine_update_stats) */
void RE_engine_update_stats(RenderEngine *engine, const char *stats, const char *info) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_layer_load_from_file) */
void RE_layer_load_from_file(struct RenderLayer *layer, struct ReportList *reports, const char *filename, int x, int y) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_result_load_from_file) */
void RE_result_load_from_file(struct RenderResult *result, struct ReportList *reports, const char *filename) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_AcquireResultImage) */
void RE_AcquireResultImage(struct Render *re, struct RenderResult *rr, const int view_id) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_ReleaseResult) */
void RE_ReleaseResult(struct Render *re) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_ReleaseResultImage) */
void RE_ReleaseResultImage(struct Render *re) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_engine_test_break) */
bool RE_engine_test_break(struct RenderEngine *engine) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_engines_init) */
void RE_engines_init() RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_engines_exit) */
void RE_engines_exit() RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_engine_report) */
void RE_engine_report(struct RenderEngine *engine, int type, const char *msg) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (R_engines) */
ListBase R_engines = {NULL, NULL};
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_engine_free) */
void RE_engine_free(struct RenderEngine *engine) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_engines_find) */
struct RenderEngineType *RE_engines_find(const char *idname) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_engine_update_memory_stats) */
void RE_engine_update_memory_stats(struct RenderEngine *engine, float mem_used, float mem_peak) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_engine_create) */
struct RenderEngine *RE_engine_create(struct RenderEngineType *type) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_engine_frame_set) */
void RE_engine_frame_set(struct RenderEngine *engine, int frame, float subframe) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_FreePersistentData) */
void RE_FreePersistentData(void) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_point_density_cache) */
void RE_point_density_cache(struct Scene *scene, struct PointDensity *pd, const bool use_render_params) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_point_density_minmax) */
void RE_point_density_minmax(struct Scene *scene, struct PointDensity *pd, const bool use_render_params, float r_min[3], float r_max[3]) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_point_density_sample) */
void RE_point_density_sample(struct Scene *scene, struct PointDensity *pd, int resolution, const bool use_render_params, float *values) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_point_density_free) */
void RE_point_density_free(struct PointDensity *pd) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_instance_get_particle_info) */
void RE_instance_get_particle_info(struct ObjectInstanceRen *obi, float *index, float *random, float *age, float *lifetime, float co[3], float *size, float vel[3], float angvel[3]) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_FreeAllPersistentData) */
void RE_FreeAllPersistentData(void) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_fresnel_dielectric) */
float RE_fresnel_dielectric(float incoming[3], float normal[3], float eta) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_engine_register_pass) */
void RE_engine_register_pass(struct RenderEngine *engine, struct Scene *scene, struct SceneRenderLayer *srl, const char *name, int channels, const char *chanid, int type) RET_NONE
#endif

/* rna space */
#ifndef WITH_BLENDER /* duplicate: real impl now linked (BIF_selectTransformOrientationValue) */
void BIF_selectTransformOrientationValue(struct Scene *C, int orientation) RET_NONE
#endif

/* rna ui */
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiLayoutGridFlow) */
struct uiLayout *uiLayoutGridFlow(uiLayout *layout, bool row_major, int num_columns, bool even_columns, bool even_rows, bool align) RET_NULL
#endif
void WM_paneltype_remove(struct PanelType *mt) RET_NONE
bool WM_paneltype_add(struct PanelType *mt) RET_ZERO
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiLayoutGetEmboss) */
int uiLayoutGetEmboss(uiLayout *layout) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiLayoutSetEmboss) */
void uiLayoutSetEmboss(uiLayout *layout, char emboss) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiLayoutGetPropSep) */
bool uiLayoutGetPropSep(uiLayout *layout) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiLayoutSetPropSep) */
void uiLayoutSetPropSep(uiLayout *layout, bool is_sep) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiLayoutGetPropDecorate) */
bool uiLayoutGetPropDecorate(uiLayout *layout) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiLayoutSetPropDecorate) */
void uiLayoutSetPropDecorate(uiLayout *layout, bool is_sep) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiItemPopoverPanelFromGroup) */
void uiItemPopoverPanelFromGroup(uiLayout *layout, struct bContext *C, int space_id, int region_id, const char *context, const char *category) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiItemSpacer) */
void uiItemSpacer(uiLayout *layout) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiItemPopoverPanel) */
void uiItemPopoverPanel(uiLayout *layout, struct bContext *C, const char *panelname, const char *name, int icon) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (UI_popover_layout) */
struct uiLayout *UI_popover_layout(uiPopover *head) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (UI_popover_begin) */
struct uiPopover *UI_popover_begin(struct bContext *C, int ui_size_x, bool from_active_button) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (UI_popover_end) */
void UI_popover_end(struct bContext *C, struct uiPopover *head, struct wmKeyMap *keymap) RET_NONE
#endif

/* python */
struct wmOperatorType *WM_operatortype_find(const char *idname, bool quiet) RET_NULL
void WM_operatortype_iter(struct GHashIterator *ghi) RET_NONE
struct wmOperatorTypeMacro *WM_operatortype_macro_define(struct wmOperatorType *ot, const char *idname) RET_NULL
int WM_operator_call_py(struct bContext *C, struct wmOperatorType *ot, short context, struct PointerRNA *properties, struct ReportList *reports, const bool is_undo) RET_ZERO
void WM_operatortype_remove_ptr(struct wmOperatorType *ot) RET_NONE
bool WM_operatortype_remove(const char *idname) RET_ZERO
bool WM_operator_poll(struct bContext *C, struct wmOperatorType *ot) RET_ZERO
bool WM_operator_poll_context(struct bContext *C, struct wmOperatorType *ot, short context) RET_ZERO
int WM_operator_props_popup(struct bContext *C, struct wmOperator *op, const struct wmEvent *event) RET_ZERO
void WM_operator_properties_free(struct PointerRNA *ptr) RET_NONE
void WM_operator_properties_create(struct PointerRNA *ptr, const char *opstring) RET_NONE
void WM_operator_properties_create_ptr(struct PointerRNA *ptr, struct wmOperatorType *ot) RET_NONE
void WM_operator_properties_sanitize(struct PointerRNA *ptr, const bool no_context) RET_NONE
void WM_operatortype_append_ptr(void (*opfunc)(struct wmOperatorType *, void *), void *userdata) RET_NONE
void WM_operatortype_append_macro_ptr(void (*opfunc)(struct wmOperatorType *, void *), void *userdata) RET_NONE
void WM_operator_bl_idname(char *to, const char *from) RET_NONE
void WM_operator_py_idname(char *to, const char *from) RET_NONE
bool WM_operator_py_idname_ok_or_report(struct ReportList *reports, const char *classname, const char *idname) RET_ZERO
int WM_operator_ui_popup(struct bContext *C, struct wmOperator *op, int width, int height) RET_ZERO
#ifndef WITH_BLENDER /* duplicate: real impl now linked (update_autoflags_fcurve) */
void update_autoflags_fcurve(struct FCurve *fcu, struct bContext *C, struct ReportList *reports, struct PointerRNA *ptr) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (insert_keyframe) */
short insert_keyframe(struct Main *bmain, struct ReportList *reports, struct ID *id, struct bAction *act, const char group[], const char rna_path[], int array_index, float cfra, eBezTriple_KeyframeType keytype, eInsertKeyFlags flag) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (delete_keyframe) */
short delete_keyframe(struct ReportList *reports, struct ID *id, struct bAction *act, const char group[], const char rna_path[], int array_index, float cfra, eInsertKeyFlags flag) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (verify_adt_action) */
struct bAction *verify_adt_action(struct Main *bmain, struct ID *id, short add) RET_NULL
#endif
char *WM_operator_pystring_ex(struct bContext *C, struct wmOperator *op, const bool all_args, const bool macro_args, struct wmOperatorType *ot, struct PointerRNA *opptr) RET_NULL
char *WM_operator_pystring(struct bContext *C, struct wmOperator *op, const bool all_args, const bool macro_args) RET_NULL
struct wmKeyMapItem *WM_modalkeymap_add_item(struct wmKeyMap *km, int type, int val, int modifier, int keymodifier, int value) RET_NULL
struct wmKeyMapItem *WM_modalkeymap_add_item_str(struct wmKeyMap *km, int type, int val, int modifier, int keymodifier, const char *value) RET_NULL
struct wmKeyMap *WM_modalkeymap_add(struct wmKeyConfig *keyconf, const char *idname, const struct EnumPropertyItem *items) RET_NULL
#ifndef WITH_BLENDER /* duplicate: real impl now linked (UI_popup_menu_begin) */
struct uiPopupMenu *UI_popup_menu_begin(struct bContext *C, const char *title, int icon) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (UI_popup_menu_end) */
void UI_popup_menu_end(struct bContext *C, struct uiPopupMenu *head) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (UI_popup_menu_layout) */
struct uiLayout *UI_popup_menu_layout(struct uiPopupMenu *head) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (UI_pie_menu_layout) */
struct uiLayout *UI_pie_menu_layout(struct uiPieMenu *pie) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (UI_pie_menu_invoke) */
int UI_pie_menu_invoke(struct bContext *C, const char *idname, const struct wmEvent *event) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (UI_pie_menu_begin) */
struct uiPieMenu *UI_pie_menu_begin(struct bContext *C, const char *title, int icon, const struct wmEvent *event) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (UI_pie_menu_end) */
void UI_pie_menu_end(struct bContext *C, uiPieMenu *pie) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiLayoutRadial) */
struct uiLayout *uiLayoutRadial(struct uiLayout *layout) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (UI_pie_menu_invoke_from_operator_enum) */
int UI_pie_menu_invoke_from_operator_enum(struct bContext *C, const char *title, const char *opname,
                             const char *propname, const struct wmEvent *event) RET_ZERO
#endif

#ifndef WITH_BLENDER /* duplicate: real impl now linked (ED_mesh_calc_tessface) */
void ED_mesh_calc_tessface(struct Mesh *mesh, bool free_mpoly) RET_NONE
#endif

/* bpy/python internal api */
extern void BPY_RNA_operator_wrapper(struct wmOperatorType *ot, void *userdata);
extern void BPY_RNA_operator_macro_wrapper(struct wmOperatorType *ot, void *userdata);
#ifndef WITH_BLENDER /* duplicate: real impl now linked (BPY_RNA_operator_wrapper) */
void BPY_RNA_operator_wrapper(struct wmOperatorType *ot, void *userdata) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (BPY_RNA_operator_macro_wrapper) */
void BPY_RNA_operator_macro_wrapper(struct wmOperatorType *ot, void *userdata) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (BPY_text_free_code) */
void BPY_text_free_code(struct Text *text) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (BPY_id_release) */
void BPY_id_release(struct ID *id) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (BPY_context_member_get) */
int BPY_context_member_get(struct bContext *C, const char *member, struct bContextDataResult *result) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (BPY_pyconstraint_target) */
void BPY_pyconstraint_target(struct bPythonConstraint *con, struct bConstraintTarget *ct) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (BPY_driver_exec) */
float BPY_driver_exec(PathResolvedRNA *anim_rna, struct ChannelDriver *driver, const float evaltime) RET_ZERO /* might need this one! */
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (BPY_DECREF) */
void BPY_DECREF(void *pyob_ptr) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (BPY_DECREF_RNA_INVALIDATE) */
void BPY_DECREF_RNA_INVALIDATE(void *pyob_ptr) RET_NONE;
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (BPY_pyconstraint_exec) */
void BPY_pyconstraint_exec(struct bPythonConstraint *con, struct bConstraintOb *cob, struct ListBase *targets) RET_NONE
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (pyrna_id_FromPyObject) */
bool pyrna_id_FromPyObject(struct PyObject *obj, struct ID **id) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (pyrna_id_CreatePyObject) */
struct PyObject *pyrna_id_CreatePyObject(struct ID *id) RET_NULL
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (pyrna_id_CheckPyObject) */
bool pyrna_id_CheckPyObject(struct PyObject *obj) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (BPY_context_update) */
void BPY_context_update(struct bContext *C) RET_NONE
#endif
const char *BPY_app_translations_py_pgettext(const char *msgctxt, const char *msgid) RET_ARG(msgid)

/* intern/dualcon */

void *dualcon(const DualConInput *input_mesh,
              /* callbacks for output */
              DualConAllocOutput alloc_output,
              DualConAddVert add_vert,
              DualConAddQuad add_quad,

              DualConFlags flags,
              DualConMode mode,
              float threshold,
              float hermite_num,
              float scale,
              int depth) RET_ZERO

/* compositor */
void COM_execute(RenderData *rd, Scene *scene, bNodeTree *editingtree, int rendering,
                 const ColorManagedViewSettings *viewSettings, const ColorManagedDisplaySettings *displaySettings,
                 const char *viewName) RET_NONE

/*multiview*/
#ifndef WITH_BLENDER /* duplicate: real impl now linked (RE_RenderResult_is_stereo) */
bool RE_RenderResult_is_stereo(RenderResult *res) RET_ZERO
#endif
#ifndef WITH_BLENDER /* duplicate: real impl now linked (uiTemplateImageViews) */
void uiTemplateImageViews(uiLayout *layout, struct PointerRNA *imfptr) RET_NONE
#endif

#endif // WITH_GAMEENGINE
