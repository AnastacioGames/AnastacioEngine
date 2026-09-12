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

~rdb
