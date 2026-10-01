"""VR menu made only of logic bricks: three gaze buttons in front of the player.

Run with:  RangeEngine -b --python tools/create_vr_menu_scene.py -- <output.range>
In game (Cardboard): look at a button for 1 s and its counter goes up.
Each button has a Ray "VR Gaze" sensor with "Self" on, so it can be duplicated as is.
The camera has its own VR Gaze sensor only to draw the reticle (filtered by the "botao" property).
--curved puts the buttons side by side on a 3 m arc around the player (curved panels facing the eye).
"""
import bpy
import math
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
# Button labels are 3D text objects; --no-text leaves only the colored planes.
WITH_TEXT = "--no-text" not in argv
CURVED = "--curved" in argv
output = next((a for a in argv if not a.startswith("--")), "vr_menu.range")

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
gs = scene.game_settings
gs.show_debug_properties = True
gs.stereo = 'STEREO'
gs.stereo_mode = 'SIDEBYSIDE'
gs.stereo_eye_separation = 0.064
gs.vr_head_tracking = True
gs.vr_lens_distortion = True
gs.vr_lens_strength = 30
gs.vr_head_smoothing = 40
gs.vr_vignette = 50
gs.vr_recenter_time = 2000


def material(name, color):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    return mat


def curved_panel(name, radius, angle, width, height, z, segments=8):
    """Piece of a cylinder around the eye (x=y=0), centered at angle (rad, 0 = +y), normals toward the eye."""
    verts, faces = [], []
    for i in range(segments + 1):
        a = angle - width / 2 + width * i / segments
        x, y = -math.sin(a) * radius, math.cos(a) * radius
        verts += [(x, y, z - height / 2), (x, y, z + height / 2)]
        if i:
            b = 2 * (i - 1)
            faces.append((b, b + 1, b + 3, b + 2))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    scene.objects.link(obj)
    scene.objects.active = obj
    obj.select = True
    return obj


def add(obj, kind, type_, **kw):
    name = "%s_%s" % (kind, type_.lower())
    getattr(bpy.ops.logic, kind + "_add")(type=type_, name=name, object=obj.name)
    brick = getattr(obj.game, kind + "s")[name]
    for key, value in kw.items():
        setattr(brick, key, value)
    return brick


bpy.ops.mesh.primitive_plane_add(location=(0, 0, 0), radius=10)
floor = bpy.context.object
floor.name = "Chao"
floor.game.physics_type = 'STATIC'
floor.data.materials.append(material("ChaoMat", (0.3, 0.3, 0.3)))

bpy.ops.object.lamp_add(type='SUN', location=(0, 0, 10), rotation=(0.5, 0.2, 0))

bpy.ops.object.camera_add(location=(0, 0, 1.6), rotation=(math.pi / 2, 0, 0))
cam = bpy.context.object
cam.name = "Camera"
scene.camera = cam
reticle = add(cam, "sensor", 'RAY', axis='GAZE', range=20, property="botao",
              gaze_time=1000, use_gaze_reticle=True)

for i, (label, color) in enumerate((("Jogar", (0.2, 0.8, 0.3)), ("Opcoes", (0.2, 0.5, 1.0)),
                                    ("Sair", (1.0, 0.3, 0.2)))):
    if CURVED:
        # 24 deg per button, 4 deg gap, at eye height.
        angle = math.radians((1 - i) * 28)
        z = 1.6
        button = curved_panel("Botao" + label, 3.0, angle, math.radians(24), 0.4, z)
    else:
        angle = 0.0
        z = 2.1 - i * 0.5
        bpy.ops.mesh.primitive_plane_add(location=(0, 3, z), rotation=(math.pi / 2, 0, 0))
        button = bpy.context.object
        button.name = "Botao" + label
        button.scale = (0.6, 0.2, 1)
    button.game.physics_type = 'STATIC'
    button.data.materials.append(material(label + "Mat", color))
    bpy.ops.object.game_property_new(type='BOOL', name="botao")
    bpy.ops.object.game_property_new(type='INT', name="cliques")
    button.game.properties["cliques"].show_debug = True

    if WITH_TEXT:
        # Label just in front of the panel, centered on its angle and turned to the eye.
        r = 2.97 if CURVED else 2.98
        ox = 0.07 * len(label) / 2 if CURVED else 0.25
        loc = (-math.sin(angle) * r - math.cos(angle) * ox, math.cos(angle) * r - math.sin(angle) * ox, z - 0.07)
        bpy.ops.object.text_add(location=loc, rotation=(math.pi / 2, 0, angle))
        text = bpy.context.object
        text.name = "Texto" + label
        text.data.body = label
        text.scale = (0.18, 0.18, 0.18)
        text.game.physics_type = 'NO_COLLISION'
        text.parent = button
        text.matrix_parent_inverse = button.matrix_world.inverted()

    gaze = add(button, "sensor", 'RAY', axis='GAZE', range=20, gaze_time=1000, use_gaze_self=True,
                use_gaze_highlight=True)
    cont = add(button, "controller", 'LOGIC_AND')
    act = add(button, "actuator", 'PROPERTY', mode='ADD', property="cliques", value="1")
    gaze.link(cont)
    cont.link(actuator=act)

bpy.ops.wm.save_as_mainfile(filepath=bpy.path.abspath(output))
print("SAVED", output)
