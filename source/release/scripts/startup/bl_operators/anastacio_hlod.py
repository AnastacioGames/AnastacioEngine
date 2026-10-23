# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
# ##### END GPL LICENSE BLOCK #####

"""Game > Performance > Build HLOD: far groups of objects drawn as one simplified mesh.

The scene floor is cut into square cells. The meshes of each cell are joined into one proxy object
(Decimate Collapse, High Quality, applied) placed at the cell center. Everything is baked here, in
the editor; the game only switches LoD levels:
  - the proxy has an invisible base level and shows its own mesh from Distance on;
  - each original gets a last invisible level at Distance + cell radius, measured from its origin.
An original only hides once its proxy is already showing, so far groups never open holes; in the
band between the two distances both are drawn.

Left out: meshes with shape keys or an armature, dynamic physics objects, Static Batch objects and
objects whose LoD levels go past the HLOD distance. "Clear HLOD" deletes what this tool made."""

import math

import bpy
from bpy.app.translations import pgettext_tip as tip_
from bpy.props import FloatProperty, IntProperty
from bpy.types import Operator
from mathutils import Matrix, Vector

# Marks the proxies this tool made (value: cell name) and the originals it hid (value: proxy name).
TAG = "anastacio_hlod"
TAG_SOURCE = "anastacio_hlod_source"


def _skip_reason(ob):
    if ob.type != 'MESH' or ob.data is None:
        return "not a mesh"
    if TAG in ob:
        return "HLOD proxy"
    if ob.data.shape_keys is not None:
        return "shape keys"
    if any(m.type == 'ARMATURE' for m in ob.modifiers) or (ob.parent and ob.parent.type == 'ARMATURE'):
        return "armature"
    if ob.game.physics_type in {'DYNAMIC', 'RIGID_BODY', 'SOFT_BODY', 'CHARACTER', 'VEHICLE'}:
        return "moves"
    if ob.use_static_batch:
        return "Static Batch"
    return None


def _world_mesh(scene, ob):
    mesh = ob.to_mesh(scene, True, 'PREVIEW')
    mesh.transform(ob.matrix_world)
    return mesh


def _joined_proxy(scene, objects, name):
    """One object with the world-space meshes of objects joined (materials kept)."""
    parts = []
    for ob in objects:
        part = bpy.data.objects.new(name, _world_mesh(scene, ob))
        scene.objects.link(part)
        parts.append(part)
    for ob in scene.objects:
        ob.select = False
    for part in parts:
        part.select = True
    scene.objects.active = parts[0]
    if len(parts) > 1:
        bpy.ops.object.join()
    proxy = scene.objects.active
    proxy.name = name
    proxy.data.name = name
    return proxy


def _decimate(scene, ob, ratio):
    if ratio >= 1.0:
        return
    modifier = ob.modifiers.new("hlod_decimate", 'DECIMATE')
    modifier.decimate_type = 'COLLAPSE'
    modifier.ratio = ratio
    modifier.use_collapse_quality = True
    old = ob.data
    try:
        ob.data = ob.to_mesh(scene, True, 'PREVIEW')
    finally:
        ob.modifiers.remove(modifier)
    ob.data.name = old.name
    if old.users == 0:
        bpy.data.meshes.remove(old)


def _set_invisible_from(scene, ob, distance):
    """Append a last invisible LoD level to ob. False when its own levels already reach further."""
    levels = ob.lod_levels
    if len(levels) > 1 and levels[-1].distance >= distance:
        return False
    scene.objects.active = ob
    bpy.ops.object.lod_add()
    level = ob.lod_levels[-1]
    level.object = None
    level.use_mesh = False
    level.use_material = False
    level.use_invisible_mesh = True
    # No hysteresis: the original and its proxy must cross at fixed distances.
    level.use_object_hysteresis = True
    level.object_hysteresis_percentage = 0
    level.distance = distance
    return True


def _cells(objects, size):
    cells = {}
    for ob in objects:
        p = ob.matrix_world.translation
        cells.setdefault((math.floor(p.x / size), math.floor(p.y / size)), []).append(ob)
    return cells


def clear(scene):
    """Delete the proxies and the invisible levels this tool added. Returns the proxy count."""
    active = scene.objects.active
    for ob in list(scene.objects):
        if TAG_SOURCE not in ob:
            continue
        levels = ob.lod_levels
        if len(levels) > 1 and levels[-1].use_invisible_mesh:
            scene.objects.active = ob
            bpy.ops.object.lod_remove(index=len(levels) - 1)
        del ob[TAG_SOURCE]
    proxies = [ob for ob in scene.objects if TAG in ob]
    for ob in proxies:
        mesh = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        if mesh is not None and mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    scene.objects.active = active if active and active.name in scene.objects else None
    return len(proxies)


def build(scene, objects, cell_size=40.0, distance=80.0, ratio=0.25, min_objects=4):
    """Build one proxy per cell. Returns (proxies, skipped) where skipped is a list of (object, reason)."""
    clear(scene)
    skipped, usable = [], []
    for ob in objects:
        reason = _skip_reason(ob)
        if reason:
            skipped.append((ob, reason))
        else:
            usable.append(ob)

    active = scene.objects.active
    selected = [ob for ob in scene.objects if ob.select]
    proxies = []
    for (cx, cy), group in sorted(_cells(usable, cell_size).items()):
        if len(group) < min_objects:
            continue
        center = sum((ob.matrix_world.translation for ob in group), Vector()) / len(group)
        center.z = min(ob.matrix_world.translation.z for ob in group)
        radius = max((ob.matrix_world.translation - center).length for ob in group)

        group = [ob for ob in group if _set_invisible_from(scene, ob, distance + radius)
                 or skipped.append((ob, "own LoD reaches further"))]
        if not group:
            continue

        proxy = _joined_proxy(scene, group, "HLOD_%d_%d" % (cx, cy))
        proxy.data.transform(Matrix.Translation(-center))
        proxy.matrix_world = Matrix.Translation(center)
        _decimate(scene, proxy, ratio)
        proxy[TAG] = proxy.name
        proxy.layers = group[0].layers[:]
        proxy.game.physics_type = 'NO_COLLISION'
        for ob in group:
            ob[TAG_SOURCE] = proxy.name

        scene.objects.active = proxy
        bpy.ops.object.lod_add()
        base, far = proxy.lod_levels[0], proxy.lod_levels[1]
        base.use_invisible_mesh = True
        far.object = proxy
        far.use_mesh = True
        far.use_material = True
        far.use_object_hysteresis = True
        far.object_hysteresis_percentage = 0
        far.distance = distance
        proxies.append(proxy)

    for ob in scene.objects:
        ob.select = ob in selected
    scene.objects.active = active
    return proxies, skipped


class GAME_OT_hlod_build(Operator):
    """Join far groups of meshes into one simplified proxy per cell (selected meshes, or every static mesh when nothing is selected)"""
    bl_idname = "game.hlod_build"
    bl_label = "Build HLOD"
    bl_options = {'REGISTER', 'UNDO'}

    cell_size: FloatProperty(name="Cell Size", description="Side of the square cells that are joined",
                             default=40.0, min=1.0, unit='LENGTH')
    distance: FloatProperty(name="Distance", description="Camera distance from which a cell is drawn as its proxy",
                            default=80.0, min=1.0, unit='LENGTH')
    ratio: FloatProperty(name="Ratio", description="Share of the triangles kept in the proxy",
                         default=0.25, min=0.01, max=1.0)
    min_objects: IntProperty(name="Min Objects", description="Cells with fewer objects are left as they are",
                             default=4, min=2)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        scene = context.scene
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        objects = [ob for ob in context.selected_objects if TAG not in ob]
        if not objects:
            objects = [ob for ob in scene.objects if ob.type == 'MESH' and TAG not in ob]
        proxies, skipped = build(scene, objects, self.cell_size, self.distance, self.ratio, self.min_objects)
        msg = tip_("HLOD: %d proxy(ies)") % len(proxies)
        moved = [s for s in skipped if s[1] != "not a mesh"]
        if moved:
            msg += tip_("; left out %d: %s") % (len(moved), ", ".join(
                "%s (%s)" % (ob.name, tip_(reason)) for ob, reason in moved[:5]))
        self.report({'INFO'} if proxies else {'WARNING'}, msg)
        return {'FINISHED'} if proxies else {'CANCELLED'}


class GAME_OT_hlod_clear(Operator):
    """Delete the HLOD proxies and the invisible levels Build HLOD added"""
    bl_idname = "game.hlod_clear"
    bl_label = "Clear HLOD"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        removed = clear(context.scene)
        self.report({'INFO'}, tip_("Removed %d HLOD proxy(ies)") % removed)
        return {'FINISHED'}


classes = (
    GAME_OT_hlod_build,
    GAME_OT_hlod_clear,
)
