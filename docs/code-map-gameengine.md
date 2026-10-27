# Mapa de código — arquivos grandes do gameengine

Guia de navegação para achar rápido onde fica cada responsabilidade nos maiores arquivos do gameengine,
sem lê-los inteiros. Não descreve arquitetura nem decisões; é só um índice. Para `KX_GameObject.cpp`, veja
[code-map-kx-gameobject.md](code-map-kx-gameobject.md).

**Linhas conferidas em 2026-10-26 (`HEAD` `f4e37e60`).** As linhas são aproximadas e envelhecem a cada edição: use-as
como ponto de partida e confirme com `grep -n "Classe::Metodo"`. O agrupamento por domínio foi feito pelo nome
dos métodos e por fronteiras confirmadas no código (marcadas onde houve conferência); leia o trecho antes de
mudar algo com base neste mapa.

Caminhos abaixo relativos a `source/source/gameengine/`.

---

## `Ketsji/KX_Scene.cpp` (4.709 linhas)

Cena em execução: dona dos objetos, listas de render, câmera ativa e bindings Python. Cutscene e Trace Rail ficam em
`Ketsji/KX_SceneCutscene.cpp` (mesma classe `KX_Scene`). O header é
`Ketsji/KX_Scene.h` (864 linhas).

| Domínio | Métodos (linha inicial) |
|---|---|
| Ciclo de vida da cena | funções `static` de réplica/destruição/atualização do SceneGraph 127–150, construtor 162, destrutor 334 |
| Acessores e listas | `GetName`/`SetName` 792–797, managers e listas (`GetObjectList`, `GetLightList`, `GetCameraList`, `GetRenderList`, `GetLogicManager`…) 852–917, framing 515–520 |
| Mundo, sol e terremoto | `Set/GetWorldInfo` 525–530, `SetWorldSun`/`GetWorldSun`/`SetAutoWorldSun`/`UpdateAutoWorldSun` 913–934, `UpdateEarthquake` 983 |
| Suspensão e culling (config) | `Suspend`/`Resume`/`IsSuspended` 1092–1107, `SetActivityCulling` 1087, `Set/GetDbvtCulling` e oclusão 719–734 |
| Objetos: criação/réplica/grupos | `AddNodeReplicaObject` 1145, `ReplicateLogic` 1347, `DupliGroupRecurse` 1433, `IsObjectInGroup` 1575, `FindInactiveObjectAcrossScenes` 1580, `AddReplicaObject` 1627 |
| Objetos: remoção | `RemoveNodeDestructObject` 1135, `RemoveObject` 1725, `RemoveDupliGroup` 1738, `DelayedRemoveObject` 1747, `RemoveEuthanasyObjects` 1754, `NewRemoveObject` 1774 |
| Câmera e estatísticas de culling | `Get/SetActiveCamera` 1450–1468, contadores `GetLast*` 1474–1504, `Get/SetOverrideCullingCamera` 1511–1516, `SetCameraOnTop` 2014 |
| Culling e listas visíveis | `PhysicsCullingCallback` 2035, `CalculateVisibleMeshes` 2054–2077, `UpdateObjectActivity` 3313 |
| Debug (desenho e ImGui) | `GetDebugDraw` 2256, `DrawDebug` 2261, `RenderDebugProperties` 2298, `RenderDebugPropertiesImGui` 2351, `FlushDebugDraw` 2497, `AddObjectDebugProperties` 1117 |
| Frame lógico | `LogicBeginFrame` 2502, `LogicUpdateFrame` 2789, `LogicEndFrame` 2815, `UpdateParents` 2838 |
| Animação | `AddAnimatedObject` 2519, `UpdateAnimPoseTask` 2607, `UpdateAnimDeformTask` 2634, `UpdateAnimations` 2663, `UpdateAnimationDeformers` 2778 |
| Render | `RenderBuckets` 2861, `RenderTextureRenderers` 2874, `Get2DFilterManager` 3624, `Render2DFilters` 3629 |
| LOD | `UpdateObjectLods` 2880, hysteresis 2185–2200 |
| Partículas GPU | `UpdateGpuParticleEmitters` 3001, listas de emissores/colisores 2219–2250 |
| Sombras (listas) | casters estáticos/dinâmicos e flag "dirty" 2255–2298 |
| Física e rede | `Get/SetPhysicsEnvironment` 2339–2344, gravidade 2353–2358, `Get/SetNetworkMessageScene` 2329–2334, `Get/SetSuspendedDelta` 2363–2368 |
| Merge de cenas | `MergeScene_LogicBrick` 3388, `MergeScene_GameObject` 3411, `MergeScene` 3486 |
| Iluminação (flag) | `Get/SetUseLightScatter` 2582–2587 |
| Cutscene e Trace Rail (em `Ketsji/KX_SceneCutscene.cpp`, 901 linhas) | `SetCutsceneManager` 153, `StopCutscene` 164, `RestartCutscene` 174, `UpdateCutscene` 185, `StartTraceRail` 241, `StartTraceRailOrigin` 295, `UpdateTraceRail` 361, `UpdateCutscenePaths` 467, `TakePendingCutsceneEvents` 518, `DispatchCutsceneEvents` 574 (~300 linhas), `ClearCutsceneSpawnedObjects` 877, `GetCutsceneManager` 893 |
| Busca e texto (`static`, em `KX_SceneCutscene.cpp`) | `FindObjectWithComponent` 526, `FindGameObject` 548, `GetLocalizedText` 566 |
| Callbacks de Python | `RunDrawingCallbacks` 3700, `RunOnRemoveCallbacks` 3716 |
| Bindings Python (3014–fim) | `Type` 3043, `Methods[]` 3068, `Attributes[]` 3441, `Map_*`/`Seq_Contains` (`static`) 3085–3186, `pyattr_*` 3225–3428, métodos (`addObject` 3466, `end`, `restart`, `replace`, `suspend`, `resume`, `play_cutscene`, `get`…) 3466–3692, `ConvertPythonToScene` 4653 |

Observações: `DispatchCutsceneEvents` e `AddReplicaObject` são as funções mais longas; a remoção de objetos tem
cinco caminhos (`RemoveObject`, `DelayedRemoveObject`, `RemoveEuthanasyObjects`, `NewRemoveObject`,
`RemoveDupliGroup`) e convém ler todos antes de mexer em um deles.

---

## `Ketsji/KX_PythonInit.cpp` (3.862 linhas)

Bootstrap do Python embutido e módulos `Range`/`bge`. O registro dos **tipos** (`KX_GameObject`, `KX_Scene`…)
não está aqui: fica em `Ketsji/KX_PythonInitTypes.cpp`. Há código específico de Web (`__EMSCRIPTEN__`) em 69,
3151 e 3243–3281.

| Domínio | Funções (linha inicial) |
|---|---|
| Utilitários do módulo `Range` (funções globais `gPy*`) | aleatório/gravidade/caminho 214–243, `gPyStartGame`/`EndGame`/`RestartGame` 261–289, `SaveGlobalDict`/`LoadGlobalDict` 300–318, `GetProfileInfo` 336, `SendMessage` 349, `GetSpectrum` 372 |
| Taxas e relógio | tic rate, render rate, animation rate, exit key, max frames, clock/time scale 384–602 |
| Lista de arquivos e cenas | `.blend`/`.range`/`.rasec` 607–660, `AddScene`/`GetCurrentScene`/`GetSceneList` 671–707 |
| Informação de sistema | `pyPrintStats` 837, GPU vendor/renderer 722–735, CPU 749–759, `pyPrintExt` 919 |
| Bibliotecas externas | `gLibLoad` 938, `gLibNew` 1157, `gLibFree` 1211, `gLibList` 1227, `gPyNextFrame` 1253 |
| Tabela `game_methods[]` | 997 |
| Janela, mouse, estéreo, screenshot | `gPyGetWindowHeight`… 1388–1582 |
| Render (GLSL, AA, filtro, vsync, `drawLine`) | motion blur 1273–1290, GLSL 1302–1398, anisotropia/AA/mipmap/vsync 1413–1577, `gPyDrawLine` 1893, janela/fullscreen 1507–1524 |
| Áudio e debug na tela | `MasterVolume` 1585–1597, `ShowFramerate`/`ShowProfile`/`ShowProperties`/`AutoDebugList` 1606–1650, `GetDisplayDimensions` 1660 |
| Tabela `rasterizer_methods[]` | 1679 |
| Módulo lógica (`GameLogic`) | `GameLogic_module_def` 1748, `initGameLogicPythonBinding` 2262 (~430 linhas, constantes de tipos/estados) |
| Ambiente `sys` e caminhos | `backupPySysObjects` 2692 … `restorePySysObjects` 2767, `appendPythonPath` 2795, `addImportMain`/`removeImportMain` 2806–2811 |
| Módulo `Range` e compatibilidade | `addSubModule` 2828, `initRANGE` 2836, `RANGE_module_def` 2310, `installLegacyCollectionsAliases` 2874, `installLegacyAudFactoryAlias` 2928 (alias `bge`/`aud`) |
| Init/saída do Python | `initPlayerPython` 2976, `exitPlayerPython` 3016, console 2528–2595, `initGamePython` 3107, `exitGamePython` 3201 |
| Console e joystick | `createPythonConsole` 3223, `getPythonJoystick` 3235, `updatePythonJoysticks` 3240 |
| Módulo `Rasterizer` | `initRasterizerPythonBinding` 3281 |
| Teclas | `gPyEventToString`/`ToCharacter` 2775–2812, `initGameKeysPythonBinding` 3415 (~190 linhas de constantes) |
| Módulo `Application` | `initApplicationPythonBinding` 3610 |
| Config persistente do jogo | `saveGamePythonConfig` 3672, `loadGamePythonConfig` 3751, `pathGamePythonConfig` 3828 (contém código Web/IDBFS) |

Observação: `initPlayerPython` (editor não usa) é o caminho do standalone; o editor entra por `BPY_python_start`.

---

## `Physics/Bullet/CcdPhysicsEnvironment.cpp` (4.105 linhas)

Ambiente físico Bullet. O header é `CcdPhysicsEnvironment.h` (391 linhas). `m_dynamicsWorld` é membro do
ambiente; o callback de subtick é registrado no construtor com `this`.

| Domínio | Conteúdo (linha inicial) |
|---|---|
| Classes auxiliares de veículo | `VehicleClosestRayResultCallback` 100, `BlenderVehicleRaycaster` 146, `WrapperVehicle` 198 |
| Filtro de broadphase | `CcdOverlapFilterCallBack` 621 |
| Ciclo de vida do ambiente | `SetDebugDrawer` 695, construtor 646, `MergeEnvironment` 2529 |
| Controllers e constraints (add/remove) | `AddCcdPhysicsController` 752, `RemoveConstraint` 809, `RemoveVehicle` 842–851, `RestoreConstraint` 884, `RemoveCcdPhysicsController` 918, `Update/RefreshCcdPhysicsController` 882–915, graphic controllers 931–952, `UpdateCcdPhysicsControllerShape` 1049 |
| Simulação (passo) | `DebugDrawWorld` 1061, subticks 980–987, `ProceedDeltaTime` 1084, `ProceedDeltaTimeCar` 1161, `ProcessFhSprings` 1245 |
| Parâmetros do mundo | `SetDebugMode`… `SetSolverType` 1527–1677 (iterações, erp/cfm, sleeping, slop, ccd), `Get/SetGravity` 1447–1452, `WakeAllBodies` 1575 |
| Constraints (consulta) | `RemoveConstraintById` 1588, `GetConstraintById` 2596 |
| Raycast e consulta de esfera | `GetHitTriangle` 1660, `RayTest` 1701, `SphereQuery` 2413 (broadphase `aabbTest`, usado pelo `scene.explode()`) |
| **Oclusão em software (não é física)** | `struct OcclusionBuffer` 1740 (~520 linhas, rasterizador de oclusão), `DbvtCullingCallback` 2262, `CullingTest` 2482 |
| Contatos e broadphase | `GetNumContactPoints` 2510, `GetBroadphase`/`GetDispatcher` 2524–2529 |
| Sensores e callbacks de colisão | `AddSensor` 2614, `Add/RemoveCollisionCallback` 2460–2471, `CallbackTriggers` 2643, `CheckCollision` 2699, `needBroadphaseCollision` 2739 |
| Veículos e personagem | `GetVehicleConstraint`/`GetNumVehicles`/`GetVehicleFromIndex` 2802–2822, `GetCharacterController` 2810, `CreateVehicle` 3153, `DestroyVehicle` 3178 |
| Criação de shapes | `CreateSphereController` 2817, `CreateConeController` 3187, `Ccd_FindClosestNode` 2844 |
| Constraints (criação) | `CreateConstraint` 2861 (~290 linhas) |
| Exportação e fábrica | `getAppliedImpulse` 3106, `ExportFile` 3234, `Create` 3298 |
| Conversão de objeto | `ConvertObject` 3323 (~530 linhas), `SetupObjectConstraints` 3935 |
| Dados de colisão | `CcdCollData` 4022–4078 (contatos, atrito, restituição) |

Observação: ~520 linhas de `OcclusionBuffer` estão neste arquivo sem relação com o mundo Bullet; é o candidato
mais óbvio a viver em outro arquivo se um dia dividirem esse `.cpp`.

---

## `Physics/Bullet/CcdPhysicsController.cpp` (3.276 linhas)

Um corpo físico (rigid/soft/personagem) e seus motion states. O header é `CcdPhysicsController.h` (1.016 linhas).

| Domínio | Conteúdo (linha inicial) |
|---|---|
| Personagem | `CcdCharacter` 362–489 (pulo, caminhada, velocidade de queda, inclinação máxima) |
| Ciclo de vida | construtor 199, `PostProcessReplica` 1287, `SetPhysicsEnvironment` 1352, `GetReplica` 2631, `GetReplicaForSensors` 2638 |
| Constraints (referências) | `add/remove/getCcdConstraintRef` 236–254 |
| Motion state e transformação | `GetTransformFromMotionState` 614, `SetCenterOfMassOffset` 676, `SimulationTick` 1173, `SynchronizeMotionStates` 1210, `Write*ToDynamics/MotionState` 849–855, `SetTransform`, posição/orientação/escala 936–1185, `DefaultMotionState` 2741–2787 |
| Criação de corpos | `CreateSoftbody` 719 (~200 linhas), `CreateCharacterController` 956, `CreateRigidbody` 983 |
| Shapes | `DeleteBulletShape` 1055, `DeleteControllerShape` 1071, `ReplaceControllerShape` 1092, `ReinstancePhysicsShape` 2689, `ReplacePhysicsShape` 2714, `CreateBulletShape` 3017 (~160 linhas), `AddShape` 3245, `UpdateMesh` 2823 (~170 linhas), `FindMesh` 2787 |
| Compound | `AddCompoundChild` 2500, `RemoveCompoundChild` 2577 |
| Suspensão | `SuspendPhysics`/`RestorePhysics` 1556–1561, `SuspendDynamics`/`RestoreDynamics` 1647–1670, `IsPhysicsSuspended` 2674 |
| Massa, atrito, forças, velocidades | 1185–1421 e 1791–1840 |
| Colisão | group/mask 1425–1440, `SetActive` 2014, `RefreshCollisions` 1531 |
| Damping e CCD | 1445–1495 |
| **Soft body (parâmetros)** | `SetSoft*` e coeficientes 1506–1776 (~270 linhas de setters quase idênticos) |
| Sleeping | `UpdateDeactivation` 2479, `WantsSleeping` 2487 |

---

## `Converter/BL_BlenderDataConversion.cpp` (4.057 linhas)

Conversão do `.blend` para objetos do runtime. O header é `BL_BlenderDataConversion.h` (100 linhas).

| Domínio | Funções (linha inicial) |
|---|---|
| Utilitários | `BL_ConvertKeyCode` 455, `BL_GetUvRgba` 460 |
| Materiais e malhas | `BL_ConvertMaterial` 500, `BL_ConvertMesh` 635, `BL_ComputeVertexBoneData` 797, `BL_ConvertDerivedMeshToArray` 1158 |
| Deformers e ações | `BL_ConvertDeformer` 1714, `BL_ConvertAction(s)` 834–843 |
| Física e gráfico | `BL_CreateGraphicObjectNew` 1839, `BL_CreatePhysicsObjectNew` 1867 |
| LOD, animação, culling | `BL_LodManagerFromBlenderObject` 1916, `BL_AnimationEventManagerFromBlenderObject` 1932, `activityCullingInfoFromBlenderObject` 1946 |
| Luz, câmera, speaker | `BL_GameLightFromBlenderLamp` 1979, `BL_GameCameraFromBlenderCamera` 2049, `BL_SpeakerFromBlenderSpeaker` 2130 |
| Objeto de jogo | `BL_GameObjectFromBlenderObject` 2227 (~180 linhas) |
| Pose, constraints, fundo | `BL_GetActivePoseChannel` 2458, `BL_GetActiveConstraint` 2473, `BL_SetBlenderSceneBackground` 2496 |
| Componentes e cutscene | `BL_ConvertComponentsObject` 2507, `BL_ConvertCutscene` 2730 |
| Conversão de objeto único | `bl_ConvertBlenderObject_Single` 2592 |
| **Passagem principal** | `BL_ConvertBlenderObjects` 2799–3498 (**uma função de ~700 linhas** que converte os objetos da cena) |
| Pós-conversão e cursor | `BL_PostConvertBlenderObjects` 3841, `BL_ConvertCustomMouseCursor` 4036 |

Observação: `BL_ConvertBlenderObjects` concentra a conversão numa só função; mudanças aqui exigem ler o
trecho inteiro, não só um método.

---

## `Ketsji/KX_KetsjiEngine.cpp` (1.632 linhas)

Laço do jogo: tempo, frames lógicos/físicos, cenas. O desenho em si fica em `KX_RenderPipeline.cpp` (abaixo).

| Domínio | Métodos (linha inicial) |
|---|---|
| Construção e serviços | `KX_KetsjiEngine` 189, `SetCanvas` 327, `SetRasterizer` 333, `SetConverter` 421, `StartEngine` 453, `StopEngine` 1128 |
| Frame | `BeginFrame` 494, `EndFrame` 518, `UpdateDynamicResolution` 599, **`NextFrame`** 689 (lógica, física, animação), `Render` 1056 |
| Tempo e espera | `ServerSleep` 908, `SleepUnderRate` 921, `UpdateSleepTime` 934, `ClockTiming` 1174, `FrameTiming` 1210, `AdvanceStepTime` 1223 |
| Animação e sombra | `UpdateAnimations` 1114, `IsStaticShadowSettled` 1123 |
| Cenas | `AddScene` 1168, `ConvertAndAddScene` 1267, `PreloadScene` 1272, `RemoveScene` 1277, `ReplaceScene` 1292, `SuspendScene` 1297, `ResumeScene` 1302 |
| Taxas e flags | `SetTicRate` 1328, `SetUseFixedTimestep` 1400, `SetShadowCulling` 1427, `SetDynamicResolution` 1432 |

## `Ketsji/KX_RenderPipeline.cpp` (1.224 linhas)

| Domínio | Funções (linha inicial) |
|---|---|
| Névoa volumétrica | `KX_FillVolumetricFog` 125 |
| Frame | **`Render`** 375 (sombras, câmeras, filtros), `RenderCollisionDepthBuffer` 555 |
| Câmeras e visibilidade | `GetCameraRenderData` 598, `GetRenderData` 644, `GetVisibleMeshes` 738, `RenderCamera` 783 |
| Pós-render | `PostRenderScene` 929 (2D filters, offscreen final) |

## `Converter/BL_Converter.cpp` (1.973 linhas)

Conversão de cenas e LibLoad (síncrono e assíncrono). A conversão objeto a objeto fica em
`BL_BlenderDataConversion.cpp` (acima).

| Domínio | Métodos (linha inicial) |
|---|---|
| Cena | `ConvertScene` 682, `CompileSceneShaders` 721, `ConvertScene` 911, `PostConvertScene` 1018, `RemoveScene` 1023 |
| Objetos sob demanda | `FindOrConvertMainObject` 253, `FindSceneObject` 298, `ConvertSceneObject` 310, `FreeUnconvertedData` 470 |
| LibLoad | `LinkBlendFileMemory` 1421, `LinkBlendFilePath` 1429, **`LinkBlendFile`** 1458, `FreeBlendFileData` 1625, `FreeBlendFile` 1748 |
| Merge e assíncrono | `StepMerge` 1141, `StepReloads` 1268, `ProcessScheduledLibraries` 1309, `FinalizeAsyncLoads` 1350, `AsyncConvertTask` 1381, `MergeSceneData` 1779, `MergeScene` 1793 |
| Shaders e malhas | `ReloadShaders` 1827, `ConvertMeshSpecial` 1865 |
