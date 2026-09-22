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
| SG_Frustum.cpp | 267 | `SG_Frustum` |
| SG_Frustum.h | 39 | `SG_Frustum` |
| SG_Interpolator.cpp | 44 | `SG_Interpolator` |
| SG_Interpolator.h | 57 | `SG_Interpolator` |
| SG_Node.cpp | 576 | `SG_Node` |
| SG_Node.h | 362 | `SG_Callbacks`, `SG_Node` |
| SG_ParentRelation.h | 116 | `SG_ParentRelation` |
| SG_QList.h | 167 | `SG_QList`, `iterator` |
| SG_ScalarInterpolator.h | 45 | `SG_ScalarInterpolator` |

## source/source/gameengine/Converter

| arquivo | linhas | classes |
|---|---:|---|
| BL_ActionActuator.cpp | 421 | `BL_ActionActuator` |
| BL_ActionActuator.h | 126 | `BL_ActionActuator` |
| BL_ActionData.cpp | 38 | `BL_ActionData` |
| BL_ActionData.h | 31 | `BL_ActionData` |
| BL_ArmatureActuator.cpp | 300 | `BL_ArmatureActuator` |
| BL_ArmatureActuator.h | 96 | `BL_ArmatureActuator` |
| BL_ArmatureChannel.cpp | 489 | `BL_ArmatureChannel`, `BL_ArmatureBone` |
| BL_ArmatureChannel.h | 97 | `BL_ArmatureChannel`, `BL_ArmatureBone` |
| BL_ArmatureConstraint.cpp | 537 | `BL_ArmatureConstraint` |
| BL_ArmatureConstraint.h | 114 | `BL_ArmatureConstraint` |
| BL_ArmatureObject.cpp | 623 | `BL_ArmatureObject` |
| BL_ArmatureObject.h | 133 | `BL_ArmatureObject` |
| BL_BlenderDataConversion.cpp **grande** | 2436 |  |
| BL_BlenderDataConversion.h | 81 | `BL_MeshMaterial` |
| BL_ConvertActuators.cpp | 1367 |  |
| BL_ConvertActuators.h | 45 |  |
| BL_ConvertControllers.cpp | 242 |  |
| BL_ConvertControllers.h | 47 |  |
| BL_ConvertObjectInfo.cpp | 6 |  |
| BL_ConvertObjectInfo.h | 22 | `BL_ConvertObjectInfo` |
| BL_ConvertProperties.cpp | 293 |  |
| BL_ConvertProperties.h | 44 |  |
| BL_ConvertSensors.cpp | 767 |  |
| BL_ConvertSensors.h | 45 |  |
| BL_Converter.cpp | 936 | `BL_Converter`, `SceneSlot` |
| BL_Converter.h | 227 | `BL_Converter`, `SceneSlot`, `ThreadInfo` |
| BL_IpoConvert.cpp | 436 |  |
| BL_IpoConvert.h | 68 |  |
| BL_MeshDeformer.cpp | 170 | `BL_MeshDeformer` |
| BL_MeshDeformer.h | 89 | `BL_MeshDeformer` |
| BL_ModifierDeformer.cpp | 199 | `BL_ModifierDeformer` |
| BL_ModifierDeformer.h | 82 | `BL_ModifierDeformer` |
| BL_Resource.cpp | 35 | `Library`, `BL_Resource` |
| BL_Resource.h | 47 | `BL_Resource`, `Library` |
| BL_ScalarInterpolator.cpp | 52 | `BL_ScalarInterpolator` |
| BL_ScalarInterpolator.h | 56 | `BL_ScalarInterpolator` |
| BL_SceneConverter.cpp | 177 | `BL_SceneConverter` |
| BL_SceneConverter.h | 119 | `BL_SceneConverter` |
| BL_ShapeDeformer.cpp | 210 | `BL_ShapeDeformer` |
| BL_ShapeDeformer.h | 77 | `BL_ShapeDeformer` |
| BL_SkinDeformer.cpp | 417 | `BL_SkinDeformer` |
| BL_SkinDeformer.h | 107 | `BL_SkinDeformer` |

## source/source/gameengine/Ketsji

| arquivo | linhas | classes |
|---|---:|---|
| BL_Action.cpp | 545 | `BL_Action` |
| BL_Action.h | 161 | `BL_Action` |
| BL_ActionManager.cpp | 191 | `BL_ActionManager` |
| BL_ActionManager.h | 137 | `BL_ActionManager` |
| BL_BlenderShader.cpp | 272 | `BL_BlenderShader` |
| BL_BlenderShader.h | 102 | `BL_BlenderShader` |
| BL_Shader.cpp | 962 | `BL_Shader` |
| BL_Shader.h | 107 | `BL_Shader` |
| BL_Texture.cpp | 758 | `BL_Texture` |
| BL_Texture.h | 137 | `BL_Texture` |
| KX_2DFilter.cpp | 275 | `KX_2DFilter` |
| KX_2DFilter.h | 70 | `KX_2DFilter` |
| KX_2DFilterManager.cpp | 766 | `KX_2DFilterManager` |
| KX_2DFilterManager.h | 85 | `KX_2DFilterManager` |
| KX_2DFilterOffScreen.cpp | 116 | `KX_2DFilterOffScreen` |
| KX_2DFilterOffScreen.h | 56 | `KX_2DFilterOffScreen` |
| KX_AddObjectActuator.cpp | 319 | `KX_AddObjectActuator` |
| KX_AddObjectActuator.h | 131 | `KX_AddObjectActuator` |
| KX_AnimationEvent.cpp | 193 | `KX_AnimationEvent` |
| KX_AnimationEvent.h | 82 | `KX_AnimationEvent` |
| KX_AnimationEventManager.cpp | 202 | `KX_AnimationEventManager` |
| KX_AnimationEventManager.h | 79 | `KX_AnimationEventManager` |
| KX_ArmatureSensor.cpp | 220 | `KX_ArmatureSensor` |
| KX_ArmatureSensor.h | 90 | `KX_ArmatureSensor` |
| KX_BatchGroup.cpp | 327 | `KX_BatchGroup` |
| KX_BatchGroup.h | 81 | `KX_BatchGroup` |
| KX_BlenderMaterial.cpp | 1024 | `KX_BlenderMaterial` |
| KX_BlenderMaterial.h | 141 | `KX_BlenderMaterial` |
| KX_BoneParentNodeRelationship.cpp | 105 | `KX_BoneParentRelation` |
| KX_BoneParentNodeRelationship.h | 65 | `KX_BoneParentRelation` |
| KX_BoundingBox.cpp | 410 | `KX_BoundingBox` |
| KX_BoundingBox.h | 90 | `KX_BoundingBox` |
| KX_Camera.cpp | 1091 | `KX_Camera`, `View` |
| KX_Camera.h | 284 | `KX_Camera`, `View` |
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
| KX_CollisionEventManager.cpp | 264 | `KX_CollisionEventManager`, `NewCollision` |
| KX_CollisionEventManager.h | 96 | `KX_CollisionEventManager`, `NewCollision` |
| KX_CollisionSensor.cpp | 340 | `KX_CollisionSensor` |
| KX_CollisionSensor.h | 145 | `KX_CollisionSensor` |
| KX_ConsoleWindow.cpp | 91 | `KX_ConsoleWindow` |
| KX_ConsoleWindow.h | 46 | `KX_ConsoleWindow` |
| KX_ConstraintActuator.cpp | 633 | `KX_ConstraintActuator` |
| KX_ConstraintActuator.h | 142 | `KX_ConstraintActuator` |
| KX_ConstraintWrapper.cpp | 175 | `KX_ConstraintWrapper` |
| KX_ConstraintWrapper.h | 65 | `KX_ConstraintWrapper` |
| KX_CubeMap.cpp | 155 | `KX_CubeMap` |
| KX_CubeMap.h | 63 | `KX_CubeMap` |
| KX_CullingHandler.cpp | 111 | `KX_CullingHandler` |
| KX_CullingHandler.h | 44 | `KX_CullingHandler` |
| KX_CutsceneManager.cpp | 164 | `KX_CutsceneManager` |
| KX_CutsceneManager.h | 121 | `KX_CutsceneManager`, `Event`, `Sequence`, `SpawnedObjects` |
| KX_DebugMode.cpp | 1138 | `KX_DebugMode` |
| KX_DebugMode.h | 236 | `ScrollingBuffer`, `KX_DebugMode` |
| KX_DebugRenderer.cpp | 125 | `KX_DebugRenderer` |
| KX_DebugRenderer.h | 61 | `KX_DebugRenderer` |
| KX_DynamicActuator.cpp | 184 | `KX_DynamicActuator` |
| KX_DynamicActuator.h | 78 | `KX_DynamicActuator` |
| KX_EmptyObject.cpp | 37 |  |
| KX_EmptyObject.h | 45 | `KX_EmptyObject` |
| KX_EndObjectActuator.cpp | 133 | `KX_EndObjectActuator` |
| KX_EndObjectActuator.h | 72 | `KX_EndObjectActuator` |
| KX_FontObject.cpp | 503 | `KX_FontObject` |
| KX_FontObject.h | 133 | `KX_FontObject` |
| KX_GameActuator.cpp | 220 | `KX_GameActuator` |
| KX_GameActuator.h | 95 | `KX_GameActuator` |
| KX_GameObject.cpp **grande** | 5979 | `KX_GameObject`, `ActivityCullingInfo`, `RayCastData` |
| KX_GameObject.h | 1304 | `KX_GameObject`, `ActivityCullingInfo`, `DebugProfilingData`, `RayCastData` |
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
| KX_KetsjiEngine.cpp | 1279 | `KX_KetsjiEngine` |
| KX_KetsjiEngine.h | 794 | `KX_ExitInfo`, `KX_KetsjiEngine`, `CustomMouseCursor` |
| KX_LibLoadStatus.cpp | 231 | `KX_LibLoadStatus` |
| KX_LibLoadStatus.h | 90 | `KX_LibLoadStatus` |
| KX_LightIpoSGController.cpp | 59 | `KX_LightIpoSGController` |
| KX_LightIpoSGController.h | 78 | `KX_LightIpoSGController` |
| KX_LightObject.cpp | 587 | `KX_LightObject` |
| KX_LightObject.h | 145 | `KX_LightObject` |
| KX_LodLevel.cpp | 149 | `KX_LodLevel` |
| KX_LodLevel.h | 87 | `KX_LodLevel` |
| KX_LodManager.cpp | 290 | `KX_LodManager`, `LodLevelIterator` |
| KX_LodManager.h | 125 | `KX_LodManager`, `LodLevelIterator` |
| KX_MaterialIpoController.cpp | 39 | `KX_MaterialIpoController` |
| KX_MaterialIpoController.h | 44 | `KX_MaterialIpoController` |
| KX_Mesh.cpp | 610 | `KX_Mesh` |
| KX_Mesh.h | 97 | `KX_Mesh` |
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
| KX_NavMeshObject.cpp | 752 | `KX_NavMeshObject` |
| KX_NavMeshObject.h | 89 | `KX_NavMeshObject` |
| KX_NearSensor.cpp | 316 | `KX_NearSensor` |
| KX_NearSensor.h | 114 | `KX_NearSensor` |
| KX_NodeRelationships.cpp | 207 | `KX_SlowParentRelation`, `KX_VertexParentRelation`, `KX_NormalParentRelation` |
| KX_NodeRelationships.h | 107 | `KX_NormalParentRelation`, `KX_VertexParentRelation`, `KX_SlowParentRelation` |
| KX_ObColorIpoSGController.cpp | 47 | `KX_ObColorIpoSGController` |
| KX_ObColorIpoSGController.h | 51 | `KX_ObColorIpoSGController` |
| KX_ObjectActuator.cpp | 758 | `KX_ObjectActuator` |
| KX_ObjectActuator.h | 165 | `KX_LocalFlags`, `KX_ObjectActuator` |
| KX_ObstacleSimulation.cpp | 824 | `KX_ObstacleSimulation`, `KX_ObstacleSimulationTOI`, `KX_ObstacleSimulationTOI_rays`, `KX_ObstacleSimulationTOI_cells` |
| KX_ObstacleSimulation.h | 132 | `KX_Obstacle`, `KX_ObstacleSimulation`, `KX_ObstacleSimulationTOI`, `KX_ObstacleSimulationTOI_rays`, `KX_ObstacleSimulationTOI_cells` |
| KX_ParentActuator.cpp | 219 | `KX_ParentActuator` |
| KX_ParentActuator.h | 91 | `KX_ParentActuator` |
| KX_ParticleDebugUI.cpp | 383 |  |
| KX_ParticleDebugUI.h | 57 |  |
| KX_ParticleSystem.cpp | 471 | `KX_ParticleSystem` |
| KX_ParticleSystem.h | 115 | `KX_ParticleSystem` |
| KX_PhysicsEngineEnums.h | 42 |  |
| KX_PlanarMap.cpp | 278 | `KX_PlanarMap` |
| KX_PlanarMap.h | 78 | `KX_PlanarMap` |
| KX_PolyProxy.cpp | 268 | `KX_PolyProxy` |
| KX_PolyProxy.h | 88 | `KX_PolyProxy` |
| KX_PyConstraintBinding.cpp | 987 |  |
| KX_PyConstraintBinding.h | 49 |  |
| KX_PyMath.cpp | 116 |  |
| KX_PyMath.h | 318 |  |
| KX_PythonComponent.cpp | 244 | `KX_PythonComponent` |
| KX_PythonComponent.h | 74 | `KX_PythonComponent` |
| KX_PythonComponentManager.cpp | 59 | `KX_PythonComponentManager` |
| KX_PythonComponentManager.h | 25 | `KX_PythonComponentManager` |
| KX_PythonInit.cpp **grande** | 3284 |  |
| KX_PythonInit.h | 87 | `PyNextFrameState` |
| KX_PythonInitTypes.cpp | 344 |  |
| KX_PythonInitTypes.h | 40 |  |
| KX_PythonJoystick.cpp | 315 | `KX_PythonJoystick` |
| KX_PythonJoystick.h | 116 | `KX_PythonJoystick` |
| KX_PythonKeyboard.cpp | 229 | `KX_PythonKeyboard` |
| KX_PythonKeyboard.h | 51 | `KX_PythonKeyboard` |
| KX_PythonMain.cpp | 60 |  |
| KX_PythonMain.h | 43 |  |
| KX_PythonMouse.cpp | 363 | `KX_PythonMouse` |
| KX_PythonMouse.h | 74 | `KX_PythonMouse` |
| KX_RadarSensor.cpp | 230 | `KX_RadarSensor` |
| KX_RadarSensor.h | 101 | `KX_RadarSensor` |
| KX_RayCast.cpp | 122 | `KX_RayCast` |
| KX_RayCast.h | 139 | `KX_RayCast` |
| KX_RaySensor.cpp | 362 | `KX_RaySensor` |
| KX_RaySensor.h | 112 | `KX_RaySensor` |
| KX_RenderPipeline.cpp | 654 | `KX_RenderPipeline` |
| KX_RenderPipeline.h | 163 | `KX_CameraRenderData`, `KX_SceneRenderData`, `KX_FrameRenderData`, `KX_RenderData`, `KX_RenderPipeline` |
| KX_ReplaceMeshActuator.cpp | 181 | `KX_ReplaceMeshActuator` |
| KX_ReplaceMeshActuator.h | 89 | `KX_ReplaceMeshActuator` |
| KX_RuntimePropertyRegistry.cpp | 92 | `KX_RuntimePropertyRegistry` |
| KX_RuntimePropertyRegistry.h | 57 | `KX_RuntimePropertyDescriptor`, `KX_RuntimePropertyValue`, `KX_RuntimePropertyRegistry` |
| KX_Scene.cpp **grande** | 3767 | `KX_Scene` |
| KX_Scene.h | 678 | `KX_Scene`, `AnimationPoolData`, `CullingInfo` |
| KX_SceneActuator.cpp | 274 | `KX_SceneActuator` |
| KX_SceneActuator.h | 104 | `KX_SceneActuator` |
| KX_SceneScheduler.cpp | 261 | `KX_SceneScheduler` |
| KX_SceneScheduler.h | 88 | `KX_SceneScheduler` |
| KX_ShadowRenderer.cpp | 634 | `KX_ShadowRenderer` |
| KX_ShadowRenderer.h | 85 | `KX_ShadowRenderer` |
| KX_SimulationPipeline.cpp | 147 | `KX_SimulationPipeline` |
| KX_SimulationPipeline.h | 63 | `KX_SimulationPipeline` |
| KX_SoftBodyDeformer.cpp | 136 | `KX_SoftBodyDeformer` |
| KX_SoftBodyDeformer.h | 76 | `KX_SoftBodyDeformer` |
| KX_SoundActuator.cpp | 664 | `KX_SoundActuator` |
| KX_SoundActuator.h | 131 | `KX_SoundActuator` |
| KX_Speaker.cpp | 1240 | `KX_Speaker` |
| KX_Speaker.h | 217 | `KX_Speaker` |
| KX_StateActuator.cpp | 171 | `KX_StateActuator` |
| KX_StateActuator.h | 97 | `KX_StateActuator` |
| KX_SteeringActuator.cpp | 650 | `KX_SteeringActuator` |
| KX_SteeringActuator.h | 111 | `KX_SteeringActuator` |
| KX_TextMaterial.cpp | 115 | `KX_TextMaterial` |
| KX_TextMaterial.h | 62 | `KX_TextMaterial` |
| KX_TextureRenderer.cpp | 231 | `KX_TextureRenderer` |
| KX_TextureRenderer.h | 115 | `KX_TextureRenderer` |
| KX_TextureRendererManager.cpp | 254 | `KX_TextureRendererManager` |
| KX_TextureRendererManager.h | 96 | `KX_TextureRendererManager` |
| KX_TimeCategoryLogger.cpp | 112 | `KX_TimeCategoryLogger` |
| KX_TimeCategoryLogger.h | 126 | `KX_TimeCategoryLogger` |
| KX_TimeLogger.cpp | 108 | `KX_TimeLogger` |
| KX_TimeLogger.h | 106 | `KX_TimeLogger` |
| KX_TrackToActuator.cpp | 478 | `KX_TrackToActuator` |
| KX_TrackToActuator.h | 108 | `KX_TrackToActuator` |
| KX_VehicleDebugUI.cpp | 556 | `KX_VehicleDebugUI` |
| KX_VehicleDebugUI.h | 111 | `KX_VehicleDebugUI`, `TelemetrySample`, `PendingEdit` |
| KX_VehiclePreset.cpp | 537 |  |
| KX_VehiclePreset.h | 130 | `KX_VehiclePresetWheel`, `KX_VehiclePreset` |
| KX_VehicleWrapper.cpp | 770 | `KX_VehicleWrapper` |
| KX_VehicleWrapper.h | 77 | `KX_VehicleWrapper` |
| KX_VertexProxy.cpp | 614 | `KX_VertexProxy` |
| KX_VertexProxy.h | 117 | `KX_VertexProxy` |
| KX_VisibilityActuator.cpp | 120 | `KX_VisibilityActuator` |
| KX_VisibilityActuator.h | 75 | `KX_VisibilityActuator` |
| KX_WorldInfo.cpp | 905 | `KX_WorldInfo` |
| KX_WorldInfo.h | 136 | `KX_WorldInfo` |
| KX_WorldIpoController.cpp | 87 | `KX_WorldIpoController` |
| KX_WorldIpoController.h | 93 | `KX_WorldIpoController` |

## source/source/gameengine/Ketsji/KXImgui

| arquivo | linhas | classes |
|---|---:|---|
| KX_Imgui.cpp | 457 | `KX_Imgui` |
| KX_Imgui.h | 88 | `KX_Imgui` |
| KX_Imgui_Impl_Inputs.cpp | 542 |  |
| KX_Imgui_Impl_Inputs.h | 21 |  |
| KX_PythonImgui.cpp | 677 |  |
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
| KX_NetworkMessageSensor.cpp | 218 | `KX_NetworkMessageSensor` |
| KX_NetworkMessageSensor.h | 91 | `KX_NetworkMessageSensor` |
