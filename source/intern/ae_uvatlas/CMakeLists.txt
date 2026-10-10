# Lightmap UV atlas (xatlas) for the "Baked Lighting" bake operator.
# Shared library loaded from Python with ctypes; the operator falls back to the UV Lightmap Pack when it is missing.

add_library(ae_uvatlas SHARED ae_uvatlas.cc ../../extern/xatlas/xatlas.cpp)
target_include_directories(ae_uvatlas PRIVATE ../../extern/xatlas)
set_target_properties(ae_uvatlas PROPERTIES
	RUNTIME_OUTPUT_DIRECTORY ${EXECUTABLE_OUTPUT_PATH}
	LIBRARY_OUTPUT_DIRECTORY ${EXECUTABLE_OUTPUT_PATH})
install(TARGETS ae_uvatlas RUNTIME DESTINATION "." LIBRARY DESTINATION ".")
if(NOT WIN32)
	find_package(Threads REQUIRED)  # xatlas runs its chart work on std::thread
	target_link_libraries(ae_uvatlas Threads::Threads)
endif()
