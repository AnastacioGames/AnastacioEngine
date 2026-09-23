"""
Benchmark automatico com relatorio - AnastacioEngine (versao KX_PythonComponent).

Uso: no objeto que vai rodar o benchmark, adicione este componente pela
aba de Python Components do editor (nao precisa de sensor/controller,
o proprio sistema de componentes chama update() todo frame sozinho).

Campos editaveis no painel do componente (args):
    duration        (float) duracao do benchmark em segundos. Padrao: 10.0
    sample_interval (float) intervalo entre amostras em segundos. Padrao: 1.0
    output_dir      (string) pasta de saida, relativa ao arquivo da cena.
                    Padrao: "//benchmarks/"

Ao final da duracao, escreve um relatorio .txt em output_dir com
media/minimo/maximo por categoria do profiler, FPS medio e a progressao
da contagem de objetos ao longo do tempo. Tambem grava benchmark_debug.log
a cada amostra, para diagnostico mesmo se o console estiver cheio de
outros logs (ex.: GPU_texture_bind).
"""

from collections import OrderedDict
import Range
import os
import time
import traceback


class BenchmarkComponent(Range.types.KX_PythonComponent):
    args = OrderedDict([
        ("duration", 10.0),
        ("sample_interval", 1.0),
        ("output_dir", "//benchmarks/"),
    ])

    def start(self, args):
        self.duration = args["duration"]
        self.sample_interval = args["sample_interval"]
        self.output_dir = args["output_dir"]

        self.resolved_dir = Range.logic.expandPath(self.output_dir)
        os.makedirs(self.resolved_dir, exist_ok=True)

        self.start_time = time.perf_counter()
        self.last_sample = 0.0
        self.frames = 0
        self.samples = []
        self.done = False

        msg = "iniciado (component) - duracao: {:.1f}s, intervalo: {:.1f}s, output_dir: {}".format(
            self.duration, self.sample_interval, self.resolved_dir)
        print("[Benchmark] {}".format(msg))
        self._debug_log(msg)

    def update(self):
        if self.done:
            return

        try:
            self._update()
        except Exception:
            tb = traceback.format_exc()
            print("[Benchmark][ERRO]\n{}".format(tb))
            self._debug_log("ERRO:\n{}".format(tb))
            self.done = True

    def _update(self):
        scene = Range.logic.getCurrentScene()

        self.frames += 1
        elapsed = time.perf_counter() - self.start_time

        if elapsed - self.last_sample >= self.sample_interval:
            self.last_sample = elapsed
            profile = Range.logic.getProfileInfo()
            snapshot = {
                "t": elapsed,
                "objects": len(scene.objects),
                "profile": dict(profile),
            }
            self.samples.append(snapshot)
            msg = "amostra #{} t={:.2f}s frames={} objetos={}".format(
                len(self.samples), elapsed, self.frames, snapshot["objects"])
            print("[Benchmark] {}".format(msg))
            self._debug_log(msg)

        if elapsed >= self.duration:
            self._debug_log("duracao atingida ({:.2f}s >= {:.1f}s), escrevendo relatorio...".format(
                elapsed, self.duration))
            self._write_report(scene, elapsed)
            self.done = True

    def _debug_log(self, msg):
        try:
            path = os.path.join(self.resolved_dir, "benchmark_debug.log")
            with open(path, "a", encoding="utf-8") as f:
                f.write("[{}] {}\n".format(time.strftime("%H:%M:%S"), msg))
        except Exception:
            print("[Benchmark][debug-log-falhou] {}".format(msg))

    def _write_report(self, scene, elapsed):
        samples = self.samples
        frames = self.frames

        if not samples:
            print("[Benchmark] nenhuma amostra coletada, relatorio nao gerado.")
            self._debug_log("nenhuma amostra coletada, relatorio nao gerado.")
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

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(self.resolved_dir, "benchmark_report_{}.txt".format(timestamp))

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
        self._debug_log("relatorio gerado em: {}".format(filename))
