import bge, os
LOG = os.environ.get('VTEST_LOG', 'r.log'); st = {'f': 0}
def log(*a):
    with open(LOG, 'a') as f: f.write(' '.join(str(x) for x in a) + '\n')
def tick(cont):
    st['f'] += 1; f = st['f']; w = bge.logic.getCurrentScene().world
    try:
        if f == 1: log('rain_start', w.getWeather('rain'))
        if f == 40: bge.render.makeScreenshot(LOG + '_A.png')
        if f == 42: w.setWeather('rain', True); w.setWeather('intensity', 1.0) if False else None; log('rain_on', w.getWeather('rain'))
        if f == 80: bge.render.makeScreenshot(LOG + '_B.png')
        if f == 82: w.setWeather('rain', False); log('rain_off', w.getWeather('rain'))
        if f == 120: bge.render.makeScreenshot(LOG + '_C.png')
        if f == 124: log('done'); bge.logic.endGame()
    except Exception:
        import traceback; log('EXC', traceback.format_exc()); bge.logic.endGame()
