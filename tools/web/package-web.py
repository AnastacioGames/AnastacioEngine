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
import unicodedata
import zipfile
from pathlib import Path

SCHEMA_VERSION = 1
REPO_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_FILES = ("RangeRuntime.js", "RangeRuntime.wasm", "RangeRuntime.data")
PERF_FILE = "frame-time-perf.js"
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
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
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
  #fs { position: fixed; left: 8px; top: 8px; z-index: 10; font-size: 14px; padding: 8px 12px;
        background: rgba(0,0,0,.5); color: #fff; border: 1px solid rgba(255,255,255,.35); }
  #fs[hidden] { display: none; }
  #touch { position: fixed; inset: 0; z-index: 20; pointer-events: none; --u: clamp(46px, 12vmin, 80px);
           --sl: env(safe-area-inset-left, 0px); --sr: env(safe-area-inset-right, 0px);
           --sb: env(safe-area-inset-bottom, 0px);
           user-select: none; -webkit-user-select: none; -webkit-touch-callout: none; }
  #touch[hidden] { display: none; }
  #touch .zone, #touch .btn, #touch .dpad { position: absolute; pointer-events: auto; touch-action: none; }
  #touch .zone { bottom: 0; width: 45%; height: 70%; }
  #touch .zone.left { left: 0; }
  #touch .zone.right { right: 0; }
  #touch .base { position: absolute; box-sizing: border-box; width: calc(var(--u) * 2); height: calc(var(--u) * 2);
                 bottom: calc(var(--sb) + var(--u) * .8); border-radius: 50%;
                 background: rgba(255,255,255,.12); border: 2px solid rgba(255,255,255,.4); }
  #touch .left .base { left: calc(var(--sl) + var(--u) * .8); }
  #touch .right .base { right: calc(var(--sr) + var(--u) * .8); }
  #touch .knob { position: absolute; left: 50%; top: 50%; width: calc(var(--u) * .9); height: calc(var(--u) * .9);
                 margin: calc(var(--u) * -.45) 0 0 calc(var(--u) * -.45); border-radius: 50%;
                 background: rgba(255,255,255,.45); }
  #touch .btn { box-sizing: border-box; width: calc(var(--u) * 1.1); height: calc(var(--u) * 1.1); border-radius: 50%;
                display: flex; align-items: center; justify-content: center; font: bold 20px system-ui, sans-serif;
                color: rgba(255,255,255,.85); background: rgba(255,255,255,.15); border: 2px solid rgba(255,255,255,.4); }
  #touch .dpad { box-sizing: border-box; width: calc(var(--u) * 2.4); height: calc(var(--u) * 2.4);
                 left: calc(var(--sl) + var(--u) * .7); bottom: calc(var(--sb) + var(--u) * .7);
                 border-radius: 50%; background: rgba(255,255,255,.06); }
  #touch .dpad i { position: absolute; width: calc(var(--u) * .8); height: calc(var(--u) * .8); border-radius: 6px;
                   background: rgba(255,255,255,.25); }
  #touch .zone.on .knob, #touch .btn.on, #touch .dpad i.on { background: rgba(232,134,42,.7); }
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
<button id="fs" hidden>Tela cheia</button>
<div id="touch" hidden></div>
<pre id="log"></pre>
__PERF_SCRIPT__
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
    if (pf) pf.failure = String(msg);
    el("progress").hidden = true;
    el("play").hidden = true;
    el("status").textContent = "Nao foi possivel iniciar o jogo.";
    var e = el("error");
    e.hidden = false;
    e.textContent = msg + "\\n\\nRecarregue a pagina para tentar novamente. Use ?debug=1 para ver o log.";
    el("overlay").hidden = false;
    stopTouch();
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
    requestMotionPermission();
    el("overlay").hidden = true;
    el("fs").hidden = !fsSupported;
    startTouch();
    el("canvas").focus();
  }

  // Tela cheia: a pagina inteira (overlay de perf/log continuam visiveis). O canvas mantem a resolucao
  // de desenho e so e escalado por CSS, preservando a proporcao (o mapeamento de toque/mouse segue certo).
  // iPhone nao tem Fullscreen API para elementos fora de <video>: o botao fica oculto la. No APK Android
  // (MainActivity acrescenta "RangeWebView/" ao user agent) a Activity ja e imersiva: botao oculto tambem.
  var root = document.documentElement;
  var inAndroidApp = /\\bRangeWebView\\//.test(navigator.userAgent);
  var fsSupported = !inAndroidApp && !!(root.requestFullscreen || root.webkitRequestFullscreen);
  // O WebView do Android nao tem pointer lock: o pedido do runtime (cursor oculto) rejeita com "UnknownError ...
  // report this bug to chromium" e a pagina mostrava erro. No APK o pedido vira no-op; toque/arrasto seguem pelo
  // cursor virtual do runtime, como sem pointer lock no navegador.
  if (inAndroidApp && window.Element && Element.prototype.requestPointerLock)
    Element.prototype.requestPointerLock = function () { return Promise.resolve(); };
  function isFullscreen() { return !!(document.fullscreenElement || document.webkitFullscreenElement); }
  // Proporcao do jogo. O runtime cria a janela com a resolucao do .range (pode diferir de __WIDTH__x__HEIGHT__), e
  // depois o SDL (janela redimensionavel) troca canvas.width/height pelo tamanho CSS a cada resize. Medir a proporcao
  // por eles a cada vez deformava a imagem ao girar (achatada ou cortada). Aqui so vale uma troca de tamanho com
  // proporcao diferente da do CSS atual, ou seja, pedida pelo jogo e nao pelo SDL acompanhando o CSS.
  var canvasAspect = el("canvas").width / el("canvas").height;
  if (window.MutationObserver) new MutationObserver(function () {
    var c = el("canvas"), a = c.width / c.height, r = c.getBoundingClientRect();
    if (!(a > 0) || Math.abs(a / canvasAspect - 1) < 0.01) return;
    if (c.style.width && r.height > 0 && Math.abs(a / (r.width / r.height) - 1) < 0.01) return;
    canvasAspect = a;
    fitCanvas();
  }).observe(el("canvas"), { attributes: true, attributeFilter: ["width", "height"] });
  function fitCanvas() {
    var c = el("canvas");
    // No APK a pagina ja ocupa a tela toda: o canvas sempre se ajusta a ela, em paisagem ou retrato.
    if (!isFullscreen() && !inAndroidApp) { c.style.width = c.style.height = ""; return; }
    var w = Math.min(window.innerWidth, window.innerHeight * canvasAspect);
    c.style.width = Math.floor(w) + "px";
    c.style.height = Math.floor(w / canvasAspect) + "px";
  }
  function toggleFullscreen() {
    if (isFullscreen()) {
      (document.exitFullscreen || document.webkitExitFullscreen).call(document);
      return;
    }
    var req = root.requestFullscreen ? root.requestFullscreen() : root.webkitRequestFullscreen();
    Promise.resolve(req).then(function () {
      var c = el("canvas");
      // Android/Chrome so permite travar a orientacao em tela cheia; falha em silencio nos demais.
      if (c.width > c.height && screen.orientation && screen.orientation.lock)
        return screen.orientation.lock("landscape");
    }).catch(function () {});
  }
  function onFullscreenChange() {
    el("fs").textContent = isFullscreen() ? "Sair da tela cheia" : "Tela cheia";
    fitCanvas();
    el("canvas").focus();
  }
  // Sensores de movimento -> bge.logic.motion (KX_PythonMotion.cpp le Module.rangeMotion).
  // Os eixos do aparelho (x direita, y topo, z para fora da tela em retrato) sao girados para os da tela
  // atual, para "inclinar a direita" continuar sendo +x em paisagem. Gravidade no sentido do W3C: aponta
  // para cima (aparelho deitado de face para cima da z ~ +9.8).
  var motion = { t: 0, gyro: [0, 0, 0], accel: [0, 0, 0], gravity: [0, 0, 0], orient: [0, 0, 0] };
  var motionLogAt = 0;
  var iosMotion = /iPhone|iPad|iPod/.test(navigator.userAgent) ||
                  (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  function screenAngle() {
    var a = screen.orientation && typeof screen.orientation.angle === "number" ? screen.orientation.angle
          : (typeof window.orientation === "number" ? window.orientation : 0);
    return a * Math.PI / 180;
  }
  function toScreen(x, y, z) {
    var a = screenAngle(), c = Math.cos(a), s = Math.sin(a);
    return [x * c - y * s, x * s + y * c, z];
  }
  function onDeviceMotion(e) {
    var g = e.accelerationIncludingGravity, r = e.rotationRate, lin = e.acceleration;
    if (!g || g.x === null) return;
    var accel = toScreen(g.x, g.y, g.z);
    var grav;
    if (lin && lin.x !== null) grav = toScreen(g.x - lin.x, g.y - lin.y, g.z - lin.z);
    else {
      // Sem aceleracao linear separada: passa-baixa sobre a leitura com gravidade.
      grav = motion.t ? motion.gravity : accel.slice();
      for (var i = 0; i < 3; i++) grav[i] += 0.1 * (accel[i] - grav[i]);
    }
    var d = Math.PI / 180;
    // rotationRate em graus/s. Chrome/WebView preenchem alpha=x, beta=y, gamma=z (conferido com sensor
    // emulado, verify-motion.cjs); Safari segue a especificacao (alpha=z, beta=x, gamma=y), nao testado.
    var ra = r && r.alpha !== null ? [(r.alpha || 0) * d, (r.beta || 0) * d, (r.gamma || 0) * d] : null;
    motion.gyro = !ra ? [0, 0, 0] : iosMotion ? toScreen(ra[1], ra[2], ra[0]) : toScreen(ra[0], ra[1], ra[2]);
    motion.accel = accel;
    motion.gravity = grav;
    motion.t = performance.now();
    if (debug && motion.t - motionLogAt > 1000) {
      motionLogAt = motion.t;
      log("[motion] accel " + accel.map(function (v) { return v.toFixed(2); }).join(" ") +
          " | gyro " + motion.gyro.map(function (v) { return v.toFixed(2); }).join(" ") +
          " | orient " + motion.orient.map(function (v) { return v.toFixed(0); }).join(" "));
    }
  }
  function onDeviceOrientation(e) {
    if (e.alpha === null && e.beta === null) return;
    motion.orient = [e.alpha || 0, e.beta || 0, e.gamma || 0];
  }
  window.addEventListener("devicemotion", onDeviceMotion);
  window.addEventListener("deviceorientation", onDeviceOrientation);
  // iOS so entrega os eventos depois de permissao pedida num gesto do usuario (o clique em Jogar).
  function requestMotionPermission() {
    [window.DeviceMotionEvent, window.DeviceOrientationEvent].forEach(function (E) {
      if (E && typeof E.requestPermission === "function")
        E.requestPermission().catch(function (e) { console.warn("[web] sensores recusados: " + e); });
    });
  }

  // Controle na tela -> gamepad 0 do runtime (DEV_JoystickEvents.cpp le Module.rangePad a cada quadro).
  // axes na ordem do SDL GameController (LX, LY, RX, RY, gatilho E, gatilho D; -1..1, gatilhos 0..1);
  // buttons e mascara de bits na ordem de SDL_GameControllerButton (A=1, B=2, X=4, Y=8, ...).
  var pad = { active: false, axes: [0, 0, 0, 0, 0, 0], buttons: 0 };

  // Overlay do controle na tela: cada controle segue um dedo (pointerId), entao mover e apertar ao mesmo tempo
  // funciona. Toques fora dos controles seguem para o canvas (arrastar para olhar continua). Aparece em tela de
  // toque (pointer: coarse) ou com ?touch=1; ?touch=0 esconde; ?touchlayout= e ?touchstick= trocam a config.
  var TOUCH = __TOUCH__;
  var DPAD_UP = 1 << 11, DPAD_DOWN = 1 << 12, DPAD_LEFT = 1 << 13, DPAD_RIGHT = 1 << 14;
  var STICK_DEADZONE = 0.1;
  var touchLayouts = {
    stick: [{ type: "stick", side: "left", axes: [0, 1] },
            { type: "button", bit: 0, label: "A", at: [-0.75, 0.55] },
            { type: "button", bit: 1, label: "B", at: [0.75, -0.55] }],
    dpad: [{ type: "dpad" },
           { type: "button", bit: 0, label: "A", at: [0, 1] }, { type: "button", bit: 1, label: "B", at: [1, 0] },
           { type: "button", bit: 2, label: "X", at: [-1, 0] }, { type: "button", bit: 3, label: "Y", at: [0, -1] }],
    twin: [{ type: "stick", side: "left", axes: [0, 1] }, { type: "stick", side: "right", axes: [2, 3] }]
  };
  var touchControls = [], touchLogAt = 0, touchLogButtons = 0;
  function touchParam(name) {
    var m = new RegExp("[?&]" + name + "=(\\\\w+)").exec(location.search);
    return m ? m[1] : null;
  }
  function node(tag, cls, text) {
    var n = document.createElement(tag);
    n.className = cls;
    if (text) n.textContent = text;
    return n;
  }
  function updatePad() {
    var axes = [0, 0, 0, 0, 0, 0], bits = 0;
    touchControls.forEach(function (c) {
      if (c.axes) { axes[c.axes[0]] = c.value[0]; axes[c.axes[1]] = c.value[1]; }
      bits |= c.bits;
    });
    pad.axes = axes;
    pad.buttons = bits;
    var now = performance.now();
    if (debug && (bits !== touchLogButtons || now - touchLogAt > 250)) {
      touchLogAt = now;
      touchLogButtons = bits;
      log("[touch] axes " + axes.map(function (v) { return v.toFixed(2); }).join(" ") + " | buttons " + bits);
    }
  }
  // Um dedo por controle, preso a ele por pointer capture: arrastar para fora nao solta nem pega outro controle.
  function bindPointer(target, ctl, down, move) {
    var id = null;
    function end(e) {
      if (e.pointerId !== id) return;
      id = null;
      ctl.reset();
      updatePad();
    }
    target.addEventListener("pointerdown", function (e) {
      e.preventDefault();
      if (id !== null) return;
      id = e.pointerId;
      try { target.setPointerCapture(id); } catch (x) {}
      down(e);
      updatePad();
    });
    target.addEventListener("pointermove", function (e) {
      if (e.pointerId !== id) return;
      move(e);
      updatePad();
    });
    target.addEventListener("pointerup", end);
    target.addEventListener("pointercancel", end);
    target.addEventListener("lostpointercapture", end);
    ctl.release = function () {
      var was = id;
      id = null;
      if (was !== null) try { target.releasePointerCapture(was); } catch (x) {}
      ctl.reset();
    };
  }
  // Stick fixo: o centro e a posicao de repouso. Dinamico: a base vai para onde o dedo tocou dentro da zona.
  function makeStick(c, dynamic) {
    var zone = node("div", "zone " + c.side), base = node("div", "base"), knob = node("div", "knob");
    base.appendChild(knob);
    zone.appendChild(base);
    var ctl = { node: zone, axes: c.axes, value: [0, 0], bits: 0 }, cx = 0, cy = 0, r = 1;
    function aim(e) {
      var dx = e.clientX - cx, dy = e.clientY - cy, len = Math.sqrt(dx * dx + dy * dy);
      if (len > r) { dx *= r / len; dy *= r / len; }
      knob.style.transform = "translate(" + dx + "px," + dy + "px)";
      var n = Math.min(1, len / r);
      var k = n <= STICK_DEADZONE ? 0 : (n - STICK_DEADZONE) / (1 - STICK_DEADZONE) / n;
      ctl.value = [dx / r * k, dy / r * k];
    }
    ctl.reset = function () {
      ctl.value = [0, 0];
      knob.style.transform = "";
      base.removeAttribute("style");
      zone.classList.remove("on");
    };
    bindPointer(zone, ctl, function (e) {
      var b = base.getBoundingClientRect();
      r = b.width / 2;
      if (dynamic) {
        var z = zone.getBoundingClientRect();
        var x = Math.max(r, Math.min(z.width - r, e.clientX - z.left));
        var y = Math.max(r, Math.min(z.height - r, e.clientY - z.top));
        base.style.left = x - r + "px";
        base.style.top = y - r + "px";
        base.style.right = base.style.bottom = "auto";
        cx = z.left + x;
        cy = z.top + y;
      } else {
        cx = b.left + r;
        cy = b.top + r;
      }
      zone.classList.add("on");
      aim(e);
    }, aim);
    return ctl;
  }
  // D-pad de 8 direcoes pelo angulo do dedo em relacao ao centro (diagonal aperta os dois botoes).
  function makeDpad() {
    var box = node("div", "dpad"), arms = {};
    [["up", DPAD_UP, 0.8, 0], ["down", DPAD_DOWN, 0.8, 1.6], ["left", DPAD_LEFT, 0, 0.8], ["right", DPAD_RIGHT, 1.6, 0.8]]
      .forEach(function (a) {
        var i = node("i", "");
        i.style.left = "calc(var(--u) * " + a[2] + ")";
        i.style.top = "calc(var(--u) * " + a[3] + ")";
        box.appendChild(i);
        arms[a[1]] = i;
      });
    var ctl = { node: box, value: null, bits: 0 };
    function aim(e) {
      var b = box.getBoundingClientRect(), r = b.width / 2;
      var dx = (e.clientX - b.left - r) / r, dy = (e.clientY - b.top - r) / r, len = Math.sqrt(dx * dx + dy * dy);
      var bits = 0;
      if (len > 0.2) {
        dx /= len;
        dy /= len;
        if (dy < -0.38) bits |= DPAD_UP;
        if (dy > 0.38) bits |= DPAD_DOWN;
        if (dx < -0.38) bits |= DPAD_LEFT;
        if (dx > 0.38) bits |= DPAD_RIGHT;
      }
      ctl.bits = bits;
      for (var k in arms) arms[k].classList.toggle("on", !!(bits & k));
    }
    ctl.reset = function () { aim({ clientX: NaN, clientY: NaN }); };
    bindPointer(box, ctl, aim, aim);
    return ctl;
  }
  // Botoes em volta de um centro no canto inferior direito; "at" em unidades de --u (x para a direita, y para baixo).
  function makeButton(c) {
    var b = node("div", "btn", c.label), ctl = { node: b, value: null, bits: 0 };
    b.style.right = "calc(var(--sr) + var(--u) * " + (1.35 - c.at[0]) + ")";
    b.style.bottom = "calc(var(--sb) + var(--u) * " + (1.35 - c.at[1]) + ")";
    ctl.reset = function () { ctl.bits = 0; b.classList.remove("on"); };
    bindPointer(b, ctl, function () { ctl.bits = 1 << c.bit; b.classList.add("on"); }, function () {});
    return ctl;
  }
  function startTouch() {
    var show = touchParam("touch");
    var layout = touchLayouts[touchParam("touchlayout") || TOUCH.layout];
    var coarse = !!(window.matchMedia && window.matchMedia("(pointer: coarse)").matches);
    if (!layout || show === "0" || (show !== "1" && !coarse) || touchControls.length) return;
    var dynamic = (touchParam("touchstick") || TOUCH.stick) !== "fixed";
    layout.forEach(function (c) {
      var ctl = c.type === "stick" ? makeStick(c, dynamic) : c.type === "dpad" ? makeDpad() : makeButton(c);
      touchControls.push(ctl);
      el("touch").appendChild(ctl.node);
    });
    el("touch").hidden = false;
    pad.active = true;
    log("[touch] controle na tela: " + (touchParam("touchlayout") || TOUCH.layout) + (dynamic ? " (stick dinamico)" : ""));
  }
  // Soltar tudo quando a pagina perde o foco ou some: sem isso um dedo "preso" seguia andando ao voltar.
  function releaseTouch() {
    if (!touchControls.length) return;
    touchControls.forEach(function (c) { c.release(); });
    updatePad();
  }
  function stopTouch() {
    releaseTouch();
    pad.active = false;
    el("touch").hidden = true;
  }
  window.addEventListener("blur", releaseTouch);
  window.addEventListener("pagehide", releaseTouch);
  window.addEventListener("orientationchange", releaseTouch);
  document.addEventListener("visibilitychange", function () { if (document.hidden) releaseTouch(); });

  el("fs").addEventListener("click", toggleFullscreen);
  document.addEventListener("fullscreenchange", onFullscreenChange);
  document.addEventListener("webkitfullscreenchange", onFullscreenChange);
  window.addEventListener("resize", fitCanvas);
  if (inAndroidApp) fitCanvas();

  // Alguns avisos da emulacao GL saem direto por console.error (antes do printErr).
  var _consoleError = console.error.bind(console);
  console.error = function () {
    var t = arguments.length ? String(arguments[0]) : "";
    if (/using emscripten GL (immediate mode )?emulation/.test(t)) console.warn.apply(console, arguments);
    else _consoleError.apply(null, arguments);
  };

  window.Module = {
    canvas: el("canvas"),
    arguments: [GAME],
    rangeMotion: motion,
    rangePad: pad,
    print: function (t) { log("[out] " + t); console.log(t); },
    printErr: function (t) {
      log("[err] " + t);
      // Avisos conhecidos e inofensivos da emulacao GL legada do emscripten.
      if (/using emscripten GL (immediate mode )?emulation/.test(t)) console.warn(t); else console.error(t);
    },
    onAbort: function (w) {
      if (pf) pf.runtimeAborted = String(w);
      fail("O runtime foi interrompido: " + w);
    },
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
      if (pf) pf.runtimeInitialized = true;
      log("[event] runtime inicializado");
      markReady();
    }
  };

  window.addEventListener("error", function (ev) { fail("Erro: " + ev.message); });
  window.addEventListener("unhandledrejection", function (ev) {
    var msg = ev.reason && ev.reason.message ? ev.reason.message : String(ev.reason);
    // Pedido de pointer lock recusado (Esc recente, iframe, navegador sem suporte): o jogo segue sem trava.
    if (/pointer ?lock|exited the lock/i.test(msg)) { ev.preventDefault(); console.warn("[web] pointer lock recusado: " + msg); return; }
    fail("Erro: " + msg);
  });

  // O jogo so comeca a ser mostrado apos um clique: libera foco de teclado e permite audio (politica de autoplay).
  var script = document.createElement("script");
  script.src = "RangeRuntime.js?v=" + encodeURIComponent(VERSION);
  script.onerror = function () { fail("RangeRuntime.js nao foi encontrado no servidor."); };
  // Liberar o botao so quando o runtime terminou de inicializar (onRuntimeInitialized): com rede lenta o
  // script carrega antes do .data/.wasm e o botao ficava ativo cedo demais (achado no GitHub Pages).
  function markReady() {
    if (failed || ready) return;
    ready = true;
    el("progress").hidden = true;
    el("status").textContent = "Pronto.";
    el("play").disabled = false;
  }
  el("play").addEventListener("click", tryStart);

  // Pre-voo: eventos estruturados do runtime tem precedencia; o parser de console
  // permanece apenas para binarios antigos e caminhos que ainda nao emitem eventos.
  var preflight = /[?&]preflight=1/.test(location.search);
  var pf = { shaders: [], python: [], diagnostics: [], contextLost: false, runtimeInitialized: false,
             runtimeAborted: "", failure: "" };
  var pfOpenShader = null, pfPyOpen = false, pfSeen = {}, pfStructuredShader = false;
  var pfStructuredPyKinds = {};
  function pfAddPy(rec) {
    // O mesmo erro se repete a cada frame do controller; um registro por causa basta.
    // Heuristica de console nao duplica um erro que ja chegou como evento estruturado.
    if (!rec.structured && pfStructuredPyKinds[rec.kind]) return;
    var key = rec.kind + "|" + (rec.module || "") + "|" + (rec.file || "") + "|" + (rec.origin || "") + "|" + rec.text;
    if (!pfSeen[key]) { pfSeen[key] = true; pf.python.push(rec); }
  }
  function pfAddShader(rec) {
    var key = rec.operation + "|" + rec.stage + "|" + (rec.material || "") + "|" + rec.log;
    if (!pfSeen[key]) { pfSeen[key] = true; pf.shaders.push(rec); }
  }
  function pfDiagnostic(rec) {
    if (!rec || rec.version !== 1 || typeof rec.category !== "string") return;
    pf.diagnostics.push(rec);
    if (rec.category === "shader" && rec.severity === "error") {
      pfStructuredShader = true;
      pfAddShader({ material: rec.origin || "", stage: rec.stage || "", operation: rec.operation || "",
                    log: rec.log || "", structured: true });
    }
    else if (rec.category === "python" && rec.severity === "error") {
      var kind = rec.exception_type || "Exception";
      pfStructuredPyKinds[kind] = true;
      var mod = "";
      var mm = /(?:ModuleNotFoundError|ImportError).*?['"]([\\w.]+)['"]/.exec(rec.message || "");
      if (mm) mod = mm[1];
      pfAddPy({ kind: kind, module: mod, file: "", text: rec.message || "", origin: rec.origin || "",
                context: rec.context || "", traceback: rec.traceback || "", structured: true });
    }
  }
  function pfLine(t) {
    t = t.replace(/\\x1b\\[[0-9;]*m/g, "");
    // O log do compilador GLSL chega em linhas soltas depois do cabecalho; outra linha fecha.
    if (pfOpenShader) {
      if (/^\\s*(ERROR|WARNING):/.test(t)) { pfOpenShader.log += "\\n" + t; return; }
      pfOpenShader = null;
    }
    var m = /(ModuleNotFoundError|ImportError)\\b.*?['"]([\\w.]+)['"]/.exec(t);
    if (m) { pfAddPy({ kind: m[1], module: m[2], file: "", text: t }); return; }
    m = /FileNotFoundError.*?['"]([^'"]+)['"]/.exec(t);
    if (m) { pfAddPy({ kind: "FileNotFoundError", file: m[1], text: t }); return; }
    if (/Traceback \\(most recent/.test(t) || /Python\\W*.*script error/i.test(t)) { pfPyOpen = true; return; }
    if (pfPyOpen) {
      m = /^([\\w.]*(Error|Exception))\\b/.exec(t);
      if (m) { pfPyOpen = false; pfAddPy({ kind: m[1], text: t, file: "" }); return; }
    }
    if (!pfStructuredShader && /shader/i.test(t) && /(fail|error|compil|link)/i.test(t)) {
      var rec = { material: "", stage: /vertex/i.test(t) ? "vertex" : /fragment/i.test(t) ? "fragment" : "?", log: t,
                  structured: false };
      pfAddShader(rec);
      pfOpenShader = rec;
    }
  }
  function pfProbeGL() {
    try {
      var c = document.createElement("canvas");
      var gl = c.getContext("webgl2");
      if (gl) return { version: 2, missing_extensions: [] };
      return { version: c.getContext("webgl") ? 1 : 0, missing_extensions: [],
               error: "WebGL 2 indisponivel" };
    } catch (e) { return { version: 0, missing_extensions: [], error: String(e) }; }
  }
  function hex(buf) {
    return Array.prototype.map.call(new Uint8Array(buf), function (b) { return ("0" + b.toString(16)).slice(-2); }).join("");
  }
  function pfFiles() {
    return fetch("manifest.json?v=" + encodeURIComponent(VERSION), { cache: "no-store" })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      }).then(function (man) {
        if (!man || typeof man.files !== "object") throw new Error("manifesto sem lista de arquivos");
        return man;
      }).catch(function (e) {
        return { files: {}, preflight_manifest_error: String(e) };
      })
      .then(function (man) {
        if (man.preflight_manifest_error) {
          return [{ name: "manifest.json", status: null, mime: "", error: man.preflight_manifest_error }];
        }
        var names = Object.keys(man.files || {}).filter(function (n) {
          return n !== "manifest.json" && n !== "SHA256SUMS.txt";
        });
        return Promise.all(names.map(function (n) {
          var rec = { name: n, status: null, mime: "", error: "", expected_sha256: man.files[n].sha256 };
          return fetch(n + "?v=" + encodeURIComponent(VERSION), { cache: "no-store" }).then(function (r) {
            rec.status = r.status;
            rec.mime = (r.headers.get("content-type") || "").split(";")[0];
            return r.arrayBuffer();
          }).then(function (buf) {
            if (window.crypto && crypto.subtle) return crypto.subtle.digest("SHA-256", buf).then(function (d) { rec.sha256 = hex(d); });
          }).catch(function (e) { rec.error = String(e); }).then(function () { return rec; });
        }));
      });
  }
  function pfBuild(files) {
    return { schema: "range-web-preflight", schema_version: 2,
             cross_origin_isolated: !!window.crossOriginIsolated,
             webgl: pfProbeGL(), files: files, context_lost: pf.contextLost,
             runtime_initialized: pf.runtimeInitialized, runtime_aborted: pf.runtimeAborted,
             runtime_failure: pf.failure,
             diagnostics: pf.diagnostics, shader_errors: pf.shaders, python_errors: pf.python };
  }
  if (preflight) {
    document.body.classList.add("debug");
    var _print = Module.print, _printErr = Module.printErr;
    Module.print = function (t) { pfLine(String(t)); _print(t); };
    Module.printErr = function (t) { pfLine(String(t)); _printErr(t); };
    Module.onDiagnostic = pfDiagnostic;
    el("canvas").addEventListener("webglcontextlost", function () { pf.contextLost = true; }, false);
    var pfFilesCache = null;
    window.rangePreflight = function () {
      var p = pfFilesCache ? Promise.resolve(pfFilesCache) : pfFiles().then(function (f) { return (pfFilesCache = f); });
      return p.then(pfBuild);
    };
    var box = document.createElement("pre");
    box.id = "preflight";
    box.style.cssText = "position:fixed;top:0;right:0;max-width:45%;max-height:60%;overflow:auto;margin:0;" +
                        "background:rgba(0,0,0,.85);color:#8cf;font:11px monospace;padding:6px;z-index:9";
    document.body.appendChild(box);
    var pfRefresh = function () {
      window.rangePreflight().then(function (r) { box.textContent = JSON.stringify(r, null, 2); });
    };
    setInterval(pfRefresh, 2000);
    pfRefresh();
    // &post=1: o editor (range_web/preflight_run.py) espera o relatorio em POST /__preflight.
    if (/[?&]post=1/.test(location.search)) {
      var pfDelay = Number((/[?&]delay=(\\d+)/.exec(location.search) || [0, 12])[1]) * 1000;
      setTimeout(function () {
        window.rangePreflight().then(function (r) {
          return fetch("__preflight", { method: "POST", body: JSON.stringify(r) });
        });
      }, pfDelay);
    }
  }

  document.body.appendChild(script);
})();
</script>
</body>
</html>
"""


SERVE_PY = '''#!/usr/bin/env python3
"""Servidor local para testar o pacote Web: python serve.py [porta] (0 = porta livre)"""
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


port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080  # 0 escolhe uma porta livre
handler = functools.partial(Handler, directory=ROOT)
server = http.server.ThreadingHTTPServer(("", port), handler)
print(f"Servindo em http://localhost:{server.server_address[1]}/  (Ctrl+C para parar)", flush=True)
server.serve_forever()
'''

HOSTING_MD = """# Hospedagem do pacote Web

Este pacote e estatico: basta servir a pasta por HTTP(S). Nao abra `index.html` por `file://`.

- Teste local: `python serve.py 8080` e abra http://localhost:8080/
- MIME: `.wasm` como `application/wasm` (senao o navegador recusa a compilacao em streaming).
- Compressao: habilite gzip/brotli para `.wasm`, `.js` e `.data` no servidor; reduz muito o download.
  Medido: `.wasm` 20,3 MiB -> 8,0 MiB, `.data` 24,8 MiB -> 8,4 MiB, `.js` 0,9 MiB -> 0,2 MiB (gzip nivel 6);
  o download total cai de ~46 MiB para ~17 MiB.
- Receitas: Netlify/Cloudflare Pages ja comprimem e servem `application/wasm` sozinhos. GitHub Pages tambem
  (gzip). itch.io: envie o zip (`--zip`) como projeto HTML, com `index.html` na raiz. nginx: `gzip on;
  gzip_types application/wasm application/javascript application/octet-stream;` e `types { application/wasm wasm; }`.
  Apache: `AddType application/wasm .wasm` e `AddOutputFilterByType DEFLATE application/wasm application/javascript application/octet-stream`.
- Conferir apos publicar: `curl -sI -H "Accept-Encoding: gzip" <url>/RangeRuntime.wasm` deve mostrar
  `content-type: application/wasm` e `content-encoding: gzip` (ou `br`).
- Cache: os arquivos sao referenciados com `?v=<versao>`; ao publicar uma versao nova, mude a versao
  (`--version`) para nao misturar arquivos antigos e novos.
- COOP/COEP: **nao sao necessarios**. Este runtime nao usa pthreads/SharedArrayBuffer.
- Requisito do navegador: WebGL 2 (Chrome/Edge/Firefox recentes em computador). Mobile nao validado.
- Save: usa IndexedDB do navegador, isolado por origem (dominio). Limpar dados do site apaga os saves.
- Diagnostico: adicione `?debug=1` na URL para ver o log do runtime na pagina.
- `manifest.json` lista hashes e avisos do pacote; `SHA256SUMS.txt` permite conferir a integridade.
"""


def safe_name(name):
    """Nome aceito pelo FS virtual: tira acentos e troca espaco/caractere invalido por '_'."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    stem, dot, ext = re.sub(r"[^A-Za-z0-9._-]", "_", ascii_name).rpartition(".")
    if not dot:
        stem, ext = ext, ""
    if not stem.strip("._"):
        stem = "game"  # nome so com caracteres nao ASCII
    return stem + dot + ext


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
    ap.add_argument("--perf", action="store_true",
                    help="inclui frame-time-perf.js (ativo so com ?perf=1 na URL)")
    ap.add_argument("--zip", action="store_true", help="tambem gera <name>-<version>-web.zip")
    ap.add_argument("--touch-layout", choices=["none", "stick", "dpad", "twin"], default="stick",
                    help="controle na tela em aparelhos de toque (padrao: stick + botoes A/B)")
    ap.add_argument("--touch-stick", choices=["dynamic", "fixed"], default="dynamic",
                    help="stick dinamico (nasce onde o dedo toca) ou fixo")
    args = ap.parse_args()

    game_name = safe_name(args.game.name)
    if game_name != args.game.name:
        print(f"Nome do jogo ajustado para o FS virtual: {game_name}")
    name = args.name or safe_name(args.game.stem)
    if not NAME_RE.match(name):
        die("--name so pode ter letras, numeros, ponto, sublinhado ou hifen")
    if not NAME_RE.match(args.version):
        die("--version so pode ter letras, numeros, ponto, sublinhado ou hifen")
    if not NAME_RE.match(game_name) or game_name.startswith("."):
        die(f"nome do arquivo do jogo invalido para o FS virtual: {args.game.name}")
    for x in args.extra:
        if not x.is_file():
            die(f"arquivo extra nao encontrado: {x}")
        rel = extra_rel(x, args.extra_root)
        if not all(NAME_RE.match(part) and part not in (".", "..") for part in rel.split("/")):
            die(f"nome de arquivo extra invalido: {rel}")
    names = [game_name] + [extra_rel(x, args.extra_root) for x in args.extra]
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
    if args.perf:
        shutil.copy2(Path(__file__).with_name(PERF_FILE), tmp / PERF_FILE)
    shutil.copy2(args.game, tmp / "game" / game_name)
    for x in args.extra:
        dst = tmp / "game" / extra_rel(x, args.extra_root)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(x, dst)

    title = args.title or name
    html = (INDEX_TEMPLATE
            .replace("__TITLE__", title.replace("<", "&lt;").replace(">", "&gt;"))
            .replace("__GAME__", game_name)
            .replace("__EXTRAS__", json.dumps([extra_rel(x, args.extra_root) for x in args.extra]))
            .replace("__PERF_SCRIPT__", '<script src="%s"></script>' % PERF_FILE if args.perf else "")
            .replace("__VERSION__", args.version)
            .replace("__TOUCH__", json.dumps({"layout": args.touch_layout, "stick": args.touch_stick}))
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
        "entry_game": f"game/{game_name}",
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
