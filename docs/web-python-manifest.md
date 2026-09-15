# Manifesto do Python Wasm (PoC) — insumo para a Etapa 6

Consolida, num único lugar, o que `docs/web-integration-audit.md` (seção 5,
item 1: "Ordem de convergência com a PoC") pede antes de começar a
integração real ao `RangeRuntime`. Não altera nem substitui
`docs/web-python-poc-plan.md`, que continua sendo o registro de processo;
este documento é o resumo "pronto para consumo" pela auditoria do Codex.

## Revisão e SDK

| Item | Valor |
|---|---|
| CPython | branch `3.11`, commit `9eaf48a56547872b86de5cecbaa7edd3279159ed` (2026-08-20) |
| emsdk | `6.0.9` (mesma versão usada no `D:\emsdk` do Windows e em `~/emsdk` no WSL) |
| Processo de build | `Tools/wasm/wasm_build.py` (fluxo oficial `configure-build-python` → `configure-host` → `make-host`), sem patches locais |
| Diretório de origem | `~/web-python-poc/cpython` (WSL), separado de `build-web/` (Windows/Ninja) |

## Threads

- **Sem pthreads / `SharedArrayBuffer`** nesta PoC (Etapas 2–3). Decisão
  tomada na Etapa 1 para simplificar o primeiro teste (evita exigir
  cabeçalhos COOP/COEP no servidor).
- Isso **não decide** a questão de threads da engine (`TASK_SCHEDULER_AUTO_THREADS`,
  `pthread_create` em `task.c:454`, TBB em `KX_CullingHandler.cpp`) — ver
  seção "Threads: há mais que TBB" do audit. Se a integração exigir pthreads
  reais, os testes das Etapas 2–3 precisam ser **repetidos** com CPython
  recompilado nessa configuração antes de reusar os artefatos abaixo.

## Artefatos de build (entradas de compilação)

Gerados em `~/web-python-poc/cpython/builddir/emscripten-browser/`:

| Artefato | Papel |
|---|---|
| `libpython3.11.a` (~29 MB) | biblioteca estática do interpretador |
| Headers (`Include/`, `pyconfig.h` do alvo) | compilação de qualquer C que use a API Python |
| `Modules/_decimal/libmpdec/libmpdec.a` | dependência de `_decimal` |
| `Modules/expat/libexpat.a` | dependência de `pyexpat` |

Flags de link obrigatórias (reproduzidas do `python.js` de referência do
próprio CPython, confirmadas por link bem-sucedido nas Etapas 2 e 3):

```
-lpython3.11
<path>/libmpdec.a
<path>/libexpat.a
-sUSE_ZLIB -sUSE_BZIP2 -sUSE_SQLITE3
-lpthread -ldl -lm
```

`-lpthread` aqui é a variante no-threads do runtime (POSIX threads
stub/single-thread), não pthreads reais do Emscripten — consistente com a
decisão da Etapa 1.

## Stdlib e caminhos (dados de runtime)

- Stdlib empacotada em `usr/local/lib/python3.11` + `python311.zip`, dentro
  do mesmo diretório de build.
- Carregada no FS virtual via `--preload-file=<host>/usr/local@/usr/local`
  — **não** é `IDBFS` (reservado para persistência/saves, Etapa 7).
- Scripts/módulos do jogo (ex.: `game_logic.py`, `config.json` na Etapa 3)
  usam um `--preload-file` **separado**, mapeado para um destino próprio
  (`/assets` no teste da Etapa 3) e adicionados a `sys.path` explicitamente
  via `PyList_Append` em C antes do `PyImport_ImportModule`.
- Nenhum caminho absoluto de Windows/WSL aparece no binário ou no
  `sys.path` final — só caminhos virtuais (`/usr/local`, `/assets`).
- **Ainda não reconciliado com o player real**: `initPlayerPython` usa
  `BKE_appdir_folder_id(BLENDER_SYSTEM_PYTHON, ...)` +
  `PyC_SetHomePath`/`Py_SetPythonHome` (ver audit, seção 6, "Contrato dos
  arquivos e caminhos"). A PoC chama `Py_InitializeEx(0)` direto, sem
  configurar home path — a Etapa 6 precisa decidir a raiz virtual do Python
  (ex. `/usr/local`) e alimentar isso em `PyC_SetHomePath`, não presumir que
  os dois caminhos já coincidem.

## Testes aprovados (o que está provado, e o que não está)

| Teste | Etapa | Resultado |
|---|---|---|
| `Py_Initialize` + script embutido retornando valor pro C | 2 | `STAGE2_OK valor_recebido_do_python=42`, validado via Node **e confirmado em Chrome real** (headless, `--dump-dom`) |
| Import de stdlib (`json`, `math`) + módulo externo real + leitura de arquivo + traceback de exceção controlada | 3 | `STAGE3_DISTANCE_OK valor=5.000000` + traceback completo e correto via `PyErr_Print()`, validado via Node **e confirmado em Chrome real** |
| Callback por frame (`emscripten_set_main_loop`) + round-trip Python → C | 4 | `STAGE4_INIT_OK` confirmado em Chrome real (boot idêntico ao Node); `STAGE4_OK frames=180 posicao_final=0.000000` validado via Node — a impressão final do loop de frames não foi recapturada em Chrome headless por limitação de automação (`--dump-dom` não aguarda de forma confiável o ciclo completo de `requestAnimationFrame`), não por falha da lógica |
| SDL2 + WebGL + Python movendo objeto | 5 | **confirmado em Chrome real** (headless, WebGL via ANGLE/SwiftShader): `STAGE5_GL_CONTEXT_OK versao=OpenGL ES 3.0 (WebGL 2.0)`, quadrado renderizado corretamente (screenshot); **e em Chrome real com sessão interativa do usuário**, incluindo teclas A/D movendo o objeto corretamente. Falha esperada em Node (`ReferenceError: screen is not defined`, ambiente sem DOM/WebGL) — comportamento correto, não é bug. **Bug real encontrado e corrigido durante a validação**: o `index.html` gerado para esta etapa não continha elemento `<canvas>`, causando erros repetidos (`registerOrRemoveHandler: the target element for event handler registration does not exist`) e impedindo a criação do contexto GL; corrigido adicionando `<canvas id="canvas">` e `Module.canvas` apontando para ele. Esse HTML é gerado localmente (fora do repo), então não há arquivo versionado a ajustar — mas a Etapa 6 precisa garantir que o HTML final do `RangeRuntime` sempre inclua um `<canvas>` referenciado por `Module.canvas` |

Confirmação em Chrome real feita em duas etapas: (1) Chrome headless
(`--headless=new`, `--use-gl=angle --use-angle=swiftshader` para WebGL via
software) rodando no Windows contra os servidores HTTP do WSL, com captura
de DOM (`--dump-dom`) e screenshot (`--screenshot`); (2) sessão interativa
real do usuário nas 4 URLs, que confirmou visualmente as Etapas 2–5,
incluindo movimentação por teclado (A/D) na Etapa 5 — cobrindo a lacuna que
a simulação headless de eventos de teclado não conseguiu validar.

## O que este manifesto não cobre

- Módulos nativos da engine (`mathutils`, `bgl`, `blf`, `Range` e
  submódulos) — não fazem parte do CPython puro, são registrados por
  `initGamePython`/`initRANGE` no player (ver audit, seção 6). Ficam por
  conta da Etapa 6 linkar contra o `libpython3.11.a` desta PoC.
- Decisão final de threads da engine (schedulers, TBB, `pthread_create`).
- Qualquer coisa do renderer (seção 4 do audit) — fora do escopo desta PoC
  Python-isolada.

## Etapa 6 — início (2026-09-12)

Os artefatos descritos acima foram relocados para `D:\python-wasm-web` (fora
do WSL) e o preset `web-runtime` religou `WITH_PYTHON=ON` com sucesso no
configure. O build travou logo em seguida num problema estrutural do
preset, **não relacionado ao Python**: ferramentas geradoras de código do
build (`makesdna`, `datatoc`, conversor de shaders) compilam para wasm em
vez de nativo e não rodam no host Windows. Detalhes e próximos passos em
`docs/web-python-poc-plan.md`, seção "Etapa 6", "Status (2026-09-12)".

## Referências

- `docs/web-python-poc-plan.md` — processo completo, Etapas 0–7.
- `docs/web-integration-audit.md` — auditoria da integração (Codex).
