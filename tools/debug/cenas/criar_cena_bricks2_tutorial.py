# Cena tutorial do Logic Bricks 2.0: estados com nome, Wait, "Então" (sensor Finished) e presets.
# Uso: AnastacioEngine.exe -b --factory-startup --python criar_cena_bricks2_tutorial.py -- <saida.blend> [resultado.txt]
# Com resultado.txt, um objeto Checker grava o que aconteceu e fecha o jogo (teste automático).
import bpy, sys

args = sys.argv[sys.argv.index("--") + 1:]
out = args[0]
res = args[1] if len(args) > 1 else None

sc = bpy.context.scene
sc.render.engine = 'BLENDER_GAME'
for o in list(sc.objects):
    if o.type == 'MESH':
        bpy.data.objects.remove(o, do_unlink=True)


def mat(name, color):
    m = bpy.data.materials.new(name)
    m.diffuse_color = color
    return m


def cube(name, loc, scale=(1, 1, 1), phys='STATIC', color=(0.8, 0.8, 0.8)):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    o = sc.objects.active
    o.name = name
    o.scale = scale
    o.game.physics_type = phys
    o.data.materials.append(mat(name, color))
    return o


def prop(o, name, typ, value):
    sc.objects.active = o
    bpy.ops.object.game_property_new(type=typ, name=name)
    o.game.properties[name].value = value


def preset(o, typ):
    sc.objects.active = o
    assert bpy.ops.logic.preset_add(type=typ) == {'FINISHED'}, typ


def add(o, kind, typ, name, **props):
    getattr(bpy.ops.logic, kind + "_add")(type=typ, name=name, object=o.name)
    b = getattr(o.game, kind + "s")[-1]
    for k, v in props.items():
        setattr(b, k, v)
    return b


def only(state):
    return tuple(i == state - 1 for i in range(30))


def label(text, loc):
    bpy.ops.object.text_add(location=loc, rotation=(1.5708, 0, 0))
    t = sc.objects.active
    t.data.body = text
    t.data.size = 0.5
    t.data.align_x = 'CENTER'
    return t


# chão e área de perigo (quem cai volta para o último checkpoint)
cube("Floor", (0, 6, -0.5), (12, 14, 0.5), color=(0.35, 0.45, 0.35))
danger = cube("Danger", (0, 6, -8), (60, 60, 0.5), color=(0.6, 0.1, 0.1))
prop(danger, "kill", 'BOOL', True)
cube("Platform Gap Far", (0, 30, -0.5), (6, 6, 0.5), color=(0.35, 0.45, 0.35))

# jogador: Walk + Jump + Checkpoint, e dois estados com nome: "Normal" e "Hurt"
player = cube("Player", (0, -4, 1), (0.5, 0.5, 0.5), 'DYNAMIC', (0.2, 0.4, 0.9))
player.game.use_actor = True
prop(player, "player", 'BOOL', True)
preset(player, 'WALK')
preset(player, 'JUMP')
preset(player, 'CHECKPOINT')
g = player.game
g.state_names[0].name = "Normal"
g.state_names[1].name = "Hurt"
g.states_initial = only(1)
# encostar no inimigo: estado Hurt; no Hurt, Wait 1.5 s e "Então" volta ao Normal
hit = add(player, "sensor", "COLLISION", "Hit Enemy", property="enemy", group="Hurt")
to_hurt = add(player, "actuator", "STATE", "To Hurt", operation='SET', states=only(2), group="Hurt")
push = add(player, "actuator", "MOTION", "Push Back", linear_velocity=(0, -4, 4), use_local_linear_velocity=False,
           group="Hurt")
c = add(player, "controller", "LOGIC_AND", "Got Hit", group="Hurt")
c.link(sensor=hit); c.link(actuator=to_hurt); c.link(actuator=push)
enter = add(player, "sensor", "ALWAYS", "Enter Hurt", group="Hurt")
recover = add(player, "actuator", "WAIT", "Recover", duration=1.5, group="Hurt")
c = add(player, "controller", "LOGIC_AND", "Start Recover", group="Hurt")
c.states = 2
c.link(sensor=enter); c.link(actuator=recover)
done = add(player, "sensor", "ACTUATOR", "Then Recover", actuator="Recover", mode='FINISHED', group="Hurt")
to_normal = add(player, "actuator", "STATE", "To Normal", operation='SET', states=only(1), group="Hurt")
c = add(player, "controller", "LOGIC_AND", "Back To Normal", group="Hurt")
c.states = 2
c.link(sensor=done); c.link(actuator=to_normal)
# no Hurt o jogador não anda: Walk e Jump ficam só no estado 1 (já é o padrão dos presets)

# câmera seguindo o jogador
bpy.ops.object.camera_add(location=(0, -14, 6))
sc.camera = sc.objects.active
preset(player, 'CAMERA')

# moeda (Collect) e porta (Door com uma Action que sobe)
coin = cube("Coin", (3, 0, 0.6), (0.3, 0.3, 0.3), color=(1.0, 0.8, 0.1))
coin.game.physics_type = 'STATIC'
coin.game.use_ghost = True
preset(coin, 'COLLECT')

door = cube("Door", (0, 4, 1.5), (2, 0.2, 1.5), color=(0.5, 0.3, 0.15))
door.keyframe_insert("location", frame=1)
door.location.z = 4.5
door.keyframe_insert("location", frame=30)
door.location.z = 1.5
act = door.animation_data.action
act.name = "DoorOpen"
door.animation_data.action = None
preset(door, 'DOOR')
anim = door.game.actuators["Door Animation"]
anim.action = act
anim.frame_start = 1
anim.frame_end = 30
label("E: abrir a porta", (0, 3.6, 3.4))

# checkpoint depois da porta
cp = cube("Checkpoint", (0, 8, 0.05), (1, 1, 0.05), color=(0.1, 0.9, 0.9))
cp.game.use_ghost = True
prop(cp, "checkpoint", 'BOOL', True)

# inimigo que persegue
enemy = cube("Enemy", (5, 12, 0.6), (0.5, 0.5, 0.5), "DYNAMIC", (0.9, 0.2, 0.2))
prop(enemy, "enemy", 'BOOL', True)
preset(enemy, 'CHASE')

# plataforma que vai e volta sobre o buraco (estados Going/Returning + Wait + Então)
plat = cube("Platform", (0, 21, -0.4), (1.5, 1.5, 0.2), color=(0.7, 0.7, 0.2))
preset(plat, 'PLATFORM')

label("Logic Bricks 2.0\nWASD anda, Espaço pula\nF1 + clique no objeto: janela Logic Bricks",
      (0, -2, 3))

bpy.ops.object.lamp_add(type='SUN', location=(0, 0, 10), rotation=(0.6, 0.2, 0))

tut = bpy.data.texts.new("LEIA-ME")
tut.write("""Tutorial do Logic Bricks 2.0

Abra o Logic Editor e selecione cada objeto:

Player
  - grupos Walk, Jump e Checkpoint vêm dos presets (Add > Preset).
  - estados com nome: 1 "Normal", 2 "Hurt" (clique com o direito no quadradinho do estado para renomear).
  - grupo Hurt: encostar no Enemy leva ao estado Hurt; nele o Wait "Recover" conta 1,5 s
    e o sensor Finished "Then Recover" (botão Então no actuator) volta ao Normal.

Platform
  - preset Moving Platform: estado Going anda 2 s (Wait), "Então" muda para Returning, e volta.

Enemy
  - preset Chase Enemy: Near + Steering Seek atrás do objeto com a propriedade "player".

Door, Coin e Checkpoint
  - Door: E perto abre (preset Door). Coin some ao tocar (Collect).
  - Checkpoint: o Player salva o lugar ao tocar; cair no Danger ("kill") volta para lá.

No jogo, ligue o Debug Mode, abra a janela Logic Bricks e clique no Player:
o histórico mostra as últimas ocorrências, clicar no nome de um brick pausa o jogo quando ele disparar.
""")

if res:
    sc.game_settings.show_debug_mode = True
    SRC = """import bge
def chk(cont):
    o = bge.logic.getCurrentScene().objects
    own = cont.owner
    p = o["Platform"]
    own["ymax"] = max(own.get("ymax", -99.0), p.worldPosition.y)
    own["states"] = own.get("states", "") + ("" if own.get("last") == p.state else str(p.state) + ",")
    own["last"] = p.state
    pl = o["Player"]
    own["pstates"] = own.get("pstates", "") + ("" if own.get("plast") == pl.state else "%%d@%%d," %% (pl.state, own.get("n", 0)))
    own["plast"] = pl.state
    e = o["Enemy"]
    if "e0" not in own:
        own["e0"] = e.worldPosition.y
    own["n"] = own.get("n", 0) + 1
    if own["n"] %% 30 == 0:
        own["log"] = own.get("log", "") + "%%d enemy %%s player %%s %%d\\n" %% (
            own["n"], [round(v, 2) for v in e.worldPosition], [round(v, 2) for v in o["Player"].worldPosition],
            o["Player"].state)
    if cont.sensors["End"].positive:
        open(r"%s", "w").write("platform ymax=%%.2f y=%%.2f states=%%s player=%%s enemy_dy=%%.2f\\n" %% (
            own["ymax"], p.worldPosition.y, own["states"], own["pstates"], e.worldPosition.y - own["e0"]) + own.get("log", ""))
        bge.logic.endGame()
""" % res
    bpy.data.texts.new("chk.py").from_string(SRC)
    e = cube("Checker", (40, 40, 1))
    tick = add(e, "sensor", "ALWAYS", "Tick", use_pulse_true_level=True)
    end = add(e, "sensor", "DELAY", "End", delay=330)
    c = add(e, "controller", "PYTHON", "chk", mode='MODULE', module="chk.chk")
    c.link(sensor=tick); c.link(sensor=end)
    # o inimigo precisa de um alvo perto: no teste o jogador começa ao lado dele
    player.location = (5, 6, 1)

sc.objects.active = player
bpy.ops.wm.save_as_mainfile(filepath=out)
print("SCENE OK", out)
