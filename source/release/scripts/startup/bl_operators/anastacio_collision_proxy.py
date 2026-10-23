# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
# ##### END GPL LICENSE BLOCK #####

"""Game > Performance > Collision Proxies: dense static scenery keeps its mesh for drawing, and a
decimated copy, invisible, takes the Triangle Mesh physics. The original becomes No Collision, which
also keeps it a Static Batch candidate (the proxy is not parented, it lies at the same place).

The proxy copies collision group/mask, margin, materials (friction) and game properties, so collision
sensors that look for a property still fire. Scripts that compare the hit object by name see the proxy.

Left out: objects that are not Static, have logic (EndObject would leave the proxy behind), have a
parent, sit in an inactive layer (spawned by AddObject; the proxy would not come along) or are light.
The cooked file keys meshes by content, so the proxy is cooked like any other mesh.
"Clear Collision Proxies" deletes the proxies and restores the physics of the originals."""

import bpy
from bpy.app.translations import pgettext_tip as tip_
from bpy.props import EnumProperty
from bpy.types import Operator

# On the proxy: name of the object it serves. On the original: its physics settings before the proxy.
TAG = "anastacio_collision_proxy"
PREV = "anastacio_collision_proxy_prev"
MIN_TRIS = 5000
# The proxy aims at a tenth of the triangles, never below this many nor above half.
TARGET_SHARE = 0.1
TARGET_MIN_TRIS = 500


def _tris(mesh):
    return sum(len(p.vertices) - 2 for p in mesh.polygons)


def _in_active_layer(scene, ob):
    return any(a and b for a, b in zip(ob.layers, scene.layers))


def _has_logic(ob):
    game = ob.game
    return bool(game.actuators) or bool(game.components) or any(c.type == 'PYTHON' for c in game.controllers)


def _uses_triangle_mesh(ob):
    game = ob.game
    # Without collision bounds a static mesh collides with its triangles.
    return not game.use_collision_bounds or game.collision_bounds_type == 'TRIANGLE_MESH'


def skip_reason(scene, ob):
    if ob.type != 'MESH' or ob.data is None:
        return "not a mesh"
    if TAG in ob:
        return "is a proxy"
    if PREV in ob:
        return "has a proxy"
    if ob.game.physics_type != 'STATIC' or not _uses_triangle_mesh(ob):
        return "not Static Triangle Mesh"
    if _has_logic(ob):
        return "logic"
    if ob.parent is not None:
        return "parent"
    if not _in_active_layer(scene, ob):
        return "inactive layer"
    if _tris(ob.data) < MIN_TRIS:
        return "light mesh"
    return None


def candidates(scene):
    return [ob for ob in scene.objects if skip_reason(scene, ob) is None]


def _decimated_mesh(scene, ob, ratio, name):
    modifier = ob.modifiers.new("collision_proxy_decimate", 'DECIMATE')
    modifier.decimate_type = 'COLLAPSE'
    modifier.ratio = ratio
    modifier.use_collapse_quality = True
    try:
        mesh = ob.to_mesh(scene, True, 'PREVIEW')
    finally:
        ob.modifiers.remove(modifier)
    mesh.name = name
    return mesh


def _copy_game_properties(src, dst):
    for prop in src.game.properties:
        scene_ob = bpy.context.scene.objects.active
        bpy.context.scene.objects.active = dst
        bpy.ops.object.game_property_new(type=prop.type, name=prop.name)
        bpy.context.scene.objects.active = scene_ob
        dst.game.properties[prop.name].value = prop.value


def make_proxy(scene, ob, meshes=None):
    tris = _tris(ob.data)
    target = max(TARGET_MIN_TRIS, tris * TARGET_SHARE)
    ratio = min(0.5, target / tris)
    key = (ob.data.name, tuple(m.name for m in ob.modifiers), ratio)
    mesh = meshes.get(key) if meshes is not None else None
    if mesh is None:
        mesh = _decimated_mesh(scene, ob, ratio, ob.data.name + "_COL")
        if meshes is not None:
            meshes[key] = mesh

    proxy = bpy.data.objects.new(ob.name + "_COL", mesh)
    proxy[TAG] = ob.name
    scene.objects.link(proxy)
    proxy.layers = ob.layers
    proxy.matrix_world = ob.matrix_world
    proxy.hide_render = True
    src, dst = ob.game, proxy.game
    dst.physics_type = 'STATIC'
    dst.use_collision_bounds = True
    dst.collision_bounds_type = 'TRIANGLE_MESH'
    dst.collision_margin = src.collision_margin
    dst.collision_group = src.collision_group
    dst.collision_mask = src.collision_mask
    _copy_game_properties(ob, proxy)

    ob[PREV] = {
        "physics_type": src.physics_type,
        "use_collision_bounds": src.use_collision_bounds,
        "collision_bounds_type": src.collision_bounds_type,
    }
    src.physics_type = 'NO_COLLISION'
    return proxy


def generate(scene, objects):
    """Returns (done, skipped) where skipped is a list of (object, reason)."""
    done, skipped = [], []
    meshes = {}
    for ob in objects:
        reason = skip_reason(scene, ob)
        if reason:
            skipped.append((ob, reason))
            continue
        make_proxy(scene, ob, meshes)
        done.append(ob)
    return done, skipped


def clear(scene, ob):
    """Delete the proxy of ob and restore its physics. Returns True when there was one."""
    if PREV not in ob:
        return False
    prev = ob[PREV].to_dict()
    ob.game.physics_type = prev["physics_type"]
    ob.game.use_collision_bounds = prev["use_collision_bounds"]
    ob.game.collision_bounds_type = prev["collision_bounds_type"]
    del ob[PREV]
    for proxy in [o for o in bpy.data.objects if o.get(TAG) == ob.name]:
        mesh = proxy.data
        bpy.data.objects.remove(proxy, do_unlink=True)
        if mesh is not None and mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    return True


class GAME_OT_collision_proxy_generate(Operator):
    """Give dense static scenery a decimated invisible copy that takes the physics (selected objects, or every candidate when nothing is selected)"""
    bl_idname = "game.collision_proxy_generate"
    bl_label = "Generate Collision Proxies"
    bl_options = {'REGISTER', 'UNDO'}

    source: EnumProperty(
        name="Objects",
        items=(('AUTO', "Selected or All", "Selected objects, or every candidate when nothing is selected"),
               ('SELECTED', "Selected", "Only the selected objects"),
               ('ALL', "All Candidates", "Every static Triangle Mesh with %d triangles or more" % MIN_TRIS)),
        default='AUTO')

    def execute(self, context):
        scene = context.scene
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        selected = list(context.selected_objects)
        if self.source == 'SELECTED' or (self.source == 'AUTO' and selected):
            objects = selected
        else:
            objects = candidates(scene)
        if not objects:
            self.report({'WARNING'}, tip_("No dense static Triangle Mesh to simplify"))
            return {'CANCELLED'}
        done, skipped = generate(scene, objects)
        msg = tip_("Collision proxies made for %d object(s)") % len(done)
        if skipped:
            msg += tip_("; left out %d: %s") % (len(skipped), ", ".join(
                "%s (%s)" % (ob.name, tip_(reason)) for ob, reason in skipped[:5]))
        self.report({'INFO'} if done else {'WARNING'}, msg)
        return {'FINISHED'} if done else {'CANCELLED'}


class GAME_OT_collision_proxy_clear(Operator):
    """Delete the collision proxies and restore the physics of the originals (selected objects, or the whole scene when nothing is selected)"""
    bl_idname = "game.collision_proxy_clear"
    bl_label = "Clear Collision Proxies"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        objects = list(context.selected_objects) or list(scene.objects)
        # A selected proxy stands for its original.
        originals = {scene.objects.get(ob[TAG], ob) if TAG in ob else ob for ob in objects}
        restored = sum(clear(scene, ob) for ob in originals)
        self.report({'INFO'}, tip_("Removed %d collision proxy(ies)") % restored)
        return {'FINISHED'}


classes = (
    GAME_OT_collision_proxy_generate,
    GAME_OT_collision_proxy_clear,
)
