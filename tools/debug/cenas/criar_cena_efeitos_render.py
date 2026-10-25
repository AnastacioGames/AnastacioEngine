# Cena de teste dos efeitos de render (plano-efeitos-render.md): SSR (esfera espelhada e rugosa),
# SSAO (cantos e escada), SSGI, névoa volumétrica e Bloom (bloco emissivo), com a câmera em vaivém na frente.
# Teclas no jogo: C pausa/retoma a órbita, 1 Low, 2 Medium, 3 High (o preset reinicia a cena).
# Uso: AnastacioEngine.exe -b --factory-startup --python criar_cena_efeitos_render.py -- saida.range
import bpy
import sys
from mathutils import Vector

saida = sys.argv[sys.argv.index("--") + 1]

scene = bpy.context.scene
for ob in list(scene.objects):
    scene.objects.unlink(ob)
    bpy.data.objects.remove(ob)
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_shading_nodes = True
scene.game_settings.use_frame_rate = True
scene.game_settings.resolution_x = 1280
scene.game_settings.resolution_y = 720


def principled(nome, cor, metal=0.0, rough=0.5):
    mat = bpy.data.materials.new(nome)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    for n in list(nodes):
        nodes.remove(n)
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (cor[0], cor[1], cor[2], 1.0)
    bsdf.inputs['Metallic'].default_value = metal
    bsdf.inputs['Roughness'].default_value = rough
    out_node = nodes.new('ShaderNodeOutputMaterial')
    mat.node_tree.links.new(bsdf.outputs[0], out_node.inputs[0])
    return mat


def emissivo(nome, cor, forca):
    mat = bpy.data.materials.new(nome)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    for n in list(nodes):
        nodes.remove(n)
    em = nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (cor[0], cor[1], cor[2], 1.0)
    em.inputs['Strength'].default_value = forca
    out_node = nodes.new('ShaderNodeOutputMaterial')
    mat.node_tree.links.new(em.outputs[0], out_node.inputs[0])
    return mat


def cubo(nome, loc, escala, mat):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    ob = bpy.context.object
    ob.name = nome
    ob.scale = escala
    ob.data.materials.append(mat)
    return ob


# Piso liso e dielétrico: reflete as esferas pelo SSR.
cubo("Piso", (0, 0, -0.1), (12, 12, 0.1), principled("PisoMat", (0.18, 0.2, 0.24), 0.0, 0.08))
# Parede e escada: cantos para o SSAO e cor forte para o SSGI rebater.
cubo("Parede", (0, -6, 2), (8, 0.2, 2), principled("ParedeMat", (0.85, 0.82, 0.75), 0.0, 0.7))
cubo("ParedeVermelha", (-6, -2, 2), (0.2, 4, 2), principled("VermelhaMat", (0.9, 0.08, 0.05), 0.0, 0.8))
for i in range(4):
    cubo("Degrau.%d" % i, (3.5, -5.2 + i * 0.6, 0.15 + i * 0.3), (1.5, 0.3 + 0.3 * (3 - i), 0.15 + i * 0.3),
         principled("DegrauMat%d" % i, (0.3 + 0.1 * i, 0.55, 0.3), 0.0, 0.6))
cubo("CaixaCanto", (-5.2, -5.2, 0.5), (0.5, 0.5, 0.5), principled("CaixaMat", (0.2, 0.4, 0.9), 0.0, 0.5))

# Esferas: espelho (riscos na borda do SSR) e rugosa (lobo GGX).
bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, size=1.2, location=(-1.6, 0, 1.2))
esp = bpy.context.object
esp.name = "EsferaEspelho"
esp.data.materials.append(principled("EspelhoMat", (0.95, 0.95, 0.95), 1.0, 0.02))
bpy.ops.object.shade_smooth()
bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, size=1.2, location=(1.6, 0, 1.2))
rug = bpy.context.object
rug.name = "EsferaRugosa"
rug.data.materials.append(principled("RugosaMat", (0.95, 0.7, 0.3), 1.0, 0.4))
bpy.ops.object.shade_smooth()

# Bloco emissivo forte para o Bloom.
cubo("Luzinha", (0, 3, 0.6), (0.4, 0.4, 0.6), emissivo("LuzinhaMat", (1.0, 0.6, 0.2), 12.0))

# Sol inclinado (névoa e sombras) e um ponto de preenchimento.
bpy.ops.object.lamp_add(type='SUN', location=(4, 4, 8))
sol = bpy.context.object
sol.rotation_euler = (Vector((0, 0, 0)) - sol.location).to_track_quat('-Z', 'Y').to_euler()
sol.data.energy = 1.5
sol.data.shadow_method = 'RAY_SHADOW'

world = bpy.data.worlds.new("Mundo")
scene.world = world
world.horizon_color = (0.45, 0.55, 0.7)
world.zenith_color = (0.15, 0.25, 0.5)
world.mist_settings.use_mist = False
world.weather_settings.use_volumetric_fog = True
world.weather_settings.vfog_density = 0.03

# Efeitos.
fx = scene.scenefx_settings
fx.quality_preset = 'MEDIUM'
fx.use_ssr = True
fx.use_ssao = True
fx.use_bloom = True
fx.use_tonemap = True
fx.use_fxaa = True
scene.ae_ssgi_use = True

# Câmera em órbita, mirando o centro.
alvo = Vector((0, -1, 1))
bpy.ops.object.camera_add(location=(0, 9, 3.5))
cam = bpy.context.object
cam.name = "Camera"
cam.data.type = 'PERSP'
cam.data.lens = 24
cam.rotation_euler = (alvo - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.camera = cam

texto = bpy.data.texts.new("teste_efeitos.py")
texto.write('''import Range, math, os, time

ALVO = (0.0, -1.0, 1.0)
RAIO = 9.0


def _log(msg):
    caminho = os.environ.get("TESTE_EFEITOS_LOG")
    if caminho:
        with open(caminho, "a") as f:
            f.write(msg + "\\n")


def tick(cont):
    own = cont.owner
    scene = Range.logic.getCurrentScene()
    kb = Range.logic.keyboard
    JA = Range.logic.KX_INPUT_JUST_ACTIVATED
    if "ini" not in own:
        # TESTE_EFEITOS_PRESET=LOW|MEDIUM|...: aplica o preset uma vez (o restart recria a cena).
        alvo = os.environ.get("TESTE_EFEITOS_PRESET")
        gd = Range.logic.globalDict
        if alvo and not gd.get("preset_aplicado"):
            gd["preset_aplicado"] = True
            scene.setQualityPreset(alvo)
            scene.restart()
            return
        own["ini"] = True
        if os.environ.get("TESTE_EFEITOS_DOF"):
            # TESTE_EFEITOS_DOF=1: foco no alvo e fundo/frente desfocados (mede o passe do DOF).
            own.useDof = True
            own.dofBlur = 12.0
            own.dofQuality = 2
            own.focusManualDistance = RAIO
            own.focusRange = 2.0
        Range.logic.globalDict["t0"] = time.time()
        own["ang"] = 0.0
        own["orbita"] = True
        _log("inicio preset=%s" % scene.getQualityPreset())
    if kb.events[Range.events.CKEY] == JA:
        own["orbita"] = not own["orbita"]
    for tecla, nome in ((Range.events.ONEKEY, "LOW"), (Range.events.TWOKEY, "MEDIUM"),
                        (Range.events.THREEKEY, "HIGH")):
        if kb.events[tecla] == JA:
            scene.setQualityPreset(nome)
            scene.restart()
            return
    if own["orbita"]:
        own["ang"] += 0.4 / 60.0
    # Vaivém na frente da cena (+-55 graus): nunca passa atrás das paredes.
    a = math.sin(own["ang"]) * 0.95
    own.worldPosition = (ALVO[0] + math.sin(a) * RAIO, ALVO[1] + math.cos(a) * RAIO, 3.5)
    own.alignAxisToVect([own.worldPosition[0] - ALVO[0], own.worldPosition[1] - ALVO[1],
                         own.worldPosition[2] - ALVO[2]], 2, 1.0)
    own.alignAxisToVect([0, 0, 1], 1, 0.3)
    seg = float(os.environ.get("TESTE_EFEITOS_SEGUNDOS", "0"))
    if seg > 0 and time.time() - Range.logic.globalDict["t0"] > seg:
        # FPS médio sem os 2 primeiros segundos (carga de shaders).
        gd = Range.logic.globalDict
        fps = (gd.get("quadros", 0) - gd.get("q2", 0)) / max(seg - 2.0, 0.1)
        _log("fim ok quadros=%d fps=%.1f" % (gd.get("quadros", 0), fps))
        Range.logic.endGame()
    gd = Range.logic.globalDict
    gd["quadros"] = gd.get("quadros", 0) + 1
    if "q2" not in gd and time.time() - Range.logic.globalDict["t0"] > 2.0:
        gd["q2"] = gd["quadros"]
''')

scene.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', object=cam.name)
bpy.ops.logic.controller_add(type='PYTHON', object=cam.name)
sens = cam.game.sensors[-1]
sens.use_pulse_true_level = True
ctrl = cam.game.controllers[-1]
ctrl.mode = 'MODULE'
ctrl.module = "teste_efeitos.tick"
sens.link(ctrl)

bpy.ops.wm.save_as_mainfile(filepath=saida)
print("salvo", saida)
