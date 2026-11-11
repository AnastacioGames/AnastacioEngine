# meshoptimizer helpers for editor tools (Build HLOD "Sloppy" proxies).
# Shared library loaded from Python with ctypes; the tool reports an error when it is missing.

add_library(ae_meshopt SHARED ae_meshopt.cc ../../extern/meshoptimizer/src/simplifier.cpp)
target_include_directories(ae_meshopt PRIVATE ../../extern/meshoptimizer/src)
set_target_properties(ae_meshopt PROPERTIES
	RUNTIME_OUTPUT_DIRECTORY ${EXECUTABLE_OUTPUT_PATH}
	LIBRARY_OUTPUT_DIRECTORY ${EXECUTABLE_OUTPUT_PATH})
install(TARGETS ae_meshopt RUNTIME DESTINATION "." LIBRARY DESTINATION ".")
