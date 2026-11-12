# Probe Volume GI (docs/probe-volume-gi.md): Add menu entry and Object panel. The game reads plain
# game properties on a box Empty ("probe_volume" and the optional "probe_volume_*"), so the panel only
# edits those: files made by hand keep working and the panel shows them too.
import math
import os

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


ALL_PROPS = ["probe_volume", "probe_volume_quality"] + [o[0] for o in OPTIONS]


def _enabled_get(ob):
    return is_volume(ob)


def _enabled_set(ob, value):
    """Off keeps the settings on the object (ae_probe_volume_backup), so turning it on again restores them."""
    if ob.type != 'EMPTY' or value == is_volume(ob):
        return
    props = ob.game.properties
    if value:
        ob.empty_draw_type = 'CUBE'
        backup = ob.get("ae_probe_volume_backup")
        _setup(ob)
        if backup:
            for name in ALL_PROPS:
                if name in backup.keys():
                    old = backup[name]
                    if name == "probe_volume_quality":
                        _add_prop(ob, name, 'STRING', str(old))
                    elif name in props:
                        props[name].value = old
            del ob["ae_probe_volume_backup"]
    else:
        ob["ae_probe_volume_backup"] = {name: props[name].value for name in ALL_PROPS if name in props}
        for name in ALL_PROPS:
            _remove_prop(ob, name)


bpy.types.Object.ae_probe_volume = bpy.props.BoolProperty(
    name="Light Probe Volume",
    description="Light the area inside this box with bounced light from walls and floor (a grid of light probes)",
    get=_enabled_get, set=_enabled_set)


class OBJECT_OT_probe_volume_add(Operator):
    """Add a Light Probe Volume: a box Empty that lights the area inside it with bounced light from walls and floor"""
    bl_idname = "object.probe_volume_add"
    bl_label = "Light Probe Volume"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.ops.object.empty_add(type='CUBE', location=context.scene.cursor_location)
        ob = context.object
        ob.name = "LightProbeVolume"
        # A small room; scale it to cover the area.
        ob.scale = (5.0, 5.0, 2.0)
        ob.location.z += 2.0
        _setup(ob)
        return {'FINISHED'}


class OBJECT_OT_probe_volume_toggle(Operator):
    """Turn this box Empty into a Light Probe Volume, or back into a plain Empty"""
    bl_idname = "object.probe_volume_toggle"
    bl_label = "Probe Volume"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'EMPTY'

    def execute(self, context):
        ob = context.object
        ob.ae_probe_volume = not is_volume(ob)
        return {'FINISHED'}


class OBJECT_OT_probe_volume_quality(Operator):
    """Quality of this grid: Preset follows Scene > Quality, the others cap the probes (64, 128, 256)"""
    bl_idname = "object.probe_volume_quality"
    bl_label = "Light Probe Volume Quality"
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
    """Keep this object out of the Light Probe Volume captures (it still receives their light)"""
    bl_idname = "object.probe_volume_skip"
    bl_label = "Skip in Light Probe Volume"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ob = context.object
        if "probe_volume_skip" in ob.game.properties:
            _remove_prop(ob, "probe_volume_skip")
        else:
            _add_prop(ob, "probe_volume_skip", 'BOOL', True)
        return {'FINISHED'}


def probes_count(path):
    """Volumes recorded in a .probes file (same layout as KX_TextureRendererManager::SaveBakedLight)."""
    import struct
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return 0
    if data[:4] != b"RPV1":
        return 0
    pos, count = 4, 0
    while pos + 4 <= len(data):
        length = struct.unpack_from("<i", data, pos)[0]
        pos += 4 + length + 12 + 24
        if length <= 0 or pos + 4 > len(data):
            break
        probes = struct.unpack_from("<i", data, pos)[0]
        pos += 4 + probes * 128  # 3 + 27 floats and 2 ints a probe
        if pos > len(data):
            break
        count += 1
    return count


def probes_path(scene):
    """Saved light of the scene's volumes, read by the game next to itself (KX_TextureRendererManager::BakedPath)."""
    if not bpy.data.filepath:
        return ""
    return os.path.join(os.path.dirname(bpy.data.filepath), scene.name + ".probes")


class SCENE_OT_probe_volume_bake(Operator):
    """Capture the light of every Light Probe Volume now and save it next to the project (<scene>.probes), """ \
        """so the game starts with it ready instead of capturing while it plays. Esc cancels"""
    bl_idname = "scene.probe_volume_bake"
    bl_label = "Bake Probes"

    @classmethod
    def poll(cls, context):
        return bool(bpy.data.filepath) and any(is_volume(o) for o in context.scene.objects)

    def invoke(self, context, event):
        import subprocess
        import tempfile
        from bl_operators.anastacio_cook import _runtime_path

        runtime = _runtime_path()
        if not os.path.isfile(runtime):
            self.report({'ERROR'}, "Game runtime not found: %s" % runtime)
            return {'CANCELLED'}
        # The game runs a copy: unsaved changes are baked too, and it starts from no saved light.
        self._tempdir = tempfile.mkdtemp(prefix="anastacio_probes_")
        copy = os.path.join(self._tempdir, "bake.range")
        if 'FINISHED' not in bpy.ops.wm.save_as_mainfile(filepath=copy, copy=True, relative_remap=True, compress=False):
            self._cleanup()
            self.report({'ERROR'}, "Could not save the temporary scene")
            return {'CANCELLED'}
        self._fresh = os.path.join(self._tempdir, context.scene.name + ".probes")
        self._target = probes_path(context.scene)
        env = dict(os.environ, RANGE_PROBE_VOLUME_BAKE="all")
        try:
            self._process = subprocess.Popen([runtime, "-w", "320", "180", copy], env=env, stdout=subprocess.DEVNULL,
                                             stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
        except OSError as ex:
            self._cleanup()
            self.report({'ERROR'}, "Bake Probes failed: %s" % ex)
            return {'CANCELLED'}
        # Progress: the game saves the finished volumes every second.
        self._ready = 0
        self._total = sum(1 for o in context.scene.objects if is_volume(o))
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.25, context.window)
        wm.progress_begin(0, 100)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _cleanup(self):
        import shutil
        shutil.rmtree(self._tempdir, ignore_errors=True)

    def _finish(self, context):
        wm = context.window_manager
        wm.event_timer_remove(self._timer)
        wm.progress_end()
        if context.area:
            context.area.header_text_set()
        self._cleanup()

    def modal(self, context, event):
        if event.type == 'ESC':
            self._process.kill()
            self._finish(context)
            self.report({'WARNING'}, "Bake Probes cancelled, the saved light was not changed")
            return {'CANCELLED'}
        if event.type != 'TIMER':
            return {'PASS_THROUGH'}
        self._ready = probes_count(self._fresh)
        if self._total:
            context.window_manager.progress_update(100 * self._ready // self._total)
            if context.area:
                context.area.header_text_set("Bake Probes: %d of %d volumes (Esc cancels)" % (self._ready, self._total))
        if self._process.poll() is None:
            return {'PASS_THROUGH'}
        import shutil
        ok = os.path.isfile(self._fresh) and self._total and self._ready == self._total
        if os.path.isfile(self._fresh):
            shutil.copy2(self._fresh, self._target + ".tmp")
            os.replace(self._target + ".tmp", self._target)
        self._finish(context)
        if ok:
            self.report({'INFO'}, "Bake Probes: light of %d volumes saved in %s" % (self._total, self._target))
            return {'FINISHED'}
        self.report({'ERROR'}, "Bake Probes stopped at %d of %d volumes (runtime exit code %s)" %
                    (self._ready, self._total, self._process.returncode))
        return {'CANCELLED'}


class EmptyProbePanel:
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"

    @classmethod
    def poll(cls, context):
        ob = context.object
        return ob is not None and ob.type == 'EMPTY' and context.scene.render.engine == 'BLENDER_GAME'


class DATA_PT_probe_volume(EmptyProbePanel, Panel):
    bl_label = "Light Probe Volume"

    def draw_header(self, context):
        self.layout.prop(context.object, "ae_probe_volume", text="")

    def draw(self, context):
        layout = self.layout
        ob = context.object
        if not is_volume(ob):
            layout.label(text="Lights the area inside this box with bounced light from walls and floor", icon='INFO')
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

        box = layout.box()
        box.label(text="Saved Light:", icon='FILE_TICK')
        box.operator("scene.probe_volume_bake", icon='RENDER_STILL')
        path = probes_path(context.scene)
        if not path:
            box.label(text="Save the project first", icon='INFO')
        elif os.path.isfile(path):
            box.label(text="%s is ready, the game starts with it" % os.path.basename(path), icon='INFO')
        else:
            box.label(text="No saved light: the game captures it while it plays", icon='INFO')

        if ob.empty_draw_type != 'CUBE':
            layout.label(text="Display the Empty as Cube: the box is the volume", icon='ERROR')
        if any(abs(a) > 1e-3 for a in ob.matrix_world.to_euler()):
            layout.label(text="Rotation is ignored, the grid follows the world axes", icon='ERROR')


class OBJECT_PT_probe_volume_skip(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    bl_label = "Light Probe Volume"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        ob = context.object
        return (ob is not None and ob.type == 'MESH' and context.scene.render.engine == 'BLENDER_GAME' and
                any(is_volume(o) for o in context.scene.objects))

    def draw(self, context):
        box = self.layout.box()
        box.label(text="Light Probe Volume:", icon='MESH_GRID')
        skip = "probe_volume_skip" in context.object.game.properties
        box.operator("object.probe_volume_skip", text="Skip in Light Probe Volume",
                     icon='CHECKBOX_HLT' if skip else 'CHECKBOX_DEHLT', emboss=False)


classes = (
    OBJECT_OT_probe_volume_add,
    OBJECT_OT_probe_volume_toggle,
    OBJECT_OT_probe_volume_quality,
    OBJECT_OT_probe_volume_skip,
    SCENE_OT_probe_volume_bake,
    DATA_PT_probe_volume,
    OBJECT_PT_probe_volume_skip,
)

if __name__ == "__main__":  # only for live edit.
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
