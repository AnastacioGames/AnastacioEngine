import bge, os
LOG = os.environ.get('VTEST_LOG', 'vtest.log')
st = {'f': 0}
def log(*a):
    with open(LOG, 'a') as f: f.write(' '.join(str(x) for x in a) + '\n')
def expect_err(fn, name):
    try: fn(); log('FAIL no error:', name)
    except (ValueError, TypeError) as e: log('OK error:', name, e)
def tick(cont):
    st['f'] += 1; f = st['f']
    sc = bge.logic.getCurrentScene(); ch = sc.objects['GT2_a-a7r']; v = ch.getVehicle()
    n = v.getNumWheels()
    try:
        if f == 1: log('wheels', n, 'torque', ch.getVehicleMaxTorque(), 'rpm', ch.getVehicleMaxRPM(), 'gears', ch.getVehicleGearRatios())
        if f == 90:
            log('contact', [v.getWheelState(i)['isInContact'] for i in range(n)], 'force', [round(v.getWheelState(i)['suspensionForce'],1) for i in range(n)])
            log('z_before', round(ch.worldPosition.z, 3))
            ch.setVehicleMaxTorque(123.0); ch.setVehicleMaxRPM(4567); ch.setVehicleGearRatios([3.5, 2.0, 1.25])
            log('engine_set', ch.getVehicleMaxTorque(), ch.getVehicleMaxRPM(), ch.getVehicleGearRatios())
            expect_err(lambda: ch.setVehicleMaxTorque(-1), 'torque<0')
            expect_err(lambda: ch.setVehicleGearRatios(['x']), 'gears str')
            expect_err(lambda: v.setSuspensionRestLength(0, 0), 'rest 0')
            expect_err(lambda: v.setSuspensionRestLength(0.3, 99), 'rest idx')
            st['rest'] = [v.getWheelConfig(i)['suspensionRestLength'] for i in range(n)]
            st['rad'] = [v.getWheelConfig(i)['wheelRadius'] for i in range(n)]
            for i in range(n):
                v.setSuspensionRestLength(st['rest'][i] + 0.15, i)
                v.setWheelRadius(st['rad'][i] * 1.1, i)
        if f == 92:
            p = LOG + '.preset.json'
            v.savePreset(p); st['p'] = p
            log('rest', [round(x,3) for x in st['rest']], '->', [round(v.getWheelConfig(i)['suspensionRestLength'],3) for i in range(n)])
            log('radius', [round(x,3) for x in st['rad']], '->', [round(v.getWheelConfig(i)['wheelRadius'],3) for i in range(n)])
        if f == 200:
            log('z_after', round(ch.worldPosition.z, 3))
            ch.setVehicleMaxTorque(999.0)
            v.loadPreset(st['p'])
            log('after_loadPreset torque', ch.getVehicleMaxTorque())
            log('contact_end', [v.getWheelState(i)['isInContact'] for i in range(n)])
        if f == 202:
            log('done'); bge.logic.endGame()
    except Exception as e:
        import traceback; log('EXC', traceback.format_exc()); bge.logic.endGame()
