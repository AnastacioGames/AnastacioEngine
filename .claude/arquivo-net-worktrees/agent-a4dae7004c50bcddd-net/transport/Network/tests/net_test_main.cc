/* PROVISIONAL (Frente B): test entry point; on merge keep net/core's if it has one. */

#include "gtest/gtest.h"

int main(int argc, char **argv)
{
	testing::InitGoogleTest(&argc, argv);
	return RUN_ALL_TESTS();
}
