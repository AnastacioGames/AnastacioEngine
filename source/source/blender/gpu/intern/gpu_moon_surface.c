/* SPDX-License-Identifier: GPL-2.0-or-later
 * Optional visual moon surface. The formula follows sky_moon's procedural albedo;
 * CPU/GPU sin precision and finite sampling intentionally need visual validation.
 * No camera, sun, size or brightness belongs in this immutable surface cache. */
#include <math.h>

#include "MEM_guardedalloc.h"
#include "GPU_texture.h"
#include "gpu_private.h"

#define MOON_SURFACE_SIZE 512
static GPUTexture *moon_surface;

static float moon_mix(float a, float b, float f)
{
	return a + (b - a) * f;
}

static float moon_hash(float x, float y, float z)
{
	float h = sinf(x * 127.1f + y * 311.7f + z * 74.7f) * 43758.5453f;
	return h - floorf(h);
}

static float moon_noise(float x, float y, float z)
{
	float ix = floorf(x), iy = floorf(y), iz = floorf(z);
	x -= ix; y -= iy; z -= iz;
	x = x * x * (3.0f - 2.0f * x);
	y = y * y * (3.0f - 2.0f * y);
	z = z * z * (3.0f - 2.0f * z);
	return moon_mix(
	    moon_mix(moon_mix(moon_hash(ix, iy, iz), moon_hash(ix + 1, iy, iz), x),
	             moon_mix(moon_hash(ix, iy + 1, iz), moon_hash(ix + 1, iy + 1, iz), x), y),
	    moon_mix(moon_mix(moon_hash(ix, iy, iz + 1), moon_hash(ix + 1, iy, iz + 1), x),
	             moon_mix(moon_hash(ix, iy + 1, iz + 1), moon_hash(ix + 1, iy + 1, iz + 1), x), y), z);
}

static float moon_fbm(float x, float y, float z)
{
	return 0.5f * moon_noise(x, y, z) + 0.25f * moon_noise(x * 2.03f, y * 2.03f, z * 2.03f) +
	       0.125f * moon_noise(x * 4.01f, y * 4.01f, z * 4.01f) +
	       0.0625f * moon_noise(x * 8.07f, y * 8.07f, z * 8.07f);
}

static float moon_smooth(float lo, float hi, float x)
{
	float t = fminf(fmaxf((x - lo) / (hi - lo), 0.0f), 1.0f);
	return t * t * (3.0f - 2.0f * t);
}

GPUTexture *gpu_moon_surface_texture(void)
{
	if (moon_surface) return moon_surface;
	float *pixels = MEM_mallocN(sizeof(float) * MOON_SURFACE_SIZE * MOON_SURFACE_SIZE * 4,
	                            "precomputed moon surface");
	for (int y = 0; y < MOON_SURFACE_SIZE; ++y) {
		for (int x = 0; x < MOON_SURFACE_SIZE; ++x) {
			float nx = 2.0f * ((x + 0.5f) / MOON_SURFACE_SIZE) - 1.0f;
			float ny = 2.0f * ((y + 0.5f) / MOON_SURFACE_SIZE) - 1.0f;
			float nz = sqrtf(fmaxf(1.0f - nx * nx - ny * ny, 0.0f));
			float maria = moon_smooth(0.48f, 0.62f, moon_fbm(nx * 2.2f + 4.1f, ny * 2.2f + 1.7f, nz * 2.2f + 0.3f));
			float fine = moon_fbm(nx * 14.0f + 7.0f, ny * 14.0f + 7.0f, nz * 14.0f + 7.0f);
			float crat = moon_smooth(0.62f, 0.75f, moon_fbm(nx * 26.0f + 2.0f, ny * 26.0f + 2.0f, nz * 26.0f + 2.0f));
			float albedo = moon_mix(0.95f, 0.52f, maria) * (0.82f + 0.3f * fine) + 0.15f * crat * (1.0f - maria);
			float *pixel = pixels + (y * MOON_SURFACE_SIZE + x) * 4;
			pixel[0] = pixel[1] = pixel[2] = albedo;
			pixel[3] = 1.0f;
		}
	}
	moon_surface = GPU_texture_create_2D(MOON_SURFACE_SIZE, MOON_SURFACE_SIZE, pixels, GPU_HDR_NONE, NULL);
	MEM_freeN(pixels);
	return moon_surface;
}

void gpu_moon_surface_exit(void)
{
	if (moon_surface) GPU_texture_free(moon_surface);
	moon_surface = NULL;
}
