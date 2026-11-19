"""Stubs gerados de text_autocomplete_api.json (tools/autocomplete/gerar_stubs.py). Nao edite."""
from typing import Any, Generic, Iterator, TypeVar

from mathutils import Vector

def area_tri(v1, v2, v3) -> float:
    """Returns the area size of the 2D or 3D triangle defined."""
def barycentric_transform(point, tri_a1, tri_a2, tri_a3, tri_b1, tri_b2, tri_b3) -> Vector:
    """Return a transformed point, the transformation is defined by 2 triangles."""
def box_fit_2d(points) -> float:
    """Returns an angle that best fits the points to an axis aligned rectangle"""
def box_pack_2d(boxes) -> tuple:
    """Returns the normal of the 3D tri or quad."""
def convex_hull_2d(points) -> list[Any]:
    """Returns a list of indices into the list given"""
def distance_point_to_plane(pt, plane_co, plane_no) -> float:
    """Returns the signed distance between a point and a plane    (negative when below the normal)."""
def interpolate_bezier(knot1, handle1, handle2, knot2, resolution) -> list[Vector]:
    """Interpolate a bezier spline segment."""
def intersect_line_line(v1, v2, v3, v4) -> list[Vector]:
    """Returns a tuple with the points on each line respectively closest to the other."""
def intersect_line_line_2d(lineA_p1, lineA_p2, lineB_p1, lineB_p2) -> Vector:
    """Takes 2 segments (defined by 4 vectors) and returns a vector for their point of intersection or None."""
def intersect_line_plane(line_a, line_b, plane_co, plane_no, no_flip=False) -> Vector:
    """Calculate the intersection between a line (as 2 vectors) and a plane. Returns a vector for the intersection or None."""
def intersect_line_sphere(line_a, line_b, sphere_co, sphere_radius, clip=True) -> Vector:
    """Takes a line (as 2 points) and a sphere (as a point and a radius) and returns the intersection"""
def intersect_line_sphere_2d(line_a, line_b, sphere_co, sphere_radius, clip=True) -> Vector:
    """Takes a line (as 2 points) and a sphere (as a point and a radius) and returns the intersection"""
def intersect_plane_plane(plane_a_co, plane_a_no, plane_b_co, plane_b_no) -> list[Vector]:
    """Return the intersection between two planes"""
def intersect_point_line(pt, line_p1, line_p2) -> Vector:
    """Takes a point and a line and returns a tuple with the closest point on the line and its distance from the first point of the line as a percentage of the length of the line."""
def intersect_point_quad_2d(pt, quad_p1, quad_p2, quad_p3, quad_p4) -> int:
    """Takes 5 vectors (using only the x and y coordinates): one is the point and the next 4 define the quad, only the x and y are used from the vectors. Returns 1 if the point is within the quad, otherwise 0. Works only with convex quads without singular edges."""
def intersect_point_tri(pt, tri_p1, tri_p2, tri_p3) -> Vector:
    """Takes 4 vectors: one is the point and the next 3 define the triangle."""
def intersect_point_tri_2d(pt, tri_p1, tri_p2, tri_p3) -> int:
    """Takes 4 vectors (using only the x and y coordinates): one is the point and the next 3 define the triangle. Returns 1 if the point is within the triangle, otherwise 0."""
def intersect_ray_tri(v1, v2, v3, ray, orig, clip=True) -> Vector:
    """Returns the intersection between a ray and a triangle, if possible, returns None otherwise."""
def intersect_sphere_sphere_2d(p_a, radius_a, p_b, radius_b) -> list[Vector]:
    """Returns 2 points on between intersecting circles."""
def normal(vectors) -> Vector:
    """Returns the normal of a 3D polygon."""
def points_in_planes(planes) -> Any:
    """Returns a list of points inside all planes given and a list of index values for the planes used."""
def tessellate_polygon(veclist_list) -> list[Any]:
    """Takes a list of polylines (each point a vector) and returns the point indices for a polyline filled with triangles."""
def volume_tetrahedron(v1, v2, v3, v4) -> float:
    """Return the volume formed by a tetrahedron (points can be in any order)."""
