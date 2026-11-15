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
    faltando = sorted(k for k in reg if k not in le.CONTAINERS and k not in le.ITENS and k not in le.TEMPLATES)
    faltando += sorted({n['tipo'] for n in (_todos(js) if js else []) if n.get('sem_suporte') and n['tipo'] in le.TEMPLATES})
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

# Teste 4: templates com dados e escrita de ponteiro/índice.
falhas4 = []


def conf(nome, cond, extra=''):
    print(('OK4 ' if cond else 'FALHOU4 ') + nome, extra)
    if not cond:
        falhas4.append(nome)


js_m, _, _ = le.desenhar(bpy.types.MATERIAL_PT_context_material, ctx_para(cubo))
nos = list(_todos(js_m)) if js_m else []
tl = [n for n in nos if n['tipo'] == 'template_list']
conf('template_list com itens', tl and not tl[0].get('sem_suporte') and tl[0]['itens_lista'], tl[:1])
conf('template_list ativo', tl and tl[0]['ativo']['rna']['caminho'] == 'active_material_index')
tid = [n for n in nos if n['tipo'] == 'template_ID']
conf('template_ID material', tid and tid[0].get('valor') == 'Material' and 'Material' in tid[0]['opcoes'], tid[:1])
mat2 = bpy.data.materials.new('Mat2')
rna_slot = {'id_tipo': 'Object', 'id': 'Cube', 'caminho': 'material_slots[0].material'}
conf('pointer material', le.escrever(rna_slot, 'Mat2') == 'Mat2' and cubo.material_slots[0].material == mat2)
le.escrever(rna_slot, 'Material')
for nome, rna, v in [('pointer inexistente', rna_slot, 'NaoExiste'),
                     ('pointer tipo errado', rna_slot, 3),
                     ('world com material', {'id_tipo': 'Scene', 'id': cena.name, 'caminho': 'world'}, 'Mat2'),
                     ('indice fora', {'id_tipo': 'Object', 'id': 'Cube', 'caminho': 'active_material_index'}, 5),
                     ('indice bool', {'id_tipo': 'Object', 'id': 'Cube', 'caminho': 'active_material_index'}, True)]:
    try:
        le.escrever(rna, v)
        conf(nome + ' recusado', False)
    except (ValueError, KeyError, TypeError):
        conf(nome + ' recusado', True)
conf('indice ok', le.escrever({'id_tipo': 'Object', 'id': 'Cube', 'caminho': 'active_material_index'}, 0) == 0)
if cena.world:
    w2 = bpy.data.worlds.new('W2')
    antigo = cena.world.name
    conf('world da cena', le.escrever({'id_tipo': 'Scene', 'id': cena.name, 'caminho': 'world'}, 'W2') == 'W2')
    le.escrever({'id_tipo': 'Scene', 'id': cena.name, 'caminho': 'world'}, antigo)
# Lista de grupos de vértices: rna do índice ativo e escrita.
for nome_g in ('G1', 'G2'):
    if nome_g not in cubo.vertex_groups:
        cubo.vertex_groups.new(nome_g)
js_v, _, _ = le.desenhar(bpy.types.DATA_PT_vertex_groups, ctx_para(cubo))
tl_v = [n for n in _todos(js_v) if n['tipo'] == 'template_list'] if js_v else []
rna_vg = tl_v and tl_v[0]['ativo']['rna']
conf('vertex groups: rna do ativo', rna_vg == {'id_tipo': 'Object', 'id': 'Cube', 'caminho': 'vertex_groups.active_index'}, rna_vg)
conf('vertex groups: lista com itens', tl_v and [i['nome'] for i in tl_v[0]['itens_lista']][-2:] == ['G1', 'G2'], tl_v[:1])
if rna_vg:
    conf('vertex groups: escreve índice ativo', le.escrever(rna_vg, 0) == 0 and cubo.vertex_groups.active_index == 0)
    try:
        le.escrever(rna_vg, len(cubo.vertex_groups))
        conf('vertex groups: índice fora recusado', False)
    except ValueError:
        conf('vertex groups: índice fora recusado', True)
print('TESTE4', 'falhas=', falhas4)
