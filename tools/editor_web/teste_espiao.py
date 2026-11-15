"""Testes 1 e 3 do editor na Web, em background.

AnastacioEngine -b --factory-startup --python tools/editor_web/teste_espiao.py -- <pasta_saida>
Gera transform.json (teste 1) e contagem.json (teste 3).
"""
import json, os, sys
from collections import Counter
import bpy

sys.path.insert(0, os.path.dirname(__file__))
import layout_espiao as le

saida = sys.argv[sys.argv.index('--') + 1] if '--' in sys.argv else '.'
os.makedirs(saida, exist_ok=True)

cena = bpy.context.scene
cubo = bpy.data.objects['Cube']
cena.objects.active = cubo


ctx_para = le.contexto_para


# Teste 1: Transform do cubo.
cls = bpy.types.OBJECT_PT_transform
js, reg, erro = le.desenhar(cls, ctx_para(cubo))
with open(os.path.join(saida, 'transform.json'), 'w', encoding='utf-8') as f:
    json.dump({'erro': erro, 'chamadas': reg, 'arvore': js}, f, ensure_ascii=False, indent=1)
print('TESTE1', 'erro=', erro, 'chamadas=', reg)

# Variação: modo de rotação quaternion muda a árvore?
cubo.rotation_mode = 'QUATERNION'
js_q, _, _ = le.desenhar(cls, ctx_para(cubo))
cubo.rotation_mode = 'XYZ'
props = lambda a: [] if a is None else [n.get('rna', {}) and n['rna']['caminho'] for n in _todos(a) if n['tipo'] == 'prop']


def _todos(no):
    yield no
    for f in no.get('itens', []):
        yield from _todos(f)
    if 'cabecalho' in no:
        yield from _todos(no['cabecalho'])


print('TESTE1 props XYZ:', props(js))
print('TESTE1 props QUAT:', props(js_q))

# Teste 3: todos os painéis de Properties com cubo, lâmpada e câmera.
paineis = le.paineis_properties()
objetos = [cubo] + [next(o for o in bpy.data.objects if o.type == t) for t in ('LAMP', 'CAMERA')
                    if any(o.type == t for o in bpy.data.objects)]
resultado = {}
arvores = {}
metodos = Counter()
sem_suporte = Counter()
for c in paineis:  # ordem de registro = ordem no editor
    melhor = None
    for obj in objetos:
        js, reg, erro = le.desenhar(c, ctx_para(obj))
        if erro != 'poll falso':
            melhor = (obj.name, js, reg, erro)
            if erro is None:
                break
    if melhor is None:
        resultado[c.__name__] = {'estado': 'poll falso em todos'}
        continue
    nome_obj, js, reg, erro = melhor
    faltando = sorted(k for k in reg if k not in le.CONTAINERS and k not in le.ITENS)
    for k, n in reg.items():
        metodos[k] += n
    for k in faltando:
        sem_suporte[k] += 1
    if erro:
        estado = 'erro'
    elif faltando:
        estado = 'parcial'
    else:
        estado = 'ok'
    if estado != 'erro':
        arvores[c.__name__] = {'aba': getattr(c, 'bl_context', ''), 'ordem': len(arvores), 'arvore': js}
    resultado[c.__name__] = {'estado': estado, 'obj': nome_obj, 'erro': erro,
                             'sem_suporte': faltando, 'contexto': getattr(c, 'bl_context', '')}

with open(os.path.join(saida, 'paineis.json'), 'w', encoding='utf-8') as f:
    json.dump(arvores, f, ensure_ascii=False)
resumo = Counter(v['estado'] for v in resultado.values())
with open(os.path.join(saida, 'contagem.json'), 'w', encoding='utf-8') as f:
    json.dump({'resumo': resumo, 'sem_suporte_por_painel': sem_suporte.most_common(),
               'metodos': metodos.most_common(), 'paineis': resultado}, f, ensure_ascii=False, indent=1)
print('TESTE3 total', len(paineis), dict(resumo))
print('TESTE3 sem suporte (painéis):', sem_suporte.most_common(15))
for n, v in resultado.items():
    if v['estado'] == 'erro':
        print('ERRO', n, v['erro'])
