"""Runs the perf_* scenes and prints a comparison table.

    python tools/run_perf_suite.py projects-teste/perf/pbr_lights
    python tools/run_perf_suite.py projects-teste/perf/pbr_lights --tags before after --rounds 3
    python tools/run_perf_suite.py projects-teste/perf/pbr_lights --report-only

With two tags the rounds **alternate** (A,B,A,B,...) instead of running A three times and then B
three times: GPU clocks and thermal throttling drift over a session, and a grouped order charges
that drift to the change under test. Alternating spreads it over both tags.

Each round appends to the scene's perf_<case>_<tag>.txt, so the dispersion between rounds is
visible; a delta smaller than the spread within one tag means nothing.
"""
import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNTIME = os.path.join(ROOT, "build", "bin", "AnastacioRuntime.exe")

HEADER = re.compile(r"^scene (\S+)\s+tag (\S+)")
FPS = re.compile(r"([\d.]+) fps reported\s+([\d.]+) ticks/s\s+([\d.]+) ms/tick")
ROW = re.compile(r"^(\S.*?)\s{2,}([\d.]+)\s+([\d.]+)\s+([\d.]+)$")
COUNTER = re.compile(r"^(\w+)\s+(\d+)\s+(\d+)")


def runs(path):
    """Every report block in one perf_*.txt, as {'ms', 'fps', 'cat', 'counters'}."""
    out = []
    section = None
    with open(path) as f:
        for line in f:
            line = line.rstrip("\n")
            if HEADER.match(line.strip()):
                section = {"cat": {}, "counters": {}, "ms": None, "fps": None}
                out.append(section)
                mode = None
                continue
            if section is None:
                continue
            m = FPS.search(line)
            if m:
                section["fps"] = float(m.group(1))
                section["ms"] = float(m.group(3))
                continue
            if line.startswith("category"):
                mode = "cat"
                continue
            if line.startswith("counter"):
                mode = "counters"
                continue
            if not line.strip():
                continue
            if mode == "cat":
                m = ROW.match(line)
                if m:
                    section["cat"][m.group(1).strip()] = float(m.group(2))
            elif mode == "counters":
                m = COUNTER.match(line.strip())
                if m:
                    section["counters"][m.group(1)] = (int(m.group(2)), int(m.group(3)))
    return out


def play(scene, tag, env_extra):
    env = dict(os.environ)
    env["RANGE_SHOT_TAG"] = tag
    env.update(env_extra)
    print("  [%s] %s" % (tag, os.path.basename(scene)))
    subprocess.call([RUNTIME, scene], env=env, cwd=ROOT)


def stats(values):
    if not values:
        return 0.0, 0.0
    avg = sum(values) / len(values)
    return avg, (max(values) - min(values))


def report(outdir, cases, tags):
    print()
    print("%-28s %-8s %8s %7s %8s %7s %9s %9s"
          % ("case", "tag", "ms/tick", "spread", "fps", "runs", "drawCalls", "lightBinds"))
    for case in cases:
        for tag in tags:
            path = os.path.join(outdir, "perf_%s_%s.txt" % (case, tag))
            if not os.path.exists(path):
                continue
            blocks = runs(path)
            if not blocks:
                continue
            ms, spread = stats([b["ms"] for b in blocks if b["ms"] is not None])
            fps, _ = stats([b["fps"] for b in blocks if b["fps"] is not None])
            counters = blocks[-1]["counters"]
            print("%-28s %-8s %8.3f %6.1f%% %8.1f %7d %9s %9s"
                  % (case, tag, ms, 100.0 * spread / max(ms, 1e-9), fps, len(blocks),
                     counters.get("drawCalls", ("-",))[0],
                     counters.get("lightBinds", ("-",))[0]))

    if len(tags) == 2:
        a, b = tags
        print()
        print("delta %s -> %s   (negative ms = faster; counters must move as predicted)" % (a, b))
        print("%-28s %10s %10s %10s" % ("case", "ms", "lightBinds", "drawCalls"))
        for case in cases:
            pa = os.path.join(outdir, "perf_%s_%s.txt" % (case, a))
            pb = os.path.join(outdir, "perf_%s_%s.txt" % (case, b))
            if not (os.path.exists(pa) and os.path.exists(pb)):
                continue
            ba, bb = runs(pa), runs(pb)
            if not (ba and bb):
                continue
            ma, _ = stats([x["ms"] for x in ba if x["ms"] is not None])
            mb, _ = stats([x["ms"] for x in bb if x["ms"] is not None])
            ca = ba[-1]["counters"]
            cb = bb[-1]["counters"]
            def dc(key):
                va, vb = ca.get(key), cb.get(key)
                if va is None or vb is None:
                    return "-"
                return "%d->%d" % (va[0], vb[0])
            print("%-28s %9.1f%% %10s %10s"
                  % (case, 100.0 * (mb - ma) / max(ma, 1e-9), dc("lightBinds"), dc("drawCalls")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("outdir", help="directory holding the generated .range cases")
    ap.add_argument("--tags", nargs="+", default=["run"], help="one tag, or two to compare")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--filter", default="", help="substring a case name must contain")
    ap.add_argument("--sample-sec", default=None, help="override RANGE_PERF_SAMPLE_SEC")
    ap.add_argument("--report-only", action="store_true", help="re-read existing reports, run nothing")
    args = ap.parse_args()

    outdir = os.path.abspath(args.outdir)
    scenes = sorted(f for f in os.listdir(outdir)
                    if f.endswith(".range") and args.filter in f)
    if not scenes:
        sys.exit("no .range cases in %s" % outdir)
    cases = [os.path.splitext(f)[0] for f in scenes]

    if not args.report_only:
        if not os.path.exists(RUNTIME):
            sys.exit("missing %s -- build RangeRuntime first" % RUNTIME)
        env_extra = {}
        if args.sample_sec:
            env_extra["RANGE_PERF_SAMPLE_SEC"] = args.sample_sec
        # Old reports would be appended to and mixed into the averages.
        for case in cases:
            for tag in args.tags:
                stale = os.path.join(outdir, "perf_%s_%s.txt" % (case, tag))
                if os.path.exists(stale):
                    os.remove(stale)
        for r in range(args.rounds):
            print("round %d/%d" % (r + 1, args.rounds))
            for tag in args.tags:          # alternating, see the module docstring
                for scene in scenes:
                    play(os.path.join(outdir, scene), tag, env_extra)

    report(outdir, cases, args.tags)


if __name__ == "__main__":
    main()
