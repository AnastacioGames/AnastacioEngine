# PROVISIONAL (Frente B): minimal CMakeLists with the contract targets
# (ge_network, net_tests). On merge, prefer net/core's file and add the
# Frente B sources/tests listed below.

cmake_minimum_required(VERSION 3.10)

option(NET_STANDALONE "Build the network core alone, with tests" OFF)

if(NET_STANDALONE)
	project(ge_network CXX C)
	set(CMAKE_CXX_STANDARD 17)
	set(CMAKE_CXX_STANDARD_REQUIRED ON)
endif()

set(NET_EXTERN_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../../../extern)

if(NOT TARGET extern_enet)
	add_subdirectory(${NET_EXTERN_DIR}/enet ${CMAKE_CURRENT_BINARY_DIR}/extern_enet)
endif()

set(NET_SRC
	NET_ITransport.h
	NET_Session.cpp
	NET_Session.h
	NET_SessionCodec.cpp
	NET_SessionCodec.h
	NET_TransportENet.cpp
	NET_TransportENet.h
	NET_TransportLoopback.cpp
	NET_TransportLoopback.h
	NET_TransportSimulated.cpp
	NET_Types.h
)

add_library(ge_network STATIC ${NET_SRC})
target_include_directories(ge_network PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(ge_network PRIVATE extern_enet)
target_compile_features(ge_network PUBLIC cxx_std_17)

if(MSVC)
	set(NET_WARN_FLAGS /W4)
else()
	set(NET_WARN_FLAGS -Wall -Wextra)
endif()
target_compile_options(ge_network PRIVATE ${NET_WARN_FLAGS})

if(NET_STANDALONE)
	# extern/gtest uses Blender macros, so build its sources directly here.
	set(GTEST_DIR ${NET_EXTERN_DIR}/gtest)
	add_library(net_gtest STATIC ${GTEST_DIR}/src/gtest-all.cc)
	target_include_directories(net_gtest SYSTEM PUBLIC ${GTEST_DIR}/include)
	target_include_directories(net_gtest PRIVATE ${GTEST_DIR})
	find_package(Threads)
	if(Threads_FOUND)
		target_link_libraries(net_gtest PUBLIC Threads::Threads)
	endif()
	if(MSVC)
		target_compile_definitions(net_gtest PUBLIC _SILENCE_TR1_NAMESPACE_DEPRECATION_WARNING GTEST_HAS_TR1_TUPLE=0)
		target_compile_options(net_gtest PRIVATE /W0)
	else()
		target_compile_options(net_gtest PRIVATE -w)
	endif()

	enable_testing()
	add_executable(net_tests
		tests/net_test_main.cc
		tests/NET_transport_test.cc
		tests/NET_session_test.cc
		tests/NET_enet_test.cc
	)
	target_link_libraries(net_tests PRIVATE ge_network net_gtest)
	target_compile_options(net_tests PRIVATE ${NET_WARN_FLAGS})
	add_test(NAME net_tests COMMAND net_tests)

	add_executable(net_echo tools/net_echo.cpp)
	target_link_libraries(net_echo PRIVATE ge_network)
	target_compile_options(net_echo PRIVATE ${NET_WARN_FLAGS})
endif()
