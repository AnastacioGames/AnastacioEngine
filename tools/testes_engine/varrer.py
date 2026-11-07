#!/usr/bin/env python3
"""Roda todos os operadores no editor invisível e guarda o resultado de cada um.

  python tools/testes_engine/varrer.py [--filtro mesh.] [--limite 50]

Crash ou travada marca o operador e reabre o editor. Resultado em
artifacts/testes/varredura/ops.jsonl; rodar de novo continua de onde parou.
Estados: ok, sem_contexto, recusou (erro normal do operador), falha (traceback),
crash, travou, pulado (mexe em disco, rede ou janela).
"""
import argparse, collections, json, re, socket, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import controle

SAIDA = controle.PASTA / 'varredura'
PERIGOSOS = re.compile(
    r'^(wm|file|script|screen|render|cycles|sound|ui|export_\w*|import_\w*|preferences|cloth|buttons)\.|'
    r'save|export|import|open|load|reload|revert|recover|quit|exit|install|uninstall|publish|upload|download|'
    r'build|deploy|package|url|browser|steam|delete_file|remove_file|game_start|standalone|play|record|'
    r'performance|bake|cook|screenshot|render|external|pack|unpack|link|append|console|sysinfo|new_window|fullscreen')
EDITORES = {'node': 'NODE_EDITOR', 'logic': 'LOGIC_EDITOR', 'image': 'IMAGE_EDITOR', 'uv': 'IMAGE_EDITOR',
            'text': 'TEXT_EDITOR', 'graph': 'GRAPH_EDITOR', 'action': 'DOPESHEET_EDITOR', 'nla': 'NLA_EDITOR',
            'sequencer': 'SEQUENCE_EDITOR', 'clip': 'CLIP_EDITOR', 'outliner': 'OUTLINER', 'info': 'INFO',
            'time': 'TIMELINE', 'marker': 'TIMELINE', 'anim': 'TIMELINE'}
MODOS = {'mesh': 'EDIT', 'curve': 'OBJECT', 'sculpt': 'SCULPT', 'paint': 'TEXTURE_PAINT'}
PREPARA = """
for nome in list(bpy.data.objects.keys()):
    pass
o = bpy.data.objects.get('Cube')
sc = bpy.context.scene
if bpy.context.object and bpy.context.object.mode != 'OBJECT':
    bpy.ops.object.mode_set(contexto(), mode='OBJECT')
if o is None or o.name not in sc.objects:
    bpy.ops.mesh.primitive_cube_add(contexto('VIEW_3D'))
    bpy.context.object.name = 'Cube'
    o = bpy.context.object
sc.objects.active = o
o.select = True
resultado = 1
"""


def conecta():
    controle.abrir()
    return controle.Editor()


def encerra(editor):
    if editor:
        subprocess.run(['taskkill', '/T', '/F', '/PID', str(editor.sessao['pid'])], capture_output=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--filtro', default='')
    p.add_argument('--limite', type=int, default=0)
    p.add_argument('--tempo', type=int, default=30, help='segundos por operador')
    a = p.parse_args()
    SAIDA.mkdir(parents=True, exist_ok=True)
    res = SAIDA / 'ops.jsonl'
    feitos = {}
    if res.exists():
        for linha in res.read_text(encoding='utf-8').splitlines():
            r = json.loads(linha)
            feitos[r['op']] = r['estado']
    editor = conecta()
    nomes = [n for n in editor.pedir('listar', tipo='ops', filtro=a.filtro)['resultado'] if n not in feitos]
    if a.limite:
        nomes = nomes[:a.limite]
    saida = res.open('a', encoding='utf-8')

    def grava(op, estado, detalhe=''):
        feitos[op] = estado
        saida.write(json.dumps({'op': op, 'estado': estado, 'detalhe': detalhe[:1600]}) + '\n')
        saida.flush()

    for i, op in enumerate(nomes):
        if PERIGOSOS.search(op):
            grava(op, 'pulado')
            continue
        grupo = op.split('.')[0]
        pedido = {'nome': op, 'editor': EDITORES.get(grupo, 'VIEW_3D')}
        if grupo in MODOS:
            pedido['modo'] = MODOS[grupo]
        try:
            editor.socket.settimeout(a.tempo)
            editor.pedir('py', codigo=PREPARA.replace('contexto()', "contexto('VIEW_3D')"))
            r = editor.pedir('op', **pedido)
            if r['ok']:
                grava(op, 'sem_contexto' if r['resultado']['estado'] == 'sem_contexto' else 'ok')
            else:
                grava(op, 'falha' if 'Traceback' in r.get('erro', '') else 'recusou', r.get('erro', ''))
        except (socket.timeout, TimeoutError):
            grava(op, 'travou')
            encerra(editor)
            editor = conecta()
        except (ConnectionError, OSError) as erro:
            log = (controle.PASTA / 'editor.log').read_text(errors='replace')
            cauda = log[log.find('symbolized'):][:1400]
            grava(op, 'crash', str(erro) + '\n' + cauda)
            time.sleep(1)
            editor = conecta()
        if i % 100 == 0:
            print(i, '/', len(nomes), op, flush=True)
    encerra(editor)
    print(collections.Counter(feitos.values()))


if __name__ == '__main__':
    main()
