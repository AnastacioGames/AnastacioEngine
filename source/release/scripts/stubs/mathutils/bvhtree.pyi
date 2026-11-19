"""Stubs gerados de text_autocomplete_api.json (tools/autocomplete/gerar_stubs.py). Nao edite."""
from typing import Any, Generic, Iterator, TypeVar


class BVHTree:
    def FromBMesh(self, bmesh, epsilon=0.0) -> Any:
        """BVH tree based on :class:`BMesh` data."""
    def FromObject(self, object, scene, deform=True, render=False, cage=False, epsilon=0.0) -> Any:
        """BVH tree based on :class:`Object` data."""
    def FromPolygons(self, vertices, polygons, all_triangles=False, epsilon=0.0) -> Any:
        """BVH tree constructed geometry passed in as arguments."""
    def find_nearest(self, origin, distance=1.84467e+19) -> tuple:
        """Find the nearest element (typically face index) to a point."""
    def find_nearest_range(self, origin, distance=1.84467e+19) -> Any:
        """Find the nearest elements (typically face index) to a point in the distance range."""
    def overlap(self, other_tree) -> Any:
        """Find overlapping indices between 2 trees."""
    def ray_cast(self, origin, direction, distance=...) -> tuple:
        """Cast a ray onto the mesh."""

