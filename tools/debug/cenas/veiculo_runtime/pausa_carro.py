import bge, os
LOG = os.environ.get('VTEST_LOG', 'pc.log'); st = {'f': 0}
def log(*a):
    with open(LOG, 'a') as f: f.write(' '.join(str(x) for x in a) + '\n')
def r(v): return [round(x, 3) for x in v]
def tick(cont):
    st['f'] += 1; f = st['f']; sc = bge.logic.getCurrentScene()
    try:
        ch = sc.objects['GT2_a-a7r']; v = ch.getVehicle(); n = v.getNumWheels()
        if f == 60: bge.logic.setTimeScale(0.0); log('pause pos', r(ch.worldPosition), 'vel', r(ch.worldLinearVelocity))
        if 60 <= f < 120:
            for i in range(n): v.applyEngineForce(3000, i)
            ch.applyTorque((0, 0, 3000), False); ch.applyForce((0, 2000, 0), False)
        if f == 119: log('paused pos', r(ch.worldPosition), 'vel', r(ch.worldLinearVelocity))
        if f == 120:
            bge.logic.setTimeScale(1.0)
            for i in range(n): v.applyEngineForce(0, i)
        if f in (122, 140): log('resume+%d pos' % (f-120), r(ch.worldPosition), 'vel', r(ch.worldLinearVelocity), 'ang', r(ch.worldAngularVelocity))
        if f == 142: log('done'); bge.logic.endGame()
    except Exception:
        import traceback; log('EXC', traceback.format_exc()); bge.logic.endGame()
