"""Teste 2: editor nativo invisível, escrita pelo caminho da UI Web + desfazer/refazer."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'testes_engine'))
import controle

PREP = '''
import sys
sys.path.insert(0, r"%s")
import importlib, layout_espiao as le
importlib.reload(le)
''' % str(Path(__file__).resolve().parent)

controle.abrir()
ed = controle.Editor()
ok = True


def py(codigo):
    r = ed.pedir('py', codigo=PREP + codigo)
    if not r['ok']:
        raise RuntimeError(r.get('traceback') or r['erro'])
    return r['resultado']


def conferir(nome, obtido, esperado):
    global ok
    bate = json.dumps(obtido) == json.dumps(esperado)
    ok &= bate
    print('OK ' if bate else 'FALHOU', nome, obtido, '' if bate else '(esperado %s)' % esperado)


try:
    rna_loc = {'id_tipo': 'Object', 'id': 'Cube', 'caminho': 'location'}
    py('bpy.ops.ed.undo_push(contexto(), message="inicio")')
    # Escrever como a UI Web faria (vetor inteiro e um componente).
    conferir('escrever location', py('resultado = list(le.escrever(%r, (1.0, 2.0, 3.0)))' % rna_loc), [1.0, 2.0, 3.0])
    py('bpy.ops.ed.undo_push(contexto(), message="Location")')
    conferir('escrever location[2]', py('resultado = list(le.escrever(%r, 5.0, 2))' % rna_loc), [1.0, 2.0, 5.0])
    py('bpy.ops.ed.undo_push(contexto(), message="Location Z")')
    conferir('escrever rotation_mode', py('''resultado = le.escrever({"id_tipo":"Object","id":"Cube","caminho":"rotation_mode"}, "QUATERNION")'''), 'QUATERNION')
    py('bpy.ops.ed.undo_push(contexto(), message="Modo")')
    # Painel reconstruído mostra rotation_quaternion?
    conferir('painel acompanha', py('''
ctx = le.ContextoFalso(object=bpy.data.objects["Cube"], space_data=le.EspacoPropriedades())
js, reg, erro = le.desenhar(bpy.types.OBJECT_PT_transform, ctx)
def t(n):
    yield n
    for f in n.get("itens", []): yield from t(f)
resultado = [n["rna"]["caminho"] for n in t(js) if n["tipo"] == "prop"]'''), ['location', 'rotation_quaternion', 'scale', 'rotation_mode'])
    # Desfazer 2x e refazer 1x.
    py('bpy.ops.ed.undo(contexto())'); py('bpy.ops.ed.undo(contexto())')
    conferir('undo 2x', py('o = bpy.data.objects["Cube"]; resultado = [list(o.location), o.rotation_mode]'), [[1.0, 2.0, 3.0], 'XYZ'])
    py('bpy.ops.ed.redo(contexto())')
    conferir('redo 1x', py('o = bpy.data.objects["Cube"]; resultado = list(o.location)'), [1.0, 2.0, 5.0])
    # Segurança e objeto sumido.
    for nome, codigo, esperado in [
        ('bloco proibido', 'le.escrever({"id_tipo":"Text","id":"x","caminho":"name"}, 1)', 'ValueError'),
        ('prop só leitura', 'le.escrever({"id_tipo":"Object","id":"Cube","caminho":"type"}, "LAMP")', 'ValueError'),
        ('objeto apagado', 'bpy.data.objects.remove(bpy.data.objects["Cube"], do_unlink=True); le.escrever(%r, (0,0,0))' % rna_loc, 'KeyError'),
    ]:
        r = py('try:\n    %s\n    resultado = "passou"\nexcept Exception as e:\n    resultado = type(e).__name__' % codigo)
        conferir(nome, r, esperado)
finally:
    try:
        ed.pedir('fechar')
    except Exception:
        pass
print('TESTE2', 'PASSOU' if ok else 'FALHOU')
