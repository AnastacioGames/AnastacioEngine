"""Kit de modelagem low poly para a Anastacio Engine (API bpy 2.79).

Uso num gerador: sys.path.insert(0, 'tools/modelagem'); from lowpoly_kit import *
Unidades em metros. Convencao: frente do objeto em +X, Z para cima, origem no chao.
"""
import bpy, bmesh, math
from mathutils import Vector, Matrix


def limpar_cena(scn=None):
    scn = scn or bpy.context.scene
    for o in list(scn.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    scn.render.engine = 'BLENDER_GAME'
    return scn


def material(nome, cor, spec=0.3):
    m = bpy.data.materials.get(nome) or bpy.data.materials.new(nome)
    m.diffuse_color = cor
    m.specular_intensity = spec
    return m


def raiz(nome, scn=None):
    scn = scn or bpy.context.scene
    e = bpy.data.objects.new(nome, None)
    scn.objects.link(e)
    e.empty_draw_size = 0.3
    return e


def pivo(nome, pai, loc, tam=0.1):
    """Empty para animar uma peca (roda, guidao, timao)."""
    e = bpy.data.objects.new(nome, None)
    bpy.context.scene.objects.link(e)
    e.parent = pai
    e.location = loc
    e.empty_draw_size = tam
    return e


def objeto(nome, bm, mat, pai=None, suave=False):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(nome)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = suave
    o = bpy.data.objects.new(nome, me)
    bpy.context.scene.objects.link(o)
    o.parent = pai
    return o


def _verts(geom):
    return [e for e in geom if isinstance(e, bmesh.types.BMVert)]


def caixa(bm, centro, tamanho, rot=None):
    """Caixa com centro e tamanho total (x, y, z); rot = (eixo, graus)."""
    r = bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=tamanho, verts=r['verts'])
    if rot:
        bmesh.ops.rotate(bm, verts=r['verts'], cent=(0, 0, 0),
                         matrix=Matrix.Rotation(math.radians(rot[1]), 3, rot[0]))
    bmesh.ops.translate(bm, vec=centro, verts=r['verts'])
    return r['verts']


def cilindro(bm, centro, raio, comprimento, eixo='Y', lados=16, raio2=None):
    """Cilindro/cone. ATENCAO: no 2.79 'diameter1' do create_cone e o RAIO."""
    r = bmesh.ops.create_cone(bm, cap_ends=True, segments=lados, diameter1=raio,
                              diameter2=raio if raio2 is None else raio2, depth=comprimento)
    if eixo == 'Y':
        bmesh.ops.rotate(bm, verts=r['verts'], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, 'X'))
    elif eixo == 'X':
        bmesh.ops.rotate(bm, verts=r['verts'], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, 'Y'))
    bmesh.ops.translate(bm, vec=centro, verts=r['verts'])
    return r['verts']


def tubo(bm, a, b, espessura=0.03):
    """Barra quadrada ligando os pontos a e b (quadro, guidao, alcas)."""
    a, b = Vector(a), Vector(b)
    d = b - a
    r = bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(espessura, espessura, d.length + espessura), verts=r['verts'])
    q = Vector((0, 0, 1)).rotation_difference(d.normalized())
    bmesh.ops.rotate(bm, verts=r['verts'], cent=(0, 0, 0), matrix=q.to_matrix())
    bmesh.ops.translate(bm, vec=(a + b) / 2, verts=r['verts'])


def perfil_extrudado(bm, pontos_xz, largura, y=0.0):
    """Silhueta da vista lateral (lista X,Z em ordem) extrudada em Y. Base de tanque, banco, carenagem."""
    v = [bm.verts.new((x, y - largura / 2, z)) for x, z in pontos_xz]
    f = bm.faces.new(v)
    r = bmesh.ops.extrude_face_region(bm, geom=[f])
    bmesh.ops.translate(bm, vec=(0, largura, 0), verts=_verts(r['geom']))


def roda(nome, pai, centro, raio, largura, mat_pneu, mat_aro, eixo='Y'):
    """Roda com empty proprio (gira no eixo Y local)."""
    e = pivo(nome, pai, centro, raio)
    bm = bmesh.new(); cilindro(bm, (0, 0, 0), raio, largura, eixo, 20)
    objeto(nome + "_Pneu", bm, mat_pneu, e)
    bm = bmesh.new(); cilindro(bm, (0, 0, 0), raio * 0.62, largura + 0.01, eixo, 20)
    objeto(nome + "_Aro", bm, mat_aro, e)
    return e


def luz_e_camera(alvo, distancia=3.0, scn=None):
    scn = scn or bpy.context.scene
    sun = bpy.data.objects.new("Sun", bpy.data.lamps.new("Sun", "SUN"))
    scn.objects.link(sun)
    sun.rotation_euler = (math.radians(50), 0, math.radians(30))
    cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    scn.objects.link(cam)
    alvo = Vector(alvo)
    cam.location = alvo + Vector((0.75, -0.65, 0.45)).normalized() * distancia
    cam.rotation_euler = (alvo - cam.location).to_track_quat('-Z', 'Y').to_euler()
    scn.camera = cam
    w = scn.world or bpy.data.worlds.new("World")
    scn.world = w
    w.horizon_color = (0.6, 0.65, 0.7)
    w.mist_settings.use_mist = False


# ---------------------------------------------------------------------------
# Ferramentas para modelos mais detalhados (superficies curvas, pecas torneadas)

def material_fino(nome, cor, spec=0.5, dureza=50, alpha=1.0):
    m = material(nome, cor, spec)
    m.specular_hardness = dureza
    if alpha < 1.0:
        m.use_transparency = True
        m.alpha = alpha
        m.game_settings.alpha_blend = 'ALPHA'
    return m


def prender(o, pai):
    """Parenta mantendo a posicao no mundo (pivo inclinado, ex.: direcao)."""
    bpy.context.scene.update()
    o.parent = pai
    o.matrix_parent_inverse = pai.matrix_world.inverted()


def aplicar_subsurf(o, niveis=2, suave=True):
    """Subdivide e aplica (o jogo recebe a malha final, sem custo de modificador)."""
    m = o.modifiers.new("Subsurf", 'SUBSURF')
    m.levels = niveis
    me = o.to_mesh(bpy.context.scene, True, 'PREVIEW')
    o.modifiers.remove(m)
    velho = o.data
    o.data = me
    me.name = o.name
    if velho.users == 0:
        bpy.data.meshes.remove(velho)
    for p in me.polygons:
        p.use_smooth = suave
    return o


def suavizar(o, angulo=40):
    """Smooth com auto smooth: curvas lisas e quinas vivas (pecas mecanicas)."""
    for p in o.data.polygons:
        p.use_smooth = True
    o.data.use_auto_smooth = True
    o.data.auto_smooth_angle = math.radians(angulo)
    return o


def anel(n, w, h, zc, p=0.6, yc=0.0):
    """Secao superelipse (p<1 = mais quadrada); retorna lista de (y, z)."""
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        c, s = math.cos(a), math.sin(a)
        pts.append((yc + w * math.copysign(abs(c) ** p, c), zc + h * math.copysign(abs(s) ** p, s)))
    return pts


def loft(bm, secoes, n=16, tampas=True):
    """Superficie por secoes ao longo de X: secoes = [(x, w, h, zc, p[, yc])].
    Base para tanque, carenagem, rabeta, banco, longarinas (use aplicar_subsurf depois)."""
    aneis = []
    for s in secoes:
        x, w, h, zc, p = s[:5]
        yc = s[5] if len(s) > 5 else 0.0
        aneis.append([bm.verts.new((x, y, z)) for y, z in anel(n, w, h, zc, p, yc)])
    for a, b in zip(aneis, aneis[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], b[j], b[i]))
    if tampas:
        bm.faces.new(aneis[0])
        bm.faces.new(list(reversed(aneis[-1])))


def torneado(bm, perfil, centro, lados=32, fechado=True, a0=0.0, a1=None):
    """Gira um perfil (r, y) em volta do eixo Y: pneu, aro, disco, tampa, farol.
    a0/a1 em radianos para arcos parciais (paralama)."""
    cheio = a1 is None
    a1 = 2 * math.pi if cheio else a1
    nseg = lados if cheio else lados + 1
    cx, cy, cz = centro
    aneis = []
    for r, y in perfil:
        ring = []
        for j in range(nseg):
            a = a0 + (a1 - a0) * j / float(lados)
            ring.append(bm.verts.new((cx + r * math.cos(a), cy + y, cz + r * math.sin(a))))
        aneis.append(ring)
    pares = list(zip(aneis, aneis[1:]))
    if fechado:
        pares.append((aneis[-1], aneis[0]))
    for a, b in pares:
        for j in range(lados):
            k = (j + 1) % nseg
            bm.faces.new((a[j], a[k], b[k], b[j]))


def tubo_curva(nome, pontos, raio, mat, pai=None, ordem=3, ciclico=False, res=10):
    """Tubo liso por NURBS (escapamento, cabos, corrente, mola) ja convertido em malha."""
    cu = bpy.data.curves.new(nome, 'CURVE')
    cu.dimensions = '3D'
    cu.fill_mode = 'FULL'
    cu.bevel_depth = raio
    cu.bevel_resolution = 3
    cu.resolution_u = res
    sp = cu.splines.new('NURBS')
    sp.points.add(len(pontos) - 1)
    for p, c in zip(sp.points, pontos):
        p.co = (c[0], c[1], c[2], 1.0)
    sp.order_u = min(ordem, len(pontos))
    sp.use_endpoint_u = not ciclico
    sp.use_cyclic_u = ciclico
    tmp = bpy.data.objects.new(nome + "_tmp", cu)
    bpy.context.scene.objects.link(tmp)
    me = tmp.to_mesh(bpy.context.scene, True, 'PREVIEW')
    bpy.data.objects.remove(tmp, do_unlink=True)
    bpy.data.curves.remove(cu)
    me.name = nome
    me.materials.clear()
    me.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = True
    o = bpy.data.objects.new(nome, me)
    bpy.context.scene.objects.link(o)
    o.parent = pai
    return o


def atlas_de_paleta(objs, nome="Atlas", cel=16, degrade=0.35):
    """Troca os materiais de cor dos meshes por UM material com textura de paleta.

    Cada cor vira um bloco do atlas com degrade vertical (escuro embaixo); o UV de
    cada face cai no bloco da sua cor e sobe no degrade pela altura (Z) do vertice.
    Filtro 'closest' (sem interpolacao/mipmap) para cores limpas. Retorna o material.
    """
    # transparentes (vidro, lanterna) ficam com o material proprio
    meshes = [o for o in objs if o.type == 'MESH' and o.data.materials
              and not any(m and m.use_transparency for m in o.data.materials)]
    cores = []
    for o in meshes:
        for m in o.data.materials:
            if m and m not in cores:
                cores.append(m)
    n = max(1, int(math.ceil(math.sqrt(len(cores)))))
    lado = n * cel
    img = bpy.data.images.new(nome, lado, lado, alpha=False)
    px = [0.0] * (lado * lado * 4)
    for i, m in enumerate(cores):
        cx, cy = (i % n) * cel, (i // n) * cel
        for yy in range(cel):
            f = 1.0 - degrade * (1.0 - yy / float(cel - 1))
            for xx in range(cel):
                k = ((cy + yy) * lado + cx + xx) * 4
                px[k:k + 4] = [m.diffuse_color[0] * f, m.diffuse_color[1] * f, m.diffuse_color[2] * f, 1.0]
    img.pixels = px
    img.pack(as_png=True)

    tex = bpy.data.textures.new(nome, 'IMAGE')
    tex.image = img
    tex.use_interpolation = False
    tex.use_mipmap = False
    tex.filter_type = 'BOX'
    mat = material(nome, (1, 1, 1), 0.3)
    slot = mat.texture_slots.add()
    slot.texture = tex
    slot.texture_coords = 'UV'

    zs = [(o.matrix_world * v.co).z for o in meshes for v in o.data.vertices]
    z0, z1 = min(zs), max(zs)
    for o in meshes:
        me = o.data
        mats = list(me.materials)
        uv = me.uv_textures.new(nome)
        lay = me.uv_layers[uv.name]
        for p in me.polygons:
            i = cores.index(mats[p.material_index]) if mats and mats[p.material_index] in cores else 0
            u0, v0 = (i % n) * cel, (i // n) * cel
            for li in p.loop_indices:
                z = (o.matrix_world * me.vertices[me.loops[li].vertex_index].co).z
                t = (z - z0) / (z1 - z0) if z1 > z0 else 0.5
                lay.data[li].uv = ((u0 + cel * 0.5) / lado, (v0 + 0.5 + t * (cel - 1)) / lado)
            uv.data[p.index].image = img
        me.materials.clear()
        me.materials.append(mat)
    return mat


def relatorio(caminho, scn=None):
    """Grava nome, tipo e dimensoes de cada objeto (para conferir escala)."""
    scn = scn or bpy.context.scene
    with open(caminho, "w") as f:
        for o in scn.objects:
            f.write("%s %s %s\n" % (o.name, o.type, tuple(round(x, 3) for x in o.dimensions)))
