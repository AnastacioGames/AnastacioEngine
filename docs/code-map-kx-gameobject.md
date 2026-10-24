# Mapa de código — `KX_GameObject`

Guia de navegação para achar rápido onde fica cada responsabilidade de `KX_GameObject` sem ler os arquivos
inteiros. Não descreve arquitetura nem decisões; é só um índice. A classe está dividida em três arquivos:
o núcleo C++ em [`KX_GameObject.cpp`](../source/source/gameengine/Ketsji/KX_GameObject.cpp) e os bindings
Python em [`KX_GameObject_Python.cpp`](../source/source/gameengine/Ketsji/KX_GameObject_Python.cpp)
(tabelas, tipo e atributos) e
[`KX_GameObject_PyMethods.cpp`](../source/source/gameengine/Ketsji/KX_GameObject_PyMethods.cpp) (métodos).

**Linhas conferidas em 2026-10-23 (`HEAD` `7a93da6c`).** Números de linha são aproximados e envelhecem a cada
edição: use-os como ponto de partida e confirme com `grep -n "KX_GameObject::NomeDoMetodo"`.

Para a declaração das classes e membros, o header é
[`KX_GameObject.h`](../source/source/gameengine/Ketsji/KX_GameObject.h) (1.412 linhas).

## `Ketsji/KX_GameObject.cpp` (2.728 linhas)

Núcleo C++.

Os métodos de um mesmo domínio **não são contíguos**: por exemplo, animação aparece em 643–698 e de novo em
803–818, e partículas ficam no meio do bloco de animação. Procure pelo nome, não pela faixa.

| Domínio | Métodos (linha inicial) |
|---|---|
| Ciclo de vida | construtor 120, construtor de cópia 165, destrutor 233, `GetReplica` 1032, `RemoveRessources` 1042 |
| Identidade e propriedades | `GetName`/`SetName` 357–363, `GetClientObject` 343, `GetRuntimeProperty`/`SetRuntimeProperty` 452–472, `GetBlenderObject` 2302, `GetConvertObjectInfo`/`SetConvertObjectInfo` 2323–2328 |
| Veículo (parâmetros armazenados) | `Set/GetVehicle*` 303–358 (constraint id, roda de direção, torque, RPM, marchas, tipo de câmbio) |
| Controllers (física/gráfico) | `GetPhysicsController` 367, `SetPhysicsController` 495, `Get/SetGraphicController` 436–441, `ActivateGraphicController` 998, `GetDeformer` 362 |
| Grupos/instâncias e constraints | `Get/SetDupliGroupObject` 446/481, `Get/Add/RemoveInstanceObject(s)` 451–473, `GetConstraints`/`ReplicateConstraints` 561–566 |
| Hierarquia | `GetParent` 579, `SetParent` 595, `RemoveParent` 666 |
| Animação | `GetActionManager` 712, `PlayAction` 721, `StopAction` 744, `IsActionDone` 749, `IsActionsSuspended` 759, `UpdateActionManager` 764, frames/nomes/camadas 688–698 e 803–818, `SetPlayMode` 976, `SuspendAnimations`/`ResumeAnimations` 2459–2469, `Get/SetAnimationEventManager` 1389–1402, `GetDoAnimations`/`SetHalfAnimations` 1797–1809 |
| Partículas GPU | `SetupGPUParticlesBuffer` 839, `SetupGPUParticles` 905, `SetupGPUParticlesMix` 910, `UpdateParticles` 915, `GetParticleBuffer(Mix)` 793–798 |
| Colisão | `Set/GetCollisionGroup` 850/865, `Set/GetCollisionMask` 857/869, `Register/UnregisterCollisionCallbacks` 2157–2178, `RunCollisionCallbacks` 2507 |
| Física: parâmetros | `IsDynamic` 1066, damping 925–956, CCD 964–970, **soft body** (`SetSoft*`, coeficientes, solver iterations) 981–1154 |
| Física: forças e velocidades | `ApplyForce/Torque/Movement/Rotation` 1166–1189, `Add/SetLinearVelocity`, `SetAngularVelocity` 1961–1976, `GetMass`…`GetVelocity` 2152–2219, `SuspendPhysics`/`RestorePhysics` 2442–2449 |
| Malhas e renderização | `UpdateBlenderObjectMatrix` 1358, `AddMeshUser` 1369, `UpdateBuckets` 1421, `ReplaceMesh` 1444, `RemoveMeshes` 1474, `GetMeshList` 1491, `Renderable` 1501, cor 1686–1691, `Get/SetPassIndex` 1654–1659, `Get/SetLayer` 1644–1649 |
| LOD | `Set/GetLodManager` 1291–1313, `UpdateLod` 1549, `GetVisibleLOD`/`UpdateVisibleLOD` 1808–1813 |
| Visibilidade e depuração | `GetVisible`/`SetVisible` 1845/1563, `SetOccluder` 1873, `SetUseDebugProperties` 1908, helpers `static` `setVisible_recursive` 1828, `setOccluder_recursive` 1857, `setDebug_recursive` 1885 |
| Atividade e culling | `UpdateActivity` 1685, `Get/SetActivityCullingInfo` 2092–2097, `SetActivityCulling` 2395, `UpdateBounds` 2333, `Get/SetBoundsAabb` 2070–2081, `GetCullingNode` 2380 |
| SceneGraph e transformação | `UpdateTransform`/`SynchronizeTransform` 1763–1792, `AlignAxisToVect` 1978, `NodeSet*`/`NodeGet*` 1878–2015, `SetNode` 2328 |
| Componentes Python | `SetComponents` 2649, `UpdateComponents` 2654 (runtime; ficam no núcleo apesar do `#ifdef WITH_PYTHON`) |
| Helpers `static` do núcleo | `setGraphicController_recursive` 981, `walk_children`/`walk_parent` 2608–2630 (servem a `GetChildren*`) |

## `Ketsji/KX_GameObject_Python.cpp` (2.816 linhas)

Bindings Python, parte 1. Tudo dentro de `#ifdef WITH_PYTHON`. Ordem do arquivo:

| Linhas | Conteúdo |
|---|---|
| 127–417 | macro `PYTHON_CHECK_PHYSICS_CONTROLLER`, callbacks mathutils (`static`), `KX_GameObject_Mathutils_Callback_Init` 410 (público, chamada por `KX_PythonInitTypes.cpp`) |
| 419–1386 | `Methods[]`, helpers de destruição (`static`), `Attributes[]`, `Map_GetItem` 1179, `Map_SetItem`, `Seq_Contains` (`static`), `Mapping`, `Sequence`, `KX_GameObject::Type` |
| 1387–fim | getters/setters de atributos Python (`pyattr_get_*`, `pyattr_set_*`, a partir de `pyattr_get_name` 1387) e `py_get_*_item` |

## `Ketsji/KX_GameObject_PyMethods.cpp` (1.853 linhas)

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
