# Modernização do núcleo Ketsji — plano mestre

## Objetivo

Modernizar aos poucos o núcleo de execução da AnastacioEngine
(`KX_KetsjiEngine.cpp`): menor, mais seguro, mensurável, previsível e rápido,
sem quebrar projetos existentes.

## Estado do documento

- Planos 1-11 feitos ou encerrados em 2026-09 (Plano 8 revisto em 2026-09-26 e
  2026-10-06). O histórico detalhado de cada unidade está em
  [changelog-arquivo.md](changelog-arquivo.md) e [changelog.md](changelog.md).
- Este arquivo guarda agora só o resumo do que foi feito e **tudo que ficou
  aberto, adiado ou com limite conhecido**.
- O [roadmap](roadmap.md) continua sendo a fonte do trabalho aberto.
- Antes de retomar qualquer item, reler o código e o estado do Git: os achados
  aqui são de 2026-09.

## Princípios e protocolo

1. Corrigir problemas comprovados antes de refatorar.
2. Medir antes e depois de toda otimização. Sem ganho medido, descartar.
3. Preservar comportamento antes de melhorar arquitetura.
4. Uma responsabilidade por vez; não misturar correção, refatoração e
   otimização no mesmo commit.
5. Editor, Play embutido e standalone em paridade.
6. Compatibilidade de arquivos e scripts Python faz parte do contrato.
7. Etapa só está concluída após build e validação aplicável.
8. Remover código desativado em vez de comentar; preservar comentários de
   contrato ou motivo.
9. Toda correção começa com reprodução ou teste, quando viável.

Cada unidade nova começa com um anúncio (plano, papel, arquivos lidos/escritos,
validação prevista, concorrência conhecida) e termina com resumo de
continuidade + `PONTO DE /compact`. Papéis: auditor (só leitura),
implementador (único escritor), verificador (revisão e build). Não escrever
nos arquivos do Vehicle System enquanto outra frente mexer neles.

## Planos feitos (resumo)

- **Plano 1A — correções comprovadas:** feito em 2026-09-05 (contador do CSM,
  `shadowCulling` separado de `maxphystep`, validação de taxas, projeção do Sol,
  cursor personalizado). Ver
  [changelog](changelog-arquivo.md#2026-09-05--ketsji-plano-1a-contador-csm).
- **Plano 1B — higiene do arquivo:** feito em 2026-09-05. Ver
  [changelog](changelog-arquivo.md#2026-09-05--ketsji-plano-1b-higiene-conservadora-do-arquivo).
- **Plano 2 — instrumentação:** 13 unidades em 2026-09-06 (categorias finas
  de tempo e contadores no Debug Mode). Ver
  [changelog](changelog-arquivo.md#2026-09-06--ketsji-plano-2-categoria-de-profiling-para-o-collision-depth-pass).
- **Plano 3 — testes:** 8 unidades em 2026-09-06 (relógio manual do
  `CM_Clock`, scripts de regressão de cenas, callbacks, câmeras e partículas,
  self-test do CSM). Ver seção própria abaixo.
- **Plano 4 — RAII:** 6 unidades em 2026-09-06 (guardas de offscreen, 2D
  filter, câmera temporária, framebuffer de sombra, texture renderer e
  `PopMatrix`). Ver
  [changelog](changelog-arquivo.md#2026-09-06--ketsji-plano-4-guarda-de-escopo-para-o-offscreen-de-collision-depth),
  [2D filter](changelog-arquivo.md#2026-09-06--ketsji-plano-4-guardas-de-escopo-em-ras_2dfilterrender),
  [câmera](changelog-arquivo.md#2026-09-06--ketsji-plano-4-guarda-de-camera-temporaria-em-rendershadowbuffers),
  [framebuffer](changelog-arquivo.md#2026-09-06--ketsji-plano-4-guardas-de-bindunbind-de-framebuffer-em-rendershadowbuffers),
  [texture renderer](changelog-arquivo.md#2026-09-06--ketsjirasterizer-plano-4-guardas-em-kx_texturerenderermanager-e-ras_rasterizer).
- **Plano 5 — sombras:** `KX_ShadowRenderer` extraído e otimizado em
  2026-09-06 (matrizes uma vez por luz, câmeras reusadas, cache de cascata,
  propriedade `Camera.csm_cache_max_stale_frames`).
- **Plano 6 — render:** `KX_RenderPipeline` extraído em 2026-09-06, com cache
  de culling por `(cullingcam, eye)`. Redução de buckets medida: nada seguro a
  ganhar sem mudar a arquitetura de buckets.
- **Plano 7 — simulação e cenas:** `KX_SimulationPipeline`,
  `KX_SceneScheduler` e `KX_DebugRenderer` extraídos em 2026-09-06, ordem
  preservada (3 `UpdateParents`, Replace → Remove → Add).
- **Plano 8 — passo fixo:** acumulador em `NextFrame()` atrás da opção
  `use_fixed_timestep` (2026-09-07); desligado em 2026-09-26 após revisão;
  corrigido e religado em 2026-10-06. Ver
  [changelog](changelog-arquivo.md#2026-09-07--ketsji-plano-8-introducao-do-acumulador-de-passo-fixo-atras-de-flag-desligada)
  e as entradas de 2026-09-26 e 2026-10-06.
- **Plano 9 — otimização por perfil:** em 2026-09-07: swap interval só quando
  muda, `DebugDrawWorld` só com debug ligado, `reserve()` no culling, log
  `[Plano9] drawcalls=...` atrás de `SHOW_RENDER_QUERIES`. Descartados após
  avaliar: buckets inalterados, reuso de culling entre passes, passes sem
  consumidor, mais instancing (~145-296 draw calls/frame no RolimaRacer) e
  paralelização (nenhuma etapa livre de Python/SceneGraph/Bullet/GL).
- **Plano 10 — limpeza e contrato:** em 2026-09-07: código morto removido;
  ordem do frame e ownership documentados em
  [architecture.md](architecture.md).
- **Plano 11 — `friend class`:** feito em 2026-09-07; `KX_KetsjiEngine.h` não
  declara mais `friend class`.

## Pendente, adiado ou com limite conhecido

### Plano 1A

- CSM: validação visual em jogo real do contador de estabilização ficou
  pendente.
- `maxPhysicsFrame`/`maxphystep` na API Python ficou deprecated, sem restaurar
  o limite de frames físicos. Decisão em aberto, só se surgir consumidor real.

### Plano 2 — Instrumentação granular e baseline

Encerrado por decisão do usuário em 2026-09-06. Adiado, não cancelado:

- contadores de casters por cascata, câmeras/viewports/probes renderizadas e
  corpos físicos ativos;
- aceite formal de baseline em ms/percentis;
- dividir `tc_physics`: os sub-passos vivem dentro de `CcdPhysicsEnvironment`;
  precisa de um plano de Física à parte (não aberto).

### Plano 3 — Testes e infraestrutura de segurança

Encerrado por decisão do usuário em 2026-09-06. Pendente, sem trabalho
iniciado (exige instrumentação C++ antes): regressão de sombras, filtros 2D,
render-to-texture e avaliação de ASan/UBSan. Habilitar gtest (`WITH_GTESTS`,
hoje `OFF`) foi adiado. O relógio manual do `CM_Clock` ainda não tem consumidor
(nem harness C++ nem binding Python). Detalhe a partir do
[changelog](changelog-arquivo.md#2026-09-06--ketsji-plano-3-relogio-controlavelfalso-para-testes-de-temporizacao).

### Plano 4

Sem novo candidato. Falta decidir entre varrer outras áreas do motor no mesmo
padrão ou dar o plano por fechado. `RAS_2DFilterOffScreen::Bind`/`Unbind` foi
reexaminado e não é candidato.

### Plano 5

- Falta teste em jogo real da tolerância `csm_cache_max_stale_frames = 2`:
  ver se reduz o tremor ao mover a câmera sem "pop" ao parar.
- Medir o custo real de GPU do cross-fade entre cascatas e do `csm_debug_tint`.
- O cache de cascata só ganha em cena sem caster dinâmico e com câmera parada.

### Plano 6

Teste em jogo real pendente da extração dos métodos (unidade 2) e do cache de
culling (unidade 3, foco em override culling camera e vários viewports).

### Plano 7 — requisitos que seguem valendo

- Preservar as três passagens de `UpdateParents()` e sua posição em relação a
  logic bricks, actuators e física.
- Manter a atualização de partículas no ponto atual até auditar seu contrato
  com visibilidade e câmera.
- `m_scenes` não muda durante o `Render()` só por ordem de chamada, não por
  proteção explícita. Callbacks `PRE_DRAW` só agendam mudanças de cena. Falta
  formalizar isso no `KX_SceneScheduler`.
- Testar pause, render desligado, cenas suspensas e trocas de cena agendadas.

### Auditoria de dados para snapshot (entre Planos 7 e 8)

Só o mapa de leituras foi feito (2026-09-06). Snapshot imutável ou render
thread **não iniciados**. Antes de começar, precisa estar demonstrado:

- testes de ciclo de vida dos Planos 3, 6 e 7;
- contrato de callbacks Python de desenho documentado e coberto;
- ownership de câmeras temporárias, offscreens e dados de cena;
- baseline de CPU, GPU, memória e latência (cenas simples, reais e pesadas);
- teste real no editor e no standalone (sombras, filtros, partículas, várias
  câmeras, troca de cenas);
- plano de falha, sincronização e encerramento de recursos gráficos.

Mapa de leituras do renderer:

| Leitura | Classe | Observação |
|---|---|---|
| `KX_RenderData` e filhos (montados em `GetRenderData()`) | Dado estável do frame | Já é cópia por valor a cada `Render()`; núcleo natural do snapshot. `KX_CameraRenderData` guarda `AddRef()` da câmera estéreo: decidir ownership do ponteiro. |
| `GetVisibleMeshes` (cache por `cullingcam`/`eye`) | Dado estável do frame | Válido só com as matrizes de câmera que o geraram; congelar junto. |
| Matrizes de câmera (`UpdateView`) | Estado gráfico mutável | Escreve no `KX_Camera` vivo; depende de ownership de câmera. |
| `RAS_Rasterizer`/`RAS_ICanvas` | Estado gráfico mutável | Fica no thread de render. |
| `CascadeMatrixCache` (mapa estático por ponteiro de luz) | Estado gráfico mutável | Best-effort (reuso de endereço = até 1 frame de cascata velha); cruzar thread exige mutex ou realocação. |
| Listas de casters em `ComputeCascadeShadowMatrices` | Dado estável (parcial) | AABBs só lidos, mas a lista vem do SceneGraph vivo. |
| `RAS_ILightObject` (buffers e binds de sombra) | Estado gráfico mutável | Recursos de GPU por luz. |
| Listas da cena (luzes, câmeras, partículas GPU, casters) | Dependência de SceneGraph | Sem estratégia de ownership/sincronização definida. |
| `RAS_ParticleBuffer::Draw` | Callback com efeito colateral | Simula fora, desenha aqui lendo `GetVisible()`; contrato de visibilidade com Override Culling não auditado. |
| `DebugDrawWorld`, `DrawDebugVehicles` | Dependência de Bullet | Depende de quando o snapshot de física é congelado. |
| `RunDrawingCallbacks` (Python) | Callback com efeito colateral | GIL e API Python: manter ordem e thread. |
| `KX_WorldInfo`, filtros 2D, posição do Sol | Estado gráfico mutável | Escritos e consumidos no mesmo frame. |

Estimativa: copiar transforms é barato; o bloqueador é decidir quem pode
mudar `KX_GameObject`/`KX_Camera`/`KX_LightObject` vivos enquanto o snapshot
existir.

### Plano 8 — passo fixo

- Próximo passo possível: interpolação de transform no render (opcional, só
  para estados com par anterior/atual definido).
- Com `timescale = 0` e passo fixo ligado, o laço pode rodar `m_maxLogicFrame`
  `Update()` vazios por frame (achado de 2026-09-07). Conferir no código atual
  se a correção de 2026-10-06 mudou isso.
- Requisitos do modelo-alvo que seguem: limites reais de catch-up para lógica
  e física, política para excesso de tempo, pause/time scale/render desligado
  bem definidos, reprodutibilidade medida (sem prometer determinismo bit a
  bit), modo de compatibilidade e testes com frame time artificial.

### Plano 9 — candidatos e limites

- Pular `m_deformer->Apply()` quando nada mudou: exige auditar `RAS_Deformer`
  antes.
- Teste em jogo real do swap interval só quando muda (troca de vsync deve
  seguir funcionando) ficou pendente.
- Cena pesada (`projects-teste/benchmark.range`): `Overhead` 48% e
  `ShadowCulling` 26% do frame, não investigados. Candidato a plano futuro ou
  revisão do CSM.
- Higiene futura do standalone: `-g nome valor` (sem `=`) é ignorado em
  `GPG_Ghost.cpp`, e as opções de debug não usam `gm.flag` como padrão
  (`LA_Launcher.cpp`), ao contrário do Play do editor.
- Concorrência (double buffering, render thread) só depois da auditoria de
  snapshot, baselines A/B e ownership de GL, Python/GIL, Bullet, SceneGraph e
  recursos de GPU. Não usar ECS como requisito, não copiar o mundo inteiro por
  frame, não chamar `RenderData` de snapshot, não usar locks genéricos sem mapa
  de ownership.

### Plano 10 — decisões de escopo

- Renomear taxas e passos (`m_timestep`, `m_framestep`, `m_ticrate` etc.):
  descartado; risco maior que o ganho.
- Extrair `UpdateSleepTime()`/`ClockTiming()`/`FrameOver()`/`FrameTiming()`
  para `KX_FrameClock`: descartado por ora. Se voltar, entra como plano próprio
  com hipótese, benchmark A/B e teste de regressão. É a mudança de maior risco
  (~24-30 membros `m_*time*`).
- `EndFrame()` ainda mistura swap com log de draw calls e overlay de debug de
  partículas (candidato a `KX_DebugRenderer`).
- `tc_scenegraph` é código morto de profiling.

## Gates para qualquer retomada

- Sem edição concorrente nos arquivos tocados.
- Escopo e comportamento esperado escritos antes.
- Builds relevantes e testes aplicáveis passando.
- Teste em jogo real quando houver parte visual ou física.
- Métricas antes e depois para otimizações.
- Regressões resolvidas ou aceitas pelo usuário.

## Critério de conclusão do programa

- `KX_KetsjiEngine` coordena, sem implementar internamente, subsistemas grandes.
- Temporização e limites de simulação com contratos testados.
- Recursos temporários e estado gráfico restaurados automaticamente.
- Entradas públicas inválidas falham de forma segura.
- CPU e GPU analisáveis por fases granulares.
- Nenhuma otimização sem benchmark reproduzível.
- Editor, Play embutido e standalone compatíveis.
- Cena real sem regressão de física, sombras, partículas, filtros, várias
  câmeras ou troca de cenas.
