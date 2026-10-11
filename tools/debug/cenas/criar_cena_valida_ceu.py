"""Cena de validacao visual - CEU / NUVENS (varios itens de uma vez).

Rodar:
  AnastacioEngine -b --factory-startup --python tools/debug/cenas/criar_cena_valida_ceu.py -- <saida.range>

Modo padrao: Sky Layers (Ceu em Camadas) + Clouds LIGADOS juntos:
  -> validar que as duas camadas COMPOEM (nao se excluem) - commits 86232060 / f4705337.
  Sky Layers em laranja, nuvens em branco. Tecla 2 liga/desliga so as nuvens brancas (setWeather);
  o laranja tem que continuar.
Modo "vclouds" (2o arg): liga SO as Volumetric Clouds (raymarch real); Sky Layers e Clouds
desligadas, mas com cobertura > 0, para pegar o bug em que a Volumetric acendia as layers junto.
Tecla 2 liga as nuvens brancas por cima, p/ conferir que a combinacao continua funcionando.
O chao e um poste servem de referencia; a camera olha pro horizonte/ceu.
"""
import bpy
import sys
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "valida_ceu.range"
modo = argv[1] if len(argv) > 1 else "layers"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 1280
scene.game_settings.resolution_y = 720
scene.game_settings.use_shading_nodes = True

world = bpy.data.worlds.new("ValidaCeu World")
world.horizon_color = (0.35, 0.55, 0.85)
world.zenith_color = (0.1, 0.25, 0.6)
world.use_sky_blend = True
world.mist_settings.use_mist = False
scene.world = world

ws = world.weather_settings
# Sky Layers (Ceu em Camadas)
ws.use_sky_layers = (modo != "vclouds")
ws.sky_layer_coverage = 0.5
ws.sky_layer_scale = 2.0
ws.sky_layer_speed = 0.3
ws.sky_layer_color = (1.0, 0.6, 0.35)  # laranja: distingue das nuvens brancas
# Nuvens procedurais classicas (devem compor junto com as layers)
ws.use_clouds = (modo != "vclouds")
ws.cloud_coverage = 0.5
ws.cloud_scale = 1.5
ws.cloud_speed = 0.3
ws.cloud_color = (1.0, 1.0, 1.0)
# Volumetric Clouds: so no modo "vclouds".
try:
    ws.use_volumetric_clouds = (modo == "vclouds")
    ws.vcloud_coverage = 0.5
    ws.vcloud_density = 0.6
    ws.vcloud_altitude = 200.0
    ws.vcloud_thickness = 120.0
    ws.vcloud_quality = 'MEDIUM'
except Exception as e:
    print("vclouds nao disponivel:", e)

# Chao de referencia.
bpy.ops.mesh.primitive_plane_add(location=(0, 0, 0))
ground = bpy.context.object
ground.scale = (40, 40, 1)
gmat = bpy.data.materials.new("GroundMat")
gmat.use_nodes = True
gt = gmat.node_tree
gt.nodes.clear()
gout = gt.nodes.new("ShaderNodeOutputMaterial")
gdiff = gt.nodes.new("ShaderNodeBsdfDiffuse")
gdiff.inputs["Color"].default_value = (0.25, 0.3, 0.2, 1.0)
gt.links.new(gdiff.outputs[0], gout.inputs["Surface"])
ground.data.materials.append(gmat)

# Poste branco de referencia.
bpy.ops.mesh.primitive_cylinder_add(location=(3, 2, 2.5), radius=0.3, depth=5)
poste = bpy.context.object
pmat = bpy.data.materials.new("Poste")
pmat.diffuse_color = (0.9, 0.9, 0.9)
poste.data.materials.append(pmat)

bpy.ops.object.lamp_add(type='SUN', location=(6, -8, 12))
sun = bpy.context.object
sun.rotation_euler = (0.6, 0.2, 0.5)

# Camera olhando pro horizonte (ceu ocupa a metade de cima).
cam_loc = Vector((0.0, -14.0, 3.0))
alvo = Vector((0.0, 10.0, 7.0))
bpy.ops.object.camera_add(location=cam_loc)
cam = bpy.context.object
cam.data.type = 'PERSP'
cam.data.lens = 20
cam.rotation_euler = (alvo - cam_loc).to_track_quat('-Z', 'Y').to_euler()
scene.camera = cam

# Tecla 2 liga/desliga as nuvens procedurais (setWeather) p/ comparar com as Sky Layers.
text = bpy.data.texts.new("toggle_ceu.py")
text.write('''import bge
kb = bge.logic.keyboard
JUST = bge.logic.KX_INPUT_JUST_ACTIVATED
w = bge.logic.getCurrentScene().world

if kb.events[bge.events.TWOKEY] == JUST:
    try:
        # flags de clima so aceitam bool; 0.0/1.0 cai em "unknown setting"
        atual = w.getWeather("clouds")
        w.setWeather("clouds", not atual)
        print("clouds ->", w.getWeather("clouds"))
    except Exception as e:
        print("setWeather indisponivel:", e)
''')
scene.objects.active = cam
bpy.ops.logic.sensor_add(type='KEYBOARD', object=cam.name)
sens = cam.game.sensors[-1]
sens.use_all_keys = True
bpy.ops.logic.controller_add(type='PYTHON', object=cam.name)
cont = cam.game.controllers[-1]
cont.text = text
sens.link(cont)

bpy.ops.wm.save_as_mainfile(filepath=output)
print("Saved", output)
