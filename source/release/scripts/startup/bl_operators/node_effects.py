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

# Effects shelf of the Node Editor (Compositing): ready-made chains of nodes, all of them
# supported by the game compositor (no node groups: the game does not read them). Each effect
# goes in a Frame named after it, between the image and the Composite.
# The previews are PNGs named after the effect in startup/node_effects/ (replace them freely).

import os
import bpy
from bpy.types import Operator, Panel
from bpy.props import EnumProperty, StringProperty

PREVIEW_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "node_effects")

CATEGORIES = (
    ('ALL', "All", ""),
    ('LENS', "Camera & Lens", ""),
    ('COLOR', "Color", ""),
    ('GLOW', "Glow", ""),
    ('STYLE', "Style", ""),
)


def _set(node, **props):
    for key, value in props.items():
        if hasattr(node, key):
            setattr(node, key, value)


def _vignette(tree, new, link, image):
    mask = new('CompositorNodeEllipseMask')
    _set(mask, width=0.75, height=0.75, mask_type='ADD')
    blur = new('CompositorNodeBlur')
    _set(blur, filter_type='GAUSS', use_relative=True, factor_x=30.0, factor_y=30.0)
    mix = new('CompositorNodeMixRGB')
    mix.blend_type = 'MULTIPLY'
    mix.inputs[0].default_value = 1.0
    link(mask.outputs[0], blur.inputs[0])
    link(image, mix.inputs[1])
    link(blur.outputs[0], mix.inputs[2])
    return mix.outputs[0]


def _chromatic(tree, new, link, image):
    lens = new('CompositorNodeLensdist')
    _set(lens, use_fit=True)
    lens.inputs[2].default_value = 0.1  # Dispersion
    link(image, lens.inputs[0])
    return lens.outputs[0]


def _fisheye(tree, new, link, image):
    lens = new('CompositorNodeLensdist')
    _set(lens, use_fit=True)
    lens.inputs[1].default_value = 0.2  # Distort
    link(image, lens.inputs[0])
    return lens.outputs[0]


def _sepia(tree, new, link, image):
    bw = new('CompositorNodeRGBToBW')
    ramp = new('CompositorNodeValToRGB')
    ramp.color_ramp.elements[0].color = (0.10, 0.05, 0.02, 1.0)
    ramp.color_ramp.elements[1].color = (1.00, 0.88, 0.68, 1.0)
    link(image, bw.inputs[0])
    link(bw.outputs[0], ramp.inputs[0])
    return ramp.outputs[0]


def _split_toning(tree, new, link, image):
    cb = new('CompositorNodeColorBalance')
    _set(cb, correction_method='LIFT_GAMMA_GAIN')
    _set(cb, lift=(0.97, 1.0, 1.06), gamma=(1.0, 1.0, 1.0), gain=(1.04, 1.0, 0.95))
    link(image, cb.inputs[1])
    return cb.outputs[0]


def _tune(tree, new, link, image):
    hs = new('CompositorNodeHueSat')
    _set(hs, color_saturation=1.2)
    if hasattr(hs.inputs, "get") and hs.inputs.get("Saturation"):
        hs.inputs["Saturation"].default_value = 1.2
    bc = new('CompositorNodeBrightContrast')
    bc.inputs[2].default_value = 12.0  # Contrast
    gamma = new('CompositorNodeGamma')
    gamma.inputs[1].default_value = 0.95
    link(image, hs.inputs["Image"])
    link(hs.outputs[0], bc.inputs[0])
    link(bc.outputs[0], gamma.inputs[0])
    return gamma.outputs[0]


def _glare(kind, **props):
    def build(tree, new, link, image):
        glare = new('CompositorNodeGlare')
        glare.glare_type = kind
        _set(glare, **props)
        link(image, glare.inputs[0])
        return glare.outputs[0]
    return build


def _pixel_art(tree, new, link, image):
    down = new('CompositorNodeScale')
    down.space = 'RELATIVE'
    down.inputs[1].default_value = down.inputs[2].default_value = 1.0 / 12.0
    pix = new('CompositorNodePixelate')
    up = new('CompositorNodeScale')
    up.space = 'RELATIVE'
    up.inputs[1].default_value = up.inputs[2].default_value = 12.0
    link(image, down.inputs[0])
    link(down.outputs[0], pix.inputs[0])
    link(pix.outputs[0], up.inputs[0])
    return up.outputs[0]


def _outline(tree, new, link, image):
    sobel = new('CompositorNodeFilter')
    sobel.filter_type = 'SOBEL'
    bw = new('CompositorNodeRGBToBW')
    mix = new('CompositorNodeMixRGB')
    mix.blend_type = 'SUBTRACT'
    mix.inputs[0].default_value = 1.0
    link(image, sobel.inputs[1])
    link(sobel.outputs[0], bw.inputs[0])
    link(image, mix.inputs[1])
    link(bw.outputs[0], mix.inputs[2])
    return mix.outputs[0]


def _motion(tree, new, link, image):
    dblur = new('CompositorNodeDBlur')
    _set(dblur, iterations=4, zoom=0.12)
    link(image, dblur.inputs[0])
    return dblur.outputs[0]


# id, name, category, builder, tooltip
EFFECTS = (
    ('vignette', "Vignette", 'LENS', _vignette, "Darkens the corners of the image"),
    ('chromatic', "Chromatic Aberration", 'LENS', _chromatic, "Colors split at the borders, like a cheap lens"),
    ('fisheye', "Fisheye", 'LENS', _fisheye, "Bulges the image like a wide lens"),
    ('sepia', "Sepia", 'COLOR', _sepia, "Old photo: brown shades"),
    ('split_toning', "Split Toning", 'COLOR', _split_toning, "Blue shadows and warm highlights"),
    ('tune', "Tune Image", 'COLOR', _tune, "More saturation and contrast"),
    ('bloom', "Bloom", 'GLOW', _glare('BLOOM', threshold=0.8, size=8, mix=0.0),
     "Wide soft glow around the bright parts"),
    ('sun_beams', "Sun Beams", 'GLOW', _glare('SUN_BEAMS', threshold=0.8, mix=0.0),
     "Rays from the bright parts"),
    ('pixel_art', "Pixel Art", 'STYLE', _pixel_art, "Big square pixels"),
    ('outline', "Outline", 'STYLE', _outline, "Dark lines on the edges"),
    ('motion', "Motion Blur", 'STYLE', _motion, "Blur toward the borders, like speed"),
)

_previews = None


def preview_icon(effect_id):
    """Icon id of the preview PNG of the effect, 0 when there is none."""
    global _previews
    path = os.path.join(PREVIEW_DIR, effect_id + ".png")
    if not os.path.isfile(path):
        return 0
    if _previews is None:
        import bpy.utils.previews
        _previews = bpy.utils.previews.new()
    if effect_id not in _previews:
        _previews.load(effect_id, path, 'IMAGE')
    return _previews[effect_id].icon_id


def _ensure_tree(scene):
    scene.use_nodes = True
    tree = scene.node_tree
    composite = next((n for n in tree.nodes if n.type == 'COMPOSITE'), None)
    if composite is None:
        composite = tree.nodes.new('CompositorNodeComposite')
        composite.location = (300.0, 0.0)
    if not composite.inputs[0].is_linked:
        layers = next((n for n in tree.nodes if n.type == 'R_LAYERS'), None)
        if layers is None:
            layers = tree.nodes.new('CompositorNodeRLayers')
            layers.location = (composite.location.x - 400.0, composite.location.y)
        tree.links.new(layers.outputs[0], composite.inputs[0])
    return tree, composite


class NODE_OT_effect_add(Operator):
    """Add a ready-made effect before the Composite (it also runs in the game)"""
    bl_idname = "node.effect_add"
    bl_label = "Add Effect"
    bl_options = {'REGISTER', 'UNDO'}

    effect = StringProperty()

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return space and space.type == 'NODE_EDITOR' and space.tree_type == 'CompositorNodeTree'

    def execute(self, context):
        effect = next((e for e in EFFECTS if e[0] == self.effect), None)
        if effect is None:
            self.report({'ERROR'}, "Unknown effect: %s" % self.effect)
            return {'CANCELLED'}
        tree, composite = _ensure_tree(context.scene)
        source = composite.inputs[0].links[0].from_socket
        before = set(tree.nodes)

        frame = tree.nodes.new('NodeFrame')
        frame.label = effect[1]
        frame.shrink = True

        def new(idname):
            node = tree.nodes.new(idname)
            node.parent = frame
            return node

        out = effect[3](tree, new, tree.links.new, source)

        # every link that read the image (Composite, Viewer...) now reads the effect
        added = set(tree.nodes) - before
        for l in list(tree.links):
            if l.from_socket == source and l.to_node not in added:
                tree.links.new(out, l.to_socket)

        # the new nodes in a row, the Composite moves right to make room
        nodes = [n for n in added if n != frame]
        nodes.sort(key=lambda n: n.name)
        x0 = composite.location.x
        for i, node in enumerate(nodes):
            node.location = (x0 + i * 200.0, composite.location.y - (i % 2) * 40.0)
            node.select = True
        composite.location.x = x0 + len(nodes) * 200.0 + 60.0
        for node in tree.nodes:
            if node.type == 'VIEWER' and node.location.x < composite.location.x:
                node.location.x = composite.location.x
        return {'FINISHED'}


class NODE_PT_effects_shelf(Panel):
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "Effects"
    bl_options = {'HIDE_HEADER'}

    @classmethod
    def poll(cls, context):
        return context.space_data.tree_type == 'CompositorNodeTree'

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager
        row = layout.row(align=True)
        row.prop(wm, "node_effects_tab", expand=True)

        row = layout.row()
        for effect_id, name, category, _build, tip in EFFECTS:
            if wm.node_effects_tab not in {'ALL', category}:
                continue
            col = row.column(align=True)
            icon = preview_icon(effect_id)
            if icon:
                col.operator_preview("node.effect_add", icon_value=icon, scale=4.0,
                                     description=tip).effect = effect_id
            else:
                sub = col.column(align=True)
                sub.scale_y = 4.0
                sub.operator("node.effect_add", text="", icon='NODE_COMPOSITING').effect = effect_id
            col.label(text=name)


bpy.types.WindowManager.node_effects_tab = EnumProperty(
    name="Category", items=CATEGORIES, default='ALL',
    description="Kind of effect shown in the shelf")


classes = (
    NODE_OT_effect_add,
    NODE_PT_effects_shelf,
)
