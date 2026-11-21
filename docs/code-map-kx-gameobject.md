# Mapa de código — `KX_GameObject`

Guia de navegação para achar rápido onde fica cada responsabilidade de `KX_GameObject` sem ler os arquivos
inteiros. Não descreve arquitetura nem decisões; é só um índice. A classe está dividida em três arquivos:
o núcleo C++ em [`KX_GameObject.cpp`](../source/source/gameengine/Ketsji/KX_GameObject.cpp) e os bindings
Python em [`KX_GameObject_Python.cpp`](../source/source/gameengine/Ketsji/KX_GameObject_Python.cpp)
(tabelas, tipo e atributos) e
[`KX_GameObject_PyMethods.cpp`](../source/source/gameengine/Ketsji/KX_GameObject_PyMethods.cpp) (métodos).

**Linhas conferidas em 2026-11-20 (`HEAD` `d09c51a4`).** Números de linha são aproximados e envelhecem a cada
edição: use-os como ponto de partida e confirme com `grep -n "KX_GameObject::NomeDoMetodo"`.

Para a declaração das classes e membros, o header é
[`KX_GameObject.h`](../source/source/gameengine/Ketsji/KX_GameObject.h) (1.453 linhas).

## `Ketsji/KX_GameObject.cpp` (2.814 linhas)

Núcleo C++.

Os métodos de um mesmo domínio **não são contíguos**: por exemplo, animação aparece em 643–698 e de novo em
803–818, e partículas ficam no meio do bloco de animação. Procure pelo nome, não pela faixa.

| Domínio | Métodos (linha inicial) |
|---|---|
| Ciclo de vida | construtor 120, construtor de cópia 165, destrutor 233, `GetReplica` 1079, `RemoveRessources` 1089 |
| Identidade e propriedades | `GetName`/`SetName` 359–365, `GetClientObject` 345, `GetRuntimeProperty`/`SetRuntimeProperty` 454–474, `GetBlenderObject` 2386, `GetConvertObjectInfo`/`SetConvertObjectInfo` 2407–2412 |
| Veículo (parâmetros armazenados) | `Set/GetVehicle*` 303–358 (constraint id, roda de direção, torque, RPM, marchas, tipo de câmbio) |
| Controllers (física/gráfico) | `GetPhysicsController` 369, `SetPhysicsController` 497, `Get/SetGraphicController` 436–441, `ActivateGraphicController` 1045, `GetDeformer` 364 |
| Grupos/instâncias e constraints | `Get/SetDupliGroupObject` 446/481, `Get/Add/RemoveInstanceObject(s)` 451–473, `GetConstraints`/`ReplicateConstraints` 563–568 |
| Hierarquia | `GetParent` 581, `SetParent` 597, `RemoveParent` 669 |
| Animação | `GetActionManager` 715, `PlayAction` 724, `StopAction` 747, `IsActionDone` 752, `IsActionsSuspended` 797, `UpdateActionManager` 802, frames/nomes/camadas 688–698 e 803–818, `SetPlayMode` 1023, `SuspendAnimations`/`ResumeAnimations` 2545–2555, `Get/SetAnimationEventManager` 1389–1402, `GetDoAnimations`/`SetHalfAnimations` 1881–1893 |
| Partículas GPU | `SetupGPUParticlesBuffer` 886, `SetupGPUParticles` 952, `SetupGPUParticlesMix` 957, `UpdateParticles` 962, `GetParticleBuffer(Mix)` 793–798 |
| Colisão | `Set/GetCollisionGroup` 850/865, `Set/GetCollisionMask` 857/869, `Register/UnregisterCollisionCallbacks` 2157–2178, `RunCollisionCallbacks` 2593 |
| Física: parâmetros | `IsDynamic` 1113, damping 925–956, CCD 964–970, **soft body** (`SetSoft*`, coeficientes, solver iterations) 981–1154 |
| Física: forças e velocidades | `ApplyForce/Torque/Movement/Rotation` 1166–1189, `Add/SetLinearVelocity`, `SetAngularVelocity` 2045–2060, `GetMass`…`GetVelocity` 2236–2303, `SuspendPhysics`/`RestorePhysics` 2528–2535 |
| Malhas e renderização | `UpdateBlenderObjectMatrix` 1405, `AddMeshUser` 1416, `UpdateBuckets` 1468, `ReplaceMesh` 1491, `RemoveMeshes` 1521, `GetMeshList` 1538, `Renderable` 1548, cor 1686–1691, `Get/SetPassIndex` 1654–1659, `Get/SetLayer` 1644–1649 |
| LOD | `Set/GetLodManager` 1291–1313, `UpdateLod` 1600, `GetVisibleLOD`/`UpdateVisibleLOD` 1892–1897 |
| Visibilidade e depuração | `GetVisible`/`SetVisible` 1929/1563, `SetOccluder` 1957, `SetUseDebugProperties` 1992, helpers `static` `setVisible_recursive` 1912, `setOccluder_recursive` 1941, `setDebug_recursive` 1969 |
| Atividade e culling | `UpdateActivity` 1775, `Get/SetActivityCullingInfo` 2092–2097, `SetActivityCulling` 2479, `UpdateBounds` 2417, `Get/SetBoundsAabb` 2070–2081, `GetCullingNode` 2464 |
| SceneGraph e transformação | `UpdateTransform`/`SynchronizeTransform` 1847–1876, `AlignAxisToVect` 2062, `NodeSet*`/`NodeGet*` 1878–2015, `SetNode` 2412 |
| Componentes Python | `SetComponents` 2735, `UpdateComponents` 2740 (runtime; ficam no núcleo apesar do `#ifdef WITH_PYTHON`) |
| Helpers `static` do núcleo | `setGraphicController_recursive` 1028, `walk_children`/`walk_parent` 2694–2716 (servem a `GetChildren*`) |

## `Ketsji/KX_GameObject_Python.cpp` (2.896 linhas)

Bindings Python, parte 1. Tudo dentro de `#ifdef WITH_PYTHON`. Ordem do arquivo:

| Linhas | Conteúdo |
|---|---|
| 127–417 | macro `PYTHON_CHECK_PHYSICS_CONTROLLER`, callbacks mathutils (`static`), `KX_GameObject_Mathutils_Callback_Init` 413 (público, chamada por `KX_PythonInitTypes.cpp`) |
| 419–1386 | `Methods[]`, helpers de destruição (`static`), `Attributes[]`, `Map_GetItem` 1194, `Map_SetItem`, `Seq_Contains` (`static`), `Mapping`, `Sequence`, `KX_GameObject::Type` |
| 1387–fim | getters/setters de atributos Python (`pyattr_get_*`, `pyattr_set_*`, a partir de `pyattr_get_name` 1459) e `py_get_*_item` |

## `Ketsji/KX_GameObject_PyMethods.cpp` (2.024 linhas)

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
