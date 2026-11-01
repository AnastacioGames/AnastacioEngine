"""Personagem automático (docs/personagem-auto-rig-plan.md), etapa 1: alinhar a malha do Fuse à base.

Antes de copiar pesos, a malha nova precisa estar de pé, de frente para o mesmo lado da armature base e
na mesma unidade (metros). Esta parte mede e corrige isso; nada aqui depende de janela.
"""

import math

from mathutils import Matrix, Vector

# Peças do Fuse que não contam na altura do corpo.
ACCESSORIES = {"hair", "hats", "hat", "eyewear", "masks", "mask"}

# Direções de frente possíveis no chão (o personagem já está de pé em Z).
_DIRS = {"+Y": Vector((0, 1, 0)), "-Y": Vector((0, -1, 0)), "+X": Vector((1, 0, 0)), "-X": Vector((-1, 0, 0))}


def world_verts(objects):
    return [o.matrix_world * v.co for o in objects if o.type == 'MESH' for v in o.data.vertices]


def bounds(verts):
    mn = Vector((min(v[i] for v in verts) for i in range(3)))
    mx = Vector((max(v[i] for v in verts) for i in range(3)))
    return mn, mx


def _feet_vs_shin(verts, axis, mn, height):
    """Pés (0-4 % da altura) comparados com o centro da canela (12-18 %): a ponta do pé passa mais para a
    frente do que o calcanhar para trás. >0: frente no sentido + do eixo."""
    shin = [v[axis] for v in verts if mn.z + 0.12 * height <= v.z <= mn.z + 0.18 * height]
    feet = [v[axis] for v in verts if v.z <= mn.z + 0.04 * height]
    if not shin or not feet:
        return 0.0
    c = sum(shin) / len(shin)
    return (max(feet) - c) + (min(feet) - c)


def mesh_front(objects):
    """Frente da malha em T. Retorna (direção, confiança relativa à altura).

    O eixo dos braços abertos (o mais largo) é o lado; a frente está no outro eixo. Sinal principal: a peça
    "Eyes" do Fuse à frente do centro da cabeça. Sem olhos: ponta dos pés à frente da canela."""
    verts = world_verts(objects)
    mn, mx = bounds(verts)
    size = mx - mn
    height = size.z
    axis = 1 if size.x >= size.y else 0
    eyes = [o for o in objects if o.type == 'MESH' and o.name.split(".")[0].lower() == "eyes"]
    if eyes:
        ev = world_verts(eyes)
        eye_c = sum(v[axis] for v in ev) / len(ev)
        head = [v[axis] for v in verts if v.z >= mn.z + 0.85 * height]
        diff = eye_c - (min(head) + max(head)) / 2.0
        if abs(diff) > 0.01 * height:
            return ("+" if diff > 0 else "-") + "XY"[axis], abs(diff) / height
    score = _feet_vs_shin(verts, axis, mn, height)
    return ("+" if score > 0 else "-") + "XY"[axis], abs(score) / max(height, 1e-6)


def armature_front(arm, toe="mixamorig:LeftToeBase", foot="mixamorig:LeftFoot"):
    """Frente da armature: direção do pé até a ponta do dedo, no chão."""
    bones = arm.data.bones
    start = bones[foot].head_local if foot in bones else None
    end = bones[toe].tail_local if toe in bones else None
    if start is None or end is None:
        raise ValueError("armature sem %s/%s para achar a frente" % (foot, toe))
    d = arm.matrix_world.to_3x3() * (end - start)
    d.z = 0.0
    return max(_DIRS, key=lambda k: _DIRS[k].dot(d))


def armature_height(arm, head="mixamorig:Head"):
    bones = arm.data.bones
    return (arm.matrix_world * bones[head].tail_local).z if head in bones else None


def unit_scale(height):
    """Fator para metros pela altura: Fuse/Mixamo exportam em centímetros (~100x)."""
    if height > 20.0:
        return 0.01
    if height < 0.05:
        return 100.0
    return 1.0


def is_upright(objects):
    mn, mx = bounds(world_verts(objects))
    s = mx - mn
    return s.z >= max(s.x, s.y) * 0.6 or s.z >= min(s.x, s.y) * 3.0


def align_to_base(objects, base_arm, match_height=True, report=print):
    """Põe as peças de pé, em metros, com o pé no chão, centradas, de frente para o lado da base e,
    com match_height, na mesma altura da base.

    Aplica a transformação nas malhas (escala 1, rotação 0). Retorna um dicionário com o que mudou."""
    out = {}
    # De pé: o OBJ do Fuse é Y-up; o importador do Blender já gira, mas um OBJ importado sem isso fica deitado.
    if not is_upright(objects):
        rot = Matrix.Rotation(math.radians(90.0), 4, 'X')
        for o in objects:
            o.matrix_world = rot * o.matrix_world
        out["deitado"] = True
    _transform(objects, Matrix.Identity(4))
    # De cabeça para baixo: em pose T os braços (fatia mais larga) ficam na metade de cima.
    if _widest_slice(world_verts(objects)) < 0.5:
        _transform(objects, Matrix.Rotation(math.pi, 4, 'Y'))
        out["virou_de_cabeca"] = True

    verts = world_verts(objects)
    mn, mx = bounds(verts)
    factor = unit_scale(mx.z - mn.z)
    if factor != 1.0:
        _transform(objects, Matrix.Scale(factor, 4))
        out["escala"] = factor

    front, conf = mesh_front(objects)
    target = armature_front(base_arm)
    out["frente_malha"], out["frente_base"], out["confianca"] = front, target, round(conf, 3)
    if front != target:
        a, b = _DIRS[front], _DIRS[target]
        angle = math.atan2(a.x * b.y - a.y * b.x, a.dot(b))
        _transform(objects, Matrix.Rotation(angle, 4, 'Z'))
        out["girou_graus"] = round(math.degrees(angle))
    if conf < 0.02:
        report("aviso: frente da malha incerta (%.3f); confira se o personagem olha para %s" % (conf, target))

    # Pé no chão e centro do quadril em X/Y = 0, como a base.
    mn, mx = bounds(world_verts(objects))
    _transform(objects, Matrix.Translation(Vector(((-(mn.x + mx.x) / 2), -(mn.y + mx.y) / 2, -mn.z))))
    mn, mx = bounds(world_verts(objects))
    base_h = armature_height(base_arm)
    # A altura é a do corpo: cabelo, chapéu, óculos e máscara ficam de fora (um penteado alto não encolhe ninguém).
    core = [o for o in objects if o.name.split(".")[0].lower() not in ACCESSORIES] or objects
    cmn, cmx = bounds(world_verts(core))
    if base_h:
        out["altura_base"] = round(base_h, 3)
        # Todos os personagens com a altura da base (pé no chão fica no lugar).
        if match_height and abs((cmx.z - cmn.z) - base_h) > 0.001:
            out["altura_original"] = round(cmx.z - cmn.z, 3)
            _transform(objects, Matrix.Scale(base_h / (cmx.z - cmn.z), 4))
            cmn, cmx = bounds(world_verts(core))
    out["altura"] = round(cmx.z - cmn.z, 3)
    return out


def _widest_slice(verts, slices=20):
    """Altura relativa (0 = pé, 1 = topo) da fatia horizontal mais larga."""
    mn, mx = bounds(verts)
    h = max(mx.z - mn.z, 1e-6)
    side = 0 if (mx.x - mn.x) >= (mx.y - mn.y) else 1
    lo = [float("inf")] * slices
    hi = [float("-inf")] * slices
    for v in verts:
        i = min(int((v.z - mn.z) / h * slices), slices - 1)
        lo[i] = min(lo[i], v[side])
        hi[i] = max(hi[i], v[side])
    widths = [b - a if b >= a else 0.0 for a, b in zip(lo, hi)]
    return (widths.index(max(widths)) + 0.5) / slices


def _transform(objects, matrix):
    for o in objects:
        o.data.transform(matrix * o.matrix_world)
        o.matrix_world = Matrix.Identity(4)
        o.data.update()

