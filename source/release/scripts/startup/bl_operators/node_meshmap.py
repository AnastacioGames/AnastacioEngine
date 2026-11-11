# Bake of the "@param <name>: meshmap(<kind>)" maps of a GLSL Script node from the active object:
# ao, curvature, thickness, normal (object space) and position (bounding box). See docs/shader-nodes.md.

import bpy
import math
import re
from bpy.types import Operator, Panel
from bpy.props import EnumProperty, StringProperty

_MESHMAP_RE = re.compile(r"^\s*//\s*@param\s+(\w+)\s*:\s*meshmap\s*\(\s*(\w+)\s*\)")
KINDS = ("ao", "curvature", "thickness", "normal", "position")
SIZES = (('128', "128", ""), ('256', "256", ""), ('512', "512", ""), ('1024', "1024", ""))
RAYS = 24
PADDING = 4


def meshmap_params(node):
    """(name, kind) of the meshmap params in the header of a GLSL Script node."""
    text = getattr(node, "script", None)
    if node is None or node.bl_idname != "ShaderNodeGLSLScript" or text is None:
        return []
    found = []
    for line in text.as_string().splitlines():
        s = line.strip()
        if s and not s.startswith("//"):
            break
        m = _MESHMAP_RE.match(s)
        if m and m.group(2) in KINDS:
            found.append((m.group(1), m.group(2)))
    return found


def _directions(n):
    """n directions spread over the sphere (Fibonacci)."""
    out = []
    golden = math.pi * (3.0 - math.sqrt(5.0))
    for i in range(n):
        z = 1.0 - 2.0 * (i + 0.5) / n
        r = math.sqrt(max(0.0, 1.0 - z * z))
        a = golden * i
        out.append((math.cos(a) * r, math.sin(a) * r, z))
    return out


def _mesh_data(ob):
    """Triangles in UV with position, normal and vertex curvature, plus the BVH of the mesh."""
    import bmesh
    from mathutils.bvhtree import BVHTree
    if ob.mode == 'EDIT':
        ob.update_from_editmode()  # bake the current edit (and a fresh unwrap), not the last saved mesh
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    uv = bm.loops.layers.uv.active
    if uv is None:
        bm.free()
        raise ValueError("'%s' has no UV map" % ob.name)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bm.verts.ensure_lookup_table()
    bm.normal_update()
    # Curvature per vertex: how much the neighbours fall below (convex) or above (concave) its plane.
    curv = []
    for v in bm.verts:
        acc, cnt = 0.0, 0
        for e in v.link_edges:
            d = e.other_vert(v).co - v.co
            if d.length > 1e-9:
                acc += -v.normal.dot(d.normalized())
                cnt += 1
        curv.append(acc / cnt if cnt else 0.0)
    tris = []
    for f in bm.faces:
        ls = f.loops
        tris.append(([tuple(l[uv].uv) for l in ls], [tuple(l.vert.co) for l in ls],
                     [tuple(l.vert.normal if f.smooth else f.normal) for l in ls],
                     [curv[l.vert.index] for l in ls]))
    bvh = BVHTree.FromBMesh(bm)
    lo = [min(v.co[i] for v in bm.verts) for i in range(3)]
    hi = [max(v.co[i] for v in bm.verts) for i in range(3)]
    bm.free()
    return tris, bvh, lo, hi


def _rasterize(tris, size):
    """Per texel (y, x): position, normal and curvature interpolated in the triangle that covers it."""
    import numpy as np
    pos = np.zeros((size, size, 3), np.float32)
    nor = np.zeros((size, size, 3), np.float32)
    cur = np.zeros((size, size), np.float32)
    mask = np.zeros((size, size), bool)
    for uvs, cos, nos, cus in tris:
        p = np.array(uvs, np.float64) * size - 0.5
        x0, y0 = np.floor(p.min(axis=0)).astype(int)
        x1, y1 = np.ceil(p.max(axis=0)).astype(int)
        x0, y0 = max(x0, 0), max(y0, 0)
        x1, y1 = min(x1, size - 1), min(y1, size - 1)
        if x1 < x0 or y1 < y0:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
        (ax, ay), (bx, by), (cx, cy) = p
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-12:
            continue
        w0 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / den
        w1 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / den
        w2 = 1.0 - w0 - w1
        inside = (w0 >= -1e-4) & (w1 >= -1e-4) & (w2 >= -1e-4)
        if not inside.any():
            continue
        yy, xx = ys[inside], xs[inside]
        w = np.stack([w0[inside], w1[inside], w2[inside]], axis=1)
        pos[yy, xx] = w @ np.array(cos)
        n = w @ np.array(nos)
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
        nor[yy, xx] = n
        cur[yy, xx] = w @ np.array(cus)
        mask[yy, xx] = True
    return pos, nor, cur, mask


def _rays(pos, nor, mask, bvh, dist, inward):
    """Per texel: AO (share of rays that leave the mesh) or thickness (mean inner hit distance)."""
    import numpy as np
    from mathutils import Vector
    dirs = [Vector(d) for d in _directions(RAYS)]
    out = np.zeros(mask.shape, np.float32)
    eps = dist * 1e-3
    for y, x in zip(*np.nonzero(mask)):
        n = Vector(nor[y, x])
        if inward:
            n = -n
        o = Vector(pos[y, x]) + n * eps
        acc, cnt = 0.0, 0
        for d in dirs:
            c = d.dot(n)
            if c <= 0.0:
                d, c = -d, -c
            hit = bvh.ray_cast(o, d, dist)[0]
            if inward:
                acc += ((hit - o).length if hit is not None else dist)
            else:
                acc += c if hit is None else 0.0
            cnt += c if not inward else 1
        out[y, x] = acc / max(cnt, 1e-9) if not inward else (acc / cnt) / dist
    return out


def _dilate(img, mask, steps):
    """Grows the islands a few texels so filtering at the UV seams does not read the background."""
    import numpy as np
    img, mask = img.copy(), mask.copy()
    for _ in range(steps):
        acc = np.zeros_like(img)
        cnt = np.zeros(mask.shape, np.float32)
        # Shift without wrapping: a texel only takes values from its real neighbours.
        h, w = mask.shape
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            m = np.zeros_like(mask)
            v = np.zeros_like(img)
            dst = (slice(max(dy, 0), h + min(dy, 0)), slice(max(dx, 0), w + min(dx, 0)))
            src = (slice(max(-dy, 0), h + min(-dy, 0)), slice(max(-dx, 0), w + min(-dx, 0)))
            m[dst] = mask[src]
            v[dst] = img[src]
            acc[m] += v[m]
            cnt[m] += 1
        grow = (~mask) & (cnt > 0)
        img[grow] = acc[grow] / cnt[grow][:, None]
        mask = mask | grow
    return img


def bake(ob, kind, size):
    """RGBA float array (size, size, 4) of the map."""
    import numpy as np
    tris, bvh, lo, hi = _mesh_data(ob)
    pos, nor, cur, mask = _rasterize(tris, size)
    diag = max(math.sqrt(sum((h - l) ** 2 for h, l in zip(hi, lo))), 1e-6)
    if kind == "ao":
        v = _rays(pos, nor, mask, bvh, diag * 0.25, False)
        rgb = np.repeat(v[:, :, None], 3, axis=2)
    elif kind == "thickness":
        v = np.clip(_rays(pos, nor, mask, bvh, diag * 0.5, True), 0.0, 1.0)
        rgb = np.repeat(v[:, :, None], 3, axis=2)
    elif kind == "curvature":
        v = np.clip(0.5 + cur, 0.0, 1.0)
        rgb = np.repeat(v[:, :, None], 3, axis=2)
    elif kind == "normal":
        rgb = nor * 0.5 + 0.5
    else:
        span = np.maximum(np.array(hi) - np.array(lo), 1e-6)
        rgb = (pos - np.array(lo)) / span
    rgb = _dilate(rgb.astype(np.float32), mask, PADDING)
    return np.concatenate([rgb, np.ones((size, size, 1), np.float32)], axis=2)


def bake_image(ob, kind, size, name):
    pixels = bake(ob, kind, size)
    image = bpy.data.images.get(name)
    if image is None or tuple(image.size) != (size, size):
        if image is not None:
            image.name = name + ".old"
        image = bpy.data.images.new(name, size, size, alpha=False)
    try:
        image.colorspace_settings.name = 'Non-Color'
    except TypeError:
        pass
    image.pixels[:] = pixels.ravel().tolist()
    image.update()
    # Packed: the map travels in the .range and the exported game.
    image.pack(as_png=True)
    return image


class NODE_OT_glsl_meshmap_bake(Operator):
    """Bake the mesh map of a GLSL node param from the active object (needs a UV map)"""
    bl_idname = "node.glsl_meshmap_bake"
    bl_label = "Bake Mesh Map"
    bl_options = {'REGISTER', 'UNDO'}

    node_name: StringProperty(name="Node")
    param: StringProperty(name="Param", description="Empty: every meshmap param of the node")
    size: EnumProperty(name="Size", items=SIZES, default='256')

    @classmethod
    def poll(cls, context):
        ob = context.object
        space = context.space_data
        return (ob is not None and ob.type == 'MESH' and space is not None and space.type == 'NODE_EDITOR' and
                space.edit_tree is not None)

    def execute(self, context):
        import time
        tree = context.space_data.edit_tree
        node = tree.nodes.get(self.node_name)
        params = [p for p in meshmap_params(node) if not self.param or p[0] == self.param]
        if not params:
            self.report({'ERROR'}, "No meshmap param to bake")
            return {'CANCELLED'}
        ob = context.object
        t0 = time.time()
        try:
            for name, kind in params:
                image = bake_image(ob, kind, int(self.size), "%s_%s" % (ob.name, kind))
                node["img_" + name] = image
        except (ValueError, ImportError) as ex:
            self.report({'ERROR'}, str(ex))
            return {'CANCELLED'}
        tree.interface_update(context)
        self.report({'INFO'}, "Baked %d map(s) of %s in %.1f s" % (len(params), ob.name, time.time() - t0))
        return {'FINISHED'}


class NODE_PT_glsl_meshmaps(Panel):
    """Mesh maps of the active GLSL node, baked from the active object"""
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_label = "GLSL Mesh Maps"

    @classmethod
    def poll(cls, context):
        space = context.space_data
        tree = getattr(space, "edit_tree", None)
        return tree is not None and bool(meshmap_params(tree.nodes.active))

    def draw(self, context):
        layout = self.layout
        node = context.space_data.edit_tree.nodes.active
        ob = context.object
        layout.label(text="From: %s" % (ob.name if ob else "(no active object)"), icon='OBJECT_DATA')
        for name, kind in meshmap_params(node):
            row = layout.row(align=True)
            image = node.get("img_" + name)
            row.label(text="%s (%s)" % (name, kind))
            row.label(text=image.name if image else "-")
            props = row.operator("node.glsl_meshmap_bake", text="", icon='RENDER_STILL')
            props.node_name, props.param = node.name, name
        props = layout.operator("node.glsl_meshmap_bake", text="Bake All", icon='RENDER_STILL')
        props.node_name, props.param = node.name, ""


classes = (
    NODE_OT_glsl_meshmap_bake,
    NODE_PT_glsl_meshmaps,
)
