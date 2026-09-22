# Gera cenas para validar visualmente (nao via captura automatizada - ver AGENTS.md)
# a combinacao de Lamps de cena (Sun + Point) com IBL ligado no BLENDER_GAME.
# Uso: RangeEngine.exe -b --python make_lights_ibl.py
import bpy, math, os

here = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()


def build(tag, use_ibl, add_point):
    bpy.ops.wm.open_mainfile(filepath=os.path.join(here, "pbr_test.blend"))
    scn = bpy.context.scene
    scn.render.engine = 'BLENDER_GAME'
    gs = scn.game_settings
    gs.use_shading_nodes = True
    gs.use_glsl_environment_lighting = use_ibl
    gs.use_glsl_shadows = True

    # pbr_test.blend traz logic bricks de captura automatica (endGame apos 45
    # frames) usados no diagnostico anterior; remove-los para permitir jogar
    # a cena interativamente sem fechar sozinha.
    cam = scn.camera
    if cam is not None:
        for s in list(cam.game.sensors):
            bpy.ops.logic.sensor_remove(sensor=s.name, object=cam.name)
        for c in list(cam.game.controllers):
            bpy.ops.logic.controller_remove(controller=c.name, object=cam.name)
    if "shot.py" in bpy.data.texts:
        bpy.data.texts.remove(bpy.data.texts["shot.py"])

    if add_point:
        bpy.ops.object.lamp_add(type='POINT', location=(-2.5, -3.5, 3.0))
        point = bpy.context.object
        point.data.energy = 1.5
        point.data.distance = 15.0
        point.name = "PointTest"

    out = os.path.join(here, "game_lights_ibl_%s.blend" % tag)
    bpy.ops.wm.save_as_mainfile(filepath=out)
    print("SALVO", out, "engine=%s ibl=%s shading_nodes=%s shadows=%s" % (
        scn.render.engine, gs.use_glsl_environment_lighting, gs.use_shading_nodes, gs.use_glsl_shadows))


# 1) so IBL (sem Point extra), so o Sun ja presente em pbr_test.blend
build("sun_ibl", use_ibl=True, add_point=False)
# 2) Sun + Point, IBL ligado -> caso alvo do item 4
build("sun_point_ibl", use_ibl=True, add_point=True)
# 3) Sun + Point, IBL desligado -> baseline para comparar visualmente com (2)
build("sun_point_noibl", use_ibl=False, add_point=True)
