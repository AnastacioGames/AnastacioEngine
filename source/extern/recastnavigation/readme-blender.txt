The version of Recast and Detour is 1.6.0, from:
https://github.com/recastnavigation/recastnavigation
Changes made:
  * Recast/Source/RecastMesh.cpp: made buildMeshAdjacency() non-static so it can be used with recast-capi
  * Recast/Include/Recast.h: Added forward declaration for buildMeshAdjacency()

The following additional files were added:
  * recast-capi.cpp
  * recast-capi.h
These expose a C interface to the Recast library, which has only C++ headers.

The CMakeLists.txt file has been added, since the original software does not include build files for the libraries.

2026-09: Upgraded from the old Detour "Stat"/"Tile" API (dtStatNavMesh,
dtStatNavMeshBuilder) to the current dtNavMesh/dtNavMeshQuery API. See
docs/roadmap.md and docs/changelog.md for the port of recast-capi, KX_NavMeshObject
and KX_SteeringActuator to the new API.

2026-09-28: Added DetourTileCache/ (DetourTileCache and DetourTileCacheBuilder, unchanged)
from upstream commit 9f4ce64458dfae86e1239c525ddc219c4e9e06f1, for the dynamic navmesh
(obstacles). DetourTileCache/Include/DetourTileCacheCompressorNone.h is a Range addition:
a passthrough compressor, so no fastlz dependency is needed.

~rdb
