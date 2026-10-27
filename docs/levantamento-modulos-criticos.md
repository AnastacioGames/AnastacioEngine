# Levantamento dos módulos críticos para análise de código

Data: 2026-10-26. Escopo: runtime, suas integrações com o editor e plataformas.

Este levantamento organiza a próxima análise por responsabilidade e alcance de uma falha. A prioridade
é uma avaliação arquitetural; não é um ranking de gargalos medidos. Foram conferidos os índices, mapas,
documentação vigente e trechos dos caminhos de simulação, componentes, culling, física e mensagens.
Não houve alteração de comportamento, build, benchmark ou execução de jogo nesta etapa.

Rodada posterior: a [revisão integral de KX_Scene](revisao-kx-scene.md) aprofunda a primeira frente,
com compreensão por trecho e quatro defeitos reproduzidos em cena isolada.
A [revisão da frente 8](revisao-dados-editor.md) começa a análise de baixo para cima: versioning e
leitura/gravação dos dados da engine.

## Andamento consolidado — 2026-10-26

Estado conferido nos relatórios e commits locais. A coluna de responsável identifica quem registrou
o trabalho; não presume que o outro agente esteja executando agora. Uma rodada de leitura concluída
não encerra a frente enquanto houver correções ou validações pendentes.

| Frente | Trabalho registrado | Situação e validação | Próximo passo |
|---|---|---|---|
| **1. Cenas e objetos — Codex** | Leitura integral de `KX_Scene`, núcleo e bindings de `KX_GameObject`; helper de argumentos Python e seus 25 usos conferidos. | Quatro defeitos de cena reproduzidos, ainda sem correção. OBJ-01..03, PY-01..08 e helper corrigidos (`06a10024`); editor/player compilados, CTest 15/15, 82 verificações do parser e sete cenários de regressão passaram. | Corrigir os quatro casos de cena; resolver contratos de réplica e validar os riscos restantes de referências, LOD, partículas e LibLoad. |
| **2. Loop, SceneGraph e animação — Codex, frente atual** | Três rodadas: nós/filas/parenting/pipeline; relógio/acumulador/suspensão; input/joystick e animação durante catch-up. Conferida aplicação adiada de taxas durante o lote. | Quinze achados: SG-01..06, CLK-01..05, INP-01..03 e ANI-01. INP-01/02/03, ANI-01, SG-01..06 corrigidos (SG-04/05 ainda sem build completo). Regressões de input passaram; quatro cenas de animação no player passaram com ação, osso/filho, eventos e restrições de taxa. Editor/player compilados e editor validado em background. Restam CLK-01..05. | **Build completo + regressões de SG-04/05; depois CLK-01** e seguir SG/CLK por partes. Joystick físico, skinning/ImageRender com render, auditoria parada e custo de CPU pendentes; limites no relatório. |
| **3. Renderização e materiais** | Roteiro e arquivos de entrada mapeados. Há melhorias de render no histórico, mas elas não equivalem à revisão desta frente. | Sem relatório específico desta revisão registrado nesta lista. | Iniciar leitura do pipeline de render, sombras, buckets e materiais, apoiada em perfil CPU/GPU. |
| **4. Física — Claude** | Duas rodadas: ciclo de vida de constraints e veículos; personagem e callbacks de colisão que suspendem/removem objetos ([revisão](revisao-fisica.md)). | FIS-01..05 corrigidos: constraint e personagem apagados derrubavam o player, `constraint_id` era pedaço de ponteiro, corpo suspenso removido deixava constraint viva, contato lido de manifold liberado. 14 casos `--server` passaram. | Soft body e tempo de física com muitos corpos; decidir o lado de `localPointA` nos callbacks. |
| **5. Conversão e carregamento — Claude** | Primeira rodada: ciclo LibLoad → merge assíncrono → LibFree → remoção de cena ([revisão](revisao-conversao-libload.md)). | LIB-01..03 corrigidos: LibFree duplo corrompia o heap, LibFree durante carga assíncrona era descartado, remover a cena de destino deixava merge em cena liberada. 4 casos `--server` passaram. | Memória estável em 150 ciclos e `.cooked` conferido (hash + validação de limites). Resta medir picos do merge com janela. |
| **6. Lógica e Python — Claude; bindings de objetos por Codex** | Claude revisou componentes e mensagens; confirmou que sensores, controladores e atuadores não foram lidos individualmente. Codex revisou os bindings de objetos e o helper citados na frente 1. | LOG-01 corrigido em `fc55dc8c`: broadcast sem destinatário não é duplicado. Claude confirmou teste em segundo plano com os números esperados. | Claude segue para a frente 5; fica pendente a leitura individual de sensores, controladores e atuadores da frente 6. |
| **7. Multiplayer — Claude** | Relatório cobre sessão, mensagens, replicação, RPC, predição, compensação de lag e transportes; Steam e cliente WebSocket tiveram escopo limitado. | NET-01..04 corrigidos (`7ff15741`, `7115be4c`); `net_tests` 121/121. Claude confirmou recompilação posterior do editor e player, atualizando a pendência de relink do relatório. | Testar host/cliente com janela: saída por Quit/kick, entrada com o mesmo ID e devolução dos objetos de cena ao servidor. Teste com janela depende de pedido do usuário. |
| **8. Dados, editor e plataformas — Claude; segunda revisão por Codex** | Versioning, dados de cutscene, exportadores, RNA, UI e encerramento revisados. Codex conferiu os oito commits informados e registrou CR-01..04. | Correções iniciais commitadas; CR-01..04 corrigidos por Claude em `f4ba9cb0`. Build editor/player e validações em background registrados; Web 136/136. Isso não substitui validação visual e em outras plataformas. | Definir o comportamento de `overwrite_lib` no export nativo (EXP-03), pendência ainda aberta no roadmap. |

Relatórios para conferir os detalhes e limites:

- Frente 1: [cena](revisao-kx-scene.md), [núcleo do objeto](revisao-kx-gameobject.md),
  [bindings](revisao-kx-gameobject-python.md) e [parser](revisao-parser-python.md).
- Frente 2: [SceneGraph, loop e relógio](revisao-scenegraph-loop.md).
- Frente 6: [lógica, componentes e Python](revisao-logica-python.md).
- Frente 7: [multiplayer](revisao-multiplayer.md).
- Frente 8: [dados, editor e plataformas](revisao-dados-editor.md).

**Retomada do Codex:** continuar a frente 2 no ponto indicado acima, sem iniciar outra frente
antes de registrar o resultado dessa leitura. As correções abertas da frente 1 continuam pendentes.
**Retomada do Claude:** frente 5, conforme atualização encaminhada pelo usuário. Claude informou
concluídas suas rodadas nas frentes 8, 7 e 6; permanecem as pendências específicas registradas acima.
Este quadro é o ponto de coordenação entre agentes; cada um deve atualizar sua linha com evidências,
pendências e próximo passo, preservando a distinção entre análise, correção e validação.

## Ordem de análise

| Ordem | Frente | Impacto principal | Motivo para analisar |
|---|---|---|---|
| 1 | Cenas e objetos (Ketsji) | Estabilidade, memória, criação e remoção | Concentra referências e registros usados pelos outros sistemas |
| 2 | Loop e SceneGraph | CPU, sincronização e ordem do frame | Mudanças propagam para lógica, física, animação e render |
| 3 | Renderização e materiais | GPU, CPU de desenho e compatibilidade visual | Cruza Ketsji, Rasterizer, GPU do Blender e GLSL |
| 4 | Física Bullet | CPU, contatos, veículos e personagens | Concentra simulação e sincronização de corpos |
| 5 | Conversão e carregamento | Tempo de carga, memória e LibLoad | Conecta dados persistidos a quase todos os módulos do runtime |
| 6 | Lógica e Python | CPU de gameplay, callbacks e compatibilidade | Código do jogo pode criar/remover objetos durante a atualização |
| 7 | Multiplayer | Estado compartilhado, tick e ciclo de sessão | Liga transporte e replicação à simulação; sobe de prioridade em jogos online |
| 8 | Dados, editor e exportação | Compatibilidade de projetos e plataformas | Uma propriedade atravessa DNA, RNA, UI, conversor e empacotamento |

Para investigar FPS, começar pelo perfil CPU/GPU e escolher entre as frentes 2, 3, 4 e 6.
Para crashes em troca de cena/LibLoad, começar por 1 e 5. Para falha ao abrir projetos, incluir 8.

## Tamanho observado

Contagem recursiva de arquivos `.c`, `.cpp`, `.h` e `.glsl` em `source/source/gameengine/`,
incluindo comentários, linhas vazias e testes presentes nessas pastas. Tamanho orienta o esforço de
leitura; não comprova complexidade nem custo de execução. GPU do Blender fica fora desta tabela.

| Pasta | Arquivos | Linhas |
|---|---:|---:|
| Ketsji | 271 | 94.923 |
| Rasterizer | 133 | 26.218 |
| Physics | 22 | 11.160 |
| Converter | 43 | 15.362 |
| SceneGraph | 18 | 2.463 |
| GameLogic | 79 | 12.142 |
| Expressions | 39 | 7.225 |
| Network | 59 | 17.417 |
| Launcher | 8 | 2.185 |
| Device | 10 | 1.933 |
| VideoTexture | 36 | 12.596 |

## 1. Cenas e objetos

**Entrada:** [KX_Scene.cpp](../source/source/gameengine/Ketsji/KX_Scene.cpp),
[KX_GameObject.cpp](../source/source/gameengine/Ketsji/KX_GameObject.cpp).
Navegação: [mapa de cena](code-map-gameengine.md) e [mapa do objeto](code-map-kx-gameobject.md).

- Seguir criação → registro nas listas → réplica → suspensão → remoção → liberação de referências.
- Comparar `AddNodeReplicaObject`, `AddReplicaObject`, `NewRemoveObject`, remoção adiada e merge de cenas.
- Inventariar os donos de objetos e registros secundários: componentes, animação, sombras, partículas,
  física e callbacks. Verificar se todas as saídas desfazem os registros correspondentes.
- Validação proposta: repetir spawn/despawn, réplicas, parenting e troca de cenas; acompanhar contagem
  de objetos, registros e memória depois do aquecimento.

**Estrutura atual:** o núcleo de `KX_GameObject.cpp` tem 2.731 linhas; os bindings já estão separados em
`KX_GameObject_Python.cpp` (2.871) e `KX_GameObject_PyMethods.cpp` (1.857). Cutscene/Trace Rail da cena
já ficam em `KX_SceneCutscene.cpp`. A análise deve respeitar essas extrações existentes.

## 2. Loop, transformações e animação

Três rodadas registradas: [SceneGraph, relógio, input e animação durante catch-up](revisao-scenegraph-loop.md).
Quinze achados com evidências e limites documentados: INP-01/02/03 e ANI-01 corrigidos, com
regressões, build completo e execução editor/player em segundo plano passando. Outros 11 achados
SG/CLK sem correção; joystick físico, skinning/ImageRender com render e medições ainda pendentes.
Integração dos casos ainda pendente; a frente não está encerrada.

**Entrada:** [KX_KetsjiEngine.cpp](../source/source/gameengine/Ketsji/KX_KetsjiEngine.cpp),
[KX_SimulationPipeline.cpp](../source/source/gameengine/Ketsji/KX_SimulationPipeline.cpp),
[SG_Node.cpp](../source/source/gameengine/SceneGraph/SG_Node.cpp).

- Reconstituir a ordem real a partir de `NextFrame` e `KX_SimulationPipeline::Update`.
  O tick de rede envolve a atualização; dentro de cada cena há atividade, animação, cutscene,
  lógica, componentes/atuadores, física e serviços finais.
- Há três pontos de `UpdateParents` na simulação: após controladores, após atuadores e após física.
  São fronteiras de sincronização; sua presença não comprova trabalho redundante.
- Seguir `SetModified`, agendamento de nós e propagação para filhos; verificar quanto trabalho ocorre
  com a cena parada, objetos suspensos e corpos dormindo.
- Conferir animação de pose versus deformação: o servidor mantém poses e evita deformação de malhas.
- Validação proposta: detector de trabalho repetido em cena parada, hierarquia móvel e cena suspensa;
  comparar categorias de tempo e número de atualizações, preservando a ordem do frame.

Render, simulação, sombras, agendamento de cenas e debug já têm classes extraídas. A eventual extração
do relógio continua uma decisão de maior risco; consultar o [plano Ketsji](ketsji-engine-modernization-plan.md).

## 3. Renderização, sombras e materiais

**Entrada:** [KX_RenderPipeline.cpp](../source/source/gameengine/Ketsji/KX_RenderPipeline.cpp),
[KX_ShadowRenderer.cpp](../source/source/gameengine/Ketsji/KX_ShadowRenderer.cpp),
[RAS_BucketManager.cpp](../source/source/gameengine/Rasterizer/RAS_BucketManager.cpp).
Para material/GLSL, começar pelo [mapa GPU](code-map-gpu.md) e pelo [índice rendering](local-knowledge/index-rendering.md).

- Seguir visibilidade → LOD → buckets → binds de material → draw → pós-processamento.
- Separar custo por câmera, por passe de sombra, por material e por objeto; incluir transparência,
  instancing, static batch, cascatas e render-to-texture.
- `CalculateVisibleMeshes` ainda cria vetor local e reserva a capacidade da lista de renderização.
  Há também um snapshot próprio para culling de sombras; mapear seu escopo antes de propor outro cache.
- `RAS_OpenGLQuery` oferece `Available`, `ResultNoWait` e `Result`. Conferir os consumidores e o fallback
  de `GL_QUERY_RESULT_NO_WAIT`; a existência de `Result` não comprova espera problemática no jogo.
- Validação proposta: medir ms de CPU/GPU, draw calls e passes com cena opaca, transparente e múltiplas
  câmeras. GLSL precisa compilar em runtime; aparência precisa ser conferida no jogo real.

## 4. Física

**Entrada:** [CcdPhysicsEnvironment.cpp](../source/source/gameengine/Physics/Bullet/CcdPhysicsEnvironment.cpp),
[CcdPhysicsController.cpp](../source/source/gameengine/Physics/Bullet/CcdPhysicsController.cpp).
Navegação: [mapa gameengine](code-map-gameengine.md) e [índice physics](local-knowledge/index-physics.md).

- Separar solver/contatos, callbacks de sensores, constraints, veículos, personagens e shapes.
- Seguir `ProceedDeltaTime`/`ProceedDeltaTimeCar` e a sincronização de motion states com o SceneGraph.
- Conferir remoção de corpos, sensores, veículos e constraints, principalmente após réplica e LibFree.
- `CcdPhysicsEnvironment.cpp` também contém `OcclusionBuffer`, `DbvtCullingCallback` e `CullingTest`:
  culling e oclusão estão junto da física porque usam a estrutura espacial Bullet. Isso é uma fronteira
  possível de organização, não autorização para reescrever o sistema.
- Validação proposta: corpos dormindo/ativos, pilhas, veículo, personagem, criação/remoção de constraints
  e comparação do tempo de física com quantidade de corpos e contatos.

## 5. Conversão, cooking e LibLoad

**Entrada:** [BL_BlenderDataConversion.cpp](../source/source/gameengine/Converter/BL_BlenderDataConversion.cpp),
[BL_Converter.cpp](../source/source/gameengine/Converter/BL_Converter.cpp),
[CcdCookedData.cpp](../source/source/gameengine/Physics/Bullet/CcdCookedData.cpp).

- Separar conversão de mesh/material, objetos, componentes, física e pós-conversão.
- Seguir `LinkBlendFile`, conversão assíncrona, filas de merge/reload e `FreeBlendFile` até a liberação.
- Conferir ownership entre `Main`, dados compartilhados, cena convertida, cache e tarefas pendentes.
- Comparar caminho cru e `.cooked`, invalidação e fallback, incluindo materiais novos via LibLoad.
- Validação proposta: carga fria/quente, arquivo sem cache, cache incompatível e repetição LibLoad/LibFree;
  medir `[Load]`, picos de frame e memória. O arquivo de conversão tem atualmente 4.057 linhas.

## 6. Lógica, componentes e API Python

**Entrada:** [SCA_LogicManager.cpp](../source/source/gameengine/GameLogic/SCA_LogicManager.cpp),
[KX_PythonComponentManager.cpp](../source/source/gameengine/Ketsji/KX_PythonComponentManager.cpp),
[KX_PythonInit.cpp](../source/source/gameengine/Ketsji/KX_PythonInit.cpp).
Navegação: [índice logic-scripting](local-knowledge/index-logic-scripting.md).

- Separar sensores/controladores/atuadores, componentes e bindings; `Expressions` fornece valores e
  a ponte de referências com Python. Conferir referências possuídas/emprestadas e callbacks de remoção.
- `RegisterObject` usa `push_back` sem guarda; há pelo menos dois pontos de chamada: réplica em
  `KX_Scene` e pós-conversão em `BL_PostConvertBlenderObjects`. Isso atualiza a informação antiga da
  auditoria, que citava apenas um. Não demonstra que o mesmo objeto percorra os dois caminhos.
- `UpdateComponents` copia o vetor de ponteiros antes de iterar para permitir alterações na coleção.
  Medir a cópia e analisar a validade dos objetos quando um componente remove outro durante o tick.
- Mensagens de Logic Bricks ficam em `Ketsji/KXNetwork`, separadas do multiplayer `Network`.
  `GetMessages` monta um vetor e consulta mapas com `operator[]`; medir consultas vazias e verificar
  o caso `to` vazio, no qual as referências ao receptor e ao broadcast apontam para o mesmo mapa.
- Validação proposta: um update por componente/tick, suspensão, criar/remover objetos em callback,
  reload de componentes e mensagens com/sem destinatário. Cobrir editor, Play e standalone.

## 7. Multiplayer

**Entrada:** [NET_Session.cpp](../source/source/gameengine/Network/NET_Session.cpp),
[NET_Replicator.cpp](../source/source/gameengine/Network/NET_Replicator.cpp),
[KX_NetworkManager.cpp](../source/source/gameengine/Ketsji/KX_NetworkManager.cpp).
Contrato: [plano](multiplayer-plan.md) e [protocolo](multiplayer-protocol.md).

- Seguir sessão → transporte → mensagens → réplica/RPC → aplicação ao mundo.
- Conferir identidade e destruição de réplicas, relevância, filas limitadas, desconexão, troca de cena,
  validação de pacotes e transição para passo fixo; tratar predição e compensação de lag separadamente.
- Validação proposta: começar pelos testes existentes em `Network/tests`, depois host/cliente,
  perda/latência simulada e reconexão. Usar o roadmap para distinguir cobertura existente de pendências.

## 8. Dados, editor e plataformas

**Entrada:** [guia de manutenção](maintenance-guide.md), [arquitetura](architecture.md),
[índice DNA](local-knowledge/index-dna-blend.md) e [perfil Web](web-profile-validation-plan.md).

- Rastrear UI → RNA → DNA/versioning → conversor → consumidor; conferir save/load de projetos antigos.
- Separar problema do editor, Play embutido, player, Web e exportador. Device/Launcher/GHOST entram na
  análise de input, janela, pausa e encerramento; VideoTexture/Audaspace entram quando houver vídeo/áudio.
- Android usa APK WebView sobre o runtime Web; não há uma frente de runtime NDK a inventariar.
- Validação proposta: ida e volta de arquivo, exportação, pacote extraído e execução nas plataformas
  afetadas. Mudanças de DNA têm exigências específicas de rebuild no AGENTS.md.

## Como transformar este levantamento em auditoria

Para cada frente, produzir uma ficha com: caminho e símbolo, fluxo que o alcança, contrato esperado,
evidência, hipótese de falha, reprodução, métrica e resultado. Classificar como observado no código,
suspeita ou defeito reproduzido. Não promover suspeita a bug nem prometer ganho sem medição.

Primeira rodada sugerida: ciclo de vida de cena/objeto e registros de componentes; depois transformações
em cena parada; em seguida perfil de render/física. Reaproveitar os instrumentos de
[performance](performance-audit.md), [trabalho repetido](auditoria-trabalho-repetido.md) e os testes existentes.
As suspeitas antigas precisam ser relidas no código atual: algumas já receberam testes sem reprodução.

Este documento é um roteiro de leitura e investigação. Não substitui os mapas de navegação, o roadmap
nem os resultados de auditorias específicas.
