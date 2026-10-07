# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# <pep8 compliant>

"""Baked indirect light (lightmap) for the Game PBR (Shading Nodes) path.

One atlas for the whole scene: every static mesh gets a UV layer named "Lightmap" packed together, and
Cycles bakes into a single image the light that the game does not compute live:
  - the bounces of every lamp (INDIRECT), with the lamps rebuilt to match the game falloff/units;
  - the direct light of the World and of emissive meshes (lamps hidden), which the lightmap replaces
    in the game (it takes the place of the probe/World diffuse).
Direct lamp light and its shadows stay dynamic in the game shader.

The image is stored as RGBM (gamma 2, range 8) in an 8-bit PNG packed in the file, so it also works on
the Web/Android export. node_bsdf_principled reads it through node_shader_gpu_lightmap (C), which looks
for the scene properties "ae_lightmap" (image name) and "ae_lightmap_use".
"""

import math

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty, StringProperty
from bpy.types import Operator
from mathutils import Matrix

UV_NAME = "Lightmap"
IMAGE_NAME = "AE_Lightmap"
VOLUME_IMAGE_NAME = "AE_LightVolume"
VOLUME_MAX_PROBES = 32  # per axis
NODE_NAME = "AE_lightmap_bake"
RGBM_RANGE = 8.0

# Cycles units -> game units, measured with a light-only DIFFUSE bake of a white plane:
# Sun strength 1 gives 1/pi, a point light with "Constant" falloff strength 1 gives 1/(4 pi^2),
# a uniform World of radiance 1 gives 1 (same as the game probe/World diffuse).
SUN_SCALE = math.pi
POINT_SCALE = 4.0 * math.pi * math.pi


def lightmap_objects(scene):
    """Static meshes that receive the lightmap. Moving things (rigid/dynamic bodies, objects with
    logic) keep the probe ambient, as do objects with the "ae_lightmap_exclude" property."""
    result = []
    for ob in scene.objects:
        if ob.type != 'MESH' or ob.hide_render or not ob.data.polygons:
            continue
        if not any(ob.layers[i] and scene.layers[i] for i in range(20)):
            continue
        if ob.game.physics_type not in {'STATIC', 'NO_COLLISION', 'OCCLUDER', 'NAVMESH'}:
            continue
        if ob.game.controllers or "ae_lightmap_exclude" in ob.game.properties or ob.get("ae_lightmap_exclude"):
            continue
        if not any(slot.material and slot.material.use_nodes for slot in ob.material_slots):
            continue
        result.append(ob)
    return result


def moving_objects(scene, static):
    """Meshes that move in the game (outside the lightmap): hidden while baking so they neither shadow
    the static scene nor tint the light volume, which lights them later."""
    return [ob for ob in scene.objects if ob.type == 'MESH' and not ob.hide_render and ob not in static and
            (ob.game.physics_type not in {'STATIC', 'NO_COLLISION', 'OCCLUDER', 'NAVMESH'} or ob.game.controllers)]


def volume_grid(objects, spacing):
    """Probe grid over the world bounds of the static meshes: (min, cell size, counts). Probe i sits at the
    cell center min + (i + 0.5) * cell, so the probes stay inside a room whose walls are the bounds."""
    import numpy as np
    lo = np.full(3, 1e30)
    hi = np.full(3, -1e30)
    for ob in objects:
        # from the vertices: bound_box is stale after make_lightmap_uvs rescales the mesh
        co = np.empty(len(ob.data.vertices) * 3, dtype=np.float64)
        ob.data.vertices.foreach_get("co", co)
        m = np.array(ob.matrix_world)
        w = co.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]
        lo = np.minimum(lo, w.min(axis=0))
        hi = np.maximum(hi, w.max(axis=0))
    lo, hi = lo.tolist(), hi.tolist()
    ext = [b - a for a, b in zip(lo, hi)]
    dims = [max(1, min(VOLUME_MAX_PROBES, int(math.ceil(e / spacing - 1e-3)))) for e in ext]
    cell = [max(e, 1e-3) / d for e, d in zip(ext, dims)]
    return lo, cell, dims


def fill_buried_probes(pixels, dims):
    """Probes inside a closed mesh (a sofa, a thick wall) see only back faces and bake black, which would
    darken objects passing near them. They take the average of their lit neighbors instead (in place)."""
    import numpy as np
    nx, ny, nz = dims
    # (k, j, face, i, rgb) -> (k, j, i, face, rgb)
    vol = pixels.reshape(nz, ny, 6, nx, 4)[..., :3].transpose(0, 1, 3, 2, 4).copy()
    lum = vol.max(axis=(3, 4))
    lit = lum > 0.05 * max(float(lum.mean()), 1e-6)
    for _ in range(max(dims)):
        if lit.all() or not lit.any():
            break
        acc = np.zeros_like(vol)
        cnt = np.zeros(lit.shape)
        for axis in range(3):
            for step in (-1, 1):
                src = np.roll(vol * lit[..., None, None], step, axis)
                n = np.roll(lit.astype(np.float64), step, axis)
                # no wrap-around at the grid border
                edge = [slice(None)] * 3
                edge[axis] = 0 if step == 1 else -1
                src[tuple(edge)] = 0.0
                n[tuple(edge)] = 0.0
                acc += src
                cnt += n
        grow = ~lit & (cnt > 0)
        vol[grow] = acc[grow] / cnt[grow][:, None, None]
        lit = lit | grow
    out = pixels.reshape(nz, ny, 6, nx, 4)
    out[..., :3] = vol.transpose(0, 1, 3, 2, 4)


def make_volume_mesh(scene, grid):
    """Temporary mesh: a 2 cm cube per probe whose six faces each cover one texel of the volume image
    (x = face * nx + i, y = k * ny + j, faces +X -X +Y -Y +Z -Z). A Cycles DIFFUSE bake of a face gives
    the irradiance from that direction: the ambient cube read by lightvol_sample (GLSL)."""
    from mathutils import Vector
    lo, cell, (nx, ny, nz) = grid
    width, height = nx * 6, ny * nz
    axes = (Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)))
    h = 0.01
    verts, faces, uvs = [], [], []
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                c = Vector([lo[a] + ((i, j, k)[a] + 0.5) * cell[a] for a in range(3)])
                for face in range(6):
                    a, s = face // 2, (1.0 if face % 2 == 0 else -1.0)
                    u, v = axes[(a + 1) % 3], axes[(a + 2) % 3]
                    if s < 0:
                        u, v = v, u
                    base = c + axes[a] * (s * h)
                    first = len(verts)
                    for du, dv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                        verts.append(base + (u * du + v * dv) * h)
                        uvs.append(((face * nx + i + 0.5 + 0.45 * du) / width,
                                    (k * ny + j + 0.5 + 0.45 * dv) / height))
                    faces.append((first, first + 1, first + 2, first + 3))
    me = bpy.data.meshes.new("AE_lightvol_probes")
    me.from_pydata(verts, [], faces)
    me.uv_textures.new(name=UV_NAME)
    uv = me.uv_layers[0].data
    for loop in me.loops:
        uv[loop.index].uv = uvs[loop.vertex_index]
    mat = bpy.data.materials.new("AE_lightvol_probes")
    mat.use_nodes = True
    me.materials.append(mat)
    ob = bpy.data.objects.new("AE_lightvol_probes", me)
    scene.objects.link(ob)
    ob.layers = scene.layers
    vis = ob.cycles_visibility
    vis.diffuse = vis.glossy = vis.transmission = vis.scatter = vis.shadow = False
    return ob, mat, (width, height)


def scale_matrix(scale):
    m = Matrix.Identity(4)
    for i in range(3):
        m[i][i] = scale[i] if abs(scale[i]) > 1e-6 else 1.0
    return m


def select_only(scene, objects):
    for ob in scene.objects:
        ob.select = False
    for ob in objects:
        ob.select = True
    scene.objects.active = objects[0]


def lightmap_scale(ob):
    """Per-object texel density multiplier (Object.ae_lightmap_scale, default 1)."""
    return max(0.01, float(getattr(ob, "ae_lightmap_scale", 1.0)))


def make_lightmap_uvs(scene, objects, size, margin_px=4):
    """Adds/refreshes the "Lightmap" UV layer and packs all objects in one atlas. Meshes shared by
    several objects are made single-user (each object needs its own place in the atlas)."""
    for ob in objects:
        if ob.data.users > 1:
            ob.data = ob.data.copy()
    for ob in objects:
        me = ob.data
        layer = me.uv_textures.get(UV_NAME) or me.uv_textures.new(name=UV_NAME)
        render = next((uv for uv in me.uv_textures if uv.active_render), None)
        me.uv_textures.active = layer
        if render is None or render == layer:
            # keep the material UV (first other layer) as the render one
            other = next((uv for uv in me.uv_textures if uv != layer), None)
            if other:
                other.active_render = True
        # the packer measures faces in mesh space: apply the object scale meanwhile so a stretched
        # wall gets as many texels per meter as a small box
        # (times the per-object lightmap scale, to give an object more or fewer texels)
        me.transform(scale_matrix(ob.scale * lightmap_scale(ob)))

    # margin in texels of the atlas: each chart is contracted by this on every side, so two charts are
    # 2*margin_px apart and the dilation after the bake has room without bleeding into the neighbour.
    # (the operator turns the percentage into a divisor of the packed size)
    margin_pct = min(1.0, max(0.3, 100.0 * margin_px / float(size)))
    select_only(scene, objects)
    bpy.ops.uv.lightmap_pack(PREF_CONTEXT='ALL_OBJECTS', PREF_PACK_IN_ONE=True, PREF_NEW_UVLAYER=False,
                             PREF_APPLY_IMAGE=False, PREF_IMG_PX_SIZE=size, PREF_BOX_DIV=12,
                             PREF_MARGIN_DIV=margin_pct)

    for ob in objects:
        ob.data.transform(scale_matrix(ob.scale * lightmap_scale(ob)).inverted())


def emulate_game_lamp(ob):
    """Temporary Cycles copy of a lamp that lights like the game shader (scene_light_dir): Sun = energy,
    Point/Spot = energy / (1 + att1 d/D + att2 d^2/D^2), built with Light Falloff + Math nodes."""
    la = ob.data.copy()
    la.use_nodes = True
    nt = la.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputLamp")
    emit = nt.nodes.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value = tuple(la.color) + (1.0,)
    nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    if la.type in {'SUN', 'HEMI'}:
        emit.inputs["Strength"].default_value = SUN_SCALE * la.energy
    else:
        def math_node(op, a, b):
            m = nt.nodes.new("ShaderNodeMath")
            m.operation = op
            for i, v in enumerate((a, b)):
                if isinstance(v, float):
                    m.inputs[i].default_value = v
                else:
                    nt.links.new(v, m.inputs[i])
            return m.outputs[0]

        dist = nt.nodes.new("ShaderNodeLightFalloff")
        dist.inputs["Strength"].default_value = 1.0
        dist.inputs["Smooth"].default_value = 0.0
        d = dist.outputs["Linear"]  # = distance with strength 1
        D = max(la.distance, 1e-4)
        att1 = la.linear_attenuation / D
        att2 = la.quadratic_attenuation / (D * D)
        q = math_node('ADD', math_node('ADD', math_node('MULTIPLY', d, att1),
                                       math_node('MULTIPLY', math_node('MULTIPLY', d, d), att2)), 1.0)
        falloff = nt.nodes.new("ShaderNodeLightFalloff")
        falloff.inputs["Smooth"].default_value = 0.0
        nt.links.new(math_node('DIVIDE', POINT_SCALE * la.energy, q), falloff.inputs["Strength"])
        nt.links.new(falloff.outputs["Constant"], emit.inputs["Strength"])
        la.shadow_soft_size = min(la.shadow_soft_size, 0.1)
    if la.use_negative:
        emit.inputs["Strength"].default_value = 0.0
    original = ob.data
    ob.data = la
    return original, la


def use_gpu_device(scene):
    """Bakes on the GPU when Cycles finds one (CUDA first, then OpenCL); returns the old setting so it
    can be put back. Without a GPU the bake stays on the CPU."""
    import _cycles
    addon = bpy.context.user_preferences.addons.get("cycles")
    if addon is None:
        return None
    prefs = addon.preferences
    old = (prefs.compute_device_type, scene.cycles.device)
    for kind in ('CUDA', 'OPENCL'):
        if any(d[1] == kind for d in _cycles.available_devices(kind)):
            prefs.compute_device_type = kind
            prefs.get_devices()
            gpus = [d for d in prefs.devices if d.type == kind]
            # with a dedicated card, leave out the integrated one ("... Graphics"): it slows the bake down
            dedicated = [d for d in gpus if not d.name.endswith("Graphics")]
            for d in prefs.devices:
                d.use = d in (dedicated or gpus)
            scene.cycles.device = 'GPU'
            return old
    return old


def oidn_library():
    """ae_denoise (Intel Open Image Denoise wrapper, source/intern/ae_denoise) next to the executable, or None."""
    import ctypes
    import os
    import sys
    name = "ae_denoise.dll" if sys.platform == "win32" else "libae_denoise.so"
    path = os.path.join(os.path.dirname(bpy.app.binary_path), name)
    if not os.path.isfile(path):
        return None
    try:
        lib = ctypes.CDLL(path)
    except OSError:
        return None
    lib.ae_denoise.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_int)
    return lib


def denoise_oidn(lib, pixels, mask, size):
    """AI denoise of the whole atlas; texels outside the charts keep their value (masked out later)."""
    import numpy as np
    rgb = np.ascontiguousarray(pixels.reshape(size, size, 4)[..., :3], dtype=np.float32)
    if lib.ae_denoise(rgb.ctypes.data, size, size) != 0:
        return None
    out = pixels.reshape(size, size, 4).copy()
    inside = mask.reshape(size, size) > 0.5
    out[inside, :3] = rgb[inside]
    return out.reshape(-1, 4)


def denoise(pixels, mask, size, radius=1, passes=2):
    """Masked box blur: averages only texels of baked charts, so the light of one wall never leaks into the
    chart next to it on the atlas. Cheap stand-in until OIDN is wired in."""
    import numpy as np
    rgb = pixels.reshape(size, size, 4)[..., :3].copy()
    w = (mask.reshape(size, size) > 0.5).astype(np.float32)
    for _ in range(passes):
        acc = np.zeros_like(rgb)
        cnt = np.zeros_like(w)
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                sw = np.roll(np.roll(w, dy, 0), dx, 1)
                acc += np.roll(np.roll(rgb * w[..., None], dy, 0), dx, 1)
                cnt += sw
        rgb = np.where(cnt[..., None] > 0, acc / np.maximum(cnt, 1e-6)[..., None], rgb)
    out = pixels.reshape(size, size, 4).copy()
    out[..., :3] = rgb
    return out.reshape(-1, 4)


def dilate(pixels, mask, size, passes, keep_empty=None):
    """Edge padding: grows the baked charts outward texel by texel (each new texel = mean of its valid
    8-neighbours), so bilinear filtering and mipmaps at chart borders read lit texels instead of black.
    Returns (pixels, mask) with the grown texels marked valid."""
    import numpy as np
    rgb = pixels.reshape(size, size, 4)[..., :3].copy()
    valid = mask.reshape(size, size) > 0.5
    blocked = keep_empty.reshape(size, size) if keep_empty is not None else np.zeros_like(valid)
    offsets = [(dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx]
    for _ in range(passes):
        w = valid.astype(np.float32)
        pad_w = np.pad(w, 1)
        pad_c = np.pad(rgb * w[..., None], ((1, 1), (1, 1), (0, 0)))
        acc = np.zeros_like(rgb)
        cnt = np.zeros_like(w)
        for dy, dx in offsets:
            acc += pad_c[1 + dy:1 + dy + size, 1 + dx:1 + dx + size]
            cnt += pad_w[1 + dy:1 + dy + size, 1 + dx:1 + dx + size]
        grow = (~valid) & (cnt > 0) & (~blocked)
        if not grow.any():
            break
        rgb[grow] = acc[grow] / cnt[grow][:, None]
        valid = valid | grow
    out = pixels.reshape(size, size, 4).copy()
    out[..., :3] = rgb
    out[..., 3] = valid
    return out.reshape(-1, 4), valid.reshape(-1).astype(np.float32)


def bake_progress(percent, status):
    """Bar in the Info header (drawn by INFO_HT_header). The bake blocks the UI, so the window is
    redrawn by hand at each step; status "" hides the bar."""
    wm = bpy.context.window_manager
    wm.ae_bake_progress = percent
    wm.ae_bake_status = status
    if bpy.app.background:
        return
    if status:
        print("AE lightmap: %3d%% %s" % (percent, status))
    try:
        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
    except RuntimeError:
        pass


def encode_rgbm(pixels, alpha_mask):
    """Linear irradiance -> RGBM (gamma 2, range 8). Texels outside the charts get alpha 0."""
    import numpy as np
    px = pixels.reshape(-1, 4)
    g = np.sqrt(np.clip(px[:, :3], 0.0, RGBM_RANGE * RGBM_RANGE)) / RGBM_RANGE
    a = np.clip(np.ceil(g.max(axis=1) * 255.0) / 255.0, 1.0 / 255.0, 1.0)
    out = np.empty_like(px)
    out[:, :3] = g / a[:, None]
    out[:, 3] = np.where(alpha_mask > 0.5, a, 0.0)
    out[alpha_mask <= 0.5, :3] = 0.0
    return out


class SCENE_OT_lightmap_bake(Operator):
    """Bake the indirect light of the static meshes into one lightmap (Cycles), used by the """ \
        """Game PBR materials instead of the probe/World ambient"""
    bl_idname = "scene.ae_lightmap_bake"
    bl_label = "Bake Lightmap"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene and context.mode == 'OBJECT'

    def execute(self, context):
        import numpy as np
        scene = context.scene
        settings = scene.ae_lightmap_settings
        objects = lightmap_objects(scene)
        if not objects:
            self.report({'WARNING'}, "No static mesh with a node material to bake")
            return {'CANCELLED'}
        import addon_utils
        addon_utils.enable("cycles", default_set=False)

        bake_progress(2, "Lightmap UVs")
        # objects created or moved by a script are only placed where Cycles sees them after an update
        scene.update()
        size = int(settings.resolution)
        make_lightmap_uvs(scene, objects, size, max(2, settings.margin))

        materials = {slot.material for ob in objects for slot in ob.material_slots
                     if slot.material and slot.material.use_nodes}
        added = []
        for mat in materials:
            node = mat.node_tree.nodes.new("ShaderNodeTexImage")
            node.name = NODE_NAME
            added.append((mat, node, mat.node_tree.nodes.active))
            mat.node_tree.nodes.active = node

        render = scene.render
        old = (render.engine, scene.cycles.samples if hasattr(scene, "cycles") else 0)
        render.engine = 'CYCLES'
        scene.cycles.samples = settings.samples
        scene.cycles.max_bounces = max(scene.cycles.max_bounces, 4)
        scene.cycles.diffuse_bounces = max(scene.cycles.diffuse_bounces, 4)
        old_device = use_gpu_device(scene) if settings.use_gpu else None
        lamps = [ob for ob in scene.objects if ob.type == 'LAMP' and not ob.hide_render]
        hidden = moving_objects(scene, objects)
        swapped = []
        probe_ob = probe_mat = probe_target = None
        volume_passes = []
        try:
            for ob in hidden:
                ob.hide_render = True
            if settings.use_volume:
                grid = volume_grid(objects, settings.volume_spacing)
                probe_ob, probe_mat, probe_size = make_volume_mesh(scene, grid)
                node = probe_mat.node_tree.nodes.new("ShaderNodeTexImage")
                probe_mat.node_tree.nodes.active = node
                probe_target = ([probe_ob], [(probe_mat, node, None)], probe_size, 0,
                                max(settings.samples * 32, 512))  # few texels: cheap
                scene.update()

            def bake_target(passes, target, percent, status):
                bake_progress(percent, status)
                targets, nodes, (width, height), margin, samples = target
                select_only(scene, targets)
                scene.cycles.samples = samples
                # a fresh transparent image per pass: rewriting .pixels of the bake target makes Cycles
                # bake into a stale buffer; alpha stays 0 where no chart was baked
                work = bpy.data.images.new("AE_lightmap_work", width, height, alpha=True, float_buffer=True)
                work.generated_color = (0.0, 0.0, 0.0, 0.0)
                for mat, node, active in nodes:
                    node.image = work
                bpy.ops.object.bake(type='DIFFUSE', pass_filter=passes, margin=margin,
                                    use_clear=False)  # the active UV layer is "Lightmap"
                result = np.array(work.pixels[:], dtype=np.float32)
                for mat, node, active in nodes:
                    node.image = None
                bpy.data.images.remove(work)
                return result

            lightmap_target = (objects, added, (size, size), settings.margin, settings.samples)

            def bake(passes, percent, status):
                # the light volume gets the same passes (same lamps), so moving objects match the lightmap
                if probe_target:
                    volume_passes.append(bake_target(passes, probe_target, percent, status + " (light volume)"))
                    percent += 10
                return bake_target(passes, lightmap_target, percent, status)

            # 1. bounces of the game lamps
            for ob in lamps:
                swapped.append((ob, ) + emulate_game_lamp(ob))
            indirect = bake({'INDIRECT'}, 8, "Baking lamp bounces")
            for ob, original, temp in swapped:
                ob.data = original
                bpy.data.lamps.remove(temp)
            swapped = []
            # 2. World and emissive meshes, direct (the game lamps stay live)
            for ob in lamps:
                ob.hide_render = True
            direct = (bake({'DIRECT'}, 45, "Baking World light") if settings.use_world
                      else np.zeros_like(indirect))
            for ob in lamps:
                ob.hide_render = False

            total = indirect.reshape(-1, 4).copy()
            total[:, :3] += direct.reshape(-1, 4)[:, :3]
            mask = total[:, 3].copy()
            # (0,0) and the wrapped corners stay empty: meshes without the UV layer read there
            corners = np.zeros((size, size), dtype=bool)
            corners[:2, :2] = corners[:2, -2:] = corners[-2:, :2] = corners[-2:, -2:] = True
            mask[corners.reshape(-1)] = 0.0
            # fill the gutters before denoising so OIDN does not pull black into the chart borders
            bake_progress(80, "Denoising" if settings.use_denoise else "Filling margins")
            pad = max(4, settings.margin * 2)
            total[mask <= 0.5, :3] = 0.0
            total, grown = dilate(total, mask, size, pad, corners)
            if settings.use_denoise:
                lib = oidn_library()
                result = denoise_oidn(lib, total, mask, size) if lib else None
                total = result if result is not None else denoise(total, mask, size)
                print("AE lightmap: denoise", "OIDN" if result is not None else "box blur")
            # denoise only trusted the charts: rebuild the padding from the denoised chart texels
            total[mask <= 0.5, :3] = 0.0
            total, mask = dilate(total, mask, size, pad, corners)
            encoded = encode_rgbm(total, mask)
            if probe_target:
                vol = volume_passes[0].reshape(-1, 4).copy()
                for extra in volume_passes[1:]:
                    vol[:, :3] += extra.reshape(-1, 4)[:, :3]
                fill_buried_probes(vol, grid[2])
                volume_encoded = encode_rgbm(vol, np.ones(len(vol), dtype=np.float32))
        finally:
            bake_progress(0, "")
            for ob in hidden:
                ob.hide_render = False
            if probe_ob:
                me = probe_ob.data
                bpy.data.objects.remove(probe_ob)
                bpy.data.meshes.remove(me)
                bpy.data.materials.remove(probe_mat)
            for ob, original, temp in swapped:
                ob.data = original
                bpy.data.lamps.remove(temp)
            for ob in lamps:
                ob.hide_render = False
            for mat, node, active in added:
                mat.node_tree.nodes.remove(node)
                if active:
                    mat.node_tree.nodes.active = active
            if old_device:
                bpy.context.user_preferences.addons["cycles"].preferences.compute_device_type = old_device[0]
                scene.cycles.device = old_device[1]
            render.engine = old[0]
            scene.cycles.samples = old[1] or scene.cycles.samples

        image = bpy.data.images.get(scene.ae_lightmap) or bpy.data.images.get(IMAGE_NAME)
        if image and (image.size[0] != size or image.size[1] != size):
            bpy.data.images.remove(image)
            image = None
        if image is None:
            image = bpy.data.images.new(IMAGE_NAME, size, size, alpha=True)
        image.colorspace_settings.name = 'Non-Color'
        image.alpha_mode = 'STRAIGHT'
        image.use_alpha = True
        image.pixels = encoded.reshape(-1).tolist()
        image.pack(as_png=True)
        image.use_fake_user = True

        scene.ae_lightmap = image.name
        scene.ae_lightmap_use = True

        if probe_target:
            width, height = probe_size
            vimage = bpy.data.images.get(scene.ae_lightvol) or bpy.data.images.get(VOLUME_IMAGE_NAME)
            if vimage and tuple(vimage.size) != (width, height):
                bpy.data.images.remove(vimage)
                vimage = None
            if vimage is None:
                vimage = bpy.data.images.new(VOLUME_IMAGE_NAME, width, height, alpha=True)
            vimage.colorspace_settings.name = 'Non-Color'
            vimage.alpha_mode = 'STRAIGHT'
            vimage.use_alpha = True
            vimage.pixels = volume_encoded.reshape(-1).tolist()
            vimage.pack(as_png=True)
            vimage.use_fake_user = True
            scene.ae_lightvol = vimage.name
            scene.ae_lightvol_grid = list(grid[0]) + list(grid[1]) + [float(d) for d in grid[2]]
            scene.ae_lightvol_use = True
            print("AE lightmap: light volume %dx%dx%d probes" % tuple(grid[2]))
        # recompile the game materials with the new texture
        for mat in materials:
            mat.update_tag()
        self.report({'INFO'}, "Lightmap baked: %d objects, %dx%d" % (len(objects), size, size))
        return {'FINISHED'}


class SCENE_OT_lightmap_clear(Operator):
    """Remove the baked lightmap (image and "Lightmap" UV layers); materials go back to the probe/World """ \
        """ambient"""
    bl_idname = "scene.ae_lightmap_clear"
    bl_label = "Clear Lightmap"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        image = bpy.data.images.get(scene.ae_lightmap)
        if image:
            image.use_fake_user = False
            if image.users == 0:
                bpy.data.images.remove(image)
        for ob in scene.objects:
            if ob.type == 'MESH':
                layer = ob.data.uv_textures.get(UV_NAME)
                if layer:
                    ob.data.uv_textures.remove(layer)
        scene.ae_lightmap = ""
        scene.ae_lightmap_use = False
        vimage = bpy.data.images.get(scene.ae_lightvol)
        if vimage:
            vimage.use_fake_user = False
            if vimage.users == 0:
                bpy.data.images.remove(vimage)
        scene.ae_lightvol = ""
        scene.ae_lightvol_use = False
        return {'FINISHED'}


class AnastacioLightmapSettings(bpy.types.PropertyGroup):
    resolution: EnumProperty(
        name="Resolution",
        description="Size of the lightmap atlas (one texture for the whole scene)",
        items=(('256', "256", ""), ('512', "512", ""), ('1024', "1024", ""), ('2048', "2048", ""), ('4096', "4096", "")),
        default='1024')
    use_denoise: BoolProperty(
        name="Denoise", description="Smooth the bake noise inside each chart (lets you bake with few samples)",
        default=True)
    use_gpu: BoolProperty(
        name="GPU", description="Bake on the graphics card (CUDA/OpenCL) when Cycles finds one, much faster "
        "than the CPU", default=True)
    samples: IntProperty(
        name="Samples", description="Cycles samples per texel (more = less noise, slower bake)",
        default=80, min=8, max=8192)
    margin: IntProperty(
        name="Margin", description="Pixels the baked charts are extended by (avoids dark seams)",
        default=4, min=0, max=32)
    use_world: BoolProperty(
        name="World Light",
        description="Also bake the sky/World and emissive meshes (the lightmap replaces the probe/World "
                    "diffuse in the game)",
        default=True)
    use_volume: BoolProperty(
        name="Light Volume",
        description="Also bake a grid of light probes that lights the moving objects (outside the lightmap) "
                    "with the same bounced light",
        default=True)
    volume_spacing: FloatProperty(
        name="Probe Spacing", description="Distance between the light volume probes",
        default=1.0, min=0.1, max=100.0, subtype='DISTANCE', unit='LENGTH')


classes = (
    AnastacioLightmapSettings,
    SCENE_OT_lightmap_bake,
    SCENE_OT_lightmap_clear,
)


def register_props():
    bpy.types.Object.ae_lightmap_scale = FloatProperty(
        name="Lightmap Scale",
        description="Texel density of this object in the lightmap atlas (2 = twice as sharp, 0.5 = half)",
        default=1.0, min=0.05, max=16.0, soft_min=0.1, soft_max=8.0)
    bpy.types.Scene.ae_lightmap_settings = bpy.props.PointerProperty(type=AnastacioLightmapSettings)
    # Plain scene properties: read by name from C (node_shader_gpu_lightmap).
    bpy.types.Scene.ae_lightmap = StringProperty(
        name="Lightmap Image", description="Baked lightmap atlas used by the Game PBR materials")
    bpy.types.Scene.ae_lightmap_use = BoolProperty(
        name="Use Lightmap",
        description="Light the static meshes with the baked lightmap (works on Desktop, Web and Android)",
        default=False)
    bpy.types.Scene.ae_lightvol = StringProperty(
        name="Light Volume Image", description="Baked light volume (ambient cube per probe) for moving objects")
    bpy.types.Scene.ae_lightvol_use = BoolProperty(
        name="Use Light Volume",
        description="Light the moving objects with the baked light volume (6 texture reads per pixel)",
        default=False)
    bpy.types.WindowManager.ae_bake_progress = FloatProperty(
        name="Bake Progress", subtype='PERCENTAGE', min=0.0, max=100.0, options={'SKIP_SAVE'})
    bpy.types.WindowManager.ae_bake_status = StringProperty(options={'SKIP_SAVE'})
    bpy.types.Scene.ae_lightvol_grid = FloatVectorProperty(
        name="Light Volume Grid", description="Minimum xyz, cell size xyz and probe counts xyz",
        size=9, options={'HIDDEN'})


def unregister_props():
    del bpy.types.WindowManager.ae_bake_status
    del bpy.types.WindowManager.ae_bake_progress
    del bpy.types.Object.ae_lightmap_scale
    del bpy.types.Scene.ae_lightvol_grid
    del bpy.types.Scene.ae_lightvol_use
    del bpy.types.Scene.ae_lightvol
    del bpy.types.Scene.ae_lightmap_use
    del bpy.types.Scene.ae_lightmap
    del bpy.types.Scene.ae_lightmap_settings
