"""Cria um personagem pronto (Group<Nome>.range + textures/) a partir do OBJ exportado do Fuse.

    build/bin/AnastacioEngine.exe -b --factory-startup --python tools/create_fuse_character.py -- \
        <arquivo.obj> <Nome> <pasta de saida> [esqueleto] [--sem-ragdoll] [--projeto <pasta do jogo>]

esqueleto: id da biblioteca (padrao mixamo_two_fingers; veja datafiles/characters).
--projeto: raiz do jogo, para registrar o componente de ragdoll do RolimaRacer
(scripts.VehicleSystem.ragdoll_system.ragdoll.Ragdoll).
Plano e formato: docs/personagem-auto-rig-plan.md.
"""
import sys

import range_character_autorig as ar

args = sys.argv[sys.argv.index("--") + 1:]
flags = {a for a in args if a.startswith("--")}
root = None
if "--projeto" in args:
    root = args[args.index("--projeto") + 1]
    args = args[:args.index("--projeto")] + args[args.index("--projeto") + 2:]
pos = [a for a in args if not a.startswith("--")]
obj_path, name, out_dir = pos[0], pos[1], pos[2]
skeleton = pos[3] if len(pos) > 3 else "mixamo_two_fingers"

folders = {sid: folder for sid, _n, folder in ar.list_skeletons()}
if skeleton not in folders:
    raise SystemExit("esqueleto %r nao encontrado; opcoes: %s" % (skeleton, ", ".join(folders)))
info = ar.create_character(obj_path, folders[skeleton], name, out_dir,
                           ragdoll="--sem-ragdoll" not in flags, game_root=root)
print("PERSONAGEM", info)
