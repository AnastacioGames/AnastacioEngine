# Gera pares (opcao PBR desligada/ligada) com engine BLENDER_GAME para as cenas variants e grade.
import bpy, os
here = os.path.dirname(os.path.abspath(__file__))
for src, tag in (("pbr_variants.blend", "variants"), ("pbr_test.blend", "grid")):
    for on in (False, True):
        bpy.ops.wm.open_mainfile(filepath=os.path.join(here, src))
        sc = bpy.context.scene
        sc.render.engine = 'BLENDER_GAME'
        sc.game_settings.use_shading_nodes = on
        out = os.path.join(here, "game_%s_%s.blend" % (tag, "pbr" if on else "off"))
        bpy.ops.wm.save_as_mainfile(filepath=out)
        print("SALVO", out, sc.render.engine, sc.game_settings.use_shading_nodes)
