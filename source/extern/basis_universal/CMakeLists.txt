# SPDX-License-Identifier: GPL-2.0-or-later
# Basis Universal (Apache-2.0): KTX2 textures that transcode to BC, ETC2 or ASTC on the device.
# Desktop builds get the encoder (editor converts textures); the Web runtime only transcodes.

set(INC
	transcoder
	encoder
	zstd
)

set(INC_SYS
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

if(MSVC AND CMAKE_SIZEOF_VOID_P EQUAL 8)
	add_definitions(-DBASISU_SUPPORT_SSE=1)
	# third-party code: its own warning level, not ours
	add_compile_options(/W0 /bigobj)
else()
	add_definitions(-DBASISU_SUPPORT_SSE=0)
	add_compile_options(-w -fno-strict-aliasing)
endif()

if(EMSCRIPTEN)
	# transcoder only; XUASTC / UASTC HDR cannot be turned off at this revision (other decoders need them)
	set(SRC
		transcoder/basisu_transcoder.cpp
		zstd/zstddeclib.c
		transcoder/basisu_transcoder.h
	)
else()
	set(SRC
		encoder/basisu_backend.cpp
		encoder/basisu_basis_file.cpp
		encoder/basisu_comp.cpp
		encoder/basisu_enc.cpp
		encoder/basisu_etc.cpp
		encoder/basisu_frontend.cpp
		encoder/basisu_gpu_texture.cpp
		encoder/basisu_pvrtc1_4.cpp
		encoder/basisu_resampler.cpp
		encoder/basisu_resample_filters.cpp
		encoder/basisu_ssim.cpp
		encoder/basisu_uastc_enc.cpp
		encoder/basisu_bc7e_scalar.cpp
		encoder/basisu_dds_export.cpp
		encoder/basisu_bc7enc.cpp
		encoder/jpgd.cpp
		encoder/basisu_kernels_sse.cpp
		encoder/basisu_bc15_spmd.cpp
		encoder/basisu_bc15_spmd_sse.cpp
		encoder/basisu_opencl.cpp
		encoder/pvpngreader.cpp
		encoder/basisu_uastc_hdr_4x4_enc.cpp
		encoder/basisu_astc_hdr_6x6_enc.cpp
		encoder/basisu_astc_hdr_common.cpp
		encoder/basisu_astc_ldr_common.cpp
		encoder/basisu_astc_ldr_encode.cpp
		encoder/basisu_astc_ldr_fencode.cpp
		encoder/basisu_xbc7_encode.cpp
		encoder/basisu_tinyexr.cpp
		transcoder/basisu_transcoder.cpp
		zstd/zstd.c
		encoder/basisu_comp.h
		transcoder/basisu_transcoder.h
	)
endif()

set(LIB
)

blender_add_lib(extern_basisu "${SRC}" "${INC}" "${INC_SYS}" "${LIB}")
