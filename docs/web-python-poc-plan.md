# Plano — Prova de conceito Python-no-navegador (pré-requisito do port Web)

## Contexto

O build `web-runtime` (Emscripten) já avança até compilar boa parte do
`RangeRuntime` (ver `docs/web-export-plan.md`), mas trava porque o game
engine (BGE) usa a API do Python incondicionalmente, sem guardas
`#ifdef WITH_PYTHON`, em dezenas de arquivos. Reescrever esse código é
arriscado (quebra lógica de jogo). A rota escolhida é cross-compilar CPython
3.11 para `wasm32-emscripten` e religar `WITH_PYTHON=ON`.

Este documento define uma **prova de conceito incremental**, isolando cada
variável antes de integrar ao build completo da engine — evita descobrir
problemas de fundo (path da stdlib, FS virtual, padrão de chamada por frame)
só depois de um build de 10+ minutos do `RangeRuntime` inteiro.

Consolidado a partir de duas propostas independentes (Claude e Codex, revisão
cruzada em 2026-09-12); a versão do Codex corrigiu pontos concretos da
primeira leitura, incorporados abaixo.

## Etapa 0 — Ambiente

- WSL2 Ubuntu, realocado para `D:\WSL\Ubuntu` (concluído).
- Dependências de build instaladas via `apt-get` (concluído).
- Pendente: ativar emsdk **Linux** dentro do WSL (o `D:\emsdk` existente é
  Windows-only, não roda a partir do ambiente Linux).
- Diretório de build desta PoC deve ficar **separado** do `build-web/`
  gerado no Windows, para não misturar artefatos de toolchains diferentes.

## Etapa 1 — Fixar ambiente e versões antes de compilar

- Registrar explicitamente: revisão exata do CPython 3.11 (tag/commit),
  versão do emsdk usada, opções de configuração do `wasm_build.py`.
- Usar o **mesmo** SDK Linux (emsdk) para: compilar o Python, rodar os
  testes mínimos desta PoC, e depois compilar a engine — evita divergência
  de toolchain entre etapas.
- Decidir threads cedo: começar **sem** pthreads/`SharedArrayBuffer` no
  teste mínimo (mais simples, sem exigir cabeçalhos COOP/COEP no servidor).
  Se a engine precisar de threads reais em algum subsistema, isso é uma
  decisão separada, tomada mais adiante — não travar a PoC nisso agora.
  Se a integração exigir pthreads, revisar a configuração e recompilar
  CPython e dependências conforme necessário para compatibilidade com o
  runtime. Os binários da PoC sem threads não são artefatos definitivos do
  port; repetir os testes das Etapas 2–5 na configuração escolhida antes
  de avançar com a integração.

**Entrega:** procedimento reproduzível, com ferramentas/caminhos/versões
documentados (neste arquivo ou em anexo).

### Versões fixadas (2026-09-12)

- CPython: branch `3.11`, commit `9eaf48a56547872b86de5cecbaa7edd3279159ed`
  (2026-08-20), clonado em `~/web-python-poc/cpython` dentro do WSL.
- emsdk: `6.0.9` — mesma versão já ativa no `D:\emsdk` (Windows), agora
  também instalada e ativada em `~/emsdk` dentro do WSL, via
  `./emsdk install 6.0.9 && ./emsdk activate 6.0.9`.
- Diretório de trabalho da PoC: `~/web-python-poc/` (dentro do filesystem
  do WSL), separado do `build-web/` gerado no Windows.
- Threads: sem pthreads/`SharedArrayBuffer` nesta primeira rodada, conforme
  decidido acima.

## Etapa 2 — Compilar CPython e provar integração C → Python no navegador

- Rodar o processo oficial de `Tools/wasm/wasm_build.py` (ou os passos que
  ele automatiza: `configure-build-python` → `configure-host` → `make-host`)
  para a revisão fixada na Etapa 1.
- Preservar: `libpython3.11.a`, headers, `pyconfig.h` gerado para o alvo
  wasm, stdlib empacotada, flags de link necessárias.
- Programa de teste em C: `Py_Initialize()`, executa um script Python que
  **retorna um valor** para o C (não só imprime), com **relato explícito de
  erro** se a inicialização falhar (não falhar silenciosamente).

**Aceite:** página servida por HTTP real (`python3 -m http.server`, não
apenas rodar via `node`) executa o teste, e o código C recebe o valor
esperado de volta do Python. Rodar só no Node não fecha esta etapa — o
runtime dentro do navegador tem diferenças de FS/ambiente que o Node não
expõe.

### Status (2026-09-12)

- CPython compilado com sucesso para `emscripten-browser` via
  `wasm_build.py` (revisão fixada acima). Artefatos gerados em
  `~/web-python-poc/cpython/builddir/emscripten-browser/`:
  `libpython3.11.a` (~29 MB), `pyconfig.h`, `python.js`/`python.wasm`
  (build de referência do próprio CPython) e stdlib empacotada em
  `usr/local/lib/python3.11` + `python311.zip`.
- Programa de teste em C criado (`docs/web-python-poc-stage2-test.c`):
  `Py_InitializeEx(0)`, roda um script Python (`6 * 7`), recupera o valor
  via `PyDict_GetItemString`/`PyLong_AsLong`, com `PyErr_Print()` em cada
  ponto de falha (init, execução do script, valor ausente).
- Link final via `emcc`, replicando o mesmo conjunto de libs do
  `python.js` de referência: `libpython3.11.a` + `libmpdec.a` (decimal) +
  `libexpat.a` + `-sUSE_ZLIB -sUSE_BZIP2 -sUSE_SQLITE3` + `-lpthread -ldl -lm`
  + `--preload-file=.../usr/local@/usr/local` (stdlib no FS virtual).
  Primeira tentativa de link falhou por símbolos `mpd_*` não resolvidos
  (faltava `libmpdec.a`/`libexpat.a`/flags de uso das libs) — corrigido
  adicionando exatamente as mesmas libs/flags do link de referência.
- Validado via Node (`node stage2_test.js`): saída
  `STAGE2_OK valor_recebido_do_python=42` — confirma o roundtrip
  C → Python → C.
- Servido via `python3 -m http.server 8765` dentro do WSL
  (`~/web-python-poc/test_stage2/index.html` +
  `docs/web-python-poc-stage2-index.html` como fonte). Pendente:
  confirmação visual em navegador real (WSL2 encaminha `localhost`
  automaticamente para o Windows) — sem headless browser disponível no
  ambiente de build para automatizar essa checagem.

## Etapa 3 — Validar import de módulos e arquivos, antes do loop por frame

- Empacotar um `game_logic.py` externo (fora do binário, arquivo real).
- Importar módulos da stdlib (`json`, `math`) e o módulo externo.
- Ler um arquivo de configuração simples a partir do Python.
- Provocar uma exceção controlada e verificar que o traceback aparece
  corretamente (diagnóstico de erro, não só o caminho feliz).
- **Correção importante**: `--preload-file` (Emscripten) é o mecanismo para
  carregar arquivos/scripts iniciais no FS virtual; `IDBFS` é para
  **persistência** (saves) e não é necessário aqui. Ver
  [packaging files](https://emscripten.org/docs/porting/files/packaging_files.html)
  e [Filesystem API](https://emscripten.org/docs/api_reference/Filesystem-API.html).

**Aceite:** imports, leitura de arquivo e diagnóstico de exceção funcionam
sem depender de nenhum caminho da máquina de desenvolvimento (tudo via
`--preload-file`/FS virtual).

### Status (2026-09-12)

- Módulo externo `game_logic.py` criado
  (`docs/web-python-poc-stage3-game_logic.py`): `compute_distance(config_path)`
  lê um `config.json` (`json.load`) e calcula distância euclidiana
  (`math.sqrt`); `trigger_controlled_exception()` levanta `ValueError`
  proposital.
- Arquivo de config (`docs/web-python-poc-stage3-config.json`): dois pontos
  `(0,0)` e `(3,4)` — distância esperada `5.0`, valor determinístico fácil
  de conferir.
- Programa de teste em C (`docs/web-python-poc-stage3-test.c`): adiciona
  `/assets` a `sys.path`, importa `game_logic`, chama `compute_distance`
  com `/assets/config.json`, confere o valor recebido, depois chama
  `trigger_controlled_exception` e verifica que o C recebe `NULL` (erro
  Python) em vez de derrubar o processo — imprime o traceback via
  `PyErr_Print()` entre marcadores (`STAGE3_EXCEPTION_TRACEBACK_INICIO/FIM`).
- Link via `emcc`: mesmo conjunto de libs da Etapa 2
  (`libpython3.11.a` + `libmpdec.a` + `libexpat.a` +
  `-sUSE_ZLIB -sUSE_BZIP2 -sUSE_SQLITE3` + `-lpthread -ldl -lm`), com
  **dois** `--preload-file`: a stdlib (`usr/local@/usr/local`, igual à
  Etapa 2) e os assets do jogo
  (`test_stage3/assets@/assets`, contendo `game_logic.py` e
  `config.json`) — compilou de primeira, sem erros de link novos.
- Validado via Node (stdout/stderr capturados separadamente, pois o
  console do Node intercala os dois fluxos e embaralha a leitura se
  combinados): stdout mostra
  `STAGE3_DISTANCE_OK valor=5.000000` seguido de
  `STAGE3_EXCEPTION_TRACEBACK_INICIO` / `_FIM` / `STAGE3_OK`; stderr
  mostra o traceback completo e correto (`game_logic.py`, linha do
  `raise`, mensagem da exceção) — confirma import de stdlib, import de
  módulo externo, leitura de arquivo via FS virtual, e diagnóstico de
  exceção sem crash.
- Servido via `python3 -m http.server 8766` dentro do WSL
  (`test_stage3/index.html`, cópia do harness da Etapa 2 apontando para
  `stage3_test.js`). HTTP 200 confirmado para a página e para o `.js`.
  Pendente, como na Etapa 2: confirmação visual em navegador real (sem
  headless browser disponível neste ambiente para automatizar).

> **Pacote de execução 1 (próximo passo imediato): Etapas 1–3.**
> Entrega uma página HTTP que chama Python, importa um script externo e
> devolve um resultado pro C — avanço concreto e revisável antes de tocar no
> loop da engine.

## Etapa 4 — Chamadas repetidas e ponte Python → C (padrão de frame)

- Expandir o teste para um callback por frame via
  `emscripten_set_main_loop()`, com Python inicializado **uma única vez**
  (não por frame).
- C chama `update(dt, input)`; Python chama de volta uma pequena função
  exposta pelo C para atualizar uma posição (round-trip bidirecional,
  simulando o padrão real do BGE: engine chama script, script chama API da
  engine).
- O navegador precisa recuperar o controle entre frames — não pode haver
  loop bloqueante. Ver
  [Emscripten runtime environment](https://emscripten.org/docs/porting/emscripten-runtime-environment.html).

**Aceite:** resultado correto sustentado por alguns minutos, página
responsiva, sem crescimento contínuo inexplicado de memória. (Detecta
problemas evidentes; não prova sozinho ausência de vazamentos — validação
mais profunda fica para a integração real.)

### Status (2026-09-12)

- Módulo `game_logic.py` (`docs/web-python-poc-stage4-game_logic.py`):
  `update(dt, input_left, input_right)` mantém uma posição em variável de
  módulo e chama `stage4_engine.set_position(...)` — o módulo
  `stage4_engine` é a "API da engine" exposta pelo C, não um arquivo
  Python.
- Programa em C (`docs/web-python-poc-stage4-test.c`): registra o módulo
  embutido `stage4_engine` via `PyImport_AppendInittab` **antes** de
  `Py_InitializeEx`, com um único método (`set_position`) que grava num
  campo de uma `struct` estática (`Stage4State g_state`) — deliberadamente
  **não** uma variável local de `main`, para não capturar um ponteiro que
  sairia de escopo no callback assíncrono (risco citado em
  `docs/web-integration-audit.md`, seção 3).
- Loop por frame via `emscripten_set_main_loop(main_loop_iter, 0, 1)`
  (fps=0 → usa `requestAnimationFrame`; `simulate_infinite_loop=1` → o
  controle volta ao navegador entre frames, sem `while` bloqueante).
  `Py_InitializeEx` roda uma única vez em `main`, antes do registro do
  loop; cada iteração só chama `PyObject_CallObject` em `update`.
- Padrão de input determinístico (sem depender de teclado real): move para
  a direita por 90 frames, depois para a esquerda por mais 90 — simetria
  escolhida para dar um valor final verificável (deve voltar a `0.0`) sem
  provar por si só que a posição mudou no meio do caminho.
- Compilou de primeira reusando o mesmo conjunto de libs/flags das Etapas
  2–3 (`libpython3.11.a` + `libmpdec.a` + `libexpat.a` +
  `-sUSE_ZLIB -sUSE_BZIP2 -sUSE_SQLITE3` + `-lpthread -ldl -lm`), com os
  dois `--preload-file` de sempre (stdlib + assets do jogo).
- Validado via Node (stdout/stderr separados): `STAGE4_INIT_OK aguardando
  frames...`, depois `STAGE4_MEIO_CAMINHO frame=89 posicao=14.833333`
  (confirma que a posição mudou de fato, não ficou travada em zero) e por
  fim `STAGE4_OK frames=180 posicao_final=0.000000` — round-trip C → Python
  → C sustentado por 180 chamadas de frame, sem crash, sem loop
  bloqueante, sem reinicializar o Python a cada frame.
- Servido via `python3 -m http.server 8767` dentro do WSL
  (`test_stage4/index.html`, mesmo harness das etapas anteriores apontando
  para `stage4_test.js`). HTTP 200 confirmado para a página e para o `.js`.
  Pendente, como nas Etapas 2–3: confirmação visual em navegador real (sem
  headless browser disponível neste ambiente).
- **Limite explícito desta etapa**: 180 frames via Node não é o mesmo que
  "alguns minutos" num navegador real com `requestAnimationFrame` de
  verdade — fecha a prova de padrão (callback, round-trip, sem
  reinicialização), não fecha sozinha a parte de estabilidade/memória do
  aceite. Isso fica para quando o navegador rodar o teste por mais tempo.

## Etapa 5 — Prova gráfica: SDL2 + WebGL + Python

- Antes de tocar no `RangeRuntime`: programa separado que desenha um
  triângulo/quadrado via SDL2 e o move com teclado real, usando a mesma
  função Python da Etapa 4 para calcular a posição.
- Alvo inicial proposto: **WebGL 2**, sujeito a confirmação com os caminhos
  gráficos já existentes na engine (ver gaps de GLSL ES/WebGL 1 vs. 2 em
  `docs/web-export-plan.md`).

**Aceite:** desenho e movimento no navegador, sem erro de compilação de
shader. Este marco comprova a combinação das tecnologias (Python + SDL2 +
WebGL); a compatibilidade do renderizador *da engine* continua sendo uma
etapa própria, não coberta por este teste isolado.

### Status (2026-09-12)

- Programa em C (`docs/web-python-poc-stage5-test.c`): reusa o mesmo
  padrão da Etapa 4 (`stage4_engine.set_position`, `game_logic.update`),
  acrescentando `SDL_Init(SDL_INIT_VIDEO)`, criação de janela/contexto
  `SDL_GL_CONTEXT_PROFILE_ES` (WebGL 2), leitura de teclado real via
  `SDL_GetKeyboardState` (`A`/`D`) em vez do padrão determinístico da
  Etapa 4, e desenho de um quadrado (via `glScissor`+`glClear`, sem
  depender de pipeline de shader/VBO) cuja posição horizontal reflete a
  variável atualizada pelo Python.
- Compilado com `-sUSE_SDL=2 -sMIN_WEBGL_VERSION=2 -sMAX_WEBGL_VERSION=2`,
  além do mesmo conjunto de libs/flags do Python usado nas Etapas 2–4.
  Primeira compilação: o Emscripten baixou e cacheou automaticamente o
  port `sdl2` (`libSDL2.a`) — sem intervenção manual, sem erro de link.
- **Validação via Node não fechou esta etapa** (esperado, conforme o
  próprio texto da Etapa 5 e da Etapa 2): falhou em
  `_emscripten_get_screen_size` com `ReferenceError: screen is not
  defined` — Node não tem `window`/`screen`/WebGL. Isso não é um bug a
  corrigir; é a ausência de DOM do Node, motivo pelo qual esta etapa
  **depende do navegador real** para fechar (diferente das Etapas 2–4,
  que puderam ser pré-validadas fora do navegador).
- Servido via `python3 -m http.server 8768` dentro do WSL
  (`test_stage5/index.html`, mesmo harness, apontando para
  `stage5_test.js`). HTTP 200 confirmado para página, `.js` e `.wasm`.
  **Pendente integralmente**: confirmação visual em navegador real —
  contexto WebGL criado com sucesso, quadrado desenhado, e movimento com
  teclas A/D. Sem headless browser neste ambiente, este é o primeiro teste
  da PoC que não pôde ser parcialmente pré-validado por mim antes da
  checagem do usuário.

## Etapa 6 — Integração ao RangeRuntime em partes verificáveis

- Preparar o preset `web-runtime` para o build a partir do WSL (hoje ele
  ainda aponta para o Ninja do Windows e mantém `WITH_PYTHON=OFF` e
  emulação de OpenGL legado — precisa de ajuste próprio, não é só apontar
  `PYTHON_LIBRARY`/`PYTHON_INCLUDE_DIR`).
- Religar `WITH_PYTHON=ON` e resolver as dependências obrigatórias
  identificadas nas explorações anteriores.
- **Atenção**: `NODERAWFS` é usado hoje só para os geradores de dados
  (`datatoc`/`makesdna`/`makesrna`) rodarem sob Node durante o build — é
  exclusivo desse ambiente de ferramenta e **não deve** ser levado ao
  runtime final servido no navegador. Ver
  [NODERAWFS](https://emscripten.org/docs/api_reference/Filesystem-API.html#noderawfs).
- Adaptar inicialização, execução por frame (`emscripten_set_main_loop`) e
  encerramento em mudanças pequenas, verificadas uma a uma:
  inicialização → carregamento do `.range` → cena desenhada → controller
  Python → resposta a teclado.

**Aceite decisivo:** cubo da engine, movido por um Python Controller real,
rodando no navegador — validação visual + logs sem falha.

### Status (2026-09-12)

- Artefatos do CPython wasm (Etapas 2–5) relocados do diretório de trabalho
  do WSL (`~/web-python-poc/cpython/builddir/emscripten-browser/`, fora do
  repo) para um caminho estável acessível pelo build Windows/Ninja:
  `D:\python-wasm-web`, em layout Unix-like (`include/python3.11/`,
  `lib/libpython3.11.a`, `lib/libmpdec.a`, `lib/libexpat.a`,
  `lib/python3.11/` + `lib/python311.zip` para a stdlib).
- `source/CMakePresets.json` (preset `web-runtime`): `WITH_PYTHON` religado
  para `ON`, com `PYTHON_VERSION=3.11` e `PYTHON_ROOT_DIR=D:/python-wasm-web`.
  Adicionado também `CMAKE_FIND_ROOT_PATH_MODE_INCLUDE=BOTH` e
  `CMAKE_FIND_ROOT_PATH_MODE_LIBRARY=BOTH` — sem isso o `find_package` só
  enxerga o sysroot do Emscripten e não encontra o Python fora dele.
- `source/build_files/cmake/platform/platform_web.cmake` (antes um stub
  vazio): adicionado `find_package(PythonLibsUnix REQUIRED)` sob
  `WITH_PYTHON`, espelhando o que `platform_unix.cmake` já fazia.
- **Configure passa limpo** com essas mudanças — `PythonLibsUnix` é
  encontrado e linkado.
- **Build trava em `[49/1688]`, antes de qualquer código do Python ou do
  renderer**: as ferramentas geradoras de código do próprio processo de
  build (`makesdna`, `datatoc`, conversor de shaders GLSL→C) estão sendo
  compiladas para `wasm32-emscripten` (`.js`) em vez de nativas, e o Ninja
  tenta rodá-las via `cmd.exe` no host Windows, que não sabe executar um
  `.js` diretamente. Esse problema é **anterior e independente** da mudança
  de Python — é uma lacuna estrutural do preset `web-runtime`: essas
  ferramentas geram `.c`/`.h` consumidos pelo próprio build e por isso
  precisam rodar no host, não no alvo wasm.
- Correção provável: passe de build separado (nativo, Windows) só para
  `makesdna`/`datatoc`/o conversor de shaders, usado como
  `IMPORTED EXECUTABLE`/`ExternalProject` pelo passe Emscripten — não
  decidido nem implementado ainda; ver nota abaixo sobre a regra anti-loop.
- Pausado aqui por decisão do usuário (sessão longa) antes de investigar o
  dual-toolchain. Próximo passo ao retomar: decidir e implementar como
  compilar essas ferramentas geradoras como binários nativos dentro do
  preset `web-runtime`.

## Etapa 7 — Depois do cubo: rumo a um jogo exportável

- Áudio (OpenAL via Emscripten), saves persistentes (IDBFS, agora sim
  aplicável), shaders restantes, módulos Python usados pelos jogos reais,
  tamanho de download, orçamento de memória, requisitos de hospedagem
  (COOP/COEP se threads reais forem necessárias).
- Registrar recursos suportados e limitações observadas como conclusão
  formal do port.

## Nota sobre bugs secundários já mapeados

Em vez de "resolver Boost/TBB/codecs de imagem conforme o build reclamar"
(abordagem reativa usada até aqui), fazer um **inventário curto dessas
dependências antes do build completo da Etapa 6** — mantendo, ainda assim,
correções isoladas uma por vez e a regra anti-loop do repositório:

- Após duas tentativas falhas de resolver o mesmo erro de build, parar e
  pedir orientação ao usuário, mesmo que os comandos tenham mudado.
- Se o erro aparecer duas vezes seguidas de forma idêntica, não repetir o
  comando pela terceira vez; ler o erro completo e identificar a causa.
- Se um fix conhecido resultar em um erro diferente, parar e relatar o
  erro exato ao usuário, conforme o `AGENTS.md`, sem testar variações às cegas.

## Divisão de trabalho (Claude + Codex, em paralelo)

Para não haver conflito de arquivos nem retrabalho, o trabalho foi dividido
em duas frentes independentes que convergem na Etapa 6:

- **Claude** segue a cadeia 0 → 6: ambiente WSL, compilação do CPython
  wasm32-emscripten, testes mínimos C↔Python (Etapas 0–5), preparando o
  binário/headers que a integração final vai consumir.
- **Codex** audita, em paralelo e sem alterar código nem build, o que a
  integração final (Etapa 6) vai exigir, registrando os achados em
  `docs/web-integration-audit.md` (documento próprio, separado deste):
  - Dependências necessárias para a primeira cena (o que pode ficar
    desligado sem quebrar o teste do cubo).
  - Mapeamento do loop principal da engine: onde adaptar a execução ao
    navegador (`emscripten_set_main_loop`), incluindo chamadas ao Python e
    processamento de input.
  - Auditoria do renderer para WebGL: usos de OpenGL incompatíveis,
    separando bloqueios reais de itens opcionais.
  - Critérios claros do teste final (Etapa 6): cena mínima com cubo,
    controller Python e teclado — o que precisa ser verdade para considerar
    "funcionou".

Ponto de encontro: quando o binário Python da Claude estiver pronto (fim da
Etapa 3/5) e a auditoria da Codex estiver documentada, a Etapa 6 usa os dois
resultados juntos. Nenhuma das duas frentes deve, por enquanto, compilar a
engine inteira, fixar decisão definitiva de threads, ou alterar o renderer —
isso é trabalho da própria Etapa 6, feito depois que as duas partes
convergirem.

## Referências

- `docs/web-export-plan.md` — levantamento e histórico de bugs já corrigidos
  no build Emscripten da engine.
- `docs/changelog.md` — entradas de 2026-09-12 com os fixes aplicados até
  agora.
- [Emscripten: packaging files](https://emscripten.org/docs/porting/files/packaging_files.html)
- [Emscripten: Filesystem API](https://emscripten.org/docs/api_reference/Filesystem-API.html)
- [Emscripten: runtime environment](https://emscripten.org/docs/porting/emscripten-runtime-environment.html)
