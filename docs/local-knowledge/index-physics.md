# Indice de codigo: physics

> Gerado por `tools/build_code_index.py` (regex sobre o codigo, sem LLM). Colunas: linhas | classes declaradas (.h) ou implementadas (.cpp).
> Arquivos com mais de 1500 linhas estao marcados com **grande**: nao leia inteiros; veja `docs/code-map-*.md` quando existir.

## source/source/gameengine/Physics/Bullet

| arquivo | linhas | classes |
|---|---:|---|
| CcdConstraint.cpp | 207 | `CcdConstraint` |
| CcdConstraint.h | 39 | `CcdConstraint` |
| CcdGraphicController.cpp | 134 | `CcdGraphicController` |
| CcdGraphicController.h | 97 | `CcdGraphicController` |
| CcdMathUtils.h | 54 |  |
| CcdPhysicsController.cpp **grande** | 2593 | `CcdPhysicsController`, `CcdCharacter`, `CcdShapeConstructionInfo`, `DefaultMotionState`, `CleanPairCallback` |
| CcdPhysicsController.h | 976 | `CcdShapeConstructionInfo`, `UVco`, `CcdConstructionInfo`, `CcdCharacter`, `CleanPairCallback`, `CcdPhysicsController` |
| CcdPhysicsEnvironment.cpp **grande** | 3830 | `CcdPhysicsEnvironment`, `CcdCollData`, `CcdOverlapFilterCallBack` |
| CcdPhysicsEnvironment.h | 361 | `CcdPhysicsEnvironment`, `CollisionPair`, `CcdCollData` |

## source/source/gameengine/Physics/Common

| arquivo | linhas | classes |
|---|---:|---|
| PHY_DynamicTypes.h | 106 | `PHY_ICollData`, `PHY_CollisionTestResult` |
| PHY_ICharacter.h | 52 | `PHY_ICharacter` |
| PHY_IConstraint.h | 25 | `PHY_IConstraint` |
| PHY_IController.h | 56 | `PHY_IController` |
| PHY_IGraphicController.h | 59 | `PHY_IGraphicController` |
| PHY_IMotionState.h | 59 | `PHY_IMotionState` |
| PHY_IPhysicsController.h | 203 | `PHY_IPhysicsController` |
| PHY_IPhysicsEnvironment.h | 292 | `PHY_RayCastResult`, `PHY_IRayCastFilterCallback`, `PHY_IPhysicsEnvironment` |
| PHY_IVehicle.h | 194 | `PHY_VehicleWheelConfig`, `PHY_VehicleWheelState`, `PHY_VehicleParameterCommand`, `PHY_IVehicle` |

## source/source/gameengine/Physics/Dummy

| arquivo | linhas | classes |
|---|---:|---|
| DummyPhysicsEnvironment.cpp | 122 | `DummyPhysicsEnvironment` |
| DummyPhysicsEnvironment.h | 149 | `DummyPhysicsEnvironment` |

## source/source/blender/physics

| arquivo | linhas | classes |
|---|---:|---|
| BPH_mass_spring.h | 59 |  |

## source/source/blender/physics/intern

| arquivo | linhas | classes |
|---|---:|---|
| BPH_mass_spring.cpp | 1106 |  |
| ConstrainedConjugateGradient.h | 294 | `MatrixFilter`, `ConstrainedConjugateGradient` |
| eigen_utils.h | 222 | `Vector3`, `Matrix3`, `lVector3f`, `lMatrix3fCtor` |
| hair_volume.cpp | 1154 |  |
| implicit.h | 172 |  |
| implicit_blender.c **grande** | 1964 |  |
| implicit_eigen.cpp | 1339 |  |
