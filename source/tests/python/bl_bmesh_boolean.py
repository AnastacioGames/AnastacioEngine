# Apache License, Version 2.0

# AnastacioEngine: replaces upstream bool_regression.blend (only available as a
# newer, unreadable .blend). Builds its own scene, no test data needed.
#
# ./AnastacioEngine --background -noaudio --factory-startup --python tests/python/bl_bmesh_boolean.py

import bpy
import bmesh
import unittest
from mathutils import Vector


def clear_scene():
    scene = bpy.context.scene
    for ob in list(scene.objects):
        scene.objects.unlink(ob)
        bpy.data.objects.remove(ob)


def mesh_object(name, bm):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.objects.link(ob)
    return ob


def make_cube(name, size=1.0, offset=(0.0, 0.0, 0.0)):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=size)
    bmesh.ops.translate(bm, verts=bm.verts, vec=offset)
    return mesh_object(name, bm)


def make_sphere(name, diameter=1.0, offset=(0.0, 0.0, 0.0)):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, diameter=diameter)
    bmesh.ops.translate(bm, verts=bm.verts, vec=offset)
    return mesh_object(name, bm)


def apply_boolean(ob, cutter, operation, solver):
    mod = ob.modifiers.new("Boolean", 'BOOLEAN')
    mod.object = cutter
    mod.operation = operation
    if hasattr(mod, "solver"):
        mod.solver = solver
    # The modifier reads the cutter's evaluated mesh, which needs a scene update.
    bpy.context.scene.update()
    me = ob.to_mesh(bpy.context.scene, True, 'PREVIEW')
    bm = bmesh.new()
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)
    return bm


def bounds(bm):
    lo = Vector((min(v.co[i] for v in bm.verts) for i in range(3)))
    hi = Vector((max(v.co[i] for v in bm.verts) for i in range(3)))
    return lo, hi


class BooleanTest(unittest.TestCase):

    def setUp(self):
        clear_scene()
        # Cube of size 2 at origin, sphere of radius 1 centered on the +X face
        # (create_uvsphere "diameter" is the radius in 2.79).
        self.cube = make_cube("Cube", size=2.0)
        self.cutter = make_sphere("Sphere", diameter=1.0, offset=(1.0, 0.0, 0.0))
        self.cutter.hide_render = True

    def check_solid(self, bm):
        self.assertGreater(len(bm.faces), 0)
        for e in bm.edges:
            self.assertTrue(e.is_manifold, "non-manifold edge %d" % e.index)

    def check_bounds(self, bm, lo, hi):
        blo, bhi = bounds(bm)
        for i in range(3):
            self.assertAlmostEqual(blo[i], lo[i], places=3)
            self.assertAlmostEqual(bhi[i], hi[i], places=3)

    def run_operation(self, solver):
        bm = apply_boolean(self.cube, self.cutter, 'DIFFERENCE', solver)
        self.check_solid(bm)
        self.check_bounds(bm, (-1, -1, -1), (1, 1, 1))
        # The sphere carves a hollow into the +X face, so vertices appear inside the cube.
        self.assertTrue(any(v.co.x < 0.99 and abs(v.co.y) < 0.5 and abs(v.co.z) < 0.5 for v in bm.verts))
        bm.free()
        self.cube.modifiers.clear()

        bm = apply_boolean(self.cube, self.cutter, 'UNION', solver)
        self.check_solid(bm)
        self.check_bounds(bm, (-1, -1, -1), (2, 1, 1))
        bm.free()
        self.cube.modifiers.clear()

        bm = apply_boolean(self.cube, self.cutter, 'INTERSECT', solver)
        self.check_solid(bm)
        self.check_bounds(bm, (0, -1, -1), (1, 1, 1))
        bm.free()

    def test_bmesh_solver(self):
        self.run_operation('BMESH')

    def test_carve_solver(self):
        mod = self.cube.modifiers.new("Probe", 'BOOLEAN')
        has_carve = hasattr(mod, "solver") and 'CARVE' in {
            item.identifier for item in mod.bl_rna.properties["solver"].enum_items}
        self.cube.modifiers.remove(mod)
        if not has_carve:
            self.skipTest("Carve solver not available")
        self.run_operation('CARVE')


if __name__ == '__main__':
    import sys
    sys.argv = [__file__] + (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    result = unittest.main(exit=False).result
    sys.exit(not result.wasSuccessful())
