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

#include "render/buffers.h"
#include "render/tile.h"

CCL_NAMESPACE_BEGIN

/* Regression tests for CYC-003: width * height products at the RNA limit
 * (65536 x 65536) don't fit in int, so tile bookkeeping must widen them. */

static const int MAX_RESOLUTION = 65536;
static const uint64_t MAX_PIXELS = (uint64_t)MAX_RESOLUTION * MAX_RESOLUTION;

static void reset_tile_manager(TileManager& tile_manager, int width, int height, int samples)
{
	BufferParams params;
	params.width = params.full_width = width;
	params.height = params.full_height = height;
	tile_manager.reset(params, samples);
}

TEST(render_tile, total_pixel_samples_at_max_resolution)
{
	TileManager tile_manager(false, 1, make_int2(64, 64), INT_MAX, false, true, TILE_CENTER);
	reset_tile_manager(tile_manager, MAX_RESOLUTION, MAX_RESOLUTION, 4);

	EXPECT_EQ(tile_manager.state.total_pixel_samples, 4 * MAX_PIXELS);
}

TEST(render_tile, total_pixel_samples_with_denoising)
{
	TileManager tile_manager(false, 1, make_int2(64, 64), INT_MAX, false, true, TILE_CENTER);
	tile_manager.schedule_denoising = true;
	reset_tile_manager(tile_manager, MAX_RESOLUTION, MAX_RESOLUTION, 1);

	/* One pass of samples plus one denoising pass over every pixel. */
	EXPECT_EQ(tile_manager.state.total_pixel_samples, 2 * MAX_PIXELS);
}

TEST(render_tile, resolution_divider)
{
	TileManager tile_manager(true, 1, make_int2(64, 64), 64, false, false, TILE_CENTER);

	reset_tile_manager(tile_manager, 1920, 1080, 1);
	EXPECT_EQ(tile_manager.state.resolution_divider, 32);

	/* 65536 * 65536 wraps to 0 in int, which used to skip the division. */
	reset_tile_manager(tile_manager, MAX_RESOLUTION, MAX_RESOLUTION, 1);
	EXPECT_EQ(tile_manager.state.resolution_divider, 1024);
}

TEST(render_tile, preview_pixel_samples_at_max_resolution)
{
	TileManager tile_manager(true, 1, make_int2(64, 64), 64, false, false, TILE_CENTER);
	reset_tile_manager(tile_manager, MAX_RESOLUTION, MAX_RESOLUTION, 1);

	/* Preview passes at dividers 512 .. 2 render 128^2 .. 32768^2 pixels,
	 * i.e. 4^7 + ... + 4^15, followed by the full resolution samples. */
	uint64_t preview_pixels = 0;
	for(int k = 7; k <= 15; k++) {
		preview_pixels += (uint64_t)1 << (2 * k);
	}
	EXPECT_EQ(tile_manager.state.total_pixel_samples, preview_pixels + MAX_PIXELS);
}

CCL_NAMESPACE_END
