# -*- coding: utf-8 -*-
"""Regressão bpy 2.79. Recebe pasta de saída após --; não abre/altera o jogo.

Passos: build/bin/AnastacioEngine.exe -b --factory-startup --python este.py -- pasta
Segunda execução com AUTORIA_RAGDOLL_REOPEN=1 reabre a cena e confere persistência.
AUTORIA_RAGDOLL_UNDO=1 requer editor com janela; encerra após testar Undo/Redo.
"""
import json
import os
import sys
import traceback

import bpy
from mathutils import Matrix

root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, os.path.join(root, 'source', 'release', 'scripts', 'addons'))
import anastacio_ragdoll as addon

dest = os.path.abspath(sys.argv[sys.argv.index('--') + 1])
os.makedirs(dest, exist_ok=True)
mode = ('undo' if os.environ.get('AUTORIA_RAGDOLL_UNDO') else
        'viewport' if os.environ.get('AUTORIA_RAGDOLL_VIEWPORT') else
        'reopen' if os.environ.get('AUTORIA_RAGDOLL_REOPEN') else 'generate')
checks = []
draw_calls = 0
draw_errors = []
original_draw = addon.draw_preview


def measured_draw():
    global draw_calls
    try:
        original_draw()
        draw_calls += 1
    except Exception:
        draw_errors.append(traceback.format_exc())


if mode == 'viewport':
    addon.draw_preview = measured_draw


def check(condition, message):
    assert condition, message
    checks.append(message)


def verify_geometry(rig):
    bpy.context.scene.update()
    parts = addon.descriptors(rig)
    bodies = {obj.anastacio_ragdoll_link.key: obj for obj in addon.owned(rig)
              if obj.anastacio_ragdoll_link.role == 'BODY'}
    check(len(parts) == len(bodies), 'contagem de caixas coincide com descritor')
    folder, unused = addon.ragdoll_folder(bpy.context.scene, rig)
    check(folder is not None, 'rig possui collection própria')
    check(all(bpy.context.scene.object_bases[obj.name].collection == folder
              for obj in addon.owned(rig)), 'corpos e empties ficam na mesma collection')
    for part in parts:
        body = bodies[part['key']]
        actual = [body.matrix_world * vertex.co for vertex in body.data.vertices]
        check(all((a - b).length < 1e-4 for a, b in zip(actual, part['corners'])),
              'vértices gerados coincidem com prévia: ' + part['bone'])
        pivot = next(obj for obj in body.children if obj.anastacio_ragdoll_link.role == 'PIVOT')
        check(max(abs(a - b) for row_a, row_b in zip(pivot.matrix_world, part['pivot'])
                  for a, b in zip(row_a, row_b)) < 1e-4, 'pivô coincide com osso: ' + part['bone'])
        check(body.game.physics_type == 'NO_COLLISION', 'autoria não ativa física sem componente')


def expect_error(fn, message):
    try:
        fn()
    except ValueError:
        checks.append(message)
    else:
        raise AssertionError(message)


def run():
    addon.register()
    scene_path = os.path.join(dest, 'autoria-ragdoll.range')
    if mode in {'reopen', 'undo', 'viewport'}:
        # No modo UI o arquivo vem como argumento do executável. Abrir mainfile
        # dentro do script de startup invalida o contexto de janela dessa chamada.
        if mode == 'reopen':
            bpy.ops.wm.open_mainfile(filepath=scene_path)
        rig = bpy.data.objects['AutoriaRig']
        bpy.context.scene.objects.active = rig
        check(len(rig.anastacio_ragdoll.bones) == 4, 'configuração persistiu')
        check(abs(rig.anastacio_ragdoll.bones[1].width - 0.31) < 1e-5, 'edição por osso persistiu')
        check(len(addon.owned(rig)) == 6, 'propriedade dos objetos persistiu')
        verify_geometry(rig)
        if mode == 'undo':
            bpy.context.user_preferences.edit.use_global_undo = True
            bpy.ops.ed.undo_push(message='Antes de atualizar ragdoll')
            rig.anastacio_ragdoll.bones['Arm'].width = 0.52
            check('FINISHED' in bpy.ops.anastacio.ragdoll_generate(), 'operador atualizar executou')
            bpy.ops.ed.undo_push(message='Depois de atualizar ragdoll')
            bpy.ops.ed.undo()
            rig = bpy.data.objects['AutoriaRig']
            check(abs(rig.anastacio_ragdoll.bones['Arm'].width - 0.31) < 1e-5,
                  'Undo da geração restaura ajuste por osso')
            verify_geometry(rig)
            bpy.ops.ed.redo()
            rig = bpy.data.objects['AutoriaRig']
            check(abs(rig.anastacio_ragdoll.bones['Arm'].width - 0.52) < 1e-5,
                  'Redo da geração restaura novo ajuste')
            verify_geometry(rig)
            bpy.ops.ed.undo_push(message='Antes de remover ragdoll')
            check('FINISHED' in bpy.ops.anastacio.ragdoll_remove(), 'operador remover executou')
            check(len(addon.owned(rig)) == 0, 'remoção limpa objetos')
            check(addon.ragdoll_folder(bpy.context.scene, rig)[0] is None,
                  'remoção limpa collection vazia')
            bpy.ops.ed.undo_push(message='Depois de remover ragdoll')
            bpy.ops.ed.undo()
            rig = bpy.data.objects['AutoriaRig']  # Undo invalida referências RNA anteriores.
            check(len(addon.owned(rig)) == 6, 'Undo restaura corpos e vínculos')
            verify_geometry(rig)
            bpy.ops.ed.redo()
            rig = bpy.data.objects['AutoriaRig']
            check(len(addon.owned(rig)) == 0, 'Redo remove somente corpos próprios')
            check(addon.ragdoll_folder(bpy.context.scene, rig)[0] is None,
                  'Redo remove collection vazia')
            check(bpy.data.objects.get('UserHelper') is not None, 'Undo/Redo preserva objeto do usuário')
        return

    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_GAME'
    parent_folder = scene.collections.new('Personagens')
    bpy.ops.object.armature_add(location=(2, 3, 1))
    rig = bpy.context.object
    rig.name = 'AutoriaRig'
    scene.object_bases[rig.name].collection = parent_folder
    bpy.ops.object.mode_set(mode='EDIT')
    root_bone = rig.data.edit_bones[0]
    root_bone.name = 'Root'
    for name, head, tail, parent in [
            ('Arm', (0, 0, 1), (1, 0.5, 2), 'Root'),
            ('Hand', (1, 0.5, 2), (1.4, 0.5, 2.4), 'Arm'),
            ('Control', (0, 0, 0), (0, 1, 0), None)]:
        bone = rig.data.edit_bones.new(name)
        bone.head, bone.tail = head, tail
        if parent:
            bone.parent = rig.data.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    rig.data.bones['Control'].use_deform = False
    rig.scale = (1.7, 1.7, 1.7)
    rig.rotation_euler = (0.1, 0.2, 0.3)
    scene.update()
    before = len(bpy.data.objects)
    addon.sync_bones(rig)
    for bone in rig.data.bones:
        bone.select = False
    check(addon.ANASTACIO_PT_ragdoll.poll(bpy.context),
          'painel disponível com armature em Object Mode sem osso selecionado')
    check(len(rig.anastacio_ragdoll.bones) == 4, 'lista inclui quatro ossos')
    check(not rig.anastacio_ragdoll.bones['Control'].enabled, 'controle excluído por padrão')
    check(len(addon.descriptors(rig)) == 3 and len(bpy.data.objects) == before,
          'prévia não cria objetos')
    item = rig.anastacio_ragdoll.bones['Arm']
    item.width, item.depth, item.length_ratio = 0.31, 0.19, 0.65
    item.offset, item.rotation = (0.03, 0.1, -0.02), (0.1, 0.2, 0.3)
    helper = bpy.data.objects.new('UserHelper', None)
    scene.objects.link(helper)
    user_constraint = rig.pose.bones['Root'].constraints.new('COPY_LOCATION')
    user_constraint.name, user_constraint.target, user_constraint.influence = 'UserConstraint', helper, 0.37
    check(addon.generate(bpy.context, rig) == 3, 'primeira geração')
    folder, unused = addon.ragdoll_folder(scene, rig)
    folder_uid = folder.uid
    check(any(child.uid == folder_uid for child in parent_folder.children),
          'collection nasce dentro da pasta da armature')
    folder.name = 'Minha pasta de física'
    bpy.context.scene.objects.active = next(obj for obj in addon.owned(rig)
                                            if obj.type == 'MESH')
    check(addon.ANASTACIO_PT_ragdoll.poll(bpy.context) and addon.context_rig(bpy.context) == rig,
          'seleção de corpo mantém painel ligado à armature')
    bpy.context.scene.objects.active = next(obj for obj in addon.owned(rig)
                                            if obj.type == 'EMPTY')
    check(addon.ANASTACIO_PT_ragdoll.poll(bpy.context) and addon.context_rig(bpy.context) == rig,
          'seleção de empty mantém painel ligado à armature')
    bpy.context.scene.objects.active = rig
    verify_geometry(rig)
    count = len(bpy.data.objects)
    check(addon.generate(bpy.context, rig) == 3 and len(bpy.data.objects) == count,
          'segunda geração não duplica objetos')
    check(addon.ragdoll_folder(scene, rig)[0].uid == folder_uid,
          'atualização reutiliza collection mesmo renomeada')
    check(abs(user_constraint.influence - 0.37) < 1e-5 and user_constraint.target == helper,
          'constraint do usuário preservada')
    old = set(addon.owned(rig))
    # Falha no meio do staging precisa deixar os objetos anteriores intactos.
    class FailingObjects:
        calls = 0
        def link(self, obj):
            self.calls += 1
            if self.calls == 3:
                raise RuntimeError('falha injetada de link')
            scene.objects.link(obj)
    class FailingScene:
        objects = FailingObjects()
        def __getattr__(self, name):
            return getattr(scene, name)
    class FailingContext:
        scene = FailingScene()
    try:
        addon.generate(FailingContext(), rig)
    except RuntimeError:
        pass
    else:
        raise AssertionError('falha injetada não ocorreu')
    check(set(addon.owned(rig)) == old and len(bpy.data.objects) == count,
          'rollback preserva geração anterior e remove staging parcial')
    foreign = helper.constraints.new('COPY_LOCATION')
    foreign.target = next(iter(old))
    expect_error(lambda: addon.generate(bpy.context, rig), 'atualização recusa referência externa')
    helper.constraints.remove(foreign)
    child = bpy.data.objects.new('UserChild', None)
    scene.objects.link(child)
    child.parent = next(iter(old))
    expect_error(lambda: addon.preflight(rig), 'remoção recusa filho do usuário')
    bpy.data.objects.remove(child, do_unlink=True)
    for obj in old:
        obj.name = 'RenamedManagedObject'
    addon.generate(bpy.context, rig)
    check(len(addon.owned(rig)) == 6, 'renomear corpos não perde propriedade')
    rig.scale = (1, 2, 1)
    scene.update()
    expect_error(lambda: addon.generate(bpy.context, rig), 'escala não uniforme recusada sem alterar corpos')
    rig.scale = (-1, 1, 1)
    scene.update()
    expect_error(lambda: addon.descriptors(rig), 'espelhamento recusado explicitamente')
    rig.scale = (1.7, 1.7, 1.7)
    scene.update()
    # Rig duplicado não pode apagar nem reutilizar corpos do original.
    clone = rig.copy()
    clone.data = rig.data.copy()
    scene.objects.link(clone)
    expect_error(lambda: addon.generate(bpy.context, clone), 'cópia com vínculos antigos recusada')
    for bone in clone.pose.bones:
        for c in list(bone.constraints):
            if c.name.startswith('Anastacio Ragdoll '):
                bone.constraints.remove(c)
    folder_count = len(addon.scene_folders(scene))
    class FailingBases:
        def get(self, name):
            return scene.object_bases.get(name)
        def __getitem__(self, name):
            raise RuntimeError('falha injetada ao organizar collection')
    class FailingFolderScene:
        object_bases = FailingBases()
        def __getattr__(self, name):
            return getattr(scene, name)
    class FailingFolderContext:
        scene = FailingFolderScene()
    try:
        addon.generate(FailingFolderContext(), clone)
    except RuntimeError:
        pass
    else:
        raise AssertionError('falha de collection não ocorreu')
    check(not addon.owned(clone) and addon.ragdoll_folder(scene, clone)[0] is None
          and len(addon.scene_folders(scene)) == folder_count,
          'rollback remove collection recém-criada e corpos incompletos')
    addon.generate(bpy.context, clone)
    check(len(addon.owned(clone)) == 6 and len(addon.owned(rig)) == 6, 'dois rigs têm propriedade independente')
    clone_folder, unused = addon.ragdoll_folder(scene, clone)
    check(clone_folder.uid != folder_uid, 'rig duplicado ganha collection independente')
    scene.object_bases[helper.name].collection = clone_folder
    addon.remove_generated(clone, addon.preflight(clone))
    check(scene.object_bases[helper.name].collection == clone_folder,
          'remover preserva pasta com conteúdo do usuário')
    scene.object_bases[helper.name].collection = None
    addon.cleanup_folders(clone)
    check(addon.ragdoll_folder(scene, clone)[0] is None, 'pasta vazia pode ser limpa depois')
    bpy.data.objects.remove(clone, do_unlink=True)
    # A constraint ativa testou preservação acima. O exemplo visual não deve desviar a pose.
    user_constraint.mute = True
    rig.anastacio_ragdoll.preview = True
    bpy.context.scene.objects.active = rig
    rig.select = True
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            area.spaces.active.region_3d.view_location = rig.location
            area.spaces.active.region_3d.view_distance = 8
            area.spaces.active.region_3d.view_perspective = 'PERSP'
        elif area.type == 'PROPERTIES':
            area.spaces.active.context = 'PHYSICS'
    verify_geometry(rig)
    bpy.ops.wm.save_as_mainfile(filepath=scene_path)


def finish(error=None):
    result = {'ok': error is None, 'mode': mode, 'checks': checks}
    if error:
        result['error'] = error
    if mode == 'viewport':
        result.update(draw_calls=draw_calls, draw_errors=draw_errors)
    with open(os.path.join(dest, mode + '-result.json'), 'w', encoding='utf-8') as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=True))
    if not bpy.app.background:
        # Só nesta sessão de teste; não salva preferências globais do usuário.
        bpy.context.user_preferences.view.use_quit_dialog = False
        bpy.ops.wm.quit_blender()


class ANASTACIO_OT_autoria_viewport_test(bpy.types.Operator):
    bl_idname = 'anastacio.autoria_viewport_test'
    bl_label = 'Teste de desenho da autoria'
    ticks = 0

    def execute(self, context):
        self.timer = context.window_manager.event_timer_add(0.4, context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type != 'TIMER':
            return {'PASS_THROUGH'}
        self.ticks += 1
        if self.ticks < 5:
            addon.redraw()
            return {'PASS_THROUGH'}
        context.window_manager.event_timer_remove(self.timer)
        try:
            check(draw_calls > 0, 'callback POST_VIEW executou no editor')
            check(not draw_errors, 'desenho GL sem exceções')
        except Exception:
            finish(traceback.format_exc())
        else:
            addon.unregister()
            finish()
        return {'FINISHED'}


try:
    run()
except Exception:
    finish(traceback.format_exc())
else:
    if mode == 'viewport':
        bpy.utils.register_class(ANASTACIO_OT_autoria_viewport_test)
        bpy.ops.anastacio.autoria_viewport_test()
    else:
        finish()
