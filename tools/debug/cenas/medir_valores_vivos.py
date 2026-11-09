"""Mede se ajustar valores (material, textura, lamp, mundo) recompila shaders na viewport.

Roda dentro do editor, por tools/testes_engine/controle.py:
  controle.py py "exec(open(r'tools/debug/cenas/medir_valores_vivos.py').read())"
Em 'resultado' fica um dict campo -> ms do redraw. Referencia: 'FORCA_RECOMPILAR'.
"""
import bpy, time, json

N = 60
for o in list(bpy.data.objects):
    bpy.context.scene.objects.unlink(o)
    bpy.data.objects.remove(o)
sc = bpy.context.scene
img = bpy.data.images.new("TEX", 64, 64)
tex = bpy.data.textures.new("T", 'IMAGE')
tex.image = img
mats = []
for i in range(N):
    bpy.ops.mesh.primitive_uv_sphere_add(location=((i % 10) * 2.5, (i // 10) * 2.5, 0))
    m = bpy.data.materials.new("M%d" % i)
    m.diffuse_color = (i / N, 1 - i / N, .5)
    m.emit = i * 0.001
    s = m.texture_slots.add()
    s.texture = tex
    bpy.context.object.data.materials.append(m)
    mats.append(m)
bpy.ops.object.lamp_add(type='SPOT', location=(12, 7, 15))
spot = bpy.context.object.data
spot.use_shadow = True
bpy.ops.object.lamp_add(type='HEMI', location=(0, 0, 10))
if not sc.world:
    sc.world = bpy.data.worlds.new("W")
win = bpy.context.window
area = next(a for a in bpy.context.screen.areas if a.type == 'VIEW_3D')
area.spaces.active.viewport_shade = 'MATERIAL'
over = {'window': win, 'screen': bpy.context.screen, 'area': area,
        'region': next(r for r in area.regions if r.type == 'WINDOW')}

def redraw():
    t = time.perf_counter()
    bpy.ops.wm.redraw_timer(over, type='DRAW', iterations=1)
    return (time.perf_counter() - t) * 1000

primeira = redraw(); redraw()
base = sum(redraw() for _ in range(3)) / 3
r = {'BASE_ms': round(base, 2), 'PRIMEIRO_DRAW_COMPILA': round(primeira, 2)}
m = mats[0]; sl = m.texture_slots[0]; w = sc.world
casos = [
    ('diffuse_color', m, 'diffuse_color', (.9, .1, .1)), ('specular_color', m, 'specular_color', (.2, .9, .1)),
    ('alpha', m, 'alpha', .4), ('diffuse_intensity', m, 'diffuse_intensity', .3),
    ('specular_intensity', m, 'specular_intensity', .9), ('specular_hardness', m, 'specular_hardness', 200),
    ('emit', m, 'emit', .6), ('ambient', m, 'ambient', .2), ('translucency', m, 'translucency', .4),
    ('slot.diffuse_color_factor', sl, 'diffuse_color_factor', .5), ('slot.alpha_factor', sl, 'alpha_factor', .5),
    ('slot.offset', sl, 'offset', (.2, .1, 0)), ('slot.scale', sl, 'scale', (2, 2, 1)),
    ('spot.spot_size', spot, 'spot_size', .9), ('spot.bias', spot, 'shadow_buffer_bias', 2.0),
    ('spot.shadow_color', spot, 'shadow_color', (.3, 0, 0)), ('world.horizon', w, 'horizon_color', (.1, .4, .8)),
]
for nome, obj, attr, val in casos:
    setattr(obj, attr, val)
    r[nome] = round(redraw(), 2)
for v in (50, 80, 120, 300):
    m.specular_hardness = v
    r['specular_hardness=%d' % v] = round(redraw(), 2)
for mt in mats:
    mt.update_tag()
sc.update()
r['FORCA_RECOMPILAR'] = round(redraw(), 2)
resultado = r
