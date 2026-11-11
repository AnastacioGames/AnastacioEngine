# meshoptimizer (MIT): vertex cache / overdraw ordering of the game engine draw indices.
# See README.txt and docs/plano-opensource.md.

set(INC
	src
)

set(INC_SYS
)

set(SRC
	src/allocator.cpp
	src/clusterizer.cpp
	src/indexcodec.cpp
	src/indexgenerator.cpp
	src/overdrawanalyzer.cpp
	src/overdrawoptimizer.cpp
	src/quantization.cpp
	src/simplifier.cpp
	src/spatialorder.cpp
	src/stripifier.cpp
	src/vcacheanalyzer.cpp
	src/vcacheoptimizer.cpp
	src/vertexcodec.cpp
	src/vertexfilter.cpp
	src/vfetchanalyzer.cpp
	src/vfetchoptimizer.cpp

	src/meshoptimizer.h
)

set(LIB
)

blender_add_lib(extern_meshoptimizer "${SRC}" "${INC}" "${INC_SYS}" "${LIB}")
