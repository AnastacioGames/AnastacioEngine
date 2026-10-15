# -*- coding: utf-8 -*-
"""Execução comum de ragdoll, sem input ou regras específicas de um jogo."""
from collections import OrderedDict
import math

import Range
from mathutils import Matrix, Vector

PREFIX = 'Anastacio Ragdoll '
BODY_GROUP = 1 << 15
RUNTIME_VERSION = (0, 3, 0)


class AnastacioRagdoll(Range.types.KX_PythonComponent):
    args = OrderedDict([
        ('Active', False), ('Recovery Mode', 'FREE'),
        ('Auto Recover', True), ('Recovery Delay', 3.0),
        ('Anchor', ''), ('Controller', ''), ('Velocity Source', ''),
        ('Linear Inheritance', 1.0), ('Angular Inheritance', 1.0),
    ])
    anastacio_ragdoll = True
    runtime_version = RUNTIME_VERSION
    is_valid = False
    active = False
    error = ''

    @staticmethod
    def world_transform(obj):
        # Setters atualizam localTransform antes do cache mundial do scenegraph.
        # Compõe a hierarquia para transições no mesmo tick, sem precisar de C++.
        result = obj.localTransform.copy()
        parent = obj.parent
        while parent:
            result = parent.localTransform * result
            parent = parent.parent
        return result

    def start(self, args):
        self.active = False
        self.is_valid = False
        self.error = ''
        self.blocked_reason = ''
        self.entries = []
        self._ready = False
        self._requested = bool(args.get('Active', False))
        self._started_at = self._retry_at = 0.0
        self._initial = None
        self._recovered_time = None
        self._recovered_pose = None
        # O jogo pode fornecer callbacks: validar destino e retomar AI/animação.
        self.recovery_validator = None
        self.on_recovered = None
        self.mode = args.get('Recovery Mode', 'FREE').upper()
        self.auto_recover = bool(args.get('Auto Recover', True))
        self.recovery_delay = max(0.0, float(args.get('Recovery Delay', 3.0)))
        self.linear_inheritance = float(args.get('Linear Inheritance', 1.0))
        self.angular_inheritance = float(args.get('Angular Inheritance', 1.0))
        self.controller = self.anchor = self.velocity_source = None
        try:
            if self.mode not in {'FREE', 'ANCHOR'}:
                raise ValueError('Recovery Mode deve ser FREE ou ANCHOR')
            self.controller = self._resolve(args.get('Controller', ''))
            self.anchor = self._resolve(args.get('Anchor', ''))
            self.velocity_source = self._resolve(args.get('Velocity Source', ''))
            if self.mode == 'ANCHOR':
                self.anchor = self.anchor or self.object.parent
                if self.anchor is None or self.anchor == self.object:
                    raise ValueError('Modo ANCHOR exige uma âncora externa')
            else:
                self.controller = self.controller or self.object.parent
                if self.controller is None or self.controller == self.object:
                    raise ValueError('Modo FREE exige colisor/controlador separado da armature')
                if self.controller.parent is not None:
                    raise ValueError('Controlador FREE deve estar na raiz da cena')
                # BOX sólido é validado pelo gerador; o runtime não depende de bpy.
                if not self.controller.getPhysicsId() or not self.controller.meshes:
                    raise ValueError('FREE exige controlador físico com malha e bounds BOX')
            self.velocity_source = self.velocity_source or self.controller or self.anchor
            for constraint in self.object.constraints:
                if constraint.type != 23 or not constraint.name.startswith(PREFIX):
                    continue
                pivot = constraint.target
                if pivot is None or pivot.get('ar_role') != 'PIVOT':
                    raise ValueError('Pivô gerado ausente: ' + constraint.name)
                body = pivot.parent
                key = pivot.get('ar_key')
                if (body is None or body.get('ar_role') != 'BODY'
                        or not key or body.get('ar_key') != key
                        or pivot.get('ar_constraint') != constraint.name):
                    raise ValueError('Associação corpo/pivô inválida: %r' %
                                     ((constraint.name, key, pivot.get('ar_key'),
                                       body.get('ar_key') if body else None,
                                       body.get('ar_role') if body else None),))
                if any(item['body'] == body for item in self.entries):
                    raise ValueError('Corpo associado a mais de um osso')
                if body.parent is not None or not body.getPhysicsId():
                    raise ValueError('Corpo gerado deve ter física própria e ficar sem pai')
                self.entries.append(dict(body=body, pivot=pivot, constraint=constraint,
                                         bone=pivot['ar_bone'], offset=pivot.localTransform.inverted()))
            if not self.entries:
                raise ValueError('Nenhum corpo preparado para o novo runtime')
            for item in self.entries:
                item['constraint'].enforce = 0.0
                item['body'].suspendPhysics()
            self.object['active_ragdoll'] = self._requested
            self.object['ragdoll_error'] = ''
            self.is_valid = True
        except Exception as exc:
            self._fail(exc)

    def _resolve(self, name):
        if not name:
            return None
        obj = self.object.scene.objects.get(name)
        if obj is None:
            raise ValueError('Objeto configurado não encontrado: ' + name)
        return obj

    def _fail(self, exc):
        self.error = str(exc)
        self.is_valid = False
        self.object['ragdoll_error'] = self.error
        # Não confirma recuperação nem restaura controle após falha parcial.
        for item in self.entries:
            if not item['body'].invalid:
                item['body'].suspendPhysics()
        print('[Anastacio Ragdoll] %s: %s' % (self.object.name, self.error))

    def _ensure_ready(self):
        if self._ready:
            return True
        if not self.object.channels:
            return False
        for item in self.entries:
            channel = self.object.channels[item['bone']]
            if self.object.constraints[item['bone'] + ':' + item['constraint'].name] != item['constraint']:
                raise ValueError('Constraint não pertence ao canal configurado')
            item['channel'] = channel
        self._root = min(self.entries, key=lambda item: self._bone_depth(item['channel'].bone))
        self._ready = True
        return True

    @staticmethod
    def _bone_depth(bone):
        depth = 0
        while bone.parent:
            depth += 1
            bone = bone.parent
        return depth

    def _validate(self):
        for obj in (self.controller, self.anchor, self.velocity_source):
            if obj is not None and obj.invalid:
                raise ValueError('Controlador, âncora ou fonte de velocidade removida')
        target = self.anchor if self.mode == 'ANCHOR' else self.controller
        if not self._finite_transform(self.world_transform(target)):
            raise ValueError('Transformação da âncora/controlador inválida ou escala não uniforme')
        for item in self.entries:
            if item['body'].invalid or item['pivot'].invalid:
                raise ValueError('Corpo/pivô removido')
            if item['pivot'].parent != item['body'] or item['constraint'].target != item['pivot']:
                raise ValueError('Vínculo de ragdoll alterado durante execução')

    def _pose_matrices(self):
        if self._recovered_time == Range.logic.getFrameTime():
            return self._recovered_pose
        return {item['bone']: item['channel'].pose_matrix.copy() for item in self.entries}

    def _align(self, matrices):
        poses = [(item['body'], self.world_transform(self.object) * matrices[item['bone']] * item['offset'])
                 for item in self.entries]
        if any(not all(math.isfinite(value) for row in pose for value in row) for _, pose in poses):
            raise ValueError('Pose inválida (NaN/Inf); alinhamento interrompido')
        for body, pose in poses:
            body.worldTransform = pose
            body.worldLinearVelocity = (0, 0, 0)
            body.worldAngularVelocity = (0, 0, 0)

    def activate(self, velocity_source=None):
        if not self.is_valid:
            return False
        try:
            if not self._ensure_ready():
                return False
            if self.active:
                return True
            if velocity_source is not None:
                self.velocity_source = velocity_source
            self._validate()
            if self.object.parent and self.mode == 'FREE' and self.object.parent != self.controller:
                raise ValueError('Armature FREE deve estar vinculada ao controlador configurado')
            parent = self.object.parent
            world = self.world_transform(self.object)
            anchor_local = (self.world_transform(self.anchor).inverted() * world
                            if self.mode == 'ANCHOR' else None)
            self._initial = dict(parent=parent, world=world, anchor_local=anchor_local,
                                 matrices=self._pose_matrices(),
                                 poses=[(item['channel'], tuple(item['channel'].location),
                                         tuple(item['channel'].scale), tuple(item['channel'].rotation_quaternion),
                                         tuple(item['channel'].rotation_euler)) for item in self.entries])
            if self.mode == 'FREE':
                self._initial['controller'] = self.world_transform(self.controller)
                self._initial['rig_local'] = self.world_transform(self.controller).inverted() * world
            self._align(self._initial['matrices'])
            source = self.velocity_source
            physical_source = source is not None and source.getPhysicsId()
            linear = source.getLinearVelocity() if physical_source else Vector((0, 0, 0))
            angular = source.getAngularVelocity() if physical_source else Vector((0, 0, 0))
            origin = self.world_transform(source).translation if source else world.translation
            self._initial['root_head'] = self.world_transform(self._root['pivot']).translation
            if self.mode == 'FREE':
                self.controller.suspendPhysics()
            self.object.removeParent()
            self.object.worldTransform = world
            for layer in range(8):
                if self.object.isPlayingAction(layer):
                    self.object.stopAction(layer)
            for item in self.entries:
                item['constraint'].enforce = 1.0
                body = item['body']
                body.restorePhysics()
                radius = self.world_transform(body).translation - origin
                body.worldLinearVelocity = linear * self.linear_inheritance + angular.cross(radius) * self.angular_inheritance
                body.worldAngularVelocity = angular * self.angular_inheritance
            self.active = True
            self.object['active_ragdoll'] = True
            self._started_at = Range.logic.getFrameTime()
            self.blocked_reason = ''
            return True
        except Exception as exc:
            self._fail(exc)
            return False

    @staticmethod
    def _aabb(obj, transform):
        box = obj.cullingBox
        lower, upper = box.min, box.max
        points = [transform * Vector((x, y, z)) for x in (lower.x, upper.x)
                  for y in (lower.y, upper.y) for z in (lower.z, upper.z)]
        return (Vector(tuple(min(p[axis] for p in points) for axis in range(3))),
                Vector(tuple(max(p[axis] for p in points) for axis in range(3))))

    def _free_destination(self):
        controller = self.controller
        head = self.world_transform(self._root['pivot']).translation
        hit, point, normal = controller.rayCast(head - Vector((0, 0, 10)),
                                               head + Vector((0, 0, 2)), 0.0, '', 0, 1, 0,
                                               0xFFFF ^ BODY_GROUP)
        if hit is None or normal.z < 0.7:
            self.blocked_reason = 'Sem chão suficientemente plano para recuperar (%r, %s, %r)' % (
                tuple(head), hit.name if hit else 'sem hit', tuple(normal) if normal else None)
            return None
        yaw = self._initial['controller'].to_euler().z
        candidate = Matrix.Rotation(yaw, 4, 'Z')
        # Preserva escala do colisor e orientação vertical; não gira o corpo pelo impacto.
        for axis, scale in enumerate(self._initial['controller'].to_scale()):
            for row in range(3):
                candidate[row][axis] *= scale
        position = self._initial['controller'].translation.copy()
        position.x += head.x - self._initial['root_head'].x
        position.y += head.y - self._initial['root_head'].y
        candidate.translation = position
        lower, upper = self._aabb(controller, candidate)
        candidate.translation.z += point.z + 0.1 - lower.z
        return candidate

    def _destination_clear(self, candidate):
        lower, upper = self._aabb(self.controller, candidate)
        ignored = {self.object, self.controller}
        ignored.update(item['body'] for item in self.entries)
        ignored.update(item['pivot'] for item in self.entries)
        for other in self.object.scene.objects:
            if other in ignored or not other.getPhysicsId():
                continue
            if not other.meshes:
                self.blocked_reason = 'Não foi possível validar o volume de ' + other.name
                return False
            a, b = self._aabb(other, self.world_transform(other))
            if all(lower[i] < b[i] + 0.04 and upper[i] > a[i] - 0.04 for i in range(3)):
                self.blocked_reason = 'Volume de retorno ocupado por ' + other.name
                return False
        return True

    @staticmethod
    def _finite_transform(matrix):
        if (len(matrix) != 4 or not all(math.isfinite(value) for row in matrix for value in row)
                or matrix.determinant() <= 0.0):
            return False
        scale = matrix.to_scale()
        if min(scale) <= 1e-6 or max(scale) - min(scale) > max(scale) * 1e-4:
            return False
        axes = [matrix.col[i].to_3d().normalized() for i in range(3)]
        return not any(abs(axes[i].dot(axes[j])) > 1e-4 for i in range(3) for j in range(i + 1, 3))

    def recover(self, destination=None):
        """FREE: destination é matriz do controlador; ANCHOR: matriz da armature."""
        if not self.is_valid:
            return False
        if not self.active:
            return True
        try:
            self._validate()
            initial = self._initial
            if self.mode == 'ANCHOR':
                target = destination if destination is not None else self.world_transform(self.anchor) * initial['anchor_local']
                rig_target = target
            else:
                target = destination if destination is not None else self._free_destination()
                if target is None:
                    return False
                if not self._finite_transform(target):
                    self.blocked_reason = 'Matriz de destino inválida'
                    return False
                if not self._destination_clear(target):
                    return False
                rig_target = target * initial['rig_local']
            if not self._finite_transform(rig_target):
                self.blocked_reason = 'Matriz de retorno inválida'
                return False
            if self.recovery_validator and not self.recovery_validator(self, rig_target):
                self.blocked_reason = 'Destino recusado pelo jogo'
                return False
            # Somente após todas as validações começa a transição de retorno.
            for item in self.entries:
                item['body'].suspendPhysics()
                item['constraint'].enforce = 0.0
            if self.mode == 'FREE':
                self.controller.worldTransform = target
                self.controller.worldLinearVelocity = (0, 0, 0)
                self.controller.worldAngularVelocity = (0, 0, 0)
            parent = self.anchor if self.mode == 'ANCHOR' else self.controller
            self.object.setParent(parent, False, False)
            self.object.worldTransform = rig_target
            for channel, location, scale, quaternion, euler in initial['poses']:
                channel.location, channel.scale = location, scale
                channel.rotation_quaternion, channel.rotation_euler = quaternion, euler
            self.object.update()
            self._align(initial['matrices'])
            if self.mode == 'FREE':
                self.controller.restorePhysics()
            self.active = False
            self._recovered_time = Range.logic.getFrameTime()
            self._recovered_pose = initial['matrices']
            self.object['active_ragdoll'] = False
            self.blocked_reason = ''
            if self.on_recovered:
                try:
                    self.on_recovered(self)
                except Exception as exc:
                    print('[Anastacio Ragdoll] callback de recuperação: ' + str(exc))
            return True
        except Exception as exc:
            self._fail(exc)
            return False

    def set_active(self, active, velocity_source=None):
        return self.activate(velocity_source) if active else self.recover()

    def update(self):
        if not self.is_valid:
            return
        try:
            if not self._ensure_ready():
                return
            requested = bool(self.object.get('active_ragdoll', self.active))
            if requested != self.active:
                if not self.set_active(requested):
                    self.object['active_ragdoll'] = self.active
            if self.active:
                self.object.update()
                now = Range.logic.getFrameTime()
                if self.auto_recover and now - self._started_at >= self.recovery_delay and now >= self._retry_at:
                    self._retry_at = now + 1.0
                    self.recover()
        except Exception as exc:
            self._fail(exc)
