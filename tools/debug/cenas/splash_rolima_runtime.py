"""Controles da composicao; captura somente quando o usuario pressiona F12."""
import json
import os
import Range

_speed_filter = None


def tick(cont):
    global _speed_filter
    own = cont.owner
    scene = Range.logic.getCurrentScene()
    frame = own.get('splash_frame', 0) + 1
    own['splash_frame'] = frame
    log = os.environ.get('SPLASH_LOG')
    if frame == 1:
        own['impact_next'] = Range.logic.getRealTime() + 2.0
        if log:
            with open(log, 'w') as f:
                f.write('RUNTIME_STARTED\n')
        for obj in scene.objects:
            if obj.name.startswith('Hero_Piloto_') and hasattr(obj, 'playAction') and 'Armature' in obj.name:
                obj.playAction('CARRO_Main_drive_position', 1, 1)
        if not os.environ.get('SPLASH_SMOKE'):
            from splash_rolima_speed_data import SHADER
            _speed_filter = scene.filterManager.addFilter(0, Range.logic.RAS_2DFILTER_CUSTOMFILTER, SHADER)
            _speed_filter.setUniform('u_strength', 0.10)
            own['speed_effect'] = True
            if log:
                with open(log, 'a') as f:
                    f.write('SPEED_FILTER_COMPILE_LOG=' + str(_speed_filter.compileLog) + '\n')
    if frame == 30 and log:
        with open(log, 'a') as f:
            json.dump({'scene': scene.name, 'frame': frame, 'objects': len(scene.objects),
                       'camera': scene.active_camera.name, 'status': 'runtime_ok'}, f)
    events = Range.logic.keyboard.events
    pressed = lambda key: events.get(key) == Range.logic.KX_INPUT_JUST_ACTIVATED
    if pressed(Range.events.BKEY) and _speed_filter is not None:
        own['speed_effect'] = not own.get('speed_effect', True)
        _speed_filter.setUniform('u_strength', 0.10 if own['speed_effect'] else 0.0)
    now = Range.logic.getRealTime()
    if pressed(Range.events.RKEY) or now >= own['impact_next']:
        own['impact_next'] = now + 10.0
        own['impact_pulses'] = 5
        own['impact_pulse_next'] = now
        emitter = scene.objects['Splash_Raio_Impacto']
        bomb = scene.addObject('Splash_Explosao_Template', scene.objects['Splash_Impacto_Alvo'], 0)
        detonated = bomb.detonate()
        if os.environ.get('SPLASH_CAPTURE') and not own.get('capture_done', False):
            own['capture_at'] = now + 0.12
        if log:
            with open(log, 'a') as f:
                f.write('\nIMPACT time=%.3f detonate=%s next=%.3f\n' % (now, detonated, own['impact_next']))
    if own.get('impact_pulses', 0) > 0 and now >= own['impact_pulse_next']:
        scene.objects['Splash_Raio_Impacto'].strikeLightning(True)
        own['impact_pulses'] -= 1
        own['impact_pulse_next'] = now + 0.18
    if 'capture_at' in own and now >= own['capture_at'] and not own.get('capture_done', False):
        Range.render.makeScreenshot(os.environ['SPLASH_CAPTURE'])
        own['capture_done'] = True
        if log:
            with open(log, 'a') as f:
                f.write('\nCAPTURE_REQUESTED\n')
    if pressed(Range.events.F12KEY):
        dest = Range.logic.expandPath('//captura-splash-060.png')
        Range.render.makeScreenshot(dest)
        print('Splash salvo em', dest)
    if os.environ.get('SPLASH_SMOKE') and frame >= 120:
        if log:
            with open(log, 'a') as f:
                f.write('\nSMOKE_COMPLETED_120\n')
        Range.logic.endGame()
