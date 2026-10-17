# Valida os exemplos Partida (+ update com network.input) e InputDoJogador do guia multiplayer.md (codigo do guia
# sem alterar; o trecho "dentro da classe Partida" substitui o update vazio e ganha o "import struct", como o guia manda).
# Uso: AnastacioEngine.exe -b --factory-startup --python criar_cena_guia_multiplayer.py -- <pasta de saida>
# Depois rode duas instancias (cada uma com TEMP proprio e copia propria da pasta):
#   GUIA_NET_ROLE=host   GUIA_NET_PORT=<p> AnastacioRuntime.exe -w 320 240 <host>/guia_multiplayer.range
#   GUIA_NET_ROLE=client GUIA_NET_PORT=<p> AnastacioRuntime.exe -w 320 240 <cliente>/guia_multiplayer.range
# Evidencias em <pasta>/guia_multiplayer_<role>.txt. Script pronto: rodar_guia_multiplayer.sh
import os
import sys

import bpy

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import comum  # noqa: E402

out_dir = sys.argv[sys.argv.index("--") + 1]
os.makedirs(out_dir, exist_ok=True)

blocos = comum.blocos_python(os.path.join(comum.DOCS_GUIAS, "multiplayer.md"))
partida = [b for b in blocos if "class Partida" in b][0]
entrada = [b for b in blocos if "class InputDoJogador" in b][0]
upd = [b for b in blocos if "dentro da classe Partida" in b][0]
vazio = "    def update(self):\n        pass\n"
assert vazio in partida
partida = "import struct\n" + partida.replace(vazio, upd)
with open(os.path.join(out_dir, "guia_partida.py"), "w", encoding="utf-8") as f:
    f.write(partida)
with open(os.path.join(out_dir, "guia_input.py"), "w", encoding="utf-8") as f:
    f.write(entrada)
with open(os.path.join(out_dir, "teclado_falso.py"), "w", encoding="utf-8") as f:
    f.write(comum.TECLADO_FALSO)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_frame_rate = True


def mat(nome, cor):
    m = bpy.data.materials.new(nome)
    m.diffuse_color = cor
    return m


bpy.ops.mesh.primitive_plane_add(location=(0, 0, 0))
chao = bpy.context.active_object
chao.scale = (10, 10, 1)
chao.game.physics_type = 'NO_COLLISION'
chao.data.materials.append(mat("Chao", (0.3, 0.5, 0.3)))

# Jogador replicado numa camada inativa (camada 2).
bpy.ops.mesh.primitive_cube_add(location=(0, 0, 1), radius=0.5)
jog = bpy.context.active_object
jog.name = "Jogador"
jog.game.physics_type = 'NO_COLLISION'
jog.data.materials.append(mat("Jogador", (0.9, 0.2, 0.1)))
jog.game.network.use_replicate = True
jog.game.network.sync_transform = True
jog.layers = [i == 1 for i in range(20)]

sys.path.insert(0, out_dir)


def empty(nome, comp):
    ob = bpy.data.objects.new(nome, None)
    scene.objects.link(ob)
    scene.objects.active = ob
    if comp:
        bpy.ops.logic.python_component_register(component_name=comp)
    return ob


empty("Partida", "guia_partida.Partida")
empty("Controle", "guia_input.InputDoJogador")
verif_ob = empty("Verif", None)

verif = bpy.data.texts.new("verif_net.py")
verif.write('''import os
import time
import Range
from Range import logic, events, network
import teclado_falso

ROLE = os.environ.get("GUIA_NET_ROLE", "host")
PORT = int(os.environ.get("GUIA_NET_PORT", "27931"))
F = {"t0": None, "linhas": [], "feito": set(), "ultimo": -1.0}


def log(s):
    F["linhas"].append("[%6.2f] %s" % (time.time() - F["t0"], s))


def uma_vez(chave):
    if chave in F["feito"]:
        return False
    F["feito"].add(chave)
    return True


def bonecos(scene):
    return [o for o in scene.objects if o.name.startswith("Jogador")]


def fmt(v):
    return "(%.2f, %.2f, %.2f)" % tuple(v)


def tick(cont):
    scene = logic.getCurrentScene()
    if F["t0"] is None:
        F["t0"] = time.time()
        log("papel=%s porta=%d teclado falso=%s" % (ROLE, PORT, teclado_falso.instalar()))
    t = time.time() - F["t0"]
    partida = scene.objects["Partida"].components[0]
    if ROLE == "host":
        if uma_vez("host"):
            log("host() -> %r" % network.host(PORT, max_players=4, room_name="guia", websocket_port=0))
        if t > 0.3 and uma_vez("pos_host"):
            log("logo apos host(): Partida.jogadores=%r" % sorted(partida.jogadores))
        if any(c.ready and not c.isHost for c in network.clients) and uma_vez("start"):
            log("start_game() -> %r" % network.start_game())
    else:
        if t > 1.5 and uma_vez("join"):
            log("join() -> %r" % network.join("127.0.0.1:%d" % PORT))
        if network.isConnected and uma_vez("conectado"):
            log("conectado como cliente %r" % network.localId)
        if network.isConnected and t > 2.5 and uma_vez("ready"):
            network.set_ready(True)
        if network.isConnected and t > 3.0:
            for cid in (0, 1):
                if uma_vez("input%d" % cid):
                    try:
                        log("cliente: network.input(%d) -> %r" % (cid, network.input(cid)))
                    except Exception as e:
                        log("cliente: network.input(%d) -> ERRO %s: %s" % (cid, type(e).__name__, e))
    if t > 4.5 and uma_vez("teclas"):
        teclado_falso.apertar(events.WKEY if ROLE == "host" else events.DKEY)
        log("aperta %s" % ("W" if ROLE == "host" else "D"))
    if t - F["ultimo"] >= 1.0:
        F["ultimo"] = t
        extra = ""
        if ROLE == "host":
            extra = " jogadores=%r clientes=%r input(0)=%r input(1)=%r" % (
                {k: fmt(v.worldPosition) for k, v in partida.jogadores.items()},
                [(c.id, c.isHost, c.ready) for c in network.clients], network.input(0), network.input(1))
        log("bonecos na cena: %r%s" % ([(o.name, fmt(o.worldPosition)) for o in bonecos(scene)], extra))
    if t > 9.0:
        log("fim")
        with open(os.path.join(logic.expandPath("//"), "guia_multiplayer_%s.txt" % ROLE), "w") as f:
            f.write("\\n".join(F["linhas"]) + "\\n")
        logic.endGame()
''')
bpy.ops.logic.sensor_add(type='ALWAYS', name='tick', object=verif_ob.name)
bpy.ops.logic.controller_add(type='PYTHON', name='py', object=verif_ob.name)
verif_ob.game.sensors['tick'].use_pulse_true_level = True
c = verif_ob.game.controllers['py']
c.mode = 'MODULE'
c.module = 'verif_net.tick'
c.link(sensor=verif_ob.game.sensors['tick'])

bpy.ops.object.lamp_add(type='SUN', location=(0, 0, 10), rotation=(0.6, 0.3, 0))
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
scene.objects.link(cam)
cam.location = (0, -14, 10)
from mathutils import Vector  # noqa: E402
cam.rotation_euler = (Vector((0, 0, 0)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
cam.data.lens = 16
scene.camera = cam
scene.layers = [i == 0 for i in range(20)]

path = os.path.join(out_dir, "guia_multiplayer.range")
bpy.ops.wm.save_as_mainfile(filepath=path)
print("GUIA salvo:", path, jog.game.network.net_id)
