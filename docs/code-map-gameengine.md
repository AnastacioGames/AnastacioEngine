# Mapa de código — arquivos grandes do gameengine

Guia de navegação para achar rápido onde fica cada responsabilidade nos maiores arquivos do gameengine,
sem lê-los inteiros. Não descreve arquitetura nem decisões; é só um índice. Para `KX_GameObject.cpp`, veja
[code-map-kx-gameobject.md](code-map-kx-gameobject.md).

**Linhas conferidas em 2026-11-12 (`HEAD` `f830ce8e`).** As linhas são aproximadas e envelhecem a cada edição: use-as
como ponto de partida e confirme com `grep -n "Classe::Metodo"`. O agrupamento por domínio foi feito pelo nome
dos métodos e por fronteiras confirmadas no código (marcadas onde houve conferência); leia o trecho antes de
mudar algo com base neste mapa.

Caminhos abaixo relativos a `source/source/gameengine/`.

---

## `Ketsji/KX_Scene.cpp` (5.052 linhas)

Cena em execução: dona dos objetos, listas de render, câmera ativa e bindings Python. Cutscene e Trace Rail ficam em
`Ketsji/KX_SceneCutscene.cpp` (mesma classe `KX_Scene`). O header é
`Ketsji/KX_Scene.h` (947 linhas).

| Domínio | Métodos (linha inicial) |
|---|---|
| Ciclo de vida da cena | funções `static` de réplica/destruição/atualização do SceneGraph 127–150, construtor 162, destrutor 334 |
| Acessores e listas | `GetName`/`SetName` 823–828, managers e listas (`GetObjectList`, `GetLightList`, `GetCameraList`, `GetRenderList`, `GetLogicManager`…) 883–948, framing 515–520 |
| Mundo, sol e terremoto | `Set/GetWorldInfo` 525–530, `SetWorldSun`/`GetWorldSun`/`SetAutoWorldSun`/`UpdateAutoWorldSun` 944–965, `UpdateEarthquake` 1014 |
| Suspensão e culling (config) | `Suspend`/`Resume`/`IsSuspended` 1123–1138, `SetActivityCulling` 1118, `Set/GetDbvtCulling` e oclusão 719–734 |
| Objetos: criação/réplica/grupos | `AddNodeReplicaObject` 1191, `ReplicateLogic` 1393, `DupliGroupRecurse` 1479, `IsObjectInGroup` 1621, `FindInactiveObjectAcrossScenes` 1626, `AddReplicaObject` 1673 |
| Objetos: remoção | `RemoveNodeDestructObject` 1181, `RemoveObject` 1771, `RemoveDupliGroup` 1784, `DelayedRemoveObject` 1793, `RemoveEuthanasyObjects` 1800, `NewRemoveObject` 1820 |
| Câmera e estatísticas de culling | `Get/SetActiveCamera` 1450–1468, contadores `GetLast*` 1474–1504, `Get/SetOverrideCullingCamera` 1511–1516, `SetCameraOnTop` 2217 |
| Culling e listas visíveis | `PhysicsCullingCallback` 2254, `CalculateVisibleMeshes` 2273–2296, `UpdateObjectActivity` 3613; Automatic Occluders: `CountCullingCallback` 2245 e liga/desliga dentro de `CalculateVisibleMeshes` 2380 |
| Debug (desenho e ImGui) | `GetDebugDraw` 2516, `DrawDebug` 2521, `RenderDebugProperties` 2558, `RenderDebugPropertiesImGui` 2611, `FlushDebugDraw` 2757, `AddObjectDebugProperties` 1163 |
| Frame lógico | `LogicBeginFrame` 2762, `LogicUpdateFrame` 3087, `LogicEndFrame` 3113, `UpdateParents` 3136 |
| Animação | `AddAnimatedObject` 2779, `UpdateAnimPoseTask` 2867, `UpdateAnimDeformTask` 2897, `UpdateAnimations` 2865, `UpdateAnimationDeformers` 3078 |
| Render | `RenderBuckets` 3159, `RenderTextureRenderers` 3174, `Get2DFilterManager` 3924, `Render2DFilters` 3929 |
| LOD | `UpdateObjectLods` 3180, hysteresis 2185–2200 |
| Partículas GPU | `UpdateGpuParticleEmitters` 3301, listas de emissores/colisores 2219–2250 |
| Sombras (listas) | casters estáticos/dinâmicos e flag "dirty" 2255–2298 |
| Física e rede | `Get/SetPhysicsEnvironment` 2339–2344, gravidade 2353–2358, `Get/SetNetworkMessageScene` 2329–2334, `Get/SetSuspendedDelta` 2363–2368 |
| Merge de cenas | `MergeScene_LogicBrick` 3688, `MergeScene_GameObject` 3711, `MergeScene` 3786 |
| Iluminação (flag) | `Get/SetUseLightScatter` 2582–2587 |
| Cutscene e Trace Rail (em `Ketsji/KX_SceneCutscene.cpp`, 901 linhas) | `SetCutsceneManager` 153, `StopCutscene` 164, `RestartCutscene` 174, `UpdateCutscene` 185, `StartTraceRail` 241, `StartTraceRailOrigin` 295, `UpdateTraceRail` 361, `UpdateCutscenePaths` 467, `TakePendingCutsceneEvents` 518, `DispatchCutsceneEvents` 574 (~300 linhas), `ClearCutsceneSpawnedObjects` 877, `GetCutsceneManager` 893 |
| Busca e texto (`static`, em `KX_SceneCutscene.cpp`) | `FindObjectWithComponent` 526, `FindGameObject` 548, `GetLocalizedText` 566 |
| Callbacks de Python | `RunDrawingCallbacks` 4002, `RunOnRemoveCallbacks` 4018 |
| Bindings Python (3014–fim) | `Type` 3043, `Methods[]` 3068, `Attributes[]` 3441, `Map_*`/`Seq_Contains` (`static`) 3085–3186, `pyattr_*` 3225–3428, métodos (`addObject` 3466, `end`, `restart`, `replace`, `suspend`, `resume`, `play_cutscene`, `get`…) 3466–3692, `ConvertPythonToScene` 4996 |

Observações: `DispatchCutsceneEvents` e `AddReplicaObject` são as funções mais longas; a remoção de objetos tem
cinco caminhos (`RemoveObject`, `DelayedRemoveObject`, `RemoveEuthanasyObjects`, `NewRemoveObject`,
`RemoveDupliGroup`) e convém ler todos antes de mexer em um deles.

---

## `Ketsji/KX_PythonInit.cpp` (3.944 linhas)

Bootstrap do Python embutido e módulos `Range`/`bge`. O registro dos **tipos** (`KX_GameObject`, `KX_Scene`…)
não está aqui: fica em `Ketsji/KX_PythonInitTypes.cpp`. Há código específico de Web (`__EMSCRIPTEN__`) em 69,
3151 e 3243–3281.

| Domínio | Funções (linha inicial) |
|---|---|
| Utilitários do módulo `Range` (funções globais `gPy*`) | aleatório/gravidade/caminho 214–243, `gPyStartGame`/`EndGame`/`RestartGame` 261–289, `SaveGlobalDict`/`LoadGlobalDict` 300–318, `GetProfileInfo` 336, `SendMessage` 349, `GetSpectrum` 372 |
| Taxas e relógio | tic rate, render rate, animation rate, exit key, max frames, clock/time scale 384–602 |
| Lista de arquivos e cenas | `.blend`/`.range`/`.rasec` 607–660, `AddScene`/`GetCurrentScene`/`GetSceneList` 671–707 |
| Informação de sistema | `pyPrintStats` 892, GPU vendor/renderer 722–735, CPU 749–759, `pyPrintExt` 974 |
| Bibliotecas externas | `gLibLoad` 993, `gLibNew` 1218, `gLibFree` 1272, `gLibList` 1288, `gPyNextFrame` 1314 |
| Tabela `game_methods[]` | 997 |
| Janela, mouse, estéreo, screenshot | `gPyGetWindowHeight`… 1452–1646 |
| Render (GLSL, AA, filtro, vsync, `drawLine`) | motion blur 1273–1290, GLSL 1302–1398, anisotropia/AA/mipmap/vsync 1413–1577, `gPyDrawLine` 1957, janela/fullscreen 1507–1524 |
| Áudio e debug na tela | `MasterVolume` 1585–1597, `ShowFramerate`/`ShowProfile`/`ShowProperties`/`AutoDebugList` 1606–1650, `GetDisplayDimensions` 1660 |
| Tabela `rasterizer_methods[]` | 1679 |
| Módulo lógica (`GameLogic`) | `GameLogic_module_def` 1748, `initGameLogicPythonBinding` 2326 (~430 linhas, constantes de tipos/estados) |
| Ambiente `sys` e caminhos | `backupPySysObjects` 2769 … `restorePySysObjects` 2844, `appendPythonPath` 2872, `addImportMain`/`removeImportMain` 2883–2888 |
| Módulo `Range` e compatibilidade | `addSubModule` 2905, `initRANGE` 2913, `RANGE_module_def` 2310, `installLegacyCollectionsAliases` 2952, `installLegacyAudFactoryAlias` 3006 (alias `bge`/`aud`) |
| Init/saída do Python | `initPlayerPython` 3054, `exitPlayerPython` 3094, console 2528–2595, `initGamePython` 3185, `exitGamePython` 3282 |
| Console e joystick | `createPythonConsole` 3305, `getPythonJoystick` 3317, `updatePythonJoysticks` 3322 |
| Módulo `Rasterizer` | `initRasterizerPythonBinding` 3363 |
| Teclas | `gPyEventToString`/`ToCharacter` 2775–2812, `initGameKeysPythonBinding` 3497 (~190 linhas de constantes) |
| Módulo `Application` | `initApplicationPythonBinding` 3692 |
| Config persistente do jogo | `saveGamePythonConfig` 3754, `loadGamePythonConfig` 3833, `pathGamePythonConfig` 3910 (contém código Web/IDBFS) |

Observação: `initPlayerPython` (editor não usa) é o caminho do standalone; o editor entra por `BPY_python_start`.

---

## `Physics/Bullet/CcdPhysicsEnvironment.cpp` (4.137 linhas)

Ambiente físico Bullet. O header é `CcdPhysicsEnvironment.h` (391 linhas). `m_dynamicsWorld` é membro do
ambiente; o callback de subtick é registrado no construtor com `this`.

| Domínio | Conteúdo (linha inicial) |
|---|---|
| Classes auxiliares de veículo | `VehicleClosestRayResultCallback` 100, `BlenderVehicleRaycaster` 146, `WrapperVehicle` 198 |
| Filtro de broadphase | `CcdOverlapFilterCallBack` 621 |
| Ciclo de vida do ambiente | `SetDebugDrawer` 698, construtor 646, `MergeEnvironment` 2534 |
| Controllers e constraints (add/remove) | `AddCcdPhysicsController` 755, `RemoveConstraint` 812, `RemoveVehicle` 845–854, `RestoreConstraint` 887, `RemoveCcdPhysicsController` 921, `Update/RefreshCcdPhysicsController` 882–915, graphic controllers 931–952, `UpdateCcdPhysicsControllerShape` 1052 |
| Simulação (passo) | `DebugDrawWorld` 1064, subticks 980–987, `ProceedDeltaTime` 1087, `ProceedDeltaTimeCar` 1165, `ProcessFhSprings` 1250 |
| Parâmetros do mundo | `SetDebugMode`… `SetSolverType` 1532–1682 (iterações, erp/cfm, sleeping, slop, ccd), `Get/SetGravity` 1447–1452, `WakeAllBodies` 1580 |
| Constraints (consulta) | `RemoveConstraintById` 1593, `GetConstraintById` 2601 |
| Raycast e consulta de esfera | `GetHitTriangle` 1665, `RayTest` 1706, `SphereQuery` 2418 (broadphase `aabbTest`, usado pelo `scene.explode()`) |
| **Oclusão em software (não é física)** | `struct OcclusionBuffer` 1740 (~520 linhas, rasterizador de oclusão), `DbvtCullingCallback` 2262, `CullingTest` 2487 |
| Contatos e broadphase | `GetNumContactPoints` 2515, `GetBroadphase`/`GetDispatcher` 2529–2534 |
| Sensores e callbacks de colisão | `AddSensor` 2619, `Add/RemoveCollisionCallback` 2460–2471, `CallbackTriggers` 2648, `CheckCollision` 2704, `needBroadphaseCollision` 2744 |
| Veículos e personagem | `GetVehicleConstraint`/`GetNumVehicles`/`GetVehicleFromIndex` 2807–2827, `GetCharacterController` 2815, `CreateVehicle` 3158, `DestroyVehicle` 3183 |
| Criação de shapes | `CreateSphereController` 2822, `CreateConeController` 3192, `Ccd_FindClosestNode` 2849 |
| Constraints (criação) | `CreateConstraint` 2866 (~290 linhas) |
| Exportação e fábrica | `getAppliedImpulse` 3106, `ExportFile` 3239, `Create` 3303 |
| Conversão de objeto | `ConvertObject` 3328 (~530 linhas), `SetupObjectConstraints` 3967 |
| Dados de colisão | `CcdCollData` 4054–4110 (contatos, atrito, restituição) |

Observação: ~520 linhas de `OcclusionBuffer` estão neste arquivo sem relação com o mundo Bullet; é o candidato
mais óbvio a viver em outro arquivo se um dia dividirem esse `.cpp`.

---

## `Physics/Bullet/CcdPhysicsController.cpp` (3.679 linhas)

Um corpo físico (rigid/soft/personagem) e seus motion states. O header é `CcdPhysicsController.h` (1.100 linhas).

| Domínio | Conteúdo (linha inicial) |
|---|---|
| Personagem | `CcdCharacter` 362–489 (pulo, caminhada, velocidade de queda, inclinação máxima) |
| Ciclo de vida | construtor 199, `PostProcessReplica` 1678, `SetPhysicsEnvironment` 1743, `GetReplica` 3026, `GetReplicaForSensors` 3033 |
| Constraints (referências) | `add/remove/getCcdConstraintRef` 236–254 |
| Motion state e transformação | `GetTransformFromMotionState` 1001, `SetCenterOfMassOffset` 1063, `SimulationTick` 1564, `SynchronizeMotionStates` 1601, `Write*ToDynamics/MotionState` 849–855, `SetTransform`, posição/orientação/escala 936–1185, `DefaultMotionState` 3136–3182 |
| Criação de corpos | `CreateSoftbody` 1106 (~200 linhas), `CreateCharacterController` 1343, `CreateRigidbody` 1374 |
| Shapes | `DeleteBulletShape` 1446, `DeleteControllerShape` 1462, `ReplaceControllerShape` 1483, `ReinstancePhysicsShape` 3084, `ReplacePhysicsShape` 3109, `CreateBulletShape` 3215 (~160 linhas), `AddShape` 3648, `UpdateMesh` 3218 (~170 linhas), `FindMesh` 3182 |
| Compound | `AddCompoundChild` 2895, `RemoveCompoundChild` 2972 |
| Suspensão | `SuspendPhysics`/`RestorePhysics` 1947–1952, `SuspendDynamics`/`RestoreDynamics` 2038–2061, `IsPhysicsSuspended` 3069 |
| Massa, atrito, forças, velocidades | 1185–1421 e 1791–1840 |
| Colisão | group/mask 1425–1440, `SetActive` 2409, `RefreshCollisions` 1922 |
| Damping e CCD | 1445–1495 |
| **Soft body (parâmetros)** | `SetSoft*` e coeficientes 1506–1776 (~270 linhas de setters quase idênticos) |
| Sleeping | `UpdateDeactivation` 2874, `WantsSleeping` 2882 |

---

## `Converter/BL_BlenderDataConversion.cpp` (4.284 linhas)

Conversão do `.blend` para objetos do runtime. O header é `BL_BlenderDataConversion.h` (101 linhas).

| Domínio | Funções (linha inicial) |
|---|---|
| Utilitários | `BL_ConvertKeyCode` 460, `BL_GetUvRgba` 465 |
| Materiais e malhas | `BL_ConvertMaterial` 505, `BL_ConvertMesh` 703, `BL_ComputeVertexBoneData` 865, `BL_ConvertDerivedMeshToArray` 1228 |
| Deformers e ações | `BL_ConvertDeformer` 1789, `BL_ConvertAction(s)` 834–843 |
| Física e gráfico | `BL_IsAutoOccluder` 1921 (Automatic Occluders), `BL_CreateGraphicObjectNew` 1967, `BL_CreatePhysicsObjectNew` 1995 |
| LOD, animação, culling | `BL_LodManagerFromBlenderObject` 2044, `BL_AnimationEventManagerFromBlenderObject` 2060, `activityCullingInfoFromBlenderObject` 2074 |
| Luz, câmera, speaker | `BL_GameLightFromBlenderLamp` 2107, `BL_GameCameraFromBlenderCamera` 2177, `BL_SpeakerFromBlenderSpeaker` 2258 |
| Objeto de jogo | `BL_GameObjectFromBlenderObject` 2355 (~180 linhas) |
| Pose, constraints, fundo | `BL_GetActivePoseChannel` 2586, `BL_GetActiveConstraint` 2601, `BL_SetBlenderSceneBackground` 2624 |
| Componentes e cutscene | `BL_ConvertComponentsObject` 2635, `BL_ConvertCutscene` 2858 |
| Conversão de objeto único | `bl_ConvertBlenderObject_Single` 2720 |
| **Passagem principal** | `BL_ConvertBlenderObjects` 2935–3634 (**uma função de ~700 linhas** que converte os objetos da cena) |
| Pós-conversão e cursor | `BL_PostConvertBlenderObjects` 4002, `BL_ConvertCustomMouseCursor` 4263 |

Observação: `BL_ConvertBlenderObjects` concentra a conversão numa só função; mudanças aqui exigem ler o
trecho inteiro, não só um método.

---

## `Ketsji/KX_KetsjiEngine.cpp` (1.841 linhas)

Laço do jogo: tempo, frames lógicos/físicos, cenas. O desenho em si fica em `KX_RenderPipeline.cpp` (abaixo).

| Domínio | Métodos (linha inicial) |
|---|---|
| Construção e serviços | `KX_KetsjiEngine` 194, `SetCanvas` 334, `SetRasterizer` 340, `SetConverter` 428, `StartEngine` 460, `StopEngine` 1313 |
| Frame | `BeginFrame` 501, `EndFrame` 528, `UpdateDynamicResolution` 617, **`NextFrame`** 750 (lógica, física, animação), `Render` 1146 |
| Tempo e espera | `ServerSleep` 980, `SleepUnderRate` 921, `UpdateSleepTime` 1051, `ClockTiming` 1359, `FrameTiming` 1395, `AdvanceStepTime` 1408 |
| Animação e sombra | `UpdateAnimations` 1299, `IsStaticShadowSettled` 1308 |
| Cenas | `AddScene` 1353, `ConvertAndAddScene` 1455, `PreloadScene` 1460, `RemoveScene` 1465, `ReplaceScene` 1480, `SuspendScene` 1485, `ResumeScene` 1490 |
| Taxas e flags | `SetTicRate` 1516, `SetUseFixedTimestep` 1609, `SetShadowCulling` 1636, `SetDynamicResolution` 1641 |

## `Ketsji/KX_RenderPipeline.cpp` (1.403 linhas)

| Domínio | Funções (linha inicial) |
|---|---|
| Névoa volumétrica | `KX_FillVolumetricFog` 137 |
| Frame | **`Render`** 387 (sombras, câmeras, filtros), `RenderCollisionDepthBuffer` 660 |
| Câmeras e visibilidade | `GetCameraRenderData` 703, `GetRenderData` 749, `GetVisibleMeshes` 847, `RenderCamera` 892 |
| Pós-render | `PostRenderScene` 1083 (2D filters, offscreen final) |

## `Converter/BL_Converter.cpp` (2.000 linhas)

Conversão de cenas e LibLoad (síncrono e assíncrono). A conversão objeto a objeto fica em
`BL_BlenderDataConversion.cpp` (acima).

| Domínio | Métodos (linha inicial) |
|---|---|
| Cena | `ConvertScene` 688, `CompileSceneShaders` 727, `ConvertScene` 938, `PostConvertScene` 1045, `RemoveScene` 1050 |
| Objetos sob demanda | `FindOrConvertMainObject` 253, `FindSceneObject` 298, `ConvertSceneObject` 310, `FreeUnconvertedData` 470 |
| LibLoad | `LinkBlendFileMemory` 1448, `LinkBlendFilePath` 1456, **`LinkBlendFile`** 1485, `FreeBlendFileData` 1652, `FreeBlendFile` 1775 |
| Merge e assíncrono | `StepMerge` 1168, `StepReloads` 1295, `ProcessScheduledLibraries` 1336, `FinalizeAsyncLoads` 1377, `AsyncConvertTask` 1408, `MergeSceneData` 1806, `MergeScene` 1820 |
| Shaders e malhas | `ReloadShaders` 1854, `ConvertMeshSpecial` 1892 |
