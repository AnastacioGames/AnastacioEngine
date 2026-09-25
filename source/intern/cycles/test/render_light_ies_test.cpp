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

#include <sstream>

#include "device/device.h"
#include "render/light.h"
#include "render/scene.h"
#include "util/util_profiling.h"
#include "util/util_stats.h"

CCL_NAMESPACE_BEGIN

/* Regression tests for CYC-005: the packed IES table is now sized in size_t.
 * Exceeding INT_MAX needs gigabytes of profiles, so these cover the offset
 * table layout that the rewrite must keep intact. */

namespace {

class IESLightManager : public LightManager {
public:
	using LightManager::device_update_ies;
};

/* Type C profile with a single horizontal angle and num_v vertical angles.
 * Packs to 2 + 2 + num_v + 2 * num_v floats. */
string ies_profile(int num_v)
{
	std::ostringstream ss;
	ss << "IESNA:LM-63-2002\nTILT=NONE\n";
	ss << "1 1000 1 " << num_v << " 1 1 1 0 0 0\n1 1 100\n";
	for(int i = 0; i < num_v; i++) {
		ss << i * 90.0 / (num_v - 1) << " ";
	}
	ss << "\n0\n";
	for(int i = 0; i < num_v; i++) {
		ss << "100 ";
	}
	ss << "\n";
	return ss.str();
}

int packed_size(int num_v)
{
	return 2 + 2 + num_v + 2 * num_v;
}

}  // namespace

class RenderLightIES : public testing::Test
{
protected:
	Stats stats;
	Profiler profiler;
	DeviceInfo device_info;
	Device *device_cpu;
	DeviceScene *dscene;
	IESLightManager light_manager;

	virtual void SetUp()
	{
		device_cpu = Device::create(device_info, stats, profiler, true);
		dscene = new DeviceScene(device_cpu);
	}

	virtual void TearDown()
	{
		delete dscene;
		delete device_cpu;
	}

	int table_int(size_t i)
	{
		return __float_as_int(dscene->ies_lights.data()[i]);
	}
};

TEST_F(RenderLightIES, offset_table)
{
	EXPECT_EQ(light_manager.add_ies(ustring(ies_profile(3))), 0);
	EXPECT_EQ(light_manager.add_ies(ustring("not an IES file")), 1);
	EXPECT_EQ(light_manager.add_ies(ustring(ies_profile(5))), 2);

	light_manager.device_update_ies(dscene);

	ASSERT_EQ(dscene->ies_lights.size(), (size_t)(3 + packed_size(3) + packed_size(5)));
	EXPECT_EQ(table_int(0), 3);
	EXPECT_EQ(table_int(1), -1);
	EXPECT_EQ(table_int(2), 3 + packed_size(3));

	/* Each packed profile starts with its horizontal and vertical counts. */
	EXPECT_EQ(table_int(3), 2);
	EXPECT_EQ(table_int(4), 3);
	EXPECT_EQ(table_int(3 + packed_size(3)), 2);
	EXPECT_EQ(table_int(3 + packed_size(3) + 1), 5);
}

TEST_F(RenderLightIES, removed_slot_becomes_invalid)
{
	light_manager.add_ies(ustring(ies_profile(3)));
	light_manager.add_ies(ustring(ies_profile(5)));
	light_manager.remove_ies(0);

	light_manager.device_update_ies(dscene);

	ASSERT_EQ(dscene->ies_lights.size(), (size_t)(2 + packed_size(5)));
	EXPECT_EQ(table_int(0), -1);
	EXPECT_EQ(table_int(1), 2);
}

TEST_F(RenderLightIES, trailing_removed_slots_are_dropped)
{
	light_manager.add_ies(ustring(ies_profile(3)));
	light_manager.add_ies(ustring(ies_profile(5)));
	light_manager.remove_ies(1);

	light_manager.device_update_ies(dscene);

	ASSERT_EQ(dscene->ies_lights.size(), (size_t)(1 + packed_size(3)));
	EXPECT_EQ(table_int(0), 1);
}

CCL_NAMESPACE_END
