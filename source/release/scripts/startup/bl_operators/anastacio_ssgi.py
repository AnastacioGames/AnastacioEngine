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


class SCENE_OT_anastacio_ssgi_enable_nodes(bpy.types.Operator):
    """Enable PBR Shading Nodes, required by Native SSGI (changes how every material is shaded)"""
    bl_idname = "scene.anastacio_ssgi_enable_nodes"
    bl_label = "Enable PBR Shading Nodes"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        context.scene.game_settings.use_shading_nodes = True
        return {'FINISHED'}


# Mirrors GPU_material_ssgi_outputs() in gpu_material.c: keep both in sync.
_SSGI_ROOTS = {'BSDF_PRINCIPLED', 'BSDF_DIFFUSE', 'EMISSION'}
_SSGI_BLEND = {'OPAQUE'}

# Last "Check Scene" result shown by the panel: (participating, [(material, reason)]).
check_result = None


def _surface_node(tree):
    output = next((n for n in tree.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output), None)
    if output is None:
        output = next((n for n in tree.nodes if n.type == 'OUTPUT_MATERIAL'), None)
    if output is None or not output.inputs['Surface'].is_linked:
        return None
    node = output.inputs['Surface'].links[0].from_node
    while node.type == 'REROUTE' and node.inputs[0].is_linked:
        node = node.inputs[0].links[0].from_node
    return node


def ssgi_material_issue(ma):
    """None when the material writes SSGI data, else a short reason."""
    blend = ma.game_settings.alpha_blend
    if blend not in _SSGI_BLEND:
        return "transparency (%s)" % blend.replace('_', ' ').title()
    if not ma.use_nodes or not ma.node_tree:
        return None
    node = _surface_node(ma.node_tree)
    if node is None:
        return "nothing linked to Material Output"
    if node.type not in _SSGI_ROOTS:
        return "%s node on Output" % node.bl_label
    return None


class SCENE_OT_anastacio_ssgi_check(bpy.types.Operator):
    """List the materials in this Scene that Native SSGI cannot use, and why"""
    bl_idname = "scene.anastacio_ssgi_check"
    bl_label = "Check Scene"

    def execute(self, context):
        global check_result
        materials = {slot.material for ob in context.scene.objects if ob.type == 'MESH'
                     for slot in ob.material_slots if slot.material}
        issues = sorted((ma.name, reason) for ma in materials
                        for reason in (ssgi_material_issue(ma),) if reason)
        check_result = (len(materials) - len(issues), issues)
        self.report({'INFO'}, "Native SSGI: %d of %d materials participate" % (check_result[0], len(materials)))
        return {'FINISHED'}


classes = (SCENE_OT_anastacio_ssgi_quality, SCENE_OT_anastacio_ssgi_enable_nodes,
           SCENE_OT_anastacio_ssgi_check)


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
