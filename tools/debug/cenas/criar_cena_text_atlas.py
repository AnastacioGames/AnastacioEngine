"""Cena de teste do Bitmap Atlas de texto: Text com atlas (cima) x BLF (baixo).

Uso: AnastacioEngine.exe -b --factory-startup --python criar_cena_text_atlas.py -- atlas.json saida.range [shot.png] [log.txt]
"""
import sys
import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
json_path, out_path = argv[0], argv[1]
shot_path = argv[2] if len(argv) > 2 else ""
log_path = argv[3] if len(argv) > 3 else ""

bpy.ops.wm.read_factory_settings()
scene = bpy.context.scene
for ob in list(scene.objects):
    scene.objects.unlink(ob)
    bpy.data.objects.remove(ob)
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 960
scene.game_settings.resolution_y = 540
world = scene.world or bpy.data.worlds.new("World")
scene.world = world
world.horizon_color = (0.08, 0.08, 0.12)
world.mist_settings.use_mist = False


def make_text(name, body, loc, color, atlas):
    bpy.ops.object.text_add(location=loc, rotation=(1.5708, 0, 0))
    ob = bpy.context.object
    ob.name = name
    ob.data.body = body
    ob.color = color
    if atlas:
        bpy.ops.font.text_atlas_import(filepath=json_path)
        ob.data.atlas_image.pack()
        ob.data.use_bitmap_atlas = True
    return ob


t1 = make_text("TextAtlas", "AAA Ação!\nOlá ÁÉ", (-3, 0, 0.6), (1, 1, 1, 1), True)
t2 = make_text("TextBLF", "AAA Ação!", (-3, 0, -1.6), (0.4, 0.8, 1, 1), False)

bpy.ops.object.camera_add(location=(0, -8, 0))
cam = bpy.context.object
cam.rotation_euler = (Vector((0, 0, -0.2)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.camera = cam

logic = bpy.data.texts.new("probe.py")
logic.from_string("import bge\n"
                  "SHOT = %r\nLOG = %r\n"
                  "def tick(cont):\n"
                  "    own = cont.owner\n"
                  "    own['t'] = own.get('t', 0) + 1\n"
                  "    if own['t'] == 30 and LOG:\n"
                  "        sc = bge.logic.getCurrentScene()\n"
                  "        with open(LOG, 'w') as f:\n"
                  "            for n in ('TextAtlas', 'TextBLF'):\n"
                  "                o = sc.objects[n]\n"
                  "                f.write('%%s text=%%r\\n' %% (n, o.text))\n"
                  "            f.write('frames_ok\\n')\n"
                  "    if SHOT and own['t'] == 60:\n"
                  "        bge.render.makeScreenshot(SHOT)\n"
                  "    if own['t'] == 75:\n"
                  "        bge.logic.endGame()\n" % (shot_path, log_path))
scene.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', object=cam.name)
bpy.ops.logic.controller_add(type='PYTHON', object=cam.name)
s = cam.game.sensors[-1]
s.use_pulse_true_level = True
c = cam.game.controllers[-1]
c.mode = 'MODULE'
c.module = 'probe.tick'
s.link(c)

bpy.ops.wm.save_as_mainfile(filepath=out_path)
print("TEXT_ATLAS_OK", t1.data.atlas_glyph_count)
