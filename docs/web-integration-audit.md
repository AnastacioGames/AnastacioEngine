# Web — auditoria da integração com a engine

Data: 2026-09-12. Complemento à Etapa 6 de [web-python-poc-plan.md](web-python-poc-plan.md).

**Estado: auditoria estática concluída; integração, build e execução Web não realizados nesta frente.** Nenhum código, preset ou artefato da PoC foi alterado. Os pontos abaixo distinguem evidência no código de propostas a validar. Não constituem inventário exaustivo de símbolos de link ou de shaders.

## Resultado que guia o trabalho

O Python Wasm continua necessário, mas não encerra o port. Há três frentes confirmadas no código: configuração de dependências, duração de vida do launcher no loop assíncrono e adaptação do caminho gráfico desktop. A engine já oferece uma unidade de execução por frame; não é necessário começar reescrevendo a lógica do jogo.

Trabalhar de trás para frente aqui significa definir o teste final e localizar seus pré-requisitos. A implementação continua respeitando essas dependências. Claude pode concluir a PoC 0–5 enquanto esta auditoria prepara a convergência; a decisão definitiva de threads e alterações no renderer permanecem na Etapa 6.

## 1. Contrato do primeiro teste real

Preparar posteriormente uma cena `.range` com câmera ativa e cubo visível, material opaco simples, sem texturas externas, sombras, partículas, armatures, filtros, áudio, streaming ou scripts de menu. Preservar a física padrão inicialmente, sem exigir simulação dinâmica para movimentar o cubo.

Usar **Python Controller real**, acionado por sensor Always com pulso, e módulo com `import Range` (não presumir alias `bge`). Ler A/D via `Range.logic.keyboard` e alterar a posição do proprietário. Não configurar um script que assuma o loop principal Python da engine. Validar primeiro essa mesma cena no desktop para separar defeito do conteúdo de defeito do port.

Aceite no navegador, servido por HTTP:

1. `.range`, stdlib e scripts são encontrados no FS virtual, sem caminhos locais Windows/WSL.
2. Logs identificam cena carregada, Python inicializado, controller executado e contexto gráfico efetivamente obtido.
3. Cubo desenhado pela engine; A/D pressionadas e liberadas movem e param o cubo. Um desenho SDL separado não satisfaz esse item.
4. Página responsiva por alguns minutos; registrar contagem de frames/controllers e memória ao longo do teste. Crescimento inicial não deve ser confundido com vazamento; ausência de crescimento não prova ausência de vazamentos.
5. Perder e recuperar foco não deixa tecla presa; aba oculta e retomada não produzem salto descontrolado. Medir o comportamento antes de escolher política de pausa/tempo.
6. Encerrar cancela callbacks antes de liberar cena/Python/contexto. Recarregar a página permite repetir o teste. Restart e troca de jogo podem ficar explicitamente sem suporte neste primeiro marco.
7. Guardar navegador/versão, SDK, revisão Python, flags, logs de shaders e confirmação visual do usuário. Sem isso, registrar apenas o marco parcial alcançado.

## 2. Dependências: mínimo de conteúdo não é mínimo de compilação

Referências locais: [preset](../source/CMakePresets.json), [plataforma Web](../source/build_files/cmake/platform/platform_web.cmake), [CMake do imbuf](../source/source/blender/imbuf/CMakeLists.txt).

| Peça | Evidência / ação para a Etapa 6 |
|---|---|
| CPython | Consumir biblioteca Wasm, headers e `pyconfig.h` do alvo produzidos pela PoC; religar Python e revisar includes/link/stdlib. Python executado no host para geração de código é outro papel. |
| JPEG e PNG | `jpeg.c` e `png.c` estão na lista base de `bf_imbuf`; não desaparecem com uma cena sem texturas. Fornecer bibliotecas/headers do alvo e integração CMake. |
| TIFF e OpenJPEG | **Correção do levantamento anterior:** `tiff.c` e `jp2.c` são condicionais a `WITH_IMAGE_TIFF` e `WITH_IMAGE_OPENJPEG`. Ambas opções têm default ON e não são desligadas no preset Web lido. Propor OFF no mínimo e verificar o cache efetivo; não reescrever codecs. |
| zlib, FreeType, SDL2 | Preset já contém flags das portas. Confirmar que todos os alvos consumidores recebem headers e flags de link; a presença da flag global não valida o produto final. |
| Boost | Includes diretos de `boost/format.hpp` e `boost/algorithm/string.hpp` em Expressions, Ketsji, GameLogic e player. Esses usos são candidatos a atendimento por headers; não concluir que todos os usos transitivos dispensam bibliotecas compiladas. Desligar `WITH_BOOST` não remove includes incondicionais. |
| TBB | `KX_CullingHandler.cpp:6,88` inclui TBB e executa `parallel_reduce` sem guarda. Desligar `WITH_TBB` não cria automaticamente alternativa serial. Decidir entre biblioteca compatível e fallback serial pequeno, preservando teste, lista visível e contagem; ainda não implementado. |
| Bullet | Manter inicialmente a dependência vendorizada e a configuração física existente. Nenhuma validação Wasm foi feita nesta auditoria; não marcar como portado. |
| Áudio, vídeo e recursos pesados | OpenAL/Audaspace, FFmpeg/AVI, Cycles, OCIO/OIIO, OpenVDB, fluid/smoke já estão OFF no preset. Manter no primeiro marco; confirmar dependências transitivas no grafo configurado. |

`platform_web.cmake` ainda é um stub sem descoberta de dependências. O preset usa Ninja do Windows e diretório `build-web`; a integração WSL precisa de diretório próprio e configuração Linux. Não reaproveitar cache nativo nem bibliotecas `.lib`/ELF como bibliotecas Wasm.

Separar geradores de build e runtime: `makesdna` e `makesrna` têm `NODERAWFS` próprio nos respectivos CMakeLists. Preservar essa separação; não copiar essa flag para a página final. Fazer a inspeção do grafo configurado e das bibliotecas antes do primeiro link completo, pois a lista acima não prova fechamento de todas as dependências.

### Threads: há mais que TBB

[KX_KetsjiEngine.cpp](../source/source/gameengine/Ketsji/KX_KetsjiEngine.cpp) e [RAS_ICanvas.cpp](../source/source/gameengine/Rasterizer/RAS_ICanvas.cpp) criam schedulers com `TASK_SCHEDULER_AUTO_THREADS`. Em [task.c](../source/source/blender/blenlib/intern/task.c), `BLI_task_scheduler_create` (linha 454) chama `pthread_create`; mesmo solicitar uma thread total entra no ramo que acrescenta uma thread de background. Portanto, limitar a contagem a um não demonstra execução sem workers.

Antes da integração escolher, com teste específico, entre um caminho serial completo dos schedulers/culling e build com pthreads. Não substituir `pthread_create` por um no-op: tarefas pendentes, espera e encerramento precisam continuar corretos. O sucesso da PoC Python sem threads não decide isso. Pthreads Web têm requisitos de compilação/hospedagem e restrições de bloqueio na thread principal; conferir na versão de SDK fixada. [Referência oficial](https://emscripten.org/docs/porting/pthreads.html).

## 3. Ponto de adaptação do loop e input

O fluxo standalone está em [GPG_Ghost.cpp](../source/source/gameengine/GamePlayer/GPG_Ghost.cpp), linhas 1583–1613: constrói `LA_PlayerLauncher` como variável local, chama `InitEngine`, `EngineMainLoop`, copia configurações e chama `ExitEngine`, liberando depois dados da cena. Há um loop externo para restart/troca de jogo e limpeza posterior de Python/GPU.

Em [LA_Launcher.cpp](../source/source/gameengine/Launcher/LA_Launcher.cpp):

- `EngineMainLoop` contém o `while` bloqueante (linha 541).
- `EngineNextFrame` já executa `KX_KetsjiEngine::NextFrame`, consulta saída, renderiza quando necessário, processa/entrega eventos GHOST e verifica tecla de saída/fechamento.
- Existe um caminho alternativo `GetPythonMainLoopCode` → `RunPythonMainLoop` → `PyRun_SimpleString`, com estado local para callbacks Python. Adaptar só o `while` C++ deixaria esse caminho potencialmente bloqueante.

Proposta: estado persistente de sessão Web possuindo launcher, dados carregados e recursos que hoje vivem no escopo local. Inicializar uma vez e registrar callback que chama **uma vez** `EngineNextFrame`, retornando ao navegador. Ao receber saída, cancelar o callback e executar limpeza exatamente uma vez. Não deixar o fluxo cair imediatamente no `ExitEngine` após registrar o callback, nem capturar ponteiro para variável local que saiu de escopo. [Modelo de execução Emscripten](https://emscripten.org/docs/porting/emscripten-runtime-environment.html).

Preservar inicialmente a ordem atual de eventos/frame. `GHOST_SystemSDL.cpp` traduz `SDL_KEYDOWN/SDL_KEYUP` (linhas 417–418) e usa `SDL_PollEvent` (585); há espera apenas no caminho condicionado de processamento. `EngineNextFrame` solicita `processEvents(false)`. Verificar a entrega ao input da engine e foco no teste real, sem criar outra camada de teclado JavaScript antes de provar necessidade.

Controllers já executam pela lógica da engine: [SCA_PythonController.cpp](../source/source/gameengine/GameLogic/SCA_PythonController.cpp), `Trigger`, chama `PyEval_EvalCode`/`PyObject_CallObject`. Não adicionar uma chamada paralela ao script do cubo no callback Web: isso deixaria de testar o controller e poderia duplicar execução.

## 4. Renderer: bloqueios e recursos adiáveis

WebGL 2 é uma **proposta de piso**, não compatibilidade comprovada. O perfil core desktop existente é trabalho reaproveitável, mas não equivale a GLSL ES. A emulação de OpenGL legado do Emscripten é incompleta; não prova suporte ao renderer. Flags MIN/MAX_WEBGL_VERSION e criação do contexto precisam concordar. [Suporte oficial OpenGL/Emscripten](https://emscripten.org/docs/porting/multimedia_and_graphics/OpenGL-support.html).

| Caminho encontrado | Classificação e próximo teste |
|---|---|
| `GHOST_WindowSDL.cpp:85–91` passa perfil e versões como zero para `GHOST_ContextSDL`; este repassa atributos ao SDL | Contrato de contexto ainda não fixa WebGL 2. Testar criação explícita e registrar versão real; compilar GHOST não prova abertura da janela no navegador. |
| `gpu_shader.c`, `gpu_shader_version`, gera `#version 330 core` ou variantes desktop compatibility/120/130 | Bloqueio concreto do caminho desktop para shaders WebGL. Preparar variante ES e verificar também corpo, atributos, saídas, precision e extensões; trocar só o texto de versão não basta. |
| `KXImgui/KX_Imgui.cpp:75` inicializa backend com `#version 120` | Verificar inicialização mesmo sem menu visível. Ocultar UI não garante que shaders do backend deixam de ser compilados. Adaptar ou excluir explicitamente do caminho mínimo. |
| `gpu_framebuffer.c` usa `glDrawBuffer`, além de `glDrawBuffers` | Auditar operações realmente usadas pelos offscreens do cubo e validar completude de framebuffer. Não presumir que sem filtros não há offscreen. |
| `RAS_OpenGLRasterizer.cpp:347–350` usa `glPolygonMode` para linha **e preenchimento** | Wireframe pode ser adiado, mas o ramo de preenchimento também deve receber tratamento compatível. Não basta desligar wireframe na cena. |
| `RAS_StorageVbo.cpp:130` usa `glMapBufferRange` com escrita/invalidação | Condicional ao caminho de atualização dos índices. Confirmar alcance no cubo; avaliar upload explícito ou emulação suportada pelo SDK, sem tratar como API WebGL direta. |
| Partículas, skinning, sombras, filtros, queries e readback | Fora do conteúdo mínimo. Código ainda compilado/linkado pode exigir guardas ou integração mesmo sem executar o recurso; ausência na cena não elimina símbolos. Auditar cada recurso antes de anunciar suporte. |

Próximo teste gráfico útil após a PoC SDL: compilar e executar o shader/material efetivamente gerado para o cubo, conservar fonte e log completo de falha, verificar buffers/offscreen e só então expandir materiais. Não iniciar conversão indiscriminada de todos os shaders nesta auditoria.

## 5. Ordem de convergência com a PoC

1. Receber manifesto do Python: revisão, SDK, flags, threads, caminhos de biblioteca/headers/stdlib e testes no navegador aprovados.
2. Configurar árvore Web Linux isolada, conferir dependências efetivas e escolher tratamento de TBB/schedulers; revalidar Python se mudar threads.
3. Provar link e inicialização da engine; cada falha deve ter causa e correção isoladas, respeitando a regra anti-loop do `AGENTS.md`.
4. Adaptar duração de vida/callback/encerramento; validar frames retornando ao navegador e carga da cena.
5. Validar contexto, shader e desenho da cena mínima. Religar o controller e validar input pelo caminho existente.
6. Executar o contrato da seção 1. Só depois abrir áudio, persistência e recursos de jogo da Etapa 7.

## 6. Complemento: passagem do Python isolado para o player

Auditoria adicional em 2026-09-12, somente leitura de fontes. Estes itens preparam a integração; não exigem alterar a PoC em andamento nem comprovam compatibilidade binária com CPython 3.11 Wasm.

### Inicialização em duas fases

O standalone chama `initPlayerPython(argc, argv)` em `GPG_Ghost.cpp:1321`, antes do loop de carregamento de jogos. A função em [KX_PythonInit.cpp](../source/source/gameengine/Ketsji/KX_PythonInit.cpp) configura nome do programa, registra módulos internos, procura o Python distribuído com a aplicação e chama `Py_Initialize`. O caminho do editor, `BPY_python_start`, é separado: uma adaptação feita somente nele não atende o player.

Depois, `LA_Launcher::InitEngine` define `KX_SetMainPath(m_maggie->name)` e chama `initGamePython`, antes de converter/criar a cena. Essa segunda fase configura imports associados ao arquivo do jogo, importa módulos nativos e cria `Range` e seus submódulos. Portanto, distinguir nos logs:

1. Interpretador inicializado e stdlib acessível.
2. Módulos internos importados e `Range` registrado.
3. Cena convertida e controller executado.

O sucesso do primeiro marco não implica o segundo. Evitar acrescentar outra inicialização do Python ao callback Web: o player já tem um responsável por isso.

### Módulos obrigatórios antes do cubo

`bge_internal_modules` registra `mathutils`, `bgl` e `blf` incondicionalmente; `aud` é condicionado a `WITH_AUDASPACE`. `initGamePython` importa cada entrada mesmo que o script do cubo não a use. São módulos nativos da engine, não arquivos que aparecem automaticamente ao empacotar a stdlib do CPython.

`initRANGE` também chama os inicializadores de `Range.application`, `constraints`, `events`, `logic`, `render`, `types`, `imgui` e `texture`. Isso amplia a superfície de inicialização além do controller mínimo; não significa que todos os recursos desses módulos serão executados.

Há um ponto concreto de diagnóstico a tratar na integração: o loop de imports usa `Py_DECREF(mod)` sem verificar se `PyImport_ImportModuleLevel` retornou nulo. Uma falha de import pode terminar em acesso inválido antes de produzir um diagnóstico útil. A futura correção deve verificar o retorno, emitir o traceback e interromper a inicialização com limpeza adequada. Trocar apenas por `Py_XDECREF` e continuar ocultaria a falha. Não houve alteração desse código nesta frente.

### Contrato dos arquivos e caminhos

| Entrada | Evidência e decisão pendente |
|---|---|
| Raiz do Python | `initPlayerPython` consulta `BKE_appdir_folder_id(BLENDER_SYSTEM_PYTHON, ...)`. Em [appdir.c](../source/source/blender/blenkernel/intern/appdir.c), a busca considera a variável `BLENDER_SYSTEM_PYTHON` e diretórios de instalação. Definir na integração uma raiz existente no FS virtual, compatível com o layout realmente produzido pela PoC. |
| Configuração do interpretador | [PyC_SetHomePath](../source/source/blender/python/generic/py_capi_utils.c) chama `Py_SetPythonHome` quando recebe um caminho. Não copiar um home desktop nem presumir que apontar para qualquer diretório de scripts resolve a stdlib. Se a PoC usar outra configuração de inicialização, reconciliar explicitamente os dois caminhos. |
| Arquivo do jogo | Usar caminho virtual explícito, por exemplo `/game/cube.range`. Esse nome deve chegar ao carregador e a `m_maggie->name`/`KX_GetMainPath`; o exemplo é um contrato proposto, não um caminho já implementado. |
| Módulo externo | `initPySysObjects` acrescenta ao `sys.path` o diretório do jogo e os diretórios das bibliotecas vinculadas. Um `cube_logic.py` ao lado do `.range` é um primeiro layout simples a testar. Registrar `sys.path` efetivo após essa fase. |
| Console Python | `createPythonConsole` procura `scripts/bge/interpreter.py` e o abre com `fopen(..., "r+")`, sem verificação local de nulo antes de executar. Manter `GAME_PYTHON_CONSOLE` desligado na cena mínima; o console tem empacotamento e tratamento de erro próprios a validar depois. |

Para entregar os artefatos da PoC à integração, registrar o caminho no host **e** o destino virtual de cada componente: biblioteca/headers são entradas de compilação; stdlib/scripts/cena são dados do runtime. Incluir formato da stdlib, módulos disponíveis e configuração de inicialização que efetivamente passou no navegador. Não impor agora um novo layout ao trabalho do Claude.

### Callback deve preservar também o resize do player

[LA_PlayerLauncher.cpp](../source/source/gameengine/Launcher/LA_PlayerLauncher.cpp) sobrescreve `EngineNextFrame`: antes de chamar a implementação base, trata `WINRESIZE`, atualiza canvas/offscreen e informa a engine. O callback futuro deve chamar o método do launcher concreto, preservando esse caminho. Uma chamada qualificada diretamente a `LA_Launcher::EngineNextFrame` contornaria o tratamento de resize.

Acrescentar ao aceite: redimensionar o canvas/janela, verificar desenho e input após a mudança, guardar erros de framebuffer/contexto. Isso é teste adicional da engine; não precisa ser incorporado à PoC Python isolada.

### Sequência curta para diagnosticar a primeira integração

| Último marco observado | Próxima inspeção dirigida |
|---|---|
| Não chegou a inicializar Python | Arquivos virtuais disponíveis no momento da inicialização, home e configuração herdada da PoC. |
| Python funciona, mas inicialização do jogo falha | Retornos e traceback dos imports `mathutils`/`bgl`/`blf`, seguidos da criação de `Range`. |
| `Range` existe, módulo do cubo não importa | Nome efetivo do `.range`, `KX_GetMainPath`, `sys.path` e presença do módulo no FS virtual. |
| Controller executa, cubo não aparece | Seguir a auditoria de contexto/shader/offscreen da seção 4; não atribuir automaticamente ao Python. |
| Desenho funciona, resize quebra | Conferir despacho pelo `LA_PlayerLauncher` e recriação de offscreens. |

Esses marcos são uma proposta de instrumentação e triagem para a Etapa 6, ainda não executada. A leitura não substitui compilar contra os headers Wasm exatos nem testar imports e execução no navegador.

## Limites e manutenção

Leitura de código e documentação oficial, sem build nem teste visual. A consulta auxiliar via `tools/ask_local.sh` retornou resposta sem análise do arquivo; os achados foram verificados diretamente no código. Referências de linha são indicativas e podem mudar com trabalho concorrente.

O roadmap ainda descreve `OPENGLES_LIBRARY` como bloqueio atual, embora a seção posterior de `web-export-plan.md` registre sua correção. Também é imprecisa a afirmação anterior de que TIFF/OpenJPEG não têm gate. Este documento registra as correções sem editar os arquivos compartilhados durante a PoC. Ao integrar os resultados, atualizar o estado vigente e o histórico conforme o workflow do projeto.
