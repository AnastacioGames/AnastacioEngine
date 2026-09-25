/*
 * Copyright 2011-2016 Blender Foundation
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#ifndef __UTIL_IMAGE_IMPL_H__
#define __UTIL_IMAGE_IMPL_H__

#include "util/util_algorithm.h"
#include "util/util_half.h"
#include "util/util_image.h"

CCL_NAMESPACE_BEGIN

namespace {

template<typename T>
const T *util_image_read(const vector<T>& pixels,
                         const size_t width,
                         const size_t height,
                         const size_t /*depth*/,
                         const size_t components,
                         const size_t x, const size_t y, const size_t z) {
	const size_t index = ((size_t)z * (width * height) +
	                      (size_t)y * width +
	                      (size_t)x) * components;
	return &pixels[index];
}

template<typename T>
void util_image_downscale_sample(const vector<T>& pixels,
                                 const size_t width,
                                 const size_t height,
                                 const size_t depth,
                                 const size_t components,
                                 const size_t kernel_size,
                                 const float x,
                                 const float y,
                                 const float z,
                                 T *result)
{
	assert(components <= 4);
	const size_t ix = (size_t)x,
	             iy = (size_t)y,
	             iz = (size_t)z;
	/* TODO(sergey): Support something smarter than box filer. */
	float accum[4] = {0};
	size_t count = 0;
	for(size_t dz = 0; dz < kernel_size; ++dz) {
		for(size_t dy = 0; dy < kernel_size; ++dy) {
			for(size_t dx = 0; dx < kernel_size; ++dx) {
				const size_t nx = ix + dx,
				             ny = iy + dy,
				             nz = iz + dz;
				if(nx >= width || ny >= height || nz >= depth) {
					continue;
				}
				const T *pixel = util_image_read(pixels,
				                                 width, height, depth,
				                                 components,
				                                 nx, ny, nz);
				for(size_t k = 0; k < components; ++k) {
					accum[k] += util_image_cast_to_float(pixel[k]);
				}
				++count;
			}
		}
	}
	if(count != 0) {
		const float inv_count = 1.0f / (float)count;
		for(size_t k = 0; k < components; ++k) {
			result[k] = util_image_cast_from_float<T>(accum[k] * inv_count);
		}
	}
	else {
		for(size_t k = 0; k < components; ++k) {
			result[k] = T(0.0f);
		}
	}
}

template<typename T>
void util_image_downscale_pixels(const vector<T>& input_pixels,
                                 const size_t input_width,
                                 const size_t input_height,
                                 const size_t input_depth,
                                 const size_t components,
                                 const float inv_scale_factor,
                                 const size_t output_width,
                                 const size_t output_height,
                                 const size_t output_depth,
                                 vector<T> *output_pixels)
{
	const size_t kernel_size = (size_t)(inv_scale_factor + 0.5f);
	for(size_t z = 0; z < output_depth; ++z) {
		for(size_t y = 0; y < output_height; ++y) {
			for(size_t x = 0; x < output_width; ++x) {
				const float input_x = (float)x * inv_scale_factor,
				            input_y = (float)y * inv_scale_factor,
				            input_z = (float)z * inv_scale_factor;
				const size_t output_index =
				        (z * output_width * output_height +
				         y * output_width + x) * components;
				util_image_downscale_sample(input_pixels,
				                            input_width, input_height, input_depth,
				                            components,
				                            kernel_size,
				                            input_x, input_y, input_z,
				                            &output_pixels->at(output_index));
			}
		}
	}
}

/* Maps an output pixel center to the two nearest input pixels along one axis
 * and the weight of the second one. */
inline void util_image_upscale_axis(const size_t output_coord,
                                    const size_t input_size,
                                    const float inv_scale_factor,
                                    size_t *i0,
                                    size_t *i1,
                                    float *t)
{
	float coord = ((float)output_coord + 0.5f) * inv_scale_factor - 0.5f;
	coord = min(max(coord, 0.0f), (float)(input_size - 1));
	*i0 = min((size_t)coord, input_size - 1);
	*i1 = min(*i0 + 1, input_size - 1);
	*t = coord - (float)(*i0);
}

template<typename T>
void util_image_upscale_pixels(const vector<T>& input_pixels,
                               const size_t input_width,
                               const size_t input_height,
                               const size_t input_depth,
                               const size_t components,
                               const size_t output_width,
                               const size_t output_height,
                               const size_t output_depth,
                               vector<T> *output_pixels)
{
	assert(components <= 4);
	if(input_width == 0 || input_height == 0 || input_depth == 0) {
		std::fill(output_pixels->begin(), output_pixels->end(), T(0.0f));
		return;
	}
	/* Per axis factors, so truncated output sizes and axes that are kept at
	 * their input size still cover the whole input. */
	const float inv_scale_x = (float)input_width / (float)output_width,
	            inv_scale_y = (float)input_height / (float)output_height,
	            inv_scale_z = (float)input_depth / (float)output_depth;
	for(size_t z = 0; z < output_depth; ++z) {
		size_t z0, z1;
		float tz;
		util_image_upscale_axis(z, input_depth, inv_scale_z, &z0, &z1, &tz);
		for(size_t y = 0; y < output_height; ++y) {
			size_t y0, y1;
			float ty;
			util_image_upscale_axis(y, input_height, inv_scale_y, &y0, &y1, &ty);
			for(size_t x = 0; x < output_width; ++x) {
				size_t x0, x1;
				float tx;
				util_image_upscale_axis(x, input_width, inv_scale_x, &x0, &x1, &tx);
				const size_t corner_x[2] = {x0, x1},
				             corner_y[2] = {y0, y1},
				             corner_z[2] = {z0, z1};
				const float weight_x[2] = {1.0f - tx, tx},
				            weight_y[2] = {1.0f - ty, ty},
				            weight_z[2] = {1.0f - tz, tz};
				float accum[4] = {0};
				for(int dz = 0; dz < 2; ++dz) {
					for(int dy = 0; dy < 2; ++dy) {
						for(int dx = 0; dx < 2; ++dx) {
							const float weight = weight_x[dx] * weight_y[dy] * weight_z[dz];
							const T *pixel = util_image_read(input_pixels,
							                                 input_width, input_height, input_depth,
							                                 components,
							                                 corner_x[dx], corner_y[dy], corner_z[dz]);
							for(size_t k = 0; k < components; ++k) {
								accum[k] += weight * util_image_cast_to_float(pixel[k]);
							}
						}
					}
				}
				const size_t output_index =
				        (z * output_width * output_height +
				         y * output_width + x) * components;
				T *result = &output_pixels->at(output_index);
				for(size_t k = 0; k < components; ++k) {
					result[k] = util_image_cast_from_float<T>(accum[k]);
				}
			}
		}
	}
}

}  /* namespace */

template<typename T>
void util_image_resize_pixels(const vector<T>& input_pixels,
                              const size_t input_width,
                              const size_t input_height,
                              const size_t input_depth,
                              const size_t components,
                              const float scale_factor,
                              vector<T> *output_pixels,
                              size_t *output_width,
                              size_t *output_height,
                              size_t *output_depth)
{
	/* Early output for case when no scaling is applied. */
	if(scale_factor == 1.0f) {
		*output_width = input_width;
		*output_height = input_height;
		*output_depth = input_depth;
		*output_pixels = input_pixels;
		return;
	}
	/* First of all, we calculate output image dimensions.
	 * We clamp them to be 1 pixel at least so we do not generate degenerate
	 * image.
	 */
	*output_width = max((size_t)((float)input_width * scale_factor), (size_t)1);
	*output_height = max((size_t)((float)input_height * scale_factor), (size_t)1);
	*output_depth = max((size_t)((float)input_depth * scale_factor), (size_t)1);
	/* 2D images are stored with a depth of 1; upscaling must not turn them
	 * into volumes. */
	if(input_depth == 1) {
		*output_depth = 1;
	}
	/* Prepare pixel storage for the result. */
	const size_t num_output_pixels = ((*output_width) *
	                                  (*output_height) *
	                                  (*output_depth)) * components;
	output_pixels->resize(num_output_pixels);
	if(scale_factor < 1.0f) {
		const float inv_scale_factor = 1.0f / scale_factor;
		util_image_downscale_pixels(input_pixels,
		                            input_width, input_height, input_depth,
		                            components,
		                            inv_scale_factor,
		                            *output_width, *output_height, *output_depth,
		                            output_pixels);
	} else {
		util_image_upscale_pixels(input_pixels,
		                          input_width, input_height, input_depth,
		                          components,
		                          *output_width, *output_height, *output_depth,
		                          output_pixels);
	}
}

CCL_NAMESPACE_END

#endif  /* __UTIL_IMAGE_IMPL_H__ */
