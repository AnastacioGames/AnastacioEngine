"""Add > Force Field no modo Game: so os 4 tipos que o jogo simula, e o objeto ja nasce com o campo ligado no jogo."""
from rodar import py

CENA = '''
sc = bpy.context.scene
sc.render.engine = 'BLENDER_GAME'
res = []
for tipo in ('FORCE', 'WIND', 'VORTEX', 'TURBULENCE'):
    bpy.ops.object.effector_add(type=tipo)
    o = bpy.context.object
    res.append((tipo, o.field.type, o.field.use_game_field))
sc.render.engine = 'BLENDER_RENDER'
bpy.ops.object.effector_add(type='WIND')
res.append(('RENDER', bpy.context.object.field.type, bpy.context.object.field.use_game_field))
assert hasattr(bpy.types, 'INFO_MT_game_force_field_add')
assert [r[2] for r in res] == [True, True, True, True, False], res
'''


def testar(t):
    t.gerar(CENA)
