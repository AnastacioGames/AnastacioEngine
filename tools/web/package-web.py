#!/usr/bin/env python3
"""Empacota um jogo .range + RangeRuntime (Emscripten) numa pasta hospedavel.

Equivalente Web de tools/linux/package-runtime.sh. Nao compila nada: consome
build-web/bin/RangeRuntime.{js,wasm,data} ja gerados pelo preset web-runtime.

Saida (<out>/<name>/):
  index.html          pagina de producao (progresso, erro visivel, clique para jogar)
  RangeRuntime.*      runtime copiado do build
  game/<jogo>.range   jogo (+ arquivos extras, ao lado, no FS virtual "/")
  manifest.json       schema, hashes, tamanhos, requisitos e avisos
  SHA256SUMS.txt
  serve.py            servidor local com MIME correto (teste antes de hospedar)
  HOSTING.md          requisitos de hospedagem

Uso:
  python tools/web/package-web.py --game meu_jogo.range --name meu-jogo --version 0.1.0 --zip
"""

import argparse
import datetime
import hashlib
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

SCHEMA_VERSION = 1
REPO_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_FILES = ("RangeRuntime.js", "RangeRuntime.wasm", "RangeRuntime.data")
NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def die(msg):
    print(f"erro: {msg}", file=sys.stderr)
    sys.exit(1)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_game(path):
    if not path.is_file():
        die(f"jogo nao encontrado: {path}")
    with open(path, "rb") as f:
        head = f.read(12)
    # .range/.blend: "BLENDER" + ponteiro (_/-) + endian (v/V) + versao; pode estar comprimido (gzip).
    if not (head.startswith(b"BLENDER") or head.startswith(b"\x1f\x8b")):
        die(f"{path.name} nao parece um arquivo .range/.blend valido")


def check_runtime(runtime_dir):
    missing = [n for n in RUNTIME_FILES if not (runtime_dir / n).is_file()]
    if missing:
        die(
            f"runtime Web incompleto em {runtime_dir}: falta {', '.join(missing)}. "
            "Compile antes: cmake --build --preset web-runtime --target RangeRuntime"
        )
    with open(runtime_dir / "RangeRuntime.wasm", "rb") as f:
        if f.read(4) != b"\0asm":
            die("RangeRuntime.wasm nao tem o cabecalho WebAssembly")


def runtime_warnings(runtime_dir):
    warnings = []
    js = (runtime_dir / "RangeRuntime.js").read_bytes()
    if b"SAFE_HEAP" in js or b"safeSetHeap" in js or b"SAFE_HEAP_STORE" in js:
        warnings.append(
            "Runtime compilado com SAFE_HEAP/ASSERTIONS (build de depuracao): mais lento e maior. "
            "Use um preset Web de release antes de publicar."
        )
    if (runtime_dir / "RangeRuntime.data").stat().st_size > 50 * 1024 * 1024:
        warnings.append("Download inicial acima de 50 MiB (orcamento sugerido em web-profile-validation-plan.md).")
    return warnings


INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<link rel="icon" href="data:,">
<style>
  html, body { margin: 0; height: 100%; background: #111; color: #ddd; font-family: system-ui, sans-serif; }
  #stage { position: relative; width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; }
  canvas { max-width: 100%; max-height: 100%; background: #000; outline: none; }
  #overlay { position: absolute; inset: 0; display: flex; flex-direction: column; gap: 14px;
             align-items: center; justify-content: center; background: rgba(0,0,0,.85); text-align: center; padding: 16px; }
  #overlay[hidden] { display: none; }
  button { font-size: 18px; padding: 12px 32px; border: 0; border-radius: 6px; background: #e8862a; color: #111; cursor: pointer; }
  button:disabled { background: #555; color: #999; cursor: default; }
  progress { width: min(360px, 80vw); }
  #error { color: #ff8a80; white-space: pre-wrap; max-width: 90vw; }
  #log { display: none; position: fixed; left: 0; right: 0; bottom: 0; max-height: 35%; overflow: auto; margin: 0;
         background: rgba(0,0,0,.8); color: #9f9; font: 11px monospace; padding: 6px; white-space: pre-wrap; }
  body.debug #log { display: block; }
</style>
</head>
<body>
<div id="stage">
  <canvas id="canvas" tabindex="0" width="__WIDTH__" height="__HEIGHT__" oncontextmenu="event.preventDefault()"></canvas>
  <div id="overlay">
    <h2 id="title">__TITLE__</h2>
    <progress id="progress" max="100" value="0"></progress>
    <div id="status">Carregando...</div>
    <button id="play" disabled>Jogar</button>
    <div id="error" hidden></div>
  </div>
</div>
<pre id="log"></pre>
<script>
(function () {
  var GAME = "__GAME__";
  var EXTRAS = __EXTRAS__;
  var VERSION = "__VERSION__";
  var el = function (id) { return document.getElementById(id); };
  var debug = /[?&]debug=1/.test(location.search);
  if (debug) document.body.classList.add("debug");
  function log(s) { if (debug) el("log").textContent += s + "\\n"; }

  var failed = false;
  function fail(msg) {
    if (failed) return;
    failed = true;
    el("progress").hidden = true;
    el("play").hidden = true;
    el("status").textContent = "Nao foi possivel iniciar o jogo.";
    var e = el("error");
    e.hidden = false;
    e.textContent = msg + "\\n\\nRecarregue a pagina para tentar novamente. Use ?debug=1 para ver o log.";
    el("overlay").hidden = false;
  }

  function fetchInto(url, fsName) {
    return fetch(url + "?v=" + encodeURIComponent(VERSION)).then(function (r) {
      if (!r.ok) throw new Error(url + ": HTTP " + r.status);
      return r.arrayBuffer();
    }).then(function (buf) {
      var parts = fsName.split("/"), dir = "/";
      for (var i = 0; i < parts.length - 1; i++) {
        try { Module.FS_createPath(dir, parts[i], true, true); } catch (e) {}
        dir += parts[i] + "/";
      }
      Module.FS_createDataFile(dir, parts[parts.length - 1], new Uint8Array(buf), true, false);
      log("[fs] /" + fsName + " (" + buf.byteLength + " bytes)");
    });
  }

  var ready = false, started = false;
  function tryStart() {
    if (started || !ready) return;
    started = true;
    el("overlay").hidden = true;
    el("canvas").focus();
  }

  window.Module = {
    canvas: el("canvas"),
    arguments: [GAME],
    print: function (t) { log("[out] " + t); console.log(t); },
    printErr: function (t) { log("[err] " + t); console.error(t); },
    onAbort: function (w) { fail("O runtime foi interrompido: " + w); },
    setStatus: function (t) {
      if (failed) return;
      var m = /(.+) \\((\\d+(?:\\.\\d+)?)\\/(\\d+)\\)/.exec(t);
      if (m) { el("progress").value = 100 * m[2] / m[3]; el("status").textContent = "Baixando dados do jogo..."; }
      else if (t) el("status").textContent = t;
    },
    preRun: [function () {
      Module.addRunDependency("game-files");
      var jobs = [fetchInto("game/" + GAME, GAME)];
      EXTRAS.forEach(function (n) { jobs.push(fetchInto("game/" + n, n)); });
      Promise.all(jobs).then(function () {
        Module.removeRunDependency("game-files");
      }).catch(function (e) { fail("Falha ao baixar arquivos do jogo: " + e.message); });
    }],
    onRuntimeInitialized: function () {
      log("[event] runtime inicializado");
    }
  };

  window.addEventListener("error", function (ev) { fail("Erro: " + ev.message); });
  window.addEventListener("unhandledrejection", function (ev) {
    fail("Erro: " + (ev.reason && ev.reason.message ? ev.reason.message : ev.reason));
  });

  // O jogo so comeca a ser mostrado apos um clique: libera foco de teclado e permite audio (politica de autoplay).
  var script = document.createElement("script");
  script.src = "RangeRuntime.js?v=" + encodeURIComponent(VERSION);
  script.onerror = function () { fail("RangeRuntime.js nao foi encontrado no servidor."); };
  script.onload = function () {
    if (failed) return;
    // O runtime ja esta rodando quando os dados terminam de carregar; o botao apenas confirma o inicio.
    ready = true;
    el("progress").hidden = true;
    el("status").textContent = "Pronto.";
    el("play").disabled = false;
  };
  el("play").addEventListener("click", tryStart);
  document.body.appendChild(script);
})();
</script>
</body>
</html>
"""


SERVE_PY = '''#!/usr/bin/env python3
"""Servidor local para testar o pacote Web: python serve.py [porta]"""
import functools
import http.server
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".wasm": "application/wasm",
        ".js": "text/javascript",
        ".data": "application/octet-stream",
        ".range": "application/octet-stream",
    }

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
print(f"Servindo em http://localhost:{port}/  (Ctrl+C para parar)")
handler = functools.partial(Handler, directory=ROOT)
http.server.ThreadingHTTPServer(("", port), handler).serve_forever()
'''

HOSTING_MD = """# Hospedagem do pacote Web

Este pacote e estatico: basta servir a pasta por HTTP(S). Nao abra `index.html` por `file://`.

- Teste local: `python serve.py 8080` e abra http://localhost:8080/
- MIME: `.wasm` como `application/wasm` (senao o navegador recusa a compilacao em streaming).
- Compressao: habilite gzip/brotli para `.wasm`, `.js` e `.data` no servidor; reduz muito o download.
- Cache: os arquivos sao referenciados com `?v=<versao>`; ao publicar uma versao nova, mude a versao
  (`--version`) para nao misturar arquivos antigos e novos.
- COOP/COEP: **nao sao necessarios**. Este runtime nao usa pthreads/SharedArrayBuffer.
- Requisito do navegador: WebGL 2 (Chrome/Edge/Firefox recentes em computador). Mobile nao validado.
- Save: usa IndexedDB do navegador, isolado por origem (dominio). Limpar dados do site apaga os saves.
- Diagnostico: adicione `?debug=1` na URL para ver o log do runtime na pagina.
- `manifest.json` lista hashes e avisos do pacote; `SHA256SUMS.txt` permite conferir a integridade.
"""


def extra_rel(path, root):
    """Caminho do extra no FS virtual: relativo a `root` se estiver dentro dele, senao o nome."""
    if root:
        try:
            return path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            pass
    return path.name


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game", required=True, type=Path, help="arquivo .range do jogo")
    ap.add_argument("--extra", action="append", default=[], type=Path,
                    help="arquivo extra colocado ao lado do .range (ex.: modulo .py); repetivel")
    ap.add_argument("--extra-root", type=Path,
                    help="pasta base: extras dentro dela mantem o caminho relativo no FS virtual")
    ap.add_argument("--runtime-dir", type=Path, default=REPO_ROOT / "build-web" / "bin")
    ap.add_argument("--out-dir", type=Path, default=REPO_ROOT / "build-web" / "dist")
    ap.add_argument("--name", help="nome do pacote (padrao: nome do .range)")
    ap.add_argument("--title", help="titulo da pagina (padrao: nome)")
    ap.add_argument("--version", default="0.0.0")
    ap.add_argument("--width", type=int, default=960)
    ap.add_argument("--height", type=int, default=540)
    ap.add_argument("--zip", action="store_true", help="tambem gera <name>-<version>-web.zip")
    args = ap.parse_args()

    name = args.name or args.game.stem
    if not NAME_RE.match(name):
        die("--name so pode ter letras, numeros, ponto, sublinhado ou hifen")
    if not NAME_RE.match(args.version):
        die("--version so pode ter letras, numeros, ponto, sublinhado ou hifen")
    if not NAME_RE.match(args.game.name):
        die(f"nome do arquivo do jogo invalido para o FS virtual: {args.game.name}")
    for x in args.extra:
        if not x.is_file():
            die(f"arquivo extra nao encontrado: {x}")
        rel = extra_rel(x, args.extra_root)
        if not all(NAME_RE.match(part) and part not in (".", "..") for part in rel.split("/")):
            die(f"nome de arquivo extra invalido: {rel}")
    names = [args.game.name] + [extra_rel(x, args.extra_root) for x in args.extra]
    if len(set(names)) != len(names):
        die("nomes duplicados entre jogo e extras (colidiriam no FS virtual)")

    check_game(args.game)
    check_runtime(args.runtime_dir)
    warnings = runtime_warnings(args.runtime_dir)

    pkg = args.out_dir / name
    tmp = args.out_dir / f".{name}.tmp"
    if tmp.exists():
        shutil.rmtree(tmp)
    (tmp / "game").mkdir(parents=True)

    for n in RUNTIME_FILES:
        shutil.copy2(args.runtime_dir / n, tmp / n)
    shutil.copy2(args.game, tmp / "game" / args.game.name)
    for x in args.extra:
        dst = tmp / "game" / extra_rel(x, args.extra_root)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(x, dst)

    title = args.title or name
    html = (INDEX_TEMPLATE
            .replace("__TITLE__", title.replace("<", "&lt;").replace(">", "&gt;"))
            .replace("__GAME__", args.game.name)
            .replace("__EXTRAS__", json.dumps([extra_rel(x, args.extra_root) for x in args.extra]))
            .replace("__VERSION__", args.version)
            .replace("__WIDTH__", str(args.width))
            .replace("__HEIGHT__", str(args.height)))
    (tmp / "index.html").write_text(html, encoding="utf-8", newline="\n")
    (tmp / "serve.py").write_text(SERVE_PY, encoding="utf-8", newline="\n")
    (tmp / "HOSTING.md").write_text(HOSTING_MD, encoding="utf-8", newline="\n")

    files = {}
    for p in sorted(tmp.rglob("*")):
        if p.is_file():
            files[p.relative_to(tmp).as_posix()] = {"bytes": p.stat().st_size, "sha256": sha256(p)}

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "name": name,
        "title": title,
        "version": args.version,
        "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "entry_game": f"game/{args.game.name}",
        "requirements": {"webgl": 2, "threads": False, "cross_origin_isolation": False},
        "runtime": {n: files[n] for n in RUNTIME_FILES},
        "files": files,
        "warnings": warnings,
    }
    (tmp / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")

    lines = [f"{sha256(p)}  {p.relative_to(tmp).as_posix()}" for p in sorted(tmp.rglob("*")) if p.is_file()]
    (tmp / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    # Substituicao controlada: so troca o pacote anterior depois do novo estar completo.
    if pkg.exists():
        shutil.rmtree(pkg)
    tmp.rename(pkg)

    print(f"Pacote criado: {pkg}")
    total = sum(f["bytes"] for f in files.values())
    print(f"Tamanho total: {total / (1 << 20):.1f} MiB em {len(files)} arquivos")
    for w in warnings:
        print(f"AVISO: {w}")

    if args.zip:
        archive = args.out_dir / f"{name}-{args.version}-web.zip"
        if archive.exists():
            archive.unlink()
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
            for p in sorted(pkg.rglob("*")):
                if p.is_file():
                    z.write(p, f"{name}/{p.relative_to(pkg).as_posix()}")
        (args.out_dir / (archive.name + ".sha256")).write_text(
            f"{sha256(archive)}  {archive.name}\n", encoding="utf-8", newline="\n")
        print(f"ZIP: {archive}")


if __name__ == "__main__":
    main()
