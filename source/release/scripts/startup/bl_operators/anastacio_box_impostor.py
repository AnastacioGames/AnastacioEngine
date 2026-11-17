# Impostor de Caixa (docs/plano-imposter-caixa.md), Etapa 2: bake das 6 vistas.
#
# The object is framed by a cube (in "meters": local coordinates times the object scale, the same
# convention as surface(uv).position of the GLSL @surface node). Each of the 6 faces of the cube is
# one orthographic view, stored in a 3x2 atlas cell (view i -> column i % 3, row i // 3):
#   0 +X  1 -X  2 +Y  3 -Y  4 +Z  5 -Z   (the camera sits on that side, looking inward)
# Cell UV (u, v) maps to the point  center + (2u-1)*half*U + (2v-1)*half*V  on the face, with the
# per-view axes U, V below (U x V = face normal, so the camera's right is U and its up is V).
#
# <obj>_imp_color: RGBA albedo without lighting (Blender Internal render, materials shadeless).
# <obj>_imp_data:  RGB = normal in the object's axes (meters) * 0.5 + 0.5, A = depth from the face
#                  inward / cube size (0 = on the face, 1 = opposite face; 1 where nothing is hit).
#                  Non-Color.
# Depth and normal come from ray casts against the evaluated mesh (no compositor passes).

import math
import os

import bpy
from bpy.props import EnumProperty
from bpy.types import Operator
from mathutils import Matrix, Vector

VIEWS = (
    # face normal,  U axis,       V axis
    ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
    ((-1, 0, 0), (0, -1, 0), (0, 0, 1)),
    ((0, 1, 0), (-1, 0, 0), (0, 0, 1)),
    ((0, -1, 0), (1, 0, 0), (0, 0, 1)),
    ((0, 0, 1), (1, 0, 0), (0, 1, 0)),
    ((0, 0, -1), (1, 0, 0), (0, -1, 0)),
)
COLS, ROWS = 3, 2


def _cube(ob, sca):
    """Center and half size of the framing cube, in meters (local * scale)."""
    pts = [Vector((c[0] * sca.x, c[1] * sca.y, c[2] * sca.z)) for c in ob.bound_box]
    lo = Vector((min(p[i] for p in pts) for i in range(3)))
    hi = Vector((max(p[i] for p in pts) for i in range(3)))
    center = (lo + hi) * 0.5
    half = max(max((hi - lo)) * 0.5, 1e-4) * 1.02
    return center, half


def _bvh(ob):
    import bmesh
    from mathutils.bvhtree import BVHTree
    me = ob.to_mesh(bpy.context.scene, True, 'PREVIEW')
    try:
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.faces.ensure_lookup_table()
        bvh = BVHTree.FromBMesh(bm)
        # Per face: flat normal, or the corner positions/normals for smooth interpolation.
        faces = []
        for f in bm.faces:
            if f.smooth:
                faces.append(([v.co.copy() for v in f.verts], [v.normal.copy() for v in f.verts]))
            else:
                faces.append((None, f.normal.copy()))
        bm.free()
    finally:
        bpy.data.meshes.remove(me)
    return bvh, faces


def _hit_normal(faces, index, point):
    cos, nor = faces[index]
    if cos is None:
        return nor
    try:
        from mathutils.interpolate import poly_3d_calc
        w = poly_3d_calc(cos, point)
        n = Vector((0.0, 0.0, 0.0))
        for wi, ni in zip(w, nor):
            n += ni * wi
        return n if n.length > 1e-8 else nor[0]
    except (ImportError, ValueError):
        return nor[0]


def bake_data(ob, res):
    """Data atlas as a numpy float array (rows, cols, 4), plus (center, half) in meters."""
    import numpy as np
    sca = ob.matrix_world.decompose()[2]
    center, half = _cube(ob, sca)
    bvh, faces = _bvh(ob)
    inv = Vector((1.0 / sca.x if sca.x else 0.0, 1.0 / sca.y if sca.y else 0.0,
                  1.0 / sca.z if sca.z else 0.0))
    atlas = np.zeros((res * ROWS, res * COLS, 4), np.float32)
    atlas[..., 0:3] = 0.5
    atlas[..., 3] = 1.0
    size = 2.0 * half
    for i, (n, u, v) in enumerate(VIEWS):
        n, u, v = Vector(n), Vector(u), Vector(v)
        face = center + n * half
        d_m = -n
        d_l = Vector((d_m.x * inv.x, d_m.y * inv.y, d_m.z * inv.z))
        if d_l.length < 1e-12:
            continue
        d_l.normalize()
        x0, y0 = (i % COLS) * res, (i // COLS) * res
        for py in range(res):
            fv = (2.0 * (py + 0.5) / res - 1.0) * half
            for px in range(res):
                fu = (2.0 * (px + 0.5) / res - 1.0) * half
                o_m = face + u * fu + v * fv + n * (half * 0.01)
                o_l = Vector((o_m.x * inv.x, o_m.y * inv.y, o_m.z * inv.z))
                hit, nor, index, _dist = bvh.ray_cast(o_l, d_l)
                if hit is None:
                    continue
                hit_m = Vector((hit.x * sca.x, hit.y * sca.y, hit.z * sca.z))
                depth = (face - hit_m).dot(n) / size
                nl = _hit_normal(faces, index, hit)
                # Normal from local to meters: inverse-transpose of the scale.
                nm = Vector((nl.x * inv.x, nl.y * inv.y, nl.z * inv.z))
                nm = nm.normalized() if nm.length > 1e-12 else n
                atlas[y0 + py, x0 + px] = (nm.x * 0.5 + 0.5, nm.y * 0.5 + 0.5, nm.z * 0.5 + 0.5,
                                           min(max(depth, 0.0), 1.0))
    return atlas, center, half


def bake_color(ob, res, center, half, workdir):
    """Color atlas (rows, cols, 4) from 6 shadeless orthographic Blender Internal renders."""
    import numpy as np
    scene = bpy.context.scene
    loc, rot, sca = ob.matrix_world.decompose()
    rot_m = rot.to_matrix()

    def to_world(p_m):
        return loc + rot_m * p_m

    cam_data = bpy.data.cameras.new("_BoxImpostorCam")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = 2.0 * half
    cam_data.clip_start = half * 0.001
    cam_data.clip_end = half * 4.0
    cam = bpy.data.objects.new("_BoxImpostorCam", cam_data)
    scene.objects.link(cam)

    r = scene.render
    vs = scene.view_settings
    saved = {
        "camera": scene.camera, "engine": r.engine, "rx": r.resolution_x, "ry": r.resolution_y,
        "pct": r.resolution_percentage, "alpha": r.alpha_mode, "path": r.filepath,
        "fmt": r.image_settings.file_format, "mode": r.image_settings.color_mode,
        "vt": vs.view_transform, "look": vs.look, "exp": vs.exposure, "gamma": vs.gamma,
        "curve": vs.use_curve_mapping,
    }
    hidden = [(o, o.hide_render) for o in scene.objects if o not in (ob, cam)]
    mats = [s.material for s in ob.material_slots if s.material]
    shadeless = [(m, m.use_shadeless) for m in mats]
    atlas = np.zeros((res * ROWS, res * COLS, 4), np.float32)
    try:
        for o, _ in hidden:
            o.hide_render = True
        for m in mats:
            m.use_shadeless = True
        r.engine = 'BLENDER_RENDER'
        r.resolution_x = r.resolution_y = res
        r.resolution_percentage = 100
        r.alpha_mode = 'TRANSPARENT'
        r.image_settings.file_format = 'PNG'
        r.image_settings.color_mode = 'RGBA'
        vs.view_transform = 'Default'
        vs.look = 'None'
        vs.exposure = 0.0
        vs.gamma = 1.0
        vs.use_curve_mapping = False
        scene.camera = cam
        for i, (n, u, v) in enumerate(VIEWS):
            n, u, v = Vector(n), Vector(u), Vector(v)
            basis = Matrix((u, v, n)).transposed()
            cam.matrix_world = Matrix.Translation(to_world(center + n * (half * 2.0))) * \
                (rot_m * basis).to_4x4()
            path = os.path.join(workdir, "_box_impostor_view%d.png" % i)
            r.filepath = path
            bpy.ops.render.render(write_still=True)
            img = bpy.data.images.load(path)
            try:
                px = np.array(img.pixels[:], np.float32).reshape(res, res, 4)
            finally:
                bpy.data.images.remove(img)
            try:
                os.remove(path)
            except OSError:
                pass
            x0, y0 = (i % COLS) * res, (i // COLS) * res
            atlas[y0:y0 + res, x0:x0 + res] = px
    finally:
        for o, h in hidden:
            o.hide_render = h
        for m, s in shadeless:
            m.use_shadeless = s
        scene.camera = saved["camera"]
        r.engine = saved["engine"]
        r.resolution_x, r.resolution_y = saved["rx"], saved["ry"]
        r.resolution_percentage = saved["pct"]
        r.alpha_mode = saved["alpha"]
        r.filepath = saved["path"]
        r.image_settings.file_format = saved["fmt"]
        r.image_settings.color_mode = saved["mode"]
        vs.view_transform = saved["vt"]
        vs.look = saved["look"]
        vs.exposure = saved["exp"]
        vs.gamma = saved["gamma"]
        vs.use_curve_mapping = saved["curve"]
        scene.objects.unlink(cam)
        bpy.data.objects.remove(cam)
        bpy.data.cameras.remove(cam_data)
    return atlas


def _store_image(name, atlas, non_color):
    h, w = atlas.shape[0], atlas.shape[1]
    image = bpy.data.images.get(name)
    if image is not None and tuple(image.size) != (w, h):
        bpy.data.images.remove(image)
        image = None
    if image is None:
        image = bpy.data.images.new(name, w, h, alpha=True)
    if non_color:
        image.colorspace_settings.name = 'Non-Color'
    image.pixels[:] = atlas.ravel().tolist()
    image.pack(as_png=True)
    return image


def _card(ob, center, half):
    """Quad on the local XZ plane (the Billboard node's convention) covering the cube from any side."""
    name = ob.name + "_box_impostor"
    r = half * math.sqrt(3.0)
    verts = [(-r, 0.0, -r), (r, 0.0, -r), (r, 0.0, r), (-r, 0.0, r)]
    card = bpy.data.objects.get(name)
    if card is not None and card.type == 'MESH':
        me = card.data
        me.clear_geometry()
    else:
        me = bpy.data.meshes.new(name)
        card = bpy.data.objects.new(name, me)
        bpy.context.scene.objects.link(card)
    me.from_pydata(verts, [], [(0, 1, 2, 3)])
    me.update()
    loc, rot, _sca = ob.matrix_world.decompose()
    card.matrix_world = Matrix.Translation(loc + rot.to_matrix() * center) * rot.to_matrix().to_4x4()
    card["box_impostor_half"] = half
    card["box_impostor_source"] = ob.name
    return card


class OBJECT_OT_bake_box_impostor(Operator):
    """Bake 6 orthographic views (albedo, normal, depth) of the active mesh into two atlases and """ \
        """create a camera-facing card for the Box Impostor"""
    bl_idname = "object.bake_box_impostor"
    bl_label = "Bake Box Impostor"
    bl_options = {'REGISTER', 'UNDO'}

    resolution: EnumProperty(
        name="Resolution", description="Size of each of the 6 views in pixels",
        items=(('64', "64", ""), ('128', "128", ""), ('256', "256", ""), ('512', "512", "")),
        default='256')

    @classmethod
    def poll(cls, context):
        ob = context.object
        return ob is not None and ob.type == 'MESH'

    def execute(self, context):
        import time
        ob = context.object
        if not ob.data.polygons:
            self.report({'ERROR'}, "The object has no faces")
            return {'CANCELLED'}
        res = int(self.resolution)
        workdir = bpy.app.tempdir or os.path.dirname(bpy.data.filepath) or "."
        t0 = time.time()
        data, center, half = bake_data(ob, res)
        color = bake_color(ob, res, center, half, workdir)
        _store_image(ob.name + "_imp_color", color, False)
        _store_image(ob.name + "_imp_data", data, True)
        card = _card(ob, center, half)
        self.report({'INFO'}, "Box Impostor: %s, %d px per view, %.1f s" % (card.name, res, time.time() - t0))
        return {'FINISHED'}


classes = (OBJECT_OT_bake_box_impostor,)
