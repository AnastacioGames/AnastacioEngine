/* Test runner: gtest plus the --update-golden flag. */

#include "net_test_util.h"

#include "gtest/gtest.h"

#include <cstdlib>
#include <cstring>

namespace net_test {

static bool g_updateGolden = false;

bool updateGolden()
{
	return g_updateGolden;
}

void setUpdateGolden(bool update)
{
	g_updateGolden = update;
}

}  // namespace net_test

int main(int argc, char **argv)
{
	testing::InitGoogleTest(&argc, argv);
	const char *env = std::getenv("NET_UPDATE_GOLDEN");
	net_test::setUpdateGolden(env && std::strcmp(env, "1") == 0);
	for (int i = 1; i < argc; ++i) {
		if (std::strcmp(argv[i], "--update-golden") == 0) {
			net_test::setUpdateGolden(true);
		}
	}
	return RUN_ALL_TESTS();
}
