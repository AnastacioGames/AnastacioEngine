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

#include "testing/testing.h"

#include "util/util_path.h"

CCL_NAMESPACE_BEGIN

/* ******** Tests for path_filename() ******** */

#ifndef _WIN32
TEST(util_path_filename, simple_unix)
{
	string str = path_filename("/tmp/foo.txt");
	EXPECT_EQ(str, "foo.txt");
}

TEST(util_path_filename, root_unix)
{
	string str = path_filename("/");
	EXPECT_EQ(str, "/");
}

TEST(util_path_filename, last_slash_unix)
{
	string str = path_filename("/tmp/foo.txt/");
	EXPECT_EQ(str, ".");
}

TEST(util_path_filename, alternate_slash_unix)
{
	string str = path_filename("/tmp\\foo.txt");
	EXPECT_EQ(str, "tmp\\foo.txt");
}
#endif  /* !_WIN32 */

TEST(util_path_filename, file_only)
{
	string str = path_filename("foo.txt");
	EXPECT_EQ(str, "foo.txt");
}

TEST(util_path_filename, empty)
{
	string str = path_filename("");
	EXPECT_EQ(str, "");
}

#ifdef _WIN32
TEST(util_path_filename, simple_windows)
{
	string str = path_filename("C:\\tmp\\foo.txt");
	EXPECT_EQ(str, "foo.txt");
}

TEST(util_path_filename, root_windows)
{
	string str = path_filename("C:\\");
	EXPECT_EQ(str, "\\");
}

TEST(util_path_filename, last_slash_windows)
{
	string str = path_filename("C:\\tmp\\foo.txt\\");
	EXPECT_EQ(str, ".");
}

TEST(util_path_filename, alternate_slash_windows)
{
	string str = path_filename("C:\\tmp/foo.txt");
	EXPECT_EQ(str, "foo.txt");
}
#endif  /* _WIN32 */

/* ******** Tests for path_dirname() ******** */

#ifndef _WIN32
TEST(util_path_dirname, simple_unix)
{
	string str = path_dirname("/tmp/foo.txt");
	EXPECT_EQ(str, "/tmp");
}

TEST(util_path_dirname, root_unix)
{
	string str = path_dirname("/");
	EXPECT_EQ(str, "");
}

TEST(util_path_dirname, last_slash_unix)
{
	string str = path_dirname("/tmp/foo.txt/");
	EXPECT_EQ(str, "/tmp/foo.txt");
}

TEST(util_path_dirname, alternate_slash_unix)
{
	string str = path_dirname("/tmp\\foo.txt");
	EXPECT_EQ(str, "/");
}
#endif  /* !_WIN32 */

TEST(util_path_dirname, file_only)
{
	string str = path_dirname("foo.txt");
	EXPECT_EQ(str, "");
}

TEST(util_path_dirname, empty)
{
	string str = path_dirname("");
	EXPECT_EQ(str, "");
}

#ifdef _WIN32
TEST(util_path_dirname, simple_windows)
{
	string str = path_dirname("C:\\tmp\\foo.txt");
	EXPECT_EQ(str, "C:\\tmp");
}

TEST(util_path_dirname, root_windows)
{
	string str = path_dirname("C:\\");
	EXPECT_EQ(str, "C:");
}

TEST(util_path_dirname, last_slash_windows)
{
	string str = path_dirname("C:\\tmp\\foo.txt\\");
	EXPECT_EQ(str, "C:\\tmp\\foo.txt");
}

TEST(util_path_dirname, alternate_slash_windows)
{
	string str = path_dirname("C:\\tmp/foo.txt");
	EXPECT_EQ(str, "C:\\tmp");
}
#endif  /* _WIN32 */

/* ******** Tests for path_join() ******** */

TEST(util_path_join, empty_both)
{
	string str = path_join("", "");
	EXPECT_EQ(str, "");
}

TEST(util_path_join, empty_directory)
{
	string str = path_join("", "foo.txt");
	EXPECT_EQ(str, "foo.txt");
}

TEST(util_path_join, empty_filename)
{
	string str = path_join("foo", "");
	EXPECT_EQ(str, "foo");
}

#ifndef _WIN32
TEST(util_path_join, simple_unix)
{
	string str = path_join("foo", "bar");
	EXPECT_EQ(str, "foo/bar");
}

TEST(util_path_join, directory_slash_unix)
{
	string str = path_join("foo/", "bar");
	EXPECT_EQ(str, "foo/bar");
}

TEST(util_path_join, filename_slash_unix)
{
	string str = path_join("foo", "/bar");
	EXPECT_EQ(str, "foo/bar");
}

TEST(util_path_join, both_slash_unix)
{
	string str = path_join("foo/", "/bar");
	EXPECT_EQ(str, "foo//bar");
}

TEST(util_path_join, directory_alternate_slash_unix)
{
	string str = path_join("foo\\", "bar");
	EXPECT_EQ(str, "foo\\/bar");
}

TEST(util_path_join, filename_alternate_slash_unix)
{
	string str = path_join("foo", "\\bar");
	EXPECT_EQ(str, "foo/\\bar");
}

TEST(util_path_join, both_alternate_slash_unix)
{
	string str = path_join("foo", "\\bar");
	EXPECT_EQ(str, "foo/\\bar");
}

TEST(util_path_join, empty_dir_filename_slash_unix)
{
	string str = path_join("", "/foo.txt");
	EXPECT_EQ(str, "/foo.txt");
}

TEST(util_path_join, empty_dir_filename_alternate_slash_unix)
{
	string str = path_join("", "\\foo.txt");
	EXPECT_EQ(str, "\\foo.txt");
}

TEST(util_path_join, empty_filename_dir_slash_unix)
{
	string str = path_join("foo/", "");
	EXPECT_EQ(str, "foo/");
}

TEST(util_path_join, empty_filename_dir_alternate_slash_unix)
{
	string str = path_join("foo\\", "");
	EXPECT_EQ(str, "foo\\");
}
#else  /* !_WIN32 */
TEST(util_path_join, simple_windows)
{
	string str = path_join("foo", "bar");
	EXPECT_EQ(str, "foo\\bar");
}

TEST(util_path_join, directory_slash_windows)
{
	string str = path_join("foo\\", "bar");
	EXPECT_EQ(str, "foo\\bar");
}

TEST(util_path_join, filename_slash_windows)
{
	string str = path_join("foo", "\\bar");
	EXPECT_EQ(str, "foo\\bar");
}

TEST(util_path_join, both_slash_windows)
{
	string str = path_join("foo\\", "\\bar");
	EXPECT_EQ(str, "foo\\\\bar");
}

TEST(util_path_join, directory_alternate_slash_windows)
{
	string str = path_join("foo/", "bar");
	EXPECT_EQ(str, "foo/bar");
}

TEST(util_path_join, filename_alternate_slash_windows)
{
	string str = path_join("foo", "/bar");
	EXPECT_EQ(str, "foo/bar");
}

TEST(util_path_join, both_alternate_slash_windows)
{
	string str = path_join("foo/", "/bar");
	EXPECT_EQ(str, "foo//bar");
}

TEST(util_path_join, empty_dir_filename_slash_windows)
{
	string str = path_join("", "\\foo.txt");
	EXPECT_EQ(str, "\\foo.txt");
}

TEST(util_path_join, empty_dir_filename_alternate_slash_windows)
{
	string str = path_join("", "/foo.txt");
	EXPECT_EQ(str, "/foo.txt");
}

TEST(util_path_join, empty_filename_dir_slash_windows)
{
	string str = path_join("foo\\", "");
	EXPECT_EQ(str, "foo\\");
}

TEST(util_path_join, empty_filename_dir_alternate_slash_windows)
{
	string str = path_join("foo/", "");
	EXPECT_EQ(str, "foo/");
}
#endif  /* !_WIN32 */

/* ******** Tests for path_escape() ******** */

TEST(util_path_escape, no_escape_chars)
{
	string str = path_escape("/tmp/foo/bar");
	EXPECT_EQ(str, "/tmp/foo/bar");
}

TEST(util_path_escape, simple)
{
	string str = path_escape("/tmp/foo bar");
	EXPECT_EQ(str, "/tmp/foo\\ bar");
}

TEST(util_path_escape, simple_end)
{
	string str = path_escape("/tmp/foo/bar ");
	EXPECT_EQ(str, "/tmp/foo/bar\\ ");
}

TEST(util_path_escape, multiple)
{
	string str = path_escape("/tmp/foo  bar");
	EXPECT_EQ(str, "/tmp/foo\\ \\ bar");
}

TEST(util_path_escape, simple_multiple_end)
{
	string str = path_escape("/tmp/foo/bar  ");
	EXPECT_EQ(str, "/tmp/foo/bar\\ \\ ");
}

/* ******** Tests for path_is_relative() ******** */

TEST(util_path_is_relative, filename)
{
	bool is_relative = path_is_relative("foo.txt");
	EXPECT_TRUE(is_relative);
}

#ifndef _WIN32
TEST(util_path_is_relative, absolute_unix)
{
	bool is_relative = path_is_relative("/tmp/foo.txt");
	EXPECT_FALSE(is_relative);
}

TEST(util_path_is_relative, relative_dir_unix)
{
	bool is_relative = path_is_relative("tmp/foo.txt");
	EXPECT_TRUE(is_relative);
}

TEST(util_path_is_relative, absolute_windir_on_unix)
{
	bool is_relative = path_is_relative("C:\\tmp\\foo.txt");
	EXPECT_TRUE(is_relative);
}

TEST(util_path_is_relative, relative_windir_on_unix)
{
	bool is_relative = path_is_relative("tmp\\foo.txt");
	EXPECT_TRUE(is_relative);
}
#endif  /* !_WIN32 */

#ifdef _WIN32
TEST(util_path_is_relative, absolute_windows)
{
	bool is_relative = path_is_relative("C:\\tmp\\foo.txt");
	EXPECT_FALSE(is_relative);
}

TEST(util_path_is_relative, relative_dir_windows)
{
	bool is_relative = path_is_relative("tmp\\foo.txt");
	EXPECT_TRUE(is_relative);
}

TEST(util_path_is_relative, absolute_unixdir_on_windows)
{
	bool is_relative = path_is_relative("/tmp/foo.txt");
	EXPECT_TRUE(is_relative);
}

TEST(util_path_is_relative, relative_unixdir_on_windows)
{
	bool is_relative = path_is_relative("tmp/foo.txt");
	EXPECT_TRUE(is_relative);
}
#endif  /* _WIN32 */

/* ******** Tests for path_write_binary() and path_read_binary() ******** */

static string binary_test_dir()
{
	const char *dir = getenv("TEMP");
	if(dir == NULL) {
		dir = getenv("TMPDIR");
	}
	return path_join((dir != NULL)? dir: ".", "cycles_util_path_test");
}

TEST(util_path_binary, write_read_roundtrip)
{
	const string path = path_join(binary_test_dir(), "roundtrip.bin");
	vector<uint8_t> written;
	for(int i = 0; i < 1000; i++) {
		written.push_back((uint8_t)(i * 7));
	}

	EXPECT_TRUE(path_write_binary(path, written));

	vector<uint8_t> read;
	EXPECT_TRUE(path_read_binary(path, read));
	EXPECT_EQ(read, written);

	path_remove(path);
}

TEST(util_path_binary, write_to_directory_fails)
{
	/* The target can't be opened as a file, so the write must report failure. */
	const string dir = binary_test_dir();
	path_create_directories(path_join(dir, "dummy"));
	ASSERT_TRUE(path_is_directory(dir));

	vector<uint8_t> data(16, 42);
	EXPECT_FALSE(path_write_binary(dir, data));
}

TEST(util_path_binary, read_missing_clears_vector)
{
	const string path = path_join(binary_test_dir(), "does_not_exist.bin");
	path_remove(path);

	vector<uint8_t> data(16, 42);
	EXPECT_FALSE(path_read_binary(path, data));
	EXPECT_TRUE(data.empty());
}

TEST(util_path_binary, read_empty_clears_vector)
{
	const string path = path_join(binary_test_dir(), "empty.bin");
	EXPECT_TRUE(path_write_binary(path, vector<uint8_t>()));
	EXPECT_EQ(path_file_size(path), (size_t)0);

	vector<uint8_t> data(16, 42);
	EXPECT_FALSE(path_read_binary(path, data));
	EXPECT_TRUE(data.empty());

	path_remove(path);
}

TEST(util_path_binary, file_size_of_missing_is_sentinel)
{
	/* path_read_binary() relies on this sentinel to avoid resizing to SIZE_MAX. */
	const string path = path_join(binary_test_dir(), "does_not_exist.bin");
	path_remove(path);

	EXPECT_EQ(path_file_size(path), (size_t)-1);
}

CCL_NAMESPACE_END
