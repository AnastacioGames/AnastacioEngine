# Cena de teste da luz ambiente do World por SH9: céu em imagem (gerada aqui, empacotada) com sol forte,
# lado +X vermelho, lado -X azul e chão verde; esferas brancas/coloridas e um piso mostram de onde vem a luz.
# Uso: AnastacioEngine.exe -b --factory-startup --python criar_cena_sh9_ambiente.py -- saida.range
# Env: TESTE_SH9_MAPA=EQUIRECT (padrão), ANGMAP ou CUBE; TESTE_SH9_LEGADO=1 usa materiais antigos (sem nós);
#      TESTE_SH9_RELEVO=1 põe um Normal Map em faixas inclinadas para ±X (o ambiente deve seguir o relevo);
#      TESTE_SH9_SHOT=<pasta> tira um screenshot no frame 30 e fecha.
import bpy
import math
import os
import sys
from mathutils import Vector

saida = sys.argv[sys.argv.index("--") + 1]
mapa = os.environ.get("TESTE_SH9_MAPA", "EQUIRECT")
legado = os.environ.get("TESTE_SH9_LEGADO") == "1"
shot = os.environ.get("TESTE_SH9_SHOT", "")
relevo = os.environ.get("TESTE_SH9_RELEVO") == "1"

scene = bpy.context.scene
for ob in list(scene.objects):
    scene.objects.unlink(ob)
    bpy.data.objects.remove(ob)
scene.render.engine = 'BLENDER_GAME'
scene.render.use_shadows = True
scene.game_settings.use_shading_nodes = not legado
scene.game_settings.resolution_x = 960
scene.game_settings.resolution_y = 540


def ceu(d):
    """Cor do céu na direção d (x, y, z normalizado)."""
    x, y, z = d
    if z < 0.0:
        return (0.15, 0.45, 0.12)
    c = [0.35 + 0.3 * z, 0.5 + 0.3 * z, 0.9]
    if x > 0.3:
        c = [1.0, 0.15, 0.1]
    elif x < -0.3:
        c = [0.1, 0.2, 1.0]
    sol = Vector((0.3, 0.5, 0.8)).normalized()
    if Vector(d).dot(sol) > 0.97:
        c = [1.0, 1.0, 0.9]
    return tuple(c)


def dir_equirect(u, v):
    phi = (0.5 - u) * 2.0 * math.pi
    theta = (v - 0.5) * math.pi
    return (math.cos(theta) * math.cos(phi), math.cos(theta) * math.sin(phi), math.sin(theta))


def dir_angular(u, v):
    # inverso de uv_angular(): (2u - 1, 2v - 1) = (x, z) / div, div = sqrt(2 (1 - y)), logo r^2 = (1 + y) / 2
    a, b = 2.0 * u - 1.0, 2.0 * v - 1.0
    r2 = a * a + b * b
    if r2 > 1.0:
        return (0.0, 1.0, 0.0)
    y = 2.0 * r2 - 1.0
    div = math.sqrt(max(2.0 * (1.0 - y), 0.0))
    return (a * div, y, b * div)


def dir_cube(col, row, w):
    """Direção do texel (col, row) da cruz 3x2 de gpu_gen_cube_map() (linha 0 = embaixo)."""
    rh = 2 * w
    if row < w:
        if col >= 2 * w:
            f, s, t = 2, col - 2 * w, row
        elif col >= w:
            f, s, t = 4, col - w, row
        else:
            f, s, t = 5, w - 1 - col, w - 1 - row
    else:
        if col >= 2 * w:
            # +X (s = rh-1-row, t = col-2w) e -Y (s = 2w-1-col, t = rh-1-row) dividem a metade de cima
            f, s, t = 0, rh - 1 - row, col - 2 * w
        elif col >= w:
            f, s, t = 3, 2 * w - 1 - col, rh - 1 - row
        else:
            f, s, t = 1, row - w, w - 1 - col
    sc = (s + 0.5) / w * 2.0 - 1.0
    tc = (t + 0.5) / w * 2.0 - 1.0
    d = {0: (1.0, -tc, -sc), 1: (-1.0, -tc, sc), 2: (sc, 1.0, tc),
         3: (sc, -1.0, -tc), 4: (sc, -tc, 1.0), 5: (-sc, -tc, -1.0)}[f]
    return tuple(Vector(d).normalized())


if mapa == "CUBE":
    w = 64
    largura, altura = 3 * w, 2 * w
else:
    largura, altura = (512, 256) if mapa == "EQUIRECT" else (256, 256)
img = bpy.data.images.new("CeuSH9", largura, altura)
px = []
for j in range(altura):
    for i in range(largura):
        if mapa == "CUBE":
            d = dir_cube(i, j, w)
        elif mapa == "EQUIRECT":
            d = dir_equirect((i + 0.5) / largura, (j + 0.5) / altura)
        else:
            d = dir_angular((i + 0.5) / largura, (j + 0.5) / altura)
        c = ceu(d)
        px += [c[0], c[1], c[2], 1.0]
img.pixels = px
img.pack(as_png=True)

tex = bpy.data.textures.new("CeuSH9", 'ENVIRONMENT_MAP' if mapa == "CUBE" else 'IMAGE')
tex.image = img
if mapa == "CUBE":
    tex.environment_map.source = 'IMAGE_FILE'

world = scene.world or bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = False
world.use_sky_blend = False
world.horizon_color = (0.2, 0.2, 0.2)
ls = world.light_settings
ls.use_environment_light = True
ls.environment_color = 'SKY_TEXTURE'
ls.environment_energy = 1.0
slot = world.texture_slots.add()
slot.texture = tex
slot.texture_coords = 'EQUIRECT' if mapa in ("EQUIRECT", "CUBE") else 'ANGMAP'
slot.use_map_horizon = True
slot.use_map_blend = False


def material(nome, cor):
    mat = bpy.data.materials.new(nome)
    mat.diffuse_color = cor
    mat.specular_intensity = 0.0
    if not legado:
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        for n in list(nodes):
            nodes.remove(n)
        bsdf = nodes.new('ShaderNodeBsdfPrincipled')
        bsdf.inputs['Base Color'].default_value = (cor[0], cor[1], cor[2], 1.0)
        bsdf.inputs['Roughness'].default_value = 1.0
        bsdf.inputs['Specular'].default_value = 0.0
        if relevo:
            nm = bpy.data.images.new("RelevoSH9", 64, 64)
            k = 0.7071
            px = []
            for j in range(64):
                for i in range(64):
                    nx = k if (i // 8) % 2 == 0 else -k
                    px += [nx * 0.5 + 0.5, 0.5, k * 0.5 + 0.5, 1.0]
            nm.pixels = px
            nm.pack(as_png=True)
            nm.colorspace_settings.name = 'Non-Color'
            tex_node = nodes.new('ShaderNodeTexImage')
            tex_node.image = nm
            tex_node.color_space = 'NONE'
            nmap = nodes.new('ShaderNodeNormalMap')
            mat.node_tree.links.new(tex_node.outputs['Color'], nmap.inputs['Color'])
            mat.node_tree.links.new(nmap.outputs['Normal'], bsdf.inputs['Normal'])
        out_node = nodes.new('ShaderNodeOutputMaterial')
        mat.node_tree.links.new(bsdf.outputs[0], out_node.inputs[0])
    return mat


branco = material("Branco", (0.8, 0.8, 0.8))
for k, x in enumerate((-3.0, 0.0, 3.0)):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, size=1.2, location=(x, 0.0, 1.2), calc_uvs=True)
    ob = bpy.context.object
    bpy.ops.object.shade_smooth()
    ob.data.materials.append(branco)
bpy.ops.mesh.primitive_plane_add(radius=8.0, location=(0.0, 0.0, 0.0), calc_uvs=True)
bpy.context.object.data.materials.append(branco)

cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
scene.objects.link(cam)
scene.camera = cam
cam.location = (0.0, -9.0, 3.5)
cam.rotation_euler = (Vector((0.0, 0.0, 1.0)) - cam.location).to_track_quat('-Z', 'Y').to_euler()

if shot:
    t = bpy.data.texts.new("shot.py")
    t.write('''import bge
n = 0
def tick(cont):
    global n
    n += 1
    if n == 30:
        bge.render.makeScreenshot(%r)
    if n == 34:
        bge.logic.endGame()
''' % (os.path.join(shot, "sh9_%s%s.png" % (mapa.lower(), ("_legado" if legado else "") + ("_relevo" if relevo else "")))))
    scene.objects.active = cam
    bpy.ops.logic.sensor_add(type='ALWAYS', object=cam.name)
    bpy.ops.logic.controller_add(type='PYTHON', object=cam.name)
    sen = cam.game.sensors[0]
    sen.use_pulse_true_level = True
    con = cam.game.controllers[0]
    con.mode = 'MODULE'
    con.module = 'shot.tick'
    sen.link(con)

bpy.ops.wm.save_as_mainfile(filepath=saida)
