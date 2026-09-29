# Cena do teste do loop de tempo. Uso: RangeEngine -b --python gen_loop.py
import bpy, os
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_GAME'
sc.world = bpy.data.worlds.new("World")
gs = sc.game_settings
gs.show_framerate_profile = True
gs.show_debug_properties = True
gs.vsync = 'ON'
gs.fps = 60
sc.world.horizon_color = (0.15, 0.2, 0.3)
def mat(ob, nome, cor):
    m = bpy.data.materials.new(nome); m.diffuse_color = cor; ob.data.materials.append(m)
bpy.ops.mesh.primitive_plane_add(radius=30, location=(0, 0, 0))
mat(bpy.context.object, "Chao", (0.25, 0.25, 0.25))
bpy.ops.object.lamp_add(type='SUN', location=(0, 0, 10), rotation=(0.6, 0.3, 0))
bpy.ops.object.camera_add(location=(0, -14, 10), rotation=(1.0, 0, 0))
sc.camera = bpy.context.object
bpy.ops.mesh.primitive_cube_add(location=(0, 0, 1))
cube = bpy.context.object; cube.name = "Jogador"
mat(cube, "Vermelho", (0.8, 0.1, 0.1))
for n, v in (("teclas", 0), ("vsync", "ON"), ("pico_ms", 0)):
    bpy.ops.object.game_property_new(type='INT' if isinstance(v, int) else 'STRING', name=n)
    cube.game.properties[n].value = v
    cube.game.properties[n].show_debug = True
txt = bpy.data.texts.new("loop.py")
txt.write('''import bge, time
from bge import logic, render, events
c = logic.getCurrentController(); o = c.owner; k = logic.keyboard
# O runtime separado nao le Show Framerate/Properties da cena: liga aqui
if "_init" not in o:
    o["_init"] = True
    render.showFramerate(True); render.showProfile(True); render.showProperties(True)
def on(key): return k.inputs[key].active
def tap(key): return k.inputs[key].activated
# Setas: 5 unidades/s por tick de logica (se o loop perder ticks, o cubo fica lento)
d = 5.0 / logic.getLogicTicRate()
if on(events.RIGHTARROWKEY): o.worldPosition.x += d
if on(events.LEFTARROWKEY): o.worldPosition.x -= d
if on(events.UPARROWKEY): o.worldPosition.y += d
if on(events.DOWNARROWKEY): o.worldPosition.y -= d
# Espaco: conta cada toque (compare com quantas vezes voce apertou)
if tap(events.SPACEKEY): o["teclas"] += 1
# V: alterna v-sync
if tap(events.VKEY):
    liga = render.getVsync() == render.VSYNC_OFF
    render.setVsync(render.VSYNC_ON if liga else render.VSYNC_OFF)
    o["vsync"] = "ON" if liga else "OFF"
# P: liga/desliga pico de carga (80 ms a cada ~1 s)
if tap(events.PKEY): o["pico_ms"] = 0 if o["pico_ms"] else 80
if o["pico_ms"] and logic.getFrameTime() % 1.0 < 0.02: time.sleep(o["pico_ms"] / 1000)
# R: volta ao centro
if tap(events.RKEY): o.worldPosition = (0, 0, 1)
''')
s = cube.game.sensors; bpy.ops.logic.sensor_add(type='ALWAYS', object=cube.name)
cube.game.sensors[-1].use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', object=cube.name)
cube.game.controllers[-1].text = txt
cube.game.sensors[-1].link(cube.game.controllers[-1])
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(os.path.dirname(os.path.abspath(__file__)), "loop_tempo.blend"))
