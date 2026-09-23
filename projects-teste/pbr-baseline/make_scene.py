# Cria pbr_test.blend: grade de esferas Principled (roughness x metallic), chao, Sun e camera fixa.
# Uso: RangeEngine.exe -b --python make_scene.py
import bpy, math, os

here = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
out = os.path.join(here, "pbr_test.blend")

bpy.ops.wm.read_factory_settings(use_empty=True)
scn = bpy.context.scene
scn.render.engine = 'BLENDER_RENDER'
gs = scn.game_settings
gs.use_glsl_shaders = True
gs.use_glsl_nodes = True
gs.use_glsl_lights = True
gs.use_glsl_shadows = True
gs.use_glsl_extra_textures = True
gs.use_glsl_environment_lighting = False
scn.render.resolution_x = 1280
scn.render.resolution_y = 720
scn.world = bpy.data.worlds.new("World")
scn.world.horizon_color = (0.35, 0.45, 0.6)
scn.world.zenith_color = (0.15, 0.25, 0.5)
scn.world.ambient_color = (0.05, 0.05, 0.05)

def principled(name, color, metallic, roughness):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out_n = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = color
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['Roughness'].default_value = roughness
    nt.links.new(bsdf.outputs[0], out_n.inputs['Surface'])
    return m

metals = [0.0, 0.5, 1.0]
roughs = [0.1, 0.3, 0.5, 0.7, 0.9]
for j, me in enumerate(metals):
    for i, ro in enumerate(roughs):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, size=0.45,
                                             location=((i - 2) * 1.1, 0, (1 - j) * 1.1 + 0.9))
        o = bpy.context.object
        o.name = "S_m%.1f_r%.1f" % (me, ro)
        bpy.ops.object.shade_smooth()
        o.data.materials.append(principled(o.name, (0.8, 0.35, 0.2, 1.0), me, ro))

bpy.ops.mesh.primitive_plane_add(radius=8, location=(0, 0, -1.2))
plane = bpy.context.object
plane.name = "Chao"
plane.data.materials.append(principled("Chao", (0.5, 0.5, 0.5, 1.0), 0.0, 0.8))

bpy.ops.object.lamp_add(type='SUN', location=(4, -6, 8))
sun = bpy.context.object
sun.rotation_euler = (math.radians(50), 0, math.radians(35))
sun.data.energy = 1.2

bpy.ops.object.camera_add(location=(0, -8.5, 1.3), rotation=(math.radians(90), 0, 0))
cam = bpy.context.object
cam.name = "Camera"
scn.camera = cam

# Script de captura: espera alguns frames, salva screenshot e encerra o jogo.
txt = bpy.data.texts.new("shot.py")
txt.write('''import bge, os
def main(cont):
    own = cont.owner
    own["f"] = own.get("f", 0) + 1
    if own["f"] == 30:
        path = bge.logic.globalDict.get("shot_path") or os.environ.get("PBR_SHOT", "shot.png")
        bge.render.makeScreenshot(path)
    if own["f"] == 45:
        bge.logic.endGame()
''')
bpy.context.scene.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', object=cam.name)
bpy.ops.logic.controller_add(type='PYTHON', object=cam.name)
s = cam.game.sensors[-1]
c = cam.game.controllers[-1]
c.mode = 'MODULE'
c.module = "shot.main"
c.link(sensor=s)
s.use_pulse_true_level = True

bpy.ops.wm.save_as_mainfile(filepath=out)
print("SALVO", out)
