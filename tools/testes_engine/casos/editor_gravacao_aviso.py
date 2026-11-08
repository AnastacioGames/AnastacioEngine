"""Menu Record e aviso de gravação: o selo REC aparece enquanto grava, some ao salvar e o Sound é criado."""
import time

from rodar import py

PREPARA = '''
import aud, types
from bl_operators import anastacio_sound_record as m
real = aud.Microphone
falso = types.SimpleNamespace(**{k: getattr(aud, k) for k in dir(aud) if not k.startswith('__')})
falso.Microphone = lambda device=None, rate=44100, channels=1, seconds=2.0: real(backend='Test', rate=rate, channels=channels, seconds=seconds)
m.aud = falso
m._device_names = lambda: []
m.saved_device = lambda: ''
resultado = hasattr(bpy.types, 'INFO_PT_record')
'''
STATUS = "from bl_operators import anastacio_sound_record as m\nresultado = m.recording_status()"
MEIO = '''
j = bpy.context.window_manager.windows[0]
a = next(a for a in j.screen.areas if a.type == 'VIEW_3D')
resultado = [a.x + a.width // 2, j.height - 1 - (a.y + a.height // 2)]
'''
SONS = "resultado = [s.name for s in bpy.data.sounds]"


def testar(t):
    e = t.editor()
    assert py(e, PREPARA), 'painel INFO_PT_record não registrado'
    assert py(e, STATUS) == '', 'aviso ligado antes de gravar'
    py(e, "bpy.ops.sound.record_microphone(contexto('VIEW_3D'), 'INVOKE_DEFAULT', target='NEW')")
    time.sleep(1.5)
    status = py(e, STATUS)
    assert status.startswith('Recording'), 'aviso não apareceu: %r' % status
    print_rec = t.pasta / 'gravando.png'
    e.pedir('tela', arquivo=str(print_rec), editor='VIEW_3D')
    x, y = py(e, MEIO)
    for valor in ('PRESS', 'RELEASE'):
        assert e.pedir('evento', tipo='ESC', valor=valor, x=x, y=y)['ok']
    time.sleep(1.0)
    assert py(e, STATUS) == '', 'aviso não saiu depois de salvar'
    sons = py(e, SONS)
    assert sons, 'nenhum Sound criado'
    janelas = "resultado = [[a.type for a in w.screen.areas] for w in bpy.context.window_manager.windows]"
    n = len(py(e, janelas))
    py(e, "bpy.ops.sound.open_sequencer_window(contexto('VIEW_3D'))")
    time.sleep(1.0)
    depois = py(e, janelas)
    assert len(depois) == n + 1 and depois[-1] == ['SEQUENCE_EDITOR'], 'janela do Sequencer: %s' % depois
    t.nota('%s; sons %s; print %s' % (status, sons, print_rec))
