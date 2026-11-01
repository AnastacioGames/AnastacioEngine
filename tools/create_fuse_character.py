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

ar.cli_main(sys.argv[sys.argv.index("--") + 1:])
