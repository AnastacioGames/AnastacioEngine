/*
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

#include "testing/testing.h"

#include "util/util_half.h"
#include "util/util_image.h"

CCL_NAMESPACE_BEGIN

/* The upscale branch of util_image_resize_pixels used to allocate the output
 * and leave it unfilled. Outputs are pre-filled with a sentinel so unwritten
 * pixels show up. */

static const float SENTINEL = -1.0f;

struct ResizeResult {
	vector<float> pixels;
	size_t width, height, depth;
};

static ResizeResult resize(const vector<float>& pixels,
                           size_t width, size_t height, size_t depth,
                           size_t components,
                           float scale_factor)
{
	ResizeResult result;
	result.pixels.resize(4096, SENTINEL);
	util_image_resize_pixels(pixels,
	                         width, height, depth,
	                         components,
	                         scale_factor,
	                         &result.pixels,
	                         &result.width, &result.height, &result.depth);
	return result;
}

TEST(util_image, no_scale_copies)
{
	const vector<float> pixels = {0.0f, 1.0f, 2.0f, 3.0f};
	ResizeResult r = resize(pixels, 2, 2, 1, 1, 1.0f);
	EXPECT_EQ(r.width, 2);
	EXPECT_EQ(r.height, 2);
	EXPECT_EQ(r.depth, 1);
	EXPECT_EQ(r.pixels, pixels);
}

TEST(util_image, downscale_box_filter)
{
	const vector<float> pixels = {0.0f, 1.0f, 2.0f, 3.0f};
	ResizeResult r = resize(pixels, 2, 2, 1, 1, 0.5f);
	EXPECT_EQ(r.width, 1);
	EXPECT_EQ(r.height, 1);
	EXPECT_EQ(r.depth, 1);
	ASSERT_EQ(r.pixels.size(), 1);
	EXPECT_FLOAT_EQ(r.pixels[0], 1.5f);
}

TEST(util_image, upscale_keeps_2d_depth)
{
	const vector<float> pixels(2 * 3, 0.5f);
	ResizeResult r = resize(pixels, 2, 3, 1, 1, 2.0f);
	EXPECT_EQ(r.width, 4);
	EXPECT_EQ(r.height, 6);
	EXPECT_EQ(r.depth, 1);
	ASSERT_EQ(r.pixels.size(), 4 * 6);
	for(size_t i = 0; i < r.pixels.size(); i++) {
		EXPECT_FLOAT_EQ(r.pixels[i], 0.5f) << "pixel " << i;
	}
}

TEST(util_image, upscale_linear_row)
{
	/* Output pixel centers map to input x = -0.25, 0.25, 0.75, 1.25, clamped
	 * to the edge pixels. */
	const vector<float> pixels = {0.0f, 1.0f};
	ResizeResult r = resize(pixels, 2, 1, 1, 1, 2.0f);
	EXPECT_EQ(r.width, 4);
	EXPECT_EQ(r.height, 2);
	ASSERT_EQ(r.pixels.size(), 4 * 2);
	const float expected[4] = {0.0f, 0.25f, 0.75f, 1.0f};
	for(size_t y = 0; y < 2; y++) {
		for(size_t x = 0; x < 4; x++) {
			EXPECT_FLOAT_EQ(r.pixels[y * 4 + x], expected[x]) << x << ", " << y;
		}
	}
}

TEST(util_image, upscale_components_stay_separate)
{
	const vector<float> pixels = {0.1f, 0.2f, 0.3f, 0.4f,
	                              0.1f, 0.2f, 0.3f, 0.4f};
	ResizeResult r = resize(pixels, 2, 1, 1, 4, 3.0f);
	EXPECT_EQ(r.width, 6);
	EXPECT_EQ(r.height, 3);
	ASSERT_EQ(r.pixels.size(), 6 * 3 * 4);
	for(size_t i = 0; i < r.pixels.size(); i += 4) {
		EXPECT_FLOAT_EQ(r.pixels[i + 0], 0.1f);
		EXPECT_FLOAT_EQ(r.pixels[i + 1], 0.2f);
		EXPECT_FLOAT_EQ(r.pixels[i + 2], 0.3f);
		EXPECT_FLOAT_EQ(r.pixels[i + 3], 0.4f);
	}
}

TEST(util_image, upscale_fractional_fills_everything)
{
	/* 3 x 3 x 3 volume at 1.5 gives 4 x 4 x 4. */
	vector<float> pixels(3 * 3 * 3);
	for(size_t i = 0; i < pixels.size(); i++) {
		pixels[i] = (float)i / (float)(pixels.size() - 1);
	}
	ResizeResult r = resize(pixels, 3, 3, 3, 1, 1.5f);
	EXPECT_EQ(r.width, 4);
	EXPECT_EQ(r.height, 4);
	EXPECT_EQ(r.depth, 4);
	ASSERT_EQ(r.pixels.size(), 4 * 4 * 4);
	for(size_t i = 0; i < r.pixels.size(); i++) {
		EXPECT_GE(r.pixels[i], 0.0f) << "pixel " << i;
		EXPECT_LE(r.pixels[i], 1.0f) << "pixel " << i;
	}
	/* Corners map onto the input corners. */
	EXPECT_FLOAT_EQ(r.pixels[0], 0.0f);
	EXPECT_FLOAT_EQ(r.pixels[r.pixels.size() - 1], 1.0f);
}

TEST(util_image, upscale_uchar)
{
	const vector<uchar> pixels = {0, 255};
	vector<uchar> output(64, 7);
	size_t width, height, depth;
	util_image_resize_pixels(pixels, 2, 1, 1, 1, 2.0f,
	                         &output, &width, &height, &depth);
	EXPECT_EQ(width, 4);
	EXPECT_EQ(height, 2);
	EXPECT_EQ(depth, 1);
	ASSERT_EQ(output.size(), 4 * 2);
	const uchar expected[4] = {0, 64, 191, 255};
	for(size_t y = 0; y < 2; y++) {
		for(size_t x = 0; x < 4; x++) {
			EXPECT_EQ(output[y * 4 + x], expected[x]) << x << ", " << y;
		}
	}
}

TEST(util_image, upscale_empty_input)
{
	ResizeResult r = resize(vector<float>(), 0, 0, 0, 1, 2.0f);
	EXPECT_EQ(r.width, 1);
	EXPECT_EQ(r.height, 1);
	EXPECT_EQ(r.depth, 1);
	ASSERT_EQ(r.pixels.size(), 1);
	EXPECT_EQ(r.pixels[0], 0.0f);
}

CCL_NAMESPACE_END
