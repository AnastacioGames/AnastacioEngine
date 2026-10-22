import bge, os
LOG = os.environ.get('VTEST_LOG', 'rc.log'); st = {'f': 0}
def log(*a):
    with open(LOG, 'a') as f: f.write(' '.join(str(x) for x in a) + '\n')
def tick(cont):
    st['f'] += 1; f = st['f']; sc = bge.logic.getCurrentScene()
    try:
        ch = sc.objects['GT2_a-a7r']; v = ch.getVehicle(); n = v.getNumWheels()
        if f == 60:
            M = ch.worldTransform.inverted()
            for i in range(n):
                cp = v.getWheelConfig(i)['connectionPoint']
                wp = M * v.getWheelPosition(i)
                log('wheel', i, 'cfg', [round(x,3) for x in cp], 'real', [round(x,3) for x in wp], 'dy', round(wp[1]-cp[1],3))
            log('done'); bge.logic.endGame()
    except Exception:
        import traceback; log('EXC', traceback.format_exc()); bge.logic.endGame()
