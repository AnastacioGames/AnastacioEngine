# Mapa de código — `KX_GameObject.cpp`

Guia de navegação para achar rápido onde fica cada responsabilidade de
[`KX_GameObject.cpp`](../source/source/gameengine/Ketsji/KX_GameObject.cpp) (5.979 linhas) sem ler o
arquivo inteiro. Não descreve arquitetura nem decisões; é só um índice.

**Válido para o `HEAD` `bd513d15` (2026-09-21).** Números de linha são aproximados e envelhecem a cada
edição: use-os como ponto de partida e confirme com `grep -n "KX_GameObject::NomeDoMetodo"`. Se o arquivo
for dividido, este mapa deve
ser refeito.

Para a declaração das classes e membros, o header é
[`KX_GameObject.h`](../source/source/gameengine/Ketsji/KX_GameObject.h) (1.304 linhas).

## Núcleo C++ (linhas 1–2360)

Os métodos de um mesmo domínio **não são contíguos**: por exemplo, animação aparece em 643–698 e de novo em
803–818, e partículas ficam no meio do bloco de animação. Procure pelo nome, não pela faixa.

| Domínio | Métodos (linha inicial) |
|---|---|
| Ciclo de vida | construtor 120, construtor de cópia 165, destrutor 233, `GetReplica` 874, `RemoveRessources` 884 |
| Identidade e propriedades | `GetName`/`SetName` 282–288, `GetClientObject` 274, `GetRuntimeProperty`/`SetRuntimeProperty` 363–383, `GetBlenderObject` 2020, `GetConvertObjectInfo`/`SetConvertObjectInfo` 2026–2031 |
| Veículo (parâmetros armazenados) | `Set/GetVehicle*` 303–358 (constraint id, roda de direção, torque, RPM, marchas, tipo de câmbio) |
| Controllers (física/gráfico) | `GetPhysicsController` 298, `SetPhysicsController` 426, `Get/SetGraphicController` 436–441, `ActivateGraphicController` 840, `GetDeformer` 293 |
| Grupos/instâncias e constraints | `Get/SetDupliGroupObject` 446/481, `Get/Add/RemoveInstanceObject(s)` 451–473, `GetConstraints`/`ReplicateConstraints` 487–492 |
| Hierarquia | `GetParent` 510, `SetParent` 526, `RemoveParent` 597 |
| Animação | `GetActionManager` 643, `PlayAction` 653, `StopAction` 668, `IsActionDone` 673, `IsActionsSuspended` 678, `UpdateActionManager` 683, frames/nomes/camadas 688–698 e 803–818, `SetPlayMode` 818, `SuspendAnimations`/`ResumeAnimations` 2140–2150, `Get/SetAnimationEventManager` 1389–1402, `GetDoAnimations`/`SetHalfAnimations` 1503–1515 |
| Partículas GPU | `SetupGPUParticlesBuffer` 703, `SetupGPUParticles` 766, `SetupGPUParticlesMix` 771, `UpdateParticles` 776, `GetParticleBuffer(Mix)` 793–798 |
| Colisão | `Set/GetCollisionGroup` 850/865, `Set/GetCollisionMask` 857/869, `Register/UnregisterCollisionCallbacks` 2157–2178, `RunCollisionCallbacks` 2198 |
| Física: parâmetros | `IsDynamic` 909, damping 925–956, CCD 964–970, **soft body** (`SetSoft*`, coeficientes, solver iterations) 981–1154 |
| Física: forças e velocidades | `ApplyForce/Torque/Movement/Rotation` 1166–1189, `Add/SetLinearVelocity`, `SetAngularVelocity` 1664–1679, `GetMass`…`GetVelocity` 1803–1870, `SuspendPhysics`/`RestorePhysics` 2126–2133 |
| Malhas e renderização | `UpdateBlenderObjectMatrix` 1201, `AddMeshUser` 1212, `UpdateBuckets` 1229, `ReplaceMesh` 1244, `RemoveMeshes` 1263, `GetMeshList` 1276, `Renderable` 1286, cor 1686–1691, `Get/SetPassIndex` 1654–1659, `Get/SetLayer` 1644–1649 |
| LOD | `Set/GetLodManager` 1291–1313, `UpdateLod` 1318, `GetVisibleLOD`/`UpdateVisibleLOD` 1521–1526 |
| Visibilidade e depuração | `GetVisible`/`SetVisible` 1497/1563, `SetOccluder` 1591, `SetUseDebugProperties` 1626, helpers `static` `setVisible_recursive` 1546, `setOccluder_recursive` 1575, `setDebug_recursive` 1603 |
| Atividade e culling | `UpdateActivity` 1407, `Get/SetActivityCullingInfo` 2092–2097, `SetActivityCulling` 2102, `UpdateBounds` 2041, `Get/SetBoundsAabb` 2070–2081, `GetCullingNode` 2087 |
| SceneGraph e transformação | `UpdateTransform`/`SynchronizeTransform` 1463–1492, `AlignAxisToVect` 1696, `NodeSet*`/`NodeGet*` 1878–2015, `SetNode` 2036 |
| Componentes Python | `SetComponents` 2287, `UpdateComponents` 2292 (runtime; ficam no núcleo apesar do `#ifdef WITH_PYTHON`) |
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
