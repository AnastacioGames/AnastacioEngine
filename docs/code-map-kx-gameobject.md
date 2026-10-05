# Mapa de código — `KX_GameObject.cpp`

Guia de navegação para achar rápido onde fica cada responsabilidade de
[`KX_GameObject.cpp`](../source/source/gameengine/Ketsji/KX_GameObject.cpp) (6.479 linhas) sem ler o
arquivo inteiro. Não descreve arquitetura nem decisões; é só um índice.

**Linhas conferidas em 2026-10-05 (`HEAD` `77fe23e9`).** Números de linha são aproximados e envelhecem a cada
edição: use-os como ponto de partida e confirme com `grep -n "KX_GameObject::NomeDoMetodo"`. Se o arquivo
for dividido, este mapa deve
ser refeito.

Para a declaração das classes e membros, o header é
[`KX_GameObject.h`](../source/source/gameengine/Ketsji/KX_GameObject.h) (1.384 linhas).

## Núcleo C++ (linhas 1–2360)

Os métodos de um mesmo domínio **não são contíguos**: por exemplo, animação aparece em 643–698 e de novo em
803–818, e partículas ficam no meio do bloco de animação. Procure pelo nome, não pela faixa.

| Domínio | Métodos (linha inicial) |
|---|---|
| Ciclo de vida | construtor 120, construtor de cópia 165, destrutor 233, `GetReplica` 978, `RemoveRessources` 988 |
| Identidade e propriedades | `GetName`/`SetName` 324–330, `GetClientObject` 310, `GetRuntimeProperty`/`SetRuntimeProperty` 419–439, `GetBlenderObject` 2188, `GetConvertObjectInfo`/`SetConvertObjectInfo` 2209–2214 |
| Veículo (parâmetros armazenados) | `Set/GetVehicle*` 303–358 (constraint id, roda de direção, torque, RPM, marchas, tipo de câmbio) |
| Controllers (física/gráfico) | `GetPhysicsController` 334, `SetPhysicsController` 462, `Get/SetGraphicController` 436–441, `ActivateGraphicController` 944, `GetDeformer` 329 |
| Grupos/instâncias e constraints | `Get/SetDupliGroupObject` 446/481, `Get/Add/RemoveInstanceObject(s)` 451–473, `GetConstraints`/`ReplicateConstraints` 528–533 |
| Hierarquia | `GetParent` 546, `SetParent` 562, `RemoveParent` 633 |
| Animação | `GetActionManager` 679, `PlayAction` 689, `StopAction` 704, `IsActionDone` 709, `IsActionsSuspended` 714, `UpdateActionManager` 719, frames/nomes/camadas 688–698 e 803–818, `SetPlayMode` 922, `SuspendAnimations`/`ResumeAnimations` 2328–2338, `Get/SetAnimationEventManager` 1389–1402, `GetDoAnimations`/`SetHalfAnimations` 1683–1695 |
| Partículas GPU | `SetupGPUParticlesBuffer` 791, `SetupGPUParticles` 851, `SetupGPUParticlesMix` 856, `UpdateParticles` 861, `GetParticleBuffer(Mix)` 793–798 |
| Colisão | `Set/GetCollisionGroup` 850/865, `Set/GetCollisionMask` 857/869, `Register/UnregisterCollisionCallbacks` 2157–2178, `RunCollisionCallbacks` 2376 |
| Física: parâmetros | `IsDynamic` 1013, damping 925–956, CCD 964–970, **soft body** (`SetSoft*`, coeficientes, solver iterations) 981–1154 |
| Física: forças e velocidades | `ApplyForce/Torque/Movement/Rotation` 1166–1189, `Add/SetLinearVelocity`, `SetAngularVelocity` 1847–1862, `GetMass`…`GetVelocity` 2038–2105, `SuspendPhysics`/`RestorePhysics` 2311–2318 |
| Malhas e renderização | `UpdateBlenderObjectMatrix` 1305, `AddMeshUser` 1316, `UpdateBuckets` 1362, `ReplaceMesh` 1385, `RemoveMeshes` 1404, `GetMeshList` 1417, `Renderable` 1427, cor 1686–1691, `Get/SetPassIndex` 1654–1659, `Get/SetLayer` 1644–1649 |
| LOD | `Set/GetLodManager` 1291–1313, `UpdateLod` 1459, `GetVisibleLOD`/`UpdateVisibleLOD` 1694–1699 |
| Visibilidade e depuração | `GetVisible`/`SetVisible` 1731/1563, `SetOccluder` 1759, `SetUseDebugProperties` 1794, helpers `static` `setVisible_recursive` 1546, `setOccluder_recursive` 1575, `setDebug_recursive` 1603 |
| Atividade e culling | `UpdateActivity` 1575, `Get/SetActivityCullingInfo` 2092–2097, `SetActivityCulling` 2280, `UpdateBounds` 2219, `Get/SetBoundsAabb` 2070–2081, `GetCullingNode` 2265 |
| SceneGraph e transformação | `UpdateTransform`/`SynchronizeTransform` 1649–1678, `AlignAxisToVect` 1864, `NodeSet*`/`NodeGet*` 1878–2015, `SetNode` 2214 |
| Componentes Python | `SetComponents` 2518, `UpdateComponents` 2523 (runtime; ficam no núcleo apesar do `#ifdef WITH_PYTHON`) |
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
