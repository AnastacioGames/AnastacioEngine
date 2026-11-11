/* meshoptimizer (extern/meshoptimizer) for editor tools: Build HLOD "Sloppy" mode
 * (release/scripts/startup/bl_operators/anastacio_hlod.py). Loaded with ctypes. */

#include <cstddef>

#include "meshoptimizer.h"

#ifdef _WIN32
#  define AE_EXPORT extern "C" __declspec(dllexport)
#else
#  define AE_EXPORT extern "C" __attribute__((visibility("default")))
#endif

/* meshopt_simplifySloppy: positions xyz per vertex, indices 3 per triangle. out must hold
 * index_count indices. Returns the index count written (0 when nothing is left or on bad input);
 * out_error gets the relative error reached (fraction of the mesh extent). */
AE_EXPORT int ae_simplify_sloppy(const float *positions, int vertex_count, const unsigned int *indices,
                                 int index_count, int target_index_count, float target_error,
                                 unsigned int *out, float *out_error)
{
	if (vertex_count <= 0 || index_count <= 0 || index_count % 3 || !positions || !indices || !out) {
		return 0;
	}
	for (int i = 0; i < index_count; i++) {
		if (indices[i] >= (unsigned int)vertex_count) {
			return 0;
		}
	}
	int target = target_index_count - target_index_count % 3;
	if (target < 3) {
		target = 3;
	}
	float err = 0.0f;
	size_t n = meshopt_simplifySloppy(out, indices, (size_t)index_count, positions, (size_t)vertex_count,
	                                  sizeof(float) * 3, (size_t)target, target_error, &err);
	if (out_error) {
		*out_error = err;
	}
	return (int)n;
}
