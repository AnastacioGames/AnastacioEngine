"""Cena de teste do Compositing no jogo (fase 1): a árvore do compositor vira um 2D Filter.

    AnastacioEngine -b --python tools/debug/cenas/criar_cena_compositing_jogo.py -- PASTA

Gera PASTA/compositing.range: cubos coloridos, sol e uma árvore com Color Balance, Hue/Sat,
vinheta (Ellipse Mask -> Blur -> Mix Multiply), Lens Distortion com dispersão, RGB Curves,
Color Ramp misturado em Overlay, Brilho/Contraste, Gamma e um nó sem suporte (Glare, passa direto).
Com janela: a imagem deve sair mais quente, com cantos escuros e franja colorida nas bordas.
"""
import bpy, sys, os
out = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_GAME'
for i, col in enumerate([(1, 0.2, 0.2), (0.2, 1, 0.2), (0.2, 0.2, 1)]):
    bpy.ops.mesh.primitive_cube_add(location=(i * 3 - 3, 0, 0))
    m = bpy.data.materials.new("M%d" % i); m.diffuse_color = col
    bpy.context.object.data.materials.append(m)
bpy.ops.mesh.primitive_plane_add(location=(0, 0, -1)); bpy.context.object.scale = (10, 10, 1)
bpy.ops.object.lamp_add(type='SUN', location=(0, 0, 10))
cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera")); sc.objects.link(cam)
cam.location = (0, -12, 4); cam.rotation_euler = (1.25, 0, 0); sc.camera = cam

sc.use_nodes = True
nt = sc.node_tree
N = nt.nodes; L = nt.links
for n in list(N):
    if n.type not in ('R_LAYERS', 'COMPOSITE'):
        N.remove(n)
rl = [n for n in N if n.type == 'R_LAYERS'][0]
comp = [n for n in N if n.type == 'COMPOSITE'][0]
cb = N.new('CompositorNodeColorBalance'); cb.gain = (1.1, 1.0, 0.85)
hs = N.new('CompositorNodeHueSat'); hs.inputs['Saturation'].default_value = 1.3
el = N.new('CompositorNodeEllipseMask'); el.width = 0.9; el.height = 0.7
bl = N.new('CompositorNodeBlur'); bl.use_relative = True; bl.factor_x = 20; bl.factor_y = 20
mix = N.new('CompositorNodeMixRGB'); mix.blend_type = 'MULTIPLY'
ld = N.new('CompositorNodeLensdist'); ld.inputs['Dispersion'].default_value = 0.15
cu = N.new('CompositorNodeCurveRGB')
cr = N.new('CompositorNodeValToRGB')
ov = N.new('CompositorNodeMixRGB'); ov.blend_type = 'OVERLAY'; ov.inputs[0].default_value = 0.2
bc = N.new('CompositorNodeBrightContrast'); bc.inputs['Contrast'].default_value = 10
gm = N.new('CompositorNodeGamma'); gm.inputs['Gamma'].default_value = 1.1
gl = N.new('CompositorNodeGlare')
L.new(rl.outputs['Image'], cb.inputs['Image'])
L.new(cb.outputs['Image'], hs.inputs['Image'])
L.new(hs.outputs['Image'], mix.inputs[1])
L.new(el.outputs['Mask'], bl.inputs['Image'])
L.new(bl.outputs['Image'], mix.inputs[2])
L.new(mix.outputs['Image'], ld.inputs['Image'])
L.new(ld.outputs['Image'], cu.inputs['Image'])
L.new(cu.outputs['Image'], ov.inputs[1])
L.new(rl.outputs['Depth'], cr.inputs['Fac'])
L.new(cr.outputs['Image'], ov.inputs[2])
L.new(ov.outputs['Image'], bc.inputs['Image'])
L.new(bc.outputs['Image'], gm.inputs['Image'])
L.new(gm.outputs['Image'], gl.inputs['Image'])
L.new(gl.outputs['Image'], comp.inputs['Image'])

T = '''import Range
own = Range.logic.getCurrentController().owner
own["f"] = own.get("f", 0) + 1
if own["f"] == 5:
    print("COMPOSITING TESTE FIM")
    Range.logic.endGame()
'''
t = bpy.data.texts.new("t.py"); t.write(T)
sc.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', name="A", object=cam.name)
s = cam.game.sensors["A"]; s.use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', name="P", object=cam.name)
c = cam.game.controllers["P"]; c.text = t; s.link(c)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "compositing.range"), check_existing=False)
