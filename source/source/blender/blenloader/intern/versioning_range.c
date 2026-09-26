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
 * Contributor(s): Blender Foundation
 *
 * ***** END GPL LICENSE BLOCK *****
 *
 */

/** \file blender/blenloader/intern/versioning_range.c
 *  \ingroup blenloader
 */

#include "BLI_compiler_attrs.h"
#include "BLI_listbase.h"
#include "BLI_utildefines.h"
#include "BLI_math.h"

#include <stdio.h>
#include <string.h>

/* allow readfile to use deprecated functionality */
#define DNA_DEPRECATED_ALLOW

#include "DNA_camera_types.h"
#include "DNA_genfile.h"
#include "DNA_material_types.h"
#include "DNA_mesh_types.h"
#include "DNA_object_force_types.h"
#include "DNA_object_types.h"
#include "DNA_property_types.h"
#include "DNA_python_component_types.h"
#include "DNA_screen_types.h"
#include "DNA_sdna_types.h"
#include "DNA_sensor_types.h"
#include "DNA_space_types.h"
#include "DNA_view3d_types.h"
#include "DNA_world_types.h"

#include "BLI_string.h"
#include "BLI_string_utils.h"

#include "BKE_main.h"
#include "BKE_node.h"
#include "BKE_property.h"
#include "BKE_screen.h"
#include "BKE_scene.h"

#include "BLI_math_base.h"

#include "BLO_readfile.h"

#include "wm_event_types.h"

#include "readfile.h"

#include "MEM_guardedalloc.h"

static ARegion *do_versions_find_region_or_null(ListBase *regionbase, int regiontype)
{
  LISTBASE_FOREACH (ARegion *, region, regionbase) {
    if (region->regiontype == regiontype) {
      return region;
    }
  }
  return NULL;
}

void blo_do_versions_range(FileData *fd, Library *lib, Main *main)
{
  // printf("Range: open file from version : %i, subversion : %i\n", main->rangeversionfile,
  // main->rangesubversionfile);
  if (!MAIN_VERSION_RANGE_ATLEAST(main, 1, 0, 0)) {
    printf("Upbge/bge file is now updated for Range Game Engine.\n");

    if (main->upbgeversionfile != 0) {
      /* UPBGE 0.2.5b stored the wheel and movement mouse events as 5, 6 and 8.
       * Range added the thumb and extra buttons in those positions, so migrate the
       * old values before the file is shown or converted to game sensors. */
      LISTBASE_FOREACH (Object *, object, &main->object) {
        LISTBASE_FOREACH (bSensor *, sensor, &object->sensors) {
          if (sensor->type == SENS_MOUSE) {
            bMouseSensor *mouse_sensor = (bMouseSensor *)sensor->data;

            switch (mouse_sensor->type) {
              case 5:
                mouse_sensor->type = BL_SENS_MOUSE_WHEEL_UP;
                break;
              case 6:
                mouse_sensor->type = BL_SENS_MOUSE_WHEEL_DOWN;
                break;
              case 8:
                mouse_sensor->type = BL_SENS_MOUSE_MOVEMENT;
                break;
            }
          }
        }
      }

      /* The Range atmospheric sky modes took bits 3 and 4. Preserve the two
       * UPBGE sky flags that occupied those bits. */
      LISTBASE_FOREACH (World *, world, &main->world) {
        if (world->skytype & (1 << 3)) {
          world->skytype &= ~(1 << 3);
          world->skytype |= WO_SKYTEX;
        }
        if (world->skytype & (1 << 4)) {
          world->skytype &= ~(1 << 4);
          world->skytype |= WO_ZENUP;
        }
      }

      /* Range inserted Clipping and Dithering ahead of the UPBGE shadow
       * filters. Keep the filter selected by old lamp datablocks. */
      LISTBASE_FOREACH (Lamp *, lamp, &main->lamp) {
        switch (lamp->shadow_filter) {
          case 1:
            lamp->shadow_filter = LA_SHADOW_FILTER_PCF;
            break;
          case 2:
            lamp->shadow_filter = LA_SHADOW_FILTER_PCF_BAIL;
            break;
          case 3:
            lamp->shadow_filter = LA_SHADOW_FILTER_PCF_JITTER;
            break;
        }
      }

    }
  }

  if (!MAIN_VERSION_RANGE_ATLEAST(main, 1, 2, 0)) {
    if (!DNA_struct_elem_find(fd->filesdna, "PythonComponent", "int", "flag_toggle_exec")) {

      for (Object *ob = main->object.first; ob; ob = ob->id.next) {
        for (PythonComponent *pc = ob->components.first; pc != NULL; pc = (PythonComponent *)pc->next) {
          pc->flag_toggle_exec = true;
        }
      }
    }
  }

  if (!MAIN_VERSION_RANGE_ATLEAST(main, 1, 4, 2)) {
    LISTBASE_FOREACH (bScreen *, screen, &main->screen) {
      LISTBASE_FOREACH (ScrArea *, sa, &screen->areabase) {
        LISTBASE_FOREACH (SpaceLink *, sl, &sa->spacedata) {
          ListBase *regionbase = (sl == sa->spacedata.first) ? &sa->regionbase : &sl->regionbase;
          ARegion *region_header = do_versions_find_region_or_null(regionbase, RGN_TYPE_HEADER);

          // Leave the header at the top.
          if (region_header) {
            region_header->alignment = RGN_ALIGN_TOP;
          }

          // If it is Space_Buts, we add the vertical bar.
          if (sl->spacetype == SPACE_BUTS) {
            /* we need to check if the navBar region was previously added by previews without
             * minsubversion */
            ARegion *region_navbar = do_versions_find_region_or_null(regionbase, RGN_TYPE_NAV_BAR);
            if (region_navbar) {
              continue;
            }

            /* if you got here, add */
            ARegion *ar = MEM_callocN(sizeof(ARegion), "navigation bar for properties");
            ARegion *ar_header = NULL;

            for (ar_header = regionbase->first; ar_header; ar_header = ar_header->next) {
              if (ar_header->regiontype == RGN_TYPE_HEADER) {
                break;
              }
            }
            BLI_assert(ar_header);

            BLI_insertlinkafter(regionbase, ar_header, ar);

            ar->regiontype = RGN_TYPE_NAV_BAR;
            ar->alignment = RGN_ALIGN_LEFT;
          }
        }
      }
    }
  }

  if (!MAIN_VERSION_RANGE_ATLEAST(main, 1, 4, 3)) {

    LISTBASE_FOREACH (bScreen *, screen, &main->screen) {
      LISTBASE_FOREACH (ScrArea *, area, &screen->areabase) {
        LISTBASE_FOREACH (SpaceLink *, slink, &area->spacedata) {
          if (slink->spacetype == SPACE_USERPREF) {
            ARegion *navigation_region = BKE_spacedata_find_region_type(
                slink, area, RGN_TYPE_NAV_BAR);

            if (!navigation_region) {
              ListBase *regionbase = (slink == area->spacedata.first) ? &area->regionbase :
                                                                        &slink->regionbase;

              navigation_region = MEM_callocN(sizeof(ARegion),
                                              "userpref navigation-region do_versions");

              BLI_addhead(regionbase, navigation_region); /* order matters, addhead not addtail! */
              navigation_region->regiontype = RGN_TYPE_NAV_BAR;
              navigation_region->alignment = RGN_ALIGN_LEFT;
            }
          }
        }
      }
    }
  }
  if (!MAIN_VERSION_RANGE_ATLEAST(main, 1, 5, 1)) {
    LISTBASE_FOREACH (Scene *, scene, &main->scene) {
      scene->gm.cursor_size = 20;
      scene->orientation_index_custom = -1;
    }
    LISTBASE_FOREACH (bScreen *, sc, &main->screen) {
      LISTBASE_FOREACH (ScrArea *, sa, &sc->areabase) {
        LISTBASE_FOREACH (SpaceLink *, sl, &sa->spacedata) {
          if (sl->spacetype == SPACE_VIEW3D) {
            View3D *v3d = (View3D *)sl;
            v3d->flag2 |= V3D_RENDER_SHOW_COMPONENTS;
          }
        }
      }
    }

    LISTBASE_FOREACH (Object *, ob, &main->object) {
      ob->gameflag |= OB_TASK_CONVERT;
    }

    LISTBASE_FOREACH (World *, wo, &main->world) {
      wo->sun_size = 0.2f;
      wo->turbidity = 0.2f;
      wo->ground = 1.0f;
    }
  }

  if (!MAIN_VERSION_RANGE_ATLEAST(main, 1, 5, 100)) {
    LISTBASE_FOREACH (Material *, ma, &main->mat) {
      if (ma->ref == 0.8f) {
        ma->ref = 1.0;
      }
    }
    LISTBASE_FOREACH (World *, wo, &main->world) {
      if (wo->range == 0.8f) {
        wo->range = 1.0;
      }
    }
  }

  /* 1.5a */
  if (!MAIN_VERSION_RANGE_ATLEAST(main, 1, 5, 101)) {
    LISTBASE_FOREACH (World *, wo, &main->world) {
      if (wo->turbidity == 1.0f) {
        wo->sun_size = 0.1f;
        wo->turbidity = 0.5f;
        wo->ground = 0.85f;
      }
    }
  }

  /* 1.6 */
  if (!MAIN_VERSION_RANGE_ATLEAST(main, 1, 6, 100)) {
    LISTBASE_FOREACH (Lamp *, light, &main->lamp) {
      if (light->type == LA_SUN) {
        light->spotblend = 0.05f;
      }
    }

    // Change default IOR value
    LISTBASE_FOREACH (Material *, ma, &main->mat) {
      if (ma->refrac == 4.0f) {
        ma->refrac = 1.5f;
      }
    }

	// Change Font Name
    LISTBASE_FOREACH (VFont *, vf, &main->vfont) {
      if (strcmp(vf->id.name, "VFBfont") == 0) {
        strcpy(vf->id.name, "VFRoboto-Medium");
      }
    }

    LISTBASE_FOREACH (Object *, ob, &main->object) {
      LISTBASE_FOREACH (bSensor *, sens, &ob->sensors) {
        // Set default sensor color.
        if (U.themes.first) {
          bTheme *btheme = U.themes.first;
          /* bSensor.color has 3 bytes and ends the struct, copying 4 overflows it. */
          copy_v3_v3_char(sens->color, (const char *)btheme->tui.wcol_box.inner);
        }
      }
    }

    LISTBASE_FOREACH (World *, wo, &main->world) {
      wo->mistheight = 5.0f;
      wo->mistdensity = 1.0f;
    }

    LISTBASE_FOREACH (Scene *, scene, &main->scene) {
      // Old FXAA location
      if (scene->gm.aasamples == 1) {
        scene->gm.aasamples = 0;
        scene->scenefx_settings.scenefx_flag |= SCENE_FX_FLAG_FXAA;
        /* The camera button independently controls viewport rendering.  The
         * legacy AA option had no separate viewport toggle, so preserve its
         * visible behavior when migrating an old Range file. */
        scene->scenefx_settings.editor_render_flag |= SCENE_FX_FLAG_FXAA;
      }

      /* Files from this era can carry stray bits in scenefx_flag/
       * editor_render_flag outside the currently defined eSCENEFXFlags range
       * (leftover from a removed/repurposed effect slot). Such a bit is
       * never cleared by turning filters off in the UI, which keeps the
       * compositor permanently "on" with zero real passes and hangs the GL
       * driver. Scrub to the known bits on load. */
      scene->scenefx_settings.scenefx_flag &=
          (SCENE_FX_FLAG_BLOOM | SCENE_FX_FLAG_TONEMAP | SCENE_FX_FLAG_LIGHTSCATTER |
           SCENE_FX_FLAG_SSR | SCENE_FX_FLAG_SSAO | SCENE_FX_FLAG_FXAA);
      scene->scenefx_settings.editor_render_flag &=
          (SCENE_FX_FLAG_BLOOM | SCENE_FX_FLAG_TONEMAP | SCENE_FX_FLAG_LIGHTSCATTER |
           SCENE_FX_FLAG_SSR | SCENE_FX_FLAG_SSAO | SCENE_FX_FLAG_FXAA);
    }

    LISTBASE_FOREACH (bScreen *, sc, &main->screen) {
      LISTBASE_FOREACH (ScrArea *, sa, &sc->areabase) {
        LISTBASE_FOREACH (SpaceLink *, sl, &sa->spacedata) {
          if (sl->spacetype == SPACE_VIEW3D) {
            View3D *v3d = (View3D *)sl;

            // SSAO has moved to scenefx
            if (v3d->fx_settings.fx_flag & (1 << 1))
              v3d->fx_settings.fx_flag = 0;
          }
        }
      }
    }
  }

  if (!MAIN_VERSION_RANGE_ATLEAST(main, 1, 6, 102)) {
    /* Fase I moved the GPU particle emitter settings from Scene.gpu_particles (Fase H) to
     * Object.gpu_particles (per-object emitters, opt-in via gameflag2 & OB_GPU_PARTICLES).
     * Scene.gpu_particles no longer exists, so there is nothing to migrate from it - just
     * seed every object with the same defaults Fase H used, so turning use_gpu_particles on
     * later starts from a sane configuration instead of all-zero DNA. */
    LISTBASE_FOREACH (Object *, ob, &main->object) {
      ob->gpu_particles.gravity[0] = 0.0f;
      ob->gpu_particles.gravity[1] = 0.0f;
      ob->gpu_particles.gravity[2] = -9.8f;
      ob->gpu_particles.lifetime = 3.0f;
      ob->gpu_particles.emitter_position[0] = 0.0f;
      ob->gpu_particles.emitter_position[1] = 0.0f;
      ob->gpu_particles.emitter_position[2] = 0.0f;
      ob->gpu_particles.emitter_radius = 1.0f;
      ob->gpu_particles.velocity[0] = 0.0f;
      ob->gpu_particles.velocity[1] = 0.0f;
      ob->gpu_particles.velocity[2] = 4.0f;
      ob->gpu_particles.velocity_randomness = 2.0f;
      ob->gpu_particles.size = 0.35f;
      ob->gpu_particles.color[0] = 1.0f;
      ob->gpu_particles.color[1] = 0.2f;
      ob->gpu_particles.color[2] = 0.8f;
      ob->gpu_particles.color[3] = 1.0f;
      copy_v4_v4(ob->gpu_particles.end_color, ob->gpu_particles.color);
      ob->gpu_particles.end_size = ob->gpu_particles.size;
      ob->gpu_particles.particle_count = 200;
      ob->gpu_particles.texture_path[0] = '\0';
      ob->gpu_particles.emission_direction[0] = 0.0f;
      ob->gpu_particles.emission_direction[1] = 0.0f;
      ob->gpu_particles.emission_direction[2] = 1.0f;
      ob->gpu_particles.emission_angle = 180.0f;
    }
  }

  if (!MAIN_VERSION_RANGE_ATLEAST(main, 1, 6, 103)) {
    /* GPU Particles Actuator was replaced by a real Object Game Property
     * ("GPU_Particles_Enabled") toggled via the standard Property actuator, so objects
     * saved with use_gpu_particles already on need the property backfilled - otherwise
     * the checkbox's update callback (which creates it) never runs again on load. */
    LISTBASE_FOREACH (Object *, ob, &main->object) {
      if (ob->gameflag2 & OB_GPU_PARTICLES) {
        if (!BKE_bproperty_object_get(ob, "GPU_Particles_Enabled")) {
          bProperty *prop = BKE_bproperty_new(GPROP_BOOL);
          BLI_strncpy(prop->name, "GPU_Particles_Enabled", sizeof(prop->name));
          prop->data = 1;
          BLI_addtail(&ob->prop, prop);
          BLI_uniquename(&ob->prop, prop, "GPU_Particles_Enabled", '.', offsetof(bProperty, name), sizeof(prop->name));
        }
      }
    }
  }

  if (!MAIN_VERSION_RANGE_ATLEAST(main, 1, 6, 104)) {
    /* Fase 5 wired World.weather_flag (rain/clouds/lens flare) to the runtime 2D
     * filter chain, but the DNA fields it reads were previously always zero
     * (never exposed in the UI before now), so existing Worlds would enable a
     * filter with every parameter at 0 - fully invisible. Seed sane defaults. */
    LISTBASE_FOREACH (World *, wo, &main->world) {
      wo->rain_intensity = 0.5f;
      wo->rain_speed = 1.0f;
      wo->rain_wind = 0.1f;
      wo->rain_darken = 0.3f;
      wo->rain_ripple = 0.15f;
      wo->rain_color[0] = 0.8f;
      wo->rain_color[1] = 0.8f;
      wo->rain_color[2] = 0.8f;

      wo->cloud_coverage = 0.5f;
      wo->cloud_scale = 1.0f;
      wo->cloud_speed = 0.3f;
      wo->cloud_color[0] = 1.0f;
      wo->cloud_color[1] = 1.0f;
      wo->cloud_color[2] = 1.0f;

      wo->flare_scale = 1.0f;
      wo->flare_intensity = 1.0f;
    }
  }

  if (!MAIN_VERSION_RANGE_ATLEAST(main, 1, 6, 105)) {
    /* Split the Rain effect into independently toggleable droplets/streaks and puddle
     * ripples (previously a single "Use Rain" switch drove both). Existing files had
     * both baked into that one switch, so keep both sub-effects on to match prior
     * behavior instead of silently losing the ripples half. */
    LISTBASE_FOREACH (World *, wo, &main->world) {
      wo->weather_flag |= (WO_WEATHER_RAIN_DROPLETS | WO_WEATHER_RAIN_RIPPLE);
    }
  }

  if (!MAIN_VERSION_RANGE_ATLEAST(main, 1, 6, 106)) {
    /* GPU particle collision (Ground Plane / Screen-Space). collision_mode defaults to
     * None so existing emitters are unaffected, but bounce/friction need sane non-zero
     * defaults so switching the mode on later doesn't start from "particle sticks dead". */
    LISTBASE_FOREACH (Object *, ob, &main->object) {
      ob->gpu_particles.collision_mode = GPU_PARTICLE_COLLISION_NONE;
      ob->gpu_particles.collision_height = 0.0f;
      ob->gpu_particles.collision_bounce = 0.4f;
      ob->gpu_particles.collision_friction = 0.9f;
    }
  }

  if (!MAIN_VERSION_RANGE_ATLEAST(main, 1, 6, 107)) {
    /* GameData.shadowCulling replaces the repurposed pad5 slot and takes over the
     * "Shadow Culling" RNA property, which used to alias GameData.maxphystep even
     * though that field's name and Python API (get/setMaxPhysicsFrame) promise a
     * physics catch-up limit unrelated to shadows. shadowCulling is new to this
     * version and always reads 0 from an old file, so seed it from the old
     * maxphystep value it used to share to keep existing files' shadow culling
     * behavior unchanged. maxphystep itself is untouched and keeps driving the
     * deprecated Python API. */
    LISTBASE_FOREACH (Scene *, scene, &main->scene) {
      scene->gm.shadowCulling = (scene->gm.maxphystep != 0) ? 1 : 0;
    }
  }

  if (!MAIN_VERSION_RANGE_ATLEAST(main, 1, 6, 108)) {
    /* Camera.csmCacheMaxStaleFrames replaces a repurposed pad2 slot and drives the CSM
     * cascade-matrix cache in KX_ShadowRenderer (0 disables it, 1 is the exact-match behavior,
     * 2 tolerates one frame of small movement). It always reads 0 from an old file, which would
     * silently disable the cache instead of keeping the previous exact-match behavior, so seed
     * it to 1 here. */
    LISTBASE_FOREACH (Camera *, camera, &main->camera) {
      camera->csmCacheMaxStaleFrames = 1;
    }
  }

  if (!MAIN_VERSION_RANGE_ATLEAST(main, 1, 6, 109)) {
    /* Cutscene settings are new scene-owned data. Older files have no settings block,
     * so create an empty one instead of leaving later RNA/UI access to handle a NULL
     * pointer. The empty list deliberately preserves their prior behavior. */
    LISTBASE_FOREACH (Scene *, scene, &main->scene) {
      scene->cutscene_settings = BKE_cutscene_settings_new();
    }
  }

  if (!MAIN_VERSION_RANGE_ATLEAST(main, 1, 6, 110)) {
    /* Dynamic resolution is opt-in. Seed its controls for old files so enabling it later
     * gives the same predictable defaults as a newly created scene. */
    LISTBASE_FOREACH (Scene *, scene, &main->scene) {
      scene->gm.useDynamicResolution = 0;
      scene->gm.dynamicResolutionTargetFPS = 60;
      scene->gm.dynamicResolutionMinScale = 50;
      scene->gm.dynamicResolutionMaxScale = 100;
      scene->gm.dynamicResolutionStep = 5;
    }
  }

  if (!MAIN_VERSION_RANGE_ATLEAST(main, 1, 6, 111)) {
    /* Preserve the original weather appearance in old files while constraining
     * ripples to nearby upward-facing surfaces. */
    LISTBASE_FOREACH (World *, wo, &main->world) {
      wo->rain_density = 1.0f;
      wo->rain_ripple = 0.4f;
      wo->rain_ripple_distance = 20.0f;
      wo->rain_ripple_min_up = 0.5f;
    }
  }

  if (!MAIN_VERSION_RANGE_ATLEAST(main, 1, 6, 112)) {
    LISTBASE_FOREACH (World *, wo, &main->world) {
      wo->rain_ripple = 0.4f;
    }
  }

  if (!MAIN_VERSION_RANGE_ATLEAST(main, 1, 6, 113)) {
    /* The moon is opt-in so existing skies retain their exact appearance. */
    LISTBASE_FOREACH (World *, wo, &main->world) {
      wo->moon_enabled = 0.0f;
      wo->moon_size = 0.01f;
      wo->moon_brightness = 0.25f;
    }
  }

  if (!DNA_struct_elem_find(fd->filesdna, "Material", "float", "foliage_distance")) {
    /* Files from before Foliage Optimization get the same wind distance as new materials. */
    LISTBASE_FOREACH (Material *, ma, &main->mat) {
      ma->foliage_distance = 50.0f;
    }
  }

  if (!DNA_struct_elem_find(fd->filesdna, "SCENEFXSettings", "float", "fxaa_edge_threshold")) {
    /* FXAA values became settings; keep the look the shaders had before. */
    LISTBASE_FOREACH (Scene *, scene, &main->scene) {
      scene->scenefx_settings.fxaa_edge_threshold = SCENE_FX_FXAA_EDGE_THRESHOLD;
      scene->scenefx_settings.fxaa_edge_threshold_min = SCENE_FX_FXAA_EDGE_THRESHOLD_MIN;
      scene->scenefx_settings.fxaa_subpix = SCENE_FX_FXAA_SUBPIX;
      scene->scenefx_settings.fxaa_search_steps = SCENE_FX_FXAA_SEARCH_STEPS;
    }
  }
}
