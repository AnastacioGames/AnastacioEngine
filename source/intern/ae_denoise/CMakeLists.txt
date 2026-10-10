# Lightmap denoiser (Intel Open Image Denoise) for the "Baked Lighting" bake operator.
# Shared library loaded from Python with ctypes; the operator falls back to a box blur when it is missing.

if(WIN32)
	set(_oidn ${LIBDIR}/openimagedenoise)
	set(AE_OIDN_INCLUDE_DIRS ${_oidn}/include)
	set(AE_OIDN_LIBRARIES
		${_oidn}/lib/openimagedenoise.lib ${_oidn}/lib/common.lib ${_oidn}/lib/mkldnn.lib
		${LIBDIR}/tbb/lib/tbb.lib)
	unset(_oidn)
else()
	find_package(OpenImageDenoise)
	find_package(TBB)
	if(NOT OPENIMAGEDENOISE_FOUND OR NOT TBB_FOUND)
		message(STATUS "ae_denoise: OpenImageDenoise/TBB not found, lightmap bake uses the box blur")
		return()
	endif()
	set(AE_OIDN_INCLUDE_DIRS ${OPENIMAGEDENOISE_INCLUDE_DIRS})
	set(AE_OIDN_LIBRARIES ${OPENIMAGEDENOISE_LIBRARIES} ${TBB_LIBRARIES})
endif()

add_library(ae_denoise SHARED ae_denoise.cc)
target_include_directories(ae_denoise PRIVATE ${AE_OIDN_INCLUDE_DIRS})
target_compile_definitions(ae_denoise PRIVATE OIDN_STATIC_LIB)
target_link_libraries(ae_denoise ${AE_OIDN_LIBRARIES})
if(MSVC)
	# the prebuilt OIDN libs pull LIBCMT; the engine uses the DLL runtime
	set_target_properties(ae_denoise PROPERTIES LINK_FLAGS "/NODEFAULTLIB:LIBCMT")
endif()
set_target_properties(ae_denoise PROPERTIES
	RUNTIME_OUTPUT_DIRECTORY ${EXECUTABLE_OUTPUT_PATH}
	LIBRARY_OUTPUT_DIRECTORY ${EXECUTABLE_OUTPUT_PATH})
install(TARGETS ae_denoise RUNTIME DESTINATION "." LIBRARY DESTINATION ".")
