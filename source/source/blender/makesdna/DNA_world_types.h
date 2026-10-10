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
 *
 * The Original Code is Copyright (C) 2001-2002 by NaN Holding BV.
 * All rights reserved.
 */

/** \file DNA_world_types.h
 *  \ingroup DNA
 */

#ifndef __DNA_WORLD_TYPES_H__
#define __DNA_WORLD_TYPES_H__

#include "DNA_defs.h"
#include "DNA_ID.h"

struct AnimData;
struct Ipo;
struct MTex;
struct bNodeTree;

#ifndef MAX_MTEX
#define MAX_MTEX	18
#endif


/**
 * World defines general modeling data such as a background fill,
 * gravity, color model etc. It mixes game-data, rendering
 * data and modeling data. */
typedef struct World {
	ID id;
	struct AnimData *adt;	/* animation data (must be immediately after id for utilities to use it) */

	short colormodel, totex;
	short texact, mistype;

	float horr, horg, horb;
	float zenr, zeng, zenb;
	float nadr, nadg, nadb;
	float ambr, ambg, ambb;
	float pad1;

	/**
	 * Exposure= mult factor. unused now, but maybe back later. Kept in to be upward compat.
	 * New is exp/range control. linfac & logfac are constants... don't belong in
	 * file, but allocating 8 bytes for temp mem isn't useful either.
	 */
	float exposure, exp, range;
	float linfac, logfac;

	float sun_size, turbidity, ground;
	/* Visual moon only: it mirrors the World Sun and never creates a Lamp. */
	float moon_enabled, moon_size, moon_brightness;
	short star_style; /* WO_STARS_SIMPLE/REALISTIC/CONSTELLATIONS (era pad2[0]; arquivos antigos = 0 = simples) */
	short aurora_flag;   /* WO_AURORA_ENABLE (era pad2[0]; 0 = desligada) */
	short aurora_colors; /* WO_AURORA_GREEN/CLASSIC/RAINBOW */
	short pad2[1];

	/**
	 * Gravitation constant for the game world
	 */
	float gravity; // XXX moved to scene->gamedata in 2.5

	/**
	 * Radius of the activity bubble, in Manhattan length. Objects
	 * outside the box are activity-culled. */
	float activityBoxRadius; // XXX moved to scene->gamedata in 2.5

	short skytype;
	/**
	 * Some world modes
	 * bit 0: Do mist
	 * bit 1: Do stars
	 * bit 2: (reserved) depth of field
	 * bit 3: (gameengine): Activity culling is enabled.
	 * bit 4: ambient occlusion
	 * bit 5: (gameengine) : enable Bullet DBVT tree for view frustum culling
	 */
	short mode;												// partially moved to scene->gamedata in 2.5
	short occlusionRes;		/* resolution of occlusion Z buffer in pixel */	// XXX moved to scene->gamedata in 2.5
	short physicsEngine;	/* here it's aligned */					// XXX moved to scene->gamedata in 2.5
	short ticrate, maxlogicstep, physubstep, maxphystep;	// XXX moved to scene->gamedata in 2.5

	float misi, miststa, mistdist, misthi;
	float mistheight, mistdensity; // height fog exp parameters

	float starr  DNA_DEPRECATED, starg  DNA_DEPRECATED, starb  DNA_DEPRECATED, stark  DNA_DEPRECATED; /* Deprecated */
	float starsize DNA_DEPRECATED, starmindist DNA_DEPRECATED;
	float stardist DNA_DEPRECATED, starcolnoise DNA_DEPRECATED;

	/* unused now: DOF */
	short dofsta, dofend, dofmin, dofmax;

	/* ambient occlusion */
	float aodist, aodistfac, aoenergy, aobias;
	short aomode, aosamp, aomix, aocolor;
	float ao_adapt_thresh, ao_adapt_speed_fac;
	float ao_approx_error, ao_approx_correction;
	float ao_indirect_energy, ao_env_energy, ao_pad2;
	short ao_indirect_bounces, ao_pad;
	short ao_samp_method, ao_gather_method, ao_approx_passes;

	/* assorted settings (in the middle of ambient occlusion settings for padding reasons) */
	short flag;

	/* ambient occlusion (contd...) */
	float *aosphere, *aotables;


	struct Ipo *ipo  DNA_DEPRECATED;  /* old animation system, deprecated for 2.5 */
	struct MTex *mtex[18];		/* MAX_MTEX */
	short pr_texture, use_nodes, pad[2];

	/* previews */
	struct PreviewImage *preview;

	/* nodes */
	struct bNodeTree *nodetree;

	/* weather */
	short weather_flag;      /* WO_WEATHER_RAIN, WO_WEATHER_CLOUDS, WO_WEATHER_LENSFLARE (bits) */
	short rain_style;        /* WO_RAIN_STYLE_CLASSIC, WO_RAIN_STYLE_VOLUMETRIC */
	short weather_expand_flag; /* show_expanded_* dos efeitos de weather na UI, reusa os bits WO_WEATHER_* */
	short earthquake_mode;   /* WO_EARTHQUAKE_HORIZONTAL/VERTICAL/BOTH (era weather_pad3; arquivos antigos = 0 = horizontal) */

	float rain_intensity, rain_density, rain_speed, rain_wind, rain_darken, rain_ripple;
	float rain_ripple_distance, rain_ripple_min_up;
	float rain_ripple_normal; /* forca da normal das ondas (era rain_weather_pad; 0 = arquivo antigo = 1.0) */
	float rain_color[3];
	/* respingo nas superficies de cima e aura de riscos na silhueta, ver WO_WEATHER_RAIN_SPLASH/AURA */
	float rain_splash_size, rain_splash_rate, rain_splash_intensity, rain_splash_distance;
	float rain_aura_size, rain_aura_rate, rain_aura_intensity, rain_aura_distance;
	float rain_streak_width; /* largura dos riscos da chuva Classic (1 = original) */
	float rain_lightning_rate; /* raios por minuto no modo automatico, ver WO_WEATHER_RAIN_LIGHTNING */
	char  rain_aura_prop[64]; /* propriedade de jogo que marca os objetos com aura */
	float rain_lightning_intensity, rain_lightning_distance, rain_lightning_width;
	short rain_aura_style; /* WO_RAIN_AURA_STATIC/ANIMATED; ocupa o antigo pad, 0 = Static */
	short rain_aura_pad;
	/* Ripples e Splash com a mesma lista de ajustes (tamanho/taxa/normal/superficie de cima) */
	float rain_ripple_size, rain_ripple_rate;
	float rain_splash_normal, rain_splash_min_up;
	/* Pocas de agua nas superficies de cima, ver WO_WEATHER_RAIN_PUDDLES */
	float rain_puddle_amount, rain_puddle_size, rain_puddle_darkness;
	float rain_puddle_reflection, rain_puddle_distance, rain_puddle_min_up;

	float cloud_coverage, cloud_scale, cloud_speed;
	float cloud_color[3];

	int   earthquake_level; /* 0 (off) a 5 (extremo), ver WO_WEATHER_EARTHQUAKE */
	float earthquake_scale;  /* multiplicador da forca do terremoto, 0.1 a 5 (0 = arquivo antigo, tratado como 1) */
	short weather_editor_hide; /* bits WO_WEATHER_* (+ WO_WEATHER_FOG) escondidos so na viewport; era earthquake_pad2, 0 = tudo visivel */
	short weather_editor_pad;
	float earthquake_camera; /* tremor da camera ativa, 0 (off) a 2 (era earthquake_pad; arquivos antigos = 0) */

	char  sun_object_name[64]; /* nome do objeto Lamp, resolvido em runtime */
	float flare_scale, flare_intensity;

	/* Atmospheric sky (WO_SKYATMOSPHERIC): own parameters, independent of the sun lamp energy */
	float atmo_intensity;          /* brilho do ceu */
	float atmo_rayleigh_col[3];    /* cor do espalhamento Rayleigh (azul do ceu) */
	float atmo_rayleigh_density;   /* 1 = ar da Terra */
	float atmo_mie_density;        /* neblina/poeira, 1 = Terra */
	float atmo_mie_g;              /* direcao do Mie: brilho em volta do sol */
	float atmo_altitude;           /* altura da camera em metros */

	ListBase gpumaterial;		/* runtime */

	/* game engine: properties shared by all objects through the World ("World Properties") */
	ListBase prop;
} World;

/* **************** WORLD ********************* */

/* skytype */
#define WO_SKYBLEND             (1 << 0)
#define WO_SKYREAL              (1 << 1)
#define WO_SKYPAPER             (1 << 2)
#define WO_SKYATMOSPHERIC       (1 << 3)
#define WO_SKYATMOSPHERIC_STARS (1 << 4) // Draw stars

/* star_style */
#define WO_STARS_SIMPLE         0
#define WO_STARS_REALISTIC      1
#define WO_STARS_CONSTELLATIONS 2

/* aurora_flag / aurora_colors */
#define WO_AURORA_ENABLE        (1 << 0)
#define WO_AURORA_GREEN         0
#define WO_AURORA_CLASSIC       1
#define WO_AURORA_RAINBOW       2
/* while render: */
#define WO_SKYTEX               (1 << 5)
#define WO_ZENUP                (1 << 6)

/* mode */
#define WO_MIST                (1 << 0)
//#define WO_STARS               (1 << 1) /* deprecated */
/*#define WO_DOF                 (1 << 2) */
#define WO_ACTIVITY_CULLING    (1 << 3)
#define WO_ENV_LIGHT          (1 << 4)
#define WO_DBVT_CULLING       (1 << 5)
#define WO_AMB_OCC            (1 << 6)
#define WO_INDIRECT_LIGHT     (1 << 7)

/* weather_flag */
#define WO_WEATHER_RAIN            (1 << 0)
#define WO_WEATHER_CLOUDS          (1 << 1)
#define WO_WEATHER_LENSFLARE       (1 << 2)
#define WO_WEATHER_RAIN_DROPLETS   (1 << 3)
#define WO_WEATHER_RAIN_RIPPLE     (1 << 4)
#define WO_WEATHER_EARTHQUAKE      (1 << 5)
#define WO_WEATHER_RAIN_SPLASH     (1 << 6)
#define WO_WEATHER_RAIN_AURA       (1 << 7)

/* rain_aura_style */
#define WO_RAIN_AURA_STATIC   0
#define WO_RAIN_AURA_ANIMATED 1
#define WO_WEATHER_RAIN_LIGHTNING  (1 << 8)
/* So em weather_expand_flag/weather_editor_hide: o Fog continua sendo World.mode & WO_MIST. */
#define WO_WEATHER_FOG             (1 << 9)
/* Lightning: alguns raios correm na horizontal (nuvem a nuvem), nao so para baixo */
#define WO_WEATHER_RAIN_LIGHTNING_SIDE (1 << 10)
/* Pocas de agua no chao (Rain > Puddles) */
#define WO_WEATHER_RAIN_PUDDLES    (1 << 11)
/* Pocas refletem a cena por screen-space (SSR) antes de cair no ceu */
#define WO_WEATHER_RAIN_PUDDLE_SSR (1 << 12)
/* Ripples so dentro da agua das pocas (liga as Pocas junto) */
#define WO_WEATHER_RAIN_RIPPLE_PUDDLE (1 << 13)
/* Splash so dentro da agua das pocas (liga as Pocas junto) */
#define WO_WEATHER_RAIN_SPLASH_PUDDLE (1 << 14)

/* earthquake_mode */
#define WO_EARTHQUAKE_HORIZONTAL   0
#define WO_EARTHQUAKE_VERTICAL     1
#define WO_EARTHQUAKE_BOTH         2

/* rain_style */
#define WO_RAIN_STYLE_CLASSIC      0
#define WO_RAIN_STYLE_VOLUMETRIC   1

/* aomix */
enum {
	WO_AOADD    = 0,
#ifdef DNA_DEPRECATED
	WO_AOSUB    = 1,  /* deprecated */
	WO_AOADDSUB = 2,  /* deprecated */
#endif
	WO_AOMUL    = 3,
};

/* ao_samp_method - methods for sampling the AO hemi */
#define WO_AOSAMP_CONSTANT			0
#define WO_AOSAMP_HALTON			1
#define WO_AOSAMP_HAMMERSLEY		2

/* aomode (use distances & random sampling modes) */
#define WO_AODIST       (1 << 0)
#define WO_AORNDSMP     (1 << 1)
#define WO_AOCACHE      (1 << 2)

/* aocolor */
#define WO_AOPLAIN	0
#define WO_AOSKYCOL	1
#define WO_AOSKYTEX	2

/* ao_gather_method */
#define WO_AOGATHER_RAYTRACE	0
#define WO_AOGATHER_APPROX		1

/* texco (also in DNA_material_types.h) */
#define TEXCO_ANGMAP      (1 << 6)
#define TEXCO_H_SPHEREMAP (1 << 8)
#define TEXCO_H_TUBEMAP   (1 << 10)
#define TEXCO_EQUIRECTMAP (1 << 11)

/* mapto */
#define WOMAP_BLEND     (1 << 0)
#define WOMAP_HORIZ     (1 << 1)
#define WOMAP_ZENUP     (1 << 2)
#define WOMAP_ZENDOWN   (1 << 3)
// #define WOMAP_MIST   (1 << 4) /* Deprecated */

/* flag */
#define WO_DS_EXPAND	(1<<0)
	/* NOTE: this must have the same value as MA_DS_SHOW_TEXS,
	 * otherwise anim-editors will not read correctly
	 */
#define WO_DS_SHOW_TEXS	(1<<2)

#endif
