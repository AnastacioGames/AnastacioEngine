"""Mede o FPS do Compositing no jogo em vários formatos de árvore.

    AnastacioEngine -b --factory-startup --python tools/debug/cenas/medir_compositing_jogo.py -- PASTA PRESET [segundos]

Gera PASTA/comp_PRESET.range. Com COMP_SHOT=arquivo.png o jogo grava um print aos 1,5 s
Com COMP_UNCAP=1 a cena sai sem a trava do Game Rate (fps 1000).
(compare com RANGE_COMPOSITOR_NO_CACHE=1 para ver se as texturas intermediárias mudam a imagem). Ao rodar no AnastacioRuntime, o jogo aquece 2 s, mede o FPS médio
nos segundos seguintes, grava PASTA/comp_PRESET.txt e fecha sozinho.

Presets:
  off        Use Nodes desligado (base)
  padrao     só Render Layers -> Composite (não deve criar passo)
  cor        cadeia de 8 nós de cor (um passo barato)
  teste      a árvore da cena criar_cena_compositing_jogo.py
  blur       Render Layers -> Blur -> Composite
  blur_cor   8 nós de cor -> Blur (o Blur recalcula a cadeia 49x)
  blur2      Blur -> Blur (49 x 49 leituras)
  lente_blur Blur -> Lens Distortion (3 x 49)
  glare_fog / glare_streaks / glare_star / glare_ghosts   Glare sobre a imagem (Threshold 0.5)
  glare_b5   Fog Glow com Blender 5 Style (Strength 2, Saturation 0.5, Tint laranja, Max Brightness 3)
  glare_b5_suave Fog Glow com Blender 5 Style e Smoothness 1 (Max Brightness 3)
  glare_bloom Bloom (modo do Blender 5, só no jogo)
  glare_sunbeams Sun Beams (Blender 5, só no jogo; sol em 0.7, 0.8, Length 0.4)
  glare_cor  8 nós de cor -> Glare Fog Glow (com textura intermediária)
  nos_filtro    Filter Sobel (Fac 0.5) -> Sharpen
  nos_transform Transform (gira/escala/desloca) -> Flip X -> Translate com Wrap X
  nos_pixel     Scale 1/16 -> Pixelate -> Scale 16
  nos_valores   Map Range da profundidade, Map Value, Switch e Separate/Combine HSVA (matiz +0.3)
  nos_sunbeams  nó Sun Beams (fonte 0.7, 0.8; Ray Length 0.3)
  diamante   6 Mix seguidos que usam o nó anterior nas duas entradas (2^6 chamadas se não houver cache)
"""
import bpy, sys, os

argv = sys.argv[sys.argv.index("--") + 1:]
out, preset = os.path.abspath(argv[0]), argv[1]
secs = float(argv[2]) if len(argv) > 2 else 8.0
os.makedirs(out, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_GAME'
gs = sc.game_settings
gs.use_frame_rate = False
gs.vsync = 'OFF'
if os.environ.get('COMP_UNCAP'):
    gs.fps = 1000  # tira a trava do Game Rate para ver o custo real (sem isso o FPS fica no campo FPS)
sc.render.resolution_x, sc.render.resolution_y = 1280, 720
gs.resolution_x, gs.resolution_y = 1280, 720

for i, col in enumerate([(1, 0.2, 0.2), (0.2, 1, 0.2), (0.2, 0.2, 1)]):
    bpy.ops.mesh.primitive_cube_add(location=(i * 3 - 3, 0, 0))
    m = bpy.data.materials.new("M%d" % i); m.diffuse_color = col
    bpy.context.object.data.materials.append(m)
bpy.ops.mesh.primitive_plane_add(location=(0, 0, -1)); bpy.context.object.scale = (10, 10, 1)
bpy.ops.object.lamp_add(type='SUN', location=(0, 0, 10))
cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera")); sc.objects.link(cam)
cam.location = (0, -12, 4); cam.rotation_euler = (1.25, 0, 0); sc.camera = cam

if preset.startswith('glare'):
    # fundo escuro e cubos que brilham (emit), para o Glare ter só pontos claros
    for ob in sc.objects:
        if ob.type == 'MESH':
            m = ob.data.materials[0] if ob.data.materials else None
            if m is None:
                m = bpy.data.materials.new("Chao"); ob.data.materials.append(m)
                m.diffuse_color = (0.05, 0.05, 0.05)
            else:
                m.emit = 1.5
    w = bpy.data.worlds.new("W"); w.horizon_color = (0.01, 0.01, 0.02); sc.world = w

if preset != 'off':
    sc.use_nodes = True
    nt = sc.node_tree; N = nt.nodes; L = nt.links
    for n in list(N):
        if n.type not in ('R_LAYERS', 'COMPOSITE'):
            N.remove(n)
    rl = [n for n in N if n.type == 'R_LAYERS'][0]
    comp = [n for n in N if n.type == 'COMPOSITE'][0]

    def chain_cor(src):
        """8 nós de cor em fila; devolve o socket de saída"""
        s = src
        for t in ('CompositorNodeColorBalance', 'CompositorNodeHueSat', 'CompositorNodeCurveRGB',
                  'CompositorNodeBrightContrast', 'CompositorNodeGamma', 'CompositorNodeInvert',
                  'CompositorNodeInvert', 'CompositorNodeGamma'):
            n = N.new(t)
            L.new(s, n.inputs['Color'] if 'Color' in n.inputs else n.inputs['Image'])
            s = n.outputs[0]
        return s

    def blur(src, size=10):
        n = N.new('CompositorNodeBlur'); n.size_x = n.size_y = size
        L.new(src, n.inputs['Image'])
        return n.outputs[0]

    img = rl.outputs['Image']
    if preset == 'padrao':
        s = img
    elif preset == 'cor':
        s = chain_cor(img)
    elif preset == 'blur':
        s = blur(img)
    elif preset == 'blur_cor':
        s = blur(chain_cor(img))
    elif preset == 'blur2':
        s = blur(blur(img))
    elif preset == 'lente_blur':
        ld = N.new('CompositorNodeLensdist'); ld.inputs['Dispersion'].default_value = 0.15
        L.new(blur(img), ld.inputs['Image']); s = ld.outputs[0]
    elif preset.startswith('glare'):
        g = N.new('CompositorNodeGlare'); g.threshold = 0.5
        if preset == 'glare_b5':
            g.use_game_blender5 = True
            g.strength = 2.0; g.saturation = 0.5; g.tint = (1.0, 0.7, 0.4); g.max_brightness = 3.0
        if preset == 'glare_b5_suave':
            g.use_game_blender5 = True; g.max_brightness = 3.0; g.smoothness = 1.0
        g.glare_type = {'glare_b5': 'FOG_GLOW', 'glare_b5_suave': 'FOG_GLOW', 'glare_fog': 'FOG_GLOW', 'glare_cor': 'FOG_GLOW', 'glare_streaks': 'STREAKS',
                        'glare_star': 'SIMPLE_STAR', 'glare_ghosts': 'GHOSTS', 'glare_bloom': 'BLOOM',
                        'glare_sunbeams': 'SUN_BEAMS'}[preset]
        if preset == 'glare_sunbeams':
            g.sun_position = (0.7, 0.8); g.sun_beams_length = 0.4
        L.new(chain_cor(img) if preset == 'glare_cor' else img, g.inputs['Image']); s = g.outputs[0]
    elif preset == 'nos_filtro':
        # Sobel nas bordas misturado meio a meio, depois Sharpen
        f1 = N.new('CompositorNodeFilter'); f1.filter_type = 'SOBEL'; f1.inputs['Fac'].default_value = 0.5
        f2 = N.new('CompositorNodeFilter'); f2.filter_type = 'SHARPEN'
        L.new(img, f1.inputs['Image']); L.new(f1.outputs[0], f2.inputs['Image']); s = f2.outputs[0]
    elif preset == 'nos_transform':
        # Transform (gira 0.3, escala 0.8, desloca) -> Flip X -> Translate com Wrap X
        tf = N.new('CompositorNodeTransform'); tf.inputs['Angle'].default_value = 0.3
        tf.inputs['Scale'].default_value = 0.8; tf.inputs['X'].default_value = 80
        fl = N.new('CompositorNodeFlip'); fl.axis = 'X'
        tr = N.new('CompositorNodeTranslate'); tr.wrap_axis = 'XAXIS'; tr.inputs['X'].default_value = 300
        L.new(img, tf.inputs['Image']); L.new(tf.outputs[0], fl.inputs['Image'])
        L.new(fl.outputs[0], tr.inputs['Image']); s = tr.outputs[0]
    elif preset == 'nos_pixel':
        # Scale 1/16 -> Pixelate -> Scale 16: blocos de 16 px
        a = N.new('CompositorNodeScale'); a.inputs['X'].default_value = a.inputs['Y'].default_value = 1 / 16
        px = N.new('CompositorNodePixelate')
        b = N.new('CompositorNodeScale'); b.inputs['X'].default_value = b.inputs['Y'].default_value = 16
        L.new(img, a.inputs['Image']); L.new(a.outputs[0], px.inputs['Color'])
        L.new(px.outputs[0], b.inputs['Image']); s = b.outputs[0]
    elif preset == 'nos_valores':
        # Map Range da profundidade (5..25 -> 1..0) multiplica a imagem; Map Value e Switch no caminho;
        # Separate/Combine HSVA gira o matiz em 0.3
        mr = N.new('CompositorNodeMapRange'); mr.use_clamp = True
        mr.inputs[1].default_value = 5; mr.inputs[2].default_value = 25
        mr.inputs[3].default_value = 1; mr.inputs[4].default_value = 0
        mv = N.new('CompositorNodeMapValue'); mv.size = [1.0]; mv.offset = [0.0]
        sw = N.new('CompositorNodeSwitch'); sw.check = True
        sep = N.new('CompositorNodeSepHSVA'); comb = N.new('CompositorNodeCombHSVA')
        ad = N.new('CompositorNodeMath'); ad.operation = 'ADD'; ad.inputs[1].default_value = 0.3
        md = N.new('CompositorNodeMath'); md.operation = 'MODULO'; md.inputs[1].default_value = 1.0
        mul = N.new('CompositorNodeMixRGB'); mul.blend_type = 'MULTIPLY'; mul.inputs[0].default_value = 1.0
        L.new(rl.outputs['Depth'], mr.inputs[0]); L.new(mr.outputs[0], mv.inputs[0])
        L.new(img, sep.inputs[0]); L.new(sep.outputs[0], ad.inputs[0]); L.new(ad.outputs[0], md.inputs[0])
        L.new(md.outputs[0], comb.inputs[0]); L.new(sep.outputs[1], comb.inputs[1])
        L.new(sep.outputs[2], comb.inputs[2]); L.new(sep.outputs[3], comb.inputs[3])
        L.new(img, sw.inputs[0]); L.new(comb.outputs[0], sw.inputs[1])
        L.new(sw.outputs[0], mul.inputs[1]); L.new(mv.outputs[0], mul.inputs[2]); s = mul.outputs[0]
    elif preset == 'nos_sunbeams':
        sb = N.new('CompositorNodeSunBeams'); sb.source = (0.7, 0.8); sb.ray_length = 0.3
        L.new(img, sb.inputs[0]); s = sb.outputs[0]
    elif preset == 'diamante':
        s = img
        for i in range(6):
            mx = N.new('CompositorNodeMixRGB'); mx.blend_type = 'ADD'
            L.new(s, mx.inputs[1]); L.new(s, mx.inputs[2]); s = mx.outputs[0]
    elif preset == 'teste':
        # mesma árvore da cena de teste, sem o script dela
        cb = N.new('CompositorNodeColorBalance'); cb.gain = (1.1, 1.0, 0.85)
        hs = N.new('CompositorNodeHueSat')
        el = N.new('CompositorNodeEllipseMask'); el.width = 0.9; el.height = 0.7
        bl = N.new('CompositorNodeBlur'); bl.use_relative = True; bl.factor_x = 20; bl.factor_y = 20
        mix = N.new('CompositorNodeMixRGB'); mix.blend_type = 'MULTIPLY'
        ld = N.new('CompositorNodeLensdist'); ld.inputs['Dispersion'].default_value = 0.15
        cu = N.new('CompositorNodeCurveRGB')
        cr = N.new('CompositorNodeValToRGB')
        ov = N.new('CompositorNodeMixRGB'); ov.blend_type = 'OVERLAY'; ov.inputs[0].default_value = 0.2
        bc = N.new('CompositorNodeBrightContrast')
        gm = N.new('CompositorNodeGamma')
        L.new(img, cb.inputs['Image']); L.new(cb.outputs[0], hs.inputs['Image'])
        L.new(hs.outputs[0], mix.inputs[1]); L.new(el.outputs[0], bl.inputs['Image'])
        L.new(bl.outputs[0], mix.inputs[2]); L.new(mix.outputs[0], ld.inputs['Image'])
        L.new(ld.outputs[0], cu.inputs['Image']); L.new(cu.outputs[0], ov.inputs[1])
        L.new(rl.outputs['Depth'], cr.inputs['Fac']); L.new(cr.outputs[0], ov.inputs[2])
        L.new(ov.outputs[0], bc.inputs['Image']); L.new(bc.outputs[0], gm.inputs['Image'])
        s = gm.outputs[0]
    else:
        raise SystemExit("preset desconhecido: " + preset)
    L.new(s, comp.inputs['Image'])

log = os.path.join(out, "comp_%s.txt" % preset).replace("\\", "/")
T = '''import Range, time
own = Range.logic.getCurrentController().owner
t = time.perf_counter()
if "t0" not in own:
    own["t0"] = t
    own["n"] = 0
own["n"] += 1
el = t - own["t0"]
import os
shot = os.environ.get("COMP_SHOT")
if shot and "shot" not in own and el >= 1.5:
    own["shot"] = 1
    Range.render.makeScreenshot(shot)
if "m0" not in own and el >= 2.0:
    own["m0"] = el; own["n0"] = own["n"]
if "m0" in own and el >= 2.0 + %(secs)r:
    fps = (own["n"] - own["n0"]) / (el - own["m0"])
    c = Range.logic.getCurrentScene().filterManager.compositor
    m = getattr(Range.render, "getGraphicsCardRenderer", None) or getattr(Range.logic, "getGraphicsCardRenderer", None)
    gpu = m() if m else "?"
    open(%(log)r, "w").write("fps %%.1f\\ncompositor %%s\\ngpu %%s\\n" %% (fps, c is not None, gpu))
    Range.logic.endGame()
''' % {"secs": secs, "log": log}
t = bpy.data.texts.new("medir.py"); t.write(T)
ob = cam
bpy.context.scene.objects.active = ob
bpy.ops.logic.sensor_add(type='ALWAYS', object=ob.name)
ob.game.sensors[-1].use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', object=ob.name)
ob.game.controllers[-1].text = t
ob.game.sensors[-1].link(ob.game.controllers[-1])
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "comp_%s.range" % preset))
