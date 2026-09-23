"""Smoke test for Ketsji Plano 1A, item 3 (rate validation).

Run from the repository root after building both executables:
  build/bin/RangeRuntime.exe -w 640 360 -d gpu \
    -p projects-teste/scripts/ketsji_rate_validation_smoke.py \
    "projects-teste/Teste de nova luz e sombra.range"

Any scene works: this test does not touch rendering or shadows. It calls
setLogicTicRate/setRenderRate/setAnimationRate with zero, negative, NaN and
infinite values and asserts the corresponding getter keeps the last valid
rate. It also confirms a valid rate is still accepted afterwards.
"""

import traceback

from Range import logic

INVALID_VALUES = (0.0, -1.0, -60.0, float("nan"), float("inf"), float("-inf"))


def check_rejects_invalid(name, setter, getter, valid_value):
    setter(valid_value)
    baseline = getter()
    assert baseline == valid_value, "{} did not accept a valid rate".format(name)

    for bad in INVALID_VALUES:
        setter(bad)
        current = getter()
        assert current == baseline, (
            "{} changed on invalid input {} (got {}, expected {})".format(
                name, bad, current, baseline
            )
        )

    other_valid = valid_value * 2.0
    setter(other_valid)
    assert getter() == other_valid, "{} rejected a valid rate after invalid input".format(name)


def run():
    check_rejects_invalid("logic tic rate", logic.setLogicTicRate, logic.getLogicTicRate, 60.0)
    check_rejects_invalid("render rate", logic.setRenderRate, logic.getRenderRate, 60.0)
    check_rejects_invalid("animation rate", logic.setAnimationRate, logic.getAnimationRate, 60.0)
    print("KETSJI_RATE_VALIDATION_SMOKE: PASS", flush=True)
    logic.endGame()
    logic.NextFrame()


try:
    run()
except Exception:
    print("KETSJI_RATE_VALIDATION_SMOKE: FAIL", flush=True)
    traceback.print_exc()
    logic.endGame()
    logic.NextFrame()
