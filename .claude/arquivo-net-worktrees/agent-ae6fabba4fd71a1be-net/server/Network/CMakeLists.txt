# PROVISIONAL (Frente C): minimal build so net/server compiles and tests alone.
# The authoritative file comes from Frente A (net/core); on merge, keep A's file and add the
# Frente C sources and tests listed below.

cmake_minimum_required(VERSION 3.10)
project(ge_network CXX)

option(NET_STANDALONE "Build ge_network alone with its tests" OFF)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_library(ge_network STATIC
	NET_ITransport.h
	NET_TransportWebSocket.h
	NET_TransportWebSocketServer.cpp
	NET_TransportMulti.cpp
	NET_TransportWebClient.cpp
)
target_include_directories(ge_network PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
if(WIN32)
	target_link_libraries(ge_network PUBLIC ws2_32)
endif()

if(NET_STANDALONE)
	if(MSVC)
		string(REGEX REPLACE "/W[0-4]" "" CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS}")
		target_compile_options(ge_network PRIVATE /W4)
	else()
		target_compile_options(ge_network PRIVATE -Wall -Wextra)
	endif()

	# gtest built straight from source/extern/gtest (its own CMakeLists needs Blender macros).
	set(NET_GTEST_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../../../extern/gtest)
	find_package(Threads REQUIRED)
	add_library(net_gtest STATIC ${NET_GTEST_DIR}/src/gtest-all.cc ${NET_GTEST_DIR}/src/gtest_main.cc)
	target_include_directories(net_gtest SYSTEM PUBLIC ${NET_GTEST_DIR}/include PRIVATE ${NET_GTEST_DIR})
	target_link_libraries(net_gtest PUBLIC Threads::Threads)
	# Old bundled gtest: MSVC needs these to skip std::tr1.
	target_compile_definitions(net_gtest PUBLIC GTEST_LANG_CXX11=1 GTEST_HAS_TR1_TUPLE=0)

	enable_testing()
	add_executable(net_tests
		tests/net_websocket_test.cc
		tests/net_multi_test.cc
	)
	target_link_libraries(net_tests PRIVATE ge_network net_gtest)
	if(MSVC)
		target_compile_options(net_tests PRIVATE /W4)
	else()
		target_compile_options(net_tests PRIVATE -Wall -Wextra)
	endif()
	add_test(NAME net_tests COMMAND net_tests)
endif()
