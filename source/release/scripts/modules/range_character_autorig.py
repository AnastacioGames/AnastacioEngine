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
    ragdoll_sizes_from_mesh(arm, src)
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


# -- Ragdoll ----------------------------------------------------------------------------------------------
#
# Usa o addon Anastacio Ragdoll (caixas pelos ossos). Os tamanhos saem da WeightProxy uma vez só, ao gerar a
# biblioteca, e ficam guardados no esqueleto: na hora de criar o personagem a malha não é usada.

RAGDOLL_BONES = tuple("mixamorig:" + n for n in (
    "Hips", "Spine1", "Spine2", "Head",
    "LeftArm", "LeftForeArm", "RightArm", "RightForeArm",
    "LeftUpLeg", "LeftLeg", "LeftFoot", "RightUpLeg", "RightLeg", "RightFoot"))

# Formato dos pilotos do RolimaRacer (scripts/fix_ragdoll_collisions.py, camera_change.py).
GAME_RAGDOLL = {"collision_group": 3, "collision_mask": (1,), "part_mass": 2.0,
                "focus_bone": "mixamorig:Spine1", "focus_prop": "foco_camera_ragdoll", "names": "RagdollPart",
                # juntas e amortecimento iguais aos pilotos prontos (Fabio): o preset do addon (+-45/25) deixa mole
                "joint_limit": (0.0, 15.0), "damping": (0.04, 0.1)}


def stiffen_ragdoll(bodies, game=GAME_RAGDOLL):
    """Juntas Cone Twist de 0 a 15 graus em X/Y/Z e o amortecimento dos pilotos do jogo."""
    lo, hi = (math.radians(a) for a in game["joint_limit"])
    for body in bodies:
        body.game.damping, body.game.rotation_damping = game["damping"]
        for c in body.constraints:
            if c.type != 'RIGID_BODY_JOINT':
                continue
            for a in "xyz":
                setattr(c, "use_angular_limit_" + a, True)
                setattr(c, "limit_angle_min_" + a, lo)
                setattr(c, "limit_angle_max_" + a, hi)


def _ragdoll_addon():
    import addon_utils
    addon_utils.enable("anastacio_ragdoll", default_set=True)
    import anastacio_ragdoll
    return anastacio_ragdoll


def ragdoll_sizes_from_mesh(arm, mesh, bones=RAGDOLL_BONES, shrink=0.85):
    """Guarda no esqueleto (addon) o tamanho de cada caixa: vértices com esse osso como dominante, no espaço
    do osso (X largura, Z profundidade, Y comprimento)."""
    rd = _ragdoll_addon()
    rd.sync_bones(arm)
    names = {g.index: g.name for g in mesh.vertex_groups}
    inv_arm = arm.matrix_world.inverted()
    pts = {b: [] for b in bones}
    for v in mesh.data.vertices:
        if not v.groups:
            continue
        g = max(v.groups, key=lambda x: x.weight)
        name = names.get(g.group)
        if name in pts and g.weight > 0.5:
            pts[name].append(inv_arm * (mesh.matrix_world * v.co))
    for item in arm.anastacio_ragdoll.bones:
        item.enabled = item.name in bones
        if not item.enabled:
            continue
        bone = arm.data.bones[item.name]
        local = [bone.matrix_local.inverted() * p for p in pts[item.name]]
        if len(local) < 8:
            continue
        xs = [p.x for p in local]
        ys = [p.y for p in local]
        zs = [p.z for p in local]
        item.width = max(0.02, (max(xs) - min(xs)) * shrink)
        item.depth = max(0.02, (max(zs) - min(zs)) * shrink)
        cy = (max(ys) + min(ys)) / 2.0
        length = max(0.02, (max(ys) - min(ys)) * shrink)
        item.length_ratio = min(3.0, max(0.05, length / bone.length))
        item.offset = ((max(xs) + min(xs)) / 2.0, cy - bone.length * 0.5, (max(zs) + min(zs)) / 2.0)
    rd.apply_preset(arm)


def add_ragdoll(arm, game=GAME_RAGDOLL):
    """Gera as caixas, pivôs, constraints e juntas (addon) e aplica o formato do jogo, se houver."""
    import bpy
    rd = _ragdoll_addon()
    context = bpy.context
    for o in context.scene.objects:
        o.select = o is arm
    context.scene.objects.active = arm
    rd.generate(context, arm, runtime=False)
    created = rd.owned(arm)
    parts = rd.descriptors(arm)
    rd.prepare_physics(context, arm, created, parts)
    bodies = [o for o in created if o.anastacio_ragdoll_link.role == 'BODY']
    if not game:
        return bodies
    by_key = {p['key']: p['bone'] for p in parts}
    for body in bodies:
        bone = by_key[body.anastacio_ragdoll_link.key]
        body.game.collision_group = tuple(i == game["collision_group"] - 1 for i in range(16))
        body.game.collision_mask = tuple((i + 1) in game["collision_mask"] for i in range(16))
        body.game.mass = game["part_mass"]
        if bone == game["focus_bone"]:
            rd.game_property(context, body, game["focus_prop"], 0)
        if game.get("names"):
            pivot = next(c for c in body.children if c.anastacio_ragdoll_link.role == 'PIVOT')
            body.name = "%s-%s-%s-Dynamic" % (game["names"], arm.name, bone)
            pivot.name = "%s-%s-%s-Empty" % (game["names"], arm.name, bone)
    if game.get("joint_limit"):
        stiffen_ragdoll(bodies, game)
    return bodies


# -- Atlas (sem bake) -------------------------------------------------------------------------------------
#
# As peças do Fuse já têm UV 0-1 e uma textura cada: copia cada textura para uma célula de um atlas 2048 e
# reposiciona o UV. Olhos e cílios usam a textura do corpo e ficam na mesma célula.

BIG_PIECES = ("body",)            # 1/4 do atlas
LARGE_PIECES = ("tops", "bottoms")  # 1/4 se couber, senão 1/16


def _piece(o):
    return o.name.split(".")[0].lower()


def _slot_image(obj, kind):
    for mat in obj.data.materials:
        if mat is None:
            continue
        for s in mat.texture_slots:
            if s and s.texture and s.texture.type == 'IMAGE' and s.texture.image:
                if kind == "diffuse" and s.use_map_color_diffuse:
                    return s.texture.image
                if kind == "normal" and s.use_map_normal:
                    return s.texture.image
    return None


def _atlas_layout(keys, size):
    """keys = [(image, peça)] na ordem de prioridade. Retorna {image: (x, y, lado)} em pixels."""
    q = size // 2
    cell = size // 4
    big = [k for k in keys if k[1] in BIG_PIECES][:1]
    rest = [k for k in keys if k not in big]
    large = [k for k in rest if k[1] in LARGE_PIECES]
    small = [k for k in rest if k not in large]
    quads = [(0, 0), (q, 0), (0, q), (q, q)]
    layout = {}
    if big:
        layout[big[0][0]] = quads.pop(0) + (q,)
    # Peças grandes ganham um quadrante enquanto o resto ainda couber nas células de 1/16.
    while large and len(quads) * 4 - 4 >= len(small) + len(large) - 1:
        layout[large.pop(0)[0]] = quads.pop(0) + (q,)
    cells = [(qx + cx, qy + cy) for qx, qy in quads for cy in (0, cell) for cx in (0, cell)]
    for img, _p in large + small:
        if not cells:
            raise ValueError("peças demais para um atlas %d" % size)
        layout[img] = cells.pop(0) + (cell,)
    return layout


def _paste(dst, size, src, x, y, side, default):
    """Copia src redimensionada para (x, y, side) dentro de dst (lista RGBA de size*size)."""
    import bpy
    if src is None:
        for row in range(side):
            o = ((y + row) * size + x) * 4
            dst[o:o + side * 4] = default * side
        return
    tmp = src.copy()
    if tuple(tmp.size) != (side, side):
        tmp.scale(side, side)
    px = list(tmp.pixels)
    bpy.data.images.remove(tmp)
    for row in range(side):
        o = ((y + row) * size + x) * 4
        dst[o:o + side * 4] = px[row * side * 4:(row + 1) * side * 4]


def build_atlas(objects, out_dir, name, size=2048, normal=True, uv_name="UV_Atlas"):
    """Atlas de diffuse (com alfa) e normal, UV novo em cada peça, um material só. Salva PNGs em out_dir."""
    import os
    import bpy
    order = sorted(objects, key=lambda o: (_piece(o) not in BIG_PIECES, _piece(o) not in LARGE_PIECES, o.name))
    keys, img_of = [], {}
    for o in order:
        img = _slot_image(o, "diffuse")
        img_of[o] = img
        if img is not None and all(k[0] is not img for k in keys):
            keys.append((img, _piece(o)))
    layout = _atlas_layout(keys, size)
    maps = {"diffuse": [0.0] * (size * size * 4)}
    if normal:
        maps["normal"] = [0.0] * (size * size * 4)
    for img, _p in keys:
        x, y, side = layout[img]
        owner = next(o for o in order if img_of[o] is img)
        _paste(maps["diffuse"], size, img, x, y, side, [1.0, 1.0, 1.0, 1.0])
        if normal:
            _paste(maps["normal"], size, _slot_image(owner, "normal"), x, y, side, [0.5, 0.5, 1.0, 1.0])
    os.makedirs(out_dir, exist_ok=True)
    images = {}
    for kind, px in maps.items():
        im = bpy.data.images.new("%s_%s" % (name, kind), size, size, alpha=(kind == "diffuse"))
        im.pixels = px
        im.filepath_raw = os.path.join(out_dir, "%s_%s.png" % (name, kind))
        im.file_format = 'PNG'
        im.save()
        images[kind] = im
    # Material único (Blender Internal, como os pilotos do jogo); alfa por recorte só onde a textura tem alfa.
    mat = bpy.data.materials.new(name + "_mat")
    mat.specular_intensity = 0.1
    mat.use_transparency = True
    mat.alpha = 0.0
    mat.game_settings.alpha_blend = 'CLIP'
    for kind, im in images.items():
        tex = bpy.data.textures.new("%s_%s" % (name, kind), 'IMAGE')
        tex.image = im
        slot = mat.texture_slots.add()
        slot.texture = tex
        slot.texture_coords = 'UV'
        slot.uv_layer = uv_name
        if kind == "diffuse":
            slot.use_map_alpha = True
        else:
            tex.use_normal_map = True
            slot.use_map_color_diffuse = False
            slot.use_map_normal = True
            slot.normal_factor = 1.0
    for o in order:
        img = img_of[o]
        x, y, side = layout[img] if img is not None else (0, 0, 0)
        src_uv = o.data.uv_layers.active
        new = o.data.uv_textures.new(uv_name)
        dst_uv = o.data.uv_layers[uv_name]
        for a, b in zip(src_uv.data, dst_uv.data):
            b.uv = ((x + a.uv.x * side) / size, (y + a.uv.y * side) / size)
        o.data.uv_textures.active = new
        o.data.uv_textures[uv_name].active_render = True
        o.data.materials.clear()
        o.data.materials.append(mat)
    return mat, layout


def join_pieces(objects, name="Body"):
    """Junta as peças numa malha só (pesos e UV do atlas juntos). Retorna o objeto."""
    import bpy
    scene = bpy.context.scene
    for o in scene.objects:
        o.select = o in objects
    scene.objects.active = next(o for o in objects if _piece(o) == "body") if any(
        _piece(o) == "body" for o in objects) else objects[0]
    bpy.ops.object.join()
    body = scene.objects.active
    body.name = body.data.name = name
    # Só o UV do atlas fica (o UV original de cada peça já foi convertido).
    for uv in [u for u in body.data.uv_textures if u.name != "UV_Atlas"]:
        body.data.uv_textures.remove(uv)
    return body


# -- Personagem pronto (formato dos pilotos do RolimaRacer) -----------------------------------------------

FP_BONES = ("Head", "Neck")      # sempre na parte escondida em 1a pessoa
FP_HEIGHT = 0.62                 # e o resto acima desta fracao da altura (Fabio: 1,10 m de 1,77 m)
BODY_TRIS = 9000                 # o corpo do Fuse (20-26 mil) nao entra no jogo: o nivel 0 ja e reduzido
FP_TRIS = 6000                   # dos 9000, a parte de cima (cabeca e peito): rosto amassava com a reducao por igual
# (triangulos, distancia); Mestre Deen: 3450/1268/427. DESLIGADO: LOD de malha com armature em arquivo
# carregado por LibLoad aparece em pose T no jogo (sem deformacao); volta quando o motor for corrigido.
LOD_LEVELS = ()   # era ((2500, 10.0), (900, 25.0))
HIDDEN_LAYER = 1                 # camada 2: a cena mostra so a 1, como no RolimaRacer
GAME_COMPONENT = "scripts.VehicleSystem.ragdoll_system.ragdoll.Ragdoll"


def _select_only(obj):
    import bpy
    scene = bpy.context.scene
    for o in scene.objects:
        o.select = o is obj
    scene.objects.active = obj


def _tris(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def decimate_to(ob, tris):
    """Collapse (High Quality) ate ~tris triangulos; pesos e UV seguem. Nao faz nada se ja for menor."""
    import bpy
    ratio = tris / max(_tris(ob), 1)
    if ratio >= 1.0:
        return
    mod = ob.modifiers.new("Decimate", 'DECIMATE')
    mod.ratio = ratio
    if hasattr(mod, "use_collapse_quality"):
        mod.use_collapse_quality = True
    _select_only(ob)
    while ob.modifiers[0] != mod:
        bpy.ops.object.modifier_move_up(modifier=mod.name)
    bpy.ops.object.modifier_apply(modifier=mod.name)


def _decimated_copy(scene, src, tris, name):
    ob = src.copy()
    ob.data = src.data.copy()
    ob.name = ob.data.name = name
    scene.objects.link(ob)
    decimate_to(ob, tris)
    return ob


def split_fp_part(body, height):
    """Separa a cabeca e o alto do tronco (camera_hide_fp). Retorna (resto, parte_escondida)."""
    import bmesh
    import bpy
    names = {g.index: g.name.replace("mixamorig:", "") for g in body.vertex_groups}
    mw = body.matrix_world
    zmin = min((mw * v.co).z for v in body.data.vertices)
    limit = zmin + FP_HEIGHT * height
    hide = set()
    for v in body.data.vertices:
        if not v.groups:
            continue
        dom = names[max(v.groups, key=lambda g: g.weight).group]
        arm_side = any(k in dom for k in ("Arm", "Hand", "Thumb", "Index", "Middle", "Ring", "Pinky"))
        if dom in FP_BONES or ((mw * v.co).z > limit and not arm_side):
            hide.add(v.index)
    scene = bpy.context.scene
    _select_only(body)
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(body.data)
    for f in bm.faces:
        f.select = sum(1 for v in f.verts if v.index in hide) * 2 > len(f.verts)
    bmesh.update_edit_mesh(body.data)
    bpy.ops.mesh.separate(type='SELECTED')
    bpy.ops.object.mode_set(mode='OBJECT')
    part = next(o for o in scene.objects if o.select and o is not body)
    return body, part


def _prop(obj, name, value):
    import bpy
    _select_only(obj)
    if name not in obj.game.properties:
        kind = 'BOOL' if isinstance(value, bool) else ('FLOAT' if isinstance(value, float) else 'INT')
        bpy.ops.object.game_property_new(type=kind, name=name)
    obj.game.properties[name].value = value


def finish_pilot(arm, body, group_name, component=GAME_COMPONENT, report=print):
    """Malha em 2 partes + LOD + propriedades + componente + grupo, como GroupFabio."""
    import bpy
    scene = bpy.context.scene
    height = arm.get("autorig_height") or 1.7
    mat = body.data.materials[0]
    mat.name = group_name + "Material"
    mat.use_transparency = False
    mat.game_settings.alpha_blend = 'OPAQUE'
    # alpha 0 + alpha da textura deixava o corpo meio transparente no jogo; o cartao baixa o brilho so p/ a foto
    mat.alpha = 1.0
    mat.specular_intensity = 0.2       # brilho branco alto deixava o piloto esbranquicado (pista molhada)
    # metal 0,5 (padrao novo) refletia o ambiente no lugar da cor: piloto cinza-azulado e lavado no jogo
    mat.diffuse_metallic_bsdf = mat.specular_metallic_bsdf = 0.0
    mat.use_object_color = True        # como os pilotos prontos (o jogo pode tingir/esmaecer pelo obj.color)
    for ts in mat.texture_slots:
        if ts and ts.texture:
            ts.use_map_alpha = False
            if ts.use_map_normal and ts.texture.image:
                ts.texture.image.colorspace_settings.name = 'Non-Color'
    lods = [_decimated_copy(scene, body, r, "Bodylod%d%s" % (i, group_name))
            for i, (r, _d) in enumerate(LOD_LEVELS, 1)]
    rest, fp = split_fp_part(body, height)
    decimate_to(fp, FP_TRIS)
    decimate_to(rest, BODY_TRIS - FP_TRIS)
    rest.name = rest.data.name = "Body" + group_name
    fp.name = fp.data.name = "Body%s.001" % group_name
    for part in (rest, fp):
        _select_only(part)
        for _lod in lods:
            bpy.ops.object.lod_add()   # o primeiro também cria o nível 0 (a própria malha)
        for i, ((_ratio, dist), lod) in enumerate(zip(LOD_LEVELS, lods), 1):
            part.lod_levels[i].object = lod
            part.lod_levels[i].distance = dist
        # sem "aura_rain_effect": a aura da chuva cobre o corpo com agua e o deixa com cara de fantasma
        # (os pilotos prontos nao tem a propriedade)
        limit_head_weights(part, arm)
    _prop(fp, "camera_hide_fp", True)
    arm.name = "Armature" + group_name
    arm.game.physics_type = 'NO_COLLISION'
    arm.data.deform_method = 'BGE_GPU'   # skinning na GPU (cai para CPU sozinho se o material nao suportar)
    _prop(arm, "pilot.armature", False)
    _prop(arm, "active_ragdoll", False)
    if component:
        _select_only(arm)
        try:
            bpy.ops.logic.python_component_register(component_name=component)
        except Exception as exc:
            report("aviso: componente %s nao registrado (%s); anexe pelo painel Logic" % (component, exc))
    root = bpy.data.objects.new(group_name, None)
    scene.objects.link(root)
    root.empty_draw_size = 0.3
    _prop(root, "is_pilot", False)
    # Como os pilotos do jogo: so as pecas do ragdoll tem fisica. Malha STATIC (padrao do import) prende o
    # ragdoll dentro do proprio corpo e bate no carro.
    for o in [rest, fp, root] + lods:
        o.game.physics_type = 'NO_COLLISION'
    # Como no RolimaRacer.range: o grupo tem armature, corpo e ragdoll; os LOD ficam fora (o corpo os chama
    # pelo lod_levels; dentro do grupo o addObject criaria todos na tela) e o Empty instancia o grupo.
    grp = bpy.data.groups.new(group_name)
    members = [arm, rest, fp] + [o for o in scene.objects if o.name.startswith("RagdollPart-")]
    for o in members:
        grp.objects.link(o)
    root.dupli_type = 'GROUP'
    root.dupli_group = grp
    return grp



# -- Cartao do menu (foto do piloto) ---------------------------------------------------------------------

CARD_SIZE = (512, 1024)          # os cartoes do RolimaRacer sao 256x512 (corpo inteiro, fundo transparente)
PHOTO_SIZE = 256                 # foto do rosto no botao de escolha
CARD_POSE = ("RolimaRacer.range", "PLAYER_IDLE_CAPOEIRA 1_104", 50)   # ginga, como o cartao do Fabio   # (arquivo do jogo, acao, quadro)


def _pose_from_game(arm, game_root, pose=CARD_POSE):
    """Aplica um quadro de uma animacao do jogo (mesmos nomes mixamorig:). False se nao achar."""
    import os
    import bpy
    if not game_root:
        return False
    path = os.path.join(game_root, pose[0])
    if not os.path.isfile(path):
        return False
    with bpy.data.libraries.load(path) as (src, dst):
        if pose[1] not in src.actions:
            return False
        dst.actions = [pose[1]]
    act = dst.actions[0]
    names = {pb.name for pb in arm.pose.bones}
    for fc in act.fcurves:
        if not fc.data_path.startswith("pose.bones"):
            continue
        bone = fc.data_path.split('"')[1]
        prop = fc.data_path.rsplit(".", 1)[1]
        if bone not in names or prop == "location":   # posicao fica da armature do personagem
            continue
        pb = arm.pose.bones[bone]
        if prop == "rotation_quaternion":
            pb.rotation_mode = 'QUATERNION'
        elif prop == "rotation_euler":
            if pb.rotation_mode == 'QUATERNION':
                pb.rotation_mode = 'XYZ'
        if hasattr(pb, prop):
            getattr(pb, prop)[fc.array_index] = fc.evaluate(pose[2])
    bpy.data.actions.remove(act)
    return True


def _pose_arms_down(arm):
    """Sem jogo: abaixa os bracos da pose T."""
    for side in ("Left", "Right"):
        pb = arm.pose.bones.get("mixamorig:%sArm" % side)
        if not pb:
            continue
        d = (pb.tail - pb.head).normalized()
        target = Vector((d.x * 0.3, 0.05, -0.95)).normalized()
        q = d.rotation_difference(target)
        m = pb.matrix.copy()
        pb.matrix = Matrix.Translation(m.to_translation()) * q.to_matrix().to_4x4() *             Matrix.Translation(-m.to_translation()) * m


def limit_head_weights(mesh, arm, margin=0.02,
                       chain=(("mixamorig:Head", "mixamorig:Neck"), ("mixamorig:Neck", "mixamorig:Spine2"))):
    """Peso da cabeca so acima da base dela, peso do pescoco so acima da base dele (o resto vai para o osso
    de baixo). A transferencia de pesos espalhava a cabeca no pescoco e nos ombros: ao girar a cabeca
    (head_look, camera de lado) eles torciam junto."""
    to_arm = arm.matrix_world.inverted() * mesh.matrix_world
    groups = {g.name: g for g in mesh.vertex_groups}
    for bone_name, lower_name in chain:
        bone = arm.data.bones.get(bone_name)
        g, low = groups.get(bone_name), groups.get(lower_name)
        if not bone or not g or not low:
            continue
        floor = bone.head_local.z - margin
        for v in mesh.data.vertices:
            if (to_arm * v.co).z >= floor:
                continue
            w = next((e.weight for e in v.groups if e.group == g.index), 0.0)
            if w <= 0.0:
                continue
            g.remove([v.index])
            low.add([v.index], w, 'ADD')


SEAT_POSE = ("RolimaRacer.range", "CARRO_Main_drive_position", 1)


def bake_seat_pose(arm, game_root, pose=SEAT_POSE):
    """Grava nos ossos a pose sentada do jogo (rotacao e posicao, como os pilotos prontos foram salvos).
    No jogo a action de base ja esteve mutada: sem isto o piloto ficava em pose T. Le as curvas mesmo mutadas."""
    import os
    import bpy
    if not game_root or not os.path.isfile(os.path.join(game_root, pose[0])):
        return False
    with bpy.data.libraries.load(os.path.join(game_root, pose[0])) as (src, dst):
        if pose[1] not in src.actions:
            return False
        dst.actions = [pose[1]]
    act = dst.actions[0]
    names = {pb.name for pb in arm.pose.bones}
    for fc in act.fcurves:
        if not fc.data_path.startswith("pose.bones"):
            continue
        bone = fc.data_path.split('"')[1]
        prop = fc.data_path.rsplit(".", 1)[1]
        if bone not in names or not hasattr(arm.pose.bones[bone], prop):
            continue
        pb = arm.pose.bones[bone]
        if prop == "rotation_quaternion":
            pb.rotation_mode = 'QUATERNION'
        getattr(pb, prop)[fc.array_index] = fc.evaluate(pose[2])
    bpy.data.actions.remove(act)
    return True


def render_card(arm, meshes, path, game_root=None, size=CARD_SIZE, photo_path=None, report=print):
    """Foto do corpo inteiro em pose, luz Sun, fundo transparente (cartao do menu de escolha)."""
    import bpy
    scene = bpy.context.scene
    if not _pose_from_game(arm, game_root):
        report("cartao: animacao do jogo nao encontrada, pose manual")
        _pose_arms_down(arm)
    scene.update()
    pts = [o.matrix_world * v.co for o in meshes for v in o.to_mesh(scene, True, 'RENDER').vertices]
    zmin = min(p.z for p in pts)
    zmax = max(p.z for p in pts)
    h = zmax - zmin
    ang = math.radians(25)             # 3/4, o personagem olha para +Y
    right = Vector((-math.cos(ang), math.sin(ang), 0.0))   # eixo X da camera
    xs = [p.dot(right) for p in pts]
    w = max(xs) - min(xs)
    mid = (max(xs) + min(xs)) / 2
    cam_data = bpy.data.cameras.new("CardCam")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = max(h, w * size[1] / size[0]) * 1.08   # cabe em pe e com os bracos abertos
    cam = bpy.data.objects.new("CardCam", cam_data)
    scene.objects.link(cam)
    dist = 10.0
    c = right * mid
    cam.location = (c.x + dist * math.sin(ang), c.y + dist * math.cos(ang), zmin + h / 2)
    cam.rotation_euler = (math.radians(90), 0, math.radians(180) - ang)
    sun_data = bpy.data.lamps.new("CardSun", 'SUN')
    sun_data.energy = 1.1
    sun = bpy.data.objects.new("CardSun", sun_data)
    scene.objects.link(sun)
    sun.rotation_euler = (math.radians(-55), math.radians(-25), math.radians(20))
    world = scene.world or bpy.data.worlds.new("CardWorld")
    scene.world = world
    world.ambient_color = (0.12, 0.12, 0.13)
    for o in meshes:
        for m in o.data.materials:
            if m:
                m.ambient = 1.0
                m.specular_intensity = 0.1
    r = scene.render
    r.engine = 'BLENDER_RENDER'
    r.resolution_x, r.resolution_y = size
    r.resolution_percentage = 100
    r.alpha_mode = 'TRANSPARENT'
    r.image_settings.file_format = 'PNG'
    r.image_settings.color_mode = 'RGBA'
    r.use_antialiasing = True
    scene.view_settings.view_transform = 'Default'   # cor como no jogo (2.79 abre em Filmic)
    scene.camera = cam
    for ob in (cam, sun):
        ob.layers = meshes[0].layers
    r.filepath = path
    bpy.ops.render.render(write_still=True)
    # foto do botao (rosto, quadrada): cabeca reta (a ginga tomba a cabeca), quase de frente e mais clara,
    # como as fotos dos pilotos antigos
    fill = None
    head = next((pb for pb in arm.pose.bones if pb.name.endswith("Head")), None)
    if head and photo_path:
        _rest_pose(arm)
        _pose_arms_down(arm)
        scene.update()
        ang = math.radians(12)
        hc = arm.matrix_world * head.head + Vector((0, 0, 0.06))
        cam_data.ortho_scale = 0.46
        cam.location = (hc.x + dist * math.sin(ang), hc.y + dist * math.cos(ang), hc.z)
        cam.rotation_euler = (math.radians(90), 0, math.radians(180) - ang)
        # ambiente cinza lava a cor; Sun + Hemi multiplicam a cor da pele e mantem a saturacao
        sun_data.energy = 1.0
        sun.rotation_euler = (math.radians(70), 0, math.radians(160))   # de cima e da frente (+Y), um pouco de lado
        fill_data = bpy.data.lamps.new("CardFill", 'HEMI')
        fill_data.energy = 0.55
        fill = bpy.data.objects.new("CardFill", fill_data)
        scene.objects.link(fill)
        fill.layers = meshes[0].layers
        fill.rotation_euler = (math.radians(90), 0, math.radians(180))   # vem da camera (+Y)
        world.ambient_color = (0.03, 0.03, 0.03)
        r.resolution_x = r.resolution_y = PHOTO_SIZE
        r.filepath = photo_path
        bpy.ops.render.render(write_still=True)
    for ob in (cam, sun, fill):
        if ob is None:
            continue
        bpy.data.objects.remove(ob, do_unlink=True)
    _rest_pose(arm)
    scene.update()
    return path


def _rest_pose(arm):
    for pb in arm.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.rotation_euler = (0, 0, 0)
        pb.scale = (1, 1, 1)


def create_character(obj_path, skeleton_folder, name, out_dir, ragdoll=True, game=GAME_RAGDOLL,
                     component=GAME_COMPONENT, game_root=None, report=print):
    """Do OBJ do Fuse ao Group<Nome>.range pronto. Retorna um resumo com o caminho salvo."""
    import os
    import sys
    import bpy
    if game_root and game_root not in sys.path:
        sys.path.insert(0, game_root)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    _ragdoll_addon()
    arm0, proxy = load_library_base(skeleton_folder)
    before = set(scene.objects)
    bpy.ops.import_scene.obj(filepath=obj_path)
    pieces = [o for o in scene.objects if o not in before and o.type == 'MESH']
    scene.update()
    info = align_to_base(pieces, arm0, report=report)
    arm = fit_skeleton(arm0, proxy, pieces)
    transfer_weights(proxy, pieces, arm)
    group_name = "Group" + name
    tex_dir = os.path.join(out_dir, "textures")
    build_atlas(pieces, tex_dir, group_name)
    body = join_pieces(pieces)
    bpy.data.objects.remove(proxy, do_unlink=True)
    bpy.data.objects.remove(arm0, do_unlink=True)
    arm.name = "Armature" + group_name
    if ragdoll:
        add_ragdoll(arm, game)
    card = os.path.join(tex_dir, name + "_card.png")
    try:
        info["cartao"] = render_card(arm, [body], card, game_root,
                                     photo_path=os.path.join(tex_dir, name + "_foto.png"), report=report)
    except Exception as exc:
        report("aviso: cartao nao renderizado (%s)" % exc)
    finish_pilot(arm, body, group_name, component, report)
    # Materiais, texturas e imagens das peças do Fuse ficaram sem uso depois do atlas.
    for coll in (bpy.data.materials, bpy.data.textures, bpy.data.images, bpy.data.meshes):
        for block in [b for b in coll if b.users == 0]:
            coll.remove(block)
    # O atlas fica em textures/ ao lado do .range, não empacotado (como os pilotos prontos).
    # (este editor liga o empacotamento automático em arquivos novos)
    bpy.data.use_autopack = False
    for im in bpy.data.images:
        if im.packed_file:
            im.unpack(method='REMOVE')
    if not bake_seat_pose(arm, game_root):
        report("aviso: pose sentada do jogo nao encontrada; o piloto fica em pose T se a action de base nao tocar")
    hide_for_libload(scene)
    path = os.path.join(out_dir, group_name + ".range")
    bpy.context.user_preferences.filepaths.save_version = 0   # sem .range1 ao salvar de novo
    bpy.ops.wm.save_as_mainfile(filepath=path, relative_remap=True)
    info["dds"] = prepare_dds(report)
    if info["dds"]:
        bpy.ops.wm.save_mainfile()     # guarda o mapa PNG -> DDS usado pelo export do jogo
    info["arquivo"] = path
    return info


def hide_for_libload(scene, layer=HIDDEN_LAYER):
    """Objetos so na camada escondida: no LibLoad do jogo entram inativos (prontos p/ addObject)."""
    for o in scene.objects:
        o.layers = [i == layer for i in range(20)]
    scene.layers = [i == 0 for i in range(20)]


def prepare_dds(report=print):
    """Game > Performance > Textures (DDS) no arquivo do personagem (o export do jogo nao prepara os
    arquivos de LibLoad). So a cor vira DDS; o normal map fica PNG (regra do conversor)."""
    import bpy
    try:
        from bl_operators import anastacio_prepare_textures as pt
    except ImportError:
        report("aviso: conversor DDS nao encontrado")
        return []
    colors = pt.color_usage()
    feitos = []
    for im in bpy.data.images:
        reason = pt.skip_reason(im, colors)
        if reason:
            continue
        try:
            pt.prepare_image(im, 2048, 10)
            feitos.append(im.name)
        except Exception as exc:
            report("aviso: DDS de %s falhou (%s)" % (im.name, exc))
    return feitos


def cli_main(args):
    """Linha de comando (tools/create_fuse_character.py e o operador do editor, em segundo plano):
    <obj> <Nome> <saida> [esqueleto] [--sem-ragdoll] [--projeto <raiz do jogo>]."""
    root = None
    if "--projeto" in args:
        i = args.index("--projeto")
        root = args[i + 1]
        args = args[:i] + args[i + 2:]
    flags = {a for a in args if a.startswith("--")}
    pos = [a for a in args if not a.startswith("--")]
    obj_path, name, out_dir = pos[0], pos[1], pos[2]
    skeleton = pos[3] if len(pos) > 3 else "mixamo_two_fingers"
    folders = {sid: folder for sid, _n, folder in list_skeletons()}
    if skeleton not in folders:
        raise SystemExit("skeleton %r not found; options: %s" % (skeleton, ", ".join(folders)))
    info = create_character(obj_path, folders[skeleton], name, out_dir,
                            ragdoll="--sem-ragdoll" not in flags, game_root=root)
    print("PERSONAGEM", info)
    return info
