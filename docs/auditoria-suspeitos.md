# Suspeitos de trabalho repetido por frame

Relatório vivo da varredura descrita em [auditoria-trabalho-repetido.md](auditoria-trabalho-repetido.md).
Achados vêm de leitura de código (agentes por área); nada aqui foi medido ainda.

Status: `suspeito` → `verificado` (confirmado com detector/medição) → `corrigido` | `falso positivo`.
Caminhos relativos a `source/source/gameengine/` salvo indicação.

## Classificação por gravidade (estimativa, antes de medir)

Critério: dano ao jogo (crash/comportamento errado) > custo por frame que escala com a cena inteira > custo por
objeto/feature específica > custo por evento (spawn/LibLoad) > trivial. Vai ser reordenada depois das medições.

**0. Bugs de correção (comportamento errado, independem de desempenho)**
1. ~~`RemoveRessources`~~ **corrigido** (`KX_GameObject.cpp:989`): ramo do material só saía do laço interno e seguia iterando `m_meshes` limpo (UB no LibFree); agora `return` nos dois ramos.
2. ~~PH8~~ **corrigido**: `ProcessFhSprings` testa `body` nulo antes de usar (sensores/personagens não têm rigid body).
3. ~~SP3~~ **corrigido**: `ReplaceMesh` com física passa `dupli=true` a `ReinstancePhysicsShape`; o objeto ganha shape info próprio e as cópias irmãs mantêm a colisão.
4. ~~SP1~~ **corrigido**: `AddNodeReplicaObject` constrói a navmesh da cópia (`newobj`), não do original.
5. ~~PY2~~ **corrigido**: `worldOrientation[i] = ...` (callback mathutils `ORI_GLOBAL`) usa `NodeSetGlobalOrientation`.
6. ~~Texto bitmap~~ **corrigido**: o objeto guarda as malhas duplicadas em `m_bitmapTextMeshes`; `NewRemoveObject` as desregistra do conversor.
7. ~~PY3~~ **corrigido**: `UpdateComponents` só deixa o activity culling parar os componentes com a opção Components ligada; outra suspensão sempre para.
8. ~~LP `ComputeTextureOffsets`~~ **corrigido**: `RAS_2DFilter::Initialize` recalcula os offsets quando o tamanho do canvas muda.

**1. Crítico — todo frame, escala com a cena inteira, provável nos jogos atuais**
- GP1 = GP2 = RA1: 8 luzes × 11 uniforms + sombras reenviados por objeto por passe (~100 GL por draw).
  Medido (2026-10-09, contador `lightUniforms`): 0 no RolimaRacer, que não tem lâmpada com sombra em buffer (no COMPAT as
  luzes vão por `gl_LightSource`); ~880 GL por frame (~22 por draw) com 3 spots com sombra na cena de teste; com o cache do GPUShader caiu de ~902 para ~334 (cena corrigida, cubos visíveis).
- KX1 + KX3 = CV2 = GL1, com PY1/PY2: setters do nó sem comparar + callback de transform sempre; pela física
  `activate(true)` impede o corpo de dormir.
- PH1: AABB de todos os corpos (estáticos inclusos) recalculado a cada sub-passo.
- CV1 = KX2: ação de armature força sync de transform da subárvore inteira.
- LP1: depois do primeiro efeito de câmera (nitro), cópia de tela cheia por frame para sempre.
- PH2: modo "Use Frame Rate" sincroniza todos os controllers 2×/frame (crítico só se os jogos usam esse modo).
- CV3: armature fora da tela faz pose + skinning completos (decisão de design; custo alto por personagem).

**2. Alto — por frame, por objeto/feature comum**
- RA3 (zsort refaz sort + IBO com tudo parado), KX6 (filhos de osso sempre atualizam), CV4/CV5 (reskin/shape key
  sem mudança), KX5 (probes refazem animação por face e trocam LOD 2×/frame), PH3 (soft body + `ExtendAabb`),
  RA5/RA6 (lacos sobre todos os buckets), KX4 (billboard quebra lote), ~~CV7/CV8~~ (objetos inativos removidos),
  GP3/GP4/GP6 (texturas/uniforms/matrizes de lamp por material), RA4 (VBO de instancing refeito), KX10.
- Por evento, mas com travada visível: SP8 (LibFree recompila todos os shaders), SP11 (on demand não reaproveita
  material/malha → quebra lote e compila shader), SP13 (separar membro reenvia o lote inteiro), SP6/SP7 (remoção
  O(N)×20 e O(K²)).

**3. Médio**
- Por frame: KX8 (Auto World Sun invalida sombras), GP7, RA2, RA9 = KX11, PH7, PH4, ~~CV6~~, KX13, PY4, RA8, GL2/GL3
  (rede: serializa e refaz grade todo tick), GL4, GL7, LP2, LP4, LP3 (só estéreo).
- Por evento: SP2, SP4, SP5, SP10.
- Só no Play embutido do editor: LP9, LP10.

**4. Baixo — trivial ou raro**
KX7, KX9, KX12, KX14, RA7, PH5, PH6 = GL8, PH8 (custo), PH9, GL5, GL6, GL9, GL10, PY5, PY6, PY7, LP5-LP8,
LP11-LP14, GP5, GP8, SP9, SP12, SP14, SP15.


## Fila de verificação (ordem sugerida)

Agrupado por causa raiz; vários IDs são o mesmo problema visto de áreas diferentes.

1. **Setters do nó sem comparar + callback sempre**: KX1, KX3 = CV2 = GL1, KX2 = CV1, PH5, PH4, KX6, KX8.
   Uma correção no `SG_Node` (comparar antes de `SetModified`; usar o retorno de `UpdateSpatialData`) cobre a maioria.
   Medir: `sceneNodeUpdates`/`transformSyncs` com personagens em idle, atuador Set position, objetos em osso.
2. **Luzes reenviadas por objeto**: GP1 = GP2 = RA1; depois GP6/RA5, RA9 = KX11. Precisa de contador novo de uniforms.
3. **Física**: PH2 (se os jogos usam "Use Frame Rate"), PH1, PH7.
4. **Marca sempre ligada (forma de 98f54d7f)**: ~~KX9~~ e ~~PH3~~ corrigidos. `KX_SoftBodyDeformer::Apply` compara as posições e normais exatas antes de atualizar o array, notifica apenas os atributos alterados e só recalcula o AABB se as posições mudaram. Sem gravidade o solver Bullet ainda move os nós e o upload continua corretamente; com o corpo suspenso, uma grade de 6 561 nós passou de 1 para 0 `updateNotifies`/`boundsPushes` por frame. O custo do solver continua separado.
5. **Animacao**: ~~CV5/CV8~~, KX5 (animacao das probes) e KX13 corrigidos; decisoes de design CV3/CV4.
6. **Render**: RA3 (zsort), KX4 (billboard), RA4 (instancing), RA6, KX10.
7. **Resto de custo baixo**: GL2-GL10, RA2/RA7/RA8, GP3-GP5/GP7/GP8, PH9, KX7/KX12/KX14.

Grupo 1 também cobre PY1/PY2 (caminho Python + `activate(true)` da física). PY3 e PY4 entram no grupo 7 se a cena tiver muitos componentes/shaders custom.

**Bugs de correção à parte (não são desempenho):**
- ~~PH8~~ (corrigido): `CcdPhysicsEnvironment.cpp:1178` desreferencia `body` antes do teste de nulo.
- PY2: `worldOrientation` por índice grava orientação local (`KX_GameObject.cpp:2863`).
- PY3: activity culling de componentes nunca desliga o `update()`.
- LP: `RAS_2DFilter::ComputeTextureOffsets` não acompanha resize.
- SP1: `KX_Scene.cpp:875` reconstrói a navmesh do **original** a cada cópia; a cópia fica sem navmesh.
- SP3: `ReinstancePhysicsShape` com `m_shapeInfo` compartilhado troca a colisão das cópias irmãs.
- SP: ~~`RemoveRessources` itera `m_meshes` depois de limpar~~ (corrigido); texto bitmap duplicado nunca é desregistrado (vazamento por spawn).

LP1 entra no grupo 6 (render) com prioridade alta: pode estar ativo no RolimaRacer depois do primeiro nitro.
LP9/LP10 só afetam o Play embutido no editor.

8. **Spawn/remoção/LibLoad (custo por evento, não por frame)**: SP2 (ReplaceMesh sem comparar), SP4/SP5 (hull/hash por cópia), SP6/SP7 (remoção O(N)/O(K²)), SP8 (LibFree recompila tudo), SP10 (partículas GPU leem disco por spawn), SP11/SP12, SP13 (lote reenvia VBO), SP9/SP14/SP15.

## Converter / animação (deformers, armature, ações, IPO)

| ID | Onde | Padrão | Custo | Confiança | Status |
|---|---|---|---|---|---|
| CV1 | `Ketsji/BL_Action.cpp:~457`, `UpdateIPOs` :569 | `m_requestIpo = true` sem condição, mesmo sem canais de objeto (armature só com bones) → `UpdateWorldDataThread` do nó e subárvore | transform sync por ação tocando × filhos | alta | suspeito |
| CV2 | `Ketsji/KX_IpoController.cpp:84+`, `SceneGraph/SG_Node.cpp:381/409/426`, `SG_Controller.cpp:58` | IPO grava loc/rot/scale sem comparar; `SetLocal*` e `SetSimulatedTime` marcam modificado sempre | `sceneNodeUpdates`/`transformSyncs` com keys em hold | média | corrigido (ef80cf62): setters comparam e o sync só roda se o nó mudou; cena criar_cena_grava_igual.py 1600→0 syncs/frame |
| CV3 | `Ketsji/KX_Scene.cpp:~2180` `anim_needs_update` | armature fora da tela faz pose + skinning completos (intencional: AABB segue o pose) | O(vértices × influências) por personagem culled | alta / decisão de design | suspeito |
| CV4 | `Converter/BL_SkinDeformer.h:70` `PoseUpdated` | compara tempo, não o conteúdo do pose → reskin + reenvio de VBO com bones parados | alto por personagem, só com ação ativa | média | suspeito |
| CV5 | `Ketsji/BL_Action.cpp:530` | ação de shape key chama `SetLastFrame` sem checar se `curval` mudou → `BKE_key_evaluate_relative` + malha inteira (modifier deformer: derived mesh) | alto | média | suspeito |
| CV6 | `Converter/BL_ShapeDeformer.cpp:117-132` | `m_useShapeDrivers` sempre true → avalia animdata + `ForceUpdate` mesmo sem drivers | médio | média | suspeito |
| CV7 | `Ketsji/KX_GameObject.cpp:680-729`, `KX_Scene.cpp:2362-2372` | getters nao registram mais; objeto comum sai de `m_animatedlist` quando todos os layers terminam e `PlayAction` o registra de novo ao iniciar | baixo por objeto, cresce com a cena | alta | corrigido |
| CV8 | `Ketsji/KX_Scene.cpp:2286-2372` | `m_animNeedsUpdateCache` so recebe objetos com acao ativa; a poda pos-eventos evita repovoa-lo nos frames ociosos | baixo; agrava CV7 | media | corrigido |

Verificados OK: `BL_Action::Update` (sai cedo se terminada/pausada/tempo repetido), `ApplyPose` (guarda `m_lastapplyframe`),
`UpdateTimestep`, `BL_SkinDeformer::Apply` (`GetInvalidAndClear`), `BL_MeshDeformer::Apply`, `BL_ModifierDeformer::Update`
(guarda `m_lastModifierUpdate`), skinning por GPU (só a paleta muda).

Validação sugerida: cena com personagens em idle loop; `transformSyncs` proporcional a ações tocando confirma CV1/CV2;
CV5/CV6 corrigidos (2026-10-09): shape key constante nao remarca a malha e key sem driver nao avalia animdata; validacao no runtime pendente. CV7/CV8 corrigidos (2026-10-09): getters de acao nao inserem mais o objeto; apos eventos, objetos comuns sem layer ativa saem de `m_animatedlist`, enquanto armatures continuam para constraints/deformers. `PlayAction` reinseriu corretamente uma acao terminada no teste de runtime.

## Ketsji + SceneGraph

| ID | Onde | Padrão | Custo | Confiança | Status |
|---|---|---|---|---|---|
| KX1 | `SceneGraph/SG_Node.cpp:219-232` `UpdateWorldData` (e `:244-258` thread) | ignora o retorno de `UpdateSpatialData`; `ActivateUpdateTransformCallback` roda sempre → física + DBVT em toda a subárvore visitada | sync por nó visitado | alta | corrigido (ef80cf62): setters comparam e o sync só roda se o nó mudou; cena criar_cena_grava_igual.py 1600→0 syncs/frame |
| KX2 | `Ketsji/BL_Action.cpp:~455` | = CV1 (dois agentes) | subárvore por objeto animado | alta | suspeito |
| KX3 | `SG_Controller.cpp:58`, `KX_IpoController.cpp:150+`, `SG_Node.cpp:381/409/426`, `KX_GameObject.cpp:2052-2091` | = CV2/GL1; setters do nó e da física não comparam (pode acordar corpo) | nó + física por escrita | média | corrigido (ef80cf62): setters comparam e o sync só roda se o nó mudou; cena criar_cena_grava_igual.py 1600→0 syncs/frame |
| KX4 | `Ketsji/KX_GameObject.cpp:1497-1517` `UpdateLod` (billboard) | `NodeSetGlobalOrientation` + `NodeUpdate` todo frame sem comparar heading; ruído de float quebra lote (`SplitMeshUser`) | por billboard visível × câmera × face de probe | alta | suspeito |
| KX5 | `Ketsji/KX_TextureRendererManager.cpp:335-345` | a probe nao reavalia animacao durante cada face; a simulacao ja atualiza pose/deformer antes do render. LOD por face permanece: e necessario para a reflexao usar a distancia da probe, e troca a malha quando difere da camera principal | animados × 6 faces eliminado; LOD depende da cena | média-alta / média | corrigido (animacao); LOD intencional |
| KX6 | `Converter/BL_ArmatureObject.cpp:451-475`, `Ketsji/KX_BoneParentNodeRelationship.cpp:49-101` | `UpdateTimestep` agenda apenas filhos de osso quando a pose pode mudar; o filho nao se reagenda ocioso | no + descendentes apenas com acao, constraint ou `armature.update()` | alta (padrão) | corrigido; teste visual pendente |
| KX7 | `Ketsji/KX_NodeRelationships.cpp:138-206` `KX_SlowParentRelation` | deixa de reagendar quando a interpolacao nao altera a transformacao | raro | media | corrigido; translacao/repouso/retomada passaram no player; rotacao/escala e visual pendentes |
| KX8 | `Ketsji/KX_Scene.cpp:604-671` `UpdateAutoWorldSun` | setters do SG ja comparam transformacoes; probe compara assinatura | 1 no | alta (so c/ Auto World Sun) | invalidacao continua nao reproduzida: repouso sem updates, camera move sol; sombras/parenting e visual pendentes |
| KX9 | `Ketsji/KX_Camera.cpp:654-731` `UpdateView` | frustumDirty condicionado a mudanca exata de modelview/projecao | baixo; culling continua por frame | alta (padrao) | corrigido em 6d8c640d; movimento/retorno e lente validados no player; stereo/Camera FX e visual pendentes |
| KX10 | `Ketsji/KX_ShadowRenderer.cpp:357-407`, `KX_Scene.cpp:1747` `AutoShadowStillValid` / `BuildShadowCullCache` | mapa de casters so reconstruido ao invalidar; snapshot compartilhado por passada, varredura permanece | O(N) por luz Auto; alocacao so na invalidacao | media | parcial: build/player passaram; 18 amostras iguais; benchmark estatico: sombras 0,613 -> 0,194 ms, FPS +28,3%; jogo real, Spot/deformadores/layers e visual pendentes |
| KX11 | `KX_LightObject.cpp:119`, `RAS_OpenGLLight.cpp:560`, `blender/gpu/intern/gpu_material.c:4063` | = RA9; cache da matriz de entrada/escala evita normalizacao e inversa repetidas; cache do angulo evita cosseno; hide/Area/projecao continuam atualizados | baixo × luzes | media | corrigido; diferencial e runtime antes/depois passaram; FPS e visual real pendentes |
| KX12 | `Ketsji/KX_GameObject.cpp:1380` `UpdateBuckets` | matriz/front face protegidos por DIRTY_RENDER; bitmap text tem cache; setters CPU baratos; ativacao dos slots necessaria por passe | — | baixa | verificado por leitura; sem correcao ou ganho medido |
| KX13 | `KX_Scene.cpp:2155-2270` | os passes de pose/deformer percorrem filhos pelo `SG_Node`, sem vetor temporario. Eventos ja carregavam `const char*`, sem copia de string C++ | alocacao × animados eliminada | média | corrigido |
| KX14 | `KX_GameObject.cpp:874` particulas, `KX_FontObject.cpp:258`, `KX_Speaker.cpp:258` | Text-Res agora conserva texto de entrada; speaker conserva ultimo estado 3D aceito pelo handle; SetModelMatrix so copia 16 floats CPU | baixo | confirmada para texto/audio | corrigido texto/audio; build e testes passaram; FPS, visual e avaliacao auditiva pendentes; particulas sem mudanca |

Verificados OK: `UpdateParents` (só agendados; relações normal/vertex saem cedo), `ClearModified`, `UpdateBuckets`
(`SetMatrix` sob `DIRTY_RENDER`), `UpdateBounds` (98f54d7f), `UpdateLod` fora do billboard, `UpdateObjectActivity`,
`SetShakeShift`, `UpdateEarthquake`, reverb, `UpdateWorldSettings`, `CheckWorldChanged`, `KX_TextureRenderer::NeedUpdate`,
swap interval, `DebugDrawWorld`, `m_visibleMeshCache`, `BL_Action::Update`, `UpdateGpuParticleEmitters`.

Não verificados: `RAS_ParticleBuffer::SetModelMatrix`, `KX_BatchGroup::SplitMeshUser`.

## Rasterizer

Padrão dominante aqui não é marca sempre ligada, e sim reenvio à GPU de valores parados, por draw e por passada
(principal, cada cascade/face de sombra, texture renderers). Os contadores atuais de `CM_WorkCounters` não pegam isto.

| ID | Onde | Padrão | Custo | Confiança | Status |
|---|---|---|---|---|---|
| RA1 | `Ketsji/BL_BlenderShader.cpp:246` `BindShadowLamps` | = GP1 + GP2 (confirmado por dois agentes) | ~100 GL por draw | alta | medido 2026-10-09: 0 no RolimaRacer (sem lâmpada com sombra em buffer); ~880 GL/frame (~22 por draw) na cena `tools/debug/cenas/criar_cena_luzes_sombra.py` com 3 spots com sombra; **corrigido 2026-10-09** com cache do último valor no GPUShader: ~334 GL/frame contra ~902 sem o cache, com os 40 cubos visíveis (sobram os binds de textura de sombra) |
| RA2 | `Ketsji/BL_BlenderShader.cpp:332` -> `gpu/intern/gpu_material.c:902` `GPU_material_bind_uniforms` | produto view x object reutilizado dentro da chamada para local-to-view, normal e inversa; inversas continuam por draw; cast apenas com uniform Damage ativo (GP8) | ate 2 produtos 4x4 eliminados por chamada | confirmada para produto duplicado | parcial: produto e Damage/GP8 corrigidos; build editor/player e diferenciais passaram; benchmark/visual real pendentes; cache de inversas nao implementado |
| RA3 | `Rasterizer/RAS_MeshSlot.cpp:108-115` → `RAS_DisplayArray.cpp:219` `SortPolygons`, `RAS_StorageVbo.cpp:128` | zsort: aloca vector + `std::sort` + reenvio do IBO inteiro por slot por draw, mesmo com câmera e objeto parados; também no shadow pass | alto p/ malhas alpha grandes | alta | suspeito |
| RA4 | `Rasterizer/RAS_DisplayArrayBucket.cpp:268-309` → `RAS_InstancingBuffer.cpp:111` | VBO de instancing refeito por completo a cada passada | ~100 B × instância × passada | média | suspeito |
| RA5 | `Rasterizer/RAS_BucketManager.cpp:102-113` `PrepareBuckets` | `Prepare` (texturas + `update_lamps`) em todos os buckets, inclusive sem slot ativo; infla `IncMaterialChangeCount` | O(materiais × lamps) por passada | alta (laço) / média (custo) | suspeito |
| RA6 | `Rasterizer/RAS_MaterialBucket.cpp:113`, `RAS_BucketManager.cpp:366` | `GenerateTree` e `RemoveActiveMeshSlots` percorrem todos os display-array buckets de todos os materiais | O(buckets da cena) por passada | média | suspeito |
| RA7 | `Rasterizer/RAS_Rasterizer.cpp:862-875` `SetCullFace` | checagem de estado repetido comentada; invalida alpha blend | baixo | média (ver por que foi comentado) | suspeito |
| RA8 | `Rasterizer/RAS_DisplayArrayBucket.cpp:361-392` `RunBatchingNode` | aloca `counts`/`indices` por batch por passada | baixo-médio | média | suspeito |
| RA9 | `Ketsji/KX_LightObject.cpp:119`, `RAS_OpenGLLight.cpp:560`; `KX_ShadowRenderer.cpp:593` | = KX11; inversa/cone agora com cache seletivo; cores/atenuacao sao atribuicoes CPU; set de casters so preenchido com Static Split | baixo × luzes | media | cache KX11 corrigido/testado; FPS, visual e custo do Static Split pendentes |

Verificados OK: `RAS_MeshBoundingBox::Update` (98f54d7f), `RAS_BoundingBoxManager::Update`, `RAS_MeshUser::SetMatrix`
(memcmp; chamador protegido por `DIRTY_RENDER`), `UpdateActiveMeshSlots`, `RAS_InstancingBuffer::Realloc`,
`RAS_StorageVbo::UpdateVertexData`, cache de estado (`SetPolygonOffset`, `SetFrontFace`, `ProcessLighting`, lights),
`KX_Mesh::UpdateBitmapText`, deformers (impostor, dent, batch merge), cache de sombras/cascades.

## Physics (Bullet + ligação com o Ketsji)

Raiz comum com CV2/GL1: `SG_Node::SetLocalPosition/Orientation` marcam modificado sem comparar, então toda escrita
por frame num MotionState vira `UpdateParents` + `UpdateTransform`. Bullet em `source/extern/bullet2/src/`.

| ID | Onde | Padrão | Custo | Confiança | Status |
|---|---|---|---|---|---|
| PH1 | `btCollisionWorld.cpp:73/200`; mundo criado em `Physics/Bullet/CcdPhysicsEnvironment.cpp:695-709` | `m_forceUpdateAllAabbs` fica true → AABB de todos (estáticos incluídos) recalculado e reinserido no broadphase a cada sub-passo; estáticos nunca vão p/ árvore fixa | O(objetos × sub-passos) | alta | suspeito |
| PH2 | `CcdPhysicsEnvironment.cpp:1106/1132` `ProceedDeltaTimeCar`; `CcdPhysicsController.cpp:1129-1177` | modo "Use Frame Rate": `SynchronizeMotionStates` em todos os controllers 2×/frame (dormindo e cinemáticos inclusos); `setLocalScaling` incondicional (compound/hull recalculam AABB); cinemático fica acordado p/ sempre (linha 1617) | O(N) × 2 por frame + `UpdateParents` de todos | alta | corrigido (8f45943b): pula dinâmico dormindo e escala igual; RolimaRacer (Use Frame Rate ligado) sem ganho mensurável, física ~0,23 ms/frame |
| PH3 | `Ketsji/KX_SoftBodyDeformer.cpp:70-160`; `Rasterizer/RAS_BoundingBox.cpp:111-116` `ExtendAabb` | `ExtendAabb` e o deformer só invalidam quando posições/normais realmente mudam; sem gravidade o solver pode continuar mudando nós, sem pular deformação real | O(vértices) de comparação; o upload/AABB é 0 com corpo suspenso (grade de 6 561 nós) | alta | corrigido |
| PH4 | `CcdPhysicsEnvironment.cpp:275-290` `SyncWheels` | rodas sincronizadas com carro parado/dormindo | ~4 nós por carro | média | suspeito |
| PH5 | `CcdPhysicsController.cpp:363-371` `CcdCharacter::updateAction` | publica transform todo sub-passo sem comparar | baixo | média | suspeito |
| PH6 | `KX_CollisionEventManager.cpp:179`, Near/Radar | = GL8 | baixo × sensores | média | suspeito |
| PH7 | `CcdPhysicsEnvironment.cpp:710/1007-1014` `SimulationSubtickCallback` | percorre o `std::set` de todos os controllers por sub-passo; só importa quem tem clamp de velocidade | O(N × sub-passos) | média | suspeito |
| PH8 | `CcdPhysicsEnvironment.cpp:1167-1183` `ProcessFhSprings` | laço sobre todos quando há algum Fh; **bug**: linha 1178 desreferencia `body` antes de checar nulo (sensores/personagens) | baixo; bug de crash | baixa (custo) / média (bug) | suspeito |
| PH9 | `CcdPhysicsEnvironment.cpp:2564-2610` `CallbackTriggers` | `std::map` + `new CcdCollData` por par em contato por sub-passo | baixo | baixa | suspeito |

Verificados OK: `ProceedDeltaTime` padrão (`SynchronizeActiveMotionStates` filtra ativos), retorno cedo sem passo,
`synchronizeMotionStates` do Bullet, `KX_Scene::UpdateParents` (só a lista agendada), `UpdateTransform`,
`KX_CollisionSensor::SynchronizeTransform` (vazio), soft bodies no solver, terremoto, `btBvhTriangleMeshShape::setLocalScaling`,
rotinas sob demanda (`WakeAllBodies` etc.), ambiente Dummy.

Teste sugerido: cena com dinâmicos dormindo + cinemáticos parados, com e sem "Use Frame Rate"; no modo Car
`sceneNodeUpdates`/`transformSyncs` devem ficar perto de N.

## GameLogic / Common / Expressions / Network / VideoTexture

| ID | Onde | Padrão | Custo | Confiança | Status |
|---|---|---|---|---|---|
| GL1 | `SceneGraph/SG_Node.cpp:381` `SetLocalPosition` (e Orientation/Scale); via `Ketsji/KX_ObjectActuator.cpp:~375` (modo Set position) e `SCA_PropertyActuator.cpp:132` | grava e `SetModified()` sem comparar; física também reescrita (`KX_GameObject.cpp:2052`) | nó + filhos por atuador ativo por frame | alta (mesma raiz de CV2) | corrigido (ef80cf62): setters comparam e o sync só roda se o nó mudou; cena criar_cena_grava_igual.py 1600→0 syncs/frame |
| GL2 | `Network/NET_Replicator.cpp:318` `capture` | só pula `isSleeping`, que é falso p/ estático/cinemático/sem física → serializa + hash todo tick (envio OK: delta por hash) | O(N replicados) CPU + alocação por tick | média | suspeito |
| GL3 | `Network/NET_Replicator.cpp:377` `rebuildGrid` | limpa e reinsere a grade inteira todo tick | O(N) por tick | média | suspeito |
| GL4 | `VideoTexture/Texture.cpp:385-440`, `loadTexture` :165 | `refresh()` com fonte estática refaz `glTexImage2D` (+ mipmap CPU, rescale) sem "versão já enviada" | upload completo por chamada | média | suspeito |
| GL5 | `GameLogic/SCA_PropertyActuator.cpp:151-180` | cria parser e reprocessa expressão constante a cada ativação; modo runtime reconverte strings | baixo-médio | média | suspeito |
| GL6 | `GameLogic/SCA_PropertySensor.cpp:149-280` | lookup + `GetText()` + upper/`CM_StringTo` de constantes todo frame | baixo × sensores | média | suspeito |
| GL7 | `Ketsji/KX_RaySensor.cpp:348-380` (gaze-cone) | percorre `GetObjectList()` inteiro por sensor por frame quando o raio erra | O(N objetos) por sensor | média | suspeito |
| GL8 | `Ketsji/KX_NearSensor.cpp:94`, `KX_RadarSensor.cpp:116` `SynchronizeTransform` | reescreve transform do sensor na física sem checar se o pai se moveu; Radar recalcula sen/cos | baixo × sensores | baixa | suspeito |
| GL9 | `GameLogic/SCA_TimeEventManager.cpp:75` | `new EXP_FloatValue` por frame (atualização em si é necessária) | baixo | baixa | suspeito |
| GL10 | `GameLogic/SCA_KeyboardSensor.cpp:122`, `SCA_MouseManager.cpp:69` | lookup de `m_toggleprop` vazio; `GetInput` invariante dentro do laço | trivial | baixa | suspeito |

Verificados OK: `SCA_LogicManager` (guiado por evento), `SCA_ISensor::Activate`, Always/Actuator/Joystick managers,
`KX_NearSensor::Evaluate`, `KX_CollisionEventManager`, `KX_ObjectActuator` (exceto Set position), `CM_UpdateServer`
(`BL_Shader.cpp:906` compara), Expressions (sem observadores), envio de rede (delta por hash), vídeo com `refresh(True)`.

## Bindings Python

Quase nenhum setter Python compara o valor; os de transformação herdam GL1 e ainda somam `activate(true)` na física
e um `UpdateWorldData` imediato por escrita. Getters mathutils não escrevem de volta (OK).

| ID | Onde | Padrão | Custo | Confiança | Status |
|---|---|---|---|---|---|
| PY1 | `Ketsji/KX_GameObject.cpp:4164-4360` `pyattr_set_world/local Position/Orientation/Transform` | `NodeSet*` + `NodeUpdate()` sem comparar; `CcdPhysicsController::SetPosition` (:1406) faz `activate(true)` → corpo nunca dorme; estático vira `CF_KINEMATIC_OBJECT` | árvore + física + culling por escrita | alta | suspeito |
| PY2 | `KX_GameObject.cpp:2715/2796/2847` callbacks mathutils de escrita | `obj.worldPosition.x = v` faz set completo; 3 componentes = 3 syncs; velocidades (`SetLinearVelocity` :1837) acordam sempre, mesmo gravando zero | ×3 do PY1 | alta | suspeito |
| PY3 | `KX_GameObject.cpp:2530-2548` `UpdateComponents` | os dois ramos do if/else são idênticos → activity culling de componentes não tem efeito; `KX_PythonComponentManager.cpp:38` copia o vetor por frame; `PyObject_CallMethod` busca `update` por frame | N componentes × chamada Python | alta (bug) / média (impacto) | suspeito |
| PY4 | `BL_Shader.cpp:405-640` → `Rasterizer/RAS_Shader.cpp:211/231` | `setUniform*` liga `m_dirty` sem `memcmp`; `ApplyShader` reenvia todos os uniforms; `FindUniform` linear | K glUniform por bind | média/baixa | suspeito |
| PY5 | `Ketsji/KX_Camera.cpp:1296-1454` setters (fov, lens, near...) | `InvalidateProjectionMatrix` sem comparar → invalida todas as probes/espelhos | baixo | baixa | suspeito |
| PY6 | `KX_PythonInit.cpp:1367` `showMouse` → `GPG_Canvas.cpp:148` / `KX_BlenderCanvas.cpp:167` | chamada ao SO a cada chamada sem comparar estado | 1 syscall | baixa | suspeito |
| PY7 | `KX_GameObject.cpp:1737` `SetVisible` | `Activate` do graphic controller sempre; `recursive=True` percorre a árvore | baixo | baixa | suspeito |

**Bug de correção à parte:** `KX_GameObject.cpp:2863-2867` `MATHUTILS_MAT_CB_ORI_GLOBAL` chama `NodeSetLocalOrientation`
em vez de `NodeSetGlobalOrientation` — em filho, `obj.worldOrientation[i][j] = x` grava a orientação local.

Verificados OK: `SCA_PythonController::Trigger` (só recompila com `m_bModified`), getters mathutils, setters de luz,
material e World (atribuição simples), `BL_Shader::LinkProgram`, `getRenderStats`, `GetUniformLocation`, `SetScaling` na física (compara).

## Laço principal, plataforma, filtros 2D, overlays e áudio

Nenhum framebuffer/textura recriado por frame (offscreens só em resize/mudança de escala).

| ID | Onde | Padrão | Custo | Confiança | Status |
|---|---|---|---|---|---|
| LP1 | `Rasterizer/RAS_2DFilterManager.cpp:240-316` `RenderFilters`; `Ketsji/KX_2DFilterManager.cpp:489-509` `UpdateCameraFX` | passes de Camera FX ficam montados e só desligados → `m_filters` nunca vazio → cópia de tela inteira (`DrawOffScreen`, + blit com MSAA) por cena todo frame depois que um efeito foi usado uma vez (nitro, troca de câmera) | 1 quad/blit de tela cheia por frame | alta | suspeito |
| LP2 | `Ketsji/KX_KetsjiEngine.cpp:911-921` `UpdateSleepTime` | `m_pyprofiledict` refeito todo frame (tuplas/floats Python + média de 25) sem ninguém ler; só `getProfileInfo()` usa | ~45 alocações Python por frame | alta (padrão) / baixa (custo) | suspeito |
| LP3 | `Ketsji/KX_RenderPipeline.cpp:345-353`, `:382-466` | estéreo: `new KX_Camera` por olho por frame; mono: vetores alocados por frame | alto só em estéreo | média | suspeito |
| LP4 | `Ketsji/KXImgui/KX_Imgui.cpp:192-226`; `KX_KetsjiEngine.cpp:498/613` | `ImGui::NewFrame`/`Render` todo frame mesmo sem nenhuma UI ativa | dezenas de µs CPU | média | suspeito |
| LP5 | `KXImgui/KX_Imgui_Impl_Inputs.cpp:522-541` | `SDL_SetCursor`/`SDL_ShowCursor` todo frame sem comparar; pode brigar com o mouse do engine | baixo | baixa | suspeito |
| LP6 | `KX_Imgui_Impl_Inputs.cpp:451-519` | `NavEnableGamepad` sempre: varre joysticks e lê ~24 entradas por frame sem UI | baixo | média | suspeito |
| LP7 | `KX_Imgui_Impl_Inputs.cpp:254-268` | laço sobre todas as teclas com mapeamento + `AddKeyEvent` + `std::count` mesmo sem mudança (só com debug/profile/game UI) | 100-200 lookups | média/baixa | suspeito |
| LP8 | `KX_Imgui.cpp:237-258` `DrawCustomCursor` | bind + `glTexParameteri` do cursor todo frame | 4 GL | baixa | suspeito |
| LP9 | `Launcher/LA_BlenderLauncher.cpp:383-490` `LiveSyncFromBlender` | Play embutido: movimento do mouse conta como evento → varre todos os Objects do Main (strings de componentes, props O(P²)) | O(objetos × props²) por frame | média (só editor) | suspeito |
| LP10 | `source/source/blender/windowmanager/intern/wm_draw.c:1019-1152` `wm_draw_update_game_live` | ~40 `glGet*` + Push/PopAttrib + recomposição de tela inteira por frame no Play embutido | sync de GPU + 1 quad | média (só editor) | suspeito |
| LP11 | `Rasterizer/RAS_2DFilter.cpp:404-420` `BindTextures` | `MipmapTextures` 2× quando o shader usa as duas texturas; mipmap de slots não lidos (só com `filter.mipmap`) | `glGenerateMipmap` dobrado | baixa | suspeito |
| LP12 | `RAS_2DFilter.cpp:475-688`, `KX_RenderPipeline.cpp:672-762` | uniforms de filtro reenviados e parâmetros do World copiados todo frame | desprezível (1 draw) | baixa | suspeito |
| LP13 | `KX_SoundActuator.cpp:200-280` (complementa KX14) | `AUD_Handle_*` sem comparar; cada um trava mutex do device; `getStatus` 2× | baixo | baixa | suspeito |
| LP14 | `KX_KetsjiEngine.cpp:624-636` | varre todas as partículas GPU de todas as cenas por frame só p/ achar `debugUI` | O(partículas) | baixa | suspeito |

**Bug de correção à parte:** `RAS_2DFilter::ComputeTextureOffsets` (:389) roda uma vez só; com resize ou resolução
dinâmica, `bgl_TextureCoordinateOffset` fica com o tamanho antigo.

Verificados OK: offscreens principais e de filtro/bloom (comparam tamanho), shaders de filtro, resolução dinâmica e vsync,
profiler (`g_enabled`), overlays e desenho de debug (sob flag), screenshots, motion blur, rain mask, entrada
(`ClearInputs` inerente, joystick por evento), canvas, `ApplyAreaReverb` (bom exemplo de comparação).

## gpu / depsgraph (lado Blender)

O runtime não usa `draw/`, UBO nem depsgraph (nenhum `DEG_id_tag_update` em `gameengine/`): é o caminho GLSL 2.7x com
`glUniform*` direto e sem cache em `GPU_shader_uniform_vector`. Caminhos em `source/source/blender/gpu/` ou `gameengine/`.

| ID | Onde | Padrão | Custo | Confiança | Status |
|---|---|---|---|---|---|
| GP1 | `gpu/intern/gpu_material.c:5004` `GPU_material_bind_scene_lights`, via `Ketsji/BL_BlenderShader.cpp:266` | sobe 8 luzes × 11 uniforms (+ IES) por objeto, embora `ProcessLighting` já saiba que nada mudou | ~90 glUniform por objeto por passe | alta | medido 2026-10-09: 0 no RolimaRacer (sem lâmpada com sombra em buffer); ~880 GL/frame (~22 por draw) na cena `tools/debug/cenas/criar_cena_luzes_sombra.py` com 3 spots com sombra; **corrigido 2026-10-09** com cache do último valor no GPUShader: ~334 GL/frame contra ~902 sem o cache, com os 40 cubos visíveis (sobram os binds de textura de sombra) |
| GP2 | `gpu_material.c:4818` `GPU_material_bind_shadow_lamps`, via `BL_BlenderShader.cpp:260` | por objeto: `BLI_findptr`, bind de textura de sombra, persmat/bias; slots vazios fazem bind(0) | ~20-30 chamadas GL por objeto | alta | medido 2026-10-09: 0 no RolimaRacer (sem lâmpada com sombra em buffer); ~880 GL/frame (~22 por draw) na cena `tools/debug/cenas/criar_cena_luzes_sombra.py` com 3 spots com sombra; **corrigido 2026-10-09** com cache do último valor no GPUShader: ~334 GL/frame contra ~902 sem o cache, com os 40 cubos visíveis (sobram os binds de textura de sombra) |
| GP3 | `gpu_codegen.c:1741` → `gpu_texture.c:453` → `gpu_draw.c:497` `GPU_verify_image` | por bind de material: acquire ibuf (spinlock global), bind/unbind, `compare=0` anula atalho | ~4 GL + lock por textura, por material | média | suspeito |
| GP4 | `gpu_codegen.c:1774` `GPU_pass_update_uniforms` | reenvia todos os inputs dinâmicos a cada bind | por material × passe | média | suspeito |
| GP5 | `gpu_material.c:754` `GPU_material_bind` | recalcula `dynlayer` de todos lamps, `BLI_findlink`, view/proj por bind | baixo | baixa | suspeito |
| GP6 | `gpu_material.c:696` `GPU_material_update_lamps`, via `KX_BlenderMaterial.cpp:344` | recalcula matrizes do lamp por material (só dependem de lamp+view) | CPU, N_mat × N_lamps | média | suspeito |
| GP7 | `Ketsji/BL_BlenderShader.cpp:309-322` | `FindProbe` + bind de probe por objeto todo frame; cache só p/ probe ausente | médio | média | suspeito |
| GP8 | `gpu_material.c:5014` `GPU_material_use_damage` / `GPU_material_bind_damage`, `BL_BlenderShader.cpp:353` | cast apenas se uniform Damage ativo; count usa cache por GPUShader; arrays de hits continuam enviados | casts desnecessarios e count repetido eliminados | confirmada | corrigido; diferencial com programa compartilhado passou; benchmark/visual real pendentes |

Correção comum GP1/GP2: geração do estado de luz (incrementa só quando `ProcessLighting` recalcula) + "último enviado"
por `GPUMaterial`, zerado em `GPU_material_bind` — mesmo padrão de `objectlay_valid`.

Verificados OK: `GPU_material_bind_uniforms` (obmat etc. necessário; `GPU_OBJECT_LAY` já com cache), `ProcessLighting`,
`EnableLights`/`DisableLights`, `BL_Texture::CheckValidTexture`, `GPU_verify_image` não reenvia pixels, `GPU_material_world`,
`GPU_lamp_update` não roda por frame, cache de sombra estática (`RAS_OpenGLLight.cpp:450`).

Medição sugerida: contador de "uploads de uniform" em `CM_WorkCounters` nos escopos `GPU_RENDER_LIGHTS`/`GPU_RENDER_SHADOW`.

## Spawn, remoção, LibLoad, lote e conversão sob demanda

Custo por evento (spawn/remoção/carga), não por frame — mas vira por frame com Always em pulso ou spawns contínuos.

| ID | Onde | Padrão | Custo | Confiança | Status |
|---|---|---|---|---|---|
| SP1 | `Ketsji/KX_Scene.cpp:875` `AddNodeReplicaObject` | `BuildNavMesh()` chamado no original, não na cópia (bug + trabalho) | Recast inteiro por spawn | alta | suspeito |
| SP2 | `Ketsji/KX_GameObject.cpp:1386` `ReplaceMesh`; `KX_ReplaceMeshActuator.cpp:144` | Não compara com a malha atual; refaz mesh user + bounds a cada pulso | O(vértices) + VBO | alta | suspeito |
| SP3 | `CcdPhysicsController.cpp:2584` → `CcdPhysicsEnvironment.cpp:983` | Shape info compartilhado: recria shape de todas as cópias irmãs, sem saída para malha igual | O(controllers) + O(cópias×malha) | alta | suspeito |
| SP4 | `CcdPhysicsController.cpp:2947`; `CcdCookedData.cpp:340` | Hash do hull por cópia; sem `record` recalcula `btConvexHullComputer` por spawn | O(V) / O(V log V) | alta/média | suspeito |
| SP5 | `CcdPhysicsController.cpp:117-235` `shared_bvh_key` | Hash de todos os vértices/índices por spawn para achar BVH já compartilhada | O(V+F) | alta | suspeito |
| SP6 | `KX_Scene.cpp:1448` `NewRemoveObject`; `BaseListValue.cpp:82` | ~20 remoções lineares por objeto; `RemoveValue` não para ao achar | O(N)×20 por remoção | alta | suspeito |
| SP7 | `KX_Scene.cpp:1421` `DelayedRemoveObject`/`RemoveEuthanasyObjects` | AddIfNotFound O(K) + erase do front | O(K²) | alta | suspeito |
| SP8 | `Converter/BL_Converter.cpp:1420` `FreeBlendFileData` | `ReloadMaterials()` de todos os materiais sem checar luzes | recompila shaders | alta | suspeito |
| SP9 | `CcdPhysicsEnvironment.cpp:868` `RemoveCcdPhysicsController` | Varre todos os pares antes do Bullet fazer o mesmo | O(pares)×2 | média | suspeito |
| SP10 | `KX_GameObject.cpp:792` `SetupGPUParticlesBuffer` | Lê shader do disco, imagem, assa curvas em texturas novas, copia vértices por spawn; poll de reload por emissor | I/O + texturas | alta/média | suspeito |
| SP11 | `BL_Converter.cpp:228-423`; `BL_BlenderDataConversion.cpp:493` | Conversão sob demanda não reaproveita material/malha/shape existentes (quebra lote/instancing) | conversão + shader | média-alta | suspeito |
| SP12 | `KX_AddObjectActuator.cpp:278`; `KX_Scene.cpp:4140` | Modo propriedade busca linear no Main a cada disparo | O(objetos) | média | suspeito |
| SP13 | `Rasterizer/RAS_BatchDisplayArray.cpp:107` `Split` | Separar membro reenvia o VBO do lote inteiro; `RemoveObject` 2× | O(vértices do lote) | média-alta | suspeito |
| SP14 | `BL_Converter.cpp:800` `UnregisterMesh` | Por decal expirado percorre todos os objetos × malhas | O(N) | média | suspeito |
| SP15 | `KX_DestructionManager.cpp:740` `SpawnDecal` | Monta mesh user/bounds e logo refaz com `ReplaceMesh` | 2× | média | suspeito |

Menores: `ReplicateLogic` SearchValue O(N) por link externo; `RegisterObject` FindEntry linear; `RemoveStaticShadowCasterObject` com dirty incondicional (código morto); cópias nunca entram nas listas de shadow casters (verificar).

Relação: SP2/SP3 agravam KX5; SP13 é a outra metade de KX4; SP10 complementa KX14.

Conferido OK: buckets/display arrays reaproveitados no spawn; spawn não percorre a cena; BVH compartilhada; cache de shader de partículas; `RAS_ParticleBuffer::SetModelMatrix` trivial; `UpdateLod` compara; `RAS_MeshUser::SetMatrix` usa memcmp; merge de LibLoad proporcional ao carregado; merge async só recompila com luzes novas; mesmo .blend não recarrega.
