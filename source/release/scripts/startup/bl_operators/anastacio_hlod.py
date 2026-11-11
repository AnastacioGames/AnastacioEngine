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
(Decimate Collapse, High Quality, applied; or meshoptimizer's sloppy simplifier, which ignores
topology and also fuses separate objects) placed at the cell center. Everything is baked here, in
the editor; the game only switches LoD levels:
  - the proxy has an invisible base level and shows its own mesh from Distance on;
  - each original gets a last invisible level at the same Distance whose object is the proxy: the
    runtime then measures the original's distance from the proxy, so the whole cell and its proxy
    switch on the same frame (no holes, no band where both are drawn).

Left out: meshes with shape keys or an armature, dynamic physics objects, Static Batch objects and
objects whose LoD levels go past the HLOD distance. "Clear HLOD" deletes what this tool made."""

import math

import bpy
from bpy.app.translations import pgettext_tip as tip_
from bpy.props import EnumProperty, FloatProperty, IntProperty
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


def _meshopt_lib():
    import ctypes
    from .anastacio_lightmap import native_library
    u32 = ctypes.POINTER(ctypes.c_uint)
    fp = ctypes.POINTER(ctypes.c_float)
    return native_library("ae_meshopt", lambda lib: setattr(lib.ae_simplify_sloppy, "argtypes", (
        fp, ctypes.c_int, u32, ctypes.c_int, ctypes.c_int, ctypes.c_float, u32, fp)))


def _sloppy(ob, ratio):
    """Replace ob's mesh with meshopt_simplifySloppy (ae_meshopt) of its triangles. The simplifier only
    keeps original vertices, so each new triangle takes material and UVs from the nearest original
    triangle (UV of the closest point on it). Returns False when ae_meshopt is missing; keeps
    the mesh when nothing would be left."""
    if ratio >= 1.0:
        return True
    import ctypes
    import numpy as np
    from mathutils.bvhtree import BVHTree
    from .anastacio_lightmap import loop_triangles
    u32 = ctypes.POINTER(ctypes.c_uint)
    fp = ctypes.POINTER(ctypes.c_float)
    lib = _meshopt_lib()
    if lib is None:
        return False
    me = ob.data
    loops = loop_triangles(me)
    if not len(loops):
        return True
    loop_vert = np.empty(len(me.loops), dtype=np.int64)
    me.loops.foreach_get("vertex_index", loop_vert)
    pos = np.empty(len(me.vertices) * 3, dtype=np.float32)
    me.vertices.foreach_get("co", pos)
    idx = np.ascontiguousarray(loop_vert[loops], dtype=np.uint32)
    out = np.empty(len(idx), dtype=np.uint32)
    err = ctypes.c_float()
    n = lib.ae_simplify_sloppy(pos.ctypes.data_as(fp), len(me.vertices), idx.ctypes.data_as(u32), len(idx),
                               int(len(idx) * ratio), 1.0, out.ctypes.data_as(u32), ctypes.byref(err))
    if n < 3:
        return True
    out = out[:n].reshape(-1, 3)

    pos = pos.reshape(-1, 3)
    loops = loops.reshape(-1, 3)
    loop_poly = np.empty(len(me.loops), dtype=np.int64)
    for p in me.polygons:
        loop_poly[p.loop_start:p.loop_start + p.loop_total] = p.index
    mats = np.empty(len(me.polygons), dtype=np.int64)
    me.polygons.foreach_get("material_index", mats)
    smooth = np.empty(len(me.polygons), dtype=bool)
    me.polygons.foreach_get("use_smooth", smooth)
    tris = loop_vert[loops]
    bvh = BVHTree.FromPolygons([Vector(v) for v in pos], tris.tolist(), all_triangles=True)
    layers = [np.empty(len(me.loops) * 2, dtype=np.float32) for _ in me.uv_layers]
    for layer, data in zip(me.uv_layers, layers):
        layer.data.foreach_get("uv", data)
    layers = [d.reshape(-1, 2) for d in layers]

    used, remap = np.unique(out, return_inverse=True)
    faces = remap.reshape(-1, 3)
    source = []
    for a, b, c in out:
        _, _, t, _ = bvh.find_nearest(Vector((pos[a] + pos[b] + pos[c]) / 3.0))
        source.append(t if t is not None else 0)

    new = bpy.data.meshes.new(me.name)
    new.vertices.add(len(used))
    new.vertices.foreach_set("co", pos[used].ravel())
    new.loops.add(len(faces) * 3)
    new.loops.foreach_set("vertex_index", faces.ravel().astype(np.int32))
    new.polygons.add(len(faces))
    new.polygons.foreach_set("loop_start", np.arange(0, len(faces) * 3, 3, dtype=np.int32))
    new.polygons.foreach_set("loop_total", np.full(len(faces), 3, dtype=np.int32))
    src_poly = loop_poly[loops[source, 0]]
    new.polygons.foreach_set("material_index", mats[src_poly].astype(np.int32))
    new.polygons.foreach_set("use_smooth", smooth[src_poly])
    for m in me.materials:
        new.materials.append(m)
    # Barycentric weights of every new corner on its source triangle, clamped to it (no extrapolation).
    # Exact when the corner is a vertex of that triangle; near borders it is only close to the nearest
    # point, good enough for a proxy seen from far away.
    src = np.asarray(source, dtype=np.int64)
    a, b, c = (pos[tris[src, k]] for k in range(3))
    p = pos[out]  # (faces, 3 corners, xyz)
    e0, e1 = (b - a)[:, None], (c - a)[:, None]
    e2 = p - a[:, None]
    d00, d01, d11 = (e0 * e0).sum(-1), (e0 * e1).sum(-1), (e1 * e1).sum(-1)
    d20, d21 = (e2 * e0).sum(-1), (e2 * e1).sum(-1)
    den = d00 * d11 - d01 * d01
    den[den == 0.0] = 1.0
    wb = (d11 * d20 - d01 * d21) / den
    wc = (d00 * d21 - d01 * d20) / den
    w = np.clip(np.stack((1.0 - wb - wc, wb, wc), -1), 0.0, None)
    w /= np.maximum(w.sum(-1, keepdims=True), 1e-12)
    for layer, data in zip(me.uv_layers, layers):
        tri_uv = data[loops[src]]  # (faces, 3 source corners, uv)
        uv = np.einsum('fks,fsu->fku', w, tri_uv).astype(np.float32)
        new.uv_textures.new(layer.name)
        new.uv_layers[layer.name].data.foreach_set("uv", uv.ravel())
    if me.uv_textures.active is not None:
        new.uv_textures.active = new.uv_textures[me.uv_textures.active.name]
    for layer in me.vertex_colors:
        size = len(layer.data[0].color) if len(layer.data) else 3  # RGB or RGBA
        col = np.empty(len(me.loops) * size, dtype=np.float32)
        layer.data.foreach_get("color", col)
        tri_col = col.reshape(-1, size)[loops[src]]
        dst = new.vertex_colors.new(layer.name)
        dst.data.foreach_set("color", np.einsum('fks,fsc->fkc', w, tri_col).astype(np.float32).ravel())
    if me.vertex_colors.active is not None:
        new.vertex_colors.active = new.vertex_colors[me.vertex_colors.active.name]
    new.validate()
    new.update(calc_edges=True)
    ob.data = new
    if me.users == 0:
        bpy.data.meshes.remove(me)
    new.name = ob.name
    return True


def _set_invisible_from(scene, ob, distance, anchor):
    """Append a last invisible LoD level to ob, measured from anchor. False when its own levels already reach further."""
    levels = ob.lod_levels
    if len(levels) > 1 and levels[-1].distance >= distance:
        return False
    scene.objects.active = ob
    bpy.ops.object.lod_add()
    level = ob.lod_levels[-1]
    level.object = anchor
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


def build(scene, objects, cell_size=40.0, distance=80.0, ratio=0.25, min_objects=4, method='DECIMATE'):
    """Build one proxy per cell. Returns (proxies, skipped) where skipped is a list of (object, reason).
    method: 'DECIMATE' (Decimate Collapse) or 'SLOPPY' (meshoptimizer; RuntimeError without ae_meshopt)."""
    if method == 'SLOPPY' and _meshopt_lib() is None:
        raise RuntimeError("ae_meshopt library not found next to the executable")
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
        group = [ob for ob in group if not (len(ob.lod_levels) > 1 and ob.lod_levels[-1].distance >= distance)
                 or skipped.append((ob, "own LoD reaches further"))]
        if len(group) < min_objects:
            continue

        proxy = _joined_proxy(scene, group, "HLOD_%d_%d" % (cx, cy))
        proxy.data.transform(Matrix.Translation(-center))
        proxy.matrix_world = Matrix.Translation(center)
        if method == 'SLOPPY':
            if not _sloppy(proxy, ratio):
                bpy.data.objects.remove(proxy, do_unlink=True)
                raise RuntimeError("ae_meshopt library not found next to the executable")
        else:
            _decimate(scene, proxy, ratio)
        proxy[TAG] = proxy.name
        proxy.layers = group[0].layers[:]
        proxy.game.physics_type = 'NO_COLLISION'
        for ob in group:
            _set_invisible_from(scene, ob, distance, proxy)
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
    method: EnumProperty(name="Method", description="How the joined mesh of a cell is simplified", items=(
        ('DECIMATE', "Decimate", "Decimate Collapse (High Quality): keeps the shape and UV seams"),
        ('SLOPPY', "Sloppy", "meshoptimizer: much faster on big cells, ignores topology and fuses "
                             "nearby parts; for proxies seen only from far away"),
    ), default='DECIMATE')
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
        try:
            proxies, skipped = build(scene, objects, self.cell_size, self.distance, self.ratio, self.min_objects,
                                     self.method)
        except RuntimeError as ex:
            self.report({'ERROR'}, "HLOD: " + tip_(str(ex)))
            return {'CANCELLED'}
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
