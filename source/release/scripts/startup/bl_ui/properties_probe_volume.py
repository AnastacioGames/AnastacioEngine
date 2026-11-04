# Probe Volume GI (docs/probe-volume-gi.md): Add menu entry and Object panel. The game reads plain
# game properties on a box Empty ("probe_volume" and the optional "probe_volume_*"), so the panel only
# edits those: files made by hand keep working and the panel shows them too.
import math

import bpy
from bpy.types import Operator, Panel
from bpy.props import EnumProperty

# Same numbers as KX_ProbeVolume.cpp (probes per quality) and the default spacing (0 = 4 m).
MAX_PROBES = (64, 128, 256)
DEFAULT_SPACING = 4.0

# name, type, default, label
OPTIONS = (
    ("probe_volume_bounce", 'FLOAT', 0.3, "Bounce"),
    ("probe_volume_clip_end", 'FLOAT', 30.0, "Clip End"),
    ("probe_volume_ssgi", 'FLOAT', 0.5, "SSGI Inside"),
    ("probe_volume_ignore_layers", 'INT', 0, "Ignore Layers"),
    ("probe_volume_freeze", 'BOOL', False, "Freeze"),
)


def is_volume(ob):
    return ob is not None and ob.type == 'EMPTY' and "probe_volume" in ob.game.properties


def _add_prop(ob, name, typ, value):
    props = ob.game.properties
    if name not in props:
        scene = bpy.context.scene
        active = scene.objects.active
        scene.objects.active = ob
        bpy.ops.object.game_property_new(type=typ, name=name)
        scene.objects.active = active
        props[name].value = value


def _remove_prop(ob, name):
    props = ob.game.properties
    if name in props:
        scene = bpy.context.scene
        active = scene.objects.active
        scene.objects.active = ob
        bpy.ops.object.game_property_remove(index=list(props.keys()).index(name))
        scene.objects.active = active


def _setup(ob):
    _add_prop(ob, "probe_volume", 'FLOAT', DEFAULT_SPACING)
    for name, typ, value, _label in OPTIONS:
        _add_prop(ob, name, typ, value)


def _quality(ob):
    prop = ob.game.properties.get("probe_volume_quality")
    if prop is None:
        return 'PRESET'
    value = prop.value
    if isinstance(value, str):
        return {"low": 'LOW', "medium": 'MEDIUM', "med": 'MEDIUM', "high": 'HIGH'}.get(value.lower(), 'MEDIUM')
    return ('LOW', 'MEDIUM', 'HIGH')[min(max(int(value), 0), 2)]


def _grid(ob):
    """Probes along each axis and the spacing the game will use (it grows past the quality limit)."""
    spacing = float(ob.game.properties["probe_volume"].value) or DEFAULT_SPACING
    spacing = max(spacing, 0.25)
    scale = ob.matrix_world.to_scale()
    half = [max(abs(scale[i]) * ob.empty_draw_size, 0.01) for i in range(3)]
    quality = {'LOW': 0, 'MEDIUM': 1, 'HIGH': 2}.get(_quality(ob), 2)
    limit = MAX_PROBES[quality]
    used = spacing
    while True:
        dims = [max(2, int(math.ceil(2.0 * h / used)) + 1) for h in half]
        if dims[0] * dims[1] * dims[2] <= limit:
            return dims, spacing, used, limit
        used *= 1.1


class OBJECT_OT_probe_volume_add(Operator):
    """Add a Probe Volume: a box Empty whose grid of probes gives the bounced light inside it"""
    bl_idname = "object.probe_volume_add"
    bl_label = "Probe Volume"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.ops.object.empty_add(type='CUBE', location=context.scene.cursor_location)
        ob = context.object
        ob.name = "ProbeVolume"
        # A small room; scale it to cover the area.
        ob.scale = (5.0, 5.0, 2.0)
        ob.location.z += 2.0
        _setup(ob)
        return {'FINISHED'}


class OBJECT_OT_probe_volume_toggle(Operator):
    """Turn this box Empty into a Probe Volume, or back into a plain Empty"""
    bl_idname = "object.probe_volume_toggle"
    bl_label = "Probe Volume"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'EMPTY'

    def execute(self, context):
        ob = context.object
        if is_volume(ob):
            for name in ["probe_volume", "probe_volume_quality"] + [o[0] for o in OPTIONS]:
                _remove_prop(ob, name)
        else:
            ob.empty_draw_type = 'CUBE'
            _setup(ob)
        return {'FINISHED'}


class OBJECT_OT_probe_volume_quality(Operator):
    """Quality of this grid: Preset follows Scene > Quality, the others cap the probes (64, 128, 256)"""
    bl_idname = "object.probe_volume_quality"
    bl_label = "Probe Volume Quality"
    bl_options = {'REGISTER', 'UNDO'}

    quality = EnumProperty(items=(
        ('PRESET', "Preset", "Follow the scene quality preset (Low on integrated GPUs, off on Very Low)"),
        ('LOW', "Low", "Up to 64 probes, 2 faces per frame"),
        ('MEDIUM', "Medium", "Up to 128 probes, 4 faces per frame"),
        ('HIGH', "High", "Up to 256 probes, 8 faces per frame"),
    ))

    def execute(self, context):
        ob = context.object
        if self.quality == 'PRESET':
            _remove_prop(ob, "probe_volume_quality")
        else:
            _add_prop(ob, "probe_volume_quality", 'STRING', "")
            ob.game.properties["probe_volume_quality"].value = self.quality.capitalize()
        return {'FINISHED'}


class OBJECT_OT_probe_volume_skip(Operator):
    """Keep this object out of the Probe Volume captures (it still receives their light)"""
    bl_idname = "object.probe_volume_skip"
    bl_label = "Skip in Probe Volume"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ob = context.object
        if "probe_volume_skip" in ob.game.properties:
            _remove_prop(ob, "probe_volume_skip")
        else:
            _add_prop(ob, "probe_volume_skip", 'BOOL', True)
        return {'FINISHED'}


class EmptyProbePanel:
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"

    @classmethod
    def poll(cls, context):
        ob = context.object
        return ob is not None and ob.type == 'EMPTY' and context.scene.render.engine == 'BLENDER_GAME'


class DATA_PT_probe_volume(EmptyProbePanel, Panel):
    bl_label = "Probe Volume"

    def draw_header(self, context):
        self.layout.operator("object.probe_volume_toggle", text="",
                             icon='CHECKBOX_HLT' if is_volume(context.object) else 'CHECKBOX_DEHLT', emboss=False)

    def draw(self, context):
        layout = self.layout
        ob = context.object
        if not is_volume(ob):
            layout.label(text="Lights the area inside this box with probes (bounced light)", icon='INFO')
            return
        props = ob.game.properties

        box = layout.box()
        box.label(text="Grid:", icon='MESH_GRID')
        row = box.row(align=True)
        current = _quality(ob)
        for key, text in (('PRESET', "Preset"), ('LOW', "Low"), ('MEDIUM', "Med"), ('HIGH', "High")):
            row.operator("object.probe_volume_quality", text=text, depress=(current == key)).quality = key
        box.prop(props["probe_volume"], "value", text="Spacing (m)")
        dims, spacing, used, limit = _grid(ob)
        total = dims[0] * dims[1] * dims[2]
        if used > spacing * 1.01:
            box.label(text="%dx%dx%d = %d probes, spread to %.1f m (limit %d)" % (dims[0], dims[1], dims[2], total, used, limit),
                      icon='ERROR')
        else:
            box.label(text="%dx%dx%d = %d probes" % (dims[0], dims[1], dims[2], total), icon='INFO')

        box = layout.box()
        box.label(text="Light:", icon='LAMP_SUN')
        if "probe_volume_bounce" in props:
            box.prop(props["probe_volume_bounce"], "value", text="Bounce")
        if "probe_volume_ssgi" in props:
            box.prop(props["probe_volume_ssgi"], "value", text="SSGI Inside")

        box = layout.box()
        box.label(text="Capture:", icon='RENDER_STILL')
        for name, label in (("probe_volume_clip_end", "Clip End"), ("probe_volume_ignore_layers", "Ignore Layers"),
                            ("probe_volume_freeze", "Freeze")):
            if name in props:
                box.prop(props[name], "value", text=label)

        if ob.empty_draw_type != 'CUBE':
            layout.label(text="Display the Empty as Cube: the box is the volume", icon='ERROR')
        if any(abs(a) > 1e-3 for a in ob.matrix_world.to_euler()):
            layout.label(text="Rotation is ignored, the grid follows the world axes", icon='ERROR')


class OBJECT_PT_probe_volume_skip(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    bl_label = "Probe Volume"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        ob = context.object
        return (ob is not None and ob.type == 'MESH' and context.scene.render.engine == 'BLENDER_GAME' and
                any(is_volume(o) for o in context.scene.objects))

    def draw(self, context):
        box = self.layout.box()
        box.label(text="Probe Volume:", icon='MESH_GRID')
        skip = "probe_volume_skip" in context.object.game.properties
        box.operator("object.probe_volume_skip", text="Skip in Probe Volume",
                     icon='CHECKBOX_HLT' if skip else 'CHECKBOX_DEHLT', emboss=False)


classes = (
    OBJECT_OT_probe_volume_add,
    OBJECT_OT_probe_volume_toggle,
    OBJECT_OT_probe_volume_quality,
    OBJECT_OT_probe_volume_skip,
    DATA_PT_probe_volume,
    OBJECT_PT_probe_volume_skip,
)

if __name__ == "__main__":  # only for live edit.
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
