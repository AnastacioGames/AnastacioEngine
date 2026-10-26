"""PCSS cai para sombra dura nos presets Low e Very Low.

Gera pcss_<preset>.range com um sol (PCF Penumbra, Soft 1) e materiais clássico e Principled.
Com RANGE_SHADER_LOG, os shaders do Low/Very Low não devem ter a flag SHADOW_PCSS (0x400);
os do Medium/High devem ter.

    AnastacioEngine -b --python tools/debug/cenas/criar_teste_pcss_preset.py -- PASTA
    set PCSS_FRAMES=5 && set RANGE_NO_SHADER_CACHE=1 && set RANGE_SHADER_LOG=log.txt
    AnastacioRuntime --server PASTA/pcss_LOW.range
"""
import bpy, sys, os
from mathutils import Vector

out = sys.argv[sys.argv.index("--") + 1]
for preset in ("VERY_LOW", "LOW", "MEDIUM", "HIGH"):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_GAME'
    sc.game_settings.use_shading_nodes = True

    m = bpy.data.materials.new("PBR")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    nt.links.new(nt.nodes.new('ShaderNodeBsdfPrincipled').outputs[0],
                 nt.nodes.new('ShaderNodeOutputMaterial').inputs[0])
    classic = bpy.data.materials.new("Classic")

    bpy.ops.mesh.primitive_plane_add(radius=10)
    bpy.context.object.data.materials.append(m)
    bpy.ops.mesh.primitive_cube_add(location=(0, 0, 1))
    bpy.context.object.data.materials.append(classic)

    la = bpy.data.lamps.new("Sun", 'SUN')
    la.use_shadow = True
    la.shadow_filter = 'PCF_PENUMBRA'
    la.shadow_buffer_soft = 1.0
    sun = bpy.data.objects.new("Sun", la)
    sc.objects.link(sun)
    sun.location = (0, 0, 10)
    sun.rotation_euler = (0.6, 0.2, 0.3)

    cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    sc.objects.link(cam)
    cam.location = (0, -10, 6)
    cam.rotation_euler = (Vector((0, 0, 0)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.camera = cam
    sc.scenefx_settings.quality_preset = preset

    t = bpy.data.texts.new("fim.py")
    t.write('''import Range, os
own = Range.logic.getCurrentController().owner
own["f"] = own.get("f", 0) + 1
if os.environ.get("PCSS_FRAMES") and own["f"] >= int(os.environ["PCSS_FRAMES"]):
    Range.logic.endGame()
''')
    sc.objects.active = cam
    bpy.ops.logic.sensor_add(type='ALWAYS', name="A", object=cam.name)
    s = cam.game.sensors["A"]
    s.use_pulse_true_level = True
    bpy.ops.logic.controller_add(type='PYTHON', name="P", object=cam.name)
    c = cam.game.controllers["P"]
    c.text = t
    s.link(c)
    print("PRESET", preset, "samples", la.shadow_buffer_samples)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "pcss_%s.range" % preset), check_existing=False)
