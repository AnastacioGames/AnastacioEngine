/* Lightmap UV atlas (xatlas, extern/xatlas) for the "Baked Lighting" bake operator
 * (release/scripts/startup/bl_operators/anastacio_lightmap.py). Loaded with ctypes; when it is
 * missing the operator falls back to bpy.ops.uv.lightmap_pack. */

#include <cstdint>
#include <vector>

#include "xatlas.h"

#ifdef _WIN32
#  define AE_EXPORT extern "C" __declspec(dllexport)
#else
#  define AE_EXPORT extern "C" __attribute__((visibility("default")))
#endif

/* Packs all meshes into one size x size atlas.
 * positions: xyz per vertex of every mesh in a row (already scaled to the wanted texel density),
 * indices: 3 per triangle, local to each mesh. Writes uv (0..1 of size) per triangle corner, in the
 * input order; corners xatlas dropped (degenerate faces) get 0,0. Returns 0 on success. */
AE_EXPORT int ae_uvatlas(int mesh_count, const int *vert_counts, const float *positions,
                         const int *tri_counts, const uint32_t *indices, int size, int padding,
                         int brute_force, float *out_uv)
{
	xatlas::Atlas *atlas = xatlas::Create();
	const float *pos = positions;
	const uint32_t *idx = indices;
	for (int m = 0; m < mesh_count; m++) {
		xatlas::MeshDecl decl;
		decl.vertexPositionData = pos;
		decl.vertexPositionStride = sizeof(float) * 3;
		decl.vertexCount = (uint32_t)vert_counts[m];
		decl.indexData = idx;
		decl.indexCount = (uint32_t)tri_counts[m] * 3;
		decl.indexFormat = xatlas::IndexFormat::UInt32;
		if (xatlas::AddMesh(atlas, decl, (uint32_t)mesh_count) != xatlas::AddMeshError::Success) {
			xatlas::Destroy(atlas);
			return 1;
		}
		pos += vert_counts[m] * 3;
		idx += tri_counts[m] * 3;
	}
	xatlas::ComputeCharts(atlas);

	/* xatlas only estimates the density from the resolution: search the largest texels per unit whose
	 * single atlas still fits in size x size, so the charts fill the lightmap */
	xatlas::PackOptions pack;
	pack.padding = (uint32_t)padding;
	pack.bilinear = true;
	pack.bruteForce = brute_force != 0;
	pack.resolution = (uint32_t)size;
	xatlas::PackCharts(atlas, pack);
	pack.resolution = 0; /* from here on: one atlas whose size follows the density */
	float lo = 0.0f, hi = atlas->texelsPerUnit * 2.0f;
	for (int i = 0; i < 12; i++) {
		pack.texelsPerUnit = (i == 0) ? atlas->texelsPerUnit : 0.5f * (lo + hi);
		xatlas::PackCharts(atlas, pack);
		if (atlas->width <= (uint32_t)size && atlas->height <= (uint32_t)size) {
			lo = pack.texelsPerUnit;
		}
		else {
			hi = pack.texelsPerUnit;
		}
		if (hi - lo < hi * 0.005f) {
			break;
		}
	}
	if (lo <= 0.0f) {
		xatlas::Destroy(atlas);
		return 2;
	}
	if (pack.texelsPerUnit != lo) {
		pack.texelsPerUnit = lo;
		xatlas::PackCharts(atlas, pack);
	}

	const float inv = 1.0f / (float)size;
	float *uv = out_uv;
	for (uint32_t m = 0; m < atlas->meshCount; m++) {
		const xatlas::Mesh &mesh = atlas->meshes[m];
		for (uint32_t i = 0; i < mesh.indexCount; i++) {
			const xatlas::Vertex &v = mesh.vertexArray[mesh.indexArray[i]];
			uv[0] = v.chartIndex < 0 ? 0.0f : v.uv[0] * inv;
			uv[1] = v.chartIndex < 0 ? 0.0f : v.uv[1] * inv;
			uv += 2;
		}
	}
	xatlas::Destroy(atlas);
	return 0;
}
