# ENet (https://github.com/lsalzman/enet), MIT license, see LICENSE.
# Library target: extern_enet. Plain CMake so it also builds in the standalone network build.

include(CheckFunctionExists)
include(CheckStructHasMember)
include(CheckTypeSize)

set(ENET_DEFS)
if(WIN32)
	list(APPEND ENET_DEFS _WINSOCK_DEPRECATED_NO_WARNINGS _CRT_SECURE_NO_WARNINGS)
else()
	check_function_exists("fcntl" HAS_FCNTL)
	check_function_exists("poll" HAS_POLL)
	check_function_exists("getaddrinfo" HAS_GETADDRINFO)
	check_function_exists("getnameinfo" HAS_GETNAMEINFO)
	check_function_exists("gethostbyname_r" HAS_GETHOSTBYNAME_R)
	check_function_exists("gethostbyaddr_r" HAS_GETHOSTBYADDR_R)
	check_function_exists("inet_pton" HAS_INET_PTON)
	check_function_exists("inet_ntop" HAS_INET_NTOP)
	check_struct_has_member("struct msghdr" "msg_flags" "sys/types.h;sys/socket.h" HAS_MSGHDR_FLAGS)
	set(CMAKE_EXTRA_INCLUDE_FILES "sys/types.h" "sys/socket.h")
	check_type_size("socklen_t" HAS_SOCKLEN_T BUILTIN_TYPES_ONLY)
	unset(CMAKE_EXTRA_INCLUDE_FILES)
	foreach(_def
		HAS_FCNTL HAS_POLL HAS_GETADDRINFO HAS_GETNAMEINFO HAS_GETHOSTBYNAME_R
		HAS_GETHOSTBYADDR_R HAS_INET_PTON HAS_INET_NTOP HAS_MSGHDR_FLAGS HAS_SOCKLEN_T)
		if(${_def})
			list(APPEND ENET_DEFS ${_def}=1)
		endif()
	endforeach()
endif()

set(SRC
	callbacks.c
	compress.c
	host.c
	list.c
	packet.c
	peer.c
	protocol.c
	unix.c
	win32.c

	include/enet/callbacks.h
	include/enet/enet.h
	include/enet/list.h
	include/enet/protocol.h
	include/enet/time.h
	include/enet/types.h
	include/enet/unix.h
	include/enet/utility.h
	include/enet/win32.h
)

add_library(extern_enet STATIC ${SRC})
set_target_properties(extern_enet PROPERTIES LINKER_LANGUAGE C)
target_include_directories(extern_enet SYSTEM PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_compile_definitions(extern_enet PRIVATE ${ENET_DEFS})
if(WIN32)
	target_link_libraries(extern_enet PUBLIC ws2_32 winmm)
endif()
