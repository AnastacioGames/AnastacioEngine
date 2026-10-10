# SPDX-License-Identifier: GPL-2.0-or-later
#
# Network core (ge_network). Engine-independent: standard library only.
# Standalone build (library + tests):
#   cmake -S source/source/gameengine/Network -B build-net -DNET_STANDALONE=ON

cmake_minimum_required(VERSION 3.10)

if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
	project(ge_network CXX)
	option(NET_STANDALONE "Build ge_network standalone with gtest unit tests" OFF)
endif()

set(NET_SRC
	NET_BitStream.cpp
	NET_Messages.cpp
	NET_Snapshot.cpp

	NET_Types.h
	NET_BitStream.h
	NET_Messages.h
	NET_Snapshot.h
	NET_SnapshotBuffer.h
)

add_library(ge_network STATIC ${NET_SRC})
target_include_directories(ge_network PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
set_target_properties(ge_network PROPERTIES CXX_STANDARD 17 CXX_STANDARD_REQUIRED ON CXX_EXTENSIONS OFF)

if(MSVC)
	set(NET_WARN_FLAGS /W4)
else()
	set(NET_WARN_FLAGS -Wall -Wextra)
endif()
target_compile_options(ge_network PRIVATE ${NET_WARN_FLAGS})

if(NET_STANDALONE)
	enable_testing()

	# source/extern/gtest/CMakeLists.txt depends on Blender's build macros (blender_add_lib), so the
	# standalone build compiles the same gtest sources directly (see NOTES-A.md).
	get_filename_component(NET_GTEST_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../../extern/gtest" ABSOLUTE)
	add_library(net_gtest STATIC
		${NET_GTEST_DIR}/src/gtest-all.cc
		${NET_GTEST_DIR}/src/gtest_main.cc
	)
	target_include_directories(net_gtest SYSTEM PUBLIC ${NET_GTEST_DIR}/include)
	target_include_directories(net_gtest PRIVATE ${NET_GTEST_DIR})
	target_compile_definitions(net_gtest PUBLIC GTEST_HAS_TR1_TUPLE=0 GTEST_LANG_CXX11=1)
	if(MSVC)
		target_compile_definitions(net_gtest PUBLIC _SILENCE_TR1_NAMESPACE_DEPRECATION_WARNING _CRT_SECURE_NO_WARNINGS)
	endif()
	set_target_properties(net_gtest PROPERTIES CXX_STANDARD 17 CXX_STANDARD_REQUIRED ON)
	find_package(Threads)
	if(Threads_FOUND)
		target_link_libraries(net_gtest PUBLIC Threads::Threads)
	endif()

	add_executable(net_tests
		tests/test_bitstream.cpp
		tests/test_messages.cpp
		tests/test_snapshot.cpp
		tests/test_golden.cpp
		tests/test_fuzz.cpp
		tests/net_test_util.h
	)
	set_target_properties(net_tests PROPERTIES CXX_STANDARD 17 CXX_STANDARD_REQUIRED ON CXX_EXTENSIONS OFF)
	target_compile_options(net_tests PRIVATE ${NET_WARN_FLAGS})
	target_compile_definitions(net_tests PRIVATE NET_GOLDEN_DIR="${CMAKE_CURRENT_SOURCE_DIR}/tests/golden")
	target_link_libraries(net_tests PRIVATE ge_network net_gtest)
	add_test(NAME net_tests COMMAND net_tests)
endif()
