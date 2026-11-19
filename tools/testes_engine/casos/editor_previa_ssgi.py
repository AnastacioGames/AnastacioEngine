"""Prévia na 3D View, Fase 3c (docs/plano-previa-viewport.md): Native SSGI do jogo (Scene > Native SSGI)
na viewport com Game Preview > SSGI, em shading Material. Os materiais escrevem os 4 buffers do SSGI
durante o desenho dos objetos e os passes do jogo (trace + composição) somam a luz rebatida: com o
toggle a imagem fica mais clara perto das paredes, sem pixels inválidos (NaN vira preto/rosa)."""
from PIL import Image, ImageChops, ImageStat
from rodar import py

CENA = '''
from mathutils import Vector
sc = bpy.context.scene
sc.render.engine = 'BLENDER_GAME'
sc.game_settings.use_shading_nodes = True
sc['ae_ssgi_use'] = True
sc['ae_ssgi_rays'] = 8
sc['ae_ssgi_steps'] = 16
sc['ae_ssgi_radius'] = 5.0
sc['ae_ssgi_divisor'] = 2
sc['ae_ssgi_thickness'] = 0.15
sc['ae_ssgi_strength'] = 2.0
sc['ae_ssgi_denoise'] = 1
w = bpy.data.worlds.new('W')
w.horizon_color = (0, 0, 0)
sc.world = w

def mat(nome, cor):
    m = bpy.data.materials.new(nome)
    m.use_nodes = True
    m.node_tree.nodes.clear()
    s = m.node_tree.nodes.new('ShaderNodeBsdfDiffuse')
    s.inputs['Color'].default_value = cor
    o = m.node_tree.nodes.new('ShaderNodeOutputMaterial')
    m.node_tree.links.new(s.outputs[0], o.inputs['Surface'])
    return m

def cubo(loc, esc, m):
    bpy.ops.mesh.primitive_cube_add(radius=1, location=loc)
    ob = sc.objects.active
    ob.scale = esc
    ob.data.materials.append(m)

cubo((0, 0, -0.1), (4, 4, 0.1), mat('Chao', (0.7, 0.7, 0.7, 1)))
cubo((-1.5, 0, 1.5), (0.1, 2.5, 1.5), mat('Vermelha', (0.9, 0.02, 0.02, 1)))
cubo((0, 2.6, 1.5), (3, 0.1, 1.5), mat('Branca', (0.8, 0.8, 0.8, 1)))
sol = bpy.data.objects.new('Sol', bpy.data.lamps.new('Sol', 'SUN'))
sc.objects.link(sol)
sol.rotation_euler = Vector((-1, 0.5, -2)).to_track_quat('-Z', 'Y').to_euler()
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
sc.objects.link(cam)
cam.location = (7, -9, 6)
cam.rotation_euler = (Vector((0, 0, 1)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
cam.data.lens = 28
sc.camera = cam
'''

PREPARAR = '''
import bpy
for a in bpy.context.screen.areas:
    if a.type == 'VIEW_3D':
        sp = a.spaces.active
        sp.region_3d.view_perspective = 'CAMERA'
        sp.viewport_shade = 'MATERIAL'
        sp.show_only_render = True
        sp.fx_settings.use_game_ssgi = %s
        r = [r for r in a.regions if r.type == 'WINDOW'][0]
        caixa = (r.x, bpy.context.window.height - r.y - r.height, r.x + r.width, bpy.context.window.height - r.y)
bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=3)
resultado = list(caixa)
'''


def recorte(e, png, caixa):
    e.pedir("tela", arquivo=png)
    im = Image.open(png).convert('RGB').crop(caixa)
    w, h = im.size
    im = im.crop((w // 10, h // 10, w * 9 // 10, h * 8 // 10))
    im.save(png)
    return im


def testar(t):
    cena = t.gerar(CENA)
    e = t.editor(cena)

    caixa = py(e, PREPARAR % 'False')
    off = recorte(e, str(t.pasta / 'off.png'), caixa)
    caixa = py(e, PREPARAR % 'True')
    on = recorte(e, str(t.pasta / 'on.png'), caixa)
    on2 = recorte(e, str(t.pasta / 'on2.png'), caixa)

    m_off, m_on = ImageStat.Stat(off).mean, ImageStat.Stat(on).mean
    ganho = sum(m_on) / 3 - sum(m_off) / 3
    tremor = sum(ImageStat.Stat(ImageChops.difference(on, on2)).mean) / 3
    # rosa de shader quebrado / NaN: pixels quase (255, 0, 255)
    rosa = sum(1 for p in on.getdata() if p[0] > 200 and p[1] < 40 and p[2] > 200)
    t.nota('média RGB sem SSGI %s, com SSGI %s; ganho %.2f; diferença entre redesenhos %.3f; rosa %d'
           % ([round(v, 1) for v in m_off], [round(v, 1) for v in m_on], ganho, tremor, rosa))
    assert ganho > 1.0, 'o SSGI não somou luz rebatida'
    assert ganho < 60.0, 'o SSGI estourou a imagem'
    assert rosa == 0, 'pixels de shader quebrado'
    assert tremor < 0.5, 'o SSGI muda entre redesenhos com a vista parada'
