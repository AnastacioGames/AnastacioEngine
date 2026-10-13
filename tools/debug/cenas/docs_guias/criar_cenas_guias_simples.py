# Cenas que testam os exemplos dos guias em rascunho do site (clima, camera-fx, load-mode, receitas).
# O código vem direto dos blocos ```python de cada .md, sem alteração.
# Uso: AnastacioEngine.exe -b --factory-startup -P criar_cenas_guias_simples.py -- <pasta de saida> <pasta dos guias>
# Depois: AnastacioRuntime.exe <pasta>/guia_<nome>.range ; resultado em <pasta>/guia_<nome>.txt
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


# Sonda: roda passos por quadro, captura exceções e grava o resultado.
SONDA = '''import Range, os, traceback
from Range import logic, events

class _Self:
    pass

def tick(cont):
    own = cont.owner
    g = logic.globalDict
    g.setdefault("frame", 0)
    g["frame"] += 1
    passos = PASSOS.get(g["frame"])
    if passos is None:
        if g["frame"] > FIM:
            with open(os.path.join(logic.expandPath("//"), SAIDA), "w") as f:
                f.write("\\n".join(g.get("linhas", [])) + "\\n")
            DEPOIS(own)
        return
    ns = g.setdefault("ns", {"Range": Range, "logic": logic, "events": events})
    s = _Self()
    s.object = own
    ns["self"] = s
    for rotulo, codigo in passos:
        # Receita que remove o objeto roda num objeto descartável, para a sonda continuar viva.
        s.object = own.scene.objects["Descartavel"] if "endObject" in codigo else own
        try:
            exec(codigo, ns)
            g.setdefault("linhas", []).append("OK " + rotulo)
        except Exception:
            g.setdefault("linhas", []).append("FALHA " + rotulo + "\\n" + traceback.format_exc())
'''


def material(ob, cor):
    m = bpy.data.materials.new(ob.name + "_mat")
    m.diffuse_color = cor
    ob.data.materials.append(m)


def cena_base(nome):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = nome
    scene.render.engine = 'BLENDER_GAME'
    w = bpy.data.worlds.new("World")
    w.mist_settings.use_mist = False
    scene.world = w
    bpy.ops.mesh.primitive_plane_add(radius=10, location=(0, 0, 0))
    material(bpy.context.object, (0.4, 0.4, 0.4))
    bpy.ops.mesh.primitive_cube_add(location=(0, 0, 1))
    cubo = bpy.context.object
    cubo.name = "Cubo"
    material(cubo, (0.9, 0.2, 0.1))
    sun = bpy.data.objects.new("Sun", bpy.data.lamps.new("Sun", 'SUN'))
    sun.rotation_euler = (0.6, 0.2, 0.4)
    scene.objects.link(sun)
    cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    cam.location = (0, -10, 5)
    cam.rotation_euler = (Vector((0, 0, 1)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    scene.objects.link(cam)
    scene.camera = cam
    return scene, cubo


def sonda(scene, dono, passos, fim, saida, depois="def DEPOIS(own):\n    logic.endGame()\n"):
    t = bpy.data.texts.new("sonda_%s.py" % scene.name)
    t.write(SONDA + "\nPASSOS = %r\nFIM = %d\nSAIDA = %r\n%s" % (passos, fim, saida, depois))
    scene.objects.active = dono
    bpy.ops.logic.sensor_add(type='ALWAYS', name='tick', object=dono.name)
    bpy.ops.logic.controller_add(type='PYTHON', name='py', object=dono.name)
    dono.game.sensors['tick'].use_pulse_true_level = True
    c = dono.game.controllers['py']
    c.mode = 'MODULE'
    c.module = t.name[:-3] + ".tick"
    c.link(sensor=dono.game.sensors['tick'])


def componente(arquivo, codigo, ob, classe):
    with open(os.path.join(out_dir, arquivo + ".py"), "w", encoding="utf-8") as f:
        f.write(codigo)
    bpy.context.scene.objects.active = ob
    bpy.ops.logic.python_component_register(component_name="%s.%s" % (arquivo, classe))


def salvar(nome):
    p = os.path.join(out_dir, "guia_%s.range" % nome)
    bpy.ops.wm.save_as_mainfile(filepath=p)
    print("salvo:", p)


# --- clima: componente do guia (5 s) e conferência depois de 7 s ---
b = blocos("clima")
scene, cubo = cena_base("clima")
scene.world.weather_settings.use_rain = True
componente("clima", b[0], cubo, "Clima")
sonda(scene, cubo, {420: [("componente Clima rodou 7 s", "assert self.object.components[0].tempestade")]}, 420, "guia_clima.txt")
salvar("clima")

# --- camera-fx: componente do tremor + trechos do menu e do grão + shake direto ---
b = blocos("camera-fx")
scene, cubo = cena_base("camera")
componente("tremer", b[0], cubo, "TremerNoEspaco")
sonda(scene, cubo, {
    5: [("menu de efeitos", b[1]), ("grao", b[2]),
        ("shake", "cam = self.object.scene.active_camera\ncam.shake(0.8, 0.6)")],
    8: [("trauma > 0 depois do shake", "assert self.object.scene.active_camera.shakeTrauma > 0, self.object.scene.active_camera.shakeTrauma")],
    9: [("speed blur ligado", "assert self.object.scene.active_camera.useSpeedBlur")],
}, 10, "guia_camera.txt")
salvar("camera")

# --- load-mode: Chefe On Demand na camada ativa, Tiro On Demand na camada 2, Arma normal ---
b = blocos("load-mode")
scene, cubo = cena_base("loadmode")
bpy.ops.mesh.primitive_uv_sphere_add(location=(3, 0, 1))
chefe = bpy.context.object
chefe.name = "Chefe"
material(chefe, (0.1, 0.3, 0.9))
bpy.ops.mesh.primitive_cone_add(location=(0, 0, 3), layers=[False, True] + [False] * 18)
tiro = bpy.context.object
tiro.name = "Tiro"
material(tiro, (0.9, 0.9, 0.1))
bpy.ops.mesh.primitive_cylinder_add(location=(-3, 0, 1))
arma = bpy.context.object
arma.name = "Arma"
material(arma, (0.2, 0.8, 0.2))
chefe.game_load_mode = 'ON_DEMAND'
tiro.game_load_mode = 'ON_DEMAND'
scene.layers[0] = True
sonda(scene, cubo, {
    3: [("Chefe ausente ao abrir", "assert 'Chefe' not in self.object.scene.objects"),
        ("unconvertedObjects lista os dois", "u = self.object.scene.unconvertedObjects\nassert 'Chefe' in u and 'Tiro' in u, u"),
        ("convertObject Chefe", b[0]),
        ("Chefe apareceu", "assert 'Chefe' in self.object.scene.objects"),
        ("Tiro com addObject", b[1]),
        ("Tiro adicionado", "assert any(o.name == 'Tiro' for o in self.object.scene.objects)"),
        ("getLoadLog", b[2])],
}, 4, "guia_loadmode.txt")
salvar("loadmode")

# --- receitas: cada bloco na ordem; replace/restart por último, com Fase2 confirmando ---
b = blocos("receitas")
scene, cubo = cena_base("receitas")
bpy.ops.mesh.primitive_cube_add(location=(0, 3, 1))
jog = bpy.context.object
jog.name = "Jogador"
material(jog, (0.1, 0.8, 0.9))
bpy.ops.mesh.primitive_cone_add(location=(0, 0, 3), layers=[False, True] + [False] * 18)
t2 = bpy.context.object
t2.name = "Tiro"
material(t2, (0.9, 0.9, 0.1))
bpy.ops.mesh.primitive_ico_sphere_add(location=(3, 3, 1))
desc = bpy.context.object
desc.name = "Descartavel"
material(desc, (0.8, 0.1, 0.8))
scene.objects.active = cubo
bpy.ops.object.game_property_new(type='BOOL', name="inimigo")
passos = [("receita %d" % i, c) for i, c in enumerate(b) if "replace(" not in c]
troca = [c for c in b if "replace(" in c][0]
passos.append(("Descartavel removido", "assert 'Descartavel' not in self.object.scene.objects"))
sonda(scene, cubo, {5: passos}, 6, "guia_receitas.txt",
      "def DEPOIS(own):\n    s = _Self()\n    s.object = own\n    ns = logic.globalDict['ns']\n    ns['self'] = s\n"
      "    exec(%r.split('\\n')[0], ns)\n" % troca)
# Fase2: confirma que replace chegou e encerra.
fase2 = bpy.data.scenes.new("Fase2")
fase2.render.engine = 'BLENDER_GAME'
bpy.context.screen.scene = fase2
cam2 = bpy.data.objects.new("Cam2", bpy.data.cameras.new("Cam2"))
fase2.objects.link(cam2)
fase2.camera = cam2
e = bpy.data.objects.new("Marca", None)
fase2.objects.link(e)
t = bpy.data.texts.new("fase2.py")
t.write("import os\nfrom Range import logic\ndef tick(cont):\n"
        "    with open(os.path.join(logic.expandPath('//'), 'guia_receitas.txt'), 'a') as f:\n"
        "        f.write('OK replace chegou na Fase2\\n')\n    logic.endGame()\n")
bpy.context.scene.objects.active = e
bpy.ops.logic.sensor_add(type='ALWAYS', name='tick', object=e.name)
bpy.ops.logic.controller_add(type='PYTHON', name='py', object=e.name)
c = e.game.controllers['py']
c.mode = 'MODULE'
c.module = "fase2.tick"
c.link(sensor=e.game.sensors['tick'])
bpy.context.screen.scene = scene
salvar("receitas")
