/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "NET_AnastacioPlugin.h"
#include "gtest/gtest.h"
#include <filesystem>
TEST(AnastacioPlugin, AbsentAndRelativeLibraries)
{
    net::AnastacioPlugin plugin;
    EXPECT_FALSE(plugin.initialize(480));
    EXPECT_FALSE(plugin.load("missing.dll"));
    EXPECT_FALSE(plugin.load(std::filesystem::absolute("missing-anastacio.dll").u8string()));
    EXPECT_FALSE(plugin.ready());
    EXPECT_EQ(plugin.identity(), 0u);
    plugin.pump(); plugin.unload(); plugin.unload();
}
TEST(AnastacioPlugin, RejectsIncompatibleTables)
{
    net::AnastacioPlugin plugin;
    EXPECT_FALSE(plugin.load(ANASTACIO_FIXTURE_BAD_VERSION));
    EXPECT_FALSE(plugin.load(ANASTACIO_FIXTURE_BAD_SIZE));
    EXPECT_FALSE(plugin.load(ANASTACIO_FIXTURE_BAD_FUNCTION));
    EXPECT_FALSE(plugin.ready());
}
TEST(AnastacioPlugin, LifecycleAndReload)
{
    net::AnastacioPlugin plugin;
    for (int i = 0; i < 3; ++i) {
        ASSERT_TRUE(plugin.load(ANASTACIO_FIXTURE_GOOD));
        EXPECT_FALSE(plugin.ready());
        plugin.pump(); // Must not call the fixture before initialization.
        EXPECT_FALSE(plugin.initialize(0));
        EXPECT_EQ(plugin.error(), "AppID required");
        ASSERT_TRUE(plugin.initialize(480));
        EXPECT_TRUE(plugin.ready());
        EXPECT_FALSE(plugin.initialize(480));
        EXPECT_EQ(plugin.identity(), 76561198000000000ULL);
        plugin.pump();
        EXPECT_EQ(plugin.identity(), 76561198000000001ULL);
        plugin.unload();
        EXPECT_FALSE(plugin.ready());
    }
    ASSERT_TRUE(plugin.load(ANASTACIO_FIXTURE_GOOD));
    ASSERT_TRUE(plugin.initialize(480));
    ASSERT_TRUE(plugin.load(ANASTACIO_FIXTURE_GOOD)); // Reload closes the live context.
    EXPECT_FALSE(plugin.ready());
    ASSERT_TRUE(plugin.load(ANASTACIO_FIXTURE_GOOD));
    ASSERT_TRUE(plugin.initialize(480)); // Destructor owns final shutdown/unload.
}
