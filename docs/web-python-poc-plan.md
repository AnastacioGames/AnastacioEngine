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

## Referências

- `docs/web-export-plan.md` — levantamento e histórico de bugs já corrigidos
  no build Emscripten da engine.
- `docs/changelog.md` — entradas de 2026-09-12 com os fixes aplicados até
  agora.
- [Emscripten: packaging files](https://emscripten.org/docs/porting/files/packaging_files.html)
- [Emscripten: Filesystem API](https://emscripten.org/docs/api_reference/Filesystem-API.html)
- [Emscripten: runtime environment](https://emscripten.org/docs/porting/emscripten-runtime-environment.html)
