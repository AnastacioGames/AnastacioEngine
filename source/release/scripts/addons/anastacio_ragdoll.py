# -*- coding: utf-8 -*-
"""Autoria de corpos e articulações com componente comum distribuído pela engine."""
import math
import uuid

import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty,
                       FloatVectorProperty, IntProperty, PointerProperty, StringProperty)
from mathutils import Euler, Matrix, Vector

bl_info = {
    'name': 'Anastacio Ragdoll', 'author': 'Anastacio Games',
    'version': (0, 3, 0), 'blender': (2, 79, 0),
    'location': 'Properties > Physics > Anastacio Ragdoll',
    'description': 'Prévia e autoria por osso de corpos de ragdoll',
    'category': 'Game Engine',
}

_handle = None
_MODULE = 'anastacio_ragdoll_runtime'
_COMPONENT = 'AnastacioRagdoll'
_PRESETS = {
    'HARD': ((15, 10, 15), 0.15, 0.8),
    'BALANCED': ((45, 25, 45), 0.08, 0.45),
    'LIGHT': ((80, 50, 80), 0.03, 0.15),
}
_CORNERS = [(x, y, z) for x in (-0.5, 0.5)
            for y in (-0.5, 0.5) for z in (-0.5, 0.5)]
_EDGES = [(i, j) for i in range(8) for j in range(i + 1, 8)
          if sum(a != b for a, b in zip(_CORNERS[i], _CORNERS[j])) == 1]
_FACES = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1),
          (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]


def redraw(self=None, context=None):
    wm = bpy.context.window_manager
    if wm:
        for window in wm.windows:
            for area in window.screen.areas:
                if area.type in {'VIEW_3D', 'PROPERTIES'}:
                    area.tag_redraw()


def context_rig(context):
    obj = getattr(context, 'object', None)
    if obj is None:
        return None
    if obj.type == 'ARMATURE':
        return obj
    # Selecionar um corpo/empty também mantém a configuração do seu rig acessível.
    rig = obj.anastacio_ragdoll_link.rig
    return rig if rig and rig.type == 'ARMATURE' else None


class AnastacioRagdollBone(bpy.types.PropertyGroup):
    # A chave sobrevive à renomeação do objeto gerado. O nome do osso é validado.
    key = StringProperty()
    enabled = BoolProperty(name='Incluir', default=True, update=redraw)
    width = FloatProperty(name='Largura X', default=0.08, min=0.001, update=redraw)
    depth = FloatProperty(name='Profundidade Z', default=0.08, min=0.001, update=redraw)
    length_ratio = FloatProperty(name='Comprimento / osso', default=0.8,
                                 min=0.01, max=3.0, update=redraw)
    offset = FloatVectorProperty(name='Deslocamento local', subtype='TRANSLATION', update=redraw)
    rotation = FloatVectorProperty(name='Rotação local', subtype='EULER', update=redraw)
    mass_weight = FloatProperty(name='Peso relativo de massa', default=1.0, min=0.01)
    joint_limits = FloatVectorProperty(name='Limites da articulação XYZ', subtype='EULER',
                                      default=tuple(math.radians(v) for v in (45, 25, 45)),
                                      min=0.01, max=math.pi)
    linear_damping = FloatProperty(name='Amortecimento linear', default=0.08, min=0, max=1)
    angular_damping = FloatProperty(name='Amortecimento angular', default=0.45, min=0, max=1)


class AnastacioRagdollSettings(bpy.types.PropertyGroup):
    schema_version = IntProperty(default=1)
    bones = CollectionProperty(type=AnastacioRagdollBone)
    index = IntProperty(default=0, min=0, update=redraw)
    preview = BoolProperty(name='Mostrar prévia', default=False, update=redraw)
    preset = EnumProperty(name='Comportamento', items=[('HARD', 'Duro', 'Juntas restritas e amortecimento alto'),
                          ('BALANCED', 'Equilibrado', 'Flexibilidade intermediária'),
                          ('LIGHT', 'Leve', 'Juntas amplas e amortecimento baixo')], default='BALANCED')
    total_mass = FloatProperty(name='Massa total', default=70.0, min=0.1)
    recovery_mode = EnumProperty(name='Recuperação', items=[('FREE', 'Livre / NPC', 'Retorna ao chão'),
                                      ('ANCHOR', 'Âncora / veículo', 'Retorna à âncora')])
    auto_recover = BoolProperty(name='Recuperar automaticamente', default=True)
    recovery_delay = FloatProperty(name='Tempo para recuperar', default=3.0, min=0, subtype='TIME')
    anchor = PointerProperty(name='Âncora', type=bpy.types.Object)
    controller = PointerProperty(name='Colisor / controlador', type=bpy.types.Object)
    velocity_source = PointerProperty(name='Fonte de velocidade', type=bpy.types.Object)
    linear_inheritance = FloatProperty(name='Herança linear', default=1.0, min=0, max=3)
    angular_inheritance = FloatProperty(name='Herança angular', default=1.0, min=0, max=3)


class AnastacioRagdollLink(bpy.types.PropertyGroup):
    rig = PointerProperty(type=bpy.types.Object)
    key = StringProperty()
    role = StringProperty()


class AnastacioRagdollFolder(bpy.types.PropertyGroup):
    # Collections pertencem à cena: UID sozinho não identifica pasta de outra cena.
    rig = PointerProperty(type=bpy.types.Object)
    uid = IntProperty()


def scene_folders(scene):
    def walk(items):
        for folder in items:
            yield folder
            for child in walk(folder.children):
                yield child
    return {folder.uid: folder for folder in walk(scene.collections)}


def ragdoll_folder(scene, rig, create=False):
    folders = scene_folders(scene)
    for record in scene.anastacio_ragdoll_folders:
        if record.rig == rig and record.uid in folders:
            return folders[record.uid], False
    if not create:
        return None, False
    base = scene.object_bases.get(rig.name)
    folder = scene.collections.new('Ragdoll - ' + rig.name,
                                   parent=base.collection if base else None)
    try:
        record = scene.anastacio_ragdoll_folders.add()
        record.rig, record.uid = rig, folder.uid
    except Exception:
        scene.collections.remove(folder)
        raise
    return folder, True


def cleanup_folders(rig):
    for scene in bpy.data.scenes:
        folders = scene_folders(scene)
        records = scene.anastacio_ragdoll_folders
        for index in range(len(records) - 1, -1, -1):
            record = records[index]
            if record.rig != rig:
                continue
            folder = folders.get(record.uid)
            if folder is not None:
                # Pasta renomeada continua identificada. Conteúdo alheio é preservado.
                if len(folder.children) or any(base.collection == folder
                                               for base in scene.object_bases):
                    continue
                scene.collections.remove(folder)
            records.remove(index)


def sync_bones(rig):
    """Não apaga configuração de ossos ausentes; nunca usa nome para possuir objetos."""
    settings = rig.anastacio_ragdoll
    known = {item.name for item in settings.bones}
    for bone in rig.data.bones:
        if bone.name not in known:
            item = settings.bones.add()
            item.name = bone.name
            item.key = uuid.uuid4().hex
            item.enabled = bone.use_deform and bone.length > 1e-5
            item.width = item.depth = max(0.001, bone.length * 0.25)


def apply_preset(rig):
    limits, linear, angular = _PRESETS[rig.anastacio_ragdoll.preset]
    for item in rig.anastacio_ragdoll.bones:
        if item.enabled:
            item.joint_limits = tuple(math.radians(v) for v in limits)
            item.linear_damping, item.angular_damping = linear, angular


def runtime_component(rig):
    return next((component for component in rig.game.components
                 if component.module == _MODULE and component.name == _COMPONENT), None)


def runtime_config(rig, scene=None):
    scene = scene or bpy.context.scene
    settings = rig.anastacio_ragdoll
    if rig.data.pose_position != 'POSE':
        raise ValueError('Selecione Pose Position no painel antes de preparar execução; os cubos continuam em repouso.')
    target = settings.anchor if settings.recovery_mode == 'ANCHOR' else settings.controller
    target = target or rig.parent
    if target is None or target == rig or target not in list(scene.objects):
        raise ValueError('Configure uma âncora/controlador externo nesta cena antes de preparar execução.')
    scale = target.matrix_world.to_scale()
    if (target.matrix_world.determinant() <= 0 or min(scale) <= 1e-6
            or max(scale) - min(scale) > max(scale) * 1e-4):
        raise ValueError('Aplique a escala não uniforme/negativa da âncora ou controlador e seus pais.')
    axes = [target.matrix_world.col[i].to_3d().normalized() for i in range(3)]
    if any(abs(axes[i].dot(axes[j])) > 1e-4 for i in range(3) for j in range(i + 1, 3)):
        raise ValueError('Remova o cisalhamento da âncora/controlador.')
    ancestor = target
    while ancestor:
        if ancestor == rig:
            raise ValueError('Âncora/controlador não pode ser descendente da armature.')
        ancestor = ancestor.parent
    if settings.recovery_mode == 'FREE':
        if target.parent or target.game.physics_type not in {'RIGID_BODY', 'DYNAMIC'}:
            raise ValueError('Modo livre inicial exige Rigid Body/Dynamic separado, na raiz da cena.')
        if (not target.game.use_collision_bounds or target.game.collision_bounds_type != 'BOX'
                or target.game.use_ghost):
            raise ValueError('Modo livre inicial exige colisor sólido com bounds BOX.')
        if rig.parent and rig.parent != target:
            raise ValueError('Armature deve estar vinculada ao controlador selecionado.')
    if rig.game.physics_type != 'NO_COLLISION':
        raise ValueError('A armature deve usar No Collision; a física fica nos corpos/controlador.')
    return {'Recovery Mode': settings.recovery_mode, 'Auto Recover': settings.auto_recover,
            'Recovery Delay': settings.recovery_delay,
            'Anchor': target.name if settings.recovery_mode == 'ANCHOR' else '',
            'Controller': target.name if settings.recovery_mode == 'FREE' else '',
            'Velocity Source': settings.velocity_source.name if settings.velocity_source else '',
            'Linear Inheritance': settings.linear_inheritance, 'Angular Inheritance': settings.angular_inheritance}


def _override(context, rig):
    override = bpy.context.copy()
    override.update(object=rig, active_object=rig, scene=context.scene,
                    selected_objects=[rig], selected_editable_objects=[rig])
    return override


def game_property(context, obj, name, value):
    kind = 'STRING' if isinstance(value, str) else 'INT'
    if name not in obj.game.properties:
        bpy.ops.object.game_property_new(_override(context, obj), type=kind, name=name)
    obj.game.properties[name].value = value


def prepare_physics(context, rig, created, parts):
    settings = rig.anastacio_ragdoll
    bodies = {obj.anastacio_ragdoll_link.key: obj for obj in created
              if obj.anastacio_ragdoll_link.role == 'BODY'}
    by_bone = {part['bone']: bodies[part['key']] for part in parts}
    weights = {part['key']: (settings.bones[part['bone']].mass_weight
                            * settings.bones[part['bone']].width
                            * settings.bones[part['bone']].depth
                            * rig.data.bones[part['bone']].length
                            * settings.bones[part['bone']].length_ratio) for part in parts}
    weight_sum = sum(weights.values())
    for obj in created:
        link = obj.anastacio_ragdoll_link
        game_property(context, obj, 'ar_role', link.role)
        game_property(context, obj, 'ar_key', link.key)
    for part in parts:
        body = bodies[part['key']]
        item = settings.bones[part['bone']]
        body.game.physics_type = 'RIGID_BODY'
        body.game.mass = max(0.001, settings.total_mass * weights[part['key']] / weight_sum)
        body.game.damping, body.game.rotation_damping = item.linear_damping, item.angular_damping
        body.game.collision_group = tuple(i == 15 for i in range(16))
        # Colide com cenário/personagens, sem auto-colisão entre ragdolls nesta versão.
        body.game.collision_mask = tuple(i != 15 for i in range(16))
        body.game.collision_margin = 0.005
        pivot = next(obj for obj in body.children if obj.anastacio_ragdoll_link.role == 'PIVOT')
        game_property(context, pivot, 'ar_bone', part['bone'])
        pose_constraints = rig.pose.bones[part['bone']].constraints
        constraint = next(c for c in pose_constraints if c.target == pivot and c.type == 'COPY_TRANSFORMS')
        game_property(context, pivot, 'ar_constraint', constraint.name)
        parent = rig.data.bones[part['bone']].parent
        while parent and parent.name not in by_bone:
            parent = parent.parent
        if parent is None:
            continue
        joint = body.constraints.new('RIGID_BODY_JOINT')
        joint.name = 'Anastacio Joint ' + part['key']
        joint.target = by_bone[parent.name]
        joint.pivot_type = 'CONE_TWIST'
        position = part['matrix'].inverted() * part['pivot'].translation
        joint.pivot_x, joint.pivot_y, joint.pivot_z = position
        axes = (part['matrix'].to_quaternion().inverted()
                * part['pivot'].to_quaternion()).to_euler()
        joint.axis_x, joint.axis_y, joint.axis_z = axes
        joint.use_linked_collision = True  # RNA: Disable Linked Collision.
        for axis, limit in zip('xyz', item.joint_limits):
            setattr(joint, 'use_angular_limit_' + axis, True)
            setattr(joint, 'limit_angle_min_' + axis, -limit)
            setattr(joint, 'limit_angle_max_' + axis, limit)


def descriptors(rig):
    """Única fonte de geometria: repouso, em unidades locais da armature.

    Bone X/Z definem espessura, Y comprimento; deslocamento/rotação são locais
    ao osso. Escala mundial uniforme é incorporada nas dimensões finais.
    """
    scale = rig.matrix_world.to_scale()
    if rig.matrix_world.determinant() <= 0 or min(scale) <= 1e-8:
        raise ValueError('Aplique o espelhamento/escala negativa antes de gerar.')
    if max(scale) - min(scale) > max(scale) * 1e-4:
        raise ValueError('Aplique a escala não uniforme da armature e dos pais.')
    normalized = [rig.matrix_world.col[i].to_3d().normalized() for i in range(3)]
    if any(abs(normalized[i].dot(normalized[j])) > 1e-4
           for i in range(3) for j in range(i + 1, 3)):
        raise ValueError('Remova o cisalhamento da hierarquia antes de gerar.')
    result = []
    keys = set()
    for item in rig.anastacio_ragdoll.bones:
        if not item.enabled:
            continue
        bone = rig.data.bones.get(item.name)
        if bone is None:
            raise ValueError('Osso ausente/renomeado: ' + item.name + '. Desmarque ou ressincronize a entrada.')
        if bone.length <= 1e-5:
            raise ValueError('Osso sem comprimento: ' + bone.name)
        if not item.key or item.key in keys:
            raise ValueError('Identidade de osso inválida: ' + bone.name)
        keys.add(item.key)
        offset = Vector(item.offset) + Vector((0, bone.length * 0.5, 0))
        frame = (rig.matrix_world * bone.matrix_local * Matrix.Translation(offset)
                 * Euler(item.rotation).to_matrix().to_4x4())
        dimensions = Vector((item.width, bone.length * item.length_ratio, item.depth))
        corners = [frame * Vector(tuple(v * d for v, d in zip(corner, dimensions)))
                   for corner in _CORNERS]
        body_frame = frame.to_quaternion().to_matrix().to_4x4()
        body_frame.translation = frame.translation
        result.append({'key': item.key, 'bone': bone.name, 'matrix': body_frame,
                       'corners': corners,
                       'pivot': rig.matrix_world * bone.matrix_local})
    return result


def owned(rig):
    return [obj for obj in bpy.data.objects if obj.anastacio_ragdoll_link.rig == rig]


def own_constraint(constraint, rig, objects):
    return (constraint.type == 'COPY_TRANSFORMS' and constraint.target in objects
            and constraint.target.anastacio_ragdoll_link.role == 'PIVOT')


def preflight(rig):
    old = owned(rig)
    old_set = set(old)
    if rig.library or rig.data.library:
        raise ValueError('Use uma armature local e editável.')
    # Nunca apaga filhos, modificadores ou referências de constraints do usuário.
    for obj in old:
        if obj.library or any(child not in old_set for child in obj.children):
            raise ValueError('Corpo possui vínculo externo/filho do usuário: ' + obj.name)
    for obj in bpy.data.objects:
        if obj in old_set:
            continue
        if obj.parent in old_set:
            raise ValueError('Objeto do usuário depende do ragdoll: ' + obj.name)
        constraints = list(obj.constraints)
        if obj.type == 'ARMATURE':
            for bone in obj.pose.bones:
                for c in bone.constraints:
                    if obj == rig and own_constraint(c, rig, old_set):
                        if c.influence != 0:
                            raise ValueError('Desative as constraints do ragdoll antes de editar.')
                        continue
                    constraints.append(c)
        if any(getattr(c, 'target', None) in old_set for c in constraints):
            raise ValueError('Constraint do usuário depende do ragdoll: ' + obj.name)
        if any(getattr(mod, 'object', None) in old_set for mod in obj.modifiers):
            raise ValueError('Modificador do usuário depende do ragdoll: ' + obj.name)
    # Não migra um Easy Ragdoll existente silenciosamente.
    for bone in rig.pose.bones:
        for c in bone.constraints:
            if (c.name.startswith('Anastacio Ragdoll ') and c.target
                    and c.target.anastacio_ragdoll_link.rig != rig):
                raise ValueError('Rig duplicado com vínculos do original. Remova os vínculos copiados antes de gerar.')
            if (c.type == 'COPY_TRANSFORMS' and c.target and c.target.parent
                    and c.target.parent.name.startswith('RagdollPart-')
                    and c.target not in old_set):
                raise ValueError('Este rig já usa Easy Ragdoll. Use uma cópia limpa para a nova autoria.')
    return old


def _discard(objects):
    meshes = []
    for obj in objects:
        if obj.type == 'MESH':
            meshes.append(obj.data)
        bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in meshes:
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)


def remove_generated(rig, objects, cleanup=True):
    for bone in rig.pose.bones:
        for c in list(bone.constraints):
            if own_constraint(c, rig, objects):
                bone.constraints.remove(c)
    _discard(objects)
    if cleanup:
        cleanup_folders(rig)


def generate(context, rig, runtime=None):
    """Constrói em staging; falhas antes do commit preservam a geração anterior."""
    old = preflight(rig)
    component = runtime_component(rig)
    runtime = component is not None if runtime is None else runtime
    config = runtime_config(rig, context.scene) if runtime else None
    parts = descriptors(rig)
    if not parts:
        raise ValueError('Inclua ao menos um osso.')
    created, constraints = [], []
    folder_created = False
    component_created = False
    try:
        for part in parts:
            mesh = bpy.data.meshes.new('AnastacioRagdollBox')
            body = bpy.data.objects.new('AnastacioRagdoll-' + part['bone'], mesh)
            created.append(body)
            local = [part['matrix'].inverted() * p for p in part['corners']]
            mesh.from_pydata(local, [], _FACES)
            mesh.update()
            context.scene.objects.link(body)
            body.matrix_world = part['matrix']
            body.draw_type = 'WIRE'
            body.show_wire = True
            body.hide_render = True
            # Esta etapa entrega autoria, sem corpos soltos caindo ao dar Play.
            # O núcleo comum configurará Bullet e anexará o componente na próxima etapa.
            body.game.physics_type = 'NO_COLLISION'
            body.game.use_collision_bounds = True
            body.game.collision_bounds_type = 'BOX'
            pivot = bpy.data.objects.new('AnastacioRagdollPivot-' + part['bone'], None)
            created.append(pivot)
            context.scene.objects.link(pivot)
            pivot.empty_draw_size = 0.04
            pivot.hide_render = True
            pivot.game.physics_type = 'NO_COLLISION'
            pivot.parent = body
            pivot.matrix_parent_inverse = Matrix.Identity(4)
            pivot.matrix_basis = part['matrix'].inverted() * part['pivot']
            for obj, role in ((body, 'BODY'), (pivot, 'PIVOT')):
                obj.anastacio_ragdoll_link.rig = rig
                obj.anastacio_ragdoll_link.key = part['key']
                obj.anastacio_ragdoll_link.role = role
            c = rig.pose.bones[part['bone']].constraints.new('COPY_TRANSFORMS')
            constraints.append((rig.pose.bones[part['bone']], c))
            c.name = 'Anastacio Ragdoll ' + part['key']
            c.target = pivot
            c.influence = 0
        context.scene.update()
        folder, folder_created = ragdoll_folder(context.scene, rig, create=True)
        for obj in created:
            context.scene.object_bases[obj.name].collection = folder
        if runtime:
            prepare_physics(context, rig, created, parts)
            if component is None:
                result = bpy.ops.logic.python_component_register(
                    _override(context, rig), component_name=_MODULE + '.' + _COMPONENT)
                component = runtime_component(rig)
                component_created = component is not None
                if 'FINISHED' not in result or component is None:
                    raise ValueError('Não foi possível anexar o componente comum.')
            # Tipos/campos conhecidos: valida antes de substituir a geração anterior.
            if any(name not in component.properties for name in config):
                raise ValueError('Componente desatualizado: recarregue antes de gerar.')
    except Exception:
        if component_created:
            index = list(rig.game.components).index(component)
            bpy.ops.logic.python_component_remove(_override(context, rig), index=index)
        for bone, c in constraints:
            bone.constraints.remove(c)
        _discard(created)
        if folder_created:
            cleanup_folders(rig)
        raise
    # Operação de dados reversível pelo Undo do editor. Não reutiliza constraints alheias.
    remove_generated(rig, old, cleanup=False)
    if runtime:
        for name, value in config.items():
            component.properties[name].value = value
    return len(parts)


def draw_preview():
    rig = context_rig(bpy.context)
    if not rig or rig.type != 'ARMATURE' or not rig.anastacio_ragdoll.preview:
        return
    if rig.mode == 'EDIT':
        return
    try:
        parts = descriptors(rig)
    except ValueError:
        return  # O painel apresenta a mensagem; desenho não altera os dados.
    import bgl
    # Salva/restaura estado GL também quando o desenho é interrompido.
    bgl.glPushAttrib(bgl.GL_ENABLE_BIT | bgl.GL_CURRENT_BIT | bgl.GL_LINE_BIT)
    try:
        bgl.glDisable(bgl.GL_DEPTH_TEST)
        bgl.glLineWidth(2.0)
        selected = rig.anastacio_ragdoll.index
        items = rig.anastacio_ragdoll.bones
        selected_key = items[selected].key if selected < len(items) else None
        for part in parts:
            if part['key'] == selected_key:
                bgl.glColor4f(1.0, 0.65, 0.1, 1.0)
            else:
                bgl.glColor4f(0.1, 0.8, 1.0, 1.0)
            bgl.glBegin(bgl.GL_LINES)
            for i, j in _EDGES:
                bgl.glVertex3f(*part['corners'][i])
                bgl.glVertex3f(*part['corners'][j])
            bgl.glEnd()
    finally:
        bgl.glPopAttrib()


class AnastacioRagdollOperator:
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context_rig(context)
        return bool(obj and obj.type == 'ARMATURE'
                    and obj.mode != 'EDIT' and not obj.library)


class ANASTACIO_OT_ragdoll_sync(AnastacioRagdollOperator, bpy.types.Operator):
    bl_idname = 'anastacio.ragdoll_sync'
    bl_label = 'Ler ossos / atualizar lista'
    bl_description = 'Adiciona ossos novos; controles sem deformação começam desmarcados'

    def execute(self, context):
        sync_bones(context_rig(context))
        redraw()
        return {'FINISHED'}


class ANASTACIO_OT_ragdoll_selected(AnastacioRagdollOperator, bpy.types.Operator):
    bl_idname = 'anastacio.ragdoll_selected'
    bl_label = 'Usar somente ossos selecionados'

    def execute(self, context):
        rig = context_rig(context)
        sync_bones(rig)
        for item in rig.anastacio_ragdoll.bones:
            bone = rig.data.bones.get(item.name)
            item.enabled = bool(bone and bone.select and bone.length > 1e-5)
        return {'FINISHED'}


class ANASTACIO_OT_ragdoll_generate(AnastacioRagdollOperator, bpy.types.Operator):
    bl_idname = 'anastacio.ragdoll_generate'
    bl_label = 'Gerar / atualizar corpos'
    bl_description = 'Gera caixas em repouso; substitui somente a geração desta ferramenta'

    def execute(self, context):
        try:
            count = generate(context, context_rig(context))
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, '{} corpos preparados'.format(count))
        redraw()
        return {'FINISHED'}


class ANASTACIO_OT_ragdoll_runtime(AnastacioRagdollOperator, bpy.types.Operator):
    bl_idname = 'anastacio.ragdoll_runtime'
    bl_label = 'Preparar física + componente'

    def execute(self, context):
        try:
            generate(context, context_rig(context), runtime=True)
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, 'Física preparada e componente AnastacioRagdoll anexado')
        return {'FINISHED'}


class ANASTACIO_OT_ragdoll_preset(AnastacioRagdollOperator, bpy.types.Operator):
    bl_idname = 'anastacio.ragdoll_preset'
    bl_label = 'Aplicar preset aos ossos incluídos'

    def execute(self, context):
        apply_preset(context_rig(context))
        return {'FINISHED'}


class ANASTACIO_OT_ragdoll_remove(AnastacioRagdollOperator, bpy.types.Operator):
    bl_idname = 'anastacio.ragdoll_remove'
    bl_label = 'Remover corpos gerados'

    def execute(self, context):
        try:
            rig = context_rig(context)
            old = preflight(rig)
            remove_generated(rig, old)
            component = runtime_component(rig)
            if component is not None:
                bpy.ops.logic.python_component_remove(_override(context, rig),
                                                      index=list(rig.game.components).index(component))
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        redraw()
        return {'FINISHED'}


class ANASTACIO_UL_ragdoll_bones(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, 'enabled', text='')
        row.label(text=item.name, icon='BONE_DATA')


class ANASTACIO_PT_ragdoll(bpy.types.Panel):
    bl_label = 'Anastacio Ragdoll — Autoria'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'physics'

    @classmethod
    def poll(cls, context):
        if getattr(context.window_manager, 'ae_physics_panel_category', 'PHYSICS') != 'PHYSICS':
            return False
        return context_rig(context) is not None

    def draw(self, context):
        layout = self.layout
        rig = context_rig(context)
        settings = rig.anastacio_ragdoll
        layout.label(text=rig.name, icon='OUTLINER_OB_ARMATURE')
        layout.label(text='Caixas na pose de repouso', icon='BONE_DATA')
        layout.prop(rig.data, 'pose_position', expand=True)
        layout.prop(settings, 'preview')
        layout.operator('anastacio.ragdoll_sync')
        layout.operator('anastacio.ragdoll_selected')
        layout.template_list('ANASTACIO_UL_ragdoll_bones', '', settings, 'bones',
                             settings, 'index', rows=5)
        if settings.index < len(settings.bones):
            item = settings.bones[settings.index]
            box = layout.box()
            box.label(text=item.name)
            box.prop(item, 'enabled')
            for prop in ('width', 'depth', 'length_ratio', 'offset', 'rotation'):
                box.prop(item, prop)
            for prop in ('mass_weight', 'joint_limits', 'linear_damping', 'angular_damping'):
                box.prop(item, prop)
        try:
            parts = descriptors(rig)
            layout.label(text='{} corpos incluídos'.format(len(parts)))
        except ValueError as exc:
            layout.label(text=str(exc), icon='ERROR')
        layout.operator('anastacio.ragdoll_generate', icon='MESH_CUBE')
        layout.operator('anastacio.ragdoll_remove', icon='X')
        box = layout.box()
        box.label(text='Física e execução', icon='PHYSICS')
        box.prop(settings, 'preset')
        box.operator('anastacio.ragdoll_preset')
        box.prop(settings, 'total_mass')
        box.prop(settings, 'recovery_mode')
        box.prop(settings, 'anchor' if settings.recovery_mode == 'ANCHOR' else 'controller')
        box.prop(settings, 'auto_recover')
        if settings.auto_recover:
            box.prop(settings, 'recovery_delay')
        box.prop(settings, 'velocity_source')
        box.prop(settings, 'linear_inheritance')
        box.prop(settings, 'angular_inheritance')
        box.operator('anastacio.ragdoll_runtime', icon='PHYSICS')
        if runtime_component(rig):
            box.label(text='Componente anexado; atualizar aplica estes campos.', icon='CHECKMARK')
        else:
            box.label(text='Gerar corpos mantém apenas autoria até preparar execução.', icon='INFO')


_CLASSES = (AnastacioRagdollBone, AnastacioRagdollSettings, AnastacioRagdollLink,
            AnastacioRagdollFolder,
            ANASTACIO_OT_ragdoll_sync, ANASTACIO_OT_ragdoll_selected,
            ANASTACIO_OT_ragdoll_generate, ANASTACIO_OT_ragdoll_remove,
            ANASTACIO_OT_ragdoll_runtime, ANASTACIO_OT_ragdoll_preset,
            ANASTACIO_UL_ragdoll_bones, ANASTACIO_PT_ragdoll)


def register():
    global _handle
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Object.anastacio_ragdoll = PointerProperty(type=AnastacioRagdollSettings)
    bpy.types.Object.anastacio_ragdoll_link = PointerProperty(type=AnastacioRagdollLink)
    bpy.types.Scene.anastacio_ragdoll_folders = CollectionProperty(type=AnastacioRagdollFolder)
    if not bpy.app.background:
        _handle = bpy.types.SpaceView3D.draw_handler_add(draw_preview, (), 'WINDOW', 'POST_VIEW')


def unregister():
    global _handle
    if _handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_handle, 'WINDOW')
        _handle = None
    del bpy.types.Object.anastacio_ragdoll_link
    del bpy.types.Object.anastacio_ragdoll
    del bpy.types.Scene.anastacio_ragdoll_folders
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
    redraw()
