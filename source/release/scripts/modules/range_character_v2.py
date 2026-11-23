"""Personagem v2 (docs/personagem-v2-plan.md): pipeline em etapas com checkpoint por etapa.

Reaproveita range_character_autorig (alinhamento, esqueleto, pesos, atlas); aqui ficam as etapas novas
ou refeitas. Cada etapa abre o checkpoint anterior e grava o seu (NN_<etapa>.range na pasta de trabalho).
"""

import math
import os

import bpy

from mathutils import Matrix, Vector

import range_character_autorig as autorig

DEFAULT_SKELETON = "mixamo_full_fingers"

# Peças do Fuse cujo alfa da textura recorta a malha (cards de cabelo, cílios). O resto é opaco: o alfa
# das outras texturas só marca área vazia do UV, e alpha 0 com transparência deixava o corpo "lavado".
ALPHA_PIECES = {"hair", "eyelashes", "eyebrows", "beard", "moustache"}


# -- Etapa 1: importar e limpar ----------------------------------------------------------------------------

def _gloss_image(diffuse_img):
    """Fuse: <nome>_<Peça>_gloss.png ao lado do diffuse (o importador OBJ ignora map_Ns)."""
    if diffuse_img is None:
        return None
    path = bpy.path.abspath(diffuse_img.filepath)
    gloss = path.replace("_diffuse.", "_gloss.")
    if gloss == path or not os.path.isfile(gloss):
        return None
    return bpy.data.images.load(gloss, check_existing=True)


def _fuse_images(mat):
    """(diffuse, normal, specular) do material que o importador OBJ montou."""
    found = {"diffuse": None, "normal": None, "specular": None}
    for slot in mat.texture_slots:
        if not (slot and slot.texture and slot.texture.type == 'IMAGE' and slot.texture.image):
            continue
        img = slot.texture.image
        if slot.use_map_color_diffuse:
            found["diffuse"] = img
        elif slot.use_map_normal:
            found["normal"] = img
        elif "_specular." in img.filepath:
            found["specular"] = img
    return found["diffuse"], found["normal"], found["specular"]


def _add_slot(mat, name, img, **flags):
    tex = bpy.data.textures.new(name, 'IMAGE')
    tex.image = img
    slot = mat.texture_slots.add()
    slot.texture = tex
    slot.texture_coords = 'UV'
    slot.use_map_color_diffuse = False
    for k, v in flags.items():
        if k.startswith("tex_"):
            setattr(tex, k[4:], v)
        else:
            setattr(slot, k, v)
    return slot


def fix_fuse_material(mat, alpha_clip):
    """Material NOVO no formato do jogo a partir das imagens do Fuse: opaco (ou recorte por alfa), normal
    map de verdade, especular pelo mapa e dureza pelo gloss, sem metal.

    Não aproveita o material do importador OBJ: com ele o render saía preto mesmo com os campos iguais
    aos de um material novo (Ka 0 do .mtl, bump no lugar de normal map, etc.)."""
    diffuse, normal, specular = _fuse_images(mat)
    name = mat.name
    mat.name = name + "_obj"
    new = bpy.data.materials.new(name)
    if diffuse:
        _add_slot(new, name + "_diffuse", diffuse, use_map_color_diffuse=True,
                  use_map_alpha=alpha_clip, alpha_factor=1.0)
    if normal:
        normal.colorspace_settings.name = 'Non-Color'
        _add_slot(new, name + "_normal", normal, use_map_normal=True, normal_factor=1.0,
                  normal_map_space='TANGENT', tex_use_normal_map=True)
    # cabelo e cílios sem brilho: no runtime o especular deixava o cabelo grisalho de frente para o sol
    # (no GLSL do editor não aparecia); conferido na etapa 10
    if specular and not alpha_clip:
        specular.colorspace_settings.name = 'Non-Color'
        _add_slot(new, name + "_specular", specular, use_map_specular=True, specular_factor=0.2)
    gloss = None if alpha_clip else _gloss_image(diffuse)
    if gloss:
        gloss.colorspace_settings.name = 'Non-Color'
        _add_slot(new, name + "_gloss", gloss, use_map_hardness=True, hardness_factor=0.5)
    mat = new
    mat.diffuse_color = (1.0, 1.0, 1.0)
    mat.diffuse_intensity = 1.0
    mat.specular_color = (1.0, 1.0, 1.0)
    mat.specular_intensity = 0.0 if alpha_clip else 0.2   # 1,0 do OBJ deixava o piloto de plástico
    mat.specular_hardness = 40
    mat.diffuse_metallic_bsdf = mat.specular_metallic_bsdf = 0.0
    if alpha_clip:
        mat.use_transparency = True
        mat.transparency_method = 'Z_TRANSPARENCY'
        mat.alpha = 0.0
        mat.game_settings.alpha_blend = 'CLIP'
        mat.use_cast_shadows = True
    else:
        mat.use_transparency = False
        mat.alpha = 1.0
        mat.game_settings.alpha_blend = 'OPAQUE'
    return {"material": mat.name, "alfa": alpha_clip, "gloss": bool(gloss)}


def clip_base_color(ob):
    """Cor base dos materiais com recorte (cabelo, cílios) = média da textura onde a peça está (UV, pesada
    pelo alfa). No 2.79 a imagem com alfa só pinta na proporção do alfa: nas mechas semitransparentes
    aparecia a cor base branca do material e o cabelo ficava grisalho, com contorno branco, no jogo."""
    uv = ob.data.uv_layers.active
    if uv is None:
        return None
    out = {}
    for mat in ob.data.materials:
        if mat is None or not mat.use_transparency:
            continue
        slot = next((s for s in mat.texture_slots if s and s.use_map_color_diffuse and s.texture
                     and getattr(s.texture, "image", None)), None)
        if slot is None:
            continue
        im = slot.texture.image
        w, h = im.size
        px = im.pixels[:]
        mi = list(ob.data.materials).index(mat)
        acc, wsum = [0.0, 0.0, 0.0], 0.0
        for p in ob.data.polygons:
            if p.material_index != mi:
                continue
            for li in p.loop_indices:
                u, v = uv.data[li].uv
                x, y = int((u % 1.0) * (w - 1)), int((v % 1.0) * (h - 1))
                k = (y * w + x) * 4
                a = px[k + 3]
                for c in range(3):
                    acc[c] += px[k + c] * a
                wsum += a
        if wsum <= 0.0:
            continue
        srgb = [c / wsum for c in acc]
        lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
        mat.diffuse_color = lin
        out[mat.name] = [round(c, 3) for c in srgb]
    return out


def import_fuse(obj_path, skeleton=DEFAULT_SKELETON, report=print):
    """Etapa 1: OBJ do Fuse -> peças de pé, em metros, frente +Y (como a base), pé no chão, transformações
    aplicadas, materiais corrigidos. Cena nova (apaga a atual). Retorna (peças, info)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.world = autorig.default_world()
    folder = _skeleton_folder(skeleton)
    arm0, proxy = autorig.load_library_base(folder)
    before = set(scene.objects)
    bpy.ops.import_scene.obj(filepath=obj_path)
    pieces = [o for o in scene.objects if o not in before and o.type == 'MESH']
    scene.update()
    info = autorig.align_to_base(pieces, arm0, report=report)
    info["frente_depois"] = autorig.mesh_front(pieces)[0]
    bpy.data.objects.remove(proxy, do_unlink=True)
    bpy.data.objects.remove(arm0, do_unlink=True)
    mats, made = [], {}
    for o in sorted(pieces, key=lambda p: p.name):
        clip = autorig._piece(o) in ALPHA_PIECES
        for i, mat in enumerate(o.data.materials):
            if mat is None:
                continue
            # cílios dividem o material do corpo, mas recortam pelo alfa: material próprio
            key = (mat.as_pointer(), clip)
            if key not in made:
                src = mat.copy() if clip else mat
                if clip:
                    src.name = o.name.split(".")[0]   # Hair, Eyelashes
                info_mat = fix_fuse_material(src, clip)
                made[key] = bpy.data.materials[info_mat["material"]]
                mats.append(info_mat)
            o.data.materials[i] = made[key]
        if clip:
            clip_base_color(o)
    for mat in [m for m in bpy.data.materials if m.users == 0]:
        tex = [s.texture for s in mat.texture_slots if s and s.texture]
        bpy.data.materials.remove(mat)
        for t in tex:
            if t.users == 0:
                bpy.data.textures.remove(t)
    info["materiais"] = mats
    info["pecas"] = {o.name: autorig._tris(o) for o in pieces}
    info["esqueleto"] = skeleton
    return pieces, info


def mixamo_material(name, tex_dir, prefix):
    """Material no formato do jogo a partir dos PNGs extraídos do FBX do Mixamo (<prefix>_Diffuse/Normal/
    Specular/Glossiness.png): opaco, normal map de verdade, especular pelo mapa e dureza pelo gloss."""
    def load(kind):
        f = os.path.join(tex_dir, "%s_%s.png" % (prefix, kind))
        return bpy.data.images.load(f, check_existing=True) if os.path.isfile(f) else None
    diffuse, normal, specular, gloss = load("Diffuse"), load("Normal"), load("Specular"), load("Glossiness")
    new = bpy.data.materials.new(name)
    if diffuse:
        _add_slot(new, name + "_diffuse", diffuse, use_map_color_diffuse=True)
    if normal:
        normal.colorspace_settings.name = 'Non-Color'
        _add_slot(new, name + "_normal", normal, use_map_normal=True, normal_factor=1.0,
                  normal_map_space='TANGENT', tex_use_normal_map=True)
    if specular:
        specular.colorspace_settings.name = 'Non-Color'
        _add_slot(new, name + "_specular", specular, use_map_specular=True, specular_factor=0.2)
    if gloss:
        gloss.colorspace_settings.name = 'Non-Color'
        _add_slot(new, name + "_gloss", gloss, use_map_hardness=True, hardness_factor=0.5)
    new.diffuse_color = (1.0, 1.0, 1.0)
    new.diffuse_intensity = 1.0
    new.specular_color = (1.0, 1.0, 1.0)
    new.specular_intensity = 0.2
    new.specular_hardness = 40
    new.diffuse_metallic_bsdf = new.specular_metallic_bsdf = 0.0
    new.use_transparency = False
    new.alpha = 1.0
    new.game_settings.alpha_blend = 'OPAQUE'
    return new


def import_mixamo(fbx_path, tex_dir, tex_prefix, skeleton=DEFAULT_SKELETON, report=print):
    """Etapa 1 para personagem que vem direto do Mixamo (sem Fuse): FBX com malha única + esqueleto + pesos.
    Joga fora o rig e os grupos de vértice do Mixamo (o v2 refaz esqueleto e pesos, igual aos do Fuse; o FBX
    original fica guardado em 00_original), põe a malha de pé, em metros, frente +Y, altura da base, material
    novo com as texturas extraídas do FBX. A malha vira a peça "Body". Retorna (peças, info)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.world = autorig.default_world()
    arm0, proxy = autorig.load_library_base(_skeleton_folder(skeleton))
    before = set(scene.objects)
    bpy.ops.import_scene.fbx(filepath=fbx_path)
    new = [o for o in scene.objects if o not in before]
    meshes = [o for o in new if o.type == 'MESH']
    if not meshes:
        raise ValueError("FBX sem malha: %s" % fbx_path)
    info = {"ossos_mixamo": sum(len(o.data.bones) for o in new if o.type == 'ARMATURE'),
            "malhas_fbx": {o.name: autorig._tris(o) for o in meshes}}
    scene.update()
    for o in meshes:
        for m in [m for m in o.modifiers if m.type == 'ARMATURE']:
            o.modifiers.remove(m)
        mw = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = mw
        o.vertex_groups.clear()
    for o in new:
        if o.type != 'MESH':
            bpy.data.objects.remove(o, do_unlink=True)
    for a in list(bpy.data.actions):
        bpy.data.actions.remove(a)
    # uma peça só (várias malhas são juntas), com o nome que o pipeline espera
    if len(meshes) > 1:
        bpy.ops.object.select_all(action='DESELECT')
        for o in meshes:
            o.select = True
        scene.objects.active = meshes[0]
        bpy.ops.object.join()
        meshes = [scene.objects.active]
    body = meshes[0]
    body.name = body.data.name = "Body"
    mat = mixamo_material("Body", tex_dir, tex_prefix)
    body.data.materials.clear()
    body.data.materials.append(mat)
    for p in body.data.polygons:
        p.material_index = 0
    for mat0 in [m for m in bpy.data.materials if m.users == 0]:
        bpy.data.materials.remove(mat0)
    scene.update()
    info.update(autorig.align_to_base([body], arm0, report=report))
    info["frente_depois"] = autorig.mesh_front([body])[0]
    bpy.data.objects.remove(proxy, do_unlink=True)
    bpy.data.objects.remove(arm0, do_unlink=True)
    info["pecas"] = {body.name: autorig._tris(body)}
    info["esqueleto"] = skeleton
    return [body], info


def _skeleton_folder(skeleton):
    if os.path.isdir(skeleton):
        return skeleton
    for sid, _name, folder in autorig.list_skeletons():
        if sid == skeleton:
            return folder
    raise ValueError("esqueleto não encontrado na biblioteca: %s" % skeleton)


# -- Etapa 2: esqueleto ------------------------------------------------------------------------------------

FINGERS = ("Thumb", "Index", "Middle", "Ring", "Pinky")


def _finger_chain(arm, side, finger):
    names = ["mixamorig:%sHand%s%d" % (side, finger, i) for i in (1, 2, 3)]
    return names if all(n in arm.data.bones for n in names) else None


def _principal_axis(pts):
    """(centroide, direção principal) de uma nuvem de pontos."""
    import numpy as np
    a = np.array([tuple(p) for p in pts])
    cen = a.mean(axis=0)
    _u, _s, vt = np.linalg.svd(a - cen, full_matrices=False)
    return Vector(cen.tolist()), Vector(vt[0].tolist()).normalized()


def _section_center(verts, root, axis, t, line_dist, slab=0.004):
    """Centro (caixa) da seção do dedo a `t` da raiz, só vértices perto da linha da cadeia."""
    pts = []
    for c in verts:
        d = c - root
        tt = d.dot(axis)
        if abs(tt - t) < slab and (d - axis * tt).length < line_dist:
            pts.append(c)
    if len(pts) < 3:
        return None, len(pts)
    mn = Vector((min(p[i] for p in pts) for i in range(3)))
    mx = Vector((max(p[i] for p in pts) for i in range(3)))
    c = (mn + mx) / 2.0
    # só a parte perpendicular ao dedo: a posição ao longo dele é a da junta
    off = c - root
    return root + axis * t + (off - axis * off.dot(axis)), len(pts)


def _thumb_line(hverts, root, axis, reach):
    """Dedão: eixo principal dos vértices perto da cadeia, refeito com o eixo novo. (p0, d, ponta)."""
    p0, d, pts = root, axis, None
    for _it in range(4):
        cur = []
        for c in hverts:
            q = c - p0
            t = q.dot(d)
            if (q - d * t).length < reach and (c - root).dot(axis) > 0.015:
                cur.append(c)
        if len(cur) < 12:
            break
        cen, nd = _principal_axis(cur)
        if nd.dot(d) < 0:
            nd = -nd
        p0, d, pts = cen, nd, cur
    if pts is None:
        return None
    far = max(pts, key=lambda c: (c - p0).dot(d))
    return p0, d, p0 + d * (far - p0).dot(d)


def _slice_loops(bm, sgn, x):
    """Corta bm (coordenadas do mundo) no plano X = sgn*x; devolve os anéis do corte (listas de pontos)."""
    import bmesh
    res = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
                                 plane_co=(sgn * x, 0.0, 0.0), plane_no=(1.0, 0.0, 0.0), dist=1e-6)
    cut = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]
    adj = {}
    for e in cut:
        a, b = e.verts
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    seen, loops = set(), []
    for v in adj:
        if v in seen:
            continue
        comp, stack = [], [v]
        seen.add(v)
        while stack:
            u = stack.pop()
            comp.append(u.co.copy())
            for w in adj[u]:
                if w not in seen:
                    seen.add(w)
                    stack.append(w)
        loops.append(comp)
    return loops


def _long_finger_centers(arm, side, body, step=0.003, max_err=0.012):
    """Indicador a mínimo: a malha do corpo é cortada em fatias ao longo da mão (pose T: dedos em ±X). Cada
    dedo vira um anel fechado separado no corte; o centro do anel é o centro do dedo, ligado ao dedo da base
    mais próximo. Não depende de a linha da base estar dentro do dedo (no lado direito do Enzo ela passava
    5-7 mm fora). Separar por vão entre vértices falhava: a malha é esparsa (vãos de até 8 mm no próprio dedo).
    Retorna {dedo: (p0, d, ponta)}."""
    import bmesh
    mw = arm.matrix_world
    bones = arm.data.bones
    lines = {}
    for f in FINGERS[1:]:
        names = _finger_chain(arm, side, f)
        if names:
            lines[f] = (mw * bones[names[0]].head_local, mw * bones[names[2]].tail_local)
    if not lines or body is None:
        return {}
    sgn = 1.0 if next(iter(lines.values()))[1].x > 0 else -1.0
    bm = bmesh.new()
    bm.from_mesh(body.data)
    bm.transform(body.matrix_world)
    x0 = max(sgn * r.x for r, _t in lines.values()) + 0.006
    x1 = max(sgn * v.co.x for v in bm.verts)
    centers = {f: [] for f in lines}
    last = {}
    x = x0
    while x < x1 - 0.002:
        taken = {}
        small = []
        for loop in _slice_loops(bm, sgn, x):
            if len(loop) < 4:
                continue
            ys = [c.y for c in loop]
            zs = [c.z for c in loop]
            if max(ys) - min(ys) > 0.03 or max(zs) - min(zs) > 0.03:   # palma/braço, não um dedo
                continue
            small.append(Vector((sgn * x, (min(ys) + max(ys)) / 2.0, (min(zs) + max(zs)) / 2.0)))
        order = sorted(lines, key=lambda f: -lines[f][0].y)   # indicador, médio, anelar, mínimo (de +Y a -Y)
        if len(small) == len(order):
            # um anel por dedo: a ordem em Y vale mais que a distância à linha da base (mão maior/mais larga
            # que a da base deixava os dedos a ~2 cm das linhas e o médio virava anelar)
            for f, c in zip(order, sorted(small, key=lambda c: -c.y)):
                taken[f] = (0.0, c)
            last.update({f: c for f, (_e, c) in taken.items()})
        elif last:
            # ponta do dedo (anel some ou se junta): segue o dedo da fatia anterior, não a linha da base
            for c in small:
                best_f, best_e = None, 0.008
                for f, lc in last.items():
                    e = abs(c.y - lc.y)
                    if e < best_e:
                        best_f, best_e = f, e
                if best_f and (best_f not in taken or best_e < taken[best_f][0]):
                    taken[best_f] = (best_e, c)
            last.update({f: c for f, (_e, c) in taken.items()})
        else:
            for c in small:
                best_f, best_e = None, max_err
                for f, (r, t) in lines.items():
                    u = (sgn * x - r.x) / (t.x - r.x if abs(t.x - r.x) > 1e-6 else 1e-6)
                    e = abs(c.y - (r.y + u * (t.y - r.y)))
                    if e < best_e:
                        best_f, best_e = f, e
                if best_f and (best_f not in taken or best_e < taken[best_f][0]):
                    taken[best_f] = (best_e, c)
        for f, (_e, c) in taken.items():
            centers[f].append(c)
        x += step
    tip_verts = [v.co.copy() for v in bm.verts]
    bm.free()
    out = {}
    for f, cs in centers.items():
        if len(cs) < 3:
            continue
        p0, d = _principal_axis(cs)
        if d.x * sgn < 0:
            d = -d
        near = [c for c in tip_verts if ((c - p0) - d * (c - p0).dot(d)).length < 0.008]
        far = max((c - p0).dot(d) for c in near) if near else (cs[-1] - p0).dot(d)
        out[f] = (p0, d, p0 + d * far)
    return out


def fit_fingers(arm, meshes, reach=0.010, thumb_reach=0.016):
    """Os 5 dedos (cadeias <Dedo>1-3): estica cada cadeia até a ponta do dedo da malha e leva cada junta ao
    centro da seção do dedo. Só mexe nos ossos (os pesos são a etapa 3).

    reach: distância máxima da linha da cadeia (dedos vizinhos ficam a ~1,6 cm; o polegar é mais grosso).
    Retorna {osso: deslocamento da cabeça em mm} e avisos."""
    from mathutils import Vector as V
    scene = bpy.context.scene
    core = [o for o in meshes if autorig._piece(o) not in autorig.ACCESSORIES]
    verts = autorig.world_verts(core)
    mw = arm.matrix_world
    bones = arm.data.bones
    plan, report, warn = {}, {}, []
    for side in ("Left", "Right"):
        hand = bones.get("mixamorig:%sHand" % side)
        if hand is None:
            continue
        hx = (mw * hand.head_local).x
        hverts = [c for c in verts if abs(c.x) >= abs(hx) - 0.01 and (c.x > 0) == (hx > 0)]
        body = next((o for o in meshes if autorig._piece(o) == "body"), None)
        long_fingers = _long_finger_centers(arm, side, body)
        wide = None
        for finger in FINGERS:
            names = _finger_chain(arm, side, finger)
            if not names:
                continue
            root = mw * bones[names[0]].head_local
            tip0 = mw * bones[names[2]].tail_local
            axis = (tip0 - root).normalized()
            fracs = [(mw * bones[n].head_local - root).dot(axis) / (tip0 - root).length for n in names] + [1.0]
            if finger == "Thumb":
                line = _thumb_line(hverts, root, axis, thumb_reach)
                if line is None:      # mão maior que a da base (Fabio): procura mais longe da linha
                    line = _thumb_line(hverts, root, axis, thumb_reach * 1.7)
            else:
                line = long_fingers.get(finger)
                if line is None:
                    if wide is None:
                        wide = _long_finger_centers(arm, side, body, max_err=0.022)
                    line = wide.get(finger)
            if line is None:
                warn.append("%s %s: dedo não achado na malha, mantido o da base" % (side, finger))
                continue
            p0, d, tip = line
            if d.dot(axis) < 0.766:       # mais de 40 graus (era 25: a medida por ordem dos anéis é mais confiável) do dedo da base: medida errada
                warn.append("%s %s: eixo medido torto (%.0f graus), mantido o da base"
                            % (side, finger, math.degrees(math.acos(max(-1.0, min(1.0, d.dot(axis)))))))
                continue
            base = p0 + d * (root - p0).dot(d)          # nó do dedo (dentro da palma) levado para a linha
            length = (tip - base).dot(d)
            plan[(side, finger)] = (names, [base + d * (f * length) for f in fracs])
    if not plan:
        return report, warn
    for o in scene.objects:
        o.select = o is arm
    scene.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')
    inv = mw.inverted()
    eb = arm.data.edit_bones
    for names, joints in plan.values():
        for i, n in enumerate(names):
            old = mw * eb[n].head
            eb[n].head, eb[n].tail = inv * joints[i], inv * joints[i + 1]
            report[n.replace("mixamorig:", "")] = round((joints[i] - old).length * 1000, 1)
    bpy.ops.object.mode_set(mode='OBJECT')
    return report, warn


WRIST_TO_TIP = 0.142      # m: do pulso à ponta do dedo médio nos pilotos de 1,672 m (Enzo 14,2; Aldebaran 13,7; Azeite 15,3)
WRIST_TOL = 0.015


def fit_wrist(arm, meshes):
    """Pulso: o autorig estica o braço pela envergadura e em alguns corpos (Fabio, Biel) o osso Hand fica 2-5 cm
    perto demais da ponta dos dedos (a palma vira antebraço e dobra com os dedos). Recua a cabeça do Hand (e a
    ponta do ForeArm) ao longo do antebraço até WRIST_TO_TIP da ponta da malha. Retorna {lado: cm recuados}."""
    core = [o for o in meshes if autorig._piece(o) not in autorig.ACCESSORIES]
    verts = autorig.world_verts(core)
    mw = arm.matrix_world
    inv = mw.inverted()
    plan = {}
    for side in ("Left", "Right"):
        hand = arm.data.bones.get("mixamorig:%sHand" % side)
        fore = arm.data.bones.get("mixamorig:%sForeArm" % side)
        if hand is None or fore is None:
            continue
        h = mw * hand.head_local
        f0 = mw * fore.head_local
        sgn = 1.0 if h.x > 0 else -1.0
        tip = max(sgn * c.x for c in verts)
        gap = tip - sgn * h.x
        if gap >= WRIST_TO_TIP - WRIST_TOL:
            continue
        d = (h - f0).normalized()
        if sgn * d.x < 0.5:
            continue
        back = (WRIST_TO_TIP - gap) / (sgn * d.x)     # a mudança em X vira distância ao longo do antebraço
        plan[side] = (h - d * back, back)
    if not plan:
        return {}
    for o in bpy.context.scene.objects:
        o.select = o is arm
    bpy.context.scene.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.data.edit_bones
    out = {}
    for side, (pos, back) in plan.items():
        local = inv * pos
        eb["mixamorig:%sForeArm" % side].tail = local
        eb["mixamorig:%sHand" % side].head = local
        out[side] = round(back * 100, 1)
    bpy.ops.object.mode_set(mode='OBJECT')
    return out


def fit_skeleton_v2(pieces, skeleton=DEFAULT_SKELETON, report=print):
    """Etapa 2: traz o esqueleto da biblioteca, estica braços pela envergadura (autorig.fit_skeleton) e
    encaixa os 5 dedos. A malha ainda não é ligada (etapa 3). Retorna (armature, info)."""
    arm0, proxy = autorig.load_library_base(_skeleton_folder(skeleton))
    arm = autorig.fit_skeleton(arm0, proxy, pieces)
    bpy.data.objects.remove(proxy, do_unlink=True)
    bpy.data.objects.remove(arm0, do_unlink=True)
    arm.name = "Armature"
    arm["v2_skeleton"] = skeleton
    arm.data.draw_type = 'STICK'
    arm.show_x_ray = True
    wrist = fit_wrist(arm, pieces)
    moved, warn = fit_fingers(arm, pieces)
    if wrist:
        warn.append("pulso recuado (cm): %s" % wrist)
    for w in warn:
        report("aviso: " + w)
    return arm, {"ossos": len(arm.data.bones), "dedos_mm": moved, "avisos": warn}


def dump_hand(path, arm, pieces):
    """JSON com vértices das mãos e juntas dos ossos da mão, para o gráfico de conferência."""
    import json
    mw = arm.matrix_world
    out = {}
    core = [o for o in pieces if autorig._piece(o) not in autorig.ACCESSORIES]
    verts = autorig.world_verts(core)
    for side in ("Left", "Right"):
        hand = arm.data.bones.get("mixamorig:%sHand" % side)
        if hand is None:
            continue
        hx = (mw * hand.head_local).x
        out[side] = {
            "verts": [tuple(c) for c in verts if abs(c.x) >= abs(hx) - 0.02 and (c.x > 0) == (hx > 0)],
            "bones": {b.name.replace("mixamorig:", ""): (tuple(mw * b.head_local), tuple(mw * b.tail_local))
                      for b in arm.data.bones if side + "Hand" in b.name},
        }
    with open(path, "w") as f:
        json.dump(out, f)
    return path


# -- Etapa 3: pesos -----------------------------------------------------------------------------------------

def _finger_polyline(arm, names):
    mw = arm.matrix_world
    b = arm.data.bones
    return [mw * b[n].head_local for n in names] + [mw * b[names[-1]].tail_local]


def _project_polyline(c, pts):
    """(distância, t ao longo da linha a partir de pts[0]); o 1º trecho continua para trás (palma)."""
    best = None
    acc = 0.0
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        seg = b - a
        L = seg.length
        u = (c - a).dot(seg) / (L * L)
        if i > 0:
            u = max(u, 0.0)
        if i < len(pts) - 2:
            u = min(u, 1.0)
        q = a + seg * u
        d = (c - q).length
        if best is None or d < best[0]:
            best = (d, acc + u * L)
        acc += L
    return best


def _smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3.0 - 2.0 * x)


FINGER_RADIUS = 0.011        # do eixo até a pele do dedo (~7-8 mm) + folga; o vizinho fica a ~16 mm
THUMB_RADIUS = 0.017
JOINT_BLEND = 0.004          # meia faixa de mistura nas juntas entre falanges
KNUCKLE_BLEND = (-0.010, 0.006)    # da palma (só Hand) ao começo do dedo (só <Dedo>1), em t
THUMB_BASE_BLEND = (0.000, 0.014)


def finger_weights(arm, meshes):
    """Pesos das mãos pelos ossos encaixados (não copiados da base): cada vértice perto de um dedo fica só
    com os ossos desse dedo (mistura suave nas juntas) e com Hand na palma, em degradê até o nó do dedo.
    Os pesos copiados da base decimada esticavam e quebravam o formato dos dedos ao dobrar.
    Retorna {lado: vértices refeitos}."""
    out = {}
    for side in ("Left", "Right"):
        hand = "mixamorig:%sHand" % side
        if hand not in arm.data.bones:
            continue
        chains = {}
        for f in FINGERS:
            names = _finger_chain(arm, side, f)
            if names:
                chains[f] = (names, _finger_polyline(arm, names))
        own = {hand} | {n for names, _p in chains.values() for n in names}
        hx = (arm.matrix_world * arm.data.bones[hand].head_local).x
        count = 0
        skin = [o for o in meshes if o.type == 'MESH' and autorig._piece(o) == "body"]
        for o in skin:
            groups = {g.name: g for g in o.vertex_groups}
            for v in o.data.vertices:
                c = o.matrix_world * v.co
                if (c.x > 0) != (hx > 0) or abs(c.x) < abs(hx) - 0.005:
                    continue
                hits = []
                for f, (names, pts) in chains.items():
                    d, t = _project_polyline(c, pts)
                    radius = THUMB_RADIUS if f == "Thumb" else FINGER_RADIUS
                    lo = THUMB_BASE_BLEND[0] if f == "Thumb" else KNUCKLE_BLEND[0]
                    if d < radius and t > lo:
                        hits.append((d, f, t))
                # Só vértices que já eram da mão/dedos (pulso e antebraço ficam com a transferência).
                old = {o.vertex_groups[e.group].name: e.weight for e in v.groups}
                if sum(x for n, x in old.items() if n in own) < 0.5:
                    continue
                if not hits:
                    # palma/costas da mão longe de qualquer dedo: só Hand. A transferência da base dava
                    # pesos de falange a vértices da palma quando a mão é maior que a da base (Fabio, Biel).
                    if any(x > 0.05 for n, x in old.items() if n in own and n != hand):
                        for e in list(v.groups):
                            o.vertex_groups[e.group].remove([v.index])
                        g = groups.get(hand) or o.vertex_groups.new(hand)
                        groups[hand] = g
                        g.add([v.index], 1.0, 'REPLACE')
                        count += 1
                    continue
                d, f, t = min(hits)
                names, pts = chains[f]
                cuts = [0.0]
                for i in range(1, len(pts)):
                    cuts.append(cuts[-1] + (pts[i] - pts[i - 1]).length)
                # falange pela posição, misturando com a vizinha perto das juntas 1 e 2
                seg = 0 if t < cuts[1] else (1 if t < cuts[2] else 2)
                w = {names[seg]: 1.0}
                for j in (1, 2):
                    k = (t - cuts[j]) / JOINT_BLEND
                    if -1.0 < k < 1.0:
                        w = {names[j - 1]: 0.5 - k / 2.0, names[j]: 0.5 + k / 2.0}
                # nó do dedo: degradê da mão para a 1ª falange
                lo, hi = THUMB_BASE_BLEND if f == "Thumb" else KNUCKLE_BLEND
                kf = _smooth((t - lo) / (hi - lo))
                if kf < 1.0:
                    w = {n: x * kf for n, x in w.items()}
                    w[hand] = w.get(hand, 0.0) + (1.0 - kf)
                for e in list(v.groups):
                    o.vertex_groups[e.group].remove([v.index])
                for n, x in w.items():
                    if x <= 1e-4:
                        continue
                    g = groups.get(n)
                    if g is None:
                        g = groups[n] = o.vertex_groups.new(n)
                    g.add([v.index], x, 'REPLACE')
                count += 1
        count += _cloth_follow_hand(arm, side, skin, [o for o in meshes if o.type == 'MESH' and o not in skin], own, hx)
        out[side] = count
    return out


def _cloth_follow_hand(arm, side, skin, cloth, own, hx, dist=0.03, k=4):
    """Luva e manga da mão copiam os pesos (já refeitos) dos vértices de pele mais próximos, até 3 cm: com
    a malha da roupa a ~1 cm da pele o raio dos dedos não pegava e a luva ficava rígida ou rasgava."""
    from mathutils import kdtree
    pts = [(o.matrix_world * v.co, o, v) for o in skin for v in o.data.vertices
           if (o.matrix_world * v.co).x * hx > 0 and abs((o.matrix_world * v.co).x) >= abs(hx) - 0.03]
    if not pts:
        return 0
    tree = kdtree.KDTree(len(pts))
    for i, (co, _o, _v) in enumerate(pts):
        tree.insert(co, i)
    tree.balance()
    count = 0
    for o in cloth:
        for v in o.data.vertices:
            c = o.matrix_world * v.co
            if (c.x > 0) != (hx > 0) or abs(c.x) < abs(hx) - 0.005:
                continue
            old = {o.vertex_groups[e.group].name: e.weight for e in v.groups}
            if sum(x for n, x in old.items() if n in own) < 0.5:
                continue
            hits = [h for h in tree.find_n(c, k) if h[2] <= dist]
            if not hits:
                continue
            acc, tot = {}, 0.0
            for _co, i, d in hits:
                sk, sv = pts[i][1], pts[i][2]
                w = 1.0 / max(d, 0.002)
                tot += w
                for e in sv.groups:
                    nm = sk.vertex_groups[e.group].name
                    acc[nm] = acc.get(nm, 0.0) + w * e.weight
            for e in list(v.groups):
                o.vertex_groups[e.group].remove([v.index])
            for nm, w in acc.items():
                if w / tot > 0.001:
                    g = o.vertex_groups.get(nm) or o.vertex_groups.new(nm)
                    g.add([v.index], w / tot, 'REPLACE')
            count += 1
    return count


def weights_v2(arm, pieces, skeleton=None):
    """Etapa 3: pesos do corpo pela malha da base (autorig.transfer_weights), mãos refeitas pelos ossos
    (finger_weights) e pescoço/cabeça cortados (autorig.limit_head_weights). Liga as peças na armature."""
    skeleton = skeleton or arm.get("v2_skeleton") or DEFAULT_SKELETON
    arm0, proxy = autorig.load_library_base(_skeleton_folder(skeleton))
    bpy.data.objects.remove(arm0, do_unlink=True)
    autorig.transfer_weights(proxy, pieces, arm)
    bpy.data.objects.remove(proxy, do_unlink=True)
    hands = finger_weights(arm, pieces)
    for o in pieces:
        autorig.limit_head_weights(o, arm)
    sem_peso = {o.name: sum(1 for v in o.data.vertices if not v.groups) for o in pieces}
    return {"maos_vertices": hands, "sem_peso": {k: n for k, n in sem_peso.items() if n}}


def pose_grip(arm, curl=(55.0, 70.0, 50.0), thumb=(15.0, 25.0, 25.0)):
    """Pose de teste: dedos fechados como segurando o volante (palma para baixo na pose T).

    O eixo de dobra de cada dedo é fixo, medido no repouso (direção do dedo x baixo), e vira rotação LOCAL de
    cada falange (como uma animação). Com o eixo recalculado pela direção já dobrada, depois de ~125° o eixo
    invertia e a ponta voltava em vez de dobrar."""
    from mathutils import Quaternion
    down = (arm.matrix_world.inverted().to_3x3() * Vector((0.0, 0.0, -1.0))).normalized()
    for side in ("Left", "Right"):
        for f in FINGERS:
            names = _finger_chain(arm, side, f)
            if not names:
                continue
            b0 = arm.data.bones[names[0]]
            d = (b0.tail_local - b0.head_local).normalized()
            axis = d.cross(down)
            if axis.length < 1e-6:
                continue
            axis.normalize()
            angles = thumb if f == "Thumb" else curl
            for n, ang in zip(names, angles):
                bone = arm.data.bones[n]
                local = (bone.matrix_local.to_3x3().inverted() * axis).normalized()
                pb = arm.pose.bones[n]
                pb.rotation_mode = 'QUATERNION'
                pb.rotation_quaternion = Quaternion(local, math.radians(ang))
    bpy.context.scene.update()


def clear_pose(arm):
    for pb in arm.pose.bones:
        pb.location = (0.0, 0.0, 0.0)
        pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        pb.rotation_euler = (0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)
    bpy.context.scene.update()


def render_hands(path, arm, pieces):
    """As duas mãos de perto, aberta e fechada (pose_grip). Volta à pose de repouso no fim."""
    mw = arm.matrix_world
    outs = []
    body = [o for o in pieces if autorig._piece(o) not in autorig.ACCESSORIES]
    for pose in ("aberta", "fechada"):
        clear_pose(arm)
        if pose == "fechada":
            pose_grip(arm)
        for side in ("Left", "Right"):
            hand = arm.pose.bones["mixamorig:%sHand" % side]
            c = mw * (hand.head + (hand.tail - hand.head) * 1.6)
            outs += render_check(path.replace(".png", "_%s_%s.png" % (side, pose)), body, size=(512, 512),
                                 center=c, extent=0.17,
                                 views=(("frente", (0.0, 1.0, -0.35)), ("baixo", (0.15, 0.35, -1.0))))
    clear_pose(arm)
    return outs


# -- Etapa 4: separar a cabeça ---------------------------------------------------------------------------

HEAD_BONE = "mixamorig:Head"
# Peças do Fuse que vão inteiras com a cabeça.
HEAD_PIECES = {"hair", "eyes", "eyelashes", "eyebrows", "beard", "moustache", "hat", "hats", "eyewear",
               "mask", "masks"}


def _weight(o, v, name):
    g = o.vertex_groups.get(name)
    if g is None:
        return 0.0
    return next((e.weight for e in v.groups if e.group == g.index), 0.0)


def head_weights_whole(arm, pieces, chin_gap=0.022, nape_drop=0.010):
    """Etapa 4 sem corte (2026-11-18, o impostor da cabeça não ficou bom): a malha não é separada. Acima do
    mesmo plano do corte (2,2 cm sob o queixo / 1 cm sob o crânio) o corpo passa a pesar 100 % Head (os pesos do
    Fuse dão pouco Head ao queixo e ao lábio de baixo e a boca entortava ao virar), cabelo/olhos/cílios/acessórios
    também; abaixo, o pescoço em degradê (blend_neck) com teto radial (limit_neck_radial: alça e trapézio não
    giram). Retorna info."""
    body = next(o for o in pieces if autorig._piece(o) == "body")
    hv, cut = _head_side(arm, body, chin_gap, nape_drop, bisect=False)
    before = [{body.vertex_groups[e.group].name: round(e.weight, 4) for e in v.groups} for v in body.data.vertices]
    g_head = body.vertex_groups.get(HEAD_BONE) or body.vertex_groups.new(HEAD_BONE)
    for i in hv:
        v = body.data.vertices[i]
        for e in list(v.groups):
            body.vertex_groups[e.group].remove([i])
        g_head.add([i], 1.0, 'REPLACE')
    ring = set()
    for poly in body.data.polygons:
        inside = [i for i in poly.vertices if i in hv]
        if inside and len(inside) < len(poly.vertices):
            ring.update(inside)
    neck = blend_neck(arm, body, ring_idx=ring)
    lim = limit_neck_radial(arm, body, ring_idx=ring, keep=hv)   # a cabeça fica 100 % Head
    others = [o for o in pieces if o is not body and autorig._piece(o) not in HEAD_PIECES]
    inset = inset_skin_under_cloth(body, others)
    changed = [i for i, v in enumerate(body.data.vertices)
               if {body.vertex_groups[e.group].name: round(e.weight, 4) for e in v.groups} != before[i]]
    parts = [o for o in pieces if autorig._piece(o) in HEAD_PIECES]
    clothes = follow_skin_weights(body, changed, [o for o in pieces if o is not body and o not in parts])
    for o in parts:
        o.vertex_groups.clear()
        g = o.vertex_groups.new(HEAD_BONE)
        g.add([v.index for v in o.data.vertices], 1.0, 'REPLACE')
    return {"corte": cut, "cabeca_vertices": len(hv), "borda": len(ring), "pescoco_degrade": neck,
            "pescoco_teto_radial": lim, "pele_recuada": inset, "roupa_seguiu_pele": clothes, "pecas_100_head": sorted(o.name for o in parts)}


CLOTH_FOLLOW_DIST = 0.03   # m: roupa até 3 cm da pele mudada copia os pesos dela (gola não rasga ao virar)


def follow_skin_weights(body, changed, others, dist=CLOTH_FOLLOW_DIST, k=6):
    """Gola, alça e capuz seguem a pele que mexe com a cabeça: média (inverso da distância) dos pesos dos k vértices
    de pele mais próximos; até `dist` copia inteiro, de `dist` a 2x`dist` mistura com o peso original (sem degrau
    entre a roupa que seguiu e a que não seguiu, que rasgava/deixava a pele furar ao virar)."""
    from mathutils import kdtree
    if not changed:
        return {}
    bw = body.matrix_world
    # pele mudada na etapa 4 ou com peso do Head/Neck (o head_look gira os dois)
    hn = {g.index for g in body.vertex_groups if g.name in (HEAD_BONE, NECK_BONE)}
    src = set(changed) | {v.index for v in body.data.vertices if any(e.group in hn and e.weight > 0.0 for e in v.groups)}
    tree = kdtree.KDTree(len(src))
    for i in src:
        tree.insert(bw * body.data.vertices[i].co, i)
    tree.balance()
    names = [g.name for g in body.vertex_groups]
    out = {}
    for o in others:
        n = 0
        for v in o.data.vertices:
            hits = tree.find_n(o.matrix_world * v.co, k)
            if not hits or hits[0][2] > 2.0 * dist:
                continue
            acc, tot = {}, 0.0
            for co, j, d in hits:
                if d > 2.0 * dist:
                    continue
                w = 1.0 / max(d, 0.002)
                tot += w
                for e in body.data.vertices[j].groups:
                    acc[names[e.group]] = acc.get(names[e.group], 0.0) + w * e.weight
            t = 1.0 if hits[0][2] <= dist else 1.0 - _smooth((hits[0][2] - dist) / dist)
            old = {o.vertex_groups[e.group].name: e.weight for e in v.groups}
            mix = {g: t * acc.get(g, 0.0) / tot + (1.0 - t) * old.get(g, 0.0) for g in set(acc) | set(old)}
            s = sum(mix.values()) or 1.0
            for e in list(v.groups):
                o.vertex_groups[e.group].remove([v.index])
            for g, w in mix.items():
                if w / s > 0.001:
                    (o.vertex_groups.get(g) or o.vertex_groups.new(g)).add([v.index], w / s, 'REPLACE')
            n += 1
        if n:
            out[o.name] = n
    return out


SKIN_INSET = 0.004   # m: pele sob a roupa fica pelo menos isto abaixo dela (não fura na pose nem no LOD)
SKIN_INSET_REACH = 0.02


def inset_skin_under_cloth(body, clothes, depth=SKIN_INSET, reach=SKIN_INSET_REACH):
    """Empurra para dentro a pele que está coberta por roupa a menos de `depth` (pontinhos de pele furando a gola)."""
    from mathutils.bvhtree import BVHTree
    import bmesh
    trees = []
    for o in clothes:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bm.transform(o.matrix_world)
        trees.append(BVHTree.FromBMesh(bm))
        bm.free()
    if not trees:
        return 0
    mw = body.matrix_world
    inv = mw.inverted()
    nm = mw.to_3x3().inverted().transposed()
    n = 0
    for v in body.data.vertices:
        p = mw * v.co
        nr = (nm * v.normal).normalized()
        best = None
        for t in trees:
            hit = t.ray_cast(p - nr * 0.001, nr, reach)
            if hit[0] is not None:
                d = (hit[0] - p).dot(nr)
                best = d if best is None else min(best, d)
        if best is not None and best < depth:
            v.co = inv * (p - nr * (depth - best))
            n += 1
    body.data.update()
    return n


HEAD_NECK_RADIUS = 0.07   # m: abaixo do queixo, raio do pescoço que ainda conta como cabeça (sem corte)


def _head_side(arm, body, chin_gap, nape_drop, bisect=True):
    """Vértices do corpo acima do plano do corte (lado da cabeça) e os 2 pontos que definem o plano."""
    mw = arm.matrix_world
    hb = arm.data.bones[HEAD_BONE]
    skull = mw * hb.head_local                        # base do crânio, no alto do pescoço
    neck = arm.data.bones.get("mixamorig:Neck")
    neck_z = (mw * neck.head_local).z if neck else skull.z - 0.08
    to_w = body.matrix_world
    # queixo: o ponto mais baixo do rosto à frente do osso, perto do meio, acima da base do pescoço
    front = [to_w * v.co for v in body.data.vertices]
    front = [c for c in front if c.y > skull.y + 0.04 and abs(c.x - skull.x) < 0.03 and c.z > neck_z + 0.02
             and c.z < skull.z + 0.02]
    chin = min(front, key=lambda c: c.z) if front else skull + Vector((0.0, 0.08, -0.04))
    a = Vector((0.0, chin.y, chin.z - chin_gap))          # frente
    b = Vector((0.0, skull.y - 0.06, skull.z - nape_drop))   # nuca
    # plano que contém a reta a-b (no plano YZ) e o eixo X; normal para cima
    n = Vector((1.0, 0.0, 0.0)).cross(b - a).normalized()
    if n.z < 0:
        n = -n
    # Corta a malha no plano (faca) antes de separar: emenda reta. Só selecionar faces inteiras acima do plano
    # deixava a borda serrilhada e o serrilhado dobrava ao virar a cabeça. Pesos e UV são interpolados no corte.
    import bmesh
    if not bisect:
        # o plano é infinito para os lados: atrás (baixo) ele pegava o alto do trapézio (Aldebaran, ombro girava
        # com a cabeça). Abaixo do queixo só conta o que está perto do eixo do pescoço.
        top = mw * hb.tail_local
        bot = mw * neck.head_local if neck else skull - Vector((0, 0, 0.08))
        ax = (top - bot).normalized()

        def near_axis(c):
            q = c - bot
            return (q - ax * q.dot(ax)).length < HEAD_NECK_RADIUS

        side = set()
        for v in body.data.vertices:
            c = to_w * v.co
            if (c - a).dot(n) > -1e-5 and c.z > neck_z and (c.z >= chin.z or near_axis(c)):
                side.add(v.index)
        return side, {"queixo_z": round(chin.z, 3), "nuca_z": round(skull.z, 3)}
    inv = to_w.inverted()
    bm = bmesh.new()
    bm.from_mesh(body.data)
    near = [e for e in bm.edges if any((to_w * v.co).z > neck_z for v in e.verts)]
    geom = list({v for e in near for v in e.verts}) + near + list({f for e in near for f in e.link_faces})
    bmesh.ops.bisect_plane(bm, geom=geom, plane_co=inv * a, plane_no=(inv.to_3x3().transposed().inverted() * n).normalized(),
                           dist=1e-5)
    bm.to_mesh(body.data)
    bm.free()
    body.data.update()
    side = {v.index for v in body.data.vertices if (to_w * v.co - a).dot(n) > -1e-5
            and (to_w * v.co).z > neck_z}
    return side, {"queixo_z": round(chin.z, 3), "nuca_z": round(skull.z, 3)}


def split_head(arm, pieces, chin_gap=0.022, nape_drop=0.010):
    """Etapa 4: a cabeça vira o objeto "Cabeca", rígido e preso ao osso Head (parent BONE, sem pesos nem
    modificador Armature), pronto para ter o Impostor de Caixa como LOD.

    Do corpo vão as faces acima de um plano inclinado: na frente `chin_gap` abaixo do queixo, atrás
    `nape_drop` abaixo da base do crânio (cabeça do osso Head). Valores aprovados pelo usuário: 2,2 cm / 1 cm. A mandíbula inteira vai com a cabeça; o pescoço fica no corpo e dobra.
    (Corte por peso do Head >= 0,5 passava pela boca: queixo e lábio de baixo ficavam no corpo e rasgavam ao
    virar a cabeça.) Cabelo, olhos, cílios e acessórios de cabeça vão inteiros. O anel do corpo na borda do corte passa a pesar 100 % Head: a emenda não abre quando a
    cabeça gira (a peça da cabeça é rígida no Head). Retorna (cabeca, info)."""
    import bmesh
    scene = bpy.context.scene
    body = next(o for o in pieces if autorig._piece(o) == "body")
    hv, cut = _head_side(arm, body, chin_gap, nape_drop)
    seam = set()
    for poly in body.data.polygons:
        inside = [i for i in poly.vertices if i in hv]
        if inside and len(inside) < len(poly.vertices):
            seam.update(inside)
    seam_co = {tuple(round(x, 6) for x in body.data.vertices[i].co) for i in seam}
    autorig._select_only(body)
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(body.data)
    bm.verts.ensure_lookup_table()
    for f in bm.faces:
        f.select = all(v.index in hv for v in f.verts)
    bmesh.update_edit_mesh(body.data)
    bpy.ops.mesh.separate(type='SELECTED')
    bpy.ops.object.mode_set(mode='OBJECT')
    face = next(o for o in scene.objects if o.select and o is not body)
    # anel da emenda no corpo: 100 % Head
    g_head = body.vertex_groups.get(HEAD_BONE) or body.vertex_groups.new(HEAD_BONE)
    ring = 0
    for v in body.data.vertices:
        if tuple(round(x, 6) for x in v.co) in seam_co:
            for e in list(v.groups):
                body.vertex_groups[e.group].remove([v.index])
            g_head.add([v.index], 1.0, 'REPLACE')
            ring += 1
    pescoco = blend_neck(arm, body)   # torção do Head espalhada pelo pescoço (sem quina ao virar o rosto)
    parts = [face] + [o for o in pieces if autorig._piece(o) in HEAD_PIECES]
    part_names = sorted(o.name for o in parts[1:])
    for o in scene.objects:
        o.select = o in parts
    scene.objects.active = face
    bpy.ops.object.join()
    head = face
    head.name = head.data.name = "Cabeca"
    for m in [m for m in head.modifiers if m.type == 'ARMATURE']:
        head.modifiers.remove(m)
    head.vertex_groups.clear()
    mw = head.matrix_world.copy()
    head.parent = arm
    head.parent_type = 'BONE'
    head.parent_bone = HEAD_BONE
    head.matrix_world = mw
    tris = autorig._tris(head)
    return head, {"corte": cut, "cabeca_tris": tris, "corpo_tris": autorig._tris(body), "anel_emenda": ring,
                  "pescoco_degrade": pescoco,
                  "pecas_na_cabeca": part_names}


NECK_BONE = "mixamorig:Neck"


NECK_EXTRA = 0.08        # o degradê passa 8 cm da base do pescoço (cabeça do Neck); 2-6 cm ainda dobrava
NECK_RADIUS_SOFT = 1.0   # borda do cilindro do pescoço: cai de 1 a 0 entre R e 2R (grade em Enzo/11_pescoco)


def blend_neck(arm, ob, extra=NECK_EXTRA, soft=NECK_RADIUS_SOFT, ring_idx=None):
    """Pescoço em degradê para o Head. O anel da emenda é 100 % Head (a cabeça é rígida no Head), mas logo
    abaixo o pescoço do Fuse pesa ~80 % Spine2 e ~20 % Neck; no jogo só o Head gira (head_look até 40°) e a
    torção inteira caía na 1ª faixa: o pescoço fazia uma quina. Aqui cada vértice do pescoço ganha peso do Head
    t = 1 no anel -> 0 a `extra` abaixo da base do pescoço (curva suave), vezes um fator radial (só dentro do
    cilindro do pescoço: ombro, trapézio e peito ficam como estão); os outros pesos encolhem na mesma proporção.
    Rodar na malha cheia (etapa 4), antes da redução. Retorna nº de vértices mudados."""
    from mathutils import kdtree
    g_head = ob.vertex_groups.get(HEAD_BONE)
    if g_head is None:
        return 0
    mw = ob.matrix_world
    if ring_idx is None:
        ring = [mw * v.co for v in ob.data.vertices if _weight(ob, v, HEAD_BONE) >= 0.999]
    else:   # sem corte: só a borda de baixo da cabeça (a cabeça inteira daria o raio da cabeça, não o do pescoço)
        ring = [mw * ob.data.vertices[i].co for i in ring_idx]
    if not ring:
        return 0
    am = arm.matrix_world
    base = am * arm.data.bones[NECK_BONE].head_local
    topo = am * arm.data.bones[HEAD_BONE].head_local
    eixo = (topo - base).normalized()

    def radial(p):
        q = p - base
        return (q - eixo * q.dot(eixo)).length

    raio = sorted(radial(c) for c in ring)[len(ring) // 2]   # raio do pescoço na emenda (mediana)
    centro = sum(ring, Vector()) / len(ring)
    falloff = (centro - base).dot(eixo) + extra
    tree = kdtree.KDTree(len(ring))
    for i, c in enumerate(ring):
        tree.insert(c, i)
    tree.balance()
    mudou = 0
    for v in ob.data.vertices:
        wh = _weight(ob, v, HEAD_BONE)
        if wh >= 0.999:
            continue
        p = mw * v.co
        d = tree.find(p)[2]
        t = (1.0 - _smooth(d / falloff)) * (1.0 - _smooth((radial(p) - raio) / (raio * soft)))
        if t <= 0.001:
            continue
        novo = wh + (1.0 - wh) * t
        escala = (1.0 - novo) / (1.0 - wh)
        for e in list(v.groups):
            g = ob.vertex_groups[e.group]
            if g.name.startswith("mixamorig") and g is not g_head:
                g.add([v.index], e.weight * escala, 'REPLACE')
        g_head.add([v.index], novo, 'REPLACE')
        mudou += 1
    return mudou


NECK_RADIAL_LIMIT = 0.5   # fora do cilindro do pescoço o Head cai a 0 em 0,5 raio (alça e trapézio não giram)


def limit_neck_radial(arm, ob, soft=NECK_RADIAL_LIMIT, ring_idx=None, keep=()):
    """Teto do peso do Head pela distância ao eixo do pescoço: 1 dentro do raio da emenda, 0 a `soft` raios fora.
    O excesso vai para o Neck (o head_look só gira o Head). Com a borda larga do blend_neck (1 raio) a alça da
    regata e o trapézio giravam com a cabeça e faziam uma quina a 40° (2026-11-18). Rodar antes de juntar a
    cabeça (o anel ainda é o corte). Retorna nº de vértices mudados."""
    g_head = ob.vertex_groups.get(HEAD_BONE)
    g_neck = ob.vertex_groups.get(NECK_BONE) or ob.vertex_groups.new(NECK_BONE)
    if g_head is None:
        return 0
    mw = ob.matrix_world
    if ring_idx is None:   # o anel do corte: de antes do blend_neck (depois dele há vértices novos com 1)
        ring_idx = {v.index for v in ob.data.vertices if _weight(ob, v, HEAD_BONE) >= 0.999}
    ring = [mw * ob.data.vertices[i].co for i in ring_idx]
    if not ring:
        return 0
    am = arm.matrix_world
    base = am * arm.data.bones[NECK_BONE].head_local
    eixo = ((am * arm.data.bones[HEAD_BONE].head_local) - base).normalized()

    def radial(p):
        q = p - base
        return (q - eixo * q.dot(eixo)).length

    raio = sorted(radial(c) for c in ring)[len(ring) // 2]
    mudou = 0
    for v in ob.data.vertices:
        wh = _weight(ob, v, HEAD_BONE)
        if wh <= 0.0 or v.index in ring_idx or v.index in keep:
            continue
        teto = 1.0 - _smooth((radial(mw * v.co) - raio) / (raio * soft))
        if wh <= teto + 1e-4:
            continue
        g_head.add([v.index], teto, 'REPLACE')
        g_neck.add([v.index], _weight(ob, v, NECK_BONE) + (wh - teto), 'REPLACE')
        mudou += 1
    return mudou


def match_seam_normals(body, head, tol=0.0015):
    """Normal da emenda igual nos dois objetos: cada lado calculava a normal só com as próprias faces e a luz
    mudava de uma vez na linha do corte. Os vértices do corpo e da cabeça na mesma posição (até `tol`) ganham
    a média das normais das faces dos dois lados, como normal personalizada (auto smooth 180°; o resto da malha
    fica igual). A engine usa a normal personalizada; o skinning só gira a normal. Retorna nº de pares."""
    from mathutils import kdtree
    def world_normals(ob):
        me = ob.data
        mw = ob.matrix_world
        nm = mw.to_3x3().inverted().transposed()
        acc = [Vector() for _ in me.vertices]
        for p in me.polygons:
            n = (nm * p.normal).normalized() * p.area
            for vi in p.vertices:
                acc[vi] += n
        return [mw * v.co for v in me.vertices], acc
    bco, bn = world_normals(body)
    hco, hn = world_normals(head)
    tree = kdtree.KDTree(len(hco))
    for i, c in enumerate(hco):
        tree.insert(c, i)
    tree.balance()
    btree = kdtree.KDTree(len(bco))
    for i, c in enumerate(bco):
        btree.insert(c, i)
    btree.balance()
    # cada ponto da emenda: todos os vértices dos dois lados ali (a malha do Fuse tem duplicados na mesma posição)
    shared_b, shared_h = {}, {}
    for bi, c in enumerate(bco):
        if bi in shared_b:
            continue
        hs = [i for _co, i, _d in tree.find_range(c, tol)]
        if not hs:
            continue
        bs = [i for _co, i, _d in btree.find_range(c, tol)]
        n = sum((bn[i] for i in bs), Vector()) + sum((hn[i] for i in hs), Vector())
        n.normalize()
        for i in bs:
            shared_b[i] = n
        for i in hs:
            shared_h[i] = n
    if not shared_b:
        return 0
    pairs = shared_b
    for ob, shared in ((body, shared_b), (head, shared_h)):
        me = ob.data
        me.use_auto_smooth = True
        me.auto_smooth_angle = math.pi
        me.calc_normals_split()
        to_local = ob.matrix_world.to_3x3().transposed()   # normal do mundo -> objeto (sem escala não uniforme)
        out = []
        for loop in me.loops:
            n = shared.get(loop.vertex_index)
            out.append(tuple((to_local * n).normalized()) if n is not None else tuple(loop.normal))
        me.normals_split_custom_set(out)
    return len(pairs)


def pose_head_test(arm, yaw=40.0, pitch=15.0, neck=15.0):
    """Pose de teste: pescoço inclinado e cabeça virada (conferir a emenda)."""
    from mathutils import Euler
    for n, rot in (("mixamorig:Neck", (math.radians(neck), 0.0, 0.0)),
                   (HEAD_BONE, (math.radians(pitch), math.radians(yaw), 0.0))):
        pb = arm.pose.bones.get(n)
        if pb:
            pb.rotation_mode = 'QUATERNION'
            pb.rotation_quaternion = Euler(rot, 'XYZ').to_quaternion()
    bpy.context.scene.update()


def render_head(path, arm, head, body_parts):
    """Corte (cabeça em vermelho chapado) e cabeça virada, de perto."""
    mw = arm.matrix_world
    hb = arm.pose.bones[HEAD_BONE]
    outs = []
    red = bpy.data.materials.new("_corte")
    red.diffuse_color = (0.9, 0.1, 0.1)
    red.specular_intensity = 0.0
    objs = body_parts + [head]
    for pose in ("repouso", "virada"):
        clear_pose(arm)
        if pose == "virada":
            pose_head_test(arm)
        c = mw * hb.head
        for tint in ((True, False) if pose == "repouso" else (False,)):
            over = {head.name: red} if tint else None
            tag = "corte" if tint else pose
            outs += render_check(path.replace(".png", "_%s.png" % tag), objs, size=(512, 512),
                                 center=c, extent=0.42, override=over,
                                 views=(("frente", (0.35, 1.0, 0.1)), ("lado", (1.0, -0.15, 0.05)),
                                        ("atras", (-0.3, -1.0, 0.1))))
    clear_pose(arm)
    bpy.data.materials.remove(red)
    return outs


# -- Etapa 5: mãos para o jogo ----------------------------------------------------------------------------

PROTECT_GROUP = "proteger_maos"
GRIPS = {"MAOS_VOLANTE": 0.016, "MAOS_GUIDAO": 0.012}
GRIP_FRAMES = (1, 12)    # aberta -> fechada; soltar = tocar ao contrário (12 -> 1)   # raio da barra (aro do volante ~3,2 cm; guidão ~2,4 cm)
THUMB_GRIP = (10.0, 15.0, 20.0)   # dedão ao longo do aro
FINGER_HALF = 0.0065      # do eixo do dedo até a pele (encosta na barra)


def protect_hands(arm, pieces):
    """Grupo de vértices `proteger_maos` (1 nas mãos e dedos, degradê no pulso): a redução da etapa 7 usa
    como trava (Decimate com vertex group). A redução por igual quebrava o formato dos dedos."""
    names = {b.name for b in arm.data.bones if "Hand" in b.name}
    count = 0
    for o in pieces:
        if o.type != 'MESH' or not o.vertex_groups:
            continue
        idx = {g.index for g in o.vertex_groups if g.name in names}
        if not idx:
            continue
        g = o.vertex_groups.get(PROTECT_GROUP) or o.vertex_groups.new(PROTECT_GROUP)
        for v in o.data.vertices:
            w = sum(e.weight for e in v.groups if e.group in idx)
            if w > 0.0:
                g.add([v.index], min(1.0, w * 2.0), 'REPLACE')
                count += 1
    return count


def _bend_axis_local(arm, bone_name, axis_arm):
    bone = arm.data.bones[bone_name]
    return (bone.matrix_local.to_3x3().inverted() * axis_arm).normalized()


def _bar(arm, side, radius):
    """Barra virtual sob a palma (pose T, palma para baixo): (ponto no eixo, direção do eixo), espaço da armature.
    O eixo é perpendicular aos dedos, no plano da palma; a barra fica encostada embaixo dos nós dos dedos."""
    b = arm.data.bones
    knuckles = [b["mixamorig:%sHand%s1" % (side, f)].head_local for f in FINGERS[1:]]
    mid = sum(knuckles, Vector()) / len(knuckles)
    tips = [b["mixamorig:%sHand%s3" % (side, f)].tail_local for f in FINGERS[1:]]
    fdir = (sum(tips, Vector()) / len(tips) - mid).normalized()
    down = (arm.matrix_world.inverted().to_3x3() * Vector((0.0, 0.0, -1.0))).normalized()
    axis = fdir.cross(down).normalized()
    palm_half = 0.011
    center = mid - fdir * 0.004 + down * (palm_half + radius)   # na palma, junto da base dos dedos
    return center, axis, fdir, down


def _dist_to_axis(p, c, a):
    q = p - c
    return (q - a * q.dot(a)).length


def pose_grip_bar(arm, radius, step=2.0):
    """Fecha os dedos em volta da barra: cada falange gira (eixo fixo do dedo, rotação local) até a ponta
    encostar na barra (distância ao eixo = raio + meia grossura do dedo). O dedão gira em volta de um eixo
    paralelo à barra, do outro lado. Retorna {osso: graus}."""
    from mathutils import Quaternion
    scene = bpy.context.scene
    out = {}
    for side in ("Left", "Right"):
        if "mixamorig:%sHand" % side not in arm.data.bones:
            continue
        c, a, fdir, down = _bar(arm, side, radius)
        target = radius + FINGER_HALF
        for f in FINGERS:
            names = _finger_chain(arm, side, f)
            if not names:
                continue
            b0 = arm.data.bones[names[0]]
            d = (b0.tail_local - b0.head_local).normalized()
            axis = d.cross(down).normalized()
            if f == "Thumb":
                # Volante/guidão: o dedão deita ao longo do aro (paralelo à barra), com curva leve.
                for n, ang in zip(names, THUMB_GRIP):
                    pb = arm.pose.bones[n]
                    pb.rotation_mode = 'QUATERNION'
                    pb.rotation_quaternion = Quaternion(_bend_axis_local(arm, n, axis), math.radians(ang))
                    out[n.replace("mixamorig:", "")] = ang
                scene.update()
                continue
            for n in names:
                local = _bend_axis_local(arm, n, axis)
                pb = arm.pose.bones[n]
                pb.rotation_mode = 'QUATERNION'
                best_ang, best_d = 0.0, None
                ang = 0.0
                limit = 60.0 if (f == "Thumb" and n == names[0]) else 100.0
                while ang <= limit:
                    pb.rotation_quaternion = Quaternion(local, math.radians(ang))
                    scene.update()
                    dist = _dist_to_axis(pb.tail, c, a)
                    if best_d is None or dist < best_d:
                        best_ang, best_d = ang, dist
                    if dist <= target:
                        best_ang = ang
                        break
                    ang += step
                pb.rotation_quaternion = Quaternion(local, math.radians(best_ang))
                scene.update()
                out[n.replace("mixamorig:", "")] = best_ang
    return out


def make_grip_actions(arm):
    """Uma action por barra (MAOS_VOLANTE, MAOS_GUIDAO) só com os ossos dos dedos, fake user: o movimento de
    fechar a mão, quadro 1 aberta (repouso) -> quadro 12 fechada na barra. O jogo toca numa camada acima da
    animação de dirigir (só dedos); para soltar, toca de 12 para 1."""
    info = {}
    if arm.animation_data is None:
        arm.animation_data_create()
    finger_bones = [n for side in ("Left", "Right") for f in FINGERS for n in (_finger_chain(arm, side, f) or [])]
    for name, radius in GRIPS.items():
        clear_pose(arm)
        angles = pose_grip_bar(arm, radius)
        act = bpy.data.actions.get(name) or bpy.data.actions.new(name)
        for fc in list(act.fcurves):
            act.fcurves.remove(fc)
        for n in finger_bones:
            pb = arm.pose.bones[n]
            path = 'pose.bones["%s"].rotation_quaternion' % n
            for i in range(4):
                fc = act.fcurves.new(path, index=i, action_group=n)
                fc.keyframe_points.insert(GRIP_FRAMES[0], (1.0, 0.0, 0.0, 0.0)[i])
                fc.keyframe_points.insert(GRIP_FRAMES[1], pb.rotation_quaternion[i])
        act.use_fake_user = True
        info[name] = angles
    clear_pose(arm)
    arm.animation_data.action = None
    return info


def _bar_object(arm, side, radius, name):
    c, a, _f, _d = _bar(arm, side, radius)
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=radius, depth=0.14)
    ob = bpy.context.active_object
    ob.name = name
    mw = arm.matrix_world
    ob.matrix_world = mw * (Matrix.Translation(c) * a.to_track_quat('Z', 'Y').to_matrix().to_4x4())
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (0.25, 0.25, 0.3)
    ob.data.materials.append(mat)
    return ob


def render_grips(path, arm, pieces):
    """Cada pegada com a barra, as duas mãos, de frente e de baixo."""
    body = [o for o in pieces if autorig._piece(o) not in autorig.ACCESSORIES]
    mw = arm.matrix_world
    outs = []
    for name, radius in GRIPS.items():
        clear_pose(arm)
        arm.animation_data.action = bpy.data.actions[name]
        bpy.context.scene.frame_set(GRIP_FRAMES[1])     # mão fechada
        bars = [_bar_object(arm, side, radius, "_barra_" + side) for side in ("Left", "Right")]
        for side, bar in zip(("Left", "Right"), bars):
            hand = arm.pose.bones["mixamorig:%sHand" % side]
            c = mw * (hand.head + (hand.tail - hand.head) * 1.6)
            outs += render_check(path.replace(".png", "_%s_%s.png" % (name, side)), body + [bar],
                                 size=(512, 512), center=c, extent=0.17,
                                 views=(("frente", (0.0, 1.0, -0.35)), ("ponta", (1.0 if c.x > 0 else -1.0, 0.0, -0.2))))
        for bar in bars:
            me, mat = bar.data, bar.data.materials[0]
            bpy.data.objects.remove(bar, do_unlink=True)
            bpy.data.meshes.remove(me)
            bpy.data.materials.remove(mat)
        arm.animation_data.action = None
    clear_pose(arm)
    return outs


# -- Etapa 6: atlas do corpo ------------------------------------------------------------------------------

AO_SAMPLES = 16          # o addon automate_atlas_bake usava 10
AO_STRENGTH = 0.5        # igual ao addon: 1 - (1 - ao) * força
AO_DISTANCE = 0.25       # metros; o padrão do world (10 m) deixava o corpo todo cinza


def bake_ao_into_atlas(body, tex_dir, name, size=2048, samples=AO_SAMPLES, strength=AO_STRENGTH,
                       distance=AO_DISTANCE):
    """Assa a oclusão de ambiente (sombras de contato) do Body no UV do atlas e multiplica na cor do atlas,
    como o modo Combined do addon automate_atlas_bake no processo antigo. A Cabeca e o resto da cena entram
    como obstáculo (pescoço sob o queixo, axilas, entre as pernas). Grava <name>_ao.png e guarda a cor sem AO
    em <name>_diffuse_sem_ao.png. Retorna o caminho da cor com AO."""
    scene = bpy.context.scene
    old_engine = scene.render.engine
    scene.render.engine = 'BLENDER_RENDER'
    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    ls = world.light_settings
    keep = (ls.use_ambient_occlusion, ls.samples, ls.distance, ls.gather_method)
    ls.use_ambient_occlusion = True
    ls.gather_method = 'RAYTRACE'
    ls.samples = samples
    ls.distance = distance
    r = scene.render
    r.bake_type = 'AO'
    r.use_bake_normalize = True
    r.bake_margin = 8
    r.use_bake_selected_to_active = False
    r.use_bake_clear = True
    img = bpy.data.images.new(name + "_ao", size, size, alpha=False)
    uv = body.data.uv_textures["UV_Atlas"]
    body.data.uv_textures.active = uv
    for poly in uv.data:
        poly.image = img
    autorig._select_only(body)
    bpy.ops.object.bake_image()
    for poly in uv.data:
        poly.image = None
    ls.use_ambient_occlusion, ls.samples, ls.distance, ls.gather_method = keep
    scene.render.engine = old_engine
    ao = list(img.pixels)
    img.filepath_raw = os.path.join(tex_dir, name + "_ao.png")
    img.file_format = 'PNG'
    img.save()
    import shutil
    diff_path = os.path.join(tex_dir, name + "_diffuse.png")
    shutil.copyfile(diff_path, os.path.join(tex_dir, name + "_diffuse_sem_ao.png"))
    info = combine_ao(body, tex_dir, name, ao, strength)
    dark = sum(1 for i in range(0, len(ao), 4) if ao[i] < 0.7) / (len(ao) / 4)
    info.update({"ao": img.filepath_raw, "pixels_escuros_pct": round(dark * 100, 1)})
    return info


AO_SEAM_FADE = 0.05      # a AO some na emenda do pescoço e volta inteira 5 cm abaixo
SEAM_RATIO_SMOOTH = 0.015   # a razão de tom de cada ponto da emenda é a média dos vizinhos até 1,5 cm


def _bake_vertex_rgb(body, size, rgb):
    """Assa uma cor por vértice (lista RGB 0-1) no UV do atlas (Blender Internal, VERTEX_COLORS). Pixels RGBA."""
    me = body.data
    vc = me.vertex_colors.new("_assar")
    rgba = len(vc.data) > 0 and len(vc.data[0].color) == 4   # esta build tem cor de vértice RGBA
    for li, loop in enumerate(me.loops):
        c = rgb[loop.vertex_index]
        vc.data[li].color = (c[0], c[1], c[2], 1.0) if rgba else tuple(c)
    me.vertex_colors.active = vc
    scene = bpy.context.scene
    old_engine = scene.render.engine
    scene.render.engine = 'BLENDER_RENDER'
    r = scene.render
    r.bake_type = 'VERTEX_COLORS'
    r.bake_margin = 8
    r.use_bake_selected_to_active = False
    r.use_bake_clear = True
    img = bpy.data.images.new("_assar", size, size, alpha=False)
    uv = me.uv_textures["UV_Atlas"]
    me.uv_textures.active = uv
    for poly in uv.data:
        poly.image = img
    autorig._select_only(body)
    bpy.ops.object.bake_image()
    for poly in uv.data:
        poly.image = None
    px = list(img.pixels)
    me.vertex_colors.remove(vc)
    bpy.data.images.remove(img)
    scene.render.engine = old_engine
    return px


def _loop_colors(ob, img, verts):
    """{vértice: cor média da textura `img` nos loops dele} (UV ativo)."""
    me = ob.data
    w, h = img.size
    px = img.pixels[:]
    uv = me.uv_layers.active.data
    acc = {}
    for li, loop in enumerate(me.loops):
        vi = loop.vertex_index
        if vi in verts:
            u, v = uv[li].uv
            k = (min(h - 1, int(v % 1.0 * h)) * w + min(w - 1, int(u % 1.0 * w))) * 4
            a = acc.setdefault(vi, [0.0, 0.0, 0.0, 0])
            a[0] += px[k]
            a[1] += px[k + 1]
            a[2] += px[k + 2]
            a[3] += 1
    return {vi: Vector(a[:3]) / a[3] for vi, a in acc.items()}


def _seam_ratio(body, head, sem, tol=0.0015, smooth=SEAM_RATIO_SMOOTH):
    """{vértice do anel do corpo: razão cor_da_cabeça / cor_do_corpo (RGB)} ponto a ponto, suavizada ao longo
    da emenda. As texturas do Fuse do pescoço e do rosto diferem 2-5 % e variam em volta do pescoço: uma razão
    média só ainda deixava degrau em alguns trechos."""
    from mathutils import kdtree
    hmat = head.data.materials[0] if head.data.materials else None
    himg = next((s.texture.image for s in hmat.texture_slots if s and s.use_map_color_diffuse and s.texture
                 and s.texture.type == 'IMAGE' and s.texture.image), None) if hmat else None
    if himg is None:
        return {}
    bm, hm = body.matrix_world, head.matrix_world
    ring = [v.index for v in body.data.vertices if _weight(body, v, HEAD_BONE) >= 0.999]
    htree = kdtree.KDTree(len(head.data.vertices))
    for v in head.data.vertices:
        htree.insert(hm * v.co, v.index)
    htree.balance()
    near = {bi: [i for _c, i, _d in htree.find_range(bm * body.data.vertices[bi].co, tol)] for bi in ring}
    near = {bi: hs for bi, hs in near.items() if hs}
    if not near:
        return {}
    cb = _loop_colors(body, sem, set(near))
    ch = _loop_colors(head, himg, {i for hs in near.values() for i in hs})
    raw = {}
    for bi, hs in near.items():
        cs = [ch[i] for i in hs if i in ch]
        if bi in cb and cs:
            h = sum(cs, Vector()) / len(cs)
            raw[bi] = Vector(tuple(min(1.5, max(0.5, h[c] / max(cb[bi][c], 1e-3))) for c in range(3)))
    pos = {bi: bm * body.data.vertices[bi].co for bi in raw}
    rtree = kdtree.KDTree(len(pos))
    for bi, p in pos.items():
        rtree.insert(p, bi)
    rtree.balance()
    out = {}
    for bi, p in pos.items():
        viz = [raw[i] for _c, i, _d in rtree.find_range(p, smooth)]
        out[bi] = sum(viz, Vector()) / len(viz)
    return out


def combine_ao(body, tex_dir, name, ao=None, strength=AO_STRENGTH, fade=AO_SEAM_FADE):
    """Cor do atlas = cor_sem_ao * (m * AO + (1 - m) * razão_da_emenda). m = 0 no anel da emenda (Head 1) -> 1 a
    `fade` dele: a cabeça não tem AO (texturas do Fuse) e a sombra do queixo assada só no pescoço deixava um
    degrau de tom; no anel a cor do corpo vira a da cabeça, ponto a ponto. Sem `ao`, lê <name>_ao.png (refazer
    a combinação de um atlas já assado). Grava <name>_diffuse.png."""
    from mathutils import kdtree
    diff_path = os.path.join(tex_dir, name + "_diffuse.png")
    if ao is None:
        ao_img = bpy.data.images.load(os.path.join(tex_dir, name + "_ao.png"), check_existing=False)
        ao = list(ao_img.pixels)
        bpy.data.images.remove(ao_img)
    sem = bpy.data.images.load(os.path.join(tex_dir, name + "_diffuse_sem_ao.png"), check_existing=False)
    px = list(sem.pixels)
    size = sem.size[0]
    head = next((o for o in bpy.data.objects if o.name.startswith("Cabeca") and o.type == 'MESH'
                 and o.data.materials), None)
    body.data.uv_textures.active = body.data.uv_textures["UV_Atlas"]
    ratio = _seam_ratio(body, head, sem) if head is not None else {}
    bpy.data.images.remove(sem)
    mask = rpx = None
    if ratio:
        mw = body.matrix_world
        tree = kdtree.KDTree(len(ratio))
        for bi in ratio:
            tree.insert(mw * body.data.vertices[bi].co, bi)
        tree.balance()
        m_rgb, r_rgb = [], []
        for v in body.data.vertices:
            _c, bi, d = tree.find(mw * v.co)
            m = _smooth(d / fade)
            m_rgb.append((m, m, m))
            r_rgb.append(tuple(x * 0.5 for x in ratio[bi]))     # razão 0-2 cabe em 0-1
        mask = _bake_vertex_rgb(body, size, m_rgb)
        rpx = _bake_vertex_rgb(body, size, r_rgb)
    for i in range(0, len(px), 4):
        k_ao = 1.0 - (1.0 - ao[i]) * strength
        if mask is None:
            for c in range(3):
                px[i + c] *= k_ao
            continue
        m = mask[i]
        for c in range(3):
            px[i + c] *= m * k_ao + (1.0 - m) * rpx[i + c] * 2.0
    diff = next(i for i in bpy.data.images if bpy.path.abspath(i.filepath) == os.path.abspath(diff_path)
                or i.name == name + "_diffuse")
    diff.pixels = px
    diff.filepath_raw = diff_path
    diff.file_format = 'PNG'
    diff.save()
    vals = list(ratio.values())
    return {"cor": diff_path, "emenda_pontos": len(vals),
            "razao_min_max": [round(min(r[0] for r in vals), 3), round(max(r[0] for r in vals), 3)] if vals else None}


def atlas_body(pieces, tex_dir, name):
    """Etapa 6: as peças do corpo (tudo menos a Cabeca) num atlas 2048 (cor + normal, autorig.build_atlas) e
    numa malha só "Body" com um material opaco no formato do jogo. A Cabeca não muda (tem os materiais
    próprios do Fuse; o impostor dela é assado na etapa 8). Retorna (body, info)."""
    whole = bpy.data.objects.get("Cabeca") is None
    # sem corte (2026-11-18): cabelo, cílios e acessórios transparentes ficam com o material do Fuse (recorte por alfa)
    # e entram no Body depois do AO; o rosto vai no atlas com o corpo
    # (só as que precisam de recorte por alfa; olhos e acessórios opacos vão no atlas: textura a menos por piloto)
    head_parts = [o for o in pieces if o.type == 'MESH' and autorig._piece(o) in HEAD_PIECES
                  and any(_see_through(m) for m in o.data.materials)] if whole else []
    for o in head_parts:
        for m in o.data.materials:
            if m and "lash" in m.name.lower():
                for i, sl in enumerate(m.texture_slots):
                    if sl and sl.use_map_normal:
                        m.texture_slots.clear(i)   # normal map não aparece em cílios: uma textura a menos
    body_pieces = [o for o in pieces if o.type == 'MESH' and o.name != "Cabeca" and o not in head_parts]
    before = {o.name: autorig._tris(o) for o in body_pieces}
    mat, layout = autorig.build_atlas(body_pieces, tex_dir, name)
    body = autorig.join_pieces(body_pieces, "Body")
    mat.name = name + "Material"
    # como finish_pilot: opaco, brilho baixo, sem metal (alfa 0 deixava o corpo meio transparente no jogo)
    mat.use_transparency = False
    mat.alpha = 1.0
    mat.game_settings.alpha_blend = 'OPAQUE'
    mat.specular_intensity = 0.2
    mat.specular_hardness = 40
    mat.diffuse_metallic_bsdf = mat.specular_metallic_bsdf = 0.0
    mat.use_object_color = True
    for ts in mat.texture_slots:
        if ts and ts.texture:
            ts.use_map_alpha = False
            if ts.use_map_normal and ts.texture.image:
                ts.texture.image.colorspace_settings.name = 'Non-Color'
    # materiais/texturas das peças que ficaram sem uso (a Cabeca ainda usa os dela)
    for coll in (bpy.data.materials, bpy.data.textures):
        for block in [b for b in coll if b.users == 0]:
            coll.remove(block)
    ao = bake_ao_into_atlas(body, tex_dir, name)
    if head_parts:
        join_keep_materials(body, head_parts)
    return body, {"ao": ao, "pecas": before, "corpo_tris": autorig._tris(body), "material": mat.name,
                  "atlas": {img.name: list(cell) for img, cell in layout.items()},
                  "materiais_cabeca": sorted({m.name for m in body.data.materials if m and m is not mat})}


def join_keep_materials(body, parts):
    """Junta `parts` no `body` mantendo os materiais delas: depois de juntar o UV ativo é o do atlas, então os
    slots de textura sem UV nomeado passam a ler o UV da peça pelo nome (como head_in_body_up_close)."""
    for o in parts:
        uv = o.data.uv_layers.active.name if o.data.uv_layers.active else None
        if uv:
            for m in o.data.materials:
                for sl in (m.texture_slots if m else []):
                    if sl and sl.texture_coords == 'UV' and not sl.uv_layer:
                        sl.uv_layer = uv
    scene = bpy.context.scene
    for o in scene.objects:
        o.select = o is body or o in parts
    scene.objects.active = body
    bpy.ops.object.join()


# -- Etapa 7: redução e LOD do corpo ---------------------------------------------------------------------

BODY_REST_TRIS = 3000        # corpo sem as mãos (o gerador antigo dava 3000 ao corpo sem a parte de cima)
HANDS_TRIS = None            # None = mãos inteiras no nível 0 (reduzir entortava os dedos, 2026-11-21); número = alvo das duas mãos com as juntas travadas
JOINT_GROUP = "proteger_juntas"
JOINT_KEEP = 0.004           # até 4 mm de uma junta: trava total
JOINT_FADE = 0.010           # trava some aos poucos até 10 mm da junta (meio da falange, palma: reduz)
BODY_LODS = ((2500, 15.0), (900, 35.0))
BODY_LODS_WITH_HEAD = ((4000, 15.0), (1500, 35.0))   # sem corte: a cabeça vai junto nos LODs   # (triângulos, distância) como o gerador antigo; mãos sem trava


def _hand_tris(ob):
    g = ob.vertex_groups.get(PROTECT_GROUP)
    if g is None:
        return 0
    w = {}
    for v in ob.data.vertices:
        for e in v.groups:
            if e.group == g.index:
                w[v.index] = e.weight
    return sum(len(p.vertices) - 2 for p in ob.data.polygons
               if sum(1 for i in p.vertices if w.get(i, 0.0) > 0.5) * 2 > len(p.vertices))


def _apply_decimate(ob, ratio, protect, group=PROTECT_GROUP):
    mod = ob.modifiers.new("Decimate", 'DECIMATE')
    mod.decimate_type = 'COLLAPSE'
    mod.ratio = ratio
    mod.use_collapse_quality = True
    if protect:
        mod.vertex_group = group
        mod.invert_vertex_group = True      # peso 1 no grupo = não reduz
    autorig._select_only(ob)
    while ob.modifiers[0] != mod:
        bpy.ops.object.modifier_move_up(modifier=mod.name)
    bpy.ops.object.modifier_apply(modifier=mod.name)


def joint_weights(arm, body):
    """Grupo `proteger_juntas`: 1 perto das juntas dos dedos, do nó dos dedos e do pulso (onde a malha dobra),
    caindo a 0 no meio das falanges, na palma e nas costas da mão. A redução tira vértices onde não dobra."""
    from mathutils import Vector as V
    hand_idx = {g.index for g in body.vertex_groups if g.name == PROTECT_GROUP}
    g = body.vertex_groups.get(JOINT_GROUP) or body.vertex_groups.new(JOINT_GROUP)
    mw = body.matrix_world
    chains, wrists = [], []
    for side in ("Left", "Right"):
        hb = arm.data.bones.get("mixamorig:%sHand" % side)
        if hb is None:
            continue
        wrists.append((arm.matrix_world * hb.head_local,
                       (arm.matrix_world.to_3x3() * (hb.tail_local - hb.head_local)).normalized()))
        for f in FINGERS:
            names = _finger_chain(arm, side, f)
            if names:
                pts = _finger_polyline(arm, names)
                cuts = [0.0]
                for i in range(1, len(pts)):
                    cuts.append(cuts[-1] + (pts[i] - pts[i - 1]).length)
                chains.append((f, pts, cuts))
    count = 0
    for v in body.data.vertices:
        if not any(e.group in hand_idx and e.weight > 0.0 for e in v.groups):
            g.add([v.index], 1.0, 'REPLACE')   # fora das mãos: travado (já reduzido na 1ª passada)
            continue
        c = mw * v.co
        w, hdir = min(wrists, key=lambda wd: (c - wd[0]).length)
        if (c - w).dot(hdir) < 0.015:
            keep = 1.0                          # pulso e antebraço: a 1ª passada já reduziu; aqui não mexe
        else:
            best = None
            for f, pts, cuts in chains:
                d, t = _project_polyline(c, pts)
                radius = THUMB_RADIUS if f == "Thumb" else FINGER_RADIUS
                if d < radius and (best is None or d < best[0]):
                    best = (d, t, cuts)
            if best is None:
                keep = 0.0                      # palma / costas da mão
            else:
                _d, t, cuts = best
                dj = min(abs(t - cj) for cj in cuts[:-1])    # juntas: nó, 1-2, 2-3 (a ponta não dobra)
                keep = 1.0 - _smooth((dj - JOINT_KEEP) / (JOINT_FADE - JOINT_KEEP))
                if t > cuts[-1] - 0.004:
                    keep = max(keep, 0.6)       # ponta do dedo: mantém a forma arredondada
        g.add([v.index], keep, 'REPLACE')
        count += 1
    return count


def reduce_protected(ob, target, protect=True, tries=6, group=PROTECT_GROUP):
    """Collapse (High Quality) até ~target triângulos, com as mãos travadas (grupo proteger_maos invertido).
    A trava muda a relação ratio -> triângulos: acerta a razão em algumas tentativas numa cópia."""
    src = ob.data.copy()
    total = autorig._tris(ob)
    ratio = min(1.0, target / max(total, 1))
    best = None
    for _ in range(tries):
        ob.data = src.copy()
        _apply_decimate(ob, ratio, protect, group)
        got = autorig._tris(ob)
        if best is None or abs(got - target) < abs(best[1] - target):
            best = (ratio, got)
        if abs(got - target) <= target * 0.03 or got == total:
            break
        ratio = min(1.0, max(0.01, ratio * target / max(got, 1)))
    if autorig._tris(ob) != best[1]:
        ob.data = src.copy()
        _apply_decimate(ob, best[0], protect, group)
    bpy.data.meshes.remove(src)
    return autorig._tris(ob)


GAME_ROOT = r"D:\ProjetoRolimaRacer"   # pose sentada do jogo (RolimaRacer.range) para testar faces escondidas
HIDDEN_RAYS = 64           # raios por face (hemisfério em volta da normal)


def _hemisphere(n):
    """n direções (Fibonacci) no hemisfério +Z."""
    out = []
    golden = math.pi * (3.0 - math.sqrt(5.0))
    for i in range(n):
        z = 1.0 - (i + 0.5) / n
        r = math.sqrt(max(0.0, 1.0 - z * z))
        a = golden * i
        out.append(Vector((math.cos(a) * r, math.sin(a) * r, z)))
    return out


OUTSIDE_RAYS = 160


def _sphere_dirs(n):
    out = []
    golden = math.pi * (3.0 - math.sqrt(5.0))
    for i in range(n):
        z = 1.0 - 2.0 * (i + 0.5) / n
        r = math.sqrt(max(0.0, 1.0 - z * z))
        out.append(Vector((math.cos(golden * i) * r, math.sin(golden * i) * r, z)))
    return out


def _see_through(m):
    return m is not None and (m.use_transparency or any(k in m.name.lower() for k in ("hair", "lash", "brow")))


def _hidden_in_current_pose(ob, occluders, dirs):
    """Índices das faces de `ob` fechadas por dentro na pose atual (malhas avaliadas com a armature)."""
    from mathutils.bvhtree import BVHTree
    scene = bpy.context.scene
    verts, polys = [], []
    for o in occluders:
        me = o.to_mesh(scene, True, 'PREVIEW')
        base = len(verts)
        verts.extend(o.matrix_world * v.co for v in me.vertices)
        # cabelo/cílios recortados por alfa não fecham nada: o couro cabeludo sob o cabelo tem que ficar
        clear = {i for i, m in enumerate(o.data.materials) if _see_through(m)}
        polys.extend(tuple(base + i for i in p.vertices) for p in me.polygons if p.material_index not in clear)
        bpy.data.meshes.remove(me)
    tree = BVHTree.FromPolygons(verts, polys)
    me = ob.to_mesh(scene, True, 'PREVIEW')     # mesma topologia (só armature): índices iguais aos do ob
    mw = ob.matrix_world
    n3 = mw.to_3x3().inverted().transposed()
    hidden = set()
    for p in me.polygons:
        c = mw * p.center
        nrm = (n3 * p.normal).normalized()
        rot = Vector((0.0, 0.0, 1.0)).rotation_difference(nrm).to_matrix()
        escaped = False
        for side in (1.0, -1.0):
            origin = c + nrm * (side * 0.0015)
            for d in dirs:
                if tree.ray_cast(origin, rot * d * side, 3.0)[0] is None:
                    escaped = True
                    break
            if escaped:
                break
        if not escaped:
            hidden.add(p.index)
    # Conferência por fora: raios vindos de longe, de todos os lados, em direção ao centro de cada candidata. Se o
    # 1º ponto atingido é a própria face, ela aparece e fica (faces do lado do tronco do Fabio sumiam: buraco).
    outside = _sphere_dirs(OUTSIDE_RAYS)
    for p in list(hidden):
        poly = me.polygons[p]
        c0 = mw * poly.center
        # centro e pontos perto de cada canto: uma face que só aparece pela borda (fresta do bolso) também fica
        samples = [c0] + [c0 + (mw * me.vertices[i].co - c0) * 0.6 for i in poly.vertices]
        seen = False
        for c in samples:
            for d in outside:
                hit = tree.ray_cast(c + d * 2.0, -d, 2.1)[0]
                if hit is not None and (hit - c).length < 0.004:
                    seen = True
                    break
            if seen:
                break
        if seen:
            hidden.discard(p)
    bpy.data.meshes.remove(me)
    return hidden


def remove_hidden_faces(ob, occluders, rays=HIDDEN_RAYS, poses=(None,)):
    """Apaga as faces que nunca aparecem: de cada face saem `rays` raios para fora (hemisfério da normal e,
    para não apagar parede fina vista por trás, também do lado de trás); se nenhum escapa do personagem, a face
    está fechada por dentro (forro da roupa, pele sob a roupa, interior das aberturas). Retorna faces apagadas.

    `poses`: funções que põem a armature numa pose (None = pose atual). A face só sai se estiver escondida em
    todas: na pose de descanso a cava da regata fica fechada pelo braço, sentado ela abre (o LOD1 ficava com
    buraco no ombro no jogo)."""
    import bmesh
    dirs = _hemisphere(rays)
    hidden = None
    for pose in poses:
        if pose is not None:
            pose()
        bpy.context.scene.update()
        h = _hidden_in_current_pose(ob, occluders, dirs)
        hidden = h if hidden is None else hidden & h
    hidden = sorted(hidden or ())
    if hidden:
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bm.faces.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[bm.faces[i] for i in hidden], context=5)   # 2.79: 5 = DEL_FACES
        bm.to_mesh(ob.data)
        bm.free()
        ob.data.update()
    return len(hidden)


HEAD_REGION_ABOVE_NECK = 0.03   # m acima da base do pescoço (cabeça do osso Neck)
HEAD_REGION_HALF_X = 0.14       # m para cada lado do pescoço (fora disso: ombros e braços)


def head_region(arm, body):
    """Vértices da cabeça e do alto do pescoço (sem corte, 2026-11-18): ficam inteiros no nível 0."""
    nb = arm.data.bones.get(NECK_BONE) or arm.data.bones[HEAD_BONE]
    base = arm.matrix_world * nb.head_local
    mw = body.matrix_world
    out = set()
    for v in body.data.vertices:
        c = mw * v.co
        if c.z > base.z + HEAD_REGION_ABOVE_NECK and abs(c.x - base.x) < HEAD_REGION_HALF_X:
            out.add(v.index)
    return out


def reduce_body(arm, body, rest_tris=BODY_REST_TRIS, hands_tris=HANDS_TRIS, lods=BODY_LODS,
                game_root=GAME_ROOT):
    """Etapa 7: nível 0 em duas passadas: (1) resto do corpo a rest_tris com as mãos inteiras travadas;
    (2) mãos a ~hands_tris com só as juntas travadas (proteger_juntas). LOD por distância (cópias reduzidas
    por igual a partir do corpo cheio). Retorna info com triângulos antes/depois."""
    scene = bpy.context.scene
    if bpy.data.objects.get("Cabeca") is None and lods is BODY_LODS:
        lods = BODY_LODS_WITH_HEAD
    head = bpy.data.objects.get("Cabeca")

    def rest():
        clear_pose(arm)

    def seated():
        clear_pose(arm)
        if not autorig.bake_seat_pose(arm, game_root):
            raise RuntimeError("pose sentada do jogo não encontrada em %s" % game_root)

    # Faces fechadas por dentro (forro da roupa, pele sob a roupa) saem da malha CHEIA antes de qualquer redução,
    # no nível 0 e nos LODs (2026-11-21): depois da redução a roupa tem frestas finas que os raios não acham, e
    # sem a pele de baixo elas viravam buraco no ombro (LOD sentado no jogo).
    hidden = remove_hidden_faces(body, [body] + ([head] if head else []), poses=(rest, seated))
    clear_pose(arm)
    hands0 = _hand_tris(body)
    full = body.data.copy()
    tris0 = autorig._tris(body)
    # anel do corte travado: na etapa 9 a cabeça cheia é soldada nele (nível 0 sem emenda); a redução
    # deslocava os vértices do anel e só 3 de 42 ainda coincidiam com a cabeça
    ring = [v.index for v in body.data.vertices if _weight(body, v, HEAD_BONE) >= 0.999]
    if bpy.data.objects.get("Cabeca") is None:
        ring = sorted(set(ring) | head_region(arm, body))   # cabeça inteira no corpo: nível 0 com a cabeça cheia
    gp = body.vertex_groups.get(PROTECT_GROUP)
    if gp is not None and ring:
        gp.add(ring, 1.0, 'REPLACE')
    rs = set(ring)
    locked = sum(len(p.vertices) - 2 for p in body.data.polygons if all(i in rs for i in p.vertices))         if bpy.data.objects.get("Cabeca") is None else 0   # cabeça travada não conta na meta do resto do corpo
    reduce_protected(body, hands0 + rest_tris + locked)
    if gp is not None and ring:
        # fora do grupo das mãos de novo (ele conta os triângulos das mãos); na 2ª passada o proteger_juntas
        # já trava tudo fora das mãos
        again = {v.index for v in body.data.vertices if _weight(body, v, HEAD_BONE) >= 0.999}
        if bpy.data.objects.get("Cabeca") is None:
            again |= head_region(arm, body)   # índices mudam depois da redução: recalcula
        body.vertex_groups[PROTECT_GROUP].remove(sorted(again))
    if hands_tris is None:
        got = autorig._tris(body)       # mãos inteiras (sem a 2ª passada)
    else:
        joint_weights(arm, body)
        rest_now = autorig._tris(body) - _hand_tris(body)
        got = reduce_protected(body, rest_now + hands_tris, group=JOINT_GROUP)
    hands1 = _hand_tris(body)
    head = bpy.data.objects.get("Cabeca")

    lod_objs = []
    for i, (tris, dist) in enumerate(lods, 1):
        ob = body.copy()
        ob.data = full.copy()
        ob.name = ob.data.name = "%slod%d" % (body.name, i)
        scene.objects.link(ob)
        reduce_protected(ob, tris, protect=False)
        ob.layers = body.layers
        lod_objs.append((ob, dist))
    bpy.data.meshes.remove(full)
    autorig._select_only(body)
    for _ob, _d in lod_objs:
        bpy.ops.object.lod_add()
    for i, (ob, dist) in enumerate(lod_objs, 1):
        body.lod_levels[i].object = ob
        body.lod_levels[i].distance = dist
    return {"antes": tris0, "nivel0": got, "maos_antes": hands0, "maos_depois": hands1,
            "lods": {ob.name: [autorig._tris(ob), d] for ob, d in lod_objs},
            "lods_faces_escondidas_removidas": hidden}


# -- Etapa 8: Impostor de Caixa da cabeça -----------------------------------------------------------------

HEAD_IMPOSTOR_RES = '256'      # pixels por vista (6 vistas): igual a 512 no jogo (prints 2026-11-18), 4x menos memória
HEAD_IMPOSTOR_DIST = 10.0      # metros: junto do LOD1 do corpo
HEAD_IMPOSTOR_STEPS = 10       # passos do raio no Volume: prints 32/17/10 quase iguais (2026-11-18), 1/3 do custo


def _origin_to_center(ob):
    """Origem do objeto no centro da caixa da malha, sem mexer na posição no mundo (a Cabeca veio do corpo
    com a origem nos pés; o cartão do impostor fica na origem e no tamanho do objeto)."""
    mn = Vector((min(v.co[i] for v in ob.data.vertices) for i in range(3)))
    mx = Vector((max(v.co[i] for v in ob.data.vertices) for i in range(3)))
    c = (mn + mx) / 2.0
    if c.length < 1e-6:
        return
    mw = ob.matrix_world.copy()
    ob.data.transform(Matrix.Translation(-c))
    ob.matrix_world = mw * Matrix.Translation(c)


def bake_head_impostor(head, resolution=HEAD_IMPOSTOR_RES, distance=HEAD_IMPOSTOR_DIST):
    """Etapa 8: Impostor de Caixa da Cabeca (object.bake_box_impostor da engine) como nível de LOD.
    De perto fica a cabeça cheia do Fuse; além de `distance` o cartão (6 vistas, volume e luz da cena)."""
    _origin_to_center(head)
    autorig._select_only(head)
    bpy.context.scene.update()
    res = bpy.ops.object.bake_box_impostor(resolution=resolution, mode='AUTO', normal_map=True,
                                           use_lod=True, lod_distance=distance, steps=HEAD_IMPOSTOR_STEPS)
    card = next((l.object for l in head.lod_levels[1:] if l.object), None)
    if card is None:
        raise RuntimeError("bake_box_impostor não criou o cartão (%s)" % res)
    return card, {"cartao": card.name, "distancia": distance, "resolucao": resolution,
                  "modo": "Box" if card.get("box_impostor_fill", 0) >= 0.95 else "Volume",
                  "preenchimento": round(card.get("box_impostor_fill", 0.0), 3),
                  "imagens": [i.name for i in bpy.data.images if i.name.startswith(head.name + "_imp")]}


NECK_EXTRA_UP_CLOSE = 0.16       # m abaixo da base do pescoço: degradê do nível 0 (testes Enzo/15_pescoco_fp)
NECK_RADIUS_SOFT_UP_CLOSE = 1.0
HEAD_SWITCH_MARGIN = 0.3    # m a mais na folga entre a origem do corpo (pés) e a da Cabeca na troca do LOD


def head_in_body_up_close(arm, body, head, report=print):
    """Cabeça sem emenda de perto (2026-11-17, Enzo): a cabeça cheia volta para dentro do nível 0 do corpo,
    soldada no corte (os vértices duplicados viram um só: normal e skinning contínuos). A cabeça continua 100 %
    Head e o pescoço com o degradê do blend_neck (os pesos do Fuse entortavam a boca ao virar: o queixo e o
    lábio de baixo pesam pouco no Head). A Cabeca
    fica com um triângulo invisível de perto e só mostra o Impostor de Caixa de longe, trocando um pouco antes
    do LOD1 do corpo (que já não tem cabeça): a origem da Cabeca fica na cabeça e a do corpo nos pés, então as
    distâncias diferem até a distância entre as duas origens (melhor uma cabeça dupla rápida que um buraco).
    Retorna info."""
    import bmesh
    scene = bpy.context.scene
    clear_pose(arm)
    scene.update()
    # 0. pescoço do nível 0 (o que se vê de perto) com degradê mais longo: com os 8 cm da etapa 4 a torção do
    # head_look (40°) caía toda logo abaixo do queixo e a mandíbula virava uma ponta (2026-11-18). Só sobe o peso
    # do Head (blend_neck nunca baixa), antes de juntar a cabeça (o anel ainda é o corte).
    ring_idx = {v.index for v in body.data.vertices if _weight(body, v, HEAD_BONE) >= 0.999}
    neck = blend_neck(arm, body, extra=NECK_EXTRA_UP_CLOSE, soft=NECK_RADIUS_SOFT_UP_CLOSE)
    neck_lim = limit_neck_radial(arm, body, ring_idx=ring_idx)
    # 1. cópia da cabeça como malha deformada pela armature (tudo 100 % Head) e junta no corpo
    hc = bpy.data.objects.new("_cabeca_corpo", head.data.copy())
    scene.objects.link(hc)
    hc.matrix_world = head.matrix_world.copy()
    g = hc.vertex_groups.new(HEAD_BONE)
    g.add([v.index for v in hc.data.vertices], 1.0, 'REPLACE')
    # depois de juntar, o UV ativo da malha é o do atlas: os materiais da cabeça (slot sem nome = UV ativo)
    # passam a ler o UV da cabeça pelo nome, senão o rosto sai sem textura
    huv = hc.data.uv_layers.active.name if hc.data.uv_layers.active else None
    if huv:
        for m in hc.data.materials:
            for s in (m.texture_slots if m else []):
                if s and s.texture_coords == 'UV' and not s.uv_layer:
                    s.uv_layer = huv
    n_head = len(hc.data.vertices)
    n_body = len(body.data.vertices)
    for o in scene.objects:
        o.select = o in (body, hc)
    scene.objects.active = body
    bpy.ops.object.join()
    me = body.data
    head_idx = range(n_body, n_body + n_head)
    # 2. solda do corte: vértice da cabeça a até 1 mm de um vértice do corpo vira o do corpo
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    weld_targets = {}
    from mathutils import kdtree
    tree = kdtree.KDTree(n_body)
    for i in range(n_body):
        tree.insert(bm.verts[i].co, i)
    tree.balance()
    for i in head_idx:
        co, j, d = tree.find(bm.verts[i].co)
        if d <= 0.001:
            weld_targets[bm.verts[i]] = bm.verts[j]
    bmesh.ops.weld_verts(bm, targetmap=weld_targets)
    bm.to_mesh(me)
    bm.free()
    me.update()
    # 4. Cabeca: um triângulo invisível de perto, impostor de longe
    card_lvl = next((l for l in head.lod_levels[1:] if l.object), None)
    ph = bpy.data.meshes.new(head.name + "_perto")
    # triângulo de área zero (pontos na mesma reta) com a caixa da cabeça: não desenha nada, mas a caixa de recorte
    # fica do tamanho da cabeça e o LOD é reavaliado sempre que a cabeça está no quadro (um triângulo minúsculo
    # podia ficar fora do quadro e travar o nível)
    hv = [v.co for v in head.data.vertices]
    mn = Vector((min(c.x for c in hv), min(c.y for c in hv), min(c.z for c in hv)))
    mx = Vector((max(c.x for c in hv), max(c.y for c in hv), max(c.z for c in hv)))
    ph.from_pydata([tuple(mn), tuple(mx), tuple((mn + mx) / 2.0)], [], [(0, 1, 2)])
    if card_lvl is not None:
        ph.materials.append(card_lvl.object.data.materials[0])
    old = head.data
    head.data = ph
    if old.users == 0:
        bpy.data.meshes.remove(old)
    autorig.bake_seat_pose(arm, GAME_ROOT)
    scene.update()
    gap = (head.matrix_world.translation - body.matrix_world.translation).length + HEAD_SWITCH_MARGIN
    clear_pose(arm)
    body_lod1 = body.lod_levels[1].distance if len(body.lod_levels) > 1 else HEAD_IMPOSTOR_DIST
    if card_lvl is not None:
        card_lvl.distance = max(1.0, body_lod1 - gap)
    return {"soldados": len(weld_targets), "pescoco_nivel0": neck, "pescoco_teto_radial": neck_lim,
            "cabeca_impostor_a": round(card_lvl.distance, 2) if card_lvl else None,
            "corpo_lod1_a": body_lod1, "nivel0_tris": autorig._tris(body)}


LOD_HYST_BAND = 0.5          # m de folga (histerese) em toda troca de LOD do piloto, igual nas três partes
BODY_CARD_HEAD_MARGIN = 1.0  # m: a Cabeca/alto do tronco só somem depois que o corpo já virou o cartão


def match_lod_hysteresis(objs, band=LOD_HYST_BAND):
    """A histerese do LOD da engine é uma % da distância ENTRE o nível e o anterior (KX_LodManager): o corpo
    (15→20 m) ganhava 0,5 m de folga e a Cabeca (9→20 m) 1,1 m, então na volta o corpo virava malha sem cabeça
    antes de a Cabeca reaparecer (2026-11-18, Enzo: "corpo invisível na hora errada"). Cada nível ganha a sua
    % para a folga ficar `band` metros em todas as partes; a ordem das trocas fica só nas distâncias."""
    for ob in objs:
        if ob is None:
            continue
        lv = ob.lod_levels
        for i in range(1, len(lv)):
            gap = abs(lv[i].distance - lv[i - 1].distance)
            lv[i].use_object_hysteresis = True
            lv[i].object_hysteresis_percentage = int(max(0, min(100, round(100.0 * band / gap)))) if gap > 1e-3 else 0


def split_first_person(arm, body):
    """Separa do nível 0 a cabeça e o alto do tronco (autorig.split_fp_part, a mesma altura dos antigos).
    A parte separada ganha os mesmos níveis de LOD como nível invisível (use_invisible_mesh) SEM objeto: a engine só
    reavalia o LOD de quem está no quadro, e o triângulo minúsculo de antes (na origem, nos pés) saía do quadro com
    a câmera na cabeça e o tronco ficava invisível de perto (2026-11-18). Invisível, o objeto guarda a caixa da
    malha real. Sem objeto: com objeto a engine fixa a origem da distância nele (recurso do HLOD)."""
    height = arm.get("autorig_height") or 1.672
    _rest, fp = autorig.split_fp_part(body, height)
    if fp is None or fp is body:
        return None
    autorig._select_only(fp)
    while len(fp.lod_levels) < len(body.lod_levels):
        bpy.ops.object.lod_add()
    for i in range(1, len(body.lod_levels)):
        fp.lod_levels[i].object = None
        fp.lod_levels[i].use_invisible_mesh = True
        fp.lod_levels[i].distance = body.lod_levels[i].distance
    return fp


def _skin_slots(ob):
    return {i for i, m in enumerate(ob.data.materials) if m and not m.use_transparency
            and not any(k in m.name.lower() for k in ("eye", "lash", "hair", "teeth", "tongue"))}


# -- Etapa 9: fechar o piloto ----------------------------------------------------------------------------

def finish_pilot_v2(arm, body, head, name, game_root, out_dir, ragdoll=True, report=print, head_in_body=True):
    """Etapa 9: o piloto no formato que o RolimaRacer carrega por LibLoad (como autorig.finish_pilot):
    ragdoll, propriedades e componente na armature, Cabeca com camera_hide_fp, Empty Group<Nome> com is_pilot
    instanciando o grupo (armature + Body + Cabeca + ragdoll; LODs e cartão do impostor fora do grupo, como os
    LOD do gerador antigo), cartão/foto do menu, pose sentada do jogo, camada escondida e DDS.
    Salva <out_dir>/Group<Nome>.range + textures/. Retorna info."""
    import sys
    if game_root and game_root not in sys.path:
        sys.path.insert(0, game_root)
    scene = bpy.context.scene
    group_name = "Group" + name
    info = {}
    autorig._ragdoll_addon()
    clear_pose(arm)
    if arm.animation_data:
        arm.animation_data.action = None
    bpy.context.scene.update()
    # grupos auxiliares da redução (etapa 7) saem: com peso 1 eles "ganhavam" dos ossos e a separação da 1ª
    # pessoa escondia braços e mãos junto com o tronco (2026-11-18)
    for ob in [body] + [l.object for l in body.lod_levels[1:] if l.object]:
        for gname in (PROTECT_GROUP, JOINT_GROUP):
            g = ob.vertex_groups.get(gname)
            if g is not None:
                ob.vertex_groups.remove(g)
    if head is None:
        # sem corte (2026-11-18): a cabeça já está no corpo em todos os níveis, com os pesos do Fuse
        fp_body = split_first_person(arm, body)
        info["primeira_pessoa_tris"] = autorig._tris(fp_body) if fp_body else 0
    elif head_in_body:
        # de perto a cabeça fica dentro do corpo, soldada no corte: sem emenda
        info["cabeca_no_corpo"] = head_in_body_up_close(arm, body, head, report)
        # 1ª pessoa (como os pilotos antigos): cabeça + alto do tronco, sem os braços, num objeto à parte com
        # camera_hide_fp (a câmera fica dentro do piloto). De longe ele não desenha nada: o LOD do corpo é um só.
        fp_body = split_first_person(arm, body)
        info["primeira_pessoa_tris"] = autorig._tris(fp_body) if fp_body else 0
    else:
        fp_body = None
    match_lod_hysteresis([body, fp_body, head])
    head_objs = [head] + [l.object for l in head.lod_levels[1:] if l.object] if head else []
    # nomes com o grupo antes do ragdoll (as peças levam o nome da armature): vários pilotos v2 na mesma
    # corrida não podem repetir Cabeca, materiais ou actions
    arm.name = "Armature" + group_name
    if ragdoll:
        autorig.add_ragdoll(arm)
    make_handlebar_action(name)
    for act_name in GRIPS:
        act = bpy.data.actions.get(act_name)
        if act:
            act.name = "%s.%s" % (act_name, group_name)
    if head is not None:
        head.name = head.data.name = "Cabeca" + group_name
        for lvl in head.lod_levels[1:]:
            if lvl.object:
                lvl.object.name = lvl.object.data.name = head.name + "_box_impostor"
    for im in bpy.data.images:
        # imagens do impostor da cabeça com o grupo no nome (Cabeca_imp_* se repetiria em todo piloto v2)
        if im.name.startswith("Cabeca_imp"):
            im.name = head.name + im.name[len("Cabeca"):]
    # materiais do Fuse (cabeça/cabelo/olhos) com o nome do piloto; o do atlas já tem o grupo no nome
    with_fuse = head_objs or [body] + [l.object for l in body.lod_levels[1:] if l.object] + ([fp_body] if fp_body else [])
    for ob in with_fuse:
        for m in ob.data.materials:
            if m and not m.name.startswith(name + "_") and group_name not in m.name:
                m.name = "%s_%s" % (name, m.name)
    ik_ph = add_tricycle_ik(arm, group_name, scene)
    tex_dir = os.path.join(out_dir, "textures")
    os.makedirs(tex_dir, exist_ok=True)
    import shutil
    for im in bpy.data.images:
        # o piloto leva as próprias texturas (como os do gerador antigo): copia e aponta para textures/
        src = bpy.path.abspath(im.filepath) if im.filepath else ""
        if not im.packed_file and src and os.path.isfile(src):
            dst = os.path.join(tex_dir, os.path.basename(src))
            if os.path.abspath(src) != os.path.abspath(dst):
                shutil.copyfile(src, dst)
            im.filepath = dst
    try:
        info["cartao"] = autorig.render_card(arm, [body] + ([fp_body] if fp_body and head is None else []) + head_objs[:1], os.path.join(tex_dir, name + "_card.png"),
                                             game_root, photo_path=os.path.join(tex_dir, name + "_foto.png"),
                                             report=report)
    except Exception as exc:
        report("aviso: cartão não renderizado (%s)" % exc)
    body.name = body.data.name = "Body" + group_name
    for lvl in body.lod_levels[1:]:
        if lvl.object:
            lvl.object.name = lvl.object.data.name = lvl.object.name.replace("Body", "Body" + group_name, 1)
    if head is not None:
        autorig._prop(head, "camera_hide_fp", True)   # 1ª pessoa: esconde a cabeça
    if fp_body is not None:
        fp_body.name = fp_body.data.name = "Body%s.001" % group_name    # como os antigos
        autorig._prop(fp_body, "camera_hide_fp", True)
        fp_body.game.physics_type = 'NO_COLLISION'
    arm.game.physics_type = 'NO_COLLISION'
    arm.data.deform_method = 'BGE_GPU'
    autorig._prop(arm, "pilot.armature", False)
    autorig._prop(arm, "active_ragdoll", False)
    try:
        autorig._select_only(arm)
        bpy.ops.logic.python_component_register(component_name=autorig.GAME_COMPONENT)
    except Exception as exc:
        report("aviso: componente %s não registrado (%s)" % (autorig.GAME_COMPONENT, exc))
    root = bpy.data.objects.new(group_name, None)
    scene.objects.link(root)
    root.empty_draw_size = 0.3
    autorig._prop(root, "is_pilot", False)
    extra = [l.object for l in body.lod_levels[1:] if l.object] + head_objs[1:]
    for o in [body, root] + head_objs[:1] + extra:
        o.game.physics_type = 'NO_COLLISION'
    grp = bpy.data.groups.get(group_name) or bpy.data.groups.new(group_name)
    members = [arm, body, ik_ph] + head_objs[:1] + ([fp_body] if fp_body is not None else []) + [o for o in scene.objects if o.name.startswith("RagdollPart-")]
    for o in members:
        if o.name not in grp.objects:
            grp.objects.link(o)
    root.dupli_type = 'GROUP'
    root.dupli_group = grp
    if not autorig.bake_seat_pose(arm, game_root):
        report("aviso: pose sentada do jogo não encontrada")
    for coll in (bpy.data.materials, bpy.data.textures, bpy.data.meshes):
        for block in [b for b in coll if b.users == 0]:
            coll.remove(block)
    bpy.data.use_autopack = False
    for im in bpy.data.images:
        # o atlas e as texturas do Fuse ficam em arquivo; as imagens do impostor são geradas: continuam
        # empacotadas (não têm arquivo)
        if im.packed_file and im.filepath and os.path.isfile(bpy.path.abspath(im.filepath)):
            im.unpack(method='USE_ORIGINAL')
    autorig.hide_for_libload(scene)
    path = os.path.join(out_dir, group_name + ".range")
    os.makedirs(out_dir, exist_ok=True)
    bpy.context.user_preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=path, relative_remap=True)
    info["dds"] = autorig.prepare_dds(report)
    if info["dds"]:
        bpy.ops.wm.save_mainfile()
    info.update({"arquivo": path, "grupo": [o.name for o in grp.objects if not o.name.startswith("RagdollPart-")],
                 "ragdoll_pecas": sum(1 for o in grp.objects if o.name.startswith("RagdollPart-")),
                 "tris": {"corpo": autorig._tris(body), "cabeca": autorig._tris(head) if head else 0,
                          "lods": {o.name: autorig._tris(o) for o in extra}}})
    return info


def add_tricycle_ik(arm, group_name, scene):
    """IK_tri (pernas e antebraços) e ROT_tri (mãos) mutados, como nos pilotos antigos: o triciclo do jogo
    (animations_manager.ik_triciclo) troca os alvos pelos tri_ik_* do veículo e liga. Os alvos do arquivo só
    existem para a engine criar os constraints: ik_ph.<Armature> (no grupo) e ik_pole_<L/R>.<Grupo>."""
    def empty(nome):
        ob = bpy.data.objects.get(nome) or bpy.data.objects.new(nome, None)
        if ob.name not in scene.objects:
            scene.objects.link(ob)
        return ob
    ph = empty("ik_ph." + arm.name)
    for s, lado in (("L", "Left"), ("R", "Right")):
        pole = empty("ik_pole_%s.%s" % (s, group_name))
        for osso, tem_pole in (("mixamorig:%sLeg" % lado, False), ("mixamorig:%sForeArm" % lado, True)):
            pb = arm.pose.bones[osso]
            c = pb.constraints.get("IK_tri") or pb.constraints.new('IK')
            c.name = "IK_tri"
            c.target = ph
            c.chain_count = 2
            c.iterations = 500
            c.use_tail = True
            c.use_stretch = True
            if tem_pole:
                c.pole_target = pole
                c.pole_angle = 1.5708
            c.mute = True
        pb = arm.pose.bones["mixamorig:%sHand" % lado]
        c = pb.constraints.get("ROT_tri") or pb.constraints.new('COPY_ROTATION')
        c.name = "ROT_tri"
        c.target = ph
        c.mute = True
    return ph


def make_handlebar_action(name):
    """maos_<Nome>: o triciclo toca só o quadro 1 (camada 8), então é a mão fechada do MAOS_GUIDAO (quadro 12)
    num keyframe só no quadro 1."""
    src = bpy.data.actions["MAOS_GUIDAO"]
    act = bpy.data.actions.get("maos_" + name) or bpy.data.actions.new("maos_" + name)
    for fc in list(act.fcurves):
        act.fcurves.remove(fc)
    for fc in src.fcurves:
        nova = act.fcurves.new(fc.data_path, index=fc.array_index, action_group=fc.group.name if fc.group else "")
        nova.keyframe_points.insert(1, fc.evaluate(GRIP_FRAMES[1]))
    act.use_fake_user = True
    return act


def save_checkpoint(out_dir, name):
    """Salva NN_<etapa>.range na pasta de trabalho, texturas por caminho (sem empacotar)."""
    os.makedirs(out_dir, exist_ok=True)
    bpy.data.use_autopack = False
    bpy.context.user_preferences.filepaths.save_version = 0
    path = os.path.join(out_dir, name + ".range")
    bpy.ops.wm.save_as_mainfile(filepath=path, relative_remap=True)
    return path


def render_check(path, objects, size=(768, 768), center=None, extent=None, views=None, override=None):
    """Render de conferência, um PNG por vista (padrão: frente, câmera em +Y, e lado, câmera em +X).
    center/extent: enquadramento (padrão: o personagem inteiro). views: [(nome, direção da câmera)].
    Não altera o arquivo salvo (cena temporária com cópias)."""
    verts = autorig.world_verts(objects)
    mn, mx = autorig.bounds(verts)
    if center is None:
        center = (mn + mx) / 2.0
    height = extent or (mx.z - mn.z)
    if views is None:
        views = (("frente", (0, 1, 0)), ("lado", (1, 0, 0)))
    tmp = bpy.data.scenes.new("_check")
    world = bpy.data.worlds.new("_check_world")   # neutro: o céu azul do arquivo tingia o render
    tmp.world = world
    copies = []
    for o in objects:      # cópias, como render_card: o mesmo objeto em duas cenas não pegava a luz
        c = o.copy()
        tmp.objects.link(c)
        c.layers = [i == 0 for i in range(20)]
        if override and o.name in override:      # material só na cópia (ex.: pintar a cabeça)
            for slot in c.material_slots:
                slot.link = 'OBJECT'
                slot.material = override[o.name]
        copies.append(c)
    tmp.layers = [i == 0 for i in range(20)]
    sun_data = bpy.data.lamps.new("_check_sun", 'SUN')
    sun_data.energy = 1.0
    sun_data.shadow_method = 'NOSHADOW'
    sun = bpy.data.objects.new("_check_sun", sun_data)
    # vem da frente (+Y), de cima e um pouco do lado
    sun.rotation_euler = (Vector((0.0, 0.0, 0.0)) - Vector((0.6, 1.0, 1.2))).to_track_quat('-Z', 'Y').to_euler()
    tmp.objects.link(sun)
    sun.layers = [i == 0 for i in range(20)]
    cam_data = bpy.data.cameras.new("_check_cam")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = height * 1.1
    cam = bpy.data.objects.new("_check_cam", cam_data)
    tmp.objects.link(cam)
    cam.layers = [i == 0 for i in range(20)]
    tmp.camera = cam
    r = tmp.render
    r.engine = 'BLENDER_RENDER'   # cena nova herda Blender Game: render em background sai preto
    tmp.view_settings.view_transform = 'Default'   # como render_card do autorig
    hemi_data = bpy.data.lamps.new("_check_hemi", 'HEMI')
    hemi_data.energy = 0.4
    hemi = bpy.data.objects.new("_check_hemi", hemi_data)
    tmp.objects.link(hemi)
    hemi.layers = [i == 0 for i in range(20)]
    r.resolution_x, r.resolution_y, r.resolution_percentage = size[0], size[1], 100
    r.alpha_mode = 'TRANSPARENT'
    r.image_settings.file_format = 'PNG'
    r.image_settings.color_mode = 'RGBA'
    outs = []
    for tag, loc in views:
        direction = Vector(loc).normalized()
        cam.location = center + direction * max(height * 3, 2.0)
        cam.rotation_euler = (-direction).to_track_quat('-Z', 'Y').to_euler()   # Y = cima da câmera
        cam_data.clip_end = max(height * 6, 10.0)
        out = path.replace(".png", "_%s.png" % tag)
        r.filepath = out
        bpy.ops.render.render(write_still=True, scene=tmp.name)
        outs.append(out)
    bpy.data.scenes.remove(tmp, do_unlink=True)
    for ob in [sun, cam, hemi] + copies:
        bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.lamps.remove(sun_data)
    bpy.data.lamps.remove(hemi_data)
    bpy.data.worlds.remove(world)
    bpy.data.cameras.remove(cam_data)
    return outs


# -- Etapa 11: impostor do corpo inteiro (sentado) como último LOD ---------------------------------------

BODY_IMPOSTOR_RES = '512'      # usuário aprovou 512 (1024 só tira um pouco da mancha vista de cima)
BODY_IMPOSTOR_DIST = 20.0      # metros: o cartão sentado no lugar do corpo (testado e aprovado no jogo, Enzo)
BODY_IMPOSTOR_LOD2 = 15.0      # o LOD2 de malha vem antes do cartão (os níveis precisam ser crescentes)


def bake_body_impostor(arm, body, head, game_root=GAME_ROOT, resolution=BODY_IMPOSTOR_RES):
    """Impostor de Caixa do corpo CHEIO (abra o 06_atlas.range: o 07+ já é reduzido) na pose sentada do jogo.
    Corpo + cabeça viram uma malha estática no espaço do Body (origem nos pés, a mesma do Body), então o cartão
    serve de nível de LOD do próprio Body. Retorna o cartão (com as imagens empacotadas)."""
    scene = bpy.context.scene
    head_lods = [lvl.object for lvl in head.lod_levels]
    for lvl in head.lod_levels[1:]:
        lvl.object = None
    clear_pose(arm)
    autorig.bake_seat_pose(arm, game_root)
    scene.update()
    # depois de juntar, o UV ativo é o do atlas do corpo: os slots da cabeça leem o UV dela pelo nome
    huv = head.data.uv_layers.active.name if head.data.uv_layers.active else None
    for m in head.data.materials:
        for s in (m.texture_slots if m else []):
            if huv and s and s.texture_coords == 'UV' and not s.uv_layer:
                s.uv_layer = huv
    parts = []
    for ob in (body, head):
        me = ob.to_mesh(scene, True, 'PREVIEW')
        o = bpy.data.objects.new("_p_" + ob.name, me)
        scene.objects.link(o)
        o.matrix_world = ob.matrix_world.copy()
        parts.append(o)
    for o in scene.objects:
        o.select = o in parts
    scene.objects.active = parts[0]
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.join()
    whole = scene.objects.active
    whole.name = whole.data.name = "CorpoSentado"
    # espaço do Body: o cartão herda origem/eixos do objeto e vira malha de LOD dele
    whole.data.transform(body.matrix_world.inverted())
    whole.matrix_world = body.matrix_world.copy()
    clear_pose(arm)
    autorig._select_only(whole)
    scene.update()
    bpy.ops.object.bake_box_impostor(resolution=resolution, mode='AUTO', normal_map=True,
                                     use_lod=True, lod_distance=BODY_IMPOSTOR_DIST)
    card = next((l.object for l in whole.lod_levels[1:] if l.object), None)
    if card is None:
        raise RuntimeError("bake_box_impostor não criou o cartão do corpo")
    card.name = card.data.name = "CorpoSentado_impostor"
    for lvl, obj in zip(head.lod_levels, head_lods):
        lvl.object = obj
    return card


def add_body_impostor(body, fp_body, head, card, name, distance=BODY_IMPOSTOR_DIST, lod2=BODY_IMPOSTOR_LOD2):
    """O cartão vira o último nível do Body<Grupo>. A Cabeca (impostor) e o Body<Grupo>.001 ganham um nível
    use_invisible_mesh BODY_CARD_HEAD_MARGIN depois (o cartão já tem cabeça: nunca fica sem cabeça na troca) e
    todos a mesma folga em metros (match_lod_hysteresis). lod_max_ragdoll: o componente Ragdoll do jogo
    trava o LOD nesse nível (lodLevelMax da engine) enquanto o piloto cai: caído ele não está sentado."""
    if body.get("corpo_impostor"):
        raise RuntimeError("%s já tem o impostor do corpo: refaça a etapa fechar antes" % body.name)
    group = body.name[len("Body"):] if body.name.startswith("Body") else name
    card.name = card.data.name = "Corpo%s_impostor" % group
    for m in card.data.materials:
        if m and not m.name.startswith(name + "_"):
            m.name = "%s_corpo_%s" % (name, m.name)
    for im in bpy.data.images:
        if im.name.startswith("CorpoSentado"):
            im.name = im.name.replace("CorpoSentado", "Corpo" + group, 1)
    if card.name not in bpy.context.scene.objects:
        bpy.context.scene.objects.link(card)
    card.layers = [i == autorig.HIDDEN_LAYER for i in range(20)]
    card.parent = None
    card.matrix_world = body.matrix_world.copy()

    def level(ob, obj, dist, invisible=False):
        autorig._select_only(ob)
        bpy.ops.object.lod_add()
        lvl = ob.lod_levels[-1]
        lvl.object = obj
        lvl.distance = dist
        lvl.use_mesh = lvl.use_material = True
        lvl.use_invisible_mesh = invisible
        return lvl

    for ob in (body, fp_body):
        if ob is not None and lod2 and len(ob.lod_levels) > 2:
            ob.lod_levels[2].distance = min(ob.lod_levels[2].distance, lod2)
    level(body, card, distance)
    autorig._prop(body, "lod_max_ragdoll", len(body.lod_levels) - 2)   # propriedade de jogo
    for ob in (fp_body, head):
        if ob is None or len(ob.lod_levels) < 2:
            continue
        level(ob, None, distance + BODY_CARD_HEAD_MARGIN, invisible=True)   # sem objeto: senão a engine fixa a origem da distância nele
        autorig._prop(ob, "lod_max_ragdoll", len(ob.lod_levels) - 2)
    match_lod_hysteresis([body, fp_body, head])
    body["corpo_impostor"] = card.name
    return {"cartao": card.name, "distancia": distance, "lod2": lod2,
            "corpo": [(l.object.name if l.object else None, round(l.distance, 2), l.object_hysteresis_percentage)
                      for l in body.lod_levels],
            "cabeca": [(round(l.distance, 2), l.use_invisible_mesh) for l in head.lod_levels],
            "lod_max_ragdoll": {o.name: o.game.properties["lod_max_ragdoll"].value for o in (body, fp_body, head)
                                if o and "lod_max_ragdoll" in o.game.properties}}


# ---------------------------------------------------------------------------------------------------------------------
# Saia solta (vestido longo): ossos extras na barra, movidos por script (mola) no jogo
# ---------------------------------------------------------------------------------------------------------------------
SKIRT_SECTORS = 6          # correntes em volta da saia (6x2 = 12 grupos: o corpo fica em 51+12 = 63 <= 64, GPU skinning)
SKIRT_LINKS = 2            # ossos por corrente (joelho -> meio -> barra)
SKIRT_FREE_TOP = 0.05      # m acima do joelho: a roupa começa a se soltar das pernas
SKIRT_FREE_BOTTOM = 0.07   # m abaixo do joelho: solta por inteiro
SKIRT_PREFIX = "Skirt"


def _smoothstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3.0 - 2.0 * t)


def skirt_bone_names():
    return ["%s%d_%d" % (SKIRT_PREFIX, i, k + 1) for i in range(SKIRT_SECTORS) for k in range(SKIRT_LINKS)]


def add_skirt_bones(arm, dress, sectors=SKIRT_SECTORS, links=SKIRT_LINKS, report=print):
    """Cria correntes de ossos na barra do vestido (filhas do osso da perna do mesmo lado) e passa os pesos da barra
    para elas. Acima do joelho a roupa segue as pernas como antes (sentada, o vestido apoia nas coxas); abaixo, os
    ossos da barra podem balançar. Os ossos ficam com o eixo local Z apontando para fora da saia (X = tangente):
    girar em X abre/fecha a barra, em Z balança para o lado."""
    from mathutils import Vector
    dress_z = [v.co.z for v in dress.data.vertices]
    knee = arm.data.bones["mixamorig:LeftLeg"].head_local.z
    hem = min(dress_z)
    cx, cy = 0.0, arm.data.bones["mixamorig:Hips"].head_local.y
    step = (knee - hem) / links
    # raio da saia por altura e ângulo (para pôr cada osso dentro do tecido)
    sector_angle = [(2 * math.pi) * (i + 0.5) / sectors for i in range(sectors)]   # 0 = frente (+Y), cresce para -X? ver abaixo

    def ang(x, y):
        return math.atan2(-(x - cx), y - cy) % (2 * math.pi)   # 0 = +Y (frente), π/2 = -X (esquerda do piloto: x<0)

    def radius_at(z, a):
        best = []
        for v in dress.data.vertices:
            if abs(v.co.z - z) < step * 0.6:
                d = abs((ang(v.co.x, v.co.y) - a + math.pi) % (2 * math.pi) - math.pi)
                if d < math.pi / sectors:
                    best.append(math.hypot(v.co.x - cx, v.co.y - cy))
        return (sum(best) / len(best)) if best else 0.2

    bpy.context.scene.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.data.edit_bones
    names = []
    for i, a in enumerate(sector_angle):
        out = Vector((-math.sin(a), math.cos(a), 0.0))        # direção radial no plano
        left = out.x < 0.0
        parent = eb["mixamorig:%sLeg" % ("Left" if left else "Right")]
        prev = None
        for k in range(links):
            z0 = knee - k * step
            z1 = z0 - step
            r0, r1 = radius_at(z0, a) * 0.85, radius_at(z1, a) * 0.85
            b = eb.new("%s%d_%d" % (SKIRT_PREFIX, i, k + 1))
            b.head = Vector((cx + out.x * r0, cy + out.y * r0, z0))
            b.tail = Vector((cx + out.x * r1, cy + out.y * r1, z1))
            b.align_roll(out)
            b.parent = prev if prev is not None else parent
            b.use_connect = False
            b.use_deform = True
            names.append(b.name)
            prev = b
    bpy.ops.object.mode_set(mode='OBJECT')
    for n in names:
        if n not in dress.vertex_groups:
            dress.vertex_groups.new(n)
    gidx = {n: dress.vertex_groups[n].index for n in names}
    count = 0
    for v in dress.data.vertices:
        z = v.co.z
        s = _smoothstep(knee + SKIRT_FREE_TOP, knee - SKIRT_FREE_BOTTOM, z)   # 0 acima, 1 abaixo
        if s <= 0.0:
            continue
        a = ang(v.co.x, v.co.y)
        w_sec = []
        for i, sa in enumerate(sector_angle):
            d = abs((a - sa + math.pi) % (2 * math.pi) - math.pi)
            w_sec.append(max(0.0, 1.0 - d / (2 * math.pi / sectors)))
        tot = sum(w_sec) or 1.0
        # distribuição entre os elos (1 = perto do joelho, links = barra)
        u = max(0.0, min(1.0, (knee - z) / (knee - hem)))
        link_w = []
        for k in range(links):
            c = (k + 0.5) / links
            link_w.append(max(0.0, 1.0 - abs(u - c) * links))
        lt = sum(link_w) or 1.0
        # pesos originais encolhem para (1 - s)
        old = [(g.group, g.weight) for g in v.groups]
        for gi, w in old:
            dress.vertex_groups[gi].add([v.index], w * (1.0 - s), 'REPLACE')
        for i in range(sectors):
            if w_sec[i] <= 0.0:
                continue
            for k in range(links):
                w = s * (w_sec[i] / tot) * (link_w[k] / lt)
                if w > 0.001:
                    dress.vertex_groups[gidx["%s%d_%d" % (SKIRT_PREFIX, i, k + 1)]].add([v.index], w, 'REPLACE')
        count += 1
    report("saia: %d ossos, %d vértices da roupa movidos para a barra" % (len(names), count))
    return {"ossos": names, "vertices": count}


# ---------------------------------------------------------------------------------------------------------------------
# Rabo de cavalo / trança: corrente de ossos filha do Head, movida por script (mola) no jogo
# ---------------------------------------------------------------------------------------------------------------------
TAIL_LINKS = 3
TAIL_BEHIND = 0.035        # m atrás do fundo do crânio: o que passa disso no cabelo é o rabo (a calota do cabelo fica antes)
TAIL_ROOT_BLEND = 0.04     # m abaixo do alto do rabo: o cabelo se solta da cabeça aos poucos
TAIL_PREFIX = "Tail"
TAIL_Y_BLEND = 0.03        # m: o cabelo só se solta por inteiro 3 cm além do corte (fios da nuca ficam quase na cabeça)


def tail_bone_names(links=TAIL_LINKS):
    return ["%s%d" % (TAIL_PREFIX, k + 1) for k in range(links)]


def add_ponytail_bones(arm, hair, skin, links=TAIL_LINKS, report=print, braid=False):
    """Acha o rabo no cabelo (vértices bem atrás do crânio), põe `links` ossos Tail1..N em cadeia (filhos do Head, de
    cima para baixo pelo centro do rabo em cada altura) e passa os pesos do rabo para eles. O resto do cabelo continua
    100 % Head. Eixos do osso: Y ao longo do rabo, Z para a frente, X para o lado (girar X = balançar para frente/trás,
    girar Z = para o lado)."""
    head_b = arm.data.bones[HEAD_BONE]
    back = min(v.co.y for v in skin.data.vertices if v.co.z > head_b.head_local.z + 0.06 and abs(v.co.x) < 0.08)
    cut = back - TAIL_BEHIND
    if braid:   # trança colada na nuca: tudo abaixo da calota do cabelo e atrás do eixo da cabeça
        z_cap = head_b.head_local.z + 0.13
        tail = [v for v in hair.data.vertices if v.co.z < z_cap and v.co.y < head_b.head_local.y - 0.015]
    else:
        tail = [v for v in hair.data.vertices if v.co.y < cut and v.co.z < head_b.tail_local.z - 0.02]
    if len(tail) < 12:
        report("rabo: nenhum rabo achado (%d vértices atrás de y=%.3f)" % (len(tail), cut))
        return {"ossos": [], "vertices": 0}
    top = max(v.co.z for v in tail)
    bot = min(v.co.z for v in tail)
    span = top - bot
    knots = []
    for j in range(links + 1):
        z = top - span * j / links
        near = [v.co for v in tail if abs(v.co.z - z) <= span / links * 0.6] or [min(tail, key=lambda v: abs(v.co.z - z)).co]
        knots.append(Vector((sum(p.x for p in near) / len(near), sum(p.y for p in near) / len(near), z)))
    bpy.context.scene.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.data.edit_bones
    prev = eb[HEAD_BONE]
    names = tail_bone_names(links)
    for j, n in enumerate(names):
        b = eb.new(n)
        b.head, b.tail = knots[j].copy(), knots[j + 1].copy()
        b.align_roll(Vector((0.0, 1.0, 0.0)))
        b.parent = prev
        b.use_connect = False
        b.use_deform = True
        prev = b
    bpy.ops.object.mode_set(mode='OBJECT')
    for n in names:
        if n not in hair.vertex_groups:
            hair.vertex_groups.new(n)
    gidx = {n: hair.vertex_groups[n].index for n in names}
    count = 0
    for v in tail:
        u = (top - v.co.z) / span                       # 0 no alto do rabo, 1 na ponta
        s = _smoothstep(0.0, TAIL_ROOT_BLEND / span, top - v.co.z) * (1.0 if braid else _smoothstep(cut, cut - TAIL_Y_BLEND, v.co.y))   # 0 = Head, 1 = solto
        old = [(g.group, g.weight) for g in v.groups]
        for gi, w in old:
            hair.vertex_groups[gi].add([v.index], w * (1.0 - s), 'REPLACE')
        lw = [max(0.0, 1.0 - abs(u * links - (j + 0.5))) for j in range(links)]
        lt = sum(lw) or 1.0
        for j in range(links):
            w = s * lw[j] / lt
            if w > 0.001:
                hair.vertex_groups[gidx[names[j]]].add([v.index], w, 'REPLACE')
        count += 1
    report("rabo: %d ossos, %d vértices (do alto z=%.3f à ponta z=%.3f)" % (len(names), count, top, bot))
    return {"ossos": names, "vertices": count, "alto": top, "ponta": bot}


def merge_toes_into_feet(arm, report=print):
    """Junta os pesos de LeftToeBase/RightToeBase no pé (Foot) e apaga esses grupos de todas as malhas: libera 2 dos
    64 grupos do GPU skinning para os ossos da saia/rabo (os dedos do pé ficam dentro da bota)."""
    n = 0
    for o in bpy.data.objects:
        if o.type != 'MESH' or not any(m.type == 'ARMATURE' for m in o.modifiers):
            continue
        for lado in ("Left", "Right"):
            toe = o.vertex_groups.get("mixamorig:%sToeBase" % lado)
            foot = o.vertex_groups.get("mixamorig:%sFoot" % lado)
            if toe is None:
                continue
            if foot is None:
                foot = o.vertex_groups.new("mixamorig:%sFoot" % lado)
            for v in o.data.vertices:
                w = _weight(o, v, toe.name)
                if w > 0.0:
                    foot.add([v.index], w + _weight(o, v, foot.name), 'REPLACE')
                    n += 1
            o.vertex_groups.remove(toe)
    report("dedos do pé fundidos nos pés (%d vértices)" % n)
    return n
