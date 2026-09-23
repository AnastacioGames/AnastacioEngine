# Hospedagem do pacote Web

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
