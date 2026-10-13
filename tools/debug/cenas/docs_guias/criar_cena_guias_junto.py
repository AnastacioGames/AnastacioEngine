# Uma cena só com os exemplos de clima, câmera, Load Mode e receitas, para conferir na tela.
# Teclas aparecem no canto da tela. Código dos componentes vem direto dos guias.
# Uso: AnastacioEngine.exe -b --factory-startup -P criar_cena_guias_junto.py -- <pasta de saida> <pasta dos guias>
import bpy
import os
import re
import sys
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
out_dir, guias = argv[0], argv[1]
sys.path.insert(0, out_dir)


def blocos(nome):
    with open(os.path.join(guias, nome + ".md"), encoding="utf-8") as f:
        return re.findall(r"```python\n(.*?)```", f.read(), re.S)


def material(ob, cor):
    m = bpy.data.materials.new(ob.name + "_mat")
    m.diffuse_color = cor
    ob.data.materials.append(m)


def malha(op, nome, loc, cor, camada=0, **kw):
    camadas = [i == camada for i in range(20)]
    op(location=loc, layers=camadas, **kw)
    ob = bpy.context.object
    ob.name = nome
    material(ob, cor)
    return ob


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.layers[0] = True
w = bpy.data.worlds.new("World")
w.mist_settings.use_mist = False
w.horizon_color = (0.35, 0.4, 0.5)
w.weather_settings.use_rain = True
scene.world = w

malha(bpy.ops.mesh.primitive_plane_add, "Chao", (0, 0, 0), (0.35, 0.35, 0.35), radius=15)
cubo = malha(bpy.ops.mesh.primitive_cube_add, "Cubo", (0, 0, 1), (0.9, 0.2, 0.1))
chefe = malha(bpy.ops.mesh.primitive_uv_sphere_add, "Chefe", (4, 2, 1.5), (0.1, 0.3, 0.9), size=1.5)
chefe.game_load_mode = 'ON_DEMAND'
tiro = malha(bpy.ops.mesh.primitive_cone_add, "Tiro", (0, 0, 0), (0.95, 0.9, 0.1), camada=1)
tiro.game_load_mode = 'ON_DEMAND'
arma = malha(bpy.ops.mesh.primitive_cylinder_add, "Arma", (-4, 2, 1), (0.2, 0.8, 0.2))

sun = bpy.data.objects.new("Sun", bpy.data.lamps.new("Sun", 'SUN'))
sun.rotation_euler = (0.6, 0.2, 0.4)
scene.objects.link(sun)
cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
cam.location = (0, -14, 6)
cam.rotation_euler = (Vector((0, 0, 1)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.objects.link(cam)
scene.camera = cam

# Componentes dos guias, sem alteração.
for arquivo, codigo, classe in (("clima", blocos("clima")[0], "Clima"),
                                ("tremer", blocos("camera-fx")[0], "TremerNoEspaco")):
    with open(os.path.join(out_dir, arquivo + ".py"), "w", encoding="utf-8") as f:
        f.write(codigo)
    scene.objects.active = cubo
    bpy.ops.logic.python_component_register(component_name="%s.%s" % (arquivo, classe))

cf, lm = blocos("camera-fx"), blocos("load-mode")
painel = bpy.data.texts.new("painel.py")
painel.write('''import math
import Range
from Range import logic, events, imgui

AJUDA = ["1  efeitos (speed blur, DOF)", "2  grao", "ESPACO  tremor",
         "C  cria Chefe (On Demand)", "T  atira (Tiro On Demand)", "Chuva forte, pocas e raio aos 5 s"]

MENU = %r
GRAO = %r
CHEFE = %r
TIRO = %r


def tick(cont):
    own = cont.owner
    cena = own.scene
    camera = cena.active_camera
    if "t" not in own:
        own["t"] = 0.0
        # Foco e rastreio do guia (no editor é o painel Focus & Tracking).
        camera.focusMode = 1
        camera.focusObject = own
        camera.trackMode = 1
        camera.trackSpeed = 0.3
    own["t"] += 1.0 / 60.0
    own.worldPosition.x = math.sin(own["t"] * 0.6) * 6.0

    imgui.set_game_ui_open(True)
    imgui.set_next_window_pos(10.0, 10.0, imgui.COND_ALWAYS)
    shown, _ = imgui.begin("Teclas")
    if shown:
        for linha in AJUDA:
            imgui.text(linha)
    imgui.end()

    t = logic.keyboard.inputs
    ns = {"Range": Range, "logic": logic, "events": events}
    if t[events.ONEKEY].activated:
        exec(MENU, ns)
        camera.useDof = not camera.useDof
    if t[events.TWOKEY].activated:
        exec(GRAO, ns)
    if t[events.CKEY].activated and "Chefe" not in cena.objects:
        exec(CHEFE, ns)
    if t[events.TKEY].activated:
        ns["cena"] = cena
        if "Tiro" not in [o.name for o in cena.objectsInactive]:
            exec(TIRO, ns)
            tiro = ns["tiro"]
        else:
            tiro = cena.addObject("Tiro", cena.objects["Arma"], 120)
        # Nasce em cima do cilindro e voa para frente, para ser visto.
        tiro.worldPosition.z += 2.0
        tiro["voa"] = True
    for o in cena.objects:
        if "voa" in o:
            o.worldPosition.y += 0.15
''' % (cf[1], cf[2], lm[0], lm[1]))

scene.objects.active = cubo
bpy.ops.logic.sensor_add(type='ALWAYS', name='tick', object=cubo.name)
bpy.ops.logic.controller_add(type='PYTHON', name='py', object=cubo.name)
cubo.game.sensors['tick'].use_pulse_true_level = True
c = cubo.game.controllers['py']
c.mode = 'MODULE'
c.module = "painel.tick"
c.link(sensor=cubo.game.sensors['tick'])

p = os.path.join(out_dir, "testes_guias.range")
bpy.ops.wm.save_as_mainfile(filepath=p)
print("salvo:", p)
