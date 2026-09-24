"""Mede frame time e memoria do jogo Web no aparelho Android (APK debug ou Chrome) por adb + CDP.

Uso:
  python tools/android/measure-device.py apk --package com.anastaciogames.firstperson --rounds 3
  python tools/android/measure-device.py chrome --dir build-web/dist/First_Person --rounds 3
Opcoes: --seconds N (janela medida), --warmup N, --walk (segura W e alterna A/D durante a medida).

O APK precisa ser debug (depuracao remota do WebView). A amostragem e injetada por CDP, entao nao depende de
--perf no pacote. Resultado: uma linha JSON por rodada e um resumo; use --out para gravar tudo em arquivo.
"""
import argparse, base64, json, os, re, socket, statistics, struct, subprocess, sys, time, urllib.request

ADB = os.path.join(os.environ.get("ANDROID_HOME") or os.path.join(os.environ.get("LOCALAPPDATA", ""), "Android", "Sdk"),
                   "platform-tools", "adb.exe")
HTTP_PORT = 8841
cdp_port = None
CHROME = "com.android.chrome"


def adb(*args, check=True):
    r = subprocess.run([ADB, *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and r.returncode:
        raise RuntimeError("adb %s: %s" % (" ".join(args), r.stderr.strip()))
    return r.stdout


class Cdp:
    """Cliente WebSocket minimo (so frames de texto), suficiente para Runtime/Input do CDP."""

    def __init__(self, ws_url):
        m = re.match(r"ws://([^/:]+):(\d+)(/.*)", ws_url)
        self.sock = socket.create_connection((m.group(1), int(m.group(2))), timeout=30)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall(("GET %s HTTP/1.1\r\nHost: %s:%s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                           "Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n"
                           % (m.group(3), m.group(1), m.group(2), key)).encode())
        head = b""
        while b"\r\n\r\n" not in head:
            head += self.sock.recv(1)
        if b" 101 " not in head.split(b"\r\n")[0]:
            raise RuntimeError("handshake CDP falhou: %r" % head[:80])
        self.next_id = 0

    def _recv_exact(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise RuntimeError("conexao CDP fechada")
            buf += chunk
        return buf

    def _recv(self):
        data = b""
        while True:
            b0, b1 = self._recv_exact(2)
            n = b1 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._recv_exact(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._recv_exact(8))[0]
            data += self._recv_exact(n)
            if b0 & 0x80:
                return data.decode()

    def call(self, method, **params):
        self.next_id += 1
        payload = json.dumps({"id": self.next_id, "method": method, "params": params}).encode()
        mask = os.urandom(4)
        n = len(payload)
        head = bytes([0x81]) + (bytes([0x80 | n]) if n < 126 else bytes([0x80 | 126]) + struct.pack(">H", n)
                                if n < 65536 else bytes([0x80 | 127]) + struct.pack(">Q", n))
        self.sock.sendall(head + mask + bytes(c ^ mask[i % 4] for i, c in enumerate(payload)))
        while True:
            msg = json.loads(self._recv())
            if msg.get("id") == self.next_id:
                if "error" in msg:
                    raise RuntimeError("%s: %s" % (method, msg["error"]))
                return msg.get("result", {})

    def eval(self, expr):
        r = self.call("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True)
        return r.get("result", {}).get("value")


SAMPLER = """(() => {
  if (window.__measure) return true;
  const m = window.__measure = { frames: [], on: false, last: undefined };
  const tick = now => { if (m.on && m.last !== undefined) m.frames.push(now - m.last); m.last = now; requestAnimationFrame(tick); };
  requestAnimationFrame(tick);
  return true;
})()"""

REPORT = """(() => {
  const f = window.__measure.frames.slice(), a = f.slice().sort((x, y) => x - y);
  const q = p => a.length ? a[Math.min(a.length - 1, Math.floor((a.length - 1) * p))] : 0;
  const total = f.reduce((s, x) => s + x, 0), c = document.querySelector('canvas');
  const mem = performance.memory || {};
  return { frames: f.length, fps: total ? 1000 * f.length / total : 0, p50_ms: q(.5), p95_ms: q(.95), p99_ms: q(.99),
    max_ms: a[a.length - 1] || 0, over20: f.filter(x => x > 20).length / (f.length || 1),
    over34: f.filter(x => x > 34).length / (f.length || 1),
    jsHeapMB: mem.usedJSHeapSize ? mem.usedJSHeapSize / 1048576 : null,
    canvas: c ? c.width + 'x' + c.height : null, dpr: devicePixelRatio, ua: navigator.userAgent };
})()"""


def pids(package):
    out = adb("shell", "ps", "-A", "-o", "PID,NAME")
    return [(int(l.split()[0]), l.split()[1]) for l in out.splitlines()[1:]
            if len(l.split()) == 2 and l.split()[1].startswith(package)]


def pss_mb(package):
    total = 0
    for pid, _name in pids(package):
        m = re.search(r"TOTAL PSS:\s+(\d+)", adb("shell", "dumpsys", "meminfo", str(pid), check=False)) or \
            re.search(r"TOTAL\s+(\d+)", adb("shell", "dumpsys", "meminfo", str(pid), check=False))
        total += int(m.group(1)) if m else 0
    return round(total / 1024, 1)


def battery():
    out = adb("shell", "dumpsys", "battery")
    t = re.search(r"temperature: (\d+)", out)
    lv = re.search(r"level: (\d+)", out)
    return {"battery_temp_c": int(t.group(1)) / 10 if t else None, "battery_level": int(lv.group(1)) if lv else None}


def find_page(socket_name, timeout=40):
    global cdp_port
    cdp_port = int(adb("forward", "tcp:0", "localabstract:" + socket_name).strip())  # porta livre escolhida pelo adb
    end = time.time() + timeout
    while time.time() < end:
        try:
            pages = json.load(urllib.request.urlopen("http://127.0.0.1:%d/json" % cdp_port, timeout=5))
            pages = [p for p in pages if p.get("type") == "page" and ("appassets" in p["url"] or ":%d" % HTTP_PORT in p["url"])]
            if pages:
                return Cdp(pages[0]["webSocketDebuggerUrl"])
        except OSError:
            pass
        time.sleep(1)
    raise RuntimeError("pagina do jogo nao apareceu no CDP (%s)" % socket_name)


def launch(args):
    if args.target == "apk":
        adb("shell", "am", "force-stop", args.package)
        adb("shell", "am", "start", "-n", args.package + "/com.anastaciogames.rangewebview.MainActivity",
            "--es", "query", "measure=1")
        end = time.time() + 20
        while time.time() < end:
            main = [p for p, n in pids(args.package) if n == args.package]
            if main:
                return find_page("webview_devtools_remote_%d" % main[0])
            time.sleep(0.5)
        raise RuntimeError("processo %s nao iniciou" % args.package)
    adb("shell", "am", "force-stop", CHROME)
    adb("shell", "am", "start", "-a", "android.intent.action.VIEW", "-p", CHROME,
        "-d", "http://127.0.0.1:%d/?measure=1" % HTTP_PORT)
    return find_page("chrome_devtools_remote")


def key(cdp, kind, k):
    code = {"w": 87, "a": 65, "d": 68}[k]
    cdp.call("Input.dispatchKeyEvent", type=kind, key=k, code="Key" + k.upper(), windowsVirtualKeyCode=code,
             nativeVirtualKeyCode=code)


def round_(args, n):
    cdp = launch(args)
    end = time.time() + 60
    while not cdp.eval("!!document.getElementById('play') && !document.getElementById('play').disabled"):
        if time.time() > end:
            raise RuntimeError("botao Jogar nao ficou pronto")
        time.sleep(0.5)
    load_s = cdp.eval("performance.now() / 1000")
    cdp.eval("document.getElementById('play').click()")
    cdp.eval(SAMPLER)
    time.sleep(args.warmup)
    before = battery()
    cdp.eval("window.__measure.frames = []; window.__measure.on = true")
    if args.walk:
        key(cdp, "keyDown", "w")
        side, t0 = "a", time.time()
        while time.time() - t0 < args.seconds:
            key(cdp, "keyDown", side)
            time.sleep(1.5)
            key(cdp, "keyUp", side)
            side = "d" if side == "a" else "a"
        key(cdp, "keyUp", "w")
    else:
        time.sleep(args.seconds)
    r = cdp.eval(REPORT)
    cdp.eval("window.__measure.on = false")
    # O renderer do WebView roda num processo sandboxed do pacote do WebView, nao do app.
    pss = pss_mb(args.package) + pss_mb("com.google.android.webview:sandboxed") if args.target == "apk" else pss_mb(CHROME)
    r.update(round=n, target=args.target, walk=args.walk, seconds=args.seconds, load_to_ready_s=round(load_s, 2),
             pss_mb=round(pss, 1), **{k + "_after": v for k, v in battery().items()}, **before)
    return r


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", choices=("apk", "chrome"))
    ap.add_argument("--package", default="com.anastaciogames.firstperson")
    ap.add_argument("--dir", help="pacote Web servido ao Chrome por adb reverse (alvo chrome)")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--seconds", type=float, default=20)
    ap.add_argument("--warmup", type=float, default=5)
    ap.add_argument("--walk", action="store_true")
    ap.add_argument("--out")
    args = ap.parse_args()

    server = None
    if args.target == "chrome":
        if not args.dir:
            ap.error("--dir obrigatorio para chrome")
        server = subprocess.Popen([sys.executable, "serve.py", str(HTTP_PORT)], cwd=args.dir,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        adb("reverse", "tcp:%d" % HTTP_PORT, "tcp:%d" % HTTP_PORT)
    results = []
    try:
        for n in range(1, args.rounds + 1):
            try:
                r = round_(args, n)
            except Exception as e:  # uma rodada falha sem perder as outras
                r = {"round": n, "target": args.target, "error": str(e)}
            print(json.dumps(r), flush=True)
            results.append(r)
    finally:
        if cdp_port:
            adb("forward", "--remove", "tcp:%d" % cdp_port, check=False)
        if server:
            adb("reverse", "--remove", "tcp:%d" % HTTP_PORT, check=False)
            server.kill()
    ok = [r for r in results if "error" not in r]
    if ok:
        med = lambda k: round(statistics.median(r[k] for r in ok), 2)
        print("resumo %s (%d/%d rodadas): fps %s | p50 %s ms | p95 %s ms | p99 %s ms | >20ms %s | PSS %s MB"
              % (args.target, len(ok), len(results), med("fps"), med("p50_ms"), med("p95_ms"), med("p99_ms"),
                 med("over20"), med("pss_mb")))
    if args.out:
        with open(args.out, "a", encoding="utf-8") as f:
            for r in results:
                f.write(json.dumps(r) + "\n")
    return 0 if len(ok) == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
