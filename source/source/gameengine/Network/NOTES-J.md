# Frente J: CI, Web e Docker

Criado em 2026-10-04. Branch `net/ci`. Arquivos: `.github/workflows/network.yml`, bloco Emscripten no
`CMakeLists.txt` do `Network/`, `tools/net_web_echo.cpp`, `tools/web_echo_test.sh`.

## O que o workflow faz

Disparado por push/PR que mexe em `source/source/gameengine/Network/**`, `source/extern/enet/**`,
`tools/net_menu/**` ou no próprio workflow (e manualmente, `workflow_dispatch`).

| Job | O quê |
|---|---|
| Linux (gcc, clang) | build isolado Release + `ctest`; lista warnings fora de `source/extern` (aviso, não falha) |
| Windows (MSVC) | build isolado Release + `ctest -C Release` |
| wasm32 | `emcmake` (emsdk 6.0.11 por `mymindstorm/setup-emsdk@v14`), `ctest` no node com os testes do núcleo, depois o cliente wasm contra o `net_echo` nativo |
| Menu | `pytest tools/net_menu/tests` (Python 3.11) |
| Server image | `docker build` do `tools/net_server/Dockerfile` + container de pé com a porta WebSocket |

## Mudanças de build (sem mudar comportamento)

- `ge_network` no Emscripten exporta `-lwebsocket.js` (o `NET_TransportWebClient` precisa).
- `net_tests` no Emscripten: `-sNODERAWFS=1` (lê os golden do disco), `-sALLOW_MEMORY_GROWTH=1`,
  `-sEXIT_RUNTIME=1`, e o `ctest` roda só o núcleo: `NetTypes`, `NetBitStream`, `NetGolden`, `NetMessages`,
  `NetSnapshot*`, `NetSession` (loopback), `NetTransportLoopback`, `NetTransportSimulated` e o vetor RFC do
  WebSocket. Ficam fora: `NetSession.OverENet`, `NetTransportENet`, `NetWebSocket` (servidor TCP) e
  `NetMultiTransport`. Suítes novas (frentes E–I) também ficam fora até alguém incluí-las no filtro.
- `net_web_echo` (só Emscripten): conecta por WebSocket, manda `Hello` e 3 `Chat`, confere os ecos. Usa
  `emscripten_set_main_loop` para devolver o controle ao loop do JavaScript.
- **Mesma saída em x64 e wasm32:** os testes golden comparam byte a byte com os arquivos de
  `tests/golden/`; passando nas duas plataformas, a saída é a mesma (etapa 0 do contrato).

## O que rodou nesta sessão (Linux x64, container)

- Build isolado GCC e Clang, `ctest` e ASan/UBSan: 69 testes passam, sem warnings.
- Emscripten 6.0.11 (emsdk instalado no container): `ge_network`, `net_tests`, `net_echo` e `net_web_echo`
  compilam sem warnings; `ctest` no node: 59 testes passam, golden incluídos.
- `tools/web_echo_test.sh`: cliente wasm em node 24 (o do emsdk) contra o `net_echo` nativo: conecta,
  3/3 ecos. Não precisou do pacote `ws`: node 22+ tem `WebSocket` global, que o `libwebsocket.js` usa.
- Docker 29 (daemon iniciado no container): a imagem builda; o container com `--network host` responde ao
  cliente wasm (3/3 ecos).
- `pytest tools/net_menu/tests`: 72 passam.
- `actionlint 1.7.7`: workflow sem erros.

## O que não deu para rodar aqui

- **Windows/MSVC:** sem Windows no container; fica para o primeiro run do workflow.
- **Navegador:** só node. Teste manual no navegador:
  1. `emcmake cmake -S source/source/gameengine/Network -B build-wasm -DNET_STANDALONE=ON && cmake --build build-wasm --target net_web_echo`
  2. `net_echo server 7777 7778` numa máquina com o build nativo.
  3. Servir `build-wasm/` (`python3 -m http.server -d build-wasm 8000`) e abrir
     `http://localhost:8000/net_web_echo.html` (gerar com `-o net_web_echo.html` ou carregar o `.js` numa
     página mínima). O console mostra `net_web_echo: 3/3 echoes, OK`.

## Dúvidas

1. Warnings viram falha (`-Werror`) só no núcleo? Deixei como aviso no log para não quebrar por warning de
   compilador novo no runner; dá para endurecer depois.
2. A versão do emsdk está fixa (`EMSDK_VERSION`) para o resultado ser reproduzível; atualizar à mão.
3. Fuzz: a frente J não tem decode novo.
