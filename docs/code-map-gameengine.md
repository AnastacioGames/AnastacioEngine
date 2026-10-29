# Mapa de código — arquivos grandes do gameengine

Guia de navegação para achar rápido onde fica cada responsabilidade nos maiores arquivos do gameengine,
sem lê-los inteiros. Não descreve arquitetura nem decisões; é só um índice. Para `KX_GameObject.cpp`, veja
[code-map-kx-gameobject.md](code-map-kx-gameobject.md).

**Linhas conferidas em 2026-10-29 (`HEAD` `fb2e4645`).** As linhas são aproximadas e envelhecem a cada edição: use-as
como ponto de partida e confirme com `grep -n "Classe::Metodo"`. O agrupamento por domínio foi feito pelo nome
dos métodos e por fronteiras confirmadas no código (marcadas onde houve conferência); leia o trecho antes de
mudar algo com base neste mapa.

Caminhos abaixo relativos a `source/source/gameengine/`.

---

## `Ketsji/KX_Scene.cpp` (4.744 linhas)

Cena em execução: dona dos objetos, listas de render, câmera ativa e bindings Python. Cutscene e Trace Rail ficam em
`Ketsji/KX_SceneCutscene.cpp` (mesma classe `KX_Scene`). O header é
`Ketsji/KX_Scene.h` (870 linhas).

| Domínio | Métodos (linha inicial) |
|---|---|
| Ciclo de vida da cena | funções `static` de réplica/destruição/atualização do SceneGraph 127–150, construtor 162, destrutor 334 |
| Acessores e listas | `GetName`/`SetName` 795–800, managers e listas (`GetObjectList`, `GetLightList`, `GetCameraList`, `GetRenderList`, `GetLogicManager`…) 855–920, framing 515–520 |
| Mundo, sol e terremoto | `Set/GetWorldInfo` 525–530, `SetWorldSun`/`GetWorldSun`/`SetAutoWorldSun`/`UpdateAutoWorldSun` 916–937, `UpdateEarthquake` 986 |
| Suspensão e culling (config) | `Suspend`/`Resume`/`IsSuspended` 1095–1110, `SetActivityCulling` 1090, `Set/GetDbvtCulling` e oclusão 719–734 |
| Objetos: criação/réplica/grupos | `AddNodeReplicaObject` 1148, `ReplicateLogic` 1350, `DupliGroupRecurse` 1436, `IsObjectInGroup` 1578, `FindInactiveObjectAcrossScenes` 1583, `AddReplicaObject` 1630 |
| Objetos: remoção | `RemoveNodeDestructObject` 1138, `RemoveObject` 1728, `RemoveDupliGroup` 1741, `DelayedRemoveObject` 1750, `RemoveEuthanasyObjects` 1757, `NewRemoveObject` 1777 |
| Câmera e estatísticas de culling | `Get/SetActiveCamera` 1450–1468, contadores `GetLast*` 1474–1504, `Get/SetOverrideCullingCamera` 1511–1516, `SetCameraOnTop` 2017 |
| Culling e listas visíveis | `PhysicsCullingCallback` 2038, `CalculateVisibleMeshes` 2057–2080, `UpdateObjectActivity` 3347 |
| Debug (desenho e ImGui) | `GetDebugDraw` 2259, `DrawDebug` 2264, `RenderDebugProperties` 2301, `RenderDebugPropertiesImGui` 2354, `FlushDebugDraw` 2500, `AddObjectDebugProperties` 1120 |
| Frame lógico | `LogicBeginFrame` 2505, `LogicUpdateFrame` 2821, `LogicEndFrame` 2847, `UpdateParents` 2870 |
| Animação | `AddAnimatedObject` 2522, `UpdateAnimPoseTask` 2610, `UpdateAnimDeformTask` 2637, `UpdateAnimations` 2701, `UpdateAnimationDeformers` 2812 |
| Render | `RenderBuckets` 2893, `RenderTextureRenderers` 2908, `Get2DFilterManager` 3658, `Render2DFilters` 3663 |
| LOD | `UpdateObjectLods` 2914, hysteresis 2185–2200 |
| Partículas GPU | `UpdateGpuParticleEmitters` 3035, listas de emissores/colisores 2219–2250 |
| Sombras (listas) | casters estáticos/dinâmicos e flag "dirty" 2255–2298 |
| Física e rede | `Get/SetPhysicsEnvironment` 2339–2344, gravidade 2353–2358, `Get/SetNetworkMessageScene` 2329–2334, `Get/SetSuspendedDelta` 2363–2368 |
| Merge de cenas | `MergeScene_LogicBrick` 3422, `MergeScene_GameObject` 3445, `MergeScene` 3520 |
| Iluminação (flag) | `Get/SetUseLightScatter` 2582–2587 |
| Cutscene e Trace Rail (em `Ketsji/KX_SceneCutscene.cpp`, 901 linhas) | `SetCutsceneManager` 153, `StopCutscene` 164, `RestartCutscene` 174, `UpdateCutscene` 185, `StartTraceRail` 241, `StartTraceRailOrigin` 295, `UpdateTraceRail` 361, `UpdateCutscenePaths` 467, `TakePendingCutsceneEvents` 518, `DispatchCutsceneEvents` 574 (~300 linhas), `ClearCutsceneSpawnedObjects` 877, `GetCutsceneManager` 893 |
| Busca e texto (`static`, em `KX_SceneCutscene.cpp`) | `FindObjectWithComponent` 526, `FindGameObject` 548, `GetLocalizedText` 566 |
| Callbacks de Python | `RunDrawingCallbacks` 3734, `RunOnRemoveCallbacks` 3750 |
| Bindings Python (3014–fim) | `Type` 3043, `Methods[]` 3068, `Attributes[]` 3441, `Map_*`/`Seq_Contains` (`static`) 3085–3186, `pyattr_*` 3225–3428, métodos (`addObject` 3466, `end`, `restart`, `replace`, `suspend`, `resume`, `play_cutscene`, `get`…) 3466–3692, `ConvertPythonToScene` 4688 |

Observações: `DispatchCutsceneEvents` e `AddReplicaObject` são as funções mais longas; a remoção de objetos tem
cinco caminhos (`RemoveObject`, `DelayedRemoveObject`, `RemoveEuthanasyObjects`, `NewRemoveObject`,
`RemoveDupliGroup`) e convém ler todos antes de mexer em um deles.

---

## `Ketsji/KX_PythonInit.cpp` (3.889 linhas)

Bootstrap do Python embutido e módulos `Range`/`bge`. O registro dos **tipos** (`KX_GameObject`, `KX_Scene`…)
não está aqui: fica em `Ketsji/KX_PythonInitTypes.cpp`. Há código específico de Web (`__EMSCRIPTEN__`) em 69,
3151 e 3243–3281.

| Domínio | Funções (linha inicial) |
|---|---|
| Utilitários do módulo `Range` (funções globais `gPy*`) | aleatório/gravidade/caminho 214–243, `gPyStartGame`/`EndGame`/`RestartGame` 261–289, `SaveGlobalDict`/`LoadGlobalDict` 300–318, `GetProfileInfo` 336, `SendMessage` 349, `GetSpectrum` 372 |
| Taxas e relógio | tic rate, render rate, animation rate, exit key, max frames, clock/time scale 384–602 |
| Lista de arquivos e cenas | `.blend`/`.range`/`.rasec` 607–660, `AddScene`/`GetCurrentScene`/`GetSceneList` 671–707 |
| Informação de sistema | `pyPrintStats` 862, GPU vendor/renderer 722–735, CPU 749–759, `pyPrintExt` 944 |
| Bibliotecas externas | `gLibLoad` 963, `gLibNew` 1182, `gLibFree` 1236, `gLibList` 1252, `gPyNextFrame` 1278 |
| Tabela `game_methods[]` | 997 |
| Janela, mouse, estéreo, screenshot | `gPyGetWindowHeight`… 1415–1609 |
| Render (GLSL, AA, filtro, vsync, `drawLine`) | motion blur 1273–1290, GLSL 1302–1398, anisotropia/AA/mipmap/vsync 1413–1577, `gPyDrawLine` 1920, janela/fullscreen 1507–1524 |
| Áudio e debug na tela | `MasterVolume` 1585–1597, `ShowFramerate`/`ShowProfile`/`ShowProperties`/`AutoDebugList` 1606–1650, `GetDisplayDimensions` 1660 |
| Tabela `rasterizer_methods[]` | 1679 |
| Módulo lógica (`GameLogic`) | `GameLogic_module_def` 1748, `initGameLogicPythonBinding` 2289 (~430 linhas, constantes de tipos/estados) |
| Ambiente `sys` e caminhos | `backupPySysObjects` 2719 … `restorePySysObjects` 2794, `appendPythonPath` 2822, `addImportMain`/`removeImportMain` 2833–2838 |
| Módulo `Range` e compatibilidade | `addSubModule` 2855, `initRANGE` 2863, `RANGE_module_def` 2310, `installLegacyCollectionsAliases` 2901, `installLegacyAudFactoryAlias` 2955 (alias `bge`/`aud`) |
| Init/saída do Python | `initPlayerPython` 3003, `exitPlayerPython` 3043, console 2528–2595, `initGamePython` 3134, `exitGamePython` 3228 |
| Console e joystick | `createPythonConsole` 3250, `getPythonJoystick` 3262, `updatePythonJoysticks` 3267 |
| Módulo `Rasterizer` | `initRasterizerPythonBinding` 3308 |
| Teclas | `gPyEventToString`/`ToCharacter` 2775–2812, `initGameKeysPythonBinding` 3442 (~190 linhas de constantes) |
| Módulo `Application` | `initApplicationPythonBinding` 3637 |
| Config persistente do jogo | `saveGamePythonConfig` 3699, `loadGamePythonConfig` 3778, `pathGamePythonConfig` 3855 (contém código Web/IDBFS) |

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

## `Ketsji/KX_KetsjiEngine.cpp` (1.765 linhas)

Laço do jogo: tempo, frames lógicos/físicos, cenas. O desenho em si fica em `KX_RenderPipeline.cpp` (abaixo).

| Domínio | Métodos (linha inicial) |
|---|---|
| Construção e serviços | `KX_KetsjiEngine` 191, `SetCanvas` 331, `SetRasterizer` 337, `SetConverter` 425, `StartEngine` 457, `StopEngine` 1237 |
| Frame | `BeginFrame` 498, `EndFrame` 525, `UpdateDynamicResolution` 610, **`NextFrame`** 700 (lógica, física, animação), `Render` 1087 |
| Tempo e espera | `ServerSleep` 927, `SleepUnderRate` 921, `UpdateSleepTime` 992, `ClockTiming` 1283, `FrameTiming` 1319, `AdvanceStepTime` 1332 |
| Animação e sombra | `UpdateAnimations` 1223, `IsStaticShadowSettled` 1232 |
| Cenas | `AddScene` 1277, `ConvertAndAddScene` 1379, `PreloadScene` 1384, `RemoveScene` 1389, `ReplaceScene` 1404, `SuspendScene` 1409, `ResumeScene` 1414 |
| Taxas e flags | `SetTicRate` 1440, `SetUseFixedTimestep` 1533, `SetShadowCulling` 1560, `SetDynamicResolution` 1565 |

## `Ketsji/KX_RenderPipeline.cpp` (1.242 linhas)

| Domínio | Funções (linha inicial) |
|---|---|
| Névoa volumétrica | `KX_FillVolumetricFog` 125 |
| Frame | **`Render`** 375 (sombras, câmeras, filtros), `RenderCollisionDepthBuffer` 558 |
| Câmeras e visibilidade | `GetCameraRenderData` 601, `GetRenderData` 647, `GetVisibleMeshes` 745, `RenderCamera` 790 |
| Pós-render | `PostRenderScene` 946 (2D filters, offscreen final) |

## `Converter/BL_Converter.cpp` (1.979 linhas)

Conversão de cenas e LibLoad (síncrono e assíncrono). A conversão objeto a objeto fica em
`BL_BlenderDataConversion.cpp` (acima).

| Domínio | Métodos (linha inicial) |
|---|---|
| Cena | `ConvertScene` 688, `CompileSceneShaders` 727, `ConvertScene` 917, `PostConvertScene` 1024, `RemoveScene` 1029 |
| Objetos sob demanda | `FindOrConvertMainObject` 253, `FindSceneObject` 298, `ConvertSceneObject` 310, `FreeUnconvertedData` 470 |
| LibLoad | `LinkBlendFileMemory` 1427, `LinkBlendFilePath` 1435, **`LinkBlendFile`** 1464, `FreeBlendFileData` 1631, `FreeBlendFile` 1754 |
| Merge e assíncrono | `StepMerge` 1147, `StepReloads` 1274, `ProcessScheduledLibraries` 1315, `FinalizeAsyncLoads` 1356, `AsyncConvertTask` 1387, `MergeSceneData` 1785, `MergeScene` 1799 |
| Shaders e malhas | `ReloadShaders` 1833, `ConvertMeshSpecial` 1871 |
