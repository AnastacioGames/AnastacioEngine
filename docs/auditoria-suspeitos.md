# Suspeitos de trabalho repetido por frame

Relatório vivo da varredura descrita em [auditoria-trabalho-repetido.md](auditoria-trabalho-repetido.md).
Achados vieram de leitura de código por área; os medidos dizem onde e como.
Resultados detalhados do lote GL/RA: [auditoria-claude-resultados.md](auditoria-claude-resultados.md).
Histórico de cada correção: `docs/changelog.md` e `docs/changelog-arquivo.md`.

Status: `suspeito` → `verificado` → `corrigido` | `falso positivo` | `adiado` (com motivo).
Caminhos relativos a `source/source/gameengine/` salvo indicação.

## Resumo

- **Nível 0 (bugs de correção):** todos corrigidos, só compilados; falta conferir em jogo. São: `RemoveRessources`
  (`KX_GameObject.cpp:989`), PH8, SP3, SP1, PY2, texto bitmap desregistrado no `NewRemoveObject`, PY3 e
  `RAS_2DFilter::ComputeTextureOffsets` no resize.
- **Crítico/alto:** GP1 = GP2 = RA1 (luzes por objeto), grupo 1 (setters do nó), LP1, PH2, CV1-CV8, KX4, RA4,
  RA8, SP4, SP13 corrigidos. PH1 segue adiado.
- **Abertos** estão em cada seção abaixo, inteiros. Os fechados viram uma linha.

## Fila de verificação (grupos)

Agrupado por causa raiz; vários IDs são o mesmo problema visto de áreas diferentes.

1. **Setters do nó sem comparar + callback sempre**: KX1, KX3 = CV2 = GL1, KX2 = CV1, PH5, PH4, KX6, KX8, PY1/PY2.
   Corrigido em ef80cf62 (setters comparam; sync só se o nó mudou). Cena `criar_cena_grava_igual.py`
   (grupo 1 + PH2): 1600 → 0 syncs/frame.
2. **Luzes reenviadas por objeto**: GP1 = GP2 = RA1; depois GP6/RA5, RA9 = KX11. Cena
   `criar_cena_luzes_sombra.py` (contador `lightUniforms`).
3. **Física**: PH2, PH1, PH7.
4. **Marca sempre ligada**: KX9 e PH3 corrigidos.
5. **Animação**: CV3/CV4/CV5/CV8, KX5 e KX13 corrigidos.
6. **Render**: RA3, KX4, RA4, RA6, KX10, LP1.
7. **Custo baixo**: GL2-GL4/GL7/GL8, RA2/RA7/RA8, GP3-GP5/GP7/GP8, PH9, KX7/KX12/KX14, PY3, PY4.
8. **Spawn/remoção/LibLoad**: SP2, SP4-SP15.

## Converter / animação (deformers, armature, ações, IPO)

Fechados:

- CV1 = KX2 — ação de armature forçava sync da subárvore: corrigido em 2026-10-09 (só com canais de transform).
- CV2 — IPO gravava sem comparar: corrigido em ef80cf62.
- CV7 — getters de ação registravam o objeto: corrigido em 2026-10-09.
- CV8 — `m_animNeedsUpdateCache` com objetos sem ação: corrigido em 2026-10-09.

Abertos (corrigidos, falta validação):

| ID | Onde | Status |
|---|---|---|
| CV3 | `Ketsji/KX_Scene.cpp:2192` `anim_needs_update`, `Converter/BL_ArmatureObject.cpp` `TickCullSkip` | **corrigido 2026-10-11** (decisão de design aprovada): armature 100% culled não faz pose + skinning todo frame; `TickCullSkip()` força update a cada 15 frames pulados e `ResetCullSkip()` zera após update real. Validado com `tools/debug/cenas/criar_cena_cv3_correcao.py` (pose congela em blocos de 15 frames, salta a cada 15). A transição culled→visível usa o ramo antigo, sem mudança. **Falta:** avaliação visual no jogo real (pose não trava nem suaviza errado ao reaparecer). |
| CV4 | `Converter/BL_SkinDeformer.h:70` `PoseUpdated` | **corrigido 2026-10-09**: snapshot das matrizes da pose; pose igual não refaz skin (smoke `criar_cena_lote_auditoria.py`). **Falta:** visual. |
| CV5 | `Ketsji/BL_Action.cpp:530` | corrigido (`SetLastFrameIfShapeChanged`): shape key constante não remarca a malha. **Falta:** validação no runtime. |
| CV6 | `Converter/BL_ShapeDeformer.cpp:117-132` | corrigido (`m_useShapeDrivers`): key sem driver não avalia animdata. **Falta:** validação no runtime. |

## Ketsji + SceneGraph

Fechados:

- KX1, KX3 — `UpdateWorldData` e setters sem comparar: corrigido em ef80cf62.
- KX4 — billboard reescrevia orientação: corrigido em 2026-10-09 (`criar_cena_kx4_ra8.py`).
- KX5 — probe reavaliava animação por face: corrigido; LOD por face é intencional.
- KX12 — `UpdateBuckets`: descartado, já protegido por `DIRTY_RENDER`.
- KX13 — vetor temporário nos passes de pose: corrigido.

Abertos:

| ID | Onde | Status |
|---|---|---|
| KX6 | `Converter/BL_ArmatureObject.cpp:451-475`, `Ketsji/KX_BoneParentNodeRelationship.cpp:49-101` | corrigido: `UpdateTimestep` agenda filhos de osso só quando a pose pode mudar. **Falta:** teste visual. |
| KX7 | `Ketsji/KX_NodeRelationships.cpp:138-206` `KX_SlowParentRelation` | corrigido: para de reagendar quando a interpolação não muda nada; translação/repouso/retomada passaram no player. **Falta:** rotação/escala e visual. |
| KX8 | `Ketsji/KX_Scene.cpp:604-671` `UpdateAutoWorldSun` | setters do SG já comparam; probe compara assinatura. Invalidação de sombras não reproduzida (repouso sem updates, câmera move o sol). **Falta:** sombras/parenting e visual. |
| KX9 | `Ketsji/KX_Camera.cpp:654-731` `UpdateView` | corrigido em 6d8c640d; movimento/retorno e lente validados no player. **Falta:** estéreo/Camera FX e visual. |
| KX10 | `Ketsji/KX_ShadowRenderer.cpp:357-407`, `KX_Scene.cpp:1747` `AutoShadowStillValid` / `BuildShadowCullCache` | **corrigido**: mapa de casters só refeito ao invalidar. Benchmark estático: sombras 0,613 → 0,194 ms, FPS +28,3%. Cena `criar_cena_kx10_correcao.py` (2026-10-11): com armature em alcance `lightsShadowUpdated` = 1 em todos os frames; sem armature 0 em repouso e 1 só no frame após cada mudança de alcance. **Falta:** checagem visual no jogo real. |
| KX11 = RA9 | `KX_LightObject.cpp:119`, `RAS_OpenGLLight.cpp:560`, `blender/gpu/intern/gpu_material.c:4063`; `KX_ShadowRenderer.cpp:593` | corrigido: cache da matriz de entrada/escala e do ângulo do cone; diferencial e runtime passaram. **Falta:** FPS, visual e custo do Static Split (`dynamicCasterSet`). |
| KX14 | `KX_GameObject.cpp:874`, `KX_FontObject.cpp:258`, `KX_Speaker.cpp:258` | corrigido texto/áudio (Text-Res conserva texto; speaker conserva último estado 3D). Partículas sem mudança. **Falta:** FPS, visual e avaliação auditiva. |

Não verificado: `KX_BatchGroup::SplitMeshUser`.

## Rasterizer

Fechados:

- RA1 — = GP1/GP2, corrigido em 2026-10-09 (ver gpu / depsgraph).
- RA4 — VBO de instancing reenviado em repouso: corrigido (1 upload inicial, 0 em repouso).
- RA5 — preparação de buckets sem slots ativos: corrigido, aceito pelo usuário (preparações 25 → 1).
- RA6 — laços sobre todos os buckets: descartado em 2026-10-09, bucket vazio já sai cedo; só com medição.
- RA7 — `SetCullFace` sem cache: descartado, `GL_CULL_FACE` é alterado fora do rasterizer.
- RA8 — `counts`/`indices` por batch: corrigido em 2026-10-09 (40 cubos 41 → 2 draws).

Abertos:

| ID | Onde | Status |
|---|---|---|
| RA2 | `Ketsji/BL_BlenderShader.cpp:332` → `gpu/intern/gpu_material.c:902` `GPU_material_bind_uniforms` | **corrigido 2026-10-11**: produto view × object reutilizado; cache de inversas em `GPUMaterial` (`invcache_*`, zerado por bind) quando o mesmo `obmat`+`viewmat` repete na mesma ativação. Saída igual na cena `criar_cena_luzes_sombra.py`. **Falta:** medir em cena com várias passadas por objeto, benchmark e visual no jogo. |
| RA3 | `Rasterizer/RAS_MeshSlot.cpp`, `RAS_DisplayArrayStorage.cpp`, `RAS_DisplayArray.cpp` `SortPolygons` | integrado em 12741810; visual aprovado. **Falta:** benchmark conclusivo e passes adicionais ([plano](ra3-transparencia-plan.md)). |

## Physics (Bullet + ligação com o Ketsji)

Fechados:

- PH2 — "Use Frame Rate" sincronizava todos 2×/frame: corrigido em 8f45943b; sem ganho mensurável no RolimaRacer.
- PH3 — soft body invalidava sempre: corrigido (grade de 6 561 nós: 1 → 0 updates em repouso).
- PH4 — rodas com carro parado: descartado em 2026-10-09, pular pularia comandos de direção; ganho baixo.
- PH5 — personagem publicava transform sempre: corrigido em 2026-10-09.
- PH6 = GL8 — Near/Radar: corrigido em 2026-10-09.
- PH7 — `std::set` de controllers por sub-passo: descartado em 2026-10-09, custo baixo e exigiria aviso nos setters.
- PH8 — `ProcessFhSprings` com `body` nulo: bug corrigido; custo do laço segue baixo.
- PH9 — `std::map` em `CallbackTriggers`: corrigido em 2026-10-09 (vetor reutilizado).

Aberto:

| ID | Onde | Status |
|---|---|---|
| PH1 | `btCollisionWorld.cpp:73/200`; mundo criado em `Physics/Bullet/CcdPhysicsEnvironment.cpp:695-709` | **adiado**: `m_forceUpdateAllAabbs` fica true e recalcula AABB de todos (estáticos inclusos) a cada sub-passo. Desligar exige `updateSingleAabb` em todo caminho que move estático ou kinematic. |

## GameLogic / Common / Expressions / Network / VideoTexture

Fechados:

- GL1 — = KX1/CV2, corrigido em ef80cf62.
- GL4 — `refresh()` reenviava fonte estática: corrigido em 2026-10-09 (contador de versão).
- GL5 — PropertyActuator recriava parser: corrigido, cache só de literal (-31% na cena GL).
- GL6 — PropertySensor: falso positivo; só o `GetText()` duplicado do Changed foi corrigido.
- GL7 — cone Gaze com `acos` por objeto: corrigido em 2026-10-09 (~12%); laço O(objetos) fica (raro).
- GL8 = PH6 — corrigido em 2026-10-09.
- GL9 — TimeEventManager: falso positivo prático; retorno cedo sem Timer.
- GL10 — teclado/mouse: corrigido.

Abertos:

| ID | Onde | Status |
|---|---|---|
| GL2 | `Network/NET_Replicator.cpp:318` `capture` | **concluído 2026-10-09**: estado bruto idêntico pula serialização + hash. Compilado; **não testado em rede**. |
| GL3 | `Network/NET_Replicator.cpp:377` `rebuildGrid` | **concluído 2026-10-09**: grade só reconstrói se objeto entra/sai ou muda de célula. Compilado; **não testado em rede**. |

## Bindings Python

Fechados:

- PY1 — setters de transform sem comparar: descartado (o nó pode estar atrasado em relação à física).
- PY2 — `worldOrientation[i]` gravava local: bug corrigido; custo por componente fica.
- PY3 — activity culling de componentes sem efeito: corrigido; cópia do vetor e `CallMethod` ficam.
- PY4 — `setUniform*` sujava com valor igual: corrigido (memcmp).
- PY5 — lens/fov invalidavam sempre: corrigido.
- PY6 — `showMouse` sem comparar: descartado, o SO pode mudar o cursor fora da engine.

Aberto:

| ID | Onde | Status |
|---|---|---|
| PY7 | `KX_GameObject.cpp:1737` `SetVisible` | **adiado**: `Activate` do graphic controller sempre; risco com controller criado depois contando com `SetVisible` igual. |

## Laço principal, plataforma, filtros 2D, overlays e áudio

Fechados:

- LP1 — Camera FX copiava a tela todo frame após o 1º uso: corrigido (sai cedo sem filtro `Ok()`).
- LP2 — `m_pyprofiledict` por frame: corrigido, só em `getProfileInfo()`.
- LP4 — ImGui `NewFrame` sem UI: descartado, necessário para `imgui.*`.
- LP5 — `SDL_SetCursor` por frame: descartado, cache divergiria do cursor da engine.
- LP6 — `NavEnableGamepad`: descartado, já sai cedo.
- LP7 — `AddKeyEvent` por tecla: descartado, ignora repetidos.
- LP8 — bind do cursor: descartado, custo trivial.
- LP11 — `MipmapTextures` 2×: corrigido.
- LP12 — uniforms de filtro por frame: descartado, desprezível.
- LP13 — `AUD_Handle_*` sem comparar: corrigido.
- LP14 — varredura de partículas por `debugUI`: descartado, laço já tem break.
- `ComputeTextureOffsets` no resize: corrigido (nível 0).

Abertos:

| ID | Onde | Status |
|---|---|---|
| LP3 | `Ketsji/KX_RenderPipeline.cpp:345-353`, `:382-466` | **parcial**: mono sem alocação (vetores → arrays). Estéreo **adiado**: `new KX_Camera` por olho por frame; depende do tempo de vida da câmera. |
| LP9 | `Launcher/LA_BlenderLauncher.cpp:383-490` `LiveSyncFromBlender` | **adiado**: no Play embutido, mover o mouse varre todos os Objects (O(objetos × props²)). Arrastar pode mudar sliders; o mapa já é sob demanda. |
| LP10 | `source/source/blender/windowmanager/intern/wm_draw.c:1019-1152` `wm_draw_update_game_live` | **adiado**: ~40 `glGet*` + Push/PopAttrib + recomposição por frame no Play embutido. Estado GL sujo já causou crash de driver. |

## gpu / depsgraph (lado Blender)

O runtime não usa `draw/`, UBO nem depsgraph: é o caminho GLSL 2.7x com `glUniform*` direto.

Fechados:

- GP1 = GP2 = RA1 — luzes e sombras reenviadas por objeto: corrigido em 2026-10-09 com cache do último valor no
  GPUShader. Cena `criar_cena_luzes_sombra.py`: ~902 → ~334 GL/frame. RolimaRacer: 0 (sem lâmpada com sombra).
- GP4 — `GPU_pass_update_uniforms`: descartado em 2026-10-11, inputs mudam de fato; cache já tentado sem ganho.
- GP5 — `GPU_material_bind` recalcula `dynlayer`: descartado em 2026-10-11, depende do material; custo baixo.
- GP6 — matrizes de lamp por material: corrigido em 2026-10-11 (cache por `GPULamp`).

Abertos:

| ID | Onde | Status |
|---|---|---|
| GP3 | `gpu_codegen.c:1741` → `gpu_texture.c:453` → `gpu_draw.c:497` `GPU_verify_image` | **adiado** (2026-10-11): acquire ibuf com spinlock + bind por textura, por material. Trocar `compare` para 1 corromperia o bindcode. Cache correto exige o atalho devolver `ima->gputexture[gputt]->bindcode`, mexendo nos outros 4 chamadores (`gpu_draw.c`, `drawmesh.c`). |
| GP7 | `Ketsji/BL_BlenderShader.cpp:309-322` | **adiado** (2026-10-11): `FindProbe` + bind por objeto todo frame. Cache por objeto erraria quando a sonda se move. Desenho: contador de geração em `KX_TextureRendererManager` a cada mudança de posição de sonda; exige API nova e validação visual. |
| GP8 | `gpu_material.c:5014` `GPU_material_use_damage` / `GPU_material_bind_damage`, `BL_BlenderShader.cpp:353` | corrigido: cast só com uniform Damage ativo; count com cache por GPUShader. **Falta:** benchmark e visual. |

## Spawn, remoção, LibLoad, lote e conversão sob demanda

Custo por evento, não por frame — mas vira por frame com Always em pulso ou spawns contínuos.

Fechados:

- SP1 — navmesh construída no original: corrigido.
- SP2 — `ReplaceMesh` sem comparar: corrigido.
- SP3 — shape info compartilhado: corrigido (`dupli=true`).
- SP4 — hull por cópia: corrigido e medido em 2026-10-11 (`addObject()` 6,645 → 0,182 ms).
- SP5 — hash de BVH por spawn: corrigido em 2026-10-11 (ganho abaixo do ruído do setup do Bullet).
- SP8 — LibFree recompilava todos os shaders: corrigido.
- SP12 — Add Object buscava linear no Main: corrigido em 2026-10-05 (`m_inactiveNameIndex`).
- SP13 — `RemoveValue` duplo no `Split`: corrigido em 2026-10-11; reenvio do lote é inerente.

Abertos (adiados com motivo, 2026-10-11):

| ID | Onde | Status |
|---|---|---|
| SP6 | `KX_Scene.cpp:1448` `NewRemoveObject`; `BaseListValue.cpp:82` | **adiado**: ~20 remoções lineares por objeto. `RemoveValue` remove todas as ocorrências de propósito; índice teria de acompanhar cada lista e `Release`. Sem carga real de remoção em massa. |
| SP7 | `KX_Scene.cpp:1421` `DelayedRemoveObject`/`RemoveEuthanasyObjects` | **adiado**: O(K²). A fila é FIFO e `NewRemoveObject` tira filhos destruídos com o pai; mudar altera a ordem observável. Precisa de teste de ciclo de vida. |
| SP9 | `CcdPhysicsEnvironment.cpp:868` `RemoveCcdPhysicsController` | **adiado**: `CleanPairCallback` roda antes de `removeRigidBody`; tirar a limpeza local depende do Bullet e pode deixar callbacks para proxy liberado. |
| SP10 | `KX_GameObject.cpp:792` `SetupGPUParticlesBuffer` | **adiado**: cache de shader já compartilhado com hot-reload. Cachear buffers/texturas exige invalidar por arquivo, curvas, mesh e contexto GL. |
| SP11 | `BL_Converter.cpp:228-423`; `BL_BlenderDataConversion.cpp:493` | **adiado**: conversão sob demanda não reaproveita material/malha (quebra lote, compila shader). Converte por `Scene` temporária + `MergeScene`; reaproveitar exige conversão incremental. |
| SP14 | `BL_Converter.cpp:800` `UnregisterMesh` | **adiado**: O(N) por decal expirado. Índice reverso teria de cobrir listas ativa/inativa, `ReplaceMesh`, réplica e mesh dinâmica; não roda por frame. |
| SP15 | `KX_DestructionManager.cpp:740` `SpawnDecal` | **adiado**: monta mesh user e refaz com `ReplaceMesh`. A réplica precisa herdar lógica antes; caminho especial arrisca batches/ownership. |

Menores, não verificados: `ReplicateLogic` SearchValue O(N) por link externo; `RegisterObject` FindEntry linear;
cópias nunca entram nas listas de shadow casters (verificar).
