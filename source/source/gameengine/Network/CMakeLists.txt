# ***** BEGIN GPL LICENSE BLOCK *****
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ***** END GPL LICENSE BLOCK *****

# Network core (protocol contract: docs/multiplayer-protocol.md).
# Standalone build: cmake -S source/source/gameengine/Network -B build-net -DNET_STANDALONE=ON

cmake_minimum_required(VERSION 3.10)

if(NET_STANDALONE)
	project(anastacio_network C CXX)
endif()

set(NET_EXTERN_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../../../extern)

# ENet: built here because the engine's extern list is not touched by the network core.
if(NOT TARGET extern_enet)
	add_subdirectory(${NET_EXTERN_DIR}/enet ${CMAKE_CURRENT_BINARY_DIR}/extern_enet)
endif()

set(NET_SRC
	NET_BitStream.cpp
	NET_Clock.cpp
	NET_LagCompensation.cpp
	NET_LanDiscovery.cpp
	NET_Messages.cpp
	NET_Prediction.cpp
	NET_RPC.cpp
	NET_ReplicaClient.cpp
	NET_Replicator.cpp
	NET_Session.cpp
	NET_Snapshot.cpp
	NET_TransportENet.cpp
	NET_TransportLoopback.cpp
	NET_TransportMulti.cpp
	NET_TransportSimulated.cpp
	NET_TransportWebClient.cpp
	NET_TransportWebSocketServer.cpp

	NET_BitStream.h
	NET_Clock.h
	NET_ITransport.h
	NET_IWorld.h
	NET_LagCompensation.h
	NET_LanDiscovery.h
	NET_Messages.h
	NET_Prediction.h
	NET_RPC.h
	NET_ReplicaClient.h
	NET_Replicator.h
	NET_Session.h
	NET_Snapshot.h
	NET_Socket.h
	NET_TransportWeb.h
	NET_Types.h
)

add_library(ge_network STATIC ${NET_SRC})
target_include_directories(ge_network PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(ge_network PUBLIC extern_enet)
if(WIN32)
	target_link_libraries(ge_network PUBLIC ws2_32)  # WebSocket server sockets
endif()
set_target_properties(ge_network PROPERTIES CXX_STANDARD 17 CXX_STANDARD_REQUIRED ON)
if(EMSCRIPTEN)
	target_link_options(ge_network INTERFACE "-lwebsocket.js")  # NET_TransportWebClient
endif()

if(NET_STANDALONE)
	if(MSVC)
		target_compile_options(ge_network PRIVATE /W4)
	else()
		target_compile_options(ge_network PRIVATE -Wall -Wextra)
	endif()

	enable_testing()

	# The engine's gtest CMakeLists relies on Blender macros: provide minimal ones.
	find_package(Threads REQUIRED)
	macro(remove_cc_flag)
	endmacro()
	function(blender_add_lib name sources includes includes_sys libs)
		add_library(${name} STATIC ${sources})
		target_include_directories(${name} SYSTEM PUBLIC ${includes})
		target_link_libraries(${name} PUBLIC Threads::Threads)
		set_target_properties(${name} PROPERTIES CXX_STANDARD 17)
		if(MSVC)
			target_compile_definitions(${name} PUBLIC
				_SILENCE_TR1_NAMESPACE_DEPRECATION_WARNING
				GTEST_HAS_TR1_TUPLE=0
			)
		else()
			target_compile_options(${name} PRIVATE -w)
		endif()
	endfunction()

	add_subdirectory(${NET_EXTERN_DIR}/gtest ${CMAKE_CURRENT_BINARY_DIR}/extern_gtest)

	set(NET_TEST_SRC
		tests/net_test_main.cpp
		tests/net_test_samples.h
		tests/net_test_util.h
		tests/NET_BitStream_test.cpp
		tests/NET_Golden_test.cpp
		tests/NET_LanDiscovery_test.cpp
		tests/NET_Messages_test.cpp
		tests/NET_Prediction_test.cpp
		tests/NET_RPC_test.cpp
		tests/NET_Replication_test.cpp
		tests/NET_Session_test.cpp
		tests/NET_Snapshot_test.cpp
		tests/NET_Transport_test.cpp
		tests/NET_WebSocket_test.cpp
	)

	add_executable(net_tests ${NET_TEST_SRC})
	target_link_libraries(net_tests PRIVATE ge_network extern_gtest)
	set_target_properties(net_tests PROPERTIES CXX_STANDARD 17 CXX_STANDARD_REQUIRED ON)
	target_compile_definitions(net_tests PRIVATE
		NET_GOLDEN_DIR="${CMAKE_CURRENT_SOURCE_DIR}/tests/golden"
	)
	if(MSVC)
		target_compile_options(net_tests PRIVATE /W4)
	else()
		target_compile_options(net_tests PRIVATE -Wall -Wextra)
	endif()

	if(EMSCRIPTEN)
		# wasm32 under node: core tests only (no sockets, no ENet); golden files read from the host.
		target_link_options(net_tests PRIVATE -sNODERAWFS=1 -sALLOW_MEMORY_GROWTH=1 -sEXIT_RUNTIME=1)
		set(NET_WASM_TEST_FILTER
			"NetTypes.*:NetBitStream.*:NetGolden.*:NetMessages.*:NetSnapshot.*:NetSnapshotBuffer.*:NetSession.*:NetTransportLoopback.*:NetTransportSimulated.*:NetWebSocket.AcceptKeyRfcVector-NetSession.OverENet"
		)
		add_test(NAME net_tests COMMAND net_tests "--gtest_filter=${NET_WASM_TEST_FILTER}")
	else()
		add_test(NAME net_tests COMMAND net_tests)
	endif()

	# Manual test tool.
	add_executable(net_echo tools/net_echo.cpp)
	target_link_libraries(net_echo PRIVATE ge_network)
	set_target_properties(net_echo PROPERTIES CXX_STANDARD 17 CXX_STANDARD_REQUIRED ON)
	if(MSVC)
		target_compile_options(net_echo PRIVATE /W4)
	else()
		target_compile_options(net_echo PRIVATE -Wall -Wextra)
	endif()

	# Replication benchmark (plan, section 4 targets).
	add_executable(net_bench tools/net_bench.cpp)
	target_link_libraries(net_bench PRIVATE ge_network)
	set_target_properties(net_bench PROPERTIES CXX_STANDARD 17 CXX_STANDARD_REQUIRED ON)
	if(MSVC)
		target_compile_options(net_bench PRIVATE /W4)
	else()
		target_compile_options(net_bench PRIVATE -Wall -Wextra)
	endif()

	# Browser/node client for net_echo over WebSocket (Emscripten only).
	if(EMSCRIPTEN)
		add_executable(net_web_echo tools/net_web_echo.cpp)
		target_link_libraries(net_web_echo PRIVATE ge_network)
		set_target_properties(net_web_echo PROPERTIES CXX_STANDARD 17 CXX_STANDARD_REQUIRED ON)
		target_compile_options(net_web_echo PRIVATE -Wall -Wextra)
		target_link_options(net_web_echo PRIVATE -sEXIT_RUNTIME=1 -sALLOW_MEMORY_GROWTH=1)
	endif()
endif()
