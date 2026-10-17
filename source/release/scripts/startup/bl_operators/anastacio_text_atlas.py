# Bitmap atlas for game text: generated inside the engine from the Text font (with an
# optional ready-made style), edited externally/by AI and reloaded; or loaded from
# atlas.png + atlas.json made by tools/text_atlas.py. Everything is stored in the .range.

import json
import math
import os
import random

import bpy
from bpy.types import Operator
from bpy.props import BoolProperty, EnumProperty, StringProperty
from bpy_extras.io_utils import ImportHelper

JSON_KEY = "text_atlas_json"


def _text_curve(context):
    cu = getattr(context, "curve", None)
    if cu is None:
        ob = context.object
        if ob and ob.type == 'FONT':
            cu = ob.data
    return cu


def _apply_atlas(cu, json_path):
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    png = os.path.join(os.path.dirname(json_path), "atlas.png")
    if not os.path.isfile(png):
        raise RuntimeError("atlas.png not found next to %s" % json_path)

    image = cu.atlas_image
    if image and os.path.normcase(bpy.path.abspath(image.filepath)) == os.path.normcase(png):
        image.reload()
    else:
        image = bpy.data.images.load(png, check_existing=True)
        image.reload()
    image.use_alpha = True

    glyphs = data["glyphs"]
    cu.atlas_glyphs_resize(len(glyphs))
    for dst, src in zip(cu.atlas_glyphs, glyphs):
        dst.code = src["code"]
        dst.uv_min = (src["u0"], src["v0"])
        dst.uv_max = (src["u1"], src["v1"])
        dst.advance = src["advance"]
    cu.atlas_image = image
    cu.atlas_size = data.get("size", data["line_height"])
    cu.atlas_padding = data["padding"]
    cu.atlas_cell = data["cell"]
    cu.atlas_baseline = data["baseline"]
    cu.atlas_line_height = data["line_height"]
    cu.use_bitmap_atlas = True
    cu[JSON_KEY] = bpy.path.relpath(json_path) if bpy.data.filepath else json_path
    return len(glyphs)


# --- image helpers (numpy, rows run top to bottom) -----------------------------------

def _np():
    import numpy
    return numpy


def _shift(m, dx, dy):
    """Move an array dx right and dy down, filling with 0."""
    np = _np()
    out = np.zeros_like(m)
    h, w = m.shape[:2]
    xs, xd = (0, dx) if dx >= 0 else (-dx, 0)
    ys, yd = (0, dy) if dy >= 0 else (-dy, 0)
    cw, ch = w - abs(dx), h - abs(dy)
    if cw > 0 and ch > 0:
        out[yd:yd + ch, xd:xd + cw] = m[ys:ys + ch, xs:xs + cw]
    return out


def _grow(m, r, fn):
    for _ in range(max(0, int(r))):
        m = fn(m, fn(_shift(m, 1, 0), _shift(m, -1, 0)))
        m = fn(m, fn(_shift(m, 0, 1), _shift(m, 0, -1)))
    return m


def _dilate(m, r):
    return _grow(m, r, _np().maximum)


def _erode(m, r):
    return _grow(m, r, _np().minimum)


def _blur(m, r):
    for _ in range(max(0, int(r))):
        m = (m * 2 + _shift(m, 1, 0) + _shift(m, -1, 0)) / 4
        m = (m * 2 + _shift(m, 0, 1) + _shift(m, 0, -1)) / 4
    return m


def _layer(out, rgb, mask, alpha=1.0):
    """Straight-alpha 'over' of color rgb (3-tuple or HxWx3) cut by mask onto out (HxWx4)."""
    np = _np()
    a = np.clip(mask * alpha, 0.0, 1.0)[..., None]
    ab = out[..., 3:4]
    ao = a + ab * (1.0 - a)
    rgb = np.broadcast_to(np.asarray(rgb, dtype=np.float32), out[..., :3].shape)
    col = rgb * a + out[..., :3] * ab * (1.0 - a)
    out[..., :3] = np.where(ao > 1e-6, col / np.maximum(ao, 1e-6), out[..., :3])
    out[..., 3:4] = ao


def _vgrad(h, w, top, bottom, y0=0, y1=None):
    np = _np()
    y1 = h if y1 is None else y1
    top, bottom = np.asarray(top, np.float32), np.asarray(bottom, np.float32)
    t = np.clip((np.arange(h, dtype=np.float32) - y0) / max(1, y1 - y0), 0, 1)[:, None, None]
    return top + (bottom - top) * t + np.zeros((1, w, 1), np.float32)


# --- ready-made styles: fn(mask, cell, baseline, scale, rnd) -> RGBA cell ------------

def _style_wood(m, cell, base, k, rnd):
    np = _np()
    h, w = m.shape
    out = np.zeros((h, w, 4), np.float32)
    o = max(1, round(3 * k))
    _layer(out, (0, 0, 0), _blur(_shift(_dilate(m, o), o, round(4 * k)), round(2 * k)), 0.6)
    _layer(out, (0.23, 0.12, 0.05), _dilate(m, o))
    wood = _vgrad(h, w, (0.91, 0.63, 0.31), (0.69, 0.38, 0.16))
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    ph, fr = rnd.uniform(0, 6.28), rnd.uniform(0.18, 0.26) / k
    grain = np.sin(yy * fr + np.sin(xx * 0.07 / k + ph) * 2.2 + ph)
    wood *= (1.0 - 0.18 * np.maximum(0, grain) ** 3)[..., None]
    _layer(out, wood, m)
    inner = _erode(m, 1)
    d = max(1, round(2 * k))
    _layer(out, (1.0, 0.87, 0.63), np.clip(inner - _shift(inner, d, d), 0, 1), 0.67)
    _layer(out, (0.35, 0.18, 0.06), np.clip(inner - _shift(inner, -d, -d), 0, 1), 0.55)
    return out


def _style_arcade(m, cell, base, k, rnd):
    np = _np()
    h, w = m.shape
    p = max(2, round(4 * k))
    hh, ww = h // p * p, w // p * p
    blocks = m[:hh, :ww].reshape(hh // p, p, ww // p, p).mean(axis=(1, 3)) > 0.4
    pm = np.zeros_like(m)
    pm[:hh, :ww] = np.repeat(np.repeat(blocks, p, 0), p, 1)
    out = np.zeros((h, w, 4), np.float32)
    dark = (0.1, 0.07, 0.16)
    _layer(out, dark, _shift(_dilate(pm, p), p, p))
    _layer(out, dark, _dilate(pm, p))
    fill = np.zeros((h, w, 3), np.float32) + np.asarray((0.98, 0.81, 0.24), np.float32)
    fill[max(0, base - int(cell * 0.28)):] = (0.89, 0.25, 0.13)
    _layer(out, fill, pm)
    return out


def _style_boxed(m, cell, base, k, rnd):
    np = _np()
    h, w = m.shape
    out = np.zeros((h, w, 4), np.float32)
    ext = m
    for i in range(1, max(2, round(7 * k))):
        ext = np.maximum(ext, _shift(m, i, i))
    _layer(out, (0.16, 0.06, 0.24), _dilate(ext, max(1, round(2 * k))))
    _layer(out, (0.36, 0.16, 0.47), ext)
    _layer(out, _vgrad(h, w, (1.0, 0.84, 0.27), (0.94, 0.63, 0.12), 0, base), m)
    return out


def _style_candy(m, cell, base, k, rnd):
    np = _np()
    h, w = m.shape
    out = np.zeros((h, w, 4), np.float32)
    _layer(out, (0.59, 0.08, 0.16), _dilate(m, max(1, round(3 * k))))
    _layer(out, (0.98, 0.84, 0.63), m)
    ys, xs = np.nonzero(m > 0.5)
    if len(ys):
        y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
        top = y0 + (y1 - y0) * 0.38
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        cover = (yy <= top).astype(np.float32)
        x = float(x0)
        while x < x1:
            r = rnd.uniform(3, 5) * k
            ry = rnd.uniform(1, 4) * r
            drop = ((xx - x) / r) ** 2 + ((yy - top) / ry) ** 2 <= 1
            cover = np.maximum(cover, drop.astype(np.float32))
            x += rnd.uniform(7, 12) * k
        icing = _erode(m, max(1, round(2 * k))) * cover
        color = rnd.choice([(1.0, 0.47, 0.67), (0.98, 0.82, 0.24), (0.59, 0.86, 0.35), (0.75, 0.59, 1.0)])
        _layer(out, color, icing)
        _layer(out, (1, 1, 1), np.clip(icing - _shift(icing, 0, max(1, round(2 * k))), 0, 1), 0.63)
    return out


STYLES = {
    'WOOD': ("Wood", "Carved wood with dark outline and shadow", _style_wood),
    'ARCADE': ("Arcade", "Pixel letters, yellow and red, dark outline", _style_arcade),
    'BOXED': ("Boxed", "Yellow gradient with purple 3D extrusion", _style_boxed),
    'CANDY': ("Candy", "Cream letters with dripping icing", _style_candy),
}
# free pixels each style needs around the glyph at 64 px (outline, shadow, extrusion)
STYLE_PADDING = {'NONE': 4, 'WOOD': 10, 'ARCADE': 12, 'BOXED': 12, 'CANDY': 6}

def _chars(*ranges):
    return "".join(chr(c) for a, b in ranges for c in range(a, b + 1))


CHARSET_ASCII = _chars((0x20, 0x7E))
CHARSET_LATIN = _chars((0xA0, 0xFF))
CHARSET_CYRILLIC = _chars((0x400, 0x45F))  # Russian and other Cyrillic letters
CHARSET_KANA = _chars((0x3000, 0x3003), (0x300C, 0x300F), (0x3041, 0x3096), (0x309B, 0x309E),
                      (0x30A0, 0x30FF), (0xFF01, 0xFF01), (0xFF1F, 0xFF1F))  # hiragana, katakana, 。「」ー！？


def _bleed(rgba, passes=4):
    """Transparent pixels take the color of opaque neighbours (no dark/white fringe when filtered)."""
    np = _np()
    rgb = rgba[..., :3].copy()
    solid = rgba[..., 3] > 0
    for _ in range(passes):
        acc = np.zeros_like(rgb)
        cnt = np.zeros(solid.shape, np.float32)
        s0 = solid.astype(np.float32)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            s = _shift(s0, dx, dy)
            acc += _shift(rgb, dx, dy) * s[..., None]
            cnt += s
        new = (~solid) & (cnt > 0)
        rgb[new] = acc[new] / cnt[new][:, None]
        solid |= new
    rgba[..., :3] = rgb
    return rgba


def _apply_style(cu, image, style):
    np = _np()
    w, h = image.size
    px = np.array(image.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1].copy()
    if style in STYLES:
        fn = STYLES[style][2]
        cell = int(round(cu.atlas_cell))
        base = int(round(cu.atlas_baseline))
        k = cu.atlas_size / 64.0
        for g in cu.atlas_glyphs:
            x = int(round(g.uv_min[0] * w))
            y = h - int(round(g.uv_max[1] * h))
            m = px[y:y + cell, x:x + cell, 3].copy()
            px[y:y + cell, x:x + cell] = fn(m, cell, base, k, random.Random(g.code))
    px = _bleed(px)
    image.pixels[:] = px[::-1].ravel()


class FONT_OT_text_atlas_generate(Operator):
    """Make the bitmap atlas from this text's font, plain or with a ready-made style. """ \
        """Then edit the image (Edit Externally, Texture Paint or an AI tool) and press Reload"""
    bl_idname = "font.text_atlas_generate"
    bl_label = "Generate Bitmap Atlas"
    bl_options = {'REGISTER', 'UNDO'}

    style = EnumProperty(
        name="Style",
        items=[('NONE', "Plain (white)", "White letters, tinted by the object color")]
        + [(key, v[0], v[1]) for key, v in STYLES.items()],
        default='NONE')
    size = EnumProperty(
        name="Letter Size",
        description="Pixels per letter: bigger stays sharp when the text is large on screen",
        items=[('32', "32 px", ""), ('64', "64 px", ""), ('128', "128 px", ""), ('256', "256 px", "")],
        default='64')
    chars = EnumProperty(
        name="Characters",
        items=[('FULL', "Latin (accents)", "ASCII plus Latin-1: covers Portuguese and Spanish"),
               ('ASCII', "ASCII", "Only basic letters, digits and symbols"),
               ('TEXT', "Only This Text", "Only the characters this text uses (smallest image)"),
               ('CUSTOM', "Custom", "The characters typed below")],
        default='FULL')
    use_cyrillic = BoolProperty(name="Russian (Cyrillic)", default=False,
                                description="Also bake the Cyrillic alphabet")
    use_kana = BoolProperty(name="Japanese (Hiragana, Katakana)", default=False,
                            description="Also bake hiragana, katakana and Japanese punctuation. "
                            "Letters the text font lacks come from the bundled international font")
    custom = StringProperty(name="Custom Characters", default="")

    @classmethod
    def poll(cls, context):
        return _text_curve(context) is not None

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "style")
        col.prop(self, "size")
        col.prop(self, "chars")
        if self.chars == 'CUSTOM':
            col.prop(self, "custom", text="")
        if self.chars in {'FULL', 'ASCII', 'CUSTOM'}:
            col.prop(self, "use_cyrillic")
            col.prop(self, "use_kana")

    def execute(self, context):
        cu = _text_curve(context)
        if self.chars == 'TEXT':
            chars = " " + cu.body
        elif self.chars == 'CUSTOM':
            chars = " " + self.custom
        else:
            chars = CHARSET_ASCII + (CHARSET_LATIN if self.chars == 'FULL' else "")
        if self.chars != 'TEXT':
            chars += (CHARSET_CYRILLIC if self.use_cyrillic else "") + (CHARSET_KANA if self.use_kana else "")
        chars = "".join(c for c in chars if c not in "\n\r\t")
        size = int(self.size)
        pad = int(math.ceil(STYLE_PADDING.get(self.style, 4) * size / 64.0)) + 2
        old = cu.atlas_image
        image = cu.atlas_bake_font(size=size, padding=pad, chars=chars)
        if image is None:
            return {'CANCELLED'}
        image.name = "TextAtlas_" + cu.name
        try:
            _apply_style(cu, image, self.style)
        except ImportError:
            self.report({'WARNING'}, "numpy missing: atlas left plain")
        image.pack(as_png=True)
        if old and old.users == 0:
            bpy.data.images.remove(old)
        if JSON_KEY in cu:
            del cu[JSON_KEY]
        cu.use_bitmap_atlas = True
        self.report({'INFO'}, "Bitmap atlas: %d glyphs, %dx%d" % (
            len(cu.atlas_glyphs), image.size[0], image.size[1]))
        return {'FINISHED'}


def _write_atlas_file(image):
    """Make the atlas image a PNG file on disk (out of the .range) and return its absolute path."""
    path = bpy.path.abspath(image.filepath) if image.filepath else ""
    if not image.packed_file and path and os.path.isfile(path):
        return path
    name = bpy.path.clean_name(image.name) + ".png"
    if bpy.data.filepath:
        rel = "//textures/" + name
        path = bpy.path.abspath(rel)
    else:
        rel = path = os.path.join(bpy.app.tempdir, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    image.filepath_raw = rel
    image.pack(as_png=True)  # the pack remembers filepath: unpack writes the PNG there
    image.unpack(method='WRITE_ORIGINAL')
    return os.path.normpath(path)


class FONT_OT_text_atlas_edit_external(Operator):
    """Save the atlas image as a PNG and open it in your image editor (or give the file to an AI tool). """ \
        """Keep each letter inside its cell, save, then press Reload"""
    bl_idname = "font.text_atlas_edit_external"
    bl_label = "Edit Externally"

    @classmethod
    def poll(cls, context):
        cu = _text_curve(context)
        return cu is not None and cu.atlas_image is not None

    def execute(self, context):
        path = _write_atlas_file(_text_curve(context).atlas_image)
        try:
            bpy.ops.image.external_edit(filepath=path)
        except RuntimeError as ex:
            self.report({'WARNING'}, "Saved %s (could not open an editor: %s)" % (path, ex))
            return {'FINISHED'}
        self.report({'INFO'}, "Editing %s - save it there, then press Reload" % path)
        return {'FINISHED'}


class FONT_OT_text_atlas_pack(Operator):
    """Store the atlas image inside the .range (needed to share or export the game)"""
    bl_idname = "font.text_atlas_pack"
    bl_label = "Pack Atlas Image"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        cu = _text_curve(context)
        return cu is not None and cu.atlas_image is not None and not cu.atlas_image.packed_file

    def execute(self, context):
        _text_curve(context).atlas_image.pack(as_png=True)
        return {'FINISHED'}


class FONT_OT_text_atlas_import(Operator, ImportHelper):
    """Load a bitmap atlas (atlas.json + atlas.png made by tools/text_atlas.py build) into this text"""
    bl_idname = "font.text_atlas_import"
    bl_label = "Load Bitmap Atlas"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".json"
    filter_glob = StringProperty(default="atlas.json;*.json", options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        return _text_curve(context) is not None

    def execute(self, context):
        try:
            count = _apply_atlas(_text_curve(context), self.filepath)
        except (OSError, KeyError, ValueError, RuntimeError) as ex:
            self.report({'ERROR'}, "Bitmap atlas: %s" % ex)
            return {'CANCELLED'}
        self.report({'INFO'}, "Bitmap atlas: %d glyphs" % count)
        return {'FINISHED'}


class FONT_OT_text_atlas_reload(Operator):
    """Read the atlas image again after editing it (and atlas.json, when it came from tools/text_atlas.py)"""
    bl_idname = "font.text_atlas_reload"
    bl_label = "Reload Bitmap Atlas"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        cu = _text_curve(context)
        return cu is not None and (JSON_KEY in cu or cu.atlas_image is not None)

    def execute(self, context):
        cu = _text_curve(context)
        if JSON_KEY not in cu:
            image = cu.atlas_image
            path = bpy.path.abspath(image.filepath) if image.filepath else ""
            if not path or not os.path.isfile(path):
                self.report({'WARNING'}, "No atlas PNG on disk: press Edit Externally first")
                return {'CANCELLED'}
            if image.packed_file:  # packed (by hand or auto pack): read the edited file, pack it again
                image.unpack(method='USE_ORIGINAL')
                image.reload()
                image.pack(as_png=True)
            else:
                image.reload()
            self.report({'INFO'}, "Bitmap atlas image reloaded")
            return {'FINISHED'}
        try:
            count = _apply_atlas(cu, bpy.path.abspath(cu[JSON_KEY]))
        except (OSError, KeyError, ValueError, RuntimeError) as ex:
            self.report({'ERROR'}, "Bitmap atlas: %s" % ex)
            return {'CANCELLED'}
        self.report({'INFO'}, "Bitmap atlas: %d glyphs" % count)
        return {'FINISHED'}


classes = (
    FONT_OT_text_atlas_generate,
    FONT_OT_text_atlas_edit_external,
    FONT_OT_text_atlas_pack,
    FONT_OT_text_atlas_import,
    FONT_OT_text_atlas_reload,
)
