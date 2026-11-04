# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
# ##### END GPL LICENSE BLOCK #####

"""Add > Mesh > Brazilian House / Brazilian Street Block.

Low poly houses from range_buildings: one shared atlas texture and one material, so a
whole block is a single mesh and a single draw call. LOD1 is a far version (<= 40 tris)."""

import math

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty
from bpy.types import Operator
from mathutils import Matrix


def _style_items(self, context):
    import range_buildings as rb
    return [(k, rb.LABELS[k][0], rb.LABELS[k][1]) for k in rb.STYLES]


LOD_ITEMS = (
    ('LOD0', "Near (LOD0)", "Full detail (up to 300 triangles, 500 for the apartment block)"),
    ('LOD1', "Far (LOD1)", "Box and roof with the facade in the texture (up to 40 triangles)"),
    ('BOTH', "LOD0 + LOD1 Switch", "Near mesh with the far mesh as a level of detail"),
)
LOD_LAYER = 19


def _place(context, ob):
    ob.location = context.scene.cursor_location
    for o in context.selected_objects:
        o.select = False
    ob.select = True
    context.scene.objects.active = ob


def _attach_lod(context, ob, far_mesh, distance):
    lod = bpy.data.objects.new(ob.name + "_LOD1", far_mesh)
    context.scene.objects.link(lod)
    lod.layers = [k == LOD_LAYER for k in range(20)]
    lod.matrix_world = ob.matrix_world
    lod.hide_render = True
    lod.game.physics_type = 'NO_COLLISION'
    context.scene.objects.active = ob
    bpy.ops.object.lod_add()
    level = ob.lod_levels[len(ob.lod_levels) - 1]
    level.object = lod
    level.use_mesh = True
    level.distance = distance


class MESH_OT_brazilian_house_add(Operator):
    """Add a low poly Brazilian house (one shared atlas material)"""
    bl_idname = "mesh.brazilian_house_add"
    bl_label = "Brazilian House"
    bl_options = {'REGISTER', 'UNDO'}

    style: EnumProperty(name="Style", items=_style_items)
    seed: IntProperty(name="Seed", default=0, min=0)
    width: FloatProperty(name="Width", description="Lot width (0 = from the seed)", default=0.0, min=0.0,
                         max=20.0, unit='LENGTH')
    depth: FloatProperty(name="Depth", description="Lot depth (0 = from the seed)", default=0.0, min=0.0,
                         max=30.0, unit='LENGTH')
    floors: IntProperty(name="Floors", description="0 = from the seed", default=0, min=0, max=5)
    lod: EnumProperty(name="Detail", items=LOD_ITEMS, default='LOD0')
    foundation: FloatProperty(name="Foundation", description="Walls go this far below the ground (slopes)",
                              default=0.0, min=0.0, max=10.0, unit='LENGTH')
    lod_distance: FloatProperty(name="LOD Distance", default=60.0, min=5.0, unit='LENGTH')

    def execute(self, context):
        import range_buildings as rb
        kw = dict(width=self.width or None, depth=self.depth or None, floors=self.floors or None,
                  foundation=self.foundation)
        near = self.lod != 'LOD1'
        built = rb.build(self.style, self.seed, lod=0 if near else 1, **kw)
        name = "Casa_%s_%d" % (self.style, self.seed)
        ob = bpy.data.objects.new(name, rb.to_mesh(name, built))
        context.scene.objects.link(ob)
        ob.game.physics_type = 'NO_COLLISION'
        ob["range_buildings"] = "%s:%d" % (self.style, self.seed)
        _place(context, ob)
        if self.lod == 'BOTH':
            context.scene.update()
            far = rb.to_mesh(name + "_LOD1", rb.build(self.style, self.seed, lod=1, **kw))
            _attach_lod(context, ob, far, self.lod_distance)
        return {'FINISHED'}


class MESH_OT_brazilian_street_add(Operator):
    """Add a row of varied Brazilian houses side by side as one mesh"""
    bl_idname = "mesh.brazilian_street_add"
    bl_label = "Brazilian Street Block"
    bl_options = {'REGISTER', 'UNDO'}

    count: IntProperty(name="Houses", default=8, min=1, max=60)
    seed: IntProperty(name="Seed", default=0, min=0)
    mixed: BoolProperty(name="Mixed Styles", default=True)
    style: EnumProperty(name="Style", items=_style_items)
    sidewalk: BoolProperty(name="Sidewalk", default=True)
    sidewalk_width: FloatProperty(name="Sidewalk Width", default=2.5, min=0.5, max=8.0, unit='LENGTH')
    lod: EnumProperty(name="Detail", items=LOD_ITEMS, default='LOD0')
    foundation: FloatProperty(name="Foundation", default=0.0, min=0.0, max=10.0, unit='LENGTH')
    lod_distance: FloatProperty(name="LOD Distance", default=90.0, min=5.0, unit='LENGTH')

    def _built(self, lod):
        import random
        import range_buildings as rb
        R = random.Random(self.seed * 7919 + 13)
        items, x = [], 0.0
        for k in range(self.count):
            st = R.choice(rb.STYLES) if self.mixed else self.style
            s = R.randrange(100000)
            b = rb.build(st, s, lod=lod, foundation=self.foundation)
            items.append((b, Matrix.Translation((x + b["size"][0] / 2, 0, 0))))
            x += b["size"][0]
        if self.sidewalk:
            items.append((rb.sidewalk(x, self.sidewalk_width), Matrix.Translation((x / 2, 0, 0))))
        center = Matrix.Translation((-x / 2, 0, 0))
        return rb.merge([(b, center * m) for b, m in items])

    def execute(self, context):
        import range_buildings as rb
        near = self.lod != 'LOD1'
        name = "Rua_%d" % self.seed
        ob = bpy.data.objects.new(name, rb.to_mesh(name, self._built(0 if near else 1)))
        context.scene.objects.link(ob)
        ob.game.physics_type = 'NO_COLLISION'
        _place(context, ob)
        if self.lod == 'BOTH':
            context.scene.update()
            _attach_lod(context, ob, rb.to_mesh(name + "_LOD1", self._built(1)), self.lod_distance)
        return {'FINISHED'}


def menu_func(self, context):
    self.layout.separator()
    self.layout.operator(MESH_OT_brazilian_house_add.bl_idname, icon='MESH_CUBE')
    self.layout.operator(MESH_OT_brazilian_street_add.bl_idname, icon='MESH_GRID')


def _menu():
    menu = getattr(bpy.types, "INFO_MT_mesh_add", None)
    if menu is None:  # bl_ui registra depois de bl_operators
        from bl_ui.space_view3d import INFO_MT_mesh_add as menu
    return menu


def register_props():
    _menu().append(menu_func)


def unregister_props():
    try:
        _menu().remove(menu_func)
    except Exception:
        pass


classes = (
    MESH_OT_brazilian_house_add,
    MESH_OT_brazilian_street_add,
)
