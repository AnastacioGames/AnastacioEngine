"""Faz cada tutorial sozinho, passo a passo, no editor invisível, e diz onde ele quebra.

    python tools/tutoriais/revisar_tutoriais.py [nome ...]

Para cada passo: (1) a checagem já é verdadeira antes da ação? (o passo pularia sozinho);
(2) faz a ação de solucoes_tutoriais.py (o que o aluno faria, por bpy); (3) a checagem passa?
Passos de jogo (jogo_rodou) não abrem o jogo: só contam como rodado.
Resultado em artifacts/testes/revisar_tutoriais.json e um resumo na tela.
"""
import json
import os
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
os.environ.setdefault('ANASTACIO_CONTROLE_PASTA', str(RAIZ / 'artifacts/testes/controle_revisar'))
sys.path.insert(0, str(AQUI.parent / 'testes_engine'))
sys.path.insert(0, str(AQUI))
import controle  # noqa: E402
import solucoes_tutoriais  # noqa: E402

PASTA = RAIZ / 'source/release/scripts/tutoriais'
SAIDA = RAIZ / 'artifacts/testes/revisar_tutoriais.json'

# Roda dentro do editor: prepara a cena do tutorial e testa um passo por vez.
AMBIENTE = r'''
import bpy, os, time, json, tempfile
import range_tutorials as rt
C = bpy.context
D = bpy.data

def area(tipo):
    return next(a for a in C.screen.areas if a.type == tipo)

def baixo():
    return min(C.screen.areas, key=lambda a: (a.y, a.x))

def trocar_baixo(tipo, arvore=None):
    a = baixo()
    a.type = tipo
    if arvore:
        a.spaces.active.tree_type = arvore
    return a

def aba(contexto):
    for a in C.screen.areas:
        if a.type == 'PROPERTIES':
            a.spaces.active.context = contexto

def ov(tipo='VIEW_3D', regiao='WINDOW'):
    a = area(tipo) if tipo != 'BAIXO' else baixo()
    r = next(r for r in a.regions if r.type == regiao)
    return {'window': C.window, 'screen': C.screen, 'area': a, 'region': r,
            'space_data': a.spaces.active, 'scene': C.scene, 'object': C.scene.objects.active,
            'active_object': C.scene.objects.active,
            'selected_objects': [o for o in C.scene.objects if o.select],
            'selected_editable_objects': [o for o in C.scene.objects if o.select]}

def sel(nome):
    for o in C.scene.objects:
        o.select = False
    o = C.scene.objects[nome]
    o.select = True
    C.scene.objects.active = o
    return o

def ob():
    return C.scene.objects.active

def shift_c():
    bpy.ops.view3d.view_all(ov(), center=True)

def salvar():
    NOME = os.environ.get('NOME_TUTORIAL', 'x')
    pasta = os.path.join(tempfile.gettempdir(), 'revisar_tutoriais', NOME)
    os.makedirs(pasta, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(pasta, 'teste.range'))

def jogo():
    rt._jogos[0] += 1

def ui_tree():
    return next(a.spaces.active.node_tree for a in C.screen.areas
                if a.type == 'NODE_EDITOR' and a.spaces.active.node_tree is not None)

def no_ativo(tipo, filtro=lambda n: True):
    t = ui_tree()
    for n in t.nodes:
        n.select = False
    n = next(n for n in t.nodes if n.bl_idname == tipo and filtro(n))
    n.select = True
    t.nodes.active = n
    return n
'''

PREPARAR = r'''
NOME = %(nome)r
rt._parar()
cena = os.path.join(rt.PASTA, NOME, rt.CENA)
if os.path.isfile(cena):  # como o tutorial faz: abre uma cópia na pasta temporária
    import shutil
    copia = os.path.join(bpy.app.tempdir, 'tutorial_' + rt.CENA)
    shutil.copyfile(cena, copia)
    bpy.ops.wm.open_mainfile(filepath=copia)
else:
    bpy.ops.wm.read_homefile()
os.environ['NOME_TUTORIAL'] = NOME
resultado = 'ok'
'''

PASSO = r'''
NOME = %(nome)r
roteiro = rt._ler_roteiro(NOME)
passo = roteiro['passos'][%(i)d]
rt.estado.clear()
rt.estado.update(roteiro=roteiro, passo=%(i)d, inicio_passo=time.time() + %(i)d, jogos_inicio=rt._jogos[0])
checar = rt._checagem(passo)
antes = bool(checar(C)) if checar else None
erro = None
try:
    exec(%(acao)r)
except Exception as e:
    import traceback
    erro = traceback.format_exc(limit=2)[-600:]
C.scene.update()  # dimensões e afins só se atualizam depois do depsgraph
depois = bool(checar(C)) if checar else None
rt.estado.clear()
resultado = {'antes': antes, 'depois': depois, 'erro': erro}
'''


def rodar(ed, codigo):
    r = ed.pedir('py', codigo=AMBIENTE + codigo)  # cada pedido roda num espaço novo
    if not r['ok']:
        raise RuntimeError(r.get('traceback') or r.get('erro'))
    return r.get('resultado')


def main():
    nomes = sys.argv[1:] or sorted(p.name for p in PASTA.iterdir() if (p / 'roteiro.json').is_file())
    controle.abrir()
    ed = controle.Editor()
    rodar(ed, AMBIENTE + "\nresultado = 'ok'")
    relatorio = {}
    try:
        for nome in nomes:
            roteiro = json.loads((PASTA / nome / 'roteiro.json').read_text(encoding='utf-8'))
            requer = roteiro.get('requer')
            if requer and not rodar(ed, "resultado = hasattr(bpy.types, %r)" % requer):
                print('%-24s fica escondido: falta %s (addon desligado)' % (nome, requer))
                relatorio[nome] = [{'erro': 'escondido, falta ' + requer}]
                continue
            acoes = solucoes_tutoriais.SOLUCOES.get(nome)
            if acoes is None or len(acoes) != len(roteiro['passos']):
                relatorio[nome] = [{'erro': 'solução com %s passos, roteiro com %d' % (
                    None if acoes is None else len(acoes), len(roteiro['passos']))}]
                print('??', nome, relatorio[nome][0]['erro'])
                continue
            rodar(ed, PREPARAR % {'nome': nome})
            linhas = []
            for i, acao in enumerate(acoes):
                if os.environ.get('REVISAR_VERBOSO'):
                    print('  passo', i, acao[:90], flush=True)
                r = rodar(ed, PASSO % {'nome': nome, 'i': i, 'acao': acao})
                problema = []
                if r['antes']:
                    problema.append('PULA SOZINHO')
                if r['erro']:
                    problema.append('ERRO')
                if r['depois'] is False:
                    problema.append('NAO PASSA')
                r.update(passo=i, problema=problema)
                linhas.append(r)
            relatorio[nome] = linhas
            ruins = [l for l in linhas if l['problema']]
            print('%-24s %2d passos  %s' % (nome, len(linhas), 'ok' if not ruins else
                  '; '.join('%d:%s' % (l['passo'], '/'.join(l['problema'])) for l in ruins)))
    finally:
        SAIDA.parent.mkdir(parents=True, exist_ok=True)
        SAIDA.write_text(json.dumps(relatorio, indent=1, ensure_ascii=False), encoding='utf-8')
        try:
            ed.pedir('fechar')
        except OSError:
            pass  # o editor fecha antes de responder


if __name__ == '__main__':
    main()
