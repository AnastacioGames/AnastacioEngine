"""Personagem v2 por etapas (docs/personagem-v2-plan.md).

  build\\bin\\AnastacioEngine.exe -b --factory-startup --python tools\\personagem_v2.py -- \\
      importar <arquivo.obj> <pasta_de_trabalho> [esqueleto]

Cada etapa grava NN_<etapa>.range + render de conferência na pasta de trabalho e imprime PERSONAGEM_V2 {...}.
"""

import json
import os
import sys

import range_character_v2 as v2


def etapa_importar(args):
    obj_path, out_dir = args[0], args[1]
    skeleton = args[2] if len(args) > 2 else v2.DEFAULT_SKELETON
    pieces, info = v2.import_fuse(obj_path, skeleton)
    info["arquivo"] = v2.save_checkpoint(out_dir, "01_importado")
    info["render"] = v2.render_check(os.path.join(out_dir, "01_importado.png"), pieces)
    return info


def etapa_esqueleto(args):
    """-- esqueleto <pasta_de_trabalho> [esqueleto]: abre 01_importado.range, grava 02_esqueleto.range."""
    import bpy
    out_dir = args[0]
    skeleton = args[1] if len(args) > 1 else v2.DEFAULT_SKELETON
    bpy.ops.wm.open_mainfile(filepath=os.path.join(out_dir, "01_importado.range"))
    pieces = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    arm, info = v2.fit_skeleton_v2(pieces, skeleton)
    info["arquivo"] = v2.save_checkpoint(out_dir, "02_esqueleto")
    info["maos_json"] = v2.dump_hand(os.path.join(out_dir, "02_maos.json"), arm, pieces)
    return info


def etapa_pesos(args):
    """-- pesos <pasta_de_trabalho>: abre 02_esqueleto.range, grava 03_pesos.range + renders das mãos."""
    import bpy
    out_dir = args[0]
    bpy.ops.wm.open_mainfile(filepath=os.path.join(out_dir, "02_esqueleto.range"))
    scene = bpy.context.scene
    arm = next(o for o in scene.objects if o.type == 'ARMATURE')
    pieces = [o for o in scene.objects if o.type == 'MESH']
    info = v2.weights_v2(arm, pieces)
    info["arquivo"] = v2.save_checkpoint(out_dir, "03_pesos")
    info["render"] = v2.render_hands(os.path.join(out_dir, "03_maos.png"), arm, pieces)
    return info


def etapa_cabeca(args):
    """-- cabeca <pasta_de_trabalho>: abre 03_pesos.range, grava 04_cabeca.range + renders do corte."""
    import bpy
    out_dir = args[0]
    bpy.ops.wm.open_mainfile(filepath=os.path.join(out_dir, "03_pesos.range"))
    scene = bpy.context.scene
    arm = next(o for o in scene.objects if o.type == 'ARMATURE')
    pieces = [o for o in scene.objects if o.type == 'MESH']
    head, info = v2.split_head(arm, pieces)
    info["arquivo"] = v2.save_checkpoint(out_dir, "04_cabeca")
    rest = [o for o in scene.objects if o.type == 'MESH' and o is not head]
    info["render"] = v2.render_head(os.path.join(out_dir, "04_cabeca.png"), arm, head, rest)
    return info


def etapa_maos(args):
    """-- maos <pasta_de_trabalho>: abre 04_cabeca.range, grava 05_maos.range + renders das pegadas."""
    import bpy
    out_dir = args[0]
    bpy.ops.wm.open_mainfile(filepath=os.path.join(out_dir, "04_cabeca.range"))
    scene = bpy.context.scene
    arm = next(o for o in scene.objects if o.type == 'ARMATURE')
    pieces = [o for o in scene.objects if o.type == 'MESH']
    info = {"protegidos": v2.protect_hands(arm, pieces), "pegadas": v2.make_grip_actions(arm)}
    info["arquivo"] = v2.save_checkpoint(out_dir, "05_maos")
    info["render"] = v2.render_grips(os.path.join(out_dir, "05_maos.png"), arm, pieces)
    return info


def etapa_atlas(args):
    """-- atlas <pasta_de_trabalho> [Nome]: abre 05_maos.range, grava 06_atlas.range + textures/ + render."""
    import bpy
    out_dir = args[0]
    name = args[1] if len(args) > 1 else os.path.basename(os.path.normpath(out_dir))
    bpy.ops.wm.open_mainfile(filepath=os.path.join(out_dir, "05_maos.range"))
    scene = bpy.context.scene
    pieces = [o for o in scene.objects if o.type == 'MESH']
    body, info = v2.atlas_body(pieces, os.path.join(out_dir, "textures"), "Group" + name)
    info["arquivo"] = v2.save_checkpoint(out_dir, "06_atlas")
    meshes = [o for o in scene.objects if o.type == 'MESH']
    info["render"] = v2.render_check(os.path.join(out_dir, "06_atlas.png"), meshes)
    return info


def etapa_lod(args):
    """-- lod <pasta_de_trabalho>: abre 06_atlas.range, grava 07_lod.range + renders (nível 0 e LODs, mãos)."""
    import bpy
    out_dir = args[0]
    bpy.ops.wm.open_mainfile(filepath=os.path.join(out_dir, "06_atlas.range"))
    scene = bpy.context.scene
    arm = next(o for o in scene.objects if o.type == 'ARMATURE')
    body = bpy.data.objects["Body"]
    info = v2.reduce_body(arm, body)
    info["arquivo"] = v2.save_checkpoint(out_dir, "07_lod")
    head = bpy.data.objects["Cabeca"]
    info["render"] = v2.render_check(os.path.join(out_dir, "07_lod.png"), [body, head])
    for lvl in body.lod_levels[1:]:
        info["render"] += v2.render_check(os.path.join(out_dir, "07_%s.png" % lvl.object.name), [lvl.object, head],
                                          views=(("frente", (0, 1, 0)),))
    info["render"] += v2.render_hands(os.path.join(out_dir, "07_maos.png"), arm, [body])
    return info


def etapa_impostor(args):
    """-- impostor <pasta_de_trabalho>: abre 07_lod.range, grava 08_impostor.range (cabeça com Impostor de
    Caixa como LOD). A Cabeca não passa pela redução da etapa 7: o bake sai da cabeça cheia do Fuse."""
    import bpy
    out_dir = args[0]
    bpy.ops.wm.open_mainfile(filepath=os.path.join(out_dir, "07_lod.range"))
    head = bpy.data.objects["Cabeca"]
    card, info = v2.bake_head_impostor(head)
    info["cabeca_tris"] = sum(len(p.vertices) - 2 for p in head.data.polygons)
    info["arquivo"] = v2.save_checkpoint(out_dir, "08_impostor")
    return info


def etapa_fechar(args):
    """-- fechar <pasta_de_trabalho> [Nome] [--projeto <jogo>] [--sem-ragdoll]: abre 08_impostor.range e grava
    <pasta>/09_piloto/Group<Nome>.range (não mexe no piloto que o jogo usa hoje)."""
    import bpy
    out_dir = args[0]
    game = r"D:\ProjetoRolimaRacer"
    name = None
    rest = list(args[1:])
    while rest:
        a = rest.pop(0)
        if a == "--projeto" and rest:
            game = rest.pop(0)
        elif not a.startswith("--") and name is None:
            name = a
    name = name or os.path.basename(os.path.normpath(out_dir))
    bpy.ops.wm.open_mainfile(filepath=os.path.join(out_dir, "08_impostor.range"))
    scene = bpy.context.scene
    arm = next(o for o in scene.objects if o.type == 'ARMATURE')
    body, head = bpy.data.objects["Body"], bpy.data.objects["Cabeca"]
    return v2.finish_pilot_v2(arm, body, head, name, game, os.path.join(out_dir, "09_piloto"),
                              ragdoll="--sem-ragdoll" not in args)


def etapa_corpo(args):
    """-- corpo <pasta_de_trabalho> [Nome] [--dist 20] [--lod2 15] [--res 512] [--projeto <jogo>]: etapa 11.
    Assa o Impostor de Caixa do corpo cheio sentado (06_atlas.range) em 10_impostor_corpo.range e o põe como
    último LOD do 09_piloto/Group<Nome>.range (grava por cima; refaça a etapa fechar para repetir)."""
    import bpy
    out_dir = args[0]
    game = r"D:\ProjetoRolimaRacer"
    name, dist, lod2, res = None, v2.BODY_IMPOSTOR_DIST, v2.BODY_IMPOSTOR_LOD2, v2.BODY_IMPOSTOR_RES
    rest = list(args[1:])
    while rest:
        a = rest.pop(0)
        if a == "--dist" and rest:
            dist = float(rest.pop(0))
        elif a == "--lod2" and rest:
            lod2 = float(rest.pop(0))
        elif a == "--res" and rest:
            res = rest.pop(0)
        elif a == "--projeto" and rest:
            game = rest.pop(0)
        elif not a.startswith("--") and name is None:
            name = a
    name = name or os.path.basename(os.path.normpath(out_dir))
    bpy.ops.wm.open_mainfile(filepath=os.path.join(out_dir, "06_atlas.range"))
    arm = next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
    card = v2.bake_body_impostor(arm, bpy.data.objects["Body"], bpy.data.objects["Cabeca"], game, res)
    card_file = os.path.join(out_dir, "10_impostor_corpo.range")
    bpy.data.libraries.write(card_file, {card}, fake_user=True)
    card_name = card.name
    pilot = os.path.join(out_dir, "09_piloto", "Group%s.range" % name)
    bpy.ops.wm.open_mainfile(filepath=pilot)
    with bpy.data.libraries.load(card_file) as (src, dst):
        dst.objects = [card_name]
    card = dst.objects[0]
    card.use_fake_user = False
    group = "Group" + name
    ob = bpy.data.objects
    info = v2.add_body_impostor(ob["Body" + group], ob.get("Body%s.001" % group), ob["Cabeca" + group], card, name,
                                dist, lod2)
    bpy.context.user_preferences.filepaths.save_version = 0
    bpy.ops.wm.save_mainfile()
    info["arquivo"] = pilot
    info["cartao_arquivo"] = card_file
    return info


ETAPAS = {"importar": etapa_importar, "esqueleto": etapa_esqueleto, "pesos": etapa_pesos,
          "cabeca": etapa_cabeca, "maos": etapa_maos, "atlas": etapa_atlas, "lod": etapa_lod,
          "impostor": etapa_impostor, "fechar": etapa_fechar, "corpo": etapa_corpo}


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if not argv or argv[0] not in ETAPAS:
        print("uso: -- <%s> ..." % "|".join(ETAPAS))
        sys.exit(1)
    info = ETAPAS[argv[0]](argv[1:])
    print("PERSONAGEM_V2 " + json.dumps(info, ensure_ascii=False, default=str))


main()
