/*
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
 */

/** \file blender/blenloader/intern/versioning_defaults.c
 *  \ingroup blenloader
 */

#include "BLI_listbase.h"
#include "BLI_math.h"
#include "BLI_utildefines.h"

#include "DNA_brush_types.h"
#include "DNA_curve_types.h"
#include "DNA_freestyle_types.h"
#include "DNA_linestyle_types.h"
#include "DNA_material_types.h"
#include "DNA_mesh_types.h"
#include "DNA_object_types.h"
#include "DNA_scene_types.h"
#include "DNA_screen_types.h"
#include "DNA_space_types.h"
#include "DNA_userdef_types.h"
#include "DNA_world_types.h"

#include "BKE_brush.h"
#include "BKE_library.h"
#include "BKE_main.h"
#include "BKE_world.h"

#include "BLO_readfile.h"

/**
 * Override values in in-memory startup.blend, avoids resaving for small changes.
 */
void BLO_update_defaults_userpref_blend(void)
{
  /* defaults from T37518 */

  U.uiflag |= USER_DEPTH_CURSOR;
  U.uiflag |= USER_QUIT_PROMPT;
  U.uiflag |= USER_CONTINUOUS_MOUSE;

  /* See T45301 */
  U.uiflag |= USER_LOCK_CURSOR_ADJUST;

  U.versions = 1;
  U.savetime = 2;

  /* default from T47064 */
  U.audiorate = 48000;

  /* Keep this a very small, non-zero number so zero-alpha doesn't mask out objects behind it.
   * but take care since some hardware has driver bugs here (T46962).
   * Further hardware workarounds should be made in gpu_extensions.c */
  U.glalphaclip = (1.0f / 255);

  /* default so DPI is detected automatically */
  U.dpi = 0;
  U.ui_scale = 1.0f;

#ifdef WITH_PYTHON_SECURITY
  /* use alternative setting for security nuts
   * otherwise we'd need to patch the binary blob - startup.blend.c */
  U.flag |= USER_SCRIPT_AUTOEXEC_DISABLE;
#else
  U.flag &= ~USER_SCRIPT_AUTOEXEC_DISABLE;
#endif

  /* AnastacioEngine factory defaults (Preferences panels) */

  /* Interface */
  U.header_size = 26;
  /* USER_TOOLTIPS_PYTHON usa RNA_def_property_boolean_negative_sdna: o bit ligado
   * deixa a checkbox "Python Tooltips" desmarcada. Deixamos o bit desligado para
   * a checkbox vir marcada por padrao (testa o caminho de tooltip Python). */
  U.flag |= USER_TOOLTIPS | USER_DEVELOPER_UI | USER_SCENEGLOBAL;
  U.flag &= ~USER_TOOLTIPS_PYTHON;
  U.uiflag |= USER_SHOW_VIEWPORTNAME | USER_SHOW_FPS | USER_SHOW_ROTVIEWICON;
  U.uiflag &= ~USER_SPLASH_DISABLE; /* Show Splash */
  U.app_flag &= ~(USER_APP_LOCK_UI_LAYOUT | USER_APP_VIEW3D_HIDE_CURSOR); /* Show Layout Widgets / Show 3D View Cursor */
  U.obcenter_dia = 6;
  U.rvisize = 25;
  U.rvibright = 8;

  /* View Manipulation */
  U.uiflag |= USER_LOCKAROUND | USER_CAM_LOCK_NO_PARENT;
  U.uiflag &= ~(USER_DEPTH_NAVIGATE | USER_ZOOM_TO_MOUSEPOS | USER_ORBIT_SELECTION | USER_AUTOPERSP);
  U.smooth_viewtx = 200;
  U.pad_rot_angle = 15.0f;
  U.v2d_min_gridsize = 35;

  /* Menus / Pie Menus */
  U.uiflag |= USER_MENUOPENAUTO;
  U.menuthreshold1 = 5;
  U.menuthreshold2 = 2;
  U.pie_initial_timeout = 0;
  U.pie_animation_timeout = 6;
  U.pie_menu_radius = 100;
  U.pie_menu_threshold = 12;
  U.pie_menu_confirm = 0;

  /* Editing */
  U.flag &= ~USER_MAT_ON_OB; /* Link Materials To: ObData */
  U.flag &= ~USER_ADD_EDITMODE; /* Enter Edit Mode (new objects) */
  U.gp_eraser = 25;
  U.gp_manhattendist = 1;
  U.gp_euclideandist = 2;
  U.gp_settings &= ~GP_PAINT_DOSIMPLIFY; /* Simplify Stroke */
  copy_v4_fl4(U.gpencil_new_layer_col, 0.0f, 0.0f, 0.0f, 0.9f);
  U.uiflag |= USER_GLOBALUNDO;
  U.undosteps = 32;
  U.undomemory = 0;
  U.flag &= ~USER_NONEGFRAMES; /* Allow Negative Frames */
  U.node_margin = 80;
  U.fcu_inactive_alpha = 0.25f;
  U.autokey_mode = AUTOKEY_MODE_NORMAL; /* Auto Keyframing on + Show Auto Keying Warning */
  U.autokey_flag &= ~(AUTOKEY_FLAG_AUTOMATKEY | AUTOKEY_FLAG_INSERTNEEDED |
                       AUTOKEY_FLAG_INSERTAVAIL | AUTOKEY_FLAG_NOWARNING);
  U.ipo_new = BEZT_IPO_BEZ;
  U.keyhandles_new = HD_AUTO_ANIM;
  U.autokey_flag |= AUTOKEY_FLAG_XYZ2RGB;
  U.dupflag = USER_DUP_MESH | USER_DUP_SURF | USER_DUP_CURVE | USER_DUP_FONT |
              USER_DUP_MBALL | USER_DUP_ARM | USER_DUP_LAMP | USER_DUP_ACT;

  /* Input */
  U.dragthreshold = 5;
  U.tweak_threshold = 10;
  U.dbl_click_time = 350;
  U.flag &= ~USER_NONUMPAD; /* Emulate Numpad */
  U.flag &= ~USER_TRACKBALL; /* Orbit Style: Turntable */
  U.viewzoom = USER_ZOOM_DOLLY;
  U.uiflag &= ~(USER_ZOOM_INVERT | USER_ZOOM_HORIZ | USER_WHEELZOOMDIR);
  U.navigation_mode = VIEW_NAVIGATION_WALK;
  U.walk_navigation.mouse_speed = 1.0f;
  U.walk_navigation.walk_speed = 2.5f;
  U.walk_navigation.walk_speed_factor = 5.0f;
  U.walk_navigation.teleport_time = 0.2f;
  U.walk_navigation.flag &= ~(USER_WALK_GRAVITY | USER_WALK_MOUSE_REVERSE);
  U.ndof_sensitivity = 1.0f;
  U.ndof_orbit_sensitivity = 1.0f;
  U.ndof_deadzone = 0.1f;
  U.ndof_flag &= ~NDOF_MODE_ORBIT; /* Navigation Style: Free */
  U.ndof_flag |= NDOF_TURNTABLE; /* Rotation Style: Turntable */

  /* System / General */
  U.frameserverport = 8080;
  U.scrollback = 256;
  U.mixbufsize = 2048;
  U.glalphaclip = 0.004f;
  U.use_gpu_mipmap = 1;
  U.use_16bit_textures = 1;
  U.gameflags &= ~USER_DISABLE_MIPMAP;
  U.gpu_select_method = USER_SELECT_AUTO; /* Selection: Automatic (also clears OpenGL Depth Picking) */
  U.wmdrawmethod = USER_DRAW_AUTOMATIC;
  U.ogl_multisamples = USER_MULTISAMPLE_NONE;
  U.uiflag2 &= ~USER_REGION_OVERLAP;
  U.text_render &= ~USER_TEXT_DISABLE_AA;
  U.textimeout = 120;
  U.texcollectrate = 60;
  U.image_draw_method = IMAGE_DRAW_METHOD_2DTEXTURE;
  U.memcachelimit = 1024;

  /* Files */
  U.flag |= USER_RELPATHS;
  U.flag &= ~USER_FILECOMPRESS; /* Compress File */
  U.uiflag |= USER_FILTERFILEEXTS | USER_HIDE_DOT;
  U.flag &= ~USER_FILENOUI; /* Load UI */
  U.uiflag &= ~(USER_HIDE_RECENT | USER_HIDE_SYSTEM_BOOKMARKS | USER_SHOW_THUMBNAILS);
  U.versions = 1;
  U.recent_files = 10;
  U.flag |= USER_SAVE_PREVIEWS;
  U.uiflag2 &= ~USER_KEEP_SESSION;
  U.flag |= USER_AUTOSAVE;
  U.flag &= ~USER_TXT_TABSTOSPACES_DISABLE;
}

/**
 * Update defaults in startup.blend, without having to save and embed the file.
 * This function can be emptied each time the startup.blend is updated. */
void BLO_update_defaults_startup_blend(Main *bmain)
{
  /* The embedded startup.blend already holds a World, so BKE_world_init() never runs for it. */
  for (World *wrld = bmain->world.first; wrld; wrld = wrld->id.next) {
    BKE_world_status_props_ensure(wrld);
  }

  for (Scene *scene = bmain->scene.first; scene; scene = scene->id.next) {
    scene->r.im_format.planes = R_IMF_PLANES_RGBA;
    scene->r.im_format.compress = 15;

    for (SceneRenderLayer *srl = scene->r.layers.first; srl; srl = srl->next) {
      srl->freestyleConfig.sphere_radius = 0.1f;
      srl->pass_alpha_threshold = 0.5f;
    }

    if (scene->toolsettings) {
      ToolSettings *ts = scene->toolsettings;

      if (ts->sculpt) {
        Sculpt *sculpt = ts->sculpt;
        sculpt->paint.symmetry_flags |= PAINT_SYMM_X;
        sculpt->flags |= SCULPT_DYNTOPO_COLLAPSE;
        sculpt->detail_size = 12;
      }

      if (ts->vpaint) {
        VPaint *vp = ts->vpaint;
        vp->radial_symm[0] = vp->radial_symm[1] = vp->radial_symm[2] = 1;
      }

      if (ts->wpaint) {
        VPaint *wp = ts->wpaint;
        wp->radial_symm[0] = wp->radial_symm[1] = wp->radial_symm[2] = 1;
      }

      if (ts->gp_sculpt.brush[0].size == 0) {
        GP_BrushEdit_Settings *gset = &ts->gp_sculpt;
        GP_EditBrush_Data *brush;

        brush = &gset->brush[GP_EDITBRUSH_TYPE_SMOOTH];
        brush->size = 25;
        brush->strength = 0.3f;
        brush->flag = GP_EDITBRUSH_FLAG_USE_FALLOFF | GP_EDITBRUSH_FLAG_SMOOTH_PRESSURE;

        brush = &gset->brush[GP_EDITBRUSH_TYPE_THICKNESS];
        brush->size = 25;
        brush->strength = 0.5f;
        brush->flag = GP_EDITBRUSH_FLAG_USE_FALLOFF;

        brush = &gset->brush[GP_EDITBRUSH_TYPE_STRENGTH];
        brush->size = 25;
        brush->strength = 0.5f;
        brush->flag = GP_EDITBRUSH_FLAG_USE_FALLOFF;

        brush = &gset->brush[GP_EDITBRUSH_TYPE_GRAB];
        brush->size = 50;
        brush->strength = 0.3f;
        brush->flag = GP_EDITBRUSH_FLAG_USE_FALLOFF;

        brush = &gset->brush[GP_EDITBRUSH_TYPE_PUSH];
        brush->size = 25;
        brush->strength = 0.3f;
        brush->flag = GP_EDITBRUSH_FLAG_USE_FALLOFF;

        brush = &gset->brush[GP_EDITBRUSH_TYPE_TWIST];
        brush->size = 50;
        brush->strength = 0.3f;  // XXX?
        brush->flag = GP_EDITBRUSH_FLAG_USE_FALLOFF;

        brush = &gset->brush[GP_EDITBRUSH_TYPE_PINCH];
        brush->size = 50;
        brush->strength = 0.5f;  // XXX?
        brush->flag = GP_EDITBRUSH_FLAG_USE_FALLOFF;

        brush = &gset->brush[GP_EDITBRUSH_TYPE_RANDOMIZE];
        brush->size = 25;
        brush->strength = 0.5f;
        brush->flag = GP_EDITBRUSH_FLAG_USE_FALLOFF;
      }

      ts->gpencil_v3d_align = GP_PROJECT_VIEWSPACE;
      ts->gpencil_v2d_align = GP_PROJECT_VIEWSPACE;
      ts->gpencil_seq_align = GP_PROJECT_VIEWSPACE;
      ts->gpencil_ima_align = GP_PROJECT_VIEWSPACE;

      ParticleEditSettings *pset = &ts->particle;
      for (int a = 0; a < ARRAY_SIZE(pset->brush); a++) {
        pset->brush[a].strength = 0.5f;
        pset->brush[a].count = 10;
      }
      pset->brush[PE_BRUSH_CUT].strength = 1.0f;
    }

    scene->gm.lodflag |= SCE_LOD_USE_HYST;
    scene->gm.scehysteresis = 10;

    scene->r.ffcodecdata.audio_mixrate = 48000;
  }

  for (FreestyleLineStyle *linestyle = bmain->linestyle.first; linestyle;
       linestyle = linestyle->id.next)
  {
    linestyle->flag = LS_SAME_OBJECT | LS_NO_SORTING | LS_TEXTURE;
    linestyle->sort_key = LS_SORT_KEY_DISTANCE_FROM_CAMERA;
    linestyle->integration_type = LS_INTEGRATION_MEAN;
    linestyle->texstep = 1.0;
    linestyle->chain_count = 10;
  }

  for (bScreen *screen = bmain->screen.first; screen; screen = screen->id.next) {
    ScrArea *area;
    for (area = screen->areabase.first; area; area = area->next) {
      SpaceLink *space_link;
      ARegion *ar;

      for (space_link = area->spacedata.first; space_link; space_link = space_link->next) {
        if (space_link->spacetype == SPACE_CLIP) {
          SpaceClip *space_clip = (SpaceClip *)space_link;
          space_clip->flag &= ~SC_MANUAL_CALIBRATION;
        }
      }

      for (ar = area->regionbase.first; ar; ar = ar->next) {
        /* Remove all stored panels, we want to use defaults (order, open/closed) as defined by UI
         * code here! */
        BLI_freelistN(&ar->panels);

        /* some toolbars have been saved as initialized,
         * we don't want them to have odd zoom-level or scrolling set, see: T47047 */
        if (ELEM(ar->regiontype, RGN_TYPE_UI, RGN_TYPE_TOOLS, RGN_TYPE_TOOL_PROPS)) {
          ar->v2d.flag &= ~V2D_IS_INITIALISED;
        }
      }
    }
  }

  for (Mesh *me = bmain->mesh.first; me; me = me->id.next) {
    me->smoothresh = DEG2RADF(180.0f);
    me->flag &= ~ME_TWOSIDED;
  }

  for (Material *mat = bmain->mat.first; mat; mat = mat->id.next) {
    mat->line_col[0] = mat->line_col[1] = mat->line_col[2] = 0.0f;
    mat->line_col[3] = 1.0f;
  }

  {
    Object *ob;

    ob = (Object *)BKE_libblock_find_name(bmain, ID_OB, "Camera");
    if (ob) {
      ob->rot[1] = 0.0f;
    }
  }

  {
    Brush *br;

    br = (Brush *)BKE_libblock_find_name(bmain, ID_BR, "Fill");
    if (!br) {
      br = BKE_brush_add(bmain, "Fill", OB_MODE_TEXTURE_PAINT);
      id_us_min(&br->id); /* fake user only */
      br->imagepaint_tool = PAINT_TOOL_FILL;
      br->ob_mode = OB_MODE_TEXTURE_PAINT;
    }

    /* Vertex/Weight Paint */
    br = (Brush *)BKE_libblock_find_name(bmain, ID_BR, "Average");
    if (!br) {
      br = BKE_brush_add(bmain, "Average", OB_MODE_VERTEX_PAINT | OB_MODE_WEIGHT_PAINT);
      id_us_min(&br->id); /* fake user only */
      br->vertexpaint_tool = PAINT_BLEND_AVERAGE;
      br->ob_mode = OB_MODE_VERTEX_PAINT | OB_MODE_WEIGHT_PAINT;
    }
    br = (Brush *)BKE_libblock_find_name(bmain, ID_BR, "Smear");
    if (!br) {
      br = BKE_brush_add(bmain, "Smear", OB_MODE_VERTEX_PAINT | OB_MODE_WEIGHT_PAINT);
      id_us_min(&br->id); /* fake user only */
      br->vertexpaint_tool = PAINT_BLEND_SMEAR;
      br->ob_mode = OB_MODE_VERTEX_PAINT | OB_MODE_WEIGHT_PAINT;
    }

    br = (Brush *)BKE_libblock_find_name(bmain, ID_BR, "Mask");
    if (br) {
      br->imagepaint_tool = PAINT_TOOL_MASK;
      br->ob_mode |= OB_MODE_TEXTURE_PAINT;
    }

    /* remove polish brush (flatten/contrast does the same) */
    br = (Brush *)BKE_libblock_find_name(bmain, ID_BR, "Polish");
    if (br) {
      BKE_libblock_delete(bmain, br);
    }

    /* remove brush brush (huh?) from some modes (draw brushes do the same) */
    br = (Brush *)BKE_libblock_find_name(bmain, ID_BR, "Brush");
    if (br) {
      BKE_libblock_delete(bmain, br);
    }

    /* remove draw brush from texpaint (draw brushes do the same) */
    br = (Brush *)BKE_libblock_find_name(bmain, ID_BR, "Draw");
    if (br) {
      br->ob_mode &= ~OB_MODE_TEXTURE_PAINT;
    }

    /* rename twist brush to rotate brush to match rotate tool */
    br = (Brush *)BKE_libblock_find_name(bmain, ID_BR, "Twist");
    if (br) {
      BKE_libblock_rename(bmain, &br->id, "Rotate");
    }

    /* use original normal for grab brush (otherwise flickers with normal weighting). */
    br = (Brush *)BKE_libblock_find_name(bmain, ID_BR, "Grab");
    if (br) {
      br->flag |= BRUSH_ORIGINAL_NORMAL;
    }

    /* increase strength, better for smoothing method */
    br = (Brush *)BKE_libblock_find_name(bmain, ID_BR, "Blur");
    if (br) {
      br->alpha = 1.0f;
    }

    br = (Brush *)BKE_libblock_find_name(bmain, ID_BR, "Flatten/Contrast");
    if (br) {
      br->flag |= BRUSH_ACCUMULATE;
    }
  }
}
