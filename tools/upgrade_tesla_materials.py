"""Apply editable procedural PBR materials to an existing Tesla piano scene.

RangeEngine -b TeslaPiano.range --python tools/upgrade_tesla_materials.py
Writes a sibling TeslaPiano_PBR.range; preserves the source and game logic.
"""
import bpy
import os


def node(tree, kind, label, x, y):
    n = tree.nodes.new(kind)
    n.label = label
    n.location = (x, y)
    return n


def ramp(tree, label, colors, x, y):
    n = node(tree, 'ShaderNodeValToRGB', label, x, y)
    for e, (pos, color) in zip(n.color_ramp.elements, colors):
        e.position = pos
        e.color = color
    return n


def material(name, color, metallic, roughness, style):
    m = bpy.data.materials.new('Anastacio_' + name)
    m.diffuse_color = color[:3]
    m.use_nodes = True
    t = m.node_tree
    t.nodes.clear()
    out = node(t, 'ShaderNodeOutputMaterial', 'Saida PBR', 850, 150)
    p = node(t, 'ShaderNodeBsdfPrincipled', name, 550, 150)
    p.inputs['Base Color'].default_value = color
    p.inputs['Metallic'].default_value = metallic
    p.inputs['Roughness'].default_value = roughness
    t.links.new(p.outputs[0], out.inputs['Surface'])
    coord = node(t, 'ShaderNodeTexCoord', 'Coordenadas locais', -1050, 100)
    noise = node(t, 'ShaderNodeTexNoise', 'Microtextura', -650, -220)
    noise.inputs['Scale'].default_value = 85
    noise.inputs['Detail'].default_value = 2
    t.links.new(coord.outputs['Generated'], noise.inputs['Vector'])
    bump = node(t, 'ShaderNodeBump', 'Relevo sutil', 310, -130)
    bump.inputs['Strength'].default_value = 0.18
    bump.inputs['Distance'].default_value = 0.015
    t.links.new(noise.outputs['Fac'], bump.inputs['Height'])
    t.links.new(bump.outputs['Normal'], p.inputs['Normal'])
    if style == 'copper':
        wave = node(t, 'ShaderNodeTexWave', 'Espiras de cobre', -650, 220)
        wave.wave_type = 'BANDS'
        wave.inputs['Scale'].default_value = 65
        wave.inputs['Distortion'].default_value = 0
        separate = node(t, 'ShaderNodeSeparateXYZ', 'Altura da bobina', -850, 380)
        combine = node(t, 'ShaderNodeCombineXYZ', 'Espiras horizontais', -650, 480)
        t.links.new(coord.outputs['Generated'], separate.inputs[0])
        t.links.new(separate.outputs['Z'], combine.inputs['X'])
        t.links.new(combine.outputs[0], wave.inputs['Vector'])
        c = ramp(t, 'Cobre / sulcos escuros', [(0.18, (0.045, 0.012, 0.005, 1)), (0.48, color)], -300, 240)
        t.links.new(wave.outputs['Fac'], c.inputs[0])
        t.links.new(c.outputs['Color'], p.inputs['Base Color'])
        t.links.new(wave.outputs['Fac'], bump.inputs['Height'])
        bump.inputs['Distance'].default_value = 0.025
    elif style == 'floor':
        noise.inputs['Scale'].default_value = 3.5
        t.links.new(coord.outputs['Object'], noise.inputs['Vector'])
        c = ramp(t, 'Concreto escuro', [(0.2, (0.012, 0.018, 0.024, 1)), (0.8, color)], -300, 240)
        t.links.new(noise.outputs['Fac'], c.inputs[0])
        t.links.new(c.outputs['Color'], p.inputs['Base Color'])
        wet = node(t, 'ShaderNodeTexNoise', 'Distribuicao das pocas', -650, -500)
        wet.inputs['Scale'].default_value = 0.35
        wet.inputs['Detail'].default_value = 2
        t.links.new(coord.outputs['Object'], wet.inputs['Vector'])
        r = ramp(t, 'Molhado / seco', [(0.43, (0.07, 0.07, 0.07, 1)), (0.60, (0.65, 0.65, 0.65, 1))], -300, -430)
        t.links.new(wet.outputs['Fac'], r.inputs[0])
        t.links.new(r.outputs['Color'], p.inputs['Roughness'])
        bump.inputs['Distance'].default_value = 0.035
    else:
        r = ramp(t, 'Variacao de rugosidade', [(0.15, (roughness * 0.65,) * 3 + (1,)), (0.85, (min(roughness * 1.4, 1),) * 3 + (1,))], -300, 200)
        t.links.new(noise.outputs['Fac'], r.inputs[0])
        t.links.new(r.outputs['Color'], p.inputs['Roughness'])
    return m


source = bpy.data.filepath
if not source:
    raise RuntimeError('Abra primeiro a cena TeslaPiano.range')
materials = {
    'copper': material('Cobre_Bobinado', (0.55, 0.205, 0.065, 1), 0.95, 0.27, 'copper'),
    'steel': material('Aco_Escovado', (0.48, 0.54, 0.62, 1), 0.95, 0.23, 'steel'),
    'base': material('Base_Grafite', (0.025, 0.032, 0.043, 1), 0.65, 0.36, 'base'),
    'floor': material('Concreto_Molhado', (0.09, 0.105, 0.12, 1), 0.05, 0.4, 'floor'),
}
glow = bpy.data.materials.new('Anastacio_Terminal_Emissivo')
glow.use_nodes = True
t = glow.node_tree
t.nodes.clear()
e = node(t, 'ShaderNodeEmission', 'Luz azul do terminal', 0, 0)
e.inputs['Color'].default_value = (0.22, 0.48, 1, 1)
e.inputs['Strength'].default_value = 2
out = node(t, 'ShaderNodeOutputMaterial', 'Saida', 250, 0)
t.links.new(e.outputs[0], out.inputs['Surface'])
changed = []
for ob in bpy.data.objects:
    if not hasattr(ob.data, 'materials'):
        continue
    name = ob.name
    mat = None
    if name == 'Chao':
        mat = materials['floor']
    elif name == 'Haste_Central' or (name.startswith('Bobina_') and '_Toro' in name):
        mat = materials['steel']
    elif name.startswith('Bobina_'):
        mat = materials['base'] if '_Base' in name else materials['copper']
    elif name == 'Terminal' or name.startswith('Tecla_'):
        mat = glow
    if mat:
        ob.data.materials.clear()
        ob.data.materials.append(mat)
        for poly in getattr(ob.data, 'polygons', []):
            poly.material_index = 0
        changed.append(name)
for scene in bpy.data.scenes:
    scene.game_settings.use_shading_nodes = True
    # Hemi is unsupported by Game PBR: retain its transform and use a soft Sun.
    for ob in scene.objects:
        if ob.type == 'LAMP' and ob.data.type == 'HEMI':
            ob.data.type = 'SUN'
            ob.data.energy = 0.35
            ob.data.color = (0.38, 0.52, 0.75)
output = os.path.splitext(source)[0] + '_PBR.range'
bpy.ops.wm.save_as_mainfile(filepath=output)
print('TESLA_PBR_SAVED', output, 'objects', len(changed), flush=True)
