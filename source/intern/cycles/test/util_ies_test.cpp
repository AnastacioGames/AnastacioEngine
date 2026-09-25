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

#include <iomanip>
#include <sstream>

#include "util/util_ies.h"
#include "util/util_string.h"
#include "util/util_vector.h"

CCL_NAMESPACE_BEGIN

/* Regression tests for CYC-002: counts read from the IES text must be
 * validated before they size any allocation. */

static string ies_text(const string& tilt,
                       const string& v_num,
                       const string& h_num,
                       const vector<double>& v_angles,
                       const vector<double>& h_angles)
{
	std::ostringstream ss;
	ss << std::setprecision(10);
	ss << "IESNA:LM-63-2002\n[TEST] cycles\nTILT=" << tilt << "\n";
	/* Lamps, lumens, multiplier, vertical and horizontal counts, type C,
	 * units, width, length, height. */
	ss << "1 1000 1 " << v_num << " " << h_num << " 1 1 0 0 0\n";
	/* Ballast factor, ballast-lamp factor, input watts. */
	ss << "1 1 100\n";
	for(size_t i = 0; i < v_angles.size(); i++) {
		ss << v_angles[i] << " ";
	}
	ss << "\n";
	for(size_t i = 0; i < h_angles.size(); i++) {
		ss << h_angles[i] << " ";
	}
	ss << "\n";
	for(size_t i = 0; i < v_angles.size() * h_angles.size(); i++) {
		ss << "100 ";
	}
	ss << "\n";
	return ss.str();
}

static vector<double> angles(int num, double step)
{
	vector<double> result;
	for(int i = 0; i < num; i++) {
		result.push_back(i * step);
	}
	return result;
}

static string simple_ies(const string& tilt = "NONE")
{
	return ies_text(tilt, "3", "1", angles(3, 45.0), angles(1, 0.0));
}

static bool load_ies(IESFile& ies, const string& text)
{
	return ies.load(ustring(text));
}

TEST(util_ies, valid_type_c)
{
	IESFile ies;
	EXPECT_TRUE(load_ies(ies, simple_ies()));
	/* Header (2) + horizontal angles (1 + mirrored 360) + vertical angles (3)
	 * + intensities (2 * 3). */
	EXPECT_EQ(ies.packed_size(), 13);
}

TEST(util_ies, valid_type_c_without_trailing_newline)
{
	IESFile ies;
	string text = simple_ies();
	ASSERT_EQ(text[text.size() - 1], '\n');
	text.resize(text.size() - 1);
	EXPECT_TRUE(load_ies(ies, text));
	EXPECT_EQ(ies.packed_size(), 13);
}

TEST(util_ies, zero_vertical_angles)
{
	IESFile ies;
	EXPECT_FALSE(load_ies(ies, ies_text("NONE", "0", "1", vector<double>(), angles(1, 0.0))));
	EXPECT_EQ(ies.packed_size(), 0);
}

TEST(util_ies, negative_horizontal_angles)
{
	IESFile ies;
	EXPECT_FALSE(load_ies(ies, ies_text("NONE", "3", "-1", angles(3, 45.0), vector<double>())));
	EXPECT_EQ(ies.packed_size(), 0);
}

TEST(util_ies, too_many_vertical_angles)
{
	/* Rejected from the count alone, before any angle is read. */
	IESFile ies;
	EXPECT_FALSE(load_ies(ies, ies_text("NONE", "4097", "1", vector<double>(), vector<double>())));
	EXPECT_EQ(ies.packed_size(), 0);
}

TEST(util_ies, too_many_horizontal_angles)
{
	IESFile ies;
	EXPECT_FALSE(load_ies(ies, ies_text("NONE", "1", "4097", vector<double>(), vector<double>())));
	EXPECT_EQ(ies.packed_size(), 0);
}

TEST(util_ies, too_many_intensity_values)
{
	/* Both axes are within range, but the grid exceeds 1024 * 1024 values. */
	IESFile ies;
	EXPECT_FALSE(load_ies(ies, ies_text("NONE", "4096", "257", vector<double>(), vector<double>())));
	EXPECT_EQ(ies.packed_size(), 0);
}

TEST(util_ies, overflowing_count)
{
	IESFile ies;
	EXPECT_FALSE(load_ies(ies, ies_text("NONE", "99999999999999999999", "1", vector<double>(), vector<double>())));
	EXPECT_FALSE(load_ies(ies, ies_text("NONE", "-99999999999999999999", "1", vector<double>(), vector<double>())));
	EXPECT_EQ(ies.packed_size(), 0);
}

TEST(util_ies, max_intensity_grid_accepted)
{
	/* 4096 x 256 is exactly the intensity limit. The horizontal step makes the
	 * parser append the 360 degree entry, giving 257 horizontal angles. */
	IESFile ies;
	const string text = ies_text("NONE", "4096", "256", angles(4096, 90.0 / 4095), angles(256, 360.0 / 256));
	EXPECT_TRUE(load_ies(ies, text));
	EXPECT_EQ(ies.packed_size(), 2 + 257 + 4096 + 257 * 4096);
}

TEST(util_ies, tilt_include_valid)
{
	IESFile ies;
	EXPECT_TRUE(load_ies(ies, simple_ies("INCLUDE\n1\n2\n0 90\n1 1")));
	EXPECT_EQ(ies.packed_size(), 13);
}

TEST(util_ies, tilt_include_negative_count)
{
	IESFile ies;
	EXPECT_FALSE(load_ies(ies, simple_ies("INCLUDE\n1\n-1")));
	EXPECT_EQ(ies.packed_size(), 0);
}

TEST(util_ies, tilt_include_too_many)
{
	IESFile ies;
	EXPECT_FALSE(load_ies(ies, simple_ies("INCLUDE\n1\n4097")));
	EXPECT_EQ(ies.packed_size(), 0);
}

TEST(util_ies, failed_load_clears_previous)
{
	IESFile ies;
	ASSERT_TRUE(load_ies(ies, simple_ies()));
	EXPECT_FALSE(load_ies(ies, ies_text("NONE", "4097", "1", vector<double>(), vector<double>())));
	EXPECT_EQ(ies.packed_size(), 0);
}

CCL_NAMESPACE_END
