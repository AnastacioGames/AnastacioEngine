"""
Benchmark automatico com relatorio - AnastacioEngine.

Uso: crie um objeto na cena (ex.: BenchmarkManager) com um Python Controller
em modo "Module" apontando para "benchmark_report.run", ligado a um Always
sensor com pulso true (True Level Triggering) para rodar a cada frame.

Propriedades de jogo (game properties) opcionais no objeto:
    duration        (float) duracao do benchmark em segundos. Padrao: 10.0
    sample_interval (float) intervalo entre amostras em segundos. Padrao: 1.0
    output_dir      (string) pasta de saida, relativa ao arquivo da cena.
                    Padrao: "//benchmarks/"

Ao final da duracao configurada, escreve um relatorio .txt em output_dir
com media/minimo/maximo por categoria do profiler, FPS medio e a
progressao da contagem de objetos ao longo do tempo. Depois se desativa.'

Modo debug: a cada chamada, grava uma linha em benchmark_debug.log (na
mesma pasta de output_dir) com o frame atual, elapsed e ultimo erro, para
diagnosticar sem depender do console (que pode estar cheio de outros logs).
"""

import Range as bge
import os
import time
import traceback


def _debug_dir():
    output_dir = "//benchmarks/"
    try:
        owner_dir = bge.logic.getCurrentController().owner.get("output_dir", output_dir)
        output_dir = owner_dir
    except Exception:
        pass
    resolved = bge.logic.expandPath(output_dir)
    os.makedirs(resolved, exist_ok=True)
    return resolved


def _debug_log(msg):
    try:
        resolved = _debug_dir()
        path = os.path.join(resolved, "benchmark_debug.log")
        with open(path, "a", encoding="utf-8") as f:
            f.write("[{}] {}\n".format(time.strftime("%H:%M:%S"), msg))
    except Exception:
        print("[Benchmark][debug-log-falhou] {}".format(msg))


def run(cont):
    try:
        _run(cont)
    except Exception:
        tb = traceback.format_exc()
        print("[Benchmark][ERRO]\n{}".format(tb))
        _debug_log("ERRO:\n{}".format(tb))


def _run(cont):
    owner = cont.owner

    if owner.get("_benchmark_done", False):
        return

    duration = owner.get("duration", 10.0)
    sample_interval = owner.get("sample_interval", 1.0)
    output_dir = owner.get("output_dir", "//benchmarks/")

    scene = bge.logic.getCurrentScene()

    if "_benchmark_start" not in owner:
        owner["_benchmark_start"] = time.perf_counter()
        owner["_benchmark_last_sample"] = 0.0
        owner["_benchmark_frames"] = 0
        owner["_benchmark_samples"] = []
        resolved_dir = bge.logic.expandPath(output_dir)
        msg = "iniciado - duracao: {:.1f}s, intervalo: {:.1f}s, output_dir resolvido: {}".format(
            duration, sample_interval, resolved_dir)
        print("[Benchmark] {}".format(msg))
        _debug_log(msg)

    owner["_benchmark_frames"] += 1
    elapsed = time.perf_counter() - owner["_benchmark_start"]

    if elapsed - owner["_benchmark_last_sample"] >= sample_interval:
        owner["_benchmark_last_sample"] = elapsed
        profile = bge.logic.getProfileInfo()
        snapshot = {
            "t": elapsed,
            "objects": len(scene.objects),
            "profile": dict(profile),
        }
        owner["_benchmark_samples"].append(snapshot)
        msg = "amostra #{} t={:.2f}s frames={} objetos={}".format(
            len(owner["_benchmark_samples"]), elapsed, owner["_benchmark_frames"], snapshot["objects"])
        print("[Benchmark] {}".format(msg))
        _debug_log(msg)

    if elapsed >= duration:
        _debug_log("duracao atingida ({:.2f}s >= {:.1f}s), escrevendo relatorio...".format(elapsed, duration))
        _write_report(owner, scene, elapsed, output_dir)
        owner["_benchmark_done"] = True


def _write_report(owner, scene, elapsed, output_dir):
    samples = owner["_benchmark_samples"]
    frames = owner["_benchmark_frames"]

    if not samples:
        print("[Benchmark] nenhuma amostra coletada, relatorio nao gerado.")
        _debug_log("nenhuma amostra coletada, relatorio nao gerado.")
        return

    categories = sorted(samples[0]["profile"].keys())
    stats = {}
    for cat in categories:
        ms_values = [s["profile"][cat][0] for s in samples if cat in s["profile"]]
        pct_values = [s["profile"][cat][1] for s in samples if cat in s["profile"]]
        if not ms_values:
            continue
        stats[cat] = {
            "avg_ms": sum(ms_values) / len(ms_values),
            "min_ms": min(ms_values),
            "max_ms": max(ms_values),
            "avg_pct": sum(pct_values) / len(pct_values),
        }

    avg_fps = frames / elapsed if elapsed > 0 else 0.0

    resolved_dir = bge.logic.expandPath(output_dir)
    os.makedirs(resolved_dir, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(resolved_dir, "benchmark_report_{}.txt".format(timestamp))

    lines = []
    lines.append("Relatorio de Benchmark - AnastacioEngine")
    lines.append("Data/hora: {}".format(time.strftime("%Y-%m-%d %H:%M:%S")))
    lines.append("Cena: {}".format(scene.name))
    lines.append("Duracao: {:.1f}s | Frames: {} | FPS medio: {:.1f}".format(
        elapsed, frames, avg_fps))
    lines.append("Amostras coletadas: {}".format(len(samples)))
    lines.append("")
    lines.append("Categorias do profiler (media / minimo / maximo em ms, media em %):")
    lines.append("-" * 64)
    for cat, s in stats.items():
        lines.append("{:<16} avg={:>8.3f}ms  min={:>8.3f}ms  max={:>8.3f}ms  avg%={:>5.1f}%".format(
            cat, s["avg_ms"], s["min_ms"], s["max_ms"], s["avg_pct"]))
    lines.append("")
    lines.append("Progressao de objetos na cena ao longo do tempo:")
    lines.append("-" * 64)
    step = max(1, len(samples) // 10)
    for i in range(0, len(samples), step):
        s = samples[i]
        lines.append("t={:>6.1f}s  objetos={}".format(s["t"], s["objects"]))
    lines.append("t={:>6.1f}s  objetos={}".format(samples[-1]["t"], samples[-1]["objects"]))

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print("[Benchmark] relatorio gerado em: {}".format(filename))
    _debug_log("relatorio gerado em: {}".format(filename))
