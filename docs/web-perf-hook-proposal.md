# Proposta: ligar `frame-time-perf.js` ao pacote Web

Estado: **aplicada** em `package-web.py` (`--perf`; verificada em 2026-09-21: com `--perf` o pacote inclui o script e o manifesto o lista, `perf-run.cjs` recebe frames em Edge headless; sem `--perf`, sem arquivo, sem tag e `__rangePerf` indefinido). O texto abaixo é o original da proposta. O plano proíbe editar `tools/web/package-web.py` nesta frente; este diff só
descreve o gancho para quem for autorizado a aplicá-lo. Nada abaixo foi executado.

## Comportamento desejado

- Opt-in: `package-web.py --perf` copia `tools/web/frame-time-perf.js` para a raiz do pacote e o carrega no `index.html`.
- Sem `--perf`, o pacote sai idêntico ao de hoje (sem o arquivo e sem a tag).
- O script já se desativa sozinho sem `?perf=1` na URL; a flag existe só para não distribuir o arquivo por padrão.
- No celular: abrir `https://.../?perf=1`, jogar ~60 s e ler `__rangePerf()` no console remoto, ou o log `[perf]` ao sair.
  Sem console remoto, o item abaixo ("Exibição na página") evita depender dele.

## Diff proposto

```diff
--- a/tools/web/package-web.py
+++ b/tools/web/package-web.py
@@ RUNTIME_FILES = ("RangeRuntime.js", "RangeRuntime.wasm", "RangeRuntime.data")
+PERF_FILE = "frame-time-perf.js"
@@ INDEX_TEMPLATE (antes do <script> principal, linha ~119)
 <pre id="log"></pre>
+__PERF_SCRIPT__
 <script>
 (function () {
@@ main() (parser de argumentos)
+    ap.add_argument("--perf", action="store_true",
+                    help="inclui frame-time-perf.js (ativo so com ?perf=1 na URL)")
@@ main(), depois de copiar o runtime (linha ~489)
+    if args.perf:
+        shutil.copy2(Path(__file__).with_name(PERF_FILE), tmp / PERF_FILE)
@@ main(), no .replace() do html (linha ~500)
+            .replace("__PERF_SCRIPT__", '<script src="%s"></script>' % PERF_FILE if args.perf else "")
```

Se `manifest.json` lista os arquivos do pacote com hash, incluir `frame-time-perf.js` nessa lista quando `--perf`
(e em `SHA256SUMS.txt`), para o `validate-web.py` não acusar arquivo desconhecido. Conferir antes de aplicar.

## Exibição na página (opcional, pequeno)

Para medir no celular sem console: em `frame-time-perf.js`, quando `?perf=1`, criar um `<pre id="perf">` fixo no canto
que atualiza a cada 2 s com `count/p50/p95`. Assim o usuário fotografa a tela. Também registrar aparelho
(`navigator.userAgent`), `devicePixelRatio` e o tamanho do canvas no mesmo objeto, pois o procedimento do M3 exige
anotar aparelho, resolução e escala.

## Verificação necessária depois de aplicar

1. `package-web.py --perf` e sem `--perf`: conferir presença/ausência do arquivo e da tag; `validate-web.py` passa nos dois.
2. Edge headless isolado com `?perf=1`: `__rangePerf().count > 0` depois de ~10 s de jogo; sem `?perf=1`, `window.__rangePerf` indefinido.
3. Comparar o tempo de frame com e sem a sonda numa cena fixa (o custo do próprio gancho deve ser desprezível).
