# Relatório de melhorias — AnastacioEngine

Este documento registra o estado técnico vigente da engine. O trabalho ainda aberto fica em
[`docs/roadmap.md`](docs/roadmap.md), e o histórico detalhado de implementação e medições fica em
[`docs/changelog.md`](docs/changelog.md).

## Contexto

RangeArmor estÃ¡ validada para runtimes Windows/Linux x86_64, com cÃ³pia dos runtimes disponÃ­veis,
exportaÃ§Ã£o `.zip`/`.tar.xz` e interface sem alvos 32-bit. Campos 32-bit antigos permanecem aceitos
somente para leitura de projetos legados.

A AnastacioEngine é um fork da Range Engine 1.6 Rev1, derivada da UPBGE 0.2.5b e do Blender 2.79. As
frentes principais são performance, iluminação/renderização e ferramentas de runtime.

Um item só entra no roadmap de engine quando exige mudança em `source/` e recompilação. Configuração de
cena, preparação de assets e scripts independentes são registrados no changelog ou na documentação da
ferramenta correspondente.

## Capacidades herdadas que não devem ser reimplementadas

- GPU instancing com `RAS_InstancingBuffer` e `RAS_DisplayArrayBucket::RunInstancingNode`.
- Batching estático com `RAS_BatchDisplayArray` e `RAS_BatchGroup`.
- LOD por distância com `KX_LodManager` e `KX_LodLevel`.
- Frustum culling com `SG_CullingNode`, `KX_CullingHandler` e `SG_Frustum`.
- Occlusion culling por DBVT do Bullet. A cena usa `use_occlusion_culling`, e objetos grandes podem ser
  marcados como `Occluder`; isso é configuração de conteúdo, não um gap de C++.
- Principled BSDF/PBR herdado do fork. Não criar outro modelo PBR antes de verificar a exposição existente.
- MSAA de ponta a ponta, já confirmado no código e no runtime.

## Melhorias implementadas

### Performance

- O buffer de instancing conserva capacidade e só realoca quando necessário; o rebind redundante dos
  atributos por frame também foi eliminado.
- Resolução dinâmica opt-in preserva a resolução da janela e escala apenas os offscreens internos do
  jogo para perseguir um FPS-alvo. A decisão usa `GL_TIME_ELAPSED`, média suave, histerese e cooldown;
  o usuário configura alvo, escala mínima/máxima e passo em `Game Render Properties > Dynamic Resolution`.
  Ela vale para Play e standalone, nunca para a 3D View de edição.
- GPU Skinning move a deformação por bones para o vertex shader e está liberado para uso.
- Z-prepass para materiais alpha-cutout reduziu o tempo de GPU do benchmark de 28,29 ms para 21,45 ms.
- Streaming por distância está disponível em `projects-teste/scripts/streaming_manager.py`.
- LOD de impostor possui billboard cilíndrico e bake automático de atlas multiângulo.
- Partículas GPU por objeto usam transform feedback, shader cache compartilhado, sprites/texturas, curvas,
  presets, debug ImGui e colisão Ground Plane/Screen-Space.
- Fragment shader customizado por emissor (Fase P): arquivo `.glsl` externo (`object.particles.fragmentShaderPath`
  em Python, campo "Fragment Shader File" na UI), com hot-reload automático (poll de mtime a cada ~0,5s) —
  edita-se o arquivo com o jogo rodando e o efeito atualiza sozinho. Exemplos prontos em
  [`projects-teste/shaders/particles/`](projects-teste/shaders/particles/).

### Iluminação e renderização

- O caminho usado pelo `RangeRuntime` foi migrado para OpenGL core profile, mantendo o editor em
  compatibility profile. Os no-ops aceitos no core são motion blur legado, clipping de espelho/água e
  texto de debug baseado em `BLF_draw`.
- CSM para luzes Sun usa três cascatas ajustadas ao frustum e considera os bounds dos casters no recorte Z.
  O bug de sombra estática ausente no ângulo inicial foi corrigido e confirmado visualmente.
- Novas Lamps já nascem com o preset de sombras para Sun: mapa Simple com filtro PCF, 1024 px na cascata
  Near, com CSM e debug desativados, splits 0,40/0,35 e cascatas Medium/Low em 512/128 px. Os valores continuam
  editáveis por lamp e dados existentes não são alterados.
- FXAA foi atualizado para uma implementação no estilo 3.11 com nove amostras.
- Bloom, SSAO, SSR, Tonemap e Light Scattering podem ser controlados pelo actuator Filter 2D com faixas de
  passes reservadas.
- Depth Transparency possui captura de profundidade dedicada e comportamento seguro fora do jogo.
- Weather nativo no `World` oferece chuva, nuvens e lens flare; a chuva inclui modos Classic e Volumetric.

### Runtime e ferramentas

- `External Files` registra bibliotecas sem misturá-las a Links/Appends
  normais, inclusive quando o conteúdo é um Group. O Outliner lista seus
  datablocks `Text`; uma dependência ausente é marcada como quebrada e pode
  ser importada individualmente para o arquivo raiz, sem sobrescrever um Text
  local nem trazer os demais dados da biblioteca.
- Pathfinding/navmesh (`KX_NavMeshObject`, `KX_SteeringActuator`) usa a API moderna do Detour
  (`dtNavMesh`/`dtNavMeshQuery`), substituindo a antiga `dtStatNavMesh`; walkable
  Height/Radius/Climb do bake respeitam a configuração da cena. Navmesh dinâmica (rebake em
  runtime) não existe e está no roadmap.
- Menu in-game em ImGui com suporte por mouse, teclado e bindings de gamepad.
- Debug Mode expõe bounding boxes, frusta de câmera/sombra e render queries.
- Console ImGui espelha o log da engine no Play e no standalone.
- Global Properties podem ser compartilhadas pelo `World` no runtime. A criação automática das propriedades
  de World Status continua pendente e está no roadmap.
- Runtime Properties tipadas ampliam Property Sensors/Actuators; detalhes e pendências estão em
  [`docs/logic-bricks-modernization.md`](docs/logic-bricks-modernization.md).
- Atlas externo de ícones configurável em `User Preferences > Files > Icons`, com fallback embutido.
- `Create Project`, disponível no splash e em `File`, abre o navegador de pastas e cria uma estrutura pronta
  para o fluxo RangeArmor: `data/` com o `.range`, a cópia protegida `.rasec`, scripts e assets; pastas
  independentes de engine, launcher, ícones e builds em `release/`. Pastas existentes nunca são sobrescritas.
- Objetos podem ser marcados nativamente como chassi de veículo (`game.is_vehicle`, DNA/RNA) com uma lista
  editável de rodas (`ob.vehicle_wheels`, com raio/suspensão/steering por roda), no painel "Vehicle" da aba
  Physics. Ao converter a cena, o próprio motor cria o `PHY_IVehicle`/`KX_VehicleWrapper` e as rodas
  automaticamente a partir desses dados — não é mais só um marcador de design. `KX_GameObject::getVehicle()`
  expõe o veículo já pronto para Python. O painel Vehicle também tem um botão para criar/anexar o
  `vehicle_player_component.py` de controle jogável direto no objeto.
- "Export Game (1 Click)" (`Scene > Export (RangeArmor)`) empacota o jogo direto do Blender sem
  precisar abrir o RangeArmor Panel manualmente antes: scaffold do projeto (`config.json`,
  `Launcher.exe`, ícones, runtime), geração do `.rasec` protegido e chamada do `build_release.py`
  são todos automáticos, com barra de progresso/cursor de espera durante o processo. O template de
  `Launcher.exe` usado no scaffold também se mantém sempre atualizado sozinho: se estiver mais
  antigo que seu source Rust (`source/launcher/src/main.rs`), é recompilado automaticamente com
  `cargo build --release` antes de ser copiado, sem diálogo nem passo manual — evita que um
  binário desatualizado volte a causar o jogo exportado "abrindo e fechando" na hora. Ver
  `docs/export-presets-plan.md` e `docs/changelog.md` (2026-09-12).

## Decisões técnicas vigentes

- O contexto compatibility já expõe OpenGL 4.6 no hardware testado; core profile é uma decisão de
  arquitetura e validação estrita, não um desbloqueio automático de performance.
- Filtros 2D do jogo e efeitos multipass nativos são pipelines diferentes e devem ser validados
  separadamente.
- Dados por objeto não devem ser armazenados ingenuamente em meshes compartilhadas durante a conversão
  Blender → Ketsji.
- `object.particles.enabled` pode ser sincronizado pela Game Property `GPU_Particles_Enabled`; scripts que
  precisam persistir o controle devem alterar essa property.
- Mudanças em DNA exigem clean rebuild. O procedimento completo está em
  [`docs/build-notes.md`](docs/build-notes.md).
- A checagem de range em tempo de compilação da RNA (`USE_RNA_RANGE_CHECK`,
  `rna_internal.h`) está desativada apenas para o toolchain Emscripten —
  é um **contorno temporário** para incompatibilidades reais e
  pré-existentes entre tipo do campo DNA e hardmax da RNA (ex.:
  `ImageUser.fie_ima`, `Material.seed1`/`seed2`), não uma correção. Não
  presumir "alargar o tipo do campo DNA" como solução padrão — cada caso
  exige análise individual e consideração explícita de compatibilidade
  com `.blend` legado. Detalhes em [`docs/roadmap.md`](docs/roadmap.md).

## Fontes relacionadas

- [Roadmap atual](docs/roadmap.md)
- [Histórico técnico](docs/changelog.md)
- [Arquitetura](docs/architecture.md)
- [Guia de manutenção](docs/maintenance-guide.md)
