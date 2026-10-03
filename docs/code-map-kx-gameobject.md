# Mapa de código — `KX_GameObject.cpp`

Guia de navegação para achar rápido onde fica cada responsabilidade de
[`KX_GameObject.cpp`](../source/source/gameengine/Ketsji/KX_GameObject.cpp) (6.328 linhas) sem ler o
arquivo inteiro. Não descreve arquitetura nem decisões; é só um índice.

**Linhas conferidas em 2026-10-02 (`HEAD` `9afb6b2a`).** Números de linha são aproximados e envelhecem a cada
edição: use-os como ponto de partida e confirme com `grep -n "KX_GameObject::NomeDoMetodo"`. Se o arquivo
for dividido, este mapa deve
ser refeito.

Para a declaração das classes e membros, o header é
[`KX_GameObject.h`](../source/source/gameengine/Ketsji/KX_GameObject.h) (1.348 linhas).

## Núcleo C++ (linhas 1–2360)

Os métodos de um mesmo domínio **não são contíguos**: por exemplo, animação aparece em 643–698 e de novo em
803–818, e partículas ficam no meio do bloco de animação. Procure pelo nome, não pela faixa.

| Domínio | Métodos (linha inicial) |
|---|---|
| Ciclo de vida | construtor 120, construtor de cópia 165, destrutor 233, `GetReplica` 940, `RemoveRessources` 950 |
| Identidade e propriedades | `GetName`/`SetName` 319–325, `GetClientObject` 305, `GetRuntimeProperty`/`SetRuntimeProperty` 414–434, `GetBlenderObject` 2150, `GetConvertObjectInfo`/`SetConvertObjectInfo` 2161–2166 |
| Veículo (parâmetros armazenados) | `Set/GetVehicle*` 303–358 (constraint id, roda de direção, torque, RPM, marchas, tipo de câmbio) |
| Controllers (física/gráfico) | `GetPhysicsController` 329, `SetPhysicsController` 457, `Get/SetGraphicController` 436–441, `ActivateGraphicController` 906, `GetDeformer` 324 |
| Grupos/instâncias e constraints | `Get/SetDupliGroupObject` 446/481, `Get/Add/RemoveInstanceObject(s)` 451–473, `GetConstraints`/`ReplicateConstraints` 523–528 |
| Hierarquia | `GetParent` 541, `SetParent` 557, `RemoveParent` 628 |
| Animação | `GetActionManager` 674, `PlayAction` 684, `StopAction` 699, `IsActionDone` 704, `IsActionsSuspended` 709, `UpdateActionManager` 714, frames/nomes/camadas 688–698 e 803–818, `SetPlayMode` 884, `SuspendAnimations`/`ResumeAnimations` 2280–2290, `Get/SetAnimationEventManager` 1389–1402, `GetDoAnimations`/`SetHalfAnimations` 1645–1657 |
| Partículas GPU | `SetupGPUParticlesBuffer` 734, `SetupGPUParticles` 818, `SetupGPUParticlesMix` 823, `UpdateParticles` 828, `GetParticleBuffer(Mix)` 793–798 |
| Colisão | `Set/GetCollisionGroup` 850/865, `Set/GetCollisionMask` 857/869, `Register/UnregisterCollisionCallbacks` 2157–2178, `RunCollisionCallbacks` 2328 |
| Física: parâmetros | `IsDynamic` 975, damping 925–956, CCD 964–970, **soft body** (`SetSoft*`, coeficientes, solver iterations) 981–1154 |
| Física: forças e velocidades | `ApplyForce/Torque/Movement/Rotation` 1166–1189, `Add/SetLinearVelocity`, `SetAngularVelocity` 1809–1824, `GetMass`…`GetVelocity` 2000–2067, `SuspendPhysics`/`RestorePhysics` 2263–2270 |
| Malhas e renderização | `UpdateBlenderObjectMatrix` 1267, `AddMeshUser` 1278, `UpdateBuckets` 1324, `ReplaceMesh` 1347, `RemoveMeshes` 1366, `GetMeshList` 1379, `Renderable` 1389, cor 1686–1691, `Get/SetPassIndex` 1654–1659, `Get/SetLayer` 1644–1649 |
| LOD | `Set/GetLodManager` 1291–1313, `UpdateLod` 1421, `GetVisibleLOD`/`UpdateVisibleLOD` 1656–1661 |
| Visibilidade e depuração | `GetVisible`/`SetVisible` 1693/1563, `SetOccluder` 1721, `SetUseDebugProperties` 1756, helpers `static` `setVisible_recursive` 1546, `setOccluder_recursive` 1575, `setDebug_recursive` 1603 |
| Atividade e culling | `UpdateActivity` 1537, `Get/SetActivityCullingInfo` 2092–2097, `SetActivityCulling` 2232, `UpdateBounds` 2171, `Get/SetBoundsAabb` 2070–2081, `GetCullingNode` 2217 |
| SceneGraph e transformação | `UpdateTransform`/`SynchronizeTransform` 1611–1640, `AlignAxisToVect` 1826, `NodeSet*`/`NodeGet*` 1878–2015, `SetNode` 2166 |
| Componentes Python | `SetComponents` 2470, `UpdateComponents` 2475 (runtime; ficam no núcleo apesar do `#ifdef WITH_PYTHON`) |
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
