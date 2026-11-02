"""Regressao do estudio isolado; executar em background com um piloto aberto.

AnastacioEngine.exe -b GroupBia.range --python tools/debug/teste_autorig_retratos.py -- <saida>
Nao salva o piloto. Confere sucesso e limpeza apos falha no processamento do PNG.
"""
import json
import os
import sys

import bpy
import range_character_autorig as generator


def snapshot(arm):
    scene = bpy.context.scene
    return {
        'world': scene.world.as_pointer() if scene.world else None,
        'camera': scene.camera.as_pointer() if scene.camera else None,
        'render': (scene.render.engine, scene.render.filepath, scene.render.resolution_x,
                   scene.render.resolution_y, scene.view_settings.view_transform),
        'pose': [list(row) for p in arm.pose.bones for row in p.matrix_basis],
        'materials': [(m.name, m.alpha, m.ambient, m.specular_intensity, m.use_transparency,
                       [(t.texture.name, t.texture.image.colorspace_settings.name)
                        for t in m.texture_slots if t and t.texture and
                        t.texture.type == 'IMAGE' and t.texture.image]) for m in bpy.data.materials],
        'counts': [len([b for b in getattr(bpy.data, n)
                       if getattr(b, 'type', None) != 'RENDER_RESULT'])
                   for n in ['scenes', 'objects', 'meshes', 'materials', 'textures',
                             'images', 'cameras', 'lamps', 'worlds', 'actions']]}


out = os.path.abspath(sys.argv[sys.argv.index('--')+1])
os.makedirs(out, exist_ok=True)
scene = bpy.context.scene
arm = next(o for o in scene.objects if o.type == 'ARMATURE')
meshes = [o for o in scene.objects if o.name.startswith('BodyGroup')]
assert len(meshes) == 2, 'Esperado corpo LOD0 + parte de primeira pessoa'
before = snapshot(arm)
generator.render_card(arm, meshes, os.path.join(out, 'card.png'),
                      photo_path=os.path.join(out, 'foto.png'))
assert before == snapshot(arm), 'Estado alterado depois do sucesso'
for filename, size in [('card.png', (512, 1024)), ('foto.png', (256, 256))]:
    im = bpy.data.images.load(os.path.join(out, filename), check_existing=False)
    try:
        assert tuple(im.size) == size and im.channels == 4
        alphas = im.pixels[:][3::4]
        assert min(alphas) == 0 and max(alphas) == 1
    finally:
        bpy.data.images.remove(im)


def fail(*args):
    raise RuntimeError('Falha injetada no Lanczos')


original = generator._lanczos_png
generator._lanczos_png = fail
try:
    try:
        generator.render_card(arm, meshes, os.path.join(out, 'falha.png'))
    except RuntimeError as exc:
        assert str(exc) == 'Falha injetada no Lanczos'
    else:
        raise AssertionError('Falha injetada nao ocorreu')
finally:
    generator._lanczos_png = original
assert before == snapshot(arm), 'Estado alterado depois da falha'
with open(os.path.join(out, 'validation.json'), 'w') as f:
    json.dump({'success_preserved': True, 'failure_preserved': True,
               'rgba_sizes_valid': True}, f, indent=2)
print('PORTRAITS_REGRESSION_OK')

