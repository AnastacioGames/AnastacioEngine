"""Native desktop SSGI controls. Scene ID properties avoid a DNA/file-format change."""
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty


QUALITY_PRESETS = {
    'LOW': {
        'label': "Low",
        'radius': 3.0, 'strength': 1.0, 'rays': 4, 'steps': 8,
        'divisor': 4, 'thickness': 0.1,
    },
    'MEDIUM': {
        'label': "Medium",
        'radius': 3.0, 'strength': 1.0, 'rays': 6, 'steps': 12,
        'divisor': 2, 'thickness': 0.1,
    },
    'HIGH': {
        'label': "High",
        'radius': 3.0, 'strength': 1.0, 'rays': 8, 'steps': 16,
        'divisor': 1, 'thickness': 0.1,
    },
    # The trace shader accepts up to 16 rays and 32 steps. Keep the most
    # expensive preset opt-in, for still or slow desktop scenes.
    'ULTRA': {
        'label': "Ultra",
        'radius': 3.0, 'strength': 1.0, 'rays': 12, 'steps': 24,
        'divisor': 1, 'thickness': 0.1,
    },
}

_applying_preset = False


def _mark_custom(scene, context):
    """Keep the label honest when an advanced setting changes by hand."""
    if not _applying_preset and hasattr(scene, 'ae_ssgi_quality'):
        scene.ae_ssgi_quality = 'CUSTOM'


class SCENE_OT_anastacio_ssgi_quality(bpy.types.Operator):
    """Apply an SSGI quality preset to this Scene"""
    bl_idname = "scene.anastacio_ssgi_quality"
    bl_label = "Apply Native SSGI Quality"
    bl_options = {'REGISTER', 'UNDO'}

    quality: EnumProperty(
        name="Quality",
        items=[(key, preset['label'], "Apply the %s Native SSGI preset" % preset['label'])
               for key, preset in QUALITY_PRESETS.items()],
        default='MEDIUM')

    def execute(self, context):
        global _applying_preset
        scene = context.scene
        preset = QUALITY_PRESETS[self.quality]
        _applying_preset = True
        try:
            scene.ae_ssgi_radius = preset['radius']
            scene.ae_ssgi_strength = preset['strength']
            scene.ae_ssgi_rays = preset['rays']
            scene.ae_ssgi_steps = preset['steps']
            scene.ae_ssgi_divisor = preset['divisor']
            scene.ae_ssgi_thickness = preset['thickness']
            scene.ae_ssgi_quality = self.quality
        finally:
            _applying_preset = False
        self.report({'INFO'}, "Native SSGI quality: %s" % preset['label'])
        return {'FINISHED'}


classes = (SCENE_OT_anastacio_ssgi_quality,)


def register_props():
    bpy.types.Scene.ae_ssgi_use = BoolProperty(name="Native SSGI", default=False,
        description="Screen-space indirect light for opaque Principled materials (desktop); enable before Play")
    bpy.types.Scene.ae_ssgi_show_help = BoolProperty(name="Requirements & Limits", default=False,
        description="Show Native SSGI requirements and limitations")
    bpy.types.Scene.ae_fast_shader_show_help = BoolProperty(name="Gain & Loss", default=True,
        description="Show what Fast Shader Loading gains and loses")
    bpy.types.Scene.ae_ssgi_quality = EnumProperty(name="Quality", default='CUSTOM', items=(
        ('LOW', "Low", "4 rays, 8 steps, quarter resolution"),
        ('MEDIUM', "Medium", "6 rays, 12 steps, half resolution"),
        ('HIGH', "High", "8 rays, 16 steps, full resolution"),
        ('ULTRA', "Ultra", "12 rays, 24 steps, full resolution; desktop GPU intensive"),
        ('CUSTOM', "Custom", "Manual Native SSGI settings"),
    ), description="Last Native SSGI preset applied to this Scene")
    bpy.types.Scene.ae_ssgi_radius = FloatProperty(name="Radius", default=3.0, min=0.01, max=100.0,
        description="Maximum ray distance in world units", update=_mark_custom)
    bpy.types.Scene.ae_ssgi_strength = FloatProperty(name="Strength", default=1.0, min=0.0, max=4.0,
        update=_mark_custom)
    bpy.types.Scene.ae_ssgi_rays = IntProperty(name="Rays", default=4, min=1, max=16, update=_mark_custom)
    bpy.types.Scene.ae_ssgi_steps = IntProperty(name="Steps", default=8, min=2, max=32, update=_mark_custom)
    bpy.types.Scene.ae_ssgi_divisor = IntProperty(name="Resolution Divisor", default=2, min=1, max=4,
        description="1 = full resolution, 2 = half width and height, 4 = quarter", update=_mark_custom)
    bpy.types.Scene.ae_ssgi_thickness = FloatProperty(name="Thickness", default=0.1, min=0.001, max=10.0,
        description="Depth intersection tolerance; high values can leak light", update=_mark_custom)


def unregister_props():
    for name in ('use', 'show_help', 'quality', 'radius', 'strength', 'rays', 'steps', 'divisor', 'thickness'):
        delattr(bpy.types.Scene, 'ae_ssgi_' + name)
