# Indice de codigo: rendering

> Gerado por `tools/build_code_index.py` (regex sobre o codigo, sem LLM). Colunas: linhas | classes declaradas (.h) ou implementadas (.cpp).
> Arquivos com mais de 1500 linhas estao marcados com **grande**: nao leia inteiros; veja `docs/code-map-*.md` quando existir.

## source/source/gameengine/Rasterizer

| arquivo | linhas | classes |
|---|---:|---|
| RAS_2DFilter.cpp | 584 | `RAS_2DFilter` |
| RAS_2DFilter.h | 140 | `RAS_2DFilter` |
| RAS_2DFilterData.cpp | 35 |  |
| RAS_2DFilterData.h | 129 | `RAS_2DFilterData` |
| RAS_2DFilterManager.cpp | 378 | `RAS_2DFilterManager` |
| RAS_2DFilterManager.h | 141 | `RAS_2DFilterManager` |
| RAS_2DFilterOffScreen.cpp | 215 | `RAS_2DFilterOffScreen` |
| RAS_2DFilterOffScreen.h | 107 | `RAS_2DFilterOffScreen` |
| RAS_AttributeArray.cpp | 73 | `RAS_AttributeArray` |
| RAS_AttributeArray.h | 82 | `RAS_AttributeArray`, `Attrib` |
| RAS_AttributeArrayStorage.cpp | 24 | `RAS_AttributeArrayStorage` |
| RAS_AttributeArrayStorage.h | 23 | `RAS_AttributeArrayStorage` |
| RAS_BatchDisplayArray.cpp | 166 | `RAS_BatchDisplayArray` |
| RAS_BatchDisplayArray.h | 80 | `RAS_BatchDisplayArray`, `Part` |
| RAS_BatchGroup.cpp | 219 | `RAS_BatchGroup`, `Batch` |
| RAS_BatchGroup.h | 111 | `RAS_BatchGroup`, `Batch` |
| RAS_BoundingBox.cpp | 191 | `RAS_BoundingBox`, `RAS_MeshBoundingBox` |
| RAS_BoundingBox.h | 114 | `RAS_BoundingBox`, `RAS_MeshBoundingBox`, `DisplayArraySlot` |
| RAS_BoundingBoxManager.cpp | 81 | `RAS_BoundingBoxManager` |
| RAS_BoundingBoxManager.h | 72 | `RAS_BoundingBoxManager` |
| RAS_BucketManager.cpp | 491 | `RAS_BucketManager`, `SortedMeshSlot`, `backtofront`, `fronttoback` |
| RAS_BucketManager.h | 136 | `RAS_BucketManager`, `SortedMeshSlot`, `backtofront`, `fronttoback`, `TextData` |
| RAS_CameraData.h | 76 | `RAS_CameraData` |
| RAS_DebugDraw.cpp | 137 | `RAS_DebugDraw`, `Shape`, `Line`, `Aabb`, `Frustum`, `Text2d` |
| RAS_DebugDraw.h | 145 | `RAS_DebugDraw`, `Shape`, `Line`, `Aabb`, `Frustum`, `Text2d` |
| RAS_Deformer.cpp | 76 | `RAS_Deformer` |
| RAS_Deformer.h | 124 | `RAS_Deformer`, `DisplayArraySlot` |
| RAS_DisplayArray.cpp | 328 | `RAS_DisplayArray` |
| RAS_DisplayArray.h | 350 | `RAS_DisplayArray`, `Format`, `VertexData` |
| RAS_DisplayArrayBucket.cpp | 430 | `RAS_DisplayArrayBucket` |
| RAS_DisplayArrayBucket.h | 120 | `RAS_DisplayArrayBucket` |
| RAS_DisplayArrayLayout.h | 18 | `RAS_DisplayArrayLayout` |
| RAS_DisplayArrayStorage.cpp | 59 | `RAS_DisplayArrayStorage` |
| RAS_DisplayArrayStorage.h | 47 | `RAS_DisplayArrayStorage` |
| RAS_FramingManager.cpp | 409 | `RAS_FramingManager` |
| RAS_FramingManager.h | 264 | `RAS_FrameSettings`, `RAS_FrameFrustum`, `RAS_FramingManager` |
| RAS_ICanvas.cpp | 307 | `RAS_ICanvas` |
| RAS_ICanvas.h | 243 | `RAS_ICanvas`, `Screenshot` |
| RAS_ILightObject.h | 138 | `RAS_ILightObject` |
| RAS_IMaterial.cpp | 170 | `RAS_IMaterial` |
| RAS_IMaterial.h | 164 | `RAS_IMaterial` |
| RAS_ISync.h | 48 | `RAS_ISync` |
| RAS_InstancingBuffer.cpp | 173 | `RAS_InstancingBuffer` |
| RAS_InstancingBuffer.h | 152 | `RAS_InstancingBuffer` |
| RAS_MaterialBucket.cpp | 181 | `RAS_MaterialBucket` |
| RAS_MaterialBucket.h | 86 | `RAS_MaterialBucket` |
| RAS_Mesh.cpp | 305 | `RAS_Mesh` |
| RAS_Mesh.h | 187 | `RAS_Mesh`, `Layer`, `LayersInfo`, `PolygonInfo`, `PolygonRangeInfo` |
| RAS_MeshMaterial.cpp | 87 | `RAS_MeshMaterial` |
| RAS_MeshMaterial.h | 77 | `RAS_MeshMaterial` |
| RAS_MeshSlot.cpp | 129 | `RAS_MeshSlot` |
| RAS_MeshSlot.h | 67 | `RAS_MeshSlot` |
| RAS_MeshUser.cpp | 167 | `RAS_MeshUser` |
| RAS_MeshUser.h | 93 | `RAS_MeshUser` |
| RAS_OffScreen.cpp | 276 | `RAS_OffScreen`, `Slot` |
| RAS_OffScreen.h | 139 | `RAS_OffScreen`, `Attachment` |
| RAS_ParticleBuffer.cpp | 563 | `RAS_ParticleBuffer` |
| RAS_ParticleBuffer.h | 320 | `RAS_ParticleBuffer` |
| RAS_ParticleShaderCache.cpp | 720 | `RAS_ParticleShaderCache` |
| RAS_ParticleShaderCache.h | 142 | `RAS_ParticleShaderCache` |
| RAS_Query.cpp | 77 | `RAS_Query` |
| RAS_Query.h | 76 | `RAS_Query` |
| RAS_Rasterizer.cpp | 1499 | `RAS_Rasterizer` |
| RAS_Rasterizer.h | 706 | `RAS_Rasterizer`, `RayCastTranform`, `OverrideShaderDrawFrameBufferInterface`, `OverrideShaderStereoStippleInterface`, `OverrideShaderStereoAnaglyph`, `OverrideShaderShadowInterface` |
| RAS_Rect.h | 124 | `RAS_Rect` |
| RAS_Shader.cpp | 596 | `RAS_Shader`, `RAS_Uniform`, `UniformInfo` |
| RAS_Shader.h | 218 | `RAS_Shader`, `RAS_Uniform`, `RAS_DefUniform`, `UniformInfo` |
| RAS_TextUser.cpp | 147 | `RAS_TextUser` |
| RAS_TextUser.h | 77 | `RAS_TextUser` |
| RAS_Texture.cpp | 87 | `RAS_Texture` |
| RAS_Texture.h | 90 | `RAS_Texture` |
| RAS_TextureRenderer.cpp | 215 | `RAS_TextureRenderer`, `Face` |
| RAS_TextureRenderer.h | 100 | `RAS_TextureRenderer`, `Face` |
| RAS_TransformFeedbackShader.cpp | 127 | `RAS_TransformFeedbackShader` |
| RAS_TransformFeedbackShader.h | 79 | `RAS_TransformFeedbackShader` |
| RAS_VertexInfo.cpp | 42 |  |
| RAS_VertexInfo.h | 75 | `RAS_VertexInfo` |

## source/source/gameengine/Rasterizer/Node

| arquivo | linhas | classes |
|---|---:|---|
| RAS_BaseNode.h | 92 | `RAS_BaseNode` |
| RAS_DownwardNode.h | 149 | `RAS_DownwardNode` |
| RAS_DummyNode.h | 46 | `RAS_DummyNodeData`, `RAS_DummyNodeTuple`, `RAS_DummyNode` |
| RAS_RenderNode.h | 253 | `RAS_ManagerNodeData`, `RAS_MaterialNodeData`, `RAS_DisplayArrayNodeData`, `RAS_MeshSlotNodeData`, `RAS_MaterialNodeTuple`, `RAS_DisplayArrayNodeTuple` |
| RAS_UpwardNode.h | 92 | `RAS_UpwardNode` |
| RAS_UpwardNodeIterator.h | 135 | `RAS_DummyUpwardNodeIterator`, `RAS_UpwardNodeIterator` |

## source/source/gameengine/Rasterizer/RAS_OpenGLRasterizer

| arquivo | linhas | classes |
|---|---:|---|
| RAS_GLExtensionManager.h | 43 |  |
| RAS_OpenGLDebugDraw.cpp | 434 | `RAS_OpenGLDebugDraw` |
| RAS_OpenGLDebugDraw.h | 95 | `RAS_OpenGLDebugDraw` |
| RAS_OpenGLLight.cpp | 486 | `RAS_OpenGLLight` |
| RAS_OpenGLLight.h | 76 | `RAS_OpenGLLight` |
| RAS_OpenGLQuery.cpp | 118 | `RAS_OpenGLQuery` |
| RAS_OpenGLQuery.h | 56 | `RAS_OpenGLQuery` |
| RAS_OpenGLRasterizer.cpp | 699 | `RAS_OpenGLRasterizer`, `ScreenPlane` |
| RAS_OpenGLRasterizer.h | 146 | `RAS_OpenGLRasterizer`, `ScreenPlane` |
| RAS_OpenGLSync.cpp | 82 | `RAS_OpenGLSync` |
| RAS_OpenGLSync.h | 50 | `RAS_OpenGLSync` |
| RAS_StorageVao.cpp | 194 | `RAS_StorageVao` |
| RAS_StorageVao.h | 47 | `RAS_StorageVao` |
| RAS_StorageVbo.cpp | 153 | `RAS_StorageVbo` |
| RAS_StorageVbo.h | 70 | `RAS_StorageVbo` |

## source/source/blender/gpu

| arquivo | linhas | classes |
|---|---:|---|
| GPU_basic_shader.h | 134 |  |
| GPU_buffers.h | 273 |  |
| GPU_compositing.h | 117 |  |
| GPU_debug.h | 61 |  |
| GPU_draw.h | 156 |  |
| GPU_extensions.h | 87 |  |
| GPU_framebuffer.h | 105 |  |
| GPU_glew.h | 29 |  |
| GPU_init_exit.h | 38 |  |
| GPU_material.h | 467 | `GPUParticleInfo` |
| GPU_select.h | 54 |  |
| GPU_shader.h | 158 |  |
| GPU_texture.h | 125 |  |
| GPU_vertex_array.h | 44 |  |

## source/source/blender/gpu/intern

| arquivo | linhas | classes |
|---|---:|---|
| gpu_basic_shader.c | 777 |  |
| gpu_buffers.c **grande** | 2119 |  |
| gpu_codegen.c **grande** | 1954 |  |
| gpu_codegen.h | 192 | `GPUNode`, `GPUNodeLink`, `GPUPass` |
| gpu_compositing.c **grande** | 2125 |  |
| gpu_debug.c | 807 |  |
| gpu_draw.c **grande** | 2479 |  |
| gpu_extensions.c | 383 |  |
| gpu_framebuffer.c | 1070 |  |
| gpu_init_exit.c | 67 |  |
| gpu_material.c **grande** | 4625 |  |
| gpu_private.h | 32 |  |
| gpu_select.c | 228 |  |
| gpu_select_pick.c | 742 |  |
| gpu_select_private.h | 47 |  |
| gpu_select_sample_query.c | 207 |  |
| gpu_shader.c | 1263 |  |
| gpu_texture.c | 1017 |  |
| gpu_vertex_array.c | 71 |  |
