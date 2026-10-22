import bge, os
LOG = os.environ.get('VTEST_LOG', 'p.log'); st = {'f': 0}
def log(*a):
    with open(LOG, 'a') as f: f.write(' '.join(str(x) for x in a) + '\n')
def tick(cont):
    st['f'] += 1; f = st['f']; sc = bge.logic.getCurrentScene()
    try:
        b = sc.objects['Caixa']
        if f == 30: log('fixed', bge.logic.getUseFixedTimestep() if hasattr(bge.logic,'getUseFixedTimestep') else '?'); bge.logic.setTimeScale(0.0); log('pause pos', list(b.worldPosition), 'vel', list(b.worldLinearVelocity))
        if 30 <= f < 90:
            b.applyForce((0, 0, 200), False); b.applyTorque((0, 0, 50), False)
        if f == 89: log('paused pos', list(b.worldPosition), 'vel', list(b.worldLinearVelocity))
        if f == 90: bge.logic.setTimeScale(1.0)
        if f == 92: log('resume+2 pos', list(b.worldPosition), 'vel', list(b.worldLinearVelocity), 'ang', list(b.worldAngularVelocity))
        if f == 95: log('done'); bge.logic.endGame()
    except Exception:
        import traceback; log('EXC', traceback.format_exc()); bge.logic.endGame()
