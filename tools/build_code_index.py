#!/usr/bin/env python3
"""Gera indices mecanicos (sem LLM) por area do engine em docs/local-knowledge/index-<area>.md.

Para cada arquivo .h/.cpp/.c/.cc da area: numero de linhas, classes/structs declarados (headers)
e classes cujos metodos sao implementados (.cpp). Tudo extraido por regex do codigo real, entao
nao alucina - mas tambem nao descreve o "porque". Use para achar rapido onde algo mora.

Uso: python tools/build_code_index.py [area]
"""
import os
import re
import sys
from collections import Counter

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
OUT = os.path.join(ROOT, 'docs', 'local-knowledge')
AREAS = {
    'rendering': ['source/source/gameengine/Rasterizer', 'source/source/blender/gpu'],
    'physics': ['source/source/gameengine/Physics', 'source/source/blender/physics'],
    'logic-scripting': ['source/source/gameengine/GameLogic', 'source/source/gameengine/Expressions',
                        'source/source/blender/python'],
    'scenegraph-converter': ['source/source/gameengine/SceneGraph', 'source/source/gameengine/Converter',
                             'source/source/gameengine/Ketsji'],
    'dna-blend': ['source/source/blender/makesdna', 'source/source/blender/blenloader'],
}
EXT = ('.h', '.hpp', '.cpp', '.cc', '.c')
BIG = 1500
decl = re.compile(r'^\s*(?:template\s*<[^>]*>\s*)?(?:class|struct)\s+(?:[A-Z_]+\s+)*(\w+)\s*(?::|\{|$)')
impl = re.compile(r'^[A-Za-z_][\w:<>\*&\s,]*?\b(\w+)::~?\w+\s*\(')


def scan(path):
    n, names, is_hdr = 0, Counter(), path.endswith(('.h', '.hpp'))
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            n += 1
            if is_hdr:
                m = decl.match(line)
                if m and not line.rstrip().endswith(';'):
                    names[m.group(1)] += 1
            elif not line.startswith((' ', '\t', '#', '/', '*')):
                m = impl.match(line)
                if m:
                    names[m.group(1)] += 1
    return n, [k for k, _ in names.most_common(6)]


def build(area):
    lines = [f'# Indice de codigo: {area}', '',
             '> Gerado por `tools/build_code_index.py` (regex sobre o codigo, sem LLM). '
             'Colunas: linhas | classes declaradas (.h) ou implementadas (.cpp).',
             f'> Arquivos com mais de {BIG} linhas estao marcados com **grande**: nao leia inteiros; '
             'veja `docs/code-map-*.md` quando existir.', '']
    total = 0
    for base in AREAS[area]:
        top = os.path.join(ROOT, base)
        if not os.path.isdir(top):
            continue
        for dirpath, dirs, files in os.walk(top):
            dirs.sort()
            fs = sorted(f for f in files if f.endswith(EXT))
            if not fs:
                continue
            lines += [f'## {os.path.relpath(dirpath, ROOT).replace(os.sep, "/")}', '',
                      '| arquivo | linhas | classes |', '|---|---:|---|']
            for f in fs:
                n, names = scan(os.path.join(dirpath, f))
                flag = ' **grande**' if n > BIG else ''
                cls = ', '.join(f'`{c}`' for c in names)
                lines.append(f'| {f}{flag} | {n} | {cls} |')
                total += 1
            lines.append('')
    with open(os.path.join(OUT, f'index-{area}.md'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(lines))
    print(area, total, 'arquivos')


for a in ([sys.argv[1]] if len(sys.argv) > 1 else AREAS):
    build(a)
