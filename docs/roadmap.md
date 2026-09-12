# Roadmap

## RangeArmor

O fluxo de runtime Windows/Linux x86_64 foi concluÃ­do e estÃ¡ documentado em
[`rangearmor-modernization-plan.md`](rangearmor-modernization-plan.md). A interface 32-bit foi retirada;
resta apenas validar o runtime em uma distribuiÃ§Ã£o Linux nativa fora do WSL.

Somente itens abertos, pendentes de validação ou explicitamente adiados ficam neste arquivo. Recursos
concluídos estão resumidos em [`../relatorio-melhorias-anastacioengine.md`](../relatorio-melhorias-anastacioengine.md)
e detalhados no [`changelog.md`](changelog.md).

## Prioridade atual

- **Cutscene nativo**: Fases 0–2 e 4–5 implementadas, incluindo dados persistidos,
  aba Properties depois de World com ícone `SEQUENCE`, operadores nativos,
  runtime C++, API Python, import/export JSON e exemplo `.blend`. Permanecem
  abertos a Fase 3 (ícones PNG próprios para identificação e ações específicas,
  sem substituir os ícones padrão `ZOOMIN`/`ZOOMOUT` de adicionar/apagar) e a
  validação manual de Play → Stop → Play e standalone. Ver o
  [plano de integração](cutscene-native-integration-plan.md) e o
  [roteiro do exemplo](cutscene-native-example.md).
- **Runtime Linux x86_64**: preflight e configuração passaram no Debian 13 via WSL com Python 3.11 isolado,
  e todos os objetos de `RangeRuntime` foram compilados. A primeira ligação falha porque dependências
  transitivas ainda pedem `bf_editor_animation`, `bf_editor_interface`, `bf_editor_space_api` e `extern_glew`
  apesar de `WITH_BLENDER=OFF`. Corrigir esse grafo, repetir a ligação, instalar, empacotar e validar em Linux
  nativo; ainda não há release Linux oficial.
- **Associação de arquivos**: permitir abrir `.blend` e `.range` diretamente com os executáveis adequados,
  definindo instalação/registro no Windows e comportamento de duplo clique.
- **World Status**: as oito Global Properties automáticas foram implementadas e compiladas, mas não
  apareceram em um `World` novo no teste real. Diagnosticar criação, versionamento e atualização da UI.
- **Auditoria de `source/source/blender`**: confirmar ou descartar os candidatos registrados em
  [`relatorio-varredura-bugs-silenciosos.md`](relatorio-varredura-bugs-silenciosos.md), com reprodução,
  correção isolada e teste aplicável.
- **Vehicle System / Vehicle Lab**: executar por marcos o
  [plano 2](vehicle-system-plan-2.md) — Fase B (Steering & Brakes, incl. volante visual),
  Fase C (Powertrain: drive type, torque/RPM, marchas), Fase A (Chassis: Center of Mass
  offset). Fase D (Wheel & Suspension) está fechada, sem trabalho novo.

## Performance

- Investigar o custo residual de `MainRender` na cena de benchmark. O teste A/B já descartou GPU Skinning
  como causa; qualquer nova hipótese deve começar por medição.
- Avaliar o conteúdo de folhagem e os níveis de LOD na cena real. A infraestrutura de impostor e o bake de
  atlas já existem; o restante pode ser trabalho de asset, não de engine.
- Vendorizar `Recast/`/`Detour/` a partir de `tools/recastnavigation-main` (a API de integração
  já foi portada para `dtNavMesh`/`dtNavMeshQuery`, ver
  [changelog](changelog.md#2026-09-08--recastnavigation-port-para-api-moderna-dtnavmeshdtnavmeshquery);
  falta trazer a lib em si, com a varredura de bugs silenciosos prevista no plano original).
- Navmesh dinâmica: hoje o navmesh é gerado uma única vez (`mesh.navmesh_make`) e não reage a
  objetos que se movem depois do bake. Suporte a isso exigiria trazer `DetourTileCache`
  (não vendorizado hoje) e um sistema de obstáculos temporários — escopo novo, não iniciado.

## Iluminação e gráficos

- **Resolução dinâmica (runtime)**: implementada como opt-in em `Game Render Properties > Dynamic Resolution`, com alvo de FPS, limites e passo. O controlador mede GPU, aplica média/histerese e reduz somente os offscreens do 3D; a janela, input e UI continuam na resolução nativa. Funciona no Play do Game Engine e no standalone, não na 3D View de edição. Build e smoke test passaram; falta validar visualmente numa cena GPU-bound, comparando ligado/desligado e observando se não há oscilação perceptível de escala ou artefatos nos efeitos.
- CSM: blend suave entre cascatas (`shadow_simple_csm`/`shadow_vsm_csm`, cross-fade via
  `smoothstep` numa banda de 10% do split) e visualização de debug (`csm_debug_tint`, DNA/RNA/UI)
  já estão implementados em `gpu_shader_material.glsl` — item desatualizado, mantido aqui só até
  medir o custo real de GPU dessas duas features, que segue pendente.
- Avaliar antialiasing temporal somente com um caso de uso e critérios de qualidade definidos.
- Permanecem aceitos como no-op no core profile: motion blur legado, clipping de espelho/água e texto de
  debug via `BLF_draw`. Reabrir apenas com demanda concreta.

## Validações pendentes

- Cutscene nativo: executar no editor o roteiro de
  [`cutscene-native-example.md`](cutscene-native-example.md), cobrindo
  salvar/reabrir, Play → Stop → Play e execução standalone; confirmar que o
  `Spawn Object` dispara uma vez, limpa a réplica no Stop/Restart e mantém o
  mesmo resultado nos dois modos. A validação automatizada de geração,
  reabertura, importação/exportação e estrutura do exemplo já passou.

- Ketsji / Plano 1A: contador de estabilização CSM corrigido, rebuild limpo e
  smoke test de reinício aprovados. Validar sombras no jogo real em
  Play → Stop → Play e standalone, incluindo múltiplas luzes/cenas e a transição
  do nono para o décimo frame elegível. Ver
  [plano mestre](ketsji-engine-modernization-plan.md). Registrar separadamente
  os avisos de textura sem nível-base vistos em `-d gpu`; origem ainda não
  determinada. O runtime local testado reporta perfil Compatibility.
- Ketsji / Plano 1A: `shadowCulling` separado de `maxphystep` (DNA/RNA/
  versionamento/engine/launcher/Python docs), rebuild limpo (2.935/2.935) e
  smoke test aprovados. Falta testar a migração de arquivo antigo com
  `maxphystep` gravado em 0/1/5/10 real (hoje só revisada por leitura) e
  validar visualmente que arquivos antigos preservam o comportamento de
  sombra. Ver [plano mestre](ketsji-engine-modernization-plan.md).
- Ketsji / Plano 1A: `SetTicRate`/`SetRenderRate`/`SetAnimationRate` agora
  rejeitam zero, negativo, NaN e infinito (Python e C++), preservando a
  última taxa válida; rebuild e smoke test dedicado aprovados.
- Ketsji / Plano 1A: cálculo da posição do Sol em `PostRenderScene` agora
  ignora `screenPos.w` nulo/próximo de zero/negativo (Sol atrás da câmera ou
  paralelo ao plano de visão) em vez de dividir por ele; rebuild e smoke test
  dedicado (cena `ketsji_sun_projection_smoke.range` nova) aprovados. Falta
  confirmar visualmente no jogo real que o Light Scattering/Lens Flare não
  pisca ou salta ao cruzar esses ângulos, já que os uniforms não são
  inspecionáveis via Python. Ver [plano mestre](ketsji-engine-modernization-plan.md).
- Ketsji / Plano 1A: item 5 (último) — `FreeCustomMouseCursor` corrige a
  remoção do cursor personalizado com `nullptr` (o setter desreferenciava o
  ponteiro novo antes de checar se existia) e o vazamento da struct
  `CustomMouseCursor` na troca e no encerramento da engine; rebuild e smoke
  test dedicado aprovados. **Plano 1A concluído (itens 1–5).** Nenhum ponto de
  entrada Python passa `nullptr` ao setter hoje, então esse ramo específico
  não tem cobertura automatizada, só revisão de código. Ver
  [plano mestre](ketsji-engine-modernization-plan.md).
- Ketsji / Plano 2: categorias `tc_collisiondepth` (`CollisionDepth`) e
  `tc_texturerenderers` (`TextureRenderers`) separadas do profiler (antes
  somadas em `Shadows`/`MainRender`), completando o item "Texture renderers e
  collision-depth pass" em duas unidades; clean rebuild aprovado nas duas.
  Falta confirmar visualmente as duas categorias como linhas separadas num
  relatório de benchmark — validação opcional, não bloqueante. Ver [plano
  mestre](ketsji-engine-modernization-plan.md).
- Ketsji / Plano 2: categoria `tc_particles` (`ParticleUpdate`) separada de
  `Scenegraph`, isolando `KX_Scene::UpdateGpuParticleEmitters()` (metade
  "atualização" do item "atualização e desenho de partículas"); clean
  rebuild e teste no jogo real aprovados. Ver [plano
  mestre](ketsji-engine-modernization-plan.md).
- Ketsji / Plano 2: categoria `tc_actuators` (`Actuators`) separada de
  `Logic`, isolando `SCA_LogicManager::UpdateFrame` (parte "actuators" do
  item "sensores, controllers/Python e actuators separadamente"; sensores e
  controllers seguem fundidos, fora do escopo); clean rebuild e teste no
  jogo real aprovados. Ver [plano
  mestre](ketsji-engine-modernization-plan.md).
- Ketsji / Plano 2: categoria `tc_input` (`Input`) separada de `Overhead`,
  isolando o bloco de input/ImGui no início de `NextFrame()` (item "Input e
  ImGui"); clean rebuild e teste no jogo real aprovados. Ver [plano
  mestre](ketsji-engine-modernization-plan.md).
- Ketsji / Plano 2: categoria `tc_scenegraph` (`UpdateParents`) separada em
  três — `tc_scenegraph_logic`, `tc_scenegraph_actuators` e
  `tc_scenegraph_physics` —, uma para cada passagem de `UpdateParents()` em
  `NextFrame()` (item "Cada passagem de `UpdateParents`"); clean rebuild e
  teste no jogo real aprovados. Ver [plano
  mestre](ketsji-engine-modernization-plan.md).
- Ketsji / Plano 2: categoria `tc_lightupdate` (`LightUpdate`) separada de
  `Shadows`, isolando o loop de atualização de luzes
  (`UpdateDistanceCulling`/`Update`/glow) em `RenderShadowBuffers()` (7ª
  unidade, parte "atualização de luzes" do item "Atualização de luzes,
  ajuste de matrizes CSM, shadow culling e shadow draw"; shadow
  culling/shadow draw já estavam separados, ajuste de matrizes CSM ficou
  fora por não ter ponto de retomada isolado); clean rebuild e teste no
  jogo real aprovados. Ver [plano
  mestre](ketsji-engine-modernization-plan.md).
- Ketsji / Plano 5: 3ª e 4ª unidades de otimização de sombras concluídas e com
  build limpo — reutilização das câmeras temporárias de sombra e cache por
  luz que pula o recálculo das matrizes de cascata quando câmera/luz não se
  moveram e não há shadow casters dinâmicos. Falta validar em jogo real (CSM,
  split estático/dinâmico, debug do frustum) antes de dar o Plano 5 por
  encerrado. Ver [plano mestre](ketsji-engine-modernization-plan.md).
- Ketsji / Plano 5: 5ª unidade — nova propriedade de câmera
  `csm_cache_max_stale_frames` ("Shadow Cascade Cache Tolerance", painel
  Culling, slider 0/1/2) para o usuário controlar o cache de cascata da 4ª
  unidade, motivada por um relato de tremor de sombra ao mover a câmera.
  Rebuild limpo e teste em jogo real aprovados: valor 2 (Tolerant) não
  mostrou diferença perceptível de tremor nem pop de sombra. O cap de 1
  frame de tolerância (`kCSMCacheToleranceEpsilon`) foi mantido como está —
  aumentar esse limite ficaria como trabalho futuro isolado, não decidido
  agora. **Plano 5 concluído (unidades 1–5).** Ver
  [plano mestre](ketsji-engine-modernization-plan.md).
- Confirmar visualmente o splash e About no `RangeEngine`: todo o popup deve subir discretamente em 1,2 s; o
  painel inferior precisa manter o estilo limpo (sem caixas cinzas), `Create Project`, recentes e os links de
  rede devem permanecer interativos.
- Antes da próxima distribuição, declarar explicitamente se o fork será publicado como GPLv2-or-later ou
  sob GPLv3 e incluir o arquivo de licença correspondente na raiz/pacote.
- Confirmar no editor a aba Particles em objetos Empty e as ordens ajustadas nos painéis Render Layers e
  Physics.
- Testar os bindings do menu ImGui com um gamepad físico e ajustar as áreas clicáveis, se necessário.
- Executar a cena de regressão física dos Runtime Property Sensors/Actuators, incluindo massa, velocidades,
  gravidade e referências a objetos removidos.
- Sob stress real, exercitar start/stop de captura de vídeo e múltiplos efeitos OpenAL. Os fixes estáticos de
  concorrência já compilam; este teste é complementar.

## Fora do escopo atual

- Paralelização ampla do loop principal e remoção do GIL de Python.
- Atualização completa do Bullet apenas para obter solver multithread.
- Edição de cena durante o jogo com persistência automática.
- Reimplementação de recursos herdados listados no relatório de melhorias.
