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
- GPU Skinning move a deformação por bones para o vertex shader e está liberado para uso.
- Z-prepass para materiais alpha-cutout reduziu o tempo de GPU do benchmark de 28,29 ms para 21,45 ms.
- Streaming por distância está disponível em `projects-teste/scripts/streaming_manager.py`.
- LOD de impostor possui billboard cilíndrico e bake automático de atlas multiângulo.
- Partículas GPU por objeto usam transform feedback, shader cache compartilhado, sprites/texturas, curvas,
  presets, debug ImGui e colisão Ground Plane/Screen-Space.

### Iluminação e renderização

- O caminho usado pelo `RangeRuntime` foi migrado para OpenGL core profile, mantendo o editor em
  compatibility profile. Os no-ops aceitos no core são motion blur legado, clipping de espelho/água e
  texto de debug baseado em `BLF_draw`.
- CSM para luzes Sun usa três cascatas ajustadas ao frustum e considera os bounds dos casters no recorte Z.
  O bug de sombra estática ausente no ângulo inicial foi corrigido e confirmado visualmente.
- FXAA foi atualizado para uma implementação no estilo 3.11 com nove amostras.
- Bloom, SSAO, SSR, Tonemap e Light Scattering podem ser controlados pelo actuator Filter 2D com faixas de
  passes reservadas.
- Depth Transparency possui captura de profundidade dedicada e comportamento seguro fora do jogo.
- Weather nativo no `World` oferece chuva, nuvens e lens flare; a chuva inclui modos Classic e Volumetric.

### Runtime e ferramentas

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

## Fontes relacionadas

- [Roadmap atual](docs/roadmap.md)
- [Histórico técnico](docs/changelog.md)
- [Arquitetura](docs/architecture.md)
- [Guia de manutenção](docs/maintenance-guide.md)
