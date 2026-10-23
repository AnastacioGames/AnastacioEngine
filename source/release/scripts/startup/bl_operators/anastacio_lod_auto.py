# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
# ##### END GPL LICENSE BLOCK #####

"""Game > Performance > Generate LODs: builds levels of detail for many meshes at once.

Each level is a real low-poly mesh (Decimate Collapse, High Quality, applied), held by a hidden object
on the last layer. Switch distances come from the object size: a level starts when the object fills
less than a given share of the screen height. Objects sharing a mesh share the generated meshes.

Left out: meshes with shape keys or an armature (they deform), Static Batch objects (a LoD switch
splits them out of the batch) and objects that already have LoD levels made by hand.
"Clear Generated LODs" deletes what this tool made and empties the LoD list."""

import math

import bpy
from bpy.app.translations import pgettext_tip as tip_
from bpy.props import BoolProperty, EnumProperty, IntProperty
from bpy.types import Operator

# Marks the hidden objects this tool made; the value is the name of the object they serve.
TAG = "anastacio_lod_auto"
LOD_LAYER = 19
HEAVY_TRIS = 50000

# (decimate ratio, share of the screen height under which the level starts)
LEVELS = (
    (0.5, 0.25),
    (0.25, 0.10),
    (0.1, 0.04),
)
# Vertical field of view assumed for the distances (Range default camera, 35 mm lens).
HALF_FOV_TAN = math.tan(math.radians(49.1) / 2.0)
HYSTERESIS = 10


def _tris(mesh):
    return sum(len(p.vertices) - 2 for p in mesh.polygons)


def _skip_reason(ob):
    if ob.type != 'MESH' or ob.data is None:
        return "not a mesh"
    if ob.data.shape_keys is not None:
        return "shape keys"
    if any(m.type == 'ARMATURE' for m in ob.modifiers) or (ob.parent and ob.parent.type == 'ARMATURE'):
        return "armature"
    if ob.use_static_batch:
        return "Static Batch"
    if TAG in ob:
        return "generated LoD"
    if len(ob.lod_levels) > 1 and not _generated_levels(ob):
        return "LoD made by hand"
    return None


def _generated_levels(ob):
    return [level.object for level in ob.lod_levels[1:]
            if level.object is not None and level.object.get(TAG) == ob.name]


def _radius(ob):
    # Half of the largest side, in world units (dimensions already include the scale).
    return max(ob.dimensions) * 0.5


def lod_distance(radius, screen_share):
    """Distance at which a sphere of this radius fills screen_share of the screen height."""
    return radius / (screen_share * HALF_FOV_TAN)


def _decimated_mesh(scene, ob, ratio, name):
    modifier = ob.modifiers.new("lod_auto_decimate", 'DECIMATE')
    modifier.decimate_type = 'COLLAPSE'
    modifier.ratio = ratio
    modifier.use_collapse_quality = True
    try:
        mesh = ob.to_mesh(scene, True, 'PREVIEW')
    finally:
        ob.modifiers.remove(modifier)
    mesh.name = name
    return mesh


def clear_generated(scene, ob):
    """Remove the levels this tool made for ob. Returns how many were removed."""
    generated = _generated_levels(ob)
    if not generated:
        return 0
    active = scene.objects.active
    scene.objects.active = ob
    while len(ob.lod_levels) > 1:
        # Removing the last user level also drops the base level.
        if 'CANCELLED' in bpy.ops.object.lod_remove(index=len(ob.lod_levels) - 1):
            break
    scene.objects.active = active
    for lod in generated:
        mesh = lod.data
        bpy.data.objects.remove(lod, do_unlink=True)
        if mesh is not None and mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    return len(generated)


def generate(scene, objects, count=3):
    """Generate count-1 levels for each object that can take them.

    Returns (done, skipped) where skipped is a list of (object, reason)."""
    done, skipped = [], []
    meshes = {}
    levels = LEVELS[:max(1, count - 1)]
    active = scene.objects.active
    for ob in objects:
        reason = _skip_reason(ob)
        if reason:
            skipped.append((ob, reason))
            continue
        clear_generated(scene, ob)
        radius = _radius(ob)
        if radius <= 0.0:
            skipped.append((ob, "no size"))
            continue

        scene.objects.active = ob
        for i, (ratio, share) in enumerate(levels, 1):
            key = (ob.data.name, tuple(m.name for m in ob.modifiers), ratio)
            mesh = meshes.get(key)
            if mesh is None:
                mesh = _decimated_mesh(scene, ob, ratio, "%s_LOD%d" % (ob.data.name, i))
                meshes[key] = mesh
            lod = bpy.data.objects.new("%s_LOD%d" % (ob.name, i), mesh)
            lod[TAG] = ob.name
            scene.objects.link(lod)
            lod.layers = [k == LOD_LAYER for k in range(20)]
            lod.matrix_world = ob.matrix_world
            lod.hide_render = True
            lod.game.physics_type = 'NO_COLLISION'

            bpy.ops.object.lod_add()
            level = ob.lod_levels[i]
            level.object = lod
            level.use_mesh = True
            level.use_object_hysteresis = True
            level.object_hysteresis_percentage = HYSTERESIS
            level.distance = lod_distance(radius, share)
        done.append(ob)
    scene.objects.active = active
    return done, skipped


def heavy_meshes(scene):
    return [ob for ob in scene.objects if ob.type == 'MESH' and ob.data is not None
            and TAG not in ob and _tris(ob.data) >= HEAVY_TRIS]


class GAME_OT_lod_generate_batch(Operator):
    """Generate levels of detail for the selected meshes (or every heavy mesh when nothing is selected), with distances from each object's size"""
    bl_idname = "game.lod_generate_batch"
    bl_label = "Generate LODs"
    bl_options = {'REGISTER', 'UNDO'}

    count: IntProperty(name="Levels", description="Levels including the original mesh",
                       default=3, min=2, max=len(LEVELS) + 1)
    source: EnumProperty(
        name="Objects",
        items=(('AUTO', "Selected or Heavy", "Selected meshes, or every heavy mesh when nothing is selected"),
               ('SELECTED', "Selected", "Only the selected meshes"),
               ('HEAVY', "Heavy Meshes", "Every mesh with %d triangles or more" % HEAVY_TRIS)),
        default='AUTO')

    def execute(self, context):
        scene = context.scene
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        selected = [ob for ob in context.selected_objects if TAG not in ob]
        if self.source == 'SELECTED' or (self.source == 'AUTO' and selected):
            objects = selected
        else:
            objects = heavy_meshes(scene)
        if not objects:
            self.report({'WARNING'}, tip_("No meshes to generate LODs for"))
            return {'CANCELLED'}
        done, skipped = generate(scene, objects, self.count)
        msg = tip_("LODs generated for %d object(s)") % len(done)
        if skipped:
            msg += tip_("; left out %d: %s") % (len(skipped), ", ".join(
                "%s (%s)" % (ob.name, tip_(reason)) for ob, reason in skipped[:5]))
        self.report({'INFO'} if done else {'WARNING'}, msg)
        return {'FINISHED'} if done else {'CANCELLED'}


class GAME_OT_lod_clear_generated(Operator):
    """Delete the levels of detail made by Generate LODs (selected objects, or the whole scene when nothing is selected)"""
    bl_idname = "game.lod_clear_generated"
    bl_label = "Clear Generated LODs"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        objects = [ob for ob in context.selected_objects if TAG not in ob] or list(scene.objects)
        removed = sum(clear_generated(scene, ob) for ob in objects if TAG not in ob)
        self.report({'INFO'}, tip_("Removed %d generated LoD level(s)") % removed)
        return {'FINISHED'}


classes = (
    GAME_OT_lod_generate_batch,
    GAME_OT_lod_clear_generated,
)
