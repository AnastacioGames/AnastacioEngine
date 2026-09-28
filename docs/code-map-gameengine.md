# Mapa de código — arquivos grandes do gameengine

Guia de navegação para achar rápido onde fica cada responsabilidade nos maiores arquivos do gameengine,
sem lê-los inteiros. Não descreve arquitetura nem decisões; é só um índice. Para `KX_GameObject.cpp`, veja
[code-map-kx-gameobject.md](code-map-kx-gameobject.md).

**Linhas conferidas em 2026-09-28 (`HEAD` `d70de38b`).** As linhas são aproximadas e envelhecem a cada edição: use-as
como ponto de partida e confirme com `grep -n "Classe::Metodo"`. O agrupamento por domínio foi feito pelo nome
dos métodos e por fronteiras confirmadas no código (marcadas onde houve conferência); leia o trecho antes de
mudar algo com base neste mapa.

Caminhos abaixo relativos a `source/source/gameengine/`.

---

## `Ketsji/KX_Scene.cpp` (3.843 linhas)

Cena em execução: dona dos objetos, listas de render, câmera ativa, cutscene e bindings Python. O header é
`Ketsji/KX_Scene.h` (693 linhas).

| Domínio | Métodos (linha inicial) |
|---|---|
| Ciclo de vida da cena | funções `static` de réplica/destruição/atualização do SceneGraph 127–150, construtor 162, destrutor 334 |
| Acessores e listas | `GetName`/`SetName` 444–449, managers e listas (`GetObjectList`, `GetLightList`, `GetCameraList`, `GetRenderList`, `GetLogicManager`…) 504–569, framing 515–520 |
| Mundo, sol e terremoto | `Set/GetWorldInfo` 525–530, `SetWorldSun`/`GetWorldSun`/`SetAutoWorldSun`/`UpdateAutoWorldSun` 560–581, `UpdateEarthquake` 620 |
| Suspensão e culling (config) | `Suspend`/`Resume`/`IsSuspended` 718–733, `SetActivityCulling` 713, `Set/GetDbvtCulling` e oclusão 719–734 |
| Objetos: criação/réplica/grupos | `AddNodeReplicaObject` 771, `ReplicateLogic` 936, `DupliGroupRecurse` 1022, `IsObjectInGroup` 1163, `FindInactiveObjectAcrossScenes` 1168, `AddReplicaObject` 1184 |
| Objetos: remoção | `RemoveNodeDestructObject` 761, `RemoveObject` 1285, `RemoveDupliGroup` 1298, `DelayedRemoveObject` 1307, `RemoveEuthanasyObjects` 1314, `NewRemoveObject` 1334 |
| Câmera e estatísticas de culling | `Get/SetActiveCamera` 1450–1468, contadores `GetLast*` 1474–1504, `Get/SetOverrideCullingCamera` 1511–1516, `SetCameraOnTop` 1531 |
| Culling e listas visíveis | `PhysicsCullingCallback` 1552, `CalculateVisibleMeshes` 1571–1594, `UpdateObjectActivity` 2354 |
| Debug (desenho e ImGui) | `GetDebugDraw` 1651, `DrawDebug` 1656, `RenderDebugProperties` 1693, `RenderDebugPropertiesImGui` 1746, `FlushDebugDraw` 1892, `AddObjectDebugProperties` 743 |
| Frame lógico | `LogicBeginFrame` 1897, `LogicUpdateFrame` 2149, `LogicEndFrame` 2170, `UpdateParents` 2190 |
| Animação | `AddAnimatedObject` 1922, `UpdateAnimPoseTask` 1991, `UpdateAnimDeformTask` 2013, `UpdateAnimations` 2042, `UpdateAnimationDeformers` 2138 |
| Render | `RenderBuckets` 2207, `RenderTextureRenderers` 2220, `Get2DFilterManager` 2643, `Render2DFilters` 2648 |
| LOD | `UpdateObjectLods` 2226, hysteresis 2185–2200 |
| Partículas GPU | `UpdateGpuParticleEmitters` 2256, listas de emissores/colisores 2219–2250 |
| Sombras (listas) | casters estáticos/dinâmicos e flag "dirty" 2255–2298 |
| Física e rede | `Get/SetPhysicsEnvironment` 2339–2344, gravidade 2353–2358, `Get/SetNetworkMessageScene` 2329–2334, `Get/SetSuspendedDelta` 2363–2368 |
| Merge de cenas | `MergeScene_LogicBrick` 2378, `MergeScene_GameObject` 2401, `MergeScene` 2527 |
| Iluminação (flag) | `Get/SetUseLightScatter` 2582–2587 |
| Cutscene | `SetCutsceneManager` 2658, `StopCutscene` 2668, `RestartCutscene` 2677, `UpdateCutscene` 2687, `TakePendingCutsceneEvents` 2698, `DispatchCutsceneEvents` 2754 (~280 linhas), `ClearCutsceneSpawnedObjects` 3034, `GetCutsceneManager` 3050 |
| Busca e texto | `FindObjectWithComponent` 2655, `FindGameObject` 2677, `GetLocalizedText` 2695 |
| Callbacks de Python | `RunDrawingCallbacks` 3092, `RunOnRemoveCallbacks` 3108 |
| Bindings Python (3014–fim) | `Type` 3043, `Methods[]` 3068, `Attributes[]` 3441, `Map_*`/`Seq_Contains` (`static`) 3085–3186, `pyattr_*` 3225–3428, métodos (`addObject` 3466, `end`, `restart`, `replace`, `suspend`, `resume`, `play_cutscene`, `get`…) 3466–3692, `ConvertPythonToScene` 3711 |

Observações: `DispatchCutsceneEvents` e `AddReplicaObject` são as funções mais longas; a remoção de objetos tem
cinco caminhos (`RemoveObject`, `DelayedRemoveObject`, `RemoveEuthanasyObjects`, `NewRemoveObject`,
`RemoveDupliGroup`) e convém ler todos antes de mexer em um deles.

---

## `Ketsji/KX_PythonInit.cpp` (3.310 linhas)

Bootstrap do Python embutido e módulos `Range`/`bge`. O registro dos **tipos** (`KX_GameObject`, `KX_Scene`…)
não está aqui: fica em `Ketsji/KX_PythonInitTypes.cpp`. Há código específico de Web (`__EMSCRIPTEN__`) em 69,
3151 e 3243–3281.

| Domínio | Funções (linha inicial) |
|---|---|
| Utilitários do módulo `Range` (funções globais `gPy*`) | aleatório/gravidade/caminho 214–243, `gPyStartGame`/`EndGame`/`RestartGame` 261–289, `SaveGlobalDict`/`LoadGlobalDict` 300–318, `GetProfileInfo` 336, `SendMessage` 349, `GetSpectrum` 372 |
| Taxas e relógio | tic rate, render rate, animation rate, exit key, max frames, clock/time scale 384–602 |
| Lista de arquivos e cenas | `.blend`/`.range`/`.rasec` 607–660, `AddScene`/`GetCurrentScene`/`GetSceneList` 671–707 |
| Informação de sistema | `pyPrintStats` 716, GPU vendor/renderer 722–735, CPU 749–759, `pyPrintExt` 798 |
| Bibliotecas externas | `gLibLoad` 817, `gLibNew` 896, `gLibFree` 950, `gLibList` 966, `gPyNextFrame` 979 |
| Tabela `game_methods[]` | 997 |
| Janela, mouse, estéreo, screenshot | `gPyGetWindowHeight`… 1063–1257 |
| Render (GLSL, AA, filtro, vsync, `drawLine`) | motion blur 1273–1290, GLSL 1302–1398, anisotropia/AA/mipmap/vsync 1413–1577, `gPyDrawLine` 1463, janela/fullscreen 1507–1524 |
| Áudio e debug na tela | `MasterVolume` 1585–1597, `ShowFramerate`/`ShowProfile`/`ShowProperties`/`AutoDebugList` 1606–1650, `GetDisplayDimensions` 1660 |
| Tabela `rasterizer_methods[]` | 1679 |
| Módulo lógica (`GameLogic`) | `GameLogic_module_def` 1748, `initGameLogicPythonBinding` 1760 (~430 linhas, constantes de tipos/estados) |
| Ambiente `sys` e caminhos | `backupPySysObjects` 2186 … `restorePySysObjects` 2261, `appendPythonPath` 2289, `addImportMain`/`removeImportMain` 2295–2300 |
| Módulo `Range` e compatibilidade | `addSubModule` 2322, `initRANGE` 2330, `RANGE_module_def` 2310, `installLegacyCollectionsAliases` 2365, `installLegacyAudFactoryAlias` 2419 (alias `bge`/`aud`) |
| Init/saída do Python | `initPlayerPython` 2467, `exitPlayerPython` 2504, console 2528–2595, `initGamePython` 2595, `exitGamePython` 2636 |
| Console e joystick | `createPythonConsole` 2655, `getPythonJoystick` 2667, `updatePythonJoysticks` 2672 |
| Módulo `Rasterizer` | `initRasterizerPythonBinding` 2713 |
| Teclas | `gPyEventToString`/`ToCharacter` 2775–2812, `initGameKeysPythonBinding` 2842 (~190 linhas de constantes) |
| Módulo `Application` | `initApplicationPythonBinding` 3037 |
| Config persistente do jogo | `saveGamePythonConfig` 3099, `loadGamePythonConfig` 3178, `pathGamePythonConfig` 3241 (contém código Web/IDBFS) |

Observação: `initPlayerPython` (editor não usa) é o caminho do standalone; o editor entra por `BPY_python_start`.

---

## `Physics/Bullet/CcdPhysicsEnvironment.cpp` (3.847 linhas)

Ambiente físico Bullet. O header é `CcdPhysicsEnvironment.h` (362 linhas). `m_dynamicsWorld` é membro do
ambiente; o callback de subtick é registrado no construtor com `this`.

| Domínio | Conteúdo (linha inicial) |
|---|---|
| Classes auxiliares de veículo | `VehicleClosestRayResultCallback` 100, `BlenderVehicleRaycaster` 146, `WrapperVehicle` 198 |
| Filtro de broadphase | `CcdOverlapFilterCallBack` 621 |
| Ciclo de vida do ambiente | `SetDebugDrawer` 638, construtor 646, `MergeEnvironment` 2386 |
| Controllers e constraints (add/remove) | `AddCcdPhysicsController` 695, `RemoveConstraint` 752, `RemoveVehicle` 783–792, `RestoreConstraint` 808, `RemoveCcdPhysicsController` 835, `Update/RefreshCcdPhysicsController` 882–915, graphic controllers 931–952, `UpdateCcdPhysicsControllerShape` 963 |
| Simulação (passo) | `DebugDrawWorld` 975, subticks 980–987, `ProceedDeltaTime` 998, `ProceedDeltaTimeCar` 1069, `ProcessFhSprings` 1147 |
| Parâmetros do mundo | `SetDebugMode`… `SetSolverType` 1428–1578 (iterações, erp/cfm, sleeping, slop, ccd), `Get/SetGravity` 1447–1452, `WakeAllBodies` 1476 |
| Constraints (consulta) | `RemoveConstraintById` 1489, `GetConstraintById` 2453 |
| Raycast | `GetHitTriangle` 1544, `RayTest` 1602 |
| **Oclusão em software (não é física)** | `struct OcclusionBuffer` 1740 (~520 linhas, rasterizador de oclusão), `DbvtCullingCallback` 2262, `CullingTest` 2339 |
| Contatos e broadphase | `GetNumContactPoints` 2367, `GetBroadphase`/`GetDispatcher` 2381–2386 |
| Sensores e callbacks de colisão | `AddSensor` 2471, `Add/RemoveCollisionCallback` 2460–2471, `CallbackTriggers` 2500, `CheckCollision` 2547, `needBroadphaseCollision` 2587 |
| Veículos e personagem | `GetVehicleConstraint`/`GetNumVehicles`/`GetVehicleFromIndex` 2650–2670, `GetCharacterController` 2658, `CreateVehicle` 3002, `DestroyVehicle` 3027 |
| Criação de shapes | `CreateSphereController` 2665, `CreateConeController` 3036, `Ccd_FindClosestNode` 2675 |
| Constraints (criação) | `CreateConstraint` 2709 (~290 linhas) |
| Exportação e fábrica | `getAppliedImpulse` 3062, `ExportFile` 3081, `Create` 3145 |
| Conversão de objeto | `ConvertObject` 3170 (~530 linhas), `SetupObjectConstraints` 3700 |
| Dados de colisão | `CcdCollData` 3787–3843 (contatos, atrito, restituição) |

Observação: ~520 linhas de `OcclusionBuffer` estão neste arquivo sem relação com o mundo Bullet; é o candidato
mais óbvio a viver em outro arquivo se um dia dividirem esse `.cpp`.

---

## `Physics/Bullet/CcdPhysicsController.cpp` (2.601 linhas)

Um corpo físico (rigid/soft/personagem) e seus motion states. O header é `CcdPhysicsController.h` (976 linhas).

| Domínio | Conteúdo (linha inicial) |
|---|---|
| Personagem | `CcdCharacter` 60–187 (pulo, caminhada, velocidade de queda, inclinação máxima) |
| Ciclo de vida | construtor 199, `PostProcessReplica` 867, `SetPhysicsEnvironment` 923, `GetReplica` 2033, `GetReplicaForSensors` 2040 |
| Constraints (referências) | `add/remove/getCcdConstraintRef` 236–254 |
| Motion state e transformação | `GetTransformFromMotionState` 259, `SetCenterOfMassOffset` 308, `SimulationTick` 767, `SynchronizeMotionStates` 804, `Write*ToDynamics/MotionState` 849–855, `SetTransform`, posição/orientação/escala 936–1185, `DefaultMotionState` 2143–2189 |
| Criação de corpos | `CreateSoftbody` 351 (~200 linhas), `CreateCharacterController` 555, `CreateRigidbody` 582 |
| Shapes | `DeleteBulletShape` 654, `DeleteControllerShape` 670, `ReplaceControllerShape` 691, `ReinstancePhysicsShape` 2091, `ReplacePhysicsShape` 2116, `CreateBulletShape` 2410 (~160 linhas), `AddShape` 2570, `UpdateMesh` 2222 (~170 linhas), `FindMesh` 2189 |
| Compound | `AddCompoundChild` 1902, `RemoveCompoundChild` 1979 |
| Suspensão | `SuspendPhysics`/`RestorePhysics` 1109–1114, `SuspendDynamics`/`RestoreDynamics` 1137–1160, `IsPhysicsSuspended` 2076 |
| Massa, atrito, forças, velocidades | 1185–1421 e 1791–1840 |
| Colisão | group/mask 1425–1440, `SetActive` 1429, `RefreshCollisions` 1084 |
| Damping e CCD | 1445–1495 |
| **Soft body (parâmetros)** | `SetSoft*` e coeficientes 1506–1776 (~270 linhas de setters quase idênticos) |
| Sleeping | `UpdateDeactivation` 1881, `WantsSleeping` 1889 |

---

## `Converter/BL_BlenderDataConversion.cpp` (2.451 linhas)

Conversão do `.blend` para objetos do runtime. O header é `BL_BlenderDataConversion.h` (81 linhas).

| Domínio | Funções (linha inicial) |
|---|---|
| Utilitários | `BL_ConvertKeyCode` 403, `BL_GetUvRgba` 408 |
| Materiais e malhas | `BL_ConvertMaterial` 448, `BL_ConvertMesh` 474, `BL_ComputeVertexBoneData` 577, `BL_ConvertDerivedMeshToArray` 625 |
| Deformers e ações | `BL_ConvertDeformer` 751, `BL_ConvertAction(s)` 834–843 |
| Física e gráfico | `BL_CreateGraphicObjectNew` 851, `BL_CreatePhysicsObjectNew` 879 |
| LOD, animação, culling | `BL_LodManagerFromBlenderObject` 928, `BL_AnimationEventManagerFromBlenderObject` 944, `activityCullingInfoFromBlenderObject` 958 |
| Luz, câmera, speaker | `BL_GameLightFromBlenderLamp` 991, `BL_GameCameraFromBlenderCamera` 1055, `BL_SpeakerFromBlenderSpeaker` 1097 |
| Objeto de jogo | `BL_GameObjectFromBlenderObject` 1194 (~180 linhas) |
| Pose, constraints, fundo | `BL_GetActivePoseChannel` 1378, `BL_GetActiveConstraint` 1393, `BL_SetBlenderSceneBackground` 1416 |
| Componentes e cutscene | `BL_ConvertComponentsObject` 1427, `BL_ConvertCutscene` 1594 |
| Conversão de objeto único | `bl_ConvertBlenderObject_Single` 1512 |
| **Passagem principal** | `BL_ConvertBlenderObjects` 1634–2333 (**uma função de ~700 linhas** que converte os objetos da cena) |
| Pós-conversão e cursor | `BL_PostConvertBlenderObjects` 2333, `BL_ConvertCustomMouseCursor` 2415 |

Observação: `BL_ConvertBlenderObjects` concentra a conversão numa só função; mudanças aqui exigem ler o
trecho inteiro, não só um método.
