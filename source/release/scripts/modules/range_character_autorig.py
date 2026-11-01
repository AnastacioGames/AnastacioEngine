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


def align_to_base(objects, base_arm, match_height=True, base_height=None, report=print):
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
    base_h = base_height or base_arm.get("autorig_height") or armature_height(base_arm)
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



# -- Base (rig do Mixamo) ---------------------------------------------------------------------------------

END_BONES = ("HeadTop_End", "Toe_End", "Thumb4", "Index4", "Middle4", "Ring4", "Pinky4")


def load_base(fbx_path, drop=(), front="+Y"):
    """Importa o FBX do Mixamo (T-pose, With Skin) e devolve (armature, malhas) com transformações aplicadas.

    Tira os ossos de ponta (sem pesos) e junta as peças numa malha só, usada como fonte dos pesos."""
    import bpy
    scene = bpy.context.scene
    before = set(scene.objects)
    bpy.ops.import_scene.fbx(filepath=fbx_path)
    new = [o for o in scene.objects if o not in before]
    arm = next(o for o in new if o.type == 'ARMATURE')
    meshes = [o for o in new if o.type == 'MESH']
    for o in scene.objects:
        o.select = o in new
    scene.objects.active = arm
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    # Frente igual à dos personagens do jogo (+Y, como os pilotos do RolimaRacer): o Mixamo vem em -Y.
    current = armature_front(arm)
    if current != front:
        a, b = _DIRS[current], _DIRS[front]
        angle = math.atan2(a.x * b.y - a.y * b.x, a.dot(b))
        rot = Matrix.Rotation(angle, 4, 'Z')
        for o in new:
            o.matrix_world = rot * o.matrix_world
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    # Ossos de ponta: não deformam nada.
    bpy.ops.object.mode_set(mode='EDIT')
    for b in list(arm.data.edit_bones):
        if b.name.endswith(END_BONES):
            arm.data.edit_bones.remove(b)
    bpy.ops.object.mode_set(mode='OBJECT')
    # Altura do corpo sem acessórios, medida antes de juntar (depois as peças perdem o nome).
    scene.update()
    core = [o for o in meshes if o.name.split(".")[0].lower() not in ACCESSORIES] or meshes
    cmn, cmx = bounds(world_verts(core))
    arm["autorig_height"] = cmx.z - cmn.z
    # Peças que não entram na fonte dos pesos (ex.: olhos e cílios na biblioteca).
    for o in [o for o in meshes if o.name.split(".")[0].lower() in drop]:
        meshes.remove(o)
        bpy.data.objects.remove(o, do_unlink=True)
    for o in scene.objects:
        o.select = o in meshes
    scene.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    source = scene.objects.active
    source.name = "AutoRigSource"
    scene.update()
    return arm, source


# -- Encaixe do esqueleto ---------------------------------------------------------------------------------

def _half_span(objects):
    core = [o for o in objects if o.name.split(".")[0].lower() not in ACCESSORIES] or objects
    return max(abs(v.x) for v in world_verts(core))


def fit_skeleton(arm, base_source, objects):
    """Copia a armature base e estica os braços para a envergadura da malha nova (pose T, braços em X).

    Altura já igualada em align_to_base. Erro medido contra o rig do Mixamo do Fabio: 2,3 cm em média."""
    import bpy
    scene = bpy.context.scene
    new_arm = arm.copy()
    new_arm.data = arm.data.copy()
    scene.objects.link(new_arm)
    base_span = _half_span([base_source])
    new_span = _half_span(objects)
    for o in scene.objects:
        o.select = o is new_arm
    scene.objects.active = new_arm
    bpy.ops.object.mode_set(mode='EDIT')
    eb = new_arm.data.edit_bones
    for side in ("Left", "Right"):
        upper = eb.get("mixamorig:%sArm" % side)
        if upper is None:
            continue
        sh = abs(upper.head.x)
        k = (new_span - sh) / max(base_span - sh, 1e-6)
        for b in eb:
            n = b.name
            if side not in n or not any(t in n for t in ("Arm", "Hand")):
                continue
            for p in (b.head, b.tail):
                s = 1.0 if p.x > 0 else -1.0
                if abs(p.x) > sh:
                    p.x = s * (sh + (abs(p.x) - sh) * k)
    bpy.ops.object.mode_set(mode='OBJECT')
    return new_arm


# -- Pesos ------------------------------------------------------------------------------------------------

def transfer_weights(base_source, objects, arm, max_bones=4):
    """Pesos da malha base para cada peça e liga na armature nova.

    Para cada vértice: ponto mais próximo na malha base (BVH), pesos dos cantos da face misturados pelo
    inverso da distância a cada canto. Fica com os max_bones ossos mais fortes, normalizados."""
    from mathutils.bvhtree import BVHTree
    src = base_source.data
    names = {g.index: g.name for g in base_source.vertex_groups}
    bones = set(b.name for b in arm.data.bones)
    src_w = [{names[g.group]: g.weight for g in v.groups if g.weight > 0.0 and names[g.group] in bones}
             for v in src.vertices]
    mw = base_source.matrix_world
    verts = [mw * v.co for v in src.vertices]
    polys = [tuple(p.vertices) for p in src.polygons]
    tree = BVHTree.FromPolygons(verts, polys)
    for o in objects:
        for g in list(o.vertex_groups):
            o.vertex_groups.remove(g)
        groups = {}
        for v in o.data.vertices:
            co = o.matrix_world * v.co
            hit, _normal, index, _dist = tree.find_nearest(co)
            if hit is None:
                continue
            acc = {}
            total = 0.0
            for vi in polys[index]:
                k = 1.0 / max((verts[vi] - hit).length, 1e-5)
                total += k
                for name, w in src_w[vi].items():
                    acc[name] = acc.get(name, 0.0) + w * k
            best = sorted(acc.items(), key=lambda x: -x[1])[:max_bones]
            norm = sum(w for _n, w in best)
            if norm <= 0.0:
                continue
            for name, w in best:
                g = groups.get(name)
                if g is None:
                    g = groups[name] = o.vertex_groups.new(name)
                g.add([v.index], w / norm, 'REPLACE')
        o.parent = arm
        m = o.modifiers.new("Armature", 'ARMATURE')
        m.object = arm
    return objects


# -- Biblioteca de esqueletos -----------------------------------------------------------------------------
#
# datafiles/characters/<id>/base.range: só a armature e "WeightProxy" (malha simplificada, sem textura, que
# serve apenas de fonte dos pesos). base.json: {"name", "bones", "order"}. Pastas extras do usuário entram
# por extra_dirs.

LIBRARY_DIR = "characters"


def library_dirs(extra_dirs=()):
    """Pastas da biblioteca: a do usuário, a local (ao lado do exe) e a do sistema, mais extra_dirs."""
    import os
    import bpy
    dirs = []
    for kind in ('USER', 'LOCAL', 'SYSTEM'):
        root = bpy.utils.resource_path(kind)
        if root:
            path = os.path.join(root, "datafiles", LIBRARY_DIR)
            if path not in dirs:
                dirs.append(path)
    dirs.extend(extra_dirs)
    return dirs


def list_skeletons(extra_dirs=()):
    """[(id, nome, pasta)] em ordem: primeiro "order" do base.json, depois o nome."""
    import json
    import os
    found = {}
    for root in library_dirs(extra_dirs):
        if not root or not os.path.isdir(root):
            continue
        for sid in sorted(os.listdir(root)):
            folder = os.path.join(root, sid)
            info = os.path.join(folder, "base.json")
            if os.path.isfile(info) and os.path.isfile(os.path.join(folder, "base.range")):
                with open(info, encoding="utf-8") as f:
                    data = json.load(f)
                found[sid] = (data.get("order", 99), data.get("name", sid), folder)
    return [(sid, name, folder) for sid, (_o, name, folder) in sorted(found.items(), key=lambda x: (x[1][0], x[1][1]))]


def load_library_base(folder):
    """Traz a armature e a WeightProxy de uma base da biblioteca para a cena. Retorna (armature, proxy)."""
    import os
    import bpy
    path = os.path.join(folder, "base.range")
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.objects = list(src.objects)
    scene = bpy.context.scene
    arm = proxy = None
    for o in dst.objects:
        if o is None:
            continue
        scene.objects.link(o)
        if o.type == 'ARMATURE':
            arm = o
        elif o.type == 'MESH':
            proxy = o
    scene.update()
    return arm, proxy


def make_library_base(fbx_path, folder, name, order=99, target_faces=6000):
    """Gera datafiles/characters/<id>/ a partir do FBX do Mixamo (T-pose, With Skin)."""
    import json
    import os
    import bpy
    arm, src = load_base(fbx_path, drop=("eyes", "eyelashes"))
    scene = bpy.context.scene
    for o in scene.objects:
        o.select = o is src
    scene.objects.active = src
    faces = len(src.data.polygons)
    if faces > target_faces:
        dec = src.modifiers.new("Decimate", 'DECIMATE')
        dec.ratio = target_faces / float(faces)
        bpy.ops.object.modifier_apply(modifier=dec.name)
    for m in list(src.modifiers):
        src.modifiers.remove(m)
    src.data.materials.clear()
    while src.data.uv_textures:
        src.data.uv_textures.remove(src.data.uv_textures[0])
    src.name = src.data.name = "WeightProxy"
    src.parent = arm
    src.matrix_parent_inverse.identity()
    arm.name = "Armature"
    arm.data.name = "Armature"
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "base.range")
    bpy.data.libraries.write(path, {arm, src}, fake_user=False)
    info = {"name": name, "order": order, "bones": len(arm.data.bones),
            "height": round(arm["autorig_height"], 4), "faces": len(src.data.polygons)}
    with open(os.path.join(folder, "base.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=1)
    return info
