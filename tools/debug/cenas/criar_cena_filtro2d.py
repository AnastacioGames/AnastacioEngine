"""Cena de teste das ferramentas do 2D Filter (erros com linha, recompilacao, uniforms bgl_*/u_*).

Uso:
  AnastacioEngine.exe -b --factory-startup --python tools/debug/cenas/criar_cena_filtro2d.py -- <saida.range> <dir_trabalho> [segundos]

Cria em <dir_trabalho>:
  filtro_externo.glsl  texto externo usado pelo atuador 2D Filter (pass 1), recarregado ao salvar;
  filtro2d_log.txt     evidencias gravadas pelo jogo (o jogo fecha sozinho).

O script do jogo:
  1. addFilter(0) com erro na linha 3 -> compileLog precisa citar a linha 3;
  2. recompile() com fonte valida usando bgl_Time/bgl_Resolution/bgl_PreviousTexture/
     bgl_InverseProjectionMatrix/bgl_DepthTexture e u_strength/u_tint;
  3. activeUniforms, setUniform() (inclusive nome errado -> KeyError);
  4. reescreve filtro_externo.glsl com erro -> o filtro do atuador mantem o programa e compileLog
     mostra o erro; depois reescreve valido -> recompila e compileLog fica vazio;
  5. mede FPS medio nos ultimos segundos.
"""
import bpy
import os
import sys
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = os.path.abspath(argv[0])
workdir = os.path.abspath(argv[1])
seconds = float(argv[2]) if len(argv) > 2 else 10.0
os.makedirs(workdir, exist_ok=True)

glsl_path = os.path.join(workdir, "filtro_externo.glsl")
GOOD_EXTERNAL = """uniform sampler2D bgl_RenderedTexture;
in vec4 bgl_TexCoord;
out vec4 fragColor;
uniform float u_gain;
void main()
{
    fragColor = texture(bgl_RenderedTexture, bgl_TexCoord.xy) * (u_gain > 0.0 ? u_gain : 1.0);
}
"""
with open(glsl_path, "w") as f:
    f.write(GOOD_EXTERNAL)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 960
scene.game_settings.resolution_y = 540
scene.game_settings.use_frame_rate = False
world = bpy.data.worlds.new("Filtro2D World")
world.horizon_color = (0.35, 0.5, 0.7)
world.mist_settings.use_mist = False
scene.world = world


def material(name, color):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    return mat


bpy.ops.mesh.primitive_plane_add(location=(0, 0, 0))
ground = bpy.context.object
ground.scale = (10, 10, 1)
ground.data.materials.append(material("Chao", (0.4, 0.4, 0.4)))
for i, color in enumerate([(0.9, 0.2, 0.1), (0.1, 0.8, 0.2), (0.1, 0.3, 0.9)]):
    bpy.ops.mesh.primitive_cube_add(location=(i * 3 - 3, 0, 1))
    bpy.context.object.data.materials.append(material("Cubo%d" % i, color))

bpy.ops.object.lamp_add(type='SUN', location=(0, 0, 10))
sun = bpy.context.object
sun.rotation_euler = (0.6, 0.3, 0.4)

bpy.ops.object.camera_add(location=(0, -10, 5))
cam = bpy.context.object
cam.rotation_euler = (Vector((0, 0, 0.5)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.camera = cam

# External text (file on disk) for the actuator, so live reload can be tested.
ext_text = bpy.data.texts.load(glsl_path)

test = bpy.data.texts.new("filtro_teste.py")
test.write('''import bge, os, time

LOG = %r
GLSL = %r
SECONDS = %r
BAD = """uniform sampler2D bgl_RenderedTexture;
out vec4 fragColor;
void main() { fragColor = vec4(undefined_name); }
"""
GOOD = """uniform sampler2D bgl_RenderedTexture;
uniform sampler2D bgl_DepthTexture;
uniform sampler2D bgl_PreviousTexture;
uniform float bgl_Time;
uniform vec2 bgl_Resolution;
uniform mat4 bgl_InverseProjectionMatrix;
uniform float u_strength;
uniform vec3 u_tint;
in vec4 bgl_TexCoord;
out vec4 fragColor;
void main()
{
    vec2 uv = gl_FragCoord.xy / bgl_Resolution;
    float d = texture(bgl_DepthTexture, uv).r;
    vec4 view = bgl_InverseProjectionMatrix * vec4(uv * 2.0 - 1.0, d * 2.0 - 1.0, 1.0);
    vec4 cur = texture(bgl_RenderedTexture, uv);
    vec4 prev = texture(bgl_PreviousTexture, uv);
    float wobble = 0.5 + 0.5 * sin(bgl_Time);
    fragColor = mix(cur, prev, 0.1 * u_strength * wobble) * vec4(u_tint, 1.0) + 0.0 * view;
}
"""

def log(*a):
    with open(LOG, "a") as f:
        f.write(" ".join(str(x) for x in a) + "\\n")

def tick(cont):
    own = cont.owner
    scene = bge.logic.getCurrentScene()
    fm = scene.filterManager
    t0 = bge.logic.globalDict.get("t0")
    now = time.time()
    if t0 is None:
        bge.logic.globalDict["t0"] = now
        own["frames"] = 0
        own["step"] = 0
        f = fm.addFilter(0, bge.logic.RAS_2DFILTER_CUSTOMFILTER, BAD)
        log("bad.sourceName", f.sourceName)
        log("bad.compileLog", repr(f.compileLog))
        log("bad.cita_linha_3", ("(3)" in f.compileLog) or (":3:" in f.compileLog) or ("3:" in f.compileLog))
        ok = f.recompile(GOOD)
        log("good.recompile", ok, "log_vazio", f.compileLog == "")
        log("good.activeUniforms", sorted(f.activeUniforms))
        f.setUniform("u_strength", 1.0)
        f.setUniform("u_tint", (1.0, 0.9, 0.9))
        try:
            f.setUniform("u_nao_existe", 1.0)
            log("keyerror", False)
        except KeyError as e:
            log("keyerror", True, e)
        try:
            f.setUniform("u_tint", 1.0)
            log("valueerror", False)
        except ValueError as e:
            log("valueerror", True, e)
        return
    own["frames"] += 1
    el = now - t0
    ext = fm.getFilter(1)
    step = own["step"]
    if step == 0 and el > 1.0 and ext:
        log("ext.sourceName", ext.sourceName, "sourcePath", ext.sourcePath, "log_vazio", ext.compileLog == "")
        with open(GLSL, "w") as fh:
            fh.write(BAD)
        own["step"] = 1
        own["ts"] = el
    elif step == 1 and el - own["ts"] > 1.5:
        log("ext.apos_erro.log_tem_erro", ext.compileLog != "", "isValid", ext.isValid())
        log("ext.apos_erro.compileLog", repr(ext.compileLog))
        with open(GLSL, "w") as fh:
            fh.write(GOOD)
        own["step"] = 2
        own["ts"] = el
    elif step == 2 and el - own["ts"] > 1.5:
        log("ext.apos_correcao.log_vazio", ext.compileLog == "", "uniforms", sorted(ext.activeUniforms))
        own["step"] = 3
        own["fps_t"] = el
        own["fps_f"] = own["frames"]
    if el > SECONDS:
        if "fps_t" in own:
            log("fps_medio", (own["frames"] - own["fps_f"]) / (el - own["fps_t"]))
        log("# fim")
        bge.logic.endGame()
''' % (os.path.join(workdir, "filtro2d_log.txt"), glsl_path, seconds))

ctrl_obj = cam
scene.objects.active = ctrl_obj
bpy.ops.logic.sensor_add(type='ALWAYS', object=ctrl_obj.name)
sensor = ctrl_obj.game.sensors[-1]
sensor.use_pulse_true_level = True
bpy.ops.logic.controller_add(type='PYTHON', object=ctrl_obj.name)
ctrl = ctrl_obj.game.controllers[-1]
ctrl.mode = 'MODULE'
ctrl.module = 'filtro_teste.tick'
sensor.link(ctrl)

# 2D Filter actuator (custom, pass 1) bound to the external text.
bpy.ops.logic.sensor_add(type='ALWAYS', object=ctrl_obj.name)
s2 = ctrl_obj.game.sensors[-1]
bpy.ops.logic.controller_add(type='LOGIC_AND', object=ctrl_obj.name)
c2 = ctrl_obj.game.controllers[-1]
bpy.ops.logic.actuator_add(type='FILTER_2D', object=ctrl_obj.name)
act = ctrl_obj.game.actuators[-1]
act.mode = 'CUSTOMFILTER'
act.filter_pass = 1
act.glsl_shader = ext_text
s2.link(c2)
act.link(c2)

bpy.ops.wm.save_as_mainfile(filepath=output)
print("salvo", output)
