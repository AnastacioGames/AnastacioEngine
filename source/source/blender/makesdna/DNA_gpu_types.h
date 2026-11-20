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

/** \file DNA_gpu_types.h
 *  \ingroup DNA
 */

#ifndef __DNA_GPU_TYPES_H__
#define __DNA_GPU_TYPES_H__

/* properties for dof effect */
typedef struct GPUDOFSettings {
	float focus_distance; /* focal distance for depth of field */
	float fstop;
	float focal_length;
	float sensor;
	int num_blades;
	int high_quality;
} GPUDOFSettings;

typedef struct GPUFXSettings {
	GPUDOFSettings *dof;
	char fx_flag;  /* eGPUFXFlags */
	char fx_flag2; /* eGPUFXFlags2 */
	char pad[6];
} GPUFXSettings;

/* shaderfx enables */
typedef enum eGPUFXFlags {
	GPU_FX_FLAG_DOF         = (1 << 0),
	/* preview of the active camera's Game FX lens: chromatic aberration, vignette, fisheye */
	GPU_FX_FLAG_CAMERA_LENS = (1 << 1),
	/* preview of the scene's compositor nodes as the game runs them (Compositing in the game) */
	GPU_FX_FLAG_NODE_COMPOSITOR = (1 << 2),
	/* preview of the Custom Filter actuators declared in the scene (2D Filters in the game) */
	GPU_FX_FLAG_2D_FILTERS  = (1 << 3),
	/* preview of the active camera's Game FX depth of field (the game's bokeh pass) */
	GPU_FX_FLAG_CAMERA_DOF  = (1 << 4),
	/* preview of the active camera's Game FX Directional / Speed Blur from the view's own motion */
	GPU_FX_FLAG_CAMERA_MOTION = (1 << 5),
	/* preview of the scene's TAA (Scene > Post-process), converged over the view's redraws */
	GPU_FX_FLAG_TAA         = (1 << 6),
	/* preview of the scene's Native SSGI (game material buffers + the game's passes) */
	GPU_FX_FLAG_SSGI        = (1 << 7),
} eGPUFXFlags;

/* second byte of shaderfx enables (fx_flag has no free bit left) */
typedef enum eGPUFXFlags2 {
	/* preview of the GPU particle emitters (Object > Particles) with the game's own buffer */
	GPU_FX2_PARTICLES = (1 << 0),
} eGPUFXFlags2;

#endif  /* __DNA_GPU_TYPES_H__ */
