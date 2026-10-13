# Cena unica de aceite visual: junta numa so cena o que espera conferencia do usuario.
#   Tecla 1 - Nos de shader: Billboard, Strands (grama em malha subdividida), Fur normal/direcao, Explode.
#   Tecla 2 - Specular com roughness 0 (piso 0.15): esferas rough 0 / 0.15 / 0.4, dieletrico e metal.
#   Tecla 3 - Decimate Collapse 0.1: original | High Quality desligado | ligado (textura UV grid).
#   Tecla 4 - Planar Reflection (ja aceito, fica como referencia).
#   Som: World Sound com Music (2 faixas) e Ambient (vento, chiado) tocando desde o inicio.
#   Tecla 5 liga/desliga a Music, para ouvir o Ambient sozinho. Log em <pasta>/som_log.txt.
#   Esc sai.
# Uso:
#   AnastacioEngine.exe -b --factory-startup --python criar_cena_aceite_visual.py -- <pasta>
import math
import os
import struct
import sys
import wave

import bpy
from mathutils import Vector

folder = os.path.abspath(sys.argv[sys.argv.index("--") + 1])
os.makedirs(os.path.join(folder, "audio"), exist_ok=True)

scene = bpy.context.scene
for ob in list(scene.objects):
    scene.objects.unlink(ob)
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_shading_nodes = True
scene.game_settings.show_framerate_profile = False

world = bpy.data.worlds.new("World")
world.horizon_color = (0.05, 0.05, 0.08)
scene.world = world


def node_material(name):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    tree = mat.node_tree
    for n in list(tree.nodes):
        tree.nodes.remove(n)
    out = tree.nodes.new("ShaderNodeOutputMaterial")
    out.location = (600, 0)
    bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (300, 0)
    tree.links.new(bsdf.outputs[0], out.inputs["Surface"])
    return mat, tree, out, bsdf


def add(op, name, loc, mat=None, **kw):
    op(location=loc, **kw)
    ob = bpy.context.active_object
    ob.name = name
    if mat:
        ob.data.materials.append(mat)
    return ob


def label(text, loc, size=0.5):
    cu = bpy.data.curves.new("Label_" + text, 'FONT')
    cu.body = text
    cu.align_x = 'CENTER'
    cu.size = size
    ob = bpy.data.objects.new("Label_" + text, cu)
    ob.location = loc
    ob.rotation_euler = (math.radians(90), 0, 0)
    scene.objects.link(ob)
    return ob


cameras = []


def camera(name, loc, target, lens=24):
    cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
    cam.data.lens = lens
    cam.data.clip_end = 40.0
    scene.objects.link(cam)
    cam.location = loc
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cameras.append(cam)
    return cam


# ---------------- 1: nos de shader (y = 0)
mat, tree, out, bsdf = node_material("MatBillboard")
bb = tree.nodes.new("ShaderNodeBillboard")
bb.inputs["Lock Axis"].default_value = 1.0
bb.inputs["Scale"].default_value = 1.0
bsdf.inputs["Base Color"].default_value = (0.2, 0.6, 1.0, 1.0)
tree.links.new(bb.outputs["Offset"], out.inputs["Vertex Offset"])
add(bpy.ops.mesh.primitive_plane_add, "BillboardCard", (-8, 0, 1.2), mat, radius=0.8,
    rotation=(math.radians(90), 0, 0))
bpy.ops.object.transform_apply(rotation=True)  # o no espera o quad no plano local XZ
label("Billboard", (-8, 0, 2.6))

mat, tree, out, bsdf = node_material("MatStrands")
st = tree.nodes.new("ShaderNodeStrands")
st.inputs["Density"].default_value = 6.0
st.inputs["Length"].default_value = 0.3
st.inputs["Curvature"].default_value = 0.5
grad = tree.nodes.new("ShaderNodeMixRGB")  # verde escuro na base, claro na ponta
grad.inputs["Color1"].default_value = (0.05, 0.18, 0.03, 1.0)
grad.inputs["Color2"].default_value = (0.45, 0.8, 0.2, 1.0)
tree.links.new(st.outputs["Tip Factor"], grad.inputs["Fac"])
tree.links.new(grad.outputs["Color"], bsdf.inputs["Base Color"])
add(bpy.ops.mesh.primitive_grid_add, "Grama", (-4, 0, 0), mat, x_subdivisions=24, y_subdivisions=24, radius=1.5)
label("Strands", (-4, 0, 2.6))


def make_fur(name, loc, direction, strength, text):
    mat, tree, out, bsdf = node_material(name)
    mat.game_settings.alpha_blend = 'CLIP'
    fur = tree.nodes.new("ShaderNodeFurShells")
    fur.inputs["Length"].default_value = 0.25
    fur.inputs["Layers"].default_value = 10.0
    fur.inputs["Density"].default_value = 180.0
    fur.inputs["Direction"].default_value = direction
    fur.inputs["Direction Strength"].default_value = strength
    bsdf.inputs["Base Color"].default_value = (0.45, 0.28, 0.12, 1.0)
    mix = tree.nodes.new("ShaderNodeMixShader")
    transp = tree.nodes.new("ShaderNodeBsdfTransparent")
    tree.links.new(fur.outputs["Alpha"], mix.inputs["Fac"])
    tree.links.new(transp.outputs[0], mix.inputs[1])
    tree.links.new(bsdf.outputs[0], mix.inputs[2])
    tree.links.new(mix.outputs[0], out.inputs["Surface"])
    add(bpy.ops.mesh.primitive_uv_sphere_add, name, loc, mat)
    bpy.ops.object.shade_smooth()
    label(text, (loc[0], 0, 2.6))


make_fur("FurNormal", (0, 0, 1.2), (0.0, 0.0, 0.0), 0.0, "Fur normal")
make_fur("FurDirecao", (4, 0, 1.2), (1.0, 0.0, 0.0), 1.0, "Fur direcao +X")

mat, tree, out, bsdf = node_material("MatExplode")
ex = tree.nodes.new("ShaderNodeExplode")
ex.inputs["Factor"].default_value = 0.4
tree.links.new(ex.outputs["Amount"], bsdf.inputs["Metallic"])
add(bpy.ops.mesh.primitive_cube_add, "Destroco", (8, 0, 1.0), mat)
label("Explode", (8, 0, 2.6))
camera("Cam1_Nos", (0, -18, 6), (0, 0, 1.0), lens=18)

# ---------------- 2: specular (y = 20)
for col, rough in enumerate((0.0, 0.15, 0.4)):
    for row, metal in enumerate((0.0, 1.0)):
        mat, tree, out, bsdf = node_material("MatSpec_r%.2f_m%d" % (rough, metal))
        bsdf.inputs["Base Color"].default_value = (0.8, 0.1, 0.1, 1.0) if metal == 0 else (0.9, 0.75, 0.3, 1.0)
        bsdf.inputs["Roughness"].default_value = rough
        bsdf.inputs["Metallic"].default_value = metal
        add(bpy.ops.mesh.primitive_uv_sphere_add, "Spec_%d_%d" % (col, row),
            (-3 + col * 3, 100, 1 + row * 2.5), mat, segments=48, ring_count=24)
        bpy.ops.object.shade_smooth()
    label("rough %.2f" % rough, (-3 + col * 3, 100, -0.6), 0.4)
camera("Cam2_Specular", (0, 91, 2.2), (0, 100, 2.2), lens=28)

# ---------------- 3: decimate (y = 40)
img = bpy.data.images.new("UVGrid", 1024, 1024)
img.generated_type = 'UV_GRID'
mat, tree, out, bsdf = node_material("MatUV")
tex = tree.nodes.new("ShaderNodeTexImage")
tex.image = img
tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
for i, (name, ratio, quality) in enumerate((("Original", None, None),
                                            ("HQ desligado", 0.1, False),
                                            ("HQ ligado", 0.1, True))):
    ob = add(bpy.ops.mesh.primitive_monkey_add, "Dec_" + str(i), (-3.5 + i * 3.5, 200, 1.2), mat)
    bpy.ops.object.modifier_add(type='SUBSURF')
    ob.modifiers[-1].levels = 2
    bpy.ops.object.modifier_apply(modifier=ob.modifiers[-1].name)
    bpy.ops.object.shade_smooth()
    if ratio:
        m = ob.modifiers.new("Decimate", 'DECIMATE')
        m.decimate_type = 'COLLAPSE'
        m.ratio = ratio
        m.use_collapse_quality = quality
    label(name, (-3.5 + i * 3.5, 200, 2.6), 0.4)
camera("Cam3_Decimate", (0, 192, 2.2), (0, 200, 1.4), lens=28)

# ---------------- 4: planar reflection (y = 60)
mat, tree, out, bsdf = node_material("MatEspelho")
pl = tree.nodes.new("ShaderNodePlanarReflection")
pl.inputs["Enable"].default_value = True
pl.inputs["Resolution"].default_value = 1024
pl.inputs["Clip End"].default_value = 50.0
tree.nodes.remove(bsdf)
em = tree.nodes.new("ShaderNodeEmission")
tree.links.new(pl.outputs["Color"], em.inputs["Color"])
tree.links.new(em.outputs[0], out.inputs["Surface"])
add(bpy.ops.mesh.primitive_plane_add, "Espelho", (0, 300, 0), mat, radius=3.0)
mat, tree, out, bsdf = node_material("MatCubo")
bsdf.inputs["Base Color"].default_value = (0.9, 0.2, 0.1, 1.0)
add(bpy.ops.mesh.primitive_cube_add, "CuboEspelho", (0, 300, 2.0), mat)
camera("Cam4_Espelho", (0, 291, 5), (0, 300, 0.5), lens=28)

# luz
lamp = bpy.data.lamps.new("Sun", 'SUN')
sun = bpy.data.objects.new("Sun", lamp)
scene.objects.link(sun)
sun.rotation_euler = (0.8, 0.2, 0.6)
scene.camera = cameras[0]


# ---------------- World Sound
def write_tone(path, frequency, seconds, tremolo=0.0):
    rate = 22050
    frames = bytearray()
    for i in range(int(rate * seconds)):
        t = i / rate
        gain = 0.25 * (1.0 - tremolo * (0.5 + 0.5 * math.sin(2.0 * math.pi * 3.0 * t)))
        frames += struct.pack('<h', int(32767 * gain * math.sin(2.0 * math.pi * frequency * t)))
    w = wave.open(path, 'wb')
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(rate)
    w.writeframes(bytes(frames))
    w.close()


write_tone(os.path.join(folder, "audio", "tema1.wav"), 440.0, 3.0)
write_tone(os.path.join(folder, "audio", "tema2.wav"), 660.0, 3.0)
def write_wind(path, seconds):
    import random
    rate = 22050
    rnd = random.Random(1)
    frames = bytearray()
    low = 0.0
    n = int(rate * seconds)
    for i in range(n):
        t = i / rate
        low += 0.15 * (rnd.uniform(-1.0, 1.0) - low)  # ruido suavizado = chiado de vento
        # rajadas; termina igual ao inicio para o loop nao estalar
        gust = 0.55 + 0.45 * math.sin(2.0 * math.pi * t / seconds) ** 2
        frames += struct.pack('<h', int(32767 * 0.8 * gust * low))
    w = wave.open(path, 'wb')
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(rate)
    w.writeframes(bytes(frames))
    w.close()


write_wind(os.path.join(folder, "audio", "vento.wav"), 4.0)
music = world.sound_modules.new("Music", type='MUSIC')
music.fade_time = 0.5
music.sounds.new("tema1", filepath="//audio/tema1.wav")
music.sounds.new("tema2", filepath="//audio/tema2.wav")
ambient = world.sound_modules.new("Ambient", type='AMBIENT')
ambient.volume = 1.0
ambient.sounds.new("vento", filepath="//audio/vento.wav")

# ---------------- troca de camera nas teclas 1-4
text = bpy.data.texts.new("cams.py")
text.from_string('''import bge

KEYS = (bge.events.ONEKEY, bge.events.TWOKEY, bge.events.THREEKEY, bge.events.FOURKEY)
NAMES = %r

def _log(text):
    with open(bge.logic.expandPath("//som_log.txt"), "a") as f:
        f.write(text + "
")

def tick(cont):
    scene = bge.logic.getCurrentScene()
    keys = bge.logic.keyboard.events
    own = cont.owner
    if "logged" not in own:
        own["logged"] = True
        _log("inicio modulos=%%s music=%%s ambient=%%s" %% (bge.audio.modules(), bge.audio.playing("Music"),
                                                       bge.audio.playing("Ambient")))
    if keys[bge.events.FIVEKEY] == bge.logic.KX_INPUT_JUST_ACTIVATED:
        if bge.audio.playing("Music"):
            bge.audio.stop("Music")
        else:
            bge.audio.play("Music")
        _log("tecla5 music=%%s ambient=%%s" %% (bge.audio.playing("Music"), bge.audio.playing("Ambient")))
    for key, name in zip(KEYS, NAMES):
        if keys[key] == bge.logic.KX_INPUT_JUST_ACTIVATED:
            scene.active_camera = scene.objects[name]
''' % [c.name for c in cameras])
ctrl = cameras[0]
scene.objects.active = ctrl
bpy.ops.logic.sensor_add(type='KEYBOARD', object=ctrl.name)
bpy.ops.logic.controller_add(type='PYTHON', object=ctrl.name)
s = ctrl.game.sensors[-1]
s.use_all_keys = True
c = ctrl.game.controllers[-1]
c.mode = 'MODULE'
c.module = 'cams.tick'
s.link(c)
# Always (uma vez) para o log do inicio sair sem precisar apertar tecla
bpy.ops.logic.sensor_add(type='ALWAYS', object=ctrl.name)
ctrl.game.sensors[-1].link(c)

path = os.path.join(folder, "aceite_visual.range")
bpy.ops.wm.save_as_mainfile(filepath=path)
print("CENA_SALVA", path)
