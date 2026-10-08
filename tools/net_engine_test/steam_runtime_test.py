"""B2 smoke test: RangeRuntime --server -p this_script minimal.range.
Set ANASTACIO_STEAM_DLL to a local complement; optional ANASTACIO_EXPECT_STEAM=online/offline.
Never opens or rewrites the user's game. Does not print account identity.
"""
import os
import traceback
from Range import logic
from Range.network import steam

def check(ok, text):
    if not ok:
        raise AssertionError(text)
    print("STEAMTEST ok " + text, flush=True)

try:
    check(not steam.status()['loaded'], 'starts without complement')
    for app_id in (0, -1, 2**32):
        try:
            steam.initialize('missing.dll', app_id)
        except (ValueError, OverflowError):
            pass
        else:
            raise AssertionError('invalid AppID accepted')
    try:
        steam.initialize('missing.dll', 480)
    except RuntimeError:
        pass
    else:
        raise AssertionError('missing complement accepted')
    check(not steam.status()['loaded'], 'missing DLL cleaned up')
    fixture = os.environ['ANASTACIO_STEAM_FIXTURE']
    check(steam.initialize(fixture, 480), 'fixture initializes through Python')
    first = steam.status()['steam_id']
    check(first == 76561198000000000, 'identity remains exact uint64')
    for i in range(4):
        logic.NextFrame()
    check(steam.status()['steam_id'] > first, 'engine pumps callbacks')
    try:
        steam.initialize(fixture, 480)
    except RuntimeError:
        pass
    else:
        raise AssertionError('duplicate initialization accepted')
    steam.shutdown()
    steam.shutdown()
    check(not steam.status()['loaded'], 'shutdown is idempotent')
    real_dll = os.environ['ANASTACIO_STEAM_DLL']
    expected = os.environ.get('ANASTACIO_EXPECT_STEAM', 'auto')
    try:
        steam.initialize(real_dll, 480)
    except RuntimeError as error:
        check('Unable to load' not in str(error) and 'ABI' not in str(error), 'real DLL loads and reaches SDK initialization')
        check(expected != 'online', 'offline initialization fails clearly')
        check(not steam.status()['loaded'], 'failed real init releases service')
        print('STEAMTEST real SDK unavailable: ' + str(error), flush=True)
    else:
        check(expected != 'offline', 'real SDK online')
        check(steam.status()['ready'] and steam.status()['steam_id'] > 0, 'real identity available')
        for i in range(30):
            logic.NextFrame()
        steam.shutdown()
        check(steam.initialize(real_dll, 480), 'real SDK can reinitialize after shutdown')
        print('STEAMTEST real SDK online PASS', flush=True)
    steam.shutdown()
    check(steam.initialize(fixture, 480), 'final fixture ready for engine stop cleanup')
    print('STEAMTEST PASS', flush=True)
except Exception:
    traceback.print_exc()
    print('STEAMTEST FAIL', flush=True)
finally:
    # Leave final context live: engine stop must call shutdown before fixture destroy.
    logic.endGame()
    logic.NextFrame()
