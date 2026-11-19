"""Find Next com o cursor no fim do texto (Wrap desligado): continua do começo em vez de falhar."""
from rodar import py

PREP = '''
j = bpy.context.window_manager.windows[0]
a = next(a for a in j.screen.areas if a.type == 'VIEW_3D')
a.type = 'TEXT_EDITOR'
t = bpy.data.texts.new("busca.py")
t.from_string(chr(10).join(["def update(self):", "    self.scene = 1", "    pass", ""]))
s = a.spaces[0]
s.text = t
s.use_find_wrap = False
s.use_find_all = False
s.find_text = "self"
bpy.ops.text.move(contexto('TEXT_EDITOR'), type='FILE_BOTTOM')
r = bpy.ops.text.find(contexto('TEXT_EDITOR'))
resultado = [list(r), t.current_line_index, t.current_character, t.select_end_character]
'''


def testar(t):
    e = t.editor()
    r = py(e, PREP)
    assert r[0] == ['FINISHED'] and r[1] == 0 and r[3] - r[2] == 4, r
    t.nota('achou "self" na linha 1 com o cursor no fim: %r' % r)
