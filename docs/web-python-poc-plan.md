# Python no navegador (CPython wasm32)

> PoC concluída: o runtime Web roda com Python no navegador. O histórico das etapas 0–7
> (2026-09-12 a 2026-10-13) está em [changelog-arquivo.md](changelog-arquivo.md) e no git.
> Pendências abertas ficam na seção Web do [roadmap](roadmap.md).

O BGE usa a API Python sem guardas `#ifdef WITH_PYTHON`. Por isso a rota foi cross-compilar
CPython 3.11 para `wasm32-emscripten` e manter `WITH_PYTHON=ON` no runtime Web.
O que o runtime Python suporta está em [web-python-manifest.md](web-python-manifest.md).

## Decisões vigentes

- Sem pthreads/`SharedArrayBuffer`. Threads reais seriam um build separado, com COOP/COEP na hospedagem.
- A stdlib entra no FS virtual por `--preload-file`. IDBFS serve só para saves.
- `NODERAWFS` só vale para as ferramentas de build (`makesdna`, `makesrna`, `datatoc`) sob Node.
  Não levar ao runtime servido no navegador.
- As ferramentas geradoras rodam nativas no host; o resto do alvo é wasm.
- `bgl` no Web: `glLogicOp` e `gluPickMatrix` são stubs no-op; `glMaterialf` encaminha para `glMaterialfv`.
- wasm32 exige alinhamento estrito: structs com `double`/`uint64_t` usam alocação alinhada a 8
  (SDNA, `Main`, `ImBuf` via `MEM_mallocN_aligned`).

## Versões fixadas

- CPython: branch `3.11`, commit `9eaf48a56547872b86de5cecbaa7edd3279159ed` (2026-08-20).
- emsdk: `6.0.9`.

## Build do Python wasm32 em host Linux

Usado pelo preset `web-runtime-release-linux`. Nada disso é versionado: `~/web-python-poc/` fica fora do repo.

1. Clonar o CPython em `~/web-python-poc/cpython` na revisão acima.
2. Rodar `python3 Tools/wasm/wasm_build.py --verbose emscripten-browser build` com um `EM_CONFIG`
   próprio (`~/web-python-poc/emscripten-config`), com os caminhos do emsdk escritos por extenso.
   O `wasm_build.py` faz `exec()` do arquivo e não resolve o `$CFGDIR` do `~/emsdk/.emscripten`.
   Não altere o `.emscripten` principal.
3. Teste rápido: `node python.js -c "print(42*2)"` deve imprimir `84`.
4. Montar `~/web-python-poc/python-wasm-web` no layout que `FindPythonLibsUnix.cmake` exige:
   - `include/python3.11/`: `Include/*.h` do fonte + `pyconfig.h` do build wasm32.
   - `lib/libpython3.11.a`, `lib/libexpat.a`, `lib/libmpdec.a`. As duas últimas (usadas por
     `audaspace-py`) ficam em `Modules/expat/` e `Modules/_decimal/libmpdec/` do builddir.
   - `lib/python3.11/`: cópia do `Lib/` do fonte (o `usr/local/lib/python3.11` do build é incompleto).
   - `lib/python311.zip`: de `builddir/emscripten-browser/usr/local/lib/`. Sem ele o link falha só
     no `file_packager`, depois de ~1887 alvos.
5. `export PYTHON_WASM_ROOT_DIR=~/web-python-poc/python-wasm-web`, depois
   `cmake --preset web-runtime-release-linux` e `cmake --build build-web-release --target RangeRuntime`.

No Windows o preset `web-runtime` usa `PYTHON_ROOT_DIR=D:/python-wasm-web`, no mesmo layout.

## Estado do build Linux

Configure, build e carga no Chrome headless passam (`tools/web/verify-package.cjs`: cena convertida,
texturas e materiais sem `alignment fault`). Falta o teste ponta a ponta jogável/visual antes de
refazer o pacote Linux com `web/` (ver roadmap).

## Referências

- [web-integration-audit.md](web-integration-audit.md): auditoria da integração (Codex).
- [Emscripten: packaging files](https://emscripten.org/docs/porting/files/packaging_files.html)
- [Emscripten: Filesystem API](https://emscripten.org/docs/api_reference/Filesystem-API.html)
- [Emscripten: runtime environment](https://emscripten.org/docs/porting/emscripten-runtime-environment.html)
