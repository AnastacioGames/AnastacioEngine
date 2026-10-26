# Mapa de código — arquivos grandes do gameengine

Guia de navegação para achar rápido onde fica cada responsabilidade nos maiores arquivos do gameengine,
sem lê-los inteiros. Não descreve arquitetura nem decisões; é só um índice. Para `KX_GameObject.cpp`, veja
[code-map-kx-gameobject.md](code-map-kx-gameobject.md).

**Linhas conferidas em 2026-10-26 (`HEAD` `1a63417a`).** As linhas são aproximadas e envelhecem a cada edição: use-as
como ponto de partida e confirme com `grep -n "Classe::Metodo"`. O agrupamento por domínio foi feito pelo nome
dos métodos e por fronteiras confirmadas no código (marcadas onde houve conferência); leia o trecho antes de
mudar algo com base neste mapa.

Caminhos abaixo relativos a `source/source/gameengine/`.

---

## `Ketsji/KX_Scene.cpp` (4.697 linhas)

Cena em execução: dona dos objetos, listas de render, câmera ativa e bindings Python. Cutscene e Trace Rail ficam em
`Ketsji/KX_SceneCutscene.cpp` (mesma classe `KX_Scene`). O header é
`Ketsji/KX_Scene.h` (862 linhas).

| Domínio | Métodos (linha inicial) |
|---|---|
| Ciclo de vida da cena | funções `static` de réplica/destruição/atualização do SceneGraph 127–150, construtor 162, destrutor 334 |
| Acessores e listas | `GetName`/`SetName` 791–796, managers e listas (`GetObjectList`, `GetLightList`, `GetCameraList`, `GetRenderList`, `GetLogicManager`…) 851–916, framing 515–520 |
| Mundo, sol e terremoto | `Set/GetWorldInfo` 525–530, `SetWorldSun`/`GetWorldSun`/`SetAutoWorldSun`/`UpdateAutoWorldSun` 912–933, `UpdateEarthquake` 982 |
| Suspensão e culling (config) | `Suspend`/`Resume`/`IsSuspended` 1091–1106, `SetActivityCulling` 1086, `Set/GetDbvtCulling` e oclusão 719–734 |
| Objetos: criação/réplica/grupos | `AddNodeReplicaObject` 1144, `ReplicateLogic` 1346, `DupliGroupRecurse` 1432, `IsObjectInGroup` 1574, `FindInactiveObjectAcrossScenes` 1579, `AddReplicaObject` 1626 |
| Objetos: remoção | `RemoveNodeDestructObject` 1134, `RemoveObject` 1724, `RemoveDupliGroup` 1737, `DelayedRemoveObject` 1746, `RemoveEuthanasyObjects` 1753, `NewRemoveObject` 1773 |
| Câmera e estatísticas de culling | `Get/SetActiveCamera` 1450–1468, contadores `GetLast*` 1474–1504, `Get/SetOverrideCullingCamera` 1511–1516, `SetCameraOnTop` 2010 |
| Culling e listas visíveis | `PhysicsCullingCallback` 2031, `CalculateVisibleMeshes` 2050–2073, `UpdateObjectActivity` 3301 |
| Debug (desenho e ImGui) | `GetDebugDraw` 2252, `DrawDebug` 2257, `RenderDebugProperties` 2294, `RenderDebugPropertiesImGui` 2347, `FlushDebugDraw` 2493, `AddObjectDebugProperties` 1116 |
| Frame lógico | `LogicBeginFrame` 2498, `LogicUpdateFrame` 2777, `LogicEndFrame` 2803, `UpdateParents` 2826 |
| Animação | `AddAnimatedObject` 2515, `UpdateAnimPoseTask` 2603, `UpdateAnimDeformTask` 2630, `UpdateAnimations` 2659, `UpdateAnimationDeformers` 2766 |
| Render | `RenderBuckets` 2849, `RenderTextureRenderers` 2862, `Get2DFilterManager` 3612, `Render2DFilters` 3617 |
| LOD | `UpdateObjectLods` 2868, hysteresis 2185–2200 |
| Partículas GPU | `UpdateGpuParticleEmitters` 2989, listas de emissores/colisores 2219–2250 |
| Sombras (listas) | casters estáticos/dinâmicos e flag "dirty" 2255–2298 |
| Física e rede | `Get/SetPhysicsEnvironment` 2339–2344, gravidade 2353–2358, `Get/SetNetworkMessageScene` 2329–2334, `Get/SetSuspendedDelta` 2363–2368 |
| Merge de cenas | `MergeScene_LogicBrick` 3376, `MergeScene_GameObject` 3399, `MergeScene` 3474 |
| Iluminação (flag) | `Get/SetUseLightScatter` 2582–2587 |
| Cutscene e Trace Rail (em `Ketsji/KX_SceneCutscene.cpp`, 901 linhas) | `SetCutsceneManager` 153, `StopCutscene` 164, `RestartCutscene` 174, `UpdateCutscene` 185, `StartTraceRail` 241, `StartTraceRailOrigin` 295, `UpdateTraceRail` 361, `UpdateCutscenePaths` 467, `TakePendingCutsceneEvents` 518, `DispatchCutsceneEvents` 574 (~300 linhas), `ClearCutsceneSpawnedObjects` 877, `GetCutsceneManager` 893 |
| Busca e texto (`static`, em `KX_SceneCutscene.cpp`) | `FindObjectWithComponent` 526, `FindGameObject` 548, `GetLocalizedText` 566 |
| Callbacks de Python | `RunDrawingCallbacks` 3688, `RunOnRemoveCallbacks` 3704 |
| Bindings Python (3014–fim) | `Type` 3043, `Methods[]` 3068, `Attributes[]` 3441, `Map_*`/`Seq_Contains` (`static`) 3085–3186, `pyattr_*` 3225–3428, métodos (`addObject` 3466, `end`, `restart`, `replace`, `suspend`, `resume`, `play_cutscene`, `get`…) 3466–3692, `ConvertPythonToScene` 4641 |

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

## `Physics/Bullet/CcdPhysicsEnvironment.cpp` (4.068 linhas)

Ambiente físico Bullet. O header é `CcdPhysicsEnvironment.h` (368 linhas). `m_dynamicsWorld` é membro do
ambiente; o callback de subtick é registrado no construtor com `this`.

| Domínio | Conteúdo (linha inicial) |
|---|---|
| Classes auxiliares de veículo | `VehicleClosestRayResultCallback` 100, `BlenderVehicleRaycaster` 146, `WrapperVehicle` 198 |
| Filtro de broadphase | `CcdOverlapFilterCallBack` 621 |
| Ciclo de vida do ambiente | `SetDebugDrawer` 695, construtor 646, `MergeEnvironment` 2520 |
| Controllers e constraints (add/remove) | `AddCcdPhysicsController` 752, `RemoveConstraint` 809, `RemoveVehicle` 840–849, `RestoreConstraint` 882, `RemoveCcdPhysicsController` 909, `Update/RefreshCcdPhysicsController` 882–915, graphic controllers 931–952, `UpdateCcdPhysicsControllerShape` 1040 |
| Simulação (passo) | `DebugDrawWorld` 1052, subticks 980–987, `ProceedDeltaTime` 1075, `ProceedDeltaTimeCar` 1152, `ProcessFhSprings` 1236 |
| Parâmetros do mundo | `SetDebugMode`… `SetSolverType` 1518–1668 (iterações, erp/cfm, sleeping, slop, ccd), `Get/SetGravity` 1447–1452, `WakeAllBodies` 1566 |
| Constraints (consulta) | `RemoveConstraintById` 1579, `GetConstraintById` 2587 |
| Raycast e consulta de esfera | `GetHitTriangle` 1651, `RayTest` 1692, `SphereQuery` 2404 (broadphase `aabbTest`, usado pelo `scene.explode()`) |
| **Oclusão em software (não é física)** | `struct OcclusionBuffer` 1740 (~520 linhas, rasterizador de oclusão), `DbvtCullingCallback` 2262, `CullingTest` 2473 |
| Contatos e broadphase | `GetNumContactPoints` 2501, `GetBroadphase`/`GetDispatcher` 2515–2520 |
| Sensores e callbacks de colisão | `AddSensor` 2605, `Add/RemoveCollisionCallback` 2460–2471, `CallbackTriggers` 2634, `CheckCollision` 2684, `needBroadphaseCollision` 2724 |
| Veículos e personagem | `GetVehicleConstraint`/`GetNumVehicles`/`GetVehicleFromIndex` 2787–2807, `GetCharacterController` 2795, `CreateVehicle` 3139, `DestroyVehicle` 3164 |
| Criação de shapes | `CreateSphereController` 2802, `CreateConeController` 3173, `Ccd_FindClosestNode` 2829 |
| Constraints (criação) | `CreateConstraint` 2846 (~290 linhas) |
| Exportação e fábrica | `getAppliedImpulse` 3106, `ExportFile` 3220, `Create` 3284 |
| Conversão de objeto | `ConvertObject` 3309 (~530 linhas), `SetupObjectConstraints` 3921 |
| Dados de colisão | `CcdCollData` 4008–4064 (contatos, atrito, restituição) |

Observação: ~520 linhas de `OcclusionBuffer` estão neste arquivo sem relação com o mundo Bullet; é o candidato
mais óbvio a viver em outro arquivo se um dia dividirem esse `.cpp`.

---

## `Physics/Bullet/CcdPhysicsController.cpp` (3.274 linhas)

Um corpo físico (rigid/soft/personagem) e seus motion states. O header é `CcdPhysicsController.h` (1.016 linhas).

| Domínio | Conteúdo (linha inicial) |
|---|---|
| Personagem | `CcdCharacter` 362–489 (pulo, caminhada, velocidade de queda, inclinação máxima) |
| Ciclo de vida | construtor 199, `PostProcessReplica` 1285, `SetPhysicsEnvironment` 1350, `GetReplica` 2629, `GetReplicaForSensors` 2636 |
| Constraints (referências) | `add/remove/getCcdConstraintRef` 236–254 |
| Motion state e transformação | `GetTransformFromMotionState` 614, `SetCenterOfMassOffset` 676, `SimulationTick` 1171, `SynchronizeMotionStates` 1208, `Write*ToDynamics/MotionState` 849–855, `SetTransform`, posição/orientação/escala 936–1185, `DefaultMotionState` 2739–2785 |
| Criação de corpos | `CreateSoftbody` 719 (~200 linhas), `CreateCharacterController` 956, `CreateRigidbody` 983 |
| Shapes | `DeleteBulletShape` 1055, `DeleteControllerShape` 1071, `ReplaceControllerShape` 1092, `ReinstancePhysicsShape` 2687, `ReplacePhysicsShape` 2712, `CreateBulletShape` 3015 (~160 linhas), `AddShape` 3243, `UpdateMesh` 2821 (~170 linhas), `FindMesh` 2785 |
| Compound | `AddCompoundChild` 2498, `RemoveCompoundChild` 2575 |
| Suspensão | `SuspendPhysics`/`RestorePhysics` 1554–1559, `SuspendDynamics`/`RestoreDynamics` 1645–1668, `IsPhysicsSuspended` 2672 |
| Massa, atrito, forças, velocidades | 1185–1421 e 1791–1840 |
| Colisão | group/mask 1425–1440, `SetActive` 2012, `RefreshCollisions` 1529 |
| Damping e CCD | 1445–1495 |
| **Soft body (parâmetros)** | `SetSoft*` e coeficientes 1506–1776 (~270 linhas de setters quase idênticos) |
| Sleeping | `UpdateDeactivation` 2477, `WantsSleeping` 2485 |

---

## `Converter/BL_BlenderDataConversion.cpp` (3.938 linhas)

Conversão do `.blend` para objetos do runtime. O header é `BL_BlenderDataConversion.h` (100 linhas).

| Domínio | Funções (linha inicial) |
|---|---|
| Utilitários | `BL_ConvertKeyCode` 451, `BL_GetUvRgba` 456 |
| Materiais e malhas | `BL_ConvertMaterial` 496, `BL_ConvertMesh` 631, `BL_ComputeVertexBoneData` 793, `BL_ConvertDerivedMeshToArray` 1154 |
| Deformers e ações | `BL_ConvertDeformer` 1710, `BL_ConvertAction(s)` 834–843 |
| Física e gráfico | `BL_CreateGraphicObjectNew` 1835, `BL_CreatePhysicsObjectNew` 1863 |
| LOD, animação, culling | `BL_LodManagerFromBlenderObject` 1912, `BL_AnimationEventManagerFromBlenderObject` 1928, `activityCullingInfoFromBlenderObject` 1942 |
| Luz, câmera, speaker | `BL_GameLightFromBlenderLamp` 1975, `BL_GameCameraFromBlenderCamera` 2045, `BL_SpeakerFromBlenderSpeaker` 2126 |
| Objeto de jogo | `BL_GameObjectFromBlenderObject` 2223 (~180 linhas) |
| Pose, constraints, fundo | `BL_GetActivePoseChannel` 2421, `BL_GetActiveConstraint` 2436, `BL_SetBlenderSceneBackground` 2459 |
| Componentes e cutscene | `BL_ConvertComponentsObject` 2470, `BL_ConvertCutscene` 2693 |
| Conversão de objeto único | `bl_ConvertBlenderObject_Single` 2555 |
| **Passagem principal** | `BL_ConvertBlenderObjects` 2762–3461 (**uma função de ~700 linhas** que converte os objetos da cena) |
| Pós-conversão e cursor | `BL_PostConvertBlenderObjects` 3722, `BL_ConvertCustomMouseCursor` 3917 |

Observação: `BL_ConvertBlenderObjects` concentra a conversão numa só função; mudanças aqui exigem ler o
trecho inteiro, não só um método.

---

## `Ketsji/KX_KetsjiEngine.cpp` (1.623 linhas)

Laço do jogo: tempo, frames lógicos/físicos, cenas. O desenho em si fica em `KX_RenderPipeline.cpp` (abaixo).

| Domínio | Métodos (linha inicial) |
|---|---|
| Construção e serviços | `KX_KetsjiEngine` 189, `SetCanvas` 327, `SetRasterizer` 333, `SetConverter` 421, `StartEngine` 453, `StopEngine` 1119 |
| Frame | `BeginFrame` 494, `EndFrame` 518, `UpdateDynamicResolution` 599, **`NextFrame`** 689 (lógica, física, animação), `Render` 1047 |
| Tempo e espera | `ServerSleep` 899, `SleepUnderRate` 912, `UpdateSleepTime` 925, `ClockTiming` 1165, `FrameTiming` 1201, `AdvanceStepTime` 1214 |
| Animação e sombra | `UpdateAnimations` 1105, `IsStaticShadowSettled` 1114 |
| Cenas | `AddScene` 1159, `ConvertAndAddScene` 1258, `PreloadScene` 1263, `RemoveScene` 1268, `ReplaceScene` 1283, `SuspendScene` 1288, `ResumeScene` 1293 |
| Taxas e flags | `SetTicRate` 1319, `SetUseFixedTimestep` 1391, `SetShadowCulling` 1418, `SetDynamicResolution` 1423 |

## `Ketsji/KX_RenderPipeline.cpp` (1.224 linhas)

| Domínio | Funções (linha inicial) |
|---|---|
| Névoa volumétrica | `KX_FillVolumetricFog` 125 |
| Frame | **`Render`** 375 (sombras, câmeras, filtros), `RenderCollisionDepthBuffer` 555 |
| Câmeras e visibilidade | `GetCameraRenderData` 598, `GetRenderData` 644, `GetVisibleMeshes` 738, `RenderCamera` 783 |
| Pós-render | `PostRenderScene` 929 (2D filters, offscreen final) |

## `Converter/BL_Converter.cpp` (1.924 linhas)

Conversão de cenas e LibLoad (síncrono e assíncrono). A conversão objeto a objeto fica em
`BL_BlenderDataConversion.cpp` (acima).

| Domínio | Métodos (linha inicial) |
|---|---|
| Cena | `ConvertScene` 682, `CompileSceneShaders` 721, `ConvertScene` 911, `PostConvertScene` 1018, `RemoveScene` 1023 |
| Objetos sob demanda | `FindOrConvertMainObject` 253, `FindSceneObject` 298, `ConvertSceneObject` 310, `FreeUnconvertedData` 470 |
| LibLoad | `LinkBlendFileMemory` 1375, `LinkBlendFilePath` 1383, **`LinkBlendFile`** 1412, `FreeBlendFileData` 1579, `FreeBlendFile` 1703 |
| Merge e assíncrono | `StepMerge` 1138, `StepReloads` 1227, `ProcessScheduledLibraries` 1268, `FinalizeAsyncLoads` 1304, `AsyncConvertTask` 1335, `MergeSceneData` 1730, `MergeScene` 1744 |
| Shaders e malhas | `ReloadShaders` 1778, `ConvertMeshSpecial` 1816 |
