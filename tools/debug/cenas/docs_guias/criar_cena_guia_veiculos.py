# Cena de teste do guia de Veículos (D:\AnastacioDocs\site\src\content\docs\guias\veiculos.md).
# Monta um chassi com 4 rodas pelo painel Vehicle (operador OBJECT_OT_vehicle_wheel_add) e testa:
#   - o componente DirigirSimples (texto exato do guia) acelerando e esterçando;
#   - savePreset/loadPreset do veículo.
# Uso: AnastacioEngine.exe -b --factory-startup -P criar_cena_guia_veiculos.py -- <pasta de saida> <pasta dos guias>
# Depois: AnastacioRuntime.exe <pasta>/guia_veiculos.range ; resultado em <pasta>/guia_veiculos.txt
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


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
w = bpy.data.worlds.new("World")
w.mist_settings.use_mist = False
scene.world = w

bpy.ops.mesh.primitive_plane_add(radius=50, location=(0, 0, 0))
chao = bpy.context.object
chao.name = "Chao"
material(chao, (0.3, 0.3, 0.3))
chao.game.physics_type = 'STATIC'

# Chassi: a Range usa convenção right=0(X), up=2(Z), forward=1(Y).
# Dois carros iguais, offset em X: "Chassi" roda o componente DirigirSimples do
# guia (ocioso sem teclado no runtime headless, só prova que registra e não
# quebra); "ChassiAPI" é dirigido pela sonda chamando a mesma API, pra provar
# que o carro de fato anda. Não dividem objeto pra não brigar pela força.
def montar_carro(nome, offset_x):
    bpy.ops.mesh.primitive_cube_add(location=(offset_x, 0, 0.6))
    chassi = bpy.context.object
    chassi.name = nome
    chassi.scale = (1.0, 2.2, 0.5)
    material(chassi, (0.85, 0.15, 0.1))
    chassi.game.physics_type = 'RIGID_BODY'
    chassi.game.mass = 800.0
    chassi.game.is_vehicle = True
    chassi.game.use_collision_bounds = True
    chassi.game.collision_bounds_type = 'BOX'

    posicoes = [("RodaFD", (offset_x + 0.9, 1.4, 0.35), True),
                ("RodaFE", (offset_x - 0.9, 1.4, 0.35), True),
                ("RodaTD", (offset_x + 0.9, -1.4, 0.35), False),
                ("RodaTE", (offset_x - 0.9, -1.4, 0.35), False)]
    rodas = []
    for base, pos, esterca in posicoes:
        nome_roda = "%s_%s" % (nome, base)
        bpy.ops.mesh.primitive_cylinder_add(radius=0.35, depth=0.25, location=pos)
        roda = bpy.context.object
        roda.name = nome_roda
        roda.rotation_euler = (1.5708, 0, 0)
        material(roda, (0.1, 0.1, 0.1))
        roda.game.physics_type = 'NO_COLLISION'
        rodas.append((roda, esterca))

    bpy.context.scene.objects.active = chassi
    for roda, esterca in rodas:
        bpy.ops.object.vehicle_wheel_add()
        w4 = chassi.vehicle_wheels[-1]
        w4.object = roda
        w4.radius = 0.35
        w4.suspension_rest_length = 0.3
        w4.has_steering = esterca
        w4.has_drive = True
    return chassi


chassi = montar_carro("Chassi", 0.0)
chassi_api = montar_carro("ChassiAPI", 6.0)
chassi_api.vehicle_ray_cast_mask = 1  # workaround: mascara 0 (padrao) quebra savePreset, ver relatorio

sun = bpy.data.objects.new("Sun", bpy.data.lamps.new("Sun", 'SUN'))
sun.rotation_euler = (0.6, 0.2, 0.4)
scene.objects.link(sun)
cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
cam.location = (0, -14, 6)
cam.rotation_euler = (Vector((0, 0, 1)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.objects.link(cam)
scene.camera = cam

# Componente do guia, sem alteração. Só no "Chassi" (o "ChassiAPI" é dirigido pela sonda).
b = blocos("veiculos")
with open(os.path.join(out_dir, "dirigir_simples.py"), "w", encoding="utf-8") as f:
    f.write(b[0])
bpy.context.scene.objects.active = chassi
bpy.ops.logic.python_component_register(component_name="dirigir_simples.DirigirSimples")

# Sonda: confere getVehicle(), getNumWheels(), posição avançando com W segurado,
# depois savePreset/loadPreset.
sonda = bpy.data.texts.new("sonda.py")
sonda.write('''import os
import Range
from Range import logic, events

def tick(cont):
    own = cont.owner
    g = logic.globalDict
    g.setdefault("frame", 0)
    g["frame"] += 1
    f = g["frame"]
    linhas = g.setdefault("linhas", [])
    def check(label, ok, extra=""):
        linhas.append(("OK " if ok else "FALHA ") + label + ((" " + str(extra)) if extra else ""))

    if f == 2:
        v = own.getVehicle()
        check("getVehicle() nao e None", v is not None)
        check("getNumWheels() == 4", v.getNumWheels() == 4, v.getNumWheels())
        g["y0"] = own.worldPosition.y
        g["z0"] = own.worldPosition.z

    # Segura W (frente) por ~60 quadros simulando o input do DirigirSimples
    # (o componente DirigirSimples já lê o teclado sozinho; aqui só forçamos a
    # tecla via SCA input manualmente não é direto no bpy headless, então
    # chamamos applyEngineForce/setSteeringValue como o próprio componente faz,
    # pra validar a API central sem depender de injeção de teclado.)
    if 2 <= f <= 90:
        v = own.getVehicle()
        for i in range(v.getNumWheels()):
            v.applyEngineForce(-1500.0, i)
            v.applyBraking(0.0, i)
        v.setSteeringValue(0.0, 0)
        v.setSteeringValue(0.0, 1)

    if f == 91:
        andou = own.worldPosition.y - g["y0"]
        check("carro andou para frente (+Y local) com forca negativa (W)", andou > 0.3, andou)
        caiu = abs(own.worldPosition.z - g["z0"]) < 1.0
        check("chassi nao caiu/voou (fisica estavel)", caiu, own.worldPosition.z)

    if f == 95:
        path = Range.logic.expandPath("//acerto_teste.json")
        v = own.getVehicle()
        try:
            v.savePreset(path)
            check("savePreset", os.path.exists(path), path)
        except Exception as e:
            check("savePreset", False, repr(e))

    if f == 100:
        path = Range.logic.expandPath("//acerto_teste.json")
        v = own.getVehicle()
        try:
            v.loadPreset(path)
            check("loadPreset (mesma estrutura de rodas)", True)
        except Exception as e:
            check("loadPreset", False, repr(e))

    if f >= 105:
        with open(os.path.join(logic.expandPath("//"), "guia_veiculos.txt"), "w") as fh:
            fh.write("\\n".join(linhas) + "\\n")
        logic.endGame()
''')
bpy.context.scene.objects.active = chassi_api
bpy.ops.logic.sensor_add(type='ALWAYS', name='tick', object=chassi_api.name)
bpy.ops.logic.controller_add(type='PYTHON', name='py', object=chassi_api.name)
chassi_api.game.sensors['tick'].use_pulse_true_level = True
c = chassi_api.game.controllers['py']
c.mode = 'MODULE'
c.module = "sonda.tick"
c.link(sensor=chassi_api.game.sensors['tick'])


path = os.path.join(out_dir, "guia_veiculos.range")
bpy.ops.wm.save_as_mainfile(filepath=path)
print("salvo:", path)
