/** \file CcdCookedData.h
 *  \ingroup physbullet
 *  Cooked conversion data ("<game>.cooked"): results of expensive shape computations, keyed by a hash
 *  of the mesh vertices so an edited mesh simply misses the cache. Playing a .blend records new
 *  entries; the exported game only reads the file that Export Game copies next to it.
 *  Also keeps the GL program binaries of the material shaders (GPU_shader_binary_cache_set). They only
 *  work on the GPU and driver that made them, so the exported game also keeps its own shaders in a
 *  per user cache file (the game folder may be read-only), filled while playing and by the warm-up.
 */

#ifndef __CCD_COOKED_DATA_H__
#define __CCD_COOKED_DATA_H__

#include <string>
#include <vector>

#include "LinearMath/btScalar.h"

namespace CcdCookedData
{
/** Loads the cooked file of the main game file (its path without extension + ".cooked") and, for an
 *  exported game, its user shader cache. deviceKey: GPU_shader_binary_device_key(), 0 without binaries.
 */
void Open(const std::string& mainFile, unsigned long long deviceKey);
/// The user shader cache is missing or made by another GPU/driver: every shader should be compiled once.
bool NeedsWarmUp();
/// Writes the file back when recording and new entries were added, then forgets everything.
void Close();

/** Convex hull points of the given vertices (x, y, z per vertex).
 *  \return false when not cooked: the caller computes the hull and calls AddHull().
 */
bool FindHull(const btScalar *vertices, unsigned int numVertices, std::vector<btScalar>& points);
void AddHull(const btScalar *vertices, unsigned int numVertices, const btScalar *points, unsigned int numPoints);

/// GL program binary of a shader key (GPUShaderBinaryFind/Add signatures), nullptr when not cooked.
const void *FindShader(unsigned long long key, unsigned int *format, int *size);
void AddShader(unsigned long long key, unsigned int format, const void *data, int size);
}

#endif  // __CCD_COOKED_DATA_H__
