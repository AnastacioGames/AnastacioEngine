"""Native desktop SSGI controls. Scene ID properties avoid a DNA/file-format change."""
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty


QUALITY_PRESETS = {
    'LOW': {
        'label': "Low",
        'radius': 3.0, 'strength': 1.0, 'rays': 4, 'steps': 8,
        'divisor': 4, 'thickness': 0.1, 'denoise': 'HIGH',
    },
    'MEDIUM': {
        'label': "Medium",
        'radius': 3.0, 'strength': 1.0, 'rays': 6, 'steps': 12,
        'divisor': 2, 'thickness': 0.1, 'denoise': 'HIGH',
    },
    'HIGH': {
        'label': "High",
        'radius': 3.0, 'strength': 1.0, 'rays': 8, 'steps': 16,
        'divisor': 1, 'thickness': 0.1, 'denoise': 'NORMAL',
    },
    # The trace shader accepts up to 16 rays and 32 steps. Keep the most
    # expensive preset opt-in, for still or slow desktop scenes.
    'ULTRA': {
        'label': "Ultra",
        'radius': 3.0, 'strength': 1.0, 'rays': 12, 'steps': 24,
        'divisor': 1, 'thickness': 0.1, 'denoise': 'NORMAL',
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
            scene.ae_ssgi_denoise = preset['denoise']
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


# Mirrors gpu_ssgi_closure() in gpu_material.c: keep both in sync.
_SSGI_ROOTS = {'BSDF_PRINCIPLED', 'BSDF_DIFFUSE', 'EMISSION'}
_SSGI_EMPTY = {'BSDF_TRANSPARENT', 'HOLDOUT'}
_SSGI_SPECULAR = {'BSDF_GLOSSY', 'BSDF_GLASS', 'BSDF_REFRACTION', 'BSDF_ANISOTROPIC'}
_SSGI_BLEND = {'OPAQUE', 'CLIP'}

# Last "Check Scene" result shown by the panel:
# (full, approximated, excluded, [(material, reason, is_excluded)]).
check_result = None


def _linked_node(socket):
    """Node feeding a socket, through reroutes and into node groups, like the GPU graph."""
    while socket.is_linked:
        node = socket.links[0].from_node
        if node.type == 'REROUTE':
            socket = node.inputs[0]
        elif node.type == 'GROUP' and node.node_tree:
            out = next((n for n in node.node_tree.nodes if n.type == 'GROUP_OUTPUT'), None)
            name = socket.links[0].from_socket.name
            if out is None or name not in out.inputs:
                return None
            socket = out.inputs[name]
        elif node.type == 'GROUP_INPUT':
            return None
        else:
            return node
    return None


def _closure_state(node, approximate):
    """'full', 'partial' (approximated closure) or None (excluded), plus the node that decided it."""
    if node is None or node.type in _SSGI_ROOTS or node.type in _SSGI_EMPTY:
        return 'full', None
    if node.type in {'MIX_SHADER', 'ADD_SHADER'}:
        shaders = [sock for sock in node.inputs if sock.type == 'SHADER']
        states = [_closure_state(_linked_node(sock), approximate) for sock in shaders]
        for state in ('excluded', 'partial'):
            hit = next((st for st in states if (st[0] or 'excluded') == state), None)
            if hit:
                return hit
        return 'full', None
    return ('partial' if approximate else None), node


def ssgi_material_issue(ma, approximate=True):
    """None when the material fully writes SSGI data, else (excluded, short reason)."""
    blend = ma.game_settings.alpha_blend
    if blend not in _SSGI_BLEND:
        return True, "transparency (%s)" % blend.replace('_', ' ').title()
    if not ma.use_nodes or not ma.node_tree:
        return None
    tree = ma.node_tree
    output = next((n for n in tree.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output), None)
    output = output or next((n for n in tree.nodes if n.type == 'OUTPUT_MATERIAL'), None)
    if output is None:
        return True, "no Material Output"
    state, node = _closure_state(_linked_node(output.inputs['Surface']), approximate)
    if state == 'full':
        return None
    if state == 'partial':
        what = "blocks rays only" if node.type in _SSGI_SPECULAR else "approximate color"
        return False, "%s: %s" % (node.bl_label, what)
    return True, "%s node (Approximate Unsupported is off)" % node.bl_label


class SCENE_OT_anastacio_ssgi_check(bpy.types.Operator):
    """List the materials in this Scene that Native SSGI approximates or cannot use, and why"""
    bl_idname = "scene.anastacio_ssgi_check"
    bl_label = "Check Scene"

    def execute(self, context):
        global check_result
        scene = context.scene
        materials = {slot.material for ob in scene.objects if ob.type == 'MESH'
                     for slot in ob.material_slots if slot.material}
        issues = sorted((excluded, ma.name, reason) for ma in materials
                        for issue in (ssgi_material_issue(ma, scene.ae_ssgi_approximate),) if issue
                        for excluded, reason in (issue,))
        partial = sum(1 for issue in issues if not issue[0])
        excluded = len(issues) - partial
        check_result = (len(materials) - len(issues), partial, excluded,
                        [(name, reason, ex) for ex, name, reason in sorted(issues, key=lambda i: (not i[0], i[1]))])
        self.report({'INFO'}, "Native SSGI: %d full, %d approximate, %d excluded"
                    % (check_result[0], partial, excluded))
        return {'FINISHED'}


classes = (SCENE_OT_anastacio_ssgi_quality, SCENE_OT_anastacio_ssgi_enable_nodes,
           SCENE_OT_anastacio_ssgi_check)


def register_props():
    bpy.types.Scene.ae_ssgi_use = BoolProperty(name="Native SSGI", default=False,
        description="Screen-space indirect light for opaque and Alpha Clip materials (desktop); enable before Play")
    bpy.types.Scene.ae_ssgi_approximate = BoolProperty(name="Approximate Unsupported", default=True,
        description="Node graphs without SSGI data still receive bounce light using their color "
                    "(specular ones only block rays); enable before Play")
    bpy.types.Scene.ae_ssgi_show_help = BoolProperty(name="Limits", default=False,
        description="Show Native SSGI limitations")
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
    # Enum numbers are read by KX_Scene.cpp from the IDProperty: keep 0/1/2.
    bpy.types.Scene.ae_ssgi_denoise = EnumProperty(name="Denoise", default='NORMAL', items=(
        ('OFF', "Off", "Edge-aware upsampling only; sharpest, noisiest", 0),
        ('NORMAL', "Normal", "5x5 edge-aware filter", 1),
        ('HIGH', "High", "7x7 edge-aware filter; smoothest, for few rays or low resolution", 2),
    ), description="Smooths SSGI noise while keeping edges; enable before Play", update=_mark_custom)


def unregister_props():
    for name in ('use', 'approximate', 'show_help', 'quality', 'radius', 'strength', 'rays', 'steps', 'divisor', 'thickness', 'denoise'):
        delattr(bpy.types.Scene, 'ae_ssgi_' + name)
