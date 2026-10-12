"""Logic Bricks -> Python: registro de teclas do sensor Keyboard (Log Toggle + Target) com digitacao de verdade.

Run with:  AnastacioEngine -b --python tools/create_logic_convert_scene_keylog.py -- <output.range> [convert|none]
O objeto Typer tem um sensor Keyboard (All Keys) com Log Toggle ligado e Target numa propriedade de texto;
Other tem o mesmo sensor com o Log Toggle desligado ate o quadro 150. O jogo dura 600 quadros e grava
<cena>_check_keylog.txt ao lado do .range com o texto registrado. Digite (ou simule as teclas) a mesma
sequencia na rodada de bricks e na convertida: os dois arquivos tem que sair iguais.
"""

import bpy
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "logic_convert_keylog.range"
convert = len(argv) > 1 and argv[1].startswith("convert")
mode = argv[1].split(":", 1)[1] if convert and ":" in argv[1] else "COMPONENT"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.world = bpy.data.worlds.new("World")
tested = []


def typer(name, loc, log_on):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    o = bpy.context.active_object
    o.name = name
    for pname, ptype, value in (("txt", 'STRING', "x"), ("logon", 'BOOL', log_on), ("n", 'INT', 0)):
        bpy.ops.object.game_property_new(type=ptype, name=pname)
        o.game.properties[pname].value = value
    bpy.ops.logic.sensor_add(type='KEYBOARD', name="Keys", object=o.name)
    s = o.game.sensors["Keys"]
    s.use_all_keys = True
    s.log = "logon"
    s.target = "txt"
    bpy.ops.logic.actuator_add(type='PROPERTY', name="Count", object=o.name)
    a = o.game.actuators["Count"]
    a.mode = 'ADD'
    a.property = "n"
    a.value = "1"
    bpy.ops.logic.controller_add(type='LOGIC_AND', name="Go", object=o.name)
    c = o.game.controllers["Go"]
    s.link(c)
    a.link(c)
    tested.append(o)
    return o


cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
cam.location = (0, 0, 20)
scene.objects.link(cam)
scene.camera = cam
typer("Typer", (-2, 0, 0), True)
o = typer("Other", (2, 0, 0), False)
# Liga o registro de Other no quadro 150.
bpy.ops.logic.sensor_add(type='DELAY', name="At150", object=o.name)
o.game.sensors["At150"].delay = 150
bpy.ops.logic.actuator_add(type='PROPERTY', name="LogOn", object=o.name)
a = o.game.actuators["LogOn"]
a.mode = 'ASSIGN'
a.property = "logon"
a.value = "1"
bpy.ops.logic.controller_add(type='LOGIC_AND', name="Arm", object=o.name)
o.game.sensors["At150"].link(o.game.controllers["Arm"])
a.link(o.game.controllers["Arm"])

checker = bpy.data.objects.new("Checker", None)
scene.objects.link(checker)
text = bpy.data.texts.new("checker.py")
text.from_string('''
from Range import logic
cont = logic.getCurrentController()
own = cont.owner
own['frames'] = own.get('frames', 0) + 1
n = own.scene.objects['Typer']['n']
if n != own.get('last', 0):
    # Quadro de cada disparo e as teclas ativas nele.
    from Range import events
    held = [events.EventToString(k) for k, e in logic.keyboard.inputs.items() if e.active or e.activated]
    own['hist'] = own.get('hist', '') + '%d:%d:%s ' % (own['frames'], n, '+'.join(held))
    own['last'] = n
if own['frames'] == 600:
    o = own.scene.objects
    with open(logic.expandPath('//' + own.scene.name + '_check_keylog.txt'), 'w', encoding='utf-8') as f:
        for name in ('Typer', 'Other'):
            f.write('%s txt=%r n=%d' % (name, o[name]['txt'], o[name]['n']) + chr(10))
        f.write('disparos ' + own.get('hist', '') + chr(10))
    logic.endGame()
''')
bpy.ops.logic.sensor_add(type='ALWAYS', name="Frame", object=checker.name)
checker.game.sensors["Frame"].use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', name="Check", object=checker.name)
checker.game.controllers["Check"].text = text
checker.game.sensors["Frame"].link(checker.game.controllers["Check"])

if convert:
    left = []
    for o in tested:
        scene.objects.active = o
        print("CONVERT", o.name, bpy.ops.logic.convert_to_component(mode=mode))
    for t in bpy.data.texts:
        left += [(t.name, ln.strip()) for ln in t.as_string().splitlines() if "# TODO:" in ln]
    print("LEFT_AS_BRICK", len(left), left)

bpy.ops.wm.save_as_mainfile(filepath=output)
