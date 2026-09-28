# Teste do bug "folhagem branca/preta dependendo do arquivo aberto primeiro" (Kitsuy).
# menu.range aplica setAntiAliasing(0) (como o menu ImGui do template) e abre level.range com startGame.
# level.range tem planos "Alpha Anti-Aliasing" (hashed) com alpha em degrade; loga getAntiAliasing()
# e salva screenshot. level_aa0.range: o proprio nivel chama setAntiAliasing(0). Com MSAA: degrade. Sem MSAA: quadrado solido.
# Uso: RangeEngine.exe -b --python gen_foliage_aa.py
import bpy
import os

DIR = os.path.dirname(os.path.abspath(__file__))


def base_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_GAME'
    scene.world = bpy.data.worlds.new("World")
    scene.world.horizon_color = (0.2, 0.3, 0.5)
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    cam.location = (0, -6, 0)
    cam.rotation_euler = (1.5708, 0, 0)
    scene.objects.link(cam)
    scene.camera = cam
    return scene


def add_logic(obj, name, code):
    text = bpy.data.texts.new(name)
    text.write(code)
    bpy.context.scene.objects.active = obj
    bpy.ops.logic.sensor_add(type='ALWAYS', object=obj.name)
    bpy.ops.logic.controller_add(type='PYTHON', object=obj.name)
    sens = obj.game.sensors[-1]
    sens.use_pulse_true_level = True
    cont = obj.game.controllers[-1]
    cont.text = text
    sens.link(cont)


# ---------------- level ----------------
scene = base_scene()
img = bpy.data.images.new("Grad", 64, 64, alpha=True)
px = []
for y in range(64):
    for x in range(64):
        px += [1.0, 1.0, 1.0, x / 63.0]
img.pixels = px
img.pack(as_png=True)
tex = bpy.data.textures.new("Grad", 'IMAGE')
tex.image = img
mat = bpy.data.materials.new("Leaf")
mat.use_shadeless = True
mat.use_transparency = True
mat.alpha = 0.0
mat.diffuse_color = (1, 1, 1)
mat.game_settings.alpha_blend = 'ALPHA_ANTIALIASING'
slot = mat.texture_slots.add()
slot.texture = tex
slot.use_map_alpha = True
slot.alpha_factor = 1.0
for i, x in enumerate((-1.6, 1.6)):
    bpy.ops.mesh.primitive_plane_add(radius=1.4, location=(x, 0, 0), rotation=(1.5708, 0, 0))
    plane = bpy.context.active_object
    plane.name = "Leaf%d" % i
    plane.data.materials.append(mat)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.uv.unwrap()
    bpy.ops.object.mode_set(mode='OBJECT')
    for p in plane.data.uv_textures[0].data:
        p.image = img
ctrl = bpy.data.objects.new("Ctrl", None)
scene.objects.link(ctrl)
add_logic(ctrl, "level.py", r'''import bge
own = bge.logic.getCurrentController().owner
n = own.get("n", 0)
own["n"] = n + 1
if n == 5 and own.get("aa0", False):
    bge.render.setAntiAliasing(0)
if n == 30:
    shot = bge.logic.expandPath("//level_shot.png")
    bge.render.makeScreenshot(shot)
    with open(bge.logic.expandPath("//foliage_log.txt"), "a") as f:
        f.write("LEVEL aa=%d\n" % bge.render.getAntiAliasing())
if n == 40:
    bge.logic.endGame()
''')
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(DIR, "level.blend"))
# Variante: o proprio nivel aplica setAntiAliasing(0) (ex.: script de opcoes rodando no nivel).
bpy.context.scene.objects.active = ctrl
bpy.ops.object.game_property_new(type="BOOL", name="aa0")
ctrl.game.properties["aa0"].value = True
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(DIR, "level_aa0.blend"))

# ---------------- menu ----------------
scene = base_scene()
ctrl = bpy.data.objects.new("Menu", None)
scene.objects.link(ctrl)
add_logic(ctrl, "menu.py", r'''import bge
own = bge.logic.getCurrentController().owner
n = own.get("n", 0)
own["n"] = n + 1
if n == 5:
    bge.render.setAntiAliasing(0)
    with open(bge.logic.expandPath("//foliage_log.txt"), "a") as f:
        f.write("MENU aa=%d\n" % bge.render.getAntiAliasing())
if n == 10:
    bge.logic.startGame(bge.logic.expandPath("//level.range"))
''')
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(DIR, "menu.blend"))
print("SAVED foliage_aa")
