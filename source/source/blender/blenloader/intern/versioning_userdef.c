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
 * ***** END GPL LICENSE BLOCK *****
 *
 */

/** \file blender/blenloader/intern/versioning_userdef.c
 *  \ingroup blenloader
 *
 * Version patch user preferences.
 */

#include <string.h>

#include "BLI_utildefines.h"

#include "DNA_curve_types.h"
#include "DNA_userdef_types.h"
#include "DNA_windowmanager_types.h"

#include "BLI_math.h"

#include "BKE_addon.h"
#include "BKE_colorband.h"
#include "BKE_main.h"

#include "BLO_readfile.h" /* Own include. */

#define U (_error_)

/* patching UserDef struct and Themes */
void BLO_version_defaults_userpref_blend(UserDef *userdef)
{
  /* #UserDef & #Main happen to have the same struct member. */
#define USER_VERSION_ATLEAST(ver, subver) MAIN_VERSION_ATLEAST(userdef, ver, subver)

  /* the UserDef struct is not corrected with do_versions() .... ugh! */
  if (userdef->wheellinescroll == 0)
    userdef->wheellinescroll = 3;
  if (userdef->menuthreshold1 == 0) {
    userdef->menuthreshold1 = 5;
    userdef->menuthreshold2 = 2;
  }
  if (userdef->tb_leftmouse == 0) {
    userdef->tb_leftmouse = 5;
    userdef->tb_rightmouse = 5;
  }
  if (userdef->mixbufsize == 0)
    userdef->mixbufsize = 2048;
  if (userdef->autokey_mode == 0) {
    /* 'add/replace' but not on */
    userdef->autokey_mode = 2;
  }
  if (userdef->savetime <= 0) {
    userdef->savetime = 1;
    // XXX		error(STRINGIFY(BLENDER_STARTUP_FILE)" is buggy, please consider removing it.\n");
  }
  if (userdef->pad_rot_angle == 0.0f)
    userdef->pad_rot_angle = 15.0f;

  /* graph editor - unselected F-Curve visibility */
  if (userdef->fcu_inactive_alpha == 0) {
    userdef->fcu_inactive_alpha = 0.25f;
  }

  if (!USER_VERSION_ATLEAST(192, 0)) {
    strcpy(userdef->sounddir, "/");
  }

  /* patch to set Dupli Armature */
  if (!USER_VERSION_ATLEAST(220, 0)) {
    userdef->dupflag |= USER_DUP_ARM;
  }

  /* added seam, normal color, undo */
  if (!USER_VERSION_ATLEAST(235, 0)) {
    bTheme *btheme;

    userdef->uiflag |= USER_GLOBALUNDO;
    if (userdef->undosteps == 0)
      userdef->undosteps = 32;

    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      /* check for (alpha == 0) is safe, then color was never set */
      if (btheme->tv3d.edge_seam[3] == 0) {
        rgba_char_args_set(btheme->tv3d.edge_seam, 230, 150, 50, 255);
      }
      if (btheme->tv3d.normal[3] == 0) {
        rgba_char_args_set(btheme->tv3d.normal, 0x22, 0xDD, 0xDD, 255);
      }
      if (btheme->tv3d.vertex_normal[3] == 0) {
        rgba_char_args_set(btheme->tv3d.vertex_normal, 0x23, 0x61, 0xDD, 255);
      }
      if (btheme->tv3d.face_dot[3] == 0) {
        rgba_char_args_set(btheme->tv3d.face_dot, 255, 138, 48, 255);
        btheme->tv3d.facedot_size = 4;
      }
    }
  }
  if (!USER_VERSION_ATLEAST(236, 0)) {
    /* illegal combo... */
    if (userdef->flag & USER_LMOUSESELECT)
      userdef->flag &= ~USER_TWOBUTTONMOUSE;
  }
  if (!USER_VERSION_ATLEAST(237, 0)) {
    bTheme *btheme;
    /* new space type */
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      /* check for (alpha == 0) is safe, then color was never set */
      if (btheme->ttime.back[3] == 0) {
        /* copied from ui_theme_init_default */
        btheme->ttime = btheme->tv3d;
        rgba_char_args_set_fl(btheme->ttime.back, 0.45, 0.45, 0.45, 1.0);
        rgba_char_args_set_fl(btheme->ttime.grid, 0.36, 0.36, 0.36, 1.0);
        rgba_char_args_set(btheme->ttime.shade1, 173, 173, 173, 255); /* sliders */
      }
      if (btheme->text.syntaxn[3] == 0) {
        rgba_char_args_set(btheme->text.syntaxn, 0, 0, 200, 255);  /* Numbers  Blue*/
        rgba_char_args_set(btheme->text.syntaxl, 100, 0, 0, 255);  /* Strings  red */
        rgba_char_args_set(btheme->text.syntaxc, 0, 100, 50, 255); /* Comments greenish */
        rgba_char_args_set(btheme->text.syntaxv, 95, 95, 0, 255);  /* Special */
        rgba_char_args_set(btheme->text.syntaxb, 128, 0, 80, 255); /* Builtin, red-purple */
      }
    }
  }
  if (!USER_VERSION_ATLEAST(238, 0)) {
    bTheme *btheme;
    /* bone colors */
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      /* check for alpha==0 is safe, then color was never set */
      if (btheme->tv3d.bone_solid[3] == 0) {
        rgba_char_args_set(btheme->tv3d.bone_solid, 200, 200, 200, 255);
        rgba_char_args_set(btheme->tv3d.bone_pose, 80, 200, 255, 80);
      }
    }
  }
  if (!USER_VERSION_ATLEAST(239, 0)) {
    bTheme *btheme;
    /* bone colors */
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      /* check for alpha==0 is safe, then color was never set */
      if (btheme->tnla.strip[3] == 0) {
        rgba_char_args_set(btheme->tnla.strip_select, 0xff, 0xff, 0xaa, 255);
        rgba_char_args_set(btheme->tnla.strip, 0xe4, 0x9c, 0xc6, 255);
      }
    }
  }
  if (!USER_VERSION_ATLEAST(240, 0)) {
    bTheme *btheme;

    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      /* Lamp theme, check for alpha==0 is safe, then color was never set */
      if (btheme->tv3d.lamp[3] == 0) {
        rgba_char_args_set(btheme->tv3d.lamp, 0, 0, 0, 40);
        /* TEMPORAL, remove me! (ton) */
        userdef->uiflag |= USER_PLAINMENUS;
      }
    }
    if (userdef->obcenter_dia == 0)
      userdef->obcenter_dia = 6;
  }
  if (!USER_VERSION_ATLEAST(242, 0)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      /* Node editor theme, check for alpha==0 is safe, then color was never set */
      if (btheme->tnode.syntaxn[3] == 0) {
        /* re-uses syntax color storage */
        btheme->tnode = btheme->tv3d;
        rgba_char_args_set(btheme->tnode.edge_select, 255, 255, 255, 255);
        rgba_char_args_set(btheme->tnode.syntaxl, 150, 150, 150, 255); /* TH_NODE, backdrop */
        rgba_char_args_set(btheme->tnode.syntaxn, 129, 131, 144, 255); /* in/output */
        rgba_char_args_set(btheme->tnode.syntaxb, 127, 127, 127, 255); /* operator */
        rgba_char_args_set(btheme->tnode.syntaxv, 142, 138, 145, 255); /* generator */
        rgba_char_args_set(btheme->tnode.syntaxc, 120, 145, 120, 255); /* group */
      }
      /* Group theme colors */
      if (btheme->tv3d.group[3] == 0) {
        rgba_char_args_set(btheme->tv3d.group, 0x0C, 0x30, 0x0C, 255);
        rgba_char_args_set(btheme->tv3d.group_active, 0x66, 0xFF, 0x66, 255);
      }
      /* Sequence editor theme*/
      if (btheme->tseq.movie[3] == 0) {
        rgba_char_args_set(btheme->tseq.movie, 81, 105, 135, 255);
        rgba_char_args_set(btheme->tseq.image, 109, 88, 129, 255);
        rgba_char_args_set(btheme->tseq.scene, 78, 152, 62, 255);
        rgba_char_args_set(btheme->tseq.audio, 46, 143, 143, 255);
        rgba_char_args_set(btheme->tseq.effect, 169, 84, 124, 255);
        rgba_char_args_set(btheme->tseq.transition, 162, 95, 111, 255);
        rgba_char_args_set(btheme->tseq.meta, 109, 145, 131, 255);
      }
    }

    /* set defaults for 3D View rotating axis indicator */
    /* since size can't be set to 0, this indicates it's not saved in startup.blend */
    if (userdef->rvisize == 0) {
      userdef->rvisize = 15;
      userdef->rvibright = 8;
      userdef->uiflag |= USER_SHOW_ROTVIEWICON;
    }
  }
  if (!USER_VERSION_ATLEAST(243, 0)) {
    bTheme *btheme;

    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      /* long keyframe color */
      /* check for alpha==0 is safe, then color was never set */
      if (btheme->tact.strip[3] == 0) {
        rgba_char_args_set(btheme->tv3d.edge_sharp, 255, 32, 32, 255);
        rgba_char_args_set(btheme->tact.strip_select, 0xff, 0xff, 0xaa, 204);
        rgba_char_args_set(btheme->tact.strip, 0xe4, 0x9c, 0xc6, 204);
      }

      /* IPO-Editor - Vertex Size*/
      if (btheme->tipo.vertex_size == 0) {
        btheme->tipo.vertex_size = 3;
      }
    }
  }
  if (!USER_VERSION_ATLEAST(244, 0)) {
    /* set default number of recently-used files (if not set) */
    if (userdef->recent_files == 0)
      userdef->recent_files = 10;
  }
  if (!USER_VERSION_ATLEAST(245, 3)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      rgba_char_args_set(btheme->tv3d.editmesh_active, 255, 255, 255, 128);
    }
    if (userdef->coba_weight.tot == 0)
      BKE_colorband_init(&userdef->coba_weight, true);
  }
  if (!USER_VERSION_ATLEAST(245, 3)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      /* these should all use the same color */
      rgba_char_args_set(btheme->tv3d.cframe, 0x60, 0xc0, 0x40, 255);
      rgba_char_args_set(btheme->tipo.cframe, 0x60, 0xc0, 0x40, 255);
      rgba_char_args_set(btheme->tact.cframe, 0x60, 0xc0, 0x40, 255);
      rgba_char_args_set(btheme->tnla.cframe, 0x60, 0xc0, 0x40, 255);
      rgba_char_args_set(btheme->tseq.cframe, 0x60, 0xc0, 0x40, 255);
      // rgba_char_args_set(btheme->tsnd.cframe, 0x60, 0xc0, 0x40, 255); Not needed anymore
      rgba_char_args_set(btheme->ttime.cframe, 0x60, 0xc0, 0x40, 255);
    }
  }
  if (!USER_VERSION_ATLEAST(245, 3)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      /* action channel groups (recolor anyway) */
      rgba_char_args_set(btheme->tact.group, 0x39, 0x7d, 0x1b, 255);
      rgba_char_args_set(btheme->tact.group_active, 0x7d, 0xe9, 0x60, 255);

      /* bone custom-color sets */
      /*if (btheme->tarm[0].solid[3] == 0)
        ui_theme_init_boneColorSets(btheme);*/
    }
  }
  if (!USER_VERSION_ATLEAST(245, 3)) {
    userdef->flag |= USER_ADD_EDITMODE;
  }
  if (!USER_VERSION_ATLEAST(245, 3)) {
    bTheme *btheme;

    /* adjust themes */
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      const char *col;

      /* IPO Editor: Handles/Vertices */
      col = btheme->tipo.vertex;
      rgba_char_args_set(btheme->tipo.handle_vertex, col[0], col[1], col[2], 255);
      col = btheme->tipo.vertex_select;
      rgba_char_args_set(btheme->tipo.handle_vertex_select, col[0], col[1], col[2], 255);
      btheme->tipo.handle_vertex_size = btheme->tipo.vertex_size;

      /* Sequence/Image Editor: colors for GPencil text */
      col = btheme->tv3d.bone_pose;
      rgba_char_args_set(btheme->tseq.bone_pose, col[0], col[1], col[2], 255);
      rgba_char_args_set(btheme->tima.bone_pose, col[0], col[1], col[2], 255);
      col = btheme->tv3d.vertex_select;
      rgba_char_args_set(btheme->tseq.vertex_select, col[0], col[1], col[2], 255);
    }
  }
  if (!USER_VERSION_ATLEAST(250, 0)) {
    bTheme *btheme;

    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      /* this was not properly initialized in 2.45 */
      if (btheme->tima.face_dot[3] == 0) {
        rgba_char_args_set(btheme->tima.editmesh_active, 255, 255, 255, 128);
        rgba_char_args_set(btheme->tima.face_dot, 255, 133, 0, 255);
        btheme->tima.facedot_size = 2;
      }

      /* DopeSheet - (Object) Channel color */
      rgba_char_args_set(btheme->tact.ds_channel, 82, 96, 110, 255);
      rgba_char_args_set(btheme->tact.ds_subchannel, 124, 137, 150, 255);
      /* DopeSheet - Group Channel color (saner version) */
      rgba_char_args_set(btheme->tact.group, 79, 101, 73, 255);
      rgba_char_args_set(btheme->tact.group_active, 135, 177, 125, 255);

      /* Graph Editor - (Object) Channel color */
      rgba_char_args_set(btheme->tipo.ds_channel, 82, 96, 110, 255);
      rgba_char_args_set(btheme->tipo.ds_subchannel, 124, 137, 150, 255);
      /* Graph Editor - Group Channel color */
      rgba_char_args_set(btheme->tipo.group, 79, 101, 73, 255);
      rgba_char_args_set(btheme->tipo.group_active, 135, 177, 125, 255);

      /* Nla Editor - (Object) Channel color */
      rgba_char_args_set(btheme->tnla.ds_channel, 82, 96, 110, 255);
      rgba_char_args_set(btheme->tnla.ds_subchannel, 124, 137, 150, 255);
      /* NLA Editor - New Strip colors */
      rgba_char_args_set(btheme->tnla.strip, 12, 10, 10, 128);
      rgba_char_args_set(btheme->tnla.strip_select, 255, 140, 0, 255);
    }

    /* adjust grease-pencil distances */
    userdef->gp_manhattendist = 1;
    userdef->gp_euclideandist = 2;

    /* adjust default interpolation for new IPO-curves */
    userdef->ipo_new = BEZT_IPO_BEZ;
  }

  if (!USER_VERSION_ATLEAST(250, 1)) {
    bTheme *btheme;

    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {

      /* common (new) variables, it checks for alpha==0 */
      // ui_theme_init_new(btheme);

      if (btheme->tui.wcol_num.outline[3] == 0)
        // ui_widget_color_init(&btheme->tui);

        /* Logic editor theme, check for alpha==0 is safe, then color was never set */
        if (btheme->tlogic.syntaxn[3] == 0) {
          /* re-uses syntax color storage */
          btheme->tlogic = btheme->tv3d;
          rgba_char_args_set(btheme->tlogic.back, 100, 100, 100, 255);
        }

      rgba_char_args_set_fl(btheme->tinfo.back, 0.45, 0.45, 0.45, 1.0);
      rgba_char_args_set_fl(btheme->tuserpref.back, 0.45, 0.45, 0.45, 1.0);
    }
  }

  if (!USER_VERSION_ATLEAST(250, 3)) {
    /* new audio system */
    if (userdef->audiochannels == 0)
      userdef->audiochannels = 2;
    if (userdef->audiodevice == 0) {
#ifdef WITH_OPENAL
      userdef->audiodevice = 2;
#endif
#ifdef WITH_SDL
      userdef->audiodevice = 1;
#endif
    }
    if (userdef->audioformat == 0)
      userdef->audioformat = 0x24;
    if (userdef->audiorate == 0)
      userdef->audiorate = 48000;
  }

  if (!USER_VERSION_ATLEAST(250, 8)) {
    wmKeyMap *km;

    for (km = userdef->user_keymaps.first; km; km = km->next) {
      if (STREQ(km->idname, "Armature_Sketch"))
        strcpy(km->idname, "Armature Sketch");
      else if (STREQ(km->idname, "View3D"))
        strcpy(km->idname, "3D View");
      else if (STREQ(km->idname, "View3D Generic"))
        strcpy(km->idname, "3D View Generic");
      else if (STREQ(km->idname, "EditMesh"))
        strcpy(km->idname, "Mesh");
      else if (STREQ(km->idname, "TimeLine"))
        strcpy(km->idname, "Timeline");
      else if (STREQ(km->idname, "UVEdit"))
        strcpy(km->idname, "UV Editor");
      else if (STREQ(km->idname, "Animation_Channels"))
        strcpy(km->idname, "Animation Channels");
      else if (STREQ(km->idname, "GraphEdit Keys"))
        strcpy(km->idname, "Graph Editor");
      else if (STREQ(km->idname, "GraphEdit Generic"))
        strcpy(km->idname, "Graph Editor Generic");
      else if (STREQ(km->idname, "Action_Keys"))
        strcpy(km->idname, "Dopesheet");
      else if (STREQ(km->idname, "NLA Data"))
        strcpy(km->idname, "NLA Editor");
      else if (STREQ(km->idname, "Node Generic"))
        strcpy(km->idname, "Node Editor");
      else if (STREQ(km->idname, "Logic Generic"))
        strcpy(km->idname, "Logic Editor");
      else if (STREQ(km->idname, "File"))
        strcpy(km->idname, "File Browser");
      else if (STREQ(km->idname, "FileMain"))
        strcpy(km->idname, "File Browser Main");
      else if (STREQ(km->idname, "FileButtons"))
        strcpy(km->idname, "File Browser Buttons");
      else if (STREQ(km->idname, "Buttons Generic"))
        strcpy(km->idname, "Property Editor");
    }
  }
  if (!USER_VERSION_ATLEAST(250, 16)) {
    if (userdef->wmdrawmethod == USER_DRAW_TRIPLE)
      userdef->wmdrawmethod = USER_DRAW_AUTOMATIC;
  }

  if (!USER_VERSION_ATLEAST(252, 3)) {
    if (userdef->flag & USER_LMOUSESELECT)
      userdef->flag &= ~USER_TWOBUTTONMOUSE;
  }
  if (!USER_VERSION_ATLEAST(252, 4)) {
    bTheme *btheme;

    /* default new handle type is auto handles */
    userdef->keyhandles_new = HD_AUTO;

    /* init new curve colors */
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      // ui_theme_space_init_handles_color(&btheme->tv3d);
      // ui_theme_space_init_handles_color(&btheme->tipo);

      /* edge crease */
      rgba_char_args_set_fl(btheme->tv3d.edge_crease, 0.8, 0, 0.6, 1.0);
    }
  }
  if (!USER_VERSION_ATLEAST(253, 0)) {
    bTheme *btheme;

    /* init new curve colors */
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      if (btheme->tv3d.lastsel_point[3] == 0)
        rgba_char_args_set(btheme->tv3d.lastsel_point, 0xff, 0xff, 0xff, 255);
    }
  }
  if (!USER_VERSION_ATLEAST(252, 5)) {
    bTheme *btheme;

    /* interface_widgets.c */
    struct uiWidgetColors wcol_progress = {{0, 0, 0, 255},
                                           {190, 190, 190, 255},
                                           {100, 100, 100, 180},
                                           {128, 128, 128, 255},

                                           {0, 0, 0, 255},
                                           {255, 255, 255, 255},

                                           0,
                                           5,
                                           -5};

    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      /* init progress bar theme */
      btheme->tui.wcol_progress = wcol_progress;
    }
  }

  if (!USER_VERSION_ATLEAST(255, 2)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      rgba_char_args_set(btheme->tv3d.extra_edge_len, 32, 0, 0, 255);
      rgba_char_args_set(btheme->tv3d.extra_face_angle, 0, 32, 0, 255);
      rgba_char_args_set(btheme->tv3d.extra_face_area, 0, 0, 128, 255);
    }
  }

  if (!USER_VERSION_ATLEAST(256, 4)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      if ((btheme->tv3d.outline_width) == 0)
        btheme->tv3d.outline_width = 1;
    }
  }

  if (!USER_VERSION_ATLEAST(257, 0)) {
    /* clear "AUTOKEY_FLAG_ONLYKEYINGSET" flag from userprefs,
     * so that it doesn't linger around from old configs like a ghost */
    userdef->autokey_flag &= ~AUTOKEY_FLAG_ONLYKEYINGSET;
  }

  if (!USER_VERSION_ATLEAST(258, 2)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      btheme->tnode.noodle_curving = 5;
    }
  }

  if (!USER_VERSION_ATLEAST(259, 1)) {
    bTheme *btheme;

    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      btheme->tv3d.speaker[3] = 255;
    }
  }

  if (!USER_VERSION_ATLEAST(260, 3)) {
    bTheme *btheme;

    /* if new keyframes handle default is stuff "auto", make it "auto-clamped" instead
     * was changed in 260 as part of GSoC11, but version patch was wrong
     */
    if (userdef->keyhandles_new == HD_AUTO)
      userdef->keyhandles_new = HD_AUTO_ANIM;

    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      if (btheme->tv3d.bundle_solid[3] == 0)
        rgba_char_args_set(btheme->tv3d.bundle_solid, 200, 200, 200, 255);

      if (btheme->tv3d.camera_path[3] == 0)
        rgba_char_args_set(btheme->tv3d.camera_path, 0x00, 0x00, 0x00, 255);

      if ((btheme->tclip.back[3]) == 0) {
        btheme->tclip = btheme->tv3d;

        rgba_char_args_set(btheme->tclip.marker_outline, 0x00, 0x00, 0x00, 255);
        rgba_char_args_set(btheme->tclip.marker, 0x7f, 0x7f, 0x00, 255);
        rgba_char_args_set(btheme->tclip.act_marker, 0xff, 0xff, 0xff, 255);
        rgba_char_args_set(btheme->tclip.sel_marker, 0xff, 0xff, 0x00, 255);
        rgba_char_args_set(btheme->tclip.dis_marker, 0x7f, 0x00, 0x00, 255);
        rgba_char_args_set(btheme->tclip.lock_marker, 0x7f, 0x7f, 0x7f, 255);
        rgba_char_args_set(btheme->tclip.path_before, 0xff, 0x00, 0x00, 255);
        rgba_char_args_set(btheme->tclip.path_after, 0x00, 0x00, 0xff, 255);
        rgba_char_args_set(btheme->tclip.grid, 0x5e, 0x5e, 0x5e, 255);
        rgba_char_args_set(btheme->tclip.cframe, 0x60, 0xc0, 0x40, 255);
        rgba_char_args_set(btheme->tclip.handle_vertex, 0x00, 0x00, 0x00, 0xff);
        rgba_char_args_set(btheme->tclip.handle_vertex_select, 0xff, 0xff, 0, 0xff);
        btheme->tclip.handle_vertex_size = 5;
      }

      /* auto-clamped handles -> based on auto */
      if (btheme->tipo.handle_auto_clamped[3] == 0)
        rgba_char_args_set(btheme->tipo.handle_auto_clamped, 0x99, 0x40, 0x30, 255);
      if (btheme->tipo.handle_sel_auto_clamped[3] == 0)
        rgba_char_args_set(btheme->tipo.handle_sel_auto_clamped, 0xf0, 0xaf, 0x90, 255);
    }

    /* enable (Cycles) addon by default */
    BKE_addon_ensure(&userdef->addons, "cycles");
  }

  if (!USER_VERSION_ATLEAST(260, 5)) {
    bTheme *btheme;

    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      rgba_char_args_set(btheme->tui.panel.header, 0, 0, 0, 25);
      btheme->tui.icon_alpha = 1.0;
    }
  }

  if (!USER_VERSION_ATLEAST(261, 4)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      rgba_char_args_set_fl(btheme->tima.preview_stitch_face, 0.071, 0.259, 0.694, 0.150);
      rgba_char_args_set_fl(btheme->tima.preview_stitch_edge, 1.0, 0.522, 0.0, 0.7);
      rgba_char_args_set_fl(btheme->tima.preview_stitch_vert, 1.0, 0.522, 0.0, 0.5);
      rgba_char_args_set_fl(btheme->tima.preview_stitch_stitchable, 0.0, 1.0, 0.0, 1.0);
      rgba_char_args_set_fl(btheme->tima.preview_stitch_unstitchable, 1.0, 0.0, 0.0, 1.0);
      rgba_char_args_set_fl(btheme->tima.preview_stitch_active, 0.886, 0.824, 0.765, 0.140);

      rgba_char_args_set_fl(btheme->toops.match, 0.2, 0.5, 0.2, 0.3);
      rgba_char_args_set_fl(btheme->toops.selected_highlight, 0.51, 0.53, 0.55, 0.3);
    }

    userdef->use_16bit_textures = true;
  }

  if (!USER_VERSION_ATLEAST(262, 2)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      if (btheme->tui.wcol_menu_item.item[3] == 255)
        rgba_char_args_set(btheme->tui.wcol_menu_item.item, 172, 172, 172, 128);
    }
  }

  if (!USER_VERSION_ATLEAST(262, 3)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      if (btheme->tui.wcol_tooltip.inner[3] == 0) {
        btheme->tui.wcol_tooltip = btheme->tui.wcol_menu_back;
      }
      if (btheme->tui.wcol_tooltip.text[0] == 160) { /* hrmf */
        rgba_char_args_set(btheme->tui.wcol_tooltip.text, 255, 255, 255, 255);
      }
    }
  }

  if (!USER_VERSION_ATLEAST(262, 4)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      if (btheme->tseq.movieclip[3] == 0) {
        rgba_char_args_set(btheme->tseq.movieclip, 32, 32, 143, 255);
      }
    }
  }

  if (!USER_VERSION_ATLEAST(263, 2)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      if (btheme->tclip.strip[0] == 0) {
        rgba_char_args_set(btheme->tclip.list, 0x66, 0x66, 0x66, 0xff);
        rgba_char_args_set(btheme->tclip.strip, 0x0c, 0x0a, 0x0a, 0x80);
        rgba_char_args_set(btheme->tclip.strip_select, 0xff, 0x8c, 0x00, 0xff);
      }
    }
  }

  if (!USER_VERSION_ATLEAST(263, 6)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next)
      rgba_char_args_set(btheme->tv3d.skin_root, 180, 77, 77, 255);
  }

  if (!USER_VERSION_ATLEAST(263, 7)) {
    bTheme *btheme;

    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      /* DopeSheet Summary */
      rgba_char_args_set(btheme->tact.anim_active, 204, 112, 26, 102);

      /* NLA Colors */
      rgba_char_args_set(
          btheme->tnla.anim_active, 204, 112, 26, 102); /* same as dopesheet above */
      rgba_char_args_set(btheme->tnla.anim_non_active, 153, 135, 97, 77);

      rgba_char_args_set(btheme->tnla.nla_tweaking, 77, 243, 26, 77);
      rgba_char_args_set(btheme->tnla.nla_tweakdupli, 217, 0, 0, 255);

      rgba_char_args_set(btheme->tnla.nla_transition, 28, 38, 48, 255);
      rgba_char_args_set(btheme->tnla.nla_transition_sel, 46, 117, 219, 255);
      rgba_char_args_set(btheme->tnla.nla_meta, 51, 38, 66, 255);
      rgba_char_args_set(btheme->tnla.nla_meta_sel, 105, 33, 150, 255);
      rgba_char_args_set(btheme->tnla.nla_sound, 43, 61, 61, 255);
      rgba_char_args_set(btheme->tnla.nla_sound_sel, 31, 122, 122, 255);
    }
  }

  if (!USER_VERSION_ATLEAST(263, 11)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      if (btheme->tseq.mask[3] == 0) {
        rgba_char_args_set(btheme->tseq.mask, 152, 78, 62, 255);
      }
    }
  }

  if (!USER_VERSION_ATLEAST(263, 15)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      rgba_char_args_set(btheme->tv3d.bone_pose_active, 140, 255, 255, 80);
    }
  }

  if (!USER_VERSION_ATLEAST(263, 16)) {
    bTheme *btheme;

    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      if (btheme->tact.anim_active[3] == 0)
        rgba_char_args_set(btheme->tact.anim_active, 204, 112, 26, 102);

      if (btheme->tnla.anim_active[3] == 0)
        rgba_char_args_set(btheme->tnla.anim_active, 204, 112, 26, 102);
    }
  }

  if (!USER_VERSION_ATLEAST(263, 22)) {
    bTheme *btheme;

    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      if (btheme->tipo.lastsel_point[3] == 0)
        rgba_char_args_set(btheme->tipo.lastsel_point, 0xff, 0xff, 0xff, 255);

      if (btheme->tv3d.skin_root[3] == 0)
        rgba_char_args_set(btheme->tv3d.skin_root, 180, 77, 77, 255);
    }
  }

  if (!USER_VERSION_ATLEAST(264, 9)) {
    bTheme *btheme;

    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      rgba_char_args_set(btheme->tui.xaxis, 220, 0, 0, 255);
      rgba_char_args_set(btheme->tui.yaxis, 0, 220, 0, 255);
      rgba_char_args_set(btheme->tui.zaxis, 0, 0, 220, 255);
    }
  }

  if (!USER_VERSION_ATLEAST(267, 0)) {
    /* Freestyle color settings */
    bTheme *btheme;

    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      /* check for alpha == 0 is safe, then color was never set */
      if (btheme->tv3d.freestyle_edge_mark[3] == 0) {
        rgba_char_args_set(btheme->tv3d.freestyle_edge_mark, 0x7f, 0xff, 0x7f, 255);
        rgba_char_args_set(btheme->tv3d.freestyle_face_mark, 0x7f, 0xff, 0x7f, 51);
      }

      if (btheme->tv3d.wire_edit[3] == 0) {
        rgba_char_args_set(btheme->tv3d.wire_edit, 0x0, 0x0, 0x0, 255);
      }
    }

    /* GL Texture Garbage Collection */
    if (userdef->textimeout == 0) {
      userdef->texcollectrate = 60;
      userdef->textimeout = 120;
    }
    if (userdef->memcachelimit <= 0) {
      userdef->memcachelimit = 32;
    }
    if (userdef->frameserverport == 0) {
      userdef->frameserverport = 8080;
    }
    if (userdef->dbl_click_time == 0) {
      userdef->dbl_click_time = 350;
    }
    if (userdef->v2d_min_gridsize == 0) {
      userdef->v2d_min_gridsize = 35;
    }
    if (userdef->dragthreshold == 0)
      userdef->dragthreshold = 5;
    if (userdef->widget_unit == 0)
      userdef->widget_unit = 20;
    if (userdef->header_size == 0)
      userdef->header_size = 26;
    if (userdef->anisotropic_filter <= 0)
      userdef->anisotropic_filter = 1;

    if (userdef->ndof_sensitivity == 0.0f) {
      userdef->ndof_sensitivity = 1.0f;
      userdef->ndof_flag = (NDOF_LOCK_HORIZON | NDOF_SHOULD_PAN | NDOF_SHOULD_ZOOM |
                            NDOF_SHOULD_ROTATE);
    }

    if (userdef->ndof_orbit_sensitivity == 0.0f) {
      userdef->ndof_orbit_sensitivity = userdef->ndof_sensitivity;

      if (!(userdef->flag & USER_TRACKBALL))
        userdef->ndof_flag |= NDOF_TURNTABLE;
    }
    if (userdef->tweak_threshold == 0)
      userdef->tweak_threshold = 10;
  }

  if (!USER_VERSION_ATLEAST(265, 1)) {
    bTheme *btheme;

    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      /* note: the toggle operator for transparent backdrops limits to these spacetypes */
      if (btheme->tnode.button[3] == 255) {
        btheme->tv3d.button[3] = 128;
        btheme->tnode.button[3] = 128;
        btheme->tima.button[3] = 128;
        btheme->tseq.button[3] = 128;
        btheme->tclip.button[3] = 128;
      }
    }
  }

  /* panel header/backdrop supported locally per editor now */
  if (!USER_VERSION_ATLEAST(265, 2)) {
    bTheme *btheme;

    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      ThemeSpace *ts;

      /* new color, panel backdrop. Not used anywhere yet, until you enable it */
      copy_v3_v3_char(btheme->tui.panel.back, btheme->tbuts.button);
      btheme->tui.panel.back[3] = 128;

      for (ts = UI_THEMESPACE_START(btheme); ts != UI_THEMESPACE_END(btheme); ts++) {
        ts->panelcolors = btheme->tui.panel;
      }
    }
  }

  /* NOTE!! from now on use userdef->versionfile and userdef->subversionfile */
#undef USER_VERSION_ATLEAST
#define USER_VERSION_ATLEAST(ver, subver) MAIN_VERSION_ATLEAST(userdef, ver, subver)

  if (!USER_VERSION_ATLEAST(266, 0)) {
    bTheme *btheme;

    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      /* rna definition limits fac to 0.01 */
      if (btheme->tui.menu_shadow_fac == 0.0f) {
        btheme->tui.menu_shadow_fac = 0.5f;
        btheme->tui.menu_shadow_width = 12;
      }
    }
  }

  if (!USER_VERSION_ATLEAST(265, 4)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      rgba_char_args_set(
          btheme->text.syntaxd, 50, 0, 140, 255); /* Decorator/Preprocessor Dir.  Blue-purple */
      rgba_char_args_set(btheme->text.syntaxr, 140, 60, 0, 255); /* Reserved  Orange */
      rgba_char_args_set(btheme->text.syntaxs, 76, 76, 76, 255); /* Gray (mix between fg/bg) */
    }
  }

  if (!USER_VERSION_ATLEAST(265, 6)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      copy_v4_v4_char(btheme->tv3d.gradients.high_gradient, btheme->tv3d.back);
    }
  }

  if (!USER_VERSION_ATLEAST(265, 9)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      rgba_char_args_test_set(btheme->tnode.syntaxs, 151, 116, 116, 255); /* matte nodes */
      rgba_char_args_test_set(btheme->tnode.syntaxd, 116, 151, 151, 255); /* distort nodes */
    }
  }

  if (!USER_VERSION_ATLEAST(265, 11)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      rgba_char_args_test_set(btheme->tconsole.console_select, 255, 255, 255, 48);
    }
  }

  if (!USER_VERSION_ATLEAST(266, 2)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      rgba_char_args_test_set(
          btheme->tnode.console_output, 223, 202, 53, 255); /* interface nodes */
    }
  }

  if (!USER_VERSION_ATLEAST(268, 3)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      rgba_char_args_test_set(btheme->tima.uv_others, 96, 96, 96, 255);
      rgba_char_args_test_set(btheme->tima.uv_shadow, 112, 112, 112, 255);
    }
  }

  if (!USER_VERSION_ATLEAST(269, 5)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      rgba_char_args_set(btheme->tima.wire_edit, 192, 192, 192, 255);
      rgba_char_args_set(btheme->tima.edge_select, 255, 133, 0, 255);
    }
  }

  if (!USER_VERSION_ATLEAST(269, 6)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      char r, g, b;
      r = btheme->tnode.syntaxn[0];
      g = btheme->tnode.syntaxn[1];
      b = btheme->tnode.syntaxn[2];
      rgba_char_args_test_set(btheme->tnode.nodeclass_output, r, g, b, 255);
      r = btheme->tnode.syntaxb[0];
      g = btheme->tnode.syntaxb[1];
      b = btheme->tnode.syntaxb[2];
      rgba_char_args_test_set(btheme->tnode.nodeclass_filter, r, g, b, 255);
      rgba_char_args_test_set(btheme->tnode.nodeclass_vector, r, g, b, 255);
      rgba_char_args_test_set(btheme->tnode.nodeclass_texture, r, g, b, 255);
      rgba_char_args_test_set(btheme->tnode.nodeclass_shader, r, g, b, 255);
      rgba_char_args_test_set(btheme->tnode.nodeclass_script, r, g, b, 255);
      rgba_char_args_test_set(btheme->tnode.nodeclass_pattern, r, g, b, 255);
      rgba_char_args_test_set(btheme->tnode.nodeclass_layout, r, g, b, 255);
    }
  }

  if (!USER_VERSION_ATLEAST(269, 8)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      rgba_char_args_test_set(btheme->tinfo.info_selected, 96, 128, 255, 255);
      rgba_char_args_test_set(btheme->tinfo.info_selected_text, 255, 255, 255, 255);
      rgba_char_args_test_set(btheme->tinfo.info_error, 220, 0, 0, 255);
      rgba_char_args_test_set(btheme->tinfo.info_error_text, 0, 0, 0, 255);
      rgba_char_args_test_set(btheme->tinfo.info_warning, 220, 128, 96, 255);
      rgba_char_args_test_set(btheme->tinfo.info_warning_text, 0, 0, 0, 255);
      rgba_char_args_test_set(btheme->tinfo.info_info, 0, 170, 0, 255);
      rgba_char_args_test_set(btheme->tinfo.info_info_text, 0, 0, 0, 255);
      rgba_char_args_test_set(btheme->tinfo.info_debug, 196, 196, 196, 255);
      rgba_char_args_test_set(btheme->tinfo.info_debug_text, 0, 0, 0, 255);
    }
  }

  if (!USER_VERSION_ATLEAST(269, 9)) {
    bTheme *btheme;

    userdef->tw_size = userdef->tw_size * 5.0f;

    /* Action Editor (and NLA Editor) - Keyframe Colors */
    /* Graph Editor - larger vertex size defaults */
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      /* Action Editor ................. */
      /* key types */
      rgba_char_args_set(btheme->tact.keytype_keyframe, 232, 232, 232, 255);
      rgba_char_args_set(btheme->tact.keytype_keyframe_select, 255, 190, 50, 255);
      rgba_char_args_set(btheme->tact.keytype_extreme, 232, 179, 204, 255);
      rgba_char_args_set(btheme->tact.keytype_extreme_select, 242, 128, 128, 255);
      rgba_char_args_set(btheme->tact.keytype_breakdown, 179, 219, 232, 255);
      rgba_char_args_set(btheme->tact.keytype_breakdown_select, 84, 191, 237, 255);
      rgba_char_args_set(btheme->tact.keytype_jitter, 148, 229, 117, 255);
      rgba_char_args_set(btheme->tact.keytype_jitter_select, 97, 192, 66, 255);

      /* key border */
      rgba_char_args_set(btheme->tact.keyborder, 0, 0, 0, 255);
      rgba_char_args_set(btheme->tact.keyborder_select, 0, 0, 0, 255);

      /* NLA ............................ */
      /* key border */
      rgba_char_args_set(btheme->tnla.keyborder, 0, 0, 0, 255);
      rgba_char_args_set(btheme->tnla.keyborder_select, 0, 0, 0, 255);

      /* Graph Editor ................... */
      btheme->tipo.vertex_size = 6;
      btheme->tipo.handle_vertex_size = 5;
    }

    /* grease pencil - new layer color */
    if (userdef->gpencil_new_layer_col[3] < 0.1f) {
      /* defaults to black, but must at least be visible! */
      userdef->gpencil_new_layer_col[3] = 0.9f;
    }
  }

  if (!USER_VERSION_ATLEAST(269, 10)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      ThemeSpace *ts;

      for (ts = UI_THEMESPACE_START(btheme); ts != UI_THEMESPACE_END(btheme); ts++) {
        rgba_char_args_set(ts->tab_active, 114, 114, 114, 255);
        rgba_char_args_set(ts->tab_inactive, 83, 83, 83, 255);
        rgba_char_args_set(ts->tab_back, 64, 64, 64, 255);
        rgba_char_args_set(ts->tab_outline, 60, 60, 60, 255);
      }
    }
  }

  if (!USER_VERSION_ATLEAST(271, 0)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      rgba_char_args_set(btheme->tui.wcol_tooltip.text, 255, 255, 255, 255);
    }
  }

  if (!USER_VERSION_ATLEAST(272, 2)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      rgba_char_args_set_fl(btheme->tv3d.paint_curve_handle, 0.5f, 1.0f, 0.5f, 0.5f);
      rgba_char_args_set_fl(btheme->tv3d.paint_curve_pivot, 1.0f, 0.5f, 0.5f, 0.5f);
      rgba_char_args_set_fl(btheme->tima.paint_curve_handle, 0.5f, 1.0f, 0.5f, 0.5f);
      rgba_char_args_set_fl(btheme->tima.paint_curve_pivot, 1.0f, 0.5f, 0.5f, 0.5f);
      rgba_char_args_set(btheme->tnode.syntaxr, 115, 115, 115, 255);
    }
  }

  if (!USER_VERSION_ATLEAST(271, 5)) {
    bTheme *btheme;

    struct uiWidgetColors wcol_pie_menu = {{10, 10, 10, 200},
                                           {25, 25, 25, 230},
                                           {140, 140, 140, 255},
                                           {45, 45, 45, 230},

                                           {160, 160, 160, 255},
                                           {255, 255, 255, 255},

                                           1,
                                           10,
                                           -10};

    userdef->pie_menu_radius = 100;
    userdef->pie_menu_threshold = 12;
    userdef->pie_animation_timeout = 6;

    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      btheme->tui.wcol_pie_menu = wcol_pie_menu;

      // ui_theme_space_init_handles_color(&btheme->tclip);
      // ui_theme_space_init_handles_color(&btheme->tima);
      btheme->tima.handle_vertex_size = 5;
      btheme->tclip.handle_vertex_size = 5;
    }
  }

  if (!USER_VERSION_ATLEAST(271, 6)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      /* check for (alpha == 0) is safe, then color was never set */
      if (btheme->tv3d.loop_normal[3] == 0) {
        rgba_char_args_set(btheme->tv3d.loop_normal, 0xDD, 0x23, 0xDD, 255);
      }
    }
  }

  if (!USER_VERSION_ATLEAST(272, 3)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      rgba_char_args_set_fl(btheme->tui.widget_emboss, 1.0f, 1.0f, 1.0f, 0.02f);
    }
  }

  if (!USER_VERSION_ATLEAST(273, 1)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      /* Grease Pencil vertex settings */
      rgba_char_args_set(btheme->tv3d.gp_vertex, 0, 0, 0, 255);
      rgba_char_args_set(btheme->tv3d.gp_vertex_select, 255, 133, 0, 255);
      btheme->tv3d.gp_vertex_size = 3;

      rgba_char_args_set(btheme->tseq.gp_vertex, 0, 0, 0, 255);
      rgba_char_args_set(btheme->tseq.gp_vertex_select, 255, 133, 0, 255);
      btheme->tseq.gp_vertex_size = 3;

      rgba_char_args_set(btheme->tima.gp_vertex, 0, 0, 0, 255);
      rgba_char_args_set(btheme->tima.gp_vertex_select, 255, 133, 0, 255);
      btheme->tima.gp_vertex_size = 3;

      rgba_char_args_set(btheme->tnode.gp_vertex, 0, 0, 0, 255);
      rgba_char_args_set(btheme->tnode.gp_vertex_select, 255, 133, 0, 255);
      btheme->tnode.gp_vertex_size = 3;

      /* Timeline Keyframe Indicators */
      rgba_char_args_set(btheme->ttime.time_keyframe, 0xDD, 0xD7, 0x00, 0xFF);
      rgba_char_args_set(btheme->ttime.time_gp_keyframe, 0xB5, 0xE6, 0x1D, 0xFF);
    }
  }

  if (!USER_VERSION_ATLEAST(273, 5)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      uchar *cp = (uchar *)btheme->tv3d.clipping_border_3d;
      int c;
      copy_v4_v4_char((char *)cp, btheme->tv3d.back);
      c = cp[0] - 8;
      CLAMP(c, 0, 255);
      cp[0] = c;
      c = cp[1] - 8;
      CLAMP(c, 0, 255);
      cp[1] = c;
      c = cp[2] - 8;
      CLAMP(c, 0, 255);
      cp[2] = c;
      cp[3] = 255;
    }
  }

  if (!USER_VERSION_ATLEAST(274, 5)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      copy_v4_v4_char(btheme->tima.metadatatext, btheme->tima.text_hi);
      copy_v4_v4_char(btheme->tseq.metadatatext, btheme->tseq.text_hi);
    }
  }

  if (!USER_VERSION_ATLEAST(275, 1)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      copy_v4_v4_char(btheme->tclip.metadatatext, btheme->tseq.text_hi);
    }
  }

  if (!USER_VERSION_ATLEAST(275, 2)) {
    userdef->ndof_deadzone = 0.1;
  }

  if (!USER_VERSION_ATLEAST(275, 4)) {
    userdef->node_margin = 80;
  }

  if (!USER_VERSION_ATLEAST(276, 1)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      rgba_char_args_set_fl(btheme->tima.preview_back, 0.0f, 0.0f, 0.0f, 0.3f);
    }
  }

  if (!USER_VERSION_ATLEAST(276, 2)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      rgba_char_args_set(btheme->tclip.gp_vertex, 0, 0, 0, 255);
      rgba_char_args_set(btheme->tclip.gp_vertex_select, 255, 133, 0, 255);
      btheme->tclip.gp_vertex_size = 3;
    }
  }

  if (!USER_VERSION_ATLEAST(276, 3)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      rgba_char_args_set(btheme->tseq.text_strip, 162, 151, 0, 255);
    }
  }

  if (!USER_VERSION_ATLEAST(276, 8)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      rgba_char_args_set(btheme->tui.wcol_progress.item, 128, 128, 128, 255);
    }
  }

  if (!USER_VERSION_ATLEAST(276, 10)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      /* 3dView Keyframe Indicators */
      rgba_char_args_set(btheme->tv3d.time_keyframe, 0xDD, 0xD7, 0x00, 0xFF);
      rgba_char_args_set(btheme->tv3d.time_gp_keyframe, 0xB5, 0xE6, 0x1D, 0xFF);
    }
  }

  if (!USER_VERSION_ATLEAST(277, 0)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      if (memcmp(btheme->tui.wcol_list_item.item,
                 btheme->tui.wcol_list_item.text_sel,
                 sizeof(char) * 3) == 0)
      {
        copy_v4_v4_char(btheme->tui.wcol_list_item.item, btheme->tui.wcol_text.item);
        copy_v4_v4_char(btheme->tui.wcol_list_item.text_sel, btheme->tui.wcol_text.text_sel);
      }
    }
  }

  if (!USER_VERSION_ATLEAST(277, 2)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      if (btheme->tact.keyframe_scale_fac < 0.1f)
        btheme->tact.keyframe_scale_fac = 1.0f;
    }
  }

  if (!USER_VERSION_ATLEAST(278, 2)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      rgba_char_args_set(btheme->tv3d.vertex_bevel, 0, 165, 255, 255);
      rgba_char_args_set(btheme->tv3d.edge_bevel, 0, 165, 255, 255);
    }
  }

  if (!USER_VERSION_ATLEAST(278, 3)) {
    for (bTheme *btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      /* Keyframe Indicators (were using wrong alpha) */
      btheme->tv3d.time_keyframe[3] = btheme->tv3d.time_gp_keyframe[3] = 255;
      btheme->ttime.time_keyframe[3] = btheme->ttime.time_gp_keyframe[3] = 255;
    }
  }

  if (!USER_VERSION_ATLEAST(278, 6)) {
    /* Clear preference flags for re-use. */
    userdef->flag &= ~(USER_FLAG_DEPRECATED_1 | USER_FLAG_DEPRECATED_2 | USER_FLAG_DEPRECATED_3 |
                       USER_FLAG_DEPRECATED_6 | USER_FLAG_DEPRECATED_7 | USER_FLAG_DEPRECATED_9 |
                       USER_DEVELOPER_UI);
    userdef->uiflag &= ~(USER_UIFLAG_DEPRECATED_7);
    userdef->transopts &= ~(USER_TR_DEPRECATED_2 | USER_TR_DEPRECATED_3 | USER_TR_DEPRECATED_4 |
                            USER_TR_DEPRECATED_6 | USER_TR_DEPRECATED_7);
    userdef->gameflags &= ~(USER_GL_RENDER_DEPRECATED_0 | USER_GL_RENDER_DEPRECATED_1 |
                            USER_GL_RENDER_DEPRECATED_3 | USER_GL_RENDER_DEPRECATED_4);

    userdef->uiflag |= USER_LOCK_CURSOR_ADJUST;
  }

  /**
   * Include next version bump.
   */
  {
    /* (keep this block even if it becomes empty). */
  }

  if (userdef->pixelsize == 0.0f)
    userdef->pixelsize = 1.0f;

  if (userdef->image_draw_method == 0)
    userdef->image_draw_method = IMAGE_DRAW_METHOD_2DTEXTURE;

/* Range Engine UserDer Versioning */
/* NOTE!! from now on use userdef->versionrangefile and userdef->subversionrangefile and
 * userdef->minsubversionrangefile */
#undef USER_VERSION_ATLEAST
#define USER_VERSION_ATLEAST(ver, subver, minsubver) \
  MAIN_VERSION_RANGE_ATLEAST(userdef, ver, subver, minsubver)

  if (!USER_VERSION_ATLEAST(1, 4, 2)) {
    bTheme *btheme;
    for (btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      copy_v4_v4_char(btheme->tbuts.navigation_bar, btheme->tbuts.header);
    }
  }

  if (!USER_VERSION_ATLEAST(1, 4, 3)) {
    /* interface_widgets.c */
    struct uiWidgetColors wcol_tab = {
        {255, 255, 255, 255},
        {83, 83, 83, 255},
        {114, 114, 114, 255},
        {90, 90, 90, 255},

        {0, 0, 0, 255},
        {0, 0, 0, 255},

        0,
        0,
        0,
        0,
        0.5f,
    };

    for (bTheme *btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      btheme->tui.wcol_tab = wcol_tab;

      rgba_char_args_set_fl(btheme->tui.wcol_state.inner_overridden, 0.0f, 0.7f, 0.0f, 1.0f);
      rgba_char_args_set_fl(btheme->tui.wcol_state.inner_overridden_sel, 0.0f, 0.7f, 0.0f, 1.0f);
      rgba_char_args_set_fl(btheme->tui.wcol_state.inner_changed, 0.0f, 0.7f, 0.0f, 1.0f);
      rgba_char_args_set_fl(btheme->tui.wcol_state.inner_changed_sel, 0.0f, 0.7f, 0.0f, 1.0f);

      rgba_char_args_set_fl(btheme->tuserpref.button_text, 0.0f, 1.0f, 0.0f, 1.0f);
      rgba_char_args_set_fl(btheme->tuserpref.navigation_bar, 0.15f, 0.15f, 0.15f, 1.0f);

      btheme->tui.wcol_regular.roundness = 0.25f;
      btheme->tui.wcol_tool.roundness = 0.2f;
      btheme->tui.wcol_text.roundness = 0.2f;
      btheme->tui.wcol_radio.roundness = 0.2f;
      btheme->tui.wcol_option.roundness = 0.2f;
      btheme->tui.wcol_toggle.roundness = 0.25f;
      btheme->tui.wcol_num.roundness = 0.2f;
      btheme->tui.wcol_numslider.roundness = 0.2f;
      btheme->tui.wcol_tab.roundness = 0.25f;
      btheme->tui.wcol_menu.roundness = 0.2f;
      btheme->tui.wcol_pulldown.roundness = 0.2f;
      btheme->tui.wcol_menu_back.roundness = 0.25f;
      btheme->tui.wcol_menu_item.roundness = 0.25f;
      btheme->tui.wcol_tooltip.roundness = 0.25f;
      btheme->tui.wcol_box.roundness = 0.2f;
      btheme->tui.wcol_scroll.roundness = 0.5f;
      btheme->tui.wcol_progress.roundness = 0.25f;
      btheme->tui.wcol_list_item.roundness = 0.2f;
      btheme->tui.wcol_pie_menu.roundness = 0.5f;
    }

    // Enable RanGE 1.4 Addons
    BKE_addon_ensure(&userdef->addons, "Range_Object_Pencil");
  }

  if (!USER_VERSION_ATLEAST(1, 5, 101)) {
    for (bTheme *btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      // Properties Icons Color, expected userdef_default_theme.c soon
#if 0
      copy_v4_v4_char(btheme->tui.icon_collection, U_theme_default.tui.icon_collection);
      copy_v4_v4_char(btheme->tui.icon_object, U_theme_default.tui.icon_object);
      copy_v4_v4_char(btheme->tui.icon_object_data, U_theme_default.tui.icon_object_data);
      copy_v4_v4_char(btheme->tui.icon_modifier, U_theme_default.tui.icon_modifier);
      copy_v4_v4_char(btheme->tui.icon_shading, U_theme_default.tui.icon_shading);
#else
      rgba_char_args_set_fl(btheme->tui.icon_scene, 0.95f, 0.95f, 0.95f, 1.0f);
      rgba_char_args_set_fl(btheme->tui.icon_collection, 0.95f, 0.95f, 0.95f, 1.0f);
      rgba_char_args_set_fl(btheme->tui.icon_object, 1.0f, 0.6f, 0.31f, 1.0f);
      rgba_char_args_set_fl(btheme->tui.icon_object_data, 0.0f, 0.87f, 0.62f, 1.0f);
      rgba_char_args_set_fl(btheme->tui.icon_modifier, 0.44f, 0.69f, 1.0f, 1.0f);
      rgba_char_args_set_fl(btheme->tui.icon_shading, 1.0f, 0.32f, 0.33f, 1.0f);
#endif
    }
  }

  if (!USER_VERSION_ATLEAST(1, 5, 102)) {
    for (bTheme *btheme = userdef->themes.first; btheme; btheme = btheme->next) {
      /* Initialize the shared theme from the existing 3D View colors. */
      btheme->tglobal = btheme->tv3d;
      btheme->tglobal_ui = btheme->tui;
      btheme->global_theme_spaces = 0;
    }
  }

  // we default to the first audio device
  userdef->audiodevice = 0;

  /* funny name, but it is GE stuff, moves userdef stuff to engine */
  // XXX	space_set_commmandline_options();
  /* this timer uses U */
  // XXX	reset_autosave();

#undef USER_VERSION_ATLEAST
}
