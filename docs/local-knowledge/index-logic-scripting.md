# Indice de codigo: logic-scripting

> Gerado por `tools/build_code_index.py` (regex sobre o codigo, sem LLM). Colunas: linhas | classes declaradas (.h) ou implementadas (.cpp).
> Arquivos com mais de 1500 linhas estao marcados com **grande**: nao leia inteiros; veja `docs/code-map-*.md` quando existir.

## source/source/gameengine/GameLogic

| arquivo | linhas | classes |
|---|---:|---|
| SCA_2DFilterActuator.cpp | 206 | `SCA_2DFilterActuator` |
| SCA_2DFilterActuator.h | 76 | `SCA_2DFilterActuator` |
| SCA_ANDController.cpp | 124 | `SCA_ANDController` |
| SCA_ANDController.h | 51 | `SCA_ANDController` |
| SCA_ActuatorEventManager.cpp | 64 | `SCA_ActuatorEventManager` |
| SCA_ActuatorEventManager.h | 46 | `SCA_ActuatorEventManager` |
| SCA_ActuatorSensor.cpp | 169 | `SCA_ActuatorSensor` |
| SCA_ActuatorSensor.h | 70 | `SCA_ActuatorSensor` |
| SCA_AlwaysSensor.cpp | 139 | `SCA_AlwaysSensor` |
| SCA_AlwaysSensor.h | 53 | `SCA_AlwaysSensor` |
| SCA_AnimationEventSensor.cpp | 175 | `SCA_AnimationEventSensor` |
| SCA_AnimationEventSensor.h | 76 | `SCA_AnimationEventSensor` |
| SCA_BasicEventManager.cpp | 56 | `SCA_BasicEventManager` |
| SCA_BasicEventManager.h | 49 | `SCA_BasicEventManager` |
| SCA_DelaySensor.cpp | 202 | `SCA_DelaySensor` |
| SCA_DelaySensor.h | 71 | `SCA_DelaySensor` |
| SCA_EventManager.cpp | 87 | `SCA_EventManager` |
| SCA_EventManager.h | 84 | `SCA_EventManager` |
| SCA_ExpressionController.cpp | 154 | `SCA_ExpressionController` |
| SCA_ExpressionController.h | 63 | `SCA_ExpressionController` |
| SCA_IActuator.cpp | 168 | `SCA_IActuator` |
| SCA_IActuator.h | 152 | `SCA_IActuator` |
| SCA_IController.cpp | 283 | `SCA_IController` |
| SCA_IController.h | 90 | `SCA_IController` |
| SCA_IInputDevice.cpp | 191 | `SCA_IInputDevice` |
| SCA_IInputDevice.h | 249 | `SCA_IInputDevice` |
| SCA_ILogicBrick.cpp | 178 | `SCA_ILogicBrick` |
| SCA_ILogicBrick.h | 144 | `SCA_ILogicBrick` |
| SCA_IObject.cpp | 386 | `SCA_IObject` |
| SCA_IObject.h | 181 | `SCA_IObject` |
| SCA_IScene.cpp | 121 | `SCA_IScene` |
| SCA_IScene.h | 69 | `SCA_DebugProp`, `SCA_IScene` |
| SCA_ISensor.cpp | 496 | `SCA_ISensor` |
| SCA_ISensor.h | 207 | `SCA_ISensor` |
| SCA_InputEvent.cpp | 228 | `SCA_InputEvent` |
| SCA_InputEvent.h | 89 | `SCA_InputEvent` |
| SCA_JoystickManager.cpp | 63 | `SCA_JoystickManager` |
| SCA_JoystickManager.h | 49 | `SCA_JoystickManager` |
| SCA_JoystickSensor.cpp | 392 | `SCA_JoystickSensor` |
| SCA_JoystickSensor.h | 200 | `SCA_JoystickSensor` |
| SCA_KeyboardManager.cpp | 71 | `SCA_KeyboardManager` |
| SCA_KeyboardManager.h | 54 | `SCA_KeyboardManager` |
| SCA_KeyboardSensor.cpp | 377 | `SCA_KeyboardSensor` |
| SCA_KeyboardSensor.h | 112 | `SCA_KeyboardSensor` |
| SCA_LogicManager.cpp | 325 | `SCA_LogicManager` |
| SCA_LogicManager.h | 159 | `SCA_LogicManager` |
| SCA_MouseManager.cpp | 95 | `SCA_MouseManager` |
| SCA_MouseManager.h | 55 | `SCA_MouseManager` |
| SCA_MouseSensor.cpp | 247 | `SCA_MouseSensor` |
| SCA_MouseSensor.h | 112 | `SCA_MouseSensor` |
| SCA_NANDController.cpp | 126 | `SCA_NANDController` |
| SCA_NANDController.h | 52 | `SCA_NANDController` |
| SCA_NORController.cpp | 126 | `SCA_NORController` |
| SCA_NORController.h | 48 | `SCA_NORController` |
| SCA_ORController.cpp | 123 | `SCA_ORController` |
| SCA_ORController.h | 49 | `SCA_ORController` |
| SCA_PropertyActuator.cpp | 327 | `SCA_PropertyActuator` |
| SCA_PropertyActuator.h | 92 | `SCA_PropertyActuator` |
| SCA_PropertySensor.cpp | 376 | `SCA_PropertySensor` |
| SCA_PropertySensor.h | 104 | `SCA_PropertySensor` |
| SCA_PythonController.cpp | 508 | `SCA_PythonController` |
| SCA_PythonController.h | 120 | `SCA_PythonController` |
| SCA_RandomActuator.cpp | 569 | `SCA_RandomActuator` |
| SCA_RandomActuator.h | 120 | `SCA_RandomActuator` |
| SCA_RandomNumberGenerator.cpp | 137 | `SCA_RandomNumberGenerator` |
| SCA_RandomNumberGenerator.h | 76 | `SCA_RandomNumberGenerator` |
| SCA_RandomSensor.cpp | 187 | `SCA_RandomSensor` |
| SCA_RandomSensor.h | 71 | `SCA_RandomSensor` |
| SCA_RuntimeProperty.h | 18 | `SCA_RuntimePropertyValue` |
| SCA_TimeEventManager.cpp | 112 | `SCA_TimeEventManager` |
| SCA_TimeEventManager.h | 56 | `SCA_TimeEventManager` |
| SCA_VibrationActuator.cpp | 197 | `SCA_VibrationActuator` |
| SCA_VibrationActuator.h | 72 | `SCA_VibrationActuator` |
| SCA_XNORController.cpp | 129 | `SCA_XNORController` |
| SCA_XNORController.h | 53 | `SCA_XNORController` |
| SCA_XORController.cpp | 128 | `SCA_XORController` |
| SCA_XORController.h | 48 | `SCA_XORController` |

## source/source/gameengine/Expressions

| arquivo | linhas | classes |
|---|---:|---|
| EXP_BaseListValue.h | 85 | `EXP_BaseListValue` |
| EXP_BaseListWrapper.h | 106 | `EXP_BaseListWrapper` |
| EXP_BoolValue.h | 55 | `EXP_BoolValue` |
| EXP_ConstExpr.h | 40 | `EXP_ConstExpr` |
| EXP_EmptyValue.h | 38 | `EXP_EmptyValue` |
| EXP_ErrorValue.h | 42 | `EXP_ErrorValue` |
| EXP_Expression.h | 46 | `EXP_Expression` |
| EXP_FloatValue.h | 50 | `EXP_FloatValue` |
| EXP_IdentifierExpr.h | 51 | `EXP_IdentifierExpr` |
| EXP_IfExpr.h | 40 | `EXP_IfExpr` |
| EXP_InputParser.h | 108 | `EXP_Parser` |
| EXP_IntValue.h | 56 | `EXP_IntValue` |
| EXP_ListValue.h | 190 | `EXP_ListValue`, `const_iterator` |
| EXP_ListWrapper.h | 76 | `EXP_ListWrapper` |
| EXP_Operator1Expr.h | 39 | `EXP_Operator1Expr` |
| EXP_Operator2Expr.h | 44 | `EXP_Operator2Expr` |
| EXP_PyObjectPlus.h | 623 | `EXP_PyObjectPlus` |
| EXP_Python.h | 80 |  |
| EXP_PythonCallBack.h | 55 |  |
| EXP_StringValue.h | 56 | `EXP_StringValue` |
| EXP_Value.h | 202 | `EXP_Value`, `EXP_PropValue` |

## source/source/gameengine/Expressions/intern

| arquivo | linhas | classes |
|---|---:|---|
| BaseListValue.cpp | 622 | `EXP_BaseListValue` |
| BaseListWrapper.cpp | 418 | `EXP_BaseListWrapper` |
| BoolValue.cpp | 168 | `EXP_BoolValue` |
| ConstExpr.cpp | 51 | `EXP_ConstExpr` |
| EmptyValue.cpp | 60 | `EXP_EmptyValue` |
| ErrorValue.cpp | 82 | `EXP_ErrorValue` |
| Expression.cpp | 27 |  |
| FloatValue.cpp | 372 | `EXP_FloatValue` |
| IdentifierExpr.cpp | 66 | `EXP_IdentifierExpr` |
| IfExpr.cpp | 69 | `EXP_IfExpr` |
| InputParser.cpp | 702 | `EXP_Parser` |
| IntValue.cpp | 334 | `EXP_IntValue` |
| Operator1Expr.cpp | 54 | `EXP_Operator1Expr` |
| Operator2Expr.cpp | 61 | `EXP_Operator2Expr` |
| PyObjectPlus.cpp | 1290 | `EXP_PyObjectPlus` |
| PythonCallBack.cpp | 205 |  |
| StringValue.cpp | 127 | `EXP_StringValue` |
| Value.cpp | 415 | `EXP_Value` |

## source/source/blender/python

| arquivo | linhas | classes |
|---|---:|---|
| BPY_extern.h | 105 |  |
| BPY_extern_clog.h | 31 |  |

## source/source/blender/python/bmesh

| arquivo | linhas | classes |
|---|---:|---|
| bmesh_py_api.c | 222 |  |
| bmesh_py_api.h | 29 |  |
| bmesh_py_geometry.c | 104 |  |
| bmesh_py_geometry.h | 29 |  |
| bmesh_py_ops.c | 346 |  |
| bmesh_py_ops.h | 29 |  |
| bmesh_py_ops_call.c | 775 |  |
| bmesh_py_ops_call.h | 35 |  |
| bmesh_py_types.c **grande** | 4079 |  |
| bmesh_py_types.h | 222 |  |
| bmesh_py_types_customdata.c | 1163 |  |
| bmesh_py_types_customdata.h | 75 |  |
| bmesh_py_types_meshdata.c | 799 |  |
| bmesh_py_types_meshdata.h | 61 |  |
| bmesh_py_types_select.c | 458 |  |
| bmesh_py_types_select.h | 52 |  |
| bmesh_py_utils.c | 842 |  |
| bmesh_py_utils.h | 29 |  |

## source/source/blender/python/generic

| arquivo | linhas | classes |
|---|---:|---|
| bgl.c **grande** | 3768 |  |
| bgl.h | 57 |  |
| blf_py_api.c | 464 |  |
| blf_py_api.h | 26 |  |
| bpy_internal_import.c | 373 |  |
| bpy_internal_import.h | 56 |  |
| bpy_threads.c | 50 |  |
| idprop_py_api.c **grande** | 1801 |  |
| idprop_py_api.h | 77 |  |
| imbuf_py_api.c | 467 |  |
| imbuf_py_api.h | 28 |  |
| py_capi_utils.c **grande** | 1540 |  |
| py_capi_utils.h | 153 |  |
| python_utildefines.h | 55 |  |

## source/source/blender/python/intern

| arquivo | linhas | classes |
|---|---:|---|
| bpy.c | 374 |  |
| bpy.h | 33 |  |
| bpy_app.c | 426 |  |
| bpy_app.h | 26 |  |
| bpy_app_alembic.c | 107 |  |
| bpy_app_alembic.h | 29 |  |
| bpy_app_build_options.c | 312 |  |
| bpy_app_build_options.h | 26 |  |
| bpy_app_ffmpeg.c | 141 |  |
| bpy_app_ffmpeg.h | 26 |  |
| bpy_app_handlers.c | 339 |  |
| bpy_app_handlers.h | 26 |  |
| bpy_app_ocio.c | 107 |  |
| bpy_app_ocio.h | 26 |  |
| bpy_app_oiio.c | 107 |  |
| bpy_app_oiio.h | 26 |  |
| bpy_app_opensubdiv.c | 104 |  |
| bpy_app_opensubdiv.h | 26 |  |
| bpy_app_openvdb.c | 110 |  |
| bpy_app_openvdb.h | 29 |  |
| bpy_app_sdl.c | 143 |  |
| bpy_app_sdl.h | 26 |  |
| bpy_app_translations.c | 820 |  |
| bpy_app_translations.h | 27 |  |
| bpy_capi_utils.c | 145 |  |
| bpy_capi_utils.h | 47 |  |
| bpy_driver.c | 667 |  |
| bpy_driver.h | 34 |  |
| bpy_interface.c | 1034 |  |
| bpy_interface_atexit.c | 91 |  |
| bpy_intern_string.c | 79 |  |
| bpy_intern_string.h | 41 |  |
| bpy_library.h | 27 |  |
| bpy_library_load.c | 482 |  |
| bpy_library_write.c | 217 |  |
| bpy_operator.c | 445 |  |
| bpy_operator.h | 34 |  |
| bpy_operator_wrap.c | 196 |  |
| bpy_operator_wrap.h | 33 |  |
| bpy_path.c | 60 |  |
| bpy_path.h | 27 |  |
| bpy_props.c **grande** | 3518 |  |
| bpy_props.h | 44 |  |
| bpy_rna.c **grande** | 8553 |  |
| bpy_rna.h | 225 |  |
| bpy_rna_anim.c | 508 |  |
| bpy_rna_anim.h | 34 |  |
| bpy_rna_array.c | 953 |  |
| bpy_rna_callback.c | 331 |  |
| bpy_rna_callback.h | 35 |  |
| bpy_rna_driver.c | 104 |  |
| bpy_rna_driver.h | 33 |  |
| bpy_rna_id_collection.c | 295 |  |
| bpy_rna_id_collection.h | 26 |  |
| bpy_rna_types_capi.c | 128 |  |
| bpy_rna_types_capi.h | 26 |  |
| bpy_traceback.c | 181 |  |
| bpy_traceback.h | 27 |  |
| bpy_utils_previews.c | 182 |  |
| bpy_utils_previews.h | 26 |  |
| bpy_utils_units.c | 333 |  |
| bpy_utils_units.h | 26 |  |
| gpu.c | 358 |  |
| gpu.h | 33 |  |
| gpu_offscreen.c | 410 |  |
| stubs.c | 40 |  |

## source/source/blender/python/mathutils

| arquivo | linhas | classes |
|---|---:|---|
| mathutils.c | 731 |  |
| mathutils.h | 174 | `Mathutils_Callback` |
| mathutils_Color.c | 1028 |  |
| mathutils_Color.h | 54 |  |
| mathutils_Euler.c | 825 |  |
| mathutils_Euler.h | 56 |  |
| mathutils_Matrix.c **grande** | 3206 |  |
| mathutils_Matrix.h | 92 |  |
| mathutils_Quaternion.c | 1395 |  |
| mathutils_Quaternion.h | 52 |  |
| mathutils_Vector.c **grande** | 3084 |  |
| mathutils_Vector.h | 54 |  |
| mathutils_bvhtree.c | 1319 |  |
| mathutils_bvhtree.h | 43 |  |
| mathutils_geometry.c **grande** | 1533 |  |
| mathutils_geometry.h | 26 |  |
| mathutils_interpolate.c | 132 |  |
| mathutils_interpolate.h | 26 |  |
| mathutils_kdtree.c | 485 |  |
| mathutils_kdtree.h | 29 |  |
| mathutils_noise.c | 913 |  |
| mathutils_noise.h | 28 |  |
