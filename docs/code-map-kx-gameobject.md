# Mapa de código — `KX_GameObject`

Guia de navegação para achar rápido onde fica cada responsabilidade de `KX_GameObject` sem ler os arquivos
inteiros. Não descreve arquitetura nem decisões; é só um índice. A classe está dividida em três arquivos:
o núcleo C++ em [`KX_GameObject.cpp`](../source/source/gameengine/Ketsji/KX_GameObject.cpp) e os bindings
Python em [`KX_GameObject_Python.cpp`](../source/source/gameengine/Ketsji/KX_GameObject_Python.cpp)
(tabelas, tipo e atributos) e
[`KX_GameObject_PyMethods.cpp`](../source/source/gameengine/Ketsji/KX_GameObject_PyMethods.cpp) (métodos).

**Linhas conferidas em 2026-10-26 (`HEAD` `1a63417a`).** Números de linha são aproximados e envelhecem a cada
edição: use-os como ponto de partida e confirme com `grep -n "KX_GameObject::NomeDoMetodo"`.

Para a declaração das classes e membros, o header é
[`KX_GameObject.h`](../source/source/gameengine/Ketsji/KX_GameObject.h) (1.422 linhas).

## `Ketsji/KX_GameObject.cpp` (2.731 linhas)

Núcleo C++.

Os métodos de um mesmo domínio **não são contíguos**: por exemplo, animação aparece em 643–698 e de novo em
803–818, e partículas ficam no meio do bloco de animação. Procure pelo nome, não pela faixa.

| Domínio | Métodos (linha inicial) |
|---|---|
| Ciclo de vida | construtor 120, construtor de cópia 165, destrutor 233, `GetReplica` 1035, `RemoveRessources` 1045 |
| Identidade e propriedades | `GetName`/`SetName` 357–363, `GetClientObject` 343, `GetRuntimeProperty`/`SetRuntimeProperty` 452–472, `GetBlenderObject` 2305, `GetConvertObjectInfo`/`SetConvertObjectInfo` 2326–2331 |
| Veículo (parâmetros armazenados) | `Set/GetVehicle*` 303–358 (constraint id, roda de direção, torque, RPM, marchas, tipo de câmbio) |
| Controllers (física/gráfico) | `GetPhysicsController` 367, `SetPhysicsController` 495, `Get/SetGraphicController` 436–441, `ActivateGraphicController` 1001, `GetDeformer` 362 |
| Grupos/instâncias e constraints | `Get/SetDupliGroupObject` 446/481, `Get/Add/RemoveInstanceObject(s)` 451–473, `GetConstraints`/`ReplicateConstraints` 561–566 |
| Hierarquia | `GetParent` 579, `SetParent` 595, `RemoveParent` 666 |
| Animação | `GetActionManager` 712, `PlayAction` 721, `StopAction` 744, `IsActionDone` 749, `IsActionsSuspended` 759, `UpdateActionManager` 764, frames/nomes/camadas 688–698 e 803–818, `SetPlayMode` 979, `SuspendAnimations`/`ResumeAnimations` 2462–2472, `Get/SetAnimationEventManager` 1389–1402, `GetDoAnimations`/`SetHalfAnimations` 1800–1812 |
| Partículas GPU | `SetupGPUParticlesBuffer` 842, `SetupGPUParticles` 908, `SetupGPUParticlesMix` 913, `UpdateParticles` 918, `GetParticleBuffer(Mix)` 793–798 |
| Colisão | `Set/GetCollisionGroup` 850/865, `Set/GetCollisionMask` 857/869, `Register/UnregisterCollisionCallbacks` 2157–2178, `RunCollisionCallbacks` 2510 |
| Física: parâmetros | `IsDynamic` 1069, damping 925–956, CCD 964–970, **soft body** (`SetSoft*`, coeficientes, solver iterations) 981–1154 |
| Física: forças e velocidades | `ApplyForce/Torque/Movement/Rotation` 1166–1189, `Add/SetLinearVelocity`, `SetAngularVelocity` 1964–1979, `GetMass`…`GetVelocity` 2155–2222, `SuspendPhysics`/`RestorePhysics` 2445–2452 |
| Malhas e renderização | `UpdateBlenderObjectMatrix` 1361, `AddMeshUser` 1372, `UpdateBuckets` 1424, `ReplaceMesh` 1447, `RemoveMeshes` 1477, `GetMeshList` 1494, `Renderable` 1504, cor 1686–1691, `Get/SetPassIndex` 1654–1659, `Get/SetLayer` 1644–1649 |
| LOD | `Set/GetLodManager` 1291–1313, `UpdateLod` 1552, `GetVisibleLOD`/`UpdateVisibleLOD` 1811–1816 |
| Visibilidade e depuração | `GetVisible`/`SetVisible` 1848/1563, `SetOccluder` 1876, `SetUseDebugProperties` 1911, helpers `static` `setVisible_recursive` 1831, `setOccluder_recursive` 1860, `setDebug_recursive` 1888 |
| Atividade e culling | `UpdateActivity` 1688, `Get/SetActivityCullingInfo` 2092–2097, `SetActivityCulling` 2398, `UpdateBounds` 2336, `Get/SetBoundsAabb` 2070–2081, `GetCullingNode` 2383 |
| SceneGraph e transformação | `UpdateTransform`/`SynchronizeTransform` 1766–1795, `AlignAxisToVect` 1981, `NodeSet*`/`NodeGet*` 1878–2015, `SetNode` 2331 |
| Componentes Python | `SetComponents` 2652, `UpdateComponents` 2657 (runtime; ficam no núcleo apesar do `#ifdef WITH_PYTHON`) |
| Helpers `static` do núcleo | `setGraphicController_recursive` 984, `walk_children`/`walk_parent` 2611–2633 (servem a `GetChildren*`) |

## `Ketsji/KX_GameObject_Python.cpp` (2.871 linhas)

Bindings Python, parte 1. Tudo dentro de `#ifdef WITH_PYTHON`. Ordem do arquivo:

| Linhas | Conteúdo |
|---|---|
| 127–417 | macro `PYTHON_CHECK_PHYSICS_CONTROLLER`, callbacks mathutils (`static`), `KX_GameObject_Mathutils_Callback_Init` 413 (público, chamada por `KX_PythonInitTypes.cpp`) |
| 419–1386 | `Methods[]`, helpers de destruição (`static`), `Attributes[]`, `Map_GetItem` 1182, `Map_SetItem`, `Seq_Contains` (`static`), `Mapping`, `Sequence`, `KX_GameObject::Type` |
| 1387–fim | getters/setters de atributos Python (`pyattr_get_*`, `pyattr_set_*`, a partir de `pyattr_get_name` 1442) e `py_get_*_item` |

## `Ketsji/KX_GameObject_PyMethods.cpp` (1.857 linhas)

Bindings Python, parte 2: métodos (`PyApply*` a partir de `PyApplyForce` 136, `EXP_PYMETHODDEF_DOC*`: rayCast,
getVectTo, playAction, addDebugProperty, …). Repete a macro `PYTHON_CHECK_PHYSICS_CONTROLLER` (usada nos dois
arquivos). Helpers `static`: `py_vehicle_float` 1033, `CheckRayCastObject` 1237, `none_tuple_3` 1323,
`layer_check` 1540. Também traz `RayCastData`/`RayHit`/`NeedRayCast` e `ConvertPythonToGameObject` 1794.

## Como achar algo

- **Um atributo Python** (`obj.worldPosition`): procure `pyattr_get_worldPosition` em `KX_GameObject_Python.cpp`.
- **Um método Python** (`obj.rayCast`): procure `EXP_PYMETHODDEF_DOC(KX_GameObject, rayCast` em
  `KX_GameObject_PyMethods.cpp`; sua entrada na tabela está em `Methods[]` de `KX_GameObject_Python.cpp`.
- **Um método C++**: procure `KX_GameObject::Nome(` e use a tabela do núcleo para o domínio.
- **Quem chama/instancia**: `KX_Scene.cpp` (réplica, `AddObject`), `BL_BlenderDataConversion.cpp`
  (criação a partir do `.blend`) e as subclasses `KX_Camera`, `KX_LightObject`, `KX_FontObject`,
  `KX_Speaker`, `BL_ArmatureObject`.
