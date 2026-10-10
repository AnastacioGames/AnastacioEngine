"""Overlay scene alpha after render.drawLine (bug reported by Kitsuy).

  RangeEngine -b --python tools/create_overlay_alpha_test.py -- projects-teste/overlay_alpha
  RangeRuntime projects-teste/overlay_alpha/overlay_alpha.range

Main scene: ground, a 2D filter and render.drawLine every frame. Overlay "HUD": a green
Alpha Blend plane (alpha 0.3) over the left half. With the bug the plane comes out opaque:
drawLine left the blend cache at Alpha, the 2D filter turned GL_BLEND off behind its back and
the HUD material skipped the blend switch. Screenshot at frame 40 (shot_<tag>.png), then quits.
Pass AUTO_QUIT=0 in the environment to keep it open.
"""
import bpy
import os
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
outdir = os.path.abspath(argv[0] if argv else "projects-teste/overlay_alpha")
os.makedirs(outdir, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)

MAIN = r'''import Range, os
from Range import logic, render
own = logic.getCurrentController().owner
scene = logic.getCurrentScene()
frame = own.get("frame", 0) + 1
own["frame"] = frame
if frame == 1:
    scene.filterManager.addFilter(0, logic.RAS_2DFILTER_CUSTOMFILTER,
        "uniform sampler2D bgl_RenderedTexture;\n"
        "void main() { gl_FragColor = texture2D(bgl_RenderedTexture, gl_TexCoord[0].st); }")
    logic.addScene("HUD", 1)
if os.environ.get("NO_DRAWLINE") != "1":
    for i in range(8):
        render.drawLine([-4 + i, -4, 0.1], [4 - i, 4, 0.1], [1, 0, 1])
if frame == 40:
    tag = os.environ.get("RANGE_SHOT_TAG", "shot")
    render.makeScreenshot(logic.expandPath("//shot_%s.png" % tag))
    print("[overlay_alpha] screenshot", tag, flush=True)
if frame == 45 and os.environ.get("AUTO_QUIT", "1") == "1":
    logic.endGame()
'''


def logic_script(ob, text):
    bpy.context.scene.objects.active = ob
    bpy.ops.logic.sensor_add(type='ALWAYS', object=ob.name)
    bpy.ops.logic.controller_add(type='PYTHON', object=ob.name)
    ob.game.sensors[-1].use_pulse_true_level = True
    ob.game.controllers[-1].text = text
    ob.game.sensors[-1].link(ob.game.controllers[-1])


def setup(scene):
    scene.render.engine = 'BLENDER_GAME'
    scene.game_settings.resolution_x, scene.game_settings.resolution_y = 960, 540
    scene.game_settings.vsync = 'OFF'


# --- Main scene
main = bpy.context.scene
main.name = "Main"
setup(main)
main.world = bpy.data.worlds.new("World")
main.world.horizon_color = (0.4, 0.25, 0.15)

bpy.ops.mesh.primitive_plane_add(radius=6)
ground = bpy.context.object
gmat = bpy.data.materials.new("Ground")
gmat.diffuse_color = (0.7, 0.45, 0.3)
ground.data.materials.append(gmat)

sun = bpy.data.objects.new("Sun", bpy.data.lamps.new("Sun", 'SUN'))
main.objects.link(sun)
sun.rotation_euler = (0.5, 0.2, 0.0)

cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
main.objects.link(cam)
cam.location = (0, -9, 7)
cam.rotation_euler = (0.9, 0, 0)
main.camera = cam
text = bpy.data.texts.new("main.py")
text.write(MAIN)
logic_script(cam, text)

# --- Overlay scene
hud = bpy.data.scenes.new("HUD")
setup(hud)
bpy.context.screen.scene = hud
hcam = bpy.data.objects.new("HudCam", bpy.data.cameras.new("HudCam"))
hud.objects.link(hcam)
hcam.data.type = 'ORTHO'
hcam.data.ortho_scale = 10
hcam.location = (0, 0, 10)
hud.camera = hcam

bpy.ops.mesh.primitive_plane_add(radius=2.5, location=(-2.5, 0, 0))
panel = bpy.context.object
pmat = bpy.data.materials.new("PanelAlpha")
pmat.diffuse_color = (0.0, 1.0, 0.0)
pmat.use_shadeless = True
pmat.use_transparency = True
pmat.alpha = 0.3
pmat.game_settings.alpha_blend = 'ALPHA'
panel.data.materials.append(pmat)

bpy.context.screen.scene = main
path = os.path.join(outdir, "overlay_alpha.range")
bpy.ops.wm.save_as_mainfile(filepath=path, check_existing=False, compress=False)
print("[overlay_alpha] wrote", path)
