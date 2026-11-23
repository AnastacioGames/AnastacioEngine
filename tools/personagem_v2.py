"""Personagem v2 por etapas (docs/personagem-v2-plan.md).

  build\\bin\\AnastacioEngine.exe -b --factory-startup --python tools\\personagem_v2.py -- \\
      importar <arquivo.obj> <pasta_de_trabalho> [esqueleto]

Cada etapa grava NN_<etapa>.range + render de conferência na pasta de trabalho e imprime PERSONAGEM_V2 {...}.
"""

import json
import os
import sys

import range_character_v2 as v2


def _abrir(out_dir, *nomes):
    """Abre o 1º checkpoint que existir (sem corte da cabeça as etapas 4 e 8 não rodam, 2026-11-18)."""
    import bpy
    for n in nomes:
        f = os.path.join(out_dir, n + ".range")
        if os.path.isfile(f):
            bpy.ops.wm.open_mainfile(filepath=f)
            return n
    raise FileNotFoundError(", ".join(nomes))


def etapa_importar(args):
    obj_path, out_dir = args[0], args[1]
    skeleton = args[2] if len(args) > 2 else v2.DEFAULT_SKELETON
    pieces, info = v2.import_fuse(obj_path, skeleton)
    info["arquivo"] = v2.save_checkpoint(out_dir, "01_importado")
    info["render"] = v2.render_check(os.path.join(out_dir, "01_importado.png"), pieces)
    return info


def etapa_importar_mixamo(args):
    """-- importar_mixamo <piloto.fbx> <pasta_de_trabalho> [esqueleto]: personagem direto do Mixamo (sem Fuse).
    Extrai as texturas embutidas do FBX para <pasta>/00_original/textures (se ainda não estiverem lá), guarda o
    FBX em 00_original e grava 01_importado.range como se fosse a saída da etapa importar. Daí em diante é igual."""
    import re
    import struct
    fbx, out_dir = args[0], args[1]
    skeleton = args[2] if len(args) > 2 else v2.DEFAULT_SKELETON
    orig = os.path.join(out_dir, "00_original")
    tex_dir = os.path.join(orig, "textures")
    os.makedirs(tex_dir, exist_ok=True)
    dst = os.path.join(orig, os.path.basename(fbx))
    if not os.path.isfile(dst):
        import shutil
        shutil.copy2(fbx, dst)
    data = open(dst, "rb").read()
    names = ["Diffuse", "Specular", "Glossiness", "Normal"]   # ordem em que o Mixamo embute
    prefix = None
    for m in re.finditer(rb"(\w+)_1001_Diffuse\.png", data):
        prefix = m.group(1).decode()
        break
    if prefix is None:
        raise ValueError("FBX sem textura embutida reconhecível (<nome>_1001_Diffuse.png)")
    # nomes na ordem real dos PNGs embutidos: o último "<prefix>_1001_<Tipo>.png" antes de cada assinatura PNG
    for i, m in enumerate(re.finditer(b"\x89PNG\r\n\x1a\n", data)):
        s, p = m.start(), m.start() + 8
        while True:
            ln, = struct.unpack(">I", data[p:p + 4])
            typ = data[p + 4:p + 8]
            p += 12 + ln
            if typ == b"IEND":
                break
        kind = re.findall(rb"_1001_(\w+)\.png", data[max(0, s - 400):s])
        kind = kind[-1].decode() if kind else names[i]
        f = os.path.join(tex_dir, "%s_%s.png" % (prefix, kind))
        if not os.path.isfile(f):
            open(f, "wb").write(data[s:p])
    pieces, info = v2.import_mixamo(dst, tex_dir, prefix + "_1001", skeleton)
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
    """-- cabeca <pasta_de_trabalho> [--cortar]: abre 03_pesos.range, grava 04_cabeca.range. Padrão (2026-11-18):
    sem corte, só os pesos da cabeça (100 % Head acima do plano do queixo) e do pescoço em degradê."""
    import bpy
    out_dir = args[0]
    bpy.ops.wm.open_mainfile(filepath=os.path.join(out_dir, "03_pesos.range"))
    scene = bpy.context.scene
    arm = next(o for o in scene.objects if o.type == 'ARMATURE')
    pieces = [o for o in scene.objects if o.type == 'MESH']
    if "--cortar" in args:   # antigo: cabeça separada para o Impostor de Caixa (não usar, 2026-11-18)
        head, info = v2.split_head(arm, pieces)
        info["arquivo"] = v2.save_checkpoint(out_dir, "04_cabeca")
        rest = [o for o in scene.objects if o.type == 'MESH' and o is not head]
        info["render"] = v2.render_head(os.path.join(out_dir, "04_cabeca.png"), arm, head, rest)
        return info
    info = v2.head_weights_whole(arm, pieces)
    info["arquivo"] = v2.save_checkpoint(out_dir, "04_cabeca")
    return info


def etapa_maos(args):
    """-- maos <pasta_de_trabalho>: abre 04_cabeca.range (ou 03_pesos.range, sem corte), grava 05_maos.range."""
    import bpy
    out_dir = args[0]
    _abrir(out_dir, "04_cabeca", "03_pesos")
    scene = bpy.context.scene
    arm = next(o for o in scene.objects if o.type == 'ARMATURE')
    pieces = [o for o in scene.objects if o.type == 'MESH']
    info = {"protegidos": v2.protect_hands(arm, pieces), "pegadas": v2.make_grip_actions(arm)}
    info["arquivo"] = v2.save_checkpoint(out_dir, "05_maos")
    info["render"] = v2.render_grips(os.path.join(out_dir, "05_maos.png"), arm, pieces)
    return info


def etapa_saia(args):
    """-- saia <pasta_de_trabalho> [--peca Tops]: opcional (vestido longo), abre 05_maos.range e grava 05_saia.range com os
    ossos da barra (Skirt<i>_<k>); o atlas abre este arquivo se ele existir."""
    import bpy
    out_dir = args[0]
    _abrir(out_dir, "05_maos")
    scene = bpy.context.scene
    arm = next(o for o in scene.objects if o.type == 'ARMATURE')
    nome = args[args.index("--peca") + 1] if "--peca" in args else "Tops"
    info = v2.add_skirt_bones(arm, bpy.data.objects[nome], report=lambda *a: None)
    info["arquivo"] = v2.save_checkpoint(out_dir, "05_saia")
    return info


def etapa_rabo(args):
    """-- rabo <pasta_de_trabalho> [--elos 3] [--fundir-dedos]: opcional (rabo de cavalo/trança), abre 05_saia.range (ou 05_maos.range) e grava
    05_rabo.range com os ossos Tail1..3; o atlas abre este arquivo se ele existir."""
    import bpy
    out_dir = args[0]
    _abrir(out_dir, "05_saia", "05_maos")
    scene = bpy.context.scene
    arm = next(o for o in scene.objects if o.type == 'ARMATURE')
    elos = int(args[args.index("--elos") + 1]) if "--elos" in args else v2.TAIL_LINKS
    info = v2.add_ponytail_bones(arm, bpy.data.objects["Hair"], bpy.data.objects["Body"], links=elos,
                                 report=lambda *a: None, braid="--tranca" in args)
    if "--fundir-dedos" in args:   # corpo com saia + rabo passa de 64 grupos sem isto
        info["dedos_pe"] = v2.merge_toes_into_feet(arm, report=lambda *a: None)
    info["arquivo"] = v2.save_checkpoint(out_dir, "05_rabo")
    return info


def etapa_atlas(args):
    """-- atlas <pasta_de_trabalho> [Nome]: abre 05_maos.range, grava 06_atlas.range + textures/ + render."""
    import bpy
    out_dir = args[0]
    name = args[1] if len(args) > 1 else os.path.basename(os.path.normpath(out_dir))
    _abrir(out_dir, "05_rabo", "05_saia", "05_maos")
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
    head = [o for o in [bpy.data.objects.get("Cabeca")] if o]
    info["render"] = v2.render_check(os.path.join(out_dir, "07_lod.png"), [body] + head)
    for lvl in body.lod_levels[1:]:
        info["render"] += v2.render_check(os.path.join(out_dir, "07_%s.png" % lvl.object.name), [lvl.object] + head,
                                          views=(("frente", (0, 1, 0)),))
    info["render"] += v2.render_hands(os.path.join(out_dir, "07_maos.png"), arm, [body])
    return info


def etapa_impostor(args):
    """-- impostor <pasta_de_trabalho> [--res 512]: abre 07_lod.range, grava 08_impostor.range (cabeça com
    Impostor de Caixa como LOD). A Cabeca não passa pela redução da etapa 7: o bake sai da cabeça cheia do Fuse."""
    import bpy
    out_dir = args[0]
    res = args[args.index("--res") + 1] if "--res" in args else v2.HEAD_IMPOSTOR_RES
    bpy.ops.wm.open_mainfile(filepath=os.path.join(out_dir, "07_lod.range"))
    head = bpy.data.objects["Cabeca"]
    card, info = v2.bake_head_impostor(head, resolution=res)
    info["cabeca_tris"] = sum(len(p.vertices) - 2 for p in head.data.polygons)
    info["arquivo"] = v2.save_checkpoint(out_dir, "08_impostor")
    return info


def etapa_fechar(args):
    """-- fechar <pasta_de_trabalho> [Nome] [--projeto <jogo>] [--sem-ragdoll]: abre 08_impostor.range (ou
    07_lod.range, sem corte da cabeça) e grava
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
    _abrir(out_dir, "08_impostor", "07_lod")
    scene = bpy.context.scene
    arm = next(o for o in scene.objects if o.type == 'ARMATURE')
    body, head = bpy.data.objects["Body"], bpy.data.objects.get("Cabeca")
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


ETAPAS = {"importar": etapa_importar, "importar_mixamo": etapa_importar_mixamo, "esqueleto": etapa_esqueleto, "pesos": etapa_pesos,
          "cabeca": etapa_cabeca, "maos": etapa_maos, "saia": etapa_saia, "rabo": etapa_rabo, "atlas": etapa_atlas, "lod": etapa_lod,
          "impostor": etapa_impostor, "fechar": etapa_fechar, "corpo": etapa_corpo}


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if not argv or argv[0] not in ETAPAS:
        print("uso: -- <%s> ..." % "|".join(ETAPAS))
        sys.exit(1)
    info = ETAPAS[argv[0]](argv[1:])
    print("PERSONAGEM_V2 " + json.dumps(info, ensure_ascii=False, default=str))


main()
