# Teste de geracao do conversor Logic Bricks -> Python para os bricks do Bricks 2.0: actuators Wait e
# Video (todos os modos) e sensor Actuator no modo Finished. Converte, compila o codigo gerado e simula os
# helpers _wait/_video com um logic e um Video Player falsos; nao roda o jogo.
# Uso: GEN_OUT=<prefixo> AnastacioEngine.exe -b --factory-startup --python tools/test_logic_convert_bricks2_codegen.py
# Saida: <prefixo>.txt (resumo) e <prefixo>_<objeto>.py (codigo gerado).
import bpy, os, traceback, types
from bl_operators import logic_to_python as L
sc = bpy.context.scene
sc.render.engine = 'BLENDER_GAME'
out = []
def mk(name):
    ob = bpy.data.objects.new(name, bpy.data.meshes.new(name)); sc.objects.link(ob); return ob
ob = mk('heroi'); tela = mk('tela')
def wire(o, stype, sset, atype, aset, name=None):
    sc.objects.active = o
    n = len(o.game.controllers)
    bpy.ops.logic.sensor_add(type=stype, name='s%d' % n, object=o.name)
    bpy.ops.logic.controller_add(type='LOGIC_AND', name='c%d' % n, object=o.name)
    bpy.ops.logic.actuator_add(type=atype, name=name or 'a%d' % n, object=o.name)
    s, c, a = o.game.sensors[-1], o.game.controllers[-1], o.game.actuators[-1]
    for k, v in sset.items(): setattr(s, k, v)
    for k, v in aset.items(): setattr(a, k, v)
    s.link(c); a.link(c)
    return s, c, a
wire(ob, 'ALWAYS', {}, 'WAIT', dict(duration=1.5, use_restart=True), 'espera')
for m in ('PLAY', 'PAUSE', 'TOGGLE', 'STOP', 'RESTART', 'SEEK'):
    wire(ob, 'KEYBOARD', dict(key='A'), 'VIDEO', dict(mode=m, object=tela, seconds=-2.0, use_relative=True),
         'video_' + m.lower())
# Then: sensor Finished lendo o Wait e o Video Play; um terceiro lendo uma Action (fica TODO)
wire(ob, 'ACTUATOR', dict(actuator='espera', mode='FINISHED'), 'VISIBILITY', {})
wire(ob, 'ACTUATOR', dict(actuator='video_play', mode='FINISHED'), 'VISIBILITY', {})
wire(ob, 'ACTUATOR', dict(actuator='espera'), 'VISIBILITY', {})
wire(ob, 'ALWAYS', {}, 'ACTION', dict(action=bpy.data.actions.new('Andar')), 'anda')
wire(ob, 'ACTUATOR', dict(actuator='anda', mode='FINISHED'), 'VISIBILITY', {})
try:
    code, conv, todos = L.convert_object(ob, L._class_name(ob.name))
    compile(code, ob.name, 'exec')
    out.append('%s: %d de %d controllers convertidos, codigo compila (%d linhas)' % (
        ob.name, len(conv), len(ob.game.controllers), code.count('\n')))
    out += ['   TODO ' + t for t in todos]
    for need in ('def _wait(', 'def _video(', "self._act_done.get('espera', False)",
                 "self._act_done.get('video_play', False)", "self._act_done['espera'] = True",
                 "self._act_on.get('espera', False)", 'bool(state & 1)'):
        out.append('   %s: %s' % (need, 'ok' if need in code else 'FALTA'))
    out.append('   Action Finished vira TODO: %s' % ('ok' if any('ACTION' in t for t in todos) else 'FALTA'))
    open(os.environ['GEN_OUT'] + '_' + ob.name + '.py', 'w', encoding='utf-8').write(code)
except Exception:
    out.append('%s: ERRO\n%s' % (ob.name, traceback.format_exc()))

# Simulacao dos helpers
clock = [0.0]
logic = types.SimpleNamespace(getFrameTime=lambda: clock[0])
g = {'logic': logic}
exec("class C:\n" + L._EXTRA['_wait'] + L._EXTRA['_video'], g)
C = g['C']
c = C(); c._ticks = {}
def done(key):
    return c._ticks.pop('done:' + key, False)
# Wait 1 s, sem restart
res = []
for i, (fire, live) in enumerate([(True, True)] + [(False, True)] * 70):
    clock[0] = i / 60.0
    c._wait('w', fire, live, 1.0, False)
    if done('w'):
        res.append(i)
out.append('sim wait 1s termina no tic 60: %s (%s)' % ('ok' if res == [60] else 'FALHA', res))
c._ticks = {}; clock[0] = 0.0
c._wait('w', True, True, 1.0, False); clock[0] = 0.5; c._wait('w', False, False, 1.0, False)
out.append('sim wait cancela ao sair do estado: %s' % ('ok' if 'w' not in c._ticks and not done('w') else 'FALHA'))
c._ticks = {}; clock[0] = 0.0
c._wait('w', True, True, 0.0, False)
out.append('sim wait 0 termina no mesmo tic: %s' % ('ok' if done('w') else 'FALHA'))

class Player:
    anastacio_video = True
    def __init__(self): self.finished = False; self.playing = False; self.time = 3.0; self.duration = 10.0; self.log = []
    def play(self): self.playing = True; self.finished = False; self.log.append('play')
    def pause(self): self.playing = False; self.log.append('pause')
    def stop(self): self.playing = False; self.log.append('stop')
    def seek(self, t): self.log.append('seek %.1f' % t)
p = Player()
scene = types.SimpleNamespace(objects={'tela': types.SimpleNamespace(components=[p])})
own = types.SimpleNamespace(scene=scene, name='heroi')
c._ticks = {}
c._video('v', True, True, 'tela', 0, 0.0, False, own=own)
ok1 = p.log == ['play'] and 'v' in c._ticks and not done('v')
p.finished = True; p.playing = False
c._video('v', False, True, 'tela', 0, 0.0, False, own=own)
out.append('sim video play termina no fim do video: %s' % ('ok' if ok1 and done('v') and 'v' not in c._ticks else 'FALHA'))
p.log = []; c._video('v', True, True, 'tela', 5, -5.0, True, own=own)
out.append('sim video seek relativo prende em 0: %s (%s)' % ('ok' if p.log == ['seek 0.0'] and done('v') else 'FALHA', p.log))
p.log = []; p.playing = True; c._video('v', True, True, 'tela', 2, 0.0, False, own=own)
out.append('sim video play/pause pausa: %s' % ('ok' if p.log == ['pause'] and done('v') else 'FALHA'))
p.log = []; c._video('v', True, True, 'tela', 4, 0.0, False, own=own)
c._video('v', False, False, 'tela', 4, 0.0, False, own=own)
out.append('sim video restart, sair do estado cancela: %s' % (
    'ok' if p.log == ['seek 0.0', 'play'] and 'v' not in c._ticks and not done('v') else 'FALHA'))
open(os.environ['GEN_OUT'] + '.txt', 'w', encoding='utf-8').write('\n'.join(out) + '\n')
