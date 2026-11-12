# Mede o granulado do SSAO (GTAO meia resolução + temporal + blur) numa cena controlada.
#
# Cena: chão liso, canto de paredes, caixas e esfera, tudo cinza fosco. Só o SSAO muda entre as rodadas.
# Para cada preset (LOW/MEDIUM/HIGH), câmera parada e andando, roda o jogo no desktop invisível
# com SSAO ligado e desligado e tira dois prints seguidos. Métricas, só na parte da imagem sem quinas:
#   ruido   = desvio do AO (liga/desliga) menos a versão borrada 5x5 dele (grão fino, em % de luz)
#   piscar  = diferença média do AO entre dois quadros seguidos (grão que mexe, em %)
#
# Uso: python tools/debug/cenas/medir_ssao_granulado.py [pasta_saida]
import os
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
EDITOR = RAIZ / 'build' / 'bin' / 'AnastacioEngine.exe'
RUNTIME = RAIZ / 'build' / 'bin' / 'AnastacioRuntime.exe'

CENA = r'''
import bpy, sys, math
from mathutils import Vector
argv = sys.argv[sys.argv.index("--") + 1:]
saida, preset, ssao, mover, base = argv[0], argv[1], argv[2] == "1", argv[3] == "1", argv[4]
scene = bpy.context.scene
for ob in list(scene.objects):
    scene.objects.unlink(ob); bpy.data.objects.remove(ob)
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_shading_nodes = True
scene.game_settings.resolution_x = 1280
scene.game_settings.resolution_y = 720
scene.game_settings.show_framerate_profile = False

mat = bpy.data.materials.new("Cinza")
mat.use_nodes = True
nodes = mat.node_tree.nodes
for n in list(nodes): nodes.remove(n)
bsdf = nodes.new('ShaderNodeBsdfPrincipled')
bsdf.inputs['Base Color'].default_value = (0.6, 0.6, 0.6, 1.0)
bsdf.inputs['Roughness'].default_value = 0.9
bsdf.inputs['Specular'].default_value = 0.0
out = nodes.new('ShaderNodeOutputMaterial')
mat.node_tree.links.new(bsdf.outputs[0], out.inputs[0])

def obj(op, **kw):
    op(**kw); o = bpy.context.object; o.data.materials.append(mat); return o
obj(bpy.ops.mesh.primitive_plane_add, location=(0, 0, 0), radius=12)
p = obj(bpy.ops.mesh.primitive_cube_add, location=(0, -4, 2)); p.scale = (6, 0.2, 2)
p = obj(bpy.ops.mesh.primitive_cube_add, location=(-6, 2, 2)); p.scale = (0.2, 6, 2)
obj(bpy.ops.mesh.primitive_cube_add, location=(-2, -2, 0.75)).scale = (0.75, 0.75, 0.75)
obj(bpy.ops.mesh.primitive_cube_add, location=(1.5, 0, 0.5)).scale = (0.5, 1.5, 0.5)
s = obj(bpy.ops.mesh.primitive_uv_sphere_add, location=(-3.5, 1.5, 1.0), size=1.0, segments=48, ring_count=24)
bpy.ops.object.shade_smooth()

bpy.ops.object.lamp_add(type='SUN', location=(0, 0, 10), rotation=(math.radians(40), 0, math.radians(30)))
world = scene.world or bpy.data.worlds.new("W"); scene.world = world
world.horizon_color = (0.4, 0.4, 0.4); world.zenith_color = (0.4, 0.4, 0.4)
world.ambient_color = (0.5, 0.5, 0.5)
world.mist_settings.use_mist = False

fx = scene.scenefx_settings
fx.quality_preset = preset
fx.use_ssao = ssao
for nome in ("use_ssr", "use_bloom", "use_fxaa", "use_tonemap", "use_dof", "use_lightscattering", "use_taa"):
    if hasattr(fx, nome): setattr(fx, nome, False)
if hasattr(scene, "ae_ssgi_use"): scene.ae_ssgi_use = False

alvo = Vector((-1.5, -0.5, 0.5))
bpy.ops.object.camera_add(location=(5, 6, 3.5))
cam = bpy.context.object; cam.data.lens = 28
cam.rotation_euler = (alvo - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.camera = cam
txt = bpy.data.texts.new("shot.py")
txt.write("""import Range
from Range import logic
own = logic.getCurrentController().owner
f = own['f'] = own.get('f', 0) + 1
if %(mover)s:
    own.applyMovement((0.01, 0.0, 0.0), True)
if f == 120: Range.render.makeScreenshot(%(a)r)
if f == 121: Range.render.makeScreenshot(%(b)r)
if f == 130: logic.endGame()
""" % dict(mover=mover, a=base + "_a.png", b=base + "_b.png"))
scene.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', object=cam.name)
bpy.ops.logic.controller_add(type='PYTHON', object=cam.name)
cam.game.sensors[-1].use_pulse_true_level = True
cam.game.controllers[-1].text = txt
cam.game.sensors[-1].link(cam.game.controllers[-1])
bpy.ops.wm.save_as_mainfile(filepath=saida)
'''


def rodar(pasta, preset, ssao, mover):
    nome = '%s_%s_%s' % (preset.lower(), 'on' if ssao else 'off', 'mov' if mover else 'par')
    base = str(pasta / nome)
    script = pasta / '_cena.py'
    script.write_text(CENA, encoding='utf-8')
    rng = pasta / (nome + '.range')
    subprocess.run([str(EDITOR), '-b', '--factory-startup', '--python', str(script), '--',
                    str(rng), preset, '1' if ssao else '0', '1' if mover else '0', base],
                   check=True, capture_output=True)
    sys.path.insert(0, str(RAIZ / 'tools' / 'testes_engine'))
    import controle
    for f in (base + '_a.png', base + '_b.png'):
        if os.path.exists(f):
            os.remove(f)
    pid = controle.iniciar_invisivel([str(RUNTIME), '-w', '1280', '720', '0', '0', str(rng)],
                                     pasta / (nome + '.log'), dict(os.environ, RANGE_NO_CRASH_DIALOG='1'))
    limite = time.time() + 60
    while time.time() < limite and not os.path.exists(base + '_b.png'):
        time.sleep(0.3)
    time.sleep(1.0)
    controle.encerrar(pid, 5)
    return base


def carregar(caminho):
    from PIL import Image
    import numpy as np
    return np.asarray(Image.open(caminho).convert('L'), dtype=np.float32) / 255.0


def borrar(img, r=2):
    import numpy as np
    pad = np.pad(img, r, mode='edge')
    acc = np.zeros_like(img)
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            acc += pad[r + dy:r + dy + img.shape[0], r + dx:r + dx + img.shape[1]]
    return acc / (2 * r + 1) ** 2


def medir(on, off):
    import numpy as np
    a_on, b_on = carregar(on + '_a.png'), carregar(on + '_b.png')
    a_off, b_off = carregar(off + '_a.png'), carregar(off + '_b.png')
    ao_a = a_on / np.maximum(a_off, 0.02)
    ao_b = b_on / np.maximum(b_off, 0.02)
    # Sem quinas: onde a imagem sem SSAO é lisa e não é fundo.
    gy, gx = np.gradient(borrar(a_off, 1))
    lisa = (np.hypot(gx, gy) < 0.004) & (a_off > 0.05)
    lisa[:8] = lisa[-8:] = False
    lisa[:, :8] = lisa[:, -8:] = False
    fino = ao_a - borrar(ao_a, 2)
    ruido = float(np.std(fino[lisa])) * 100
    piscar = float(np.mean(np.abs(ao_a - ao_b)[lisa])) * 100
    escuro = float(np.mean(1.0 - np.clip(ao_a, 0, 1))) * 100
    return ruido, piscar, escuro, float(lisa.mean()) * 100


def main():
    pasta = Path(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.environ.get('TEMP', '.'), 'ssao_granulado'))
    pasta.mkdir(parents=True, exist_ok=True)
    print('%-7s %-7s %8s %8s %9s %7s' % ('preset', 'camera', 'ruido%', 'piscar%', 'escuro%', 'area%'))
    for preset in ('LOW', 'MEDIUM', 'HIGH'):
        for mover in (False, True):
            on = rodar(pasta, preset, True, mover)
            off = rodar(pasta, preset, False, mover)
            try:
                r = medir(on, off)
            except FileNotFoundError as e:
                print(preset, 'sem print:', e)
                continue
            print('%-7s %-7s %8.2f %8.2f %9.2f %7.1f' % ((preset, 'andando' if mover else 'parada') + r))


if __name__ == '__main__':
    main()
