# Mapa de código — `KX_GameObject.cpp`

Guia de navegação para achar rápido onde fica cada responsabilidade de
[`KX_GameObject.cpp`](../source/source/gameengine/Ketsji/KX_GameObject.cpp) (6.501 linhas) sem ler o
arquivo inteiro. Não descreve arquitetura nem decisões; é só um índice.

**Linhas conferidas em 2026-10-09 (`HEAD` `6d8c640d`).** Números de linha são aproximados e envelhecem a cada
edição: use-os como ponto de partida e confirme com `grep -n "KX_GameObject::NomeDoMetodo"`. Se o arquivo
for dividido, este mapa deve
ser refeito.

Para a declaração das classes e membros, o header é
[`KX_GameObject.h`](../source/source/gameengine/Ketsji/KX_GameObject.h) (1.387 linhas).

## Núcleo C++ (linhas 1–2360)

Os métodos de um mesmo domínio **não são contíguos**: por exemplo, animação aparece em 643–698 e de novo em
803–818, e partículas ficam no meio do bloco de animação. Procure pelo nome, não pela faixa.

| Domínio | Métodos (linha inicial) |
|---|---|
| Ciclo de vida | construtor 120, construtor de cópia 165, destrutor 233, `GetReplica` 991, `RemoveRessources` 1001 |
| Identidade e propriedades | `GetName`/`SetName` 325–331, `GetClientObject` 311, `GetRuntimeProperty`/`SetRuntimeProperty` 420–440, `GetBlenderObject` 2212, `GetConvertObjectInfo`/`SetConvertObjectInfo` 2233–2238 |
| Veículo (parâmetros armazenados) | `Set/GetVehicle*` 303–358 (constraint id, roda de direção, torque, RPM, marchas, tipo de câmbio) |
| Controllers (física/gráfico) | `GetPhysicsController` 335, `SetPhysicsController` 463, `Get/SetGraphicController` 436–441, `ActivateGraphicController` 957, `GetDeformer` 330 |
| Grupos/instâncias e constraints | `Get/SetDupliGroupObject` 446/481, `Get/Add/RemoveInstanceObject(s)` 451–473, `GetConstraints`/`ReplicateConstraints` 529–534 |
| Hierarquia | `GetParent` 547, `SetParent` 563, `RemoveParent` 634 |
| Animação | `GetActionManager` 680, `PlayAction` 689, `StopAction` 712, `IsActionDone` 717, `IsActionsSuspended` 727, `UpdateActionManager` 732, frames/nomes/camadas 688–698 e 803–818, `SetPlayMode` 935, `SuspendAnimations`/`ResumeAnimations` 2353–2363, `Get/SetAnimationEventManager` 1389–1402, `GetDoAnimations`/`SetHalfAnimations` 1707–1719 |
| Partículas GPU | `SetupGPUParticlesBuffer` 804, `SetupGPUParticles` 864, `SetupGPUParticlesMix` 869, `UpdateParticles` 874, `GetParticleBuffer(Mix)` 793–798 |
| Colisão | `Set/GetCollisionGroup` 850/865, `Set/GetCollisionMask` 857/869, `Register/UnregisterCollisionCallbacks` 2157–2178, `RunCollisionCallbacks` 2401 |
| Física: parâmetros | `IsDynamic` 1025, damping 925–956, CCD 964–970, **soft body** (`SetSoft*`, coeficientes, solver iterations) 981–1154 |
| Física: forças e velocidades | `ApplyForce/Torque/Movement/Rotation` 1166–1189, `Add/SetLinearVelocity`, `SetAngularVelocity` 1871–1886, `GetMass`…`GetVelocity` 2062–2129, `SuspendPhysics`/`RestorePhysics` 2336–2343 |
| Malhas e renderização | `UpdateBlenderObjectMatrix` 1317, `AddMeshUser` 1328, `UpdateBuckets` 1380, `ReplaceMesh` 1403, `RemoveMeshes` 1423, `GetMeshList` 1440, `Renderable` 1450, cor 1686–1691, `Get/SetPassIndex` 1654–1659, `Get/SetLayer` 1644–1649 |
| LOD | `Set/GetLodManager` 1291–1313, `UpdateLod` 1482, `GetVisibleLOD`/`UpdateVisibleLOD` 1718–1723 |
| Visibilidade e depuração | `GetVisible`/`SetVisible` 1755/1563, `SetOccluder` 1783, `SetUseDebugProperties` 1818, helpers `static` `setVisible_recursive` 1546, `setOccluder_recursive` 1575, `setDebug_recursive` 1603 |
| Atividade e culling | `UpdateActivity` 1598, `Get/SetActivityCullingInfo` 2092–2097, `SetActivityCulling` 2305, `UpdateBounds` 2243, `Get/SetBoundsAabb` 2070–2081, `GetCullingNode` 2290 |
| SceneGraph e transformação | `UpdateTransform`/`SynchronizeTransform` 1673–1702, `AlignAxisToVect` 1888, `NodeSet*`/`NodeGet*` 1878–2015, `SetNode` 2238 |
| Componentes Python | `SetComponents` 2543, `UpdateComponents` 2548 (runtime; ficam no núcleo apesar do `#ifdef WITH_PYTHON`) |
| Helpers `static` do núcleo | `setGraphicController_recursive` 823, `walk_children`/`walk_parent` 2224–2246 (servem a `GetChildren*`) |

## Bindings Python (linhas 2363–5979)

Tudo dentro de `#ifdef WITH_PYTHON`. Ordem do arquivo:

| Linhas | Conteúdo |
|---|---|
| 2363–2653 | macro `PYTHON_CHECK_PHYSICS_CONTROLLER`, callbacks mathutils (`static`), `KX_GameObject_Mathutils_Callback_Init` (público, chamada por `KX_PythonInitTypes.cpp`) |
| 2655–3110 | `Methods[]`, `Attributes[]`, `Map_GetItem`/`Map_SetItem`/`Seq_Contains` (`static`), `Mapping`, `Sequence`, `KX_GameObject::Type` |
| 3113–4352 | getters/setters de atributos Python (`pyattr_get_*`, `pyattr_set_*`, ~167) e `py_get_*_item` |
| 4354–5979 | métodos Python: `PyApply*` e `EXP_PYMETHODDEF_DOC*` (rayCast, getVectTo, playAction, addDebugProperty, …) e helpers `static` `CheckRayCastObject`, `none_tuple_*`, `layer_check` |

## Como achar algo

- **Um atributo Python** (`obj.worldPosition`): procure `pyattr_get_worldPosition` na faixa 3113–4352.
- **Um método Python** (`obj.rayCast`): procure `EXP_PYMETHODDEF_DOC(KX_GameObject, rayCast` na faixa
  4354–5979; sua entrada na tabela está em `Methods[]` (2657–2757).
- **Um método C++**: procure `KX_GameObject::Nome(` e use a tabela acima para o domínio.
- **Quem chama/instancia**: `KX_Scene.cpp` (réplica, `AddObject`), `BL_BlenderDataConversion.cpp`
  (criação a partir do `.blend`) e as subclasses `KX_Camera`, `KX_LightObject`, `KX_FontObject`,
  `KX_Speaker`, `BL_ArmatureObject`.
