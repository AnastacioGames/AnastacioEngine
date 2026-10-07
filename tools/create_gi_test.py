"""Indirect light (GI) before/after test scenes (Game PBR, Shading Nodes). Does not need engine changes.

Run with:  RangeEngine -b --python tools/create_gi_test.py -- <output.range> [cornell|sala] [--shot] [--ref]
- cornell: closed box, red left wall, green right wall, white floor/ceiling/back, lamp near the ceiling,
  a tall and a short white box. With GI the white boxes and floor pick up red/green near the walls and the
  shadows are not black.
- sala (default): room 8 x 6 x 3 with a window on the right wall, Sun entering through it and a bright patch
  on the floor; the rest of the room should be lit only by the bounce of that patch. A reflection probe
  (current engine feature) covers the room, so "antes" is the best the engine does today. An orange sphere
  goes back and forth through the sun patch: with a light volume it should change tone smoothly.
--shot    adds a camera controller that saves <output>_game.png at frame 30 and ends the game
          (the sphere stops so the before/after shots match).
--bake    bakes the lightmap (World > Baked Lighting, scene.ae_lightmap_bake) before saving: the "depois".
--ref     also renders the same camera with Cycles (path tracing, reference "how it should look")
          into <output>_cycles.png.
"""
import bpy
import math
import os
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = os.path.abspath(argv[0] if argv else "gi_test.range")
variant = "cornell" if "cornell" in argv else "sala"
want_shot = "--shot" in argv
want_cycles = "--ref" in argv
want_bake = "--bake" in argv
base = os.path.splitext(output)[0].replace("\\", "/")

bpy.ops.wm.read_factory_settings(use_empty=True)
import addon_utils
addon_utils.enable("cycles")
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 1280
scene.game_settings.resolution_y = 720
scene.game_settings.use_shading_nodes = True
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.resolution_percentage = 100

world = bpy.data.worlds.new("GI World")
world.use_nodes = True
sky = (0.35, 0.5, 0.8, 1.0) if variant == "sala" else (0.0, 0.0, 0.0, 1.0)
world.node_tree.nodes["Background"].inputs["Color"].default_value = sky
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
scene.world = world


def material(name, color, roughness=0.8):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = color + (1.0,)
    bsdf.inputs["Roughness"].default_value = roughness
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return m


WHITE = material("White", (0.75, 0.75, 0.75))
RED = material("Red", (0.7, 0.05, 0.05))
GREEN = material("Green", (0.05, 0.6, 0.08))
ORANGE = material("Orange", (0.9, 0.35, 0.05), 0.4)
WOOD = material("Floor", (0.55, 0.38, 0.22), 0.6)


def box(name, center, size, mat):
    bpy.ops.mesh.primitive_cube_add(location=center)
    ob = bpy.context.object
    ob.name = name
    ob.scale = (size[0] / 2, size[1] / 2, size[2] / 2)
    ob.data.materials.append(mat)
    return ob


def lamp(kind, name, location, rotation, energy, cycles_strength, color=(1.0, 0.95, 0.85)):
    bpy.ops.object.lamp_add(type=kind, location=location, rotation=rotation)
    ob = bpy.context.object
    ob.name = name
    ob.data.energy = energy
    ob.data.color = color
    ob.data.shadow_method = 'RAY_SHADOW'
    ob.data.use_nodes = True
    ob.data.node_tree.nodes["Emission"].inputs["Strength"].default_value = cycles_strength
    if hasattr(ob.data, "cycles"):
        ob.data.cycles.cast_shadow = True
    return ob


t = 0.1  # wall thickness
if variant == "cornell":
    s = 4.0
    box("Floor", (0, 0, -t / 2), (s, s, t), WHITE)
    box("Ceiling", (0, 0, s + t / 2), (s, s, t), WHITE)
    box("Back", (0, s / 2 + t / 2, s / 2), (s, t, s), WHITE)
    box("Left", (-s / 2 - t / 2, 0, s / 2), (t, s, s), RED)
    box("Right", (s / 2 + t / 2, 0, s / 2), (t, s, s), GREEN)
    tall = box("TallBox", (-0.7, 0.6, 1.2), (1.1, 1.1, 2.4), WHITE)
    tall.rotation_euler.z = math.radians(18)
    short = box("ShortBox", (0.75, -0.5, 0.6), (1.1, 1.1, 1.2), WHITE)
    short.rotation_euler.z = math.radians(-17)
    lamp('POINT', "CeilingLamp", (0, 0, s - 0.3), (0, 0, 0), 2.0, 300.0)
    bpy.ops.object.camera_add(location=(0, -7.6, s / 2), rotation=(math.radians(90), 0, 0))
    scene.camera = bpy.context.object
    scene.camera.data.lens = 35.0
    probe_center, probe_scale = (0, 0, s / 2), (s / 2, s / 2, s / 2)
else:
    w, d, h = 8.0, 6.0, 3.0
    box("Floor", (0, 0, -t / 2), (w, d, t), WOOD)
    box("Ceiling", (0, 0, h + t / 2), (w, d, t), WHITE)
    box("Back", (0, d / 2 + t / 2, h / 2), (w, t, h), WHITE)
    box("Front", (0, -d / 2 - t / 2, h / 2), (w, t, h), WHITE)
    box("Left", (-w / 2 - t / 2, 0, h / 2), (t, d, h), RED)
    # right wall with a window 2.4 wide x 1.4 tall (sill at 0.8)
    win_w, sill, win_h = 2.4, 0.8, 1.4
    side = (d - win_w) / 2
    box("RightA", (w / 2 + t / 2, -d / 2 + side / 2, h / 2), (t, side, h), WHITE)
    box("RightB", (w / 2 + t / 2, d / 2 - side / 2, h / 2), (t, side, h), WHITE)
    box("RightSill", (w / 2 + t / 2, 0, sill / 2), (t, win_w, sill), WHITE)
    box("RightTop", (w / 2 + t / 2, 0, (sill + win_h + h) / 2), (t, win_w, h - sill - win_h), WHITE)
    box("Sofa", (-2.6, 1.2, 0.4), (1.2, 2.6, 0.8), GREEN)
    box("Table", (0.2, 0.8, 0.35), (1.4, 0.9, 0.7), WHITE)
    # Sun from the right, low, through the window onto the floor
    lamp('SUN', "Sun", (8, 0, 6), (0, math.radians(55), 0), 3.0, 4.0)
    bpy.ops.mesh.primitive_uv_sphere_add(location=(1.5, -1.2, 0.5), size=0.5, segments=32, ring_count=16)
    sphere = bpy.context.object
    sphere.name = "MovingSphere"
    sphere.game.physics_type = 'DYNAMIC'  # moving: lit by the probe, not baked
    sphere.data.materials.append(ORANGE)
    bpy.ops.object.shade_smooth()
    if not want_shot:
        mover = bpy.data.texts.new("gi_move_sphere.py")
        mover.write(
            "import math\n"
            "from Range import logic\n"
            "own = logic.getCurrentController().owner\n"
            "own['t'] = own.get('t', 0.0) + 1.0 / 60.0\n"
            "own.worldPosition.x = 1.5 + 1.8 * math.sin(own['t'] * 0.6)\n"
        )
        scene.objects.active = sphere
        bpy.ops.logic.sensor_add(type='ALWAYS', object=sphere.name)
        bpy.ops.logic.controller_add(type='PYTHON', object=sphere.name)
        sphere.game.sensors[-1].use_pulse_true_level = True
        sphere.game.controllers[-1].text = mover
        sphere.game.sensors[-1].link(sphere.game.controllers[-1])
    bpy.ops.object.camera_add(location=(-3.6, -2.7, 1.7), rotation=(math.radians(84), 0, math.radians(-62)))
    scene.camera = bpy.context.object
    scene.camera.data.lens = 22.0
    probe_center, probe_scale = (0, 0, h / 2), (w / 2, d / 2, h / 2)

# Reflection probe over the whole room (diffuse from the same cubemap): today's best indirect light.
bpy.ops.object.empty_add(type='CUBE', location=probe_center)
probe = bpy.context.object
probe.name = "GIProbe"
probe.scale = probe_scale
bpy.ops.object.game_property_new(type='FLOAT', name="probe")
probe.game.properties["probe"].value = max(probe_scale) * 1.8
bpy.ops.object.game_property_new(type='BOOL', name="probe_realtime")
probe.game.properties["probe_realtime"].value = False

scene.game_settings.show_framerate_profile = False
scene.game_settings.show_debug_properties = False

if want_shot:
    shot = base + "_game.png"
    text = bpy.data.texts.new("gi_auto_screenshot.py")
    text.write(
        "import Range\n"
        "from Range import logic\n"
        "own = logic.getCurrentController().owner\n"
        "own['frame'] = own.get('frame', 0) + 1\n"
        "if own['frame'] == 30:\n"
        "    Range.render.makeScreenshot('%s')\n"
        "if own['frame'] == 36:\n"
        "    logic.endGame()\n" % shot
    )
    cam = scene.camera
    scene.objects.active = cam
    bpy.ops.logic.sensor_add(type='ALWAYS', object=cam.name)
    bpy.ops.logic.controller_add(type='PYTHON', object=cam.name)
    cam.game.sensors[-1].use_pulse_true_level = True
    cam.game.controllers[-1].text = text
    cam.game.sensors[-1].link(cam.game.controllers[-1])

if want_bake:
    scene.ae_lightmap_settings.samples = 8
    scene.ae_lightmap_settings.resolution = next((a[6:] for a in argv if a.startswith('--res=')), '256')
    scene.ae_lightmap_settings.use_gpu = False
    print("GI_TEST bake", bpy.ops.scene.ae_lightmap_bake())

bpy.ops.wm.save_as_mainfile(filepath=output)
print("GI_TEST saved", variant, output)

if want_cycles:
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 256
    scene.cycles.max_bounces = 6
    scene.view_settings.view_transform = 'Filmic' if 'Filmic' in [
        i.identifier for i in scene.view_settings.bl_rna.properties['view_transform'].enum_items] else 'Default'
    scene.render.filepath = base + "_cycles.png"
    bpy.ops.render.render(write_still=True)
    print("GI_TEST cycles reference", scene.render.filepath)
