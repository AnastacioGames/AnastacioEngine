# Plano de execução: pendências Web do AnastacioEngine

Preparado em 2026-09-20 para execução pelo Claude, a partir da análise somente leitura do runtime Web. Este documento é um roteiro, não comprovação de implementação. As constatações estáticas devem ser reconferidas contra a revisão efetivamente trabalhada.

## Estado de execução (2026-09-20)

- **M0 implementado, validação de navegador pendente** no commit `1c9d1562`: o manifesto passou a declarar `bge` e `aud` condicionado a `WITH_AUDASPACE`; o pré-voo exige WebGL 2 e reprova abort, falha e inicialização incompleta; o empacotador registra essas condições. A suite `tools/tests/web_profile` passou com 83 testes. Falta exportar/executar um pacote Web real.
- **M1 parcialmente implementado, não concluído** no commit `8251b0dc`: falhas de compilação/link do shader comum em WebGL emitem `Module.onDiagnostic` estruturado, com operação, estágio, origem e log; a origem do material/world agora é propagada de `GPU_generate_pass`. `package-web.py` grava relatório v2 e conserva a heurística como fallback; `preflight.py` aceita v1/v2. Depois disso entraram a captura Python, os shaders especiais/filtros e testes Web reais (Edge, build de depuração) de exceção, import, SyntaxError, Unicode/aspas/log longo, repetição em vários objetos, exceção em componente e em callback, e fragment em filtro 2D. Faltam: componente/callback, vertex/link, importação no editor e execução sem pré-voo.
- **Validação feita para o checkpoint M1:** `python -m unittest tools.tests.web_profile.test_preflight -v` (11 testes), `py_compile` dos scripts Python alterados e `git diff --check`, todos aprovados. Uma tentativa de build não é evidência: o diretório `build-android` da worktree apontava para a árvore principal, portanto não compilou este diff. Reconfigurar um build Web limpo da worktree antes de compilar.

## Instrução para o Claude

Execute este plano por marcos, seguindo `AGENTS.md`. Comece pelo M0. Preserve mudanças existentes no workspace. Implemente e valide uma peça autocontida por vez; antes de avançar entre peças grandes ou arriscadas de C++, apresente o resultado e peça confirmação, conforme a regra do repositório, salvo autorização explícita do usuário para execução autônoma.

Não implemente automaticamente os marcos condicionais. Fusão de filtros depende de medição; áudio 3D depende de requisito concreto do jogo; OpenAL depende de insuficiência comprovada do caminho SDL/Audaspace. NumPy e um backend Web Audio próprio ficam fora desta rodada.

Não considere um marco implementado como concluído sem build e execução pertinentes. Diferencie sempre: análise estática, teste automatizado, execução no navegador e aceitação visual/auditiva pelo usuário. Registre bloqueios e validações pendentes com precisão.

## Contexto e preparação

O runtime dos presets `web-runtime` e `web-runtime-release` já executa render, teclado, mouse, gamepad, IDBFS, áudio e Python. Preserve essas capacidades e os jogos já aceitos. Não reabra problemas históricos resolvidos sem reproduzir regressão.

Antes de editar, leia:

- `AGENTS.md` e `docs/README.md`.
- Seção Web de `docs/roadmap.md` e estado vigente em `relatorio-melhorias-anastacioengine.md`.
- `docs/web-deploy.md` e `docs/web-profile-validation-plan.md`.
- Entradas Web de 2026-09-12 a 2026-09-20 em `docs/changelog.md`.
- `docs/web-audio-analysis.md` antes do trabalho de áudio.
- Resumos pertinentes em `docs/local-knowledge/`, tratando-os como orientação, não como prova. Use o modelo local para primeira varredura/resumo conforme `AGENTS.md`; decisões arquiteturais e revisão permanecem com o agente principal.

Faça `git status --short` e identifique alterações prévias. Na preparação deste plano já havia alterações em documentação, um plano Android não rastreado e diretórios de projetos de teste não rastreados. Não limpar, sobrescrever nem incorporar esse conteúdo indiscriminadamente.

Use os procedimentos de build do repositório: ambiente MSVC via `vcvars64.bat` na mesma chamada do processo e configuração Emscripten documentada para os presets Web. Não adivinhe comandos ou flags para contornar erro de ambiente. Respeite o limite de tentativas de `AGENTS.md`. Para DNA, planeje regeneração dos geradores/artefatos e rebuild limpo dos produtos afetados; não confie somente no incremental. Não editar arquivos gerados.

## Prioridades e estimativas

Estimativas em dias de trabalho de um desenvolvedor familiarizado com o projeto; não são compromissos de prazo. Builds completos, disponibilidade de aparelhos e testes do usuário podem ampliar o tempo decorrido. Os custos não devem ser somados mecanicamente: há validações compartilhadas.

| Ordem | Entrega | Decisão | Risco | Esforço estimado |
|---|---|---|---|---|
| M0 | Manifesto correto e pré-voo sem falsos resultados limpos | Fazer agora | Baixo a médio | 1–2 dias |
| M1 | Diagnósticos estruturados de shader/Python | Fazer agora | Médio | 3–5 dias |
| M2 | Corrigir cinco campos DNA e reativar checagem RNA | Fazer agora, em peça isolada | Médio; compatibilidade exige prova | 2–4 dias |
| M3 | Correções de filtros, baseline e perfil móvel | Fazer agora | Médio | 1–2 dias para medição; correções a dimensionar |
| M4 | Fusão seletiva e/ou bloom reduzido | Depois, se M3 justificar | Médio | 3–6 dias |
| M5 | Validar e habilitar 3D pelo SDL/Audaspace | Depois, se algum jogo precisar | Médio | 2–4 dias |
| M6 | Adaptar backend OpenAL ao Emscripten | Depois, se M5 for insuficiente | Alto | 7–12 dias |
| — | Backend Web Audio próprio | Descartar nesta rodada | Alto | 3–5 semanas |
| — | Portar NumPy para atender apenas `Sound.data()`/`buffer()` | Descartar nesta rodada | Alto | 2–4 semanas, com incerteza |
| R1/R2/R3 | ABI de constraints, persistência e erros de áudio | Triar agora; corrigir isoladamente conforme reprodução | Alto impacto potencial | Dimensionar após reprodução |

Sequência principal: M0 → M1 → M2 → M3. M4 depende das medições de M3; M5/M6 dependem do jogo. Fazer a triagem dos riscos R1–R3 antes de encerrar a rodada; uma falha reproduzida que aborte o runtime ou perca dados pode exigir reordenar as prioridades.

## M0 — Tornar confiáveis as informações de compatibilidade (implementado; validação Web pendente)

### Problemas encontrados

- `tools/web/make-runtime-manifest.py` ainda descreve áudio como desabilitado e mantém uma lista de módulos da engine que omite `aud` e o alias `bge`.
- No manifesto release inspecionado, isso provoca `WEB-PY-001` para imports suportados de `aud` e `bge`.
- Em `preflight.py`, `_check_webgl` verifica a presença de uma versão, mas pode aceitar WebGL 1, embora o runtime exija WebGL 2.
- No JavaScript gerado por `package-web.py`, `pfFiles` pode transformar falha de leitura do manifesto em uma coleção vazia, sem erro correspondente.

### Implementação

1. Corrigir a geração do manifesto para refletir o produto construído: áudio, módulos da engine e aliases efetivos. Evitar uma lista de capacidades otimista e independente da configuração.
2. Ajustar o consumidor somente onde necessário. Não liberar imports indiscriminadamente para compensar manifesto incorreto.
3. Exigir WebGL 2 e registrar falha de aquisição de contexto, leitura do manifesto, timeout e runtime abortado.
4. Distinguir sucesso, falha e execução incompleta. Relatório sem erros, mas sem inicialização concluída, não pode significar aprovação.
5. Planejar o vínculo entre relatório, pacote/runtime e execução; concretizá-lo no contrato de M1 para impedir importação silenciosa de relatório de outro pacote.

Arquivos principais: `tools/web/make-runtime-manifest.py`, `tools/web/package-web.py`, `source/release/scripts/modules/range_web/{runtime.py,rules_python.py,preflight.py}`. Procurar os consumidores e testes existentes antes de ampliar o formato.

### Aceite

- `import Range`, `import bge` e `import aud` passam com o runtime que os suporta; módulo realmente ausente continua diagnosticado.
- WebGL 1, contexto indisponível, manifesto ausente/inválido, abort e timeout produzem falha ou estado incompleto explícito.
- Relatório válido continua importável pelo fluxo existente.
- Ampliar testes pertinentes em `tools/tests/web_profile/`, especialmente `test_runtime.py`, `test_range_web.py`, `test_preflight.py` e `test_preflight_run.py`; executar o fluxo real de exportação/pré-voo.

## M1 — Diagnósticos estruturados de shader e Python (parcial: shader comum)

### Decisão de arquitetura

O parsing heurístico principal está no JavaScript gerado por `tools/web/package-web.py`, em `pfLine`/`pfBuild`. `preflight.py` consome o relatório; `rules_python.py` analisa AST; `runtime.py` trata identificação/manifesto do runtime. Não tentar resolver o problema apenas trocando regex nesses módulos Python.

Criar uma ponte mínima de eventos C/C++ → JavaScript. Preferência: callback `Module.onDiagnostic` com objeto estruturado. Uma linha prefixada, por exemplo `RANGE_DIAG_V1 ` seguida de JSON, pode ser transporte alternativo/fallback. Centralizar serialização e escapar corretamente strings; não montar JSON por concatenação de mensagens arbitrárias.

Definir primeiro o contrato e os leitores, depois instrumentar produtores, em peças revisáveis:

1. Envelope versionado com identidade do pacote/runtime, identificador de execução, estado de inicialização, término/timeout e cobertura observada.
2. Evento com categoria, severidade, mensagem, origem e identificador. Shader: operação `compile`/`link`, estágio quando aplicável, programa/variante, material/world/filtro quando conhecido e log completo. Python: tipo de exceção, mensagem, traceback, arquivo/linha e contexto disponível de objeto/componente/controller.
3. Usar origem desconhecida explicitamente quando não houver informação; não deduzir material a partir de texto ambíguo. Link não deve receber artificialmente um estágio de compilação.
4. Manter leitura do relatório v1 e suporte a runtimes antigos. Marcar diagnósticos extraídos por heurística como tal. Quando houver evento estruturado correspondente, evitar duplicação com stdout/stderr.
5. Limitar crescimento em memória: contar repetições e preservar amostras úteis, sem juntar erros de objetos/materiais diferentes apenas porque a mensagem coincide. Indicar truncamento quando necessário.

### Produtores e arquivos

| Área | Arquivos/funções a revisar | Alteração esperada |
|---|---|---|
| GLSL comum | `source/source/blender/gpu/intern/gpu_shader.c`: `shader_print_errors`, `GPU_shader_create_ex` | Distinguir compilação de vertex/fragment/geometry e link; emitir evento na falha real |
| Proveniência | `gpu_codegen.c`: `GPU_generate_pass`; `gpu_material.c`: `gpu_material_construct_end` | Aproveitar nome hoje descartado por `UNUSED(name)` e propagar identidade sem depender do tempo de vida de ponteiro temporário |
| Shaders da engine/filtros | `source/source/gameengine/Rasterizer/RAS_Shader.cpp`: `LinkProgram`; `RAS_2DFilter.cpp`: `LinkProgram` | Identificar programa e filtro; preservar APIs desktop |
| Caminhos especiais | `RAS_ParticleShaderCache.cpp`, `RAS_TransformFeedbackShader.cpp` | Cobrir chamadas diretas de compilação/link ou declarar cobertura ausente |
| Controllers | `source/source/gameengine/GameLogic/SCA_PythonController.cpp`: `ErrorPrint` | Capturar exceção antes de impressão/limpeza, preservando referência e semântica |
| Componentes/callbacks | `source/source/gameengine/Ketsji/KX_PythonComponent.cpp`: `Awake`, `Start`, `Update`, `Dispose`; `Expressions/intern/PythonCallBack.cpp` e demais chamadas de `PyErr_Print` | Reutilizar helper seguro e incluir contexto disponível |
| Coleta e leitura | `tools/web/package-web.py`; `source/release/scripts/modules/range_web/preflight.py` e consumidores | Receber eventos, exportar/importar versão nova e manter compatibilidade |

Na captura Python, revisar `PyErr_Fetch`/normalização/restauração ou mecanismo equivalente compatível com o Python embarcado. A coleta não pode consumir a exceção antes do log normal, vazar referências nem disparar uma segunda exceção que esconda a primeira. O hook JS também não pode interromper o runtime quando o coletor estiver ausente ou falhar.

### Aceite

- Injetar falhas distintas em vertex, fragment e link; confirmar estágio/operação e origem de material e filtro.
- Injetar `ImportError`, `SyntaxError` e exceção em controller, componente e callback.
- Testar aspas, quebras de linha, Unicode, logs longos e erros repetidos em objetos diferentes.
- Exportar, importar e exibir o relatório no editor; testar versão antiga, nova e versão desconhecida.
- Rodar sem pré-voo habilitado e conferir funcionamento/logs normais e ausência de custo por frame desnecessário.
- Registrar que o pré-voo cobre apenas os caminhos executados; cena não visitada e shader não compilado continuam fora da evidência.

## M2 — Resolver DNA/RNA sem alterar o layout legado

### Inventário inicial

A inspeção dos setters automáticos gerados encontrou cinco campos físicos e sete propriedades RNA afetadas. Repetir a auditoria com os arquivos gerados da revisão atual; ela não prova automaticamente a correção de setters manuais.

| Campo DNA atualmente `char` | Propriedade RNA | Faixa publicada | Arquivos |
|---|---|---|---|
| `ImageUser.fie_ima` | `ImageUser.fields_per_frame` | 1–200 | `DNA_image_types.h`, `rna_image.c` |
| `Material.seed1` | `MaterialHalo.seed` | 0–255 | `DNA_material_types.h`, `rna_material.c` |
| `Material.seed2` | `MaterialHalo.flare_seed` | 0–255 | `DNA_material_types.h`, `rna_material.c` |
| `ToolSettings.skgen_subdivision_number` | `ToolSettings.etch_subdivision_number` | 1–255 | `DNA_scene_types.h`, `rna_scene.c` |
| `ThemeSpace.handle_vertex_size` | `ThemeGraphEditor`, `ThemeImageEditor` e `ThemeClipEditor`: `handle_vertex_size` | 0–255 | `DNA_userdef_types.h`, `rna_userdef.c` |

Os headers ficam em `source/source/blender/makesdna/`; as definições RNA, em `source/source/blender/makesrna/intern/`.

### Implementação proposta, sujeita à prova de compatibilidade

1. Corrigir o lado DNA para `unsigned char` literal somente nesses campos. Manter tamanho de um byte e faixas RNA. Separar declarações agrupadas para não mudar campos vizinhos, como `ImageUser.cycl`.
2. Não reduzir hardmax a 127 apenas para satisfazer o compilador. Não ampliar campos para `short`/`int`. Não aplicar alteração global de signedness.
3. Verificar `source/source/blender/makesdna/intern/makesdna.c`: o parser atual descarta o qualificador `unsigned`, preservando a identificação SDNA como `char`. Não substituir por alias `uchar` sem nova análise, pois pode alterar a identificação serializada.
4. Comparar SDNA gerado, tamanhos e offsets antes/depois. Compatibilidade esperada é preservação dos bytes/layout; valores acima de 127 passarão a ser interpretados como não negativos. Não prometer reprodução de comportamento negativo anterior.
5. Revisar consumidores e conversões: `editors/interface/resources.c::UI_ThemeGetColorPtr`, `blenloader/intern/versioning_legacy.c`, cálculo de frames em `blenkernel/intern/image.c`, uso de seeds em `convertblender.c`/`rendercore.c` e subdivisão em `editarmature_generate.c`. Adaptar ponteiros/casts específicos e procurar sentinelas negativas antes de alterar.
6. Regenerar makesdna/makesrna e revisar todos os asserts emitidos por `makesrna.c::rna_clamp_value_range_check`, usando tipos C reais. SDNA sozinho oculta `unsigned`; isso produziu falsos positivos em campos Freestyle durante a análise.
7. Remover apenas a exclusão de Emscripten em `rna_internal.h` e manter o restante das condições de suporte da checagem. Resolver eventual campo adicional individualmente.

### Aceite

- SDNA, tamanhos e offsets preservados, com evidência comparável antes/depois.
- Builds limpos do editor/runtime nativos e de ambos os presets Web, com a checagem ativa onde suportada.
- Carregar arquivos legados e testar roundtrip pelos valores válidos nas fronteiras 0/1/127/128/200/255, conforme cada propriedade.
- Incluir `userpref.blend` para os três temas, sequência de imagens, seeds de halo/flare e subdivisão de armature. Conferir animação de propriedade quando aplicável.
- Testar também leituras inválidas/limites via RNA e documentar o comportamento. Não declarar compatibilidade somente porque compilou.

## M3 — Medir filtros e corrigir problemas de base

### Baseline

Em `KX_2DFilterManager.cpp`, bloom cria oito passes; SSR, dois; light scatter, dois. Com SSAO, FXAA e tonemap, são quinze passes configuráveis. Isso não significa que todos estejam ativos em toda cena; contar os passes efetivamente executados.

Revisar `EnsureBloomFilters`, criação de SSR/light scatter, `RAS_2DFilterManager::RenderFilters`, `RAS_2DFilter::Render` e `RAS_2DFilterOffScreen::Update`.

Antes de otimizar:

1. Corrigir/verificar a colisão entre `reservedPassIndex = 17`, LensFlare no índice 17 e filtro customizado de índice zero. Atualizar de forma consistente adicionar, consultar e remover filtros; testar API Python existente.
2. Verificar seleção do último filtro quando há filtros desativados e blit final evitável. Alterar somente após confirmar o fluxo de buffers.
3. Verificar resize dos offscreens built-in criados com dimensões fixas/flags zero: redimensionamento do canvas, fullscreen e mudança de escala não podem deixar buffers incoerentes.
4. Corrigir a interpretação de GPU timer indisponível. `RAS_OpenGLQuery.cpp` desabilita consultas temporais em Emscripten e pode retornar zero; `KX_KetsjiEngine::UpdateDynamicResolution` não pode tratá-lo como GPU instantânea e subir a resolução continuamente.

Reutilizar a medição CPU de filtros existente em `KX_RenderPipeline`. Tempo CPU de submissão não equivale a tempo GPU. Se necessário, integrar `EXT_disjoint_timer_query_webgl2` por detecção de capacidade, leitura assíncrona e descarte de amostras disjoint; não bloquear esperando resultado e manter caminho funcional sem a extensão.

### Perfil móvel e aceite

- Medir jogo real em desktop e celular físico, registrando aparelho, navegador, resolução, escala, cena, filtros ativos e aquecimento. Coletar tempo de frame p50/p95, número de passes e tamanho/formato dos offscreens.
- Como hipótese inicial para um perfil de 30 fps, avaliar p95 próximo ou abaixo de 33,3 ms, ajustando a meta ao jogo. Comparar trechos reproduzíveis e mais de uma execução, sem inferir ganho de uma captura isolada.
- Propor perfil explícito: preservar tonemap; avaliar FXAA; desligar primeiro SSR, light scatter e SSAO; bloom desligado ou reduzido. Avaliar escala 0,75 somente com aceitação visual. Não desabilitar efeito necessário à jogabilidade silenciosamente.
- Validar no jogo real resize/fullscreen, ativação/desativação, transparência, filtros customizados, MRT e transições de cena.
- Aceite visual pelo usuário, conforme `AGENTS.md`; screenshot automatizado não substitui esse aceite.

Saída de M3: tabela medida, correções isoladas validadas e decisão fundamentada de executar ou adiar M4.

## M4 — Otimização seletiva, condicionada ao resultado de M3

Implementar uma alternativa por vez e comparar com o baseline:

1. **FXAA seguido de tonemap:** candidato a fusão se adjacentes e compatíveis. Aplicar tonemap após o cálculo FXAA, preservando ordem. A remoção do intermediário pode mudar quantização/clamp; validar aparência e ganho.
2. **Operações locais por pixel:** grayscale/sepia/invert podem ser compostas se a sequência for conhecida, preservando alpha e ordem. Não tentar interpretar/fundir shaders customizados arbitrários.
3. **Bloom móvel:** avaliar uma única escala, com extração, blur horizontal, blur vertical e composição: quatro passes em vez de oito. Deve ser opção de qualidade explícita, não substituição silenciosa do resultado existente.

Não fundir ingenuamente blur separável H/V: com onze taps em cada direção, a combinação direta pode trocar cerca de 22 amostras por 121. Não fundir SSR, SSAO ou scatter só por proximidade na lista; possuem dependências e vizinhanças distintas.

Arquivos: managers e filtros de M3, GLSL correspondente em `source/source/gameengine/Rasterizer/`, geração/registro dos shaders. Localizar os nomes efetivos antes de editar. Em `RAS_2DFilter::LinkProgram`, revisar a classificação Web de shaders com uma saída: há comparação explícita de fontes para tratamento de draw buffers. Shader novo não pode quebrar MRT; não classificar todo custom shader como saída única.

Aceite: build de shaders, compilação GLSL real no navegador, comparação visual no jogo e ganho repetível de tempo de frame/custo GPU quando medível. Se não houver ganho relevante ou houver regressão visual incompatível com o perfil, não manter a complexidade.

## M5 — Primeiro validar o áudio 3D já existente

Condição de entrada: um jogo precisa de posicionamento, distância, cone ou Doppler; registrar quais propriedades são necessárias e uma cena reproduzível.

O caminho SDL usa Audaspace `SoftwareDevice`, que já implementa interfaces 3D e cálculo espacial. `SoftwareDevice::SoftwareHandle::update` tem caminho especial para fontes mono; fonte estéreo não é um teste adequado para provar ausência de espacialização. Web Audio/OpenAL e NumPy não são pré-requisitos para avaliar esse caminho.

Arquivos/funções:

- `source/extern/audaspace/src/devices/SoftwareDevice.cpp`: `SoftwareHandle::update`.
- `source/source/gameengine/Launcher/LA_Launcher.cpp`: configuração global de áudio 3D desabilitada no Web por `if (false)`.
- `source/extern/audaspace/bindings/C/AUD_Device.cpp`: setters 3D que fazem cast para `I3DDevice` e usam o resultado sem validação.
- `source/source/gameengine/Ketsji/KX_SoundActuator.cpp` e `KX_Speaker.cpp`: listener, posição relativa, câmera e atualizações.

Substituir dependência de índice numérico do dispositivo por capacidade/interface validada, protegendo dispositivo nulo/sem 3D. Só então habilitar as configurações 3D pertinentes para SDL. Preservar o dispositivo compartilhado, volumes e comportamento atual do módulo `aud`.

Aceite com fones e fontes mono: esquerda/direita, distância, giro do listener, cone, Doppler, múltiplas vozes, loop/seek, troca de cena e pausa/retomada. Usar estéreo como controle. Repetir no navegador móvel, após gesto de desbloqueio de áudio e após background/foreground. Registrar resultado audível, não apenas ausência de crash.

Se atender ao jogo, encerrar a frente 3D sem iniciar M6.

## M6 — OpenAL somente se houver lacuna concreta

O Emscripten oferece implementação OpenAL 1.1 sobre Web Audio vinculada com `-lopenal`; não pressupor uma flag `USE_OPENAL` nem portar OpenAL Soft por padrão. Detectar extensões; não prometer EFX apenas por habilitar OpenAL.

O backend Audaspace em `source/extern/audaspace/plugins/openal/OpenALDevice.cpp` usa thread, sleeps e joins em streaming (`start`, `updateStreams`, destrutor). A adaptação exige projetar atualização cooperativa limitada pelo loop Web e revisar buffers, pausa, finalização e underruns. Não é apenas mudar CMake.

Revisar seleção do dispositivo, CMake/configuração Web, lifecycle e integração com `aud`. Começar por prova pequena de playback/streaming; depois validar os requisitos 3D de M5, uso de CPU e estabilidade em celular. Preservar uma rota de retorno ao backend atual se a alternativa não trouxer benefício.

NumPy: `source/extern/audaspace/bindings/python/PySound.cpp` protege `Sound.data()`/`buffer()` e `import_array` no Web. NumPy em Wasm é possível, mas pacotes de Pyodide não são automaticamente compatíveis com o CPython/ABI/toolchain deste runtime. Não trocar silenciosamente retorno ndarray por memoryview. Se aparecer demanda real por acesso a amostras, estudar uma API adicional baseada em buffer antes de assumir o custo do port de NumPy.

Referências técnicas para reconferência durante execução: [áudio no Emscripten](https://emscripten.org/docs/porting/Audio.html), [Pyodide](https://pyodide.org/en/stable/), [ABI do Pyodide](https://pyodide.org/en/stable/development/abi.html) e [GPU timer WebGL 2](https://registry.khronos.org/webgl/extensions/EXT_disjoint_timer_query_webgl2/).

## Riscos adicionais: tarefas separadas

### R1 — ABI de funções Python de constraints

Em `source/source/gameengine/Ketsji/KX_PyConstraintBinding.cpp`, conferir callbacks como `gPySetGravity` e `gPySetNumIterations`: há assinaturas de três argumentos registradas com `METH_VARARGS`, que entrega dois. Em Wasm, divergência de assinatura de função é especialmente problemática.

Inventariar os registros, reproduzir as chamadas e alinhar assinatura e flags preservando a API pública. Não adicionar keywords indiscriminadamente só para acomodar a assinatura. Fazer correção isolada, com teste de argumentos válidos/inválidos e execução Web e nativa.

### R2 — Isolamento e confirmação de saves

Em `source/source/gameengine/Ketsji/KX_PythonInit.cpp`, revisar `pathGamePythonConfig`/`saveGamePythonConfig`; em `source/source/blenderplayer/web_idbfs_prerun.js`, montagem e sincronização IDBFS.

O caminho padrão `/saves/game.save` e o armazenamento por origem podem causar colisão entre jogos hospedados na mesma origem. A gravação no filesystem em memória também antecede a conclusão assíncrona de `FS.syncfs`; erro pode ficar apenas no console.

Propor identidade estável de jogo, independente de versão do build, e migração do caminho legado. Se a origem tiver múltiplos jogos e o dono do save antigo for ambíguo, não copiar/apagar automaticamente para todos. Definir contrato de conclusão/erro da persistência e impedir que leitura inicial falha seguida de save sobrescreva silenciosamente estado recuperável.

Validar dois jogos na mesma origem, atualização do mesmo jogo, reload, erro de sincronização, armazenamento indisponível e fechamento logo após salvar. Não prometer durabilidade antes da confirmação de sync nem depender só de evento de fechamento da aba. Preservar API antiga quando possível, acrescentando confirmação explícita de forma compatível.

### R3 — Falhas de áudio que abortam o Wasm

O histórico contém aborts por exceções C++ de áudio. Testar arquivos inválidos, codec indisponível e operações inválidas de `aud`; localizar a fronteira que deve converter erro em exceção Python/diagnóstico. Não habilitar exceções globalmente sem avaliar configuração, tamanho e comportamento. Corrigir com caso reproduzível e validar que a cena continua operando após erro tratável.

Os outros riscos adicionais — manifesto incorreto, pré-voo incompleto tratado como sucesso, colisão de índices de filtros e GPU timer zero — já estão incorporados em M0/M1/M3.

## Entrega e acompanhamento por marco

Ao terminar cada peça, apresentar:

- Problema e comportamento resultante, arquivos alterados e escopo do diff.
- Comandos de build/teste realmente executados e resultado; navegador/aparelho/cena quando aplicável.
- Evidências de compatibilidade e regressão pertinentes, sem generalizar além do que foi executado.
- Pendências que dependem de jogo/aparelho/aceite do usuário e próxima peça proposta.

Atualizar documentação conforme `AGENTS.md`: estado aberto no roadmap, decisão vigente no relatório e detalhes de implementação/validação no changelog. Não registrar como concluído um efeito visual ou audível ainda não conferido. Manter este plano marcado por marcos durante a execução e remover o handoff quando terminado, conforme as regras documentais do repositório.

Critério de encerramento desta rodada: M0–M3 implementados e validados, ou bloqueios explicitamente documentados; R1–R3 triados com decisão registrada; M4–M6 classificados com base em medição/requisito, sem apresentar adiamento como implementação concluída.
