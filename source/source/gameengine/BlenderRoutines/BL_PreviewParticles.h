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
 */

/** \file gameengine/BlenderRoutines/BL_PreviewParticles.h
 *  \ingroup blroutines
 *
 * 3D View preview of the GPU particle emitters (Object.use_gpu_particles / use_gpu_particles_mix): the same
 * RAS_ParticleBuffer the game uses (simulation, looks, flipbook, curves), driven from the viewport draw so
 * the particles are seen without playing. C interface for the editor (space_view3d).
 */

#ifndef __BL_PREVIEWPARTICLES_H__
#define __BL_PREVIEWPARTICLES_H__

#ifdef __cplusplus
extern "C" {
#endif

struct Scene;

/** Steps the simulation of every emitter of the scene on the layers `layers` by the real time elapsed since
 *  the last call, then draws it with the matrices of the current view (column-major, as Blender stores them).
 *  Creates (or rebuilds, when the settings changed) the buffers on demand. Returns the number of emitters
 *  drawn. Needs a GL context with transform feedback (the same the game uses). */
int BL_preview_particles_draw(struct Scene *scene, unsigned int layers,
                              const float viewmat[4][4], const float winmat[4][4]);

/** Frees every buffer (GL context current): at exit, on new file, when the preview is turned off. */
void BL_preview_particles_free(void);

#ifdef __cplusplus
}
#endif

#endif  /* __BL_PREVIEWPARTICLES_H__ */
