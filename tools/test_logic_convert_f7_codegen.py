# Teste de geracao (F7) do conversor Logic Bricks -> Python: Action, Armature, Filter 2D, Vibration,
# Motion Servo/Character/Set Position, Change Color, Game Save/Load/Screenshot, Property Level/Runtime API,
# Mouse Over com material/x-ray e Weather Effects volumetrico. Converte e compila o codigo gerado; nao roda o jogo.
# Uso: GEN_OUT=<prefixo> AnastacioEngine.exe -b --factory-startup --python tools/test_logic_convert_f7_codegen.py
# Saida: <prefixo>.txt (resumo) e <prefixo>_<objeto>.py (codigo gerado).
import bpy, os, traceback
from bl_operators import logic_to_python as L
sc = bpy.context.scene
sc.render.engine = 'BLENDER_GAME'
out = []
def mk(name, arm=False):
    data = bpy.data.armatures.new(name) if arm else bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, data); sc.objects.link(ob); return ob
ob = mk('heroi'); alvo = mk('alvo'); arm = mk('esq', True)
ob.game.physics_type = 'DYNAMIC'
act = bpy.data.actions.new('Andar')
txt = bpy.data.texts.new('f.glsl'); txt.write('void main(){gl_FragColor=vec4(1.0);}')
def wire(o, stype, sset, atype, aset):
    sc.objects.active = o
    n = len(o.game.controllers)
    bpy.ops.logic.sensor_add(type=stype, name='s%d' % n, object=o.name)
    bpy.ops.logic.controller_add(type='LOGIC_AND', name='c%d' % n, object=o.name)
    bpy.ops.logic.actuator_add(type=atype, name='a%d' % n, object=o.name)
    s, c, a = o.game.sensors[-1], o.game.controllers[-1], o.game.actuators[-1]
    for k, v in sset.items(): setattr(s, k, v)
    for k, v in aset.items(): setattr(a, k, v)
    s.link(c); a.link(c)
for pm in ('PLAY','PINGPONG','FLIPPER','LOOPSTOP','LOOPEND','PROPERTY'):
    wire(ob, 'ALWAYS', {}, 'ACTION', dict(action=act, play_mode=pm, frame_end=20, property='p', frame_property='f'))
for m in ('ENABLE','REMOVE','MOTIONBLUR','BLUR','OUTLINE','SSAO','FXAA','CUSTOMFILTER'):
    wire(ob, 'ALWAYS', {}, 'FILTER_2D', dict(mode=m, glsl_shader=txt, filter_pass=2))
wire(ob, 'ALWAYS', {}, 'VIBRATION', dict(mode='PLAY'))
wire(ob, 'ALWAYS', {}, 'VIBRATION', dict(mode='STOP'))
wire(ob, 'ALWAYS', {}, 'MOTION', dict(mode='OBJECT_SERVO', linear_velocity=(1,0,0), reference_object=alvo, use_servo_limit_x=True))
wire(ob, 'ALWAYS', {}, 'MOTION', dict(mode='OBJECT_SERVO', servo_mode='SERVO_ANGULAR', angular_velocity=(0,0,1)))
wire(ob, 'ALWAYS', {}, 'MOTION', dict(mode='OBJECT_CHARACTER', offset_location=(0,.1,0), use_character_jump=True))
wire(ob, 'ALWAYS', {}, 'MOTION', dict(mode='OBJECT_NORMAL_SET', offset_location=(1,2,3)))
wire(ob, 'ALWAYS', {}, 'MOTION', dict(offset_location=(0,.1,0), offset_rotation=(0,0,.1), linear_velocity=(1,0,0), angular_velocity=(0,0,1), damping=10))
wire(ob, 'ALWAYS', {}, 'EDIT_OBJECT', dict(mode='CHANGECOLOR', use_lerp_col=True))
wire(ob, 'ALWAYS', {}, 'EDIT_OBJECT', dict(mode='CHANGECOLOR'))
for m in ('SAVECFG','LOADCFG','SCREENSHOT'):
    wire(ob, 'ALWAYS', {}, 'GAME', dict(mode=m))
wire(ob, 'ALWAYS', {}, 'PROPERTY', dict(mode='LEVEL', property='lv'))
for rp in sorted(L._RUNTIME_PROPS):
    wire(ob, 'PROPERTY', dict(use_runtime_property=True, runtime_property=rp, runtime_target=alvo), 'PROPERTY', dict(actuator_mode='RUNTIME_API', runtime_property=rp, mode='ASSIGN', object=alvo))
wire(ob, 'PROPERTY', dict(use_runtime_property=True, runtime_property='MASS', evaluation_type='PROPINTERVAL'), 'PROPERTY', dict(actuator_mode='RUNTIME_API', runtime_property='MASS', mode='ADD'))
for ev in ('MOUSEOVER','MOUSEOVERANY'):
    wire(ob, 'MOUSE', dict(mouse_event=ev, use_x_ray=True, property='x'), 'VISIBILITY', {})
    wire(ob, 'MOUSE', dict(mouse_event=ev, use_material='MATERIAL', material='M'), 'VISIBILITY', {})
    wire(ob, 'MOUSE', dict(mouse_event=ev, use_material='MATERIAL', use_x_ray=True, material='M'), 'VISIBILITY', {})
for cat, prop, val in (('VOLUMETRIC_FOG','vfog_effect','WEATHER_VFOG_DENSITY'),('VOLUMETRIC_FOG','vfog_effect','WEATHER_VFOG_USE_LAMPS'),('VOLUMETRIC_CLOUDS','vcloud_effect','WEATHER_VCLOUD_COVERAGE'),('CLOUDS','cloud_effect','WEATHER_USE_SKY_LAYERS'),('CLOUDS','cloud_effect','WEATHER_CLOUD_COLOR_R')):
    wire(ob, 'ALWAYS', {}, 'PROPERTY', {'actuator_mode':'WEATHER_EFFECTS','weather_category':cat, prop:val})
wire(ob, 'DELAY', dict(use_deltatime=True, delay_time=1.5), 'VISIBILITY', {})
for tt in ('STATECHG','LINERRORBELOW','ROTERRORABOVE'):
    wire(arm, 'ARMATURE', dict(test_type=tt, bone='B', constraint='IK'), 'ARMATURE', dict(mode='RUN'))
for m in ('ENABLE','DISABLE','SETTARGET','SETWEIGHT','SETINFLUENCE'):
    wire(arm, 'ALWAYS', {}, 'ARMATURE', dict(mode=m, bone='B', constraint='IK', target=alvo))
wire(arm, 'ALWAYS', {}, 'ACTION', dict(action=act))
# links de outro objeto: sensor do alvo dispara actuators do heroi
sc.objects.active = alvo
bpy.ops.logic.sensor_add(type='ALWAYS', name='fs', object=alvo.name); bpy.ops.logic.controller_add(type='LOGIC_AND', name='fc', object=alvo.name)
fs, fc = alvo.game.sensors[-1], alvo.game.controllers[-1]; fs.link(fc)
for a in ob.game.actuators: a.link(fc)
for o in (ob, arm, alvo):
    try:
        code, conv, todos = L.convert_object(o, L._class_name(o.name))
        compile(code, o.name, 'exec')
        out.append('%s: %d de %d controllers convertidos, codigo compila (%d linhas)' % (o.name, len(conv), len(o.game.controllers), code.count('\n')))
        out += ['   TODO ' + t for t in todos]
        open(os.environ['GEN_OUT'] + '_' + o.name + '.py', 'w', encoding='utf-8').write(code)
    except Exception:
        out.append('%s: ERRO\n%s' % (o.name, traceback.format_exc()))
open(os.environ['GEN_OUT'] + '.txt', 'w', encoding='utf-8').write('\n'.join(out) + '\n')
