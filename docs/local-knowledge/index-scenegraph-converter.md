# Indice de codigo: scenegraph-converter

> Gerado por `tools/build_code_index.py` (regex sobre o codigo, sem LLM). Colunas: linhas | classes declaradas (.h) ou implementadas (.cpp).
> Arquivos com mais de 1500 linhas estao marcados com **grande**: nao leia inteiros; veja `docs/code-map-*.md` quando existir.

## source/source/gameengine/SceneGraph

| arquivo | linhas | classes |
|---|---:|---|
| SG_BBox.cpp | 101 | `SG_BBox` |
| SG_BBox.h | 79 | `SG_BBox` |
| SG_Controller.cpp | 76 | `SG_Controller` |
| SG_Controller.h | 91 | `SG_Controller` |
| SG_CullingNode.cpp | 26 | `SG_CullingNode` |
| SG_CullingNode.h | 30 | `SG_CullingNode` |
| SG_DList.h | 264 | `SG_DList`, `iterator`, `const_iterator`, `SG_DListHead` |
| SG_Familly.cpp | 37 | `SG_Familly` |
| SG_Familly.h | 53 | `SG_Familly` |
| SG_Frustum.cpp | 270 | `SG_Frustum` |
| SG_Frustum.h | 39 | `SG_Frustum` |
| SG_Interpolator.cpp | 44 | `SG_Interpolator` |
| SG_Interpolator.h | 57 | `SG_Interpolator` |
| SG_Node.cpp | 600 | `SG_Node` |
| SG_Node.h | 362 | `SG_Callbacks`, `SG_Node` |
| SG_ParentRelation.h | 122 | `SG_ParentRelation` |
| SG_QList.h | 167 | `SG_QList`, `iterator` |
| SG_ScalarInterpolator.h | 45 | `SG_ScalarInterpolator` |

## source/source/gameengine/Converter

| arquivo | linhas | classes |
|---|---:|---|
| BL_ActionActuator.cpp | 486 | `BL_ActionActuator` |
| BL_ActionActuator.h | 131 | `BL_ActionActuator` |
| BL_ActionData.cpp | 48 | `BL_ActionData` |
| BL_ActionData.h | 35 | `BL_ActionData` |
| BL_ArmatureActuator.cpp | 300 | `BL_ArmatureActuator` |
| BL_ArmatureActuator.h | 96 | `BL_ArmatureActuator` |
| BL_ArmatureChannel.cpp | 489 | `BL_ArmatureChannel`, `BL_ArmatureBone` |
| BL_ArmatureChannel.h | 97 | `BL_ArmatureChannel`, `BL_ArmatureBone` |
| BL_ArmatureConstraint.cpp | 537 | `BL_ArmatureConstraint` |
| BL_ArmatureConstraint.h | 114 | `BL_ArmatureConstraint` |
| BL_ArmatureObject.cpp | 798 | `BL_ArmatureObject` |
| BL_ArmatureObject.h | 159 | `BL_ArmatureObject`, `BoneRotationOffset` |
| BL_BlenderDataConversion.cpp **grande** | 3938 |  |
| BL_BlenderDataConversion.h | 100 | `BL_MeshMaterial` |
| BL_ConvertActuators.cpp | 1416 |  |
| BL_ConvertActuators.h | 45 |  |
| BL_ConvertControllers.cpp | 243 |  |
| BL_ConvertControllers.h | 47 |  |
| BL_ConvertObjectInfo.cpp | 6 |  |
| BL_ConvertObjectInfo.h | 22 | `BL_ConvertObjectInfo` |
| BL_ConvertProperties.cpp | 304 |  |
| BL_ConvertProperties.h | 44 |  |
| BL_ConvertSensors.cpp | 795 |  |
| BL_ConvertSensors.h | 45 |  |
| BL_Converter.cpp **grande** | 1924 | `BL_Converter`, `SceneSlot` |
| BL_Converter.h | 320 | `BL_Converter`, `SceneSlot`, `ThreadInfo`, `PendingMerge`, `PendingReload` |
| BL_IpoConvert.cpp | 436 |  |
| BL_IpoConvert.h | 68 |  |
| BL_LoadStats.h | 137 | `BL_LoadStats`, `BL_LoadTimer`, `BL_LoadLog`, `Entry` |
| BL_MeshDeformer.cpp | 170 | `BL_MeshDeformer` |
| BL_MeshDeformer.h | 89 | `BL_MeshDeformer` |
| BL_ModifierDeformer.cpp | 213 | `BL_ModifierDeformer` |
| BL_ModifierDeformer.h | 82 | `BL_ModifierDeformer` |
| BL_Resource.cpp | 35 | `Library`, `BL_Resource` |
| BL_Resource.h | 47 | `BL_Resource`, `Library` |
| BL_ScalarInterpolator.cpp | 52 | `BL_ScalarInterpolator` |
| BL_ScalarInterpolator.h | 56 | `BL_ScalarInterpolator` |
| BL_SceneConverter.cpp | 190 | `BL_SceneConverter` |
| BL_SceneConverter.h | 126 | `BL_SceneConverter` |
| BL_ShapeDeformer.cpp | 246 | `BL_ShapeDeformer` |
| BL_ShapeDeformer.h | 80 | `BL_ShapeDeformer` |
| BL_SkinDeformer.cpp | 544 | `BL_SkinDeformer` |
| BL_SkinDeformer.h | 133 | `BL_SkinDeformer` |

## source/source/gameengine/Ketsji

| arquivo | linhas | classes |
|---|---:|---|
| BL_Action.cpp | 578 | `BL_Action` |
| BL_Action.h | 170 | `BL_Action` |
| BL_ActionManager.cpp | 209 | `BL_ActionManager` |
| BL_ActionManager.h | 145 | `BL_ActionManager` |
| BL_BlenderShader.cpp | 420 | `BL_BlenderShader` |
| BL_BlenderShader.h | 105 | `BL_BlenderShader` |
| BL_Shader.cpp | 959 | `BL_Shader` |
| BL_Shader.h | 107 | `BL_Shader` |
| BL_Texture.cpp | 767 | `BL_Texture` |
| BL_Texture.h | 137 | `BL_Texture` |
| KX_2DFilter.cpp | 575 | `KX_2DFilter` |
| KX_2DFilter.h | 100 | `KX_2DFilter`, `ActiveUniform`, `UniformValue` |
| KX_2DFilterManager.cpp | 1351 | `KX_2DFilterManager` |
| KX_2DFilterManager.h | 132 | `KX_2DFilterManager` |
| KX_2DFilterOffScreen.cpp | 116 | `KX_2DFilterOffScreen` |
| KX_2DFilterOffScreen.h | 56 | `KX_2DFilterOffScreen` |
| KX_AddObjectActuator.cpp | 338 | `KX_AddObjectActuator` |
| KX_AddObjectActuator.h | 138 | `KX_AddObjectActuator` |
| KX_AnimationEvent.cpp | 244 | `KX_AnimationEvent` |
| KX_AnimationEvent.h | 89 | `KX_AnimationEvent` |
| KX_AnimationEventManager.cpp | 164 | `KX_AnimationEventManager` |
| KX_AnimationEventManager.h | 79 | `KX_AnimationEventManager` |
| KX_ArmatureSensor.cpp | 220 | `KX_ArmatureSensor` |
| KX_ArmatureSensor.h | 90 | `KX_ArmatureSensor` |
| KX_AudioManager.cpp | 1120 | `KX_AudioManager` |
| KX_AudioManager.h | 164 | `KX_AudioManager`, `DelayedEvent` |
| KX_BatchGroup.cpp | 348 | `KX_BatchGroup` |
| KX_BatchGroup.h | 87 | `KX_BatchGroup` |
| KX_BlenderMaterial.cpp | 1158 | `KX_BlenderMaterial` |
| KX_BlenderMaterial.h | 158 | `KX_BlenderMaterial`, `ScriptUniform` |
| KX_BoneParentNodeRelationship.cpp | 108 | `KX_BoneParentRelation` |
| KX_BoneParentNodeRelationship.h | 66 | `KX_BoneParentRelation` |
| KX_BoundingBox.cpp | 410 | `KX_BoundingBox` |
| KX_BoundingBox.h | 90 | `KX_BoundingBox` |
| KX_Camera.cpp **grande** | 1781 | `KX_Camera`, `View` |
| KX_Camera.h | 430 | `KX_Camera`, `GameFX`, `View` |
| KX_CameraActuator.cpp | 389 | `KX_CameraActuator` |
| KX_CameraActuator.h | 128 | `KX_CameraActuator` |
| KX_CameraIpoSGController.cpp | 63 | `KX_CameraIpoSGController` |
| KX_CameraIpoSGController.h | 75 | `KX_CameraIpoSGController` |
| KX_ChangeColorActuator.cpp | 146 | `KX_ChangeColorActuator` |
| KX_ChangeColorActuator.h | 70 | `KX_ChangeColorActuator` |
| KX_CharacterWrapper.cpp | 315 | `KX_CharacterWrapper` |
| KX_CharacterWrapper.h | 54 | `KX_CharacterWrapper` |
| KX_ClientObjectInfo.h | 79 | `KX_ClientObjectInfo` |
| KX_CollisionContactPoints.cpp | 190 | `KX_CollisionContactPoint`, `KX_CollisionContactPointList` |
| KX_CollisionContactPoints.h | 96 | `KX_CollisionContactPoint`, `KX_CollisionContactPointList` |
| KX_CollisionEventManager.cpp | 275 | `KX_CollisionEventManager`, `NewCollision` |
| KX_CollisionEventManager.h | 96 | `KX_CollisionEventManager`, `NewCollision` |
| KX_CollisionSensor.cpp | 340 | `KX_CollisionSensor` |
| KX_CollisionSensor.h | 145 | `KX_CollisionSensor` |
| KX_ConsoleWindow.cpp | 103 | `KX_ConsoleWindow` |
| KX_ConsoleWindow.h | 48 | `KX_ConsoleWindow` |
| KX_ConstraintActuator.cpp | 633 | `KX_ConstraintActuator` |
| KX_ConstraintActuator.h | 142 | `KX_ConstraintActuator` |
| KX_ConstraintWrapper.cpp | 175 | `KX_ConstraintWrapper` |
| KX_ConstraintWrapper.h | 65 | `KX_ConstraintWrapper` |
| KX_CubeMap.cpp | 155 | `KX_CubeMap` |
| KX_CubeMap.h | 63 | `KX_CubeMap` |
| KX_CullingHandler.cpp | 111 | `KX_CullingHandler` |
| KX_CullingHandler.h | 44 | `KX_CullingHandler` |
| KX_CutsceneManager.cpp | 186 | `KX_CutsceneManager` |
| KX_CutsceneManager.h | 134 | `KX_CutsceneManager`, `Event`, `Sequence`, `SpawnedObjects` |
| KX_DebugMode.cpp **grande** | 1748 | `KX_DebugMode` |
| KX_DebugMode.h | 279 | `ScrollingBuffer`, `KX_DebugMode`, `LogicEvent` |
| KX_DebugRenderer.cpp | 125 | `KX_DebugRenderer` |
| KX_DebugRenderer.h | 61 | `KX_DebugRenderer` |
| KX_DentDeformer.cpp | 450 | `KX_DentDeformer` |
| KX_DentDeformer.h | 120 | `KX_DentDeformer` |
| KX_DestructionManager.cpp **grande** | 1679 | `KX_DestructionManager` |
| KX_DestructionManager.h | 300 | `KX_DestructionManager`, `Entry`, `PendingScrape`, `PendingDent`, `DecalAnchor`, `Decal` |
| KX_DynamicActuator.cpp | 184 | `KX_DynamicActuator` |
| KX_DynamicActuator.h | 78 | `KX_DynamicActuator` |
| KX_EmptyObject.cpp | 37 |  |
| KX_EmptyObject.h | 45 | `KX_EmptyObject` |
| KX_EndObjectActuator.cpp | 133 | `KX_EndObjectActuator` |
| KX_EndObjectActuator.h | 72 | `KX_EndObjectActuator` |
| KX_EngineProfiler.cpp | 399 |  |
| KX_EngineProfiler.h | 140 | `Scope`, `Sections` |
| KX_FontObject.cpp | 863 | `KX_FontObject` |
| KX_FontObject.h | 192 | `KX_LocaleState`, `KX_FontObject` |
| KX_GameActuator.cpp | 220 | `KX_GameActuator` |
| KX_GameActuator.h | 95 | `KX_GameActuator` |
| KX_GameObject.cpp **grande** | 2728 | `KX_GameObject`, `ActivityCullingInfo` |
| KX_GameObject.h | 1412 | `KX_GameObject`, `ActivityCullingInfo`, `DebugProfilingData`, `RayCastData` |
| KX_GameObject_PyMethods.cpp **grande** | 1853 | `KX_GameObject`, `RayCastData` |
| KX_GameObject_Python.cpp **grande** | 2816 | `KX_GameObject` |
| KX_Globals.cpp | 94 |  |
| KX_Globals.h | 50 |  |
| KX_ImpostorAtlasDeformer.cpp | 90 | `KX_ImpostorAtlasDeformer` |
| KX_ImpostorAtlasDeformer.h | 60 | `KX_ImpostorAtlasDeformer` |
| KX_InputSystem.cpp | 454 | `KX_InputSystem` |
| KX_InputSystem.h | 73 | `KX_InputSystem` |
| KX_InputTable.cpp | 766 | `KX_InputTable` |
| KX_InputTable.h | 181 | `KX_InputTable`, `Binding`, `Processor`, `InputMap` |
| KX_IpoController.cpp | 252 | `KX_IpoController` |
| KX_IpoController.h | 96 | `KX_IpoController` |
| KX_IpoTransform.h | 81 | `KX_IpoTransform` |
| KX_KetsjiEngine.cpp **grande** | 1606 | `KX_KetsjiEngine` |
| KX_KetsjiEngine.h | 841 | `KX_ExitInfo`, `KX_KetsjiEngine`, `CustomMouseCursor` |
| KX_LibLoadStatus.cpp | 233 | `KX_LibLoadStatus` |
| KX_LibLoadStatus.h | 90 | `KX_LibLoadStatus` |
| KX_LightIpoSGController.cpp | 59 | `KX_LightIpoSGController` |
| KX_LightIpoSGController.h | 78 | `KX_LightIpoSGController` |
| KX_LightObject.cpp | 685 | `KX_LightObject` |
| KX_LightObject.h | 161 | `KX_LightObject` |
| KX_LightProbe.cpp | 131 | `KX_LightProbe` |
| KX_LightProbe.h | 63 | `KX_LightProbe` |
| KX_LightningActuator.cpp | 94 | `KX_LightningActuator` |
| KX_LightningActuator.h | 52 | `KX_LightningActuator` |
| KX_LodLevel.cpp | 149 | `KX_LodLevel` |
| KX_LodLevel.h | 87 | `KX_LodLevel` |
| KX_LodManager.cpp | 295 | `KX_LodManager`, `LodLevelIterator` |
| KX_LodManager.h | 140 | `KX_LodManager`, `LodLevelIterator` |
| KX_MaterialIpoController.cpp | 39 | `KX_MaterialIpoController` |
| KX_MaterialIpoController.h | 44 | `KX_MaterialIpoController` |
| KX_Mesh.cpp | 716 | `KX_Mesh` |
| KX_Mesh.h | 131 | `KX_Mesh`, `BitmapGlyph`, `BitmapTextFace` |
| KX_MeshBuilder.cpp | 679 | `KX_MeshBuilderSlot`, `KX_MeshBuilder` |
| KX_MeshBuilder.h | 139 | `KX_MeshBuilderSlot`, `KX_MeshBuilder` |
| KX_MotionState.cpp | 108 | `KX_MotionState` |
| KX_MotionState.h | 58 | `KX_MotionState` |
| KX_MouseActuator.cpp | 411 | `KX_MouseActuator` |
| KX_MouseActuator.h | 117 | `KX_MouseActuator` |
| KX_MouseFocusSensor.cpp | 509 | `KX_MouseFocusSensor` |
| KX_MouseFocusSensor.h | 210 | `KX_MouseFocusSensor` |
| KX_MovementSensor.cpp | 225 | `KX_MovementSensor` |
| KX_MovementSensor.h | 89 | `KX_MovementSensor` |
| KX_NavMeshObject.cpp | 1180 | `KX_NavMeshObject` |
| KX_NavMeshObject.h | 132 | `KX_NavMeshObject`, `NavObstacle` |
| KX_NearSensor.cpp | 345 | `KX_NearSensor` |
| KX_NearSensor.h | 122 | `KX_NearSensor` |
| KX_NetworkManager.cpp **grande** | 2661 | `KX_NetworkManager` |
| KX_NetworkManager.h | 496 | `KX_NetworkManager`, `HostOptions`, `Event`, `PlayerInfo`, `ReplicateOptions`, `Quantization` |
| KX_NodeRelationships.cpp | 223 | `KX_SlowParentRelation`, `KX_VertexParentRelation`, `KX_NormalParentRelation` |
| KX_NodeRelationships.h | 107 | `KX_NormalParentRelation`, `KX_VertexParentRelation`, `KX_SlowParentRelation` |
| KX_ObColorIpoSGController.cpp | 47 | `KX_ObColorIpoSGController` |
| KX_ObColorIpoSGController.h | 51 | `KX_ObColorIpoSGController` |
| KX_ObjectActuator.cpp | 874 | `KX_ObjectActuator` |
| KX_ObjectActuator.h | 178 | `KX_LocalFlags`, `KX_ObjectActuator` |
| KX_ObstacleSimulation.cpp | 824 | `KX_ObstacleSimulation`, `KX_ObstacleSimulationTOI`, `KX_ObstacleSimulationTOI_rays`, `KX_ObstacleSimulationTOI_cells` |
| KX_ObstacleSimulation.h | 132 | `KX_Obstacle`, `KX_ObstacleSimulation`, `KX_ObstacleSimulationTOI`, `KX_ObstacleSimulationTOI_rays`, `KX_ObstacleSimulationTOI_cells` |
| KX_ParentActuator.cpp | 219 | `KX_ParentActuator` |
| KX_ParentActuator.h | 91 | `KX_ParentActuator` |
| KX_ParticleDebugUI.cpp | 387 |  |
| KX_ParticleDebugUI.h | 57 |  |
| KX_ParticleSystem.cpp | 657 | `KX_ParticleSystem` |
| KX_ParticleSystem.h | 131 | `KX_ParticleSystem` |
| KX_PhysicsEngineEnums.h | 42 |  |
| KX_PlanarMap.cpp | 299 | `KX_PlanarMap` |
| KX_PlanarMap.h | 80 | `KX_PlanarMap` |
| KX_PlanarReflector.cpp | 121 | `KX_PlanarReflector` |
| KX_PlanarReflector.h | 66 | `KX_PlanarReflector` |
| KX_PolyProxy.cpp | 268 | `KX_PolyProxy` |
| KX_PolyProxy.h | 88 | `KX_PolyProxy` |
| KX_PyConstraintBinding.cpp | 987 |  |
| KX_PyConstraintBinding.h | 49 |  |
| KX_PyMath.cpp | 116 |  |
| KX_PyMath.h | 318 |  |
| KX_PyNetwork.cpp **grande** | 1621 |  |
| KX_PyNetwork.h | 35 |  |
| KX_PythonComponent.cpp | 321 | `KX_PythonComponent` |
| KX_PythonComponent.h | 79 | `KX_PythonComponent` |
| KX_PythonComponentManager.cpp | 59 | `KX_PythonComponentManager` |
| KX_PythonComponentManager.h | 25 | `KX_PythonComponentManager` |
| KX_PythonInit.cpp **grande** | 3862 |  |
| KX_PythonInit.h | 87 | `PyNextFrameState` |
| KX_PythonInitTypes.cpp | 354 |  |
| KX_PythonInitTypes.h | 40 |  |
| KX_PythonJoystick.cpp | 315 | `KX_PythonJoystick` |
| KX_PythonJoystick.h | 116 | `KX_PythonJoystick` |
| KX_PythonKeyboard.cpp | 229 | `KX_PythonKeyboard` |
| KX_PythonKeyboard.h | 51 | `KX_PythonKeyboard` |
| KX_PythonMain.cpp | 60 |  |
| KX_PythonMain.h | 43 |  |
| KX_PythonMotion.cpp | 357 | `KX_PythonMotion` |
| KX_PythonMotion.h | 106 | `KX_PythonMotion` |
| KX_PythonMouse.cpp | 363 | `KX_PythonMouse` |
| KX_PythonMouse.h | 74 | `KX_PythonMouse` |
| KX_RadarSensor.cpp | 225 | `KX_RadarSensor` |
| KX_RadarSensor.h | 101 | `KX_RadarSensor` |
| KX_RainAura.cpp | 524 | `KX_RainAura` |
| KX_RainAura.h | 114 | `KX_RainAura`, `Edge`, `Silhouette`, `Stroke` |
| KX_RainLightning.cpp | 611 | `KX_RainLightning`, `Manual` |
| KX_RainLightning.h | 130 | `KX_RainLightning`, `StrikeState`, `Manual`, `Emitter` |
| KX_RainShelterMap.cpp | 438 | `KX_RainShelterMap` |
| KX_RainShelterMap.h | 101 | `KX_RainShelterMap`, `Draw`, `MeshBuffer` |
| KX_RainSurfaceMask.cpp | 445 | `KX_RainSurfaceMask` |
| KX_RainSurfaceMask.h | 138 | `KX_RainSurfaceMask`, `Target`, `Draw`, `MeshBuffer` |
| KX_RayCast.cpp | 122 | `KX_RayCast` |
| KX_RayCast.h | 139 | `KX_RayCast` |
| KX_RaySensor.cpp | 580 | `KX_RaySensor` |
| KX_RaySensor.h | 135 | `KX_RaySensor` |
| KX_RenderPipeline.cpp | 1216 | `KX_RenderPipeline` |
| KX_RenderPipeline.h | 163 | `KX_CameraRenderData`, `KX_SceneRenderData`, `KX_FrameRenderData`, `KX_RenderData`, `KX_RenderPipeline` |
| KX_RenderProfileSample.h | 24 | `RenderSample` |
| KX_ReplaceMeshActuator.cpp | 181 | `KX_ReplaceMeshActuator` |
| KX_ReplaceMeshActuator.h | 89 | `KX_ReplaceMeshActuator` |
| KX_RuntimePropertyRegistry.cpp | 92 | `KX_RuntimePropertyRegistry` |
| KX_RuntimePropertyRegistry.h | 57 | `KX_RuntimePropertyDescriptor`, `KX_RuntimePropertyValue`, `KX_RuntimePropertyRegistry` |
| KX_Scene.cpp **grande** | 4599 | `KX_Scene` |
| KX_Scene.h | 860 | `KX_NavMeshObstacle`, `KX_Scene`, `AnimationPoolData`, `CullingInfo`, `ShadowCullEntry`, `CutscenePathPlayback` |
| KX_SceneActuator.cpp | 274 | `KX_SceneActuator` |
| KX_SceneActuator.h | 111 | `KX_SceneActuator` |
| KX_SceneCutscene.cpp | 901 | `KX_Scene` |
| KX_SceneScheduler.cpp | 471 | `KX_SceneScheduler` |
| KX_SceneScheduler.h | 136 | `KX_SceneScheduler`, `PendingScene` |
| KX_ShadowRenderer.cpp | 886 | `KX_ShadowRenderer` |
| KX_ShadowRenderer.h | 104 | `KX_ShadowRenderer`, `CasterLightBounds` |
| KX_SimulationPipeline.cpp | 182 | `KX_SimulationPipeline` |
| KX_SimulationPipeline.h | 63 | `KX_SimulationPipeline` |
| KX_SoftBodyDeformer.cpp | 167 | `KX_SoftBodyDeformer` |
| KX_SoftBodyDeformer.h | 76 | `KX_SoftBodyDeformer` |
| KX_SoundActuator.cpp | 688 | `KX_SoundActuator` |
| KX_SoundActuator.h | 133 | `KX_SoundActuator` |
| KX_Speaker.cpp | 1408 | `KX_Speaker` |
| KX_Speaker.h | 236 | `KX_Speaker` |
| KX_StateActuator.cpp | 171 | `KX_StateActuator` |
| KX_StateActuator.h | 97 | `KX_StateActuator` |
| KX_SteeringActuator.cpp | 656 | `KX_SteeringActuator` |
| KX_SteeringActuator.h | 113 | `KX_SteeringActuator` |
| KX_TextMaterial.cpp | 115 | `KX_TextMaterial` |
| KX_TextMaterial.h | 62 | `KX_TextMaterial` |
| KX_TextureRenderer.cpp | 231 | `KX_TextureRenderer` |
| KX_TextureRenderer.h | 130 | `KX_TextureRenderer` |
| KX_TextureRendererManager.cpp | 440 | `KX_TextureRendererManager` |
| KX_TextureRendererManager.h | 143 | `KX_TextureRendererManager`, `ProbeSlot` |
| KX_TimeCategoryLogger.cpp | 117 | `KX_TimeCategoryLogger` |
| KX_TimeCategoryLogger.h | 129 | `KX_TimeCategoryLogger` |
| KX_TimeLogger.cpp | 113 | `KX_TimeLogger` |
| KX_TimeLogger.h | 109 | `KX_TimeLogger` |
| KX_TrackToActuator.cpp | 478 | `KX_TrackToActuator` |
| KX_TrackToActuator.h | 108 | `KX_TrackToActuator` |
| KX_VFogGlow.cpp | 46 |  |
| KX_VFogGlow.h | 28 | `KX_VFogGlow` |
| KX_VRHeadSensor.cpp | 231 | `KX_VRHeadSensor` |
| KX_VRHeadSensor.h | 76 | `KX_VRHeadSensor` |
| KX_VehicleDebugUI.cpp | 652 | `KX_VehicleDebugUI` |
| KX_VehicleDebugUI.h | 112 | `KX_VehicleDebugUI`, `TelemetrySample`, `PendingEdit` |
| KX_VehiclePreset.cpp | 612 |  |
| KX_VehiclePreset.h | 146 | `KX_VehiclePresetWheel`, `KX_VehiclePreset` |
| KX_VehicleWrapper.cpp | 817 | `KX_VehicleWrapper` |
| KX_VehicleWrapper.h | 82 | `KX_VehicleWrapper` |
| KX_VertexProxy.cpp | 621 | `KX_VertexProxy` |
| KX_VertexProxy.h | 118 | `KX_VertexProxy` |
| KX_VideoActuator.cpp | 355 | `KX_VideoActuator` |
| KX_VideoActuator.h | 84 | `KX_VideoActuator` |
| KX_VisibilityActuator.cpp | 120 | `KX_VisibilityActuator` |
| KX_VisibilityActuator.h | 75 | `KX_VisibilityActuator` |
| KX_WorldInfo.cpp | 1489 | `KX_WorldInfo` |
| KX_WorldInfo.h | 183 | `KX_WorldInfo`, `SkySettings` |
| KX_WorldIpoController.cpp | 87 | `KX_WorldIpoController` |
| KX_WorldIpoController.h | 93 | `KX_WorldIpoController` |

## source/source/gameengine/Ketsji/KXImgui

| arquivo | linhas | classes |
|---|---:|---|
| KX_Imgui.cpp | 549 | `KX_Imgui` |
| KX_Imgui.h | 95 | `KX_Imgui` |
| KX_Imgui_Impl_Inputs.cpp | 582 |  |
| KX_Imgui_Impl_Inputs.h | 26 |  |
| KX_PythonImgui.cpp | 795 |  |
| KX_PythonImgui.h | 40 |  |

## source/source/gameengine/Ketsji/KXNetwork

| arquivo | linhas | classes |
|---|---:|---|
| KX_NetworkMessageActuator.cpp | 135 | `KX_NetworkMessageActuator` |
| KX_NetworkMessageActuator.h | 67 | `KX_NetworkMessageActuator` |
| KX_NetworkMessageManager.cpp | 84 | `KX_NetworkMessageManager` |
| KX_NetworkMessageManager.h | 89 | `KX_NetworkMessageManager`, `Message` |
| KX_NetworkMessageScene.cpp | 59 | `KX_NetworkMessageScene` |
| KX_NetworkMessageScene.h | 73 | `KX_NetworkMessageScene` |
| KX_NetworkMessageSensor.cpp | 227 | `KX_NetworkMessageSensor` |
| KX_NetworkMessageSensor.h | 91 | `KX_NetworkMessageSensor` |
