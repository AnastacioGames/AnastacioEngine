# -*- coding: utf-8 -*-
"""Ragdoll body and joint authoring with the shared component shipped by the engine."""
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
    'description': 'Per-bone preview and authoring of ragdoll bodies',
    'category': 'Game Engine',
}

_t = bpy.app.translations.pgettext_iface
_tip = bpy.app.translations.pgettext_tip

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
    enabled = BoolProperty(name='Include', default=True, update=redraw)
    width = FloatProperty(name='Width X', default=0.08, min=0.001, update=redraw)
    depth = FloatProperty(name='Depth Z', default=0.08, min=0.001, update=redraw)
    length_ratio = FloatProperty(name='Length / Bone', default=0.8,
                                 min=0.01, max=3.0, update=redraw)
    offset = FloatVectorProperty(name='Local Offset', subtype='TRANSLATION', update=redraw)
    rotation = FloatVectorProperty(name='Local Rotation', subtype='EULER', update=redraw)
    mass_weight = FloatProperty(name='Relative Mass Weight', default=1.0, min=0.01)
    joint_limits = FloatVectorProperty(name='Joint Limits XYZ', subtype='EULER',
                                      default=tuple(math.radians(v) for v in (45, 25, 45)),
                                      min=0.01, max=math.pi)
    linear_damping = FloatProperty(name='Linear Damping', default=0.08, min=0, max=1)
    angular_damping = FloatProperty(name='Angular Damping', default=0.45, min=0, max=1)


class AnastacioRagdollSettings(bpy.types.PropertyGroup):
    schema_version = IntProperty(default=1)
    bones = CollectionProperty(type=AnastacioRagdollBone)
    index = IntProperty(default=0, min=0, update=redraw)
    preview = BoolProperty(name='Show Preview', default=False, update=redraw)
    preset = EnumProperty(name='Behavior', items=[('HARD', 'Stiff', 'Tight joints and high damping'),
                          ('BALANCED', 'Balanced', 'Medium flexibility'),
                          ('LIGHT', 'Loose', 'Wide joints and low damping')], default='BALANCED')
    total_mass = FloatProperty(name='Total Mass', default=70.0, min=0.1)
    recovery_mode = EnumProperty(name='Recovery', items=[('FREE', 'Free / NPC', 'Returns to the ground'),
                                      ('ANCHOR', 'Anchor / Vehicle', 'Returns to the anchor')])
    auto_recover = BoolProperty(name='Auto Recover', default=True)
    recovery_delay = FloatProperty(name='Recovery Delay', default=3.0, min=0, subtype='TIME')
    anchor = PointerProperty(name='Anchor', type=bpy.types.Object)
    controller = PointerProperty(name='Collider / Controller', type=bpy.types.Object)
    velocity_source = PointerProperty(name='Velocity Source', type=bpy.types.Object)
    linear_inheritance = FloatProperty(name='Linear Inheritance', default=1.0, min=0, max=3)
    angular_inheritance = FloatProperty(name='Angular Inheritance', default=1.0, min=0, max=3)


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
        raise ValueError(_t('Select Pose Position in the panel before preparing for runtime; the boxes stay in rest pose.'))
    target = settings.anchor if settings.recovery_mode == 'ANCHOR' else settings.controller
    target = target or rig.parent
    if target is None or target == rig or target not in list(scene.objects):
        raise ValueError(_t('Set an external anchor/controller in this scene before preparing for runtime.'))
    scale = target.matrix_world.to_scale()
    if (target.matrix_world.determinant() <= 0 or min(scale) <= 1e-6
            or max(scale) - min(scale) > max(scale) * 1e-4):
        raise ValueError(_t('Apply the non-uniform/negative scale of the anchor or controller and its parents.'))
    axes = [target.matrix_world.col[i].to_3d().normalized() for i in range(3)]
    if any(abs(axes[i].dot(axes[j])) > 1e-4 for i in range(3) for j in range(i + 1, 3)):
        raise ValueError(_t('Remove shear from the anchor/controller.'))
    ancestor = target
    while ancestor:
        if ancestor == rig:
            raise ValueError(_t('Anchor/controller cannot be a descendant of the armature.'))
        ancestor = ancestor.parent
    if settings.recovery_mode == 'FREE':
        if target.parent or target.game.physics_type not in {'RIGID_BODY', 'DYNAMIC'}:
            raise ValueError(_t('Free mode requires a separate Rigid Body/Dynamic object at the scene root.'))
        if (not target.game.use_collision_bounds or target.game.collision_bounds_type != 'BOX'
                or target.game.use_ghost):
            raise ValueError(_t('Free mode requires a solid collider with BOX bounds.'))
        if rig.parent and rig.parent != target:
            raise ValueError(_t('The armature must be parented to the selected controller.'))
    if rig.game.physics_type != 'NO_COLLISION':
        raise ValueError(_t('The armature must use No Collision; physics lives on the bodies/controller.'))
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
        raise ValueError(_t('Apply mirroring/negative scale before generating.'))
    if max(scale) - min(scale) > max(scale) * 1e-4:
        raise ValueError(_t('Apply the non-uniform scale of the armature and its parents.'))
    normalized = [rig.matrix_world.col[i].to_3d().normalized() for i in range(3)]
    if any(abs(normalized[i].dot(normalized[j])) > 1e-4
           for i in range(3) for j in range(i + 1, 3)):
        raise ValueError(_t('Remove shear from the hierarchy before generating.'))
    result = []
    keys = set()
    for item in rig.anastacio_ragdoll.bones:
        if not item.enabled:
            continue
        bone = rig.data.bones.get(item.name)
        if bone is None:
            raise ValueError(_t('Missing/renamed bone: {}. Uncheck or resync the entry.').format(item.name))
        if bone.length <= 1e-5:
            raise ValueError(_t('Zero-length bone: {}').format(bone.name))
        if not item.key or item.key in keys:
            raise ValueError(_t('Invalid bone identity: {}').format(bone.name))
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
        raise ValueError(_t('Use a local, editable armature.'))
    # Nunca apaga filhos, modificadores ou referências de constraints do usuário.
    for obj in old:
        if obj.library or any(child not in old_set for child in obj.children):
            raise ValueError(_t('Body has an external link or a user child: {}').format(obj.name))
    for obj in bpy.data.objects:
        if obj in old_set:
            continue
        if obj.parent in old_set:
            raise ValueError(_t('User object depends on the ragdoll: {}').format(obj.name))
        constraints = list(obj.constraints)
        if obj.type == 'ARMATURE':
            for bone in obj.pose.bones:
                for c in bone.constraints:
                    if obj == rig and own_constraint(c, rig, old_set):
                        if c.influence != 0:
                            raise ValueError(_t('Disable the ragdoll constraints before editing.'))
                        continue
                    constraints.append(c)
        if any(getattr(c, 'target', None) in old_set for c in constraints):
            raise ValueError(_t('User constraint depends on the ragdoll: {}').format(obj.name))
        if any(getattr(mod, 'object', None) in old_set for mod in obj.modifiers):
            raise ValueError(_t('User modifier depends on the ragdoll: {}').format(obj.name))
    # Não migra um Easy Ragdoll existente silenciosamente.
    for bone in rig.pose.bones:
        for c in bone.constraints:
            if (c.name.startswith('Anastacio Ragdoll ') and c.target
                    and c.target.anastacio_ragdoll_link.rig != rig):
                raise ValueError(_t('Duplicated rig still linked to the original. Remove the copied links before generating.'))
            if (c.type == 'COPY_TRANSFORMS' and c.target and c.target.parent
                    and c.target.parent.name.startswith('RagdollPart-')
                    and c.target not in old_set):
                raise ValueError(_t('This rig already uses Easy Ragdoll. Use a clean copy for new authoring.'))
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
        raise ValueError(_t('Include at least one bone.'))
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
                    raise ValueError(_t('Could not attach the shared component.'))
            # Tipos/campos conhecidos: valida antes de substituir a geração anterior.
            if any(name not in component.properties for name in config):
                raise ValueError(_t('Outdated component: reload it before generating.'))
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
    bl_label = 'Read Bones / Refresh List'
    bl_description = 'Adds new bones; non-deforming control bones start unchecked'

    def execute(self, context):
        sync_bones(context_rig(context))
        redraw()
        return {'FINISHED'}


class ANASTACIO_OT_ragdoll_selected(AnastacioRagdollOperator, bpy.types.Operator):
    bl_idname = 'anastacio.ragdoll_selected'
    bl_label = 'Use Selected Bones Only'

    def execute(self, context):
        rig = context_rig(context)
        sync_bones(rig)
        for item in rig.anastacio_ragdoll.bones:
            bone = rig.data.bones.get(item.name)
            item.enabled = bool(bone and bone.select and bone.length > 1e-5)
        return {'FINISHED'}


class ANASTACIO_OT_ragdoll_generate(AnastacioRagdollOperator, bpy.types.Operator):
    bl_idname = 'anastacio.ragdoll_generate'
    bl_label = 'Generate / Update Bodies'
    bl_description = 'Generates boxes in rest pose; replaces only what this tool generated'

    def execute(self, context):
        try:
            count = generate(context, context_rig(context))
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, _tip('{} bodies prepared').format(count))
        redraw()
        return {'FINISHED'}


class ANASTACIO_OT_ragdoll_runtime(AnastacioRagdollOperator, bpy.types.Operator):
    bl_idname = 'anastacio.ragdoll_runtime'
    bl_label = 'Prepare Physics + Component'

    def execute(self, context):
        try:
            generate(context, context_rig(context), runtime=True)
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, _tip('Physics prepared and AnastacioRagdoll component attached'))
        return {'FINISHED'}


class ANASTACIO_OT_ragdoll_preset(AnastacioRagdollOperator, bpy.types.Operator):
    bl_idname = 'anastacio.ragdoll_preset'
    bl_label = 'Apply Preset to Included Bones'

    def execute(self, context):
        apply_preset(context_rig(context))
        return {'FINISHED'}


class ANASTACIO_OT_ragdoll_remove(AnastacioRagdollOperator, bpy.types.Operator):
    bl_idname = 'anastacio.ragdoll_remove'
    bl_label = 'Remove Generated Bodies'

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
    bl_label = 'Ragdoll'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'physics'

    @classmethod
    def poll(cls, context):
        if getattr(context.window_manager, 'ae_physics_panel_category', 'PHYSICS') != 'PHYSICS':
            return False
        return context_rig(context) is not None

    def draw(self, context):
        layout = self.layout.box()
        rig = context_rig(context)
        settings = rig.anastacio_ragdoll
        layout.label(text=rig.name, icon='OUTLINER_OB_ARMATURE')
        layout.label(text='Boxes in Rest Pose', icon='BONE_DATA')
        layout.row(align=True).prop(rig.data, 'pose_position', expand=True)
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
            def vector_row(prop):
                box.label(text=item.bl_rna.properties[prop].name + ':')
                box.row(align=True).prop(item, prop, text='')

            box.label(text='Size (width X, depth Z, length):')
            size_row = box.row(align=True)
            for prop, label in (('width', 'X'), ('depth', 'Z'), ('length_ratio', 'Len.')):
                size_row.prop(item, prop, text=label)
            vector_row('offset')
            vector_row('rotation')
            box.prop(item, 'mass_weight')
            vector_row('joint_limits')
            box.label(text='Damping:')
            damping_row = box.row(align=True)
            damping_row.prop(item, 'linear_damping', text='Linear')
            damping_row.prop(item, 'angular_damping', text='Angular')
        try:
            parts = descriptors(rig)
            layout.label(text=_t('{} bodies included').format(len(parts)))
        except ValueError as exc:
            layout.label(text=str(exc), icon='ERROR')
        layout.operator('anastacio.ragdoll_generate', icon='MESH_CUBE')
        layout.operator('anastacio.ragdoll_remove', icon='X')
        box = layout.box()
        box.label(text='Physics and Runtime', icon='PHYSICS')
        box.prop(settings, 'preset')
        box.operator('anastacio.ragdoll_preset')
        box.prop(settings, 'total_mass')
        box.prop(settings, 'recovery_mode')
        box.prop(settings, 'anchor' if settings.recovery_mode == 'ANCHOR' else 'controller')
        box.prop(settings, 'auto_recover')
        if settings.auto_recover:
            box.prop(settings, 'recovery_delay')
        box.prop(settings, 'velocity_source')
        box.label(text='Inheritance:')
        inheritance_row = box.row(align=True)
        inheritance_row.prop(settings, 'linear_inheritance', text='Linear')
        inheritance_row.prop(settings, 'angular_inheritance', text='Angular')
        box.operator('anastacio.ragdoll_runtime', icon='PHYSICS')
        if runtime_component(rig):
            box.label(text='Component attached; updating applies these fields.', icon='FILE_TICK')
        else:
            box.label(text='Generating bodies is authoring only until you prepare for runtime.', icon='INFO')


_CLASSES = (AnastacioRagdollBone, AnastacioRagdollSettings, AnastacioRagdollLink,
            AnastacioRagdollFolder,
            ANASTACIO_OT_ragdoll_sync, ANASTACIO_OT_ragdoll_selected,
            ANASTACIO_OT_ragdoll_generate, ANASTACIO_OT_ragdoll_remove,
            ANASTACIO_OT_ragdoll_runtime, ANASTACIO_OT_ragdoll_preset,
            ANASTACIO_UL_ragdoll_bones, ANASTACIO_PT_ragdoll)


# English is the source language; translations ship with the addon.
translations_dict = {
    'pt_BR': {
        ("*", 'Per-bone preview and authoring of ragdoll bodies'): 'Prévia e autoria por osso de corpos de ragdoll',
        ("*", 'Include'): 'Incluir',
        ("*", 'Width X'): 'Largura X',
        ("*", 'Depth Z'): 'Profundidade Z',
        ("*", 'Length / Bone'): 'Comprimento / osso',
        ("*", 'Local Offset'): 'Deslocamento local',
        ("*", 'Local Rotation'): 'Rotação local',
        ("*", 'Relative Mass Weight'): 'Peso relativo de massa',
        ("*", 'Joint Limits XYZ'): 'Limites da articulação XYZ',
        ("*", 'Linear Damping'): 'Amortecimento linear',
        ("*", 'Angular Damping'): 'Amortecimento angular',
        ("*", 'Show Preview'): 'Mostrar prévia',
        ("*", 'Behavior'): 'Comportamento',
        ("*", 'Stiff'): 'Duro',
        ("*", 'Tight joints and high damping'): 'Juntas restritas e amortecimento alto',
        ("*", 'Balanced'): 'Equilibrado',
        ("*", 'Medium flexibility'): 'Flexibilidade intermediária',
        ("*", 'Loose'): 'Leve',
        ("*", 'Wide joints and low damping'): 'Juntas amplas e amortecimento baixo',
        ("*", 'Total Mass'): 'Massa total',
        ("*", 'Recovery'): 'Recuperação',
        ("*", 'Free / NPC'): 'Livre / NPC',
        ("*", 'Returns to the ground'): 'Retorna ao chão',
        ("*", 'Anchor / Vehicle'): 'Âncora / veículo',
        ("*", 'Returns to the anchor'): 'Retorna à âncora',
        ("*", 'Auto Recover'): 'Recuperar automaticamente',
        ("*", 'Recovery Delay'): 'Tempo para recuperar',
        ("*", 'Anchor'): 'Âncora',
        ("*", 'Collider / Controller'): 'Colisor / controlador',
        ("*", 'Velocity Source'): 'Fonte de velocidade',
        ("*", 'Linear Inheritance'): 'Herança linear',
        ("*", 'Angular Inheritance'): 'Herança angular',
        ("*", 'Select Pose Position in the panel before preparing for runtime; the boxes stay in rest pose.'): 'Selecione Pose Position no painel antes de preparar execução; os cubos continuam em repouso.',
        ("*", 'Set an external anchor/controller in this scene before preparing for runtime.'): 'Configure uma âncora/controlador externo nesta cena antes de preparar execução.',
        ("*", 'Apply the non-uniform/negative scale of the anchor or controller and its parents.'): 'Aplique a escala não uniforme/negativa da âncora ou controlador e seus pais.',
        ("*", 'Remove shear from the anchor/controller.'): 'Remova o cisalhamento da âncora/controlador.',
        ("*", 'Anchor/controller cannot be a descendant of the armature.'): 'Âncora/controlador não pode ser descendente da armature.',
        ("*", 'Free mode requires a separate Rigid Body/Dynamic object at the scene root.'): 'Modo livre inicial exige Rigid Body/Dynamic separado, na raiz da cena.',
        ("*", 'Free mode requires a solid collider with BOX bounds.'): 'Modo livre inicial exige colisor sólido com bounds BOX.',
        ("*", 'The armature must be parented to the selected controller.'): 'Armature deve estar vinculada ao controlador selecionado.',
        ("*", 'The armature must use No Collision; physics lives on the bodies/controller.'): 'A armature deve usar No Collision; a física fica nos corpos/controlador.',
        ("*", 'Apply mirroring/negative scale before generating.'): 'Aplique o espelhamento/escala negativa antes de gerar.',
        ("*", 'Apply the non-uniform scale of the armature and its parents.'): 'Aplique a escala não uniforme da armature e dos pais.',
        ("*", 'Remove shear from the hierarchy before generating.'): 'Remova o cisalhamento da hierarquia antes de gerar.',
        ("*", 'Use a local, editable armature.'): 'Use uma armature local e editável.',
        ("*", 'Disable the ragdoll constraints before editing.'): 'Desative as constraints do ragdoll antes de editar.',
        ("*", 'Duplicated rig still linked to the original. Remove the copied links before generating.'): 'Rig duplicado com vínculos do original. Remova os vínculos copiados antes de gerar.',
        ("*", 'This rig already uses Easy Ragdoll. Use a clean copy for new authoring.'): 'Este rig já usa Easy Ragdoll. Use uma cópia limpa para a nova autoria.',
        ("*", 'Include at least one bone.'): 'Inclua ao menos um osso.',
        ("*", 'Could not attach the shared component.'): 'Não foi possível anexar o componente comum.',
        ("*", 'Outdated component: reload it before generating.'): 'Componente desatualizado: recarregue antes de gerar.',
        ("*", 'Read Bones / Refresh List'): 'Ler ossos / atualizar lista',
        ("Operator", 'Read Bones / Refresh List'): 'Ler ossos / atualizar lista',
        ("*", 'Adds new bones; non-deforming control bones start unchecked'): 'Adiciona ossos novos; controles sem deformação começam desmarcados',
        ("*", 'Use Selected Bones Only'): 'Usar somente ossos selecionados',
        ("Operator", 'Use Selected Bones Only'): 'Usar somente ossos selecionados',
        ("*", 'Generate / Update Bodies'): 'Gerar / atualizar corpos',
        ("Operator", 'Generate / Update Bodies'): 'Gerar / atualizar corpos',
        ("*", 'Generates boxes in rest pose; replaces only what this tool generated'): 'Gera caixas em repouso; substitui somente a geração desta ferramenta',
        ("*", 'Physics prepared and AnastacioRagdoll component attached'): 'Física preparada e componente AnastacioRagdoll anexado',
        ("*", 'Prepare Physics + Component'): 'Preparar física + componente',
        ("Operator", 'Prepare Physics + Component'): 'Preparar física + componente',
        ("*", 'Apply Preset to Included Bones'): 'Aplicar preset aos ossos incluídos',
        ("Operator", 'Apply Preset to Included Bones'): 'Aplicar preset aos ossos incluídos',
        ("*", 'Remove Generated Bodies'): 'Remover corpos gerados',
        ("Operator", 'Remove Generated Bodies'): 'Remover corpos gerados',
        ("*", 'Boxes in Rest Pose'): 'Caixas na pose de repouso',
        ("*", 'Size (width X, depth Z, length):'): 'Tamanho (largura X, profundidade Z, comprimento):',
        ("*", 'Len.'): 'Comp.',
        ("*", 'Damping:'): 'Amortecimento:',
        ("*", 'Physics and Runtime'): 'Física e execução',
        ("*", 'Inheritance:'): 'Herança:',
        ("*", 'Component attached; updating applies these fields.'): 'Componente anexado; atualizar aplica estes campos.',
        ("*", 'Generating bodies is authoring only until you prepare for runtime.'): 'Gerar corpos mantém apenas autoria até preparar execução.',
        ("*", '{} bodies prepared'): '{} corpos preparados',
        ("*", '{} bodies included'): '{} corpos incluídos',
        ("*", 'Missing/renamed bone: {}. Uncheck or resync the entry.'): 'Osso ausente/renomeado: {}. Desmarque ou ressincronize a entrada.',
        ("*", 'Zero-length bone: {}'): 'Osso sem comprimento: {}',
        ("*", 'Invalid bone identity: {}'): 'Identidade de osso inválida: {}',
        ("*", 'Body has an external link or a user child: {}'): 'Corpo possui vínculo externo/filho do usuário: {}',
        ("*", 'User object depends on the ragdoll: {}'): 'Objeto do usuário depende do ragdoll: {}',
        ("*", 'User constraint depends on the ragdoll: {}'): 'Constraint do usuário depende do ragdoll: {}',
        ("*", 'User modifier depends on the ragdoll: {}'): 'Modificador do usuário depende do ragdoll: {}',
    },
    'es': {
        ("*", 'Per-bone preview and authoring of ragdoll bodies'): 'Vista previa y creación por hueso de cuerpos de ragdoll',
        ("*", 'Include'): 'Incluir',
        ("*", 'Width X'): 'Ancho X',
        ("*", 'Depth Z'): 'Profundidad Z',
        ("*", 'Length / Bone'): 'Longitud / hueso',
        ("*", 'Local Offset'): 'Desplazamiento local',
        ("*", 'Local Rotation'): 'Rotación local',
        ("*", 'Relative Mass Weight'): 'Peso relativo de masa',
        ("*", 'Joint Limits XYZ'): 'Límites de la articulación XYZ',
        ("*", 'Linear Damping'): 'Amortiguación lineal',
        ("*", 'Angular Damping'): 'Amortiguación angular',
        ("*", 'Show Preview'): 'Mostrar vista previa',
        ("*", 'Behavior'): 'Comportamiento',
        ("*", 'Stiff'): 'Rígido',
        ("*", 'Tight joints and high damping'): 'Articulaciones restringidas y amortiguación alta',
        ("*", 'Balanced'): 'Equilibrado',
        ("*", 'Medium flexibility'): 'Flexibilidad intermedia',
        ("*", 'Loose'): 'Suelto',
        ("*", 'Wide joints and low damping'): 'Articulaciones amplias y amortiguación baja',
        ("*", 'Total Mass'): 'Masa total',
        ("*", 'Recovery'): 'Recuperación',
        ("*", 'Free / NPC'): 'Libre / NPC',
        ("*", 'Returns to the ground'): 'Vuelve al suelo',
        ("*", 'Anchor / Vehicle'): 'Ancla / vehículo',
        ("*", 'Returns to the anchor'): 'Vuelve al ancla',
        ("*", 'Auto Recover'): 'Recuperar automáticamente',
        ("*", 'Recovery Delay'): 'Tiempo para recuperar',
        ("*", 'Anchor'): 'Ancla',
        ("*", 'Collider / Controller'): 'Colisionador / controlador',
        ("*", 'Velocity Source'): 'Fuente de velocidad',
        ("*", 'Linear Inheritance'): 'Herencia lineal',
        ("*", 'Angular Inheritance'): 'Herencia angular',
        ("*", 'Select Pose Position in the panel before preparing for runtime; the boxes stay in rest pose.'): 'Selecciona Pose Position en el panel antes de preparar la ejecución; las cajas siguen en reposo.',
        ("*", 'Set an external anchor/controller in this scene before preparing for runtime.'): 'Configura un ancla/controlador externo en esta escena antes de preparar la ejecución.',
        ("*", 'Apply the non-uniform/negative scale of the anchor or controller and its parents.'): 'Aplica la escala no uniforme/negativa del ancla o controlador y sus padres.',
        ("*", 'Remove shear from the anchor/controller.'): 'Elimina la cizalla del ancla/controlador.',
        ("*", 'Anchor/controller cannot be a descendant of the armature.'): 'El ancla/controlador no puede ser descendiente de la armature.',
        ("*", 'Free mode requires a separate Rigid Body/Dynamic object at the scene root.'): 'El modo libre requiere un Rigid Body/Dynamic separado en la raíz de la escena.',
        ("*", 'Free mode requires a solid collider with BOX bounds.'): 'El modo libre requiere un colisionador sólido con bounds BOX.',
        ("*", 'The armature must be parented to the selected controller.'): 'La armature debe estar vinculada al controlador seleccionado.',
        ("*", 'The armature must use No Collision; physics lives on the bodies/controller.'): 'La armature debe usar No Collision; la física va en los cuerpos/controlador.',
        ("*", 'Apply mirroring/negative scale before generating.'): 'Aplica el reflejo/escala negativa antes de generar.',
        ("*", 'Apply the non-uniform scale of the armature and its parents.'): 'Aplica la escala no uniforme de la armature y sus padres.',
        ("*", 'Remove shear from the hierarchy before generating.'): 'Elimina la cizalla de la jerarquía antes de generar.',
        ("*", 'Use a local, editable armature.'): 'Usa una armature local y editable.',
        ("*", 'Disable the ragdoll constraints before editing.'): 'Desactiva las constraints del ragdoll antes de editar.',
        ("*", 'Duplicated rig still linked to the original. Remove the copied links before generating.'): 'Rig duplicado con vínculos del original. Quita los vínculos copiados antes de generar.',
        ("*", 'This rig already uses Easy Ragdoll. Use a clean copy for new authoring.'): 'Este rig ya usa Easy Ragdoll. Usa una copia limpia para la nueva creación.',
        ("*", 'Include at least one bone.'): 'Incluye al menos un hueso.',
        ("*", 'Could not attach the shared component.'): 'No se pudo adjuntar el componente común.',
        ("*", 'Outdated component: reload it before generating.'): 'Componente desactualizado: recárgalo antes de generar.',
        ("*", 'Read Bones / Refresh List'): 'Leer huesos / actualizar lista',
        ("Operator", 'Read Bones / Refresh List'): 'Leer huesos / actualizar lista',
        ("*", 'Adds new bones; non-deforming control bones start unchecked'): 'Añade huesos nuevos; los controles sin deformación empiezan desmarcados',
        ("*", 'Use Selected Bones Only'): 'Usar solo huesos seleccionados',
        ("Operator", 'Use Selected Bones Only'): 'Usar solo huesos seleccionados',
        ("*", 'Generate / Update Bodies'): 'Generar / actualizar cuerpos',
        ("Operator", 'Generate / Update Bodies'): 'Generar / actualizar cuerpos',
        ("*", 'Generates boxes in rest pose; replaces only what this tool generated'): 'Genera cajas en reposo; reemplaza solo lo generado por esta herramienta',
        ("*", 'Physics prepared and AnastacioRagdoll component attached'): 'Física preparada y componente AnastacioRagdoll adjuntado',
        ("*", 'Prepare Physics + Component'): 'Preparar física + componente',
        ("Operator", 'Prepare Physics + Component'): 'Preparar física + componente',
        ("*", 'Apply Preset to Included Bones'): 'Aplicar preset a los huesos incluidos',
        ("Operator", 'Apply Preset to Included Bones'): 'Aplicar preset a los huesos incluidos',
        ("*", 'Remove Generated Bodies'): 'Quitar cuerpos generados',
        ("Operator", 'Remove Generated Bodies'): 'Quitar cuerpos generados',
        ("*", 'Boxes in Rest Pose'): 'Cajas en la pose de reposo',
        ("*", 'Size (width X, depth Z, length):'): 'Tamaño (ancho X, profundidad Z, longitud):',
        ("*", 'Len.'): 'Long.',
        ("*", 'Damping:'): 'Amortiguación:',
        ("*", 'Physics and Runtime'): 'Física y ejecución',
        ("*", 'Inheritance:'): 'Herencia:',
        ("*", 'Component attached; updating applies these fields.'): 'Componente adjuntado; actualizar aplica estos campos.',
        ("*", 'Generating bodies is authoring only until you prepare for runtime.'): 'Generar cuerpos es solo creación hasta preparar la ejecución.',
        ("*", '{} bodies prepared'): '{} cuerpos preparados',
        ("*", '{} bodies included'): '{} cuerpos incluidos',
        ("*", 'Missing/renamed bone: {}. Uncheck or resync the entry.'): 'Hueso ausente/renombrado: {}. Desmarca o resincroniza la entrada.',
        ("*", 'Zero-length bone: {}'): 'Hueso sin longitud: {}',
        ("*", 'Invalid bone identity: {}'): 'Identidad de hueso no válida: {}',
        ("*", 'Body has an external link or a user child: {}'): 'El cuerpo tiene un vínculo externo/hijo del usuario: {}',
        ("*", 'User object depends on the ragdoll: {}'): 'Un objeto del usuario depende del ragdoll: {}',
        ("*", 'User constraint depends on the ragdoll: {}'): 'Una constraint del usuario depende del ragdoll: {}',
        ("*", 'User modifier depends on the ragdoll: {}'): 'Un modificador del usuario depende del ragdoll: {}',
    },
    'ru_RU': {
        ("*", 'Per-bone preview and authoring of ragdoll bodies'): 'Предпросмотр и настройка тел ragdoll по костям',
        ("*", 'Include'): 'Включить',
        ("*", 'Width X'): 'Ширина X',
        ("*", 'Depth Z'): 'Глубина Z',
        ("*", 'Length / Bone'): 'Длина / кость',
        ("*", 'Local Offset'): 'Локальное смещение',
        ("*", 'Local Rotation'): 'Локальный поворот',
        ("*", 'Relative Mass Weight'): 'Относительный вес массы',
        ("*", 'Joint Limits XYZ'): 'Пределы сустава XYZ',
        ("*", 'Linear Damping'): 'Линейное затухание',
        ("*", 'Angular Damping'): 'Угловое затухание',
        ("*", 'Show Preview'): 'Показать предпросмотр',
        ("*", 'Behavior'): 'Поведение',
        ("*", 'Stiff'): 'Жёсткий',
        ("*", 'Tight joints and high damping'): 'Ограниченные суставы и сильное затухание',
        ("*", 'Balanced'): 'Сбалансированный',
        ("*", 'Medium flexibility'): 'Средняя гибкость',
        ("*", 'Loose'): 'Свободный',
        ("*", 'Wide joints and low damping'): 'Широкие суставы и слабое затухание',
        ("*", 'Total Mass'): 'Общая масса',
        ("*", 'Recovery'): 'Восстановление',
        ("*", 'Free / NPC'): 'Свободный / NPC',
        ("*", 'Returns to the ground'): 'Возвращается на землю',
        ("*", 'Anchor / Vehicle'): 'Якорь / транспорт',
        ("*", 'Returns to the anchor'): 'Возвращается к якорю',
        ("*", 'Auto Recover'): 'Автовосстановление',
        ("*", 'Recovery Delay'): 'Задержка восстановления',
        ("*", 'Anchor'): 'Якорь',
        ("*", 'Collider / Controller'): 'Коллайдер / контроллер',
        ("*", 'Velocity Source'): 'Источник скорости',
        ("*", 'Linear Inheritance'): 'Линейное наследование',
        ("*", 'Angular Inheritance'): 'Угловое наследование',
        ("*", 'Select Pose Position in the panel before preparing for runtime; the boxes stay in rest pose.'): 'Выберите Pose Position на панели перед подготовкой к запуску; коробки остаются в позе покоя.',
        ("*", 'Set an external anchor/controller in this scene before preparing for runtime.'): 'Задайте внешний якорь/контроллер в этой сцене перед подготовкой к запуску.',
        ("*", 'Apply the non-uniform/negative scale of the anchor or controller and its parents.'): 'Примените неравномерный/отрицательный масштаб якоря или контроллера и их родителей.',
        ("*", 'Remove shear from the anchor/controller.'): 'Уберите сдвиг (shear) у якоря/контроллера.',
        ("*", 'Anchor/controller cannot be a descendant of the armature.'): 'Якорь/контроллер не может быть потомком armature.',
        ("*", 'Free mode requires a separate Rigid Body/Dynamic object at the scene root.'): 'Свободный режим требует отдельного Rigid Body/Dynamic в корне сцены.',
        ("*", 'Free mode requires a solid collider with BOX bounds.'): 'Свободный режим требует твёрдого коллайдера с bounds BOX.',
        ("*", 'The armature must be parented to the selected controller.'): 'Armature должна быть привязана к выбранному контроллеру.',
        ("*", 'The armature must use No Collision; physics lives on the bodies/controller.'): 'Armature должна использовать No Collision; физика находится в телах/контроллере.',
        ("*", 'Apply mirroring/negative scale before generating.'): 'Примените отражение/отрицательный масштаб перед генерацией.',
        ("*", 'Apply the non-uniform scale of the armature and its parents.'): 'Примените неравномерный масштаб armature и её родителей.',
        ("*", 'Remove shear from the hierarchy before generating.'): 'Уберите сдвиг (shear) в иерархии перед генерацией.',
        ("*", 'Use a local, editable armature.'): 'Используйте локальную редактируемую armature.',
        ("*", 'Disable the ragdoll constraints before editing.'): 'Отключите constraints ragdoll перед редактированием.',
        ("*", 'Duplicated rig still linked to the original. Remove the copied links before generating.'): 'Дубликат рига связан с оригиналом. Удалите скопированные связи перед генерацией.',
        ("*", 'This rig already uses Easy Ragdoll. Use a clean copy for new authoring.'): 'Этот риг уже использует Easy Ragdoll. Используйте чистую копию для новой настройки.',
        ("*", 'Include at least one bone.'): 'Включите хотя бы одну кость.',
        ("*", 'Could not attach the shared component.'): 'Не удалось прикрепить общий компонент.',
        ("*", 'Outdated component: reload it before generating.'): 'Компонент устарел: перезагрузите его перед генерацией.',
        ("*", 'Read Bones / Refresh List'): 'Прочитать кости / обновить список',
        ("Operator", 'Read Bones / Refresh List'): 'Прочитать кости / обновить список',
        ("*", 'Adds new bones; non-deforming control bones start unchecked'): 'Добавляет новые кости; управляющие кости без деформации изначально не отмечены',
        ("*", 'Use Selected Bones Only'): 'Только выбранные кости',
        ("Operator", 'Use Selected Bones Only'): 'Только выбранные кости',
        ("*", 'Generate / Update Bodies'): 'Создать / обновить тела',
        ("Operator", 'Generate / Update Bodies'): 'Создать / обновить тела',
        ("*", 'Generates boxes in rest pose; replaces only what this tool generated'): 'Создаёт коробки в позе покоя; заменяет только созданное этим инструментом',
        ("*", 'Physics prepared and AnastacioRagdoll component attached'): 'Физика подготовлена, компонент AnastacioRagdoll прикреплён',
        ("*", 'Prepare Physics + Component'): 'Подготовить физику + компонент',
        ("Operator", 'Prepare Physics + Component'): 'Подготовить физику + компонент',
        ("*", 'Apply Preset to Included Bones'): 'Применить пресет к включённым костям',
        ("Operator", 'Apply Preset to Included Bones'): 'Применить пресет к включённым костям',
        ("*", 'Remove Generated Bodies'): 'Удалить созданные тела',
        ("Operator", 'Remove Generated Bodies'): 'Удалить созданные тела',
        ("*", 'Boxes in Rest Pose'): 'Коробки в позе покоя',
        ("*", 'Size (width X, depth Z, length):'): 'Размер (ширина X, глубина Z, длина):',
        ("*", 'Len.'): 'Дл.',
        ("*", 'Damping:'): 'Затухание:',
        ("*", 'Physics and Runtime'): 'Физика и запуск',
        ("*", 'Inheritance:'): 'Наследование:',
        ("*", 'Component attached; updating applies these fields.'): 'Компонент прикреплён; обновление применит эти поля.',
        ("*", 'Generating bodies is authoring only until you prepare for runtime.'): 'Создание тел — только настройка, пока вы не подготовите запуск.',
        ("*", '{} bodies prepared'): 'Подготовлено тел: {}',
        ("*", '{} bodies included'): 'Включено тел: {}',
        ("*", 'Missing/renamed bone: {}. Uncheck or resync the entry.'): 'Кость отсутствует/переименована: {}. Снимите отметку или синхронизируйте запись.',
        ("*", 'Zero-length bone: {}'): 'Кость нулевой длины: {}',
        ("*", 'Invalid bone identity: {}'): 'Недопустимый идентификатор кости: {}',
        ("*", 'Body has an external link or a user child: {}'): 'Тело имеет внешнюю связь или дочерний объект пользователя: {}',
        ("*", 'User object depends on the ragdoll: {}'): 'Объект пользователя зависит от ragdoll: {}',
        ("*", 'User constraint depends on the ragdoll: {}'): 'Constraint пользователя зависит от ragdoll: {}',
        ("*", 'User modifier depends on the ragdoll: {}'): 'Модификатор пользователя зависит от ragdoll: {}',
    },
}


def register():
    global _handle
    try:
        bpy.app.translations.register(__name__, translations_dict)
    except ValueError:
        bpy.app.translations.unregister(__name__)
        bpy.app.translations.register(__name__, translations_dict)
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
    try:
        bpy.app.translations.unregister(__name__)
    except Exception:
        pass
    redraw()
