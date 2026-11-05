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
# The Original Code is Copyright (C) 2006, Blender Foundation
# All rights reserved.
#
# The Original Code is: all of this file.
#
# Contributor(s):
#
# ***** END GPL LICENSE BLOCK *****

set(INC
	.
	..
	../..
	../../../blenkernel
	../../../blenlib
	../../../makesdna
	../../../../../intern/guardedalloc
	../../../../../intern/utfconv
)

set(INC_SYS

)

set(SRC
	BlockDXT.h
	Color.h
	ColorBlock.h
	Common.h
	DirectDrawSurface.h
	FlipDXT.h
	Image.h
	PixelFormat.h
	Stream.h
	dds_api.h

	BlockDXT.cpp
	ColorBlock.cpp
	DirectDrawSurface.cpp
	FlipDXT.cpp
	Image.cpp
	Stream.cpp
	dds_api.cpp
	dds_write.cpp
	ktx2_api.cpp
)

set(LIB
	extern_basisu
)

# must match extern/basis_universal/CMakeLists.txt: the transcoder headers change with them
list(APPEND INC_SYS
	../../../../../extern/basis_universal/transcoder
	../../../../../extern/basis_universal/encoder
)
add_definitions(
	-DBASISD_SUPPORT_KTX2=1
	-DBASISD_SUPPORT_KTX2_ZSTD=1
	-DBASISU_SUPPORT_OPENCL=0
	-DBASISU_USE_WUFFS_LDR_LOADER=0
	-DBASISU_DISABLE_ANDROID_ASTC_DECOMP=1
	-DBASISD_SUPPORT_PVRTC1=0
	-DBASISD_SUPPORT_PVRTC2=0
	-DBASISD_SUPPORT_ATC=0
	-DBASISD_SUPPORT_FXT1=0
)
if(NOT EMSCRIPTEN)
	add_definitions(-DWITH_KTX2_ENCODER)
	if(MSVC AND CMAKE_SIZEOF_VOID_P EQUAL 8)
		add_definitions(-DBASISU_SUPPORT_SSE=1)
	else()
		add_definitions(-DBASISU_SUPPORT_SSE=0)
	endif()
endif()

if(WITH_IMAGE_DDS)
	add_definitions(-DWITH_DDS)
endif()

blender_add_lib(bf_imbuf_dds "${SRC}" "${INC}" "${INC_SYS}" "${LIB}")
