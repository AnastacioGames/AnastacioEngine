"""Open in External Editor num texto que só existe dentro do .range: salva sozinho ao lado do
.range e abre; se o nome já existe no disco, pede o Save As e abre depois de salvar.
O open_file do módulo é trocado por um gravador (não abre o VS Code de verdade)."""
import os
import tempfile
import time

from rodar import py

PREPARAR = '''
import text_external_editor as tee
chamadas = []
tee.open_file = lambda caminho, linha=1: chamadas.append((caminho, linha))
bpy.app.driver_namespace['_chamadas_ext'] = chamadas
bpy.ops.wm.save_as_mainfile(filepath=%r, check_existing=False)
j = bpy.context.window_manager.windows[0]
a = next(a for a in j.screen.areas if a.type == 'VIEW_3D')
a.type = 'TEXT_EDITOR'
t = bpy.data.texts.new("LIGA_DESLIGA")
t.from_string("print(1)\\n")
a.spaces[0].text = t
resultado = True
'''

ABRIR = '''
a = next(a for a in bpy.context.window_manager.windows[0].screen.areas if a.type == 'TEXT_EDITOR')
a.spaces[0].text = bpy.data.texts[%r]
r = bpy.ops.text.open_external(contexto('TEXT_EDITOR'), 'INVOKE_DEFAULT')
t = bpy.data.texts[%r]
resultado = [list(r), t.filepath, t.is_in_memory, list(bpy.app.driver_namespace['_chamadas_ext'])]
'''


def testar(t):
    pasta = tempfile.mkdtemp(prefix='ext_', dir='D:\\AnastacioTestes') if os.path.isdir('D:\\AnastacioTestes') \
        else tempfile.mkdtemp(prefix='ext_')
    blend = os.path.join(pasta, 'cena.range')
    e = t.editor()
    py(e, PREPARAR % blend)

    # 1. .range salvo e nome livre: salva <pasta>/LIGA_DESLIGA.py e abre direto
    r = py(e, ABRIR % ('LIGA_DESLIGA', 'LIGA_DESLIGA'))
    esperado = os.path.join(pasta, 'LIGA_DESLIGA.py')
    assert r[0] == ['FINISHED'], r
    assert os.path.normcase(os.path.abspath(r[1])) == os.path.normcase(esperado), r
    assert not r[2] and os.path.isfile(esperado), r
    assert len(r[3]) == 1 and os.path.normcase(r[3][0][0]) == os.path.normcase(esperado), r
    t.nota('salvo e aberto: %s' % r[3][0][0])

    # 2. nome já ocupado no disco: não sobrescreve, abre o Save As e espera
    with open(os.path.join(pasta, 'OUTRO.py'), 'w') as f:
        f.write('# do usuario\n')
    py(e, "bpy.data.texts.new('OUTRO').from_string('x = 2\\n')\nresultado = True")
    r = py(e, ABRIR % ('OUTRO', 'OUTRO'))
    assert r[0] == ['CANCELLED'] and r[2], r
    assert open(os.path.join(pasta, 'OUTRO.py')).read() == '# do usuario\n'
    assert len(r[3]) == 1, r
    # o usuário escolhe outro nome na janela (o "Save As" do operador = exec com o caminho)
    time.sleep(0.5)
    novo = os.path.join(pasta, 'outro_nome.py')
    aberta = py(e, "areas = bpy.context.window_manager.windows[0].screen.areas\n"
                   "resultado = any(a.type == 'FILE_BROWSER' for a in areas)")
    assert aberta, 'janela de salvar nao abriu'
    t.nota('janela de salvar abriu')
    for valor in ('PRESS', 'RELEASE'):  # Esc de verdade fecha a janela
        e.pedir('evento', tipo='ESC', valor=valor, x=200, y=200)
    time.sleep(0.5)
    fechou = py(e, "resultado = not any(a.type == 'FILE_BROWSER' for a in "
                   "bpy.context.window_manager.windows[0].screen.areas)")
    assert fechou, 'janela de salvar nao fechou'
    r = py(e, "r = bpy.ops.text.save_as_open_external(contexto('TEXT_EDITOR'), filepath=%r)\n"
              "resultado = [list(r), list(bpy.app.driver_namespace['_chamadas_ext'])]" % novo)
    c = r[1]
    assert r[0] == ['FINISHED'] and os.path.isfile(novo), r
    assert len(c) == 2 and os.path.normcase(c[1][0]) == os.path.normcase(novo), c
    t.nota('depois do Save As: %s' % c[1][0])
