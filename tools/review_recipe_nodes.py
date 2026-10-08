"""Review existing demos without changing their originals (Blender/Range 2.79 API).

RangeEngine -b --python tools/review_recipe_nodes.py -- [demo-name ...]
Copies go to demos/revisados/. Run with --validate-runtime to also create temporary
players with an automatic exit (no screenshots); see demos/revisados/README.md.
"""
import bpy
import json
import os
import sys
import tempfile
import textwrap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(ROOT, "demos", "revisados")
DEMOS = ("parallax_interior_mapping", "triplanar", "dissolve", "escudo",
         "agua", "neve_musgo", "vento", "toon", "lava", "grama_trilha", "pelos")
BLUE = (0.18, 0.26, 0.40)
GREEN = (0.20, 0.34, 0.22)
PURPLE = (0.32, 0.22, 0.40)


def stage(nt, title, explanation, nodes, color=PURPLE):
    f = nt.nodes.new('NodeFrame')
    f.label = title
    f.use_custom_color = True
    f.color = color
    for n in nodes:
        n.parent = f
    note = nt.nodes.new('NodeFrame')
    note.label = 'Explicação — ' + title
    note.text = bpy.data.texts.new('nota revisão — ' + title)
    note.text.write(explanation)
    note['review_stage'] = f.name
    return f


def math_node(nt, op, a, b=0.0, label=None, parent=None):
    n = nt.nodes.new('ShaderNodeMath')
    n.operation = op
    n.label = label or op
    n.hide = True
    n.parent = parent
    for i, v in enumerate((a, b)):
        if isinstance(v, (int, float)):
            n.inputs[i].default_value = float(v)
        else:
            nt.links.new(v, n.inputs[i])
    return n


def find(nt, label):
    return next(n for n in nt.nodes if n.label == label)


def replace_consumers(nt, old, new, consumers):
    for socket in consumers:
        nt.links.new(new, socket)


def fix_dissolve():
    for m in bpy.data.materials:
        if not m.name.startswith('Dissolver ('):
            continue
        nt = m.node_tree
        keep = find(nt, 'fica (> 0)')
        amount = find(nt, 'x 0.76').inputs[0].links[0].from_socket
        targets = [l.to_socket for l in keep.outputs[0].links]
        # Explicit endpoints: the noise distribution is not a contract.
        active = math_node(nt, 'GREATER_THAN', amount, 0.0, 'q > 0')
        done = math_node(nt, 'LESS_THAN', amount, 1.0, 'q < 1')
        intact = math_node(nt, 'SUBTRACT', 1.0, active.outputs[0], 'Inteiro em q = 0')
        cut = math_node(nt, 'MULTIPLY', keep.outputs[0], active.outputs[0], 'Corte intermediário')
        final = math_node(nt, 'ADD', cut.outputs[0], intact.outputs[0], 'Inteiro ou corte')
        final = math_node(nt, 'MULTIPLY', final.outputs[0], done.outputs[0], 'Visibilidade 0..1')
        replace_consumers(nt, keep.outputs[0], final.outputs[0], targets)
        edge = find(nt, 'borda')
        targets = [l.to_socket for l in edge.outputs[0].links]
        edge_final = math_node(nt, 'MULTIPLY', edge.outputs[0], final.outputs[0], 'Brasa só na superfície visível')
        replace_consumers(nt, edge.outputs[0], edge_final.outputs[0], targets)
        width = nt.nodes.new('ShaderNodeValue')
        width.label = 'Largura da brasa'
        width.outputs[0].default_value = 0.025
        nt.links.new(width.outputs[0], find(nt, 'na borda (< largura)').inputs[1])
        nt.links.new(width.outputs[0], find(nt, 'posicao na borda').inputs[1])
        stage(nt, '3b. Controle exato do corte',
              'Quantidade <= 0: objeto inteiro. Quantidade >= 1: desaparece.\n'
              'Entre esses extremos, o ruído define o corte.\n'
              'A brasa aparece apenas na parte que sobrevive ao corte.\n'
              'Largura da brasa controla corte e gradiente juntos; mantenha > 0.',
              [active, done, intact, cut, final.inputs[0].links[0].from_node,
               final, edge_final, width])


def fix_cover():
    nt = bpy.data.node_groups['Cobertura']
    gi = next(n for n in nt.nodes if n.type == 'GROUP_INPUT')
    mask = find(nt, 'mascara')
    targets = [l.to_socket for l in mask.outputs[0].links]
    active = math_node(nt, 'GREATER_THAN', gi.outputs['Amount'], 0.0, 'Quantidade > 0')
    # Use >= 1 exactly, expressed as 1 - (q < 1), supported in 2.79.
    full = math_node(nt, 'LESS_THAN', gi.outputs['Amount'], 1.0, 'Quantidade < 1')
    inv = math_node(nt, 'SUBTRACT', 1.0, full.outputs[0], 'Cobertura completa')
    partial = math_node(nt, 'MULTIPLY', mask.outputs[0], active.outputs[0], 'Nada em q = 0')
    final = math_node(nt, 'MAXIMUM', partial.outputs[0], inv.outputs[0], 'Máscara com extremos exatos')
    replace_consumers(nt, mask.outputs[0], final.outputs[0], targets)
    coord = nt.nodes.new('ShaderNodeTexCoord')
    coord.label = 'Ruído preso ao objeto'
    noise = find(nt, 'Ruido da borda')
    nt.links.new(coord.outputs['Object'], noise.inputs['Vector'])
    stage(nt, '3b. Extremos e estabilidade',
          'Amount <= 0: sem cobertura. Amount >= 1: cobertura completa.\n'
          'Isso vale mesmo com Noise Breakup alto ou Softness grande.\n'
          'A normal continua no mundo: neve fica em cima ao girar.\n'
          'O ruído usa Object: mover o objeto não faz as manchas deslizar.',
          [active, full, inv, partial, final, coord])
    note = next(n for n in nt.nodes if n.type == 'FRAME' and n.text
                and 'Ruido na posicao do mundo' in n.text.as_string())
    note.text.clear()
    note.text.write('Ruído em coordenadas Object somado à normal Z do mundo.\n'
                    'Noise Breakup = irregularidade; Noise Scale = frequência.\n'
                    'Aplique a escala para manter o tamanho das manchas.')


def fix_water():
    nt = bpy.data.materials['Agua Estilizada'].node_tree
    bump = find(nt, 'Relevo das ondas')
    foam = find(nt, 'Cor da espuma')
    nt.links.new(bump.outputs['Normal'], foam.inputs['Normal'])
    for m in bpy.data.materials:
        if m.name not in ('Areia (espuma)', 'Pedra (espuma)'):
            continue
        nt = m.node_tree
        coord = next(n for n in nt.nodes if n.type == 'TEX_COORD')
        geo = nt.nodes.new('ShaderNodeNewGeometry')
        geo.label = 'Nível da água em coordenadas do mundo'
        geo.parent = coord.parent
        for l in list(coord.outputs['Object'].links):
            nt.links.new(geo.outputs['Position'], l.to_socket)
        for note in nt.nodes:
            if note.type == 'FRAME' and note.text:
                value = note.text.as_string().replace(
                    'Aplique transformacoes: usa Object = mundo.',
                    'Geometry Position: nível Z do mundo, mesmo movendo a pedra.')
                note.text.clear()
                note.text.write(value)
    stage(bpy.data.materials['Agua Estilizada'].node_tree,
          '5. Como reutilizar a água',
          'A espuma da água recebe a mesma normal das ondas.\n'
          'A costa usa Z do mundo: faixa de espuma centrada em Z = 0.\n'
          'Cor da água: aproximação pela distância da costa, não profundidade real.\n'
          'Esta receita é opaca; não simula refração nem desloca a malha.', [])


def fix_interior():
    nt = bpy.data.node_groups['Interior Mapping']
    sep = find(nt, 'Tamanho do comodo')
    nodes = []
    for axis, socket in zip('XYZ', sep.outputs):
        targets = [l.to_socket for l in socket.links]
        safe = math_node(nt, 'MAXIMUM', socket, 0.001, 'Tamanho ' + axis + ' >= 1 mm')
        replace_consumers(nt, socket, safe.outputs[0], targets)
        nodes.append(safe)
    nt.inputs['Room Size'].min_value = 0.001
    nt.inputs['Lit Ratio'].min_value = 0.0
    nt.inputs['Lit Ratio'].max_value = 1.0
    stage(nt, '1b. Dimensões seguras',
          'Room Size deve ser positivo em X, Y e Z (metros).\n'
          'Cada divisor é limitado a 0.001 para evitar tamanho zero/negativo.\n'
          'Offset alinha a grade de cômodos; Lit Ratio varia entre 0 e 1.', nodes)


def fix_triplanar():
    nt = bpy.data.materials['Pedra Triplanar'].node_tree
    bw = next(n for n in nt.nodes if n.type == 'RGBTOBW')
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    bump = nt.nodes.new('ShaderNodeBump')
    bump.label = 'Relevo suave da pedra'
    bump.inputs['Strength'].default_value = 0.18
    bump.inputs['Distance'].default_value = 0.04
    nt.links.new(bw.outputs[0], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    stage(nt, '2b. Microrelevo da pedra',
          'Bump usa a luminância da textura já projetada em Box.\n'
          'Strength 0.18 e Distance 0.04: relevo discreto, sem mudar a malha.\n'
          'Coloque Strength = 0 para comparar com o original.\n'
          'É uma altura aproximada pela cor; um height map próprio é melhor.', [bump], GREEN)


def fix_toon():
    # The player converts the base mesh (CDDM_from_mesh), not Solidify's result.
    # Bake only the outline modifier; its flipped normals and material indices
    # must be present in the mesh that the runtime actually receives.
    for ob in bpy.context.scene.objects:
        if ob.type != 'MESH':
            continue
        for modifier in list(ob.modifiers):
            if modifier.type == 'SOLIDIFY' and modifier.name == 'Contorno':
                bpy.context.scene.objects.active = ob
                bpy.ops.object.modifier_apply(modifier=modifier.name)
                outline = next(i for i, m in enumerate(ob.data.materials)
                               if m and m.name == 'Contorno (casco invertido)')
                assert any(p.material_index == outline for p in ob.data.polygons), ob.name
    nt = bpy.data.materials['Contorno (casco invertido)'].node_tree
    for note in nt.nodes:
        if note.type == 'FRAME' and note.text:
            note.text.clear()
            note.text.write('Casco Solidify aplicado na cópia: faces existem na malha do jogo.\n'
                            'Normais invertidas e Backface Culling mostram só a silhueta.\n'
                            'O slot 2 recebe as faces do contorno.\n'
                            'A espessura foi preservada da demo original (casco já gravado).')


def node_height(n):
    if n.hide:
        return 54
    if n.type == 'BSDF_PRINCIPLED':
        return 950
    if n.type == 'MAPPING':
        return 600
    return max(220, 110 + 28 * (len(n.inputs) + len(n.outputs)))


def layout(nt):
    """Lay out each stage by dependencies, with dedicated space for its note.

    Coordinates are assigned AFTER parenting (2.79's parent setter changes local
    coordinates). Fixed frame bounds reserve space for tall Principled nodes.
    """
    frames = [n for n in nt.nodes if n.type == 'FRAME' and not n.text]
    frames.sort(key=lambda n: (n.label, n.name))
    free = [n for n in nt.nodes if n.type != 'FRAME' and n.parent is None]
    inputs = [n for n in free if n.type == 'GROUP_INPUT']
    outputs = [n for n in free if n.type == 'GROUP_OUTPUT']
    auxiliary = [n for n in free if n not in inputs + outputs]
    if inputs:
        frames.insert(0, stage(nt, '0. Entradas do grupo',
                              'Parâmetros usados pelas etapas à direita.', inputs, BLUE))
    if auxiliary:
        frames.append(stage(nt, 'Material auxiliar',
                            'Siga os fios da esquerda para a direita.', auxiliary, BLUE))
    if outputs:
        frames.append(stage(nt, 'Saídas do grupo',
                            'Resultados entregues ao material que usa este grupo.', outputs, BLUE))
    cursor = 0.0
    for f in frames:
        members = [n for n in nt.nodes if n.parent == f and n.type != 'FRAME']
        # Original notes match stage title through their Text datablock name.
        notes = [n for n in nt.nodes if n.type == 'FRAME' and n.text
                 and (n.get('review_stage') == f.name or n.text.name == 'nota - ' + f.label
                      or n.text.name.startswith('nota - ' + f.label + '.'))]
        if not notes:
            note = nt.nodes.new('NodeFrame')
            note.text = bpy.data.texts.new('nota revisão — ' + f.label)
            note.text.write('Etapa: ' + f.label + '\n'
                            'Nós: ' + ', '.join(sorted(set(n.bl_label for n in members))) + '\n'
                            'Siga as conexões da esquerda para a direita.\n'
                            'BSDF define a superfície; Output entrega o resultado ao material.'
                            if any(n.type.startswith('BSDF') for n in members) else
                            'Etapa: ' + f.label + '\n'
                            'Siga as conexões da esquerda para a direita; ajuste os valores nos nós.')
            notes = [note]
        ranks = {}
        pending = list(members)
        while pending:
            ready = [n for n in pending if all(l.from_node not in pending
                     for s in n.inputs for l in s.links)]
            if not ready:
                raise RuntimeError('Ciclo no grupo ' + nt.name + ': ' + f.label)
            for n in ready:
                upstream = [ranks[l.from_node.name] for s in n.inputs for l in s.links
                            if l.from_node.name in ranks]
                ranks[n.name] = max(upstream) + 1 if upstream else 0
                pending.remove(n)
        max_height = 100
        for rank in sorted(set(ranks.values())):
            column = sorted([n for n in members if ranks[n.name] == rank],
                            key=lambda n: (-n.location.y, n.name))
            y = -70
            for n in column:
                n.width = 230
                n.location = (40 + rank * 310, y)
                y -= node_height(n) + 55
            max_height = max(max_height, -y)
        f.shrink = False
        f.label_size = 22
        f.width = max(640, (max(ranks.values()) + 1) * 310 + 40) if ranks else 640
        f.height = max_height + 40
        f.location = (cursor, 0)
        note_y = 70
        for note in notes:
            # Wrap text so the explanation never extends into another stage.
            value = '\n'.join(textwrap.fill(line, 70) for line in note.text.as_string().splitlines())
            note.text.clear()
            note.text.write(value)
            note.shrink = False
            note.label = 'Explicação — ' + f.label
            note.label_size = 18
            note.use_custom_color = True
            note.color = (0.16, 0.16, 0.14)
            note.width = f.width
            note.height = 70 + 24 * len(value.splitlines())
            note.location = (cursor, note_y + note.height)
            note_y += note.height + 30
        cursor += f.width + 140
    for n in nt.nodes:
        n.select = False


def trees():
    result = {}
    for owner in list(bpy.data.materials) + list(bpy.data.worlds) + list(bpy.data.lamps):
        if owner.use_nodes and owner.node_tree:
            result[owner.node_tree.as_pointer()] = owner.node_tree
    for nt in bpy.data.node_groups:
        if nt.bl_idname == 'ShaderNodeTree':
            result[nt.as_pointer()] = nt
    return list(result.values())


def evaluate(socket, overrides):
    """Evaluate actual Math links for endpoint regression checks, without rendering."""
    n = socket.node
    if (n.name, socket.name) in overrides:
        return overrides[(n.name, socket.name)]
    if n.type != 'MATH':
        return overrides[(n.name, socket.name)]
    values = [evaluate(s.links[0].from_socket, overrides) if s.is_linked else s.default_value
              for s in n.inputs[:2]]
    a, b = values
    ops = {'ADD': lambda: a + b, 'SUBTRACT': lambda: a - b,
           'MULTIPLY': lambda: a * b, 'DIVIDE': lambda: a / b if b else 0,
           'MAXIMUM': lambda: max(a, b), 'MINIMUM': lambda: min(a, b),
           'GREATER_THAN': lambda: float(a > b), 'LESS_THAN': lambda: float(a < b)}
    value = ops[n.operation]()
    return max(0, min(1, value)) if n.use_clamp else value


def verify(name):
    for nt in trees():
        assert all(n.parent is not None for n in nt.nodes if n.type != 'FRAME'), nt.name
        for n in nt.nodes:
            if n.type != 'FRAME':
                assert n.location.x >= 0 and n.location.y <= 0, (nt.name, n.name)
                assert n.location.x + n.width <= n.parent.width, (nt.name, n.name)
                assert -n.location.y + node_height(n) <= n.parent.height, (nt.name, n.name)
    if name == 'dissolve':
        for m in bpy.data.materials:
            if not m.name.startswith('Dissolver ('):
                continue
            nt = m.node_tree
            q = find(nt, 'x 0.76').inputs[0].links[0].from_socket
            noise = find(nt, 'Ruido da queima').outputs['Fac']
            keep = find(nt, 'Visibilidade 0..1').outputs[0]
            for amount in (-1, 0, 1, 2):
                for sample in (0, 0.12, 0.5, 0.88, 1):
                    assert evaluate(keep, {(q.node.name, q.name): amount,
                                          (noise.node.name, noise.name): sample}) == float(amount <= 0)
    if name == 'neve_musgo':
        nt = bpy.data.node_groups['Cobertura']
        gi = next(n for n in nt.nodes if n.type == 'GROUP_INPUT')
        normal = next(n for n in nt.nodes if n.type == 'SEPXYZ').outputs['Z']
        noise = find(nt, 'Ruido da borda').outputs['Fac']
        mask = find(nt, 'Máscara com extremos exatos').outputs[0]
        for amount in (0, 1):
            for nz in (-1, 0, 1):
                for sample in (0, 0.5, 1):
                    for softness in (0, 0.15, 1):
                        values = {(gi.name, 'Amount'): amount, (gi.name, 'Softness'): softness,
                                  (gi.name, 'Noise Breakup'): 2,
                                  (normal.node.name, normal.name): nz,
                                  (noise.node.name, noise.name): sample}
                        assert evaluate(mask, values) == amount


def runtime_copy(name):
    text = bpy.data.texts.new('anastacio_review_validation.py')
    text.write('from Range import logic\n'
               'own = logic.getCurrentController().owner\n'
               "own['review_ticks'] = own.get('review_ticks', 0) + 1\n"
               "if own['review_ticks'] >= 120:\n"
               "    print('ANASTACIO_REVIEW_RUNTIME_PASS: " + name + "')\n"
               '    logic.endGame()\n')
    # Use a separate empty so existing demo controllers remain unchanged.
    bpy.ops.object.empty_add()
    ob = bpy.context.object
    ob.name = 'Anastacio Review Validation'
    bpy.ops.logic.sensor_add(type='ALWAYS', object=ob.name)
    bpy.ops.logic.controller_add(type='PYTHON', object=ob.name)
    sensor = ob.game.sensors[-1]
    sensor.use_pulse_true_level = True
    controller = ob.game.controllers[-1]
    controller.text = text
    sensor.link(controller)
    scene = bpy.context.scene
    scene.game_settings.resolution_x = 640
    scene.game_settings.resolution_y = 360
    scene.game_settings.show_framerate_profile = False
    path = os.path.join(tempfile.gettempdir(), 'anastacio_recipe_review_' + name + '.range')
    bpy.ops.wm.save_as_mainfile(filepath=path)
    return path


args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
validate_runtime = '--validate-runtime' in args
names = [a for a in args if not a.startswith('--')] or list(DEMOS)
os.makedirs(DEST, exist_ok=True)
report = []
for name in names:
    if name not in DEMOS:
        raise ValueError('Demo desconhecida: ' + name)
    source = os.path.join(ROOT, 'demos', name + '.range')
    bpy.ops.wm.open_mainfile(filepath=source)
    if name == 'dissolve':
        fix_dissolve()
    elif name == 'neve_musgo':
        fix_cover()
    elif name == 'agua':
        fix_water()
    elif name == 'parallax_interior_mapping':
        fix_interior()
    elif name == 'triplanar':
        fix_triplanar()
    elif name == 'toon':
        fix_toon()
    for m in bpy.data.materials:
        if m.use_nodes and m.script_vert:
            stage(m.node_tree, 'Código de vértice (Text Editor)',
                  'Movimento/deformação vem do texto: ' + m.script_vert.name + '\n'
                  'Os nós abaixo controlam cor e recorte; o texto controla a malha.\n'
                  'Abra o Text Editor para ajustar os #define comentados.\n'
                  'Preserve UVs, textura de trilha e número de camadas da receita.', [])
    for nt in trees():
        layout(nt)
    verify(name)
    out = os.path.join(DEST, name + '_revisado.range')
    bpy.ops.wm.save_as_mainfile(filepath=out)
    item = {'demo': name, 'output': out, 'trees': len(trees()), 'structure': 'PASS'}
    if validate_runtime:
        item['runtime_file'] = runtime_copy(name)
    report.append(item)
    print('ANASTACIO_REVIEW_COPY_PASS:', name)
with open(os.path.join(DEST, 'validation.json'), 'w', encoding='utf-8') as stream:
    json.dump(report, stream, indent=2)
