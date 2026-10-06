"""Shared sampler for the perf_* test scenes: warmup, sample, write one report, quit.

The perf scene generators copy this file into the .range as a text block so the runtime can
``import perf_probe``; it is never imported by the editor. Each generated scene calls
:func:`tick` once per logic tick from its Always sensor.

Report goes to ``//perf_<scene>_<tag>.txt`` in append mode, tag from ``RANGE_SHOT_TAG``
(default ``run``), so A/B rounds of the same build accumulate in one file.

Warmup is adaptive, then sampling is measured in **real seconds**, not ticks. Adaptive matters
because GLSL programs compile lazily on first draw: a case with 900 distinct materials spends
many seconds inside a handful of ticks, and a fixed warmup would start sampling in the middle of
that and report a frame time hundreds of times too high. Sampling therefore starts only once
STABLE_TICKS consecutive ticks have each come in under STABLE_MS. The perf scenes run a high
logic ticrate so the engine's frame cap sits far above the cost being measured
(KX_KetsjiEngine::UpdateSleepTime always sleeps up to 1/ticrate, so FPS can never exceed the
ticrate no matter what "Use Frame Rate" is set to), and at a high ticrate a fixed tick count
would mean a different wall-clock duration for every case.

The engine's own counters (draw calls, light binds, culling, shadow passes) are reported as
min/max, not as an average: in a deterministic scene they must be constant. A min different
from the max means the scene varies between frames and its timings cannot be used for A/B.
"""
import os

WARMUP_SEC = float(os.environ.get("RANGE_PERF_WARMUP_SEC", "1.0"))
SAMPLE_SEC = float(os.environ.get("RANGE_PERF_SAMPLE_SEC", "10.0"))
# A tick slower than this is treated as still compiling shaders, not as the scene's real cost.
STABLE_MS = float(os.environ.get("RANGE_PERF_STABLE_MS", "120.0"))
STABLE_TICKS = int(os.environ.get("RANGE_PERF_STABLE_TICKS", "20"))
# Safety net so a genuinely heavy scene still reports instead of running forever.
WARMUP_MAX_SEC = float(os.environ.get("RANGE_PERF_WARMUP_MAX_SEC", "120.0"))

# Counters that legitimately vary frame to frame, so a min != max on them is not a warning.
# controllersTriggered/actuatorsUpdated are read mid-frame (see bge.logic.getRenderStats docs).
_NOISY = ("controllersTriggered", "actuatorsUpdated")


def _state():
    import Range
    g = Range.logic.globalDict
    st = g.get("_perf")
    if st is None:
        st = g["_perf"] = {"n": 0, "cat": {}, "fps": 0.0, "stat": {},
                           "samples": 0, "t0": None, "done": False,
                           "boot": None, "prev": None, "stable": 0}
    return st


def tick(scene, meta=None, camera=None):
    """Advance one sample. ``scene`` names the report, ``meta`` is an ordered list of
    ``(label, value)`` pairs for the header (object/light/material counts). ``camera``, when
    given, is called as ``camera(n)`` with the tick number so the view is a function of the
    tick and not of elapsed time -- two runs then draw exactly the same frames."""
    import Range

    st = _state()
    st["n"] += 1
    n = st["n"]

    if camera is not None:
        camera(n)

    if st["done"]:
        return

    now = Range.logic.getClockTime()
    if st["boot"] is None:
        st["boot"] = now
        st["prev"] = now
        return

    if st["t0"] is None:
        delta_ms = (now - st["prev"]) * 1000.0
        st["prev"] = now
        st["stable"] = st["stable"] + 1 if delta_ms <= STABLE_MS else 0
        if st["stable"] < STABLE_TICKS and (now - st["boot"]) < WARMUP_MAX_SEC:
            return
        st["t0"] = now
        st["boot_sec"] = now - st["boot"]
        return

    elapsed = now - st["t0"]
    if elapsed < WARMUP_SEC:
        return

    st["samples"] += 1
    profile = Range.logic.getProfileInfo()
    cat = st["cat"]
    for key, value in profile.items():
        ms = value[0] if isinstance(value, (tuple, list)) else float(value)
        acc = cat.get(key)
        if acc is None:
            cat[key] = [ms, ms, ms]        # sum, min, max
        else:
            acc[0] += ms
            acc[1] = min(acc[1], ms)
            acc[2] = max(acc[2], ms)

    st["fps"] += Range.logic.getAverageFrameRate()

    stat = st["stat"]
    for key, value in Range.logic.getRenderStats().items():
        acc = stat.get(key)
        if acc is None:
            stat[key] = [value, value]     # min, max
        else:
            acc[0] = min(acc[0], value)
            acc[1] = max(acc[1], value)

    if elapsed >= WARMUP_SEC + SAMPLE_SEC:
        st["done"] = True
        _report(scene, meta or [], elapsed - WARMUP_SEC)
        Range.logic.endGame()


def _report(scene, meta, duration):
    import Range

    st = _state()
    tag = os.environ.get("RANGE_SHOT_TAG", "run")
    path = Range.logic.expandPath("//perf_%s_%s.txt" % (scene, tag))

    samples = max(st["samples"], 1)
    fps = st["fps"] / samples
    out = []
    out.append("=" * 78)
    out.append("scene %s   tag %s   warmup %.1fs (+%.1fs to settle)   sampled %.2fs over %d ticks"
               % (scene, tag, WARMUP_SEC, st.get("boot_sec", 0.0), duration, samples))
    if meta:
        out.append("  " + "   ".join("%s=%s" % (k, v) for k, v in meta))
    out.append("  %.1f fps reported   %.1f ticks/s   %.3f ms/tick"
               % (fps, samples / max(duration, 1e-3), 1000.0 * duration / samples))
    out.append("")
    out.append("%-26s %9s %9s %9s" % ("category", "avg ms", "min ms", "max ms"))
    # Heaviest first: the point of the report is which category to attack.
    for key, acc in sorted(st["cat"].items(), key=lambda kv: -kv[1][0]):
        avg = acc[0] / samples
        if avg < 1e-4 and acc[2] < 1e-4:
            continue
        out.append("%-26s %9.4f %9.4f %9.4f" % (key, avg, acc[1], acc[2]))
    out.append("")
    out.append("%-26s %9s %9s" % ("counter", "min", "max"))
    for key in sorted(st["stat"]):
        lo, hi = st["stat"][key]
        warn = "   <-- VARIES, scene is not deterministic" if lo != hi and key not in _NOISY else ""
        out.append("%-26s %9d %9d%s" % (key, lo, hi, warn))
    out.append("")

    with open(path, "a") as f:
        f.write("\n".join(out))
