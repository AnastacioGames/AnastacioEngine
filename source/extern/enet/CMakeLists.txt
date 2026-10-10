# ENet fork with real IPv6 support (https://github.com/zpl-c/enet), MIT license, see LICENSE.
# Single-header library: enet_impl.c is the one translation unit that defines
# ENET_IMPLEMENTATION and pulls in include/enet/enet.h's implementation.
# Library target: extern_enet. Plain CMake so it also builds in the standalone network build.

set(ENET_DEFS)
if(WIN32)
	list(APPEND ENET_DEFS _WINSOCK_DEPRECATED_NO_WARNINGS _CRT_SECURE_NO_WARNINGS)
endif()

# The fork defaults to dual-stack (IPv6 socket, IPv4-mapped): ENetAddress.host becomes a
# 16-byte in6_addr. The engine doesn't expose IPv6 in the net.host/net.join API yet (see
# NOTES-engine.md, "IPv6 no ENet/UDP"), and some build/test environments have no IPv6 stack
# at all (AF_INET6 unavailable), so default to IPv4-only for now -- same ENetAddress layout
# and behavior as the previous vendor. Flip this once the API/test work for IPv6 is done.
option(ENET_IPV4_ONLY "Build ENet in IPv4-only mode (no dual-stack IPv6)" ON)
if(ENET_IPV4_ONLY)
	list(APPEND ENET_DEFS ENET_IPV4_ONLY)
else()
	# Dual-stack: use the fork's IPv6-aware address functions (set_host/get_host resolve and
	# format AF_INET6 too). Without this the macros fall back to the AF_INET-only *_old
	# variants, so an IPv6 literal like "::1" never resolves on the dual-stack socket.
	list(APPEND ENET_DEFS ENET_FEATURE_ADDRESS_MAPPING)
endif()

set(SRC
	enet_impl.c

	include/enet/enet.h
)

add_library(extern_enet STATIC ${SRC})
set_target_properties(extern_enet PROPERTIES LINKER_LANGUAGE C)
target_include_directories(extern_enet SYSTEM PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_compile_definitions(extern_enet PUBLIC ${ENET_DEFS})
if(WIN32)
	target_link_libraries(extern_enet PUBLIC ws2_32 winmm)
endif()
