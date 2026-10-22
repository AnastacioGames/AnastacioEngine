import bge, os
LOG = os.environ.get('VTEST_LOG', 'c.log'); st = {'f': 0}
def log(*a):
    with open(LOG, 'a') as f: f.write(' '.join(str(x) for x in a) + '\n')
def tick(cont):
    st['f'] += 1; f = st['f']; w = bge.logic.getCurrentScene().world
    try:
        if f == 1: log('start', w.getWeather('clouds'), w.getWeather('lens_flare'))
        if f == 40: bge.render.makeScreenshot(LOG + '_A.png')
        if f == 42: w.setWeather('clouds', True); w.setWeather('lens_flare', True); log('on', w.getWeather('clouds'), w.getWeather('lens_flare'))
        if f == 80: bge.render.makeScreenshot(LOG + '_B.png')
        if f == 82: w.setWeather('clouds', False); w.setWeather('lens_flare', False); log('off')
        if f == 120: bge.render.makeScreenshot(LOG + '_C.png')
        if f == 124: log('done'); bge.logic.endGame()
    except Exception:
        import traceback; log('EXC', traceback.format_exc()); bge.logic.endGame()
