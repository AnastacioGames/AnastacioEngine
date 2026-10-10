# Roda o Play do editor (player embutido) em editor_test.blend e confere o estado depois.
# Uso (com janela, não -b): RangeEngine editor_test.blend -P run_editor_test.py
import bpy, os

feito = [False]


def rodar(_scene):
    if feito[0]:
        return
    feito[0] = True
    bpy.app.handlers.scene_update_post.remove(rodar)
    win = bpy.context.window_manager.windows[0]
    area = next(a for a in win.screen.areas if a.type == 'VIEW_3D')
    region = next(r for r in area.regions if r.type == 'WINDOW')
    bpy.ops.view3d.game_start({"window": win, "screen": win.screen, "area": area, "region": region,
                               "scene": win.screen.scene})
    fase = bpy.data.scenes["Fase"]
    linhas = ["depois do Play: " + " ".join("%s=%s" % (n, fase.objects[n].convert_object) for n in "ABC"),
              "esperado:       A=False B=True C=False",
              "malha C: %d vertices (esperado 3)" % len(bpy.data.meshes["C"].vertices)]
    with open(bpy.path.abspath("//editor_results.txt"), "a") as f:
        f.write("\n".join(linhas) + "\n")
    bpy.ops.wm.quit_blender()


bpy.app.handlers.scene_update_post.append(rodar)
